from app.engine.aether import ARIA, BRIDGE, CHAMBER, HARBOUR, KABIR, MEERA, SUN_CRYSTAL
from app.engine.invariants import check_invariants
from app.engine.movement import start_travel
from app.engine.objects import drop, give, pick_up


def test_pick_up_and_drop(world):
    assert pick_up(world, ARIA, "brass_gear").ok
    assert [o.id for o in world.inventory(ARIA)] == ["brass_gear"]
    assert drop(world, ARIA, "brass_gear").ok
    assert world.objects["brass_gear"].location_id == HARBOUR
    assert check_invariants(world) == []


def test_cannot_pick_up_object_elsewhere(world):
    result = pick_up(world, ARIA, SUN_CRYSTAL)
    assert not result.ok and "not here" in result.message


def test_meera_cannot_carry_heavy_timber(world):
    result = pick_up(world, MEERA, "timber_planks")
    assert not result.ok and "heavy" in result.message
    assert pick_up(world, KABIR, "timber_planks").ok


def test_crystal_cannot_be_held_twice(world):
    for cid in (ARIA, MEERA):
        world.characters[cid].location_id = CHAMBER
    assert pick_up(world, ARIA, SUN_CRYSTAL).ok
    second = pick_up(world, MEERA, SUN_CRYSTAL)
    assert not second.ok
    assert world.objects[SUN_CRYSTAL].carried_by == ARIA
    assert check_invariants(world) == []


def test_carry_capacity(world):
    world.objects["spare"] = world.objects["brass_gear"].model_copy(update={"id": "spare"})
    assert pick_up(world, ARIA, "brass_gear").ok
    assert pick_up(world, ARIA, "timber_planks").ok
    result = pick_up(world, ARIA, "spare")
    assert not result.ok and "capacity" in result.message


def test_give_requires_same_location(world):
    assert give(world, KABIR, ARIA, "toolkit").ok
    assert world.objects["toolkit"].carried_by == ARIA

    world.characters[KABIR].location_id = BRIDGE
    result = give(world, ARIA, KABIR, "toolkit")
    assert not result.ok and "same location" in result.message


def test_give_respects_receiver_limits(world):
    assert pick_up(world, KABIR, "timber_planks").ok
    result = give(world, KABIR, MEERA, "timber_planks")
    assert not result.ok and "heavy" in result.message
    assert world.objects["timber_planks"].carried_by == KABIR


def test_cannot_drop_what_you_do_not_carry(world):
    assert not drop(world, ARIA, "toolkit").ok


def test_no_item_actions_while_travelling(world):
    start_travel(world, ARIA, BRIDGE)
    assert not pick_up(world, ARIA, "brass_gear").ok
    assert not give(world, KABIR, ARIA, "toolkit").ok
