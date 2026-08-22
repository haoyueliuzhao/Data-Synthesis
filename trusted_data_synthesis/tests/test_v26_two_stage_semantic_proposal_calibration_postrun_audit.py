from __future__ import annotations

import json
from pathlib import Path

from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_two_stage_semantic_proposal_calibration_postrun_audit import (  # noqa: E501
    NEXT_STAGE,
    AuthorityInstrumentAudit,
    CompletionRescueAudit,
    DestructiveAudit,
    PostrunSourceReplayAudit,
    PromptDisclosureAudit,
    ResponseInterfaceAudit,
    build_two_stage_semantic_proposal_calibration_postrun_audit,
)

LOCAL_PACKAGE_ROOT = Path(__file__).resolve().parents[1]
CANONICAL_PACKAGE_ROOT = Path(
    "/home/zhuxinrui/datatmp/projects/Data-Synthesis/trusted_data_synthesis"
)
PACKAGE_ROOT = CANONICAL_PACKAGE_ROOT if CANONICAL_PACKAGE_ROOT.is_dir() else LOCAL_PACKAGE_ROOT


def _load(path: Path) -> object:
    return json.loads(path.read_bytes())


def test_v26_111_reproduces_execution_and_response_interface(
    tmp_path: Path,
) -> None:
    report = build_two_stage_semantic_proposal_calibration_postrun_audit(
        output_dir=tmp_path,
        package_root=PACKAGE_ROOT,
        implementation_root=LOCAL_PACKAGE_ROOT,
    )
    response = ResponseInterfaceAudit.model_validate(
        _load(tmp_path / "response_interface_audit.json")
    )
    completion = CompletionRescueAudit.model_validate(
        _load(tmp_path / "completion_rescue_audit.json")
    )
    authority = AuthorityInstrumentAudit.model_validate(
        _load(tmp_path / "authority_instrument_audit.json")
    )
    assert report.exact_job_denominator == 32
    assert report.provider_call_count == 64
    assert response.response_payload_count == 51
    assert response.unique_top_level_key_set_count == 46
    assert response.exact_schema_accept_count == 0
    assert response.primary_missing_state_id_count == 31
    assert response.rescue_missing_decision_kind_count == 20
    assert completion.terminal_counts == {
        "completion_unusable": 12,
        "model_invalid_trajectory": 20,
    }
    assert completion.rescue_success_count == 0
    assert authority.instrument_failure_count == 0
    assert authority.stage_two_provider_call_count == 0
    assert authority.stage_two_commit_count == 0
    assert report.next_permitted_stage == NEXT_STAGE


def test_v26_111_reproduces_prompt_disclosure_and_source_replay(
    tmp_path: Path,
) -> None:
    build_two_stage_semantic_proposal_calibration_postrun_audit(
        output_dir=tmp_path,
        package_root=PACKAGE_ROOT,
        implementation_root=LOCAL_PACKAGE_ROOT,
    )
    source = PostrunSourceReplayAudit.model_validate(_load(tmp_path / "source_replay_audit.json"))
    prompt = PromptDisclosureAudit.model_validate(_load(tmp_path / "prompt_disclosure_audit.json"))
    assert source.replayed_file_count == 2017
    assert source.replay_pass_count == 2017
    assert source.model_api_calls == 0
    assert prompt.exact_payload_field_count == 10
    assert prompt.primary_exact_field_name_disclosure_count == 1
    assert prompt.rescue_exact_field_name_disclosure_count == 1
    assert prompt.primary_prompt_hash_reproduction_count == 32
    assert prompt.rescue_prompt_hash_reproduction_count == 32


def test_v26_111_dual_build_is_byte_identical(tmp_path: Path) -> None:
    formal = tmp_path / "formal"
    independent = tmp_path / "independent"
    first = build_two_stage_semantic_proposal_calibration_postrun_audit(
        output_dir=formal,
        package_root=PACKAGE_ROOT,
        implementation_root=LOCAL_PACKAGE_ROOT,
    )
    second = build_two_stage_semantic_proposal_calibration_postrun_audit(
        output_dir=independent,
        package_root=PACKAGE_ROOT,
        implementation_root=LOCAL_PACKAGE_ROOT,
    )
    assert first == second
    formal_files = tuple(sorted(path.name for path in formal.iterdir()))
    independent_files = tuple(sorted(path.name for path in independent.iterdir()))
    assert formal_files == independent_files
    assert len(formal_files) == 10
    assert all(
        (formal / filename).read_bytes() == (independent / filename).read_bytes()
        for filename in formal_files
    )


def test_v26_111_destructive_controls_fail_closed(tmp_path: Path) -> None:
    build_two_stage_semantic_proposal_calibration_postrun_audit(
        output_dir=tmp_path,
        package_root=PACKAGE_ROOT,
        implementation_root=LOCAL_PACKAGE_ROOT,
    )
    destructive = DestructiveAudit.model_validate(_load(tmp_path / "destructive_audit.json"))
    assert destructive.mutation_count == 20
    assert destructive.rejected_count == 20
    assert destructive.provider_calls == 0
    assert len({item.mutation for item in destructive.mutation_results}) == 20
