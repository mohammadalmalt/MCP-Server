"""MCP server entry point.

Run with:
    python -m mysql_mcp.server
or via Claude Desktop's `mcpServers` config.

Required env var: MYSQL_DB
Optional env vars: MYSQL_HOST, MYSQL_PORT, MYSQL_USER, MYSQL_PASSWORD,
                   MYSQL_POOL_SIZE, MYSQL_MAX_ROWS, MYSQL_READ_ONLY,
                   ALLOWED_OPERATIONS (comma-separated)
"""

from __future__ import annotations

import logging
import sys

from mcp.server.fastmcp import FastMCP

from .config import Config
from .connection import MySqlPool
from .security import SqlValidator
from .tools import advanced, basic, transactions, write


def _setup_logging() -> None:
    # MCP communicates over stdio; logs must go to stderr.
    logging.basicConfig(
        level=logging.INFO,
        stream=sys.stderr,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


def build_server() -> FastMCP:
    config = Config.from_env()
    pool = MySqlPool(config)
    validator = SqlValidator(config)

    mcp = FastMCP(
        name="mysql-mcp-server",
        instructions=(
            f"MySQL MCP server connected to database '{config.database}'. "
            "Use parameterised queries (%s placeholders + params) for any user "
            "data. The `query` tool is read-only; use `insert`/`update`/`delete` "
            "for writes, `execute_ddl` for schema changes, and "
            "`execute_transaction` for atomic batches."
        ),
    )

    basic.register(mcp, pool, validator, config)
    write.register(mcp, pool, validator, config)
    advanced.register(mcp, pool, validator, config)
    transactions.register(mcp, pool, validator, config)

    # Warm the pool once so misconfiguration fails fast at startup.
    try:
        pool.ping()
        logging.info("Connected to MySQL database '%s'", config.database)
    except Exception as e:  # noqa: BLE001
        logging.error("Initial MySQL connection check failed: %s", e)
        raise

    return mcp


def main() -> None:
    _setup_logging()
    server = build_server()
    server.run()


if __name__ == "__main__":
    main()
