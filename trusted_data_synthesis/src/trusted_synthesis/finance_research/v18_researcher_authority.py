"""Named source-grounded research judgment; no API receipt or automatic semantic repair."""

from __future__ import annotations

import copy
import json
from pathlib import Path

from .calibration import now
from .contracts import digest
from .v6_collection import bound, persist, require, sha
from .v13_material_registration import entry, read_ref

ABMD = "ABMD/2008/page_87.pdf-1"
KIND = "codex_source_grounded_research_adjudication"
PROJECT = Path("/data1/zhuxinrui/projects/Data-Synthesis")


def file_ref(path):
    path = Path(path).resolve()
    return dict(path=str(path), sha256=sha(path))


def read_draft(ref):
    require(sha(ref["path"]) == ref["sha256"], "named research judgment draft changed")
    return json.loads(Path(ref["path"]).read_bytes())


def original_inputs(draft, source_request_ref):
    q = read_ref(source_request_ref)
    provenance = draft["provenance"]
    require(
        q["task_id"] == draft["task_id"] == ABMD
        and len(q["views"]) == 4
        and source_request_ref["sha256"] == provenance["record_file_sha256"]
        and Path(source_request_ref["path"]) == (PROJECT / provenance["record_path"]).resolve(),
        "only the complete fixed ABMD four originals may be judged",
    )
    originals = provenance["originals"]
    require(len(originals) == 4, "all four independently read original views required")
    for i, (view, ref) in enumerate(zip(q["views"], originals, strict=True)):
        require(
            ref["alias"] == f"p{i}"
            and ref["slot_id"] == view["slot_id"]
            and ref["view_id"] == view["view_id"]
            and ref["episode_sha256"] == view["episode_sha256"]
            and ref["view_canonical_sha256"] == digest(view),
            "original package/view identity or complete public bytes changed",
        )
    policies = {
        str((PROJECT / p["path"]).resolve()): p["sha256"] for p in provenance["definitions"]
    }
    require(
        policies and all(sha(path) == expected for path, expected in policies.items()),
        "researcher must use the exact original semantic definitions",
    )
    return dict(
        source_request_ref=source_request_ref,
        original_view_hashes={v["slot_id"]: digest(v) for v in q["views"]},
        original_view_ids={v["slot_id"]: v["view_id"] for v in q["views"]},
        policy_source_hashes=policies,
    ), q


def located(value, view):
    docs = {d["segment_id"]: d for d in view["segments"]}
    require(value["segment_id"] in docs, "evidence must be from this original package")
    doc = docs[value["segment_id"]]
    start, end, quote = value["start"], value["end"], value["quote"]
    require(
        type(start) is type(end) is int
        and 0 <= start < end <= len(doc["text"])
        and isinstance(quote, str)
        and quote
        and doc["text"][start:end] == quote,
        "research evidence must retain exact original nonempty character spans",
    )
    return doc


def inspection_for(draft, q):
    """Check source/coverage only. Semantic equivalence remains the named judgment."""
    require(
        draft["schema"] == "v18_abmd_source_grounded_research_judgment_proposal.v1"
        and draft["task_id"] == ABMD
        and type(draft["ambiguities"]) is list,
        "explicit complete-partition research judgment required",
    )
    actor = draft["adjudicator"]
    require(
        actor["new_external_api_calls"] == 0
        and actor["provider_receipt"] is None
        and actor["student_artifacts_read"] is False
        and actor["training_progress_artifacts_read"] is False
        and actor["independent_financial_truth_certification"] is False
        and actor["identity"] == "AI collaboration agent; not a human researcher",
        "disclose the actual non-human, source-only judgment; never forge a paid receipt",
    )
    views = {v["slot_id"]: v for v in q["views"]}
    seen, state_ids = set(), set()
    states = copy.deepcopy(draft["states"])
    require(states, "an empty mapping cannot silently become a complete partition")
    for state in states:
        require(
            state["state_id"] not in state_ids
            and state["state_id"]
            and state["slot_ids"]
            and len(state["slot_ids"]) == len(set(state["slot_ids"]))
            and set(state["slot_ids"]) <= set(views)
            and not (seen & set(state["slot_ids"]))
            and type(state["chi"]) is int
            and state["chi"] in (0, 1)
            and state["basis"].strip()
            and state["chi_reason"].strip()
            and "semantic_summary" not in state,
            "explicit unique members, semantic basis and chi; no replacement summary/schema",
        )
        seen.update(state["slot_ids"])
        state_ids.add(state["state_id"])
        covered = set()
        for evidence in state["evidence"]:
            slot = evidence["slot_id"]
            require(slot in state["slot_ids"], "cross-state evidence cannot imply membership")
            located(evidence, views[slot])
            covered.add(slot)
        require(covered == set(state["slot_ids"]), "evidence must cover every original member")
        demonstrated = set()
        for intervention in state["interventions"]:
            slot = intervention["slot_id"]
            require(
                slot in state["slot_ids"]
                and intervention["kind"] in ("verification", "revision")
                and intervention["effect"].strip(),
                "named actual intervention per chi1 member",
            )
            view = views[slot]
            actions = {
                a["action_id"]: (a, turn["turn_index"])
                for turn in view["turns"]
                for a in turn["actions"]
            }
            require(
                intervention["action_id"] in actions, "action must exist in original trajectory"
            )
            action, turn = actions[intervention["action_id"]]
            event = next(e for e in view["events"] if e["event_id"] == action["event_id"])
            require(
                event["action_id"] == action["action_id"]
                and event["observation_segment_id"] == intervention["observation_segment_id"],
                "actual original action/observation pair required",
            )
            consequence = located(intervention["consequence"], view)
            require(
                consequence["kind"] in ("public_content", "action_arguments")
                and consequence["turn_index"] > turn,
                "actual later model consequence required",
            )
            demonstrated.add(slot)
        require(
            (state["chi"] == 0 and not state["interventions"])
            or (state["chi"] == 1 and demonstrated == set(state["slot_ids"])),
            "no default chi and no exemplar substitution",
        )
    complete = draft["mapping_status"] == "complete" and not draft["ambiguities"]
    require(not complete or seen == set(views), "complete judgment must include all four originals")
    state_by_slot = {s: z["state_id"] for z in states for s in z["slot_ids"]}
    chi_by_state = {z["state_id"]: z["chi"] for z in states}
    require(
        draft["state_by_slot"] == state_by_slot and draft["chi_by_state"] == chi_by_state,
        "serialization must not change the researcher's complete state or chi decision",
    )
    return bound(
        dict(
            schema="v18_researcher_mapping_inspection.v1",
            task_id=ABMD,
            slot_ids=q["slot_ids"],
            states=states,
            mapping_status="complete" if complete else "unknown",
            mapping_admitted=complete,
            state_by_slot=state_by_slot if complete else {},
            chi_by_state=chi_by_state if complete else {},
            chi_status="semantically_annotated" if complete else "unknown",
            deterministic_singleton=False,
            ambiguities=draft["ambiguities"],
            judgment_source_kind=KIND,
            human_judgment=False,
            not_purely_mechanical=True,
            semantic_truth_proved=False,
            actual_model_call_receipt_verified=False,
            Student_information_used=False,
            production_admitted=False,
        )
    )


def approve(draft_path, source_request_path, output):
    """Call only after the main analyst has read all originals and approved this draft."""
    draft_ref, source_ref = file_ref(draft_path), entry(source_request_path)
    draft = read_draft(draft_ref)
    inputs, q = original_inputs(draft, source_ref)
    inspected = inspection_for(draft, q)
    result = bound(
        dict(
            schema="v18_researcher_mapping_authority.v1",
            at=now(),
            task_id=ABMD,
            slot_ids=q["slot_ids"],
            inspection=inspected,
            original_inputs=inputs,
            source_judgment_draft=draft_ref,
            judgment_source_kind=KIND,
            researcher_identity=dict(
                actor="Codex",
                agent="v18_abmd_research_judgment",
                human=False,
                independent_financial_truth_certification=False,
            ),
            main_analyst_approval=dict(
                actor="Codex main research assistant",
                complete_four_originals_read=True,
                complete_partition_and_chi_approved=True,
                Student_results_used=False,
            ),
            authority_scope="complete_ABMD_partition_and_chi",
            API_calls=0,
            human_judgment=False,
            not_purely_mechanical=True,
            no_Student_information_used=True,
            old_binding_or_hold_modified=False,
            summary_or_supervision_generated=False,
        )
    )
    persist(output, result)
    return result


def load_authority(reference, task_slots):
    record = read_ref(reference)
    require(
        record["schema"] == "v18_researcher_mapping_authority.v1"
        and record["task_id"] == ABMD
        and record["slot_ids"] == task_slots[ABMD]
        and record["judgment_source_kind"] == KIND
        and record["API_calls"] == 0
        and record["human_judgment"] is False
        and record["not_purely_mechanical"] is True
        and record["no_Student_information_used"] is True
        and record["authority_scope"] == "complete_ABMD_partition_and_chi"
        and record["researcher_identity"]["human"] is False
        and record["main_analyst_approval"]["complete_four_originals_read"] is True
        and record["main_analyst_approval"]["complete_partition_and_chi_approved"] is True,
        "only the explicit non-human research judgment may supply this new ABMD authority",
    )
    draft = read_draft(record["source_judgment_draft"])
    inputs, q = original_inputs(draft, record["original_inputs"]["source_request_ref"])
    require(
        record["original_inputs"] == inputs and record["inspection"] == inspection_for(draft, q),
        "original read hashes, complete membership/chi or exact evidence changed",
    )
    return copy.deepcopy(record["inspection"])
