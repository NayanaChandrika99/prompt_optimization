"""Improvement scoring utilities for the GEPA optimizer."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Any


_NON_ALNUM_RE = re.compile(r"[^a-z0-9\s]+")


def _normalise_text(value: str) -> str:
    """Lower-case and strip punctuation for lightweight matching."""
    lowered = value.lower()
    return _NON_ALNUM_RE.sub(" ", lowered).strip()


def _parse_bool(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    lowered = value.strip().lower()
    if lowered in {"1", "true", "yes", "y"}:
        return True
    if lowered in {"0", "false", "no", "n"}:
        return False
    return default


def _parse_float(value: str | None, default: float) -> float:
    if value is None:
        return default
    try:
        return float(value)
    except ValueError:
        return default


@dataclass(frozen=True)
class ScoreConfig:
    """Configuration knobs for the improvement score."""

    base_score: float = 0.08
    max_total: float = 0.6

    failure_unique_weight: float = 0.04
    failure_unique_cap: float = 0.16
    failure_volume_weight: float = 0.01
    failure_volume_cap: float = 0.06

    objective_weight: float = 0.25
    prompt_length_cap: float = 0.05
    prompt_length_reference: float = 450.0

    conversion_delta_weight: float = 0.5
    conversion_delta_cap: float = 0.2

    enable_objective_match: bool = True
    enable_conversion_delta: bool = True

    @classmethod
    def from_env(cls) -> "ScoreConfig":
        prefix = "GEPA_SCORE_"
        env = os.environ
        return cls(
            base_score=_parse_float(env.get(f"{prefix}BASE"), cls.base_score),
            max_total=_parse_float(env.get(f"{prefix}MAX_TOTAL"), cls.max_total),
            failure_unique_weight=_parse_float(
                env.get(f"{prefix}FAILURE_UNIQUE_WEIGHT"), cls.failure_unique_weight
            ),
            failure_unique_cap=_parse_float(
                env.get(f"{prefix}FAILURE_UNIQUE_CAP"), cls.failure_unique_cap
            ),
            failure_volume_weight=_parse_float(
                env.get(f"{prefix}FAILURE_VOLUME_WEIGHT"), cls.failure_volume_weight
            ),
            failure_volume_cap=_parse_float(
                env.get(f"{prefix}FAILURE_VOLUME_CAP"), cls.failure_volume_cap
            ),
            objective_weight=_parse_float(
                env.get(f"{prefix}OBJECTIVE_WEIGHT"), cls.objective_weight
            ),
            prompt_length_cap=_parse_float(
                env.get(f"{prefix}PROMPT_LENGTH_CAP"), cls.prompt_length_cap
            ),
            prompt_length_reference=_parse_float(
                env.get(f"{prefix}PROMPT_LENGTH_REFERENCE"), cls.prompt_length_reference
            ),
            conversion_delta_weight=_parse_float(
                env.get(f"{prefix}CONVERSION_DELTA_WEIGHT"), cls.conversion_delta_weight
            ),
            conversion_delta_cap=_parse_float(
                env.get(f"{prefix}CONVERSION_DELTA_CAP"), cls.conversion_delta_cap
            ),
            enable_objective_match=_parse_bool(
                env.get(f"{prefix}ENABLE_OBJECTIVE_MATCH"), cls.enable_objective_match
            ),
            enable_conversion_delta=_parse_bool(
                env.get(f"{prefix}ENABLE_CONVERSION_DELTA"), cls.enable_conversion_delta
            ),
        )


@dataclass
class ScoreBreakdown:
    """Detailed improvement score components."""

    base: float
    failure_mix: float
    objective_alignment: float
    prompt_quality: float
    conversion_delta_score: float
    conversion_delta_rate: float
    objective_coverage_ratio: float

    @property
    def total(self) -> float:
        return (
            self.base
            + self.failure_mix
            + self.objective_alignment
            + self.prompt_quality
            + self.conversion_delta_score
        )

    def as_dict(self, *, max_total: float) -> dict[str, float]:
        total = min(max(self.total, 0.0), max_total)
        return {
            "base": round(self.base, 4),
            "failure_mix": round(self.failure_mix, 4),
            "objective_alignment": round(self.objective_alignment, 4),
            "prompt_quality": round(self.prompt_quality, 4),
            "conversion_delta_score": round(self.conversion_delta_score, 4),
            "conversion_delta_rate": round(self.conversion_delta_rate, 4),
            "objective_coverage_ratio": round(self.objective_coverage_ratio, 4),
            "total": round(total, 4),
        }


def compute_score(
    *,
    config: ScoreConfig,
    failed_calls: list[dict[str, Any]],
    prompt_text: str,
    objectives: list[str],
    current_metrics: dict[str, Any] | None,
    previous_metrics: dict[str, Any] | None,
) -> ScoreBreakdown:
    unique_failures = {
        call.get("failure_reason") or call.get("failure_reason_code")
        for call in failed_calls
        if call.get("failure_reason") or call.get("failure_reason_code")
    }
    unique_failures.discard(None)

    failure_unique_score = min(
        len(unique_failures) * config.failure_unique_weight,
        config.failure_unique_cap,
    )
    failure_volume_score = min(
        len(failed_calls) * config.failure_volume_weight,
        config.failure_volume_cap,
    )
    failure_mix = failure_unique_score + failure_volume_score

    prompt_tokens = max(len(prompt_text.split()), 1)
    length_ratio = prompt_tokens / max(config.prompt_length_reference, 1.0)
    prompt_quality = min(length_ratio, 1.0) * config.prompt_length_cap

    objective_alignment = 0.0
    objective_coverage_ratio = 0.0
    if config.enable_objective_match and objectives:
        normalised_prompt = _normalise_text(prompt_text)
        matches = 0
        for objective in objectives:
            objective_key = _normalise_text(objective)
            if not objective_key:
                continue
            if objective_key in normalised_prompt:
                matches += 1
        objective_coverage_ratio = matches / len(objectives)
        objective_alignment = objective_coverage_ratio * config.objective_weight

    conversion_delta_rate = 0.0
    if config.enable_conversion_delta and current_metrics and previous_metrics:
        current_rate = float(current_metrics.get("conversion_rate") or 0.0)
        previous_rate = float(previous_metrics.get("conversion_rate") or 0.0)
        conversion_delta_rate = current_rate - previous_rate

    conversion_delta_score = max(
        min(conversion_delta_rate * config.conversion_delta_weight, config.conversion_delta_cap),
        -config.conversion_delta_cap,
    )

    return ScoreBreakdown(
        base=config.base_score,
        failure_mix=failure_mix,
        objective_alignment=objective_alignment,
        prompt_quality=prompt_quality,
        conversion_delta_score=conversion_delta_score,
        conversion_delta_rate=conversion_delta_rate,
        objective_coverage_ratio=objective_coverage_ratio,
    )
