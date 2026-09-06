# E6 通知与依赖适配扩展（Notification & Dependency Adapter）

> 输入文档：`../dangjian/dangjian_politic_proposal.md`（第 11 章）、`../dangjian/dangjian_politic_design.md`（2、4.6、6）  
> 前置依赖：E1、E2、E3、现有通知中心/知识库/Agent 工具  
> 完成定义：政治面貌审核通过只通知本人，Workflow 事件边界与 Skill 只读接口扩展就绪，政治学习资料按适用对象进入知识库。

## 任务清单

- [x] E6-1 政治面貌审核通知
  - 交付物：`party_notify_adapter.py` 支持 `type=political_status_change`、`ref_type=political_status_review`；幂等沿用 `type + ref_type + ref_id`；只通知本人。
  - 验收：审核通过后本人收到通知，其他角色不收到。
- [x] E6-2 Workflow 事件边界
  - 交付物：`party_workflow_events.py` 增加 `party.political_status_approved` 事件常量与载荷定义。
  - 验收：事件定义可被调度器直接引用，不实现调度逻辑。
- [x] E6-3 Skill 只读接口扩展
  - 交付物：`party_skill_boundary.py` 增加 `get_my_political_status`、`list_political_learning_materials`；团学活动复用既有活动工具；管理员可查询政治面貌统计。
  - 验收：权限校验生效，写操作不开放。
- [x] E6-4 知识库适配
  - 交付物：政治学习资料按适用对象进入 `class` 知识库；“指定人员”资料排除。
  - 验收：公开资料可被 RAG 检索，指定人员资料不进入。
- [x] E6-5 测试
  - 交付物：`backend/tests/test_political_dependency_adapter.py`。
  - 验收：通知幂等、事件常量、Skill 权限、知识库过滤断言通过。
