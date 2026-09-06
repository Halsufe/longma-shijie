# E7 兼容与迁移（Compatibility & Migration）

> 输入文档：`../dangjian/dangjian_politic_proposal.md`（第 12 章）、`../dangjian/dangjian_politic_design.md`（2、4.7、5、11）  
> 前置依赖：现有数据库与 Alembic 基线（已应用 `i012f3c4d5e6`）  
> 完成定义：新迁移安全可回退，既有 `party_json` 数据正确回填，旧接口与无政治面貌用户兼容。

## 任务清单

- [x] E7-1 Alembic 迁移
  - 交付物：新增独立迁移：`users.political_status`、`users.political_status_updated_at`、`political_status_reviews`、`political_materials` 及索引；upgrade/downgrade 完整；不修改已应用迁移。
  - 验收：迁移 up/down 成功，既有数据保留。
- [x] E7-2 既有数据回填
  - 交付物：迁移回填 `party_json` 用户：正式党员→中共党员、预备党员→预备党员、入党积极分子→入党积极分子，其余默认“群众”；写入 `political_status_updated_at`。
  - 验收：回填结果与 `party_json` 一致，可重复执行。
- [x] E7-3 无政治面貌用户兼容
  - 交付物：无 `political_status` 的用户视为“群众”；既有 `party_*` 接口不破坏。
  - 验收：学生/教师/校友现有功能回归正常。
- [x] E7-4 路由与权限依赖
  - 交付物：新接口静态段注册顺序固定；复用 `require_admin`、`get_current_user`。
  - 验收：静态路由不被动态参数吞掉，权限校验生效。
- [x] E7-5 迁移与回归测试
  - 交付物：迁移 up/down、回填、既有模块回归、新表约束测试。
  - 验收：全部通过。
