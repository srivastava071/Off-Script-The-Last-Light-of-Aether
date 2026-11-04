import pytest
from pydantic import ValidationError

from app.engine.aether import (
    ARIA, BRIDGE, CHAMBER, HARBOUR, KABIR, LIGHTHOUSE, MEERA, SUN_CRYSTAL, build_initial_world,
)
from app.engine.invariants import check_invariants
from app.models.enums import GameMode, RouteStatus
from app.models.world import WorldObject


def test_initial_world_is_valid(world):
    assert check_invariants(world) == []
    assert set(world.characters) == {ARIA, KABIR, MEERA}
    assert all(c.location_id == HARBOUR for c in world.characters.values())
    assert world.objects[SUN_CRYSTAL].location_id == CHAMBER
    assert world.clock.now == 0 and world.clock.deadline == 600


def test_every_location_is_connected_on_the_map(world):
    seen, stack = {HARBOUR}, [HARBOUR]
    while stack:
        here = stack.pop()
        for route in world.routes_from(here):
            there = route.other_end(here)
            if there not in seen:
                seen.add(there)
                stack.append(there)
    assert seen == set(world.locations)


def test_initial_obstacles(world):
    assert world.routes["main_bridge"].status is RouteStatus.BROKEN
    assert world.routes["temple_gate"].status is RouteStatus.LOCKED
    assert world.routes["forest_trail"].hidden


def test_runs_do_not_share_state():
    a = build_initial_world("a", GameMode.GAME)
    b = build_initial_world("b", GameMode.GAME)
    a.routes["main_bridge"].status = RouteStatus.OPEN
    a.characters[ARIA].location_id = BRIDGE
    assert b.routes["main_bridge"].status is RouteStatus.BROKEN
    assert b.characters[ARIA].location_id == HARBOUR


def test_object_needs_exactly_one_holder():
    with pytest.raises(ValidationError):
        WorldObject(id="x", kind="k", name="X")
    with pytest.raises(ValidationError):
        WorldObject(id="x", kind="k", name="X", location_id=HARBOUR, carried_by=ARIA)


def test_invariants_detect_a_duplicate_crystal(world):
    world.objects["fake"] = WorldObject(id="fake", kind=SUN_CRYSTAL, name="Sun Crystal", location_id=LIGHTHOUSE)
    assert any("exactly one Sun Crystal" in p for p in check_invariants(world))


def test_default_mode_has_no_deadline():
    assert build_initial_world("d", GameMode.DEFAULT).clock.deadline is None
