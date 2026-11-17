"""A character's private mind: beliefs, memories and current plan.

Agents plan only from their Beliefs, never from the true WorldState, so a character who has
not seen or been told about a change keeps acting on what it last knew.
"""

from typing import Literal

from pydantic import BaseModel, Field

from app.models.actions import ProposedAction
from app.models.enums import RouteStatus
from app.models.obstacles import FloodState, LighthouseState, TempleLock


class RouteBelief(BaseModel):
    known: bool  # False for hidden routes the character has not learned about
    status: RouteStatus = RouteStatus.OPEN
    obstructed: bool = False
    hazard_active: bool = False
    as_of: int = 0


class ObjectBelief(BaseModel):
    """Where the character thinks an object is. Both None means 'unknown'."""

    location_id: str | None = None
    carried_by: str | None = None
    as_of: int = 0


class CharacterBelief(BaseModel):
    location_id: str | None = None  # last seen location
    as_of: int = 0


class Beliefs(BaseModel):
    routes: dict[str, RouteBelief] = {}
    objects: dict[str, ObjectBelief] = {}
    characters: dict[str, CharacterBelief] = {}
    temple: TempleLock = Field(default_factory=TempleLock)
    temple_as_of: int = 0
    lighthouse: LighthouseState = Field(default_factory=LighthouseState)
    lighthouse_as_of: int = 0
    flood: FloodState = Field(default_factory=FloodState)
    flood_as_of: int = 0
    searched: list[str] = []  # locations already searched for hidden paths


class Memory(BaseModel):
    time: int
    description: str
    source: str  # "observed", "briefing", "told:<id>", "signal:<id>", "self", "summary"
    importance: int = Field(ge=1, le=5)
    related: list[str] = []
    confidence: float = Field(default=1.0, ge=0, le=1)
    event_seq: int | None = None
    kind: str | None = None  # EventKind of the event this memory came from, if any


class Plan(BaseModel):
    strategy: str     # machine-readable, e.g. "repair_bridge", "route_via_forest"
    goal: str         # what the character is trying to achieve right now
    summary: str      # one-line human description shown in the UI and log
    created_at: int
    status: str = "pursuing"  # pursuing | waiting | blocked | failed
    trigger: str | None = None


class HelpRequest(BaseModel):
    from_id: str
    action: "ProposedAction"  # the action the helper agreed to take (actor = helper)
    made_at: int
    expires_at: int


class Order(BaseModel):
    """One step of a player command, already validated against the game's vocabulary."""

    kind: Literal["go_to", "action", "wait"]
    location: str | None = None          # go_to
    action: ProposedAction | None = None  # action / wait (actor = the character who carries it out)
    summary: str                          # e.g. "repair the Main Bridge"
    from_id: str
    given_at: int
    started_at: int | None = None  # set when the action itself begins; it is done once the character is idle again


class OptionTrace(BaseModel):
    strategy: str
    summary: str
    status: str = "pursuing"


class DecisionTrace(BaseModel):
    """Why the character does what it does: the options its rules offered and who picked one (Mind View)."""

    since: int  # when this choice was first made
    options: list[OptionTrace] = []
    chosen: str
    chosen_by: Literal["rules", "ai", "lesson", "player"] = "rules"
    trigger: str | None = None  # the news that prompted this choice, if any
    thought: str | None = None  # the AI's one-line reason, or the lesson that was applied


class WaitEpisode(BaseModel):
    """A stretch of time the character spent waiting or blocked, and what else it could have done."""

    strategy: str
    summary: str
    location_id: str | None = None
    started_at: int
    ended_at: int | None = None
    alternatives: list[OptionTrace] = []


class ActiveLesson(BaseModel):
    """A lesson from an earlier game: where the rules would pick ``instead_of``, pick ``prefer`` (if it is an option)."""

    id: int
    instead_of: str
    prefer: str
    text: str
    status: Literal["kept", "trying"] = "kept"


class Mind(BaseModel):
    beliefs: Beliefs
    memories: list[Memory] = []
    plan: Plan | None = None
    last_planned_at: int | None = None
    memory_cursor: int = 0  # memories before this index have already been considered for replanning
    failed_actions: int = 0
    last_failure: str | None = None
    replans: int = 0
    adaptations: int = 0
    signalled: list[str] = []  # facts already broadcast, so signals are not repeated
    trust: dict[str, int] = {}  # -5..5 towards each other character
    requests: list[HelpRequest] = []  # help this character has agreed to give
    # Strategy preference from an LLM deliberation; used only while it remains a valid option.
    preferred_strategy: str | None = None
    preference_expires_at: int | None = None
    preference_thought: str | None = None  # the LLM's one-line reason for that preference
    deliberations: int = 0
    trace: DecisionTrace | None = None
    wait_log: list[WaitEpisode] = []
    lessons: list[ActiveLesson] = []  # from the team journal, loaded when the run is created
    lessons_used: list[int] = []      # ids of lessons that actually changed a decision in this run
    orders: list[Order] = []  # player commands to carry out, in order, before resuming own plans
