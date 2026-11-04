"""Initial world for "The Last Light of Aether". Pure data: every run starts from build_initial_world()."""

from app.engine.ids import (  # noqa: F401  (re-exported for convenience)
    ARIA, BRIDGE, CHAMBER, FOREST, GEAR, HARBOUR, KABIR, LIGHTHOUSE, MEERA, SUN_CRYSTAL, TEMPLE, TIMBER, TOOLKIT,
)
from app.engine.knowledge import init_minds
from app.models.enums import Ability, GameMode, RouteStatus
from app.models.story import Objective, StoryBeat, StoryState
from app.models.world import (
    CharacterProfile,
    CharacterState,
    Location,
    Route,
    SimulationClock,
    WorldObject,
    WorldState,
)

LOCATIONS = [
    Location(id=HARBOUR, name="Abandoned Harbour", x=190, y=580,
             description="Rotting piers and a wrecked supply ship. The team lands here."),
    Location(id=LIGHTHOUSE, name="Lighthouse", x=130, y=170,
             description="The dark lighthouse on the northern cliff, its crystal socket empty."),
    Location(id=BRIDGE, name="Broken Bridge", x=470, y=520,
             description="A rope-and-plank bridge over a deep ravine, its middle span torn away."),
    Location(id=FOREST, name="Whispering Forest", x=450, y=210,
             description="Dense, murmuring woods. Old hunters' traps lie beneath the leaves."),
    Location(id=TEMPLE, name="Temple Entrance", x=740, y=380,
             description="A carved stone doorway sealed by a mechanical lock of gears and symbols."),
    Location(id=CHAMBER, name="Flooded Chamber", x=880, y=170,
             description="A sunken hall where rising water surrounds the crystal's pedestal."),
]

ROUTES = [
    Route(id="cliff_stairs", name="Cliff Stairs", a=HARBOUR, b=LIGHTHOUSE, base_seconds=40),
    Route(id="coast_road", name="Coast Road", a=HARBOUR, b=BRIDGE, base_seconds=35),
    Route(id="main_bridge", name="Main Bridge", a=BRIDGE, b=TEMPLE, base_seconds=30,
          status=RouteStatus.BROKEN),
    Route(id="ravine_climb", name="Ravine Climb", a=BRIDGE, b=TEMPLE, base_seconds=50,
          requires_ability=Ability.CLIMB, blockable=False),
    Route(id="forest_path", name="Forest Path", a=HARBOUR, b=FOREST, base_seconds=40),
    Route(id="forest_trail", name="Hidden Forest Trail", a=FOREST, b=TEMPLE, base_seconds=70,
          hidden=True, hazard="traps", hazard_active=True, hazard_bypass=Ability.CLIMB,
          hazard_penalty_seconds=40),
    Route(id="temple_gate", name="Temple Gate", a=TEMPLE, b=CHAMBER, base_seconds=20,
          status=RouteStatus.LOCKED, blockable=False),
]

# Obstacle timings (simulated seconds). Tuned so the undisturbed story takes about five minutes.
BRIDGE_REPAIR_SECONDS = 45
CLEAR_ROUTE_SECONDS = 30
BLOCK_ROUTE_SECONDS = 20
MECHANISM_REPAIR_SECONDS = 25
LIGHTHOUSE_REPAIR_SECONDS = 20
FLOOD_SECONDS = 120         # after the gate opens, the chamber floods and the gate becomes impassable
FLOOD_WARNING_SECONDS = 60  # warning issued this long after the gate opens

OBJECTS = [
    WorldObject(id=SUN_CRYSTAL, kind="sun_crystal", name="Sun Crystal", location_id=CHAMBER,
                description="The glowing heart of Aether's barrier."),
    WorldObject(id="timber_planks", kind="material", name="Timber Planks", heavy=True,
                location_id=HARBOUR, description="Salvaged ship timber, enough to patch a bridge span."),
    WorldObject(id="brass_gear", kind="component", name="Brass Gear", location_id=HARBOUR,
                description="A spare cog from the wrecked ship's winch."),
    WorldObject(id="toolkit", kind="tool", name="Engineer's Toolkit", carried_by=KABIR,
                description="Kabir's hammers, rope and fasteners."),
]

PROFILES = [
    CharacterProfile(
        id=ARIA, name="Aria", title="The Explorer", color="#f2a541",
        personality="Brave, curious, resourceful and occasionally impulsive.",
        primary_goal="Reach the temple, retrieve the Sun Crystal and help restore the island's barrier.",
        abilities=[Ability.CLIMB, Ability.JUMP_GAP, Ability.INSPECT_CLUES],
        restrictions=[
            "Cannot repair complex machinery.",
            "Cannot swim through deep-water hazards.",
            "Cannot break heavy barriers without a tool.",
        ],
        speed_multiplier=1.25, carry_capacity=2, can_carry_heavy=True,
    ),
    CharacterProfile(
        id=KABIR, name="Kabir", title="The Engineer", color="#4fa3d1",
        personality="Logical, patient, methodical and cautious.",
        primary_goal="Establish a viable route to the temple and ensure the Lighthouse can be activated.",
        abilities=[Ability.REPAIR, Ability.BUILD_BRIDGE, Ability.OPERATE_MECHANISM, Ability.DIAGNOSE],
        restrictions=[
            "Moves more slowly than Aria.",
            "Cannot jump wide gaps.",
            "Cannot perform repairs without the required resources.",
        ],
        speed_multiplier=0.8, carry_capacity=3, can_carry_heavy=True,
    ),
    CharacterProfile(
        id=MEERA, name="Meera", title="The Scout", color="#7bc67e",
        personality="Observant, intelligent, protective and tactically minded.",
        primary_goal="Find a safe route, identify hazards and help the team obtain the crystal.",
        abilities=[Ability.DETECT_TRAPS, Ability.DISCOVER_ROUTES, Ability.DISTRACT, Ability.DECODE_SYMBOLS,
                   Ability.SIGNAL],
        restrictions=[
            "Cannot repair machinery.",
            "Cannot carry heavy objects alone.",
            "Cannot defeat major creatures directly.",
        ],
        speed_multiplier=1.0, carry_capacity=2, can_carry_heavy=False,
    ),
]


STORY_BEATS = [
    ("landing", "The team lands at the Abandoned Harbour"),
    ("bridge_broken", "The Main Bridge is found broken"),
    ("way_across", "A way across the ravine is found"),
    ("temple_reached", "The team reaches the Temple Entrance"),
    ("puzzle_solved", "The temple mechanism is solved and the gate opens"),
    ("chamber_entered", "Someone wades into the Flooded Chamber"),
    ("crystal_retrieved", "The Sun Crystal is retrieved"),
    ("return_journey", "The Sun Crystal reaches the Lighthouse"),
    ("beacon_lit", "The beacon is lit"),
]

OBJ_MAIN = "restore_light"
OBJ_BRIDGE = "bridge_restored"
OBJ_TRAPS = "no_trap_injuries"
OBJ_LEFT_BEHIND = "nobody_left_behind"


def initial_objectives() -> list[Objective]:
    return [
        Objective(id=OBJ_MAIN, optional=False, title="Restore the light",
                  description="Retrieve the Sun Crystal, install it in the Lighthouse and activate it before the deadline."),
        Objective(id=OBJ_BRIDGE, optional=True, title="Secure the return route",
                  description="Leave the Main Bridge repaired for the islanders."),
        Objective(id=OBJ_TRAPS, optional=True, title="No one hurt by traps",
                  description="Cross the forest without springing a snare."),
        Objective(id=OBJ_LEFT_BEHIND, optional=True, title="Nobody left behind",
                  description="Nobody is trapped when the chamber floods."),
    ]


def build_initial_world(
    run_id: str,
    mode: GameMode,
    *,
    tick_seconds: int = 5,
    deadline_seconds: int | None = None,
) -> WorldState:
    """Return a fresh, independent copy of the starting world, with each character briefed."""
    world = WorldState(
        run_id=run_id,
        mode=mode,
        clock=SimulationClock(now=0, tick_seconds=tick_seconds, deadline=deadline_seconds),
        locations={loc.id: loc.model_copy(deep=True) for loc in LOCATIONS},
        routes={r.id: r.model_copy(deep=True) for r in ROUTES},
        objects={o.id: o.model_copy(deep=True) for o in OBJECTS},
        profiles={p.id: p.model_copy(deep=True) for p in PROFILES},
        characters={p.id: CharacterState(id=p.id, location_id=HARBOUR) for p in PROFILES},
    )
    world.story = StoryState(
        beats=[StoryBeat(id=b, title=t) for b, t in STORY_BEATS],
        objectives=initial_objectives(),
    )
    init_minds(world)
    return world
