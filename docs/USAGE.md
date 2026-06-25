# RiverORM Usage Guide

RiverORM is a minimalistic, async-first ORM for Python, designed for simplicity and modern development.

## Installation

See the [Installation Guide](./INSTALL.md) for details on installing RiverORM and database backends.

---

## Database Connections and Model Mapping

RiverORM uses a central `DatabaseRegistry` to manage all database connections. You can register multiple connections (e.g., for different databases or environments) and assign them to models as needed.

### Registering Connections

At application startup, register your DB connections:

```python
from riverorm.db import DatabaseRegistry, MySQLDatabase, PostgresDatabase

# Register connections
DatabaseRegistry.register("db1", PostgresDatabase("postgresql://user:pass@localhost/db1", debug=True))
DatabaseRegistry.register("db2", MySQLDatabase("mysql://user:pass@localhost/db2", debug=True))

# The first registered connection becomes the default. You can change the default:
DatabaseRegistry.set_default("db2")
```

### Assigning Connections to Models

By default, all models use the default connection. To assign a specific connection to a model, set `db_alias` in the model's `Meta` class:

```python
from riverorm import Field, Model

class User(Model):
    id: int | None = Field(default=None)
    username: str

    class Meta:
        db_alias = "db1"  # Use the Postgres connection

class Product(Model):
    id: int | None = Field(default=None)
    name: str
    price: float
    in_stock: bool = Field(True)

    class Meta:
        db_alias = "db2"  # Use the MySQL connection
```

If `db_alias` is not set, the model uses the default connection.

### Error Handling

If no connections are registered, or a model's `db_alias` is not found, any DB operation will raise a clear exception.

---

## Defining Models

Models in RiverORM inherit from `Model` and use type annotations with `Field` for schema definition. Fields are real Pydantic fields, so you get validation and metadata for free.

Two equivalent syntaxes are supported — choose whichever fits your style:

```python
from riverorm import Field, Model

# Classic assignment style
class Product(Model):
    id: int | None = Field(default=None)  # `id` is the primary key by default
    name: str = Field(max_length=200)
    price: float
    in_stock: bool = Field(True)

# Annotated style (PEP 593) — keeps type and metadata visually separate
from typing import Annotated

class Product(Model):
    id: int | None = Field(default=None)
    name: Annotated[str, Field(max_length=200)]
    price: Annotated[float, Field()]
    in_stock: Annotated[bool, Field(True)]
```

Both styles are fully equivalent: they produce the same Pydantic model, the same
DDL, and the same query behaviour. Use `Annotated` when you want to keep the type
signature clean and the ORM metadata as a secondary annotation.

### Nullability

Annotate a field as `T | None` (or `Optional[T]`) when the column should be
nullable in the database. Non-optional fields emit `NOT NULL` in the generated
`CREATE TABLE` SQL:

```python
class User(Model):
    id: int | None = Field(default=None)   # nullable (auto-increment PK)
    username: str                           # NOT NULL
    email: str | None = Field(default=None) # nullable column
```

The primary key is the `id` field by default. To use a different primary key,
mark a field with `Field(primary_key=True)`:

```python
class Product(Model):
    sku: str = Field(primary_key=True)
    name: str
```

(Setting `Meta.primary_key = "sku"` also works.) Once a row is persisted, its
primary key is **protected** — reassigning it on a saved instance raises
`PrimaryKeyError`.

### Field options

`Field()` is RiverORM's thin wrapper around Pydantic's `Field`. It accepts all
the usual Pydantic arguments plus schema metadata used for DDL and querying:

| Option | Meaning |
| --- | --- |
| `primary_key=True` | Use this column as the primary key. |
| `index=True` | Create an index for this column. |
| `unique=True` | Add a unique constraint. |
| `db_column="..."` | Override the database column name. |
| `max_length=N` | Maximum length (also enforced by Pydantic validation). |

```python
class User(Model):
    id: int | None = Field(default=None)
    username: str = Field(unique=True, max_length=50)
    email: str | None = Field(default=None, index=True)
```

> **Note:** the deprecated `Field(pk=True)` still works but emits a
> `DeprecationWarning` — prefer `Field(primary_key=True)`.

---

## Relationships

Relationships are declared with a **foreign-key column** plus an annotated
**relation field** that RiverORM populates for you. A forward relation needs a
`<name>_id` column and a field typed as the related model; a reverse relation is
a field typed as a `list[...]` of the related model.

```python
from __future__ import annotations

from riverorm import Field, Model

class User(Model):
    id: int | None = Field(default=None)
    username: str
    # Reverse relation — populated by load_related("orders")
    orders: list[Order] = Field(default_factory=list)

class Order(Model):
    id: int | None = Field(default=None)
    quantity: int
    user_id: int | None = Field(default=None)     # foreign key column
    product_id: int | None = Field(default=None)  # foreign key column
    # Forward relations — populated by select_related(...) / load_related(...)
    user: User | None = Field(default=None)
    product: Product | None = Field(default=None)
```

Relation fields (`user`, `product`, `orders`) are *virtual*: they are never
stored as columns. Only scalar columns — including the `_id` foreign keys —
are created in the database.

### Eager loading (no manual SQL)

Choose how related data is fetched:

```python
# select_related: a single SQL JOIN, best for forward (to-one) relations
orders = await Order.objects.select_related("user", "product").all()
print(orders[0].user.username)

# load_related: one batched query per relation (avoids N+1); works for
# forward, reverse, and nested ("__") relations
users = await User.objects.load_related("orders").all()
paid = await Order.objects.load_related("product__user").filter(status="paid")
```

Eager loading composes with the rest of the query API (filtering, ordering,
limits) described under [Querying](#querying) below.

---

## Creating and Using Model Instances

Model instances are created like Pydantic models. Leave the primary key unset
to let the database auto-generate it on `save()`:

```python
user = User(username="alice")
await user.save()  # user.id is populated after insert

product = Product(name="Laptop", price=999.99)
await product.save()

order = Order(quantity=1, user_id=user.id, product_id=product.id)
await order.save()
```

### Serialization

Every model instance exposes convenience methods for converting to plain Python
dicts or JSON strings. By default, virtual (relation) fields are excluded so the
output only contains database columns:

```python
user = await User.objects.get(id=1)

# Serialize to dict (relation fields excluded)
d = user.to_dict()
# {'id': 1, 'username': 'alice', 'email': 'alice@ex.com', 'is_active': True}

# Exclude None values too
d = user.to_dict(exclude_none=True)

# Serialize to JSON
json_str = user.to_json()

# Include relation fields if they were eagerly loaded
user_with_orders = await User.objects.load_related("orders").get(id=1)
d = user_with_orders.to_dict(exclude_virtual=False)
```

Pydantic's own `model_dump()` / `model_dump_json()` work too, with the full
field set (including virtual fields and private attrs excluded by Pydantic).

---

## Querying

Every model exposes a chainable, lazy query API through `Model.objects`. Each
method returns a **new** `QuerySet`, and **nothing touches the database until you
`await`** it (or call a terminal such as `get()` / `count()`):

```python
# Build and execute a query
users = await User.objects.filter(is_active=True).order_by("-id").limit(10)

# QuerySets are lazy and reusable — chaining never mutates the original
active = User.objects.filter(is_active=True)
recent = await active.order_by("-id").limit(5)   # `active` is unchanged

# Eager loading composes with filtering / ordering / limits
orders = await Order.objects.select_related("user").filter(status="paid").order_by("-id")
```

### Chaining methods

| Method | Effect |
| --- | --- |
| `filter(**lookups)` | Add `AND` conditions (see lookups below). |
| `exclude(**lookups)` | Add negated (`NOT`) conditions. |
| `order_by("-id", "name")` | Order rows (leading `-` = descending). |
| `limit(n)` / `offset(n)` | Slice the result set. |
| `select_related(*fields)` | Eager-load forward relations via a `JOIN`. |
| `load_related(*fields)` | Batched eager loading (forward / reverse / nested). |
| `only(*fields)` | SELECT only the named columns (partial load). |
| `defer(*fields)` | SELECT all columns *except* the named ones (partial load). |

### Terminal methods (await these)

| Method | Returns |
| --- | --- |
| `await qs` / `qs.all()` | `list[Model]` of all matches. |
| `first()` | The first match, or `None`. |
| `get(**lookups)` | Exactly one match; raises `DoesNotExist` or `MultipleObjectsReturned`. |
| `count()` | Number of matching rows (`int`). |
| `exists()` | `True` if any row matches. |
| `update(**fields)` | Bulk-update all matching rows; returns affected row count. |
| `delete()` | Bulk-delete all matching rows; returns deleted row count. |

```python
product = await Product.objects.get(id=1)
n = await Product.objects.filter(in_stock=True).count()
if await User.objects.filter(username="alice").exists():
    ...
```

### Field-subset loading (`only` / `defer`)

`only()` fetches only the named columns; `defer()` fetches everything *except*
the named columns.  Use `Model.f.field_name` for typed, rename-safe field
references — typos raise `AttributeError` at the call site rather than
producing a SQL error.  Plain strings are accepted too.

```python
f = User.f  # typed field-reference namespace

# Include only these columns
users = await User.objects.only(f.id, f.username).filter(is_active=True).all()

# Exclude columns (fetch everything else)
products = await Product.objects.defer(f.description).order_by("name").all()

# Plain strings are accepted too (backward-compatible)
users = await User.objects.only("id", "username").all()

# Shorthand via the model class
users = await User.only(f.id, f.username).all()
users = await User.defer(f.email).all()
```

Instances returned from partial queries are created with Pydantic's
`model_construct` (no validation). Columns that were not fetched carry their
Python-level defaults (`None`, `True`, `[]`, etc.), **not** the actual DB values.
The primary key is always loaded (even if you omit it from `only()` or name it
in `defer()`), so partial instances stay identity-safe.

Calling `.save()` on a partial instance is safe: the UPDATE is confined to the
columns that were actually fetched, so un-fetched columns keep their stored DB
values instead of being overwritten with defaults. Pass `update_fields` to
write a specific subset explicitly (works on any instance, partial or not):

```python
user = await User.objects.only(f.id, f.username).get(id=1)
user.username = "renamed"
await user.save()                         # UPDATE users SET username=… WHERE id=1
await user.save(update_fields=["username"])  # same, explicit
```

Both `only()` and `defer()` raise `ValueError` immediately if you name a field
that does not exist as a real (non-relation) column on the model.

All database operations are async. To create, update, or delete a single row,
use the instance methods or the `objects` API:

```python
# Insert via objects.create() — creates, saves, and returns in one call
product = await Product.objects.create(name="Laptop", price=999.99)

# Equivalent longhand: instantiate then save (primary key is filled in after)
product = Product(name="Laptop", price=999.99)
await product.save()

# Update a single row: change attributes and save again (existing PK → UPDATE)
product.name = "Apple MacBook"
await product.save()

# Delete a single row
await product.delete()
```

### Bulk write operations

`QuerySet` also exposes write terminals that operate on all matching rows at once:

```python
# Bulk update — returns number of rows changed
count = await Order.objects.filter(status="pending").update(status="cancelled")

# Bulk delete — returns number of rows removed
count = await User.objects.filter(is_active=False).delete()

# Get an existing row or create it if missing — returns (instance, created: bool)
user, created = await User.objects.get_or_create(
    username="alice",
    defaults={"email": "alice@ex.com", "is_active": True},
)
```

> **Note:** `get_or_create` is not atomic by default. For concurrent writes,
> wrap it in a transaction (see the planned transaction support).

### Filter lookups

`filter()`, `exclude()`, and `get()` accept Django-style field lookups via a
`field__operator` suffix:

| Lookup        | SQL        | Example                         |
| ------------- | ---------- | ------------------------------- |
| `field`       | `=`        | `filter(in_stock=True)`         |
| `field__eq`   | `=`        | `filter(status__eq="paid")`     |
| `field__ne`   | `!=`       | `filter(status__ne="draft")`    |
| `field__gt`   | `>`        | `filter(price__gt=100)`         |
| `field__gte`  | `>=`       | `filter(price__gte=100)`        |
| `field__lt`   | `<`        | `filter(price__lt=1000)`        |
| `field__lte`  | `<=`       | `filter(price__lte=1000)`       |
| `field__in`   | `IN (...)` | `filter(id__in=[1, 2, 3])`      |

Multiple lookups are combined with `AND`.

> **Shortcut classmethods:** `Model.all()`, `Model.get()`, `Model.filter()`,
> `Model.select_related()`, and `Model.load_related()` remain as thin wrappers
> around `Model.objects` for quick one-off queries.

---

## Databases

RiverORM speaks both **PostgreSQL** (via `asyncpg`) and **MySQL** (via `aiomysql`)
from the same model code — backend differences (placeholders, quoting, types,
auto-increment, `RETURNING` vs `lastrowid`) are handled by an internal SQL
dialect, so you never write database-specific SQL. Register connections and
point models at them with `Meta.db_alias` as shown in
[Database Connections](#database-connections-and-model-mapping) above. SQLite
support is planned.

---

## More Information

- See the [Project Overview](../README.md) for design philosophy.
- See [tests/models.py](../tests/models.py) for more model examples.

For advanced usage and API reference, see future documentation updates.
