"""Constructed audit-object controls, never evidence of actual Provider/model calls.

The local callback is explicitly synthetic.  Positive exporter tests supply a
constructed verified qualification to exercise that consumer's contract; the
independent online attribution auditor, not this fixture, owns real provenance.
All generated sessions and HTTP-shaped artifacts remain in pytest temp paths.
"""

from __future__ import annotations

import copy
import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from trusted_synthesis.canonical_json import canonical_json_bytes
from trusted_synthesis.domains.finance.qa_vnext import catalog as domain
from trusted_synthesis.domains.finance.qa_vnext.callbacks import PublicFixtureCallback
from trusted_synthesis.domains.finance.qa_vnext.measurement import audit_session
from trusted_synthesis.domains.finance.qa_vnext.program_adapter import ProgramTaskAdapter
from trusted_synthesis.domains.finance.qa_vnext.protocol import (
    ProtocolError,
)
from trusted_synthesis.domains.finance.qa_vnext.protocol import (
    record as public_record,
)
from trusted_synthesis.domains.finance.qa_vnext.runner import build_catalog
from trusted_synthesis.domains.finance.qa_vnext.runtime import PublicQARuntime
from trusted_synthesis.domains.finance.qa_vnext.share_adapter import SHARE_FAMILY, ShareTaskAdapter
from trusted_synthesis.experiments.finance_qa_vnext_model_execution import representation as export
from trusted_synthesis.experiments.finance_qa_vnext_model_execution.models import (
    identity,
    record,
    sha,
)
from trusted_synthesis.experiments.qa_reasoning_share_public_protocol.models import PARENT

ROOT = Path(__file__).resolve().parents[2]


def reseal(
    value: dict[str, Any], kind: str, *, public: bool = False, **changes: Any
) -> dict[str, Any]:
    body = {key: item for key, item in value.items() if key not in {"id", "schema_version"}}
    return (public_record if public else record)(kind, **{**body, **changes})


def write_json(path: Path, value: Any) -> bytes:
    data = canonical_json_bytes(value)
    path.write_bytes(data)
    return data


class SyntheticHTTPCallback:
    """HTTP-shaped files are unit-test data, not verified live model exchanges."""

    def __init__(self, directory: Path, *, reject_first: bool = False, long_first: bool = False):
        directory.mkdir()
        self.directory = directory
        self.reject_first = reject_first
        self.long_first = long_first
        self.fixture = PublicFixtureCallback()
        self.binding = public_record(
            "callback_binding",
            origin="constructed_unit_test_only",
            model_sample=False,
            synthetic_http=True,
            actual_provider_calls=0,
        )
        self.turns: list[dict[str, Any]] = []
        self.configuration = record("model_configuration", test_only=True, model="unit-test-model")
        write_json(directory / "model_configuration.json", self.configuration)

    def generate(self, request: dict[str, Any]) -> bytes:
        index = len(self.turns)
        prefix = f"{index:03d}_"
        raw = (
            b' {"kind": "action"} \n'
            if index == 0 and self.reject_first
            else self.fixture.generate(request)
        )
        if not (index == 0 and self.reject_first):
            # Formatting and exact number strings are intentionally not canonicalized.
            raw = json.dumps(json.loads(raw), ensure_ascii=False, indent=3).encode() + b"\n"
        if index == 0 and self.long_first:
            raw += b" \n" * 60_000
        request_raw = canonical_json_bytes(request)
        messages = [
            {
                "role": "system",
                "content": "Synthetic unit-test callback. No actual model is invoked.",
            },
            {"role": "user", "content": request_raw.decode()},
        ]
        body = {"model": "unit-test-model", "messages": messages, "stream": False}
        body_raw = canonical_json_bytes(body)
        response = {
            "id": f"unit-test-response-{index}",
            "model": "unit-test-model",
            "choices": [
                {
                    "index": 0,
                    "finish_reason": "stop",
                    "message": {"role": "assistant", "content": raw.decode()},
                }
            ],
        }
        response_raw = canonical_json_bytes(response)
        attempt = record(
            "attempt", turn_index=index, public_request_id=request["id"], test_only=True
        )
        request_record = record(
            "http_request", attempt_id=attempt["id"], body_sha256=sha(body_raw), test_only=True
        )
        response_record = record(
            "http_response",
            request_id=request_record["id"],
            body_sha256=sha(response_raw),
            test_only=True,
        )
        outcome = record(
            "attempt_outcome",
            attempt_id=attempt["id"],
            response_id=response_record["id"],
            test_only=True,
        )
        for suffix, value in (
            ("attempt.json", attempt),
            ("request.json", request_record),
            ("response.json", response_record),
            ("outcome.json", outcome),
        ):
            write_json(self.directory / (prefix + suffix), value)
        files = {
            "public_request": (prefix + "public_request.json", request_raw),
            "request": (prefix + "http_request.body", body_raw),
            "response": (prefix + "http_response.body", response_raw),
            "raw_public_content": (prefix + "public_content.txt", raw),
        }
        turn = {
            "turn_index": index,
            "public_request_id": request["id"],
            "public_runtime_state_id": request["state"]["id"],
            "provider_attempt_id": attempt["id"],
            "request_id": request_record["id"],
            "response_id": response_record["id"],
            "provider_response_id": response["id"],
            "model_origin_evidence_id": outcome["id"],
        }
        for kind, (name, data) in files.items():
            (self.directory / name).write_bytes(data)
            turn[kind + "_path"] = name
            turn[kind + "_sha256"] = sha(data)
        self.turns.append(turn)
        return raw


def make_control(
    base: Path, path: str = "share", *, reject_first: bool = False, long_first: bool = False
) -> dict[str, Any]:
    base.mkdir(parents=True)
    catalog = build_catalog(ROOT)
    if path == "share":
        adapter = ShareTaskAdapter(ROOT, catalog.registry, catalog.resolve(SHARE_FAMILY).receipt)
    else:
        task_type = (
            "derived_growth_absolute_spread"
            if path == "branch"
            else "registered_cross_metric_comparison"
        )
        cases, _ = catalog.frozen_source_cases(ROOT, task_types=(task_type,))
        adapter = ProgramTaskAdapter(cases[0], catalog.registry)
    callback = SyntheticHTTPCallback(
        base / "transport", reject_first=reject_first, long_first=long_first
    )
    runtime = PublicQARuntime(adapter, callback, base / "runtime")
    session = runtime.run()
    audit = audit_session(adapter, session, base / "runtime")
    assert audit["qualified"] is True, audit["errors"]
    turns = []
    for turn, event in zip(callback.turns, session["events"], strict=True):
        turns.append(
            {
                **turn,
                "submission_id": event["submission"]["id"],
                "receipt_id": event["receipt"]["id"],
                "admitted": event["receipt"]["admitted"],
            }
        )
    ledger = record("transport_ledger", test_only=True, attempts=len(turns))
    write_json(callback.directory / "ledger.json", ledger)
    manifest = record(
        "transport_manifest",
        self_excluding=True,
        test_only=True,
        members=[
            {"path": item.name, "bytes": len(item.read_bytes()), "sha256": sha(item.read_bytes())}
            for item in sorted(callback.directory.iterdir())
        ],
    )
    manifest_raw = write_json(callback.directory / "manifest.json", manifest)
    qualification = record(
        "qualification",
        constructed_verified_objects_for_consumer_test_only=True,
        actual_provider_calls=0,
        registration_id="test-only-registration:source-control",
        registered_session_id="test-only-registered-session:" + path,
        session_id=session["id"],
        task_id=adapter.context["task_id"],
        context_id=session["context_id"],
        protocol_id=session["protocol_id"],
        status="success",
        evidence_complete=True,
        model_origin_verified=True,
        qa_valid=True,
        trajectory_valid=True,
        qualified=True,
        end_to_end_success=True,
        export_eligible=True,
        projection_status="supported" if audit["projection_supported"] else "undetermined",
        domain_audit=audit,
        verified_turns=turns,
        transport_manifest_id=manifest["id"],
        transport_manifest_sha256=sha(manifest_raw),
        transport_ledger_id=ledger["id"],
        transport_binding_id=callback.binding["id"],
        model_configuration_id=callback.configuration["id"],
    )
    return {
        "session": session,
        "qualification": qualification,
        "directory": callback.directory,
        "adapter": adapter,
    }


@pytest.fixture(scope="module", autouse=True)
def original_sources_and_tokenizer_unchanged() -> Iterator[None]:
    paths = [ROOT / domain.ARCHIVE_PATH, ROOT / export.frozen_tokenizer_assets.SOURCE_CONFIGURATION]
    paths.extend(
        export.frozen_tokenizer_assets.MODEL_DIRECTORY / name
        for name, _, _ in export.frozen_tokenizer_assets.TOKENIZER_MEMBERS
    )
    for directory in (domain.FROZEN_SOURCE_DIRECTORY, PARENT):
        paths.extend(path for path in (ROOT / directory).rglob("*") if path.is_file())
    before = {path: sha(path.read_bytes()) for path in paths}
    yield
    assert {path: sha(path.read_bytes()) for path in paths} == before


@pytest.fixture(scope="module")
def controls(tmp_path_factory: pytest.TempPathFactory) -> dict[str, dict[str, Any]]:
    base = tmp_path_factory.mktemp("representation_controls")
    return {
        "share": make_control(base / "share"),
        "corrected": make_control(base / "corrected", reject_first=True),
    }


def exported(control: dict[str, Any]) -> dict[str, Any]:
    return export.export_candidates(
        control["session"], control["qualification"], control["directory"]
    )


@pytest.fixture(scope="module")
def tokenizer_binding() -> dict[str, Any]:
    return export.register_tokenizer(ROOT)


def test_original_http_messages_and_noncanonical_targets_survive_export_exactly(
    controls: dict[str, Any],
) -> None:
    control = controls["share"]
    before = canonical_json_bytes({name: control[name] for name in ("session", "qualification")})
    result = exported(control)
    assert result["candidate_count"] == 5
    assert [row["submission_kind"] for row in result["rows"]] == [
        "action",
        "update",
        "action",
        "update",
        "final",
    ]
    for row, turn, event in zip(
        result["rows"],
        control["qualification"]["verified_turns"],
        control["session"]["events"],
        strict=True,
    ):
        identity(row, "supervision_candidate")
        body = json.loads((control["directory"] / turn["request_path"]).read_bytes())
        content = (control["directory"] / turn["raw_public_content_path"]).read_bytes()
        assert row["messages"] == body["messages"]
        assert row["target_text"].encode() == content
        assert content != canonical_json_bytes(event["parsed"])
        assert row["target_raw_sha256"] == sha(content)
        assert row["target_raw_byte_count"] == len(content)
        assert row["public_runtime_state_id"] == event["request"]["state"]["id"]
        assert row["request_id"] == turn["request_id"] != row["public_request_id"]
        assert row["response_id"] == turn["response_id"]
        assert row["submission_id"] == event["submission"]["id"]
        assert row["receipt_id"] == event["receipt"]["id"]
        assert row["qualification_id"] == control["qualification"]["id"]
        assert row["quotient_assignment_id"] is None
        assert row["class_weights_assigned"] is False
        assert "state_id" not in row and "weight" not in row
    assert (
        canonical_json_bytes({name: control[name] for name in ("session", "qualification")})
        == before
    )


def test_corrected_qualified_session_exports_admitted_targets_with_real_feedback_and_no_assignment(
    controls: dict[str, Any],
) -> None:
    control = controls["corrected"]
    result = exported(control)
    assert result["candidate_count"] == 5 and result["excluded_submission_count"] == 1
    assert [row["turn_index"] for row in result["rows"]] == [1, 2, 3, 4, 5]
    assert all(row["projection_status"] == "undetermined" for row in result["rows"])
    assert all(row["quotient_assignment_id"] is None for row in result["rows"])
    request = json.loads(result["rows"][0]["messages"][-1]["content"])
    assert request["state"]["last_feedback"] == {"code": "submission.schema", "admitted": False}
    assert request["state"]["submission_count"] == 1
    assert (
        result["excluded_submissions"][0]["submission_id"]
        == control["session"]["events"][0]["submission"]["id"]
    )
    assert result["excluded_submissions"][0]["original_transport_bytes_retained"] is True


@pytest.mark.parametrize("path,count", [("branch", 17), ("comparison", 3)])
def test_new_program_paths_have_their_own_row_counts_not_the_old_27_rows(
    tmp_path: Path, path: str, count: int
) -> None:
    control = make_control(tmp_path / path, path)
    result = exported(control)
    assert result["candidate_count"] == count
    assert {row["task_id"] for row in result["rows"]} == {control["qualification"]["task_id"]}
    assert all(row["session_id"] == control["session"]["id"] for row in result["rows"])
    assert result["legacy_27_rows_imported"] is False
    assert result["old_P_Q_probabilities_inherited"] is False


@pytest.mark.parametrize(
    "status,qualified,model_verified,evidence",
    [
        ("known_failure", False, True, True),
        ("unknown", None, False, False),
        ("success", True, False, True),
    ],
)
def test_unqualified_or_unverified_sessions_export_zero_without_reading_http_or_tokenizer(
    controls: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
    status: str,
    qualified: bool | None,
    model_verified: bool,
    evidence: bool,
) -> None:
    control = controls["share"]
    qualification = reseal(
        control["qualification"],
        "qualification",
        status=status,
        qualified=qualified,
        model_origin_verified=model_verified,
        evidence_complete=evidence,
        export_eligible=False,
    )

    def forbidden(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("ineligible session reached positive-data consumer")

    monkeypatch.setattr(export, "_bound_bytes", forbidden)
    monkeypatch.setattr(export.frozen_tokenizer_assets, "load_tokenizer", forbidden)
    result = export.export_candidates(control["session"], qualification, Path("/path/not/read"))
    assert result["rows"] == [] and result["candidate_count"] == 0
    assert result["session_exclusion_reasons"]
    tokens = export.tokenize_candidates(result["rows"])
    assert tokens["records"] == [] and tokens["status"] == "no_positive_candidates"
    assert tokens["positive_representation_validated"] is False
    assert tokens["tokenizer_loaded"] is False


def test_not_started_session_creates_neither_placeholder_nor_positive_token_check(
    controls: dict[str, Any],
) -> None:
    qualification = reseal(
        controls["share"]["qualification"],
        "qualification",
        session_id=None,
        status="not_started",
        qualified=None,
        model_origin_verified=False,
        export_eligible=False,
        domain_audit=None,
        verified_turns=[],
    )
    result = export.export_candidates(None, qualification, Path("/not/read"))
    assert result["rows"] == [] and result["session_id"] is None
    assert export.tokenize_candidates(result["rows"])["positive_representation_validated"] is False


def test_callback_model_label_alone_is_never_export_authority_and_fixture_is_excluded(
    controls: dict[str, Any],
) -> None:
    control = controls["share"]
    for origin in ("model", "fixture"):
        binding = reseal(
            control["session"]["callback_binding"], "callback_binding", public=True, origin=origin
        )
        session = reseal(control["session"], "session", public=True, callback_binding=binding)
        qualification = reseal(
            control["qualification"],
            "qualification",
            session_id=session["id"],
            model_origin_verified=origin == "fixture",
            export_eligible=origin == "fixture",
        )
        result = export.export_candidates(session, qualification, Path("/not/read"))
        assert result["rows"] == []
        expected = (
            "fixture_session" if origin == "fixture" else "model_origin_not_independently_verified"
        )
        assert expected in result["session_exclusion_reasons"]


def test_old_public_protocol_cannot_enter_new_candidates(controls: dict[str, Any]) -> None:
    control = controls["share"]
    session = reseal(
        control["session"], "session", public=True, protocol_id="old_share_public_protocol:legacy"
    )
    qualification = reseal(
        control["qualification"],
        "qualification",
        session_id=session["id"],
        protocol_id=session["protocol_id"],
    )
    with pytest.raises(ProtocolError, match="representation.new_public_protocol"):
        export.export_candidates(session, qualification, control["directory"])


@pytest.mark.parametrize("field", export.TURN_IDS)
def test_missing_verified_turn_identity_is_rejected_not_filled(
    controls: dict[str, Any], field: str
) -> None:
    control = controls["share"]
    turns = copy.deepcopy(control["qualification"]["verified_turns"])
    del turns[0][field]
    qualification = reseal(control["qualification"], "qualification", verified_turns=turns)
    with pytest.raises(ProtocolError, match="representation.complete_turn_ids"):
        export.export_candidates(control["session"], qualification, control["directory"])


@pytest.mark.parametrize("mutation", ["missing", "duplicate", "future_index"])
def test_turn_map_must_cover_every_actual_event_once_including_unadmitted(
    controls: dict[str, Any], mutation: str
) -> None:
    control = controls["corrected"]
    turns = copy.deepcopy(control["qualification"]["verified_turns"])
    if mutation == "missing":
        turns.pop(0)
    elif mutation == "duplicate":
        turns[-1] = turns[0]
    else:
        turns[-1]["turn_index"] = 99
    qualification = reseal(control["qualification"], "qualification", verified_turns=turns)
    with pytest.raises(ProtocolError, match="representation.exhaustive_turn_binding"):
        export.export_candidates(control["session"], qualification, control["directory"])


@pytest.mark.parametrize(
    "field",
    ["public_request_id", "public_runtime_state_id", "submission_id", "receipt_id", "admitted"],
)
def test_future_state_or_other_receipt_parent_is_rejected(
    controls: dict[str, Any], field: str
) -> None:
    control = controls["share"]
    turns = copy.deepcopy(control["qualification"]["verified_turns"])
    turns[0][field] = False if field == "admitted" else "future-or-other-parent"
    qualification = reseal(control["qualification"], "qualification", verified_turns=turns)
    with pytest.raises(ProtocolError, match="representation.turn_parent_binding"):
        export.export_candidates(control["session"], qualification, control["directory"])


@pytest.mark.parametrize(
    "field",
    ["request_sha256", "response_sha256", "public_request_sha256", "raw_public_content_sha256"],
)
def test_qualified_metadata_cannot_bypass_exact_transport_bytes(
    controls: dict[str, Any], field: str
) -> None:
    control = controls["share"]
    turns = copy.deepcopy(control["qualification"]["verified_turns"])
    turns[0][field] = "0" * 64
    qualification = reseal(control["qualification"], "qualification", verified_turns=turns)
    with pytest.raises(ProtocolError, match="representation.bound_bytes"):
        export.export_candidates(control["session"], qualification, control["directory"])


@pytest.mark.parametrize("path", ["../outside.body", "/tmp/outside.body"])
def test_transport_binding_cannot_escape_qualified_directory(
    controls: dict[str, Any], path: str
) -> None:
    control = controls["share"]
    turns = copy.deepcopy(control["qualification"]["verified_turns"])
    turns[0]["request_path"] = path
    qualification = reseal(control["qualification"], "qualification", verified_turns=turns)
    with pytest.raises(ProtocolError, match="representation.relative_path"):
        export.export_candidates(control["session"], qualification, control["directory"])


@pytest.mark.parametrize(
    "mutation", ["future_user", "history_append", "normalized_response", "manifest"]
)
def test_modified_http_conditions_or_normalized_response_are_not_silently_used(
    tmp_path: Path, mutation: str
) -> None:
    control = make_control(tmp_path / "control")
    turns = copy.deepcopy(control["qualification"]["verified_turns"])
    turn = turns[0]
    if mutation in {"future_user", "history_append"}:
        path = control["directory"] / turn["request_path"]
        body = json.loads(path.read_bytes())
        if mutation == "future_user":
            body["messages"][-1]["content"] = canonical_json_bytes(
                control["session"]["events"][-1]["request"]
            ).decode()
            error = "representation.actual_request_not_future_state"
        else:
            body["messages"].append({"role": "assistant", "content": "future answer"})
            error = "representation.original_messages"
        turn["request_sha256"] = sha(write_json(path, body))
    elif mutation == "normalized_response":
        path = control["directory"] / turn["response_path"]
        body = json.loads(path.read_bytes())
        body["choices"][0]["message"]["content"] = canonical_json_bytes(
            control["session"]["events"][0]["parsed"]
        ).decode()
        turn["response_sha256"] = sha(write_json(path, body))
        error = "representation.exact_original_target"
    else:
        path = control["directory"] / "manifest.json"
        path.write_bytes(path.read_bytes() + b"\n")
        error = "representation.qualified_transport_manifest"
    qualification = reseal(control["qualification"], "qualification", verified_turns=turns)
    with pytest.raises(ProtocolError, match=error):
        export.export_candidates(control["session"], qualification, control["directory"])


@pytest.mark.parametrize(
    "field", ["qualified", "qa_valid", "trajectory_valid", "evidence_complete"]
)
def test_independent_domain_audit_cannot_be_replaced_by_online_success_flags(
    controls: dict[str, Any], field: str
) -> None:
    control = controls["share"]
    audit = reseal(
        control["qualification"]["domain_audit"], "session_audit", public=True, **{field: False}
    )
    qualification = reseal(control["qualification"], "qualification", domain_audit=audit)
    with pytest.raises(ProtocolError, match="representation.qualified_domain_audit"):
        export.export_candidates(control["session"], qualification, control["directory"])


def test_qualification_identity_and_projection_status_are_not_mutable_flags(
    controls: dict[str, Any],
) -> None:
    control = controls["corrected"]
    qualification = copy.deepcopy(control["qualification"])
    qualification["projection_status"] = "supported"
    with pytest.raises(ProtocolError, match="online.identity.qualification"):
        export.export_candidates(control["session"], qualification, control["directory"])
    qualification = reseal(qualification, "qualification")
    with pytest.raises(ProtocolError, match="representation.projection_status"):
        export.export_candidates(control["session"], qualification, control["directory"])


def test_new_rows_use_frozen_five_file_tokenizer_and_only_original_content_mask(
    controls: dict[str, Any], tokenizer_binding: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    rows = exported(controls["corrected"])["rows"]
    snapshot = canonical_json_bytes(rows)

    def forbidden(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("old row eligibility/tokenization was reused")

    monkeypatch.setattr(export.frozen_tokenizer_assets, "_validate_row", forbidden)
    monkeypatch.setattr(export.frozen_tokenizer_assets, "_tokenize_row", forbidden)
    result = export.tokenize_candidates(rows, tokenizer_binding)
    tokenizer = export.frozen_tokenizer_assets.load_tokenizer(tokenizer_binding)
    assert tokenizer_binding["member_count"] == 5
    assert tokenizer_binding["maximum_sequence_length"] == 24_576
    assert tokenizer_binding["language_model_loaded"] is False
    assert result["candidate_count"] == result["fit_count"] == 5
    assert result["not_fit_count"] == 0
    for row, tokens in zip(rows, result["records"], strict=True):
        start, end = tokens["target_token_start"], tokens["target_token_end"]
        ids, mask, labels = tokens["input_ids"], tokens["target_mask"], tokens["labels"]
        assert tokens["tokenrepresentation_status"] == "fit"
        assert tokens["qualification_id"] == row["qualification_id"]
        assert tokens["public_runtime_state_id"] == row["public_runtime_state_id"]
        assert (
            tokenizer.decode(
                ids[start:end], skip_special_tokens=False, clean_up_tokenization_spaces=False
            )
            == row["target_text"]
        )
        assert mask == [int(start <= index < end) for index in range(len(ids))]
        assert labels == [token if mask[index] else -100 for index, token in enumerate(ids)]
        assert tokens["attention_mask"] == [1] * len(ids)
        assert ids[end:] == [151645, 198] and labels[end:] == [-100, -100]
        assert tokens["causal_shift"] == 1 and tokens["causal_target_token_start"] == start - 1
        assert tokens["causal_target_token_end"] == end - 1
        assert sum(mask[1:]) == tokens["target_token_count"]
        assert all(tokens["boundary_checks"].values())
        assert (
            tokens["quotient_assignment_id"] is None and tokens["class_weights_assigned"] is False
        )
    assert canonical_json_bytes(rows) == snapshot
    assert result["old_eligibility_or_rows_reused"] is False
    assert (
        result["student_parameter_loads"]
        == result["student_forward_calls"]
        == result["student_parameter_updates"]
        == result["GPU_jobs"]
        == 0
    )


def test_long_original_target_overflow_retains_qualified_raw_row_without_truncation(
    tmp_path: Path, tokenizer_binding: dict[str, Any]
) -> None:
    control = make_control(tmp_path / "long_target", long_first=True)
    candidate_set = exported(control)
    rows = candidate_set["rows"]
    before = canonical_json_bytes(rows)
    assert control["qualification"]["qualified"] is True and len(rows) == 5
    assert rows[0]["target_text"].endswith(" \n" * 60_000)
    result = export.tokenize_candidates(rows, tokenizer_binding)
    first = result["records"][0]
    assert first["sequence_length"] > 24_576
    assert first["target_token_count"] > 24_576
    assert first["tokenrepresentation_status"] == "not_fit"
    assert first["reason"] == "maximum_sequence_length_exceeded"
    assert first["consumable_token_representation"] is False
    assert first["input_ids"] is first["labels"] is first["target_mask"] is None
    assert first["target_raw_sha256"] == rows[0]["target_raw_sha256"]
    assert first["qualification_id"] == rows[0]["qualification_id"]
    assert first["raw_candidate_and_qualification_retained"] is True and first["truncated"] is False
    assert result["candidate_count"] == 5 and result["not_fit_count"] >= 1
    assert canonical_json_bytes(rows) == before
    assert control["qualification"]["qualified"] is True


def test_tokenization_is_deterministic_and_never_assigns_legacy_weights(
    controls: dict[str, Any], tokenizer_binding: dict[str, Any]
) -> None:
    rows = exported(controls["share"])["rows"][:1]
    left = export.tokenize_candidates(rows, tokenizer_binding)
    right = export.tokenize_candidates(rows, tokenizer_binding)
    assert canonical_json_bytes(left) == canonical_json_bytes(right)
    assert left["class_weights_assigned"] is False


@pytest.mark.parametrize(
    "mutation",
    ["old_protocol", "old_schema", "assignment", "class_weight", "target_bytes", "duplicate"],
)
def test_token_consumer_rejects_old_or_rewritten_candidates_before_loading(
    controls: dict[str, Any], monkeypatch: pytest.MonkeyPatch, mutation: str
) -> None:
    row = copy.deepcopy(exported(controls["share"])["rows"][0])
    if mutation == "old_schema":
        row["schema_version"] = "old_share_27_row_export.v1"
    elif mutation == "old_protocol":
        row = reseal(row, "supervision_candidate", protocol_id="old-public-protocol")
    elif mutation == "assignment":
        row = reseal(row, "supervision_candidate", quotient_assignment_id="old-assignment")
    elif mutation == "class_weight":
        row = reseal(row, "supervision_candidate", class_weights_assigned=True)
    elif mutation == "target_bytes":
        row = reseal(row, "supervision_candidate", target_text=row["target_text"] + " ")
    rows = [row, row] if mutation == "duplicate" else [row]

    def forbidden(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("invalid candidate reached tokenizer loading")

    monkeypatch.setattr(export.frozen_tokenizer_assets, "load_tokenizer", forbidden)
    with pytest.raises(ProtocolError):
        export.tokenize_candidates(rows, {})


def test_sequence_limit_cannot_be_silently_raised(
    controls: dict[str, Any], tokenizer_binding: dict[str, Any]
) -> None:
    rows = exported(controls["share"])["rows"][:1]
    modified = {**tokenizer_binding, "maximum_sequence_length": 131_072}
    with pytest.raises(ProtocolError, match="representation.fixed_sequence_cap"):
        export.tokenize_candidates(rows, modified)


@pytest.mark.parametrize("failure", ["render", "prefix", "boundary", "decode", "padding", "suffix"])
def test_new_row_boundary_failures_are_not_reported_as_fitted(
    controls: dict[str, Any],
    tokenizer_binding: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
    failure: str,
) -> None:
    row = exported(controls["share"])["rows"][0]
    real = export.frozen_tokenizer_assets.load_tokenizer(tokenizer_binding)

    class BrokenTokenizer:
        all_special_ids = real.all_special_ids
        chat_template = real.chat_template

        def apply_chat_template(self, messages: Any, **kwargs: Any) -> str:
            value = real.apply_chat_template(messages, **kwargs)
            return (
                value + "changed"
                if failure == "render" and not kwargs["add_generation_prompt"]
                else value
            )

        def __call__(self, text: str, **kwargs: Any) -> dict[str, Any]:
            value = real(text, **kwargs)
            if kwargs.get("return_offsets_mapping"):
                if failure == "prefix":
                    value["input_ids"][0] += 1
                elif failure == "boundary":
                    start = len(
                        real.apply_chat_template(
                            row["messages"], tokenize=False, add_generation_prompt=True
                        )
                    )
                    index = next(
                        index
                        for index, (left, _) in enumerate(value["offset_mapping"])
                        if left == start
                    )
                    value["offset_mapping"][index] = (start - 1, start + 1)
                elif failure == "padding":
                    value["attention_mask"][0] = 0
                elif failure == "suffix":
                    value["input_ids"][-1] = 42
            return value

        def decode(self, ids: Any, **kwargs: Any) -> str:
            value = real.decode(ids, **kwargs)
            return value + "changed" if failure == "decode" else value

    monkeypatch.setattr(
        export.frozen_tokenizer_assets, "load_tokenizer", lambda binding: BrokenTokenizer()
    )
    with pytest.raises(ProtocolError, match="representation"):
        export.tokenize_candidates([row], tokenizer_binding)
