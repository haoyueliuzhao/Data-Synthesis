from __future__ import annotations

import argparse
import gc
import hashlib
import json
import math
import os
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from trusted_synthesis.experiments.vtdo_experiment.multistate import (
    FinanceTaskStateArtifact,
    LineageStrategy,
    load_finance_multi_state_artifacts,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_contribution_gradient import (
    GRADIENT_STATE_STRATEGY_PRIORITY,
    _assert_trainable_parameter_precision,
    _configure_numeric_policy,
    _gradient_parameter_manifest,
    _load_numeric_contract,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_probe_gpu import (
    _adapter_tensor_sha256,
    _baseline_lora_model,
    _batch,
    _load_records,
    _load_tokenizer,
    _read_json,
    _record_from_state,
    _seed_everything,
    _write_json,
)
from trusted_synthesis.experiments.vtdo_experiment.schema import VTDOTrainingRecord
from trusted_synthesis.hashing import canonical_hash

CONTRIBUTION_SUPPORT_VERSION = "finance_contribution_evaluation_support.v7"
OBJECTIVE_STRATEGY_PRIORITY: tuple[LineageStrategy, ...] = GRADIENT_STATE_STRATEGY_PRIORITY
TARGET_IDENTIFIABILITY_ROLE = "target_identifiability"
TARGET_OBSERVABILITY_ROLE = "target_observability"
SEALED_DEVELOPMENT_ROLES = frozenset({TARGET_IDENTIFIABILITY_ROLE, TARGET_OBSERVABILITY_ROLE})
SUPPORT_RUN_ROLES = ("smoke", "production_candidate", *sorted(SEALED_DEVELOPMENT_ROLES))
PRODUCTION_ESTIMATION_RECORD_COUNT = 16
PRODUCTION_VALIDATION_RECORD_COUNT = 16
PRODUCTION_AUTHORIZATION_RECORD_COUNT = 16
TARGET_OBSERVABILITY_RECORD_COUNT = 128
STRATIFICATION_FIELDS = (
    "task_type",
    "context_length_bucket",
    "evidence_count_bucket",
    "program_depth_bucket",
    "state_strategy_family",
    "verification_family",
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _replay_support_numeric_contract(plan: dict[str, Any]) -> dict[str, Any]:
    path = Path(str(plan["numeric_contract_path"]))
    if not path.is_file() or _sha256(path) != plan["numeric_contract_sha256"]:
        raise ValueError("Contribution Support numeric contract changed after planning")
    contract = _load_numeric_contract(path)
    if contract != plan.get("numeric_contract"):
        raise ValueError("Contribution Support plan embeds another numeric contract")
    if contract["contract_hash"] != plan.get("numeric_contract_hash"):
        raise ValueError("Contribution Support numeric contract identity changed")
    if contract["selected_profile"] != plan.get("numeric_profile"):
        raise ValueError("Contribution Support numeric profile changed")
    return contract


def _count_bucket(value: int, *, boundaries: tuple[int, ...]) -> str:
    for boundary in boundaries:
        if value <= boundary:
            return f"le_{boundary}"
    return f"gt_{boundaries[-1]}"


def _task_program_depth(artifact: FinanceTaskStateArtifact) -> int:
    nodes = {node.node_id: node for node in artifact.omega.task.oracle.task_program.nodes}
    depths: dict[str, int] = {}
    pending = dict(nodes)
    while pending:
        progressed = False
        for node_id, node in tuple(pending.items()):
            if all(dependency in depths for dependency in node.dependencies):
                depths[node_id] = 1 + max(
                    (depths[dependency] for dependency in node.dependencies),
                    default=0,
                )
                del pending[node_id]
                progressed = True
        if not progressed:
            raise ValueError("Objective support Oracle program is cyclic or dangling")
    return max(depths.values(), default=0)


def _artifact_stratum(artifact: FinanceTaskStateArtifact) -> dict[str, str]:
    public = artifact.omega.task.public
    oracle = artifact.omega.task.oracle
    state_strategies = tuple(sorted(state.strategy for state in artifact.accepted_states))
    verification_profiles = {
        (
            round(state.assignment.attributes.verification_degree, 6),
            tuple(sorted(state.assignment.attributes.capability_tags)),
        )
        for state in artifact.accepted_states
    }
    verification_family = "||".join(
        f"degree_{degree:.6f}|" + "+".join(capability_tags)
        for degree, capability_tags in sorted(verification_profiles)
    )
    return {
        "task_type": public.task_type,
        "context_length_bucket": _count_bucket(len(public.instruction), boundaries=(120, 180, 240)),
        "evidence_count_bucket": _count_bucket(len(oracle.gold_evidence_ids), boundaries=(1, 2, 4)),
        "program_depth_bucket": _count_bucket(_task_program_depth(artifact), boundaries=(1, 2, 3)),
        "state_strategy_family": "+".join(state_strategies),
        "verification_family": verification_family,
    }


def _selection_priority(
    artifact: FinanceTaskStateArtifact,
    *,
    selected_counts: dict[str, Counter[str]],
    selected_joint_counts: Counter[str],
    salt: str,
) -> tuple[float, str]:
    stratum = _artifact_stratum(artifact)
    weights = {
        "context_length_bucket": 4.0,
        "evidence_count_bucket": 5.0,
        "program_depth_bucket": 5.0,
        "state_strategy_family": 3.0,
        "verification_family": 1.0,
    }
    joint = canonical_hash(stratum, prefix="finance_objective_support_stratum:")
    diversity_score = 8.0 / (1 + selected_joint_counts[joint])
    diversity_score += sum(
        weight / (1 + selected_counts[field][stratum[field]]) for field, weight in weights.items()
    )
    stable_order = canonical_hash(
        {"salt": salt, "artifact_id": artifact.artifact_id},
        prefix="finance_contribution_support_order:",
    )
    return diversity_score, stable_order


def _select_stratified_artifacts(
    artifacts: tuple[FinanceTaskStateArtifact, ...],
    *,
    count: int,
    salt: str,
) -> tuple[FinanceTaskStateArtifact, ...]:
    groups: defaultdict[str, list[FinanceTaskStateArtifact]] = defaultdict(list)
    for artifact in artifacts:
        groups[artifact.omega.task.public.task_type].append(artifact)
    selected: list[FinanceTaskStateArtifact] = []
    selected_counts: dict[str, Counter[str]] = {field: Counter() for field in STRATIFICATION_FIELDS}
    selected_joint_counts: Counter[str] = Counter()
    group_names = tuple(sorted(groups))
    while len(selected) < count:
        progressed = False
        for name in group_names:
            values = groups[name]
            if not values:
                continue
            chosen = max(
                values,
                key=lambda item: _selection_priority(
                    item,
                    selected_counts=selected_counts,
                    selected_joint_counts=selected_joint_counts,
                    salt=salt,
                ),
            )
            values.remove(chosen)
            selected.append(chosen)
            stratum = _artifact_stratum(chosen)
            for field in STRATIFICATION_FIELDS:
                selected_counts[field][stratum[field]] += 1
            selected_joint_counts[
                canonical_hash(stratum, prefix="finance_objective_support_stratum:")
            ] += 1
            progressed = True
            if len(selected) == count:
                break
        if not progressed:
            break
    if len(selected) != count:
        raise ValueError(f"only {len(selected)} artifacts available for requested {count}")
    return tuple(selected)


def _partition_manifest(
    artifacts: tuple[FinanceTaskStateArtifact, ...],
    records: tuple[VTDOTrainingRecord, ...],
) -> dict[str, Any]:
    if len(artifacts) != len(records):
        raise ValueError("Objective support partition Artifact and record counts differ")
    strata = tuple(_artifact_stratum(artifact) for artifact in artifacts)
    dimension_counts = {
        field: dict(sorted(Counter(row[field] for row in strata).items()))
        for field in STRATIFICATION_FIELDS
    }
    joint_counts = Counter(
        canonical_hash(row, prefix="finance_objective_support_stratum:") for row in strata
    )
    record_ids = tuple(record.record_id for record in records)
    return {
        "record_ids": record_ids,
        "task_ids": tuple(artifact.omega.task.task_id for artifact in artifacts),
        "set_id": canonical_hash(
            record_ids,
            prefix="finance_contribution_objective_partition:",
        ),
        "stratification_fields": STRATIFICATION_FIELDS,
        "dimension_counts": dimension_counts,
        "joint_stratum_counts": dict(sorted(joint_counts.items())),
        "joint_stratum_coverage": len(joint_counts),
        "objective_strategy_counts": dict(
            sorted(
                Counter(
                    str(record.metadata.get("objective_support_strategy")) for record in records
                ).items()
            )
        ),
    }


def _evaluate_strict(
    model: Any,
    tokenizer: Any,
    records: tuple[VTDOTrainingRecord, ...],
) -> tuple[float, float, int]:
    import torch

    model.eval()
    weighted_losses: list[float] = []
    token_count = 0
    with torch.inference_mode():
        for record in records:
            batch, supervised = _batch(tokenizer, record)
            output = model(**batch)
            weighted_losses.append(float(output.loss.detach().float().cpu()) * supervised)
            token_count += supervised
            del output, batch
    if token_count == 0:
        raise ValueError("Objective support evaluation has no supervised tokens")
    loss = math.fsum(weighted_losses) / token_count
    return -loss, loss, token_count


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
    return frozenset(item.evidence_version_id for item in artifact.omega.public_corpus.evidence)


def _objective_record(
    artifact: FinanceTaskStateArtifact,
    *,
    strategy: LineageStrategy,
) -> VTDOTrainingRecord:
    states = {state.strategy: state for state in artifact.accepted_states}
    if strategy not in states:
        raise ValueError(f"objective support lacks required strategy:{strategy}")
    return _record_from_state(
        artifact,
        states[strategy],
        "B2_validity",
        sampling_weight=1.0,
        extra_metadata={"objective_support_strategy": strategy},
    )


def _objective_records(
    artifacts: tuple[FinanceTaskStateArtifact, ...],
    *,
    salt: str,
) -> tuple[VTDOTrainingRecord, ...]:
    records = []
    for index, artifact in enumerate(artifacts):
        available = {state.strategy for state in artifact.accepted_states}
        candidates = tuple(
            strategy for strategy in OBJECTIVE_STRATEGY_PRIORITY if strategy in available
        )
        if len(candidates) < 3:
            raise ValueError("objective support requires at least three trajectory strategies")
        offset = int(
            canonical_hash(salt, prefix="finance_objective_strategy_salt:").rsplit(":", 1)[-1][:8],
            16,
        ) % len(candidates)
        strategy = candidates[(index + offset) % len(candidates)]
        records.append(_objective_record(artifact, strategy=strategy))
    return tuple(records)


def _required_partition_counts(run_role: str) -> tuple[int, int, int]:
    if run_role == TARGET_OBSERVABILITY_ROLE:
        return (TARGET_OBSERVABILITY_RECORD_COUNT,) * 3
    return (
        PRODUCTION_ESTIMATION_RECORD_COUNT,
        PRODUCTION_VALIDATION_RECORD_COUNT,
        PRODUCTION_AUTHORIZATION_RECORD_COUNT,
    )


def prepare(args: argparse.Namespace) -> None:
    if args.run_role not in SUPPORT_RUN_ROLES:
        raise ValueError("unknown Contribution support run role")
    if args.internal_validation_count < 8 or args.final_test_count < 4:
        raise ValueError("Contribution support smoke splits are too small")
    if args.internal_validation_count % 2:
        raise ValueError("Contribution internal support must split evenly")
    required_estimation, required_validation, required_authorization = _required_partition_counts(
        args.run_role
    )
    if args.run_role == "production_candidate" or args.run_role in SEALED_DEVELOPMENT_ROLES:
        if (
            args.internal_validation_count < required_estimation + required_validation
            or args.final_test_count < required_authorization
        ):
            raise ValueError(
                f"{args.run_role} Contribution support requires at least "
                f"{required_estimation} estimation, {required_validation} validation, "
                f"and {required_authorization} authorization records"
            )
    if args.run_role in SEALED_DEVELOPMENT_ROLES and (
        args.internal_validation_count != required_estimation + required_validation
        or args.final_test_count != required_authorization
    ):
        raise ValueError(
            f"{args.run_role} support requires exactly {required_estimation} estimation, "
            f"{required_validation} validation, and {required_authorization} sealed "
            "authorization records"
        )
    numeric_contract_path = Path(args.numeric_contract_path).resolve()
    numeric_contract = _load_numeric_contract(numeric_contract_path)
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
    prior_used_task_ids = {record.task_id for record in source_records.values()}
    for plan in prior_plans:
        prior_used_task_ids.update(str(value) for value in plan["selected_task_ids"])

    disjoint_paths = tuple(Path(path).resolve() for path in args.disjoint_artifact_paths)
    disjoint_artifacts = tuple(
        artifact for path in disjoint_paths for artifact in load_finance_multi_state_artifacts(path)
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
    support_selection_forbidden_task_ids = prior_used_task_ids | disjoint_task_ids

    artifacts = load_finance_multi_state_artifacts(artifacts_path)
    rejected_task_id_overlap = {
        artifact.omega.task.task_id
        for artifact in artifacts
        if artifact.omega.task.task_id in support_selection_forbidden_task_ids
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
        rejected_task_id_overlap | rejected_semantic_overlap | rejected_evidence_overlap
    )
    strategy_ineligible_task_ids = {
        artifact.omega.task.task_id
        for artifact in artifacts
        if len(
            {state.strategy for state in artifact.accepted_states}
            & set(OBJECTIVE_STRATEGY_PRIORITY)
        )
        < 3
    }
    eligible = tuple(
        artifact
        for artifact in artifacts
        if artifact.omega.task.task_id not in freshness_rejected_task_ids
        and artifact.omega.task.task_id not in strategy_ineligible_task_ids
    )
    estimation_count = args.internal_validation_count // 2
    estimation_artifacts = _select_stratified_artifacts(
        eligible,
        count=estimation_count,
        salt="gradient_estimation",
    )
    estimation_task_ids = {artifact.omega.task.task_id for artifact in estimation_artifacts}
    validation_artifacts = _select_stratified_artifacts(
        tuple(
            artifact
            for artifact in eligible
            if artifact.omega.task.task_id not in estimation_task_ids
        ),
        count=estimation_count,
        salt="gradient_validation",
    )
    validation_task_ids = {artifact.omega.task.task_id for artifact in validation_artifacts}
    authorization_artifacts = _select_stratified_artifacts(
        tuple(
            artifact
            for artifact in eligible
            if artifact.omega.task.task_id not in estimation_task_ids | validation_task_ids
        ),
        count=args.final_test_count,
        salt="untouched_authorization",
    )
    estimation_records = _objective_records(
        estimation_artifacts,
        salt="estimation_objective_support",
    )
    validation_records = _objective_records(
        validation_artifacts,
        salt="validation_objective_support",
    )
    authorization_records = _objective_records(
        authorization_artifacts,
        salt="authorization_objective_support",
    )
    objective_partitions = {
        "estimation": _partition_manifest(estimation_artifacts, estimation_records),
        "validation": _partition_manifest(validation_artifacts, validation_records),
        "authorization": _partition_manifest(
            authorization_artifacts,
            authorization_records,
        ),
    }
    records = (
        *baseline_records,
        *estimation_records,
        *validation_records,
        *authorization_records,
    )
    if len({record.record_id for record in records}) != len(records):
        raise ValueError("Contribution support records overlap")
    records_path = output_dir / "evaluation_support_records.jsonl"
    records_path.write_text(
        "".join(record.model_dump_json() + "\n" for record in records),
        encoding="utf-8",
    )
    objective_support_task_ids = (
        estimation_task_ids
        | validation_task_ids
        | {artifact.omega.task.task_id for artifact in authorization_artifacts}
    )
    objective_support_excluded_task_ids = prior_used_task_ids | objective_support_task_ids
    future_population_excluded_task_ids = (
        support_selection_forbidden_task_ids
        | freshness_rejected_task_ids
        | objective_support_task_ids
    )
    gradient_target_contract = {
        "task_ids": tuple(sorted(disjoint_task_ids)),
        "task_set_id": canonical_hash(
            tuple(sorted(disjoint_task_ids)),
            prefix="finance_gradient_target_task_set:",
        ),
        "semantic_signature_count": len(disjoint_task_signatures),
        "semantic_signature_set_id": canonical_hash(
            tuple(sorted(disjoint_task_signatures)),
            prefix="finance_gradient_target_semantic_signature_set:",
        ),
        "evidence_version_count": len(disjoint_evidence_versions),
        "evidence_version_set_id": canonical_hash(
            tuple(sorted(disjoint_evidence_versions)),
            prefix="finance_gradient_target_evidence_version_set:",
        ),
    }
    objective_support_exclusion_contract = {
        "task_ids": tuple(sorted(objective_support_excluded_task_ids)),
        "task_set_id": canonical_hash(
            tuple(sorted(objective_support_excluded_task_ids)),
            prefix="finance_objective_support_excluded_task_set:",
        ),
        "reason": "source_or_prior_use_or_objective_support_membership",
    }
    future_population_exclusion_contract = {
        "task_ids": tuple(sorted(future_population_excluded_task_ids)),
        "task_set_id": canonical_hash(
            tuple(sorted(future_population_excluded_task_ids)),
            prefix="finance_future_population_excluded_task_set:",
        ),
        "reason": "all_frozen_source_target_support_and_freshness_identities",
    }
    if disjoint_task_ids & objective_support_excluded_task_ids:
        raise ValueError("Gradient target tasks overlap Objective support exclusions")
    values: dict[str, Any] = {
        "experiment_version": CONTRIBUTION_SUPPORT_VERSION,
        "run_role": args.run_role,
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
            "strategy_ineligible_task_count": len(strategy_ineligible_task_ids),
            "eligible_task_count": len(eligible),
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
        "objective_partitions": objective_partitions,
        "gradient_target_contract": gradient_target_contract,
        "objective_support_exclusion_contract": objective_support_exclusion_contract,
        "future_population_exclusion_contract": future_population_exclusion_contract,
        "selection_policy": ("task_type_round_robin_then_multidimensional_inverse_frequency"),
        "objective_strategy_policy": (
            "salted_balanced_assignment_over_available_verified_trajectory_strategies"
        ),
        "objective_partition_contract": {
            "estimation_record_count": len(estimation_records),
            "validation_record_count": len(validation_records),
            "authorization_record_count": len(authorization_records),
            "minimum_production_records_per_partition": required_estimation,
            "partitions_disjoint": True,
            "partition_identity_explicit": True,
            "stratification_fields": STRATIFICATION_FIELDS,
            "evaluated_roles": (
                ("estimation", "validation")
                if args.run_role in SEALED_DEVELOPMENT_ROLES
                else ("estimation", "validation", "authorization")
            ),
            "authorization_objective_access": (
                "forbidden"
                if args.run_role in SEALED_DEVELOPMENT_ROLES
                else "allowed_by_source_protocol"
            ),
        },
        "selected_task_semantic_signatures": tuple(
            sorted(
                _task_semantic_signature(artifact)
                for artifact in (
                    *estimation_artifacts,
                    *validation_artifacts,
                    *authorization_artifacts,
                )
            )
        ),
        "evaluation_seed": args.evaluation_seed,
        "numeric_contract_path": str(numeric_contract_path),
        "numeric_contract_sha256": _sha256(numeric_contract_path),
        "numeric_contract": numeric_contract,
        "numeric_contract_hash": numeric_contract["contract_hash"],
        "numeric_profile": numeric_contract["selected_profile"],
        "claim_boundary": (
            f"These records support the {args.run_role} development study only; "
            "the Authorization partition is frozen but its Objective remains unopened."
            if args.run_role in SEALED_DEVELOPMENT_ROLES
            else (
                "These records expand Contribution evaluation support only. They are disjoint "
                "from the Phase 1.2 horizon-selection tasks and must not train the beneficiary."
            )
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
    numeric_contract = _replay_support_numeric_contract(plan)
    _configure_numeric_policy(numeric_contract["selected_profile"])
    artifacts_path = Path(plan["artifacts_path"])
    if _sha256(artifacts_path) != plan["artifacts_sha256"]:
        raise ValueError("Contribution support task Artifact changed after planning")
    disjoint_paths = tuple(Path(path) for path in plan["disjoint_artifact_paths"])
    if tuple(_sha256(path) for path in disjoint_paths) != tuple(plan["disjoint_artifact_sha256"]):
        raise ValueError("Contribution support disjoint Artifact pool changed")
    disjoint_artifacts = tuple(
        artifact for path in disjoint_paths for artifact in load_finance_multi_state_artifacts(path)
    )
    disjoint_signatures = {_task_semantic_signature(artifact) for artifact in disjoint_artifacts}
    disjoint_evidence_versions = {
        evidence_version_id
        for artifact in disjoint_artifacts
        for evidence_version_id in _artifact_evidence_version_ids(artifact)
    }
    target_contract = plan.get("gradient_target_contract")
    if not isinstance(target_contract, dict):
        raise ValueError("Contribution support Gradient target contract is missing")
    target_task_ids = {str(value) for value in target_contract.get("task_ids", ())}
    if target_task_ids != {artifact.omega.task.task_id for artifact in disjoint_artifacts}:
        raise ValueError("Contribution support Gradient target task identities changed")
    if target_contract.get("task_set_id") != canonical_hash(
        tuple(sorted(target_task_ids)),
        prefix="finance_gradient_target_task_set:",
    ):
        raise ValueError("Contribution support Gradient target task set is invalid")
    if target_contract.get("semantic_signature_set_id") != canonical_hash(
        tuple(sorted(disjoint_signatures)),
        prefix="finance_gradient_target_semantic_signature_set:",
    ):
        raise ValueError("Contribution support Gradient target semantics changed")
    if target_contract.get("evidence_version_set_id") != canonical_hash(
        tuple(sorted(disjoint_evidence_versions)),
        prefix="finance_gradient_target_evidence_version_set:",
    ):
        raise ValueError("Contribution support Gradient target Evidence changed")
    partitions = plan["objective_partitions"]
    if set(partitions) != {"estimation", "validation", "authorization"}:
        raise ValueError("Contribution support Objective partitions are incomplete")
    partition_task_sets = {name: set(values["task_ids"]) for name, values in partitions.items()}
    if any(
        left & right
        for index, left in enumerate(partition_task_sets.values())
        for right in tuple(partition_task_sets.values())[index + 1 :]
    ):
        raise ValueError("Contribution support Objective task partitions overlap")
    selected_task_ids = set().union(*partition_task_sets.values())
    exclusion_contract = plan.get("objective_support_exclusion_contract")
    if not isinstance(exclusion_contract, dict):
        raise ValueError("Contribution support exclusion contract is missing")
    objective_excluded_task_ids = {str(value) for value in exclusion_contract.get("task_ids", ())}
    if exclusion_contract.get("task_set_id") != canonical_hash(
        tuple(sorted(objective_excluded_task_ids)),
        prefix="finance_objective_support_excluded_task_set:",
    ):
        raise ValueError("Contribution support exclusion task set is invalid")
    if not selected_task_ids <= objective_excluded_task_ids:
        raise ValueError("Objective support tasks are absent from their exclusion contract")
    if target_task_ids & objective_excluded_task_ids:
        raise ValueError("Gradient target tasks overlap Objective support exclusions")
    future_contract = plan.get("future_population_exclusion_contract")
    if not isinstance(future_contract, dict):
        raise ValueError("Contribution support future-population contract is missing")
    future_excluded_task_ids = {str(value) for value in future_contract.get("task_ids", ())}
    if future_contract.get("task_set_id") != canonical_hash(
        tuple(sorted(future_excluded_task_ids)),
        prefix="finance_future_population_excluded_task_set:",
    ):
        raise ValueError("Contribution support future-population task set is invalid")
    if not target_task_ids | objective_excluded_task_ids <= future_excluded_task_ids:
        raise ValueError("Future-population exclusion contract is incomplete")
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
    parameter_manifest, parameter_manifest_hash = _gradient_parameter_manifest(model)
    _assert_trainable_parameter_precision(parameter_manifest)
    evaluated_roles = (
        ("estimation", "validation")
        if plan["run_role"] in SEALED_DEVELOPMENT_ROLES
        else ("estimation", "validation", "authorization")
    )
    if tuple(plan["objective_partition_contract"].get("evaluated_roles", ())) != evaluated_roles:
        raise ValueError("Contribution support Objective access contract changed")
    partition_results = {}
    for name in evaluated_roles:
        partition_records = tuple(
            records[record_id] for record_id in partitions[name]["record_ids"]
        )
        performance, loss, token_count = _evaluate_strict(
            model,
            tokenizer,
            partition_records,
        )
        partition_results[name] = {
            "record_ids": partitions[name]["record_ids"],
            "set_id": partitions[name]["set_id"],
            "performance": performance,
            "negative_log_likelihood": loss,
            "supervised_tokens": token_count,
        }
    report: dict[str, Any] = {
        "experiment_version": CONTRIBUTION_SUPPORT_VERSION,
        "run_role": plan["run_role"],
        "plan_hash": plan["plan_hash"],
        "source_beneficiary_report_hash": source_baseline["report_hash"],
        "model_state_id": plan["beneficiary_model_state_id"],
        "checkpoint_hash": plan["beneficiary_checkpoint_hash"],
        "base_model_manifest_hash": plan["base_model_manifest_hash"],
        "adapter_dir": plan["beneficiary_adapter_dir"],
        "adapter_tensor_sha256": plan["beneficiary_adapter_tensor_sha256"],
        "parameter_manifest": parameter_manifest,
        "parameter_manifest_hash": parameter_manifest_hash,
        "training_record_ids": plan["baseline_record_ids"],
        "objective_partition_results": partition_results,
        "authorization_objective_access": (
            "forbidden" if plan["run_role"] in SEALED_DEVELOPMENT_ROLES else "evaluated"
        ),
        "authorization_partition_frozen": True,
        "objective_partition_contract": plan["objective_partition_contract"],
        "objective_partitions": plan["objective_partitions"],
        "gradient_target_task_set_id": target_contract["task_set_id"],
        "objective_support_excluded_task_set_id": exclusion_contract["task_set_id"],
        "future_population_excluded_task_set_id": future_contract["task_set_id"],
        "evaluation_seed": plan["evaluation_seed"],
        "numeric_contract_hash": numeric_contract["contract_hash"],
        "numeric_profile": numeric_contract["selected_profile"],
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
    prepare_parser.add_argument("--numeric-contract-path", required=True)
    prepare_parser.add_argument("--prior-population-plans", required=True, nargs="+")
    prepare_parser.add_argument("--disjoint-artifact-paths", required=True, nargs="+")
    prepare_parser.add_argument("--output-dir", required=True)
    prepare_parser.add_argument(
        "--run-role",
        choices=SUPPORT_RUN_ROLES,
        required=True,
    )
    prepare_parser.add_argument("--internal-validation-count", type=int, default=32)
    prepare_parser.add_argument("--final-test-count", type=int, default=16)
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
