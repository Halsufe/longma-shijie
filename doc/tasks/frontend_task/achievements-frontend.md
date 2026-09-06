# F16 成果子模块前端任务

> 依赖：F05
> 影响文件：`frontend/js/achievement_templates.js`、`achievement_list.js`、`achievement_timeline.js`、`achievement_form.js`、`achievement_upload.js`
> 集成方：F10 `community.js`、F06 `overview.js` 的成果入口
> 目标：把成果展示、表单、时间线和证明材料做成可复用的最小子模块。

## 最小任务

- [x] 核对并保留成果类别、等级、日期和详情字段模板。
- [x] `achievement_list.js` 输出稳定的列表行/卡片结构，支持状态、标签和操作区。
- [x] `achievement_timeline.js` 输出按年份/时间排序的时间线，不改变排序数据。
- [x] `achievement_form.js` 复用字段模板，保留现有校验、编辑和提交行为。
- [x] `achievement_upload.js` 处理文件选择、待上传列表、进度/失败展示，不改变上传协议。
- [x] 为无成果、无证明、加载和上传失败提供共享状态。
- [x] 所有 HTML 文本继续转义，图标按钮提供 aria-label/title。

## 验收

- [ ] community 页面可以组合列表、时间线、表单和上传模块，不出现重复事件绑定。
- [ ] 工作台成果入口能跳转到原有 community 视图/筛选状态。
- [ ] 移动端标签、附件名和操作按钮不溢出。
