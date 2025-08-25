import re
from typing import TypeVar

from pydantic import BaseModel, ConfigDict, Field
from pydantic.fields import FieldInfo

from riverorm.db import db
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
        primary_key: str = "id"

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
            row = await db.fetchrow(query, *values)
            if row and pk_name in row:
                setattr(self, pk_name, row[pk_name])
        else:
            # UPDATE
            values = [getattr(self, f) for f in fields]
            cols = ", ".join(f"{f} = ${i + 1}" for i, f in enumerate(fields))
            query = f'UPDATE "{self.table_name()}" SET {cols} WHERE {pk_name} = ${len(fields) + 1}'
            values.append(pk)
            await db.update(query, *values)

        # TODO: Update the instance with the new values from the database
        # self.__dict__.update(**row)
        return self

    async def delete(self):
        pk_value = getattr(self, self.Meta.primary_key)
        query = f'DELETE FROM "{self.table_name()}" WHERE {self.Meta.primary_key} = $1'
        await db.execute(query, pk_value)

    @classmethod
    async def all(cls: type[T], limit: int = 1000) -> list[T]:
        query = f'SELECT * FROM "{cls.table_name()}" LIMIT {limit};'
        rows = await db.fetch(query)
        return [cls(**dict(row)) for row in rows]

    @classmethod
    async def get(cls: type[T], **kwargs) -> T | None:
        keys = list(kwargs.keys())
        values = list(kwargs.values())
        conditions = " AND ".join(f"{k} = ${i + 1}" for i, k in enumerate(keys))
        query = f'SELECT * FROM "{cls.table_name()}" WHERE {conditions} LIMIT 1'
        row = await db.fetchrow(query, *values)
        return cls(**row) if row else None

    @classmethod
    async def filter(cls: type[T], **kwargs) -> list[T]:
        keys = list(kwargs.keys())
        values = list(kwargs.values())
        conditions = " AND ".join(f"{k} = ${i + 1}" for i, k in enumerate(keys))
        query = f'SELECT * FROM "{cls.table_name()}" WHERE {conditions}'
        rows = await db.fetch(query, *values)
        return [cls(**dict(r)) for r in rows]

    @classmethod
    async def create_table(cls: type[T]):
        parts = []
        pk_name = getattr(cls.Meta, "primary_key", "id")
        for name, field in cls.model_real_fields().items():
            field_type = field.annotation
            if field_type is None:
                raise ValueError(f"Field '{name}' has no type annotation")

            if name == pk_name and is_int_type(field_type):
                parts.append(f"{name} SERIAL PRIMARY KEY")
            else:
                db_field_type = db.python_to_sql_type(field_type)
                parts.append(f"{name} {db_field_type}")
        sql = f'CREATE TABLE IF NOT EXISTS "{cls.table_name()}" ({", ".join(parts)});'
        return await db.execute(sql)

    @classmethod
    async def drop_table(cls: type[T]):
        sql = f'DROP TABLE IF EXISTS "{cls.table_name()}";'
        return await db.execute(sql)
