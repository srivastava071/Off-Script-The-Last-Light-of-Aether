"""CharacterAgent: the observe -> remember -> decide -> propose -> validate loop for one character.

The agent never edits the world. It proposes an action; the rules engine accepts or rejects it.
A plan change counts as an *adaptation* when the character keeps the same goal but switches
strategy because of something it learned from outside (an event it saw, a message, a failure).
"""

from collections.abc import Callable

from app.agents.orders import mark_done, next_order_action
from app.agents.planner import Decision, FallbackPlanner, Planner
from app.engine import knowledge
from app.engine.rules import check_action, perform
from app.models.actions import ProposedAction
from app.models.enums import ActionType, EventKind
from app.models.events import WorldEvent
from app.models.mind import Plan
from app.models.world import WorldState

SIGNIFICANT = 4

# Outcomes of a character's own work. If one of these just happened, a strategy change is
# ordinary progress ("bridge done, now cross it"), not an adaptation.
OWN_PROGRESS = {
    EventKind.BRIDGE_REPAIRED, EventKind.ROUTE_CLEARED, EventKind.ROUTE_BLOCKED, EventKind.ROUTE_DISCOVERED,
    EventKind.SEARCHED, EventKind.TRAPS_MARKED, EventKind.MECHANISM_REPAIRED, EventKind.SYMBOLS_DECODED,
    EventKind.GATE_OPENED, EventKind.LIGHTHOUSE_REPAIRED, EventKind.CRYSTAL_INSTALLED, EventKind.ITEM_PICKED_UP,
    EventKind.ITEM_DROPPED, EventKind.ITEM_GIVEN, EventKind.SIGNALLED,
}


class CharacterAgent:
    def __init__(self, character_id: str, planner: Planner | None = None,
                 on_trigger: Callable[[str, str], None] | None = None):
        self.character_id = character_id
        self.planner = planner or FallbackPlanner()
        # Called with (character_id, trigger) when something significant happens, so an LLM can be
        # consulted in the background. The agent never waits for it: it keeps acting on its rules.
        self.on_trigger = on_trigger

    def _take_trigger(self, world: WorldState) -> tuple[str | None, bool]:
        """Most recent significant outside information since the last decision, and whether
        the character's own work just produced progress."""
        mind = world.minds[self.character_id]
        new = mind.memories[mind.memory_cursor:]
        mind.memory_cursor = len(mind.memories)
        progressed = any(m.source == "self" and m.kind in {k.value for k in OWN_PROGRESS} for m in new)
        if mind.last_failure:
            reason, mind.last_failure = mind.last_failure, None
            return f"Action failed: {reason}", False
        significant = [
            m for m in new
            if m.importance >= SIGNIFICANT and (m.source != "self" or m.kind == EventKind.ACTION_FAILED.value)
        ]
        failed = any(m.kind == EventKind.ACTION_FAILED.value for m in significant)
        return (significant[-1].description if significant else None), progressed and not failed

    def _update_plan(
        self, world: WorldState, decision: Decision, trigger: str | None, progressed: bool
    ) -> list[WorldEvent]:
        mind = world.minds[self.character_id]
        old = mind.plan
        now = world.clock.now
        mind.last_planned_at = now
        if old is not None and old.strategy == decision.strategy:
            if (old.summary, old.goal, old.status) != (decision.summary, decision.goal, decision.status):
                mind.plan = old.model_copy(
                    update={"summary": decision.summary, "goal": decision.goal, "status": decision.status})
            return []
        # Adaptation: same goal, new strategy, caused by outside information - not by finishing
        # one's own step, and not by the end of an expected wait (e.g. "symbols are set, pull the lever").
        adaptation = (
            old is not None and trigger is not None and old.goal == decision.goal
            and not progressed and old.status != "waiting"
        )
        mind.plan = Plan(strategy=decision.strategy, goal=decision.goal, summary=decision.summary,
                         created_at=now, status=decision.status, trigger=trigger if adaptation else None)
        mind.replans += 1
        if adaptation:
            mind.adaptations += 1
        name = world.name(self.character_id)
        text = f"{name}: {decision.summary}"
        if adaptation:
            text = f"{name} adapts — {trigger} New plan: {decision.summary}"
        return [world.record(
            EventKind.PLAN_CHANGED, text, actor=self.character_id,
            location_id=world.characters[self.character_id].location_id,
            old_strategy=old.strategy if old else None, new_strategy=decision.strategy, goal=decision.goal,
            trigger=trigger, adaptation=adaptation, planner=decision.source, status=decision.status,
        )]

    def _maintain_requests(self, world: WorldState) -> list[WorldEvent]:
        """Drop promises that expired, were fulfilled, or became impossible - and say so."""
        cid = self.character_id
        mind = world.minds[cid]
        if not mind.requests:
            return []
        req = mind.requests[0]
        here = world.characters[cid].location_id
        reason = None
        if req.action.type is ActionType.MOVE:
            if here == req.action.destination:
                mind.requests.pop(0)  # arrived: the meeting request is fulfilled
                return []
        elif (blocker := check_action(world, req.action)) is not None:
            reason = f"can no longer help: {blocker}"
        if reason is None and world.clock.now >= req.expires_at:
            reason = "the request has lapsed"
        if reason is None:
            return []
        mind.requests.pop(0)
        return [world.record(EventKind.HELP_DECLINED, f"{world.name(cid)} {reason}", actor=cid, location_id=here,
                             target=req.from_id, reason=reason)]

    def step(self, world: WorldState) -> list[WorldEvent]:
        """Decide and start one action if this character is idle. Returns the events produced."""
        cid = self.character_id
        if world.characters[cid].busy:
            return []
        knowledge.perceive(world, cid)
        events = self._maintain_requests(world)
        trigger, progressed = self._take_trigger(world)
        if trigger is not None and self.on_trigger is not None:
            self.on_trigger(cid, trigger)
        order_action, order, order_events = next_order_action(world, cid)
        events += order_events
        if order_action is not None and order is not None:
            # Player orders come first ("obey if able"); the agent resumes its own plan when they are done.
            boss = world.name(order.from_id)
            decision = Decision(strategy="follow_orders", goal=f"Do what {boss} asked", action=order_action,
                                summary=f"Following {boss}'s instruction: {order.summary}.")
        else:
            decision = self.planner.decide(world, cid, trigger)
        mind = world.minds[cid]
        if mind.preferred_strategy and decision.source != "llm":
            mind.preferred_strategy = mind.preference_expires_at = None  # no longer a valid option
        events += self._update_plan(world, decision, trigger, progressed)

        action = decision.action or ProposedAction(actor=cid, type=ActionType.WAIT, seconds=10)
        result = perform(world, action)
        mind = world.minds[cid]
        if result.ok and mind.requests and mind.requests[0].action == action:
            mind.requests.pop(0)  # the requested help has been given
        if result.ok:
            events += mark_done(world, cid, action)
        if not result.ok:
            mind = world.minds[cid]
            mind.failed_actions += 1
            mind.last_failure = result.message
            knowledge.remember(world, cid, f"{world.name(cid)} tried to {action.type.value} but: {result.message}",
                               source="self", importance=SIGNIFICANT, kind=EventKind.ACTION_FAILED.value)
            result = perform(world, ProposedAction(actor=cid, type=ActionType.WAIT, seconds=5))
        knowledge.observe(world, result.events)
        return events + result.events
