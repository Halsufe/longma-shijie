# E5 成长档案联动扩展（Achievement Link Extension）

> 输入文档：`../dangjian/dangjian_politic_proposal.md`（第 10、13 章）、`../dangjian/dangjian_politic_design.md`（2、4.5、6）  
> 前置依赖：E2、成果档案模块  
> 完成定义：团学活动完成签到后可一键写入成长档案，分类由管理员指定，团员身份不联动。

## 任务清单

- [x] E5-1 link_type=league_activity 支持
  - 交付物：`PartyAchievementLinkService` 扩展 `link_type="league_activity"`，管理员在发布/联动时指定“组织管理/社会实践”。
  - 验收：团学活动可联动，分类正确。
- [x] E5-2 签到前置校验与防重
  - 交付物：仅完成签到的团学活动可联动；复用 `source_type="party"`、`source_id` 防重。
  - 验收：未签到活动被拒，重复联动不产生重复成果。
- [x] E5-3 团员身份不联动
  - 交付物：不提供团员身份写入成长档案的入口与接口参数。
  - 验收：团员身份不会生成身份类成果。
- [x] E5-4 测试
  - 交付物：`backend/tests/test_party_league_achievement_link.py`。
  - 验收：联动、防重、签到前置、身份不联动断言通过。
