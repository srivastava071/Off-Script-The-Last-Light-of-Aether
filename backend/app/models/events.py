from typing import Any

from pydantic import BaseModel

from app.models.enums import EventKind


class WorldEvent(BaseModel):
    seq: int
    time: int
    kind: EventKind
    description: str
    actor: str | None = None
    location_id: str | None = None
    data: dict[str, Any] = {}
