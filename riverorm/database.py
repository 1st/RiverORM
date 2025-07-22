import logging

import asyncpg

logger = logging.getLogger("riverorm")
_connection: asyncpg.Connection | None = None


async def connect(dsn: str):
    global _connection
    _connection = await asyncpg.connect(dsn)


async def close():
    # global _connection
    if _connection is None:
        raise Exception("Connection is already closed")
    await _connection.close()


async def execute(query: str, *args):
    if _connection is None:
        raise Exception("Connection is not established")
    logger.debug(f"SQL: {query} - {args}")
    return await _connection.execute(query, *args)


async def fetch(query: str, *args):
    if _connection is None:
        raise Exception("Connection is not established")
    if not query.strip().lower().startswith("select"):
        raise ValueError("Fetch can only be used with SELECT queries")
    if not query.strip().endswith(";"):
        query += ";"
    return await _connection.fetch(query, *args)


async def fetchrow(query: str, *args):
    if _connection is None:
        raise Exception("Connection is not established")
    if not query.strip().lower().startswith("select"):
        raise ValueError("Fetchrow can only be used with SELECT queries")
    if not query.strip().endswith(";"):
        query += ";"
    return await _connection.fetchrow(query, *args)
