"""Utilities for RiverORM."""

import types


def is_int_type(ft):
    """Check if a field type is or includes int."""
    if ft is int:
        return True
    if hasattr(types, "UnionType") and isinstance(ft, types.UnionType):
        return any(is_int_type(a) for a in ft.__args__ if a is not type(None))
    origin = getattr(ft, "__origin__", None)
    args = getattr(ft, "__args__", ())
    if origin is not None and args:
        return any(is_int_type(a) for a in args if a is not type(None))
    return False
