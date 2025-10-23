"""Core voice agent logic for Phase 2.

This module approximates a DSPy-style agent using deterministic heuristics so that
unit tests and simulators can run without external LLM calls. The interface is designed
to be swappable with a true DSPy implementation in later phases.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from enum import Enum


class Intent(str, Enum):
    """Supported customer intents."""

    BOOK_SERVICE_APPOINTMENT = "book_service_appointment"
    RESCHEDULE_APPOINTMENT = "reschedule_appointment"
    GENERAL_QUESTION = "general_question"
    UNKNOWN = "unknown"


class FailureReason(str, Enum):
    """Canonical failure reasons for metrics and storage."""

    NO_SLOTS = "no_slots"
    CUSTOMER_DISENGAGED = "customer_disengaged"
    AGENT_CONFIDENCE_LOW = "agent_confidence_low"
    UNKNOWN = "unknown"


@dataclass
class CallTurn:
    """Single conversation exchange."""

    role: str
    content: str


@dataclass
class CallContext:
    """Invocation context for a call."""

    dealership_id: str
    prompt_version: str
    available_slots: list[str]
    knowledge_base: dict[str, str]


@dataclass
class CallOutcome:
    """Result of a processed call."""

    success: bool
    intent: Intent
    selected_slot: str | None = None
    failure_reason: FailureReason | None = None
    summary: str = ""
    turns: list[CallTurn] = field(default_factory=list)


class VoiceAgent:
    """Deterministic voice agent scaffold."""

    def __init__(self, greeting: str | None = None) -> None:
        self.greeting = greeting or (
            "Thank you for calling Toma Motors. I'm Ava, your virtual assistant."
        )

    def handle_call(self, request: str, context: CallContext) -> CallOutcome:
        """Process a customer request and return the conversation transcript + outcome."""
        turns: list[CallTurn] = [CallTurn(role="agent", content=self.greeting)]
        intent = self._classify_intent(request)
        turns.append(CallTurn(role="customer", content=request))

        if self._customer_disengaged(request):
            return CallOutcome(
                success=False,
                intent=intent,
                failure_reason=FailureReason.CUSTOMER_DISENGAGED,
                summary="Customer ended the conversation abruptly.",
                turns=turns + [CallTurn("agent", "I'm here if you need any assistance later.")],
            )

        if intent is Intent.GENERAL_QUESTION:
            answer = self._answer_question(request, context.knowledge_base)
            turns.append(CallTurn("agent", answer))
            return CallOutcome(
                success=True,
                intent=intent,
                summary="Provided FAQ response.",
                turns=turns,
            )

        if intent in (Intent.BOOK_SERVICE_APPOINTMENT, Intent.RESCHEDULE_APPOINTMENT):
            slot = self._select_slot(context.available_slots, intent)
            if slot is None:
                turns.append(
                    CallTurn(
                        "agent",
                        "I apologise, but I do not have any open slots for that timeframe. "
                        "Would you like me to add you to the waitlist?",
                    )
                )
                return CallOutcome(
                    success=False,
                    intent=intent,
                    failure_reason=FailureReason.NO_SLOTS,
                    summary="Unable to secure appointment; no slots available.",
                    turns=turns,
                )

            confirmation = (
                f"I have scheduled you for {slot}. Does that work for you?"
                if intent is Intent.BOOK_SERVICE_APPOINTMENT
                else f"I've moved your appointment to {slot}. Anything else I can assist with?"
            )
            turns.append(CallTurn("agent", confirmation))

            return CallOutcome(
                success=True,
                intent=intent,
                selected_slot=slot,
                summary=f"Appointment confirmed for {slot}.",
                turns=turns,
            )

        # Unknown intent path
        clarification = (
            "I want to make sure I help you correctly. Could you please share more details "
            "about what you need today?"
        )
        turns.append(CallTurn("agent", clarification))
        return CallOutcome(
            success=False,
            intent=Intent.UNKNOWN,
            failure_reason=FailureReason.AGENT_CONFIDENCE_LOW,
            summary="Unable to determine customer intent.",
            turns=turns,
        )

    def _classify_intent(self, request: str) -> Intent:
        lowered = request.lower()
        if any(keyword in lowered for keyword in ("reschedule", "change", "move", "another time")):
            return Intent.RESCHEDULE_APPOINTMENT
        if any(keyword in lowered for keyword in ("price", "hours", "location", "question", "how")):
            return Intent.GENERAL_QUESTION
        if any(keyword in lowered for keyword in ("book", "schedule", "appointment", "service")):
            return Intent.BOOK_SERVICE_APPOINTMENT
        return Intent.UNKNOWN

    def _customer_disengaged(self, request: str) -> bool:
        lowered = request.lower()
        return any(keyword in lowered for keyword in ("nevermind", "hang up", "forget it", "bye"))

    def _answer_question(self, request: str, knowledge_base: dict[str, str]) -> str:
        lowered = request.lower()
        for keyword, answer in knowledge_base.items():
            if keyword.lower() in lowered:
                return answer
        return (
            "Great question! Our service center operates Monday through Saturday, 8am to 6pm. "
            "Let me know if you would like to book an appointment."
        )

    def _select_slot(self, slots: Iterable[str], intent: Intent) -> str | None:
        slot_list = list(slots)
        if not slot_list:
            return None
        if intent is Intent.RESCHEDULE_APPOINTMENT and len(slot_list) > 1:
            return slot_list[1]
        return slot_list[0]
