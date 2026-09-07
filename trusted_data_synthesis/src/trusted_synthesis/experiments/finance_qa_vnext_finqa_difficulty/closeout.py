"""Zero-Provider post-batch review; never changes frozen online artifacts or labels."""

from __future__ import annotations

import hashlib
import json
import subprocess
from collections import Counter
from pathlib import Path

from trusted_synthesis.domains.finance.qa_vnext.protocol import record, require
from trusted_synthesis.domains.finance.qa_vnext.runtime import DurableStore
from trusted_synthesis.experiments.finance_qa_vnext_harness_responsibility.audit import manifest
from trusted_synthesis.experiments.finance_qa_vnext_model_execution.plan import seal_directory

from .audit import read, verify_session
from .controls import witness
from .panel import Panel
from .reference_revision import VERSION, ReferenceExplicitRuntime
from .semantics import equivalent
from .stage import OUTPUT, history_guard

REVIEW = {
    "C1_E_01": (
        "Both needed source values eventually accepted, no subtraction before "
        "submission cap. Reference-interface attrition, not evidence of inability "
        "to subtract."
    ),
    "C2_E_01": (
        "Correct raw ratio executed but pending acceptance at cap. No percentage "
        "result established. Reference-interface attrition."
    ),
    "E1_E_01": (
        "Reads correct 15.3 million and 139549 table-thousand values; executes "
        "their unscaled division, despite reason identifying thousands. Scale "
        "handling problem plus reference attrition."
    ),
    "E1_F_01": (
        "Executes 15.3/139549*100 without thousand/million normalization. Sixteen "
        "wrong-target Final submissions. Repeated operations do not supply the "
        "missing conversion."
    ),
    "E3_E_01": (
        "Only two reads executed; second read remains pending. Cannot infer "
        "method ability from this termination."
    ),
    "E3_F_01": (
        "0.997 is a legitimate million-to-billion intermediate, not automatically "
        "an error. Later executes 7*1000 and 997/7000 correctly; cap reached "
        "after ratio acceptance, before percent conversion/Final."
    ),
    "M1_E_01": (
        "Correct three-member average already executed at submission 14; eighteen "
        "subsequent malformed Update references prevent acceptance. Strong direct "
        "example of protocol failure, not failed averaging."
    ),
    "M2_E_01": (
        "Four of five maturity amounts read; fourth pending at cap. Incomplete "
        "trace, not demonstrated inability to aggregate."
    ),
    "M3_E_01": (
        "Only coal amounts read; third pending at cap. Insufficient executed "
        "evidence to assess the final method."
    ),
    "M3_F_01": (
        "Uses 2016 coal and 2016 operating total only, then percentage, although "
        "question asks 2014-2016 aggregate. Period-set/method error plus "
        "reference attrition, not an off-reference-source read."
    ),
    "J1_E_01": (
        "Initially computes pre-tax cost growth, omitting both tax benefits; six "
        "target rejections. Later reads one tax benefit but cannot complete. "
        "Financial-definition/method error plus protocol attrition."
    ),
    "J1_F_01": (
        "Reads all four right facts and computes 2010 after-tax cost as "
        "18.1+(-6.3)=11.8. Pending acceptance at cap; no demonstrated failure of "
        "final net-growth formula."
    ),
    "J2_E_01": (
        "Reads two quantities and one corresponding price, with incomplete "
        "execution at cap. Public reason proposes the right quantity-times-price "
        "structure; reason is not an executed answer."
    ),
    "J2_F_01": (
        "All four needed facts are read, but final product uses 2016 quantity 13 "
        "with 2017 price 33.32, yielding 433.16 instead of 11*33.32. "
        "Period-to-input binding error, not failure to locate all four numbers."
    ),
    "J3_E_01": (
        "Only two payment amounts read, second pending at cap; cannot infer aggregation inability."
    ),
    "J3_F_01": (
        "Initially reads source:p1n3 (year 2018) while reason expects payment "
        "22.3, then explicitly corrects to p1n2. The unused year Claim remains in "
        "the record; correct five-payment sum and Final succeed."
    ),
}


def main(root=None):
    root = Path.cwd() if root is None else root
    output = root / OUTPUT
    preparation_seal = manifest(output / "preparation")
    online_seal = manifest(output / "online")
    frozen = read(output / "preparation/implementation.json")
    for member in frozen["members"]:
        require(
            hashlib.sha256((root / member["path"]).read_bytes()).hexdigest() == member["sha256"],
            "closeout.frozen_source_member_changed",
        )
    # New, unused post-batch modules are explicitly distinguished from the launch snapshot.
    frozen_paths = {m["path"] for m in frozen["members"]}
    additions = sorted(
        p.relative_to(root).as_posix()
        for p in (root / "trusted_data_synthesis/src").rglob("*.py")
        if p.relative_to(root).as_posix() not in frozen_paths
    )
    panel = Panel(root)
    registrations = read(output / "preparation/registrations.json")
    summary = read(output / "online/summary.json")
    rows, errors, admitted, operations, observation_errors = (
        [],
        Counter(),
        Counter(),
        Counter(),
        Counter(),
    )
    for registration in registrations:
        label = registration["label"]
        directory = output / "online/sessions" / label
        manifest(directory)
        require(
            verify_session(panel, registration, directory) == read(directory / "audit.json"),
            "closeout.independent_audit_mismatch",
        )
        result = read(directory / "runtime/result.json")
        task = panel.tasks[registration["task_key"]]
        terminal_claims = [
            c["id"]
            for c in result["final_state"]["claims"]
            if equivalent(c["expression"], task["target"], task["facts"], task["relations"])
        ]
        pending = result["final_state"]["pending_observation"]
        pending_correct = bool(
            pending
            and equivalent(pending["expression"], task["target"], task["facts"], task["relations"])
        )
        per_errors, action_rows = Counter(), []
        for path in sorted((directory / "runtime/turns").glob("*_transition.json")):
            event = read(path)
            model = event["model_submission"] or {}
            if event["admitted"]:
                admitted[model["kind"]] += 1
                if event["observation"]:
                    operations[model["operation"]] += 1
                    action_rows.append(
                        {
                            "submission": event["submission_count"],
                            "operation": model["operation"],
                            "inputs": model["inputs"],
                            "reason": model["reason"],
                            "value": event["observation"]["value"],
                            "expression": event["observation"]["expression"],
                        }
                    )
            else:
                errors[event["error"]] += 1
                per_errors[event["error"]] += 1
                if event["error"] == "lifecycle.observation_binding":
                    ref = model.get("observation", "")
                    category = (
                        "wrong_observation_id"
                        if ref.startswith("finance_qa_vnext_observation:")
                        else "not_an_observation_id"
                    )
                    observation_errors[category] += 1
        rows.append(
            {
                "label": label,
                "denominator": 1,
                "complete_valid": result["terminal"],
                "actions": result["actions"],
                "submissions": result["submissions"],
                "errors": dict(per_errors),
                "correct_accepted_answer_claims": terminal_claims,
                "correct_pending_answer": pending_correct,
                "pending_observation": pending is not None,
                "executed_actions": action_rows,
                "review": REVIEW.get(
                    label,
                    (
                        "Successful original-task execution, with reference rejections retained; "
                        "no separate substantive source/method error established in review."
                    ),
                ),
                "review_is_posthoc_descriptive_not_blind_error_annotation": True,
            }
        )
    attempts = sum(r["provider_attempts"] for r in summary["sessions"])
    http_bytes = {h: {"request_body_bytes": 0, "response_body_bytes": 0} for h in ("E", "F")}
    for registration in registrations:
        transport = output / "online/sessions" / registration["label"] / "transport/attempts"
        for path in transport.glob("*_http_request.body"):
            http_bytes[registration["condition"]]["request_body_bytes"] += path.stat().st_size
        for path in transport.glob("*_http_response.body"):
            http_bytes[registration["condition"]]["response_body_bytes"] += path.stat().st_size
    require(attempts == sum(r["submissions"] for r in rows), "closeout.attempt_submission_ledger")
    require(sum(errors.values()) + sum(admitted.values()) == attempts, "closeout.transition_ledger")
    require(sum(operations.values()) == admitted["action"], "closeout.operation_ledger")
    store = DurableStore(output / "closeout")
    store.json("trajectory_review.json", rows)
    store.json(
        "source_integrity.json",
        {
            "online_source_commit": frozen["source_commit"],
            "all_online_snapshot_member_hashes_still_match": True,
            "post_batch_additional_modules_not_in_online_snapshot": additions,
            "preparation_manifest_id": preparation_seal["id"],
            "online_manifest_id": online_seal["id"],
            "all_24_session_seals_and_audits_reverified": True,
            "provider_calls": 0,
            "history_guard": history_guard(root),
        },
    )
    tests = [
        "trusted_data_synthesis/tests/test_qa_vnext_finqa_difficulty.py",
        "trusted_data_synthesis/tests/test_qa_vnext_finqa_update_reference_revision.py",
    ]
    check = subprocess.run(
        [
            str(root / "trusted_data_synthesis/.venv/bin/python"),
            "-m",
            "pytest",
            "-q",
            "--tb=short",
            *tests,
        ],
        cwd=root,
        capture_output=True,
        check=False,
    )
    store.write("tests_stdout.txt", check.stdout)
    store.write("tests_stderr.txt", check.stderr)
    require(check.returncode == 0, "closeout.offline_revision_controls")
    capacities = []
    for registration in registrations:
        runtime = ReferenceExplicitRuntime(
            panel,
            registration["task_key"],
            registration["condition"],
            "post-batch-offline:" + registration["label"],
        )
        proof = witness(runtime)
        store.json("reference_revision_witnesses/" + registration["label"] + ".json", proof)
        capacities.append(
            {
                "label": registration["label"],
                "actions": proof["actions"],
                "submissions": proof["submissions"],
                "complete": proof["complete"],
            }
        )
    store.json(
        "reference_revision.json",
        {
            "version": VERSION,
            "provider_calls": 0,
            "population_samples": 0,
            "pre_call_v2_controls": 40,
            "post_batch_v21_new_controls": 27,
            "combined_local_controls_exit_code": check.returncode,
            "only_changes": [
                "protocol version",
                "Update observation field description",
                "pending observation ID const in public schema",
                "explicit public ID-copy rule",
            ],
            "changed_raw_responses_or_old_labels": False,
            "host_filled_references": False,
            "changed_financial_semantics_or_final_feedback_or_reason_limit": False,
            "online_effectiveness": "NOT_MEASURED",
            "offline_capacities": capacities,
            "future_online_requires_separate_condition_registration": True,
        },
    )
    report = record(
        "finqa_closeout",
        online_summary_id=summary["id"],
        by_condition=summary["by_condition"],
        registered_sessions=24,
        complete_valid_sessions=sum(r["complete_valid"] for r in rows),
        provider_attempts=attempts,
        provider_attempt_cap=768,
        unused_provider_attempts=768 - attempts,
        actual_reserved_token_upper_bound=attempts * 107520,
        http_body_bytes_by_condition=http_bytes,
        total_provider_tokens=sum(
            h["usage"]["total_tokens"] for h in summary["by_condition"].values()
        ),
        error_counts=dict(errors),
        admitted_counts=dict(admitted),
        operation_counts=dict(operations),
        observation_reference_error_forms=dict(observation_errors),
        all_cost_includes_failed_and_rejected=True,
        missing_reasoning_usage="unknown",
        evidence_integrity_gate="PASS_AS_RECORDED",
        census_and_static_instantiation_gate="PASS_AS_SCOPED",
        E_F_difficulty_effect_gate="NOT_SUPPORTED_BY_THIS_INTERFACE_CONFOUNDED_SINGLE_SAMPLE_BATCH",
        interface_finding=(
            "Public v2 schema leaves observation as undescribed string; many model "
            "responses use prose instead of ID. This is a real contract-clarity "
            "defect. v2.1 efficacy is unmeasured, not assumed."
        ),
        original_batch_replaced_or_resampled=False,
        post_batch_provider_calls=0,
        analysis_source_commit=subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=root, text=True
        ).strip(),
    )
    store.json("report.json", report)
    seal_directory(store, kind="finqa_closeout_manifest", online_summary_id=summary["id"])
    print(
        json.dumps(
            {k: v for k, v in report.items() if k != "by_condition"}, ensure_ascii=False, indent=2
        )
    )


if __name__ == "__main__":
    main()
