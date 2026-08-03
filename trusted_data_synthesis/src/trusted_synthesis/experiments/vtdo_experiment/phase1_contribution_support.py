from __future__ import annotations

import argparse
import gc
import hashlib
import json
import os
from collections import defaultdict
from pathlib import Path
from typing import Any

from trusted_synthesis.experiments.vtdo_experiment.multistate import (
    FinanceTaskStateArtifact,
    load_finance_multi_state_artifacts,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_probe_gpu import (
    TARGET_STRATEGIES,
    _adapter_tensor_sha256,
    _baseline_lora_model,
    _evaluate,
    _load_records,
    _load_tokenizer,
    _read_json,
    _record_from_state,
    _seed_everything,
    _selected_states,
    _write_json,
)
from trusted_synthesis.experiments.vtdo_experiment.schema import VTDOTrainingRecord
from trusted_synthesis.hashing import canonical_hash

CONTRIBUTION_SUPPORT_VERSION = "finance_contribution_evaluation_support.v3"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _select_balanced_artifacts(
    artifacts: tuple[FinanceTaskStateArtifact, ...],
    *,
    count: int,
    salt: str,
) -> tuple[FinanceTaskStateArtifact, ...]:
    groups: defaultdict[str, list[FinanceTaskStateArtifact]] = defaultdict(list)
    for artifact in artifacts:
        groups[artifact.omega.task.public.task_type].append(artifact)
    for values in groups.values():
        values.sort(
            key=lambda item: (
                canonical_hash(
                    {"salt": salt, "artifact_id": item.artifact_id},
                    prefix="finance_contribution_support_order:",
                ),
                item.artifact_id,
            )
        )
    selected: list[FinanceTaskStateArtifact] = []
    cursor = 0
    group_names = tuple(sorted(groups))
    while len(selected) < count:
        progressed = False
        for name in group_names:
            values = groups[name]
            if cursor >= len(values):
                continue
            selected.append(values[cursor])
            progressed = True
            if len(selected) == count:
                break
        if not progressed:
            break
        cursor += 1
    if len(selected) != count:
        raise ValueError(f"only {len(selected)} artifacts available for requested {count}")
    return tuple(selected)


def _task_semantic_signature(artifact: FinanceTaskStateArtifact) -> str:
    public = artifact.omega.task.public
    return canonical_hash(
        {
            "task_type": public.task_type,
            "program_skeleton": public.program_skeleton,
            "retrieval_scope": public.retrieval_scope,
            "answer_schema": public.answer_schema,
        },
        prefix="finance_task_semantic_signature:",
    )


def _artifact_evidence_version_ids(
    artifact: FinanceTaskStateArtifact,
) -> frozenset[str]:
    return frozenset(
        item.evidence_version_id for item in artifact.omega.public_corpus.evidence
    )


def _compact_record(artifact: FinanceTaskStateArtifact) -> VTDOTrainingRecord:
    states = {state.strategy: state for state in _selected_states(artifact)}
    return _record_from_state(
        artifact,
        states["compact_direct"],
        "B2_validity",
        sampling_weight=1.0,
    )


def prepare(args: argparse.Namespace) -> None:
    if args.internal_validation_count < 5 or args.final_test_count < 5:
        raise ValueError("Contribution support requires at least five records per evaluation role")
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    artifacts_path = Path(args.artifacts_path).resolve()
    source_probe_path = Path(args.source_probe_plan).resolve()
    source_baseline_path = Path(args.source_baseline_report).resolve()
    source_probe = _read_json(source_probe_path)
    source_baseline = _read_json(source_baseline_path)
    if source_baseline["plan_hash"] != source_probe["plan_hash"]:
        raise ValueError("source beneficiary report does not replay its Probe plan")
    source_records_path = Path(source_probe["records_path"]).resolve()
    source_records = _load_records(source_records_path)
    baseline_ids = tuple(source_probe["baseline_record_ids"])
    baseline_records = tuple(source_records[record_id] for record_id in baseline_ids)

    prior_plans = tuple(_read_json(Path(path).resolve()) for path in args.prior_population_plans)
    previously_used_task_ids = {record.task_id for record in source_records.values()}
    for plan in prior_plans:
        previously_used_task_ids.update(str(value) for value in plan["selected_task_ids"])

    disjoint_paths = tuple(Path(path).resolve() for path in args.disjoint_artifact_paths)
    disjoint_artifacts = tuple(
        artifact
        for path in disjoint_paths
        for artifact in load_finance_multi_state_artifacts(path)
    )
    if not disjoint_artifacts:
        raise ValueError("Contribution support requires a non-empty disjoint Artifact pool")
    disjoint_task_ids = {artifact.omega.task.task_id for artifact in disjoint_artifacts}
    disjoint_task_signatures = {
        _task_semantic_signature(artifact) for artifact in disjoint_artifacts
    }
    disjoint_evidence_versions = {
        evidence_version_id
        for artifact in disjoint_artifacts
        for evidence_version_id in _artifact_evidence_version_ids(artifact)
    }
    previously_used_task_ids.update(disjoint_task_ids)

    artifacts = load_finance_multi_state_artifacts(artifacts_path)
    rejected_task_id_overlap = {
        artifact.omega.task.task_id
        for artifact in artifacts
        if artifact.omega.task.task_id in previously_used_task_ids
    }
    rejected_semantic_overlap = {
        artifact.omega.task.task_id
        for artifact in artifacts
        if _task_semantic_signature(artifact) in disjoint_task_signatures
    }
    rejected_evidence_overlap = {
        artifact.omega.task.task_id
        for artifact in artifacts
        if _artifact_evidence_version_ids(artifact) & disjoint_evidence_versions
    }
    freshness_rejected_task_ids = (
        rejected_task_id_overlap
        | rejected_semantic_overlap
        | rejected_evidence_overlap
    )
    eligible = tuple(
        artifact
        for artifact in artifacts
        if artifact.omega.task.task_id not in freshness_rejected_task_ids
        and all(
            strategy in {state.strategy for state in artifact.accepted_states}
            for strategy in TARGET_STRATEGIES
        )
    )
    internal_artifacts = _select_balanced_artifacts(
        eligible,
        count=args.internal_validation_count,
        salt="internal_validation",
    )
    internal_task_ids = {artifact.omega.task.task_id for artifact in internal_artifacts}
    final_artifacts = _select_balanced_artifacts(
        tuple(
            artifact
            for artifact in eligible
            if artifact.omega.task.task_id not in internal_task_ids
        ),
        count=args.final_test_count,
        salt="untouched_final_test",
    )
    internal_records = tuple(_compact_record(artifact) for artifact in internal_artifacts)
    final_records = tuple(_compact_record(artifact) for artifact in final_artifacts)
    records = (*baseline_records, *internal_records, *final_records)
    if len({record.record_id for record in records}) != len(records):
        raise ValueError("Contribution support records overlap")
    records_path = output_dir / "evaluation_support_records.jsonl"
    records_path.write_text(
        "".join(record.model_dump_json() + "\n" for record in records),
        encoding="utf-8",
    )
    additional_excluded_task_ids = (
        previously_used_task_ids
        | freshness_rejected_task_ids
        | internal_task_ids
        | {artifact.omega.task.task_id for artifact in final_artifacts}
    )
    values: dict[str, Any] = {
        "experiment_version": CONTRIBUTION_SUPPORT_VERSION,
        "artifacts_path": str(artifacts_path),
        "artifacts_sha256": _sha256(artifacts_path),
        "source_probe_plan_path": str(source_probe_path),
        "source_probe_plan_hash": source_probe["plan_hash"],
        "source_baseline_report_path": str(source_baseline_path),
        "source_baseline_report_hash": source_baseline["report_hash"],
        "prior_population_plan_paths": tuple(
            str(Path(path).resolve()) for path in args.prior_population_plans
        ),
        "prior_population_plan_hashes": tuple(plan["plan_hash"] for plan in prior_plans),
        "disjoint_artifact_paths": tuple(str(path) for path in disjoint_paths),
        "disjoint_artifact_sha256": tuple(_sha256(path) for path in disjoint_paths),
        "disjoint_task_count": len(disjoint_task_ids),
        "disjoint_task_semantic_signature_count": len(disjoint_task_signatures),
        "disjoint_evidence_version_count": len(disjoint_evidence_versions),
        "strict_freshness_contract": {
            "task_identity_overlap_allowed": False,
            "task_semantic_signature_overlap_allowed": False,
            "evidence_version_overlap_allowed": False,
        },
        "freshness_funnel": {
            "candidate_task_count": len(artifacts),
            "rejected_task_identity_overlap_count": len(rejected_task_id_overlap),
            "rejected_task_semantic_overlap_count": len(rejected_semantic_overlap),
            "rejected_evidence_overlap_count": len(rejected_evidence_overlap),
            "unique_rejected_task_count": len(freshness_rejected_task_ids),
            "strictly_fresh_task_count": len(artifacts) - len(freshness_rejected_task_ids),
        },
        "model_dir": source_probe["model_dir"],
        "base_model_manifest_hash": source_probe["base_model_manifest_hash"],
        "beneficiary_adapter_dir": source_baseline["adapter_dir"],
        "beneficiary_adapter_tensor_sha256": source_baseline["adapter_tensor_sha256"],
        "beneficiary_model_state_id": source_baseline["model_state_id"],
        "beneficiary_checkpoint_hash": source_baseline["checkpoint_hash"],
        "records_path": str(records_path),
        "records_sha256": _sha256(records_path),
        "baseline_record_ids": baseline_ids,
        "internal_validation_record_ids": tuple(record.record_id for record in internal_records),
        "final_test_record_ids": tuple(record.record_id for record in final_records),
        "internal_validation_task_ids": tuple(
            artifact.omega.task.task_id for artifact in internal_artifacts
        ),
        "final_test_task_ids": tuple(artifact.omega.task.task_id for artifact in final_artifacts),
        "additional_excluded_task_ids": tuple(sorted(additional_excluded_task_ids)),
        "selection_policy": "task_type_round_robin_then_salted_canonical_hash",
        "selected_task_semantic_signatures": tuple(
            sorted(
                _task_semantic_signature(artifact)
                for artifact in (*internal_artifacts, *final_artifacts)
            )
        ),
        "internal_validation_set_id": canonical_hash(
            tuple(record.record_id for record in internal_records),
            prefix="finance_contribution_internal_validation:",
        ),
        "final_test_set_id": canonical_hash(
            tuple(record.record_id for record in final_records),
            prefix="finance_contribution_final_test:",
        ),
        "evaluation_seed": args.evaluation_seed,
        "numeric_policy": {
            "float32_matmul_precision": "high",
            "cuda_matmul_allow_tf32": True,
        },
        "claim_boundary": (
            "These records expand Contribution evaluation support only. They are disjoint "
            "from the Phase 1.2 horizon-selection tasks and must not train the beneficiary."
        ),
    }
    values["plan_hash"] = canonical_hash(
        values,
        prefix="finance_contribution_evaluation_support_plan:",
    )
    _write_json(output_dir / "plan.json", values)
    print(json.dumps(values, ensure_ascii=False, indent=2, sort_keys=True))


def evaluate(args: argparse.Namespace) -> None:
    os.environ["CUDA_VISIBLE_DEVICES"] = str(args.gpu_id)
    import torch

    output_dir = Path(args.output_dir).resolve()
    plan = _read_json(output_dir / "plan.json")
    if plan["experiment_version"] != CONTRIBUTION_SUPPORT_VERSION:
        raise ValueError("unsupported Contribution evaluation-support plan")
    artifacts_path = Path(plan["artifacts_path"])
    if _sha256(artifacts_path) != plan["artifacts_sha256"]:
        raise ValueError("Contribution support task Artifact changed after planning")
    disjoint_paths = tuple(Path(path) for path in plan["disjoint_artifact_paths"])
    if tuple(_sha256(path) for path in disjoint_paths) != tuple(
        plan["disjoint_artifact_sha256"]
    ):
        raise ValueError("Contribution support disjoint Artifact pool changed")
    disjoint_artifacts = tuple(
        artifact
        for path in disjoint_paths
        for artifact in load_finance_multi_state_artifacts(path)
    )
    disjoint_signatures = {
        _task_semantic_signature(artifact) for artifact in disjoint_artifacts
    }
    disjoint_evidence_versions = {
        evidence_version_id
        for artifact in disjoint_artifacts
        for evidence_version_id in _artifact_evidence_version_ids(artifact)
    }
    selected_task_ids = set(plan["internal_validation_task_ids"]) | set(
        plan["final_test_task_ids"]
    )
    selected_artifacts = tuple(
        artifact
        for artifact in load_finance_multi_state_artifacts(artifacts_path)
        if artifact.omega.task.task_id in selected_task_ids
    )
    if {artifact.omega.task.task_id for artifact in selected_artifacts} != selected_task_ids:
        raise ValueError("Contribution support Objective task set is incomplete")
    if any(
        _task_semantic_signature(artifact) in disjoint_signatures
        or bool(_artifact_evidence_version_ids(artifact) & disjoint_evidence_versions)
        for artifact in selected_artifacts
    ):
        raise ValueError("Contribution support Objective tasks violate strict freshness")
    records_path = Path(plan["records_path"])
    if _sha256(records_path) != plan["records_sha256"]:
        raise ValueError("evaluation-support records changed after planning")
    source_probe = _read_json(Path(plan["source_probe_plan_path"]))
    source_baseline = _read_json(Path(plan["source_baseline_report_path"]))
    if source_probe["plan_hash"] != plan["source_probe_plan_hash"]:
        raise ValueError("source Probe plan changed after support planning")
    if source_baseline["report_hash"] != plan["source_baseline_report_hash"]:
        raise ValueError("source beneficiary report changed after support planning")
    records = _load_records(records_path)
    _seed_everything(int(plan["evaluation_seed"]))
    tokenizer = _load_tokenizer(Path(plan["model_dir"]))
    torch.cuda.reset_peak_memory_stats()
    model = _baseline_lora_model(
        Path(plan["model_dir"]),
        Path(plan["beneficiary_adapter_dir"]),
    )
    if _adapter_tensor_sha256(model) != plan["beneficiary_adapter_tensor_sha256"]:
        raise ValueError("evaluation support loaded another beneficiary Adapter")
    validation_records = tuple(
        records[record_id] for record_id in plan["internal_validation_record_ids"]
    )
    final_records = tuple(records[record_id] for record_id in plan["final_test_record_ids"])
    validation_performance, validation_loss, validation_tokens = _evaluate(
        model,
        tokenizer,
        validation_records,
    )
    final_performance, final_loss, final_tokens = _evaluate(model, tokenizer, final_records)
    report: dict[str, Any] = {
        "experiment_version": CONTRIBUTION_SUPPORT_VERSION,
        "plan_hash": plan["plan_hash"],
        "source_beneficiary_report_hash": source_baseline["report_hash"],
        "model_state_id": plan["beneficiary_model_state_id"],
        "checkpoint_hash": plan["beneficiary_checkpoint_hash"],
        "base_model_manifest_hash": plan["base_model_manifest_hash"],
        "adapter_dir": plan["beneficiary_adapter_dir"],
        "adapter_tensor_sha256": plan["beneficiary_adapter_tensor_sha256"],
        "training_record_ids": plan["baseline_record_ids"],
        "internal_validation_record_ids": plan["internal_validation_record_ids"],
        "validation_performance": validation_performance,
        "validation_negative_log_likelihood": validation_loss,
        "validation_supervised_tokens": validation_tokens,
        "final_test_record_ids": plan["final_test_record_ids"],
        "final_test_performance": final_performance,
        "final_test_negative_log_likelihood": final_loss,
        "final_test_supervised_tokens": final_tokens,
        "evaluation_seed": plan["evaluation_seed"],
        "numeric_policy": plan["numeric_policy"],
        "peak_gpu_memory_bytes": int(torch.cuda.max_memory_allocated()),
        "gpu_name": torch.cuda.get_device_name(0),
        "status": "passed",
        "claim_boundary": plan["claim_boundary"],
    }
    report["report_hash"] = canonical_hash(
        report,
        prefix="finance_contribution_evaluation_support_report:",
    )
    _write_json(output_dir / "beneficiary_evaluation_report.json", report)
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    del model
    gc.collect()
    torch.cuda.empty_cache()


def main() -> None:
    parser = argparse.ArgumentParser(description="Freeze disjoint Contribution evaluation support")
    subparsers = parser.add_subparsers(dest="command", required=True)
    prepare_parser = subparsers.add_parser("prepare")
    prepare_parser.add_argument("--artifacts-path", required=True)
    prepare_parser.add_argument("--source-probe-plan", required=True)
    prepare_parser.add_argument("--source-baseline-report", required=True)
    prepare_parser.add_argument("--prior-population-plans", required=True, nargs="+")
    prepare_parser.add_argument("--disjoint-artifact-paths", required=True, nargs="+")
    prepare_parser.add_argument("--output-dir", required=True)
    prepare_parser.add_argument("--internal-validation-count", type=int, default=6)
    prepare_parser.add_argument("--final-test-count", type=int, default=6)
    prepare_parser.add_argument("--evaluation-seed", type=int, default=20261100)
    evaluate_parser = subparsers.add_parser("evaluate")
    evaluate_parser.add_argument("--output-dir", required=True)
    evaluate_parser.add_argument("--gpu-id", type=int, required=True)
    args = parser.parse_args()
    if args.command == "prepare":
        prepare(args)
    else:
        evaluate(args)


if __name__ == "__main__":
    main()
