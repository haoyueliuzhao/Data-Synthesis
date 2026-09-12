import json

import pytest

from trusted_synthesis.experiments.finance_qa_vnext_eval_readiness import power


def rows():
    return [
        {
            "task_id": str(i),
            "family": "dual_sufficient",
            "source_cluster": str(i // 2),
            "period_ids": ["p1", "p2"],
        }
        for i in range(4)
    ]


def test_independence_is_explicit_scenario_not_default_inference():
    assert power.covariance_sum(rows(), 0, 0) == 4
    result = power.describe(rows())
    assert not result["independence_assumed_by_default"]
    assert not result["adequate_power_established"]


def test_actual_shared_membership_gram_not_raw_overlap_count():
    assert power.covariance_sum(rows(), 0.5, 0) == 6
    assert power.covariance_sum(rows(), 0, 0.5) == pytest.approx(6)
    disjoint = rows()
    for row in disjoint:
        row["period_ids"] = [row["task_id"]]
    assert power.covariance_sum(disjoint, 0, 0.5) == 4


def test_scenario_is_PSD_and_no_seed_multiplication():
    with pytest.raises(ValueError):
        power.covariance_sum(rows(), 0.8, 0.8)
    with pytest.raises(ValueError):
        power.describe(rows() + rows())
    assert power.run({"dev": rows()})["actual_Student_observations"] == 0


def test_small_source_cluster_limitation_preserved():
    result = power.describe(rows())
    assert result["source_clusters"] == 2 and result["largest_source_task_share"] == 0.5
    assert power.policy()["normal_approximation_fragile_with_few_clusters"]
    assert len(result["scenarios"]) == len(power.SCENARIOS) * len(power.VARIANCES)


def test_entire_frozen_protocol_is_JSON_roundtrip_stable():
    from trusted_synthesis.experiments.finance_qa_vnext_eval_readiness import panel, protocol

    value = protocol.policy(panel.policy())
    assert json.loads(json.dumps(value)) == value
