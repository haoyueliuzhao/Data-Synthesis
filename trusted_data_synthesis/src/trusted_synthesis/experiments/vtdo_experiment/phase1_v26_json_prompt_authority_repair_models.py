from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.hashing import canonical_hash

SCHEMA_VERSION = "json_prompt_authority_repair.v1"
AUTHORIZED_STAGE = (
    "json_explicit_prompt_population_authoritative_exact_set_"
    "and_runner_callsite_totality_repair_preflight_only"
)
NEXT_STAGE = (
    "json_explicit_prompt_population_authority_and_runner_callsite_totality_independent_audit_only"
)


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


def make_identity(
    model_type: type[BaseModel],
    values: dict[str, Any],
    *,
    field: str,
    prefix: str,
) -> Any:
    provisional = model_type.model_construct(**{field: "pending"}, **values)
    identifier = canonical_hash(
        provisional.model_dump(mode="json", exclude={field}, warnings=False),
        prefix=prefix,
    )
    return model_type(**{field: identifier}, **values)


def validate_identity(model: BaseModel, field: str, prefix: str) -> bool:
    return getattr(model, field) == canonical_hash(
        model.model_dump(mode="json", exclude={field}, warnings=False),
        prefix=prefix,
    )


class FileBinding(FrozenModel):
    relative_path: str = Field(min_length=1)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    byte_count: int = Field(ge=0)
    source_kind: Literal[
        "v26_192_transitive_source",
        "v26_192_formal_artifact",
        "v26_193_source",
        "v26_193_formal_artifact",
    ]


class ExternalAuditAuthorization(FrozenModel):
    authorization_id: str = Field(min_length=1)
    audit_sha256: Literal["35ff5c6f064dafbe604eb3cf24eb99942ee6f714424c77e3582c73d3c9ad3546"]
    audit_byte_count: Literal[22168] = 22168
    consumed_stage: Literal[
        "json_explicit_prompt_population_authoritative_exact_set_"
        "and_runner_callsite_totality_repair_preflight_only"
    ] = (
        "json_explicit_prompt_population_authoritative_exact_set_"
        "and_runner_callsite_totality_repair_preflight_only"
    )
    v26_192_decision: Literal[
        "json_explicit_prompt_local_constructibility_passed_but_"
        "prompt_population_and_parent_authority_failed"
    ] = (
        "json_explicit_prompt_local_constructibility_passed_but_"
        "prompt_population_and_parent_authority_failed"
    )
    provider_calls_authorized: Literal[False] = False
    online_execution_authorized: Literal[False] = False
    historical_rewrite_authorized: Literal[False] = False
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_authorization(self) -> ExternalAuditAuthorization:
        if not validate_identity(
            self,
            "authorization_id",
            "finance_v26_193_external_authorization:",
        ):
            raise ValueError("v26.193 external authorization identity differs")
        return self


class SourceProjectionAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    authorization_id: str = Field(min_length=1)
    audited_v26_192_source_commit: Literal["281abb8a2eb12434a6ade981c2a6b35b5951d98a"]
    audited_v26_192_source_tree: Literal["d1bf6b2f165875348e6e9bcdc54492ffa07cfc84"]
    audited_source_archive_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    audited_source_archive_byte_count: int = Field(gt=0)
    current_source_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    current_source_tree: str = Field(pattern=r"^[0-9a-f]{40}$")
    current_source_archive_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    current_source_archive_byte_count: int = Field(gt=0)
    transitive_source_files: tuple[FileBinding, ...] = Field(min_length=1)
    transitive_source_file_count: int = Field(gt=0)
    v26_192_formal_files: tuple[FileBinding, ...] = Field(min_length=17, max_length=17)
    v26_192_formal_file_count: Literal[17] = 17
    v26_192_byte_match_count: Literal[17] = 17
    v26_192_mismatch_count: Literal[0] = 0
    caller_supplied_source_identity_trusted: Literal[False] = False
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_source(self) -> SourceProjectionAudit:
        if self.transitive_source_file_count != len(self.transitive_source_files):
            raise ValueError("v26.192 transitive source count differs")
        paths = tuple(item.relative_path for item in self.transitive_source_files)
        if paths != tuple(sorted(paths)) or len(set(paths)) != len(paths):
            raise ValueError("v26.192 transitive source manifest is not canonical")
        formal = tuple(item.relative_path for item in self.v26_192_formal_files)
        if formal != tuple(sorted(formal)) or len(set(formal)) != 17:
            raise ValueError("v26.192 formal replay manifest is not exact")
        if not validate_identity(
            self,
            "audit_id",
            "finance_v26_193_source_projection_audit:",
        ):
            raise ValueError("v26.193 source projection identity differs")
        return self


class ParentAuthorityAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    source_projection_id: str = Field(min_length=1)
    runner_package_catalog_id: str = Field(min_length=1)
    manifest_id: str = Field(min_length=1)
    runner_id: str = Field(min_length=1)
    source_job_count: Literal[192] = 192
    fresh_job_count: Literal[192] = 192
    source_runner_package_count: Literal[32] = 32
    fresh_runner_package_count: Literal[32] = 32
    package_source_parent_match_count: Literal[32] = 32
    package_schedule_parent_match_count: Literal[32] = 32
    job_source_parent_match_count: Literal[192] = 192
    job_package_parent_match_count: Literal[192] = 192
    job_schedule_parent_match_count: Literal[192] = 192
    job_namespace_parent_match_count: Literal[192] = 192
    exact_source_job_set_match: Literal[True] = True
    exact_package_replica_cell_set_match: Literal[True] = True
    manifest_parent_match: Literal[True] = True
    runner_parent_match: Literal[True] = True
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> ParentAuthorityAudit:
        if not validate_identity(
            self,
            "audit_id",
            "finance_v26_193_parent_authority_audit:",
        ):
            raise ValueError("v26.193 parent authority identity differs")
        return self


PromptPhase = Literal["first_action", "subsequent_action", "correction", "final"]
PromptKind = Literal["action", "correction", "final"]


class PromptCoordinate(FrozenModel):
    coordinate_id: str = Field(min_length=1)
    fresh_job_id: str = Field(min_length=1)
    source_job_id: str = Field(min_length=1)
    runner_package_id: str = Field(min_length=1)
    source_runner_package_id: str = Field(min_length=1)
    replica_index: int = Field(ge=0, le=5)
    invocation_index: int = Field(ge=0, le=9)
    phase: PromptPhase
    prompt_kind: PromptKind
    component_index: int | None = Field(default=None, ge=0, le=3)
    component_key: str | None = None
    schedule_id: str | None = None
    state_token: str = Field(min_length=1)
    expected_prompt_core_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    rejected_action_id: str | None = None
    rejection_receipt_id: str | None = None
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_coordinate(self) -> PromptCoordinate:
        if self.phase == "final" and self.prompt_kind != "final":
            raise ValueError("Final coordinate does not use the Final Prompt kind")
        if self.phase in {"first_action", "subsequent_action"} and self.prompt_kind != "action":
            raise ValueError("Action coordinate does not use the Action Prompt kind")
        if self.phase == "first_action" and self.component_index != 0:
            raise ValueError("first Action coordinate is not Component zero")
        if self.phase == "subsequent_action" and (
            self.component_index is None or self.component_index == 0
        ):
            raise ValueError("subsequent Action coordinate lacks a later Component")
        if self.phase == "final":
            if any(
                value is not None
                for value in (
                    self.component_index,
                    self.component_key,
                    self.schedule_id,
                    self.rejected_action_id,
                    self.rejection_receipt_id,
                )
            ):
                raise ValueError("Final coordinate carries Component state")
        elif any(
            value is None for value in (self.component_index, self.component_key, self.schedule_id)
        ):
            raise ValueError("Action coordinate lacks an exact Component parent")
        if self.phase == "correction":
            if self.prompt_kind != "correction" or any(
                value is None for value in (self.rejected_action_id, self.rejection_receipt_id)
            ):
                raise ValueError("Correction coordinate lacks its typed rejection parent")
        elif self.prompt_kind == "correction" or any(
            value is not None for value in (self.rejected_action_id, self.rejection_receipt_id)
        ):
            raise ValueError("non-Correction coordinate carries a rejection parent")
        if not validate_identity(
            self,
            "coordinate_id",
            "json_explicit_prompt_coordinate:",
        ):
            raise ValueError("Prompt coordinate identity differs")
        return self


class ProviderRequestEvidenceRow(FrozenModel):
    row_id: str = Field(min_length=1)
    coordinate: PromptCoordinate
    prompt_contract_id: str = Field(min_length=1)
    prompt_schema_id: str = Field(min_length=1)
    generation_profile_id: str = Field(min_length=1)
    rendered_prompt: str = Field(min_length=1)
    prompt_core_canonical_json: str = Field(min_length=1)
    request_body_canonical_json: str = Field(min_length=1)
    rendered_prompt_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    prompt_core_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    request_body_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    request_body_byte_count: int = Field(gt=0)
    invocation_event_sequence: tuple[Literal["render", "body", "validate", "sink"], ...] = (
        "render",
        "body",
        "validate",
        "sink",
    )
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_row(self) -> ProviderRequestEvidenceRow:
        if not validate_identity(
            self,
            "row_id",
            "json_explicit_provider_request_evidence_row:",
        ):
            raise ValueError("Provider request evidence row identity differs")
        return self


class ExactPromptEvidenceSet(FrozenModel):
    evidence_set_id: str = Field(min_length=1)
    manifest_id: str = Field(min_length=1)
    runner_id: str = Field(min_length=1)
    runner_package_catalog_id: str = Field(min_length=1)
    expected_coordinate_set_id: str = Field(min_length=1)
    expected_coordinate_ids: tuple[str, ...] = Field(min_length=792, max_length=792)
    rows: tuple[ProviderRequestEvidenceRow, ...] = Field(min_length=792, max_length=792)
    exact_job_count: Literal[192] = 192
    row_count: Literal[792] = 792
    unique_row_count: Literal[792] = 792
    unique_coordinate_count: Literal[792] = 792
    first_action_count: Literal[192] = 192
    subsequent_action_count: Literal[288] = 288
    correction_count: Literal[120] = 120
    final_count: Literal[192] = 192
    request_body_reparse_count: Literal[792] = 792
    exact_request_body_match_count: Literal[792] = 792
    exact_prompt_core_match_count: Literal[792] = 792
    exact_parent_coordinate_match_count: Literal[792] = 792
    complete_model_reachable_state_census_claimed: Literal[False] = False
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_set(self) -> ExactPromptEvidenceSet:
        row_ids = tuple(item.row_id for item in self.rows)
        coordinates = tuple(item.coordinate.coordinate_id for item in self.rows)
        if len(set(row_ids)) != self.unique_row_count:
            raise ValueError("Prompt evidence set repeats a row")
        if len(set(coordinates)) != self.unique_coordinate_count:
            raise ValueError("Prompt evidence set repeats a coordinate")
        if self.expected_coordinate_ids != tuple(sorted(coordinates)):
            raise ValueError("Prompt evidence set coordinate set differs")
        expected_set_id = canonical_hash(
            self.expected_coordinate_ids,
            prefix="json_explicit_expected_prompt_coordinate_set:",
        )
        if self.expected_coordinate_set_id != expected_set_id:
            raise ValueError("expected Prompt coordinate set identity differs")
        phases = {
            phase: 0 for phase in ("first_action", "subsequent_action", "correction", "final")
        }
        for row in self.rows:
            phases[row.coordinate.phase] += 1
        if phases != {
            "first_action": self.first_action_count,
            "subsequent_action": self.subsequent_action_count,
            "correction": self.correction_count,
            "final": self.final_count,
        }:
            raise ValueError("Prompt evidence phase denominator differs")
        if not validate_identity(
            self,
            "evidence_set_id",
            "json_explicit_exact_prompt_evidence_set:",
        ):
            raise ValueError("exact Prompt evidence-set identity differs")
        return self


class RunnerCallsiteTotalityAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    runner_id: str = Field(min_length=1)
    runner_source_relative_path: str = Field(min_length=1)
    runner_source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    invoke_method_count: Literal[1] = 1
    renderer_callsite_count: Literal[1] = 1
    request_body_builder_callsite_count: Literal[1] = 1
    transport_sink_callsite_count: Literal[1] = 1
    action_route_count: Literal[1] = 1
    correction_route_count: Literal[1] = 1
    final_route_count: Literal[1] = 1
    direct_provider_client_constructor_count: Literal[0] = 0
    network_library_callsite_count: Literal[0] = 0
    bypass_callsite_count: Literal[0] = 0
    renderer_precedes_request_body_callsite: Literal[True] = True
    request_body_precedes_transport_sink_callsite: Literal[True] = True
    local_invocation_count: Literal[792] = 792
    rendered_before_request_body_count: Literal[792] = 792
    request_body_validated_before_sink_count: Literal[792] = 792
    accepted_prefix_trajectory_parent_count: Literal[4632] = 4632
    accepted_prefix_state_parent_count: Literal[14388] = 14388
    accepted_prefix_candidate_evaluation_parent_count: Literal[41124] = 41124
    reachability_basis: Literal["source_callsite_totality_not_792_row_exhaustion"] = (
        "source_callsite_totality_not_792_row_exhaustion"
    )
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> RunnerCallsiteTotalityAudit:
        if not validate_identity(
            self,
            "audit_id",
            "finance_v26_193_runner_callsite_totality_audit:",
        ):
            raise ValueError("Runner callsite totality identity differs")
        return self


class TypedAttackResult(FrozenModel):
    attack_id: str = Field(min_length=1)
    attack_name: str = Field(min_length=1)
    expected_exception_type: str = Field(min_length=1)
    actual_exception_type: str = Field(min_length=1)
    expected_stage: str = Field(min_length=1)
    actual_stage: str = Field(min_length=1)
    expected_reason: str = Field(min_length=1)
    actual_reason: str = Field(min_length=1)
    target_validator_reached: Literal[True] = True
    fully_rehashed: Literal[True] = True
    rejected: Literal[True] = True
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_result(self) -> TypedAttackResult:
        if (
            self.actual_exception_type != self.expected_exception_type
            or self.actual_stage != self.expected_stage
            or self.actual_reason != self.expected_reason
        ):
            raise ValueError("typed attack rejected at an unexpected boundary")
        if not validate_identity(self, "attack_id", "json_prompt_typed_attack_result:"):
            raise ValueError("typed attack identity differs")
        return self


class TypedDestructiveAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    attacks: tuple[TypedAttackResult, ...] = Field(min_length=14, max_length=14)
    attempted_count: Literal[14] = 14
    rejected_count: Literal[14] = 14
    accepted_count: Literal[0] = 0
    exact_type_match_count: Literal[14] = 14
    exact_stage_match_count: Literal[14] = 14
    exact_reason_match_count: Literal[14] = 14
    target_validator_reached_count: Literal[14] = 14
    fully_rehashed_count: Literal[14] = 14
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> TypedDestructiveAudit:
        names = tuple(item.attack_name for item in self.attacks)
        if len(set(names)) != self.attempted_count:
            raise ValueError("typed destructive audit repeats an attack")
        if not validate_identity(
            self,
            "audit_id",
            "finance_v26_193_typed_destructive_audit:",
        ):
            raise ValueError("typed destructive audit identity differs")
        return self


class FieldDifferenceWitness(FrozenModel):
    json_path: str = Field(min_length=1)
    old_present: bool
    new_present: bool
    old_canonical_json: str = Field(min_length=1)
    new_canonical_json: str = Field(min_length=1)
    old_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    new_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    classification: Literal[
        "content_identity",
        "parent_identity",
        "semantic_event_or_receipt",
        "semantic_validity_or_answer",
        "other",
    ]

    @model_validator(mode="after")
    def validate_presence(self) -> FieldDifferenceWitness:
        if not self.old_present and not self.new_present:
            raise ValueError("field difference cannot be absent on both sides")
        return self


class ResultDriftWitness(FrozenModel):
    witness_id: str = Field(min_length=1)
    fresh_job_id: str = Field(min_length=1)
    source_job_id: str = Field(min_length=1)
    capability_family: Literal["semantic_reconciliation"] = "semantic_reconciliation"
    replica_index: int = Field(ge=0, le=5)
    old_result_id: str = Field(min_length=1)
    snapshot_result_id: str = Field(min_length=1)
    new_result_id: str = Field(min_length=1)
    snapshot_matches_old_canonical_bytes: bool
    snapshot_matches_current_canonical_bytes: bool
    old_result_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    new_result_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    old_result_byte_count: int = Field(gt=0)
    new_result_byte_count: int = Field(gt=0)
    differences: tuple[FieldDifferenceWitness, ...] = Field(min_length=1)
    changed_field_count: int = Field(gt=0)
    first_changed_path: str = Field(min_length=1)
    semantic_event_or_receipt_difference: bool
    semantic_validity_or_answer_difference: bool
    historical_result_mutated: Literal[False] = False
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_witness(self) -> ResultDriftWitness:
        if self.changed_field_count != len(self.differences):
            raise ValueError("Result drift witness field count differs")
        paths = tuple(item.json_path for item in self.differences)
        if paths != tuple(sorted(paths)) or self.first_changed_path != paths[0]:
            raise ValueError("Result drift witness paths are not canonical")
        if not validate_identity(self, "witness_id", "json_prompt_result_drift_witness:"):
            raise ValueError("Result drift witness identity differs")
        return self


class ResultDriftDecompositionAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    manifest_id: str = Field(min_length=1)
    compared_result_count: Literal[192] = 192
    exact_identity_match_count: Literal[144] = 144
    identity_drift_count: Literal[48] = 48
    witness_count: Literal[48] = 48
    historical_catalog_sha256: Literal[
        "51ed5b6344aa19cd3d51ab01d85e30a1b40d8b7fef04dc2ae04c7383b950bd95"
    ]
    v179_source_commit: Literal["27ac98d03d078d522cecf7a0cb290230cac63036"]
    v179_source_tree: Literal["e2c46cd3735aa0ea090c852f1290a8e978b2b3c8"]
    v179_source_archive_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    v179_source_archive_byte_count: int = Field(gt=0)
    v179_snapshot_replay_count: Literal[192] = 192
    v179_snapshot_old_byte_match_count: Literal[192] = 192
    v179_snapshot_current_byte_match_count: Literal[144] = 144
    witnesses: tuple[ResultDriftWitness, ...] = Field(min_length=48, max_length=48)
    semantic_event_or_receipt_drift_count: int = Field(ge=0, le=48)
    semantic_validity_or_answer_drift_count: int = Field(ge=0, le=48)
    json_envelope_causal_count: Literal[0] = 0
    historical_result_rewrite_count: Literal[0] = 0
    online_execution_blocked_by_drift_if_semantic: bool
    online_execution_blocked_by_unknown_or_semantic_drift: Literal[True] = True
    semantic_equivalence_claimed: Literal[False] = False
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> ResultDriftDecompositionAudit:
        if len({item.source_job_id for item in self.witnesses}) != self.witness_count:
            raise ValueError("Result drift audit repeats a source Job")
        semantic = sum(item.semantic_event_or_receipt_difference for item in self.witnesses)
        validity = sum(item.semantic_validity_or_answer_difference for item in self.witnesses)
        if (
            semantic != self.semantic_event_or_receipt_drift_count
            or validity != self.semantic_validity_or_answer_drift_count
            or self.online_execution_blocked_by_drift_if_semantic != bool(semantic or validity)
            or self.semantic_equivalence_claimed
        ):
            raise ValueError("Result drift safety projection differs")
        if not validate_identity(
            self,
            "audit_id",
            "finance_v26_193_result_drift_decomposition_audit:",
        ):
            raise ValueError("Result drift decomposition identity differs")
        return self


class OutcomeAuthorityGapRegister(FrozenModel):
    register_id: str = Field(min_length=1)
    manifest_id: str = Field(min_length=1)
    runner_id: str = Field(min_length=1)
    required_layers: tuple[str, ...] = (
        "fresh_terminal_registry_binding",
        "fresh_raw_execution_descriptor_contract",
        "fresh_job_result_descriptor_contract",
        "fresh_job_bound_attempt_trace_contract",
        "fresh_outcome_row_contract",
        "fresh_exact_evidence_set_evaluator",
    )
    materialized_layers: tuple[str, ...] = ()
    missing_layer_count: Literal[6] = 6
    old_v26_186_contract_reused: Literal[False] = False
    empirical_rows: Literal[0] = 0
    online_execution_authority: Literal[False] = False
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_register(self) -> OutcomeAuthorityGapRegister:
        if self.missing_layer_count != len(self.required_layers) - len(self.materialized_layers):
            raise ValueError("fresh Outcome authority gap count differs")
        if not validate_identity(
            self,
            "register_id",
            "finance_v26_193_outcome_authority_gap_register:",
        ):
            raise ValueError("Outcome authority gap Register identity differs")
        return self


class StaticGate(FrozenModel):
    gate_id: str = Field(min_length=1)
    gate_name: str = Field(min_length=1)
    passed: bool
    evidence_ids: tuple[str, ...] = Field(min_length=1)
    evidence_count: int = Field(gt=0)
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_gate(self) -> StaticGate:
        if self.evidence_count != len(self.evidence_ids):
            raise ValueError("static Gate evidence count differs")
        if not validate_identity(self, "gate_id", "json_prompt_authority_static_gate:"):
            raise ValueError("static Gate identity differs")
        return self


class StaticAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    gates: tuple[StaticGate, ...] = Field(min_length=20)
    gate_count: int = Field(ge=20)
    passed_gate_count: int = Field(ge=0)
    failed_gate_count: int = Field(ge=0)
    repair_preflight_gates_passed: bool
    online_execution_gate_passed: Literal[False] = False
    provider_calls: Literal[0] = 0
    credentials_read: Literal[0] = 0
    gpu_jobs: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> StaticAudit:
        if self.gate_count != len(self.gates):
            raise ValueError("static Gate denominator differs")
        passed = sum(item.passed for item in self.gates)
        if (
            passed != self.passed_gate_count
            or self.failed_gate_count != self.gate_count - passed
            or self.repair_preflight_gates_passed != (passed == self.gate_count)
        ):
            raise ValueError("static Gate aggregate differs")
        if not validate_identity(self, "audit_id", "finance_v26_193_static_audit:"):
            raise ValueError("v26.193 static Audit identity differs")
        return self


class ProspectiveTransition(FrozenModel):
    transition_id: str = Field(min_length=1)
    current_stage: str = AUTHORIZED_STAGE
    repair_preflight_gates_passed: bool
    next_stage: str = NEXT_STAGE
    independent_audit_required: Literal[True] = True
    online_development_execution_authorized: Literal[False] = False
    fresh_outcome_authority_complete: Literal[False] = False
    historical_rewrite_authorized: Literal[False] = False
    capability_estimate_authorized: Literal[False] = False
    mapper_state_frequency_contribution_vtdo_authorized: Literal[False] = False
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_transition(self) -> ProspectiveTransition:
        if not validate_identity(
            self,
            "transition_id",
            "finance_v26_193_prompt_authority_transition:",
        ):
            raise ValueError("v26.193 Transition identity differs")
        return self


class ArtifactManifest(FrozenModel):
    manifest_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    members: tuple[FileBinding, ...] = Field(min_length=1)
    file_count: int = Field(gt=0)
    total_byte_count: int = Field(gt=0)
    artifact_root: str = Field(min_length=1)
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_manifest(self) -> ArtifactManifest:
        paths = tuple(item.relative_path for item in self.members)
        if paths != tuple(sorted(paths)) or len(set(paths)) != len(paths):
            raise ValueError("artifact Manifest members are not canonical")
        if self.file_count != len(self.members):
            raise ValueError("artifact Manifest file count differs")
        if self.total_byte_count != sum(item.byte_count for item in self.members):
            raise ValueError("artifact Manifest byte count differs")
        root = canonical_hash(self.members, prefix="finance_v26_193_artifact_root:")
        if self.artifact_root != root:
            raise ValueError("artifact Root differs")
        if not validate_identity(
            self,
            "manifest_id",
            "finance_v26_193_artifact_manifest:",
        ):
            raise ValueError("artifact Manifest identity differs")
        return self


class RepairReport(FrozenModel):
    report_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    authorization_id: str = Field(min_length=1)
    source_projection_id: str = Field(min_length=1)
    parent_authority_id: str = Field(min_length=1)
    prompt_evidence_set_id: str = Field(min_length=1)
    runner_callsite_totality_id: str = Field(min_length=1)
    typed_destructive_audit_id: str = Field(min_length=1)
    result_drift_audit_id: str = Field(min_length=1)
    outcome_authority_gap_register_id: str = Field(min_length=1)
    static_audit_id: str = Field(min_length=1)
    transition_id: str = Field(min_length=1)
    v26_192_formal_files_rebuilt: Literal[17] = 17
    exact_fresh_job_count: Literal[192] = 192
    exact_prompt_evidence_row_count: Literal[792] = 792
    complete_model_reachable_prompt_census_claimed: Literal[False] = False
    runner_callsite_totality_passed: Literal[True] = True
    typed_attack_count: Literal[14] = 14
    typed_attack_rejection_count: Literal[14] = 14
    result_identity_match_count: Literal[144] = 144
    result_identity_drift_count: Literal[48] = 48
    result_semantic_equivalence_claimed: bool
    repair_preflight_gates_passed: bool
    online_execution_gate_passed: Literal[False] = False
    online_development_execution_authorized: Literal[False] = False
    provider_calls: Literal[0] = 0
    development_model_outcomes: Literal[0] = 0
    historical_outcome_reclassification_count: Literal[0] = 0
    mapper_rows: Literal[0] = 0
    state_rows: Literal[0] = 0
    frequency_rows: Literal[0] = 0
    contribution_rows: Literal[0] = 0
    vtdo_rows: Literal[0] = 0
    training_rows: Literal[0] = 0
    next_stage: str = NEXT_STAGE
    decision: Literal[
        "prompt_population_parent_authority_and_callsite_totality_repair_preflight_passed_"
        "online_remains_blocked"
    ] = (
        "prompt_population_parent_authority_and_callsite_totality_repair_preflight_passed_"
        "online_remains_blocked"
    )
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_report(self) -> RepairReport:
        if not validate_identity(
            self,
            "report_id",
            "finance_v26_193_prompt_authority_repair_report:",
        ):
            raise ValueError("v26.193 Report identity differs")
        return self


__all__ = [
    "AUTHORIZED_STAGE",
    "NEXT_STAGE",
    "ArtifactManifest",
    "ExactPromptEvidenceSet",
    "ExternalAuditAuthorization",
    "FieldDifferenceWitness",
    "FileBinding",
    "FrozenModel",
    "OutcomeAuthorityGapRegister",
    "ParentAuthorityAudit",
    "PromptCoordinate",
    "ProviderRequestEvidenceRow",
    "RepairReport",
    "ResultDriftDecompositionAudit",
    "ResultDriftWitness",
    "RunnerCallsiteTotalityAudit",
    "SourceProjectionAudit",
    "StaticAudit",
    "StaticGate",
    "TypedAttackResult",
    "TypedDestructiveAudit",
    "make_identity",
]
