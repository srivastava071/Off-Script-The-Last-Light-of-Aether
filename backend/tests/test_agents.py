from app.agents.character_agent import CharacterAgent
from app.engine import knowledge
from app.engine.aether import (
    ARIA, BRIDGE, FOREST, HARBOUR, KABIR, LIGHTHOUSE, MEERA, SUN_CRYSTAL, TEMPLE, build_initial_world,
)
from app.engine.invariants import check_invariants
from app.engine.rules import perform
from app.engine.simulation import run_tick
from app.models.actions import ProposedAction
from app.models.enums import ActionType as A
from app.models.enums import EventKind, GameMode, RouteStatus


def agents_for(world, *ids):
    return {cid: CharacterAgent(cid) for cid in ids}


def player(world, actor, type, **kw):
    """A player action goes through exactly the same rules as an agent's."""
    result = perform(world, ProposedAction(actor=actor, type=type, **kw))
    assert result.ok, result.message
    knowledge.observe(world, result.events)
    return result


def run_until(world, agents, done, limit=900):
    while not done(world):
        assert world.clock.now < limit, "condition never reached"
        run_tick(world, agents)
        assert check_invariants(world) == []


def plan_changes(world, actor):
    return [e for e in world.events if e.kind is EventKind.PLAN_CHANGED and e.actor == actor]


# --- knowledge ------------------------------------------------------------------------------------

def test_briefing_is_common_knowledge_but_hidden_trail_is_not(world):
    for cid in (ARIA, KABIR, MEERA):
        b = world.minds[cid].beliefs
        assert b.routes["main_bridge"].status is RouteStatus.BROKEN
        assert not b.routes["forest_trail"].known
        assert b.objects[SUN_CRYSTAL].location_id == "chamber"


def test_only_characters_present_see_an_event(world):
    world.characters[KABIR].location_id = BRIDGE
    world.characters[ARIA].location_id = BRIDGE
    world.characters[MEERA].location_id = FOREST
    player(world, ARIA, A.BLOCK_ROUTE, route_id="main_bridge")
    events = []
    from app.engine.timeline import advance_clock
    advance_clock(world, 20, lambda new: (events.extend(new), knowledge.observe(world, new)))
    assert world.minds[KABIR].beliefs.routes["main_bridge"].obstructed
    assert not world.minds[MEERA].beliefs.routes["main_bridge"].obstructed
    assert any("blocks the Main Bridge" in m.description for m in world.minds[KABIR].memories)
    assert not any("blocks the Main Bridge" in m.description for m in world.minds[MEERA].memories)


def test_talking_shares_newer_knowledge(world):
    world.clock.now = 10
    world.routes["main_bridge"].obstructed = True
    world.routes["main_bridge"].blocked_by = ARIA
    world.characters[KABIR].location_id = BRIDGE
    knowledge.perceive(world, KABIR)
    world.characters[KABIR].location_id = HARBOUR
    assert not world.minds[MEERA].beliefs.routes["main_bridge"].obstructed

    player(world, KABIR, A.TALK, target_id=MEERA)
    assert world.minds[MEERA].beliefs.routes["main_bridge"].obstructed
    told = [m for m in world.minds[MEERA].memories if m.source == f"told:{KABIR}"]
    assert told and "Main Bridge is blocked" in told[-1].description


def test_signal_reaches_teammates_anywhere(world):
    world.clock.now = 10
    world.characters[MEERA].location_id = FOREST
    world.routes["forest_trail"].hidden = False
    knowledge.perceive(world, MEERA)
    assert not world.minds[KABIR].beliefs.routes["forest_trail"].known
    player(world, MEERA, A.SIGNAL)
    assert world.minds[KABIR].beliefs.routes["forest_trail"].known
    assert world.minds[ARIA].beliefs.routes["forest_trail"].known


def test_kabir_cannot_signal(world):
    result = perform(world, ProposedAction(actor=KABIR, type=A.SIGNAL))
    assert not result.ok


def test_memory_stays_bounded():
    world = build_initial_world("m", GameMode.DEFAULT)
    for i in range(200):
        knowledge.remember(world, ARIA, f"routine {i}", source="observed", importance=1)
    assert len(world.minds[ARIA].memories) <= knowledge.MAX_MEMORIES
    assert any(m.source == "summary" for m in world.minds[ARIA].memories)


# --- autonomous story --------------------------------------------------------------------------------

def _autonomous_run():
    world = build_initial_world("auto", GameMode.DEFAULT)
    run_until(world, agents_for(world, ARIA, KABIR, MEERA), lambda w: w.lighthouse.activated)
    return world


def test_autonomous_team_completes_the_mission():
    world = _autonomous_run()
    assert world.lighthouse.activated
    assert world.objects[SUN_CRYSTAL].location_id == LIGHTHOUSE
    assert all(m.failed_actions == 0 for m in world.minds.values())
    # Undisturbed, nobody needs to adapt.
    assert all(m.adaptations == 0 for m in world.minds.values())


def test_autonomous_runs_are_reproducible():
    assert _autonomous_run().model_dump() == _autonomous_run().model_dump()


def test_agents_never_hold_more_memories_than_allowed():
    world = _autonomous_run()
    assert all(len(m.memories) <= knowledge.MAX_MEMORIES for m in world.minds.values())


# --- adaptation scenarios (player controls Aria) -------------------------------------------------------

def test_blocked_bridge_makes_kabir_change_strategy_and_actions(world):
    agents = agents_for(world, KABIR, MEERA)
    player(world, ARIA, A.MOVE, destination=BRIDGE)
    run_until(world, agents, lambda w: w.characters[ARIA].location_id == BRIDGE)
    player(world, ARIA, A.BLOCK_ROUTE, route_id="main_bridge")
    run_until(world, agents, lambda w: w.routes["main_bridge"].status is RouteStatus.OPEN)

    adaptations = [e for e in plan_changes(world, KABIR) if e.data["adaptation"]]
    assert adaptations, "Kabir should adapt to the blocked bridge"
    assert adaptations[0].data["old_strategy"] == "repair_bridge"
    assert adaptations[0].data["new_strategy"] == "clear_and_repair_bridge"
    assert "blocked" in adaptations[0].data["trigger"]
    # The adaptation changed what he actually did, not just what he said.
    kinds_by_kabir = [e.kind for e in world.events if e.actor == KABIR]
    assert EventKind.ROUTE_CLEARED in kinds_by_kabir
    assert kinds_by_kabir.index(EventKind.ROUTE_CLEARED) < kinds_by_kabir.index(EventKind.BRIDGE_REPAIRED)


def test_without_timber_kabir_waits_then_takes_meeras_trail(world):
    agents = agents_for(world, KABIR, MEERA)
    player(world, ARIA, A.PICK_UP, object_id="timber_planks")  # the player takes Kabir's materials
    run_until(world, agents, lambda w: w.characters[KABIR].location_id == TEMPLE)

    changes = plan_changes(world, KABIR)
    strategies = [e.data["new_strategy"] for e in changes]
    assert "await_route" in strategies and "route_via_forest" in strategies
    switch = next(e for e in changes if e.data["new_strategy"] == "route_via_forest")
    assert switch.data["adaptation"] and "horn signal" in switch.data["trigger"]
    arrival = next(e for e in world.events if e.actor == KABIR and e.kind is EventKind.ARRIVED and e.location_id == TEMPLE)
    assert arrival.data["route_id"] == "forest_trail"
    assert world.routes["main_bridge"].status is RouteStatus.BROKEN  # the default bridge repair never happened


def test_team_finishes_mission_even_if_player_does_nothing(world):
    agents = agents_for(world, KABIR, MEERA)  # Aria is player-controlled but idle at the harbour
    run_until(world, agents, lambda w: w.lighthouse.activated)
    lever = next(e for e in world.events if e.kind is EventKind.GATE_OPENED)
    assert lever.actor == KABIR  # Kabir rigged the lever because Aria never came
    pickup = next(e for e in world.events if e.kind is EventKind.ITEM_PICKED_UP and e.data["object_id"] == SUN_CRYSTAL)
    assert pickup.actor in (KABIR, MEERA)
    assert world.characters[ARIA].location_id == HARBOUR


def test_same_start_different_decisions_different_outcomes():
    undisturbed = _autonomous_run()

    world = build_initial_world("b", GameMode.GAME)
    agents = agents_for(world, KABIR, MEERA)
    player(world, ARIA, A.PICK_UP, object_id="timber_planks")
    run_until(world, agents, lambda w: w.lighthouse.activated, limit=1200)  # deadlines arrive in Step 6
    assert world.lighthouse.activated_at > undisturbed.lighthouse.activated_at  # taking the timber cost time
    routes = lambda w: {e.data.get("route_id") for e in w.events if e.kind is EventKind.ARRIVED}  # noqa: E731
    assert "forest_trail" in routes(world) - routes(undisturbed) or "main_bridge" in routes(undisturbed) - routes(world)
