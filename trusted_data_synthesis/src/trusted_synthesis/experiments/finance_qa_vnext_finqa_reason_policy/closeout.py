"""Read-only raw replay and complete cost accounting; no model callback here."""

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

from trusted_synthesis.domains.finance.qa_vnext.protocol import record, require
from trusted_synthesis.domains.finance.qa_vnext.runtime import DurableStore
from trusted_synthesis.experiments.finance_qa_vnext_finqa_difficulty.panel import Panel
from trusted_synthesis.experiments.finance_qa_vnext_harness_responsibility.audit import manifest
from trusted_synthesis.experiments.finance_qa_vnext_model_execution.plan import (
    seal_directory,
    verify_source_snapshot,
)

from .audit import read, verify_session
from .metrics import aggregate
from .stage import LABELS, OUTPUT, history_guard


def collect(
    panel, registrations, sessions_root, expected_rows, annotations, *, model_required=True
):
    rows, reviews, errors, kinds, operations = [], [], Counter(), Counter(), Counter()
    sizes = {"request_body_bytes": 0, "response_body_bytes": 0}
    require(
        set(annotations) == {r["label"] for r in registrations}, "closeout.every_session_reviewed"
    )
    for registration, expected in zip(registrations, expected_rows, strict=True):
        directory = sessions_root / registration["label"]
        manifest(directory)
        audit = verify_session(panel, registration, directory, model_required=model_required)
        require(audit == read(directory / "audit.json") == expected, "closeout.raw_reaudit")
        review = annotations[registration["label"]]
        require(
            all(
                k in review
                for k in (
                    "first_error",
                    "executed_adjustment",
                    "acceptance_and_consumption",
                    "terminal_point",
                    "evidence_submissions",
                    "interpretation_and_limits",
                    "reason_contract_layers",
                )
            ),
            "closeout.review_fields",
        )
        require(
            set(review["evidence_submissions"]) <= set(range(1, audit["submissions"] + 1)),
            "closeout.review_indices",
        )
        for path in sorted((directory / "runtime/turns").glob("*_transition.json")):
            event = read(path)
            model = event["model_submission"] or {}
            if event["admitted"]:
                kinds[model["kind"]] += 1
                if model["kind"] == "action":
                    operations[model["operation"]] += 1
            else:
                errors[event["error"]] += 1
        for field, pattern in (
            ("request_body_bytes", "*_http_request.body"),
            ("response_body_bytes", "*_http_response.body"),
        ):
            sizes[field] += sum(
                p.stat().st_size for p in (directory / "transport/attempts").glob(pattern)
            )
        rows.append(audit)
        reviews.append(
            {
                "label": registration["label"],
                "audit_id": audit["id"],
                "review": review,
                "recovery_trace": audit["recovery_trace"],
                "action_layers": audit["action_layers"],
            }
        )
    total = aggregate(rows)
    require(
        total["submissions"] == sum(kinds.values()) + sum(errors.values()),
        "closeout.submission_ledger",
    )
    require(
        total["observations"]["total_observations"] == kinds["action"],
        "closeout.observation_ledger",
    )
    require(
        total["observations"]["resolved_accept"] + total["observations"]["resolved_reject"]
        == kinds["update"],
        "closeout.update_ledger",
    )
    require(
        total["action_layers"]["actual_executions"] == kinds["action"],
        "closeout.layer_execution_ledger",
    )
    require(
        total["action_layers"]["accepted_observations"] == total["observations"]["resolved_accept"],
        "closeout.layer_acceptance_ledger",
    )
    usage = total["usage"]
    if all(
        usage[k]["total"] is not None
        for k in ("prompt_tokens", "completion_tokens", "total_tokens")
    ):
        require(
            usage["prompt_tokens"]["total"] + usage["completion_tokens"]["total"]
            == usage["total_tokens"]["total"],
            "closeout.token_sum",
        )
    return {
        "total": total,
        "admitted_kinds": dict(kinds),
        "operation_counts": dict(operations),
        "rejection_counts": dict(errors),
        "http_bytes": sizes,
        "trajectory_reviews": reviews,
        "by_success_status": {
            key: aggregate([r for r in rows if r["complete_valid"] == complete])
            for key, complete in (("complete", True), ("not_complete", False))
        },
    }


def closeout(root, reviews):
    output = root / OUTPUT
    prep_seal, online_seal = manifest(output / "preparation"), manifest(output / "online")
    frozen = read(output / "preparation/implementation.json")
    verify_source_snapshot(root, frozen)
    guard = history_guard(root)
    summary = read(output / "online/summary.json")
    registrations = read(output / "preparation/registrations.json")
    require([r["label"] for r in registrations] == list(LABELS), "closeout.fixed_population")
    collected = collect(
        Panel(root), registrations, output / "online/sessions", summary["sessions"], read(reviews)
    )
    require(collected["total"] == summary["total"], "closeout.total_recompute")
    require(collected["total"]["provider_attempts"] <= 256, "closeout.attempt_cap")
    for h in ("E", "F"):
        for policy in ("C", "P"):
            rows = [
                r
                for r in summary["sessions"]
                if r["condition"] == h and r["expression_condition"] == policy
            ]
            require(
                len(rows) == 2 and aggregate(rows) == summary["by_cell"][h + "_" + policy],
                "closeout.cell_recompute",
            )
    for policy in ("C", "P"):
        rows = [r for r in summary["sessions"] if r["expression_condition"] == policy]
        require(
            len(rows) == 4 and aggregate(rows) == summary["by_policy"][policy],
            "closeout.policy_recompute",
        )
    store = DurableStore(output / "closeout")
    store.write("posthoc_review_input.json", reviews.read_bytes())
    store.json(
        "source_integrity.json",
        {
            "online_source_commit": frozen["source_commit"],
            "source_member_hashes_and_set_match": True,
            "preparation_manifest_id": prep_seal["id"],
            "online_manifest_id": online_seal["id"],
            "all_eight_raw_replays_and_seals_reverified": True,
            "history_guard": guard,
            "posthoc_review_sha256": hashlib.sha256(reviews.read_bytes()).hexdigest(),
            "provider_calls": 0,
        },
    )
    report = record(
        "e1_reason_policy_closeout",
        registered_sessions=8,
        by_cell=summary["by_cell"],
        by_policy=summary["by_policy"],
        all_registered_sessions_executed_once=True,
        provider_attempts_without_model_submission=collected["total"]["provider_attempts"]
        - collected["total"]["submissions"],
        unused_attempts=256 - collected["total"]["provider_attempts"],
        expression_policy_differs_from_initial_request=True,
        fixed_R_feedback_not_claimed_effective=True,
        limitations=[
            "One inspected development task; two fresh sessions per information/feedback cell.",
            "No forced error, resampling, historical-control substitution, or stopping on "
            "success beyond each original session.",
            "Recovery NOT_APPLICABLE without target rejection; direct success stays in the "
            "full denominator.",
            "Conditional trigger subgroups are descriptive, not an independently randomized "
            "recovery cohort.",
            "Aligned derivation or public reason alone is not recovery; explicit acceptance "
            "and actual Final ancestry matter.",
            "Small finite witnesses do not establish stable success probability, general "
            "financial ability, or training benefit.",
            "E/F are information packages; the same model name does not prove an immutable "
            "Provider snapshot.",
            "No J2 change, unit gate, Claim deletion, tokenizer export, Student, or VTDO update.",
            "Long reasons have no intrinsic correctness or reward; only actual accepted "
            "dependencies count.",
            "C/P changes the initial expression contract, not just recovery from identical "
            "error states.",
        ],
        provider_calls_during_closeout=0,
        **collected,
    )
    store.json("report.json", report)
    seal_directory(store, kind="e1_reason_policy_closeout_manifest", report_id=report["id"])
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--reviews", type=Path, required=True)
    args = parser.parse_args()
    result = closeout(args.root, args.reviews)
    print(json.dumps({"id": result["id"], "total": result["total"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
