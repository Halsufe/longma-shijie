import hashlib
import random
import string
import logging

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.core.config import settings
from backend.app.core.security import (
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_refresh_token,
)
from backend.app.core.errors import AppException
from backend.app.repositories.user_repo import UserRepository
from backend.app.repositories.session_repo import SessionRepository
from backend.app.schemas.user import UserLogin, UserLoginResponse, ChangePassword
from backend.app.schemas.session import RefreshRequest, RefreshResponse
from backend.app.api.deps import get_current_user, get_current_user_allow_pending

logger = logging.getLogger(__name__)
router = APIRouter()

_attempt_cache: dict[str, list[float]] = {}

import time


def _check_rate_limit(key: str, max_attempts: int = 10, window_minutes: int = 5) -> bool:
    now = time.time()
    window_start = now - (window_minutes * 60)
    if key not in _attempt_cache:
        _attempt_cache[key] = []
    _attempt_cache[key] = [t for t in _attempt_cache[key] if t > window_start]
    if len(_attempt_cache[key]) >= max_attempts:
        return False
    _attempt_cache[key].append(now)
    return True


def _generate_temp_password(length: int = 10) -> str:
    chars = string.ascii_letters + string.digits
    return "".join(random.choice(chars) for _ in range(length))


def _device_fingerprint(user_agent: str, ip: str) -> str:
    raw = f"{user_agent}|{ip}"
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


def _truncate_ua(user_agent: str) -> str:
    return (user_agent or "")[:255]


@router.post("/login", response_model=UserLoginResponse)
async def login(form: UserLogin, request: Request, db: Session = Depends(get_db)):
    ip = request.client.host if request.client else "unknown"
    rate_key = f"login:{form.student_no}:{ip}"

    if not _check_rate_limit(rate_key):
        raise AppException("RATE_LIMITED", "登录尝试过于频繁，请稍后再试", 429)

    user = UserRepository.get_by_student_no(db, form.student_no)
    if not user or not verify_password(form.password, user.password_hash):
        logger.warning("Login failed: student_no=%s ip=%s", form.student_no, ip)
        raise AppException("AUTH_INVALID", "学号或密码错误", 401)

    if user.status == "disabled":
        raise AppException("ACCOUNT_DISABLED", "账号已被禁用", 403)

    UserRepository.update_last_active(db, user)

    # 签发 access + refresh（共享 jti，绑定同一会话）
    refresh_token, jti, expires_at = create_refresh_token(subject=str(user.id))
    access_token = create_access_token(subject=str(user.id), jti=jti)

    ua = _truncate_ua(request.headers.get("user-agent", ""))
    device_id = _device_fingerprint(ua, ip)
    SessionRepository.create(
        db,
        user_id=user.id,
        device_id=device_id,
        jti=jti,
        refresh_token_hash=hash_refresh_token(refresh_token),
        expires_at=expires_at,
        device_name=ua or None,
        ip=ip,
        user_agent=ua or None,
    )

    logger.info("Login success: user_id=%s ip=%s", user.id, ip)

    return UserLoginResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user={
            "id": user.id,
            "student_no": user.student_no,
            "name": user.name,
            "role": user.role,
            "status": user.status,
        },
    )


@router.post("/logout")
async def logout(
    request: Request,
    current_user=Depends(get_current_user_allow_pending),
    db: Session = Depends(get_db),
):
    jti = getattr(request.state, "token_jti", None)
    if jti:
        SessionRepository.revoke_by_jti(db, jti)
    logger.info("Logout: user_id=%s", current_user.id)
    return {"message": "登出成功"}


@router.post("/refresh", response_model=RefreshResponse)
async def refresh(form: RefreshRequest, db: Session = Depends(get_db)):
    payload = decode_token(form.refresh_token)
    if not payload or payload.get("type") != "refresh":
        raise AppException("AUTH_INVALID", "refresh token 无效", 401)

    jti = payload.get("jti")
    subject = payload.get("sub")
    if not jti or not subject:
        raise AppException("AUTH_INVALID", "refresh token 无效", 401)

    session = SessionRepository.get_by_jti(db, jti)
    if not session or session.revoked_at is not None:
        raise AppException("AUTH_INVALID", "会话已撤销，请重新登录", 401)

    from datetime import datetime, timezone

    # SQLite 读回的 datetime 可能无 tzinfo，统一按 UTC 处理后再比较
    exp = session.expires_at
    if exp.tzinfo is None:
        exp = exp.replace(tzinfo=timezone.utc)
    if exp < datetime.now(timezone.utc):
        raise AppException("AUTH_INVALID", "refresh token 已过期，请重新登录", 401)

    # 校验 refresh token 哈希匹配（防伪造）
    if session.refresh_token_hash != hash_refresh_token(form.refresh_token):
        raise AppException("AUTH_INVALID", "refresh token 校验失败", 401)

    SessionRepository.touch_active(db, session)

    # 旋转 refresh token（发新 jti，撤销旧会话）
    new_refresh, new_jti, new_expires = create_refresh_token(subject=subject)
    new_access = create_access_token(subject=subject, jti=new_jti)
    SessionRepository.revoke(db, session)
    SessionRepository.create(
        db,
        user_id=session.user_id,
        device_id=session.device_id,
        jti=new_jti,
        refresh_token_hash=hash_refresh_token(new_refresh),
        expires_at=new_expires,
        device_name=session.device_name,
        ip=session.ip,
        user_agent=session.user_agent,
    )

    return RefreshResponse(access_token=new_access, refresh_token=new_refresh)


@router.post("/change-password")
async def change_password(
    form: ChangePassword,
    request: Request,
    current_user=Depends(get_current_user_allow_pending),
    db: Session = Depends(get_db),
):
    if not verify_password(form.old_password, current_user.password_hash):
        raise AppException("PASSWORD_INVALID", "旧密码错误", 401)

    if form.new_password == form.old_password:
        raise AppException("PASSWORD_SAME", "新密码不能与旧密码相同", 400)

    UserRepository.update(
        db,
        current_user,
        password_hash=hash_password(form.new_password),
        status="active",
    )
    # 改密后撤销除当前会话外所有会话
    current_jti = getattr(request.state, "token_jti", None)
    SessionRepository.revoke_all_except(db, current_user.id, except_jti=current_jti)
    logger.info("Password changed: user_id=%s", current_user.id)
    return {"message": "密码修改成功"}
