"""The team journal: lessons that carry over from one game to the next.

- When a run is created, its autonomous characters receive the lessons that were kept, and in
  a Watch run also the one lesson currently being tried.
- When a run finishes, the journal records it. After a Watch run it first judges the lesson
  that was being tried (kept or rejected, see ``learning.verdict``), then reflects on the run
  and writes at most one new lesson to try next time.

Game Mode runs use kept lessons but never test new ones: a player changes too much for a fair test.
"""

from app.agents.learning import ENDING_TITLES, candidates, verdict
from app.engine.aether import PROFILES
from app.models.enums import EndingId, GameMode
from app.models.mind import ActiveLesson
from app.models.world import WorldState
from app.persistence.repository import RunRepository

NAMES = {p.id: p.name for p in PROFILES}


class TeamJournal:
    def __init__(self, repo: RunRepository):
        self.repo = repo

    def lessons_for(self, mode: GameMode, player_character: str | None) -> dict[str, list[ActiveLesson]]:
        out: dict[str, list[ActiveLesson]] = {}
        for row in self.repo.lessons(statuses=("kept", "trying")):
            if row.character_id == player_character:
                continue
            if row.status == "trying" and mode is not GameMode.DEFAULT:
                continue
            out.setdefault(row.character_id, []).append(ActiveLesson(
                id=row.id, instead_of=row.instead_of, prefer=row.prefer, text=row.text, status=row.status))
        return out

    def after_finish(self, world: WorldState) -> None:
        """Record a finished run once; after a Watch run, judge the lesson on trial and learn a new one."""
        ending = world.story.ending
        if ending is None or self.repo.journal_has(world.run_id):
            return
        seconds = ending.finished_at
        used = sorted({i for mind in world.minds.values() for i in mind.lessons_used})
        notes: list[str] = []
        if world.mode is GameMode.DEFAULT:
            rejected = False
            trials = {le.id: cid for cid, mind in world.minds.items() for le in mind.lessons if le.status == "trying"}
            for lesson_id, cid in trials.items():
                row = self.repo.lesson(lesson_id)
                if row is None or row.status != "trying":
                    continue
                if lesson_id in used:
                    kept, result = verdict((EndingId(row.baseline_ending), row.baseline_seconds), (ending.ending, seconds))
                else:
                    kept, result = False, "The situation never came up, so it could not be tested."
                self.repo.update_lesson(lesson_id, status="kept" if kept else "rejected", tested_in_run=world.run_id,
                                        tested_ending=ending.ending.value, tested_seconds=seconds, result=result)
                notes.append(f"{NAMES.get(cid, cid)} tried a lesson. {result} "
                             + ("Lesson kept." if kept else "Lesson dropped."))
                rejected = rejected or not kept
            if rejected:
                notes.append("The next Watch run goes back to the lessons that worked.")
            elif not self.repo.lessons(statuses=("trying",)):
                known = {(r.character_id, r.instead_of, r.prefer) for r in self.repo.lessons()}
                fresh = [c for c in candidates(world) if (c.character_id, c.instead_of, c.prefer) not in known]
                if fresh:
                    c = fresh[0]
                    self.repo.add_lesson(
                        character_id=c.character_id, instead_of=c.instead_of, prefer=c.prefer, text=c.text,
                        evidence=c.evidence, status="trying", learned_in_run=world.run_id,
                        baseline_ending=ending.ending.value, baseline_seconds=seconds,
                    )
                    notes.append(f"{NAMES.get(c.character_id, c.character_id)} wrote a new lesson to try next time: "
                                 f"\"{c.text}\"")
                else:
                    notes.append("No long waits left to learn from: the team plays as well as it knows how.")
        elif used:
            notes.append(f"The team used {len(used)} lesson(s) from earlier Watch runs.")
        self.repo.add_journal_run(
            run_id=world.run_id, mode=world.mode.value, player_character=world.story.player_character,
            ending=ending.ending.value, finished_at=seconds, lessons_used=used, note=" ".join(notes),
        )


__all__ = ["TeamJournal", "ENDING_TITLES", "NAMES"]
