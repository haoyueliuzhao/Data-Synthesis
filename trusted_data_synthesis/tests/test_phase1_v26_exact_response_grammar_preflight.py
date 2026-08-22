from __future__ import annotations

import json
from pathlib import Path

from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_exact_response_grammar_rematerialization import (  # noqa: E501
    build as build_rematerialization,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_exact_response_grammar_runner_preflight import (  # noqa: E501
    build as build_runner_preflight,
)
from trusted_synthesis.runtime.agent.prospective_two_stage_exact_response_grammar import (
    DECISION_FIELD_RULES,
    EXACT_RESPONSE_PROTOCOL_VERSION,
    FIELD_ORDER,
    ExactStageOneSemanticProposalPayload,
    compile_stage_one_response_grammar,
)

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
CANONICAL_ROOT = Path("/home/zhuxinrui/datatmp/projects/Data-Synthesis/trusted_data_synthesis")
EVIDENCE_ROOT = CANONICAL_ROOT if CANONICAL_ROOT.is_dir() else PACKAGE_ROOT
V26_112_DIR = (
    PACKAGE_ROOT / "artifacts/vtdo_experiment/"
    "finance_v26_112_exact_response_grammar_rematerialization_v1_20260823"
)

EXPECTED_V26_112_REPORT_ID = (
    "finance_v26_exact_grammar_rematerialization_report:"
    "88b4a2cac6d43e46d52a45a0af7956787b78805893daf86af2ac01abde5e2f8f"
)
EXPECTED_V26_113_REPORT_ID = (
    "finance_v26_exact_grammar_runner_preflight_report:"
    "da5f397ce5082137ef0f343e240db57ce88e6f89178ac4a2b486118cdc5d24cf"
)


def _payload(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def test_exact_response_grammar_is_compiled_from_the_strong_schema() -> None:
    grammar = compile_stage_one_response_grammar()
    assert tuple(ExactStageOneSemanticProposalPayload.model_fields) == FIELD_ORDER
    assert grammar.field_order == FIELD_ORDER
    assert grammar.response_protocol == EXACT_RESPONSE_PROTOCOL_VERSION
    assert set(grammar.json_skeleton) == set(FIELD_ORDER)
    assert tuple(item.decision_kind for item in grammar.decision_rules) == tuple(
        DECISION_FIELD_RULES
    )
    assert grammar.exact_top_level_field_set_required
    assert not grammar.extra_fields_allowed
    assert not grammar.top_level_wrapper_allowed
    assert grammar.exactly_one_proposal_required


def test_v26_112_rematerialization_rebuilds_byte_identically(tmp_path: Path) -> None:
    formal = tmp_path / "formal"
    independent = tmp_path / "independent"
    first = build_rematerialization(
        package_root=EVIDENCE_ROOT,
        implementation_root=PACKAGE_ROOT,
        output_dir=formal,
    )
    second = build_rematerialization(
        package_root=EVIDENCE_ROOT,
        implementation_root=PACKAGE_ROOT,
        output_dir=independent,
    )
    assert first == second
    assert first.report_id == EXPECTED_V26_112_REPORT_ID
    assert sorted(path.name for path in formal.iterdir()) == sorted(
        path.name for path in independent.iterdir()
    )
    for path in formal.iterdir():
        assert path.read_bytes() == (independent / path.name).read_bytes()


def test_v26_112_constructibility_and_resource_bounds_are_closed() -> None:
    audit = _payload(V26_112_DIR / "response_constructibility_audit.json")
    paths = json.loads((V26_112_DIR / "two_stage_path_audits.json").read_text())
    cross = _payload(V26_112_DIR / "cross_artifact_binding_audit.json")
    destructive = _payload(V26_112_DIR / "destructive_preflight_audit.json")
    assert audit["semantic_proposal_state_count"] == 324
    assert audit["prompt_only_parser_pass_count"] == 648
    assert audit["exact_state_binding_pass_count"] == 648
    assert audit["primary_rescue_semantic_projection_match_count"] == 324
    assert audit["rescue_smaller_than_primary_count"] == 324
    assert audit["maximum_primary_prompt_utf8_bytes"] == 7724
    assert audit["maximum_rescue_prompt_utf8_bytes"] == 4996
    assert max(item["static_complete_path_upper_bound_tokens"] for item in paths) == 258646
    assert min(item["static_rollout_headroom_tokens"] for item in paths) == 1354
    assert cross["task_response_grammar_binding_count"] == 24
    assert cross["path_prompt_binding_count"] == 48
    assert cross["seed_projection_match_count"] == 32
    assert destructive["mutation_count"] == destructive["rejection_count"] == 16


def test_v26_113_runner_preflight_rebuilds_byte_identically(tmp_path: Path) -> None:
    formal = tmp_path / "formal"
    independent = tmp_path / "independent"
    first = build_runner_preflight(
        package_root=EVIDENCE_ROOT,
        implementation_root=PACKAGE_ROOT,
        output_dir=formal,
    )
    second = build_runner_preflight(
        package_root=EVIDENCE_ROOT,
        implementation_root=PACKAGE_ROOT,
        output_dir=independent,
    )
    assert first == second
    assert first.report_id == EXPECTED_V26_113_REPORT_ID
    for path in formal.iterdir():
        assert path.read_bytes() == (independent / path.name).read_bytes()


def test_v26_113_runner_counts_usage_recovery_and_authority() -> None:
    root = PACKAGE_ROOT / (
        "artifacts/vtdo_experiment/"
        "finance_v26_113_exact_response_grammar_runner_preflight_v1_20260823"
    )
    fixture = _payload(root / "runner_fixture_audit.json")
    controls = _payload(root / "certificate_usage_recovery_audit.json")
    destructive = _payload(root / "destructive_runner_audit.json")
    report = _payload(root / "report.json")
    assert fixture["job_count"] == 32
    assert fixture["stage_one_scripted_provider_call_count"] == 256
    assert fixture["semantic_proposal_payload_count"] == 224
    assert fixture["exact_grammar_payload_count"] == 224
    assert fixture["stage_two_commit_count"] == 224
    assert fixture["public_observation_count"] == 192
    assert fixture["replay_v3_pass_count"] == 32
    assert fixture["independent_validity_pass_count"] == 32
    assert fixture["mechanism_success_count"] == 32
    assert fixture["stage_two_provider_call_count"] == 0
    assert controls["serialization_rescue_accepted"] is True
    assert controls["rescue_uses_exact_response_protocol"] is True
    assert controls["completion_16385_admitted_and_charged"] is True
    assert controls["completion_16386_instrument_failure"] is True
    assert controls["complete_raw_recovery_provider_calls"] == 0
    assert destructive["mutation_count"] == destructive["rejection_count"] == 10
    assert report["next_permitted_stage"] == "exact_response_grammar_calibration_execution_only"
    assert report["real_provider_calls"] == 0
    assert report["stage_two_provider_calls"] == 0
    assert report["execution_authorized"] is True
