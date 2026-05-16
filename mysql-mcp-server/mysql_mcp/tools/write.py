"""Write tools: INSERT, UPDATE, DELETE.

Each tool insists on parameterised input and refuses when the server is in
read-only mode. The underlying validator enforces operation whitelisting.
"""

from __future__ import annotations

import json
from typing import Any, Optional

from mcp.server.fastmcp import FastMCP

from ..config import Config
from ..connection import MySqlPool
from ..exceptions import SecurityError
from ..security import SqlValidator


def register(mcp: FastMCP, pool: MySqlPool, validator: SqlValidator, config: Config) -> None:

    def _run_write(sql: str, params: Optional[list[Any]], expected_ops: set[str]) -> str:
        validated = validator.validate(sql)
        if validated.operation not in expected_ops:
            raise SecurityError(
                f"Expected one of {sorted(expected_ops)}, got '{validated.operation}'"
            )
        result = pool.execute(
            validated.sql,
            tuple(params) if params else None,
            commit=True,
        )
        return json.dumps({
            "operation": validated.operation,
            "rowcount": result["rowcount"],
            "lastrowid": result["lastrowid"],
        }, indent=2, default=str)

    @mcp.tool()
    def insert(sql: str, params: Optional[list[Any]] = None) -> str:
        """Execute an INSERT statement.

        Args:
            sql: INSERT statement with %s placeholders.
            params: Values to bind. Required for any user-supplied data.
        """
        return _run_write(sql, params, {"INSERT", "REPLACE"})

    @mcp.tool()
    def update(sql: str, params: Optional[list[Any]] = None) -> str:
        """Execute an UPDATE statement.

        Args:
            sql: UPDATE statement with %s placeholders. Must include a WHERE clause.
            params: Values to bind.
        """
        if " WHERE " not in sql.upper():
            raise SecurityError("UPDATE without WHERE is refused; specify a filter.")
        return _run_write(sql, params, {"UPDATE"})

    @mcp.tool()
    def delete(sql: str, params: Optional[list[Any]] = None) -> str:
        """Execute a DELETE statement.

        Args:
            sql: DELETE statement with %s placeholders. Must include a WHERE clause.
            params: Values to bind.
        """
        if " WHERE " not in sql.upper():
            raise SecurityError("DELETE without WHERE is refused; specify a filter.")
        return _run_write(sql, params, {"DELETE"})
