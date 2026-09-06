# M3 语义向量服务（Semantic Vector Service）

> 输入文档：`../../skills_proposal.md`（第 3.6、8、11 章）、`../../skills_design.md`（4.3、5.1、5.4）  
> 前置依赖：无（M4/M5 消费其接口）  
> 完成定义：向量可生成、持久化、刷新与检索；模型不可用时自动回退关键词推荐。

## 任务清单

- [x] T3-1 配置项
  - 交付物：`backend/app/core/config.py` 新增 `EMBEDDING_MODEL_NAME`、`EMBEDDING_DEVICE`、`EMBEDDING_DIM`、`SKILL_RECOMMEND_LIMIT`、`SEMANTIC_MIN_SCORE`、`EMBEDDING_BATCH_SIZE`。
  - 验收：默认值与设计 5.4 一致，`.env` 可覆盖。
- [x] T3-2 SkillEmbedding 模型与迁移
  - 交付物：`backend/app/models/skill_embedding.py`；Alembic 迁移 `j1234f5a6b7c_add_skill_embeddings.py`；`backend/app/main.py` 导入模型。
  - 验收：SQLite/PostgreSQL 均可建表；唯一索引 `(entity_type, entity_id)` 生效。
- [x] T3-3 SkillEmbeddingRepository
  - 交付物：`backend/app/repositories/skill_embedding_repo.py` 实现 upsert、按类型检索、按实体删除、按更新时间增量查询。
  - 验收：新增覆盖旧向量、删除后不再返回。
- [x] T3-4 SemanticService
  - 交付物：`backend/app/services/semantic_service.py` 实现模型懒加载、文本向量化、归一化、余弦相似度、综合得分与阈值过滤。
  - 验收：`score = 0.7 × cosine + 0.2 × keyword + 0.1 × popularity`；低于 `SEMANTIC_MIN_SCORE` 被剔除。
- [x] T3-5 关键词回退
  - 交付物：`SemanticService` 在模型不可用、向量缺失或全部低于阈值时调用 `RecommendationService` 回退。
  - 验收：模拟模型失败时接口仍返回非空推荐，不抛异常。
- [x] T3-6 增量刷新钩子
  - 交付物：资源审核通过/更新/软删除、教师方向 CRUD、教师资料更新时同步刷新 `skill_embeddings`。
  - 验收：数据变更后新向量可检索，旧向量被覆盖或删除。
- [x] T3-7 测试
  - 交付物：`backend/tests/test_semantic_service.py`。
  - 验收：embedding、相似度、阈值、回退、刷新断言全部通过。
