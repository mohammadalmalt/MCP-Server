"""SQL security & validation layer.

Strategy:
- Parse SQL with sqlparse to classify the leading statement keyword.
- Reject anything outside the configured ALLOWED_OPERATIONS whitelist.
- Reject multi-statement input (no stacked queries) unless explicitly a txn batch.
- Reject obvious injection markers (comment-out tricks, unbalanced quotes).
- Force a LIMIT on bare SELECTs when MYSQL_MAX_ROWS is set.

This is defence-in-depth on top of parameterised execution; both layers stay on.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

import sqlparse
from sqlparse.sql import Statement
from sqlparse.tokens import DML, DDL, Keyword

from .config import Config
from .exceptions import SecurityError

WRITE_OPS = {"INSERT", "UPDATE", "DELETE", "REPLACE",
             "CREATE", "ALTER", "DROP", "TRUNCATE", "RENAME", "GRANT", "REVOKE"}

DANGEROUS_PATTERNS = [
    # Comment-injection: trailing -- or /* */ used to neutralise the rest of a query.
    re.compile(r"(--\s|#\s|/\*)", re.IGNORECASE),
    # Stacked queries: ; followed by another statement
    re.compile(r";\s*\S", re.IGNORECASE),
]


@dataclass
class ValidatedQuery:
    sql: str
    operation: str  # SELECT, INSERT, etc.
    is_write: bool


class SqlValidator:
    def __init__(self, config: Config):
        self.config = config
        self.allowed = set(op.upper() for op in config.allowed_operations)

    def _leading_keyword(self, stmt: Statement) -> str:
        for token in stmt.tokens:
            if token.ttype in (DML, DDL, Keyword) and token.normalized:
                return token.normalized.upper().split()[0]
            if not token.is_whitespace and token.ttype is None:
                # CTE: WITH ... — recurse into the first child
                if hasattr(token, "tokens"):
                    for child in token.tokens:
                        if child.ttype in (DML, DDL, Keyword):
                            return child.normalized.upper().split()[0]
        return ""

    def validate(self, sql: str, *, allow_multi: bool = False) -> ValidatedQuery:
        if not sql or not sql.strip():
            raise SecurityError("Empty SQL")

        stripped = sql.strip().rstrip(";").strip()

        # Block comment / stacked-query patterns unless we're in a txn batch.
        if not allow_multi:
            for pattern in DANGEROUS_PATTERNS:
                if pattern.search(stripped):
                    raise SecurityError(
                        "Query contains comment or stacked-statement patterns; "
                        "use parameterised queries instead."
                    )

        parsed = sqlparse.parse(stripped)
        if not parsed:
            raise SecurityError("Could not parse SQL")
        if len(parsed) > 1 and not allow_multi:
            raise SecurityError("Multiple statements are not allowed in a single call")

        op = self._leading_keyword(parsed[0])
        if not op:
            raise SecurityError("Could not determine SQL operation")

        if op not in self.allowed:
            raise SecurityError(
                f"Operation '{op}' is not in ALLOWED_OPERATIONS. "
                f"Allowed: {sorted(self.allowed)}"
            )

        is_write = op in WRITE_OPS
        if is_write and self.config.read_only:
            raise SecurityError(
                f"Server is in read-only mode; '{op}' is rejected."
            )

        return ValidatedQuery(sql=stripped, operation=op, is_write=is_write)

    def with_safety_limit(self, sql: str, op: str) -> str:
        """Append a LIMIT clause to bare SELECTs that lack one."""
        if op != "SELECT" or self.config.max_rows <= 0:
            return sql
        if re.search(r"\bLIMIT\s+\d+", sql, re.IGNORECASE):
            return sql
        return f"{sql}\nLIMIT {self.config.max_rows}"
