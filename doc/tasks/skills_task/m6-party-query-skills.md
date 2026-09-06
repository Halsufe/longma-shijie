# M6 党建查询 Skill（Party Query）

> 输入文档：`../../skills_proposal.md`（第 6 章）、`../../skills_design.md`（4.6、7.5）  
> 前置依赖：M2、已实现党建模块  
> 完成定义：用户可通过自然语言查询党员/活动/本人记录，全程只读且权限隔离。

## 任务清单

- [x] T6-1 PartyQueryExecutor 包装
  - 交付物：`backend/app/ai/business_skills/party_query.py` 封装 `PartySkillBoundary` 的 5 个只读工具。
  - 验收：不新增写工具，不绕过现有权限。
- [x] T6-2 意图解析
  - 交付物：解析名册、党员详情、活动列表、活动详情、本人记录 5 类意图与筛选参数。
  - 验收：自然语言问题可映射到对应工具。
- [x] T6-3 活动材料 RAG
  - 交付物：询问学习材料时调用 `RAGService.search(scope=class)` 并返回引用来源；涉敏发展材料排除。
  - 验收：引用来源展示正确，发展材料不出现。
- [x] T6-4 Agent 工具接线与 Prompt
  - 交付物：`AgentTools` 新增 `list_party_members`、`get_party_member`、`list_party_activities`、`get_party_activity`、`get_party_my_records` 委托工具；补充 Prompt 说明。
  - 验收：`@agent 党员有多少人` 等可正常查询。
- [x] T6-5 测试
  - 交付物：`backend/tests/test_party_query_skill.py`。
  - 验收：角色隔离、活动可见性、无写操作、RAG 排除断言全部通过。
