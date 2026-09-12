"""One frozen source-extension/real-rewrite Build; no Teacher or Student execution."""

import argparse
import hashlib
import json
import re
import subprocess
from collections import Counter, deque
from datetime import datetime, timezone
from pathlib import Path

from finraw.qa import pipeline
from finraw.qa.verbalizer import build_question_contract, validate_question_roundtrip

from ..finance_qa_vnext_task_build import factory, native_facts
from ..finance_qa_vnext_task_build.archive import OUTPUT as PARENT
from ..finance_qa_vnext_task_build.archive import WORK as PARENT_WORK
from ..finance_qa_vnext_task_build.archive import (
    RecordDB,
    record,
    require,
    sha,
    validate_record,
    write_json,
)
from .budget import Ledger
from .guards import rewrite_guard
from .protocol import policy, qa_config
from .sources import OUTPUT, WORK
from .transport import MODEL, Provider, credential

PACKAGE = "trusted_data_synthesis/src/trusted_synthesis/experiments/"
CODE_DIRECTORIES = [
    PACKAGE + "finance_qa_vnext_surface_build",
    PACKAGE + "finance_qa_vnext_task_build",
    "raw_financial_data_lake/finraw/qa",
]
CODE_FILES = [
    "trusted_data_synthesis/scripts/audit_qa_vnext_task_build.py",
    "raw_financial_data_lake/finraw/llm_client.py",
    "raw_financial_data_lake/finraw/db/client.py",
    PACKAGE + "finance_qa_vnext_task_panel/guards.py",
]


def read(path):
    return json.loads(Path(path).read_bytes())


def now():
    return datetime.now(timezone.utc).isoformat()


def canonical_bytes(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def parent_identity(root):
    directory = root / PARENT
    manifest = read(directory / "manifest.json")
    validate_record(manifest, "manifest")
    for member in manifest["members"]:
        path = directory / member["path"]
        require(
            path.resolve().is_relative_to(directory.resolve()) and not path.is_symlink(),
            "surface.parent_member_contained",
        )
        require(
            path.stat().st_size == member["bytes"] and sha(path) == member["sha256"],
            "surface.original_221_archive_unchanged",
        )
    return {
        "manifest_id": manifest["id"],
        "manifest_sha256": sha(directory / "manifest.json"),
        "members": len(manifest["members"]),
        "task_count": len(read(directory / "catalog.json")["tasks"]),
    }


def original_sources(root):
    # Freeze bytes of the already indexed input set; no semantic census or source search here.
    inventory = read(root / PARENT / "native_source_inventory.json")
    issuers = read(root / PARENT / "issuer_source_tables.json")
    raw_objects = {
        row["raw_object"]["raw_object_id"]: row["raw_object"]
        for row in [*inventory, *issuers["sources"]]
    }
    rows = []
    for identifier, raw in sorted(raw_objects.items()):
        path = native_facts.resolve_raw(root, raw)
        rows.append(
            {
                "raw_object_id": identifier,
                "path": str(path.relative_to(root)),
                "sha256": raw["content_sha256"],
                "bytes": path.stat().st_size,
            }
        )
    projection = root / PARENT_WORK / "qa_build.sqlite3"
    rows.append(
        {
            "path": str(projection.relative_to(root)),
            "sha256": sha(projection),
            "bytes": projection.stat().st_size,
            "role": "old read-only archive serving projection",
        }
    )
    return rows


def freeze(root):
    root, output = Path(root).resolve(), Path(root).resolve() / OUTPUT
    require(not (output / "stage_freeze.json").exists(), "surface.new_freeze_only")
    require(
        not (output / "native_fact_build_report.json").exists(),
        "surface.no_production_outputs_before_freeze",
    )
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    paths = sorted(
        {
            *CODE_FILES,
            *[
                str(path.relative_to(root))
                for directory in CODE_DIRECTORIES
                for path in (root / directory).glob("*.py")
            ],
        }
    )
    code = []
    for relative in paths:
        committed = subprocess.check_output(["git", "show", head + ":" + relative], cwd=root)
        require(
            committed == (root / relative).read_bytes(), "surface.code_committed_before_generation"
        )
        code.append({"path": relative, "sha256": sha(root / relative)})
    inputs = [
        {"path": str(path.relative_to(root)), "sha256": sha(path), "bytes": path.stat().st_size}
        for path in sorted((output / "inputs").rglob("*"))
        if path.is_file()
    ]
    value = record(
        "surface_stage_freeze",
        created_at=now(),
        git_commit=head,
        code=code,
        rule=policy(),
        inherited_parent=parent_identity(root),
        original_sources=original_sources(root),
        source_acquisition_inputs=inputs,
        source_diagnostics_known_before_freeze=True,
        production_task_or_model_response_outputs_observed=False,
    )
    write_json(output / "stage_freeze.json", value)
    return {
        "stage_freeze_id": value["id"],
        "git_commit": head,
        "source_files": len(value["original_sources"]),
    }


def check_freeze(root, frozen):
    validate_record(frozen, "surface_stage_freeze")
    require(frozen["rule"] == policy(), "surface.same_frozen_rule")
    for member in [
        *frozen["code"],
        *frozen["original_sources"],
        *frozen["source_acquisition_inputs"],
    ]:
        require(
            sha(root / member["path"]) == member["sha256"], "surface.frozen_input_bytes_unchanged"
        )
    require(
        parent_identity(root) == frozen["inherited_parent"], "surface.inherited_parent_identity"
    )


def make_surface(item, sample, public, candidate, frozen_id):
    generation = read_json_field(sample["source_metadata"])["question_generation"]
    slots = generation["surface_slots"]
    semantics = candidate["canonical_semantics"]
    semantics = {
        **semantics,
        "time_scope": pipeline._question_display_time_scope(candidate["time_scope"], semantics),
    }
    contract = build_question_contract(semantics, slots, list(slots))
    actual_check = validate_question_roundtrip(sample["question"], contract, trusted_contract=True)
    require(actual_check["passed"], "surface.actual_final_question_semantics")
    require(
        contract["temporal_quantity"]["quantity"] == item["target"]["quantity"],
        "surface.same_physical_target_quantity",
    )
    requests = list((generation.get("llm_telemetry") or {}).get("request_ids") or [])
    method = sample["generation_method"]
    words_changed = re.findall(r"\w+", sample["question"].casefold()) != re.findall(
        r"\w+", sample["canonical_question"].casefold()
    )
    if method == "controlled_llm_protected_rewrite":
        category = (
            "accepted_true_rewrite"
            if words_changed and generation.get("rewrite_template_changed")
            else "unchanged_or_format_only"
        )
    elif method == "controlled_llm_surface_realization":
        category = "surface_only"
    else:
        category = "canonical_fallback"
        require(
            sample["question"] == sample["canonical_question"], "surface.fallback_exact_canonical"
        )
    public_hash = hashlib.sha256(
        canonical_bytes(factory.teacher_messages({"public": public}))
    ).hexdigest()
    version = (
        "surface_" + hashlib.sha256(canonical_bytes([item["task_id"], public_hash])).hexdigest()
    )
    return record(
        "task_surface_realization",
        stage_freeze_id=frozen_id,
        canonical_task_id=item["task_id"],
        surface_version_id=version,
        public_messages_sha256=public_hash,
        category=category,
        canonical_question=sample["canonical_question"],
        generation_method=method,
        question_contract=contract,
        actual_question_validation=actual_check,
        generation_validation=generation,
        model_requests=[
            {
                "request_id": identifier,
                "purpose": "question_rewrite",
                "is_Teacher_trajectory": False,
            }
            for identifier in requests
        ],
        future_AB_and_all_conditions_use_same_public_bytes=True,
        prior_response_relabeling_allowed=False,
    )


def read_json_field(value):
    return json.loads(value) if isinstance(value, str) else value


def realization_stats(tasks, output, ledger):
    surfaces = [read(output / row["path"])["surface_realization"] for row in tasks]
    counts = Counter(row["category"] for row in surfaces)
    checks = [
        check
        for row in surfaces
        for check in row["generation_validation"].get("variant_checks", [])
    ]
    failed = [check for check in checks if not check["passed"]]
    semantic = [
        check
        for check in failed
        if any("question_semantics:" in error for error in check["errors"])
    ]
    snapshot = ledger.snapshot()
    req, success = snapshot["sent_request_count"], snapshot["http_success_count"]
    n = len(surfaces)
    per_task = {}
    for row in snapshot["reservations"]:
        per_task.setdefault(row["task_id"], []).append(row)
    no_return = sum(
        bool(per_task.get(row["canonical_task_id"]))
        and not any(
            item["outcome"] in {"response_received", "rewrite_structure_failure"}
            for item in per_task[row["canonical_task_id"]]
        )
        for row in surfaces
    )
    return {
        "registered_task_count": n,
        "actual_request_count": req,
        "http_success_count": success,
        "http_success_rate": success / req if req else None,
        "http_rate_status": "OBSERVED" if req else "NOT_APPLICABLE",
        "accepted_true_rewrite_count": counts["accepted_true_rewrite"],
        "accepted_true_rewrite_rate": counts["accepted_true_rewrite"] / n if n else None,
        "surface_only_count": counts["surface_only"],
        "unchanged_or_format_only_count": counts["unchanged_or_format_only"],
        "canonical_fallback_count": counts["canonical_fallback"],
        "no_returned_response_task_count": no_return,
        "no_request_task_count": sum(not row["model_requests"] for row in surfaces),
        "evaluated_candidate_variant_count": len(checks),
        "rejected_candidate_variant_count": len(failed),
        "semantic_rejected_variant_count": len(semantic),
        "rejection_error_counts": dict(Counter(error for row in failed for error in row["errors"])),
        "all_returned_variants_retained_in_raw_responses": True,
        "later_candidates_not_evaluated_after_first_valid_accept": True,
        "repair_request_count": sum(row["attempt"] == 2 for row in snapshot["reservations"]),
        "model_identity_counts": dict(
            Counter(
                row["response_model"] for row in snapshot["reservations"] if row["response_model"]
            )
        ),
        "budget": {key: value for key, value in snapshot.items() if key != "reservations"},
    }


def build_tasks(root, output, native, frozen, ledger, key):
    db = RecordDB(str(root / WORK / "native_fact_qa.sqlite3"))
    kg = native["kg_build"]
    bindings = read(output / "native_bindings.json")
    facts = pipeline._load_facts_by_id(
        db, list(bindings), kg["input_fact_build_id"], kg["input_entity_build_id"]
    )
    usage = {
        key: {field: row[field] for field in ("split", "allowed_uses", "source_cluster")}
        for key, row in bindings.items()
    }
    write_json(output / "all_leaf_usage.json", usage)
    selected, failures, enumeration = factory.enumerate_bindings(facts, bindings, usage)
    write_json(output / "binding_failures.json", failures)
    write_json(output / "binding_enumeration.json", enumeration)
    queues = [
        deque(selected[group])
        for group in ("stock_rollforward", "annual_flow", "company_defined_metric")
    ]
    duals = []
    while any(queues):
        for queue in queues:
            if queue:
                duals.append(queue.popleft())
    first, rest = duals[:12] + selected["control"][:8], duals[12:] + selected["control"][8:]
    require(len(first) == 20 and len(first + rest) <= 260, "surface.frozen_first_and_total_caps")
    registry = record(
        "canonical_task_registry",
        stage_freeze_id=frozen["id"],
        tasks=[
            {
                key: row[key]
                for key in ("task_id", "target", "family", "previous_fact_id", "current_fact_id")
            }
            for row in first + rest
        ],
        scientific_task_count=len(first + rest),
        source_rule_frozen_before_enumeration=True,
        created_before_any_rewrite_request=True,
        first_20_included=True,
    )
    write_json(output / "canonical_task_registry.json", registry)
    exported, rejected, batches = [], [], []
    for name, items in (("first_20", first), ("candidate_catalog", rest)):
        if not items:
            continue
        build, candidates, plans, compilations, validation = factory.compile_batch(
            db,
            kg,
            items,
            facts,
            bindings,
            output,
            name,
            config=qa_config(),
            provider_factory=lambda task: Provider(task, ledger, output, key),
        )
        by_id = {row["candidate_id"]: row for row in candidates}

        def surface_context(item, sample, public, _by_id=by_id):
            return make_surface(item, sample, public, _by_id[sample["candidate_id"]], frozen["id"])

        batch_tasks, batch_rejected = factory.export_batch(
            db,
            kg,
            build,
            items,
            candidates,
            plans,
            compilations,
            facts,
            bindings,
            usage,
            output,
            surface_context=surface_context,
        )
        exported.extend(batch_tasks)
        rejected.extend(batch_rejected)
        batch = {
            "batch": name,
            "qa_build_id": build,
            "registered_count": len(items),
            "exported_count": len(batch_tasks),
            "qa_validation": validation,
        }
        batches.append(batch)
        write_json(output / name / "export_report.json", batch)
        statistics = realization_stats(exported, output, ledger)
        print(
            json.dumps(
                {
                    "batch": name,
                    "registered": len(items),
                    "exported": len(batch_tasks),
                    "cumulative_requests": statistics["actual_request_count"],
                    "cumulative_true_rewrites": statistics["accepted_true_rewrite_count"],
                }
            ),
            flush=True,
        )
        require(
            not batch_rejected and len(batch_tasks) == len(items),
            "surface.no_model_based_task_deletion",
        )
        if name == "first_20":
            write_json(output / "first_20/integration_observation.json", statistics)
            require(
                statistics["actual_request_count"] > 0
                and statistics["accepted_true_rewrite_count"] > 0,
                "surface.real_rewrite_integration_not_established",
            )
    require(
        {row["task_id"] for row in exported} == {row["task_id"] for row in registry["tasks"]},
        "surface.complete_registered_task_retention",
    )
    write_json(
        output / "catalog.json",
        record(
            "fixed_task_catalog",
            tasks=exported,
            stage_freeze_id=frozen["id"],
            registry_id=registry["id"],
            both_future_pools_use_this_exact_catalog=True,
            final_training_population_selected=False,
            training_mu_fixed=False,
            mixed_LLM_and_canonical_surfaces=True,
        ),
    )
    write_json(output / "qa_validation_rejections.json", rejected)
    parents = factory.dump_parents(db, output)
    statistics = realization_stats(exported, output, ledger)
    write_json(output / "rewrite_budget_ledger.json", ledger.snapshot())
    families = Counter(row["family"] for row in exported)
    feasible = 5 * min(
        40,
        families["annual_flow"],
        families["stock_rollforward"],
        families["company_defined_metric"],
        families["control"] // 2,
    )
    summary = record(
        "protected_surface_report",
        status="ACTUAL_SOURCE_EXTENSION_AND_PROTECTED_REWRITE_BUILD",
        stage_freeze_id=frozen["id"],
        canonical_task_registry_id=registry["id"],
        batches=batches,
        exported_task_count=len(exported),
        family_counts=dict(families),
        rewrite=statistics,
        source_cluster_count=len({row["source_cluster"] for row in exported}),
        family_source_cluster_counts={
            group: len({row["source_cluster"] for row in exported if row["family"] == group})
            for group in families
        },
        binding_rejection_count=len(failures),
        binding_rejection_reasons=dict(Counter(row["reason"] for row in failures)),
        qa_rejection_count=len(rejected),
        parent_tables=parents,
        balanced_training_supply_ceiling=feasible,
        training_supply_is_not_material_or_worker_readiness=True,
        target_group_shortfalls={
            group: max(0, 40 - families[group])
            for group in ("annual_flow", "stock_rollforward", "company_defined_metric")
        },
        original_FinQA_questions_answers_programs_used=0,
        actual_Teacher_sessions=0,
        actual_Student_runs=0,
        actual_GPU_runs=0,
        actual_tokenizer_loads=0,
        training_material_rows=0,
        final_training_population_selected=False,
        future_training_or_material_kernel_frozen=False,
        old_responses_reused_under_new_prefix=0,
    )
    write_json(output / "report.json", summary)
    db.close()
    return summary


def run(root):
    root, output = Path(root).resolve(), Path(root).resolve() / OUTPUT
    frozen = read(output / "stage_freeze.json")
    check_freeze(root, frozen)
    require(not (output / "run_started.json").exists(), "surface.one_run_per_frozen_stage")
    write_json(
        output / "run_started.json",
        record("surface_run_start", stage_freeze_id=frozen["id"], started_at=now()),
    )
    ledger = Ledger(root / WORK / "rewrite_budget.sqlite3", frozen["id"])
    write_json(output / "rewrite_budget_initial.json", ledger.snapshot())
    key = credential(root)
    try:
        with rewrite_guard() as counters:
            native = native_facts.run(root, output, work=WORK, extra_issuer_sources=())
            print(
                json.dumps(
                    {
                        "native_fact_build": native["id"],
                        "issuer_FCF": native["issuer_FCF_source_counts"],
                    }
                ),
                flush=True,
            )
            summary = build_tasks(root, output, native, frozen, ledger, key)
        require(
            not any(counters["forbidden"].values()),
            "surface.no_forbidden_model_or_training_execution",
        )
        write_json(output / "execution_guards.json", record("surface_execution_guards", **counters))
        check_freeze(root, frozen)
        write_json(
            output / "run_completed.json",
            record(
                "surface_run_completion",
                stage_freeze_id=frozen["id"],
                report_id=summary["id"],
                completed_at=now(),
                parent_archive_unchanged=True,
            ),
        )
    except BaseException as exc:
        write_json(
            output / "run_failed.json",
            record(
                "surface_run_failure",
                error_type=type(exc).__name__,
                error_code=str(exc).replace(key, "[REDACTED_CREDENTIAL]")
                if isinstance(exc, ValueError)
                else None,
                failed_at=now(),
                remaining_budget_cannot_be_replayed=True,
                budget=ledger.snapshot(),
            ),
        )
        seal(root)
        raise
    seal(root)
    return {
        "report_id": summary["id"],
        "tasks": summary["exported_task_count"],
        "family_counts": summary["family_counts"],
        "rewrite": summary["rewrite"],
        "balanced_training_supply_ceiling": summary["balanced_training_supply_ceiling"],
    }


def seal(root):
    output = Path(root).resolve() / OUTPUT
    members = []
    for path in sorted(output.rglob("*")):
        if path.is_file() and path != output / "manifest.json":
            require(not path.is_symlink(), "surface.manifest_regular_files")
            members.append(
                {
                    "path": str(path.relative_to(output)),
                    "sha256": sha(path),
                    "bytes": path.stat().st_size,
                }
            )
    manifest = record(
        "manifest",
        members=members,
        runtime_SQLite_excluded=WORK,
        scope="new source/rewrite stage; old namespace untouched",
    )
    write_json(output / "manifest.json", manifest)
    return manifest


def verify(root):
    root, output = Path(root).resolve(), Path(root).resolve() / OUTPUT
    manifest = read(output / "manifest.json")
    validate_record(manifest, "manifest")
    for member in manifest["members"]:
        path = output / member["path"]
        require(
            path.resolve().is_relative_to(output) and not path.is_symlink(),
            "surface.member_contained",
        )
        require(
            path.stat().st_size == member["bytes"] and sha(path) == member["sha256"],
            "surface.member_identity",
        )
    require(
        {
            str(path.relative_to(output))
            for path in output.rglob("*")
            if path.is_file() and path != output / "manifest.json"
        }
        == {row["path"] for row in manifest["members"]},
        "surface.complete_manifest_member_set",
    )
    frozen = read(output / "stage_freeze.json")
    check_freeze(root, frozen)
    require((output / "run_completed.json").exists(), "surface.run_actually_completed")
    tasks, versions = set(), set()
    for reference in read(output / "catalog.json")["tasks"]:
        path = output / reference["path"]
        bundle = read(path)
        validate_record(bundle, "TaskBundle")
        surface = bundle["surface_realization"]
        validate_record(surface, "task_surface_realization")
        require(bundle["id"] == reference["bundle_id"], "surface.catalog_bundle_identity")
        require(
            bundle["task_id"] == bundle["canonical_task_id"] == surface["canonical_task_id"]
            and bundle["task_id"] not in tasks,
            "surface.unique_canonical_task",
        )
        require(surface["surface_version_id"] not in versions, "surface.unique_public_version")
        actual = validate_question_roundtrip(
            bundle["public"]["question"], surface["question_contract"], trusted_contract=True
        )
        require(actual["passed"], "surface.actual_final_text_semantics_replayed")
        visible = read(path.parent / "teacher_visible.json")
        require(visible == factory.teacher_messages(bundle), "surface.exact_shared_public_messages")
        require(
            hashlib.sha256(canonical_bytes(visible)).hexdigest()
            == surface["public_messages_sha256"],
            "surface.public_message_byte_identity",
        )
        require(
            sha(path.parent / "teacher_visible.json") == surface["public_messages_sha256"],
            "surface.literal_public_file_bytes",
        )
        expected_version = (
            "surface_"
            + hashlib.sha256(
                canonical_bytes([bundle["task_id"], surface["public_messages_sha256"]])
            ).hexdigest()
        )
        require(expected_version == surface["surface_version_id"], "surface.version_identity")
        tasks.add(bundle["task_id"])
        versions.add(surface["surface_version_id"])
    report = read(output / "report.json")
    require(
        len(tasks) == report["exported_task_count"]
        and report["rewrite"]["actual_request_count"] > 0
        and report["rewrite"]["accepted_true_rewrite_count"] > 0,
        "surface.real_retained_build_not_zero_model",
    )
    snapshot = read(output / "rewrite_budget_ledger.json")
    registry_ids = {
        row["task_id"] for row in read(output / "canonical_task_registry.json")["tasks"]
    }
    require(
        tasks == registry_ids and len(tasks) <= 260,
        "surface.registry_complete_not_wording_expansion",
    )
    require(
        {row["task_id"] for row in snapshot["reservations"]} <= tasks,
        "surface.requests_only_for_registered_tasks",
    )
    require(
        max(Counter(row["task_id"] for row in snapshot["reservations"]).values(), default=0) <= 2,
        "surface.at_most_two_attempts_per_task",
    )
    for reference in read(output / "catalog.json")["tasks"]:
        bundle = read(output / reference["path"])
        surface = bundle["surface_realization"]
        rows = [row for row in snapshot["reservations"] if row["task_id"] == bundle["task_id"]]
        require(
            {row["request_id"] for row in rows}
            == {row["request_id"] for row in surface["model_requests"]},
            "surface.exact_per_task_request_accounting",
        )
        if surface["category"] == "accepted_true_rewrite":
            require(
                rows
                and rows[-1]["response_model"] == MODEL
                and rows[-1]["http_success"] == 1
                and rows[-1]["outcome"] == "response_received"
                and rows[-1]["state"] == "settled",
                "surface.accepted_rewrite_has_real_qualified_response",
            )
    require(
        snapshot["request_reservations"] <= 520
        and snapshot["budget_breach_count"] == 0
        and snapshot["conservative_charged_tokens"] <= snapshot["policy"]["token_cap"],
        "surface.actual_request_token_caps",
    )
    require(
        all(
            row["response_model"] in {None, MODEL} or row["outcome"] != "response_received"
            for row in snapshot["reservations"]
        ),
        "surface.no_accepted_wrong_model",
    )
    return {
        "manifest_id": manifest["id"],
        "members": len(manifest["members"]),
        "canonical_tasks": len(tasks),
        "surface_versions": len(versions),
        "actual_text_semantics_passed": len(tasks),
        "old_221_archive_byte_identity": True,
        "actual_rewrite_requests": snapshot["sent_request_count"],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=["freeze", "run", "verify"])
    parser.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    print(
        json.dumps(
            {"freeze": freeze, "run": run, "verify": verify}[args.phase](args.root),
            ensure_ascii=False,
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
