"""Freeze, acquire, build a true increment and run offline interface/panel controls."""

import argparse
import json
import subprocess
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

from finraw.qa import pipeline

from ..finance_qa_vnext_basis_scale_preparation import design
from ..finance_qa_vnext_surface_build.guards import rewrite_guard
from ..finance_qa_vnext_surface_build.stage import make_surface, realization_stats
from ..finance_qa_vnext_surface_build.transport import Provider, credential
from ..finance_qa_vnext_task_build import factory, native_facts
from ..finance_qa_vnext_task_build.archive import (
    RecordDB,
    record,
    require,
    sha,
    validate_record,
    write_json,
)
from ..finance_qa_vnext_task_build.protocol import policy as source_policy
from ..qa_reasoning_share_training_preflight import tokenization as assets
from . import acquisition, controls, panels
from .budget import IncrementLedger
from .catalog import OfflineCatalog, Parent, PublicCatalog, compose, read
from .protocol import OUTPUT, PARENT, PARENT_MANIFEST, WORK, policy, qa_config

PACKAGE = "trusted_data_synthesis/src/trusted_synthesis/experiments/"
CODE_DIRS = [
    PACKAGE + "finance_qa_vnext_catalog_bridge",
    PACKAGE + "finance_qa_vnext_task_build",
    PACKAGE + "finance_qa_vnext_surface_build",
    "raw_financial_data_lake/finraw/qa",
]
CODE_EXTRA = [
    "trusted_data_synthesis/scripts/audit_qa_vnext_catalog_incremental.py",
    "trusted_data_synthesis/scripts/audit_qa_vnext_task_build.py",
    PACKAGE + "finance_qa_vnext_basis_scale_preparation/design.py",
    PACKAGE + "finance_qa_vnext_task_panel/guards.py",
    PACKAGE + "finance_qa_vnext_model_execution/representation.py",
    PACKAGE + "qa_reasoning_share_training_preflight/tokenization.py",
    PACKAGE + "finance_qa_vnext_autonomous_formula/online/calculator.py",
    "trusted_data_synthesis/pyproject.toml",
]


def now():
    return datetime.now(timezone.utc).isoformat()


def parent(root):
    return Parent(root, PARENT, PARENT_MANIFEST)


def freeze(root):
    root, output = Path(root).resolve(), Path(root).resolve() / OUTPUT
    require(not (output / "stage_freeze.json").exists(), "bridge.one_freeze")
    require(not (output / "incremental").exists(), "bridge.no_tasks_before_rule_freeze")
    original = parent(root)
    original.verify_all()
    credential(root)  # Environment preflight precedes every start marker.
    old_inputs = original.read("stage_freeze.json")["original_sources"]
    for row in old_inputs:
        require(sha(root / row["path"]) == row["sha256"], "bridge.original_source_input_identity")
    metadata = panels.inspect_source_metadata(root)
    source_files = {row["path"]: row for row in old_inputs}
    for row in metadata["rows"]:
        raw = row["raw_object"]
        if (
            raw is not None
            and row["split"] in {"dev", "confirm"}
            and not row["historical_confirmation_issuer"]
        ):
            path = native_facts.resolve_raw(root, raw)
            source_files[str(path.relative_to(root))] = {
                "path": str(path.relative_to(root)),
                "sha256": raw["content_sha256"],
                "bytes": raw["content_size_bytes"],
                "role": "isolated_eval_snapshot",
            }
    historical = metadata["historical_confirmation_authority"]
    source_files[historical["path"]] = historical
    tokenizer = []
    for name, size, digest in assets.TOKENIZER_MEMBERS:
        path = assets.MODEL_DIRECTORY / name
        require(path.stat().st_size == size and sha(path) == digest, "bridge.tokenizer_asset_pin")
        tokenizer.append({"absolute_path": str(path), "sha256": digest, "bytes": size})
    require(
        sha(root / assets.SOURCE_CONFIGURATION) == assets.SOURCE_CONFIGURATION_SHA256,
        "bridge.existing_Student_configuration_pin",
    )
    source_files[str(assets.SOURCE_CONFIGURATION)] = {
        "path": str(assets.SOURCE_CONFIGURATION),
        "sha256": assets.SOURCE_CONFIGURATION_SHA256,
        "bytes": (root / assets.SOURCE_CONFIGURATION).stat().st_size,
        "role": "existing_Student_configuration_read_only",
    }
    paths = sorted(
        {
            *CODE_EXTRA,
            *[
                str(path.relative_to(root))
                for directory in CODE_DIRS
                for path in (root / directory).glob("*.py")
            ],
        }
    )
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    code = []
    for relative in paths:
        committed = subprocess.check_output(["git", "show", head + ":" + relative], cwd=root)
        require(
            committed == (root / relative).read_bytes(), "bridge.code_committed_before_production"
        )
        code.append({"path": relative, "sha256": sha(root / relative)})
    debit = original.read("rewrite_budget_ledger.json")
    require(
        debit["conservative_charged_tokens"] == 211338 and debit["unsettled_or_unknown_count"] == 0,
        "bridge.actual_prior_debit",
    )
    prior = [
        {
            "id": original.manifest["id"] + "/rewrite_budget_ledger.json",
            "tokens": 211338,
            "path": PARENT + "/rewrite_budget_ledger.json",
            "sha256": original.members["rewrite_budget_ledger.json"]["sha256"],
        }
    ]
    zero_references = []
    zero_reports = [
        (
            "trusted_data_synthesis/artifacts/qa_vnext_task_build/task_factory_20260911/report.json",
            ("task_generation_LLM_calls", "actual_Teacher_sessions", "actual_Student_runs"),
        ),
        (
            "trusted_data_synthesis/artifacts/qa_vnext_basis_scale_preparation/"
            "source_inventory_20260911/source_intake/report.json",
            ("semantic_model_requests", "new_Teacher_sessions", "Student_runs"),
        ),
        (
            "trusted_data_synthesis/artifacts/qa_vnext_basis_scale_preparation/"
            "source_inventory_20260911/source_census/report.json",
            ("new_semantic_API_requests", "new_Teacher_sessions", "new_Student_runs"),
        ),
    ]
    for relative, fields in zero_reports:
        prior_report = read(root / relative)
        require(
            all(prior_report[field] == 0 for field in fields),
            "bridge.earlier_same_study_zero_model",
        )
        zero_references.append(
            {"path": relative, "sha256": sha(root / relative), "zero_fields": list(fields)}
        )
    frozen = record(
        "catalog_bridge_freeze",
        created_at=now(),
        git_commit=head,
        code=code,
        rule=policy(panels.policy()),
        parent=original.descriptor(),
        panel_source_metadata=metadata,
        source_files=list(source_files.values()),
        tokenizer_assets=tokenizer,
        prior_debits=prior,
        prior_zero_model_evidence=zero_references,
        previous_preparation_and_task_factory_model_calls=0,
        production_task_outputs_observed=False,
        Teacher_or_Student_outputs_observed=False,
    )
    write_json(output / "stage_freeze.json", frozen)
    write_json(output / "inputs/panel_source_metadata.json", metadata)
    return {
        "freeze_id": frozen["id"],
        "git_commit": head,
        "panel_source_metadata_id": metadata["id"],
        "known_prior_debit": 211338,
    }


def check_freeze(root, frozen):
    validate_record(frozen, "catalog_bridge_freeze")
    require(frozen["rule"] == policy(panels.policy()), "bridge.frozen_rule")
    for member in [*frozen["code"], *frozen["source_files"], *frozen["prior_zero_model_evidence"]]:
        require(
            sha(root / member["path"]) == member["sha256"], "bridge.frozen_code_or_source_bytes"
        )
    for member in frozen["tokenizer_assets"]:
        require(sha(member["absolute_path"]) == member["sha256"], "bridge.frozen_tokenizer_bytes")
    require(parent(root).descriptor() == frozen["parent"], "bridge.unchanged_old_parent_manifest")


def acquire(root):
    root = Path(root).resolve()
    frozen = read(root / OUTPUT / "stage_freeze.json")
    check_freeze(root, frozen)
    result = acquisition.acquire(root)
    members = [
        {"path": str(path.relative_to(root)), "sha256": sha(path), "bytes": path.stat().st_size}
        for path in sorted((root / OUTPUT / "inputs").rglob("*"))
        if path.is_file()
    ]
    final = record(
        "catalog_bridge_input_freeze",
        stage_freeze_id=frozen["id"],
        members=members,
        source_acquisition_id=result["id"],
        created_before_new_TaskBundle=True,
    )
    write_json(root / OUTPUT / "input_bytes_freeze.json", final)
    return {
        "input_freeze_id": final["id"],
        "source_HTTP_attempts": result["request_count"],
        "qualified_extra_sources": len(result["sources"]),
    }


def seal(directory, **fields):
    directory = Path(directory)
    members = [
        {
            "path": str(path.relative_to(directory)),
            "sha256": sha(path),
            "bytes": path.stat().st_size,
        }
        for path in sorted(directory.rglob("*"))
        if path.is_file() and path != directory / "manifest.json"
    ]
    value = record("manifest", members=members, **fields)
    write_json(directory / "manifest.json", value)
    return value


def build_increment(root, frozen, key):
    output = root / OUTPUT / "incremental"
    original = parent(root)
    old_ids = {row["task_id"] for row in original.read("catalog.json")["tasks"]}
    acquired = read(root / OUTPUT / "inputs/source_acquisition.json")
    write_json(
        output / "stage_freeze.json",
        record(
            "incremental_task_freeze",
            git_commit=frozen["git_commit"],
            stage_freeze_id=frozen["id"],
            rule={"source_split": source_policy()["source_split"]},
            input_freeze=read(root / OUTPUT / "input_bytes_freeze.json"),
        ),
    )
    native = native_facts.run(
        root, output, work=WORK + "/train", extra_issuer_sources=acquired["sources"]
    )
    print(
        json.dumps(
            {
                "phase": "increment_native",
                "source_observations": native["source_observation_count"],
                "issuer_FCF": native["issuer_FCF_source_counts"],
            }
        ),
        flush=True,
    )
    db = RecordDB(str(root / WORK / "train/native_fact_qa.sqlite3"))
    try:
        kg = native["kg_build"]
        bindings = read(output / "native_bindings.json")
        facts = pipeline._load_facts_by_id(
            db, list(bindings), kg["input_fact_build_id"], kg["input_entity_build_id"]
        )
        usage = {
            key: {field: value[field] for field in ("split", "allowed_uses", "source_cluster")}
            for key, value in bindings.items()
        }
        write_json(output / "all_leaf_usage.json", usage)
        selected, failures, enumeration = factory.enumerate_bindings(facts, bindings, usage)
        write_json(output / "binding_failures.json", failures)
        write_json(output / "binding_enumeration.json", enumeration)
        new = [
            row
            for group in ("stock_rollforward", "annual_flow", "company_defined_metric", "control")
            for row in selected[group]
            if row["task_id"] not in old_ids
        ]
        # Selection uses source enumeration only, never rewrite outcomes.
        omitted = new[27:]
        new = new[:27]
        require(
            all(row["family"] == "company_defined_metric" for row in new),
            "bridge.only_registered_issuer_source_extension",
        )
        registry = record(
            "incremental_target_registry",
            stage_freeze_id=frozen["id"],
            tasks=[
                {key: value for key, value in row.items() if key != "certificate"} for row in new
            ],
            omitted_beyond_remaining_cap=[row["task_id"] for row in omitted],
            old_ids_rewritten=[],
            registered_before_rewrite=True,
        )
        write_json(output / "canonical_task_registry.json", registry)
        ledger = IncrementLedger(
            root / WORK / "rewrite_budget.sqlite3",
            frozen["id"],
            prior_debits=frozen["prior_debits"],
        )
        ledger.register([row["task_id"] for row in new], old_ids)
        write_json(output / "budget_initial.json", ledger.snapshot())
        exported, rejected, validation = [], [], None
        if new:
            build, candidates, plans, compilations, validation = factory.compile_batch(
                db,
                kg,
                new,
                facts,
                bindings,
                output,
                "new_tasks",
                config=qa_config(),
                provider_factory=lambda task: Provider(task, ledger, output, key),
            )
            lookup = {row["candidate_id"]: row for row in candidates}
            exported, rejected = factory.export_batch(
                db,
                kg,
                build,
                new,
                candidates,
                plans,
                compilations,
                facts,
                bindings,
                usage,
                output,
                surface_context=lambda item, sample, public: make_surface(
                    item, sample, public, lookup[sample["candidate_id"]], frozen["id"]
                ),
            )
        else:
            pipeline.ensure_qa_schema(db)
            write_json(output / "new_tasks/pattern_compilations.json", [])
        require(not rejected and len(exported) == len(new), "bridge.all_incremental_tasks_retained")
        write_json(
            output / "catalog.json",
            record(
                "fixed_task_catalog",
                tasks=exported,
                parent_manifest_id=PARENT_MANIFEST,
                final_training_population_selected=False,
            ),
        )
        write_json(output / "qa_validation_rejections.json", rejected)
        tables = factory.dump_parents(db, output)
        stats = realization_stats(exported, output, ledger)
        report = record(
            "incremental_task_report",
            tasks=len(exported),
            rewrite=stats,
            actual_parents=tables,
            QA_validation=validation,
            old_task_count_preserved=233,
            old_task_rewrite_requests=0,
            new_task_ids=[row["task_id"] for row in exported],
            binding_rejection_count=len(failures),
            original_source_acquisition_id=acquired["id"],
        )
        write_json(output / "rewrite_budget_ledger.json", ledger.snapshot())
        write_json(output / "report.json", report)
        seal(
            output,
            scope="only new scientific tasks, real Fact/KG/QA parents and new surface responses",
        )
        return report
    finally:
        db.close()


def run_controls(root, full, public):
    output = root / OUTPUT
    online = PublicCatalog(root, OUTPUT + "/public_catalog.json", public["id"])
    offline = OfflineCatalog(root, OUTPUT + "/catalog.json", full["id"])
    cells = {}
    for item in sorted(full["tasks"], key=lambda row: row["task_id"]):
        if item["parent_manifest_id"] != PARENT_MANIFEST:
            continue
        surface = (
            "rewritten" if item["surface_category"] == "accepted_true_rewrite" else "canonical"
        )
        cells.setdefault((item["family"], item["quantity"], surface), item["task_id"])
    frozen = record(
        "script_control_selection",
        rule="first existing old TaskID in each family/quantity/surface cell; no invented variants",
        rows=[
            {"family": cell[0], "quantity": cell[1], "surface": cell[2], "task_id": task}
            for cell, task in sorted(cells.items())
        ],
        missing_cells=[
            list(cell)
            for cell in (
                (g, q, s)
                for g in ("stock_rollforward", "annual_flow", "company_defined_metric", "control")
                for q in ("difference", "relative_change")
                for s in ("rewritten", "canonical")
            )
            if cell not in cells
        ],
    )
    write_json(output / "controls/fixture_selection.json", frozen)
    fixtures = [offline.fixture(task, online) for _, task in sorted(cells.items())]
    result = controls.run_scripted_controls(fixtures, root, tokenize=True)
    write_json(output / "controls/report.json", result)
    require(result["status"] == "PASS", "bridge.scripted_controls_pass")
    require(
        result["materialization"]["status"] == "PASS_SCRIPTED_REPRESENTATION_ONLY"
        and not result["materialization"]["failures"],
        "bridge.actual_scripted_token_materialization_pass",
    )
    return result


def run(root):
    root, output = Path(root).resolve(), Path(root).resolve() / OUTPUT
    frozen = read(output / "stage_freeze.json")
    check_freeze(root, frozen)
    inputs = read(output / "input_bytes_freeze.json")
    validate_record(inputs, "catalog_bridge_input_freeze")
    acquired = read(output / "inputs/source_acquisition.json")
    validate_record(acquired, "bounded_source_acquisition")
    require(
        inputs["stage_freeze_id"] == frozen["id"]
        and inputs["source_acquisition_id"] == acquired["id"],
        "bridge.exact_input_freeze_join",
    )
    for row in inputs["members"]:
        require(sha(root / row["path"]) == row["sha256"], "bridge.final_input_bytes")
    key = credential(root)
    require(not (output / "run_started.json").exists(), "bridge.one_production_run")
    require(
        not (root / WORK / "train/native_fact_qa.sqlite3").exists()
        and not (output / "panels").exists(),
        "bridge.new_work_only",
    )
    write_json(
        output / "run_started.json",
        record("bridge_run_start", stage_freeze_id=frozen["id"], at=now()),
    )
    try:
        with rewrite_guard() as counters, ThreadPoolExecutor(max_workers=2) as pool:
            panel_future = pool.submit(
                panels.run,
                root,
                output / "panels",
                root / WORK / "panels",
                expected_policy_id=panels.policy()["id"],
                expected_source_metadata_id=frozen["panel_source_metadata"]["id"],
                freeze_id=frozen["id"],
            )
            incremental = build_increment(root, frozen, key)
            fresh = Parent(root, OUTPUT + "/incremental")
            full, public = compose(root, output, [parent(root), fresh], frozen["id"])
            checked = run_controls(root, full, public)
            panel = panel_future.result()
        require(not any(counters["forbidden"].values()), "bridge.no_forbidden_model_or_GPU_paths")
        write_json(output / "execution_guards.json", record("bridge_execution_guards", **counters))
        counts = Counter(row["family"] for row in full["tasks"])
        maximum = 5 * min(
            40,
            counts["stock_rollforward"],
            counts["annual_flow"],
            counts["company_defined_metric"],
            counts["control"] // 2,
        )
        budget = read(output / "incremental/rewrite_budget_ledger.json")
        report = record(
            "catalog_bridge_report",
            stage_freeze_id=frozen["id"],
            status="BOUNDED_INCREMENT_AND_INTERFACE_PREPARATION_COMPLETED",
            catalog_id=full["id"],
            public_catalog_id=public["id"],
            tasks=len(full["tasks"]),
            new_tasks=incremental["tasks"],
            preserved_tasks=233,
            family_counts=dict(counts),
            balanced_reference_supply_ceiling=maximum,
            source_quota_at_least_180=maximum >= 180,
            prospective_population_design=design.population(maximum) if maximum >= 180 else None,
            scripted_control_count=checked["registered"],
            scripted_control_passed=checked["passed"],
            materialization_summary={
                key: value
                for key, value in checked["materialization"].items()
                if key not in {"checks", "failures", "policy"}
            },
            evaluation_panel_status=panel["status"],
            evaluation_tasks=panel["unique_task_count"],
            evaluation_panel_quota_complete=panel["quota_complete"],
            evaluation_worker_primary_qualification_established=False,
            known_cumulative_token_debit=budget["cumulative_conservative_debit"],
            remaining_registered_global_allowance=budget["remaining_registered_global_allowance"],
            Teacher_sessions=0,
            Student_runs=0,
            GPU_runs=0,
            actual_training_packages=0,
            common_AB_material_ready_population_established=False,
            formal_collection_started=False,
            stop_or_next_boundary=(
                "source supply below 180: stop formal collection"
                if maximum < 180
                else "source-only quota sufficient; no common real A/B material established, "
                "evaluation worker qualification still required before formal collection"
            ),
        )
        write_json(output / "report.json", report)
        check_freeze(root, frozen)
        parent(root).verify_all()
        write_json(
            output / "run_completed.json",
            record("bridge_run_completed", at=now(), report_id=report["id"]),
        )
    except BaseException as error:
        write_json(
            output / "run_failed.json",
            record(
                "bridge_run_failure",
                at=now(),
                type=type(error).__name__,
                reason=str(error).replace(key, "[REDACTED]"),
                no_automatic_replay=True,
            ),
        )
        seal(output, status="failed", original_budget_not_reset=True)
        raise
    seal(output, runtime_SQLite_excluded=WORK, original_parent_unchanged=True)
    return {
        key: report[key]
        for key in (
            "id",
            "tasks",
            "new_tasks",
            "family_counts",
            "balanced_reference_supply_ceiling",
            "evaluation_tasks",
            "scripted_control_count",
            "known_cumulative_token_debit",
        )
    }


def verify(root):
    root = Path(root).resolve()
    frozen = read(root / OUTPUT / "stage_freeze.json")
    check_freeze(root, frozen)
    outer = Parent(root, OUTPUT)
    outer.verify_all()
    parent(root).verify_all()
    full, public = outer.read("catalog.json"), outer.read("public_catalog.json")
    online = PublicCatalog(root, OUTPUT + "/public_catalog.json", public["id"])
    offline = OfflineCatalog(root, OUTPUT + "/catalog.json", full["id"])
    for item in full["tasks"]:
        fixture = offline.fixture(item["task_id"], online)
        require(fixture["bundle"]["validation"]["status"] == "passed", "bridge.actual_QA_pass")
    original_ids = {row["task_id"] for row in parent(root).read("catalog.json")["tasks"]}
    actual_ids = {row["task_id"] for row in full["tasks"]}
    require(
        original_ids <= actual_ids and len(actual_ids) == len(full["tasks"]) <= 260,
        "bridge.preserved_unique_scientific_tasks",
    )
    budget = read(root / OUTPUT / "incremental/rewrite_budget_ledger.json")
    require(
        budget["request_reservations"] <= 54
        and budget["conservative_charged_tokens"] <= 525312
        and budget["cumulative_conservative_debit"] <= 1_000_000_000
        and budget["previous_registered_debit"] == 211338,
        "bridge.budget_continuity",
    )
    require(
        all(row["task_id"] not in original_ids for row in budget["reservations"]),
        "bridge.no_old_surface_retry",
    )
    require((root / OUTPUT / "run_completed.json").exists(), "bridge.actual_run_completed")
    return {
        "manifest_id": outer.manifest["id"],
        "members": len(outer.members),
        "preserved_tasks": len(original_ids),
        "new_tasks": len(actual_ids - original_ids),
        "total_tasks": len(actual_ids),
        "cumulative_debit": budget["cumulative_conservative_debit"],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=["freeze", "acquire", "run", "verify"])
    parser.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    print(
        json.dumps(
            {"freeze": freeze, "acquire": acquire, "run": run, "verify": verify}[args.phase](
                args.root
            ),
            ensure_ascii=False,
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
