"""Gameplay analytics for one run, built only from its recorded events (for the gameplay graphs).

- Timeline: for each character, when it was travelling and when it was working on a task.
  Any other time counts as waiting (standing by, or deciding).
- Mission progress: when each story beat was reached.
- Decisions: plan changes, adaptations, AI choices, lessons used and failed actions per character.
"""

from pydantic import BaseModel

from app.models.enums import EventKind
from app.models.world import WorldState


class Segment(BaseModel):
    start: int
    end: int
    kind: str  # travel | work
    label: str


class CharacterTimeline(BaseModel):
    id: str
    name: str
    color: str
    segments: list[Segment]
    travel: int   # seconds
    work: int
    waiting: int


class BeatPoint(BaseModel):
    time: int
    title: str
    reached: int  # beats reached so far, including this one


class DecisionCounts(BaseModel):
    id: str
    name: str
    color: str
    plan_changes: int
    adaptations: int
    ai_choices: int
    lessons_used: int
    failed_actions: int


class RunAnalytics(BaseModel):
    duration: int
    deadline: int | None
    beats_total: int
    progress: list[BeatPoint]
    timelines: list[CharacterTimeline]
    decisions: list[DecisionCounts]


def _end_of_run(world: WorldState) -> int:
    return world.story.ending.finished_at if world.story.ending else world.clock.now


def run_analytics(world: WorldState) -> RunAnalytics:
    end = max(1, _end_of_run(world))
    segments: dict[str, list[Segment]] = {cid: [] for cid in world.characters}
    places = world.locations
    for e in world.events:
        if e.actor not in segments:
            continue
        if e.kind is EventKind.TRAVEL_STARTED:
            to = e.data.get("destination")
            stop = min(int(e.data.get("arrive_at", e.time)), end)
            label = f"Travel to the {places[to].name}" if to in places else "Travel"
            segments[e.actor].append(Segment(start=e.time, end=stop, kind="travel", label=label))
        elif e.kind is EventKind.ACTION_STARTED:
            stop = min(int(e.data.get("completes_at", e.time)), end)
            action = str(e.data.get("action", "task")).replace("_", " ")
            segments[e.actor].append(Segment(start=e.time, end=stop, kind="work", label=action.capitalize()))

    timelines = []
    for cid in sorted(world.characters):
        segs = [s for s in segments[cid] if s.end > s.start]
        travel = sum(s.end - s.start for s in segs if s.kind == "travel")
        work = sum(s.end - s.start for s in segs if s.kind == "work")
        p = world.profiles[cid]
        timelines.append(CharacterTimeline(id=cid, name=p.name, color=p.color, segments=segs, travel=travel,
                                           work=work, waiting=max(0, end - travel - work)))

    reached = sorted((b for b in world.story.beats if b.reached_at is not None), key=lambda b: b.reached_at or 0)
    progress = [BeatPoint(time=b.reached_at or 0, title=b.title, reached=i + 1) for i, b in enumerate(reached)]

    decisions = []
    for cid in sorted(world.characters):
        mine = [e for e in world.events if e.actor == cid]
        p = world.profiles[cid]
        decisions.append(DecisionCounts(
            id=cid, name=p.name, color=p.color,
            plan_changes=sum(1 for e in mine if e.kind is EventKind.PLAN_CHANGED),
            adaptations=sum(1 for e in mine if e.kind is EventKind.PLAN_CHANGED and e.data.get("adaptation")),
            ai_choices=sum(1 for e in mine if e.kind is EventKind.LLM_DELIBERATION and e.data.get("applied")),
            lessons_used=sum(1 for e in mine if e.kind is EventKind.LESSON_APPLIED),
            failed_actions=world.minds[cid].failed_actions,
        ))
    return RunAnalytics(duration=end, deadline=world.clock.deadline, beats_total=len(world.story.beats),
                        progress=progress, timelines=timelines, decisions=decisions)
