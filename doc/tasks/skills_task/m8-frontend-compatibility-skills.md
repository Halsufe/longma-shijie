# M8 前端与兼容迁移（Frontend & Compatibility）

> 输入文档：`../../skills_proposal.md`（第 10、12 章）、`../../skills_design.md`（4.8、5.5、8、9）  
> 前置依赖：M1-M7  
> 完成定义：前端可进入业务 Skill、确认卡片可用、迁移与文档完整，端到端验收通过。

## 任务清单

- [x] T8-1 公共 Skill 列表接口
  - 交付物：新增 `backend/app/api/routes/skills.py`，`GET /api/v1/skills` 返回启用的 Skill 列表；在 `backend/app/main.py` 注册。
  - 验收：登录用户可获取 4 个业务 Skill 与触发词。
- [x] T8-2 动态 Skill chips
  - 交付物：`frontend/js/views/chat.js` 从 `/api/v1/skills` 动态加载 chips，保留 `@agent` 入口。
  - 验收：接口返回后 chips 自动渲染，点击填入触发词。
- [x] T8-3 推荐结果与确认卡片
  - 交付物：`frontend/js/ui.js` 与 `chat.js` 支持推荐结果表格渲染、理由突出显示、成果确认预览卡片（确认/取消）。
  - 验收：确认前展示操作摘要，确认后执行，取消不落库。
- [x] T8-4 管理端展示
  - 交付物：`frontend/js/views/admin.js` Skill 列表展示 `category=business` 的 4 个 Skill，启停可用。
  - 验收：新增 Skill 自动出现，启停生效。
- [x] T8-5 文档更新
  - 交付物：更新 `README.md`、`backend-task-list.md`，记录业务 Skill、语义服务与 `skill_embeddings`。
  - 验收：文档与新接口、新配置一致。
- [x] T8-6 端到端验收
  - 交付物：`backend/tests/test_skills_e2e.py` 或等价冒烟用例；执行全量 `pytest`。
  - 验收：需求文档第 14 章验收要点全部通过，全量测试通过。
