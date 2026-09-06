# M4 工作档案模块（Party Archive）

> 输入文档：`../dangjian/dangjian_proposal.md`（第 8、13 章）、`../dangjian/dangjian_design.md`（4.4、6）  
> 前置依赖：M2、M3  
> 完成定义：活动归档与党员发展档案可查询，名册/参与名单/统计支持 CSV 导出。

## 任务清单

- [x] T4-1 活动归档服务
  - 交付物：POST `/api/v1/party/activities/{id}/summary` 后生成档案视图（活动信息 + 应参加名单 + 报名/签到 + 材料 + 总结）。
  - 验收：归档只读，状态 finished/archived 时数据完整。
- [x] T4-2 党员发展档案查询
  - 交付物：按党员展示身份阶段时间轴与材料清单。
  - 验收：时间轴顺序正确，材料列表完整。
- [x] T4-3 档案查询筛选
  - 交付物：年份/班级/活动类别/党员类型/申请状态组合筛选。
  - 验收：筛选组合返回正确结果。
- [x] T4-4 CSV 导出
  - 交付物：POST `/api/v1/party/stats/export` 与名册/参与名单导出（UTF-8 BOM），单次上限 5000 条。
  - 验收：Excel 打开不乱码，条数限制生效。
- [x] T4-5 测试
  - 交付物：`backend/tests/test_party_archive.py`。
  - 验收：归档、筛选、导出断言全部通过。
