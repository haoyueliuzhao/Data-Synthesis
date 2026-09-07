"""Post-batch public-contract clarification: offline controls, zero Provider."""

import json
from pathlib import Path

import pytest

from trusted_synthesis.experiments.finance_qa_vnext_finqa_difficulty.controls import witness
from trusted_synthesis.experiments.finance_qa_vnext_finqa_difficulty.panel import SPECS, Panel
from trusted_synthesis.experiments.finance_qa_vnext_finqa_difficulty.reference_revision import (
    REFERENCE_RULE,
    VERSION,
    ReferenceExplicitRuntime,
)
from trusted_synthesis.experiments.finance_qa_vnext_finqa_difficulty.runtime import Runtime


@pytest.fixture(scope="module")
def panel():
    return Panel(Path(__file__).resolve().parents[2])


@pytest.mark.parametrize("key", list(SPECS))
@pytest.mark.parametrize("condition", ["E", "F"])
def test_reference_contract_visible_and_task_reachable(panel, key, condition):
    runtime = ReferenceExplicitRuntime(panel, key, condition, "revision-control:" + key + condition)
    proof = witness(runtime)
    assert proof["complete"] and proof["provider_calls"] == 0
    assert proof["actions"] <= 12 and proof["submissions"] <= 32
    for turn in proof["events"]:
        request = turn["request"]
        prop = request["response_schemas"]["update"]["properties"]["observation"]
        assert prop["description"] == REFERENCE_RULE
        if request["state"]["pending_observation"]:
            assert prop["const"] == request["state"]["pending_observation"]["id"]
            assert json.loads(turn["raw_response"])["observation"] == prop["const"]


def test_prior_version_retained_and_no_semantic_changes(panel):
    old = Runtime(panel, "E1", "F", "old")
    new = ReferenceExplicitRuntime(panel, "E1", "F", "new")
    assert old.protocol["version"] != VERSION == new.protocol["version"]
    assert old.context == new.context
    for key in old.protocol:
        if key not in {"id", "version"}:
            assert old.protocol[key] == new.protocol[key]
    old_request, new_request = old.request(), new.request()
    assert (
        "description" not in old_request["response_schemas"]["update"]["properties"]["observation"]
    )
    for kind in ("action", "final"):
        assert old_request["response_schemas"][kind] == new_request["response_schemas"][kind]
    for key in old_request["rules"]:
        assert old_request["rules"][key] == new_request["rules"][key]


@pytest.mark.parametrize("disposition", ["accept", "reject"])
def test_judgment_remains_model_owned_and_prose_not_repaired(panel, disposition):
    runtime = ReferenceExplicitRuntime(panel, "C1", "E", "negative-control")
    request = runtime.request()
    action = {
        "kind": "action",
        "state_id": request["state"]["id"],
        "subgoal": "offline control",
        "reason": "Read a source number.",
        "operation": "read",
        "inputs": [runtime.task["selected"][0]],
        "parameters": {},
    }
    assert runtime.transition(json.dumps(action).encode(), request)["admitted"]
    request = runtime.request()
    prose = {
        "kind": "update",
        "state_id": request["state"]["id"],
        "observation": "Accepted read of source with correct value.",
        "disposition": disposition,
    }
    event = runtime.transition(json.dumps(prose).encode(), request)
    assert not event["admitted"] and event["error"] == "lifecycle.observation_binding"
    assert runtime.pending is not None and not runtime.claims
    request = runtime.request()
    explicit = {
        "kind": "update",
        "state_id": request["state"]["id"],
        "disposition": disposition,
        "observation": request["response_schemas"]["update"]["properties"]["observation"]["const"],
    }
    assert runtime.transition(json.dumps(explicit).encode(), request)["admitted"]
    assert len(runtime.claims) == (1 if disposition == "accept" else 0)
