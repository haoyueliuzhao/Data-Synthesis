from __future__ import annotations

import math
import statistics

from .schema import AggregateMetric

_T_975 = {
    1: 12.706,
    2: 4.303,
    3: 3.182,
    4: 2.776,
    5: 2.571,
    6: 2.447,
    7: 2.365,
    8: 2.306,
    9: 2.262,
    10: 2.228,
    11: 2.201,
    12: 2.179,
    13: 2.160,
    14: 2.145,
    15: 2.131,
    16: 2.120,
    17: 2.110,
    18: 2.101,
    19: 2.093,
    20: 2.086,
    21: 2.080,
    22: 2.074,
    23: 2.069,
    24: 2.064,
    25: 2.060,
    26: 2.056,
    27: 2.052,
    28: 2.048,
    29: 2.045,
    30: 2.042,
}


def aggregate_metric(values: list[float]) -> AggregateMetric:
    """Return a two-sided 95% Student-t interval over independent runs."""

    if not values:
        raise ValueError("cannot aggregate an empty metric")
    count = len(values)
    mean = statistics.fmean(values)
    deviation = statistics.stdev(values) if count > 1 else 0.0
    critical = _student_t_critical_95(count - 1) if count > 1 else 0.0
    return AggregateMetric(
        mean=mean,
        standard_deviation=deviation,
        ci95_half_width=critical * deviation / math.sqrt(count),
        sample_count=count,
        interval_method="student_t_95",
    )


def _student_t_critical_95(degrees_of_freedom: int) -> float:
    if degrees_of_freedom <= 0:
        return 0.0
    if degrees_of_freedom <= 30:
        return _T_975[degrees_of_freedom]
    if degrees_of_freedom <= 40:
        return 2.021
    if degrees_of_freedom <= 60:
        return 2.000
    if degrees_of_freedom <= 120:
        return 1.980
    return 1.960
