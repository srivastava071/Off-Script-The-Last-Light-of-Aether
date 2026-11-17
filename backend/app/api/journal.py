"""The team journal: lessons the characters carry from one game to the next (no run token needed)."""

from datetime import datetime

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from app.agents.learning import ENDING_TITLES
from app.models.enums import EndingId
from app.services.journal import NAMES
from app.services.run_manager import RunManager

router = APIRouter(prefix="/api/journal", tags=["journal"])


class LessonView(BaseModel):
    id: int
    character_id: str
    character: str
    text: str
    evidence: str
    status: str  # trying | kept | rejected
    result: str | None
    learned_in_run: str
    tested_in_run: str | None
    baseline_seconds: int
    tested_seconds: int | None
    created_at: datetime


class JournalRunView(BaseModel):
    run_id: str
    mode: str
    player_character: str | None
    ending: str
    ending_title: str
    finished_at: int
    lessons_used: list[int]
    note: str
    created_at: datetime


class JournalView(BaseModel):
    lessons: list[LessonView]
    runs: list[JournalRunView]  # oldest first: the learning curve


def manager(request: Request) -> RunManager:
    return request.app.state.run_manager


def _view(runs: RunManager) -> JournalView:
    repo = runs.repo
    return JournalView(
        lessons=[LessonView(id=r.id, character_id=r.character_id, character=NAMES.get(r.character_id, r.character_id),
                            text=r.text, evidence=r.evidence, status=r.status, result=r.result,
                            learned_in_run=r.learned_in_run, tested_in_run=r.tested_in_run,
                            baseline_seconds=r.baseline_seconds, tested_seconds=r.tested_seconds,
                            created_at=r.created_at) for r in repo.lessons()],
        runs=[JournalRunView(run_id=r.run_id, mode=r.mode, player_character=r.player_character, ending=r.ending,
                             ending_title=ENDING_TITLES[EndingId(r.ending)], finished_at=r.finished_at,
                             lessons_used=r.lessons_used, note=r.note, created_at=r.created_at)
              for r in repo.journal_runs()],
    )


@router.get("", response_model=JournalView)
def journal(runs: RunManager = Depends(manager)) -> JournalView:
    return _view(runs)


@router.post("/reset", response_model=JournalView)
def reset(runs: RunManager = Depends(manager)) -> JournalView:
    """Forget every lesson: the next Watch run plays exactly as the rules alone would."""
    runs.repo.reset_journal()
    return _view(runs)
