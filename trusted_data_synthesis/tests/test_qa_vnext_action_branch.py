"""Finite Action disclosure and two-session integration checks; synthetic HTTP only."""

from __future__ import annotations

import socket
import sys
from pathlib import Path

import pytest

from trusted_synthesis.canonical_json import canonical_json_bytes
from trusted_synthesis.domains.finance.qa_vnext.action_public_contract import (
    public_action_contract,
    publish_action_contract,
    rejection_feedback,
)
from trusted_synthesis.domains.finance.qa_vnext.action_readonly import evaluate_action_readonly
from trusted_synthesis.domains.finance.qa_vnext.callbacks import PublicFixtureCallback
from trusted_synthesis.domains.finance.qa_vnext.program_adapter import ProgramTaskAdapter
from trusted_synthesis.domains.finance.qa_vnext.protocol import ProtocolError
from trusted_synthesis.domains.finance.qa_vnext.runtime import DurableStore, PublicQARuntime
from trusted_synthesis.domains.finance.qa_vnext.share_adapter import ShareTaskAdapter
from trusted_synthesis.domains.finance.qa_vnext.update_public_contract import (
    rejection_feedback as update_feedback,
)
from trusted_synthesis.experiments.finance_qa_vnext_action_branch import plan, runner
from trusted_synthesis.experiments.finance_qa_vnext_action_branch.__main__ import main
from trusted_synthesis.experiments.finance_qa_vnext_action_branch.controls import (
    isolated_action_receiver,
    run_controls,
    saved_requests,
    validator_preservation,
)
from trusted_synthesis.experiments.finance_qa_vnext_model_execution import runner as original_runner
from trusted_synthesis.experiments.finance_qa_vnext_model_execution.models import read_json, record
from trusted_synthesis.experiments.finance_qa_vnext_model_execution.representation import (
    register_tokenizer,
)
from trusted_synthesis.experiments.finance_qa_vnext_model_execution.transport import (
    SYSTEM_PROMPT,
    HTTPResponse,
    HttpxSender,
    TransportConfig,
)

ROOT = Path(__file__).resolve().parents[2]
DESIGN = Path(
    "/home/zhuxinrui/.codex/attachments/3f5ff547-07af-4d78-8ca1-068e1c9c7dc8/pasted-text.txt"
)


def forbidden(*args, **kwargs):
    pytest.fail("test may not call Provider, real credentials, or replay financial Operations")


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(runner, "_credential", forbidden)


@pytest.fixture(scope="module")
def panel():
    return plan.load_panel(ROOT)


@pytest.fixture(scope="module")
def source_requests(panel):
    return saved_requests(panel)


def test_original_standards_and_update_publication_preserved():
    result = validator_preservation(ROOT)
    assert result["passed"] and len(result["checks"]) == 7


def test_only_two_fresh_B_registrations_and_64_bound():
    config = plan.configuration()
    condition, rows, panel = plan.freeze_condition(
        ROOT, config.as_record(), record("implementation", synthetic=True), run_tag="test-branch"
    )
    assert config.system_prompt == SYSTEM_PROMPT
    assert config.attempts_per_session == 32 and config.maximum_pilot_attempts == 64
    assert [r["label"] for r in rows] == ["B01", "B02"]
    assert {r["task_group"] for r in rows} == {"B"}
    assert {r["round"] for r in rows} == {1}
    assert len({r["session_id"] for r in rows}) == 2
    assert (
        condition["session_count"] == 2
        and condition["maximum_reserved_token_allowance"] == 64 * 107520
    )
    assert sum(r["registered_model_sessions"] for r in panel.coverage) == 2
    assert sum(r["selected_for_model_population"] for r in panel.coverage) == 1
    assert condition["public_action_contract"] == public_action_contract()


@pytest.mark.parametrize(
    "config",
    [
        TransportConfig(),
        TransportConfig(maximum_pilot_attempts=192),
        TransportConfig(maximum_pilot_attempts=64, attempts_per_session=1),
    ],
)
def test_old_population_and_calibration_configurations_rejected(config):
    with pytest.raises(ProtocolError, match="branch.fixed_configuration"):
        plan.freeze_condition(ROOT, config.as_record(), record("implementation"), run_tag="bad")


def test_dynamic_controls_same_acceptance_sets_and_no_execution(panel, tmp_path, monkeypatch):
    monkeypatch.setattr(PublicQARuntime, "run", forbidden)
    monkeypatch.setattr(ProgramTaskAdapter, "execute", forbidden)
    monkeypatch.setattr(ShareTaskAdapter, "execute", forbidden)
    monkeypatch.setattr(HttpxSender, "send", forbidden)
    result = run_controls(panel, tmp_path / "controls", plan.configuration())
    assert result["passed"] and result["control_count"] == 69
    assert result["covered_branch_candidate_counts"] == [2, 3, 4]
    assert result["local_admission_evaluations"] == 138
    assert result["provider_calls"] == result["action_executions"] == 0
    assert all(
        r["before"]["action_admitted"] == r["after"]["action_admitted"] for r in result["rows"]
    )
    assert max(r["body_bytes"] for r in result["full_branch_budget_rows"]) <= 98304
    assert {r["case"] for r in result["rows"]} >= {
        "stale_initial_full_set",
        "input_order_not_set_equality",
        "other_candidate_basis",
        "other_candidate_operation",
    }


def test_feedback_reports_current_missing_extra_duplicates_without_repair(panel, source_requests):
    old = next(
        r["request"]
        for r in source_requests
        if r["group"] == "B" and len(r["request"]["available_actions"]) == 4
    )
    request = publish_action_contract(old)
    value = isolated_action_receiver(request, request["available_actions"][0]["id"])
    chosen = value["decision"]["selected_action_id"]
    value["decision"]["candidate_action_ids"] = [chosen, chosen, "control:extra"]
    before = canonical_json_bytes(value), canonical_json_bytes(request)
    result = evaluate_action_readonly(canonical_json_bytes(value), request, panel.adapter("B"))
    assert not result["action_admitted"] and result["error_code"] == "admission.alternative_set"
    diagnostic = result["feedback"]["public_diagnostic"]
    assert diagnostic["missing_ids"] == sorted(
        a["id"] for a in request["available_actions"] if a["id"] != chosen
    )
    assert diagnostic["extra_ids"] == ["control:extra"] and diagnostic["duplicate_ids"] == [chosen]
    assert diagnostic["rule_id"].endswith(":alternative_set")
    assert diagnostic["response_rewritten"] is diagnostic["action_selected_by_host"] is False
    assert (canonical_json_bytes(value), canonical_json_bytes(request)) == before


@pytest.mark.parametrize(
    "field,expected",
    [
        ("operation", "admission.selected_action_content"),
        ("inputs", "admission.selected_action_content"),
        ("parameters", "admission.selected_action_content"),
        ("obligation_id", "admission.public_judgment"),
        ("subgoal", "admission.public_judgment"),
        ("basis", "admission.public_judgment"),
        ("expected_effect", "admission.public_judgment"),
        ("selection_rule", "admission.public_judgment"),
        ("unresolved_uncertainty_refs", "admission.public_judgment"),
    ],
)
def test_selected_correspondence_feedback_names_violated_field(
    panel, source_requests, field, expected
):
    old = next(
        r["request"]
        for r in source_requests
        if r["group"] == "B"
        and any(a["operation"] == "growth" for a in r["request"]["available_actions"])
    )
    request = publish_action_contract(old)
    selected = next(a for a in request["available_actions"] if a["operation"] == "growth")
    value = isolated_action_receiver(request, selected["id"])
    if field == "operation":
        value[field] = "lookup"
    elif field == "inputs":
        value[field].reverse()
    elif field == "parameters":
        value[field] = {"method": "wrong"}
    elif field == "obligation_id":
        value["decision"][field] = "other_obligation"
    elif field == "subgoal":
        value["decision"][field] = "resolve_evidence"
    elif field == "basis":
        value["decision"][field]["claim_refs"] = []
    elif field == "expected_effect":
        value["decision"][field]["establishes_obligation"] = "other_obligation"
    elif field == "selection_rule":
        value["decision"][field] = "disclosed_total"
    else:
        value["decision"][field] = ["invented_uncertainty"]
    result = evaluate_action_readonly(canonical_json_bytes(value), request, panel.adapter("B"))
    assert result["error_code"] == expected
    pointer = (
        "/" + field if field in {"operation", "inputs", "parameters"} else "/decision/" + field
    )
    assert pointer in result["feedback"]["public_diagnostic"]["response_field_paths"]


def test_existing_update_and_final_feedback_are_not_changed(source_requests):
    request = publish_action_contract(source_requests[0]["request"])
    for code, value in [
        ("admission.final_qa", {"kind": "final"}),
        ("submission.schema", None),
        ("admission.observation_parent", {"kind": "update"}),
    ]:
        assert rejection_feedback(code, request, value) == update_feedback(code, request, value)


def setup_population(tmp_path, monkeypatch, *, actual_prepare=False):
    preparation = tmp_path / "preparation"
    if actual_prepare:
        monkeypatch.setattr(
            sys,
            "argv",
            [
                "branch",
                "prepare",
                "--root",
                str(ROOT),
                "--preparation",
                str(preparation),
                "--design",
                str(DESIGN),
                "--run-tag",
                "actual-branch-cli-roundtrip",
            ],
        )
        main()
        prepared = plan._prepared(ROOT, preparation)
    else:
        implementation = record("implementation", synthetic_unit_test=True)
        condition, registrations, panel = plan.freeze_condition(
            ROOT, plan.configuration().as_record(), implementation, run_tag="synthetic-branch"
        )
        store = DurableStore(preparation)
        for r in registrations:
            store.json(
                f"initial/{r['label']}_request.json", plan.initial_request(panel.adapter("B"))
            )
        prepared = {
            "implementation": implementation,
            "condition": condition,
            "registrations": registrations,
            "panel": panel,
            "config": plan.configuration(),
            "coverage": panel.coverage,
            "tokenizer_binding": register_tokenizer(ROOT),
            "report": record(
                "action_branch_preparation", execution_directory=str(tmp_path / "execution")
            ),
            "manifest": record("preparation_manifest", synthetic_unit_test=True),
        }
        monkeypatch.setattr(runner, "_prepared", lambda root, p: prepared)
        monkeypatch.setattr(runner, "verify_source_snapshot", lambda root, value: None)
    return preparation, prepared


def install_http(monkeypatch, prepared, tmp_path, behavior):
    sends = []
    labels = {r["session_id"]: r["label"] for r in prepared["registrations"]}

    def send(sender, http, *, api_key):
        assert api_key == "synthetic-placeholder-not-a-credential"
        label = labels[http["session_id"]]
        request = read_json(http["messages"][1]["content"].encode())
        assert request["public_action_contract"] == public_action_contract()
        assert http["messages"][0]["content"] == SYSTEM_PROMPT
        sends.append(label)
        if behavior == "empty" or behavior == "known_failure" and label == "B01":
            raw = b""
        elif request["available_actions"]:
            options = request["available_actions"]
            # Exercise both legal schedules without prescribing one in the real condition.
            selected = options[0 if label == "B01" else -1]
            value = isolated_action_receiver(request, selected["id"])
            if (
                behavior == "limit"
                or behavior == "correction"
                and label == "B01"
                and request["state"]["submission_count"] == 0
            ):
                value["decision"]["candidate_action_ids"] = [selected["id"]]
            raw = canonical_json_bytes(value)
        else:
            raw = PublicFixtureCallback().generate(request)
        return HTTPResponse(
            200,
            canonical_json_bytes(
                {
                    "id": "synthetic-branch-never-provider",
                    "object": "chat.completion",
                    "model": "deepseek-v4-pro",
                    "choices": [
                        {
                            "index": 0,
                            "finish_reason": "stop",
                            "message": {"role": "assistant", "content": raw.decode()},
                        }
                    ],
                }
            ),
        )

    monkeypatch.setattr(HttpxSender, "send", send)
    monkeypatch.setattr(
        runner, "_credential", lambda path: "synthetic-placeholder-not-a-credential"
    )
    if behavior == "unknown":
        original = original_runner.qualify_session

        def missing(*args, **kwargs):
            registration, session, transport = args[1], args[2], Path(args[4])
            if registration["label"] == "B01" and session is not None:
                path = transport / "attempts/000_http_response.body"
                assert path.is_relative_to(tmp_path)
                if path.exists():
                    path.unlink()  # Only newly generated pytest evidence.
            return original(*args, **kwargs)

        monkeypatch.setattr(original_runner, "qualify_session", missing)
        monkeypatch.setattr(runner, "qualify_session", missing)
    return sends


@pytest.mark.parametrize(
    "behavior", ["success", "correction", "known_failure", "unknown", "empty", "limit"]
)
def test_two_session_runtime_qualification_progress_export_and_reanalysis(
    tmp_path, monkeypatch, behavior
):
    preparation, prepared = setup_population(tmp_path, monkeypatch)
    sends = install_http(monkeypatch, prepared, tmp_path, behavior)
    result = runner.run(ROOT, preparation)
    assert set(sends) == {"B01", "B02"} and len(sends) <= 64
    assert result["measurement"]["registered_session_denominator"] == 2
    assert result["measurement"]["fixed_task_denominator"] == 1
    assert result["maximum_reserved_token_allowance"] == 64 * 107520
    assert result["finite_comparison_count"] <= 1
    if behavior in {"success", "correction"}:
        assert result["measurement"]["equal_task_weight_mean"] == 1
        assert result["candidate_count"] == 34 and len(sends) == (
            35 if behavior == "correction" else 34
        )
        assert result["scientific_objects"]["branch_complete_reachability_witness"]
        for row in result["session_rows"]:
            p = row["progress"]
            assert p["first_nontransparent_operation"]["operation"] == "growth"
            assert p["first_branch_merge"] and p["first_absolute_operation"]
            assert p["first_claim_consumption"] and row["qualified"]
            assert row["depth_metrics"]["actual_action_dependency_semantic_depth"] == 3
            assert row["request_presentation"]["all_full_task_publication"]
        if behavior == "correction":
            assert result["session_rows"][0]["projection_status"] == "undetermined"
            assert (
                result["session_rows"][0]["progress"]["candidate_set_rows"][0][
                    "full_set_and_unique"
                ]
                is False
            )
    elif behavior == "known_failure":
        assert (
            result["measurement"]["equal_task_weight_mean"] == 0.5
            and result["candidate_count"] == 17
        )
    elif behavior == "unknown":
        assert result["measurement"]["equal_task_weight_mean"] is None
        assert [r["status"] for r in result["session_rows"]] == ["unknown", "success"]
    else:
        assert (
            result["measurement"]["equal_task_weight_mean"] == 0 and result["candidate_count"] == 0
        )
        assert not result["scientific_objects"]["positive_token_representation_validated"]
        assert len(sends) == (64 if behavior == "limit" else 2)
    with pytest.raises(ProtocolError, match="run.population_already_started"):
        runner.run(ROOT, preparation)
    monkeypatch.setattr(HttpxSender, "send", forbidden)
    monkeypatch.setattr(runner, "_credential", forbidden)
    monkeypatch.setattr(PublicQARuntime, "run", forbidden)
    monkeypatch.setattr(ProgramTaskAdapter, "execute", forbidden)
    monkeypatch.setattr(ShareTaskAdapter, "execute", forbidden)
    again = runner.analyze(ROOT, preparation, tmp_path / "execution", tmp_path / "reanalysis")
    assert canonical_json_bytes(again) == canonical_json_bytes(result)


def test_actual_committed_cli_and_two_session_roundtrip(tmp_path, monkeypatch):
    if not DESIGN.exists():
        pytest.skip("exact user experimental design is not available locally")
    preparation, prepared = setup_population(tmp_path, monkeypatch, actual_prepare=True)
    sends = install_http(monkeypatch, prepared, tmp_path, "success")
    result = runner.run(ROOT, preparation)
    assert len(sends) == 34 and result["candidate_count"] == 34
    assert result["workflow_evidence_complete"] and result["full_two_session_execution_complete"]
