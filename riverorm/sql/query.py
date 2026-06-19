"""Dialect-independent description of SQL queries.

These frozen dataclasses describe *what* a query does without committing to any
particular SQL syntax. A :class:`~riverorm.sql.compiler.Compiler` paired with a
:class:`~riverorm.sql.dialect.Dialect` turns them into a concrete
``(sql, params)`` pair.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Operator(str, Enum):
    """Comparison operators supported in a :class:`Condition`.

    Mirrors the operators currently understood by ``Model.filter()``.
    """

    EQ = "="
    NE = "!="
    GT = ">"
    LT = "<"
    GTE = ">="
    LTE = "<="
    IN = "IN"


@dataclass(frozen=True)
class Column:
    """A reference to a column, optionally qualified by a table/alias.

    When ``alias`` is set the column compiles to ``"alias"."name"``; otherwise it
    compiles to ``"name"``. ``output_name`` renders an ``AS`` clause in SELECT
    projections (used for the ``rel__col`` aliases of ``select_related``).
    """

    name: str
    table: str | None = None
    output_name: str | None = None


@dataclass(frozen=True)
class Condition:
    """A single ``WHERE`` predicate: ``column <operator> value(s)``.

    For :attr:`Operator.IN`, ``value`` must be a sequence; each element becomes a
    positional parameter. For all other operators ``value`` is a single scalar.
    """

    column: Column
    operator: Operator
    value: Any
    negated: bool = False


@dataclass(frozen=True)
class OrderBy:
    """An ``ORDER BY`` term."""

    column: Column
    descending: bool = False


@dataclass(frozen=True)
class Join:
    """A ``LEFT JOIN`` of ``table`` (aliased as ``alias``) onto the query.

    The join condition is ``left.left_column = right.right_column`` where ``left``
    is identified by :attr:`left_table` and ``right`` by :attr:`alias`.
    """

    table: str
    alias: str
    left_table: str
    left_column: str
    right_column: str


@dataclass(frozen=True)
class SelectQuery:
    """A ``SELECT`` statement."""

    table: str
    columns: tuple[Column, ...] = ()
    table_alias: str | None = None
    joins: tuple[Join, ...] = ()
    where: tuple[Condition, ...] = ()
    order_by: tuple[OrderBy, ...] = ()
    limit: int | None = None
    offset: int | None = None
    count: bool = False


@dataclass(frozen=True)
class InsertQuery:
    """An ``INSERT`` statement.

    ``columns`` and ``values`` are positionally paired. ``returning`` names a
    column to render in a ``RETURNING`` clause (Postgres-style) when supported by
    the dialect.
    """

    table: str
    columns: tuple[str, ...]
    values: tuple[Any, ...]
    returning: str | None = None


@dataclass(frozen=True)
class UpdateQuery:
    """An ``UPDATE`` statement.

    ``assignments`` are positionally paired ``column``/``value`` tuples.
    """

    table: str
    columns: tuple[str, ...]
    values: tuple[Any, ...]
    where: tuple[Condition, ...] = field(default=())


@dataclass(frozen=True)
class DeleteQuery:
    """A ``DELETE`` statement."""

    table: str
    where: tuple[Condition, ...] = field(default=())
