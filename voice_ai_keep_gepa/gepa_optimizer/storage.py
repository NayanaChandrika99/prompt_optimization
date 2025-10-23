"""Persistence layer for GEPA optimizer prompts and runs."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum
from typing import Any

from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    create_engine,
)
from sqlalchemy import (
    Enum as SqlEnum,
)
from sqlalchemy import inspect, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class PromptRecord(Base):
    __tablename__ = "prompts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    version: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    is_active: Mapped[bool] = mapped_column(default=False, nullable=False)

    runs: Mapped[list[OptimizationRunRecord]] = relationship(
        "OptimizationRunRecord", back_populates="prompt", cascade="all, delete-orphan"
    )


class RunStatusEnum(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


class OptimizationRunRecord(Base):
    __tablename__ = "optimization_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    prompt_id: Mapped[int] = mapped_column(ForeignKey("prompts.id", ondelete="CASCADE"))
    alert_id: Mapped[str | None] = mapped_column(String(128))
    status: Mapped[RunStatusEnum] = mapped_column(SqlEnum(RunStatusEnum), nullable=False)
    model: Mapped[str] = mapped_column(String(128), nullable=False)
    previous_version: Mapped[str | None] = mapped_column(String(32))
    new_version: Mapped[str | None] = mapped_column(String(32))
    improvement: Mapped[float | None] = mapped_column(Float)
    duration_seconds: Mapped[float | None] = mapped_column(Float)
    score_components: Mapped[str | None] = mapped_column(Text)
    conversion_snapshot: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    prompt: Mapped[PromptRecord] = relationship("PromptRecord", back_populates="runs")


def create_engine_from_dsn(dsn: str | None):
    if not dsn:
        return None
    return create_engine(dsn, future=True)


def create_tables(engine) -> None:
    if engine is None:
        return
    Base.metadata.create_all(engine)
    try:
        inspector = inspect(engine)
        columns = {col["name"] for col in inspector.get_columns("optimization_runs")}
    except SQLAlchemyError:
        return

    desired_columns = {
        "score_components": "TEXT",
        "conversion_snapshot": "TEXT",
    }
    missing = [name for name in desired_columns if name not in columns]
    if not missing:
        return

    for column in missing:
        ddl = desired_columns[column]
        try:
            with engine.begin() as conn:
                conn.execute(
                    text(f"ALTER TABLE optimization_runs ADD COLUMN {column} {ddl}")
                )
        except SQLAlchemyError:
            # Ignore migration issues; column may already exist in concurrent runs.
            continue


def _dump_json(data: Any) -> str | None:
    if data is None:
        return None
    return json.dumps(data)


def _load_json(raw: str | None) -> Any:
    if not raw:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


@dataclass
class PromptVersion:
    version: str
    content: str
    notes: str | None
    created_at: datetime
    is_active: bool


@dataclass
class OptimizationRun:
    id: int
    status: RunStatusEnum
    model: str
    previous_version: str | None
    new_version: str | None
    improvement: float | None
    duration_seconds: float | None
    created_at: datetime
    completed_at: datetime | None
    notes: str | None
    score_components: dict[str, Any] | None
    conversion_snapshot: dict[str, Any] | None


class PromptRepository:
    """High-level API for prompt and run persistence."""

    def __init__(self, engine) -> None:
        self._engine = engine

    def get_active_prompt(self) -> PromptVersion | None:
        if self._engine is None:
            return None
        with Session(self._engine) as session:
            row = (
                session.query(PromptRecord)
                .filter(PromptRecord.is_active.is_(True))
                .order_by(PromptRecord.created_at.desc())
                .first()
            )
            if row is None:
                return None
            return PromptVersion(
                version=row.version,
                content=row.content,
                notes=row.notes,
                created_at=row.created_at,
                is_active=row.is_active,
            )

    def list_prompts(self, limit: int = 20) -> list[PromptVersion]:
        if self._engine is None:
            return []
        with Session(self._engine) as session:
            rows = (
                session.query(PromptRecord)
                .order_by(PromptRecord.created_at.desc())
                .limit(limit)
                .all()
            )
            return [
                PromptVersion(
                    version=row.version,
                    content=row.content,
                    notes=row.notes,
                    created_at=row.created_at,
                    is_active=row.is_active,
                )
                for row in rows
            ]

    def create_prompt(self, version: str, content: str, notes: str | None) -> PromptVersion:
        if self._engine is None:
            raise RuntimeError("Database engine is not configured")
        with Session(self._engine) as session:
            # Deactivate previous active prompt
            session.query(PromptRecord).filter(PromptRecord.is_active.is_(True)).update(
                {PromptRecord.is_active: False}
            )
            record = PromptRecord(version=version, content=content, notes=notes, is_active=True)
            session.add(record)
            session.commit()
            session.refresh(record)
            return PromptVersion(
                version=record.version,
                content=record.content,
                notes=record.notes,
                created_at=record.created_at,
                is_active=record.is_active,
            )

    def log_run(
        self,
        prompt_version: str,
        status: RunStatusEnum,
        *,
        alert_id: str | None = None,
        model: str,
        previous_version: str | None,
        new_version: str | None,
        improvement: float | None,
        duration_seconds: float | None,
        notes: str | None = None,
        score_components: dict[str, Any] | None = None,
        conversion_snapshot: dict[str, Any] | None = None,
    ) -> OptimizationRun:
        if self._engine is None:
            raise RuntimeError("Database engine is not configured")
        with Session(self._engine) as session:
            prompt = (
                session.query(PromptRecord)
                .filter(PromptRecord.version == prompt_version)
                .one()
            )
            record = OptimizationRunRecord(
                prompt=prompt,
                alert_id=alert_id,
                status=status,
                model=model,
                previous_version=previous_version,
                new_version=new_version,
                improvement=improvement,
                duration_seconds=duration_seconds,
                score_components=_dump_json(score_components),
                conversion_snapshot=_dump_json(conversion_snapshot),
                completed_at=datetime.now(UTC) if status == RunStatusEnum.COMPLETED else None,
                notes=notes,
            )
            session.add(record)
            session.commit()
            session.refresh(record)
            return OptimizationRun(
                id=record.id,
                status=record.status,
                model=record.model,
                previous_version=record.previous_version,
                new_version=record.new_version,
                improvement=record.improvement,
                duration_seconds=record.duration_seconds,
                created_at=record.created_at,
                completed_at=record.completed_at,
                notes=record.notes,
                score_components=_load_json(record.score_components),
                conversion_snapshot=_load_json(record.conversion_snapshot),
            )

    def recent_runs(self, limit: int = 10) -> list[OptimizationRun]:
        if self._engine is None:
            return []
        with Session(self._engine) as session:
            rows = (
                session.query(OptimizationRunRecord)
                .order_by(OptimizationRunRecord.created_at.desc())
                .limit(limit)
                .all()
            )
            return [
                OptimizationRun(
                    id=row.id,
                    status=row.status,
                    model=row.model,
                    previous_version=row.previous_version,
                    new_version=row.new_version,
                    improvement=row.improvement,
                duration_seconds=row.duration_seconds,
                created_at=row.created_at,
                completed_at=row.completed_at,
                notes=row.notes,
                score_components=_load_json(row.score_components),
                conversion_snapshot=_load_json(row.conversion_snapshot),
            )
            for row in rows
        ]

    def metrics(self) -> dict[str, Any]:
        if self._engine is None:
            return {
                "total_runs": 0,
                "success_rate": 0.0,
                "average_improvement": 0.0,
                "last_run_timestamp": None,
                "score_breakdown": {
                    "base": 0.0,
                    "failure_mix": 0.0,
                    "objective_alignment": 0.0,
                    "prompt_quality": 0.0,
                    "conversion_delta_score": 0.0,
                    "conversion_delta_rate": 0.0,
                    "objective_coverage_ratio": 0.0,
                    "total": 0.0,
                },
                "latest_conversion_snapshot": None,
            }
        with Session(self._engine) as session:
            total = session.query(OptimizationRunRecord).count()
            completed = (
                session.query(OptimizationRunRecord)
                .filter(OptimizationRunRecord.status == RunStatusEnum.COMPLETED)
                .count()
            )
            improvement_rows = (
                session.query(OptimizationRunRecord.improvement)
                .filter(OptimizationRunRecord.improvement.isnot(None))
                .all()
            )
            improvements = [value for (value,) in improvement_rows if value is not None]
            last_run = (
                session.query(OptimizationRunRecord.created_at)
                .order_by(OptimizationRunRecord.created_at.desc())
                .first()
            )
            component_rows = (
                session.query(OptimizationRunRecord.score_components)
                .filter(OptimizationRunRecord.score_components.isnot(None))
                .all()
            )
            breakdown_keys = [
                "base",
                "failure_mix",
                "objective_alignment",
                "prompt_quality",
                "conversion_delta_score",
                "objective_coverage_ratio",
                "conversion_delta_rate",
                "total",
            ]
            breakdown_totals = {key: 0.0 for key in breakdown_keys}
            component_count = 0
            for (raw_components,) in component_rows:
                data = _load_json(raw_components)
                if not isinstance(data, dict):
                    continue
                component_count += 1
                for key in breakdown_keys:
                    breakdown_totals[key] += float(data.get(key) or 0.0)

            score_breakdown = {key: 0.0 for key in breakdown_keys}
            if component_count:
                score_breakdown = {
                    key: round(breakdown_totals[key] / component_count, 4)
                    for key in breakdown_keys
                }

            latest_snapshot_row = (
                session.query(OptimizationRunRecord.conversion_snapshot)
                .order_by(OptimizationRunRecord.created_at.desc())
                .first()
            )
            latest_snapshot = (
                _load_json(latest_snapshot_row[0]) if latest_snapshot_row else None
            )
            avg_improvement = (
                sum(improvements) / len(improvements)
                if improvements
                else 0.0
            )
            return {
                "total_runs": total,
                "success_rate": (completed / total) if total else 0.0,
                "average_improvement": avg_improvement,
                "last_run_timestamp": last_run[0].isoformat() if last_run else None,
                "score_breakdown": score_breakdown,
                "latest_conversion_snapshot": latest_snapshot,
            }
