from __future__ import annotations

import json
import random
from collections import Counter, defaultdict
from collections.abc import Iterable
from pathlib import Path
from typing import Any, Literal, cast

from trusted_synthesis.core.evaluation.answer import CandidateAnswerNormalizer
from trusted_synthesis.core.evaluation.critic.dataset import make_quality_critic_dataset
from trusted_synthesis.core.evaluation.critic.schema import (
    AcceptabilityLabel,
    QualityCriticDataset,
    QualityCriticExample,
)
from trusted_synthesis.core.evaluation.utility import UtilityCohort
from trusted_synthesis.core.operations.program import TaskProgramExecutor
from trusted_synthesis.core.task.program import InputRefKind
from trusted_synthesis.core.task.schema import PlanningTrack, RetrievalTrack
from trusted_synthesis.core.trajectory.schema import ActionType, Trajectory
from trusted_synthesis.experiments.agent_validation.schema import AgentValidationReport
from trusted_synthesis.experiments.agent_validation.tracks import materialize_track_variant
from trusted_synthesis.experiments.counterfactual_finance_fixture import (
    build_finance_counterfactual_cases,
)
from trusted_synthesis.experiments.cross_domain_contract_suite.fixtures import (
    build_pattern_validation_cases,
)
from trusted_synthesis.hashing import canonical_hash
from trusted_synthesis.runtime.agent.schema import AgentResponseContract

from .schema import (
    CohortDatasetManifest,
    SFTRecord,
    TrainingUtilityDataManifest,
    TrainingUtilityMVPConfig,
    TrainingUtilityReadinessReport,
)

SYSTEM_PROMPT = (
    "You are a proof-carrying evidence agent. Use only the supplied public task and "
    "evidence. Return one JSON object with schema_version, plan_summary, "
    "selected_evidence_ids, execution_trace, verification_result, and final_answer. "
    "Do not emit markdown or hidden reasoning. Bind concrete executions to public "
    "plan node IDs and parameters when a plan is given."
)


def load_agent_artifacts(
    artifact_dir: Path,
) -> tuple[AgentValidationReport, QualityCriticDataset]:
    report = AgentValidationReport.model_validate_json(
        (artifact_dir / "agent_validation_report.json").read_text(encoding="utf-8")
    )
    examples = tuple(
        QualityCriticExample.model_validate_json(line)
        for line in (artifact_dir / "quality_critic_dataset.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
        if line.strip()
    )
    dataset = make_quality_critic_dataset(examples)
    if report.critic_dataset_id != dataset.dataset_id:
        raise ValueError("agent report and Quality Critic dataset identities do not match")
    return report, dataset


def audit_training_utility_readiness(
    config: TrainingUtilityMVPConfig,
    report: AgentValidationReport,
    critic_dataset: QualityCriticDataset,
) -> TrainingUtilityReadinessReport:
    """Fail-closed capacity audit for every D1-D5 domain quota."""

    reference_records, _ = _reference_and_evaluation_records(config)
    expected_by_task = {item.task_id: item for item in reference_records}
    expected_task_ids = set(expected_by_task)
    pool_examples = tuple(
        item for item in critic_dataset.examples if item.task_id in expected_task_ids
    )
    real_examples = tuple(item for item in pool_examples if item.candidate_source == "real_agent")
    accepted = tuple(
        item
        for item in real_examples
        if item.contract_annotation.acceptability == AcceptabilityLabel.ACCEPT
    )
    prediction_task_ids = {
        item.task_id for item in report.samples if item.critic_prediction is not None
    }
    reviewed_accepted = tuple(item for item in accepted if item.task_id in prediction_task_ids)
    counterfactuals = tuple(
        item for item in pool_examples if item.candidate_source == "typed_counterfactual"
    )
    representable_real = _representable_example_records(
        real_examples,
        UtilityCohort.RANDOM_SYNTHETIC,
    )
    representable_counterfactual = _representable_example_records(
        counterfactuals,
        UtilityCohort.RANDOM_SYNTHETIC,
    )
    accepted_by_task = {item.task_id: item for item in accepted}
    repairable_task_ids: set[str] = set()
    for item in counterfactuals:
        clean = accepted_by_task.get(item.task_id)
        if clean is None:
            continue
        try:
            trajectory_to_response(Trajectory.model_validate(item.critic_input["trajectory"]))
            trajectory_to_response(Trajectory.model_validate(clean.critic_input["trajectory"]))
        except ValueError:
            continue
        repairable_task_ids.add(item.task_id)

    d1_counterfactual = round(config.cohort_size * config.d1_counterfactual_fraction)
    d4_repairs = round(config.cohort_size * config.d4_repair_fraction)
    required = {
        "expected_tasks": config.candidate_tasks_per_domain,
        "d1_real": (config.cohort_size - d1_counterfactual) // 3,
        "d1_counterfactual": d1_counterfactual // 3,
        "d3_accepted": config.cohort_size // 3,
        "d4_direct": (config.cohort_size - d4_repairs) // 3,
        "d4_repair": d4_repairs // 3,
        "d5_critic_reviewed": config.cohort_size // 3,
    }
    observed: dict[str, dict[str, int]] = {}
    blockers: list[str] = []
    real_task_ids = [item.task_id for item in real_examples]
    missing = sorted(expected_task_ids - set(real_task_ids))
    unexpected = sorted(set(real_task_ids) - expected_task_ids)
    duplicate_count = len(real_task_ids) - len(set(real_task_ids))
    if missing:
        blockers.append(f"missing_real_candidate_tasks={len(missing)}")
    if unexpected:
        blockers.append(f"unexpected_real_candidate_tasks={len(unexpected)}")
    if duplicate_count:
        blockers.append(f"duplicate_real_candidates={duplicate_count}")

    record_groups: dict[str, tuple[Any, ...]] = {
        "real_candidates": real_examples,
        "representable_real": representable_real,
        "accepted": accepted,
        "critic_reviewed_accepted": reviewed_accepted,
        "counterfactuals": counterfactuals,
        "representable_counterfactual": representable_counterfactual,
    }
    for domain in ("finance", "legal", "science"):
        domain_counts = {
            "expected_tasks": sum(item.domain == domain for item in reference_records),
            **{
                name: sum(item.domain == domain for item in records)
                for name, records in record_groups.items()
            },
            "repairable_tasks": sum(
                expected_by_task[task_id].domain == domain for task_id in repairable_task_ids
            ),
        }
        observed[domain] = domain_counts
        checks = {
            "expected_tasks": domain_counts["real_candidates"],
            "d1_real": domain_counts["representable_real"],
            "d1_counterfactual": domain_counts["representable_counterfactual"],
            "d3_accepted": domain_counts["accepted"],
            "d4_direct": domain_counts["accepted"],
            "d4_repair": domain_counts["repairable_tasks"],
            "d5_critic_reviewed": domain_counts["critic_reviewed_accepted"],
        }
        for requirement, observed_count in checks.items():
            required_count = required[requirement]
            if observed_count < required_count:
                blockers.append(f"{domain}:{requirement}={observed_count}<{required_count}")
    identity = {
        "config_hash": config.config_hash,
        "source_agent_run_id": report.run_id,
        "source_critic_dataset_id": critic_dataset.dataset_id,
        "required_per_domain": required,
        "observed_per_domain": observed,
        "blockers": tuple(sorted(blockers)),
    }
    return TrainingUtilityReadinessReport(
        config_hash=config.config_hash,
        source_agent_run_id=report.run_id,
        source_critic_dataset_id=critic_dataset.dataset_id,
        expected_real_candidate_count=len(expected_task_ids),
        observed_real_candidate_count=len(real_examples),
        accepted_real_candidate_count=len(accepted),
        critic_reviewed_accepted_count=len(reviewed_accepted),
        required_per_domain=required,
        observed_per_domain=observed,
        blockers=tuple(sorted(blockers)),
        status="blocked" if blockers else "ready",
        readiness_hash=canonical_hash(identity, prefix="training_utility_readiness:"),
    )


def build_training_utility_datasets(
    config: TrainingUtilityMVPConfig,
    report: AgentValidationReport,
    critic_dataset: QualityCriticDataset,
) -> tuple[
    dict[UtilityCohort, tuple[SFTRecord, ...]],
    tuple[SFTRecord, ...],
    TrainingUtilityDataManifest,
]:
    readiness = audit_training_utility_readiness(config, report, critic_dataset)
    if readiness.status != "ready":
        raise ValueError("training utility readiness blocked: " + "; ".join(readiness.blockers))
    reference_records, evaluation_records = _reference_and_evaluation_records(config)
    reference_by_task = {item.task_id: item for item in reference_records}
    expected_task_ids = set(reference_by_task)
    pool_examples = tuple(
        item for item in critic_dataset.examples if item.task_id in expected_task_ids
    )
    real_examples = tuple(item for item in pool_examples if item.candidate_source == "real_agent")
    if {item.task_id for item in real_examples} != expected_task_ids:
        raise ValueError(
            "real Agent artifacts must cover the exact resolved/plan-given candidate task pool"
        )
    if len(real_examples) != len(expected_task_ids):
        raise ValueError("real Agent artifacts must contain exactly one candidate per task")
    clean_examples = tuple(
        item
        for item in real_examples
        if item.contract_annotation.acceptability == AcceptabilityLabel.ACCEPT
    )
    prediction_by_task = {
        item.task_id: item.critic_prediction
        for item in report.samples
        if item.critic_prediction is not None
    }
    if len(clean_examples) < config.cohort_size:
        raise ValueError(
            f"D3 requires {config.cohort_size} accepted real candidates; "
            f"observed {len(clean_examples)}"
        )
    reviewed_clean = tuple(item for item in clean_examples if item.task_id in prediction_by_task)
    if len(reviewed_clean) < config.cohort_size:
        raise ValueError(
            f"D5 requires {config.cohort_size} Critic-reviewed accepted candidates; "
            f"observed {len(reviewed_clean)}"
        )

    d1_records = _d1_random_records(config, pool_examples)
    selected_reference = _balanced_take(
        tuple(reference_by_task.values()),
        config.cohort_size,
        config.seed + 2,
    )
    selected_clean = _balanced_take(
        tuple(
            _record_from_example(item, UtilityCohort.CONTRACT_FILTERED) for item in clean_examples
        ),
        config.cohort_size,
        config.seed + 3,
    )
    d4_records = _d4_counterfactual_calibrated_records(
        config,
        clean_examples,
        pool_examples,
    )
    ranked_reviewed = tuple(
        sorted(
            reviewed_clean,
            key=lambda item: (
                -float(prediction_by_task[item.task_id].accept_probability),
                item.example_id,
            ),
        )
    )
    d5_records = _balanced_ranked_take(
        tuple(
            _record_from_example(
                item,
                UtilityCohort.CRITIC_SELECTED,
                metadata={
                    "critic_accept_probability": prediction_by_task[
                        item.task_id
                    ].accept_probability,
                    "critic_prediction_id": prediction_by_task[item.task_id].prediction_id,
                },
            )
            for item in ranked_reviewed
        ),
        config.cohort_size,
    )
    cohorts = {
        UtilityCohort.RANDOM_SYNTHETIC: d1_records,
        UtilityCohort.REFERENCE_WORKFLOW: tuple(
            item.model_copy(update={"cohort": UtilityCohort.REFERENCE_WORKFLOW})
            for item in selected_reference
        ),
        UtilityCohort.CONTRACT_FILTERED: selected_clean,
        UtilityCohort.CONTRACT_COUNTERFACTUAL: d4_records,
        UtilityCohort.CRITIC_SELECTED: d5_records,
    }
    for cohort, records in cohorts.items():
        if len(records) != config.cohort_size:
            raise ValueError(
                f"{cohort.value} has {len(records)} records, expected {config.cohort_size}"
            )
        expected_per_domain = config.cohort_size // 3
        counts = Counter(item.domain for item in records)
        if set(counts.values()) != {expected_per_domain} or set(counts) != {
            "finance",
            "legal",
            "science",
        }:
            raise ValueError(f"{cohort.value} is not domain balanced: {dict(counts)}")
    training_task_ids = tuple(
        sorted({item.task_id for records in cohorts.values() for item in records})
    )
    evaluation_task_ids = tuple(sorted(item.task_id for item in evaluation_records))
    overlap = len(set(training_task_ids) & set(evaluation_task_ids))
    cohort_manifests = tuple(_cohort_manifest(cohort, cohorts[cohort]) for cohort in UtilityCohort)
    evaluation_hash = canonical_hash(
        tuple(item.record_hash for item in evaluation_records),
        prefix="training_utility_evaluation_dataset:",
    )
    identity = {
        "config_hash": config.config_hash,
        "source_agent_run_id": report.run_id,
        "source_agent_model": report.requested_model,
        "source_critic_dataset_id": critic_dataset.dataset_id,
        "cohort_hashes": tuple(item.dataset_hash for item in cohort_manifests),
        "evaluation_hash": evaluation_hash,
    }
    manifest = TrainingUtilityDataManifest(
        manifest_id=canonical_hash(identity, prefix="training_utility_data_manifest:"),
        config_hash=config.config_hash,
        source_agent_run_id=report.run_id,
        source_agent_model=report.requested_model,
        source_critic_dataset_id=critic_dataset.dataset_id,
        accepted_real_candidate_count=len(clean_examples),
        critic_reviewed_accepted_count=len(reviewed_clean),
        critic_model_ids=tuple(
            sorted(
                {
                    prediction.model_id
                    for prediction in prediction_by_task.values()
                    if prediction.example_id in {item.example_id for item in reviewed_clean}
                }
            )
        ),
        cohorts=cohort_manifests,
        evaluation_record_count=len(evaluation_records),
        evaluation_domain_counts=dict(
            sorted(Counter(item.domain for item in evaluation_records).items())
        ),
        evaluation_record_ids=tuple(item.record_id for item in evaluation_records),
        evaluation_dataset_hash=evaluation_hash,
        training_task_ids=training_task_ids,
        evaluation_task_ids=evaluation_task_ids,
        train_evaluation_overlap_count=overlap,
    )
    return cohorts, evaluation_records, manifest


def write_training_utility_datasets(
    output_dir: Path,
    cohorts: dict[UtilityCohort, tuple[SFTRecord, ...]],
    evaluation_records: tuple[SFTRecord, ...],
    manifest: TrainingUtilityDataManifest,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    for cohort, records in cohorts.items():
        _write_jsonl(output_dir / f"{cohort.value}.jsonl", records)
    _write_jsonl(output_dir / "evaluation.jsonl", evaluation_records)
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest.model_dump(mode="json"), ensure_ascii=False, indent=2, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )


def write_reference_training_preflight(
    config: TrainingUtilityMVPConfig,
    output_dir: Path,
) -> dict[str, Any]:
    """Materialize deterministic D2/evaluation records for a real model smoke test."""

    reference_records, evaluation_records = _reference_and_evaluation_records(config)
    selected = tuple(
        item.model_copy(update={"cohort": UtilityCohort.REFERENCE_WORKFLOW})
        for item in _balanced_take(
            reference_records,
            config.cohort_size,
            config.seed + 2,
        )
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    cohort_path = output_dir / f"{UtilityCohort.REFERENCE_WORKFLOW.value}.jsonl"
    evaluation_path = output_dir / "evaluation.jsonl"
    _write_jsonl(cohort_path, selected)
    _write_jsonl(evaluation_path, evaluation_records)
    manifest = {
        "kind": "reference_training_preflight",
        "config_hash": config.config_hash,
        "cohort": UtilityCohort.REFERENCE_WORKFLOW.value,
        "cohort_record_count": len(selected),
        "cohort_domain_counts": dict(sorted(Counter(item.domain for item in selected).items())),
        "cohort_dataset_hash": canonical_hash(
            tuple(item.record_hash for item in selected),
            prefix="training_utility_cohort_dataset:",
        ),
        "evaluation_record_count": len(evaluation_records),
        "evaluation_domain_counts": dict(
            sorted(Counter(item.domain for item in evaluation_records).items())
        ),
        "evaluation_dataset_hash": canonical_hash(
            tuple(item.record_hash for item in evaluation_records),
            prefix="training_utility_evaluation_dataset:",
        ),
        "training_evaluation_overlap_count": len(
            {item.task_id for item in selected} & {item.task_id for item in evaluation_records}
        ),
    }
    (output_dir / "reference_preflight_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return manifest


def load_sft_records(path: Path) -> tuple[SFTRecord, ...]:
    return tuple(
        SFTRecord.model_validate_json(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    )


def trajectory_to_response(trajectory: Trajectory) -> dict[str, Any]:
    operation_steps = tuple(
        step
        for step in trajectory.steps
        if step.program_node_id is not None
        and step.action in {ActionType.SELECT_EVIDENCE, ActionType.CALCULATE}
    )
    selected_step = next(
        (
            step
            for step in trajectory.steps
            if step.action == ActionType.SELECT_EVIDENCE and step.program_node_id is None
        ),
        None,
    )
    if not operation_steps:
        raise ValueError("trajectory cannot be represented as an Agent response contract")
    selected_evidence_ids = (
        selected_step.evidence_ids
        if selected_step is not None
        else tuple(
            dict.fromkeys(
                evidence_id for step in operation_steps for evidence_id in step.evidence_ids
            )
        )
    )
    if not selected_evidence_ids:
        raise ValueError("trajectory has no evidence selection lineage")
    plan_step = next(step for step in trajectory.steps if step.action == ActionType.PLAN)
    planning_track = plan_step.observation.get(
        "planning_track",
        PlanningTrack.PLAN_GIVEN.value,
    )
    execution_ids = {
        step.program_node_id: f"exec_{ordinal:03d}"
        for ordinal, step in enumerate(operation_steps, start=1)
        if step.program_node_id is not None
    }
    verify_step = next(
        (step for step in trajectory.steps if step.action == ActionType.VERIFY),
        None,
    )
    output_node_id = (
        verify_step.program_node_id
        if verify_step is not None
        else operation_steps[-1].program_node_id
    )
    assert output_node_id is not None
    payload = {
        "schema_version": "agent_response.v2",
        "plan_summary": "Select grounded evidence and execute the typed operation program.",
        "selected_evidence_ids": list(selected_evidence_ids),
        "execution_trace": {
            "trace_version": "agent_execution_trace.v1",
            "steps": [
                {
                    "execution_id": execution_ids[cast(str, step.program_node_id)],
                    "planned_node_id": (
                        step.program_node_id
                        if planning_track == PlanningTrack.PLAN_GIVEN.value
                        else None
                    ),
                    "operator_id": step.operator_id,
                    "tool_name": step.tool_name,
                    "input_refs": [
                        _operation_ref_to_execution_ref(ref, execution_ids)
                        for ref in step.input_refs
                    ],
                    "parameters": step.tool_input.get("parameters", {}),
                    "evidence_ids": list(step.evidence_ids),
                    "observation": {"result": step.observation.get("result", {})},
                    "status": step.status.value,
                    "rationale_summary": step.rationale_summary,
                }
                for step in operation_steps
            ],
            "output_execution_id": execution_ids[output_node_id],
        },
        "verification_result": (
            None if verify_step is None else verify_step.observation.get("verified_result")
        ),
        "final_answer": trajectory.final_answer,
    }
    AgentResponseContract.model_validate(payload)
    return payload


def _operation_ref_to_execution_ref(
    ref: str,
    execution_ids: dict[str, str],
) -> str:
    if not ref.startswith("operation:"):
        return ref
    node_id, separator, selector = ref.removeprefix("operation:").partition("#")
    try:
        execution_id = execution_ids[node_id]
    except KeyError as exc:
        raise ValueError(f"unresolved operation ref in trajectory: {ref}") from exc
    suffix = f"#{selector}" if separator else ""
    return f"execution:{execution_id}{suffix}"


def _record_from_example(
    example: QualityCriticExample,
    cohort: UtilityCohort,
    *,
    candidate_attempt: dict[str, Any] | None = None,
    target_override: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
) -> SFTRecord:
    trajectory = Trajectory.model_validate(example.critic_input["trajectory"])
    target = target_override or trajectory_to_response(trajectory)
    task = dict(example.critic_input["task"])
    evidence = list(example.critic_input["evidence_corpus"])
    return _make_record(
        cohort=cohort,
        task=task,
        evidence=evidence,
        target=target,
        source_kind=example.candidate_source,
        contract_label=example.contract_annotation.acceptability.value,
        candidate_attempt=candidate_attempt,
        metadata={"example_id": example.example_id, **(metadata or {})},
    )


def _make_record(
    *,
    cohort: UtilityCohort | Literal["evaluation"],
    task: dict[str, Any],
    evidence: list[dict[str, Any]],
    target: dict[str, Any],
    source_kind: str,
    contract_label: str | None,
    candidate_attempt: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
) -> SFTRecord:
    mode = "repair_candidate" if candidate_attempt is not None else "solve"
    user_payload: dict[str, Any] = {
        "mode": mode,
        "public_task": task,
        "evidence_corpus": evidence,
        "output_contract": {
            "schema_version": "agent_response.v2",
            "selected_evidence_ids": "array of supplied evidence IDs",
            "execution_trace": (
                "topologically ordered concrete executions with evidence and observations"
            ),
            "verification_result": "required when requested by the task",
            "final_answer": "structured result with grounded citations",
        },
    }
    if candidate_attempt is not None:
        user_payload["candidate_attempt_to_repair"] = candidate_attempt
        user_payload["repair_instruction"] = (
            "Identify and repair the candidate using only the public task and evidence. "
            "Return the corrected Agent response contract, not a critique."
        )
    user_prompt = json.dumps(user_payload, ensure_ascii=False, sort_keys=True)
    assistant_target = json.dumps(target, ensure_ascii=False, sort_keys=True)
    identity = {
        "cohort": cohort.value if isinstance(cohort, UtilityCohort) else cohort,
        "task_id": task["task_id"],
        "source_kind": source_kind,
        "user_prompt": user_prompt,
        "assistant_target": assistant_target,
    }
    return SFTRecord(
        record_id=canonical_hash(identity, prefix="training_utility_record:"),
        cohort=cohort,
        task_id=str(task["task_id"]),
        domain=str(task["domain"]),
        system_prompt=SYSTEM_PROMPT,
        user_prompt=user_prompt,
        assistant_target=assistant_target,
        source_kind=source_kind,
        contract_label=contract_label,
        counterfactual_repair=candidate_attempt is not None,
        metadata=dict(metadata or {}),
    )


def _d1_random_records(
    config: TrainingUtilityMVPConfig,
    examples: tuple[QualityCriticExample, ...],
) -> tuple[SFTRecord, ...]:
    positive = _representable_example_records(
        tuple(item for item in examples if item.candidate_source == "real_agent"),
        UtilityCohort.RANDOM_SYNTHETIC,
    )
    negative = _representable_example_records(
        tuple(item for item in examples if item.candidate_source == "typed_counterfactual"),
        UtilityCohort.RANDOM_SYNTHETIC,
    )
    negative_count = round(config.cohort_size * config.d1_counterfactual_fraction)
    positive_count = config.cohort_size - negative_count
    return tuple(
        (
            *_balanced_take(positive, positive_count, config.seed + 101),
            *_balanced_take(negative, negative_count, config.seed + 102),
        )
    )


def _d4_counterfactual_calibrated_records(
    config: TrainingUtilityMVPConfig,
    clean_examples: tuple[QualityCriticExample, ...],
    all_examples: tuple[QualityCriticExample, ...],
) -> tuple[SFTRecord, ...]:
    clean_by_task = {item.task_id: item for item in clean_examples}
    negative_by_domain: dict[str, list[QualityCriticExample]] = defaultdict(list)
    for item in all_examples:
        if item.candidate_source == "typed_counterfactual" and item.task_id in clean_by_task:
            negative_by_domain[item.domain].append(item)
    repair_count = round(config.cohort_size * config.d4_repair_fraction)
    direct_count = config.cohort_size - repair_count
    direct = _balanced_take(
        tuple(
            _record_from_example(item, UtilityCohort.CONTRACT_COUNTERFACTUAL)
            for item in clean_examples
        ),
        direct_count,
        config.seed + 401,
    )
    repairs: list[SFTRecord] = []
    per_domain = repair_count // 3
    for domain in ("finance", "legal", "science"):
        candidates = sorted(
            negative_by_domain[domain],
            key=lambda item: canonical_hash(
                {"seed": config.seed + 402, "example_id": item.example_id},
                prefix="counterfactual_repair_order:",
            ),
        )
        used_tasks: set[str] = set()
        for negative in candidates:
            if negative.task_id in used_tasks:
                continue
            clean = clean_by_task[negative.task_id]
            negative_trajectory = Trajectory.model_validate(negative.critic_input["trajectory"])
            clean_trajectory = Trajectory.model_validate(clean.critic_input["trajectory"])
            try:
                candidate_attempt = trajectory_to_response(negative_trajectory)
                target_override = trajectory_to_response(clean_trajectory)
            except ValueError:
                continue
            repairs.append(
                _record_from_example(
                    clean,
                    UtilityCohort.CONTRACT_COUNTERFACTUAL,
                    candidate_attempt=candidate_attempt,
                    target_override=target_override,
                    metadata={
                        "counterfactual_example_id": negative.example_id,
                        "failure_families": negative.contract_annotation.failure_families,
                    },
                )
            )
            used_tasks.add(negative.task_id)
            if len(used_tasks) >= per_domain:
                break
        if len(used_tasks) < per_domain:
            raise ValueError(f"D4 lacks counterfactual repairs for {domain}")
    return tuple((*direct, *repairs))


def _reference_and_evaluation_records(
    config: TrainingUtilityMVPConfig,
) -> tuple[tuple[SFTRecord, ...], tuple[SFTRecord, ...]]:
    total = config.candidate_tasks_per_domain + config.evaluation_tasks_per_domain
    cases = (
        *build_finance_counterfactual_cases(count=total),
        *build_pattern_validation_cases(per_domain=total),
    )
    domain_seen: Counter[str] = Counter()
    train: list[SFTRecord] = []
    evaluation: list[SFTRecord] = []
    for case in cases:
        ordinal = domain_seen[case.domain]
        domain_seen[case.domain] += 1
        task = materialize_track_variant(
            case.task,
            case.corpus,
            retrieval_track=RetrievalTrack.RESOLVED,
            planning_track=PlanningTrack.PLAN_GIVEN,
        )
        record = _make_record(
            cohort=(
                UtilityCohort.REFERENCE_WORKFLOW
                if ordinal < config.candidate_tasks_per_domain
                else "evaluation"
            ),
            task=task.public.model_dump(mode="json", exclude_none=True),
            evidence=[
                item.model_dump(mode="json", exclude_none=True) for item in case.corpus.evidence
            ],
            target=_reference_response(task, case.bundle, case.registry),
            source_kind="deterministic_reference_workflow",
            contract_label="accept",
            metadata={"fixture_ordinal": ordinal + 1},
        )
        (train if ordinal < config.candidate_tasks_per_domain else evaluation).append(record)
    return tuple(train), tuple(evaluation)


def _reference_response(task, bundle, registry) -> dict[str, Any]:
    """Render the deterministic program as a concrete Agent execution trace."""

    evidence_by_id = {item.evidence_id: item for item in bundle.evidence}
    execution = TaskProgramExecutor(registry).execute(
        task.oracle.task_program,
        evidence_by_id,
    )
    execution_ids = {
        node.node_id: f"exec_{ordinal:03d}"
        for ordinal, node in enumerate(task.oracle.task_program.nodes, start=1)
    }
    execution_steps = []
    for node in task.oracle.task_program.nodes:
        input_refs = []
        for ref in node.input_refs:
            prefix = "evidence:" if ref.kind == InputRefKind.EVIDENCE else "operation:"
            selector = f"#{ref.selector}" if ref.selector else ""
            input_refs.append(f"{prefix}{ref.ref_id}{selector}")
        definition = registry.require(node.operator_id)
        execution_steps.append(
            {
                "execution_id": execution_ids[node.node_id],
                "planned_node_id": node.node_id,
                "operator_id": node.operator_id,
                "tool_name": definition.tool_capability,
                "input_refs": [
                    _operation_ref_to_execution_ref(ref, execution_ids) for ref in input_refs
                ],
                "parameters": node.parameters,
                "evidence_ids": [
                    ref.ref_id for ref in node.input_refs if ref.kind == InputRefKind.EVIDENCE
                ],
                "observation": {"result": execution.node_outputs[node.node_id]},
                "status": "succeeded",
                "rationale_summary": "Execute the pinned typed operation node.",
            }
        )
    gold_evidence = tuple(
        evidence_by_id[evidence_id] for evidence_id in task.oracle.gold_evidence_ids
    )
    citations = [
        {
            "evidence_id": evidence_id,
            "source_id": evidence_by_id[evidence_id].source.source_id,
            "source_locator": evidence_by_id[evidence_id].source_locator.model_dump(
                mode="json",
                exclude_none=True,
            ),
        }
        for evidence_id in task.oracle.gold_evidence_ids
    ]
    response = {
        "schema_version": "agent_response.v2",
        "plan_summary": "Select grounded evidence and execute the typed operation program.",
        "selected_evidence_ids": list(task.oracle.gold_evidence_ids),
        "execution_trace": {
            "trace_version": "agent_execution_trace.v1",
            "steps": execution_steps,
            "output_execution_id": execution_ids[task.oracle.task_program.output_node_id],
        },
        "verification_result": execution.final_output,
        "final_answer": {
            "result": CandidateAnswerNormalizer().normalize_oracle(
                task,
                execution.final_output,
                gold_evidence,
            ),
            "citations": citations,
        },
    }
    AgentResponseContract.model_validate(response)
    return response


def _representable_example_records(
    examples: tuple[QualityCriticExample, ...],
    cohort: UtilityCohort,
) -> tuple[SFTRecord, ...]:
    records = []
    for example in examples:
        try:
            records.append(_record_from_example(example, cohort))
        except ValueError:
            continue
    return tuple(records)


def _balanced_take(
    records: tuple[SFTRecord, ...],
    count: int,
    seed: int,
) -> tuple[SFTRecord, ...]:
    if count % 3:
        raise ValueError("balanced record count must be divisible by three")
    per_domain = count // 3
    rng = random.Random(seed)
    output: list[SFTRecord] = []
    for domain in ("finance", "legal", "science"):
        domain_records = [item for item in records if item.domain == domain]
        rng.shuffle(domain_records)
        if len(domain_records) < per_domain:
            raise ValueError(f"insufficient {domain} records: {len(domain_records)} < {per_domain}")
        output.extend(domain_records[:per_domain])
    rng.shuffle(output)
    return tuple(output)


def _balanced_ranked_take(
    records: tuple[SFTRecord, ...],
    count: int,
) -> tuple[SFTRecord, ...]:
    if count % 3:
        raise ValueError("balanced record count must be divisible by three")
    per_domain = count // 3
    output: list[SFTRecord] = []
    for domain in ("finance", "legal", "science"):
        domain_records = [item for item in records if item.domain == domain]
        if len(domain_records) < per_domain:
            raise ValueError(f"insufficient ranked {domain} records")
        output.extend(domain_records[:per_domain])
    return tuple(output)


def _cohort_manifest(
    cohort: UtilityCohort,
    records: tuple[SFTRecord, ...],
) -> CohortDatasetManifest:
    record_ids = tuple(item.record_id for item in records)
    return CohortDatasetManifest(
        cohort=cohort,
        record_count=len(records),
        domain_counts=dict(sorted(Counter(item.domain for item in records).items())),
        source_kind_counts=dict(sorted(Counter(item.source_kind for item in records).items())),
        counterfactual_repair_count=sum(item.counterfactual_repair for item in records),
        record_ids=record_ids,
        dataset_hash=canonical_hash(
            tuple(item.record_hash for item in records),
            prefix="training_utility_cohort_dataset:",
        ),
    )


def _write_jsonl(path: Path, records: Iterable[SFTRecord]) -> None:
    path.write_text(
        "".join(
            json.dumps(item.model_dump(mode="json"), ensure_ascii=False, sort_keys=True) + "\n"
            for item in records
        ),
        encoding="utf-8",
    )
