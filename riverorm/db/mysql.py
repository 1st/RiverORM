from __future__ import annotations

import logging

import aiomysql

from riverorm.sql import Dialect, MySQLDialect

from .base import BaseDatabase

logger = logging.getLogger(__name__)


class MySQLDatabase(BaseDatabase):
    _conn: aiomysql.Connection | None
    _debug: bool
    _dsn: str
    _dialect: Dialect = MySQLDialect()

    def __init__(self, dsn: str, debug: bool = False):
        self._conn = None
        self._debug = debug
        self._dsn = dsn
        if debug:
            logger.setLevel(logging.DEBUG)
        else:
            logger.setLevel(logging.INFO)

    @property
    def dialect(self) -> Dialect:
        return self._dialect

    def dsn_to_dict(self, dsn: str) -> dict:
        """Convert DSN string (RFC 1738 style) to a dictionary for aiomysql.connect."""
        from urllib.parse import unquote, urlparse

        url = urlparse(dsn)
        if url.scheme not in ("mysql", "mariadb"):
            raise ValueError(f"Unsupported DSN scheme: {url.scheme}")

        # Extract user, password, host, port, db
        user = unquote(url.username) if url.username else None
        password = unquote(url.password) if url.password else None
        host = url.hostname or "localhost"
        port = url.port or 3306
        db = url.path.lstrip("/") if url.path else None

        dct = {"host": host, "port": port}
        if user:
            dct["user"] = user
        if password:
            dct["password"] = password
        if db:
            dct["db"] = db
        # Optionally: parse query params for extra options
        # from urllib.parse import parse_qs
        # opts = parse_qs(url.query)
        # for k, v in opts.items():
        #     dct[k] = v[0] if v else None
        return dct

    async def connect(self) -> None:
        # autocommit so writes/DDL persist without explicit transaction handling,
        # matching asyncpg's default behaviour.
        self._conn = await aiomysql.connect(autocommit=True, **self.dsn_to_dict(self._dsn))
        self.is_connected = True

    async def close(self) -> None:
        if self._conn is None:
            raise Exception("Connection is already closed")
        self._conn.close()  # MySQL driver still uses regular sync style for closing connection
        self.is_connected = False

    async def execute(self, query: str, *args):
        if self._conn is None:
            raise Exception("Connection is not established")
        if self._debug:
            logger.debug(f"SQL: {query} - {args}")
        async with self._conn.cursor() as cursor:
            await cursor.execute(query, args)
            return cursor.rowcount

    async def fetch(self, query: str, *args):
        if self._conn is None:
            raise Exception("Connection is not established")
        if self._debug:
            logger.debug(f"SQL: {query} - {args}")
        async with self._conn.cursor(aiomysql.DictCursor) as cursor:
            await cursor.execute(query, args)
            return await cursor.fetchall()

    async def fetchrow(self, query: str, *args):
        if self._conn is None:
            raise Exception("Connection is not established")
        if self._debug:
            logger.debug(f"SQL: {query} - {args}")
        async with self._conn.cursor(aiomysql.DictCursor) as cursor:
            await cursor.execute(query, args)
            return await cursor.fetchone()

    async def update(self, query: str, *args):
        if self._conn is None:
            raise Exception("Connection is not established")
        if self._debug:
            logger.debug(f"SQL: {query} - {args}")
        async with self._conn.cursor() as cursor:
            await cursor.execute(query, args)
            return cursor.rowcount

    async def execute_insert(self, query: str, *args):
        """Run an ``INSERT`` and return the auto-increment PK via ``lastrowid``.

        MySQL has no ``RETURNING`` clause; the generated primary key is taken
        from ``cursor.lastrowid``. Assumes a single integer auto-increment PK.
        """
        if self._conn is None:
            raise Exception("Connection is not established")
        if self._debug:
            logger.debug(f"SQL: {query} - {args}")
        async with self._conn.cursor() as cursor:
            await cursor.execute(query, args)
            return cursor.lastrowid
