from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.hashing import canonical_hash


class FinancePilotConfig(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    pilot_id: str = "finance_synthesis_pilot.small.v1"
    evidence_scan_limit: int = Field(default=20_000, ge=0)
    evidence_sample_size: int = Field(default=20_000, ge=100)
    stratum_reservoir_size: int = Field(default=2_500, ge=10)
    distractors_per_task: int = Field(default=6, ge=1, le=20)
    hard_distractors_per_task: int = Field(default=7, ge=1, le=20)
    hard_distractor_types: tuple[str, ...] = (
        "wrong_definition",
        "stale_version",
        "forecast",
        "lower_authority",
        "unit_mismatch",
        "currency_mismatch",
        "wrong_scope",
    )
    task_quotas: dict[str, int] = Field(
        default_factory=lambda: {
            "fact_retrieval": 6,
            "comparison": 6,
            "temporal_growth": 6,
            "temporal_average": 6,
        }
    )
    mutation_types: tuple[str, ...] = (
        "missing_evidence",
        "wrong_entity",
        "time_shift",
        "predicate_mismatch",
        "arithmetic_error",
        "wrong_answer",
        "citation_mismatch",
        "unsupported_claim",
        "oracle_leakage",
        "disallowed_tool",
        "failed_step",
        "extra_result_field",
        "program_node_mismatch",
        "conflicting_calculation",
        "verification_result_mismatch",
        "claim_value_mismatch",
        "multi_error",
    )
    require_full_quota: bool = True

    @model_validator(mode="after")
    def validate_task_quotas(self) -> FinancePilotConfig:
        supported = {
            "fact_retrieval",
            "comparison",
            "temporal_growth",
            "temporal_average",
            "temporal_absolute_change",
            "registered_ratio",
            "derived_growth_comparison",
        }
        unknown = set(self.task_quotas) - supported
        if unknown:
            raise ValueError(f"unsupported pilot task types: {sorted(unknown)}")
        if not self.task_quotas or any(value < 1 for value in self.task_quotas.values()):
            raise ValueError("pilot task quotas must be positive")
        supported_distractors = {
            "wrong_definition",
            "stale_version",
            "forecast",
            "lower_authority",
            "unit_mismatch",
            "currency_mismatch",
            "wrong_scope",
        }
        unknown_distractors = set(self.hard_distractor_types) - supported_distractors
        if unknown_distractors:
            raise ValueError(f"unsupported hard distractors: {sorted(unknown_distractors)}")
        return self

    @classmethod
    def from_json(cls, path: str | Path) -> FinancePilotConfig:
        return cls.model_validate_json(Path(path).read_text(encoding="utf-8"))

    @property
    def config_hash(self) -> str:
        return canonical_hash(self, prefix="finance_pilot_config:")

    def write(self, path: Path) -> None:
        path.write_text(
            json.dumps(self.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
