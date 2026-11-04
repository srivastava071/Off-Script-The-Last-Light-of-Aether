import pytest

from app.agents.director import DEFAULT_SIGNATURE, Director
from app.engine.aether import ARIA, BRIDGE, KABIR, MEERA, SUN_CRYSTAL, TEMPLE
from app.engine.invariants import check_invariants
from app.engine.rules import check_action
from app.engine.run import Run, RunError
from app.models.actions import ProposedAction
from app.models.enums import ActionType as A
from app.models.enums import EndingId, EventKind, GameMode, ObjectiveStatus, RunStatus


def act(run, type, **kw):
    return run.player_action(ProposedAction(actor=run.world.story.player_character, type=type, **kw))


def tick_until(run, done, limit=2000):
    for _ in range(limit):
        if done(run) or run.status is RunStatus.FINISHED:
            return
        run.tick()
        assert check_invariants(run.world) == []
    raise AssertionError("condition never reached")


def finish(run):
    tick_until(run, lambda r: False)


def game(player):
    run = Run.create(GameMode.GAME, player)
    run.start()
    return run


# --- Default Mode -------------------------------------------------------------------------------------

@pytest.fixture(scope="module")
def default_run():
    run = Run.create(GameMode.DEFAULT)
    run.run_to_end()
    return run


def test_default_mode_reaches_the_light_returns(default_run):
    ending = default_run.world.story.ending
    assert ending.ending is EndingId.LIGHT_RETURNS and ending.title == "The Light Returns"
    assert ending.main_success
    assert all(o.status is ObjectiveStatus.COMPLETE for o in ending.objectives)
    assert Director.signature(default_run.world) == DEFAULT_SIGNATURE


def test_default_mode_takes_about_five_minutes(default_run):
    assert 270 <= default_run.world.story.ending.finished_at <= 360


def test_default_mode_hits_every_story_beat_in_order(default_run):
    times = [b.reached_at for b in default_run.world.story.beats]
    assert all(t is not None for t in times)
    assert times == sorted(times)


def test_default_mode_is_reproducible(default_run):
    again = Run.create(GameMode.DEFAULT, run_id=default_run.world.run_id)
    again.run_to_end()
    assert again.world.model_dump() == default_run.world.model_dump()


def test_default_mode_refuses_player_input():
    run = Run.create(GameMode.DEFAULT)
    run.start()
    result = run.player_action(ProposedAction(actor=ARIA, type=A.MOVE, destination=BRIDGE))
    assert not result.ok and "player input is disabled" in result.message


def test_default_mode_report_lists_routes_and_events(default_run):
    ending = default_run.world.story.ending
    assert ending.routes[ARIA][0] == "Abandoned Harbour" and ending.routes[ARIA][-1] == "Lighthouse"
    assert any("lights" in e or "barrier rises" in e for e in ending.key_events)
    assert ending.stats["adaptations"] == 0


# --- creation and control ---------------------------------------------------------------------------------

@pytest.mark.parametrize("player", [ARIA, KABIR, MEERA])
def test_any_character_can_be_selected(player):
    run = game(player)
    assert run.world.story.player_character == player
    assert player not in run.agents and len(run.agents) == 2
    assert run.world.clock.deadline == 600


def test_invalid_run_configurations_are_rejected():
    with pytest.raises(RunError):
        Run.create(GameMode.GAME, None)
    with pytest.raises(RunError):
        Run.create(GameMode.GAME, "ghost")
    with pytest.raises(RunError):
        Run.create(GameMode.DEFAULT, ARIA)


def test_player_controls_only_their_character():
    run = game(ARIA)
    result = run.player_action(ProposedAction(actor=KABIR, type=A.MOVE, destination=BRIDGE))
    assert not result.ok and "You control Aria only" in result.message


def test_player_cannot_act_before_start():
    run = Run.create(GameMode.GAME, ARIA)
    assert not act(run, A.INSPECT).ok


def test_other_agents_act_while_player_is_idle():
    run = game(ARIA)
    tick_until(run, lambda r: r.world.clock.now >= 120)
    actors = {e.actor for e in run.world.events if e.kind is EventKind.TRAVEL_STARTED}
    assert {KABIR, MEERA} <= actors and ARIA not in actors


# --- endings ---------------------------------------------------------------------------------------------

def test_deadline_failure_when_the_engineer_does_nothing():
    run = game(KABIR)  # nobody else can repair the temple mechanism
    finish(run)
    ending = run.world.story.ending
    assert ending.ending is EndingId.LAST_STORM and not ending.main_success
    assert run.world.clock.now == 600  # stops exactly at the deadline, never past it
    assert "temple mechanism" in ending.explanation
    assert len([e for e in run.world.events if e.kind is EventKind.STORM_WARNING]) == 3


def test_unexpected_route_when_aria_stays_home():
    run = game(ARIA)
    finish(run)
    ending = run.world.story.ending
    assert ending.ending is EndingId.UNEXPECTED_ROUTE and ending.main_success
    assert Director.signature(run.world)["gate_opened_by"] == KABIR


def test_costly_victory_when_player_takes_the_timber():
    run = game(ARIA)
    assert act(run, A.PICK_UP, object_id="timber_planks").ok
    finish(run)
    ending = run.world.story.ending
    assert ending.ending is EndingId.COSTLY_VICTORY and ending.main_success
    bridge = next(o for o in ending.objectives if o.id == "bridge_restored")
    assert bridge.status is ObjectiveStatus.FAILED
    assert ending.stats["adaptations"] >= 1


def test_blocking_the_bridge_triggers_adaptation_and_still_succeeds():
    run = game(ARIA)
    assert act(run, A.MOVE, destination=BRIDGE).ok
    tick_until(run, lambda r: r.world.characters[ARIA].location_id == BRIDGE)
    assert act(run, A.BLOCK_ROUTE, route_id="main_bridge").ok
    finish(run)
    ending = run.world.story.ending
    assert ending.main_success
    assert any("Kabir adapts" in a for a in ending.adaptations)
    assert ending.stats["blocked_route_events"] == 1


def test_crystal_lost_in_flood_ends_the_run_early():
    """Aria opens the gate herself and then dawdles; her teammates assume she has the crystal."""
    run = game(ARIA)
    assert act(run, A.MOVE, destination=BRIDGE).ok
    tick_until(run, lambda r: not r.world.characters[ARIA].busy)
    assert act(run, A.MOVE, destination=TEMPLE).ok
    lever = ProposedAction(actor=ARIA, type=A.PULL_LEVER)
    tick_until(run, lambda r: not r.world.characters[ARIA].busy and check_action(r.world, lever) is None)
    assert run.player_action(lever).ok
    finish(run)
    ending = run.world.story.ending
    assert ending.ending is EndingId.LAST_STORM
    assert "lost" in ending.explanation
    assert run.world.clock.now < 600
    assert run.world.objects[SUN_CRYSTAL].location_id == "chamber"


# --- terminal state ---------------------------------------------------------------------------------------

def test_single_terminal_state_and_no_actions_after_end(default_run):
    before = default_run.world.model_dump()
    assert default_run.tick() == []
    assert default_run.world.model_dump() == before
    assert sum(1 for e in default_run.world.events if e.kind is EventKind.RUN_ENDED) == 1

    run = game(KABIR)
    finish(run)
    result = act(run, A.WAIT, seconds=10)
    assert not result.ok and "ended" in result.message
    assert run.world.story.ending.ending is EndingId.LAST_STORM


def test_success_is_never_overturned_by_the_deadline():
    run = game(ARIA)
    finish(run)
    assert run.world.story.ending.main_success
    run.world.clock.now = 10_000  # even if time somehow moved on, the ending is fixed
    assert Director().evaluate(run.world) == []
    assert run.world.story.ending.main_success


def test_director_never_changes_the_physical_world():
    run = game(KABIR)
    tick_until(run, lambda r: r.world.clock.now >= 200)
    physical = ("routes", "objects", "characters", "temple_lock", "lighthouse", "flood", "minds", "scheduled")
    before = run.world.model_dump(include=set(physical))
    run.world.clock.now += 130  # force a stall check and a storm warning
    assert Director().evaluate(run.world)  # it does narrate...
    assert run.world.model_dump(include=set(physical)) == before  # ...but changes nothing physical
