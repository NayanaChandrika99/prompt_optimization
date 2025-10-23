from __future__ import annotations

import pytest

from voice_ai_keep_gepa.gepa_optimizer.scoring import ScoreConfig, compute_score


def test_compute_score_matches_objectives():
    config = ScoreConfig()
    breakdown = compute_score(
        config=config,
        failed_calls=[{"failure_reason": "no_slots"}],
        prompt_text="Always apologise and offer a waitlist option if slots are full.",
        objectives=["apologise", "waitlist"],
        current_metrics=None,
        previous_metrics=None,
    )

    assert breakdown.objective_coverage_ratio == pytest.approx(1.0, rel=0.1)
    assert breakdown.objective_alignment > 0


def test_compute_score_includes_conversion_delta():
    config = ScoreConfig()
    breakdown = compute_score(
        config=config,
        failed_calls=[{"failure_reason": "hang_up"}],
        prompt_text="Prompt text",
        objectives=[],
        current_metrics={"conversion_rate": 0.72},
        previous_metrics={"conversion_rate": 0.55},
    )

    assert breakdown.conversion_delta_rate == pytest.approx(0.17, rel=0.1)
    assert breakdown.conversion_delta_score > 0


def test_compute_score_handles_negative_conversion_delta():
    config = ScoreConfig()
    breakdown = compute_score(
        config=config,
        failed_calls=[{"failure_reason": "hang_up"}],
        prompt_text="Prompt text",
        objectives=[],
        current_metrics={"conversion_rate": 0.4},
        previous_metrics={"conversion_rate": 0.6},
    )

    assert breakdown.conversion_delta_rate == pytest.approx(-0.2, rel=0.1)
    assert breakdown.conversion_delta_score < 0
