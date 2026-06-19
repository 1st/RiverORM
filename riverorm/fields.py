"""RiverORM field definitions.

:func:`Field` is a thin wrapper around :func:`pydantic.Field` that additionally
accepts ORM-level metadata (primary key, index, uniqueness, column name, length).
The metadata is stored as a :class:`FieldMeta` instance inside Pydantic's
``json_schema_extra`` under a private key so it round-trips on the resulting
``FieldInfo`` and can be read back per-field by the model.

``FieldMeta`` is intentionally small and extensible: it is the foundation for
upcoming features such as relationships, indexes/constraints, and migrations.
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass
from typing import Any

from pydantic import Field as _PydanticField
from pydantic.fields import FieldInfo

#: Private key under which :class:`FieldMeta` is stashed in ``json_schema_extra``.
RIVERORM_META_KEY = "__riverorm__"


@dataclass
class FieldMeta:
    """ORM-level metadata attached to a model field.

    Kept deliberately minimal and extensible so future increments
    (relationships, indexes/constraints, migrations) can add attributes here
    without changing the ``Field`` call sites.
    """

    primary_key: bool = False
    index: bool = False
    unique: bool = False
    db_column: str | None = None
    max_length: int | None = None


def Field(  # noqa: N802 - mirrors pydantic.Field's callable-as-name convention
    default: Any = ...,
    *,
    primary_key: bool = False,
    index: bool = False,
    unique: bool = False,
    db_column: str | None = None,
    max_length: int | None = None,
    pk: bool | None = None,
    **kwargs: Any,
) -> Any:
    """Define a model field, forwarding to :func:`pydantic.Field`.

    In addition to every argument accepted by ``pydantic.Field``, this accepts
    ORM metadata: ``primary_key``, ``index``, ``unique``, ``db_column`` and
    ``max_length``. The metadata is stored on the field's ``json_schema_extra``
    as a :class:`FieldMeta` so the model can read it back via
    :meth:`riverorm.models.Model._field_meta`.

    ``max_length`` is also forwarded to Pydantic for validation.

    The legacy ``pk=True`` keyword is still accepted (mapped to
    ``primary_key=True``) but emits a :class:`DeprecationWarning`.
    """
    if pk is not None:
        warnings.warn(
            "Field(pk=...) is deprecated; use Field(primary_key=...) instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        primary_key = primary_key or pk

    meta = FieldMeta(
        primary_key=primary_key,
        index=index,
        unique=unique,
        db_column=db_column,
        max_length=max_length,
    )

    # Merge our metadata into json_schema_extra without clobbering user values.
    extra = kwargs.pop("json_schema_extra", None)
    if extra is None:
        extra = {}
    if isinstance(extra, dict):
        extra = {**extra, RIVERORM_META_KEY: meta}
    # If a callable json_schema_extra was provided, leave it untouched and skip
    # storing metadata that way (callable extras are rare and out of scope).
    if isinstance(extra, dict):
        kwargs["json_schema_extra"] = extra

    if max_length is not None:
        kwargs.setdefault("max_length", max_length)

    return _PydanticField(default, **kwargs)


def field_meta(field: FieldInfo) -> FieldMeta:
    """Return the :class:`FieldMeta` for a ``FieldInfo`` (default if absent)."""
    extra = field.json_schema_extra
    if isinstance(extra, dict):
        meta = extra.get(RIVERORM_META_KEY)
        if isinstance(meta, FieldMeta):
            return meta
    return FieldMeta()
