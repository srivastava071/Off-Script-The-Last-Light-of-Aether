import pytest
from pydantic import ValidationError

from app.engine.aether import ARIA, BRIDGE, FOREST, HARBOUR, KABIR, LIGHTHOUSE, MEERA
from app.engine.rules import available_actions
from app.engine.run import Run
from app.models.actions import ProposedAction
from app.models.enums import ActionType as A
from app.models.enums import EventKind, GameMode, RunStatus


def game(player):
    run = Run.create(GameMode.GAME, player)
    run.start()
    return run


def act(run, type, request_id=None, **kw):
    action = ProposedAction(actor=run.world.story.player_character, type=type, **kw)
    return run.player_action(action, request_id=request_id)


def events_of(run, kind, actor=None):
    return [e for e in run.world.events if e.kind is kind and (actor is None or e.actor == actor)]


def tick_until(run, done, limit=400):
    for _ in range(limit):
        if done(run) or run.status is RunStatus.FINISHED:
            return
        run.tick()
    raise AssertionError("condition never reached")


# --- asking ---------------------------------------------------------------------------------------------

def test_ask_about_plan_reveals_the_agents_real_plan():
    run = game(ARIA)
    run.tick()  # Kabir has decided something by now
    # Kabir is still at the harbour gathering supplies
    result = act(run, A.ASK, target_id=KABIR, topic="plan")
    assert result.ok
    assert run.world.minds[KABIR].plan.summary in result.events[0].description


def test_ask_for_news_passes_on_knowledge():
    run = game(ARIA)
    w = run.world
    w.clock.now = 30
    w.routes["coast_road"].obstructed, w.routes["coast_road"].blocked_by = True, MEERA
    w.characters[KABIR].location_id = BRIDGE
    from app.engine import knowledge
    knowledge.perceive(w, KABIR)          # Kabir sees the blocked road from the bridge
    w.characters[KABIR].location_id = HARBOUR
    assert not w.minds[ARIA].beliefs.routes["coast_road"].obstructed

    assert act(run, A.ASK, target_id=KABIR, topic="news").ok
    assert w.minds[ARIA].beliefs.routes["coast_road"].obstructed
    assert any(m.source == f"told:{KABIR}" for m in w.minds[ARIA].memories)


def test_ask_requires_topic_and_presence():
    run = game(ARIA)
    assert "plan" in act(run, A.ASK, target_id=KABIR).message
    run.world.characters[MEERA].location_id = FOREST
    assert "not here" in act(run, A.ASK, target_id=MEERA, topic="plan").message


# --- talking ------------------------------------------------------------------------------------------------

def test_agents_reply_when_spoken_to():
    run = game(ARIA)
    run.tick()  # Meera has left for the forest; Kabir is still packing at the harbour
    result = act(run, A.TALK, target_id=KABIR, message="Where are you headed?")
    replies = [e for e in result.events if e.kind is EventKind.TALKED and e.actor == KABIR]
    assert replies and run.world.minds[KABIR].plan.summary in replies[0].description


# --- requesting help ---------------------------------------------------------------------------------------

def test_request_for_an_item_is_accepted_and_carried_out():
    run = game(MEERA)
    result = act(run, A.REQUEST_HELP, target_id=KABIR, request=A.GIVE, object_id="toolkit")
    assert result.ok
    assert any(e.kind is EventKind.HELP_ACCEPTED for e in result.events)
    run.tick()
    assert run.world.objects["toolkit"].carried_by == MEERA


def test_request_must_be_physically_possible():
    run = game(ARIA)
    result = act(run, A.REQUEST_HELP, target_id=MEERA, request=A.REPAIR_BRIDGE)
    assert not result.ok and "Meera cannot do that" in result.message


def test_meet_me_request_changes_where_the_agent_goes():
    run = game(ARIA)
    assert act(run, A.REQUEST_HELP, target_id=MEERA, request=A.MOVE, destination=LIGHTHOUSE).ok
    tick_until(run, lambda r: r.world.characters[MEERA].location_id == LIGHTHOUSE)
    first_trip = events_of(run, EventKind.TRAVEL_STARTED, MEERA)[0]
    assert first_trip.data["destination"] == LIGHTHOUSE  # not the forest, as in the default story
    assert run.world.minds[MEERA].requests == []
    tick_until(run, lambda r: r.world.characters[MEERA].location_id == FOREST)  # then she resumes her role


def test_distrusted_player_is_refused():
    run = game(ARIA)
    run.world.minds[KABIR].trust[ARIA] = -3
    result = act(run, A.REQUEST_HELP, target_id=KABIR, request=A.GIVE, object_id="toolkit")
    declined = [e for e in result.events if e.kind is EventKind.HELP_DECLINED]
    assert declined and "doesn't trust" in declined[0].description
    run.tick()
    assert run.world.objects["toolkit"].carried_by == KABIR


def test_blocking_a_route_in_front_of_someone_costs_their_trust(world):
    from app.engine import knowledge
    from app.engine.rules import perform
    from app.engine.timeline import advance_clock
    world.characters[ARIA].location_id = world.characters[KABIR].location_id = BRIDGE
    world.characters[MEERA].location_id = FOREST
    result = perform(world, ProposedAction(actor=ARIA, type=A.BLOCK_ROUTE, route_id="main_bridge"))
    knowledge.observe(world, result.events)
    advance_clock(world, 20, lambda new: knowledge.observe(world, new))
    assert world.minds[KABIR].trust[ARIA] == -1   # saw it happen: 1 - 2
    assert world.minds[MEERA].trust[ARIA] == 1    # was elsewhere: unchanged


def test_requests_cannot_nest():
    with pytest.raises(ValidationError):
        ProposedAction(actor=ARIA, type=A.REQUEST_HELP, target_id=KABIR, request=A.REQUEST_HELP)


def test_promise_lapses_if_requester_walks_away():
    run = game(MEERA)
    assert act(run, A.REQUEST_HELP, target_id=KABIR, request=A.GIVE, object_id="toolkit").ok
    run.world.characters[MEERA].location_id = FOREST  # she is no longer there to receive it
    run.tick()
    assert any("can no longer help" in e.description for e in events_of(run, EventKind.HELP_DECLINED, KABIR))
    assert run.world.objects["toolkit"].carried_by == KABIR


# --- reliability ----------------------------------------------------------------------------------------------

def test_duplicate_request_id_is_applied_once():
    run = game(ARIA)
    first = act(run, A.MOVE, request_id="req-1", destination=BRIDGE)
    events_after_first = len(run.world.events)
    again = act(run, A.MOVE, request_id="req-1", destination=BRIDGE)
    assert first.ok and again.ok and again.duplicate
    assert len(run.world.events) == events_after_first


def test_spamming_actions_is_rejected_until_time_passes():
    run = game(ARIA)
    assert act(run, A.INSPECT).ok
    for _ in range(20):
        assert not act(run, A.INSPECT).ok  # busy: no free actions
    run.tick(); run.tick()
    assert act(run, A.INSPECT).ok


def test_player_cannot_edit_world_through_actions():
    for bad in ({"deadline": 9999}, {"clock": 0}, {"location_id": "chamber"}, {"memories": []}):
        with pytest.raises(ValidationError):
            ProposedAction(actor=ARIA, type=A.WAIT, **bad)


def test_restart_is_a_new_run_with_a_fresh_clock_not_a_reset():
    run = game(ARIA)
    tick_until(run, lambda r: r.world.clock.now >= 100)
    fresh = game(ARIA)
    assert fresh.world.run_id != run.world.run_id
    assert run.world.clock.now >= 100 and run.world.clock.deadline == 600  # the old run is untouched


def test_menu_offers_social_actions_only_when_possible():
    run = game(ARIA)
    labels = [o.label for o in available_actions(run.world, ARIA) if o.available]
    assert "Ask Kabir about their plan" in labels and "Ask Meera for news" in labels
    assert "Ask Kabir to hand over the Engineer's Toolkit" in labels
    assert not any(label.startswith("Ask Meera to repair") for label in labels)
    assert "Ask Kabir to meet at the Lighthouse" in labels
