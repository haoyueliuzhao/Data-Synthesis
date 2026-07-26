from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, model_validator


class TemporalContext(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    label: str | None = None
    valid_from: date | None = None
    valid_to: date | None = None
    observed_at: date | None = None
    published_at: datetime | None = None
    retrieved_at: datetime | None = None
    basis: str | None = None
    frequency: str | None = None

    @model_validator(mode="after")
    def validate_ranges(self) -> TemporalContext:
        if self.valid_from and self.valid_to and self.valid_from > self.valid_to:
            raise ValueError("valid_from must not be after valid_to")
        return self
