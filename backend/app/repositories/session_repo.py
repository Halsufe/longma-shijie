from datetime import datetime, timezone
from typing import Optional, List

from sqlalchemy.orm import Session

from backend.app.models.user_session import UserSession
from backend.app.core.database import local_now


class SessionRepository:
    @staticmethod
    def create(
        db: Session,
        user_id: int,
        device_id: str,
        jti: str,
        refresh_token_hash: str,
        expires_at: datetime,
        device_name: Optional[str] = None,
        ip: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> UserSession:
        s = UserSession(
            user_id=user_id,
            device_id=device_id,
            device_name=device_name,
            ip=ip,
            user_agent=user_agent,
            jti=jti,
            refresh_token_hash=refresh_token_hash,
            expires_at=expires_at,
        )
        db.add(s)
        db.commit()
        db.refresh(s)
        return s

    @staticmethod
    def get_by_jti(db: Session, jti: str) -> Optional[UserSession]:
        return db.query(UserSession).filter(UserSession.jti == jti).first()

    @staticmethod
    def get_by_id(db: Session, session_id: int, user_id: int) -> Optional[UserSession]:
        return (
            db.query(UserSession)
            .filter(UserSession.id == session_id, UserSession.user_id == user_id)
            .first()
        )

    @staticmethod
    def list_active_by_user(db: Session, user_id: int) -> List[UserSession]:
        return (
            db.query(UserSession)
            .filter(
                UserSession.user_id == user_id,
                UserSession.revoked_at.is_(None),
                UserSession.expires_at > local_now(),
            )
            .order_by(UserSession.last_active_at.desc())
            .all()
        )

    @staticmethod
    def revoke(db: Session, session: UserSession) -> UserSession:
        session.revoked_at = local_now()
        db.commit()
        db.refresh(session)
        return session

    @staticmethod
    def revoke_by_jti(db: Session, jti: str) -> bool:
        s = SessionRepository.get_by_jti(db, jti)
        if not s or s.revoked_at is not None:
            return False
        SessionRepository.revoke(db, s)
        return True

    @staticmethod
    def revoke_all_except(db: Session, user_id: int, except_jti: Optional[str] = None) -> int:
        """撤销该用户所有会话（除指定 jti 外），返回撤销数"""
        now = local_now()
        sessions = (
            db.query(UserSession)
            .filter(
                UserSession.user_id == user_id,
                UserSession.revoked_at.is_(None),
            )
            .all()
        )
        count = 0
        for s in sessions:
            if except_jti and s.jti == except_jti:
                continue
            s.revoked_at = now
            count += 1
        db.commit()
        return count

    @staticmethod
    def touch_active(db: Session, session: UserSession) -> None:
        session.last_active_at = local_now()
        db.commit()
