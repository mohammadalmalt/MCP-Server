"""Configuration loaded from environment variables.

Connection defaults are hard-coded to localhost root/root per project spec.
The only thing the caller must provide is the database name (MYSQL_DB).
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field


def _parse_csv(value: str | None, default: list[str]) -> list[str]:
    if not value:
        return default
    return [v.strip().upper() for v in value.split(",") if v.strip()]


def _parse_bool(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in ("1", "true", "yes", "on")


@dataclass(frozen=True)
class Config:
    host: str = "localhost"
    port: int = 3306
    user: str = "root"
    password: str = "root"
    database: str = ""

    pool_name: str = "mysql_mcp_pool"
    pool_size: int = 5
    connection_timeout: int = 10

    # Security
    allowed_operations: list[str] = field(default_factory=list)
    max_rows: int = 1000
    read_only: bool = False

    @classmethod
    def from_env(cls) -> "Config":
        db = os.environ.get("MYSQL_DB") or os.environ.get("MYSQL_DATABASE")
        if not db:
            raise RuntimeError(
                "MYSQL_DB environment variable is required. "
                "Set it to the database name you want to connect to."
            )

        default_ops = ["SELECT", "SHOW", "DESCRIBE", "EXPLAIN",
                       "INSERT", "UPDATE", "DELETE",
                       "CREATE", "ALTER", "DROP", "TRUNCATE",
                       "BEGIN", "COMMIT", "ROLLBACK"]

        return cls(
            host=os.environ.get("MYSQL_HOST", "localhost"),
            port=int(os.environ.get("MYSQL_PORT", "3306")),
            user=os.environ.get("MYSQL_USER", "root"),
            password=os.environ.get("MYSQL_PASSWORD", "root"),
            database=db,
            pool_size=int(os.environ.get("MYSQL_POOL_SIZE", "5")),
            connection_timeout=int(os.environ.get("MYSQL_TIMEOUT", "10")),
            allowed_operations=_parse_csv(os.environ.get("ALLOWED_OPERATIONS"), default_ops),
            max_rows=int(os.environ.get("MYSQL_MAX_ROWS", "1000")),
            read_only=_parse_bool(os.environ.get("MYSQL_READ_ONLY"), False),
        )
