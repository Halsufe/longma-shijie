# M3 报名签到模块（Registration & Attendance）

> 输入文档：`../dangjian/dangjian_proposal.md`（第 7、13 章）、`../dangjian/dangjian_design.md`（4.3、5.4、6）  
> 前置依赖：M1、M2  
> 完成定义：目标用户可按对象/截止/名额报名与取消，签到窗口内可自助签到，管理员可代签/补签/缺席，参与记录可查询。

## 任务清单

- [x] T3-1 PartyActivityParticipant 模型与唯一约束
  - 交付物：模型字段与设计 5.4 一致；(activity_id, user_id) 唯一索引。
  - 验收：重复报名被数据库与服务双重拦截。
- [x] T3-2 报名与取消报名
  - 交付物：POST `/api/v1/party/activities/{id}/register`、DELETE `/api/v1/party/activities/{id}/register`；校验活动对象、截止时间、名额。
  - 验收：截止后/对象外/超名额均返回明确业务错误；取消释放名额。
- [x] T3-3 自助签到
  - 交付物：POST `/api/v1/party/activities/{id}/sign-in`（self）；窗口按 `party_sign_in_window_minutes` 判定；记录 `sign_in_time`/`sign_in_method`。
  - 验收：窗口外签到被拒，窗口内成功且记录正确。
- [x] T3-4 管理员代签/补签/缺席
  - 交付物：PUT `/api/v1/party/activities/{id}/participants/{user_id}/attendance`；支持 signed_in/absent 与 manual 代签。
  - 验收：管理员可处理，学生不可调用。
- [x] T3-5 我的参与记录
  - 交付物：GET `/api/v1/party/mine` 返回本人报名/签到记录。
  - 验收：仅本人数据，字段完整。
- [x] T3-6 测试
  - 交付物：`backend/tests/test_party_registration.py`。
  - 验收：报名/取消/签到/补签/权限断言全部通过。
