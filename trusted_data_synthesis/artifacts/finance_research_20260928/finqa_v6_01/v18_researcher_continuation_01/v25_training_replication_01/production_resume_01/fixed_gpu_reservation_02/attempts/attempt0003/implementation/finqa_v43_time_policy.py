"""Explicit removal of wall-clock run caps, without removing any safety gate."""

from __future__ import annotations

import math

SCHEMA = "v43_explicit_no_wallclock_limits.v1"
USER_INSTRUCTION = "授权修复版运行，当前资源紧张，取消截止时间限制，设置自动恢复"


def require(condition, message):
    if not condition:
        raise ValueError(message)


def record():
    return dict(
        schema=SCHEMA,
        user_instruction=USER_INSTRUCTION,
        phase_deadline_epoch=None,
        outer_compute_limit_seconds=None,
        cumulative_resource_wait_limit_seconds=None,
        inherited_elapsed_accounting_retained=True,
        stage_and_outer_elapsed_accounting_continues=True,
        finite_far_future_deadline_substitution=False,
        runtime_memory_host_and_identity_gates_unchanged=True,
        explicit_stop_signals_remain_effective=True,
        draining_grace_seconds=600,
        draining_is_shutdown_grace_not_run_deadline=True,
    )


def validate(plan):
    require(plan.get("time_policy") == record(), "explicit unlimited time policy changed")
    return plan


def require_no_deadline(deadline_epoch):
    require(deadline_epoch is None, "V43 requires an actual null deadline, not a clock sentinel")


def deadline_expired(deadline_epoch, now=None):
    require_no_deadline(deadline_epoch)
    return False


def elapsed(start, end):
    require(
        all(type(value) in (int, float) and math.isfinite(value) for value in (start, end))
        and 0 <= start <= end,
        "elapsed accounting clock is invalid or reversed",
    )
    return end - start
