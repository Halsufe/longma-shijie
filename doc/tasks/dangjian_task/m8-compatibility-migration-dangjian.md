# M8 兼容与迁移模块（Compatibility）

> 输入文档：`../dangjian/dangjian_proposal.md`（第 12 章）、`../dangjian/dangjian_design.md`（4.8、5、11）  
> 前置依赖：现有数据库与 Alembic 基线  
> 完成定义：users.party_json 与 3 张新表迁移安全可回退，无党员身份用户兼容，路由与权限依赖就绪。

## 任务清单

- [x] T8-1 Alembic 迁移
  - 交付物：新增迁移：users.party_json（Text 默认 {}）、party_activities、party_activity_participants、party_materials 及索引；upgrade/downgrade 完整。
  - 验收：迁移 up/down 成功，既有数据保留。
- [x] T8-2 无党员身份用户兼容
  - 交付物：party_json 为空或缺失时视为普通学生，不报错。
  - 验收：学生/教师/校友现有功能回归正常。
- [x] T8-3 路由与权限依赖
  - 交付物：party 路由静态段注册顺序固定；require_admin/require_party_member 接入。
  - 验收：静态路由不被动态参数吞掉，权限校验生效。
- [x] T8-4 软删除语义
  - 交付物：党员档案、活动、材料删除均使用 deleted_at；统计/列表排除已删除。
  - 验收：软删后列表与统计不可见，数据仍保留。
- [x] T8-5 迁移与回归测试
  - 交付物：迁移 up/down、既有模块回归、新表约束测试。
  - 验收：全部通过。
