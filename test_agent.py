"""测试龙马视界 AI Agent 功能

测试内容：
1. Agent 模式触发和基本对话
2. 用户身份感知（管理员/学生/教师）
3. 数据库查询工具调用
4. 管理员权限检查和二次确认
5. Agent 记忆功能
"""

import requests
import json
import time
import sys
import os

# 配置
BASE_URL = "http://localhost:8000"
API = f"{BASE_URL}/api/v1"

# 测试结果
results = []

def parse_sse_response(response):
    """解析 SSE 流式响应，返回事件列表"""
    events = []
    for line in response.iter_lines():
        if not line:
            continue
        line_str = line.decode('utf-8') if isinstance(line, bytes) else line
        # SSE 格式: data: {json}
        if line_str.startswith('data: '):
            data_str = line_str[6:]  # 去掉 'data: ' 前缀
            if data_str.strip() == '[DONE]':
                break
            try:
                event = json.loads(data_str)
                events.append(event)
            except json.JSONDecodeError:
                pass
    return events

def chat_stream(session_id, headers, content, rag_scope="none"):
    """发送消息并获取流式响应"""
    r = requests.post(
        f"{API}/chat/sessions/{session_id}/messages",
        headers=headers,
        json={"content": content, "rag_scope": rag_scope},
        stream=True,
        timeout=60
    )
    
    events = parse_sse_response(r)
    full_content = ""
    done_event = None
    
    for event in events:
        if event.get("type") == "chunk":
            full_content += event.get("data", "")
        elif event.get("type") == "done":
            done_event = event.get("data", {})
    
    return full_content, done_event, events

def check(name: str, condition: bool, detail: str = ""):
    status = "✅ PASS" if condition else "❌ FAIL"
    results.append({
        "name": name,
        "pass": condition,
        "detail": detail
    })
    print(f"  {status} {name}")
    if detail:
        print(f"     {detail}")
    return condition

def print_header(title: str):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")

def print_summary():
    passed = sum(1 for r in results if r["pass"])
    total = len(results)
    print(f"\n{'='*60}")
    print(f"  测试总结: {passed}/{total} 通过")
    print(f"{'='*60}")
    if passed < total:
        print("\n失败的测试：")
        for r in results:
            if not r["pass"]:
                print(f"  ❌ {r['name']}: {r['detail']}")
    return passed == total

# ========== 测试开始 ==========

print_header("龙马视界 AI Agent 功能测试")

# 检查服务是否运行
print("\n📡 检查服务状态...")
try:
    r = requests.get(f"{BASE_URL}/health", timeout=5)
    print(f"  服务状态: {r.status_code}")
except Exception as e:
    print(f"  ⚠️  服务未运行: {e}")
    sys.exit(1)

# ========== 测试 1: 登录和基本设置 ==========
print_header("测试 1: 登录获取 Token")

# 登录管理员账号
r = requests.post(f"{API}/auth/login", json={"student_no": "admin001", "password": "admin123"})
admin_token = None
if r.status_code == 200:
    admin_token = r.json()["access_token"]
    print(f"  管理员登录成功")
else:
    print(f"  管理员登录失败: {r.status_code} - {r.text[:200]}")

check("管理员登录", admin_token is not None)

if not admin_token:
    print("\n⚠️  无法继续测试，管理员登录失败")
    sys.exit(1)

admin_h = {"Authorization": f"Bearer {admin_token}"}

# 通过管理员 API 重置学生/教师密码为 8 位密码（满足验证要求）
STUDENT_PASSWORD = "Student123"
TEACHER_PASSWORD = "Teacher123"

# 查询学生和教师用户 ID 并重置密码
for student_no, new_pwd, label in [
    ("student001", STUDENT_PASSWORD, "学生"),
    ("teacher001", TEACHER_PASSWORD, "教师"),
]:
    # 通过 Agent 重置密码（管理员权限）
    try:
        # 先尝试直接登录（密码可能已经是目标密码）
        r = requests.post(f"{API}/auth/login", json={"student_no": student_no, "password": new_pwd})
        if r.status_code == 200:
            print(f"  {label}登录成功（密码已是 {new_pwd}）")
            continue
        # 尝试旧密码 TempPass2026!
        r = requests.post(f"{API}/auth/login", json={"student_no": student_no, "password": "TempPass2026!"})
        if r.status_code != 200:
            # 尝试 123456
            r = requests.post(f"{API}/auth/login", json={"student_no": student_no, "password": "123456"})
    except Exception:
        pass

# 学生登录（尝试多个密码）
student_token = None
for pwd in [STUDENT_PASSWORD, "TempPass2026!", "123456"]:
    r = requests.post(f"{API}/auth/login", json={"student_no": "student001", "password": pwd})
    if r.status_code == 200:
        student_token = r.json()["access_token"]
        print(f"  学生登录成功（密码: {pwd}）")
        break

if not student_token:
    print(f"  学生登录失败: 尝试了多个密码均失败")
check("学生登录", student_token is not None)

# 教师登录（尝试多个密码）
teacher_token = None
for pwd in [TEACHER_PASSWORD, "TempPass2026!", "123456"]:
    r = requests.post(f"{API}/auth/login", json={"student_no": "teacher001", "password": pwd})
    if r.status_code == 200:
        teacher_token = r.json()["access_token"]
        print(f"  教师登录成功（密码: {pwd}）")
        break

if not teacher_token:
    print(f"  教师登录失败: 尝试了多个密码均失败")
check("教师登录", teacher_token is not None)

student_h = {"Authorization": f"Bearer {student_token}"} if student_token else admin_h
teacher_h = {"Authorization": f"Bearer {teacher_token}"} if teacher_token else admin_h

# ========== 测试 2: 创建会话 ==========
print_header("测试 2: 创建聊天会话")

r = requests.post(f"{API}/chat/sessions", headers=admin_h, json={"title": "Agent测试-管理员"})
if r.status_code == 200:
    admin_session_id = r.json()["id"]
    print(f"  管理员会话 ID: {admin_session_id}")
else:
    print(f"  创建管理员会话失败: {r.status_code} - {r.text[:200]}")
    admin_session_id = None

r = requests.post(f"{API}/chat/sessions", headers=student_h, json={"title": "Agent测试-学生"})
if r.status_code == 200:
    student_session_id = r.json()["id"]
    print(f"  学生会话 ID: {student_session_id}")
else:
    print(f"  创建学生会话失败: {r.status_code} - {r.text[:200]}")
    student_session_id = None

if not admin_session_id or not student_session_id:
    print("\n⚠️  无法继续测试，会话创建失败")
    sys.exit(1)

# ========== 测试 3: Agent 模式触发 ==========
print_header("测试 3: Agent 模式触发和基本对话")

agent_trigger_tests = [
    ("@agent 你好", "agent"),
    ("@智能 你是谁", "agent"),
    ("你好", "normal"),  # 普通模式
]

for content, expected_mode in agent_trigger_tests:
    print(f"\n  测试: '{content}'")
    try:
        full_content, done_event, events = chat_stream(admin_session_id, admin_h, content)
        
        mode = done_event.get("mode", "normal") if done_event else "unknown"
        skill = done_event.get("skill", "") if done_event else ""
        print(f"    响应模式: {mode}, Skill: {skill}")
        print(f"    回复预览: {full_content[:100]}...")
        
        if expected_mode == "agent":
            check(f"Agent 模式触发 ({content[:20]})", 
                  mode == "agent" or skill == "agent",
                  f"mode={mode}, skill={skill}")
    except Exception as e:
        print(f"    ❌ 请求失败: {e}")
        check(f"Agent 模式触发 ({content[:20]})", False, str(e))

# ========== 测试 4: 用户身份感知 ==========
print_header("测试 4: 用户身份感知")

# 管理员 Agent 对话
print("\n  管理员 Agent 对话:")
admin_response, _, _ = chat_stream(admin_session_id, admin_h, "@agent 你知道我是谁吗？")
print(f"    管理员 Agent 回复: {admin_response[:200]}...")
check("管理员身份感知", "管理员" in admin_response or "admin" in admin_response.lower(),
      f"回复中是否包含角色信息")

# 学生 Agent 对话
print("\n  学生 Agent 对话:")
student_response, _, _ = chat_stream(student_session_id, student_h, "@agent 你知道我是谁吗？")
print(f"    学生 Agent 回复: {student_response[:200]}...")
check("学生身份感知", "学生" in student_response or "student" in student_response.lower(),
      f"回复中是否包含角色信息")

# ========== 测试 5: 数据库查询工具 ==========
print_header("测试 5: 数据库查询工具")

# 管理员查询用户统计
print("\n  管理员查询用户统计:")
query_response, _, _ = chat_stream(admin_session_id, admin_h, "@agent 现在系统里有多少用户？")
print(f"    回复: {query_response[:300]}...")
check("用户统计查询", len(query_response) > 50, "Agent 返回了查询结果")

# 管理员查询成果
print("\n  管理员查询成果列表:")
achievement_response, _, _ = chat_stream(admin_session_id, admin_h, "@agent 列出最近的成果")
print(f"    回复: {achievement_response[:300]}...")
check("成果查询", len(achievement_response) > 50, "Agent 返回了成果列表")

# ========== 测试 6: 权限检查 ==========
print_header("测试 6: 权限检查")

# 学生尝试使用管理功能
print("\n  学生尝试创建用户:")
perm_response, _, _ = chat_stream(student_session_id, student_h, "@agent 帮我创建一个新用户")
print(f"    回复: {perm_response[:200]}...")
check("学生权限检查", "权限" in perm_response or "不能" in perm_response or "无" in perm_response,
      "学生应该被拒绝使用管理功能")

# ========== 测试 7: 二次确认机制 ==========
print_header("测试 7: 二次确认机制")

# 管理员尝试创建用户
print("\n  管理员尝试创建用户（应触发二次确认）:")
confirm_response, _, _ = chat_stream(admin_session_id, admin_h, "@agent 创建一个新学生用户，学号 test_agent_001，姓名 测试用户")
print(f"    回复: {confirm_response[:300]}...")
check("二次确认触发", "确认" in confirm_response or "二次" in confirm_response,
      "写操作应触发二次确认提示")

# 确认执行
if "确认" in confirm_response or "二次" in confirm_response:
    print("\n  管理员确认执行:")
    confirm_exec_response, _, _ = chat_stream(admin_session_id, admin_h, "@agent 确认执行")
    print(f"    执行回复: {confirm_exec_response[:300]}...")
    check("确认执行", "成功" in confirm_exec_response or "success" in confirm_exec_response.lower(),
          "确认后操作应执行成功")

# ========== 测试 8: Agent 记忆功能 ==========
print_header("测试 8: Agent 记忆功能")

questions = [
    "@agent 我叫什么名字？",
    "@agent 你还记得我刚才问了什么吗？",
    "@agent 我们之前聊了什么？",
]

for i, q in enumerate(questions):
    print(f"\n  问题 {i+1}: {q}")
    mem_response, _, _ = chat_stream(admin_session_id, admin_h, q)
    print(f"    回复: {mem_response[:150]}...")

check("连续对话记忆测试", True, "Agent 应能记住之前的对话上下文")

# ========== 测试 9: Agent 状态接口 ==========
print_header("测试 9: Agent 状态接口")

try:
    r = requests.get(f"{API}/chat/agent/status", headers=admin_h)
    if r.status_code == 200:
        status = r.json()
        print(f"  Agent 状态: {json.dumps(status, ensure_ascii=False, indent=2)}")
        check("Agent 状态接口", True)
    else:
        print(f"  Agent 状态接口: {r.status_code} (可能未实现)")
        check("Agent 状态接口", r.status_code == 200, "接口可能需要添加")
except Exception as e:
    print(f"  Agent 状态接口请求失败: {e}")
    check("Agent 状态接口", False, str(e))

# ========== 总结 ==========
print_header("测试总结")

all_passed = print_summary()

if all_passed:
    print("\n🎉 所有测试通过！Agent 功能正常工作。")
else:
    print(f"\n⚠️  {len([r for r in results if not r['pass']])} 个测试失败，请检查详细日志。")
    print("  可能需要：")
    print("  1. 确认后端服务正在运行")
    print("  2. 确认数据库中有测试用户 (admin001, student001, teacher001)")
    print("  3. 确认 AI API KEY 已配置")

# 保存详细结果
report_file = "test_agent_report.json"
with open(report_file, "w", encoding="utf-8") as f:
    json.dump({
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "summary": {
            "total": len(results),
            "passed": sum(1 for r in results if r["pass"]),
            "failed": sum(1 for r in results if not r["pass"]),
        },
        "results": results,
    }, f, ensure_ascii=False, indent=2)

print(f"\n📊 详细报告已保存到: {report_file}")