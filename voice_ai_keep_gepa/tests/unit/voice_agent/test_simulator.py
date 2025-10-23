from __future__ import annotations

import pytest

pytest.importorskip("sqlalchemy")

from voice_ai_keep_gepa.voice_agent.metrics import MetricsAggregator
from voice_ai_keep_gepa.voice_agent.simulate_calls import (
    DEFAULT_SCENARIOS,
    run_simulation,
)


def test_run_simulation_produces_deterministic_results():
    metrics = MetricsAggregator()
    results = run_simulation(
        dealerships=1,
        runs=3,
        scenarios=DEFAULT_SCENARIOS,
        seed=123,
        metrics=metrics,
        repository=None,
    )

    assert len(results) == 3
    snapshot = metrics.snapshot()
    assert snapshot["total_calls"] == 3
    assert 0 <= snapshot["conversion_rate"] <= 1
