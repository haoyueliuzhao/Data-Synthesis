import copy
import json
from itertools import combinations

import pytest

from trusted_synthesis.finance_research.contracts import digest
from trusted_synthesis.finance_research.semantic_review import (
    ReviewError,
    audit_packet,
    document_index,
    resolve_pair,
    review_request,
    validate_review,
)


def fixture_bundle():
    slots = []
    for index in range(8):
        sid = f"s{index}"
        texts = [
            ("source", "source_text", "Revenue was 120."),
            ("content", "public_content", "Revenue is 120."),
            ("arguments", "action_arguments", '{"program":"add(120, 0)"}'),
            ("observation", "tool_observation", '{"submitted":true}'),
        ]
        segments = [
            dict(
                segment_id=key,
                kind=kind,
                text=text,
                start=0,
                end=len(text),
                **(dict(turn_index=0) if kind in {"public_content", "action_arguments"} else {}),
            )
            for key, kind, text in texts
        ]
        view = dict(
            task_id="finqa/task",
            episode_sha256=f"episode-{index}",
            view_id=f"view-{index}",
            slot_id=None,
            segments=segments,
            turns=[
                dict(
                    turn_index=0,
                    actions=[
                        dict(
                            action_id="a0", name="submit_program", arguments_segment_id="arguments"
                        )
                    ],
                )
            ],
            events=[dict(action_id="a0", observation_segment_id="observation", is_error=False)],
        )
        slots.append(dict(slot_id=sid, trajectory=view))
    return dict(
        schema="v6_task_review_bundle.v1", task_id="finqa/task", seal_id="sealed", slots=slots
    )


def quote(docs, doc_id):
    text = docs[doc_id]["text"]
    return dict(doc_id=doc_id, start=0, end=len(text), quote=text)


def fixture_review(bundle, reviewer=0):
    docs = document_index(bundle)
    source = quote(docs, "shared/source")
    slots = []
    for slot in bundle["slots"]:
        sid = slot["slot_id"]
        content = quote(docs, f"slot/{sid}/content")
        args = quote(docs, f"slot/{sid}/arguments")
        slots.append(
            dict(
                slot_id=sid,
                v_trace="valid",
                reason_codes=[],
                coverage_complete=True,
                propositions=[
                    dict(
                        proposition_id="p",
                        status="assertion",
                        critical=True,
                        judgment="supported",
                        accepted=True,
                        text=[content],
                        support=[source],
                        retraction=[],
                    )
                ],
                actions=[
                    dict(
                        action_doc_id=args["doc_id"],
                        label="approved",
                        proposition_ids=["p"],
                        evidence=[args, content],
                    )
                ],
                updates=[],
                mask=[
                    content | dict(label="approved", component="reason", proposition_ids=["p"]),
                    args | dict(label="approved", component="final", proposition_ids=["p"]),
                ],
                semantic_graph=dict(
                    nodes=[
                        dict(
                            node_id="n",
                            predicate="answer",
                            operation="none",
                            term_ids=["t"],
                            source_doc_ids=["shared/source"],
                            proposition_ids=["p"],
                            accepted=True,
                            evidence=[content],
                        )
                    ],
                    edges=[],
                ),
            )
        )
    relations = [
        dict(
            left=left,
            right=right,
            relation="equivalent",
            basis="same_semantic_graph",
            left_nodes=["n"],
            right_nodes=["n"],
            evidence=[quote(docs, f"slot/{left}/content"), quote(docs, f"slot/{right}/content")],
        )
        for left, right in combinations([slot["slot_id"] for slot in bundle["slots"]], 2)
    ]
    return dict(
        schema_version="v6_semantic_review.v1",
        reviewer=reviewer,
        task_bundle_sha256=digest(bundle),
        terms=[
            dict(
                term_id="t",
                subject="company",
                attribute="revenue",
                period="reported",
                value="120",
                unit="reporting unit",
                source_doc_ids=["shared/source"],
            )
        ],
        slots=slots,
        relations=relations,
    )


def checked(bundle, review):
    return validate_review(
        json.dumps(review),
        document_index(bundle),
        expected_reviewer=review["reviewer"],
        expected_bundle_sha256=digest(bundle),
    )


def mechanical():
    return {
        f"s{i}": dict(
            sealed=True,
            history_complete=True,
            calls_settled=True,
            actions_observations_bound=True,
            private_reference_isolated=True,
            native_correct=True,
        )
        for i in range(8)
    }


def test_group_two_contexts_and_q_v_mapper_separation():
    bundle = fixture_bundle()
    a, b = fixture_review(bundle, 0), fixture_review(bundle, 1)
    checks = mechanical()
    checks["s0"]["native_correct"] = False
    result = resolve_pair(checked(bundle, a), checked(bundle, b), checks)
    assert result["slots"]["s0"]["q_native"] is False
    assert result["slots"]["s0"]["v_trace"] == "valid"
    assert result["task_mapping"] == "complete"
    assert result["slots"]["s0"]["mapper"] == "not_applicable"
    assert result["slots"]["s0"]["common_material_exclusion"] == "native_incorrect"
    assert len(result["valid_slots_retained"]) == 7
    assert len(result["process_valid_slots_retained"]) == 8
    assert len({result["slots"][sid]["state_id"] for sid in result["valid_slots_retained"]}) == 1
    assert all(result["slots"][sid]["chi"] == 0 for sid in result["valid_slots_retained"])
    encoding = result["slots"]["s1"]["encoding_manifest"]
    assert encoding["positive_action_ids"] == ["a0"]
    assert encoding["positive_content_spans"][0]["original_segment_id"] == "content"
    assert encoding["mask_agreement"] and encoding["slot_id"] is None
    assert encoding["consensus_sha256"] and encoding["not_a_TokenReceipt"]
    assert not result["human_reviewed"] and not result["mathematical_proof"]
    json.dumps(checked(bundle, a))  # Saved review artifacts must not have tuple dict keys.
    request = review_request(bundle, {"program": "add(120, 0)", "answer": 120}, 0)
    assert request["model"] == "deepseek-flash"
    assert not request["other_reviewer_output_visible"]
    assert "review_only_private_reference" in request["messages"][1]["content"]
    assert all(doc["kind"] != "private_reference" for doc in request["document_index"].values())


def test_aliases_order_duplicate_nodes_do_not_mint_states_or_mask_disagreement():
    bundle = fixture_bundle()
    a, b = fixture_review(bundle, 0), fixture_review(bundle, 1)
    b["terms"][0]["term_id"] = "renamed_term"
    for slot in b["slots"]:
        slot["propositions"][0]["proposition_id"] = "renamed_prop"
        for action in slot["actions"]:
            action["proposition_ids"] = ["renamed_prop"]
        for mask in slot["mask"]:
            mask["proposition_ids"] = ["renamed_prop"]
        node = slot["semantic_graph"]["nodes"][0]
        node.update(
            node_id="renamed_node", term_ids=["renamed_term"], proposition_ids=["renamed_prop"]
        )
        duplicate = copy.deepcopy(node)
        duplicate["node_id"] = "duplicate"
        slot["semantic_graph"]["nodes"].append(duplicate)
    for relation in b["relations"]:
        relation.update(left_nodes=["renamed_node"], right_nodes=["renamed_node"])
    result = resolve_pair(checked(bundle, a), checked(bundle, b), mechanical())
    assert result["task_mapping"] == "complete"
    assert all(s["mask_status"] == "agreed" for s in result["slots"].values())


def test_mapper_unknown_does_not_turn_process_validity_into_error_or_drop_valid_slot():
    bundle = fixture_bundle()
    a, b = fixture_review(bundle, 0), fixture_review(bundle, 1)
    b["relations"][0].update(relation="unknown", basis="unresolved")
    result = resolve_pair(checked(bundle, a), checked(bundle, b), mechanical())
    assert result["task_mapping"] == "incomplete"
    assert len(result["valid_slots_retained"]) == 8
    assert all(
        s["v_trace"] == "valid" and s["mapper"] == "unknown" for s in result["slots"].values()
    )


def test_native_incorrect_or_unknown_process_valid_slot_cannot_overblock_common_mapper():
    bundle = fixture_bundle()
    a, b = fixture_review(bundle, 0), fixture_review(bundle, 1)
    for review in (a, b):
        for relation in review["relations"]:
            if relation["left"] in {"s0", "s1"}:
                relation.update(relation="unknown", basis="unresolved")
    checks = mechanical()
    checks["s0"]["native_correct"] = False
    checks["s1"]["native_correct"] = None
    result = resolve_pair(checked(bundle, a), checked(bundle, b), checks)
    assert result["task_mapping"] == "complete"
    assert result["valid_slots_retained"] == [f"s{i}" for i in range(2, 8)]
    assert len(result["process_valid_slots_retained"]) == 8
    assert result["slots"]["s1"]["common_material_exclusion"] == "native_unknown"


def test_unparsed_original_call_is_read_only_context_not_positive_target():
    bundle = fixture_bundle()
    segment = dict(
        segment_id="unparsed",
        kind="unparsed_tool_call",
        text='{"arguments":"{bad"}',
        start=0,
        end=len('{"arguments":"{bad"}'),
        turn_index=0,
    )
    bundle["slots"][0]["trajectory"]["segments"].append(segment)
    docs = document_index(bundle)
    assert docs["slot/s0/unparsed"]["kind"] == "unparsed_tool_call"
    review = fixture_review(bundle)
    assert checked(bundle, review)["derived"]["s0"]["mask_complete"]
    review["slots"][0]["mask"].append(
        quote(docs, "slot/s0/unparsed")
        | dict(label="approved", component="action", proposition_ids=["p"])
    )
    with pytest.raises(ReviewError, match="positive targets"):
        checked(bundle, review)


def test_nonvalid_pair_not_applicable_does_not_block_other_valid_slots():
    bundle = fixture_bundle()
    a, b = fixture_review(bundle, 0), fixture_review(bundle, 1)
    for review in (a, b):
        review["slots"][0]["v_trace"] = "invalid"
        for relation in review["relations"]:
            if relation["left"] == "s0":
                relation.update(relation="not_applicable", basis="not_applicable")
    result = resolve_pair(checked(bundle, a), checked(bundle, b), mechanical())
    assert result["task_mapping"] == "complete" and len(result["valid_slots_retained"]) == 7
    assert result["slots"]["s0"]["mapper"] == "not_applicable"
    assert result["slots"]["s0"]["encoding_manifest"] is None


@pytest.mark.parametrize("mutation", ["quote", "coverage", "source_target", "contradiction"])
def test_mechanical_evidence_and_mask_negative_controls(mutation):
    bundle = fixture_bundle()
    review = fixture_review(bundle)
    slot = review["slots"][0]
    if mutation == "quote":
        slot["propositions"][0]["text"][0]["quote"] = "invented quote"
    elif mutation == "coverage":
        slot["mask"].pop()
    elif mutation == "source_target":
        slot["mask"][0].update(quote(document_index(bundle), "shared/source"))
    else:
        slot["propositions"][0]["judgment"] = "contradicted"
    with pytest.raises(ReviewError):
        checked(bundle, review)


def test_no_json_repair_no_extra_state_id_and_all_eight_denominator():
    bundle = fixture_bundle()
    docs = document_index(bundle)
    review = fixture_review(bundle)
    raw = json.dumps(review)
    with pytest.raises(ReviewError, match="duplicate"):
        validate_review('{"reviewer":0,"reviewer":1}', docs)
    with pytest.raises((ValueError, ReviewError)):
        validate_review("```json\n" + raw + "\n```", docs)
    review["slots"][0]["state_id"] = "best"
    with pytest.raises(ValueError):
        checked(bundle, review)
    review = fixture_review(bundle)
    review["slots"].pop()
    with pytest.raises(ValueError):
        checked(bundle, review)


def test_tool_failure_never_promoted_to_positive_action_by_review_vote():
    bundle = fixture_bundle()
    bundle["slots"][0]["trajectory"]["events"][0]["is_error"] = True
    a, b = fixture_review(bundle, 0), fixture_review(bundle, 1)
    result = resolve_pair(checked(bundle, a), checked(bundle, b), mechanical())
    assert result["slots"]["s0"]["encoding_manifest"]["positive_action_ids"] == []


def test_pending_finite_human_packet_is_not_fabricated_review_or_training_gate():
    bundle = fixture_bundle()
    result = resolve_pair(
        checked(bundle, fixture_review(bundle, 0)),
        checked(bundle, fixture_review(bundle, 1)),
        mechanical(),
    )
    packet = audit_packet(bundle, result, maximum_cases=2)
    assert [case["slot_id"] for case in packet["cases"]] == ["s0", "s1"]
    assert packet["status"] == "pending" and not packet["human_reviewed"]
    assert packet["not_an_extra_training_admission_gate"]


def revision_fixture():
    bundle = fixture_bundle()
    for slot in bundle["slots"]:
        view = slot["trajectory"]
        for segment in view["segments"]:
            if segment["segment_id"] in {"content", "arguments"}:
                segment["turn_index"] = 1
        view["turns"][0]["turn_index"] = 1
        extra = [
            ("prior", "public_content", "Revenue is 90."),
            ("run", "action_arguments", '{"program":"add(120, 0)"}'),
            ("run_result", "tool_observation", '{"result":120}'),
        ]
        for key, kind, text in extra:
            view["segments"].append(
                dict(
                    segment_id=key,
                    kind=kind,
                    text=text,
                    start=0,
                    end=len(text),
                    **(dict(turn_index=0) if kind != "tool_observation" else {}),
                )
            )
        content = next(s for s in view["segments"] if s["segment_id"] == "content")
        content["text"] = "I retract 90: the observed result is 120."
        content["end"] = len(content["text"])
        view["turns"].insert(
            0,
            dict(
                turn_index=0,
                actions=[dict(action_id="run0", name="run_program", arguments_segment_id="run")],
            ),
        )
        view["events"].insert(
            0, dict(action_id="run0", observation_segment_id="run_result", is_error=False)
        )
    docs = document_index(bundle)
    review = fixture_review(bundle)
    for slot in review["slots"]:
        sid = slot["slot_id"]
        prior, run, observed = [
            quote(docs, f"slot/{sid}/{key}") for key in ("prior", "run", "run_result")
        ]
        content = quote(docs, f"slot/{sid}/content")
        slot["propositions"].append(
            dict(
                proposition_id="wrong",
                status="retracted",
                critical=True,
                judgment="contradicted",
                accepted=False,
                text=[prior],
                support=[quote(docs, "shared/source")],
                retraction=[content],
            )
        )
        slot["actions"].append(
            dict(
                action_doc_id=run["doc_id"],
                label="approved",
                proposition_ids=["p"],
                evidence=[run, observed, content],
            )
        )
        slot["mask"].extend(
            [
                prior | dict(label="retracted", component="reason", proposition_ids=["wrong"]),
                run | dict(label="approved", component="action", proposition_ids=["p"]),
            ]
        )
        slot["semantic_graph"]["nodes"].append(
            dict(
                node_id="revision",
                predicate="semantic_revision",
                operation="none",
                term_ids=["t"],
                source_doc_ids=["shared/source"],
                proposition_ids=["p"],
                accepted=True,
                evidence=[prior, observed, content],
            )
        )
        slot["semantic_graph"]["edges"].append(
            dict(from_node="revision", to_node="n", relation="revises", evidence=[content])
        )
        slot["updates"].append(
            dict(
                kind="semantic_revision",
                prior_proposition="wrong",
                posterior_proposition="p",
                action_doc_id=run["doc_id"],
                observation_doc_id=observed["doc_id"],
                decision_change="submission_change",
                substantive=True,
                evidence=[prior, run, observed, content],
                nonredundancy_evidence=[prior, quote(docs, "shared/source"), content],
            )
        )
    return bundle, review


def test_real_revision_chi_and_retracted_history_zero_target():
    bundle, a = revision_fixture()
    b = copy.deepcopy(a)
    b["reviewer"] = 1
    result = resolve_pair(checked(bundle, a), checked(bundle, b), mechanical())
    assert result["task_mapping"] == "complete"
    assert all(s["chi"] == 1 for s in result["slots"].values())
    mask = result["slots"]["s0"]["positive_target_mask"]
    assert next(s for s in mask if s["doc_id"].endswith("/prior"))["label"] == "retracted"
    encoder = result["slots"]["s0"]["encoding_manifest"]
    assert all(s["original_segment_id"] != "prior" for s in encoder["positive_content_spans"])
    assert encoder["positive_action_ids"] == ["a0", "run0"]
    a["slots"][0]["updates"][0]["kind"] = "format_repair"
    with pytest.raises(ReviewError, match="format/count/repetition"):
        checked(bundle, a)


def test_fake_retraction_or_wrong_observation_cannot_create_chi():
    bundle, review = revision_fixture()
    review["slots"][0]["updates"][0]["observation_doc_id"] = "slot/s0/observation"
    with pytest.raises(ReviewError, match="actual named action"):
        checked(bundle, review)
    bundle, review = revision_fixture()
    prior = quote(document_index(bundle), "slot/s0/prior")
    review["slots"][0]["propositions"][1]["retraction"] = [prior]
    with pytest.raises(ReviewError, match="follow the claim"):
        checked(bundle, review)
