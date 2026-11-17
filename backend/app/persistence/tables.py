from datetime import UTC, datetime
from typing import Any

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def _now() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


class RunRow(Base):
    """One playthrough: its latest full snapshot plus searchable summary columns."""

    __tablename__ = "runs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    token_hash: Mapped[str] = mapped_column(String(64))
    mode: Mapped[str] = mapped_column(String(16))
    player_character: Mapped[str | None] = mapped_column(String(32), nullable=True)
    status: Mapped[str] = mapped_column(String(16), index=True)
    ending: Mapped[str | None] = mapped_column(String(32), nullable=True)
    sim_time: Mapped[int] = mapped_column(Integer, default=0)
    last_event_seq: Mapped[int] = mapped_column(Integer, default=0)
    snapshot: Mapped[dict[str, Any]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)


class EventRow(Base):
    """Append-only event history."""

    __tablename__ = "run_events"
    __table_args__ = (UniqueConstraint("run_id", "seq"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id", ondelete="CASCADE"), index=True)
    seq: Mapped[int] = mapped_column(Integer)
    time: Mapped[int] = mapped_column(Integer)
    kind: Mapped[str] = mapped_column(String(32))
    actor: Mapped[str | None] = mapped_column(String(32), nullable=True)
    location_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    description: Mapped[str] = mapped_column(Text)
    data: Mapped[dict[str, Any]] = mapped_column(JSON)


class SnapshotRow(Base):
    """Periodic full snapshots, for replay and analysis."""

    __tablename__ = "run_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id", ondelete="CASCADE"), index=True)
    sim_time: Mapped[int] = mapped_column(Integer)
    snapshot: Mapped[dict[str, Any]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class MemoryRow(Base):
    """Important character memories (importance >= 4), kept beyond in-run compaction."""

    __tablename__ = "run_memories"
    __table_args__ = (UniqueConstraint("run_id", "character_id", "time", "description"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id", ondelete="CASCADE"), index=True)
    character_id: Mapped[str] = mapped_column(String(32))
    time: Mapped[int] = mapped_column(Integer)
    description: Mapped[str] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(32))
    importance: Mapped[int] = mapped_column(Integer)
    confidence: Mapped[float] = mapped_column(Float)


class LessonRow(Base):
    """Team journal: a lesson the characters learned in one Watch run and tested in the next.

    ``status`` is "trying" (being tested in the next Watch run), "kept" (it helped) or "rejected".
    """

    __tablename__ = "lessons"
    __table_args__ = (UniqueConstraint("character_id", "instead_of", "prefer"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    character_id: Mapped[str] = mapped_column(String(32))
    instead_of: Mapped[str] = mapped_column(String(64))
    prefer: Mapped[str] = mapped_column(String(64))
    text: Mapped[str] = mapped_column(Text)
    evidence: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16), index=True)
    learned_in_run: Mapped[str] = mapped_column(String(64))
    baseline_ending: Mapped[str] = mapped_column(String(32))
    baseline_seconds: Mapped[int] = mapped_column(Integer)
    tested_in_run: Mapped[str | None] = mapped_column(String(64), nullable=True)
    tested_ending: Mapped[str | None] = mapped_column(String(32), nullable=True)
    tested_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    result: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class JournalRunRow(Base):
    """One finished run as the team journal saw it: the learning curve, and what was learned or tested."""

    __tablename__ = "journal_runs"

    run_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    mode: Mapped[str] = mapped_column(String(16))
    player_character: Mapped[str | None] = mapped_column(String(32), nullable=True)
    ending: Mapped[str] = mapped_column(String(32))
    finished_at: Mapped[int] = mapped_column(Integer)
    lessons_used: Mapped[list[int]] = mapped_column(JSON)
    note: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
