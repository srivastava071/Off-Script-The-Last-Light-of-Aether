"""Typed / spoken player commands: interpretation, validation and execution."""

import json

import pytest
from fastapi.testclient import TestClient

from app.agents.commands import Interpretation, Step, parse_fallback, parse_interpretation, validate
from app.core.config import AIProvider, Settings
from app.engine.aether import ARIA, BRIDGE, FOREST, KABIR, LIGHTHOUSE, MEERA, TEMPLE
from app.engine.invariants import check_invariants
from app.engine.run import Run
from app.main import create_app
from app.models.enums import EventKind, GameMode, RouteStatus, RunStatus
from app.services.llm import LLMService
from tests.test_llm import FakeProvider


def game(player=ARIA):
    run = Run.create(GameMode.GAME, player)
    run.start()
    return run


def say(run, text):
    return run.give_command(text, parse_fallback(run.world, run.world.story.player_character, text), "keyword parser")


def tick_until(run, done, limit=400):
    for _ in range(limit):
        if done(run) or run.status is not RunStatus.RUNNING:
            return
        run.tick()
        assert check_invariants(run.world) == []
    raise AssertionError("condition never reached")


def kinds(result):
    return [e.kind for e in result.events]


# --- keyword parser --------------------------------------------------------------------------------------

def steps_of(world, text, player=ARIA):
    return [(s.who, s.kind, s.location or s.action) for s in parse_fallback(world, player, text).steps]


def test_parser_addresses_people_and_splits_instructions(world):
    assert steps_of(world, "Kabir, pick up the timber and fix the bridge. Meera, scout the forest") == [
        (KABIR, "do", "pick_up"), (KABIR, "do", "repair_bridge"),
        (MEERA, "go_to", FOREST), (MEERA, "do", "discover_route"),
    ]


def test_parser_defaults_to_the_player_and_understands_places(world):
    assert steps_of(world, "go to the lighthouse") == [(ARIA, "go_to", LIGHTHOUSE)]
    assert steps_of(world, "I'll head to the temple then pull the lever") == [
        (ARIA, "go_to", TEMPLE), (ARIA, "do", "pull_lever")]


def test_parser_handles_give_wait_and_resume(world):
    parsed = parse_fallback(world, MEERA, "Kabir give me the toolkit")
    assert parsed.steps[0].action == "give" and parsed.steps[0].to == MEERA and parsed.steps[0].object == "toolkit"
    assert steps_of(world, "Meera wait 20s") == [(MEERA, "wait", None)]
    assert steps_of(world, "Kabir, carry on with your own plan") == [(KABIR, "resume", None)]


def test_gibberish_produces_no_orders(world):
    assert parse_fallback(world, ARIA, "what a lovely sunset").steps == []


# --- validation ---------------------------------------------------------------------------------------------

def test_impossible_orders_are_refused_up_front(world):
    checked = validate(world, ARIA, Interpretation(steps=[
        Step(who="meera", kind="do", action="repair_bridge"),
        Step(who="kabir", kind="do", action="pull_lever"),       # Kabir can rig it: allowed
        Step(who="ghost", kind="go_to", location="temple"),
        Step(who="aria", kind="go_to", location="castle"),
        Step(who="aria", kind="do", action="teleport"),
    ]))
    assert list(checked.orders) == [KABIR]
    reasons = " | ".join(r for _, r in checked.refusals)
    assert "Meera cannot repair" in reasons and "nobody called 'ghost'" in reasons
    assert "no place called 'castle'" in reasons and "'teleport'" in reasons


def test_llm_style_action_variants_are_accepted(world):
    checked = validate(world, ARIA, Interpretation(steps=[Step(who="meera", kind="do", action="discover_routes"),
                                                          Step(who="meera", kind="do", action="mark traps")]))
    assert [o.action.type.value for o in checked.orders[MEERA]] == ["discover_route", "detect_traps"]
    assert checked.orders[MEERA][1].action.route_id is None  # chosen once Meera knows a trapped route


def test_scout_then_mark_traps_works_in_order():
    run = game(KABIR)
    assert say(run, "Meera, scout the forest and mark the traps").ok
    tick_until(run, lambda r: not r.world.routes["forest_trail"].hazard_active)
    marked = next(e for e in run.world.events if e.kind is EventKind.TRAPS_MARKED)
    assert marked.actor == MEERA and marked.data["route_id"] == "forest_trail"


def test_orders_cannot_use_undiscovered_routes(world):
    checked = validate(world, ARIA, Interpretation(steps=[Step(who="aria", kind="do", action="block_route",
                                                                 route="forest_trail")]))
    assert not checked.orders and "Which route" in checked.refusals[0][1]


# --- execution ------------------------------------------------------------------------------------------------

def test_teammate_obeys_instead_of_following_own_plan():
    run = game(ARIA)
    result = say(run, "Meera, go to the lighthouse")
    assert result.ok and EventKind.ORDER_ACCEPTED in kinds(result)
    tick_until(run, lambda r: r.world.characters[MEERA].location_id == LIGHTHOUSE)
    trips = [e for e in run.world.events if e.kind is EventKind.TRAVEL_STARTED and e.actor == MEERA]
    assert trips[0].data["destination"] == LIGHTHOUSE  # not the forest, where her own plan would take her
    assert any(e.kind is EventKind.ORDER_COMPLETED and e.actor == MEERA for e in run.world.events)
    tick_until(run, lambda r: r.world.characters[MEERA].location_id == FOREST)  # then back to her own plan


def test_order_walks_to_the_right_place_first_then_acts():
    run = game(ARIA)
    assert say(run, "Kabir, pick up the timber and the gear, then repair the bridge").ok
    tick_until(run, lambda r: r.world.routes["main_bridge"].status is RouteStatus.OPEN)
    by_kabir = [e.kind for e in run.world.events if e.actor == KABIR]
    assert EventKind.BRIDGE_REPAIRED in by_kabir


def test_order_completes_only_when_the_action_has_finished():
    run = game(KABIR)
    assert say(run, "Meera wait 30s").ok
    tick_until(run, lambda r: any(e.kind is EventKind.ORDER_COMPLETED for e in r.world.events))
    done = next(e for e in run.world.events if e.kind is EventKind.ORDER_COMPLETED)
    assert done.time >= 30


def test_order_that_turns_out_impossible_is_reported():
    run = game(ARIA)
    assert say(run, "Kabir repair the bridge").ok  # he is not carrying the timber
    tick_until(run, lambda r: any(e.kind is EventKind.ORDER_FAILED for e in r.world.events))
    failed = next(e for e in run.world.events if e.kind is EventKind.ORDER_FAILED)
    assert failed.actor == KABIR and "Timber Planks" in failed.description


def test_player_autopilot_carries_out_own_instructions():
    run = game(ARIA)
    assert say(run, "go to the broken bridge and block the main bridge").ok
    tick_until(run, lambda r: r.world.routes["main_bridge"].obstructed)
    assert run.world.routes["main_bridge"].blocked_by == ARIA


def test_manual_action_cancels_autopilot():
    from app.models.actions import ProposedAction
    from app.models.enums import ActionType
    run = game(ARIA)
    assert say(run, "go to the lighthouse").ok
    assert run.player_action(ProposedAction(actor=ARIA, type=ActionType.INSPECT)).ok
    assert run.world.minds[ARIA].orders == []


def test_new_command_replaces_old_and_resume_clears():
    run = game(ARIA)
    say(run, "Kabir go to the lighthouse")
    say(run, "Kabir go to the forest")
    assert [o.summary for o in run.world.minds[KABIR].orders] == ["go to the Whispering Forest"]
    say(run, "Kabir, carry on")
    assert run.world.minds[KABIR].orders == []


def test_commands_need_game_mode_and_a_running_run():
    default = Run.create(GameMode.DEFAULT)
    default.start()
    assert "disabled" in default.give_command("go", Interpretation(), "x").message
    unstarted = Run.create(GameMode.GAME, ARIA)
    assert not unstarted.give_command("go", Interpretation(), "x").ok


def test_unrecognised_command_explains_itself():
    run = game(ARIA)
    result = say(run, "sing a song")
    assert not result.ok and "could not be turned into orders" in result.message


def test_radio_reaches_teammates_anywhere_and_they_remember_it():
    run = game(ARIA)
    run.world.characters[MEERA].location_id = TEMPLE
    say(run, "Meera, decode the symbols")
    assert any(m.source == f"told:{ARIA}" for m in run.world.minds[MEERA].memories)
    assert run.world.minds[MEERA].orders[0].summary == "decode the temple symbols"


# --- LLM interpretation ---------------------------------------------------------------------------------------

def test_llm_json_is_parsed_and_validated():
    text = '```json\n{"steps": [{"who": "kabir", "kind": "go_to", "location": "bridge"}]}\n```'
    assert parse_interpretation(text).steps[0].location == BRIDGE
    assert parse_interpretation("I think Kabir should go") is None


def live(tmp_path, provider):
    settings = Settings(_env_file=None, database_url=f"sqlite:///{(tmp_path / 'c.db').as_posix()}", sim_autorun=False,
                        ai_provider=AIProvider.OPENAI_COMPATIBLE, groq_api_key="unused")
    return TestClient(create_app(settings, llm=LLMService([provider], max_calls_per_minute=100, max_retries=0)))


def started(c):
    d = c.post("/api/runs", json={"mode": "game", "player_character": "aria"}).json()
    h = {"X-Run-Token": d["token"]}
    c.post(f"/api/runs/{d['run_id']}/start", headers=h)
    return d["run_id"], h


def test_command_endpoint_uses_llm_interpretation(tmp_path):
    reply = json.dumps({"steps": [{"who": "meera", "kind": "go_to", "location": "lighthouse"},
                                  {"who": "kabir", "kind": "do", "action": "decode_symbols"}]})
    with live(tmp_path, FakeProvider("fake", "m1", reply=reply)) as c:
        run_id, h = started(c)
        r = c.post(f"/api/runs/{run_id}/command", json={"text": "Meera to the lighthouse, Kabir decode"}, headers=h).json()
        given = next(e for e in r["events"] if e["kind"] == "command_given")
        assert given["data"]["interpreted_by"] == "fake:m1"
        assert any(e["kind"] == "order_accepted" and e["actor"] == "meera" for e in r["events"])
        assert any(e["kind"] == "order_refused" and "Kabir cannot" in e["description"] for e in r["events"])
        state = c.get(f"/api/runs/{run_id}/state", headers=h).json()
        assert next(ch for ch in state["characters"] if ch["id"] == "meera")["orders"] == ["go to the Lighthouse"]


def test_command_falls_back_to_parser_when_llm_fails(tmp_path):
    with live(tmp_path, FakeProvider(error="down")) as c:
        run_id, h = started(c)
        r = c.post(f"/api/runs/{run_id}/command", json={"text": "Kabir, go to the lighthouse"}, headers=h).json()
        assert r["ok"]
        given = next(e for e in r["events"] if e["kind"] == "command_given")
        assert given["data"]["interpreted_by"].startswith("keyword parser")


@pytest.mark.parametrize("body", [{"text": ""}, {"text": "x" * 301}, {"text": "go", "actor": "kabir"}])
def test_command_request_validation(tmp_path, body):
    with live(tmp_path, FakeProvider(reply="{}")) as c:
        run_id, h = started(c)
        assert c.post(f"/api/runs/{run_id}/command", json=body, headers=h).status_code == 422
