# M1 Skill 注册与调度（Skill Registry & Dispatcher）

> 输入文档：`../../skills_proposal.md`（第 3.1、3.2、11 章）、`../../skills_design.md`（4.1、5.3）  
> 前置依赖：无  
> 完成定义：4 个业务 Skill 可注册、可触发、可启停，`@agent` 优先级正确，旧 Skill 行为不回归。

## 任务清单

- [x] T1-1 业务 Skill 种子数据
  - 交付物：`backend/app/repositories/skill_repo.py` 的 `SYSTEM_SKILLS` 新增 `competition_recommend`、`mentor_match`、`party_query`、`achievement_manage`，`category=business`，触发词与设计 5.3 一致。
  - 验收：清库启动后 4 个 Skill 写入 `skills` 表，可重复启动不重复插入。
- [x] T1-2 兜底触发词与解析优先级
  - 交付物：`backend/app/ai/skill_dispatcher.py` 的 `SKILL_TRIGGERS` 补充 4 个业务触发词；`ChatService` 保持 `@agent` 前缀优先于业务 Skill 触发词。
  - 验收：`@agent` 消息进入 Agent 模式；`@竞赛推荐` 等命中对应 Skill；多个触发词命中时取注册顺序第一个。
- [x] T1-3 业务 Prompt 构建器注册
  - 交付物：新增 `backend/app/ai/skills/competition_recommend.py`、`mentor_match.py`、`party_query.py`、`achievement_manage.py`，并在 `backend/app/ai/skills/__init__.py` 的 `SKILL_PROMPT_BUILDERS` 注册。
  - 验收：`get_skill_prompt("competition_recommend", input)` 等返回业务专用提示词。
- [x] T1-4 ChatService 业务 Skill 分流
  - 交付物：`backend/app/services/chat_service.py` 的 `send_message_stream` 与 `send_message_simple` 在解析到业务 Skill 后调用 `BusinessSkillService`；权限检查沿用 `_check_skill_permission`。
  - 验收：业务 Skill 消息不落入普通 prompt 聊天路径，返回结构化业务结果。
- [x] T1-5 测试
  - 交付物：`backend/tests/test_skills_registry.py`。
  - 验收：种子、触发解析、优先级、权限、旧 Skill 回归断言全部通过。
