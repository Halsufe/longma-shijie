# AI Agent 业务 Skills 需求文档

> 文档版本：v0.1
> 编写日期：2026-08-05
> 适用模块：AI Agent 业务 Skills（建设方案对照检查清单第一部分第 3 项）
> 输入文档：《建设方案对照检查清单》（`BD/建设方案对照检查清单.md`）、`CampusMate_项目需求分析文档_V2.0_.md`、`龙马视界-系统架构与功能设计.md`、`doc/dangjian/dangjian_proposal.md`
> 关联现状：`backend/app/ai/skill_dispatcher.py`、`backend/app/ai/skills/`、`backend/app/ai/agent.py`、`backend/app/ai/agent_tools.py`、`backend/app/core/confirmation.py`、`backend/app/services/party_skill_boundary.py`、`backend/app/services/recommendation_service.py`

---

## 1. 文档目的与范围

本文档细化“AI Agent 业务 Skills”需求，覆盖建设方案要求的 4 个业务 Skill：

1. 竞赛推荐 Skill：结合学生画像与比赛库推荐，并解释推荐理由。
2. 导师匹配 Skill：根据对话中提供的项目描述做语义匹配，推荐合适教师与研究方向。
3. 党建查询 Skill：查询党员/活动信息，依赖已实现的党建模块，只读。
4. 成果管理 Skill：允许学生用 AI 新增、修改、删除、查询本人成果，写操作走任务确认。

已确认的落地方式：

- 输出位置：`BD/LM_SJ/skills_proposal.md`。
- 4 个业务 Skill 详细设计；竞赛结构化字段、创新项目空间、Agent 记忆持久化等前置能力只写依赖边界，不展开实现。
- 党建查询 Skill 基于已实现的党建模块（`party` 接口与 `PartySkillBoundary`）写完整查询需求。
- 成果管理 Skill 覆盖全部 8 类成果，学生只能操作本人成果，写操作全部任务确认，新增数据默认 `pending` 审核。
- 4 个 Skill 同时支持独立 `@触发词` 与 `@agent` 意图自动调度。
- 竞赛推荐与导师匹配本期做语义向量匹配；导师匹配输入先来自对话中的项目描述，不依赖未实现的项目空间。
- 文档包含数据模型变更、接口清单、校验规则、验收要点与任务拆分，颗粒度对齐 `doc/dangjian/dangjian_proposal.md`。

本期不覆盖：党建模块本身、创新项目空间、Workflow 调度器、Agent 记忆持久化、RAG 通用向量化、Skill 配置编辑（触发词/说明/模型配置编辑）、成果导出。以上内容分别由对应模块文档或 P1/P2 迭代承接，本文档只在依赖边界处说明。

---

## 2. 现状与改造思路

### 2.1 现状

| 能力 | 现状位置 | 与本需求的关系 |
| --- | --- | --- |
| Skill 调度 | `skill_dispatcher.py` + `ai/skills/*`（当前 6 个文本/代码 Skill，均为 prompt 型） | 新增 4 个业务 Skill 的种子、触发词、Prompt 构建器与调度注册 |
| Agent 模式 | `@agent` + `agent_tools.py` 18 个工具（12 查询 + 6 管理） | 业务 Skill 需并入 Agent 意图自动调度，并新增业务工具 |
| 任务确认 | `core/confirmation.py`（JWT 预览→确认，5 分钟有效）；`_CONFIRMABLE_OPERATIONS` 已有 `achievement.create/update/delete` | 成果管理 Skill 写操作必须复用确认机制；业务接口尚未校验确认令牌，需补 |
| 党建模块 | 已实现：`party` 路由、`party_*` 服务、`party_skill_boundary.py` 5 个只读工具契约 | 党建查询 Skill 直接复用，不新增写能力 |
| 推荐服务 | `recommendation_service.py` 关键词+热度打分 | 竞赛推荐/导师匹配需升级为语义向量匹配，关键词作为兜底 |
| 向量能力 | `file_chunks` 无 embedding 列；`requirements-optional.txt` 已有 `sentence-transformers==3.0.1` | 新增业务 Skill 专用 embedding 存储与语义检索服务 |
| 前端 | `chat.js` 硬编码 6 个 Skill chips；`admin.js` 已有 Skill 启停列表 | 需要展示/调度 4 个业务 Skill |

### 2.2 改造思路

- 将 4 个业务 Skill 注册为系统 Skill（`category=business`），同时支持 `@触发词` 与 `@agent` 意图调度。
- 新增统一的“业务 Skill 执行层”，复用现有确认机制、审计、`skill_calls` 记录；普通 Skill 保留 prompt 型实现。
- 新增语义向量服务：对比赛、教师方向生成 embedding 并持久化，用于竞赛推荐与导师匹配；模型不可用时回退到现有关键词打分。
- 成果管理 Skill 新增本人成果的 Agent 工具，写操作必须预览、确认、审计；成果接口补充确认令牌校验。
- 党建查询 Skill 直接包装 `PartySkillBoundary`，不绕过现有权限。

---

## 3. 总体需求

### 3.1 业务 Skill 清单总览

| Skill 名 | 展示名 | 类别 | 推荐触发词 | 读写 | 主要权限 |
| --- | --- | --- | --- | --- | --- |
| `competition_recommend` | 竞赛推荐 | business | `@竞赛推荐`、`@比赛推荐`、`@推荐比赛`、`@competition` | 只读 | 所有登录用户 |
| `mentor_match` | 导师匹配 | business | `@导师匹配`、`@找导师`、`@匹配导师`、`@mentor` | 只读 | 所有登录用户 |
| `party_query` | 党建查询 | business | `@党建查询`、`@党建`、`@党员查询`、`@party` | 只读 | 按党建模块权限 |
| `achievement_manage` | 成果管理 | business | `@成果管理`、`@我的成果`、`@成果录入`、`@achievement` | 读 + 写（写需确认） | 本人成果 |

### 3.2 双触发机制

1. 独立触发词：消息以 `@业务触发词` 开头时，由 `SkillDispatcher` 命中对应业务 Skill，进入业务 Skill 执行流程。
2. Agent 自动调度：消息以 `@agent`（含 `@智能`、`@助手`、`@ai`）开头，或普通对话意图明显时，由 Agent 识别意图并调用业务工具。
3. 优先级：`@agent` 前缀优先进入 Agent 模式；其他消息按 Skill 触发词匹配；多个触发词同时命中时取注册顺序第一个。

### 3.3 执行流程

业务 Skill 执行层（建议 `backend/app/ai/business_skills/` 或 `business_skill_service.py`）统一处理两类入口：

1. 解析意图与参数（从触发词后的自然语言提取）。
2. 调用只读数据服务：竞赛推荐、导师匹配、党建查询、成果查询。
3. 成果写操作生成预览与确认令牌，等待用户确认。
4. 将结构化结果交给 LLM 生成自然语言回复，推荐类必须包含理由。
5. 记录 `skill_calls`；写操作写 `audit_logs`。

### 3.4 权限与安全

| Skill | 权限矩阵 |
| --- | --- |
| 竞赛推荐 | 所有登录用户；不展示未审核（`pending/rejected`）比赛 |
| 导师匹配 | 所有登录用户；只返回在职教师、有效研究方向 |
| 党建查询 | 管理员可查名册/统计/全部活动；党员本人可查本人信息与记录；普通用户按活动可见性查询；不开放写 |
| 成果管理 | 仅本人查询/新增/修改/删除本人成果；管理员审核走原流程，不通过 Skill 代审 |

安全要求：

- 业务 Skill 不绕过 `api/deps.py` 的登录、角色、党员身份校验。
- 党建发展材料、思想汇报等涉敏材料不进入 AI 检索与 Skill 返回。
- 推荐/匹配结果不泄露教师联系方式、党员发展材料等非授权信息。
- 所有写操作必须经过任务确认，确认令牌过期或数据不一致时拒绝执行。

### 3.5 任务确认

- 复用 `ConfirmationManager`：`POST /api/v1/confirm/preview` 生成预览与令牌，业务接口校验令牌后执行。
- 成果管理 Skill 新增/修改/删除的确认预览必须展示：操作类型、对象摘要、关键字段、影响说明。
- 确认令牌与数据哈希绑定，用户、操作、数据任一不一致即拒绝。
- 确认有效期 5 分钟；过期后需要重新预览。
- 写操作无论成功失败都记录审计日志与 `skill_calls`。

### 3.6 语义向量服务

本期为业务 Skill 增加语义匹配能力，需求如下：

1. 启用 `sentence-transformers`，加载中文 embedding 模型；推荐 `BAAI/bge-small-zh-v1.5`（512 维），支持通过配置切换模型与离线模型路径。
2. 新增 `skill_embeddings` 表持久化业务实体向量（见第 8 章）。
3. 语义匹配以余弦相似度为主，关键词精确命中加权，热度作为同分兜底。
4. 模型加载失败、向量缺失或相似度全部低于阈值时，自动回退到现有关键词推荐，保证功能可用。
5. 向量在业务数据变更时增量刷新：比赛审核通过/更新/删除、教师方向新增/更新/删除、教师资料更新。
6. 用户画像向量按需生成，不要求批量入库。

### 3.7 观测与审计

- 每个 Skill 调用写入 `skill_calls`：Skill 名、用户、输入、输出摘要、耗时、状态、Token 用量、错误信息。
- 成果写操作写入 `audit_logs`：操作者、动作、目标 ID、结果、确认令牌哈希（可审计但不在前端展示原文）。
- 管理端 Skill 列表可启停 4 个业务 Skill；调用统计沿用现有 Skill 统计。

---

## 4. 竞赛推荐 Skill（competition_recommend）

### 4.1 目标

结合学生画像与比赛库，向学生推荐适合的比赛，并解释推荐理由。

### 4.2 触发与输入

| 项 | 说明 |
| --- | --- |
| 独立触发词 | `@竞赛推荐`、`@比赛推荐`、`@推荐比赛`、`@competition` |
| Agent 意图 | “推荐比赛”“有什么比赛适合我”“近期比赛”“竞赛推荐”等 |
| 画像输入 | `users.profile_json` 的 `major`、`research`、`skills`、`field`、`directions`、`grade` |
| 对话补充输入 | 用户在对话中描述的赛道、方向、技能、参赛目标、时间限制 |
| 可选筛选 | 标签、来源、截止日期范围、数量（默认 5，上限 10） |

### 4.3 执行逻辑

1. 组装用户文本：画像字段 + 对话补充描述。
2. 语义向量召回：对 `resources` 中 `type=competition`、`status=approved`、未删除的比赛（标题 + 正文 + 标签 + 来源）做向量匹配。
3. 关键词加权：画像关键词命中标签、标题时加分。
4. 过滤已截止比赛，按综合得分排序，取前 N 个。
5. 生成推荐理由：命中方向/技能、匹配标签、比赛来源、截止时间、热度。

### 4.4 输出

每条推荐包含：

- 比赛 ID、标题、类型、标签、来源、截止时间、浏览量/点赞数。
- 推荐理由（必须解释“为什么适合用户”）。
- 综合得分（调试/置信度展示可选）。

回复建议使用中文表格 + 简短理由，例如：“推荐理由：与你填写的‘机器学习’方向匹配，截止 2026-09-30。”

### 4.5 验收

1. 学生画像含“机器学习”时，能推荐标签或正文含“机器学习/人工智能”的比赛。
2. 已截止比赛不出现。
3. 无画像关键词时按热度推荐，不返回空结果。
4. 语义模型不可用时回退关键词推荐，不报错。

---

## 5. 导师匹配 Skill（mentor_match）

### 5.1 目标

根据用户对话中提供的项目描述做语义标签匹配，推荐合适教师与研究方向。

### 5.2 触发与输入

| 项 | 说明 |
| --- | --- |
| 独立触发词 | `@导师匹配`、`@找导师`、`@匹配导师`、`@mentor` |
| Agent 意图 | “帮我找导师”“哪个老师适合这个项目”“导师匹配”等 |
| 必填输入 | 项目描述（来自对话文本，建议不少于 20 字；不足时引导用户补充） |
| 可选输入 | 教师姓名/学院筛选、方向筛选、结果数量（默认 5，上限 10） |

### 5.3 执行逻辑

1. 对项目描述生成向量。
2. 对 `teacher_directions`（标题 + 描述 + 标签）与教师 `profile_json`（`research`、`skills`、`directions`、`field`）做向量匹配。
3. 综合得分：语义相似度为主，关键词命中加权，同分按教师方向更新时间兜底。
4. 每个教师取最优研究方向作为推荐依据，输出推荐理由。
5. 本项目描述仅用于本次会话计算，不依赖创新项目空间；是否沉淀到用户长期记忆由 Agent 记忆持久化（P1）承接。

### 5.4 输出

每条推荐包含：

- 教师 ID、姓名。
- 匹配的研究方向 ID、标题、描述、标签。
- 相似度/综合得分。
- 推荐理由（说明项目描述与方向的匹配点）。

本期不包含“一键发起交流申请”；如后续需要，在确认机制下走现有交流申请接口，作为增强项。

### 5.5 验收

1. 输入“基于大语言模型的自动论文摘要系统”能匹配 NLP/机器学习方向教师。
2. 匹配结果包含方向与理由，教师信息不越权展示。
3. 项目描述过短时引导补充，不静默返回空结果。

---

## 6. 党建查询 Skill（party_query）

### 6.1 目标

基于已实现的党建模块，让用户用自然语言查询党员/活动/本人参与信息；全程只读。

### 6.2 触发与输入

| 项 | 说明 |
| --- | --- |
| 独立触发词 | `@党建查询`、`@党建`、`@党员查询`、`@party` |
| Agent 意图 | “本周有什么党建活动”“党员有多少人”“我的签到记录”“活动几点开始”等 |

### 6.3 数据与工具

复用 `PartySkillBoundary` 的 5 个只读工具契约：

| 工具 | 权限 | 说明 |
| --- | --- | --- |
| `list_party_members` | admin | 党员名册查询（班级/类型/状态筛选、分页） |
| `get_party_member` | admin/self | 党员信息查询 |
| `list_party_activities` | 登录用户（按可见性） | 活动列表查询 |
| `get_party_activity` | 可见用户 | 活动详情查询 |
| `get_party_my_records` | 本人 | 本人报名/签到记录查询 |

补充需求：

- 用户询问活动学习材料内容时，可从班级知识库检索党建活动材料并给出引用来源；涉敏发展材料始终排除。
- 党建查询 Skill 不提供任何写工具，不触发报名/签到/修改活动。
- 查询结果按现有 `party` 接口的可见性口径返回，Skill 不得绕过权限。

### 6.4 输出

按问题类型输出：

- 党员名册/统计：表格（姓名、班级、类型、状态），管理员可见。
- 活动列表/详情：标题、类别、时间、地点、报名截止、状态、材料/总结摘要。
- 本人记录：活动、报名状态、签到状态、签到时间。

### 6.5 验收

1. 管理员可问“党员有多少人”“XX 班党员名单”。
2. 党员本人可问“我的党建活动记录”。
3. 普通学生查询党员名册被拒绝；活动按可见性返回。
4. 无写操作可被触发；接口权限用例全部通过。

---

## 7. 成果管理 Skill（achievement_manage）

### 7.1 目标

允许学生用 AI 新增、修改、删除、查询本人成果，覆盖全部 8 类；写操作全部走任务确认。

### 7.2 触发与输入

| 项 | 说明 |
| --- | --- |
| 独立触发词 | `@成果管理`、`@我的成果`、`@成果录入`、`@achievement` |
| Agent 意图 | “帮我录入论文”“添加竞赛获奖”“修改我的项目成果”“删除某条成果”“我的成果统计”等 |
| 覆盖分类 | paper、award、research、patent、innovation、organization、social、arts |

### 7.3 功能需求

#### 查询

- 查询本人成果：按分类、状态、年份、关键词筛选，返回模板字段。
- 查询公开成果：仅返回 `approved` 且 `is_public=true` 的数据。
- 查询模板说明：AI 按分类模板向用户逐项收集必填字段。

#### 新增

- AI 按分类模板收集必填字段，复用 `achievement_service` 的分类/级别/模板校验。
- 新增成果默认 `pending`，进入原审核流程。
- 证明材料缺失时按第 13 章待确认策略处理（推荐：提示用户先上传或到“我的成果”页补充，不静默落库）。

#### 修改

- 仅允许修改本人成果；AI 先读取现状，用户确认变更内容。
- 修改沿用模板校验；是否重置审核状态见第 13 章待确认事项。

#### 删除

- 仅允许删除本人成果；软删除，复用现有 `AchievementRepository.soft_delete`。

### 7.4 任务确认

1. 写操作先调用 `POST /api/v1/confirm/preview`（operation 为 `achievement.create/update/delete`），返回预览与确认令牌。
2. 用户确认后，业务接口携带令牌执行；令牌校验失败或过期则拒绝。
3. 预览必须包含操作类型、成果标题/分类、变更字段摘要、影响说明。
4. 写操作成功/失败均写审计日志与 `skill_calls`。

### 7.5 验收

1. 可新增/修改/删除全部 8 类本人成果，模板校验生效。
2. 非本人成果不可通过 Skill 读取/修改/删除。
3. 新增成果默认 `pending`，删除为软删除。
4. 无确认令牌的写操作不执行；令牌过期/数据不一致时拒绝。
5. 写操作有审计记录。

---

## 8. 数据模型变更

### 8.1 新增 `skill_embeddings` 表

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | int PK | 主键 |
| `entity_type` | str(40) | `competition` / `teacher_direction` / `teacher_profile` |
| `entity_id` | int | 业务实体 ID |
| `source_text` | text | 生成向量所用的文本（便于排查与重建） |
| `embedding_json` | text | 向量数组 JSON（SQLite/PG 通用；后续可迁移 pgvector） |
| `version` | int | 向量版本（模型或文本变化时递增） |
| `created_at/updated_at` | datetime | 时间戳 |

约束与索引：

- 唯一索引 `(entity_type, entity_id)`。
- 索引 `entity_type + updated_at`，便于增量刷新。
- 不存放敏感文本；党建发展材料不生成向量。

### 8.2 现有模型调整

- `AchievementCreate` / `AchievementUpdate` 新增可选 `confirmation_token` 字段。
- 成果删除接口新增可选 `confirmation_token` 查询参数（或等价请求头）。
- `skills` 表无需改结构；通过种子数据新增 4 个业务 Skill。
- `users.profile_json` 保持现有画像字段，本期不新增画像字段。

### 8.3 配置项

| 配置 | 推荐值 | 说明 |
| --- | --- | --- |
| `EMBEDDING_MODEL_NAME` | `BAAI/bge-small-zh-v1.5` | embedding 模型，可配置离线路径 |
| `EMBEDDING_DEVICE` | `cpu` | 设备 |
| `EMBEDDING_DIM` | 512 | 与模型输出维度一致 |
| `SKILL_RECOMMEND_LIMIT` | 5 | 默认推荐数量 |
| `SEMANTIC_MIN_SCORE` | 0.35 | 低于该值的语义匹配不计入，避免低质量推荐 |

---

## 9. 接口清单

### 9.1 新增接口（建议）

| 方法 | 路径 | 权限 | 说明 |
| --- | --- | --- | --- |
| POST | `/api/v1/skills/business/competition-recommend` | 登录用户 | 竞赛推荐；body：`query`、`tags`、`source`、`limit` |
| POST | `/api/v1/skills/business/mentor-match` | 登录用户 | 导师匹配；body：`project_description`、`tag`、`teacher_name`、`limit` |

> 上述接口供 Skill 执行层与前端快捷调用；对话场景可只走后端执行层，不强制前端直连。

### 9.2 变更接口

| 方法 | 路径 | 变更 | 说明 |
| --- | --- | --- | --- |
| POST | `/api/v1/achievements` | 新增可选 `confirmation_token` | 校验令牌后创建 |
| PUT | `/api/v1/achievements/{id}` | 新增可选 `confirmation_token` | 校验令牌后修改 |
| DELETE | `/api/v1/achievements/{id}` | 新增可选 `confirmation_token` | 校验令牌后软删除 |
| GET | `/api/v1/skills` | 返回新增业务 Skill | 前端动态加载 chips |
| PUT | `/api/v1/admin/skills/{id}` | 无需改结构 | 可启停 4 个业务 Skill |

### 9.3 复用接口

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| POST | `/api/v1/confirm/preview` | 成果写操作生成预览与确认令牌 |
| POST | `/api/v1/confirm/verify` | 前端确认前校验令牌 |
| GET | `/api/v1/party/activities`、`/api/v1/party/mine` 等 | 党建查询 Skill 数据源（或直接调用 `PartySkillBoundary`） |
| GET | `/api/v1/recommendations/resources?type=competition` | 语义能力不可用时的兜底 |

---

## 10. 前端需求

1. `chat.js` 的 Skill chips 改为动态加载（或补充 4 个业务 Skill），点击后填入对应触发词。
2. 业务 Skill 触发后，回复中推荐结果支持表格渲染；理由行突出显示。
3. 成果管理 Skill 的确认环节在对话中展示操作预览（操作类型、字段摘要、影响说明），提供“确认/取消”；确认后执行并展示结果。
4. 管理端 Skill 列表自动出现 4 个业务 Skill，可启停；类别显示 `business`。
5. Agent 待确认列表（`/chat/agent/status`）继续展示成果写操作待确认项。

---

## 11. 校验规则汇总

| 规则 | 约束 |
| --- | --- |
| 触发词 | 4 个业务 Skill 触发词不与现有 Skill 冲突；`@agent` 优先级最高 |
| 竞赛推荐 | 只返回 `approved`、未删除、未截止的 `type=competition` 资源 |
| 导师匹配 | `project_description` 必填，建议最少 20 字；只返回在职教师与有效方向 |
| 党建查询 | 只读；名册仅管理员；本人记录仅本人；活动按可见性 |
| 成果写操作 | 仅本人；新增默认 `pending`；删除软删除；必须携带有效确认令牌 |
| 成果模板 | 复用 `achievement_service` 分类、级别、模板、证明文件校验 |
| 向量 | 模型不可用时回退关键词；低于 `SEMANTIC_MIN_SCORE` 不计入 |
| 审计 | 写操作记录 `audit_logs`；所有调用记录 `skill_calls` |

---

## 12. 建议任务拆分

### M1 业务 Skill 框架与种子注册

- T1-1：`SYSTEM_SKILLS` 注册 4 个业务 Skill（`category=business`），补 `SKILL_TRIGGERS` 兜底映射。
- T1-2：新增 4 个业务 Skill Prompt 构建器并注册到 `SKILL_PROMPT_BUILDERS`。
- T1-3：新增业务 Skill 执行层，接入 `ChatService` 的触发词路径与 `@agent` 路径。
- T1-4：`AgentTools` 新增业务工具与工具描述，Agent 提示词加入业务 Skill 说明。
- T1-5：前端动态加载 Skill chips；管理端验证启停。
- 完成定义：4 个 Skill 种子可见，`@触发词` 与 `@agent` 均能进入对应流程（可先 stub），启停生效。

### M2 语义向量服务

- T2-1：激活 `sentence-transformers` 依赖与模型加载（支持配置/离线路径）。
- T2-2：`skill_embeddings` 模型 + Alembic 迁移。
- T2-3：语义服务：embedding、余弦相似度、阈值过滤、关键词加权、热度兜底。
- T2-4：比赛/教师方向/教师资料变更时增量刷新向量。
- T2-5：单元与集成测试。
- 完成定义：向量可持久化、可刷新，模型不可用时回退关键词，测试通过。

### M3 竞赛推荐 + 导师匹配 Skill

- T3-1：`competition_recommend` 执行逻辑与结果格式化。
- T3-2：`mentor_match` 执行逻辑与结果格式化。
- T3-3：新增 2 个业务接口并接入执行层。
- T3-4：Prompt 与自然语言回复模板（含推荐理由）。
- T3-5：测试（画像匹配、截止过滤、理由输出、回退、权限）。
- 完成定义：两个 Skill 在两类触发方式下均可返回带理由的推荐结果。

### M4 党建查询 Skill

- T4-1：执行层接入 `PartySkillBoundary` 5 个只读工具。
- T4-2：Prompt 与意图解析（名册/活动/本人记录/材料检索）。
- T4-3：活动学习材料 RAG 引用（可选范围）；涉敏材料排除校验。
- T4-4：测试（角色隔离、可见性、无写操作）。
- 完成定义：管理员/党员/普通用户查询结果符合权限矩阵，无写路径。

### M5 成果管理 Skill

- T5-1：Agent/执行层新增本人成果查询工具（列表、详情、模板说明）。
- T5-2：新增/修改/删除执行路径，复用模板校验。
- T5-3：写操作接入 `ConfirmationManager` 预览→确认→执行，业务接口校验令牌。
- T5-4：审计日志与 `skill_calls` 记录。
- T5-5：测试（8 类、权限、确认、软删除、pending）。
- 完成定义：AI 可完成本人成果全流程，未确认不落库。

### M6 兼容与验收

- T6-1：SQLite/PostgreSQL 迁移与运行验证。
- T6-2：更新 `README.md` 与 `backend-task-list.md`，记录新 Skill 与依赖。
- T6-3：端到端验收用例与回归测试。
- 完成定义：第 14 章验收要点全部通过。

---

## 13. 待确认事项

以下事项本文档给出推荐默认值，评审时确认：

1. embedding 模型选型与部署：推荐 `BAAI/bge-small-zh-v1.5`；如离线部署，需提前准备模型文件并通过 `EMBEDDING_MODEL_NAME` 指向本地路径。
2. 竞赛结构化字段（报名时间、参赛要求、研究方向等）：本期推荐仍用 `title/content/tags` 做语义匹配，结构化字段由 P1 竞赛信息迭代补充。
3. 成果证明材料：推荐 AI 在证明材料缺失时提示用户先上传或到“我的成果”页补充，不落库；如需 AI 先建“草稿”再补材料，需新增草稿状态。
4. 修改已审核成果后是否重置为 `pending`：推荐重置为 `pending` 以保持档案可信；与现有接口行为不一致，需确认是否本期调整。
5. 导师匹配后是否支持“确认后一键发起交流申请”：推荐本期不做，只返回匹配方向。
6. 向量存储格式：推荐 JSON 数组存 `skill_embeddings.embedding_json`，兼容 SQLite；PostgreSQL 生产环境可后续引入 pgvector。
7. 业务 Skill 是否允许管理员编辑触发词/说明：当前管理端只支持启停，编辑能力归 P2 Skill 配置迭代。

---

## 14. 验收要点

1. 4 个业务 Skill 已注册、可在管理端启停，前端可看到对应触发入口。
2. `@触发词` 与 `@agent` 两种方式均可触发竞赛推荐、导师匹配、党建查询、成果管理。
3. 竞赛推荐返回带理由的结果，过滤已截止比赛，语义失效时回退关键词。
4. 导师匹配基于对话中的项目描述返回教师 + 研究方向 + 理由。
5. 党建查询复用已实现党建模块，权限隔离生效，无写操作。
6. 成果管理覆盖 8 类成果，学生仅能操作本人数据，新增默认 `pending`，删除软删除。
7. 成果写操作必须确认：无令牌不执行，令牌过期/数据不一致被拒绝，审计有记录。
8. `skill_embeddings` 向量可生成、持久化、增量刷新；语义服务有回退路径。
9. 全量测试通过：业务 Skill、语义匹配、确认机制、党建权限、成果管理回归。
