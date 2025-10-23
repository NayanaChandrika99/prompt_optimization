"""GEPA optimization workflow orchestrator."""

from __future__ import annotations

import textwrap
import time
from dataclasses import dataclass
from typing import Any

from voice_ai_keep_gepa.voice_agent.agent import FailureReason
from voice_ai_keep_gepa.voice_agent.objectives import derive_objectives

from .qwen_client import QwenClient
from .scoring import ScoreBreakdown, ScoreConfig, compute_score
from .schemas import FailedCall, OptimizationPayload, OptimizationResult
from .storage import PromptRepository, PromptVersion, RunStatusEnum
from .voice_metrics_client import VoiceMetricsClient

DEFAULT_PROMPT = textwrap.dedent(
    """
    You are Ava, the virtual voice agent for Toma Motors. Your responsibilities:
    - Diagnose customer intent quickly.
    - Confirm vehicle details and preferred appointment slots.
    - Offer relevant upsells when appropriate.
    - Remain polite, concise, and confident.

    Always summarize the outcome and confirm next steps before ending the call.
    """
).strip()


@dataclass
class OptimizationContext:
    payload: OptimizationPayload
    active_prompt: PromptVersion
    objectives: list[str]


class PromptOptimizer:
    def __init__(
        self,
        repository: PromptRepository,
        qwen_client: QwenClient,
        *,
        metrics_client: VoiceMetricsClient | None = None,
        score_config: ScoreConfig | None = None,
    ) -> None:
        self._repository = repository
        self._client = qwen_client
        self._metrics_client = metrics_client
        self._score_config = score_config or ScoreConfig.from_env()

    def optimize(self, payload: OptimizationPayload) -> OptimizationResult:
        active_prompt = self._ensure_active_prompt(payload.prompt_version)
        if payload.objectives:
            objectives = payload.objectives
        else:
            failure_enums: list[FailureReason | None] = []
            for call in payload.failed_calls:
                code = call.failure_reason
                if code:
                    try:
                        failure_enums.append(FailureReason(code))
                    except ValueError:
                        failure_enums.append(None)
                else:
                    failure_enums.append(None)
            objectives = derive_objectives(failure_enums)
        context = OptimizationContext(
            payload=payload,
            active_prompt=active_prompt,
            objectives=objectives,
        )

        baseline_metrics: dict[str, Any] | None = None
        if self._metrics_client:
            baseline_metrics = self._metrics_client.fetch_snapshot()

        previous_runs = self._repository.recent_runs(limit=1)
        previous_metrics: dict[str, Any] | None = (
            previous_runs[0].conversion_snapshot if previous_runs else None
        )

        start = time.perf_counter()
        qwen_response = self._client.generate(
            prompt=self._build_prompt(context),
            system_prompt=(
                "You are a prompt engineering expert improving contact-center voice agents."
            ),
            max_tokens=256,
            temperature=0.4,
        )
        elapsed = time.perf_counter() - start

        new_version = self._next_version(context.active_prompt.version)
        combined_prompt = self._compose_prompt(context.active_prompt.content, qwen_response)
        notes = self._summarize_notes(
            context.payload.failed_calls,
            qwen_response,
            context.objectives,
        )

        new_prompt = self._repository.create_prompt(new_version, combined_prompt, notes)

        score_breakdown = self._evaluate_score(
            failed_calls=context.payload.failed_calls,
            prompt_text=combined_prompt,
            objectives=context.objectives,
            current_metrics=baseline_metrics,
            previous_metrics=previous_metrics,
        )
        score_components = score_breakdown.as_dict(max_total=self._score_config.max_total)
        improvement = score_components["total"]

        run = self._repository.log_run(
            prompt_version=new_prompt.version,
            status=RunStatusEnum.COMPLETED,
            alert_id=payload.alert_id,
            model=self._client._cfg.model,  # pylint: disable=protected-access
            previous_version=context.active_prompt.version,
            new_version=new_prompt.version,
            improvement=improvement,
            duration_seconds=elapsed,
            notes=notes,
            score_components=score_components,
            conversion_snapshot=baseline_metrics,
        )

        return OptimizationResult(
            alert_id=payload.alert_id,
            run_id=run.id,
            previous_version=context.active_prompt.version,
            new_version=new_prompt.version,
            improvement=improvement,
            duration_seconds=elapsed,
            prompt_preview=combined_prompt[:400],
            score_components=score_components,
        )

    def _ensure_active_prompt(self, requested_version: str | None) -> PromptVersion:
        prompt = self._repository.get_active_prompt()
        if prompt and (requested_version is None or prompt.version == requested_version):
            return prompt
        if requested_version:
            prompts = {p.version: p for p in self._repository.list_prompts(limit=50)}
            if requested_version in prompts:
                return prompts[requested_version]
        # Seed default prompt
        return self._repository.create_prompt("v1", DEFAULT_PROMPT, "Seed prompt")

    def _build_prompt(self, context: OptimizationContext) -> str:
        bullet_failures = "\n".join(
            f"- {call.summary or call.transcript[:120]}" for call in context.payload.failed_calls
        )
        objectives = "\n".join(f"* {obj}" for obj in context.objectives) or (
            "* Increase successful call resolutions by 10%"
        )
        return textwrap.dedent(
            f"""
            Current prompt (version {context.active_prompt.version}):
            ```
            {context.active_prompt.content}
            ```

            Failed calls (latest {len(context.payload.failed_calls)}):
            {bullet_failures}

            Objectives:
            {objectives}

            Produce an updated prompt that keeps the strengths of the existing one
            while addressing the failures.
            Respond with the full updated prompt text only.
            """
        ).strip()

    def _compose_prompt(self, existing_prompt: str, qwen_response: str) -> str:
        if "```" in qwen_response:
            # extract fenced block if present
            segments = qwen_response.split("```")
            if len(segments) >= 3:
                return segments[1 if segments[1].strip() else 2].strip()
        return qwen_response.strip() or existing_prompt

    def _summarize_notes(
        self,
        failed_calls: list[FailedCall],
        qwen_response: str,
        objectives: list[str] | None = None,
    ) -> str:
        snippet = qwen_response.strip().splitlines()[0][:160]
        objectives_text = ", ".join(objectives or [])
        return textwrap.dedent(
            f"""
            Updated to address {len(failed_calls)} failures.
            Objectives: {objectives_text or 'n/a'}
            First line of model response: {snippet}
            """
        ).strip()

    def _evaluate_score(
        self,
        *,
        failed_calls: list[FailedCall],
        prompt_text: str,
        objectives: list[str],
        current_metrics: dict[str, Any] | None,
        previous_metrics: dict[str, Any] | None,
    ) -> ScoreBreakdown:
        failed_call_dicts = [self._serialize_failed_call(call) for call in failed_calls]
        return compute_score(
            config=self._score_config,
            failed_calls=failed_call_dicts,
            prompt_text=prompt_text,
            objectives=objectives,
            current_metrics=current_metrics,
            previous_metrics=previous_metrics,
        )

    @staticmethod
    def _serialize_failed_call(call: FailedCall) -> dict[str, Any]:
        return {
            "transcript": call.transcript,
            "summary": call.summary,
            "failure_reason": call.failure_reason,
            "customer_id": call.customer_id,
        }

    def _next_version(self, current_version: str) -> str:
        if current_version.lower().startswith("v"):
            try:
                number = int(current_version[1:]) + 1
                return f"v{number}"
            except ValueError:
                pass
        timestamp = int(time.time())
        return f"v{timestamp}"
