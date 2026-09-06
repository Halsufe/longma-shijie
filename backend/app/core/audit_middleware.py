import logging
import re
from typing import Optional

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

from backend.app.core.security import decode_token
from backend.app.repositories.audit_repo import AuditRepository
from backend.app.repositories.user_repo import UserRepository
from backend.app.core import database as db_mod

logger = logging.getLogger(__name__)

WRITE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}

# 路径前缀 → target_type 映射
PATH_TARGET_MAP = [
    (r"/api/v1/admin/users", "user"),
    (r"/api/v1/admin/skills", "skill"),
    (r"/api/v1/class-knowledge/files", "class_file"),
    (r"/api/v1/knowledge/files", "file"),
    (r"/api/v1/courses", "course"),
    (r"/api/v1/assignments", "assignment"),
    (r"/api/v1/submissions", "submission"),
    (r"/api/v1/chat/sessions", "chat_session"),
]

# 路径 → action 映射（特殊处理）
ACTION_OVERRIDES = {
    "/api/v1/auth/login": "login",
    "/api/v1/auth/logout": "logout",
    "/api/v1/auth/change-password": "change_password",
}


def _resolve_target_type(path: str) -> Optional[str]:
    for pattern, ttype in PATH_TARGET_MAP:
        if path.startswith(pattern):
            return ttype
    return None


def _resolve_action(method: str, path: str) -> str:
    if path in ACTION_OVERRIDES:
        return ACTION_OVERRIDES[path]
    return {
        "POST": "create",
        "PUT": "update",
        "PATCH": "update",
        "DELETE": "delete",
    }.get(method, method.lower())


def _extract_target_id(path: str) -> Optional[str]:
    """从路径中提取末尾的数字 ID"""
    m = re.search(r"/(\d+)(?:/|$)", path)
    return m.group(1) if m else None


def _get_operator(request: Request) -> tuple[Optional[int], Optional[str]]:
    """从 Authorization 头解析操作者（best-effort，失败返回 None）"""
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return None, None
    payload = decode_token(auth[len("Bearer "):])
    if not payload:
        return None, None
    try:
        uid = int(payload.get("sub", 0))
    except (ValueError, TypeError):
        return None, None
    if not uid:
        return None, None
    # 查用户名（低频，可接受）
    db = db_mod.SessionLocal()
    try:
        user = UserRepository.get_by_id(db, uid)
        return uid, user.name if user else None
    finally:
        db.close()


class AuditMiddleware(BaseHTTPMiddleware):
    """审计日志中间件：仅记录写操作，不存密码/Token/Key"""

    SKIP_PATHS = {"/api/v1/auth/refresh", "/api/v1/auth/login"}

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)

        method = request.method
        path = request.url.path

        # 仅记录写操作 + /api/v1 路径
        if method not in WRITE_METHODS or not path.startswith("/api/v1"):
            return response

        # login 特殊处理（记录登录尝试），其它写操作正常记录
        # 不记录请求体（含密码），仅记录元信息
        try:
            operator_id, operator_name = _get_operator(request)
            # login 时还没有有效 token，operator 为 None 是正常的
            result = "success" if response.status_code < 400 else "failed"

            AuditRepository.create(
                db=db_mod.SessionLocal(),
                operator_id=operator_id,
                operator_name=operator_name,
                action=_resolve_action(method, path),
                target_type=_resolve_target_type(path),
                target_id=_extract_target_id(path),
                result=result,
                ip=request.client.host if request.client else None,
                user_agent=request.headers.get("user-agent", "")[:255],
                detail=None,  # 不记录请求体，避免泄露密码/Token
            )
        except Exception as e:
            logger.warning("Audit log failed: %s", e)

        return response
