# 0006 — Transaction support (ContextVar-bound, pool-staged)

**Status:** proposed (pending maintainer decisions — see Open questions)
**Date:** 2026-06-27

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

Adopt **ContextVar-bound transactions with a connection pool, staged in two
steps so the public API never changes:**

1. **Phase 1 — API on the shared connection.** Add `transaction()` to
   `BaseDatabase` and a `ContextVar` recording the active transaction. Inside the
   block, statements run on the existing shared connection without autocommit;
   `COMMIT` on clean exit, `ROLLBACK` on exception. Documented limitation: **one
   transaction at a time per backend** (concurrent transactions are unsafe on a
   single connection).
2. **Phase 2 — pool underneath (non-breaking).** Replace the single connection
   with `asyncpg.create_pool` / `aiomysql.create_pool`. A
   `ContextVar[Connection | None]` holds the task's checked-out connection;
   `execute/fetch/...` use it when set, else acquire a one-off connection. This
   makes concurrent transactions correct. **User code is unchanged.**

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

One implementation backs `db.transaction()`, an `atomic()` decorator, and an
optional `Model.transaction()` convenience.

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
- **Phase 2 introduces a pool:** `connect()`/`close()` become pool create/close;
  `is_connected` shifts from "have a connection" to "pool open." Adds pool-size
  config surface (where? `config.py` vs DSN params).
- **Hidden per-task state** (the ContextVar) is accepted as the cost of
  ergonomic binding; document the caveat: do not share one transaction across
  concurrently-running `asyncio.gather` tasks.
- **`get_or_create` becomes atomic** when wrapped, closing its documented gap.
- Phase 1 transactions are **not concurrency-safe** until Phase 2 lands — a
  documented interim limitation if we ship Phase 1 alone.

## Open questions (maintainer decisions)

1. **Ship order:** land Phase 1 (API on shared connection, documented
   single-transaction caveat) first, or go straight to Phase 2 (pool) so the
   first transactional release is concurrency-safe (FastAPI-ready)?
2. **Savepoints in v1:** real nested SAVEPOINTs now, or flat "outermost only"
   first with nesting later?
3. **Pool config:** min/max size and where it's configured (kept minimal per the
   project mission).
4. **Public entry points:** `db.transaction()` only, or also
   `DatabaseRegistry.transaction(alias)` and `Model.transaction()`?
5. **asyncpg native vs. raw SQL:** use asyncpg's built-in
   `connection.transaction()` (handles savepoints) vs. raw `BEGIN`/`SAVEPOINT`
   via the dialect for symmetry with the aiomysql path.

## Sources

- SQLAlchemy 2.0 async — https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html
- Django transactions — https://docs.djangoproject.com/en/5.1/topics/db/transactions/
- Tortoise ORM transactions — https://tortoise.github.io/transactions.html
- encode `databases` — https://www.encode.io/databases/connections_and_transactions/
- Peewee transactions — https://docs.peewee-orm.com/en/latest/peewee/transactions.html
