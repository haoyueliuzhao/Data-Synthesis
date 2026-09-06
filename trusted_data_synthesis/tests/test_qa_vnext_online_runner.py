"""Synthetic twelve-session orchestration; no actual Provider or model evidence.

Only the HttpxSender I/O boundary is replaced. A test-only prepared object bypasses
the committed-source preparation gate, and _credential supplies a local dummy
without opening .env. Successful population tests use the real tokenizer-only
representation path. Failure-scheduling tests explicitly stub that already
tested representation consumer, never qualification or HTTP-to-Runtime links.
"""

from __future__ import annotations

import copy
import socket
from pathlib import Path
from typing import Any

import pytest

from trusted_synthesis.canonical_json import canonical_json_bytes
from trusted_synthesis.domains.finance.qa_vnext.callbacks import PublicFixtureCallback
from trusted_synthesis.domains.finance.qa_vnext.program_adapter import ProgramTaskAdapter
from trusted_synthesis.domains.finance.qa_vnext.protocol import ProtocolError
from trusted_synthesis.domains.finance.qa_vnext.share_adapter import ShareTaskAdapter
from trusted_synthesis.experiments.finance_qa_vnext_model_execution import runner
from trusted_synthesis.experiments.finance_qa_vnext_model_execution.models import (
    identity,
    read_json,
    record,
)
from trusted_synthesis.experiments.finance_qa_vnext_model_execution.plan import (
    freeze_condition,
    verify_directory,
)
from trusted_synthesis.experiments.finance_qa_vnext_model_execution.transport import (
    HTTPResponse,
    HttpxSender,
    TransportConfig,
)

ROOT = Path(__file__).resolve().parents[2]
REAL_CREDENTIAL = runner._credential


def _forbidden(*args: Any, **kwargs: Any) -> Any:
    pytest.fail("synthetic runner tests must not perform this external or execution action")


def _fixture(
    patch: pytest.MonkeyPatch,
    directory: Path,
    *,
    behavior: str = "success",
    tokenizer_binding: dict[str, Any] | None = None,
) -> dict[str, Any]:
    patch.setattr(socket, "create_connection", _forbidden)
    patch.setattr(socket.socket, "connect", _forbidden)
    config = TransportConfig()
    implementation = record("implementation", synthetic_unit_test=True)
    condition, registrations, panel = freeze_condition(
        ROOT, config.as_record(), implementation, run_tag="synthetic-" + directory.name
    )
    preparation = directory / "preparation"
    execution = directory / "execution"
    prepared = {
        "panel": panel,
        "config": config,
        "configuration": config.as_record(),
        "registrations": registrations,
        "condition": condition,
        "implementation": implementation,
        "coverage": panel.coverage,
        "tokenizer_binding": tokenizer_binding,
        "report": record(
            "preparation", execution_directory=str(execution), synthetic_unit_test=True
        ),
        "manifest": record("preparation_manifest", synthetic_unit_test=True),
    }
    prepared_reads, credential_accesses, sends = [], [], []
    by_id = {row["session_id"]: row for row in registrations}

    def prepared_reader(root: Path, path: Path) -> dict[str, Any]:
        assert root == ROOT and path == preparation
        prepared_reads.append(path)
        return prepared

    def source_verification(root: Path, snapshot: dict[str, Any]) -> None:
        assert root == ROOT and snapshot == implementation

    def local_credential(path: Path) -> str:
        assert path == ROOT / ".env"
        credential_accesses.append(path)
        return "synthetic-runner-dummy-not-a-credential"

    def synthetic_send(
        sender: HttpxSender, request: dict[str, Any], *, api_key: str | None
    ) -> HTTPResponse:
        assert api_key == "synthetic-runner-dummy-not-a-credential"
        registration = by_id[request["session_id"]]
        body = read_json(request["body_json"].encode("utf-8"))
        public = read_json(body["messages"][1]["content"].encode("utf-8"))
        sends.append(
            {
                "label": registration["label"],
                "round": registration["round"],
                "attempt_index": request["attempt_index"],
                "state_id": public["state"]["id"],
            }
        )
        content = PublicFixtureCallback().generate(public).decode("utf-8")
        if behavior == "known_failure" and registration["label"] == "C01":
            content = ""
        return HTTPResponse(
            200,
            canonical_json_bytes(
                {
                    "id": "synthetic-"
                    + registration["label"]
                    + "-"
                    + str(request["attempt_index"]),
                    "object": "chat.completion",
                    "model": "deepseek-v4-pro-0813",
                    "choices": [
                        {
                            "index": 0,
                            "finish_reason": "stop",
                            "message": {"role": "assistant", "content": content},
                        }
                    ],
                }
            ),
            headers=(("x-synthetic-runner-test", "true"),),
        )

    patch.setattr(runner, "_prepared", prepared_reader)
    patch.setattr(runner, "verify_source_snapshot", source_verification)
    patch.setattr(runner, "_credential", local_credential)
    patch.setattr(HttpxSender, "send", synthetic_send)
    if tokenizer_binding is None:

        def representation_stub(rows: list[dict[str, Any]], binding: Any) -> dict[str, Any]:
            assert binding is None
            return record(
                "token_representation_dataset",
                synthetic_failure_scheduling_test_only=True,
                candidate_ids=[row["id"] for row in rows],
                records=[],
                fit_count=0,
                not_fit_count=len(rows),
                positive_representation_validated=False,
            )

        patch.setattr(runner, "tokenize_candidates", representation_stub)
    if behavior == "unknown":
        original = runner.qualify_session

        def missing_response(*args: Any, **kwargs: Any) -> dict[str, Any]:
            registration, session, transport = args[1], args[2], Path(args[4])
            if registration["label"] == "C01" and session is not None:
                # Deliberately remove one generated test artifact before its first
                # independent audit; never modify production or user evidence.
                path = transport / "attempts/000_http_response.body"
                if path.exists():
                    path.unlink()
            return original(*args, **kwargs)

        patch.setattr(runner, "qualify_session", missing_response)
    return {
        "preparation": preparation,
        "execution": execution,
        "prepared": prepared,
        "prepared_reads": prepared_reads,
        "credential_accesses": credential_accesses,
        "sends": sends,
    }


@pytest.fixture(scope="module")
def successful_population(tmp_path_factory: pytest.TempPathFactory):
    directory = tmp_path_factory.mktemp("synthetic-twelve-population")
    with pytest.MonkeyPatch.context() as patch:
        binding = runner.register_tokenizer(ROOT)
        fixture = _fixture(patch, directory, tokenizer_binding=binding)
        fixture["report"] = runner.run(ROOT, fixture["preparation"])
        yield fixture


def test_twelve_synthetic_sessions_complete_real_runtime_qualification_export_and_tokenization(
    successful_population: dict[str, Any],
) -> None:
    result = successful_population
    report = result["report"]
    identity(report, "pilot_report")
    assert len(result["sends"]) == report["provider_attempt_count"] == 100
    assert report["candidate_count"] == report["token_fit_count"] == 100
    assert report["token_not_fit_count"] == 0
    assert report["reserved_token_allowance"] == 100 * 107520
    assert report["actual_response_models"] == ["deepseek-v4-pro-0813"]
    assert len(report["session_rows"]) == 12
    assert all(row["status"] == "success" and row["qualified"] for row in report["session_rows"])
    assert report["measurement"]["equal_task_weight_mean"] == 1.0
    assert report["measurement"]["registered_session_denominator"] == 12
    assert report["measurement"]["fixed_task_denominator"] == 3
    assert report["finite_comparison_count"] == 18
    assert report["workflow_evidence_complete"] and report["full_twelve_session_execution_complete"]
    assert (
        report["provider_calls_by_analysis"] == report["task_operation_executions_by_analysis"] == 0
    )
    assert report["student_parameter_loads"] == report["student_forward_calls"] == 0
    assert report["student_updates"] == report["gpu_jobs"] == 0
    for row in report["session_rows"]:
        expected = {"C": 3, "B": 17, "S": 5}[row["label"][0]]
        assert (
            row["provider_attempts"] == row["submissions"] == row["exported_candidates"] == expected
        )
    # This entire record lives only in pytest temporary data; its counts describe
    # the synthetic I/O exercise, not actual Provider usage or pilot observations.


def test_launches_follow_four_frozen_rounds_without_replacements(
    successful_population: dict[str, Any],
) -> None:
    result = successful_population
    schedule = read_json((result["execution"] / "schedule.json").read_bytes())
    assert schedule["registered_denominator"] == 12
    assert schedule["session_replacements"] == 0
    assert schedule["halt_reason"] is None
    assert [row["round"] for row in schedule["events"]] == [1, 1, 1, 2, 2, 2, 3, 3, 3, 4, 4, 4]
    assert [row["ordinal"] for row in schedule["events"]] == list(range(12))
    assert all(row["status"] == "started" for row in schedule["events"])
    assert [row["round"] for row in result["sends"]] == sorted(
        row["round"] for row in result["sends"]
    )
    assert len({row["session_id"] for row in result["prepared"]["registrations"]}) == 12


def test_share_route_witness_follows_actual_final_scale_ratio_and_denominator_claims(
    successful_population: dict[str, Any],
) -> None:
    result = successful_population
    rows = [row for row in result["report"]["session_rows"] if row["label"].startswith("S")]
    assert len(rows) == 4
    for row in rows:
        witness = row["share_support"]
        session = read_json(
            (result["execution"] / "sessions" / row["label"] / "runtime/session.json").read_bytes()
        )
        claims = {claim["id"]: claim for claim in session["claims"]}
        producers = {
            event["observation"]["id"]: event["observation"]["selected_action"]
            for event in session["events"]
            if event.get("observation") is not None
        }
        final = claims[session["final"]["answer"]["answer_claim_id"]]
        scale = producers[final["observation_id"]]
        ratio = claims[next(ref for ref in scale["inputs"] if ref["role"] == "ratio")["ref_id"]]
        ratio_action = producers[ratio["observation_id"]]
        denominator = next(ref for ref in ratio_action["inputs"] if ref["role"] == "denominator")
        assert scale["operation"] == "scale_percent" and ratio_action["operation"] == "share_ratio"
        assert witness["final_claim_id"] == final["id"]
        assert witness["ratio_claim_id"] == ratio["id"]
        assert witness["denominator"] == denominator
        assert denominator["kind"] == "evidence"
        assert witness["route"] == "disclosed_total"
        assert witness["final_dependency_chain_inspected"]
        assert witness["calling_relation_sum_alone_is_not_a_route_witness"]


def test_reanalysis_is_byte_equal_without_provider_callback_or_operation_execution(
    successful_population: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    result = successful_population
    monkeypatch.setattr(HttpxSender, "send", _forbidden)
    monkeypatch.setattr(PublicFixtureCallback, "generate", _forbidden)
    monkeypatch.setattr(ProgramTaskAdapter, "execute", _forbidden)
    monkeypatch.setattr(ShareTaskAdapter, "execute", _forbidden)
    reproduced = runner.analyze(
        ROOT, result["preparation"], result["execution"], tmp_path / "reanalysis"
    )
    assert canonical_json_bytes(reproduced) == canonical_json_bytes(result["report"])
    original_root, repeated_root = result["execution"] / "analysis", tmp_path / "reanalysis"
    original = {
        path.relative_to(original_root).as_posix(): path.read_bytes()
        for path in original_root.rglob("*")
        if path.is_file()
    }
    repeated = {
        path.relative_to(repeated_root).as_posix(): path.read_bytes()
        for path in repeated_root.rglob("*")
        if path.is_file()
    }
    assert repeated == original
    verify_directory(result["execution"], kind="execution_manifest")
    verify_directory(repeated_root, kind="analysis_manifest")


def test_existing_population_cannot_execute_again_or_read_credentials_again(
    successful_population: dict[str, Any],
) -> None:
    result = successful_population
    before = (len(result["sends"]), len(result["credential_accesses"]))
    with pytest.raises(ProtocolError, match="run.population_already_started"):
        runner.run(ROOT, result["preparation"])
    assert before == (len(result["sends"]), len(result["credential_accesses"]))


def test_known_observed_failure_continues_all_registered_future_rounds(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    result = _fixture(monkeypatch, tmp_path, behavior="known_failure")
    report = runner.run(ROOT, result["preparation"])
    statuses = {row["label"]: row["status"] for row in report["session_rows"]}
    assert statuses["C01"] == "known_failure"
    assert list(statuses.values()).count("success") == 11
    assert len(result["sends"]) == report["provider_attempt_count"] == 98
    assert report["candidate_count"] == 97
    assert report["measurement"]["equal_task_weight_mean"] == 11 / 12
    assert report["measurement"]["complete_decidable_population"]
    assert report["session_rows"][0]["submissions"] == 0
    assert report["session_rows"][0]["termination_reason"] == "provider.no_public_content"
    schedule = read_json((result["execution"] / "schedule.json").read_bytes())
    assert schedule["halt_reason"] is None
    assert all(row["status"] == "started" for row in schedule["events"])


def test_missing_evidence_is_unknown_and_halts_future_rounds_without_failure_imputation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    result = _fixture(monkeypatch, tmp_path, behavior="unknown")
    report = runner.run(ROOT, result["preparation"])
    statuses = [row["status"] for row in report["session_rows"]]
    assert statuses[:3] == ["unknown", "success", "success"]
    assert statuses[3:] == ["not_started"] * 9
    assert len(result["sends"]) == 25
    assert {row["round"] for row in result["sends"]} == {1}
    assert report["provider_attempt_count"] is None
    assert report["reserved_token_allowance"] is None
    assert report["candidate_count"] == 22
    assert report["measurement"]["equal_task_weight_mean"] is None
    assert not report["measurement"]["complete_decidable_population"]
    assert not report["workflow_evidence_complete"]
    assert not report["full_twelve_session_execution_complete"]
    assert all(
        row["complete_success_proportion"] is None for row in report["measurement"]["task_rows"]
    )
    schedule = read_json((result["execution"] / "schedule.json").read_bytes())
    assert schedule["halt_reason"] == "prior_round_integrity_or_internal_execution_failure"
    for row in report["session_rows"][3:]:
        qualification = read_json(
            (result["execution"] / "sessions" / row["label"] / "qualification.json").read_bytes()
        )
        assert qualification["qualified"] is None
        assert qualification["end_to_end_success"] is None
        assert qualification["qa_valid"] is None
        assert qualification["provider_attempt_count"] == 0
        assert qualification["runtime_submission_count"] == 0


@pytest.mark.parametrize("undecidable_status", ["unknown", "not_started"])
def test_summary_keeps_unknown_and_not_started_out_of_numeric_success_denominators(
    undecidable_status: str,
) -> None:
    qualifications = [
        {"task_group": group, "status": "success", "end_to_end_success": True}
        for group in ("C", "B", "S")
        for _ in range(4)
    ]
    original = copy.deepcopy(qualifications)
    qualifications[0].update(status=undecidable_status, end_to_end_success=None)
    summary = runner.summarize(qualifications, [])
    assert summary["registered_session_denominator"] == 12
    assert summary["task_rows"][0]["registered_denominator"] == 4
    assert summary["task_rows"][0]["complete_success_proportion"] is None
    assert summary["task_rows"][0]["success_numerator"] == 3
    assert summary["task_rows"][0][undecidable_status] == 1
    assert summary["equal_task_weight_mean"] is None
    assert runner.summarize(original, [])["equal_task_weight_mean"] == 1.0


@pytest.mark.parametrize(
    ("contents", "expected"),
    [
        ("DEEPSEEK_API_KEY=dummy-key\n", "dummy-key"),
        ("# comment\nIGNORED=value\nexport DEEPSEEK_API_KEY = 'dummy-key'\n", "dummy-key"),
        ('DEEPSEEK_API_KEY = "literal-${DUMMY}-$(ignored)"\n', "literal-${DUMMY}-$(ignored)"),
    ],
)
def test_credential_reader_accepts_only_literal_dummy_values_without_interpolation(
    tmp_path: Path, contents: str, expected: str
) -> None:
    path = tmp_path / "unit-test-dummy.env"
    path.write_text(contents, encoding="utf-8")
    assert REAL_CREDENTIAL(path) == expected


@pytest.mark.parametrize(
    "contents",
    [
        "",
        "OTHER_KEY=dummy\n",
        "DEEPSEEK_API_KEY=\n",
        "DEEPSEEK_API_KEY=''\n",
        "DEEPSEEK_API_KEY=dummy\nDEEPSEEK_API_KEY=second-dummy\n",
        "DEEPSEEK_API_KEY=dummy\x00value\n",
        "DEEPSEEK_API_KEY=dummy\x01value\n",
        "DEEPSEEK_API_KEY=dummy\tvalue\n",
        "DEEPSEEK_API_KEY='dummy\n",
        'DEEPSEEK_API_KEY="dummy\n',
        "DEEPSEEK_API_KEY=" + "x" * 2049 + "\n",
    ],
)
def test_credential_reader_rejects_missing_ambiguous_or_malformed_dummy_values(
    tmp_path: Path, contents: str
) -> None:
    path = tmp_path / "unit-test-dummy.env"
    path.write_text(contents, encoding="utf-8")
    with pytest.raises(ProtocolError, match="run.credential_unavailable"):
        REAL_CREDENTIAL(path)
