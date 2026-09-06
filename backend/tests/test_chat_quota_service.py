from datetime import date
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from backend.app.core.database import Base
from backend.app.models.token_quota import TokenQuotaPolicy
from backend.app.models.user import User
from backend.app.services.chat_quota_service import ChatQuotaService


def _db() -> Session:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    return Session(engine)


def test_daily_usage_is_idempotent_and_policy_driven():
    db = _db()
    try:
        user = User(student_no="quota-1", name="Quota", password_hash="x", role="student", status="active")
        db.add(user)
        db.add(TokenQuotaPolicy(role="student", daily_limit=1000))
        db.commit()
        first = ChatQuotaService.daily_usage(db, user)
        second = ChatQuotaService.daily_usage(db, user)
        assert first.id == second.id
        assert ChatQuotaService.usage_summary(db, user)["remaining_tokens"] == 1000
    finally:
        db.close()


def test_reservation_and_unknown_usage_go_to_reconciliation():
    db = _db()
    try:
        user = User(student_no="quota-2", name="Quota", password_hash="x", role="student", status="active")
        db.add(user)
        db.add(TokenQuotaPolicy(role="student", daily_limit=100))
        db.commit()
        ChatQuotaService.reserve_request(db, user, request_id="req-1", reservation=40, idempotency_key="req-1:1")
        event = ChatQuotaService.settle_request(
            db, user, request_id="req-1", reservation=40,
            input_tokens=None, output_tokens=None, idempotency_key="req-1:1",
        )
        assert event.status == "pending_reconciliation"
        assert ChatQuotaService.usage_summary(db, user)["used_tokens"] == 0
        assert ChatQuotaService.usage_summary(db, user)["pending_reconciliation"] == 40
    finally:
        db.close()


def test_reconcile_pending_event_uses_actual_usage_once():
    db = _db()
    try:
        from backend.app.models.token_quota import ChatTokenUsageEvent
        user = User(student_no="quota-3", name="Quota", password_hash="x", role="student", status="active")
        db.add(user)
        db.add(TokenQuotaPolicy(role="student", daily_limit=100))
        db.commit()
        ChatQuotaService.reserve_request(db, user, request_id="req-2", reservation=40, idempotency_key="req-2:1")
        ChatQuotaService.settle_request(db, user, request_id="req-2", reservation=40, input_tokens=None, output_tokens=None, idempotency_key="req-2:1")
        event = db.query(ChatTokenUsageEvent).filter_by(request_id="req-2").first()
        settled = ChatQuotaService.reconcile_event(db, event.id, input_tokens=4, output_tokens=6)
        assert settled.status == "settled"
        assert ChatQuotaService.usage_summary(db, user)["used_tokens"] == 10
        assert ChatQuotaService.reconcile_event(db, event.id, input_tokens=100, output_tokens=100).total_tokens == 10
    finally:
        db.close()


def test_duplicate_reservation_and_settlement_are_idempotent():
    db = _db()
    try:
        user = User(student_no="quota-4", name="Quota", password_hash="x", role="student", status="active")
        db.add(user)
        db.add(TokenQuotaPolicy(role="student", daily_limit=100))
        db.commit()

        first = ChatQuotaService.reserve_request(
            db, user, request_id="req-3", reservation=40, idempotency_key="req-3:1"
        )
        second = ChatQuotaService.reserve_request(
            db, user, request_id="req-3", reservation=40, idempotency_key="req-3:1"
        )
        assert first.reserved_tokens == second.reserved_tokens == 40

        ChatQuotaService.settle_request(
            db, user, request_id="req-3", reservation=40,
            input_tokens=4, output_tokens=6, idempotency_key="req-3:1",
        )
        ChatQuotaService.settle_request(
            db, user, request_id="req-3", reservation=40,
            input_tokens=4, output_tokens=6, idempotency_key="req-3:1",
        )
        summary = ChatQuotaService.usage_summary(db, user)
        assert summary["used_tokens"] == 10
        assert summary["reserved_tokens"] == 0
    finally:
        db.close()


def test_concurrent_reservations_cannot_exceed_daily_limit(tmp_path):
    database_url = f"sqlite:///{(tmp_path / 'quota-concurrency.db').as_posix()}"
    engine = create_engine(database_url, connect_args={"check_same_thread": False, "timeout": 10})
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        user = User(student_no="quota-5", name="Quota", password_hash="x", role="student", status="active")
        db.add(user)
        db.add(TokenQuotaPolicy(role="student", daily_limit=100))
        db.commit()
        user_id = user.id
        ChatQuotaService.daily_usage(db, user)

    barrier = Barrier(2)

    def reserve(request_id: str) -> str:
        with Session(engine) as db:
            user = db.get(User, user_id)
            assert user is not None
            barrier.wait()
            try:
                ChatQuotaService.reserve_request(
                    db, user, request_id=request_id, reservation=60,
                    idempotency_key=f"{request_id}:1",
                )
                return "reserved"
            except ValueError as exc:
                return str(exc)

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(reserve, ("req-a", "req-b")))

    assert sorted(results) == ["TOKEN_QUOTA_EXCEEDED", "reserved"]
    with Session(engine) as db:
        user = db.get(User, user_id)
        assert user is not None
        assert ChatQuotaService.usage_summary(db, user)["reserved_tokens"] == 60


def test_retry_attempts_are_individually_traceable():
    from backend.app.models.token_quota import ChatTokenUsageEvent

    db = _db()
    try:
        user = User(student_no="quota-6", name="Quota", password_hash="x", role="student", status="active")
        db.add(user)
        db.commit()
        first = ChatQuotaService.record_unmetered_attempt(
            db, user, request_id="req-retry", attempt_no=2,
            idempotency_key="req-retry:attempt:2",
        )
        duplicate = ChatQuotaService.record_unmetered_attempt(
            db, user, request_id="req-retry", attempt_no=2,
            idempotency_key="req-retry:attempt:2",
        )
        assert first.id == duplicate.id
        assert first.status == "pending_reconciliation"
        assert db.query(ChatTokenUsageEvent).filter_by(request_id="req-retry").count() == 1
    finally:
        db.close()
