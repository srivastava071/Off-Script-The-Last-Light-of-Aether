"""Learning across games: the team journal reflects on Watch runs and tests one lesson at a time."""

import pytest
from fastapi.testclient import TestClient

from app.agents.learning import candidates, verdict
from app.core.config import Settings
from app.engine.ids import ARIA, KABIR
from app.engine.run import Run
from app.main import create_app
from app.models.enums import EndingId, EventKind, GameMode
from app.models.mind import ActiveLesson
from app.persistence.repository import RunRepository, make_engine
from app.services.journal import TeamJournal


@pytest.fixture
def journal(tmp_path) -> TeamJournal:
    repo = RunRepository(make_engine(f"sqlite:///{(tmp_path / 'journal.db').as_posix()}"))
    repo.create_schema()
    return TeamJournal(repo)


def play(journal: TeamJournal, mode: GameMode = GameMode.DEFAULT, player: str | None = None) -> Run:
    """One finished run that starts from the journal's lessons, and is then recorded by it (like the server)."""
    run = Run.create(mode, player, lessons=journal.lessons_for(mode, player))
    run.run_to_end()
    journal.after_finish(run.world)
    return run


def test_reflection_finds_the_long_wait_at_the_temple():
    run = Run.create(GameMode.DEFAULT)
    run.run_to_end()
    first = candidates(run.world)[0]
    assert (first.character_id, first.instead_of, first.prefer) == (ARIA, "wait_at_temple", "decode_symbols_myself")
    assert first.waited >= 100 and "Temple Entrance" in first.text


def test_a_lesson_changes_the_choice_only_in_its_situation():
    lesson = ActiveLesson(id=7, instead_of="wait_at_temple", prefer="decode_symbols_myself", text="Decode it myself.")
    run = Run.create(GameMode.DEFAULT, lessons={ARIA: [lesson]})
    events = run.run_to_end()
    applied = [e for e in events if e.kind is EventKind.LESSON_APPLIED]
    assert len(applied) == 1 and applied[0].actor == ARIA  # announced once, the first time it is used
    assert run.world.minds[ARIA].lessons_used == [7]
    assert run.world.story.ending.finished_at < 330  # faster than the rules alone


def test_the_player_character_never_receives_lessons():
    lesson = ActiveLesson(id=1, instead_of="x", prefer="y", text="t")
    run = Run.create(GameMode.GAME, ARIA, lessons={ARIA: [lesson], KABIR: [lesson]})
    assert run.world.minds[ARIA].lessons == [] and len(run.world.minds[KABIR].lessons) == 1


def test_verdict_keeps_only_real_improvements():
    best, light = EndingId.LIGHT_RETURNS, 330
    assert verdict((best, light), (best, 325))[0] is True
    assert verdict((best, light), (best, 360))[0] is False
    assert verdict((best, light), (best, light))[0] is False
    kept, why = verdict((EndingId.COSTLY_VICTORY, 300), (best, 400))
    assert kept and "The Light Returns" in why
    assert verdict((best, light), (EndingId.UNEXPECTED_ROUTE, 300))[0] is False


def test_the_learning_loop_keeps_what_helps_and_drops_what_hurts(journal):
    repo = journal.repo
    first = play(journal)
    assert first.world.story.ending.finished_at == 330
    [trying] = repo.lessons(statuses=("trying",))
    assert trying.character_id == ARIA and trying.prefer == "decode_symbols_myself"

    second = play(journal)
    assert second.world.story.ending.finished_at == 325
    assert repo.lesson(trying.id).status == "kept" and "5s sooner" in repo.lesson(trying.id).result
    [next_try] = repo.lessons(statuses=("trying",))  # learned from the improved run

    third = play(journal)
    assert repo.lesson(next_try.id).status == "rejected"
    assert third.world.story.ending.finished_at > 325
    assert repo.lessons(statuses=("trying",)) == []  # a rejected run teaches nothing new

    fourth = play(journal)
    assert fourth.world.story.ending.finished_at == 325  # back to the lessons that worked
    assert [r.finished_at for r in repo.journal_runs()] == [330, 325, third.world.story.ending.finished_at, 325]


def test_game_mode_uses_kept_lessons_but_never_tests_new_ones(journal):
    play(journal)  # Watch run: a lesson for Aria is now on trial
    run = play(journal, GameMode.GAME, KABIR)
    assert run.world.minds[ARIA].lessons == []  # on trial: Watch runs only
    assert len(journal.repo.lessons(statuses=("trying",))) == 1  # untouched by the Game run


def test_each_run_is_recorded_once(journal):
    run = play(journal)
    journal.after_finish(run.world)
    assert len(journal.repo.journal_runs()) == 1 and len(journal.repo.lessons()) == 1


def test_journal_api_learns_between_watch_runs_and_resets(tmp_path):
    settings = Settings(_env_file=None, database_url=f"sqlite:///{(tmp_path / 'api.db').as_posix()}", sim_autorun=False)
    with TestClient(create_app(settings)) as client:
        def watch() -> dict:
            created = client.post("/api/runs", json={"mode": "default"}).json()
            h = {"X-Run-Token": created["token"]}
            client.post(f"/api/runs/{created['run_id']}/start", headers=h)
            return client.post(f"/api/runs/{created['run_id']}/advance", json={"ticks": 120}, headers=h).json()

        assert watch()["story"]["ending"]["finished_at"] == 330
        journal = client.get("/api/journal").json()
        assert [le["status"] for le in journal["lessons"]] == ["trying"]
        assert "new lesson" in journal["runs"][-1]["note"]

        state = watch()
        aria = next(c for c in state["characters"] if c["id"] == "aria")
        assert aria["mind"]["lessons"][0]["used"] is True
        assert client.get("/api/journal").json()["lessons"][0]["status"] == "kept"

        assert client.post("/api/journal/reset").json() == {"lessons": [], "runs": []}
        assert watch()["story"]["ending"]["finished_at"] == 330  # forgotten: the rules alone again
