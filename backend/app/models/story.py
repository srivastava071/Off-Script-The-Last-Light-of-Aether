"""Narrative state tracked by the Director: beats, objectives, assessment and the ending."""

from pydantic import BaseModel, Field

from app.models.actions import ActionResult
from app.models.enums import EndingId, ObjectiveStatus, RunStatus


class StoryBeat(BaseModel):
    id: str
    title: str
    reached_at: int | None = None


class Objective(BaseModel):
    id: str
    title: str
    description: str
    optional: bool
    status: ObjectiveStatus = ObjectiveStatus.PENDING
    resolved_at: int | None = None


class Assessment(BaseModel):
    progress: float = 0.0          # fraction of story beats reached
    risk: str = "on_track"         # on_track | at_risk | failing
    note: str = "The expedition sets out."
    blocked: list[str] = []        # autonomous characters whose plans are blocked


class EndingResult(BaseModel):
    ending: EndingId
    title: str
    main_success: bool
    finished_at: int
    explanation: str
    summary: str
    objectives: list[Objective]
    routes: dict[str, list[str]]   # character -> locations visited, in order
    adaptations: list[str]
    key_events: list[str]
    stats: dict[str, int]
    narration: str | None = None       # optional LLM epilogue, grounded in key_events
    narrated_by: str | None = None     # "provider:model" that wrote it


class Chapter(BaseModel):
    """One page of the live storybook. Written from a template at once; an LLM may rewrite it later."""

    id: int
    time: int
    title: str
    text: str
    kind: str                       # "beat" | "twist"
    facts: list[str] = []           # the recorded events it is based on (grounding for the LLM)
    generated_by: str = "template"  # "template" or "provider:model"


class AIStats(BaseModel):
    """Per-run record of LLM use, for evaluation and so mock output is never passed off as LLM output."""

    deliberations_requested: int = 0
    deliberations_applied: int = 0     # a valid choice that the character then acted on
    fallbacks: int = 0                 # LLM unavailable, budget exhausted, invalid or stale answer
    invalid_answers: int = 0
    deliberations_discarded: int = 0   # the run ended before the answer arrived
    llm_replies: int = 0
    template_replies: int = 0
    calls_succeeded: int = 0
    total_latency_ms: int = 0
    providers: dict[str, int] = {}


class StoryState(BaseModel):
    status: RunStatus = RunStatus.CREATED
    player_character: str | None = None  # None in Default Mode
    beats: list[StoryBeat] = []
    objectives: list[Objective] = []
    assessment: Assessment = Field(default_factory=Assessment)
    storm_warnings: list[int] = []        # remaining-seconds thresholds already announced
    last_beat_at: int = 0
    stall_noted: bool = False
    event_cursor: int = 0                 # events before this seq have been reviewed by the Director
    ending: EndingResult | None = None
    ai: AIStats = Field(default_factory=AIStats)
    chapters: list[Chapter] = []
    chapter_cursor: int = 0               # events up to this seq are already told in a chapter
    twists_used: int = 0
    last_twist_at: int | None = None
    processed_requests: dict[str, ActionResult] = {}  # request id -> result, for idempotent retries
