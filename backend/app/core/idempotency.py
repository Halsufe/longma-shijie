"""Idempotency-Key 中间件：写操作防重复提交

对 POST/PUT 请求，若携带 Idempotency-Key header，按 (身份, key) 缓存响应。
重复请求返回缓存响应并加 X-Idempotent-Replay: true。

注意：内存存储，单进程。多 worker 部署需替换为 Redis。
"""
import time
import threading
from collections import OrderedDict

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

_TTL_SECONDS = 24 * 3600
_MAX_ENTRIES = 1000


class _ResponseCache:
    def __init__(self, max_entries: int = _MAX_ENTRIES):
        self._lock = threading.Lock()
        self._store: OrderedDict[str, tuple[float, bytes, int, dict]] = OrderedDict()
        self._max = max_entries

    def get(self, key: str):
        with self._lock:
            item = self._store.get(key)
            if not item:
                return None
            ts, body, status, headers = item
            if time.time() - ts > _TTL_SECONDS:
                self._store.pop(key, None)
                return None
            self._store.move_to_end(key)
            return body, status, headers

    def set(self, key: str, body: bytes, status: int, headers: dict):
        with self._lock:
            self._store[key] = (time.time(), body, status, headers)
            self._store.move_to_end(key)
            while len(self._store) > self._max:
                self._store.popitem(last=False)


_cache = _ResponseCache()


def _identity(request: Request) -> str:
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        from backend.app.core.security import decode_token

        payload = decode_token(auth_header[len("Bearer "):])
        if payload and payload.get("sub"):
            return f"u:{payload['sub']}"
    ip = request.client.host if request.client else "unknown"
    return f"ip:{ip}"


class IdempotencyMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        method = request.method
        key = request.headers.get("Idempotency-Key")

        # 仅对写操作且带 key 的请求处理
        if method not in ("POST", "PUT") or not key:
            return await call_next(request)

        cache_key = f"{_identity(request)}|{key}"
        cached = _cache.get(cache_key)
        if cached:
            body, status, headers = cached
            headers = dict(headers)
            headers["X-Idempotent-Replay"] = "true"
            return Response(content=body, status_code=status, headers=headers)

        response = await call_next(request)

        # 跳过流式响应（SSE），避免缓冲整个事件流
        content_type = response.headers.get("content-type", "")
        if "text/event-stream" in content_type:
            return response

        # 仅缓存成功响应（2xx）
        if 200 <= response.status_code < 300:
            try:
                body_bytes = b""
                async for chunk in response.body_iterator:
                    body_bytes += chunk
                # 重建响应
                headers = {k: v for k, v in response.headers.items()}
                _cache.set(cache_key, body_bytes, response.status_code, headers)
                return Response(content=body_bytes, status_code=response.status_code, headers=headers)
            except Exception:
                pass
        return response
