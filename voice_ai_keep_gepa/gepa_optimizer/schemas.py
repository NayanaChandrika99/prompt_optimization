"""Request/response schemas for the GEPA optimizer service."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class FailedCall:
    transcript: str
    customer_id: str | None
    summary: str | None
    failure_reason: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> FailedCall:
        transcript = data.get("transcript")
        if not transcript:
            raise ValueError("failed_calls[].transcript is required")
        return cls(
            transcript=transcript,
            customer_id=data.get("customer_id"),
            summary=data.get("summary"),
            failure_reason=data.get("failure_reason"),
        )


@dataclass
class OptimizationPayload:
    alert_id: str | None
    prompt_version: str | None
    failed_calls: list[FailedCall]
    objectives: list[str]

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> OptimizationPayload:
        failed_calls_raw = data.get("failed_calls") or []
        if not isinstance(failed_calls_raw, list) or not failed_calls_raw:
            raise ValueError("failed_calls must be a non-empty list")
        failed_calls = [FailedCall.from_dict(item) for item in failed_calls_raw]
        objectives = data.get("objectives") or []
        if not isinstance(objectives, list):
            raise ValueError("objectives must be a list if provided")
        return cls(
            alert_id=data.get("alert_id"),
            prompt_version=data.get("prompt_version"),
            failed_calls=failed_calls,
            objectives=[str(obj) for obj in objectives],
        )


@dataclass
class OptimizationResult:
    alert_id: str | None
    run_id: int
    previous_version: str | None
    new_version: str
    improvement: float
    duration_seconds: float
    prompt_preview: str
    score_components: dict[str, float]
