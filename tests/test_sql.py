"""Pure unit tests for the dialect/compiler SQL foundation.

These tests are deliberately database-free: they exercise only the pure
dialect + compiler machinery and assert exact ``(sql, params)`` output.
"""

from datetime import date, datetime
from uuid import UUID

import pytest

from riverorm.sql import (
    Column,
    Compiler,
    Condition,
    DeleteQuery,
    InsertQuery,
    Join,
    Operator,
    OrderBy,
    PostgresDialect,
    SelectQuery,
    UpdateQuery,
)


@pytest.fixture
def compiler() -> Compiler:
    return Compiler(PostgresDialect())


# -- identifier quoting & placeholders --------------------------------------


def test_quote_basic():
    assert PostgresDialect().quote("users") == '"users"'


def test_quote_escapes_embedded_quotes():
    assert PostgresDialect().quote('we"ird') == '"we""ird"'


def test_placeholder_is_one_based():
    d = PostgresDialect()
    assert d.placeholder(1) == "$1"
    assert d.placeholder(3) == "$3"


def test_placeholder_rejects_zero():
    with pytest.raises(ValueError):
        PostgresDialect().placeholder(0)


# -- SELECT ------------------------------------------------------------------


def test_select_with_mixed_where_order_limit_offset(compiler: Compiler):
    query = SelectQuery(
        table="users",
        where=(
            Condition(Column("age"), Operator.GTE, 18),
            Condition(Column("status"), Operator.NE, "banned"),
            Condition(Column("id"), Operator.IN, [1, 2, 3]),
        ),
        order_by=(OrderBy(Column("created_at"), descending=True),),
        limit=10,
        offset=5,
    )
    sql, params = compiler.compile_select(query)
    assert sql == (
        'SELECT * FROM "users"'
        ' WHERE "age" >= $1 AND "status" != $2 AND "id" IN ($3, $4, $5)'
        ' ORDER BY "created_at" DESC'
        " LIMIT 10 OFFSET 5"
    )
    assert params == [18, "banned", 1, 2, 3]


def test_select_with_join_projection_and_aliases(compiler: Compiler):
    query = SelectQuery(
        table="order",
        table_alias="order",
        columns=(
            Column("id", table="order"),
            Column("user_id", table="order"),
            Column("username", table="user", output_name="user__username"),
        ),
        joins=(
            Join(
                table="user",
                alias="user",
                left_table="order",
                left_column="user_id",
                right_column="id",
            ),
        ),
    )
    sql, params = compiler.compile_select(query)
    assert sql == (
        'SELECT "order"."id", "order"."user_id",'
        ' "user"."username" AS "user__username"'
        ' FROM "order" AS "order"'
        ' LEFT JOIN "user" AS "user"'
        ' ON "order"."user_id" = "user"."id"'
    )
    assert params == []


def test_select_no_where(compiler: Compiler):
    sql, params = compiler.compile_select(SelectQuery(table="users", limit=1000))
    assert sql == 'SELECT * FROM "users" LIMIT 1000'
    assert params == []


# -- INSERT ------------------------------------------------------------------


def test_insert_with_returning(compiler: Compiler):
    query = InsertQuery(
        table="users",
        columns=("username", "email"),
        values=("alice", "alice@example.com"),
        returning="id",
    )
    sql, params = compiler.compile_insert(query)
    assert sql == ('INSERT INTO "users" ("username", "email") VALUES ($1, $2) RETURNING "id"')
    assert params == ["alice", "alice@example.com"]


# -- UPDATE & DELETE ---------------------------------------------------------


def test_update_with_where(compiler: Compiler):
    query = UpdateQuery(
        table="users",
        columns=("username", "email"),
        values=("bob", "bob@example.com"),
        where=(Condition(Column("id"), Operator.EQ, 7),),
    )
    sql, params = compiler.compile_update(query)
    assert sql == ('UPDATE "users" SET "username" = $1, "email" = $2 WHERE "id" = $3')
    assert params == ["bob", "bob@example.com", 7]


def test_delete_with_where(compiler: Compiler):
    query = DeleteQuery(
        table="users",
        where=(Condition(Column("id"), Operator.EQ, 42),),
    )
    sql, params = compiler.compile_delete(query)
    assert sql == 'DELETE FROM "users" WHERE "id" = $1'
    assert params == [42]


# -- type map & autoincrement ------------------------------------------------


@pytest.mark.parametrize(
    "annotation,expected",
    [
        (int, "INTEGER"),
        (float, "REAL"),
        (bool, "BOOLEAN"),
        (str, "TEXT"),
        (datetime, "TIMESTAMP"),
        (date, "DATE"),
        (UUID, "UUID"),
        (list, "JSONB"),
        (list[int], "JSONB"),
        (int | None, "INTEGER"),
        (str | None, "TEXT"),
    ],
)
def test_postgres_type_map(annotation, expected):
    assert PostgresDialect.python_to_sql_type(annotation) == expected


def test_postgres_type_map_rejects_unknown():
    with pytest.raises(TypeError):
        PostgresDialect.python_to_sql_type(object)


def test_postgres_autoincrement_pk():
    assert PostgresDialect().auto_increment_pk("id") == "id SERIAL PRIMARY KEY"


def test_supports_returning_flag():
    assert PostgresDialect().supports_returning is True
