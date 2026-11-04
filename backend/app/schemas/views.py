"""Read models returned by the API.

The view shows what a player is allowed to see: hidden routes stay hidden until discovered,
and live traps are only shown once someone has found them. Agent plans are shown because the
UI displays each character's current goal.
"""

from datetime import datetime

from pydantic import BaseModel

from app.agents import storyteller
from app.engine.movement import travel_progress
from app.engine.rules import RULES, ActionOption, available_actions
from app.models.enums import ActionType, EventKind, GameMode, RunStatus
from app.models.events import WorldEvent
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


def character_views(world: WorldState) -> list[CharacterView]:
    player = world.story.player_character
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
            replans=mind.replans, adaptations=mind.adaptations,
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
