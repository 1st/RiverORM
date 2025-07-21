# Our mission

RiverORM is a modern, async-enabled Python ORM that uses [Pydantic](https://github.com/pydantic/pydantic) models for schema and data. Its key features and benefits include:

1. **Async/await support out-of-the-box**. Like Tortoise ORM, all database operations return awaitables. You can write, for example, `users = await User.objects.filter(active=True).all()`. This makes it plug-and-play with [FastAPI](https://github.com/fastapi/fastapi), Starlette, Sanic, etc. Our ORM follow async-first approach by default.

2. **Single Pydantic-based model**. Each ORM model class inherits from a base that includes Pydantic validation. This means you define one class and get both the database schema and the JSON-schema/validation. Like Ormar, “you don’t have to maintain Pydantic and other ORM models” separately. This greatly reduces code duplication and errors. Returned rows can be directly output as Pydantic objects, or used as FastAPI response models.

3. **Compact, Pythonic syntax**. We design the API to be concise (inspired by Peewee and Ormar). For example, you might write filters using Python operators (`User.age > 30`) or keyword lookups (`User.get(name="Alice")`). Defaults and introspection will minimize boilerplate (e.g. auto-generated id fields). The ORM is fully type-annotated and use Python 3.13+ features, giving good IDE/editor support and static checks (as SQLAlchemy 2.0 and SQLModel do).

4. **Explicit query control**. Developers will choose when to load related data. The ORM supports both lazy and eager loading of relations, similar to Django’s _select_related/prefetch_related_ or Ormar’s techniques. Importantly, it is possible to inspect or log the raw SQL (as SQLAlchemy encourages), so there are no “hidden” or mysterious queries. This transparency addresses a common complaint about ORMs generating extra queries.

5. **Lightweight and modular**. Unlike monolithic ORMs, RiverORM has minimal core dependencies. We may leverage lightweight components (e.g. databases for async DB drivers) but keep our own query-builder layer. This aims to give the power of SQLAlchemy-style expressions without forcing the user to learn or install SQLAlchemy itself.

6. **Pluggable and framework-agnostic**. The ORM doesn't assume any specific web framework. It can be used in FastAPI, Django, Flask, CLI tools, scripts, etc. It includes optional integration examples (e.g. how to plug into FastAPI dependency injection). Because we use Pydantic, it will fit naturally into FastAPI/Starlette workflows, but it will not depend on them.

7. **Multi-DB support**. We start with PostgreSQL (asyncpg driver) to get advanced features (JSONB, array, etc.), but design the core so that other backends can be added. Later we can add MySQL, SQLite, etc., similar to Ormar’s support for multiple backends. Also our plans include to add NoSQL backends, like MongoDB.

8. **Future migrations and admin**. Initially, schema migrations may be manual or via an external tool (like Alembic). In the future, we could develop a simple migration system or integrate with existing ones. We may also consider providing a built-in admin interface or integration (as Django/Piccolo do) for developers who want it.

By combining these elements, RiverORM aims to deliver the lightweight ease-of-use of Peewee, the async-first nature of Tortoise, and the Pydantic integration of Ormar, while giving developers full insight and control over the generated SQL.
