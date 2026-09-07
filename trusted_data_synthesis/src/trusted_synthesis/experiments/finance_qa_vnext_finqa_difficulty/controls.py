"""Static reachability witnesses, explicitly excluded from online denominators."""

import json

from trusted_synthesis.domains.finance.qa_vnext.protocol import require


def submission(runtime, fields):
    request = runtime.request()
    raw = json.dumps({"state_id": request["state"]["id"], **fields}).encode()
    event = runtime.transition(raw, request)
    require(event["admitted"], "control.static_witness_failed")
    return request, raw, event


def witness(runtime):
    events, cache = [], {}

    def send(fields):
        request, raw, event = submission(runtime, fields)
        events.append({"request": request, "raw_response": raw.decode(), "event": event})
        return event

    def visit(tree):
        key = json.dumps(tree, sort_keys=True)
        if key in cache:
            return cache[key]
        if isinstance(tree, str) and tree.startswith("constant:"):
            return tree
        op = "read" if isinstance(tree, str) else tree["op"]
        inputs = [tree] if isinstance(tree, str) else [visit(t) for t in tree["args"]]
        send(
            {
                "kind": "action",
                "subgoal": "static offline witness",
                "reason": "Control only; no Provider or population sample.",
                "operation": op,
                "inputs": inputs,
                "parameters": {},
            }
        )
        event = send(
            {"kind": "update", "observation": runtime.pending["id"], "disposition": "accept"}
        )
        cache[key] = event["claim"]["id"]
        return cache[key]

    final_id = visit(runtime.task["target"])
    final = next(c for c in runtime.claims if c["id"] == final_id)
    send(
        {
            "kind": "final",
            "answer_claim": final_id,
            "result": {"value": final["value"], "unit": runtime.task["unit"]},
            "citations": final["lineage"],
        }
    )
    return {
        "provider_calls": 0,
        "population_samples": 0,
        "origin": "adapter_mock",
        "complete": runtime.terminal,
        "actions": runtime.actions,
        "submissions": runtime.submissions,
        "events": events,
    }
