"""The rules engine: the only way players and agents change the world.

``perform`` validates a ProposedAction and starts it. Every action has an explicit duration:
- immediate actions apply now and keep the actor busy for their duration (a cooldown);
- deferred actions apply when they complete, after re-checking their preconditions.
A busy actor cannot start another action, so actions cannot be spammed without time passing.
"""

from collections.abc import Callable
from dataclasses import dataclass

from pydantic import BaseModel

from app.engine import knowledge
from app.engine import obstacles as ob
from app.engine.aether import (
    BLOCK_ROUTE_SECONDS, BRIDGE, BRIDGE_REPAIR_SECONDS, CLEAR_ROUTE_SECONDS, LIGHTHOUSE, LIGHTHOUSE_REPAIR_SECONDS,
    MECHANISM_REPAIR_SECONDS, TEMPLE,
)
from app.engine.movement import move_blocker, start_travel, travel_seconds
from app.engine.objects import drop, drop_blocker, give, give_blocker, pick_up, pick_up_blocker
from app.models.actions import ActionResult, ProposedAction
from app.models.enums import Ability, ActionType, EventKind
from app.models.events import WorldEvent
from app.models.world import Activity, CharacterState, WorldState

Check = Callable[[WorldState, ProposedAction], str | None]
Apply = Callable[[WorldState, ProposedAction], list[WorldEvent]]
Seconds = Callable[[WorldState, ProposedAction], int]


@dataclass(frozen=True)
class Rule:
    check: Check
    apply: Apply
    seconds: Seconds
    deferred: bool
    verb: str  # "{name} begins to {verb}"


def _fixed(n: int) -> Seconds:
    return lambda _w, _a: n


def _no_check(_w: WorldState, _a: ProposedAction) -> str | None:
    return None


# --- simple actions -------------------------------------------------------------------------

def _wait_apply(w: WorldState, a: ProposedAction) -> list[WorldEvent]:
    secs = a.seconds or w.clock.tick_seconds
    return [w.record(EventKind.WAITED, f"{w.name(a.actor)} waits for {secs}s.",
                     actor=a.actor, location_id=w.characters[a.actor].location_id)]


def _inspect_apply(w: WorldState, a: ProposedAction) -> list[WorldEvent]:
    here = w.characters[a.actor].location_id
    assert here is not None
    loc = w.locations[here]
    routes = []
    for r in w.routes_from(here):
        if r.hidden:
            continue
        state = "blocked" if r.obstructed else r.status.value
        trap = ", trapped" if r.hazard_active else ""
        routes.append(f"{r.name} to {w.locations[r.other_end(here)].name} ({state}{trap})")
    objs = [o.name for o in w.objects_at(here)]
    people = [w.name(c) for c in w.characters_at(here) if c != a.actor]
    text = f"{w.name(a.actor)} looks around the {loc.name}. {loc.description}"
    text += f" Paths: {'; '.join(routes) or 'none'}."
    if objs:
        text += f" Items here: {', '.join(objs)}."
    if people:
        text += f" Also here: {', '.join(people)}."
    return [w.record(EventKind.INSPECTED, text, actor=a.actor, location_id=here,
                     routes=[r.id for r in w.routes_from(here) if not r.hidden], objects=[o.id for o in w.objects_at(here)])]


def _talk_check(w: WorldState, a: ProposedAction) -> str | None:
    if a.target_id is None or a.target_id not in w.characters:
        return f"Unknown character '{a.target_id}'."
    if a.target_id == a.actor:
        return "A character cannot talk to themselves."
    here = w.characters[a.actor].location_id
    if here is None or w.characters[a.target_id].location_id != here:
        return f"{w.name(a.target_id)} is not here."
    return None


def _talk_apply(w: WorldState, a: ProposedAction) -> list[WorldEvent]:
    assert a.target_id is not None
    said = f': "{a.message}"' if a.message else "."
    return [w.record(EventKind.TALKED, f"{w.name(a.actor)} speaks with {w.name(a.target_id)}{said}",
                     actor=a.actor, location_id=w.characters[a.actor].location_id,
                     target=a.target_id, message=a.message)]


def _ask_check(w: WorldState, a: ProposedAction) -> str | None:
    if a.topic is None:
        return "Ask about 'plan' or 'news'."
    return _talk_check(w, a)


def _ask_apply(w: WorldState, a: ProposedAction) -> list[WorldEvent]:
    assert a.target_id is not None and a.topic is not None
    reply = knowledge.answer(w, a.target_id, a.topic)
    question = "what their plan is" if a.topic == "plan" else "for news"
    return [w.record(EventKind.ASKED, f"{w.name(a.actor)} asks {w.name(a.target_id)} {question}. {reply}",
                     actor=a.actor, location_id=w.characters[a.actor].location_id,
                     target=a.target_id, topic=a.topic, reply=reply)]


NOT_REQUESTABLE = {ActionType.WAIT, ActionType.INSPECT}


def requested_action(a: ProposedAction) -> ProposedAction:
    """The action the helper would take on the requester's behalf."""
    assert a.target_id is not None and a.request is not None
    return ProposedAction(
        actor=a.target_id, type=a.request, destination=a.destination, route_id=a.route_id,
        object_id=a.object_id, target_id=a.actor if a.request is ActionType.GIVE else None,
    )


def request_blocker(w: WorldState, a: ProposedAction) -> str | None:
    """Can the helper physically do what is asked? (Whether they *agree* is the helper's decision.)"""
    if a.request is None:
        return "Say what you need help with."
    if a.request in NOT_REQUESTABLE:
        return "That is not something to ask for help with."
    helper = a.target_id or ""
    wanted = requested_action(a)
    if wanted.type is ActionType.MOVE:
        if wanted.destination not in w.locations:
            return f"Unknown location '{wanted.destination}'."
        if w.characters[helper].location_id == wanted.destination:
            return f"{w.name(helper)} is already there."
        return None
    if reason := RULES[wanted.type].check(w, wanted):
        return f"{w.name(helper)} cannot do that: {reason}"
    return None


def _request_check(w: WorldState, a: ProposedAction) -> str | None:
    return _talk_check(w, a) or request_blocker(w, a)


def _request_apply(w: WorldState, a: ProposedAction) -> list[WorldEvent]:
    assert a.target_id is not None
    wanted = requested_action(a)
    return [w.record(EventKind.HELP_REQUESTED,
                     f"{w.name(a.actor)} asks {w.name(a.target_id)} to {_request_phrase(w, wanted)}.",
                     actor=a.actor, location_id=w.characters[a.actor].location_id, target=a.target_id,
                     request=wanted.model_dump(mode="json", exclude_none=True))]


def _request_phrase(w: WorldState, wanted: ProposedAction) -> str:
    if wanted.type is ActionType.GIVE:
        return f"hand over the {w.objects[wanted.object_id or ''].name}"
    if wanted.type is ActionType.MOVE:
        return f"meet at the {w.locations[wanted.destination or ''].name}"
    if wanted.route_id:
        return f"{RULES[wanted.type].verb} ({w.routes[wanted.route_id].name})"
    return RULES[wanted.type].verb


def _signal_check(w: WorldState, a: ProposedAction) -> str | None:
    if not w.profiles[a.actor].has(Ability.SIGNAL):
        return f"{w.name(a.actor)} has no way to signal the team from afar."
    return None


def _signal_apply(w: WorldState, a: ProposedAction) -> list[WorldEvent]:
    # The knowledge layer turns this event into route reports for every teammate.
    said = f': "{a.message}"' if a.message else "."
    return [w.record(EventKind.SIGNALLED, f"{w.name(a.actor)} sounds the horn code to the team{said}",
                     actor=a.actor, location_id=w.characters[a.actor].location_id, message=a.message)]


def _events(result: ActionResult) -> list[WorldEvent]:
    return result.events


RULES: dict[ActionType, Rule] = {
    ActionType.WAIT: Rule(_no_check, _wait_apply, lambda w, a: a.seconds or w.clock.tick_seconds, False, "wait"),
    ActionType.INSPECT: Rule(_no_check, _inspect_apply, _fixed(10), False, "look around"),
    ActionType.TALK: Rule(_talk_check, _talk_apply, _fixed(5), False, "talk"),
    ActionType.SIGNAL: Rule(_signal_check, _signal_apply, _fixed(5), False, "signal the team"),
    ActionType.ASK: Rule(_ask_check, _ask_apply, _fixed(5), False, "ask a question"),
    ActionType.REQUEST_HELP: Rule(_request_check, _request_apply, _fixed(5), False, "ask for help"),
    ActionType.PICK_UP: Rule(
        lambda w, a: pick_up_blocker(w, a.actor, a.object_id),
        lambda w, a: _events(pick_up(w, a.actor, a.object_id or "")), _fixed(5), False, "pick something up"),
    ActionType.DROP: Rule(
        lambda w, a: drop_blocker(w, a.actor, a.object_id),
        lambda w, a: _events(drop(w, a.actor, a.object_id or "")), _fixed(5), False, "put something down"),
    ActionType.GIVE: Rule(
        lambda w, a: give_blocker(w, a.actor, a.target_id, a.object_id),
        lambda w, a: _events(give(w, a.actor, a.target_id or "", a.object_id or "")), _fixed(5), False, "hand over an item"),
    ActionType.DISCOVER_ROUTE: Rule(ob.discover_route_check, ob.discover_route_apply, ob.discover_route_seconds, True,
                                    "search for hidden paths"),
    ActionType.DETECT_TRAPS: Rule(ob.detect_traps_check, ob.detect_traps_apply, _fixed(15), True, "search for traps"),
    ActionType.REPAIR_BRIDGE: Rule(ob.repair_bridge_check, ob.repair_bridge_apply, _fixed(BRIDGE_REPAIR_SECONDS), True,
                                   "repair the Main Bridge"),
    ActionType.BLOCK_ROUTE: Rule(ob.block_route_check, ob.block_route_apply, _fixed(BLOCK_ROUTE_SECONDS), True, "block a route"),
    ActionType.CLEAR_ROUTE: Rule(ob.clear_route_check, ob.clear_route_apply, _fixed(CLEAR_ROUTE_SECONDS), True, "clear a blocked route"),
    ActionType.REPAIR_MECHANISM: Rule(ob.repair_mechanism_check, ob.repair_mechanism_apply, _fixed(MECHANISM_REPAIR_SECONDS), True,
                                      "repair the temple mechanism"),
    ActionType.DECODE_SYMBOLS: Rule(ob.decode_symbols_check, ob.decode_symbols_apply, ob.decode_symbols_seconds, True,
                                    "decode the temple symbols"),
    ActionType.PULL_LEVER: Rule(ob.pull_lever_check, ob.pull_lever_apply, ob.pull_lever_seconds, True,
                                "work the elevated lever"),
    ActionType.REPAIR_LIGHTHOUSE: Rule(ob.repair_lighthouse_check, ob.repair_lighthouse_apply, _fixed(LIGHTHOUSE_REPAIR_SECONDS), True,
                                       "repair the lighthouse mechanism"),
    ActionType.INSTALL_CRYSTAL: Rule(ob.install_crystal_check, ob.install_crystal_apply, _fixed(10), True,
                                     "install the Sun Crystal"),
    ActionType.ACTIVATE_LIGHTHOUSE: Rule(ob.activate_lighthouse_check, ob.activate_lighthouse_apply, _fixed(10), True,
                                         "activate the lighthouse"),
}


# What each action needs from the character itself (any one of the listed abilities). Used to refuse
# impossible orders up front; location, items and world state are checked when the action is tried.
REQUIRES_ANY: dict[ActionType, tuple[Ability, ...]] = {
    ActionType.REPAIR_BRIDGE: (Ability.BUILD_BRIDGE,),
    ActionType.REPAIR_MECHANISM: (Ability.REPAIR,),
    ActionType.REPAIR_LIGHTHOUSE: (Ability.REPAIR,),
    ActionType.DECODE_SYMBOLS: (Ability.DECODE_SYMBOLS, Ability.INSPECT_CLUES),
    ActionType.PULL_LEVER: (Ability.CLIMB, Ability.OPERATE_MECHANISM),
    ActionType.DISCOVER_ROUTE: (Ability.DISCOVER_ROUTES, Ability.INSPECT_CLUES),
    ActionType.DETECT_TRAPS: (Ability.DETECT_TRAPS,),
    ActionType.SIGNAL: (Ability.SIGNAL,),
}
NEEDS_STRENGTH = {ActionType.BLOCK_ROUTE, ActionType.CLEAR_ROUTE}


def capability_blocker(world: WorldState, actor: str, action_type: ActionType) -> str | None:
    """Can this character ever do this kind of action? (Ignores where they are and what they carry.)"""
    profile = world.profiles[actor]
    needed = REQUIRES_ANY.get(action_type)
    if needed and not any(profile.has(a) for a in needed):
        return f"{profile.name} cannot {RULES[action_type].verb}."
    if action_type in NEEDS_STRENGTH and not profile.can_carry_heavy:
        return f"{profile.name} is not strong enough to {RULES[action_type].verb}."
    return None


def _busy_reason(world: WorldState, state: CharacterState) -> str | None:
    name = world.name(state.id)
    if state.travel is not None:
        return f"{name} is travelling until t={state.travel.arrive_at}s."
    if state.activity is not None:
        verb = RULES[state.activity.action.type].verb
        return f"{name} is busy ({verb}) until t={state.activity.completes_at}s."
    return None


def check_action(world: WorldState, action: ProposedAction) -> str | None:
    """Why this action cannot start now, or None if it can. Never mutates the world."""
    if action.actor not in world.characters:
        return f"Unknown character '{action.actor}'."
    if reason := _busy_reason(world, world.characters[action.actor]):
        return reason
    if action.type is ActionType.MOVE:
        if action.destination is None:
            return "No destination given."
        return move_blocker(world, action.actor, action.destination, action.route_id)
    return RULES[action.type].check(world, action)


def action_seconds(world: WorldState, action: ProposedAction) -> int:
    if action.type is ActionType.MOVE:
        state = world.characters[action.actor]
        routes = [r for r in world.routes_from(state.location_id or "")
                  if r.other_end(state.location_id or "") == action.destination
                  and (action.route_id is None or r.id == action.route_id)]
        return min((travel_seconds(world, action.actor, r) for r in routes), default=0)
    return RULES[action.type].seconds(world, action)


def perform(world: WorldState, action: ProposedAction) -> ActionResult:
    """Validate and start an action. Returns a rejection with a reason if it is not allowed."""
    if reason := check_action(world, action):
        return ActionResult.reject(reason)
    if action.type is ActionType.MOVE:
        assert action.destination is not None
        return start_travel(world, action.actor, action.destination, action.route_id)

    rule = RULES[action.type]
    state = world.characters[action.actor]
    now = world.clock.now
    seconds = rule.seconds(world, action)
    if rule.deferred:
        events = [world.record(
            EventKind.ACTION_STARTED, f"{world.name(action.actor)} begins to {rule.verb} ({seconds}s).",
            actor=action.actor, location_id=state.location_id, action=action.type.value, completes_at=now + seconds,
        )]
    else:
        events = rule.apply(world, action)
    state.activity = Activity(action=action, started_at=now, completes_at=now + seconds, deferred=rule.deferred)
    message = events[-1].description if events else f"{world.name(action.actor)} acts."
    return ActionResult.success(message, *events, completes_at=now + seconds)


def complete_activity(world: WorldState, state: CharacterState) -> list[WorldEvent]:
    """Called by the timeline when an activity's time is up."""
    activity = state.activity
    assert activity is not None
    state.activity = None
    if not activity.deferred:
        return []
    rule = RULES[activity.action.type]
    if reason := rule.check(world, activity.action):
        return [world.record(
            EventKind.ACTION_FAILED, f"{world.name(state.id)} could not {rule.verb}: {reason}",
            actor=state.id, location_id=state.location_id, action=activity.action.type.value, reason=reason,
        )]
    return rule.apply(world, activity.action)


# --- contextual action menu ------------------------------------------------------------------

class ActionOption(BaseModel):
    action: ProposedAction
    label: str
    seconds: int
    available: bool
    reason: str | None = None


def _label(world: WorldState, a: ProposedAction) -> str:
    t = a.type
    if t is ActionType.MOVE:
        route = world.routes[a.route_id] if a.route_id else None
        via = f" via {route.name}" if route else ""
        return f"Go to {world.locations[a.destination or ''].name}{via}"
    if t in (ActionType.PICK_UP, ActionType.DROP):
        return f"{'Pick up' if t is ActionType.PICK_UP else 'Drop'} {world.objects[a.object_id or ''].name}"
    if t is ActionType.GIVE:
        return f"Give {world.objects[a.object_id or ''].name} to {world.name(a.target_id or '')}"
    if t is ActionType.TALK:
        return f"Talk to {world.name(a.target_id or '')}"
    if t is ActionType.ASK:
        about = "about their plan" if a.topic == "plan" else "for news"
        return f"Ask {world.name(a.target_id or '')} {about}"
    if t is ActionType.REQUEST_HELP:
        return f"Ask {world.name(a.target_id or '')} to {_request_phrase(world, requested_action(a))}"
    if t in (ActionType.BLOCK_ROUTE, ActionType.CLEAR_ROUTE, ActionType.DETECT_TRAPS):
        verb = {ActionType.BLOCK_ROUTE: "Block", ActionType.CLEAR_ROUTE: "Clear",
                ActionType.DETECT_TRAPS: "Detect traps on"}[t]
        return f"{verb} the {world.routes[a.route_id or ''].name}"
    return RULES[t].verb[0].upper() + RULES[t].verb[1:]


_LOCATION_ACTIONS = {
    BRIDGE: [ActionType.REPAIR_BRIDGE],
    TEMPLE: [ActionType.REPAIR_MECHANISM, ActionType.DECODE_SYMBOLS, ActionType.PULL_LEVER],
    LIGHTHOUSE: [ActionType.REPAIR_LIGHTHOUSE, ActionType.INSTALL_CRYSTAL, ActionType.ACTIVATE_LIGHTHOUSE],
}


def available_actions(world: WorldState, actor: str) -> list[ActionOption]:
    """Actions relevant to the actor's situation. Unavailable ones carry the reason (for greyed-out UI)."""
    state = world.characters[actor]
    if state.busy or state.location_id is None:
        return []
    here = state.location_id
    P = lambda t, **kw: ProposedAction(actor=actor, type=t, **kw)  # noqa: E731
    candidates: list[ProposedAction] = [P(ActionType.INSPECT), P(ActionType.WAIT, seconds=10)]
    if ob.discover_route_check(world, P(ActionType.DISCOVER_ROUTE)) is None:
        candidates.append(P(ActionType.DISCOVER_ROUTE))
    for route in sorted(world.routes_from(here), key=lambda r: r.id):
        if route.hidden:
            continue
        candidates.append(P(ActionType.MOVE, destination=route.other_end(here), route_id=route.id))
        if route.obstructed:
            candidates.append(P(ActionType.CLEAR_ROUTE, route_id=route.id))
        elif route.blockable:
            candidates.append(P(ActionType.BLOCK_ROUTE, route_id=route.id))
        if route.hazard is not None:  # offered whether or not traps are live, so the menu leaks nothing
            candidates.append(P(ActionType.DETECT_TRAPS, route_id=route.id))
    others = [c for c in world.characters_at(here) if c != actor]
    requests: list[ProposedAction] = []
    for other in others:
        candidates.append(P(ActionType.TALK, target_id=other))
        candidates += [P(ActionType.ASK, target_id=other, topic="plan"), P(ActionType.ASK, target_id=other, topic="news")]
        R = lambda t, **kw: P(ActionType.REQUEST_HELP, target_id=other, request=t, **kw)  # noqa: E731
        requests += [R(ActionType.GIVE, object_id=o.id) for o in world.inventory(other)]
        requests += [R(t) for t in _LOCATION_ACTIONS.get(here, [])]
        requests += [R(ActionType.DISCOVER_ROUTE)]
        requests += [R(ActionType.CLEAR_ROUTE, route_id=r.id) for r in world.routes_from(here) if r.obstructed]
        requests += [R(ActionType.DETECT_TRAPS, route_id=r.id) for r in world.routes_from(here)
                     if r.hazard is not None and not r.hidden]
        requests += [R(ActionType.MOVE, destination=d) for d in (TEMPLE, LIGHTHOUSE) if d != here]
    if _signal_check(world, P(ActionType.SIGNAL)) is None:
        candidates.append(P(ActionType.SIGNAL))
    for obj in world.objects_at(here):
        if obj.portable:
            candidates.append(P(ActionType.PICK_UP, object_id=obj.id))
    for obj in world.inventory(actor):
        candidates.append(P(ActionType.DROP, object_id=obj.id))
        for other in others:
            candidates.append(P(ActionType.GIVE, object_id=obj.id, target_id=other))
    candidates += [P(t) for t in _LOCATION_ACTIONS.get(here, [])]

    # Help requests are only listed when the helper could actually do them.
    candidates += [r for r in requests if check_action(world, r) is None]

    options = []
    for action in candidates:
        reason = check_action(world, action)
        options.append(ActionOption(
            action=action, label=_label(world, action), available=reason is None, reason=reason,
            seconds=action_seconds(world, action) if reason is None else 0,
        ))
    return options
