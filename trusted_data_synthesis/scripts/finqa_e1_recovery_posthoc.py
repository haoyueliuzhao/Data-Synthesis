"""Post-batch raw proposal supplement; does not repair/replay/admit submissions.

Frozen metrics classify parsed model_submission. This read-only inspection also
exposes valid-JSON Action-shaped raw content rejected at schema validation.
No Provider callback and no hypothetical repaired trajectory are constructed.
"""

import argparse
import hashlib
import json
from pathlib import Path

from pydantic import ValidationError

from trusted_synthesis.domains.finance.qa_vnext.protocol import record, require
from trusted_synthesis.domains.finance.qa_vnext.runtime import DurableStore
from trusted_synthesis.experiments.finance_qa_vnext_finqa_difficulty.panel import Panel
from trusted_synthesis.experiments.finance_qa_vnext_finqa_difficulty.runtime import (
    Action,
    Final,
    Update,
)
from trusted_synthesis.experiments.finance_qa_vnext_finqa_difficulty.semantics import (
    TOOLS,
    equivalent,
)
from trusted_synthesis.experiments.finance_qa_vnext_finqa_final_recovery.audit import (
    independent_value,
    read,
)
from trusted_synthesis.experiments.finance_qa_vnext_finqa_final_recovery.stage import LABELS, OUTPUT
from trusted_synthesis.experiments.finance_qa_vnext_harness_responsibility.audit import manifest
from trusted_synthesis.experiments.finance_qa_vnext_model_execution.plan import (
    seal_directory,
    verify_source_snapshot,
)


def inspect(root):
    output = root / OUTPUT
    online = manifest(output / "online")
    verify_source_snapshot(root, read(output / "preparation/implementation.json"))
    task = Panel(root).tasks["E1"]
    target = task["target"]
    numerator, denominator = target["args"][0]["args"]
    probes = {
        "denominator_in_numerator_scale": denominator,
        "numerator_in_denominator_scale": {
            "op": "multiply",
            "args": [numerator, denominator["args"][1]],
        },
        "normalized_ratio": target["args"][0],
        "complete_percent_target": target,
    }
    rows = []
    for label in LABELS:
        directory = output / "online/sessions" / label
        manifest(directory)
        audit = read(directory / "audit.json")
        trigger = audit["recovery_trace"]["first_target_rejection_submission"]
        invalid, raw_action_indices, candidates = [], [], []
        for path in sorted((directory / "runtime/turns").glob("*_transition.json")):
            event = read(path)
            index = event["submission_count"]
            request_path = path.with_name(path.name.replace("_transition.json", "_request.json"))
            request = read(request_path)
            raw_path = path.with_name(path.name.replace("_transition.json", "_response.raw"))
            raw = raw_path.read_bytes()
            require(hashlib.sha256(raw).hexdigest() == event["raw_sha256"], "posthoc.original_raw")
            try:
                value = json.loads(raw)
            except json.JSONDecodeError as exc:
                require(not event["admitted"], "posthoc.invalid_json_not_admitted")
                invalid.append(
                    {
                        "submission": index,
                        "error": event["error"],
                        "raw_path": raw_path.relative_to(root).as_posix(),
                        "raw_sha256": event["raw_sha256"],
                        "classification": "invalid_json",
                        "json_error": exc.msg,
                        "raw_kind_not_inferred_from_invalid_json": True,
                    }
                )
                continue
            if not isinstance(value, dict):
                continue
            after = trigger is not None and index > trigger
            if value.get("kind") == "action" and after:
                raw_action_indices.append(index)
            if event["error"] != "schema.invalid_submission":
                continue
            try:
                {"action": Action, "update": Update, "final": Final}[value["kind"]].model_validate(
                    value
                )
                errors = []
            except ValidationError as exc:
                errors = [{"location": list(e["loc"]), "type": e["type"]} for e in exc.errors()]
            except KeyError:
                errors = [{"location": ["kind"], "type": "unknown_kind"}]
            row = {
                "submission": index,
                "after_first_target_rejection": after,
                "error": event["error"],
                "classification": "schema_invalid",
                "raw_path": raw_path.relative_to(root).as_posix(),
                "raw_sha256": event["raw_sha256"],
                "raw_kind": value.get("kind"),
                "operation": value.get("operation"),
                "inputs": value.get("inputs"),
                "reason_characters": len(value.get("reason", "")),
                "validation_errors": errors,
                "executed": False,
                "claim_created": False,
                "raw_response_rewritten": False,
                "action_core_inspectable": False,
                "unexecuted_source_expression": None,
                "alignment_probe_matches": [],
            }
            op, inputs = value.get("operation"), value.get("inputs")
            claims = {c["id"]: c for c in request["state"]["claims"]}
            constants = set(request["protocol"]["constants"])
            sources = {f["id"] for f in request["context"]["numeric_catalog"]}
            core_valid = (
                value.get("kind") == "action"
                and op in TOOLS
                and isinstance(inputs, list)
                and all(isinstance(ref, str) for ref in inputs)
                and value.get("parameters") == {}
                and value.get("state_id") == request["state"]["id"]
                and request["state"]["pending_observation"] is None
                and request["state"]["remaining_actions"] > 0
            )
            tree = None
            if core_valid:
                arity = 1 if op in {"read", "absolute"} else 2
                core_valid = (
                    len(inputs) == arity
                    if op in {"read", "absolute", "add", "subtract", "multiply", "divide"}
                    else 2 <= len(inputs) <= 8
                )
            if core_valid and op == "read":
                core_valid = inputs[0] in sources
                tree = inputs[0] if core_valid else None
            elif core_valid:
                core_valid = all(ref in constants or ref in claims for ref in inputs)
                if core_valid:
                    tree = {
                        "op": op,
                        "args": [
                            ref if ref in constants else claims[ref]["expression"] for ref in inputs
                        ],
                    }
            if core_valid:
                row["action_core_inspectable"] = True
                row["unexecuted_source_expression"] = tree
                row["unexecuted_exact_value"] = str(independent_value(tree, task["facts"]))
                row["alignment_probe_matches"] = [
                    name
                    for name, probe in probes.items()
                    if equivalent(tree, probe, task["facts"], task["relations"])
                ]
                if after and row["alignment_probe_matches"]:
                    candidates.append(row)
            invalid.append(row)
        rows.append(
            {
                "label": label,
                "first_target_rejection": trigger,
                "frozen_first_parsed_post_trigger_action_proposal": audit["recovery_trace"][
                    "first_post_trigger_action_proposal"
                ],
                "posthoc_first_valid_json_action_shaped_response": raw_action_indices[0]
                if raw_action_indices
                else None,
                "posthoc_valid_json_action_shaped_indices": raw_action_indices,
                "schema_and_json_failures": invalid,
                "unexecuted_aligned_action_core_candidates": candidates,
                "complete_recovery_unchanged": audit["complete_valid"],
            }
        )
    store = DurableStore(output / "posthoc")
    report = record(
        "e1_raw_proposal_posthoc",
        provider_calls=0,
        online_manifest_id=online["id"],
        online_source_and_artifacts_unchanged=True,
        measurement_limitation=(
            "Frozen Action proposal metrics use schema-parsed model_submission; "
            "schema-invalid raw proposals need a separate inspection."
        ),
        candidate_semantics=(
            "Original operation and ordered accepted-Claim/constant inputs can describe "
            "an aligned expression, but the original response was rejected; this is not "
            "an execution, repaired response, Claim, recovery, or counterfactual completion."
        ),
        script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        sessions=rows,
    )
    store.json("raw_proposal_inspection.json", report)
    seal_directory(store, kind="e1_raw_proposal_posthoc_manifest", report_id=report["id"])
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.cwd())
    report = inspect(parser.parse_args().root)
    print(
        json.dumps(
            {
                r["label"]: {
                    "first_raw_action": r["posthoc_first_valid_json_action_shaped_response"],
                    "first_parsed_action": r["frozen_first_parsed_post_trigger_action_proposal"],
                    "unexecuted_aligned_core_candidates": [
                        c["submission"] for c in r["unexecuted_aligned_action_core_candidates"]
                    ],
                }
                for r in report["sessions"]
            },
            ensure_ascii=False,
            indent=2,
        )
    )
