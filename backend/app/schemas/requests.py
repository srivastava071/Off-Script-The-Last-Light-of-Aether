from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import ActionType, GameMode


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CreateRunRequest(_Strict):
    mode: GameMode
    player_character: str | None = None


class PlayerActionRequest(_Strict):
    """A player action. The actor is always the run's player character, so it is not sent."""

    type: ActionType
    destination: str | None = None
    route_id: str | None = None
    object_id: str | None = None
    target_id: str | None = None
    seconds: int | None = Field(default=None, ge=5, le=60)
    message: str | None = Field(default=None, max_length=280)
    topic: Literal["plan", "news"] | None = None
    request: ActionType | None = None
    request_id: str | None = Field(default=None, min_length=1, max_length=64)


class DialogueRequest(_Strict):
    target_id: str
    message: str = Field(min_length=1, max_length=280)
    request_id: str | None = Field(default=None, min_length=1, max_length=64)


class CommandRequest(_Strict):
    """A typed or spoken instruction, relayed to the team by radio."""

    text: str = Field(min_length=1, max_length=300)
    request_id: str | None = Field(default=None, min_length=1, max_length=64)


class SayRequest(_Strict):
    """Something said to the team by radio: heard and remembered, never obeyed."""

    text: str = Field(min_length=1, max_length=280)
    request_id: str | None = Field(default=None, min_length=1, max_length=64)


class TwistRequest(_Strict):
    """A story twist written by the player; matched to what the island allows right now."""

    text: str = Field(min_length=1, max_length=200)
    request_id: str | None = Field(default=None, min_length=1, max_length=64)


class AdvanceRequest(_Strict):
    ticks: int = Field(default=1, ge=1, le=120)


class PauseRequest(_Strict):
    paused: bool
