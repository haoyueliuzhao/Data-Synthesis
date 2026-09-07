"""New-stage zero-Provider controls; no historical experiment reruns."""

import json
from pathlib import Path

import pytest

from trusted_synthesis.experiments.finance_qa_vnext_finqa_difficulty.census import census, structure
from trusted_synthesis.experiments.finance_qa_vnext_finqa_difficulty.panel import SPECS, Panel
from trusted_synthesis.experiments.finance_qa_vnext_finqa_difficulty.runtime import Runtime
from trusted_synthesis.experiments.finance_qa_vnext_finqa_difficulty.semantics import equivalent
from trusted_synthesis.experiments.finance_qa_vnext_finqa_difficulty.sources import numeric_spans

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def panel():
    return Panel(ROOT)


def submit(runtime, **fields):
    request = runtime.request()
    raw = json.dumps({"state_id": request["state"]["id"], **fields}).encode()
    return runtime.transition(raw, request)


def action(runtime, op, inputs):
    return submit(
        runtime,
        kind="action",
        operation=op,
        inputs=inputs,
        parameters={},
        subgoal="offline control",
        reason="Source-bound static reachability control, never a population sample.",
    )


def accept(runtime):
    result = submit(runtime, kind="update", observation=runtime.pending["id"], disposition="accept")
    assert result["admitted"]
    return result["claim"]["id"]


def execute_tree(runtime, tree, cache=None):
    cache = {} if cache is None else cache
    key = json.dumps(tree, sort_keys=True)
    if key in cache:
        return cache[key]
    if isinstance(tree, str):
        if tree.startswith("constant:"):
            return tree
        event = action(runtime, "read", [tree])
    else:
        inputs = [execute_tree(runtime, t, cache) for t in tree["args"]]
        event = action(runtime, tree["op"], inputs)
    assert event["admitted"], event
    cache[key] = accept(runtime)
    return cache[key]


def finish(runtime, claim_id):
    answer = next(c for c in runtime.claims if c["id"] == claim_id)
    return submit(
        runtime,
        kind="final",
        answer_claim=claim_id,
        result={"value": answer["value"], "unit": runtime.task["unit"]},
        citations=answer["lineage"],
    )


def test_census_exact_repository_population():
    rows, summary = census(ROOT)
    assert len(rows) == 1147
    assert summary["histograms"]["program_ops"] == {"1": 654, "2": 409, "3": 55, "4": 10, "5": 19}
    assert summary["total_annotated_operations"] == 1772
    assert summary["histograms"]["support_type"] == {"mixed": 158, "table": 706, "text": 283}
    assert summary["branch_merge_questions"] == 32
    assert summary["intermediate_reuse_questions"] == 8
    assert summary["overlap"]["document"]["distinct"] == 380
    assert all(r["program_re_depth"] == r["final_dag_depth"] for r in rows)


def test_dependency_not_execution_order():
    s = structure("subtract(3, 1), divide(#0, 1), subtract(4, 1), divide(#2, 1), subtract(#1, #3)")
    assert s["program_ops"] == 5 and s["dag_depth"] == 3 and s["branch_merge_nodes"] == 1


@pytest.mark.parametrize("key", list(SPECS))
@pytest.mark.parametrize("condition", ["E", "F"])
def test_original_task_reachable(panel, key, condition):
    r = Runtime(panel, key, condition, "mock:" + key + condition)
    claim = execute_tree(r, r.task["target"])
    assert finish(r, claim)["admitted"]
    assert r.actions <= 12 and r.submissions <= 25


def test_source_and_gold_annotations_unchanged(panel):
    for b in panel.bindings():
        assert b["original_qa"] == panel.entries[b["qa_id"]]["qa"]
        assert not b["semantic_question_changed"]
    for key in SPECS:
        e, f = panel.public(key, "E"), panel.public(key, "F")
        assert e["question"] == f["question"] == panel.tasks[key]["entry"]["qa"]["question"]
        assert f["original_source"] == {
            k: panel.tasks[key]["entry"][k] for k in ("table", "pre_text", "post_text")
        }
        assert {i["id"] for i in e["numeric_catalog"]} < {i["id"] for i in f["numeric_catalog"]}
        assert "target" not in f and "gold_inds" not in f and "selected" not in f


def test_negative_accounting_duplicate_is_not_positive():
    assert [s["value"] for s in numeric_spans("$ -6.3 ( 6.3 )")] == ["-63/10"]


def test_numeric_truth_is_not_target_validity(panel):
    r = Runtime(panel, "C3", "F", "mock")
    assert action(r, "read", [r.task["selected"][0]])["admitted"]
    c = accept(r)
    assert not finish(r, c)["admitted"]  # number equals minimum, but minimum not established
    assert r.feedback == "final.target_not_established"


def test_pending_and_current_session_refs(panel):
    r = Runtime(panel, "C1", "F", "mock")
    action(r, "read", [r.task["selected"][0]])
    assert not action(r, "add", [r.pending["id"], "constant:1"])["admitted"]
    c = accept(r)
    other = Runtime(panel, "C1", "F", "other")
    assert not action(other, "add", [c, "constant:1"])["admitted"]


def test_no_host_percent_conversion(panel):
    r = Runtime(panel, "C2", "F", "mock")
    claim = execute_tree(r, r.task["target"]["args"][0])
    assert not finish(r, claim)["admitted"]
    assert r.feedback == "final.target_not_established"


def test_alternative_mean_and_order_are_not_whitelisted(panel):
    r = Runtime(panel, "M1", "E", "mock")
    alternative = {
        "op": "divide",
        "args": [{"op": "sum", "args": list(reversed(r.task["selected"]))}, "constant:3"],
    }
    assert equivalent(alternative, r.task["target"])
    assert finish(r, execute_tree(r, alternative))["admitted"]


def test_wrong_period_same_number_not_semantically_aliased(panel):
    # 2015 coal 3237 appears in the 2016 source, but different source identities
    # are not admitted simply because the resulting numeric value coincides.
    assert not equivalent("source:t1c1n0", "source:t1c2n0")


def test_reason_and_schema_not_repaired(panel):
    r = Runtime(panel, "C1", "E", "mock")
    event = submit(
        r,
        kind="action",
        operation="read",
        inputs=[r.task["selected"][0]],
        parameters={},
        subgoal="x",
        reason="x" * 481,
    )
    assert not event["admitted"] and r.actions == 0
    request = r.request()
    assert not r.transition(b'{"kind":"action","kind":"final"}', request)["admitted"]


def test_mock_transport_and_readonly_audit_end_to_end(panel, tmp_path):
    from trusted_synthesis.domains.finance.qa_vnext.protocol import record
    from trusted_synthesis.experiments.finance_qa_vnext_finqa_difficulty.audit import verify_session
    from trusted_synthesis.experiments.finance_qa_vnext_finqa_difficulty.controls import witness
    from trusted_synthesis.experiments.finance_qa_vnext_finqa_difficulty.stage import configuration
    from trusted_synthesis.experiments.finance_qa_vnext_model_execution.transport import (
        HTTPResponse,
        OnlineModelCallback,
    )

    registration = record("mock_registration", label="C1_E_01", task_key="C1", condition="E")
    expected = witness(Runtime(panel, "C1", "E", registration["id"]))

    class Sender:
        def send(self, request, *, api_key):
            e = expected["events"][request["turn_index"]]
            assert json.loads(request["body"]["messages"][1]["content"]) == e["request"]
            envelope = {
                "id": "mock-not-a-provider-sample",
                "object": "chat.completion",
                "model": "deepseek-v4-pro",
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": e["raw_response"]},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
            }
            return HTTPResponse(200, json.dumps(envelope).encode())

    callback = OnlineModelCallback(
        configuration(),
        session_id=registration["id"],
        evidence_directory=tmp_path / "transport",
        sender=Sender(),
    )
    runtime = Runtime(panel, "C1", "E", registration["id"], callback, tmp_path / "runtime")
    runtime.run()
    callback.finalize()
    audit = verify_session(panel, registration, tmp_path, model_required=False)
    assert audit["complete_valid"] and not audit["model_origin_verified"]
    assert audit["provider_attempts"] == 7
    with pytest.raises(Exception, match="audit.model_origin"):
        verify_session(panel, registration, tmp_path)


@pytest.mark.parametrize("key", ["C1", "C2", "M1"])
def test_alternative_source_support_is_executable(panel, key):
    r = Runtime(panel, key, "F", "alternative:" + key)
    if key == "C1":
        alternative = {"op": "sum", "args": [f"source:t{i}c1n0" for i in range(2, 8)]}
    elif key == "C2":
        alternative = {
            "op": "multiply",
            "args": [
                {
                    "op": "divide",
                    "args": [
                        r.task["selected"][0],
                        {"op": "add", "args": ["source:t7c1n0", "source:t8c1n0"]},
                    ],
                },
                "constant:100",
            ],
        }
    else:
        alternative = {
            "op": "average",
            "args": [
                {"op": "subtract", "args": [f"source:t13c{i}n0", f"source:t12c{i}n0"]}
                for i in range(1, 4)
            ],
        }
    assert finish(r, execute_tree(r, alternative))["admitted"]
    assert r.actions <= 12


def test_source_sign_supports_magnitude_alternative(panel):
    task = panel.tasks["J1"]
    a, b, c, d = task["selected"]

    def sub(x, y):
        return {"op": "subtract", "args": [x, {"op": "absolute", "args": [y]}]}

    alternative = {
        "op": "multiply",
        "args": [
            {
                "op": "divide",
                "args": [{"op": "subtract", "args": [sub(a, b), sub(c, d)]}, sub(c, d)],
            },
            "constant:100",
        ],
    }
    r = Runtime(panel, "J1", "F", "magnitude")
    assert finish(r, execute_tree(r, alternative))["admitted"]


def test_final_decimal_schema_and_citations_not_filled(panel):
    r = Runtime(panel, "C1", "E", "final-control")
    cid = execute_tree(r, r.task["target"])
    assert not submit(
        r,
        kind="final",
        answer_claim=cid,
        result={"value": "94/1", "unit": "USD_million"},
        citations=[],
    )["admitted"]
    assert not submit(
        r,
        kind="final",
        answer_claim=cid,
        result={"value": "94", "unit": "USD_million"},
        citations=[],
    )["admitted"]
    assert not r.terminal
