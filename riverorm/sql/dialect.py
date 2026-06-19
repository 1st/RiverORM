"""SQL dialects: per-database syntax rules, kept pure (no DB, no I/O).

A :class:`Dialect` answers the small set of questions that differ between
databases: how to quote identifiers, how to render positional placeholders, how
Python types map to column types, how to declare an auto-increment primary key,
and how new-row primary keys are returned on insert.
"""

from __future__ import annotations

import types
import typing
from abc import ABC, abstractmethod


class Dialect(ABC):
    """Abstract, stateless description of a database's SQL syntax."""

    #: Whether ``INSERT ... RETURNING <pk>`` is supported to fetch generated PKs.
    supports_returning: bool = False

    @abstractmethod
    def quote(self, identifier: str) -> str:
        """Quote an identifier (table/column/alias), escaping embedded quotes."""
        ...

    @abstractmethod
    def placeholder(self, index: int) -> str:
        """Render the positional placeholder for a 1-based parameter ``index``."""
        ...

    @staticmethod
    @abstractmethod
    def python_to_sql_type(annotation: type) -> str:
        """Map a Python type annotation to this dialect's SQL column type."""
        ...

    @abstractmethod
    def auto_increment_pk(self, column: str) -> str:
        """Render a column definition declaring an auto-increment primary key."""
        ...

    def render_returning(self, column: str) -> str:
        """Render a ``RETURNING <column>`` clause for an insert.

        Dialects without ``RETURNING`` support return an empty string.
        """
        if not self.supports_returning:
            return ""
        return f"RETURNING {self.quote(column)}"

    def boolean_literal(self, value: bool) -> str:
        """Render a boolean literal (used when inlining, not for params)."""
        return "TRUE" if value else "FALSE"


class PostgresDialect(Dialect):
    """PostgreSQL syntax: ``"id"`` quoting and ``$1`` placeholders."""

    supports_returning = True

    def quote(self, identifier: str) -> str:
        escaped = identifier.replace('"', '""')
        return f'"{escaped}"'

    def placeholder(self, index: int) -> str:
        if index < 1:
            raise ValueError("placeholder index is 1-based and must be >= 1")
        return f"${index}"

    @staticmethod
    def python_to_sql_type(annotation: type) -> str:
        # Ported verbatim from PostgresDatabase.python_to_sql_type for parity.
        py_type: typing.Any = annotation

        # Handle Union types (e.g., Optional[int], int | None).
        # For PEP 604 (int | None), __origin__ is types.UnionType in Python 3.10+.
        union_types = (
            getattr(typing, "Union", None),
            getattr(types, "UnionType", None),
        )
        if (hasattr(py_type, "__origin__") and py_type.__origin__ in union_types) or (
            hasattr(types, "UnionType") and isinstance(py_type, types.UnionType)
        ):
            args = getattr(py_type, "__args__", None)
            if (
                args is None
                and hasattr(py_type, "__origin__")
                and hasattr(py_type.__origin__, "__args__")
            ):
                args = py_type.__origin__.__args__
            if args:
                py_type = next(t for t in args if t is not type(None))

        if py_type is int:
            return "INTEGER"
        elif py_type is float:
            return "REAL"
        elif py_type is bool:
            return "BOOLEAN"
        elif py_type is str:
            return "TEXT"
        elif hasattr(py_type, "__name__") and py_type.__name__ == "datetime":
            return "TIMESTAMP"
        elif hasattr(py_type, "__name__") and py_type.__name__ == "date":
            return "DATE"
        elif hasattr(py_type, "__name__") and py_type.__name__ == "UUID":
            return "UUID"
        elif py_type is list or (hasattr(py_type, "__origin__") and py_type.__origin__ is list):
            return "JSONB"
        else:
            raise TypeError(f"Unsupported Python type for SQL: {py_type}")

    def auto_increment_pk(self, column: str) -> str:
        return f"{column} SERIAL PRIMARY KEY"
