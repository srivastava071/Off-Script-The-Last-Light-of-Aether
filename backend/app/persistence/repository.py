"""SQLite persistence for runs. All writes for a run happen while the caller holds that run's lock."""

from pathlib import Path

from sqlalchemy import create_engine, event, select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.models.world import WorldState
from app.persistence.tables import Base, EventRow, MemoryRow, RunRow, SnapshotRow

IMPORTANT = 4


def make_engine(url: str) -> Engine:
    if url.startswith("sqlite:///") and ":memory:" not in url:
        Path(url.removeprefix("sqlite:///")).parent.mkdir(parents=True, exist_ok=True)
    kwargs: dict = {"connect_args": {"check_same_thread": False}} if url.startswith("sqlite") else {}
    if ":memory:" in url:
        kwargs["poolclass"] = StaticPool  # one shared in-memory database
    engine = create_engine(url, **kwargs)
    if url.startswith("sqlite"):
        @event.listens_for(engine, "connect")
        def _pragmas(conn, _record):  # noqa: ANN001
            cur = conn.cursor()
            cur.execute("PRAGMA foreign_keys=ON")
            cur.execute("PRAGMA journal_mode=WAL")
            cur.close()
    return engine


class RunRepository:
    def __init__(self, engine: Engine):
        self.engine = engine
        self.sessions = sessionmaker(engine, expire_on_commit=False)

    def create_schema(self) -> None:
        Base.metadata.create_all(self.engine)

    # --- writes --------------------------------------------------------------------------------------

    def create(self, world: WorldState, token_hash: str) -> None:
        with self.sessions.begin() as s:
            s.add(RunRow(
                id=world.run_id, token_hash=token_hash, mode=world.mode.value,
                player_character=world.story.player_character, status=world.story.status.value,
                sim_time=world.clock.now, last_event_seq=world.next_event_seq - 1,
                snapshot=world.model_dump(mode="json"),
            ))
            s.flush()  # the run row must exist before its events reference it
            self._append_events(s, world, after_seq=0)

    def save(self, world: WorldState, *, history: bool = False) -> None:
        """Store the latest snapshot and any new events; optionally also a history snapshot + memories."""
        with self.sessions.begin() as s:
            row = s.get(RunRow, world.run_id)
            if row is None:
                raise KeyError(world.run_id)
            self._append_events(s, world, after_seq=row.last_event_seq)
            snapshot = world.model_dump(mode="json")
            row.snapshot = snapshot
            row.status = world.story.status.value
            row.sim_time = world.clock.now
            row.last_event_seq = world.next_event_seq - 1
            row.ending = world.story.ending.ending.value if world.story.ending else None
            if history:
                s.add(SnapshotRow(run_id=world.run_id, sim_time=world.clock.now, snapshot=snapshot))
                self._save_memories(s, world)

    @staticmethod
    def _append_events(s: Session, world: WorldState, after_seq: int) -> None:
        rows = [
            EventRow(run_id=world.run_id, seq=e.seq, time=e.time, kind=e.kind.value, actor=e.actor,
                     location_id=e.location_id, description=e.description, data=e.data)
            for e in world.events if e.seq > after_seq
        ]
        s.add_all(rows)

    @staticmethod
    def _save_memories(s: Session, world: WorldState) -> None:
        rows = [
            {"run_id": world.run_id, "character_id": cid, "time": m.time, "description": m.description,
             "source": m.source, "importance": m.importance, "confidence": m.confidence}
            for cid, mind in world.minds.items() for m in mind.memories if m.importance >= IMPORTANT
        ]
        if rows:
            s.execute(sqlite_insert(MemoryRow).values(rows).on_conflict_do_nothing())

    # --- reads ----------------------------------------------------------------------------------------

    def load(self, run_id: str) -> tuple[WorldState, str] | None:
        with self.sessions() as s:
            row = s.get(RunRow, run_id)
            if row is None:
                return None
            return WorldState.model_validate(row.snapshot), row.token_hash

    def list_runs(self, limit: int = 20, status: str | None = None) -> list[RunRow]:
        with self.sessions() as s:
            q = select(RunRow).order_by(RunRow.updated_at.desc()).limit(limit)
            if status:
                q = q.where(RunRow.status == status)
            return list(s.scalars(q))

    def events(self, run_id: str, after_seq: int = 0) -> list[EventRow]:
        with self.sessions() as s:
            q = select(EventRow).where(EventRow.run_id == run_id, EventRow.seq > after_seq).order_by(EventRow.seq)
            return list(s.scalars(q))

    def memories(self, run_id: str) -> list[MemoryRow]:
        with self.sessions() as s:
            return list(s.scalars(select(MemoryRow).where(MemoryRow.run_id == run_id).order_by(MemoryRow.time)))

    def snapshot_count(self, run_id: str) -> int:
        with self.sessions() as s:
            return len(list(s.scalars(select(SnapshotRow.id).where(SnapshotRow.run_id == run_id))))
