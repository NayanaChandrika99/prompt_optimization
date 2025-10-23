from __future__ import annotations

import json

from voice_ai_keep_gepa.dashboard.app import create_app, get_dashboard_payload


def test_get_dashboard_payload_uses_helpers(monkeypatch):
    monkeypatch.setattr(
        "voice_ai_keep_gepa.dashboard.app.fetch_voice_metrics",
        lambda: {"total_calls": 3, "recent_calls": []},
    )
    monkeypatch.setattr(
        "voice_ai_keep_gepa.dashboard.app.fetch_gepa_metrics",
        lambda: {"total_runs": 2},
    )
    monkeypatch.setattr(
        "voice_ai_keep_gepa.dashboard.app.fetch_prompts",
        lambda limit=10: [{"version": "v2"}],
    )

    payload = get_dashboard_payload()

    assert payload["voice_metrics"]["total_calls"] == 3
    assert payload["gepa_metrics"]["total_runs"] == 2
    assert payload["prompts"][0]["version"] == "v2"


def test_dashboard_api_returns_json(monkeypatch):
    fake_payload = {
        "voice_metrics": {"total_calls": 5, "recent_calls": []},
        "gepa_metrics": {"total_runs": 1, "recent_runs": []},
        "prompts": [],
    }
    monkeypatch.setattr(
        "voice_ai_keep_gepa.dashboard.app.get_dashboard_payload", lambda: fake_payload
    )

    app = create_app()
    app.config.update(TESTING=True)
    client = app.test_client()

    response = client.get("/api/dashboard")
    assert response.status_code == 200
    assert response.get_json() == fake_payload


def test_dashboard_index_embeds_initial_data(monkeypatch):
    fake_payload = {
        "voice_metrics": {"total_calls": 1, "recent_calls": []},
        "gepa_metrics": {"total_runs": 0, "recent_runs": []},
        "prompts": [],
    }
    monkeypatch.setattr(
        "voice_ai_keep_gepa.dashboard.app.get_dashboard_payload", lambda: fake_payload
    )

    app = create_app()
    app.config.update(TESTING=True)
    client = app.test_client()

    response = client.get("/")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "Voice AI Health Dashboard" in html
    assert json.dumps(fake_payload) in html
