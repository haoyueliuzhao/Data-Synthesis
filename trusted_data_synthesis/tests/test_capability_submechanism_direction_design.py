from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import pytest
from pydantic import ValidationError

from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_mechanism_information_geometry import (  # noqa: E501
    CONFIRMED_MECHANISM_IDS,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_submechanism_catalog import (  # noqa: E501
    make_candidate_specs,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_submechanism_direction_design import (  # noqa: E501
    CapabilitySubmechanismSpec,
    StructuralDirectionThresholds,
    SubmechanismActionGraph,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_submechanism_direction_runner import (  # noqa: E501
    make_structural_gates,
    run_direction_design,
    select_submechanisms,
    structural_geometry,
)


def test_submechanism_catalog_is_balanced_and_mechanically_witnessed() -> None:
    candidates = make_candidate_specs()

    assert len(candidates) == 24
    assert Counter(item.parent_mechanism_id for item in candidates) == {
        mechanism_id: 6 for mechanism_id in CONFIRMED_MECHANISM_IDS
    }
    assert all(
        item.capability_witnesses[axis]
        for item in candidates
        for axis, value in item.raw_capability_demand.items()
        if value > 0
    )


def test_submechanism_demand_and_graph_tampering_fail_closed() -> None:
    source = make_candidate_specs()[0]
    payload = source.model_dump(mode="json")
    payload["raw_capability_demand"]["retrieval"] += 1
    with pytest.raises(ValidationError, match="not mechanically derived"):
        CapabilitySubmechanismSpec.model_validate(payload)

    graph_payload = source.action_graph.model_dump(mode="json")
    graph_payload["nodes"][1]["depends_on"] = ["unknown_predecessor"]
    with pytest.raises(ValidationError, match="not topologically ordered"):
        SubmechanismActionGraph.model_validate(graph_payload)


def test_direction_selection_passes_preregistered_structural_gates() -> None:
    thresholds = StructuralDirectionThresholds()
    candidates = make_candidate_specs()
    first = select_submechanisms(candidates, thresholds=thresholds)
    second = select_submechanisms(candidates, thresholds=thresholds)
    geometry = structural_geometry(first, thresholds=thresholds)
    gates = make_structural_gates(
        candidates=candidates,
        selected=first,
        geometry=geometry,
        thresholds=thresholds,
    )

    assert tuple(item.submechanism_id for item in first) == tuple(
        item.submechanism_id for item in second
    )
    assert Counter(item.parent_mechanism_id for item in first) == {
        mechanism_id: 5 for mechanism_id in CONFIRMED_MECHANISM_IDS
    }
    assert geometry.residual_numerical_rank >= 5
    assert geometry.residual_effective_rank >= 4
    assert min(geometry.parent_support_per_axis.values()) >= 2
    assert all(item.passed for item in gates)


def test_direction_report_blocks_api_until_runtime_population_exists(tmp_path: Path) -> None:
    source = tmp_path / "v25_23_report.json"
    source.write_text(
        json.dumps(
            {
                "report_id": "finance_v25_23_fixture",
                "confirmed_mechanism_ids": list(CONFIRMED_MECHANISM_IDS),
                "information_geometry_ready": False,
                "next_permitted_stage": "capability_mechanism_support_redesign_only",
                "failure_codes": [
                    "raw_effective_rank",
                    "raw_condition_number",
                    "residual_numerical_rank",
                    "residual_effective_rank",
                ],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    output = tmp_path / "direction"

    report = run_direction_design(
        source_geometry_report_path=source,
        output_dir=output,
        run_id="v25_24_test",
    )

    assert report.structural_geometry_ready is True
    assert report.runtime_population_ready is False
    assert report.api_calls == report.model_tokens == report.gpu_jobs == 0
    assert report.next_permitted_stage == "submechanism_runtime_implementation_only"
    assert report.failure_codes == ("runtime_implementation_coverage",)
    assert (output / "finance_capability_submechanism_direction_report.md").is_file()
    with pytest.raises(ValueError, match="immutable"):
        run_direction_design(
            source_geometry_report_path=source,
            output_dir=output,
            run_id="v25_24_test",
        )
