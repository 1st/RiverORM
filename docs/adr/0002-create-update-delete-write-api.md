# 0002 — QuerySet write terminals: create, update, delete, get_or_create

**Status:** accepted  
**Date:** 2026-06-20

## Context

RiverORM's initial QuerySet API covered read paths only (`all`, `first`, `get`,
`count`, `exists`). Production applications routinely need to:

- Insert a row in one expression without an intermediate variable.
- Update many rows atomically without fetching them first (avoids N+1 round-trips).
- Delete many rows with a filter without fetching them first.
- Retrieve a row or create it when absent (a very common idempotent-write pattern).

Without these, callers fall back to fetch-then-loop patterns that:
1. Require extra queries.
2. Discard the database's ability to execute the operation as a single statement.

## Decision

Add four write operations to `QuerySet` and `Manager`, and a convenience
classmethod to `Model`:

| API | Description |
| --- | --- |
| `Model.objects.create(**kwargs)` / `Model.create(**kwargs)` | Instantiate, persist, and return in one call. |
| `QuerySet.update(**fields)` → `int` | Bulk-UPDATE all matching rows; returns affected count. |
| `QuerySet.delete()` → `int` | Bulk-DELETE all matching rows; returns deleted count. |
| `Manager.get_or_create(defaults=None, **lookups)` → `(T, bool)` | Fetch or create; second element is `True` when a new row was inserted. |

`Manager.update()` and `Manager.delete()` are thin wrappers around the
QuerySet equivalents that operate on the entire table (no filter).

**`execute_returning_rowcount(sql, *params) -> int`** was added to
`BaseDatabase` (and implemented in `PostgresDatabase` and `MySQLDatabase`) to
give a unified rowcount return for write queries across backends:

- Postgres: parses the asyncpg status string (`"DELETE 3"`, `"UPDATE 2"`).
- MySQL: returns `cursor.rowcount` directly.

**`save()`** return type was narrowed from implicit `Model` to `Self` so that
callers like `await Product(...).save()` have the correct concrete type inferred
by mypy without a cast.

## Consequences

**Positive**
- Common patterns are now one-liners: `await Order.objects.filter(status="x").delete()`.
- Bulk writes avoid fetch overhead: `UPDATE` and `DELETE` go to the database as
  a single statement regardless of how many rows match.
- `get_or_create` enables idempotent writes (seed data, upsert-light patterns).
- `save()` returning `Self` means chaining `await Model(...).save()` is
  type-safe; no cast needed in callers.

**Negative / obligations**
- `get_or_create` is **not atomic** — there is a TOCTOU race between the GET
  and the CREATE under concurrent writers. This is acceptable for now; the fix
  (wrap in a transaction) belongs to the planned transaction support (Epic E).
  The docstring and USAGE.md both note this limitation.
- `QuerySet.update()` does not refresh in-memory instances. Callers that hold a
  reference to a model object and then call `qs.update()` on it will see stale
  data until they re-fetch. This is consistent with Django ORM's behaviour and
  is not considered a bug.
- `Manager.delete()` (no filter) deletes **all rows**. This is intentional and
  mirrors Django, but contributors should be aware: `User.objects.delete()` is a
  table-wide `DELETE FROM users`.
