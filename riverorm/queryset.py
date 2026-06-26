"""Chainable, immutable, lazy query API for RiverORM.

A :class:`QuerySet` describes a read query as accumulated state (filters,
ordering, limits, relation specs). It never builds SQL strings itself: when
executed it assembles a :class:`~riverorm.sql.query.SelectQuery` and hands it to
the model's compiler. Every chaining method returns a brand-new ``QuerySet`` so
instances are immutable and freely reusable.

Execution is lazy. A ``QuerySet`` runs only when awaited (``await qs``), iterated
(``async for``), or when a terminal method (``all``/``get``/``first``/``count``/
``exists``) is awaited.

The :class:`Manager`, reached through ``Model.objects``, is a stateless factory
that hands out fresh ``QuerySet`` objects bound to its model.
"""

from __future__ import annotations

import dataclasses
from collections.abc import AsyncIterator, Generator
from typing import TYPE_CHECKING, Any, Generic, TypeVar

from riverorm.fields import FieldRef
from riverorm.sql import Column, Condition, DeleteQuery, OrderBy, SelectQuery, UpdateQuery

if TYPE_CHECKING:
    from riverorm.models import Model

T = TypeVar("T", bound="Model")
M = TypeVar("M", bound="Model")


class DoesNotExist(Exception):
    """Raised by :meth:`QuerySet.get` when no row matches."""


class MultipleObjectsReturned(Exception):
    """Raised by :meth:`QuerySet.get` when more than one row matches."""


@dataclasses.dataclass(frozen=True)
class QuerySet(Generic[T]):
    """An immutable, lazily-evaluated description of a ``SELECT`` over ``model``.

    Chaining methods (:meth:`filter`, :meth:`exclude`, :meth:`order_by`,
    :meth:`limit`, :meth:`offset`, :meth:`select_related`, :meth:`load_related`)
    each return a new ``QuerySet`` and never mutate ``self``. The query is sent
    to the database only on ``await``/``async for`` or a terminal method.
    """

    model: type[T]
    where: tuple[Condition, ...] = ()
    order: tuple[OrderBy, ...] = ()
    limit_value: int | None = None
    offset_value: int | None = None
    select_related_fields: tuple[str, ...] = ()
    load_related_fields: tuple[str, ...] = ()
    only_fields: tuple[str, ...] = ()
    defer_fields: tuple[str, ...] = ()

    # -- chaining (all return a fresh QuerySet) -----------------------------

    def filter(self, **lookups: Any) -> QuerySet[T]:
        """Return a new ``QuerySet`` with extra ``field__op=value`` conditions."""
        conditions = self.model._conditions_from_kwargs(lookups)
        return dataclasses.replace(self, where=self.where + conditions)

    def exclude(self, **lookups: Any) -> QuerySet[T]:
        """Return a new ``QuerySet`` negating each given condition.

        Each kwarg is rendered as ``NOT (<condition>)`` and the negated
        conditions are AND-combined with any existing ones. Django's multi-kwarg
        OR semantics for ``exclude`` are intentionally out of scope.
        """
        conditions = tuple(
            dataclasses.replace(c, negated=True)
            for c in self.model._conditions_from_kwargs(lookups)
        )
        return dataclasses.replace(self, where=self.where + conditions)

    def order_by(self, *fields: str) -> QuerySet[T]:
        """Return a new ``QuerySet`` ordered by ``fields`` (leading ``-`` = DESC)."""
        terms = tuple(
            OrderBy(Column(f[1:] if f.startswith("-") else f), descending=f.startswith("-"))
            for f in fields
        )
        return dataclasses.replace(self, order=terms)

    def limit(self, n: int) -> QuerySet[T]:
        """Return a new ``QuerySet`` limited to ``n`` rows."""
        return dataclasses.replace(self, limit_value=n)

    def offset(self, n: int) -> QuerySet[T]:
        """Return a new ``QuerySet`` skipping the first ``n`` rows."""
        return dataclasses.replace(self, offset_value=n)

    def select_related(self, *fields: str) -> QuerySet[T]:
        """Return a new ``QuerySet`` that JOIN-loads the given FK relations."""
        return dataclasses.replace(self, select_related_fields=self.select_related_fields + fields)

    def load_related(self, *fields: str) -> QuerySet[T]:
        """Return a new ``QuerySet`` that prefetches the given relations."""
        return dataclasses.replace(self, load_related_fields=self.load_related_fields + fields)

    def only(self, *fields: str | FieldRef) -> QuerySet[T]:
        """Return a new ``QuerySet`` that SELECTs only the named fields.

        Pass :class:`~riverorm.fields.FieldRef` objects (via ``Model.f``) for
        rename-safe references, or plain strings for convenience::

            f = User.f
            await User.objects.only(f.id, f.username).all()
            await User.objects.only("id", "username").all()  # string form

        Instances from partial queries use :meth:`~pydantic.BaseModel.model_construct`
        (no validation). Un-fetched optional fields carry their Python defaults;
        un-fetched required fields will not be set on the instance.
        """
        if not fields:
            return dataclasses.replace(self, only_fields=(), defer_fields=())
        names = self._validate_field_refs(fields, "only")
        return dataclasses.replace(self, only_fields=names, defer_fields=())

    def defer(self, *fields: str | FieldRef) -> QuerySet[T]:
        """Return a new ``QuerySet`` that SELECTs all fields *except* the named ones.

        Pass :class:`~riverorm.fields.FieldRef` objects (via ``Model.f``) for
        rename-safe references, or plain strings for convenience::

            f = User.f
            await User.objects.defer(f.email).all()
            await User.objects.defer("email").all()  # string form

        Instances from partial queries use :meth:`~pydantic.BaseModel.model_construct`
        (no validation). Deferred optional fields carry their Python defaults;
        deferred required fields will not be set on the instance.
        """
        if not fields:
            return dataclasses.replace(self, defer_fields=(), only_fields=())
        names = self._validate_field_refs(fields, "defer")
        return dataclasses.replace(self, defer_fields=names, only_fields=())

    def _validate_field_refs(
        self, fields: tuple[str | FieldRef, ...], method: str
    ) -> tuple[str, ...]:
        """Coerce ``only()`` / ``defer()`` arguments to validated column names.

        Accepts strings or :class:`~riverorm.fields.FieldRef` values and raises
        ``ValueError`` if any name is not a real (non-relation) column.
        """
        names = tuple(f if isinstance(f, str) else f.name for f in fields)
        unknown = set(names) - set(self.model.model_real_fields())
        if unknown:
            raise ValueError(
                f"Unknown fields for {method}() on {self.model.__name__}: {sorted(unknown)}"
            )
        return names

    # -- terminals ----------------------------------------------------------

    async def all(self) -> list[T]:
        """Execute the query and return all matching instances."""
        return await self._execute()

    async def first(self) -> T | None:
        """Return the first matching instance, or ``None`` if there are none."""
        rows = await self.limit(1)._execute()
        return rows[0] if rows else None

    async def get(self, **lookups: Any) -> T:
        """Return exactly one instance matching ``lookups`` (plus existing filters).

        Raises :class:`DoesNotExist` if nothing matches and
        :class:`MultipleObjectsReturned` if more than one row matches.
        """
        qs = self.filter(**lookups) if lookups else self
        rows = await qs.limit(2)._execute()
        if not rows:
            raise self.model.DoesNotExist(f"{self.model.__name__} matching query does not exist")
        if len(rows) > 1:
            raise self.model.MultipleObjectsReturned(
                f"get() returned more than one {self.model.__name__}"
            )
        return rows[0]

    async def count(self) -> int:
        """Return the number of matching rows via ``SELECT COUNT(*)``."""
        db = self.model.db()
        query = SelectQuery(table=self.model.table_name(), where=self.where, count=True)
        sql, params = db.compiler.compile_select(query)
        row = await db.fetchrow(sql, *params)
        if row is None:
            return 0
        values = list(dict(row).values())
        return int(values[0])

    async def exists(self) -> bool:
        """Return ``True`` if at least one row matches."""
        return await self.limit(1).count() > 0

    async def update(self, **kwargs: Any) -> int:
        """Bulk-update all matching rows and return the number of rows affected.

        Example::

            count = await Order.objects.filter(status="pending").update(status="cancelled")
        """
        db = self.model.db()
        query = UpdateQuery(
            table=self.model.table_name(),
            columns=tuple(kwargs.keys()),
            values=tuple(kwargs.values()),
            where=self.where,
        )
        sql, params = db.compiler.compile_update(query)
        return await db.execute_returning_rowcount(sql, *params)

    async def delete(self) -> int:
        """Bulk-delete all matching rows and return the number of rows deleted.

        Example::

            count = await User.objects.filter(is_active=False).delete()
        """
        db = self.model.db()
        query = DeleteQuery(table=self.model.table_name(), where=self.where)
        sql, params = db.compiler.compile_delete(query)
        return await db.execute_returning_rowcount(sql, *params)

    # -- execution ----------------------------------------------------------

    def _build_query(self) -> SelectQuery:
        if self.only_fields:
            # Always load the primary key so partial instances stay identity-safe
            # (save()/delete() rely on it), mirroring Django's only()/defer().
            pk = self.model.primary_key()
            names = self.only_fields if pk in self.only_fields else (pk, *self.only_fields)
            columns: tuple[Column, ...] = tuple(Column(f) for f in names)
        elif self.defer_fields:
            skipped = set(self.defer_fields) - {self.model.primary_key()}
            columns = tuple(Column(f) for f in self.model.model_real_fields() if f not in skipped)
        else:
            columns = ()
        return SelectQuery(
            table=self.model.table_name(),
            columns=columns,
            where=self.where,
            order_by=self.order,
            limit=self.limit_value,
            offset=self.offset_value,
        )

    async def _execute(self) -> list[T]:
        if self.select_related_fields:
            if self.only_fields or self.defer_fields:
                raise ValueError(
                    "only() / defer() cannot be combined with select_related(); "
                    "the JOIN builds its own column list. Drop one of them."
                )
            return await self._execute_select_related()
        db = self.model.db()
        sql, params = db.compiler.compile_select(self._build_query())
        rows = await db.fetch(sql, *params)
        if self.only_fields or self.defer_fields:
            objects = [self.model._from_partial_row(dict(row)) for row in rows]
        else:
            objects = [self.model._from_row(dict(row)) for row in rows]
        if self.load_related_fields:
            await self.model._prefetch_related(objects, list(self.load_related_fields))
        return objects

    async def _execute_select_related(self) -> list[T]:
        """Run a JOIN-based select_related query, reusing the Model helper."""
        db = self.model.db()
        rel_map = self.model._build_rel_map(self.select_related_fields)
        columns, joins = self.model._select_related_columns_and_joins(rel_map)
        base = self.model.table_name()
        # Qualify accumulated WHERE columns with the base table for the JOIN.
        where = tuple(
            dataclasses.replace(c, column=dataclasses.replace(c.column, table=base))
            if c.column.table is None
            else c
            for c in self.where
        )
        query = SelectQuery(
            table=base,
            table_alias=base,
            columns=columns,
            joins=joins,
            where=where,
            order_by=self.order,
            limit=self.limit_value,
            offset=self.offset_value,
        )
        sql, params = db.compiler.compile_select(query)
        rows = await db.fetch(sql, *params)
        objects = [self.model._hydrate_select_related(row, rel_map) for row in rows]
        if self.load_related_fields:
            await self.model._prefetch_related(objects, list(self.load_related_fields))
        return objects

    # -- laziness -----------------------------------------------------------

    def __await__(self) -> Generator[Any, None, list[T]]:
        return self._execute().__await__()

    async def __aiter__(self) -> AsyncIterator[T]:
        for obj in await self._execute():
            yield obj


class Manager(Generic[T]):
    """Stateless factory of :class:`QuerySet` objects bound to ``model``.

    Reached through the :class:`ManagerDescriptor` as ``Model.objects``. Each
    call returns a fresh, empty ``QuerySet`` for the model, so managers carry no
    query state of their own.
    """

    def __init__(self, model: type[T]) -> None:
        self.model = model

    def get_queryset(self) -> QuerySet[T]:
        """Return a fresh, unfiltered ``QuerySet`` for this manager's model."""
        return QuerySet(self.model)

    def filter(self, **lookups: Any) -> QuerySet[T]:
        return self.get_queryset().filter(**lookups)

    def exclude(self, **lookups: Any) -> QuerySet[T]:
        return self.get_queryset().exclude(**lookups)

    def order_by(self, *fields: str) -> QuerySet[T]:
        return self.get_queryset().order_by(*fields)

    def limit(self, n: int) -> QuerySet[T]:
        return self.get_queryset().limit(n)

    def offset(self, n: int) -> QuerySet[T]:
        return self.get_queryset().offset(n)

    def select_related(self, *fields: str) -> QuerySet[T]:
        return self.get_queryset().select_related(*fields)

    def load_related(self, *fields: str) -> QuerySet[T]:
        return self.get_queryset().load_related(*fields)

    def only(self, *fields: str | FieldRef) -> QuerySet[T]:
        return self.get_queryset().only(*fields)

    def defer(self, *fields: str | FieldRef) -> QuerySet[T]:
        return self.get_queryset().defer(*fields)

    async def all(self) -> list[T]:
        return await self.get_queryset().all()

    async def first(self) -> T | None:
        return await self.get_queryset().first()

    async def get(self, **lookups: Any) -> T:
        return await self.get_queryset().get(**lookups)

    async def count(self) -> int:
        return await self.get_queryset().count()

    async def exists(self) -> bool:
        return await self.get_queryset().exists()

    async def create(self, **kwargs: Any) -> T:
        """Create, persist, and return a new instance.

        Equivalent to ``Model(**kwargs).save()`` but reads more naturally in a
        chain and is the preferred way to create single rows.

        Example::

            user = await User.objects.create(username="alice", email="alice@ex.com")
        """
        obj = self.model(**kwargs)
        await obj.save()
        return obj

    async def get_or_create(
        self, defaults: dict[str, Any] | None = None, **lookups: Any
    ) -> tuple[T, bool]:
        """Return ``(instance, created)``.

        Tries to fetch a row matching ``lookups``; if none exists, creates one
        with ``{**lookups, **defaults}``. The second tuple element is ``True``
        when a new row was inserted.

        Note: this is not atomic. Wrap in a transaction when strict uniqueness
        under concurrent writes is required.

        Example::

            user, created = await User.objects.get_or_create(
                username="alice",
                defaults={"email": "alice@ex.com", "is_active": True},
            )
        """
        try:
            obj = await self.get(**lookups)
            return obj, False
        except self.model.DoesNotExist:
            obj = await self.create(**(lookups | (defaults or {})))
            return obj, True

    async def update(self, **kwargs: Any) -> int:
        """Bulk-update all rows for this model and return the number affected."""
        return await self.get_queryset().update(**kwargs)

    async def delete(self) -> int:
        """Bulk-delete all rows for this model and return the number deleted."""
        return await self.get_queryset().delete()


class ManagerDescriptor:
    """Descriptor exposing a :class:`Manager` as ``Model.objects``.

    Resolving ``objects`` on a class (or subclass) yields a ``Manager`` bound to
    that exact class, so managers compose correctly with inheritance and ``T`` is
    inferred from the accessing class.
    """

    def __get__(self, instance: object, owner: type[M]) -> Manager[M]:
        return Manager(owner)
