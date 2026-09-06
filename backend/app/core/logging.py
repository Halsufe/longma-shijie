import logging
import re
import sys


# 敏感字段名（不区分大小写）
_SENSITIVE_KEYS = (
    "password",
    "passwd",
    "token",
    "accesstoken",
    "refreshtoken",
    "secret",
    "api_key",
    "apikey",
    "authorization",
    "auth",
    "cookie",
)

# 匹配 key=value 或 key: value 形式中的敏感值
_KV_PATTERN = re.compile(
    r"(?i)(\"?(?:" + "|".join(_SENSITIVE_KEYS) + r")\"?\s*[:=]\s*)"
    r"(\"?[^\s,;}\]\"']+\"?)",
)

# 匹配 Bearer token（包含 JWT 的 base64url 字符：A-Za-z0-9-_. 以及 +/=）
_BEARER_PATTERN = re.compile(r"(?i)(bearer\s+)([A-Za-z0-9._\-+/=]+)")


def sanitize_text(text: str) -> str:
    if not text:
        return text
    # 先脱敏 Bearer token，避免 KV 模式把 "Bearer" 当作 authorization 的值先行替换
    text = _BEARER_PATTERN.sub(lambda m: m.group(1) + "***", text)
    text = _KV_PATTERN.sub(lambda m: m.group(1) + "***", text)
    return text


class SanitizingFilter(logging.Filter):
    """对日志消息做敏感字段脱敏：password/token/secret/key/authorization → ***"""

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            msg = record.getMessage()
        except Exception:
            return True
        sanitized = sanitize_text(msg)
        if sanitized != msg:
            # 替换 record.msg 以使 format() 输出脱敏后的文本
            record.msg = sanitized
            record.args = None
        return True


def setup_logging(level: str = "INFO"):
    log_format = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(log_format))
    handler.addFilter(SanitizingFilter())

    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    root_logger.handlers.clear()
    root_logger.addHandler(handler)

    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
