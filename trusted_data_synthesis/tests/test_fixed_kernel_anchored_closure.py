"""Cheap score/metadata checks, not training or financial re-evaluation."""

import importlib
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
c = importlib.import_module("fixed_kernel_anchored_closure_20260919")


def fixture_scores():
    tasks = [
        dict(task_id=f"{group}_{i}", group=group, source_cluster=f"CIK{i}")
        for group in c.GROUPS
        for i in range(3)
    ]
    scores = {
        (arm, seed): {row["task_id"]: int(arm == "Static") for row in tasks}
        for arm in c.ARMS
        for seed in c.SEEDS
    }
    return tasks, scores


def test_paired_counts_sign_and_shared_cluster_weights():
    tasks, scores = fixture_scores()
    result = c.paired_statistics(tasks, scores, draws=50)
    assert len(result["pairs"]) == 27
    effect = result["contrasts"]["Full_minus_Static"]
    assert effect["gain"] == 0 and effect["loss"] == 27 and effect["net"] == -27
    assert effect["point"] == -1 and effect["descriptive_CIK_percentile95"] == [-1, -1]
    same = result["contrasts"]["Full_minus_C_only"]
    assert same["unchanged"] == 27 and same["descriptive_CIK_percentile95"] == [0, 0]
    assert result["resampling"]["same_weights_all_arms_and_seeds"]


def test_missing_score_is_not_zero_reward():
    tasks, scores = fixture_scores()
    del scores[("Full", 11)][tasks[0]["task_id"]]
    with pytest.raises(ValueError, match="complete paired score coverage"):
        c.paired_statistics(tasks, scores, draws=5)


def test_nonzero_novelty_potential_does_not_enable_c_only_term():
    update = {"novelty_active": True, "numeric_core_update": {"effective_novelty_exponent": 0.0}}
    result = c.novelty_fields(update)
    assert result["novelty_potential_nonzero"] and not result["novelty_term_active"]
    update["numeric_core_update"]["effective_novelty_exponent"] = 0.2
    assert c.novelty_fields(update)["novelty_term_active"]
    update["novelty_active"] = False
    assert not c.novelty_fields(update)["novelty_term_active"]
