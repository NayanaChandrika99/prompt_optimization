from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

pytest.importorskip("sqlalchemy")

from voice_ai_keep_gepa.gepa_optimizer.qwen_client import QwenClient
from voice_ai_keep_gepa.gepa_optimizer.service import create_app
from voice_ai_keep_gepa.gepa_optimizer.storage import (
    PromptRepository,
    create_engine_from_dsn,
    create_tables,
)


@pytest.fixture
def app(monkeypatch, tmp_path):
    database_url = f"sqlite+pysqlite:///{tmp_path/'gepa.db'}"

    engine = create_engine_from_dsn(database_url)
    create_tables(engine)

    repo = PromptRepository(engine)

    fake_client = MagicMock(spec=QwenClient)
    fake_client.generate.return_value = "Optimized prompt"
    fake_client._cfg = MagicMock(model="Qwen/Qwen3-Next-80B-A3B-Instruct")  # noqa: SLF001

    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setenv("QWEN_MODEL", "Qwen/Qwen3-Next-80B-A3B-Instruct")
    monkeypatch.setenv("QWEN_ENDPOINT", "https://api.together.xyz/v1/chat/completions")
    monkeypatch.setenv("QWEN_PROVIDER", "together")

    monkeypatch.setattr(
        "voice_ai_keep_gepa.gepa_optimizer.service.PromptRepository",
        lambda engine: repo,
    )
    monkeypatch.setattr(
        "voice_ai_keep_gepa.gepa_optimizer.service.QwenClient",
        MagicMock(from_env=lambda: fake_client),
    )

    app = create_app()
    app.config.update(TESTING=True)
    return app


@pytest.fixture
def client(app):
    return app.test_client()


def test_optimize_endpoint_returns_result(client):
    payload = {
        "alert_id": "alert-123",
        "failed_calls": [{"transcript": "customer hung up", "summary": "hung up"}],
        "objectives": ["recover hung up"],
    }

    response = client.post("/optimize", data=json.dumps(payload), content_type="application/json")

    assert response.status_code == 202
    data = response.get_json()
    assert data["status"] == "completed"
    assert data["new_version"].startswith("v")
    assert "score_components" in data


def test_metrics_endpoint(client):
    response = client.get("/metrics")
    assert response.status_code == 200
    data = response.get_json()
    assert "total_runs" in data
    assert "score_breakdown" in data
