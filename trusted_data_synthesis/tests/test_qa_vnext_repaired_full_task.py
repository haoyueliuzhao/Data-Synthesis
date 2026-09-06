"""Six-session wiring, actual Runtime/qualification/export, synthetic HTTP only."""

from __future__ import annotations

import socket
import sys
from collections import Counter
from pathlib import Path

import pytest

from trusted_synthesis.canonical_json import canonical_json_bytes
from trusted_synthesis.domains.finance.qa_vnext.callbacks import PublicFixtureCallback
from trusted_synthesis.domains.finance.qa_vnext.program_adapter import ProgramTaskAdapter
from trusted_synthesis.domains.finance.qa_vnext.protocol import ProtocolError
from trusted_synthesis.domains.finance.qa_vnext.runtime import DurableStore, PublicQARuntime
from trusted_synthesis.domains.finance.qa_vnext.share_adapter import ShareTaskAdapter
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
from trusted_synthesis.experiments.finance_qa_vnext_repaired_full_task import plan, runner
from trusted_synthesis.experiments.finance_qa_vnext_repaired_full_task.__main__ import main
from trusted_synthesis.experiments.finance_qa_vnext_repaired_full_task.controls import run_controls

ROOT = Path(__file__).resolve().parents[2]
DESIGN = Path(
    "/home/zhuxinrui/.codex/attachments/7efb3ee2-a0c9-450d-930a-037d87cf8cad/pasted-text.txt"
)


def forbidden(*args, **kwargs):
    pytest.fail("this test cannot perform external calls, credentials, or replay Operations")


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(runner, "_credential", forbidden)


def population():
    implementation = record("implementation", synthetic_unit_test=True)
    condition, registrations, panel = plan.freeze_condition(
        ROOT, plan.configuration().as_record(), implementation, run_tag="synthetic-six"
    )
    return implementation, condition, registrations, panel


def test_exact_population_configuration_and_coverage():
    _, condition, rows, panel = population()
    assert len(rows) == len({r["session_id"] for r in rows}) == 6
    assert [r["label"] for r in rows] == ["C01", "B01", "S01", "C02", "B02", "S02"]
    assert Counter(r["task_group"] for r in rows) == {"C": 2, "B": 2, "S": 2}
    assert condition["maximum_provider_attempts"] == 192
    assert condition["maximum_reserved_token_allowance"] == 192 * 107520
    assert condition["maximum_same_task_comparison_pairs"] == 3
    config = plan.configuration()
    assert config.system_prompt == SYSTEM_PROMPT and config.attempts_per_session == 32
    assert config.maximum_pilot_attempts == 192
    assert Counter(r["population_status"] for r in panel.coverage) == {
        "selected_model_task": 3,
        "source_available_not_selected": 5,
        "source_unavailable": 3,
    }
    assert sum(r["registered_model_sessions"] for r in panel.coverage) == 6


@pytest.mark.parametrize(
    "config",
    [
        TransportConfig(),
        TransportConfig(attempts_per_session=1, maximum_pilot_attempts=192),
        TransportConfig(maximum_pilot_attempts=192, system_prompt="accept only"),
    ],
)
def test_reject_old_or_calibration_configuration(config):
    with pytest.raises(ProtocolError, match="six.fixed_configuration"):
        plan.freeze_condition(ROOT, config.as_record(), record("implementation"), run_tag="bad")


def test_later_branch_share_shapes_use_existing_admission_without_execution(tmp_path, monkeypatch):
    _, _, _, panel = population()
    monkeypatch.setattr(PublicQARuntime, "run", forbidden)
    monkeypatch.setattr(ProgramTaskAdapter, "execute", forbidden)
    monkeypatch.setattr(ShareTaskAdapter, "execute", forbidden)
    monkeypatch.setattr(HttpxSender, "send", forbidden)
    result = run_controls(panel, tmp_path / "controls", plan.configuration())
    assert result["passed"] and result["provider_attempts"] == result["action_executions"] == 0
    assert len(result["initial_rows"]) == 3
    assert result["later_shape_control_count"] == 26
    assert {r["operation"] for r in result["later_shape_rows"]} >= {
        "growth",
        "signed_percentage_point_gap",
        "absolute_percentage_point_gap",
        "scale_percent",
        "relation_sum",
        "share_ratio",
    }
    assert all(r["evaluation"]["update_admitted"] for r in result["later_shape_rows"])


def install_synthetic_http(monkeypatch, registrations, *, behavior="success"):
    sends = []
    by_id = {r["session_id"]: r for r in registrations}

    def synthetic_send(sender, request, *, api_key):
        assert api_key == "synthetic-dummy-not-a-credential"
        row = by_id[request["session_id"]]
        public = read_json(request["messages"][1]["content"].encode())
        assert request["messages"][0]["content"] == SYSTEM_PROMPT
        assert public["public_update_contract"]["version"] == "finance_qa_update_public_contract.v1"
        sends.append((row["label"], row["round"], public["state"]["submission_count"]))
        raw = PublicFixtureCallback().generate(public)
        if behavior == "known_failure" and row["label"] == "C01":
            raw = b""
        elif (
            behavior in {"correction", "reject"}
            and row["label"] == "C01"
            and public["state"]["submission_count"] == 1
        ):
            from trusted_synthesis.experiments.finance_qa_vnext_update_calibration.controls import (
                isolated_receiver,
            )

            value = isolated_receiver(public, "reject" if behavior == "reject" else "accept")
            if behavior == "correction":
                value["proposed_claim"] = None
            raw = canonical_json_bytes(value)
        return HTTPResponse(
            200,
            canonical_json_bytes(
                {
                    "id": "synthetic-six-not-provider",
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

    monkeypatch.setattr(HttpxSender, "send", synthetic_send)
    monkeypatch.setattr(runner, "_credential", lambda path: "synthetic-dummy-not-a-credential")
    if behavior == "unknown":
        actual = original_runner.qualify_session

        def missing(*args, **kwargs):
            registration, session, transport = args[1], args[2], Path(args[4])
            if registration["label"] == "C01" and session is not None:
                path = transport / "attempts/000_http_response.body"
                if path.exists():
                    path.unlink()  # Only our synthetic pytest artifact.
            return actual(*args, **kwargs)

        monkeypatch.setattr(original_runner, "qualify_session", missing)
        monkeypatch.setattr(runner, "qualify_session", missing)
    return sends


def synthetic_run(tmp_path, monkeypatch, *, behavior="success", actual_prepare=False):
    preparation = tmp_path / "preparation"
    if actual_prepare:
        monkeypatch.setattr(
            sys,
            "argv",
            [
                "six",
                "prepare",
                "--root",
                str(ROOT),
                "--preparation",
                str(preparation),
                "--design",
                str(DESIGN),
                "--run-tag",
                "actual-committed-six-local-http",
            ],
        )
        main()
        prepared = plan._prepared(ROOT, preparation)
    else:
        implementation, condition, registrations, panel = population()
        store = DurableStore(preparation)
        for row in registrations:
            store.json(
                f"initial/{row['label']}_request.json",
                plan.initial_request(panel.adapter(row["task_group"])),
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
                "repaired_preparation", execution_directory=str(tmp_path / "execution")
            ),
            "manifest": record("preparation_manifest", synthetic_unit_test=True),
        }
        monkeypatch.setattr(runner, "_prepared", lambda root, directory: prepared)
        monkeypatch.setattr(runner, "verify_source_snapshot", lambda root, value: None)
    sends = install_synthetic_http(monkeypatch, prepared["registrations"], behavior=behavior)
    report = runner.run(ROOT, preparation)
    return preparation, prepared, sends, report


@pytest.mark.parametrize(
    "behavior", ["success", "known_failure", "unknown", "correction", "reject"]
)
def test_six_real_entry_loop_and_readonly_measurements(tmp_path, monkeypatch, behavior):
    preparation, prepared, sends, report = synthetic_run(tmp_path, monkeypatch, behavior=behavior)
    assert report["measurement"]["registered_session_denominator"] == 6
    assert report["maximum_reserved_token_allowance"] == 20_643_840
    assert len(report["session_rows"]) == 6
    assert [r[1] for r in sends] == sorted(r[1] for r in sends)
    assert report["finite_comparison_count"] <= 3
    assert all(r["registered_denominator"] == 2 for r in report["measurement"]["task_rows"])
    if behavior == "unknown":
        assert [r["status"] for r in report["session_rows"]] == [
            "unknown",
            "success",
            "success",
            "not_started",
            "not_started",
            "not_started",
        ]
        assert report["measurement"]["equal_task_weight_mean"] is None
        assert report["session_rows"][0]["progress"]["evidence_measured"] is False
    elif behavior == "known_failure":
        assert report["measurement"]["equal_task_weight_mean"] == 5 / 6
        assert report["candidate_count"] == 47
    else:
        assert report["measurement"]["equal_task_weight_mean"] == 1
        assert report["finite_comparison_count"] == 3
        assert report["scientific_objects"]["all_three_selected_tasks_have_complete_witness"]
        for row in report["session_rows"]:
            assert row["request_presentation"]["all_full_task_publication"]
            assert (
                row["progress"]["first_accepted_claim"]
                and row["progress"]["first_claim_consumption"]
            )
        first = report["session_rows"][0]
        observations = first["progress"]["observations"]
        if behavior == "success":
            assert len(sends) == report["candidate_count"] == report["token_fit_count"] == 50
            assert first["progress"]["first_claim_consumption"]["kind"] == "final"
        elif behavior == "correction":
            assert first["qualified"] and first["projection_status"] == "undetermined"
            assert len(observations) == 1 and observations[0]["pending_model_submission_count"] == 2
            assert observations[0]["first_typed_update_admitted"] is False
            assert observations[0]["eventual_disposition"] == "accept"
        elif behavior == "reject":
            assert len(observations) == 2 and observations[0]["eventual_disposition"] == "reject"
            assert observations[0]["committed_claim_id"] is None
    with pytest.raises(ProtocolError, match="run.population_already_started"):
        runner.run(ROOT, preparation)
    monkeypatch.setattr(HttpxSender, "send", forbidden)
    monkeypatch.setattr(runner, "_credential", forbidden)
    monkeypatch.setattr(PublicQARuntime, "run", forbidden)
    monkeypatch.setattr(ProgramTaskAdapter, "execute", forbidden)
    monkeypatch.setattr(ShareTaskAdapter, "execute", forbidden)
    repeated = runner.analyze(ROOT, preparation, tmp_path / "execution", tmp_path / "reanalysis")
    assert canonical_json_bytes(repeated) == canonical_json_bytes(report)
    for path in (tmp_path / "execution/analysis").rglob("*"):
        if path.is_file():
            assert (
                path.read_bytes()
                == (
                    tmp_path / "reanalysis" / path.relative_to(tmp_path / "execution/analysis")
                ).read_bytes()
            )


def test_actual_committed_preparation_and_full_runner_roundtrip(tmp_path, monkeypatch):
    # Run explicitly after source commit. No preparation/source/panel/configuration mocks.
    if not DESIGN.exists():
        pytest.skip("the exact user-supplied experimental design is not locally available")
    preparation, prepared, sends, report = synthetic_run(tmp_path, monkeypatch, actual_prepare=True)
    assert len(prepared["registrations"]) == 6 and len(sends) == 50
    assert report["workflow_evidence_complete"] and report["candidate_count"] == 50
