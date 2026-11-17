"""Mind View: the decision trace and beliefs-versus-reality shown for each character."""

from app.agents.character_agent import CharacterAgent
from app.agents.commands import parse_fallback
from app.engine.ids import ARIA, FOREST_TRAIL, KABIR, MAIN_BRIDGE, MEERA, TIMBER
from app.engine.run import Run
from app.models.enums import GameMode
from app.schemas.views import character_views


def run_until(run: Run, seconds: int) -> Run:
    run.start()
    while run.world.clock.now < seconds:
        run.tick()
    return run


def mind_of_world(world, cid: str):
    return next(c.mind for c in character_views(world) if c.id == cid)


def mind_of(run: Run, cid: str):
    return mind_of_world(run.world, cid)


def test_trace_lists_the_options_and_marks_the_chosen_one():
    run = run_until(Run.create(GameMode.DEFAULT), 120)
    thinking = mind_of(run, ARIA).thinking
    assert thinking is not None and thinking.chosen_by == "rules"
    assert [o.chosen for o in thinking.options].count(True) == 1
    assert thinking.options[0].strategy == "wait_at_temple" and thinking.options[0].chosen
    assert "decode_symbols_myself" in {o.strategy for o in thinking.options}


def test_long_wait_is_logged_with_the_alternatives():
    run = Run.create(GameMode.DEFAULT)
    run.run_to_end()
    episode = next(e for e in run.world.minds[ARIA].wait_log if e.strategy == "wait_at_temple")
    assert episode.ended_at is not None and episode.ended_at - episode.started_at >= 100
    assert "decode_symbols_myself" in {a.strategy for a in episode.alternatives}


def test_outdated_belief_is_flagged_against_reality():
    run = run_until(Run.create(GameMode.DEFAULT), 120)
    # Kabir repaired the bridge at ~99s; Meera was in the forest and has not seen or heard it yet.
    bridge = next(f for f in mind_of(run, MEERA).beliefs if f.route_id == MAIN_BRIDGE)
    assert run.world.routes[MAIN_BRIDGE].status.value == "open"
    assert bridge.believed == "broken" and bridge.actual == "open" and not bridge.up_to_date
    assert mind_of(run, MEERA).outdated >= 1


def test_the_hidden_trail_is_not_revealed_before_it_is_found():
    run = Run.create(GameMode.DEFAULT)
    facts = mind_of(run, KABIR).beliefs
    assert all(f.route_id != FOREST_TRAIL for f in facts)


def test_a_character_knows_it_no_longer_holds_what_it_used():
    run = run_until(Run.create(GameMode.DEFAULT), 120)
    assert TIMBER not in run.world.objects  # used to repair the bridge
    timber = next(f for f in mind_of(run, KABIR).beliefs if f.kind == "item" and f.subject == "Timber Planks")
    assert timber.believed == "whereabouts unknown" and timber.up_to_date


def test_ai_reason_appears_in_the_trace(world):
    mind = world.minds[KABIR]
    mind.preferred_strategy, mind.preference_thought = "secure_lighthouse", "The lighthouse is right next to us."
    CharacterAgent(KABIR).step(world)
    thinking = mind_of_world(world, KABIR).thinking
    assert thinking.chosen == "secure_lighthouse" and thinking.chosen_by == "ai"
    assert thinking.thought == "The lighthouse is right next to us."
    assert thinking.options[0].strategy != "secure_lighthouse"  # the AI picked a non-default option


def test_player_orders_show_as_chosen_by_the_player():
    run = Run.create(GameMode.GAME, player_character=ARIA)
    run.start()
    text = "Kabir, repair the lighthouse"
    assert run.give_command(text, parse_fallback(run.world, ARIA, text), "keyword parser").ok
    run.tick()
    assert mind_of(run, KABIR).thinking.chosen_by == "player"


def test_memories_are_newest_first_and_skip_routine_waits():
    run = run_until(Run.create(GameMode.DEFAULT), 150)
    memories = mind_of(run, ARIA).memories
    assert memories and all(m.importance >= 2 for m in memories)
    assert [m.time for m in memories] == sorted((m.time for m in memories), reverse=True)
