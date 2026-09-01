from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.hashing import canonical_hash

SCHEMA_VERSION = "fresh_artifact_backed_outcome_authority_preflight.v1"
AUTHORIZED_STAGE = "fresh_artifact_backed_outcome_authority_preflight_only"
NEXT_STAGE = "fresh_artifact_backed_outcome_authority_preflight_independent_audit_only"


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
    audit_sha256: Literal["a1b70efd0a73261a71ac6d8e62e21fb590baecb294c2a7dc69dc191542ecfcc3"]
    audit_byte_count: Literal[8598] = 8598
    audit_decision: Literal[
        "authoritative_execution_kernel_parent_binding_independent_audit_passed_"
        "fresh_artifact_backed_outcome_authority_preflight_only_authorized"
    ]
    consumed_stage: Literal["fresh_artifact_backed_outcome_authority_preflight_only"] = (
        "fresh_artifact_backed_outcome_authority_preflight_only"
    )
    provider_calls_authorized: Literal[False] = False
    development_outcomes_authorized: Literal[False] = False
    empirical_estimates_authorized: Literal[False] = False
    online_execution_authorized: Literal[False] = False
    historical_rewrite_authorized: Literal[False] = False
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_authorization(self) -> ExternalAuditAuthorization:
        if not validate_identity(
            self,
            "authorization_id",
            "finance_v26_195_external_authorization:",
        ):
            raise ValueError("v26.195 external authorization identity differs")
        return self


class V194ExternalAnchor(FrozenModel):
    anchor_id: str = Field(min_length=1)
    authorization_id: str = Field(min_length=1)
    source_commit: Literal["2a5b8322a94e7be84065375dd6720e532bfe05cb"]
    source_tree: Literal["3f75f98f8ad11a3a7125523ee83233b23036a82d"]
    report_id: Literal[
        "finance_v26_194_execution_kernel_preflight_report:"
        "f95f59b95819f081153774abba04a26f255d41b6ce7ce819db031625faec9747"
    ]
    sealed_manifest_id: Literal[
        "finance_v26_194_sealed_evidence_artifact_manifest:"
        "5193780194eeaf7e7b53ce4954c01e835300f22cd8b2bad500402266e5092207"
    ]
    sealed_artifact_root: Literal[
        "finance_v26_194_sealed_evidence_artifact_root:"
        "91c2492673c1ac9ba3c0c90bc1a17b20547355235abe357bb11af7383ee17b8f"
    ]
    distribution_manifest_id: Literal[
        "finance_v26_194_distribution_artifact_manifest:"
        "69031f0f4625b3ffbf74be0c02006011bc51ef60d8628266106dbe7b4632fe15"
    ]
    distribution_artifact_root: Literal[
        "finance_v26_194_distribution_artifact_root:"
        "d9a9bf6d4345def14bd01379818e898a88b380fc95363ece291980d295e84b10"
    ]
    execution_contract_id: Literal[
        "authoritative_execution_kernel_contract:"
        "53dccfcd1a4516ae8c79c9b64cd41193b99e8594598a25049335db565070786d"
    ]
    manifest_id: Literal[
        "authoritative_kernel_manifest:"
        "15da508affe0a4727f85fbc727ac1a4b6772b014fdb6a40d4e5c93ae374cd803"
    ]
    runner_id: Literal[
        "authoritative_execution_kernel_runner:"
        "7a3b8ae6bfb178c351f10a00c08c18373ee61f0bf64b500f245644cc99e1e034"
    ]
    package_catalog_id: Literal[
        "authoritative_kernel_package_catalog:"
        "cd7bee78c7ed7bc618d7b4d6441546264d1a6392336dceedee9abb89ea7e7211"
    ]
    runtime_semantic_contract_id: Literal[
        "current_runtime_semantic_contract:"
        "68cbbcf9d0e562b046bd67832aeab533d474f458f4b8d342ee3fe3d4549960a6"
    ]
    runtime_implementation_binding_id: Literal[
        "current_runtime_implementation_binding:"
        "0c65f9a608bef22292e6dde952e6ca028a32a615a900e77c23bc335e2249bf0b"
    ]
    exact_files: tuple[FileBinding, ...] = Field(min_length=22, max_length=22)
    exact_file_count: Literal[22] = 22
    exact_file_match_count: Literal[22] = 22
    candidate_report_values_used_as_expectations: Literal[False] = False
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_anchor(self) -> V194ExternalAnchor:
        paths = tuple(item.relative_path for item in self.exact_files)
        if paths != tuple(sorted(paths)) or len(set(paths)) != 22:
            raise ValueError("v26.194 exact file vector differs")
        if not validate_identity(self, "anchor_id", "finance_v26_194_external_anchor:"):
            raise ValueError("v26.194 external anchor identity differs")
        return self


class OutcomeWriterImplementationBinding(FrozenModel):
    binding_id: str = Field(min_length=1)
    external_anchor_id: str = Field(min_length=1)
    source_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    source_tree: str = Field(pattern=r"^[0-9a-f]{40}$")
    source_file: FileBinding
    symbols: tuple[SymbolBinding, ...] = Field(min_length=3, max_length=3)
    exact_v194_writer_class: Literal["NoReplaceKernelJournalWriter"] = (
        "NoReplaceKernelJournalWriter"
    )
    raw_before_result_required: Literal[True] = True
    old_fixture_complete_payload_admissible: Literal[False] = False
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_binding(self) -> OutcomeWriterImplementationBinding:
        if tuple(item.symbol for item in self.symbols) != (
            "FreshOutcomeArtifactWriter",
            "FreshOutcomeArtifactWriter.write_raw",
            "FreshOutcomeArtifactWriter.write_result",
        ):
            raise ValueError("fresh Outcome writer symbols differ")
        if any(item.relative_path != self.source_file.relative_path for item in self.symbols):
            raise ValueError("fresh Outcome writer symbol crosses its source file")
        if not validate_identity(
            self,
            "binding_id",
            "fresh_outcome_writer_implementation_binding:",
        ):
            raise ValueError("fresh Outcome writer binding identity differs")
        return self


class FreshAuthorityAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    external_anchor_id: str = Field(min_length=1)
    execution_contract_id: str = Field(min_length=1)
    manifest_id: str = Field(min_length=1)
    runner_id: str = Field(min_length=1)
    package_catalog_id: str = Field(min_length=1)
    writer_implementation_binding_id: str = Field(min_length=1)
    terminal_registry_id: str = Field(min_length=1)
    raw_descriptor_contract_id: str = Field(min_length=1)
    result_descriptor_contract_id: str = Field(min_length=1)
    attempt_trace_contract_id: str = Field(min_length=1)
    outcome_row_contract_id: str = Field(min_length=1)
    evaluator_contract_id: str = Field(min_length=1)
    materialized_layers: tuple[
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
    fresh_layer_count: Literal[6] = 6
    exact_job_parent_match_count: Literal[192] = 192
    old_v26_186_authority_identity_reuse_count: Literal[0] = 0
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> FreshAuthorityAudit:
        if len(set(self.materialized_layers)) != 6:
            raise ValueError("fresh Outcome authority layer denominator differs")
        if not validate_identity(self, "audit_id", "finance_v26_195_fresh_authority_audit:"):
            raise ValueError("fresh authority audit identity differs")
        return self


class EvidenceDagAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    fresh_authority_audit_id: str = Field(min_length=1)
    evaluation_id: str = Field(min_length=1)
    writer_implementation_binding_id: str = Field(min_length=1)
    exact_job_count: Literal[192] = 192
    raw_descriptor_count: Literal[192] = 192
    result_descriptor_count: Literal[192] = 192
    attempt_trace_count: Literal[192] = 192
    outcome_row_count: Literal[192] = 192
    raw_result_file_count: Literal[384] = 384
    actual_byte_match_count: Literal[384] = 384
    canonical_json_match_count: Literal[384] = 384
    exact_job_set_match: Literal[True] = True
    unique_layer_identity_match: Literal[True] = True
    raw_before_result_write_count: Literal[192] = 192
    writer_orphan_count: Literal[0] = 0
    old_fixture_complete_payload_rejection_count: Literal[1] = 1
    provider_artifact_count: Literal[0] = 0
    token_usage: Literal[0] = 0
    development_model_outcomes: Literal[0] = 0
    formal_empirical_rows: Literal[0] = 0
    empirical_estimates: Literal[0] = 0
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> EvidenceDagAudit:
        if not validate_identity(self, "audit_id", "finance_v26_195_evidence_dag_audit:"):
            raise ValueError("fresh evidence DAG audit identity differs")
        return self


class AttackResult(FrozenModel):
    attack_id: str = Field(min_length=1)
    attack_name: str = Field(min_length=1)
    target_layer: str = Field(min_length=1)
    expected_reason: str = Field(min_length=1)
    actual_reason: str = Field(min_length=1)
    fully_rehashed: bool
    target_validator_reached: Literal[True] = True
    rejected: Literal[True] = True
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_attack(self) -> AttackResult:
        if self.expected_reason != self.actual_reason:
            raise ValueError("fresh Outcome attack rejection reason differs")
        if not validate_identity(self, "attack_id", "fresh_outcome_authority_attack:"):
            raise ValueError("fresh Outcome attack identity differs")
        return self


class DestructiveAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    evaluator_contract_id: str = Field(min_length=1)
    predecessor_execution_kernel_attack_count: Literal[12] = 12
    predecessor_execution_kernel_rejection_count: Literal[12] = 12
    attacks: tuple[AttackResult, ...] = Field(min_length=20)
    attack_count: int = Field(ge=20)
    rejection_count: int = Field(ge=20)
    accepted_count: Literal[0] = 0
    fully_rehashed_attack_count: int = Field(ge=10)
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> DestructiveAudit:
        if (
            self.attack_count != len(self.attacks)
            or self.rejection_count != len(self.attacks)
            or self.fully_rehashed_attack_count
            != sum(int(item.fully_rehashed) for item in self.attacks)
            or len({item.attack_name for item in self.attacks}) != len(self.attacks)
        ):
            raise ValueError("fresh Outcome destructive denominator differs")
        if not validate_identity(
            self,
            "audit_id",
            "finance_v26_195_fresh_outcome_destructive_audit:",
        ):
            raise ValueError("fresh Outcome destructive audit identity differs")
        return self


class StaticGate(FrozenModel):
    name: str = Field(min_length=1)
    passed: Literal[True] = True
    evidence_ids: tuple[str, ...] = Field(min_length=1)


class StaticAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    gates: tuple[StaticGate, ...] = Field(min_length=20)
    gate_count: int = Field(ge=20)
    passed_count: int = Field(ge=20)
    failed_count: Literal[0] = 0
    provider_calls: Literal[0] = 0
    development_model_outcomes: Literal[0] = 0
    empirical_rows: Literal[0] = 0
    empirical_estimates: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> StaticAudit:
        if (
            self.gate_count != len(self.gates)
            or self.passed_count != len(self.gates)
            or len({item.name for item in self.gates}) != len(self.gates)
        ):
            raise ValueError("fresh Outcome static Gate denominator differs")
        if not validate_identity(self, "audit_id", "finance_v26_195_static_audit:"):
            raise ValueError("fresh Outcome static audit identity differs")
        return self


class ProspectiveTransition(FrozenModel):
    transition_id: str = Field(min_length=1)
    evaluator_contract_id: str = Field(min_length=1)
    evaluation_id: str = Field(min_length=1)
    destructive_audit_id: str = Field(min_length=1)
    static_audit_id: str = Field(min_length=1)
    next_stage: Literal[
        "fresh_artifact_backed_outcome_authority_preflight_independent_audit_only"
    ] = "fresh_artifact_backed_outcome_authority_preflight_independent_audit_only"
    online_execution_authorized: Literal[False] = False
    empirical_evaluation_authorized: Literal[False] = False
    provider_calls: Literal[0] = 0
    schema_version: str = SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_transition(self) -> ProspectiveTransition:
        if not validate_identity(self, "transition_id", "finance_v26_195_transition:"):
            raise ValueError("v26.195 transition identity differs")
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
            raise ValueError("v26.195 artifact member set differs")
        if self.file_count != len(self.members) or self.total_byte_count != sum(
            item.byte_count for item in self.members
        ):
            raise ValueError("v26.195 artifact aggregate differs")
        expected_root = canonical_hash(
            tuple(item.model_dump(mode="json") for item in self.members),
            prefix=f"finance_v26_195_{self.scope}_artifact_root:",
        )
        if self.artifact_root != expected_root:
            raise ValueError("v26.195 artifact Root differs")
        if not validate_identity(
            self,
            "manifest_id",
            f"finance_v26_195_{self.scope}_artifact_manifest:",
        ):
            raise ValueError("v26.195 artifact Manifest identity differs")
        return self


class PreflightReport(FrozenModel):
    report_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    authorization_id: str = Field(min_length=1)
    external_anchor_id: str = Field(min_length=1)
    source_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    source_tree: str = Field(pattern=r"^[0-9a-f]{40}$")
    execution_contract_id: str = Field(min_length=1)
    manifest_id: str = Field(min_length=1)
    runner_id: str = Field(min_length=1)
    package_catalog_id: str = Field(min_length=1)
    writer_implementation_binding_id: str = Field(min_length=1)
    terminal_registry_id: str = Field(min_length=1)
    raw_descriptor_contract_id: str = Field(min_length=1)
    result_descriptor_contract_id: str = Field(min_length=1)
    attempt_trace_contract_id: str = Field(min_length=1)
    outcome_row_contract_id: str = Field(min_length=1)
    evaluator_contract_id: str = Field(min_length=1)
    evaluation_id: str = Field(min_length=1)
    fresh_authority_audit_id: str = Field(min_length=1)
    evidence_dag_audit_id: str = Field(min_length=1)
    destructive_audit_id: str = Field(min_length=1)
    static_audit_id: str = Field(min_length=1)
    transition_id: str = Field(min_length=1)
    sealed_evidence_manifest_id: str = Field(min_length=1)
    sealed_evidence_artifact_root: str = Field(min_length=1)
    decision: Literal[
        "fresh_artifact_backed_outcome_authority_preflight_passed_"
        "independent_audit_required_online_execution_blocked"
    ]
    fresh_layer_count: Literal[6] = 6
    exact_job_count: Literal[192] = 192
    raw_descriptor_count: Literal[192] = 192
    result_descriptor_count: Literal[192] = 192
    attempt_trace_count: Literal[192] = 192
    outcome_row_count: Literal[192] = 192
    raw_result_artifact_count: Literal[384] = 384
    old_v26_186_authority_identity_reuse_count: Literal[0] = 0
    independent_audit_required: Literal[True] = True
    online_development_execution_authorized: Literal[False] = False
    provider_calls: Literal[0] = 0
    development_model_outcomes: Literal[0] = 0
    empirical_rows: Literal[0] = 0
    empirical_estimates: Literal[0] = 0
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
            self,
            "report_id",
            "finance_v26_195_fresh_outcome_preflight_report:",
        ):
            raise ValueError("v26.195 Report identity differs")
        return self
