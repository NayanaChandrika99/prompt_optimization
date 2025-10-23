from __future__ import annotations

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from voice_ai_keep_gepa.voice_agent.agent import CallContext, VoiceAgent
from voice_ai_keep_gepa.voice_agent.storage import (
    CallMessageRecord,
    CallRecord,
    CallRepository,
    create_tables,
)


def test_repository_persists_call_records():
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    create_tables(engine)
    repository = CallRepository(engine)

    agent = VoiceAgent()
    context = CallContext(
        dealership_id="dealer-42",
        prompt_version="v1.0",
        available_slots=["Friday 2pm"],
        knowledge_base={},
    )

    outcome = agent.handle_call("Please book me for Friday afternoon", context)
    repository.log_call(context.dealership_id, context.prompt_version, outcome, outcome.turns)

    with Session(engine) as session:
        call_row = session.execute(select(CallRecord)).scalar_one()
        assert call_row.dealership_id == "dealer-42"
        assert call_row.outcome == "success"
        messages = (
            session.execute(select(CallMessageRecord).order_by(CallMessageRecord.id)).scalars().all()
        )
        assert len(messages) == len(outcome.turns)
