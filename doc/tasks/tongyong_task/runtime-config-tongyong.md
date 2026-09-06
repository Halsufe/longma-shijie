# S3 运行时配置服务任务清单

> 来源：`tongyong_design.md` 第 4.8 节
> 覆盖：M10 AI 模型/配额/提醒时间配置

- [x] 数据：`RuntimeConfig` 模型 + Alembic 迁移（key 唯一、value_json、updated_by、updated_at）。
- [x] 服务：`runtime_config_service.py` 启动加载并合并：默认值 ← 环境变量 ← 数据库覆盖。
- [x] 服务：白名单键与类型校验（class_name、default_quota_mb、login_max_attempts、login_window_minutes、ai_model、ai_base_url、assignment_reminder_hours）。
- [x] 路由：`GET/PUT /api/v1/admin/config` 改为持久化读写并刷新内存 `settings`。
- [x] 安全：API Key 不落库、不回显，只显示“已配置/未配置”。
- [x] 审计：配置修改写 `audit_logs`。
- [x] 前端：`admin.js` 系统配置可编辑表单（配合 D4/M10）。
- [x] 测试：配置覆盖优先级与非法键/类型拒绝。

## 验收

- [x] 管理员配置可持久化且启动后自动恢复。
