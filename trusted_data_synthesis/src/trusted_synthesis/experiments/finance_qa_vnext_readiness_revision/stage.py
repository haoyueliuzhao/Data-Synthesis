"""Freeze, execute the two bounded repairs, and admit an inherited fixed study."""

import argparse
import json
import subprocess
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from ..finance_qa_vnext_catalog_bridge.catalog import (
    OfflineCatalog,
    Parent,
    PublicCatalog,
    compose,
    read,
    safe_path,
)
from ..finance_qa_vnext_catalog_bridge.stage import seal
from ..finance_qa_vnext_eval_readiness import (
    collection,
    materials,
    source_policy,
    training_increment,
)
from ..finance_qa_vnext_eval_readiness import stage as prior_stage
from ..finance_qa_vnext_eval_readiness.budget import ResearchLedger
from ..finance_qa_vnext_eval_readiness.runtime import record as evaluation_record
from ..finance_qa_vnext_eval_readiness.transport import Provider, verify_receipts
from ..finance_qa_vnext_surface_build.guards import rewrite_guard
from ..finance_qa_vnext_surface_build.transport import credential
from ..finance_qa_vnext_task_build.archive import record, require, sha, validate_record, write_json
from ..qa_reasoning_share_training_preflight import tokenization as assets
from . import budget_transition, provenance, reassessment
from .protocol import (
    AUDIT_ATTACHMENT,
    AUDITS,
    COLLECTION,
    OUTPUT,
    PARENT,
    PARENT_WORK,
    WORK,
    policy,
)


def freeze(root):
    root = Path(root).resolve()
    output = safe_path(root, OUTPUT)
    require(not output.exists(), "revision.one_new_freeze")
    require(not safe_path(root, WORK).exists(), "revision.no_preexisting_successor_runtime")
    credential(root)
    prepared, audited, old = provenance.parents(root)
    compatibility = provenance.check_original_code(root, old)
    prior_stage.verify_old_public_bytes(root)
    source_policy.validate_metadata(root, old["training_source_metadata"])
    for row in [*old["source_files"], *old["prior_debits"]]:
        require(sha(safe_path(root, row["path"])) == row["sha256"], "revision.original_inputs")
    assets._read_members(assets.MODEL_DIRECTORY)
    for row in old["tokenizer_assets"]:
        require(sha(row["absolute_path"]) == row["sha256"], "revision.original_tokenizer_assets")
    require(
        prior_stage.software_versions() == old["software_versions"],
        "revision.inherited_runtime_versions",
    )
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    paths = sorted(
        set(prior_stage.code_paths(root))
        | {
            str(path.relative_to(root))
            for directory in ("trusted_data_synthesis/tests", "raw_financial_data_lake/tests")
            for path in (root / directory).rglob("*.py")
        }
    )
    code = []
    for relative in paths:
        committed = subprocess.check_output(["git", "show", head + ":" + relative], cwd=root)
        require(
            committed == safe_path(root, relative).read_bytes(), "revision.committed_code_tests"
        )
        code.append({"path": relative, "sha256": sha(root / relative)})
    tests = sorted(
        (root / "trusted_data_synthesis/tests").glob("test_qa_vnext_readiness_revision_*.py")
    )
    require(bool(tests), "revision.new_consumer_contract_tests_present")
    checked = subprocess.run(
        [
            str(root / "trusted_data_synthesis/.venv/bin/python"),
            "-m",
            "pytest",
            "-q",
            *[str(path) for path in tests],
        ],
        cwd=root,
        capture_output=True,
        text=True,
    )
    require(checked.returncode == 0, "revision.new_contract_controls_passed")
    # Predecessor inspection/handoff is explicitly separate from immutable scientific files.
    predecessor = budget_transition.inspect_predecessor(
        root / PARENT_WORK / "rewrite_and_Teacher_budget.sqlite3",
        expected_stage_id=old["id"],
        prior_debits=old["prior_debits"],
    )
    frozen = record(
        "readiness_revision_freeze",
        created_at=prior_stage.now(),
        git_commit=head,
        rule=policy(),
        code=code,
        parent_preparation=prepared.descriptor(),
        parent_audits=audited.descriptor(),
        parent_freeze_id=old["id"],
        compatibility=compatibility,
        source_files=old["source_files"],
        prior_debits=old["prior_debits"],
        training_source_metadata=old["training_source_metadata"],
        tokenizer_assets=old["tokenizer_assets"],
        software_versions=old["software_versions"],
        predecessor_budget=predecessor,
        inherited_transport_and_consumer_control_evidence={
            "parent_freeze_id": old["id"],
            "new_test_result": old["new_test_result"],
            "unchanged_implementation_verified": True,
        },
        new_test_result={
            "return_code": checked.returncode,
            "stdout": checked.stdout,
            "stderr": checked.stderr,
            "live_API_calls": 0,
            "tokenizer_loads": 0,
        },
        audit_attachment_sha256=sha(AUDIT_ATTACHMENT),
        known_prior_failures_used_for_implementation=True,
        revised_UNP_numeric_admission_outputs_observed=False,
        revised_fixed_70_qualification_outputs_observed=False,
        new_Teacher_outputs_observed=False,
    )
    write_json(output / "stage_freeze.json", frozen)
    return {
        "freeze_id": frozen["id"],
        "git_commit": head,
        "tests": checked.stdout,
        "prior_common_debit": 221538,
    }


def check_freeze(root, frozen, *, verify_parent_members=False):
    root = Path(root).resolve()
    validate_record(frozen, "readiness_revision_freeze")
    require(frozen["rule"] == policy(), "revision.exact_frozen_rules")
    require(
        frozen["software_versions"] == prior_stage.software_versions(), "revision.software_pins"
    )
    for row in [*frozen["code"], *frozen["source_files"], *frozen["prior_debits"]]:
        require(sha(safe_path(root, row["path"])) == row["sha256"], "revision.frozen_code_inputs")
    for row in frozen["tokenizer_assets"]:
        require(sha(row["absolute_path"]) == row["sha256"], "revision.frozen_tokenizer")
    prepared, audited, old = provenance.parents(root, verify_members=verify_parent_members)
    require(
        prepared.descriptor() == frozen["parent_preparation"]
        and audited.descriptor() == frozen["parent_audits"]
        and old["id"] == frozen["parent_freeze_id"],
        "revision.exact_parent_freeze_chain",
    )
    require(
        provenance.check_original_code(root, old) == frozen["compatibility"],
        "revision.same_bounded_code_compatibility",
    )
    require(
        old["training_source_metadata"] == frozen["training_source_metadata"]
        and old["prior_debits"] == frozen["prior_debits"],
        "revision.no_source_or_budget_reset",
    )
    return prepared, audited, old


def ledger(root, frozen):
    check_budget_owner(root, frozen)
    return ResearchLedger(
        root / WORK / "rewrite_and_Teacher_budget.sqlite3",
        frozen["id"],
        prior_debits=frozen["prior_debits"],
    )


def check_budget_owner(root, frozen):
    transition = read(root / OUTPUT / "budget_transition.json")
    require(
        transition["predecessor"] == frozen["predecessor_budget"]
        and transition["old_stage_id"] == frozen["parent_freeze_id"],
        "revision.frozen_predecessor_transition_join",
    )
    return budget_transition.check_transition(
        root / PARENT_WORK / "rewrite_and_Teacher_budget.sqlite3",
        root / WORK / "rewrite_and_Teacher_budget.sqlite3",
        transition,
        frozen["id"],
        frozen["prior_debits"],
    )


def prepare(root):
    root = Path(root).resolve()
    output = safe_path(root, OUTPUT)
    frozen = read(output / "stage_freeze.json")
    parent, _, old = check_freeze(root, frozen, verify_parent_members=True)
    require(not (output / "run_started.json").exists(), "revision.single_bounded_execution")
    key = credential(root)
    write_json(
        output / "run_started.json",
        record("readiness_revision_run_start", at=prior_stage.now(), freeze_id=frozen["id"]),
    )
    try:
        transition = budget_transition.migrate(
            root / PARENT_WORK / "rewrite_and_Teacher_budget.sqlite3",
            root / WORK / "rewrite_and_Teacher_budget.sqlite3",
            expected_stage_id=old["id"],
            new_stage_id=frozen["id"],
            prior_debits=frozen["prior_debits"],
            expected_predecessor=frozen["predecessor_budget"],
        )
        write_json(output / "budget_transition.json", transition)
        bank = ledger(root, frozen)
        with rewrite_guard() as guards, ThreadPoolExecutor(max_workers=2) as pool:
            future = pool.submit(
                reassessment.run,
                root,
                output / "controls",
                PARENT,
                expected_parent_manifest_id=parent.manifest["id"],
                freeze_id=frozen["id"],
            )
            increment = training_increment.run(
                root,
                output / "incremental",
                WORK + "/train",
                frozen,
                bank,
                key,
            )
            parents = [
                Parent(root, x["directory"], x["manifest_id"])
                for x in prior_stage.old_parent(root).read("catalog.json")["parents"]
            ]
            parents.append(Parent(root, OUTPUT + "/incremental"))
            full, public = compose(root, output, parents, frozen["id"])
            require(
                full["tasks"][:243] == prior_stage.old_parent(root).read("catalog.json")["tasks"],
                "revision.exact_original_243_catalog_entries",
            )
            qualification = future.result()
        require(not any(guards["forbidden"].values()), "revision.no_unregistered_execution")
        write_json(output / "execution_guards.json", record("readiness_revision_guards", **guards))
        counts = Counter(row["family"] for row in full["tasks"])
        ceiling = 5 * min(
            40,
            counts["stock_rollforward"],
            counts["annual_flow"],
            counts["company_defined_metric"],
            counts["control"] // 2,
        )
        prior_report = parent.read("report.json")
        report = record(
            "readiness_revision_report",
            status="FINITE_REVISION_EXECUTED_AUDIT_REQUIRED",
            freeze_id=frozen["id"],
            parent_preparation=parent.descriptor(),
            catalog_id=full["id"],
            public_catalog_id=public["id"],
            training_candidates=len(full["tasks"]),
            new_training_candidates=increment["tasks"],
            family_counts=dict(counts),
            balanced_reference_supply_ceiling=ceiling,
            all_new_registered_targets_retained=increment["all_registered_tasks_retained"],
            evaluation_tasks=prior_report["evaluation_tasks"],
            panel_quota_complete=prior_report["panel_quota_complete"],
            evaluation_panel_rebuilds=0,
            old_243_public_bytes_preserved=True,
            old_control_sessions_rewritten=False,
            qualification=qualification,
            budget_transition_id=transition["id"],
            budget_owner=check_budget_owner(root, frozen),
            budget=bank.snapshot(),
            Teacher_sessions=0,
            Student_runs=0,
            GPU_runs=0,
            formal_collection_started=False,
            training_population_selected=False,
        )
        write_json(output / "report.json", report)
        check_freeze(root, frozen, verify_parent_members=True)
        prior_stage.verify_old_public_bytes(root)
        write_json(
            output / "run_completed.json",
            record(
                "readiness_revision_run_completed", at=prior_stage.now(), report_id=report["id"]
            ),
        )
    except BaseException as error:
        write_json(
            output / "run_failed.json",
            record(
                "readiness_revision_run_failed",
                at=prior_stage.now(),
                reason=str(error).replace(key, "[REDACTED]"),
                error_type=type(error).__name__,
                no_automatic_replay=True,
                original_parents_and_failed_new_outputs_preserved=True,
            ),
        )
        seal(output, status="failed", runtime_databases_excluded=WORK)
        raise
    manifest = seal(
        output,
        scope="two-consumer finite revision; unchanged scientific parent references",
        runtime_databases_excluded=WORK,
        panel_rebuilds=0,
        old_rows_reencoded=0,
    )
    return {
        "manifest_id": manifest["id"],
        "training_candidates": report["training_candidates"],
        "new_training_candidates": report["new_training_candidates"],
        "qualification": {
            k: qualification[k]
            for k in ("status", "control_count", "passed_count", "financial_valid_count")
        },
    }


def inherited_panel_audit(parent, audited):
    original = audited.read("panels.json")
    return record(
        "readiness_inherited_panel_audit",
        status=original["status"],
        parent_preparation=parent.descriptor(),
        parent_audits=audited.descriptor(),
        original_audit_id=original["id"],
        original_audit_sha256=audited.members["panels.json"]["sha256"],
        original_production_manifest_id=original["stage_manifest_id"],
        selected_tasks=900,
        compiled_overflow=48,
        original_audit_rerun=False,
        original_member_hashes_verified=True,
        no_panel_or_period_reconstruction=True,
    )


def admission_checks(prep, observed, frozen):
    q = prep["qualification"]
    inherited, added, combined = q["inherited_CPU"], q["incremental_CPU"], q["token_combined"]
    n_new = added["financial_complete_packages"]
    cpu_ok = (
        inherited["verified"] is True
        and inherited["packages"] == 39
        and inherited["rows"] == 253
        and inherited["target_tokens"] == 13642
        and 0 <= n_new <= 15
        and added["status"]
        == ("PASS_SCRIPTED_REPRESENTATION_ONLY" if n_new else "NO_FINANCIAL_COMPLETE_PACKAGES")
        and added["tokenizer_constructions"] == (1 if n_new else 0)
        and combined["all_current_qualified_covered"] is True
        and combined["financial_complete_packages"] == q["financial_valid_count"] == 39 + n_new
        and combined["inherited_rows"] == 253
        and combined["new_rows"] == added["rows"]
        and combined["maxseq"] == 24576
        and combined["truncation"] is False
        and combined["old_rows_reencoded"] == 0
    )
    test_ok = (
        frozen["new_test_result"]["return_code"] == 0
        and frozen["inherited_transport_and_consumer_control_evidence"]["new_test_result"][
            "return_code"
        ]
        == 0
        and frozen["inherited_transport_and_consumer_control_evidence"][
            "unchanged_implementation_verified"
        ]
        is True
    )
    return {
        "panel_quota_complete": prep["evaluation_tasks"] == 900
        and prep["panel_quota_complete"] is True
        and prep["evaluation_panel_rebuilds"] == 0,
        "actual_period_semantics_passed": observed["panels"]["status"] == "PASS_AS_SCOPED",
        "increment_source_semantics_passed": observed["increment"]["status"] == "passed",
        "complete_trajectory_qualification_passed": (
            q["status"] == "PASS"
            and q["control_count"] == q["passed_count"] == 70
            and q["prior_positive_regressions"] == []
            and q["prior_negative_regressions"] == []
            and q["prior_15_reached_support_assessment"] == 15
            and q["financial_valid_count"] == 54
            and test_ok
        ),
        "new_original_CPU_representation_passed": cpu_ok,
        "training_catalog_locked": (
            prep["balanced_reference_supply_ceiling"] >= 180
            and prep["all_new_registered_targets_retained"] is True
            and prep["old_243_public_bytes_preserved"] is True
        ),
        "live_transport_controls_passed": test_ok,
        "original_package_consumer_registered": test_ok and callable(materials.update_examples),
    }


def verify_control_evidence(root, prepared):
    prep = prepared.read("report.json")
    qualification = prepared.read("controls/report.json")
    require(qualification == prep["qualification"], "revision.actual_qualification_report_join")
    parent, _, _ = provenance.parents(root, verify_members=False)
    row_path = str(Path(qualification["reassessments_path"]).relative_to(prepared.relative))
    require(
        prepared.members[row_path]["sha256"] == qualification["reassessments_sha256"],
        "revision.saved_reassessment_rows_hash",
    )
    saved = prepared.read(row_path)
    validate_record(saved, "fixed_control_reassessment_rows")
    original = parent.read("controls/source_bound_report.json")
    previous = {row["name"]: row for row in original["controls"]}
    rows = saved["rows"]
    require(
        len(rows) == len(previous) == 70 and {row["name"] for row in rows} == set(previous),
        "revision.exact_original_control_denominator_and_names",
    )
    passed = valid = reached = 0
    for row in rows:
        validate_record(row, "fixed_control_reassessment")
        old = previous[row["name"]]
        require(
            row["original_session_id"] == old["session"]["id"]
            and row["original_assessment_id"] == old["assessment"]["id"]
            and row["expected_financial_valid"] == old["expected_financial_valid"]
            and row["expected_full_mapping_status"] == old["expected_full_mapping_status"],
            "revision.original_expectations_and_session_parents",
        )
        current = row["reassessment"]
        if current is not None:
            require(
                current
                == evaluation_record(
                    "evaluation_assessment",
                    **{
                        key: value
                        for key, value in current.items()
                        if key not in {"id", "schema_version"}
                    },
                ),
                "revision.production_evaluation_record_identity",
            )
            require(
                current["session_id"] == row["original_session_id"],
                "revision.current_assessment_original_session",
            )
        expected_pass = bool(
            current is not None
            and row["exception"] is None
            and current["financial_valid"] == old["expected_financial_valid"]
            and current["full_mapping_status"] == old["expected_full_mapping_status"]
        )
        require(row["passed"] is expected_pass, "revision.saved_PASS_recomputed_from_actual_result")
        passed += expected_pass
        valid += bool(current is not None and current["financial_valid"])
        entered = bool(
            old["expected_financial_valid"]
            and old["assessment"]["reason"] == "assessment.source_relation_certificate_required"
            and current is not None
            and row["exception"] is None
            and current["support_assessment_entered"]
            and current["reason"] != "assessment.source_relation_certificate_required"
        )
        require(
            row["old_wrapper_failure_reached_support_assessment"] is entered,
            "revision.actual_support_entry_not_expected_PASS_assumption",
        )
        reached += entered
    require(
        qualification["control_count"] == len(rows)
        and qualification["passed_count"] == passed
        and qualification["financial_valid_count"] == valid
        and qualification["prior_15_reached_support_assessment"] == reached,
        "revision.qualification_summary_from_all_saved_results",
    )
    added = qualification["incremental_CPU"]
    relative = str(Path(added["report_path"]).relative_to(prepared.relative))
    require(
        prepared.members[relative]["sha256"] == added["report_sha256"],
        "revision.incremental_token_member_hash",
    )
    tokens = prepared.read(relative)
    validate_record(tokens, "new_eval_token_controls")
    require(
        tokens["status"] == added["status"]
        and tokens["financial_complete_packages"] == added["financial_complete_packages"]
        and len(tokens["rows"]) == added["rows"]
        and tokens["tokenizer_constructions"] == added["tokenizer_constructions"],
        "revision.incremental_CPU_exact_saved_evidence",
    )
    if added["status"] == "PASS_SCRIPTED_REPRESENTATION_ONLY":
        require(
            not tokens["failures"]
            and all(
                row["representation"]["consumable_token_representation"] for row in tokens["rows"]
            )
            and sum(row["representation"]["target_token_count"] for row in tokens["rows"])
            == added["target_tokens"]
            and sum(row["representation"]["sequence_length"] for row in tokens["rows"])
            == added["sequence_tokens"],
            "revision.incremental_arrays_exact_no_failed_rows",
        )
    inherited = qualification["inherited_CPU"]
    require(
        inherited["parent_directory"] == parent.relative
        and inherited["parent_manifest_id"] == parent.manifest["id"]
        and inherited["token_report_path"] == parent.relative + "/controls/token_report.json"
        and inherited["token_report_sha256"]
        == parent.members["controls/token_report.json"]["sha256"]
        and inherited["original_packages_path"]
        == parent.relative + "/controls/original_packages.json"
        and inherited["original_packages_sha256"]
        == parent.members["controls/original_packages.json"]["sha256"],
        "revision.original_39_package_array_parent_not_reencoded",
    )
    return qualification


def make_gate(prepared, observed, frozen):
    prep = prepared.read("report.json")
    checks = admission_checks(prep, observed, frozen)
    return record(
        "fixed_study_admission",
        status="READY_FOR_FIXED_COLLECTION"
        if all(checks.values())
        else "BLOCKED_FOR_FORMAL_COLLECTION",
        **checks,
        failed_gates=[key for key, value in checks.items() if not value],
        preparation_manifest_id=prepared.manifest["id"],
        preparation_report_id=prep["id"],
        freeze_id=frozen["id"],
        parent_preparation=frozen["parent_preparation"],
        parent_audits=frozen["parent_audits"],
        old_failed_gate_preserved=True,
        independent_audit_ids={key: value["id"] for key, value in observed.items()},
        collection_policy_id=collection.policy()["id"],
        consumer_policy_id=materials.policy()["id"],
        reassessment_id=prep["qualification"]["id"],
        no_UNP_nonzero_yield_requirement=True,
        Teacher_sessions_at_admission=0,
        Student_runs=0,
        no_pilot_before_fixed_collection=True,
    )


def validate_admission(root, prepared, audited, frozen):
    check_budget_owner(root, frozen)
    parent, original_audit, _ = check_freeze(root, frozen, verify_parent_members=True)
    observed = {key: audited.read(key + ".json") for key in ("panels", "increment")}
    require(
        observed["panels"] == inherited_panel_audit(parent, original_audit),
        "revision.original_passed_panel_proof_not_new_audit_claim",
    )
    increment = observed["increment"]
    validate_record(increment, "readiness_independent_audit")
    filename = "trusted_data_synthesis/scripts/audit_qa_vnext_eval_readiness_increment.py"
    pin = next(row for row in frozen["code"] if row["path"] == filename)
    require(
        increment["script"] == Path(filename).name
        and increment["script_sha256"] == pin["sha256"]
        and increment["stage_manifest_id"] == prepared.manifest["id"],
        "revision.actual_frozen_UNP_independent_audit_join",
    )
    verify_control_evidence(root, prepared)
    gate = audited.read("admission_gate.json")
    require(gate == make_gate(prepared, observed, frozen), "revision.every_gate_recomputed")
    require(
        gate["status"] == "READY_FOR_FIXED_COLLECTION" and gate["failed_gates"] == [],
        "revision.no_collection_while_any_gate_blocked",
    )
    require(
        gate["collection_policy_id"] == frozen["rule"]["registered_collection_policy"]["id"]
        and gate["consumer_policy_id"]
        == frozen["rule"]["registered_original_package_consumer"]["id"],
        "revision.inherited_fixed_collection_consumer_policies",
    )
    return gate


def audit_and_admit(root):
    root = Path(root).resolve()
    frozen = read(root / OUTPUT / "stage_freeze.json")
    parent, original_audit, _ = check_freeze(root, frozen, verify_parent_members=True)
    check_budget_owner(root, frozen)
    prepared = Parent(root, OUTPUT)
    prepared.verify_all()
    require("run_completed.json" in prepared.members, "revision.completed_finite_preparation")
    require(not safe_path(root, AUDITS).exists(), "revision.single_new_admission_set")
    verify_control_evidence(root, prepared)
    observed = {"panels": inherited_panel_audit(parent, original_audit)}
    filename = "audit_qa_vnext_eval_readiness_increment.py"
    try:
        result = prior_stage.load_script(root, filename).verify(root, OUTPUT + "/incremental")
    except Exception as error:
        result = {
            "status": "AUDIT_ERROR",
            "error_type": type(error).__name__,
            "reason": str(error),
            "failed_evidence_not_repaired_or_replaced": True,
        }
    observed["increment"] = record(
        "readiness_independent_audit",
        stage_manifest_id=prepared.manifest["id"],
        script=filename,
        script_sha256=sha(root / "trusted_data_synthesis/scripts" / filename),
        result=result,
        status=result["status"],
    )
    for key, value in observed.items():
        write_json(root / AUDITS / (key + ".json"), value)
    gate = make_gate(prepared, observed, frozen)
    write_json(root / AUDITS / "admission_gate.json", gate)
    seal(
        root / AUDITS,
        scope="inherited panel proof, new original-source UNP audit and recomputed admission",
    )
    return {
        "id": gate["id"],
        "status": gate["status"],
        "failed_gates": gate["failed_gates"],
        "audit_statuses": {key: value["status"] for key, value in observed.items()},
    }


def verify(root):
    root = Path(root).resolve()
    frozen = read(root / OUTPUT / "stage_freeze.json")
    check_freeze(root, frozen, verify_parent_members=True)
    check_budget_owner(root, frozen)
    prepared = Parent(root, OUTPUT)
    prepared.verify_all()
    require("run_completed.json" in prepared.members, "revision.preparation_completed")
    prior_stage.verify_old_public_bytes(root)
    verify_control_evidence(root, prepared)
    return {
        "manifest_id": prepared.manifest["id"],
        "new_members": len(prepared.members),
        "inherited_selected_panels": 900,
        "structural_checks_not_semantic_admission": True,
    }


def collect(root):
    root = Path(root).resolve()
    frozen = read(root / OUTPUT / "stage_freeze.json")
    prepared, audited = Parent(root, OUTPUT), Parent(root, AUDITS)
    prepared.verify_all()
    audited.verify_all()
    gate = validate_admission(root, prepared, audited, frozen)
    destination = safe_path(root, COLLECTION)
    require(not destination.exists(), "revision.one_fixed_AB_batch_no_pilot")
    full, public = prepared.read("catalog.json"), prepared.read("public_catalog.json")
    online = PublicCatalog(root, OUTPUT + "/public_catalog.json", public["id"])
    offline = OfflineCatalog(root, OUTPUT + "/catalog.json", full["id"])
    bank = ledger(root, frozen)
    key = credential(root)
    bank.register_collection(list(online.tasks.values()), gate_id=gate["id"], gate=gate)
    requests = destination / "requests"
    from ..finance_qa_vnext_task_panel.guards import execution_guard

    with execution_guard(online=True) as counters:
        report = collection.run(
            root,
            destination,
            bank,
            online,
            offline,
            lambda row: Provider(bank, row["session_id"], requests, key),
            gate_id=gate["id"],
            workers=8,
            receipt_verifier=lambda session, current: verify_receipts(session, current, requests),
        )
    write_json(
        destination / "execution_guards.json", record("fixed_collection_guards", counts=counters)
    )
    seal(destination, scope="entire fixed A/B collection; complete or stopped, no pilot or refill")
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
    frozen = read(root / OUTPUT / "stage_freeze.json")
    prepared, audited, collected = (
        Parent(root, OUTPUT),
        Parent(root, AUDITS),
        Parent(root, COLLECTION),
    )
    prepared.verify_all()
    audited.verify_all()
    validate_admission(root, prepared, audited, frozen)
    collected.verify_all()
    report = collected.read("report.json")
    require(report["collection_complete"], "revision.no_partial_population")
    destination = safe_path(root, COLLECTION + "_materials")
    public = prepared.read("public_catalog.json")
    online = PublicCatalog(root, OUTPUT + "/public_catalog.json", public["id"])
    bank = ledger(root, frozen)
    from ..finance_qa_vnext_task_panel.guards import execution_guard

    with execution_guard(online=False) as counters:
        result = materials.run(
            root,
            destination,
            root / COLLECTION,
            list(online.tasks.values()),
            expected_collection_id=report["id"],
            ledger=bank,
            receipt_verifier=lambda session, current: verify_receipts(
                session, current, root / COLLECTION / "requests"
            ),
        )
    write_json(
        destination / "execution_guards.json", record("fixed_material_guards", counts=counters)
    )
    seal(
        destination,
        scope="all completed fixed collection denominators and exact common A/B original materials",
    )
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
        "phase", choices=("freeze", "prepare", "verify", "admit", "collect", "materialize")
    )
    parser.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    result = {
        "freeze": freeze,
        "prepare": prepare,
        "verify": verify,
        "admit": audit_and_admit,
        "collect": collect,
        "materialize": materialize,
    }[args.phase](args.root)
    print(json.dumps(result, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
