"""Synthetic-only issuer-cluster adapter tests; frozen kernel has its own suite."""

import copy
import hashlib
import json
from collections import Counter

import cross_market_statistics_20260926 as s
import pytest


def fixture(count=1):
    cluster = "issuer:" + "a" * 64
    tasks, outcomes = [], []
    rows = [
        dict(
            security_id=security,
            issuer_cluster_id=cluster,
            admitted=True,
            legal_name="Issuer",
            exposure=dict(project_source_identity_screen_passed=True),
            document_bindings=[dict(raw_object_id="raw-" + security, admitted=True)],
        )
        for security in ("CN-A", "HK-H")
    ]
    admission = seal(
        dict(schema_version="cross_market_calibration.v1.cross_market_issuer_admission", rows=rows)
    )
    for group in s.GROUPS:
        for i in range(count):
            security = "CN-A" if i % 2 == 0 else "HK-H"
            task = f"{group}-{i}"
            tasks.append(
                dict(
                    task_id=task,
                    group=group,
                    security_id=security,
                    issuer_cluster_id=cluster,
                    raw_object_ids=["raw-" + security],
                )
            )
            for seed in s.SEEDS:
                for arm in s.ARMS:
                    for mode, repeats in s.DECODING_REPEATS.items():
                        for repeat in repeats:
                            outcomes.append(
                                dict(
                                    task_id=task,
                                    seed=seed,
                                    arm=arm,
                                    decoding=mode,
                                    repeat=repeat,
                                    Q=int(arm == "positive"),
                                )
                            )
    return tasks, outcomes, admission


def seal(value):
    body = {k: v for k, v in value.items() if k != "id"}
    sha = hashlib.sha256(
        json.dumps(
            body, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode()
    ).hexdigest()
    return dict(**body, id="cross_market_issuer_admission:" + sha)


def run(tasks, outcomes, admission):
    return s.analyze_synthetic_for_test(
        tasks,
        outcomes,
        admission,
        sizes=Counter(r["group"] for r in tasks),
        replicates=11,
        max_draws=100,
    )


def test_different_securities_share_one_evidenced_issuer_and_never_fake_CIK():
    data = fixture(2)
    result = run(*data)
    assert result["bootstrap"]["cluster_count"] == 1
    assert result["bootstrap"]["unit"] == "evidenced_legal_issuer_cluster"
    assert "cik" not in json.dumps(result).lower()
    assert all(v["point_estimate_rational"] == "1/1" for v in result["comparisons"].values())
    assert not result["cross_market_stochastic_support"]  # synthetic never supports production
    assert s.core._validate is not s.validate


@pytest.mark.parametrize(
    "cluster", ["00001", 1, "cik:0000000001", "issuer:00001", "issuer:" + "A" * 64]
)
def test_security_code_or_CIK_is_not_valid_issuer_cluster(cluster):
    tasks, outcomes, admission = fixture()
    tasks[0]["issuer_cluster_id"] = cluster
    with pytest.raises(ValueError, match="opaque_issuer_id"):
        run(tasks, outcomes, admission)


@pytest.mark.parametrize(
    "which", ["issuer", "document", "wrong_document", "cluster", "digest", "project_history"]
)
def test_admission_is_required_for_each_task_and_document(which):
    tasks, outcomes, admission = fixture()
    if which == "issuer":
        admission["rows"][0]["admitted"] = False
    elif which == "document":
        admission["rows"][0]["document_bindings"][0]["admitted"] = False
    elif which == "wrong_document":
        tasks[0]["raw_object_ids"] = ["unregistered"]
    elif which == "cluster":
        tasks[0]["issuer_cluster_id"] = "issuer:" + "b" * 64
    elif which == "project_history":
        admission["rows"][0]["exposure"]["project_source_identity_screen_passed"] = False
    if which != "digest":
        admission = seal(admission)
    else:
        admission["rows"][0]["legal_name"] = "tampered"
    with pytest.raises(ValueError):
        run(tasks, outcomes, admission)


@pytest.mark.parametrize(
    "field,value",
    [
        ("seed", 12),
        ("repeat", 0),
        ("Q", 0.5),
        ("Q", "1"),
        ("arm", "delayed_c"),
        ("decoding", "combined"),
        ("issuer_cluster_id", "issuer:" + "b" * 64),
        ("cik", "1"),
    ],
)
def test_bad_or_mislabeled_outcomes_fail_closed(field, value):
    tasks, outcomes, admission = fixture()
    outcomes[0][field] = value
    with pytest.raises(ValueError):
        run(tasks, outcomes, admission)


def test_missing_duplicate_outcomes_and_tasks_rejected():
    tasks, outcomes, admission = fixture()
    for data in (
        (tasks, outcomes[:-1]),
        (tasks, outcomes + outcomes[:1]),
        (tasks + tasks[:1], outcomes),
    ):
        with pytest.raises(ValueError):
            run(*data, admission)


def test_modes_remain_separate_and_exact_zero_is_not_support():
    tasks, outcomes, admission = fixture()
    for row in outcomes:
        row["Q"] = int(
            row["arm"] == "positive" and row["decoding"] == "stochastic" and row["repeat"] == 1
        )
    result = run(tasks, outcomes, admission)
    assert (
        result["comparisons"]["stochastic_positive_minus_static"]["point_estimate_rational"]
        == "1/2"
    )
    assert (
        result["comparisons"]["greedy_positive_minus_negative"]["ci95"]["lower_rational"] == "0/1"
    )
    assert result["interpretation"]["zero_crossing_implies_equivalence"] is False


def test_production_is_fixed_180_4860_and_cannot_claim_original_training_value():
    with pytest.raises(ValueError, match="fixed_group_task_counts"):
        s.analyze(*fixture())
    result = s.analyze(*fixture(60))
    assert (result["task_count"], result["outcome_count"]) == (180, 4860)
    assert result["bootstrap"]["valid_replicates"] == 20000
    assert result["cross_market_stochastic_support"] is True
    assert result["full_400_step_independent_confirmation"] is False
    assert (
        result["interpretation"]["original_feedback_distribution_training_value_confirmed"] is False
    )


def test_order_invariance_and_admission_input_not_mutated():
    tasks, outcomes, admission = fixture(2)
    saved = copy.deepcopy(admission)
    assert run(tasks, outcomes, admission) == run(tasks[::-1], outcomes[::-1], admission)
    assert admission == saved
