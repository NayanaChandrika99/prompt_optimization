"""GEPA optimizer Flask application."""

from __future__ import annotations

import os
from http import HTTPStatus
from typing import Any

from flask import Flask, jsonify, request

from .optimizer import PromptOptimizer
from .qwen_client import QwenClient
from .schemas import OptimizationPayload
from .storage import PromptRepository, create_engine_from_dsn, create_tables
from .voice_metrics_client import VoiceMetricsClient


def create_app() -> Flask:
    app = Flask(__name__)
    app.json.sort_keys = False

    database_url = os.getenv("DATABASE_URL")
    engine = create_engine_from_dsn(database_url)
    if engine is None:
        raise RuntimeError("DATABASE_URL is required for GEPA optimizer")

    create_tables(engine)

    repository = PromptRepository(engine)
    qwen_client = QwenClient.from_env()
    metrics_client = VoiceMetricsClient.from_env()
    optimizer = PromptOptimizer(
        repository,
        qwen_client,
        metrics_client=metrics_client,
    )

    @app.get("/health")
    def health() -> dict[str, Any]:
        return {
            "status": "ok",
            "service": "gepa-optimizer",
            "model": qwen_client._cfg.model,  # pylint: disable=protected-access
        }

    @app.get("/metrics")
    def metrics() -> dict[str, Any]:
        data = repository.metrics()
        active = repository.get_active_prompt()
        data.update(
            {
                "active_prompt_version": active.version if active else None,
                "active_prompt_created_at": active.created_at.isoformat() if active else None,
            }
        )
        runs = repository.recent_runs(limit=10)
        data["recent_runs"] = [
            {
                "id": run.id,
                "status": run.status.value if hasattr(run.status, "value") else run.status,
                "model": run.model,
                "improvement": run.improvement,
                "duration_seconds": run.duration_seconds,
                "created_at": run.created_at.isoformat(),
                "completed_at": run.completed_at.isoformat() if run.completed_at else None,
                "notes": run.notes,
                "score_components": run.score_components,
                "conversion_snapshot": run.conversion_snapshot,
            }
            for run in runs
        ]
        return data

    @app.get("/prompts")
    def prompts() -> dict[str, Any]:
        versions = repository.list_prompts(limit=int(request.args.get("limit", 10)))
        return {
            "items": [
                {
                    "version": prompt.version,
                    "created_at": prompt.created_at.isoformat(),
                    "notes": prompt.notes,
                    "is_active": prompt.is_active,
                    "preview": (prompt.content or "")[:600],
                }
                for prompt in versions
            ]
        }

    @app.post("/optimize")
    def optimize() -> Any:
        try:
            payload_dict = request.get_json(force=True, silent=False)
        except Exception as exc:  # noqa: BLE001
            app.logger.exception("Invalid JSON payload")
            return (
                jsonify({"error": "Invalid JSON payload", "details": str(exc)}),
                HTTPStatus.BAD_REQUEST,
            )

        try:
            payload = OptimizationPayload.from_dict(payload_dict or {})
        except ValueError as exc:
            return jsonify({"error": str(exc)}), HTTPStatus.BAD_REQUEST

        try:
            result = optimizer.optimize(payload)
        except Exception as exc:  # noqa: BLE001
            app.logger.exception("Optimization failed")
            return (
                jsonify({"error": "optimization_failed", "details": str(exc)}),
                HTTPStatus.INTERNAL_SERVER_ERROR,
            )

        return (
            jsonify(
                {
                    "status": "completed",
                    "run_id": result.run_id,
                    "alert_id": result.alert_id,
                    "previous_version": result.previous_version,
                    "new_version": result.new_version,
                    "improvement": result.improvement,
                    "duration_seconds": result.duration_seconds,
                    "prompt_preview": result.prompt_preview,
                    "score_components": result.score_components,
                }
            ),
            HTTPStatus.ACCEPTED,
        )

    return app


if __name__ == "__main__":
    flask_app = create_app()
    port = int(os.getenv("GEPA_OPTIMIZER_PORT", "8000"))
    flask_app.run(host="0.0.0.0", port=port)  # noqa: S104  # required for Docker networking
