"""Compatibility shim — prefer `from app.db.types import sa_json_object`."""

from app.db.types import sa_json_array, sa_json_object  # noqa: F401

__all__ = ["sa_json_object", "sa_json_array"]
