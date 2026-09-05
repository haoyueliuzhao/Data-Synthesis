"""Materialize an offline finite-support training representation; never train a Student."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from trusted_synthesis.canonical_json import canonical_json_bytes, strict_canonical_hash
from trusted_synthesis.experiments.qa_reasoning_finite_comparison.inputs import (
    files_at,
    source_group,
    validate_manifest,
)
from trusted_synthesis.experiments.qa_reasoning_fixed_fixture.runtime import DurableArtifactWriter

from .controls import run_controls
from .independent import audit_training
from .inputs import assert_unchanged, export_rows, load_inputs, validate_text_dataset
from .loss import collate, decode_arrays, encode_arrays, run_loss_checks
from .models import (
    DIRECTIVE,
    REVIEW_BYTES,
    REVIEW_SHA256,
    STAGE,
    identity,
    record,
    representation_contract,
    require,
    sha,
)
from .safety import offline_cpu_guard
from .tokenization import register_tokenizer, tokenize_rows
from .weights import build_kernel, build_views, mass_summary

SOURCE_PATHS = tuple(
    "trusted_data_synthesis/src/trusted_synthesis/experiments/qa_reasoning_share_training_preflight/"
    + name
    for name in (
        "__init__.py",
        "models.py",
        "inputs.py",
        "tokenization.py",
        "weights.py",
        "loss.py",
        "independent.py",
        "controls.py",
        "safety.py",
        "preflight.py",
    )
)
REFERENCE_PATHS = (
    "trusted_data_synthesis/src/trusted_synthesis/canonical_json.py",
    "trusted_data_synthesis/src/trusted_synthesis/experiments/qa_reasoning_finite_comparison/inputs.py",
    "trusted_data_synthesis/src/trusted_synthesis/experiments/qa_reasoning_fixed_fixture/runtime.py",
    "trusted_data_synthesis/src/trusted_synthesis/experiments/qa_reasoning_share_quotient_measurement/inputs.py",
    "trusted_data_synthesis/src/trusted_synthesis/experiments/qa_reasoning_share_model_pilot/independent.py",
    "trusted_data_synthesis/config/vtdo_qwen2_5_7b_500k.json",
)
DEFAULT_DIRECTORY = (
    "trusted_data_synthesis/artifacts/qa_reasoning_share_training_preflight/"
    "finance_qa_vnext_finite_support_training_representation_and_class_weight_intervention_preflight_v1_20260906"
)


def _authority(root: Path, commit: str, tree: str) -> dict[str, Any]:
    return record(
        "source_authority",
        implementation=source_group(root, commit, tree, SOURCE_PATHS),
        references=source_group(root, commit, tree, REFERENCE_PATHS),
        declared_source_members_only=True,
        full_transitive_runtime_closure_claimed=False,
        source_freeze_precedes_formal_materialization=True,
        known_historical_data_development_is_blind_confirmation=False,
        old_qualification_quotient_or_training_driver_called=False,
    )


def _authorization(review: bytes, contract: dict[str, Any]) -> dict[str, Any]:
    require(
        len(review) == REVIEW_BYTES and sha(review) == REVIEW_SHA256, "preflight.review_authority"
    )
    return record(
        "authorization",
        stage=STAGE,
        operator_directive=DIRECTIVE,
        operator_directive_bytes=len(DIRECTIVE.encode()),
        operator_directive_sha256=sha(DIRECTIVE.encode()),
        external_review_bytes=len(review),
        external_review_sha256=sha(review),
        predecessor_audit="PASS_AS_SCOPED",
        mandatory_revision=False,
        current_operator_directive_authorizes_this_preflight=True,
        representation_contract_id=contract["id"],
        Provider_calls=0,
        credential_reads=0,
        new_candidate_runtime_executions=0,
        new_model_sessions=0,
        new_sources_or_tasks=0,
        Student_parameter_loads=0,
        Student_forward_passes=0,
        Student_parameter_updates=0,
        GPU_jobs=0,
        training_or_production_release=False,
        Contribution_evaluation=False,
        old_mainline="remains_paused",
        further_Student_experiments_authorized=False,
    )


def _tokens(dataset: dict[str, Any], binding: dict[str, Any]) -> dict[str, Any]:
    return record(
        "tokenized_dataset",
        dataset_id=dataset["id"],
        tokenizer_binding_id=binding["id"],
        representation_contract_id=dataset["representation_contract_id"],
        rows=tokenize_rows(dataset["rows"], binding),
        truncated=False,
        target_mask_policy="exact original assistant content only",
    )


def _gates(
    text_validation: dict[str, Any],
    independent: dict[str, Any],
    loss_checks: dict[str, Any],
    controls: dict[str, Any],
) -> dict[str, Any]:
    items = [
        (
            "G0",
            "exact original admitted request/target provenance and complete exclusions",
            text_validation["passed"],
        ),
        (
            "G1",
            "actual tokenization, content-only mask, padding and no truncation",
            independent["passed"],
        ),
        ("G2", "fixed finite kernel and exact P/Q class-only weight views", independent["passed"]),
        (
            "G3",
            "applied CPU loss equality and isolated counterfactual controls",
            loss_checks["passed"] and controls["failed"] == 0,
        ),
    ]
    return record(
        "gate_evaluation",
        gates=[
            {"gate": name, "object": title, "passed": bool(passed)} for name, title, passed in items
        ],
        passed=sum(bool(passed) for _, _, passed in items),
        failed=sum(not passed for _, _, passed in items),
        Student_performance_or_balancing_benefit_is_a_gate=False,
    )


def _report(inputs: dict[str, Any], objects: dict[str, Any]) -> dict[str, Any]:
    dataset, tokens, kernel = (
        objects["text_dataset"],
        objects["tokenized_dataset"],
        objects["materialization_kernel"],
    )
    return record(
        "report",
        stage=STAGE,
        status="finite_support_class_weight_intervention_preflight_completed",
        object_ids={name: value["id"] for name, value in objects.items()},
        parent_quotient_report_id=inputs["quotient_report"]["id"],
        original_partition_id=inputs["partition"]["id"],
        original_assignment_ids=[item["id"] for item in inputs["assignments"]],
        original_state_ids=[item["state_id"] for item in kernel["state_support"]],
        original_empirical_measurement_id=inputs["empirical_measurement"]["id"],
        original_empirical_q=inputs["empirical_measurement"]["q"],
        original_empirical_state_frequencies=inputs["empirical_measurement"]["state_frequencies"],
        counts=dataset["counts"],
        trajectories=kernel["trajectories"],
        sequence_length_min=min(row["sequence_length"] for row in tokens["rows"]),
        sequence_length_max=max(row["sequence_length"] for row in tokens["rows"]),
        maximum_sequence_length=objects["tokenizer_binding"]["maximum_sequence_length"],
        prompt_tokens=sum(row["prompt_token_count"] for row in tokens["rows"]),
        target_tokens=sum(row["target_token_count"] for row in tokens["rows"]),
        suffix_tokens=sum(row["suffix_token_count"] for row in tokens["rows"]),
        actual_batch_shape=objects["base_batch"]["shape"],
        class_weight_views=objects["mass_summary"]["views"],
        naive_normalization_diagnostics=objects["mass_summary"]["naive_normalizations"],
        controls_passed=objects["controls"]["passed"],
        loss_check_count=objects["loss_checks"]["check_count"],
        gate_passed=objects["gate_evaluation"]["passed"],
        gate_failed=objects["gate_evaluation"]["failed"],
        original_failure_M01_retained=True,
        rejected_history_removed_or_rewritten=False,
        original_qualification_or_quotient_reexecuted=False,
        new_Provider_calls=0,
        credential_reads=0,
        new_candidate_runtime_executions=0,
        new_sources_or_tasks=0,
        new_model_sessions=0,
        independent_trajectory_sample_count=5,
        new_statistical_samples=0,
        Student_parameter_loads=0,
        Student_forward_passes=0,
        Student_parameter_updates=0,
        GPU_jobs=0,
        training_or_production_release=False,
        empirical_baseline_is_optimal_claimed=False,
        balanced_Q_is_better_claimed=False,
        Q_is_coverage_prior_or_Novelty=False,
        Contribution=None,
        Student_utility=None,
        generalization_performance=None,
        old_mainline="remains_paused",
        next_stage_authorized=False,
    )


def _manifest(writer: DurableArtifactWriter, report: dict[str, Any]) -> dict[str, Any]:
    members: list[dict[str, Any]] = [
        {"relative_path": path, "sha256": sha(data), "byte_count": len(data)}
        for path, data in sorted(files_at(writer.root).items())
    ]
    body = {
        "schema_version": "share_training_manifest.v1",
        "members": members,
        "member_count": len(members),
        "member_bytes": sum(item["byte_count"] for item in members),
        "report_id": report["id"],
        "self_excluding": True,
        "artifact_root": strict_canonical_hash(members, prefix="share_training_root:"),
    }
    manifest = {
        **body,
        "manifest_id": strict_canonical_hash(body, prefix="share_training_manifest:"),
    }
    writer.write_json("artifact_manifest.json", manifest)
    validate_manifest(files_at(writer.root), manifest["manifest_id"], manifest["artifact_root"])
    return manifest


def build_preflight(
    *,
    repo_root: Path,
    external_audit: Path,
    source_commit: str,
    source_tree: str,
    output_directory: Path,
) -> dict[str, Any]:
    root = repo_root.resolve()
    require(not output_directory.exists(), "preflight.output_no_replace")
    objects: dict[str, Any] = {}
    with offline_cpu_guard() as scope:
        inputs = load_inputs(root)
        authority = _authority(root, source_commit, source_tree)
        binding = register_tokenizer(root)
        contract = representation_contract(binding)
        review = external_audit.read_bytes()
        objects.update(
            authorization=_authorization(review, contract),
            source_authority=authority,
            parent_freeze=inputs["parent_freeze"],
            tokenizer_binding=binding,
            representation_contract=contract,
        )
        writer = DurableArtifactWriter(output_directory)
        writer.create_root()
        writer.write_bytes("external_review.txt", review)
        writer.write_bytes("operator_directive.txt", DIRECTIVE.encode())
        for name, value in objects.items():
            writer.write_json(name + ".json", value)
        # Frozen source/rules/tokenizer/input bindings are durable before row materialization.
        dataset = export_rows(inputs, contract)
        tokens = _tokens(dataset, binding)
        kernel = build_kernel(inputs, dataset, tokens)
        batch, arrays, binary = collate(tokens, binding["pad_token_id"])
        views = build_views(inputs, dataset, tokens, kernel, batch)
        independent = audit_training(
            inputs, contract, dataset, tokens, kernel, batch, arrays, views
        )
        loss_checks, weight_binaries = run_loss_checks(
            dataset, tokens, kernel, batch, arrays, views
        )
        controls = run_controls(inputs, contract, dataset, tokens, kernel, batch, arrays, views)
        text_validation = validate_text_dataset(inputs, contract, dataset)
        objects.update(
            text_dataset=dataset,
            tokenized_dataset=tokens,
            materialization_kernel=kernel,
            base_batch=batch,
            text_validation=text_validation,
            independent_validation=independent,
            mass_summary=mass_summary(kernel, views),
            loss_checks=loss_checks,
            controls=controls,
            gate_evaluation=_gates(text_validation, independent, loss_checks, controls),
        )
        objects.update({"view_" + view["name"]: view for view in views})
        for name, value in objects.items():
            if not (writer.root / (name + ".json")).exists():
                writer.write_json(name + ".json", value)
        writer.write_bytes(
            "training_rows.jsonl",
            b"".join(canonical_json_bytes(row) + b"\n" for row in dataset["rows"]),
        )
        writer.write_bytes("base_batch.npz", binary)
        for name, data in weight_binaries.items():
            writer.write_bytes("weights/" + name + ".npz", data)
        for index, control in enumerate(controls["controls"], 1):
            writer.write_json(f"controls/{index:02d}_" + control["name"] + ".json", control)
        assert_unchanged(root, inputs)
    objects["runtime_scope"] = scope
    writer.write_json("runtime_scope.json", scope)
    report = _report(inputs, objects)
    require(report["gate_failed"] == 0, "preflight.failed_gate")
    writer.write_json("report.json", report)
    covered = files_at(writer.root)
    writer.write_json(
        "persistence.json",
        record(
            "persistence",
            covered_members=[
                {"relative_path": path, "sha256": sha(data), "byte_count": len(data)}
                for path, data in sorted(covered.items())
            ],
            write_events=writer.events,
            self_and_manifest_excluded=True,
            create_root_and_files_no_replace=True,
            file_then_directory_fsync=True,
            source_rules_tokenizer_written_before_training_rows=True,
        ),
    )
    manifest = _manifest(writer, report)
    validation = validate_artifacts(repo_root=root, artifact_directory=writer.root)
    files = files_at(writer.root)
    return {
        "report": report,
        "manifest": manifest,
        "validation": validation,
        "artifact_file_count": len(files),
        "artifact_total_bytes": sum(map(len, files.values())),
    }


def validate_artifacts(*, repo_root: Path, artifact_directory: Path) -> dict[str, Any]:
    files = files_at(artifact_directory)
    manifest = json.loads(files["artifact_manifest.json"])
    validate_manifest(files, manifest["manifest_id"], manifest["artifact_root"])

    def read(name: str) -> dict[str, Any]:
        data = files[name + ".json"]
        value = json.loads(data)
        require(canonical_json_bytes(value) == data, "validation.canonical_record")
        identity(value)
        return dict(value)

    names = (
        "authorization",
        "source_authority",
        "parent_freeze",
        "tokenizer_binding",
        "representation_contract",
        "text_dataset",
        "tokenized_dataset",
        "materialization_kernel",
        "base_batch",
        "text_validation",
        "independent_validation",
        "mass_summary",
        "loss_checks",
        "controls",
        "gate_evaluation",
        "view_P",
        "view_Q",
        "runtime_scope",
    )
    objects = {name: read(name) for name in names}
    with offline_cpu_guard() as scope:
        inputs = load_inputs(repo_root)
        authority = objects["source_authority"]["implementation"]
        require(
            objects["source_authority"]
            == _authority(repo_root, authority["commit"], authority["tree"]),
            "validation.source_authority",
        )
        binding = register_tokenizer(repo_root)
        contract = representation_contract(binding)
        require(
            objects["tokenizer_binding"] == binding
            and objects["representation_contract"] == contract,
            "validation.tokenizer_or_contract",
        )
        require(objects["parent_freeze"] == inputs["parent_freeze"], "validation.parent_freeze")
        require(files["operator_directive.txt"] == DIRECTIVE.encode(), "validation.directive")
        require(
            objects["authorization"] == _authorization(files["external_review.txt"], contract),
            "validation.authorization",
        )
        dataset, tokens = objects["text_dataset"], objects["tokenized_dataset"]
        require(
            objects["text_validation"] == validate_text_dataset(inputs, contract, dataset),
            "validation.text",
        )
        # Retokenize only these same 27 saved targets. No old quotient/qualification is run.
        require(tokens == _tokens(dataset, binding), "validation.actual_tokenization")
        kernel, batch = objects["materialization_kernel"], objects["base_batch"]
        arrays = decode_arrays(files["base_batch.npz"])
        require(encode_arrays(arrays) == files["base_batch.npz"], "validation.stable_npz")
        require(
            sha(files["base_batch.npz"]) == batch["npz_sha256"]
            and len(files["base_batch.npz"]) == batch["npz_byte_count"],
            "validation.batch_bytes",
        )
        views = [objects["view_P"], objects["view_Q"]]
        require(
            objects["independent_validation"]
            == audit_training(inputs, contract, dataset, tokens, kernel, batch, arrays, views),
            "validation.independent",
        )
        require(objects["mass_summary"] == mass_summary(kernel, views), "validation.mass_summary")
        loss_checks, weight_binaries = run_loss_checks(
            dataset, tokens, kernel, batch, arrays, views
        )
        require(objects["loss_checks"] == loss_checks, "validation.cpu_loss_recomputation")
        for name, data in weight_binaries.items():
            require(files["weights/" + name + ".npz"] == data, "validation.actual_weight_tensor")
        require(
            objects["controls"]
            == run_controls(inputs, contract, dataset, tokens, kernel, batch, arrays, views),
            "validation.controls",
        )
        require(
            objects["gate_evaluation"]
            == _gates(
                objects["text_validation"],
                objects["independent_validation"],
                loss_checks,
                objects["controls"],
            ),
            "validation.gates",
        )
        require(
            files["training_rows.jsonl"]
            == b"".join(canonical_json_bytes(row) + b"\n" for row in dataset["rows"]),
            "validation.jsonl",
        )
        assert_unchanged(repo_root, inputs)
    require(objects["runtime_scope"] == scope, "validation.runtime_scope")
    report = _report(inputs, objects)
    require(read("report") == report and manifest["report_id"] == report["id"], "validation.report")
    controls = objects["controls"]["controls"]
    control_paths = {
        f"controls/{index:02d}_" + item["name"] + ".json" for index, item in enumerate(controls, 1)
    }
    for index, item in enumerate(controls, 1):
        require(
            read(f"controls/{index:02d}_" + item["name"]) == item, "validation.control_inventory"
        )
    expected = (
        {name + ".json" for name in names}
        | control_paths
        | {
            "external_review.txt",
            "operator_directive.txt",
            "report.json",
            "persistence.json",
            "artifact_manifest.json",
            "training_rows.jsonl",
            "base_batch.npz",
            "weights/P.npz",
            "weights/Q.npz",
        }
    )
    require(set(files) == expected, "validation.artifact_inventory")
    persistence = read("persistence")
    covered = {
        path: data
        for path, data in files.items()
        if path not in {"persistence.json", "artifact_manifest.json"}
    }
    require(
        persistence["covered_members"]
        == [
            {"relative_path": path, "sha256": sha(data), "byte_count": len(data)}
            for path, data in sorted(covered.items())
        ],
        "validation.persistence_members",
    )
    events = persistence["write_events"]
    order = [event["relative_path"] for event in events[::2]]
    require(
        len(order) == len(set(order)) == len(covered) and set(order) == set(covered),
        "validation.write_totality",
    )
    require(
        events
        == [
            {"event_ordinal": 2 * index + offset + 1, "kind": kind, "relative_path": path}
            for index, path in enumerate(order)
            for offset, kind in enumerate(("file_fsync", "directory_fsync"))
        ],
        "validation.durable_write_order",
    )
    require(
        all(
            order.index(name + ".json") < order.index("text_dataset.json")
            for name in (
                "source_authority",
                "representation_contract",
                "parent_freeze",
                "tokenizer_binding",
            )
        ),
        "validation.freeze_before_rows",
    )
    return {
        "passed": True,
        "independent_validation_id": objects["independent_validation"]["id"],
        "same_27_rows_retokenized": True,
        "controlled_CPU_losses_recomputed": True,
        "old_qualification_or_quotient_reexecuted": False,
        "new_Provider_calls": 0,
        "Student_parameter_updates": 0,
    }


def replay_preflight(
    *, repo_root: Path, replay_from: Path, output_directory: Path
) -> dict[str, Any]:
    original = files_at(replay_from)
    validate_artifacts(repo_root=repo_root, artifact_directory=replay_from)
    source = json.loads(original["source_authority.json"])["implementation"]
    result = build_preflight(
        repo_root=repo_root,
        external_audit=replay_from / "external_review.txt",
        source_commit=source["commit"],
        source_tree=source["tree"],
        output_directory=output_directory,
    )
    require(files_at(replay_from) == original, "replay.original_changed")
    require(files_at(output_directory) == original, "replay.all_files_exact")
    return {**result, "all_files_byte_identical": True, "new_statistical_samples": 0}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", required=True, choices=("materialize", "validate", "replay"))
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--output-directory", type=Path)
    parser.add_argument("--external-audit", type=Path)
    parser.add_argument("--source-commit")
    parser.add_argument("--source-tree")
    parser.add_argument("--replay-from", type=Path)
    args = parser.parse_args()
    if args.mode == "materialize":
        require(
            all((args.output_directory, args.external_audit, args.source_commit, args.source_tree)),
            "cli.materialize_arguments",
        )
        result = build_preflight(
            repo_root=args.repo_root,
            external_audit=args.external_audit,
            source_commit=args.source_commit,
            source_tree=args.source_tree,
            output_directory=args.output_directory,
        )
    elif args.mode == "replay":
        require(
            args.replay_from is not None and args.output_directory is not None,
            "cli.replay_arguments",
        )
        result = replay_preflight(
            repo_root=args.repo_root,
            replay_from=args.replay_from,
            output_directory=args.output_directory,
        )
    else:
        require(args.replay_from is not None, "cli.validate_arguments")
        result = validate_artifacts(repo_root=args.repo_root, artifact_directory=args.replay_from)
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))


if __name__ == "__main__":
    main()
