"""Replay failed calls into the GEPA optimizer for richer prompt updates."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import requests

import sys

BASE_DIR = Path(__file__).resolve().parents[2]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from voice_ai_keep_gepa.voice_agent.agent import FailureReason
from voice_ai_keep_gepa.voice_agent.objectives import derive_objectives

DEFAULT_SOURCE = Path(__file__).resolve().parents[2] / "data" / "failed_calls.jsonl"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Replay failed call transcripts into the optimizer."
    )
    parser.add_argument(
        "--endpoint",
        default="http://localhost:8000/optimize",
        help="Optimizer /optimize endpoint",
    )
    parser.add_argument(
        "--source",
        default=str(DEFAULT_SOURCE),
        help="Path to JSONL file with failed calls",
    )
    parser.add_argument("--alert-id", default="replay", help="Alert id prefix")
    parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Maximum number of failed calls to replay",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only print payload without posting",
    )
    return parser.parse_args()


def load_failed_calls(path: Path, limit: int | None = None) -> list[dict]:
    calls: list[dict] = []
    if not path.exists():
        raise FileNotFoundError(f"Failed call library not found at {path}")
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        calls.append(json.loads(line))
        if limit is not None and len(calls) >= limit:
            break
    return calls


def main() -> None:
    args = parse_args()
    source_path = Path(args.source)
    failed_records = load_failed_calls(source_path, args.limit)

    failure_codes: list[FailureReason | None] = []
    failed_calls_payload: list[dict] = []
    for record in failed_records:
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
    payload = {
        "alert_id": f"{args.alert_id}-batch",
        "failed_calls": failed_calls_payload,
        "objectives": objectives,
    }

    if args.dry_run:
        print(json.dumps(payload, indent=2))
        return

    response = requests.post(args.endpoint, json=payload, timeout=60)
    response.raise_for_status()
    print(json.dumps(response.json(), indent=2))


if __name__ == "__main__":
    main()
