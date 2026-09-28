"""Offline correction controls using synthetic local artifacts, never paid calls."""

import hashlib
import json

import pytest
from test_finance_v7_slot_review import setup

from trusted_synthesis.finance_research import v7_review_reanalysis as audit
from trusted_synthesis.finance_research.contracts import digest
from trusted_synthesis.finance_research.storage import encode


def bound(value):
    return value | {"id": digest(value)}


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(encode(value))
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fixture_revision(tmp_path, monkeypatch, *, semantic_error=False):
    binding = bound(
        dict(
            source_commit="synthetic-committed-fixture",
            file_sha256={"fixture.py": "0" * 64},
            files_match_commit={"fixture.py": True},
            all_source_files_committed=True,
            python="fixture",
            pydantic="fixture",
        )
    )
    monkeypatch.setattr(audit, "source_binding", lambda **kwargs: binding)
    request, review = setup()
    request.update(max_output_tokens=16384, capacity_policy_id="offline-fixture")
    if semantic_error:
        review["propositions"][0]["judgment"] = "unknown"
    raw_args = json.dumps(review)
    key = "slot:synthetic"
    body = dict(
        model="deepseek-flash",
        messages=request["messages"],
        temperature=0,
        top_p=1,
        max_tokens=16384,
        thinking={"type": "disabled"},
        stream=False,
        tools=[request["strict_tool"]],
        tool_choice={"type": "function", "function": {"name": "submit_review"}},
    )
    envelope = dict(
        choices=[
            dict(
                finish_reason="tool_calls",
                message=dict(
                    tool_calls=[
                        dict(
                            id="fixture_call",
                            type="function",
                            function=dict(name="submit_review", arguments=raw_args),
                        )
                    ]
                ),
            )
        ]
    )
    raw_api = json.dumps(envelope)
    response = dict(
        semantic_review_request_sha256=digest(request),
        wire_protocol="v6_slot_review.v4",
        public_request=body,
        public_request_body_sha256=digest(body),
        request_sha256=digest(body),
        api_response_raw=raw_api,
        raw_api_response_sha256=hashlib.sha256(raw_api.encode()).hexdigest(),
        api_response=envelope,
        review_text=raw_args,
        finish_reason="tool_calls",
    )
    root = tmp_path / "revision"
    inputs = bound(
        dict(task_id=request["task_id"], original_prepared_id="fixture", requests={key: request})
    )
    input_sha = write(root / "slot_inputs/fixture/record.json", inputs)
    protocol = bound(
        dict(
            source_commit="original-synthetic-source",
            jobs=[
                dict(
                    key=key,
                    task_id=request["task_id"],
                    slot_id=request["slot_id"],
                    reviewer=request["reviewer"],
                    stage="slot",
                    request_sha256=digest(request),
                )
            ],
            slot_inputs={request["task_id"]: dict(id=inputs["id"], sha256=input_sha)},
        )
    )
    write(root / "registration/protocol.json", protocol)
    write(root / "jobs/slot_synthetic/response/record.json", response)
    write(
        root / "jobs/slot_synthetic/assessment/record.json",
        dict(
            interface_admitted=False,
            error="typed slot catalog/schema/rubric/request binding differs",
        ),
    )
    write(root / "jobs/slot_synthetic/started/record.json", dict(key=key))
    write(
        root / "technical_gate/record.json",
        bound(
            dict(
                protocol_id=protocol["id"],
                admitted=False,
                actual_review_hashes={key: digest(response)},
            )
        ),
    )
    write(root / "dispatch_stop/record.json", bound(dict(halt_retained=True)))
    return root


def file_hashes(root):
    return {
        str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in root.rglob("*.json")
    }


def test_read_only_analysis_binds_originals_and_rebuilds_actual_wire(tmp_path, monkeypatch):
    root = fixture_revision(tmp_path, monkeypatch)
    before = file_hashes(root)
    value = audit.analyze_revision(root)
    assert value["summary"]["original_response_denominator"] == 1
    assert value["summary"]["interface_admitted"] == 1
    assert value["summary"]["semantic_consistent"] == 1
    case = value["cases"][0]
    assert case["wire_binding"]["rebuilt_wire_same"]
    assert case["wire_binding"]["original_typed_locators_same"]
    assert case["original_assessment"]["interface_admitted"] is False
    assert case["corrected_assessment"]["interface_admitted"] is True
    assert value["budget_not_opened"] and value["no_halt_release"]
    assert value["summary"]["actual_api_calls_added"] == 0
    assert not value["summary"]["training_admitted"]
    assert file_hashes(root) == before


def test_immutable_publish_replay_and_original_assessments_stay_unchanged(tmp_path, monkeypatch):
    root = fixture_revision(tmp_path, monkeypatch, semantic_error=True)
    before = file_hashes(root)
    record = audit.publish_correction(root)
    output = root / audit.DEFAULT_NAME
    assert record["summary"]["interface_admitted"] == 1
    assert record["summary"]["semantic_consistent"] == 0
    replay = audit.replay_correction(output)
    assert replay["replayed"] and replay["original_files_verified"]
    assert replay["actual_api_calls_added"] == 0
    for relative, sha in before.items():
        assert hashlib.sha256((root / relative).read_bytes()).hexdigest() == sha
    with pytest.raises(ValueError, match="never overwrite"):
        audit.publish_correction(root)
    with pytest.raises(ValueError, match="separate"):
        audit.publish_correction(root, root / "technical_gate")


def test_gate_binds_every_original_response_without_cherry_picking(tmp_path, monkeypatch):
    root = fixture_revision(tmp_path, monkeypatch)
    path = root / "jobs/slot_synthetic/response/record.json"
    value = json.loads(path.read_bytes())
    value["review_text"] += " "
    write(path, value)
    with pytest.raises(ValueError, match="original sealed gate"):
        audit.analyze_revision(root)


def test_replay_rejects_changed_original_even_if_snapshot_still_replays(tmp_path, monkeypatch):
    root = fixture_revision(tmp_path, monkeypatch)
    audit.publish_correction(root)
    write(root / "jobs/slot_synthetic/assessment/record.json", {"changed": True})
    with pytest.raises(ValueError, match="original artifact"):
        audit.replay_correction(root / audit.DEFAULT_NAME)
    assert audit.replay_correction(root / audit.DEFAULT_NAME, verify_original_files=False)[
        "replayed"
    ]


def test_wire_reconstruction_rejects_even_a_hash_consistent_different_transport_body(
    tmp_path, monkeypatch
):
    root = fixture_revision(tmp_path, monkeypatch)
    value = audit.analyze_revision(root)["cases"][0]
    response = value["original_response"]
    response["public_request"]["max_tokens"] = 32768
    response["public_request_body_sha256"] = digest(response["public_request"])
    response["request_sha256"] = digest(response["public_request"])
    with pytest.raises(ValueError, match="actual sent body"):
        audit._wire_check(
            value["original_request"], response, value["wire_binding"]["registered_request_sha256"]
        )


def test_empty_prop_diagnostic_quotes_original_span_without_approving_it(tmp_path, monkeypatch):
    root = fixture_revision(tmp_path, monkeypatch)
    value = audit.analyze_revision(root)["cases"][0]["corrected_assessment"]
    span = value["validation"]["parsed"]["slot"]["mask"][0]
    span["proposition_ids"] = []
    diagnostic = audit.semantic_diagnostics(value)
    assert diagnostic["approved_spans_without_proposition_ids"][0]["quote"] == span["quote"]
    assert diagnostic["diagnostic_not_a_new_semantic_verdict"]
    assert diagnostic["no_positive_qualification_relaxed"]
