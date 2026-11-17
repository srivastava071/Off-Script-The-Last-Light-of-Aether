from enum import StrEnum


class GameMode(StrEnum):
    DEFAULT = "default"
    GAME = "game"


class RunStatus(StrEnum):
    CREATED = "created"
    RUNNING = "running"
    FINISHED = "finished"
    ABANDONED = "abandoned"  # replaced by a restart before it ended


class ObjectiveStatus(StrEnum):
    PENDING = "pending"
    COMPLETE = "complete"
    FAILED = "failed"


class EndingId(StrEnum):
    LIGHT_RETURNS = "light_returns"        # A
    COSTLY_VICTORY = "costly_victory"      # B
    UNEXPECTED_ROUTE = "unexpected_route"  # C
    LAST_STORM = "last_storm"              # D


class Ability(StrEnum):
    # Aria
    CLIMB = "climb"
    JUMP_GAP = "jump_gap"
    INSPECT_CLUES = "inspect_clues"
    # Kabir
    REPAIR = "repair"
    BUILD_BRIDGE = "build_bridge"
    OPERATE_MECHANISM = "operate_mechanism"
    DIAGNOSE = "diagnose"
    # Meera
    DETECT_TRAPS = "detect_traps"
    DISCOVER_ROUTES = "discover_routes"
    DISTRACT = "distract"
    DECODE_SYMBOLS = "decode_symbols"
    SIGNAL = "signal"  # horn calls that reach every teammate


class RouteStatus(StrEnum):
    OPEN = "open"
    BROKEN = "broken"    # physically damaged; can be repaired
    LOCKED = "locked"    # sealed by a mechanism
    FLOODED = "flooded"  # impassable because of water


class ActionType(StrEnum):
    MOVE = "move"
    WAIT = "wait"
    INSPECT = "inspect"
    TALK = "talk"
    ASK = "ask"
    REQUEST_HELP = "request_help"
    SIGNAL = "signal"
    PICK_UP = "pick_up"
    DROP = "drop"
    GIVE = "give"
    DISCOVER_ROUTE = "discover_route"
    DETECT_TRAPS = "detect_traps"
    REPAIR_BRIDGE = "repair_bridge"
    BLOCK_ROUTE = "block_route"
    CLEAR_ROUTE = "clear_route"
    REPAIR_MECHANISM = "repair_mechanism"
    DECODE_SYMBOLS = "decode_symbols"
    PULL_LEVER = "pull_lever"
    REPAIR_LIGHTHOUSE = "repair_lighthouse"
    INSTALL_CRYSTAL = "install_crystal"
    ACTIVATE_LIGHTHOUSE = "activate_lighthouse"


class EventKind(StrEnum):
    TRAVEL_STARTED = "travel_started"
    ARRIVED = "arrived"
    TRAP_SPRUNG = "trap_sprung"
    ITEM_PICKED_UP = "item_picked_up"
    ITEM_DROPPED = "item_dropped"
    ITEM_GIVEN = "item_given"
    WAITED = "waited"
    INSPECTED = "inspected"
    TALKED = "talked"
    ASKED = "asked"
    HELP_REQUESTED = "help_requested"
    HELP_ACCEPTED = "help_accepted"
    HELP_DECLINED = "help_declined"
    SIGNALLED = "signalled"
    SEARCHED = "searched"
    PLAN_CHANGED = "plan_changed"
    ACTION_STARTED = "action_started"
    ACTION_FAILED = "action_failed"
    ROUTE_DISCOVERED = "route_discovered"
    TRAPS_MARKED = "traps_marked"
    BRIDGE_REPAIRED = "bridge_repaired"
    ROUTE_BLOCKED = "route_blocked"
    ROUTE_CLEARED = "route_cleared"
    MECHANISM_REPAIRED = "mechanism_repaired"
    SYMBOLS_DECODED = "symbols_decoded"
    GATE_OPENED = "gate_opened"
    FLOOD_WARNING = "flood_warning"
    CHAMBER_FLOODED = "chamber_flooded"
    LIGHTHOUSE_REPAIRED = "lighthouse_repaired"
    CRYSTAL_INSTALLED = "crystal_installed"
    LIGHTHOUSE_ACTIVATED = "lighthouse_activated"
    # Run / Director
    RUN_STARTED = "run_started"
    RUN_ENDED = "run_ended"
    STORY_BEAT = "story_beat"
    OBJECTIVE_UPDATED = "objective_updated"
    DIRECTOR_NOTE = "director_note"
    STORM_WARNING = "storm_warning"
    LLM_DELIBERATION = "llm_deliberation"
    LESSON_APPLIED = "lesson_applied"  # a character acts on a lesson from an earlier game
    # Player commands (typed or spoken), relayed by radio
    COMMAND_GIVEN = "command_given"
    ORDER_ACCEPTED = "order_accepted"
    ORDER_REFUSED = "order_refused"
    ORDER_FAILED = "order_failed"
    ORDER_COMPLETED = "order_completed"
    # The player as co-author: radio talk that is heard but not obeyed, and story twists
    RADIO_MESSAGE = "radio_message"
    STORY_TWIST = "story_twist"
