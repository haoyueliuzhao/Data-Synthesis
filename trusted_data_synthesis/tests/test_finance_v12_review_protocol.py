"""Compact production-wire controls; synthetic original trace, no paid calls."""

import copy
import json

import pytest
from test_finance_v10_process_review import fixture

from trusted_synthesis.finance_research import v12_review_protocol as protocol
from trusted_synthesis.finance_research.contracts import digest


def specimen(role="A"):
    episode, old, old_body = fixture()
    slot = "v10gen:" + digest("synthetic-v12-original-slot")
    request = protocol.prepare_request(
        episode,
        slot_id=slot,
        role=role,
        native_result=old["native_result"],
        integrity=old["integrity"],
        protocol_id=digest("synthetic-new-matrix"),
    )
    view = request["candidate_request"]["trajectory"]
    units = request["candidate_request"]["catalog"]["units"]
    segments = {
        a["segment_id"]: b["segment_id"]
        for a, b in zip(old["trajectory"]["segments"], view["segments"], strict=True)
    }

    def ref(item):
        unit = next(
            u
            for u in units
            if u["segment_id"] == segments[item["segment_id"]]
            and u["start"] <= item["start"]
            and u["end"] >= item["end"]
        )
        return dict(id=unit["unit_id"], quote=item["quote"])

    body = dict(
        process={
            name: dict(
                status=item["status"],
                summary=item["summary"],
                evidence_ids=[],
                partial_evidence=[ref(e) for e in item["evidence"]],
            )
            for name, item in old_body["process"].items()
        }
    )
    if role == "A":
        positive = old_body["supervision"][0]
        body["supervision"] = dict(
            status="complete",
            positive_units=[],
            partial_positive_content=[ref(positive)],
            positive_actions=[a["action_id"] for t in view["turns"] for a in t["actions"]],
        )
    return request, body


def artifact(body, *, finish="tool_calls", raw=None):
    return dict(
        review_text=json.dumps(body, ensure_ascii=False) if raw is None else raw,
        finish_reason=finish,
        review_format_error=None if finish == "tool_calls" else "strict_finish_not_tool_calls",
        usage={"completion_tokens": 500},
    )


def test_all_public_strings_are_preserved_once_and_private_results_stay_host_only():
    req, _ = specimen()
    payload = json.loads(req["messages"][1]["content"])
    original = req["candidate_request"]
    assert payload["units"] == {u["unit_id"]: u["text"] for u in original["catalog"]["units"]}
    assert "not-for-process-model" not in json.dumps(req["messages"])
    assert len(req["messages"][1]["content"]) < len(original["messages"][1]["content"])
    params = req["strict_tool"]["function"]["parameters"]
    assert set(params["properties"]) == {"process", "supervision"}
    assert set(params["properties"]["supervision"]["properties"]) == {
        "status",
        "positive_units",
        "partial_positive_content",
        "positive_actions",
    }
    assert req["max_output_tokens"] in (8192, 16384, 32768, 65536)
    wire = protocol.request_body(req)
    assert wire["model"] == "deepseek-flash" and wire["thinking"] == {"type": "disabled"}


@pytest.mark.parametrize("role", ["A", "B"])
def test_wire_materialization_is_explicit_without_overwriting_raw_or_inner_production_flags(role):
    req, body = specimen(role)
    original = copy.deepcopy(body)
    result = protocol.inspect_paid_annotation(req, artifact(body))
    assert body == original
    out = result["new_pipeline_outcomes"]
    assert out["raw_wire_annotation"] == body and out["materialization_is_not_raw_model_text"]
    assert out["process_validity"] == "valid" and out["process_candidate_usable"]
    assert result["inspection"]["actual_model_call_receipt_verified"] is False
    assert result["inspection"]["training_admissibility"]["production_admitted"] is False
    assert out["projection_usable"] is (True if role == "A" else None)


def test_auxiliary_failure_preserves_core_but_critical_binding_failure_does_not_pass():
    req, body = specimen()
    body["supervision"]["positive_units"] = ["invented-unit"]
    out = protocol.inspect_paid_annotation(req, artifact(body))["new_pipeline_outcomes"]
    assert out["process_candidate_usable"] and not out["projection_usable"]
    assert "SUPERVISION_REPRESENTATION_FAILED" in out["failure_codes"]
    body["process"]["evidence_and_operations"]["partial_evidence"][0]["quote"] = "invented quote"
    out = protocol.inspect_paid_annotation(req, artifact(body))["new_pipeline_outcomes"]
    assert out["process_validity"] == "unknown" and not out["process_candidate_usable"]


@pytest.mark.parametrize("aux", ["missing", "malformed", "extra"])
def test_auxiliary_container_failure_cannot_poison_complete_critical_process(aux):
    req, body = specimen()
    if aux == "missing":
        del body["supervision"]
    elif aux == "malformed":
        body["supervision"] = []
    else:
        body["behavior"] = {"not_requested": True}
    out = protocol.inspect_paid_annotation(req, artifact(body))["new_pipeline_outcomes"]
    assert out["process_validity"] == "valid" and out["process_candidate_usable"]
    assert out["projection_usable"] is (aux == "extra")
    assert "WIRE_SCHEMA_FAILED" in out["failure_codes"]


def test_output_limit_retains_original_text_but_never_admits_even_complete_JSON():
    req, body = specimen()
    response = artifact(body, finish="length")
    result = protocol.inspect_paid_annotation(req, response)
    assert result["new_pipeline_outcomes"]["raw_JSON_complete"]
    assert not result["new_pipeline_outcomes"]["process_candidate_usable"]
    assert "OUTPUT_LIMIT_REACHED" in result["new_pipeline_outcomes"]["failure_codes"]
    broken = protocol.inspect_paid_annotation(req, artifact(body, raw=json.dumps(body)[:-8]))
    assert "RAW_JSON_PARSE_FAILED" in broken["new_pipeline_outcomes"]["failure_codes"]
    assert broken["new_pipeline_outcomes"]["JSON_repaired"] is False
    array = protocol.inspect_paid_annotation(req, artifact(body, raw="[]"))["new_pipeline_outcomes"]
    assert array["raw_JSON_complete"] and "WIRE_SCHEMA_FAILED" in array["failure_codes"]
    assert not array["process_candidate_usable"]


def test_no_model_fallback_or_reference_body_mutation_is_accepted():
    req, _ = specimen()
    req["model"] = "another-model"
    req["id"] = digest({k: v for k, v in req.items() if k != "id"})
    with pytest.raises(ValueError, match="model"):
        protocol.request_body(req)
