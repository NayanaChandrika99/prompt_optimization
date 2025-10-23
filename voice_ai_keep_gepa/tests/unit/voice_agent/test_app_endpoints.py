from __future__ import annotations

import pytest

pytest.importorskip("sqlalchemy")

from voice_ai_keep_gepa.voice_agent.app import create_app


def test_health_endpoint_reports_service():
    app = create_app()
    client = app.test_client()

    response = client.get("/health")

    assert response.status_code == 200
    assert response.get_json()["service"] == "voice-agent"


def test_simulate_endpoint_updates_metrics():
    app = create_app()
    client = app.test_client()

    payload = {
        "customer_request": "I want to book a service appointment tomorrow morning.",
        "available_slots": ["Tomorrow 10am"],
        "dealership_id": "dealer-test",
        "prompt_version": "v1.0",
    }

    simulate_response = client.post("/simulate", json=payload)

    assert simulate_response.status_code == 200
    json_data = simulate_response.get_json()
    assert json_data["success"] is True
    assert json_data["intent"] == "book_service_appointment"
    assert json_data["selected_slot"] == "Tomorrow 10am"

    metrics_response = client.get("/metrics")
    snapshot = metrics_response.get_json()

    assert snapshot["total_calls"] == 1
    assert snapshot["successful_calls"] == 1
    assert snapshot["conversion_rate"] == 1.0
