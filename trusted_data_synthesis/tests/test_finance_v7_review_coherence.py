"""Synthetic existing-rule controls; no real reviews, Base results or API calls."""

import copy
import json

import pytest
from test_finance_semantic_review import fixture_bundle, fixture_review, quote, revision_fixture
from test_finance_v7_slot_review import typed_fixture

from trusted_synthesis.finance_research import v7_review_coherence as policy
from trusted_synthesis.finance_research.contracts import digest
from trusted_synthesis.finance_research.semantic_review import document_index
from trusted_synthesis.finance_research.v7_mask_review import (
    inspect_slot_review,
    slot_review_request,
)


def verified_fixture():
    bundle, authored = revision_fixture()
    # Original observation really changes an explicitly withdrawn wrong claim.
    # This fixture tests an evidenced verification, not an extra forced model step.
    for slot in authored["slots"]:
        slot["updates"][0]["kind"] = "verification"
        slot["semantic_graph"]["nodes"][1]["predicate"] = "verification"
    return bundle, authored


def inspect_authored(bundle, authored):
    request = slot_review_request(bundle, "s0", {"program": "add(120, 0)", "answer": 120}, 0)
    raw = json.dumps(typed_fixture(request["typed_baseline_request"], authored))
    inspection = inspect_slot_review(raw, request)
    return raw, inspection


def test_legitimate_evidenced_verification_survives_original_rules_with_chi_one():
    bundle, authored = verified_fixture()
    _, inspected = inspect_authored(bundle, authored)
    assert inspected["interface_admitted"] and inspected["semantic_consistent"]
    result = inspected["validation"]
    assert result["v_trace"] == "valid" and result["derived"]["chi"] == 1
    assert result["derived"]["mapping_established"]
    before = digest(result["parsed"])
    diagnostic = policy.update_coherence_diagnostics(
        result["parsed"]["slot"], result["document_index"]
    )
    assert diagnostic["updates"][0]["reported_substantive"] is True
    assert diagnostic["updates"][0]["violations"] == []
    assert digest(result["parsed"]) == before
    assert diagnostic["chi_not_recomputed_here"] and diagnostic["no_model_label_changed"]


@pytest.mark.parametrize(
    "mutation,violation",
    [
        ("decision_none", "substantive_true_but_decision_change_none"),
        ("posterior_noncritical", "substantive_posterior_not_critical"),
        ("posterior_unaccepted", "substantive_posterior_not_accepted"),
        ("missing_action", "substantive_missing_named_action_or_observation_citation"),
        ("missing_observation", "substantive_missing_named_action_or_observation_citation"),
        ("missing_nonredundancy", "missing_evidence_or_nonredundancy_evidence"),
    ],
)
def test_r5_cross_field_contradictions_stay_unknown_without_host_repair(mutation, violation):
    bundle, authored = verified_fixture()
    slot = authored["slots"][0]
    update = slot["updates"][0]
    if mutation == "decision_none":
        update["decision_change"] = "none"
    elif mutation == "posterior_noncritical":
        slot["propositions"][0]["critical"] = False
    elif mutation == "posterior_unaccepted":
        slot["propositions"][0]["accepted"] = False
    elif mutation in {"missing_action", "missing_observation"}:
        field = "action_doc_id" if mutation == "missing_action" else "observation_doc_id"
        update["evidence"] = [e for e in update["evidence"] if e["doc_id"] != update[field]]
    elif mutation == "missing_nonredundancy":
        update["nonredundancy_evidence"] = []
    authored_before = digest(authored)
    _, inspected = inspect_authored(bundle, authored)
    assert inspected["interface_admitted"] and not inspected["semantic_consistent"]
    result = inspected["validation"]
    assert result["reported_v_trace"] == result["parsed"]["slot"]["v_trace"] == "valid"
    assert result["v_trace"] == "unknown" and result["derived"] is None
    assert result["positive_target_mask"] is None
    assert result["parsed"]["slot"]["updates"][0]["substantive"] is True
    diagnostic = policy.update_coherence_diagnostics(
        result["parsed"]["slot"], result["document_index"]
    )
    assert violation in diagnostic["updates"][0]["violations"]
    assert digest(authored) == authored_before
    assert not result["host_mask_repair"]


def test_truthfully_nonsubstantive_step_remains_possible_without_fabricated_chi():
    bundle = fixture_bundle()
    authored = fixture_review(bundle)
    docs = document_index(bundle)
    for slot in authored["slots"]:
        sid = slot["slot_id"]
        action, observation = f"slot/{sid}/arguments", f"slot/{sid}/observation"
        slot["updates"] = [
            dict(
                kind="repetition",
                prior_proposition="p",
                posterior_proposition="p",
                action_doc_id=action,
                observation_doc_id=observation,
                decision_change="none",
                substantive=False,
                evidence=[quote(docs, action), quote(docs, observation)],
                nonredundancy_evidence=[],
            )
        ]
    _, inspected = inspect_authored(bundle, authored)
    assert inspected["semantic_consistent"]
    result = inspected["validation"]
    assert result["v_trace"] == "valid" and result["derived"]["chi"] == 0
    assert result["derived"]["mapping_established"]
    diagnostic = policy.update_coherence_diagnostics(
        result["parsed"]["slot"], result["document_index"]
    )
    assert diagnostic["updates"][0]["reported_substantive"] is False
    assert not diagnostic["updates"][0]["violations"]


def test_flipping_false_does_not_make_an_accepted_verification_graph_mapped():
    bundle, authored = verified_fixture()
    authored["slots"][0]["updates"][0]["substantive"] = False
    _, inspected = inspect_authored(bundle, authored)
    result = inspected["validation"]
    assert result["derived"]["chi"] == 0
    assert result["derived"]["mapping_established"] is False
    assert result["parsed"]["slot"]["updates"][0]["substantive"] is False


def test_no_nonsubstantive_label_excuses_an_unresolved_critical_claim():
    bundle, authored = verified_fixture()
    authored["slots"][0]["updates"][0]["substantive"] = False
    authored["slots"][0]["propositions"][0]["judgment"] = "unknown"
    _, inspected = inspect_authored(bundle, authored)
    assert inspected["interface_admitted"] and not inspected["semantic_consistent"]
    assert inspected["validation"]["v_trace"] == "unknown"
    assert inspected["validation"]["positive_target_mask"] is None


def test_policy_is_pure_balanced_clarification_not_a_paid_factory_or_data_tuned_rule():
    metadata = policy.coherence_constraints()
    assert metadata["clarification_only"] and metadata["genuine_substantive_updates_remain_allowed"]
    assert (
        not metadata["host_semantic_label_changes"]
        and not metadata["uses_Base_or_development_results"]
    )
    assert not metadata["automatic_paid_calls"] and not metadata["automatic_expansion"]
    cohort = metadata["initial_engineering_scope"]
    assert cohort["tasks"] * len(cohort["isolated_reviewers"]) == cohort["maximum_calls"] == 12
    assert cohort["slot_index"] == 0 and not cohort["old_success_reuse"]
    assert "Neither label is preferred" in policy.COHERENCE_APPENDIX
    assert "You MAY truthfully report" in policy.COHERENCE_APPENDIX
    assert "SHOULD retain substantive=true" in policy.COHERENCE_APPENDIX
    assert not hasattr(policy, "slot_review_request") and not hasattr(policy, "WIRE_PROTOCOL")


def test_read_only_diagnostic_preserves_both_parsed_graph_and_document_index():
    bundle, authored = verified_fixture()
    slot, docs = copy.deepcopy(authored["slots"][0]), document_index(bundle)
    before = digest(dict(slot=slot, docs=docs))
    result = policy.update_coherence_diagnostics(slot, docs)
    assert result["diagnostic_only"] and result["semantic_verdict_not_replaced"]
    assert digest(dict(slot=slot, docs=docs)) == before
