"""The Director (Story/Narrative Agent).

Responsibilities: track story beats and objectives, monitor the deadline, assess risk, call out
stalls, announce predefined storm events, decide the ending and write the ending report.

What it may NOT do: move characters, create or move objects, change routes, override
abilities, force success, or prevent failure. Every judgement below reads the authoritative
WorldState; the only things it writes are the story state and narrative events.
"""

from app.engine.aether import OBJ_BRIDGE, OBJ_LEFT_BEHIND, OBJ_MAIN, OBJ_TRAPS
from app.engine.ids import (
    ARIA, BRIDGE, CHAMBER, FOREST_TRAIL, KABIR, LIGHTHOUSE, MAIN_BRIDGE, MEERA, RAVINE_CLIMB, SUN_CRYSTAL, TEMPLE,
)
from app.engine.knowledge import IMPORTANCE
from app.models.enums import EndingId, EventKind, GameMode, ObjectiveStatus, RouteStatus, RunStatus
from app.models.events import WorldEvent
from app.models.story import Chapter, EndingResult, Objective
from app.models.world import WorldState

MAIN, BRIDGE_RESTORED, NO_TRAP_INJURIES, NOBODY_LEFT_BEHIND = OBJ_MAIN, OBJ_BRIDGE, OBJ_TRAPS, OBJ_LEFT_BEHIND

TITLES = {
    EndingId.LIGHT_RETURNS: "The Light Returns",
    EndingId.COSTLY_VICTORY: "A Costly Victory",
    EndingId.UNEXPECTED_ROUTE: "An Unexpected Route",
    EndingId.LAST_STORM: "The Last Storm",
}

# How the predefined story unfolds. A successful run that differs from this is "An Unexpected Route".
DEFAULT_SIGNATURE = {
    "gate_opened_by": ARIA,
    "crystal_taken_by": ARIA,
    "temple_routes": {ARIA: RAVINE_CLIMB, KABIR: MAIN_BRIDGE, MEERA: FOREST_TRAIL},
}

STORM_WARNINGS = {
    # Keys are simulated seconds left; the texts avoid minutes because Game Mode runs faster than real time.
    300: "Half the time is gone. The storm wall swallows the outer reef.",
    120: "The storm is close. Lightning strikes the harbour; the barrier flickers.",
    60: "Final moments! The first waves break over the cliffs.",
}
# Opening line of each storybook chapter; the facts recorded since the last chapter follow it.
BEAT_LINES = {
    "landing": "The little boat bumped against the rotting piers of the Abandoned Harbour, and three friends "
               "stepped onto Aether Island with the storm already rumbling behind them.",
    "bridge_broken": "At the ravine they found the Main Bridge torn in two, its planks dangling over the drop.",
    "way_across": "Somehow, a way across the ravine was found.",
    "temple_reached": "The carved doorway of the temple rose out of the jungle, sealed by gears and strange symbols.",
    "puzzle_solved": "With a deep grinding groan, the temple gate swung open, and somewhere below, water began to rise.",
    "chamber_entered": "Someone waded into the Flooded Chamber, where the Sun Crystal glowed on its pedestal.",
    "crystal_retrieved": "The Sun Crystal was lifted from its pedestal, warm and bright in the gloom.",
    "return_journey": "The Sun Crystal reached the Lighthouse at last.",
    "beacon_lit": "The beacon blazed into life, and the barrier rose over Aether once more.",
}
# What counts as a storybook fact: things that happen in the world, not thinking or bookkeeping.
STORY_KINDS = {
    EventKind.TRAP_SPRUNG, EventKind.ITEM_GIVEN, EventKind.SIGNALLED, EventKind.ROUTE_DISCOVERED,
    EventKind.TRAPS_MARKED, EventKind.BRIDGE_REPAIRED, EventKind.ROUTE_BLOCKED, EventKind.ROUTE_CLEARED,
    EventKind.MECHANISM_REPAIRED, EventKind.SYMBOLS_DECODED, EventKind.GATE_OPENED, EventKind.FLOOD_WARNING,
    EventKind.CHAMBER_FLOODED, EventKind.LIGHTHOUSE_REPAIRED, EventKind.CRYSTAL_INSTALLED,
    EventKind.LIGHTHOUSE_ACTIVATED, EventKind.HELP_ACCEPTED, EventKind.HELP_DECLINED, EventKind.STORM_WARNING,
    EventKind.STORY_TWIST,
}
MAX_CHAPTER_FACTS = 6
TYPICAL_STORY_SECONDS = 330  # length of the undisturbed story, used to judge risk
STALL_SECONDS = 120
DEFAULT_MODE_SAFETY_LIMIT = 1200  # Default Mode has no deadline; this only guards against a bug


class Director:
    name = "director"

    # --- public -----------------------------------------------------------------------------------

    def evaluate(self, world: WorldState) -> list[WorldEvent]:
        """Review the world after a change. Returns the narrative events it recorded."""
        story = world.story
        if story.status is not RunStatus.RUNNING:
            return []
        events: list[WorldEvent] = []
        events += self._review_events(world)
        events += self._update_beats(world)
        events += self._storm(world)
        events += self._assess(world)
        if (ending := self._terminal(world)) is not None:
            events += self._finish(world, ending)
        return events

    # --- beats and objectives ---------------------------------------------------------------------

    def _review_events(self, world: WorldState) -> list[WorldEvent]:
        out: list[WorldEvent] = []
        new = [e for e in world.events if e.seq > world.story.event_cursor]
        if new:
            world.story.event_cursor = new[-1].seq
        for e in new:
            if e.kind is EventKind.TRAP_SPRUNG:
                out += self._resolve(world, NO_TRAP_INJURIES, ObjectiveStatus.FAILED, f"{world.name(e.actor or '')} was caught by a trap.")
            if e.kind is EventKind.CHAMBER_FLOODED and e.data.get("trapped"):
                out += self._resolve(world, NOBODY_LEFT_BEHIND, ObjectiveStatus.FAILED, "Someone was trapped by the flood.")
            if e.kind is EventKind.STORY_TWIST:
                self._chapter(world, "A twist in the tale", e.description, "twist", upto=e.seq)
        if world.routes[MAIN_BRIDGE].status is RouteStatus.OPEN:
            out += self._resolve(world, BRIDGE_RESTORED, ObjectiveStatus.COMPLETE, "The Main Bridge is restored.")
        return out

    def _resolve(self, world: WorldState, objective_id: str, status: ObjectiveStatus, why: str) -> list[WorldEvent]:
        obj = self._objective(world, objective_id)
        if obj.status is not ObjectiveStatus.PENDING:
            return []
        obj.status, obj.resolved_at = status, world.clock.now
        return [world.record(EventKind.OBJECTIVE_UPDATED, f"Objective '{obj.title}' {status.value}: {why}",
                             objective=objective_id, status=status.value)]

    @staticmethod
    def _objective(world: WorldState, objective_id: str) -> Objective:
        return next(o for o in world.story.objectives if o.id == objective_id)

    def _beat_reached(self, world: WorldState, beat_id: str) -> bool:
        at = lambda loc: bool(world.characters_at(loc))  # noqa: E731
        crystal = world.objects.get(SUN_CRYSTAL)
        carrier = crystal.carried_by if crystal else None
        return {
            "landing": True,
            "bridge_broken": any(e.kind is EventKind.ARRIVED and e.location_id == BRIDGE for e in world.events),
            "way_across": world.routes[MAIN_BRIDGE].status is RouteStatus.OPEN
                          or not world.routes[FOREST_TRAIL].hidden or at(TEMPLE),
            "temple_reached": any(e.kind is EventKind.ARRIVED and e.location_id == TEMPLE for e in world.events),
            "puzzle_solved": world.temple_lock.gate_open,
            "chamber_entered": any(e.kind is EventKind.ARRIVED and e.location_id == CHAMBER for e in world.events),
            "crystal_retrieved": carrier is not None or world.lighthouse.crystal_installed,
            "return_journey": world.lighthouse.crystal_installed
                              or (carrier is not None and world.characters[carrier].location_id == LIGHTHOUSE),
            "beacon_lit": world.lighthouse.activated,
        }[beat_id]

    def _update_beats(self, world: WorldState) -> list[WorldEvent]:
        out = []
        for beat in world.story.beats:
            if beat.reached_at is None and self._beat_reached(world, beat.id):
                beat.reached_at = world.clock.now
                world.story.last_beat_at = world.clock.now
                world.story.stall_noted = False
                out.append(world.record(EventKind.STORY_BEAT, f"Story: {beat.title}", beat=beat.id))
                self._chapter(world, beat.title, BEAT_LINES.get(beat.id, beat.title + "."), "beat", upto=out[-1].seq)
        return out

    # --- the storybook ----------------------------------------------------------------------------

    @staticmethod
    def _chapter(world: WorldState, title: str, opening: str, kind: str, upto: int) -> None:
        """Write a storybook page from the facts recorded since the previous page (template prose)."""
        story = world.story
        facts = [e.description for e in world.events
                 if story.chapter_cursor < e.seq <= upto and e.kind in STORY_KINDS][-MAX_CHAPTER_FACTS:]
        story.chapter_cursor = max(story.chapter_cursor, upto)
        extra = [f for f in facts if f != opening][-2:] if kind == "beat" else []
        text = " ".join([opening, *extra])
        story.chapters.append(Chapter(id=len(story.chapters) + 1, time=world.clock.now, title=title, text=text,
                                      kind=kind, facts=facts or [opening]))

    # --- pressure and assessment ------------------------------------------------------------------

    def _storm(self, world: WorldState) -> list[WorldEvent]:
        remaining = world.clock.remaining
        if remaining is None:
            return []
        out = []
        for threshold, text in sorted(STORM_WARNINGS.items(), reverse=True):
            if remaining <= threshold and threshold not in world.story.storm_warnings:
                world.story.storm_warnings.append(threshold)
                out.append(world.record(EventKind.STORM_WARNING, text, remaining=remaining))
        return out

    @staticmethod
    def _next_requirement(world: WorldState) -> str:
        lock, lh = world.temple_lock, world.lighthouse
        if not lock.mechanism_repaired:
            return "the temple mechanism is still broken"
        if not lock.symbols_decoded:
            return "the temple symbols are not decoded"
        if not lock.gate_open:
            return "nobody has opened the temple gate"
        crystal = world.objects[SUN_CRYSTAL]
        if crystal.location_id == CHAMBER:
            return "the Sun Crystal is still in the chamber"
        if not lh.operational:
            return "the lighthouse mechanism is not repaired"
        if not lh.crystal_installed:
            return "the Sun Crystal has not reached the lighthouse"
        return "the beacon has not been lit"

    def _assess(self, world: WorldState) -> list[WorldEvent]:
        story = world.story
        reached = [i for i, b in enumerate(story.beats) if b.reached_at is not None]
        progress = (max(reached) + 1) / len(story.beats) if reached else 0.0
        blocked = sorted(
            cid for cid, mind in world.minds.items()
            if cid != story.player_character and mind.plan is not None and mind.plan.status in ("blocked", "failed")
        )
        crystal = world.objects[SUN_CRYSTAL]
        remaining = world.clock.remaining
        expected = (1 - progress) * TYPICAL_STORY_SECONDS
        if world.flood.flooded and crystal.location_id == CHAMBER:
            risk = "failing"
        elif remaining is not None and remaining < expected * 0.6:
            risk = "failing"
        elif (remaining is not None and remaining < expected * 1.2) or blocked:
            risk = "at_risk"
        else:
            risk = "on_track"
        need = self._next_requirement(world)
        note = {"on_track": f"On track. Next: {need}.",
                "at_risk": f"At risk. Next: {need}." + (f" Blocked: {', '.join(world.name(c) for c in blocked)}." if blocked else ""),
                "failing": f"Failing. {need[0].upper() + need[1:]}."}[risk]

        out = []
        if risk != story.assessment.risk:
            out.append(world.record(EventKind.DIRECTOR_NOTE, f"Director: {note}", risk=risk, progress=round(progress, 2)))
        story.assessment = story.assessment.model_copy(update={"progress": progress, "risk": risk, "note": note, "blocked": blocked})

        if world.clock.now - story.last_beat_at >= STALL_SECONDS and not story.stall_noted:
            story.stall_noted = True
            out.append(world.record(EventKind.DIRECTOR_NOTE,
                                    f"Director: The expedition has stalled — {need}.", stalled=True, risk=risk))
        return out

    # --- endings -------------------------------------------------------------------------------------

    @staticmethod
    def signature(world: WorldState) -> dict:
        def first(kind: EventKind, **match) -> WorldEvent | None:
            return next((e for e in world.events if e.kind is kind and all(e.data.get(k) == v for k, v in match.items())), None)
        gate = first(EventKind.GATE_OPENED)
        pickup = first(EventKind.ITEM_PICKED_UP, object_id=SUN_CRYSTAL)
        temple_routes = {}
        for e in world.events:
            if e.kind is EventKind.ARRIVED and e.location_id == TEMPLE and e.actor not in temple_routes:
                temple_routes[e.actor] = e.data.get("route_id")
        return {
            "gate_opened_by": gate.actor if gate else None,
            "crystal_taken_by": pickup.actor if pickup else None,
            "temple_routes": temple_routes,
        }

    def _terminal(self, world: WorldState) -> tuple[EndingId, str] | None:
        """Deterministic priority: success variants first, then failure. Never fails after success."""
        lh = world.lighthouse
        deadline = world.clock.deadline
        if lh.activated and (deadline is None or (lh.activated_at or 0) <= deadline):
            failed = [o for o in world.story.objectives if o.optional and o.status is ObjectiveStatus.FAILED]
            if world.routes[MAIN_BRIDGE].status is not RouteStatus.OPEN:
                failed.append(self._objective(world, BRIDGE_RESTORED))  # never repaired by the end
            if failed:
                return EndingId.COSTLY_VICTORY, "The beacon is lit, but at a cost: " + "; ".join(o.title for o in failed) + "."
            if self.signature(world) != DEFAULT_SIGNATURE:
                return EndingId.UNEXPECTED_ROUTE, "The beacon is lit, but the team reached it by a path the plan never foresaw."
            return EndingId.LIGHT_RETURNS, "The Sun Crystal was delivered and the beacon lit before the storm."
        crystal = world.objects[SUN_CRYSTAL]
        if world.flood.flooded and crystal.location_id == CHAMBER:
            return EndingId.LAST_STORM, "The Sun Crystal was lost when the chamber flooded; nothing can stop the storm now."
        if deadline is not None and world.clock.now >= deadline:
            return EndingId.LAST_STORM, f"Time ran out before the beacon was lit: {self._next_requirement(world)}."
        if deadline is None and world.mode is GameMode.DEFAULT and world.clock.now >= DEFAULT_MODE_SAFETY_LIMIT:
            return EndingId.LAST_STORM, "The story did not conclude within the safety limit."
        return None

    def _finish(self, world: WorldState, ending: tuple[EndingId, str]) -> list[WorldEvent]:
        ending_id, explanation = ending
        story = world.story
        out: list[WorldEvent] = []
        success = ending_id is not EndingId.LAST_STORM
        out += self._resolve(world, MAIN, ObjectiveStatus.COMPLETE if success else ObjectiveStatus.FAILED, explanation)
        for obj in story.objectives:
            if obj.optional and obj.status is ObjectiveStatus.PENDING:
                final = ObjectiveStatus.FAILED if obj.id == BRIDGE_RESTORED else ObjectiveStatus.COMPLETE
                out += self._resolve(world, obj.id, final, "Resolved at the end of the run.")
        story.status = RunStatus.FINISHED
        story.ending = self._report(world, ending_id, explanation, success)
        out.append(world.record(EventKind.RUN_ENDED, f"{TITLES[ending_id]}. {explanation}", ending=ending_id.value))
        return out

    def _report(self, world: WorldState, ending_id: EndingId, explanation: str, success: bool) -> EndingResult:
        routes: dict[str, list[str]] = {cid: [world.locations["harbour"].name] for cid in world.characters}
        for e in world.events:
            if e.kind is EventKind.ARRIVED and e.actor and e.location_id:
                routes[e.actor].append(world.locations[e.location_id].name)
        adaptations = [f"{e.time}s {e.description}" for e in world.events
                       if e.kind is EventKind.PLAN_CHANGED and e.data.get("adaptation")]
        key_events = [f"{e.time}s {e.description}" for e in world.events if IMPORTANCE.get(e.kind, 0) >= 4]
        stats = {
            "simulated_seconds": world.clock.now,
            "events": len(world.events),
            "failed_actions": sum(m.failed_actions for m in world.minds.values())
                              + sum(1 for e in world.events if e.kind is EventKind.ACTION_FAILED),
            "blocked_route_events": sum(1 for e in world.events if e.kind is EventKind.ROUTE_BLOCKED),
            "replans": sum(m.replans for m in world.minds.values()),
            "adaptations": len(adaptations),
            "traps_sprung": sum(1 for e in world.events if e.kind is EventKind.TRAP_SPRUNG),
        }
        return EndingResult(
            ending=ending_id, title=TITLES[ending_id], main_success=success, finished_at=world.clock.now,
            explanation=explanation, summary=self._summary(world, ending_id, success),
            objectives=[o.model_copy() for o in world.story.objectives],
            routes=routes, adaptations=adaptations, key_events=key_events, stats=stats,
        )

    @staticmethod
    def _summary(world: WorldState, ending_id: EndingId, success: bool) -> str:
        """A factual narrative built only from recorded events."""
        def who(kind: EventKind, **match) -> str | None:
            e = next((e for e in world.events if e.kind is kind and all(e.data.get(k) == v for k, v in match.items())), None)
            return world.name(e.actor) if e and e.actor else None

        parts = []
        if r := who(EventKind.BRIDGE_REPAIRED):
            parts.append(f"{r} repaired the Main Bridge")
        if d := who(EventKind.ROUTE_DISCOVERED, route_id=FOREST_TRAIL):
            parts.append(f"{d} found the hidden forest trail")
        if g := who(EventKind.GATE_OPENED):
            parts.append(f"{g} opened the temple gate")
        if c := who(EventKind.ITEM_PICKED_UP, object_id=SUN_CRYSTAL):
            parts.append(f"{c} carried the Sun Crystal out of the chamber")
        if a := who(EventKind.LIGHTHOUSE_ACTIVATED):
            parts.append(f"{a} lit the beacon at {world.lighthouse.activated_at}s")
        story = ", ".join(parts) if parts else "the team never got far"
        if success:
            return f"{story[0].upper() + story[1:]}. {TITLES[ending_id]}: Aether's barrier rises again."
        return f"{story[0].upper() + story[1:]}. But the storm reached Aether before the light returned."
