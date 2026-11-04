"""Graph movement.

Travel is committed when it starts: a character already on a route finishes the trip even
if the route is blocked behind them. Arrivals are completed by the timeline (engine.timeline).
"""

import heapq
import math
from collections.abc import Iterable

from app.models.actions import ActionResult
from app.models.enums import EventKind, RouteStatus
from app.models.events import WorldEvent
from app.models.world import CharacterProfile, CharacterState, Route, Travel, WorldState


def hazard_penalty(world: WorldState, character_id: str, route: Route) -> int:
    if not route.hazard_active:
        return 0
    bypass = route.hazard_bypass
    if bypass is not None and world.profiles[character_id].has(bypass):
        return 0
    return route.hazard_penalty_seconds


def travel_seconds(world: WorldState, character_id: str, route: Route) -> int:
    """Total journey time for this character, including any hazard penalty."""
    return route_seconds(world.profiles[character_id], route)


def traverse_blocker(world: WorldState, character_id: str, route: Route) -> str | None:
    """Return why the character cannot use this route right now, or None if they can."""
    return route_blocker(world.profiles[character_id], route)


def route_blocker(profile: CharacterProfile, route: Route) -> str | None:
    if route.hidden:
        return f"{route.name} has not been discovered."
    if route.status is not RouteStatus.OPEN:
        return f"{route.name} is {route.status.value}."
    if route.obstructed:
        return f"{route.name} is blocked."
    if route.requires_ability is not None and not profile.has(route.requires_ability):
        return f"{profile.name} lacks the '{route.requires_ability.value}' ability needed for {route.name}."
    return None


def find_path(world: WorldState, character_id: str, start: str, goal: str) -> list[Route] | None:
    """Fastest currently-usable path for this character (Dijkstra), or None if unreachable."""
    return find_path_on(world.routes.values(), world.profiles[character_id], start, goal)


def route_seconds(profile: CharacterProfile, route: Route) -> int:
    """Journey time for a profile on a route, including any active hazard penalty."""
    seconds = max(1, math.ceil(route.base_seconds / profile.speed_multiplier))
    if route.hazard_active and not (route.hazard_bypass is not None and profile.has(route.hazard_bypass)):
        seconds += route.hazard_penalty_seconds
    return seconds


def find_path_on(routes: Iterable[Route], profile: CharacterProfile, start: str, goal: str) -> list[Route] | None:
    """Dijkstra over any set of routes - the true map, or a character's believed map."""
    if start == goal:
        return []
    # (elapsed, tie-breaker, location, path)
    frontier: list[tuple[int, int, str, list[Route]]] = [(0, 0, start, [])]
    best: dict[str, int] = {start: 0}
    counter = 1
    while frontier:
        elapsed, _, here, path = heapq.heappop(frontier)
        if here == goal:
            return path
        if elapsed > best.get(here, math.inf):
            continue
        for route in sorted((r for r in routes if r.connects(here)), key=lambda r: r.id):
            if route_blocker(profile, route) is not None:
                continue
            there = route.other_end(here)
            cost = elapsed + route_seconds(profile, route)
            if cost < best.get(there, math.inf):
                best[there] = cost
                heapq.heappush(frontier, (cost, counter, there, path + [route]))
                counter += 1
    return None


def _choose_route(
    world: WorldState, character_id: str, destination: str, route_id: str | None
) -> tuple[Route | None, str | None]:
    """Pick the route for a move, or explain why the move is impossible."""
    if character_id not in world.characters:
        return None, f"Unknown character '{character_id}'."
    if destination not in world.locations:
        return None, f"Unknown location '{destination}'."
    state = world.characters[character_id]
    name = world.name(character_id)
    if state.travel is not None:
        return None, f"{name} is already travelling."
    origin = state.location_id
    assert origin is not None
    if destination == origin:
        return None, f"{name} is already at {world.locations[origin].name}."

    candidates = [r for r in world.routes_from(origin) if r.other_end(origin) == destination]
    if route_id is not None:
        candidates = [r for r in candidates if r.id == route_id]
    if not candidates:
        return None, (
            f"No route connects {world.locations[origin].name} to {world.locations[destination].name}."
        )
    usable = [r for r in candidates if traverse_blocker(world, character_id, r) is None]
    if not usable:
        reasons = " ".join(traverse_blocker(world, character_id, r) or "" for r in candidates)
        return None, f"{name} cannot travel there: {reasons}"
    return min(usable, key=lambda r: (travel_seconds(world, character_id, r), r.id)), None


def move_blocker(world: WorldState, character_id: str, destination: str, route_id: str | None = None) -> str | None:
    return _choose_route(world, character_id, destination, route_id)[1]


def start_travel(
    world: WorldState, character_id: str, destination: str, route_id: str | None = None
) -> ActionResult:
    """Begin moving to an adjacent location along a usable route (the fastest one unless route_id is given)."""
    route, reason = _choose_route(world, character_id, destination, route_id)
    if route is None:
        return ActionResult.reject(reason or "Cannot move.")
    state = world.characters[character_id]
    origin = state.location_id
    assert origin is not None
    duration = travel_seconds(world, character_id, route)
    now = world.clock.now
    state.location_id = None
    state.travel = Travel(
        route_id=route.id,
        from_location=origin,
        to_location=destination,
        depart_at=now,
        arrive_at=now + duration,
        hazard_penalty=hazard_penalty(world, character_id, route),
    )
    name = world.name(character_id)
    event = world.record(
        EventKind.TRAVEL_STARTED,
        f"{name} sets off along the {route.name} towards {world.locations[destination].name}.",
        actor=character_id,
        location_id=origin,
        route_id=route.id,
        destination=destination,
        arrive_at=now + duration,
    )
    return ActionResult.success(f"{name} will arrive in {duration}s.", event, completes_at=now + duration)


def complete_travel(world: WorldState, state: CharacterState) -> list[WorldEvent]:
    """Called by the timeline at the arrival time."""
    travel = state.travel
    assert travel is not None
    name = world.name(state.id)
    route = world.routes[travel.route_id]
    events: list[WorldEvent] = []
    if travel.hazard_penalty:
        events.append(world.record(
            EventKind.TRAP_SPRUNG,
            f"{name} springs a {route.hazard} snare on the {route.name} and loses {travel.hazard_penalty}s.",
            actor=state.id, route_id=route.id, penalty=travel.hazard_penalty,
        ))
    state.location_id = travel.to_location
    state.travel = None
    events.append(world.record(
        EventKind.ARRIVED,
        f"{name} arrives at {world.locations[travel.to_location].name}.",
        actor=state.id, location_id=travel.to_location, route_id=travel.route_id,
    ))
    return events


def travel_progress(world: WorldState, character_id: str) -> float | None:
    """Fraction (0..1) of the current journey completed, for rendering; None when not travelling."""
    travel = world.characters[character_id].travel
    if travel is None:
        return None
    span = travel.arrive_at - travel.depart_at
    return min(1.0, max(0.0, (world.clock.now - travel.depart_at) / span))
