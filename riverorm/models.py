import re
from datetime import datetime
from typing import TypeVar

from pydantic import BaseModel, ConfigDict, Field
from pydantic.fields import FieldInfo

from riverorm import constants
from riverorm.db import BaseDatabase, DatabaseRegistry
from riverorm.utils import is_int_type

T = TypeVar("T", bound="Model")


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
        def camel_to_snake(name: str) -> str:
            name = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", name)
            name = re.sub(r"([a-z])([A-Z0-9])", r"\1_\2", name)
            name = re.sub(r"(\d)([A-Z][a-z])", r"\1_\2", name)
            return name.lower()

        name: str | None = getattr(cls.Meta, "table_name", None)
        if not name:
            return camel_to_snake(cls.__name__)
        return name

    @classmethod
    def model_virtual_fields(cls) -> dict[str, FieldInfo]:
        """
        Returns a dictionary of model fields with their names as keys and Field objects as values.
        """
        return {
            name: field
            for name, field in cls.model_fields.items()
            if getattr(field.annotation, "__origin__", None) in (list, tuple)
            or (isinstance(field.annotation, type) and issubclass(field.annotation, Model))
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

    async def save(self):
        """Save the model instance to the database, with auto-increment PK support."""
        fields = list(self.__class__.model_real_fields().keys())
        pk_name = self.Meta.primary_key
        pk = getattr(self, pk_name, None)

        if pk is None:
            # INSERT: omit PK if None, let DB auto-generate
            insert_fields = [f for f in fields if not (f == pk_name and getattr(self, f) is None)]
            values = [getattr(self, f) for f in insert_fields]
            cols = ", ".join(insert_fields)
            placeholders = ", ".join(f"${i + 1}" for i in range(len(insert_fields)))
            # Use RETURNING to fetch the generated PK
            query = (
                f'INSERT INTO "{self.table_name()}" ({cols}) VALUES ({placeholders}) '
                f"RETURNING {pk_name}"
            )
            row = await self.db().fetchrow(query, *values)
            if row and pk_name in row:
                setattr(self, pk_name, row[pk_name])
        else:
            # UPDATE
            values = [getattr(self, f) for f in fields]
            cols = ", ".join(f"{f} = ${i + 1}" for i, f in enumerate(fields))
            query = f'UPDATE "{self.table_name()}" SET {cols} WHERE {pk_name} = ${len(fields) + 1}'
            values.append(pk)
            await self.db().update(query, *values)
        # TODO: Update the instance with the new values from the database
        return self

    async def delete(self):
        pk_value = getattr(self, self.Meta.primary_key)
        query = f'DELETE FROM "{self.table_name()}" WHERE {self.Meta.primary_key} = $1'
        await self.db().execute(query, pk_value)

    @classmethod
    async def all(cls: type[T], limit: int = 1000) -> list[T]:
        """Fetch all rows for this model (up to the given limit)."""
        query = f'SELECT * FROM "{cls.table_name()}" LIMIT {limit};'
        rows = await cls.db().fetch(query)
        return [cls(**dict(row)) for row in rows]

    @classmethod
    async def get(cls: type[T], **kwargs) -> T | None:
        keys = list(kwargs.keys())
        values = list(kwargs.values())
        conditions = " AND ".join(f"{k} = ${i + 1}" for i, k in enumerate(keys))
        query = f'SELECT * FROM "{cls.table_name()}" WHERE {conditions} LIMIT 1'
        row = await cls.db().fetchrow(query, *values)
        return cls(**row) if row else None

    @classmethod
    async def filter(cls: type[T], **kwargs) -> list[T]:
        """
        Filter rows using field lookups, e.g. age__gt=18, name="foo".
        Supported operators: __gt, __lt, __gte, __lte, __ne, __eq (default), __in
        """
        ops = {
            "gt": ">",
            "lt": "<",
            "gte": ">=",
            "lte": "<=",
            "ne": "!=",
            "eq": "=",
            "in": "IN",
        }
        conditions = []
        values: list = []
        param_idx = 1
        for key, value in kwargs.items():
            if "__" in key:
                field, op = key.rsplit("__", 1)
                sql_op = ops.get(op)
                if not sql_op:
                    raise ValueError(f"Unsupported filter operator: {op}")
                if op == "in":
                    assert isinstance(value, (list, tuple)), (
                        "__in operator requires a list or tuple"
                    )
                    placeholders = ", ".join(f"${param_idx + i}" for i in range(len(value)))
                    conditions.append(f"{field} IN ({placeholders})")
                    values.extend(value)
                    param_idx += len(value)
                else:
                    conditions.append(f"{field} {sql_op} ${param_idx}")
                    values.append(value)
                    param_idx += 1
            else:
                conditions.append(f"{key} = ${param_idx}")
                values.append(value)
                param_idx += 1
        where = f" WHERE {' AND '.join(conditions)}" if conditions else ""
        query = f'SELECT * FROM "{cls.table_name()}"{where}'
        rows = await cls.db().fetch(query, *values)
        return [cls(**dict(r)) for r in rows]

    @classmethod
    def select_related(cls: type[T], *related_fields) -> type[T]:
        """
        Returns a subclass of the model that fetches related objects using SQL JOIN for FK fields.
        Only supports direct foreign key relationships (e.g., user_id -> User).
        """
        base_table = cls.table_name()
        model_fields = cls.model_real_fields()
        # Build mapping: related_field -> (fk_field, related_model)
        rel_map = {}
        import sys

        mod = sys.modules[cls.__module__]
        for rel in related_fields:
            fk_field = f"{rel}_id"
            if fk_field not in model_fields:
                raise ValueError(f"No foreign key field '{fk_field}' for related field '{rel}'")
            related_model = getattr(mod, rel.capitalize(), None)
            if related_model is None:
                raise ValueError(f"Related model class for '{rel}' not found in module {mod}")
            rel_map[rel] = (fk_field, related_model)

        async def all(cls, limit: int = 1000):
            base_alias = base_table
            select_cols = [f'"{base_alias}"."{f}"' for f in model_fields.keys()]
            join_clauses = []
            for rel, (fk_field, related_model) in rel_map.items():
                rel_table = related_model.table_name()
                rel_alias = rel_table
                rel_cols = [
                    f'"{rel_alias}"."{col}" AS {rel}__{col}'
                    for col in related_model.model_real_fields().keys()
                ]
                select_cols.extend(rel_cols)
                join_clauses.append(
                    f'LEFT JOIN "{rel_table}" AS "{rel_alias}" '
                    f'ON "{base_alias}"."{fk_field}" = "{rel_alias}"."id"'
                )
            select_sql = ", ".join(select_cols)
            joins = " ".join(join_clauses)
            query = (
                f'SELECT {select_sql} FROM "{base_table}" AS "{base_alias}" {joins} LIMIT {limit};'
            )
            rows = await cls.db().fetch(query)
            return [cls._hydrate_with_related(row) for row in rows]

        async def filter(cls, **kwargs):
            base_alias = base_table
            select_cols = [f'"{base_alias}"."{f}"' for f in model_fields.keys()]
            join_clauses = []
            for rel, (fk_field, related_model) in rel_map.items():
                rel_table = related_model.table_name()
                rel_alias = rel_table
                rel_cols = [
                    f'"{rel_alias}"."{col}" AS {rel}__{col}'
                    for col in related_model.model_real_fields().keys()
                ]
                select_cols.extend(rel_cols)
                join_clauses.append(
                    f'LEFT JOIN "{rel_table}" AS "{rel_alias}" '
                    f'ON "{base_alias}"."{fk_field}" = "{rel_alias}"."id"'
                )
            select_sql = ", ".join(select_cols)
            joins = " ".join(join_clauses)
            conditions = []
            values = []
            param_idx = 1
            for key, value in kwargs.items():
                conditions.append(f'"{base_alias}"."{key}" = ${param_idx}')
                values.append(value)
                param_idx += 1
            where = f" WHERE {' AND '.join(conditions)}" if conditions else ""
            query = f'SELECT {select_sql} FROM "{base_table}" AS "{base_alias}" {joins}{where};'
            rows = await cls.db().fetch(query, *values)
            return [cls._hydrate_with_related(row) for row in rows]

        def _hydrate_with_related(cls, row):
            base_data = {}
            related_objs = {}
            for k, v in dict(row).items():
                if "__" in k:
                    rel, col = k.split("__", 1)
                    related_objs.setdefault(rel, {})[col] = v
                else:
                    base_data[k] = v
            obj = cls(**base_data)
            for rel, (fk_field, related_model) in rel_map.items():
                rel_data = related_objs.get(rel)
                if rel_data and rel_data.get("id") is not None:
                    obj.__dict__[rel] = related_model(**rel_data)
                else:
                    obj.__dict__[rel] = None
            return obj

        RelatedSelected = type(
            f"{cls.__name__}RelatedSelected",
            (cls,),
            {
                "_select_related": related_fields,
                "_rel_map": rel_map,
                "all": classmethod(all),
                "filter": classmethod(filter),
                "_hydrate_with_related": classmethod(_hydrate_with_related),
                "table_name": classmethod(lambda c: cls.table_name()),
            },
        )
        return RelatedSelected

    @classmethod
    async def create_table(cls: type[T]):
        db = cls.db()
        parts = []
        pk_name = getattr(cls.Meta, "primary_key", constants.DEFAULT_PRIMARY_KEY)
        for name, field in cls.model_real_fields().items():
            field_type = field.annotation
            if field_type is None:
                raise ValueError(f"Field '{name}' has no type annotation")

            if name == pk_name and is_int_type(field_type):
                # Delegate to db backend for auto-increment PK SQL
                parts.append(db.auto_increment_primary_key_sql(name))
            else:
                db_field_type = db.python_to_sql_type(field_type)
                parts.append(f"{name} {db_field_type}")
        sql = f'CREATE TABLE IF NOT EXISTS "{cls.table_name()}" ({", ".join(parts)});'
        return await db.execute(sql)

    @classmethod
    async def drop_table(cls: type[T]):
        sql = f'DROP TABLE IF EXISTS "{cls.table_name()}";'
        return await cls.db().execute(sql)


class TimestampedModel(Model):
    """Model with date-time field: created_at and updated_at."""

    created_at: datetime | None = Field(default=None, description="Creation timestamp")
    updated_at: datetime | None = Field(default=None, description="Last update timestamp")
