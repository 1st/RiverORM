"""Database connection registry for managing multiple database instances."""

from riverorm.db import BaseDatabase


class DatabaseRegistryError(Exception):
    pass


class DatabaseRegistry:
    _connections: dict[str, BaseDatabase] = {}
    _default: str | None = None

    @classmethod
    def register(cls, alias: str, db_instance: BaseDatabase):
        """
        Register a database instance with a given alias.

        The first registered instance becomes the default if no default is set.
        """
        if alias in cls._connections:
            raise DatabaseRegistryError(f"DB alias '{alias}' is already registered.")
        cls._connections[alias] = db_instance
        if cls._default is None:
            cls._default = alias

    @classmethod
    def set_default(cls, alias: str):
        """Set the default database connection by its alias."""
        if alias not in cls._connections:
            raise DatabaseRegistryError(f"DB alias '{alias}' is not registered.")
        cls._default = alias

    @classmethod
    def get(cls, alias: str | None = None) -> BaseDatabase:
        """Retrieve a database instance by its alias or the default if alias is None."""
        if not cls._connections:
            raise DatabaseRegistryError("No database connections registered.")
        if alias is None:
            alias = cls._default
        if alias is None or alias not in cls._connections:
            raise DatabaseRegistryError(f"No database connection found for alias '{alias}'.")
        return cls._connections[alias]

    @classmethod
    def clear(cls):
        """Clear all registered database connections and reset the default."""
        cls._connections.clear()
        cls._default = None

    @classmethod
    async def connect(cls):
        """Connect all registered database instances."""
        for db in cls._connections.values():
            if not db.is_connected:
                await db.connect()
