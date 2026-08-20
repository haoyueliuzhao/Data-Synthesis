from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_budget_adequacy_root_cause_audit import (  # noqa: E501
    BudgetAdequacyDecision,
    BudgetAdequacyJobDiagnostic,
    BudgetAdequacyRootCauseReport,
    BudgetAdequacySourceEntry,
    build_budget_adequacy_root_cause_audit,
)

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "artifacts/vtdo_experiment"
RECOVERY = ARTIFACTS / "finance_v26_86_budget_closed_verifier_bound_instrument_recovery_20260820"
POSTRUN = ARTIFACTS / "finance_v26_87_budget_closed_postrun_audit_20260820"
TASK_SOURCE = (
    ARTIFACTS / "finance_v26_82_budget_closed_verifier_bound_instrument_population_v2_20260820"
)
FORMAL = ARTIFACTS / "finance_v26_88_budget_adequacy_root_cause_audit_20260820"
FILES = (
    "budget_adequacy_decision.json",
    "group_budget_summary.json",
    "job_budget_diagnostics.json",
    "source_replay_audit.json",
    "report.json",
)


def _build(output: Path) -> BudgetAdequacyRootCauseReport:
    return build_budget_adequacy_root_cause_audit(
        recovery_dir=RECOVERY,
        postrun_audit_dir=POSTRUN,
        task_source_dir=TASK_SOURCE,
        output_dir=output,
        package_root=ROOT,
    )


def test_root_cause_audit_reconstructs_budget_censoring(tmp_path: Path) -> None:
    output = tmp_path / "audit"
    report = _build(output)
    root = json.loads((output / "job_budget_diagnostics.json").read_text())
    assert report.status == "passed"
    assert report.model_api_calls == 0
    assert root["typed_no_call_count"] == 24
    assert root["denied_request_kind_counts"] == {"decision": 24}
    assert root["denial_attribution_counts"] == {
        "request_bound": 8,
        "required_reserve": 16,
    }
    assert root["no_call_by_mechanism"] == {
        "context_conditioned_action": 7,
        "failure_recovery": 1,
        "semantic_reconciliation": 8,
        "state_dependent_stopping": 8,
    }
    assert root["zero_progress_no_call_count"] == 21
    assert root["positive_progress_no_call_count"] == 3
    assert root["terminal_completed_unverified_no_call_count"] == 1
    assert root["final_answer_only_candidate_count"] == 0
    assert root["failed_observation_count_in_no_call_rows"] == 57
    assert root["identical_call_repeat_count_in_no_call_rows"] == 43
    assert root["identical_failed_call_repeat_count_in_no_call_rows"] == 25
    assert root["median_token_usage_before_denial"] == 76881
    assert root["median_prompt_growth_bytes"] == 17947
    assert root["median_headroom_deficit"] == 7503
    assert root["maximum_headroom_deficit"] == 9333
    assert root["common_ceiling_for_only_observed_denied_calls"] == 129333
    assert root["request_would_fit_without_reserves_count"] == 16
    assert root["reset_to_initial_prompt_would_fit_count"] == 24
    assert not root["budget_adequacy_established"]


def test_root_cause_dual_build_is_byte_identical(tmp_path: Path) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    assert _build(first) == _build(second)
    assert all(
        (first / relative).read_bytes() == (second / relative).read_bytes() for relative in FILES
    )


def test_job_row_rejects_changed_deficit_arithmetic(tmp_path: Path) -> None:
    output = tmp_path / "audit"
    _build(output)
    rows = json.loads((output / "job_budget_diagnostics.json").read_text())["rows"]
    payload = next(item for item in rows if item["budget_denied"])
    payload["headroom_deficit"] += 1
    with pytest.raises(ValidationError, match="total deficit changed"):
        BudgetAdequacyJobDiagnostic.model_validate(payload)


def test_decision_rejects_posthoc_budget_authorization(tmp_path: Path) -> None:
    output = tmp_path / "audit"
    _build(output)
    payload = json.loads((output / "budget_adequacy_decision.json").read_text())
    payload["direct_total_budget_increase_authorized"] = True
    with pytest.raises(ValidationError):
        BudgetAdequacyDecision.model_validate(payload)


def test_source_entry_rejects_changed_bytes() -> None:
    payload = {
        "relative_path": "source.py",
        "expected_sha256": "a" * 64,
        "observed_sha256": "b" * 64,
        "byte_count": 1,
        "source_kind": "v26_88_implementation",
    }
    with pytest.raises(ValidationError, match="source bytes changed"):
        BudgetAdequacySourceEntry.model_validate(payload)


def test_formal_budget_adequacy_audit_when_present() -> None:
    path = FORMAL / "report.json"
    if not path.exists():
        pytest.skip("formal v26.88 Budget Adequacy audit has not been materialized")
    report = BudgetAdequacyRootCauseReport.model_validate_json(path.read_text(encoding="utf-8"))
    assert report.status == "passed"
    assert report.next_permitted_stage == (
        "fresh_budget_adequacy_contract_and_static_role_preflight_only"
    )
    assert report.model_api_calls == 0
