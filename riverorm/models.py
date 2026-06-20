from __future__ import annotations

import re
import sys
from collections.abc import Sequence
from datetime import datetime
from typing import Any, ClassVar, Self, TypeVar, get_args, get_origin

from pydantic import BaseModel, ConfigDict, PrivateAttr
from pydantic.fields import FieldInfo

from riverorm import constants
from riverorm.fields import Field, FieldMeta, field_meta
from riverorm.db import BaseDatabase, DatabaseRegistry
from riverorm.queryset import (
    DoesNotExist,
    ManagerDescriptor,
    MultipleObjectsReturned,
    QuerySet,
)
from riverorm.sql import (
    Column,
    Condition,
    DeleteQuery,
    InsertQuery,
    Join,
    Operator,
    UpdateQuery,
)
from riverorm.utils import is_int_type, is_nullable, unwrap_type

T = TypeVar("T", bound="Model")


class PrimaryKeyError(ValueError):
    """Raised when the primary key of a persisted instance is mutated."""


def _camel_to_snake(name: str) -> str:
    """Convert a CamelCase class name to snake_case (e.g. OrderItem -> order_item)."""
    name = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", name)
    name = re.sub(r"([a-z])([A-Z0-9])", r"\1_\2", name)
    name = re.sub(r"(\d)([A-Z][a-z])", r"\1_\2", name)
    return name.lower()


def _related_model_from_annotation(annotation: Any) -> tuple[type[Model] | None, bool]:
    """
    Inspect a field annotation and return ``(related_model, is_collection)``.

    Handles ``Model``, ``Model | None``, ``Optional[Model]`` and ``list[Model]`` /
    ``set[Model]`` / ``tuple[Model, ...]``. Returns ``(None, False)`` for scalar fields.
    """
    origin = get_origin(annotation)
    if origin in (list, set, tuple):
        args = get_args(annotation)
        inner = _single_model(args[0]) if args else None
        return (inner, True)
    return (_single_model(annotation), False)


def _single_model(annotation: Any) -> type[Model] | None:
    """Return the ``Model`` subclass referenced by an annotation, unwrapping ``| None``."""
    if isinstance(annotation, type) and issubclass(annotation, Model):
        return annotation
    for arg in get_args(annotation):
        if isinstance(arg, type) and issubclass(arg, Model):
            return arg
    return None


def _ensure_model_complete(model: type[Model]) -> None:
    """Resolve any deferred Pydantic forward references on *model*.

    With ``from __future__ import annotations`` every annotation is stored as a
    string.  Pydantic defers the evaluation if a referenced class isn't yet
    defined when the model class body runs (e.g. ``User`` references ``Order``
    before ``Order`` is declared).  By the time *any* ORM method is called the
    defining module is already fully loaded, so ``sys.modules`` contains all the
    classes and Pydantic can resolve everything without manual ``model_rebuild()``
    calls from user code.
    """
    if getattr(model, "__pydantic_complete__", True):
        return
    module = sys.modules.get(model.__module__)
    ns = vars(module) if module is not None else None
    model.model_rebuild(raise_errors=True, _types_namespace=ns)


class Model(BaseModel):
    """
    Base model class for River ORM.

    This class can be extended to create specific models.

    TODO: Add more features:
    - Relationship fields (ForeignKey)
    - add support for transactions
    - select_related()
    - prefetch_related()
    - bulk_create()
    - bulk_update()
    - bulk_delete()
    - add methods for creating, updating, and deleting related models
    - add support for custom SQL queries
    - add support for migrations
    - add support for custom field types
    - add support for custom validation
    - add support for custom serialization and deserialization
    - add support for custom indexing
    - add support for custom constraints
    - add support for custom triggers
    - add support for custom views
    - add support for custom stored procedures
    - add support for custom functions
    """

    model_config = ConfigDict(
        populate_by_name=True,
        from_attributes=True,
        validate_by_name=True,
        use_enum_values=True,
        arbitrary_types_allowed=True,
    )

    id: int | None = Field(default=None, description="Primary key ID")

    #: Whether this instance is known to correspond to a stored DB row. Drives
    #: the INSERT-vs-UPDATE decision in :meth:`save` for non-auto-increment PKs.
    _persisted: bool = PrivateAttr(default=False)

    #: Entry point to the chainable query API: ``User.objects.filter(...)``.
    objects: ClassVar[ManagerDescriptor] = ManagerDescriptor()

    #: Raised by ``get()`` when no row matches / more than one row matches.
    DoesNotExist: ClassVar[type[Exception]] = DoesNotExist
    MultipleObjectsReturned: ClassVar[type[Exception]] = MultipleObjectsReturned

    class Meta:
        table_name: str
        primary_key: str = constants.DEFAULT_PRIMARY_KEY
        db_alias: str | None = None  # If None, use default connection

    @classmethod
    def db(cls) -> BaseDatabase:
        """Get the database instance associated with this model."""
        alias = getattr(cls.Meta, "db_alias", None)
        return DatabaseRegistry.get(alias)

    @classmethod
    def table_name(cls) -> str:
        name: str | None = getattr(cls.Meta, "table_name", None)
        if not name:
            return _camel_to_snake(cls.__name__)
        return name

    @classmethod
    def _from_row(cls: type[T], data: dict[str, Any]) -> T:
        """Build an instance from a fetched DB row and mark it as persisted."""
        obj = cls(**data)
        obj._persisted = True
        return obj

    @classmethod
    def _field_meta(cls, name: str) -> FieldMeta:
        """Return the :class:`FieldMeta` for the field ``name`` (default if absent)."""
        field = cls.model_fields.get(name)
        if field is None:
            return FieldMeta()
        return field_meta(field)

    @classmethod
    def primary_key(cls) -> str:
        """Resolve the primary key column name for this model.

        Prefers a field explicitly flagged ``Field(primary_key=True)``; otherwise
        falls back to ``Meta.primary_key`` (default ``"id"``).
        """
        for name, field in cls.model_fields.items():
            if field_meta(field).primary_key:
                return name
        return getattr(cls.Meta, "primary_key", constants.DEFAULT_PRIMARY_KEY)

    def __setattr__(self, name: str, value: Any) -> None:
        """Guard the primary key from being changed on a persisted instance.

        Allows the ``None -> generated value`` transition performed by
        :meth:`save` and re-assigning the same value, but rejects changing a
        non-``None`` primary key to a different value.
        """
        if name == self.__class__.primary_key():
            current = self.__dict__.get(name)
            if current is not None and value != current:
                raise PrimaryKeyError(
                    f"Cannot change primary key '{name}' of a persisted "
                    f"{self.__class__.__name__} from {current!r} to {value!r}."
                )
        super().__setattr__(name, value)

    @classmethod
    def model_virtual_fields(cls) -> dict[str, FieldInfo]:
        """
        Returns the relation fields (foreign keys and reverse/collection relations).

        A field is "virtual" when its annotation references another ``Model`` directly
        (``user: User`` / ``user: User | None``) or as a collection (``orders: list[Order]``).
        These are populated by ``select_related`` / ``load_related`` and are never stored
        as columns.
        """
        _ensure_model_complete(cls)
        return {
            name: field
            for name, field in cls.model_fields.items()
            if _related_model_from_annotation(field.annotation)[0] is not None
        }

    @classmethod
    def model_real_fields(cls) -> dict[str, FieldInfo]:
        """
        Returns a dictionary of model fields with their names as keys and Field objects as values,
        excluding virtual fields.
        """
        virtual_fields = set(cls.model_virtual_fields().keys())
        return {
            name: field for name, field in cls.model_fields.items() if name not in virtual_fields
        }

    @classmethod
    def _conditions_from_kwargs(cls, kwargs: dict[str, Any]) -> tuple[Condition, ...]:
        """Translate Django-style ``field__op=value`` kwargs into ``Condition``s."""
        ops = {
            "gt": Operator.GT,
            "lt": Operator.LT,
            "gte": Operator.GTE,
            "lte": Operator.LTE,
            "ne": Operator.NE,
            "eq": Operator.EQ,
            "in": Operator.IN,
        }
        conditions: list[Condition] = []
        for key, value in kwargs.items():
            if "__" in key:
                field, op = key.rsplit("__", 1)
                operator = ops.get(op)
                if operator is None:
                    raise ValueError(f"Unsupported filter operator: {op}")
                if operator is Operator.IN:
                    assert isinstance(value, (list, tuple)), (
                        "__in operator requires a list or tuple"
                    )
            else:
                field, operator = key, Operator.EQ
            conditions.append(Condition(Column(field), operator, value))
        return tuple(conditions)

    async def save(self) -> Self:
        """Persist this instance (INSERT if new, UPDATE if already saved)."""
        db = self.db()
        compiler = db.compiler
        fields = list(self.__class__.model_real_fields().keys())
        pk_name = self.primary_key()
        pk = getattr(self, pk_name, None)

        if not self._persisted:
            # INSERT: omit PK if None, let DB auto-generate it.
            insert_fields = [f for f in fields if not (f == pk_name and getattr(self, f) is None)]
            values = tuple(getattr(self, f) for f in insert_fields)
            if db.dialect.supports_returning:
                query = InsertQuery(
                    table=self.table_name(),
                    columns=tuple(insert_fields),
                    values=values,
                    returning=pk_name,
                )
                sql, params = compiler.compile_insert(query)
                row = await db.fetchrow(sql, *params)
                # Only adopt the DB-generated PK for auto-increment keys (the
                # local value was None). A caller-supplied PK keeps its value.
                if row and pk_name in row and getattr(self, pk_name, None) is None:
                    setattr(self, pk_name, row[pk_name])
            else:
                # No RETURNING (e.g. MySQL): read the generated PK from the driver
                # (cursor.lastrowid). Assumes a single int auto-increment PK.
                query = InsertQuery(
                    table=self.table_name(),
                    columns=tuple(insert_fields),
                    values=values,
                    returning=None,
                )
                sql, params = compiler.compile_insert(query)
                new_pk = await db.execute_insert(sql, *params)
                # ``lastrowid`` is only meaningful for an auto-increment PK that
                # was generated by the DB (the local value was None).
                if new_pk is not None and getattr(self, pk_name, None) is None:
                    setattr(self, pk_name, new_pk)
        else:
            # UPDATE
            values = tuple(getattr(self, f) for f in fields)
            update = UpdateQuery(
                table=self.table_name(),
                columns=tuple(fields),
                values=values,
                where=(Condition(Column(pk_name), Operator.EQ, pk),),
            )
            sql, params = compiler.compile_update(update)
            await db.update(sql, *params)
        self._persisted = True
        return self

    async def delete(self) -> None:
        pk_name = self.primary_key()
        pk_value = getattr(self, pk_name)
        db = self.db()
        delete = DeleteQuery(
            table=self.table_name(),
            where=(Condition(Column(pk_name), Operator.EQ, pk_value),),
        )
        sql, params = db.compiler.compile_delete(delete)
        await db.execute(sql, *params)

    @classmethod
    async def create(cls: type[T], **kwargs: Any) -> T:
        """Create, persist, and return a new instance.

        Convenience shorthand for ``Model(**kwargs).save()``.  Prefer
        ``Model.objects.create(...)`` in new code; this classmethod exists for
        ergonomic one-liners.
        """
        return await cls.objects.create(**kwargs)

    @classmethod
    async def all(cls: type[T], limit: int = 1000) -> list[T]:
        """Fetch all rows for this model (up to the given limit).

        Back-compat wrapper delegating to the :class:`QuerySet` API.
        """
        return await cls.objects.limit(limit).all()

    @classmethod
    async def get(cls: type[T], **kwargs: Any) -> T | None:
        """Return the first row matching ``kwargs`` (or ``None``).

        Back-compat wrapper preserving the historical "one-or-None" behaviour;
        use ``Model.objects.get(...)`` for strict ``DoesNotExist`` semantics.
        """
        return await cls.objects.filter(**kwargs).first()

    @classmethod
    async def filter(cls: type[T], **kwargs: Any) -> list[T]:
        """
        Filter rows using field lookups, e.g. age__gt=18, name="foo".
        Supported operators: __gt, __lt, __gte, __lte, __ne, __eq (default), __in

        Back-compat wrapper delegating to the :class:`QuerySet` API.
        """
        return await cls.objects.filter(**kwargs).all()

    @classmethod
    def _build_rel_map(cls, related_fields: Sequence[str]) -> dict[str, tuple[str, type[Model]]]:
        """Map each ``select_related`` field to its ``(fk_field, related_model)``.

        Only direct forward foreign keys are supported (e.g. ``user`` via
        ``user_id``). The related model is resolved from the field annotation,
        falling back to a class named like the field in the model's module.
        """
        import sys

        model_fields = cls.model_real_fields()
        mod = sys.modules[cls.__module__]
        rel_map: dict[str, tuple[str, type[Model]]] = {}
        for rel in related_fields:
            fk_field = f"{rel}_id"
            if fk_field not in model_fields:
                raise ValueError(f"No foreign key field '{fk_field}' for related field '{rel}'")
            related_model: type[Model] | None = None
            if rel in cls.model_fields:
                related_model = _related_model_from_annotation(cls.model_fields[rel].annotation)[0]
            if related_model is None:
                related_model = getattr(mod, rel.capitalize(), None)  # type: ignore[assignment]
            if related_model is None:
                raise ValueError(f"Related model class for '{rel}' not found in module {mod}")
            rel_map[rel] = (fk_field, related_model)
        return rel_map

    @classmethod
    def _select_related_columns_and_joins(
        cls, rel_map: dict[str, tuple[str, type[Model]]]
    ) -> tuple[tuple[Column, ...], tuple[Join, ...]]:
        """Build the projected columns and LEFT JOINs for a ``select_related`` query."""
        base_alias = cls.table_name()
        columns: list[Column] = [Column(name=f, table=base_alias) for f in cls.model_real_fields()]
        joins: list[Join] = []
        for rel, (fk_field, related_model) in rel_map.items():
            rel_alias = related_model.table_name()
            columns.extend(
                Column(name=col, table=rel_alias, output_name=f"{rel}__{col}")
                for col in related_model.model_real_fields()
            )
            joins.append(
                Join(
                    table=related_model.table_name(),
                    alias=rel_alias,
                    left_table=base_alias,
                    left_column=fk_field,
                    right_column=related_model.primary_key(),
                )
            )
        return tuple(columns), tuple(joins)

    @classmethod
    def _hydrate_select_related(
        cls: type[T], row: Any, rel_map: dict[str, tuple[str, type[Model]]]
    ) -> T:
        """Build an instance from a joined row, attaching the related objects."""
        base_data: dict[str, Any] = {}
        related_objs: dict[str, dict[str, Any]] = {}
        for k, v in dict(row).items():
            if "__" in k:
                rel, col = k.split("__", 1)
                related_objs.setdefault(rel, {})[col] = v
            else:
                base_data[k] = v
        obj = cls._from_row(base_data)
        for rel, (_fk_field, related_model) in rel_map.items():
            rel_data = related_objs.get(rel)
            rel_pk = related_model.primary_key()
            if rel_data and rel_data.get(rel_pk) is not None:
                obj.__dict__[rel] = related_model._from_row(rel_data)
            else:
                obj.__dict__[rel] = None
        return obj

    @classmethod
    def select_related(cls: type[T], *related_fields: str) -> QuerySet[T]:
        """Return a :class:`QuerySet` that JOIN-loads the given FK relations.

        Only direct foreign key relationships are supported (e.g. ``user_id ->
        User``). Composes with ``filter``/``order_by``/``limit``.
        """
        return cls.objects.select_related(*related_fields)

    @classmethod
    def load_related(cls: type[T], *related_fields: str) -> QuerySet[T]:
        """Return a :class:`QuerySet` that prefetches the given relations.

        Unlike :meth:`select_related` (a SQL JOIN), this issues one extra batched
        query per relation and stitches the results in Python. It handles forward
        foreign keys (``order.user`` via ``user_id``) and reverse relations
        (``user.orders``), and supports nesting with ``__`` (e.g.
        ``"product__user"``).

        Example::

            users = await User.load_related("orders", "products").all()
            orders = await Order.load_related("user", "product__user").filter(status="paid")
        """
        return cls.objects.load_related(*related_fields)

    @classmethod
    async def _prefetch_related(cls, objects: Sequence[Model], specs: list[str]) -> None:
        """Populate the relations named in ``specs`` on ``objects`` with batched queries."""
        if not objects or not specs:
            return
        _ensure_model_complete(cls)

        # Group ``"product__user"`` style specs by their root relation.
        groups: dict[str, list[str]] = {}
        for spec in specs:
            root, _, rest = spec.partition("__")
            groups.setdefault(root, [])
            if rest:
                groups[root].append(rest)

        for root, nested in groups.items():
            related_model, is_collection = _related_model_from_annotation(
                cls.model_fields[root].annotation if root in cls.model_fields else None
            )
            if related_model is None:
                raise ValueError(f"'{root}' is not a relation on {cls.__name__}")

            if is_collection:
                children = await cls._prefetch_reverse(objects, root, related_model)
            else:
                children = await cls._prefetch_forward(objects, root, related_model)

            if nested:
                await related_model._prefetch_related(children, nested)

    @classmethod
    async def _prefetch_forward(
        cls, objects: Sequence[Model], root: str, related_model: type[Model]
    ) -> list[Model]:
        """Load a forward FK relation (``cls`` has ``<root>_id``) and attach single objects."""
        fk = f"{root}_id"
        ids = {getattr(obj, fk) for obj in objects if getattr(obj, fk, None) is not None}
        related = await related_model.filter(id__in=list(ids)) if ids else []
        by_pk = {getattr(r, related_model.primary_key()): r for r in related}
        for obj in objects:
            obj.__dict__[root] = by_pk.get(getattr(obj, fk, None))
        return [obj.__dict__[root] for obj in objects if obj.__dict__.get(root) is not None]

    @classmethod
    async def _prefetch_reverse(
        cls, objects: Sequence[Model], root: str, related_model: type[Model]
    ) -> list[Model]:
        """Load a reverse relation (related rows point back via ``<cls>_id``) as lists."""
        back_fk = f"{_camel_to_snake(cls.__name__)}_id"
        pk = cls.primary_key()
        ids = [getattr(obj, pk) for obj in objects if getattr(obj, pk, None) is not None]
        related = await related_model.filter(**{f"{back_fk}__in": ids}) if ids else []
        grouped: dict[Any, list[Model]] = {}
        for row in related:
            grouped.setdefault(getattr(row, back_fk), []).append(row)
        for obj in objects:
            obj.__dict__[root] = grouped.get(getattr(obj, pk, None), [])
        return related

    def to_dict(
        self,
        *,
        exclude_none: bool = False,
        exclude_virtual: bool = True,
    ) -> dict[str, Any]:
        """Serialize to a plain Python dict, excluding virtual/relation fields by default."""
        exclude: set[str] | None = (
            set(self.__class__.model_virtual_fields()) if exclude_virtual else None
        )
        return self.model_dump(exclude=exclude, exclude_none=exclude_none)

    def to_json(
        self,
        *,
        exclude_none: bool = False,
        exclude_virtual: bool = True,
    ) -> str:
        """Serialize to a JSON string, excluding virtual/relation fields by default."""
        exclude: set[str] | None = (
            set(self.__class__.model_virtual_fields()) if exclude_virtual else None
        )
        return self.model_dump_json(exclude=exclude, exclude_none=exclude_none)

    @classmethod
    async def create_table(cls: type[T]):
        # Ensure forward references are resolved before inspecting model fields.
        # A model may be incomplete when create_table() is called (before the first
        # instance is constructed), because forward-referenced sibling classes were
        # not yet defined when the model class body executed.
        if not getattr(cls, "__pydantic_complete__", True):
            import sys

            mod = sys.modules.get(cls.__module__)
            cls.model_rebuild(raise_errors=False, _types_namespace=vars(mod) if mod else None)
        db = cls.db()
        dialect = db.dialect
        parts = []
        pk_name = cls.primary_key()
        # MySQL cannot index/key a TEXT column without a length, so a string PK
        # must be a bounded VARCHAR. Default the bound when none was declared.
        default_pk_str_length = 255
        for name, field in cls.model_real_fields().items():
            field_type = field.annotation
            if field_type is None:
                raise ValueError(f"Field '{name}' has no type annotation")

            meta = field_meta(field)
            is_pk = name == pk_name

            if is_pk and is_int_type(field_type):
                parts.append(dialect.auto_increment_pk(name))
                continue

            # Unwrap Optional/Union to get the base type for DDL decisions.
            base_type = unwrap_type(field_type)
            if base_type is str:
                length = meta.max_length or (default_pk_str_length if is_pk else None)
                db_field_type = (
                    dialect.varchar(length) if length else dialect.python_to_sql_type(field_type)
                )
            else:
                db_field_type = dialect.python_to_sql_type(field_type)

            column = f"{dialect.quote(name)} {db_field_type}"
            if is_pk:
                column += " PRIMARY KEY"
            elif not is_nullable(field_type):
                column += " NOT NULL"
            parts.append(column)
        sql = f"CREATE TABLE IF NOT EXISTS {dialect.quote(cls.table_name())} ({', '.join(parts)});"
        return await db.execute(sql)

    @classmethod
    async def drop_table(cls: type[T]):
        dialect = cls.db().dialect
        sql = f"DROP TABLE IF EXISTS {dialect.quote(cls.table_name())};"
        return await cls.db().execute(sql)


class TimestampedModel(Model):
    """Model with date-time field: created_at and updated_at."""

    created_at: datetime | None = Field(default=None, description="Creation timestamp")
    updated_at: datetime | None = Field(default=None, description="Last update timestamp")
