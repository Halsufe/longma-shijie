# E2 党团活动扩展（Party-League Activity Extension）

> 输入文档：`../dangjian/dangjian_politic_proposal.md`（第 6、7、13 章）、`../dangjian/dangjian_politic_design.md`（2、4.2、5.3、6）  
> 前置依赖：E1（政治面貌判定）  
> 完成定义：活动类别细分与参加对象扩展生效，报名与可见性按政治面貌校验，团员/群众可参与对应活动。

## 任务清单

- [x] E2-1 类别与参加对象枚举扩展
  - 交付物：`backend/app/services/party_target_roles.py` 作为枚举与判定单一数据源；`category` 增加 主题团日/团学实践/团组织建设/其他团学；`target_roles` 增加 全体团员/党员与团员/群众；旧值保留。
  - 验收：旧活动数据不失效，新枚举可正常创建。
- [x] E2-2 报名校验按政治面貌
  - 交付物：`PartyRegistrationService.register` 增加 `political_status` 与 `target_roles` 判定；群众可报“全体学生/群众”，团员可报“全体团员/党员与团员/全体学生”。
  - 验收：对象外报名返回明确业务错误；符合对象报名成功。
- [x] E2-3 活动可见性扩展
  - 交付物：`PartyActivityService.list_visible` 与 `visible_or_404` 按政治面貌过滤；公开活动（全体学生）所有在校学生可见。
  - 验收：党员/团员专属活动对不符合对象不可见；群众可见公开活动。
- [x] E2-4 前端枚举与筛选
  - 交付物：`frontend/js/views/party.js` 类别筛选增加团学细分；管理端活动表单枚举同步。
  - 验收：学生端可筛选团学活动，管理端可创建团学活动。
- [x] E2-5 测试
  - 交付物：`backend/tests/test_party_league_activity.py`。
  - 验收：枚举、报名校验、可见性、前端枚举一致性断言通过。
