# RiverORM

RiverORM - minimalistic ORM for Python with async support.


## Table of Contents

- [Features](#riverorm-features)
- [Quick Example](#quick-example)
- [Usage](docs/USAGE.md) - a quickstart and usage guide.
- [Installation](docs/INSTALL.md) - a guide to install RiverORM with optional database backends.
- [Project Setup and Development](docs/DEVELOPMENT.md) - development guide and instructions.

## RiverORM features

When compared to existing solutions, RiverORM offers several key advantages:

1. **True async support by default:** Every query is await-able without extra setup, matching the needs of modern web frameworks. Developers can immediately use it in FastAPI or async scripts. This avoids the complexity of mixing sync and async (for example, unlike SQLAlchemy’s traditional sync usage or SQLModel’s sync mode).

2. **Unified model and schema (Pydantic):** Models inherit Pydantic validation, so there is one source of truth for field definitions. This eliminates duplication and leverages Pydantic’s power (nested validation, JSON schemas, etc). It’s like having Django’s migrations with SQLAlchemy’s flexibility; in fact, Piccolo similarly “uses Pydantic internally to serialize data”.

3. **Lightweight and modern:** Unlike heavyweight ORMs _(SQLAlchemy)_ or fragmented stacks, our core is minimal and written in idiomatic Python. We use modern syntax (e.g. int|None for optionals, pattern matching) and type hints aggressively, resulting in cleaner code and better auto-completion.

4. **Fine-grained query control:** Users can explicitly specify when to join or prefetch related tables. By default, related fields load lazily; but the API will offer methods to eagerly fetch joins when needed. At all times, developers can log or inspect the SQL (a feature SQLAlchemy provides) to avoid surprises. In other words, “everything [the ORM does] is ultimately the result of a developer-initiated decision,” just as SQLAlchemy’s philosophy states.

5. **No hidden costs or extra queries:** Because the ORM requires you to be explicit (no magic N+1 by default), it will behave predictably. Like Peewee’s approach, results can be fetched in bulk or streamed, and low-level operations remain possible (returning raw tuples for performance if desired).

6. **Multi-backend and extensible:** Built atop an abstracted DB layer (like databases), adding support for other SQL engines is straightforward. Our initial focus on PostgreSQL allows us to use advanced types (JSONB, UUID, arrays) and later adapt the same model definitions to SQLite or MySQL with minimal changes, similar to how Ormar and Piccolo abstract their backends.

7. **Developer ergonomics:** Extensive use of Python features means good editor support and faster development. For example, declaring relationships will use type hints and dataclass-like syntax, providing clear IDE hints. Async operations integrate with Python’s async ecosystem. We may even offer autocomplete for queries (like Piccolo’s tab-completion support).

8. **Future-proof design:** By embracing Pydantic v2/3 and Python 3.13 features, the ORM will stay relevant for years. We’ve seen ORMs like Piccolo quickly adopt 3.13 support. We likewise aim to stay on the cutting edge, so users can leverage new Python capabilities without waiting for the ORM to catch up.

In summary, our ORM will fill the gap for a compact, async-first, Pydantic-powered data layer. It will be as easy to use as Peewee or Ormar, but give the control and transparency that serious applications demand. By combining the best practices of existing libraries and learning from their limitations (for example, avoiding Peewee’s lack of migrations or Pony’s missing async), we can offer a superior, modern data mapper tailored for Python 3.13+ development.

Read more details about our [mission](docs/MISSION.md).

## Quick Example

A minimal but complete example showing async usage, model definition, and multi-database support:

```python
from riverorm import Field, Model
from riverorm.db import DatabaseRegistry, MySQLDatabase, PostgresDatabase

# Register connections
DatabaseRegistry.register("db1", PostgresDatabase("postgresql://user:pass@localhost/db1"))
DatabaseRegistry.register("db2", MySQLDatabase("mysql://user:pass@localhost/db2"))
DatabaseRegistry.register("db3", MySQLDatabase("mysql://user:pass@localhost/db3", debug=True))
DatabaseRegistry.set_default("db1")

# Define models
class User(Model):
    id: int | None = Field(default=None, pk=True)
    username: str

class Product(Model):
    id: int | None = Field(default=None, pk=True)
    name: str
    price: float
    in_stock: bool = Field(False)

    class Meta:
        db_alias = "db2"  # Use the MySQL connection

# Async usage
async def main():
    # Create tables
    await User.create_table()
    await Product.create_table()
    # Make queries
    user = User(username="alice")
    await user.save()
    await Product(name="Laptop", price=2_499.99).save()
    await Product(name="Phone", price=799.99, in_stock=True).save()
    # Filtering
    users = await User.all()
    products = await Product.filter(in_stock=True)
```

See the [Usage Guide](docs/USAGE.md) for more details and advanced examples.
