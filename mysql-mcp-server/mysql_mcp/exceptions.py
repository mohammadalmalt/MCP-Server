"""Custom exception types for the MySQL MCP server."""


class MysqlMcpError(Exception):
    """Base error for the MySQL MCP server."""


class SecurityError(MysqlMcpError):
    """Raised when a query is rejected by the security layer."""


class ConfigError(MysqlMcpError):
    """Raised when configuration is missing or invalid."""


class ConnectionError(MysqlMcpError):
    """Raised on pool or connection failures."""
