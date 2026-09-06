# M7 通知与依赖适配模块（Notification & Dependency Adapter）

> 输入文档：`../dangjian/dangjian_proposal.md`（第 11 章）、`../dangjian/dangjian_design.md`（4.7、6）  
> 前置依赖：M1、M2、M3、现有通知中心/知识库/Agent 工具  
> 完成定义：通知落库且幂等，学习材料可进班级知识库，Skill 查询接口边界与 Workflow 事件定义就绪。

## 任务清单

- [x] T7-1 通知适配器
  - 交付物：`party_notify_adapter.py`；party_activity_notice/party_activity_reminder/party_status_change；幂等 type + ref_type + ref_id。
  - 验收：重复发布不产生重复通知。
- [x] T7-2 发布/流转通知接入
  - 交付物：活动 publish、阶段流转、报名/签到结果调用通知适配器。
  - 验收：各场景通知落库，目标用户正确。
- [x] T7-3 知识库适配器
  - 交付物：`party_knowledge_adapter.py`；活动学习材料写入 class 知识库；发展材料排除。
  - 验收：学习材料可被 RAG 检索，涉敏材料不进入。
- [x] T7-4 Skill 查询接口边界
  - 交付物：`party_skill_boundary.py` 定义 list_party_members/get_party_member/list_party_activities/get_party_activity/get_party_my_records 只读工具契约与权限。
  - 验收：契约与权限列与设计 4.7.3 一致，本期不注册写工具。
- [x] T7-5 Workflow 触发事件定义
  - 交付物：设计 4.7.2 的 5 个事件（事件名/载荷/落点）落地为常量与文档，供 Workflow 模块接入。
  - 验收：事件定义可被调度器直接引用。
- [x] T7-6 测试
  - 交付物：`backend/tests/test_party_dependency_adapter.py`。
  - 验收：通知幂等、知识库入库、工具权限断言通过。
