"""One declared Task, two actual local routes, independent replay and finite comparison."""

from __future__ import annotations

import argparse
import hashlib
import json
from decimal import Decimal, localcontext
from pathlib import Path
from typing import Any

from trusted_synthesis.canonical_json import strict_canonical_hash
from trusted_synthesis.experiments.qa_reasoning_finite_comparison.inputs import (
    files_at,
    git,
    source_group,
    validate_manifest,
)
from trusted_synthesis.experiments.qa_reasoning_fixed_fixture.runtime import DurableArtifactWriter

from . import models, runtime
from .comparison import compare_records, comparison_rule_contract
from .controls import run_controls
from .models import record, require
from .source import ARCHIVE_PATH, ARCHIVE_SHA256, load_source, selection_policy
from .validation import read_trajectory_records, validate_trajectory

SOURCE_PATHS = tuple(
    "trusted_data_synthesis/src/trusted_synthesis/experiments/qa_reasoning_part_whole_share/" + name
    for name in (
        "__init__.py",
        "models.py",
        "source.py",
        "runtime.py",
        "validation.py",
        "comparison.py",
        "controls.py",
        "preflight.py",
    )
)
REFERENCE_PATHS = tuple(
    "trusted_data_synthesis/src/trusted_synthesis/" + name
    for name in (
        "canonical_json.py",
        "experiments/qa_reasoning_finite_comparison/inputs.py",
        "experiments/qa_reasoning_fixed_fixture/runtime.py",
        "core/operations/registry.py",
        "core/operations/executors/numeric.py",
        "domains/finance/operations.py",
    )
)


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def authorize(review: bytes) -> dict[str, Any]:
    require(
        len(review) == models.REVIEW_BYTES and _sha(review) == models.REVIEW_SHA256,
        "authorization.review",
        "exact new review required",
    )
    require(
        len(models.DIRECTIVE.encode()) == 24
        and _sha(models.DIRECTIVE.encode()) == models.DIRECTIVE_SHA256,
        "authorization.directive",
        "exact operator directive required",
    )
    return record(
        "authorization",
        stage=models.STAGE,
        review_bytes=len(review),
        review_sha256=_sha(review),
        directive=models.DIRECTIVE,
        directive_sha256=models.DIRECTIVE_SHA256,
        review_access="report_review_and_count_checks_no_repository_artifact_or_source_replay",
        target="UNP/2015/page_56.pdf-1 known source group only",
        maximum_tasks=1,
        maximum_candidate_executions=2,
        maximum_finite_pairs=1,
        Provider_credential_GPU_limits=[0, 0, 0],
        old_source_scan_and_old_candidate_reruns_forbidden=True,
        old_mainline="remains_paused",
        online_authorization=False,
        additional_execution_on_failure=False,
    )


def _freeze(root: Path) -> tuple[dict[str, Any], dict[str, bytes]]:
    files = files_at(root / models.PARENT)
    manifest = validate_manifest(files, models.PARENT_MANIFEST, models.PARENT_ROOT)
    require(
        len(files) == 20 and sum(map(len, files.values())) == 1_251_021,
        "freeze.geometry",
        "closed source-branch directory differs",
    )
    decision, gate = (json.loads(files[name]) for name in ("decision.json", "gate_evaluation.json"))
    require(
        decision["status"] == "source_not_instantiated"
        and decision["scientific_witness"] is None
        and (gate["passed"], gate["failed"], gate["not_instantiated"], gate["not_run"])
        == (3, 0, 1, 1),
        "freeze.scoped_result",
        "historical uninstantiated result changed",
    )
    return record(
        "predecessor_freeze",
        directory=models.PARENT,
        manifest_id=manifest["manifest_id"],
        artifact_root=manifest["artifact_root"],
        files=len(files),
        bytes=sum(map(len, files.values())),
        original_scientific_witness=None,
        original_gate_partition=[3, 0, 1, 1],
        historical_candidate_executions=0,
        predecessor_rescan_calls=0,
    ), files


def _manifest(writer: DurableArtifactWriter, report: dict[str, Any]) -> dict[str, Any]:
    files = files_at(writer.root)
    members = [
        {"relative_path": p, "sha256": _sha(data), "byte_count": len(data)}
        for p, data in sorted(files.items())
    ]
    body = {
        "schema_version": "part_whole_share_manifest.v1",
        "members": members,
        "member_count": len(members),
        "member_bytes": sum(map(len, files.values())),
        "report_id": report["id"],
        "self_excluding": True,
        "artifact_root": strict_canonical_hash(members, prefix="part_whole_share_root:"),
    }
    manifest = {
        **body,
        "manifest_id": strict_canonical_hash(body, prefix="part_whole_share_manifest:"),
    }
    writer.write_json("artifact_manifest.json", manifest)
    validate_manifest(files_at(writer.root), manifest["manifest_id"], manifest["artifact_root"])
    return manifest


def build_preflight(
    *,
    repo_root: Path,
    external_audit_path: Path,
    source_commit: str,
    source_tree: str,
    output_directory: Path,
    replay_from: Path | None = None,
) -> dict[str, Any]:
    """Rebuilds use original runtime bytes; only the initial build dispatches D/S."""
    root = repo_root.resolve()
    review = external_audit_path.read_bytes()
    authorization = authorize(review)
    freeze, parent_files = _freeze(root)
    reference_tree = git(root, "rev-parse", f"{models.REFERENCE_COMMIT}^{{tree}}").decode().strip()
    authority = record(
        "source_authority",
        implementation=source_group(root, source_commit, source_tree, SOURCE_PATHS),
        declared_references=source_group(
            root, models.REFERENCE_COMMIT, reference_tree, REFERENCE_PATHS
        ),
        archive_member=source_group(root, models.REFERENCE_COMMIT, reference_tree, (ARCHIVE_PATH,)),
        transitive_import_or_runtime_environment_closure_claimed=False,
    )
    saved: dict[str, bytes] | None = None
    if replay_from is not None:
        saved = files_at(replay_from)
        old_manifest = json.loads(saved["artifact_manifest.json"])
        validate_manifest(saved, old_manifest["manifest_id"], old_manifest["artifact_root"])
    writer = DurableArtifactWriter(output_directory)
    writer.create_root()
    writer.write_bytes("external_review.txt", review)
    writer.write_bytes("operator_directive.txt", models.DIRECTIVE.encode())
    for name, obj in (
        ("authorization", authorization),
        ("predecessor_freeze", freeze),
        ("source_authority", authority),
        ("source_selection_policy", selection_policy()),
    ):
        writer.write_json(name + ".json", obj)
    policy_receipt = record(
        "source_policy_receipt",
        authorization_id=authorization["id"],
        policy_sha256=_sha(writer.read_bytes("source_selection_policy.json")),
        pre_target_binding=True,
        known_target_not_blind=True,
        write_events=list(writer.events),
    )
    writer.write_json("source_policy_receipt.json", policy_receipt)
    try:
        source = load_source(root)
        contract = models.contract_for(source, comparison_rule_contract())
        declarations = models.candidates_for(contract, source)
        with localcontext() as context:
            context.prec = contract["numeric"]["precision"]
            context.rounding = contract["numeric"]["rounding"]
            e = source["evidence"]
            delta = (
                Decimal(e["freight"]["value"])
                + Decimal(e["other"]["value"])
                - Decimal(e["total"]["value"])
            )
        require(
            abs(delta) <= Decimal(contract["numeric"]["source_reconciliation_tolerance"])
            and Decimal(e["total"]["value"]) != 0,
            "source.reconciliation",
            "selected source fails the frozen zero-tolerance display relation",
        )
    except (ValueError, KeyError, TypeError, ArithmeticError) as error:
        stopped = record(
            "stopped",
            status="source_or_contract_not_instantiated",
            W_share=None,
            failure_stage=getattr(error, "stage", "source.binding"),
            reason=str(error),
            candidate_runtime_executions=0,
            old_witness_unchanged=None,
            source_fallback=False,
            new_online_authorizations=0,
        )
        writer.write_json("decision.json", stopped)
        manifest = _manifest(writer, stopped)
        return {"decision": stopped, "manifest": manifest, "new_runtime_calls": 0}
    family = record(
        "candidate_family",
        task_id=contract["task"]["id"],
        contract_id=contract["id"],
        candidates=declarations,
        maximum_positive_executions=2,
        outcome_aware_replacement_permitted=False,
    )
    reconciliation = record(
        "source_reconciliation",
        source_binding_id=source["id"],
        evaluated_after_column_selection=True,
        difference=str(delta),
        tolerance=contract["numeric"]["source_reconciliation_tolerance"],
        used_for_source_selection=False,
        candidate_operation=False,
    )
    for name, obj in (
        ("source_binding", source),
        ("contract", contract),
        ("candidate_family", family),
        ("source_reconciliation", reconciliation),
    ):
        writer.write_json(name + ".json", obj)
    registration = record(
        "registration_receipt",
        authorization_id=authorization["id"],
        source_binding_id=source["id"],
        contract_id=contract["id"],
        candidate_family_id=family["id"],
        candidate_ids=[d["id"] for d in declarations],
        measurement_rule_sha256=_sha(writer.read_bytes("contract.json")),
        before_candidate_execution=True,
        controller="deterministic_fixture",
        runtime_limit=2,
        write_events=list(writer.events),
    )
    writer.write_json("registration_receipt.json", registration)
    input_bytes = {
        name: writer.read_bytes(name)
        for name in (
            "source_binding.json",
            "contract.json",
            "candidate_family.json",
            "registration_receipt.json",
        )
    }
    calls = 0
    if saved is not None:
        require(
            all(saved.get(name) == data for name, data in input_bytes.items()),
            "rebuild.frozen_inputs",
            "independently rebuilt input identities differ",
        )
        for path, payload in sorted(saved.items()):
            if path.startswith("runtime/"):
                writer.write_bytes(path, payload)
    else:
        for declaration in declarations:
            require(
                all(writer.read_bytes(name) == data for name, data in input_bytes.items()),
                "execution.registration_bytes",
                "frozen source/contract/family/receipt changed",
            )
            require(calls < 2, "execution.budget", "positive execution budget exhausted")
            calls += 1
            try:
                runtime.run_candidate(
                    contract, source, declaration, writer.root / "runtime" / declaration["route"]
                )
            except Exception as error:
                # Preserve a failed attempt and continue only to the other already registered route.
                failure = record(
                    "execution_failure",
                    candidate_id=declaration["id"],
                    stage=getattr(error, "stage", "runtime.unhandled"),
                    error_type=type(error).__name__,
                    reason=str(error),
                    retry=False,
                )
                writer.write_json("runtime/" + declaration["route"] + "/failure.json", failure)
    validations: dict[str, Any] = {}
    records: dict[str, Any] = {}
    for declaration in declarations:
        route = declaration["route"]
        directory = writer.root / "runtime" / route
        validations[route] = validate_trajectory(contract, source, directory)
        writer.write_json("validation_" + route + ".json", validations[route])
        try:
            records[route] = read_trajectory_records(directory)
        except (OSError, ValueError, KeyError, TypeError):
            records[route] = None
    if all(records.values()):
        comparison = compare_records(contract, source, records["D"], records["S"])
        controls = run_controls(contract, source, records["S"])
    else:
        comparison = {
            "status": "undetermined",
            "W_share": None,
            "formal_class_count": None,
            "reason": "registered_runtime_incomplete",
            "formal_pairs": 0,
        }
        controls = {"all_rejected": False, "status": "not_run_runtime_incomplete"}
    writer.write_json("comparison.json", comparison)
    writer.write_json("controls.json", controls)
    immutable = (
        files_at(root / models.PARENT) == parent_files
        and _sha((root / ARCHIVE_PATH).read_bytes()) == ARCHIVE_SHA256
    )
    require(immutable, "scope.historical_bytes", "historical source bytes changed")
    scope = record(
        "scope",
        stage=models.STAGE,
        new_task_instances=1,
        bound_positive_candidate_attempts=2,
        registered_candidate_ids=registration["candidate_ids"],
        complete_runtime_routes=sum(records[r] is not None for r in ("D", "S")),
        actual_operation_records=sum(len(records[r]["steps"]) for r in ("D", "S") if records[r]),
        runtime_oracle_calls=0,
        reconstruction_rebuild_dispatches_new_candidates=False,
        source_page_groups=1,
        raw_source_records_projected=4,
        whole_archive_rescan_calls=0,
        old_source_builder_calls=0,
        Provider_calls=0,
        credential_lookups=0,
        GPU_jobs=0,
        old_witness_unchanged=None,
        historical_bytes_unchanged=immutable,
        new_online_authorizations=0,
        QA_release_VTDO_training_production_rows=0,
        old_mainline="remains_paused",
        deeper_reasoning_or_coverage_claimed=False,
    )
    writer.write_json("scope.json", scope)
    own_pass = all(v["qualified"] for v in validations.values())
    determined = comparison.get("status") in ("equivalent", "different_retained_semantics")
    gate = record(
        "gate",
        rows=[
            {"gate": "G0_new_scope_and_immutable_predecessor", "status": "PASS"},
            {"gate": "G1_target_source_task_and_local_contract", "status": "PASS"},
            {
                "gate": "G2_two_actual_routes_and_own_validation",
                "status": "PASS" if own_pass else "FAIL",
            },
            {
                "gate": "G3_complete_finite_semantics_not_class_count",
                "status": "PASS" if determined else "UNDETERMINED",
            },
            {
                "gate": "G4_direct_controls_and_zero_external_execution",
                "status": "PASS" if controls["all_rejected"] else "FAIL",
            },
        ],
        second_class_required_for_pass=False,
    )
    gate["id"] = record(
        "gate", **{k: v for k, v in gate.items() if k not in ("id", "schema_version")}
    )["id"]
    writer.write_json("gate_evaluation.json", gate)
    decision = record(
        "decision",
        task_id=contract["task"]["id"],
        status=comparison.get("status"),
        W_share=comparison.get("W_share"),
        formal_class_count=comparison.get("formal_class_count"),
        qualified_by_route={r: v["qualified"] for r, v in validations.items()},
        gate_id=gate["id"],
        old_compound_task_W=None,
        fixed_task_finite_constructibility_only=True,
        model_reachability_measured=False,
    )
    writer.write_json("decision.json", decision)
    transition = record(
        "transition",
        completed_stage=models.STAGE,
        decision_id=decision["id"],
        next_stage_authorized=False,
        new_external_decision_required=True,
        no_candidate_replacement=True,
        old_mainline="remains_paused",
        model_reachability_Provider_GPU_training_Release_VTDO_authorized=False,
    )
    writer.write_json("transition.json", transition)
    report = record(
        "report",
        stage=models.STAGE,
        authorization_id=authorization["id"],
        source_authority_id=authority["id"],
        source_binding_id=source["id"],
        contract_id=contract["id"],
        task_id=contract["task"]["id"],
        registration_id=registration["id"],
        gate_id=gate["id"],
        decision_id=decision["id"],
        transition_id=transition["id"],
        scope_id=scope["id"],
        decision=decision,
        immutable_predecessor=freeze,
        experimental_semantics="known_source_deterministic_finite_mechanism",
    )
    writer.write_json("report.json", report)
    manifest = _manifest(writer, report)
    return {
        "source": source,
        "contract": contract,
        "family": family,
        "validations": validations,
        "comparison": comparison,
        "controls": controls,
        "scope": scope,
        "gate": gate,
        "decision": decision,
        "report": report,
        "manifest": manifest,
        "new_runtime_calls": calls,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("repo-root", "external-audit", "source-commit", "source-tree", "output-dir"):
        parser.add_argument("--" + name, required=True)
    parser.add_argument("--replay-from")
    args = parser.parse_args()
    result = build_preflight(
        repo_root=Path(args.repo_root),
        external_audit_path=Path(args.external_audit),
        source_commit=args.source_commit,
        source_tree=args.source_tree,
        output_directory=Path(args.output_dir),
        replay_from=Path(args.replay_from) if args.replay_from else None,
    )
    print(
        json.dumps(
            {"decision": result["decision"], "new_runtime_calls": result["new_runtime_calls"]},
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
