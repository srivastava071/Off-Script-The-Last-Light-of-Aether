"""Advancing a run: autonomous agents act, the clock moves, observers learn.

All world changes are applied here in a fixed order (agents by id, then due events by time),
so the simulation is reproducible and never has two writers at once. Agents act at the exact
moment they become idle, not just on tick boundaries.
(engine.run.Run wraps this with the Director, modes and deadlines.)
"""

from collections.abc import Mapping

from app.agents.character_agent import CharacterAgent
from app.engine import knowledge
from app.engine.timeline import advance_clock, next_due_time
from app.models.events import WorldEvent
from app.models.world import WorldState


def run_tick(world: WorldState, agents: Mapping[str, CharacterAgent], until: int | None = None) -> list[WorldEvent]:
    """Advance one simulation tick (``clock.tick_seconds``), or up to ``until`` if given."""
    end = world.clock.now + world.clock.tick_seconds if until is None else until
    events: list[WorldEvent] = []

    def on_events(new: list[WorldEvent]) -> None:
        knowledge.observe(world, new)

    while True:
        for cid in sorted(agents):
            events += agents[cid].step(world)
        due = next_due_time(world, end)
        if due is None:
            events += advance_clock(world, end - world.clock.now, on_events)
            return events
        events += advance_clock(world, due - world.clock.now, on_events)
