# 龙马·视界前端改版总体进度

> 来源：`frontend_proposal.md`、`frontend_design.md`
> 任务明细：`doc/tasks/frontend_task/<module-name-frontend>.md`
> 更新日期：2026-08-07
> 当前状态：前端主题与布局改版已完成，已通过全量质量门禁和关键视口验收

## 模块进度

- [x] F01 宿主与品牌资源：`host-assets-frontend.md`
- [x] F02 应用壳层与登录：`app-shell-frontend.md`
- [x] F03 客户端状态与导航状态：`state-frontend.md`
- [x] F04 接口适配与静态资源访问：`api-frontend.md`
- [x] F05 共享设计系统：`design-system-frontend.md`
- [x] F06 工作台：`overview-frontend.md`
- [x] F07 AI 对话：`chat-frontend.md`
- [x] F08 知识库：`knowledge-frontend.md`
- [x] F09 课程与作业：`courses-frontend.md`
- [x] F10 成果与社区页面编排：`community-frontend.md`
- [x] F11 教师与计划：`mentorship-frontend.md`
- [x] F12 党建前台：`party-frontend.md`
- [x] F13 通知中心：`notifications-frontend.md`
- [x] F14 个人设置：`profile-frontend.md`
- [x] F15 管理后台壳层：`admin-frontend.md`
- [x] F16 成果子模块：`achievements-frontend.md`
- [x] F17 党建管理子模块：`admin-party-frontend.md`

## 推荐执行顺序

1. F01 宿主与品牌资源、F03 客户端状态、F04 接口适配（基础准备）。
2. F05 共享设计系统。
3. F02 应用壳层与登录。
4. F06-F15 页面模块，可在 F05 完成后按页面并行推进。
5. F16 成果子模块与 F17 党建管理子模块，分别由 F10 和 F15 集成。
6. 跨模块回归：五个代表视口、常见浏览器、角色权限和关键业务冒烟。

## 模块完成判定

- [ ] 所有模块明细中的 checklist 已完成。
- [ ] `frontend/index.html`、`frontend/assets/styles.css`、`frontend/js/app.js` 及必要 view 无新增控制台错误。
- [ ] 320px、375px、768px、1024px、1440px 下无页面级横向溢出。
- [ ] 登录、导航、AI 对话、文件预览/下载、课程提交、成果、党建、通知和管理后台冒烟通过。
- [ ] 现有 API、权限、表单提交和数据结果未改变。

## 执行记录

- 2026-08-07：依据需求文档和概要设计完成 F01-F17 任务拆分。
- 2026-08-07：完成品牌资源、应用壳层、共享设计系统、工作台、页面布局与预览边界改版；新增前端契约测试，完成全量 pytest/mypy/ruff/node 检查及五档视口浏览器冒烟。
