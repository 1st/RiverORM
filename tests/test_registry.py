"""DatabaseRegistry and Meta.db_alias routing tests.

Pure unit tests (no real connections): registration rules, default selection,
error paths for unknown/duplicate aliases, and model→connection routing.
"""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from typing import Any

import pytest

from riverorm import Field, Model
from riverorm.db import BaseDatabase, DatabaseRegistry
from riverorm.db.registry import DatabaseRegistryError
from riverorm.sql import Dialect
from riverorm.sql.dialect import PostgresDialect


class FakeDatabase(BaseDatabase):
    """Minimal in-memory BaseDatabase used to exercise registry logic."""

    def __init__(self, dsn: str = "fake://", debug: bool = False) -> None:
        self.dsn = dsn
        self.debug = debug
        self.is_connected = False

    @property
    def dialect(self) -> Dialect:
        return PostgresDialect()

    async def connect(self) -> None:
        self.is_connected = True

    async def close(self) -> None:
        self.is_connected = False

    async def execute(self, query: str, *args: Any) -> Any:
        return None

    async def fetch(self, query: str, *args: Any) -> Sequence[Any]:
        return []

    async def fetchrow(self, query: str, *args: Any) -> Any:
        return None

    async def update(self, query: str, *args: Any) -> Any:
        return None

    async def execute_insert(self, query: str, *args: Any) -> Any:
        return None

    async def execute_returning_rowcount(self, query: str, *args: Any) -> int:
        return 0


@pytest.fixture
def isolated_registry() -> Iterator[None]:
    """Snapshot the global registry, give the test a clean slate, then restore."""
    saved_connections = dict(DatabaseRegistry._connections)
    saved_default = DatabaseRegistry._default
    DatabaseRegistry.clear()
    try:
        yield
    finally:
        DatabaseRegistry._connections = saved_connections
        DatabaseRegistry._default = saved_default


# ---------------------------------------------------------------------------
# Registration & default selection
# ---------------------------------------------------------------------------


def test_first_registered_becomes_default(isolated_registry):
    db = FakeDatabase()
    DatabaseRegistry.register("primary", db)
    assert DatabaseRegistry.get() is db
    assert DatabaseRegistry.get("primary") is db


def test_second_registration_does_not_change_default(isolated_registry):
    a, b = FakeDatabase(), FakeDatabase()
    DatabaseRegistry.register("a", a)
    DatabaseRegistry.register("b", b)
    assert DatabaseRegistry.get() is a  # default stays the first one


def test_register_duplicate_alias_raises(isolated_registry):
    DatabaseRegistry.register("dup", FakeDatabase())
    with pytest.raises(DatabaseRegistryError, match="already registered"):
        DatabaseRegistry.register("dup", FakeDatabase())


def test_set_default_switches_connection(isolated_registry):
    a, b = FakeDatabase(), FakeDatabase()
    DatabaseRegistry.register("a", a)
    DatabaseRegistry.register("b", b)
    DatabaseRegistry.set_default("b")
    assert DatabaseRegistry.get() is b


def test_set_default_unknown_alias_raises(isolated_registry):
    DatabaseRegistry.register("a", FakeDatabase())
    with pytest.raises(DatabaseRegistryError, match="not registered"):
        DatabaseRegistry.set_default("ghost")


# ---------------------------------------------------------------------------
# get() error paths
# ---------------------------------------------------------------------------


def test_get_with_no_connections_raises(isolated_registry):
    with pytest.raises(DatabaseRegistryError, match="No database connections registered"):
        DatabaseRegistry.get()


def test_get_unknown_alias_raises(isolated_registry):
    DatabaseRegistry.register("a", FakeDatabase())
    with pytest.raises(DatabaseRegistryError, match="No database connection found"):
        DatabaseRegistry.get("ghost")


def test_clear_resets_connections_and_default(isolated_registry):
    DatabaseRegistry.register("a", FakeDatabase())
    DatabaseRegistry.clear()
    assert DatabaseRegistry._connections == {}
    assert DatabaseRegistry._default is None
    with pytest.raises(DatabaseRegistryError):
        DatabaseRegistry.get()


# ---------------------------------------------------------------------------
# Meta.db_alias routing
# ---------------------------------------------------------------------------


def test_model_without_alias_uses_default(isolated_registry):
    default_db = FakeDatabase()
    DatabaseRegistry.register("default", default_db)

    class Plain(Model):
        id: int | None = Field(default=None)

    assert Plain.db() is default_db


def test_model_with_alias_routes_to_named_connection(isolated_registry):
    primary, secondary = FakeDatabase(), FakeDatabase()
    DatabaseRegistry.register("primary", primary)
    DatabaseRegistry.register("secondary", secondary)

    class Routed(Model):
        id: int | None = Field(default=None)

        class Meta:
            db_alias = "secondary"

    assert Routed.db() is secondary  # not the default ("primary")


def test_model_with_unregistered_alias_raises(isolated_registry):
    DatabaseRegistry.register("primary", FakeDatabase())

    class Orphan(Model):
        id: int | None = Field(default=None)

        class Meta:
            db_alias = "missing"

    with pytest.raises(DatabaseRegistryError, match="No database connection found"):
        Orphan.db()
