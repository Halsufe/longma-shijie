# M8 兼容与迁移模块（Compatibility）

> 输入文档：`../achievements_proposal.md`（第 10 章）、`../high-level-design.md`（4.8、5、11）  
> 前置依赖：现有数据库与 Alembic 基线  
> 完成定义：`details_json` 迁移安全可回退，旧数据可正常展示与编辑，`member_ids_json` 兼容保留。

## 任务清单

- [x] T8-1 Alembic 迁移新增 details_json
  - 交付物：新增迁移，`achievements.details_json`（Text，默认空对象），并增加 `(user_id, achievement_date)` 组合索引；upgrade/downgrade 完整。
  - 验收：迁移 up/down 成功，既有数据保留。
- [x] T8-2 旧数据读取兼容
  - 交付物：无 `details_json` 时返回 `{}`；列表与详情回退展示 `title/description/level/achievement_date`。
  - 验收：旧记录可正常查看，不报错。
- [x] T8-3 旧数据编辑兼容
  - 交付物：编辑旧数据时打开对应分类模板，仅通用字段回填，补全必填后保存生成 `details`。
  - 验收：保存不丢失原字段，校验通过后 `details` 完整。
- [x] T8-4 member_ids_json 兼容
  - 交付物：保留列与读写逻辑，不再采集、不展示；旧数据不回写 `details`。
  - 验收：含旧 `member_ids` 的数据迁移与读取正常。
- [x] T8-5 迁移与回归测试
  - 交付物：迁移 up/down、旧数据展示、旧数据编辑、新数据全流程回归测试。
  - 验收：全部通过。
