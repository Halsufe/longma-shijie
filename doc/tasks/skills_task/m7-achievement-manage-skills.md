# M7 成果管理 Skill（Achievement Manage）

> 输入文档：`../../skills_proposal.md`（第 7、9.2 章）、`../../skills_design.md`（4.7、6.2、7.4）  
> 前置依赖：M2、现有成果模块  
> 完成定义：AI 可完成本人 8 类成果查询/新增/修改/删除，写操作未确认不落库。

## 任务清单

- [x] T7-1 成果查询工具
  - 交付物：`AgentTools` 新增 `list_my_achievements`、`get_my_achievement`、`get_achievement_templates`。
  - 验收：支持分类/状态/年份筛选；非本人成果不可读。
- [x] T7-2 新增执行
  - 交付物：按分类模板收集字段，复用 `achievement_service` 校验；新增默认 `pending`；证明材料缺失时提示上传，不落库。
  - 验收：8 类模板校验生效，缺失材料不写入。
- [x] T7-3 修改执行
  - 交付物：仅本人可修改；修改后状态重置为 `pending`；沿用模板校验。
  - 验收：修改他人成果被拒，修改后重新审核。
- [x] T7-4 删除执行
  - 交付物：仅本人可软删除，复用 `AchievementRepository.soft_delete`。
  - 验收：删除后列表不可见，物理行保留。
- [x] T7-5 确认辅助函数
  - 交付物：`backend/app/core/confirmation.py` 新增 `require_confirmation_token(operation, token, data, user_id)`。
  - 验收：令牌过期、用户不匹配、数据不一致均拒绝。
- [x] T7-6 业务接口令牌接入
  - 交付物：POST/PUT 支持 body `confirmation_token`，DELETE 支持 query `confirmation_token`，调用 `require_confirmation_token`。
  - 验收：无令牌/错误令牌不执行写操作。
- [x] T7-7 审计与调用记录
  - 交付物：写操作写 `audit_logs` 与 `skill_calls`，包含操作类型、目标 ID、结果。
  - 验收：成功与失败均有记录。
- [x] T7-8 测试
  - 交付物：`backend/tests/test_achievement_manage_skill.py`。
  - 验收：8 类 CRUD、权限、确认、pending、软删除断言全部通过。
