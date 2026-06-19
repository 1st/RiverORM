"""Dialect-agnostic SQL building for RiverORM.

This package provides a clean seam between *describing* a query (the frozen
dataclasses in :mod:`riverorm.sql.query`) and *rendering* it to a concrete SQL
string for a particular database (:class:`~riverorm.sql.dialect.Dialect` plus
:class:`~riverorm.sql.compiler.Compiler`).

It is intentionally pure: no database connections, no I/O.
"""

from .compiler import Compiler as Compiler
from .dialect import Dialect as Dialect
from .dialect import MySQLDialect as MySQLDialect
from .dialect import PostgresDialect as PostgresDialect
from .query import Column as Column
from .query import Condition as Condition
from .query import DeleteQuery as DeleteQuery
from .query import InsertQuery as InsertQuery
from .query import Join as Join
from .query import Operator as Operator
from .query import OrderBy as OrderBy
from .query import SelectQuery as SelectQuery
from .query import UpdateQuery as UpdateQuery
