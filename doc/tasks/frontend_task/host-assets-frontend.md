# F01 宿主与品牌资源前端任务

> 依赖：无
> 影响文件：`frontend/index.html`、`frontend/assets/院徽.jpg`
> 目标：让院徽成为全站可用的静态品牌资源，并更新宿主级主题信息。

## 最小任务

- [x] 将 `image/院徽.jpg` 复制到 `frontend/assets/院徽.jpg`，不修改源图片。
- [x] 在浏览器中确认 `/static/assets/院徽.jpg` 可加载且响应状态为 200。
- [x] 将 `frontend/index.html` 的 favicon 改为院徽路径。
- [x] 将 `theme-color` 改为新品牌深蓝 `#14233f`。
- [x] 保留 `#app`、`#toast-region`、`#modal-root` 和 vendor 脚本加载顺序。
- [ ] 检查图片在 1x/2x 视网膜屏不拉伸，使用 `object-fit: contain` 的容器策略。

## 验收

- [ ] 登录页和应用壳层可以引用同一院徽资源（待 F02 应用壳层切换院徽路径后集成验证）。
- [x] 浏览器标签页不再显示绿色 `brand-mark.svg`。
- [x] 直接访问静态资源无 404，控制台无资源加载错误。

## 非目标

- [ ] 不修改后端静态挂载逻辑。
- [ ] 不删除 `brand-mark.svg`，只停止将其作为主品牌标识。
