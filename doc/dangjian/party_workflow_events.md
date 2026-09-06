# 党建 Workflow 事件契约

本模块仅定义调度器接入边界，不负责调度、任务幂等、失败重试或补偿。

| 事件名 | 载荷字段 | 业务落点 |
| --- | --- | --- |
| `party.activity_published` | `activity_id`, `target_user_ids` | 通知中心 |
| `party.registration_deadline_approaching` | `activity_id`, `registered_user_ids` | 通知中心 |
| `party.activity_starting` | `activity_id`, `registered_user_ids` | 通知中心 |
| `party.activity_finished` | `activity_id` | 参与记录生成、归档提醒 |
| `party.status_changed` | `user_id`, `from_status`, `to_status` | 通知本人、审计 |

运行时代码从 `backend.app.services.party_workflow_events` 引用事件常量和
`PARTY_WORKFLOW_EVENT_DEFINITIONS`，不得在调度器内重复硬编码事件名。
