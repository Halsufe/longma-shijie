# 龙马·视界 后端镜像
# 注意：本部署配置为产物，未在本环境运行时验证。
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# 系统依赖：libpq 供 psycopg2，libsqlite3 供 SQLite 兜底
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 gcc libpq-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 先装依赖（利用层缓存）
COPY requirements.txt ./
RUN pip install -r requirements.txt

# 拷贝源码
COPY . /app/

# 存储目录
RUN mkdir -p /app/backend/storage

EXPOSE 8000

# 启动前执行迁移，再起服务
CMD ["sh", "-c", "alembic upgrade head && uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --workers 4"]
