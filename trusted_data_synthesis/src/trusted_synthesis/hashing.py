from __future__ import annotations

import json
from hashlib import sha256
from typing import Any

from pydantic import BaseModel


def canonical_hash(value: Any, *, prefix: str = "") -> str:
    if isinstance(value, BaseModel):
        value = value.model_dump(mode="json", exclude_none=True)
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    digest = sha256(payload).hexdigest()
    return f"{prefix}{digest}" if prefix else digest
