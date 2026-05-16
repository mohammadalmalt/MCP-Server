"""Advanced tools: schema management, indexes, EXPLAIN, table stats."""

from __future__ import annotations

import json

from mcp.server.fastmcp import FastMCP

from ..config import Config
from ..connection import MySqlPool
from ..exceptions import SecurityError
from ..security import SqlValidator


def _safe_identifier(name: str) -> str:
    if not name or not name.replace("_", "").isalnum():
        raise SecurityError(f"Invalid identifier: {name!r}")
    return name


def register(mcp: FastMCP, pool: MySqlPool, validator: SqlValidator, config: Config) -> None:

    @mcp.tool()
    def explain(sql: str) -> str:
        """Return the MySQL EXPLAIN plan for a SELECT/UPDATE/DELETE/INSERT.

        Args:
            sql: The query to analyse. Will not be executed.
        """
        validated = validator.validate(sql)
        result = pool.execute(f"EXPLAIN {validated.sql}")
        return json.dumps(result["rows"], indent=2, default=str)

    @mcp.tool()
    def list_indexes(table: str) -> str:
        """List indexes on the given table.

        Args:
            table: Table name.
        """
        table = _safe_identifier(table)
        result = pool.execute(f"SHOW INDEX FROM `{table}`")
        return json.dumps(result["rows"], indent=2, default=str)

    @mcp.tool()
    def table_stats(table: str) -> str:
        """Return row count, data size, and last-update time for a table.

        Args:
            table: Table name.
        """
        table = _safe_identifier(table)
        result = pool.execute(
            """
            SELECT table_name, engine, table_rows, data_length, index_length,
                   create_time, update_time, table_collation
            FROM information_schema.tables
            WHERE table_schema = %s AND table_name = %s
            """,
            (config.database, table),
        )
        return json.dumps(result["rows"], indent=2, default=str)

    @mcp.tool()
    def execute_ddl(sql: str) -> str:
        """Execute a DDL statement (CREATE/ALTER/DROP/TRUNCATE/RENAME).

        Args:
            sql: The DDL statement. No parameter binding — identifiers go directly.
        """
        validated = validator.validate(sql)
        ddl_ops = {"CREATE", "ALTER", "DROP", "TRUNCATE", "RENAME"}
        if validated.operation not in ddl_ops:
            raise SecurityError(
                f"`execute_ddl` only accepts DDL; got '{validated.operation}'"
            )
        result = pool.execute(validated.sql, commit=True)
        return json.dumps({
            "operation": validated.operation,
            "rowcount": result["rowcount"],
        }, indent=2)
