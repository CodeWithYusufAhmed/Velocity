"""Typed application settings, loaded from environment / server/.env.

pydantic-settings validates every value at startup, so a bad or missing
setting fails fast instead of surfacing mid-game. Secrets live only in .env
(gitignored) — never in code.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # --- Database ---
    database_url: str = "postgresql+asyncpg://velocity:change_me@127.0.0.1:5432/velocity"

    # --- Auth (used from M2) ---
    jwt_secret: str = "dev_only_change_me"
    jwt_access_ttl_minutes: int = 15
    jwt_refresh_ttl_days: int = 30
    google_oauth_client_id: str = ""  # Web client ID; set in M2
    admin_password: str = ""  # separate strong password for /admin; empty = admin disabled

    # --- LiveKit (used from M5) ---
    livekit_url: str = "ws://127.0.0.1:7880"
    livekit_api_key: str = "devkey"
    livekit_api_secret: str = "devsecret_change_me_before_production_0000"

    # --- Game economy (defaults per spec; odds live in the DB, not here) ---
    signup_grant: int = 100_000
    daily_bonus: int = 50_000
    rescue_amount: int = 20_000
    rescue_max_per_day: int = 3
    rescue_threshold: int = 200
    game_timezone: str = "Asia/Dhaka"
    coins_per_dollar: int = 8_000  # for the Money-You-Didn't-Spend estimate

    # --- Betting chips ---
    chip_values: list[int] = [200, 500, 1_000, 4_000, 10_000, 30_000, 100_000]

    # --- Round engine ---
    round_engine_enabled: bool = True  # tests/tools disable it

    # --- Round loop timings (seconds) ---
    betting_seconds: int = 15
    spinning_seconds: int = 3
    results_seconds: int = 3

    # --- Capacity (adjustable later via admin dashboard) ---
    max_tables: int = 20
    max_listeners_per_table: int = 50


@lru_cache
def get_settings() -> Settings:
    return Settings()
