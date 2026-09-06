from datetime import datetime, timezone

import pytest

from backend.app.services.retry_policy import RetryPolicy
from backend.app.services.token_quota_service import QuotaLedger, next_reset, usage_date


def test_retry_policy_caps_logical_request_at_three_attempts():
    assert RetryPolicy.decide("TIMEOUT", 1).retry is True
    assert RetryPolicy.decide("TIMEOUT", 2).retry is True
    assert RetryPolicy.decide("TIMEOUT", 3).retry is False
    assert RetryPolicy.decide("AUTH_FAILED", 1).retry is False


def test_quota_ledger_reserves_and_settles_actual_usage():
    ledger = QuotaLedger(quota=100)
    ledger.reserve(80)
    assert ledger.remaining == 20
    assert ledger.settle(80, 25) == "settled"
    assert ledger.used == 25 and ledger.reserved == 0


def test_quota_ledger_does_not_estimate_usage_on_unknown_failure():
    ledger = QuotaLedger(quota=100)
    ledger.reserve(40)
    assert ledger.settle(40, None) == "pending_reconciliation"
    assert ledger.used == 0 and ledger.pending_reconciliation == 40


def test_beijing_usage_date_and_reset_are_server_owned():
    instant = datetime(2026, 8, 19, 16, 30, tzinfo=timezone.utc)
    assert str(usage_date(instant)) == "2026-08-20"
    assert next_reset(instant).hour == 0


def test_quota_ledger_rejects_over_reservation():
    ledger = QuotaLedger(quota=10)
    with pytest.raises(ValueError, match="TOKEN_QUOTA_EXCEEDED"):
        ledger.reserve(11)
