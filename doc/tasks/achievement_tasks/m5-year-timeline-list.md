# M5 年份筛选与列表模块（Year Timeline & List）

> 输入文档：`../achievements_proposal.md`（第 4.2、8 章）、`../high-level-design.md`（4.5、6、7.2、8）  
> 前置依赖：M2  
> 完成定义：用户可按年份时间轴查看自己当年的成果，列表展示与 DOI 跳转正确。

## 任务清单

- [x] T5-1 年份列表接口
  - 交付物：`GET /api/v1/achievements/years` 返回当前用户有成果的年份列表（降序，可按年附带计数）。
  - 验收：无成果时返回空列表；路由不被 `/{achievement_id}` 吞掉。
- [x] T5-2 年份筛选查询
  - 交付物：`GET /api/v1/achievements?year=YYYY` 仅返回该年成果；无 `year` 返回全部。
  - 验收：跨分类按统一成果年份筛选正确。
- [x] T5-3 年份时间轴组件
  - 交付物：`frontend/js/achievement_timeline.js`，显示“全部”与有数据年份，默认选中当前年份，点击年份筛选列表，含空态。
  - 验收：交互符合设计假设，切换年份列表刷新。
- [x] T5-4 成果列表组件
  - 交付物：`frontend/js/achievement_list.js`，展示标题/类别/级别/年份/状态/附件数量；学术论文标题点击跳转 DOI；保留编辑/删除/查看入口。
  - 验收：列表信息完整，无 DOI 的论文标题不跳转。
- [x] T5-5 测试
  - 交付物：年份接口、筛选、时间轴交互、DOI 跳转测试。
  - 验收：全部通过。
