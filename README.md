# MCP-Server

This repository contains MCP server projects. It currently includes:

- [`mysql-mcp-server`](./mysql-mcp-server): a Python-based Model Context Protocol server that gives MCP clients controlled access to a MySQL database.

## MySQL MCP Server

`mysql-mcp-server` exposes MySQL operations to Claude Desktop or any other MCP-compatible client over stdio. It is designed for practical database work while keeping the server surface constrained and predictable.

It can:

- inspect databases with read tools such as `query`, `list_tables`, `describe_table`, and `server_info`
- perform controlled writes with `insert`, `update`, and `delete`
- inspect and manage schema with `explain`, `list_indexes`, `table_stats`, and `execute_ddl`
- run multiple statements atomically with `execute_transaction`

## Key Behaviors

- Reads and writes are separated into dedicated tools.
- SQL operations are validated against an allowlist before execution.
- Single-statement tools reject stacked queries and obvious comment-based injection patterns.
- Parameterized execution is supported through `%s` placeholders plus `params`.
- `UPDATE` and `DELETE` are refused unless they include a `WHERE` clause.
- Bare `SELECT` statements receive an automatic row limit by default.
- A connection pool is used for database access, with retry handling for transient MySQL failures.
- `MYSQL_READ_ONLY=true` can lock the server down for exploratory use.

## Requirements

- Python 3.10+
- A reachable MySQL server
- The database name supplied through `MYSQL_DB`

By default, the server uses:

- host: `localhost`
- port: `3306`
- user: `root`
- password: `root`

Those defaults can be changed with environment variables.

## Install

From the repository root:

```powershell
pip install -e .\mysql-mcp-server
```

## Run

```powershell
$env:MYSQL_DB = "your_database"
python -m mysql_mcp.server
```

The server stays in the foreground and communicates through MCP over stdio.

## Claude Desktop Example

```json
{
  "mcpServers": {
    "mysql": {
      "command": "python",
      "args": ["-m", "mysql_mcp.server"],
      "cwd": "C:\\path\\to\\MCP-Server\\mysql-mcp-server",
      "env": {
        "MYSQL_DB": "your_database"
      }
    }
  }
}
```

## Configuration

| Variable | Default | Purpose |
| --- | --- | --- |
| `MYSQL_DB` | required | Database name to connect to |
| `MYSQL_HOST` | `localhost` | MySQL host |
| `MYSQL_PORT` | `3306` | MySQL port |
| `MYSQL_USER` | `root` | MySQL user |
| `MYSQL_PASSWORD` | `root` | MySQL password |
| `MYSQL_POOL_SIZE` | `5` | Connection pool size |
| `MYSQL_TIMEOUT` | `10` | Connection timeout in seconds |
| `MYSQL_MAX_ROWS` | `1000` | Auto-limit for bare `SELECT` queries; `0` disables it |
| `MYSQL_READ_ONLY` | `false` | Blocks write operations when enabled |
| `ALLOWED_OPERATIONS` | common MySQL verbs | Comma-separated SQL operation allowlist |

## Tool Summary

### Read Tools

- `query(sql, params?)`
- `list_tables()`
- `describe_table(table)`
- `server_info()`

### Write Tools

- `insert(sql, params?)`
- `update(sql, params?)`
- `delete(sql, params?)`

### Advanced Tools

- `explain(sql)`
- `list_indexes(table)`
- `table_stats(table)`
- `execute_ddl(sql)`

### Transaction Tool

- `execute_transaction(statements)`

## Safety Notes

This project adds guardrails, but it is still a database-access server. Use a least-privilege MySQL account in real environments, narrow `ALLOWED_OPERATIONS` to the actions you actually need, and enable read-only mode whenever writes are unnecessary.

For the full package-specific documentation, see [`mysql-mcp-server/README.md`](./mysql-mcp-server/README.md).
