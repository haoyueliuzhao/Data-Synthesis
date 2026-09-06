"""Real eight-adapter wiring with constructed HTTP bytes, never model samples.

Only the HTTP sender and literal credential IO are substituted in the committed
round trip. Ordinary precommit tests additionally bind the current Python bytes
instead of claiming those bytes already belong to a committed implementation.
The source preservation, catalog, configuration, execution, qualification,
representation and finite measurement code paths remain the production paths.
"""

from __future__ import annotations

import socket
from collections import Counter
from pathlib import Path

import pytest

from trusted_synthesis.canonical_json import canonical_json_bytes
from trusted_synthesis.domains.finance.qa_vnext.action_public_contract import (
    public_action_contract,
)
from trusted_synthesis.domains.finance.qa_vnext.callbacks import PublicFixtureCallback
from trusted_synthesis.domains.finance.qa_vnext.protocol import ProtocolError
from trusted_synthesis.domains.finance.qa_vnext.runtime import PublicQARuntime
from trusted_synthesis.domains.finance.qa_vnext.update_public_contract import public_update_contract
from trusted_synthesis.experiments.finance_qa_vnext_model_execution import runner as online_runner
from trusted_synthesis.experiments.finance_qa_vnext_model_execution.models import (
    read_json,
    record,
    sha,
)
from trusted_synthesis.experiments.finance_qa_vnext_model_execution.transport import (
    SYSTEM_PROMPT,
    HTTPResponse,
    HttpxSender,
)
from trusted_synthesis.experiments.finance_qa_vnext_task_panel import plan, stage

ROOT = Path(__file__).resolve().parents[2]
DESIGN = Path(
    "/home/zhuxinrui/.codex/attachments/2942fc0e-c982-484c-a179-8cb06dfb051a/pasted-text.txt"
)
TEST_KEY = "synthetic-unit-test-placeholder-not-a-provider-credential"


def forbidden(*args, **kwargs):
    pytest.fail("panel integration test attempted real network, credentials, or execution replay")


@pytest.fixture(autouse=True)
def no_external_io(monkeypatch):
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket.socket, "connect_ex", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(HttpxSender, "send", forbidden)
    monkeypatch.setattr(online_runner, "_credential", forbidden)


def current_test_source_snapshot(root):
    """Old verify_source_snapshot checks every current member; no verifier bypass."""
    members = []
    for path in sorted((root / "trusted_data_synthesis/src").rglob("*.py")):
        raw = path.read_bytes()
        members.append(
            {"path": path.relative_to(root).as_posix(), "bytes": len(raw), "sha256": sha(raw)}
        )
    return record(
        "implementation",
        source_commit="synthetic-uncommitted-test-only",
        source_tree="synthetic-uncommitted-test-only",
        members=members,
        every_python_source_bound=True,
        synthetic_uncommitted_test_only=True,
    )


def prepare_population(tmp_path, monkeypatch, *, committed=False):
    if not DESIGN.exists():
        pytest.skip("exact user design attachment unavailable locally")
    if not committed:
        monkeypatch.setattr(stage, "source_snapshot", current_test_source_snapshot)
    directory = tmp_path / "preparation"
    stage.prepare(ROOT, directory, DESIGN, run_tag="synthetic-panel-http-wiring-only")
    prepared = stage.prepared(ROOT, directory)
    assert prepared["source_preservation"]["all_predecessor_sources_byte_identical"] is True
    assert prepared["configuration"]["maximum_pilot_attempts"] == 512
    assert prepared["condition"]["maximum_reserved_token_allowance"] == 55_050_240
    assert [row["label"] for row in prepared["registrations"]] == [
        f"{group}{round_number:02d}" for round_number in (1, 2) for group in plan.ROUND_TASK_ORDER
    ]
    assert len({row["id"] for row in prepared["registrations"]}) == 16
    assert len({row["task_id"] for row in prepared["registrations"]}) == 8
    return directory, prepared


def install_constructed_http(monkeypatch, prepared, *, malformed_label=None):
    labels = {row["session_id"]: row["label"] for row in prepared["registrations"]}
    fixture = PublicFixtureCallback()
    sends = []

    def send(sender, http, *, api_key):
        assert api_key == TEST_KEY
        label = labels[http["session_id"]]
        request = read_json(http["messages"][1]["content"].encode())
        assert http["messages"][0] == {"role": "system", "content": SYSTEM_PROMPT}
        assert request["public_action_contract"] == public_action_contract()
        assert request["public_update_contract"] == public_update_contract()
        assert len(http["messages"]) == 2
        sends.append(label)
        raw = b"not JSON" if label == malformed_label else fixture.generate(request)
        return HTTPResponse(
            200,
            canonical_json_bytes(
                {
                    "id": f"synthetic-panel-never-provider-{label}-{http['attempt_index']}",
                    "object": "chat.completion",
                    "model": "deepseek-v4-pro",
                    "choices": [
                        {
                            "index": 0,
                            "finish_reason": "stop",
                            "message": {"role": "assistant", "content": raw.decode()},
                        }
                    ],
                    "usage": {
                        "prompt_tokens": 100,
                        "completion_tokens": 10,
                        "total_tokens": 110,
                        "completion_tokens_details": {"reasoning_tokens": 0},
                    },
                }
            ),
        )

    monkeypatch.setattr(HttpxSender, "send", send)
    monkeypatch.setattr(online_runner, "_credential", lambda path: TEST_KEY)
    return sends


def find_analysis_record(directory, kind):
    """Locate the standalone result artifact without depending on report filenames."""
    expected = f"qa_vnext_model_execution_{kind}.v1"
    found = []
    for path in sorted(directory.rglob("*.json")):
        if {"sessions", "initial", "cpu_batches", "turns", "attempts"} & set(
            path.relative_to(directory).parts
        ):
            continue
        value = read_json(path.read_bytes())
        if isinstance(value, dict) and value.get("schema_version") == expected:
            found.append(value)
    assert len(found) == 1, (kind, len(found))
    return found[0]


def assert_registered_measurement(result):
    measured = result["measurement"]
    assert measured["registered_session_denominator"] == 16
    assert measured["fixed_task_denominator"] == 8
    assert len(measured["session_rows"]) == 16 and len(measured["task_rows"]) == 8
    assert {row["task_group"] for row in measured["task_rows"]} == set(plan.TASK_GROUPS)
    assert all(row["registered_denominator"] == 2 for row in measured["task_rows"])
    assert all(
        row["design_task_marginal"] == {"numerator": 1, "denominator": 8}
        for row in measured["task_rows"]
    )
    assert measured["design_marginal_renormalized"] is False
    assert measured["historical_model_sessions_pooled"] == 0
    assert measured["replacement_sessions"] == 0
    assert measured["finite_comparison_count"] <= 8
    return measured


def test_eight_task_sixteen_session_constructed_http_roundtrip_and_readonly_reanalysis(
    tmp_path, monkeypatch
):
    from trusted_synthesis.experiments.finance_qa_vnext_task_panel import runner

    preparation, prepared = prepare_population(tmp_path, monkeypatch)
    sends = install_constructed_http(monkeypatch, prepared)
    result = runner.run(ROOT, preparation)
    measured = assert_registered_measurement(result)
    assert measured["success_numerator"] == 16 and measured["equal_task_weight_mean"] == 1
    assert measured["unknown"] == measured["known_failures"] == measured["not_started"] == 0
    assert set(sends) == {row["label"] for row in prepared["registrations"]}
    assert max(Counter(sends).values()) <= 32 and len(sends) <= 512
    assert measured["complete_repr_packages"] == 16
    assert all(row["complete_repr_packages"] == 2 for row in measured["task_rows"])
    assert measured["all_selected_tasks_have_success_witness"] is True
    assert measured["full_support_training_materialized"] is False
    dependencies = {
        group: [
            dependency
            for row in result["session_rows"]
            if row["task_group"] == group
            for consumption in row["progress"]["actual_claim_consumptions"]
            for dependency in consumption["ordered_claim_dependencies"]
        ]
        for group in ("S", "B")
    }
    assert dependencies["S"] and dependencies["B"]
    assert any(
        item["selector_present"] is False
        and item["selector"] is None
        and "selector" not in item["input_reference"]
        for item in dependencies["S"]
    )
    assert all(
        item["selector_present"] is True
        and item["selector"] == item["input_reference"]["selector"]
        for item in dependencies["B"]
    )
    tokens = find_analysis_record(tmp_path / "execution", "task_panel_token_representation_dataset")
    binding = find_analysis_record(tmp_path / "execution", "task_panel_representation_data_binding")
    packages = find_analysis_record(tmp_path / "execution", "task_panel_session_packages")
    cpu = find_analysis_record(tmp_path / "execution", "task_panel_cpu_loading")
    assert binding["generation_condition_id"] == prepared["condition"]["id"]
    assert binding["representation_policy_id"] == prepared["representation_policy"]["id"]
    assert len(binding["registration_ids"]) == len(binding["qualification_ids"]) == 16
    assert tokens["candidate_count"] == tokens["fit_count"] == cpu["loaded_records"] == len(sends)
    assert tokens["maximum_sequence_length"] == 32768 and tokens["not_fit_count"] == 0
    assert prepared["tokenizer_binding"]["maximum_sequence_length"] == 24576
    assert packages["complete_session_packages"] == len(packages["rows"]) == 16
    assert len({row["expected_units"] for row in packages["rows"]}) > 1
    assert min(row["expected_units"] for row in packages["rows"]) == 3
    assert cpu["maximum_batch_size"] == 2 and cpu["all_tensors_cpu"] is True
    assert sum(item["batch"]["shape"][0] for item in cpu["batches"]) == len(sends)
    with pytest.raises(ProtocolError):
        runner.run(ROOT, preparation)
    monkeypatch.setattr(HttpxSender, "send", forbidden)
    monkeypatch.setattr(online_runner, "_credential", forbidden)
    monkeypatch.setattr(PublicQARuntime, "run", forbidden)
    again = runner.analyze(ROOT, preparation, tmp_path / "execution", tmp_path / "reanalysis")
    assert canonical_json_bytes(again) == canonical_json_bytes(result)


def test_known_model_failure_is_not_replaced_or_a_halt_for_other_fifteen(tmp_path, monkeypatch):
    from trusted_synthesis.experiments.finance_qa_vnext_task_panel import runner

    preparation, prepared = prepare_population(tmp_path, monkeypatch)
    sends = install_constructed_http(monkeypatch, prepared, malformed_label="F01")
    result = runner.run(ROOT, preparation)
    measured = assert_registered_measurement(result)
    assert Counter(sends)["F01"] == 32 and len(set(sends)) == 16
    assert measured["success_numerator"] == 15 and measured["known_failures"] == 1
    assert measured["unknown"] == measured["not_started"] == 0
    assert measured["equal_task_weight_mean"] == 15 / 16
    failed = next(row for row in measured["session_rows"] if row["label"] == "F01")
    assert failed["status"] == "known_failure" and failed["qualified"] is False
    assert failed["representation_candidate_rows"] == 0
    assert failed["complete_representation_package"] is False
    fact = next(row for row in measured["task_rows"] if row["task_group"] == "F")
    assert fact["complete_success_fraction"] == {"numerator": 1, "denominator": 2}
    assert fact["success_pool_task_share"] == {"numerator": 1, "denominator": 15}
    assert fact["design_task_marginal"] == {"numerator": 1, "denominator": 8}


def test_internal_worker_exception_keeps_unknown_and_fourteen_unstarted(tmp_path, monkeypatch):
    from trusted_synthesis.experiments.finance_qa_vnext_task_panel import runner

    preparation, prepared = prepare_population(tmp_path, monkeypatch)
    sends = install_constructed_http(monkeypatch, prepared)
    original = online_runner._run_session

    def fail_before_runtime(panel, config, registration, store, start, api_key):
        if registration["label"] == "F01":
            raise RuntimeError("synthetic worker exception before Runtime")
        return original(panel, config, registration, store, start, api_key)

    monkeypatch.setattr(online_runner, "_run_session", fail_before_runtime)
    result = runner.run(ROOT, preparation)
    measured = assert_registered_measurement(result)
    by_label = {row["label"]: row for row in measured["session_rows"]}
    assert set(sends) == {"C01"}
    assert by_label["F01"]["status"] == "unknown" and by_label["F01"]["qualified"] is None
    assert by_label["C01"]["status"] == "success"
    assert measured["unknown"] == 1 and measured["not_started"] == 14
    assert measured["success_numerator"] == 1 and measured["known_failures"] == 0
    assert measured["equal_task_weight_mean"] is None
    assert all(
        row["end_to_end_success"] is None
        for row in measured["session_rows"]
        if row["status"] in {"unknown", "not_started"}
    )
    packages = find_analysis_record(tmp_path / "execution", "task_panel_session_packages")
    assert len(packages["rows"]) == 16 and packages["complete_session_packages"] == 1
    assert all(
        not row["complete"] and row["expected_units"] is None
        for row in packages["rows"]
        if row["qualification_status"] != "success"
    )


def test_actual_committed_eight_task_sixteen_session_roundtrip(tmp_path, monkeypatch):
    """Run after committing sources: no preparation, snapshot, panel or config substitute."""
    from trusted_synthesis.experiments.finance_qa_vnext_task_panel import runner

    preparation, prepared = prepare_population(tmp_path, monkeypatch, committed=True)
    assert prepared["implementation"].get("synthetic_uncommitted_test_only") is None
    assert len(prepared["implementation"]["source_commit"]) == 40
    sends = install_constructed_http(monkeypatch, prepared)
    result = runner.run(ROOT, preparation)
    measured = assert_registered_measurement(result)
    assert len(set(sends)) == 16 and len(sends) <= 512
    assert measured["success_numerator"] == 16 and measured["complete_repr_packages"] == 16
    assert measured["complete_decidable_population"] is True
    assert measured["selected_tasks_with_success_witness"] == 8
