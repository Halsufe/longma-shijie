# F03 客户端状态与导航状态前端任务

> 依赖：无
> 影响文件：`frontend/js/state.js`、必要时 `frontend/js/app.js`
> 目标：明确认证、路由、移动侧栏和未读数状态的边界，支持壳层改版。

## 最小任务

- [x] 保持 `accessToken`、`user`、`route`、`sidebarOpen`、`unreadCount` 的现有语义。
- [x] 核对 `setAuth`、`clearAuth`、`setCurrentUser` 的持久化和清理行为。
- [x] 确认 `navigate(route)` 只更新 hash/route，不直接渲染业务 DOM。
- [x] 为移动抽屉补充可复用的开关状态操作，避免页面模块直接修改侧栏。
- [x] 处理刷新、无效 hash、退出后 hash 清空和失效 token 回登录页场景。

## 验收

- [x] 刷新页面后认证状态和当前路由行为不回归。
- [x] 抽屉关闭不会影响当前业务 view 的局部状态。
- [x] 无权限路由仍回退到工作台。

## 非目标

- [x] 不把页面业务数据写入全局 state。
