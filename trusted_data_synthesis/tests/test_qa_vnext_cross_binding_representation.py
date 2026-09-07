"""Constructed exports on the three real bindings; no historical rows or model execution."""

from __future__ import annotations

import copy
import json
import socket
from pathlib import Path

import pytest

from trusted_synthesis.canonical_json import canonical_json_bytes
from trusted_synthesis.domains.finance.qa_vnext.bound_share_adapter import BoundShareTaskAdapter
from trusted_synthesis.domains.finance.qa_vnext.protocol import ProtocolError
from trusted_synthesis.domains.finance.qa_vnext.protocol import record as public_record
from trusted_synthesis.domains.finance.qa_vnext.runtime import PublicQARuntime
from trusted_synthesis.experiments.finance_qa_vnext_cross_binding import plan, representation
from trusted_synthesis.experiments.finance_qa_vnext_cross_binding.source import load_sources
from trusted_synthesis.experiments.finance_qa_vnext_model_execution import (
    representation as original,
)
from trusted_synthesis.experiments.finance_qa_vnext_model_execution.models import record, sha
from trusted_synthesis.experiments.finance_qa_vnext_model_execution.transport import (
    SYSTEM_PROMPT,
    HttpxSender,
)

ROOT = Path(__file__).resolve().parents[2]
panel = representation.panel


def reseal(value, kind, **changes):
    fields = {key: item for key, item in value.items() if key not in {"id", "schema_version"}}
    return record(kind, **{**fields, **changes})


def forbidden(*args, **kwargs):
    pytest.fail("representation test attempted Provider, Runtime, financial execution or asset IO")


@pytest.fixture(autouse=True)
def no_execution(monkeypatch):
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket.socket, "connect_ex", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(HttpxSender, "send", forbidden)
    monkeypatch.setattr(PublicQARuntime, "__init__", forbidden)
    monkeypatch.setattr(BoundShareTaskAdapter, "execute", forbidden)
    monkeypatch.setattr(original, "register_tokenizer", forbidden)


class CharacterTokenizer:
    """Exact in-memory codec, expressly not the production tokenizer."""

    chat_template = "test-only-cross-binding-template"
    all_special_ids = [151645, 151643]

    def apply_chat_template(self, messages, *, tokenize, add_generation_prompt):
        assert tokenize is False
        prefix = "S:" + messages[0]["content"] + "U:" + messages[1]["content"] + "A:"
        return (
            prefix
            if add_generation_prompt
            else prefix + messages[-1]["content"] + panel.assets.CHAT_SUFFIX
        )

    def __call__(self, value, **kwargs):
        assert kwargs.get("truncation") is False and kwargs.get("padding") is False
        suffix = value.endswith(panel.assets.CHAT_SUFFIX)
        text = value[: -len(panel.assets.CHAT_SUFFIX)] if suffix else value
        ids = [ord(character) + 1000 for character in text]
        offsets = [(index, index + 1) for index in range(len(text))]
        if suffix:
            ids += panel.assets.SUFFIX_TOKEN_IDS
            offsets += [(len(text), len(value) - 1), (len(value) - 1, len(value))]
        return {"input_ids": ids, "attention_mask": [1] * len(ids), "offset_mapping": offsets}

    def decode(self, ids, **kwargs):
        return "".join(
            "<|im_end|>" if value == 151645 else "\n" if value == 198 else chr(value - 1000)
            for value in ids
        )


@pytest.fixture(scope="module")
def bound_adapters():
    return [BoundShareTaskAdapter(source) for source in load_sources(ROOT)]


@pytest.fixture
def environment(monkeypatch):
    binding = {
        "id": "synthetic-tokenizer-reference-no-historical-rows",
        "maximum_sequence_length": 24576,
        "chat_template": CharacterTokenizer.chat_template,
        "chat_template_sha256": "synthetic-template-hash",
        "software_versions": {"test": "1"},
        "pad_token_id": 151643,
    }
    asset = panel.length_core.record(
        "tokenizer_assets",
        actual_max_position_embeddings=32768,
        actual_rope_scaling=None,
        members=[{"fixture": i} for i in range(5)],
    )
    monkeypatch.setattr(panel.length_core, "asset_binding", lambda value: asset)
    tokenizer, loads = CharacterTokenizer(), []
    monkeypatch.setattr(
        panel.assets, "load_tokenizer", lambda value: loads.append(value["id"]) or tokenizer
    )
    return binding, representation.representation_policy(binding), tokenizer, loads


def population(
    policy,
    adapters,
    *,
    statuses=None,
    long_label=None,
    extra_turn_label=None,
    marker="new-cross-binding-fixture",
):
    """Use actual new task/config identities; create only explicitly synthetic response records."""
    condition, registrations, _ = plan.freeze_condition(
        adapters,
        [item.source.binding_record for item in adapters],
        record("implementation", synthetic_test_marker=marker),
        policy,
        record("cross_binding_representation_test_rule", synthetic_test_only=True),
    )
    statuses = statuses or {}
    entries = []
    for reg in registrations:
        label, profile = reg["label"], reg["profile"]
        status = statuses.get(label, "success")
        eligible = status == "success"
        kinds = (
            ("action", "update", "action", "update", "final")
            if label == extra_turn_label
            else ("action", "update", "final")
        )
        events, targets = [], []
        for index, kind in enumerate(kinds):
            target = (
                "  "
                + json.dumps(
                    {"kind": kind, "test_raw_unicode": "原文🙂e\u0301", "index": index},
                    ensure_ascii=False,
                )
                + "\n"
            )
            if label == long_label and index == len(kinds) - 1:
                target += "x" * 33000
            targets.append(target)
            request = public_record(
                "request",
                state={"id": f"constructed-state:{index}"},
                context={"id": reg["context_id"], "task_id": reg["task_id"]},
            )
            submission = public_record(
                "submission",
                raw_sha256=sha(target.encode()),
                raw_bytes=len(target.encode()),
                synthetic_registration=reg["id"],
                synthetic_turn=index,
            )
            receipt = public_record("receipt", admitted=True, submission_id=submission["id"])
            events.append(
                {
                    "sequence": index,
                    "request": request,
                    "submission": submission,
                    "receipt": receipt,
                    "parsed": {"kind": kind},
                }
            )
        session = (
            public_record(
                "session",
                context_id=reg["context_id"],
                protocol_id=reg["protocol_id"],
                events=events,
                final={"qa_validation": {"qa_valid": eligible}},
                callback_binding={
                    "origin": "constructed_representation_unit_fixture_not_runtime",
                    "model_configuration_id": reg["model_configuration_id"],
                    "session_id": reg["session_id"],
                },
            )
            if status in ("success", "known_failure")
            else None
        )
        audit = (
            public_record(
                "session_audit",
                session_id=session["id"],
                context_id=reg["context_id"],
                protocol_id=reg["protocol_id"],
                task_id=reg["task_id"],
                validation_passed=True,
                evidence_complete=True,
                qualified=True,
                qa_valid=True,
                trajectory_valid=True,
                errors=[],
                projection_supported=False,
            )
            if eligible
            else None
        )
        qualification = record(
            "qualification",
            registration_id=reg["id"],
            registered_session_id=reg["session_id"],
            session_id=session["id"] if session else None,
            model_configuration_id=reg["model_configuration_id"],
            **{key: reg[key] for key in plan.TASK_FIELDS},
            status=status,
            qualified=None if status in ("unknown", "not_started") else eligible,
            model_origin_verified=eligible,
            export_eligible=eligible,
            evidence_complete=status != "unknown",
            qa_valid=eligible,
            trajectory_valid=eligible,
            domain_audit=audit,
            projection_status="undetermined",
        )
        rows = []
        if eligible:
            for event, target in zip(events, targets, strict=True):
                fields = {
                    key: f"constructed:{label}:{event['sequence']}:{key}"
                    for key in original.ROW_IDS
                }
                fields.update(
                    representation_version=original.REPRESENTATION_VERSION,
                    task_id=reg["task_id"],
                    context_id=reg["context_id"],
                    protocol_id=reg["protocol_id"],
                    session_id=session["id"],
                    registered_session_id=reg["session_id"],
                    registration_id=reg["id"],
                    qualification_id=qualification["id"],
                    domain_audit_id=audit["id"],
                    turn_index=event["sequence"],
                    public_request_id=event["request"]["id"],
                    public_runtime_state_id=event["request"]["state"]["id"],
                    submission_id=event["submission"]["id"],
                    receipt_id=event["receipt"]["id"],
                    messages=[
                        {
                            "role": "system",
                            "content": condition["configurations"][profile]["system_prompt"],
                        },
                        {
                            "role": "user",
                            "content": canonical_json_bytes(event["request"]).decode(),
                        },
                    ],
                    target_text=target,
                    target_raw_sha256=sha(target.encode()),
                    target_raw_byte_count=len(target.encode()),
                    submission_kind=event["parsed"]["kind"],
                    admitted=True,
                    qualified=True,
                    model_origin_verified=True,
                    quotient_assignment_id=None,
                    class_weights_assigned=False,
                    http_request_sha256=sha(("constructed-request-" + label).encode()),
                    http_response_sha256=sha(("constructed-response-" + label).encode()),
                )
                rows.append(record("supervision_candidate", **fields))
        export = record(
            "supervision_export",
            session_id=qualification["session_id"],
            qualification_id=qualification["id"],
            rows=rows,
            candidate_count=len(rows),
            session_exclusion_reasons=[] if eligible else [status],
        )
        entries.append(
            {
                "label": label,
                "registration": reg,
                "qualification": qualification,
                "session": session,
                "export": export,
            }
        )
    return condition, entries


def flattened(entries):
    return [row for entry in entries for row in entry["export"]["rows"]]


def change_rows(entry, rows):
    entry["export"] = reseal(
        entry["export"], "supervision_export", rows=rows, candidate_count=len(rows)
    )


def test_exact_N_E_prompts_raw_targets_and_new_token_package_links(environment, bound_adapters):
    binding, policy, tokenizer, loads = environment
    condition, entries = population(policy, bound_adapters)
    rows = flattened(entries)
    before = canonical_json_bytes(rows)
    result = representation.analyze_representation(rows, entries, binding, policy, condition)
    assert len(loads) == 1 and canonical_json_bytes(rows) == before
    assert result["tokens"]["fit_count"] == result["cpu_loading"]["loaded_records"] == 36
    assert (
        result["packages"]["registered_session_count"]
        == result["packages"]["complete_session_packages"]
        == 12
    )
    assert result["profile_checks"]["task_count"] == 3
    assert result["profile_checks"]["candidate_counts_by_profile"] == {"N": 18, "E": 18}
    linked = result["cross_binding"]
    assert linked["historical_supervision_or_token_rows_imported"] is False
    assert linked["training_weights_materialized"] is False
    assert linked["student_forward_calls"] == linked["student_updates"] == linked["gpu_jobs"] == 0
    tokens = {item["row_id"]: item for item in result["tokens"]["records"]}
    packages = {item["id"]: item for item in result["packages"]["rows"]}
    assert len(linked["session_links"]) == 12 and len(linked["candidate_links"]) == 36
    for row, link in zip(rows, linked["candidate_links"], strict=True):
        token = tokens[row["id"]]
        profile = link["profile"]
        assert (
            row["messages"][0]["content"] == condition["configurations"][profile]["system_prompt"]
        )
        assert row["messages"][0]["content"] in tokenizer.decode(token["input_ids"])
        assert (
            tokenizer.decode(
                token["input_ids"][token["target_token_start"] : token["target_token_end"]]
            )
            == row["target_text"]
        )
        assert link["token_record_id"] == token["id"]
        assert row["id"] in {unit["candidate_id"] for unit in packages[link["package_id"]]["units"]}
        panel.validate_record(row, token, result["binding"], policy, binding, tokenizer)
    assert rows[0]["target_text"] == rows[3]["target_text"]
    assert rows[0]["messages"][1] == rows[3]["messages"][1]
    assert tokens[rows[0]["id"]]["prompt_token_count"] < tokens[rows[3]["id"]]["prompt_token_count"]
    assert (
        binding["maximum_sequence_length"] == 24576 and policy["maximum_sequence_length"] == 32768
    )


def test_guided_prompt_erasure_fails_before_any_encoding(environment, bound_adapters):
    binding, policy, _, loads = environment
    condition, entries = population(policy, bound_adapters)
    entry = next(item for item in entries if item["label"] == "T01_E01")
    rows = copy.deepcopy(entry["export"]["rows"])
    messages = copy.deepcopy(rows[0]["messages"])
    messages[0]["content"] = SYSTEM_PROMPT
    rows[0] = reseal(rows[0], "supervision_candidate", messages=messages)
    change_rows(entry, rows)
    with pytest.raises(ProtocolError, match="original_profile_request_and_target"):
        representation.analyze_representation(
            flattened(entries), entries, binding, policy, condition
        )
    assert loads == []


@pytest.mark.parametrize("mutation", ["missing", "duplicate", "profile_imbalance"])
def test_frozen_three_task_twelve_registration_denominator_cannot_shrink(
    environment, bound_adapters, mutation
):
    _, policy, _, _ = environment
    condition, entries = population(policy, bound_adapters)
    if mutation == "missing":
        entries.pop()
    elif mutation == "duplicate":
        entries[-1] = copy.deepcopy(entries[0])
    else:
        entries[-1]["registration"] = reseal(
            entries[-1]["registration"], "session_registration", profile="N"
        )
    with pytest.raises(ProtocolError, match="frozen_population|per_task_profile_denominators"):
        representation.validate_profile_bindings(flattened(entries), entries, condition)


def test_same_task_field_cannot_be_replaced_by_another_source(environment, bound_adapters):
    _, policy, _, _ = environment
    condition, entries = population(policy, bound_adapters)
    entries[0]["registration"] = reseal(
        entries[0]["registration"], "session_registration", task_id=bound_adapters[1].source.task_id
    )
    with pytest.raises(ProtocolError, match="new_task_profile_parents"):
        representation.validate_profile_bindings(flattened(entries), entries, condition)


def test_original_target_rewrite_even_rehashed_cannot_replace_saved_submission(
    environment, bound_adapters
):
    binding, policy, _, loads = environment
    condition, entries = population(policy, bound_adapters)
    rows = copy.deepcopy(entries[0]["export"]["rows"])
    target = rows[0]["target_text"].strip()
    rows[0] = reseal(
        rows[0],
        "supervision_candidate",
        target_text=target,
        target_raw_sha256=sha(target.encode()),
        target_raw_byte_count=len(target.encode()),
    )
    change_rows(entries[0], rows)
    with pytest.raises(ProtocolError, match="original_profile_request_and_target"):
        representation.analyze_representation(
            flattened(entries), entries, binding, policy, condition
        )
    assert loads == []


def test_all_admitted_events_not_fixed_turn_count_define_complete_package(
    environment, bound_adapters
):
    binding, policy, _, _ = environment
    condition, entries = population(policy, bound_adapters, extra_turn_label="T03_E02")
    result = representation.analyze_representation(
        flattened(entries), entries, binding, policy, condition
    )
    assert result["tokens"]["candidate_count"] == 38
    assert result["packages"]["rows"][-1]["expected_units"] == 5
    change_rows(entries[-1], entries[-1]["export"]["rows"][:-1])
    with pytest.raises(ProtocolError, match="admitted_export_denominator"):
        representation.analyze_representation(
            flattened(entries), entries, binding, policy, condition
        )


def test_failures_unknown_not_started_stay_in_denominator_without_positive_rows(
    environment, bound_adapters
):
    binding, policy, _, _ = environment
    statuses = {"T01_N01": "known_failure", "T02_E01": "unknown", "T03_N02": "not_started"}
    condition, entries = population(policy, bound_adapters, statuses=statuses)
    result = representation.analyze_representation(
        flattened(entries), entries, binding, policy, condition
    )
    assert result["packages"]["registered_session_count"] == 12
    assert result["packages"]["complete_session_packages"] == 9
    assert result["tokens"]["candidate_count"] == 27
    for package in result["packages"]["rows"]:
        if package["label"] in statuses:
            assert package["positive_eligible"] is False and package["complete"] is False
            assert package["units"] == [] and package["expected_units"] is None
    failed = next(item for item in entries if item["label"] == "T01_N01")
    change_rows(failed, [copy.deepcopy(flattened(entries)[0])])
    with pytest.raises(ProtocolError, match="failed_positive"):
        representation.validate_profile_bindings(flattened(entries), entries, condition)


def test_overlength_final_keeps_whole_package_incomplete_and_original_target(
    environment, bound_adapters
):
    binding, policy, _, _ = environment
    condition, entries = population(policy, bound_adapters, long_label="T03_E02")
    rows = flattened(entries)
    before = canonical_json_bytes(rows)
    result = representation.analyze_representation(rows, entries, binding, policy, condition)
    assert canonical_json_bytes(rows) == before
    assert result["tokens"]["candidate_count"] == 36 and result["tokens"]["not_fit_count"] == 1
    assert result["cpu_loading"]["loaded_records"] == 35
    assert result["packages"]["complete_session_packages"] == 11
    package, token = result["packages"]["rows"][-1], result["tokens"]["records"][-1]
    assert (
        package["expected_units"] == 3
        and package["consumable_units"] == 2
        and not package["complete"]
    )
    assert token["input_ids"] is token["labels"] is None
    assert token["truncated"] is False and token["tokenrepresentation_status"] == "not_fit"
    assert result["cross_binding"]["candidate_links"][-1]["token_record_id"] == token["id"]
    assert result["cross_binding"]["candidate_links"][-1]["profile"] == "E"


def test_zero_success_loads_no_tokenizer_and_fabricates_no_complete_packages(
    environment, bound_adapters
):
    binding, policy, _, loads = environment
    statuses = {
        label: ("known_failure", "unknown", "not_started")[index % 3]
        for index, label in enumerate(plan.LABELS)
    }
    condition, entries = population(policy, bound_adapters, statuses=statuses)
    result = representation.analyze_representation([], entries, binding, policy, condition)
    assert loads == [] and result["tokens"]["status"] == "no_positive_candidates"
    assert result["packages"]["registered_session_count"] == 12
    assert result["packages"]["complete_session_packages"] == 0
    assert result["cross_binding"]["candidate_links"] == []
    assert len(result["cross_binding"]["session_links"]) == 12
    assert result["cpu_loading"]["loaded_records"] == 0 and result["binary_artifacts"] == {}


def test_fresh_population_cannot_reuse_previous_token_records(environment, bound_adapters):
    binding, policy, tokenizer, _ = environment
    condition_a, entries_a = population(
        policy, bound_adapters, marker="first-constructed-population"
    )
    condition_b, entries_b = population(
        policy, bound_adapters, marker="second-constructed-population"
    )
    rows_a, rows_b = flattened(entries_a), flattened(entries_b)
    a = representation.analyze_representation(rows_a, entries_a, binding, policy, condition_a)
    b = representation.analyze_representation(rows_b, entries_b, binding, policy, condition_b)
    assert a["binding"]["id"] != b["binding"]["id"]
    assert a["cross_binding"]["id"] != b["cross_binding"]["id"]
    assert a["tokens"]["id"] != b["tokens"]["id"]
    assert (
        a["binding"]["representation_policy_id"]
        == b["binding"]["representation_policy_id"]
        == policy["id"]
    )
    assert not set(a["binding"]["candidate_ids"]) & set(b["binding"]["candidate_ids"])
    with pytest.raises(ProtocolError, match="token_parent_binding"):
        panel.validate_record(
            rows_b[0], a["tokens"]["records"][0], b["binding"], policy, binding, tokenizer
        )
