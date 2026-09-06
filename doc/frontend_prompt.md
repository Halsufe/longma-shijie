# 龙马·视界前端改版 Vibe Coding 起始 Prompt

你是本项目的主 Agent，负责在 `D:\班级ai\BD\LM_SJ` 内自主完成“龙马·视界”全站前端主题与布局改版。整个执行过程不依赖人工确认：读取本 Prompt、需求文档、概要设计和任务清单后，主 Agent 自主安排子 Agent、实现代码、补充测试、运行质量检查、进行浏览器验证并回写进度。

## 1. 权威输入

按以下优先级理解任务：

1. 本 Prompt：执行流程、质量门禁和 Agent 协作规则。
2. `frontend_proposal.md`：已确认的产品需求、品牌方向、页面目标和验收标准。
3. `frontend_design.md`：模块边界、依赖方向、数据流、文件落点和设计 token。
4. `doc/tasks/frontend_task/frontend-progress.md`：总体进度。
5. `doc/tasks/frontend_task/<module-name-frontend>.md`：对应模块的最小执行清单。
6. 现有源码、测试和 README：用于确认实际代码契约，不得推翻上面的已确认约束。

如果源码与文档存在差异，优先保留现有业务行为，并采取最小兼容改动；将差异记录到最终报告，不自行扩大范围。无需向用户提问，除非遇到无法通过本地检查或安全替代方案解决的硬阻塞。

## 2. 工程目标

把现有原生 HTML/CSS/ES Module 前端升级为统一的现代校园视觉系统：

- 产品名统一为 `龙马·视界`。
- 品牌机构文案为 `中央财经大学管理科学与工程学院`，空间/班级文案为 `大数据管理与应用`。
- 使用 `image/院徽.jpg` 作为登录页、侧栏和 favicon 的主品牌资源，推荐静态路径 `/static/assets/院徽.jpg`。
- 采用院徽/班徽提炼的深蓝、灰蓝、亮蓝，配合少量金色和语义色。
- 保留桌面端“左侧固定导航 + 顶部栏 + 内容区”，小于 860px 使用侧栏抽屉。
- 覆盖登录页、工作台、AI 对话、知识库、课程与作业、成果与社区、教师与计划、党建、通知中心、个人设置和管理后台。
- 只改视觉、布局和为响应式适配所需的前端交互；不得改变 API、数据库、权限、路由 key、表单提交语义、文件操作和聊天数据结构。

## 3. 主 Agent 协作协议

### 3.1 启动检查

主 Agent 首先：

- 查看 `git status`、项目目录和现有未提交修改；不得撤销用户已有改动。
- 阅读四份权威文档和将要执行模块的任务文件。
- 建立执行计划，标明当前模块、依赖、测试和阻塞。
- 检查 Python、`.venv`、Node.js、浏览器自动化能力是否可用。

### 3.2 子 Agent 调度

主 Agent 必须为每个 F01-F17 模块生成一个对应子 Agent。受并发槽位限制时按依赖波次调度，不能同时让多个 Agent 修改同一文件：

| 波次 | 模块 | 说明 |
| --- | --- | --- |
| W1 | F01、F03、F04 | 资源、状态、接口边界，可并行但不得覆盖同一文件 |
| W2 | F05 | 共享 CSS/UI 设计系统，完成后才进入页面批次 |
| W3 | F02 | 应用壳层、登录、侧栏抽屉，依赖 W1/W2 |
| W4 | F06-F15 | 页面模块；同一时间只让一个 Agent 改 `styles.css`，页面 Agent 优先只改对应 view |
| W5 | F16、F17 | 成果和党建管理子模块，分别集成到 F10/F15 |
| W6 | 主 Agent | 全量回归、浏览器截图、缺陷修复和交付报告 |

每个子 Agent 的固定指令：

1. 只读取并执行自己的 `<module>-frontend.md`，同时遵守本 Prompt 和设计文档。
2. 先检查目标文件现状，再用 `apply_patch` 做最小修改；不进行无关重构。
3. 只修改自己负责的源文件和对应测试文件；不要修改总体进度文件。
4. 为每一个改变的行为补充或更新 pytest 单元/静态契约测试；必要时补充 JS 语法检查用例。
5. 运行本模块可运行的最小测试和质量检查。
6. 完成后勾选自己任务文件中的 checklist，向主 Agent 返回：改动文件、测试命令、测试结果、遗留风险和是否需要主 Agent 集成。

主 Agent 收到子 Agent 结果后负责：

- 检查 diff 是否越过模块边界、是否改变业务协议。
- 解决冲突，尤其是 `styles.css`、`app.js`、`ui.js` 和共享测试文件。
- 只有模块代码和测试通过后，才在 `frontend-progress.md` 勾选对应模块。
- 不得为了“完成”而勾选失败、跳过或未验证的任务。

### 3.3 无人工参与规则

- 不向用户发送澄清问题、确认问题或等待批准。
- 遇到样式细节未指定时，按需求文档的 token、断点和概要设计采取最小一致方案。
- 遇到依赖、端口或浏览器问题时，先使用本地替代方案、备用端口或已安装工具；连续尝试仍无法解决时，在最终报告明确记录，而不是假装通过。
- 不执行破坏性 git 操作，不重置、不覆盖用户已有且与本任务无关的修改。

## 4. 模块任务映射

| ID | 任务文件 | 主要源码 | 前置依赖 |
| --- | --- | --- | --- |
| F01 | `host-assets-frontend.md` | `frontend/index.html`、`frontend/assets/院徽.jpg` | 无 |
| F02 | `app-shell-frontend.md` | `frontend/js/app.js` | F01、F03、F05 |
| F03 | `state-frontend.md` | `frontend/js/state.js` | 无 |
| F04 | `api-frontend.md` | `frontend/js/api.js` | F01 |
| F05 | `design-system-frontend.md` | `frontend/assets/styles.css`、`frontend/js/ui.js` | F01 |
| F06 | `overview-frontend.md` | `frontend/js/views/overview.js` | F02、F05 |
| F07 | `chat-frontend.md` | `frontend/js/views/chat.js` | F02、F05 |
| F08 | `knowledge-frontend.md` | `frontend/js/views/knowledge.js` | F05 |
| F09 | `courses-frontend.md` | `frontend/js/views/courses.js` | F05 |
| F10 | `community-frontend.md` | `frontend/js/views/community.js` | F05、F16 |
| F11 | `mentorship-frontend.md` | `frontend/js/views/mentorship.js` | F05 |
| F12 | `party-frontend.md` | `frontend/js/views/party.js` | F05 |
| F13 | `notifications-frontend.md` | `frontend/js/views/notifications.js` | F05 |
| F14 | `profile-frontend.md` | `frontend/js/views/profile.js` | F03、F05 |
| F15 | `admin-frontend.md` | `frontend/js/views/admin.js` | F02、F05、F17 |
| F16 | `achievements-frontend.md` | `frontend/js/achievement_*.js` | F05 |
| F17 | `admin-party-frontend.md` | `frontend/js/admin_party.js` | F05、F15 |

## 5. 实现规则

### 5.1 技术和代码边界

- 沿用原生 HTML/CSS/ES Module；不引入 React/Vue 等框架迁移。
- 共享组件优先复用 `ui.js` 和现有 class；新增抽象只有在减少真实重复时才允许。
- 所有文本输出继续使用现有 HTML 转义工具，不能把后端文本直接当作 HTML 注入。
- 所有图标按钮必须有 `aria-label` 和 tooltip/title；保持真实 button/input/label 语义。
- 所有新增中文源码和文档使用 UTF-8；只修复本次触及的乱码文案。
- CSS 采用 token + 组件类 + 页面命名空间；禁止使用大范围 `!important` 或删除其他页面依赖的旧类。
- 设计要求中的“漂亮”不得以大面积渐变、发光、装饰图覆盖可读内容为代价。

### 5.2 资源和文案

- 主品牌文本必须准确出现：`龙马·视界`、`中央财经大学管理科学与工程学院`、`大数据管理与应用`。
- 院徽资源统一指向 `/static/assets/院徽.jpg`；图片必须 contain，不可拉伸、裁切到无法识别。
- 不再使用绿色 `brand-mark.svg` 作为主品牌或 favicon；文件可保留供兼容检查。

### 5.3 页面信息优先级

工作台首屏严格优先展示：成果统计、快捷入口、党建动态、AI 对话入口、待办、通知。其他页面沿用需求文档第 6 节的字段排序和操作位置，不创造新的业务信息。

## 6. 测试与质量门禁

### 6.1 测试策略

虽然主体是原生前端，仍必须提供完整的 pytest 覆盖：

- 每个模块对改变的静态契约补充测试，优先放在 `backend/tests/test_frontend_<module>_contract.py`。
- 测试至少覆盖品牌文案/资源路径、关键 CSS token/断点、必需 DOM hook、路由 key、现有 API 字符串和权限相关静态约束。
- 不要在 pytest 中依赖外网、生产数据库、真实 AI 服务或固定本地绝对路径。
- 复用 `Path(__file__).resolve().parents[2]` 定位项目根目录，按 UTF-8 读取源码。
- 对动态行为可使用 Node 可执行的最小 JS 单元测试或静态契约测试；不能用脆弱的完整 HTML 快照代替行为测试。
- 保留并确保现有 `test_chat_frontend_contract.py`、`test_achievement_frontend_contract.py` 等测试继续通过。

### 6.2 必须执行的命令

在项目根目录 PowerShell 执行，测试过程使用内存数据库：

```powershell
$env:DB_URL = "sqlite:///:memory:"
.\.venv\python.exe -m pytest backend/tests/ -q
.\.venv\python.exe -m mypy backend
.\.venv\python.exe -m ruff check backend
Get-ChildItem frontend\js -Filter *.js -Recurse | ForEach-Object { node --check $_.FullName }
```

如果环境没有 `.venv`，先使用仓库已有依赖环境；不得擅自升级核心依赖。若新增 Python 测试依赖，先检查 `requirements-dev.txt`，并保持可离线安装。

### 6.3 浏览器与视口验证

- 启动本地服务：`\.venv\python.exe run.py`；如默认端口被占用，使用备用端口并记录 URL。
- 使用 Playwright、项目内浏览器工具或等效自动化工具完成登录页、工作台、AI 对话、知识库/表格页和管理页检查。
- 至少验证 320px、375px、768px、1024px、1440px。
- 检查院徽实际渲染、页面非空、无重叠、无页面级横向滚动、抽屉打开/关闭、聊天输入区固定和弹窗边界。
- 保存关键页面截图或验证记录，路径放入最终报告；不能只凭 CSS 静态阅读声称视觉通过。

## 7. 进度、提交和报告规则

### 7.1 Checklist 回写

- 子 Agent 完成一项可验证工作后，勾选自己任务文件中的对应 `[ ]`。
- 主 Agent 只有在模块测试和集成检查通过后，才勾选 `frontend-progress.md` 中的模块。
- 任何失败、跳过或环境阻塞项必须保留未勾选，并在执行记录注明原因。

### 7.2 主 Agent 最终检查表

- [ ] F01-F17 所有模块均有子 Agent 结果和变更摘要。
- [ ] 资源、壳层、共享设计系统先于页面模块完成。
- [ ] 所有前端变更均未改变 API、权限、路由 key 和业务字段。
- [ ] pytest 全量通过。
- [ ] mypy 全量通过。
- [ ] ruff 全量通过。
- [ ] 所有前端 JS 通过 `node --check`。
- [ ] 浏览器视口和关键业务冒烟通过。
- [ ] 总体进度与模块 checklist 状态一致。

### 7.3 最终交付报告

主 Agent 最终回复必须简明列出：

1. 已完成的模块和主要文件。
2. pytest、mypy、ruff、Node 语法检查的实际命令和结果。
3. 浏览器验证的 URL、视口、截图路径和已覆盖场景。
4. 未完成项、已知限制或无法验证的外部条件。
5. `frontend-progress.md` 是否已同步更新。

## 8. 完成定义

本任务只有同时满足以下条件才算完成：

- 所有需求范围内页面使用统一的院徽品牌和新主题 token。
- 桌面、平板和手机布局满足需求断点，移动端抽屉可用。
- 页面业务接口、权限、表单和数据结果保持不变。
- 每个模块的 checklist 已完成或对阻塞有明确记录。
- 完整 pytest、mypy、ruff 和 Node 语法检查通过。
- 浏览器实际验证覆盖关键页面和五个视口，不以静态代码检查代替视觉验收。

