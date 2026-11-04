"""Consistency checks over a WorldState. An empty list means the world is valid.

Used by tests now and as a guard after every state transition later.
"""

from app.engine.aether import LIGHTHOUSE, SUN_CRYSTAL
from app.models.enums import RouteStatus
from app.models.world import WorldState


def check_invariants(world: WorldState) -> list[str]:
    problems: list[str] = []

    for route in world.routes.values():
        for end in (route.a, route.b):
            if end not in world.locations:
                problems.append(f"route {route.id} references unknown location {end}")

    crystals = [o for o in world.objects.values() if o.kind == SUN_CRYSTAL]
    if len(crystals) != 1:
        problems.append(f"expected exactly one Sun Crystal, found {len(crystals)}")

    for obj in world.objects.values():
        if obj.location_id is not None and obj.location_id not in world.locations:
            problems.append(f"object {obj.id} is at unknown location {obj.location_id}")
        if obj.carried_by is not None and obj.carried_by not in world.characters:
            problems.append(f"object {obj.id} is carried by unknown character {obj.carried_by}")

    for cid, state in world.characters.items():
        if cid not in world.profiles:
            problems.append(f"character {cid} has no profile")
            continue
        if state.location_id is not None and state.location_id not in world.locations:
            problems.append(f"character {cid} is at unknown location {state.location_id}")
        if state.travel is not None:
            t = state.travel
            route = world.routes.get(t.route_id)
            if route is None or {route.a, route.b} != {t.from_location, t.to_location}:
                problems.append(f"character {cid} is travelling on an inconsistent route {t.route_id}")
            if not t.depart_at <= world.clock.now < t.arrive_at:
                problems.append(f"character {cid} travel window does not contain the current time")
        if state.activity is not None and not state.activity.started_at <= world.clock.now < state.activity.completes_at:
            problems.append(f"character {cid} activity window does not contain the current time")
        carried = len(world.inventory(cid))
        if carried > world.profiles[cid].carry_capacity:
            problems.append(f"character {cid} carries {carried} items, over capacity")

    for route in world.routes.values():
        if route.obstructed != (route.blocked_by is not None):
            problems.append(f"route {route.id} obstruction and blocked_by disagree")

    gate = world.routes.get("temple_gate")
    if gate is not None:
        if world.temple_lock.gate_open and gate.status is RouteStatus.LOCKED:
            problems.append("temple gate is open but its route is still locked")
        if world.flood.flooded != (gate.status is RouteStatus.FLOODED):
            problems.append("flood state and temple gate route disagree")

    lh = world.lighthouse
    crystal = crystals[0] if len(crystals) == 1 else None
    if lh.crystal_installed and (crystal is None or crystal.location_id != LIGHTHOUSE):
        problems.append("lighthouse reports the crystal installed but it is not there")
    if lh.activated and not (lh.crystal_installed and lh.operational):
        problems.append("lighthouse is activated without crystal and working mechanism")

    for effect in world.scheduled:
        if effect.time < world.clock.now:
            problems.append(f"scheduled effect {effect.kind} is overdue")

    last_seq, last_time = 0, 0
    for event in world.events:
        if event.seq <= last_seq:
            problems.append(f"event sequence not increasing at seq {event.seq}")
        if event.time < last_time:
            problems.append(f"event time goes backwards at seq {event.seq}")
        if event.time > world.clock.now:
            problems.append(f"event {event.seq} is in the future")
        last_seq, last_time = event.seq, event.time

    return problems
