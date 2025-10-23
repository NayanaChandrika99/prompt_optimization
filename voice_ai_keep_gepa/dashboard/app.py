"""Dashboard service exposing UI and metrics proxy endpoints."""

from __future__ import annotations

import json
import logging
import os
from typing import Any

import requests
from flask import Flask, jsonify, render_template

logger = logging.getLogger(__name__)

VOICE_AGENT_BASE_URL = os.getenv("VOICE_AGENT_BASE_URL", "http://localhost:5100")
GEPA_OPTIMIZER_BASE_URL = os.getenv("GEPA_OPTIMIZER_BASE_URL", "http://localhost:8000")

DEFAULT_VOICE_METRICS = {
    "total_calls": 0,
    "successful_calls": 0,
    "failed_calls": 0,
    "conversion_rate": 0.0,
    "failure_reasons": {},
    "recent_calls": [],
}

DEFAULT_GEPA_METRICS = {
    "total_runs": 0,
    "success_rate": 0.0,
    "average_improvement": 0.0,
    "last_run_timestamp": None,
    "active_prompt_version": None,
    "active_prompt_created_at": None,
    "score_breakdown": {
        "base": 0.0,
        "failure_mix": 0.0,
        "objective_alignment": 0.0,
        "prompt_quality": 0.0,
        "conversion_delta_score": 0.0,
        "conversion_delta_rate": 0.0,
        "objective_coverage_ratio": 0.0,
        "total": 0.0,
    },
    "latest_conversion_snapshot": None,
}


def create_app() -> Flask:
    app = Flask(__name__, template_folder="templates", static_folder="static")
    app.json.sort_keys = False

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "service": "dashboard"}

    @app.get("/api/dashboard")
    def dashboard_api() -> Any:
        return jsonify(get_dashboard_payload())

    @app.get("/")
    def index() -> str:
        payload = get_dashboard_payload()
        return render_template("dashboard/index.html", initial_data=json.dumps(payload))

    return app


def get_dashboard_payload() -> dict[str, Any]:
    voice_metrics = fetch_voice_metrics()
    gepa_metrics = fetch_gepa_metrics()
    prompts = fetch_prompts(limit=10)
    return {
        "voice_metrics": voice_metrics,
        "gepa_metrics": gepa_metrics,
        "prompts": prompts,
    }


def fetch_voice_metrics() -> dict[str, Any]:
    url = f"{VOICE_AGENT_BASE_URL.rstrip('/')}/metrics"
    data = fetch_json(url, DEFAULT_VOICE_METRICS)
    # Normalise keys that might be missing depending on upstream implementation.
    data.setdefault("failure_reasons", {})
    data.setdefault("recent_calls", [])
    data.setdefault("conversion_rate", 0.0)
    return data


def fetch_gepa_metrics() -> dict[str, Any]:
    url = f"{GEPA_OPTIMIZER_BASE_URL.rstrip('/')}/metrics"
    data = fetch_json(url, DEFAULT_GEPA_METRICS)
    for key, value in DEFAULT_GEPA_METRICS.items():
        if key not in data:
            data[key] = value.copy() if isinstance(value, dict) else value
        elif isinstance(value, dict) and isinstance(data[key], dict):
            defaults = value
            merged = defaults.copy()
            merged.update(data[key])
            data[key] = merged
    return data


def fetch_prompts(*, limit: int = 10) -> list[dict[str, Any]]:
    url = f"{GEPA_OPTIMIZER_BASE_URL.rstrip('/')}/prompts?limit={limit}"
    payload = fetch_json(url, {"items": []})
    items = payload.get("items") or []
    return items[:limit]


def fetch_json(url: str, default: Any) -> Any:
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as err:
        logger.warning("Failed to fetch %s: %s", url, err)
        return default


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    flask_app = create_app()
    port = int(os.getenv("DASHBOARD_PORT", "5000"))
    flask_app.run(host="0.0.0.0", port=port)  # noqa: S104
