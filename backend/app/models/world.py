"""Typed world model. WorldState is the single source of truth for a run.

Inventories are not stored on characters: an object's holder lives only on the object
(``location_id`` or ``carried_by``), so an item can never be owned twice.
"""

from typing import Any

from pydantic import BaseModel, Field, model_validator

from app.models.actions import ProposedAction
from app.models.enums import Ability, EventKind, GameMode, RouteStatus
from app.models.events import WorldEvent
from app.models.mind import Mind
from app.models.obstacles import FloodState, LighthouseState, TempleLock
from app.models.story import StoryState


class Location(BaseModel):
    id: str
    name: str
    description: str
    # Map coordinates on a 1000 x 700 canvas, used by the renderer.
    x: float
    y: float


class Route(BaseModel):
    id: str
    name: str
    a: str
    b: str
    base_seconds: int = Field(gt=0)
    status: RouteStatus = RouteStatus.OPEN
    requires_ability: Ability | None = None
    # A hidden route physically exists but nobody can use it until it is discovered.
    hidden: bool = False
    # Obstruction is separate from status: a broken bridge can also be blocked with debris.
    blockable: bool = True
    obstructed: bool = False
    blocked_by: str | None = None
    # Optional hazard that slows down anyone who crosses without the bypass ability.
    hazard: str | None = None
    hazard_active: bool = False
    hazard_bypass: Ability | None = None
    hazard_penalty_seconds: int = Field(default=0, ge=0)

    def connects(self, location_id: str) -> bool:
        return location_id in (self.a, self.b)

    def other_end(self, location_id: str) -> str:
        if location_id == self.a:
            return self.b
        if location_id == self.b:
            return self.a
        raise ValueError(f"route {self.id} does not touch {location_id}")


class WorldObject(BaseModel):
    id: str
    kind: str
    name: str
    description: str = ""
    portable: bool = True
    heavy: bool = False
    location_id: str | None = None
    carried_by: str | None = None

    @model_validator(mode="after")
    def _exactly_one_holder(self) -> "WorldObject":
        if (self.location_id is None) == (self.carried_by is None):
            raise ValueError(f"object {self.id} must have exactly one of location_id / carried_by")
        return self


class CharacterProfile(BaseModel):
    """Static description of a character. Abilities here are enforced by the engine."""

    id: str
    name: str
    title: str
    personality: str
    primary_goal: str
    secondary_goals: list[str] = []
    abilities: list[Ability]
    restrictions: list[str] = []
    # > 1 is faster: travel time = ceil(route.base_seconds / speed_multiplier)
    speed_multiplier: float = Field(gt=0)
    carry_capacity: int = Field(ge=1)
    can_carry_heavy: bool = True
    color: str = "#ffffff"

    def has(self, ability: Ability) -> bool:
        return ability in self.abilities


class Travel(BaseModel):
    route_id: str
    from_location: str
    to_location: str
    depart_at: int
    arrive_at: int
    hazard_penalty: int = 0


class Activity(BaseModel):
    """A timed action in progress. Deferred actions take effect when the activity completes."""

    action: ProposedAction
    started_at: int
    completes_at: int
    deferred: bool


class CharacterState(BaseModel):
    """Dynamic, per-run state of a character. Exactly one of location_id / travel is set."""

    id: str
    location_id: str | None = None
    travel: Travel | None = None
    activity: Activity | None = None

    @model_validator(mode="after")
    def _at_location_or_travelling(self) -> "CharacterState":
        if (self.location_id is None) == (self.travel is None):
            raise ValueError(f"character {self.id} must be either at a location or travelling")
        if self.travel is not None and self.activity is not None:
            raise ValueError(f"character {self.id} cannot act while travelling")
        return self

    @property
    def busy(self) -> bool:
        return self.travel is not None or self.activity is not None


class ScheduledEffect(BaseModel):
    """A world change due at a fixed simulated time (e.g. the chamber flooding)."""

    time: int
    kind: str
    data: dict[str, Any] = {}


class SimulationClock(BaseModel):
    now: int = Field(default=0, ge=0)  # simulated seconds since the run started
    tick_seconds: int = Field(gt=0)
    deadline: int | None = None

    @property
    def expired(self) -> bool:
        return self.deadline is not None and self.now >= self.deadline

    @property
    def remaining(self) -> int | None:
        return None if self.deadline is None else max(0, self.deadline - self.now)


class WorldState(BaseModel):
    run_id: str
    mode: GameMode
    clock: SimulationClock
    locations: dict[str, Location]
    routes: dict[str, Route]
    objects: dict[str, WorldObject]
    profiles: dict[str, CharacterProfile]
    characters: dict[str, CharacterState]
    temple_lock: TempleLock = Field(default_factory=TempleLock)
    lighthouse: LighthouseState = Field(default_factory=LighthouseState)
    flood: FloodState = Field(default_factory=FloodState)
    scheduled: list[ScheduledEffect] = []
    minds: dict[str, Mind] = {}
    story: StoryState = Field(default_factory=StoryState)
    events: list[WorldEvent] = []
    next_event_seq: int = 1

    def record(
        self,
        kind: EventKind,
        description: str,
        *,
        time: int | None = None,
        actor: str | None = None,
        location_id: str | None = None,
        **data: Any,
    ) -> WorldEvent:
        event = WorldEvent(
            seq=self.next_event_seq,
            time=self.clock.now if time is None else time,
            kind=kind,
            description=description,
            actor=actor,
            location_id=location_id,
            data=data,
        )
        self.next_event_seq += 1
        self.events.append(event)
        return event

    def name(self, character_id: str) -> str:
        return self.profiles[character_id].name

    def inventory(self, character_id: str) -> list[WorldObject]:
        return [o for o in self.objects.values() if o.carried_by == character_id]

    def carries(self, character_id: str, object_id: str) -> bool:
        obj = self.objects.get(object_id)
        return obj is not None and obj.carried_by == character_id

    def objects_at(self, location_id: str) -> list[WorldObject]:
        return [o for o in self.objects.values() if o.location_id == location_id]

    def routes_from(self, location_id: str) -> list[Route]:
        return [r for r in self.routes.values() if r.connects(location_id)]

    def characters_at(self, location_id: str) -> list[str]:
        return [cid for cid, s in self.characters.items() if s.location_id == location_id]
