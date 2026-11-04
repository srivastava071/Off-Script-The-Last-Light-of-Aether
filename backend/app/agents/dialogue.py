"""What an autonomous character says back when someone talks to it.

This deterministic version speaks only from the character's own mind (plan, trust). An LLM
dialogue agent can replace ``reply`` later; it must stay grounded in the same mind.
"""

from app.engine.ids import ARIA, KABIR, MEERA
from app.models.events import WorldEvent
from app.models.enums import EventKind
from app.models.world import WorldState

OPENERS = {
    ARIA: "No time to lose!",
    KABIR: "Let's be methodical about this.",
    MEERA: "Stay sharp.",
}


def reply(world: WorldState, speaker: str, listener: str) -> str:
    mind = world.minds[speaker]
    opener = OPENERS.get(speaker, "")
    if mind.trust.get(listener, 0) < 0:
        opener = "After what you did, I'm keeping my distance."
    if mind.plan is None:
        return f"{opener} I'm still working out what to do."
    return f"{opener} {mind.plan.summary}"


def reply_event(world: WorldState, speaker: str, listener: str, text: str | None = None,
                generated_by: str = "template") -> WorldEvent:
    """Record a spoken reply. ``generated_by`` says honestly whether a template or an LLM wrote it."""
    text = text if text is not None else reply(world, speaker, listener)
    return world.record(EventKind.TALKED, f'{world.name(speaker)}: "{text}"', actor=speaker,
                        location_id=world.characters[speaker].location_id, target=listener,
                        message=text, reply=True, generated_by=generated_by)
