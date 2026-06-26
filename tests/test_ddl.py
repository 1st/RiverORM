"""DDL generation tests: unique / index Field metadata applied to CREATE TABLE.

Covers the pure dialect SQL, the statements ``create_table`` actually emits, and
a real uniqueness-constraint violation on both backends.
"""

from __future__ import annotations

import pytest

from riverorm import Field, Model
from riverorm.sql.dialect import MySQLDialect, PostgresDialect


class Account(Model):
    id: int | None = Field(default=None)
    email: str = Field(unique=True, max_length=200)
    slug: str = Field(index=True, max_length=100)
    name: str = Field(default="", max_length=100)


@pytest.fixture
def db_models() -> list[type[Model]]:
    # Override the conftest default so the fixture creates/drops our DDL model.
    return [Account]


# ---------------------------------------------------------------------------
# Pure dialect SQL (no DB)
# ---------------------------------------------------------------------------


def test_postgres_create_index_is_idempotent():
    sql = PostgresDialect().create_index("account", "slug", name="idx_account_slug")
    assert sql == 'CREATE INDEX IF NOT EXISTS "idx_account_slug" ON "account" ("slug");'


def test_postgres_create_unique_index():
    sql = PostgresDialect().create_index("account", "email", name="uq_account_email", unique=True)
    assert sql == ('CREATE UNIQUE INDEX IF NOT EXISTS "uq_account_email" ON "account" ("email");')


def test_mysql_create_index_uses_backticks():
    sql = MySQLDialect().create_index("account", "slug", name="idx_account_slug")
    assert sql == "CREATE INDEX `idx_account_slug` ON `account` (`slug`);"


# ---------------------------------------------------------------------------
# create_table emits the right statements (capture, no real execution)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_table_emits_unique_and_index(monkeypatch):
    executed: list[str] = []

    async def fake_execute(sql: str, *args):
        executed.append(sql)

    monkeypatch.setattr(Account.db(), "execute", fake_execute)

    await Account.create_table()

    create = next(s for s in executed if s.startswith("CREATE TABLE"))
    # UNIQUE is attached to the unique column...
    assert "UNIQUE" in create
    assert "email" in create
    # ...and a standalone CREATE INDEX is emitted for the indexed (non-unique) column.
    index_stmts = [s for s in executed if s.startswith("CREATE") and "INDEX" in s]
    assert any("slug" in s for s in index_stmts)
    # The unique column does not get a second, redundant standalone index.
    assert not any("email" in s for s in index_stmts)


# ---------------------------------------------------------------------------
# Real constraint enforcement (both backends via conftest parametrization)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_unique_constraint_rejects_duplicate(db_setup_and_teardown):
    await Account(email="a@ex.com", slug="alpha").save()

    with pytest.raises(Exception):  # noqa: B017 - driver-specific IntegrityError
        await Account(email="a@ex.com", slug="beta").save()


@pytest.mark.asyncio
async def test_unique_constraint_allows_distinct(db_setup_and_teardown):
    await Account(email="a@ex.com", slug="alpha").save()
    await Account(email="b@ex.com", slug="beta").save()

    rows = await Account.objects.all()
    assert {r.email for r in rows} == {"a@ex.com", "b@ex.com"}
