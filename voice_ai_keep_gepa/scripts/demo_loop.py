"""End-to-end demo helper that drives the voice agent, optimizer, and dashboard."""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path
from typing import Any

import requests

PACKAGE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PACKAGE_ROOT not in sys.path:
    sys.path.insert(0, PACKAGE_ROOT)

from voice_ai_keep_gepa.voice_agent.simulate_calls import DEFAULT_SCENARIOS  # noqa: E402
from voice_ai_keep_gepa.voice_agent.objectives import derive_objectives  # noqa: E402
from voice_ai_keep_gepa.voice_agent.agent import FailureReason  # noqa: E402
from voice_ai_keep_gepa.scripts.replay_failed_calls import (  # noqa: E402
    DEFAULT_SOURCE,
    load_failed_calls,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Drive a full demo loop: seed calls, run optimizer, and print metrics."
    )
    parser.add_argument(
        "--voice-url",
        default=os.getenv("VOICE_AGENT_BASE_URL", "http://localhost:5100"),
        help="Base URL for the voice agent service.",
    )
    parser.add_argument(
        "--optimizer-url",
        default=os.getenv("GEPA_OPTIMIZER_BASE_URL", "http://localhost:8000"),
        help="Base URL for the GEPA optimizer service.",
    )
    parser.add_argument(
        "--success-calls",
        type=int,
        default=8,
        help="Number of initial successful calls to simulate.",
    )
    parser.add_argument(
        "--failure-calls",
        type=int,
        default=4,
        help="Number of initial failed calls to simulate.",
    )
    parser.add_argument(
        "--post-opt-success",
        type=int,
        default=10,
        help="Additional successes to run after the first optimisation (to change conversion delta).",
    )
    parser.add_argument(
        "--replay-limit",
        type=int,
        default=12,
        help="Failed call payload size when triggering optimisation runs.",
    )
    parser.add_argument(
        "--failed-call-source",
        default=str(DEFAULT_SOURCE),
        help="Path to the failed call JSONL library used for optimiser payloads.",
    )
    parser.add_argument(
        "--delay-seconds",
        type=float,
        default=1.0,
        help="Delay between major steps so dashboard auto-refresh has time to catch up.",
    )
    return parser.parse_args()


def post_simulated_call(base_url: str, payload: dict[str, Any]) -> dict[str, Any]:
    response = requests.post(f"{base_url.rstrip('/')}/simulate", json=payload, timeout=10)
    response.raise_for_status()
    return response.json()


def fetch_voice_metrics(base_url: str) -> dict[str, Any]:
    response = requests.get(f"{base_url.rstrip('/')}/metrics", timeout=10)
    response.raise_for_status()
    return response.json()


def build_optimizer_payload(source: str, limit: int) -> dict[str, Any]:
    records = load_failed_calls(Path(source).resolve(), limit)
    failure_codes: list[FailureReason | None] = []
    failed_calls_payload: list[dict[str, Any]] = []
    for record in records:
        failure_code = record.get("failure_reason")
        enum_value: FailureReason | None = None
        if failure_code:
            try:
                enum_value = FailureReason(failure_code)
            except ValueError:
                enum_value = None
        failure_codes.append(enum_value)
        failed_calls_payload.append(
            {
                "transcript": record.get("transcript", ""),
                "summary": record.get("summary"),
                "failure_reason": failure_code,
            }
        )
    objectives = derive_objectives(failure_codes)
    return {
        "alert_id": "demo-loop",
        "failed_calls": failed_calls_payload,
        "objectives": objectives,
    }


def trigger_optimization(base_url: str, payload: dict[str, Any]) -> dict[str, Any]:
    response = requests.post(f"{base_url.rstrip('/')}/optimize", json=payload, timeout=30)
    response.raise_for_status()
    return response.json()


def print_section(title: str, data: Any) -> None:
    print(f"\n=== {title} ===")
    if isinstance(data, dict):
        for key, value in data.items():
            print(f"{key}: {value}")
    else:
        print(data)


def main() -> None:
    args = parse_args()

    success_scenario = next(s for s in DEFAULT_SCENARIOS if s.expect_success)
    failure_scenario = next(s for s in DEFAULT_SCENARIOS if not s.expect_success)

    print("Seeding baseline calls...")
    for _ in range(args.success_calls):
        post_simulated_call(
            args.voice_url,
            {
                "customer_request": success_scenario.customer_request,
                "available_slots": success_scenario.available_slots,
                "dealership_id": "dealer-demo",
                "prompt_version": "v1.0",
            },
        )
    for _ in range(args.failure_calls):
        post_simulated_call(
            args.voice_url,
            {
                "customer_request": failure_scenario.customer_request,
                "available_slots": failure_scenario.available_slots,
                "dealership_id": "dealer-demo",
                "prompt_version": "v1.0",
            },
        )

    metrics = fetch_voice_metrics(args.voice_url)
    print_section("Voice metrics after seeding", metrics)
    time.sleep(args.delay_seconds)

    payload = build_optimizer_payload(args.failed_call_source, args.replay_limit)
    print_section("Derived objectives", payload["objectives"])

    first_run = trigger_optimization(args.optimizer_url, payload)
    print_section("First optimisation run", first_run)
    time.sleep(args.delay_seconds)

    if args.post_opt_success > 0:
        print("Raising conversion rate with additional successes...")
        for _ in range(args.post_opt_success):
            post_simulated_call(
                args.voice_url,
                {
                    "customer_request": success_scenario.customer_request,
                    "available_slots": success_scenario.available_slots,
                    "dealership_id": "dealer-demo",
                    "prompt_version": first_run["new_version"],
                },
            )

        metrics = fetch_voice_metrics(args.voice_url)
        print_section("Voice metrics after conversion bump", metrics)
        time.sleep(args.delay_seconds)

        second_run = trigger_optimization(args.optimizer_url, payload)
        print_section("Second optimisation run", second_run)

    final_response = requests.get(f"{args.optimizer_url.rstrip('/')}/metrics", timeout=10)
    final_response.raise_for_status()
    final_metrics = final_response.json()
    score_breakdown = final_metrics.get("score_breakdown", {})
    print_section("Optimizer score breakdown (averaged)", score_breakdown)


if __name__ == "__main__":
    main()
