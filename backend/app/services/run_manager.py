"""Owns live runs: authorisation, serialized state changes, the real-time driver, LLM work and persistence.

Every mutation of a run happens while holding that run's asyncio.Lock, so the driver's ticks,
player actions, LLM results and saves never interleave. The backend clock is authoritative: the
driver advances it on a wall-clock schedule, and nothing a client sends can move it backwards.

LLM calls never happen while the lock is held, and nothing waits for them: characters keep acting
on their rule-based plans, and an LLM answer is applied afterwards only if it is still valid.
"""

import asyncio
import contextlib
import hashlib
import hmac
import logging
import secrets
from collections.abc import Coroutine
from dataclasses import dataclass, field
from typing import Any

from app.agents import dialogue, storyteller
from app.agents.commands import Interpretation, interpreter_messages, parse_fallback, parse_interpretation
from app.agents.planner import Decision, FallbackPlanner
from app.agents.prompts import (
    MAX_CHAPTER_CHARS, MAX_NARRATION_CHARS, MAX_REPLY_CHARS, chapter_messages, clean_text, deliberation_messages,
    dialogue_messages, narration_messages, parse_choice,
)
from app.core.config import Settings
from app.engine.run import Run, RunError
from app.models.actions import ActionResult, ProposedAction
from app.models.enums import ActionType, EventKind, GameMode, RunStatus
from app.models.world import WorldState
from app.persistence.repository import RunRepository
from app.services.llm import LLMResponse, LLMService
from app.services.rate_limit import TokenBucket

log = logging.getLogger(__name__)

MAX_ADVANCE_TICKS = 120
PREFERENCE_TTL_SECONDS = 90  # how long an LLM strategy preference stays in force


class RunNotFound(LookupError):
    pass


class NotAuthorized(PermissionError):
    pass


class RateLimited(RuntimeError):
    pass


class Conflict(RuntimeError):
    pass


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


@dataclass
class ManagedRun:
    run: Run
    token_hash: str
    limiter: TokenBucket
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    paused: bool = False
    task: asyncio.Task | None = None
    last_history_at: int = 0
    pending_triggers: dict[str, str] = field(default_factory=dict)  # character -> latest trigger
    deliberating: set[str] = field(default_factory=set)
    narration_requested: bool = False
    chapters_requested: set[int] = field(default_factory=set)

    @property
    def world(self) -> WorldState:
        return self.run.world


class RunManager:
    def __init__(self, settings: Settings, repo: RunRepository, llm: LLMService | None = None):
        self.settings = settings
        self.repo = repo
        self.llm = llm
        self._runs: dict[str, ManagedRun] = {}
        self._create_lock = asyncio.Lock()
        self._ai_tasks: set[asyncio.Task] = set()

    # --- lookup & auth ------------------------------------------------------------------------------

    def _wrap(self, world: WorldState, token_hash: str) -> ManagedRun:
        s = self.settings
        pending: dict[str, str] = {}
        run = Run(world, on_trigger=lambda cid, trigger: pending.__setitem__(cid, trigger))
        return ManagedRun(run=run, token_hash=token_hash, pending_triggers=pending,
                          limiter=TokenBucket(s.player_requests_per_second, s.player_request_burst),
                          last_history_at=world.clock.now)

    async def get(self, run_id: str, token: str | None) -> ManagedRun:
        managed = self._runs.get(run_id)
        if managed is None:
            loaded = self.repo.load(run_id)
            if loaded is None:
                raise RunNotFound(run_id)
            world, token_hash = loaded
            managed = self._runs.setdefault(run_id, self._wrap(world, token_hash))
        if token is None or not hmac.compare_digest(managed.token_hash, _hash(token)):
            raise NotAuthorized(run_id)
        self._ensure_driver(managed)
        return managed

    # --- lifecycle --------------------------------------------------------------------------------------

    async def create(self, mode: GameMode, player_character: str | None) -> tuple[ManagedRun, str]:
        world = Run.create(
            mode, player_character, tick_seconds=self.settings.sim_tick_seconds,
            deadline_seconds=self.settings.game_deadline_seconds,
        ).world  # raises RunError on a bad configuration
        token = secrets.token_urlsafe(24)
        managed = self._wrap(world, _hash(token))
        async with self._create_lock:
            self.repo.create(world, managed.token_hash)
            self._runs[world.run_id] = managed
        return managed, token

    async def start(self, m: ManagedRun) -> None:
        async with m.lock:
            if m.run.status is RunStatus.CREATED:
                m.run.start()
                self._after_change(m)
        self._ensure_driver(m)

    async def restart(self, m: ManagedRun) -> tuple[ManagedRun, str]:
        """A restart is a brand-new run from the same starting world; the old one is abandoned."""
        async with m.lock:
            m.run.abandon()
            self._persist(m, history=True)
        await self._stop_driver(m)
        world = m.world
        return await self.create(world.mode, world.story.player_character)

    async def pause(self, m: ManagedRun, paused: bool) -> None:
        if m.world.mode is GameMode.GAME and paused:
            raise Conflict("Game Mode cannot be paused: the storm does not wait.")
        async with m.lock:
            m.paused = paused

    # --- player input ------------------------------------------------------------------------------------

    def _check_rate(self, m: ManagedRun) -> None:
        if not m.limiter.allow():
            raise RateLimited("Too many requests for this run; slow down.")

    async def act(self, m: ManagedRun, action: ProposedAction, request_id: str | None) -> ActionResult:
        self._check_rate(m)
        llm_reply = (self.llm is not None and action.type is ActionType.TALK
                     and action.target_id in m.run.agents)
        async with m.lock:
            result = m.run.player_action(action, request_id=request_id, auto_reply=not llm_reply)
            if result.ok and not result.duplicate:
                self._after_change(m)
            if not (llm_reply and result.ok and not result.duplicate):
                return result
            target = action.target_id or ""
            messages = dialogue_messages(m.world, target, action.actor, action.message or "Hello.")

        # The lock is released while the model thinks, so the world keeps running.
        assert self.llm is not None
        response = await self.llm.complete(messages, max_tokens=200, temperature=0.8)
        text = clean_text(response.text, MAX_REPLY_CHARS) if response else None
        async with m.lock:
            ai = m.world.story.ai
            if text and response:
                ai.llm_replies += 1
                self._count_call(m, response)
                generated_by = response.label
            else:
                ai.template_replies += 1
                text, generated_by = dialogue.reply(m.world, target, action.actor), "template"
            if m.run.status is RunStatus.RUNNING:
                result.events.append(m.run.record_reply(target, action.actor, text, generated_by))
                self._after_change(m)
        return result

    async def command(self, m: ManagedRun, text: str, request_id: str | None) -> ActionResult:
        """A typed or spoken instruction: interpret it (LLM, else keyword parser), then let the Run validate it."""
        self._check_rate(m)
        story = m.world.story
        if request_id is not None and request_id in story.processed_requests:
            return story.processed_requests[request_id].model_copy(update={"duplicate": True})
        player = story.player_character or ""
        async with m.lock:
            messages = interpreter_messages(m.world, player, text) if player else []
        interpretation: Interpretation | None = None
        by = "keyword parser"
        if self.llm is not None and messages:
            response = await self.llm.complete(messages, max_tokens=500, temperature=0.1)
            if response:
                async with m.lock:
                    self._count_call(m, response)
                parsed = parse_interpretation(response.text)
                if parsed is not None and parsed.steps:
                    interpretation, by = parsed, response.label
            if interpretation is None:
                by = "keyword parser (LLM unavailable or unclear)"
        async with m.lock:
            if interpretation is None:
                interpretation = parse_fallback(m.world, player, text)
            result = m.run.give_command(text, interpretation, by)
            if request_id is not None:
                story.processed_requests[request_id] = result
            if result.ok:
                self._after_change(m)
            return result

    async def say(self, m: ManagedRun, text: str, request_id: str | None) -> ActionResult:
        """'Say' on the radio: teammates hear it and answer in character, but take no orders from it."""
        self._check_rate(m)
        story = m.world.story
        if request_id is not None and request_id in story.processed_requests:
            return story.processed_requests[request_id].model_copy(update={"duplicate": True})
        async with m.lock:
            result = m.run.radio_say(text)
            if request_id is not None:
                story.processed_requests[request_id] = result
            if not result.ok:
                return result
            self._after_change(m)
            world = m.world
            player = story.player_character or ""
            lowered = text.lower()
            named = [cid for cid in m.run.agents if world.name(cid).lower() in lowered]
            listeners = named or sorted(m.run.agents)
            prompts = {cid: dialogue_messages(world, cid, player, text, radio=True) for cid in listeners}

        async def answer(cid: str) -> tuple[str, LLMResponse | None]:
            if self.llm is None:
                return cid, None
            return cid, await self.llm.complete(prompts[cid], max_tokens=200, temperature=0.8)

        answers = await asyncio.gather(*(answer(cid) for cid in listeners))
        async with m.lock:
            ai = m.world.story.ai
            for cid, response in answers:
                reply = clean_text(response.text, MAX_REPLY_CHARS) if response else None
                if reply and response:
                    ai.llm_replies += 1
                    self._count_call(m, response)
                    by = response.label
                else:
                    ai.template_replies += 1
                    reply, by = dialogue.reply(m.world, cid, player), "template"
                if m.run.status is RunStatus.RUNNING:
                    result.events.append(m.run.record_reply(cid, player, reply, by))
            self._after_change(m)
        return result

    async def twist(self, m: ManagedRun, text: str, request_id: str | None) -> ActionResult:
        """'Story': map the player's twist onto the catalogue (LLM picks a number, else keywords), then apply."""
        self._check_rate(m)
        story = m.world.story
        if request_id is not None and request_id in story.processed_requests:
            return story.processed_requests[request_id].model_copy(update={"duplicate": True})
        async with m.lock:
            early = m.run.add_twist(text, None, "", "") if not m.run.can_add_twist() else None
            if early is not None:
                return early  # the explanation of why no twist is possible, without spending an LLM call
            options = storyteller.options(m.world)
            messages = storyteller.twist_messages(m.world, text, options)
        chosen: storyteller.Twist | None = None
        by = "keyword parser"
        if self.llm is not None and options:
            response = await self.llm.complete(messages, max_tokens=200, temperature=0.1)
            pick = storyteller.parse_twist_choice(response.text, len(options)) if response else None
            if response:
                async with m.lock:
                    self._count_call(m, response)
            if response and pick:
                chosen, by = options[pick - 1], response.label
            elif pick is None:
                by = "keyword parser (LLM unavailable or unclear)"
        async with m.lock:
            note = ""
            if chosen is None:  # the LLM found no match (or was unavailable): try the keywords
                chosen, note = storyteller.parse_fallback(m.world, text)
            result = m.run.add_twist(text, chosen, by, note)
            if request_id is not None:
                story.processed_requests[request_id] = result
            if result.ok:
                self._after_change(m)
            return result

    async def advance(self, m: ManagedRun, ticks: int) -> None:
        """Fast-forward simulated time (never backwards). Allowed in both modes; it only spends time."""
        self._check_rate(m)
        if not 1 <= ticks <= MAX_ADVANCE_TICKS:
            raise Conflict(f"ticks must be between 1 and {MAX_ADVANCE_TICKS}")
        async with m.lock:
            if m.run.status is not RunStatus.RUNNING:
                raise Conflict(f"The run is {m.run.status.value}; time cannot be advanced.")
            for _ in range(ticks):
                if m.run.status is not RunStatus.RUNNING:
                    break
                m.run.tick()
                self._after_change(m)  # same cadence as the real-time driver

    # --- real-time driver ----------------------------------------------------------------------------------

    def speed(self, m: ManagedRun) -> float:
        s = self.settings
        return s.game_sim_speed if m.world.mode is GameMode.GAME else s.default_sim_speed

    def _ensure_driver(self, m: ManagedRun) -> None:
        if not self.settings.sim_autorun or m.run.status is not RunStatus.RUNNING:
            return
        if m.task is None or m.task.done():
            m.task = asyncio.get_running_loop().create_task(self._drive(m), name=f"run-{m.world.run_id}")

    async def _drive(self, m: ManagedRun) -> None:
        interval = m.world.clock.tick_seconds / self.speed(m)
        try:
            while True:
                await asyncio.sleep(interval)
                async with m.lock:
                    if m.run.status is not RunStatus.RUNNING:
                        return
                    if m.paused:
                        continue
                    m.run.tick()
                    self._after_change(m)
        except asyncio.CancelledError:
            raise
        except Exception:  # pragma: no cover - logged so a crashed driver is visible, not silent
            log.exception("driver for run %s crashed", m.world.run_id)

    async def _stop_driver(self, m: ManagedRun) -> None:
        if m.task is not None and not m.task.done():
            m.task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await m.task
        m.task = None

    async def shutdown(self) -> None:
        for task in list(self._ai_tasks):
            task.cancel()
        for m in list(self._runs.values()):
            await self._stop_driver(m)
            async with m.lock:
                self._persist(m, history=True)

    # --- LLM work (always in the background) ------------------------------------------------------------

    def _spawn(self, coro: Coroutine[Any, Any, None]) -> None:
        task = asyncio.get_running_loop().create_task(coro)
        self._ai_tasks.add(task)
        task.add_done_callback(self._ai_tasks.discard)

    @staticmethod
    def _count_call(m: ManagedRun, response: LLMResponse) -> None:
        ai = m.world.story.ai
        ai.calls_succeeded += 1
        ai.total_latency_ms += response.latency_ms
        ai.providers[response.label] = ai.providers.get(response.label, 0) + 1

    def _schedule_ai(self, m: ManagedRun) -> None:
        """Called under the lock after every change: queue deliberations and the ending epilogue."""
        world = m.world
        if self.llm is None:
            m.pending_triggers.clear()
            return
        for chapter in world.story.chapters:
            if chapter.generated_by == "template" and chapter.id not in m.chapters_requested:
                m.chapters_requested.add(chapter.id)
                self._spawn(self._write_chapter(m, chapter.id, chapter_messages(world, chapter.id)))
        ending = world.story.ending
        if ending is not None and ending.narration is None and not m.narration_requested:
            m.narration_requested = True
            self._spawn(self._narrate(m, narration_messages(world)))
        if world.mode is not GameMode.GAME or m.run.status is not RunStatus.RUNNING:
            m.pending_triggers.clear()  # Default Mode stays deterministic: no LLM strategy changes
            return
        planner = FallbackPlanner()
        for cid, trigger in list(m.pending_triggers.items()):
            del m.pending_triggers[cid]
            mind = world.minds[cid]
            if cid in m.deliberating or mind.deliberations >= self.settings.llm_max_deliberations_per_run:
                continue
            options = planner.options(world, cid)
            if len(options) < 2:
                continue  # nothing to choose between
            mind.deliberations += 1
            world.story.ai.deliberations_requested += 1
            m.deliberating.add(cid)
            self._spawn(self._deliberate(m, cid, options, deliberation_messages(world, cid, trigger, options)))

    async def _deliberate(self, m: ManagedRun, cid: str, options: list[Decision],
                          messages: list[dict[str, str]]) -> None:
        try:
            assert self.llm is not None
            response = await self.llm.complete(messages, max_tokens=300, temperature=0.4)
            async with m.lock:
                world = m.world
                ai = world.story.ai
                if response:
                    self._count_call(m, response)
                if m.run.status is not RunStatus.RUNNING:
                    ai.deliberations_discarded += 1
                    self._persist(m)
                    return
                choice = parse_choice(response.text, len(options)) if response else None
                if response:
                    if choice is None:
                        ai.invalid_answers += 1
                chosen = options[choice.choice - 1] if choice else None
                still_valid = {d.strategy for d in FallbackPlanner().options(world, cid)}
                name = world.name(cid)
                here = world.characters[cid].location_id
                label = response.label if response else None
                if chosen is None or chosen.strategy not in still_valid:
                    ai.fallbacks += 1
                    reason = ("no answer from the LLM" if response is None else
                              "the LLM's answer was not a valid option" if choice is None else
                              "the LLM's choice no longer applies")
                    world.record(EventKind.LLM_DELIBERATION, f"{name} keeps the default plan ({reason}).",
                                 actor=cid, location_id=here, applied=False, reason=reason, generated_by=label)
                else:
                    mind = world.minds[cid]
                    mind.preferred_strategy = chosen.strategy
                    mind.preference_expires_at = world.clock.now + PREFERENCE_TTL_SECONDS
                    ai.deliberations_applied += 1
                    thought = f' "{choice.thought}"' if choice and choice.thought else ""
                    world.record(
                        EventKind.LLM_DELIBERATION, f"{name} weighs the options:{thought} Choice: {chosen.summary}",
                        actor=cid, location_id=here, applied=True, choice=choice.choice if choice else None,
                        strategy=chosen.strategy, default_strategy=options[0].strategy,
                        options=[d.strategy for d in options], generated_by=label,
                        latency_ms=response.latency_ms if response else None,
                    )
                self._persist(m)
        finally:
            m.deliberating.discard(cid)

    async def _write_chapter(self, m: ManagedRun, chapter_id: int, messages: list[dict[str, str]]) -> None:
        """Replace a template storybook page with LLM prose. The template stays if the LLM has no answer."""
        assert self.llm is not None
        response = await self.llm.complete(messages, max_tokens=300, temperature=0.8)
        text = clean_text(response.text, MAX_CHAPTER_CHARS) if response else None
        if not (text and response):
            return
        async with m.lock:
            chapters = m.world.story.chapters
            if chapter_id <= len(chapters) and chapters[chapter_id - 1].generated_by == "template":
                chapters[chapter_id - 1].text, chapters[chapter_id - 1].generated_by = text, response.label
                self._count_call(m, response)
                self._persist(m)

    async def _narrate(self, m: ManagedRun, messages: list[dict[str, str]]) -> None:
        assert self.llm is not None
        response = await self.llm.complete(messages, max_tokens=300, temperature=0.7)
        text = clean_text(response.text, MAX_NARRATION_CHARS) if response else None
        if not (text and response):
            return
        async with m.lock:
            ending = m.world.story.ending
            if ending is not None and ending.narration is None:
                ending.narration, ending.narrated_by = text, response.label
                self._count_call(m, response)
                self._persist(m)

    # --- persistence ---------------------------------------------------------------------------------------

    def _after_change(self, m: ManagedRun) -> None:
        self._persist(m)
        self._schedule_ai(m)

    def _persist(self, m: ManagedRun, history: bool = False) -> None:
        world = m.world
        due = world.clock.now - m.last_history_at >= self.settings.snapshot_interval_seconds
        finished = world.story.status in (RunStatus.FINISHED, RunStatus.ABANDONED)
        if history or due or finished:
            m.last_history_at = world.clock.now
        self.repo.save(world, history=history or due or finished)


__all__ = ["RunManager", "ManagedRun", "RunNotFound", "NotAuthorized", "RateLimited", "Conflict", "RunError"]
