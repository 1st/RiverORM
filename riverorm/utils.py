"""Utilities for RiverORM."""

from __future__ import annotations

import types
from typing import Any, Union, get_args, get_origin


def is_int_type(annotation: Any) -> bool:
    """Return True if int is (part of) this annotation, unwrapping Optional/Union."""
    if annotation is int:
        return True
    if isinstance(annotation, types.UnionType):
        return any(a is int for a in annotation.__args__ if a is not type(None))
    origin = get_origin(annotation)
    args = get_args(annotation)
    if origin is Union and args:
        return any(a is int for a in args if a is not type(None))
    return False


def is_nullable(annotation: Any) -> bool:
    """Return True if NoneType is part of this annotation's union."""
    if annotation is type(None):
        return True
    if isinstance(annotation, types.UnionType):  # int | None (PEP 604)
        return type(None) in annotation.__args__
    if get_origin(annotation) is Union:  # typing.Optional[int]
        return type(None) in get_args(annotation)
    return False


def unwrap_type(annotation: Any) -> Any:
    """Return the first non-None type from a Union/Optional, or the annotation itself."""
    if isinstance(annotation, types.UnionType):
        return next((a for a in annotation.__args__ if a is not type(None)), annotation)
    if get_origin(annotation) is Union:
        return next((a for a in get_args(annotation) if a is not type(None)), annotation)
    return annotation
