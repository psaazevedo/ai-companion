from functools import lru_cache
from typing import Annotated, Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    app_name: str = "Personal AI Companion"
    environment: str = "development"
    secret_key: str = "dev-secret"
    mock_mode: bool = True
    database_url: str = "postgresql://companion:companion@127.0.0.1:5432/companion"

    groq_api_key: Optional[str] = None
    groq_base_url: str = "https://api.groq.com/openai/v1"
    groq_chat_model: str = "llama-3.3-70b-versatile"
    groq_transcription_model: str = "whisper-large-v3-turbo"
    groq_tts_model: str = "canopylabs/orpheus-v1-english"
    groq_tts_voice: str = "hannah"
    groq_tts_response_format: str = "wav"
    groq_tts_style: str = ""

    supabase_url: Optional[str] = None
    supabase_publishable_key: Optional[str] = None
    supabase_embedding_function_name: str = "embed"

    embedding_provider: str = "supabase"
    embedding_api_key: Optional[str] = None
    embedding_base_url: Optional[str] = None
    embedding_model: str = "gte-small"
    embedding_dimensions: int = 384
    background_runner_enabled: bool = True
    consolidation_interval_seconds: int = 900
    proactive_scan_interval_seconds: int = 300

    allowed_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: [
            "http://localhost:8081",
            "http://localhost:8083",
            "http://localhost:19006",
            "http://localhost:3000",
            "http://127.0.0.1:8083",
        ]
    )

    @field_validator("allowed_origins", mode="before")
    @classmethod
    def parse_allowed_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    @property
    def llm_enabled(self) -> bool:
        return bool(self.groq_api_key and not self.mock_mode)

    @property
    def transcription_enabled(self) -> bool:
        return bool(self.groq_api_key and not self.mock_mode)

    @property
    def tts_enabled(self) -> bool:
        return bool(self.groq_api_key and not self.mock_mode)

    @property
    def embeddings_enabled(self) -> bool:
        if self.embedding_provider == "supabase":
            return bool(self.supabase_url and self.supabase_publishable_key)
        return bool(self.embedding_api_key)


@lru_cache
def get_settings() -> Settings:
    return Settings()
