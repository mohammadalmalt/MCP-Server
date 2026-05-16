"""Transaction tools: run a batch of validated statements atomically."""

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
    def execute_transaction(statements: list[dict[str, Any]]) -> str:
        """Run a list of statements inside a single transaction.

        Each item in `statements` is an object with:
          - sql:    the statement (with %s placeholders)
          - params: optional list of values

        If any statement fails, the entire batch is rolled back.

        Args:
            statements: Ordered list of {sql, params?} objects.
        """
        if not statements:
            raise SecurityError("`statements` must be a non-empty list")

        prepared: list[tuple[str, Optional[tuple]]] = []
        for i, item in enumerate(statements):
            if not isinstance(item, dict) or "sql" not in item:
                raise SecurityError(f"Statement {i} missing 'sql' field")
            validated = validator.validate(item["sql"])
            params = item.get("params")
            prepared.append((validated.sql, tuple(params) if params else None))

        results = pool.execute_many(prepared)
        return json.dumps({
            "committed": True,
            "statement_count": len(results),
            "results": results,
        }, indent=2, default=str)
