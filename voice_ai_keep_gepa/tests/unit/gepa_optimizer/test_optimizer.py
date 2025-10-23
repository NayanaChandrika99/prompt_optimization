from __future__ import annotations

from unittest.mock import MagicMock

import pytest

pytest.importorskip("sqlalchemy")

from voice_ai_keep_gepa.gepa_optimizer.optimizer import PromptOptimizer
from voice_ai_keep_gepa.gepa_optimizer.schemas import FailedCall, OptimizationPayload
from voice_ai_keep_gepa.gepa_optimizer.storage import (
    PromptRepository,
    RunStatusEnum,
    create_engine_from_dsn,
    create_tables,
)


def build_repository():
    engine = create_engine_from_dsn("sqlite+pysqlite:///:memory:")
    create_tables(engine)
    return PromptRepository(engine)


def test_optimize_creates_new_prompt_and_run(monkeypatch):
    repo = build_repository()

    qwen_client = MagicMock()
    qwen_client.generate.return_value = "Optimized prompt content"
    qwen_client._cfg = MagicMock(model="Qwen/Qwen3-Next-80B-A3B-Instruct")  # noqa: SLF001

    optimizer = PromptOptimizer(repo, qwen_client)

    payload = OptimizationPayload(
        alert_id="alert-1",
        prompt_version=None,
        failed_calls=[
            FailedCall(
                transcript="call text",
                customer_id=None,
                summary="customer hung up",
            )
        ],
        objectives=["Increase conversions"],
    )

    result = optimizer.optimize(payload)

    assert result.new_version.startswith("v")
    assert "total" in result.score_components
    assert result.improvement == result.score_components["total"]

    prompts = repo.list_prompts()
    assert len(prompts) >= 2  # seed + new

    runs = repo.recent_runs()
    assert runs[0].status == RunStatusEnum.COMPLETED
    assert runs[0].score_components is not None

    qwen_client.generate.assert_called_once()
