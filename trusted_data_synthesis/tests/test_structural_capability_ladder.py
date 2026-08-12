from __future__ import annotations

import copy

from trusted_synthesis.experiments.vtdo_experiment.phase1_public_contract_satisfiability import (
    _replace_runtime_operation_refs,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_structural_capability_ladder import (
    structural_group_invariant_failures,
)


def _structural_variant(tier: str) -> dict[str, object]:
    evidence_count = {
        "easy_control": 2,
        "frontier": 3,
        "hard_control": 4,
    }[tier]
    evidence = [
        {
            "evidence_id": f"evidence:{index}",
            "subject": {"subject_id": "entity:alpha"},
            "predicate": "revenue",
            "temporal_context": {"label": f"FY202{index}"},
            "definition": {"definition_id": "metric:revenue"},
            "source": {"source_id": "official-filing"},
        }
        for index in range(1, evidence_count + 1)
    ]
    nodes = []
    for index in range(1, evidence_count):
        input_refs = [
            {
                "kind": "evidence" if index == 1 else "operation",
                "ref_id": "evidence:1" if index == 1 else f"node:{index - 1}",
            },
            {
                "kind": "evidence",
                "ref_id": f"evidence:{index + 1}",
            },
        ]
        nodes.append(
            {
                "node_id": f"node:{index}",
                "operator_id": "mean",
                "input_refs": input_refs,
            }
        )
    return {
        "family": "finance.calculation_chain",
        "tier": tier,
        "evidence_bundle": {"evidence": evidence},
        "public_corpus": {"evidence": copy.deepcopy(evidence)},
        "task": {
            "oracle": {
                "task_program": {
                    "nodes": nodes,
                    "output_node_id": nodes[-1]["node_id"],
                }
            }
        },
        "structure": {
            "operation_count": len(nodes),
            "operation_dag_depth": len(nodes),
        },
        "verification": {"passed": True},
    }


def _structural_group() -> list[dict[str, object]]:
    return [
        _structural_variant(tier)
        for tier in ("easy_control", "frontier", "hard_control")
    ]


def test_structural_ladder_requires_nested_gold_and_increasing_program_depth() -> None:
    variants = _structural_group()

    assert structural_group_invariant_failures(variants) == ()

    depth_mutation = copy.deepcopy(variants)
    depth_mutation[-1]["structure"]["operation_dag_depth"] = 2
    assert "operation_dag_depth" in structural_group_invariant_failures(
        depth_mutation
    )

    nesting_mutation = copy.deepcopy(variants)
    nesting_mutation[1]["evidence_bundle"]["evidence"][0]["evidence_id"] = (
        "evidence:other"
    )
    assert "nested_gold" in structural_group_invariant_failures(nesting_mutation)


def test_structural_ladder_rejects_unreferenced_and_extra_public_evidence() -> None:
    variants = _structural_group()
    reference_mutation = copy.deepcopy(variants)
    reference_mutation[-1]["task"]["oracle"]["task_program"]["nodes"][-1][
        "input_refs"
    ][1]["ref_id"] = "evidence:3"
    assert "evidence_reference_coverage" in structural_group_invariant_failures(
        reference_mutation
    )

    corpus_mutation = copy.deepcopy(variants)
    corpus_mutation[0]["public_corpus"]["evidence"].append(
        {"evidence_id": "evidence:distractor"}
    )
    assert "public_corpus_not_gold" in structural_group_invariant_failures(
        corpus_mutation
    )


def test_runtime_operation_references_are_canonicalized_recursively() -> None:
    value = {
        "winner": "runtime:opaque:2",
        "rows": [
            {"source": "runtime:opaque:1"},
            ("runtime:opaque:2", "literal"),
        ],
    }

    assert _replace_runtime_operation_refs(
        value,
        {
            "runtime:opaque:1": "node:1",
            "runtime:opaque:2": "node:2",
        },
    ) == {
        "winner": "node:2",
        "rows": [
            {"source": "node:1"},
            ("node:2", "literal"),
        ],
    }
