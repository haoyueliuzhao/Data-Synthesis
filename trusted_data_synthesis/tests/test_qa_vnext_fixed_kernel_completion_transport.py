"""Synthetic bounded controls: no HTTP sender or GPU is used."""

import copy

import pytest
from test_qa_vnext_catalog_bridge_worker import fixture
from test_qa_vnext_fixed_kernel_runtime import Ledger, Sender, registration

from trusted_synthesis.experiments.finance_qa_vnext_fixed_kernel_value import (
    completion_transport as ct,
)
from trusted_synthesis.experiments.finance_qa_vnext_fixed_kernel_value import (
    protocol as p,
)
from trusted_synthesis.experiments.finance_qa_vnext_fixed_kernel_value import (
    runtime,
    transport,
)


class SplitLedger(Ledger):
    completion_freeze_id = "synthetic_completion_authority"

    def __init__(self, reg, parent=()):
        super().__init__(reg)
        self.parent = copy.deepcopy(list(parent))

    def reserve(self, sid):
        attempt = len(self.parent) + len(self.rows) + 1
        row = {
            "request_id": "synthetic_request_" + str(attempt),
            "session_id": sid,
            "attempt": attempt,
            "input_reservation": p.INPUT_ALLOWANCE,
            "output_cap": p.OUTPUT_ALLOWANCE,
            "reserved_tokens": p.REQUEST_RESERVATION,
            "completion_freeze_id": self.completion_freeze_id,
        }
        self.rows.append({**row, "state": "reserved", "charged_tokens": p.REQUEST_RESERVATION})
        return row

    def parent_requests(self, sid):
        assert sid == self.reg["session_id"]
        return copy.deepcopy(self.parent)

    def new_requests(self, sid):
        return self.requests(sid)


def supplied_provider(ledger, reg, root, content, *, claimed_live=True):
    sender = Sender(
        content,
        usage={"prompt_tokens": 2, "completion_tokens": 1, "total_tokens": 3},
    )
    provider = transport.Provider(ledger, reg, root, "synthetic_credential", sender=sender)
    # Explicit positive-control simulation of the metadata checked by verifier.
    # These test artifacts are NOT authentic collected materials.
    provider.live_http = claimed_live
    return provider, sender


def parent_input(tmp_path, *, claimed_live=True):
    f = fixture()
    reg = registration(f)
    ledger = SplitLedger(reg)
    provider, sender = supplied_provider(
        ledger, reg, tmp_path / "parent", "not JSON", claimed_live=claimed_live
    )

    def interrupted(messages, context):
        if context["response_index"] == 1:
            raise transport.FatalMaterialError("study.stopped_before_next_HTTP_request")
        return provider(messages, context)

    parent = runtime.generate(f["messages"], f["identity"], registered=reg, provider=interrupted)
    assert len(parent["turns"]) == sender.calls == 1
    return f, reg, ledger, parent


def complete(tmp_path, *, claimed_live=True):
    f, reg, old, parent = parent_input(tmp_path, claimed_live=claimed_live)
    ledger = SplitLedger(reg, old.rows)
    provider, sender = supplied_provider(
        ledger, reg, tmp_path / "new", '{"final":{}}', claimed_live=claimed_live
    )
    result = ct.generate(
        reg,
        f,
        provider,
        completion_freeze_id=ledger.completion_freeze_id,
        parent_session=parent,
        parent_journal=old.rows,
    )
    return parent, ledger, sender, result


def verify(tmp_path, ledger, result):
    return ct.verify_origin(
        result["session"],
        ledger,
        tmp_path / "new",
        parent_output=tmp_path / "parent",
        parent_policy=p.policy(),
        lineage=result["lineage"],
    )


def test_prefix_is_byte_exact_no_new_request_and_budget_attempt_retained(tmp_path):
    parent, ledger, sender, result = complete(tmp_path)
    session, lineage = result["session"], result["lineage"]
    assert session["turns"][:1] == parent["turns"]
    assert session["events"][:1] == parent["events"]
    assert session["first_final_index"] == 1
    assert len(session["turns"]) == 2
    assert len(ledger.rows) == sender.calls == lineage["new_provider_calls"] == 1
    assert ledger.rows[0]["attempt"] == 2
    assert lineage["parent_fatal_attempt"] == parent["provider_attempts"][-1]
    assert parent["global_fatal"] and not session["global_fatal"]
    assert lineage["public_prefix_requests_reissued"] == 0
    assert runtime.replay(session) == session
    origin = verify(tmp_path, ledger, result)
    assert origin["status"] == "PASS_AUTHENTIC_MATERIAL_PUBLIC_CHAIN"
    assert [row["source"] for row in origin["verified_turns"]] == ["parent", "completion"]


@pytest.mark.parametrize("attack", ["unknown", "failed", "extra_sent"])
def test_non_budget_request_failures_cannot_be_replayed(tmp_path, attack):
    f, reg, old, parent = parent_input(tmp_path)
    rows = copy.deepcopy(old.rows)
    if attack == "unknown":
        rows[0]["state"] = "usage_unknown"
    elif attack == "failed":
        rows[0]["outcome"] = "response_contract_failure"
    else:
        rows.append({**rows[0], "request_id": "unknown_extra", "state": "sent"})
    with pytest.raises(ValueError, match="no_sent_unknown_or_failed_request_replay"):
        ct.generate(
            reg,
            f,
            lambda *_: pytest.fail("no new request permitted"),
            completion_freeze_id="synthetic_completion_authority",
            parent_session=parent,
            parent_journal=rows,
        )


def test_finished_session_cannot_be_selected_for_continuation(tmp_path):
    _, ledger, _, result = complete(tmp_path)
    with pytest.raises(ValueError, match="budget_interrupted_original_slot_only"):
        ct.PrefixProvider(
            lambda *_: pytest.fail("no new request permitted"),
            registered=ledger.reg,
            parent_session=result["session"],
            parent_journal=ledger.parent + ledger.rows,
        )


def test_synthetic_sender_is_rejected_without_positive_control_flag(tmp_path):
    _, ledger, _, result = complete(tmp_path, claimed_live=False)
    with pytest.raises(ValueError, match="authentic_exact_split_request_response_chain"):
        verify(tmp_path, ledger, result)


def test_new_ledger_usage_and_completion_authority_are_verified(tmp_path):
    _, ledger, _, result = complete(tmp_path)
    ledger.rows[0]["charged_tokens"] += 1
    with pytest.raises(ValueError, match="origin_actual_ledger_usage"):
        verify(tmp_path, ledger, result)
    ledger.rows[0]["charged_tokens"] -= 1
    ledger.completion_freeze_id = "different_authority"
    with pytest.raises(ValueError, match="origin_registered_lineage_authority"):
        verify(tmp_path, ledger, result)


def test_not_run_slot_starts_at_original_zero_index(tmp_path):
    f = fixture()
    reg = registration(f)
    ledger = SplitLedger(reg)
    provider, sender = supplied_provider(ledger, reg, tmp_path / "new", '{"final":{}}')
    result = ct.generate(reg, f, provider, completion_freeze_id=ledger.completion_freeze_id)
    assert result["session"]["first_final_index"] == 0
    assert result["lineage"]["original_public_prefix_count"] == 0
    assert result["lineage"]["parent_material_session_id"] is None
    assert sender.calls == 1
    assert verify(tmp_path, ledger, result)["status"] == "PASS_AUTHENTIC_MATERIAL_PUBLIC_CHAIN"
