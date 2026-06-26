# 0005 — Apply `unique` / `index` Field metadata in DDL

**Status:** accepted
**Date:** 2026-06-27

## Context

`Field(unique=True)`, `Field(index=True)` and `Field(db_column=...)` were
accepted by `Field()` and stored on `FieldMeta`, but `create_table` only ever
read `max_length`. The constraints were silent no-ops — a real correctness
surprise (issue #101). Two questions had to be resolved:

1. How to emit `UNIQUE` and an index portably across Postgres and MySQL.
2. Whether `db_column` belongs in the same change.

`db_column` is fundamentally different: it requires a field-name ⇄ column-name
mapping at *every* call site that names a column — DDL, INSERT/UPDATE column
lists, SELECT projection, `WHERE` building, `select_related` aliases, and the
reverse direction when hydrating rows back into instances. That is invasive and
risk-bearing.

## Decision

Apply `unique` and `index` in `create_table` now; **split `db_column` into its
own issue** (#104) so this change stays small and reviewable.

- `unique`: rendered as a column-level `UNIQUE` (portable on both backends).
- `index`: emitted as a separate `CREATE INDEX idx_<table>_<col>` statement
  after the `CREATE TABLE`, via a new `Dialect.create_index()` method. Postgres
  overrides it to add `IF NOT EXISTS` (idempotent); MySQL has no such clause, so
  it relies on tables being dropped before recreation.
- A unique column already has an implicit index, so a standalone index is only
  emitted for `index=True and not unique` non-PK columns (no redundant index).

## Consequences

- `Field(unique=True)` / `Field(index=True)` now actually constrain the schema;
  a duplicate insert raises the driver's integrity error on both backends.
- Repeated `create_table()` is idempotent on Postgres but not MySQL (no
  `CREATE INDEX IF NOT EXISTS`); acceptable because the test fixture and
  migrations drop first. Revisit if standalone re-runs become a use case.
- `db_column` remains a silent no-op until #104; documented there, not here.
- Composite / multi-column unique constraints and named constraints are out of
  scope — single-column only for now.
