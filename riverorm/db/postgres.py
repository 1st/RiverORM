from __future__ import annotations

import logging

import asyncpg

from riverorm.sql import Dialect, PostgresDialect

from .base import BaseDatabase

logger = logging.getLogger(__name__)


class PostgresDatabase(BaseDatabase):
    _conn: asyncpg.Connection | None
    _debug: bool
    _dsn: str
    _dialect: Dialect = PostgresDialect()

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

    async def connect(self) -> None:
        self._conn = await asyncpg.connect(self._dsn)
        self.is_connected = True

    async def close(self) -> None:
        if self._conn is None:
            raise Exception("Connection is already closed")
        await self._conn.close()
        self.is_connected = False

    async def execute(self, query: str, *args):
        if self._conn is None:
            raise Exception("Connection is not established")
        if self._debug:
            logger.debug(f"SQL: {query} - {args}")
        return await self._conn.execute(query, *args)

    async def fetch(self, query: str, *args):
        if self._conn is None:
            raise Exception("Connection is not established")
        if self._debug:
            logger.debug(f"SQL: {query} - {args}")
        return await self._conn.fetch(query, *args)

    async def fetchrow(self, query: str, *args):
        if self._conn is None:
            raise Exception("Connection is not established")
        if self._debug:
            logger.debug(f"SQL: {query} - {args}")
        return await self._conn.fetchrow(query, *args)

    async def update(self, query: str, *args):
        if self._conn is None:
            raise Exception("Connection is not established")
        if self._debug:
            logger.debug(f"SQL: {query} - {args}")
        return await self._conn.execute(query, *args)

    async def execute_insert(self, query: str, *args):
        """Run an ``INSERT ... RETURNING`` and return the generated PK value.

        Postgres supports ``RETURNING``, so the caller is expected to append a
        ``RETURNING`` clause; the first returned column is the new primary key.
        """
        if self._conn is None:
            raise Exception("Connection is not established")
        if self._debug:
            logger.debug(f"SQL: {query} - {args}")
        row = await self._conn.fetchrow(query, *args)
        return next(iter(row.values())) if row else None
