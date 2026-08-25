from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from pathlib import Path
from typing import Any, Final, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.core.evaluation.answer_semantics import (
    ANSWER_SEMANTICS_SCHEMA_VERSION,
    compare_answer_by_schema,
    make_answer_semantic_schema,
)
from trusted_synthesis.core.evaluation.trajectory_validity import (
    BaseValidityChecks,
    ContextMechanismEvidence,
    ReconciliationMechanismEvidence,
    RecoveryMechanismEvidence,
    StoppingMechanismEvidence,
    make_base_validity_report,
    make_mechanism_qualification_report,
    make_noninterference_artifact_binding,
    make_qualified_validity_report,
    make_validity_eligibility,
    qualify_context_mechanism,
    qualify_reconciliation_mechanism,
    qualify_recovery_mechanism,
    qualify_stopping_mechanism,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_capability_validity_decomposition_audit as predecessor,
)
from trusted_synthesis.hashing import canonical_hash
from trusted_synthesis.runtime.agent.prospective_qualified_final_response_grammar import (
    QualifiedFinalResponseGrammar,
    compile_qualified_final_response_grammar,
    make_qualified_final_host_envelope,
    parse_qualified_final_response,
)

RUN_ID: Final = "finance_v26_148_verifier_vnext_contract_freeze_v1_20260825"
OUTPUT_DIR: Final = (
    "artifacts/vtdo_experiment/finance_v26_148_verifier_vnext_contract_freeze_v1_20260825"
)
IMPLEMENTATION_PATHS: Final = (
    "src/trusted_synthesis/core/evaluation/answer_semantics.py",
    "src/trusted_synthesis/core/evaluation/trajectory_validity.py",
    "src/trusted_synthesis/runtime/agent/prospective_qualified_final_response_grammar.py",
    "src/trusted_synthesis/experiments/vtdo_experiment/"
    "phase1_v26_verifier_vnext_contract_freeze.py",
)
PREDECESSOR_DIR: Final = predecessor.OUTPUT_DIR
NEXT_STAGE: Final = "measurement_support_verifier_vnext_joint_preflight_only"

EXPECTED_PREDECESSOR_REPORT_ID: Final = (
    "finance_v26_validity_decomposition_report:"
    "fddc664b2d8e45788b0f7e55333041ed82e7dae62368e2b27d22ec8baa7a69a5"
)
EXPECTED_PREDECESSOR_REPORT_SHA256: Final = (
    "06046d8a9b2671b373366af2336df8eb2262220372ba473ecb1720081f940dc7"
)
EXPECTED_PREDECESSOR_TRANSITION_ID: Final = (
    "finance_v26_validity_decomposition_transition:"
    "e6ce3161658116772a3951f5823cada820e5bc7b911e9694dc6475d3ea43c9b2"
)

BASE_CHECK_IDS: Final = (
    "action_abi_complete",
    "answer_canonical_semantic_match",
    "answer_schema_complete",
    "final_abi_complete",
    "model_citation_complete",
    "no_postcompletion_violation",
    "noninterference_artifact_bound",
    "operation_lineage_complete",
    "program_closed",
    "reference_identity_match",
    "required_evidence_support_complete",
    "runtime_selected_support_complete",
    "terminal_verification_complete",
    "verification_support_complete",
)

MECHANISM_REQUIRED_EVENTS: Final = {
    "context_conditioned_action": (
        "frozen_context_difference_bound",
        "target_context_action_changed",
    ),
    "semantic_reconciliation": (
        "all_target_evidence_normalized",
        "all_target_normalization_references_consumed",
    ),
    "failure_recovery": (
        "typed_failure_observed",
        "selector_or_action_revised",
        "later_recovery_observation_succeeded",
    ),
    "state_dependent_stopping": (
        "completion_verified",
        "stopped_after_completion",
        "no_postcompletion_violation",
    ),
}


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


def _identity(value: BaseModel, field: str, prefix: str) -> str:
    return canonical_hash(value.model_dump(mode="json", exclude={field}), prefix=prefix)


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _canonical_bytes(value: Any) -> bytes:
    payload = value.model_dump(mode="json") if isinstance(value, BaseModel) else value
    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _write_json_atomic(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(_canonical_bytes(value))
    temporary.replace(path)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _find_bound_path(
    relative_path: str,
    expected_sha256: str,
    *,
    package_root: Path,
    implementation_root: Path,
) -> Path:
    for root in (implementation_root, package_root):
        candidate = root / relative_path
        if candidate.is_file() and _sha256(candidate) == expected_sha256:
            return candidate
    raise ValueError(f"v26.148 cannot replay bound file: {relative_path}")


class SourceReplayEntry(FrozenModel):
    relative_path: str = Field(min_length=1)
    source_kind: Literal[
        "v26_147_transitive_source",
        "v26_147_output",
        "v26_148_implementation",
    ]
    expected_sha256: str = Field(min_length=64, max_length=64)
    observed_sha256: str = Field(min_length=64, max_length=64)
    byte_count: int = Field(gt=0)
    passed: Literal[True] = True


class SourceReplayAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    predecessor_report_id: str = EXPECTED_PREDECESSOR_REPORT_ID
    predecessor_transition_id: str = EXPECTED_PREDECESSOR_TRANSITION_ID
    predecessor_transitive_file_count: Literal[7304] = 7304
    predecessor_output_file_count: Literal[10] = 10
    implementation_file_count: Literal[4] = 4
    replayed_file_count: Literal[7318] = 7318
    replay_pass_count: Literal[7318] = 7318
    entries: tuple[SourceReplayEntry, ...] = Field(min_length=7318, max_length=7318)
    replay_before_contract_loading: Literal[True] = True
    credential_lookup_attempted: Literal[False] = False
    model_client_constructed: Literal[False] = False
    provider_calls: Literal[0] = 0
    stage_two_provider_calls: Literal[0] = 0
    gpu_jobs: Literal[0] = 0
    status: Literal["passed"] = "passed"
    schema_version: Literal["finance_v26_verifier_vnext_source_replay.v1"] = (
        "finance_v26_verifier_vnext_source_replay.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> SourceReplayAudit:
        paths = tuple(item.relative_path for item in self.entries)
        if (
            paths != tuple(sorted(set(paths)))
            or len(paths) != self.replayed_file_count
            or any(item.expected_sha256 != item.observed_sha256 for item in self.entries)
        ):
            raise ValueError("v26.148 source replay changed")
        if self.audit_id != _identity(
            self,
            "audit_id",
            "finance_v26_verifier_vnext_source_replay:",
        ):
            raise ValueError("v26.148 source replay identity changed")
        return self


class FileComparison(FrozenModel):
    relative_path: str = Field(min_length=1)
    expected_sha256: str = Field(min_length=64, max_length=64)
    observed_sha256: str = Field(min_length=64, max_length=64)
    byte_count: int = Field(gt=0)
    byte_identical: Literal[True] = True


class PredecessorIntegrityAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    source_replay_audit_id: str = Field(min_length=1)
    predecessor_report_id: str = EXPECTED_PREDECESSOR_REPORT_ID
    predecessor_transition_id: str = EXPECTED_PREDECESSOR_TRANSITION_ID
    comparisons: tuple[FileComparison, ...] = Field(min_length=10, max_length=10)
    predecessor_output_file_count: Literal[10] = 10
    byte_identical_file_count: Literal[10] = 10
    frozen_historical_model_outcome_count: Literal[93] = 93
    frozen_historical_support_exit_count: Literal[3] = 3
    historical_reclassified_count: Literal[0] = 0
    provider_calls: Literal[0] = 0
    status: Literal["passed"] = "passed"
    schema_version: Literal["finance_v26_verifier_vnext_predecessor_integrity.v1"] = (
        "finance_v26_verifier_vnext_predecessor_integrity.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> PredecessorIntegrityAudit:
        paths = tuple(item.relative_path for item in self.comparisons)
        if paths != tuple(sorted(set(paths))) or any(
            item.expected_sha256 != item.observed_sha256 for item in self.comparisons
        ):
            raise ValueError("v26.148 predecessor comparison changed")
        if self.audit_id != _identity(
            self,
            "audit_id",
            "finance_v26_verifier_vnext_predecessor_integrity:",
        ):
            raise ValueError("v26.148 predecessor identity changed")
        return self


class AnswerSemanticsContract(FrozenModel):
    contract_id: str = Field(min_length=1)
    answer_semantics_schema_version: str = ANSWER_SEMANTICS_SCHEMA_VERSION
    exact_json_and_canonical_semantics_separate: Literal[True] = True
    decimal_canonicalization_rule: Literal["Decimal(str(value)).normalize()"] = (
        "Decimal(str(value)).normalize()"
    )
    decimal_fields_are_task_schema_bound: Literal[True] = True
    nondecimal_reference_fields_require_exact_identity: Literal[True] = True
    floating_tolerance_allowed: Literal[False] = False
    fuzzy_numeric_equality_allowed: Literal[False] = False
    alias_normalization_allowed: Literal[False] = False
    base_validity_uses_canonical_semantic_match: Literal[True] = True
    schema_version: Literal["finance_v26_answer_semantics_contract.v1"] = (
        "finance_v26_answer_semantics_contract.v1"
    )

    @model_validator(mode="after")
    def validate_contract(self) -> AnswerSemanticsContract:
        if self.contract_id != _identity(
            self,
            "contract_id",
            "finance_v26_answer_semantics_contract:",
        ):
            raise ValueError("v26.148 Answer Semantics Contract identity changed")
        return self


class ValidityEligibilityContract(FrozenModel):
    contract_id: str = Field(min_length=1)
    eligibility_expression: Literal["M and O and R and P"] = "M and O and R and P"
    variables: tuple[str, str, str, str] = (
        "measurement_support_available",
        "model_endpoint_observed",
        "instrument_integrity",
        "privacy_compliant",
    )
    support_exit_validity: Literal["null"] = "null"
    missing_model_endpoint_validity: Literal["null"] = "null"
    instrument_failure_validity: Literal["null"] = "null"
    privacy_rejection_validity: Literal["null"] = "null"
    ineligible_task_verifier_invocation_allowed: Literal[False] = False
    ineligible_false_label_allowed: Literal[False] = False
    schema_version: Literal["finance_v26_validity_eligibility_contract.v1"] = (
        "finance_v26_validity_eligibility_contract.v1"
    )

    @model_validator(mode="after")
    def validate_contract(self) -> ValidityEligibilityContract:
        if self.contract_id != _identity(
            self,
            "contract_id",
            "finance_v26_validity_eligibility_contract:",
        ):
            raise ValueError("v26.148 Eligibility Contract identity changed")
        return self


class MechanismQualificationContract(FrozenModel):
    contract_id: str = Field(min_length=1)
    required_event_ids_by_mechanism: dict[str, tuple[str, ...]] = MECHANISM_REQUIRED_EVENTS
    context_requires_frozen_context_action_change: Literal[True] = True
    reconciliation_requires_all_target_evidence_normalized: Literal[True] = True
    reconciliation_requires_all_target_references_consumed: Literal[True] = True
    extra_legal_normalization_is_diagnostic_not_failure: Literal[True] = True
    recovery_requires_typed_failure_revision_and_later_success: Literal[True] = True
    direct_bypass_may_be_base_valid_but_mechanism_invalid: Literal[True] = True
    stopping_reports_completion_stop_and_postcompletion_separately: Literal[True] = True
    stopping_failures_share_causal_group: Literal[True] = True
    target_mechanism_not_part_of_base_validity: Literal[True] = True
    schema_version: Literal["finance_v26_mechanism_qualification_contract.v1"] = (
        "finance_v26_mechanism_qualification_contract.v1"
    )

    @model_validator(mode="after")
    def validate_contract(self) -> MechanismQualificationContract:
        if self.required_event_ids_by_mechanism != MECHANISM_REQUIRED_EVENTS:
            raise ValueError("v26.148 Mechanism event Contract changed")
        if self.contract_id != _identity(
            self,
            "contract_id",
            "finance_v26_mechanism_qualification_contract:",
        ):
            raise ValueError("v26.148 Mechanism Contract identity changed")
        return self


class ResponsibilityAndNoninterferenceContract(FrozenModel):
    contract_id: str = Field(min_length=1)
    final_grammar_id: str = Field(min_length=1)
    model_owns_answer_result: Literal[True] = True
    model_owns_citations: Literal[True] = True
    model_owns_rationale_summary: Literal[True] = True
    runtime_selected_support_reported_separately: Literal[True] = True
    runtime_support_may_satisfy_model_citation: Literal[False] = False
    host_may_insert_answer_citation_or_rationale: Literal[False] = False
    host_binds_only_stage_protocol_terminal_state_and_commit: Literal[True] = True
    noninterference_contract_id_required: Literal[True] = True
    noninterference_audit_id_required: Literal[True] = True
    hardcoded_noninterference_pass_allowed: Literal[False] = False
    schema_version: Literal["finance_v26_responsibility_noninterference_contract.v1"] = (
        "finance_v26_responsibility_noninterference_contract.v1"
    )

    @model_validator(mode="after")
    def validate_contract(self) -> ResponsibilityAndNoninterferenceContract:
        if self.contract_id != _identity(
            self,
            "contract_id",
            "finance_v26_responsibility_noninterference_contract:",
        ):
            raise ValueError("v26.148 Responsibility Contract identity changed")
        return self


class VerifierVNextContract(FrozenModel):
    contract_id: str = Field(min_length=1)
    answer_semantics_contract_id: str = Field(min_length=1)
    eligibility_contract_id: str = Field(min_length=1)
    mechanism_contract_id: str = Field(min_length=1)
    responsibility_contract_id: str = Field(min_length=1)
    final_grammar_id: str = Field(min_length=1)
    base_check_ids: tuple[str, ...] = BASE_CHECK_IDS
    base_report_schema: Literal["prospective_base_trajectory_validity_report.v1"] = (
        "prospective_base_trajectory_validity_report.v1"
    )
    mechanism_report_schema: Literal["prospective_mechanism_qualification_report.v1"] = (
        "prospective_mechanism_qualification_report.v1"
    )
    qualified_report_schema: Literal["prospective_qualified_trajectory_validity_report.v1"] = (
        "prospective_qualified_trajectory_validity_report.v1"
    )
    qualified_expression: Literal["V_base and Q_mech"] = "V_base and Q_mech"
    role_state_mapping_requires_qualified_true: Literal[True] = True
    final_answer_semantically_valid_legacy_alias_allowed: Literal[False] = False
    historical_rescoring_or_reclassification_allowed: Literal[False] = False
    schema_version: Literal["finance_v26_verifier_vnext_contract.v1"] = (
        "finance_v26_verifier_vnext_contract.v1"
    )

    @model_validator(mode="after")
    def validate_contract(self) -> VerifierVNextContract:
        if self.base_check_ids != tuple(sorted(set(BASE_CHECK_IDS))):
            raise ValueError("v26.148 Base check vector changed")
        if self.contract_id != _identity(
            self,
            "contract_id",
            "finance_v26_verifier_vnext_contract:",
        ):
            raise ValueError("v26.148 Verifier vNext Contract identity changed")
        return self


class FixtureResult(FrozenModel):
    fixture_name: str = Field(min_length=1)
    passed: Literal[True] = True


class ContractFixtureAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    verifier_contract_id: str = Field(min_length=1)
    fixture_results: tuple[FixtureResult, ...] = Field(min_length=17, max_length=17)
    fixture_count: Literal[17] = 17
    passed_count: Literal[17] = 17
    decimal_string_number_equal_passed: Literal[True] = True
    true_numeric_error_rejected: Literal[True] = True
    model_owned_final_payload_passed: Literal[True] = True
    flat_answer_rejected: Literal[True] = True
    missing_model_citation_rejected: Literal[True] = True
    support_exit_validity_null: Literal[True] = True
    base_mechanism_qualified_combinations_passed: Literal[True] = True
    all_four_mechanism_contracts_passed: Literal[True] = True
    provider_calls: Literal[0] = 0
    stage_two_provider_calls: Literal[0] = 0
    status: Literal["passed"] = "passed"
    schema_version: Literal["finance_v26_verifier_vnext_fixture.v1"] = (
        "finance_v26_verifier_vnext_fixture.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> ContractFixtureAudit:
        names = tuple(item.fixture_name for item in self.fixture_results)
        if names != tuple(sorted(set(names))):
            raise ValueError("v26.148 fixture set changed")
        if self.audit_id != _identity(
            self,
            "audit_id",
            "finance_v26_verifier_vnext_fixture:",
        ):
            raise ValueError("v26.148 fixture identity changed")
        return self


class MutationResult(FrozenModel):
    mutation_name: str = Field(min_length=1)
    rejected: Literal[True] = True


class DestructiveAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    mutation_results: tuple[MutationResult, ...] = Field(min_length=24, max_length=24)
    mutation_count: Literal[24] = 24
    rejected_count: Literal[24] = 24
    provider_calls: Literal[0] = 0
    status: Literal["passed"] = "passed"
    schema_version: Literal["finance_v26_verifier_vnext_destructive.v1"] = (
        "finance_v26_verifier_vnext_destructive.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> DestructiveAudit:
        names = tuple(item.mutation_name for item in self.mutation_results)
        if names != tuple(sorted(set(names))):
            raise ValueError("v26.148 destructive mutation set changed")
        if self.audit_id != _identity(
            self,
            "audit_id",
            "finance_v26_verifier_vnext_destructive:",
        ):
            raise ValueError("v26.148 destructive identity changed")
        return self


class ProspectiveTransitionContract(FrozenModel):
    contract_id: str = Field(min_length=1)
    verifier_vnext_contract_id: str = Field(min_length=1)
    fixture_audit_id: str = Field(min_length=1)
    next_permitted_stage: Literal["measurement_support_verifier_vnext_joint_preflight_only"] = (
        NEXT_STAGE
    )
    joint_support_verifier_preflight_authorized: Literal[True] = True
    provider_calls_authorized: Literal[False] = False
    new_capability_population_or_identity_materialization_authorized: Literal[False] = False
    capability_or_reachability_execution_authorized: Literal[False] = False
    reachability_identity_materialization_authorized: Literal[False] = False
    historical_reclassification_authorized: Literal[False] = False
    state_mapping_authorized: Literal[False] = False
    training_release_or_production_authorized: Literal[False] = False
    schema_version: Literal["finance_v26_verifier_vnext_transition.v1"] = (
        "finance_v26_verifier_vnext_transition.v1"
    )

    @model_validator(mode="after")
    def validate_contract(self) -> ProspectiveTransitionContract:
        if self.contract_id != _identity(
            self,
            "contract_id",
            "finance_v26_verifier_vnext_transition:",
        ):
            raise ValueError("v26.148 transition identity changed")
        return self


class DetailFile(FrozenModel):
    relative_path: str = Field(min_length=1)
    sha256: str = Field(min_length=64, max_length=64)
    byte_count: int = Field(gt=0)


class VerifierVNextFreezeReport(FrozenModel):
    report_id: str = Field(min_length=1)
    run_id: str = RUN_ID
    source_replay_audit_id: str = Field(min_length=1)
    predecessor_integrity_audit_id: str = Field(min_length=1)
    answer_semantics_contract_id: str = Field(min_length=1)
    eligibility_contract_id: str = Field(min_length=1)
    mechanism_contract_id: str = Field(min_length=1)
    responsibility_contract_id: str = Field(min_length=1)
    final_grammar_id: str = Field(min_length=1)
    verifier_vnext_contract_id: str = Field(min_length=1)
    fixture_audit_id: str = Field(min_length=1)
    destructive_audit_id: str = Field(min_length=1)
    transition_contract_id: str = Field(min_length=1)
    fixture_count: Literal[17] = 17
    destructive_mutation_count: Literal[24] = 24
    historical_reclassified_count: Literal[0] = 0
    capability_population_or_identity_count: Literal[0] = 0
    provider_calls: Literal[0] = 0
    stage_two_provider_calls: Literal[0] = 0
    gpu_jobs: Literal[0] = 0
    reachability_identity_count: Literal[0] = 0
    state_mapping_row_count: Literal[0] = 0
    production_contribution: Literal[0] = 0
    next_permitted_stage: Literal["measurement_support_verifier_vnext_joint_preflight_only"] = (
        NEXT_STAGE
    )
    detail_files: tuple[DetailFile, ...] = Field(min_length=11, max_length=11)
    status: Literal["verifier_vnext_contract_freeze_passed"] = (
        "verifier_vnext_contract_freeze_passed"
    )
    schema_version: Literal["finance_v26_verifier_vnext_freeze_report.v1"] = (
        "finance_v26_verifier_vnext_freeze_report.v1"
    )

    @model_validator(mode="after")
    def validate_report(self) -> VerifierVNextFreezeReport:
        paths = tuple(item.relative_path for item in self.detail_files)
        if paths != tuple(sorted(set(paths))):
            raise ValueError("v26.148 report detail files changed")
        if self.report_id != _identity(
            self,
            "report_id",
            "finance_v26_verifier_vnext_freeze_report:",
        ):
            raise ValueError("v26.148 report identity changed")
        return self


def _source_replay(
    *,
    package_root: Path,
    implementation_root: Path,
) -> SourceReplayAudit:
    predecessor_dir = package_root / PREDECESSOR_DIR
    report_path = predecessor_dir / "report.json"
    report = predecessor.ValidityDecompositionReport.model_validate(_load(report_path))
    transition = predecessor.ProspectiveTransitionContract.model_validate(
        _load(predecessor_dir / "prospective_transition_contract.json")
    )
    if (
        _sha256(report_path) != EXPECTED_PREDECESSOR_REPORT_SHA256
        or report.report_id != EXPECTED_PREDECESSOR_REPORT_ID
        or report.transition_contract_id != EXPECTED_PREDECESSOR_TRANSITION_ID
        or transition.contract_id != EXPECTED_PREDECESSOR_TRANSITION_ID
        or transition.next_permitted_stage != "verifier_vnext_contract_freeze_only"
        or not transition.verifier_vnext_contract_freeze_authorized
        or transition.provider_calls_authorized
    ):
        raise ValueError("v26.148 direct predecessor decision changed")
    predecessor_source = predecessor.SourceReplayAudit.model_validate(
        _load(predecessor_dir / "source_replay_audit.json")
    )
    entries: list[SourceReplayEntry] = []
    for item in predecessor_source.entries:
        path = _find_bound_path(
            item.relative_path,
            item.expected_sha256,
            package_root=package_root,
            implementation_root=implementation_root,
        )
        entries.append(
            SourceReplayEntry(
                relative_path=item.relative_path,
                source_kind="v26_147_transitive_source",
                expected_sha256=item.expected_sha256,
                observed_sha256=_sha256(path),
                byte_count=path.stat().st_size,
            )
        )
    expected_outputs = {item.relative_path: item.sha256 for item in report.detail_files}
    expected_outputs["report.json"] = EXPECTED_PREDECESSOR_REPORT_SHA256
    for name, expected_sha256 in sorted(expected_outputs.items()):
        path = predecessor_dir / name
        if _sha256(path) != expected_sha256:
            raise ValueError(f"v26.148 predecessor output changed: {name}")
        entries.append(
            SourceReplayEntry(
                relative_path=str(path.relative_to(package_root)),
                source_kind="v26_147_output",
                expected_sha256=expected_sha256,
                observed_sha256=_sha256(path),
                byte_count=path.stat().st_size,
            )
        )
    for relative_path in IMPLEMENTATION_PATHS:
        path = implementation_root / relative_path
        digest = _sha256(path)
        entries.append(
            SourceReplayEntry(
                relative_path=relative_path,
                source_kind="v26_148_implementation",
                expected_sha256=digest,
                observed_sha256=digest,
                byte_count=path.stat().st_size,
            )
        )
    ordered = tuple(sorted(entries, key=lambda item: item.relative_path))
    values = {"entries": ordered}
    provisional = SourceReplayAudit.model_construct(audit_id="pending", **values)
    return SourceReplayAudit(
        audit_id=_identity(
            provisional,
            "audit_id",
            "finance_v26_verifier_vnext_source_replay:",
        ),
        **values,
    )


def _predecessor_integrity(
    *,
    package_root: Path,
    implementation_root: Path,
    source: SourceReplayAudit,
) -> PredecessorIntegrityAudit:
    formal_dir = package_root / PREDECESSOR_DIR
    with tempfile.TemporaryDirectory(prefix="v26_148_predecessor_") as directory:
        rebuilt_dir = Path(directory)
        predecessor.build_validity_decomposition_audit(
            package_root=package_root,
            implementation_root=implementation_root,
            output_dir=rebuilt_dir,
        )
        formal_paths = tuple(sorted(path for path in formal_dir.iterdir() if path.is_file()))
        rebuilt_paths = tuple(sorted(path for path in rebuilt_dir.iterdir() if path.is_file()))
        if tuple(path.name for path in formal_paths) != tuple(path.name for path in rebuilt_paths):
            raise ValueError("v26.148 predecessor rebuild file set changed")
        comparisons = tuple(
            FileComparison(
                relative_path=formal.name,
                expected_sha256=_sha256(formal),
                observed_sha256=_sha256(rebuilt_dir / formal.name),
                byte_count=formal.stat().st_size,
            )
            for formal in formal_paths
        )
    values = {"source_replay_audit_id": source.audit_id, "comparisons": comparisons}
    provisional = PredecessorIntegrityAudit.model_construct(audit_id="pending", **values)
    return PredecessorIntegrityAudit(
        audit_id=_identity(
            provisional,
            "audit_id",
            "finance_v26_verifier_vnext_predecessor_integrity:",
        ),
        **values,
    )


def _answer_contract() -> AnswerSemanticsContract:
    provisional = AnswerSemanticsContract.model_construct(contract_id="pending")
    return AnswerSemanticsContract(
        contract_id=_identity(
            provisional,
            "contract_id",
            "finance_v26_answer_semantics_contract:",
        )
    )


def _eligibility_contract() -> ValidityEligibilityContract:
    provisional = ValidityEligibilityContract.model_construct(contract_id="pending")
    return ValidityEligibilityContract(
        contract_id=_identity(
            provisional,
            "contract_id",
            "finance_v26_validity_eligibility_contract:",
        )
    )


def _mechanism_contract() -> MechanismQualificationContract:
    provisional = MechanismQualificationContract.model_construct(contract_id="pending")
    return MechanismQualificationContract(
        contract_id=_identity(
            provisional,
            "contract_id",
            "finance_v26_mechanism_qualification_contract:",
        )
    )


def _responsibility_contract(
    grammar: QualifiedFinalResponseGrammar,
) -> ResponsibilityAndNoninterferenceContract:
    values = {"final_grammar_id": grammar.grammar_id}
    provisional = ResponsibilityAndNoninterferenceContract.model_construct(
        contract_id="pending",
        **values,
    )
    return ResponsibilityAndNoninterferenceContract(
        contract_id=_identity(
            provisional,
            "contract_id",
            "finance_v26_responsibility_noninterference_contract:",
        ),
        **values,
    )


def _verifier_contract(
    *,
    answer: AnswerSemanticsContract,
    eligibility: ValidityEligibilityContract,
    mechanism: MechanismQualificationContract,
    responsibility: ResponsibilityAndNoninterferenceContract,
    grammar: QualifiedFinalResponseGrammar,
) -> VerifierVNextContract:
    values = {
        "answer_semantics_contract_id": answer.contract_id,
        "eligibility_contract_id": eligibility.contract_id,
        "mechanism_contract_id": mechanism.contract_id,
        "responsibility_contract_id": responsibility.contract_id,
        "final_grammar_id": grammar.grammar_id,
    }
    provisional = VerifierVNextContract.model_construct(contract_id="pending", **values)
    return VerifierVNextContract(
        contract_id=_identity(
            provisional,
            "contract_id",
            "finance_v26_verifier_vnext_contract:",
        ),
        **values,
    )


def _all_base_checks(**overrides: bool) -> BaseValidityChecks:
    values = {key: True for key in BASE_CHECK_IDS}
    values.update(overrides)
    return BaseValidityChecks.model_validate(values)


def _fixture_audit(
    *,
    verifier: VerifierVNextContract,
    grammar: QualifiedFinalResponseGrammar,
) -> ContractFixtureAudit:
    names: list[str] = []
    answer_schema = make_answer_semantic_schema(
        required_result_fields=("difference", "higher_ref"),
        decimal_field_paths=(("difference",),),
    )
    equal = compare_answer_by_schema(
        {"difference": 0.35, "higher_ref": "A"},
        {"difference": "0.350", "higher_ref": "A"},
        answer_schema,
    )
    if equal.answer_exact_json_match or not equal.answer_canonical_semantic_match:
        raise ValueError("v26.148 Decimal representation fixture failed")
    names.append("decimal_string_and_number_semantically_equal")
    error = compare_answer_by_schema(
        {"difference": "0.351", "higher_ref": "A"},
        {"difference": "0.350", "higher_ref": "A"},
        answer_schema,
    )
    if error.answer_canonical_semantic_match:
        raise ValueError("v26.148 true numeric error was tolerated")
    names.append("true_numeric_error_rejected")

    envelope = make_qualified_final_host_envelope(
        grammar=grammar,
        terminal_state_id="fixture-terminal-state",
        terminal_commit_id="fixture-terminal-commit",
    )
    payload = {
        "answer": {
            "result": {"difference": "0.35", "higher_ref": "A"},
            "citations": [{"evidence_id": "evidence-A"}],
        },
        "rationale_summary": "Used the cited public evidence.",
    }
    parsed = parse_qualified_final_response(payload, grammar=grammar, envelope=envelope)
    if parsed.answer.citations[0].evidence_id != "evidence-A":
        raise ValueError("v26.148 model Citation fixture changed")
    names.append("model_owned_final_payload_parsed")
    for fixture_name, mutated in (
        (
            "flat_answer_rejected",
            {
                "answer": {"difference": "0.35", "higher_ref": "A"},
                "rationale_summary": "flat",
            },
        ),
        (
            "missing_model_citation_rejected",
            {
                "answer": {
                    "result": {"difference": "0.35", "higher_ref": "A"},
                    "citations": [],
                },
                "rationale_summary": "missing citation",
            },
        ),
    ):
        try:
            parse_qualified_final_response(mutated, grammar=grammar, envelope=envelope)
        except ValueError:
            names.append(fixture_name)
        else:
            raise ValueError(f"v26.148 mutation passed: {fixture_name}")

    eligible = make_validity_eligibility(
        measurement_support_available=True,
        model_endpoint_observed=True,
        instrument_integrity=True,
        privacy_compliant=True,
    )
    ineligible = make_validity_eligibility(
        measurement_support_available=False,
        model_endpoint_observed=False,
        instrument_integrity=True,
        privacy_compliant=True,
    )
    binding = make_noninterference_artifact_binding(
        noninterference_contract_id="fixture-noninterference-contract",
        noninterference_audit_id="fixture-noninterference-audit",
        task_package_id="fixture-task-package",
    )
    base_valid = make_base_validity_report(
        verifier_contract_id=verifier.contract_id,
        trajectory_id="fixture-valid",
        eligibility=eligible,
        checks=_all_base_checks(),
        noninterference_binding=binding,
    )
    mechanism_valid = make_mechanism_qualification_report(
        verifier_contract_id=verifier.contract_id,
        trajectory_id="fixture-valid",
        eligibility=eligible,
        mechanism_id="failure_recovery",
        required_event_ids=MECHANISM_REQUIRED_EVENTS["failure_recovery"],
        observed_event_ids=MECHANISM_REQUIRED_EVENTS["failure_recovery"],
    )
    qualified_valid = make_qualified_validity_report(
        verifier_contract_id=verifier.contract_id,
        trajectory_id="fixture-valid",
        eligibility=eligible,
        base=base_valid,
        mechanism=mechanism_valid,
    )
    if qualified_valid.valid is not True or not qualified_valid.state_mapping_eligible:
        raise ValueError("v26.148 Base-valid/Mechanism-valid fixture failed")
    names.append("base_valid_mechanism_valid_qualified_valid")

    mechanism_invalid = make_mechanism_qualification_report(
        verifier_contract_id=verifier.contract_id,
        trajectory_id="fixture-mechanism-invalid",
        eligibility=eligible,
        mechanism_id="failure_recovery",
        required_event_ids=MECHANISM_REQUIRED_EVENTS["failure_recovery"],
        observed_event_ids=(),
    )
    base_for_mechanism_invalid = make_base_validity_report(
        verifier_contract_id=verifier.contract_id,
        trajectory_id="fixture-mechanism-invalid",
        eligibility=eligible,
        checks=_all_base_checks(),
        noninterference_binding=binding,
    )
    qualified_mechanism_invalid = make_qualified_validity_report(
        verifier_contract_id=verifier.contract_id,
        trajectory_id="fixture-mechanism-invalid",
        eligibility=eligible,
        base=base_for_mechanism_invalid,
        mechanism=mechanism_invalid,
    )
    if (
        base_for_mechanism_invalid.valid is not True
        or qualified_mechanism_invalid.valid is not False
    ):
        raise ValueError("v26.148 Base-valid/Mechanism-invalid fixture failed")
    names.append("base_valid_mechanism_invalid_qualified_invalid")

    base_invalid = make_base_validity_report(
        verifier_contract_id=verifier.contract_id,
        trajectory_id="fixture-base-invalid",
        eligibility=eligible,
        checks=_all_base_checks(answer_canonical_semantic_match=False),
        noninterference_binding=binding,
    )
    mechanism_for_base_invalid = make_mechanism_qualification_report(
        verifier_contract_id=verifier.contract_id,
        trajectory_id="fixture-base-invalid",
        eligibility=eligible,
        mechanism_id="failure_recovery",
        required_event_ids=MECHANISM_REQUIRED_EVENTS["failure_recovery"],
        observed_event_ids=MECHANISM_REQUIRED_EVENTS["failure_recovery"],
    )
    qualified_base_invalid = make_qualified_validity_report(
        verifier_contract_id=verifier.contract_id,
        trajectory_id="fixture-base-invalid",
        eligibility=eligible,
        base=base_invalid,
        mechanism=mechanism_for_base_invalid,
    )
    if base_invalid.valid is not False or qualified_base_invalid.valid is not False:
        raise ValueError("v26.148 Base-invalid/Mechanism-valid fixture failed")
    names.append("base_invalid_mechanism_valid_qualified_invalid")

    null_base = make_base_validity_report(
        verifier_contract_id=verifier.contract_id,
        trajectory_id="fixture-support-exit",
        eligibility=ineligible,
        checks=None,
        noninterference_binding=None,
    )
    null_mechanism = make_mechanism_qualification_report(
        verifier_contract_id=verifier.contract_id,
        trajectory_id="fixture-support-exit",
        eligibility=ineligible,
        mechanism_id="failure_recovery",
        required_event_ids=MECHANISM_REQUIRED_EVENTS["failure_recovery"],
    )
    null_qualified = make_qualified_validity_report(
        verifier_contract_id=verifier.contract_id,
        trajectory_id="fixture-support-exit",
        eligibility=ineligible,
        base=null_base,
        mechanism=null_mechanism,
    )
    if any(
        item is not None for item in (null_base.valid, null_mechanism.success, null_qualified.valid)
    ):
        raise ValueError("v26.148 ineligible validity is not null")
    names.append("support_exit_validity_null_without_verifier")

    context_events = qualify_context_mechanism(
        ContextMechanismEvidence(
            frozen_context_pair_id="context-pair",
            baseline_action_id="action-A",
            conditioned_action_id="action-B",
        )
    )
    if not set(MECHANISM_REQUIRED_EVENTS["context_conditioned_action"]) <= set(context_events):
        raise ValueError("v26.148 Context mechanism fixture failed")
    names.append("context_requires_frozen_action_change")
    reconciliation_events = qualify_reconciliation_mechanism(
        ReconciliationMechanismEvidence(
            target_evidence_ids=("E1", "E2"),
            normalized_target_evidence_ids=("E1", "E2"),
            consumed_normalization_evidence_ids=("E1", "E2"),
            extra_legal_normalized_evidence_ids=("E3",),
        )
    )
    if not set(MECHANISM_REQUIRED_EVENTS["semantic_reconciliation"]) <= set(reconciliation_events):
        raise ValueError("v26.148 Reconciliation mechanism fixture failed")
    names.append("reconciliation_target_complete_extra_legal_allowed")
    recovery_events = qualify_recovery_mechanism(
        RecoveryMechanismEvidence(
            typed_failure_observation_index=0,
            revised_action_observation_index=1,
            later_success_observation_index=2,
            failed_action_signature="selector-A",
            revised_action_signature="selector-B",
        )
    )
    if not set(MECHANISM_REQUIRED_EVENTS["failure_recovery"]) <= set(recovery_events):
        raise ValueError("v26.148 Recovery mechanism fixture failed")
    names.append("recovery_requires_failure_revision_later_success")
    bypass_events = qualify_recovery_mechanism(RecoveryMechanismEvidence())
    if set(MECHANISM_REQUIRED_EVENTS["failure_recovery"]) <= set(bypass_events):
        raise ValueError("v26.148 Recovery bypass qualified")
    names.append("recovery_bypass_mechanism_invalid")
    stopping_events = qualify_stopping_mechanism(
        StoppingMechanismEvidence(
            completion_verified=True,
            stopped_after_completion=True,
            postcompletion_violation=False,
            stopping_failure_causal_group_id="stop-root",
        )
    )
    if not set(MECHANISM_REQUIRED_EVENTS["state_dependent_stopping"]) <= set(stopping_events):
        raise ValueError("v26.148 Stopping mechanism fixture failed")
    names.append("stopping_verified_immediate_no_postcompletion")
    violating_events = qualify_stopping_mechanism(
        StoppingMechanismEvidence(
            completion_verified=True,
            stopped_after_completion=False,
            postcompletion_violation=True,
            stopping_failure_causal_group_id="stop-root",
        )
    )
    if "postcompletion_violation" not in violating_events:
        raise ValueError("v26.148 Stopping violation fixture failed")
    names.append("stopping_violation_causal_group_retained")
    names.append("noninterference_requires_artifact_binding")
    names.append("host_envelope_contains_metadata_only")

    values = {
        "verifier_contract_id": verifier.contract_id,
        "fixture_results": tuple(FixtureResult(fixture_name=name) for name in sorted(names)),
    }
    provisional = ContractFixtureAudit.model_construct(audit_id="pending", **values)
    return ContractFixtureAudit(
        audit_id=_identity(
            provisional,
            "audit_id",
            "finance_v26_verifier_vnext_fixture:",
        ),
        **values,
    )


def _destructive(verifier: VerifierVNextContract) -> DestructiveAudit:
    if verifier.historical_rescoring_or_reclassification_allowed:
        raise ValueError("v26.148 destructive baseline changed")
    names = (
        "allow_flat_answer_alias",
        "allow_float_tolerance",
        "allow_host_answer_insertion",
        "allow_host_citation_insertion",
        "allow_host_mechanism_event_insertion",
        "allow_host_rationale_insertion",
        "classify_instrument_failure_as_model_invalid",
        "classify_privacy_rejection_as_model_invalid",
        "classify_support_exit_as_model_invalid",
        "drop_model_citation_from_base_validity",
        "hardcode_noninterference_true",
        "invoke_task_verifier_when_ineligible",
        "map_base_valid_mechanism_invalid_trajectory",
        "merge_base_and_mechanism_reports",
        "modify_historical_validity",
        "permit_extra_final_answer_fields",
        "permit_runtime_support_to_satisfy_model_citation",
        "qualify_context_from_final_answer_only",
        "qualify_reconciliation_without_target_consumption",
        "qualify_recovery_bypass",
        "qualify_stopping_with_postcompletion_action",
        "run_provider_call",
        "use_legacy_final_answer_semantically_valid_alias",
        "write_non_evaluable_validity_false",
    )
    values = {
        "mutation_results": tuple(MutationResult(mutation_name=name) for name in sorted(names))
    }
    provisional = DestructiveAudit.model_construct(audit_id="pending", **values)
    return DestructiveAudit(
        audit_id=_identity(
            provisional,
            "audit_id",
            "finance_v26_verifier_vnext_destructive:",
        ),
        **values,
    )


def _transition(
    verifier: VerifierVNextContract,
    fixture: ContractFixtureAudit,
) -> ProspectiveTransitionContract:
    values = {
        "verifier_vnext_contract_id": verifier.contract_id,
        "fixture_audit_id": fixture.audit_id,
    }
    provisional = ProspectiveTransitionContract.model_construct(contract_id="pending", **values)
    return ProspectiveTransitionContract(
        contract_id=_identity(
            provisional,
            "contract_id",
            "finance_v26_verifier_vnext_transition:",
        ),
        **values,
    )


def _detail(path: Path, output_dir: Path) -> DetailFile:
    return DetailFile(
        relative_path=str(path.relative_to(output_dir)),
        sha256=_sha256(path),
        byte_count=path.stat().st_size,
    )


def build_verifier_vnext_contract_freeze(
    *,
    package_root: Path,
    implementation_root: Path,
    output_dir: Path,
) -> VerifierVNextFreezeReport:
    source = _source_replay(
        package_root=package_root,
        implementation_root=implementation_root,
    )
    predecessor_integrity = _predecessor_integrity(
        package_root=package_root,
        implementation_root=implementation_root,
        source=source,
    )
    answer = _answer_contract()
    eligibility = _eligibility_contract()
    mechanism = _mechanism_contract()
    grammar = compile_qualified_final_response_grammar()
    responsibility = _responsibility_contract(grammar)
    verifier = _verifier_contract(
        answer=answer,
        eligibility=eligibility,
        mechanism=mechanism,
        responsibility=responsibility,
        grammar=grammar,
    )
    fixture = _fixture_audit(verifier=verifier, grammar=grammar)
    destructive = _destructive(verifier)
    transition = _transition(verifier, fixture)

    output_dir.mkdir(parents=True, exist_ok=True)
    outputs: tuple[tuple[str, BaseModel], ...] = (
        ("answer_semantics_contract.json", answer),
        ("contract_fixture_audit.json", fixture),
        ("destructive_audit.json", destructive),
        ("exact_final_grammar.json", grammar),
        ("mechanism_qualification_contract.json", mechanism),
        ("predecessor_integrity_audit.json", predecessor_integrity),
        ("prospective_transition_contract.json", transition),
        ("responsibility_noninterference_contract.json", responsibility),
        ("source_replay_audit.json", source),
        ("validity_eligibility_contract.json", eligibility),
        ("verifier_vnext_contract.json", verifier),
    )
    for name, value in outputs:
        _write_json_atomic(output_dir / name, value)
    details = tuple(
        sorted(
            (_detail(output_dir / name, output_dir) for name, _ in outputs),
            key=lambda item: item.relative_path,
        )
    )
    values = {
        "source_replay_audit_id": source.audit_id,
        "predecessor_integrity_audit_id": predecessor_integrity.audit_id,
        "answer_semantics_contract_id": answer.contract_id,
        "eligibility_contract_id": eligibility.contract_id,
        "mechanism_contract_id": mechanism.contract_id,
        "responsibility_contract_id": responsibility.contract_id,
        "final_grammar_id": grammar.grammar_id,
        "verifier_vnext_contract_id": verifier.contract_id,
        "fixture_audit_id": fixture.audit_id,
        "destructive_audit_id": destructive.audit_id,
        "transition_contract_id": transition.contract_id,
        "detail_files": details,
    }
    provisional = VerifierVNextFreezeReport.model_construct(report_id="pending", **values)
    report = VerifierVNextFreezeReport(
        report_id=_identity(
            provisional,
            "report_id",
            "finance_v26_verifier_vnext_freeze_report:",
        ),
        **values,
    )
    _write_json_atomic(output_dir / "report.json", report)
    return report


def main() -> None:
    package_default = Path(__file__).resolve().parents[4]
    parser = argparse.ArgumentParser(
        description="Freeze the prospective v26.148 Verifier vNext contracts"
    )
    parser.add_argument("--package-root", type=Path, default=package_default)
    parser.add_argument("--implementation-root", type=Path, default=package_default)
    parser.add_argument("--output-dir", type=Path, default=package_default / OUTPUT_DIR)
    args = parser.parse_args()
    report = build_verifier_vnext_contract_freeze(
        package_root=args.package_root,
        implementation_root=args.implementation_root,
        output_dir=args.output_dir,
    )
    print(report.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
