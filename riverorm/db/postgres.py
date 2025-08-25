import logging
import types
import typing

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
        # Allow SELECT and INSERT ... RETURNING queries
        q = query.strip().lower()
        if not (q.startswith("select") or (q.startswith("insert") and "returning" in q)):
            raise ValueError(
                "Fetchrow can only be used with SELECT or INSERT ... RETURNING queries"
            )
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
        # Handle Union types (e.g., Optional[int], int | None)

        # For PEP 604 (int | None), __origin__ is types.UnionType in Python 3.10+
        union_types = (
            getattr(typing, "Union", None),
            getattr(types, "UnionType", None),
        )
        # Handle typing.Union and PEP 604 unions
        if (hasattr(py_type, "__origin__") and py_type.__origin__ in union_types) or (
            hasattr(types, "UnionType") and isinstance(py_type, types.UnionType)
        ):
            # Get the first non-None type from the union
            args = getattr(py_type, "__args__", None)
            if args is None:
                args = py_type.__args__ if hasattr(py_type, "__args__") else None
            if (
                args is None
                and hasattr(py_type, "__origin__")
                and hasattr(py_type.__origin__, "__args__")
            ):
                args = py_type.__origin__.__args__
            if args is None:
                # For PEP 604, __args__ is available
                args = getattr(py_type, "__args__", None)
            if args:
                py_type = next(t for t in args if t is not type(None))

        if py_type is int:
            return "INTEGER"
        elif py_type is float:
            return "REAL"
        elif py_type is bool:
            return "BOOLEAN"
        elif py_type is str:
            return "TEXT"
        elif hasattr(py_type, "__name__") and py_type.__name__ == "datetime":
            return "TIMESTAMP"
        elif hasattr(py_type, "__name__") and py_type.__name__ == "date":
            return "DATE"
        elif hasattr(py_type, "__name__") and py_type.__name__ == "UUID":
            return "UUID"
        elif (
            py_type is list
            or (hasattr(py_type, "__origin__") and py_type.__origin__ is list)
            or (hasattr(py_type, "__origin__") and py_type.__origin__ is typing.List)
        ):
            # For list types, use JSONB in PostgreSQL
            return "JSONB"
        else:
            raise TypeError(f"Unsupported Python type for SQL: {py_type}")

    @staticmethod
    def auto_increment_primary_key_sql(name: str) -> str:
        return f"{name} SERIAL PRIMARY KEY"
