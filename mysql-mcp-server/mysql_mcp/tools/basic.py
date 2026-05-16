"""Basic read-only tools: query, list tables, describe table, server info."""

from __future__ import annotations

import json
from typing import Any, Optional

from mcp.server.fastmcp import FastMCP

from ..config import Config
from ..connection import MySqlPool
from ..exceptions import SecurityError
from ..security import SqlValidator


def register(mcp: FastMCP, pool: MySqlPool, validator: SqlValidator, config: Config) -> None:

    @mcp.tool()
    def list_tables() -> str:
        """List all tables in the current database."""
        result = pool.execute("SHOW TABLES")
        tables = [next(iter(row.values())) for row in result["rows"]]
        return json.dumps({"database": config.database, "tables": tables}, indent=2)

    @mcp.tool()
    def describe_table(table: str) -> str:
        """Return the column schema for the given table.

        Args:
            table: Table name (must be a bare identifier, no SQL).
        """
        if not table.replace("_", "").isalnum():
            raise SecurityError("Invalid table identifier")
        # SHOW COLUMNS doesn't accept parameters; use an identifier whitelist instead.
        result = pool.execute(f"SHOW COLUMNS FROM `{table}`")
        return json.dumps(result["rows"], indent=2, default=str)

    @mcp.tool()
    def query(sql: str, params: Optional[list[Any]] = None) -> str:
        """Run a read-only SELECT/SHOW/DESCRIBE/EXPLAIN query.

        Use placeholders (%s) for any user-supplied values and pass them via `params`.
        A LIMIT is auto-appended to bare SELECTs when MYSQL_MAX_ROWS is set.

        Args:
            sql: The SQL query, with %s placeholders for bound parameters.
            params: Ordered list of values to bind into the placeholders.
        """
        validated = validator.validate(sql)
        if validated.is_write:
            raise SecurityError(
                f"`query` is for reads only; '{validated.operation}' is a write — "
                "use the appropriate write tool."
            )
        safe_sql = validator.with_safety_limit(validated.sql, validated.operation)
        result = pool.execute(safe_sql, tuple(params) if params else None)
        return json.dumps(
            {"rowcount": result["rowcount"], "rows": result["rows"]},
            indent=2,
            default=str,
        )

    @mcp.tool()
    def server_info() -> str:
        """Return MySQL version, current database, and connection-pool stats."""
        version = pool.execute("SELECT VERSION() AS version")["rows"][0]
        return json.dumps({
            "database": config.database,
            "host": config.host,
            "port": config.port,
            "version": version["version"],
            "pool_size": config.pool_size,
            "read_only": config.read_only,
            "allowed_operations": config.allowed_operations,
            "max_rows": config.max_rows,
        }, indent=2)
