"""Observe immutable prior evidence only; never produce new model or finance execution."""

from __future__ import annotations

import copy
import socket
from pathlib import Path

import pytest

from trusted_synthesis.canonical_json import canonical_json_bytes
from trusted_synthesis.domains.finance.qa_vnext.program_adapter import ProgramTaskAdapter
from trusted_synthesis.domains.finance.qa_vnext.runtime import PublicQARuntime
from trusted_synthesis.domains.finance.qa_vnext.share_adapter import ShareTaskAdapter
from trusted_synthesis.experiments.finance_qa_vnext_model_execution.models import (
    identity,
    read_json,
)
from trusted_synthesis.experiments.finance_qa_vnext_model_execution.transport import HttpxSender
from trusted_synthesis.experiments.finance_qa_vnext_repaired_full_task.measurement import (
    progress as observation_progress,
)
from trusted_synthesis.experiments.finance_qa_vnext_task_panel.progress import progress

ROOT = Path(__file__).resolve().parents[2]
SOURCES = {
    "S": "qa_vnext_repaired_full_task/"
    "finance_qa_vnext_repaired_update_six_session_full_task_20260906/execution/sessions/S01",
    "B": "qa_vnext_action_branch/action_contract_branch_v1_20260906/execution/sessions/B01",
}


def forbidden(*args, **kwargs):
    pytest.fail("progress observer may not execute Runtime, Finance or Provider")


@pytest.fixture(autouse=True)
def zero_reexecution(monkeypatch):
    monkeypatch.setattr(PublicQARuntime, "__init__", forbidden)
    monkeypatch.setattr(ProgramTaskAdapter, "execute", forbidden)
    monkeypatch.setattr(ShareTaskAdapter, "execute", forbidden)
    monkeypatch.setattr(HttpxSender, "send", forbidden)
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket.socket, "connect_ex", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)


@pytest.fixture
def evidence():
    rows = {}
    for group, source in SOURCES.items():
        directory = ROOT / "trusted_data_synthesis/artifacts" / source
        rows[group] = (
            read_json((directory / "runtime/session.json").read_bytes()),
            read_json((directory / "qualification.json").read_bytes()),
        )
    return rows


def test_legal_share_claim_references_without_selector_are_preserved(evidence):
    session, qualification = evidence["S"]
    before = canonical_json_bytes(session), canonical_json_bytes(qualification)
    result = progress(session, qualification)
    identity(result, "task_panel_progress")
    assert result["complete_success"] is True
    assert result["first_branch_merge"] is result["first_absolute_operation"] is None
    assert result["depth_metrics"] == qualification["depth_metrics"]
    consumptions = result["actual_claim_consumptions"]
    assert consumptions
    for action in consumptions:
        event = next(item for item in session["events"] if item["sequence"] == action["sequence"])
        assert action["input_references"] == event["parsed"]["inputs"]
        refs = [ref for ref in event["parsed"]["inputs"] if ref["kind"] == "claim"]
        assert len(refs) == len(action["ordered_claim_dependencies"])
        for ref, dependency in zip(refs, action["ordered_claim_dependencies"], strict=True):
            assert "selector" not in ref
            assert dependency["selector_present"] is False
            assert dependency["selector"] is None
            assert dependency["input_reference"] == ref
            assert "selector" not in dependency["input_reference"]
    assert before == (canonical_json_bytes(session), canonical_json_bytes(qualification))
    assert result["provider_calls"] == result["financial_operation_executions"] == 0


def test_program_selectors_and_actual_branch_merge_are_preserved(evidence):
    session, qualification = evidence["B"]
    result = progress(session, qualification)
    assert result["complete_success"] is True
    assert result["first_lookup_claim_accepted"] is not None
    assert result["first_nontransparent_operation"]["operation"] == "growth"
    assert result["first_branch_merge"]["operation"] == "signed_percentage_point_gap"
    assert result["first_absolute_operation"]["operation"] == "absolute_percentage_point_gap"
    assert [dep["role"] for dep in result["first_branch_merge"]["ordered_claim_dependencies"]] == [
        "income_growth",
        "revenue_growth",
    ]
    for action in result["actual_claim_consumptions"]:
        for dependency in action["ordered_claim_dependencies"]:
            assert dependency["selector_present"] is True
            assert dependency["selector"] == dependency["input_reference"]["selector"]
    assert result["depth_metrics"] == qualification["depth_metrics"]


def test_absent_and_explicit_null_are_distinct_diagnostics_without_validity_claim(evidence):
    """The null/additional-field case is synthetic observer input, not a legal-session claim."""
    session, qualification = evidence["S"]
    changed = copy.deepcopy(session)
    event = next(
        item
        for item in changed["events"]
        if item["receipt"]["admitted"]
        and item.get("execution")
        and any(ref["kind"] == "claim" for ref in item["parsed"].get("inputs", []))
    )
    ref = next(ref for ref in event["parsed"]["inputs"] if ref["kind"] == "claim")
    ref["selector"] = None
    ref["diagnostic_test_extra"] = {"retained": True}
    absent = progress(session, qualification)
    explicit = progress(changed, qualification)
    old_dep = next(
        item
        for item in absent["actual_claim_consumptions"]
        if item["sequence"] == event["sequence"]
    )["ordered_claim_dependencies"][0]
    new_dep = next(
        item
        for item in explicit["actual_claim_consumptions"]
        if item["sequence"] == event["sequence"]
    )["ordered_claim_dependencies"][0]
    assert old_dep["selector"] is new_dep["selector"] is None
    assert old_dep["selector_present"] is False and new_dep["selector_present"] is True
    assert new_dep["input_reference"] == ref
    assert new_dep["input_reference"]["diagnostic_test_extra"] == {"retained": True}


@pytest.mark.parametrize("group", ["S", "B"])
def test_common_observation_and_first_blocking_evidence_are_reused_unchanged(evidence, group):
    session, qualification = evidence[group]
    base = observation_progress(session, qualification)
    observed = progress(session, qualification)
    assert all(
        observed[key] == value for key, value in base.items() if key not in {"id", "schema_version"}
    )
    assert observed["qualification_id"] == qualification["id"]


def test_unknown_and_not_started_without_session_are_not_invented_successes(evidence):
    _, old = evidence["S"]
    qualification = {
        **old,
        "evidence_complete": False,
        "end_to_end_success": None,
        "reason": "missing",
    }
    result = progress(None, qualification)
    assert result["evidence_measured"] is False and result["complete_success"] is None
    assert result["actual_claim_consumptions"] == result["candidate_set_rows"] == []
    assert result["first_branch_merge"] is result["first_absolute_operation"] is None
    assert result["first_blocking_evidence"] == {"qualification_reason": "missing"}
