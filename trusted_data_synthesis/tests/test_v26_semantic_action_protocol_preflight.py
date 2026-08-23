from __future__ import annotations

import json
from pathlib import Path

from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_semantic_action_protocol_preflight import (  # noqa: E501
    SemanticActionPreflightReport,
    build,
)

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
CANONICAL_ROOT = Path("/home/zhuxinrui/datatmp/projects/Data-Synthesis/trusted_data_synthesis")
EVIDENCE_ROOT = CANONICAL_ROOT if CANONICAL_ROOT.is_dir() else PACKAGE_ROOT
PREDECESSOR_DIR = EVIDENCE_ROOT / (
    "artifacts/vtdo_experiment/finance_v26_116_semantic_proposal_distribution_audit_v1_20260823"
)


def _build(output_dir: Path) -> SemanticActionPreflightReport:
    return build(
        package_root=EVIDENCE_ROOT,
        implementation_root=PACKAGE_ROOT,
        predecessor_dir=PREDECESSOR_DIR,
        output_dir=output_dir,
    )


def test_v26_117_semantic_action_protocol_dual_build_is_byte_identical(
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
    assert formal.compiler_path_count == 48
    assert formal.prompt_only_decision_count == 324
    assert formal.reversible_tool_call_count == 276
    assert formal.final_ready_count == 48
    assert formal.provider_calls == formal.stage_two_provider_calls == 0
    assert formal.historical_v26_114_payloads_reparsed == 0


def test_v26_117_closes_public_action_and_recovery_boundaries(
    tmp_path: Path,
) -> None:
    output_dir = tmp_path / "preflight"
    report = _build(output_dir)
    language = json.loads((output_dir / "canonical_action_language_audit.json").read_text())
    frontier = json.loads((output_dir / "operation_frontier_audit.json").read_text())
    prompt = json.loads((output_dir / "prompt_only_path_control.json").read_text())
    recovery = json.loads((output_dir / "semantic_recovery_continuity_audit.json").read_text())
    authority = json.loads((output_dir / "stage_two_authority_audit.json").read_text())
    destructive = json.loads((output_dir / "destructive_audit.json").read_text())
    transition = json.loads((output_dir / "prospective_transition_contract.json").read_text())
    assert language["decision_kind_counts"] == {
        "acquire_public_input": 156,
        "emit_final_answer": 48,
        "execute_public_operation": 72,
        "verify_terminal_operation": 48,
    }
    assert language["acquisition_mode_counts"] == {
        "open_public_document": 21,
        "query_fully_qualified": 75,
        "query_source_scoped": 12,
        "search_public_record": 48,
    }
    assert language["model_generated_direct_argument_object_count"] == 0
    assert frontier["candidates_from_blocked_dependencies_count"] == 0
    assert frontier["candidates_from_dependency_ready_count"] == 0
    assert frontier["candidates_from_terminal_verifiable_count"] == 0
    assert frontier["operation_candidate_count"] == 114
    assert prompt["exact_compiler_call_match_count"] == 276
    assert prompt["maximum_prompt_utf8_bytes"] == 16887
    assert recovery["typed_runtime_failure_visible_block_count"] == 12
    assert recovery["rejection_immediate_job_terminal_count"] == 0
    assert recovery["recovery_exact_next_call_match_count"] == 1
    assert recovery["abi_rescue_count_after_semantic_rejection"] == 1
    assert recovery["semantic_recovery_count_after"] == 1
    assert authority["stage_two_provider_calls"] == 0
    assert authority["compiler_semantic_repair_count"] == 0
    assert destructive["mutation_count"] == destructive["rejection_count"] == 20
    assert transition["provider_calls_authorized"] is False
    assert report.next_permitted_stage == (
        "fresh_semantic_action_protocol_taskpackage_contract_manifest_and_runner_preflight_only"
    )
