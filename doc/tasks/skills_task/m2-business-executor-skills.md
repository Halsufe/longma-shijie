# M2 业务 Skill 执行层（Business Skill Executor）

> 输入文档：`../../skills_proposal.md`（第 3.3、3.7 章）、`../../skills_design.md`（4.2）  
> 前置依赖：M1（调度入口）  
> 完成定义：4 个业务 Skill 有统一执行入口，结构化结果可转自然语言回复，调用记录完整。

## 任务清单

- [x] T2-1 执行器基类与注册表
  - 交付物：`backend/app/ai/business_skills/base.py` 定义 `BusinessSkillExecutor`；`backend/app/ai/business_skills/__init__.py` 定义 `BUSINESS_SKILL_REGISTRY`。
  - 验收：4 个业务 Skill 名称均可映射到执行器类。
- [x] T2-2 BusinessSkillService 分流与生成
  - 交付物：`backend/app/ai/business_skills/service.py` 实现 `execute(skill_name, user_input, user, db)`：解析意图、调用执行器、交给 AI 生成回复。
  - 验收：`@触发词` 与 `@agent` 两条路径调用同一服务方法。
- [x] T2-3 AgentTools 业务工具接线
  - 交付物：`backend/app/ai/agent_tools.py` 新增 `recommend_competitions`、`match_mentors` 及党建/成果业务工具占位，调用业务执行逻辑；`backend/app/ai/agent.py` 补充工具描述。
  - 验收：Agent 可通过工具调用 4 类业务能力，工具结果可注入对话。
- [x] T2-4 skill_calls 记录
  - 交付物：业务执行完成统一写入 `skill_calls`；`@agent` 路径按具体业务 Skill 名记录（如 `competition_recommend`），不再统一记 `agent`。
  - 验收：每条业务调用都有 `skill_name/user_id/input/output/status/duration_ms`。
- [x] T2-5 测试
  - 交付物：`backend/tests/test_business_skills_executor.py`。
  - 验收：双通道分流、调用记录、错误状态、权限拒绝断言全部通过。
