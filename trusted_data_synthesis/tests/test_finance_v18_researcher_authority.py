"""Hermetic source-bound judgment checks; no production artifacts, API or Student."""

import copy
import json

import pytest

from trusted_synthesis.finance_research import v18_researcher_authority as authority


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
    return path


def locator(view, suffix, *, member=False):
    segment = next(s for s in view["segments"] if s["segment_id"].endswith(suffix))
    result = dict(
        segment_id=segment["segment_id"], start=0, end=len(segment["text"]), quote=segment["text"]
    )
    if member:
        result["slot_id"] = view["slot_id"]
    return result


@pytest.fixture
def research_case(tmp_path, monkeypatch):
    monkeypatch.setattr(authority, "PROJECT", tmp_path)
    views = []
    for i in range(4):
        slot = f"synthetic:p{i}"
        revised = i == 1
        texts = [
            ("source", "source_text", "Rent is 5 million; commitments are 10000 thousand.", None),
            (
                "before",
                "public_content",
                "Divide 5 by 10000." if revised else "Align units and divide 5000 by 10000.",
                0,
            ),
            (
                "arguments0",
                "action_arguments",
                '{"program":"divide(5, 10000)"}'
                if revised
                else '{"program":"divide(5000, 10000)"}',
                0,
            ),
            (
                "observation",
                "tool_observation",
                '{"result":0.0005}' if revised else '{"result":0.5}',
                None,
            ),
            (
                "after",
                "public_content",
                "Reject the mixed units; convert 5 million to 5000 thousand."
                if revised
                else "The unchanged ratio is 0.5.",
                1,
            ),
            ("arguments1", "action_arguments", '{"program":"divide(5000, 10000)"}', 1),
        ]
        segments = []
        for suffix, kind, text, turn in texts:
            segment = dict(segment_id=f"{slot}/{suffix}", kind=kind, text=text)
            if turn is not None:
                segment["turn_index"] = turn
            segments.append(segment)
        views.append(
            dict(
                slot_id=slot,
                view_id=f"synthetic-view:{i}",
                episode_sha256=authority.digest({"synthetic_episode": i}),
                segments=segments,
                turns=[
                    dict(
                        turn_index=0, actions=[dict(action_id=f"{slot}/a0", event_id=f"{slot}/e0")]
                    )
                ],
                events=[
                    dict(
                        event_id=f"{slot}/e0",
                        action_id=f"{slot}/a0",
                        observation_segment_id=f"{slot}/observation",
                    )
                ],
            )
        )
    request = authority.bound(
        dict(task_id=authority.ABMD, views=views, slot_ids=[v["slot_id"] for v in views])
    )
    source_path = write_json(tmp_path / "source.json", request)
    policy_path = tmp_path / "policy.txt"
    policy_path.write_text(
        "Synthetic policy: exact sources and consequential revision.\n", encoding="utf-8"
    )
    states = []
    for state_id, members, chi in [("consistent", [0, 2, 3], 0), ("corrected", [1], 1)]:
        state = dict(
            state_id=state_id,
            slot_ids=[views[i]["slot_id"] for i in members],
            basis="Same unit-consistent ratio."
            if not chi
            else "Observed mixed units, then corrected the calculation.",
            chi=chi,
            chi_reason="No substantive change."
            if not chi
            else "Explicit rejection and changed program.",
            evidence=[locator(views[i], "/after", member=True) for i in members],
            interventions=[],
        )
        if chi:
            state["interventions"].append(
                dict(
                    slot_id=views[1]["slot_id"],
                    kind="revision",
                    action_id="synthetic:p1/a0",
                    observation_segment_id="synthetic:p1/observation",
                    consequence=locator(views[1], "/arguments1"),
                    effect=(
                        "After observing 0.0005, reject mixed units "
                        "and change numerator from 5 to 5000."
                    ),
                )
            )
        states.append(state)
    draft = dict(
        schema="v18_abmd_source_grounded_research_judgment_proposal.v1",
        task_id=authority.ABMD,
        adjudicator=dict(
            identity="AI collaboration agent; not a human researcher",
            new_external_api_calls=0,
            provider_receipt=None,
            student_artifacts_read=False,
            training_progress_artifacts_read=False,
            independent_financial_truth_certification=False,
        ),
        provenance=dict(
            record_path="source.json",
            record_file_sha256=authority.sha(source_path),
            definitions=[dict(path="policy.txt", sha256=authority.sha(policy_path))],
            originals=[
                dict(
                    alias=f"p{i}",
                    slot_id=v["slot_id"],
                    view_id=v["view_id"],
                    episode_sha256=v["episode_sha256"],
                    view_canonical_sha256=authority.digest(v),
                )
                for i, v in enumerate(views)
            ],
        ),
        mapping_status="complete",
        states=states,
        ambiguities=[],
        state_by_slot={slot: state["state_id"] for state in states for slot in state["slot_ids"]},
        chi_by_state={state["state_id"]: state["chi"] for state in states},
    )
    draft_path = write_json(tmp_path / "draft.json", draft)
    return dict(
        draft=draft,
        request=request,
        draft_path=draft_path,
        source_path=source_path,
        policy_path=policy_path,
        output=tmp_path / "authority",
    )


def test_synthetic_four_package_authority_roundtrip_keeps_labels_and_identity(research_case):
    case = research_case
    before = copy.deepcopy(case["draft"])
    record = authority.approve(case["draft_path"], case["source_path"], case["output"])
    result = authority.load_authority(
        authority.entry(case["output"] / "record.json"),
        {authority.ABMD: case["request"]["slot_ids"]},
    )
    assert result == record["inspection"]
    assert result["state_by_slot"] == before["state_by_slot"]
    assert result["chi_by_state"] == {"consistent": 0, "corrected": 1}
    assert [len(s["slot_ids"]) for s in result["states"]] == [3, 1]
    assert result["mapping_admitted"] and result["mapping_status"] == "complete"
    assert result["human_judgment"] is result["semantic_truth_proved"] is False
    assert (
        result["actual_model_call_receipt_verified"] is result["Student_information_used"] is False
    )
    assert result["not_purely_mechanical"] is True
    assert record["API_calls"] == 0 and record["researcher_identity"]["human"] is False
    assert case["draft"] == before


@pytest.mark.parametrize(
    "field,value",
    [
        ("identity", "Human researcher"),
        ("provider_receipt", {"id": "invented-receipt"}),
        ("new_external_api_calls", 1),
        ("independent_financial_truth_certification", True),
        ("student_artifacts_read", True),
        ("training_progress_artifacts_read", True),
    ],
)
def test_false_identity_receipt_or_excluded_information_is_rejected(research_case, field, value):
    case = research_case
    case["draft"]["adjudicator"][field] = value
    with pytest.raises(ValueError, match="actual non-human, source-only judgment"):
        authority.inspection_for(case["draft"], case["request"])


@pytest.mark.parametrize("fault", ["duplicate_member", "overlapping_states", "missing_member"])
def test_partition_must_cover_every_original_exactly_once(research_case, fault):
    draft, request = research_case["draft"], research_case["request"]
    state = draft["states"][0]
    if fault == "duplicate_member":
        state["slot_ids"].append(state["slot_ids"][0])
    elif fault == "overlapping_states":
        draft["states"][1]["slot_ids"].append(state["slot_ids"][0])
    else:
        removed = state["slot_ids"].pop()
        state["evidence"] = [e for e in state["evidence"] if e["slot_id"] != removed]
        del draft["state_by_slot"][removed]
    with pytest.raises(ValueError, match="unique members|include all four originals"):
        authority.inspection_for(draft, request)


@pytest.mark.parametrize(
    "fault", ["foreign_consequence", "same_turn", "wrong_observation", "observation_as_consequence"]
)
def test_chi1_needs_the_actual_pair_and_later_same_package_model_consequence(research_case, fault):
    draft, request = research_case["draft"], research_case["request"]
    intervention = draft["states"][1]["interventions"][0]
    if fault == "foreign_consequence":
        intervention["consequence"] = locator(request["views"][0], "/arguments1")
    elif fault == "same_turn":
        intervention["consequence"] = locator(request["views"][1], "/arguments0")
    elif fault == "wrong_observation":
        intervention["observation_segment_id"] = "synthetic:p0/observation"
    else:
        intervention["consequence"] = locator(request["views"][1], "/observation")
    with pytest.raises(
        ValueError, match="this original package|later model consequence|action/observation pair"
    ):
        authority.inspection_for(draft, request)


@pytest.mark.parametrize("fault", ["paraphrase", "empty_span", "boolean_offset"])
def test_fuzzy_or_changed_quotes_are_rejected(research_case, fault):
    evidence = research_case["draft"]["states"][0]["evidence"][0]
    if fault == "paraphrase":
        evidence["quote"] = "The ratio remains one half."
    elif fault == "empty_span":
        evidence.update(start=0, end=0, quote="")
    else:
        evidence["start"] = False
    with pytest.raises(ValueError, match="exact original nonempty character spans"):
        authority.inspection_for(research_case["draft"], research_case["request"])


def test_unresolved_ambiguity_never_acquires_default_labels(research_case):
    draft = research_case["draft"]
    draft["ambiguities"] = [
        dict(slot_ids=["synthetic:p1"], description="Substantive effect remains unresolved.")
    ]
    result = authority.inspection_for(draft, research_case["request"])
    assert result["mapping_status"] == result["chi_status"] == "unknown"
    assert result["mapping_admitted"] is False
    assert result["state_by_slot"] == result["chi_by_state"] == {}
    assert result["ambiguities"] == draft["ambiguities"]
    assert result["states"] == draft["states"]


@pytest.mark.parametrize(
    "fault", ["request_bytes", "rebound_view", "declared_view_hash", "policy_bytes", "draft_bytes"]
)
def test_frozen_original_and_judgment_hashes_cannot_be_replaced(research_case, fault):
    case = research_case
    draft = case["draft"]
    source_ref = authority.entry(case["source_path"])
    if fault == "draft_bytes":
        reference = authority.file_ref(case["draft_path"])
        case["draft_path"].write_text("{}", encoding="utf-8")
        with pytest.raises(ValueError, match="draft changed"):
            authority.read_draft(reference)
        return
    if fault == "request_bytes":
        case["source_path"].write_text("{}", encoding="utf-8")
    elif fault == "rebound_view":
        changed = copy.deepcopy(case["request"])
        changed["views"][0]["segments"][0]["text"] = "Altered source evidence."
        changed = authority.bound({k: v for k, v in changed.items() if k != "id"})
        write_json(case["source_path"], changed)
        source_ref = authority.entry(case["source_path"])
        draft["provenance"]["record_file_sha256"] = source_ref["sha256"]
    elif fault == "declared_view_hash":
        draft["provenance"]["originals"][0]["view_canonical_sha256"] = "0" * 64
    else:
        case["policy_path"].write_text("Altered semantic policy.", encoding="utf-8")
    with pytest.raises(
        ValueError,
        match="referenced bytes changed|public bytes changed|exact original semantic definitions",
    ):
        authority.original_inputs(draft, source_ref)
