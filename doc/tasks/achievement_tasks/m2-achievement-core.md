# M2 成果核心模块（Achievement Core）

> 输入文档：`../achievements_proposal.md`（第 4、5、10 章）、`../high-level-design.md`（4.2、5、6）  
> 前置依赖：M1、M8 的 T8-1（details_json 迁移）  
> 完成定义：成果创建、查询、更新、软删除完整支持 `details` 读写、模板校验、日期派生、年份筛选与权限隔离。

## 任务清单

- [x] T2-1 模型新增 details 读写
  - 交付物：`backend/app/models/achievement.py` 增加 `details` 属性（读写 `details_json`，模式参照 `proofs`）。
  - 验收：`details_json` 为空时 `details` 返回 `{}`。
- [x] T2-2 Schema 增加 details
  - 交付物：`backend/app/schemas/achievement.py`，`AchievementCreate/Update/Info` 增加 `details`。
  - 验收：创建、更新请求可传 `details`，详情与列表响应均返回 `details`。
- [x] T2-3 实现模板校验服务
  - 交付物：`backend/app/services/achievement_service.py`（新建），`validate_details(category, details)` 按 M1 模板校验必填、枚举、格式。
  - 验收：缺必填、非法枚举、格式错误返回字段级错误信息。
- [x] T2-4 创建/更新接入校验与派生
  - 交付物：`backend/app/api/routes/achievements.py`，create/update 时先校验，再派生 `achievement_date` 并写入 `details_json`。
  - 验收：POST/PUT 保存的 `details` 与派生日期正确。
- [x] T2-5 列表查询支持年份与排序
  - 交付物：`backend/app/repositories/achievement_repo.py`，`year`（YYYY）、`category`、`status`、分页；排序 `achievement_date desc, created_at desc`。
  - 验收：`year` 为空返回全部，筛选与既有分页兼容。
- [x] T2-6 详情与列表响应返回完整信息
  - 交付物：`AchievementInfo` 响应含 `details`、`proofs`。
  - 验收：前端可回显模板字段与附件数量。
- [x] T2-7 集成测试
  - 交付物：`backend/tests/test_achievements_v2.py`（或扩展既有测试）。
  - 验收：8 类创建、必填报错、日期派生、年份筛选、用户隔离、软删除全部通过；旧请求格式（无 `details`）不回归。
