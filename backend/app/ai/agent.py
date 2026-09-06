"""龙马视界 AI Agent - 智能助手核心

Agent 特性：
1. 工具调用：AI 可以调用数据库查询和管理工具
2. 记忆功能：记住之前的对话和工具调用结果，避免重复调用
3. 权限感知：根据用户角色限制可用工具
4. 流式输出：支持 SSE 流式响应
5. 二次确认：管理员执行写操作前必须确认
"""

import json
import inspect
import logging
import re
import time
import uuid
from typing import Optional, AsyncGenerator

from sqlalchemy.orm import Session

from backend.app.ai.base import AIAdapter, get_adapter
from backend.app.ai.agent_tools import AgentTools
from backend.app.ai.skills._base import build_user_context
from backend.app.models.user import User
from backend.app.repositories.user_repo import UserRepository

logger = logging.getLogger(__name__)


class AgentMemory:
    """Agent 记忆模块 - 存储会话历史和工具调用记录"""

    def __init__(self, max_history: int = 20):
        self.max_history = max_history
        self.conversation_history: list[dict] = []
        self.tool_call_cache: dict[str, dict] = {}
        self.fact_memory: list[str] = []

    def add_message(self, role: str, content: str) -> None:
        self.conversation_history.append({"role": role, "content": content})
        if len(self.conversation_history) > self.max_history * 2:
            self.conversation_history = self.conversation_history[-self.max_history * 2:]

    def add_tool_result(self, tool_name: str, args: dict, result: str) -> None:
        cache_key = f"{tool_name}:{json.dumps(args, sort_keys=True, ensure_ascii=False)}"
        self.tool_call_cache[cache_key] = {
            "result": result,
            "timestamp": time.time(),
        }

    def get_cached_result(self, tool_name: str, args: dict) -> Optional[str]:
        cache_key = f"{tool_name}:{json.dumps(args, sort_keys=True, ensure_ascii=False)}"
        cached = self.tool_call_cache.get(cache_key)
        if cached:
            if time.time() - cached["timestamp"] < 300:
                return cached["result"]
            else:
                del self.tool_call_cache[cache_key]
        return None

    def remember_fact(self, fact: str) -> None:
        if fact not in self.fact_memory:
            self.fact_memory.append(fact)
            if len(self.fact_memory) > 50:
                self.fact_memory = self.fact_memory[-50:]

    def get_memory_context(self) -> str:
        parts = []
        if self.fact_memory:
            parts.append("## 你记住的事实")
            for fact in self.fact_memory[-10:]:
                parts.append(f"- {fact}")
            parts.append("")
        return "\n".join(parts)

    def get_recent_context(self, limit: int = 6) -> list[dict]:
        return self.conversation_history[-limit:]

    def clear(self) -> None:
        self.conversation_history.clear()
        self.tool_call_cache.clear()
        self.fact_memory.clear()


class LongmaAgent:
    """龙马视界 AI Agent"""

    # 标记工具调用模式
    TOOL_BLOCK_PATTERN = re.compile(
        r'```tool\s*\n(.*?)\n```',
        re.DOTALL
    )

    def __init__(self, db: Session, user_id: int, memory: Optional[AgentMemory] = None):
        self.db = db
        self.user_id = user_id
        self.tools = AgentTools(db, user_id)
        self.memory = memory or AgentMemory()
        self._user: User | None = None
        self._pending_confirmations: dict[str, dict] = {}

    @property
    def user(self):
        if self._user is None:
            self._user = UserRepository.get_by_id(self.db, self.user_id)
        return self._user

    @property
    def user_role(self) -> str:
        return self.user.role if self.user else "unknown"

    @property
    def is_admin(self) -> bool:
        return self.user_role == "admin"

    @property
    def is_teacher(self) -> bool:
        return self.user_role == "teacher"

    def _build_system_prompt(self) -> str:
        user_info = {
            "id": self.user.id if self.user else 0,
            "name": self.user.name if self.user else "未知",
            "student_no": self.user.student_no if self.user else "未知",
            "role": self.user_role,
            "status": self.user.status if self.user else "unknown",
        }
        user_context = build_user_context(user_info)
        tools_desc = AgentTools.get_tools_description()
        memory_context = self.memory.get_memory_context()

        pending_text = ""
        if self._pending_confirmations:
            pending_lines = ["\n## 待确认的操作"]
            for op_id, op in self._pending_confirmations.items():
                pending_lines.append(f"- [{op_id}] {op['description']}")
            pending_lines.append("请在用户明确回复「确认执行」后再执行对应操作。")
            pending_text = "\n".join(pending_lines)

        return f"""你是「龙马·视界」平台的 AI Agent 助手。你可以帮助用户查询和管理平台数据。

{user_context}

{tools_desc}

## 业务 Skill 调度

当用户需要竞赛推荐、导师匹配、党建查询或成果管理时，分别调用
`recommend_competitions`、`match_mentors`、`query_party`、`manage_achievements`。
业务工具已经执行权限检查和调用审计；必须使用工具返回的数据作答，不得自行补造业务数据。

## 工具调用方式

当你需要调用工具时，请使用以下格式：

```tool
{{"tool": "工具名", "args": {{"参数1": "值1", "参数2": "值2"}}}}
```

## 安全规则

1. **只读操作**：查询类工具可以直接调用
2. **写操作**：管理类工具（以 admin_ 开头）必须先向用户说明操作内容和影响，等待用户明确确认后再执行
3. **权限检查**：如果用户无权使用某个工具，请告知用户权限不足
4. **记忆利用**：在回答前先检查你记住的事实，避免重复询问相同问题

## 回答风格

- 简洁、专业、友好
- 使用中文回答
- 适当使用表格展示数据
- 如果调用了工具，请在回复中自然地整合工具返回的结果

{memory_context}
{pending_text}
"""

    def _build_context_messages(self, user_content: str) -> list[dict]:
        messages = self.memory.get_recent_context(limit=6)
        messages.append({"role": "user", "content": user_content})
        return messages

    async def chat_stream(
        self,
        user_content: str,
        adapter: Optional[AIAdapter] = None,
    ) -> AsyncGenerator[str, None]:
        """流式对话，支持工具调用"""
        if adapter is None:
            adapter = get_adapter()

        system_prompt = self._build_system_prompt()
        context_messages = self._build_context_messages(user_content)

        # 检查是否为确认指令
        confirm_result = self._check_confirmation(user_content)
        if confirm_result:
            async for chunk in self._stream_text(adapter, confirm_result, system_prompt, context_messages):
                yield chunk
            return

        full_response = ""
        try:
            async for chunk in adapter.chat_stream(context_messages, system_prompt=system_prompt):
                full_response += chunk
                yield chunk
        except Exception as e:
            logger.exception("Agent stream error: user_id=%s", self.user_id)
            yield f"\n[AI 回复失败: {e}]"
            return

        # 处理工具调用
        tool_calls = self._extract_tool_calls(full_response)
        for tool_call in tool_calls:
            tool_result = await self._execute_tool_call(tool_call)
            if tool_result:
                # 将工具结果注入到对话中
                tool_result_msg = f"\n\n[工具执行结果]\n{tool_result}"
                yield tool_result_msg

                # 用工具结果继续对话
                follow_up_messages = context_messages + [
                    {"role": "assistant", "content": full_response},
                    {"role": "user", "content": f"请根据工具执行结果回答用户的问题。\n\n工具结果：{tool_result}"},
                ]

                follow_up_response = ""
                try:
                    async for chunk in adapter.chat_stream(follow_up_messages, system_prompt=system_prompt):
                        follow_up_response += chunk
                        yield chunk
                except Exception as e:
                    logger.exception("Follow-up stream error: user_id=%s", self.user_id)
                    yield f"\n[处理工具结果时出错: {e}]"

                full_response += tool_result_msg + follow_up_response

        # 更新记忆
        self.memory.add_message("user", user_content)
        self.memory.add_message("assistant", full_response)

        # 尝试从对话中提取事实
        self._extract_and_store_facts(full_response)

    async def chat(
        self,
        user_content: str,
        adapter: Optional[AIAdapter] = None,
    ) -> str:
        """非流式对话"""
        chunks = []
        async for chunk in self.chat_stream(user_content, adapter):
            chunks.append(chunk)
        return "".join(chunks)

    async def _stream_text(
        self,
        adapter: AIAdapter,
        text: str,
        system_prompt: str,
        context_messages: list[dict],
    ) -> AsyncGenerator[str, None]:
        """直接输出文本，不调用 AI"""
        yield text

    def _extract_tool_calls(self, response: str) -> list[dict]:
        """从 AI 响应中提取工具调用指令"""
        tool_calls = []

        # 方法1: 匹配 ```tool ... ``` 代码块
        matches = self.TOOL_BLOCK_PATTERN.findall(response)
        for match in matches:
            try:
                tool_call = json.loads(match.strip())
                if "tool" in tool_call and "args" in tool_call:
                    tool_calls.append(tool_call)
            except json.JSONDecodeError:
                # 尝试从匹配内容中提取 JSON 对象
                json_obj = self._extract_json_object(match.strip())
                if json_obj:
                    tool_calls.append(json_obj)

        # 方法2: 直接在文本中查找 JSON 对象
        if not tool_calls:
            json_obj = self._extract_json_object(response)
            if json_obj and "tool" in json_obj:
                tool_calls.append(json_obj)

        return tool_calls

    def _extract_json_object(self, text: str) -> Optional[dict]:
        """从文本中提取 JSON 对象（处理嵌套大括号）"""
        # 找到第一个 '{' 并提取完整的 JSON 对象
        start = text.find('{')
        if start == -1:
            return None

        # 使用大括号计数法提取完整的 JSON 对象
        depth = 0
        for i in range(start, len(text)):
            if text[i] == '{':
                depth += 1
            elif text[i] == '}':
                depth -= 1
                if depth == 0:
                    json_str = text[start:i+1]
                    try:
                        obj = json.loads(json_str)
                        if isinstance(obj, dict) and "tool" in obj:
                            return obj
                    except json.JSONDecodeError:
                        pass
                    return None
        return None

    async def _execute_tool_call(self, tool_call: dict) -> Optional[str]:
        """执行工具调用"""
        tool_name = tool_call.get("tool", "")
        args = tool_call.get("args", {})

        # 检查缓存
        business_tools = {
            "recommend_competitions",
            "match_mentors",
            "query_party",
            "manage_achievements",
        }
        cached = None if tool_name in business_tools else self.memory.get_cached_result(tool_name, args)
        if cached:
            return cached

        # 检查工具是否存在
        if not hasattr(self.tools, tool_name):
            return json.dumps({"error": f"未知工具: {tool_name}"}, ensure_ascii=False)

        # 检查是否为写操作（管理员工具）
        if tool_name.startswith("admin_"):
            # 检查该操作是否已经被确认（在 _pending_confirmations 中查找匹配的操作）
            confirmed = False
            for op_id, op_data in list(self._pending_confirmations.items()):
                if op_data["tool"] == tool_name and op_data["args"] == args:
                    # 找到了匹配的待确认操作，执行它
                    del self._pending_confirmations[op_id]
                    confirmed = True
                    break

            if not confirmed:
                # 创建待确认操作
                op_id = f"{tool_name}_{int(time.time())}"
                self._pending_confirmations[op_id] = {
                    "tool": tool_name,
                    "args": args,
                    "description": self._describe_operation(tool_name, args),
                    "timestamp": time.time(),
                }
                return json.dumps({
                    "status": "pending_confirmation",
                    "message": f"⚠️ 这是一个写操作，需要您确认后才能执行。\n\n操作描述：{self._describe_operation(tool_name, args)}\n\n请回复「确认执行」以继续。",
                    "tool": tool_name,
                    "args": args,
                }, ensure_ascii=False, indent=2)

        # 执行工具
        try:
            tool_func = getattr(self.tools, tool_name)
            result = tool_func(**args)
            if inspect.isawaitable(result):
                result = await result
            if not isinstance(result, str):
                result = json.dumps(result, ensure_ascii=False, default=str)

            # 缓存结果
            self.memory.add_tool_result(tool_name, args, result)

            # 记住事实
            self._remember_tool_result(tool_name, args, result)

            return result
        except Exception as e:
            logger.error("Tool execution error: %s.%s: %s", tool_name, args, e)
            return json.dumps({"error": f"工具执行失败: {str(e)}"}, ensure_ascii=False)

    def _check_confirmation(self, user_content: str) -> Optional[str]:
        """检查用户是否在确认待执行的操作"""
        if not self._pending_confirmations:
            return None

        content_lower = user_content.lower().strip()

        # 检查确认关键词
        confirm_keywords = ["确认执行", "确认", "执行", "确定", "ok", "yes", "confirm"]
        if any(kw in content_lower for kw in confirm_keywords):
            # 执行所有待确认的操作
            results = []
            to_execute = list(self._pending_confirmations.items())

            for op_id, op in to_execute:
                tool_name = op["tool"]
                args = op["args"]

                if hasattr(self.tools, tool_name):
                    try:
                        tool_func = getattr(self.tools, tool_name)
                        result = tool_func(**args)
                        results.append(f"✅ {op['description']}: 执行成功")
                        results.append(result)
                    except Exception as e:
                        results.append(f"❌ {op['description']}: 执行失败 - {str(e)}")

                del self._pending_confirmations[op_id]

            if results:
                return "操作已执行：\n\n" + "\n".join(results)

        return None

    def _is_operation_confirmed(self, tool_name: str, args: dict) -> bool:
        """检查操作是否已确认"""
        # 简化实现：如果有待确认的操作列表，则需要确认
        # 实际确认通过 _check_confirmation 处理
        return len(self._pending_confirmations) == 0

    def _describe_operation(self, tool_name: str, args: dict) -> str:
        """生成操作描述"""
        descriptions = {
            "admin_create_user": f"创建新用户：学号={args.get('student_no')}, 姓名={args.get('name')}, 角色={args.get('role', 'student')}",
            "admin_reset_password": f"重置用户密码：用户ID={args.get('user_id')}",
            "admin_update_user_status": f"更新用户状态：用户ID={args.get('user_id')}, 新状态={args.get('status')}",
            "admin_delete_user": f"删除用户：用户ID={args.get('user_id')}",
            "admin_approve_achievement": f"审核成果：成果ID={args.get('achievement_id')}, 通过={args.get('approve', True)}",
            "admin_approve_resource": f"审核资源：资源ID={args.get('resource_id')}, 通过={args.get('approve', True)}",
        }
        return descriptions.get(tool_name, f"执行管理操作: {tool_name}({json.dumps(args, ensure_ascii=False)})")

    def _remember_tool_result(self, tool_name: str, args: dict, result: str) -> None:
        """从工具结果中提取事实并记住"""
        try:
            data = json.loads(result) if isinstance(result, str) else result

            # 用户相关事实
            if tool_name == "get_user_info" and "name" in data:
                fact = f"用户 {data.get('name')} (ID:{data.get('id')}) 的角色是 {data.get('role')}"
                self.memory.remember_fact(fact)

            if tool_name == "count_users" and "total" in data:
                fact = f"当前系统共有 {data['total']} 个用户"
                self.memory.remember_fact(fact)

        except (json.JSONDecodeError, TypeError):
            pass

    def _extract_and_store_facts(self, response: str) -> None:
        """从 AI 回复中提取有用的事实"""
        # 简单事实提取：查找陈述性语句
        facts_patterns = [
            r'(?:你|您)?(?:是|叫)\s+(\S+?)[，,。.]',
            r'(?:我|我们)(?:有|共)\s+(\d+)\s+(?:个|位)\s+(\S+?)[，,。.]',
        ]
        for pattern in facts_patterns:
            matches = re.findall(pattern, response)
            for match in matches:
                if isinstance(match, tuple):
                    fact = " ".join(match)
                else:
                    fact = match
                if len(fact) > 5 and len(fact) < 100:
                    self.memory.remember_fact(fact)

    def get_confirmation_status(self) -> list[dict]:
        """获取当前待确认的操作列表"""
        return [
            {
                "id": op_id,
                "tool": op["tool"],
                "description": op["description"],
            }
            for op_id, op in self._pending_confirmations.items()
        ]

    def cancel_all_confirmations(self) -> str:
        """取消所有待确认的操作"""
        count = len(self._pending_confirmations)
        self._pending_confirmations.clear()
        return f"已取消 {count} 个待确认的操作"

    def get_memory_stats(self) -> dict:
        """获取记忆统计"""
        return {
            "conversation_messages": len(self.memory.conversation_history),
            "cached_tool_calls": len(self.memory.tool_call_cache),
            "remembered_facts": len(self.memory.fact_memory),
            "pending_confirmations": len(self._pending_confirmations),
        }
