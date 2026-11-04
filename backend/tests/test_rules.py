from app.engine.aether import (
    ARIA, BRIDGE, CHAMBER, FLOOD_SECONDS, FOREST, HARBOUR, KABIR, LIGHTHOUSE, MEERA, SUN_CRYSTAL, TEMPLE,
    build_initial_world,
)
from app.engine.invariants import check_invariants
from app.engine.rules import RULES, available_actions
from app.engine.timeline import advance_clock
from app.models.enums import ActionType, EventKind, GameMode, RouteStatus
from tests.helpers import act, do, settle, walk

A = ActionType


def place(world, location, *actors):
    for a in actors:
        world.characters[a].location_id = location


def give_kabir_supplies(world):
    for obj in ("timber_planks", "brass_gear"):
        world.objects[obj].location_id = None
        world.objects[obj].carried_by = KABIR


# --- timing and spam protection -------------------------------------------------------------

def test_every_action_type_has_defined_timing():
    assert set(RULES) | {A.MOVE} == set(ActionType)


def test_busy_character_cannot_act_again_until_time_passes(world):
    do(world, ARIA, A.PICK_UP, object_id="brass_gear")
    second = act(world, ARIA, A.DROP, object_id="brass_gear")
    assert not second.ok and "busy" in second.message
    advance_clock(world, 5)
    assert act(world, ARIA, A.DROP, object_id="brass_gear").ok


def test_wait_duration_is_bounded():
    import pytest
    from pydantic import ValidationError
    from app.models.actions import ProposedAction
    with pytest.raises(ValidationError):
        ProposedAction(actor=ARIA, type=A.WAIT, seconds=100000)


def test_unknown_fields_in_actions_are_rejected():
    import pytest
    from pydantic import ValidationError
    from app.models.actions import ProposedAction
    with pytest.raises(ValidationError):
        ProposedAction(actor=ARIA, type=A.MOVE, destination=BRIDGE, teleport=True)


# --- Obstacle A: broken bridge ----------------------------------------------------------------

def test_kabir_repairs_bridge_with_materials(world):
    place(world, BRIDGE, KABIR)
    rejected = act(world, KABIR, A.REPAIR_BRIDGE)
    assert not rejected.ok and "Timber Planks" in rejected.message

    give_kabir_supplies(world)
    result = do(world, KABIR, A.REPAIR_BRIDGE)
    assert result.completes_at == 45
    advance_clock(world, 44)
    assert world.routes["main_bridge"].status is RouteStatus.BROKEN  # effect only on completion
    events = advance_clock(world, 1)
    assert [e.kind for e in events] == [EventKind.BRIDGE_REPAIRED]
    assert world.routes["main_bridge"].status is RouteStatus.OPEN
    assert "timber_planks" not in world.objects  # consumed, not duplicated
    assert check_invariants(world) == []


def test_aria_and_meera_cannot_repair_the_bridge(world):
    place(world, BRIDGE, ARIA, MEERA)
    for cid in (ARIA, MEERA):
        result = act(world, cid, A.REPAIR_BRIDGE)
        assert not result.ok and "cannot repair" in result.message


def test_repair_fails_if_bridge_is_blocked_mid_repair(world):
    place(world, BRIDGE, KABIR, ARIA)
    give_kabir_supplies(world)
    do(world, KABIR, A.REPAIR_BRIDGE)                        # completes t=45
    do(world, ARIA, A.BLOCK_ROUTE, route_id="main_bridge")   # completes t=20
    events = advance_clock(world, 60)
    kinds = [e.kind for e in events]
    assert kinds == [EventKind.ROUTE_BLOCKED, EventKind.ACTION_FAILED]
    assert "Debris" in events[-1].description
    assert world.routes["main_bridge"].status is RouteStatus.BROKEN
    assert world.carries(KABIR, "timber_planks")  # materials kept when repair fails


# --- blocking and clearing --------------------------------------------------------------------

def test_block_then_clear_route(world):
    do(world, ARIA, A.BLOCK_ROUTE, route_id="coast_road")
    advance_clock(world, 20)
    assert not act(world, MEERA, A.MOVE, destination=BRIDGE).ok
    do(world, KABIR, A.CLEAR_ROUTE, route_id="coast_road")
    advance_clock(world, 30)
    assert act(world, MEERA, A.MOVE, destination=BRIDGE).ok


def test_meera_is_too_light_to_block(world):
    result = act(world, MEERA, A.BLOCK_ROUTE, route_id="coast_road")
    assert not result.ok and "not strong enough" in result.message


def test_cannot_block_unblockable_or_remote_routes(world):
    place(world, BRIDGE, ARIA)
    assert "cannot be blocked" in act(world, ARIA, A.BLOCK_ROUTE, route_id="ravine_climb").message
    assert "not at either end" in act(world, ARIA, A.BLOCK_ROUTE, route_id="cliff_stairs").message


def test_route_in_progress_is_completed_even_if_blocked_behind(world):
    do(world, MEERA, A.MOVE, destination=BRIDGE)
    do(world, ARIA, A.BLOCK_ROUTE, route_id="coast_road")
    advance_clock(world, 40)
    assert world.characters[MEERA].location_id == BRIDGE


# --- Obstacle B: hidden trail and traps -------------------------------------------------------

def test_meera_discovers_hidden_trail(world):
    place(world, FOREST, MEERA)
    assert do(world, MEERA, A.DISCOVER_ROUTE).completes_at == 20
    advance_clock(world, 20)
    assert not world.routes["forest_trail"].hidden


def test_aria_discovers_more_slowly_and_kabir_cannot(world):
    place(world, FOREST, ARIA, KABIR)
    assert do(world, ARIA, A.DISCOVER_ROUTE).completes_at == 35
    assert not act(world, KABIR, A.DISCOVER_ROUTE).ok


def test_searching_where_nothing_is_hidden_costs_time_but_reveals_nothing(world):
    do(world, MEERA, A.DISCOVER_ROUTE)
    events = advance_clock(world, 20)
    assert "finds none" in events[-1].description
    assert world.routes["forest_trail"].hidden


def test_traps_slow_kabir_but_not_aria(world):
    world.routes["forest_trail"].hidden = False
    place(world, FOREST, ARIA, KABIR)
    aria = do(world, ARIA, A.MOVE, destination=TEMPLE).completes_at   # 70/1.25 = 56, climbs past traps
    kabir = do(world, KABIR, A.MOVE, destination=TEMPLE).completes_at  # ceil(70/0.8) = 88, +40 trap
    assert (aria, kabir) == (56, 128)
    events = advance_clock(world, 140)
    sprung = [e for e in events if e.kind is EventKind.TRAP_SPRUNG]
    assert [e.actor for e in sprung] == [KABIR]


def test_meera_marks_traps_so_nobody_is_slowed(world):
    world.routes["forest_trail"].hidden = False
    place(world, FOREST, MEERA, KABIR)
    do(world, MEERA, A.DETECT_TRAPS, route_id="forest_trail")
    advance_clock(world, 15)
    assert do(world, KABIR, A.MOVE, destination=TEMPLE).completes_at == 15 + 88


# --- Obstacle C: temple mechanism -------------------------------------------------------------

def test_lever_will_not_move_until_mechanism_and_symbols_are_ready(world):
    place(world, TEMPLE, ARIA)
    result = act(world, ARIA, A.PULL_LEVER)
    assert not result.ok
    assert "mechanism is broken" in result.message and "symbols are not set" in result.message


def test_temple_puzzle_needs_valid_roles(world):
    place(world, TEMPLE, ARIA, KABIR, MEERA)
    give_kabir_supplies(world)
    assert not act(world, ARIA, A.REPAIR_MECHANISM).ok
    assert not act(world, MEERA, A.REPAIR_MECHANISM).ok
    assert not act(world, KABIR, A.DECODE_SYMBOLS).ok
    assert not act(world, MEERA, A.PULL_LEVER).ok


def test_solving_the_temple_opens_gate_and_starts_flood(world):
    place(world, TEMPLE, ARIA, KABIR, MEERA)
    give_kabir_supplies(world)
    do(world, KABIR, A.REPAIR_MECHANISM)
    do(world, MEERA, A.DECODE_SYMBOLS)
    advance_clock(world, 30)
    do(world, ARIA, A.PULL_LEVER)
    advance_clock(world, 10)
    assert world.temple_lock.gate_open
    assert world.routes["temple_gate"].status is RouteStatus.OPEN
    assert world.flood.floods_at == 40 + FLOOD_SECONDS
    assert check_invariants(world) == []


def test_flood_seals_chamber_and_loses_crystal_if_left_behind(world):
    place(world, TEMPLE, ARIA)
    world.temple_lock.mechanism_repaired = world.temple_lock.symbols_decoded = True
    do(world, ARIA, A.PULL_LEVER)
    events = advance_clock(world, 10 + FLOOD_SECONDS)
    kinds = [e.kind for e in events]
    assert EventKind.FLOOD_WARNING in kinds and EventKind.CHAMBER_FLOODED in kinds
    flood_event = next(e for e in events if e.kind is EventKind.CHAMBER_FLOODED)
    assert flood_event.data["crystal_lost"] is True
    assert world.routes["temple_gate"].status is RouteStatus.FLOODED
    assert not act(world, ARIA, A.MOVE, destination=CHAMBER).ok
    assert check_invariants(world) == []


def test_character_inside_chamber_is_trapped_by_flood(world):
    place(world, TEMPLE, ARIA)
    world.temple_lock.mechanism_repaired = world.temple_lock.symbols_decoded = True
    do(world, ARIA, A.PULL_LEVER)
    settle(world, ARIA)
    walk(world, ARIA, CHAMBER)
    advance_clock(world, FLOOD_SECONDS)
    assert world.flood.flooded
    assert not act(world, ARIA, A.MOVE, destination=TEMPLE).ok


# --- Obstacle E: lighthouse -------------------------------------------------------------------

def test_reaching_lighthouse_without_crystal_cannot_activate(world):
    place(world, LIGHTHOUSE, KABIR)
    do(world, KABIR, A.REPAIR_LIGHTHOUSE)
    advance_clock(world, 30)
    result = act(world, KABIR, A.ACTIVATE_LIGHTHOUSE)
    assert not result.ok and "not installed" in result.message
    assert not world.lighthouse.activated


def test_installed_crystal_cannot_be_taken_again(world):
    place(world, LIGHTHOUSE, ARIA)
    world.objects[SUN_CRYSTAL].location_id = None
    world.objects[SUN_CRYSTAL].carried_by = ARIA
    do(world, ARIA, A.INSTALL_CRYSTAL)
    advance_clock(world, 10)
    assert world.lighthouse.crystal_installed
    assert not act(world, ARIA, A.PICK_UP, object_id=SUN_CRYSTAL).ok


# --- contextual action menu -------------------------------------------------------------------

def test_action_menu_matches_situation(world):
    opts = {o.label: o for o in available_actions(world, ARIA)}
    assert "Go to Broken Bridge via Coast Road" in opts
    assert "Pick up Brass Gear" in opts and opts["Pick up Brass Gear"].available
    assert not any("Hidden Forest Trail" in label for label in opts)  # never leak hidden routes
    assert not any("repair" in label.lower() for label in opts)

    place(world, BRIDGE, KABIR)
    repair = next(o for o in available_actions(world, KABIR) if o.action.type is A.REPAIR_BRIDGE)
    assert not repair.available and "Timber Planks" in repair.reason


def test_action_menu_is_empty_while_busy(world):
    do(world, ARIA, A.MOVE, destination=BRIDGE)
    assert available_actions(world, ARIA) == []


# --- full playthrough --------------------------------------------------------------------------

def _scripted_playthrough(world):
    do(world, KABIR, A.PICK_UP, object_id="timber_planks")
    settle(world, KABIR)
    do(world, KABIR, A.PICK_UP, object_id="brass_gear")
    settle(world, KABIR)
    for cid in (ARIA, KABIR, MEERA):
        walk(world, cid, BRIDGE)
    do(world, KABIR, A.REPAIR_BRIDGE)
    settle(world, KABIR)
    for cid in (ARIA, KABIR, MEERA):
        walk(world, cid, TEMPLE)
    do(world, KABIR, A.REPAIR_MECHANISM)
    do(world, MEERA, A.DECODE_SYMBOLS)
    settle(world, KABIR, MEERA)
    do(world, ARIA, A.PULL_LEVER)
    settle(world, ARIA)
    walk(world, ARIA, CHAMBER)
    do(world, ARIA, A.PICK_UP, object_id=SUN_CRYSTAL)
    settle(world, ARIA)
    walk(world, ARIA, TEMPLE)
    walk(world, KABIR, LIGHTHOUSE)
    do(world, KABIR, A.REPAIR_LIGHTHOUSE)
    settle(world, KABIR)
    walk(world, ARIA, LIGHTHOUSE)
    do(world, ARIA, A.INSTALL_CRYSTAL)
    settle(world, ARIA)
    do(world, ARIA, A.ACTIVATE_LIGHTHOUSE)
    settle(world, ARIA)


def test_full_mission_can_be_completed_through_the_rules(world):
    _scripted_playthrough(world)
    assert world.lighthouse.activated
    assert world.objects[SUN_CRYSTAL].location_id == LIGHTHOUSE
    assert not world.flood.flooded or world.objects[SUN_CRYSTAL].location_id != CHAMBER
    assert check_invariants(world) == []


def test_same_actions_give_identical_history():
    a = build_initial_world("r", GameMode.GAME)
    b = build_initial_world("r", GameMode.GAME)
    _scripted_playthrough(a)
    _scripted_playthrough(b)
    assert a.model_dump() == b.model_dump()


def test_crystal_cannot_be_taken_from_afar(world):
    assert world.characters[ARIA].location_id == HARBOUR
    assert not act(world, ARIA, A.PICK_UP, object_id=SUN_CRYSTAL).ok
