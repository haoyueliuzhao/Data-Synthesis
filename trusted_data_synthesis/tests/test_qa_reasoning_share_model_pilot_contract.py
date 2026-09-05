"""Pure preparation checks: no adapter calls, session exchange, credentials or kernels."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from trusted_synthesis.canonical_json import canonical_json_bytes
from trusted_synthesis.experiments.qa_reasoning_share_model_pilot import models
from trusted_synthesis.experiments.qa_reasoning_share_model_pilot.adapter import (
    DeepSeekAdapter,
    MockTransport,
    render_http_request,
)
from trusted_synthesis.experiments.qa_reasoning_share_public_protocol.engine import verify_callback
from trusted_synthesis.experiments.qa_reasoning_share_public_protocol.models import initial_dynamic
from trusted_synthesis.experiments.qa_reasoning_share_public_protocol.public_view import (
    make_state,
    request_for,
)

ROOT = Path(__file__).resolve().parents[2]
PARENT = ROOT / models.PARENT


def _inputs():
    context = json.loads((PARENT / "public_context.json").read_bytes())
    parent_protocol = json.loads((PARENT / "protocol_contract.json").read_bytes())
    config = models.model_config()
    protocol = models.protocol_contract(parent_protocol, config)
    return context, parent_protocol, config, protocol


def test_public_grammar_and_semantic_bounds_are_identical() -> None:
    context, old, config, protocol = _inputs()
    assert protocol["public_context_id"] == context["id"]
    assert protocol["bounds"] == old["bounds"] == {"actions": 3, "updates": 3, "submissions": 12}
    assert protocol["submission_schemas"] == old["submission_schemas"]
    assert protocol["task_id"] == old["task_id"]
    assert protocol["id"] != old["id"]
    assert protocol["parent_protocol_id"] == old["id"]
    assert protocol["model_configuration_id"] == config["id"]
    assert protocol["automatic_observation_acceptance"] is False
    assert protocol["host_fills_missing_proposed_claim"] is False


def test_exact_six_neutral_nonreplaceable_declarations() -> None:
    _, _, config, protocol = _inputs()
    declarations = models.session_declarations(protocol, config)
    assert len(declarations) == len({d["id"] for d in declarations}) == 6
    assert [d["label"] for d in declarations] == ["M01", "M02", "M03", "M04", "M05", "M06"]
    assert all(d["neutral_prompt"] and d["independent_initial_state"] for d in declarations)
    assert all(d["reference_route"] is None and not d["replacement_allowed"] for d in declarations)
    assert sum(d["maximum_provider_attempts"] for d in declarations) == 72


def test_actual_serialized_input_is_measured_without_equating_bytes_to_tokens() -> None:
    context, _, config, protocol = _inputs()
    state = make_state(context, protocol, initial_dynamic())
    public_request = request_for(state, protocol)
    request = render_http_request(
        public_request, config, session_id="dry", turn_index=0, call_id="dry"
    )
    body = request["body_json"].encode()
    assert request["body_byte_count"] == len(body)
    assert request["input_token_upper_bound"] == len(body) + 1024
    assert request["input_token_upper_bound"] <= config["maximum_input_tokens"]
    assert config["exact_offline_model_tokenization_claimed"] is False
    assert config["maximum_public_response_bytes"] == 32768
    assert config["max_tokens"] == 8192
    assert json.loads(json.loads(body)["messages"][1]["content"]) == public_request
    assert public_request["allowed_submission_kinds"] == ["action", "final"]


def test_all_six_initial_http_bodies_have_identical_information() -> None:
    context, _, config, protocol = _inputs()
    snapshots = [make_state(context, protocol, initial_dynamic()) for _ in range(6)]
    bodies = [
        render_http_request(
            request_for(state, protocol), config, session_id=f"M{i}", turn_index=0, call_id=f"c{i}"
        )["body_json"]
        for i, state in enumerate(snapshots)
    ]
    assert len(set(bodies)) == 1
    snapshots[0]["evidence"]["total"]["value"] = "changed"
    assert snapshots[1]["evidence"]["total"]["value"] == "21813"


def test_resource_reservations_and_retry_limits_are_fixed() -> None:
    config = models.model_config()
    per_attempt = config["maximum_input_tokens"] + config["max_tokens"]
    assert per_attempt == config["maximum_request_reserved_tokens"] == 74752
    assert config["maximum_session_reserved_tokens"] == 12 * per_attempt
    assert config["maximum_pilot_reserved_tokens"] == 72 * per_attempt
    assert (
        config["automatic_retries"]
        == config["redirects"]
        == config["model_fallbacks"]
        == config["session_replacements"]
        == 0
    )


def test_model_and_mock_bindings_cannot_be_confused() -> None:
    config = models.model_config()
    model = DeepSeekAdapter(config)
    mock = DeepSeekAdapter(
        config, transport=MockTransport(lambda _: {"http_status": 200, "body": b"{}"})
    )
    assert model.binding["origin"] == "model"
    assert mock.binding["origin"] == "adapter_mock"
    assert model.binding["id"] != mock.binding["id"]
    assert callable(verify_callback(model, model.binding["adapter_callback"]))
    assert callable(verify_callback(mock.transport, mock.binding["transport_binding"]))


def test_request_configuration_cannot_be_changed_in_place() -> None:
    context, _, config, protocol = _inputs()
    altered = copy.deepcopy(config)
    altered["temperature"] = 0.1
    request = request_for(make_state(context, protocol, initial_dynamic()), protocol)
    with pytest.raises(ValueError, match="adapter.frozen_configuration"):
        render_http_request(request, altered, session_id="dry", turn_index=0, call_id="dry")
    assert canonical_json_bytes(config) == canonical_json_bytes(models.model_config())
