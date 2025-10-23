"""Deterministic simulator for dealership call scenarios."""

from __future__ import annotations

import argparse
import json
import random
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from .agent import CallContext, VoiceAgent
from .metrics import MetricsAggregator
from .storage import CallRepository, create_engine_from_dsn, create_tables


@dataclass
class SimulationScenario:
    """A scripted customer request."""

    name: str
    customer_request: str
    available_slots: list[str]
    expect_success: bool
    transcript: str | None = None
    summary: str | None = None
    failure_reason: str | None = None


DEFAULT_SCENARIOS: list[SimulationScenario] = [
    SimulationScenario(
        name="happy_path_booking",
        customer_request=(
            "Hi, I'd like to book a service appointment for my Camry on Friday afternoon."
        ),
        available_slots=["Friday 3pm", "Friday 4pm"],
        expect_success=True,
        transcript="Agent confirmed service appointment for Friday 3pm without issues.",
        summary="Quick confirmation",
        failure_reason=None,
    ),
    SimulationScenario(
        name="no_slots_available",
        customer_request="Can you schedule me for tomorrow morning?",
        available_slots=[],
        expect_success=False,
        transcript="\n".join(
            [
                "Customer: Can you schedule me for tomorrow morning?",
                "Agent: Let me check... the earliest I see is Friday afternoon.",
                "Customer: Is there any cancellation list?",
                "Agent: I'm afraid not. You'll have to call back later.",
                "Customer: That's frustrating, goodbye.",
            ]
        ),
        summary="Customer requested morning slot; agent offered no alternative.",
        failure_reason="no_slots",
    ),
    SimulationScenario(
        name="reschedule",
        customer_request="I need to reschedule my oil change to next Tuesday if possible.",
        available_slots=["Monday 9am", "Tuesday 1pm", "Wednesday 2pm"],
        expect_success=True,
        transcript="Agent rescheduled oil change successfully to Tuesday 1pm.",
        summary="Successful reschedule.",
        failure_reason=None,
    ),
    SimulationScenario(
        name="general_question",
        customer_request="What are your service center hours on Saturday?",
        available_slots=["Saturday 10am"],
        expect_success=True,
        transcript="Agent clarified weekend hours and offered to book a slot.",
        summary="Answered general question.",
        failure_reason=None,
    ),
    SimulationScenario(
        name="customer_disengaged",
        customer_request="Nevermind, I'll call back later.",
        available_slots=["Thursday 10am"],
        expect_success=False,
        transcript=(
            "Customer expressed frustration about wait time and hung up before agent could "
            "offer solution."
        ),
        summary="Customer disengaged after perceived poor service.",
        failure_reason="customer_disengaged",
    ),
]

FAILED_CALL_LIBRARY = Path(__file__).resolve().parents[2] / "data" / "failed_calls.jsonl"


def load_knowledge_base() -> dict[str, str]:
    return {
        "hours": "We are open Monday through Saturday, 8am to 6pm.",
        "location": "You can find us at 123 Toma Drive, right off Highway 280.",
        "price": "Standard maintenance packages start at $149, including a multi-point inspection.",
    }


def load_failed_call_library() -> list[SimulationScenario]:
    scenarios: list[SimulationScenario] = []
    if FAILED_CALL_LIBRARY.exists():
        for line in FAILED_CALL_LIBRARY.read_text().splitlines():
            if not line.strip():
                continue
            record = json.loads(line)
            scenarios.append(
                SimulationScenario(
                    name=record.get("scenario", "library_case"),
                    customer_request=record.get("transcript", ""),
                    available_slots=[],
                    expect_success=False,
                    transcript=record.get("transcript"),
                    summary=record.get("summary"),
                    failure_reason=record.get("failure_reason"),
                )
            )
    return scenarios


def run_simulation(
    dealerships: int,
    runs: int,
    scenarios: Iterable[SimulationScenario],
    seed: int,
    metrics: MetricsAggregator,
    repository: CallRepository | None = None,
) -> list[dict[str, object]]:
    rng = random.Random(seed)  # noqa: S311 - deterministic simulator RNG
    agent = VoiceAgent()
    knowledge_base = load_knowledge_base()

    results: list[dict[str, object]] = []
    scenario_list = list(scenarios) + load_failed_call_library()
    if not scenario_list:
        scenario_list = list(scenarios)

    for dealership_index in range(dealerships):
        dealership_id = f"dealer-{dealership_index+1}"
        prompt_version = "v1.0"
        for _ in range(runs):
            scenario = rng.choice(scenario_list)
            context = CallContext(
                dealership_id=dealership_id,
                prompt_version=prompt_version,
                available_slots=scenario.available_slots,
                knowledge_base=knowledge_base,
            )
            outcome = agent.handle_call(scenario.customer_request, context)
            if scenario.summary:
                outcome.summary = scenario.summary
            metrics.record(dealership_id, prompt_version, outcome)
            if repository is not None:
                repository.log_call(dealership_id, prompt_version, outcome, outcome.turns)
            results.append(
                {
                    "dealership_id": dealership_id,
                    "scenario": scenario.name,
                    "success": outcome.success,
                    "intent": outcome.intent.value,
                    "selected_slot": outcome.selected_slot,
                    "failure_reason": (
                        outcome.failure_reason.value if outcome.failure_reason else None
                    ),
                    "summary": outcome.summary,
                    "transcript": scenario.transcript,
                    "failure_reason_code": scenario.failure_reason,
                }
            )
    return results


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Simulate dealership voice agent calls.")
    parser.add_argument(
        "--dealerships",
        type=int,
        default=1,
        help="Number of dealerships to simulate.",
    )
    parser.add_argument("--runs", type=int, default=5, help="Number of calls per dealership.")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for deterministic runs.")
    parser.add_argument(
        "--database-url",
        type=str,
        default=None,
        help="Optional database URL to persist call logs.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Optional path to write simulation results JSON.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    metrics = MetricsAggregator()
    engine = create_engine_from_dsn(args.database_url)
    create_tables(engine)
    repository = CallRepository(engine) if engine is not None else None

    results = run_simulation(
        dealerships=args.dealerships,
        runs=args.runs,
        scenarios=DEFAULT_SCENARIOS,
        seed=args.seed,
        metrics=metrics,
        repository=repository,
    )

    payload = {
        "metrics": metrics.snapshot(),
        "recent_calls": metrics.recent_calls(),
        "calls": results,
    }

    if args.output:
        args.output.write_text(json.dumps(payload, indent=2))
        print(f"Wrote simulation summary to {args.output}")
    else:
        print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
