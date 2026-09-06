# S4 兼容与迁移任务清单

> 来源：`tongyong_design.md` 第 4.9 节
> 覆盖：全部新增表/字段的迁移与旧数据兼容

- [x] Alembic 迁移：新增 `alumni_conversion_requests`、`knowledge_folders`、`knowledge_file_versions`、`assignment_attachments`、`submission_attachments`、`runtime_configs`、`chat_message_attachments`。
- [x] Alembic 迁移：`knowledge_files.folder_id`、`chat_messages.regenerated_at`。
- [x] Alembic 迁移：`user_sessions (user_id, last_active_at)` 复合索引。
- [x] 旧数据兼容：`profile_json` 缺新字段视为空。
- [x] 旧数据兼容：`attachment_url`、`attachment_name` 字段保留并可继续使用。
- [x] 接口兼容：旧 `POST /admin/users/import` 保留。
- [x] 路由注册顺序：新路由不覆盖既有路由，业务 Skill/前端入口不冲突。
- [x] 迁移回滚验证（upgrade + downgrade 可逆）。
- [x] 更新 README/部署文档（LibreOffice 安装、新配置项、新接口）。

## 验收

- [x] 从当前版本升级后数据不丢失、旧功能不回退。
