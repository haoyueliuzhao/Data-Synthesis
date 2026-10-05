"""CPU-only tests of fixed weighting, intervention dose, and feedback joins."""

import copy
import importlib.util
from pathlib import Path

import pytest

SPEC = importlib.util.spec_from_file_location(
    "intervention_audit",
    Path(__file__).resolve().parents[1] / "scripts/finqa_v24_intervention_feedback_audit.py",
)
audit = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(audit)


def fixture():
    support = {
        "a": {"states": {"x": 3, "y": 1}, "n_x": 4, "chi": {"x": 0, "y": 1}},
        "b": {"states": {"x": 1}, "n_x": 1, "chi": {"x": None}},
    }
    mu = {"a": "1/2", "b": "1/2"}
    features = {"finqa/" + t: {field: t for field in audit.FIELDS} for t in support}
    return support, mu, features


def test_package_count_does_not_change_task_mass_and_chi_mass_changes():
    support, mu, features = fixture()
    prior = audit.prior_from_support(support)
    plus = audit.manual_distribution(prior, support, 1)
    before = audit.empirical_mass(prior, support, mu, features)
    after = audit.empirical_mass(plus, support, mu, features)
    assert before["total_mass"] == pytest.approx(1)
    assert after["total_mass"] == pytest.approx(1)
    assert before["max_abs_task_mass_minus_mu"] < 1e-15
    assert after["max_abs_task_mass_minus_mu"] < 1e-15
    assert before["chi_supervision_mass"]["1"] == pytest.approx(0.125)
    assert after["chi_supervision_mass"]["1"] == pytest.approx(0.2)
    assert after["chi_supervision_mass"]["null_registered_singleton"] == 0.5
    assert after["chi_supervision_mass_by_public_group"]["company"]["a"] == {"0": 0.3, "1": 0.2}


def test_tv_is_task_weighted_and_moved_count_uses_conditional_tv():
    support, mu, features = fixture()
    prior = audit.prior_from_support(support)
    plus = audit.manual_distribution(prior, support, 1)
    result = audit.task_dose(prior, plus, mu, support, features, tolerance=0.1)
    assert result["weighted_TV"] == pytest.approx(0.075)
    assert result["effective_moved_tasks"] == 1  # Conditional TV .15; dose .075.
    assert result["effective_moved_task_ids"] == ["a"]
    assert result["grouped_dose"]["company"]["top1_share"] == 1


def test_missing_task_and_non_simplex_never_silently_repaired():
    support, _, _ = fixture()
    prior = audit.prior_from_support(support)
    with pytest.raises(ValueError, match="task support"):
        audit.validate_distribution({"a": prior["a"]}, support)
    prior["a"]["x"] = 1.0
    with pytest.raises(ValueError, match="simplex"):
        audit.validate_distribution(prior, support)


def test_single_group_manual_unchanged_and_null_only_singleton():
    support, mu, features = fixture()
    support["a"]["chi"] = {"x": 0, "y": 0}
    prior = audit.prior_from_support(support)
    assert audit.manual_distribution(prior, support, 1) == prior
    support["a"]["chi"] = {"x": None, "y": None}
    with pytest.raises(ValueError, match="null chi"):
        audit.empirical_mass(prior, support, mu, features)


def feedback_fixture():
    identity = {"point_id": "point-A", "parameter_digest": "parameters"}
    tasks = ["finqa/a", "finqa/b"]
    draws = []
    for seed in (11, 29):
        keys = [
            audit.digest(
                {
                    "dataset": "finqa",
                    "task_id": t.removeprefix("finqa/"),
                    "seed": seed,
                    "point_id": identity["point_id"],
                }
            )
            for t in tasks
        ]
        run = {
            "provider": identity,
            "role": "feedback",
            "config": {"role": "feedback", "seed": seed},
            "registered_denominator": 2,
            "source_manifest_sha256": "source",
            "tasks": tasks,
            "episode_keys": keys,
        }
        run["id"] = audit.digest(run)
        seal = {
            "run_id": run["id"],
            "complete": True,
            "all_provider_calls_settled": True,
            "registered_denominator": 2,
            "episodes": [{"key": key} for key in keys],
        }
        seal["id"] = audit.digest(seal)
        draws.append((run, seal))
    intent = {
        "identity": identity,
        "denominator": 4,
        "source_manifest_sha256": "source",
        "task_ids": ["a", "b"],
        "seeds": [11, 29],
    }
    rewards = {
        "cohort_seal_sha256": "cohort",
        "rewards": [1, 0, 0, 0],
        "scores": [
            {"task_id": t, "native": {"execution_accuracy": r}}
            for t, r in zip(["a", "b", "a", "b"], [1, 0, 0, 0], strict=True)
        ],
    }
    evidence = {
        "feedback_seal_sha256": "cohort",
        "actual_feedback_denominator": 4,
        "feedback_report": {
            "cohort_seal_sha256": "cohort",
            "source_manifest_sha256": "source",
            "reward_sha256": audit.digest(rewards["rewards"]),
        },
    }
    return draws, rewards, intent, evidence, tasks


def test_feedback_join_preserves_full_zero_denominator_and_repeat_keys():
    args = feedback_fixture()
    joined = audit.feedback_join(*args)
    assert len(joined) == 4 and sum(joined.values()) == 1
    assert joined["finqa/b", 11] == joined["finqa/b", 29] == 0
    overlap = audit.pair_overlap(joined)
    assert overlap["both"] == 0 and overlap["either"] == 1 and overlap["neither"] == 1
    assert overlap["Jaccard"] == 0


@pytest.mark.parametrize(
    "mutation,message",
    [
        ("score_order", "native reward task order"),
        ("cohort", "seal binding"),
        ("partial", "feedback lengths"),
        ("run", "run content identity"),
        ("seal", "generation seal identity"),
    ],
)
def test_feedback_join_rejects_identity_order_and_denominator_changes(mutation, message):
    draws, rewards, intent, evidence, tasks = copy.deepcopy(feedback_fixture())
    if mutation == "score_order":
        rewards["scores"][0]["task_id"] = "b"
    elif mutation == "cohort":
        rewards["cohort_seal_sha256"] = "wrong"
    elif mutation == "partial":
        rewards["rewards"].pop()
    elif mutation == "run":
        draws[0][0]["tasks"] = ["finqa/b", "finqa/a"]
    else:
        draws[0][1]["complete"] = False
    with pytest.raises(ValueError, match=message):
        audit.feedback_join(draws, rewards, intent, evidence, tasks)


def test_group_success_rate_uses_all_exposures_and_zeros_retained():
    _, _, features = fixture()
    rows = [
        {"task_positive_counts": {"finqa/a": 1, "finqa/b": 0}},
        {"task_positive_counts": {"finqa/a": 2, "finqa/b": 0}},
    ]
    result = audit.feedback_summary(rows, ["finqa/a", "finqa/b"], features)
    assert result["reward_denominator"] == 8 and result["positive_rewards"] == 3
    assert result["never_positive_tasks"] == 1
    assert result["family_success_rates"]["company"]["a"]["success_rate"] == 0.75
    assert result["family_success_rates"]["company"]["b"]["exposures"] == 4
    assert result["positive_count_mass"]["company"]["mass"]["b"] == 0


def test_zero_mass_concentration_does_not_invent_probabilities():
    result = audit.normalized_concentration({"a": 0, "b": 0})
    assert result["HHI"] is None and result["top1_share"] is None
    assert result["nonzero_groups"] == 0
