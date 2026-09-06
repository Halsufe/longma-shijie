# D1 用户中心任务清单

> 来源：`tongyong_proposal.md` �?4 章、`tongyong_design.md` �?4.1 �?> 里程碑：M1 个人资料字段扩展（P1）、M2 校友转换（P1�?> 依赖：S3 运行时配置、通知服务、审计日�?
## M1 个人资料字段扩展

- [x] 后端：`schemas/user.py` 增加 profile 白名单校验（`interests`/`development_plan`/`grade`，长度与数组上限）�?- [x] 后端：`profile_service.py` 实现字段校验�?`interests` 逗号/顿号分隔转换，兼容旧 `profile_json`�?- [x] 后端：`PUT /api/v1/users/me` 接入白名单校验，未知键忽略、已知键超限返回中文错误�?- [x] 前端：`profile.js` 编辑弹窗新增“兴趣领�?未来发展规划/年级”三个输入�?- [x] 前端：`profile.js` 展示区新增三字段，空值显示“未填写”�?- [x] 测试：接口保�?读取、非法输入拒绝、旧数据兼容、竞赛推荐可读取新字段�?
## M2 校友转换

- [x] 数据：`AlumniConversionRequest` 模型 + Alembic 迁移（user_id/毕业年份/状�?审核意见/审核�?时间）�?- [x] 后端：`alumni_conversion_service.py` 申请校验（毕业年份范围、不得晚于当前年份、唯一 pending、仅 active student）�?- [x] 后端：`POST /api/v1/users/me/alumni-request` �?`GET /api/v1/users/me/alumni-request`�?- [x] 后端：管理员申请列表 `GET /api/v1/admin/users/alumni-requests`（状态筛选）�?- [x] 后端：通过/驳回接口 `approve`、`reject`（驳回必填原因）�?- [x] 后端：管理员直接转换 `POST /api/v1/admin/users/{id}/convert-alumni`�?- [x] 后端：统一转换逻辑：`role=alumni`、更�?`graduation_year`、保留档�?成果/知识�?会话�?- [x] 通知：管理员收到新申请通知、学生收到通过/驳回通知（`ref_type=alumni_request`）�?- [x] 审计：申请、通过、驳回、直接转换四类动作写 `audit_logs`�?- [x] 前端：`profile.js` 增加“申请转为校友”入口与 pending 状态展示�?- [x] 前端：`admin.js` 增加校友申请列表、通过/驳回、用户行“转为校友”�?- [x] 测试：两种转换方式、重复申请拦截、数据保留、审计与通知�?
## 验收

- [x] 三字段可填写、保存、展示并�?AI 画像读取�?- [x] 校友转换全链路可用且审计完整�?
