"""Final publication controls, with no Provider, source scan or historical execution."""

from __future__ import annotations

import copy
import json
import socket
from pathlib import Path
from types import SimpleNamespace

import pytest

from trusted_synthesis.canonical_json import canonical_json_bytes
from trusted_synthesis.domains.finance.qa_vnext.action_public_contract import (
    public_action_contract,
    rejection_feedback,
)
from trusted_synthesis.domains.finance.qa_vnext.bound_share_adapter import BoundShareTaskAdapter
from trusted_synthesis.domains.finance.qa_vnext.final_public_contract import (
    public_final_contract,
    public_final_schema,
    publish_final_contract,
)
from trusted_synthesis.domains.finance.qa_vnext.final_published_share_adapter import (
    FinalPublishedShareTaskAdapter,
)
from trusted_synthesis.domains.finance.qa_vnext.measurement import _request as audit_request
from trusted_synthesis.domains.finance.qa_vnext.protocol import (
    Final,
    ProtocolError,
    contract,
    parse,
    record,
)
from trusted_synthesis.domains.finance.qa_vnext.runtime import PublicQARuntime
from trusted_synthesis.domains.finance.qa_vnext.update_public_contract import public_update_contract
from trusted_synthesis.experiments.finance_qa_vnext_cross_binding import source

ROOT = Path(__file__).resolve().parents[2]
SOURCE_REPORT = (
    ROOT / "trusted_data_synthesis/artifacts/qa_vnext_cross_binding/"
    "cross_binding_dual_support_v1_20260907/preparation/source_report.json"
)


def forbidden(*args, **kwargs):
    pytest.fail("publication test attempted network, Runtime execution, source scan or finance")


@pytest.fixture(autouse=True)
def no_execution(monkeypatch):
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(PublicQARuntime, "__init__", forbidden)
    monkeypatch.setattr(PublicQARuntime, "run", forbidden)
    monkeypatch.setattr(BoundShareTaskAdapter, "execute", forbidden)
    monkeypatch.setattr(source, "load_sources", forbidden)


def _claim():
    return record(
        "claim",
        observation_id="synthetic-observation",
        action_submission_id="synthetic-action",
        obligation_id="percent",
        status="accepted",
        proposition={
            "operation": "scale_percent",
            "lineage": ["e.target", "e.other", "e.relation"],
            "output": {"value": "25.12500049", "unit": "percent"},
        },
    )


def _requests(*, enabled=True, ready=True):
    """Invoke real Request builders on read-only constructed views, not an executing Runtime."""
    claims = [_claim()] if ready else []
    context = record(
        "context",
        task_id="synthetic-task",
        final_projection="share_percent_quantized",
        numeric={"precision": 50, "rounding": "ROUND_HALF_EVEN", "final_quantum": "0.000001"},
        evidence={
            role: {"id": "e." + role} for role in ("target", "other", "relation", "disclosed")
        },
    )
    adapter = SimpleNamespace(
        context=context,
        public_final_contract_enabled=enabled,
        offers=lambda selected: [],
        final_claims=lambda selected: [c["id"] for c in selected],
    )
    rules = contract()
    state = record(
        "state",
        context_id=context["id"],
        protocol_id=rules["id"],
        accepted_claims=claims,
        pending_observation=None,
        phase="action",
        submission_count=6 if ready else 0,
        action_count=3 if ready else 0,
        update_count=3 if ready else 0,
        last_feedback=None,
        unresolved_uncertainties=[],
        terminal=False,
    )
    view = SimpleNamespace(
        adapter=adapter,
        claims=claims,
        pending=None,
        terminal=False,
        rules=rules,
        state=lambda: copy.deepcopy(state),
    )
    produced = PublicQARuntime.request(view)
    reconstructed = audit_request(adapter, copy.deepcopy(state), rules)
    assert canonical_json_bytes(produced) == canonical_json_bytes(reconstructed)
    return produced


def _valid_final(request):
    # This fixture value is not one of the three experiment answers and is never published.
    return {
        "kind": "final",
        "state_id": request["state"]["id"],
        "answer_claim_id": request["final_claim_ids"][0],
        "result": {"value": "25.125000", "unit": "percent"},
        "citations": ["e.target", "e.other", "e.relation"],
    }


def test_complete_contract_and_schema_available_before_and_after_answer_claim():
    for ready in (False, True):
        request = _requests(ready=ready)
        assert request["public_final_contract"] == public_final_contract()
        assert request["response_schemas"]["final"] == public_final_schema()
        assert request["public_action_contract"] == public_action_contract()
        assert request["public_update_contract"] == public_update_contract()
        result = request["response_schemas"]["final"]["properties"]["result"]
        assert result["required"] == ["value", "unit"] and result["additionalProperties"] is False
        assert result["properties"]["value"]["type"] == "string"
        assert result["properties"]["unit"]["const"] == "percent"
        assert (
            request["response_schemas"]["final"]["properties"]["citations"]["uniqueItems"] is True
        )
        text = canonical_json_bytes(public_final_contract()).decode()
        assert (
            "25.125000" not in text
            and "synthetic" not in text
            and request["state"]["id"] not in text
        )
        assert all(value not in text for value in request["final_claim_ids"])
        assert "ENTIRE" in request["public_final_contract"]["update_final_distinction"]


def test_opt_in_only_and_original_parser_contract_not_replaced():
    old = _requests(enabled=False)
    before = canonical_json_bytes(old)
    published = publish_final_contract(old)
    assert canonical_json_bytes(old) == before
    assert "public_final_contract" not in old
    assert old["response_schemas"]["final"] == Final.model_json_schema()
    for kind in ("action", "update"):
        assert published["response_schemas"][kind] == old["response_schemas"][kind]
    for name in (
        "context",
        "state",
        "available_actions",
        "final_claim_ids",
        "update_transition_options",
    ):
        assert published[name] == old[name]
    response = _valid_final(published)
    response["result"]["metric"] = "still-parses-but-strict-final-verifier-rejects"
    assert parse(canonical_json_bytes(response))["result"] == response["result"]
    with pytest.raises(ProtocolError, match="already_present"):
        publish_final_contract(published)


def test_new_adapter_inherits_unchanged_source_context_registry_and_final_verifier():
    # Explicit immutable source-binding report only; never parse the FinQA source archive.
    report = json.loads(SOURCE_REPORT.read_bytes())
    for binding, task, semantic in zip(
        report["bindings"], report["tasks"], report["semantic_contracts"], strict=True
    ):
        bound = source.BoundShareSource(
            binding["source_key"],
            task["id"],
            binding["id"],
            {key: binding[key] for key in source.CONTEXT_FIELDS},
            binding["evidence"],
            binding,
            task,
            semantic,
        )
        original, published = BoundShareTaskAdapter(bound), FinalPublishedShareTaskAdapter(bound)
        assert canonical_json_bytes(original.context) == canonical_json_bytes(published.context)
        assert original.registry.manifest() == published.registry.manifest()
        assert published.source.task_id == original.source.task_id
        assert FinalPublishedShareTaskAdapter.__init__ is BoundShareTaskAdapter.__init__
        assert FinalPublishedShareTaskAdapter.verify_final is BoundShareTaskAdapter.verify_final
        assert getattr(original, "public_final_contract_enabled", False) is False
        assert published.public_final_contract_enabled is True


@pytest.mark.parametrize(
    "case,category,violation",
    [
        ("extra", "result_fields", None),
        ("missing_unit", "result_fields", None),
        ("number", "value_projection", "value_type"),
        ("unquantized", "value_projection", "value_quantum_format"),
        ("wrong_six_decimal", "value_projection", "selected_claim_projection_mismatch"),
        ("unit", "unit", None),
        ("citations", "actual_lineage", None),
        ("duplicates", "actual_lineage", None),
    ],
)
def test_specific_public_diagnostics_without_replacement_or_mutation(case, category, violation):
    request = _requests()
    submitted = _valid_final(request)
    if case == "extra":
        submitted["result"]["metric"] = "example_metadata"
    elif case == "missing_unit":
        del submitted["result"]["unit"]
    elif case == "number":
        submitted["result"]["value"] = 25.12500049
    elif case == "unquantized":
        submitted["result"]["value"] = "25.12500049"
    elif case == "wrong_six_decimal":
        submitted["result"]["value"] = "25.124999"
    elif case == "unit":
        submitted["result"]["unit"] = "%"
    elif case == "citations":
        submitted["citations"] = ["e.target", "e.disclosed"]
    else:
        submitted["citations"].append("e.target")
    before = canonical_json_bytes([request, submitted])
    feedback = rejection_feedback("admission.final_qa", request, submitted)
    assert canonical_json_bytes([request, submitted]) == before
    assert feedback["code"] == "admission.final_qa" and feedback["admitted"] is False
    diagnostic = feedback["public_diagnostic"]
    assert len(diagnostic["violations"]) == 1
    detail = diagnostic["violations"][0]
    assert detail["category"] == category
    if violation:
        assert detail["violation"] == violation
    if case == "extra":
        assert detail["extra_fields"] == ["metric"] and detail["missing_fields"] == []
    if case == "missing_unit":
        assert detail["missing_fields"] == ["unit"]
    if case == "citations":
        assert detail["missing_ids"] == ["e.other", "e.relation"]
        assert detail["extra_ids"] == ["e.disclosed"]
    if case == "duplicates":
        assert detail["duplicate_ids"] == ["e.target"]
    assert diagnostic["response_rewritten"] is diagnostic["replacement_answer_supplied"] is False
    assert (
        diagnostic["financial_operations_executed"]
        is diagnostic["source_answer_verifier_called"]
        is False
    )
    serialized = canonical_json_bytes(feedback).decode()
    assert "25.125000" not in serialized
    assert request["state"]["id"] not in serialized
    assert submitted["answer_claim_id"] not in serialized


def test_earlier_state_and_claim_gates_do_not_report_final_qa_execution():
    request = _requests()
    submitted = _valid_final(request)
    submitted["state_id"] = "wrong-state"
    submitted["result"] = {"unexpected": "also wrong but not reached"}
    feedback = rejection_feedback("admission.current_state", request, submitted)
    details = feedback["public_diagnostic"]["violations"]
    assert [item["category"] for item in details] == ["current_state"]
    assert details[0]["required_state_source"] == "/state/id"
    assert feedback["code"] == "admission.current_state"
    submitted["answer_claim_id"] = "wrong-claim"
    feedback = rejection_feedback("admission.final_accepted_claim", request, submitted)
    assert [item["category"] for item in feedback["public_diagnostic"]["violations"]] == [
        "accepted_answer"
    ]


def test_schema_failure_and_unidentified_original_check_remain_specific_without_answer_fill():
    request = _requests()
    feedback = rejection_feedback("submission.schema", request, None)
    assert (
        feedback["public_diagnostic"]["violations"][0]["schema_source"] == "/response_schemas/final"
    )
    feedback = rejection_feedback("admission.final_qa", request, _valid_final(request))
    detail = feedback["public_diagnostic"]["violations"][0]
    assert detail["category"] == "source_consistency"
    assert (
        detail["violation"]
        == "unchanged_final_qa_rejected_no_additional_public_mismatch_identified"
    )
    assert feedback["public_diagnostic"]["source_answer_verifier_called"] is False


def test_action_update_and_non_opted_final_feedback_remain_unchanged():
    old, new = _requests(enabled=False), _requests(enabled=True)
    for submitted in ({"kind": "action"}, {"kind": "update"}):
        # Unknown-gate feedback routing remains the old Action/Update route in both presentations.
        assert rejection_feedback("synthetic.unknown", old, submitted) == rejection_feedback(
            "synthetic.unknown", new, submitted
        )
    assert rejection_feedback("admission.final_qa", old, _valid_final(old)) == {
        "code": "admission.final_qa",
        "admitted": False,
    }


def test_diagnostics_remain_json_roundtrip_stable_for_saved_requests():
    request = _requests()
    submitted = _valid_final(request)
    submitted["citations"] = ["e.target", "e.disclosed"]
    original = rejection_feedback("admission.final_qa", request, submitted)
    saved_request = json.loads(canonical_json_bytes(request))
    saved_submitted = json.loads(canonical_json_bytes(submitted))
    assert original == rejection_feedback("admission.final_qa", saved_request, saved_submitted)
