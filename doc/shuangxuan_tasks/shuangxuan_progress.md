# 学术导师双选总体进度

> 更新日期：2026-08-17  
> 输入文档：`../shuangxuan_proposal.md`、`../shuangxuan_high-level-design.md`  
> 任务明细：`doc/shuangxuan_tasks/<shuangxuan_module-name>.md`  
> 状态图例：`- [ ]` 未完成，`- [x]` 已完成

## 模块进度

- [ ] M1 批次与状态机：[m1-batch-state-machine.md](./m1-batch-state-machine.md)
- [ ] M2 参与名单：[m2-participant-roster.md](./m2-participant-roster.md)
- [ ] M3 学生档案适配：[m3-student-profile-adapter.md](./m3-student-profile-adapter.md)
- [ ] M4 学生志愿：[m4-student-preferences.md](./m4-student-preferences.md)
- [ ] M5 导师选择：[m5-mentor-decisions.md](./m5-mentor-decisions.md)
- [ ] M6 匹配与结果：[m6-matching-results.md](./m6-matching-results.md)
- [ ] M7 调度 Worker：[m7-scheduler-worker.md](./m7-scheduler-worker.md)
- [ ] M8 通知与审计：[m8-notification-audit.md](./m8-notification-audit.md)
- [ ] M9 导入导出：[m9-import-export.md](./m9-import-export.md)
- [ ] M10 前端与兼容迁移：[m10-frontend-migration.md](./m10-frontend-migration.md)

## 任务统计

| 模块 | 最小任务数 | 已完成 |
| --- | ---: | ---: |
| M1 批次与状态机 | 16 | 0 |
| M2 参与名单 | 14 | 0 |
| M3 学生档案适配 | 14 | 0 |
| M4 学生志愿 | 15 | 0 |
| M5 导师选择 | 15 | 0 |
| M6 匹配与结果 | 17 | 0 |
| M7 调度 Worker | 16 | 0 |
| M8 通知与审计 | 13 | 0 |
| M9 导入导出 | 16 | 0 |
| M10 前端与兼容迁移 | 30 | 0 |
| 合计 | 166 | 0 |

## 执行顺序

1. 基础领域：M1 -> M2。
2. 资料与填报：M3 -> M4；M5 可在 M3、M4 接口稳定后开始。
3. 核心结果：M4 + M5 -> M6。
4. 横切服务：M8 可在 M1 后并行；M6 + M8 -> M7。
5. 文件能力：M2 完成后开发 M9 导入，M6 完成后补齐结果导出。
6. 集成收尾：M1-M9 -> M10。

## 阶段门禁

### Phase 1：批次基础

- [ ] M1、M2 模块完成定义全部满足。
- [ ] 批次迁移可逆，名单资格和单进行中约束测试通过。

### Phase 2：填报与选择

- [ ] M3、M4、M5 模块完成定义全部满足。
- [ ] 学生和导师数据可见性、截止锁定、4 人名额测试通过。

### Phase 3：匹配与自动化

- [ ] M6、M7、M8 模块完成定义全部满足。
- [ ] 主选、补录、阻塞延长、重开、自动发布和停机恢复测试通过。

### Phase 4：导入导出与交付

- [ ] M9、M10 模块完成定义全部满足。
- [ ] CSV/XLSX/XLS、三端页面、旧模块迁移和端到端验收通过。

## 整体完成定义

- [ ] 10 个模块在本页全部勾选完成。
- [ ] 每个模块文件中的最小任务和模块完成定义全部勾选。
- [ ] `shuangxuan_proposal.md` 第 17 章验收标准全部通过。
- [ ] `shuangxuan_high-level-design.md` 第 15 章需求追踪矩阵逐项验证。
- [ ] Alembic 新迁移在临时 SQLite 数据库完成 upgrade/downgrade，未修改受保护的开发数据库。
- [ ] 双选专项测试和全量 `pytest` 通过。
- [ ] `ruff check backend`、`mypy backend` 和新增前端 JS 的 `node --check` 通过。
- [ ] 独立 Worker `--once`、循环模式、失败恢复和通知去重验证通过。
- [ ] 浏览器完成主选、补录、延长、自动发布、撤回重开的全流程验收。

## 执行记录

- 2026-08-17：根据需求文档和概要设计拆分 M1-M10 最小可执行任务；全部任务初始状态为未完成。
- 2026-08-17：完成首个可运行集成版本。新增批次/名单/志愿/导师决定/结果/任务/通知投递模型、线性 Alembic 迁移、角色 API、确定性匹配、独立 60 秒 Worker、CSV/XLSX/XLS 解析导出路径、学生双选档案字段和三角色原生 JS 工作区。临时 SQLite upgrade -> downgrade -> upgrade 通过；专项测试 6 项通过；全量后端回归 234 项通过；全仓 mypy（188 个源文件）和 ruff 通过；新增/修改前端 JS 通过 Node 语法检查；Worker `--once` 通过。未勾选模块任务，因为租约竞争/恢复、通知和审计全事件接入、导入确认令牌、旧交流申请破坏性迁移及浏览器全链路验收尚未达到各模块完整完成定义。

## 当前阻塞

- 当前环境的依赖下载审批超时，`openpyxl`、`xlrd`、`xlwt` 已固定到 `requirements.txt`，但本机虚拟环境尚未安装，因此 XLSX/XLS 运行时实测未执行。
- 浏览器全流程验收、Worker 双实例租约竞争和旧交流申请破坏性迁移尚未执行，相关任务保持未完成。
