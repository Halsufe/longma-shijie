# D4 管理端任务清单

> 来源：`tongyong_proposal.md` 第 7 章、`tongyong_design.md` 第 4.4 节
> 里程碑：M7-M12（P1/P2）
> 依赖：S2 任务确认适配、S3 运行时配置、党建/成果/资源现有服务

## M7 用户导入预检

- [x] 服务：`user_import_service.py` CSV 解析与行分类（create/update/restore/skip/error）。
- [x] 令牌：预检生成 JWT（file_sha256、row_count、summary_hash，10 分钟有效）。
- [x] 路由：`POST /api/v1/admin/users/import/preview`（单次上限 1000 行）。
- [x] 路由：`POST /api/v1/admin/users/import/confirm`（重新上传同文件、校验哈希、事务提交）。
- [x] 前端：`admin.js` 导入弹窗改为预检表格 + 错误高亮 + 确认导入。
- [x] 测试：错误行不落库、哈希不一致拒绝、旧接口兼容。

## M8 用户列表 CSV 导出

- [x] 服务：`user_export_service.py`（筛选条件导出全部，UTF-8 BOM）。
- [x] 路由：`GET /api/v1/admin/users/export` + 审计。
- [x] 前端：用户管理工具栏“导出 CSV”按钮。
- [x] 测试：导出行数与筛选一致、Excel 不乱码。

## M9 精确 DAU/活跃趋势

- [x] 数据：`user_sessions` 新增 `(user_id, last_active_at)` 复合索引。
- [x] 服务：`activity_stats_service.py` 按 Asia/Shanghai 自然日去重统计。
- [x] 路由：`GET /api/v1/admin/stats/activity?days=30` 与 `.../activity/export`。
- [x] 前端：概览“活跃用户”改真实今日 DAU，新增 30 天趋势面板与导出。
- [x] 测试：口径正确、无重复计数、时区边界。

## M10 Skill 与系统配置编辑

- [x] 后端：`SkillInfo/SkillUpdate` 暴露 `model_config`（白名单：model/temperature/max_tokens/top_p）。
- [x] 后端：Skill 保存后调度器热刷新触发词与配置（或明确重启生效）。
- [x] 数据：`RuntimeConfig` 模型 + Alembic 迁移（S3）。
- [x] 服务：`runtime_config_service.py` 启动合并（DB > env > 默认值）、白名单键、类型校验。
- [x] 路由：`GET/PUT /api/v1/admin/config` 持久化改造；AI 模型、Base URL、配额、登录限制、提醒时间档位可保存。
- [x] 安全：API Key 只回显“已配置/未配置”。
- [x] 审计：配置修改写 `audit_logs`。
- [x] 前端：`admin.js` Skill 行“编辑”弹窗（展示名/说明/触发词/model_config/启停）。
- [x] 前端：系统配置可编辑表单。
- [x] 测试：保存后重启仍生效、非法配置键拒绝。

## M11 党建/竞赛/项目/成果多维统计

- [x] 服务：`business_stats_service.py` + party/resource/achievement 适配器。
- [x] 服务：项目适配器返回 `not_available` 占位。
- [x] 路由：`GET /api/v1/admin/stats/business?year=&class_name=&grade=&category=`。
- [x] 前端：`admin.js` 新增“业务统计”Tab（指标卡 + 明细表 + 项目未上线提示）。
- [x] 测试：三类聚合正确、项目未上线不报错、筛选生效。

## M12 任务确认接入业务接口

- [x] 服务：`confirmation_adapter.py` 可选令牌校验（缺失放行、存在校验用户与数据哈希）。
- [x] 路由：`achievements.py`、`resources.py` 写接口接入令牌校验。
- [x] 审计：确认成功/失败均记录。
- [x] 前端：高风险操作统一确认卡片，确认后携带令牌。
- [x] 测试：过期/伪造/数据不一致令牌拒绝，旧流程兼容。

## 验收

- [x] 管理端 6 项能力全部可用且权限、审计、安全规则正确。
