# D3 课程与作业任务清单

> 来源：`tongyong_proposal.md` 第 6 章、`tongyong_design.md` 第 4.3 节
> 里程碑：M6 作业附件（P1）
> 依赖：S1 共享文件与预览服务、S2 任务确认适配（可选）

## M6 作业附件

- [x] 数据：`AssignmentAttachment`、`SubmissionAttachment` 模型 + Alembic 迁移（提交附件含 `version`）。
- [x] 存储：`StorageService` 增加 `assignment`、`submission` scope。
- [x] 后端：作业附件上传 `POST /assignments/{id}/attachments`（admin，多文件）。
- [x] 后端：作业附件删除 `DELETE /assignments/attachments/{id}`（admin，软删除）。
- [x] 后端：作业附件列表 `GET /assignments/{id}/attachments`（published 或 admin）。
- [x] 后端：附件下载与预览接口（登录用户/admin，复用 S1）。
- [x] 后端：multipart 提交 `POST /assignments/{id}/submit`（content + files），兼容原 JSON 接口。
- [x] 后端：提交附件按 `submission_versions.version` 绑定，更新提交保留旧版本附件。
- [x] 后端：提交附件列表（按版本过滤）、下载、预览，权限为本人/admin。
- [x] 校验：类型白名单、单文件 50MB、单作业/单次提交 200MB、单次最多 10 个文件。
- [x] 前端：`courses.js` 作业发布弹窗附件上传区（多文件、可移除）。
- [x] 前端：作业详情附件列表（预览/下载按钮），保留附件链接输入。
- [x] 前端：提交弹窗附件上传区，提交后展示已提交附件。
- [x] 前端：版本历史弹窗展示各版本附件。
- [x] 测试：附件全链路、历史版本附件保留、超限拒绝、越权下载拒绝。

## 验收

- [x] 教师发布、学生提交、预览、下载全链路可用。（接口回归 + 浏览器端验收）
