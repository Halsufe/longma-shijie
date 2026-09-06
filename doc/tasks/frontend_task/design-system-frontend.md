# F05 共享设计系统前端任务

> 依赖：F01
> 影响文件：`frontend/assets/styles.css`、`frontend/js/ui.js`
> 目标：建立全站可复用的颜色 token、组件样式和状态展示。

## 最小任务

- [x] 替换 `:root` 主题 token：深蓝、灰蓝、亮蓝、金色点缀、背景、文字、边框和语义色。
- [x] 保持系统中文字体回退链，统一正文、标题、辅助文本字号和行高。
- [x] 统一 button、icon-button、input、select、textarea、panel、badge、table、toolbar 样式。
- [x] 统一 `pageHeader()`、`loadingState()`、`emptyState()`、`statusBadge()`、`showModal()`、`toast()` 的视觉钩子。
- [x] 为所有交互组件补充 hover、focus-visible、active、disabled、loading、error 状态。
- [x] 建立 sidebar、topbar、main-content、scrim、content-grid 的基础布局类。
- [x] 添加 1200/860/620 断点及 320px 最小宽度保护，避免页面级横向溢出。
- [x] 控制渐变和阴影只出现在品牌区、hover、统计图形、抽屉和弹窗。

## 验收

- [x] 新页面无需重新定义基础按钮、面板、状态和表单样式。
- [x] 键盘焦点可见，图标按钮有 aria-label/title，不依赖颜色传达唯一状态。
- [ ] 共享组件在 Edge、Chrome、360 中无 CSS 解析错误。

## 非目标

- [x] 不删除业务页面依赖的现有类名，除非提供兼容别名。
