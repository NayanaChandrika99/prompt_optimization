"""Client wrapper for Together AI's Qwen chat completions API."""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Any

import requests


@dataclass
class QwenConfig:
    provider: str
    endpoint: str
    api_key: str | None
    model: str
    max_tokens: int
    temperature: float
    timeout_seconds: int


class QwenClient:
    def __init__(self, config: QwenConfig) -> None:
        self._cfg = config
        self._session = requests.Session()

    @classmethod
    def from_env(cls) -> QwenClient:
        return cls(
            QwenConfig(
                provider=os.getenv("QWEN_PROVIDER", "together"),
                endpoint=os.getenv(
                    "QWEN_ENDPOINT", "https://api.together.xyz/v1/chat/completions"
                ),
                api_key=os.getenv("TOGETHER_API_KEY"),
                model=os.getenv("QWEN_MODEL", "Qwen/Qwen3-Next-80B-A3B-Instruct"),
                max_tokens=int(os.getenv("QWEN_MAX_TOKENS", "512")),
                temperature=float(os.getenv("QWEN_TEMPERATURE", "0.7")),
                timeout_seconds=int(os.getenv("QWEN_TIMEOUT_SECONDS", "60")),
            )
        )

    def generate(
        self,
        *,
        prompt: str,
        system_prompt: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> str:
        if not self._cfg.api_key:
            return f"[QWEN-MOCK] {prompt[:120]} ..."

        if self._cfg.provider != "together":
            raise RuntimeError(f"Unsupported provider {self._cfg.provider}")

        payload: dict[str, Any] = {
            "model": self._cfg.model,
            "messages": self._build_messages(prompt, system_prompt),
            "max_tokens": max_tokens or self._cfg.max_tokens,
            "temperature": temperature if temperature is not None else self._cfg.temperature,
        }

        backoff = 0.25
        for _attempt in range(5):
            response = self._session.post(
                self._cfg.endpoint,
                json=payload,
                headers={
                    "Authorization": f"Bearer {self._cfg.api_key}",
                    "Content-Type": "application/json",
                },
                timeout=self._cfg.timeout_seconds,
            )
            if response.status_code == 200:
                data = response.json()
                try:
                    return data["choices"][0]["message"]["content"]
                except (KeyError, IndexError, TypeError) as exc:
                    raise RuntimeError(f"Unexpected Qwen response format: {data}") from exc
            if response.status_code in (429, 500, 502, 503):
                time.sleep(backoff)
                backoff = min(backoff * 2, 2.0)
                continue
            raise RuntimeError(
                f"Qwen request failed ({response.status_code}): {response.text[:500]}"
            )
        raise TimeoutError("Qwen API retries exhausted")

    def _build_messages(self, prompt: str, system_prompt: str | None) -> list[dict[str, str]]:
        messages: list[dict[str, str]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        else:
            messages.append(
                {
                    "role": "system",
                    "content": (
                        "You are a cautious optimization assistant helping refine "
                        "voice agent prompts."
                    ),
                }
            )
        messages.append({"role": "user", "content": prompt})
        return messages
