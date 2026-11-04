from app.engine.invariants import check_invariants
from app.engine.movement import find_path
from app.engine.rules import perform
from app.engine.timeline import advance_clock
from app.models.actions import ActionResult, ProposedAction
from app.models.enums import ActionType
from app.models.world import WorldState


def act(world: WorldState, actor: str, type: ActionType, **kw) -> ActionResult:
    return perform(world, ProposedAction(actor=actor, type=type, **kw))


def do(world: WorldState, actor: str, type: ActionType, **kw) -> ActionResult:
    result = act(world, actor, type, **kw)
    assert result.ok, result.message
    return result


def settle(world: WorldState, *actors: str, limit: int = 1000) -> None:
    """Advance one second at a time until the given characters are idle, checking invariants."""
    for _ in range(limit):
        if not any(world.characters[a].busy for a in actors):
            return
        advance_clock(world, 1)
        assert check_invariants(world) == []
    raise AssertionError("characters never became idle")


def walk(world: WorldState, actor: str, destination: str) -> None:
    here = world.characters[actor].location_id
    path = find_path(world, actor, here, destination)
    assert path is not None, f"{actor} has no path from {here} to {destination}"
    for route in path:
        here = world.characters[actor].location_id
        do(world, actor, ActionType.MOVE, destination=route.other_end(here), route_id=route.id)
        settle(world, actor)
