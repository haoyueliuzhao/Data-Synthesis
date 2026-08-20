from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_budget_closed_instrument_postrun_audit import (  # noqa: E501
    EXPECTED_RECOVERY_REPORT_ID,
    BudgetPostrunAuditReport,
    BudgetPostrunTerminalRow,
    build_budget_closed_postrun_audit,
)

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "artifacts/vtdo_experiment"
FAILED = (
    ARTIFACTS / "finance_v26_84_budget_closed_verifier_bound_instrument_requalification_20260820"
)
RECOVERY_PREFLIGHT = ARTIFACTS / "finance_v26_85_budget_closed_recovery_preflight_20260820"
RECOVERY = ARTIFACTS / "finance_v26_86_budget_closed_verifier_bound_instrument_recovery_20260820"
TASK_SOURCE = (
    ARTIFACTS / "finance_v26_82_budget_closed_verifier_bound_instrument_population_v2_20260820"
)
VERIFIER = ARTIFACTS / "finance_v26_75_authority_preserving_verifier_qualification_v2_20260819"
DETAIL_FILES = (
    "aggregate_reconstruction.json",
    "budget_terminal_audit.json",
    "provider_lineage_audit.json",
    "source_replay_audit.json",
    "verifier_scoring_audit.json",
    "report.json",
)


def _build(output: Path) -> BudgetPostrunAuditReport:
    return build_budget_closed_postrun_audit(
        failed_run_dir=FAILED,
        recovery_preflight_dir=RECOVERY_PREFLIGHT,
        recovery_dir=RECOVERY,
        task_source_dir=TASK_SOURCE,
        verifier_qualification_dir=VERIFIER,
        output_dir=output,
        package_root=ROOT,
    )


def test_independent_postrun_audit_reconstructs_all_gates(tmp_path: Path) -> None:
    output = tmp_path / "audit"
    report = _build(output)
    assert report.status == "passed"
    assert report.recovery_report_id == EXPECTED_RECOVERY_REPORT_ID
    assert report.model_api_calls == 0
    assert not report.model_client_constructed
    lineage = json.loads((output / "provider_lineage_audit.json").read_text())
    terminal = json.loads((output / "budget_terminal_audit.json").read_text())
    verifier = json.loads((output / "verifier_scoring_audit.json").read_text())
    aggregate = json.loads((output / "aggregate_reconstruction.json").read_text())
    assert lineage["original_provider_exact_byte_pass_count"] == 152
    assert lineage["total_provider_artifact_count"] == 241
    assert lineage["provider_call_ids_unique"]
    assert terminal["typed_no_call_count"] == 24
    assert terminal["model_invalid_trajectory_count"] == 8
    assert terminal["maximum_rollout_provider_tokens"] == 79489
    assert terminal["per_rollout_token_pass_count"] == 32
    assert verifier["replay_pass_count"] == 32
    assert verifier["non_replay_gate_reconstruction_pass_count"] == 32
    assert verifier["instrument_admitted_count"] == 32
    assert aggregate["historical_report_vector_exact_match"]
    assert aggregate["mismatch_fields"] == []


def test_independent_postrun_dual_build_is_byte_identical(tmp_path: Path) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    report = _build(first)
    rebuilt = _build(second)
    assert report == rebuilt
    assert all(
        (first / relative).read_bytes() == (second / relative).read_bytes()
        for relative in DETAIL_FILES
    )


def test_terminal_row_rejects_changed_provider_denominator(tmp_path: Path) -> None:
    output = tmp_path / "audit"
    _build(output)
    payload = json.loads((output / "budget_terminal_audit.json").read_text())["rows"][0]
    payload["permitted_request_count"] += 1
    with pytest.raises(ValidationError, match="budget post-run row Provider denominator changed"):
        BudgetPostrunTerminalRow.model_validate(payload)


def test_formal_postrun_audit_when_present() -> None:
    path = ARTIFACTS / "finance_v26_87_budget_closed_postrun_audit_20260820" / "report.json"
    if not path.exists():
        pytest.skip("formal v26.87 audit has not been materialized")
    report = BudgetPostrunAuditReport.model_validate_json(path.read_text(encoding="utf-8"))
    assert report.status == "passed"
    assert report.recovery_instrument_retained
    assert report.model_api_calls == 0
