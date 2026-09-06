"""Exact comparisons of new correction-aware finite measurement sidecars.

The old audit and its support flag are never edited or re-audited. Nodes, Final,
and normalized retained interactions all participate in the same exact labeled
DAG correspondence. Artifact hashes are references, not equivalence authority.
"""

from __future__ import annotations

from typing import Any

from trusted_synthesis.canonical_json import canonical_json_bytes
from trusted_synthesis.domains.finance.qa_vnext import measurement as domain
from trusted_synthesis.domains.finance.qa_vnext.protocol import ProtocolError

from ..finance_qa_vnext_model_execution.models import identity, record, require

PARENT_FIELDS = (
    "rule_id",
    "generation_condition_id",
    "task_group",
    "task_id",
    "context_id",
    "protocol_id",
    "registry_hash",
)
SOURCE_FIELDS = (
    "registration_id",
    "label",
    "session_id",
    "qualification_id",
    "old_domain_audit_id",
    "source_actual_graph_id",
)
BEHAVIOR_FIELDS = {"nodes", "final", "retained_interactions"}


def _sidecar(value: dict[str, Any]) -> None:
    identity(value, "panel_quotient_projection")
    require(
        all(
            isinstance(value.get(key), str) and bool(value[key])
            for key in PARENT_FIELDS + SOURCE_FIELDS
        ),
        "panel_quotient_comparison.source_identity_fields",
    )
    require(
        value.get("status") in {"supported", "undetermined", "ineligible"}
        and value.get("supported") is (value["status"] == "supported")
        and type(value.get("old_projection_supported")) is bool,
        "panel_quotient_comparison.support_status",
    )
    if value["supported"]:
        graph = value.get("behavior_projection")
        require(
            isinstance(graph, dict)
            and set(graph) == BEHAVIOR_FIELDS
            and isinstance(graph["nodes"], list)
            and bool(graph["nodes"])
            and isinstance(graph["final"], dict)
            and isinstance(graph["retained_interactions"], list),
            "panel_quotient_comparison.behavior_projection_shape",
        )
        assert isinstance(graph, dict)
        nodes = graph["nodes"]
        require(
            all(
                isinstance(node, dict)
                and isinstance(node.get("node_id"), str)
                and bool(node["node_id"])
                for node in nodes
            )
            and len({node["node_id"] for node in nodes}) == len(nodes),
            "panel_quotient_comparison.distinct_actual_nodes",
        )
        require(
            all(
                isinstance(node.get("operation"), str)
                and isinstance(node.get("inputs"), list)
                and all(
                    isinstance(node.get(key), list)
                    and all(isinstance(ref, str) for ref in node[key])
                    for key in ("input_dependencies", "decision_dependencies")
                )
                for node in nodes
            ),
            "panel_quotient_comparison.labeled_graph_shape",
        )


def _parents(left: dict[str, Any], right: dict[str, Any]) -> None:
    for value in (left, right):
        _sidecar(value)
    require(
        all(left[key] == right[key] for key in PARENT_FIELDS),
        "panel_quotient_comparison.task_context_protocol_registry_condition_rule_mismatch",
    )


def _result(
    left: dict[str, Any],
    right: dict[str, Any],
    *,
    correspondence: dict[str, str] | None = None,
    witness: dict[str, Any] | None = None,
    reason: str | None = None,
    new_isomorphism_search: bool,
    derived_from_old_pair_id: str | None = None,
) -> dict[str, Any]:
    return record(
        "panel_quotient_comparison",
        left_projection_id=left["id"],
        right_projection_id=right["id"],
        **{key: left[key] for key in PARENT_FIELDS},
        relation="undetermined"
        if reason
        else "equivalent"
        if correspondence is not None
        else "not_equivalent",
        equivalent=None if reason else correspondence is not None,
        correspondence=correspondence,
        witness=witness,
        reason=reason,
        correspondence_direction="right_node_to_left_node",
        new_isomorphism_search=new_isomorphism_search,
        derived_from_old_pair_id=derived_from_old_pair_id,
        proof_verified=reason is None,
        exact_full_graph_and_retained_interactions_compared=reason is None,
        content_hash_is_relation_authority=False,
        old_projection_support_flags_modified=False,
        trajectory_qualification_recomputed=False,
        counterfactual_graph_comparison_does_not_validate_a_new_model_trajectory=True,
    )


def compare_projections(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    """Search an exact right-to-left correspondence over all three behavior fields.

    Foreign/invalid sidecars are rejected. A valid but unsupported sidecar, or an
    exhausted finite search bound, remains undetermined and is never called unequal.
    There is no error-count, route-name, Final-only or graph-hash classifier here.
    """
    _parents(left, right)
    if not (left["supported"] and right["supported"]):
        return _result(left, right, reason="projection_not_supported", new_isomorphism_search=False)
    try:
        correspondence, witness = domain._isomorphism(
            left["behavior_projection"],
            right["behavior_projection"],
        )
    except ProtocolError as error:
        if str(error) != "comparison.isomorphism_search_bound":
            raise
        return _result(left, right, reason=str(error), new_isomorphism_search=True)
    return _result(
        left, right, correspondence=correspondence, witness=witness, new_isomorphism_search=True
    )


def reuse_clean_comparison(
    left: dict[str, Any],
    right: dict[str, Any],
    old_pair: dict[str, Any],
) -> dict[str, Any]:
    """Verify the frozen clean pair's actual mapping, without another search.

        The entire source audit is immutable metadata outside behavior_projection.
        Its identity and graph parents bind the old nodes and Final byte-for-byte;
        interactions must be empty.
    The supplied old mapping must then match both complete augmented graphs exactly.
    """
    _parents(left, right)
    identity(old_pair, "finite_pair")
    previous = old_pair["comparison"]
    domain._identity(previous, "finite_comparison")
    require(
        old_pair["task_group"] == left["task_group"]
        and old_pair["left_qualification_id"] == left["qualification_id"]
        and old_pair["right_qualification_id"] == right["qualification_id"]
        and previous["left_audit_id"] == left["old_domain_audit_id"]
        and previous["right_audit_id"] == right["old_domain_audit_id"],
        "panel_quotient_comparison.old_pair_parents",
    )
    require(
        previous["relation"] == "equivalent"
        and previous["equivalent"] is True
        and previous.get("retained_difference_witness") is None
        and isinstance(previous.get("correspondence"), dict),
        "panel_quotient_comparison.old_clean_equivalence",
    )
    for sidecar in (left, right):
        require(
            sidecar["supported"] and sidecar["old_projection_supported"] is True,
            "panel_quotient_comparison.clean_old_support",
        )
        graph = sidecar["behavior_projection"]
        audit = sidecar.get("source_domain_audit")
        require(isinstance(audit, dict), "panel_quotient_comparison.original_audit_required")
        assert isinstance(audit, dict)
        domain._identity(audit, "session_audit")
        actual = audit["actual_decision_graph"]
        domain._identity(actual, "actual_decision_graph")
        require(
            audit["id"] == sidecar["old_domain_audit_id"]
            and actual["id"] == sidecar["source_actual_graph_id"]
            and all(
                audit[key] == sidecar[key]
                for key in (
                    "session_id",
                    "task_id",
                    "context_id",
                    "protocol_id",
                    "registry_hash",
                )
            )
            and audit["projection_supported"] is True
            and actual["non_accept_event_ledger"] == [],
            "panel_quotient_comparison.original_audit_graph_binding",
        )
        source = audit["finite_projection"]
        require(
            isinstance(source, dict)
            and set(source) == {"nodes", "final"}
            and canonical_json_bytes(source["nodes"]) == canonical_json_bytes(actual["nodes"])
            and graph["retained_interactions"] == []
            and canonical_json_bytes({"nodes": graph["nodes"], "final": graph["final"]})
            == canonical_json_bytes(source),
            "panel_quotient_comparison.clean_base_not_unchanged",
        )
    mapping = previous["correspondence"]
    left_graph, right_graph = (value["behavior_projection"] for value in (left, right))
    require(
        set(mapping) == {node["node_id"] for node in right_graph["nodes"]}
        and set(mapping.values()) == {node["node_id"] for node in left_graph["nodes"]}
        and len(mapping) == len(set(mapping.values()))
        and all(isinstance(key, str) and isinstance(value, str) for key, value in mapping.items()),
        "panel_quotient_comparison.old_mapping_bijection",
    )
    require(
        canonical_json_bytes(domain._ordered_graph(left_graph, {}))
        == canonical_json_bytes(domain._ordered_graph(right_graph, mapping)),
        "panel_quotient_comparison.old_mapping_no_longer_matches",
    )
    return _result(
        left,
        right,
        correspondence=mapping,
        new_isomorphism_search=False,
        derived_from_old_pair_id=old_pair["id"],
    )
