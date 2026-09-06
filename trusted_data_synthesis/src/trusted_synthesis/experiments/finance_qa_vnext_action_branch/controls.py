"""Finite dynamic-Action wiring checks; no Provider, financial executor or old replay."""

from __future__ import annotations

import ast
import copy
import subprocess
from pathlib import Path
from typing import Any

from trusted_synthesis.canonical_json import canonical_json_bytes
from trusted_synthesis.domains.finance.qa_vnext.action_public_contract import (
    publish_action_contract,
)
from trusted_synthesis.domains.finance.qa_vnext.action_readonly import evaluate_action_readonly
from trusted_synthesis.domains.finance.qa_vnext.runtime import DurableStore, PublicQARuntime
from trusted_synthesis.domains.finance.qa_vnext.update_public_contract import (
    publish_update_contract,
)

from ..finance_qa_vnext_model_execution.models import record, require, sha
from ..finance_qa_vnext_model_execution.plan import BASELINE_ENTRY, TaskPanel, seal_directory
from ..finance_qa_vnext_model_execution.qualification import _Artifacts
from ..finance_qa_vnext_model_execution.transport import (
    SYSTEM_PROMPT,
    TransportConfig,
    render_http_request,
)
from .plan import PREDECESSOR, initial_request

PREVIOUS_EXECUTION = (
    "trusted_data_synthesis/artifacts/qa_vnext_repaired_full_task/"
    "finance_qa_vnext_repaired_update_six_session_full_task_20260906/execution"
)


def validator_preservation(root: Path) -> dict[str, Any]:
    domain = "trusted_data_synthesis/src/trusted_synthesis/domains/finance/qa_vnext/"
    checks = []
    for relative in [
        domain + name
        for name in [
            "protocol.py",
            "update_public_contract.py",
            "program_adapter.py",
            "share_adapter.py",
        ]
    ] + ["trusted_data_synthesis/src/trusted_synthesis/canonical_json.py"]:
        old = subprocess.check_output(["git", "show", PREDECESSOR + ":" + relative], cwd=root)
        current = (root / relative).read_bytes()
        require(old == current, "action_control.unchanged_bytes:" + relative)
        checks.append({"path": relative, "kind": "byte_equal", "sha256": sha(current)})
    for name, symbol in [("runtime.py", "_admit"), ("measurement.py", "_admission")]:
        relative = domain + name
        old = subprocess.check_output(["git", "show", PREDECESSOR + ":" + relative], cwd=root)
        current = (root / relative).read_bytes()

        def body(data, symbol=symbol):
            nodes = [
                n
                for n in ast.walk(ast.parse(data))
                if isinstance(n, ast.FunctionDef) and n.name == symbol
            ]
            require(len(nodes) == 1, "action_control.unique_validator")
            return ast.dump(nodes[0], include_attributes=False)

        require(body(old) == body(current), "action_control.unchanged_admission:" + symbol)
        checks.append(
            {
                "path": relative,
                "function": symbol,
                "kind": "AST_equal",
                "baseline_file_sha256": sha(old),
                "current_file_sha256": sha(current),
            }
        )
    return record(
        "action_branch_validator_preservation",
        baseline_commit=PREDECESSOR,
        checks=checks,
        passed=True,
    )


def isolated_action_receiver(request: dict[str, Any], selected_id: str) -> dict[str, Any]:
    """Interpret only public expression vocabulary; no fixture helper or Runtime private state."""
    publication = request["public_action_contract"]

    def locate(document, path):
        for raw in path[1:].split("/"):
            key = raw.replace("~1", "/").replace("~0", "~")
            document = document[int(key)] if isinstance(document, list) else document[key]
        return copy.deepcopy(document)

    binding = publication["selected_binding"]
    selected = [
        a
        for a in locate(request, binding["request_collection"])
        if a[binding["id_field"]] == selected_id
    ]
    require(len(selected) == binding["match_count"], "receiver.selected_public_choice")

    def expression(spec):
        if "literal" in spec:
            return copy.deepcopy(spec["literal"])
        if "copy_from" in spec:
            return locate(request, spec["copy_from"])
        if "all_ids_from" in spec:
            return [a[spec["id_field"]] for a in locate(request, spec["all_ids_from"])]
        if "choose_id_from" in spec:
            require(
                selected_id
                in [a[spec["id_field"]] for a in locate(request, spec["choose_id_from"])],
                "receiver.choice",
            )
            return selected_id
        if "copy_from_selected" in spec:
            return locate(selected[0], spec["copy_from_selected"])
        if "choose_from_selected" in spec:
            return locate(selected[0], spec["choose_from_selected"])[0]
        raise ValueError("receiver.unsupported_public_expression")

    response = {}
    for rule in publication["rules"]:
        for path, spec in rule["fields"].items():
            tokens, target = path[1:].split("/"), response
            for token in tokens[:-1]:
                target = target.setdefault(token, {})
            target[tokens[-1]] = expression(spec)
    return response


def saved_requests(panel: TaskPanel) -> list[dict[str, Any]]:
    candidates = []
    for label in ["B01", "B02", "C01", "S01"]:
        directory = panel.root / PREVIOUS_EXECUTION / "sessions" / label / "runtime"
        files = _Artifacts(directory)
        session = files.json("session.json")
        for event in session["events"]:
            if event["request"]["available_actions"]:
                candidates.append(
                    {
                        "label": label,
                        "group": label[0],
                        "sequence": event["sequence"],
                        "request": event["request"],
                        "manifest_id": files.manifest["id"],
                    }
                )
    branch = [r for r in candidates if r["group"] == "B"]
    selected = [
        next(r for r in branch if len(r["request"]["available_actions"]) == n) for n in [4, 3, 2]
    ]
    selected.append(
        next(
            r
            for r in branch
            if any(a["operation"] == "growth" for a in r["request"]["available_actions"])
        )
    )
    selected.extend(next(r for r in candidates if r["group"] == group) for group in ["C", "S"])
    unique = {r["request"]["id"]: r for r in selected}
    require(
        any(
            any(a["operation"] == "growth" for a in r["request"]["available_actions"])
            for r in unique.values()
        ),
        "action_control.dynamic_new_operation",
    )
    return list(unique.values())


class ZeroCallback:
    binding = record("action_branch_zero_callback", provider_calls=0)

    def generate(self, request):
        raise AssertionError("controls cannot invoke callbacks")


def run_controls(panel: TaskPanel, directory: Path, config: TransportConfig) -> dict[str, Any]:
    store = DurableStore(directory)
    require(
        config.system_prompt == SYSTEM_PROMPT
        and config.attempts_per_session == 32
        and config.maximum_pilot_attempts == 64,
        "action_control.full_configuration",
    )
    runtime = PublicQARuntime(
        panel.adapter("B"),
        ZeroCallback(),
        directory / "initial",
        max_actions=12,
        max_submissions=32,
    )
    require(
        canonical_json_bytes(runtime.request())
        == canonical_json_bytes(initial_request(panel.adapter("B"))),
        "action_control.real_initial_entry",
    )
    rows, sources, budget_rows = [], saved_requests(panel), []
    initial_ids = {
        a["id"]
        for a in next(r for r in sources if r["group"] == "B")["request"]["available_actions"]
    }

    def check(source, request, label, response, expected, expected_code=None):
        raw = canonical_json_bytes(response)
        old_result = evaluate_action_readonly(
            raw, source["request"], panel.adapter(source["group"])
        )
        new_result = evaluate_action_readonly(raw, request, panel.adapter(source["group"]))
        require(
            old_result["action_admitted"] == new_result["action_admitted"] == expected,
            "action_control.admission_result:" + label,
        )
        require(
            old_result["error_code"] == new_result["error_code"],
            "action_control.unchanged_acceptance_set",
        )
        require(
            expected_code is None or new_result["error_code"] == expected_code,
            "action_control.exact_rejection",
        )
        index = len(rows)
        store.write(f"cases/{index:03d}_response.json", raw)
        rows.append(
            {
                "case": label,
                "source_label": source["label"],
                "source_sequence": source["sequence"],
                "source_request_id": source["request"]["id"],
                "public_request_id": request["id"],
                "source_manifest_id": source["manifest_id"],
                "raw_sha256": sha(raw),
                "before": old_result,
                "after": new_result,
            }
        )

    for i, source in enumerate(sources):
        request = publish_action_contract(source["request"])
        store.json(f"sources/{i:02d}_original.json", source["request"])
        store.json(f"sources/{i:02d}_published.json", request)
        options = request["available_actions"]
        for option in options:
            good = isolated_action_receiver(request, option["id"])
            check(source, request, "every_legal_choice", good, True)
            reverse = copy.deepcopy(good)
            reverse["decision"]["candidate_action_ids"].reverse()
            check(source, request, "candidate_permutation", reverse, True)
        good = isolated_action_receiver(request, options[0]["id"])
        if len(options) > 1:
            for name, ids in [
                ("selected_only", [options[0]["id"]]),
                ("proper_subset", [a["id"] for a in options[:-1]]),
                ("duplicate", good["decision"]["candidate_action_ids"] + [options[0]["id"]]),
                (
                    "extra",
                    good["decision"]["candidate_action_ids"] + ["control:non_current_action"],
                ),
            ]:
                bad = copy.deepcopy(good)
                bad["decision"]["candidate_action_ids"] = ids
                check(source, request, name, bad, False, "admission.alternative_set")
            bad = copy.deepcopy(good)
            bad["decision"]["basis"] = copy.deepcopy(options[1]["basis"])
            check(source, request, "other_candidate_basis", bad, False, "admission.public_judgment")
            other = next((a for a in options if a["operation"] != options[0]["operation"]), None)
            if other:
                bad = copy.deepcopy(good)
                bad["operation"] = other["operation"]
                check(
                    source,
                    request,
                    "other_candidate_operation",
                    bad,
                    False,
                    "admission.selected_action_content",
                )
        bad = copy.deepcopy(good)
        bad["decision"]["selected_action_id"] = "control:non_current_action"
        check(source, request, "unavailable_selected_id", bad, False, "admission.selected_action")
        if source["group"] == "B" and {a["id"] for a in options} != initial_ids:
            bad = copy.deepcopy(good)
            bad["decision"]["candidate_action_ids"] = sorted(initial_ids)
            check(
                source, request, "stale_initial_full_set", bad, False, "admission.alternative_set"
            )
        growth = next((a for a in options if a["operation"] == "growth"), None)
        if growth:
            require(growth["id"] not in initial_ids, "action_control.not_deletion_only")
            bad = isolated_action_receiver(request, growth["id"])
            bad["inputs"].reverse()
            check(
                source,
                request,
                "input_order_not_set_equality",
                bad,
                False,
                "admission.selected_action_content",
            )
    # Budget-check all already persisted full B phases; do not execute the old trajectory.
    directory_path = panel.root / BASELINE_ENTRY / "sessions/branch_cdw_fy2015_fy2016"
    files = _Artifacts(directory_path)
    for event in files.json("session.json")["events"]:
        request = event["request"]
        if "public_update_contract" not in request:
            request = publish_update_contract(request)
        request = publish_action_contract(request)
        http = render_http_request(
            request,
            config,
            session_id="offline_full_branch_budget",
            attempt_index=event["sequence"],
        )
        require(
            http["body_byte_count"] <= config.maximum_serialized_request_bytes,
            "action_control.full_branch_http_budget",
        )
        budget_rows.append(
            {
                "sequence": event["sequence"],
                "request_id": request["id"],
                "body_bytes": http["body_byte_count"],
                "phase": request["state"]["phase"],
            }
        )
    report = record(
        "action_branch_controls",
        rows=rows,
        control_count=len(rows),
        local_admission_evaluations=2 * len(rows),
        source_request_count=len(sources),
        covered_branch_candidate_counts=sorted(
            {len(r["request"]["available_actions"]) for r in sources if r["group"] == "B"}
        ),
        full_branch_budget_rows=budget_rows,
        provider_calls=0,
        action_executions=0,
        update_commits=0,
        old_operations_reexecuted=False,
        control_outputs_in_model_prefix=False,
        current_not_initial_candidate_universe_checked=True,
        passed=True,
    )
    store.json("report.json", report)
    seal_directory(store, kind="action_branch_controls_manifest", report_id=report["id"])
    return report
