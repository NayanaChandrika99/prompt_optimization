"""HTTP client for fetching voice agent metrics."""

from __future__ import annotations

import logging
import os
from typing import Any

import requests


def _parse_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _parse_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


class VoiceMetricsClient:
    """Minimal HTTP client around the voice agent metrics endpoint."""

    def __init__(self, base_url: str, *, timeout: float = 5.0) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._logger = logging.getLogger(__name__)

    @classmethod
    def from_env(cls) -> "VoiceMetricsClient | None":
        base_url = os.getenv("VOICE_AGENT_BASE_URL")
        if not base_url:
            return None
        timeout_raw = os.getenv("GEPA_VOICE_METRICS_TIMEOUT", "5.0")
        try:
            timeout = float(timeout_raw)
        except ValueError:
            timeout = 5.0
        return cls(base_url, timeout=timeout)

    def fetch_snapshot(self) -> dict[str, Any] | None:
        """Return the latest voice metrics snapshot or None on failure."""
        url = f"{self._base_url}/metrics"
        try:
            response = requests.get(url, timeout=self._timeout)
            response.raise_for_status()
            payload = response.json()
        except (requests.RequestException, ValueError) as err:
            self._logger.warning("Failed to fetch voice metrics from %s: %s", url, err)
            return None

        snapshot = {
            "timestamp": payload.get("timestamp"),
            "prompt_version": payload.get("prompt_version"),
            "dealership_id": payload.get("dealership_id"),
            "total_calls": _parse_int(payload.get("total_calls")),
            "successful_calls": _parse_int(payload.get("successful_calls")),
            "failed_calls": _parse_int(payload.get("failed_calls")),
            "conversion_rate": _parse_float(payload.get("conversion_rate")),
            "failure_reasons": payload.get("failure_reasons") or {},
        }
        recent_calls = payload.get("recent_calls")
        if isinstance(recent_calls, list):
            snapshot["recent_calls"] = recent_calls[:5]
        return snapshot
