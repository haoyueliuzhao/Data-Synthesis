from __future__ import annotations

import json
import math
from collections.abc import Mapping
from datetime import date, datetime, time
from decimal import Decimal, InvalidOperation
from enum import Enum
from hashlib import sha256
from typing import Any

from pydantic import BaseModel


def _canonical_decimal(value: Decimal) -> str:
    if not value.is_finite():
        raise ValueError("canonical JSON does not permit a non-finite Decimal")
    normalized = value.normalize()
    if normalized == 0:
        normalized = Decimal(0)
    return format(normalized, "f")


def to_canonical_json_data(value: Any) -> Any:
    """Recursively convert registered values to deterministic JSON data.

    This is the strict v2 canonicalizer. The legacy ``canonical_hash`` helper is
    intentionally unchanged because historical content identities bind its old
    top-level-only Pydantic behavior.
    """

    if isinstance(value, BaseModel):
        return to_canonical_json_data(value.model_dump(mode="python"))
    if isinstance(value, Enum):
        return to_canonical_json_data(value.value)
    if isinstance(value, Mapping):
        output: dict[str, Any] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise TypeError("canonical JSON Mapping keys must be strings")
            output[key] = to_canonical_json_data(item)
        return output
    if isinstance(value, (list, tuple)):
        return [to_canonical_json_data(item) for item in value]
    if isinstance(value, Decimal):
        return _canonical_decimal(value)
    if isinstance(value, datetime):
        return value.isoformat(timespec="microseconds")
    if isinstance(value, time):
        return value.isoformat(timespec="microseconds")
    if isinstance(value, date):
        return value.isoformat()
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("canonical JSON does not permit a non-finite float")
        try:
            return float(_canonical_decimal(Decimal(str(value))))
        except (InvalidOperation, ValueError) as error:
            raise ValueError("canonical JSON float is invalid") from error
    raise TypeError(f"unsupported canonical JSON value: {type(value).__name__}")


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        to_canonical_json_data(value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def strict_canonical_hash(value: Any, *, prefix: str = "") -> str:
    digest = sha256(canonical_json_bytes(value)).hexdigest()
    return f"{prefix}{digest}" if prefix else digest
