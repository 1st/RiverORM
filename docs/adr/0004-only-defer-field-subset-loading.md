# 0004 — `only()` / `defer()` field-subset loading

| Field | Value |
|---|---|
| **Status** | accepted |
| **Date** | 2026-06-20 |

## Context

Full-table `SELECT *` queries are wasteful when callers only need a handful of
columns (listing UIs, large text blobs on hot paths, etc.). Issue #50 tracks
the requirement. The original draft implemented `only()` accepting plain
strings, but untyped string literals silently break when models are refactored.

## Decision

Introduce two chaining methods — `only()` and `defer()` — and a typed
`FieldRef` value so callers can reference fields as Python attributes rather
than bare strings:

```python
f = User.f
await User.objects.only(f.id, f.username).all()   # include subset
await User.objects.defer(f.email).all()            # exclude subset
await User.objects.only("id", "username").all()    # strings still work
```

**`FieldRef`** (`riverorm.fields`) is a frozen dataclass holding a field name.
It has no negation or `excluded` flag — `only()` and `defer()` are separate
methods with distinct semantics, not a single function with signed refs.

**`FieldsNamespace`** / **`_FieldsDescriptor`** (`riverorm.models`) expose
`Model.f` as a lazy descriptor. `Model.f.field_name` returns `FieldRef(field_name)`;
unknown or virtual (relation) fields raise `AttributeError` immediately at the
call site.

**`QuerySet.only(*fields)`** stores a positive `only_fields` tuple; SQL uses
`SELECT col1, col2 …`.

**`QuerySet.defer(*fields)`** stores a `defer_fields` tuple; SQL expands to
all real fields minus the deferred ones at query-build time.

Both methods validate names against `model_real_fields()` and raise
`ValueError` immediately for unknown or virtual fields. Setting one clears the
other (they are mutually exclusive per query).

The **primary key is always loaded**, even when `only()` omits it or `defer()`
names it — mirroring Django. This keeps partial instances identity-safe so
`save()` / `delete()` work and the PK is never silently lost.

Plain strings are accepted and coerced to `FieldRef` internally for
backward compatibility.

**SQL layer** — `SelectQuery.columns` already accepted an explicit column tuple
(empty = `SELECT *`). No SQL-layer changes were needed.

**Partial instantiation** — rows missing columns use `Model.model_construct()`
(bypasses Pydantic validation; Python-level defaults fill un-fetched optional
fields). The resulting instances are marked `_persisted = True` and record the
fetched columns in `_loaded_fields`.

**Save safety** — `save()` on a partial instance restricts its UPDATE to the
loaded columns (the PK is the WHERE key and never in the SET list), so
un-fetched columns are not overwritten with their Python defaults. `save()`
gained an `update_fields` argument to write an explicit subset on any instance.

## Consequences

- Field references checked against `model_real_fields()` at call time → typos
  surface as `AttributeError` / `ValueError` at the line that builds the query,
  not buried in SQL errors.
- IDEs that honour `__dir__` may show real field names as autocomplete
  suggestions on `Model.f`. Full static checking (mypy/pyright) cannot verify
  attribute names without a plugin; `Model.f.nonexistent` is a runtime error,
  not a type error.
- `model_construct` skips Pydantic coercion. MySQL `BOOLEAN` columns arrive as
  `1`/`0` integers on partial rows; code that checks `is True` instead of
  truthiness will see a difference.
- `only()` / `defer()` do not compose with `select_related()`: the JOIN path
  builds its own column list. Combining them raises `ValueError` at execution
  rather than silently ignoring the column restriction.
- Required fields (no default) that are excluded will not be set as attributes;
  accessing them raises `AttributeError`. The primary key is exempt — it is
  always fetched.
- Saving a partial instance writes only its loaded columns. Setting an
  un-fetched attribute and calling `save()` without naming it in
  `update_fields` will therefore not persist that change.
