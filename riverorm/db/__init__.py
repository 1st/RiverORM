from functools import cache

from riverorm import constants
from riverorm.config import config

from .base import BaseDatabase
from .mysql import MySQLDatabase
from .postgres import PostgresDatabase


@cache
def get_database(db_type: str, debug: bool = False) -> BaseDatabase:
    if db_type.lower() == constants.POSTGRES:
        return PostgresDatabase(config.POSTGRES_DSN, debug)
    elif db_type.lower() == constants.MYSQL:
        return MySQLDatabase(config.MYSQL_DSN, debug)
    else:
        raise ValueError(f"Unsupported database type: {db_type}")


db = get_database(config.DB_TYPE, debug=config.DEBUG)
