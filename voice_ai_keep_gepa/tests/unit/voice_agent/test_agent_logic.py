from __future__ import annotations

from voice_ai_keep_gepa.voice_agent.agent import CallContext, VoiceAgent


def build_context(available_slots):
    return CallContext(
        dealership_id="dealer-1",
        prompt_version="v1.0",
        available_slots=list(available_slots),
        knowledge_base={"hours": "We open at 8am."},
    )


def test_booking_intent_selects_first_slot():
    agent = VoiceAgent()
    context = build_context(["Friday 3pm", "Friday 4pm"])

    outcome = agent.handle_call("Please book me for Friday afternoon", context)

    assert outcome.success is True
    assert outcome.selected_slot == "Friday 3pm"
    assert outcome.intent.value == "book_service_appointment"


def test_reschedule_prefers_second_slot_when_available():
    agent = VoiceAgent()
    context = build_context(["Monday 9am", "Tuesday 1pm"])

    outcome = agent.handle_call("I need to reschedule my appointment", context)

    assert outcome.selected_slot == "Tuesday 1pm"
    assert outcome.intent.value == "reschedule_appointment"


def test_no_slots_results_in_failure_reason():
    agent = VoiceAgent()
    context = build_context([])

    outcome = agent.handle_call("Can you schedule me tomorrow?", context)

    assert outcome.success is False
    assert outcome.failure_reason.value == "no_slots"


def test_general_question_uses_knowledge_base():
    agent = VoiceAgent()
    context = build_context(["Friday 3pm"])

    outcome = agent.handle_call("What are your service center hours?", context)

    assert outcome.success is True
    assert "open" in outcome.turns[-1].content.lower()
