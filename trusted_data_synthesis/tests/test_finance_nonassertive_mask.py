"""Future zero-loss empty-Q class: no old records, paid APIs or GPU are used."""

import json

import pytest
from test_finance_semantic_review import fixture_bundle, fixture_review
from test_finance_v6_slot_review import encoded_fixture, setup

from trusted_synthesis.finance_research.contracts import digest
from trusted_synthesis.finance_research.semantic_review import (
    RUBRIC,
    NonassertiveSlotReview,
    TaskReview,
    _canonical_mask,
    _encoding_manifest,
    _validate_slot,
    is_nonassertive_context_fragment,
)
from trusted_synthesis.finance_research.v6_slot_review import (
    SlotOutput,
    inspect_slot_review,
    slot_review_request,
    slot_rubric,
    validate_slot_review,
)


def fixture(text="Q: None.", label="nonassertive_context"):
    bundle = fixture_bundle()
    bundle["slots"][0]["trajectory"]["segments"].append(
        dict(
            segment_id="empty-q",
            kind="public_content",
            text=text,
            start=0,
            end=len(text),
            turn_index=0,
        )
    )
    request = slot_review_request(bundle, "s0", {"answer": 120}, 0)
    output = encoded_fixture(request, fixture_review(bundle))
    target = next(
        eid
        for eid, row in request["document_catalog"].items()
        if row["kind"] == "public_content" and row["text"] == text
    )
    output["mask"][target] = dict(label=label, proposition_ids=[])
    return request, output, target


def test_old_schema_and_rubric_hashes_unchanged():
    request, _ = setup()
    assert (
        digest(TaskReview.model_json_schema())
        == "290b2c44b70cf085a44e64a805b779a095eb399637ac4171bc7dc37c24e5d2cf"
    )
    assert (
        digest(SlotOutput.model_json_schema())
        == "8272a54ca1a8da70c88b121d169479a623f300a6a4dde0b0ed6a4f499a37dc5d"
    )
    assert digest(RUBRIC) == "e5b7630bfd5fa86c188a192f6829f1ac9fca2a14f7baab69e4ce00b1f81a13df"
    assert (
        digest(slot_rubric(0)) == "065133e2d098a9ff08f37609b07cf782beb6159c32fd74aac0c8813dfb19f03e"
    )
    assert (
        digest(request["strict_tool"])
        == "3a1d2f9571e192d45e9eec1b718ff9bc7ac4eb931d4a18abd3fa1f7d6016f037"
    )


def test_new_empty_Q_label_requires_opt_in_retains_original_and_has_zero_target():
    request, output, _ = fixture()
    raw = json.dumps(output)
    assert not inspect_slot_review(raw, request)["interface_admitted"]
    checked = validate_slot_review(raw, request, allow_nonassertive_context=True)
    assert checked["v_trace"] == "valid" and checked["semantic_consistent"]
    assert (
        checked["derived"]["mask_complete"] and checked["requires_second_review_and_task_alignment"]
    )
    slot = checked["parsed"]["slot"]
    span = next(row for row in slot["mask"] if row["label"] == "nonassertive_context")
    assert span["quote"] == "Q: None." and span["proposition_ids"] == []
    canonical = _canonical_mask(NonassertiveSlotReview.model_validate(slot).mask)
    manifest = _encoding_manifest("s0", slot, slot, canonical, request["document_index"])
    assert all(row["quote"] != "Q: None." for row in manifest["positive_content_spans"])
    assert manifest["positive_action_ids"] == ["a0"]
    with pytest.raises(ValueError, match="explicit future opt-in"):
        _validate_slot(
            NonassertiveSlotReview.model_validate(slot), request["document_index"], checked["terms"]
        )


@pytest.mark.parametrize("text", ["Q: None.", " q: none ", "Q:N/A", "Q: N/A.", " Q : None.\t"])
def test_finite_empty_optional_field_whitelist(text):
    assert is_nonassertive_context_fragment(text)
    request, output, _ = fixture(text)
    assert validate_slot_review(json.dumps(output), request, allow_nonassertive_context=True)[
        "semantic_consistent"
    ]


@pytest.mark.parametrize(
    "text",
    [
        "Q: Revenue is 120.",
        "Q: Verified.",
        "Q: No errors.",
        "U: None.",
        "None.",
        "I will calculate.",
        "Q: None, revenue is 900.",
        "Q: unresolved errors",
        "Q: N o n e",
    ],
)
def test_facts_actions_narration_and_uncertainty_are_not_empty_optional_fields(text):
    assert not is_nonassertive_context_fragment(text)
    request, output, _ = fixture(text)
    checked = inspect_slot_review(json.dumps(output), request, allow_nonassertive_context=True)
    assert checked["interface_admitted"] and not checked["semantic_consistent"]
    assert checked["validation"]["v_trace"] == "unknown"
    assert checked["validation"]["positive_target_mask"] is None


@pytest.mark.parametrize(
    "mutation", ["action", "proposition", "approved_empty", "unknown", "critical_contradiction"]
)
def test_opt_in_does_not_promote_actions_claims_or_unknowns(mutation):
    request, output, target = fixture()
    if mutation == "action":
        action = next(iter(output["actions"]))
        output["mask"][action] = dict(label="nonassertive_context", proposition_ids=[])
    elif mutation == "proposition":
        output["mask"][target]["proposition_ids"] = ["p"]
    elif mutation == "approved_empty":
        output["mask"][target]["label"] = "approved"
    elif mutation == "unknown":
        output["mask"][target]["label"] = "unknown"
    else:
        output["propositions"][0]["judgment"] = "unknown"
    value = validate_slot_review(json.dumps(output), request, allow_nonassertive_context=True)
    if mutation == "unknown":
        assert value["semantic_consistent"] and not value["derived"]["mask_complete"]
        assert value["parsed"]["slot"]["mask"][-1]["label"] == "unknown"
    else:
        assert not value["semantic_consistent"] and value["v_trace"] == "unknown"
        assert value["positive_target_mask"] is None
