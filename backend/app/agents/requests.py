"""How an autonomous character answers a request for help.

The rules engine has already checked that the helper is *able* to do it. Here the helper decides
whether it is *willing*: it refuses people it distrusts, and it will not drop the Sun Crystal
delivery for an errand. Accepted requests are remembered and carried out by the agent's planner.
"""

from app.engine.ids import ARIA, KABIR, MEERA, SUN_CRYSTAL
from app.models.actions import ProposedAction
from app.models.enums import ActionType, EventKind
from app.models.events import WorldEvent
from app.models.mind import HelpRequest
from app.models.world import WorldState

REQUEST_TTL_SECONDS = 90
MIN_TRUST_TO_HELP = -1

AGREE = {
    ARIA: "On it — let's move!",
    KABIR: "Very well. I'll see to it properly.",
    MEERA: "Understood. Leave it to me.",
}


def respond(world: WorldState, request_event: WorldEvent) -> list[WorldEvent]:
    helper = request_event.data["target"]
    asker = request_event.actor or ""
    wanted = ProposedAction(**request_event.data["request"])
    mind = world.minds[helper]
    name, asker_name = world.name(helper), world.name(asker)
    now = world.clock.now

    reason = None
    if mind.trust.get(asker, 0) < MIN_TRUST_TO_HELP:
        reason = f"{name} doesn't trust {asker_name} after what happened."
    elif world.carries(helper, SUN_CRYSTAL) and not (
        wanted.type is ActionType.GIVE and wanted.object_id == SUN_CRYSTAL
    ):
        reason = f"{name} must get the Sun Crystal to the Lighthouse first."
    if reason:
        return [world.record(EventKind.HELP_DECLINED, f"{name} declines: {reason}", actor=helper,
                             location_id=world.characters[helper].location_id, target=asker, reason=reason)]

    mind.requests = [HelpRequest(from_id=asker, action=wanted, made_at=now, expires_at=now + REQUEST_TTL_SECONDS)]
    line = AGREE.get(helper, "All right.")
    return [world.record(EventKind.HELP_ACCEPTED, f'{name} agrees to help {asker_name}: "{line}"', actor=helper,
                         location_id=world.characters[helper].location_id, target=asker,
                         request=wanted.model_dump(mode="json", exclude_none=True))]
