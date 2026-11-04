import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.core.config import AIProvider, Settings, get_settings
from app.main import create_app


def _client(settings: Settings) -> TestClient:
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: settings
    return TestClient(app)


def test_health_reports_mock_mode():
    client = _client(Settings(_env_file=None))
    resp = client.get("/api/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["ai_provider"] == "mock"
    assert body["ai_mode"] == "mock"
    assert body["llm_model"] is None
    assert body["game_deadline_seconds"] == 600


def test_health_reports_live_mode_without_leaking_key():
    settings = Settings(
        _env_file=None,
        ai_provider=AIProvider.OPENAI_COMPATIBLE,
        llm_provider_order="groq,openrouter",
        groq_api_key="gsk-secret-value",
        openrouter_api_key="sk-or-secret-value",
    )
    resp = _client(settings).get("/api/health")
    body = resp.json()
    assert body["ai_mode"] == "live"
    assert body["llm_providers"] == [f"groq:{settings.groq_model}", f"openrouter:{settings.openrouter_model}"]
    assert body["llm_model"] == body["llm_providers"][0]
    assert "secret-value" not in resp.text


def test_providers_without_keys_are_skipped():
    settings = Settings(_env_file=None, llm_provider_order="groq,gemini,openrouter", gemini_api_key="g-key")
    assert [p.name for p in settings.llm_providers] == ["gemini"]


def test_live_provider_requires_api_key():
    with pytest.raises(ValidationError):
        Settings(_env_file=None, ai_provider=AIProvider.OPENAI_COMPATIBLE, llm_api_key="")
