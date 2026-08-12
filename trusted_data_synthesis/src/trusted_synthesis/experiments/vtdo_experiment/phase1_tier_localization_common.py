from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator


class TierLocalizationThresholds(BaseModel):
    """Runtime-neutral thresholds for grouped empirical tier localization."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    minimum_technical_resolution_rate: float = Field(default=0.80, ge=0, le=1)
    boundary_probability_lower: float = Field(default=0.10, ge=0, le=1)
    boundary_probability_upper: float = Field(default=0.90, ge=0, le=1)
    minimum_informative_group_count: int = Field(default=2, ge=1, le=3)
    minimum_group_monotonic_fraction: float = Field(default=0.60, ge=0, le=1)

    @model_validator(mode="after")
    def validate_thresholds(self) -> TierLocalizationThresholds:
        if self.boundary_probability_lower >= self.boundary_probability_upper:
            raise ValueError("tier-localization probability interval is empty")
        return self
