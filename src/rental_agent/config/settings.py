"""Typed application settings.

Two local profiles exist: ``development`` and ``production`` (08 §6). Tests use the
development profile with the dedicated ``rental_test`` database. Secrets come from
the environment / ``.env`` only and are never committed or logged.
"""

from enum import StrEnum
from pathlib import Path

from pydantic import Field, PostgresDsn, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Profile(StrEnum):
    DEVELOPMENT = "development"
    PRODUCTION = "production"


class DatabaseSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="RENTAL_DB_", env_file=".env", extra="ignore")

    host: str = "localhost"
    port: int = 5433
    user: str = "rental"
    password: SecretStr = SecretStr("rental_local_dev")
    database: str = "rental_dev"
    pool_size: int = 5
    echo: bool = False

    @property
    def url(self) -> str:
        dsn = PostgresDsn.build(
            scheme="postgresql+psycopg",
            username=self.user,
            password=self.password.get_secret_value(),
            host=self.host,
            port=self.port,
            path=self.database,
        )
        return str(dsn)


class DataPaths(BaseSettings):
    """Local data-directory conventions (08 §5). All content stays on the local
    filesystem; the database stores relative paths beneath these roots."""

    model_config = SettingsConfigDict(env_prefix="RENTAL_DATA_", env_file=".env", extra="ignore")

    root: Path = Path("local_data")

    @property
    def media(self) -> Path:
        return self.root / "media"

    @property
    def raw(self) -> Path:
        return self.root / "raw"

    @property
    def exports(self) -> Path:
        return self.root / "exports"

    @property
    def logs(self) -> Path:
        return self.root / "logs"

    @property
    def backups(self) -> Path:
        return self.root / "backups"

    def ensure_exists(self) -> None:
        for p in (self.media, self.raw, self.exports, self.logs, self.backups):
            p.mkdir(parents=True, exist_ok=True)


class ProviderSettings(BaseSettings):
    """External-provider configuration contracts (Phase 0 decisions).

    Provider *identity* is configuration; no provider ID may be hard-coded in
    canonical business logic. Keys are optional so provider-neutral foundations
    run without credentials (fakes are used in tests).
    """

    model_config = SettingsConfigDict(
        env_prefix="RENTAL_PROVIDER_", env_file=".env", extra="ignore"
    )

    # B7 (owner, 2026-08-17): NO paid Google APIs. The free Maps Embed API renders
    # the apartment/directions on listing detail for manual verification only.
    # Distance math is local PostGIS; commutes are on-demand LLM web research.
    google_maps_embed_enabled: bool = True

    # B5 (owner, 2026-08-17): OpenAI tiers.
    llm_provider_code: str = "openai"
    llm_default_model_id: str = "gpt-5.6-terra"
    llm_default_reasoning_effort: str = "low"
    llm_flagship_model_id: str = "gpt-5.6-sol"
    llm_flagship_reasoning_effort: str = "medium"
    openai_api_key: SecretStr | None = None

    # B3 (owner, 2026-08-17): StreetEasy discovery runs through a configurable
    # search provider behind the SearchProvider adapter. Owner choice: Tavily
    # (Google Custom Search JSON API is retired for new customers as of 2025,
    # shutting down 2027-01-01).
    search_provider_code: str = "tavily"
    search_provider_api_key: SecretStr | None = None

    # B7: researched commute estimates are reused for 14 days (04 §19A).
    commute_research_cache_days: int = 14

    # Map tiles (agent recommendation, replaceable): OSM default tiles via folium.
    map_tile_provider_code: str = "osm_default"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="RENTAL_", env_file=".env", extra="ignore")

    profile: Profile = Profile.DEVELOPMENT
    timezone: str = "America/New_York"
    operator_id: str = "local_operator"  # single-user audit identity (07 §5.3)

    db: DatabaseSettings = Field(default_factory=DatabaseSettings)
    paths: DataPaths = Field(default_factory=DataPaths)
    providers: ProviderSettings = Field(default_factory=ProviderSettings)

    @model_validator(mode="after")
    def _validate_production(self) -> "Settings":
        if self.profile is Profile.PRODUCTION and self.db.database == "rental_test":
            raise ValueError("production profile must not point at the test database")
        return self


def load_settings() -> Settings:
    return Settings()
