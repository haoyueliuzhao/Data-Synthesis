"""One frozen public-only LLM wording pass for the existing 900 evaluation tasks."""

import argparse
import json
import re
import sqlite3
import subprocess
import threading
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import closing
from pathlib import Path

from ..finance_qa_vnext_catalog_bridge.catalog import (
    OfflineCatalog,
    Parent,
    PublicCatalog,
    read,
    safe_path,
)
from ..finance_qa_vnext_catalog_bridge.stage import seal
from ..finance_qa_vnext_eval_readiness import collection, materials
from ..finance_qa_vnext_eval_readiness import stage as readiness_stage
from ..finance_qa_vnext_eval_readiness.transport import Provider as TeacherProvider
from ..finance_qa_vnext_eval_readiness.transport import verify_receipts
from ..finance_qa_vnext_readiness_revision import stage as revision_stage
from ..finance_qa_vnext_readiness_revision.protocol import COLLECTION as FIXED_COLLECTION
from ..finance_qa_vnext_surface_build.budget import BudgetRejected
from ..finance_qa_vnext_surface_build.guards import rewrite_guard
from ..finance_qa_vnext_surface_build.transport import credential
from ..finance_qa_vnext_task_build.archive import record, require, sha, validate_record, write_json
from . import budget, guard, overlay, transport
from .protocol import (
    AUDITS,
    LEDGER,
    OUTPUT,
    OWNER_FREEZE,
    PARENT_PANEL,
    PARENT_PANEL_MANIFEST,
    PARENT_REVISION,
    PARENT_REVISION_AUDIT_MANIFEST,
    PARENT_REVISION_MANIFEST,
    policy,
)


def parents(root, *, verify_members=True):
    scientific = Parent(root, PARENT_PANEL, PARENT_PANEL_MANIFEST)
    revised = Parent(root, PARENT_REVISION, PARENT_REVISION_MANIFEST)
    audited = Parent(root, PARENT_REVISION + "_audits", PARENT_REVISION_AUDIT_MANIFEST)
    if verify_members:
        scientific.verify_all()
        revised.verify_all()
        audited.verify_all()
    frozen = revised.read("stage_freeze.json")
    require(frozen["id"] == OWNER_FREEZE, "eval_surface.exact_finite_owner_freeze")
    gate = revision_stage.validate_admission(root, revised, audited, frozen)
    return scientific, revised, audited, frozen, gate


def wallet_preflight(root):
    """Read-only before any evaluation registration; no ledger constructor."""
    path = safe_path(root, LEDGER)
    with closing(sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)) as db:
        db.execute("PRAGMA query_only=ON")
        db.execute("BEGIN")
        metadata = dict(db.execute("SELECT key,value FROM metadata"))
        tables = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        require(
            not {"eval_registry", "eval_reservations"} & tables
            and budget.PURPOSE_KEY not in metadata,
            "eval_surface.no_prior_evaluation_purpose",
        )
        require("study_fatal" not in metadata, "eval_surface.no_prior_study_stop")
        require(
            metadata["readiness_budget_transition_role"] == "active_successor"
            and json.loads(metadata["policy"])["stage_id"] == OWNER_FREEZE,
            "eval_surface.active_finite_owner",
        )
        prior = db.execute("SELECT COALESCE(SUM(tokens),0) FROM prior_debits").fetchone()[0]
        unp = db.execute(
            "SELECT COUNT(*),COALESCE(SUM(charged_tokens),0),"
            "SUM(CASE WHEN state!='settled' THEN 1 ELSE 0 END) FROM reservations"
        ).fetchone()
        teacher = db.execute("SELECT COUNT(*) FROM teacher_reservations").fetchone()[0]
        sessions = db.execute("SELECT COUNT(*) FROM collection_sessions").fetchone()[0]
        db.execute("ROLLBACK")
    require(
        prior == 221538 and tuple(unp) == (16, 10819, 0) and teacher == sessions == 0,
        "eval_surface.exact_preexisting_232357_no_Teacher",
    )
    return record(
        "evaluation_purpose_preflight",
        ledger_path=LEDGER,
        owner_freeze_id=OWNER_FREEZE,
        prior_debit=prior,
        UNP_requests=unp[0],
        UNP_debit=unp[1],
        inherited_cumulative_debit=prior + unp[1],
        evaluation_requests=0,
        Teacher_requests=teacher,
        Teacher_sessions=sessions,
        read_only=True,
    )


def build_inputs(root):
    entries = overlay.load_entries(root, PARENT_PANEL, PARENT_PANEL_MANIFEST)
    require(
        len(entries) == 900
        and Counter(row["split"] for row in entries) == {"dev": 180, "confirm": 720},
        "eval_surface.exact_original_900_selected_tasks",
    )
    specs, registry, largest = {}, [], 0
    for entry in entries:
        public = overlay.public_object(entry["public_messages"])
        spec = guard.build_spec(public, entry["identity"])
        validate_record(spec, "evaluation_rewrite_spec")
        require(
            guard.render_and_validate(spec["canonical_template"], spec)["passed"],
            "eval_surface.complete_public_canonical_contract",
        )
        for errors in (None, ["e" * 128] * 8):
            _, raw = transport.render(spec["model_contract"], repair_reason=errors)
            largest = max(largest, len(raw) + transport.OVERHEAD)
        specs[entry["task_id"]] = spec
        registry.append(
            {
                "task_id": entry["task_id"],
                "split": entry["split"],
                "identity": entry["identity"],
                "spec_sha256": budget.canonical_sha256(spec),
            }
        )
    return entries, specs, registry, largest


def freeze(root):
    root = Path(root).resolve()
    destination = safe_path(root, OUTPUT)
    require(not destination.exists(), "eval_surface.one_new_freeze")
    credential(root)
    scientific, revised, audited, old_freeze, gate = parents(root)
    before = wallet_preflight(root)
    entries, specs, registry, largest = build_inputs(root)
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    paths = set(readiness_stage.code_paths(root))
    paths.add("trusted_data_synthesis/scripts/audit_qa_vnext_eval_surfaces.py")
    paths.update(
        str(path.relative_to(root))
        for folder in ("trusted_data_synthesis/tests", "raw_financial_data_lake/tests")
        for path in (root / folder).rglob("*.py")
    )
    code = []
    for name in sorted(paths):
        raw = safe_path(root, name).read_bytes()
        require(
            raw == subprocess.check_output(["git", "show", head + ":" + name], cwd=root),
            "eval_surface.committed_complete_dependencies",
        )
        code.append({"path": name, "sha256": sha(root / name)})
    tests = sorted((root / "trusted_data_synthesis/tests").glob("test_qa_vnext_eval_surface_*.py"))
    require(bool(tests), "eval_surface.new_three_domain_contract_tests")
    checked = subprocess.run(
        [
            str(root / "trusted_data_synthesis/.venv/bin/python"),
            "-m",
            "pytest",
            "-q",
            *map(str, tests),
        ],
        cwd=root,
        capture_output=True,
        text=True,
    )
    require(checked.returncode == 0, "eval_surface.all_new_contract_controls_pass")
    require(wallet_preflight(root) == before, "eval_surface.freeze_does_not_consume_wallet")
    frozen = record(
        "evaluation_surface_freeze",
        created_at=readiness_stage.now(),
        git_commit=head,
        rule=policy(),
        budget_policy=budget.policy(),
        transport_policy=transport.policy(),
        code=code,
        software_versions=readiness_stage.software_versions(),
        scientific_parent=scientific.descriptor(),
        finite_parent=revised.descriptor(),
        finite_audits=audited.descriptor(),
        finite_gate_id=gate["id"],
        owner_freeze_id=old_freeze["id"],
        prior_debits=old_freeze["prior_debits"],
        wallet_preflight=before,
        evaluation_registry_sha256=budget.canonical_sha256(registry),
        selected_task_ids=[entry["task_id"] for entry in entries],
        public_spec_sha256={key: budget.canonical_sha256(value) for key, value in specs.items()},
        maximum_public_request_bound=largest,
        canonical_preparation_changed_original_count=sum(
            spec["canonical_preparation_changed_original"] for spec in specs.values()
        ),
        public_quantity_counts=dict(Counter(spec["quantity_kind"] for spec in specs.values())),
        new_test_result={
            "return_code": checked.returncode,
            "stdout": checked.stdout,
            "stderr": checked.stderr,
            "actual_evaluation_requests": 0,
            "tokenizer_loads": 0,
            "GPU_calls": 0,
        },
        prior_template_content_reviewed=True,
        new_evaluation_model_outputs_observed=False,
        Student_arm_outputs_observed=False,
    )
    write_json(destination / "stage_freeze.json", frozen)
    write_json(
        destination / "evaluation_registry.json",
        record(
            "evaluation_rewrite_registry",
            freeze_id=frozen["id"],
            tasks=registry,
            selected_tasks=900,
            original_scientific_task_set_unchanged=True,
        ),
    )
    for task, spec in specs.items():
        write_json(destination / "specs" / (task + ".json"), spec)
    return {
        "freeze_id": frozen["id"],
        "git_commit": head,
        "tasks": 900,
        "maximum_request_bound": largest,
        "tests": checked.stdout,
        "known_common_debit_before": before["inherited_cumulative_debit"],
    }


def check_freeze(root, frozen, *, verify_members=True):
    validate_record(frozen, "evaluation_surface_freeze")
    require(
        frozen["rule"] == policy()
        and frozen["budget_policy"] == budget.policy()
        and frozen["transport_policy"] == transport.policy(),
        "eval_surface.frozen_three_purpose_rules",
    )
    require(
        frozen["software_versions"] == readiness_stage.software_versions(),
        "eval_surface.frozen_software",
    )
    for row in frozen["code"]:
        require(
            sha(safe_path(root, row["path"])) == row["sha256"], "eval_surface.frozen_code_and_tests"
        )
    scientific, revised, audited, old, gate = parents(root, verify_members=verify_members)
    require(
        scientific.descriptor() == frozen["scientific_parent"]
        and revised.descriptor() == frozen["finite_parent"]
        and audited.descriptor() == frozen["finite_audits"]
        and gate["id"] == frozen["finite_gate_id"]
        and old["prior_debits"] == frozen["prior_debits"],
        "eval_surface.exact_scientific_and_budget_parents",
    )
    registry = read(root / OUTPUT / "evaluation_registry.json")
    validate_record(registry, "evaluation_rewrite_registry")
    require(
        registry["freeze_id"] == frozen["id"]
        and budget.canonical_sha256(registry["tasks"]) == frozen["evaluation_registry_sha256"]
        and [row["task_id"] for row in registry["tasks"]] == frozen["selected_task_ids"],
        "eval_surface.frozen_public_task_registry",
    )
    for row in registry["tasks"]:
        spec_path = root / OUTPUT / "specs" / (row["task_id"] + ".json")
        require(
            sha(spec_path) == row["spec_sha256"] == frozen["public_spec_sha256"][row["task_id"]],
            "eval_surface.frozen_public_specs",
        )
    return registry["tasks"]


def open_ledger(root, frozen):
    return budget.EvaluationLedger(
        root / LEDGER, OWNER_FREEZE, frozen["prior_debits"], eval_freeze_id=frozen["id"]
    )


def repair_codes(errors):
    codes = list(
        dict.fromkeys(
            code
            for code in errors
            if isinstance(code, str) and re.fullmatch(r"[A-Za-z][A-Za-z0-9_.:-]{0,127}", code)
        )
    )
    return codes[:8] or ["evaluation.semantic_contract"]


def select_wording(spec, requester, *, stopped=lambda: False):
    """First semantic-valid response candidate terminates, including unchanged.

    The requester alone owns transport/billing. This selector never retries a
    transport failure and never consults any private reference or model score.
    """
    requests, variants = [], []
    reason = None
    base = {
        "category": "canonical_fallback",
        "requests": requests,
        "variant_checks": variants,
        "selected_variant_index": None,
        "selected_request_id": None,
        "selected_candidate_applied_to_final": False,
        "rendered": None,
        "global_fatal": False,
        "terminal": "no_semantic_valid_candidate",
    }
    for attempt in (1, 2):
        if stopped():
            return {**base, "global_fatal": True, "terminal": "not_requested_after_global_stop"}
        try:
            returned = requester(repair_reason=reason)
        except transport.EvaluationTransportError as error:
            requests.append(
                {
                    "request_id": error.request_id,
                    "attempt": attempt,
                    "receipt": error.receipt,
                    "transport_failed": True,
                }
            )
            return {
                **base,
                "global_fatal": error.global_fatal,
                "terminal": "transport_failure_no_retry",
            }
        except BudgetRejected as error:
            return {
                **base,
                "global_fatal": True,
                "terminal": "registered_budget_or_contract_stop",
                "reason": str(error),
            }
        requests.append(
            {
                "request_id": returned["request_id"],
                "attempt": attempt,
                "receipt": returned["receipt"],
                "transport_failed": False,
            }
        )
        errors = []
        for index, candidate in enumerate(returned["candidates"]):
            template = candidate["question_template"]
            checked = guard.render_and_validate(template, spec)
            variants.append(
                {
                    "request_id": returned["request_id"],
                    "attempt": attempt,
                    "variant_index": index,
                    "question_template": template,
                    "semantic_valid": checked["passed"],
                    "errors": checked["errors"],
                }
            )
            if checked["passed"]:
                category = checked["change_classification"]["category"]
                require(
                    category in {"accepted_true_rewrite", "unchanged_or_format_only"},
                    "eval_surface.registered_wording_classification",
                )
                return {
                    **base,
                    "category": category,
                    "rendered": checked,
                    "selected_variant_index": index,
                    "selected_request_id": returned["request_id"],
                    "selected_candidate_applied_to_final": category == "accepted_true_rewrite",
                    "terminal": "first_semantic_valid_candidate",
                }
            errors.extend(checked["errors"])
        reason = (
            ["evaluation.response_structure"]
            if returned.get("structure_errors")
            else repair_codes(errors)
        )
    return base


def run(root):
    root = Path(root).resolve()
    output = safe_path(root, OUTPUT)
    frozen = read(output / "stage_freeze.json")
    registry = check_freeze(root, frozen)
    require(not (output / "run_started.json").exists(), "eval_surface.one_bounded_execution")
    require(
        wallet_preflight(root) == frozen["wallet_preflight"],
        "eval_surface.pre_send_wallet_unchanged",
    )
    entries = overlay.load_entries(root, PARENT_PANEL, PARENT_PANEL_MANIFEST)
    require(
        [entry["task_id"] for entry in entries] == frozen["selected_task_ids"],
        "eval_surface.original_order_before_outputs",
    )
    key = credential(root)
    bank = open_ledger(root, frozen)
    stop = threading.Event()
    write_json(
        output / "run_started.json",
        record(
            "evaluation_surface_run_start",
            at=readiness_stage.now(),
            freeze_id=frozen["id"],
            new_scientific_tasks=0,
            selected_tasks=900,
        ),
    )
    registered = bank.register_evaluation(
        registry, policy_id=policy()["id"], parent_panel_manifest_id=PARENT_PANEL_MANIFEST
    )
    write_json(output / "budget_registration.json", registered)
    write_json(output / "budget_initial.json", bank.snapshot())
    failures, results = [], []

    def one(entry):
        spec = read(output / "specs" / (entry["task_id"] + ".json"))
        try:
            if stop.is_set():
                selected = {
                    "category": "canonical_fallback",
                    "requests": [],
                    "variant_checks": [],
                    "selected_variant_index": None,
                    "selected_request_id": None,
                    "selected_candidate_applied_to_final": False,
                    "rendered": None,
                    "terminal": "not_requested_after_global_stop",
                    "global_fatal": True,
                }
            else:
                provider = transport.EvaluationProvider(entry["identity"], spec, bank, output, key)
                selected = select_wording(spec, provider.request, stopped=stop.is_set)
        except Exception as error:
            stop.set()
            bank.halt("evaluation_surface_integrity_failure:" + type(error).__name__)
            selected = {
                "category": "canonical_fallback",
                "requests": [],
                "variant_checks": [],
                "selected_variant_index": None,
                "selected_request_id": None,
                "selected_candidate_applied_to_final": False,
                "rendered": None,
                "terminal": "execution_integrity_failure",
                "global_fatal": True,
                "error": str(error).replace(key, "[REDACTED]"),
                "error_type": type(error).__name__,
            }
        if selected["global_fatal"]:
            stop.set()
            bank.halt("evaluation_surface_stopped:" + selected["terminal"])
        requests = []
        for request in selected["requests"]:
            identifier = request["request_id"]
            directory = output / "evaluation_requests" / identifier
            receipt_path = directory / "receipt.json"
            if not receipt_path.exists():
                receipt_path = directory / "failure.json"
            requests.append(
                {
                    **request,
                    "receipt_id": request["receipt"]["id"],
                    "receipt_path": str(receipt_path.relative_to(root))
                    if receipt_path.exists()
                    else None,
                }
            )
        evidence = {
            key: value for key, value in selected.items() if key not in {"rendered", "requests"}
        }
        evidence.update(
            requests=requests,
            spec_id=spec["id"],
            spec_sha256=budget.canonical_sha256(spec),
            canonical_preparation_changed_original=spec["canonical_preparation_changed_original"],
            first_semantic_valid_candidate_terminates=True,
            no_later_variant_or_repair_for_unchanged=True,
            local_preparation_counted_as_LLM_rewrite=False,
        )
        item = overlay.write_surface(
            root,
            output,
            entry,
            rendered=selected["rendered"],
            evidence=evidence,
            freeze_id=frozen["id"],
        )
        return item, {
            "task_id": entry["task_id"],
            "split": entry["split"],
            "category": selected["category"],
            "terminal": selected["terminal"],
            "request_count": len(requests),
            "global_fatal": selected["global_fatal"],
            "evaluated_variants": len(selected["variant_checks"]),
            "rejected_variants": sum(
                not row["semantic_valid"] for row in selected["variant_checks"]
            ),
        }

    with rewrite_guard() as counters, ThreadPoolExecutor(max_workers=8) as executor:
        pending = {executor.submit(one, entry): entry for entry in entries}
        try:
            for future in as_completed(pending):
                entry = pending[future]
                try:
                    results.append(future.result())
                except Exception as error:
                    stop.set()
                    bank.halt("evaluation_surface_storage_or_integrity_failure")
                    failures.append(
                        {
                            "task_id": entry["task_id"],
                            "error_type": type(error).__name__,
                            "reason": str(error).replace(key, "[REDACTED]"),
                        }
                    )
                if len(results) and len(results) % 100 == 0:
                    snapshot = bank.snapshot()
                    print(
                        json.dumps(
                            {
                                "phase": "evaluation_surface",
                                "recorded_tasks": len(results),
                                "requests": snapshot["eval_sent_request_count"],
                                "evaluation_debit": snapshot["eval_conservative_charged_tokens"],
                                "study_stopped": bool(snapshot["persisted_study_stop"]),
                            }
                        ),
                        flush=True,
                    )
        except BaseException:
            stop.set()
            bank.halt("evaluation_surface_interrupted")
            raise
    write_json(output / "execution_guards.json", record("evaluation_surface_guards", **counters))
    require(not any(counters["forbidden"].values()), "eval_surface.no_unregistered_execution")
    rank = {entry["task_id"]: index for index, entry in enumerate(entries)}
    results.sort(key=lambda pair: rank[pair[0]["task_id"]])
    items = [pair[0] for pair in results]
    outcomes = [pair[1] for pair in results]
    write_json(
        output / "task_outcomes.json",
        record(
            "evaluation_surface_outcomes",
            freeze_id=frozen["id"],
            rows=outcomes,
            original_registered_denominator=900,
        ),
    )
    write_json(output / "execution_failures.json", failures)
    public = offline = None
    if len(items) == 900 and not failures:
        public, offline = overlay.write_catalog(
            root, output, entries, items, freeze_id=frozen["id"]
        )
    finalization = None
    if public is not None and not stop.is_set():
        finalization = bank.finalize_evaluation(
            public["id"], [entry["task_id"] for entry in entries]
        )
        write_json(output / "evaluation_finalization.json", finalization)
    final_budget = bank.snapshot()
    write_json(output / "budget_final.json", final_budget)
    complete = (
        len(items) == 900
        and not failures
        and not stop.is_set()
        and final_budget["persisted_study_stop"] is None
        and finalization is not None
    )
    report = record(
        "evaluation_surface_report",
        status="BOUNDED_SURFACES_EXECUTED_AUDIT_REQUIRED"
        if complete
        else "INCOMPLETE_EVALUATION_SURFACE_STOP",
        freeze_id=frozen["id"],
        selected_scientific_tasks=900,
        recorded_tasks=len(items),
        new_scientific_tasks=0,
        public_catalog_id=public["id"] if public else None,
        offline_catalog_id=offline["id"] if offline else None,
        category_counts=dict(Counter(row["category"] for row in outcomes)),
        split_category_counts={
            split: dict(Counter(row["category"] for row in outcomes if row["split"] == split))
            for split in ("dev", "confirm")
        },
        complete_fixed_wording_pass=complete,
        all_original_tasks_retained=len(items) == 900,
        evaluation_finalization_id=finalization["id"] if finalization else None,
        request_reservations=final_budget["eval_request_reservations"],
        sent_requests=final_budget["eval_sent_request_count"],
        evaluation_charged_tokens=final_budget["eval_conservative_charged_tokens"],
        cumulative_conservative_debit=final_budget["cumulative_conservative_debit"],
        model_identity_counts=dict(
            Counter(
                row["response_model"]
                for row in final_budget["eval_reservations"]
                if row["response_model"] is not None
            )
        ),
        tasks_without_request=sum(row["request_count"] == 0 for row in outcomes),
        evaluated_candidate_variants=sum(row["evaluated_variants"] for row in outcomes),
        rejected_candidate_variants=sum(row["rejected_variants"] for row in outcomes),
        canonical_preparation_changed_original_count=frozen[
            "canonical_preparation_changed_original_count"
        ],
        canonical_preparation_is_LLM_rewrite=False,
        exact_original_fallback_public_bytes=True,
        all_arms_seeds_pools_share_final_version=True,
        old_template_full_Student_panel_added=False,
        Teacher_sessions=0,
        Student_runs=0,
        GPU_runs=0,
        tokenizer_loads=0,
        source_acquisitions=0,
        QA_builds_created=0,
        explicit_operation_contract_retained=True,
        natural_language_generalization_measured=False,
    )
    write_json(output / "report.json", report)
    check_freeze(root, frozen)
    write_json(
        output / "run_completed.json",
        record(
            "evaluation_surface_run_completed",
            at=readiness_stage.now(),
            report_id=report["id"],
            bounded_pass_complete=complete,
        ),
    )
    manifest = seal(
        output,
        scope="one public-only wording overlay over the same 900 scientific targets",
        runtime_wallet_excluded=LEDGER,
        no_source_or_QA_rebuild=True,
    )
    return {
        "manifest_id": manifest["id"],
        "status": report["status"],
        "categories": report["category_counts"],
        "requests": report["sent_requests"],
        "new_debit": report["evaluation_charged_tokens"],
        "cumulative_debit": report["cumulative_conservative_debit"],
    }


def verify(root):
    root = Path(root).resolve()
    frozen = read(root / OUTPUT / "stage_freeze.json")
    check_freeze(root, frozen)
    parent = Parent(root, OUTPUT)
    parent.verify_all()
    require("run_completed.json" in parent.members, "eval_surface.actual_run_terminated")
    public = overlay.PublicOverlay(root, OUTPUT, parent.manifest["id"])
    require(len(public.tasks) == 900, "eval_surface.one_final_surface_per_original_task")
    return {
        "manifest_id": parent.manifest["id"],
        "members": len(parent.members),
        "scientific_tasks": 900,
        "structural_verification_is_not_surface_semantic_audit": True,
    }


def surface_admission_checks(prep, audit, snapshot, frozen):
    closure = snapshot.get("evaluation_finalization") or {}
    return {
        "same_900_scientific_tasks": prep["all_original_tasks_retained"]
        and prep["recorded_tasks"] == 900
        and prep["new_scientific_tasks"] == 0,
        "bounded_wording_pass_complete": prep["complete_fixed_wording_pass"],
        "independent_saved_surface_semantics_passed": audit["status"] == "passed",
        "no_shared_budget_or_model_stop": snapshot["persisted_study_stop"] is None,
        "evaluation_rewrite_purpose_permanently_closed": (
            closure.get("id") == prep["evaluation_finalization_id"]
            and closure.get("eval_freeze_id") == frozen["id"]
            and closure.get("owner_stage_id") == OWNER_FREEZE
            and closure.get("public_catalog_id") == prep["public_catalog_id"]
            and closure.get("completed_task_count") == 900
            and closure.get("outcome_task_ids") == sorted(frozen["selected_task_ids"])
            and closure.get("remaining_evaluation_attempts_permanently_closed") is True
            and closure.get("other_purposes_closed") is False
        ),
        "unified_surface_before_Student": prep["Student_runs"] == 0
        and prep["all_arms_seeds_pools_share_final_version"],
    }


def surface_gate(parent, audit, snapshot, frozen):
    prep = parent.read("report.json")
    checks = surface_admission_checks(prep, audit, snapshot, frozen)
    return record(
        "evaluation_surface_admission",
        status="READY_FOR_UNIFIED_EVALUATION_INPUT"
        if all(checks.values())
        else "BLOCKED_EVALUATION_SURFACE_INPUT",
        **checks,
        failed_gates=[key for key, value in checks.items() if not value],
        freeze_id=frozen["id"],
        surface_manifest_id=parent.manifest["id"],
        report_id=prep["id"],
        audit_id=audit["id"],
        finite_gate_id=frozen["finite_gate_id"],
        scientific_tasks=900,
        extra_template_Student_evaluation_registered=False,
        natural_language_understanding_generalization_established=False,
    )


def validate_surface_admission(root):
    frozen = read(root / OUTPUT / "stage_freeze.json")
    check_freeze(root, frozen)
    parent, audited = Parent(root, OUTPUT), Parent(root, AUDITS)
    parent.verify_all()
    audited.verify_all()
    audit = audited.read("surfaces.json")
    validate_record(audit, "evaluation_surface_independent_audit")
    filename = "trusted_data_synthesis/scripts/audit_qa_vnext_eval_surfaces.py"
    expected = next(row for row in frozen["code"] if row["path"] == filename)
    require(
        audit["script"] == Path(filename).name
        and audit["script_sha256"] == expected["sha256"]
        and audit["surface_manifest_id"] == parent.manifest["id"],
        "eval_surface.frozen_independent_saved_surface_audit",
    )
    bank = open_ledger(root, frozen)
    snapshot = bank.snapshot()
    closure = parent.read("evaluation_finalization.json")
    validate_record(closure, "evaluation_rewrite_finalization")
    require(
        closure == snapshot["evaluation_finalization"],
        "eval_surface.closed_purpose_original_record",
    )
    gate = audited.read("admission_gate.json")
    require(
        gate == surface_gate(parent, audit, snapshot, frozen)
        and gate["status"] == "READY_FOR_UNIFIED_EVALUATION_INPUT"
        and gate["failed_gates"] == [],
        "eval_surface.all_surface_gates_recomputed_before_use",
    )
    return frozen, parent, gate, bank


def audit_and_admit(root):
    root = Path(root).resolve()
    frozen = read(root / OUTPUT / "stage_freeze.json")
    check_freeze(root, frozen)
    parent = Parent(root, OUTPUT)
    parent.verify_all()
    require(not safe_path(root, AUDITS).exists(), "eval_surface.one_saved_surface_audit")
    filename = "audit_qa_vnext_eval_surfaces.py"
    try:
        result = readiness_stage.load_script(root, filename).verify(root, OUTPUT)
    except Exception as error:
        result = {
            "status": "AUDIT_ERROR",
            "error_type": type(error).__name__,
            "reason": str(error),
            "failed_saved_surfaces_not_repaired_or_replaced": True,
        }
    audit = record(
        "evaluation_surface_independent_audit",
        surface_manifest_id=parent.manifest["id"],
        script=filename,
        script_sha256=sha(root / "trusted_data_synthesis/scripts" / filename),
        result=result,
        status=result["status"],
    )
    write_json(root / AUDITS / "surfaces.json", audit)
    bank = open_ledger(root, frozen)
    snapshot = bank.snapshot()
    gate = surface_gate(parent, audit, snapshot, frozen)
    write_json(root / AUDITS / "admission_gate.json", gate)
    seal(
        root / AUDITS,
        scope="independent saved-wording audit and shared final evaluation input gate",
    )
    return {
        "id": gate["id"],
        "status": gate["status"],
        "failed_gates": gate["failed_gates"],
        "audit_status": audit["status"],
    }


def collect(root):
    """Reuse the fixed 255 training catalog, never register 900 evaluation tasks."""
    root = Path(root).resolve()
    frozen, surface, surface_admission, bank = validate_surface_admission(root)
    _, revised, _, _, finite_admission = parents(root)
    destination = safe_path(root, FIXED_COLLECTION)
    require(not destination.exists(), "eval_surface.single_full_AB_batch_no_pilot")
    catalog, public = revised.read("catalog.json"), revised.read("public_catalog.json")
    online = PublicCatalog(root, PARENT_REVISION + "/public_catalog.json", public["id"])
    offline = OfflineCatalog(root, PARENT_REVISION + "/catalog.json", catalog["id"])
    require(len(online.tasks) == 255, "eval_surface.fixed_255_training_candidates")
    bank.register_collection(
        list(online.tasks.values()), gate_id=finite_admission["id"], gate=finite_admission
    )
    key = credential(root)
    requests = destination / "requests"
    from ..finance_qa_vnext_task_panel.guards import execution_guard

    with execution_guard(online=True) as counters:
        report = collection.run(
            root,
            destination,
            bank,
            online,
            offline,
            lambda row: TeacherProvider(bank, row["session_id"], requests, key),
            gate_id=finite_admission["id"],
            workers=8,
            receipt_verifier=lambda session, current: verify_receipts(session, current, requests),
        )
    write_json(
        destination / "execution_guards.json", record("fixed_collection_guards", counts=counters)
    )
    write_json(
        destination / "evaluation_input_binding.json",
        record(
            "fixed_evaluation_input_binding",
            evaluation_surface_parent=surface.descriptor(),
            surface_gate_id=surface_admission["id"],
            surface_freeze_id=frozen["id"],
            same_900_targets=True,
            all_Student_arms_seeds_pools_share_version=True,
            additional_template_evaluations=0,
        ),
    )
    seal(
        destination, scope="complete or stopped full fixed A/B collection with three-purpose budget"
    )
    return {
        key: report[key]
        for key in (
            "id",
            "status",
            "registered_session_count",
            "recorded_session_count",
            "finished_session_count",
            "financially_valid_sessions",
            "representation_eligible_sessions",
        )
    }


def materialize(root):
    root = Path(root).resolve()
    _, surface, surface_admission, bank = validate_surface_admission(root)
    _, revised, _, _, _ = parents(root)
    collected = Parent(root, FIXED_COLLECTION)
    collected.verify_all()
    report = collected.read("report.json")
    require(report["collection_complete"], "eval_surface.no_materials_from_partial_fixed_batch")
    binding = collected.read("evaluation_input_binding.json")
    require(
        binding["evaluation_surface_parent"] == surface.descriptor()
        and binding["surface_gate_id"] == surface_admission["id"],
        "eval_surface.same_frozen_Student_input_for_material_study",
    )
    public = revised.read("public_catalog.json")
    online = PublicCatalog(root, PARENT_REVISION + "/public_catalog.json", public["id"])
    destination = safe_path(root, FIXED_COLLECTION + "_materials")
    from ..finance_qa_vnext_task_panel.guards import execution_guard

    with execution_guard(online=False) as counters:
        result = materials.run(
            root,
            destination,
            root / FIXED_COLLECTION,
            list(online.tasks.values()),
            expected_collection_id=report["id"],
            ledger=bank,
            receipt_verifier=lambda session, current: verify_receipts(
                session, current, root / FIXED_COLLECTION / "requests"
            ),
        )
    write_json(
        destination / "execution_guards.json", record("fixed_material_guards", counts=counters)
    )
    seal(destination, scope="original full fixed A/B materials; no Student training performed")
    return {
        "id": result["id"],
        "status": result["status"],
        "population_selection": result["population_selection"],
        "tokenizer_loads": result["tokenizer_loads"],
        "training_started": False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "phase", choices=("freeze", "run", "verify", "admit", "collect", "materialize")
    )
    parser.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    result = {
        "freeze": freeze,
        "run": run,
        "verify": verify,
        "admit": audit_and_admit,
        "collect": collect,
        "materialize": materialize,
    }[args.phase](args.root)
    print(json.dumps(result, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
