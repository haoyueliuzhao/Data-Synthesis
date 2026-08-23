from __future__ import annotations

import json
from pathlib import Path

from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_semantic_proposal_distribution_audit import (  # noqa: E501
    SemanticProposalAuditReport,
    build,
)

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
CANONICAL_ROOT = Path("/home/zhuxinrui/datatmp/projects/Data-Synthesis/trusted_data_synthesis")
EVIDENCE_ROOT = CANONICAL_ROOT if CANONICAL_ROOT.is_dir() else PACKAGE_ROOT
EXECUTION_DIR = EVIDENCE_ROOT / (
    "artifacts/vtdo_experiment/"
    "finance_v26_114_exact_response_grammar_calibration_execution_v1_20260823"
)
PREDECESSOR_AUDIT_DIR = EVIDENCE_ROOT / (
    "artifacts/vtdo_experiment/"
    "finance_v26_115_exact_response_grammar_calibration_postrun_audit_v1_20260823"
)


def _build(output_dir: Path) -> SemanticProposalAuditReport:
    return build(
        package_root=EVIDENCE_ROOT,
        implementation_root=PACKAGE_ROOT,
        execution_dir=EXECUTION_DIR,
        predecessor_audit_dir=PREDECESSOR_AUDIT_DIR,
        output_dir=output_dir,
    )


def test_v26_116_semantic_distribution_dual_build_is_byte_identical(
    tmp_path: Path,
) -> None:
    formal_dir = tmp_path / "formal"
    independent_dir = tmp_path / "independent"
    formal = _build(formal_dir)
    independent = _build(independent_dir)
    assert formal == independent
    assert sorted(path.name for path in formal_dir.iterdir()) == sorted(
        path.name for path in independent_dir.iterdir()
    )
    for path in formal_dir.iterdir():
        assert path.read_bytes() == (independent_dir / path.name).read_bytes()
    assert formal.exact_abi_accepted_count == 54
    assert formal.semantic_commit_count == 30
    assert formal.accepted_without_commit_count == 24
    assert formal.provider_calls == 0
    assert formal.next_permitted_stage == "semantic_action_selection_protocol_design_only"


def test_v26_116_localizes_action_selection_without_reclassification(
    tmp_path: Path,
) -> None:
    output_dir = tmp_path / "audit"
    report = _build(output_dir)
    distribution = json.loads(
        (output_dir / "semantic_proposal_distribution_audit.json").read_text()
    )
    failures = json.loads((output_dir / "action_selection_failure_audit.json").read_text())
    progression = json.loads((output_dir / "trajectory_progression_audit.json").read_text())
    diagnostics = json.loads((output_dir / "proposal_diagnostics.json").read_text())
    destructive = json.loads((output_dir / "destructive_audit.json").read_text())
    assert distribution["accepted_decision_kind_counts"] == {
        "acquire_public_input": 42,
        "execute_public_operation": 12,
    }
    assert distribution["committed_decision_kind_counts"] == {
        "acquire_public_input": 29,
        "execute_public_operation": 1,
    }
    assert failures["failure_dimension_counts"] == {
        "duplicate_failed_public_call": 3,
        "operand_grounding": 4,
        "public_state_frontier": 7,
        "tool_argument_grammar": 10,
    }
    assert failures["duplicate_prior_error_counts"] == {
        "structured_query_no_match": 1,
        "typed_selector_requires_refinement": 2,
    }
    assert progression["committed_verification_count"] == 0
    assert progression["emitted_final_count"] == 0
    assert progression["program_closed_count"] == 0
    assert len(diagnostics["diagnostics"]) == 54
    assert all(
        not row["raw_direct_argument_values_retained"] and not row["private_reasoning_retained"]
        for row in diagnostics["diagnostics"]
    )
    assert report.empirical_rows_reclassified == 0
    assert destructive["mutation_count"] == destructive["rejection_count"] == 21
    assert destructive["provider_calls"] == 0
