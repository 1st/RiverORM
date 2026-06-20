# 0001 — `from __future__ import annotations` with lazy forward-reference resolution

**Status:** accepted  
**Date:** 2026-06-20

## Context

RiverORM models use Pydantic v2 `BaseModel` and rely on type annotations for
two purposes: Pydantic validation and ORM type introspection (identifying
relation fields, determining column types, etc.).

When models reference each other in a circular or forward manner — e.g. `User`
has `orders: list[Order]` but `Order` is defined after `User` in the same
module — Python raises `NameError` unless the reference is quoted as a string
(`"Order"`). This manual quoting is verbose and inconsistent.

PEP 563 (`from __future__ import annotations`) makes *all* annotations lazy
strings automatically, removing the need for explicit quotes. However, Pydantic
marks a model as `__pydantic_complete__ = False` when it cannot resolve its
annotations at class-creation time. The canonical Pydantic fix is to call
`model_rebuild()` explicitly after all classes are defined — but this is user-
visible boilerplate that defeats the ergonomic goal.

We evaluated several approaches to automate the rebuild:

| Approach | Why it fails / is suboptimal |
| --- | --- |
| `__init_subclass__` eager rebuild | Hook fires *before* the class is bound in the module namespace, so the new class is not yet in `sys.modules[module].__dict__`. Rebuild with the class injected via `_types_namespace` triggers a different Pydantic error ("Class X is not defined") after partial resolution. |
| Global model registry + eager rebuild on each new class | Same root problem as `__init_subclass__`. Works only if no model references a class defined after it in the file, which is the common case we're trying to fix. |
| Require explicit `model_rebuild()` in user code | Leaks an internal Pydantic concept, breaks the "just define your classes" ergonomic promise, and is error-prone. |
| Lazy resolution on first ORM use | By the time any query or introspection method is called, the module is fully loaded and all classes are in `sys.modules`. Calling `model.model_rebuild(_types_namespace=vars(sys.modules[model.__module__]))` always succeeds. |

The lazy approach mirrors how SQLAlchemy 2.x resolves Annotated Mapped types
(deferred mapper configuration at first session use) and how Peewee resolves
`ForeignKeyField("ModelName")` (lookup at query generation time).

## Decision

Add `from __future__ import annotations` to every source and test file.
Replace all explicit string-quoted forward references (`"Order"`, `"User | None"`)
with bare unquoted syntax (`Order`, `User | None`).

Introduce a private `_ensure_model_complete(model)` helper in `riverorm/models.py`
that checks `model.__pydantic_complete__` and, if `False`, calls
`model.model_rebuild(_types_namespace=vars(sys.modules[model.__module__]))`.
Call this helper at the two ORM entry points that do type introspection:

- `Model.model_virtual_fields()` — resolves the current model before inspecting
  which fields are relation fields.
- `Model._prefetch_related()` — resolves before walking `model_fields` to
  identify the related model class for each relation spec.

All other introspection paths (`model_real_fields`, `_build_rel_map`,
`create_table`, `save`, query execution) flow through one of these two methods,
so a single guard at each entry point is sufficient.

## Consequences

**Positive**
- Users never call `model_rebuild()` or quote forward references. Models just work
  regardless of definition order in the file.
- All annotation syntax is modern and uniform throughout the codebase.
- Resolution is transparent: happens once per model, cached by Pydantic via
  `__pydantic_complete__`.
- Aligns with the pattern used by major async ORMs (SQLAlchemy, Peewee).

**Negative / obligations**
- Any new ORM entry point that directly accesses `model_fields` or annotation
  data without going through `model_virtual_fields` or `_prefetch_related` must
  also call `_ensure_model_complete(cls)` first, or risk receiving a `ForwardRef`
  instead of a resolved type. This requirement must be documented when adding
  new introspection paths.
- `_ensure_model_complete` calls `model_rebuild(raise_errors=True)`, so any
  genuinely unresolvable annotation (e.g. a typo in the class name) surfaces as
  a `PydanticUndefinedAnnotation` on the first ORM use rather than at class
  definition time. The error message is clear, but the timing differs from a
  plain Pydantic model.
