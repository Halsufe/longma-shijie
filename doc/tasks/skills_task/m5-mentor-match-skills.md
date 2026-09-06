# M5 导师匹配 Skill（Mentor Match）

> 输入文档：`../../skills_proposal.md`（第 5 章）、`../../skills_design.md`（4.5、6.1）  
> 前置依赖：M2、M3  
> 完成定义：用户输入项目描述即可获得教师 + 研究方向 + 理由，输入不足时引导补充。

## 任务清单

- [x] T5-1 输入校验与引导
  - 交付物：`backend/app/ai/business_skills/mentor_match.py` 校验 `project_description`（建议最少 20 字），支持 `tag/teacher_name/limit`。
  - 验收：描述过短时返回引导文案，不返回空结果。
- [x] T5-2 教师方向语义匹配
  - 交付物：对 `teacher_directions`（标题+描述+标签）与教师 `profile_json`（`research/skills/directions/field`）做 M3 语义匹配。
  - 验收：只返回在职教师与 `is_active=true` 的方向。
- [x] T5-3 输出与推荐理由
  - 交付物：每个教师取最优方向，输出 `teacher_id/name`、`direction_id/title/description/tags`、`score/reason`。
  - 验收：理由说明项目描述与方向的匹配点。
- [x] T5-4 业务接口
  - 交付物：POST `/api/v1/skills/business/mentor-match`，登录用户可调用。
  - 验收：请求/响应结构与设计一致。
- [x] T5-5 测试
  - 交付物：`backend/tests/test_mentor_match_skill.py`。
  - 验收：NLP 描述匹配、输入不足、权限、回退断言全部通过。
