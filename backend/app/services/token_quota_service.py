from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from dataclasses import dataclass


BEIJING_TZ = timezone(timedelta(hours=8), name="Asia/Shanghai")


def usage_date(now: datetime | None = None) -> date:
    """Return the server-owned Beijing usage date, regardless of host timezone."""
    value = now or datetime.now(timezone.utc)
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(BEIJING_TZ).date()


def next_reset(now: datetime | None = None) -> datetime:
    current = now or datetime.now(timezone.utc)
    local = current.astimezone(BEIJING_TZ)
    tomorrow = local.date() + timedelta(days=1)
    return datetime.combine(tomorrow, time.min, tzinfo=BEIJING_TZ)


@dataclass
class QuotaLedger:
    quota: int
    used: int = 0
    reserved: int = 0
    pending_reconciliation: int = 0

    def reserve(self, amount: int) -> None:
        amount = max(0, int(amount))
        if self.used + self.reserved + amount > self.quota:
            raise ValueError("TOKEN_QUOTA_EXCEEDED")
        self.reserved += amount

    def settle(self, reserved: int, actual: int | None) -> str:
        self.reserved = max(0, self.reserved - max(0, int(reserved)))
        if actual is None:
            self.pending_reconciliation += max(0, int(reserved))
            return "pending_reconciliation"
        self.used += max(0, int(actual))
        return "settled"

    @property
    def remaining(self) -> int:
        return max(0, self.quota - self.used - self.reserved)
