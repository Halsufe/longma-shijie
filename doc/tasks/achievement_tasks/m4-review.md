# M4 审核模块（Review）

> 输入文档：`../achievements_proposal.md`（第 5、7、9 章）、`../high-level-design.md`（4.4、6、7.4）  
> 前置依赖：M2、M3、M7 模板数据  
> 完成定义：管理员可查看按分类渲染的成果详情与附件并完成通过/拒绝，状态流转与统计口径正确。

## 任务清单

- [x] T4-1 审核列表返回新字段
  - 交付物：`GET /api/v1/achievements/admin/all` 返回 `details` 摘要、附件数量、级别、年份，保留 `status/q` 筛选。
  - 验收：待审核列表可看到模板摘要与附件数。
- [x] T4-2 审核详情与状态流转
  - 交付物：管理员详情含 `details` 全量与附件；approve/reject 沿用现有接口与 `pending → approved/rejected` 状态机。
  - 验收：审核后状态正确，响应含 `details/proofs`。
- [x] T4-3 审核页前端适配
  - 交付物：管理端待审核卡片按分类渲染模板字段（复用 `achievement_templates.js`），附件可预览/下载，通过/拒绝按钮保留。
  - 验收：审核页对 8 类成果均可正常查看和操作。
- [x] T4-4 审核与统计联动测试
  - 交付物：测试审核状态对 M6 统计的影响。
  - 验收：仅 `approved` 计入概览统计，`pending/rejected` 不计入。
