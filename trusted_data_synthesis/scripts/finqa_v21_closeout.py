"""Post-batch reporting only; preserve every byte of the online source snapshot.

The frozen closeout helper called integer stat.st_size as a function. This
standalone derivative fixes that byte-reporting typo, with no Provider calls,
runtime changes, response rewrites, or modified outcome labels.
"""

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

from trusted_synthesis.domains.finance.qa_vnext.protocol import record, require
from trusted_synthesis.domains.finance.qa_vnext.runtime import DurableStore
from trusted_synthesis.experiments.finance_qa_vnext_finqa_difficulty.panel import Panel
from trusted_synthesis.experiments.finance_qa_vnext_finqa_reference_diagnostic.audit import (
    read,
    verify_session,
)
from trusted_synthesis.experiments.finance_qa_vnext_finqa_reference_diagnostic.metrics import (
    FOCUS,
    aggregate_observations,
)
from trusted_synthesis.experiments.finance_qa_vnext_finqa_reference_diagnostic.stage import (
    LABELS,
    OUTPUT,
    history_guard,
)
from trusted_synthesis.experiments.finance_qa_vnext_harness_responsibility.audit import manifest
from trusted_synthesis.experiments.finance_qa_vnext_model_execution.plan import (
    seal_directory,
    verify_source_snapshot,
)


def closeout(root, reviews):
    output = root / OUTPUT
    prep_seal = manifest(output / "preparation")
    online_seal = manifest(output / "online")
    frozen = read(output / "preparation/implementation.json")
    verify_source_snapshot(root, frozen)
    guard = history_guard(root)
    panel = Panel(root)
    summary = read(output / "online/summary.json")
    registrations = read(output / "preparation/registrations.json")
    annotations = read(reviews)
    require(set(annotations) == set(LABELS), "closeout.every_session_reviewed")
    rows, errors, accepted, operations = [], Counter(), Counter(), Counter()
    sizes = {"request_body_bytes": 0, "response_body_bytes": 0}
    reference_forms = Counter()
    response_models = Counter()
    for registration, expected in zip(registrations, summary["sessions"], strict=True):
        directory = output / "online/sessions" / registration["label"]
        manifest(directory)
        audit = verify_session(panel, registration, directory)
        require(audit == read(directory / "audit.json") == expected, "closeout.raw_reaudit")
        review = annotations[registration["label"]]
        require(
            review["inspection_status"] == audit["financial_trace"]["inspection_status"],
            "closeout.reached_annotation",
        )
        if registration["task_key"] in FOCUS:
            require(
                all(
                    k in review
                    for k in (
                        "concrete_error",
                        "evidence_submissions",
                        "recovery",
                        "terminal_point",
                        "review",
                    )
                ),
                "closeout.focus_review_fields",
            )
            allowed = set(range(1, audit["submissions"] + 1))
            require(set(review["evidence_submissions"]) <= allowed, "closeout.review_turn_indices")
        response_models.update(audit["observed_models"])
        for path in sorted((directory / "runtime/turns").glob("*_transition.json")):
            event = read(path)
            model = event["model_submission"] or {}
            if event["admitted"]:
                accepted[model["kind"]] += 1
                if model["kind"] == "action":
                    operations[model["operation"]] += 1
            else:
                errors[event["error"]] += 1
                if event["error"] == "lifecycle.observation_binding":
                    reference = model.get("observation", "")
                    reference_forms[
                        "wrong_observation_id"
                        if reference.startswith("finance_qa_vnext_observation:")
                        else "not_an_observation_id"
                    ] += 1
        for field, pattern in (
            ("request_body_bytes", "*_http_request.body"),
            ("response_body_bytes", "*_http_response.body"),
        ):
            sizes[field] += sum(
                p.stat().st_size for p in (directory / "transport/attempts").glob(pattern)
            )
        rows.append(
            {
                "label": registration["label"],
                "audit_id": audit["id"],
                "review": review,
                "observation_diagnostics": audit["observation_diagnostics"],
                "financial_trace": audit["financial_trace"],
            }
        )
    submissions = sum(r["submissions"] for r in summary["sessions"])
    attempts = sum(r["provider_attempts"] for r in summary["sessions"])
    require(
        submissions == sum(accepted.values()) + sum(errors.values()), "closeout.submission_ledger"
    )
    require(attempts <= 768 and len(rows) == 24, "closeout.fixed_population")
    observations = aggregate_observations(
        [event for r in rows for event in r["observation_diagnostics"]["events"]]
    )
    require(observations["total_observations"] == accepted["action"], "closeout.observation_ledger")
    require(
        observations["reference_rejections"] == errors["lifecycle.observation_binding"],
        "closeout.reference_ledger",
    )
    require(
        observations["resolved_accept"] + observations["resolved_reject"] == accepted["update"],
        "closeout.update_ledger",
    )
    usage = {
        field: {
            "total": sum(r["usage"][field]["total"] for r in summary["sessions"])
            if all(r["usage"][field]["total"] is not None for r in summary["sessions"])
            else None,
            "observed_subtotal": sum(
                r["usage"][field]["observed_subtotal"] for r in summary["sessions"]
            ),
            "unknown_attempts": sum(
                r["usage"][field]["unknown_attempts"] for r in summary["sessions"]
            ),
        }
        for field in summary["sessions"][0]["usage"]
    }
    if all(
        usage[k]["total"] is not None
        for k in ("prompt_tokens", "completion_tokens", "total_tokens")
    ):
        require(
            usage["prompt_tokens"]["total"] + usage["completion_tokens"]["total"]
            == usage["total_tokens"]["total"],
            "closeout.token_sum",
        )
    store = DurableStore(output / "closeout")
    store.json("trajectory_review.json", rows)
    store.write("posthoc_review_input.json", reviews.read_bytes())
    store.json(
        "source_integrity.json",
        {
            "online_source_commit": frozen["source_commit"],
            "all_snapshot_member_hashes_and_set_match": True,
            "preparation_manifest_id": prep_seal["id"],
            "online_manifest_id": online_seal["id"],
            "all_24_session_seals_reverified": True,
            "all_24_v21_raw_replays_match": True,
            "history_guard": guard,
            "provider_calls": 0,
            "postbatch_reporter": {
                "path": "trusted_data_synthesis/scripts/finqa_v21_closeout.py",
                "sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                "reason": "frozen reporting-only helper invoked integer st_size",
                "only_computational_fix": "stat.st_size() -> stat.st_size",
                "online_source_modified": False,
            },
            "posthoc_review_sha256": hashlib.sha256(reviews.read_bytes()).hexdigest(),
        },
    )
    report = record(
        "finqa_v21_closeout",
        registered_sessions=24,
        by_condition=summary["by_condition"],
        all_sessions_executed_once=True,
        attempts=attempts,
        submissions=submissions,
        provider_attempts_without_model_submission=attempts - submissions,
        unused_attempts=768 - attempts,
        admitted_kinds=dict(accepted),
        operation_counts=dict(operations),
        rejection_counts=dict(errors),
        observation_reference_forms=dict(reference_forms),
        observations=observations,
        usage=usage,
        http_bytes=sizes,
        observed_models=dict(response_models),
        focus_reviews={r["label"]: r["review"] for r in rows if r["label"].split("_")[0] in FOCUS},
        limitations=[
            "Fixed inspected development panel, one fresh sample per task/information condition.",
            "Before/after versus old v2 is descriptive, not exact causal identification.",
            "E/F are information packages, not a pure retrieval intervention.",
            "Observation events are clustered within sessions, not independent task samples.",
            "Intermediate expressions are not automatically wrong Final answers.",
            "Missing usage remains unknown; failed attempts retain their observed costs.",
            "Finite symbolic answer certification is not a complete public behavioral quotient.",
            "No new tokenizer export, Student, VTDO, weights, or historical outcome replacement.",
        ],
        provider_calls_during_closeout=0,
    )
    store.json("report.json", report)
    seal_directory(store, kind="finqa_v21_closeout_manifest", report_id=report["id"])
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--reviews", type=Path, required=True)
    args = parser.parse_args()
    result = closeout(args.root, args.reviews)
    print(
        json.dumps(
            {k: result[k] for k in ("id", "attempts", "submissions", "observations")},
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
