"""Saved-graph and isolated measurement controls, never new model trajectories.

All source graphs below are read from the already-qualified fixed panel. Graph
mutations are counterfactual comparison inputs only: no Runtime, Operation,
qualification, audit, tokenizer, Student or GPU execution establishes them.
"""

from __future__ import annotations

import copy
from pathlib import Path

import pytest

from trusted_synthesis.canonical_json import canonical_json_bytes, strict_canonical_hash
from trusted_synthesis.domains.finance.qa_vnext import measurement as domain
from trusted_synthesis.domains.finance.qa_vnext.program_adapter import ProgramTaskAdapter
from trusted_synthesis.domains.finance.qa_vnext.protocol import ProtocolError
from trusted_synthesis.domains.finance.qa_vnext.runtime import PublicQARuntime
from trusted_synthesis.domains.finance.qa_vnext.share_adapter import ShareTaskAdapter
from trusted_synthesis.experiments.finance_qa_vnext_model_execution import qualification
from trusted_synthesis.experiments.finance_qa_vnext_model_execution.models import read_json, record
from trusted_synthesis.experiments.finance_qa_vnext_panel_quotient import comparison

ROOT = Path(__file__).resolve().parents[2]
SOURCE = (
    ROOT / "trusted_data_synthesis/artifacts/qa_vnext_task_panel/fixed_eight_task_panel_v1_20260906"
)


def forbidden(*args, **kwargs):
    pytest.fail("comparison control attempted execution, audit, or old supported-flag mapper")


@pytest.fixture(autouse=True)
def no_execution_or_reaudit(monkeypatch):
    monkeypatch.setattr(PublicQARuntime, "run", forbidden)
    monkeypatch.setattr(ProgramTaskAdapter, "execute", forbidden)
    monkeypatch.setattr(ShareTaskAdapter, "execute", forbidden)
    monkeypatch.setattr(domain, "audit_session", forbidden)
    monkeypatch.setattr(domain, "compare_sessions", forbidden)
    monkeypatch.setattr(qualification, "qualify_session", forbidden)


@pytest.fixture(scope="module")
def source():
    registrations = read_json((SOURCE / "preparation/registrations.json").read_bytes())
    conditions = read_json((SOURCE / "preparation/condition.json").read_bytes())
    entries = {}
    for registration in registrations:
        label = registration["label"]
        q = read_json((SOURCE / f"execution/analysis/qualifications/{label}.json").read_bytes())
        entries[label] = {"registration": registration, "qualification": q}
    pairs = read_json((SOURCE / "execution/analysis/finite_comparisons.json").read_bytes())["pairs"]
    return {"entries": entries, "pairs": pairs, "condition": conditions}


def reseal(value, kind="panel_quotient_projection", **changes):
    fields = {key: item for key, item in value.items() if key not in {"id", "schema_version"}}
    return record(kind, **(fields | changes))


def sidecar(source, label, *, interactions=None):
    entry = source["entries"][label]
    registration, q = entry["registration"], entry["qualification"]
    audit = q["domain_audit"]
    eligible = q["qualified"] is True
    graph = copy.deepcopy(audit["finite_projection"])
    graph["retained_interactions"] = [] if interactions is None else copy.deepcopy(interactions)
    return record(
        "panel_quotient_projection",
        rule_id="isolated_test_correction_rule_not_formal_output",
        generation_condition_id=source["condition"]["id"],
        registration_id=registration["id"],
        label=label,
        task_group=q["task_group"],
        task_id=q["task_id"],
        context_id=q["context_id"],
        protocol_id=q["protocol_id"],
        registry_hash=q["registry_hash"],
        session_id=q["session_id"],
        qualification_id=q["id"],
        old_domain_audit_id=audit["id"],
        source_actual_graph_id=audit["actual_decision_graph"]["id"],
        old_projection_supported=audit["projection_supported"],
        source_domain_audit=audit,
        status="supported" if eligible else "ineligible",
        supported=eligible,
        behavior_projection=graph if eligible else None,
        synthetic_measurement_control=True,
        new_valid_model_trajectory_claimed=False,
    )


def retained_share_episode(source):
    """A normalized test episode anchored to real S02 nodes, not a rule interpreter."""
    graph = source["entries"]["S02"]["qualification"]["domain_audit"]["finite_projection"]
    summation = next(node for node in graph["nodes"] if node["operation"] == "relation_sum")
    ratio = next(node for node in graph["nodes"] if node["operation"] == "share_ratio")
    return [
        {
            "kind": "rejected_ratio_then_different_admitted_sum",
            "public_information": {
                "accepted_producers": [],
                "available_supports": ["disclosed_total", "reconstructed_total"],
            },
            "rejected_proposal": {
                "operation": "share_ratio",
                "inputs": copy.deepcopy(ratio["inputs"]),
                "violation": "admission.alternative_set",
            },
            "next_admitted_action": {"producer_action": summation["node_id"]},
            "new_accepted_total": {"producer_action": summation["node_id"]},
            "later_ratio_action": {"producer_action": ratio["node_id"]},
            "later_denominator_support": next(
                copy.deepcopy(item["reference"])
                for item in ratio["inputs"]
                if item["role"] == "denominator"
            ),
            "sum_claim_used_as_ratio_input": False,
        }
    ]


def test_all_twelve_clean_projections_keep_base_semantics_and_alpha_compatibility(source):
    clean = [
        label
        for label, entry in source["entries"].items()
        if entry["qualification"]["domain_audit"]["projection_supported"]
    ]
    assert len(clean) == 12
    for label in clean:
        original = sidecar(source, label)
        before = canonical_json_bytes(original["source_domain_audit"])
        graph = original["behavior_projection"]
        old = original["source_domain_audit"]["finite_projection"]
        assert canonical_json_bytes(
            {"nodes": graph["nodes"], "final": graph["final"]}
        ) == canonical_json_bytes(old)
        renamed = domain._remap(
            graph,
            {node["node_id"]: f"renamed:{index}" for index, node in enumerate(graph["nodes"])},
        )
        renamed["nodes"].reverse()
        altered = reseal(original, behavior_projection=renamed)
        result = comparison.compare_projections(original, altered)
        assert result["relation"] == "equivalent" and result["proof_verified"] is True
        assert result["witness"] is None and result["correspondence"]
        assert canonical_json_bytes(original["source_domain_audit"]) == before


def test_all_five_old_pairs_reuse_the_supplied_mapping_without_search(source, monkeypatch):
    monkeypatch.setattr(domain, "_isomorphism", forbidden)
    assert len(source["pairs"]) == 5
    by_qualification = {
        entry["qualification"]["id"]: label for label, entry in source["entries"].items()
    }
    for pair in source["pairs"]:
        before = canonical_json_bytes(pair)
        left = sidecar(source, by_qualification[pair["left_qualification_id"]])
        right = sidecar(source, by_qualification[pair["right_qualification_id"]])
        result = comparison.reuse_clean_comparison(left, right, pair)
        assert result["relation"] == "equivalent" and result["equivalent"] is True
        assert result["correspondence"] == pair["comparison"]["correspondence"]
        assert result["derived_from_old_pair_id"] == pair["id"]
        assert result["new_isomorphism_search"] is False and result["proof_verified"] is True
        assert canonical_json_bytes(pair) == before


@pytest.mark.parametrize("group", ["D", "B"])
def test_reduced_corrected_graphs_require_actual_new_exact_comparison(source, group):
    left, right = sidecar(source, group + "01"), sidecar(source, group + "02")
    assert left["old_projection_supported"] is False and right["old_projection_supported"] is True
    before = canonical_json_bytes([left["source_domain_audit"], right["source_domain_audit"]])
    result = comparison.compare_projections(left, right)
    assert result["new_isomorphism_search"] is True
    assert result["relation"] == "equivalent" and result["correspondence"]
    assert result["old_projection_support_flags_modified"] is False
    assert (
        canonical_json_bytes([left["source_domain_audit"], right["source_domain_audit"]]) == before
    )


def test_retained_share_interaction_participates_in_exact_alpha_node_correspondence(source):
    left = sidecar(source, "S02", interactions=retained_share_episode(source))
    mapping = {
        node["node_id"]: f"alpha:{index}"
        for index, node in enumerate(left["behavior_projection"]["nodes"])
    }
    changed = domain._remap(left["behavior_projection"], mapping)
    changed["nodes"].reverse()
    right = reseal(left, behavior_projection=changed)
    assert strict_canonical_hash(left["behavior_projection"]) != strict_canonical_hash(changed)
    result = comparison.compare_projections(left, right)
    assert result["relation"] == "equivalent"
    assert result["correspondence"] == {value: key for key, value in mapping.items()}
    assert result["content_hash_is_relation_authority"] is False


def test_retained_episode_cannot_be_dropped_with_unchanged_nodes_and_final(source):
    left = sidecar(source, "S02", interactions=retained_share_episode(source))
    graph = copy.deepcopy(left["behavior_projection"])
    graph["retained_interactions"] = []
    right = reseal(left, behavior_projection=graph)
    result = comparison.compare_projections(left, right)
    assert result["relation"] == "not_equivalent" and result["equivalent"] is False
    assert result["witness"]["kind"] == "retained_dependency_or_final_structure"
    assert result["witness"]["left"]["retained_interactions"]
    assert result["witness"]["right"]["retained_interactions"] == []


@pytest.mark.parametrize("change", ["remove_sum", "use_sum_claim_denominator"])
def test_s02_real_sum_and_actual_disclosed_denominator_cannot_be_changed_by_final_match(
    source, change
):
    left = sidecar(source, "S02", interactions=retained_share_episode(source))
    graph = copy.deepcopy(left["behavior_projection"])
    sum_node = next(node for node in graph["nodes"] if node["operation"] == "relation_sum")
    if change == "remove_sum":
        graph["nodes"] = [node for node in graph["nodes"] if node["node_id"] != sum_node["node_id"]]
    else:
        ratio = next(node for node in graph["nodes"] if node["operation"] == "share_ratio")
        operand = next(item for item in ratio["inputs"] if item["role"] == "denominator")
        operand["kind"] = "claim"
        operand["reference"] = {"producer_action": sum_node["node_id"]}
        ratio["input_dependencies"] = [sum_node["node_id"]]
        ratio["decision_dependencies"] = [sum_node["node_id"]]
    right = reseal(left, behavior_projection=graph, isolated_counterfactual_control=change)
    assert graph["final"] == left["behavior_projection"]["final"]
    result = comparison.compare_projections(left, right)
    assert result["relation"] == "not_equivalent" and result["witness"]
    assert result["witness"]["kind"] == (
        "actual_action_count" if change == "remove_sum" else "retained_action_semantics"
    )
    assert (
        result["counterfactual_graph_comparison_does_not_validate_a_new_model_trajectory"] is True
    )


def test_raw_rejection_count_and_raw_ledger_metadata_are_not_classifiers(source):
    left = sidecar(source, "S02", interactions=retained_share_episode(source))
    left = reseal(left, raw_event_metadata={"rejected_count": 5, "ledger_id": "original"})
    right = reseal(
        left, raw_event_metadata={"rejected_count": 999, "ledger_id": "isolated-counterfactual"}
    )
    result = comparison.compare_projections(left, right)
    assert result["relation"] == "equivalent"


@pytest.mark.parametrize("field", comparison.PARENT_FIELDS)
def test_foreign_task_context_protocol_registry_generation_or_rule_is_rejected(source, field):
    left = sidecar(source, "F01")
    right = reseal(sidecar(source, "F02"), **{field: "foreign:" + field})
    with pytest.raises(ProtocolError, match="mismatch"):
        comparison.compare_projections(left, right)


@pytest.mark.parametrize("status", ["undetermined", "ineligible"])
def test_unsupported_remains_undetermined_without_search(source, monkeypatch, status):
    monkeypatch.setattr(domain, "_isomorphism", forbidden)
    left = sidecar(source, "F01")
    right = reseal(sidecar(source, "F02"), status=status, supported=False, behavior_projection=None)
    result = comparison.compare_projections(left, right)
    assert result["relation"] == "undetermined" and result["equivalent"] is None
    assert result["correspondence"] is None and result["witness"] is None
    assert result["new_isomorphism_search"] is result["proof_verified"] is False
    assert result["exact_full_graph_and_retained_interactions_compared"] is False


def test_failed_s01_cannot_receive_a_determinate_comparison(source):
    left, right = (
        sidecar(source, "S01"),
        sidecar(source, "S02", interactions=retained_share_episode(source)),
    )
    result = comparison.compare_projections(left, right)
    assert left["status"] == "ineligible" and result["relation"] == "undetermined"


def test_isomorphism_search_exhaustion_is_not_non_equivalence(source, monkeypatch):
    def exhausted(*args):
        raise ProtocolError("comparison.isomorphism_search_bound")

    monkeypatch.setattr(domain, "_isomorphism", exhausted)
    result = comparison.compare_projections(sidecar(source, "F01"), sidecar(source, "F02"))
    assert (
        result["relation"] == "undetermined"
        and result["reason"] == "comparison.isomorphism_search_bound"
    )
    assert result["proof_verified"] is False


@pytest.mark.parametrize(
    "change", ["unsealed", "duplicate_node", "old_identity", "contradictory_support"]
)
def test_invalid_identity_or_graph_shape_cannot_obtain_a_correspondence(source, change):
    left, right = sidecar(source, "F01"), sidecar(source, "F02")
    if change == "unsealed":
        right["rule_id"] = "unsealed"
    elif change == "old_identity":
        right = reseal(right, "qualification")
    elif change == "contradictory_support":
        right = reseal(right, status="ineligible", supported=True)
    else:
        graph = copy.deepcopy(right["behavior_projection"])
        graph["nodes"].append(copy.deepcopy(graph["nodes"][0]))
        right = reseal(right, behavior_projection=graph)
    with pytest.raises(ProtocolError):
        comparison.compare_projections(left, right)


@pytest.mark.parametrize(
    "change",
    [
        "base_both_changed",
        "nonempty_extension",
        "old_support_false",
        "source_audit_missing",
        "source_audit_changed",
        "source_graph_id",
        "old_mapping",
        "old_pair_parent",
    ],
)
def test_clean_reuse_rejects_changed_source_semantics_or_unverified_old_mapping(
    source, monkeypatch, change
):
    monkeypatch.setattr(domain, "_isomorphism", forbidden)
    left, right = sidecar(source, "F01"), sidecar(source, "F02")
    pair = copy.deepcopy(next(item for item in source["pairs"] if item["task_group"] == "F"))
    if change == "base_both_changed":
        altered = []
        for item in (left, right):
            graph = copy.deepcopy(item["behavior_projection"])
            graph["final"]["result"] = {"isolated_changed_answer": "same-on-both-sides"}
            altered.append(reseal(item, behavior_projection=graph))
        left, right = altered
    elif change == "nonempty_extension":
        graph = copy.deepcopy(left["behavior_projection"])
        graph["retained_interactions"] = [{"retained_test_change": True}]
        left = reseal(left, behavior_projection=graph)
    elif change == "old_support_false":
        left = reseal(left, old_projection_supported=False)
    elif change == "source_audit_missing":
        left = reseal(left, source_domain_audit=None)
    elif change == "source_audit_changed":
        audit = copy.deepcopy(left["source_domain_audit"])
        audit["projection_supported"] = False
        left = reseal(left, source_domain_audit=audit)
    elif change == "source_graph_id":
        left = reseal(left, source_actual_graph_id="wrong-source-graph")
    elif change == "old_pair_parent":
        pair = reseal(pair, "finite_pair", left_qualification_id="foreign-old-qualification")
    else:
        old = pair["comparison"]
        changed = domain.record(
            "finite_comparison",
            **{
                key: value
                for key, value in old.items()
                if key not in {"id", "schema_version", "correspondence"}
            },
            correspondence={"action:0": "wrong-left-node"},
        )
        pair = reseal(pair, "finite_pair", comparison=changed)
    with pytest.raises(ProtocolError):
        comparison.reuse_clean_comparison(left, right, pair)
