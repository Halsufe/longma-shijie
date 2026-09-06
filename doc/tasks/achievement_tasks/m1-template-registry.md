# M1 模板定义模块（Template Registry）

> 输入文档：`../achievements_proposal.md`（第 6、11 章）、`../high-level-design.md`（4.1、5.2）  
> 前置依赖：无  
> 完成定义：8 类模板字段、文案、枚举、校验规则与年份派生规则可作为前端表单和后端校验的单一数据源，且与需求文档一致。

## 任务清单

- [x] T1-1 定义模板字段项结构与分类模板结构
  - 交付物：`backend/app/services/achievement_templates.py`（新建），定义 `FieldSpec`（key/label/type/required/enum/format/hint）与分类模板（fields/title_copy/level_usage/year_source）。
  - 验收：结构能完整表达需求文档第 6 章 8 类模板；通用字段（title/level）与 `details` 字段分离。
- [x] T1-2 实现后端 8 类模板定义
  - 交付物：`achievement_templates.py` 中注册 8 类模板，模板标题文案使用需求文档原文，字段与需求文档第 6 章一一对应。
  - 验收：组织管理含 `position`（职务，自由文本）；`paper_type` 枚举为“期刊论文/会议论文/工作论文/其他”；`level` 仅 award/research/innovation/arts 使用。
- [x] T1-3 实现统一成果年份与 achievement_date 派生规则
  - 交付物：`derive_year(category, details)`、`derive_achievement_date(category, details)`，规则按设计文档 4.2/5.1。
  - 验收：论文取发表年月、获奖取获奖年月、项目取立项年份、专利未授权时用申请年月、其余分类取开始年月。
- [x] T1-4 实现前端模板注册表
  - 交付物：`frontend/js/achievement_templates.js`（新建），结构与后端模板定义一致。
  - 验收：字段、枚举、文案与后端注册表一致，M7 可直接引用渲染。
- [x] T1-5 单元测试
  - 交付物：`backend/tests/test_achievement_templates.py`。
  - 验收：8 类字段完整性、必填项、枚举、占位规则、年份派生断言全部通过。
