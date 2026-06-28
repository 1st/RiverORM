# 0006 — Transaction support (ContextVar-bound, pool-staged)

**Status:** accepted
**Date:** 2026-06-27 (decisions resolved 2026-06-28)

## Context

RiverORM has **no transaction API** — only TODO comments, and `get_or_create`
documents "this is not atomic; wrap in a transaction" with nothing to wrap it
in (#102). A production ORM needs explicit, ergonomic transactions.

### Current architecture (what constrains us)

- Both backends hold a **single shared driver connection** for the process
  lifetime; there is **no pool**. `PostgresDatabase` keeps one
  `asyncpg.Connection`; `MySQLDatabase` keeps one `aiomysql.Connection` opened
  with **`autocommit=True`**.
- Every read/write funnels through `Model.db()` → a `BaseDatabase` method
  (`execute`/`fetch`/`fetchrow`/`update`/`execute_insert`/
  `execute_returning_rowcount`). There is **no notion of a "current connection"**
  that a sequence of operations shares — each call is an independent,
  autocommitting statement.
- `DatabaseRegistry.get(alias)` returns the same shared `BaseDatabase` instance
  every time.

Consequence: *binding* in-transaction operations is easy (one path,
`Model.db()`), but the *connection model* is the hard part — one shared
connection cannot safely host concurrent transactions from different async
tasks.

### How peers solve it (discovery)

Convergent pattern across SQLAlchemy 2.0, Django, **Tortoise ORM**, encode
`databases`, and Peewee: **one nestable construct** (context manager + decorator),
outermost = `BEGIN`/`COMMIT`, inner = `SAVEPOINT`, rollback-on-exception. Every
async ORM binds the active connection per task with **`contextvars`** so model
calls inside the block need no explicit handle (Tortoise sets a `ContextVar` to
the transaction connection and `reset()`s it on exit; encode `databases` ties
"transaction state to the connection used in the current async task"). Peewee's
single reentrant `atomic()` (transaction at depth 0, savepoint deeper) is the
ergonomic gold standard. See Sources.

## Decision

Adopt **ContextVar-bound transactions on a connection pool**, implemented
directly (no staging — the maintainer chose to ship concurrency-safe from day
one so FastAPI per-request transactions are correct immediately):

- Replace each backend's single shared connection with a pool
  (`asyncpg.create_pool` / `aiomysql.create_pool`). `connect()`/`close()` become
  pool create/close.
- A `ContextVar[Connection | None]` (keyed per alias) holds the **checked-out
  connection for the current async task**. Entering `transaction()` acquires a
  pool connection, issues `BEGIN`, and `set()`s the ContextVar (keeping the
  token); on exit `COMMIT`/`ROLLBACK`, release to the pool, `reset(token)`.
- The six `BaseDatabase` methods route to `ContextVar.get()` when a transaction
  is active, else acquire a one-off pooled connection (autocommit) for the
  statement. **`models.py`/`queryset.py` call sites are untouched.**

This is exactly Tortoise's / encode-`databases`' model and gives correct
per-task isolation: concurrent FastAPI requests each run in their own task,
hence their own transaction connection.

### Public API

```python
# Context manager (primary form)
async with User.db().transaction():
    user = await User.objects.create(username="alice")
    await Order(user_id=user.id, ...).save()
# COMMIT on success; any exception → ROLLBACK, then re-raises

# Decorator
@atomic()                      # or @atomic(alias="reporting")
async def transfer(...): ...

# Nested → SAVEPOINTs
async with db.transaction():
    await a.save()
    async with db.transaction():   # SAVEPOINT
        await b.save()             # rolls back to savepoint on inner error
```

**All four entry points ship**, one implementation behind them:

- `db.transaction()` — core form on a `BaseDatabase`.
- `@atomic(alias=None)` — decorator wrapping an async function (ideal as a
  FastAPI dependency / service method).
- `Model.transaction()` — convenience routing to the model's `Meta.db_alias`.
- `DatabaseRegistry.transaction(alias)` — explicit alias selection for multi-DB
  apps.

**Nesting ships in v1 with real SAVEPOINTs:** a nested `async with
db.transaction()` (depth ≥ 1) emits `SAVEPOINT`/`RELEASE`/`ROLLBACK TO`; an inner
rollback leaves the outer transaction intact. Reentrant like Peewee's `atomic()`.

### Binding mechanism

A module-level `ContextVar` (keyed per alias) holds the active transaction
connection. The six `BaseDatabase` methods consult it: bound → use the
transaction connection; unbound → today's shared connection (Phase 1) or a
pooled one-off (Phase 2). This keeps **all changes inside `BaseDatabase` /
`postgres.py` / `mysql.py`** — `models.py` and `queryset.py` call sites are
untouched.

### FastAPI integration (first-class — see #108)

The design is shaped so it drops into FastAPI cleanly:

```python
from contextlib import asynccontextmanager
from fastapi import Depends, FastAPI

@asynccontextmanager
async def lifespan(app: FastAPI):
    DatabaseRegistry.register("default", PostgresDatabase(DSN))
    await DatabaseRegistry.connect()     # Phase 2: opens the pool
    yield
    await DatabaseRegistry.close()       # closes the pool

app = FastAPI(lifespan=lifespan)

async def tx():                          # per-request transaction dependency
    async with User.db().transaction():
        yield

@app.post("/users")
async def create_user(body: UserIn, _=Depends(tx)) -> User:
    return await User.objects.create(**body.model_dump())
```

- **Lifespan** owns pool startup/shutdown via `DatabaseRegistry.connect()/close()`.
- A **dependency** wraps each request in a transaction (commit on success,
  rollback when the endpoint raises). Per-request isolation is exactly what the
  ContextVar/pool model provides — each request runs in its own async task.
- RiverORM models *are* Pydantic models, so they double as FastAPI
  request/response schemas.

This is why the connection model (pool + ContextVar) matters: it is what makes
the per-request FastAPI pattern correct under concurrency.

## Consequences

- **Ergonomic, implicit binding:** `await user.save()` inside the block just
  works — the dominant use case (multi-write business ops, `get_or_create`)
  with zero call-site churn.
- **MySQL autocommit becomes conditional:** inside a transaction the aiomysql
  connection must be `autocommit=False` (or `conn.begin()`), restored on exit —
  a real behavioral change to `mysql.py`.
- **A pool replaces the single connection:** `connect()`/`close()` become pool
  create/close; `is_connected` shifts from "have a connection" to "pool open."
  This is a real rewrite of `postgres.py`/`mysql.py` and the largest part of the
  work.
- **Hidden per-task state** (the ContextVar) is accepted as the cost of
  ergonomic binding; document the caveat: do not share one transaction across
  concurrently-running `asyncio.gather` tasks.
- **`get_or_create` becomes atomic** when wrapped, closing its documented gap.
## Resolved decisions

1. **Connection model — pool from day one.** No staging; implement the pool +
   ContextVar directly so transactions are concurrency-safe and FastAPI-ready
   immediately.
2. **Nesting — real SAVEPOINTs in v1** (reentrant `transaction()`).
3. **Entry points — all four ship:** `db.transaction()`, `@atomic()`,
   `Model.transaction()`, `DatabaseRegistry.transaction(alias)`.
4. **Pool config — minimal:** sensible default min/max sizes; expose overrides
   later (DSN query params or `config.py`) only if needed, per the minimalistic
   mission.
5. **SAVEPOINT/BEGIN rendering — raw SQL via the dialect** for both backends, so
   Postgres and MySQL share one transaction code path (over asyncpg's native
   `connection.transaction()`), keeping behavior symmetric and testable.

Implementation tracked in #102; FastAPI guide/example in #108.

## Sources

- SQLAlchemy 2.0 async — https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html
- Django transactions — https://docs.djangoproject.com/en/5.1/topics/db/transactions/
- Tortoise ORM transactions — https://tortoise.github.io/transactions.html
- encode `databases` — https://www.encode.io/databases/connections_and_transactions/
- Peewee transactions — https://docs.peewee-orm.com/en/latest/peewee/transactions.html
