"""Limited knowledge: what each character perceives, remembers and learns from others.

Characters learn facts in exactly four ways:
- the mission briefing at the start (common knowledge);
- seeing things at their own location (``perceive``) and witnessing events there (``observe``);
- talking in person (TALK exchanges beliefs both ways);
- Meera's horn signal (SIGNAL broadcasts her route knowledge to every teammate).
Nothing else updates a mind, so an agent that was not told cannot react.
"""

from app.engine.ids import CHAMBER, LIGHTHOUSE, TEMPLE
from app.models.enums import EventKind, RouteStatus
from app.models.events import WorldEvent
from app.models.mind import Beliefs, CharacterBelief, Memory, Mind, ObjectBelief, RouteBelief
from app.models.world import WorldState

MAX_MEMORIES = 60
KEEP_RECENT = 20

IMPORTANCE: dict[EventKind, int] = {
    EventKind.TRAVEL_STARTED: 1,
    EventKind.ARRIVED: 1,
    EventKind.WAITED: 1,
    EventKind.INSPECTED: 2,
    EventKind.SEARCHED: 2,
    EventKind.ITEM_PICKED_UP: 2,
    EventKind.ITEM_DROPPED: 2,
    EventKind.ITEM_GIVEN: 3,
    EventKind.TALKED: 2,
    EventKind.SIGNALLED: 3,
    EventKind.ACTION_STARTED: 2,
    EventKind.TRAP_SPRUNG: 4,
    EventKind.ACTION_FAILED: 4,
    EventKind.ROUTE_DISCOVERED: 4,
    EventKind.TRAPS_MARKED: 3,
    EventKind.BRIDGE_REPAIRED: 4,
    EventKind.ROUTE_BLOCKED: 5,
    EventKind.ROUTE_CLEARED: 4,
    EventKind.MECHANISM_REPAIRED: 4,
    EventKind.SYMBOLS_DECODED: 4,
    EventKind.GATE_OPENED: 5,
    EventKind.FLOOD_WARNING: 4,
    EventKind.CHAMBER_FLOODED: 5,
    EventKind.LIGHTHOUSE_REPAIRED: 4,
    EventKind.CRYSTAL_INSTALLED: 5,
    EventKind.LIGHTHOUSE_ACTIVATED: 5,
    EventKind.RADIO_MESSAGE: 3,
    EventKind.STORY_TWIST: 5,
}

# Events seen by everyone on the island, wherever they are.
GLOBAL_EVENTS = {EventKind.LIGHTHOUSE_ACTIVATED, EventKind.SIGNALLED}
# Locations that can see what happens at another location.
VISIBLE_FROM = {CHAMBER: [TEMPLE]}

BRIEFING = (
    "Briefing: the storm has damaged the Main Bridge. The temple gate is sealed by an old gear-and-symbol "
    "lock. The Sun Crystal lies in the Flooded Chamber beyond it. The lighthouse mechanism must be repaired "
    "before the crystal can be lit."
)


# --- setup ------------------------------------------------------------------------------------

def briefing_beliefs(world: WorldState) -> Beliefs:
    """Common knowledge at the start: the public map, item locations and obstacle states."""
    return Beliefs(
        routes={
            r.id: RouteBelief(known=not r.hidden, status=r.status if not r.hidden else RouteStatus.OPEN,
                              obstructed=r.obstructed, hazard_active=False)
            for r in world.routes.values()
        },
        objects={o.id: ObjectBelief(location_id=o.location_id, carried_by=o.carried_by) for o in world.objects.values()},
        characters={cid: CharacterBelief(location_id=s.location_id) for cid, s in world.characters.items()},
        temple=world.temple_lock.model_copy(),
        lighthouse=world.lighthouse.model_copy(),
        flood=world.flood.model_copy(),
    )


def init_minds(world: WorldState) -> None:
    for cid in world.characters:
        world.minds[cid] = Mind(
            beliefs=briefing_beliefs(world),
            memories=[Memory(time=0, description=BRIEFING, source="briefing", importance=3)],
            trust={other: 1 for other in world.characters if other != cid},
        )


# --- relationships ------------------------------------------------------------------------------

TRUST_MIN, TRUST_MAX = -5, 5
# Witnessing these changes how much the observer trusts the actor.
TRUST_EFFECT: dict[EventKind, int] = {
    EventKind.ROUTE_BLOCKED: -2,
    EventKind.ROUTE_CLEARED: 1,
    EventKind.BRIDGE_REPAIRED: 1,
    EventKind.TRAPS_MARKED: 1,
}


def adjust_trust(world: WorldState, cid: str, towards: str, delta: int) -> None:
    trust = world.minds[cid].trust
    if towards in trust:
        trust[towards] = max(TRUST_MIN, min(TRUST_MAX, trust[towards] + delta))


def _update_trust(world: WorldState, observer: str, event: WorldEvent) -> None:
    if not event.actor or event.actor == observer:
        return
    if event.kind is EventKind.ITEM_GIVEN and event.data.get("receiver") == observer:
        adjust_trust(world, observer, event.actor, 1)
    elif delta := TRUST_EFFECT.get(event.kind):
        adjust_trust(world, observer, event.actor, delta)


# --- memory -----------------------------------------------------------------------------------

def remember(
    world: WorldState, cid: str, description: str, *, source: str, importance: int,
    related: list[str] | None = None, confidence: float = 1.0, event_seq: int | None = None,
    kind: str | None = None,
) -> Memory:
    mind = world.minds[cid]
    memory = Memory(time=world.clock.now, description=description, source=source, importance=importance,
                    related=related or [], confidence=confidence, event_seq=event_seq, kind=kind)
    mind.memories.append(memory)
    if len(mind.memories) > MAX_MEMORIES:
        compact(mind)
    return memory


def compact(mind: Mind) -> None:
    """Fold old routine memories (importance <= 2) into one summary to bound prompt size."""
    cutoff = len(mind.memories) - KEEP_RECENT
    old, recent = mind.memories[:cutoff], mind.memories[cutoff:]
    routine = [m for m in old if m.importance <= 2]
    if not routine:
        return
    kept = [m for m in old if m.importance > 2]
    summary = Memory(
        time=routine[-1].time, source="summary", importance=2,
        description=f"Earlier: {len(routine)} routine moments (travel, waiting, items) between "
                    f"t={routine[0].time}s and t={routine[-1].time}s.",
    )
    mind.memories = [*kept, summary, *recent]
    mind.memory_cursor = max(0, mind.memory_cursor - (len(old) - len(kept) - 1))


def _already_noted(mind: Mind, entity: str, since: int) -> bool:
    return any(entity in m.related and m.time >= since for m in mind.memories)


# --- perception --------------------------------------------------------------------------------

def route_fact(world: WorldState, route_id: str, rb: RouteBelief) -> str:
    name = world.routes[route_id].name
    if not rb.known:
        return f"{name} is unknown"
    state = "blocked" if rb.obstructed else rb.status.value
    return f"{name} is {state}" + (" and trapped" if rb.hazard_active else "")


def perceive(world: WorldState, cid: str) -> None:
    """Update a character's beliefs from what is visible at their current location."""
    state = world.characters[cid]
    here = state.location_id
    if here is None:
        return
    mind = world.minds[cid]
    b = mind.beliefs
    now = world.clock.now
    name = world.name(cid)

    for route in world.routes_from(here):
        if route.hidden:
            continue
        rb = b.routes[route.id]
        hazard = rb.hazard_active and route.hazard_active  # marked traps are visible; live ones are not
        changed = (not rb.known) or rb.status is not route.status or rb.obstructed != route.obstructed
        prev_as_of = rb.as_of
        b.routes[route.id] = RouteBelief(known=True, status=route.status, obstructed=route.obstructed,
                                         hazard_active=hazard, as_of=now)
        if changed and not _already_noted(mind, route.id, prev_as_of + 1):
            remember(world, cid, f"{name} sees that the {route_fact(world, route.id, b.routes[route.id])}.",
                     source="observed", importance=4, related=[route.id])

    for oid, ob in list(b.objects.items()):
        if ob.location_id == here and (oid not in world.objects or world.objects[oid].location_id != here):
            b.objects[oid] = ObjectBelief(as_of=now)  # gone from here; whereabouts unknown
    for obj in world.objects.values():
        holder = obj.carried_by
        if obj.location_id == here or (holder is not None and world.characters[holder].location_id == here):
            b.objects[obj.id] = ObjectBelief(location_id=obj.location_id, carried_by=holder, as_of=now)

    for other in world.characters_at(here):
        b.characters[other] = CharacterBelief(location_id=here, as_of=now)

    if here in (TEMPLE, CHAMBER):
        if b.temple != world.temple_lock:
            b.temple, b.temple_as_of = world.temple_lock.model_copy(), now
        if b.flood != world.flood:
            b.flood, b.flood_as_of = world.flood.model_copy(), now
    if here == LIGHTHOUSE and b.lighthouse != world.lighthouse:
        b.lighthouse, b.lighthouse_as_of = world.lighthouse.model_copy(), now


# --- events --------------------------------------------------------------------------------------

def observers(world: WorldState, event: WorldEvent) -> list[str]:
    if event.kind in GLOBAL_EVENTS:
        return sorted(world.characters)
    seen: set[str] = {event.actor} if event.actor else set()
    for key in ("target", "receiver"):
        if event.data.get(key) in world.characters:
            seen.add(event.data[key])
    if event.location_id is not None:
        for loc in [event.location_id, *VISIBLE_FROM.get(event.location_id, [])]:
            seen.update(world.characters_at(loc))
    return sorted(seen)


def observe(world: WorldState, events: list[WorldEvent]) -> None:
    """Turn freshly recorded world events into memories and belief updates for those who saw them."""
    for event in events:
        if event.kind in (EventKind.PLAN_CHANGED, EventKind.LLM_DELIBERATION):
            continue  # internal thinking, not something others can see
        for cid in observers(world, event):
            remember(world, cid, event.description, source="self" if event.actor == cid else "observed",
                     importance=IMPORTANCE.get(event.kind, 2), event_seq=event.seq, kind=event.kind.value,
                     related=[v for k, v in event.data.items() if k == "route_id"] + ([event.actor] if event.actor else []))
            _apply_event_knowledge(world, cid, event)
            _update_trust(world, cid, event)
            perceive(world, cid)
        if event.kind is EventKind.TALKED and event.actor and event.data.get("target"):
            exchange(world, event.actor, event.data["target"])
            exchange(world, event.data["target"], event.actor)
        if event.kind is EventKind.SIGNALLED and event.actor:
            broadcast(world, event.actor)
        if event.kind is EventKind.ASKED and event.actor and event.data.get("target") and event.data.get("topic") == "news":
            share_news(world, event.data["target"], event.actor)


def _apply_event_knowledge(world: WorldState, cid: str, event: WorldEvent) -> None:
    """Facts an event reveals beyond what is visible afterwards (e.g. traps, discoveries)."""
    b = world.minds[cid].beliefs
    route_id = event.data.get("route_id")
    now = world.clock.now
    if event.kind is EventKind.ROUTE_DISCOVERED and route_id:
        r = world.routes[route_id]
        b.routes[route_id] = RouteBelief(known=True, status=r.status, obstructed=r.obstructed,
                                         hazard_active=r.hazard_active, as_of=now)
    if event.kind in (EventKind.ROUTE_DISCOVERED, EventKind.SEARCHED) and event.actor == cid and event.location_id:
        if event.location_id not in b.searched:
            b.searched.append(event.location_id)
    if event.kind is EventKind.TRAP_SPRUNG and route_id:
        b.routes[route_id] = b.routes[route_id].model_copy(update={"known": True, "hazard_active": True, "as_of": now})
    if event.kind is EventKind.TRAPS_MARKED and route_id:
        b.routes[route_id] = b.routes[route_id].model_copy(update={"hazard_active": False, "as_of": now})
    if event.kind is EventKind.LIGHTHOUSE_ACTIVATED:
        b.lighthouse = world.lighthouse.model_copy()
        b.lighthouse_as_of = now


# --- communication ---------------------------------------------------------------------------------

def _merge_newer(world: WorldState, src: Beliefs, dst: Beliefs, routes_only: bool) -> list[str]:
    """Copy facts the source learned more recently than the destination. Returns readable updates."""
    learned: list[str] = []
    for rid, rb in src.routes.items():
        mine = dst.routes[rid]
        if rb.known and rb.as_of > mine.as_of:
            if (rb.known, rb.status, rb.obstructed, rb.hazard_active) != (mine.known, mine.status, mine.obstructed, mine.hazard_active):
                learned.append(route_fact(world, rid, rb))
            dst.routes[rid] = rb.model_copy()
    if routes_only:
        return learned
    for oid, ob in src.objects.items():
        if ob.as_of > dst.objects.get(oid, ObjectBelief()).as_of:
            dst.objects[oid] = ob.model_copy()
    for c, cb in src.characters.items():
        if cb.as_of > dst.characters.get(c, CharacterBelief()).as_of:
            dst.characters[c] = cb.model_copy()
    if src.temple_as_of > dst.temple_as_of:
        if src.temple != dst.temple:
            done = [k.replace("_", " ") for k, v in src.temple.model_dump().items() if v]
            learned.append(f"temple lock: {', '.join(done) or 'untouched'}")
        dst.temple, dst.temple_as_of = src.temple.model_copy(), src.temple_as_of
    if src.flood_as_of > dst.flood_as_of:
        if src.flood.floods_at and src.flood != dst.flood:
            learned.append(f"the chamber floods at t={src.flood.floods_at}s")
        dst.flood, dst.flood_as_of = src.flood.model_copy(), src.flood_as_of
    if src.lighthouse_as_of > dst.lighthouse_as_of:
        dst.lighthouse, dst.lighthouse_as_of = src.lighthouse.model_copy(), src.lighthouse_as_of
    return learned


def exchange(world: WorldState, speaker: str, listener: str) -> None:
    learned = _merge_newer(world, world.minds[speaker].beliefs, world.minds[listener].beliefs, routes_only=False)
    if learned:
        remember(world, listener, f"{world.name(speaker)} tells {world.name(listener)}: {'; '.join(learned)}.",
                 source=f"told:{speaker}", importance=4, confidence=0.9, related=[speaker])


def recent_news(world: WorldState, cid: str, limit: int = 3) -> list[Memory]:
    """The most recent important things this character witnessed or was told (not routine, not the briefing)."""
    important = [m for m in world.minds[cid].memories if m.importance >= 4 and m.source not in ("briefing", "summary")]
    return important[-limit:]


def answer(world: WorldState, target: str, topic: str) -> str:
    """What ``target`` says when asked about ``topic``. Built only from the target's own mind."""
    mind = world.minds[target]
    name = world.name(target)
    if topic == "plan":
        if mind.plan is None:
            return f"{name} hasn't settled on a plan yet."
        return f"{name}'s goal: {mind.plan.goal}. Plan: {mind.plan.summary}"
    news = recent_news(world, target)
    if not news:
        return f"{name} has nothing new to report."
    return f"{name} reports: " + " ".join(f"(t={m.time}s) {m.description}" for m in news)


def share_news(world: WorldState, teller: str, listener: str) -> None:
    """Answering 'any news?': beliefs flow from teller to listener, plus the teller's key memories."""
    _merge_newer(world, world.minds[teller].beliefs, world.minds[listener].beliefs, routes_only=False)
    known = {m.description for m in world.minds[listener].memories}
    for m in recent_news(world, teller):
        if m.description not in known:
            remember(world, listener, f"{world.name(teller)} says: {m.description}", source=f"told:{teller}",
                     importance=m.importance, related=m.related, confidence=0.9)


def broadcast(world: WorldState, sender: str) -> None:
    src = world.minds[sender]
    src.signalled = sorted({*src.signalled, *(f"{rid}:{route_fact(world, rid, rb)}" for rid, rb in src.beliefs.routes.items() if rb.known)})
    for cid in sorted(world.characters):
        if cid == sender:
            continue
        learned = _merge_newer(world, src.beliefs, world.minds[cid].beliefs, routes_only=True)
        if learned:
            remember(world, cid, f"{world.name(sender)}'s horn signal: {'; '.join(learned)}.",
                     source=f"signal:{sender}", importance=4, confidence=0.9, related=[sender])
