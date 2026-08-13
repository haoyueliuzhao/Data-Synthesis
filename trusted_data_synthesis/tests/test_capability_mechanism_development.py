from __future__ import annotations

import json

from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_mechanism_ir import (
    DEVELOPMENT_TIERS,
    MECHANISM_IDS,
    RECOVERY_ORIGIN_FAMILIES,
    REQUIRED_TAGS_BY_MECHANISM,
    MechanismTier,
    make_control_action_graph,
    make_mechanism_action_graph,
    mechanism_contract_failures_raw,
)

ALL_TOOLS = {
    "search_archive",
    "open_document",
    "query_structured_fact",
    "calculator",
    "normalize_metric_unit_period",
    "cross_check_evidence",
}


def _compatibility(mechanism_id: str, tier: MechanismTier) -> tuple[str, ...]:
    if mechanism_id != "finance.bridge_semantic_alignment":
        return ("same_entity_metric_period_scope",)
    if tier == "easy_control":
        return ("alias_equivalence",)
    return ("alias_equivalence", "unit_period_field_normalization")


def _failures(
    mechanism_id: str,
    tier: MechanismTier,
    graph: dict[str, object],
) -> tuple[str, ...]:
    return mechanism_contract_failures_raw(
        mechanism_id=mechanism_id,
        tier=tier,
        graph=graph,
        allowed_tools=ALL_TOOLS,
        compatibility_policy=_compatibility(mechanism_id, tier),
        candidate_status=(
            "valid"
            if mechanism_id == "finance.candidate_verification_and_repair"
            else "not_applicable"
        ),
        recovery_origin_family=(
            RECOVERY_ORIGIN_FAMILIES[0]
            if mechanism_id == "finance.cross_family_failure_recovery"
            else None
        ),
    )


def test_mechanism_population_contract_has_frozen_84_group_quota() -> None:
    assert len(MECHANISM_IDS) == 7
    assert len(DEVELOPMENT_TIERS) == 12
    assert DEVELOPMENT_TIERS.count("easy_control") == 2
    assert DEVELOPMENT_TIERS.count("bridge") == 4
    assert DEVELOPMENT_TIERS.count("frontier") == 4
    assert DEVELOPMENT_TIERS.count("hard_control") == 2


def test_all_mechanism_graphs_are_valid_and_depth_is_strictly_monotonic() -> None:
    tiers: tuple[MechanismTier, ...] = (
        "easy_control",
        "bridge",
        "frontier",
        "hard_control",
    )
    for mechanism_id in MECHANISM_IDS:
        graphs = tuple(make_mechanism_action_graph(mechanism_id, tier) for tier in tiers)
        assert all(
            not _failures(mechanism_id, tier, graph.model_dump(mode="json"))
            for tier, graph in zip(tiers, graphs, strict=True)
        )
        assert [item.graph_depth for item in graphs] == sorted(item.graph_depth for item in graphs)
        assert len({item.graph_depth for item in graphs}) == 4
        control = make_control_action_graph("bridge")
        assert control.terminal_node_id == "stop"


def test_each_mechanism_rejects_dependency_tag_tool_and_stopping_mutations() -> None:
    for mechanism_id in MECHANISM_IDS:
        graph = make_mechanism_action_graph(mechanism_id, "bridge")
        payload = graph.model_dump(mode="json")
        source, target = graph.required_edges[0].split("->", maxsplit=1)
        dependency_mutation = json.loads(json.dumps(payload))
        target_node = next(
            item for item in dependency_mutation["nodes"] if item["node_id"] == target
        )
        target_node["depends_on"] = [item for item in target_node["depends_on"] if item != source]
        assert "required_dependency_missing" in _failures(
            mechanism_id, "bridge", dependency_mutation
        )

        tool_mutation = json.loads(json.dumps(payload))
        tool_node = next(item for item in tool_mutation["nodes"] if item["tool_id"])
        tool_node["tool_id"] = "unknown_tool"
        assert "unregistered_tool" in _failures(mechanism_id, "bridge", tool_mutation)

        tag_mutation = json.loads(json.dumps(payload))
        tag_counts = {
            tag: sum(tag in item["contract_tags"] for item in tag_mutation["nodes"])
            for tag in REQUIRED_TAGS_BY_MECHANISM[mechanism_id]
        }
        required_tag = next(tag for tag, count in tag_counts.items() if count == 1)
        tagged_node = next(
            item for item in tag_mutation["nodes"] if required_tag in item["contract_tags"]
        )
        tagged_node["contract_tags"] = [
            item for item in tagged_node["contract_tags"] if item != required_tag
        ]
        assert "required_contract_tag_missing" in _failures(mechanism_id, "bridge", tag_mutation)

        stop_mutation = json.loads(json.dumps(payload))
        stop_mutation["terminal_node_id"] = "read_public_task"
        assert "terminal_contract_broken" in _failures(mechanism_id, "bridge", stop_mutation)
