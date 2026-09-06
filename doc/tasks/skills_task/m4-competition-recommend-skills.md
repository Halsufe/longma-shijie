# M4 竞赛推荐 Skill（Competition Recommend）

> 输入文档：`../../skills_proposal.md`（第 4 章）、`../../skills_design.md`（4.4、6.1、6.4）  
> 前置依赖：M2、M3  
> 完成定义：用户可通过 `@竞赛推荐` 或 `@agent` 获得带理由的比赛推荐，语义失效时回退。

## 任务清单

- [x] T4-1 用户文本组装
  - 交付物：`backend/app/ai/business_skills/competition_recommend.py` 组装 `profile_json` 字段与对话补充描述。
  - 验收：画像字段缺失时仍可运行，对话描述作为补充。
- [x] T4-2 比赛召回与过滤
  - 交付物：从 `resources` 召回 `type=competition`、`status=approved`、未删除、未截止的比赛，支持 `tags/source/limit` 过滤。
  - 验收：已截止比赛不出现；`limit` 默认 5、上限 10。
- [x] T4-3 排序与推荐理由
  - 交付物：调用 M3 语义匹配，输出 `id/title/tags/source/deadline/view_count/like_count/reason/score`，理由必须解释匹配点。
  - 验收：推荐结果含“为什么适合用户”的中文理由。
- [x] T4-4 业务接口
  - 交付物：POST `/api/v1/skills/business/competition-recommend`，登录用户可调用。
  - 验收：请求/响应符合设计 6.4 示例结构。
- [x] T4-5 测试
  - 交付物：`backend/tests/test_competition_recommend_skill.py`。
  - 验收：画像匹配、截止过滤、理由输出、回退、权限断言全部通过。
