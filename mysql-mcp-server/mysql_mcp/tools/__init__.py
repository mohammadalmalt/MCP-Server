"""Tool modules for the MySQL MCP server.

Each module exposes `register(server, pool, validator, config)` which attaches
its tools to the MCP server instance. Keeping the modules separate lets us
grant fine-grained permissions later.
"""

from . import basic, write, advanced, transactions

__all__ = ["basic", "write", "advanced", "transactions"]
