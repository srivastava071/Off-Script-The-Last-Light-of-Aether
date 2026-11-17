"""Run endpoints. Every run-specific call needs the run's token in the X-Run-Token header.

Rule rejections (e.g. "the bridge is broken") are normal game outcomes: they return 200 with
``ok: false`` and an explanation. HTTP errors are reserved for protocol problems:
401 bad token, 404 unknown run, 409 invalid state change, 422 malformed request, 429 too many requests.
"""

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status

from app.core.config import Settings, get_settings
from app.engine.analytics import RunAnalytics, run_analytics
from app.models.actions import ActionResult, ProposedAction
from app.models.enums import ActionType
from app.schemas.requests import (
    AdvanceRequest, CommandRequest, CreateRunRequest, DialogueRequest, PauseRequest, PlayerActionRequest, SayRequest,
    TwistRequest,
)
from app.schemas.views import (
    CharacterView, CreatedRun, EventsView, RunSummary, StateView, character_views, state_view,
)
from app.services.run_manager import (
    Conflict, ManagedRun, NotAuthorized, RateLimited, RunError, RunManager, RunNotFound,
)

router = APIRouter(prefix="/api/runs", tags=["runs"])


def manager(request: Request) -> RunManager:
    return request.app.state.run_manager


async def managed_run(
    run_id: str,
    x_run_token: str | None = Header(default=None),
    runs: RunManager = Depends(manager),
) -> ManagedRun:
    try:
        return await runs.get(run_id, x_run_token)
    except RunNotFound:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Unknown run.") from None
    except NotAuthorized:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing or invalid X-Run-Token for this run.") from None


def _state(m: ManagedRun, runs: RunManager, settings: Settings) -> StateView:
    return state_view(m.world, ai_mode="live" if settings.is_live_llm else "mock",
                      paused=m.paused, sim_speed=runs.speed(m))


async def _guard(coro):
    try:
        return await coro
    except RateLimited as e:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, str(e)) from None
    except Conflict as e:
        raise HTTPException(status.HTTP_409_CONFLICT, str(e)) from None


# --- collection ------------------------------------------------------------------------------------------

@router.post("", response_model=CreatedRun, status_code=status.HTTP_201_CREATED)
async def create_run(body: CreateRunRequest, runs: RunManager = Depends(manager),
                     settings: Settings = Depends(get_settings)) -> CreatedRun:
    try:
        m, token = await runs.create(body.mode, body.player_character)
    except RunError as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(e)) from None
    return CreatedRun(run_id=m.world.run_id, token=token, state=_state(m, runs, settings))


@router.get("", response_model=list[RunSummary])
async def list_runs(limit: int = Query(20, ge=1, le=100), status_filter: str | None = Query(None, alias="status"),
                    runs: RunManager = Depends(manager)) -> list[RunSummary]:
    return [RunSummary.model_validate(r, from_attributes=True) for r in runs.repo.list_runs(limit, status_filter)]


# --- one run --------------------------------------------------------------------------------------------------

@router.get("/{run_id}", response_model=StateView)
@router.get("/{run_id}/state", response_model=StateView)
async def get_state(m: ManagedRun = Depends(managed_run), runs: RunManager = Depends(manager),
                    settings: Settings = Depends(get_settings)) -> StateView:
    async with m.lock:
        return _state(m, runs, settings)


@router.post("/{run_id}/start", response_model=StateView)
async def start_run(m: ManagedRun = Depends(managed_run), runs: RunManager = Depends(manager),
                    settings: Settings = Depends(get_settings)) -> StateView:
    await runs.start(m)
    async with m.lock:
        return _state(m, runs, settings)


@router.post("/{run_id}/actions", response_model=ActionResult)
async def player_action(body: PlayerActionRequest, m: ManagedRun = Depends(managed_run),
                        runs: RunManager = Depends(manager)) -> ActionResult:
    actor = m.world.story.player_character or ""
    fields = body.model_dump(exclude={"request_id"}, exclude_none=True)
    try:
        action = ProposedAction(actor=actor, **fields)
    except ValueError as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(e)) from None
    return await _guard(runs.act(m, action, body.request_id))


@router.post("/{run_id}/dialogue", response_model=ActionResult)
async def dialogue(body: DialogueRequest, m: ManagedRun = Depends(managed_run),
                   runs: RunManager = Depends(manager)) -> ActionResult:
    actor = m.world.story.player_character or ""
    action = ProposedAction(actor=actor, type=ActionType.TALK, target_id=body.target_id, message=body.message)
    return await _guard(runs.act(m, action, body.request_id))


@router.post("/{run_id}/command", response_model=ActionResult)
async def command(body: CommandRequest, m: ManagedRun = Depends(managed_run),
                  runs: RunManager = Depends(manager)) -> ActionResult:
    return await _guard(runs.command(m, body.text.strip(), body.request_id))


@router.post("/{run_id}/say", response_model=ActionResult)
async def say(body: SayRequest, m: ManagedRun = Depends(managed_run),
              runs: RunManager = Depends(manager)) -> ActionResult:
    return await _guard(runs.say(m, body.text.strip(), body.request_id))


@router.post("/{run_id}/twist", response_model=ActionResult)
async def twist(body: TwistRequest, m: ManagedRun = Depends(managed_run),
                runs: RunManager = Depends(manager)) -> ActionResult:
    return await _guard(runs.twist(m, body.text.strip(), body.request_id))


@router.post("/{run_id}/advance", response_model=StateView)
async def advance(body: AdvanceRequest, m: ManagedRun = Depends(managed_run), runs: RunManager = Depends(manager),
                  settings: Settings = Depends(get_settings)) -> StateView:
    await _guard(runs.advance(m, body.ticks))
    async with m.lock:
        return _state(m, runs, settings)


@router.post("/{run_id}/pause", response_model=StateView)
async def pause(body: PauseRequest, m: ManagedRun = Depends(managed_run), runs: RunManager = Depends(manager),
                settings: Settings = Depends(get_settings)) -> StateView:
    await _guard(runs.pause(m, body.paused))
    async with m.lock:
        return _state(m, runs, settings)


@router.get("/{run_id}/events", response_model=EventsView)
async def events(after: int = Query(0, ge=0), limit: int = Query(200, ge=1, le=1000),
                 m: ManagedRun = Depends(managed_run)) -> EventsView:
    async with m.lock:
        new = [e for e in m.world.events if e.seq > after][:limit]
        return EventsView(events=new, last_event_seq=m.world.next_event_seq - 1)


@router.get("/{run_id}/characters", response_model=list[CharacterView])
async def characters(m: ManagedRun = Depends(managed_run)) -> list[CharacterView]:
    async with m.lock:
        return character_views(m.world)


@router.get("/{run_id}/analytics", response_model=RunAnalytics)
async def analytics(m: ManagedRun = Depends(managed_run)) -> RunAnalytics:
    """Gameplay graphs: each character's timeline, mission progress and decisions (so far, or for the whole run)."""
    async with m.lock:
        return run_analytics(m.world)


@router.post("/{run_id}/restart", response_model=CreatedRun, status_code=status.HTTP_201_CREATED)
async def restart(m: ManagedRun = Depends(managed_run), runs: RunManager = Depends(manager),
                  settings: Settings = Depends(get_settings)) -> CreatedRun:
    new, token = await runs.restart(m)
    return CreatedRun(run_id=new.world.run_id, token=token, state=_state(new, runs, settings))
