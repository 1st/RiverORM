"""Render dialect-independent query dataclasses to ``(sql, params)``.

The :class:`Compiler` is dialect-agnostic: every identifier passes through
``dialect.quote()`` and every value becomes a positional parameter rendered via
``dialect.placeholder(i)``. Swapping the :class:`~riverorm.sql.dialect.Dialect`
is the only thing needed to target a different database.
"""

from __future__ import annotations

from typing import Any

from .dialect import Dialect
from .query import (
    Column,
    Condition,
    DeleteQuery,
    InsertQuery,
    Operator,
    SelectQuery,
    UpdateQuery,
)


class Compiler:
    """Compile query dataclasses into SQL strings + positional params."""

    def __init__(self, dialect: Dialect) -> None:
        self.dialect = dialect

    # -- public API ---------------------------------------------------------

    def compile_select(self, query: SelectQuery) -> tuple[str, list[Any]]:
        params: list[Any] = []
        if query.count:
            columns = "COUNT(*)"
        elif query.columns:
            columns = ", ".join(self._render_column(c, projection=True) for c in query.columns)
        else:
            columns = "*"
        table = self.dialect.quote(query.table)
        if query.table_alias:
            table = f"{table} AS {self.dialect.quote(query.table_alias)}"

        sql = f"SELECT {columns} FROM {table}"

        for join in query.joins:
            sql += (
                f" LEFT JOIN {self.dialect.quote(join.table)}"
                f" AS {self.dialect.quote(join.alias)}"
                f" ON {self.dialect.quote(join.left_table)}.{self.dialect.quote(join.left_column)}"
                f" = {self.dialect.quote(join.alias)}.{self.dialect.quote(join.right_column)}"
            )

        sql += self._render_where(query.where, params)

        if query.order_by:
            terms = ", ".join(
                f"{self._render_column(o.column)} {'DESC' if o.descending else 'ASC'}"
                for o in query.order_by
            )
            sql += f" ORDER BY {terms}"
        if query.limit is not None:
            sql += f" LIMIT {query.limit}"
        if query.offset is not None:
            sql += f" OFFSET {query.offset}"

        return sql, params

    def compile_insert(self, query: InsertQuery) -> tuple[str, list[Any]]:
        params: list[Any] = list(query.values)
        cols = ", ".join(self.dialect.quote(c) for c in query.columns)
        placeholders = ", ".join(self.dialect.placeholder(i + 1) for i in range(len(query.values)))
        sql = f"INSERT INTO {self.dialect.quote(query.table)} ({cols}) VALUES ({placeholders})"
        if query.returning:
            clause = self.dialect.render_returning(query.returning)
            if clause:
                sql += f" {clause}"
        return sql, params

    def compile_update(self, query: UpdateQuery) -> tuple[str, list[Any]]:
        params: list[Any] = list(query.values)
        assignments = ", ".join(
            f"{self.dialect.quote(col)} = {self.dialect.placeholder(i + 1)}"
            for i, col in enumerate(query.columns)
        )
        sql = f"UPDATE {self.dialect.quote(query.table)} SET {assignments}"
        sql += self._render_where(query.where, params)
        return sql, params

    def compile_delete(self, query: DeleteQuery) -> tuple[str, list[Any]]:
        params: list[Any] = []
        sql = f"DELETE FROM {self.dialect.quote(query.table)}"
        sql += self._render_where(query.where, params)
        return sql, params

    # -- helpers ------------------------------------------------------------

    def _render_column(self, column: Column, projection: bool = False) -> str:
        ref = self.dialect.quote(column.name)
        if column.table:
            ref = f"{self.dialect.quote(column.table)}.{ref}"
        if projection and column.output_name:
            ref = f"{ref} AS {self.dialect.quote(column.output_name)}"
        return ref

    def _render_where(self, where: tuple[Condition, ...], params: list[Any]) -> str:
        if not where:
            return ""
        clauses = [self._render_condition(c, params) for c in where]
        return " WHERE " + " AND ".join(clauses)

    def _render_condition(self, condition: Condition, params: list[Any]) -> str:
        col = self._render_column(condition.column)
        if condition.operator is Operator.IN:
            values = list(condition.value)
            placeholders = ", ".join(
                self.dialect.placeholder(len(params) + i + 1) for i in range(len(values))
            )
            params.extend(values)
            clause = f"{col} IN ({placeholders})"
        else:
            params.append(condition.value)
            clause = f"{col} {condition.operator.value} {self.dialect.placeholder(len(params))}"
        if condition.negated:
            return f"NOT ({clause})"
        return clause
