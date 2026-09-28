"""Finite semantic alignment CPU controls, not model correctness/independence claims."""

import copy
import json
from types import SimpleNamespace

import pytest
from test_finance_semantic_review import (
    fixture_bundle,
    fixture_review,
    mechanical,
    revision_fixture,
)

from trusted_synthesis.finance_research.contracts import digest
from trusted_synthesis.finance_research.semantic_review import (
    SlotReview,
    Term,
    _meaning_terms,
    _validate_slot,
    document_index,
)
from trusted_synthesis.finance_research.v6_state_alignment import (
    PAIR_KEYS,
    alignment_request,
    inspect_alignment,
    resolve_decomposed_pair,
    validate_alignment,
)


def prepared_fixture():
    return {
        "bundle": fixture_bundle(),
        "mechanical": mechanical(),
        "requests": [{"DO_NOT_SEND_OTHER_REVIEWER": "secret-independent-review"}],
    }


def slot_reviews_fixture(
    prepared, reviewer=0, *, different_words=False, derivation=False, authored=None
):
    bundle = prepared["bundle"]
    docs = document_index(bundle)
    authored = copy.deepcopy(authored) if authored is not None else fixture_review(bundle, reviewer)
    if different_words:
        authored["terms"][0]["subject"] = "reporting entity, not the other reviewer's phrasing"
    terms = _meaning_terms(
        SimpleNamespace(terms=[Term.model_validate(t) for t in authored["terms"]]), docs
    )
    result = {}
    for slot in authored["slots"]:
        if derivation:
            node = copy.deepcopy(slot["semantic_graph"]["nodes"][0])
            node.update(node_id="d", predicate="derivation", operation="add")
            slot["semantic_graph"]["nodes"].append(node)
            slot["semantic_graph"]["edges"].append(
                {
                    "from_node": "d",
                    "to_node": "n",
                    "relation": "derives",
                    "evidence": node["evidence"],
                }
            )
        derived = _validate_slot(SlotReview.model_validate(slot), docs, terms)
        result[slot["slot_id"]] = {
            "reviewer": reviewer,
            "task_id": bundle["task_id"],
            "slot_id": slot["slot_id"],
            "task_bundle_sha256": digest(bundle),
            "v_trace": "valid",
            "reported_v_trace": "valid",
            "interface_admitted": True,
            "semantic_consistent": True,
            "parsed": {"terms": copy.deepcopy(authored["terms"]), "slot": slot},
            "terms": terms,
            "derived": derived,
            "raw_review_sha256": digest({"slot": slot, "reviewer": reviewer}),
        }
    return result


def alignment_fixture(request):
    by_slot = {}
    for eid, item in request["document_catalog"].items():
        if item["kind"] == "public_content":
            by_slot.setdefault(item["slot_id"], eid)
    own = set(request["own_eligible_slot_ids"])
    aliases = request["compact_catalog"]["slot_aliases"]
    pairs = {}
    for key in PAIR_KEYS:
        left, right = key.split("_")
        applicable = aliases[left] in own and aliases[right] in own
        pairs[key] = {
            "relation": "equivalent" if applicable else "not_applicable",
            "basis": "same_semantic_process" if applicable else "not_applicable",
            "left_nodes": ["n"] if applicable else [],
            "right_nodes": ["n"] if applicable else [],
            "evidence": [by_slot[left], by_slot[right]] if applicable else [],
            "semantic_basis": "Same accepted revenue and answer path; wording is immaterial."
            if applicable
            else "",
            "accepted_answer_path_relation": "same" if applicable else "unknown",
            "surface_or_redundant_only": "yes" if applicable else "unknown",
        }
    return {"pairs": pairs}


def setup(*, different_words=False, derivation=False):
    prepared = prepared_fixture()
    sides = [
        slot_reviews_fixture(
            prepared, r, different_words=different_words and r == 1, derivation=derivation
        )
        for r in (0, 1)
    ]
    requests = [alignment_request(prepared, sides[r], r) for r in (0, 1)]
    values = [alignment_fixture(request) for request in requests]
    return prepared, sides, requests, values


def resolved(prepared, sides, requests, values):
    alignments = [validate_alignment(json.dumps(values[r]), requests[r]) for r in (0, 1)]
    return resolve_decomposed_pair(prepared, *sides, *alignments)


def test_equal_semantics_do_not_require_identical_free_form_graph_words():
    prepared, sides, requests, values = setup(different_words=True)
    assert sides[0]["s0"]["derived"]["graph"] != sides[1]["s0"]["derived"]["graph"]
    result = resolved(prepared, sides, requests, values)
    assert result["task_mapping"] == "complete"
    assert result["valid_slots_retained"] == [f"s{i}" for i in range(8)]
    assert {slot["state_id"] for slot in result["slots"].values()} == {"z0"}
    assert (
        result["state_definitions"]["z0"]["per_slot_review_terms"]["s0"][0]
        != result["state_definitions"]["z0"]["per_slot_review_terms"]["s0"][1]
    )
    assert all(
        slot["mask_status"] == "agreed" and slot["encoding_manifest"]
        for slot in result["slots"].values()
    )
    assert (
        not result["mathematical_proof"]
        and not result["same_model_reviews_statistically_independent"]
    )


def test_request_has_only_own_compact_judgments_and_each_original_public_fragment_once():
    prepared, sides, requests, _ = setup()
    sides[1]["s0"]["OTHER_REVIEWER_SECRET"] = "forbidden-other-side"
    payload = json.loads(requests[0]["messages"][1]["content"])
    assert "secret-independent-review" not in json.dumps(payload)
    assert "forbidden-other-side" not in json.dumps(payload)
    assert "review_only_private_reference" not in payload
    assert "output_schema" not in payload and "strict_tool" not in payload
    assert len(payload["own_slot_judgments"]) == 8
    for judgment in payload["own_slot_judgments"].values():
        assert not {"document_index", "raw_review_sha256", "mask", "request"} & set(judgment)
        assert isinstance(judgment["semantic_graph"]["nodes"][0]["evidence"][0], str)
        assert judgment["semantic_graph"]["nodes"][0]["evidence"][0].startswith("e")
    assert all(key == f"e{i}" for i, key in enumerate(payload["document_catalog"]))
    parameters = requests[0]["strict_tool"]["function"]["parameters"]
    assert set(parameters["properties"]["pairs"]["properties"]) == set(PAIR_KEYS)
    assert not requests[0]["other_reviewer_output_visible"]


@pytest.mark.parametrize(
    "mutation",
    [
        "missing_pair",
        "extra_pair",
        "bad_eid",
        "cross_slot",
        "bad_node",
        "duplicate_json",
        "other_reviewer",
    ],
)
def test_bad_shape_or_actual_id_is_mechanical_interface_failure(mutation):
    _, _, requests, values = setup()
    request, value = requests[0], values[0]
    pair = value["pairs"]["s0_s1"]
    if mutation == "missing_pair":
        value["pairs"].pop("s0_s1")
    elif mutation == "extra_pair":
        value["pairs"]["s1_s0"] = copy.deepcopy(pair)
    elif mutation == "bad_eid":
        pair["evidence"] = ["e-does-not-exist"]
    elif mutation == "cross_slot":
        pair["evidence"] = values[0]["pairs"]["s2_s3"]["evidence"]
    elif mutation == "bad_node":
        pair["left_nodes"] = ["not_a_real_node"]
    elif mutation == "other_reviewer":
        request["own_slot_reviews"]["s0"]["reviewer"] = 1
    raw = '{"pairs":{},"pairs":{}}' if mutation == "duplicate_json" else json.dumps(value)
    assessed = inspect_alignment(raw, request)
    assert not assessed["interface_admitted"] and assessed["validation"] is None


@pytest.mark.parametrize(
    "mutation",
    ["unknown", "drop_eligible", "surface_distinction", "one_side_evidence", "unaccepted_node"],
)
def test_semantic_unknown_is_valid_interface_and_whole_task_mapping_stays_incomplete(mutation):
    prepared, sides, requests, values = setup()
    if mutation == "unaccepted_node":
        for reviewer in (0, 1):
            node = copy.deepcopy(
                sides[reviewer]["s0"]["parsed"]["slot"]["semantic_graph"]["nodes"][0]
            )
            node.update(node_id="unaccepted", accepted=False)
            sides[reviewer]["s0"]["parsed"]["slot"]["semantic_graph"]["nodes"].append(node)
            requests[reviewer] = alignment_request(prepared, sides[reviewer], reviewer)
            values[reviewer] = alignment_fixture(requests[reviewer])
    for value in values:
        pair = value["pairs"]["s0_s1"]
        if mutation == "unknown":
            pair.update(relation="unknown", basis="unresolved")
        elif mutation == "drop_eligible":
            pair.update(relation="not_applicable", basis="not_applicable")
        elif mutation == "surface_distinction":
            pair.update(
                relation="distinct",
                basis="derivation",
                semantic_basis="Only tool count differs.",
                accepted_answer_path_relation="same",
                surface_or_redundant_only="yes",
            )
        elif mutation == "one_side_evidence":
            pair["evidence"] = pair["evidence"][:1]
        elif mutation == "unaccepted_node":
            pair["left_nodes"] = ["unaccepted"]
    assessments = [inspect_alignment(json.dumps(values[r]), requests[r]) for r in (0, 1)]
    assert all(item["interface_admitted"] for item in assessments)
    result = resolve_decomposed_pair(
        prepared, *sides, *(item["validation"] for item in assessments)
    )
    assert result["task_mapping"] == "incomplete" and len(result["valid_slots_retained"]) == 8
    assert all(
        slot["mapper"] == "unknown" and slot["state_id"] is None
        for slot in result["slots"].values()
    )


def distinguish(pair):
    pair.update(
        relation="distinct",
        basis="derivation",
        left_nodes=["d"],
        right_nodes=["d"],
        semantic_basis="Different material accepted derivations contribute to the answer.",
        accepted_answer_path_relation="substantively_different",
        surface_or_redundant_only="no",
    )


def test_equivalence_transitivity_is_required_even_when_both_reviewers_repeat_bad_partition():
    prepared, sides, requests, values = setup(derivation=True)
    for value in values:
        distinguish(value["pairs"]["s0_s2"])
    result = resolved(prepared, sides, requests, values)
    assert result["task_mapping"] == "incomplete"
    assert any(error["reason"] == "nontransitive_equivalence" for error in result["mapping_errors"])
    assert len(result["valid_slots_retained"]) == 8


def test_material_distinction_gives_stable_task_local_classes_not_wording_hashes():
    prepared, sides, requests, values = setup(derivation=True)
    for value in values:
        for key, pair in value["pairs"].items():
            if key.startswith("s0_"):
                distinguish(pair)
    result = resolved(prepared, sides, requests, values)
    assert result["task_mapping"] == "complete"
    assert result["slots"]["s0"]["state_id"] == "z0"
    assert {result["slots"][f"s{i}"]["state_id"] for i in range(1, 8)} == {"z1"}


def test_q_v_mapper_separate_and_own_request_never_reveals_other_side_eligibility():
    prepared, sides, _, _ = setup()
    prepared["mechanical"]["s0"]["native_correct"] = False
    sides[1]["s1"].update(v_trace="unknown", derived=None)
    requests = [alignment_request(prepared, sides[r], r) for r in (0, 1)]
    assert "s1" in requests[0]["own_eligible_slot_ids"]
    assert "s1" not in requests[1]["own_eligible_slot_ids"]
    values = [alignment_fixture(request) for request in requests]
    result = resolved(prepared, sides, requests, values)
    assert result["task_mapping"] == "complete"
    assert (
        result["slots"]["s0"]["q_native"] is False and result["slots"]["s0"]["v_trace"] == "valid"
    )
    assert result["slots"]["s0"]["mapper"] == "not_applicable"
    assert (
        result["slots"]["s1"]["v_trace"] == "unknown"
        and result["slots"]["s1"]["encoding_manifest"] is None
    )
    assert result["valid_slots_retained"] == [f"s{i}" for i in range(2, 8)]


def test_all_unknown_original_placeholders_allow_28_not_applicable_without_fake_graphs():
    prepared, sides, _, _ = setup()
    for side in sides:
        for item in side.values():
            item.update(v_trace="unknown", parsed=None, derived=None, interface_admitted=False)
    requests = [alignment_request(prepared, sides[r], r) for r in (0, 1)]
    result = resolved(prepared, sides, requests, [alignment_fixture(r) for r in requests])
    assert result["valid_slots_retained"] == [] and result["task_mapping"] == "incomplete"
    assert len(result["slots"]) == 8


def test_singleton_can_be_mechanically_mapped_without_alignment_api():
    prepared, sides, _, _ = setup()
    for sid in list(prepared["mechanical"])[1:]:
        prepared["mechanical"][sid]["native_correct"] = False
    result = resolve_decomposed_pair(prepared, *sides, None, None)
    assert result["task_mapping"] == "complete" and result["valid_slots_retained"] == ["s0"]
    assert result["slots"]["s0"]["state_id"] == "z0" and result["alignment_called"] == [
        False,
        False,
    ]


def test_equivalence_class_must_preserve_chi_and_all_eligible_packages():
    prepared, sides, requests, values = setup()
    for side in sides:
        side["s0"]["derived"]["chi"] = 1
    requests = [alignment_request(prepared, sides[r], r) for r in (0, 1)]
    result = resolved(prepared, sides, requests, values)
    assert result["task_mapping"] == "incomplete"
    assert any(
        error["reason"] == "chi_inconsistent_in_equivalence_class"
        for error in result["mapping_errors"]
    )
    assert len(result["valid_slots_retained"]) == 8


def test_retracted_mask_stays_zero_and_is_not_deleted_or_promoted_by_mapping():
    bundle, authored = revision_fixture()
    prepared = {"bundle": bundle, "mechanical": mechanical()}
    sides = [slot_reviews_fixture(prepared, reviewer, authored=authored) for reviewer in (0, 1)]
    requests = [alignment_request(prepared, sides[r], r) for r in (0, 1)]
    result = resolved(prepared, sides, requests, [alignment_fixture(r) for r in requests])
    item = result["slots"]["s0"]
    assert (
        next(row for row in item["positive_target_mask"] if row["doc_id"].endswith("/prior"))[
            "label"
        ]
        == "retracted"
    )
    assert all(
        row["original_segment_id"] != "prior"
        for row in item["encoding_manifest"]["positive_content_spans"]
    )
    assert item["encoding_manifest"]["positive_action_ids"] == ["a0", "run0"]
    assert item["chi"] == 1


def test_two_semantically_valid_but_disagreeing_partitions_do_not_drop_any_package():
    prepared, sides, requests, values = setup(derivation=True)
    for key, pair in values[1]["pairs"].items():
        if key.startswith("s0_"):
            distinguish(pair)
    result = resolved(prepared, sides, requests, values)
    assert result["task_mapping"] == "incomplete" and len(result["valid_slots_retained"]) == 8
    assert any(
        error["reason"] == "pair_unknown_or_disagreement" for error in result["mapping_errors"]
    )


def test_failed_alignment_interface_is_retained_and_blocks_nontrivial_mapping():
    prepared, sides, requests, values = setup()
    bad = inspect_alignment('{"pairs":{}}', requests[0])
    good = validate_alignment(json.dumps(values[1]), requests[1])
    result = resolve_decomposed_pair(prepared, *sides, bad, good)
    assert result["task_mapping"] == "incomplete" and len(result["valid_slots_retained"]) == 8
    assert all(row["mapper"] == "unknown" for row in result["slots"].values())
