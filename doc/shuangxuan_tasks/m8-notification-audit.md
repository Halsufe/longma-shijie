# M8 通知与审计任务清单

> 来源：`../shuangxuan_proposal.md` 第 12、13.3 章；`../shuangxuan_high-level-design.md` 第 4.8、5.7 章  
> 目标：实现站内通知去重、全流程审计和 Worker 系统操作记录。  
> 依赖：M1；被 M7 调用。可与 M3-M6 并行开发服务边界。

## 最小可执行任务

### 通知投递

- [ ] M8-T01 新增 `MentorSelectionNotificationDelivery` 模型，保存批次、轮次、事件、用户、通知 ID 和投递时间。
- [ ] M8-T02 增加 `(batch_id, round, event_key, user_id)` 唯一约束并验证迁移 upgrade/downgrade。
- [ ] M8-T03 实现 `MentorSelectionNotificationService.send_once`，在单事务中创建投递记录和现有 `Notification`。
- [ ] M8-T04 定义事件键和消息构建器：批次开放、学生提交成功、导师收到新申请、导师待处理、提前一天提醒、主选发布、补录开放、补录发布、补录阻塞/延长、结果撤回。
- [ ] M8-T05 实现“当前阶段有待办才提醒”的收件人筛选，避免给已提交学生或已最终提交导师发送待办提醒。
- [ ] M8-T06 统一写入 `type/ref_type='mentor_selection'` 和 `ref_id=batch_id`，确保通知中心可跳转。

### 审计

- [ ] M8-T07 实现 `MentorSelectionAuditService`，统一脱敏 detail 并封装现有 `AuditRepository`。
- [ ] M8-T08 接入批次创建/更新/延长/重开、名单确认/移除、志愿保存/提交/撤回、导师保存/提交、计算/发布/作废审计。
- [ ] M8-T09 接入候选档案查看、证明附件查看和管理员导出审计，不记录手机号、邮箱、成绩正文或附件路径。
- [ ] M8-T10 Worker 审计使用 `operator_id=NULL` 和固定操作人名称，并关联 task key、批次和结果版本。
- [ ] M8-T11 新增管理员按批次查询双选审计记录接口或为现有审计接口增加 `target_type` 筛选约定。

### 验证

- [ ] M8-T12 添加同一事件重复投递只生成一条通知、不同轮次可分别投递和并发唯一约束测试。
- [ ] M8-T13 添加关键写操作、档案查看、附件查看、导出、Worker 操作及敏感信息脱敏测试。

## 模块完成定义

- [ ] M8-DO1 所有需求通知都有唯一事件键，Worker 重试不会产生重复通知。
- [ ] M8-DO2 需求指定的写操作和敏感读操作均可按批次追踪。
- [ ] M8-DO3 M8 专项测试、静态检查通过。
