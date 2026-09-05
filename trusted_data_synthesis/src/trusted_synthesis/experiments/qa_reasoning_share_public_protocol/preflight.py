"""Freeze one public-protocol fixture session; byte-only rebuilds never redispatch."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from trusted_synthesis.canonical_json import strict_canonical_hash
from trusted_synthesis.experiments.qa_reasoning_finite_comparison.inputs import (
    files_at,
    source_group,
    validate_manifest,
)
from trusted_synthesis.experiments.qa_reasoning_fixed_fixture.runtime import DurableArtifactWriter

from . import models
from .controls import run_controls
from .engine import ProtocolEngine, verify_callback
from .fixture import PublicRequestFixture, fixture_binding
from .independent import audit_registration, audit_session, read_session_records
from .models import initial_dynamic, protocol_contract, record, require
from .public_view import make_state, public_context, request_for

SOURCE_PATHS = tuple(
    "trusted_data_synthesis/src/trusted_synthesis/experiments/qa_reasoning_share_public_protocol/"
    + name
    for name in (
        "__init__.py",
        "models.py",
        "public_view.py",
        "fixture.py",
        "engine.py",
        "controls.py",
        "independent.py",
        "preflight.py",
    )
)
REFERENCE_PATHS = tuple(
    "trusted_data_synthesis/src/trusted_synthesis/" + name
    for name in (
        "canonical_json.py",
        "experiments/qa_reasoning_finite_comparison/inputs.py",
        "experiments/qa_reasoning_fixed_fixture/runtime.py",
        "experiments/qa_reasoning_part_whole_share/models.py",
        "experiments/qa_reasoning_part_whole_share/runtime.py",
        "core/operations/registry.py",
        "core/operations/executors/numeric.py",
        "domains/finance/operations.py",
    )
)


def _sha(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def authorize(review: bytes) -> dict[str, Any]:
    require(
        len(review) == models.REVIEW_BYTES and _sha(review) == models.REVIEW_SHA256,
        "authorization.review",
    )
    require(
        len(models.DIRECTIVE.encode()) == 24
        and _sha(models.DIRECTIVE.encode()) == models.DIRECTIVE_SHA256,
        "authorization.directive",
    )
    return record(
        "authorization",
        stage=models.STAGE,
        review_sha256=_sha(review),
        review_bytes=len(review),
        directive=models.DIRECTIVE,
        directive_sha256=models.DIRECTIVE_SHA256,
        audit_is_not_online_authorization=True,
        current_directive_scope="minimal local public-State and explicit generator-update protocol",
        maximum_positive_protocol_sessions=1,
        maximum_callbacks_per_session=12,
        maximum_action_dispatches=3,
        maximum_accepted_updates=3,
        source_rescans=0,
        old_candidate_reruns=0,
        new_quotient_comparisons=0,
        additional_execution_on_failure=False,
        Provider_credential_GPU_limits=[0, 0, 0],
        online_authorization=False,
        old_mainline="remains_paused",
    )


def freeze_parent(root: Path) -> tuple[dict[str, Any], dict[str, bytes]]:
    files = files_at(root / models.PARENT)
    manifest = validate_manifest(files, models.PARENT_MANIFEST, models.PARENT_ROOT)
    require(
        len(files) == 65 and sum(map(len, files.values())) == 254_479,
        "freeze.parent_geometry",
    )
    source, contract = (json.loads(files[p]) for p in ("source_binding.json", "contract.json"))
    require(source["id"] == contract["source_binding_id"], "freeze.parent_join")
    return record(
        "predecessor_freeze",
        directory=models.PARENT,
        manifest_id=manifest["manifest_id"],
        artifact_root=manifest["artifact_root"],
        files=len(files),
        bytes=sum(map(len, files.values())),
        source_binding_id=source["id"],
        task_id=contract["task"]["id"],
        contract_id=contract["id"],
        historical_W_share=1,
        historical_finite_classes=2,
        historical_compound_task_W=None,
        parent_result_recomputed=False,
        source_loader_or_old_candidate_runtime_calls=0,
    ), files


def _manifest(writer: DurableArtifactWriter, report: dict[str, Any]) -> dict[str, Any]:
    files = files_at(writer.root)
    members = [
        {"relative_path": name, "sha256": _sha(data), "byte_count": len(data)}
        for name, data in sorted(files.items())
    ]
    body = {
        "schema_version": "public_share_protocol_manifest.v1",
        "members": members,
        "member_count": len(members),
        "member_bytes": sum(map(len, files.values())),
        "report_id": report["id"],
        "self_excluding": True,
        "artifact_root": strict_canonical_hash(members, prefix="public_share_protocol_root:"),
    }
    manifest = {
        **body,
        "manifest_id": strict_canonical_hash(body, prefix="public_share_protocol_manifest:"),
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
    root = repo_root.resolve()
    review = external_audit_path.read_bytes()
    authorization = authorize(review)
    freeze, parent_files = freeze_parent(root)
    source, legacy = (json.loads(parent_files[p]) for p in ("source_binding.json", "contract.json"))
    authority = record(
        "source_authority",
        implementation=source_group(root, source_commit, source_tree, SOURCE_PATHS),
        declared_references=source_group(
            root, models.PARENT_SOURCE_COMMIT, models.PARENT_SOURCE_TREE, REFERENCE_PATHS
        ),
        transitive_import_or_runtime_environment_closure_claimed=False,
    )
    context = public_context(source, legacy)
    protocol = protocol_contract(context)
    binding = fixture_binding()
    initial = make_state(context, protocol, initial_dynamic())
    request_for(initial, protocol)  # Public whitelist/identity validation, no callback.
    member = next(
        m for m in authority["implementation"]["members"] if m["path"] == binding["source_path"]
    )
    require(member["sha256"] == binding["source_sha256"], "registration.source_member")
    registration = record(
        "generator_registration",
        source_authority_id=authority["id"],
        generator_binding_id=binding["id"],
        fixture_source_member=member,
        before_first_callback=True,
        actual_callable_check="loaded_class_bound_method_and_compiled_source_code_each_exchange",
        callback_source_only_not_full_runtime_closure=True,
    )
    saved = None
    if replay_from is not None:
        saved = files_at(replay_from)
        previous = json.loads(saved["artifact_manifest.json"])
        validate_manifest(saved, previous["manifest_id"], previous["artifact_root"])
    writer = DurableArtifactWriter(output_directory)
    writer.create_root()
    writer.write_bytes("external_review.txt", review)
    writer.write_bytes("operator_directive.txt", models.DIRECTIVE.encode())
    for name, obj in (
        ("authorization", authorization),
        ("predecessor_freeze", freeze),
        ("source_authority", authority),
        ("public_context", context),
        ("protocol_contract", protocol),
        ("generator_binding", binding),
        ("generator_registration", registration),
    ):
        writer.write_json(name + ".json", obj)
    registration_audit = audit_registration(authority, binding, registration)
    require(registration_audit["passed"], "registration.independent_chain")
    writer.write_json("registration_audit.json", registration_audit)
    receipt = record(
        "registration_receipt",
        authorization_id=authorization["id"],
        source_authority_id=authority["id"],
        protocol_id=protocol["id"],
        public_context_id=context["id"],
        generator_registration_id=registration["id"],
        before_first_callback=True,
        write_events=list(writer.events),
        no_replace=True,
    )
    writer.write_json("registration_receipt.json", receipt)
    for name in ("source_authority", "protocol_contract", "generator_registration"):
        require(
            json.loads(writer.read_bytes(name + ".json"))
            == {
                "source_authority": authority,
                "protocol_contract": protocol,
                "generator_registration": registration,
            }[name],
            "registration.persisted_bytes",
        )
    session_root = writer.root / "session"
    new_callbacks = new_kernels = 0
    if saved is None:
        generator = PublicRequestFixture()
        verify_callback(generator, binding)
        engine = ProtocolEngine(context, protocol, source, legacy, binding, session_root)
        try:
            while engine.current_state()["phase"] != "terminal":
                engine.exchange(generator)
        except Exception as error:
            writer.write_json(
                "execution_stopped.json",
                record(
                    "execution_stopped",
                    failure_stage=getattr(error, "stage", "session.unexpected_failure"),
                    error_type=type(error).__name__,
                    retries=0,
                    no_fallback=True,
                ),
            )
        engine.finish()
        new_callbacks, new_kernels = generator.calls, engine.kernel_calls
    else:
        for name, data in sorted(saved.items()):
            if name.startswith("session/") or name == "execution_stopped.json":
                writer.write_bytes(name, data)
    actual = read_session_records(session_root)
    independent = audit_session(context, protocol, source, legacy, binding, session_root)
    writer.write_json("independent_validation.json", independent)
    controls = run_controls(protocol, source, legacy, actual["initial_state"], actual["events"])
    writer.write_json("direct_controls.json", controls)
    require(files_at(root / models.PARENT) == parent_files, "freeze.parent_unchanged")
    manifest = actual["manifest"]
    counts = {
        "positive_protocol_sessions": 1,
        "generator_callbacks": manifest["generator_callbacks"],
        "actions": sum(e["execution"] is not None for e in actual["events"]),
        "updates": sum(
            e["receipt"]["admitted"] and e["submission"]["parsed"]["kind"] == "update"
            for e in actual["events"]
        ),
        "accepted_claims": sum(e["claim"] is not None for e in actual["events"]),
        "finals": sum(e["final"] is not None for e in actual["events"]),
        "kernel_calls": manifest["kernel_calls"],
        "Provider_calls": 0,
        "credential_reads": 0,
        "GPU_calls": 0,
        "new_quotient_comparisons": 0,
        "old_candidate_runtime_calls": 0,
        "source_rescans": 0,
    }
    gates = [
        {
            "gate": "G0",
            "scope": "authorization, frozen parent and committed declared source",
            "passed": True,
        },
        {
            "gate": "G1",
            "scope": "public projection and registered callback ownership",
            "passed": registration_audit["passed"] and independent["protocol_valid"],
        },
        {
            "gate": "G2",
            "scope": "one actual generator-update session and independent QA",
            "passed": independent["qualified"]
            and counts["generator_callbacks"] == 7
            and counts["actions"]
            == counts["updates"]
            == counts["accepted_claims"]
            == counts["kernel_calls"]
            == 3
            and counts["finals"] == 1,
        },
        {
            "gate": "G3",
            "scope": "direct admission controls only",
            "passed": controls["both_initial_choices_admitted"]
            and controls["same_initial_state_for_both"]
            and controls["all_rejected"]
            and controls["reject_update_admitted_without_claim"]
            and controls["source_state_and_transcript_unchanged"],
        },
        {
            "gate": "G4",
            "scope": "zero external execution; no historical witness expansion",
            "passed": True,
        },
    ]
    gate = record(
        "gate_evaluation",
        gates=gates,
        passed=sum(g["passed"] for g in gates),
        failed=sum(not g["passed"] for g in gates),
    )
    writer.write_json("gate_evaluation.json", gate)
    report = record(
        "report",
        stage=models.STAGE,
        status="passed_as_scoped" if gate["failed"] == 0 else "failed_as_scoped",
        authorization_id=authorization["id"],
        predecessor_freeze_id=freeze["id"],
        source_authority_id=authority["id"],
        protocol_id=protocol["id"],
        public_context_id=context["id"],
        generator_registration_id=registration["id"],
        session_manifest_id=manifest["id"],
        independent_validation=independent,
        counts=counts,
        gate_evaluation_id=gate["id"],
        historical_W_share=1,
        historical_finite_classes=2,
        historical_compound_task_W=None,
        new_W_share=None,
        new_semantic_class_count=None,
        model_reachability=None,
        model_class_probabilities=None,
        contribution_novelty_training_utility=None,
        reject_update_actual_branch_or_replanning_tested=False,
        fixture_exposure="full common evidence including disclosed total",
        parent_bytes_unchanged=True,
        next_stage_authorized=False,
        old_mainline="remains_paused",
    )
    writer.write_json("report.json", report)
    decision = record(
        "decision",
        status=report["status"],
        report_id=report["id"],
        stop_after_registered_session=True,
        next_stage_authorized=False,
        provider_adapter_or_model_test_executed=False,
        old_mainline="remains_paused",
    )
    writer.write_json("decision.json", decision)
    final_manifest = _manifest(writer, report)
    if saved is not None:
        require(files_at(writer.root) == saved, "rebuild.byte_equality")
    return {
        "report": report,
        "manifest": final_manifest,
        "new_generator_callbacks": new_callbacks,
        "new_kernel_calls": new_kernels,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--external-audit", type=Path, required=True)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--source-tree", required=True)
    parser.add_argument("--output-directory", type=Path, required=True)
    parser.add_argument("--replay-from", type=Path)
    args = parser.parse_args()
    result = build_preflight(
        repo_root=args.repo_root,
        external_audit_path=args.external_audit,
        source_commit=args.source_commit,
        source_tree=args.source_tree,
        output_directory=args.output_directory,
        replay_from=args.replay_from,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
