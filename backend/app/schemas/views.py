"""Read models returned by the API.

The view shows what a player is allowed to see: hidden routes stay hidden until discovered,
and live traps are only shown once someone has found them. Agent plans are shown because the
UI displays each character's current goal.
"""

from datetime import datetime

from pydantic import BaseModel

from app.agents import storyteller
from app.engine.aether import OBJECTS
from app.engine.movement import travel_progress
from app.engine.rules import RULES, ActionOption, available_actions
from app.models.enums import ActionType, EventKind, GameMode, RouteStatus, RunStatus
from app.models.events import WorldEvent
from app.models.mind import Memory
from app.models.obstacles import FloodState, LighthouseState, TempleLock
from app.models.story import AIStats, Assessment, EndingResult, Objective, StoryBeat
from app.models.world import WorldState


class RunInfo(BaseModel):
    id: str
    mode: GameMode
    status: RunStatus
    player_character: str | None
    ai_mode: str  # "mock" or "live"
    paused: bool
    sim_speed: float


class ClockView(BaseModel):
    now: int
    deadline: int | None
    remaining: int | None
    tick_seconds: int


class LocationView(BaseModel):
    id: str
    name: str
    description: str
    x: float
    y: float


class RouteView(BaseModel):
    id: str
    name: str
    a: str
    b: str
    base_seconds: int
    status: str
    obstructed: bool
    blocked_by: str | None
    requires_ability: str | None
    hazard: str | None        # only once someone has found the hazard
    hazard_active: bool


class TravelView(BaseModel):
    route_id: str
    from_location: str
    to_location: str
    depart_at: int
    arrive_at: int
    progress: float


class ActivityView(BaseModel):
    type: ActionType
    label: str
    started_at: int
    completes_at: int


class PlanView(BaseModel):
    goal: str
    summary: str
    strategy: str
    status: str


class BeliefFactView(BaseModel):
    """One thing a character believes, next to what is actually true (only facts the player can see anyway)."""

    kind: str  # route | item | teammate | temple | lighthouse | flood
    subject: str
    believed: str
    actual: str
    up_to_date: bool
    as_of: int | None = None            # when the character last learned this
    route_id: str | None = None
    believed_location: str | None = None  # items and teammates: where the character thinks they are
    actual_location: str | None = None


class MemoryView(BaseModel):
    time: int
    text: str
    source: str  # saw | did | told | signal | briefing | summary
    from_id: str | None = None
    importance: int


class OptionView(BaseModel):
    strategy: str
    summary: str
    chosen: bool


class ThinkingView(BaseModel):
    since: int
    chosen: str
    chosen_by: str  # rules | ai | lesson | player
    trigger: str | None
    thought: str | None
    options: list[OptionView]


class MindLessonView(BaseModel):
    id: int
    text: str
    status: str  # kept | trying
    used: bool


class MindView(BaseModel):
    """Inside a character's head: why it chose its plan and how its picture of the island differs from reality."""

    thinking: ThinkingView | None
    beliefs: list[BeliefFactView]
    outdated: int  # world facts (not teammate sightings) that are out of date
    memories: list[MemoryView]
    lessons: list[MindLessonView]


class CharacterView(BaseModel):
    id: str
    name: str
    title: str
    color: str
    personality: str
    primary_goal: str
    abilities: list[str]
    restrictions: list[str]
    autonomous: bool
    location_id: str | None
    travel: TravelView | None
    activity: ActivityView | None
    inventory: list[str]
    plan: PlanView | None
    trust: dict[str, int]
    orders: list[str]  # player instructions still to carry out, in order
    replans: int
    adaptations: int
    mind: MindView


class ObjectView(BaseModel):
    id: str
    name: str
    kind: str
    location_id: str | None
    carried_by: str | None


class ChapterView(BaseModel):
    id: int
    time: int
    title: str
    text: str
    kind: str
    generated_by: str


class TwistsView(BaseModel):
    used: int
    max: int
    ready_at: int | None    # simulated time when the next twist is allowed (None = now)
    examples: list[str]     # a few twists that are possible right now, to inspire the player


class StoryView(BaseModel):
    beats: list[StoryBeat]
    objectives: list[Objective]
    assessment: Assessment
    ending: EndingResult | None
    ai: AIStats
    chapters: list[ChapterView]
    twists: TwistsView


class StateView(BaseModel):
    run: RunInfo
    clock: ClockView
    locations: list[LocationView]
    routes: list[RouteView]
    characters: list[CharacterView]
    objects: list[ObjectView]
    temple_lock: TempleLock
    lighthouse: LighthouseState
    flood: FloodState
    story: StoryView
    last_event_seq: int
    available_actions: list[ActionOption]


class CreatedRun(BaseModel):
    run_id: str
    token: str  # shown once; required as the X-Run-Token header for this run
    state: StateView


class RunSummary(BaseModel):
    id: str
    mode: str
    player_character: str | None
    status: str
    ending: str | None
    sim_time: int
    created_at: datetime
    updated_at: datetime


class EventsView(BaseModel):
    events: list[WorldEvent]
    last_event_seq: int


# --- builders -----------------------------------------------------------------------------------------

def _hazard_known(world: WorldState, route_id: str) -> bool:
    return any(
        e.data.get("route_id") == route_id
        for e in world.events
        if e.kind in (EventKind.ROUTE_DISCOVERED, EventKind.TRAP_SPRUNG, EventKind.TRAPS_MARKED)
    )


def _twists(world: WorldState) -> TwistsView:
    story = world.story
    ready = (story.last_twist_at + storyteller.TWIST_COOLDOWN_SECONDS) if story.last_twist_at is not None else None
    examples: list[str] = []
    if world.mode is GameMode.GAME and story.status is RunStatus.RUNNING:
        seen: set[str] = set()
        for o in storyteller.options(world):  # one example per kind keeps the hints varied
            if o.kind not in seen:
                seen.add(o.kind)
                examples.append(o.summary.split(" (")[0].rstrip(".") + ".")
    return TwistsView(used=story.twists_used, max=storyteller.MAX_TWISTS,
                      ready_at=ready if ready is not None and ready > world.clock.now else None, examples=examples)


OBJECT_NAMES = {o.id: o.name for o in OBJECTS}
MIND_MEMORIES = 8


def _route_state(status: RouteStatus, obstructed: bool, traps: bool) -> str:
    return ("blocked" if obstructed else status.value) + (", traps live" if traps else "")


def _place(world: WorldState, location_id: str | None) -> str:
    return world.locations[location_id].name if location_id in world.locations else "somewhere unknown"


def _flags(state: BaseModel, labels: dict[str, str], none: str) -> str:
    done = [label for key, label in labels.items() if getattr(state, key)]
    return ", ".join(done) or none


TEMPLE_LABELS = {"mechanism_repaired": "mechanism repaired", "symbols_decoded": "symbols decoded", "gate_open": "gate open"}
LIGHTHOUSE_LABELS = {"operational": "repaired", "crystal_installed": "crystal installed", "activated": "lit"}


def _flood_text(flood: FloodState) -> str:
    if flood.flooded:
        return "flooded"
    return f"floods at {flood.floods_at}s" if flood.floods_at is not None else "not flooding yet"


def _memory_view(m: Memory) -> MemoryView:
    kind, _, who = m.source.partition(":")
    source = {"observed": "saw", "self": "did"}.get(kind, kind)
    return MemoryView(time=m.time, text=m.description, source=source, from_id=who or None, importance=m.importance)


def mind_view(world: WorldState, cid: str, known_hazards: set[str]) -> MindView:
    """Compare a character's beliefs with the truth, for facts the state view already shows the player."""
    mind, b = world.minds[cid], world.minds[cid].beliefs
    facts: list[BeliefFactView] = []

    for rid, route in sorted(world.routes.items(), key=lambda kv: kv[1].name):
        if route.hidden:
            continue  # nobody has found it, so it is not on the player's map either
        rb = b.routes[rid]
        actual_traps = route.hazard_active if rid in known_hazards else rb.hazard_active  # never leak live traps
        actual = _route_state(route.status, route.obstructed, actual_traps)
        believed = _route_state(rb.status, rb.obstructed, rb.hazard_active) if rb.known else "doesn't know it exists"
        facts.append(BeliefFactView(kind="route", subject=route.name, believed=believed, actual=actual,
                                    up_to_date=rb.known and believed == actual, as_of=rb.as_of if rb.known else None,
                                    route_id=rid))

    def where(location_id: str | None, carried_by: str | None) -> str:
        if carried_by:
            return f"carried by {world.name(carried_by)}"
        return f"at the {_place(world, location_id)}" if location_id else "whereabouts unknown"

    for oid in sorted(set(b.objects) | set(world.objects), key=lambda o: OBJECT_NAMES.get(o, o)):
        ob, obj = b.objects.get(oid), world.objects.get(oid)
        believed = where(ob.location_id, ob.carried_by) if ob else "whereabouts unknown"
        if obj is not None:
            actual, actual_loc = where(obj.location_id, obj.carried_by), obj.location_id
        else:
            actual, actual_loc = ("in the lighthouse" if world.lighthouse.crystal_installed and oid == "sun_crystal"
                                  else "used up"), None
        facts.append(BeliefFactView(kind="item", subject=OBJECT_NAMES.get(oid, oid), believed=believed, actual=actual,
                                    up_to_date=believed == actual or (obj is None and believed == "whereabouts unknown"),
                                    as_of=ob.as_of if ob else None,
                                    believed_location=ob.location_id if ob else None, actual_location=actual_loc))

    for label, believed_state, actual_state, as_of, labels, none in (
        ("Temple lock", b.temple, world.temple_lock, b.temple_as_of, TEMPLE_LABELS, "untouched"),
        ("Lighthouse", b.lighthouse, world.lighthouse, b.lighthouse_as_of, LIGHTHOUSE_LABELS, "broken"),
    ):
        believed, actual = _flags(believed_state, labels, none), _flags(actual_state, labels, none)
        facts.append(BeliefFactView(kind="temple" if label == "Temple lock" else "lighthouse", subject=label,
                                    believed=believed, actual=actual, up_to_date=believed == actual, as_of=as_of))
    believed, actual = _flood_text(b.flood), _flood_text(world.flood)
    facts.append(BeliefFactView(kind="flood", subject="Flooded Chamber", believed=believed, actual=actual,
                                up_to_date=believed == actual, as_of=b.flood_as_of))

    for other in sorted(world.characters):
        if other == cid:
            continue
        cb, s = b.characters.get(other), world.characters[other]
        believed = f"last seen at the {_place(world, cb.location_id)}" if cb and cb.location_id else "not seen yet"
        actual = f"on the way to the {_place(world, s.travel.to_location)}" if s.travel else f"at the {_place(world, s.location_id)}"
        same = cb is not None and s.travel is None and cb.location_id == s.location_id
        facts.append(BeliefFactView(kind="teammate", subject=world.name(other), believed=believed, actual=actual,
                                    up_to_date=same, as_of=cb.as_of if cb else None,
                                    believed_location=cb.location_id if cb else None,
                                    actual_location=None if s.travel else s.location_id))

    thinking = None
    if (t := mind.trace) is not None:
        thinking = ThinkingView(since=t.since, chosen=t.chosen, chosen_by=t.chosen_by, trigger=t.trigger, thought=t.thought,
                                options=[OptionView(strategy=o.strategy, summary=o.summary, chosen=o.strategy == t.chosen)
                                         for o in t.options])
    memories = [m for m in mind.memories if m.source != "summary" and m.importance >= 2][-MIND_MEMORIES:]
    return MindView(
        thinking=thinking, beliefs=facts,
        outdated=sum(1 for f in facts if not f.up_to_date and f.kind != "teammate"),
        memories=[_memory_view(m) for m in reversed(memories)],
        lessons=[MindLessonView(id=le.id, text=le.text, status=le.status, used=le.id in mind.lessons_used)
                 for le in mind.lessons],
    )


def character_views(world: WorldState) -> list[CharacterView]:
    player = world.story.player_character
    known_hazards = {r.id for r in world.routes.values() if r.hazard is not None and _hazard_known(world, r.id)}
    out = []
    for cid in sorted(world.characters):
        p, s, mind = world.profiles[cid], world.characters[cid], world.minds[cid]
        travel = None
        if s.travel is not None:
            travel = TravelView(**s.travel.model_dump(exclude={"hazard_penalty"}),
                                progress=travel_progress(world, cid) or 0.0)
        activity = None
        if s.activity is not None:
            t = s.activity.action.type
            activity = ActivityView(type=t, label=RULES[t].verb, started_at=s.activity.started_at,
                                    completes_at=s.activity.completes_at)
        plan = None
        if mind.plan is not None:
            plan = PlanView(goal=mind.plan.goal, summary=mind.plan.summary, strategy=mind.plan.strategy,
                            status=mind.plan.status)
        out.append(CharacterView(
            id=cid, name=p.name, title=p.title, color=p.color, personality=p.personality,
            primary_goal=p.primary_goal, abilities=[a.value for a in p.abilities], restrictions=p.restrictions,
            autonomous=cid != player, location_id=s.location_id, travel=travel, activity=activity,
            inventory=[o.id for o in world.inventory(cid)], plan=plan, trust=dict(mind.trust),
            orders=[o.summary for o in mind.orders],
            replans=mind.replans, adaptations=mind.adaptations, mind=mind_view(world, cid, known_hazards),
        ))
    return out


def state_view(world: WorldState, *, ai_mode: str, paused: bool, sim_speed: float) -> StateView:
    story = world.story
    routes = []
    for r in world.routes.values():
        if r.hidden:
            continue
        known = r.hazard is not None and _hazard_known(world, r.id)
        routes.append(RouteView(
            id=r.id, name=r.name, a=r.a, b=r.b, base_seconds=r.base_seconds, status=r.status.value,
            obstructed=r.obstructed, blocked_by=r.blocked_by,
            requires_ability=r.requires_ability.value if r.requires_ability else None,
            hazard=r.hazard if known else None, hazard_active=r.hazard_active and known,
        ))
    player = story.player_character
    actions = (available_actions(world, player)
               if player is not None and story.status is RunStatus.RUNNING else [])
    return StateView(
        run=RunInfo(id=world.run_id, mode=world.mode, status=story.status, player_character=player,
                    ai_mode=ai_mode, paused=paused, sim_speed=sim_speed),
        clock=ClockView(now=world.clock.now, deadline=world.clock.deadline, remaining=world.clock.remaining,
                        tick_seconds=world.clock.tick_seconds),
        locations=[LocationView(**loc.model_dump()) for loc in world.locations.values()],
        routes=routes,
        characters=character_views(world),
        objects=[ObjectView(id=o.id, name=o.name, kind=o.kind, location_id=o.location_id, carried_by=o.carried_by)
                 for o in world.objects.values()],
        temple_lock=world.temple_lock, lighthouse=world.lighthouse, flood=world.flood,
        story=StoryView(beats=story.beats, objectives=story.objectives, assessment=story.assessment,
                        ending=story.ending, ai=story.ai,
                        chapters=[ChapterView(**c.model_dump(exclude={"facts"})) for c in story.chapters],
                        twists=_twists(world)),
        last_event_seq=world.next_event_seq - 1,
        available_actions=actions,
    )
