"""Carrying out player orders, one validated step at a time.

An order is either "go to X", "do action A" or "wait". For an action that can only be done
somewhere specific (repair the bridge, pull the lever...), the character first walks there along
the path it believes exists. Every step is attempted through the rules engine; if a step turns out
to be impossible (no known path, missing timber...), the character says why and drops it.
The same code drives teammates and the player's own character ("autopilot").
"""

from app.agents.view import BeliefView
from app.engine import knowledge
from app.engine.ids import BRIDGE, LIGHTHOUSE, TEMPLE
from app.engine.rules import check_action, perform
from app.models.actions import ProposedAction
from app.models.enums import ActionType as A
from app.models.enums import EventKind
from app.models.events import WorldEvent
from app.models.mind import Order
from app.models.world import WorldState

FIXED_PLACE = {
    A.REPAIR_BRIDGE: BRIDGE,
    A.REPAIR_MECHANISM: TEMPLE,
    A.DECODE_SYMBOLS: TEMPLE,
    A.PULL_LEVER: TEMPLE,
    A.REPAIR_LIGHTHOUSE: LIGHTHOUSE,
    A.INSTALL_CRYSTAL: LIGHTHOUSE,
    A.ACTIVATE_LIGHTHOUSE: LIGHTHOUSE,
}


def required_location(world: WorldState, cid: str, action: ProposedAction) -> str | None:
    """Where the character believes it must stand to do this action (None: anywhere / here)."""
    if action.type in FIXED_PLACE:
        return FIXED_PLACE[action.type]
    v = BeliefView(world, cid)
    if action.type is A.PICK_UP and action.object_id:
        return v.item(action.object_id).location_id
    if action.type is A.GIVE and action.target_id:
        return v.last_seen(action.target_id)
    if action.type in (A.BLOCK_ROUTE, A.CLEAR_ROUTE, A.DETECT_TRAPS) and action.route_id in world.routes:
        route = world.routes[action.route_id]
        if v.here in (route.a, route.b):
            return v.here
        ends = [(v.eta(end), end) for end in (route.a, route.b)]
        reachable = [(eta, end) for eta, end in ends if eta is not None]
        return min(reachable)[1] if reachable else route.a
    return None


def _fail(world: WorldState, cid: str, order: Order, reason: str) -> WorldEvent:
    mind = world.minds[cid]
    mind.orders.pop(0)
    return world.record(EventKind.ORDER_FAILED, f"{world.name(cid)} could not {order.summary}: {reason}",
                        actor=cid, location_id=world.characters[cid].location_id, target=order.from_id,
                        order=order.summary, reason=reason)


def _completed_if_empty(world: WorldState, cid: str, order: Order) -> list[WorldEvent]:
    if world.minds[cid].orders:
        return []
    return [world.record(EventKind.ORDER_COMPLETED,
                         f"{world.name(cid)} has finished what {world.name(order.from_id)} asked"
                         f" and goes back to their own plan." if cid != order.from_id else
                         f"{world.name(cid)} has finished the instructions.",
                         actor=cid, location_id=world.characters[cid].location_id, target=order.from_id)]


def next_order_action(world: WorldState, cid: str) -> tuple[ProposedAction | None, Order | None, list[WorldEvent]]:
    """Drop finished or impossible orders and return the next action to take for the first live one."""
    mind = world.minds[cid]
    events: list[WorldEvent] = []
    while mind.orders:
        order = mind.orders[0]
        if order.started_at is not None:
            # The action ran its full duration while the character was busy. Did it succeed?
            failure = next((e for e in reversed(world.events) if e.actor == cid and e.time >= order.started_at
                            and e.kind is EventKind.ACTION_FAILED), None)
            if failure is not None:
                events.append(_fail(world, cid, order, str(failure.data.get("reason", "it did not work"))))
                continue
            mind.orders.pop(0)
            events += _completed_if_empty(world, cid, order)
            continue
        v = BeliefView(world, cid)
        if order.kind == "go_to":
            if v.here == order.location:
                mind.orders.pop(0)
                events += _completed_if_empty(world, cid, order)
                continue
            hop = v.next_hop(order.location or "")
            if hop is None:
                events.append(_fail(world, cid, order,
                                    f"{world.name(cid)} knows no way to the {world.locations[order.location or ''].name}."))
                continue
            return hop, order, events

        action = order.action
        assert action is not None
        if action.type is A.DETECT_TRAPS and action.route_id is None:
            trapped = [rid for rid, rb in v.beliefs.routes.items() if rb.known and world.routes[rid].hazard]
            if not trapped:
                events.append(_fail(world, cid, order, f"{world.name(cid)} doesn't know of any trapped route."))
                continue
            action = action.model_copy(update={"route_id": trapped[0]})
            order.action = action
        place = required_location(world, cid, action) if order.kind == "action" else None
        if place is not None and v.here != place:
            hop = v.next_hop(place)
            if hop is None:
                events.append(_fail(world, cid, order,
                                    f"{world.name(cid)} knows no way to the {world.locations[place].name}."))
                continue
            return hop, order, events
        if (reason := check_action(world, action)) is not None:
            events.append(_fail(world, cid, order, reason))
            continue
        return action, order, events
    return None, None, events


def mark_done(world: WorldState, cid: str, performed: ProposedAction) -> list[WorldEvent]:
    """After an accepted action: if it was the order itself (not a step towards it), remember that it started.

    The order counts as done only when the action has finished (checked on the next idle step).
    """
    mind = world.minds[cid]
    if mind.orders:
        order = mind.orders[0]
        if order.action is not None and order.action == performed and order.started_at is None:
            order.started_at = world.clock.now
    return []


class PlayerAutopilot:
    """Carries out the player's own spoken/typed instructions when the player is idle.

    It has the same interface as a CharacterAgent so the simulation can step it in the same loop,
    but it never decides anything by itself: with no orders, it does nothing.
    """

    def __init__(self, character_id: str):
        self.character_id = character_id

    def step(self, world: WorldState) -> list[WorldEvent]:
        cid = self.character_id
        if world.characters[cid].busy or not world.minds[cid].orders:
            return []
        knowledge.perceive(world, cid)
        action, _order, events = next_order_action(world, cid)
        if action is None:
            return events
        result = perform(world, action)
        knowledge.observe(world, result.events)
        events += result.events
        if result.ok:
            events += mark_done(world, cid, action)
        return events
