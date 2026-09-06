# M7 公告核心与数据访问任务清单

> 模块目标：建立公告领域数据模型、迁移、Repository、状态机和事务服务，作为 Web 与 Worker 共享的数据边界。  
> 前置依赖：无，是 M1 集成及 M2、M4–M11 的基础。  
> 主要目录：`backend/app/models/announcement.py`、`backend/app/repositories/announcement_repo.py`、`backend/app/services/announcement_service.py`

## 最小可执行任务

- [ ] **M7-T01 定义公告领域枚举**：来源、处理、解析、摘要、相关性、任务、汇总和投递状态；添加枚举兼容测试。
- [ ] **M7-T02 创建 `AnnouncementSource` 模型**：实现来源字段、唯一代码、启用状态、排序和运行状态。
- [ ] **M7-T03 创建 `SchoolAnnouncement` 模型**：实现标题、日期、正文、摘要、相关性、关键字段、状态和保留期字段及索引。
- [ ] **M7-T04 创建 `AnnouncementOrigin` 模型**：实现公告与来源映射及 `(source_id, canonical_url)` 唯一约束。
- [ ] **M7-T05 创建 `AnnouncementAttachment` 模型**：实现附件元数据、解析文本、状态和 `(announcement_id, url)` 唯一约束。
- [ ] **M7-T06 创建 `AnnouncementTaskRun` 模型**：实现任务键、类型、状态、窗口、租约、统计、重试和人工操作字段。
- [ ] **M7-T07 创建 `AnnouncementDigest` 模型**：实现唯一窗口、不可变快照、通知文本、发送状态和恢复标记。
- [ ] **M7-T08 创建 `AnnouncementDigestDelivery` 模型**：实现逐用户状态和 `(digest_id, user_id)` 唯一约束。
- [ ] **M7-T09 注册模型到应用元数据**：更新模型导入路径，确保内存测试数据库与生产迁移均识别所有新表。
- [ ] **M7-T10 编写 Alembic 迁移**：创建 7 张表、外键、唯一键和查询索引；验证 PostgreSQL 升级和降级脚本。
- [ ] **M7-T11 写入四个来源种子数据**：按 `code` 幂等 upsert，重复迁移/启动不产生重复记录。
- [ ] **M7-T12 实现 JSON 字段访问器**：PostgreSQL JSONB 与 SQLite 测试环境保持统一 Python 字典/数组接口。
- [ ] **M7-T13 实现来源 Repository**：启停查询、排序、成功/失败时间和连续失败次数更新。
- [ ] **M7-T14 实现公告 Repository 基础查询**：按 ID、URL 来源、日期、标题候选、发现窗口和过期日期查询。
- [ ] **M7-T15 实现公告创建事务**：在一个短事务中创建公告、来源映射和附件元数据，处理唯一键竞争。
- [ ] **M7-T16 实现来源合并事务**：锁定公告、新增来源映射和附件，避免并发重复。
- [ ] **M7-T17 实现公告更新事务**：保存正文、摘要、状态、内容指纹、关键更新字段及时间。
- [ ] **M7-T18 实现公告状态机**：限制 `discovered -> processing -> ready/partial/failed -> expired` 的合法流转。
- [ ] **M7-T19 实现可见性判定**：仅 `relevant/uncertain + ready/partial + 未过期` 可被用户查询和汇总。
- [ ] **M7-T20 实现官网发布日期保留期计算**：发布日期当天为第 1 天，第 30 个自然日结束后过期；覆盖时区边界测试。
- [ ] **M7-T21 实现任务、汇总和投递 Repository**：支持认领、心跳、唯一窗口、分批投递和失败恢复。
- [ ] **M7-T22 添加数据库结构和并发测试**：验证所有索引、唯一约束、级联关系、SQLite 兼容和 PostgreSQL 竞争路径。

## 完成条件

- [ ] Alembic 可从当前版本平滑升级，现有业务表与数据不受影响。
- [ ] Repository 覆盖 Web 查询与 Worker 写入所需能力，无路由直接拼装复杂查询。
- [ ] 数据库唯一约束能够兜底任务、来源、附件、汇总和投递幂等。

