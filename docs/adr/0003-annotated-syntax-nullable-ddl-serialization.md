# 0003 — Annotated field syntax, nullable DDL, and to_dict / to_json

**Status:** accepted  
**Date:** 2026-06-20

## Context

Two related gaps in the field system (Epic C, issues #28 and #30):

1. **Annotated syntax (#30)**: Python's `Annotated[T, metadata]` is the modern, preferred way to attach type metadata without mixing a value assignment into a field declaration. Pydantic v2 supports it natively. RiverORM should too, so users can write `username: Annotated[str, Field(max_length=50)]` instead of `username: str = Field(max_length=50)`.

2. **Nullable DDL (#28)**: `create_table` was not emitting `NOT NULL` for non-optional columns. That means the database would accept `NULL` where the application model rejects it — a correctness gap that could surface as data integrity issues at the DB level.

3. **Serialization helpers (#28)**: Pydantic's own `model_dump()` / `model_dump_json()` work but include virtual (relation) fields by default, which are not columns and shouldn't appear in a "save to DB" or "send over the wire" serialization of a model instance.

## Decision

### Annotated syntax support

Pydantic v2 processes `Annotated[T, FieldInfo]` transparently: the `FieldInfo` in the annotation metadata becomes the field's metadata in `model_fields`, with `field.annotation` set to `T`. Since our `Field()` wrapper embeds `FieldMeta` in `json_schema_extra`, and Pydantic preserves that, **no engine-level changes are needed** — the existing `field_meta()` function and `model_virtual_fields()` both work correctly with `Annotated`.

The deliverable is test coverage (unit + integration) confirming both syntax styles are equivalent, and updated documentation showing both forms.

### Nullable DDL

Added `is_nullable(annotation)` to `riverorm/utils.py`. It checks:
- `int | None` (PEP 604 `types.UnionType`)
- `typing.Optional[int]` / `typing.Union[int, None]`
- `type(None)` itself

`create_table` now appends `NOT NULL` for every non-PK, non-nullable column. Nullable columns (and PKs, which carry their own constraints) receive no extra qualifier.

Additionally, the fragile string-type detection (`hasattr(field_type, "__args__") and str in ...`) was replaced with `unwrap_type(annotation)` which strips the Optional wrapper and returns the base type. This also correctly handles `str | None` fields for VARCHAR generation.

### Serialization helpers

Added two instance methods to `Model`:

| Method | Description |
| --- | --- |
| `to_dict(*, exclude_none=False, exclude_virtual=True)` | Returns a plain `dict` with relation fields excluded by default. |
| `to_json(*, exclude_none=False, exclude_virtual=True)` | Returns a JSON `str` with relation fields excluded by default. |

Both delegate to Pydantic's `model_dump()` / `model_dump_json()` with the `exclude` set computed from `model_virtual_fields()`. Private attributes (like `_persisted`) are excluded by Pydantic automatically.

The default of `exclude_virtual=True` matches the most common use case (persistence, API response, logging) and avoids accidentally serializing large related-object graphs that were eagerly loaded.

## Consequences

**Positive**
- Both field-declaration styles are supported and equivalent; users can migrate their models incrementally.
- DDL now matches the application's nullability contract — inserting NULL into a `str` (non-Optional) column will be rejected by the database.
- `to_dict()` / `to_json()` reduce boilerplate for the common "serialize this row" pattern.

**Negative / obligations**
- **Existing tables** created before this change do not have `NOT NULL` on columns that should. A schema migration is needed to add these constraints (migrations are Epic H).
- `to_dict(exclude_virtual=False)` will include related objects **if** they were eagerly loaded; callers are responsible for ensuring related objects are serializable if they opt in.
