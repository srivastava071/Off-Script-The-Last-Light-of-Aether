import pytest

from app.engine.aether import build_initial_world
from app.models.enums import GameMode
from app.models.world import WorldState


@pytest.fixture
def world() -> WorldState:
    return build_initial_world("test-run", GameMode.GAME, tick_seconds=5, deadline_seconds=600)
