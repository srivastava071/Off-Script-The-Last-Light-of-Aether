"""Application settings, loaded from environment variables and the repo-root .env file."""

from enum import Enum
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[3]
BACKEND_ROOT = REPO_ROOT / "backend"


class AIProvider(str, Enum):
    MOCK = "mock"
    OPENAI_COMPATIBLE = "openai_compatible"


class ProviderConfig(BaseModel):
    """One OpenAI-compatible endpoint. The key never leaves the backend."""

    name: str
    base_url: str
    model: str
    api_key: SecretStr

    @property
    def label(self) -> str:
        return f"{self.name}:{self.model}"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=REPO_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    ai_provider: AIProvider = AIProvider.MOCK
    llm_provider_order: str = "groq,gemini,openrouter"

    groq_api_key: SecretStr = SecretStr("")
    groq_model: str = "qwen/qwen3.8-27b"
    groq_base_url: str = "https://api.groq.com/openai/v1"

    gemini_api_key: SecretStr = SecretStr("")
    gemini_model: str = "gemini-flash-lite-latest"
    gemini_base_url: str = "https://generativelanguage.googleapis.com/v1beta/openai"

    openrouter_api_key: SecretStr = SecretStr("")
    openrouter_model: str = "openrouter/free"  # router that picks any currently free model
    openrouter_base_url: str = "https://openrouter.ai/api/v1"

    # Optional fourth provider, called "custom".
    llm_api_key: SecretStr = SecretStr("")
    llm_model: str = ""
    llm_base_url: str = ""

    llm_timeout_seconds: float = Field(default=20.0, gt=0, le=120)
    llm_max_retries: int = Field(default=1, ge=0, le=5)
    llm_max_calls_per_minute: int = Field(default=10, ge=1, le=600)
    llm_max_deliberations_per_run: int = Field(default=30, ge=0, le=500)

    sim_tick_seconds: int = Field(default=5, ge=1, le=60)
    game_deadline_seconds: int = Field(default=600, ge=60, le=3600)

    # Real-time driver: simulated seconds per wall-clock second.
    sim_autorun: bool = True
    game_sim_speed: float = Field(default=2.0, gt=0, le=1000)  # 600 simulated s = a 5-minute game
    default_sim_speed: float = Field(default=4.0, gt=0, le=1000)
    snapshot_interval_seconds: int = Field(default=60, ge=5)
    # Per-run limits on player requests (token bucket).
    player_requests_per_second: float = Field(default=4.0, gt=0)
    player_request_burst: int = Field(default=8, ge=1)

    serve_frontend: bool = True  # serve frontend/dist at "/" when it exists

    database_url: str = "sqlite:///./data/offscript.db"
    cors_origins: str = "http://localhost:5173"

    @model_validator(mode="after")
    def _require_a_key_for_live_mode(self) -> "Settings":
        if self.ai_provider is AIProvider.OPENAI_COMPATIBLE and not self.llm_providers:
            raise ValueError(
                "AI_PROVIDER=openai_compatible needs at least one provider in LLM_PROVIDER_ORDER with an API key "
                "(GROQ_API_KEY, GEMINI_API_KEY, OPENROUTER_API_KEY or LLM_API_KEY)."
            )
        return self

    @property
    def llm_providers(self) -> list[ProviderConfig]:
        """Configured providers that have a key, in the order they should be tried."""
        available = {
            "groq": (self.groq_base_url, self.groq_model, self.groq_api_key),
            "gemini": (self.gemini_base_url, self.gemini_model, self.gemini_api_key),
            "openrouter": (self.openrouter_base_url, self.openrouter_model, self.openrouter_api_key),
            "custom": (self.llm_base_url, self.llm_model, self.llm_api_key),
        }
        order = [n.strip().lower() for n in self.llm_provider_order.split(",") if n.strip()]
        if self.llm_api_key.get_secret_value() and "custom" not in order:
            order.append("custom")
        out = []
        for name in order:
            if name not in available:
                continue
            base, model, key = available[name]
            if key.get_secret_value() and base and model:
                out.append(ProviderConfig(name=name, base_url=base.rstrip("/"), model=model, api_key=key))
        return out

    @property
    def is_live_llm(self) -> bool:
        return self.ai_provider is AIProvider.OPENAI_COMPATIBLE

    @property
    def resolved_database_url(self) -> str:
        """Relative SQLite paths are resolved against the backend folder, not the current directory."""
        prefix = "sqlite:///"
        if self.database_url.startswith(prefix) and not self.database_url.startswith(prefix + "/"):
            path = self.database_url[len(prefix):]
            if path != ":memory:" and not Path(path).is_absolute():
                return prefix + (BACKEND_ROOT / path).resolve().as_posix()
        return self.database_url

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
