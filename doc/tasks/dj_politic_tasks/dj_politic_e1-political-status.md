# E1 政治面貌模块（Political Status）

> 输入文档：`../dangjian/dangjian_politic_proposal.md`（第 5、13、15 章）、`../dangjian/dangjian_politic_design.md`（2、4.1、5.1、5.2、6）  
> 前置依赖：E7 迁移（users.political_status 与 political_status_reviews 表）  
> 完成定义：学生可查看并提交政治面貌申请，管理员单级审核后生效，党员档案可自动同步政治面貌，审计留痕。

## 任务清单

- [x] E1-1 users 政治面貌字段与 Schema
  - 交付物：`backend/app/models/user.py` 新增 `political_status`（String(30)，默认“群众”）与 `political_status_updated_at`；用户 Schema 返回字段。
  - 验收：默认值为“群众”；读写不破坏现有 `profile_json`/`party_json`。
- [x] E1-2 PoliticalStatusReview 模型与 Schema
  - 交付物：`backend/app/models/party.py` 新增 `PoliticalStatusReview`；Schema 定义申请/审核/查询模型；索引与设计 5.2 一致。
  - 验收：字段、索引与设计一致。
- [x] E1-3 学生提交政治面貌申请
  - 交付物：GET/POST `/api/v1/party/political-status/mine`；`to_status` 仅允许 共青团员/群众；同状态重复提交拒绝。
  - 验收：学生可查看本人状态并提交申请；提交党员类被拒绝；重复提交返回明确错误。
- [x] E1-4 管理员审核
  - 交付物：GET `/api/v1/party/political-status/reviews`（筛选/分页）、PUT `/api/v1/party/political-status/reviews/{id}/approve|reject`；通过后更新 `users.political_status` 与 `political_status_updated_at`，写审计；调用 E6 通知适配器。
  - 验收：一条申请只能审核一次；通过后本人状态生效；拒绝保留原值；非 admin 返回 403。
- [x] E1-5 党员档案自动同步
  - 交付物：`PartyProfileService` 更新/阶段流转后同步 `political_status`：正式党员→中共党员、预备党员→预备党员、入党积极分子→入党积极分子；学生不可直接申请党员类。
  - 验收：同步不产生审核记录；与 `party_json` 保持一致。
- [x] E1-6 单元与集成测试
  - 交付物：`backend/tests/test_political_status.py`。
  - 验收：申请、审核幂等、同步、审计、权限断言全部通过。
