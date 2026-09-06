"""Published-byte and parent-binding controls only; no historical work is reexecuted."""

from __future__ import annotations

import copy
import hashlib
import socket
from pathlib import Path

import pytest

from trusted_synthesis.canonical_json import canonical_json_bytes
from trusted_synthesis.domains.finance.qa_vnext import measurement as domain_measurement
from trusted_synthesis.domains.finance.qa_vnext.catalog import FinanceQACatalog
from trusted_synthesis.domains.finance.qa_vnext.program_adapter import ProgramTaskAdapter
from trusted_synthesis.domains.finance.qa_vnext.protocol import ProtocolError
from trusted_synthesis.domains.finance.qa_vnext.runtime import PublicQARuntime
from trusted_synthesis.domains.finance.qa_vnext.share_adapter import ShareTaskAdapter
from trusted_synthesis.experiments.finance_qa_vnext_model_execution import (
    qualification as original_qualification,
)
from trusted_synthesis.experiments.finance_qa_vnext_model_execution import (
    representation as original_representation,
)
from trusted_synthesis.experiments.finance_qa_vnext_model_execution.models import record
from trusted_synthesis.experiments.finance_qa_vnext_model_execution.transport import HttpxSender
from trusted_synthesis.experiments.finance_qa_vnext_panel_quotient import source

ROOT = Path(__file__).resolve().parents[2]


def forbidden(*args, **kwargs):
    pytest.fail(
        "immutable source checks may not rescan tasks or replay qualification/execution/tokens"
    )


@pytest.fixture(autouse=True)
def zero_historical_reexecution(monkeypatch):
    monkeypatch.setattr(PublicQARuntime, "__init__", forbidden)
    monkeypatch.setattr(ProgramTaskAdapter, "execute", forbidden)
    monkeypatch.setattr(ShareTaskAdapter, "execute", forbidden)
    monkeypatch.setattr(FinanceQACatalog, "frozen_source_cases", forbidden)
    monkeypatch.setattr(domain_measurement, "audit_session", forbidden)
    monkeypatch.setattr(original_qualification, "qualify_session", forbidden)
    monkeypatch.setattr(original_representation, "register_tokenizer", forbidden)
    monkeypatch.setattr(original_representation, "encode_original_candidate", forbidden)
    monkeypatch.setattr(HttpxSender, "send", forbidden)
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket.socket, "connect_ex", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)


@pytest.fixture(scope="module")
def original_inputs():
    return source.load_inputs(ROOT)


def test_exact_published_panel_anchor_and_original_population(original_inputs):
    # Execute the actual loader inside this test's active zero-reexecution guards.
    inputs = source.load_inputs(ROOT)
    assert inputs["source_binding_checks"] == original_inputs["source_binding_checks"]
    anchor = inputs["source_anchor"]
    assert anchor["commit"] == source.PARENT_COMMIT
    assert anchor["directory"] == source.SOURCE_ROOT
    assert anchor["file_count"] == 2771 and anchor["byte_count"] == 196_734_857
    assert all(
        len(row["git_blob_id"]) == 40 and len(row["sha256"]) == 64 for row in anchor["files"]
    )
    assert [entry["label"] for entry in inputs["entries"]] == list(source.LABELS)
    assert len(inputs["registrations"]) == len(inputs["entries"]) == 16
    assert len(inputs["coverage"]) == 11
    assert sum(row["selected_for_model_population"] for row in inputs["coverage"]) == 8
    checks = source.validate_inputs(inputs)
    assert checks["registered_sessions"] == 16 and checks["qualified_sessions"] == 15
    assert checks["original_supported_projections"] == 12
    assert checks["qualified_nonaccept_event_counts"] == {"D01": 1, "B01": 1, "S02": 5}
    assert checks["qualified_original_event_count"] == 120
    assert checks["qualified_admitted_event_count"] == 113
    assert checks["all_original_event_count"] == 152
    assert checks["qualification_recomputed"] is checks["graph_rebuilt"] is False
    assert (
        checks["provider_calls"]
        == checks["runtime_executions"]
        == checks["operation_executions"]
        == 0
    )
    assert checks["tokenizer_loads"] == checks["tokenizations"] == 0


def test_all_seven_history_prefixes_and_888_predecessor_sources_are_unchanged():
    history = source.history_inventory(ROOT)
    assert history["file_count"] == 12_947
    assert history["byte_count"] == 647_963_136
    assert history["all_historical_bytes_unchanged"] is True
    preserved = source.preserved_sources(ROOT)
    assert preserved["file_count"] == 888
    assert preserved["all_predecessor_sources_byte_identical"] is True


def test_existing_token_and_candidate_arrays_only_referenced(original_inputs):
    refs = original_inputs["representation_references"]
    assert refs["candidate_count"] == refs["token_record_count"] == 113
    assert len(refs["candidate_ids"]) == len(refs["token_record_ids"]) == 113
    assert len(refs["package_ids"]) == refs["registered_package_count"] == 16
    assert refs["complete_package_count"] == 15
    assert refs["cpu_batch_count"] == len(refs["cpu_binary_files"]) == 64
    assert len(refs["artifact_files"]) == 5
    assert refs["original_arrays_bound_by_published_file_bytes"] is True
    assert refs["tokenization_performed"] is refs["tokenizer_loaded"] is False
    assert refs["cpu_batches_loaded"] is refs["new_supervision_dataset_created"] is False
    assert "input_ids" not in canonical_json_bytes(refs).decode()
    assert "tokens" not in original_inputs and "candidates" not in original_inputs


def test_s01_failure_not_promoted_even_with_self_consistent_new_qualification_id(original_inputs):
    changed = copy.deepcopy(original_inputs)
    entry = next(row for row in changed["entries"] if row["label"] == "S01")
    fields = {
        key: value
        for key, value in entry["qualification"].items()
        if key not in {"id", "schema_version"}
    }
    fields.update(qualified=True, end_to_end_success=True, status="success")
    entry["qualification"] = record("qualification", **fields)
    with pytest.raises(ProtocolError, match="quotient_source.original_success_domain"):
        source.validate_inputs(changed)


@pytest.mark.parametrize("label", ["D01", "B01", "S02", "S01"])
def test_dropping_unmapped_success_or_failed_session_cannot_change_denominator(
    original_inputs, label
):
    changed = copy.deepcopy(original_inputs)
    changed["entries"] = [row for row in changed["entries"] if row["label"] != label]
    changed["registrations"] = [row for row in changed["registrations"] if row["label"] != label]
    with pytest.raises(ProtocolError, match="quotient_source.fixed_registered_denominator"):
        source.validate_inputs(changed)


def test_duplicate_original_registration_is_rejected(original_inputs):
    changed = copy.deepcopy(original_inputs)
    changed["registrations"][1]["id"] = changed["registrations"][0]["id"]
    with pytest.raises(ProtocolError, match="quotient_source.distinct_original_records"):
        source.validate_inputs(changed)


def test_swapping_actual_graphs_is_not_a_parent_binding(original_inputs):
    changed = copy.deepcopy(original_inputs)
    changed["entries"][0]["graph"] = copy.deepcopy(changed["entries"][1]["graph"])
    with pytest.raises(ProtocolError, match="quotient_source.original_parent_bindings"):
        source.validate_inputs(changed)


def test_erasing_old_nonaccept_ledger_is_not_an_accepted_source(original_inputs):
    changed = copy.deepcopy(original_inputs)
    entry = next(row for row in changed["entries"] if row["label"] == "S02")
    entry["graph"]["non_accept_event_ledger"] = []
    with pytest.raises(ProtocolError, match="identity"):
        source.validate_inputs(changed)


def test_old_supported_flag_cannot_be_forced_true(original_inputs):
    changed = copy.deepcopy(original_inputs)
    entry = next(row for row in changed["entries"] if row["label"] == "D01")
    entry["qualification"]["projection_status"] = "supported"
    with pytest.raises(ProtocolError, match="identity"):
        source.validate_inputs(changed)


def test_original_113_row_reference_denominator_cannot_be_filtered(original_inputs):
    changed = copy.deepcopy(original_inputs)
    refs = changed["representation_references"]
    fields = {key: value for key, value in refs.items() if key not in {"id", "schema_version"}}
    fields["candidate_ids"] = fields["candidate_ids"][:-1]
    changed["representation_references"] = record(
        "panel_quotient_representation_references", **fields
    )
    with pytest.raises(ProtocolError, match="quotient_source.original_representation_references"):
        source.validate_inputs(changed)


def test_validating_references_does_not_mutate_input_objects(original_inputs):
    before = canonical_json_bytes(original_inputs["entries"])
    source.validate_inputs(original_inputs)
    assert canonical_json_bytes(original_inputs["entries"]) == before
    assert all(
        row["qualification"]["quotient_assignment_id"] is None for row in original_inputs["entries"]
    )


def test_git_blob_byte_check_accepts_exact_bytes_and_rejects_mutation(monkeypatch):
    raw = b'{"a":1}'
    oid = hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()
    tree = f"100644 blob {oid}\tfixture/input.json\0".encode()
    monkeypatch.setattr(source, "git", lambda root, *args: tree)
    monkeypatch.setattr(source, "_regular_bytes", lambda root, relative: raw)
    rows = source._published_files(ROOT, "fixture")
    assert rows[0]["git_blob_id"] == oid and rows[0]["byte_count"] == len(raw)
    monkeypatch.setattr(source, "_regular_bytes", lambda root, relative: b'{"a":2}')
    with pytest.raises(ProtocolError, match="quotient_source.published_bytes_changed"):
        source._published_files(ROOT, "fixture")


def test_final_extra_metadata_has_the_exact_original_public_sources(original_inputs):
    d = next(row for row in original_inputs["entries"] if row["label"] == "D01")
    d_context = d["session"]["events"][6]["request"]["context"]
    d_final = d["session"]["events"][6]["parsed"]
    schema = d_context["public_task"]["answer_schema"]
    assert (
        schema["required_fields"] == ["value"] and schema["additional_result_properties"] is False
    )
    assert {key: value for key, value in d_final["result"].items() if key != "value"} == schema[
        "result_context"
    ]
    s = next(row for row in original_inputs["entries"] if row["label"] == "S02")
    s_context = s["session"]["events"][8]["request"]["context"]
    assert s_context["final_projection"] == "share_percent_quantized"
    assert s_context["numeric"]["final_quantum"] == "0.000001"
    percent = next(claim for claim in s["session"]["claims"] if claim["obligation_id"] == "percent")
    for turn in (8, 10):
        result = s["session"]["events"][turn]["parsed"]["result"]
        assert all(value == percent["proposition"]["output"][key] for key, value in result.items())
