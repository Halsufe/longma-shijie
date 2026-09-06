# 通用平台功能需求文档

> 文档版本：v0.1
> 编写日期：2026-08-06
> 适用模块：通用平台功能（《建设方案对照检查清单》第五部分）
> 输入文档：《建设方案对照检查清单》（`BD/建设方案对照检查清单.md`）、`CampusMate_项目需求分析文档_V2.0_.md`、`龙马视界-系统架构与功能设计.md`
> 关联现状：`backend/app/api/routes/users.py`、`knowledge.py`、`class_knowledge.py`、`assignments.py`、`admin_users.py`、`admin_config.py`、`admin_skills.py`、`admin_stats.py`、`chat.py`、`backend/app/models/`、`frontend/js/views/profile.js`、`knowledge.js`、`courses.js`、`admin.js`、`chat.js`

---

## 1. 文档目的与范围

本文档细化“通用平台功能”需求，覆盖建设方案对照检查清单第五部分 5 个方向的未完成项：

1. 用户中心：个人资料字段扩展、校友转换流程。
2. 知识库：文件夹/目录管理、移动文件、在线预览、班级文件版本管理。
3. 课程与作业：作业附件（上传、预览、下载）。
4. 管理端：用户导入预检、用户列表 CSV 导出、精确 DAU/活跃趋势、Skill 配置编辑、AI 模型/配额/提醒时间配置、党建/竞赛/项目/成果多维统计、任务确认机制接入业务接口与前端。
5. AI 对话：重新生成、附件消息、回答展示规范。

### 1.1 已确认落地方式

| 序号 | 待确认项 | 已确认结论 |
| --- | --- | --- |
| 1 | 文档粒度 | 对齐 `doc/dangjian/dangjian_proposal.md`：现状与改造思路、角色权限、数据模型、接口清单、校验规则、验收要点、任务拆分。 |
| 2 | 跨模块项 | Workflow 调度（作业截止提醒等）本期不展开；党建/竞赛/项目/成果多维统计纳入本文档。 |
| 3 | 作业附件 | 系统内支持上传、预览、下载文件；教师发布作业与学生提交作业均支持多文件；保留原 `attachment_url`/`attachment_name` 作为兼容字段。 |
| 4 | 在线预览 | PDF、图片、Markdown、纯文本、Word、Excel 等常见格式一并实现。 |
| 5 | 知识库文件夹 | 个人/班级知识库均支持单层文件夹，前端提供面包屑导航。 |
| 6 | 精确 DAU | 以 `user_sessions.last_active_at` 当日有活跃会话的用户数为准，展示近 30 天趋势并支持导出。 |
| 7 | 校友转换 | 学生自助申请 + 管理员审核，以及管理员直接转换两种方式均支持。 |
| 8 | AI 对话展示规范 | 写入本文档作为 P2 需求，并给出正反例。 |

### 1.2 本期不覆盖

- Workflow 调度器、作业/比赛/学习计划截止提醒：由后续 Workflow 自动化需求文档承接，本文档仅在管理端配置中预留提醒时间档位字段。
- 创新项目空间业务本身：本文档只定义“项目多维统计”的数据接入边界。
- 党建模块、竞赛/资源共享模块、成果档案模块自身功能。
- OCR 图片解析：聊天附件图片本期保存并展示，不强制 OCR。
- 清单其他部分内容：学生画像、RAG 向量化、成果导出、PostgreSQL 实测、CI/CD 等。

---

## 2. 现状与改造思路

### 2.1 现状

| 子模块 | 已实现能力 | 未实现/待补 | 关键代码位置 |
| --- | --- | --- | --- |
| 用户中心 | 统一登录、强制改密、角色权限、会话管理、通知中心、个人/班级知识库、AI 对话历史；`profile_json` 已有专业/研究方向/技能/简介；`graduation_year` 字段已存在 | 兴趣领域、未来发展规划、年级字段；校友自助转换流程 | `models/user.py`、`api/routes/users.py`、`frontend/js/views/profile.js` |
| 知识库 | 个人/班级上传、下载、重命名、标签、置顶、配额、解析状态、RAG 引用 | 文件夹/目录管理、移动文件、在线预览、版本管理 | `api/routes/knowledge.py`、`class_knowledge.py`、`services/file_service.py`、`models/file.py`、`frontend/js/views/knowledge.js` |
| 课程与作业 | 课程/排课/课表/自然语言查询、作业发布/提交/版本/迟交/未交名单/评分评语/统计；`attachment_url` 为链接字段、`attachment_name` 为文本字段 | 真实文件附件上传、预览、下载 | `api/routes/assignments.py`、`models/school.py`、`services/submission_service.py`、`frontend/js/views/courses.js` |
| 管理端 | 用户 CRUD、CSV 导入（直接导入无预检）、重置密码、启停用、软删除；成果/资源审核；Skill 启停；审计日志；基础统计与存储用量；运行时配置（AI 模型只读） | 导入预检、CSV 导出、精确 DAU/活跃趋势、Skill 配置编辑、AI 模型/配额/提醒时间配置、多维统计、任务确认接入业务接口 | `api/routes/admin_users.py`、`admin_config.py`、`admin_skills.py`、`admin_stats.py`、`frontend/js/views/admin.js` |
| AI 对话 | SSE 流式、停止显示、Skill 调度、RAG 引用、会话历史、业务 Skill 结果卡片 | 重新生成、附件消息、回答展示规范 | `api/routes/chat.py`、`services/chat_service.py`、`frontend/js/views/chat.js`、`frontend/js/ui.js` |

### 2.2 改造思路

- 用户中心：`profile_json` 内新增 JSON 字段，无需改表；新增 `alumni_conversion_requests` 表承载学生申请与审核记录。
- 知识库：新增 `knowledge_folders` 表、`knowledge_files.folder_id` 列；新增统一在线预览服务；新增 `knowledge_file_versions` 表承载班级文件历史版本。
- 课程与作业：新增 `assignment_attachments`、`submission_attachments` 两张附件表；复用 `StorageService` 与知识库预览服务；提交附件按提交版本保留，保证历史版本可回看。
- 管理端：用户导入改为“预检 + 确认”两阶段；新增 CSV 导出；新增基于 `user_sessions` 的 DAU 统计；Skill 接口暴露 `model_config_json`；系统配置改为可持久化存储；新增业务多维统计聚合服务；业务写接口接入任务确认令牌校验。
- AI 对话：新增重新生成接口；新增 `chat_message_attachments` 表支持附件消息；前端引入安全 Markdown 渲染并落实回答展示规范。

---

## 3. 角色与权限

| 角色 | 用户中心 | 知识库 | 课程与作业 | 管理端 | AI 对话 |
| --- | --- | --- | --- | --- | --- |
| admin | 审核校友申请、直接转换校友、维护任意用户资料 | 管理班级知识库（文件夹/移动/预览/版本），管理个人知识库不受限 | 发布/编辑作业、上传作业附件、批改、查看全部提交附件 | 用户导入预检/导出、DAU、Skill 与系统配置、多维统计、任务确认 | 全部会话功能 |
| student | 维护本人资料、发起校友转换申请 | 管理本人个人知识库；查看/下载/预览班级知识库 | 查看已发布作业、提交作业及附件、查看本人提交记录 | 无 | 本人会话 |
| alumni | 维护本人资料（毕业年份） | 同 student | 查看已发布作业、提交作业及附件（沿用现有前端入口） | 无 | 本人会话 |
| teacher | 维护本人资料 | 查看/下载/预览班级知识库 | 查看已发布作业与统计；不提供提交入口（沿用现有前端限制） | 无 | 本人会话 |

---

## 4. 用户中心需求

### 4.1 个人资料字段扩展（P1）

在现有 `profile_json`（专业 `major`、研究方向 `research`、技能 `skills`、简介 `bio`）基础上新增 3 个可选字段：

| 字段 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| `interests` | `list[str]` | 最多 20 项，每项不超过 50 字符 | 兴趣领域标签，如“Python、数据分析、机器学习” |
| `development_plan` | `str` | 不超过 500 字符 | 未来发展规划（升学/就业/科研等） |
| `grade` | `str` | 不超过 20 字符 | 年级，如 `2025` 或 `2025级` |

规则：

1. 字段均为可选；旧数据缺省为空，不强制补填。
2. `interests` 沿用 `skills` 的分隔规则（逗号/顿号分隔转数组），前端输入为逗号分隔文本。
3. `grade` 同时作为画像、竞赛推荐、统计筛选的可选输入；`competition_recommend.py` 已按 `profile_json` 读取 `grade` 等键，新字段直接参与画像组装。
4. 接口继续使用现有 `PUT /api/v1/users/me`，服务端对 `profile` 做白名单校验，未知键忽略或返回错误（建议忽略，保证前端可渐进升级）。
5. 前端个人资料编辑弹窗新增三个输入框；资料展示区新增“兴趣领域/未来发展规划/年级”。

验收点：

- [ ] 学生可在个人中心填写并保存 3 个新字段，刷新后仍显示。
- [ ] 非法输入（超长、非数组标签）被后端拒绝并给出中文提示。
- [ ] 竞赛推荐等 AI 服务可读取新字段作为画像输入。

### 4.2 校友转换流程（P1）

#### 4.2.1 触发方式

方式 A（学生自助申请 + 管理员审核）：

1. 在校学生（`role=student`、`status=active`）在个人中心点击“申请转为校友”，填写毕业年份与可选申请说明。
2. 后端校验后写入 `alumni_conversion_requests`，状态 `pending`，并通知管理员（通知中心新增 `alumni_request` 类型）。
3. 管理员在用户管理“校友申请”列表查看详情，选择通过或驳回；驳回必须填写原因。
4. 通过后用户角色变更为 `alumni`，并收到审核结果通知。

方式 B（管理员直接转换）：

1. 管理员在用户管理对 `student` 用户执行“转为校友”，填写毕业年份。
2. 后端执行与方式 A 通过后相同的转换逻辑，记录审计日志。

#### 4.2.2 校验与转换规则

1. 毕业年份必填，范围 1950-2100，且不得晚于当前年份（按 Asia/Shanghai）。
2. 同一学生同一时刻只能有一条 `pending` 申请，重复提交直接拒绝。
3. `disabled`、`pending_change`（未改密）状态的学生不能发起申请；管理员可直接转换，但转换后账号保持可登录状态并提示改密。
4. 转换后学号不变；`graduation_year` 更新为申请/填写值；个人档案（`profile_json`、`party_json`）、成果、知识库、会话、通知全部保留。
5. 不提供反向自助转换；管理员可用现有用户编辑能力将 `alumni` 改回 `student`。
6. 转换与审核操作写入 `audit_logs`：`alumni_request.create`、`alumni_request.approve`、`alumni_request.reject`、`alumni_convert.direct`。

#### 4.2.3 前端交互

- 学生个人中心：显示当前身份、毕业年份；“申请转为校友”弹窗；若已有 `pending` 申请，显示“审核中”状态。
- 通知中心：展示申请提交、通过、驳回三类通知。
- 管理端用户 Tab：新增“校友申请”入口，支持按状态筛选、查看明细、通过/驳回；用户行操作新增“转为校友”。

验收点：

- [ ] 学生可提交申请，重复提交被拦截。
- [ ] 管理员通过后，用户角色变为校友、毕业年份生效、原资料保留。
- [ ] 管理员可驳回申请并填写原因，学生收到通知。
- [ ] 管理员可直接把学生转为校友，无需先经过申请。
- [ ] 所有转换/审核动作均有审计记录。

---

## 5. 知识库需求

### 5.1 文件夹/目录管理与移动文件（P1）

#### 5.1.1 功能规则

1. 个人知识库（`scope=personal`）与班级知识库（`scope=class`）均支持文件夹；按已确认结论采用**单层目录**，文件夹下不再嵌套文件夹。
2. 文件位于文件夹内或根目录（`folder_id IS NULL`）。
3. 权限：个人知识库文件夹由本人管理；班级知识库文件夹由管理员管理，所有登录用户可查看、预览、下载其中的文件。
4. 文件夹支持新建、重命名、删除；删除仅允许空文件夹，非空时提示“请先移动或删除文件夹内文件”。
5. 文件支持移动到其他文件夹或根目录；移动时校验目标文件夹与文件同 `scope` 且属于同一所有者。
6. 文件夹不占用个人配额，移动文件不影响配额。
7. 上传文件时可选指定文件夹；文件列表支持按文件夹过滤。
8. 前端文件列表区分文件夹行与文件行，顶部展示面包屑导航（如 `全部文件 / 课程资料`），点击面包屑可返回上级。

#### 5.1.2 数据模型

新增 `knowledge_folders` 表：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | int PK | 文件夹 ID |
| `scope` | str | `personal` / `class` |
| `owner_user_id` | int FK users.id | 个人知识库为本人；班级知识库为创建管理员（用于归属校验） |
| `name` | str(100) | 文件夹名 |
| `created_by` | int FK users.id | 创建人 |
| `created_at` / `updated_at` | datetime | 时间 |
| `deleted_at` | datetime nullable | 软删除 |

`knowledge_files` 新增：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `folder_id` | int FK knowledge_folders.id, nullable, index | 所属文件夹；`NULL` 表示根目录 |

唯一性：`(scope, owner_user_id, name)` 内不重名（软删除记录不参与查重）；由于 `deleted_at` 可空，建议在仓储/服务层校验，不依赖数据库唯一索引。

#### 5.1.3 前端交互

- 工具栏新增“新建文件夹”按钮。
- 文件夹行支持“重命名/删除”，文件行支持“移动到”入口。
- 移动弹窗提供目标文件夹下拉框（含“根目录”选项）。
- 切换个人/班级知识库时保留当前文件夹状态（或重置为根目录，推荐重置并回到根目录）。

验收点：

- [ ] 管理员可在班级知识库建文件夹，学生只能查看不能新建/重命名/删除。
- [ ] 个人可把文件移动到文件夹和根目录，列表按文件夹过滤正确。
- [ ] 非空文件夹删除被拒绝，空文件夹删除成功。
- [ ] 同名文件夹在同一作用域内被拒绝。

### 5.2 在线预览（P1）

#### 5.2.1 支持格式与实现方式

| 分类 | 格式 | 实现方式 |
| --- | --- | --- |
| PDF | `.pdf` | 后端 inline 输出原文件，前端 `<iframe>` 加载浏览器原生 PDF 阅读器 |
| 图片 | `.png/.jpg/.jpeg/.gif/.webp/.bmp` | 后端 inline 输出，前端 `<img>` 展示 |
| 文本 | `.txt/.csv/.json/.log/.xml/.yaml/.yml/.toml/.ini` 及代码类（`.py/.js/.java/.c/.cpp/.h/.go/.rs/.rb/.php/.html/.css/.sh` 等） | 服务端读取并转安全 HTML/纯文本，前端 `<pre>` 或代码样式展示 |
| Markdown | `.md/.markdown` | 服务端转 HTML（脱敏后输出），前端渲染 |
| Word | `.docx`（`.doc` 旧格式不转换） | 服务端用 `docx2txt`/HTML 转换提取内容渲染；旧格式提示“请下载查看” |
| Excel | `.xlsx`（`.xls` 旧格式不转换） | 服务端用 `openpyxl` 转 HTML 表格，隐藏公式计算结果之外的敏感内容 |
| PowerPoint | `.pptx`（可选，`ppt` 旧格式不转换） | 服务端用 `python-pptx` 提取文本大纲渲染；如暂不引入依赖，则先提示下载 |

新增依赖建议：`openpyxl`、`python-pptx`（放在 `requirements-optional.txt` 或主依赖，实现时按部署环境确认）。

#### 5.2.2 接口与权限

- `GET /api/v1/knowledge/files/{id}/preview`：个人知识库，仅本人。
- `GET /api/v1/class-knowledge/files/{id}/preview`：班级知识库，所有登录用户。
- 返回结构建议：`{ format, content, preview_url, original_name, size, supported }`；`preview_url` 用于 PDF/图片 inline 输出，`content` 用于文本/Markdown/Word/Excel 渲染。
- 预览不计入 `download_count`；下载仍走现有下载接口。

#### 5.2.3 安全要求

1. 服务端生成的 HTML 必须脱敏：移除 `<script>`、事件属性、`<iframe>`、外部资源引用；Markdown 用白名单渲染。
2. Excel 预览不执行公式、不加载外部链接、只输出单元格值。
3. 预览前做文件头/扩展名校验，禁止通过预览绕过下载权限。
4. 超大文件（建议大于 20MB）不渲染 HTML，提示下载。

验收点：

- [ ] PDF、图片、Markdown、纯文本、DOCX、XLSX 六类文件均可在线预览。
- [ ] 无权限用户访问预览接口返回 404/403。
- [ ] 预览 HTML 不包含脚本标签或事件属性。

### 5.3 班级文件版本管理（P2）

仅班级知识库支持版本管理，管理员可“上传新版本替换当前文件”，旧版本保留可下载。

#### 5.3.1 数据模型

新增 `knowledge_file_versions` 表：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | int PK | 版本记录 ID |
| `file_id` | int FK knowledge_files.id | 所属文件 |
| `version` | int | 版本号（1 起） |
| `stored_name` | str | 旧物理文件 UUID 名 |
| `original_name` | str | 旧文件名 |
| `mime_type` / `size` | str / int | 旧文件元数据 |
| `uploaded_by` | int FK users.id | 上传人 |
| `uploaded_at` | datetime | 上传时间 |

#### 5.3.2 规则

1. `POST /api/v1/class-knowledge/files/{id}/replace`（multipart）替换当前版本：文件 `version + 1`，旧文件信息写入 `knowledge_file_versions`，物理文件保留。
2. 替换后重新解析并替换 `file_chunks`。
3. 历史版本保留上限 20 个；超过后删除最旧版本记录及对应物理文件。
4. 删除文件时同步清理历史版本记录（物理文件由现有后台清理任务处理）。
5. 接口：`GET .../files/{id}/versions`、`GET .../files/{id}/versions/{version}/download`。
6. 前端：班级文件编辑弹窗增加“上传新版本”；文件详情增加“版本历史”，可下载历史版本。

验收点：

- [ ] 管理员替换文件后版本号递增，旧版本仍可下载。
- [ ] 历史版本超过 20 个时最旧版本被清理。
- [ ] 替换后 RAG 引用指向新版本内容。

---

## 6. 课程与作业：作业附件（P1）

### 6.1 需求描述

1. 教师发布/编辑作业时可上传多个附件文件（作业材料），学生可在线预览、下载。
2. 学生提交作业时可上传多个附件文件，提交历史版本保留各自附件。
3. 保留现有 `attachment_url`（外部链接）与 `attachment_name` 文本字段作为兼容入口；新增真实文件附件能力。
4. 所有附件支持上传、预览、下载。

### 6.2 数据模型

新增 `assignment_attachments`：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | int PK | 附件 ID |
| `assignment_id` | int FK assignments.id, index | 所属作业 |
| `original_name` / `stored_name` | str | 文件名与 UUID 存储名 |
| `mime_type` / `size` | str / int | 元数据 |
| `uploaded_by` | int FK users.id | 上传人 |
| `created_at` / `deleted_at` | datetime | 时间/软删除 |

新增 `submission_attachments`：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | int PK | 附件 ID |
| `submission_id` | int FK submissions.id, index | 所属提交 |
| `version` | int | 对应 `submission_versions.version`，历史版本各自保留附件 |
| `original_name` / `stored_name` | str | 文件名与 UUID 存储名 |
| `mime_type` / `size` | str / int | 元数据 |
| `uploaded_by` | int FK users.id | 上传人 |
| `created_at` | datetime | 上传时间 |

存储复用 `StorageService.save_file`，建议新增 `scope="assignment"`、`scope="submission"`（目录按 `storage/{scope}/{user_id}/` 隔离）。

### 6.3 接口

| 接口 | 权限 | 说明 |
| --- | --- | --- |
| `POST /api/v1/assignments/{id}/attachments`（multipart） | admin | 上传作业附件，可批量 |
| `DELETE /api/v1/assignments/attachments/{attachment_id}` | admin | 删除作业附件 |
| `GET /api/v1/assignments/{id}/attachments` | 登录用户（published 或 admin） | 附件列表 |
| `GET /api/v1/assignments/attachments/{id}/download` | 登录用户 | 下载作业附件 |
| `GET /api/v1/assignments/attachments/{id}/preview` | 登录用户 | 预览作业附件（复用在线预览服务） |
| `POST /api/v1/assignments/{id}/submit`（multipart：`content` + 多文件） | student/alumni | 提交作业并保存附件；保留原 JSON 接口兼容 |
| `GET /api/v1/submissions/{id}/attachments?version=` | 本人/admin | 提交附件列表，可按版本过滤 |
| `GET /api/v1/submissions/attachments/{id}/download` | 本人/admin | 下载提交附件 |
| `GET /api/v1/submissions/attachments/{id}/preview` | 本人/admin | 预览提交附件 |

### 6.4 校验规则

1. 附件类型：`.pdf/.doc/.docx/.xls/.xlsx/.ppt/.pptx/.txt/.md/.csv`、图片（`.png/.jpg/.jpeg/.gif/.webp`）、压缩包（`.zip/.rar`）。
2. 单文件不超过 50MB；单个作业附件总大小不超过 200MB；单次提交附件总数不超过 10 个。
3. 提交作业时附件随提交事务一起落库；更新提交生成新 `submission_versions`，旧版本附件保留。
4. 作业撤销/删除后附件不可再下载（走作业权限校验）。
5. 上传文件名做规范化处理，物理文件名使用 UUID，杜绝路径穿越。

### 6.5 前端交互

- 作业发布/编辑弹窗：附件上传区（多选文件、显示待传列表、可移除），附件链接字段保留。
- 作业详情弹窗：展示作业附件列表，每项含预览/下载按钮。
- 提交弹窗：附件上传区 + 提交内容；提交成功后展示已提交附件。
- 管理端批改视图：展示学生提交附件，支持预览/下载。
- 版本历史弹窗：每个版本展示对应附件。

验收点：

- [ ] 教师发布作业可上传多个附件，学生可预览和下载。
- [ ] 学生提交可携带多个附件，再次提交后旧版本附件仍可查看。
- [ ] 超限文件/类型被拒绝并给出提示。
- [ ] 无权限用户无法下载他人提交附件。

---

## 7. 管理端需求

### 7.1 用户导入预检（P1）

现状：`POST /api/v1/admin/users/import` 直接导入，无确认步骤。

改造为两阶段：

#### 7.1.1 阶段一：预检

`POST /api/v1/admin/users/import/preview`（multipart CSV）：

1. 解析 CSV（UTF-8 BOM/GBK 兼容，沿用现有解码逻辑），必须包含“学号”列。
2. 逐行分类：

| 分类 | 判定 | 预检结果 |
| --- | --- | --- |
| 新增 | 学号不存在 | `action=create` |
| 更新 | 学号存在且未软删除 | `action=update`，展示新值变化 |
| 恢复+更新 | 学号存在且已软删除 | `action=restore` |
| 跳过 | 文件内重复学号（保留首行） | `action=skip` + 原因 |
| 错误 | 学号/姓名为空、角色非法、学号格式非法 | `action=error` + 错误明细 |

3. 返回 `{ total_rows, summary: {create, update, restore, skip, error}, items: [{row_no, student_no, name, role, action, error}], preview_token }`。
4. `preview_token` 为短时令牌（建议 JWT，有效期 10 分钟），绑定“文件内容哈希 + 行摘要”，防止确认时文件被篡改。
5. 为控制规模，单次最多预检 1000 行；超出直接拒绝。

#### 7.1.2 阶段二：确认执行

`POST /api/v1/admin/users/import/confirm`（multipart CSV + `preview_token`）：

1. 服务端重新解析文件，校验内容哈希与 `preview_token` 一致。
2. 在单个事务内执行全部 `create/update/restore` 行；`skip/error` 行不导入。
3. 返回与现有接口一致的汇总消息；`error` 行明细写入返回信息（最多展示 20 条）。
4. 保留旧 `POST /users/import` 接口用于兼容，前端切换为预检流程。

#### 7.1.3 前端

- “导入 CSV”点击后先上传并展示预检表格：学号/姓名/角色/预检结果/原因，顶部汇总新增、更新、恢复、跳过、错误数量。
- 错误行高亮；用户可返回修改 CSV 或点击“确认导入”执行。
- 确认前必须有二次确认弹窗。

验收点：

- [ ] 导入前可看到逐行分类和错误明细。
- [ ] 确认导入后错误行不落库，其余行事务性写入。
- [ ] 文件内容在预检后被篡改时，确认阶段被拒绝。

### 7.2 用户列表 CSV 导出（P1）

`GET /api/v1/admin/users/export?q=&role=&status=`：

1. 导出与用户列表相同的筛选条件下全部用户（不受分页限制）。
2. 输出 UTF-8 BOM CSV，列：学号、姓名、角色、状态、年级、毕业年份、最近活跃时间、创建时间。
3. 下载文件名：`users_YYYYMMDD_HHMMSS.csv`。
4. 操作记录审计日志 `admin.users.export`。
5. 前端用户管理工具栏新增“导出 CSV”按钮。

验收点：

- [ ] 按筛选条件导出的行数与列表一致。
- [ ] Excel 打开 CSV 不乱码。

### 7.3 精确 DAU/活跃趋势（P1）

口径：某自然日（Asia/Shanghai）内 `user_sessions` 中 `last_active_at` 在该日、未被撤销的会话对应的去重用户数。

1. `GET /api/v1/admin/stats/activity?days=30` 返回近 N 天（默认 30，上限 90）逐日 DAU、周期平均、峰值日，以及对照的启用账号数（兼容旧前端“活跃用户”卡片）。
2. `last_active_at` 由登录与 refresh 流程维护（`SessionRepository.touch_active` 已更新），无需新增埋点。
3. 建议为 `user_sessions` 增加 `(user_id, last_active_at)` 复合索引，避免统计全表扫描。
4. 前端：概览页“活跃用户”卡片改为真实今日 DAU；新增“活跃趋势”面板（30 天柱状图，使用轻量图表或不依赖外部库的 CSS 柱状图）；提供 CSV 导出按钮。
5. 导出接口：`GET /api/v1/admin/stats/activity/export?days=30`。

验收点：

- [ ] 今日登录过但未做任何操作的用户会计入 DAU。
- [ ] 趋势图按自然日聚合，无重复计数。
- [ ] 导出 CSV 列与接口一致。

### 7.4 Skill 配置编辑（P2）

现状：后端 `PUT /api/v1/admin/skills/{id}` 已支持 `display_name/triggers/description/is_enabled`，但未暴露 `model_config_json`；前端只有启停按钮。

需求：

1. `SkillInfo`/`SkillUpdate` 新增 `model_config: dict`（映射到现有 `model_config_json` 列），白名单字段建议：`model`、`temperature`、`max_tokens`、`top_p`。
2. 管理端 Skill Tab 每行新增“编辑”按钮，弹窗编辑展示名、说明、触发词（逗号分隔）、模型配置 JSON、启停。
3. 校验：展示名必填；触发词非空数组、每项以 `@` 开头且不超过 30 字符、不重复；`model_config` 必须是 JSON 对象且键在白名单内。
4. 保存后 SkillDispatcher 需要读取最新配置；若调度器在启动时缓存了触发词，需在保存时热刷新或重启生效，实现时确认。
5. 管理列表 `include_business=true` 时也展示业务 Skill，允许编辑展示名/说明/触发词/模型配置（不允许删除）。

验收点：

- [ ] 管理员可修改触发词并在新对话中按新触发词命中。
- [ ] 非法触发词/非白名单模型配置被拒绝。
- [ ] 系统内置 Skill 不可删除。

### 7.5 AI 模型/配额/提醒时间配置（P2）

现状：`GET/PUT /api/v1/admin/config` 支持班级名称、默认配额、登录限制；AI 模型只读；修改仅内存生效。

需求：

1. 配置项扩展：`ai_model`、`ai_base_url`（可选编辑，API Key 只显示“已配置/未配置”不回显）、`default_quota_mb`、`login_max_attempts`、`login_window_minutes`、`assignment_reminder_hours`（如 `[24, 2]`，仅作为 Workflow 配置字段预留，本期不实现调度）。
2. 新增 `runtime_configs` 表（key/value JSON）持久化运行时配置；服务启动时以数据库配置覆盖默认 `settings`，保证重启不丢失。
3. 前端系统配置 Tab 由只读改为可编辑表单，保存后即时生效并提示持久化状态。
4. 所有配置修改记录审计日志 `admin.config.update`。

验收点：

- [ ] 管理员可修改 AI 模型与默认配额，重启服务后配置仍生效。
- [ ] API Key 值不回显。
- [ ] 提醒时间档位可保存，但本期不触发任何定时任务。

### 7.6 党建/竞赛/项目/成果多维统计（P0/P1）

统一业务统计入口：`GET /api/v1/admin/stats/business?year=&class_name=&grade=&category=`。

维度：时间（年/月）、班级、年级、状态（审核/发布）、类别。

数据来源：

| 模块 | 统计指标 | 数据源 |
| --- | --- | --- |
| 党建 | 党员/预备党员/积极分子人数、活动数、报名数、签到数、参与率、发展情况 | `party_*` 表与 `party_stats_service.py` 聚合能力 |
| 竞赛 | 比赛总数、按类别/研究方向/状态（草稿/已发布/审核中）、已截止/未截止、收藏数 | `resources`（`type=competition`） |
| 项目 | 项目数、按状态/研究方向/团队规模 | 依赖创新项目空间；模块未实现时返回 `not_available` 标记与空数据 |
| 成果 | 成果总数、按 8 类分类、审核状态、公开比例、按年份/班级/年级 | `achievements` 表与现有分类统计接口 |

实现要求：

1. 新增 `business_stats_service.py` 聚合服务，避免前端多次请求与 N+1 查询。
2. 统计结果统一结构：`{ module, dimensions, summary, items }`；项目模块未上线时 summary 置空并带 `not_available`。
3. 前端管理端新增“业务统计”Tab：筛选器（年份/班级/年级）+ 指标卡 + 明细表格；项目区域显示“模块未上线”占位。
4. 全部统计接口仅管理员可访问，并记录审计日志。

验收点：

- [ ] 党建、竞赛、成果三项在现有数据下可正确聚合。
- [ ] 项目统计在模块未实现时不会报错，界面明确提示未上线。
- [ ] 按班级/年级/年份筛选后结果正确。

### 7.7 任务确认机制接入业务接口与前端（P1）

现状：`backend/app/core/confirmation.py` 已实现预览→确认两阶段（JWT，5 分钟有效），Agent 写操作已有确认；成果/资源等普通业务接口尚未校验确认令牌。

需求：

1. 通用平台提供统一确认令牌校验依赖（`Depends(require_confirmation_token)` 或等价中间件），业务写接口可选接收 `confirmation_token`：
   - 令牌缺失：保持现状直接执行（兼容旧客户端）。
   - 令牌存在：校验令牌有效、操作人一致、数据哈希一致；任一不满足则拒绝执行并提示重新预览。
2. 本期接入范围：成果新增/修改/删除、资源新增/修改/删除接口（具体业务设计仍在对应模块文档，本文档只定义通用接入规范）。
3. 前端为高风险操作（删除、覆盖、驳回等）提供统一确认组件：调用 `POST /api/v1/confirm/preview` 展示确认卡片，确认后携带令牌调用业务接口。
4. 确认成功后写审计日志；失败同样记录。

验收点：

- [ ] 携带过期/伪造/数据不一致令牌的业务请求被拒绝。
- [ ] 未携带令牌的旧流程仍可用。
- [ ] 前端高风险操作展示确认卡片后方可执行。

---

## 8. AI 对话需求

### 8.1 重新生成（P2）

1. `POST /api/v1/chat/sessions/{session_id}/messages/{message_id}/regenerate`（SSE）：仅允许对当前会话最后一条 `assistant` 消息执行，重新以上文为上下文生成回复。
2. 生成结果替换原消息的 `content/citations/token_usage/duration_ms`；原回复不保留（或由前端展示“已重新生成”）。
3. 并发控制：同一会话同时只允许一个重新生成任务；生成期间用户发送新消息则取消或拒绝（推荐取消并提示）。
4. 生成沿用现有 ChatService 的 Skill/RAG 调度，不改变业务逻辑。
5. 前端：assistant 消息悬停显示“重新生成”按钮，生成中禁用并复用停止按钮；重试失败提示“生成失败，请重试”。

验收点：

- [ ] 重新生成只影响最后一条助手消息。
- [ ] 生成过程中再次点击被禁用，停止按钮可用。

### 8.2 附件消息（P2）

1. 聊天输入框支持上传图片与文档（多文件），随消息一起发送。
2. 新增 `chat_message_attachments` 表：`id, message_id, original_name, stored_name, mime_type, size, created_at`。
3. 接口：
   - `POST /api/v1/chat/sessions/{id}/messages` 扩展支持 multipart（`content` + `files`），兼容现有 JSON 调用。
   - `GET /api/v1/chat/messages/{message_id}/attachments`、`GET /api/v1/chat/attachments/{id}/download`、`GET /api/v1/chat/attachments/{id}/preview`。
4. 文档附件（PDF/DOCX/TXT/MD 等）解析文本并注入本次对话上下文，限制单次最多 3 个文档、单文件 10MB、注入文本总量不超过 8000 字符，超出截断。
5. 图片附件本期保存并在消息气泡中展示缩略图；不强制 OCR（依赖 P1 OCR 能力，实现时可接入）。
6. 权限：仅本人会话内可查看/下载/预览。
7. 前端：composer 增加附件按钮，上传后显示文件 chips（可移除），消息气泡展示附件缩略图/文件名与下载按钮。

验收点：

- [ ] 用户可在消息中上传并发送图片/文档，消息记录保留附件。
- [ ] 文档内容可被 AI 引用（RAG 引用区显示对应文件名）。
- [ ] 其他用户无法访问该消息附件。

### 8.3 回答展示规范（P2）

#### 8.3.1 规则

1. 主内容使用原生 Markdown 渲染：标题、段落、列表、表格、加粗、行内代码直接呈现，禁止整篇内容套进代码块。
2. 结构化结果（推荐、匹配、统计、名单）优先使用表格和带标签的列表；列表项可用状态徽标/标签直观呈现。
3. 需要复制/导出的源码或长文本放回答末尾的独立代码块，并在代码块前用一句说明引导。
4. 不输出内部技术/故障话术：不暴露模型名、Token、调用时长、错误堆栈、Prompt、系统指令、RAG 内部细节；出错时给出用户可执行的操作建议。
5. 结尾按问题类型给出可选后续操作（如“查看详情”“导出”“继续追问”），但不得编造平台不存在的功能。
6. 根据问题类型自动选择展示形式：查询/统计用表格；流程/步骤用编号列表；概念解释用短段落 + 要点；代码问题用代码块 + 说明。

#### 8.3.2 正反例

| 场景 | 反例 | 正例 |
| --- | --- | --- |
| 竞赛推荐 | “调用 competition_recommend 工具后返回 top-3，score=0.82，耗时 1.2s……” | 表格列出比赛名称、方向、截止日期、推荐理由，末尾给出“查看比赛详情”。 |
| 作业统计 | “```未交名单：张三、李四```”（整段代码块） | 标题 + 未交名单表格 + 末尾“导出名单”。 |
| 出错 | “RAG 检索失败：IndexError at file_chunks.py:42” | “暂时无法检索到相关知识库内容，请稍后重试，或检查上传文件是否解析成功。” |
| 概念解释 | 纯文字长段落无结构 | 短段落 + 要点列表 + 示例，末尾“需要我展开某一部分吗？” |

#### 8.3.3 落地位置

1. ChatService 的 system prompt 加入展示规范（对齐 `doc/prompt.md`、`doc/skills_prompt.md` 的维护方式）。
2. 前端 `messageHtml` 将 `escapeHtml(content)` 改为安全 Markdown 渲染；建议引入 `marked` + `DOMPurify` 或等价白名单渲染库，样式约束在现有 `styles.css` 内。
3. 表格在小屏设备上允许横向滚动，禁止溢出页面。

验收点：

- [ ] 向 AI 提问“列出近期竞赛/未交名单”时，回复使用表格且无整篇代码块。
- [ ] 触发错误场景时不出现堆栈、模型名或调用耗时。
- [ ] 回答末尾出现可选后续操作，且操作入口真实可用。

---

## 9. 数据模型变更汇总

| 表/字段 | 变更 | 说明 |
| --- | --- | --- |
| `users.profile_json` | 扩展 JSON 键 | 新增 `interests`、`development_plan`、`grade` |
| `alumni_conversion_requests` | 新增表 | 校友转换申请与审核 |
| `knowledge_folders` | 新增表 | 个人/班级知识库文件夹 |
| `knowledge_files.folder_id` | 新增列 | 所属文件夹，`NULL` 为根目录 |
| `knowledge_file_versions` | 新增表 | 班级文件历史版本 |
| `assignment_attachments` | 新增表 | 作业附件 |
| `submission_attachments` | 新增表 | 提交附件（按提交版本保留） |
| `runtime_configs` | 新增表 | 运行时系统配置持久化 |
| `chat_message_attachments` | 新增表 | 聊天消息附件 |
| `skills.model_config_json` | 已存在，暴露到 API | Skill 模型配置编辑 |
| `user_sessions` | 建议新增索引 | `(user_id, last_active_at)` 支撑 DAU |

---

## 10. 接口清单

### 10.1 用户中心

| 方法 | 路径 | 权限 | 说明 |
| --- | --- | --- | --- |
| PUT | `/api/v1/users/me` | 本人 | 扩展 `profile` 字段校验 |
| POST | `/api/v1/users/me/alumni-request` | student | 发起校友转换申请 |
| GET | `/api/v1/users/me/alumni-request` | 本人 | 查询本人申请状态 |
| GET | `/api/v1/admin/users/alumni-requests` | admin | 申请列表（按状态筛选） |
| POST | `/api/v1/admin/users/alumni-requests/{id}/approve` | admin | 通过申请 |
| POST | `/api/v1/admin/users/alumni-requests/{id}/reject` | admin | 驳回申请（必填原因） |
| POST | `/api/v1/admin/users/{id}/convert-alumni` | admin | 管理员直接转换 |

### 10.2 知识库

| 方法 | 路径 | 权限 | 说明 |
| --- | --- | --- | --- |
| POST/GET | `/api/v1/knowledge/folders` | 本人/admin | 个人知识库文件夹 |
| PUT/DELETE | `/api/v1/knowledge/folders/{id}` | 本人/admin | 重命名/删除（仅空） |
| GET | `/api/v1/knowledge/files?folder_id=` | 本人 | 按文件夹过滤个人文件 |
| PUT | `/api/v1/knowledge/files/{id}/move` | 本人 | 移动个人文件 |
| POST | `/api/v1/knowledge/upload` | 本人 | 上传并指定 `folder_id` |
| GET | `/api/v1/knowledge/files/{id}/preview` | 本人 | 个人文件预览 |
| POST/GET | `/api/v1/class-knowledge/folders` | admin / 登录用户 | 班级知识库文件夹 |
| PUT/DELETE | `/api/v1/class-knowledge/folders/{id}` | admin | 重命名/删除（仅空） |
| GET | `/api/v1/class-knowledge/files?folder_id=` | 登录用户 | 按文件夹过滤班级文件 |
| PUT | `/api/v1/class-knowledge/files/{id}/move` | admin | 移动班级文件 |
| POST | `/api/v1/class-knowledge/upload` | admin | 上传并指定 `folder_id` |
| GET | `/api/v1/class-knowledge/files/{id}/preview` | 登录用户 | 班级文件预览 |
| POST | `/api/v1/class-knowledge/files/{id}/replace` | admin | 上传新版本（P2） |
| GET | `/api/v1/class-knowledge/files/{id}/versions` | 登录用户 | 版本列表（P2） |
| GET | `/api/v1/class-knowledge/files/{id}/versions/{version}/download` | 登录用户 | 下载历史版本（P2） |

### 10.3 课程与作业

| 方法 | 路径 | 权限 | 说明 |
| --- | --- | --- | --- |
| POST | `/api/v1/assignments/{id}/attachments` | admin | 上传作业附件 |
| DELETE | `/api/v1/assignments/attachments/{id}` | admin | 删除作业附件 |
| GET | `/api/v1/assignments/{id}/attachments` | 登录用户 | 附件列表 |
| GET | `/api/v1/assignments/attachments/{id}/download` | 登录用户 | 下载附件 |
| GET | `/api/v1/assignments/attachments/{id}/preview` | 登录用户 | 预览附件 |
| POST | `/api/v1/assignments/{id}/submit` | student/alumni | multipart 提交（含附件） |
| GET | `/api/v1/submissions/{id}/attachments?version=` | 本人/admin | 提交附件列表 |
| GET | `/api/v1/submissions/attachments/{id}/download` | 本人/admin | 下载提交附件 |
| GET | `/api/v1/submissions/attachments/{id}/preview` | 本人/admin | 预览提交附件 |

### 10.4 管理端

| 方法 | 路径 | 权限 | 说明 |
| --- | --- | --- | --- |
| POST | `/api/v1/admin/users/import/preview` | admin | 导入预检 |
| POST | `/api/v1/admin/users/import/confirm` | admin | 确认导入 |
| GET | `/api/v1/admin/users/export` | admin | 用户 CSV 导出 |
| GET | `/api/v1/admin/stats/activity` | admin | DAU/活跃趋势 |
| GET | `/api/v1/admin/stats/activity/export` | admin | 活跃趋势 CSV 导出 |
| PUT | `/api/v1/admin/skills/{id}` | admin | Skill 配置编辑（含 `model_config`） |
| GET/PUT | `/api/v1/admin/config` | admin | 系统配置（AI 模型/配额/提醒档位等，持久化） |
| GET | `/api/v1/admin/stats/business` | admin | 党建/竞赛/项目/成果多维统计 |
| POST | `/api/v1/confirm/preview` | 登录用户 | 任务确认预览（现有） |
| POST | `/api/v1/confirm/confirm` | 登录用户 | 任务确认执行（现有） |

### 10.5 AI 对话

| 方法 | 路径 | 权限 | 说明 |
| --- | --- | --- | --- |
| POST | `/api/v1/chat/sessions/{id}/messages/{message_id}/regenerate` | 本人 | 重新生成（SSE） |
| POST | `/api/v1/chat/sessions/{id}/messages` | 本人 | 支持 multipart 附件消息 |
| GET | `/api/v1/chat/messages/{id}/attachments` | 本人 | 消息附件列表 |
| GET | `/api/v1/chat/attachments/{id}/download` | 本人 | 下载消息附件 |
| GET | `/api/v1/chat/attachments/{id}/preview` | 本人 | 预览消息附件 |

---

## 11. 校验规则与安全

1. 上传：所有文件上传复用扩展名白名单 + 文件头/大小校验；物理文件名统一 UUID；禁止路径穿越。
2. 大小限制：知识库单文件 50MB（沿用现有提示）；作业附件单文件 50MB、单作业/单次提交总量 200MB；聊天附件单文件 10MB。
3. 预览：服务端 HTML 必须脱敏；PDF/图片用 inline 输出；Excel 不执行公式；预览不改变 `download_count`。
4. 权限：所有新增接口复用 `api/deps.py` 的登录/角色依赖；班级知识库只读与管理员写权限不放松。
5. 时区：DAU 按 Asia/Shanghai 自然日聚合；数据库时间统一 UTC，聚合时显式转换。
6. 配置：`runtime_configs` 中不存储 API Key；API Key 只回显“已配置/未配置”。
7. 任务确认：令牌 5 分钟有效，绑定用户与数据哈希；过期/篡改一律拒绝。
8. 版本：班级文件历史版本上限 20，防止存储无限增长。
9. 审计：用户导入、导出、校友转换、配置修改、Skill 编辑、多维统计访问均写入 `audit_logs`。

---

## 12. 验收要点

- [ ] 个人资料新增字段可填写、保存、展示，并被 AI 画像读取。
- [ ] 校友转换两种方式可用，数据保留，审计完整。
- [ ] 个人/班级知识库支持文件夹、面包屑导航、移动文件。
- [ ] PDF/图片/Markdown/纯文本/Word/Excel 可在线预览，预览内容安全。
- [ ] 班级文件可上传新版本并下载历史版本。
- [ ] 作业附件发布、提交、预览、下载全链路可用，提交历史保留附件。
- [ ] 用户导入有预检确认流程，错误行不落库。
- [ ] 用户列表可导出 CSV。
- [ ] DAU 与 30 天活跃趋势准确，可导出。
- [ ] Skill 与系统配置可编辑并持久化。
- [ ] 党建/竞赛/成果多维统计正确，项目统计未上线时有明确提示。
- [ ] 业务高风险操作有任务确认。
- [ ] AI 可重新生成回复，消息可带附件。
- [ ] AI 回答按展示规范输出，无内部技术话术，无整篇代码块。

---

## 13. 任务拆分与迭代顺序

| 里程碑 | 内容 | 优先级 | 依赖 |
| --- | --- | --- | --- |
| M1 | 个人资料字段扩展 | P1 | 无 |
| M2 | 校友转换（申请+审核+直接转换） | P1 | 通知服务、审计 |
| M3 | 知识库文件夹与移动 | P1 | M3 数据模型 |
| M4 | 在线预览 | P1 | M3（预览入口在知识库页面） |
| M5 | 班级文件版本管理 | P2 | M3 |
| M6 | 作业附件 | P1 | 预览服务复用 |
| M7 | 用户导入预检 | P1 | 无 |
| M8 | 用户列表 CSV 导出 | P1 | 无 |
| M9 | 精确 DAU/活跃趋势 | P1 | 无 |
| M10 | Skill 配置编辑 + AI/配额/提醒时间配置 | P2 | `runtime_configs` |
| M11 | 党建/竞赛/项目/成果多维统计 | P0/P1 | 党建/成果/资源现有接口；项目预留 |
| M12 | 任务确认接入业务接口与前端 | P1 | 现有 confirmation 服务 |
| M13 | AI 重新生成 | P2 | ChatService |
| M14 | 聊天附件消息 | P2 | 解析器、存储 |
| M15 | 回答展示规范 | P2 | 前端 Markdown 渲染 |

建议执行顺序：

1. P1 第一批：M1、M2、M3、M4、M6、M7、M8、M9。
2. P1/P0 第二批：M11、M12。
3. P2 第三批：M5、M10、M13、M14、M15。

---

## 14. 依赖边界与待确认事项

1. 项目多维统计依赖创新项目空间：模块未实现前，接口与前端以“未上线”占位呈现，不虚构数据。
2. 提醒时间档位配置仅预留字段，定时调度由后续 Workflow 文档承接。
3. 在线预览的旧格式（`.doc/.xls/.ppt`）默认不转换，仅提示下载；如需支持，依赖部署环境安装 LibreOffice 或等价转换器。
4. 聊天附件图片的 OCR 依赖清单第二部分的 OCR 能力；本期不阻塞附件消息功能。
5. 用户导入预检本期仅支持 CSV；`.xlsx` 支持可作为后续扩展。
6. `runtime_configs` 与现有 `settings`（lru_cache）的覆盖优先级实现时确认：数据库配置 > 环境变量 > 默认值。
7. 任务确认接入的具体业务接口清单（成果/资源的哪些操作必须确认）以对应模块文档为准，本文档只定义通用接入规范。
