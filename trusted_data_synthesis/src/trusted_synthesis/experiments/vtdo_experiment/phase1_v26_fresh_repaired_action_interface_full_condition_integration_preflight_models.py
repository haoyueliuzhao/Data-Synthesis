# ruff: noqa: E501
from __future__ import annotations

import hashlib
import json
from typing import Any, Final, Literal, cast

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.hashing import canonical_hash

SCHEMA_VERSION: Final = "fresh_repaired_action_interface_full_condition_integration_preflight.v1"
CONSUMED_STAGE: Final = (
    "fresh_repaired_action_interface_full_condition_integration_and_identity_preflight_only"
)
NEXT_STAGE: Final = (
    "fresh_repaired_action_interface_full_condition_integration_preflight_independent_audit_only"
)


class FrozenModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


def canonical_bytes(value: Any) -> bytes:
    if isinstance(value, BaseModel):
        value = value.model_dump(mode="json", warnings=False)
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


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


class ExternalPreflightAuthorization(FrozenModel):
    authorization_id: str = Field(min_length=1)
    audit_sha256: Literal["b0ab58a19818e7a5086bbc0b7ffa03768d1148d9c441093407c43184c9c6fd59"]
    audit_byte_count: Literal[14288] = 14_288
    audited_experiment: Literal["Finance v26.205"] = "Finance v26.205"
    audit_decision: Literal["PASS_AS_SCOPED"] = "PASS_AS_SCOPED"
    mandatory_revision_required: Literal[False] = False
    only_authorized_successor: Literal[
        "fresh_repaired_action_interface_full_condition_integration_and_identity_preflight_only"
    ] = CONSUMED_STAGE
    provider_calls_authorized: Literal[0] = 0
    credential_lookups_authorized: Literal[0] = 0
    full_repaired_192_job_execution_authorized: Literal[False] = False
    parser_relaxation_or_historical_adaptation_authorized: Literal[False] = False
    interface_factor_decomposition_authorized: Literal[False] = False
    qa_mapper_state_contribution_vtdo_authorized: Literal[False] = False
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_authorization(self) -> ExternalPreflightAuthorization:
        if self.authorization_id != identity(
            self,
            "authorization_id",
            "finance_v26_206_external_preflight_authorization:",
        ):
            raise ValueError("v26.206 external preflight Authorization identity differs")
        return self


class PredecessorFreeze(FrozenModel):
    freeze_id: str = Field(min_length=1)
    authorization_id: str = Field(min_length=1)
    v205_report_content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    v205_decision_id: str = Field(min_length=1)
    v205_transition_id: str = Field(min_length=1)
    v205_artifact_manifest_id: str = Field(min_length=1)
    v205_artifact_root: str = Field(min_length=1)
    v205_source_commit: Literal["76a2d00bc9b1517da659eda901b9dff8f3389aa0"]
    v205_source_tree: Literal["c78ad15bf191a98f085cc76deaf0f35f68c2e9a9"]
    v205_formal_file_count: Literal[14] = 14
    v205_formal_byte_count: Literal[91230] = 91_230
    v205_manifest_member_match_count: Literal[13] = 13
    v194_package_catalog_id: str = Field(min_length=1)
    v194_manifest_id: str = Field(min_length=1)
    v194_runner_id: str = Field(min_length=1)
    v194_execution_contract_id: str = Field(min_length=1)
    v194_resource_contract_id: str = Field(min_length=1)
    v193_prompt_evidence_set_id: str = Field(min_length=1)
    v203_action_contract_id: str = Field(min_length=1)
    exact_source_package_count: Literal[32] = 32
    exact_source_job_count: Literal[192] = 192
    exact_source_callsite_count: Literal[792] = 792
    historical_artifact_mutation_count: Literal[0] = 0
    provider_calls: Literal[0] = 0
    credential_lookups: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_freeze(self) -> PredecessorFreeze:
        if self.freeze_id != identity(
            self,
            "freeze_id",
            "finance_v26_206_predecessor_freeze:",
        ):
            raise ValueError("v26.206 predecessor Freeze identity differs")
        return self


class FullConditionRepairProfile(FrozenModel):
    profile_id: str = Field(min_length=1)
    authorization_id: str = Field(min_length=1)
    predecessor_freeze_id: str = Field(min_length=1)
    source_v203_action_contract_id: str = Field(min_length=1)
    frozen_action_grammar_id: str = Field(min_length=1)
    exact_required_fields: tuple[
        Literal["state_id", "action_id", "decision_kind", "protocol"], ...
    ] = ("state_id", "action_id", "decision_kind", "protocol")
    exact_allowed_fields: tuple[
        Literal["state_id", "action_id", "decision_kind", "protocol"], ...
    ] = ("state_id", "action_id", "decision_kind", "protocol")
    decision_kind_value: Literal["execute_public_operation"] = "execute_public_operation"
    protocol_value: Literal["prospective_semantic_action_exact_response.v1"] = (
        "prospective_semantic_action_exact_response.v1"
    )
    first_action_repaired: Literal[True] = True
    subsequent_action_repaired: Literal[True] = True
    typed_rejection_correction_repaired: Literal[True] = True
    final_interface_unchanged: Literal[True] = True
    grammar_id_host_side_only: Literal[True] = True
    answer_and_operation_schemas_verifier_metadata_only: Literal[True] = True
    response_abi_removed_from_user_payload: Literal[True] = True
    parser_relaxation: Literal[False] = False
    historical_payload_adaptation: Literal[False] = False
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_profile(self) -> FullConditionRepairProfile:
        expected = ("state_id", "action_id", "decision_kind", "protocol")
        if self.exact_required_fields != expected or self.exact_allowed_fields != expected:
            raise ValueError("v26.206 repair profile is not the exact four-field Contract")
        if self.profile_id != identity(
            self,
            "profile_id",
            "fresh_repaired_action_interface_full_condition_profile:",
        ):
            raise ValueError("v26.206 full-condition Repair Profile identity differs")
        return self


class RepairedRunnerPackage(FrozenModel):
    package_id: str = Field(min_length=1)
    source_v194_package_id: str = Field(min_length=1)
    source_v194_package_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    repair_profile_id: str = Field(min_length=1)
    runtime_semantic_contract_id: str = Field(min_length=1)
    runtime_implementation_binding_id: str = Field(min_length=1)
    final_grammar_id: str = Field(min_length=1)
    resource_contract_id: str = Field(min_length=1)
    capability_family: str = Field(min_length=1)
    depth: str = Field(min_length=1)
    schedule_ids: tuple[str, ...] = Field(min_length=1, max_length=4)
    component_keys: tuple[str, ...] = Field(min_length=1, max_length=4)
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_package(self) -> RepairedRunnerPackage:
        if len(self.schedule_ids) != len(self.component_keys):
            raise ValueError("v26.206 repaired Package Schedule denominator differs")
        if self.package_id != identity(
            self,
            "package_id",
            "fresh_repaired_full_condition_runner_package:",
        ):
            raise ValueError("v26.206 repaired Runner Package identity differs")
        return self


class RepairedRunnerPackageCatalog(FrozenModel):
    catalog_id: str = Field(min_length=1)
    repair_profile_id: str = Field(min_length=1)
    packages: tuple[RepairedRunnerPackage, ...] = Field(min_length=32, max_length=32)
    source_v194_package_ids: tuple[str, ...] = Field(min_length=32, max_length=32)
    package_count: Literal[32] = 32
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_catalog(self) -> RepairedRunnerPackageCatalog:
        if len({item.package_id for item in self.packages}) != 32:
            raise ValueError("v26.206 repaired Package denominator differs")
        if self.source_v194_package_ids != tuple(
            sorted(item.source_v194_package_id for item in self.packages)
        ):
            raise ValueError("v26.206 repaired Package source set differs")
        if self.catalog_id != identity(
            self,
            "catalog_id",
            "fresh_repaired_full_condition_package_catalog:",
        ):
            raise ValueError("v26.206 repaired Package Catalog identity differs")
        return self


class RepairedDevelopmentJob(FrozenModel):
    job_id: str = Field(min_length=1)
    source_v194_job_id: str = Field(min_length=1)
    source_v194_job_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    package_id: str = Field(min_length=1)
    source_v194_package_id: str = Field(min_length=1)
    repair_profile_id: str = Field(min_length=1)
    replica_index: int = Field(ge=0, le=5)
    raw_namespace: str = Field(min_length=1)
    result_namespace: str = Field(min_length=1)
    trace_namespace: str = Field(min_length=1)
    outcome_namespace: str = Field(min_length=1)
    deterministic_seed_id: str = Field(min_length=1)
    provider_calls: Literal[0] = 0
    empirical_outcome: Literal[False] = False
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_job(self) -> RepairedDevelopmentJob:
        parent = {
            "source_v194_job_id": self.source_v194_job_id,
            "package_id": self.package_id,
            "repair_profile_id": self.repair_profile_id,
            "replica_index": self.replica_index,
        }
        expected = (
            canonical_hash(parent, prefix="fresh_repaired_raw_namespace:"),
            canonical_hash(parent, prefix="fresh_repaired_result_namespace:"),
            canonical_hash(parent, prefix="fresh_repaired_trace_namespace:"),
            canonical_hash(parent, prefix="fresh_repaired_outcome_namespace:"),
            canonical_hash(parent, prefix="fresh_repaired_deterministic_seed:"),
        )
        if (
            self.raw_namespace,
            self.result_namespace,
            self.trace_namespace,
            self.outcome_namespace,
            self.deterministic_seed_id,
        ) != expected:
            raise ValueError("v26.206 repaired Job namespace parent differs")
        if self.job_id != identity(
            self,
            "job_id",
            "fresh_repaired_full_condition_development_job:",
        ):
            raise ValueError("v26.206 repaired Development Job identity differs")
        return self


class RepairedDevelopmentManifest(FrozenModel):
    manifest_id: str = Field(min_length=1)
    package_catalog_id: str = Field(min_length=1)
    repair_profile_id: str = Field(min_length=1)
    jobs: tuple[RepairedDevelopmentJob, ...] = Field(min_length=192, max_length=192)
    expected_job_ids: tuple[str, ...] = Field(min_length=192, max_length=192)
    source_v194_job_ids: tuple[str, ...] = Field(min_length=192, max_length=192)
    package_count: Literal[32] = 32
    replica_count: Literal[6] = 6
    job_count: Literal[192] = 192
    provider_calls: Literal[0] = 0
    development_model_outcomes: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_manifest(self) -> RepairedDevelopmentManifest:
        ids = tuple(item.job_id for item in self.jobs)
        if len(set(ids)) != 192 or self.expected_job_ids != tuple(sorted(ids)):
            raise ValueError("v26.206 repaired Manifest Job set differs")
        if self.source_v194_job_ids != tuple(sorted(item.source_v194_job_id for item in self.jobs)):
            raise ValueError("v26.206 repaired Manifest source Job set differs")
        if len({(item.package_id, item.replica_index) for item in self.jobs}) != 192:
            raise ValueError("v26.206 repaired Package x Replica denominator differs")
        namespaces = (
            {item.raw_namespace for item in self.jobs},
            {item.result_namespace for item in self.jobs},
            {item.trace_namespace for item in self.jobs},
            {item.outcome_namespace for item in self.jobs},
        )
        if any(len(values) != 192 for values in namespaces):
            raise ValueError("v26.206 repaired evidence namespaces are not unique")
        if self.manifest_id != identity(
            self,
            "manifest_id",
            "fresh_repaired_full_condition_manifest:",
        ):
            raise ValueError("v26.206 repaired Manifest identity differs")
        return self


class RepairedRunnerContract(FrozenModel):
    runner_id: str = Field(min_length=1)
    manifest_id: str = Field(min_length=1)
    package_catalog_id: str = Field(min_length=1)
    repair_profile_id: str = Field(min_length=1)
    source_v194_runner_id: str = Field(min_length=1)
    one_current_prompt_at_a_time: Literal[True] = True
    dynamic_contract_recompiled_per_state: Literal[True] = True
    correction_preserves_exact_four_field_abi: Literal[True] = True
    fresh_request_and_prompt_identity_required: Literal[True] = True
    exact_job_count: Literal[192] = 192
    online_execution_authorized: Literal[False] = False
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_runner(self) -> RepairedRunnerContract:
        if self.runner_id != identity(
            self,
            "runner_id",
            "fresh_repaired_full_condition_runner:",
        ):
            raise ValueError("v26.206 repaired Runner identity differs")
        return self


class RepairedExecutionContract(FrozenModel):
    contract_id: str = Field(min_length=1)
    runner_id: str = Field(min_length=1)
    manifest_id: str = Field(min_length=1)
    package_catalog_id: str = Field(min_length=1)
    repair_profile_id: str = Field(min_length=1)
    source_v194_execution_contract_id: str = Field(min_length=1)
    resource_contract_id: str = Field(min_length=1)
    exact_job_count: Literal[192] = 192
    exact_registered_callsite_count: Literal[792] = 792
    maximum_primary_requests: Literal[21] = 21
    maximum_provider_calls: Literal[23] = 23
    maximum_transport_invocations: Literal[24] = 24
    maximum_rollout_tokens: Literal[1120000] = 1_120_000
    maximum_prompt_utf8_bytes: Literal[60000] = 60_000
    maximum_transport_replacements: Literal[1] = 1
    raw_result_trace_outcome_required: Literal[True] = True
    online_execution_authorized: Literal[False] = False
    provider_calls: Literal[0] = 0
    credential_lookups: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_execution(self) -> RepairedExecutionContract:
        if self.contract_id != identity(
            self,
            "contract_id",
            "fresh_repaired_full_condition_execution_contract:",
        ):
            raise ValueError("v26.206 repaired Execution Contract identity differs")
        return self


PromptPhase = Literal["first_action", "subsequent_action", "correction", "final"]
PromptKind = Literal["action", "correction", "final"]


class RepairedCallsiteRow(FrozenModel):
    row_id: str = Field(min_length=1)
    source_v193_evidence_row_id: str = Field(min_length=1)
    source_v193_coordinate_id: str = Field(min_length=1)
    source_v194_job_id: str = Field(min_length=1)
    fresh_job_id: str = Field(min_length=1)
    invocation_index: int = Field(ge=0, le=9)
    phase: PromptPhase
    prompt_kind: PromptKind
    component_key: str | None = None
    current_state_id: str = Field(min_length=1)
    candidate_action_ids: tuple[str, ...]
    rejected_action_id: str | None = None
    rejection_receipt_id: str | None = None
    repaired_prompt_id: str = Field(min_length=1)
    request_id: str = Field(min_length=1)
    canonical_messages_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    canonical_messages_byte_count: int = Field(gt=0)
    canonical_request_body_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    canonical_request_body_byte_count: int = Field(gt=0)
    repair_profile_id: str = Field(min_length=1)
    parser_id: str = Field(min_length=1)
    grammar_id: str = Field(min_length=1)
    dynamic_state_exact: Literal[True] = True
    dynamic_candidate_set_and_order_exact: Literal[True] = True
    exact_four_field_action_contract: bool
    answer_operation_metadata_model_response_schema: Literal[False] = False
    action_grammar_id_model_visible_count: Literal[0] = 0
    old_response_abi_model_visible_count: Literal[0] = 0
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_row(self) -> RepairedCallsiteRow:
        if self.phase == "final":
            if self.prompt_kind != "final" or self.candidate_action_ids:
                raise ValueError("v26.206 Final callsite carries Action candidates")
            if self.exact_four_field_action_contract:
                raise ValueError("v26.206 Final callsite is mislabeled as Action ABI")
        else:
            if not self.candidate_action_ids or not self.exact_four_field_action_contract:
                raise ValueError("v26.206 Action callsite lacks exact Candidate-bound Contract")
            if self.phase == "correction":
                if self.prompt_kind != "correction" or any(
                    value is None for value in (self.rejected_action_id, self.rejection_receipt_id)
                ):
                    raise ValueError("v26.206 Correction callsite lacks rejection evidence")
            elif self.prompt_kind != "action" or any(
                value is not None for value in (self.rejected_action_id, self.rejection_receipt_id)
            ):
                raise ValueError("v26.206 non-Correction Action carries rejection evidence")
        if self.repaired_prompt_id != canonical_hash(
            {
                "fresh_job_id": self.fresh_job_id,
                "source_v193_coordinate_id": self.source_v193_coordinate_id,
                "canonical_messages_sha256": self.canonical_messages_sha256,
                "repair_profile_id": self.repair_profile_id,
            },
            prefix="fresh_repaired_full_condition_prompt:",
        ):
            raise ValueError("v26.206 repaired Prompt identity differs")
        if self.request_id != canonical_hash(
            {
                "fresh_job_id": self.fresh_job_id,
                "repaired_prompt_id": self.repaired_prompt_id,
                "canonical_request_body_sha256": self.canonical_request_body_sha256,
            },
            prefix="fresh_repaired_full_condition_request:",
        ):
            raise ValueError("v26.206 repaired Request identity differs")
        if self.row_id != identity(
            self,
            "row_id",
            "fresh_repaired_full_condition_callsite_row:",
        ):
            raise ValueError("v26.206 repaired Callsite Row identity differs")
        return self


class RepairedCallsiteCensus(FrozenModel):
    census_id: str = Field(min_length=1)
    execution_contract_id: str = Field(min_length=1)
    manifest_id: str = Field(min_length=1)
    repair_profile_id: str = Field(min_length=1)
    source_v193_evidence_set_id: str = Field(min_length=1)
    rows: tuple[RepairedCallsiteRow, ...] = Field(min_length=792, max_length=792)
    exact_job_count: Literal[192] = 192
    exact_callsite_count: Literal[792] = 792
    unique_row_count: Literal[792] = 792
    unique_prompt_count: Literal[792] = 792
    unique_request_count: Literal[792] = 792
    first_action_count: Literal[192] = 192
    subsequent_action_count: Literal[288] = 288
    correction_count: Literal[120] = 120
    final_count: Literal[192] = 192
    action_contract_compile_count: Literal[600] = 600
    final_grammar_binding_count: Literal[192] = 192
    maximum_repaired_message_byte_count: int = Field(gt=0, le=60000)
    maximum_repaired_request_body_byte_count: int = Field(gt=0)
    parser_relaxation_count: Literal[0] = 0
    historical_adaptation_count: Literal[0] = 0
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_census(self) -> RepairedCallsiteCensus:
        if len({item.row_id for item in self.rows}) != 792:
            raise ValueError("v26.206 Callsite census repeats a row")
        if len({item.repaired_prompt_id for item in self.rows}) != 792:
            raise ValueError("v26.206 Callsite census repeats a Prompt identity")
        if len({item.request_id for item in self.rows}) != 792:
            raise ValueError("v26.206 Callsite census repeats a Request identity")
        counts = {
            phase: 0 for phase in ("first_action", "subsequent_action", "correction", "final")
        }
        for row in self.rows:
            counts[row.phase] += 1
        if counts != {
            "first_action": 192,
            "subsequent_action": 288,
            "correction": 120,
            "final": 192,
        }:
            raise ValueError("v26.206 Callsite phase denominator differs")
        if self.census_id != identity(
            self,
            "census_id",
            "finance_v26_206_repaired_callsite_census:",
        ):
            raise ValueError("v26.206 repaired Callsite Census identity differs")
        return self


class ScriptedIntegrationRow(FrozenModel):
    row_id: str = Field(min_length=1)
    job_id: str = Field(min_length=1)
    source_v194_job_id: str = Field(min_length=1)
    callsite_row_ids: tuple[str, ...] = Field(min_length=2, max_length=10)
    first_action_count: Literal[1] = 1
    subsequent_action_count: int = Field(ge=0, le=3)
    typed_rejection_branch_count: int = Field(ge=0, le=4)
    correction_count: int = Field(ge=0, le=4)
    final_count: Literal[1] = 1
    exact_action_parse_count: int = Field(ge=1, le=4)
    action_reference_and_state_valid_count: int = Field(ge=1, le=4)
    correction_reference_and_state_valid_count: int = Field(ge=0, le=4)
    runtime_commit_count: int = Field(ge=1, le=4)
    terminal_state_reached: Literal[True] = True
    final_abi_valid: Literal[True] = True
    independent_validity_invoked: Literal[True] = True
    base_valid: Literal[True] = True
    mechanism_valid: Literal[True] = True
    qualified_valid: Literal[True] = True
    raw_id: str = Field(min_length=1)
    result_id: str = Field(min_length=1)
    trace_id: str = Field(min_length=1)
    outcome_id: str = Field(min_length=1)
    raw_result_trace_outcome_parent_closure: Literal[True] = True
    empirical: Literal[False] = False
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_row(self) -> ScriptedIntegrationRow:
        if self.typed_rejection_branch_count != self.correction_count:
            raise ValueError("v26.206 scripted Correction count differs from rejection branches")
        expected_action = self.first_action_count + self.subsequent_action_count
        if (
            self.exact_action_parse_count != expected_action
            or self.action_reference_and_state_valid_count != expected_action
            or self.runtime_commit_count != expected_action
            or self.correction_reference_and_state_valid_count != self.correction_count
        ):
            raise ValueError("v26.206 scripted Action/State/Correction geometry differs")
        expected_raw = canonical_hash(
            {"job_id": self.job_id, "callsite_row_ids": self.callsite_row_ids},
            prefix="fresh_repaired_scripted_raw:",
        )
        expected_result = canonical_hash(
            {"job_id": self.job_id, "raw_id": expected_raw, "qualified_valid": True},
            prefix="fresh_repaired_scripted_result:",
        )
        expected_trace = canonical_hash(
            {"job_id": self.job_id, "raw_id": expected_raw, "result_id": expected_result},
            prefix="fresh_repaired_scripted_trace:",
        )
        expected_outcome = canonical_hash(
            {"job_id": self.job_id, "trace_id": expected_trace, "qualified_valid": True},
            prefix="fresh_repaired_scripted_outcome:",
        )
        if (self.raw_id, self.result_id, self.trace_id, self.outcome_id) != (
            expected_raw,
            expected_result,
            expected_trace,
            expected_outcome,
        ):
            raise ValueError("v26.206 scripted evidence parent chain differs")
        if self.row_id != identity(
            self,
            "row_id",
            "finance_v26_206_scripted_integration_row:",
        ):
            raise ValueError("v26.206 scripted Integration Row identity differs")
        return self


class ScriptedIntegrationAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    execution_contract_id: str = Field(min_length=1)
    callsite_census_id: str = Field(min_length=1)
    rows: tuple[ScriptedIntegrationRow, ...] = Field(min_length=192, max_length=192)
    exact_job_count: Literal[192] = 192
    scripted_raw_count: Literal[192] = 192
    scripted_result_count: Literal[192] = 192
    scripted_trace_count: Literal[192] = 192
    scripted_outcome_count: Literal[192] = 192
    first_action_parse_count: Literal[192] = 192
    subsequent_action_parse_count: Literal[288] = 288
    typed_rejection_branch_count: Literal[120] = 120
    correction_parse_count: Literal[120] = 120
    final_parse_count: Literal[192] = 192
    terminal_state_count: Literal[192] = 192
    independent_validity_count: Literal[192] = 192
    scripted_qualified_count: Literal[192] = 192
    unique_layer_identity_count: Literal[768] = 768
    exception_escape_count: Literal[0] = 0
    empirical_row_count: Literal[0] = 0
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> ScriptedIntegrationAudit:
        if len({item.job_id for item in self.rows}) != 192:
            raise ValueError("v26.206 scripted Integration Job denominator differs")
        layer_ids = {
            value
            for item in self.rows
            for value in (item.raw_id, item.result_id, item.trace_id, item.outcome_id)
        }
        if len(layer_ids) != 768:
            raise ValueError("v26.206 scripted evidence layer identity denominator differs")
        if self.audit_id != identity(
            self,
            "audit_id",
            "finance_v26_206_scripted_full_condition_integration_audit:",
        ):
            raise ValueError("v26.206 scripted Integration Audit identity differs")
        return self


class FailureControl(FrozenModel):
    control_id: str = Field(min_length=1)
    control_name: Literal[
        "invalid_first_action_abi",
        "unknown_action_reference",
        "invalid_correction_abi",
        "invalid_final_abi",
        "typed_outer_terminal",
    ]
    target_stage: str = Field(min_length=1)
    expected_terminal: str = Field(min_length=1)
    observed_terminal: str = Field(min_length=1)
    typed_outcome_count: Literal[1] = 1
    exception_escape_count: Literal[0] = 0
    verifier_invoked: bool
    rejected_or_terminalized: Literal[True] = True
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_control(self) -> FailureControl:
        if self.expected_terminal != self.observed_terminal:
            raise ValueError("v26.206 failure control terminal differs")
        if self.control_id != identity(
            self,
            "control_id",
            "finance_v26_206_failure_control:",
        ):
            raise ValueError("v26.206 Failure Control identity differs")
        return self


class FailureControlAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    execution_contract_id: str = Field(min_length=1)
    controls: tuple[FailureControl, ...] = Field(min_length=5, max_length=5)
    control_count: Literal[5] = 5
    typed_outcome_count: Literal[5] = 5
    exception_escape_count: Literal[0] = 0
    accepted_control_count: Literal[0] = 0
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> FailureControlAudit:
        if len({item.control_name for item in self.controls}) != 5:
            raise ValueError("v26.206 Failure Control denominator differs")
        if self.audit_id != identity(
            self,
            "audit_id",
            "finance_v26_206_failure_control_audit:",
        ):
            raise ValueError("v26.206 Failure Control Audit identity differs")
        return self


class ProspectiveEstimandContract(FrozenModel):
    contract_id: str = Field(min_length=1)
    execution_contract_id: str = Field(min_length=1)
    manifest_id: str = Field(min_length=1)
    exact_denominator: Literal[192] = 192
    q_first_repaired_definition: Literal[
        "complete_qualified_jobs_with_zero_component_corrections_over_exact_192_jobs"
    ] = "complete_qualified_jobs_with_zero_component_corrections_over_exact_192_jobs"
    q_bounded_correction_repaired_definition: Literal[
        "complete_qualified_jobs_under_one_correction_per_reached_component_over_exact_192_jobs"
    ] = "complete_qualified_jobs_under_one_correction_per_reached_component_over_exact_192_jobs"
    pre_action_abi_terminal_counts_as_false: Literal[True] = True
    outer_terminal_remains_in_denominator: Literal[True] = True
    post_action_abi_conditional_null_when_denominator_zero: Literal[True] = True
    q_first_numerator: None = None
    q_bounded_correction_numerator: None = None
    q_first_estimate: None = None
    q_bounded_correction_estimate: None = None
    confidence_intervals: None = None
    empirical_rows: Literal[0] = 0
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_contract(self) -> ProspectiveEstimandContract:
        if self.contract_id != identity(
            self,
            "contract_id",
            "fresh_repaired_full_condition_prospective_estimand_contract:",
        ):
            raise ValueError("v26.206 prospective Estimand Contract identity differs")
        return self


class FullConditionGateAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    predecessor_freeze_id: str = Field(min_length=1)
    manifest_id: str = Field(min_length=1)
    callsite_census_id: str = Field(min_length=1)
    scripted_integration_audit_id: str = Field(min_length=1)
    failure_control_audit_id: str = Field(min_length=1)
    estimand_contract_id: str = Field(min_length=1)
    f0_authority_and_predecessor_freeze_passed: Literal[True] = True
    f1_exact_source_equality_and_fresh_identity_disjointness_passed: Literal[True] = True
    f2_repaired_action_interface_callsite_totality_passed: Literal[True] = True
    f3_scripted_action_state_correction_final_closure_passed: Literal[True] = True
    f4_raw_result_trace_outcome_parent_closure_passed: Literal[True] = True
    f5_zero_provider_credential_qa_mapper_vtdo_passed: Literal[True] = True
    all_gates_passed: Literal[True] = True
    source_package_equality_count: Literal[32] = 32
    source_job_equality_count: Literal[192] = 192
    fresh_identity_collision_count: Literal[0] = 0
    provider_calls: Literal[0] = 0
    credential_lookups: Literal[0] = 0
    qa_rows: Literal[0] = 0
    mapper_rows: Literal[0] = 0
    state_rows: Literal[0] = 0
    contribution_rows: Literal[0] = 0
    vtdo_rows: Literal[0] = 0
    capability_estimate: None = None
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> FullConditionGateAudit:
        if self.audit_id != identity(
            self,
            "audit_id",
            "finance_v26_206_full_condition_gate_audit:",
        ):
            raise ValueError("v26.206 Full-condition Gate Audit identity differs")
        return self


class ProspectiveTransition(FrozenModel):
    transition_id: str = Field(min_length=1)
    gate_audit_id: str = Field(min_length=1)
    execution_contract_id: str = Field(min_length=1)
    estimand_contract_id: str = Field(min_length=1)
    decision: Literal[
        "fresh_repaired_full_condition_integration_and_identity_preflight_complete_"
        "independent_audit_only"
    ] = (
        "fresh_repaired_full_condition_integration_and_identity_preflight_complete_"
        "independent_audit_only"
    )
    next_stage: Literal[
        "fresh_repaired_action_interface_full_condition_integration_preflight_"
        "independent_audit_only"
    ] = NEXT_STAGE
    provider_calls_authorized: Literal[0] = 0
    credential_lookups_authorized: Literal[0] = 0
    full_repaired_192_job_execution_authorized: Literal[False] = False
    parser_relaxation_authorized: Literal[False] = False
    historical_adaptation_authorized: Literal[False] = False
    qa_mapper_state_contribution_vtdo_authorized: Literal[False] = False
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_transition(self) -> ProspectiveTransition:
        if self.transition_id != identity(
            self,
            "transition_id",
            "finance_v26_206_transition:",
        ):
            raise ValueError("v26.206 Transition identity differs")
        return self


class SourceIdentity(FrozenModel):
    source_identity_id: str = Field(min_length=1)
    source_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    source_tree: str = Field(pattern=r"^[0-9a-f]{40}$")
    implementation_files: tuple[str, ...] = Field(min_length=3)
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_source(self) -> SourceIdentity:
        if tuple(sorted(set(self.implementation_files))) != self.implementation_files:
            raise ValueError("v26.206 source file vector differs")
        if self.source_identity_id != identity(
            self,
            "source_identity_id",
            "finance_v26_206_source_identity:",
        ):
            raise ValueError("v26.206 Source Identity differs")
        return self


class PreflightReport(FrozenModel):
    report_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    authorization_id: str = Field(min_length=1)
    predecessor_freeze_id: str = Field(min_length=1)
    repair_profile_id: str = Field(min_length=1)
    package_catalog_id: str = Field(min_length=1)
    manifest_id: str = Field(min_length=1)
    runner_id: str = Field(min_length=1)
    execution_contract_id: str = Field(min_length=1)
    callsite_census_id: str = Field(min_length=1)
    scripted_integration_audit_id: str = Field(min_length=1)
    failure_control_audit_id: str = Field(min_length=1)
    estimand_contract_id: str = Field(min_length=1)
    gate_audit_id: str = Field(min_length=1)
    transition_id: str = Field(min_length=1)
    source_identity_id: str = Field(min_length=1)
    decision: Literal[
        "fresh_repaired_full_condition_integration_and_identity_preflight_passed_"
        "no_online_execution_authorized"
    ] = (
        "fresh_repaired_full_condition_integration_and_identity_preflight_passed_"
        "no_online_execution_authorized"
    )
    provider_calls: Literal[0] = 0
    credential_lookups: Literal[0] = 0
    development_model_outcomes: Literal[0] = 0
    empirical_rows: Literal[0] = 0
    empirical_estimates: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_report(self) -> PreflightReport:
        if self.report_id != identity(
            self,
            "report_id",
            "finance_v26_206_full_condition_preflight_report:",
        ):
            raise ValueError("v26.206 Preflight Report identity differs")
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
        if tuple(item.relative_path for item in self.members) != tuple(
            sorted(item.relative_path for item in self.members)
        ):
            raise ValueError("v26.206 Artifact Manifest member order differs")
        if len({item.relative_path for item in self.members}) != len(self.members):
            raise ValueError("v26.206 Artifact Manifest repeats a path")
        if self.file_count != len(self.members):
            raise ValueError("v26.206 Artifact Manifest file count differs")
        if self.total_byte_count != sum(item.byte_count for item in self.members):
            raise ValueError("v26.206 Artifact Manifest byte count differs")
        expected_root = canonical_hash(
            tuple(item.model_dump(mode="json") for item in self.members),
            prefix="finance_v26_206_artifact_root:",
        )
        if self.artifact_root != expected_root:
            raise ValueError("v26.206 Artifact Root differs")
        if self.manifest_id != identity(
            self,
            "manifest_id",
            "finance_v26_206_artifact_manifest:",
        ):
            raise ValueError("v26.206 Artifact Manifest identity differs")
        return self


def artifact_manifest(run_id: str, payloads: dict[str, bytes]) -> ArtifactManifest:
    members = tuple(
        ArtifactMember(
            relative_path=name,
            sha256=hashlib.sha256(payload).hexdigest(),
            byte_count=len(payload),
        )
        for name, payload in sorted(payloads.items())
    )
    root = canonical_hash(
        tuple(item.model_dump(mode="json") for item in members),
        prefix="finance_v26_206_artifact_root:",
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
            prefix="finance_v26_206_artifact_manifest:",
        ),
    )
