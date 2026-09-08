"""One fixed collection followed by original materialization; no training or resampling."""

import argparse
import hashlib
import json
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from trusted_synthesis.domains.finance.qa_vnext.protocol import record, require
from trusted_synthesis.domains.finance.qa_vnext.runtime import DurableStore
from trusted_synthesis.experiments.finance_qa_vnext_finqa_binding_view.runtime import (
    ReadableBindingRuntime,
)
from trusted_synthesis.experiments.finance_qa_vnext_finqa_difficulty.panel import Panel
from trusted_synthesis.experiments.finance_qa_vnext_finqa_quotient.measurement import package_index
from trusted_synthesis.experiments.finance_qa_vnext_finqa_quotient.stage import zero_execution
from trusted_synthesis.experiments.finance_qa_vnext_harness_responsibility.audit import (
    manifest,
    no_plan,
)
from trusted_synthesis.experiments.finance_qa_vnext_model_execution.plan import (
    seal_directory,
    source_snapshot,
    verify_source_snapshot,
)
from trusted_synthesis.experiments.finance_qa_vnext_model_execution.representation import (
    encode_original_candidate,
)
from trusted_synthesis.experiments.finance_qa_vnext_model_execution.runner import _credential
from trusted_synthesis.experiments.finance_qa_vnext_model_execution.transport import (
    OnlineModelCallback,
    render_http_request,
)
from trusted_synthesis.experiments.finance_qa_vnext_task_panel.guards import (
    execution_guard,
    guard_report,
)
from trusted_synthesis.experiments.qa_reasoning_share_training_preflight import (
    tokenization as assets,
)

from .audit import verify_session
from .distribution import measure
from .judgments import template
from .materialize import candidate, load_session
from .metrics import aggregate
from .plan import (
    DOCUMENT,
    LABELS,
    OUTPUT,
    PARENT,
    QUOTIENT_PARENT,
    TEST,
    configuration,
    history_guard,
    registrations,
    rules,
)
from .projection import compare, project
from .source import read
from .support import support_graph, witnesses


def prepare(root):
    output = root / OUTPUT
    require(not output.exists(), "stage.no_existing_collection")
    implementation = source_snapshot(root)
    panel = Panel(root)
    old_bindings = {r["task_key"]: r for r in read(root / PARENT / "preparation/bindings.json")}
    bound = [old_bindings[key] for key in ("J1", "J2")]
    for binding in bound:
        task = panel.tasks[binding["task_key"]]
        require(
            task["target"] == binding["independently_reviewed_target"]
            and task["unit"] == binding["unit"]
            and [task["facts"][ref] for ref in task["selected"]] == binding["selected_facts"]
            and {k: task["entry"][k] for k in ("table", "pre_text", "post_text")}
            == binding["original_source"],
            "stage.existing_signed_task_bindings",
        )
    store = DurableStore(output / "preparation")
    store.json("implementation.json", implementation)
    store.json("history_guard.json", history_guard(root))
    store.json("bindings.json", bound)
    store.json("rules.json", rules())
    store.write("design_at_freeze.md", (root / DOCUMENT).read_bytes())
    store.json("registrations.json", registrations())
    store.json("configurations.json", {s: configuration(s).as_record() for s in ("N", "D")})
    for name in ("tokenizer_binding.json", "representation_policy.json"):
        store.write(name, (root / QUOTIENT_PARENT / "freeze" / name).read_bytes())
    check = subprocess.run(
        [
            str(root / "trusted_data_synthesis/.venv/bin/python"),
            "-m",
            "pytest",
            "-q",
            "--tb=short",
            TEST,
        ],
        cwd=root,
        capture_output=True,
        check=False,
    )
    store.write("tests_stdout.txt", check.stdout)
    store.write("tests_stderr.txt", check.stderr)
    store.json(
        "tests.json",
        {
            "exit_code": check.returncode,
            "test_sha256": hashlib.sha256((root / TEST).read_bytes()).hexdigest(),
            "old_tests_rerun": False,
            "provider_calls": 0,
        },
    )
    require(check.returncode == 0, "stage.new_controls_failed")
    for r in registrations():
        request = ReadableBindingRuntime(
            panel, r["task_key"], "E", r["id"], view_condition="V1"
        ).request()
        no_plan(request)
        store.json("initial_requests/" + r["label"] + ".json", request)
        rendered = render_http_request(
            request, configuration(r["exploration_stratum"]), session_id=r["id"], attempt_index=0
        )
        store.write("initial_http/" + r["label"] + ".body", rendered["body_json"].encode())
    seal_directory(store, kind="support_exploration_preparation_manifest", rule_id=rules()["id"])
    return panel


def run_one(panel, registration, output, config, api_key, *, sender=None):
    child = DurableStore(output / registration["label"])
    child.json("registration.json", registration)
    callback = OnlineModelCallback(
        config,
        session_id=registration["id"],
        evidence_directory=child.root / "transport",
        api_key=api_key,
        sender=sender,
    )
    runtime = ReadableBindingRuntime(
        panel,
        registration["task_key"],
        "E",
        registration["id"],
        callback,
        child.root / "runtime",
        view_condition="V1",
    )
    try:
        runtime.run()
    finally:
        callback.finalize()
    audit = verify_session(panel, registration, child.root, model_required=sender is None)
    child.json("audit.json", audit)
    child.json("support_witnesses.json", witnesses(audit))
    lines = [
        f"# {registration['label']}",
        "",
        f"{audit['status']}; complete_valid={audit['complete_valid']}",
        "",
    ]
    for e in runtime.events:
        lines.append(
            f"{e['submission_count']}. admitted={e['admitted']} error={e['error']} "
            + json.dumps(e["model_submission"], ensure_ascii=False)
        )
    child.write("review.md", "\n\n".join(lines).encode())
    seal_directory(
        child,
        kind="support_exploration_session_manifest",
        audit_id=audit["id"],
        registration_id=registration["id"],
    )
    return audit


def collect(root):
    panel = prepare(root)
    output = root / OUTPUT
    frozen = read(output / "preparation/implementation.json")
    store = DurableStore(output / "online")
    rows = registrations()
    store.json(
        "launch.json",
        record(
            "support_exploration_launch",
            registrations=rows,
            attempt_cap=384,
            maximum_reserved_tokens=41287680,
        ),
    )
    api_key = _credential(root / "trusted_data_synthesis/.env")
    results = {}
    with execution_guard(online=True) as counts:
        with ThreadPoolExecutor(max_workers=12) as pool:
            futures = {
                pool.submit(
                    run_one,
                    panel,
                    r,
                    store.root / "sessions",
                    configuration(r["exploration_stratum"]),
                    api_key,
                ): r
                for r in rows
            }
            for future in as_completed(futures):
                r = futures[future]
                try:
                    result = future.result()
                except Exception as error:
                    result = record(
                        "support_collection_unknown",
                        **{
                            k: r[k]
                            for k in (
                                "label",
                                "task_key",
                                "exploration_stratum",
                                "condition",
                                "view_condition",
                                "replicate",
                            )
                        },
                        complete_valid=False,
                        status="unknown_integrity_or_host_failure",
                        error_type=type(error).__name__,
                        denominator=1,
                    )
                    store.json("failures/" + r["label"] + ".json", result)
                results[r["label"]] = result
                print(r["label"], result["status"], result.get("submissions"), flush=True)
        store.json(
            "execution_guards.json", guard_report(counts, phase="fixed_twelve_session_collection")
        )
    ordered = [results[label] for label in LABELS]
    total = aggregate(ordered)
    require(
        total["provider_attempts"] is None or total["provider_attempts"] <= 384, "stage.global_cap"
    )
    summary = record(
        "support_exploration_online_summary",
        sessions=ordered,
        total=total,
        registered=12,
        by_task_stratum={
            task + "_" + s: aggregate(
                [r for r in ordered if r["task_key"] == task and r["exploration_stratum"] == s]
            )
            for task in ("J1", "J2")
            for s in ("N", "D")
        },
        original_source_mixture={"N": "1/2", "D": "1/2"},
        new_task_weights={"J1": "1/2", "J2": "1/2"},
        known_integrity_failure=any(
            "recovery_trace" not in r or r["condition_flags"] for r in ordered
        ),
        resampling=0,
        old_samples_used=0,
        student_forward=0,
        vtdo_updates=0,
    )
    store.json("summary.json", summary)
    templates = {}
    for r in rows:
        audit = results[r["label"]]
        if audit["complete_valid"]:
            session = load_session(store.root / "sessions" / r["label"], r, audit)
            templates[r["label"]] = template(session)
    store.json("review_template.json", templates)
    verify_source_snapshot(root, frozen)
    history_guard(root)
    seal_directory(store, kind="support_exploration_online_manifest", summary_id=summary["id"])
    return summary


def closeout(root, reviews_path):
    output = root / OUTPUT
    verify_source_snapshot(root, read(output / "preparation/implementation.json"))
    history_guard(root)
    with zero_execution() as counts:
        preparation, online = manifest(output / "preparation"), manifest(output / "online")
        rows = read(output / "preparation/registrations.json")
        summary = read(output / "online/summary.json")
        audits = {r["label"]: r for r in summary["sessions"]}
        reviews = read(reviews_path)
        require(
            set(reviews) == {k for k, a in audits.items() if a["complete_valid"]},
            "closeout.every_valid_review",
        )
        store = DurableStore(output / "closeout")
        store.write("posthoc_reviews.json", reviews_path.read_bytes())
        sessions, projections, candidates, route_witnesses = {}, {}, {}, []
        for r in rows:
            audit = audits[r["label"]]
            if "recovery_trace" in audit:
                route_witnesses.append(witnesses(audit))
            if not audit["complete_valid"]:
                continue
            label = r["label"]
            session = load_session(output / "online/sessions" / label, r, audit)
            sessions[label] = session
            p = project(session, reviews[label])
            support = support_graph(session)
            if p.get("support_graph"):
                require(
                    compare(p["support_graph"], support)["relation"] == "EQUIVALENT",
                    "closeout.two_actual_ancestry_builders",
                )
            p = record(
                "support_exploration_projection",
                **{
                    k: v for k, v in p.items() if k not in {"id", "schema_version", "support_graph"}
                },
                support_graph=support,
                public_mapping_unknown_does_not_erase_actual_support=True,
            )
            projections[label] = p
            store.json("projections/" + label + ".json", p)
            candidates[label] = []
            for turn in session["turns"]:
                index = turn["binding"]["index"]
                store.json(f"interactions/{label}/{index:03d}.json", turn["binding"])
                if turn["event"]["admitted"]:
                    row = candidate(session, turn)
                    candidates[label].append(row)
                    store.json(f"candidates/{label}/{index:03d}.json", row)
        measurement = measure(rows, summary["sessions"], projections)
        store.json("measurement.json", measurement)
        store.json("support_witnesses.json", route_witnesses)
        binding = read(output / "preparation/tokenizer_binding.json")
        old_policy = read(output / "preparation/representation_policy.json")
        require(old_policy["maximum_sequence_length"] == 32768, "tokens.fixed_cap")
        policy = record(
            "support_original_representation_policy",
            parent_policy_id=old_policy["id"],
            tokenizer_binding_id=binding["id"],
            maximum_sequence_length=32768,
            exact_N_D_inputs=True,
            target_only_mask=assets.MASK_POLICY,
            no_truncation=True,
            class_internal_prompt_composition_preserved=True,
            training_weights=None,
        )
        store.json("representation_policy.json", policy)
        tokenizer = assets.load_tokenizer(binding) if sessions else None
        packages, representations = [], []
        for label, session in sessions.items():
            tokens = []
            for row in candidates[label]:
                token = encode_original_candidate(
                    row, binding, tokenizer, maximum_sequence_length=32768
                )
                token = record(
                    "support_token_representation",
                    **{k: v for k, v in token.items() if k not in {"id", "schema_version"}},
                    representation_policy_id=policy["id"],
                    exploration_stratum=row["exploration_stratum"],
                )
                tokens.append(token)
                representations.append(token)
                store.json(f"tokens/{label}/{row['submission'] - 1:03d}.json", token)
            assignment = next(a for a in measurement["assignments"] if a["label"] == label)
            package = package_index(session, candidates[label], tokens, assignment)
            package = record(
                "support_original_package",
                **{
                    k: v
                    for k, v in package.items()
                    if k not in {"id", "schema_version", "task_key"}
                },
                task_key=session["row"]["task_key"],
                exploration_stratum=session["row"]["exploration_stratum"],
            )
            store.json("packages/" + label + ".json", package)
            packages.append(package)
        store.json(
            "execution_guards.json",
            guard_report(counts, phase="new_trajectory_materialization_only"),
        )
        report = record(
            "support_exploration_closeout",
            preparation_id=preparation["id"],
            online_id=online["id"],
            online_summary_id=summary["id"],
            measurement_id=measurement["id"],
            registered=12,
            complete_valid=len(sessions),
            original_all_outcomes_retained=True,
            materialized_units=sum(len(r) for r in candidates.values()),
            packages=packages,
            fit_rows=sum(r["consumable_token_representation"] for r in representations),
            not_fit_rows=sum(not r["consumable_token_representation"] for r in representations),
            maximum_sequence_length=max(
                (r["sequence_length"] for r in representations), default=None
            ),
            target_token_count=sum(r["target_token_count"] for r in representations),
            tokenizer_loaded=bool(sessions),
            new_provider_calls=0,
            student_loads=0,
            gpu_jobs=0,
            vtdo_updates=0,
            collection_usage=summary["total"],
            by_task_stratum=summary["by_task_stratum"],
            validity_not_changed_by_projection_or_tokens=True,
            novelty=None,
            contribution=None,
            training_utility=None,
        )
        store.json("report.json", report)
        seal_directory(store, kind="support_exploration_closeout_manifest", report_id=report["id"])
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["collect", "closeout", "verify"])
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--reviews", type=Path)
    args = parser.parse_args()
    if args.mode == "collect":
        result = collect(args.root)
    elif args.mode == "closeout":
        require(args.reviews is not None, "closeout.review_input")
        result = closeout(args.root, args.reviews)
    else:
        result = {
            p: manifest(args.root / OUTPUT / p)["id"] for p in ("preparation", "online", "closeout")
        }
    print(result.get("id", result), flush=True)


if __name__ == "__main__":
    main()
