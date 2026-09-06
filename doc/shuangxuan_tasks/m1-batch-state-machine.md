# M1 批次与状态机任务清单

> 来源：`../shuangxuan_proposal.md` 第 4、7、8 章；`../shuangxuan_high-level-design.md` 第 4.1、5.2、7.4 章  
> 目标：建立双选批次、阶段状态机、单进行中约束、延长与重开能力。  
> 依赖：现有数据库、认证、审计基础设施。  
> 后续模块：M2、M4、M5、M6、M7。

## 最小可执行任务

### 数据与迁移

- [ ] M1-T01 在 `backend/app/models/mentor_selection.py` 定义批次状态枚举，覆盖草稿、主选填报、主选导师选择、主选待发布、主选已发布、补录填报、补录导师选择、补录待发布、补录阻塞、补录已发布、已完成。
- [ ] M1-T02 新增 `MentorSelectionBatch` 模型，落地需求中的全部阶段时间、`version_no`、创建人和软删除字段。
- [ ] M1-T03 为批次增加 nullable unique `active_key`，进行中批次固定写入 `mentor_selection_active`，历史批次清空为 `NULL`。
- [ ] M1-T04 创建 Alembic 迁移并完成空 SQLite 数据库 `upgrade`、`downgrade`、再次 `upgrade` 验证。
- [ ] M1-T05 在 `backend/app/main.py` 注册批次模型，保证内存测试库能够创建新表。

### 领域逻辑

- [ ] M1-T06 新增批次 Pydantic 创建、更新、详情和列表 Schema，禁止客户端直接写 `status`、`active_key` 和统计字段。
- [ ] M1-T07 实现批次时间校验器，校验同一轮“学生开始 < 学生截止 <= 导师开始 < 导师截止 <= 发布时间”以及补录不得早于主选发布。
- [ ] M1-T08 实现 `BatchStateMachine`，集中定义允许的状态迁移并拒绝跳阶段、回退和非法完成。
- [ ] M1-T09 实现 `MentorSelectionRepository` 的批次创建、按 ID 查询、分页查询、带版本更新和行锁查询。
- [ ] M1-T10 实现 `BatchService.create/update`，在事务中维护 `active_key` 并把版本冲突映射为 `MENTOR_SELECTION_VERSION_CONFLICT`。
- [ ] M1-T11 实现 `BatchService.extend`，只允许延长未结束阶段，不允许把新截止时间设置到当前时间之前。
- [ ] M1-T12 实现重开学生阶段：作废有效结果，全部参与学生需要重新正式提交，并写入新阶段时间。
- [ ] M1-T13 实现重开导师阶段：保留学生最近正式志愿，作废导师决定和匹配结果，全部参与导师重新选择。
- [ ] M1-T14 新增管理员批次创建、列表、详情、更新、延长和重开接口，并注册 `/api/v1/mentor-selection` 路由。

### 验证

- [ ] M1-T15 添加状态机和时间顺序单元测试，覆盖所有合法迁移及至少一个非法迁移用例。
- [ ] M1-T16 添加单进行中批次、乐观锁、延长、两种重开方式的集成测试，全部使用内存数据库。

## 模块完成定义

- [ ] M1-DO1 迁移可逆，持久数据库未被测试命令修改。
- [ ] M1-DO2 批次状态只能通过领域服务改变，同一时间不能存在两个进行中批次。
- [ ] M1-DO3 M1 专项测试、`ruff check backend` 和 `mypy backend` 通过。

