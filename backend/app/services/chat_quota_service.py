from __future__ import annotations

from datetime import datetime

from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.app.core.database import local_now
from backend.app.models.token_quota import (
    ChatTokenUsageEvent,
    TokenQuotaAuditLog,
    TokenQuotaPolicy,
    UserDailyTokenUsage,
    UserTokenQuotaOverride,
)
from backend.app.services.token_quota_service import next_reset, usage_date


VALID_QUOTA_ROLES = frozenset({"admin", "teacher", "student", "alumni"})


class ChatQuotaService:
    @staticmethod
    def effective_quota(db: Session, user) -> int:
        now = local_now()
        override = (
            db.query(UserTokenQuotaOverride)
            .filter(UserTokenQuotaOverride.user_id == user.id, UserTokenQuotaOverride.valid_from <= now)
            .order_by(UserTokenQuotaOverride.id.desc())
            .first()
        )
        if override and (override.valid_until is None or override.valid_until >= now):
            return max(0, override.daily_limit)
        policy = db.query(TokenQuotaPolicy).filter(TokenQuotaPolicy.role == user.role, TokenQuotaPolicy.enabled.is_(True)).first()
        return max(0, policy.daily_limit) if policy else 0

    @classmethod
    def daily_usage(cls, db: Session, user) -> UserDailyTokenUsage:
        day = usage_date()
        row = db.query(UserDailyTokenUsage).filter(
            UserDailyTokenUsage.user_id == user.id, UserDailyTokenUsage.usage_date == day
        ).first()
        quota = cls.effective_quota(db, user)
        if row is None:
            row = UserDailyTokenUsage(user_id=user.id, usage_date=day, quota_snapshot=quota)
            db.add(row)
            db.commit()
            db.refresh(row)
        elif row.quota_snapshot != quota:
            row.quota_snapshot = quota
            row.version += 1
            db.commit()
            db.refresh(row)
        return row

    @classmethod
    def usage_summary(cls, db: Session, user) -> dict:
        row = cls.daily_usage(db, user)
        remaining = max(0, row.quota_snapshot - row.total_tokens - row.reserved_tokens)
        return {
            "usage_date": row.usage_date,
            "model": "deepseek-v4-flash",
            "quota": row.quota_snapshot,
            "input_tokens": row.input_tokens,
            "output_tokens": row.output_tokens,
            "used_tokens": row.total_tokens,
            "reserved_tokens": row.reserved_tokens,
            "remaining_tokens": remaining,
            "pending_reconciliation": row.pending_reconciliation,
            "reset_at": next_reset(),
        }

    @classmethod
    def reserve_request(cls, db: Session, user, *, request_id: str, reservation: int, idempotency_key: str) -> UserDailyTokenUsage:
        row = cls.daily_usage(db, user)
        amount = max(0, int(reservation))
        existing = db.query(ChatTokenUsageEvent).filter(
            ChatTokenUsageEvent.idempotency_key == idempotency_key
        ).first()
        if existing is not None:
            db.refresh(row)
            return row

        # Keep the quota gate in one conditional UPDATE so concurrent requests
        # cannot both pass a Python-side check against the same ledger row.
        result = db.execute(
            update(UserDailyTokenUsage)
            .where(
                UserDailyTokenUsage.id == row.id,
                UserDailyTokenUsage.total_tokens + UserDailyTokenUsage.reserved_tokens + amount
                <= UserDailyTokenUsage.quota_snapshot,
            )
            .values(
                reserved_tokens=UserDailyTokenUsage.reserved_tokens + amount,
                version=UserDailyTokenUsage.version + 1,
            )
        )
        if result.rowcount != 1:
            db.rollback()
            raise ValueError("TOKEN_QUOTA_EXCEEDED")
        db.add(ChatTokenUsageEvent(
            request_id=request_id, user_id=user.id, attempt_no=1,
            idempotency_key=idempotency_key, status="reserved", reserved_tokens=amount,
        ))
        try:
            db.commit()
        except IntegrityError:
            # A concurrent caller won the unique idempotency race.  Roll back
            # this transaction so its conditional update is not counted twice.
            db.rollback()
            existing = db.query(ChatTokenUsageEvent).filter(
                ChatTokenUsageEvent.idempotency_key == idempotency_key
            ).first()
            if existing is None:
                raise
        db.refresh(row)
        return row

    @classmethod
    def settle_request(
        cls, db: Session, user, *, request_id: str, reservation: int,
        input_tokens: int | None, output_tokens: int | None, idempotency_key: str,
        attempt_no: int = 1,
    ) -> ChatTokenUsageEvent:
        event = db.query(ChatTokenUsageEvent).filter(ChatTokenUsageEvent.idempotency_key == idempotency_key).first()
        if event is None:
            event = ChatTokenUsageEvent(
                request_id=request_id, user_id=user.id, attempt_no=attempt_no,
                idempotency_key=idempotency_key,
            )
            db.add(event)
        elif event.status != "reserved":
            # Repeated callbacks are read-only; pending events are completed by
            # the explicit reconciliation path.
            return event
        row = cls.daily_usage(db, user)
        row.reserved_tokens = max(0, row.reserved_tokens - max(0, int(reservation)))
        event.input_tokens, event.output_tokens = input_tokens, output_tokens
        if input_tokens is None or output_tokens is None:
            event.status = "pending_reconciliation"
            row.pending_reconciliation += max(0, int(reservation))
        else:
            event.total_tokens = max(0, int(input_tokens)) + max(0, int(output_tokens))
            event.status = "settled"
            row.input_tokens += max(0, int(input_tokens))
            row.output_tokens += max(0, int(output_tokens))
            row.total_tokens += event.total_tokens
        db.commit()
        db.refresh(event)
        return event

    @staticmethod
    def record_unmetered_attempt(
        db: Session, user, *, request_id: str, attempt_no: int, idempotency_key: str,
        error_code: str = "USAGE_UNAVAILABLE",
    ) -> ChatTokenUsageEvent:
        event = db.query(ChatTokenUsageEvent).filter(
            ChatTokenUsageEvent.idempotency_key == idempotency_key
        ).first()
        if event is not None:
            return event
        event = ChatTokenUsageEvent(
            request_id=request_id, user_id=user.id, attempt_no=attempt_no,
            idempotency_key=idempotency_key, status="pending_reconciliation",
            reserved_tokens=0, error_code=error_code,
        )
        db.add(event)
        db.commit()
        db.refresh(event)
        return event

    @staticmethod
    def update_policy(db: Session, *, role: str, daily_limit: int, changed_by: int, reason: str) -> TokenQuotaPolicy:
        if role not in VALID_QUOTA_ROLES:
            raise ValueError("INVALID_QUOTA_ROLE")
        if daily_limit < 0:
            raise ValueError("INVALID_QUOTA_LIMIT")
        row = db.query(TokenQuotaPolicy).filter(TokenQuotaPolicy.role == role).first()
        old_limit = row.daily_limit if row else None
        if row is None:
            row = TokenQuotaPolicy(role=role, daily_limit=daily_limit)
            db.add(row)
        else:
            row.daily_limit = daily_limit
            row.version += 1
        db.add(TokenQuotaAuditLog(role=role, old_limit=old_limit, new_limit=daily_limit, changed_by=changed_by, reason=reason))
        db.commit()
        db.refresh(row)
        return row

    @staticmethod
    def set_override(
        db: Session, *, user_id: int, daily_limit: int, changed_by: int, reason: str, valid_until: datetime | None = None
    ) -> UserTokenQuotaOverride:
        if daily_limit < 0:
            raise ValueError("INVALID_QUOTA_LIMIT")
        current = db.query(UserTokenQuotaOverride).filter(UserTokenQuotaOverride.user_id == user_id).order_by(UserTokenQuotaOverride.id.desc()).first()
        row = UserTokenQuotaOverride(
            user_id=user_id, daily_limit=daily_limit, valid_until=valid_until,
            reason=reason, updated_by=changed_by,
        )
        db.add(row)
        db.add(TokenQuotaAuditLog(
            target_user_id=user_id, old_limit=current.daily_limit if current else None,
            new_limit=daily_limit, changed_by=changed_by, reason=reason,
        ))
        db.commit()
        db.refresh(row)
        return row

    @staticmethod
    def pending_events(db: Session, *, page: int = 1, page_size: int = 50) -> tuple[list[ChatTokenUsageEvent], int]:
        query = db.query(ChatTokenUsageEvent).filter(ChatTokenUsageEvent.status == "pending_reconciliation")
        total = query.count()
        rows = query.order_by(ChatTokenUsageEvent.id.asc()).offset((max(1, page) - 1) * page_size).limit(min(100, page_size)).all()
        return rows, total

    @staticmethod
    def reconcile_event(db: Session, event_id: int, *, input_tokens: int, output_tokens: int) -> ChatTokenUsageEvent:
        if input_tokens < 0 or output_tokens < 0:
            raise ValueError("INVALID_USAGE")
        event = db.query(ChatTokenUsageEvent).filter(ChatTokenUsageEvent.id == event_id).first()
        if event is None:
            raise ValueError("USAGE_EVENT_NOT_FOUND")
        if event.status == "settled":
            return event
        row = db.query(UserDailyTokenUsage).filter(
            UserDailyTokenUsage.user_id == event.user_id,
            UserDailyTokenUsage.usage_date == usage_date(event.created_at),
        ).first()
        if row is None:
            raise ValueError("USAGE_LEDGER_NOT_FOUND")
        event.input_tokens = input_tokens
        event.output_tokens = output_tokens
        event.total_tokens = input_tokens + output_tokens
        event.status = "settled"
        row.input_tokens += input_tokens
        row.output_tokens += output_tokens
        row.total_tokens += event.total_tokens
        row.pending_reconciliation = max(0, row.pending_reconciliation - event.reserved_tokens)
        db.commit()
        db.refresh(event)
        return event
