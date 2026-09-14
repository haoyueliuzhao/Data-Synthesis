"""Only new numeric-cache framing; no archive, model, API or old-suite replay."""

import io

import numpy as np
import pytest

from trusted_synthesis.experiments.finance_qa_vnext_fixed_kernel_value import publish


def encoded(values):
    stream = io.BytesIO()
    np.save(stream, values, allow_pickle=False)
    return stream.getvalue()


def test_complete_integer_cache_vector():
    result = publish._trajectory_array(encoded(np.array([1, 17, 151645], dtype="<i4")))
    assert result == {"dtype": "int32", "elements": 3, "pickle": False}


@pytest.mark.parametrize(
    "values", [np.ones(2, dtype="<f4"), np.ones((2, 2), dtype="<i4")]
)
def test_reject_weights_or_nonvector(values):
    with pytest.raises(ValueError):
        publish._trajectory_array(encoded(values))


def test_reject_truncated_cache_vector():
    with pytest.raises(ValueError):
        publish._trajectory_array(encoded(np.array([1, 2], dtype="<i4"))[:-1])
