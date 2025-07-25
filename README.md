# RiverORM

RiverORM - minimalistic ORM for Python with async support.


## Table of Contents

- [Features](#riverorm-features)
- [Usage](docs/USAGE.md) - a quickstart and usage guide.
- [Installation](docs/INSTALL.md) - a guide to install RiverORM with optional database backends.
- [Project Setup and Development](#project-setup-and-development)


## RiverORM features

When compared to existing solutions, RiverORM offers several key advantages:

1. **True async support by default:** Every query is await-able without extra setup, matching the needs of modern web frameworks. Developers can immediately use it in FastAPI or async scripts. This avoids the complexity of mixing sync and async (for example, unlike SQLAlchemy’s traditional sync usage or SQLModel’s sync mode).

2. **Unified model and schema (Pydantic):** Models inherit Pydantic validation, so there is one source of truth for field definitions. This eliminates duplication and leverages Pydantic’s power (nested validation, JSON schemas, etc). It’s like having Django’s migrations with SQLAlchemy’s flexibility; in fact, Piccolo similarly “uses Pydantic internally to serialize data”.

3. **Lightweight and modern:** Unlike heavyweight ORMs _(SQLAlchemy)_ or fragmented stacks, our core is minimal and written in idiomatic Python. We will use modern syntax (e.g. int|None for optionals, pattern matching) and type hints aggressively, resulting in cleaner code and better auto-completion. For example, creating a model in our ORM will be as simple as:

```python
from riverorm import Field, Model

class Product(Model):
    id: int = Field(pk=True)
    name: str
```
_(This minimal style draws inspiration from Peewee’s compact definitions and SQLModel’s type-annotated models)._

4. **Fine-grained query control:** Users can explicitly specify when to join or prefetch related tables. By default, related fields load lazily; but the API will offer methods to eagerly fetch joins when needed. At all times, developers can log or inspect the SQL (a feature SQLAlchemy provides) to avoid surprises. In other words, “everything [the ORM does] is ultimately the result of a developer-initiated decision,” just as SQLAlchemy’s philosophy states.

5. **No hidden costs or extra queries:** Because the ORM requires you to be explicit (no magic N+1 by default), it will behave predictably. Like Peewee’s approach, results can be fetched in bulk or streamed, and low-level operations remain possible (returning raw tuples for performance if desired).

6. **Multi-backend and extensible:** Built atop an abstracted DB layer (like databases), adding support for other SQL engines is straightforward. Our initial focus on PostgreSQL allows us to use advanced types (JSONB, UUID, arrays) and later adapt the same model definitions to SQLite or MySQL with minimal changes, similar to how Ormar and Piccolo abstract their backends.

7. **Developer ergonomics:** Extensive use of Python features means good editor support and faster development. For example, declaring relationships will use type hints and dataclass-like syntax, providing clear IDE hints. Async operations integrate with Python’s async ecosystem. We may even offer autocomplete for queries (like Piccolo’s tab-completion support).

8. **Future-proof design:** By embracing Pydantic v2/3 and Python 3.13 features, the ORM will stay relevant for years. We’ve seen ORMs like Piccolo quickly adopt 3.13 support. We likewise aim to stay on the cutting edge, so users can leverage new Python capabilities without waiting for the ORM to catch up.

In summary, our ORM will fill the gap for a compact, async-first, Pydantic-powered data layer. It will be as easy to use as Peewee or Ormar, but give the control and transparency that serious applications demand. By combining the best practices of existing libraries and learning from their limitations (for example, avoiding Peewee’s lack of migrations or Pony’s missing async), we can offer a superior, modern data mapper tailored for Python 3.13+ development.

Read more details about our [mission](docs/MISSION.md).


## Project Setup and Development

### Initial Setup

To set up the project and install all dependencies, run:

```sh
make setup
```

This will:
- Install system dependencies (e.g., uv)
- Create a Python virtual environment using `uv`
- Install all Python dependencies

### Starting Database Containers (Optional)

If you do not already have a database running locally, you can start the required database services using Docker:

```sh
make docker-up
```

This will run `docker compose` to start the database containers defined in `docker-compose.yml`.

If you prefer to use your own local database, you can skip this step.

### Running Tests

To run the test suite:

```sh
make test
```

Some tests require a running database, so ensure you have one available (either via Docker or locally). The tests will automatically connect to the database specified in the `POSTGRES_DSN` environment variable.

Find all tests in the `tests` directory. The tests are run using `pytest`, which provides a detailed output of the test results.

### Code Checks (Linting & Formatting)

To check code style and formatting:

```sh
make lint
```

This will run `ruff` for linting and formatting checks on the codebase.

### Install pre-commit hooks

Pre-commit hooks help maintain code quality by running checks before commits. To install them, run:

```bash
pre-commit install
```
