import os
from functools import lru_cache

from dotenv import load_dotenv
from pydantic import BaseModel, ConfigDict, Field, SecretStr


class Settings(BaseModel):
    bot_token: SecretStr = Field(default=SecretStr(""), alias="BOT_TOKEN")
    database_url: str = Field(
        default="postgresql+asyncpg://mately:mately@127.0.0.1:5432/mately",
        alias="DATABASE_URL",
    )
    openai_api_key: SecretStr | None = Field(default=None, alias="OPENAI_API_KEY")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    sql_echo: bool = Field(default=False, alias="SQL_ECHO")
    default_timezone: str = Field(default="Europe/Moscow", alias="DEFAULT_TIMEZONE")
    invite_code_ttl_hours: int = Field(default=168, alias="INVITE_CODE_TTL_HOURS")

    model_config = ConfigDict(extra="ignore", populate_by_name=True)


@lru_cache
def get_settings() -> Settings:
    load_dotenv()
    return Settings.model_validate(os.environ)
