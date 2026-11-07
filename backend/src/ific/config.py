from pathlib import Path

from pydantic import Field, HttpUrl, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="IFIC_", env_file=PROJECT_ROOT / ".env", extra="ignore")

    data_dir: Path = PROJECT_ROOT / "data"
    db_dir: Path = PROJECT_ROOT / "var" / "db"
    # Storage format for newly created DB files; v1.5.0 keeps them readable by DuckDB 1.x GUI clients.
    db_storage_version: str = "v1.5.0"
    cors_origins: list[str] = ["http://localhost:5173"]

    watcher_enabled: bool = True
    watcher_interval_seconds: int = Field(3600, ge=60)
    watcher_source_url: HttpUrl = HttpUrl("https://www.itu.int/sns/wic/demowic.html")
    watcher_download_dir: Path = PROJECT_ROOT / "data" / "ific"
    watcher_state_path: Path = PROJECT_ROOT / "var" / "db" / "watcher.sqlite3"
    watcher_http_timeout_seconds: float = Field(60.0, gt=0)
    watcher_max_download_bytes: int = Field(2_000_000_000, gt=0)

    @field_validator("watcher_download_dir", "watcher_state_path")
    @classmethod
    def _resolve_against_project_root(cls, path: Path) -> Path:
        return path if path.is_absolute() else PROJECT_ROOT / path

    @property
    def db_path(self) -> Path:
        return self.db_dir / "ific.duckdb"

    @property
    def m4_allocation_json(self) -> Path:
        return self.data_dir / "api" / "taajuusjakotaulukko.json"

    @property
    def m4_dir(self) -> Path:
        return self.data_dir / "m4"

    @property
    def special_interest_csv(self) -> Path:
        return self.data_dir / "special_interest" / "Frequencies_of_interest_v05112026.csv"


settings = Settings()
