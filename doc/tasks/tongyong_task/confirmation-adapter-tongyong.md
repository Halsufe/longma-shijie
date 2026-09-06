# S2 共享任务确认适配任务清单

> 来源：`tongyong_design.md` 第 4.7 节
> 覆盖：M12 任务确认接入业务接口

- [x] 实现 `verify_optional_confirmation(db, request, operation, target_payload, token)`。
- [x] 令牌缺失放行（兼容旧客户端）。
- [x] 令牌存在：校验有效期、操作人、数据哈希一致。
- [x] 失败统一抛 `AppException("CONFIRMATION_INVALID", ...)`。
- [x] 成功/失败均写审计。
- [x] 接入 `achievements.py`、`resources.py` 写接口（配合 D4/M12）。
- [x] 前端 `api.js` 支持携带令牌，`ui.js` 确认卡片复用。
- [x] 测试：过期、伪造、数据不一致、旧流程兼容。

## 验收

- [x] 业务写接口可被确认机制保护且不破坏旧调用。
