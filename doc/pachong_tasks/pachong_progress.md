# 学校公告自动采集与推送总体进度

> 需求文档：[`../pachong_proposal.md`](../pachong_proposal.md)  
> 概要设计：[`../pachong_high-level-design.md`](../pachong_high-level-design.md)  
> 状态规则：仅当模块文件中的全部“最小可执行任务”和“完成条件”均已勾选，才可将本页对应模块标记为完成。  
> 初始状态：所有模块尚未开始。

## 模块进度

- [ ] **M1 来源配置与适配器**：[`m01_source_adapters.md`](m01_source_adapters.md)
- [ ] **M2 调度与任务编排**：[`m02_scheduler_orchestration.md`](m02_scheduler_orchestration.md)
- [ ] **M3 抓取与安全访问**：[`m03_secure_fetching.md`](m03_secure_fetching.md)
- [ ] **M4 正文与附件解析**：[`m04_content_attachment_parsing.md`](m04_content_attachment_parsing.md)
- [ ] **M5 相关性、去重与更新识别**：[`m05_relevance_dedup_updates.md`](m05_relevance_dedup_updates.md)
- [ ] **M6 AI 摘要与降级**：[`m06_ai_summary_fallback.md`](m06_ai_summary_fallback.md)
- [x] **M7 公告核心与数据访问**：[`m07_announcement_core_data.md`](m07_announcement_core_data.md)
- [ ] **M8 每日汇总与通知**：[`m08_daily_digest_notifications.md`](m08_daily_digest_notifications.md)
- [ ] **M9 公告查询与工作台**：[`m09_query_dashboard.md`](m09_query_dashboard.md)
- [ ] **M10 管理运维与告警**：[`m10_admin_operations_alerts.md`](m10_admin_operations_alerts.md)
- [ ] **M11 数据清理**：[`m11_data_cleanup.md`](m11_data_cleanup.md)

## 推荐执行顺序

模块编号表示设计边界，不代表严格的开发先后。建议按以下阶段推进：

- [x] **P1 数据基础**：完成 M7 的模型、迁移、Repository 和来源种子数据。
- [ ] **P2 采集入口**：并行完成 M3 安全抓取和 M1 四来源适配器。
- [ ] **P3 内容处理**：完成 M4 正文、附件、PaddleOCR CPU 和 LibreOffice DOC 转换。
- [ ] **P4 智能处理**：完成 M5 相关性/去重/更新与 M6 AI 摘要/降级。
- [ ] **P5 Worker 基础**：完成 M2 调度、租约、任务状态和恢复入口。
- [ ] **P6 用户投递**：完成 M8 汇总快照、批量通知、无公告和分别补发。
- [ ] **P7 用户界面**：完成 M9 查询 API、工作台区域和通知深链接。
- [ ] **P8 管理能力**：完成 M10 任务后台、人工操作、告警和审计。
- [ ] **P9 生命周期与上线**：完成 M11 清理，并执行初始化、部署及全链路验证。

## 跨模块集成检查

- [ ] **I01 数据库迁移**：所有公告表、索引、唯一键和四来源种子数据可在 PostgreSQL 正常升级。
- [ ] **I02 Web/Worker 隔离**：FastAPI Web 进程不启动公告调度器，独立 Worker 可单独启动和停止。
- [ ] **I03 完整采集链路**：四来源候选经安全抓取、解析、筛选、去重和摘要后正确入库。
- [ ] **I04 降级链路**：单站、附件、OCR 或 AI 失败时，其他公告和当日汇总仍可完成。
- [ ] **I05 定时汇总**：20:00 窗口边界正确，只向 active 且未删除用户各投递一条通知。
- [ ] **I06 恢复补发**：连续遗漏窗口按日期分别补发，重复启动不产生重复通知。
- [ ] **I07 用户体验**：工作台可查询和筛选最近 30 天公告，通知深链接可定位对应汇总。
- [ ] **I08 管理闭环**：管理员能定位失败、创建重试、查看结果并收到分级告警。
- [ ] **I09 数据保留**：公告按官网发布日期清理，历史汇总快照和站内通知继续保留。
- [ ] **I10 安全验证**：SSRF、恶意重定向、超大附件、危险 HTML 和临时文件越界测试通过。
- [ ] **I11 规模验证**：1000 个 active 用户的批量投递性能和幂等测试通过。
- [ ] **I12 首次上线**：导入最近 30 天公告但不补发历史通知，并完成一次不投递演练。

## 总体验收

- [ ] 11 个模块全部完成。
- [ ] 跨模块集成检查全部完成。
- [ ] 需求文档第 14 章验收标准全部通过。
- [ ] 生产配置、OCR 模型、中文字体和 LibreOffice 依赖已固化到部署产物。
- [ ] 管理员已能查看最近一次轮询、汇总、告警和清理结果。
