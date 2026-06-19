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

```python
from riverorm import Field, Model

class Product(Model):
    id: int | None = Field(default=None)  # `id` is the primary key by default
    name: str
    price: float
    in_stock: bool = Field(True)
```

The primary key is the `id` field by default. To use a different primary key,
set it on the model's `Meta`:

```python
class Product(Model):
    sku: str
    name: str

    class Meta:
        primary_key = "sku"
```

> **Note:** the primary key is configured via `Meta.primary_key` (default `"id"`),
> not via a `Field(pk=True)` argument.

---

## Relationships

Relationships are declared with a **foreign-key column** plus an annotated
**relation field** that RiverORM populates for you. A forward relation needs a
`<name>_id` column and a field typed as the related model; a reverse relation is
a field typed as a `list[...]` of the related model.

```python
class User(Model):
    id: int | None = Field(default=None)
    username: str
    # Reverse relation — populated by load_related("orders")
    orders: list["Order"] = Field(default_factory=list)

class Order(Model):
    id: int | None = Field(default=None)
    quantity: int
    user_id: int | None = Field(default=None)     # foreign key column
    product_id: int | None = Field(default=None)  # foreign key column
    # Forward relations — populated by select_related(...) / load_related(...)
    user: "User | None" = Field(default=None)
    product: "Product | None" = Field(default=None)
```

Relation fields (`user`, `product`, `orders`) are *virtual*: they are never
stored as columns. Only scalar columns — including the `_id` foreign keys —
are created in the database.

### Eager loading (no manual SQL)

Choose how related data is fetched:

```python
# select_related: a single SQL JOIN, best for forward (to-one) relations
orders = await Order.select_related("user", "product").all()
print(orders[0].user.username)

# load_related: one batched query per relation (avoids N+1); works for
# forward, reverse, and nested ("__") relations
users = await User.load_related("orders").all()
paid = await Order.load_related("product__user").filter(status="paid")
```

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

---

## Async Usage

All database operations are async.

```python
# Fetch a single row
product = await Product.get(id=1)

# Fetch many rows, optionally with field lookups
products = await Product.filter(in_stock=True, price__gte=500, price__lt=1000)
everything = await Product.all()

# Update: change attributes and save (an existing primary key triggers UPDATE)
product.name = "Apple MacBook"
await product.save()

# Delete
await product.delete()
```

### Filter lookups

`filter()` accepts Django-style field lookups via a `field__operator` suffix:

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

---

## More Information

- See the [Project Overview](../README.md) for design philosophy.
- See [tests/models.py](../tests/models.py) for more model examples.

For advanced usage and API reference, see future documentation updates.
