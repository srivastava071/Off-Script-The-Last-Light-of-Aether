from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app import __version__
from app.core.config import Settings, get_settings

router = APIRouter(prefix="/api", tags=["health"])


class HealthResponse(BaseModel):
    status: str
    version: str
    ai_provider: str
    ai_mode: str  # "mock" or "live" - shown in the UI so mock is never mistaken for a real LLM
    llm_model: str | None  # first provider tried
    llm_providers: list[str]  # "name:model" in failover order; never includes keys
    sim_tick_seconds: int
    game_deadline_seconds: int


@router.get("/health", response_model=HealthResponse)
def health(settings: Settings = Depends(get_settings)) -> HealthResponse:
    return HealthResponse(
        status="ok",
        version=__version__,
        ai_provider=settings.ai_provider.value,
        ai_mode="live" if settings.is_live_llm else "mock",
        llm_model=settings.llm_providers[0].label if settings.is_live_llm else None,
        llm_providers=[p.label for p in settings.llm_providers] if settings.is_live_llm else [],
        sim_tick_seconds=settings.sim_tick_seconds,
        game_deadline_seconds=settings.game_deadline_seconds,
    )
