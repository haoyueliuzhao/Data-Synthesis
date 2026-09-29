"""Only the explicit proxy transport wiring may change; pure maps, no wallet/HTTP."""

import copy

import pytest

from trusted_synthesis.finance_research import v10_proxy_execution as proxy


def source_maps():
    before = {
        scope: {
            wiring: "old-wiring-sha",
            "v10_review_provider.py": "old-provider-sha",
            "probe_budget.py": "unchanged-budget-sha",
            "v10_review_protocol.py": "unchanged-policy-sha",
        }
        for scope, wiring in (
            ("generation", "v10_generation.py"),
            ("annotation", "v10_production.py"),
        )
    }
    after = copy.deepcopy(before)
    for scope, names in proxy.ALLOWED_CHANGES.items():
        for name in names:
            after[scope][name] = "registered-new-" + name
    return before, after


def test_exact_proxy_wiring_allowed_without_mutating_before_maps():
    before, after = source_maps()
    untouched = copy.deepcopy(before)
    assert proxy.AUTHORIZATION["user_reply"] == "授权现有代理验证并恢复"
    assert proxy.changed_sources(before, after) == {
        scope: sorted(names) for scope, names in proxy.ALLOWED_CHANGES.items()
    }
    assert before == untouched


def test_proxy_permission_does_not_allow_budget_or_annotation_policy_changes():
    for scope in ("generation", "annotation"):
        for forbidden in ("probe_budget.py", "v10_review_protocol.py"):
            before, after = source_maps()
            after[scope][forbidden] = "unapproved-change"
            with pytest.raises(
                ValueError, match="proxy transition cannot change research or budget rules"
            ):
                proxy.changed_sources(before, after)


def test_proxy_permission_cannot_add_or_remove_protected_source_names():
    for scope in ("generation", "annotation"):
        before, after = source_maps()
        after[scope]["v10_transport.py"] = "must-be-pinned-separately"
        with pytest.raises(ValueError, match="protected source list cannot change"):
            proxy.changed_sources(before, after)
        before, after = source_maps()
        del after[scope]["probe_budget.py"]
        with pytest.raises(ValueError, match="protected source list cannot change"):
            proxy.changed_sources(before, after)
