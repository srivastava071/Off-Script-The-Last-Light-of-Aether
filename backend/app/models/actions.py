from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.enums import ActionType
from app.models.events import WorldEvent


class ProposedAction(BaseModel):
    """An action a player or agent wants to take. It changes nothing until the rules engine accepts it."""

    model_config = ConfigDict(extra="forbid")

    actor: str
    type: ActionType
    destination: str | None = None
    route_id: str | None = None
    object_id: str | None = None
    target_id: str | None = None  # another character
    seconds: int | None = Field(default=None, ge=5, le=60)  # WAIT only
    message: str | None = Field(default=None, max_length=280)  # TALK / SIGNAL
    topic: Literal["plan", "news"] | None = None  # ASK only
    request: ActionType | None = None  # REQUEST_HELP only: what the target is asked to do

    @model_validator(mode="after")
    def _no_nested_social_requests(self) -> "ProposedAction":
        if self.request in (ActionType.REQUEST_HELP, ActionType.ASK, ActionType.TALK, ActionType.SIGNAL):
            raise ValueError("a help request must ask for a physical action")
        return self


class ActionResult(BaseModel):
    ok: bool
    message: str
    events: list[WorldEvent] = []
    completes_at: int | None = None
    duplicate: bool = False  # True when this is a replay of an already-processed request

    @classmethod
    def reject(cls, message: str) -> "ActionResult":
        return cls(ok=False, message=message)

    @classmethod
    def success(cls, message: str, *events: WorldEvent, completes_at: int | None = None) -> "ActionResult":
        return cls(ok=True, message=message, events=list(events), completes_at=completes_at)
