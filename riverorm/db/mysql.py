import logging

import aiomysql

from .base import BaseDatabase

logger = logging.getLogger(__name__)


class MySQLDatabase(BaseDatabase):
    _conn: aiomysql.Connection | None
    _debug: bool
    _dsn: str

    def __init__(self, dsn: str, debug: bool = False):
        self._conn = None
        self._debug = debug
        self._dsn = dsn
        if debug:
            logger.setLevel(logging.DEBUG)
        else:
            logger.setLevel(logging.INFO)

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
        self._conn = await aiomysql.connect(**self.dsn_to_dict(self._dsn))
        self.is_connected = True

    async def close(self) -> None:
        if self._conn is None:
            raise Exception("Connection is already closed")
        self._conn.close()
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
        if not query.strip().lower().startswith("select"):
            raise ValueError("Fetch can only be used with SELECT queries")
        if not query.strip().endswith(";"):
            query += ";"
        async with self._conn.cursor(aiomysql.DictCursor) as cursor:
            await cursor.execute(query, args)
            return await cursor.fetchall()

    async def fetchrow(self, query: str, *args):
        if self._conn is None:
            raise Exception("Connection is not established")
        if not query.strip().lower().startswith("select"):
            raise ValueError("Fetchrow can only be used with SELECT queries")
        if not query.strip().endswith(";"):
            query += ";"
        async with self._conn.cursor(aiomysql.DictCursor) as cursor:
            await cursor.execute(query, args)
            return await cursor.fetchone()

    async def update(self, query: str, *args):
        if self._conn is None:
            raise Exception("Connection is not established")
        if not query.strip().lower().startswith("update"):
            raise ValueError("Update can only be used with UPDATE queries")
        if not query.strip().endswith(";"):
            query += ";"
        async with self._conn.cursor() as cursor:
            await cursor.execute(query, args)
            return cursor.rowcount

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
