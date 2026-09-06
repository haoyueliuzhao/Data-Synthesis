"""Isolated public-rule receiver and finite zero-Provider repair checks.

No imports of callback helpers or Runtime private fields. Receiver uses only the
published expression vocabulary plus the requested disposition; no model sample
is built by this receiver. The real readonly admission function scores controls.
"""

from __future__ import annotations

import ast
import copy
import json
import subprocess
from pathlib import Path
from typing import Any

from trusted_synthesis.canonical_json import canonical_json_bytes
from trusted_synthesis.domains.finance.qa_vnext.protocol import require
from trusted_synthesis.domains.finance.qa_vnext.runtime import evaluate_update_readonly
from trusted_synthesis.experiments.finance_qa_vnext_model_execution.models import sha

from .models import BASELINE, record


def isolated_receiver(request: dict[str, Any], disposition: str) -> dict[str, Any]:
    """Independent interpreter: no domain paths or financial field names hardcoded."""

    def locate(path: str) -> Any:
        value: Any = request
        for token in path[1:].split("/"):
            token = token.replace("~1", "/").replace("~0", "~")
            value = value[int(token)] if isinstance(value, list) else value[token]
        return copy.deepcopy(value)

    def expression(spec: dict[str, Any]) -> Any:
        if "by_disposition" in spec:
            return expression(spec["by_disposition"][disposition])
        if "literal" in spec:
            return copy.deepcopy(spec["literal"])
        if "choose_from_literal" in spec:
            assert disposition in spec["choose_from_literal"]
            return disposition
        if "copy_from" in spec:
            return locate(spec["copy_from"])
        if "wrap_in_list_from" in spec:
            return [locate(spec["wrap_in_list_from"])]
        if "choose_from" in spec:
            return locate(spec["choose_from"])[0]
        raise ValueError("control.unknown_public_expression")

    result: dict[str, Any] = {}
    for rule in request["public_update_contract"]["rules"]:
        for path, spec in rule["fields"].items():
            tokens = path[1:].split("/")
            parent = result
            for token in tokens[:-1]:
                parent = parent.setdefault(token, {})
            parent[tokens[-1]] = expression(spec)
    return result


def unchanged_validator(root: Path) -> dict[str, Any]:
    relative = "trusted_data_synthesis/src/trusted_synthesis/"
    checks = []
    for path, function in (
        ("domains/finance/qa_vnext/protocol.py", None),
        ("canonical_json.py", None),
        ("domains/finance/qa_vnext/runtime.py", "_admit"),
        ("domains/finance/qa_vnext/measurement.py", "_admission"),
    ):
        name = relative + path
        old = subprocess.check_output(["git", "show", BASELINE + ":" + name], cwd=root)
        current = (root / name).read_bytes()
        if function is None:
            same = old == current
        else:

            def body(data: bytes, function: str = function) -> str:
                nodes = [
                    node
                    for node in ast.walk(ast.parse(data))
                    if isinstance(node, ast.FunctionDef) and node.name == function
                ]
                require(len(nodes) == 1, "control.unique_validator")
                return ast.dump(nodes[0], include_attributes=False)

            same = body(old) == body(current)
        require(same, "control.validator_changed:" + name)
        checks.append(
            {
                "path": name,
                "function": function,
                "unchanged": same,
                "baseline_file_sha256": sha(old),
                "current_file_sha256": sha(current),
            }
        )
    return record("unchanged_validator", baseline_commit=BASELINE, checks=checks)


def check_public_rules(requests: dict[str, dict[str, Any]]) -> dict[str, Any]:
    rows = []
    for label in ("C01", "B01", "S01", "S03"):
        request = requests[label]
        before = canonical_json_bytes(request)
        good = isolated_receiver(request, "accept")
        cases: list[tuple[str, bytes, bool, bool]] = [
            ("accept", canonical_json_bytes(good), True, True),
            ("reject", canonical_json_bytes(isolated_receiver(request, "reject")), True, False),
            (
                "whitespace_key_order",
                json.dumps(dict(reversed(list(good.items()))), indent=3).encode(),
                True,
                True,
            ),
        ]

        def bad(name: str, path: tuple[str, ...], value: Any, good=good, cases=cases) -> None:
            changed = copy.deepcopy(good)
            target = changed
            for field in path[:-1]:
                target = target[field]
            target[path[-1]] = value
            cases.append((name, canonical_json_bytes(changed), False, False))

        prop = good["proposed_claim"]
        bad("null_accept", ("proposed_claim",), None)
        bad("flat_numeric_claim", ("proposed_claim",), {"value": "12988.7"})
        bad("single_number", ("proposed_claim",), 12988.7)
        bad("output_only", ("proposed_claim",), prop.get("output", {}))
        bad("observation_wrapper", ("proposed_claim",), request["state"]["pending_observation"])
        for field in prop:
            bad("proposition_field_" + field, ("proposed_claim", field), {"tampered": True})
        numeric_path = (
            ("proposed_claim", "output", "difference")
            if label == "C01"
            else ("proposed_claim", "output", "payload", "value")
            if label == "B01"
            else ("proposed_claim", "output", "value")
        )
        bad("numeric_value_only", numeric_path, "0")
        bad("numeric_type_coercion", numeric_path, 12988.7)
        bad("lineage_reference_only", ("proposed_claim", "lineage"), ["wrong-reference"])
        bad(
            "operation_contract_reference_only",
            ("proposed_claim", "operation_contract_id"),
            "wrong-contract",
        )
        bad("operation_name_only", ("proposed_claim", "operation"), "wrong-operation")
        if len(prop["lineage"]) > 1:
            bad(
                "lineage_array_order",
                ("proposed_claim", "lineage"),
                list(reversed(prop["lineage"])),
            )
            bad(
                "assessment_array_order",
                ("assessment", "evidence_refs"),
                list(reversed(prop["lineage"])),
            )
        missing = copy.deepcopy(prop)
        missing.pop("operation_contract_id")
        bad("omitted_contract_field", ("proposed_claim",), missing)
        bad("extra_proposition_field", ("proposed_claim",), {**prop, "unrequested": True})
        for name, path, value in (
            ("state_parent", ("state_id",), "wrong"),
            ("observation_parent", ("observation_id",), "wrong"),
            ("relation", ("assessment", "relation"), "declines_observation"),
            ("observation_refs", ("assessment", "observation_refs"), []),
            ("evidence_refs", ("assessment", "evidence_refs"), ["wrong"]),
            ("fulfills", ("assessment", "fulfills_obligation"), None),
            ("remaining", ("remaining_uncertainty_refs",), ["invented"]),
            ("enabled", ("newly_enabled_obligation_ids",), ["invented"]),
            ("next", ("next_subgoal",), "invented"),
        ):
            bad(name, path, value)
        for name, raw, admitted, accepted in cases:
            result = evaluate_update_readonly(raw, request)
            require(
                result["update_admitted"] is admitted and result["complete_accept"] is accepted,
                "control.case:" + label + name,
            )
            diagnostic = (result["feedback"] or {}).get("public_diagnostic")
            if result["error_code"] and result["error_code"].startswith("admission."):
                require(
                    diagnostic is not None
                    and diagnostic["rule_id"]
                    in {rule["rule_id"] for rule in request["public_update_contract"]["rules"]},
                    "control.feedback_public_rule",
                )
            rows.append(
                {
                    "label": label,
                    "case": name,
                    "raw_response": raw.decode(),
                    "evaluation": result,
                    "expected_admitted": admitted,
                    "expected_complete_accept": accepted,
                    "passed": True,
                }
            )
        require(canonical_json_bytes(request) == before, "control.request_mutation")
    return record(
        "public_rule_controls",
        passed=True,
        rows=rows,
        provider_calls=0,
        action_executions=0,
        update_commits=0,
        old_callback_helper_imported=False,
        receiver_uses_only_published_expressions=True,
        model_samples=0,
    )
