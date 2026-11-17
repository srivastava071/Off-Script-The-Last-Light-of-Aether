"""A single playthrough. The Run is the only gateway through which a game advances or a player acts.

- Default Mode: all three characters are autonomous, there is no deadline, and player input is refused.
- Game Mode: the player controls one character; the other two stay autonomous; the deadline is enforced.

The Run holds no hidden state of its own: everything lives in ``world`` (so it can be saved and
restored), and agents/Director are rebuilt from it.
"""

import uuid
from collections.abc import Callable

from app.agents import dialogue, requests, storyteller
from app.agents.storyteller import Twist
from app.agents.commands import Interpretation, validate
from app.agents.orders import PlayerAutopilot
from app.agents.character_agent import CharacterAgent
from app.agents.director import Director
from app.agents.planner import FallbackPlanner, Planner
from app.engine import knowledge
from app.engine.aether import build_initial_world
from app.engine.rules import perform
from app.engine.simulation import run_tick
from app.models.actions import ActionResult, ProposedAction
from app.models.enums import ActionType, EventKind, GameMode, RunStatus
from app.models.events import WorldEvent
from app.models.mind import ActiveLesson
from app.models.world import WorldState

PlannerFactory = Callable[[str], Planner]
MAX_REMEMBERED_REQUESTS = 200


class RunError(ValueError):
    """Raised when a run is created with an invalid configuration."""


class Run:
    def __init__(self, world: WorldState, planner_factory: PlannerFactory | None = None,
                 on_trigger: Callable[[str, str], None] | None = None):
        self.world = world
        make = planner_factory or (lambda _cid: FallbackPlanner())
        self.agents = {
            cid: CharacterAgent(cid, make(cid), on_trigger)
            for cid in sorted(world.characters) if cid != world.story.player_character
        }
        self.director = Director()
        player = world.story.player_character
        self.autopilot = PlayerAutopilot(player) if player is not None else None

    @classmethod
    def create(
        cls,
        mode: GameMode,
        player_character: str | None = None,
        *,
        run_id: str | None = None,
        tick_seconds: int = 5,
        deadline_seconds: int = 600,
        planner_factory: PlannerFactory | None = None,
        lessons: dict[str, list[ActiveLesson]] | None = None,
    ) -> "Run":
        """``lessons``: from the team journal, per character; the player's own character never gets any."""
        world = build_initial_world(
            run_id or uuid.uuid4().hex, mode, tick_seconds=tick_seconds,
            deadline_seconds=deadline_seconds if mode is GameMode.GAME else None,
        )
        if mode is GameMode.GAME:
            if player_character not in world.characters:
                raise RunError(f"Game Mode needs a character to control: one of {sorted(world.characters)}.")
        elif player_character is not None:
            raise RunError("Default Mode has no player character.")
        world.story.player_character = player_character
        for cid, carried in (lessons or {}).items():
            if cid in world.minds and cid != player_character:
                world.minds[cid].lessons = [le.model_copy() for le in carried]
        return cls(world, planner_factory)

    # --- lifecycle --------------------------------------------------------------------------------

    @property
    def status(self) -> RunStatus:
        return self.world.story.status

    def start(self) -> list[WorldEvent]:
        if self.status is not RunStatus.CREATED:
            return []
        self.world.story.status = RunStatus.RUNNING
        who = self.world.story.player_character
        text = ("Default Mode: the story runs on its own." if who is None
                else f"Game Mode: you are {self.world.name(who)}. The storm arrives in {self.world.clock.deadline}s.")
        events = [self.world.record(EventKind.RUN_STARTED, text, mode=self.world.mode.value, player=who)]
        return events + self.director.evaluate(self.world)

    def tick(self) -> list[WorldEvent]:
        """Advance one simulation tick. Never runs past the deadline or after the run ends."""
        if self.status is not RunStatus.RUNNING:
            return []
        clock = self.world.clock
        until = clock.now + clock.tick_seconds
        if clock.deadline is not None:
            until = min(until, clock.deadline)
        steppers = dict(self.agents)
        if self.autopilot is not None:
            steppers[self.autopilot.character_id] = self.autopilot  # carries out the player's spoken orders
        events = run_tick(self.world, steppers, until)
        return events + self.director.evaluate(self.world)

    def give_command(self, text: str, interpretation: Interpretation, interpreted_by: str) -> ActionResult:
        """Relay a typed or spoken instruction by radio. Characters obey every order they are able to carry out."""
        world, story = self.world, self.world.story
        if world.mode is GameMode.DEFAULT:
            return ActionResult.reject("Default Mode is a demonstration: player input is disabled.")
        if self.status is not RunStatus.RUNNING:
            return ActionResult.reject("Commands can only be given while the run is in progress.")
        player = story.player_character or ""
        checked = validate(world, player, interpretation)
        if not checked.orders and not checked.resume:
            reasons = " ".join(r for _, r in checked.refusals) or interpretation.note or ""
            return ActionResult.reject(
                f"That could not be turned into orders. {reasons} Try e.g. 'Kabir, fix the bridge' "
                "or 'Meera, scout the forest'.".replace("  ", " ")
            )
        here = world.characters[player].location_id
        events = [world.record(EventKind.COMMAND_GIVEN, f'{world.name(player)} (radio): "{text}"', actor=player,
                               location_id=here, text=text, interpreted_by=interpreted_by)]
        for cid in checked.resume:
            world.minds[cid].orders = []
            events.append(world.record(EventKind.ORDER_COMPLETED, f"{world.name(cid)} goes back to their own plan.",
                                       actor=cid, location_id=world.characters[cid].location_id, target=player))
        for cid, orders in checked.orders.items():
            world.minds[cid].orders = orders  # the latest instruction replaces any earlier one
            steps = " → ".join(o.summary for o in orders)
            if cid == player:
                reply = f"{world.name(cid)} will {steps}."
            else:
                later = " (after finishing the current task)" if world.characters[cid].busy else ""
                reply = f'{world.name(cid)}: "{requests.AGREE.get(cid, "Understood.")}" Will {steps}{later}.'
                knowledge.remember(world, cid, f"{world.name(player)} radioed: {text}", source=f"told:{player}",
                                   importance=4, related=[player])
            events.append(world.record(EventKind.ORDER_ACCEPTED, reply, actor=cid,
                                       location_id=world.characters[cid].location_id, target=player,
                                       orders=[o.summary for o in orders]))
        for cid, reason in checked.refusals:
            events.append(world.record(EventKind.ORDER_REFUSED, f"{world.name(cid) + ' cannot: ' if cid else ''}{reason}",
                                       actor=cid or None, target=player, reason=reason))
        events += self.director.evaluate(world)
        accepted = sum(1 for e in events if e.kind is EventKind.ORDER_ACCEPTED)
        refused = len(checked.refusals)
        msg = f"{accepted} character(s) took orders" + (f"; {refused} order(s) refused." if refused else ".")
        return ActionResult.success(msg, *events)

    def _co_author_check(self, what: str) -> ActionResult | None:
        if self.world.mode is GameMode.DEFAULT:
            return ActionResult.reject("Default Mode is a demonstration: player input is disabled.")
        if self.status is not RunStatus.RUNNING:
            return ActionResult.reject(f"{what} only while the run is in progress.")
        return None

    def radio_say(self, text: str) -> ActionResult:
        """'Say' by radio: every teammate hears and remembers it, but nobody is ordered to do anything."""
        if (rejected := self._co_author_check("You can talk on the radio")) is not None:
            return rejected
        world = self.world
        player = world.story.player_character or ""
        event = world.record(EventKind.RADIO_MESSAGE, f'{world.name(player)} (radio): "{text}"', actor=player,
                             location_id=world.characters[player].location_id, text=text)
        for cid in world.characters:
            if cid != player:
                knowledge.remember(world, cid, f'{world.name(player)} said over the radio: "{text}"',
                                   source=f"told:{player}", importance=3, related=[player], event_seq=event.seq,
                                   kind=event.kind.value)
        return ActionResult.success("Your teammates heard you.", event, *self.director.evaluate(world))

    def can_add_twist(self) -> bool:
        return self._co_author_check("") is None and storyteller.limit_reason(self.world) is None

    def add_twist(self, text: str, twist: Twist | None, interpreted_by: str, note: str = "") -> ActionResult:
        """'Story': the player adds a twist from the catalogue of what the island allows right now."""
        if (rejected := self._co_author_check("Story twists can be added")) is not None:
            return rejected
        world = self.world
        if (reason := storyteller.limit_reason(world)) is not None:
            return ActionResult.reject(reason)
        if twist is None or twist.key not in {o.key for o in storyteller.options(world)}:
            return ActionResult.reject(note or "That twist is not possible on the island right now.")
        seen_at, perceive_at = storyteller.apply(world, twist)
        story = world.story
        story.twists_used += 1
        story.last_twist_at = world.clock.now
        details = {k: v for k, v in (("route_id", twist.route_id), ("object_id", twist.object_id),
                                     ("to_location", twist.to_location)) if v is not None}
        event = world.record(EventKind.STORY_TWIST, f"Twist: {twist.summary}", location_id=seen_at, text=text,
                             twist=twist.kind, interpreted_by=interpreted_by, **details)
        if seen_at is None:  # the storm is heard island-wide
            for cid in world.characters:
                knowledge.remember(world, cid, "Thunder rolls closer: the storm is coming sooner than expected.",
                                   source="observed", importance=5, event_seq=event.seq, kind=event.kind.value)
        else:
            knowledge.observe(world, [event])
            for loc in perceive_at:
                for cid in world.characters_at(loc):
                    knowledge.perceive(world, cid)
        left = storyteller.MAX_TWISTS - story.twists_used
        return ActionResult.success(f"The island changes. {left} twist(s) left.", event, *self.director.evaluate(world))

    def record_reply(self, speaker: str, listener: str, text: str, generated_by: str) -> WorldEvent:
        """Add a reply produced outside the lock-step (e.g. by an LLM) to the record."""
        event = dialogue.reply_event(self.world, speaker, listener, text, generated_by)
        knowledge.observe(self.world, [event])
        return event

    def abandon(self) -> None:
        """Stop a run that is being replaced. A finished run keeps its ending."""
        if self.status in (RunStatus.CREATED, RunStatus.RUNNING):
            self.world.story.status = RunStatus.ABANDONED

    def run_to_end(self, max_ticks: int = 2000) -> list[WorldEvent]:
        events = self.start()
        for _ in range(max_ticks):
            if self.status is RunStatus.FINISHED:
                return events
            events += self.tick()
        raise RuntimeError("run did not finish within max_ticks")

    # --- player -----------------------------------------------------------------------------------

    def player_action(self, action: ProposedAction, request_id: str | None = None,
                      auto_reply: bool = True) -> ActionResult:
        """Validate and apply a player action. The player is held to exactly the same rules as agents.

        ``request_id`` makes retries safe: a repeated id returns the original result and changes nothing.
        """
        story = self.world.story
        if request_id is not None and request_id in story.processed_requests:
            return story.processed_requests[request_id].model_copy(update={"duplicate": True})
        result = self._player_action(action, auto_reply)
        if request_id is not None:
            story.processed_requests[request_id] = result
            while len(story.processed_requests) > MAX_REMEMBERED_REQUESTS:
                story.processed_requests.pop(next(iter(story.processed_requests)))
        return result

    def _player_action(self, action: ProposedAction, auto_reply: bool) -> ActionResult:
        story = self.world.story
        if self.world.mode is GameMode.DEFAULT:
            return ActionResult.reject("Default Mode is a demonstration: player input is disabled.")
        if self.status is RunStatus.CREATED:
            return ActionResult.reject("The run has not started yet.")
        if self.status is RunStatus.FINISHED:
            return ActionResult.reject("The run has ended; no further actions are possible.")
        if self.status is RunStatus.ABANDONED:
            return ActionResult.reject("This run was abandoned by a restart.")
        if action.actor != story.player_character:
            return ActionResult.reject(f"You control {self.world.name(story.player_character or '')} only.")
        result = perform(self.world, action)
        if not result.ok:
            return result
        knowledge.observe(self.world, result.events)
        self.world.minds[action.actor].orders = []  # acting by hand cancels the player's own autopilot
        replies: list[WorldEvent] = []
        if action.type is ActionType.REQUEST_HELP and action.target_id in self.agents:
            replies += requests.respond(self.world, result.events[-1])
        if auto_reply and action.type is ActionType.TALK and action.target_id in self.agents:
            replies.append(dialogue.reply_event(self.world, action.target_id, action.actor))
            self.world.story.ai.template_replies += 1
        knowledge.observe(self.world, replies)
        result.events += replies + self.director.evaluate(self.world)
        return result
