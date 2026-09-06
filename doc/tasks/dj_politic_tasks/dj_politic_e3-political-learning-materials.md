# E3 政治学习资料模块（Political Learning Materials）

> 输入文档：`../dangjian/dangjian_politic_proposal.md`（第 8、13 章）、`../dangjian/dangjian_politic_design.md`（2、4.3、5.4、6）  
> 前置依赖：E1、E7 迁移（political_materials 表）  
> 完成定义：管理员可发布政治学习资料并指定适用对象，学生只能查看本人政治面貌适用范围内的资料。

## 任务清单

- [x] E3-1 PoliticalLearningMaterial 模型与 Schema
  - 交付物：`backend/app/models/party.py` 新增 `PoliticalLearningMaterial`；字段与设计 5.4 一致。
  - 验收：字段、索引与设计一致。
- [x] E3-2 发布/编辑/上下架接口
  - 交付物：POST/PUT `/api/v1/party/learning-materials`、DELETE `/api/v1/party/learning-materials/{id}`；仅 admin；软删除沿用 `deleted_at`。
  - 验收：admin 可管理，非 admin 返回 403。
- [x] E3-3 按适用对象可见列表
  - 交付物：GET `/api/v1/party/learning-materials` 按 `political_status` 与 `applicable_roles_json`/`target_user_ids_json` 过滤。
  - 验收：学生仅见适用范围内的资料，越权不可见。
- [x] E3-4 附件上传
  - 交付物：资料附件复用文件服务，PDF/JPG/PNG、20MB；“指定人员”资料不进知识库。
  - 验收：附件可上传回显，超限被拒，指定人员资料不进入知识库。
- [x] E3-5 测试
  - 交付物：`backend/tests/test_political_materials.py`。
  - 验收：CRUD、可见性、附件、权限断言全部通过。
