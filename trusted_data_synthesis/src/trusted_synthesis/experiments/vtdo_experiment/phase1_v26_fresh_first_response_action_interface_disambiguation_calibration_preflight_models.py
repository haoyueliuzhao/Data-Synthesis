from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from typing import Any, Final, Literal, cast

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.hashing import canonical_hash

SCHEMA_VERSION: Final = (
    "fresh_first_response_action_interface_disambiguation_calibration_preflight.v1"
)
CONSUMED_STAGE: Final = (
    "fresh_first_response_action_interface_disambiguation_and_stratified_"
    "calibration_population_preflight_only"
)
NEXT_DECISION: Final = "no_online_calibration_authorized_without_new_external_audit_decision"
PLANNED_ONLINE_STAGE: Final = (
    "fresh_first_response_action_interface_disambiguation_paired_24_call_online_calibration_only"
)

Arm = Literal["C", "R"]
SchemaFamily = Literal["comparison", "scalar_value"]
DepthBand = Literal["lower", "higher"]
SelectionPosition = Literal["short", "median", "long"]
EvidenceKind = Literal["scripted_preflight_control", "empirical_calibration"]


class FrozenModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


def identity(value: BaseModel, field: str, prefix: str) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={field}, warnings=False),
        prefix=prefix,
    )


def make_identity(
    model_type: type[BaseModel],
    values: dict[str, Any],
    *,
    field: str,
    prefix: str,
) -> Any:
    provisional = model_type.model_construct(**{field: "pending"}, **values)
    return model_type(**{field: identity(provisional, field, prefix)}, **values)


def canonical_sha256(value: Any) -> str:
    if isinstance(value, BaseModel):
        value = value.model_dump(mode="json", warnings=False)
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


class ExternalAuditAuthorization(FrozenModel):
    authorization_id: str = Field(min_length=1)
    audit_sha256: Literal["1c3009fc757fed7ea92aa8d522efb0bc9bf91ce3660d2da11e8d526c3c088795"]
    audit_byte_count: Literal[15697] = 15_697
    revision_decision: Literal["v26_201_retrospective_interpretation_revision_accepted"]
    consumed_stage: Literal[
        "fresh_first_response_action_interface_disambiguation_and_stratified_"
        "calibration_population_preflight_only"
    ] = CONSUMED_STAGE
    population_preflight_authorized: Literal[True] = True
    provider_calls_authorized: Literal[False] = False
    historical_job_rerun_authorized: Literal[False] = False
    historical_response_adaptation_authorized: Literal[False] = False
    parser_relaxation_authorized: Literal[False] = False
    qa_mapper_state_contribution_vtdo_authorized: Literal[False] = False
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_authorization(self) -> ExternalAuditAuthorization:
        if self.authorization_id != identity(
            self,
            "authorization_id",
            "finance_v26_203_external_audit_authorization:",
        ):
            raise ValueError("v26.203 external Audit authorization identity differs")
        return self


class V202Freeze(FrozenModel):
    freeze_id: str = Field(min_length=1)
    authorization_id: str = Field(min_length=1)
    v202_decision_id: str = Field(min_length=1)
    v202_transition_id: str = Field(min_length=1)
    v202_evaluation_id: str = Field(min_length=1)
    v202_localization_id: str = Field(min_length=1)
    v202_artifact_manifest_id: str = Field(min_length=1)
    v202_artifact_root: str = Field(min_length=1)
    v202_source_commit: Literal["a4508dc1c896cb13533f2838d3d74d08d75a40ef"]
    v202_source_tree: Literal["6fb1bf2ee025ed4db1a6910b5500626e1ac3d09f"]
    formal_file_count: Literal[11] = 11
    formal_total_byte_count: Literal[674872] = 674_872
    q_first_fraction: Literal["0/192"] = "0/192"
    q_bounded_correction_fraction: Literal["0/192"] = "0/192"
    post_action_abi_denominator: Literal[0] = 0
    structural_interface_ambiguity_confirmed: Literal[True] = True
    causal_attribution_proven: Literal[False] = False
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_freeze(self) -> V202Freeze:
        if self.freeze_id != identity(self, "freeze_id", "finance_v26_203_v202_freeze:"):
            raise ValueError("v26.203 v26.202 Freeze identity differs")
        return self


class ExactActionInterfaceContract(FrozenModel):
    contract_id: str = Field(min_length=1)
    authorization_id: str = Field(min_length=1)
    v202_freeze_id: str = Field(min_length=1)
    frozen_action_grammar_id: str = Field(min_length=1)
    frozen_parser_source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    frozen_grammar_source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    field_order: tuple[str, str, str, str] = (
        "state_id",
        "action_id",
        "decision_kind",
        "protocol",
    )
    required_fields: tuple[str, str, str, str] = (
        "state_id",
        "action_id",
        "decision_kind",
        "protocol",
    )
    allowed_fields: tuple[str, str, str, str] = (
        "state_id",
        "action_id",
        "decision_kind",
        "protocol",
    )
    additional_properties_allowed: Literal[False] = False
    wrapper_allowed: Literal[False] = False
    exactly_one_json_object_required: Literal[True] = True
    protocol_value: Literal["prospective_semantic_action_exact_response.v1"] = (
        "prospective_semantic_action_exact_response.v1"
    )
    decision_kind_value: Literal["execute_public_operation"] = "execute_public_operation"
    grammar_id_model_visible: Literal[False] = False
    parser_unchanged: Literal[True] = True
    parser_relaxation_allowed: Literal[False] = False
    historical_payload_adaptation_allowed: Literal[False] = False
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_contract(self) -> ExactActionInterfaceContract:
        expected = ("state_id", "action_id", "decision_kind", "protocol")
        if (
            self.field_order != expected
            or self.required_fields != expected
            or self.allowed_fields != expected
        ):
            raise ValueError("v26.203 exact four-field Action contract differs")
        if self.contract_id != identity(
            self,
            "contract_id",
            "fresh_first_response_exact_action_interface_contract:",
        ):
            raise ValueError("v26.203 Action-interface Contract identity differs")
        return self


class InterfaceProfile(FrozenModel):
    profile_id: str = Field(min_length=1)
    contract_id: str = Field(min_length=1)
    arm: Arm
    name: Literal["contemporaneous_control", "disambiguated_action_interface"]
    message_roles: tuple[Literal["system", "user"], ...] = Field(min_length=1, max_length=2)
    source_prompt_bytes_exact: bool
    authoritative_system_contract_present: bool
    old_response_abi_visible: bool
    action_id_inside_authoritative_contract: bool
    answer_and_operation_semantics_retained: Literal[True] = True
    answer_and_operation_fields_marked_nonresponse: bool
    grammar_id_host_side_only: bool
    parser_changed: Literal[False] = False
    task_state_candidate_semantics_changed: Literal[False] = False
    composite_interface_repair_package: bool
    submechanism_attribution_authorized: Literal[False] = False
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_profile(self) -> InterfaceProfile:
        if self.arm == "C":
            expected = (
                self.name == "contemporaneous_control"
                and self.message_roles == ("user",)
                and self.source_prompt_bytes_exact
                and not self.authoritative_system_contract_present
                and self.old_response_abi_visible
                and not self.action_id_inside_authoritative_contract
                and not self.answer_and_operation_fields_marked_nonresponse
                and not self.grammar_id_host_side_only
                and not self.composite_interface_repair_package
            )
        else:
            expected = (
                self.name == "disambiguated_action_interface"
                and self.message_roles == ("system", "user")
                and not self.source_prompt_bytes_exact
                and self.authoritative_system_contract_present
                and not self.old_response_abi_visible
                and self.action_id_inside_authoritative_contract
                and self.answer_and_operation_fields_marked_nonresponse
                and self.grammar_id_host_side_only
                and self.composite_interface_repair_package
            )
        if not expected:
            raise ValueError("v26.203 interface arm profile differs")
        if self.profile_id != identity(
            self,
            "profile_id",
            "fresh_first_response_interface_profile:",
        ):
            raise ValueError("v26.203 interface Profile identity differs")
        return self


class SourceCell(FrozenModel):
    source_cell_id: str = Field(min_length=1)
    source_v200_job_id: str = Field(min_length=1)
    source_package_id: str = Field(min_length=1)
    source_runtime_job_id: str = Field(min_length=1)
    source_group_id: str = Field(min_length=1)
    capability_family: str = Field(min_length=1)
    replica_index: int = Field(ge=0, le=5)
    schedule_ids: tuple[str, ...] = Field(min_length=1)
    depth: Literal[
        "d0_observability_anchor",
        "d1_basic",
        "d2_compositional",
        "d3_stress",
    ]
    depth_band: DepthBand
    answer_schema_family: SchemaFamily
    answer_fields: tuple[str, ...] = Field(min_length=1)
    stratum_id: str = Field(min_length=1)
    stratum_size: int = Field(gt=0)
    selection_position: SelectionPosition
    selection_rank: int = Field(ge=0)
    control_prompt_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    control_prompt_byte_count: int = Field(gt=0, le=60000)
    public_task_semantic_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    current_state_semantic_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    candidate_set_order_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    current_state_id: str = Field(min_length=1)
    candidate_action_ids: tuple[str, ...] = Field(min_length=1)
    candidate_count: int = Field(gt=0)
    selection_uses_pre_response_properties_only: Literal[True] = True
    historical_response_shape_used: Literal[False] = False
    new_response_count_read: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_cell(self) -> SourceCell:
        if self.candidate_count != len(self.candidate_action_ids):
            raise ValueError("v26.203 source-cell Candidate count differs")
        if self.depth_band == "lower" and self.depth not in {
            "d0_observability_anchor",
            "d1_basic",
        }:
            raise ValueError("v26.203 lower-depth stratum differs")
        if self.depth_band == "higher" and self.depth not in {"d2_compositional", "d3_stress"}:
            raise ValueError("v26.203 higher-depth stratum differs")
        if self.source_cell_id != identity(
            self,
            "source_cell_id",
            "fresh_first_response_calibration_source_cell:",
        ):
            raise ValueError("v26.203 source Cell identity differs")
        return self


class StratifiedCalibrationPopulation(FrozenModel):
    population_id: str = Field(min_length=1)
    authorization_id: str = Field(min_length=1)
    v202_freeze_id: str = Field(min_length=1)
    cells: tuple[SourceCell, ...] = Field(min_length=12, max_length=12)
    source_cell_count: Literal[12] = 12
    stratum_count: Literal[4] = 4
    cells_per_stratum: Literal[3] = 3
    selection_rule: Literal[
        "within_answer_schema_x_depth_band_sort_prompt_bytes_package_replica_job_"
        "select_first_middle_last"
    ]
    package_id_final_tiebreak_parent: Literal[True] = True
    selection_frozen_before_online_response: Literal[True] = True
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_population(self) -> StratifiedCalibrationPopulation:
        strata: dict[str, list[SourceCell]] = defaultdict(list)
        for item in self.cells:
            strata[item.stratum_id].append(item)
        if (
            len({item.source_cell_id for item in self.cells}) != 12
            or len({item.source_v200_job_id for item in self.cells}) != 12
            or len(strata) != 4
            or any(len(items) != 3 for items in strata.values())
            or any(
                {item.selection_position for item in items} != {"short", "median", "long"}
                for items in strata.values()
            )
        ):
            raise ValueError("v26.203 stratified Population geometry differs")
        if self.population_id != identity(
            self,
            "population_id",
            "fresh_first_response_stratified_calibration_population:",
        ):
            raise ValueError("v26.203 calibration Population identity differs")
        return self


class RequestMessage(FrozenModel):
    role: Literal["system", "user"]
    content: str = Field(min_length=1)
    content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    content_byte_count: int = Field(gt=0, le=60000)

    @model_validator(mode="after")
    def validate_message(self) -> RequestMessage:
        encoded = self.content.encode("utf-8")
        if hashlib.sha256(encoded).hexdigest() != self.content_sha256 or len(encoded) != (
            self.content_byte_count
        ):
            raise ValueError("v26.203 request Message bytes differ")
        return self


class CalibrationJob(FrozenModel):
    job_id: str = Field(min_length=1)
    pair_id: str = Field(min_length=1)
    source_cell_id: str = Field(min_length=1)
    source_v200_job_id: str = Field(min_length=1)
    arm: Arm
    interface_profile_id: str = Field(min_length=1)
    execution_order_within_pair: Literal[0, 1]
    raw_namespace: str = Field(min_length=1)
    result_namespace: str = Field(min_length=1)
    observation_namespace: str = Field(min_length=1)
    model_config_id: str = Field(min_length=1)
    model_request_config_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    thinking_policy_id: str = Field(min_length=1)
    bounded_generation_policy_id: str = Field(min_length=1)
    resource_contract_id: str = Field(min_length=1)
    public_task_semantic_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    current_state_semantic_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    candidate_set_order_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    schedule_ids: tuple[str, ...] = Field(min_length=1)
    planned_stage_one_calls: Literal[1] = 1
    planned_stage_two_calls: Literal[0] = 0
    automatic_retries: Literal[0] = 0
    recovery_calls: Literal[0] = 0
    old_job_identity_reused: Literal[False] = False
    qa_parent_count: Literal[0] = 0
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_job(self) -> CalibrationJob:
        if self.job_id == self.source_v200_job_id:
            raise ValueError("v26.203 Calibration Job reused a v26.200 identity")
        if self.job_id != identity(
            self,
            "job_id",
            "fresh_first_response_calibration_job:",
        ):
            raise ValueError("v26.203 Calibration Job identity differs")
        return self


class FirstRequestDescriptor(FrozenModel):
    request_id: str = Field(min_length=1)
    job_id: str = Field(min_length=1)
    pair_id: str = Field(min_length=1)
    source_cell_id: str = Field(min_length=1)
    arm: Arm
    interface_profile_id: str = Field(min_length=1)
    messages: tuple[RequestMessage, ...] = Field(min_length=1, max_length=2)
    canonical_request_body_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    model_request_config_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    public_task_semantic_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    current_state_semantic_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    candidate_set_order_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    request_materialized_before_provider_access: Literal[True] = True
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_request(self) -> FirstRequestDescriptor:
        roles = tuple(item.role for item in self.messages)
        if (self.arm == "C" and roles != ("user",)) or (
            self.arm == "R" and roles != ("system", "user")
        ):
            raise ValueError("v26.203 request Message roles differ")
        if self.request_id != identity(
            self,
            "request_id",
            "fresh_first_response_request_descriptor:",
        ):
            raise ValueError("v26.203 FirstRequestDescriptor identity differs")
        return self


class CalibrationManifest(FrozenModel):
    manifest_id: str = Field(min_length=1)
    authorization_id: str = Field(min_length=1)
    population_id: str = Field(min_length=1)
    action_contract_id: str = Field(min_length=1)
    interface_profile_ids: tuple[str, str]
    jobs: tuple[CalibrationJob, ...] = Field(min_length=24, max_length=24)
    requests: tuple[FirstRequestDescriptor, ...] = Field(min_length=24, max_length=24)
    expected_job_ids: tuple[str, ...] = Field(min_length=24, max_length=24)
    expected_request_ids: tuple[str, ...] = Field(min_length=24, max_length=24)
    source_cell_count: Literal[12] = 12
    arm_count: Literal[2] = 2
    job_count: Literal[24] = 24
    planned_stage_one_calls: Literal[24] = 24
    planned_stage_two_calls: Literal[0] = 0
    automatic_retries: Literal[0] = 0
    recovery_calls: Literal[0] = 0
    control_first_pair_count: Literal[6] = 6
    repair_first_pair_count: Literal[6] = 6
    provider_calls: Literal[0] = 0
    empirical_response_count: Literal[0] = 0
    empirical_observation_count: Literal[0] = 0
    empirical_evaluation_count: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_manifest(self) -> CalibrationManifest:
        requests = {item.job_id: item for item in self.requests}
        by_cell: dict[str, list[CalibrationJob]] = defaultdict(list)
        for item in self.jobs:
            by_cell[item.source_cell_id].append(item)
        namespaces = [
            value
            for item in self.jobs
            for value in (item.raw_namespace, item.result_namespace, item.observation_namespace)
        ]
        if (
            len({item.job_id for item in self.jobs}) != 24
            or len({item.request_id for item in self.requests}) != 24
            or self.expected_job_ids != tuple(sorted(item.job_id for item in self.jobs))
            or self.expected_request_ids != tuple(sorted(item.request_id for item in self.requests))
            or len(requests) != 24
            or len(namespaces) != len(set(namespaces))
            or Counter(item.arm for item in self.jobs) != Counter({"C": 12, "R": 12})
            or len(by_cell) != 12
            or any({item.arm for item in rows} != {"C", "R"} for rows in by_cell.values())
        ):
            raise ValueError("v26.203 exact 24-Job Manifest geometry differs")
        control_first = 0
        for rows in by_cell.values():
            ordered = sorted(rows, key=lambda item: item.execution_order_within_pair)
            control_first += ordered[0].arm == "C"
            left, right = rows
            if (
                left.pair_id != right.pair_id
                or left.public_task_semantic_sha256 != right.public_task_semantic_sha256
                or left.current_state_semantic_sha256 != right.current_state_semantic_sha256
                or left.candidate_set_order_sha256 != right.candidate_set_order_sha256
                or left.schedule_ids != right.schedule_ids
                or left.model_request_config_sha256 != right.model_request_config_sha256
            ):
                raise ValueError("v26.203 paired-arm semantic parents differ")
        if control_first != 6:
            raise ValueError("v26.203 paired execution-order balance differs")
        for job in self.jobs:
            request = requests.get(job.job_id)
            if (
                request is None
                or request.pair_id != job.pair_id
                or request.source_cell_id != job.source_cell_id
                or request.arm != job.arm
                or request.interface_profile_id != job.interface_profile_id
                or request.model_request_config_sha256 != job.model_request_config_sha256
                or request.public_task_semantic_sha256 != job.public_task_semantic_sha256
                or request.current_state_semantic_sha256 != job.current_state_semantic_sha256
                or request.candidate_set_order_sha256 != job.candidate_set_order_sha256
            ):
                raise ValueError("v26.203 Job-to-Request parent differs")
        if self.manifest_id != identity(
            self,
            "manifest_id",
            "fresh_first_response_calibration_manifest:",
        ):
            raise ValueError("v26.203 Calibration Manifest identity differs")
        return self


class FirstResponseDescriptor(FrozenModel):
    response_id: str = Field(min_length=1)
    job_id: str = Field(min_length=1)
    request_id: str = Field(min_length=1)
    source_cell_id: str = Field(min_length=1)
    arm: Arm
    evidence_kind: EvidenceKind
    response_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    typed_outer_terminal: str | None
    exact_json_object: dict[str, Any] | None
    usage: dict[str, Any] | None
    thinking_present: bool | None
    private_reasoning_content_persisted: Literal[False] = False
    provider_call_count: Literal[0, 1]
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_response(self) -> FirstResponseDescriptor:
        if self.evidence_kind == "empirical_calibration" and self.provider_call_count != 1:
            raise ValueError("v26.203 empirical response lacks one Provider call")
        if self.evidence_kind == "scripted_preflight_control" and self.provider_call_count != 0:
            raise ValueError("v26.203 scripted response claims a Provider call")
        if self.exact_json_object is not None and canonical_sha256(self.exact_json_object) != (
            self.response_sha256
        ):
            raise ValueError("v26.203 response object bytes differ")
        if self.response_id != identity(
            self,
            "response_id",
            "fresh_first_response_descriptor:",
        ):
            raise ValueError("v26.203 FirstResponseDescriptor identity differs")
        return self


class FirstActionInterfaceObservation(FrozenModel):
    observation_id: str = Field(min_length=1)
    job_id: str = Field(min_length=1)
    request_id: str = Field(min_length=1)
    response_id: str = Field(min_length=1)
    source_cell_id: str = Field(min_length=1)
    arm: Arm
    evidence_kind: EvidenceKind
    typed_outer_terminal: str | None
    exact_json_object: dict[str, Any] | None
    exact_four_field_abi_valid: bool
    action_reference_valid: bool | None
    state_binding_valid: bool | None
    runtime_step_committed: bool | None
    answer_schema_exact_match: bool
    operation_output_schema_exact_match: bool
    usage: dict[str, Any] | None
    thinking_present: bool | None
    private_reasoning_content_persisted: Literal[False] = False
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_observation(self) -> FirstActionInterfaceObservation:
        if self.exact_four_field_abi_valid:
            if self.action_reference_valid is None or self.state_binding_valid is None:
                raise ValueError("v26.203 ABI-valid Observation lacks binding evaluation")
        elif any(
            value is not None
            for value in (
                self.action_reference_valid,
                self.state_binding_valid,
                self.runtime_step_committed,
            )
        ):
            raise ValueError("v26.203 ABI-invalid Observation fabricates downstream validity")
        if self.observation_id != identity(
            self,
            "observation_id",
            "fresh_first_action_interface_observation:",
        ):
            raise ValueError("v26.203 FirstActionInterfaceObservation identity differs")
        return self


class ExactPairedCalibrationEvaluation(FrozenModel):
    evaluation_id: str = Field(min_length=1)
    manifest_id: str = Field(min_length=1)
    observation_ids: tuple[str, ...] = Field(min_length=24, max_length=24)
    exact_job_ids: tuple[str, ...] = Field(min_length=24, max_length=24)
    source_cell_count: Literal[12] = 12
    observation_count: Literal[24] = 24
    repair_abi_success_count: int = Field(ge=0, le=12)
    repair_reference_state_valid_count: int = Field(ge=0, le=12)
    paired_repair_only_abi_success_count: int = Field(ge=0, le=12)
    paired_control_only_abi_success_count: int = Field(ge=0, le=12)
    delta_abi_numerator: int = Field(ge=-12, le=12)
    delta_abi_denominator: Literal[12] = 12
    all_gates_passed: bool
    capability_estimate: None = None
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_evaluation(self) -> ExactPairedCalibrationEvaluation:
        if len(set(self.observation_ids)) != 24 or len(set(self.exact_job_ids)) != 24:
            raise ValueError("v26.203 paired Evaluation denominator differs")
        if self.delta_abi_numerator != (
            self.paired_repair_only_abi_success_count - self.paired_control_only_abi_success_count
        ):
            raise ValueError("v26.203 paired ABI contrast differs")
        if self.evaluation_id != identity(
            self,
            "evaluation_id",
            "fresh_first_response_exact_paired_calibration_evaluation:",
        ):
            raise ValueError("v26.203 paired Evaluation identity differs")
        return self


class EvidenceSchemaAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    manifest_id: str = Field(min_length=1)
    calibration_job_schema_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    request_descriptor_schema_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    response_descriptor_schema_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    observation_schema_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    evaluation_schema_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    scripted_fixture_response_count: Literal[2] = 2
    scripted_fixture_observation_count: Literal[2] = 2
    exact_parser_fixture_pass_count: Literal[2] = 2
    empirical_response_count: Literal[0] = 0
    empirical_observation_count: Literal[0] = 0
    empirical_evaluation_count: Literal[0] = 0
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> EvidenceSchemaAudit:
        if self.audit_id != identity(
            self,
            "audit_id",
            "finance_v26_203_calibration_evidence_schema_audit:",
        ):
            raise ValueError("v26.203 evidence Schema Audit identity differs")
        return self


class OnlineGateContract(FrozenModel):
    contract_id: str = Field(min_length=1)
    manifest_id: str = Field(min_length=1)
    g0_exact_job_raw_result_observation_count: Literal[24] = 24
    g1_paired_semantic_parent_mismatch_maximum: Literal[0] = 0
    g2_parser_grammar_candidate_change_maximum: Literal[0] = 0
    g3_repair_exact_action_abi_minimum: Literal[9] = 9
    g4_repair_reference_state_valid_minimum: Literal[8] = 8
    g5_paired_repair_only_abi_success_minimum: Literal[7] = 7
    g6_paired_control_only_abi_success_maximum: Literal[1] = 1
    g7_adaptation_relaxation_retry_count_maximum: Literal[0] = 0
    g8_qa_mapper_state_contribution_vtdo_count_maximum: Literal[0] = 0
    exact_mcnemar_and_binomial_intervals_supplementary_only: Literal[True] = True
    gate_compensation_allowed: Literal[False] = False
    full_program_capability_estimand: Literal[False] = False
    online_gate_status: Literal["not_evaluated_preflight_only"] = "not_evaluated_preflight_only"
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_contract(self) -> OnlineGateContract:
        if self.contract_id != identity(
            self,
            "contract_id",
            "fresh_first_response_online_calibration_gate_contract:",
        ):
            raise ValueError("v26.203 online Gate Contract identity differs")
        return self


class ControlClassResult(FrozenModel):
    result_id: str = Field(min_length=1)
    control_class: str = Field(min_length=1)
    case_count: int = Field(gt=0)
    rejected_case_count: int = Field(gt=0)
    accepted_case_count: Literal[0] = 0
    expected_reason: str = Field(min_length=1)
    observed_reasons: tuple[str, ...] = Field(min_length=1)
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_result(self) -> ControlClassResult:
        if self.case_count != self.rejected_case_count or len(self.observed_reasons) != (
            self.case_count
        ):
            raise ValueError("v26.203 control-class denominator differs")
        if self.result_id != identity(
            self,
            "result_id",
            "finance_v26_203_preflight_control_class_result:",
        ):
            raise ValueError("v26.203 control-class Result identity differs")
        return self


class PreflightControlAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    manifest_id: str = Field(min_length=1)
    evidence_schema_audit_id: str = Field(min_length=1)
    controls: tuple[ControlClassResult, ...] = Field(min_length=6, max_length=6)
    control_class_count: Literal[6] = 6
    rejected_control_class_count: Literal[6] = 6
    accepted_control_class_count: Literal[0] = 0
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> PreflightControlAudit:
        if len({item.control_class for item in self.controls}) != 6:
            raise ValueError("v26.203 preflight control-class set differs")
        if self.audit_id != identity(
            self,
            "audit_id",
            "finance_v26_203_preflight_control_audit:",
        ):
            raise ValueError("v26.203 Preflight Control Audit identity differs")
        return self


class Decision(FrozenModel):
    decision_id: str = Field(min_length=1)
    authorization_id: str = Field(min_length=1)
    population_id: str = Field(min_length=1)
    manifest_id: str = Field(min_length=1)
    evidence_schema_audit_id: str = Field(min_length=1)
    gate_contract_id: str = Field(min_length=1)
    control_audit_id: str = Field(min_length=1)
    decision: Literal[
        "fresh_first_response_action_interface_disambiguation_stratified_"
        "24_job_population_preflight_passed"
    ]
    first_root_blocker: Literal[
        "model_visible_first_response_action_interface_not_yet_empirically_instantiated"
    ]
    population_preflight_passed: Literal[True] = True
    online_calibration_executed: Literal[False] = False
    causal_interface_effect_estimated: Literal[False] = False
    capability_estimate_materialized: Literal[False] = False
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_decision(self) -> Decision:
        if self.decision_id != identity(self, "decision_id", "finance_v26_203_decision:"):
            raise ValueError("v26.203 Decision identity differs")
        return self


class Transition(FrozenModel):
    transition_id: str = Field(min_length=1)
    decision_id: str = Field(min_length=1)
    next_decision: Literal[
        "no_online_calibration_authorized_without_new_external_audit_decision"
    ] = NEXT_DECISION
    planned_online_stage: Literal[
        "fresh_first_response_action_interface_disambiguation_paired_24_call_"
        "online_calibration_only"
    ] = PLANNED_ONLINE_STAGE
    online_execution_authorized: Literal[False] = False
    provider_calls_authorized: Literal[False] = False
    maximum_future_provider_calls_after_authorization: Literal[24] = 24
    stage_two_calls_authorized: Literal[False] = False
    retries_or_recovery_authorized: Literal[False] = False
    full_192_job_condition_authorized: Literal[False] = False
    qa_mapper_state_contribution_vtdo_authorized: Literal[False] = False
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_transition(self) -> Transition:
        if self.transition_id != identity(
            self,
            "transition_id",
            "finance_v26_203_transition:",
        ):
            raise ValueError("v26.203 Transition identity differs")
        return self


class ArtifactMember(FrozenModel):
    relative_path: str = Field(min_length=1)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    byte_count: int = Field(gt=0)


class ArtifactManifest(FrozenModel):
    manifest_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    members: tuple[ArtifactMember, ...] = Field(min_length=1)
    file_count: int = Field(gt=0)
    total_byte_count: int = Field(gt=0)
    artifact_root: str = Field(min_length=1)
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_manifest(self) -> ArtifactManifest:
        paths = tuple(item.relative_path for item in self.members)
        if paths != tuple(sorted(set(paths))):
            raise ValueError("v26.203 artifact member set differs")
        if self.file_count != len(self.members) or self.total_byte_count != sum(
            item.byte_count for item in self.members
        ):
            raise ValueError("v26.203 artifact aggregate differs")
        expected_root = canonical_hash(
            tuple(item.model_dump(mode="json") for item in self.members),
            prefix="finance_v26_203_artifact_root:",
        )
        if self.artifact_root != expected_root:
            raise ValueError("v26.203 artifact Root differs")
        if self.manifest_id != identity(
            self,
            "manifest_id",
            "finance_v26_203_artifact_manifest:",
        ):
            raise ValueError("v26.203 artifact Manifest identity differs")
        return self


def artifact_manifest(*, run_id: str, members: tuple[ArtifactMember, ...]) -> ArtifactManifest:
    root = canonical_hash(
        tuple(item.model_dump(mode="json") for item in members),
        prefix="finance_v26_203_artifact_root:",
    )
    return cast(
        ArtifactManifest,
        make_identity(
            ArtifactManifest,
            {
                "run_id": run_id,
                "members": members,
                "file_count": len(members),
                "total_byte_count": sum(item.byte_count for item in members),
                "artifact_root": root,
            },
            field="manifest_id",
            prefix="finance_v26_203_artifact_manifest:",
        ),
    )
