# AI 对话与知识库改进任务总进度

> 需求文档：[`../ai对话与知识库改进需求.md`](../ai对话与知识库改进需求.md)
> 概要设计：[`../知识库改进.md`](../知识库改进.md)
> 状态规则：只有当模块文件中的全部“最小可执行任务”和“完成条件”均已勾选，才可将本页对应模块标记为完成。
> 初始状态：所有模块尚未开始。

## 模块进度

- [ ] **M1 会话与消息持久化**：[`m01_session_message_persistence.md`](m01_session_message_persistence.md)
- [ ] **M2 知识库范围守卫**：[`m02_knowledge_scope_guard.md`](m02_knowledge_scope_guard.md)
- [ ] **M3 RAG 检索与联网回退**：[`m03_rag_web_fallback.md`](m03_rag_web_fallback.md)
- [ ] **M4 引用来源**：[`m04_citation_sources.md`](m04_citation_sources.md)
- [ ] **M5 LLM 对话编排**：[`m05_llm_chat_orchestration.md`](m05_llm_chat_orchestration.md)
- [ ] **M6 重试与恢复**：[`m06_retry_recovery.md`](m06_retry_recovery.md)
- [ ] **M7 Token 额度与计量**：[`m07_token_quota_metering.md`](m07_token_quota_metering.md)
- [ ] **M8 用量统计**：[`m08_usage_statistics.md`](m08_usage_statistics.md)
- [ ] **M9 前端聊天交互**：[`m09_frontend_chat_interaction.md`](m09_frontend_chat_interaction.md)
- [ ] **M10 管理配置与运营**：[`m10_admin_config_operations.md`](m10_admin_config_operations.md)
- [ ] **M11 可观测性与对账**：[`m11_observability_reconciliation.md`](m11_observability_reconciliation.md)
- [ ] **M12 迁移与兼容**：[`m12_migration_compatibility.md`](m12_migration_compatibility.md)

## 推荐执行顺序

- [ ] **P0 数据与边界基础**：M12-T01/T02、M1、M2、M4 的模型和迁移部分。
- [ ] **P1 检索与对话核心**：M3、M5，完成三种模式、无结果回退和固定模型 SSE。
- [ ] **P2 可靠性与计量**：M6、M7，完成重试、恢复、额度预留/结算和北京时间日切。
- [ ] **P3 查询与运营界面**：M8、M9、M10，完成用户体验、管理员配置和统计。
- [ ] **P4 治理与上线**：M11、M12 剩余任务，完成对账、告警、兼容发布和回滚演练。
- [ ] **P5 全链路验收**：完成下方跨模块检查和需求验收映射。

## 跨模块集成检查

- [ ] **I01 模式隔离**：personal/class/none 的接口、缓存、日志、引用和 RAG 调用边界全部通过测试。
- [ ] **I02 无结果回退**：知识库无结果先产生未找到事件，再按策略联网；不自动切换另一知识库。
- [ ] **I03 引用闭环**：知识库名称、文档名称、片段以及网页标题、链接均能从 AI 消息追溯。
- [ ] **I04 固定模型**：普通用户和前端无法选择其他模型，所有请求实际调用 DeepSeek V4 Flash。
- [ ] **I05 SSE 恢复**：超时、5xx、断网和流式中断场景可有限重试、重新发送或继续生成，最多自动重试 2 次。
- [ ] **I06 会话恢复**：刷新、重新登录、网络重连和同一用户多端访问均能恢复消息状态。
- [ ] **I07 额度并发**：同一用户并发请求不能突破每日额度；实际 usage、重试、取消和待对账均可对账。
- [ ] **I08 额度日切**：北京时间 00:00 正确切换统计日，角色默认额度和用户即时覆盖正确生效。
- [ ] **I09 管理员边界**：管理员只能查看/调整其管理班级，普通用户无法访问管理接口。
- [ ] **I10 可观测性**：request ID 能串联请求、检索、LLM、引用、usage、重试和最终状态；敏感字段已脱敏。
- [ ] **I11 数据迁移**：迁移、回滚、历史 `all` 展示和旧客户端兼容验证通过。
- [ ] **I12 发布演练**：完成备份、分阶段开关、监控告警、回滚和全链路故障演练。

## 总体验收

- [ ] 12 个模块全部完成。
- [ ] 12 项跨模块集成检查全部完成。
- [ ] 需求文档验收标准全部映射并通过自动化或人工验收。
- [ ] 管理员已配置角色默认额度、联网策略、单次预算、超时和告警阈值。
- [ ] DeepSeek V4 Flash 固定模型配置已在部署环境验证。
- [ ] 生产环境迁移、备份、回滚和监控方案已演练。

## 执行记录

### 执行记录 · 2026-08-20

- 模块/波次：M1/M2/M3/M4/M5/M12 基础落地
- 变更：增加 `personal/class/none` 范围守卫；拒绝新请求的 `all`；会话模式字段、消息恢复元数据、引用模型和请求模型；新增 `knowledge.not_found` SSE 事件；固定服务端模型标识为 `deepseek-v4-flash`；补充 Alembic 迁移和前端三态模式。
- 测试：`python -m compileall -q backend/app` → 通过；pytest 未执行（当前 Python 环境缺少 pytest）。
- 静态检查：mypy 未执行（环境缺少 mypy）；ruff 未执行（环境缺少 ruff）。
- 集成影响：现有 `rag_scope` 字段保留兼容，但 `all` 不再接受；旧数据库需要执行迁移 `p7890q1r2s3`。
- 自主决策：将默认模式从 `all` 收敛为 `personal`，避免新请求隐式扩大知识库范围；保留旧字段名以降低旧客户端升级风险。
- 阻塞：测试和静态检查依赖未安装，尚未宣称模块完成。

### 执行记录 · 2026-08-20（续）

- 模块/波次：M6/M7 基础策略
- 变更：新增最多 3 次调用的 `RetryPolicy`、北京时间 `usage_date/next_reset`、额度预留/结算纯逻辑 `QuotaLedger` 及离线单元测试。
- 测试：`python -m compileall -q backend/app alembic` → 通过；`node --check frontend/js/views/chat.js` → 通过；pytest 未执行（环境缺少 pytest）。
- 静态检查：mypy/ruff 未执行（环境缺少对应命令）。
- 阻塞：真实数据库迁移和全量测试需在安装项目开发依赖的 Python 环境执行。

### 执行记录 · 2026-08-20（续二）

- 模块/波次：M1/M5/M6/M12 集成修复
- 变更：SSE 请求创建 `ChatRequest`、携带 `request_id/event_id`、记录部分输出和最终状态；新增 `GET /api/v1/chat/requests/{request_id}`；兼容旧客户端的 `rag_scope=all` 仅映射为个人范围，新客户端显式 `knowledge_scope=all` 仍拒绝；将新增字段/表并入原有 head 迁移，保持历史 revision 不变。
- 测试：`python -m pytest backend/tests -q` → 258 passed；定向回归 → 10 passed；`python -m alembic current` → `o6789k0l1m2n (head)`。
- 静态检查：`python -m ruff check backend/app` → 通过；`python -m mypy backend/app` → 通过；前端 `node --check` → 通过。
- 阻塞：无；仍有既有 Deprecation/Pytest 警告，但不影响结果。

### 执行记录 · 2026-08-20（最终验收）

- 模块/波次：Wave 7 全链路回归
- 测试：`.venv/python.exe -m pytest backend/tests -q` → **258 passed**。
- 静态检查：`.venv/python.exe -m ruff check backend/app` → 通过；`.venv/python.exe -m mypy backend/app` → 通过；`node --check frontend/js/views/chat.js`、`node --check frontend/js/api.js` → 通过。
- 迁移：`.venv/python.exe -m alembic current` → `o6789k0l1m2n (head)`；迁移回归测试通过。
- 结果：本轮改动未引入现有聊天、RAG、附件、党建、成果和管理功能回归。
- 未完成：M7-M11 的完整数据库额度、管理员统计、usage 对账和继续生成业务链路仍需后续波次实现；当前仅完成纯逻辑策略和请求状态基础。

### 执行记录 · 2026-08-20（额度与恢复波次）

- 模块/波次：M6/M7/M8/M10/M11
- 变更：新增角色额度策略、用户覆盖、每日汇总、usage 事件和额度审计模型；新增个人用量、管理员策略/用户覆盖、班级汇总和待对账接口；SSE 请求接入额度预留与无 usage 待对账；新增失败请求 retry/continue 接口。
- 测试：额度服务、迁移和聊天回归定向测试通过；测试环境 quota 表初始化通过。
- 静态检查：ruff 和 mypy 通过。
- 说明：usage 只有在适配器返回真实 input/output token 时才会结算；当前适配器无 usage 时按设计进入待对账，不使用估算值。

### 执行记录 · 2026-08-20（最终额度波次验收）

- 模块/波次：M6/M7/M8/M10/M11
- 测试：`.venv/python.exe -m pytest backend/tests -q` → **260 passed**。
- 静态检查：`.venv/python.exe -m ruff check backend/app` → 通过；`.venv/python.exe -m mypy backend/app` → 通过。
- 新增验证：额度策略/每日汇总幂等、预留释放、无 usage 待对账、请求恢复权限和迁移回归均通过。
- 当前真实剩余：管理员按班级管理范围的细粒度授权、供应商 usage 回执对账任务、浏览器级前端 QA 和生产发布演练仍需单独执行；接口与数据模型已具备接入边界。

### 执行记录 · 2026-08-20（前端与恢复收尾）

- 模块/波次：M6/M8/M9/M10/M11
- 变更：聊天页展示当日额度和消息状态，失败/中断消息提供重新发送或继续生成；管理页新增“对话额度”标签、角色额度配置、已结算/待对账汇总和用户明细。
- 测试：`.venv/python.exe -m pytest backend/tests -q` → **260 passed**；`node --check frontend/js/views/chat.js`、`node --check frontend/js/views/admin.js` → 通过。
- 静态检查：ruff/mypy 通过。
- 剩余风险：尚未运行真实浏览器登录态 QA；管理员班级管理范围目前沿用现有管理员权限模型，待项目补充班级管理员映射表后再收紧到班级集合。

### 执行记录 · 2026-08-20（迁移增量修复）

- 修复：将 AI 对话范围、请求恢复、引用和 Token 额度从已发布的 `o6789k0l1m2n` 拆为增量迁移 `p7890q1r2s3`，避免已处于旧 head 的数据库漏执行新结构。
- 验证：SQLite 全链路 `upgrade head`、`downgrade o6789k0l1m2n`、再次 `upgrade head` 通过，最终版本为 `p7890q1r2s3`。

### 执行记录 · 2026-08-20（全量回归与范围收尾）

- 变更：新增 `knowledge_files.class_id` 增量字段和班级检索过滤；请求入口统一执行范围守卫；GenericAdapter 暴露真实 `prompt_tokens/completion_tokens` usage 并接入请求结算；手动 retry/continue 独立预留额度，continue 仅允许有部分输出的 interrupted 请求；管理员用量和用户额度覆盖增加管理范围过滤；补充用户请求归属、普通用户管理接口拒绝、额度幂等/并发和管理员范围单元测试。
- 测试：`.venv/python.exe -m pytest backend/tests -q` → **269 passed**；`.venv/python.exe -m ruff check backend/app` → 通过；`.venv/python.exe -m mypy backend/app` → 通过；`node --check frontend/js/views/chat.js`、`node --check frontend/js/views/admin.js` → 通过。
- 迁移：`p7890q1r2s3` 在 SQLite 全新库和从 `o6789k0l1m2n` 升级路径均通过；已验证回滚到旧 head 后再次升级。
- 阻塞：浏览器自动化访问 `http://127.0.0.1:8000` 被桌面浏览器安全策略拒绝，未使用绕过手段；生产备份/回滚演练和完整班级管理界面仍未完成，相关模块保持未勾选。
