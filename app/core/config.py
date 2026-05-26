import os
from functools import lru_cache

from dotenv import load_dotenv
from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator


class Settings(BaseModel):
    bot_token: SecretStr = Field(default=SecretStr(""), alias="BOT_TOKEN")
    database_url: str = Field(
        default="postgresql+asyncpg://mately:mately@127.0.0.1:5432/mately",
        alias="DATABASE_URL",
    )
    openai_api_key: SecretStr | None = Field(default=None, alias="OPENAI_API_KEY")
    openai_model: str = Field(default="gpt-4o-mini", alias="OPENAI_MODEL")
    openai_timeout_seconds: float = Field(default=6.0, alias="OPENAI_TIMEOUT_SECONDS")
    openai_max_tokens: int = Field(default=90, alias="OPENAI_MAX_TOKENS")
    openai_temperature: float = Field(default=0.55, alias="OPENAI_TEMPERATURE")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    sql_echo: bool = Field(default=False, alias="SQL_ECHO")
    default_timezone: str = Field(default="Europe/Moscow", alias="DEFAULT_TIMEZONE")
    invite_code_ttl_hours: int = Field(default=168, alias="INVITE_CODE_TTL_HOURS")

    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    @field_validator("database_url")
    @classmethod
    def normalize_database_url(cls, value: str) -> str:
        if value.startswith("postgresql://"):
            return value.replace("postgresql://", "postgresql+asyncpg://", 1)
        return value

    @field_validator("openai_model")
    @classmethod
    def normalize_openai_model(cls, value: str) -> str:
        normalized = value.strip()
        return normalized or "gpt-4o-mini"

    @field_validator("openai_timeout_seconds")
    @classmethod
    def clamp_openai_timeout_seconds(cls, value: float) -> float:
        return max(1.0, min(value, 30.0))

    @field_validator("openai_max_tokens")
    @classmethod
    def clamp_openai_max_tokens(cls, value: int) -> int:
        return max(20, min(value, 200))

    @field_validator("openai_temperature")
    @classmethod
    def clamp_openai_temperature(cls, value: float) -> float:
        return max(0.0, min(value, 1.2))


@lru_cache
def get_settings() -> Settings:
    load_dotenv()
    return Settings.model_validate(os.environ)
