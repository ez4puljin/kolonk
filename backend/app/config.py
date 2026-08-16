from decimal import Decimal
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://kolonk:kolonk@db:5432/kolonk"
    redis_url: str = "redis://redis:6379/0"

    jwt_secret: str = "dev-secret-change-me"
    jwt_algorithm: str = "HS256"
    jwt_expire_hours: int = 12

    vat_rate: Decimal = Decimal("0.10")
    ebarimt_mode: str = "stub"
    ebarimt_pos_id: str = ""

    backup_dir: str = "/backups"
    tz: str = "Asia/Ulaanbaatar"

    station_name: str = "Колонк ШТС"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
