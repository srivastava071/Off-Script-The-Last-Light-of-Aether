from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app import __version__
from app.api import health, journal, runs, scenario
from app.core.config import REPO_ROOT, Settings, get_settings
from app.persistence.repository import RunRepository, make_engine
from app.services.llm import LLMService
from app.services.run_manager import RunManager


FRONTEND_DIST = REPO_ROOT / "frontend" / "dist"


def create_app(settings: Settings | None = None, llm: LLMService | None = None) -> FastAPI:
    """``llm`` lets tests inject a fake model; otherwise it is built from settings (None in mock mode)."""
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        repo = RunRepository(make_engine(settings.resolved_database_url))
        repo.create_schema()
        async with httpx.AsyncClient() as client:
            service = llm if llm is not None else LLMService.from_settings(settings, client)
            app.state.llm = service
            app.state.run_manager = RunManager(settings, repo, service)
            yield
            await app.state.run_manager.shutdown()
        repo.engine.dispose()

    app = FastAPI(title="Off Script: The Last Light of Aether", version=__version__, lifespan=lifespan)
    app.dependency_overrides[get_settings] = lambda: settings
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type", "X-Run-Token"],
    )
    app.include_router(health.router)
    app.include_router(runs.router)
    app.include_router(journal.router)
    app.include_router(scenario.router)
    # When the frontend has been built (npm run build), serve it from here too, so a single address
    # (e.g. one ngrok tunnel) carries both the game page and its /api. Mounted last: /api wins.
    if settings.serve_frontend and FRONTEND_DIST.is_dir():
        app.mount("/", StaticFiles(directory=FRONTEND_DIST, html=True), name="frontend")
    return app


app = create_app()
