"""Protocol/transport controls: mock HTTP, temporary SQLite, no paid requests.

The isolated transport tests stub only the registration snapshot; exact V10 quota
registration/accounting is exercised by its dedicated budget tests.
"""

import asyncio
import copy
import json

import httpx
import pytest
from test_finance_research_probe_provider import Client
from test_finance_v6_probe_budget import v6_budget
from test_finance_v6_strict_review_provider import response_fixture
from test_finance_v10_process_review import fixture
from test_finance_v10_student_encoding import recovered_chain

from trusted_synthesis.finance_research import v10_review_protocol as protocol
from trusted_synthesis.finance_research import v10_review_provider as provider
from trusted_synthesis.finance_research.contracts import ProviderCallError, digest
from trusted_synthesis.finance_research.probe_budget import DuplicateInvocation
from trusted_synthesis.finance_research.v10_budget import BATCH_ID, generation_episode_id

KEY = "v10-unit-test-memory-key-not-real"


@pytest.fixture
def ledger(tmp_path, monkeypatch):
    value = v6_budget(tmp_path)
    original = value.snapshot
    monkeypatch.setattr(
        value, "snapshot", lambda: {**original(), "v10_partition": {"batch_id": BATCH_ID}}
    )
    return value


def requests(index=0, recovery=False):
    episode, candidate, body = recovered_chain() if recovery else fixture()
    sid = generation_episode_id(BATCH_ID, episode.task_id, index)
    body = json.loads(json.dumps(body).replace(candidate["slot_id"] + "/", sid + "/"))
    args = dict(
        slot_id=sid,
        native_result=candidate["native_result"],
        integrity=candidate["integrity"],
        protocol_id=BATCH_ID,
    )
    return (
        episode,
        [protocol.prepare_review_request(episode, role=r, **args) for r in ("A", "B")],
        body,
    )


def paid(ledger, request, body, **response_changes):
    client = Client(response_fixture(json.dumps(body), **response_changes))
    artifact = asyncio.run(
        provider.request_review(ledger=ledger, api_key=KEY, request=request, client=client)
    )
    return artifact, ledger.request_record(artifact["budget_invocation_id"]), client


def joint(ledger, index=0):
    _, pair, raw = requests(index)
    records = []
    for request in pair:
        text = raw if request["role"] == "A" else {"process": raw["process"]}
        artifact, row, _ = paid(ledger, request, text)
        records.append(protocol.review_record(request, artifact, row))
    return protocol.resolve_joint_review(*records, q_native=True)


def mapping_value(request, chi=0):
    package = request["packages"][0]
    view = package["trajectory"]
    doc = next(d for d in view["segments"] if d["kind"] == "public_content")
    evidence = dict(
        slot_id=package["slot_id"],
        segment_id=doc["segment_id"],
        start=0,
        end=len(doc["text"]),
        quote=doc["text"],
    )
    return dict(
        mapping_status="complete",
        states=[
            dict(
                state_id="state-0",
                slot_ids=[p["slot_id"] for p in request["packages"]],
                semantic_summary=(
                    "Initial-table subtraction without consequential extra verification."
                ),
                evidence=[evidence],
                chi=chi,
                chi_reason="No qualifying intervention observed.",
                interventions=[],
            )
        ],
        ambiguities=[],
    )


def test_A_B_fixed_independent_schemas_and_small_predeclared_capacity():
    _, pair, _ = requests()
    a, b = pair
    assert set(a["strict_tool"]["function"]["parameters"]["properties"]) == {
        "process",
        "behavior",
        "supervision",
    }
    assert set(b["strict_tool"]["function"]["parameters"]["properties"]) == {"process"}
    for request in pair:
        wire = json.dumps(provider.request_body(request))
        assert "not-for-process-model" not in wire and "execution_accuracy" not in wire
        assert "private_reference_for_review_only" not in request
        assert request["max_output_tokens"] == 2048
    view = copy.deepcopy(a["candidate_request"]["trajectory"])
    next(d for d in view["segments"] if d["kind"] == "public_content")["text"] *= 200
    assert protocol.capacity("A", [view])["max_output_tokens"] > 2048
    changed = copy.deepcopy(a)
    changed["max_output_tokens"] = 32768
    changed["id"] = digest({k: v for k, v in changed.items() if k != "id"})
    with pytest.raises(ValueError, match="capacity changed"):
        provider.request_body(changed)


def test_real_ledger_binding_exact_restore_and_A_only_authority(ledger):
    value = joint(ledger)
    assert value["joint_valid"] and value["supervision_authority"] == "A"
    assert value["B"]["supervision_manifest"] is None
    assert value["A_manifest"] == value["A"]["supervision_manifest"]
    assert value["A"]["actual_model_call_receipt_verified"] is True
    assert value["A"]["inspection"]["actual_model_call_receipt_verified"] is False
    artifact, request = value["A"]["artifact"], value["A"]["request"]
    row = ledger.request_record(artifact["budget_invocation_id"])
    before = ledger.snapshot()
    assert provider.restore_artifact(row, request) == artifact
    assert protocol.validate_review_record(value["A"], row) == value["A"]
    assert ledger.snapshot() == before
    client = Client()
    with pytest.raises(DuplicateInvocation):
        asyncio.run(
            provider.request_review(ledger=ledger, api_key=KEY, request=request, client=client)
        )
    assert not client.calls
    modified = copy.deepcopy(value["A"])
    modified["process_validity"] = "unknown"
    modified["id"] = digest({k: v for k, v in modified.items() if k != "id"})
    with pytest.raises(ValueError, match="replay"):
        protocol.validate_review_record(modified, row)


def test_settled_failed_annotation_retained_never_repaired_or_third_review(ledger):
    _, pair, raw = requests()
    a_art, a_row, _ = paid(ledger, pair[0], raw)
    b_art, b_row, _ = paid(ledger, pair[1], {"unexpected_mask": []})
    a = protocol.review_record(pair[0], a_art, a_row)
    b = protocol.review_record(pair[1], b_art, b_row)
    assert b["review_status"] == "annotation_failed" and b["process_validity"] == "unknown"
    assert not protocol.resolve_joint_review(a, b, q_native=True)["joint_valid"]
    assert b["artifact"]["review_text"] == json.dumps({"unexpected_mask": []})
    assert ledger.snapshot()["pending_requests"] == 0 and ledger.snapshot()["halt"] is None


def test_no_native_program_equivalence_requirement_and_false_result_stays_false(ledger):
    value = joint(ledger)
    assert (
        value["A"]["request"]["candidate_request"]["native_result"]["native"]["program_accuracy"]
        == 0
    )
    assert value["joint_valid"]
    assert not protocol.resolve_joint_review(value["A"], value["B"], q_native=False)["joint_valid"]


def test_once_mapping_keeps_whole_partition_and_actual_paid_receipt(ledger):
    material = joint(ledger)
    request = protocol.prepare_mapping_request(
        task_id=material["task_id"], joint_records=[material], protocol_id=BATCH_ID
    )
    value = mapping_value(request)
    artifact, row, _ = paid(ledger, request, value)
    result = protocol.mapping_record(request, artifact, row)
    assert protocol.validate_mapping_record(result, row) == result
    assert result["mapping_admitted"] and result["state_by_slot"] == {
        material["slot_id"]: "state-0"
    }
    assert result["chi_by_state"] == {"state-0": 0}
    missing = copy.deepcopy(value)
    missing["states"] = []
    check = protocol._inspect_mapping(json.dumps(missing), request)
    assert (
        check["mapping_status"] == "unknown" and check["annotation_status"] == "annotation_failed"
    )
    ambiguous = dict(
        mapping_status="unknown",
        states=[],
        ambiguities=[
            dict(
                slot_ids=[material["slot_id"]],
                description="Unresolved consequential-vs-redundant check.",
                evidence=[],
            )
        ],
    )
    check = protocol._inspect_mapping(json.dumps(ambiguous), request)
    assert (
        check["annotation_status"] == "annotation_succeeded"
        and check["mapping_status"] == "unknown"
    )
    assert material["joint_valid"]  # Mapping does not rejudge process quality.


def test_chi_requires_actual_action_observation_and_later_consequence_not_error_pattern():
    _, pair, _ = requests(recovery=True)
    view = pair[0]["candidate_request"]["trajectory"]
    request = dict(packages=[dict(slot_id=pair[0]["slot_id"], trajectory=view)])
    value = mapping_value(request, chi=1)
    assert protocol._inspect_mapping(json.dumps(value), request)["mapping_status"] == "unknown"
    action = view["turns"][0]["actions"][0]
    event = next(e for e in view["events"] if e["event_id"] == action["event_id"])
    doc = next(
        d
        for d in view["segments"]
        if d["segment_id"] == view["turns"][1]["public_content_segment_id"]
    )
    value["states"][0]["interventions"] = [
        dict(
            slot_id=pair[0]["slot_id"],
            kind="revision",
            action_id=action["action_id"],
            observation_segment_id=event["observation_segment_id"],
            consequence=dict(
                segment_id=doc["segment_id"], start=0, end=len(doc["text"]), quote=doc["text"]
            ),
            effect=(
                "The actual zero-divisor observation caused the expressed subtraction correction."
            ),
        )
    ]
    assert protocol._inspect_mapping(json.dumps(value), request)["mapping_status"] == "complete"
    value["states"][0]["interventions"][0]["observation_segment_id"] = "invented-observation"
    assert protocol._inspect_mapping(json.dumps(value), request)["mapping_status"] == "unknown"


def test_transports_reject_alternate_model_before_request_and_hold_network_unknown(ledger):
    _, pair, _ = requests()
    changed = copy.deepcopy(pair[0])
    changed["model"] = "another-model"
    changed["id"] = digest({k: v for k, v in changed.items() if k != "id"})
    client = Client()
    with pytest.raises(ValueError, match="model/policy"):
        asyncio.run(
            provider.request_review(ledger=ledger, api_key=KEY, request=changed, client=client)
        )
    assert not client.calls
    client = Client(failure=httpx.RemoteProtocolError("synthetic disconnect"))
    with pytest.raises(ProviderCallError):
        asyncio.run(
            provider.request_review(ledger=ledger, api_key=KEY, request=pair[0], client=client)
        )
    assert len(client.calls) == 1
    snapshot = ledger.snapshot()
    assert snapshot["unknown_requests"] == 1 and snapshot["pending_requests"] == 0
    assert snapshot["halt"]["reason"] == provider.NETWORK_REASON
    assert snapshot["halt"]["evidence"]["service_response_received"] is False


def test_real_http_client_must_use_fixed_direct_tls_factory(ledger):
    _, pair, _ = requests()

    async def check():
        async with httpx.AsyncClient() as unregistered:
            with pytest.raises(ValueError, match="direct_client"):
                await provider.request_review(
                    ledger=ledger, api_key=KEY, request=pair[0], client=unregistered
                )
        async with provider.direct_client() as fixed:
            assert fixed._trust_env is False
            assert fixed._transport._pool._retries == 0
            assert fixed._transport._pool._ssl_context.check_hostname

    asyncio.run(check())
    assert ledger.snapshot()["requests_reserved"] == 0
