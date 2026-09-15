"""Freeze a task-blind public-source window, then check all 180 inputs once.

compile_public accepts only original public fields and a public source document
selected before task enumeration. It cannot read a private task, reference plan,
model output, witness, or performance result. A separate post-compilation offline
admission checks retained declared support without changing any compiled view.
"""

# ruff: noqa: E501 -- preserve prospectively frozen policy and public wording

import argparse
import copy
import json
import subprocess
import sys
import time
from collections import Counter
from datetime import date, timedelta
from pathlib import Path

BASE = "trusted_data_synthesis/artifacts/qa_vnext_fixed_kernel_value"
OUTPUT = BASE + "/given_sources_value_20260915"
PARENT = BASE + "/parallel_tail_execution_20260914"
SCRIPT = "trusted_data_synthesis/scripts/fixed_kernel_source_view_compile_20260915.py"
RUNTIME_SCRIPT = "trusted_data_synthesis/scripts/fixed_kernel_source_view_runtime_20260915.py"
AUDIT_SHA = "d82b24afd0d6eedbf7aa6b58b3d32982dc2010c344a8902eb6fee1a451c2bf2c"


def modules(root):
    for relative in (
        "trusted_data_synthesis/src",
        "raw_financial_data_lake",
        "trusted_data_synthesis/scripts",
    ):
        value = str(Path(root) / relative)
        if value not in sys.path:
            sys.path.insert(0, value)
    import fixed_kernel_source_view_runtime_20260915 as new_runtime

    from trusted_synthesis.experiments.finance_qa_vnext_catalog_bridge.catalog import (
        Parent,
        safe_path,
    )
    from trusted_synthesis.experiments.finance_qa_vnext_eval_readiness import runtime
    from trusted_synthesis.experiments.finance_qa_vnext_eval_surface import (
        overlay,
    )
    from trusted_synthesis.experiments.finance_qa_vnext_eval_surface import (
        protocol as surface,
    )
    from trusted_synthesis.experiments.finance_qa_vnext_fixed_kernel_value import protocol as p

    return p, overlay, surface, Parent, safe_path, runtime, new_runtime


def rule(p):
    return p.record(
        "source_view_compiler_rule",
        version="public_all_registered_metrics_period_window.v1",
        input_authority="pre-task-enumeration public native_annual_records, original public periods only",
        period_window="record.end between min(public period.start or end) minus one day and max(public period.end), inclusive",
        metric_scope="all records in original public document, not filtered by task metric or operation",
        vintage_selection="inherited pre-task-enumeration tag priority then latest filing/accession; no new value-aware selection",
        missing_or_excess_length="retain error for fixed task; no outcome-aware pruning, drop, or replacement",
        preserved="native label, definition, unit, exact record, raw object SHA, URL and pointer",
        source_ID="source_ + first 24 hex SHA256([raw_object_id, native_pointer]); independent of amount/role",
        removed_only="old graph_ready flag and opaque fact ID; no numeric record within the public window removed",
        no_private_witness_or_reference_or_model_input_to_compiler=True,
        no_Probe_history_or_computed_values=True,
        all_methods_share_exact_same_view=True,
    )


def compile_public(public, document, p):
    periods = public["period_contract"]["periods"]
    lower = min(date.fromisoformat(row["start"] or row["end"]) for row in periods) - timedelta(
        days=1
    )
    upper = max(date.fromisoformat(row["end"]) for row in periods)
    selected = [
        row
        for row in document["native_annual_records"]
        if lower <= date.fromisoformat(row["record"]["end"]) <= upper
    ]
    sources = []
    for row in sorted(
        selected, key=lambda value: (value["concept"], value["unit"], value["native_pointer"])
    ):
        sources.append(
            {
                "source_id": "source_"
                + p.sha(p.encode([document["source_id"], row["native_pointer"]]))[:24],
                "source_kind": row["source_kind"],
                "raw_object_id": document["source_id"],
                **{
                    key: copy.deepcopy(row[key])
                    for key in (
                        "original_url",
                        "raw_sha256",
                        "native_pointer",
                        "concept",
                        "label",
                        "definition",
                        "unit",
                        "record",
                    )
                },
            }
        )
    p.require(
        sources and len({row["source_id"] for row in sources}) == len(sources),
        "source_view.nonempty_unique_mechanical_sources",
    )
    visible = {
        "question": public["question"],
        "quantity_contract": copy.deepcopy(public["quantity_contract"]),
        "period_contract": copy.deepcopy(public["period_contract"]),
        "sources": sources,
        "source_policy": (
            "Given original public records under the frozen all-registered-metrics period window. "
            "No source roles or solution route are selected. Choose, read and calculate your own support. "
            "Each source_id mechanically maps to its declared raw object and native pointer."
        ),
        "tool_contract": {
            "read_source": "source_id, optional unit; reads that supplied original numeric record with real unit conversion",
            "calculate": public["tool_contract"]["calculate"],
            "select_max": public["tool_contract"]["select_max"],
            "compare": public["tool_contract"]["compare"],
            "lookup_selected": public["tool_contract"]["lookup_selected"],
            "Final": public["tool_contract"]["Final"],
        },
    }
    return visible, {
        "minimum_record_end": lower.isoformat(),
        "maximum_record_end": upper.isoformat(),
        "source_records": len(sources),
        "all_original_public_records": len(document["native_annual_records"]),
    }


def read_member(parent, relative, p, safe_path, cache):
    key = (str(parent.directory), relative)
    if key not in cache:
        p.require(relative in parent.members, "source_view.member_declared")
        raw = safe_path(parent.directory, relative).read_bytes()
        expected = parent.members[relative]
        p.require(
            len(raw) == expected["bytes"] and p.sha(raw) == expected["sha256"],
            "source_view.bound_input_bytes",
        )
        cache[key] = json.loads(raw)
    return copy.deepcopy(cache[key])


def prepare(root):
    root = Path(root).resolve()
    p, overlay, surface, Parent, safe_path, old_runtime, new_runtime = modules(root)
    output = root / OUTPUT / "inputs"
    p.require(not output.exists(), "source_view.no_compilation_rerun")
    start = time.monotonic()
    frozen = p.read_json(root / PARENT / "preparation/execution_freeze.json")
    source_root = Path(frozen["source_root"])
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    code = []
    for filename in (SCRIPT, RUNTIME_SCRIPT):
        raw = (root / filename).read_bytes()
        p.require(
            raw == subprocess.check_output(["git", "show", head + ":" + filename], cwd=root),
            "source_view.rule_committed_before_first_input",
        )
        code.append(dict(path=filename, sha256=p.sha(raw)))
    registered = rule(p)
    p.write_once(output / "rule.json", registered)
    rows = frozen["evaluation_registry"]["dev"]
    p.require(
        len(rows) == 180
        and Counter(row["group"] for row in rows) == dict.fromkeys(overlay.GROUPS, 60),
        "source_view.original_dev180_only",
    )
    population_ref = frozen["input_files"]["population"]
    population_raw = (Path(frozen["input_root"]) / population_ref["path"]).read_bytes()
    p.require(
        p.sha(population_raw) == population_ref["sha256"], "source_view.frozen_train_population"
    )
    population = json.loads(population_raw)
    train_ids = {row["task_id"] for row in population["tasks"]}
    train_sources = {row["source_cluster"] for row in population["tasks"]}
    p.require(
        len(train_ids) == 200 and not train_ids.intersection(row["task_id"] for row in rows),
        "source_view.no_gradient_training_task_overlap",
    )
    p.require(
        not train_sources.intersection(row["source_cluster"] for row in rows),
        "source_view.no_training_source_cluster_overlap",
    )
    public = overlay.PublicOverlay(
        source_root,
        surface.OUTPUT,
        "manifest:f29dac61b36396baffd60916bf3b2bdca461a849f0e11bb2d519d54127d2c856",
    )
    science = Parent(source_root, surface.PARENT_PANEL, surface.PARENT_PANEL_MANIFEST)
    cache, snapshots, source_documents, view_rows, failures = {}, {}, {}, [], []
    for row in rows:
        task = row["task_id"]
        entry = public.tasks[task]
        messages = read_member(public.parent, entry["public_path"], p, safe_path, cache)
        p.require(
            p.sha(p.encode(messages)) == row["public_messages_sha256"],
            "source_view.original_public_SHA",
        )
        original = overlay.public_object(messages)
        descriptor = original["source_document"]
        p.require(isinstance(descriptor, dict), "source_view.one_original_source_document")
        key = descriptor["source_id"]
        if key not in source_documents:
            document = read_member(science, "panels/dev/" + descriptor["path"], p, safe_path, cache)
            p.require(
                document["id"] == descriptor["document_id"]
                and document["complete_original_snapshot"]
                == descriptor["complete_original_snapshot"],
                "source_view.original_public_document_binding",
            )
            source_documents[key] = document
            # One source-byte admission per distinct snapshot, never per model or task.
            original_sources = old_runtime.SnapshotSources(source_root, [descriptor])
            snapshots[key] = original_sources._payload(key)
        document = source_documents[key]
        try:
            visible, counts = compile_public(original, document, p)
            for item in visible["sources"]:
                p.require(
                    old_runtime._pointer(snapshots[key], item["native_pointer"]) == item["record"]
                    and item["raw_sha256"] == descriptor["complete_original_snapshot"]["sha256"],
                    "source_view.actual_original_record_bytes",
                )
            new_messages = [{"role": "user", "content": p.encode(visible).decode()}]
            view = p.record(
                "given_public_source_view",
                canonical_task_id=task,
                group=row["group"],
                source_cluster=row["source_cluster"],
                original_identity={
                    "task_id": task,
                    "family": row["group"],
                    "surface_version_id": row["surface_version_id"],
                    "public_messages_sha256": row["public_messages_sha256"],
                    "parent_manifest_id": public.parent.manifest["id"],
                },
                rule_id=registered["id"],
                public_messages=new_messages,
                public_messages_sha256=p.sha(p.encode(new_messages)),
                source_document_id=document["id"],
                source_window=counts,
                private_fields_received_by_compiler=False,
                no_prior_tool_results_or_Probe_history=True,
            )
            path = output / "views" / (task + ".json")
            p.write_once(path, view)
            view_rows.append(
                dict(
                    task_id=task,
                    group=row["group"],
                    source_cluster=row["source_cluster"],
                    surface_version_id=view["id"],
                    public_messages_sha256=view["public_messages_sha256"],
                    path=str(path.relative_to(root)),
                    **counts,
                )
            )
        except (ValueError, TypeError, KeyError) as error:
            failures.append(dict(task_id=task, stage="compile_public", error=str(error)))
    manifest = p.record(
        "source_view_manifest",
        rule_id=registered["id"],
        audit_sha256=AUDIT_SHA,
        source_code_binding=dict(commit=head, members=code),
        tasks=view_rows,
        failures=failures,
        planned_tasks=180,
        per_group_planned=60,
        compiled_tasks=len(view_rows),
        source_documents_read=len(source_documents),
        raw_snapshots_read=len(snapshots),
        source_snapshot_bytes=sum(
            document["complete_original_snapshot"]["bytes"]
            for document in source_documents.values()
        ),
        train_tasks_checked=len(train_ids),
        train_source_clusters=len(train_sources),
        development_source_clusters=len({row["source_cluster"] for row in rows}),
        task_and_source_cluster_train_overlap=0,
        confirm_task_contents_opened=0,
        compiler_has_private_bundle_capability=False,
        Student_model_calls=0,
    )
    p.write_once(output / "manifest.json", manifest)
    # All public views are immutable before acquiring any private sufficiency authority.
    from trusted_synthesis.experiments.qa_reasoning_share_training_preflight.tokenization import (
        load_tokenizer,
    )

    tokenizer = load_tokenizer(frozen["tokenizer_binding"])
    bindings = read_member(science, "panels/dev/native_bindings.json", p, safe_path, cache)
    original_catalog = read_member(science, "panels/dev/catalog.json", p, safe_path, cache)
    catalog_rows = {row["task_id"]: row for row in original_catalog["tasks"]}
    checks = []
    for row in view_rows:
        view = p.read_json(root / row["path"])
        visible = json.loads(view["public_messages"][0]["content"])
        identity = dict(
            task_id=row["task_id"],
            family=row["group"],
            surface_version_id=view["id"],
            public_messages_sha256=view["public_messages_sha256"],
            parent_manifest_id=manifest["id"],
        )
        new_runtime.public_document(
            view["public_messages"], identity, new_runtime.SourceViewSources(visible)
        )
        rendered = tokenizer.apply_chat_template(
            [
                {"role": "system", "content": new_runtime.SYSTEM + "\nRequested guidance: neutral"},
                *view["public_messages"],
            ],
            tokenize=False,
            add_generation_prompt=True,
        )
        token_count = len(
            tokenizer(rendered, add_special_tokens=False, truncation=False)["input_ids"]
        )
        original_row = catalog_rows[row["task_id"]]
        bundle = read_member(science, "panels/dev/" + original_row["path"], p, safe_path, cache)
        certificate = bundle["private"]["relation_certificate"]
        leaf_ids = set(certificate["leaf_fact_ids"])
        mapping = {
            (source["raw_object_id"], source["native_pointer"], source["raw_sha256"])
            for source in visible["sources"]
        }
        missing = sorted(
            key
            for key in leaf_ids
            if (
                bindings[key]["raw_object_id"],
                bindings[key]["pointer"],
                bindings[key]["raw_sha256"],
            )
            not in mapping
        )
        check = dict(
            task_id=row["task_id"],
            group=row["group"],
            source_records=len(visible["sources"]),
            initial_prompt_tokens=token_count,
            available_history_growth_tokens=24576 - 2048 - token_count,
            input_plus_reserved_generation_within_context=token_count + 2048 <= 24576,
            declared_support_leaf_count=len(leaf_ids),
            missing_declared_support=missing,
            original_question_and_targets_unchanged=True,
            compiler_input_unchanged_after_offline_check=True,
        )
        check["passed"] = not missing and check["input_plus_reserved_generation_within_context"]
        checks.append(check)
    passed = not failures and len(checks) == 180 and all(row["passed"] for row in checks)
    report = p.record(
        "source_view_input_admission",
        status="PASS_ALL_180_INPUTS" if passed else "BLOCKED_INPUT_CONTRACT",
        passed=passed,
        manifest_id=manifest["id"],
        rule_id=registered["id"],
        checks=checks,
        compiled_tasks=len(view_rows),
        passed_tasks=sum(row["passed"] for row in checks),
        failures=failures,
        runtime_binding=new_runtime.binding(),
        initial_prompt_tokens_min=min(
            (row["initial_prompt_tokens"] for row in checks), default=None
        ),
        initial_prompt_tokens_max=max(
            (row["initial_prompt_tokens"] for row in checks), default=None
        ),
        original_dev_private_bundles_read_only_for_postcompile_sufficiency=len(checks),
        tokenizer_constructions=1,
        initial_prompt_tokenizations=len(checks),
        original_training_packages_opened=0,
        original_runtime_sessions_scanned=0,
        confirm_tasks_opened=0,
        model_calls=0,
        raw_source_file_reads=len(snapshots),
        elapsed_seconds=time.monotonic() - start,
        finished_at=p.now(),
        failed_inputs_not_dropped_or_answer_trimmed=True,
        matrix_release_requires_complete_input_and_runtime_control_admission=True,
    )
    p.write_once(output / "admission.json", report)
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    result = prepare(args.root)
    print(
        json.dumps(
            {
                key: result[key]
                for key in (
                    "id",
                    "status",
                    "compiled_tasks",
                    "passed_tasks",
                    "initial_prompt_tokens_max",
                )
            }
        )
    )
