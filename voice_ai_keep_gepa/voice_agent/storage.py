"""Database models and helpers for voice agent call logging."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, relationship

from .agent import CallOutcome, CallTurn, FailureReason, Intent


class Base(DeclarativeBase):
    pass


class CallRecord(Base):
    __tablename__ = "calls"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    dealership_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    prompt_version: Mapped[str] = mapped_column(String(32), nullable=False)
    intent: Mapped[Intent] = mapped_column(Enum(Intent), nullable=False)
    outcome: Mapped[str] = mapped_column(String(16), nullable=False)
    failure_reason: Mapped[FailureReason | None] = mapped_column(Enum(FailureReason))
    selected_slot: Mapped[str | None] = mapped_column(String(64))
    summary: Mapped[str] = mapped_column(String(512))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )

    messages: Mapped[list[CallMessageRecord]] = relationship(
        "CallMessageRecord", back_populates="call", cascade="all, delete-orphan"
    )


class CallMessageRecord(Base):
    __tablename__ = "call_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    call_id: Mapped[int] = mapped_column(ForeignKey("calls.id", ondelete="CASCADE"))
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    content: Mapped[str] = mapped_column(String(2048), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )

    call: Mapped[CallRecord] = relationship("CallRecord", back_populates="messages")


def create_engine_from_dsn(database_url: str | None):
    if not database_url:
        return None
    return create_engine(database_url, future=True)


def create_tables(engine) -> None:
    if engine is None:
        return
    Base.metadata.create_all(engine)


class CallRepository:
    """Persistence helper for call logs."""

    def __init__(self, engine) -> None:
        self._engine = engine

    def log_call(
        self,
        dealership_id: str,
        prompt_version: str,
        outcome: CallOutcome,
        turns: Iterable[CallTurn],
    ) -> None:
        if self._engine is None:
            return
        record = CallRecord(
            dealership_id=dealership_id,
            prompt_version=prompt_version,
            intent=outcome.intent,
            outcome="success" if outcome.success else "failure",
            failure_reason=outcome.failure_reason,
            selected_slot=outcome.selected_slot,
            summary=outcome.summary,
        )
        record.messages = [
            CallMessageRecord(role=turn.role, content=turn.content) for turn in turns
        ]
        with Session(self._engine) as session:
            session.add(record)
            session.commit()
