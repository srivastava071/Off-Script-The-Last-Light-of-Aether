"""Turning a player's typed or spoken instruction into validated orders.

Free text is never executed. It is mapped onto a small vocabulary - go to a place, do one of the
game's actions, wait, or resume your own plan - and every step is checked against the world:
known characters, places, items and visible routes only, and abilities the character really has.
An LLM does the mapping when available; a deterministic keyword parser is the fallback.
"""

import json
import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, ValidationError

from app.agents.prompts import JSON_OBJECT, THINK_BLOCK
from app.engine.rules import RULES, capability_blocker
from app.models.actions import ProposedAction
from app.models.enums import ActionType as A
from app.models.mind import Order
from app.models.world import WorldState

MAX_COMMAND_CHARS = 300
COMMANDABLE = [
    A.DISCOVER_ROUTE, A.DETECT_TRAPS, A.REPAIR_BRIDGE, A.BLOCK_ROUTE, A.CLEAR_ROUTE, A.REPAIR_MECHANISM,
    A.DECODE_SYMBOLS, A.PULL_LEVER, A.REPAIR_LIGHTHOUSE, A.INSTALL_CRYSTAL, A.ACTIVATE_LIGHTHOUSE, A.SIGNAL,
    A.PICK_UP, A.DROP, A.GIVE, A.INSPECT,
]


class Step(BaseModel):
    model_config = ConfigDict(extra="ignore")

    who: str
    kind: Literal["go_to", "do", "wait", "resume"]
    location: str | None = None
    action: str | None = None
    route: str | None = None
    object: str | None = None
    to: str | None = None
    seconds: int | None = None


class Interpretation(BaseModel):
    steps: list[Step] = []
    note: str | None = None


# --- vocabulary ------------------------------------------------------------------------------------

PLACE_WORDS = {
    "harbour": ["harbour", "harbor", "port", "dock", "pier", "ship", "start"],
    "bridge": ["broken bridge", "bridge"],
    "forest": ["whispering forest", "forest", "woods"],
    "temple": ["temple", "entrance", "gate"],
    "chamber": ["flooded chamber", "chamber", "pool"],
    "lighthouse": ["lighthouse", "beacon", "tower"],
}
OBJECT_WORDS = {
    "sun_crystal": ["crystal", "sun crystal"],
    "timber_planks": ["timber", "plank", "planks", "wood"],
    "brass_gear": ["gear", "cog", "brass"],
    "toolkit": ["toolkit", "tools", "tool kit"],
}
ROUTE_WORDS = {
    "main_bridge": ["main bridge", "bridge"],
    "coast_road": ["coast road", "coast", "road"],
    "cliff_stairs": ["cliff stairs", "stairs", "cliff"],
    "forest_path": ["forest path", "path"],
    "forest_trail": ["forest trail", "hidden trail", "trail"],
    "ravine_climb": ["ravine climb", "ravine", "climb"],
}
SELF_WORDS = ["i", "me", "myself", "i'll", "im", "i'm", "let me", "we", "us"]

ACTION_PATTERNS: list[tuple[A, list[str]]] = [
    (A.GIVE, ["give", "hand over", "hand me", "pass"]),
    (A.INSTALL_CRYSTAL, ["install", "place the crystal", "put the crystal", "set the crystal"]),
    (A.ACTIVATE_LIGHTHOUSE, ["activate", "light the", "turn on", "switch on", "light it", "light up"]),
    (A.REPAIR_BRIDGE, []),  # resolved from "repair/fix" + what
    (A.DECODE_SYMBOLS, ["decode", "symbol", "puzzle", "dials", "solve"]),
    (A.PULL_LEVER, ["lever", "pull", "open the gate", "open gate"]),
    (A.CLEAR_ROUTE, ["clear", "unblock", "remove the debris"]),
    (A.BLOCK_ROUTE, ["block", "barricade", "obstruct"]),
    (A.DETECT_TRAPS, ["trap", "snare", "disarm"]),
    (A.DISCOVER_ROUTE, ["search", "scout", "find", "look for", "explore", "discover"]),
    (A.SIGNAL, ["signal", "horn", "warn the team", "tell the team", "tell everyone"]),
    (A.PICK_UP, ["pick up", "pick", "take", "grab", "collect", "get the", "fetch", "carry"]),
    (A.DROP, ["drop", "put down", "leave the"]),
    (A.INSPECT, ["inspect", "look around", "check the area"]),
]
REPAIR_WORDS = ["repair", "fix", "mend", "rebuild", "restore"]
MOVE_WORDS = ["go", "move", "head", "run", "walk", "travel", "come", "meet", "return", "get to", "rush", "back to"]
RESUME_WORDS = ["carry on", "your own", "resume", "as you were", "never mind", "nevermind", "cancel", "forget it",
                "do your thing", "back to your plan"]
WAIT_WORDS = ["wait", "stay", "hold", "stop"]


def _has(text: str, words: list[str]) -> str | None:
    for w in sorted(words, key=len, reverse=True):
        if re.search(rf"(?<![a-z]){re.escape(w)}(?![a-z])", text):
            return w
    return None


def _find(text: str, table: dict[str, list[str]]) -> str | None:
    best: tuple[int, str] | None = None
    for key, words in table.items():
        for w in words:
            m = re.search(rf"(?<![a-z]){re.escape(w)}(?![a-z])", text)
            if m and (best is None or m.start() < best[0]):
                best = (m.start(), key)
    return best[1] if best else None


# --- deterministic fallback parser --------------------------------------------------------------------

def parse_fallback(world: WorldState, player: str, text: str) -> Interpretation:
    names = {p.name.lower(): cid for cid, p in world.profiles.items()}
    clauses = [c.strip() for c in re.split(r"[.;!?\n]|,|\bthen\b|\band\b|\balso\b", text.lower()) if c.strip()]
    who = player
    steps: list[Step] = []
    for clause in clauses:
        named = [cid for name, cid in names.items() if re.search(rf"\b{name}\b", clause)]
        if named:
            who = named[0]
        elif _has(clause, SELF_WORDS):
            who = player
        rest = clause
        for name in names:
            rest = re.sub(rf"\b{name}\b", "", rest)
        if not rest.strip(" ,"):
            continue  # just a name: "Kabir," addresses the next clauses

        if _has(rest, RESUME_WORDS):
            steps.append(Step(who=who, kind="resume"))
            continue
        place = _find(rest, PLACE_WORDS)
        obj = _find(rest, OBJECT_WORDS)
        route = _find(rest, ROUTE_WORDS)

        action: A | None = None
        if _has(rest, REPAIR_WORDS):
            if "lighthouse" in rest or "beacon" in rest or "lens" in rest:
                action = A.REPAIR_LIGHTHOUSE
            elif "bridge" in rest:
                action = A.REPAIR_BRIDGE
            elif any(w in rest for w in ("mechanism", "lock", "temple", "gear")):
                action = A.REPAIR_MECHANISM
        if action is None:
            for candidate, words in ACTION_PATTERNS:
                if words and _has(rest, words):
                    action = candidate
                    break
        if action is A.PICK_UP and obj is None:
            action = None  # "get to the temple" is movement, not picking something up

        if action is None:
            if _has(rest, WAIT_WORDS):
                secs = re.search(r"(\d+)\s*s", rest)
                steps.append(Step(who=who, kind="wait", seconds=int(secs.group(1)) if secs else 30))
            elif place:
                steps.append(Step(who=who, kind="go_to", location=place))
            continue

        if action is A.DISCOVER_ROUTE:
            if place and place != "temple":
                steps.append(Step(who=who, kind="go_to", location=place))
            elif "trail" in rest or "forest" in rest:
                steps.append(Step(who=who, kind="go_to", location="forest"))
            steps.append(Step(who=who, kind="do", action=action.value))
            continue
        if action in (A.BLOCK_ROUTE, A.CLEAR_ROUTE, A.DETECT_TRAPS):
            route = route or ("forest_trail" if action is A.DETECT_TRAPS else None)
        if action is A.GIVE:
            to_match = re.search(r"\bto\s+(\w+)", rest)
            target = None
            if to_match:
                word = to_match.group(1)
                target = names.get(word) or (player if word in SELF_WORDS else None)
            elif re.search(r"\b(me|us)\b", rest):
                target = player
            steps.append(Step(who=who, kind="do", action=action.value, object=obj, to=target))
            continue
        if place and action in (A.PICK_UP, A.INSPECT):
            steps.append(Step(who=who, kind="go_to", location=place))
        steps.append(Step(who=who, kind="do", action=action.value, object=obj, route=route))
    return Interpretation(steps=steps, note=None if steps else "No instruction recognised.")


# --- LLM interpretation ---------------------------------------------------------------------------------

def interpreter_messages(world: WorldState, player: str, text: str) -> list[dict[str, str]]:
    chars = "; ".join(
        f"{cid} ({p.name}, abilities: {', '.join(a.value for a in p.abilities)})" for cid, p in world.profiles.items()
    )
    places = "; ".join(f"{lid} ({loc.name})" for lid, loc in world.locations.items())
    objects = "; ".join(f"{oid} ({o.name})" for oid, o in world.objects.items())
    routes = "; ".join(f"{rid} ({r.name}: {r.a}-{r.b})" for rid, r in world.routes.items() if not r.hidden)
    actions = ", ".join(a.value for a in COMMANDABLE)
    system = (
        "You translate a player's instruction in an adventure game into JSON commands. Use ONLY these ids.\n"
        f"Characters: {chars}. The player is {player}; 'I', 'me', 'myself' mean {player}.\n"
        f"Places: {places}.\nObjects: {objects}.\nRoutes: {routes}.\nActions: {actions}.\n"
        'Reply with JSON only: {"steps": [ ... ], "note": "<optional short note>"}. Each step is one of:\n'
        '{"who": "<character id>", "kind": "go_to", "location": "<place id>"}\n'
        '{"who": "<character id>", "kind": "do", "action": "<action>", "route": "<route id or null>", '
        '"object": "<object id or null>", "to": "<character id, only for give>"}\n'
        '{"who": "<character id>", "kind": "wait", "seconds": <5-60>}\n'
        '{"who": "<character id>", "kind": "resume"}  (stop following orders, go back to own plan)\n'
        "Keep the player's order of steps. Do not add steps the player did not ask for. If an action has to "
        "happen at a specific place, add the go_to step before it - in particular discover_route searches only "
        "where the character stands, so 'search the woods' is go_to forest then discover_route. detect_traps "
        "may leave route null (the trapped route is chosen when it is known). If nothing is a game instruction, "
        'return {"steps": [], "note": "<why>"}.'
    )
    return [{"role": "system", "content": system}, {"role": "user", "content": text[:MAX_COMMAND_CHARS]}]


def parse_interpretation(text: str) -> Interpretation | None:
    cleaned = THINK_BLOCK.sub("", text).replace("```json", "").replace("```", "")
    match = JSON_OBJECT.search(cleaned)
    if not match:
        return None
    try:
        return Interpretation.model_validate(json.loads(match.group(0)))
    except (ValueError, ValidationError):
        return None


# --- validation into orders ------------------------------------------------------------------------------

class Validated(BaseModel):
    orders: dict[str, list[Order]] = {}
    resume: list[str] = []
    refusals: list[tuple[str, str]] = []  # (character id or "", reason)


ACTION_ALIASES = {
    "discover_routes": A.DISCOVER_ROUTE, "search": A.DISCOVER_ROUTE, "scout": A.DISCOVER_ROUTE,
    "find_route": A.DISCOVER_ROUTE, "search_hidden_paths": A.DISCOVER_ROUTE,
    "mark_traps": A.DETECT_TRAPS, "disarm_traps": A.DETECT_TRAPS, "find_traps": A.DETECT_TRAPS,
    "decode": A.DECODE_SYMBOLS, "lever": A.PULL_LEVER, "open_gate": A.PULL_LEVER, "take": A.PICK_UP,
    "pickup": A.PICK_UP, "grab": A.PICK_UP, "block": A.BLOCK_ROUTE, "clear": A.CLEAR_ROUTE, "install": A.INSTALL_CRYSTAL,
    "activate": A.ACTIVATE_LIGHTHOUSE, "light_beacon": A.ACTIVATE_LIGHTHOUSE, "fix_bridge": A.REPAIR_BRIDGE,
}


def action_type_of(raw: str | None) -> A | None:
    """Accept the exact action id or an obvious variant an LLM might write (e.g. 'discover_routes')."""
    key = (raw or "").strip().lower().replace(" ", "_").replace("-", "_")
    try:
        return A(key)
    except ValueError:
        pass
    if key in ACTION_ALIASES:
        return ACTION_ALIASES[key]
    if key.endswith("s"):
        try:
            return A(key[:-1])
        except ValueError:
            return None
    return None


def _resolve(value: str | None, ids: dict[str, object], table: dict[str, list[str]] | None = None) -> str | None:
    if not value:
        return None
    v = value.strip().lower()
    if v in ids:
        return v
    return _find(v, table) if table else None


def validate(world: WorldState, player: str, interp: Interpretation) -> Validated:
    out = Validated()
    names = {p.name.lower(): cid for cid, p in world.profiles.items()}
    now = world.clock.now

    def who_of(raw: str) -> str | None:
        r = raw.strip().lower()
        if r in world.characters:
            return r
        if r in names:
            return names[r]
        if r in SELF_WORDS or r in ("player", "self"):
            return player
        return None

    for step in interp.steps:
        who = who_of(step.who)
        if who is None:
            out.refusals.append(("", f"There is nobody called '{step.who}' on the expedition."))
            continue
        name = world.name(who)
        if step.kind == "resume":
            out.resume.append(who)
            out.orders.pop(who, None)
            continue
        orders = out.orders.setdefault(who, [])
        if step.kind == "go_to":
            loc = _resolve(step.location, world.locations, PLACE_WORDS)
            if loc is None:
                out.refusals.append((who, f"There is no place called '{step.location}'."))
                continue
            orders.append(Order(kind="go_to", location=loc, summary=f"go to the {world.locations[loc].name}",
                                from_id=player, given_at=now))
            continue
        if step.kind == "wait":
            secs = max(5, min(60, step.seconds or 30))
            orders.append(Order(kind="wait", action=ProposedAction(actor=who, type=A.WAIT, seconds=secs),
                                summary=f"wait {secs}s", from_id=player, given_at=now))
            continue

        action_type = action_type_of(step.action)
        if action_type is None:
            out.refusals.append((who, f"'{step.action}' is not something anyone can do here."))
            continue
        if action_type not in COMMANDABLE:
            out.refusals.append((who, f"'{action_type.value}' cannot be ordered."))
            continue
        if reason := capability_blocker(world, who, action_type):
            out.refusals.append((who, reason))
            continue
        route = _resolve(step.route, world.routes, ROUTE_WORDS)
        if route is not None and world.routes[route].hidden:
            route = None  # nobody may be ordered along a route that has not been discovered
        obj = _resolve(step.object, world.objects, OBJECT_WORDS)
        target = who_of(step.to) if step.to else None
        if action_type is A.DETECT_TRAPS and (route is None or world.routes[route].hazard is None):
            route = None  # decided when carried out, from the trapped routes the character knows by then
        elif action_type in (A.BLOCK_ROUTE, A.CLEAR_ROUTE) and route is None:
            out.refusals.append((who, f"Which route should {name} {RULES[action_type].verb.split(' ')[0]}?"))
            continue
        if action_type in (A.PICK_UP, A.DROP, A.GIVE) and obj is None:
            out.refusals.append((who, f"Which item should {name} {action_type.value.replace('_', ' ')}?"))
            continue
        if action_type is A.GIVE and (target is None or target == who):
            out.refusals.append((who, f"Who should {name} give the {world.objects[obj].name} to?"))
            continue
        action = ProposedAction(actor=who, type=action_type, route_id=route, object_id=obj, target_id=target)
        orders.append(Order(kind="action", action=action, summary=describe(world, action),
                            from_id=player, given_at=now))
    out.orders = {cid: o for cid, o in out.orders.items() if o}
    return out


def describe(world: WorldState, action: ProposedAction) -> str:
    t = action.type
    if t is A.PICK_UP and action.object_id:
        return f"pick up the {world.objects[action.object_id].name}"
    if t is A.DROP and action.object_id:
        return f"drop the {world.objects[action.object_id].name}"
    if t is A.GIVE and action.object_id and action.target_id:
        return f"give the {world.objects[action.object_id].name} to {world.name(action.target_id)}"
    if t is A.DETECT_TRAPS:
        where = f" on the {world.routes[action.route_id].name}" if action.route_id else ""
        return f"mark any traps{where}"
    if action.route_id:
        return f"{RULES[t].verb.split(' ')[0]} the {world.routes[action.route_id].name}"
    return RULES[t].verb
