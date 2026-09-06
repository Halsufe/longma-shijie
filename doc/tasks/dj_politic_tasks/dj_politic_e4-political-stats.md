# E4 统计扩展（Political Stats Extension）

> 输入文档：`../dangjian/dangjian_politic_proposal.md`（第 9、13 章）、`../dangjian/dangjian_politic_design.md`（2、4.4、6）  
> 前置依赖：E1、E2、E3  
> 完成定义：管理端可按班级/年级/年份/类别/政治面貌筛选，获得政治面貌分布、团学活动参与率与资料量统计。

## 任务清单

- [x] E4-1 政治面貌分布
  - 交付物：`GET /api/v1/party/stats?type=political_counts`，按 `political_status` 分组，支持班级/年级分布。
  - 验收：计数与用户数据一致，口径以 `political_status` 为准。
- [x] E4-2 团学活动参与率
  - 交付物：按 `category` 属于团学细分集合的活动统计参与率，分母为应参加名单展开。
  - 验收：分母口径正确，除零返回 0%。
- [x] E4-3 资料量统计
  - 交付物：活动学习材料 + `political_materials` 数量，按年月/类别统计。
  - 验收：与数据一致。
- [x] E4-4 筛选参数扩展
  - 交付物：统计接口支持 `class_name/grade/year/category/political_status` 组合筛选。
  - 验收：组合参数返回正确结果。
- [x] E4-5 测试
  - 交付物：`backend/tests/test_political_stats.py`。
  - 验收：所有统计口径断言通过。
