from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class EvidenceScope(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    scope_type: str
    scope_id: str | None = None
    label: str | None = None
    attributes: dict[str, Any] = Field(default_factory=dict)
