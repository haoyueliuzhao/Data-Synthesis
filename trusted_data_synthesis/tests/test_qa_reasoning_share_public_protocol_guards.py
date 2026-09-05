"""Guards without Engine construction, callbacks, financial actions, or source scans."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from types import FunctionType, MethodType
from typing import Any

import pytest

from trusted_synthesis.experiments.qa_reasoning_share_public_protocol import (
    engine,
    fixture,
    models,
    public_view,
)

ROOT = Path(__file__).resolve().parents[2]


def _never_invoke(_self: Any, _request: dict[str, Any]) -> bytes:
    raise AssertionError("callback guard tests must never invoke a generator")


def _action_json() -> dict[str, Any]:
    """A parser-only object, not an admitted or executed action."""
    return {
        "kind": "action",
        "state_id": "guard-test-state",
        "operation": "share_ratio",
        "inputs": [
            {"role": "numerator", "kind": "evidence", "ref_id": "guard-test-freight"},
            {"role": "denominator", "kind": "evidence", "ref_id": "guard-test-total"},
        ],
        "parameters": {},
        "public_basis": {
            "relation": "requires",
            "evidence_refs": ["guard-test-freight", "guard-test-total"],
            "claim_refs": [],
            "intended_metric": "freight_share_ratio",
        },
    }


def _encoded(value: dict[str, Any]) -> bytes:
    return json.dumps(value, ensure_ascii=False).encode("utf-8")


def test_native_fixture_callback_source_identity_is_checked_without_invocation() -> None:
    client = fixture.PublicRequestFixture()
    verified = engine.verify_callback(client, client.binding)
    assert client.calls == 0
    assert client.binding["kind"] == "deterministic_fixture"
    assert client.binding["source_path"].endswith("/fixture.py")
    assert isinstance(verified, MethodType)
    assert verified.__func__ is fixture.PublicRequestFixture.generate
    assert verified.__self__ is client


def test_instance_callback_replacement_is_rejected_without_invocation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = fixture.PublicRequestFixture()
    monkeypatch.setattr(client, "generate", MethodType(_never_invoke, client))
    with pytest.raises(models.ProtocolError, match="generator.bound_method"):
        engine.verify_callback(client, client.binding)
    assert client.calls == 0


def test_class_callback_replacement_with_real_module_globals_fails_compiled_code_guard(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = fixture.PublicRequestFixture()
    # Make the replacement pass class membership and module-globals identity.
    # The guard must reach and reject the different actual method CodeType.
    forged = FunctionType(_never_invoke.__code__, vars(fixture), name="generate")
    monkeypatch.setattr(fixture.PublicRequestFixture, "generate", forged)
    with pytest.raises(models.ProtocolError, match="generator.compiled_method"):
        engine.verify_callback(client, client.binding)
    assert client.calls == 0


def test_source_hash_mismatch_does_not_become_a_caller_origin_claim() -> None:
    client = fixture.PublicRequestFixture()
    binding = deepcopy(client.binding)
    binding["source_sha256"] = "0" * 64
    with pytest.raises(models.ProtocolError, match="generator.source_bytes"):
        engine.verify_callback(client, binding)
    assert client.calls == 0


@pytest.mark.parametrize("missing", ["state_id", "inputs", "public_basis"])
def test_parser_rejects_missing_required_action_fields(missing: str) -> None:
    original = _action_json()
    assert models.parse_submission(_encoded(original)) == original
    del original[missing]
    with pytest.raises(models.ProtocolError, match="schema.public_submission"):
        models.parse_submission(_encoded(original))


def test_parser_rejects_self_reported_model_origin() -> None:
    action = _action_json()
    action["origin"] = "model"
    with pytest.raises(models.ProtocolError, match="schema.public_submission"):
        models.parse_submission(_encoded(action))


@pytest.mark.parametrize("nested", [False, True])
def test_parser_rejects_duplicate_keys_before_any_semantic_repair(nested: bool) -> None:
    payload = _encoded(_action_json())
    original = b'"relation": "requires"' if nested else b'"state_id": "guard-test-state"'
    duplicate = (
        b'"relation": "requires", "relation": "supports"'
        if nested
        else b'"state_id": "guard-test-state", "state_id": "forged-state"'
    )
    assert original in payload
    payload = payload.replace(original, duplicate, 1)
    with pytest.raises(models.ProtocolError, match="schema.duplicate_key"):
        models.parse_submission(payload)


def test_state_snapshots_isolate_dynamic_claim_observation_and_feedback_objects() -> None:
    parent = ROOT / models.PARENT
    source = json.loads((parent / "source_binding.json").read_bytes())
    legacy = json.loads((parent / "contract.json").read_bytes())
    context = public_view.public_context(source, legacy)
    protocol = models.protocol_contract(context)
    # Projection-only records; these do not assert a real action/update happened.
    claim = models.record(
        "claim", status="accepted", proposition={"lineage": ["projection-only-claim"]}
    )
    observation = models.record(
        "observation", output={"lineage": ["projection-only-observation"]}, success=True
    )
    dynamic = models.initial_dynamic()
    dynamic.update(
        phase="update",
        accepted_claims=[claim],
        pending_observation=observation,
        action_count=2,
        update_count=1,
        submission_count=3,
        last_feedback={"code": "observation_ready"},
    )
    state = public_view.make_state(context, protocol, dynamic)
    request = public_view.request_for(state, protocol)
    dynamic["accepted_claims"][0]["proposition"]["lineage"].append("private-mutated")
    dynamic["last_feedback"]["code"] = "private-mutated"
    assert state["accepted_claims"][0]["proposition"]["lineage"] == ["projection-only-claim"]
    assert state["last_feedback"] == {"code": "observation_ready"}
    state["pending_observation"]["output"]["lineage"].append("public-mutated")
    assert observation["output"]["lineage"] == ["projection-only-observation"]
    assert request["state"]["pending_observation"]["output"]["lineage"] == [
        "projection-only-observation"
    ]
    assert request["state"]["accepted_claims"][0]["proposition"]["lineage"] == [
        "projection-only-claim"
    ]
