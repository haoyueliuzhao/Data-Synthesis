from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pytest

from trusted_synthesis.core.task.authoritative_job_bound_outcome import (
    AuthoritativeJobBoundOutcomeContract,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_capability_authoritative_outcome_terminal_preflight as build_module,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_capability_authoritative_outcome_terminal_preflight_models as models,
)

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
FORMAL_DIR = Path(os.environ.get("V26_181_TEST_FORMAL_DIR", PACKAGE_ROOT / build_module.OUTPUT_DIR))


def _load(name: str) -> Any:
    return json.loads((FORMAL_DIR / name).read_text(encoding="utf-8"))


def test_authorization_freezes_and_rebuilds_v180_with_narrowed_scope() -> None:
    authorization = models.ExternalAuditAuthorization.model_validate(
        _load("external_audit_authorization.json")
    )
    predecessor = models.V180PredecessorFreezeAudit.model_validate(
        _load("v180_predecessor_freeze_audit.json")
    )
    scope = models.V180MeasurementScopeAudit.model_validate(
        _load("v180_measurement_scope_audit.json")
    )
    assert authorization.review_sha256 == build_module.EXPECTED_REVIEW_SHA256
    assert authorization.review_byte_count == build_module.EXPECTED_REVIEW_BYTE_COUNT == 25_586
    assert authorization.audited_v179_commit == build_module.AUDITED_V179_COMMIT
    assert (
        authorization.audited_v180_implementation_commit
        == build_module.AUDITED_V180_IMPLEMENTATION_COMMIT
    )
    assert predecessor.predecessor_file_count == 14
    assert predecessor.independent_rebuild_match_count == 14
    assert predecessor.predecessor_mutation_count == 0
    assert scope.negative_parent_authenticity_facts_retained is True
    assert scope.runtime_non_totality_facts_retained is True
    assert scope.historical_malformed_final_exception_type == "ValidationError"
    assert scope.old_formal_parser_rejection_gate_closed is False
    assert scope.old_complete_terminal_registry_claim == "unknown"
    assert scope.old_static_gate_interpretation == (
        "audit_integrity_and_defect_reproduction_meta_gates"
    )


def test_terminal_registry_is_source_derived_and_exhaustive() -> None:
    audit = models.TerminalRegistryDerivationAudit.model_validate(
        _load("authoritative_terminal_registry_audit.json")
    )
    assert audit.v166_case_count == 8
    assert audit.v179_endpoint_kind_count == 6
    assert audit.v180_outer_class_count == 6
    assert audit.frozen_profile_parent_count == 6
    assert audit.derivation_source_label_count == 26
    assert audit.consumed_derivation_source_label_count == 26
    assert audit.unmapped_source_label_count == 0
    assert audit.terminal_kind_count == 18
    assert audit.reachable_count == 16
    assert audit.registered_but_unreachable_count == 0
    assert audit.not_applicable_with_witness_count == 2
    assert audit.registry.silent_omission_count == 0
    assert len({item.terminal_kind for item in audit.registry.policies}) == 18
    witnesses = {item.terminal_kind: item for item in audit.registry.exclusion_witnesses}
    assert set(witnesses) == {"policy_horizon_exhausted", "measurement_support_exit"}
    assert all(item.applicable_branch_count == 0 for item in witnesses.values())
    assert all(not any(item.excluded_branch_token_counts.values()) for item in witnesses.values())


def test_final_parser_gate_requires_validationerror_at_parser_boundary() -> None:
    audit = models.FinalParserSemanticGateAudit.model_validate(
        _load("final_parser_semantic_gate_audit.json")
    )
    assert audit.parser_invocation_count == 1
    assert audit.parser_rejected is True
    assert audit.parser_exception_type == "ValidationError"
    assert audit.escaped_exception_phase == "final_parser"
    assert audit.typed_final_abi_invalid_bundle_count == 1
    assert audit.task_verifier_invocation_count == 0
    assert audit.base_validity is audit.mechanism_qualification is audit.qualified_validity is False
    assert audit.exact_outcome_row_count == 1
    assert audit.exception_escape_count == 0
    assert audit.semantic_attack_count == audit.semantic_attack_rejection_count == 4


def test_exact_192_job_evidence_dag_is_bijective_and_nonempirical() -> None:
    audit = models.AuthoritativeEvidenceDagAudit.model_validate(
        _load("authoritative_evidence_dag_audit.json")
    )
    contract = AuthoritativeJobBoundOutcomeContract.model_validate(
        _load("authoritative_job_bound_outcome_contract.json")
    )
    assert len(contract.job_component_sequences) == 192
    assert len({item.job_id for item in contract.job_component_sequences}) == 192
    assert contract.raw_result_trace_row_bijection_required is True
    assert contract.estimator_revalidates_canonical_bytes is True
    assert contract.estimator_rebuilds_rows_from_descriptors is True
    assert contract.arbitrary_caller_ids_authoritative is False
    assert contract.python_exception_escape_allowed is False
    assert audit.exact_manifest_job_count == 192
    assert audit.raw_descriptor_count == audit.unique_raw_descriptor_count == 192
    assert audit.result_descriptor_count == audit.unique_result_descriptor_count == 192
    assert audit.job_bound_trace_count == audit.unique_trace_count == 192
    assert audit.scripted_outcome_row_count == audit.unique_row_count == 192
    assert audit.scripted_evaluation.exact_job_set_match is True
    assert audit.scripted_evaluation.crossed_parent_count == 0
    assert audit.scripted_evaluation.duplicate_canonical_object_count == 0
    assert audit.scripted_evaluation.q_first_fraction == "192/192"
    assert audit.scripted_evaluation.q_bounded_correction_fraction == "192/192"
    assert audit.scripted_evaluation.empirical is False
    assert audit.formal_empirical_row_count == audit.formal_empirical_estimate_count == 0


def test_unknown_action_and_all_terminal_controls_project_typed_rows() -> None:
    unknown = models.UnknownFirstActionPolicyAudit.model_validate(
        _load("unknown_first_action_policy_audit.json")
    )
    totality = models.TerminalTotalityAudit.model_validate(
        _load("terminal_totality_preflight_audit.json")
    )
    assert unknown.action_abi_valid is True
    assert unknown.action_reference_valid is False
    assert unknown.frozen_policy == "immediate_typed_terminal_without_correction"
    assert unknown.correction_invoked is False
    assert unknown.terminal_kind == "first_action_reference_invalid"
    assert unknown.terminal_projection_count == unknown.exact_outcome_row_count == 1
    assert totality.terminal_kind_count == 18
    assert totality.exactly_one_projection_count == totality.exact_outcome_row_count == 18
    assert totality.exception_escape_count == 0
    assert totality.missing_terminal_kind_count == totality.duplicate_terminal_kind_count == 0
    assert totality.policy_match_count == 18
    assert sum(item.diagnostic_only for item in totality.rows) == 2
    assert sum(item.terminal_locus_count for item in totality.rows) == 17


def test_expanded_destructive_denominator_rehashes_and_rejects_all_attacks() -> None:
    audit = models.ProductionDestructiveAudit.model_validate(
        _load("production_destructive_audit.json")
    )
    expected = {
        "cross_job_outcome_payload_reassignment",
        "duplicate_raw_execution_id_across_jobs",
        "duplicate_result_id_across_jobs",
        "swapped_raw_and_result_parents",
        "result_parent_outcome_final_mismatch",
        "duplicate_attempt_trace_across_jobs",
        "same_raw_content_different_forged_ids",
        "same_result_content_different_forged_ids",
        "unique_trace_ids_duplicate_canonical_bytes",
        "component_attempt_truncation",
        "component_attempt_splicing",
        "component_attempt_reordering",
        "inner_outcome_job_parent_mismatch",
        "final_result_descriptor_mismatch",
        "correct_namespace_cross_job_artifact_path",
        "package_replica_same_manifest_job_replaced",
        "missing_real_job_plus_extra_fake_job",
        "outer_terminal_row_missing",
        "outer_terminal_row_duplicate",
        "raw_terminal_result_terminal_mismatch",
        "provider_transport_artifact_parent_replacement",
        "parser_validationerror_to_sentinel_valueerror",
        "parser_rejected_wrong_exception_phase",
        "parser_accepted_then_later_runtime_failure",
        "parser_exception_reason_changed",
    }
    assert audit.mutation_count == audit.fully_rehashed_mutation_count == 25
    assert audit.transition_report_rehash_count == 25
    assert audit.rejection_count == 25
    assert audit.acceptance_count == 0
    assert {item.mutation_name for item in audit.mutations} == expected
    assert len({item.mutation_transition_id for item in audit.mutations}) == 25
    assert len({item.mutation_report_id for item in audit.mutations}) == 25
    assert all(item.transition_and_report_rehashed for item in audit.mutations)
    assert all(item.rejected and not item.stale_hash_only for item in audit.mutations)


def test_transport_artifact_parent_replacement_rejects() -> None:
    frozen = build_module._load_frozen_inputs(PACKAGE_ROOT)
    registry_audit = build_module._terminal_registry(
        package_root=PACKAGE_ROOT,
        frozen=frozen,
    )
    registry = registry_audit.registry
    contract = build_module._outcome_contract(frozen=frozen, registry=registry)
    _, baseline = build_module._evidence_dag(
        frozen=frozen,
        registry=registry,
        contract=contract,
    )
    first = build_module.runtime.build_authoritative_bundle(
        job=frozen.manifest.jobs[0],
        manifest=frozen.manifest,
        runner=frozen.runner,
        registry=registry,
        terminal_kind="provider_transport_failure",
        evidence_kind="scripted_preflight_control",
    )
    foreign = build_module.runtime.build_authoritative_bundle(
        job=frozen.manifest.jobs[1],
        manifest=frozen.manifest,
        runner=frozen.runner,
        registry=registry,
        terminal_kind="provider_transport_failure",
        evidence_kind="scripted_preflight_control",
    )
    valid = build_module.EvidenceCatalogs(
        build_module._replace_at(baseline.raws, 0, first.raw),
        build_module._replace_at(baseline.results, 0, first.result),
        build_module._replace_at(baseline.traces, 0, first.trace),
        build_module._replace_at(baseline.rows, 0, first.row),
    )
    build_module._evaluate_catalogs(
        catalogs=valid,
        manifest=frozen.manifest,
        frozen=frozen,
        registry=registry,
        contract=contract,
    )
    replaced = build_module._cascade_bundle(
        first,
        raw_payload_updates={"transport_artifact_ids": foreign.raw.payload.transport_artifact_ids},
    )
    attacked = build_module.EvidenceCatalogs(
        build_module._replace_at(valid.raws, 0, replaced.raw),
        build_module._replace_at(valid.results, 0, replaced.result),
        build_module._replace_at(valid.traces, 0, replaced.trace),
        build_module._replace_at(valid.rows, 0, replaced.row),
    )
    with pytest.raises(ValueError, match="artifact parents are not owned by the exact Job"):
        build_module._evaluate_catalogs(
            catalogs=attacked,
            manifest=frozen.manifest,
            frozen=frozen,
            registry=registry,
            contract=contract,
        )


def test_meta_gates_close_preflight_but_block_online_execution() -> None:
    meta = models.AuditIntegrityMetaGateAudit.model_validate(
        _load("audit_integrity_meta_gate_audit.json")
    )
    transition = models.ProspectiveTransition.model_validate(
        _load("prospective_transition_contract.json")
    )
    report = models.PreflightReport.model_validate(_load("report.json"))
    assert meta.gate_count == meta.passed_gate_count == 41
    assert meta.failed_gate_count == 0
    assert meta.audit_construction_integrity == "PASS"
    assert meta.v179_local_scripted_preflight == "RETAINED"
    assert meta.empirical_parent_authenticity == "PREFLIGHT_CLOSED"
    assert meta.terminal_totality == "PREFLIGHT_CLOSED"
    assert meta.online_execution_admission == "BLOCKED_PENDING_INDEPENDENT_AUDIT"
    assert transition.consumed_stage == models.AUTHORIZED_STAGE
    assert transition.next_stage == models.NEXT_STAGE
    assert transition.provider_execution_authorized is False
    assert transition.development_outcomes_authorized is False
    assert transition.independent_audit_required is True
    assert transition.manifest_job_set_change_authorized is False
    assert report.report_id == (
        "finance_v26_authoritative_outcome_preflight_report:"
        "2fec6e40b8eb04cf510896979ed1088a2f716e8acd7d78641f4e027f368c99e8"
    )
    assert report.detail_file_count == 14
    assert report.provider_calls == report.stage2_provider_calls == 0
    assert report.development_model_outcomes == 0
    assert report.formal_empirical_row_count == report.formal_empirical_estimate_count == 0
    assert report.online_execution_authorized is False
    assert report.next_stage == models.NEXT_STAGE


def test_empty_directory_warning_error_rebuild_is_byte_identical(tmp_path: Path) -> None:
    rebuilt = tmp_path / "v26_181_rebuilt"
    products = build_module.build(
        package_root=PACKAGE_ROOT,
        output_dir=rebuilt,
        external_audit_path=FORMAL_DIR / "external_v180_revision_report_audit.txt",
    )
    assert products.report.provider_calls == 0
    assert products.report.formal_empirical_row_count == 0
    assert products.transition.provider_execution_authorized is False
    expected = {item.name for item in FORMAL_DIR.iterdir() if item.is_file()}
    observed = {item.name for item in rebuilt.iterdir() if item.is_file()}
    assert len(expected) == len(observed) == 15
    assert observed == expected
    for name in sorted(expected):
        assert (rebuilt / name).read_bytes() == (FORMAL_DIR / name).read_bytes()
