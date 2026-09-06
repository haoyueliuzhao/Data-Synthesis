"""Dictionary-only panel fixtures: no Provider, Runtime, Student or GPU execution."""

from __future__ import annotations

import copy

import pytest

from trusted_synthesis.canonical_json import canonical_json_bytes
from trusted_synthesis.domains.finance.qa_vnext.protocol import ProtocolError, contract
from trusted_synthesis.domains.finance.qa_vnext.protocol import record as public_record
from trusted_synthesis.experiments.finance_qa_vnext_model_execution import representation as old
from trusted_synthesis.experiments.finance_qa_vnext_model_execution.models import record, sha
from trusted_synthesis.experiments.finance_qa_vnext_task_panel import representation as panel

GENERATION = "new_test_generation_condition"


def reseal(value, kind, **fields):
    return record(
        kind,
        **{key: val for key, val in value.items() if key not in {"id", "schema_version"}} | fields,
    )


class CharacterTokenizer:
    """Exact local test codec, not a substitute for the frozen production assets."""

    chat_template = "test-only-template"
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
        plain = value[: -len(panel.assets.CHAT_SUFFIX)] if suffix else value
        ids = [ord(char) + 1000 for char in plain]
        offsets = [(index, index + 1) for index in range(len(plain))]
        if suffix:
            ids += panel.assets.SUFFIX_TOKEN_IDS
            offsets += [(len(plain), len(value) - 1), (len(value) - 1, len(value))]
        return {"input_ids": ids, "attention_mask": [1] * len(ids), "offset_mapping": offsets}

    def decode(self, ids, **kwargs):
        return "".join(
            "<|im_end|>" if item == 151645 else "\n" if item == 198 else chr(item - 1000)
            for item in ids
        )


@pytest.fixture
def environment(monkeypatch):
    binding = {
        "id": "immutable_old_test_asset_binding",
        "maximum_sequence_length": 24576,
        "chat_template": CharacterTokenizer.chat_template,
        "chat_template_sha256": "test-template-hash",
        "software_versions": {"test": "1"},
        "pad_token_id": 151643,
    }
    asset = panel.length_core.record(
        "tokenizer_assets",
        actual_max_position_embeddings=32768,
        actual_rope_scaling=None,
        model_config_sha256="test-only-config",
        members=[{"test_member": index} for index in range(5)],
    )

    def read_assets(value):
        if value["maximum_sequence_length"] != 24576:
            raise ProtocolError("test.historical_policy_immutable")
        return asset

    loads = []
    tokenizer = CharacterTokenizer()
    monkeypatch.setattr(panel.length_core, "asset_binding", read_assets)
    monkeypatch.setattr(
        panel.assets, "load_tokenizer", lambda value: loads.append(value["id"]) or tokenizer
    )
    return binding, panel.representation_policy(binding), tokenizer, loads


def entry(label, *, units=3, status="success", long_last=False, task_group="fact"):
    protocol = contract()["id"]
    reg = record(
        "session_registration",
        session_id="registered:" + label,
        label=label,
        task_id="task:" + task_group,
        context_id="context:" + task_group,
        protocol_id=protocol,
        task_group=task_group,
        task_type="fact_retrieval",
        run_condition_id=GENERATION,
    )
    events = []
    targets = []
    for index in range(units):
        kind = "final" if index == units - 1 else "action" if index % 2 == 0 else "update"
        target = "原文🙂e\u0301 " + label + str(index) + "!" * index
        if long_last and index == units - 1:
            target += "x" * 33000
        targets.append(target)
        request = public_record(
            "request",
            state={"id": "state:" + label + str(index)},
            context={"id": reg["context_id"], "task_id": reg["task_id"]},
        )
        submission = public_record(
            "submission", raw_sha256=sha(target.encode()), raw_bytes=len(target.encode())
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
            protocol_id=protocol,
            events=events,
            final={"qa_validation": {"qa_valid": True}},
            callback_binding={"origin": "test_synthetic_dictionary_not_runtime"},
        )
        if status in {"success", "known_failure"}
        else None
    )
    eligible = status == "success"
    audit = (
        public_record(
            "session_audit",
            session_id=session["id"],
            context_id=reg["context_id"],
            protocol_id=protocol,
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
        context_id=reg["context_id"],
        task_id=reg["task_id"],
        task_type=reg["task_type"],
        task_group=task_group,
        protocol_id=protocol,
        status=status,
        qualified=eligible,
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
            index = event["sequence"]
            request, submission, receipt = (
                event[key] for key in ("request", "submission", "receipt")
            )
            fields = {key: f"test:{label}:{index}:{key}" for key in old.ROW_IDS}
            fields.update(
                representation_version=old.REPRESENTATION_VERSION,
                task_id=reg["task_id"],
                context_id=reg["context_id"],
                protocol_id=protocol,
                session_id=session["id"],
                registered_session_id=reg["session_id"],
                registration_id=reg["id"],
                qualification_id=qualification["id"],
                domain_audit_id=audit["id"],
                turn_index=index,
                public_request_id=request["id"],
                public_runtime_state_id=request["state"]["id"],
                submission_id=submission["id"],
                receipt_id=receipt["id"],
                messages=[
                    {"role": "system", "content": "same neutral prompt"},
                    {"role": "user", "content": canonical_json_bytes(request).decode()},
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
    return {
        "label": label,
        "registration": reg,
        "qualification": qualification,
        "session": session,
        "export": export,
    }


def analyze(environment, entries):
    binding, policy, _, _ = environment
    rows = [row for item in entries for row in item["export"]["rows"]]
    return panel.analyze_representation(rows, entries, binding, policy, GENERATION)


def test_policy_is_reusable_and_old_binding_unchanged(environment):
    binding, policy, _, _ = environment
    before = canonical_json_bytes(binding)
    assert policy["maximum_sequence_length"] == 32768
    assert policy["cpu_maximum_batch_size"] == 2 and policy["truncation"] is False
    assert (
        not {"candidate_ids", "session_ids", "qualification_ids", "generation_condition_id"}
        & policy.keys()
    )
    first, second = analyze(environment, [entry("F01")]), analyze(environment, [entry("F02")])
    assert first["binding"]["id"] != second["binding"]["id"]
    assert (
        first["binding"]["representation_policy_id"]
        == second["binding"]["representation_policy_id"]
    )
    assert canonical_json_bytes(binding) == before and binding["maximum_sequence_length"] == 24576


@pytest.mark.parametrize("counts", [(2,), (3, 2), (2, 3, 2, 3)])
def test_variable_session_and_event_counts_with_exact_cpu_roundtrip(environment, counts):
    entries = [entry(f"F{index:02d}", units=count) for index, count in enumerate(counts)]
    result = analyze(environment, entries)
    assert result["tokens"]["fit_count"] == sum(counts)
    assert result["packages"]["complete_session_packages"] == len(counts)
    assert [row["expected_units"] for row in result["packages"]["rows"]] == list(counts)
    cpu = result["cpu_loading"]
    assert cpu["loaded_records"] == sum(counts)
    assert cpu["batch_count"] == sum((count + 1) // 2 for count in counts)
    assert cpu["all_tensors_cpu"] is True
    assert len(result["binary_artifacts"]) == cpu["batch_count"]
    assert all(item["batch"]["shape"][0] <= 2 for item in cpu["batches"])
    assert all(item["batch"]["original_arrays_roundtrip_exact"] for item in cpu["batches"])
    assert any(item["batch"]["padding_token_count"] > 0 for item in cpu["batches"])


def test_all_sixteen_outcomes_retained_and_unknown_never_positive(environment):
    entries = [
        entry(
            f"P{index:02d}",
            status=("success", "known_failure", "unknown", "not_started")[index % 4],
        )
        for index in range(16)
    ]
    result = analyze(environment, entries)
    packages = result["packages"]
    assert len(packages["rows"]) == len(result["binding"]["registration_ids"]) == 16
    assert packages["complete_session_packages"] == 4
    for package in packages["rows"]:
        if package["qualification_status"] != "success":
            assert not package["positive_eligible"] and not package["complete"]
            assert package["expected_units"] is None and package["consumable_units"] == 0
            assert package["eligibility_status"] == "ineligible_" + package["qualification_status"]


@pytest.mark.parametrize(
    "entries", [[], [entry("X", status="unknown"), entry("N", status="not_started")]]
)
def test_no_positive_rows_does_not_load_tokenizer_or_claim_positive_cpu(environment, entries):
    result = analyze(environment, entries)
    assert environment[3] == []
    assert result["tokens"]["status"] == "no_positive_candidates"
    assert result["tokens"]["tokenizer_loaded"] is False
    assert result["tokens"]["positive_representation_validated"] is False
    assert result["cpu_loading"]["positive_cpu_loading_validated"] is False
    assert result["cpu_loading"]["all_tensors_cpu"] is None
    assert result["binary_artifacts"] == {}


def test_not_fit_keeps_original_row_diagnostics_and_full_denominator(environment):
    entries = [entry("F01", long_last=True), entry("F02", units=2)]
    before = canonical_json_bytes(entries)
    result = analyze(environment, entries)
    assert result["tokens"]["candidate_count"] == 5
    assert result["tokens"]["fit_count"] == result["cpu_loading"]["loaded_records"] == 4
    assert result["tokens"]["not_fit_count"] == 1
    assert result["tokens"]["positive_representation_validated"] is False
    late = result["tokens"]["records"][2]
    assert late["sequence_length"] > 32768 and late["truncated"] is False
    assert all(late[name] is None for name in panel.ARRAYS)
    first = result["packages"]["rows"][0]
    assert first["positive_eligible"] is True and first["complete"] is False
    assert first["expected_units"] == 3 and first["consumable_units"] == 2
    assert first["missing_or_nonconsumable_turns"] == [3]
    assert canonical_json_bytes(entries) == before


def test_missing_token_keeps_actual_event_denominator(environment):
    entries = [entry("F01")]
    result = analyze(environment, entries)
    tokens = reseal(
        result["tokens"],
        "task_panel_token_representation_dataset",
        records=result["tokens"]["records"][:-1],
    )
    packages = panel.session_packages(entries[0]["export"]["rows"], entries, tokens)
    assert packages["rows"][0]["expected_units"] == 3
    assert packages["rows"][0]["consumable_units"] == 2
    assert packages["rows"][0]["complete"] is False


@pytest.mark.parametrize(
    "change", ["subset", "reorder", "foreign_target", "foreign_parent", "old_generation"]
)
def test_exact_new_export_and_parent_binding_required(environment, change):
    entries = [entry("F01")]
    rows = copy.deepcopy(entries[0]["export"]["rows"])
    if change == "subset":
        rows.pop()
    elif change == "reorder":
        rows.reverse()
    elif change == "foreign_target":
        rows[0] = reseal(
            rows[0],
            "supervision_candidate",
            target_text="rewritten",
            target_raw_sha256=sha(b"rewritten"),
            target_raw_byte_count=9,
        )
    elif change == "foreign_parent":
        rows[0] = reseal(rows[0], "supervision_candidate", qualification_id="old_qualification")
    else:
        entries[0]["registration"] = reseal(
            entries[0]["registration"],
            "session_registration",
            run_condition_id="historical_generation",
        )
    with pytest.raises(ProtocolError):
        panel.analyze_representation(rows, entries, environment[0], environment[1], GENERATION)


@pytest.mark.parametrize("change", ["old_identity", "cap", "suffix", "causal", "template"])
def test_policy_identity_and_exact_fields_cannot_be_reused_with_changes(environment, change):
    binding, policy, _, _ = environment
    if change == "old_identity":
        policy = reseal(policy, "condition")
    else:
        key, value = {
            "cap": ("maximum_sequence_length", 65536),
            "suffix": ("suffix_token_ids", []),
            "causal": ("causal_shift", 0),
            "template": ("chat_template_sha256", "changed"),
        }[change]
        policy = reseal(policy, "task_panel_representation_policy", **{key: value})
    with pytest.raises(ProtocolError):
        panel.analyze_representation([], [], binding, policy, GENERATION)


@pytest.mark.parametrize("change", ["utf8", "suffix", "mask", "labels", "causal", "old_identity"])
def test_actual_arrays_and_original_utf8_revalidated(environment, change):
    entries = [entry("F01")]
    result = analyze(environment, entries)
    row = entries[0]["export"]["rows"][0]
    token = copy.deepcopy(result["tokens"]["records"][0])
    start, end = token["target_token_start"], token["target_token_end"]
    if change == "utf8":
        token["input_ids"][start] = ord("X") + 1000
        token["labels"][start] = token["input_ids"][start]
    elif change == "suffix":
        token["input_ids"][end] = ord("X") + 1000
    elif change == "mask":
        token["target_mask"][0] = 1
    elif change == "labels":
        token["labels"][start] = -100
    elif change == "causal":
        token["causal_target_token_start"] = start
    token = reseal(
        token,
        "token_representation" if change == "old_identity" else "task_panel_token_representation",
    )
    with pytest.raises(ProtocolError):
        panel.validate_record(
            row, token, result["binding"], environment[1], environment[0], environment[2]
        )


def test_historical_encoder_default_remains_24576(environment):
    row = entry("F01")["export"]["rows"][0]
    token = old._tokenize_candidate(row, environment[0], environment[2])
    assert token["maximum_sequence_length"] == old.MAXIMUM_SEQUENCE_LENGTH == 24576
    assert token["schema_version"] == "qa_vnext_model_execution_token_representation.v1"
