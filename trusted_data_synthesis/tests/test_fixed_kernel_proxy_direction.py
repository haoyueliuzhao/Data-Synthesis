"""New finite-support cross-direction checks; no real feedback replay."""

import importlib
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
d = importlib.import_module("fixed_kernel_proxy_direction_20260919")


def geometry():
    pi = {"x": {"a": 0.5, "b": 0.5}}
    return d.Geometry([("x", "a"), ("x", "b")], pi, pi, {"x": 1.0}, [])


def test_cross_direction_is_not_the_same_as_self_score():
    rows = [
        dict(index=0, task_id="x", source_cluster="c", repeat=1),
        dict(index=1, task_id="x", source_cluster="c", repeat=2),
    ]
    result = d.repeat_analysis(
        np.array([[1.0, -1.0], [-1.0, 1.0]]), rows, geometry(), "c_only_anchored"
    )
    assert result["halves"][1]["self_score"] > 0
    assert result["cross"]["S_1_to_2"] < 0 and result["cross"]["S_2_to_1"] < 0
    assert result["fixed_repeat_denominator"] == 180 and result["fixed_total_denominator"] == 360
    assert len(result["leave_one_positive_out"]) == 2


def test_zero_repeat_is_uninformative_and_not_regrouped():
    rows = [dict(index=0, task_id="x", source_cluster="c", repeat=1)]
    result = d.repeat_analysis(np.array([[1.0], [-1.0]]), rows, geometry(), "full_anchored_vtdo")
    assert result["halves"][2]["status"] == "UNINFORMATIVE_ZERO_HALF"
    assert result["cross"]["S_1_to_2"] is None
    assert result["leave_one_positive_out"][0]["reduced_half_status"] == "UNINFORMATIVE_ZERO_HALF"
