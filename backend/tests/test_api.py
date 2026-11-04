import time

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app
from app.persistence.repository import RunRepository, make_engine


def make_settings(tmp_path, **overrides) -> Settings:
    values = {"database_url": f"sqlite:///{(tmp_path / 'test.db').as_posix()}", "sim_autorun": False} | overrides
    return Settings(_env_file=None, **values)


@pytest.fixture
def settings(tmp_path):
    return make_settings(tmp_path)


@pytest.fixture
def client(settings):
    with TestClient(create_app(settings)) as c:
        yield c


def create(client, mode="game", player="aria"):
    body = {"mode": mode} | ({"player_character": player} if mode == "game" else {})
    r = client.post("/api/runs", json=body)
    assert r.status_code == 201, r.text
    data = r.json()
    return data["run_id"], {"X-Run-Token": data["token"]}


def started(client, **kw):
    run_id, h = create(client, **kw)
    assert client.post(f"/api/runs/{run_id}/start", headers=h).status_code == 200
    return run_id, h


def advance(client, run_id, h, ticks):
    return client.post(f"/api/runs/{run_id}/advance", json={"ticks": ticks}, headers=h)


def act(client, run_id, h, **body):
    r = client.post(f"/api/runs/{run_id}/actions", json=body, headers=h)
    assert r.status_code == 200, r.text
    return r.json()


# --- lifecycle --------------------------------------------------------------------------------------------

def test_default_mode_runs_to_the_light_returns(client):
    run_id, h = started(client, mode="default")
    state = advance(client, run_id, h, 120).json()
    assert state["run"]["status"] == "finished"
    assert state["story"]["ending"]["ending"] == "light_returns"
    assert state["run"]["ai_mode"] == "mock"


def test_state_shape_for_the_frontend(client):
    run_id, h = started(client)
    state = client.get(f"/api/runs/{run_id}/state", headers=h).json()
    assert {loc["id"] for loc in state["locations"]} >= {"harbour", "lighthouse", "temple"}
    assert {c["id"] for c in state["characters"]} == {"aria", "kabir", "meera"}
    aria = next(c for c in state["characters"] if c["id"] == "aria")
    assert aria["autonomous"] is False and aria["location_id"] == "harbour"
    assert state["clock"] == {"now": 0, "deadline": 600, "remaining": 600, "tick_seconds": 5}
    assert any(o["label"].startswith("Go to") for o in state["available_actions"])


def test_hidden_route_and_traps_stay_hidden_until_discovered(client):
    run_id, h = started(client)
    ids = lambda s: {r["id"] for r in s["routes"]}  # noqa: E731
    state = client.get(f"/api/runs/{run_id}/state", headers=h).json()
    assert "forest_trail" not in ids(state)
    state = advance(client, run_id, h, 14).json()  # Meera discovers the trail at t=60
    trail = next(r for r in state["routes"] if r["id"] == "forest_trail")
    assert trail["hazard"] == "traps"


# --- authorisation and validation ----------------------------------------------------------------------

def test_tokens_protect_each_run(client):
    run_a, ha = create(client)
    run_b, hb = create(client)
    assert client.get(f"/api/runs/{run_a}/state").status_code == 401
    assert client.get(f"/api/runs/{run_a}/state", headers={"X-Run-Token": "wrong"}).status_code == 401
    assert client.get(f"/api/runs/{run_a}/state", headers=hb).status_code == 401  # B's token cannot touch A
    assert client.get("/api/runs/does-not-exist/state", headers=ha).status_code == 404


def test_scenario_describes_characters_without_a_run(client):
    data = client.get("/api/scenario").json()
    assert [c["id"] for c in data["characters"]] == ["aria", "kabir", "meera"]
    assert "climb" in next(c for c in data["characters"] if c["id"] == "aria")["abilities"]
    assert len(data["locations"]) == 6 and data["objectives"][0]["id"] == "restore_light"


def test_built_frontend_is_served_next_to_the_api(tmp_path, monkeypatch):
    import app.main as main
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("<html>Off Script</html>", encoding="utf-8")
    monkeypatch.setattr(main, "FRONTEND_DIST", dist)
    with TestClient(main.create_app(make_settings(tmp_path))) as c:
        assert "Off Script" in c.get("/").text
        assert c.get("/api/health").json()["status"] == "ok"  # the API still wins over the static files


def test_bad_run_configuration_is_422(client):
    assert client.post("/api/runs", json={"mode": "game"}).status_code == 422
    assert client.post("/api/runs", json={"mode": "game", "player_character": "ghost"}).status_code == 422
    assert client.post("/api/runs", json={"mode": "default", "player_character": "aria"}).status_code == 422


def test_player_cannot_choose_actor_or_edit_world(client):
    run_id, h = started(client)
    for body in ({"type": "move", "destination": "bridge", "actor": "kabir"},
                 {"type": "wait", "deadline": 9999},
                 {"type": "teleport"}):
        assert client.post(f"/api/runs/{run_id}/actions", json=body, headers=h).status_code == 422


def test_rule_rejections_are_explained(client):
    run_id, h = started(client)
    result = act(client, run_id, h, type="move", destination="temple")
    assert result["ok"] is False and "No route" in result["message"]
    result = act(client, run_id, h, type="repair_bridge")
    assert result["ok"] is False and "cannot repair" in result["message"]


def test_actions_dialogue_and_events(client):
    run_id, h = started(client)
    assert act(client, run_id, h, type="move", destination="bridge")["ok"]
    advance(client, run_id, h, 1)
    seq = client.get(f"/api/runs/{run_id}/events", headers=h).json()["last_event_seq"]
    r = client.post(f"/api/runs/{run_id}/dialogue", json={"target_id": "kabir", "message": "hi"}, headers=h).json()
    assert r["ok"] is False and "travelling" in r["message"]  # Aria is on the road and cannot stop to chat
    advance(client, run_id, h, 2)
    new = client.get(f"/api/runs/{run_id}/events", params={"after": seq}, headers=h).json()["events"]
    assert new and all(e["seq"] > seq for e in new)


def test_duplicate_request_id_is_applied_once(client):
    run_id, h = started(client)
    first = act(client, run_id, h, type="inspect", request_id="abc")
    again = act(client, run_id, h, type="inspect", request_id="abc")
    assert first["ok"] and again["ok"] and again["duplicate"] and not first["duplicate"]


def test_rate_limit(tmp_path):
    with TestClient(create_app(make_settings(tmp_path, player_requests_per_second=0.001, player_request_burst=3))) as c:
        run_id, h = started(c)
        codes = [c.post(f"/api/runs/{run_id}/actions", json={"type": "inspect"}, headers=h).status_code
                 for _ in range(5)]
        assert codes[:3] == [200, 200, 200] and codes[3:] == [429, 429]


# --- authoritative clock -------------------------------------------------------------------------------------

def test_deadline_is_enforced_and_cannot_be_extended(client):
    run_id, h = started(client, player="kabir")  # an idle engineer dooms the mission
    for _ in range(5):
        client.get(f"/api/runs/{run_id}/state", headers=h)  # reads never move or reset the clock
    state = advance(client, run_id, h, 120).json()
    assert state["clock"]["now"] == 600 and state["run"]["status"] == "finished"
    assert state["story"]["ending"]["ending"] == "last_storm"
    assert advance(client, run_id, h, 1).status_code == 409
    assert act(client, run_id, h, type="wait", seconds=10)["ok"] is False


def test_game_mode_cannot_pause_but_default_can(client):
    run_id, h = started(client)
    assert client.post(f"/api/runs/{run_id}/pause", json={"paused": True}, headers=h).status_code == 409
    run_id, h = started(client, mode="default")
    r = client.post(f"/api/runs/{run_id}/pause", json={"paused": True}, headers=h)
    assert r.status_code == 200 and r.json()["run"]["paused"] is True


def test_restart_creates_a_new_run_and_abandons_the_old(client):
    run_id, h = started(client)
    advance(client, run_id, h, 10)
    r = client.post(f"/api/runs/{run_id}/restart", headers=h)
    assert r.status_code == 201
    new = r.json()
    assert new["run_id"] != run_id and new["state"]["clock"]["now"] == 0
    old = client.get(f"/api/runs/{run_id}/state", headers=h).json()
    assert old["run"]["status"] == "abandoned" and old["clock"]["now"] == 50


def test_background_driver_advances_time_by_itself(tmp_path):
    with TestClient(create_app(make_settings(tmp_path, sim_autorun=True, game_sim_speed=500))) as c:
        run_id, h = started(c)
        time.sleep(0.4)
        now = c.get(f"/api/runs/{run_id}/state", headers=h).json()["clock"]["now"]
        assert 0 < now <= 600


# --- persistence ------------------------------------------------------------------------------------------------

def test_runs_survive_a_server_restart(tmp_path):
    settings = make_settings(tmp_path)
    with TestClient(create_app(settings)) as c:
        run_id, h = started(c)
        assert act(c, run_id, h, type="move", destination="bridge")["ok"]
        before = advance(c, run_id, h, 20).json()

    with TestClient(create_app(settings)) as c:  # a fresh process: nothing in memory
        after = c.get(f"/api/runs/{run_id}/state", headers=h).json()
        assert after["clock"] == before["clock"]
        assert after["characters"] == before["characters"]
        assert after["last_event_seq"] == before["last_event_seq"]
        assert c.get(f"/api/runs/{run_id}/state", headers={"X-Run-Token": "nope"}).status_code == 401
        assert advance(c, run_id, h, 1).json()["clock"]["now"] == before["clock"]["now"] + 5


def test_history_tables_are_filled(tmp_path, settings):
    with TestClient(create_app(settings)) as c:
        run_id, h = started(c, mode="default")
        state = advance(c, run_id, h, 120).json()
        listed = c.get("/api/runs", params={"status": "finished"}).json()
        assert any(r["id"] == run_id and r["ending"] == "light_returns" for r in listed)
    repo = RunRepository(make_engine(settings.resolved_database_url))
    events = repo.events(run_id)
    assert [e.seq for e in events] == list(range(1, state["last_event_seq"] + 1))
    assert repo.snapshot_count(run_id) >= 5            # a history snapshot every 60 simulated seconds
    assert any(m.importance >= 4 for m in repo.memories(run_id))
