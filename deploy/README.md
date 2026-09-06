# 龙马·视界 部署指南

> 本部署配置为产物，未在本环境运行时验证。请在目标服务器上首次部署时完整测试。

## 架构

```
nginx:80 ──> app:8000 (uvicorn x4 workers) ──> postgres:5432
                     └── storage 卷（知识库文件）
```

- **app**：FastAPI 后端，启动前自动 `alembic upgrade head` 建表/迁移。
- **db**：PostgreSQL 16，数据持久化到 `pgdata` 卷。
- **nginx**：反向代理，关键配置 `proxy_buffering off` 支持 SSE 流式对话。

## 前置准备

1. 安装 Docker + Docker Compose。
2. 准备 AI 模型 API Key（OpenAI 兼容接口）。

## 部署步骤

```bash
cd LM_SJ/deploy

# 1. 复制环境变量模板并填写
cp .env.example .env
#   必改项：SECRET_KEY、AI_API_KEY、CORS_ORIGINS、MCP_SERVICE_TOKEN、POSTGRES_PASSWORD

# 2. 构建并启动
docker compose --env-file .env up -d --build

# 3. 验证
curl http://localhost/health
# 期望：{"status":"ok","app":"龙马视界",...}

# 4. 查看日志
docker compose logs -f app
```

## 数据库迁移

- 容器启动时自动执行 `alembic upgrade head`。
- 手动迁移：`docker compose exec app alembic upgrade head`
- 回滚：`docker compose exec app alembic downgrade -1`

## 生产安全检查清单

- [x] `ENV=prod` 启动时 `validate_settings` 强制校验：
  - `SECRET_KEY` 非 dev 默认
  - `DB_URL` 为 PostgreSQL
  - `CORS_ORIGINS` 不为 `*`
  - `MCP_SERVICE_TOKEN` 非 dev 默认
  - `AI_API_KEY` 非空
- [ ] HTTPS：在 nginx 配置 TLS 或前置云负载均衡
- [ ] 定期备份 PostgreSQL 卷
- [ ] 监控存储用量（`GET /api/v1/admin/storage`）

## 注意事项

- **限流/幂等/登录限流** 为单进程内存实现，`--workers 4` 下各 worker 独立计数。生产高并发需换 Redis 后端。
- **文件清理 worker** 每小时扫描软删除超 `FILE_RETENTION_DAYS` 的文件并物理删除。
- **SSE 流式**：nginx 必须 `proxy_buffering off`，否则对话流会被缓冲。
