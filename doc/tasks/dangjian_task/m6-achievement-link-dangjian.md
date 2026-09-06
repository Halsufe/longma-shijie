# M6 成长档案联动模块（Achievement Link）

> 输入文档：`../dangjian/dangjian_proposal.md`（第 10、13 章）、`../dangjian/dangjian_design.md`（4.6、6）  
> 前置依赖：M1、M2、M3、成果档案模块  
> 完成定义：党员身份与已完成签到活动可一键写入 achievements（pending），source 标记防重，满足现有模板校验。

## 任务清单

- [x] T6-1 联动服务与防重
  - 交付物：`party_achievement_link_service.py`；details_json 写入 `source_type="party"`、`source_id`；联动前检查是否已存在。
  - 验收：重复联动返回已存在提示，不产生重复成果。
- [x] T6-2 党员身份联动
  - 交付物：正式党员/预备党员一键生成 organization 成果（标题如“许国志大数据英才班党支部党员”），状态 pending。
  - 验收：成果创建成功且模板字段满足必填。
- [x] T6-3 活动经历联动
  - 交付物：已完成签到活动按性质生成 organization/social 成果，状态 pending。
  - 验收：未签到活动不可联动。
- [x] T6-4 模板映射与错误处理
  - 交付物：organization/social 必填字段映射（无 →“无”，结束时间 →“进行中”）；模板校验失败返回可读错误。
  - 验收：联动失败不产生半成品数据。
- [x] T6-5 测试
  - 交付物：`backend/tests/test_party_achievement_link.py`。
  - 验收：防重、身份联动、活动联动、模板校验断言通过。
