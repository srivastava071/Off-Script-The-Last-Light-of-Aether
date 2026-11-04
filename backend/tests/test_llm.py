"""LLM integration, tested with fake providers (no network, no keys)."""

import asyncio
import json
import time

import pytest
from fastapi.testclient import TestClient

from app.agents.planner import FallbackPlanner
from app.agents.prompts import deliberation_messages, parse_choice, situation
from app.core.config import AIProvider, Settings
from app.engine.aether import ARIA, BRIDGE, KABIR
from app.main import create_app
from app.services.llm import LLMError, LLMService


class FakeProvider:
    def __init__(self, name="fake", model="m1", reply=None, error=None, retryable=True):
        self.name, self.model = name, model
        self.reply = reply  # str, or callable(messages) -> str
        self.error, self.retryable = error, retryable
        self.calls: list[list[dict]] = []

    async def chat(self, messages, *, max_tokens, temperature):
        self.calls.append(messages)
        if self.error:
            raise LLMError(self.error, retryable=self.retryable)
        return self.reply(messages) if callable(self.reply) else self.reply


def service(*providers, per_minute=100, retries=0):
    return LLMService(list(providers), max_calls_per_minute=per_minute, max_retries=retries)


# --- service reliability ---------------------------------------------------------------------------------

def test_fails_over_to_next_provider():
    bad = FakeProvider("groq", error="HTTP 429", retryable=True)
    good = FakeProvider("gemini", reply="hello")
    svc = service(bad, good, retries=1)
    out = asyncio.run(svc.complete([{"role": "user", "content": "hi"}]))
    assert out.text == "hello" and out.provider == "gemini"
    assert len(bad.calls) == 2  # retried once, then moved on
    assert svc.stats.failures == 2 and svc.stats.successes == 1


def test_non_retryable_error_skips_straight_to_next_provider():
    bad = FakeProvider("groq", error="HTTP 404 model not found", retryable=False)
    svc = service(bad, FakeProvider("gemini", reply="ok"), retries=3)
    assert asyncio.run(svc.complete([])).provider == "gemini"
    assert len(bad.calls) == 1


def test_never_raises_and_returns_none_when_all_fail():
    svc = service(FakeProvider("a", error="down"), FakeProvider("b", error="down"))
    assert asyncio.run(svc.complete([])) is None


def test_per_minute_budget_protects_free_tiers():
    p = FakeProvider(reply="ok")
    svc = service(p, per_minute=2)
    results = [asyncio.run(svc.complete([])) for _ in range(4)]
    assert [r is not None for r in results] == [True, True, False, False]
    assert svc.stats.skipped_budget == 2 and len(p.calls) == 2


# --- parsing and grounding ---------------------------------------------------------------------------------

@pytest.mark.parametrize("text,expected", [
    ('{"choice": 2, "thought": "Faster."}', 2),
    ('```json\n{"choice": 1, "thought": "ok"}\n```', 1),
    ('<think>hmm, option 3?</think>{"choice": 3, "thought": "go"}', 3),
    ('Sure! {"choice": 2} is my pick', 2),
])
def test_parse_choice_accepts_valid_answers(text, expected):
    assert parse_choice(text, 3).choice == expected


@pytest.mark.parametrize("text", ['{"choice": 7}', '{"choice": 0}', "I pick two", '{"choice": "two"}', ""])
def test_parse_choice_rejects_anything_else(text):
    assert parse_choice(text, 3) is None


def test_prompts_only_contain_what_the_character_knows(world):
    world.routes["forest_trail"].hidden = False  # true world: the trail exists...
    text = situation(world, KABIR)                 # ...but Kabir has not learned about it
    assert "Hidden Forest Trail" not in text
    assert "Main Bridge is broken" in text


def test_prompts_say_which_routes_the_character_cannot_use(world):
    assert "Ravine Climb is open" in situation(world, KABIR)
    assert "you CANNOT use it" in situation(world, KABIR)
    assert "you can]" in situation(world, ARIA)


def test_deliberation_prompt_lists_planner_options(world):
    options = FallbackPlanner().options(world, KABIR)
    msgs = deliberation_messages(world, KABIR, "Something changed.", options)
    assert all(o.summary in msgs[1]["content"] for o in options)
    assert "JSON" in msgs[0]["content"]


# --- end to end through the API ------------------------------------------------------------------------------

def live_settings(tmp_path, **kw) -> Settings:
    values = dict(database_url=f"sqlite:///{(tmp_path / 'llm.db').as_posix()}", sim_autorun=False,
                  ai_provider=AIProvider.OPENAI_COMPATIBLE, groq_api_key="unused-in-tests") | kw
    return Settings(_env_file=None, **values)


def started(c, **body):
    body = {"mode": "game", "player_character": "aria"} | body
    data = c.post("/api/runs", json=body).json()
    h = {"X-Run-Token": data["token"]}
    c.post(f"/api/runs/{data['run_id']}/start", headers=h)
    return data["run_id"], h


def wait_for(fn, timeout=3.0):
    end = time.time() + timeout
    while time.time() < end:
        if (value := fn()):
            return value
        time.sleep(0.02)
    raise AssertionError("timed out")


def deliberation_events(c, run_id, h):
    events = c.get(f"/api/runs/{run_id}/events", headers=h).json()["events"]
    return [e for e in events if e["kind"] == "llm_deliberation"]


def block_bridge_scenario(c):
    run_id, h = started(c)
    c.post(f"/api/runs/{run_id}/actions", json={"type": "move", "destination": BRIDGE}, headers=h)
    c.post(f"/api/runs/{run_id}/advance", json={"ticks": 6}, headers=h)
    r = c.post(f"/api/runs/{run_id}/actions", json={"type": "block_route", "route_id": "main_bridge"}, headers=h)
    assert r.json()["ok"], r.text
    c.post(f"/api/runs/{run_id}/advance", json={"ticks": 6}, headers=h)  # Kabir arrives (t=54) and sees the debris
    return run_id, h


def test_llm_choice_changes_the_agents_strategy(tmp_path):
    def choose_second(messages):
        return json.dumps({"choice": 2, "thought": "Let me try the other way."})
    fake = FakeProvider("fake", "m1", reply=choose_second)
    with TestClient(create_app(live_settings(tmp_path), llm=service(fake))) as c:
        run_id, h = block_bridge_scenario(c)
        applied = wait_for(lambda: [e for e in deliberation_events(c, run_id, h)
                                    if e["actor"] == KABIR and e["data"]["applied"]])
        d = applied[0]["data"]
        assert d["generated_by"] == "fake:m1" and d["strategy"] == d["options"][1] != d["default_strategy"]
        # Actions in progress are never interrupted: Kabir finishes clearing the debris (t=84), then decides.
        c.post(f"/api/runs/{run_id}/advance", json={"ticks": 6}, headers=h)
        state = c.get(f"/api/runs/{run_id}/state", headers=h).json()
        kabir = next(ch for ch in state["characters"] if ch["id"] == KABIR)
        assert kabir["plan"]["strategy"] == d["strategy"]  # he really acts on the LLM's choice
        events = c.get(f"/api/runs/{run_id}/events", headers=h).json()["events"]
        assert any(e["kind"] == "plan_changed" and e["data"]["planner"] == "llm" for e in events)
        assert state["story"]["ai"]["deliberations_applied"] >= 1


def test_invalid_llm_answer_keeps_the_default_plan(tmp_path):
    fake = FakeProvider(reply="I would rather go fishing.")
    with TestClient(create_app(live_settings(tmp_path), llm=service(fake))) as c:
        run_id, h = block_bridge_scenario(c)
        ev = wait_for(lambda: deliberation_events(c, run_id, h))
        assert ev[0]["data"]["applied"] is False and "not a valid option" in ev[0]["description"]


def test_total_llm_outage_does_not_break_the_game(tmp_path):
    fake = FakeProvider(error="503 overloaded")
    with TestClient(create_app(live_settings(tmp_path), llm=service(fake))) as c:
        run_id, h = block_bridge_scenario(c)
        state = c.post(f"/api/runs/{run_id}/advance", json={"ticks": 120}, headers=h).json()
        assert state["run"]["status"] == "finished"
        assert state["story"]["ending"]["main_success"]  # the rule-based team still saves the island
        r = c.post(f"/api/runs/{run_id}/dialogue", json={"target_id": KABIR, "message": "hi"}, headers=h)
        assert r.status_code == 200  # the run is over, but the request is handled cleanly


def test_dialogue_uses_llm_and_labels_it(tmp_path):
    fake = FakeProvider("fake", "m1", reply='"Let\'s be methodical; the bridge needs timber."')
    with TestClient(create_app(live_settings(tmp_path), llm=service(fake))) as c:
        run_id, h = started(c)
        r = c.post(f"/api/runs/{run_id}/dialogue", json={"target_id": KABIR, "message": "What now?"}, headers=h).json()
        reply = [e for e in r["events"] if e["actor"] == KABIR and e["data"].get("reply")]
        assert reply[0]["data"]["generated_by"] == "fake:m1"
        assert reply[0]["data"]["message"] == "Let's be methodical; the bridge needs timber."
        assert any("What now?" in call[1]["content"] for call in fake.calls)


def test_dialogue_falls_back_to_template_and_says_so(tmp_path):
    with TestClient(create_app(live_settings(tmp_path), llm=service(FakeProvider(error="down")))) as c:
        run_id, h = started(c)
        r = c.post(f"/api/runs/{run_id}/dialogue", json={"target_id": KABIR, "message": "hi"}, headers=h).json()
        reply = [e for e in r["events"] if e["actor"] == KABIR and e["data"].get("reply")]
        assert reply[0]["data"]["generated_by"] == "template"


def test_default_mode_uses_llm_only_for_storytelling(tmp_path):
    """Default Mode stays deterministic: the LLM may narrate the storybook and epilogue, never decide."""
    fake = FakeProvider("fake", "m1", reply="The beacon blazed, and Aether was safe.")
    with TestClient(create_app(live_settings(tmp_path), llm=service(fake))) as c:
        data = c.post("/api/runs", json={"mode": "default"}).json()
        run_id, h = data["run_id"], {"X-Run-Token": data["token"]}
        c.post(f"/api/runs/{run_id}/start", headers=h)
        state = c.post(f"/api/runs/{run_id}/advance", json={"ticks": 120}, headers=h).json()
        assert state["story"]["ending"]["ending"] == "light_returns"  # unchanged by the LLM
        assert deliberation_events(c, run_id, h) == []
        ending = wait_for(lambda: c.get(f"/api/runs/{run_id}/state", headers=h).json()["story"]["ending"]["narration"]
                          and c.get(f"/api/runs/{run_id}/state", headers=h).json()["story"]["ending"])
        assert ending["narration"] == "The beacon blazed, and Aether was safe." and ending["narrated_by"] == "fake:m1"
        assert all("narrator" in call[0]["content"] for call in fake.calls)  # storybook pages and epilogue only


def test_mock_mode_never_claims_llm_output(tmp_path):
    settings = Settings(_env_file=None, database_url=f"sqlite:///{(tmp_path / 'm.db').as_posix()}", sim_autorun=False)
    with TestClient(create_app(settings)) as c:
        run_id, h = started(c)
        assert c.get("/api/health").json()["ai_mode"] == "mock"
        r = c.post(f"/api/runs/{run_id}/dialogue", json={"target_id": KABIR, "message": "hi"}, headers=h).json()
        reply = [e for e in r["events"] if e["actor"] == KABIR and e["data"].get("reply")]
        assert reply[0]["data"]["generated_by"] == "template"
        assert c.get(f"/api/runs/{run_id}/state", headers=h).json()["story"]["ai"]["calls_succeeded"] == 0
