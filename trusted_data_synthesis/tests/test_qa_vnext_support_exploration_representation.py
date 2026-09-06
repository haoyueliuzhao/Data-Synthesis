"""Constructed representation fixtures only: no real HTTP, Runtime, weights or old rows."""

from __future__ import annotations

import copy
import json
import socket

import pytest

from trusted_synthesis.canonical_json import canonical_json_bytes
from trusted_synthesis.domains.finance.qa_vnext.program_adapter import ProgramTaskAdapter
from trusted_synthesis.domains.finance.qa_vnext.protocol import ProtocolError, contract
from trusted_synthesis.domains.finance.qa_vnext.protocol import record as public_record
from trusted_synthesis.domains.finance.qa_vnext.runtime import PublicQARuntime
from trusted_synthesis.domains.finance.qa_vnext.share_adapter import ShareTaskAdapter
from trusted_synthesis.experiments.finance_qa_vnext_model_execution import (
    representation as original,
)
from trusted_synthesis.experiments.finance_qa_vnext_model_execution.models import record, sha
from trusted_synthesis.experiments.finance_qa_vnext_model_execution.transport import (
    SYSTEM_PROMPT,
    HttpxSender,
)
from trusted_synthesis.experiments.finance_qa_vnext_support_exploration import (
    representation as exploration,
)

panel = exploration.panel
GUIDANCE = (
    "Try reconstructed support as a soft preference; every other legal support remains allowed."
)


def reseal(value, kind, **changes):
    fields = {key: item for key, item in value.items() if key not in {"id", "schema_version"}}
    return record(kind, **{**fields, **changes})


def forbidden(*args, **kwargs):
    pytest.fail(
        "representation test attempted Provider, Runtime, financial execution or real tokenizer"
    )


@pytest.fixture(autouse=True)
def no_execution(monkeypatch):
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket.socket, "connect_ex", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(HttpxSender, "send", forbidden)
    monkeypatch.setattr(PublicQARuntime, "__init__", forbidden)
    monkeypatch.setattr(ProgramTaskAdapter, "execute", forbidden)
    monkeypatch.setattr(ShareTaskAdapter, "execute", forbidden)


class CharacterTokenizer:
    """An exact in-memory codec; not the production tokenizer and no asset IO."""

    chat_template = "test-only-exploration-template"
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


@pytest.fixture
def environment(monkeypatch):
    binding = {
        "id": "synthetic-frozen-tokenizer-asset-reference",
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
        members=[{"synthetic_member": index} for index in range(5)],
    )
    monkeypatch.setattr(panel.length_core, "asset_binding", lambda value: asset)
    loads = []
    tokenizer = CharacterTokenizer()
    monkeypatch.setattr(
        panel.assets, "load_tokenizer", lambda value: loads.append(value["id"]) or tokenizer
    )
    return binding, exploration.representation_policy(binding), tokenizer, loads


def population(policy, *, statuses=None, run_tag="test-new-exploration", long_label=None):
    statuses = statuses or {}
    profiles = {
        name: record(
            "support_exploration_profile",
            profile=name,
            system_prompt=SYSTEM_PROMPT if name == "N" else SYSTEM_PROMPT + "\n\n" + GUIDANCE,
            synthetic_test_only=True,
        )
        for name in ("N", "E")
    }
    configurations = {
        name: record(
            "transport_config",
            profile=name,
            system_prompt=profiles[name]["system_prompt"],
            synthetic_test_only=True,
        )
        for name in ("N", "E")
    }
    condition = record(
        "support_exploration_condition",
        run_tag=run_tag,
        profiles=profiles,
        configurations=configurations,
        registered_session_count=8,
        sessions_per_profile=4,
        registered_labels=list(exploration.LABELS),
        profile_mixture={name: {"numerator": 1, "denominator": 2} for name in ("N", "E")},
        task_group="S",
        task_type=exploration.SHARE_TASK_TYPE,
        task_id="synthetic:share-task",
        context_id="synthetic:share-context",
        protocol_id=contract()["id"],
        registry_hash="synthetic:registry",
        representation_policy_id=policy["id"],
    )
    entries = []
    for label in exploration.LABELS:
        name = label[0]
        status = statuses.get(label, "success")
        eligible = status == "success"
        reg = record(
            "session_registration",
            label=label,
            profile=name,
            profile_id=profiles[name]["id"],
            model_configuration_id=configurations[name]["id"],
            session_id="synthetic:registered:" + run_tag + ":" + label,
            run_condition_id=condition["id"],
            **{
                key: condition[key]
                for key in (
                    "task_group",
                    "task_type",
                    "task_id",
                    "context_id",
                    "protocol_id",
                    "registry_hash",
                )
            },
        )
        events, targets = [], []
        for index, kind in enumerate(("action", "update", "final")):
            target = json.dumps(
                {"kind": kind, "unit_test_target": "同一原文🙂e\u0301", "index": index},
                ensure_ascii=False,
            )
            if label == long_label and index == 2:
                target += "x" * 33000
            targets.append(target)
            request = public_record(
                "request",
                state={"id": f"synthetic:shared-state:{index}"},
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
                    "origin": "synthetic_unit_fixture_not_runtime",
                    "model_configuration_id": configurations[name]["id"],
                    "session_id": reg["session_id"],
                },
            )
            if status in {"success", "known_failure"}
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
            model_configuration_id=configurations[name]["id"],
            **{
                key: reg[key]
                for key in (
                    "task_group",
                    "task_type",
                    "task_id",
                    "context_id",
                    "protocol_id",
                    "registry_hash",
                )
            },
            status=status,
            qualified=None if status in {"unknown", "not_started"} else eligible,
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
                    key: f"synthetic:{label}:{event['sequence']}:{key}" for key in original.ROW_IDS
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
                        {"role": "system", "content": profiles[name]["system_prompt"]},
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
                    http_request_sha256=sha(("synthetic-http-request-" + label).encode()),
                    http_response_sha256=sha(("synthetic-http-response-" + label).encode()),
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


def replace_first_row(entry, **changes):
    rows = entry["export"]["rows"]
    rows[0] = reseal(rows[0], "supervision_candidate", **changes)
    entry["export"] = reseal(
        entry["export"], "supervision_export", rows=rows, candidate_count=len(rows)
    )


def test_actual_profile_messages_survive_shared_encoding_and_new_eight_packages(environment):
    binding, policy, tokenizer, loads = environment
    condition, entries = population(policy)
    rows = flattened(entries)
    before = canonical_json_bytes(rows)
    result = exploration.analyze_representation(rows, entries, binding, policy, condition)
    assert len(loads) == 1
    assert canonical_json_bytes(rows) == before
    assert (
        result["tokens"]["fit_count"] == 24 and result["packages"]["registered_session_count"] == 8
    )
    assert result["packages"]["complete_session_packages"] == 8
    assert result["binding"]["generation_condition_id"] == condition["id"]
    assert result["profile_checks"]["candidate_counts_by_profile"] == {"N": 12, "E": 12}
    sidecar = result["exploration_binding"]
    assert len(sidecar["session_links"]) == 8 and len(sidecar["candidate_links"]) == 24
    assert sidecar["guided_responses_relabelled_as_neutral"] is False
    assert sidecar["profile_mixture_is_optimal_training_weight"] is False
    for row, token in zip(rows, result["tokens"]["records"], strict=True):
        rendered = tokenizer.decode(token["input_ids"])
        assert row["messages"][0]["content"] in rendered
        if GUIDANCE in row["messages"][0]["content"]:
            assert GUIDANCE in rendered
    neutral, guided = result["tokens"]["records"][0], result["tokens"]["records"][3]
    assert rows[0]["target_text"] == rows[3]["target_text"]
    assert rows[0]["messages"][1] == rows[3]["messages"][1]
    assert neutral["prompt_token_count"] < guided["prompt_token_count"]
    assert (
        neutral["input_ids"][neutral["target_token_start"] : neutral["target_token_end"]]
        == guided["input_ids"][guided["target_token_start"] : guided["target_token_end"]]
    )
    assert result["binding"]["representation_policy_id"] == policy["id"]
    assert (
        binding["maximum_sequence_length"] == 24576 and policy["maximum_sequence_length"] == 32768
    )


def test_erasing_E_guidance_is_rejected_before_encoding(environment, monkeypatch):
    binding, policy, _, loads = environment
    condition, entries = population(policy)
    entry = next(item for item in entries if item["label"] == "E01")
    messages = copy.deepcopy(entry["export"]["rows"][0]["messages"])
    messages[0]["content"] = SYSTEM_PROMPT
    replace_first_row(entry, messages=messages)
    monkeypatch.setattr(panel, "analyze_representation", forbidden)
    with pytest.raises(ProtocolError, match="actual_profile_prompt_not_preserved"):
        exploration.analyze_representation(flattened(entries), entries, binding, policy, condition)
    assert not loads


def test_reidentified_profile_configuration_mismatch_is_rejected(environment):
    _, policy, _, loads = environment
    condition, entries = population(policy)
    configurations = copy.deepcopy(condition["configurations"])
    configurations["E"] = reseal(
        configurations["E"], "transport_config", system_prompt=SYSTEM_PROMPT
    )
    changed = reseal(condition, "support_exploration_condition", configurations=configurations)
    with pytest.raises(ProtocolError, match="profile_configuration"):
        exploration.validate_profile_bindings(flattened(entries), entries, changed)
    assert not loads


def test_missing_or_duplicate_profile_session_is_not_a_new_denominator(environment):
    _, policy, _, _ = environment
    condition, entries = population(policy)
    with pytest.raises(ProtocolError, match="fixed_population"):
        exploration.validate_profile_bindings(flattened(entries[:-1]), entries[:-1], condition)
    changed = copy.deepcopy(entries)
    changed[1] = copy.deepcopy(changed[0])
    with pytest.raises(ProtocolError, match="fixed_population"):
        exploration.validate_profile_bindings(flattened(changed), changed, condition)


def test_failed_unknown_and_not_started_are_retained_without_positive_rows(environment):
    binding, policy, _, _ = environment
    condition, entries = population(
        policy, statuses={"N01": "unknown", "E01": "known_failure", "N02": "not_started"}
    )
    result = exploration.analyze_representation(
        flattened(entries), entries, binding, policy, condition
    )
    assert result["packages"]["registered_session_count"] == 8
    assert result["packages"]["complete_session_packages"] == 5
    assert result["tokens"]["candidate_count"] == 15
    for row in result["exploration_binding"]["session_links"]:
        if row["label"] in {"N01", "E01", "N02"}:
            assert row["positive_eligible"] is False and row["candidate_ids"] == []
            assert row["complete_package"] is False


def test_failure_cannot_be_given_another_profiles_positive_row(environment):
    _, policy, _, _ = environment
    condition, entries = population(policy, statuses={"E01": "known_failure"})
    failed = next(item for item in entries if item["label"] == "E01")
    row = copy.deepcopy(entries[0]["export"]["rows"][0])
    failed["export"] = reseal(failed["export"], "supervision_export", rows=[row], candidate_count=1)
    with pytest.raises(ProtocolError, match="ineligible_positive_rows"):
        exploration.validate_profile_bindings(flattened(entries), entries, condition)


def test_no_positive_outcomes_do_not_load_tokenizer_or_invent_packages(environment):
    binding, policy, _, loads = environment
    condition, entries = population(
        policy, statuses={label: "unknown" for label in exploration.LABELS}
    )
    result = exploration.analyze_representation([], entries, binding, policy, condition)
    assert loads == [] and result["tokens"]["status"] == "no_positive_candidates"
    assert result["packages"]["registered_session_count"] == 8
    assert result["packages"]["complete_session_packages"] == 0
    assert result["exploration_binding"]["candidate_links"] == []


def test_guided_overlength_row_stays_original_and_package_incomplete(environment):
    binding, policy, _, _ = environment
    condition, entries = population(policy, long_label="E04")
    rows = flattened(entries)
    original_target = rows[-1]["target_text"]
    result = exploration.analyze_representation(rows, entries, binding, policy, condition)
    assert result["tokens"]["candidate_count"] == 24
    assert result["tokens"]["not_fit_count"] == 1
    assert result["packages"]["complete_session_packages"] == 7
    package = result["packages"]["rows"][-1]
    assert (
        package["expected_units"] == 3
        and package["consumable_units"] == 2
        and package["complete"] is False
    )
    assert rows[-1]["target_text"] == original_target
    token = result["tokens"]["records"][-1]
    assert token["input_ids"] is None and token["truncated"] is False
    assert result["exploration_binding"]["candidate_links"][-1]["profile"] == "E"
    assert (
        result["exploration_binding"]["candidate_links"][-1]["tokenrepresentation_status"]
        == "not_fit"
    )


def test_new_population_has_new_data_identity_without_changing_asset_policy(environment):
    binding, policy, _, _ = environment
    first_condition, first = population(policy, run_tag="first")
    second_condition, second = population(policy, run_tag="second")
    a = exploration.analyze_representation(
        flattened(first), first, binding, policy, first_condition
    )
    b = exploration.analyze_representation(
        flattened(second), second, binding, policy, second_condition
    )
    assert a["binding"]["id"] != b["binding"]["id"]
    assert a["exploration_binding"]["id"] != b["exploration_binding"]["id"]
    assert (
        a["binding"]["representation_policy_id"]
        == b["binding"]["representation_policy_id"]
        == policy["id"]
    )
