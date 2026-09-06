# 政治面貌与党团活动全覆盖 · 任务进度总览

> 更新日期：2026-08-06  
> 输入文档：`../dangjian/dangjian_politic_proposal.md`、`../dangjian/dangjian_politic_design.md`  
> 状态图例：`- [ ]` 未开始，`- [x]` 已完成

## 模块进度

- [x] E1 政治面貌模块（Political Status）→ [dj_politic_e1-political-status.md](./dj_politic_e1-political-status.md)
- [x] E2 党团活动扩展（Party-League Activity Extension）→ [dj_politic_e2-party-league-activity.md](./dj_politic_e2-party-league-activity.md)
- [x] E3 政治学习资料模块（Political Learning Materials）→ [dj_politic_e3-political-learning-materials.md](./dj_politic_e3-political-learning-materials.md)
- [x] E4 统计扩展（Political Stats Extension）→ [dj_politic_e4-political-stats.md](./dj_politic_e4-political-stats.md)
- [x] E5 成长档案联动扩展（Achievement Link Extension）→ [dj_politic_e5-achievement-link.md](./dj_politic_e5-achievement-link.md)
- [x] E6 通知与依赖适配扩展（Notification & Dependency Adapter）→ [dj_politic_e6-notification-dependency.md](./dj_politic_e6-notification-dependency.md)
- [x] E7 兼容与迁移（Compatibility & Migration）→ [dj_politic_e7-compatibility-migration.md](./dj_politic_e7-compatibility-migration.md)

## 任务数量与状态

| 模块 | 任务数 | 完成数 |
| --- | ---: | ---: |
| E1 政治面貌模块 | 6 | 6 |
| E2 党团活动扩展 | 5 | 5 |
| E3 政治学习资料模块 | 5 | 5 |
| E4 统计扩展 | 5 | 5 |
| E5 成长档案联动扩展 | 4 | 4 |
| E6 通知与依赖适配扩展 | 5 | 5 |
| E7 兼容与迁移 | 5 | 5 |
| 合计 | 35 | 35 |

## 执行顺序建议

1. E7（先完成 E7-1 迁移与 E7-2 回填）→ E1 → E2 → E3。
2. E4 依赖 E1/E2/E3；E5 依赖 E2，可并行。
3. E6 依赖 E1/E2/E3，通知与依赖适配可并行。
4. 前端整合随 E1/E2/E3 逐步完成，最后全量回归与验收。
5. 各模块完成后按 `../dangjian/dangjian_politic_design.md` 第 12 章验收映射做整体验收。

## 整体完成定义

- [x] 7 个模块任务全部勾选完成。
- [x] 需求文档第 15 章验收要点全部通过。
- [x] 详细设计第 12 章验收映射逐项确认通过。
- [x] 既有党建模块（M1-M8）回归通过，`party_*` 接口兼容。

## 执行记录

### 2026-08-06 · 基线建立

- 已完整阅读 `dangjian_politic_proposal.md` 与 `dangjian_politic_design.md`。
- 按设计 E1-E7 拆分 35 个最小可执行任务，全部未开始。
- 现状：党建模块 M1-M8 已全部完成；`users` 尚无 `political_status`，无 `political_status_reviews` 与 `political_materials` 表。
- 实施按执行顺序建议进行，任务完成时在对应模块文件勾选并更新本页统计。

### 2026-08-06 · 实施启动

- 实际 Alembic head 已因后续 Skill 工作推进至 `j1234f5a6b7c`，因此政治扩展迁移接在该真实 head 之后，不按文档过时基线直接接 `i012f3c4d5e6`。
- 已从当前生产库创建独立副本 `database/qa_politic.db`；副本初始完整性为 `ok`，初始版本为 `j1234f5a6b7c`。
- 模块编排：E7/E1、E2/E5、E3/E6 分别由独立子 Agent 实现；主 Agent 负责 E4、前端、共享接口整合及全量验收。

### 2026-08-06 · E2/E5 完成

- E2：新增 `party_target_roles.py` 统一政治面貌与活动对象判定；保留旧活动枚举并增加主题团日、团学实践、团组织建设、其他团学，以及全体团员、党员与团员、群众对象；学生端和管理端枚举同步。
- E5：`/party/achievements/link` 支持 `link_type=league_activity` 与显式 `achievement_category`（organization/social）；仅团学活动且完成签到可联动，复用 `source_type=party` 与 `source_id` 防重，不提供团员身份联动。
- 定向验证：`test_party_league_activity.py`、`test_party_league_achievement_link.py` 及既有活动/报名/成就联动测试共 28 项通过；ruff、mypy 与前端 `node --check` 通过。

### 2026-08-06 · E1/E7 完成

- E7：新增 `k2345g6h7i8j` 迁移接真实 head `j1234f5a6b7c`，创建政治面貌字段、审核表、政治学习资料表和索引；回填 `party_json` 并记录初始化审计，支持 downgrade/upgrade。
- E1：新增学生政治面貌查询/申请、管理员审核列表及 approve/reject、审核审计与通过通知；党员档案创建/阶段流转自动同步政治面貌且不生成审核记录；补充政治学习资料 CRUD、可见性过滤和附件上传入口。
- 验证：全量 `pytest backend/tests` 为 173 passed；政治迁移与 E1 定向测试 11 passed；`ruff check backend`、`mypy backend` 通过。`database/qa_politic.db` 已完成 downgrade/upgrade，版本 `k2345g6h7i8j`，完整性 `ok`。
- 数据库说明：一次未正确传递 `DB_URL` 的 Alembic 命令将 `database/longma.db` 升级至 `k2345g6h7i8j`；只读核查确认完整性 `ok`，生产库现含政治字段/表及回填审计。后续不得回滚或覆盖生产库，需由交付方按备份策略决定处理。

### 2026-08-06 · E3/E4/E6 与前端收尾

- E3：完成政治学习资料的管理员 CRUD、软删除、PDF/JPG/JPEG/PNG 附件上传、20MB 限制和按政治面貌/指定人员可见性；教师仅能查看面向全体学生的已发布资料，指定人员资料不会进入知识库。
- E4：`/api/v1/party/stats` 增加 `political_status` 组合筛选、`political_counts`、`league_participation` 与 `political_materials` 指标；保留既有党员名册、参与、材料和发展统计字段，保证 M5 兼容。
- E6：政治面貌审核通过只通知申请人；定义 `party.political_status_approved` 事件边界；新增政治面貌、政治学习资料和管理员政治统计的只读查询方法，保持 `PARTY_SKILL_WRITE_TOOLS == ()`。
- 兼容策略：既有五项 `PARTY_SKILL_TOOL_CONTRACTS` 与 `PARTY_WORKFLOW_EVENTS` 保持不变；政治查询工具使用独立 `POLITICAL_SKILL_TOOL_CONTRACTS`，政治审核事件使用 `POLITICAL_WORKFLOW_EVENT_DEFINITIONS` 并合并到统一事件定义供新消费者发现。
- 前端：个人中心可查看/提交共青团员或群众申请；学生党建页展示适用政治学习资料；管理端提供政治面貌审核、资料管理和扩展统计入口。
- QA 迁移验证：仅对 `database/qa_politic.db` 执行 `k2345g6h7i8j -> j1234f5a6b7c -> k2345g6h7i8j`；最终 revision 为 `k2345g6h7i8j`，`PRAGMA integrity_check = ok`。
- 最终质量门禁：`pytest -q` 179 passed；`mypy backend` 141 个源文件无错误；`ruff check backend` 通过；`node --check` 对 `profile.js`、`party.js`、`admin_party.js` 通过。
- QA 验收服务：`http://127.0.0.1:8010/docs`，由 `backend/run_qa_server.bat` 启动并固定连接 `database/qa_politic.db`。
