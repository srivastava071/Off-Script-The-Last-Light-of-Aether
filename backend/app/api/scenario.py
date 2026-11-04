"""Static scenario description for menus and character selection (no run needed)."""

from fastapi import APIRouter
from pydantic import BaseModel

from app.engine.aether import LOCATIONS, PROFILES, initial_objectives
from app.models.story import Objective
from app.models.world import CharacterProfile, Location

router = APIRouter(prefix="/api", tags=["scenario"])

TITLE = "The Last Light of Aether"
BACKSTORY = (
    "Aether Island is protected by a magical barrier powered by the Sun Crystal. The crystal has been taken "
    "from the lighthouse and hidden in an ancient temple. A violent storm is coming, and the barrier is failing."
)


class Scenario(BaseModel):
    title: str
    backstory: str
    characters: list[CharacterProfile]
    locations: list[Location]
    objectives: list[Objective]


@router.get("/scenario", response_model=Scenario)
def scenario() -> Scenario:
    return Scenario(title=TITLE, backstory=BACKSTORY, characters=PROFILES, locations=LOCATIONS,
                    objectives=initial_objectives())
