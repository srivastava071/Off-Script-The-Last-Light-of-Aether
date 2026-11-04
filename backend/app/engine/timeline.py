"""The simulation timeline: advances the clock and fires everything that falls due, in time order.

Ordering within the same second: scheduled world effects, then arrivals, then activity
completions; ties broken by id. This makes every run reproducible.
"""

from collections.abc import Callable

from app.engine.movement import complete_travel
from app.engine.obstacles import apply_scheduled
from app.engine.rules import complete_activity
from app.models.events import WorldEvent
from app.models.world import WorldState

_EFFECT, _ARRIVAL, _ACTIVITY = 0, 1, 2


def _next_due(world: WorldState, until: int) -> tuple[int, int, str, object] | None:
    due: list[tuple[int, int, str, object]] = []
    for i, effect in enumerate(world.scheduled):
        if effect.time <= until:
            due.append((effect.time, _EFFECT, f"{i:04d}", effect))
    for state in world.characters.values():
        if state.travel is not None and state.travel.arrive_at <= until:
            due.append((state.travel.arrive_at, _ARRIVAL, state.id, state))
        if state.activity is not None and state.activity.completes_at <= until:
            due.append((state.activity.completes_at, _ACTIVITY, state.id, state))
    return min(due, key=lambda d: d[:3]) if due else None


def next_due_time(world: WorldState, until: int) -> int | None:
    item = _next_due(world, until)
    return None if item is None else item[0]


def advance_clock(
    world: WorldState, seconds: int, on_events: Callable[[list[WorldEvent]], None] | None = None
) -> list[WorldEvent]:
    """Move simulated time forward by ``seconds``, resolving all arrivals, completions and effects.

    ``on_events`` is called after each resolved item, so observers see the world exactly as it
    was when the event happened.
    """
    if seconds < 0:
        raise ValueError("the simulation clock cannot run backwards")
    target = world.clock.now + seconds
    events: list[WorldEvent] = []
    while (item := _next_due(world, target)) is not None:
        time, kind, _, subject = item
        world.clock.now = time
        if kind == _EFFECT:
            world.scheduled.remove(subject)  # type: ignore[arg-type]
            new = apply_scheduled(world, subject)  # type: ignore[arg-type]
        elif kind == _ARRIVAL:
            new = complete_travel(world, subject)  # type: ignore[arg-type]
        else:
            new = complete_activity(world, subject)  # type: ignore[arg-type]
        if on_events is not None and new:
            on_events(new)
        events += new
    world.clock.now = target
    return events
