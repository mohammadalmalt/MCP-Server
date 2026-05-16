"""MySQL connection pool + execution helpers.

Uses mysql-connector-python's pooled connections. Adds:
- Retry on transient errors (lost connection, deadlock).
- Health-check before checkout.
- Unified execute interface that always uses parameterised queries.
"""

from __future__ import annotations

import logging
import time
from contextlib import contextmanager
from typing import Any, Iterator, Optional

import mysql.connector
from mysql.connector import errorcode
from mysql.connector.pooling import MySQLConnectionPool, PooledMySQLConnection

from .config import Config
from .exceptions import ConnectionError as PoolConnectionError

log = logging.getLogger(__name__)

# MySQL errno values worth retrying once.
RETRYABLE_ERRNOS = {
    errorcode.CR_SERVER_LOST,
    errorcode.CR_SERVER_GONE_ERROR,
    errorcode.ER_LOCK_DEADLOCK,
    errorcode.ER_LOCK_WAIT_TIMEOUT,
}


class MySqlPool:
    def __init__(self, config: Config):
        self.config = config
        self._pool: Optional[MySQLConnectionPool] = None

    def _build(self) -> MySQLConnectionPool:
        try:
            return MySQLConnectionPool(
                pool_name=self.config.pool_name,
                pool_size=self.config.pool_size,
                pool_reset_session=True,
                host=self.config.host,
                port=self.config.port,
                user=self.config.user,
                password=self.config.password,
                database=self.config.database,
                connection_timeout=self.config.connection_timeout,
                autocommit=False,
                use_pure=True,
            )
        except mysql.connector.Error as e:
            raise PoolConnectionError(
                f"Failed to create connection pool for '{self.config.database}': {e}"
            ) from e

    @property
    def pool(self) -> MySQLConnectionPool:
        if self._pool is None:
            self._pool = self._build()
        return self._pool

    @contextmanager
    def connection(self) -> Iterator[PooledMySQLConnection]:
        conn = self._checkout()
        try:
            yield conn
        finally:
            try:
                conn.close()  # returns to pool
            except Exception:  # noqa: BLE001
                log.warning("Failed to return connection to pool", exc_info=True)

    def _checkout(self) -> PooledMySQLConnection:
        last_err: Optional[Exception] = None
        for attempt in range(2):
            try:
                conn = self.pool.get_connection()
                if not conn.is_connected():
                    conn.reconnect(attempts=2, delay=1)
                return conn
            except mysql.connector.Error as e:
                last_err = e
                if e.errno in RETRYABLE_ERRNOS and attempt == 0:
                    log.warning("Retrying connection checkout after error: %s", e)
                    time.sleep(0.2)
                    continue
                break
        raise PoolConnectionError(f"Could not check out a connection: {last_err}")

    def execute(
        self,
        sql: str,
        params: Optional[tuple | dict] = None,
        *,
        commit: bool = False,
    ) -> dict[str, Any]:
        """Execute a single statement with parameterised values.

        Returns a dict with rows (for SELECTs), rowcount, and lastrowid.
        """
        with self.connection() as conn:
            cursor = conn.cursor(dictionary=True)
            try:
                cursor.execute(sql, params or ())
                rows: list[dict[str, Any]] = []
                if cursor.with_rows:
                    rows = cursor.fetchall()
                rowcount = cursor.rowcount
                lastrowid = cursor.lastrowid
                if commit:
                    conn.commit()
                return {
                    "rows": rows,
                    "rowcount": rowcount,
                    "lastrowid": lastrowid,
                }
            except mysql.connector.Error:
                if commit:
                    conn.rollback()
                raise
            finally:
                cursor.close()

    def execute_many(
        self,
        statements: list[tuple[str, Optional[tuple | dict]]],
    ) -> list[dict[str, Any]]:
        """Run a batch of statements inside a single transaction.

        Rolls back the whole batch on any failure.
        """
        results: list[dict[str, Any]] = []
        with self.connection() as conn:
            cursor = conn.cursor(dictionary=True)
            try:
                conn.start_transaction()
                for sql, params in statements:
                    cursor.execute(sql, params or ())
                    rows = cursor.fetchall() if cursor.with_rows else []
                    results.append({
                        "sql": sql,
                        "rows": rows,
                        "rowcount": cursor.rowcount,
                        "lastrowid": cursor.lastrowid,
                    })
                conn.commit()
                return results
            except mysql.connector.Error:
                conn.rollback()
                raise
            finally:
                cursor.close()

    def ping(self) -> bool:
        with self.connection() as conn:
            conn.ping(reconnect=True, attempts=2, delay=1)
            return conn.is_connected()
