# 通用平台功能总体进度

> 更新日期：2026-08-06 23:45
> 任务明细：`doc/tasks/tongyong_task/<module-name-tongyong>.md`

## 模块进度

- [x] D1 用户中心：`user-center-tongyong.md`（M1 资料字段、M2 校友转换）
- [x] D2 知识库：`knowledge-base-tongyong.md`（M3 文件夹移动、M4 在线预览、M5 版本管理）
- [x] D3 课程与作业：`courses-assignments-tongyong.md`（M6 作业附件；接口与浏览器全链路验收完成）
- [x] D4 管理端：`admin-platform-tongyong.md`（M7-M12；接口、前端与专项测试完成）
- [x] D5 AI 对话：`ai-chat-tongyong.md`（M13-M15；附件、Markdown、重新生成、SSE 与并发保护完成）
- [x] S1 共享文件与预览：`shared-file-preview-tongyong.md`
- [x] S2 任务确认适配：`confirmation-adapter-tongyong.md`
- [x] S3 运行时配置：`runtime-config-tongyong.md`
- [x] S4 兼容与迁移：`compatibility-migration-tongyong.md`

## 里程碑进度

- [x] M1 个人资料字段扩展（P1）
- [x] M2 校友转换（P1）
- [x] M3 知识库文件夹与移动（P1）
- [x] M4 在线预览（P1）
- [x] M5 班级文件版本管理（P2）
- [x] M6 作业附件（P1）
- [x] M7 用户导入预检（P1）
- [x] M8 用户列表 CSV 导出（P1）
- [x] M9 精确 DAU/活跃趋势（P1）
- [x] M10 Skill 配置编辑 + AI/配额/提醒时间配置（P2）
- [x] M11 党建/竞赛/成果多维统计（P0/P1；创新项目已按产品范围移除）
- [x] M12 任务确认接入业务接口与前端（P1）
- [x] M13 AI 重新生成（P2）
- [x] M14 聊天附件消息（P2）
- [x] M15 回答展示规范（P2）

## 建议执行顺序

1. 基础设施先行：S1、S3、S4。
2. P1 第一批：M1、M2、M3、M4、M6、M7、M8、M9。
3. P1/P0 第二批：M11、M12（配合 S2）。
4. P2 第三批：M5、M10、M13、M14、M15。

## 执行记录

- 2026-08-06：已阅读需求、概要设计及 9 个模块任务清单，确认按 S4/S3/S1/D1-D5/S2 顺序实施并在依赖允许时并行。
- 2026-08-06：从 `database/longma.db` 只读复制创建 `database/qa_tongyong.db`；迁移与联调仅使用 QA 副本或测试临时数据库。
- 2026-08-06：自主决策遵循设计文档：Office 预览失败统一降级、运行时配置 DB > env > 默认、单层知识库目录、班级版本最多 20；创新项目统计后按产品范围调整从接口与页面移除。
- 2026-08-06 17:30：补充 D5 聊天附件服务/权限/文本注入、重新生成 SSE 兼容入口与会话锁；补充 D3 `/submit` multipart 兼容、附件扩展名校验；补充 D4 导入分类摘要哈希、业务筛选参数与服务 facade；前端加入离线 Markdown/净化、聊天附件与重新生成、课程附件和管理端预检/趋势/配置界面。
- 2026-08-06 17:35：显式内存库全量回归 `194 passed`；`mypy backend`（156 files）、`ruff check backend`、profile/knowledge/courses/admin/chat 的 `node --check` 全部通过。
- 2026-08-06 19:20：补充 `StorageService.validate_upload` 统一文件头/空文件/大小/扩展名校验，接入知识库、作业附件、班级版本与聊天附件；新增伪装文件测试。修复 `knowledge.js` 模块语法并加入入口缓存版本号。QA 浏览器完成管理员发布作业、学生两次带附件提交及历史版本附件验收；内存库全量回归 `195 passed`，`mypy`（159 files）、`ruff`、全部前端 `node --check` 通过。
- 2026-08-06 22:40：修复个人知识库配额请求结果索引导致的 `toFixed` 崩溃；新增政治学习资料附件的可见性校验下载接口及前台下载按钮；从业务统计接口与页面移除创新项目；调整管理端用户搜索图标及角色/状态筛选布局；将 DeepSeek 模型改为已实测可用的 `deepseek-chat` 并以正常网络权限重启 QA 服务。浏览器实测知识库正常、后台筛选同排、政治资料下载入口存在、AI 在 689ms 返回“AI连接正常”；全量回归 `195 passed`，`ruff`、`mypy`、全部前端 `node --check` 通过。
- 2026-08-06 23:45：修复聊天知识库模式在重新渲染后恢复默认值的问题，模式现在可跨发送、会话切换与页面刷新持久化。AI 检索链统一为“本轮附件（支持文本/PDF/DOCX）→ 所选知识库 → 权限内平台系统信息 → 最多两轮联网搜索 → 通用知识”，`none` 模式严格跳过知识库并过滤带知识库引用的历史回复。新增 Bing RSS、公开页面正文与 PyPI 结构化检索，权威结构化结果命中后立即停止。浏览器实测 `none` 模式刷新和发送后均保持，FastAPI 最新版本查询仅引用 PyPI 并在 4481ms 返回 `0.141.1`；全量回归 `199 passed`，`ruff`、`mypy`、全部前端 `node --check` 通过。
- 2026-08-06 17:30：发现测试进程曾因 `.env` 覆盖误触持久库，已用 `database/qa_tongyong.db` 逐表校验并恢复 `database/longma.db` 到旧迁移头 `k2345g6h7i8j`；后续质量命令显式设置 `DB_URL=sqlite:///:memory:`，QA 迁移只使用 `database/qa_tongyong.db`。应用对持久库跳过 `create_all`，避免再次隐式改表。


## 最终交付报告

- 实现：用户资料与校友转换、知识库目录/预览/版本、作业附件、管理端导入导出/DAU/配置/统计/确认、政治学习资料安全下载、AI 重新生成/附件消息/安全 Markdown 展示。
- 迁移：QA 数据库使用 database/qa_tongyong.db，迁移链包含 l3456、l2345、m4567。
- 质量：最近一次全量 pytest `199 passed`；ruff、mypy、全部前端 JS 的 node --check 通过。新增统一上传签名与聊天分层检索测试；所有质量命令显式使用内存 DB。
- 数据库：`database/qa_tongyong.db` 已迁移到 `m4567i8j9k0l (head)`；`database/longma.db` 已恢复旧表结构/业务行并保持 `k2345g6h7i8j`，未再用于测试。

## 当前遗留

- 浏览器端预览/下载按钮已实际触发；浏览器安全策略阻止 blob 新窗口与下载事件被自动接管，后端预览/下载接口已由全量集成测试覆盖。
- 通用上传校验已覆盖扩展名白名单、空文件、大小限制、已知二进制文件头/文本伪装检测及 UUID 物理名。


