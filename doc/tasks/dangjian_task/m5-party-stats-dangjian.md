# M5 党建统计模块（Party Stats）

> 输入文档：`../dangjian/dangjian_proposal.md`（第 9、13 章）、`../dangjian/dangjian_design.md`（4.5、6）  
> 前置依赖：M1、M2、M3、M4  
> 完成定义：管理端可按班级/年份/类别筛选获得党员人数、参与率、材料量、发展情况统计。

## 任务清单

- [x] T5-1 党员人数与班级分布
  - 交付物：GET `/api/v1/party/stats?type=member_counts`；按 party_type/class_name/grade 分组。
  - 验收：计数与名册一致，班级枚举过滤正确。
- [x] T5-2 活动参与率/报名率
  - 交付物：应参加名单由 `target_roles`/`target_member_ids_json` 展开，输出签到人数/报名人数/参与率/报名率。
  - 验收：分母口径与设计一致，除零返回 0%。
- [x] T5-3 材料上传量
  - 交付物：学习材料（materials_json）+ party_materials 数量，按年月/活动/党员统计。
  - 验收：与数据一致。
- [x] T5-4 发展情况
  - 交付物：按 apply_status 分组与年度转正数。
  - 验收：与党员档案一致。
- [x] T5-5 多维筛选与分页
  - 交付物：班级/年级/年份/活动类别参数组合；列表类统计沿用分页。
  - 验收：组合参数返回正确。
- [x] T5-6 测试
  - 交付物：`backend/tests/test_party_stats.py`。
  - 验收：所有统计口径断言通过。
