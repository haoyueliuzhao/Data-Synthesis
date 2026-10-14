import importlib
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
subject = importlib.import_module("finqa_v43_time_policy")


def test_real_none_deadline_and_unbounded_accounting():
    policy = subject.record()
    subject.validate(dict(time_policy=policy))
    assert subject.deadline_expired(None, 10**30) is False
    assert subject.elapsed(93466, 129601) == 36135
    assert policy["draining_grace_seconds"] == 600
    assert policy["runtime_memory_host_and_identity_gates_unchanged"] is True
    assert policy["explicit_stop_signals_remain_effective"] is True


@pytest.mark.parametrize("deadline", [0, 1e300, float("inf"), False, "none"])
def test_numeric_sentinels_and_implicit_deadlines_are_rejected(deadline):
    with pytest.raises(ValueError, match="actual null deadline"):
        subject.require_no_deadline(deadline)


def test_policy_cannot_remove_shutdown_grace_or_resource_gates():
    policy = subject.record()
    policy["runtime_memory_host_and_identity_gates_unchanged"] = False
    with pytest.raises(ValueError, match="policy changed"):
        subject.validate(dict(time_policy=policy))
