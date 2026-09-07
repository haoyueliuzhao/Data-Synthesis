"""Read-only source joins and isolated mutations; no historical producer is rerun."""

from __future__ import annotations

import copy
import hashlib
import socket
from pathlib import Path

import pytest

from trusted_synthesis.canonical_json import canonical_json_bytes
from trusted_synthesis.domains.finance.qa_vnext import measurement as original_audit
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
from trusted_synthesis.experiments.finance_qa_vnext_support_exploration import (
    quotient as original_support,
)
from trusted_synthesis.experiments.finance_qa_vnext_support_transition import source

ROOT = Path(__file__).resolve().parents[2]


def forbidden(*args, **kwargs):
    pytest.fail("source-only checks may not execute or recompute historical producers")


@pytest.fixture(autouse=True)
def no_replay(monkeypatch):
    for owner, name in (
        (PublicQARuntime, "__init__"),
        (ProgramTaskAdapter, "execute"),
        (ShareTaskAdapter, "execute"),
        (FinanceQACatalog, "frozen_source_cases"),
        (original_audit, "audit_session"),
        (original_audit, "_validate"),
        (original_qualification, "qualify_session"),
        (original_support, "actual_support"),
        (original_representation, "register_tokenizer"),
        (original_representation, "encode_original_candidate"),
        (original_representation.frozen_tokenizer_assets, "load_tokenizer"),
        (original_representation.frozen_tokenizer_assets, "_load_local"),
        (original_representation.frozen_tokenizer_assets, "_read_members"),
        (HttpxSender, "send"),
        (socket.socket, "connect"),
        (socket.socket, "connect_ex"),
        (socket, "create_connection"),
    ):
        monkeypatch.setattr(owner, name, forbidden)


@pytest.fixture(scope="module")
def original_inputs():
    return source.load_inputs(ROOT)


def reseal(value, kind, **changes):
    fields = {key: item for key, item in value.items() if key not in {"id", "schema_version"}}
    return record(kind, **{**fields, **changes})


def test_actual_load_binds_2893_published_files_and_does_not_parse_token_arrays(monkeypatch):
    original_load = source._load
    paths = []

    def metadata_only(root, relative, members):
        assert not relative.endswith(
            ("token_representations.json", "supervision_candidates.json", ".npz")
        )
        paths.append(relative)
        return original_load(root, relative, members)

    monkeypatch.setattr(source, "_load", metadata_only)
    inputs = source.load_inputs(ROOT)
    anchor = inputs["source_anchor"]
    assert anchor["predecessor_commit"] == "6d05782ad3e4e47978f2da19ba0bd5e3ac041fc2"
    assert anchor["file_count"] == 2893 and anchor["byte_count"] == 143_825_264
    assert all(
        len(item["git_blob_id"]) == 40 and len(item["sha256"]) == 64 for item in anchor["members"]
    )
    assert paths and inputs["source_binding_checks"]["token_arrays_decoded"] is False


def test_original_eight_outcomes_and_full_valid_event_partition_are_retained(original_inputs):
    inputs = original_inputs
    checks = source.validate_inputs(inputs)
    assert [entry["label"] for entry in inputs["entries"]] == list(source.LABELS)
    assert checks["qualified_labels"] == ["E02", "N03", "E04"]
    assert checks["registered_session_count"] == 8 and checks["known_failure_count"] == 5
    assert len(checks["qualified_qualification_ids"]) == 3
    assert checks["qualified_original_event_count"] == 42
    assert (
        checks["qualified_admitted_event_count"] == checks["qualified_unadmitted_event_count"] == 21
    )
    assert checks["all_original_event_count"] == 202
    assert checks["newly_interpreted_display_turns"] == {"E02": [1, 2, 9, 11, 12, 14], "N03": [1]}
    assert (
        checks["newly_interpreted_event_count"] == 7
        and checks["already_interpreted_event_count"] == 14
    )
    assert checks["new_interpretation_positions_are_requested_scope_not_results"] is True
    assert checks["new_event_interpretation_performed"] is False
    assert checks["qualifications_recomputed"] is checks["actual_support_recomputed"] is False


def test_old_rule_target_and_null_distribution_remain_historical_objects(original_inputs):
    condition = original_inputs["generation_condition"]
    quotient = original_inputs["old_quotient"]
    measurement = original_inputs["old_measurement"]
    assert condition["id"] == source.GENERATION_CONDITION_ID
    assert condition["rule_id"] == source.OLD_RULE_ID
    assert condition["new_post_outcome_quotient_rules_allowed"] is False
    assert quotient["target_witness"]["established"] is False
    assert (
        quotient["complete_class_count"] is None and measurement["conditional_distribution"] is None
    )
    assert measurement["success_fraction"] == {"numerator": 3, "denominator": 8}
    assert [row["label"] for row in quotient["projections"] if row["supported"]] == ["E04"]
    for entry in original_inputs["entries"]:
        assert entry["old_finite_projection"] == entry["audit"]["finite_projection"]
        assert entry["old_behavior"] == entry["old_projection"]["behavior_projection"]
        assert entry["old_support"]["projection_id"] == entry["old_projection"]["id"]


def test_original_21_representations_are_opaque_byte_and_identity_references(original_inputs):
    refs = original_inputs["representation_references"]
    assert len(refs["candidate_ids"]) == len(refs["token_record_ids"]) == 21
    assert refs["registered_package_count"] == len(refs["package_ids"]) == 8
    assert refs["complete_package_count"] == 3 and refs["cpu_batch_count"] == 12
    assert len(refs["cpu_binary_files"]) == 12 and len(refs["artifact_files"]) == 7
    candidate_file = next(
        row for row in refs["artifact_files"] if row["path"].endswith("supervision_candidates.json")
    )
    assert candidate_file["record_id"] is None
    assert refs["raw_candidate_records_parsed"] is refs["token_arrays_decoded"] is False
    assert (
        refs["cpu_arrays_loaded"] is refs["tokenizer_loaded"] is refs["new_tokenization"] is False
    )
    assert "input_ids" not in canonical_json_bytes(refs).decode()
    assert {row["profile"] for row in refs["candidate_profile_links"]} == {"N", "E"}


def test_nine_historical_prefixes_and_908_old_sources_are_published_bytes():
    history = source.history_inventory(ROOT)
    assert history["file_count"] == 15_877 and history["byte_count"] == 797_477_854
    assert history["all_historical_bytes_unchanged"] is True
    preservation = source.preserved_sources(ROOT)
    assert preservation["file_count"] == 908
    assert preservation["all_predecessor_python_bytes_unchanged"] is True


@pytest.mark.parametrize("label", ["E02", "N03", "E04"])
def test_valid_observation_cannot_be_dropped_from_eight_denominator(original_inputs, label):
    changed = copy.deepcopy(original_inputs)
    changed["entries"] = [entry for entry in changed["entries"] if entry["label"] != label]
    changed["registrations"] = [row for row in changed["registrations"] if row["label"] != label]
    with pytest.raises(ProtocolError, match="original_eight_population"):
        source.validate_inputs(changed)


@pytest.mark.parametrize("label", ["N01", "E01", "N02", "E03", "N04"])
def test_rehashed_failure_cannot_be_promoted_to_original_valid_domain(original_inputs, label):
    changed = copy.deepcopy(original_inputs)
    entry = next(row for row in changed["entries"] if row["label"] == label)
    entry["qualification"] = reseal(
        entry["qualification"],
        "qualification",
        qualified=True,
        end_to_end_success=True,
        status="success",
    )
    with pytest.raises(ProtocolError, match="original_qualified_domain"):
        source.validate_inputs(changed)


def test_original_generation_cannot_be_reidentified_with_a_new_measurement_rule(original_inputs):
    changed = copy.deepcopy(original_inputs)
    changed["generation_condition"] = reseal(
        changed["generation_condition"],
        "support_exploration_condition",
        rule_id="new_measurement_rule",
        new_post_outcome_quotient_rules_allowed=True,
    )
    with pytest.raises(ProtocolError, match="original_generation_and_measurement"):
        source.validate_inputs(changed)


def test_seven_positions_are_not_the_complete_rejected_event_domain(original_inputs):
    changed = copy.deepcopy(original_inputs)
    entry = next(row for row in changed["entries"] if row["label"] == "E02")
    entry["old_projection"]["interpretation_ledger"] = [
        row
        for row in entry["old_projection"]["interpretation_ledger"]
        if row["disposition"] == "undetermined"
    ]
    with pytest.raises(ProtocolError, match="identity"):
        source.validate_inputs(changed)


def test_replacing_original_support_proof_or_E04_projection_is_rejected(original_inputs):
    changed = copy.deepcopy(original_inputs)
    entry = next(row for row in changed["entries"] if row["label"] == "N03")
    entry["old_support"] = reseal(
        entry["old_support"], "support_exploration_support", support="disclosed_total"
    )
    with pytest.raises(ProtocolError, match="original_parent_bindings"):
        source.validate_inputs(changed)
    changed = copy.deepcopy(original_inputs)
    entry = next(row for row in changed["entries"] if row["label"] == "E04")
    entry["old_projection"] = reseal(
        entry["old_projection"],
        "panel_quotient_projection",
        status="undetermined",
        supported=False,
        behavior_projection=None,
    )
    with pytest.raises(ProtocolError, match="original_parent_bindings"):
        source.validate_inputs(changed)


def test_filtering_21_candidate_references_cannot_redefine_representation_population(
    original_inputs,
):
    changed = copy.deepcopy(original_inputs)
    refs = changed["representation_references"]
    changed["representation_references"] = reseal(
        refs,
        "support_transition_representation_references",
        candidate_ids=refs["candidate_ids"][:-1],
    )
    with pytest.raises(ProtocolError, match="original_representation_references"):
        source.validate_inputs(changed)


def test_source_join_checks_do_not_modify_original_objects(original_inputs):
    before = canonical_json_bytes(
        {
            key: value
            for key, value in original_inputs.items()
            if key not in {"root", "source_directory"}
        }
    )
    source.validate_inputs(original_inputs)
    assert before == canonical_json_bytes(
        {
            key: value
            for key, value in original_inputs.items()
            if key not in {"root", "source_directory"}
        }
    )


def test_git_blob_bytes_are_checked_not_only_file_names(monkeypatch):
    raw = b'{"original":true}'
    oid = hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()
    tree = f"100644 blob {oid}\tfixture/original.json\0".encode()
    monkeypatch.setattr(source.subprocess, "check_output", lambda *args, **kwargs: tree)
    monkeypatch.setattr(source, "_regular_bytes", lambda root, relative: raw)
    assert source._git_members(ROOT, ("fixture",))[0]["git_blob_id"] == oid
    monkeypatch.setattr(source, "_regular_bytes", lambda root, relative: b'{"original":false}')
    with pytest.raises(ProtocolError, match="published_bytes_changed"):
        source._git_members(ROOT, ("fixture",))
