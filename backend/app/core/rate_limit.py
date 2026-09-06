"""通用 API 限流中间件（滑动窗口，内存存储）"""
import time
import threading
from collections import defaultdict

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from backend.app.core.config import settings


class _SlidingWindowLimiter:
    def __init__(self):
        self._lock = threading.Lock()
        self._hits: dict[str, list[float]] = defaultdict(list)

    def allow(self, key: str, max_requests: int, window_seconds: int) -> bool:
        now = time.time()
        window_start = now - window_seconds
        with self._lock:
            hits = [t for t in self._hits[key] if t > window_start]
            if len(hits) >= max_requests:
                self._hits[key] = hits
                return False
            hits.append(now)
            self._hits[key] = hits
            return True


_limiter = _SlidingWindowLimiter()

# 限流豁免路径（健康检查、文档）
_EXEMPT_PREFIXES = ("/docs", "/redoc", "/openapi.json", "/health")


class RateLimitMiddleware(BaseHTTPMiddleware):
    """按 user_id（已登录）或 IP 限流，超限返回 429"""

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if path in _EXEMPT_PREFIXES or path.startswith(_EXEMPT_PREFIXES):
            return await call_next(request)

        # 解析身份：优先 user_id（从 JWT），退化为 IP
        identity = request.client.host if request.client else "unknown"
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            from backend.app.core.security import decode_token

            payload = decode_token(auth_header[len("Bearer "):])
            if payload and payload.get("sub"):
                identity = f"u:{payload['sub']}"

        max_req = settings.API_RATE_LIMIT
        window = settings.API_RATE_WINDOW_MINUTES * 60

        if not _limiter.allow(identity, max_req, window):
            return JSONResponse(
                status_code=429,
                content={"error": {"code": "RATE_LIMITED", "message": "请求过于频繁，请稍后再试"}, "request_id": getattr(request.state, "request_id", "")},
            )

        return await call_next(request)
