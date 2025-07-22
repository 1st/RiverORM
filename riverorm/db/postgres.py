import logging

import asyncpg

from .base import BaseDatabase

logger = logging.getLogger("riverorm.db.postgres")


class PostgresDatabase(BaseDatabase):
    _conn: asyncpg.Connection | None
    _debug: bool

    def __init__(self, debug: bool = False):
        self._conn = None
        self._debug = debug
        if debug:
            logger.setLevel(logging.DEBUG)
        else:
            logger.setLevel(logging.INFO)

    async def connect(self, dsn: str) -> None:
        self._conn = await asyncpg.connect(dsn)

    async def close(self) -> None:
        if self._conn is None:
            raise Exception("Connection is already closed")
        await self._conn.close()

    async def execute(self, query: str, *args):
        if self._conn is None:
            raise Exception("Connection is not established")
        if self._debug:
            logger.debug(f"SQL: {query} - {args}")
        return await self._conn.execute(query, *args)

    async def fetch(self, query: str, *args):
        if self._conn is None:
            raise Exception("Connection is not established")
        if not query.strip().lower().startswith("select"):
            raise ValueError("Fetch can only be used with SELECT queries")
        if not query.strip().endswith(";"):
            query += ";"
        return await self._conn.fetch(query, *args)

    async def fetchrow(self, query: str, *args):
        if self._conn is None:
            raise Exception("Connection is not established")
        if not query.strip().lower().startswith("select"):
            raise ValueError("Fetchrow can only be used with SELECT queries")
        if not query.strip().endswith(";"):
            query += ";"
        return await self._conn.fetchrow(query, *args)

    @staticmethod
    def python_to_sql_type(py_type: type) -> str:
        if py_type is int:
            return "INTEGER"
        elif py_type is float:
            return "REAL"
        elif py_type is bool:
            return "BOOLEAN"
        elif py_type is str:
            return "TEXT"
        elif py_type.__name__ == "datetime":
            return "TIMESTAMP"
        elif py_type.__name__ == "date":
            return "DATE"
        elif py_type.__name__ == "UUID":
            return "UUID"
        else:
            raise TypeError(f"Unsupported Python type for SQL: {py_type}")
