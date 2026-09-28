"""Behavior-state mapping for source-proved material, not wording or route labels."""

from __future__ import annotations

from .contracts import digest


def mapper_rules():
    body = {
        "version": "finqa_proved_behavior_mapper_v1",
        "basis": [
            "proved_source_cells",
            "canonical_dependency_DAG",
            "actually_executed_dependency_DAGs",
            "necessary_recovery",
            "delivery_mode",
        ],
        "ignored": [
            "wording",
            "slot",
            "seed",
            "NLL",
            "duplicate_reads",
            "duplicate_calculations",
            "interchangeable_execution_order",
            "commutative_operand_order",
        ],
        "no_requested_route_state": True,
        "no_minimum_state_count": True,
        "single_state_remains_static": True,
        "verification_not_claimed_without_distinct_proof": True,
        "necessary_recovery_definition": (
            "earlier failed calculate with the same alpha-renamed expression shape, followed "
            "by a source-proved necessary successful calculation; not inferred mental intent"
        ),
    }
    return {**body, "id": "finqa_state_mapper:" + digest(body)}


def map_proved_state(task_id: str, proof: dict):
    """Consume the assessor's computed semantic proof, not a requested state name."""
    if proof.get("semantic_obligations_passed") is not True:
        raise ValueError("unproved trajectories cannot create a material state")
    required = {"source_cells", "dependency_DAG", "necessary_recovery", "delivery_mode"}
    if not required <= set(proof) or proof["delivery_mode"] not in {
        "declarative_program",
        "actually_executed_calculation",
    }:
        raise ValueError("incomplete proved state basis")
    basis = {
        "task_id": task_id,
        "source_cells": sorted(
            proof["source_cells"], key=lambda cell: (cell["source_id"], cell["row"], cell["column"])
        ),
        "dependency_DAG": proof["dependency_DAG"],
        "executed_dependency_DAGs": sorted(
            {digest(node): node for node in proof.get("executed_dependency_DAGs", [])}.values(),
            key=repr,
        ),
        "necessary_recovery": bool(proof["necessary_recovery"]),
        "delivery_mode": proof["delivery_mode"],
    }
    return {
        "state_id": "finqa_state:" + digest(basis),
        "basis": basis,
        "mapper_rule_id": mapper_rules()["id"],
    }
