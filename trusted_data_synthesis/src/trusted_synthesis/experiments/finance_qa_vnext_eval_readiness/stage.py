"""Freeze once, rebuild actual-period panels and admit only an audited fixed study."""

import argparse
import importlib.util
import importlib.metadata
import json
import subprocess
import sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

from ..finance_qa_vnext_catalog_bridge import panels as previous_panels
from ..finance_qa_vnext_catalog_bridge.catalog import (
    OfflineCatalog,
    Parent,
    PublicCatalog,
    compose,
    read,
    safe_path,
)
from ..finance_qa_vnext_catalog_bridge.stage import seal
from ..finance_qa_vnext_surface_build.guards import rewrite_guard
from ..finance_qa_vnext_surface_build.transport import credential
from ..finance_qa_vnext_task_build.archive import record, require, sha, validate_record, write_json
from ..qa_reasoning_share_training_preflight import tokenization as assets
from . import (
    collection,
    controls,
    materials,
    panel,
    power,
    source_policy,
    token_controls,
    training_increment,
)
from .budget import ResearchLedger
from .protocol import AUDIT_ATTACHMENT, AUDITS, COLLECTION, OUTPUT, WORK, policy
from .runtime import SnapshotSources
from .transport import Provider as TeacherProvider
from .transport import verify_receipts

PKG = "trusted_data_synthesis/src/trusted_synthesis/experiments/"
CODE_DIRS = [
    "trusted_data_synthesis/src/trusted_synthesis",
    PKG + "finance_qa_vnext_eval_readiness",
    PKG + "finance_qa_vnext_catalog_bridge",
    PKG + "finance_qa_vnext_task_build",
    PKG + "finance_qa_vnext_surface_build",
    PKG + "finance_qa_vnext_model_execution",
    "trusted_data_synthesis/src/trusted_synthesis/domains/finance/qa_vnext",
    "raw_financial_data_lake/finraw",
    "raw_financial_data_lake/finraw/qa",
]
CODE_EXTRA = [
    "trusted_data_synthesis/src/trusted_synthesis/canonical_json.py",
    PKG + "finance_qa_vnext_basis_scale_preparation/design.py",
    PKG + "finance_qa_vnext_model_execution/representation.py",
    PKG + "finance_qa_vnext_model_execution/transport.py",
    PKG + "finance_qa_vnext_model_execution/models.py",
    PKG + "finance_qa_vnext_task_panel/guards.py",
    PKG + "finance_qa_vnext_autonomous_formula/online/calculator.py",
    PKG + "qa_reasoning_share_training_preflight/tokenization.py",
    PKG + "qa_reasoning_share_training_preflight/models.py",
    "trusted_data_synthesis/scripts/audit_qa_vnext_eval_readiness_panels.py",
    "trusted_data_synthesis/scripts/audit_qa_vnext_eval_readiness_increment.py",
    "trusted_data_synthesis/scripts/audit_qa_vnext_catalog_incremental.py",
    "trusted_data_synthesis/scripts/audit_qa_vnext_task_build.py",
    "trusted_data_synthesis/pyproject.toml",
]


def now():
    return datetime.now(timezone.utc).isoformat()


def software_versions():
    return {
        "python": sys.version,
        "packages": {
            name: importlib.metadata.version(name)
            for name in (
                "torch",
                "transformers",
                "tokenizers",
                "sympy",
                "pyarrow",
                "httpx",
                "lxml",
                "pytest",
                "pydantic",
            )
        },
    }


def old_parent(root):
    return Parent(root, source_policy.BRIDGE, source_policy.BRIDGE_MANIFEST)


def verify_old_public_bytes(root):
    parent = old_parent(root)
    catalog = parent.read("catalog.json")
    require(len(catalog["tasks"]) == 243, "stage.preserve_exact_243")
    for task in catalog["tasks"]:
        path = safe_path(root, task["public_path"])
        require(sha(path) == task["public_messages_sha256"], "stage.unchanged_old_public_bytes")
    return parent, catalog


def code_paths(root):
    return sorted(
        {
            *CODE_EXTRA,
            *[
                str(path.relative_to(root))
                for directory in CODE_DIRS
                for path in (root / directory).rglob("*.py")
            ],
        }
    )


def freeze(root):
    root = Path(root).resolve()
    output = safe_path(root, OUTPUT)
    safe_path(root, WORK)
    require(not output.exists(), "stage.single_new_freeze_directory")
    require(
        not (root / WORK / "rewrite_and_Teacher_budget.sqlite3").exists(), "stage.new_ledger_only"
    )
    credential(root)
    prior, catalog = verify_old_public_bytes(root)
    old_freeze = prior.read("stage_freeze.json")
    metadata = previous_panels.inspect_source_metadata(root)
    training = source_policy.metadata(root)
    members = {row["path"]: row for row in old_freeze["source_files"]}
    for row in [*training["source_files"], *training["cached_files"]]:
        members[row["path"]] = row
    config = root / assets.SOURCE_CONFIGURATION
    require(sha(config) == assets.SOURCE_CONFIGURATION_SHA256, "stage.frozen_Student_config")
    members[assets.SOURCE_CONFIGURATION] = {
        "path": assets.SOURCE_CONFIGURATION,
        "sha256": sha(config),
        "bytes": config.stat().st_size,
    }
    for row in members.values():
        require(sha(root / row["path"]) == row["sha256"], "stage.original_source_metadata_hash")
    tokenizer = []
    assets._read_members(assets.MODEL_DIRECTORY)  # Includes forbidden sidecars, no construction.
    for filename, size, digest in assets.TOKENIZER_MEMBERS:
        path = assets.MODEL_DIRECTORY / filename
        require(path.stat().st_size == size and sha(path) == digest, "stage.fixed_tokenizer_asset")
        tokenizer.append({"absolute_path": str(path), "bytes": size, "sha256": digest})
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    tests = sorted(
        (root / "trusted_data_synthesis/tests").glob("test_qa_vnext_eval_readiness_*.py")
    )
    fixture_dependencies = [
        str(path.relative_to(root))
        for directory in ("trusted_data_synthesis/tests", "raw_financial_data_lake/tests")
        for path in (root / directory).rglob("*.py")
    ]
    paths = sorted(set(code_paths(root) + fixture_dependencies))
    code = []
    for relative in paths:
        committed = subprocess.check_output(["git", "show", head + ":" + relative], cwd=root)
        require(committed == (root / relative).read_bytes(), "stage.committed_code_and_tests")
        code.append({"path": relative, "sha256": sha(root / relative)})
    # No old 36-session fixture dispatch or old 167-row encoding is called.
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
    require(checked.returncode == 0, "stage.new_version_mock_and_source_contract_tests_pass")
    debits = []
    for descriptor in prior.read("catalog.json")["parents"]:
        parent = Parent(root, descriptor["directory"], descriptor["manifest_id"])
        ledger = parent.read("rewrite_budget_ledger.json")
        require(ledger["unsettled_or_unknown_count"] == 0, "stage.prior_known_rewrite_debits")
        debits.append(
            {
                "id": parent.manifest["id"] + "/rewrite_budget_ledger.json",
                "tokens": ledger["conservative_charged_tokens"],
                "path": parent.relative + "/rewrite_budget_ledger.json",
                "sha256": parent.members["rewrite_budget_ledger.json"]["sha256"],
            }
        )
    require(sum(x["tokens"] for x in debits) == 221538, "stage.shared_221538_not_new_budget")
    frozen = record(
        "eval_readiness_freeze",
        created_at=now(),
        git_commit=head,
        rule=policy(panel.policy()),
        code=code,
        source_files=list(members.values()),
        tokenizer_assets=tokenizer,
        software_versions=software_versions(),
        prior_debits=debits,
        parent_bridge=prior.descriptor(),
        panel_source_metadata=metadata,
        training_source_metadata=training,
        inherited_training_catalog_id=catalog["id"],
        new_test_result={
            "return_code": checked.returncode,
            "stdout": checked.stdout,
            "stderr": checked.stderr,
            "live_API_calls": 0,
            "tokenizer_loads": 0,
        },
        audit_attachment_sha256=sha(AUDIT_ATTACHMENT),
        formal_candidate_margin_choice="bounded_UNP_six_source_attempt_up_to_17",
        new_source_numeric_outputs_observed=False,
        new_model_outputs_observed=False,
    )
    write_json(output / "stage_freeze.json", frozen)
    return {
        "freeze_id": frozen["id"],
        "git_commit": head,
        "source_scope": training["policy_id"],
        "prior_debit": 221538,
        "test_output": checked.stdout,
    }


def check_freeze(root, frozen):
    validate_record(frozen, "eval_readiness_freeze")
    require(frozen["rule"] == policy(panel.policy()), "stage.frozen_rules")
    require(frozen["software_versions"] == software_versions(), "stage.frozen_software_versions")
    for row in [*frozen["code"], *frozen["source_files"], *frozen["prior_debits"]]:
        require(sha(root / row["path"]) == row["sha256"], "stage.frozen_code_or_input_bytes")
    for row in frozen["tokenizer_assets"]:
        require(sha(row["absolute_path"]) == row["sha256"], "stage.frozen_tokenizer_bytes")
    require(
        old_parent(root).descriptor() == frozen["parent_bridge"], "stage.original_parent_manifest"
    )
    require(
        previous_panels.inspect_source_metadata(root) == frozen["panel_source_metadata"],
        "stage.same_original_eval_sources",
    )


def ledger(root, frozen):
    return ResearchLedger(
        safe_path(root, WORK + "/rewrite_and_Teacher_budget.sqlite3"),
        frozen["id"],
        prior_debits=frozen["prior_debits"],
    )


def real_control_fixtures(root, output, frozen):
    selected = []
    all_tasks = {}
    for split in ("dev", "confirm"):
        directory = output / "panels" / split
        catalog = read(directory / "catalog.json")
        bindings = read(directory / "native_bindings.json")
        cells = {}
        all_tasks[split] = []
        for item in sorted(catalog["tasks"], key=lambda row: row["task_id"]):
            bundle = read(directory / item["path"])
            contract = bundle["public"]["period_contract"]
            periods = contract["periods"]
            kind = (
                "instant"
                if any(row["period_type"] == "instant" for row in periods)
                else "calendar_duration"
                if all(row["label_basis"] == "calendar_year" for row in periods)
                else "noncalendar_duration"
            )
            cell = (split, item["family"], contract["quantity"], kind)
            cells.setdefault(cell, (item, bundle))
            all_tasks[split].append(
                {
                    "task_id": item["task_id"],
                    "source_cluster": item["source_cluster"],
                    "family": item["family"],
                    "period_ids": [x["period_id"] for x in periods],
                }
            )
        for cell, (item, bundle) in sorted(cells.items()):
            messages = read(directory / item["public_path"])
            identity = {
                key: item[key]
                for key in ("task_id", "family", "surface_version_id", "public_messages_sha256")
            }
            identity["parent_manifest_id"] = frozen["id"]
            selected.append(
                {
                    "cell": list(cell),
                    "task_id": item["task_id"],
                    "fixture": {
                        "bundle": bundle,
                        "native_bindings": bindings,
                        "messages": messages,
                        "identity": identity,
                        "sources": SnapshotSources(root, [bundle["public"]["source_document"]]),
                    },
                }
            )
    return selected, all_tasks


def prepare(root):
    root = Path(root).resolve()
    output = safe_path(root, OUTPUT)
    safe_path(root, WORK)
    frozen = read(output / "stage_freeze.json")
    check_freeze(root, frozen)
    require(not (output / "run_started.json").exists(), "stage.one_preparation_run")
    key = credential(root)
    bank = ledger(root, frozen)
    require(
        not bank.sessions() and not bank.snapshot()["request_reservations"],
        "stage.no_preexisting_production_or_Teacher",
    )
    write_json(
        output / "run_started.json",
        record("eval_readiness_run_start", at=now(), freeze_id=frozen["id"]),
    )
    try:
        with rewrite_guard() as guards, ThreadPoolExecutor(max_workers=2) as pool:
            future = pool.submit(
                panel.run,
                root,
                output / "panels",
                root / WORK / "panels",
                expected_policy_id=panel.policy()["id"],
                expected_source_metadata_id=frozen["panel_source_metadata"]["id"],
                freeze_id=frozen["id"],
            )
            increment = training_increment.run(
                root, output / "incremental", WORK + "/train", frozen, bank, key
            )
            parents = [
                Parent(root, x["directory"], x["manifest_id"])
                for x in old_parent(root).read("catalog.json")["parents"]
            ]
            parents.append(Parent(root, OUTPUT + "/incremental"))
            full, public = compose(root, output, parents, frozen["id"])
            panel_result = future.result()
            chosen, source_tasks = real_control_fixtures(root, output, frozen)
            write_json(
                output / "controls/fixture_selection.json",
                record(
                    "real_eval_fixture_selection",
                    rows=[{k: v for k, v in row.items() if k != "fixture"} for row in chosen],
                    rule=frozen["rule"]["controls"]["real_fixture_selection"],
                ),
            )
            synthetic = controls.run_controls(output=output / "controls/synthetic_report.json")
            actual = controls.run_controls(
                controls.source_bound_cases([x["fixture"] for x in chosen]),
                output=output / "controls/source_bound_report.json",
            )
            packages = controls.raw_packages(actual)
            write_json(output / "controls/original_packages.json", packages)
            tokens = token_controls.materialize(packages, root)
            write_json(output / "controls/token_report.json", tokens)
            write_json(output / "prospective_source_sensitivity.json", power.run(source_tasks))
        require(not any(guards["forbidden"].values()), "stage.no_unregistered_provider_or_GPU")
        write_json(
            output / "execution_guards.json", record("eval_readiness_execution_guards", **guards)
        )
        counts = Counter(row["family"] for row in full["tasks"])
        ceiling = 5 * min(
            40,
            counts["stock_rollforward"],
            counts["annual_flow"],
            counts["company_defined_metric"],
            counts["control"] // 2,
        )
        report = record(
            "eval_readiness_preparation_report",
            status="BOUNDED_VERSION_EXECUTED_AUDIT_REQUIRED",
            freeze_id=frozen["id"],
            catalog_id=full["id"],
            public_catalog_id=public["id"],
            training_candidates=len(full["tasks"]),
            new_training_candidates=increment["tasks"],
            all_new_registered_targets_retained=increment["all_registered_tasks_retained"],
            family_counts=dict(counts),
            balanced_reference_supply_ceiling=ceiling,
            old_243_public_bytes_preserved=True,
            old_874_panel_records_overwritten=False,
            evaluation_tasks=panel_result["unique_task_count"],
            panel_quota_complete=panel_result["quota_complete"],
            panel_public_period_checks=panel_result["all_selected_public_period_checks_passed"],
            new_synthetic_controls={
                k: synthetic[k] for k in ("status", "control_count", "passed_count")
            },
            new_source_bound_controls={
                k: actual[k] for k in ("status", "control_count", "passed_count")
            },
            new_CPU_materialization={
                k: v for k, v in tokens.items() if k not in {"rows", "tokenizer_binding"}
            },
            budget=bank.snapshot(),
            Teacher_sessions=0,
            Student_runs=0,
            GPU_runs=0,
            formal_collection_started=False,
            independent_audits_pending=True,
            no_training_population_selected=True,
        )
        write_json(output / "report.json", report)
        check_freeze(root, frozen)
        verify_old_public_bytes(root)
        write_json(
            output / "run_completed.json",
            record("eval_readiness_run_completed", at=now(), report_id=report["id"]),
        )
    except BaseException as error:
        write_json(
            output / "run_failed.json",
            record(
                "eval_readiness_run_failed",
                at=now(),
                reason=str(error).replace(key, "[REDACTED]"),
                error_type=type(error).__name__,
                original_outputs_and_budget_not_reset=True,
                no_automatic_replay=True,
            ),
        )
        seal(output, status="failed", runtime_databases_excluded=WORK)
        raise
    manifest = seal(
        output,
        scope="one actual-period panel and bounded training-candidate version",
        runtime_databases_excluded=WORK,
        original_parent_artifacts_unchanged=True,
    )
    return {
        "manifest_id": manifest["id"],
        **{
            k: report[k]
            for k in (
                "training_candidates",
                "new_training_candidates",
                "evaluation_tasks",
                "panel_quota_complete",
                "new_synthetic_controls",
                "new_source_bound_controls",
                "new_CPU_materialization",
            )
        },
    }


def load_script(root, name):
    path = root / "trusted_data_synthesis/scripts" / name
    spec = importlib.util.spec_from_file_location(name.removesuffix(".py"), path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def verify(root):
    root = Path(root).resolve()
    frozen = read(root / OUTPUT / "stage_freeze.json")
    check_freeze(root, frozen)
    parent = Parent(root, OUTPUT)
    parent.verify_all()
    verify_old_public_bytes(root)
    require((root / OUTPUT / "run_completed.json").exists(), "stage.actual_preparation_completed")
    return {
        "manifest_id": parent.manifest["id"],
        "members": len(parent.members),
        "original_training_surfaces": 243,
        "structural_verification_is_not_semantic_admission": True,
    }


def admission_checks(prep, observed, frozen):
    return {
        "panel_quota_complete": prep["panel_quota_complete"] and prep["evaluation_tasks"] == 900,
        "actual_period_semantics_passed": observed["panels"]["status"] == "PASS_AS_SCOPED",
        "increment_source_semantics_passed": observed["increment"]["status"] == "passed",
        "complete_trajectory_qualification_passed": all(
            prep[key]["status"] == "PASS" and prep[key]["control_count"] > 0
            for key in ("new_synthetic_controls", "new_source_bound_controls")
        ),
        "new_original_CPU_representation_passed": prep["new_CPU_materialization"]["status"]
        == "PASS_SCRIPTED_REPRESENTATION_ONLY"
        and not prep["new_CPU_materialization"]["failures"]
        and prep["new_CPU_materialization"]["encoded_rows"] > 0
        and prep["new_CPU_materialization"]["tokenizer_constructions"] == 1
        and prep["new_CPU_materialization"]["maximum_sequence_length"] == 24576
        and prep["new_CPU_materialization"]["truncation"] is False,
        "training_catalog_locked": prep["balanced_reference_supply_ceiling"] >= 180
        and prep["all_new_registered_targets_retained"],
        "live_transport_controls_passed": frozen["new_test_result"]["return_code"] == 0,
        "original_package_consumer_registered": callable(materials.update_examples)
        and frozen["new_test_result"]["return_code"] == 0,
    }


def validate_admission(prepared, audited, frozen):
    gate = audited.read("admission_gate.json")
    validate_record(gate, "fixed_study_admission")
    prep = prepared.read("report.json")
    observed = {key: audited.read(key + ".json") for key in ("panels", "increment")}
    for value in observed.values():
        validate_record(value, "readiness_independent_audit")
        require(
            value["stage_manifest_id"] == prepared.manifest["id"], "admission.audit_input_manifest"
        )
        pin = next(
            row
            for row in frozen["code"]
            if row["path"] == "trusted_data_synthesis/scripts/" + value["script"]
        )
        require(value["script_sha256"] == pin["sha256"], "admission.frozen_independent_auditor")
    checks = admission_checks(prep, observed, frozen)
    require(
        all(checks.values())
        and all(gate.get(key) is True for key in checks)
        and gate["failed_gates"] == []
        and gate["status"] == "READY_FOR_FIXED_COLLECTION",
        "admission.every_gate_recomputed_not_status_self_report",
    )
    require(
        gate["freeze_id"] == frozen["id"]
        and gate["preparation_report_id"] == prep["id"]
        and gate["preparation_manifest_id"] == prepared.manifest["id"]
        and gate["independent_audit_ids"] == {k: v["id"] for k, v in observed.items()},
        "admission.exact_freeze_report_audit_joins",
    )
    require(
        gate["collection_policy_id"]
        == collection.policy()["id"]
        == frozen["rule"]["registered_collection_policy"]["id"]
        and gate["consumer_policy_id"]
        == materials.policy()["id"]
        == frozen["rule"]["registered_original_package_consumer"]["id"],
        "admission.frozen_collection_and_material_policies",
    )
    return gate


def audit_and_admit(root):
    root = Path(root).resolve()
    output = safe_path(root, OUTPUT)
    audit_directory = safe_path(root, AUDITS)
    frozen = read(output / "stage_freeze.json")
    check_freeze(root, frozen)
    parent = Parent(root, OUTPUT)
    parent.verify_all()
    require((output / "run_completed.json").exists(), "admission.actual_preparation_completed")
    require(not audit_directory.exists(), "admission.one_independent_audit_set")
    observed = {}
    for label, filename, directory in (
        ("panels", "audit_qa_vnext_eval_readiness_panels.py", OUTPUT + "/panels"),
        ("increment", "audit_qa_vnext_eval_readiness_increment.py", OUTPUT + "/incremental"),
    ):
        try:
            value = load_script(root, filename).verify(root, directory)
        except Exception as error:
            value = {
                "status": "AUDIT_ERROR",
                "error_type": type(error).__name__,
                "reason": str(error),
                "failed_evidence_not_repaired_or_replaced": True,
            }
        report = record(
            "readiness_independent_audit",
            stage_manifest_id=parent.manifest["id"],
            script=filename,
            script_sha256=sha(root / "trusted_data_synthesis/scripts" / filename),
            result=value,
            status=value["status"],
        )
        write_json(root / AUDITS / (label + ".json"), report)
        observed[label] = report
    prep = parent.read("report.json")
    checks = admission_checks(prep, observed, frozen)
    ready = all(checks.values())
    gate = record(
        "fixed_study_admission",
        status="READY_FOR_FIXED_COLLECTION" if ready else "BLOCKED_FOR_FORMAL_COLLECTION",
        **checks,
        preparation_manifest_id=parent.manifest["id"],
        preparation_report_id=prep["id"],
        freeze_id=frozen["id"],
        independent_audit_ids={key: value["id"] for key, value in observed.items()},
        collection_policy_id=collection.policy()["id"],
        consumer_policy_id=materials.policy()["id"],
        Teacher_sessions_at_admission=0,
        Student_runs=0,
        no_pilot_before_fixed_collection=True,
        failed_gates=[key for key, value in checks.items() if not value],
    )
    write_json(root / AUDITS / "admission_gate.json", gate)
    seal(
        root / AUDITS,
        scope="independent read-only audits and fixed-study admission, no model calls",
    )
    return {
        "id": gate["id"],
        "status": gate["status"],
        "failed_gates": gate["failed_gates"],
        "audit_statuses": {key: value["status"] for key, value in observed.items()},
    }


def collect(root):
    root = Path(root).resolve()
    safe_path(root, OUTPUT)
    safe_path(root, AUDITS)
    destination = safe_path(root, COLLECTION)
    frozen = read(root / OUTPUT / "stage_freeze.json")
    check_freeze(root, frozen)
    prepared = Parent(root, OUTPUT)
    prepared.verify_all()
    audited = Parent(root, AUDITS)
    audited.verify_all()
    gate = validate_admission(prepared, audited, frozen)
    require(not destination.exists(), "collection.single_fixed_batch")
    full, public = prepared.read("catalog.json"), prepared.read("public_catalog.json")
    online = PublicCatalog(root, OUTPUT + "/public_catalog.json", public["id"])
    offline = OfflineCatalog(root, OUTPUT + "/catalog.json", full["id"])
    bank = ledger(root, frozen)
    key = credential(root)
    bank.register_collection(list(online.tasks.values()), gate_id=gate["id"], gate=gate)
    requests = root / COLLECTION / "requests"
    # Only the fixed API callback is live; no Student model construction or GPU.
    from ..finance_qa_vnext_task_panel.guards import execution_guard

    with execution_guard(online=True) as counters:
        report = collection.run(
            root,
            root / COLLECTION,
            bank,
            online,
            offline,
            lambda row: TeacherProvider(bank, row["session_id"], requests, key),
            gate_id=gate["id"],
            workers=8,
            receipt_verifier=lambda session, current: verify_receipts(session, current, requests),
        )
    write_json(
        root / COLLECTION / "execution_guards.json",
        record("fixed_collection_guards", counts=counters),
    )
    seal(
        root / COLLECTION, scope="entire registered fixed A/B batch, complete or stopped; no pilot"
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
    safe_path(root, OUTPUT)
    safe_path(root, COLLECTION)
    destination = safe_path(root, COLLECTION + "_materials")
    frozen = read(root / OUTPUT / "stage_freeze.json")
    check_freeze(root, frozen)
    prepared = Parent(root, OUTPUT)
    prepared.verify_all()
    collected = Parent(root, COLLECTION)
    collected.verify_all()
    report = collected.read("report.json")
    require(report["collection_complete"], "materialization.no_incomplete_population")
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
    seal(destination, scope="all fixed collection denominators and exact common A/B materials")
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
    print(
        json.dumps(
            {
                "freeze": freeze,
                "prepare": prepare,
                "verify": verify,
                "admit": audit_and_admit,
                "collect": collect,
                "materialize": materialize,
            }[args.phase](args.root),
            ensure_ascii=False,
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
