"""Private constructed math/expressibility controls, never Provider prompt examples."""

import json

from trusted_synthesis.experiments.finance_qa_vnext_finqa_difficulty.panel import node
from trusted_synthesis.experiments.finance_qa_vnext_model_execution.transport import HTTPResponse


def route(task, alternative):
    if not alternative:
        return task["target"]
    a = node
    if task["key"] == "J2":
        q1, p1, q0, p0 = task["selected"]
        return a(
            "add",
            a("multiply", a("subtract", q1, q0), p0),
            a("multiply", q1, a("subtract", p1, p0)),
        )
    c1, t1, c0, t0 = task["selected"]
    numerator = a("add", a("subtract", c1, c0), a("subtract", t1, t0))
    return a("multiply", a("divide", numerator, a("add", c0, t0)), "constant:100")


class Sender:
    transport_kind = "mock_http"

    def __init__(self, task, alternative, *, insert_error=False):
        self.task, self.tree, self.insert_error = task, route(task, alternative), insert_error
        self.called, self.sent_error = 0, False

    def choice(self, request):
        state = request["state"]
        if self.insert_error and not self.sent_error:
            self.sent_error = True
            return {
                "kind": "action",
                "state_id": state["id"],
                "operation": "read",
                "inputs": [],
                "reason": "Constructed incomplete-input control.",
                "subgoal": "Control",
                "parameters": {},
            }
        if state["pending_observation"]:
            return {
                "kind": "update",
                "state_id": state["id"],
                "observation": state["pending_observation"]["id"],
                "disposition": "accept",
            }
        claims = {json.dumps(c["expression"], sort_keys=True): c for c in state["claims"]}

        def visit(tree):
            if isinstance(tree, str) and tree.startswith("constant:"):
                return tree, None
            key = json.dumps(tree, sort_keys=True)
            if key in claims:
                return claims[key]["id"], None
            if isinstance(tree, str):
                operation, inputs = "read", [tree]
            else:
                inputs = []
                for arg in tree["args"]:
                    value, action = visit(arg)
                    if action:
                        return None, action
                    inputs.append(value)
                operation = tree["op"]
            return None, {
                "kind": "action",
                "state_id": state["id"],
                "operation": operation,
                "inputs": inputs,
                "reason": "Constructed exact dependency control.",
                "subgoal": "Local control",
                "parameters": {},
            }

        claim_id, action = visit(self.tree)
        if action:
            return action
        claim = next(c for c in state["claims"] if c["id"] == claim_id)
        return {
            "kind": "final",
            "state_id": state["id"],
            "answer_claim": claim_id,
            "result": {"value": claim["value"], "unit": self.task["unit"]},
            "citations": claim["lineage"],
        }

    def send(self, request, *, api_key):
        self.called += 1
        request = json.loads(json.loads(request["body_json"])["messages"][1]["content"])
        content = json.dumps(self.choice(request))
        return HTTPResponse(
            200,
            json.dumps(
                {
                    "id": f"mock:{self.called}",
                    "model": "deepseek-v4-pro",
                    "object": "chat.completion",
                    "choices": [
                        {
                            "index": 0,
                            "finish_reason": "stop",
                            "message": {"role": "assistant", "content": content},
                        }
                    ],
                    "usage": {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150},
                }
            ).encode(),
            (),
        )
