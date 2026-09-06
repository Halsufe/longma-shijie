from fastapi import Depends, Request
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.core.security import decode_token
from backend.app.core.errors import AppException
from backend.app.models.user import User


def _resolve_user(request: Request, db: Session) -> User:
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise AppException("AUTH_REQUIRED", "请先登录", 401)

    token = auth_header[len("Bearer "):]
    payload = decode_token(token)
    if not payload:
        raise AppException("AUTH_INVALID", "登录已过期，请重新登录", 401)

    # access token 必须带 type=access；refresh token 不可用于业务接口
    token_type = payload.get("type")
    if token_type != "access":
        raise AppException("AUTH_INVALID", "凭证类型错误，请使用 access token", 401)

    subject = payload.get("sub")
    if not subject:
        raise AppException("AUTH_INVALID", "登录凭证无效", 401)

    try:
        user_id = int(subject)
    except (ValueError, TypeError):
        raise AppException("AUTH_INVALID", "登录凭证无效", 401)

    user = db.query(User).filter(User.id == user_id, User.deleted_at.is_(None)).first()
    if not user:
        raise AppException("AUTH_INVALID", "用户不存在", 401)

    if user.status == "disabled":
        raise AppException("ACCOUNT_DISABLED", "账号已被禁用", 403)

    # 若 access token 绑定会话（带 jti），校验会话未撤销 —— 使登出/撤销会话立即生效
    jti = payload.get("jti")
    if jti:
        from backend.app.repositories.session_repo import SessionRepository

        session = SessionRepository.get_by_jti(db, jti)
        if not session or session.revoked_at is not None:
            raise AppException("AUTH_INVALID", "会话已失效，请重新登录", 401)

    # 暴露 token 信息供 logout 等使用
    request.state.token_jti = jti
    request.state.token_type = token_type
    return user


def get_current_user(request: Request, db: Session = Depends(get_db)):
    user = _resolve_user(request, db)
    if user.status == "pending_change":
        raise AppException("PASSWORD_CHANGE_REQUIRED", "请先修改初始密码", 403)
    return user


def get_current_user_allow_pending(request: Request, db: Session = Depends(get_db)):
    return _resolve_user(request, db)


def require_admin(current_user=Depends(get_current_user)):
    if not current_user.is_admin:
        raise AppException("FORBIDDEN", "需要管理员权限", 403)
    return current_user


def require_teacher_or_admin(current_user=Depends(get_current_user)):
    if not (current_user.is_teacher or current_user.is_admin):
        raise AppException("FORBIDDEN", "需要教师或管理员权限", 403)
    return current_user


def require_student_or_alumni(current_user=Depends(get_current_user)):
    if not (current_user.is_student or current_user.is_alumni):
        raise AppException("FORBIDDEN", "需要学生或校友权限", 403)
    return current_user


def require_party_member(current_user=Depends(get_current_user)):
    """Allow active student party profiles only.

    Alumni and staff cannot retain access merely by carrying stale party JSON.
    """
    valid_party_types = {"正式党员", "预备党员", "入党积极分子"}
    party = current_user.party
    if (
        not current_user.is_student
        or party.get("party_type") not in valid_party_types
        or party.get("deleted_at")
    ):
        raise AppException("PARTY_MEMBER_REQUIRED", "需要有效的学生党员身份", 403)
    return current_user
