"""Compact prospective annotation controls; synthetic original episodes, no API."""

import copy
import json

import pytest
from test_finance_public_reasoning import call, mocked_episode
from test_finance_research_datasets import finqa_record

from trusted_synthesis.finance_research import v10_process_review as review
from trusted_synthesis.finance_research.contracts import digest
from trusted_synthesis.finance_research.datasets import adapt_finqa


def fixture(content="8 minus 2 equals 6. Let me inspect the public table first."):
    task = adapt_finqa([finqa_record()], split="train", revision="v10-compact-CPU")[0]
    episode, _ = mocked_episode(
        task, [(content, [call("submit_program", {"program": "subtract(8, 2)"})])]
    )
    native = dict(
        native=dict(execution_accuracy=1.0, program_accuracy=0.0),
        status="scored",
        private_author_answer="not-for-process-model",
    )
    request = review.prepare_process_request(
        episode,
        slot_id="synthetic-slot",
        native_result=native,
        integrity={k: True for k in review.INTEGRITY_CHECKS},
    )
    documents = request["trajectory"]["segments"]
    content_doc = next(d for d in documents if d["kind"] == "public_content")
    action_doc = next(d for d in documents if d["kind"] == "action_arguments")
    source = next(d for d in documents if d["kind"] in {"source_text", "source_table_cell"})

    def location(doc, start=0, end=None):
        end = len(doc["text"]) if end is None else end
        return dict(
            segment_id=doc["segment_id"], start=start, end=end, quote=doc["text"][start:end]
        )

    end = content.index(".") + 1
    body = dict(
        process=dict(
            evidence_and_operations=dict(
                status="supported",
                summary="Uses the visible 8 and 2.",
                evidence=[location(source), location(content_doc, 0, end)],
            ),
            observation_interpretation=dict(
                status="not_applicable", summary="Direct submission.", evidence=[]
            ),
            unwithdrawn_critical_contradictions=dict(
                status="supported", summary="No critical unwithdrawn contradiction.", evidence=[]
            ),
            actual_revisions=dict(
                status="not_applicable", summary="No revision was required.", evidence=[]
            ),
        ),
        behavior=dict(
            description="Direct subtraction grounded in the initial public table.",
            evidence=[location(content_doc, 0, end), location(action_doc)],
        ),
        supervision=[
            dict(
                **location(content_doc, 0, end), decision="positive", reason="Reviewed derivation."
            ),
            dict(
                **location(content_doc, end, len(content)),
                decision="context_only",
                reason="Ordinary procedural narration, no finite English whitelist.",
            ),
            dict(**location(action_doc), decision="positive", reason="Reviewed actual submission."),
        ],
    )
    return episode, request, body


def inspect(request, body):
    return review.inspect_process_review(json.dumps(body), request)


def test_compact_direct_solution_no_regex_graph_dual_review_or_private_reference():
    episode, request, body = fixture()
    result = inspect(request, body)
    assert result["review_status"] == "annotation_succeeded"
    assert result["process_validity"] == "valid"
    assert result["semantic_truth_proved"] is False
    assert result["annotation_origin"] == "offline_candidate_contract_not_production_evidence"
    assert "not-for-process-model" not in json.dumps(request["messages"])
    assert request["native_result"]["native"]["program_accuracy"] == 0
    schema = request["strict_tool"]["function"]["parameters"]["properties"]
    assert set(schema) == {"process", "behavior", "supervision"}
    assert not {"terms", "nodes", "edges", "propositions", "targets"} & set(schema)
    manifest = review.supervision_manifest(result)
    assert review.validate_manifest(episode, manifest) == manifest
    assert len(manifest["positive_content_spans"]) == len(manifest["positive_action_ids"]) == 1
    assert manifest["positive_content_spans"][0]["quote"] == "8 minus 2 equals 6."
    assert "mask_agreement" not in manifest
    assert manifest["not_a_TokenReceipt"] and not manifest["training_material_admitted"]
    assert not manifest["actual_model_call_receipt_verified"]


def test_annotation_failure_is_not_a_financial_counterexample():
    _, request, body = fixture()
    body["process"]["evidence_and_operations"]["evidence"][0]["quote"] = "invented citation"
    failed = inspect(request, body)
    assert failed["review_status"] == "annotation_failed"
    assert failed["process_validity"] == "unknown"
    assert "exact original" in failed["annotation_failure_reason"]
    assert not review.supervision_manifest(failed)["positive_action_ids"]
    malformed = review.inspect_process_review("{", request)
    assert malformed["review_status"] == "annotation_failed"
    assert malformed["process_validity"] == "unknown"


def test_critical_error_and_unknown_differ_but_neither_becomes_positive():
    _, request, body = fixture()
    assessment = body["process"]["evidence_and_operations"]
    assessment["status"] = "critical_error"
    invalid = inspect(request, body)
    assert invalid["review_status"] == "annotation_succeeded"
    assert invalid["process_validity"] == "invalid"
    assert not review.supervision_manifest(invalid)["positive_content_spans"]
    assessment["status"] = "unknown"
    assessment["summary"] = "Critical mixed statement cannot be resolved."
    unknown = inspect(request, body)
    assert unknown["process_validity"] == "unknown"
    assert not review.supervision_manifest(unknown)["positive_action_ids"]


def test_unreviewed_content_never_defaults_positive_and_all_reason_mask_is_reported():
    episode, request, body = fixture()
    body["supervision"] = [body["supervision"][-1]]
    manifest = review.supervision_manifest(inspect(request, body))
    review.validate_manifest(episode, manifest)
    assert manifest["positive_content_spans"] == []
    assert manifest["positive_action_ids"]
    assert manifest["public_reasoning_all_masked"]
    assert manifest["omitted_spans_are_unreviewed"]
    assert manifest["arbitrary_minimum_reason_tokens_required"] is False


@pytest.mark.parametrize(
    "fault", ["partial_action", "observation", "overlap", "no_evidence", "old_graph"]
)
def test_only_original_one_authority_target_decisions_are_supported(fault):
    _, request, body = fixture()
    if fault == "partial_action":
        item = body["supervision"][-1]
        item["end"] -= 1
        item["quote"] = item["quote"][:-1]
    elif fault == "observation":
        doc = next(d for d in request["trajectory"]["segments"] if d["kind"] == "tool_observation")
        body["supervision"].append(
            dict(
                segment_id=doc["segment_id"],
                start=0,
                end=len(doc["text"]),
                quote=doc["text"],
                decision="positive",
                reason="Not allowed.",
            )
        )
    elif fault == "overlap":
        body["supervision"].append(copy.deepcopy(body["supervision"][0]))
    elif fault == "no_evidence":
        body["process"]["evidence_and_operations"]["evidence"] = []
    else:
        body["nodes"] = []
    result = inspect(request, body)
    assert (
        result["review_status"] == "annotation_failed" and result["process_validity"] == "unknown"
    )


def test_other_review_coordinate_or_semantic_description_never_implies_id_disagreement():
    episode, request, body = fixture()
    other = review.prepare_process_request(
        episode,
        slot_id=request["slot_id"],
        native_result=request["native_result"],
        integrity=request["integrity"],
        reviewer=3,
    )
    body["behavior"]["description"] = (
        "A subtraction route; optional exploration need not support the final answer."
    )
    assert inspect(other, body)["process_validity"] == "valid"
    assert review.policy_definition()["minimum_reviewers_mathematically_required"] is None


def test_manifest_requires_reproducible_authority_not_self_reported_flags_or_new_masks():
    episode, request, body = fixture()
    manifest = review.supervision_manifest(inspect(request, body))
    altered = copy.deepcopy(manifest)
    altered["positive_action_ids"] = []
    altered["id"] = digest({k: v for k, v in altered.items() if k != "id"})
    with pytest.raises(ValueError, match="derive exactly"):
        review.validate_manifest(episode, altered)
    result = inspect(request, body)
    result["process_validity"] = "invalid"
    result["id"] = digest({k: v for k, v in result.items() if k != "id"})
    with pytest.raises(ValueError, match="reproduce"):
        review.supervision_manifest(result)
    other_episode, _, _ = fixture(
        "Different original reasoning. Let me inspect the public table first."
    )
    with pytest.raises(ValueError, match="actual original Episode"):
        review.validate_manifest(other_episode, manifest)


def test_integrity_native_process_and_annotation_are_not_one_gate():
    episode, request, body = fixture()
    native = dict(
        Q_native=False, native={"native": {"execution_accuracy": 0.0, "program_accuracy": 0.0}}
    )
    changed = review.prepare_process_request(
        episode,
        slot_id=request["slot_id"],
        native_result=native,
        integrity={**request["integrity"], "history_complete": None},
    )
    result = inspect(changed, body)
    assert (
        result["process_validity"] == "valid" and result["review_status"] == "annotation_succeeded"
    )
    assert result["native_result"] == native
    assert result["record_integrity_status"] == "unknown_external_checks"
    manifest = review.supervision_manifest(result)
    assert not manifest["positive_action_ids"] and not manifest["positive_content_spans"]
    assert not manifest["external_integrity_evidence_verified_here"]


def test_no_provider_or_wallet_dispatch_entry_exists():
    assert not hasattr(review, "request_review") and not hasattr(review, "ledger_for")
    assert review.policy_definition()["production_authorized"] is False
