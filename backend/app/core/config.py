from pydantic_settings import BaseSettings
from functools import lru_cache
import logging
import os


logger = logging.getLogger("config")

# 项目根目录（backend/app/core/ → 向上 3 级到 LM_SJ/）
_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
_ENV_FILE = os.path.join(_PROJECT_ROOT, ".env")


class Settings(BaseSettings):
    APP_NAME: str = "龙马视界"
    APP_VERSION: str = "0.1.0"
    ENV: str = "dev"

    SECRET_KEY: str = "dev-secret-key-change-in-production-please-use-env-var"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    DB_URL: str = "sqlite:///./database/longma.db"
    STORAGE_PATH: str = "./backend/storage"
    # File storage. Keep local for development; use Supabase Storage in production.
    STORAGE_BACKEND: str = "local"
    SUPABASE_URL: str = ""
    SUPABASE_SERVICE_ROLE_KEY: str = ""
    SUPABASE_STORAGE_BUCKET: str = "longma-files"

    AI_API_KEY: str = ""
    AI_BASE_URL: str = ""
    AI_MODEL: str = "deepseek-v4-flash"
    CHAT_MODEL: str = "deepseek-v4-flash"
    CHAT_MAX_RESERVATION_TOKENS: int = 4096
    WEB_SEARCH_ENABLED: bool = True
    WEB_SEARCH_URL: str = "https://www.bing.com/search"
    WEB_SEARCH_TIMEOUT_SECONDS: int = 15
    WEB_SEARCH_MAX_RESULTS: int = 5

    EMBEDDING_MODEL_NAME: str = "BAAI/bge-small-zh-v1.5"
    EMBEDDING_DEVICE: str = "cpu"
    EMBEDDING_DIM: int = 512
    EMBEDDING_BATCH_SIZE: int = 32
    SKILL_RECOMMEND_LIMIT: int = 5
    SEMANTIC_MIN_SCORE: float = 0.35

    CORS_ORIGINS: str = "*"

    CLASS_NAME: str = "大数据管理与应用25级"
    DEFAULT_QUOTA_MB: int = 500
    ACHIEVEMENT_FILE_MAX_MB: int = 20
    PARTY_MATERIAL_MAX_MB: int = 20
    PARTY_CLASSES: str = "大数据25级,大数据24级,大数据23级,大数据22级"
    PARTY_SIGN_IN_WINDOW_MINUTES: int = 60

    LOGIN_MAX_ATTEMPTS: int = 10
    LOGIN_WINDOW_MINUTES: int = 5

    # 通用 API 限流（滑动窗口）
    API_RATE_LIMIT: int = 120
    API_RATE_WINDOW_MINUTES: int = 1

    # 文件清理：软删除后保留天数，超期物理删除
    FILE_RETENTION_DAYS: int = 7

    PREVIEW_OFFICE_ENABLED: bool = True
    PREVIEW_OFFICE_TIMEOUT_SECONDS: int = 60
    PREVIEW_OFFICE_MAX_MB: int = 20
    PREVIEW_OFFICE_CONCURRENCY: int = 2
    PREVIEW_CACHE_TTL_DAYS: int = 7
    ASSIGNMENT_REMINDER_HOURS: list[int] = [24, 2]

    # MCP 工具接口服务令牌（生产必须通过环境变量覆盖）
    MCP_SERVICE_TOKEN: str = "dev-mcp-token-change-in-production"
    MCP_FETCH_TIMEOUT: int = 10

    class Config:
        env_file = _ENV_FILE
        case_sensitive = True


def _mask_key(value: str, keep: int = 8) -> str:
    """脱敏显示密钥，仅保留前 keep 位"""
    if not value:
        return "(未设置)"
    if len(value) <= keep:
        return "*" * len(value)
    return value[:keep] + "*" * max(4, len(value) - keep)


@lru_cache()
def get_settings() -> Settings:
    s = Settings()

    # --- 配置加载报告 ---
    # 使用 print 作为 fallback，因为此函数可能在日志系统初始化前被调用
    env_exists = os.path.isfile(_ENV_FILE)
    env_size = os.path.getsize(_ENV_FILE) if env_exists else 0

    lines = [
        "",
        "╔══════════════════════════════════════════════════════╗",
        "║  龙马·视界  配置加载报告                              ║",
        "╠══════════════════════════════════════════════════════╣",
        "║  [配置源]",
        f"║    .env 路径:  {_ENV_FILE}",
        f"║    .env 存在:  {env_exists}  ({env_size} bytes)",
        f"║    项目根目录: {_PROJECT_ROOT}",
        f"║    当前工作目录: {os.getcwd()}",
        "║",
        "║  [基本信息]",
        f"║    APP_NAME:       {s.APP_NAME}",
        f"║    APP_VERSION:    {s.APP_VERSION}",
        f"║    ENV:            {s.ENV}",
        f"║    CLASS_NAME:     {s.CLASS_NAME}",
        "║",
        "║  [安全配置]",
        f"║    SECRET_KEY:     {_mask_key(s.SECRET_KEY)}  (len={len(s.SECRET_KEY)})",
        f"║    MCP_TOKEN:      {_mask_key(s.MCP_SERVICE_TOKEN)}  (len={len(s.MCP_SERVICE_TOKEN)})",
        f"║    ACCESS_TOKEN:   {s.ACCESS_TOKEN_EXPIRE_MINUTES} min",
        f"║    REFRESH_TOKEN:  {s.REFRESH_TOKEN_EXPIRE_DAYS} days",
        f"║    LOGIN_MAX:      {s.LOGIN_MAX_ATTEMPTS} 次 / {s.LOGIN_WINDOW_MINUTES} 分钟",
        "║",
        "║  [AI 服务]",
        f"║    AI_API_KEY:     {_mask_key(s.AI_API_KEY)}  (len={len(s.AI_API_KEY)})",
        f"║    AI_BASE_URL:    {s.AI_BASE_URL or '(未设置)'}",
        f"║    AI_MODEL:       {s.AI_MODEL or '(未设置)'}",
        f"║    AI 适配器:      {'GenericAdapter (真实 AI)' if s.AI_API_KEY and s.AI_BASE_URL else 'MockAdapter (模拟)'}",
        "║",
        "║  [数据 & 存储]",
        f"║    DB_URL:         {s.DB_URL}",
        f"║    STORAGE_PATH:   {s.STORAGE_PATH}",
        f"║    FILE_RETENTION: {s.FILE_RETENTION_DAYS} 天",
        f"║    QUOTA:          {s.DEFAULT_QUOTA_MB} MB",
        "║",
        "║  [网络 & 限流]",
        f"║    CORS_ORIGINS:   {s.CORS_ORIGINS}",
        f"║    RATE_LIMIT:     {s.API_RATE_LIMIT} 次 / {s.API_RATE_WINDOW_MINUTES} 分钟",
        "╚══════════════════════════════════════════════════════╝",
    ]
    for line in lines:
        print(line, flush=True)

    return s


settings = get_settings()


def validate_settings():
    errors = []
    if settings.ENV == "prod":
        if settings.SECRET_KEY.startswith("dev-secret-key"):
            errors.append("生产环境必须设置 SECRET_KEY 环境变量")
        if not settings.AI_API_KEY:
            errors.append("生产环境必须设置 AI_API_KEY 环境变量")
        # 生产必须用 PostgreSQL
        if not settings.DB_URL.startswith("postgresql://") and not settings.DB_URL.startswith(
            "postgresql+psycopg2://"
        ):
            errors.append("生产环境 DB_URL 必须为 PostgreSQL (postgresql://)")
        if settings.STORAGE_BACKEND.lower() == "supabase":
            if not settings.SUPABASE_URL or not settings.SUPABASE_SERVICE_ROLE_KEY:
                errors.append("STORAGE_BACKEND=supabase 时必须设置 SUPABASE_URL 和 SUPABASE_SERVICE_ROLE_KEY")
        # 生产禁止 CORS=*
        if settings.CORS_ORIGINS.strip() == "*":
            errors.append("生产环境 CORS_ORIGINS 不能为 *，须指定具体域名")
        if settings.MCP_SERVICE_TOKEN.startswith("dev-mcp-token"):
            errors.append("生产环境必须设置 MCP_SERVICE_TOKEN 环境变量")
    os.makedirs(settings.STORAGE_PATH, exist_ok=True)
    if errors:
        raise RuntimeError("配置校验失败:\n" + "\n".join(errors))
    else:
        logger.info("配置校验通过 (ENV=%s)，数据库目录: %s", settings.ENV, settings.STORAGE_PATH)
