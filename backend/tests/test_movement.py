import pytest

from app.engine.aether import ARIA, BRIDGE, FOREST, HARBOUR, KABIR, LIGHTHOUSE, MEERA, TEMPLE
from app.engine.invariants import check_invariants
from app.engine.movement import find_path, start_travel, travel_progress, travel_seconds
from app.engine.timeline import advance_clock
from app.models.enums import EventKind, RouteStatus


def test_speed_changes_travel_time(world):
    road = world.routes["coast_road"]  # 35s base
    assert travel_seconds(world, ARIA, road) == 28   # ceil(35 / 1.25)
    assert travel_seconds(world, MEERA, road) == 35
    assert travel_seconds(world, KABIR, road) == 44  # ceil(35 / 0.8)


def test_travel_completes_when_clock_reaches_arrival(world):
    result = start_travel(world, KABIR, BRIDGE)
    assert result.ok
    state = world.characters[KABIR]
    assert state.location_id is None and state.travel.arrive_at == 44

    assert advance_clock(world, 30) == []
    assert travel_progress(world, KABIR) == pytest.approx(30 / 44)
    assert check_invariants(world) == []

    events = advance_clock(world, 30)
    assert [e.kind for e in events] == [EventKind.ARRIVED]
    assert events[0].time == 44  # stamped at the real arrival time, not the tick boundary
    assert state.location_id == BRIDGE and world.clock.now == 60
    assert check_invariants(world) == []


def test_arrivals_are_processed_in_time_order(world):
    start_travel(world, KABIR, BRIDGE)  # 44s
    start_travel(world, ARIA, BRIDGE)   # 28s
    start_travel(world, MEERA, BRIDGE)  # 35s
    events = advance_clock(world, 100)
    assert [(e.actor, e.time) for e in events] == [(ARIA, 28), (MEERA, 35), (KABIR, 44)]
    assert check_invariants(world) == []


def test_no_teleporting_to_non_adjacent_location(world):
    result = start_travel(world, ARIA, TEMPLE)
    assert not result.ok and "No route" in result.message
    assert world.characters[ARIA].location_id == HARBOUR


def test_cannot_start_a_second_journey_mid_travel(world):
    start_travel(world, ARIA, BRIDGE)
    result = start_travel(world, ARIA, FOREST)
    assert not result.ok and "already travelling" in result.message


def test_broken_bridge_blocks_kabir_and_meera(world):
    for cid in (KABIR, MEERA):
        world.characters[cid].location_id = BRIDGE
        result = start_travel(world, cid, TEMPLE)
        assert not result.ok
        assert "broken" in result.message and "climb" in result.message


def test_only_aria_can_take_the_ravine_climb(world):
    world.characters[ARIA].location_id = BRIDGE
    result = start_travel(world, ARIA, TEMPLE)
    assert result.ok
    assert world.characters[ARIA].travel.route_id == "ravine_climb"


def test_hidden_trail_unusable_until_discovered(world):
    world.characters[MEERA].location_id = FOREST
    assert not start_travel(world, MEERA, TEMPLE).ok
    world.routes["forest_trail"].hidden = False
    assert start_travel(world, MEERA, TEMPLE).ok


def test_blocked_route_rejects_travel(world):
    world.routes["cliff_stairs"].obstructed = True
    world.routes["cliff_stairs"].blocked_by = ARIA
    result = start_travel(world, MEERA, LIGHTHOUSE)
    assert not result.ok and "blocked" in result.message


def test_unknown_ids_are_rejected(world):
    assert not start_travel(world, "ghost", BRIDGE).ok
    assert not start_travel(world, ARIA, "atlantis").ok


def test_clock_cannot_run_backwards(world):
    with pytest.raises(ValueError):
        advance_clock(world, -1)


def test_pathfinding_respects_obstacles_and_abilities(world):
    # Aria can climb the ravine; nobody else has a way to the temple at the start.
    assert [r.id for r in find_path(world, ARIA, HARBOUR, TEMPLE)] == ["coast_road", "ravine_climb"]
    assert find_path(world, KABIR, HARBOUR, TEMPLE) is None
    assert find_path(world, MEERA, HARBOUR, TEMPLE) is None

    world.routes["forest_trail"].hidden = False
    assert [r.id for r in find_path(world, KABIR, HARBOUR, TEMPLE)] == ["forest_path", "forest_trail"]

    world.routes["main_bridge"].status = RouteStatus.OPEN
    assert [r.id for r in find_path(world, KABIR, HARBOUR, TEMPLE)] == ["coast_road", "main_bridge"]


def test_path_to_self_is_empty(world):
    assert find_path(world, ARIA, HARBOUR, HARBOUR) == []
