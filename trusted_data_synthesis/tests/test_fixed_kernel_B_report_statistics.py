"""Small CPU-only arithmetic checks; no real experiment artifacts are opened."""

import importlib
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
s = importlib.import_module("fixed_kernel_B_report_statistics_20260925")


def test_pair_counts_and_exact_rate_difference():
    result = s._summary([(1, 1), (0, 1), (0, 1), (1, 0), (0, 0), (0, 0)])
    assert result["static"]["qualified"] == 2
    assert result["delayed_c"]["qualified"] == 3
    assert result["rate_difference_rational"] == "1/6"
    assert result["paired"] == {
        "both_pass": 1,
        "improved_static_fail_delayed_pass": 2,
        "degraded_static_pass_delayed_fail": 1,
        "both_fail": 2,
    }


@pytest.mark.parametrize("pairs", [[], [(0, 2)], [(True, 1)], [(0.0, 1)]])
def test_empty_or_nonbinary_pairs_rejected(pairs):
    with pytest.raises(ValueError):
        s._summary(pairs)


def test_signed_net_mass_not_small_overall_net_denominator():
    rows = [
        {"cik": str(index), "net_qualified_difference": difference}
        for index, difference in enumerate((5, 3, -7, 0))
    ]
    result = s._concentration(rows)
    assert result["positive_net_count_mass"] == 8
    assert result["absolute_negative_net_count_mass"] == 7
    assert result["net_count"] == 1
    assert result["positive_top_k"]["1"]["share_of_same_sign_net_mass"] == 5 / 8
    assert result["zero_net_cluster_count"] == 1


def test_zero_net_sources_do_not_create_undefined_percentages():
    result = s._concentration([{"cik": "1", "net_qualified_difference": 0}])
    assert result["positive_top_k"]["1"]["share_of_same_sign_net_mass"] is None
    assert result["negative_top_k"]["1"]["share_of_same_sign_net_mass"] is None
