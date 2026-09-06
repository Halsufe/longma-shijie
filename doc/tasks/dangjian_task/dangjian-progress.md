# 党建数字化管理体系 · 任务进度总览

> 更新日期：2026-08-05  
> 输入文档：`../dangjian/dangjian_proposal.md`、`../dangjian/dangjian_design.md`  
> 状态图例：`- [ ]` 未开始，`- [x]` 已完成

## 模块进度

- [x] M1 党员档案模块（Party Profile）→ [m1-party-profile-dangjian.md](./m1-party-profile-dangjian.md)
- [x] M2 党建活动模块（Party Activity Core）→ [m2-party-activity-dangjian.md](./m2-party-activity-dangjian.md)
- [x] M3 报名签到模块（Registration & Attendance）→ [m3-registration-attendance-dangjian.md](./m3-registration-attendance-dangjian.md)
- [x] M4 工作档案模块（Party Archive）→ [m4-party-archive-dangjian.md](./m4-party-archive-dangjian.md)
- [x] M5 党建统计模块（Party Stats）→ [m5-party-stats-dangjian.md](./m5-party-stats-dangjian.md)
- [x] M6 成长档案联动模块（Achievement Link）→ [m6-achievement-link-dangjian.md](./m6-achievement-link-dangjian.md)
- [x] M7 通知与依赖适配模块（Notification & Dependency Adapter）→ [m7-notification-dependency-dangjian.md](./m7-notification-dependency-dangjian.md)
- [x] M8 兼容与迁移模块（Compatibility）→ [m8-compatibility-migration-dangjian.md](./m8-compatibility-migration-dangjian.md)

## 任务数量与状态

| 模块 | 任务数 | 完成数 |
| --- | ---: | ---: |
| M1 党员档案模块 | 7 | 7 |
| M2 党建活动模块 | 6 | 6 |
| M3 报名签到模块 | 6 | 6 |
| M4 工作档案模块 | 5 | 5 |
| M5 党建统计模块 | 6 | 6 |
| M6 成长档案联动模块 | 5 | 5 |
| M7 通知与依赖适配模块 | 6 | 6 |
| M8 兼容与迁移模块 | 5 | 5 |
| 合计 | 46 | 46 |

## 执行顺序建议

1. M8（先完成 T8-1 迁移）→ M1 → M2 → M3。
2. M4、M5 依赖 M2/M3，可并行。
3. M6 依赖 M1/M2/M3 与成果档案模块。
4. M7 依赖 M1/M2/M3，通知与依赖适配可并行。
5. 各模块完成后按 `../dangjian/dangjian_design.md` 第 12 章验收映射做整体验收。

## 整体完成定义

- [x] 8 个模块任务全部勾选完成。
- [x] 需求文档第 15 章验收要点全部通过。
- [x] 详细设计第 12 章验收映射逐项确认通过。

## 执行记录

### 2026-08-05 · 基线建立

- 已完整阅读 `dangjian_proposal.md` 与 `dangjian_design.md`。
- 按设计 M1-M8 拆分 46 个最小可执行任务，全部未开始。
- 党建模块当前无代码实现；users 表尚无 party_json，也无 party_* 表。
- 实施按执行顺序建议进行，任务完成时在对应模块文件勾选并更新本页统计。

### 2026-08-05 · 最终交付

- M8：新增 `users.party_json` 与三张 `party_*` 表的 Alembic 迁移，支持 upgrade/downgrade、旧用户兼容、软删除与路由顺序验证。
- M1：完成党员名册 CRUD、组合筛选、CSV 导入、阶段状态机、审计、发展材料管理和 `require_party_member` 权限依赖。
- M2/M3：完成党建活动 CRUD、发布与状态流转、对象可见性、学习材料/总结、报名取消、自助签到、管理员考勤和本人参与记录。
- M4/M5：完成只读活动/党员发展档案、组合筛选、UTF-8 BOM CSV 导出（5000 条上限）以及党员、参与率、材料和发展统计。
- M6：完成党员身份与已签到活动写入成长档案，统一生成 `pending` 成果，并以 `source_type/source_id` 防重。
- M7：完成通知幂等适配、活动材料入班级知识库、发展材料隔离、五个只读 Skill 契约和五个 Workflow 事件定义。
- 前端：新增学生党建视图和管理端党员、活动、统计、档案工作台，接入导航、交互状态、上传、导出和响应式样式。

### 质量门禁

- 党建定向测试：47 项通过。
- 全量 pytest：120 项通过。
- mypy：122 个源文件无问题。
- ruff：`backend` 全部通过。
- `node --check`：`party.js`、`admin_party.js`、`app.js`、`views/admin.js`、`ui.js` 全部通过。
- 浏览器冒烟：QA 服务首页正常加载，标题与登录界面可见，控制台无 error/warn。

### 数据库验证

- `database/qa_party.db`：Alembic 版本 `i012f3c4d5e6`，`party_activities`、`party_activity_participants`、`party_materials` 和 `users.party_json` 均存在，`PRAGMA integrity_check=ok`。
- `database/longma.db`：最终只读检查仍为版本 `h901e2b3c4d5`，无 `party_*` 表、无 `users.party_json`，`PRAGMA integrity_check=ok`。
- 事件记录：早期一次测试收集因应用 `create_all()` 曾在生产库短暂创建三张空党建表，已精确移除；随后增加根级 `conftest.py`，在测试收集前强制使用内存库并忽略有导入时网络副作用的 `test_agent.py`。生产库文件时间戳因此变为 `2026-08-05 16:13:49`，但最终结构、版本和完整性均确认未留下党建变更。

### 自主决策

- 党员档案删除使用 `party_json.deleted_at`，不删除用户；材料与活动均保留物理文件/业务行并执行软删除语义。
- 活动归档是 `finished/archived` 状态的只读聚合视图，不新增归档表。
- “全体学生”活动允许普通在校学生报名；教师和校友不继承学生党建权限。
- 发布即视为报名开始，报名截止、对象、指定名单和名额在发布后锁定。
- 自助签到窗口默认活动开始前后 60 分钟；管理员手工考勤不受该窗口限制。
- 活动学习材料进入班级知识库，党员发展材料始终排除；本期 Skill 仅暴露只读工具，Workflow 仅定义事件边界。
