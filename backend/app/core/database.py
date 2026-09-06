from datetime import datetime, timezone, timedelta

from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from sqlalchemy.pool import StaticPool

from backend.app.core.config import settings


# 中国标准时区 UTC+8
CST = timezone(timedelta(hours=8))


def local_now() -> datetime:
    """返回当前本地时间（UTC+8，带时区信息）。

    用于数据库字段的默认值，替代 datetime.now(timezone.utc)，
    确保存储和显示的时间都是本地时间。

    注意：JWT 令牌相关的过期时间仍应使用 datetime.now(timezone.utc)，
    因为 JWT 标准要求使用 UTC 时间。
    """
    return datetime.now(CST)


connect_args = {}
engine_kwargs = {}

if settings.DB_URL.startswith("sqlite"):
    connect_args["check_same_thread"] = False
    if make_url(settings.DB_URL).database in (None, "", ":memory:"):
        engine_kwargs["poolclass"] = StaticPool

engine = create_engine(
    settings.DB_URL,
    connect_args=connect_args,
    future=True,
    **engine_kwargs,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, future=True)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
