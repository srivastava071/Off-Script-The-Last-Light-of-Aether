"""The player as co-author: story twists, radio 'Say', and the live storybook."""

import pytest
from fastapi.testclient import TestClient

from app.agents import storyteller
from app.core.config import Settings
from app.engine.aether import ARIA, HARBOUR, KABIR, MEERA
from app.engine.ids import FOREST_TRAIL, MAIN_BRIDGE, SUN_CRYSTAL, TIMBER
from app.engine.invariants import check_invariants
from app.engine.run import Run
from app.main import create_app
from app.models.enums import EventKind, GameMode, RunStatus
from tests.test_llm import FakeProvider, live_settings, service, started, wait_for


def game(player: str = ARIA) -> Run:
    run = Run.create(GameMode.GAME, player)
    run.start()
    return run


def twist(run: Run, text: str):
    chosen, note = storyteller.parse_fallback(run.world, text)
    return run.add_twist(text, chosen, "keyword parser", note)


def finish(run: Run) -> None:
    for _ in range(400):
        if run.status is RunStatus.FINISHED:
            return
        run.tick()
        assert check_invariants(run.world) == []
    raise AssertionError("run did not finish")


# --- twists -----------------------------------------------------------------------------------------------

@pytest.mark.parametrize("text, kind, route", [
    ("A rockslide blocks the forest path", "block_route", "forest_path"),
    ("a tree falls across the Coast Road", "block_route", "coast_road"),
    ("lightning! the storm comes sooner", "storm_closer", None),
    ("a gust of wind blows the timber to the bridge", "move_item", None),
])
def test_keyword_parser_maps_twists_onto_the_catalogue(text, kind, route):
    chosen, _ = storyteller.parse_fallback(game().world, text)
    assert chosen is not None and chosen.kind == kind and chosen.route_id == route


@pytest.mark.parametrize("text, hint", [
    ("the crystal flies away", "beyond the storyteller's reach"),
    ("a tree falls", "Say which path"),
    ("dragons attack", "Try a twist the island allows"),
])
def test_impossible_twists_are_refused_with_a_hint(text, hint):
    run = game()
    result = twist(run, text)
    assert not result.ok and hint in result.message
    assert run.world.story.twists_used == 0


def test_blocking_twist_changes_the_world_and_witnesses_notice():
    run = game()
    result = twist(run, "A rockslide blocks the forest path")
    assert result.ok
    route = run.world.routes["forest_path"]
    assert route.obstructed and route.blocked_by == storyteller.TWIST_BLOCKER
    assert check_invariants(run.world) == []
    # everyone is at the harbour, the near end, so they see it at once
    assert run.world.minds[MEERA].beliefs.routes["forest_path"].obstructed
    # the twist is nobody's fault: no trust is lost
    assert run.world.minds[MEERA].trust[ARIA] == run.world.minds[KABIR].trust[ARIA]


def test_characters_adapt_to_a_twist_and_the_story_still_ends():
    run = game(ARIA)
    assert twist(run, "A rockslide blocks the forest path").ok  # Meera's usual way to the temple
    finish(run)
    assert run.world.minds[MEERA].replans > 0
    assert run.world.story.ending is not None and run.world.story.ending.main_success


def test_twist_that_clears_a_route():
    run = game()
    twist(run, "a tree falls across the Coast Road")
    run.world.story.last_twist_at = -999  # skip the cooldown for this test
    result = twist(run, "the wind clears the coast road")
    assert result.ok and not run.world.routes["coast_road"].obstructed
    assert check_invariants(run.world) == []


def test_item_twist_never_moves_the_crystal_or_carried_things():
    run = game()
    opts = storyteller.options(run.world)
    moved = {o.object_id for o in opts if o.kind == "move_item"}
    assert SUN_CRYSTAL not in moved and "toolkit" not in moved  # Kabir carries the toolkit
    assert twist(run, "a gust of wind blows the timber to the bridge").ok
    assert run.world.objects[TIMBER].location_id == "bridge" and check_invariants(run.world) == []


def test_storm_twist_shortens_the_deadline_once_and_everyone_hears_it():
    run = game()
    assert twist(run, "the storm comes sooner").ok
    assert run.world.clock.deadline == 600 - storyteller.STORM_STEP_SECONDS
    assert all(any("storm is coming sooner" in m.description for m in run.world.minds[c].memories)
               for c in run.world.characters)
    run.world.story.last_twist_at = -999
    assert not twist(run, "the storm comes even sooner").ok


def test_hidden_routes_are_never_offered_as_twists():
    run = game()
    assert all(o.route_id != FOREST_TRAIL for o in storyteller.options(run.world))
    assert all(o.route_id != "ravine_climb" for o in storyteller.options(run.world))  # cannot be blocked


def test_twists_are_limited_and_have_a_cooldown():
    run = game()
    assert twist(run, "a tree falls across the Coast Road").ok
    second = twist(run, "a tree falls on the cliff stairs")
    assert not second.ok and "next twist is possible" in second.message
    for text in ["a tree falls on the cliff stairs", "a boulder blocks the main bridge"]:
        run.world.story.last_twist_at = -999
        assert twist(run, text).ok
    run.world.story.last_twist_at = -999
    assert "all 3 story twists" in twist(run, "a tree falls on the forest path").message


def test_twists_are_game_mode_only():
    run = Run.create(GameMode.DEFAULT)
    run.start()
    assert not twist(run, "a tree falls across the Coast Road").ok


# --- radio 'Say' --------------------------------------------------------------------------------------------

def test_say_is_heard_and_remembered_but_gives_no_orders():
    run = game(ARIA)
    result = run.radio_say("Be careful, I think there are traps in the forest")
    assert result.ok and result.events[0].kind is EventKind.RADIO_MESSAGE
    for cid in (KABIR, MEERA):
        mind = run.world.minds[cid]
        assert any("traps in the forest" in m.description for m in mind.memories)
        assert mind.orders == []


def mock_client(tmp_path) -> TestClient:
    settings = Settings(_env_file=None, database_url=f"sqlite:///{(tmp_path / 's.db').as_posix()}", sim_autorun=False)
    return TestClient(create_app(settings))


def test_say_endpoint_gets_in_character_replies(tmp_path):
    with mock_client(tmp_path) as c:
        run_id, h = started(c)
        r = c.post(f"/api/runs/{run_id}/say", json={"text": "How is everyone doing?"}, headers=h).json()
        assert r["ok"]
        replies = [e for e in r["events"] if e["data"].get("reply")]
        assert {e["actor"] for e in replies} == {KABIR, MEERA}
        assert all(e["data"]["generated_by"] == "template" for e in replies)
        named = c.post(f"/api/runs/{run_id}/say", json={"text": "Kabir, are you okay?"}, headers=h).json()
        assert {e["actor"] for e in named["events"] if e["data"].get("reply")} == {KABIR}


def test_say_replies_use_the_llm_when_available(tmp_path):
    fake = FakeProvider("fake", "m1", reply="Copy that, Aria. Moving carefully.")
    with TestClient(create_app(live_settings(tmp_path), llm=service(fake))) as c:
        run_id, h = started(c)
        r = c.post(f"/api/runs/{run_id}/say", json={"text": "Meera, stay safe"}, headers=h).json()
        reply = [e for e in r["events"] if e["data"].get("reply")]
        assert reply[0]["actor"] == MEERA and reply[0]["data"]["generated_by"] == "fake:m1"
        assert any("over the radio" in call[0]["content"] for call in fake.calls)


# --- twist endpoint ---------------------------------------------------------------------------------------

def test_twist_endpoint_uses_keywords_in_mock_mode(tmp_path):
    with mock_client(tmp_path) as c:
        run_id, h = started(c)
        r = c.post(f"/api/runs/{run_id}/twist", json={"text": "A fallen tree blocks the coast road"}, headers=h).json()
        assert r["ok"] and r["events"][0]["data"]["interpreted_by"] == "keyword parser"
        state = c.get(f"/api/runs/{run_id}/state", headers=h).json()
        assert state["story"]["twists"]["used"] == 1 and state["story"]["twists"]["ready_at"] is not None
        coast = next(rt for rt in state["routes"] if rt["id"] == "coast_road")
        assert coast["obstructed"] and coast["blocked_by"] == "storm"


def test_llm_picks_a_twist_by_number(tmp_path):
    def answer(messages):
        if "story idea" in messages[0]["content"] or "twist the game allows" in messages[0]["content"]:
            lines = messages[1]["content"].splitlines()
            n = next(line.split(".")[0] for line in lines if "Cliff Stairs" in line)
            return f'{{"choice": {n}}}'
        return "A page of the story."
    fake = FakeProvider("fake", "m1", reply=answer)
    with TestClient(create_app(live_settings(tmp_path), llm=service(fake))) as c:
        run_id, h = started(c)
        r = c.post(f"/api/runs/{run_id}/twist", json={"text": "an earthquake cracks the steps to the lighthouse"},
                   headers=h).json()
        assert r["ok"] and r["events"][0]["data"]["route_id"] == "cliff_stairs"
        assert r["events"][0]["data"]["interpreted_by"] == "fake:m1"


def test_invalid_llm_twist_answer_falls_back_to_keywords(tmp_path):
    fake = FakeProvider("fake", "m1", reply="sure! let's make it dramatic")
    with TestClient(create_app(live_settings(tmp_path), llm=service(fake))) as c:
        run_id, h = started(c)
        r = c.post(f"/api/runs/{run_id}/twist", json={"text": "a tree falls across the coast road"}, headers=h).json()
        assert r["ok"] and r["events"][0]["data"]["interpreted_by"].startswith("keyword parser")


# --- storybook --------------------------------------------------------------------------------------------

def test_storybook_has_a_page_for_every_beat_and_twist():
    run = game(MEERA)
    twist(run, "a boulder blocks the main bridge")
    finish(run)
    chapters = run.world.story.chapters
    beats = [b for b in run.world.story.beats if b.reached_at is not None]
    assert len([c for c in chapters if c.kind == "beat"]) == len(beats)
    assert [c.kind for c in chapters].count("twist") == 1
    assert [c.id for c in chapters] == list(range(1, len(chapters) + 1))
    assert all(c.generated_by == "template" and c.text for c in chapters)


def test_storybook_is_reproducible_in_default_mode():
    texts = []
    for _ in range(2):
        run = Run.create(GameMode.DEFAULT)
        run.run_to_end()
        texts.append([c.text for c in run.world.story.chapters])
    assert texts[0] == texts[1] and len(texts[0]) == 9


def test_storybook_pages_are_rewritten_by_the_llm_and_labelled(tmp_path):
    fake = FakeProvider("fake", "m1", reply="The friends hopped off the boat, giggling at the creaky piers.")
    with TestClient(create_app(live_settings(tmp_path), llm=service(fake))) as c:
        run_id, h = started(c)
        page = wait_for(lambda: next((p for p in c.get(f"/api/runs/{run_id}/state", headers=h).json()["story"]["chapters"]
                                      if p["generated_by"] == "fake:m1"), None))
        assert page["id"] == 1 and "creaky piers" in page["text"]
        prompt = next(call for call in fake.calls if "storybook" in call[0]["content"])
        assert "Abandoned Harbour" in prompt[1]["content"]  # grounded in the recorded facts


def test_twist_landing_spot_is_seen_from_the_harbour():
    run = game()
    twist(run, "a gust of wind blows the timber to the bridge")
    assert HARBOUR in {run.world.characters[c].location_id for c in run.world.characters}
    assert run.world.minds[KABIR].beliefs.objects[TIMBER].location_id != HARBOUR
