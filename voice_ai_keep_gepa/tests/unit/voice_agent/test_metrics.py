from __future__ import annotations

from voice_ai_keep_gepa.voice_agent.agent import CallContext, VoiceAgent
from voice_ai_keep_gepa.voice_agent.metrics import MetricsAggregator


def test_metrics_snapshot_counts_success_and_failure():
    agent = VoiceAgent()
    metrics = MetricsAggregator()
    context = CallContext(
        dealership_id="dealer-1",
        prompt_version="v1.0",
        available_slots=["Friday 3pm"],
        knowledge_base={},
    )

    success_outcome = agent.handle_call("Please book me for Friday", context)
    metrics.record("dealer-1", "v1.0", success_outcome)

    failure_context = CallContext(
        dealership_id="dealer-1",
        prompt_version="v1.0",
        available_slots=[],
        knowledge_base={},
    )
    failure_outcome = agent.handle_call("Schedule me tomorrow", failure_context)
    metrics.record("dealer-1", "v1.0", failure_outcome)

    snapshot = metrics.snapshot()

    assert snapshot["total_calls"] == 2
    assert snapshot["successful_calls"] == 1
    assert snapshot["failed_calls"] == 1
    assert snapshot["conversion_rate"] == 0.5
    assert snapshot["failure_reasons"]["no_slots"] == 1
