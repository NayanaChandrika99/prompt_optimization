from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from voice_ai_keep_gepa.gepa_optimizer.qwen_client import QwenClient, QwenConfig


def test_generate_returns_mock_when_no_api_key(monkeypatch):
    config = QwenConfig(
        provider="together",
        endpoint="https://example.com",
        api_key=None,
        model="Qwen/Qwen3-Next-80B-A3B-Instruct",
        max_tokens=128,
        temperature=0.5,
        timeout_seconds=30,
    )
    client = QwenClient(config)

    result = client.generate(prompt="Hello")

    assert result.startswith("[QWEN-MOCK]")


def test_generate_invokes_http_client(monkeypatch):
    config = QwenConfig(
        provider="together",
        endpoint="https://api.together.xyz/v1/chat/completions",
        api_key="key",
        model="Qwen/Qwen3-Next-80B-A3B-Instruct",
        max_tokens=64,
        temperature=0.7,
        timeout_seconds=30,
    )
    client = QwenClient(config)

    fake_session = MagicMock()
    monkeypatch.setattr(client, "_session", fake_session)

    fake_response = MagicMock()
    fake_response.status_code = 200
    fake_response.json.return_value = {
        "choices": [{"message": {"content": "Updated prompt"}}]
    }
    fake_session.post.return_value = fake_response

    output = client.generate(prompt="Improve this prompt")

    assert output == "Updated prompt"
    fake_session.post.assert_called_once()


def test_generate_raises_on_http_failure(monkeypatch):
    config = QwenConfig(
        provider="together",
        endpoint="https://api.together.xyz/v1/chat/completions",
        api_key="key",
        model="Qwen/Qwen3-Next-80B-A3B-Instruct",
        max_tokens=64,
        temperature=0.7,
        timeout_seconds=30,
    )
    client = QwenClient(config)

    fake_session = MagicMock()
    monkeypatch.setattr(client, "_session", fake_session)

    fake_response = MagicMock()
    fake_response.status_code = 400
    fake_response.text = "bad request"
    fake_session.post.return_value = fake_response

    with pytest.raises(RuntimeError):
        client.generate(prompt="Invalid")
