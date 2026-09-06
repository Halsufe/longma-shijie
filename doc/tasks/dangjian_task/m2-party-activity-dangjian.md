# M2 党建活动模块（Party Activity Core）

> 输入文档：`../dangjian/dangjian_proposal.md`（第 6、13 章）、`../dangjian/dangjian_design.md`（4.2、5.3、6）  
> 前置依赖：M1（活动对象判定）、M8 迁移（party_activities 表）  
> 完成定义：管理员可创建/编辑/发布/归档活动，活动对象、报名截止、材料与总结字段按设计约束生效。

## 任务清单

- [x] T2-1 PartyActivity 模型与 Schema
  - 交付物：`backend/app/models/party.py` 定义 `PartyActivity`；`backend/app/schemas/party.py` 定义 `PartyActivityCreate/Update/Info`、`PartyActivitySummary`；字段与设计 5.3 一致。
  - 验收：字段、枚举与索引与设计一致。
- [x] T2-2 活动 CRUD 服务与接口
  - 交付物：GET/POST `/api/v1/party/activities`、PUT `/api/v1/party/activities/{id}`；仅 admin 写。
  - 验收：CRUD 正常，普通用户写操作 403。
- [x] T2-3 活动状态机与发布
  - 交付物：draft → published → ongoing → finished → archived 流转；发布时校验 `registration_deadline < start_at`，报名开始后锁定截止/对象/名额；publish 调用 M7 通知适配器。
  - 验收：非法状态跳转被拒；发布后通知落库。
- [x] T2-4 学习材料与总结附件
  - 交付物：`materials_json`/`summary_attachments_json` 附件列表读写；复用文件服务与附件控件。
  - 验收：PDF/JPG/PNG 可上传，20MB 限制生效，列表回显正常。
- [x] T2-5 活动列表/详情与可见性
  - 交付物：GET `/api/v1/party/activities` 支持状态/类别/年份筛选；详情按 `target_roles`/`target_member_ids_json` 判定可见性；普通学生仅见公开活动，教师默认不见党员名册。
  - 验收：不同角色返回数据符合可见性规则。
- [x] T2-6 测试
  - 交付物：`backend/tests/test_party_activity.py`。
  - 验收：CRUD、状态机、发布通知、附件、可见性断言全部通过。
