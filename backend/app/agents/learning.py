"""Learning across games: reflect on a finished run, then test one lesson at a time.

After a Watch (Default Mode) run, each character looks back at its waiting log: long stretches
spent waiting while its own rules offered something else to do. That becomes a candidate
lesson in words ("Last time I waited 110s at the temple. Next time: decode the symbols
myself."), stored in the team journal. The next Watch run tries it, and the result decides:
better ending or same ending sooner -> kept; otherwise -> rejected, with the reason.

Watch runs are deterministic, so the only difference between the two runs is the lesson:
any change in the result is caused by it. One lesson is tested at a time for the same reason.
A lesson can only ever pick one of the rules' own options, so learning never breaks a rule.
"""

from dataclasses import dataclass

from app.models.enums import EndingId
from app.models.mind import OptionTrace, WaitEpisode
from app.models.world import WorldState

MIN_WAIT_SECONDS = 30  # shorter waits are normal teamwork, not worth a lesson

# How good an ending is, best first. A lesson is kept only if it reaches a better ending, or the same one sooner.
ENDING_RANK = {
    EndingId.LIGHT_RETURNS: 4,
    EndingId.UNEXPECTED_ROUTE: 3,
    EndingId.COSTLY_VICTORY: 2,
    EndingId.LAST_STORM: 1,
}
ENDING_TITLES = {
    EndingId.LIGHT_RETURNS: "The Light Returns",
    EndingId.COSTLY_VICTORY: "A Costly Victory",
    EndingId.UNEXPECTED_ROUTE: "An Unexpected Route",
    EndingId.LAST_STORM: "The Last Storm",
}


@dataclass(frozen=True)
class Candidate:
    character_id: str
    instead_of: str
    prefer: str
    waited: int
    text: str
    evidence: str


def _waited(episode: WaitEpisode, end: int) -> int:
    return (episode.ended_at if episode.ended_at is not None else end) - episode.started_at


def lesson_text(world: WorldState, episode: WaitEpisode, alternative: OptionTrace, waited: int) -> str:
    place = world.locations[episode.location_id].name if episode.location_id in world.locations else "the island"
    return f"Last time I waited {waited}s at the {place}. Next time: {alternative.summary}"


def candidates(world: WorldState) -> list[Candidate]:
    """Lessons worth testing, longest wait first: for each long wait, each other option the rules offered."""
    end = world.story.ending.finished_at if world.story.ending else world.clock.now
    found: list[tuple[int, int, Candidate]] = []
    for cid in sorted(world.minds):
        if cid == world.story.player_character:
            continue  # the player's choices are the player's, not a character's lesson
        for episode in world.minds[cid].wait_log:
            waited = _waited(episode, end)
            if waited < MIN_WAIT_SECONDS:
                continue
            for rank, alt in enumerate(episode.alternatives):
                found.append((waited, -rank, Candidate(
                    character_id=cid, instead_of=episode.strategy, prefer=alt.strategy, waited=waited,
                    text=lesson_text(world, episode, alt, waited),
                    evidence=f"{world.name(cid)} spent {waited}s on: {episode.summary}",
                )))
    found.sort(key=lambda f: (-f[0], -f[1]))
    return [c for _, _, c in found]


def score(ending: EndingId, seconds: int) -> tuple[int, int]:
    return ENDING_RANK[ending], -seconds


def verdict(baseline: tuple[EndingId, int], tested: tuple[EndingId, int]) -> tuple[bool, str]:
    """Keep the lesson only if the run that used it did better than the run it was learned from."""
    (b_end, b_sec), (t_end, t_sec) = baseline, tested
    if score(t_end, t_sec) > score(b_end, b_sec):
        if t_end != b_end:
            return True, f"It helped: {ENDING_TITLES[t_end]} instead of {ENDING_TITLES[b_end]}."
        return True, f"It helped: the beacon was lit {b_sec - t_sec}s sooner ({t_sec}s instead of {b_sec}s)."
    if t_end != b_end:
        return False, f"It made things worse: {ENDING_TITLES[t_end]} instead of {ENDING_TITLES[b_end]}."
    if t_sec > b_sec:
        return False, f"It made things worse: {t_sec - b_sec}s slower ({t_sec}s instead of {b_sec}s)."
    return False, "It made no difference, so it is not worth remembering."
