"""Voice agent service exposing health, metrics, and simulation endpoints."""

from __future__ import annotations

import os
from typing import Any

from flask import Flask, request

from .agent import CallContext, VoiceAgent
from .metrics import MetricsAggregator
from .simulate_calls import load_knowledge_base
from .storage import CallRepository, create_engine_from_dsn, create_tables


def create_app() -> Flask:
    """Create and configure the voice agent Flask app."""
    app = Flask(__name__)
    app.json.sort_keys = False

    metrics = MetricsAggregator()
    knowledge_base = load_knowledge_base()
    agent = VoiceAgent()

    database_url = os.getenv("DATABASE_URL")
    engine = create_engine_from_dsn(database_url)
    create_tables(engine)
    repository = CallRepository(engine) if engine is not None else None

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "service": "voice-agent"}

    @app.get("/metrics")
    def metrics_route() -> dict[str, Any]:
        payload = metrics.snapshot()
        payload["recent_calls"] = metrics.recent_calls()
        return payload

    @app.post("/simulate")
    def simulate_call() -> tuple[dict[str, Any], int] | dict[str, Any]:
        data = request.get_json(silent=True) or {}
        customer_request = data.get("customer_request")
        if not customer_request:
            return {"error": "customer_request is required"}, 400
        available_slots = data.get("available_slots") or []
        if not isinstance(available_slots, list):
            return {"error": "available_slots must be a list of strings"}, 400

        dealership_id = data.get("dealership_id", "dealer-sim")
        prompt_version = data.get("prompt_version", "v1.0")

        context = CallContext(
            dealership_id=dealership_id,
            prompt_version=prompt_version,
            available_slots=available_slots,
            knowledge_base=knowledge_base,
        )

        outcome = agent.handle_call(customer_request, context)
        metrics.record(dealership_id, prompt_version, outcome)
        if repository is not None:
            repository.log_call(dealership_id, prompt_version, outcome, outcome.turns)

        response = {
            "success": outcome.success,
            "intent": outcome.intent.value,
            "selected_slot": outcome.selected_slot,
            "failure_reason": (
                outcome.failure_reason.value if outcome.failure_reason else None
            ),
            "summary": outcome.summary,
            "turns": [{"role": turn.role, "content": turn.content} for turn in outcome.turns],
        }
        return response

    return app


if __name__ == "__main__":
    app = create_app()
    port = int(os.getenv("VOICE_AGENT_PORT", "5100"))
    app.run(host="0.0.0.0", port=port)  # noqa: S104  # required for Docker networking
