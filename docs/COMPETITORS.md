# Competitors

Existing Python ORM Libraries.


## Modern ORMs

Modern Python has many ORMs.

We focus here on popular and innovative ones that inspire our design:

### SQLModel

**SQLModel (★16k)** – A recent library by FastAPI’s author that wraps SQLAlchemy with Pydantic models. With a single class (inheriting from `SQLModel, table=True`), you define both the DB table and Pydantic schema. It offers excellent editor support and minimizes duplication of models. For example:

```python
class Hero(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str
    secret_name: str
    age: int | None = None
```

_(Under the hood it uses SQLAlchemy 2.0; SQLModel is sync by default and powered by SQLAlchemy’s Core and ORM. It excels in simplicity and Pydantic integration but relies on SQLAlchemy for execution)._

### Peewee

**Peewee (★11k)** – A lightweight, expressive ORM written by Charles Leifer. Peewee is “a simple and small ORM” with minimal boilerplate. It supports SQLite, PostgreSQL, MySQL, MariaDB and CockroachDB. Defining models is very concise (like Django models, but even less verbose). Queries resemble SQL (e.g. `User.select().where(User.age>30)`) and can return dicts, tuples or model instances. Peewee emphasizes ease-of-use and is highly readable. Its drawbacks: it has no built-in async support, and while you can use its SchemaManager or third-party tools for migrations, it lacks a native migrations engine.

### SQLAlchemy

**SQLAlchemy (★10k)** – The most widely-used Python ORM. SQLAlchemy has two layers: the Core (a powerful SQL expression toolkit) and the ORM on top. It gives developers full control over queries and schema. The new SQLAlchemy 2.0 (early 2023) added a modern, typed API that integrates well with Python’s type hints. In SQLAlchemy you can define models either by tables or by Python classes (dataclass style), providing flexibility. It is extremely robust (schemaless JSON, sharding, migrations via Alembic, etc.) but can be heavyweight and complex. Queries can be expressed in a SQL-like syntax (`select(User).where(User.name=="Davis")`) and you can always print or inspect the raw SQL. SQLAlchemy’s philosophy is “ORM doesn’t hide the R (relational)”, giving developers explicit control over generated queries. While powerful, newcomers sometimes find it verbose (requiring session management, explicit joins, etc.) and its default mode is synchronous.

### Tortoise

**Tortoise ORM (★5k)** – An async-native ORM inspired by Django. It only supports Python 3.9+, and is “the only one [in InfoWorld’s survey] that is asynchronous by default”. Models subclass tortoise.models.Model and fields use classes like IntField, ForeignKeyField, etc. (similar to Django fields). Queries use a more Pythonic API: e.g. `await User.filter(age__gt=20).exclude(status='inactive')` rather than raw SQL. Tortoise provides utilities like signals, a multi-database router, and even an .explain() method to show query plans. It has a Pydantic plugin for generating response models from DB objects. Being async-first, it integrates well with FastAPI/Starlette-style apps. However, it currently handles serialization only (no built-in deserialization via Pydantic) and you need an external tool (Aerich) for migrations.

### Pony

**Pony ORM (★3k)** – An older but unique ORM that lets you write queries as Python expressions. For example, you can do: `select(u for u in User if u.name.startswith("A")).order_by(User.name)` using generator syntax. Pony analyzes the Python AST and translates it to SQL, which you can always view. Model fields are declared first by behavior (e.g. Required(str, unique=True)) then by type. Pony has built-in support for JSON and array types and even shims for older DBs. Its strengths are clarity (the query syntax is very “native Python”) and interactive use. Downsides: it has no native schema migrations yet and adds some hidden behaviors (e.g. it auto-adds DISTINCT by default) that you must override. Pony does not natively support async (you typically run it in threads).

### Django

**Django ORM** – (part of Django web framework) A venerable, full-featured ORM influenced by decades of use. It auto-generates migrations and supports a rich query API, but is tightly coupled to the Django ecosystem. It uses Python classes to define models and provides a very powerful admin, but it generally requires using the Django framework itself. We mention it for completeness: its schema/migration system is mature, but it is not a drop-in for arbitrary apps outside Django.


## Other innovative ORMs

Beyond these, newer projects are pushing Python ORM design further:

### Ormar

**Ormar (★2k)** – A Pydantic- and FastAPI-oriented async ORM. It exposes an objects query manager (like Tortoise) for async operations (e.g. `await Author.objects.create(...)`). It was explicitly built so one model class (a subclass of ormar.Model) serves as both the DB schema and the Pydantic schema. Ormar’s docs highlight that it’s async and schema-agnostic, and that it uses SQLAlchemy Core under the hood and the databases library for async support. Ormar’s main benefit is “one model to maintain” – you don’t write a separate Pydantic schema since the ORM model is a Pydantic model for FastAPI routes. It has built-in support for selecting/related objects (with select_related/prefetch_related) and its query API is concise (though not as close to raw SQL as SQLAlchemy).

### Piccolo

**Piccolo ORM** – A fast, async-first ORM and query builder with admin interface and rich tooling. Piccolo is fully type-annotated (it supports Python 3.13) and uses Pydantic under the hood for serialization. It offers a built-in CLI and web-playground, and even scaffolds ASGI apps with various frameworks. Piccolo lets you generate Pydantic models from your tables (create_pydantic_model) and supports nested serialization of related objects easily. Piccolo also handles JSON/JSONB queries smoothly. It supports sync and async and has features like row locking and migrations.

### GINO

**GINO (★2k)** – An async ORM that sits on top of SQLAlchemy Core for PostgreSQL. GINO (short for “GINO Is Not ORM”) is lightweight and uses SQLAlchemy’s expression language, but is less actively developed nowadays.

### Beanie

**Beanie** (for Mongo) – Not relational, but worth mentioning if you consider NoSQL: Beanie is an async ODM (Object-Document Mapper) for MongoDB using Pydantic models. While out of scope for SQL, projects like it show how Pydantic makes async data models ergonomic.


## Conclusions

Piccolo, Ormar and Tortoise exemplify a new generation of ORMs that combine async/await, type hints/Pydantic, and minimalist design. For example, Ormar and Piccolo both aim to eliminate model duplication and fit naturally into FastAPI-like stacks.
