# 党建数字化管理体系需求文档

> 文档版本：v0.1
> 编写日期：2026-08-05
> 适用模块：党建数字化管理体系（建设方案“党建数字化管理体系”+“党建管理模块”）
> 输入文档：《许国志大数据英才班党支部数字化综合平台建设方案》对照检查清单（`BD/建设方案对照检查清单.md`，第一部分第 1 项）
> 关联现状：`backend/app/models/user.py`、`backend/app/models/achievement.py`、`backend/app/models/notification.py`、`backend/app/models/file.py`（知识库）、`backend/app/ai/skills/`（Skill 调度依赖）

---

## 1. 文档目的与范围

本文档用于细化“党建数字化管理体系”需求，覆盖以下内容：

1. 党员基础信息：党员/预备党员/入党积极分子、入党时间、支部归属、申请状态、班级等结构化字段与统一管理。
2. 党建活动：活动通知、报名/签到参与记录、学习材料、活动总结，形成党建工作档案。
3. 党建权限：党支部管理员（合并至现有 `admin` 角色）维护与审核，学生党员查看与参与活动记录；教师/普通学生按角色隔离。
4. 党建统计/分析：党员人数、活动参与率、材料上传量、发展情况等管理端统计。
5. 党建数据与学生成长档案关联（党员经历进入个人成长记录）。
6. AI/自动化依赖关系：党建材料进入知识库、“党建查询 Skill”、活动通知与参与记录的 Workflow 联动；本文档只定义依赖边界，不展开细化。

本期不覆盖：创新项目空间、竞赛推荐/导师匹配 Skill、成果管理 Skill 等其余 P0 模块；党建查询 Skill 与 Workflow 调度器由后续文档单独细化。

本期落地方式（已确认）：

- 党支部管理员不新增角色，合并到现有 `admin`。
- 党员身份等结构化字段放在 `users` 表扩展字段（推荐新增 `party_json`，见第 5 章与待确认事项）。
- 系统只有一个“大数据党支部”，内含大数据 25 级、24 级、23 级、22 级等班级；班级列表可扩展。

## 2. 现状与改造思路

### 2.1 现状

当前系统（`BD/LM_SJ`，龙马·视界 / CampusMate）无党建模块（对照清单标注 P0、完全缺失），可复用的基础如下：

| 现状能力 | 位置/机制 | 党建复用方式 |
| --- | --- | --- |
| 4 种角色 | `backend/app/models/user.py`（student/teacher/admin/alumni） | 党建管理复用 admin；党员身份用扩展字段标记，不新增角色 |
| 站内通知 | `notifications` 表 + `NotificationService` | 活动通知、报名/签到结果通知 |
| 知识库 | `knowledge_files`（personal/class）+ 解析/RAG | 党建学习材料入库供 AI 检索 |
| 成果档案 | `achievements` 表（8 类、审核状态） | 党员经历写入成长档案 |
| Agent 工具与确认 | `agent_tools.py`、任务确认机制 | 党建查询 Skill 依赖 |
| 文件存储/附件 | 现有文件服务 | 学习材料、签到表、总结附件 |

`users` 表现有字段：`student_no/name/role/status/graduation_year/profile_json` 等，无党员相关字段；`profile_json` 目前承载专业、研究方向、技能、简介等个人信息。

### 2.2 改造思路

- `users` 表新增 `party_json` 扩展字段，存放党员身份与阶段信息（推荐，见第 5 章）。
- 新增 `party_activities`、`party_activity_participants` 两张业务表承载活动与报名/签到记录；活动数据不适合放在用户扩展字段。
- 党员发展材料建议使用独立 `party_materials` 表或 `party_json.materials` 附件列表（推荐独立表，便于统计与权限控制，见待确认事项）。
- 党建管理入口合并到管理后台；学生党员侧新增“党建”页面入口。
- 活动通知复用通知中心；自动提醒与批量通知由 Workflow 调度器触发（本期仅定义触发事件）。
- 党建学习材料上传后进入班级知识库（`scope=class`），供“党建查询 Skill”检索；党员发展材料默认不进知识库（涉敏）。
- 党员经历联动成长档案，推荐按“组织管理（organization）”分类写入，状态 `pending` 走现有审核流程。

## 3. 角色与权限

| 角色 | 党建权限 | 说明 |
| --- | --- | --- |
| 管理员（admin，兼任党支部管理员） | 党员档案维护与审核、发展阶段流转、活动发布/编辑/归档、报名与签到管理、统计与导出、成长档案联动操作 | 全部党建数据可见可管 |
| 学生党员（student 且 `party_json` 存在） | 查看党建活动、按活动对象报名、签到、查看本人党员信息与本人参与记录 | 党员类型：正式党员/预备党员/入党积极分子 |
| 普通学生（student 无党员身份） | 仅可见允许公开的活动通知，可按活动对象报名（如活动面向全体学生）；不可查看党员名册、发展情况与统计 | 按活动 `target_roles` 控制 |
| 教师（teacher） | 默认不参与党建管理；不可查看党员名册与发展材料 | 是否可查看活动由活动可见性控制，见待确认事项 |
| 校友（alumni） | 默认不开放党建功能；历史参与记录仅管理员可查 | 见待确认事项 |

权限隔离原则：

- 党员名册、发展阶段、发展材料、党员统计仅 `admin` 可见。
- 活动与参与记录：本人可见自己的，管理员可见全部；普通学生/教师不得越权查看他人党员信息。
- 后端使用 `api/deps.py` 现有依赖体系，新增“党员身份”判定（`party_json` 校验），所有接口做角色+身份双重校验。

## 4. 功能需求总览

| 子模块 | 核心需求 |
| --- | --- |
| 党员档案管理 | 党员基础信息 CRUD、发展阶段流转、班级/支部归属、材料管理、批量导入导出 |
| 党建活动管理 | 活动创建/编辑/发布/归档、通知、学习材料、活动总结 |
| 报名与签到 | 报名、取消报名、签到、补签/代签、参与记录 |
| 党建工作档案 | 按年份/班级/类别查看活动档案与党员发展档案 |
| 党建统计/分析 | 党员人数、活动参与率、材料上传量、发展情况多维统计 |
| 成长档案联动 | 党员身份与活动经历写入个人成长档案 |
| AI/自动化依赖 | 学习材料入知识库、党建查询 Skill 数据源、活动通知 Workflow 触发点 |

## 5. 党员基础信息字段定义

> 字段存放于 `users.party_json`（推荐新增列，格式为 JSON 字符串，默认 `{}`），键见下表。所有字段由管理员维护；学生本人只读展示。

| 显示名 | party_json 键 | 类型/格式 | 填写说明与枚举 |
| --- | --- | --- | --- |
| 党员类型 | `party_type` | 单选 | 正式党员/预备党员/入党积极分子 |
| 支部归属 | `branch_name` | 文本 | 固定“大数据党支部”，允许扩展 |
| 班级 | `class_name` | 文本 | 大数据25级/大数据24级/大数据23级/大数据22级等 |
| 年级 | `grade` | 文本 | 如 25/24/23/22；可由班级派生，见待确认事项 |
| 递交入党申请书时间 | `apply_date` | YYYY-MM | 必填 |
| 确定为入党积极分子时间 | `activist_date` | YYYY-MM | 预备党员/正式党员必填，积极分子可填 |
| 列为发展对象时间 | `target_date` | YYYY-MM | 发展对象及以上阶段填写 |
| 接受为预备党员时间 | `probation_date` | YYYY-MM | 预备党员/正式党员必填 |
| 转为正式党员时间 | `full_date` | YYYY-MM | 正式党员必填 |
| 入党时间 | `party_join_date` | YYYY-MM | 推荐=转为正式党员时间；预备党员阶段展示预备时间，见待确认事项 |
| 申请状态 | `apply_status` | 单选 | 递交申请/确定为积极分子/列为发展对象/接受为预备党员/转为正式党员/停止发展 |
| 停止发展原因 | `stop_reason` | 文本 | 仅 `apply_status=停止发展` 时填写 |
| 介绍人 | `introducer_names` | 文本 | 姓名，多人中文逗号分隔 |
| 培养联系人 | `mentor_names` | 文本 | 姓名，多人中文逗号分隔 |
| 备注 | `remark` | 长文本 | 可选 |

阶段时间轴约定：

- `apply_date → activist_date → target_date → probation_date → full_date` 逐步推进，后一阶段时间不得早于前一阶段。
- `party_type` 与 `apply_status` 联动校验（如 `party_type=正式党员` 时 `apply_status` 至少为“转为正式党员”），具体状态机见待确认事项。
- 党员身份变更（如转正）由管理员操作，记录到审计日志。

## 6. 党建活动字段定义

新增 `party_activities` 表：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | int | 主键 |
| `title` | str | 活动标题 |
| `category` | str | 活动类别：组织生活会/主题党日/理论学习/志愿公益/发展工作/民主评议/专题教育/其他 |
| `content` | text | 活动通知正文 |
| `location` | str | 地点 |
| `start_at` | datetime | 开始时间 |
| `end_at` | datetime | 结束时间 |
| `registration_deadline` | datetime | 报名截止时间（可空=不报名，直接按应参加名单） |
| `target_roles` | str | 参加对象：全体党员/党员与积极分子/预备党员与积极分子/全体学生/指定人员 |
| `target_member_ids_json` | text | 指定人员名单（`target_roles=指定人员` 时使用） |
| `max_participants` | int | 报名人数上限（可空） |
| `materials_json` | text | 学习材料附件列表（文件名、文件标识、上传时间） |
| `summary` | text | 活动总结（活动结束后填写） |
| `summary_attachments_json` | text | 总结附件（照片、签到表、新闻稿等） |
| `status` | str | `draft/published/ongoing/finished/archived` |
| `created_by` | int | 创建管理员（FK users.id） |
| `created_at/updated_at/deleted_at` | datetime | 时间戳 |

活动状态流转：`draft → published → ongoing → finished → archived`；发布后可编辑，开始报名后不可再修改报名截止；归档后仅可查看。

## 7. 报名与签到需求

新增 `party_activity_participants` 表：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | int | 主键 |
| `activity_id` | int | 活动 ID（FK） |
| `user_id` | int | 用户 ID（FK） |
| `registration_status` | str | `registered/cancelled` |
| `attendance_status` | str | `none/signed_in/absent` |
| `sign_in_time` | datetime | 签到时间 |
| `sign_in_method` | str | `manual/self/qr/location`（本期至少支持 manual） |
| `created_at/updated_at` | datetime | 时间戳 |

约束：`(activity_id, user_id)` 唯一；活动表与参与表建立外键，活动删除时级联清理参与记录（软删除场景沿用 `deleted_at`）。

交互需求：

1. 活动发布后，管理员可选择“立即发送站内通知”；自动提醒由 Workflow 调度器按 `start_at/registration_deadline` 触发（依赖，见第 11 章）。
2. 符合活动对象的用户可报名；报名截止后不可新增/取消报名（管理员可代报名）。
3. 取消报名：报名截止前可自助取消；取消后释放名额。
4. 签到：活动开始前后开放签到窗口（窗口时间可配置）；学生党员可自助签到，管理员可代签/补签/标记缺席。
5. 学生可查看本人报名与签到记录；管理员可查看全部参与名单并导出。
6. 签到方式本期建议支持管理员手工签到，二维码/口令/位置签到作为后续增强（见待确认事项）。

## 8. 党建工作档案

1. 活动归档：活动结束后，系统汇总活动信息、参加对象、报名/签到名单、学习材料、活动总结与附件，形成一份活动档案。
2. 党员发展档案：按党员展示身份阶段时间轴（递交申请→积极分子→发展对象→预备党员→正式党员）与材料清单。
3. 查询维度：年份、班级、活动类别、党员类型、申请状态。
4. 导出：党员名册、活动参与名单、活动档案汇总建议本期支持 CSV 导出；PDF/Word 见待确认事项。

## 9. 党建统计/分析

管理端提供党建统计页，支持按班级、年级、年份、活动类别筛选：

| 统计项 | 口径（推荐） | 说明 |
| --- | --- | --- |
| 党员人数 | 按 `party_type` 分组 | 正式党员/预备党员/入党积极分子人数 |
| 班级分布 | 按 `class_name` 分组 | 各班级党员人数 |
| 活动参与率 | 签到人数/应参加人数 | 应参加人数口径见待确认事项 |
| 报名率 | 报名人数/应参加人数 | 可选 |
| 材料上传量 | 学习材料+党员发展材料数量 | 按年月/活动/党员统计 |
| 发展情况 | 按 `apply_status` 分组 | 各阶段人数及年度转正数 |

统计结果同时纳入管理端“党建/竞赛/项目/成果多维统计”入口（对照清单 P0/P1 项）。

## 10. 与成长档案联动

需求目标：党员经历进入个人成长记录。

推荐方案：

1. 党员身份：管理员将学生标记为正式党员/预备党员后，可一键生成一条“组织管理（organization）”类成果（标题如“许国志大数据英才班党支部党员”），写入本人 `achievements`，状态 `pending`，经管理员审核后计入成长档案。
2. 活动经历：学生参加并完成签到的党建活动，可按活动生成“组织管理/社会实践（social）”类成果（按活动性质），由学生或管理员一键写入，状态 `pending`。
3. 联动不自动生成未审核数据，避免污染正式档案；是否改为自动写入见待确认事项。

备选方案：在成果档案中新增“党建经历”独立分类（需同步调整 8 类成果模板与统计），见待确认事项。

## 11. AI 对接与依赖关系

本章只定义依赖边界，具体设计后续单独细化（已确认由后续文档补充）。

### 11.1 党建材料与知识库

- 党建学习材料（活动附件）上传后进入班级知识库（`scope=class`），沿用 `knowledge_files` 解析与 RAG 检索。
- 党员发展材料、思想汇报、政审材料等涉敏材料默认不进知识库、不参与 AI 检索；如业务需要，后续单独评估权限与脱敏方案。

### 11.2 党建查询 Skill（依赖）

- 依赖本模块的党员档案与活动数据，为 Agent 提供只读查询工具，建议包括：党员名单查询、党员信息查询、活动列表/详情查询、本人参与记录查询。
- 工具必须按角色+党员身份做权限隔离；写操作（如需 Agent 修改活动/材料）走现有任务确认机制。
- Skill 触发词、提示词、返回格式由后续“AI Agent 业务 Skills”文档细化。

### 11.3 Workflow 工作流（依赖）

- 触发事件：活动发布通知、报名截止提醒、活动开始提醒、活动结束后的参与情况记录、党员发展阶段变更通知。
- 依赖现有 `NotificationService`，通知幂等沿用 `type + ref_type + ref_id` 判定；任务运行记录由 Workflow 调度器提供。
- 调度实现与失败重试由后续“Workflow 工作流自动化”文档细化。

## 12. 数据模型与接口落地说明

### 12.1 数据模型

- `users` 表新增 `party_json`（Text，默认 `{}`），新增 `party` 读写属性（沿用 `profile` 的 JSON 处理模式）。
- 新增 `party_activities` 表。
- 新增 `party_activity_participants` 表，`(activity_id, user_id)` 唯一索引。
- 可选新增 `party_materials` 表（党员发展材料，推荐），见待确认事项。
- 索引建议：`party_activities(status, start_at)`、`party_activity_participants(activity_id, user_id)`。
- Alembic 迁移：本期新增迁移脚本，SQLite/PostgreSQL 兼容。

### 12.2 接口清单（概要）

> 静态路径注册在 `/{party_activity_id}` 之前，避免被动态参数吞掉；权限列写默认角色。

| 方法 | 路径 | 权限 | 说明 |
| --- | --- | --- | --- |
| GET | `/api/v1/party/members` | admin | 党员名册（支持班级/类型/状态筛选与分页） |
| POST | `/api/v1/party/members` | admin | 新增/批量导入党员身份 |
| PUT | `/api/v1/party/members/{user_id}` | admin | 更新党员基础信息 |
| PUT | `/api/v1/party/members/{user_id}/status` | admin | 发展阶段流转（转正/停止发展等） |
| POST | `/api/v1/party/materials` | admin | 上传党员发展材料 |
| GET | `/api/v1/party/members/{user_id}/materials` | admin | 党员材料列表 |
| GET | `/api/v1/party/mine` | 党员本人 | 本人党员信息与参与记录 |
| GET | `/api/v1/party/activities` | 登录用户（按可见性） | 活动列表 |
| POST | `/api/v1/party/activities` | admin | 创建活动 |
| PUT | `/api/v1/party/activities/{id}` | admin | 编辑活动 |
| POST | `/api/v1/party/activities/{id}/publish` | admin | 发布并通知 |
| GET | `/api/v1/party/activities/{id}` | 可见用户 | 活动详情（含材料/总结） |
| POST | `/api/v1/party/activities/{id}/register` | 目标用户 | 报名 |
| DELETE | `/api/v1/party/activities/{id}/register` | 本人 | 取消报名 |
| POST | `/api/v1/party/activities/{id}/sign-in` | 本人/admin | 签到/代签 |
| PUT | `/api/v1/party/activities/{id}/participants/{user_id}/attendance` | admin | 补签/标记缺席 |
| POST | `/api/v1/party/activities/{id}/summary` | admin | 填写活动总结与归档 |
| GET | `/api/v1/party/activities/{id}/archive` | admin | 活动档案 |
| GET | `/api/v1/party/stats` | admin | 党建统计 |
| POST | `/api/v1/party/stats/export` | admin | 统计/名册导出 |
| POST | `/api/v1/party/achievements/link` | admin/本人 | 一键写入成长档案 |

### 12.3 前端

- 管理后台新增“党建管理”页签：党员档案、活动管理、统计、导出。
- 学生党员新增“党建”页面：活动通知、报名/签到、本人党员信息、本人参与记录。
- 普通学生按权限展示活动通知（如活动面向全体学生）。
- 沿用原生 JS + hash 路由，新增 `frontend/js/views/party.js`（学生端），管理端在 `admin.js` 内新增党建管理区块（或独立 `admin_party.js`）。

## 13. 校验规则汇总

| 规则 | 约束 |
| --- | --- |
| 党员类型 | 仅允许 正式党员/预备党员/入党积极分子 |
| 申请状态 | 仅允许 递交申请/确定为积极分子/列为发展对象/接受为预备党员/转为正式党员/停止发展 |
| 阶段时间 | `YYYY-MM`；后一阶段时间不早于前一阶段 |
| 班级 | 大数据25级/24级/23级/22级等，管理端可维护枚举 |
| 报名截止 | 必须早于活动开始时间；发布后不可改早于当前时间 |
| 报名对象 | 仅活动 `target_roles` 对应用户可报名；不可重复报名 |
| 签到 | 仅在签到窗口内自助签到；管理员可代签/补签 |
| 参与记录 | `(activity_id, user_id)` 唯一；报名状态与签到状态分离 |
| 附件 | 学习材料/总结附件沿用系统文件服务，PDF/JPG/PNG，单文件不超过 20MB（可配置） |
| 成长档案联动 | 写入成果后状态为 `pending`，复用现有审核流程 |

## 14. 待确认事项

以下事项用户未明确，本文档给出推荐默认值，评审时确认：

1. 党员身份字段存放：推荐独立新增 `users.party_json`，而不是并入 `profile_json`，避免与个人基础资料混存。
2. 发展阶段状态机：推荐按时间轴字段（`apply_date/activist_date/target_date/probation_date/full_date`）记录完整过程；如只需当前状态可简化为一个枚举字段。
3. 普通学生/教师的活动可见性：推荐普通学生可按活动对象报名，教师默认不可查看党员名册，活动详情按活动设置可见。
4. 签到方式：本期推荐管理员手工签到 + 学生自助签到；二维码/口令/位置签到是否本期实现待确认。
5. 活动参与率分母：推荐“应参加名单（`target_roles`/`target_member_ids_json` 展开）”作为分母，报名人数作为备选口径。
6. 成长档案联动方式：推荐“一键写入 + pending 审核”；是否自动写入、是否新增“党建经历”独立成果分类待确认。
7. 涉敏材料：推荐党员发展材料不进知识库；如后续需要 AI 检索，需单独评估脱敏与权限。
8. 班级字段：推荐在 `party_json` 内维护班级/年级；如其他模块也需要班级筛选，再考虑给 `users` 增加通用班级字段。
9. 导出范围：本期推荐 CSV 导出党员名册、参与名单、统计；PDF/Word 档案导出是否本期实现待确认。
10. 校友历史记录：推荐校友不开放党建功能，历史参与记录仅管理员可查；是否保留校友党员身份展示待确认。

## 15. 验收要点

1. 管理员可维护党员基础信息：党员类型、入党时间、支部归属、申请状态、班级，字段与第 5 章一致。
2. 管理员可发布党建活动，活动含通知、报名截止、学习材料、活动总结，形成活动档案。
3. 学生党员可报名、签到，并查看本人参与记录；数据按角色隔离，普通学生/教师不能查看党员名册与统计。
4. 管理端可完成党建统计：党员人数、活动参与率、材料上传量、发展情况，支持班级/年份筛选。
5. 党建学习材料可进入班级知识库，为“党建查询 Skill”提供数据（Skill 本身按后续文档验收）。
6. 党员经历可一键联动写入成长档案（`organization` 分类，`pending` 审核）。
7. 活动通知落库到通知中心，通知幂等（重复执行不产生重复通知，依赖 Workflow 调度验收）。
8. 全流程接口权限校验生效：管理员越权不可被学生复现，普通学生不可读取党员数据。
