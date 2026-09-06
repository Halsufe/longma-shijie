# M1 党员档案模块（Party Profile）

> 输入文档：`../dangjian/dangjian_proposal.md`（第 5、13 章）、`../dangjian/dangjian_design.md`（4.1、5.1、5.2、5.5、6）  
> 前置依赖：M8 迁移（users.party_json 与 party_materials 表）  
> 完成定义：党员身份字段可通过管理端维护，阶段流转受状态机校验，发展材料可上传管理且默认不进知识库。

## 任务清单

- [x] T1-1 新增 users.party_json 列与 User.party 属性
  - 交付物：`backend/app/models/user.py` 增加 `party_json` 列与 `party` 读写属性（沿用 `profile` JSON 处理模式）；schema 中 `UserInfo` 可选返回 `party`。
  - 验收：空值返回 `{}`；读写不破坏现有 profile 数据。
- [x] T1-2 实现 party_json 字段校验
  - 交付物：`backend/app/services/party_profile_service.py` 中校验 party_type/apply_status 枚举、YYYY-MM 时间格式、阶段时间单调递增、班级枚举（读取运行时配置 party_classes）、停止发展时必填 stop_reason。
  - 验收：非法枚举、时间倒挂、未知班级、缺 stop_reason 均返回明确错误。
- [x] T1-3 党员名册 CRUD 与批量导入
  - 交付物：GET/POST `/api/v1/party/members`、PUT `/api/v1/party/members/{user_id}`；支持班级/类型/状态筛选与分页；批量导入支持 CSV（新增/更新/跳过/错误明细）。
  - 验收：管理员可维护名册；普通学生/教师访问返回 403；导入错误明细可下载。
- [x] T1-4 发展阶段状态流转
  - 交付物：PUT `/api/v1/party/members/{user_id}/status`；状态机按设计 4.1（时间轴字段 + apply_status 联动）；变更写入审计日志并触发 party_status_change 通知（走 M7 适配器）。
  - 验收：合法流转成功，非法跳级被拒绝，审计有记录。
- [x] T1-5 党员发展材料管理
  - 交付物：`party_materials` 模型与 POST `/api/v1/party/materials`、GET `/api/v1/party/members/{user_id}/materials`；复用文件服务；仅 admin 上传/查看。
  - 验收：材料不写入知识库；权限校验生效；软删除不物理删除。
- [x] T1-6 require_party_member 权限依赖
  - 交付物：`backend/app/api/deps.py` 新增 `require_party_member`（student 且 party_json.party_type 有效），并在本人查询/报名等接口接入。
  - 验收：普通学生、教师、校友均不可冒充党员身份。
- [x] T1-7 单元与集成测试
  - 交付物：`backend/tests/test_party_profile.py`。
  - 验收：字段校验、名册 CRUD、阶段流转、材料权限、批量导入断言全部通过。
