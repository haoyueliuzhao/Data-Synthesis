from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_final_grammar_privacy_rematerialization as v26_122,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_privacy_first_exact_final_runner_preflight as v26_123,
)
from trusted_synthesis.runtime.agent.prospective_exact_final_response_grammar import (
    ExactFinalResponseRejection,
    compile_exact_final_response_grammar,
    make_final_response_host_envelope,
    parse_exact_final_response_payload,
)

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
CANONICAL_ROOT = Path("/home/zhuxinrui/datatmp/projects/Data-Synthesis/trusted_data_synthesis")
EVIDENCE_ROOT = CANONICAL_ROOT if CANONICAL_ROOT.is_dir() else PACKAGE_ROOT


def _assert_byte_identical(left: Path, right: Path) -> None:
    assert sorted(path.name for path in left.iterdir()) == sorted(
        path.name for path in right.iterdir()
    )
    for path in left.iterdir():
        assert path.read_bytes() == (right / path.name).read_bytes()


def _build_v26_122(output_dir: Path) -> v26_122.FinalGrammarRematerializationReport:
    return v26_122.build(
        package_root=EVIDENCE_ROOT,
        implementation_root=PACKAGE_ROOT,
        output_dir=output_dir,
    )


def _build_v26_123(output_dir: Path) -> v26_123.PrivacyFirstRunnerPreflightReport:
    return v26_123.build(
        package_root=EVIDENCE_ROOT,
        implementation_root=PACKAGE_ROOT,
        output_dir=output_dir,
    )


def test_exact_final_response_grammar_has_one_shared_fail_closed_parser() -> None:
    grammar = compile_exact_final_response_grammar()
    envelope = make_final_response_host_envelope(
        terminal_state_id="public-terminal-state",
        terminal_commit_id="public-terminal-commit",
        grammar=grammar,
    )
    payload: dict[str, Any] = {
        "answer": {"result": {"value": "1"}, "citations": [{"evidence_id": "e1"}]},
        "rationale_summary": "Projected the verified public result.",
    }

    parsed = parse_exact_final_response_payload(payload, grammar=grammar, envelope=envelope)
    assert tuple(parsed.model_dump(mode="json")) == ("answer", "rationale_summary")
    assert envelope.model_payload_fields == ("answer", "rationale_summary")
    assert envelope.host_supplies_answer_or_rationale is False

    with pytest.raises(ExactFinalResponseRejection):
        parse_exact_final_response_payload(
            {**payload, "stage": "final_answer"},
            grammar=grammar,
            envelope=envelope,
        )
    with pytest.raises(ExactFinalResponseRejection):
        parse_exact_final_response_payload(
            {"answer": payload["answer"]},
            grammar=grammar,
            envelope=envelope,
        )
    with pytest.raises(ExactFinalResponseRejection):
        parse_exact_final_response_payload(
            {
                "answer": {**payload["answer"], "reasoning_trace": "forbidden"},
                "rationale_summary": payload["rationale_summary"],
            },
            grammar=grammar,
            envelope=envelope,
        )


def test_v26_122_rematerialization_is_reproducible_and_preserves_action_authority(
    tmp_path: Path,
) -> None:
    formal_dir = tmp_path / "formal"
    independent_dir = tmp_path / "independent"
    formal = _build_v26_122(formal_dir)
    independent = _build_v26_122(independent_dir)
    assert formal == independent
    _assert_byte_identical(formal_dir, independent_dir)

    grammar = json.loads((formal_dir / "exact_final_response_grammar.json").read_text())
    constructibility = json.loads(
        (formal_dir / "final_grammar_constructibility_audit.json").read_text()
    )
    preservation = json.loads((formal_dir / "semantic_action_preservation_audit.json").read_text())
    resource = json.loads((formal_dir / "final_grammar_resource_contract.json").read_text())
    cross = json.loads((formal_dir / "cross_artifact_binding_audit.json").read_text())
    destructive = json.loads((formal_dir / "destructive_audit.json").read_text())

    assert grammar["field_order"] == ["answer", "rationale_summary"]
    assert grammar["primary_and_rescue_share_grammar"]
    assert grammar["parser_compiled_from_same_grammar"]
    assert grammar["json_mode_lexical_cue_required"]
    assert constructibility["final_state_count"] == 48
    assert constructibility["prompt_only_primary_parse_count"] == 48
    assert constructibility["prompt_only_rescue_parse_count"] == 48
    assert constructibility["primary_rescue_semantic_projection_match_count"] == 48
    assert constructibility["compiler_answer_match_count"] == 96
    assert constructibility["wrong_answer_schema_admission_count"] == 48
    assert constructibility["host_answer_or_rationale_insertion_count"] == 0
    assert preservation["action_state_count"] == 324
    assert preservation["exact_action_prompt_hash_match_count"] == 324
    assert preservation["exact_candidate_presentation_match_count"] == 324
    assert preservation["job_assignment_and_seed_match_count"] == 32
    assert preservation["v26_120_outcome_used_for_selection"] is False
    assert resource["exact_request_completion_bound_tokens"] == 16_384
    assert resource["rollout_upper_bound_tokens"] == 400_000
    assert resource["maximum_abi_rescue_calls_per_job"] == 1
    assert resource["maximum_semantic_recovery_calls_per_job"] == 1
    assert cross["task_count"] == 24
    assert cross["path_count"] == 48
    assert cross["job_count"] == 32
    assert cross["task_identity_overlap_with_v26_118"] == 0
    assert cross["path_identity_overlap_with_v26_118"] == 0
    assert cross["job_identity_overlap_with_v26_118"] == 0
    assert destructive["mutation_count"] == destructive["rejection_count"] == 20
    assert formal.provider_calls == formal.stage_two_provider_calls == 0
    assert formal.next_permitted_stage == "privacy_first_exact_final_runner_preflight_only"


def test_v26_123_runner_preflight_is_reproducible_and_privacy_first(
    tmp_path: Path,
) -> None:
    formal_dir = tmp_path / "formal"
    independent_dir = tmp_path / "independent"
    formal = _build_v26_123(formal_dir)
    independent = _build_v26_123(independent_dir)
    assert formal == independent
    _assert_byte_identical(formal_dir, independent_dir)

    fixture = json.loads((formal_dir / "runner_fixture_audit.json").read_text())
    final = json.loads((formal_dir / "final_interface_control_audit.json").read_text())
    privacy = json.loads((formal_dir / "privacy_first_capture_audit.json").read_text())
    semantic = json.loads((formal_dir / "semantic_recovery_control_audit.json").read_text())
    certificate = json.loads((formal_dir / "certificate_usage_recovery_audit.json").read_text())
    destructive = json.loads((formal_dir / "destructive_audit.json").read_text())
    transition = json.loads((formal_dir / "prospective_transition_contract.json").read_text())

    assert fixture["job_count"] == 32
    assert fixture["scripted_stage_one_call_count"] == 256
    assert fixture["exact_action_payload_count"] == 224
    assert fixture["exact_final_payload_count"] == 32
    assert fixture["reversible_stage_two_commit_count"] == 224
    assert fixture["observation_count"] == 192
    assert fixture["privacy_first_envelope_count"] == 256
    assert fixture["public_payload_projection_count"] == 256
    assert fixture["envelope_before_projection_pass_count"] == 256
    assert fixture["independent_validity_pass_count"] == 32
    assert final["primary_failure_count"] == 1
    assert final["final_rescue_attempt_count"] == 1
    assert final["completed_after_final_rescue_count"] == 1
    assert final["wrong_answer_exact_schema_admission_count"] == 1
    assert final["wrong_answer_independent_validity_failure_count"] == 1
    assert privacy["injected_http_success_call_count"] == 1
    assert privacy["privacy_redacted_envelope_count"] == 1
    assert privacy["privacy_rejected_projection_count"] == 1
    assert privacy["complete_raw_execution_count"] == 1
    assert privacy["payload_failure_deleted_call_count"] == 0
    assert privacy["rejected_payload_content_persisted_count"] == 0
    assert privacy["rejected_payload_key_persisted_count"] == 0
    assert privacy["response_model_retained_count"] == 1
    assert privacy["usage_retained_count"] == 1
    assert privacy["complete_raw_zero_call_recovery_count"] == 1
    assert privacy["orphan_artifact_rejection_count"] == 1
    assert semantic["abi_rescue_count"] == 1
    assert semantic["semantic_recovery_count"] == 1
    assert semantic["first_choice_rejection_retained_count"] == 1
    assert semantic["completed_after_combined_recovery_count"] == 1
    assert certificate["complete_raw_recovery_byte_identical"]
    assert certificate["completion_16385_admitted_and_charged"]
    assert certificate["completion_16386_instrument_failure"]
    assert certificate["calls_blocked_after_instrument_failure"]
    assert destructive["mutation_count"] == destructive["rejection_count"] == 20
    assert transition["only_exact_fresh_32_job_manifest_authorized"]
    assert formal.provider_calls == formal.stage_two_provider_calls == 0
    assert formal.execution_authorized
    assert formal.next_permitted_stage == "exact_final_semantic_action_calibration_execution_only"
