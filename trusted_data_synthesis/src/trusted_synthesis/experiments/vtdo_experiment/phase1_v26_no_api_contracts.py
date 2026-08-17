from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_fresh_population import (
    FRESHNESS_CHANNELS,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_stage_router import V26Stage
from trusted_synthesis.hashing import canonical_hash

V26_NO_API_EXPERIMENT_VERSION = "finance_v26_no_api_joint_scaffold.v1"


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class V26ImmutableFileRecord(FrozenModel):
    relative_path: str = Field(min_length=1)
    sha256: str = Field(min_length=64, max_length=64)
    byte_count: int = Field(ge=1)


class V26CredentialFreeReplayObservation(FrozenModel):
    command: tuple[str, ...] = Field(min_length=1)
    credential_like_environment_key_count: Literal[0] = 0
    cuda_visible_devices: Literal[""] = ""
    return_code: Literal[0] = 0
    replayed_ledger_id: str = Field(min_length=1)
    replayed_next_stage: Literal["bridge_rollout"] = "bridge_rollout"
    model_api_calls: Literal[0] = 0
    gpu_jobs: Literal[0] = 0


class V26NoApiExperimentReport(FrozenModel):
    report_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    protocol_id: str = Field(min_length=1)
    development_population_id: str = Field(min_length=1)
    confirmation_population_id: str = Field(min_length=1)
    freshness_audit_id: str = Field(min_length=1)
    freshness_overlap_count_by_channel: dict[str, Literal[0]]
    joint_compilation_count: Literal[24] = 24
    trajectory_state_space_count: Literal[24] = 24
    joint_audit_evidence_count: Literal[72] = 72
    joint_atomic_case_count: int = Field(ge=1)
    joint_admission_count: Literal[24] = 24
    scaffold_ladder_count: Literal[24] = 24
    scaffold_gate_evidence_count: Literal[672] = 672
    scaffold_atomic_case_count: int = Field(ge=1)
    scaffold_admission_count: Literal[24] = 24
    history_collision_case_count: Literal[96] = 96
    cross_level_mapping_case_count: Literal[96] = 96
    bridge_static_audit_count: Literal[3] = 3
    bridge_static_atomic_case_count: Literal[144] = 144
    bridge_development_authorization_id: str = Field(min_length=1)
    final_ledger_id: str = Field(min_length=1)
    completed_stages: tuple[V26Stage, ...]
    next_stage: Literal["bridge_rollout"] = "bridge_rollout"
    credential_free_replay: V26CredentialFreeReplayObservation
    immutable_files: tuple[V26ImmutableFileRecord, ...] = Field(min_length=1)
    model_api_calls: Literal[0] = 0
    gpu_jobs: Literal[0] = 0
    status: Literal["passed"] = "passed"
    schema_version: Literal["finance_v26_no_api_joint_scaffold.v1"] = (
        "finance_v26_no_api_joint_scaffold.v1"
    )

    @model_validator(mode="after")
    def validate_report(self) -> V26NoApiExperimentReport:
        if set(self.freshness_overlap_count_by_channel) != set(FRESHNESS_CHANNELS):
            raise ValueError("v26 no-API report freshness channels are incomplete")
        if any(self.freshness_overlap_count_by_channel.values()):
            raise ValueError("v26 no-API report contains a freshness overlap")
        expected_stages: tuple[V26Stage, ...] = (
            "fresh_task_population",
            "joint_compilation",
            "joint_audit",
            "joint_admission",
            "scaffold_compilation",
            "scaffold_audit",
            "scaffold_admission",
            "bridge_development_authorization",
        )
        if self.completed_stages != expected_stages:
            raise ValueError("v26 no-API report did not complete the frozen stage prefix")
        if self.report_id != v26_no_api_experiment_report_id(self):
            raise ValueError("v26 no-API experiment report identity is invalid")
        return self


def v26_no_api_experiment_report_id(value: V26NoApiExperimentReport) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"report_id"}),
        prefix="finance_v26_no_api_joint_scaffold_report:",
    )
