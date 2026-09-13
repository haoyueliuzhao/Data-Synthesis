"""Synthetic original-schema controls, never real-material training admission."""

import copy
import json

import pytest

from trusted_synthesis.domains.finance.qa_vnext.protocol import contract
from trusted_synthesis.experiments.finance_qa_vnext_eval_readiness import training_runtime
from trusted_synthesis.experiments.finance_qa_vnext_hierarchical_loss import representation as layer
from trusted_synthesis.experiments.finance_qa_vnext_hierarchical_loss.protocol import (
    encode,
    record,
    sha,
)
from trusted_synthesis.experiments.finance_qa_vnext_model_execution import (
    representation as original,
)
from trusted_synthesis.experiments.finance_qa_vnext_model_execution.models import (
    record as model_record,
)
from trusted_synthesis.experiments.qa_reasoning_share_training_preflight.tokenization import (
    CHAT_SUFFIX,
    SUFFIX_TOKEN_IDS,
)


class SyntheticCharacterTokenizer:
    """No asset load: synthetic codepoint tokens exercise the original encoder."""

    all_special_ids = SUFFIX_TOKEN_IDS

    def apply_chat_template(self, messages, *, tokenize, add_generation_prompt):
        assert tokenize is False
        prefix_messages = messages if add_generation_prompt else messages[:-1]
        prefix = "".join("[" + item["role"] + "]" + item["content"] for item in prefix_messages)
        prefix += "[assistant]"
        return prefix if add_generation_prompt else prefix + messages[-1]["content"] + CHAT_SUFFIX

    def __call__(self, text, **kwargs):
        suffix = text.endswith(CHAT_SUFFIX)
        body = text[: -len(CHAT_SUFFIX)] if suffix else text
        ids = [1000 + ord(char) for char in body]
        offsets = [(i, i + 1) for i in range(len(body))]
        if suffix:
            ids += SUFFIX_TOKEN_IDS
            offsets += [(len(body), len(text) - 1), (len(text) - 1, len(text))]
        return {"input_ids": ids, "attention_mask": [1] * len(ids), "offset_mapping": offsets}

    def decode(self, ids, **kwargs):
        return "".join(chr(token - 1000) for token in ids)


def reseal(value, factory):
    return factory(
        **{key: item for key, item in value.items() if key not in {"id", "schema_version"}}
    )


def candidate(target, index, *, kind=None, legacy=False):
    text = (
        json.dumps(target, ensure_ascii=False, separators=(",", ":"))
        if isinstance(target, dict)
        else target
    )
    messages = [
        {"role": "system", "content": "synthetic public system"},
        {"role": "user", "content": "synthetic original question and tool observation"},
    ]
    common = dict(
        task_id="task:synthetic",
        session_id="session:synthetic",
        qualification_id="qualification:synthetic",
        messages=messages,
        target_text=text,
        target_raw_sha256=sha(text),
    )
    if not legacy:
        return training_runtime.record(
            "original_Teacher_response",
            **common,
            response_index=index,
            public_runtime_state_id="history:" + sha(encode(messages)),
            response_kind=kind or ("Final" if "final" in target else target["tool"]),
            actual_method="endpoint",
            origin="live_teacher_callback",
            training_sample=False,
            transport_evidence={"synthetic_fixture_only": True},
        )
    common.update({name: "synthetic:" + name for name in original.ROW_IDS if name not in common})
    common.update(protocol_id=contract()["id"], public_runtime_state_id="state:synthetic")
    return model_record(
        "supervision_candidate",
        **common,
        representation_version=original.REPRESENTATION_VERSION,
        turn_index=index,
        submission_kind=kind or target["kind"],
        target_raw_byte_count=len(text.encode()),
        admitted=True,
        qualified=True,
        model_origin_verified=True,
        quotient_assignment_id=None,
        class_weights_assigned=False,
        original_public_content_preserved=True,
        original_request_feedback_and_state_preserved=True,
    )


def package(candidates, *, full_record=False):
    rows = [
        {
            "candidate_id": item["id"],
            "representation": original.encode_original_candidate(
                item,
                {"id": "tokenizer:synthetic"},
                SyntheticCharacterTokenizer(),
                maximum_sequence_length=24576,
            ),
        }
        for item in candidates
    ]
    fields = dict(
        task_id="task:synthetic",
        rows=rows,
        whole_package_target_tokens=sum(
            row["representation"]["target_token_count"] for row in rows
        ),
        tokenizer_binding_id="tokenizer:synthetic",
        actual_method="endpoint",
    )
    if full_record:
        return training_runtime.record(
            "encoded_original_package", **fields, consumable=True, errors=[], truncation=False
        )
    return {"package_id": "package:synthetic", **fields}


def teacher_fixture():
    candidates = [
        candidate({"tool": "read_native", "arguments": {"source_id": "source:one"}}, 0),
        candidate({"tool": "calculate", "arguments": {"expression": "1+2"}}, 2),
        candidate(
            {"final": {"value": "3", "explanation": "公开解释", "citations": ["source:one"]}}, 3
        ),
    ]
    return package(candidates), candidates


def test_current_Teacher_schema_binds_full_public_responses_without_mutating_originals():
    value, candidates = teacher_fixture()
    before = encode(value), encode(candidates)
    result = layer.build_package_annotation(value, candidates)
    assert layer.validate_package_annotation(value, result) == result
    assert result["source_authority"] == layer.TEACHER_AUTHORITY
    assert result["profile"] == "public_tf" and result["CPU_only"] is False
    assert result["layer_token_counts"]["reasoning"] == 0
    assert (
        result["layer_token_counts"]["final"]
        == value["rows"][-1]["representation"]["target_token_count"]
    )
    assert result["original_rows_sha256"] == sha(encode(value["rows"]))
    assert result["public_candidates"] == candidates
    assert before == (encode(value), encode(candidates))


def test_full_encoded_original_package_identity_is_verified():
    _, candidates = teacher_fixture()
    value = package(candidates, full_record=True)
    assert layer.validate_package_annotation(
        value, layer.build_package_annotation(value, candidates)
    )
    value["consumable"] = False
    with pytest.raises(ValueError, match="content_identity"):
        layer.build_package_annotation(value, candidates)


def public_update():
    return {
        "kind": "update",
        "state_id": "state:synthetic",
        "observation_id": "obs:one",
        "disposition": "accept",
        "proposed_claim": {"explanation": "public observation handling"},
        "assessment": {
            "relation": "accepts_observed_proposition",
            "observation_refs": ["obs:one"],
            "evidence_refs": [],
            "fulfills_obligation": None,
        },
        "remaining_uncertainty_refs": [],
        "newly_enabled_obligation_ids": [],
        "next_subgoal": "finish",
    }


def public_action():
    return {
        "kind": "action",
        "state_id": "state:synthetic",
        "operation": "read",
        "inputs": [],
        "parameters": {},
        "decision": {
            "obligation_id": "o:one",
            "subgoal": "resolve_evidence",
            "candidate_action_ids": ["a:one"],
            "selected_action_id": "a:one",
            "selection_rule": "dependency_ready",
            "basis": {"relation": "requires", "evidence_refs": [], "claim_refs": []},
            "unresolved_uncertainty_refs": [],
            "expected_effect": {"establishes_obligation": "o:one", "output_schema": "number"},
        },
    }


@pytest.mark.parametrize("first", [public_update, public_action])
def test_old_public_update_and_action_are_tools_never_reasoning(first):
    candidates = [
        candidate(first(), 0, legacy=True),
        candidate(
            {
                "kind": "final",
                "state_id": "state:synthetic",
                "answer_claim_id": "claim:one",
                "result": {"explanation": "Final explanation remains Final"},
                "citations": ["source:one"],
            },
            1,
            legacy=True,
        ),
    ]
    value = package(candidates)
    result = layer.build_package_annotation(value, candidates)
    assert result["source_authority"] == layer.EXPORT_AUTHORITY
    assert (
        result["rows"][0]["layer_masks"]["tools"]
        == value["rows"][0]["representation"]["target_mask"]
    )
    assert result["layer_token_counts"]["reasoning"] == 0
    assert layer.validate_package_annotation(value, result)


@pytest.mark.parametrize(
    "change", ["swap_rows", "drop_row", "change_tokens", "change_package_id", "change_total"]
)
def test_annotation_reopen_rejects_changes_to_original_package(change):
    value, candidates = teacher_fixture()
    result = layer.build_package_annotation(value, candidates)
    if change == "swap_rows":
        value["rows"][:2] = list(reversed(value["rows"][:2]))
    elif change == "drop_row":
        value["rows"].pop(0)
    elif change == "change_tokens":
        value["rows"][0]["representation"]["input_ids"][0] += 1
    elif change == "change_package_id":
        value["package_id"] = "package:another"
    else:
        value["whole_package_target_tokens"] += 1
    with pytest.raises(ValueError):
        layer.validate_package_annotation(value, result)


@pytest.mark.parametrize("change", ["target", "kind", "id", "missing", "extra", "swap", "private"])
def test_candidate_bindings_reject_same_ID_tampering_or_changed_source_inventory(change):
    value, candidates = teacher_fixture()
    if change == "target":
        candidates[0]["target_text"] += " "
    elif change == "kind":
        candidates[0]["response_kind"] = "Final"
    elif change == "id":
        candidates[0]["id"] = candidates[1]["id"]
    elif change == "missing":
        candidates.pop(0)
    elif change == "extra":
        candidates.append(copy.deepcopy(candidates[-1]))
    elif change == "private":
        candidates[0]["reasoning_content"] = "not public assistant content"
    else:
        candidates[:2] = list(reversed(candidates[:2]))
    with pytest.raises(ValueError):
        layer.build_package_annotation(value, candidates)


def test_resigned_misdeclared_kind_is_still_checked_against_raw_JSON():
    _, candidates = teacher_fixture()
    candidates[0]["response_kind"] = "Final"
    candidates[0] = reseal(
        candidates[0],
        lambda **fields: training_runtime.record("original_Teacher_response", **fields),
    )
    value = package(candidates)
    with pytest.raises(ValueError, match="metadata_matches_original_raw"):
        layer.build_package_annotation(value, candidates)


@pytest.mark.parametrize(
    "raw",
    [
        '{"tool":"a","tool":"b","arguments":{}}',
        '{"tool":"a","arguments":{"v":NaN}}',
        "unstructured reasoning",
    ],
)
def test_unknown_duplicate_or_nonfinite_raw_public_content_blocks_package(raw):
    _, candidates = teacher_fixture()
    candidates[0] = candidate(raw, 0, kind="read_native")
    with pytest.raises(ValueError):
        layer.build_package_annotation(package(candidates), candidates)


@pytest.mark.parametrize(
    "field,value",
    [
        ("target_raw_sha256", "0" * 64),
        ("row_id", "candidate:other"),
        ("session_id", "session:other"),
        ("target_character_end", 0),
        ("target_token_start", 0),
        ("suffix_token_count", 1),
        ("causal_shift", 2),
        ("truncated", True),
        ("maximum_sequence_length", 12000),
        ("boundary_checks", {"no_truncation": True}),
        ("prompt_token_count", 1.0),
    ],
)
def test_resigned_representation_field_mismatch_is_not_a_valid_binding(field, value):
    original_package, candidates = teacher_fixture()
    rep = original_package["rows"][0]["representation"]
    rep[field] = value
    original_package["rows"][0]["representation"] = reseal(
        rep, lambda **fields: model_record("token_representation", **fields)
    )
    with pytest.raises(ValueError):
        layer.build_package_annotation(original_package, candidates)


@pytest.mark.parametrize(
    "change", ["reasoning", "overlap", "context", "suffix", "missing_target", "CPU_only"]
)
def test_resigned_sidecar_layers_are_rederived_not_trusted(change):
    value, candidates = teacher_fixture()
    result = layer.build_package_annotation(value, candidates)
    masks = result["rows"][0]["layer_masks"]
    target = value["rows"][0]["representation"]["target_token_start"]
    if change == "reasoning":
        masks["reasoning"], masks["tools"] = masks["tools"], masks["reasoning"]
    elif change == "overlap":
        masks["final"][target] = 1
    elif change == "context":
        masks["tools"][0] = 1
    elif change == "suffix":
        masks["tools"][-1] = 1
    elif change == "missing_target":
        masks["tools"][target] = 0
    else:
        result["CPU_only"] = True
    result = reseal(result, lambda **fields: record(layer.ANNOTATION_KIND, **fields))
    with pytest.raises(ValueError, match="recomputed"):
        layer.validate_package_annotation(value, result)


def test_missing_tools_blocks_complete_package_instead_of_dropping_it():
    _, candidates = teacher_fixture()
    candidates = candidates[-1:]
    with pytest.raises(ValueError, match="missing_required_layer"):
        layer.build_package_annotation(package(candidates), candidates)


def test_synthetic_RTF_masks_are_explicit_and_can_never_pass_as_original_public_authority():
    value, _ = teacher_fixture()
    result = layer.build_synthetic_package_annotation(value, ["reasoning", "tools", "final"])
    assert result["CPU_only"] is True and result["synthetic"] is True
    assert result["source_authority"] == layer.SYNTHETIC_AUTHORITY
    assert all(count > 0 for count in result["layer_token_counts"].values())
    assert layer.validate_package_annotation(value, result)
    result["CPU_only"] = False
    result = reseal(result, lambda **fields: record(layer.ANNOTATION_KIND, **fields))
    with pytest.raises(ValueError):
        layer.validate_package_annotation(value, result)


def test_synthetic_per_token_masks_preserve_true_row_order_and_context():
    value, _ = teacher_fixture()
    rows = value["rows"][:1]
    value["rows"] = rows
    value["whole_package_target_tokens"] = rows[0]["representation"]["target_token_count"]
    target = rows[0]["representation"]["target_mask"]
    active = [i for i, selected in enumerate(target) if selected]
    masks = {name: [0] * len(target) for name in layer.LAYERS}
    masks["reasoning"][active[0]] = 1
    masks["final"][active[-1]] = 1
    for i in active[1:-1]:
        masks["tools"][i] = 1
    result = layer.build_synthetic_package_annotation(value, [masks])
    assert layer.validate_package_annotation(value, result)
    assert sum(result["layer_token_counts"].values()) == sum(target)


def test_validator_does_not_load_or_invoke_a_tokenizer(monkeypatch):
    value, candidates = teacher_fixture()

    def forbidden(*args, **kwargs):
        pytest.fail("sidecar must not encode or load tokens")

    monkeypatch.setattr(original, "encode_original_candidate", forbidden)
    monkeypatch.setattr(original.frozen_tokenizer_assets, "load_tokenizer", forbidden)
    result = layer.build_package_annotation(value, candidates)
    assert layer.validate_package_annotation(value, result)


def test_reordering_both_candidates_and_rows_cannot_reorder_original_time():
    _, candidates = teacher_fixture()
    candidates[:2] = list(reversed(candidates[:2]))
    with pytest.raises(ValueError, match="temporal_order"):
        layer.build_package_annotation(package(candidates), candidates)


@pytest.mark.parametrize("change", ["mixed_tokenizer", "wrong_package_tokenizer", "wrong_method"])
def test_original_tokenizer_and_method_contract_cannot_be_mixed(change):
    value, candidates = teacher_fixture()
    if change == "mixed_tokenizer":
        rep = value["rows"][0]["representation"]
        rep["tokenizer_binding_id"] = "tokenizer:other"
        value["rows"][0]["representation"] = reseal(
            rep, lambda **fields: model_record("token_representation", **fields)
        )
    elif change == "wrong_package_tokenizer":
        value["tokenizer_binding_id"] = "tokenizer:other"
    else:
        value["actual_method"] = "aggregate"
    with pytest.raises(ValueError):
        layer.build_package_annotation(value, candidates)


def test_resigned_embedded_candidate_cannot_rebind_original_encoded_row():
    value, candidates = teacher_fixture()
    result = layer.build_package_annotation(value, candidates)
    candidate = result["public_candidates"][0]
    candidate["target_text"] += " "
    candidate["target_raw_sha256"] = sha(candidate["target_text"])
    result["public_candidates"][0] = reseal(
        candidate, lambda **fields: training_runtime.record("original_Teacher_response", **fields)
    )
    result = reseal(result, lambda **fields: record(layer.ANNOTATION_KIND, **fields))
    with pytest.raises(ValueError, match="no_reorder_drop_or_add"):
        layer.validate_package_annotation(value, result)


def test_synthetic_RTF_missing_layer_blocks_not_renormalizes_or_drops_rows():
    value, _ = teacher_fixture()
    before = encode(value)
    with pytest.raises(ValueError, match="missing_required_layer"):
        layer.build_synthetic_package_annotation(value, ["tools", "tools", "final"])
    assert encode(value) == before


def test_content_addressed_unknown_candidate_schema_cannot_become_public_reasoning():
    value, candidates = teacher_fixture()
    candidates[0] = record(
        "invented_public_reasoning",
        **{key: item for key, item in candidates[0].items() if key not in {"id", "schema_version"}},
    )
    value = package(candidates)
    with pytest.raises(ValueError, match="unknown_public_source_authority"):
        layer.build_package_annotation(value, candidates)
