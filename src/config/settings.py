from __future__ import annotations

from dataclasses import dataclass, field
import os
from pathlib import Path

from ..common.env import load_env_file


class StorageConfigError(ValueError):
    """Raised when database or vector-store environment settings are invalid."""


@dataclass(frozen=True)
class MySQLConfig:
    host: str
    port: int
    user: str
    password: str = field(repr=False)
    database: str
    connect_timeout: int = 10

    @classmethod
    def from_env(cls, env_file: str | Path | None = None) -> "MySQLConfig":
        if env_file is not None:
            load_env_file(env_file)
        required = ("MYSQL_USER", "MYSQL_PASSWORD", "MYSQL_DATABASE")
        missing = [name for name in required if not os.environ.get(name)]
        if missing:
            raise StorageConfigError(
                f"missing MySQL environment variables: {', '.join(missing)}"
            )
        try:
            port = int(os.environ.get("MYSQL_PORT", "3306"))
            timeout = int(os.environ.get("MYSQL_CONNECT_TIMEOUT", "10"))
        except ValueError as exc:
            raise StorageConfigError(
                "MYSQL_PORT and MYSQL_CONNECT_TIMEOUT must be integers"
            ) from exc
        return cls(
            host=os.environ.get("MYSQL_HOST", "127.0.0.1"),
            port=port,
            user=os.environ["MYSQL_USER"],
            password=os.environ["MYSQL_PASSWORD"],
            database=os.environ["MYSQL_DATABASE"],
            connect_timeout=timeout,
        )

    def connection_kwargs(self, *, include_database: bool = True) -> dict[str, object]:
        kwargs: dict[str, object] = {
            "host": self.host,
            "port": self.port,
            "user": self.user,
            "password": self.password,
            "connection_timeout": self.connect_timeout,
            "charset": "utf8mb4",
            "use_unicode": True,
        }
        if include_database:
            kwargs["database"] = self.database
        return kwargs


@dataclass(frozen=True)
class ChromaConfig:
    mode: str
    collection_name: str
    persist_directory: Path
    host: str
    port: int
    ssl: bool
    openai_api_key: str = field(repr=False)

    @classmethod
    def from_env(
        cls,
        env_file: str | Path | None = None,
        *,
        project_root: str | Path | None = None,
        default_collection: str = "documents",
        collection_env_var: str = "CHROMA_COLLECTION",
    ) -> "ChromaConfig":
        if env_file is not None:
            load_env_file(env_file)
        mode = os.environ.get("CHROMA_MODE", "persistent").strip().lower()
        if mode not in {"persistent", "http"}:
            raise StorageConfigError("CHROMA_MODE must be persistent or http")
        api_key = os.environ.get("OPENAI_API_KEY", "")
        if not api_key:
            raise StorageConfigError("OPENAI_API_KEY is not configured")
        try:
            port = int(os.environ.get("CHROMA_PORT", "8000"))
        except ValueError as exc:
            raise StorageConfigError("CHROMA_PORT must be an integer") from exc
        raw_path = Path(os.environ.get("CHROMA_PERSIST_DIRECTORY", "data/vectorstore"))
        if not raw_path.is_absolute() and project_root is not None:
            raw_path = Path(project_root) / raw_path
        return cls(
            mode=mode,
            collection_name=os.environ.get(
                collection_env_var, default_collection
            ),
            persist_directory=raw_path,
            host=os.environ.get("CHROMA_HOST", "127.0.0.1"),
            port=port,
            ssl=os.environ.get("CHROMA_SSL", "false").lower() in {"1", "true", "yes"},
            openai_api_key=api_key,
        )
