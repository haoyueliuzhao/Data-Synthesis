from __future__ import annotations

from pathlib import Path

from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_exact_response_grammar_calibration_postrun_audit import (  # noqa: E501
    build,
)

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
CANONICAL_ROOT = Path("/home/zhuxinrui/datatmp/projects/Data-Synthesis/trusted_data_synthesis")
EVIDENCE_ROOT = CANONICAL_ROOT if CANONICAL_ROOT.is_dir() else PACKAGE_ROOT
EXECUTION_DIR = EVIDENCE_ROOT / (
    "artifacts/vtdo_experiment/"
    "finance_v26_114_exact_response_grammar_calibration_execution_v1_20260823"
)


def test_v26_115_independent_postrun_audit_is_byte_identical(tmp_path: Path) -> None:
    formal_dir = tmp_path / "formal"
    independent_dir = tmp_path / "independent"
    formal = build(
        package_root=EVIDENCE_ROOT,
        implementation_root=PACKAGE_ROOT,
        execution_dir=EXECUTION_DIR,
        output_dir=formal_dir,
    )
    independent = build(
        package_root=EVIDENCE_ROOT,
        implementation_root=PACKAGE_ROOT,
        execution_dir=EXECUTION_DIR,
        output_dir=independent_dir,
    )
    assert formal == independent
    assert sorted(path.name for path in formal_dir.iterdir()) == sorted(
        path.name for path in independent_dir.iterdir()
    )
    for path in formal_dir.iterdir():
        assert path.read_bytes() == (independent_dir / path.name).read_bytes()
    assert formal.exact_abi_accepted_count == 54
    assert formal.semantic_commit_count == 30
    assert formal.program_closed_count == 0
    assert formal.independently_valid_count == 0
    assert formal.provider_calls == 0
    assert formal.next_permitted_stage == (
        "fresh_host_bound_stage_metadata_semantic_proposal_preflight_only"
    )


def test_v26_115_audit_freezes_mechanical_and_semantic_failures(tmp_path: Path) -> None:
    output_dir = tmp_path / "audit"
    build(
        package_root=EVIDENCE_ROOT,
        implementation_root=PACKAGE_ROOT,
        execution_dir=EXECUTION_DIR,
        output_dir=output_dir,
    )
    import json

    funnel = json.loads((output_dir / "response_funnel_audit.json").read_text())
    semantic = json.loads((output_dir / "semantic_runtime_audit.json").read_text())
    destructive = json.loads((output_dir / "destructive_audit.json").read_text())
    assert funnel["exact_ten_field_set_count"] == 81
    assert funnel["registered_protocol_count"] == 81
    assert funnel["exact_state_binding_count"] == 81
    assert funnel["mechanical_failure_field_counts"] == {"stage_constant": 27}
    assert semantic["semantic_compile_rejection_counts"] == {
        "compiled public call violates the exposed tool grammar": 10,
        "semantic proposal changes registered public operand sources": 4,
        "semantic proposal selects an unresolved public Operation": 7,
    }
    assert semantic["independently_decompiled_commit_count"] == 30
    assert semantic["stage_two_provider_call_count"] == 0
    assert destructive["mutation_count"] == destructive["rejection_count"] == 20
    assert destructive["provider_calls"] == 0
