from .base import BaseDatabase
from .mysql import MySQLDatabase
from .postgres import PostgresDatabase


def get_database(db_type: str, debug: bool = False) -> BaseDatabase:
    if db_type.lower() == "postgres":
        return PostgresDatabase(debug)
    elif db_type.lower() == "mysql":
        return MySQLDatabase(debug)
    else:
        raise ValueError(f"Unsupported database type: {db_type}")


db = get_database("postgres", debug=True)  # Default to Postgres for now
