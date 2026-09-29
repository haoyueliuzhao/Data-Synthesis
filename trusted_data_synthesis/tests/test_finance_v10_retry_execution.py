"""Small source-transition controls for the single final retry; no real resources."""

import copy

import pytest

from trusted_synthesis.finance_research import v10_retry_execution as revision
from trusted_synthesis.finance_research.v6_collection import bound, persist, sha


def maps():
    before = {
        scope: dict.fromkeys(sorted(names | {"v10_review_protocol.py"}), "before")
        for scope, names in revision.ALLOWED_CHANGES.items()
    }
    after = copy.deepcopy(before)
    for scope, names in revision.ALLOWED_CHANGES.items():
        for name in names:
            after[scope][name] = "after"
    return before, after


def test_only_named_retry_plumbing_can_change():
    before, after = maps()
    assert revision.changed_sources(before, after) == {
        scope: sorted(names) for scope, names in revision.ALLOWED_CHANGES.items()
    }
    after["annotation"]["v10_review_protocol.py"] = "edited-prompt"
    with pytest.raises(ValueError, match="policy/prompt"):
        revision.changed_sources(before, after)


def test_protected_source_membership_cannot_be_extended():
    before, after = maps()
    after["generation"]["unregistered.py"] = "new"
    with pytest.raises(ValueError, match="source list"):
        revision.changed_sources(before, after)


def test_exact_registered_chain_and_future_hash_drift(tmp_path, monkeypatch):
    before, after = maps()
    original = {scope: {k: "initial" for k in v} for scope, v in before.items()}
    plan = dict(id="synthetic-plan", batch_id="synthetic-batch", review_policy_id="policy")
    parent = bound(dict(original_sources=original, effective_sources=before))
    funding = bound(dict(schema="synthetic-funding"))
    permit = bound(dict(schema="synthetic-permit"))
    persist((tmp_path / revision.FUNDING_REVISION_PATH).parent, parent)
    persist((tmp_path / revision.AUTHORIZATION_PATH).parent, permit)
    monkeypatch.setattr(revision, "parent_revision", lambda *args: (parent, funding))
    live = copy.deepcopy(after)
    monkeypatch.setattr(revision, "source_maps", lambda: live)
    monkeypatch.setattr(revision, "extra_sources", lambda: {"new-retry-module": "exact"})
    record = bound(
        dict(
            schema="v10_single_final_retry_execution_revision.v1",
            protocol_id=plan["id"],
            batch_id=plan["batch_id"],
            policy_id=plan["review_policy_id"],
            authorization=revision.AUTHORIZATION,
            funding_execution_revision_id=parent["id"],
            funding_execution_revision_sha256=sha(tmp_path / revision.FUNDING_REVISION_PATH),
            funding_amendment_id=funding["id"],
            retry_permit_id=permit["id"],
            retry_permit_sha256=sha(tmp_path / revision.AUTHORIZATION_PATH),
            initial_sources=original,
            previous_effective_sources=before,
            effective_sources=after,
            changed_files=revision.changed_sources(before, after),
            additional_source_bindings=revision.extra_sources(),
        )
    )
    persist((tmp_path / revision.REVISION_PATH).parent, record)
    for scope in original:
        assert revision.validate_retry_source_transition(
            tmp_path, plan, scope=scope, original=original[scope], current=live[scope]
        ) == record
    live["annotation"]["v10_budget.py"] = "later-unregistered-edit"
    with pytest.raises(ValueError, match="exact registered"):
        revision.validate_retry_source_transition(
            tmp_path,
            plan,
            scope="annotation",
            original=original["annotation"],
            current=live["annotation"],
        )
