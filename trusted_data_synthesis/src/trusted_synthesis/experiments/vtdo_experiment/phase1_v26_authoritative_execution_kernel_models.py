from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.hashing import canonical_hash

SCHEMA_VERSION = "authoritative_execution_kernel_parent_preflight.v1"
AUTHORIZED_STAGE = "json_explicit_authoritative_execution_kernel_parent_binding_preflight_only"
NEXT_STAGE = "json_explicit_authoritative_execution_kernel_parent_binding_independent_audit_only"


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
    byte_count: int = Field(gt=0)


class SymbolBinding(FrozenModel):
    relative_path: str = Field(min_length=1)
    symbol: str = Field(min_length=1)
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_byte_count: int = Field(gt=0)


class ExternalAuditAuthorization(FrozenModel):
    authorization_id: str = Field(min_length=1)
    audit_sha256: Literal["910619d8ba69a31fb29ca4190bdf1d09e9ea3fe1071520516fdebb44a614b3bb"]
    audit_byte_count: Literal[17476] = 17476
    consumed_stage: Literal[
        "json_explicit_authoritative_execution_kernel_parent_binding_preflight_only"
    ] = "json_explicit_authoritative_execution_kernel_parent_binding_preflight_only"
    provider_calls_authorized: Literal[False] = False
    fresh_outcome_authority_authorized: Literal[False] = False
    online_execution_authorized: Literal[False] = False
    historical_rewrite_authorized: Literal[False] = False
    runtime_choice: Literal["option_b_current_runtime"] = "option_b_current_runtime"
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_authorization(self) -> ExternalAuditAuthorization:
        if not validate_identity(
            self, "authorization_id", "finance_v26_194_external_authorization:"
        ):
            raise ValueError("v26.194 external authorization identity differs")
        return self


class V193ExternalAnchor(FrozenModel):
    anchor_id: str = Field(min_length=1)
    authorization_id: str = Field(min_length=1)
    source_commit: Literal["b5b21ee90926713773d4028028ec67c7a7d40d4e"]
    source_tree: Literal["9ce799b058750a397083e125ccbd58967642b54d"]
    report_id: Literal[
        "finance_v26_193_prompt_authority_repair_report:"
        "b7d13fef2097d90cc6772320761608a79d556630fe96622f2d6ac2c884296ea3"
    ]
    artifact_manifest_id: Literal[
        "finance_v26_193_artifact_manifest:"
        "bdd16b312c8a074f852b1123da96e613b875b16ea713048f90b8db0201d7ca32"
    ]
    artifact_root: Literal[
        "finance_v26_193_artifact_root:"
        "4eaebaec735f310ac55056c7ca57f50682dc3472f79f799a4a886531c7e627e0"
    ]
    exact_files: tuple[FileBinding, ...] = Field(min_length=12, max_length=12)
    exact_file_count: Literal[12] = 12
    exact_file_match_count: Literal[12] = 12
    candidate_directory_values_used_as_expectations: Literal[False] = False
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_anchor(self) -> V193ExternalAnchor:
        paths = tuple(item.relative_path for item in self.exact_files)
        if paths != tuple(sorted(paths)) or len(set(paths)) != 12:
            raise ValueError("v26.193 external file set is not exact")
        if not validate_identity(self, "anchor_id", "finance_v26_193_external_anchor:"):
            raise ValueError("v26.193 external anchor identity differs")
        return self


class RuntimeImplementationBinding(FrozenModel):
    binding_id: str = Field(min_length=1)
    external_anchor_id: str = Field(min_length=1)
    selected_runtime: Literal["current_runtime_option_b"] = "current_runtime_option_b"
    source_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    source_tree: str = Field(pattern=r"^[0-9a-f]{40}$")
    runtime_file: FileBinding
    runtime_symbols: tuple[SymbolBinding, ...] = Field(min_length=4, max_length=4)
    required_symbols: tuple[str, ...] = ("initialize", "render_next_prompt", "step", "finalize")
    semantic_version: Literal["all_typed_rejection_step_runtime.current.v1"] = (
        "all_typed_rejection_step_runtime.current.v1"
    )
    event_identity_contract: Literal["causal_public_runtime_event.v1"] = (
        "causal_public_runtime_event.v1"
    )
    event_output_hash_contract: Literal["causal_runtime_event_output.canonical_hash.v1"] = (
        "causal_runtime_event_output.canonical_hash.v1"
    )
    result_semantic_projection_contract: Literal[
        "full_public_events_effects_validity_answer.v1"
    ] = "full_public_events_effects_validity_answer.v1"
    historical_runtime_selected: Literal[False] = False
    historical_results_mutated: Literal[False] = False
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_binding(self) -> RuntimeImplementationBinding:
        if tuple(item.symbol for item in self.runtime_symbols) != self.required_symbols:
            raise ValueError("Runtime symbol binding is incomplete or reordered")
        if any(
            item.relative_path != self.runtime_file.relative_path for item in self.runtime_symbols
        ):
            raise ValueError("Runtime symbol binding crosses a source file")
        if not validate_identity(self, "binding_id", "current_runtime_implementation_binding:"):
            raise ValueError("Runtime implementation binding identity differs")
        return self


class RuntimeSemanticContract(FrozenModel):
    contract_id: str = Field(min_length=1)
    external_anchor_id: str = Field(min_length=1)
    runtime_implementation_binding_id: str = Field(min_length=1)
    predecessor_drift_audit_id: Literal[
        "finance_v26_193_result_drift_decomposition_audit:"
        "303c64dd2cb4682dc66fd7374e4263ee39072d9361394baf7bb794e6ad8c7fdf"
    ]
    compared_result_count: Literal[192] = 192
    canonical_result_match_count: Literal[144] = 144
    drift_result_count: Literal[48] = 48
    drift_capability_family: Literal["semantic_reconciliation"] = "semantic_reconciliation"
    full_public_event_payload_match_count: Literal[0] = 0
    full_public_event_payload_drift_count: Literal[48] = 48
    public_effect_match_count: Literal[48] = 48
    public_effect_drift_count: Literal[0] = 0
    validity_answer_match_count: Literal[48] = 48
    validity_answer_drift_count: Literal[0] = 0
    output_hash_drift_count: Literal[48] = 48
    experiment_condition_changed: Literal[True] = True
    semantic_equivalence_claimed: Literal[False] = False
    historical_result_rewrite_count: Literal[0] = 0
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_contract(self) -> RuntimeSemanticContract:
        if (
            self.canonical_result_match_count + self.drift_result_count
            != self.compared_result_count
            or self.full_public_event_payload_match_count
            + self.full_public_event_payload_drift_count
            != self.drift_result_count
            or self.public_effect_match_count + self.public_effect_drift_count
            != self.drift_result_count
            or self.validity_answer_match_count + self.validity_answer_drift_count
            != self.drift_result_count
        ):
            raise ValueError("Runtime semantic denominator differs")
        if not validate_identity(self, "contract_id", "current_runtime_semantic_contract:"):
            raise ValueError("Runtime semantic contract identity differs")
        return self


class ComponentImplementationBinding(FrozenModel):
    binding_id: str = Field(min_length=1)
    binding_kind: Literal[
        "json_renderer",
        "stage_one_request_builder_certificate",
        "certified_client_transport",
        "privacy_resource_recovery_persistence",
        "authoritative_kernel_runner",
    ]
    external_anchor_id: str = Field(min_length=1)
    runtime_semantic_contract_id: str = Field(min_length=1)
    files: tuple[FileBinding, ...] = Field(min_length=1)
    symbols: tuple[SymbolBinding, ...] = Field(min_length=1)
    source_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    source_tree: str = Field(pattern=r"^[0-9a-f]{40}$")
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_binding(self) -> ComponentImplementationBinding:
        paths = tuple(item.relative_path for item in self.files)
        if paths != tuple(sorted(paths)) or len(set(paths)) != len(paths):
            raise ValueError("implementation file binding is not canonical")
        allowed = set(paths)
        if any(item.relative_path not in allowed for item in self.symbols):
            raise ValueError("symbol is not owned by an implementation file")
        if not validate_identity(
            self, "binding_id", f"{self.binding_kind}_implementation_binding:"
        ):
            raise ValueError("component implementation binding identity differs")
        return self


class KernelResourcePersistenceContract(FrozenModel):
    contract_id: str = Field(min_length=1)
    external_anchor_id: str = Field(min_length=1)
    runtime_semantic_contract_id: str = Field(min_length=1)
    request_builder_binding_id: str = Field(min_length=1)
    certified_client_binding_id: str = Field(min_length=1)
    privacy_persistence_binding_id: str = Field(min_length=1)
    maximum_primary_requests: Literal[21] = 21
    maximum_provider_calls: Literal[23] = 23
    maximum_transport_invocations: Literal[24] = 24
    maximum_rollout_tokens: Literal[1120000] = 1120000
    maximum_prompt_utf8_bytes: Literal[60000] = 60000
    maximum_transport_replacements: Literal[1] = 1
    privacy_envelope_before_semantic_parse: Literal[True] = True
    payload_projection_before_semantic_parse: Literal[True] = True
    raw_write_required: Literal[True] = True
    result_write_required_for_completed_terminal: Literal[True] = True
    orphan_artifact_blocks_retry: Literal[True] = True
    fixture_response_forbidden_from_production_input: Literal[True] = True
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_contract(self) -> KernelResourcePersistenceContract:
        if not validate_identity(
            self, "contract_id", "authoritative_kernel_resource_persistence_contract:"
        ):
            raise ValueError("resource/persistence contract identity differs")
        return self


class AuthoritativeRunnerPackage(FrozenModel):
    package_id: str = Field(min_length=1)
    source_runner_package_id: str = Field(min_length=1)
    source_runner_package_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    external_anchor_id: str = Field(min_length=1)
    runtime_semantic_contract_id: str = Field(min_length=1)
    runtime_implementation_binding_id: str = Field(min_length=1)
    renderer_binding_id: str = Field(min_length=1)
    request_builder_binding_id: str = Field(min_length=1)
    certified_client_binding_id: str = Field(min_length=1)
    privacy_persistence_binding_id: str = Field(min_length=1)
    authoritative_kernel_runner_binding_id: str = Field(min_length=1)
    resource_persistence_contract_id: str = Field(min_length=1)
    capability_family: str = Field(min_length=1)
    depth: str = Field(min_length=1)
    schedule_ids: tuple[str, ...] = Field(min_length=1, max_length=4)
    topological_component_keys: tuple[str, ...] = Field(min_length=1, max_length=4)
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_package(self) -> AuthoritativeRunnerPackage:
        if len(self.schedule_ids) != len(self.topological_component_keys):
            raise ValueError("kernel Runner Package Schedule denominator differs")
        if not validate_identity(self, "package_id", "authoritative_kernel_runner_package:"):
            raise ValueError("kernel Runner Package identity differs")
        return self


class AuthoritativeRunnerPackageCatalog(FrozenModel):
    catalog_id: str = Field(min_length=1)
    packages: tuple[AuthoritativeRunnerPackage, ...] = Field(min_length=32, max_length=32)
    expected_source_runner_package_ids: tuple[str, ...] = Field(min_length=32, max_length=32)
    package_count: Literal[32] = 32
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_catalog(self) -> AuthoritativeRunnerPackageCatalog:
        if len({item.package_id for item in self.packages}) != 32:
            raise ValueError("kernel Runner Package denominator differs")
        if tuple(sorted(item.source_runner_package_id for item in self.packages)) != (
            self.expected_source_runner_package_ids
        ):
            raise ValueError("kernel Runner Package source set differs")
        if not validate_identity(self, "catalog_id", "authoritative_kernel_package_catalog:"):
            raise ValueError("kernel Package Catalog identity differs")
        return self


class AuthoritativeDevelopmentJob(FrozenModel):
    job_id: str = Field(min_length=1)
    source_job_id: str = Field(min_length=1)
    source_job_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    package_id: str = Field(min_length=1)
    source_runner_package_id: str = Field(min_length=1)
    external_anchor_id: str = Field(min_length=1)
    runtime_semantic_contract_id: str = Field(min_length=1)
    runtime_implementation_binding_id: str = Field(min_length=1)
    renderer_binding_id: str = Field(min_length=1)
    request_builder_binding_id: str = Field(min_length=1)
    certified_client_binding_id: str = Field(min_length=1)
    privacy_persistence_binding_id: str = Field(min_length=1)
    authoritative_kernel_runner_binding_id: str = Field(min_length=1)
    resource_persistence_contract_id: str = Field(min_length=1)
    replica_index: int = Field(ge=0, le=5)
    raw_namespace: str = Field(min_length=1)
    result_namespace: str = Field(min_length=1)
    deterministic_seed_id: str = Field(min_length=1)
    provider_calls: Literal[0] = 0
    empirical_outcome: Literal[False] = False
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_job(self) -> AuthoritativeDevelopmentJob:
        parent = self.model_dump(
            mode="json",
            include={
                "source_job_id",
                "package_id",
                "runtime_semantic_contract_id",
                "runtime_implementation_binding_id",
                "renderer_binding_id",
                "request_builder_binding_id",
                "certified_client_binding_id",
                "privacy_persistence_binding_id",
                "authoritative_kernel_runner_binding_id",
                "resource_persistence_contract_id",
                "replica_index",
            },
        )
        if self.raw_namespace != canonical_hash(
            parent, prefix="authoritative_kernel_raw_namespace:"
        ):
            raise ValueError("kernel Job Raw namespace differs")
        if self.result_namespace != canonical_hash(
            parent, prefix="authoritative_kernel_result_namespace:"
        ):
            raise ValueError("kernel Job Result namespace differs")
        if self.deterministic_seed_id != canonical_hash(
            parent, prefix="authoritative_kernel_deterministic_seed:"
        ):
            raise ValueError("kernel Job deterministic seed differs")
        if not validate_identity(self, "job_id", "authoritative_kernel_development_job:"):
            raise ValueError("kernel Development Job identity differs")
        return self


class AuthoritativeDevelopmentManifest(FrozenModel):
    manifest_id: str = Field(min_length=1)
    package_catalog_id: str = Field(min_length=1)
    external_anchor_id: str = Field(min_length=1)
    runtime_semantic_contract_id: str = Field(min_length=1)
    jobs: tuple[AuthoritativeDevelopmentJob, ...] = Field(min_length=192, max_length=192)
    expected_job_ids: tuple[str, ...] = Field(min_length=192, max_length=192)
    source_job_ids: tuple[str, ...] = Field(min_length=192, max_length=192)
    package_count: Literal[32] = 32
    replica_count: Literal[6] = 6
    job_count: Literal[192] = 192
    provider_calls: Literal[0] = 0
    development_model_outcomes: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_manifest(self) -> AuthoritativeDevelopmentManifest:
        job_ids = tuple(item.job_id for item in self.jobs)
        if len(set(job_ids)) != 192 or self.expected_job_ids != tuple(sorted(job_ids)):
            raise ValueError("kernel Manifest Job denominator differs")
        if self.source_job_ids != tuple(sorted(item.source_job_id for item in self.jobs)):
            raise ValueError("kernel Manifest source Job set differs")
        if len({item.package_id for item in self.jobs}) != 32:
            raise ValueError("kernel Manifest Package denominator differs")
        if len({(item.package_id, item.replica_index) for item in self.jobs}) != 192:
            raise ValueError("kernel Manifest Package x Replica cells differ")
        if (
            len({item.raw_namespace for item in self.jobs}) != 192
            or len({item.result_namespace for item in self.jobs}) != 192
        ):
            raise ValueError("kernel Manifest namespaces are not unique")
        if not validate_identity(self, "manifest_id", "authoritative_kernel_manifest:"):
            raise ValueError("kernel Manifest identity differs")
        return self


class AuthoritativeRunnerContract(FrozenModel):
    runner_id: str = Field(min_length=1)
    manifest_id: str = Field(min_length=1)
    package_catalog_id: str = Field(min_length=1)
    external_anchor_id: str = Field(min_length=1)
    runtime_semantic_contract_id: str = Field(min_length=1)
    runtime_implementation_binding_id: str = Field(min_length=1)
    renderer_binding_id: str = Field(min_length=1)
    request_builder_binding_id: str = Field(min_length=1)
    certified_client_binding_id: str = Field(min_length=1)
    privacy_persistence_binding_id: str = Field(min_length=1)
    authoritative_kernel_runner_binding_id: str = Field(min_length=1)
    resource_persistence_contract_id: str = Field(min_length=1)
    job_count: Literal[192] = 192
    one_current_prompt_at_a_time: Literal[True] = True
    scripted_reference_only: Literal[False] = False
    certified_provider_path_instantiated: Literal[True] = True
    fixture_response_in_production_input: Literal[False] = False
    online_execution_authorized: Literal[False] = False
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_runner(self) -> AuthoritativeRunnerContract:
        if not validate_identity(self, "runner_id", "authoritative_execution_kernel_runner:"):
            raise ValueError("authoritative Runner identity differs")
        return self


class AuthoritativeExecutionContract(FrozenModel):
    contract_id: str = Field(min_length=1)
    runner_id: str = Field(min_length=1)
    manifest_id: str = Field(min_length=1)
    package_catalog_id: str = Field(min_length=1)
    external_anchor_id: str = Field(min_length=1)
    runtime_semantic_contract_id: str = Field(min_length=1)
    implementation_parent_ids: tuple[str, ...] = Field(min_length=6, max_length=6)
    resource_persistence_contract_id: str = Field(min_length=1)
    exact_job_count: Literal[192] = 192
    exact_registered_invocation_count: Literal[792] = 792
    fresh_outcome_authority_materialized: Literal[False] = False
    online_execution_authorized: Literal[False] = False
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_execution(self) -> AuthoritativeExecutionContract:
        if len(set(self.implementation_parent_ids)) != 6:
            raise ValueError("Execution Contract implementation parents are not distinct")
        if not validate_identity(self, "contract_id", "authoritative_execution_kernel_contract:"):
            raise ValueError("Execution Contract identity differs")
        return self


class KernelInvocationAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    execution_contract_id: str = Field(min_length=1)
    manifest_id: str = Field(min_length=1)
    registered_invocation_count: Literal[792] = 792
    rendered_prompt_count: Literal[792] = 792
    request_body_count: Literal[792] = 792
    request_binding_certificate_count: Literal[792] = 792
    dynamic_resource_certificate_count: Literal[792] = 792
    certified_client_invocation_count: Literal[792] = 792
    transmitted_body_hash_match_count: Literal[792] = 792
    consumed_certificate_match_count: Literal[792] = 792
    privacy_envelope_before_semantic_parse_count: Literal[792] = 792
    privacy_projection_before_semantic_parse_count: Literal[792] = 792
    raw_writer_completion_count: Literal[192] = 192
    result_writer_completion_count: Literal[192] = 192
    orphan_blocking_control_count: Literal[1] = 1
    fixture_response_production_input_count: Literal[0] = 0
    provider_calls: Literal[0] = 0
    development_model_outcomes: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> KernelInvocationAudit:
        if not validate_identity(
            self, "audit_id", "authoritative_execution_kernel_invocation_audit:"
        ):
            raise ValueError("kernel invocation audit identity differs")
        return self


class AttackResult(FrozenModel):
    attack_id: str = Field(min_length=1)
    attack_name: str = Field(min_length=1)
    target_stage: str = Field(min_length=1)
    expected_reason: str = Field(min_length=1)
    actual_reason: str = Field(min_length=1)
    target_validator_reached: Literal[True] = True
    fully_rehashed: Literal[True] = True
    rejected: Literal[True] = True
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_attack(self) -> AttackResult:
        if self.expected_reason != self.actual_reason:
            raise ValueError("attack rejection reason differs")
        if not validate_identity(self, "attack_id", "execution_kernel_attack_result:"):
            raise ValueError("attack result identity differs")
        return self


class DestructiveAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    execution_contract_id: str = Field(min_length=1)
    predecessor_attack_regression_count: Literal[14] = 14
    predecessor_attack_regression_pass_count: Literal[14] = 14
    attacks: tuple[AttackResult, ...] = Field(min_length=12, max_length=12)
    attack_count: Literal[12] = 12
    rejection_count: Literal[12] = 12
    accepted_count: Literal[0] = 0
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> DestructiveAudit:
        if len({item.attack_name for item in self.attacks}) != 12:
            raise ValueError("execution-kernel attack denominator differs")
        if not validate_identity(
            self, "audit_id", "authoritative_execution_kernel_destructive_audit:"
        ):
            raise ValueError("destructive audit identity differs")
        return self


class OutcomeAuthorityGapRegister(FrozenModel):
    register_id: str = Field(min_length=1)
    execution_contract_id: str = Field(min_length=1)
    missing_layers: tuple[
        Literal[
            "fresh_terminal_registry_binding",
            "fresh_raw_execution_descriptor_contract",
            "fresh_job_result_descriptor_contract",
            "fresh_job_bound_attempt_trace_contract",
            "fresh_outcome_row_contract",
            "fresh_exact_evidence_set_evaluator",
        ],
        ...,
    ] = Field(min_length=6, max_length=6)
    materialized_layers: tuple[str, ...] = ()
    empirical_rows: Literal[0] = 0
    online_execution_authority: Literal[False] = False
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_gap(self) -> OutcomeAuthorityGapRegister:
        if len(set(self.missing_layers)) != 6:
            raise ValueError("fresh Outcome gap register denominator differs")
        if not validate_identity(
            self, "register_id", "finance_v26_194_outcome_authority_gap_register:"
        ):
            raise ValueError("Outcome gap register identity differs")
        return self


class StaticGate(FrozenModel):
    name: str = Field(min_length=1)
    passed: Literal[True] = True
    evidence_ids: tuple[str, ...] = Field(min_length=1)


class StaticAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    gates: tuple[StaticGate, ...] = Field(min_length=18)
    gate_count: int = Field(ge=18)
    passed_count: int = Field(ge=18)
    failed_count: Literal[0] = 0
    provider_calls: Literal[0] = 0
    development_model_outcomes: Literal[0] = 0
    empirical_rows: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> StaticAudit:
        if self.gate_count != len(self.gates) or self.passed_count != len(self.gates):
            raise ValueError("static Gate denominator differs")
        if len({item.name for item in self.gates}) != len(self.gates):
            raise ValueError("static Gate names are not unique")
        if not validate_identity(self, "audit_id", "finance_v26_194_static_audit:"):
            raise ValueError("static audit identity differs")
        return self


class ProspectiveTransition(FrozenModel):
    transition_id: str = Field(min_length=1)
    execution_contract_id: str = Field(min_length=1)
    static_audit_id: str = Field(min_length=1)
    outcome_gap_register_id: str = Field(min_length=1)
    next_stage: Literal[
        "json_explicit_authoritative_execution_kernel_parent_binding_independent_audit_only"
    ] = "json_explicit_authoritative_execution_kernel_parent_binding_independent_audit_only"
    online_execution_authorized: Literal[False] = False
    fresh_outcome_authority_authorized: Literal[False] = False
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_transition(self) -> ProspectiveTransition:
        if not validate_identity(
            self, "transition_id", "finance_v26_194_execution_kernel_transition:"
        ):
            raise ValueError("v26.194 transition identity differs")
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
    scope: Literal["sealed_evidence", "distribution"]
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_manifest(self) -> ArtifactManifest:
        paths = tuple(item.relative_path for item in self.members)
        if paths != tuple(sorted(paths)) or len(set(paths)) != len(paths):
            raise ValueError("artifact member set is not canonical")
        if self.file_count != len(self.members) or self.total_byte_count != sum(
            item.byte_count for item in self.members
        ):
            raise ValueError("artifact aggregate differs")
        expected_root = canonical_hash(
            tuple(item.model_dump(mode="json") for item in self.members),
            prefix=f"finance_v26_194_{self.scope}_artifact_root:",
        )
        if self.artifact_root != expected_root:
            raise ValueError("artifact Root differs")
        if not validate_identity(
            self, "manifest_id", f"finance_v26_194_{self.scope}_artifact_manifest:"
        ):
            raise ValueError("artifact Manifest identity differs")
        return self


class PreflightReport(FrozenModel):
    report_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    authorization_id: str = Field(min_length=1)
    external_anchor_id: str = Field(min_length=1)
    source_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    source_tree: str = Field(pattern=r"^[0-9a-f]{40}$")
    runtime_semantic_contract_id: str = Field(min_length=1)
    runtime_implementation_binding_id: str = Field(min_length=1)
    package_catalog_id: str = Field(min_length=1)
    manifest_id: str = Field(min_length=1)
    runner_id: str = Field(min_length=1)
    execution_contract_id: str = Field(min_length=1)
    invocation_audit_id: str = Field(min_length=1)
    destructive_audit_id: str = Field(min_length=1)
    outcome_gap_register_id: str = Field(min_length=1)
    static_audit_id: str = Field(min_length=1)
    transition_id: str = Field(min_length=1)
    sealed_evidence_manifest_id: str = Field(min_length=1)
    sealed_evidence_artifact_root: str = Field(min_length=1)
    decision: Literal[
        "authoritative_execution_kernel_parent_binding_preflight_passed_"
        "independent_audit_required_online_and_fresh_outcome_authority_blocked"
    ]
    runtime_choice: Literal["option_b_current_runtime"] = "option_b_current_runtime"
    experiment_condition_changed: Literal[True] = True
    semantic_equivalence_claimed: Literal[False] = False
    exact_package_count: Literal[32] = 32
    exact_job_count: Literal[192] = 192
    exact_registered_invocation_count: Literal[792] = 792
    execution_kernel_preflight_gates_passed: Literal[True] = True
    independent_audit_required: Literal[True] = True
    online_development_execution_authorized: Literal[False] = False
    fresh_outcome_authority_materialized: Literal[False] = False
    provider_calls: Literal[0] = 0
    development_model_outcomes: Literal[0] = 0
    empirical_rows: Literal[0] = 0
    mapper_rows: Literal[0] = 0
    state_rows: Literal[0] = 0
    frequency_rows: Literal[0] = 0
    contribution_rows: Literal[0] = 0
    vtdo_rows: Literal[0] = 0
    training_rows: Literal[0] = 0
    release_rows: Literal[0] = 0
    production_rows: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_report(self) -> PreflightReport:
        if not validate_identity(
            self, "report_id", "finance_v26_194_execution_kernel_preflight_report:"
        ):
            raise ValueError("v26.194 report identity differs")
        return self
