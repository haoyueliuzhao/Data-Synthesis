"""Replay only the two frozen share trajectories; never execute a new candidate."""

from __future__ import annotations

import copy
import json
from decimal import Decimal, localcontext
from pathlib import Path
from typing import Any

import pytest

from trusted_synthesis.canonical_json import canonical_json_bytes
from trusted_synthesis.experiments.qa_reasoning_part_whole_share import runtime
from trusted_synthesis.experiments.qa_reasoning_part_whole_share.comparison import (
    compare_records,
    project_records,
)
from trusted_synthesis.experiments.qa_reasoning_part_whole_share.controls import (
    rehash_records,
    run_controls,
)
from trusted_synthesis.experiments.qa_reasoning_part_whole_share.models import record
from trusted_synthesis.experiments.qa_reasoning_part_whole_share.validation import (
    read_trajectory_records,
    validate_records,
    validate_trajectory,
)

ROOT = Path(__file__).resolve().parents[2]
FORMAL = ROOT / (
    "trusted_data_synthesis/artifacts/qa_reasoning_part_whole_share/"
    "finance_qa_vnext_part_whole_share_dual_support_preflight_v1_20260905"
)


@pytest.fixture(autouse=True)
def forbid_runtime(monkeypatch: pytest.MonkeyPatch) -> None:
    def forbidden(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("semantic tests may only replay frozen Runtime bytes")

    monkeypatch.setattr(runtime, "run_candidate", forbidden)
    for executor in (
        runtime.RelationSumExecutor,
        runtime.ShareRatioExecutor,
        runtime.ScalePercentExecutor,
    ):
        monkeypatch.setattr(executor, "execute", forbidden)


@pytest.fixture(scope="module")
def frozen() -> dict[str, Any]:
    def read(name: str) -> Any:
        return json.loads((FORMAL / name).read_bytes())

    return {
        "contract": read("contract.json"),
        "source": read("source_binding.json"),
        "D": read_trajectory_records(FORMAL / "runtime/D"),
        "S": read_trajectory_records(FORMAL / "runtime/S"),
        "validation_D": read("validation_D.json"),
        "validation_S": read("validation_S.json"),
        "comparison": read("comparison.json"),
        "controls": read("controls.json"),
    }


@pytest.mark.parametrize("route", ["D", "S"])
def test_actual_persisted_route_replays_exactly(frozen: dict[str, Any], route: str) -> None:
    result = validate_trajectory(frozen["contract"], frozen["source"], FORMAL / "runtime" / route)
    assert canonical_json_bytes(result) == canonical_json_bytes(frozen[f"validation_{route}"])
    assert result["qa_valid"] and result["trajectory_valid"] and result["qualified"]
    assert result["answer_oracle"]["expected_answer"] == "93.508458"
    assert result["answer_oracle"]["candidate_execution"] is False
    assert result["answer_oracle"]["oracle_result_inserted_into_trajectory"] is False
    assert result["candidate_runtime_executions"] == 0
    assert result["coverage"]["numerator"] == result["coverage"]["denominator"] == 4


def test_s_ratio_consumes_actual_sum_claim_and_d_uses_disclosed_total(
    frozen: dict[str, Any],
) -> None:
    evidence = frozen["source"]["evidence"]
    total = evidence["total"]["id"]
    sum_step, ratio_step, percent_step = frozen["S"]["steps"]
    denominator = ratio_step["execution"]["inputs"][1]
    assert denominator["kind"] == "claim"
    assert denominator["ref_id"] == sum_step["claim"]["id"] != total
    assert denominator["producer_operation"] == "relation_sum"
    assert denominator["lineage"] == sorted(
        evidence[role]["id"] for role in ("freight", "other", "part_whole")
    )
    assert total not in denominator["lineage"]
    assert sum_step["update"]["accepted_claim_id"] == denominator["ref_id"]
    assert percent_step["execution"]["inputs"][0]["ref_id"] == ratio_step["claim"]["id"]
    with localcontext() as context:
        context.prec = 50
        reconstructed = sum(
            (Decimal(item["value"]) for item in sum_step["execution"]["inputs"][:2]),
            Decimal(0),
        )
        actual_ratio = Decimal(ratio_step["execution"]["inputs"][0]["value"]) / reconstructed
    assert reconstructed == Decimal(denominator["value"]) == Decimal("21813")
    assert actual_ratio == Decimal(ratio_step["execution"]["output"]["value"])
    assert [step["execution"]["operation"] for step in frozen["D"]["steps"]] == [
        "share_ratio",
        "scale_percent",
    ]
    direct = frozen["D"]["steps"][0]["execution"]["inputs"][1]
    assert direct["kind"] == "evidence" and direct["ref_id"] == total
    assert frozen["validation_D"]["coverage"] == frozen["validation_S"]["coverage"]


def test_original_same_pair_comparison_replays_without_new_candidate_or_pair(
    frozen: dict[str, Any],
) -> None:
    replay = compare_records(frozen["contract"], frozen["source"], frozen["D"], frozen["S"])
    assert canonical_json_bytes(replay) == canonical_json_bytes(frozen["comparison"])
    assert replay["status"] == "different_retained_semantics"
    assert replay["W_share"] == 1 and replay["formal_class_count"] == 2
    assert replay["retained_difference_witnesses"]
    assert replay["both_final_answers_equal"] is True
    assert replay["graph_hash_used_as_authority"] is False
    assert replay["route_label_used_as_authority"] is False
    assert replay["node_count_used_as_authority"] is False


def test_projection_retains_actual_source_member_relation_and_updates(
    frozen: dict[str, Any],
) -> None:
    direct = project_records(frozen["contract"], frozen["source"], frozen["D"])
    reconstructed = project_records(frozen["contract"], frozen["source"], frozen["S"])
    assert direct["status"] == reconstructed["status"] == "projected"
    d_support = direct["projection"]["denominator_support"]
    s_support = reconstructed["projection"]["denominator_support"]
    assert d_support["kind"] == "evidence"
    assert d_support["actual_support"]["metric"] == "total_operating_revenues"
    assert s_support["kind"] == "claim"
    claim = s_support["actual_support"]
    assert claim["operation_contract"]["operation"] == "relation_sum"
    assert claim["actual_parameters"] == {"method": "sum"}
    members = claim["actual_uses"][:2]
    assert {member["actual_support"]["metric"] for member in members} == {
        "total_freight_revenues",
        "other_revenues",
    }
    assert all(
        member["actual_support"]["source_record_id"] == "UNP/2015/page_56.pdf-1"
        for member in members
    )
    relation = claim["actual_uses"][2]
    assert relation["role"] == "relation"
    assert relation["actual_support"]["exhaustive"] is True
    assert relation["actual_support"]["nonoverlapping"] is True
    assert relation["actual_support"]["total_target"]["value_is_arithmetic_operand"] is False
    assert claim["observation"]["success"] is True
    assert claim["claim"]["proposition"] == claim["observation"]["output"]
    assert claim["actual_update"]["accepted_this_observed_claim"] is True
    assert claim["actual_update"]["dependencies_accepted_before_consumption"] is True


def test_full_rehash_legal_sum_permutation_has_equal_projection(frozen: dict[str, Any]) -> None:
    swapped = copy.deepcopy(frozen["S"])
    lists = [
        swapped["candidate"]["nodes"][0]["inputs"],
        swapped["steps"][0]["proposal"]["inputs"],
        swapped["steps"][0]["execution"]["inputs"],
    ]
    for inputs in lists:
        inputs[0], inputs[1] = inputs[1], inputs[0]
    swapped = rehash_records(swapped)
    assert swapped["candidate"]["id"] != frozen["S"]["candidate"]["id"]
    actual = project_records(frozen["contract"], frozen["source"], frozen["S"])
    control = project_records(frozen["contract"], frozen["source"], swapped)
    assert control["validation"]["qualified"] is True
    assert control["status"] == "projected"
    assert canonical_json_bytes(control["projection"]) == canonical_json_bytes(actual["projection"])
    assert control["candidate_runtime_executions"] == control["formal_pair_comparisons"] == 0


def test_all_eight_frozen_controls_replay_without_runtime(frozen: dict[str, Any]) -> None:
    controls = run_controls(frozen["contract"], frozen["source"], frozen["S"])
    assert canonical_json_bytes(controls) == canonical_json_bytes(frozen["controls"])
    assert controls["attempted"] == controls["rejected"] == 8
    assert controls["all_rejected"] is True
    assert controls["candidate_runtime_executions"] == controls["extra_formal_semantic_pairs"] == 0
    bypass = controls["controls"][-1]
    assert bypass["all_prospective_objects_rehashed"] is True
    assert bypass["answer_bytes_retained"] is True
    assert bypass["validation"]["qa_valid"] is True
    assert bypass["validation"]["trajectory_valid"] is False
    assert bypass["validation"]["first_failure"]["stage"] == "replay.claimed_denominator_support"


@pytest.mark.parametrize("parameters", [{}, {"method": "mean"}, {"method": "sum", "unused": True}])
def test_full_rehash_wrong_parameters_are_not_erased(
    frozen: dict[str, Any], parameters: dict[str, Any]
) -> None:
    bad = copy.deepcopy(frozen["S"])
    bad["candidate"]["nodes"][0]["parameters"] = parameters
    bad["steps"][0]["proposal"]["parameters"] = parameters
    bad["steps"][0]["execution"]["parameters"] = parameters
    bad = rehash_records(bad)
    report = validate_records(frozen["contract"], frozen["source"], bad)
    assert report["qa_valid"] is True and report["trajectory_valid"] is False
    assert report["first_failure"]["stage"] == "replay.parameters"
    assert project_records(frozen["contract"], frozen["source"], bad)["status"] == "undetermined"


def test_missing_actual_observation_cannot_be_projected(frozen: dict[str, Any]) -> None:
    missing = copy.deepcopy(frozen["S"])
    del missing["steps"][0]["observation"]
    result = project_records(frozen["contract"], frozen["source"], missing)
    assert result["status"] == "undetermined" and result["projection"] is None
    assert result["validation"]["qualified"] is False


def test_unsupported_measurement_stays_undetermined_even_if_own_qualified(
    frozen: dict[str, Any],
) -> None:
    contract = copy.deepcopy(frozen["contract"])
    contract["measurement"]["unsupported_new_semantics"] = "not implemented"
    contract = record(
        "contract", **{k: v for k, v in contract.items() if k not in {"id", "schema_version"}}
    )
    candidate = copy.deepcopy(frozen["S"])
    candidate["candidate"]["contract_id"] = contract["id"]
    candidate = rehash_records(candidate)
    result = project_records(contract, frozen["source"], candidate)
    assert result["validation"]["qualified"] is True
    assert result["status"] == "undetermined" and result["projection"] is None
    assert result["reason"] == "frozen measurement rule contract differs"
