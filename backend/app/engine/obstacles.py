"""Obstacle mechanics (A-E). Each action is a check (pure) + apply (mutates) + duration.

The rules engine calls ``check`` when an action starts and again when a deferred action
completes, so a repair can fail if the world changed while it was in progress.
"""

from app.engine.aether import FLOOD_SECONDS, FLOOD_WARNING_SECONDS
from app.engine.ids import (
    BRIDGE, CHAMBER, GEAR, LIGHTHOUSE, MAIN_BRIDGE, SUN_CRYSTAL, TEMPLE, TEMPLE_GATE, TIMBER, TOOLKIT,
)
from app.models.actions import ProposedAction
from app.models.enums import Ability, EventKind, RouteStatus
from app.models.events import WorldEvent
from app.models.world import Route, ScheduledEffect, WorldState

FLOOD_WARNING = "flood_warning"
CHAMBER_FLOODS = "chamber_floods"


def _here(world: WorldState, actor: str) -> str | None:
    return world.characters[actor].location_id


def _has(world: WorldState, actor: str, ability: Ability) -> bool:
    return world.profiles[actor].has(ability)


def _need_at(world: WorldState, actor: str, location_id: str) -> str | None:
    if _here(world, actor) != location_id:
        return f"{world.name(actor)} must be at the {world.locations[location_id].name}."
    return None


def _need_items(world: WorldState, actor: str, *object_ids: str) -> str | None:
    missing = [world.objects[o].name if o in world.objects else o for o in object_ids if not world.carries(actor, o)]
    if missing:
        return f"{world.name(actor)} needs to carry: {', '.join(missing)}."
    return None


def _route_here(world: WorldState, actor: str, action: ProposedAction) -> tuple[Route | None, str | None]:
    if action.route_id is None or action.route_id not in world.routes:
        return None, f"Unknown route '{action.route_id}'."
    route = world.routes[action.route_id]
    here = _here(world, actor)
    if here is None or not route.connects(here) or route.hidden:
        return None, f"{world.name(actor)} is not at either end of a known route called {route.name}."
    return route, None


def _consume(world: WorldState, object_id: str) -> None:
    del world.objects[object_id]


# --- Obstacle A / B: routes -------------------------------------------------------------

def discover_route_check(world: WorldState, a: ProposedAction) -> str | None:
    if not (_has(world, a.actor, Ability.DISCOVER_ROUTES) or _has(world, a.actor, Ability.INSPECT_CLUES)):
        return f"{world.name(a.actor)} does not know how to search for hidden paths."
    return None


def discover_route_seconds(world: WorldState, a: ProposedAction) -> int:
    return 20 if _has(world, a.actor, Ability.DISCOVER_ROUTES) else 35


def discover_route_apply(world: WorldState, a: ProposedAction) -> list[WorldEvent]:
    # Always allowed and always costs time; finding nothing is a valid result, so the
    # action menu never leaks where hidden routes are.
    here = _here(world, a.actor)
    assert here is not None
    found = [r for r in world.routes_from(here) if r.hidden]
    if not found:
        return [world.record(EventKind.SEARCHED, f"{world.name(a.actor)} searches for hidden paths but finds none.",
                             actor=a.actor, location_id=here)]
    events = []
    for route in found:
        route.hidden = False
        events.append(world.record(
            EventKind.ROUTE_DISCOVERED,
            f"{world.name(a.actor)} discovers the {route.name}"
            + (f" — it is riddled with {route.hazard}." if route.hazard_active else "."),
            actor=a.actor, location_id=here, route_id=route.id,
        ))
    return events


def detect_traps_check(world: WorldState, a: ProposedAction) -> str | None:
    if not _has(world, a.actor, Ability.DETECT_TRAPS):
        return f"{world.name(a.actor)} cannot detect traps."
    route, reason = _route_here(world, a.actor, a)
    if route is None:
        return reason
    if not route.hazard_active:
        return f"There are no active traps on the {route.name}."
    return None


def detect_traps_apply(world: WorldState, a: ProposedAction) -> list[WorldEvent]:
    route = world.routes[a.route_id or ""]
    route.hazard_active = False
    return [world.record(EventKind.TRAPS_MARKED, f"{world.name(a.actor)} finds and marks every snare on the {route.name}.",
                         actor=a.actor, location_id=_here(world, a.actor), route_id=route.id)]


def repair_bridge_check(world: WorldState, a: ProposedAction) -> str | None:
    if not (_has(world, a.actor, Ability.REPAIR) and _has(world, a.actor, Ability.BUILD_BRIDGE)):
        return f"{world.name(a.actor)} cannot repair a bridge."
    if reason := _need_at(world, a.actor, BRIDGE):
        return reason
    bridge = world.routes[MAIN_BRIDGE]
    if bridge.status is not RouteStatus.BROKEN:
        return "The Main Bridge is not broken."
    if bridge.obstructed:
        return "Debris blocks the Main Bridge; it must be cleared before repairs."
    return _need_items(world, a.actor, TIMBER, TOOLKIT)


def repair_bridge_apply(world: WorldState, a: ProposedAction) -> list[WorldEvent]:
    _consume(world, TIMBER)
    world.routes[MAIN_BRIDGE].status = RouteStatus.OPEN
    return [world.record(EventKind.BRIDGE_REPAIRED, f"{world.name(a.actor)} lashes new planks across the gap. The Main Bridge is open.",
                         actor=a.actor, location_id=BRIDGE, route_id=MAIN_BRIDGE)]


def block_route_check(world: WorldState, a: ProposedAction) -> str | None:
    route, reason = _route_here(world, a.actor, a)
    if route is None:
        return reason
    if not route.blockable:
        return f"The {route.name} cannot be blocked."
    if route.obstructed:
        return f"The {route.name} is already blocked."
    if not world.profiles[a.actor].can_carry_heavy:
        return f"{world.name(a.actor)} is not strong enough to pile up a barricade."
    return None


def block_route_apply(world: WorldState, a: ProposedAction) -> list[WorldEvent]:
    route = world.routes[a.route_id or ""]
    route.obstructed = True
    route.blocked_by = a.actor
    return [world.record(EventKind.ROUTE_BLOCKED, f"{world.name(a.actor)} blocks the {route.name} with fallen rocks and timber.",
                         actor=a.actor, location_id=_here(world, a.actor), route_id=route.id)]


def clear_route_check(world: WorldState, a: ProposedAction) -> str | None:
    route, reason = _route_here(world, a.actor, a)
    if route is None:
        return reason
    if not route.obstructed:
        return f"The {route.name} is not blocked."
    if not world.profiles[a.actor].can_carry_heavy:
        return f"{world.name(a.actor)} is not strong enough to clear the debris."
    return None


def clear_route_apply(world: WorldState, a: ProposedAction) -> list[WorldEvent]:
    route = world.routes[a.route_id or ""]
    route.obstructed = False
    route.blocked_by = None
    return [world.record(EventKind.ROUTE_CLEARED, f"{world.name(a.actor)} clears the debris from the {route.name}.",
                         actor=a.actor, location_id=_here(world, a.actor), route_id=route.id)]


# --- Obstacle C: temple mechanism -------------------------------------------------------

def repair_mechanism_check(world: WorldState, a: ProposedAction) -> str | None:
    if not _has(world, a.actor, Ability.REPAIR):
        return f"{world.name(a.actor)} cannot repair machinery."
    if reason := _need_at(world, a.actor, TEMPLE):
        return reason
    if world.temple_lock.mechanism_repaired:
        return "The temple mechanism is already repaired."
    return _need_items(world, a.actor, GEAR, TOOLKIT)


def repair_mechanism_apply(world: WorldState, a: ProposedAction) -> list[WorldEvent]:
    _consume(world, GEAR)
    world.temple_lock.mechanism_repaired = True
    return [world.record(EventKind.MECHANISM_REPAIRED, f"{world.name(a.actor)} fits the brass gear. The temple mechanism turns freely.",
                         actor=a.actor, location_id=TEMPLE)]


def decode_symbols_check(world: WorldState, a: ProposedAction) -> str | None:
    if not (_has(world, a.actor, Ability.DECODE_SYMBOLS) or _has(world, a.actor, Ability.INSPECT_CLUES)):
        return f"{world.name(a.actor)} cannot read the temple symbols."
    if reason := _need_at(world, a.actor, TEMPLE):
        return reason
    if world.temple_lock.symbols_decoded:
        return "The symbols are already set."
    return None


def decode_symbols_seconds(world: WorldState, a: ProposedAction) -> int:
    return 20 if _has(world, a.actor, Ability.DECODE_SYMBOLS) else 45


def decode_symbols_apply(world: WorldState, a: ProposedAction) -> list[WorldEvent]:
    world.temple_lock.symbols_decoded = True
    return [world.record(EventKind.SYMBOLS_DECODED, f"{world.name(a.actor)} turns the symbol dials to the sun sequence.",
                         actor=a.actor, location_id=TEMPLE)]


def pull_lever_check(world: WorldState, a: ProposedAction) -> str | None:
    if not (_has(world, a.actor, Ability.CLIMB) or _has(world, a.actor, Ability.OPERATE_MECHANISM)):
        return f"{world.name(a.actor)} cannot reach or rig the elevated lever."
    if reason := _need_at(world, a.actor, TEMPLE):
        return reason
    lock = world.temple_lock
    if lock.gate_open:
        return "The temple gate is already open."
    missing = []
    if not lock.mechanism_repaired:
        missing.append("the mechanism is broken")
    if not lock.symbols_decoded:
        missing.append("the symbols are not set")
    if missing:
        return f"The lever will not budge: {' and '.join(missing)}."
    return None


def pull_lever_seconds(world: WorldState, a: ProposedAction) -> int:
    return 10 if _has(world, a.actor, Ability.CLIMB) else 40


def pull_lever_apply(world: WorldState, a: ProposedAction) -> list[WorldEvent]:
    now = world.clock.now
    world.temple_lock.gate_open = True
    world.routes[TEMPLE_GATE].status = RouteStatus.OPEN
    world.flood.started_at = now
    world.flood.floods_at = now + FLOOD_SECONDS
    world.scheduled.append(ScheduledEffect(time=now + FLOOD_WARNING_SECONDS, kind=FLOOD_WARNING))
    world.scheduled.append(ScheduledEffect(time=now + FLOOD_SECONDS, kind=CHAMBER_FLOODS))
    return [world.record(
        EventKind.GATE_OPENED,
        f"{world.name(a.actor)} pulls the lever. The Temple Gate grinds open — and water begins pouring "
        f"into the chamber. It will flood in {FLOOD_SECONDS}s.",
        actor=a.actor, location_id=TEMPLE, floods_at=now + FLOOD_SECONDS,
    )]


# --- Obstacle D: flood (timed world effects) --------------------------------------------

def apply_scheduled(world: WorldState, effect: ScheduledEffect) -> list[WorldEvent]:
    if effect.kind == FLOOD_WARNING:
        return [world.record(EventKind.FLOOD_WARNING, "Water in the Flooded Chamber is waist-deep and rising fast.",
                             location_id=CHAMBER)]
    if effect.kind == CHAMBER_FLOODS:
        world.flood.flooded = True
        world.routes[TEMPLE_GATE].status = RouteStatus.FLOODED
        crystal = world.objects.get(SUN_CRYSTAL)
        lost = crystal is not None and crystal.location_id == CHAMBER
        trapped = [world.name(c) for c in world.characters_at(CHAMBER)]
        text = "The Flooded Chamber fills completely; the Temple Gate is under water."
        if lost:
            text += " The Sun Crystal is lost beneath the water."
        if trapped:
            text += f" Trapped inside: {', '.join(trapped)}."
        return [world.record(EventKind.CHAMBER_FLOODED, text, location_id=CHAMBER,
                             crystal_lost=lost, trapped=world.characters_at(CHAMBER))]
    raise ValueError(f"unknown scheduled effect {effect.kind}")


# --- Obstacle E: lighthouse ---------------------------------------------------------------

def repair_lighthouse_check(world: WorldState, a: ProposedAction) -> str | None:
    if not _has(world, a.actor, Ability.REPAIR):
        return f"{world.name(a.actor)} cannot repair the lighthouse mechanism."
    if reason := _need_at(world, a.actor, LIGHTHOUSE):
        return reason
    if world.lighthouse.operational:
        return "The lighthouse mechanism already works."
    return _need_items(world, a.actor, TOOLKIT)


def repair_lighthouse_apply(world: WorldState, a: ProposedAction) -> list[WorldEvent]:
    world.lighthouse.operational = True
    return [world.record(EventKind.LIGHTHOUSE_REPAIRED, f"{world.name(a.actor)} realigns the lens gears. The lighthouse mechanism is ready.",
                         actor=a.actor, location_id=LIGHTHOUSE)]


def install_crystal_check(world: WorldState, a: ProposedAction) -> str | None:
    if reason := _need_at(world, a.actor, LIGHTHOUSE):
        return reason
    if world.lighthouse.crystal_installed:
        return "The Sun Crystal is already installed."
    return _need_items(world, a.actor, SUN_CRYSTAL)


def install_crystal_apply(world: WorldState, a: ProposedAction) -> list[WorldEvent]:
    crystal = world.objects[SUN_CRYSTAL]
    crystal.carried_by = None
    crystal.location_id = LIGHTHOUSE
    crystal.portable = False
    world.lighthouse.crystal_installed = True
    return [world.record(EventKind.CRYSTAL_INSTALLED, f"{world.name(a.actor)} sets the Sun Crystal into the lighthouse socket.",
                         actor=a.actor, location_id=LIGHTHOUSE)]


def activate_lighthouse_check(world: WorldState, a: ProposedAction) -> str | None:
    if reason := _need_at(world, a.actor, LIGHTHOUSE):
        return reason
    lh = world.lighthouse
    if lh.activated:
        return "The lighthouse is already lit."
    missing = []
    if not lh.crystal_installed:
        missing.append("the Sun Crystal is not installed")
    if not lh.operational:
        missing.append("the mechanism is not repaired")
    if missing:
        return f"The lighthouse cannot be activated: {' and '.join(missing)}."
    return None


def activate_lighthouse_apply(world: WorldState, a: ProposedAction) -> list[WorldEvent]:
    world.lighthouse.activated = True
    world.lighthouse.activated_at = world.clock.now
    return [world.record(EventKind.LIGHTHOUSE_ACTIVATED,
                         f"{world.name(a.actor)} throws the final switch. The Sun Crystal blazes and the barrier rises over Aether.",
                         actor=a.actor, location_id=LIGHTHOUSE)]
