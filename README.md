# 龙马·视界 平台文档

> CampusMate 创新创业管理平台（后端 + 前端一体）
> 版本：V3.1（2026-08-17）— 学术导师双选、党建数字化、AI 业务 Skills 与通用平台增强
> 覆盖模块：认证/用户、AI 对话、知识库、成果档案、资源社区、学术导师双选、教师方向与学习计划、课程作业、通知、管理后台、个性化推荐、任务确认、党建、AI Agent 与业务 Skills

## 学术导师双选

系统提供按批次隔离的学术导师双选流程。管理员维护名单和阶段，学生提交志愿，导师查看获授权档案并接收/拒绝，系统按学生志愿顺序生成唯一匹配。管理员不能手工调整匹配归属。

| 角色 | 在双选中的操作 |
|------|----------------|
| 管理员 | 创建批次、上传学生 Excel、勾选参与导师、开放或推进阶段、查看汇总、延长阶段、撤回已发布结果并重开 |
| 学生 | 在个人设置完善双选档案，查看导师简介和研究方向，填写主选或补录志愿，查看发布后的匹配结果 |
| 导师 | 在“研究方向与学习计划”维护研究方向，查看选择自己的候选学生档案，接收/拒绝并最终提交名单，查看最终匹配学生 |

### 管理员操作流程

1. 在“导师双选”创建批次，依次配置学生填报、导师选择、主选发布及可选的补录时间。
2. 在草稿阶段上传学生名单。支持 `.xlsx`、`.xls`、`.csv`，表头必须为 `学号、姓名、班级`，也支持 `student_no、name、class_name`。系统会先预检，再确认导入。
3. 勾选至少 3 名参与导师并保存，然后点击“开放主选”。批次开放后，学生名单和导师名单会锁定。
4. 学生完成志愿提交后，管理员推进到“导师选择”；导师最终提交名单后，再依次推进“计算主选结果”和“发布主选结果”。
5. 如启用补录，继续按“补录填报 → 补录导师选择 → 计算 → 发布”推进。补录有未匹配学生时不能发布，需延长补录阶段。

### 学生与导师操作要点

- 学生正式提交主选志愿前，必须填写个人简介、至少 3 门课程成绩、个人陈述，以及 3 至 4 位不同导师的连续志愿顺序和逐导师申请理由。补录至少选择 1 位导师。
- 导师研究方向在“导师双选 → 研究方向与学习计划 → 研究方向”中维护。学生可在志愿页查看参与导师的简介、方向说明和剩余名额。
- 导师仅可查看选择自己的学生；候选档案包括个人资料、成绩、个人陈述、对该导师的理由和已审核成果，但不包含志愿顺序、其他导师或其他理由。结果发布后，未匹配候选档案自动收回。
- 导师点击“接收”或“拒绝”会保存草稿；“最终提交”后该轮决定锁定。每位导师整个批次累计最多接收 4 人。

### 阶段与自动任务

`draft → student_apply → mentor_select → main_pending → main_published → supplement_student_apply → supplement_mentor_select → supplement_pending / supplement_blocked → supplement_published → completed`

管理员可以在页面手动推进。需要按时间自动推进时，Web 进程不运行阶段调度；生产环境应另启独立 Worker：

```powershell
.\.venv\python.exe -m backend.app.workers.mentor_selection_worker
```

使用 `--once` 可执行一次到期任务扫描后退出。学生名单导入及数据导出支持 CSV、XLSX、XLS，分别由 `openpyxl`、`xlrd`、`xlwt` 处理。部署前先执行 `alembic upgrade head` 创建双选领域表；测试和迁移演练必须使用独立 SQLite 数据库，不要操作运行中的业务库。

## 目录

> **云端部署（GitHub Pages + Render + Supabase）**：请先阅读 [初学者部署指南](DEPLOY_BEGINNER.md)。指南包含从创建 Supabase 项目、推送 GitHub 仓库到配置 Render 和 GitHub Pages 的完整步骤。

- [快速开始](#快速开始)
- [环境配置](#环境配置)
- [前端使用](#前端使用)
- [学术导师双选](#学术导师双选)
- [核心模块详解](#核心模块详解)
- [AI Agent 智能助手](#ai-agent-智能助手)
- [API 参考速查表](#api-参考速查表)
- [数据模型](#数据模型)
- [数据库迁移](#数据库迁移)
- [部署指南](#部署指南)
- [开发规范](#开发规范)
- [测试](#测试)
- [项目结构](#项目结构)
- [技术栈](#技术栈)
- [常见问题](#常见问题)
- [配置说明](#配置说明)
- [版本信息](#版本信息)

---

## 快速开始

### 环境要求

- Python 3.11+（由 `.python-version` 锁定）
- 虚拟环境 `.venv`（依赖见 `requirements.txt`、`requirements-dev.txt`、`requirements-optional.txt`）
- 首次启动需配置根目录 `.env`（可直接复制 `.env.example` 并填入 `SECRET_KEY`、`AI_API_KEY`、`MCP_SERVICE_TOKEN`）

### 启动

```bash
# 1. 进入项目目录
cd LM_SJ

# 2. 启动开发服务（后端 + 前端一体，前端无需单独构建）
.\.venv\python.exe run.py

# 3. 打开浏览器访问
# 前端应用:   http://127.0.0.1:8000/          ← 前端 SPA 入口
# API 文档:   http://127.0.0.1:8000/docs      ← Swagger UI
# 健康检查:   http://127.0.0.1:8000/health
```

### 测试账号

| 账号 | 密码 | 角色 | 说明 |
|------|------|------|------|
| `admin001` | `admin123` | 管理员 | 全部权限：用户/审计/党建/ Skill/配置 |
| `2025001` | 需管理员重置 | 学生 | 可登录，密码需管理员重置 |
| `2025003` | 需管理员重置 | 学生 | 待改密状态 |

> 学生密码可使用管理后台「用户管理」重置，或调用 `PUT /api/v1/admin/users/{id}/reset-password`。

## 环境配置

### 配置文件

在项目根目录创建 `.env` 文件（与 `run.py` 同级）覆盖默认配置，完整示例见 `.env.example`。配置入口：[backend/app/core/config.py](backend/app/core/config.py)。

```env
# 应用
APP_NAME=龙马视界
ENV=dev

# JWT 签名密钥（用 python -c "import secrets; print(secrets.token_hex(32))" 生成）
SECRET_KEY=<用 secrets.token_hex(32) 生成>
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7

# 数据库（开发用 SQLite，存放在 database/ 目录；生产用 PostgreSQL）
DB_URL=sqlite:///./database/longma.db
STORAGE_PATH=./backend/storage

# 文件大小限制（MB）
ACHIEVEMENT_FILE_MAX_MB=20
PARTY_MATERIAL_MAX_MB=20

# 党建班级与签到窗口
PARTY_CLASSES=大数据25级,大数据24级,大数据23级,大数据22级
PARTY_SIGN_IN_WINDOW_MINUTES=60

# AI 服务（已配置为 DeepSeek）
AI_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
AI_BASE_URL=https://api.deepseek.com
AI_MODEL=deepseek-chat

# 联网搜索
WEB_SEARCH_ENABLED=true
WEB_SEARCH_URL=https://www.bing.com/search
WEB_SEARCH_TIMEOUT_SECONDS=15
WEB_SEARCH_MAX_RESULTS=5

# 业务 Skill 语义向量（模型名可替换为本地离线路径）
EMBEDDING_MODEL_NAME=BAAI/bge-small-zh-v1.5
EMBEDDING_DEVICE=cpu
EMBEDDING_DIM=512
EMBEDDING_BATCH_SIZE=32
SKILL_RECOMMEND_LIMIT=5
SEMANTIC_MIN_SCORE=0.35

# CORS（开发环境 *；生产环境必须指定具体域名）
CORS_ORIGINS=*

# 班级与存储
CLASS_NAME=大数据管理与应用25级
DEFAULT_QUOTA_MB=500

# 登录安全（5 分钟内最大尝试次数）
LOGIN_MAX_ATTEMPTS=10
LOGIN_WINDOW_MINUTES=5

# MCP 服务令牌（用 python -c "import secrets; print('lm_mcp_'+secrets.token_hex(24))" 生成）
MCP_SERVICE_TOKEN=lm_mcp_<用 secrets.token_hex(24) 生成>
MCP_FETCH_TIMEOUT=10

# API 限流（滑动窗口，每分钟最大请求数）
API_RATE_LIMIT=120
API_RATE_WINDOW_MINUTES=1

# 文件软删除保留天数（超期物理删除）
FILE_RETENTION_DAYS=7

# Office 文件在线预览（依赖系统安装 LibreOffice/soffice）
PREVIEW_OFFICE_ENABLED=true
PREVIEW_OFFICE_TIMEOUT_SECONDS=60
PREVIEW_OFFICE_MAX_MB=20
PREVIEW_OFFICE_CONCURRENCY=2
PREVIEW_CACHE_TTL_DAYS=7
```

### 关键配置说明

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `DB_URL` | `sqlite:///./database/longma.db` | 开发用 SQLite，生产用 PostgreSQL |
| `SECRET_KEY` | 需在 `.env` 设置 | JWT 签名密钥（未设置时自动生成） |
| `AI_API_KEY` / `AI_BASE_URL` / `AI_MODEL` | DeepSeek | AI 服务接入配置 |
| `WEB_SEARCH_ENABLED` | `true` | AI 对话联网搜索开关 |
| `EMBEDDING_MODEL_NAME` | `BAAI/bge-small-zh-v1.5` | 业务 Skill 语义向量模型（可用本地离线路径） |
| `SKILL_RECOMMEND_LIMIT` / `SEMANTIC_MIN_SCORE` | `5` / `0.35` | 语义推荐条数与最低相似度阈值 |
| `PARTY_CLASSES` | 大数据各年级 | 党建班级名单（逗号分隔） |
| `PARTY_SIGN_IN_WINDOW_MINUTES` | `60` | 党建活动签到有效窗口 |
| `ACHIEVEMENT_FILE_MAX_MB` / `PARTY_MATERIAL_MAX_MB` | `20` | 成果附件 / 党建材料大小上限 |
| `PREVIEW_OFFICE_*` | 见上 | Office 在线预览开关、超时、并发、缓存 |
| `CORS_ORIGINS` | `*` | 生产环境必须指定具体域名 |
| `MCP_SERVICE_TOKEN` | 需在 `.env` 设置 | MCP 工具服务令牌（未设置时自动生成） |
| `CLASS_NAME` | `大数据管理与应用25级` | 班级名称（班级知识库隔离） |
---

## 前端使用

### 概述

前端为原生 JavaScript（Vanilla JS）单页应用（SPA），无需构建工具，由后端直接托管。

- **框架**：原生 JavaScript（无 React/Vue/Angular 依赖）
- **路由**：基于 `location.hash` 的前端路由
- **状态管理**：sessionStorage 持久化
- **AI 对话**：SSE 流式接收 AI 回复
- **目录**：`frontend/js/app.js`（路由与导航）、`frontend/js/views/*.js`（各页面视图）

### 启动方式

```bash
# 启动后端（同时托管前端）
.\.venv\python.exe run.py

# 浏览器打开
# http://127.0.0.1:8000/
```

### 功能模块与角色权限

| 模块 | 路由 | 说明 | 可见角色 |
|------|------|------|----------|
| 工作台 | `#overview` | 个人数据概览、最近活动、快捷入口 | 全部 |
| AI 对话 | `#chat` | AI 助手对话、SSE 流式回复、Skill 调用、联网搜索、附件 | 全部 |
| 知识库 | `#knowledge` | 个人/班级知识库、文件夹、在线预览、班级文件版本 | 全部 |
| 课程作业 | `#courses` | 课程列表、课表、作业发布/提交/批改、附件 | 全部 |
| 成果档案 | `#achievements` | 成果录入（动态表单）、附件、审核、年度时间线、统计 | 全部 |
| 资源社区 | `#community` | 资源发布、浏览、收藏、点赞 | 全部 |
| 导师双选与教师系统 | `#mentorship` | 学术导师双选、教师研究方向、学习计划、交流申请 | 学生/教师/管理员 |
| 通知 | `#notifications` | 站内通知中心（含党建/政治面貌通知） | 全部 |
| 个人中心 | `#profile` | 个人资料、画像、校友转换申请 | 全部 |
| 党建 | `#party` | 党员档案、活动、签到、材料、统计（详见党建章节） | 学生/管理员 |
| 管理后台 | `#admin` | 用户/审计/统计/配置/党建管理/ Skill 管理 | 管理员 |

> 导航栏按角色自动过滤：管理员可见全部；学生可见党建模块；教师不可见党建与成就管理入口。

### 前端项目结构

```
frontend/
├── index.html              # 单页入口
├── css/                    # 样式
└── js/
    ├── app.js              # 路由、导航、会话初始化
    ├── api.js              # API 封装（含确认令牌透传）
    ├── state.js / ui.js    # 全局状态与 UI 工具
    ├── achievement_*.js    # 成果档案表单/列表/时间线/上传/模板
    ├── admin_party.js      # 管理端党建管理
    └── views/
        ├── overview.js  chat.js  knowledge.js  courses.js
        ├── community.js  mentorship.js  notifications.js
        ├── profile.js  admin.js  party.js
```
---

## 核心模块详解

### 1. 认证与用户

- 路由：[api/routes/auth.py](backend/app/api/routes/auth.py)、[api/routes/users.py](backend/app/api/routes/users.py)、[api/routes/admin_users.py](backend/app/api/routes/admin_users.py)

#### 使用方式

```python
# --- 认证 ---
POST /api/v1/auth/login            # 登录，返回 access_token + refresh_token
POST /api/v1/auth/refresh          # 刷新令牌
POST /api/v1/auth/logout           # 登出（撤销当前会话）
POST /api/v1/auth/logout-all       # 撤销所有设备会话

# --- 用户 ---
GET  /api/v1/users/me              # 我的资料（含 role/class_name/quota/party_json/political_status）
PUT  /api/v1/users/me              # 更新资料与画像 profile_json
PUT  /api/v1/users/me/password     # 修改密码

# --- 校友转换（学生申请 → 管理员审批） ---
POST /api/v1/users/me/alumni-request           # 学生发起校友转换申请
GET  /api/v1/admin/users/alumni-requests        # 管理员查看申请列表
POST /api/v1/admin/users/alumni-requests/{id}/approve  # 批准（角色转为校友）
POST /api/v1/admin/users/alumni-requests/{id}/reject   # 拒绝
POST /api/v1/admin/users/{user_id}/convert-alumni      # 管理员直接转换
```

**角色**：`student`（在校学生）、`alumni`（校友）、`teacher`（教师）、`admin`（管理员）。

**说明**：用户表新增 `party_json`（党建档案 JSON）与 `political_status`（政治面貌及审核状态）字段，供党建模块复用。

### 2. AI 对话

- 路由：[api/routes/chat.py](backend/app/api/routes/chat.py)
- 服务：[services/chat_service.py](backend/app/services/chat_service.py)、[services/web_search_service.py](backend/app/services/web_search_service.py)、[services/chat_attachment_service.py](backend/app/services/chat_attachment_service.py)

#### 使用方式

```python
# 创建会话
POST /api/v1/chat/sessions
Body: {"title": "新会话"}

# 列出我的会话
GET /api/v1/chat/sessions

# 发送消息（SSE 流式响应）
POST /api/v1/chat/sessions/{session_id}/messages
Body: {"content": "你好"}

# 非流式（一次性返回）
POST /api/v1/chat/sessions/{session_id}/messages/simple

# 重新生成回复（V3.0 新增）
POST /api/v1/chat/sessions/{session_id}/messages/{message_id}/regenerate

# 消息附件（V3.0 新增）
GET  /api/v1/chat/messages/{message_id}/attachments
GET  /api/v1/chat/attachments/{attachment_id}/download
GET  /api/v1/chat/attachments/{attachment_id}/preview

# Agent 状态与记忆
GET  /api/v1/chat/agent/status
POST /api/v1/chat/agent/clear-memory
```

**SSE 事件序列**：`message`（用户消息已保存）→ `rag`（RAG 引用来源）→ `chunk`（AI 回复片段，多次）→ `done`（回复完成）。

**能力**：支持 RAG 检索（个人/班级知识库）、联网搜索（`WEB_SEARCH_*` 配置，默认 Bing）、Agent 工具调用、消息附件上传/下载/预览、回复重新生成。

### 3. 知识库

- 路由：[api/routes/knowledge.py](backend/app/api/routes/knowledge.py)（个人）、[api/routes/class_knowledge.py](backend/app/api/routes/class_knowledge.py)（班级）

#### 使用方式

```python
# --- 个人知识库 ---
POST   /api/v1/knowledge/upload             # 上传文件（自动解析分块入库）
GET    /api/v1/knowledge/files              # 文件列表
GET    /api/v1/knowledge/folders            # 文件夹列表（V3.0 新增）
POST   /api/v1/knowledge/folders            # 创建文件夹
PUT    /api/v1/knowledge/folders/{id}       # 重命名文件夹
DELETE /api/v1/knowledge/folders/{id}       # 删除文件夹
PUT    /api/v1/knowledge/files/{id}/move    # 移动文件到文件夹
GET    /api/v1/knowledge/files/{id}/preview        # 在线预览（文本/PDF/Office）
GET    /api/v1/knowledge/files/{id}/preview/raw    # 预览原始内容
GET    /api/v1/knowledge/files/{id}/download      # 下载
PUT    /api/v1/knowledge/files/{id}         # 重命名
DELETE /api/v1/knowledge/files/{id}         # 删除（软删除）
GET    /api/v1/knowledge/quota              # 个人配额

# --- 班级知识库（教师/管理员维护，全班共享） ---
POST   /api/v1/class-knowledge/upload
GET    /api/v1/class-knowledge/files
GET    /api/v1/class-knowledge/folders
POST   /api/v1/class-knowledge/folders
PUT    /api/v1/class-knowledge/folders/{id}
DELETE /api/v1/class-knowledge/folders/{id}
PUT    /api/v1/class-knowledge/files/{id}/move
POST   /api/v1/class-knowledge/files/{id}/replace   # 替换文件生成新版本（V3.0 新增）
GET    /api/v1/class-knowledge/files/{id}/versions  # 版本列表（V3.0 新增）
GET    /api/v1/class-knowledge/files/{id}/versions/{version}/download
GET    /api/v1/class-knowledge/files/{id}/preview
GET    /api/v1/class-knowledge/files/{id}/preview/raw
PUT    /api/v1/class-knowledge/files/{id}
DELETE /api/v1/class-knowledge/files/{id}
```

**说明**：支持 PDF/TXT/Markdown/Office（Word/Excel/PPT）在线预览，Office 转换依赖 LibreOffice（`PREVIEW_OFFICE_*` 配置）；班级文件支持版本管理（`KnowledgeFileVersion`），替换后保留历史版本可回滚下载。

### 4. 成果档案

- 路由：[api/routes/achievements.py](backend/app/api/routes/achievements.py)、[api/routes/achievement_stats.py](backend/app/api/routes/achievement_stats.py)
- 服务：[services/achievement_service.py](backend/app/services/achievement_service.py)、[services/achievement_templates.py](backend/app/services/achievement_templates.py)

#### 成果类别

`paper`（论文）、`award`（竞赛获奖）、`research`（科研项目）、`patent`（专利/软著）、`innovation`（创新创业）、`organization`（组织管理）、`social`（社会实践）、`arts`（文体活动）。

#### 使用方式

```python
# --- 成果管理 ---
POST   /api/v1/achievements               # 创建成果（动态表单，含 details_json）
POST   /api/v1/achievements/files         # 上传成果附件
GET    /api/v1/achievements               # 我的成果列表
GET    /api/v1/achievements/years         # 可选年份列表
GET    /api/v1/achievements/public/list   # 公开成果（仅已审核 + 公开）
GET    /api/v1/achievements/{id}          # 成果详情
PUT    /api/v1/achievements/{id}          # 更新成果
DELETE /api/v1/achievements/{id}          # 删除（软删除）
GET    /api/v1/achievements/stats         # 成果统计

# --- 审核（管理员） ---
GET  /api/v1/achievements/admin/all
PUT  /api/v1/achievements/admin/{id}/approve
PUT  /api/v1/achievements/admin/{id}/reject

# --- 模板（动态表单字段定义） ---
GET /api/v1/achievements/templates        # 按类别获取模板字段
```

**说明**：成果采用模板化动态表单（`achievement_templates`），按类别定义字段；支持附件（`ACHIEVEMENT_FILE_MAX_MB` 限制）、年度时间线、类别统计；党建模块可引用成果并建立关联。

### 5. 资源社区

- 路由：[api/routes/resources.py](backend/app/api/routes/resources.py)

#### 资源类型

`experience`（竞赛经验）、`material`（学习资料）、`tool`（项目工具）、`recruit`（团队招募）、`competition`（比赛信息）、`project`（项目）。

#### 使用方式

```python
POST   /api/v1/resources                # 发布资源（需确认令牌，见「任务确认」）
GET    /api/v1/resources                # 浏览资源列表（分页/类型过滤）
GET    /api/v1/resources/{id}           # 详情（自动增加浏览量）
POST   /api/v1/resources/{id}/favorite  # 收藏/取消收藏
GET    /api/v1/resources/my/favorites   # 我的收藏
POST   /api/v1/resources/{id}/like      # 点赞/取消点赞

# --- 审核（管理员） ---
GET /api/v1/resources/admin/pending
PUT /api/v1/resources/admin/{id}/approve
PUT /api/v1/resources/admin/{id}/reject
```

### 6. 教师系统

- 路由：[api/routes/teachers.py](backend/app/api/routes/teachers.py)、[api/routes/applications.py](backend/app/api/routes/applications.py)

```python
# --- 教师方向管理（教师/管理员） ---
POST   /api/v1/teachers/directions          # 创建研究方向
GET    /api/v1/teachers/directions/mine     # 我的方向
PUT    /api/v1/teachers/directions/{id}     # 更新方向
DELETE /api/v1/teachers/directions/{id}     # 删除方向（软删除）

# --- 教师匹配 ---
GET /api/v1/teachers/search                 # 学生按关键词搜索匹配教师
GET /api/v1/teachers/{id}                   # 教师详情

# --- 交流申请 ---
POST   /api/v1/applications                 # 学生提交申请
GET    /api/v1/applications/mine            # 学生查看已提交申请
GET    /api/v1/applications/received        # 教师查看收到的申请
POST   /api/v1/applications/{id}/respond    # 教师接受/拒绝
DELETE /api/v1/applications/{id}            # 学生取消申请

# --- 学习计划 ---
POST   /api/v1/learning-plans               # 创建计划
GET    /api/v1/learning-plans/mine          # 我的计划
PUT    /api/v1/learning-plans/{id}          # 更新计划
DELETE /api/v1/learning-plans/{id}          # 删除计划
```

### 7. 课程与作业

- 路由：[api/routes/courses.py](backend/app/api/routes/courses.py)、[api/routes/assignments.py](backend/app/api/routes/assignments.py)
- 服务：[services/submission_service.py](backend/app/services/submission_service.py)、[services/course_nl_service.py](backend/app/services/course_nl_service.py)

```python
# --- 课程管理（教师/管理员） ---
POST   /api/v1/courses                # 创建课程
GET    /api/v1/courses/mine           # 我的课程
GET    /api/v1/courses                # 课程列表（含课表 course_schedules）
PUT    /api/v1/courses/{id}           # 更新课程
DELETE /api/v1/courses/{id}           # 删除课程

# --- 作业管理 ---
POST   /api/v1/assignments            # 发布作业（教师/管理员，发布后自动通知学生）
GET    /api/v1/assignments            # 作业列表
POST   /api/v1/assignments/{id}/submit            # 提交作业（附件，可多次提交生成版本）
GET    /api/v1/assignments/{id}/submissions       # 查看提交历史
POST   /api/v1/assignments/{id}/submissions/{sid}/grade  # 教师批改
```

**说明**：支持课表（`course_schedules`）、作业附件（`assignment_attachments`/`submission_attachments`）、提交多版本（`submission_versions`）、教师评分批改；发布作业自动向全班学生发送站内通知。

### 8. 通知中心

- 路由：[api/routes/notifications.py](backend/app/api/routes/notifications.py)
- 服务：[services/notification_service.py](backend/app/services/notification_service.py)、[services/party_notify_adapter.py](backend/app/services/party_notify_adapter.py)

```python
GET    /api/v1/notifications                   # 我的通知列表（分页）
PUT    /api/v1/notifications/{id}/read         # 标记已读
PUT    /api/v1/notifications/read-all          # 全部标记已读
DELETE /api/v1/notifications/{id}              # 删除通知
```

**通知类型**：`system`、`achievement`、`resource`、`application`、`course`、`assignment`、`party_activity`（党建活动发布/提醒）、`political_status`（政治面貌审核结果）。

### 9. 管理后台 (Admin)

- 路由：[api/routes/admin_users.py](backend/app/api/routes/admin_users.py)、[api/routes/admin_audit.py](backend/app/api/routes/admin_audit.py)、[api/routes/admin_stats.py](backend/app/api/routes/admin_stats.py)、[api/routes/admin_config.py](backend/app/api/routes/admin_config.py)、[api/routes/admin_skills.py](backend/app/api/routes/admin_skills.py)

```python
# --- 用户管理 ---
GET    /api/v1/admin/users               # 用户列表（筛选/分页）
POST   /api/v1/admin/users               # 创建用户
PUT    /api/v1/admin/users/{id}          # 更新用户
DELETE /api/v1/admin/users/{id}          # 删除用户（软删除）
PUT    /api/v1/admin/users/{id}/reset-password
PUT    /api/v1/admin/users/{id}/enable | /disable
POST   /api/v1/admin/users/import        # 批量导入（CSV）
POST   /api/v1/admin/users/import/preview    # 导入预检（V3.0 新增：校验行数据并返回预览）
POST   /api/v1/admin/users/import/confirm    # 确认执行导入（V3.0 新增）
GET    /api/v1/admin/users/export        # 导出用户

# --- 审计日志 ---
GET /api/v1/admin/audit/logs             # Query: user_id=&action=&start_date=

# --- 系统统计 ---
GET /api/v1/admin/stats                  # 总览（用户/成果/资源/今日活跃等）
GET /api/v1/admin/storage                # 存储用量
GET /api/v1/admin/stats/activity         # 日活跃统计 DAU（V3.0 新增）
GET /api/v1/admin/stats/activity/export  # DAU 导出（V3.0 新增）
GET /api/v1/admin/stats/business         # 业务统计（V3.0 新增）

# --- 系统配置 ---
GET /api/v1/admin/config
PUT /api/v1/admin/config

# --- Skill 管理（V3.0 新增） ---
GET  /api/v1/admin/skills                # Skill 列表（含启用状态）
PUT  /api/v1/admin/skills/{id}           # 启用/停用
POST /api/v1/admin/skills/{id}/invoke    # 手动触发
GET  /api/v1/admin/skills/calls          # 调用记录
```

### 10. 个性化推荐

- 路由：[api/routes/recommendations.py](backend/app/api/routes/recommendations.py)
- 服务：[services/recommendation_service.py](backend/app/services/recommendation_service.py)

```python
GET /api/v1/recommendations/                  # 综合推荐（资源+教师+成果）
GET /api/v1/recommendations/resources?type=competition&limit=10
GET /api/v1/recommendations/teachers
GET /api/v1/recommendations/achievements
```

**算法**：基于用户 `profile_json` 的 `major/research/skills/field/directions` 关键词评分——资源按标签 ×3、标题 ×2、热度 ×1（封顶 8）；教师按方向与标签匹配；成果仅推荐公开且已审核项。未设置画像时按热度/时间兜底。

### 11. 任务执行确认（两阶段提交）

- 路由：[api/routes/confirm.py](backend/app/api/routes/confirm.py)
- 核心：[core/confirmation.py](backend/app/core/confirmation.py)

```python
GET  /api/v1/confirm/operations        # 可确认操作列表
POST /api/v1/confirm/preview           # 预览操作 + 生成确认令牌（JWT，5 分钟有效）
POST /api/v1/confirm/verify            # 执行前验证令牌
```

**流程**：`POST /confirm/preview` 计算 `data_hash`（SHA256）并签发确认令牌 → 前端展示预览 → 业务接口携带令牌执行 → 服务端重算 hash 比对并校验用户/操作/过期时间。覆盖资源发布、成果创建、党建材料上传等写操作，防止误操作与越权。

### 12. 党建数字化（V3.0 新增）

- 路由：[api/routes/party.py](backend/app/api/routes/party.py)（前缀 `/api/v1/party`）
- 服务：[services/party_*.py](backend/app/services/)：`party_profile_service`（档案）、`party_activity_service`（活动）、`party_registration_service`（报名签到）、`party_archive_service`（归档）、`party_stats_service`（统计）、`party_export_service`（导出）、`party_political_status_service`（政治面貌）、`party_political_material_service`（学习材料）、`party_achievement_link_service`（成果关联）、`party_skill_boundary`（AI 只读查询边界）
- 设计文档：[doc/dangjian/dangjian_design.md](doc/dangjian/dangjian_design.md)（M1-M8）、[doc/dangjian/dangjian_politic_design.md](doc/dangjian/dangjian_politic_design.md)（E1-E7）

#### 12.1 党员档案

```python
GET  /api/v1/party/members                      # 党员列表（按班级/状态筛选）
POST /api/v1/party/members                      # 新增党员档案（关联用户）
POST /api/v1/party/members/import               # 批量导入党员
PUT  /api/v1/party/members/{user_id}            # 更新档案
DELETE /api/v1/party/members/{user_id}          # 删除档案
PUT  /api/v1/party/members/{user_id}/status     # 变更状态（积极分子/预备/正式等）
GET  /api/v1/party/members/{user_id}/materials  # 成员材料列表
GET  /api/v1/party/members/{user_id}/archive    # 成员归档详情
```

档案数据存放在用户表的 `party_json` 字段（入党时间、介绍人、支部、班级等），班级范围由 `PARTY_CLASSES` 配置控制。

#### 12.2 党建活动

```python
GET    /api/v1/party/activities                     # 活动列表
POST   /api/v1/party/activities                     # 创建活动（含时间/地点/人数上限）
GET    /api/v1/party/activities/{id}                # 活动详情
PUT    /api/v1/party/activities/{id}                # 更新活动
POST   /api/v1/party/activities/{id}/publish        # 发布（发布后通知目标党员）
PUT    /api/v1/party/activities/{id}/status         # 变更状态（草稿/进行中/结束）
POST   /api/v1/party/activities/{id}/summary        # 填写活动总结
POST   /api/v1/party/activities/{id}/materials      # 上传活动材料
DELETE /api/v1/party/activities/{id}                # 删除活动
GET    /api/v1/party/activities/{id}/archive        # 活动归档详情
```

#### 12.3 报名与签到

```python
POST   /api/v1/party/activities/{id}/register       # 报名参加
DELETE /api/v1/party/activities/{id}/register       # 取消报名
POST   /api/v1/party/activities/{id}/sign-in        # 签到（限 PARTY_SIGN_IN_WINDOW_MINUTES 窗口）
PUT    /api/v1/party/activities/{id}/participants/{user_id}/attendance  # 管理员补录/修正考勤
```

#### 12.4 党建材料与归档

```python
POST   /api/v1/party/materials                      # 上传党建材料（大小受限 PARTY_MATERIAL_MAX_MB）
GET    /api/v1/party/materials                      # 材料列表
DELETE /api/v1/party/materials/{material_id}        # 删除材料
GET    /api/v1/party/archives                       # 归档列表（活动/成员按年度汇总）
GET    /api/v1/party/members/{user_id}/archive      # 成员归档
GET    /api/v1/party/activities/{id}/archive        # 活动归档
```

#### 12.5 党建统计与导出

```python
GET  /api/v1/party/stats        # 统计（党员构成、活动参与、签到率、材料数量等）
POST /api/v1/party/stats/export # 导出统计报表（Excel/CSV）
```

#### 12.6 政治面貌全流程（E1-E7）

```python
# 我的政治面貌
GET  /api/v1/party/political-status/mine            # 我的政治面貌与审核状态
POST /api/v1/party/political-status/mine            # 提交政治面貌变更申请

# 审核（管理员）
GET  /api/v1/party/political-status/reviews         # 待审核列表
GET  /api/v1/party/political-status/roster          # 政治面貌名册
PUT  /api/v1/party/political-status/reviews/{review_id}/approve  # 批准
PUT  /api/v1/party/political-status/reviews/{review_id}/reject   # 驳回

# 政治学习材料
GET    /api/v1/party/learning-materials             # 材料列表
POST   /api/v1/party/learning-materials             # 上传学习材料
PUT    /api/v1/party/learning-materials/{material_id}                  # 更新
DELETE /api/v1/party/learning-materials/{material_id}                  # 删除
POST   /api/v1/party/learning-materials/{material_id}/attachments      # 上传附件
GET    /api/v1/party/learning-materials/{material_id}/attachments/{file_id}  # 下载附件
```

政治面貌含群众/共青团员/入党积极分子/预备党员/正式党员等状态，变更需经管理员审核（`political_status_reviews`），审核结果通过 `political_status` 类型通知送达用户。

#### 12.7 党建与成果关联

```python
POST /api/v1/party/achievements/link     # 将个人成果关联到党建档案
GET  /api/v1/party/mine                  # 我的党建记录总览（档案+活动+材料+关联成果）
```

### 13. AI 业务 Skills（V3.0 新增）

- 路由：[api/routes/skills.py](backend/app/api/routes/skills.py)、[api/routes/business_skills.py](backend/app/api/routes/business_skills.py)、[api/routes/admin_skills.py](backend/app/api/routes/admin_skills.py)
- 服务：[services/semantic_service.py](backend/app/services/semantic_service.py)、[services/party_skill_boundary.py](backend/app/services/party_skill_boundary.py)

```python
# 启用 Skill 列表（对话页动态加载）
GET /api/v1/skills

# 业务 Skill 调用
POST /api/v1/skills/business/competition-recommend   # 竞赛推荐（按画像/标签/来源/截止时间）
POST /api/v1/skills/business/mentor-match            # 导师匹配（按项目描述匹配在职教师方向）
```

系统内置 4 个 `business` 类 Skill：**竞赛推荐、导师匹配、党建查询、成果管理**，同时支持独立 `@触发词` 与 `@agent` 工具调度。党建查询复用 `PartySkillBoundary` 的 5 个只读工具，不开放写操作；成果管理仅操作当前用户数据，写操作必须先获取确认令牌。

**语义匹配**：使用 `skill_embeddings` 保存业务实体向量，综合分 = `0.7 × cosine + 0.2 × keyword + 0.1 × popularity`；模型从本地缓存或 `EMBEDDING_MODEL_NAME` 指定路径加载，不可用时自动回退关键词与热度排序。
---

## AI Agent 智能助手

对话内置 AI Agent，可在聊天中通过 `@agent` 或业务 Skill `@触发词` 调用工具完成查询与操作。

### 触发方式

```text
@agent 帮我统计一下系统里有多少用户
@竞赛 推荐几个适合我的比赛
@导师 根据这个项目描述帮我匹配导师
@党建 查询本月党建活动安排
```

### SSE 流式回复中的工具调用

```text
event: tool
{"tool": "count_users", "args": {}}
[工具执行结果]
{"total": 5, "students": 3, ...}
```

### 写操作二次确认示例

```text
用户: @agent 帮我创建一个学生，学号2025004，姓名张三
Agent: 好的，请确认以下信息：
  - 学号: 2025004
  - 姓名: 张三
  - 角色: 学生
  - 初始密码: 123456
确认后请回复"确认执行"。

用户: 确认执行
Agent: ✅ 用户创建成功！用户ID: 9
```

写操作（创建用户、发布资源等）必须先经 `POST /api/v1/confirm/preview` 生成确认令牌，Agent 在用户确认后携带令牌执行，防止误操作。

### 记忆与状态

```python
GET  /api/v1/chat/agent/status        # 查看 Agent 记忆状态
POST /api/v1/chat/agent/clear-memory  # 清空记忆
```

### 能力矩阵

| 能力 | 说明 |
|------|------|
| 对话与 RAG | 结合个人/班级知识库回答，返回引用来源 |
| 联网搜索 | `WEB_SEARCH_ENABLED=true` 时自动联网补充信息 |
| 业务 Skills | 竞赛推荐、导师匹配、党建查询、成果管理 |
| 工具调用 | 系统查询类工具（统计、列表等） |
| 二次确认 | 写操作经确认令牌两阶段提交 |
| 消息附件 | 支持上传附件并解析内容后回答 |
---

## API 参考速查表

完整接口定义以 Swagger UI（`http://127.0.0.1:8000/docs`）为准，以下为速查：

| 模块 | 方法/路径前缀 | 说明 |
|------|---------------|------|
| 认证 | `POST /api/v1/auth/login`、`/refresh`、`/logout`、`/logout-all` | 登录、刷新、登出 |
| 用户 | `GET/PUT /api/v1/users/me`、`PUT /api/v1/users/me/password` | 个人资料、改密 |
| 用户-校友 | `POST /api/v1/users/me/alumni-request` | 校友转换申请 |
| 对话 | `POST /api/v1/chat/sessions/{id}/messages`（SSE） | 流式对话 |
| 对话 | `POST /api/v1/chat/sessions/{id}/messages/{mid}/regenerate` | 重新生成 |
| 对话 | `GET /api/v1/chat/messages/{mid}/attachments`、`/api/v1/chat/attachments/{aid}/download`、`/preview` | 消息附件 |
| 对话 | `GET /api/v1/chat/agent/status`、`POST /api/v1/chat/agent/clear-memory` | Agent 状态 |
| 知识库-个人 | `/api/v1/knowledge/*`（upload/files/folders/quota/preview/download/move） | 个人知识库 |
| 知识库-班级 | `/api/v1/class-knowledge/*`（+replace/versions） | 班级知识库与版本 |
| 课程 | `/api/v1/courses*` | 课程与课表 |
| 作业 | `/api/v1/assignments*`、`/submissions*` | 作业与批改 |
| 成果 | `/api/v1/achievements*`（+files/years/stats/templates/admin） | 成果档案 |
| 资源 | `/api/v1/resources*`（+favorite/like/admin） | 资源社区 |
| 教师 | `/api/v1/teachers*`、`/api/v1/learning-plans*` | 教师方向与匹配 |
| 申请 | `/api/v1/applications*` | 交流申请 |
| 导师双选 | `/api/v1/mentor-selection/*` | 批次、名单导入、志愿、导师决定、匹配结果与导出 |
| 推荐 | `/api/v1/recommendations*` | 个性化推荐 |
| 确认 | `/api/v1/confirm/operations`、`/preview`、`/verify` | 任务确认 |
| 通知 | `/api/v1/notifications*` | 通知中心 |
| 管理 | `/api/v1/admin/users*`（+import/preview/confirm/export/alumni-requests） | 用户管理 |
| 管理 | `/api/v1/admin/audit/logs` | 审计日志 |
| 管理 | `/api/v1/admin/stats*`（+storage/activity/export/business） | 统计与 DAU |
| 管理 | `/api/v1/admin/config` | 系统配置 |
| 管理 | `/api/v1/admin/skills*`（+calls/invoke） | Skill 管理 |
| 党建 | `/api/v1/party/*`（political-status/learning-materials/members/activities/archives/materials/stats/mine/achievements/link） | 党建数字化 |
| Skill | `GET /api/v1/skills` | 启用的 Skill 列表 |
| Skill | `POST /api/v1/skills/business/competition-recommend`、`/mentor-match` | 业务 Skill |
| MCP | `/api/v1/mcp/*` | MCP 工具服务（需 `MCP_SERVICE_TOKEN`） |
---

## 数据模型

模型定义见 [backend/app/models](backend/app/models)。SQLAlchemy 2.0 风格（`Mapped` / `mapped_column`），关键表如下：

### 用户与认证

| 表 | 说明 |
|----|------|
| `users` | 用户：`role`（student/alumni/teacher/admin）、`status`、`class_name`、`quota_mb`、`profile_json`、`party_json`（党建档案）、`political_status`（政治面貌）、`political_status_updated_at` |
| `user_sessions` | 登录会话（多设备） |
| `alumni_conversion_requests` | 校友转换申请 |

### 对话与知识库

| 表 | 说明 |
|----|------|
| `chat_sessions` / `chat_messages` | 会话与消息 |
| `chat_message_attachments` | 消息附件 |
| `knowledge_files` / `file_chunks` | 知识库文件与解析分块 |
| `knowledge_folders` | 知识库文件夹 |
| `knowledge_file_versions` | 班级文件版本 |

### 成果 / 资源 / 教师

| 表 | 说明 |
|----|------|
| `achievements` | 成果（`category`、`details_json`、`status`、`is_public`） |
| `resources` / `resource_favorites` / `resource_likes` | 资源社区 |
| `teacher_directions` | 教师研究方向 |
| `communication_applications` | 交流申请 |
| `learning_plans` | 学习计划 |
| `mentor_selection_batches` | 双选批次、阶段时间、状态和版本号 |
| `mentor_selection_batch_students` / `mentor_selection_batch_mentors` | 批次学生资格快照与参与导师名额 |
| `mentor_preference_submissions` / `mentor_preference_items` | 学生志愿版本、排序和逐导师理由 |
| `mentor_decision_submissions` / `mentor_decision_items` | 导师接收/拒绝决定版本 |
| `mentor_match_result_versions` / `mentor_match_result_items` | 可审计的匹配结果版本和学生匹配项 |
| `mentor_selection_task_runs` / `mentor_selection_notification_deliveries` | 阶段 Worker 任务与通知投递去重记录 |

### 课程与作业

| 表 | 说明 |
|----|------|
| `courses` / `course_schedules` | 课程与课表 |
| `assignments` / `assignment_attachments` | 作业与附件 |
| `submissions` / `submission_versions` / `submission_attachments` | 提交、版本、附件 |

### 党建（V3.0 新增）

| 表 | 说明 |
|----|------|
| `party_activities` | 党建活动（状态、时间、地点、人数上限、总结） |
| `party_activity_participants` | 活动报名/签到/考勤 |
| `party_materials` | 党建材料 |
| `political_status_reviews` | 政治面貌变更审核 |
| `political_materials` | 政治学习材料 |

### Skill 与运行时（V3.0 新增）

| 表 | 说明 |
|----|------|
| `skills` | Skill 注册（`code`、`name`、`category`、`enabled`） |
| `skill_calls` | Skill 调用记录 |
| `skill_embeddings` | 业务实体语义向量 |
| `runtime_config` | 运行时配置键值（`RuntimeConfig`） |

### 其它

| 表 | 说明 |
|----|------|
| `notifications` | 站内通知（`type`、`ref_type`、`ref_id`、`is_read`） |
| `audit_logs` | 审计日志 |
| `files` | 通用文件记录（软删除、保留期清理） |

---

## 数据库迁移

项目使用 Alembic 管理迁移，迁移文件位于 [alembic/versions](alembic/versions)，当前最新版本为 **`p7890q1r2s3`**（AI 对话范围、恢复和 Token 额度）。

```bash
# 查看当前迁移版本
.\.venv\python.exe -m alembic current

# 查看迁移历史
.\.venv\python.exe -m alembic history

# 升级到最新版本
.\.venv\python.exe -m alembic upgrade head

# 降级一个版本
.\.venv\python.exe -m alembic downgrade -1

# 创建新迁移
.\.venv\python.exe -m alembic revision --autogenerate -m "描述"
```

**迁移链末段**：`l3456h7i`（通用知识库）→ `m4567i8`（RuntimeConfig + 活动索引）→ `n5678j9k0l1m`（后续平台迁移）→ `o6789k0l1m2n`（学术导师双选领域表）→ `p7890q1r2s3`（AI 对话范围、恢复、引用和 Token 额度）。
---

## 部署指南

### 方式一：直接运行（开发/演示）

```bash
.\.venv\python.exe run.py
```

### 方式二：Docker Compose（生产推荐）

```bash
cd deploy
docker compose up -d --build
# 包含：FastAPI + PostgreSQL + Nginx
```

### 生产部署步骤

1. 复制 `.env.example` 为 `.env`，**必须修改**：`SECRET_KEY`、`AI_API_KEY`、`CORS_ORIGINS`、`MCP_SERVICE_TOKEN`、`POSTGRES_PASSWORD`（`validate_settings` 会阻止缺失启动）。
2. 执行数据库迁移：`.\.venv\python.exe -m alembic upgrade head`
3. 启动服务：`.\.venv\python.exe run.py`（或 Docker 方式）
4. 如需 Office 在线预览，宿主机需安装 LibreOffice（`soffice`），并开启 `PREVIEW_OFFICE_ENABLED=true`。
5. 生产推荐关闭 `WEB_SEARCH_ENABLED` 或替换为受控搜索源，并设置严格的 `CORS_ORIGINS`。

---

## 开发规范

- 后端：FastAPI + SQLAlchemy 2.0 + Pydantic v2，路由在 `backend/app/api/routes/`，业务逻辑在 `backend/app/services/`，数据访问在 `backend/app/repositories/`。
- 测试：pytest，测试文件位于 `backend/tests/`；**测试使用内存数据库**（`DB_URL=sqlite:///:memory:`），不依赖本地文件与外部服务。
- 迁移：任何模型变更必须新增 Alembic 迁移并保持迁移链连续。
- 确认机制：所有危险/敏感写操作必须先经 `confirm/preview` 获取令牌。

```bash
# 全部测试
$env:DB_URL="sqlite:///:memory:"
.\.venv\python.exe -m pytest backend/tests/ -q

# 单个测试套件
.\.venv\python.exe -m pytest backend/tests/test_xxx.py -q

# 学术导师双选（批次、Excel 名单、志愿、导师决定、匹配发布、权限）
.\.venv\python.exe -m pytest backend/tests/test_mentor_selection.py -q

# 双选前端脚本语法检查
node --check frontend/js/mentor_selection.js

# 带覆盖率
.\.venv\python.exe -m pytest backend/tests/ -q --cov=backend/app --cov-report=term-missing

# Agent 专项测试
.\.venv\python.exe test_agent.py
```

---

## 测试

### 最近验证（2026-08-17）

- **导师双选：11 passed**（`backend/tests/test_mentor_selection.py`，覆盖时间校验、名单 Excel 导入、开放批次、志愿、导师决定、匹配、结果发布和候选档案权限）
- **静态检查**：`mypy`、`ruff` 和 `node --check frontend/js/mentor_selection.js` 已在双选变更范围内执行。
- 全量测试命令见上方“开发规范”；提交前应在独立测试数据库运行完整 `backend/tests/`。

### 测试分组

| 分组 | 覆盖内容 |
|------|----------|
| 认证/用户 | 登录、刷新、登出、用户 CRUD、角色权限 |
| 校友转换 | 学生申请 → 管理员审批全流程 |
| AI 对话 | 会话、消息、SSE 流式、重新生成、附件 |
| 知识库 | 个人/班级上传、文件夹、预览、版本、配额 |
| 成果档案 | 动态表单、附件、审核、统计、时间线 |
| 资源社区 | 发布、审核、收藏、点赞 |
| 教师系统 | 方向、匹配、交流申请、学习计划 |
| 学术导师双选 | 批次时间、Excel 名单预检/导入、参与导师、志愿、导师决定、匹配发布、权限与结果查询 |
| 课程作业 | 课程、课表、作业发布/提交/批改 |
| 通知 | 已读/全部已读/删除 |
| 管理后台 | 用户导入预检、统计、DAU、配置、Skill 管理 |
| 推荐/确认 | 推荐排序、确认令牌两阶段提交 |
| 党建 | 档案、活动、报名签到、材料、归档、统计、政治面貌审核、学习材料、成果关联 |
| Skill | 注册、启用、调用、语义向量回退 |

### 最近验证

```text
backend/tests/test_mentor_selection.py: 11 passed
```
---

## 项目结构

```
LM_SJ/
├── run.py                    # 启动入口（后端 + 托管前端）
├── alembic/                  # 数据库迁移（versions/ 为迁移链）
├── backend/
│   ├── app/
│   │   ├── main.py           # FastAPI 应用与路由注册
│   │   ├── core/             # 配置、安全、确认机制
│   │   ├── api/routes/       # 各模块路由
│   │   ├── services/         # 业务逻辑服务
│   │   ├── repositories/     # 数据访问层
│   │   ├── models/           # SQLAlchemy 模型
│   │   └── schemas/          # Pydantic 模型
│   ├── app/workers/          # 独立 Worker（含导师双选阶段调度）
│   ├── storage/              # 上传文件存储
│   └── tests/                # pytest 测试（43 个文件）
├── frontend/
│   ├── index.html
│   ├── css/
│   └── js/                   # SPA（app.js 路由 + views/）
├── database/                 # 开发用 SQLite 数据库
├── deploy/                   # Docker Compose + Nginx
├── doc/                      # 设计文档（含党建/政治面貌/通用平台任务）
├── skills_design.md          # AI 业务 Skills 设计
├── tongyong_design.md        # 通用平台增强设计
├── test_agent.py             # Agent 专项测试
└── .env.example              # 环境变量示例
```

## 技术栈

| 层 | 技术 |
|----|------|
| 后端框架 | FastAPI（Python 3.11+） |
| ORM | SQLAlchemy 2.0 + Alembic |
| 校验 | Pydantic v2 |
| 数据库 | 开发 SQLite / 生产 PostgreSQL |
| 前端 | 原生 JavaScript SPA（无构建工具） |
| AI | DeepSeek API（SSE 流式）、RAG、联网搜索、语义向量 |
| 语义向量 | `BAAI/bge-small-zh-v1.5`（本地/离线） |
| 文档预览 | LibreOffice（Office 转 PDF）+ 原生文本/PDF 解析 |
| 部署 | Docker Compose + Nginx |
| 测试 | pytest（内存数据库） |

## 常见问题

**Q1：登录提示"账号或密码错误"？**
先用管理员账号登录，在管理后台重置学生密码，或调用 `PUT /api/v1/admin/users/{id}/reset-password`。

**Q2：AI 对话没有回复？**
检查 `.env` 中 `AI_API_KEY` 是否有效、`AI_BASE_URL`/`AI_MODEL` 是否正确；查看 `server-runtime.log`。

**Q3：Office 文件无法在线预览？**
确认宿主机已安装 LibreOffice 且 `PREVIEW_OFFICE_ENABLED=true`，转换超时/大小受 `PREVIEW_OFFICE_TIMEOUT_SECONDS`/`PREVIEW_OFFICE_MAX_MB` 控制。

**Q4：知识库上传后对话检索不到？**
确认文件已解析入库（上传接口返回 `status`），对话中检查 `rag` 事件返回的引用来源；班级文件需教师/管理员上传到班级知识库。

**Q5：数据库需要重置？**

```bash
# 删除现有数据库后重新迁移
Remove-Item database\longma.db
.\.venv\python.exe -m alembic upgrade head
```

**Q6：Skill 语义匹配不可用？**
首次使用会尝试加载 `EMBEDDING_MODEL_NAME`（可改为本地离线路径）；加载失败时自动回退关键词与热度排序，功能不受影响。

**Q7：学生无法正式提交导师志愿？**
确认批次处于“学生填报”阶段，学生已在管理员导入的名单中，并在个人设置填写个人简介和至少 3 门课程成绩。主选必须选择 3 至 4 位导师，填写个人陈述和每位导师的申请理由。

**Q8：导师看不到候选学生或无法做出决定？**
确认批次处于“导师选择”阶段，导师已被管理员加入该批次，且学生已正式提交并选择该导师。导师点击接收/拒绝会保存草稿，最终提交后决定锁定。

**Q9：管理员无法开放主选？**
仅草稿批次可开放。请先完成 Excel 名单预检与导入，并保存至少 3 名参与导师；页面会显示未满足的具体条件。

## 配置说明

### 生成密钥

```bash
# SECRET_KEY（JWT 签名用）
.\.venv\python.exe -c "import secrets; print(secrets.token_hex(32))"

# MCP_SERVICE_TOKEN
.\.venv\python.exe -c "import secrets; print('lm_mcp_' + secrets.token_hex(24))"
```

### 生产部署必须修改

| 配置项 | 说明 | 生成方式 |
|--------|------|---------|
| `SECRET_KEY` | 生产 JWT 密钥 | `openssl rand -hex 32` |
| `AI_API_KEY` | 生产 AI API Key | 到服务商控制台申请新 Key |
| `CORS_ORIGINS` | 前端实际域名 | 如 `https://campusmate.your-school.edu.cn` |
| `MCP_SERVICE_TOKEN` | 生产 MCP Token | `openssl rand -hex 24` |
| `POSTGRES_PASSWORD` | 数据库密码 | 自行设置强密码 |

---

## 版本信息

**当前版本：V3.1（2026-08-17）**

- **V3.1 新增**：学术导师双选。支持批次和阶段管理、CSV/XLSX/XLS 学生名单预检与导入、参与导师和名额、学生主选/补录志愿、导师授权档案查看与接收/拒绝、确定性匹配、结果发布、补录门禁、结果重开、独立阶段 Worker、通知投递去重记录和可审计结果版本。

- **V3.0 新增**：党建数字化（党员档案/活动/报名签到/材料/归档/统计）、政治面貌全流程（申请-审核-名册-学习材料）、AI 业务 Skills（竞赛推荐/导师匹配/党建查询/成果管理 + 语义向量）、通用平台增强（消息附件/回复重新生成/知识库文件夹/班级文件版本/管理端导入预检/DAU 与业务统计/Skill 管理/校友转换/Office 在线预览）
- **V2.1（2026-08-04）**：P1-P9 全部完成 + AI Agent，6 套测试共 155 项断言通过
- **V2.0**：成果档案、资源社区、教师方向、交流申请、学习计划、个性化推荐、任务确认机制

**关联文档**：[CampusMate 需求文档 V2.0](../CampusMate_项目需求分析文档_V2.0_.md)、[系统架构与功能设计](../龙马视界-系统架构与功能设计.md)、[党建设计](doc/dangjian/dangjian_design.md)、[政治面貌设计](doc/dangjian/dangjian_politic_design.md)、[Skills 设计](skills_design.md)、[通用平台设计](tongyong_design.md)
