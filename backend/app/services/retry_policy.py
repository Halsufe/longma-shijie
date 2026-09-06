from __future__ import annotations

from dataclasses import dataclass


RETRYABLE_CODES = frozenset({"NETWORK_ERROR", "TIMEOUT", "MODEL_5XX", "UPSTREAM_TEMPORARY"})


@dataclass(frozen=True)
class RetryDecision:
    retry: bool
    attempt_no: int
    max_attempts: int = 3


class RetryPolicy:
    """At most two retries for one logical request."""

    max_attempts = 3

    @classmethod
    def decide(cls, error_code: str | None, attempt_no: int) -> RetryDecision:
        next_attempt = max(1, int(attempt_no) + 1)
        return RetryDecision(
            retry=bool(error_code in RETRYABLE_CODES and next_attempt <= cls.max_attempts),
            attempt_no=next_attempt,
        )
