"""Object transfers. Every transfer moves the single holder field, so items can never be duplicated.

Each action has a ``*_blocker`` (pure validation) and an applying function that re-validates.
"""

from app.models.actions import ActionResult
from app.models.enums import EventKind
from app.models.world import WorldState


def _carry_blocker(world: WorldState, character_id: str, object_id: str) -> str | None:
    profile = world.profiles[character_id]
    obj = world.objects[object_id]
    if not obj.portable:
        return f"{obj.name} cannot be carried."
    if obj.heavy and not profile.can_carry_heavy:
        return f"{profile.name} cannot carry the heavy {obj.name} alone."
    if len(world.inventory(character_id)) >= profile.carry_capacity:
        return f"{profile.name} cannot carry any more (capacity {profile.carry_capacity})."
    return None


def _stationary_blocker(world: WorldState, character_id: str) -> str | None:
    if character_id not in world.characters:
        return f"Unknown character '{character_id}'."
    if world.characters[character_id].travel is not None:
        return f"{world.name(character_id)} is travelling."
    return None


def pick_up_blocker(world: WorldState, character_id: str, object_id: str | None) -> str | None:
    if reason := _stationary_blocker(world, character_id):
        return reason
    if object_id is None or object_id not in world.objects:
        return f"Unknown object '{object_id}'."
    obj = world.objects[object_id]
    if obj.location_id != world.characters[character_id].location_id:
        return f"{obj.name} is not here."
    return _carry_blocker(world, character_id, object_id)


def drop_blocker(world: WorldState, character_id: str, object_id: str | None) -> str | None:
    if reason := _stationary_blocker(world, character_id):
        return reason
    if object_id is None or object_id not in world.objects:
        return f"Unknown object '{object_id}'."
    obj = world.objects[object_id]
    if obj.carried_by != character_id:
        return f"{world.name(character_id)} is not carrying the {obj.name}."
    return None


def give_blocker(world: WorldState, giver_id: str, receiver_id: str | None, object_id: str | None) -> str | None:
    if receiver_id is None:
        return "No receiver given."
    for cid in (giver_id, receiver_id):
        if reason := _stationary_blocker(world, cid):
            return reason
    if giver_id == receiver_id:
        return "A character cannot give an item to themselves."
    if object_id is None or object_id not in world.objects:
        return f"Unknown object '{object_id}'."
    obj = world.objects[object_id]
    if obj.carried_by != giver_id:
        return f"{world.name(giver_id)} is not carrying the {obj.name}."
    if world.characters[receiver_id].location_id != world.characters[giver_id].location_id:
        return f"{world.name(receiver_id)} is not at the same location as {world.name(giver_id)}."
    return _carry_blocker(world, receiver_id, object_id)


def pick_up(world: WorldState, character_id: str, object_id: str) -> ActionResult:
    if reason := pick_up_blocker(world, character_id, object_id):
        return ActionResult.reject(reason)
    obj = world.objects[object_id]
    here = world.characters[character_id].location_id
    name = world.name(character_id)
    obj.location_id = None
    obj.carried_by = character_id
    event = world.record(
        EventKind.ITEM_PICKED_UP, f"{name} picks up the {obj.name}.",
        actor=character_id, location_id=here, object_id=object_id,
    )
    return ActionResult.success(f"{name} now carries the {obj.name}.", event)


def drop(world: WorldState, character_id: str, object_id: str) -> ActionResult:
    if reason := drop_blocker(world, character_id, object_id):
        return ActionResult.reject(reason)
    obj = world.objects[object_id]
    here = world.characters[character_id].location_id
    assert here is not None
    name = world.name(character_id)
    obj.carried_by = None
    obj.location_id = here
    event = world.record(
        EventKind.ITEM_DROPPED, f"{name} puts down the {obj.name}.",
        actor=character_id, location_id=here, object_id=object_id,
    )
    return ActionResult.success(f"{name} left the {obj.name} at {world.locations[here].name}.", event)


def give(world: WorldState, giver_id: str, receiver_id: str, object_id: str) -> ActionResult:
    if reason := give_blocker(world, giver_id, receiver_id, object_id):
        return ActionResult.reject(reason)
    obj = world.objects[object_id]
    here = world.characters[giver_id].location_id
    giver, receiver = world.name(giver_id), world.name(receiver_id)
    obj.carried_by = receiver_id
    event = world.record(
        EventKind.ITEM_GIVEN, f"{giver} hands the {obj.name} to {receiver}.",
        actor=giver_id, location_id=here, object_id=object_id, receiver=receiver_id,
    )
    return ActionResult.success(f"{receiver} now carries the {obj.name}.", event)
