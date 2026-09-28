import pytest

from trusted_synthesis.finance_research.state_mapping import map_proved_state, mapper_rules


def proof():
    return {
        "semantic_obligations_passed": True,
        "source_cells": [
            {"source_id": "table:0", "row": 1, "column": 2},
            {"source_id": "table:0", "row": 1, "column": 1},
        ],
        "dependency_DAG": ("subtract", ("leaf", "current"), ("leaf", "prior")),
        "necessary_recovery": False,
        "delivery_mode": "declarative_program",
    }


def test_mapper_ignores_slot_wording_and_source_list_order_but_keeps_actual_delivery():
    one = map_proved_state("task", proof())
    changed = {
        **proof(),
        "slot": 7,
        "wording": "different",
        "source_cells": list(reversed(proof()["source_cells"])),
    }
    assert one["state_id"] == map_proved_state("task", changed)["state_id"]
    assert (
        one["state_id"]
        != map_proved_state("task", {**proof(), "delivery_mode": "actually_executed_calculation"})[
            "state_id"
        ]
    )
    assert mapper_rules()["no_minimum_state_count"]


def test_mapper_rejects_unproved_input_instead_of_assigning_requested_route():
    with pytest.raises(ValueError, match="unproved"):
        map_proved_state(
            "task", {"semantic_obligations_passed": False, "requested_route": "second"}
        )
