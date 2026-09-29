"""Small controls for the exact group-retry source boundary, with no resources."""

import copy

import pytest

from trusted_synthesis.finance_research import v10_network_retry_execution as revision


def maps():
    before = {
        scope: dict.fromkeys(sorted(names | {"v10_review_protocol.py", "probe_budget.py"}), "old")
        for scope, names in revision.ALLOWED_CHANGES.items()
    }
    after = copy.deepcopy(before)
    for scope, names in revision.ALLOWED_CHANGES.items():
        for name in names:
            after[scope][name] = "registered-new"
    return before, after


def test_explicit_new_scope_and_only_named_group_plumbing():
    before, after = maps()
    assert revision.AUTHORIZATION["user_reply"] == "批准上述本批全部网络 UNKNOWN 补发范围"
    assert revision.changed_sources(before, after) == {
        scope: sorted(names) for scope, names in revision.ALLOWED_CHANGES.items()
    }
    after["annotation"]["v10_review_protocol.py"] = "edited-policy"
    with pytest.raises(ValueError, match="policy/scoring/kernel"):
        revision.changed_sources(before, after)


def test_cannot_relax_money_rules_or_protected_membership():
    before, after = maps()
    after["generation"]["probe_budget.py"] = "altered-global-money-cap"
    with pytest.raises(ValueError, match="policy/scoring/kernel"):
        revision.changed_sources(before, after)
    before, after = maps()
    after["generation"]["unregistered.py"] = "extra"
    with pytest.raises(ValueError, match="source list"):
        revision.changed_sources(before, after)
