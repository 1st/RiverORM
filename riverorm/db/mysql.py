import logging

import aiomysql

from .base import BaseDatabase

logger = logging.getLogger("riverorm.db.postgres")


class MySQLDatabase(BaseDatabase):
    _conn: aiomysql.Connection | None
    _debug: bool

    def __init__(self, debug: bool = False):
        self._conn = None
        self._debug = debug
        if debug:
            logger.setLevel(logging.DEBUG)
        else:
            logger.setLevel(logging.INFO)

    def dsn_to_dict(self, dsn: str) -> dict:
        """Convert DSN string to a dictionary."""
        # TODO: Implement a proper DSN parser
        parts = dsn.split(";")
        return {k: v for k, v in (part.split("=") for part in parts if "=" in part)}

    async def connect(self, dsn: str) -> None:
        self._conn = await aiomysql.connect(**self.dsn_to_dict(dsn))

    async def close(self) -> None:
        if self._conn is None:
            raise Exception("Connection is already closed")
        await self._conn.close()

    async def execute(self, query: str, *args):
        if self._conn is None:
            raise Exception("Connection is not established")
        if self._debug:
            logger.debug(f"SQL: {query} - {args}")
        with self._conn.cursor() as cursor:
            await cursor.execute(query, args)
            return cursor.rowcount

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

    async def update(self, query: str, *args):
        if self._conn is None:
            raise Exception("Connection is not established")
        if not query.strip().lower().startswith("update"):
            raise ValueError("Update can only be used with UPDATE queries")
        if not query.strip().endswith(";"):
            query += ";"
        return await self._conn.execute(query, *args)

    @staticmethod
    def python_to_sql_type(py_type: type) -> str:
        if py_type is int:
            return "INT"
        elif py_type is float:
            return "FLOAT"
        elif py_type is str:
            return "VARCHAR(255)"
        elif py_type is bool:
            return "BOOLEAN"
        elif py_type is bytes:
            return "BLOB"
        else:
            raise ValueError(f"Unsupported type: {py_type}")

    @staticmethod
    def auto_increment_primary_key_sql(name: str) -> str:
        return f"{name} INTEGER PRIMARY KEY AUTO_INCREMENT"
