"""Gameplay graphs: analytics built from a run's recorded events."""

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.engine.analytics import run_analytics
from app.engine.ids import ARIA, KABIR
from app.engine.run import Run
from app.main import create_app
from app.models.enums import GameMode


def test_time_adds_up_for_every_character():
    run = Run.create(GameMode.DEFAULT)
    run.run_to_end()
    a = run_analytics(run.world)
    assert a.duration == 330 and a.deadline is None
    for c in a.timelines:
        assert c.travel + c.work + c.waiting == a.duration
        assert all(0 <= s.start < s.end <= a.duration for s in c.segments)
    kabir = next(c for c in a.timelines if c.id == KABIR)
    assert any(s.kind == "work" and s.label == "Repair bridge" for s in kabir.segments)


def test_progress_follows_the_story_beats_in_order():
    run = Run.create(GameMode.DEFAULT)
    run.run_to_end()
    a = run_analytics(run.world)
    assert [p.reached for p in a.progress] == list(range(1, a.beats_total + 1))
    assert [p.time for p in a.progress] == sorted(p.time for p in a.progress)
    assert a.progress[-1].time == 330


def test_decisions_are_counted_per_character():
    run = Run.create(GameMode.DEFAULT)
    run.run_to_end()
    a = run_analytics(run.world)
    aria = next(d for d in a.decisions if d.id == ARIA)
    assert aria.plan_changes == run.world.minds[ARIA].replans
    assert aria.lessons_used == 0 and aria.ai_choices == 0


def test_a_run_in_progress_is_measured_up_to_now():
    run = Run.create(GameMode.GAME, ARIA)
    run.start()
    for _ in range(10):
        run.tick()
    a = run_analytics(run.world)
    assert a.duration == run.world.clock.now == 50 and a.deadline == 600
    assert all(s.end <= 50 for c in a.timelines for s in c.segments)


def test_analytics_endpoint_needs_the_run_token(tmp_path):
    settings = Settings(_env_file=None, database_url=f"sqlite:///{(tmp_path / 'a.db').as_posix()}", sim_autorun=False)
    with TestClient(create_app(settings)) as client:
        created = client.post("/api/runs", json={"mode": "default"}).json()
        run_id, h = created["run_id"], {"X-Run-Token": created["token"]}
        client.post(f"/api/runs/{run_id}/start", headers=h)
        client.post(f"/api/runs/{run_id}/advance", json={"ticks": 120}, headers=h)
        assert client.get(f"/api/runs/{run_id}/analytics").status_code == 401
        data = client.get(f"/api/runs/{run_id}/analytics", headers=h).json()
        assert data["duration"] == 330 and len(data["timelines"]) == 3
        finished = client.get("/api/runs?status=finished").json()
        assert [r["id"] for r in finished] == [run_id] and finished[0]["sim_time"] == 330
