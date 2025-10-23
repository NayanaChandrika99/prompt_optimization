"""Objective generation utilities for optimisation payloads."""

from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path

from .agent import FailureReason

BASE_DIR = Path(__file__).resolve().parents[2]
OBJECTIVE_RULES_PATH = BASE_DIR / "data" / "objective_rules.json"


def load_objective_rules() -> dict[str, list[str]]:
    if OBJECTIVE_RULES_PATH.exists():
        return json.loads(OBJECTIVE_RULES_PATH.read_text())
    return {}


def derive_objectives(failure_reasons: Iterable[FailureReason | None]) -> list[str]:
    rules = load_objective_rules()
    collected: list[str] = []
    for reason in failure_reasons:
        if reason is None:
            continue
        key = reason.value
        collected.extend(rules.get(key, []))
    if not collected:
        collected = rules.get("general", ["Improve customer experience and clarity"])
    # Deduplicate while preserving order
    seen = set()
    deduped = []
    for item in collected:
        if item not in seen:
            seen.add(item)
            deduped.append(item)
    return deduped
