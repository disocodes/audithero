from __future__ import annotations

import json
from datetime import date, datetime
from typing import Any


def _json_ready(value: Any) -> Any:
    """Convert AuditHero values to JSON-safe public data without masking errors.

    Keys beginning with ``_`` are runtime/cache implementation details and are
    deliberately excluded from persisted evidence JSON. Supported temporal
    values are emitted in ISO-8601 form. Any other unsupported Python object
    raises ``TypeError`` so setup and audit failures remain visible.
    """
    if isinstance(value, dict):
        return {
            str(key): _json_ready(item)
            for key, item in value.items()
            if not str(key).startswith("_")
        }
    if isinstance(value, (list, tuple)):
        return [_json_ready(item) for item in value]
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def json_dumps_public(value: Any, **kwargs: Any) -> str:
    """Serialize public AuditHero data while preserving strict error behaviour."""
    return json.dumps(_json_ready(value), **kwargs)
