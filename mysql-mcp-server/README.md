# MySQL MCP Server

A secure, production-minded **Model Context Protocol** server that gives Claude Desktop (or any MCP client) direct, controlled access to a local MySQL database.

Connection is hard-wired to `localhost` with `root` / `root`. **The only thing the caller must provide is the database name** via the `MYSQL_DB` environment variable.

## Why this exists

Most MCP database examples are toys: raw SQL passes through unchecked, write paths are missing, errors are cryptic, and there's no transaction story. This server fixes that:

- **SQL injection defence in depth** — every query is parsed with `sqlparse`, classified, whitelisted, and executed parameterised.
- **Operation whitelist** — `ALLOWED_OPERATIONS` env var restricts the server to the SQL verbs you trust.
- **Modular tools** — basic / write / advanced / transactions, so you can later split permissions.
- **Connection pool** — `mysql-connector-python` pooling with retry on transient errors.
- **Read-only mode** — single flag locks the server to reads only.
- **Auto-LIMIT** — bare `SELECT`s get a `LIMIT` appended so the model can't accidentally pull millions of rows.

## Install

The package **must be installed** (not just have dependencies installed) so that
Claude Desktop can import it — `cwd` in the Claude config doesn't put the
project on `sys.path`.

```powershell
pip install -e C:\Steag\Development\Python\mysql-mcp-server
```

Verify it's importable from anywhere:

```powershell
python -c "import mysql_mcp; print(mysql_mcp.__file__)"
```

Requires Python 3.10+ and a local MySQL with the `root`/`root` account.

## Run

```powershell
$env:MYSQL_DB = "your_database"
python -m mysql_mcp.server
```

The process stays in the foreground and speaks MCP over stdio.

## Claude Desktop config

Edit `%APPDATA%\Claude\claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "mysql": {
      "command": "python",
      "args": ["-m", "mysql_mcp.server"],
      "cwd": "C:\\Steag\\Development\\Python\\mysql-mcp-server",
      "env": {
        "MYSQL_DB": "your_database"
      }
    }
  }
}
```

Restart Claude Desktop. The `mysql` tools should appear in the tool list.

## Environment variables

| Variable             | Default                  | Description                                       |
|----------------------|--------------------------|---------------------------------------------------|
| `MYSQL_DB`           | _required_               | Database name to connect to.                      |
| `MYSQL_HOST`         | `localhost`              | Override only if you really need to.              |
| `MYSQL_PORT`         | `3306`                   |                                                   |
| `MYSQL_USER`         | `root`                   |                                                   |
| `MYSQL_PASSWORD`     | `root`                   |                                                   |
| `MYSQL_POOL_SIZE`    | `5`                      | Pool size.                                        |
| `MYSQL_TIMEOUT`      | `10`                     | Connect timeout (seconds).                        |
| `MYSQL_MAX_ROWS`     | `1000`                   | Auto-LIMIT applied to bare `SELECT`s. `0` = off. |
| `MYSQL_READ_ONLY`    | `false`                  | If `true`, blocks all write operations.           |
| `ALLOWED_OPERATIONS` | (all common verbs)       | CSV whitelist, e.g. `SELECT,SHOW,EXPLAIN`.        |

## Tools exposed

**Basic (read)**
- `query(sql, params?)` — Run a SELECT/SHOW/DESCRIBE/EXPLAIN.
- `list_tables()`
- `describe_table(table)`
- `server_info()`

**Write**
- `insert(sql, params?)`
- `update(sql, params?)` — refuses without a `WHERE` clause.
- `delete(sql, params?)` — refuses without a `WHERE` clause.

**Advanced**
- `explain(sql)`
- `list_indexes(table)`
- `table_stats(table)`
- `execute_ddl(sql)` — CREATE / ALTER / DROP / TRUNCATE / RENAME.

**Transactions**
- `execute_transaction(statements)` — `[{sql, params?}, ...]` run atomically.

## Security model

1. **Operation whitelist.** Configure `ALLOWED_OPERATIONS` to narrow the surface.
2. **Statement parsing.** `sqlparse` classifies the leading verb; anything not on the whitelist is rejected before reaching MySQL.
3. **Stacked-query guard.** Multiple `;`-separated statements are refused in single-statement tools.
4. **Comment-injection guard.** `--`, `#`, and `/*` markers are blocked outside of transactional batches where they're legitimate.
5. **Parameterised execution.** Every tool exposes a `params` argument so the model never has to splice values into SQL.
6. **Identifier whitelisting.** Tools that take a table name validate it as a bare identifier (no SQL).
7. **Read-only mode.** A single env var locks the server down for exploratory use.
8. **Auto-LIMIT.** Prevents accidental megabyte-scale result sets.

## Manual smoke test

```powershell
$env:MYSQL_DB = "your_database"
python -c "from mysql_mcp.server import build_server; build_server(); print('OK')"
```

A clean `OK` means the pool, validator, and tool registration are all wired up.
