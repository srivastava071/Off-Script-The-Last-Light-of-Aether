"""Goal-directed planning from beliefs.

Each character's behaviour is an ordered list of rules. A rule looks at the character's
beliefs and offers zero or more Decisions. Reading the rules in order gives:
- the deterministic choice: the first option offered (used in mock mode, Default Mode, and
  whenever the LLM is unavailable, slow, or suggests something stale);
- a short list of valid alternatives, which an LLM may choose between (``options``).
Because every alternative comes from these rules, an LLM can pick a strategy but can never
invent an action; the rules engine still validates whatever is finally attempted.

Every rule works from that character's beliefs, so when the situation changes the strategies
change with it - e.g. Kabir compares "clear and repair the bridge" against "go round through
the forest" by estimated time, using only routes he knows about.
"""

from collections.abc import Callable
from typing import Protocol

from pydantic import BaseModel

from app.agents.view import BeliefView
from app.engine.aether import BRIDGE_REPAIR_SECONDS, CLEAR_ROUTE_SECONDS
from app.engine.ids import (
    ARIA, BRIDGE, CHAMBER, FOREST, FOREST_TRAIL, GEAR, KABIR, LIGHTHOUSE, MAIN_BRIDGE, MEERA, RAVINE_CLIMB,
    SUN_CRYSTAL, TEMPLE, TEMPLE_GATE, TIMBER, TOOLKIT,
)
from app.engine.knowledge import route_fact
from app.models.actions import ProposedAction
from app.models.enums import ActionType as A
from app.models.enums import RouteStatus
from app.models.world import Route, WorldState

GOAL_PREPARE = "Prepare tools and materials"
GOAL_REACH_TEMPLE = "Reach the Temple Entrance"
GOAL_REPAIR_MECH = "Repair the temple mechanism"
GOAL_OPEN_GATE = "Open the temple gate"
GOAL_SCOUT = "Find a safe route to the temple"
GOAL_REPORT = "Keep the team informed"
GOAL_DECODE = "Decode the temple symbols"
GOAL_RETRIEVE = "Retrieve the Sun Crystal"
GOAL_DELIVER = "Deliver the Sun Crystal to the Lighthouse"
GOAL_LIGHTHOUSE = "Make the lighthouse operational"
GOAL_ACTIVATE = "Light the beacon"
GOAL_SUPPORT = "Support the team"
GOAL_LOST = "Mission lost"

MAX_OPTIONS = 4


class Decision(BaseModel):
    strategy: str
    goal: str
    summary: str
    action: ProposedAction | None = None
    status: str = "pursuing"  # pursuing | waiting | blocked | failed
    source: str = "fallback"  # "fallback" or "llm" (an LLM preferred this option)


class Planner(Protocol):
    name: str

    def decide(self, world: WorldState, character_id: str, trigger: str | None) -> Decision: ...


Offer = Decision | list[Decision] | None
Rule = Callable[[BeliefView], Offer]


# --- helpers ------------------------------------------------------------------------------------

def _wait(v: BeliefView, strategy: str, goal: str, summary: str, status: str = "waiting") -> Decision:
    return Decision(strategy=strategy, goal=goal, summary=summary, status=status,
                    action=v.action(A.WAIT, seconds=10))


def _someone_else_doing(v: BeliefView, act: ProposedAction) -> bool:
    """Visible: another character at this location is already busy with the very same task."""
    key = (act.type, act.object_id, act.route_id)
    for cid in v.world.characters_at(v.here or ""):
        activity = v.world.characters[cid].activity
        if cid != v.cid and activity is not None:
            a = activity.action
            if (a.type, a.object_id, a.route_id) == key:
                return True
    return False


def _go_do(v: BeliefView, location: str, act: ProposedAction | None,
           strategy: str, goal: str, summary: str) -> Decision | None:
    """Do ``act`` at ``location``, walking there first along the believed fastest path."""
    if v.here == location:
        if act is None:
            return _wait(v, strategy, goal, summary)
        if _someone_else_doing(v, act):
            return _wait(v, strategy, goal, f"{summary} (a teammate is already on it)")
        return Decision(strategy=strategy, goal=goal, summary=summary, action=act)
    hop = v.next_hop(location)
    if hop is None:
        return None
    return Decision(strategy=strategy, goal=goal, summary=summary, action=hop)


def _route_strategy(path: list[Route]) -> str:
    ids = {r.id for r in path}
    if RAVINE_CLIMB in ids:
        return "climb_ravine"
    if FOREST_TRAIL in ids:
        return "route_via_forest"
    if MAIN_BRIDGE in ids:
        return "route_via_bridge"
    return "travel"


def _route_phrase(path: list[Route]) -> str:
    return " then ".join(f"the {r.name}" for r in path)


def _flood_safe(v: BeliefView) -> bool:
    flood = v.beliefs.flood
    if flood.flooded:
        return False
    if flood.floods_at is None:
        return True
    to_temple = 0 if v.here in (TEMPLE, CHAMBER) else v.eta(TEMPLE)
    if to_temple is None:
        return False
    return flood.floods_at - v.now > to_temple + 2 * v.route_time(TEMPLE_GATE) + 10


RECHECK_AFTER_SECONDS = 30  # how old a belief about a closed route must be before it is worth re-checking


def _recheck_route(v: BeliefView, goal: str) -> Decision | None:
    """With no known way to the temple, walk to a closed crossing seen a while ago: someone may have fixed it."""
    best: tuple[int, Decision] | None = None
    for route in sorted(v.world.routes.values(), key=lambda r: r.id):
        if not route.connects(TEMPLE):
            continue
        rb = v.route(route.id)
        near = route.other_end(TEMPLE)
        if not rb.known or (rb.status is RouteStatus.OPEN and not rb.obstructed) or near == v.here:
            continue
        if v.now - rb.as_of < RECHECK_AFTER_SECONDS:
            continue
        eta, hop = v.eta(near), v.next_hop(near)
        if eta is None or hop is None:
            continue
        d = Decision(strategy="recheck_route", goal=goal, action=hop,
                     summary=f"No news for a while: go and see whether the {route.name} is passable now.")
        if best is None or eta < best[0]:
            best = (eta, d)
    return best[1] if best else None


def _travel_to_temple(v: BeliefView, goal: str, purpose: str) -> Decision:
    path = v.path(TEMPLE)
    if path is None:
        return _recheck_route(v, goal) or _wait(
            v, "await_route", goal, "No known way to the temple yet; wait for news of another route.", status="blocked")
    hop = v.next_hop(TEMPLE)
    return Decision(strategy=_route_strategy(path), goal=goal, action=hop,
                    summary=f"Head to the temple via {_route_phrase(path)} to {purpose}.")


# --- shared rules ---------------------------------------------------------------------------------

def _mission_lost(v: BeliefView) -> Offer:
    if v.beliefs.flood.flooded and v.item(SUN_CRYSTAL).location_id == CHAMBER:
        return _wait(v, "mission_lost", GOAL_LOST, "The Sun Crystal is lost beneath the flood.", status="failed")
    return None


def _honour_request(v: BeliefView) -> Offer:
    """Help a teammate who asked (requests are accepted, kept and expired by the agent)."""
    if not v.mind.requests:
        return None
    req = v.mind.requests[0]
    who = v.world.name(req.from_id)
    goal = f"Help {who}"
    if req.action.type is A.MOVE:
        dest = req.action.destination or ""
        hop = v.next_hop(dest)
        if hop is None:
            return None
        return Decision(strategy="help_meet", goal=goal, action=hop,
                        summary=f"Meet {who} at the {v.world.locations[dest].name} as asked.")
    return Decision(strategy=f"help_{req.action.type.value}", goal=goal, action=req.action,
                    summary=f"Do what {who} asked: {req.action.type.value.replace('_', ' ')}.")


def _deliver(v: BeliefView) -> Offer:
    if not v.carrying(SUN_CRYSTAL):
        return None
    d = _go_do(v, LIGHTHOUSE, v.action(A.INSTALL_CRYSTAL), "deliver_crystal", GOAL_DELIVER,
               "Carry the Sun Crystal to the Lighthouse and install it.")
    return d or _wait(v, "hold_crystal", GOAL_DELIVER, "No known way to the Lighthouse; guard the crystal.", "blocked")


def _activate(v: BeliefView) -> Offer:
    lh = v.beliefs.lighthouse
    if lh.crystal_installed and lh.operational and not lh.activated:
        return _go_do(v, LIGHTHOUSE, v.action(A.ACTIVATE_LIGHTHOUSE), "light_beacon", GOAL_ACTIVATE,
                      "Everything is in place: activate the lighthouse.")
    return None


def _retrieve(v: BeliefView, strategy: str, summary: str) -> Decision | None:
    if not (v.beliefs.temple.gate_open and v.item(SUN_CRYSTAL).location_id == CHAMBER and _flood_safe(v)):
        return None
    return _go_do(v, CHAMBER, v.action(A.PICK_UP, object_id=SUN_CRYSTAL), strategy, GOAL_RETRIEVE, summary)


def _regroup(v: BeliefView) -> Offer:
    d = _go_do(v, LIGHTHOUSE, None, "regroup_at_lighthouse", GOAL_SUPPORT, "Regroup at the Lighthouse.")
    return d or _wait(v, "hold_position", GOAL_SUPPORT, "Hold position; no known way to the Lighthouse.")


UNIVERSAL: list[Rule] = [_mission_lost, _honour_request, _deliver, _activate]


# --- Kabir: the engineer --------------------------------------------------------------------------

def _kabir_gather(v: BeliefView) -> Offer:
    if v.beliefs.temple.mechanism_repaired:
        return None
    needs = []
    if not v.carrying(GEAR):
        needs.append(GEAR)
    if v.route(MAIN_BRIDGE).status is RouteStatus.BROKEN and not v.carrying(TIMBER) and v.path(TEMPLE) is None:
        needs.append(TIMBER)
    for item in needs:
        where = v.item(item).location_id
        if where is None:
            continue  # carried by someone else, used up, or whereabouts unknown
        name = v.world.objects[item].name if item in v.world.objects else item
        d = _go_do(v, where, v.action(A.PICK_UP, object_id=item), "gather_supplies", GOAL_PREPARE,
                   f"Collect the {name} before setting out.")
        if d:
            return d
    return None


def _kabir_repair_mechanism(v: BeliefView) -> Offer:
    if v.beliefs.temple.mechanism_repaired or v.here != TEMPLE:
        return None
    if v.carrying(GEAR) and v.carrying(TOOLKIT):
        return Decision(strategy="repair_mechanism", goal=GOAL_REPAIR_MECH, action=v.action(A.REPAIR_MECHANISM),
                        summary="Fit the brass gear into the temple lock.")
    return _wait(v, "missing_parts", GOAL_REPAIR_MECH, "Without the brass gear the lock cannot be repaired.",
                 status="blocked")


def _kabir_reach_temple(v: BeliefView) -> Offer:
    """All known ways to the temple, cheapest first."""
    if v.beliefs.temple.mechanism_repaired or v.here == TEMPLE:
        return None
    options: list[tuple[int, int, Decision]] = []
    if v.path(TEMPLE) is not None:
        options.append((v.eta(TEMPLE) or 0, 1, _travel_to_temple(v, GOAL_REACH_TEMPLE, "repair the lock")))

    bridge = v.route(MAIN_BRIDGE)
    if bridge.status is RouteStatus.BROKEN and v.carrying(TIMBER) and v.carrying(TOOLKIT):
        to_bridge = 0 if v.here == BRIDGE else v.eta(BRIDGE)
        if to_bridge is not None:
            cost = (to_bridge + (CLEAR_ROUTE_SECONDS if bridge.obstructed else 0) + BRIDGE_REPAIR_SECONDS
                    + v.route_time(MAIN_BRIDGE))
            if bridge.obstructed:
                d = _go_do(v, BRIDGE, v.action(A.CLEAR_ROUTE, route_id=MAIN_BRIDGE), "clear_and_repair_bridge",
                           GOAL_REACH_TEMPLE, "The Main Bridge is blocked: clear the debris, then repair it.")
            else:
                d = _go_do(v, BRIDGE, v.action(A.REPAIR_BRIDGE), "repair_bridge", GOAL_REACH_TEMPLE,
                           "Repair the Main Bridge with the salvaged timber.")
            if d:
                options.append((cost, 0, d))
    if not options:
        return _wait(v, "await_route", GOAL_REACH_TEMPLE,
                     "No known way to the temple and nothing to repair the bridge with; wait for news.",
                     status="blocked")
    return [d for _, _, d in sorted(options, key=lambda o: (o[0], o[1]))]


def _kabir_open_gate(v: BeliefView) -> Offer:
    lock = v.beliefs.temple
    if not lock.mechanism_repaired or lock.gate_open or v.here != TEMPLE or v.last_seen(ARIA) == TEMPLE:
        return None
    if lock.symbols_decoded:
        return Decision(strategy="operate_lever_myself", goal=GOAL_OPEN_GATE, action=v.action(A.PULL_LEVER),
                        summary="Aria is not here, so rig the elevated lever myself.")
    return _wait(v, "guard_temple", GOAL_OPEN_GATE,
                 "Stay at the temple until the symbols are set and someone can work the lever.")


def _kabir_fetch_crystal(v: BeliefView) -> Offer:
    if v.beliefs.temple.gate_open and v.last_seen(ARIA) not in (TEMPLE, CHAMBER):
        return _retrieve(v, "retrieve_crystal_for_aria", "Aria is not here; fetch the crystal before the flood.")
    return None


def _kabir_lighthouse(v: BeliefView) -> Offer:
    if v.beliefs.lighthouse.operational:
        return None
    d = _go_do(v, LIGHTHOUSE, v.action(A.REPAIR_LIGHTHOUSE), "secure_lighthouse", GOAL_LIGHTHOUSE,
               "Head back and repair the lighthouse mechanism.")
    return d or _wait(v, "await_route", GOAL_LIGHTHOUSE, "No known way back to the Lighthouse.", status="blocked")


KABIR_RULES: list[Rule] = [
    _kabir_gather, _kabir_repair_mechanism, _kabir_reach_temple, _kabir_open_gate, _kabir_fetch_crystal,
    _kabir_lighthouse,
]


# --- Meera: the scout ------------------------------------------------------------------------------

def _meera_unreported(v: BeliefView) -> str | None:
    for rid, rb in sorted(v.beliefs.routes.items()):
        if not rb.known:
            continue
        noteworthy = rid == FOREST_TRAIL or rb.obstructed or (rid == MAIN_BRIDGE and rb.status is RouteStatus.OPEN)
        fact = route_fact(v.world, rid, rb)
        if noteworthy and f"{rid}:{fact}" not in v.mind.signalled:
            return fact
    return None


def _meera_scout(v: BeliefView) -> Offer:
    if v.route(FOREST_TRAIL).known or FOREST in v.beliefs.searched or v.beliefs.temple.gate_open:
        return None
    return _go_do(v, FOREST, v.action(A.DISCOVER_ROUTE), "scout_forest_trail", GOAL_SCOUT,
                  "Search the Whispering Forest for the old trail to the temple.")


def _meera_traps(v: BeliefView) -> Offer:
    trail = v.route(FOREST_TRAIL)
    if trail.known and trail.hazard_active and v.here in (FOREST, TEMPLE):
        return Decision(strategy="clear_trail_traps", goal=GOAL_SCOUT,
                        action=v.action(A.DETECT_TRAPS, route_id=FOREST_TRAIL),
                        summary="Find and mark every snare on the forest trail.")
    return None


def _meera_report(v: BeliefView) -> Offer:
    if fact := _meera_unreported(v):
        return Decision(strategy="report_route", goal=GOAL_REPORT, action=v.action(A.SIGNAL, message=fact),
                        summary=f"Signal the team: {fact}.")
    return None


def _meera_decode(v: BeliefView) -> Offer:
    if v.beliefs.temple.symbols_decoded:
        return None
    if v.here == TEMPLE:
        if _someone_else_doing(v, v.action(A.DECODE_SYMBOLS)):
            return _wait(v, "decode_symbols", GOAL_DECODE, "A teammate is already decoding the symbols.")
        return Decision(strategy="decode_symbols", goal=GOAL_DECODE, action=v.action(A.DECODE_SYMBOLS),
                        summary="Read the carvings and set the symbol dials.")
    return _travel_to_temple(v, GOAL_DECODE, "decode the symbols")


def _meera_fetch_crystal(v: BeliefView) -> Offer:
    if v.beliefs.temple.gate_open and v.last_seen(ARIA) not in (TEMPLE, CHAMBER):
        return _retrieve(v, "retrieve_crystal_for_aria", "Aria is not here; fetch the crystal before the flood.")
    return None


MEERA_RULES: list[Rule] = [_meera_scout, _meera_traps, _meera_report, _meera_decode, _meera_fetch_crystal]


# --- Aria: the explorer ----------------------------------------------------------------------------

def _aria_retrieve(v: BeliefView) -> Offer:
    if v.beliefs.temple.gate_open:
        return _retrieve(v, "retrieve_crystal", "Dash into the chamber and grab the Sun Crystal before it floods.")
    return None


def _aria_at_temple(v: BeliefView) -> Offer:
    lock = v.beliefs.temple
    if lock.gate_open or v.here != TEMPLE:
        return None
    if lock.mechanism_repaired and lock.symbols_decoded:
        return Decision(strategy="open_temple_gate", goal=GOAL_OPEN_GATE, action=v.action(A.PULL_LEVER),
                        summary="Climb to the elevated lever and pull it.")
    wait = _wait(v, "wait_at_temple", GOAL_OPEN_GATE, "Wait at the temple for the lock to be repaired and decoded.")
    if lock.symbols_decoded or _someone_else_doing(v, v.action(A.DECODE_SYMBOLS)):
        return wait
    decode = Decision(strategy="decode_symbols_myself", goal=GOAL_OPEN_GATE, action=v.action(A.DECODE_SYMBOLS),
                      summary="Meera is not here; puzzle out the symbols myself.")
    # Decoding herself is the default only when it is the last thing missing and Meera is away.
    if lock.mechanism_repaired and v.last_seen(MEERA) != TEMPLE:
        return [decode, wait]
    return [wait, decode]


def _aria_to_temple(v: BeliefView) -> Offer:
    if v.beliefs.temple.gate_open or v.here == TEMPLE:
        return None
    return _travel_to_temple(v, GOAL_REACH_TEMPLE, "open the gate")


ARIA_RULES: list[Rule] = [_aria_retrieve, _aria_at_temple, _aria_to_temple]

ROLE_RULES: dict[str, list[Rule]] = {ARIA: ARIA_RULES, KABIR: KABIR_RULES, MEERA: MEERA_RULES}


# --- planner ------------------------------------------------------------------------------------------

def _offers(offer: Offer) -> list[Decision]:
    if offer is None:
        return []
    return offer if isinstance(offer, list) else [offer]


class FallbackPlanner:
    """Deterministic, rule-based planner over beliefs. Never calls a model.

    If the character's mind holds a still-valid strategy preference (set from an LLM
    deliberation), the matching option is chosen instead of the first one.
    """

    name = "fallback"

    def options(self, world: WorldState, character_id: str, limit: int = MAX_OPTIONS) -> list[Decision]:
        v = BeliefView(world, character_id)
        rules = [*UNIVERSAL, *ROLE_RULES.get(character_id, []), _regroup]
        seen: set[str] = set()
        out: list[Decision] = []
        for rule in rules:
            for d in _offers(rule(v)):
                if d.strategy not in seen:
                    seen.add(d.strategy)
                    out.append(d)
                    if len(out) >= limit:
                        return out
        return out

    def decide(self, world: WorldState, character_id: str, trigger: str | None) -> Decision:
        options = self.options(world, character_id)
        mind = world.minds[character_id]
        preferred = mind.preferred_strategy
        if preferred and (mind.preference_expires_at is None or world.clock.now < mind.preference_expires_at):
            for d in options:
                if d.strategy == preferred:
                    return d.model_copy(update={"source": "llm"})
        return options[0]
