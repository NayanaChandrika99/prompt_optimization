"""Metrics aggregation utilities for the voice agent."""

from __future__ import annotations

from collections import Counter, deque
from dataclasses import dataclass, field
from datetime import UTC, datetime

from .agent import CallOutcome, FailureReason


@dataclass
class RecordedCall:
    """Lightweight record used for in-memory storage and metrics."""

    dealership_id: str
    prompt_version: str
    outcome: CallOutcome
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))


class MetricsAggregator:
    """Aggregates call outcomes across the agent fleet."""

    def __init__(self, max_recent: int = 50) -> None:
        self._total_calls = 0
        self._successful_calls = 0
        self._failure_reasons: Counter[str] = Counter()
        self._recent_calls: deque[RecordedCall] = deque(maxlen=max_recent)
        self._last_prompt_version: str | None = None
        self._last_dealership_id: str | None = None

    def record(self, dealership_id: str, prompt_version: str, outcome: CallOutcome) -> None:
        self._total_calls += 1
        if outcome.success:
            self._successful_calls += 1
        else:
            reason = outcome.failure_reason or FailureReason.UNKNOWN
            self._failure_reasons[reason.value] += 1

        self._last_prompt_version = prompt_version
        self._last_dealership_id = dealership_id
        self._recent_calls.append(RecordedCall(dealership_id, prompt_version, outcome))

    @property
    def total_calls(self) -> int:
        return self._total_calls

    @property
    def successful_calls(self) -> int:
        return self._successful_calls

    @property
    def failed_calls(self) -> int:
        return self._total_calls - self._successful_calls

    def conversion_rate(self) -> float:
        if self._total_calls == 0:
            return 0.0
        return round(self._successful_calls / self._total_calls, 3)

    def snapshot(self) -> dict[str, object]:
        """Return metrics payload following the documented contract."""
        timestamp = datetime.now(UTC).isoformat()
        return {
            "timestamp": timestamp,
            "dealership_id": self._last_dealership_id or "unknown",
            "prompt_version": self._last_prompt_version or "v0",
            "total_calls": self._total_calls,
            "successful_calls": self._successful_calls,
            "failed_calls": self.failed_calls,
            "failure_reasons": dict(self._failure_reasons),
            "conversion_rate": self.conversion_rate(),
        }

    def recent_calls(self) -> list[dict[str, object]]:
        """Return serialized recent call records."""
        items: list[dict[str, object]] = []
        for record in list(self._recent_calls):
            items.append(
                {
                    "timestamp": record.timestamp.isoformat(),
                    "dealership_id": record.dealership_id,
                    "prompt_version": record.prompt_version,
                    "success": record.outcome.success,
                    "intent": record.outcome.intent.value,
                    "failure_reason": (
                        record.outcome.failure_reason.value
                        if record.outcome.failure_reason
                        else None
                    ),
                    "selected_slot": record.outcome.selected_slot,
                    "summary": record.outcome.summary,
                }
            )
        return items

    def reset(self) -> None:
        self._total_calls = 0
        self._successful_calls = 0
        self._failure_reasons.clear()
        self._recent_calls.clear()
        self._last_dealership_id = None
        self._last_prompt_version = None
