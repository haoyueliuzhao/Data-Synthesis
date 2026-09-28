"""Small arithmetic/output controls for the read-only completion report."""

import pytest
from report_finance_research_audit_20260928 import paired, percentile, write_once


def test_paired_keeps_same_task_denominator_and_direction():
    left = {str(i): {"metric": v} for i, v in enumerate([1, 1, 0, 0])}
    right = {str(i): {"metric": v} for i, v in enumerate([1, 0, 1, 1])}
    result = paired(left, right, "metric")
    assert result["denominator"] == 4
    assert result["both_positive"] == 1
    assert result["left_only"] == 1 and result["right_only"] == 2
    assert result["right_minus_left_percentage_points"] == 25
    with pytest.raises(AssertionError):
        paired(left, {"other": {"metric": 0}}, "metric")


def test_nearest_rank_percentile():
    assert percentile([4, 1, 3, 2], 0.5) == 2
    assert percentile(list(range(1, 121)), 0.95) == 114


def test_output_is_repeatable_without_overwriting_different_bytes(tmp_path):
    path = tmp_path / "report.json"
    write_once(path, b"original")
    write_once(path, b"original")
    with pytest.raises(ValueError, match="refuse to overwrite"):
        write_once(path, b"different")
    assert path.read_bytes() == b"original"
