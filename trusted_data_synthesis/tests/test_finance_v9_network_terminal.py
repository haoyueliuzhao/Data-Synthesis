"""Explicit terminal accounting with synthetic ledgers, never API/real billing."""

import copy
import json
from types import SimpleNamespace

import pytest
from test_finance_v8_single_target_review import fixture
from test_finance_v9_conditional_training import population
from test_finance_v9_monetary_amendment import synthetic_parent as synthetic_parent
from test_finance_v9_monetary_amendment import wallet as wallet
from test_finance_v9_network_unknowns import authority
from test_finance_v9_network_unknowns import network_wallet as network_wallet

from trusted_synthesis.finance_research import v9_network_terminal as terminal
from trusted_synthesis.finance_research.contracts import digest
from trusted_synthesis.finance_research.probe_budget import (
    V9_NETWORK_PROTOCOL_ID,
    V9_NETWORK_UNKNOWN_REASON,
)
from trusted_synthesis.finance_research.storage import read_json
from trusted_synthesis.finance_research.v6_collection import bound
from trusted_synthesis.finance_research.v6_decomposed_review import job_directory
from trusted_synthesis.finance_research.v8_single_target_review import slot_review_record
from trusted_synthesis.finance_research.v9_conditional_training import _completion
from trusted_synthesis.finance_research.v9_review_preflight import request_body
from trusted_synthesis.finance_research.v9_review_recovery import inspect_recovery


def fixture_terminal(tmp_path, monkeypatch, ledger):
    _, _, requests, _, _ = fixture()
    request = requests[0]["s0"]
    request.update(max_output_tokens=16384, capacity_policy_id="synthetic-fixed")
    body = request_body(request)
    job = dict(
        key="slot:synthetic-network",
        stage="slot",
        task_id=request["task_id"],
        slot_id="s0",
        reviewer=0,
    )
    plan = dict(
        id=V9_NETWORK_PROTOCOL_ID,
        jobs=[job],
        budget_config=dict(run_id=ledger.run_id),
        budget_database=str(ledger.path),
    )
    auth = authority(no_prefix_training=True, same_matrix_and_namespace=True)
    revision = bound(
        dict(
            schema="v9_same_matrix_network_terminal_revision.v1",
            protocol_id=plan["id"],
            authorization_record=auth,
            jobs_sha256=digest(plan["jobs"]),
        )
    )
    monkeypatch.setattr(terminal, "revision_for", lambda output, p: revision)
    monkeypatch.setattr(terminal, "_request_body", lambda saved, req: (request_body(req), 0))
    coordinates = terminal.coordinates(plan, job)
    iid = coordinates["invocation_id"]
    ledger.reserve(
        iid, coordinates=coordinates, request=body, request_body=json.dumps(body).encode()
    )
    ledger.mark_dispatched(iid)
    evidence = dict(
        budget_invocation_id=iid,
        budget_coordinates=coordinates,
        request_sha256=digest(body),
        service_response_received=False,
        exception_type="RemoteProtocolError",
        reviewer=0,
        task_bundle_sha256=request["task_bundle_sha256"],
        rubric_sha256=request["rubric_sha256"],
        review_request_metadata_sha256=digest(request),
        semantic_review_request_sha256=digest(request),
        wire_protocol=request["wire_protocol"],
        endpoint="https://api.deepseek.com/beta/chat/completions",
        strict_tool_sha256=request["strict_tool_sha256"],
    )
    ledger.unknown(iid, reason=V9_NETWORK_UNKNOWN_REASON, evidence=evidence)
    return plan, revision, request, job, SimpleNamespace(request=lambda j: request)


def test_unknown_terminal_keeps_hold_no_fabricated_return_and_recovery_counts_separately(
    tmp_path, monkeypatch, network_wallet
):
    ledger, _, _ = network_wallet
    plan, revision, request, job, context = fixture_terminal(tmp_path, monkeypatch, ledger)
    before = ledger.snapshot()
    output = tmp_path / "cohort"
    terminal.materialize_network_terminals(output, plan, ledger, context)
    after = ledger.snapshot()
    for key in (
        "requests_reserved",
        "requests_dispatched",
        "settled_tariff_microcny",
        "held_microcny",
        "unknown_requests",
    ):
        assert before[key] == after[key]
    assert after["unacknowledged_unknown_requests"] == 0 and after["halt"] is None
    artifact = read_json(job_directory(output, job) / "response/record.json")
    assert (
        artifact["usage"] is None
        and artifact["review_text"] is None
        and artifact["api_response_raw"] is None
    )
    assert artifact["actual_model_calls"] is None and artifact["model_response_received"] is False
    record = slot_review_record(request, artifact)
    assert record["v_trace"] == "unknown" and record["derived"] is None
    audit, completed, costs = inspect_recovery(output, plan, ledger, context, repair_local=True)
    assert audit["resume_admitted"] and audit["reused_returned_jobs"] == []
    assert audit["reused_terminal_jobs"] == [job["key"]]
    assert completed[job["key"]]["returned"] is False
    assert costs == dict(cost_microcny=0, prompt_tokens=0, completion_tokens=0)
    terminal.materialize_network_terminals(output, plan, ledger, context)
    assert ledger.snapshot() == after
    changed = copy.deepcopy(artifact)
    changed["review_text"] = "fabricated valid"
    with pytest.raises(ValueError, match="cannot fabricate"):
        terminal.validate_terminal(
            changed,
            protocol_id=plan["id"],
            semantic_request_sha256=digest(request),
            revision=revision,
        )


def test_new_terminal_seal_keeps_old_full_return_requirement_and_truthful_counts():
    protocol, old, _, _ = population()
    authority_record = authority(
        protocol_id=protocol["id"], no_prefix_training=True, same_matrix_and_namespace=True
    )
    revision = bound(
        dict(
            schema="v9_same_matrix_network_terminal_revision.v1",
            protocol_id=protocol["id"],
            authorization_record=authority_record,
            jobs_sha256=digest(protocol["jobs"]),
        )
    )
    rows = [dict(row, terminal_kind="model_response") for row in old["jobs"]]
    rows[0]["terminal_kind"] = terminal.TERMINAL_KIND
    new = bound(
        {k: v for k, v in old.items() if k != "id"}
        | dict(
            schema="v9_production_completion_seal.v2",
            jobs=rows,
            completed_requests=9,
            processed_jobs=10,
            network_unknown_jobs=1,
            all_registered_returns_present=False,
            all_registered_jobs_have_terminal_records=True,
            execution_revision=revision,
        )
    )
    _completion(protocol, new)
    for changes in (
        dict(completed_requests=10),
        dict(schema="v9_production_completion_seal.v1"),
        dict(processed_jobs=9),
        dict(all_registered_returns_present=True),
    ):
        altered = bound({k: v for k, v in new.items() if k != "id"} | changes)
        with pytest.raises(ValueError):
            _completion(protocol, altered)
    assert old["schema"] == "v9_production_completion_seal.v1" and old["completed_requests"] == 10


@pytest.mark.parametrize("field", ["no_resend", "permanent_full_hold", "unknown_never_positive"])
def test_explicit_terminal_scope_cannot_be_weakened(field):
    auth = authority(no_prefix_training=True, same_matrix_and_namespace=True, **{field: False})
    with pytest.raises(ValueError, match="explicit bounded"):
        terminal.validate_authorization(auth, V9_NETWORK_PROTOCOL_ID)
