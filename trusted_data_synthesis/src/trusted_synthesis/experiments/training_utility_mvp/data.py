from __future__ import annotations

import json
import math
import random
from collections import Counter, defaultdict
from collections.abc import Iterable
from pathlib import Path
from typing import Any, cast

from trusted_synthesis.core.evaluation.answer import CandidateAnswerNormalizer
from trusted_synthesis.core.evaluation.critic.dataset import make_quality_critic_dataset
from trusted_synthesis.core.evaluation.critic.schema import (
    AcceptabilityLabel,
    QualityCriticDataset,
    QualityCriticExample,
)
from trusted_synthesis.core.evaluation.critic.selection import (
    QualityAwareSelector,
    QualitySelectionPolicy,
)
from trusted_synthesis.core.evaluation.utility import UtilityCohort
from trusted_synthesis.core.evidence.schema import EvidenceItem
from trusted_synthesis.core.operations.program import TaskProgramExecutor
from trusted_synthesis.core.operations.registry import OperationRegistry, default_registry
from trusted_synthesis.core.task.program import InputRefKind
from trusted_synthesis.core.task.schema import PlanningTrack, RetrievalTrack, TaskPublicSpec
from trusted_synthesis.core.trajectory.schema import ActionType, Trajectory
from trusted_synthesis.domains.legal.operations import legal_operation_registry
from trusted_synthesis.domains.science.operations import science_operation_registry
from trusted_synthesis.experiments.agent_validation.schema import AgentValidationReport
from trusted_synthesis.experiments.agent_validation.tracks import materialize_track_variant
from trusted_synthesis.experiments.counterfactual_finance_fixture import (
    build_finance_counterfactual_cases,
)
from trusted_synthesis.experiments.cross_domain_contract_suite.fixtures import (
    ContractCase,
    build_pattern_validation_cases,
)
from trusted_synthesis.hashing import canonical_hash
from trusted_synthesis.runtime.agent.host_execution import (
    execute_action_plan,
    make_host_execution_feedback,
)
from trusted_synthesis.runtime.agent.schema import (
    AgentActionPlanContract,
    AgentAnswerDecisionContract,
    AgentResponseContract,
    HostExecutionFeedbackContract,
)

from .schema import (
    SUPPORTED_TRAINING_UTILITY_AGENT_PROMPT_VERSIONS,
    TRAINING_UTILITY_AGENT_PROMPT_VERSION,
    CohortDatasetManifest,
    SFTMessage,
    SFTRecord,
    TrainingUtilityDataManifest,
    TrainingUtilityMVPConfig,
    TrainingUtilityReadinessReport,
)

LEGACY_SYSTEM_PROMPT = (
    "You are a proof-carrying evidence agent in a host-instrumented loop. Use only the "
    "supplied public task and evidence. First emit AgentActionPlanContract JSON. The host "
    "executes registered operations and returns immutable results as a tool message. Then "
    "emit AgentAnswerDecisionContract JSON. Never invent execution IDs, observations, source "
    "locators, or host verification fields. Do not emit markdown or hidden reasoning."
)

V5_SYSTEM_PROMPT = (
    "You are a proof-carrying evidence agent in a host-instrumented loop. Use only the "
    "supplied public task, evidence, and operation catalog. Your first reply must be one JSON "
    "object and nothing else. It may contain only schema_version, plan_summary, "
    "selected_evidence_ids, executions, and output_step_index. Each execution may contain only "
    "operator_id, inputs, parameters, and rationale_summary. Each input is either "
    '{"source":"evidence","evidence_id":"..."} or '
    '{"source":"step","step_index":1}; selector is the only optional input '
    "field. Do not copy kind, role_id, semantic_constraints, source_id, or other Program "
    "Skeleton fields into action inputs. The host executes the plan and returns an immutable "
    "tool message. Your second reply must be one JSON object and nothing else. It may contain "
    "only schema_version, result, cited_evidence_ids, status, and claims. Never invent execution "
    "IDs, observations, source locators, or host verification fields. Do not emit markdown or "
    "hidden reasoning."
)
SYSTEM_PROMPT = V5_SYSTEM_PROMPT + (
    " In the second response, result must exactly match public_task.answer_schema. "
    "Include every schema-required context field such as unit, currency, result_context, "
    "or source_id. Transform the immutable Host output into that public answer shape; do "
    "not copy a raw Host wrapper or omit required context."
)
TRAINING_UTILITY_AGENT_PROMPT_HASH = canonical_hash(
    SYSTEM_PROMPT, prefix="training_utility_agent_prompt:"
)


def _system_prompt_for_version(prompt_version: str) -> str:
    if prompt_version == TRAINING_UTILITY_AGENT_PROMPT_VERSION:
        return SYSTEM_PROMPT
    if prompt_version == "training_utility_agent_prompt.v5":
        return V5_SYSTEM_PROMPT
    if prompt_version in SUPPORTED_TRAINING_UTILITY_AGENT_PROMPT_VERSIONS:
        return LEGACY_SYSTEM_PROMPT
    raise ValueError(f"unsupported training utility prompt: {prompt_version}")


def _student_output_contract(prompt_version: str) -> dict[str, Any]:
    if prompt_version not in {
        "training_utility_agent_prompt.v5",
        TRAINING_UTILITY_AGENT_PROMPT_VERSION,
    }:
        return {
            "schema_version": "agent_action_plan.v1",
            "selected_evidence_ids": "array of supplied evidence IDs",
            "executions": "topologically ordered semantic operation decisions",
            "output_step_index": "one-based final output step",
        }
    return {
        "prompt_version": prompt_version,
        "first_response": {
            "schema_version": "agent_action_plan.v1",
            "allowed_fields": [
                "schema_version",
                "plan_summary",
                "selected_evidence_ids",
                "executions",
                "output_step_index",
            ],
            "execution_allowed_fields": [
                "operator_id",
                "inputs",
                "parameters",
                "rationale_summary",
            ],
            "evidence_input": {
                "source": "evidence",
                "evidence_id": "a supplied evidence ID",
                "selector": "optional selector",
            },
            "step_input": {
                "source": "step",
                "step_index": "one-based earlier execution index",
                "selector": "optional selector",
            },
            "forbidden_input_fields": [
                "kind",
                "role_id",
                "semantic_constraints",
                "source_id",
            ],
        },
        "second_response_after_tool": {
            "schema_version": "agent_answer_decision.v1",
            "allowed_fields": [
                "schema_version",
                "result",
                "cited_evidence_ids",
                "status",
                "claims",
            ],
            **(
                {
                    "result_contract": (
                        "exactly public_task.answer_schema, including unit, currency, "
                        "result_context, or source_id when required; never a raw Host wrapper"
                    )
                }
                if prompt_version == TRAINING_UTILITY_AGENT_PROMPT_VERSION
                else {}
            ),
        },
        "serialization": "one JSON object only; no markdown fences or commentary",
    }


def load_agent_artifacts(
    artifact_dir: Path,
) -> tuple[AgentValidationReport, QualityCriticDataset]:
    report = AgentValidationReport.model_validate_json(
        (artifact_dir / "agent_validation_report.json").read_text(encoding="utf-8")
    )
    critic_path = artifact_dir / "quality_critic_dataset.jsonl"
    with critic_path.open(encoding="utf-8") as critic_file:
        examples = tuple(
            QualityCriticExample.model_validate_json(line) for line in critic_file if line.strip()
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
        prompt_version=config.prompt_version,
    )
    representable_counterfactual = _representable_example_records(
        counterfactuals,
        UtilityCohort.RANDOM_SYNTHETIC,
        prompt_version=config.prompt_version,
    )
    accepted_by_task = {item.task_id: item for item in accepted}
    representable_accepted_task_ids = {
        item.task_id
        for item in _representable_example_records(
            accepted,
            UtilityCohort.CONTRACT_COUNTERFACTUAL,
            prompt_version=config.prompt_version,
        )
    }
    feedback_task_ids = {
        item.task_id
        for item in counterfactuals
        if item.task_id in accepted_by_task and item.task_id in representable_accepted_task_ids
    }
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

    shared_required = {
        "d1_real": config.cohort_size // 3,
        "d3_accepted": config.cohort_size // 3,
        "d4_feedback_clean": config.cohort_size // 3,
        "d5_critic_reviewed": config.cohort_size // 3,
    }
    if config.d1_construction_mode == "legacy_counterfactual_mix":
        d1_counterfactual = round(config.cohort_size * config.d1_counterfactual_fraction)
        shared_required["d1_real"] = (config.cohort_size - d1_counterfactual) // 3
        shared_required["d1_counterfactual"] = d1_counterfactual // 3
    if config.d4_training_format == "legacy_mixed_repair":
        d4_repairs = round(config.cohort_size * config.d4_repair_fraction)
        shared_required.pop("d4_feedback_clean")
        shared_required["d4_direct"] = (config.cohort_size - d4_repairs) // 3
        shared_required["d4_repair"] = d4_repairs // 3
    required = {
        domain: {
            "candidate_pool_tasks": config.candidate_task_target(domain),
            "attempted_tasks": math.ceil(
                config.candidate_task_target(domain) * config.minimum_real_candidate_completion_rate
            ),
            "real_candidates": math.ceil(
                config.candidate_task_target(domain) * config.minimum_real_candidate_completion_rate
            ),
            **shared_required,
        }
        for domain in ("finance", "legal", "science")
    }
    observed: dict[str, dict[str, int]] = {}
    blockers: list[str] = []
    attempted_task_ids = {
        item.task_id
        for item in report.samples
        if item.retrieval_track == RetrievalTrack.RESOLVED
        and item.planning_track == PlanningTrack.PLAN_GIVEN
    }
    real_task_ids = [item.task_id for item in real_examples]
    unexpected = sorted(attempted_task_ids - expected_task_ids)
    duplicate_count = len(real_task_ids) - len(set(real_task_ids))
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
            "attempted_tasks": sum(
                item.domain == domain
                and item.retrieval_track == RetrievalTrack.RESOLVED
                and item.planning_track == PlanningTrack.PLAN_GIVEN
                for item in report.samples
            ),
            **{
                name: sum(item.domain == domain for item in records)
                for name, records in record_groups.items()
            },
            "repairable_tasks": sum(
                expected_by_task[task_id].domain == domain for task_id in repairable_task_ids
            ),
            "feedback_clean_tasks": sum(
                expected_by_task[task_id].domain == domain for task_id in feedback_task_ids
            ),
        }
        domain_counts["unattempted_tasks"] = (
            domain_counts["expected_tasks"] - domain_counts["attempted_tasks"]
        )
        observed[domain] = domain_counts
        checks = {
            "attempted_tasks": domain_counts["attempted_tasks"],
            "real_candidates": domain_counts["real_candidates"],
            "d1_real": domain_counts["representable_real"],
            "d3_accepted": domain_counts["accepted"],
            "d4_feedback_clean": domain_counts["feedback_clean_tasks"],
            "d5_critic_reviewed": domain_counts["critic_reviewed_accepted"],
        }
        if config.d1_construction_mode == "legacy_counterfactual_mix":
            checks["d1_counterfactual"] = domain_counts["representable_counterfactual"]
        if config.d4_training_format == "legacy_mixed_repair":
            checks.pop("d4_feedback_clean")
            checks["d4_direct"] = domain_counts["accepted"]
            checks["d4_repair"] = domain_counts["repairable_tasks"]
        for requirement, observed_count in checks.items():
            required_count = required[domain][requirement]
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
    if not {item.task_id for item in real_examples}.issubset(expected_task_ids):
        raise ValueError(
            "real Agent artifacts contain tasks outside the pinned candidate task pool"
        )
    if len(real_examples) != len({item.task_id for item in real_examples}):
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
            record_from_quality_example(
                item,
                UtilityCohort.CONTRACT_FILTERED,
                prompt_version=config.prompt_version,
            )
            for item in clean_examples
        ),
        config.cohort_size,
        config.seed + 3,
    )
    d4_records = _d4_counterfactual_calibrated_records(
        config,
        clean_examples,
        pool_examples,
    )
    d5_examples, d5_selection = _select_d5_examples(
        config,
        reviewed_clean,
        prediction_by_task,
    )
    d5_records = tuple(
        record_from_quality_example(
            item,
            UtilityCohort.CRITIC_SELECTED,
            prompt_version=config.prompt_version,
            metadata={
                "critic_accept_probability": prediction_by_task[item.task_id].accept_probability,
                "critic_prediction_id": prediction_by_task[item.task_id].prediction_id,
                "quality_selection_id": d5_selection["selection_id"],
                "quality_selection_policy_hash": d5_selection["policy_hash"],
                "quality_vector_interpretation": "diagnostic_uncalibrated",
                "critic_role": "advisory_ranking_only",
            },
        )
        for item in d5_examples
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
    training_records = tuple(item for records in cohorts.values() for item in records)
    isolation = _evaluation_isolation(training_records, evaluation_records)
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
        "evaluation_isolation": isolation,
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
        evaluation_pattern_counts=_metadata_counts(evaluation_records, "pattern_id"),
        evaluation_program_signature_counts=_metadata_counts(
            evaluation_records, "program_signature"
        ),
        evaluation_worst_case_95ci_half_width=_evaluation_ci_by_domain(evaluation_records),
        evaluation_record_ids=tuple(item.record_id for item in evaluation_records),
        evaluation_dataset_hash=evaluation_hash,
        training_task_ids=training_task_ids,
        evaluation_task_ids=evaluation_task_ids,
        train_evaluation_overlap_count=overlap,
        train_evaluation_subject_overlap_count=isolation["subject_overlap_count"],
        train_evaluation_evidence_overlap_count=isolation["evidence_overlap_count"],
        train_evaluation_evidence_version_overlap_count=(
            isolation["evidence_version_overlap_count"]
        ),
        train_evaluation_source_record_overlap_count=(isolation["source_record_overlap_count"]),
        train_evaluation_binding_overlap_count=isolation["binding_overlap_count"],
        train_evaluation_program_signature_overlap_count=(
            isolation["program_signature_overlap_count"]
        ),
        d5_selection_id=d5_selection["selection_id"],
        d5_selection_policy_hash=d5_selection["policy_hash"],
        d5_selection_status=d5_selection["status"],
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
    isolation = _evaluation_isolation(selected, evaluation_records)
    output_dir.mkdir(parents=True, exist_ok=True)
    cohort_path = output_dir / f"{UtilityCohort.REFERENCE_WORKFLOW.value}.jsonl"
    evaluation_path = output_dir / "evaluation.jsonl"
    _write_jsonl(cohort_path, selected)
    _write_jsonl(evaluation_path, evaluation_records)
    manifest = {
        "kind": "reference_training_preflight",
        "config_hash": config.config_hash,
        "candidate_pool_record_count": len(reference_records),
        "candidate_pool_domain_counts": dict(
            sorted(Counter(item.domain for item in reference_records).items())
        ),
        "candidate_pool_pattern_counts": _metadata_counts(reference_records, "pattern_id"),
        "candidate_pool_program_signature_counts": _metadata_counts(
            reference_records, "program_signature"
        ),
        "candidate_pool_structural_group_count": len(
            {item.metadata["structural_group_id"] for item in reference_records}
        ),
        "cohort": UtilityCohort.REFERENCE_WORKFLOW.value,
        "cohort_record_count": len(selected),
        "cohort_domain_counts": dict(sorted(Counter(item.domain for item in selected).items())),
        "cohort_pattern_counts": _metadata_counts(selected, "pattern_id"),
        "cohort_program_signature_counts": _metadata_counts(selected, "program_signature"),
        "cohort_dataset_hash": canonical_hash(
            tuple(item.record_hash for item in selected),
            prefix="training_utility_cohort_dataset:",
        ),
        "evaluation_record_count": len(evaluation_records),
        "evaluation_domain_counts": dict(
            sorted(Counter(item.domain for item in evaluation_records).items())
        ),
        "evaluation_pattern_counts": _metadata_counts(evaluation_records, "pattern_id"),
        "evaluation_program_signature_counts": _metadata_counts(
            evaluation_records, "program_signature"
        ),
        "evaluation_worst_case_95ci_half_width": _evaluation_ci_by_domain(evaluation_records),
        "evaluation_dataset_hash": canonical_hash(
            tuple(item.record_hash for item in evaluation_records),
            prefix="training_utility_evaluation_dataset:",
        ),
        "training_evaluation_overlap_count": len(
            {item.task_id for item in selected} & {item.task_id for item in evaluation_records}
        ),
        "training_evaluation_identity_overlap": isolation,
        "evaluation_track": "internal_iid_contract",
        "external_benchmark_status": "not_executed",
    }
    (output_dir / "reference_preflight_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return manifest


def _metadata_counts(records: tuple[SFTRecord, ...], key: str) -> dict[str, int]:
    return dict(
        sorted(Counter(str(item.metadata.get(key) or "unknown") for item in records).items())
    )


def _evaluation_isolation(
    training_records: tuple[SFTRecord, ...],
    evaluation_records: tuple[SFTRecord, ...],
) -> dict[str, int]:
    training = _dataset_identity_sets(training_records)
    evaluation = _dataset_identity_sets(evaluation_records)
    return {
        f"{key}_overlap_count": len(training[key] & evaluation[key])
        for key in (
            "subject",
            "evidence",
            "evidence_version",
            "source_record",
            "binding",
            "program_signature",
        )
    }


def _dataset_identity_sets(records: tuple[SFTRecord, ...]) -> dict[str, set[str]]:
    identities: dict[str, set[str]] = {
        "subject": set(),
        "evidence": set(),
        "evidence_version": set(),
        "source_record": set(),
        "binding": set(),
        "program_signature": set(),
    }
    for record in records:
        program_signature = str(record.metadata.get("program_signature") or "")
        if program_signature:
            identities["program_signature"].add(program_signature)
        payload = json.loads(record.user_prompt)
        public_task = payload.get("public_task") or {}
        retrieval_scope = public_task.get("retrieval_scope") or {}
        identities["subject"].update(
            str(subject_id) for subject_id in retrieval_scope.get("subject_ids") or () if subject_id
        )
        for evidence in payload.get("evidence_corpus") or ():
            subject_id = str((evidence.get("subject") or {}).get("subject_id") or "")
            evidence_id = str(evidence.get("evidence_id") or "")
            evidence_version_id = str(evidence.get("evidence_version_id") or "")
            source_record_id = str((evidence.get("provenance") or {}).get("source_record_id") or "")
            if evidence_id:
                identities["evidence"].add(evidence_id)
            if evidence_version_id:
                identities["evidence_version"].add(evidence_version_id)
            if source_record_id:
                identities["source_record"].add(source_record_id)
            identities["binding"].add(
                canonical_hash(
                    {
                        "domain": evidence.get("domain"),
                        "subject_id": subject_id,
                        "predicate": evidence.get("predicate"),
                        "temporal_context": evidence.get("temporal_context"),
                        "scope": evidence.get("scope"),
                        "definition_id": (evidence.get("definition") or {}).get("definition_id"),
                    },
                    prefix="training_utility_binding_identity:",
                )
            )
    return identities


def _evaluation_ci_by_domain(records: tuple[SFTRecord, ...]) -> dict[str, float]:
    counts = Counter(item.domain for item in records)
    return {
        domain: 1.96 * (0.25 / count) ** 0.5 for domain, count in sorted(counts.items()) if count
    }


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
        "schema_version": "agent_response.v3",
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


def record_from_quality_example(
    example: QualityCriticExample,
    cohort: UtilityCohort | str,
    *,
    prompt_version: str = TRAINING_UTILITY_AGENT_PROMPT_VERSION,
    candidate_attempt: dict[str, Any] | None = None,
    target_override: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
    sampling_weight: float = 1.0,
) -> SFTRecord:
    trajectory = Trajectory.model_validate(example.critic_input["trajectory"])
    target = target_override or trajectory_to_response(trajectory)
    task = dict(example.critic_input["task"])
    public_task = TaskPublicSpec.model_validate(task)
    evidence = list(example.critic_input["evidence_corpus"])
    return make_sft_record(
        cohort=cohort,
        task=task,
        evidence=evidence,
        target=target,
        source_kind=example.candidate_source,
        contract_label=example.contract_annotation.acceptability.value,
        prompt_version=prompt_version,
        candidate_attempt=candidate_attempt,
        metadata={
            **_task_structure_metadata(public_task),
            "example_id": example.example_id,
            **(metadata or {}),
        },
        sampling_weight=sampling_weight,
    )


def make_sft_record(
    *,
    cohort: UtilityCohort | str,
    task: dict[str, Any],
    evidence: list[dict[str, Any]],
    target: dict[str, Any],
    source_kind: str,
    contract_label: str | None,
    prompt_version: str = TRAINING_UTILITY_AGENT_PROMPT_VERSION,
    candidate_attempt: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
    sampling_weight: float = 1.0,
) -> SFTRecord:
    system_prompt = _system_prompt_for_version(prompt_version)
    action_plan, host_execution, answer_decision = _student_contracts_from_response(
        target,
        task=task,
        evidence=evidence,
    )
    mode = "repair_candidate" if candidate_attempt is not None else "solve"
    user_payload: dict[str, Any] = {
        "mode": mode,
        "public_task": task,
        "evidence_corpus": evidence,
        "operation_catalog": _student_operation_catalog(target),
        "output_contract": _student_output_contract(prompt_version),
    }
    if candidate_attempt is not None:
        user_payload["candidate_attempt_to_repair"] = _model_owned_candidate_attempt(
            candidate_attempt
        )
        user_payload["repair_instruction"] = (
            "Identify and repair the candidate using only the public task and evidence. "
            "Return the corrected Action Plan first; the host will execute it."
        )
    user_prompt = json.dumps(user_payload, ensure_ascii=False, sort_keys=True)
    action_text = json.dumps(action_plan, ensure_ascii=False, sort_keys=True)
    host_text = json.dumps(host_execution, ensure_ascii=False, sort_keys=True)
    answer_text = json.dumps(answer_decision, ensure_ascii=False, sort_keys=True)
    assistant_target = json.dumps(
        {
            "schema_version": "host_instrumented_student_target.v1",
            "action_plan": action_plan,
            "answer_decision": answer_decision,
        },
        ensure_ascii=False,
        sort_keys=True,
    )
    messages = (
        SFTMessage(role="system", content=system_prompt, phase="context"),
        SFTMessage(role="user", content=user_prompt, phase="context"),
        SFTMessage(
            role="assistant",
            content=action_text,
            supervise=True,
            phase="action_plan",
        ),
        SFTMessage(
            role="tool",
            content=host_text,
            phase="host_execution",
        ),
        SFTMessage(
            role="assistant",
            content=answer_text,
            supervise=True,
            phase="answer_decision",
        ),
    )
    identity = {
        "cohort": cohort.value if isinstance(cohort, UtilityCohort) else cohort,
        "task_id": task["task_id"],
        "source_kind": source_kind,
        "user_prompt": user_prompt,
        "assistant_target": assistant_target,
        "system_prompt": system_prompt,
        "prompt_version": prompt_version,
        "training_format": "host_instrumented_joint",
        "sampling_weight": sampling_weight,
    }
    return SFTRecord(
        record_id=canonical_hash(identity, prefix="training_utility_record:"),
        cohort=cohort,
        task_id=str(task["task_id"]),
        domain=str(task["domain"]),
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        assistant_target=assistant_target,
        training_format="host_instrumented_joint",
        messages=messages,
        source_kind=source_kind,
        contract_label=contract_label,
        counterfactual_repair=candidate_attempt is not None,
        metadata={
            **dict(metadata or {}),
            "prompt_version": prompt_version,
            "prompt_manifest_hash": canonical_hash(
                system_prompt, prefix="training_utility_agent_prompt:"
            ),
        },
        prompt_version=prompt_version,
        sampling_weight=sampling_weight,
    )


def _student_contracts_from_response(
    target: dict[str, Any],
    *,
    task: dict[str, Any],
    evidence: list[dict[str, Any]],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    action_plan, answer_decision = _student_model_contracts_from_response(target)
    public_task = TaskPublicSpec.model_validate(task)
    evidence_items = tuple(EvidenceItem.model_validate(item) for item in evidence)
    trace = execute_action_plan(
        public_task,
        evidence_items,
        AgentActionPlanContract.model_validate(action_plan),
        _student_operation_registry(public_task.domain),
    )
    host_execution = make_host_execution_feedback(trace).model_dump(mode="json")
    HostExecutionFeedbackContract.model_validate(host_execution)
    return action_plan, host_execution, answer_decision


def _student_model_contracts_from_response(
    target: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    response = AgentResponseContract.model_validate(target)
    execution_positions = {
        item.execution_id: index
        for index, item in enumerate(response.execution_trace.steps, start=1)
    }
    action_plan = {
        "schema_version": "agent_action_plan.v1",
        "plan_summary": response.plan_summary,
        "selected_evidence_ids": list(response.selected_evidence_ids),
        "executions": [
            {
                "operator_id": item.operator_id,
                "inputs": [
                    _student_action_input(ref, execution_positions) for ref in item.input_refs
                ],
                "parameters": item.parameters,
                "rationale_summary": item.rationale_summary,
            }
            for item in response.execution_trace.steps
        ],
        "output_step_index": execution_positions[response.execution_trace.output_execution_id],
    }
    final_answer = response.final_answer
    answer_decision = {
        "schema_version": "agent_answer_decision.v1",
        "result": final_answer.result,
        "cited_evidence_ids": [item.evidence_id for item in final_answer.citations],
        **({"status": final_answer.status} if final_answer.status is not None else {}),
        **({"claims": final_answer.claims} if final_answer.claims is not None else {}),
    }
    AgentActionPlanContract.model_validate(action_plan)
    AgentAnswerDecisionContract.model_validate(answer_decision)
    return action_plan, answer_decision


def _student_operation_registry(domain: str) -> OperationRegistry:
    if domain == "legal":
        return legal_operation_registry()
    if domain == "science":
        return science_operation_registry()
    return default_registry()


def _student_action_input(
    ref: str,
    execution_positions: dict[str, int],
) -> dict[str, Any]:
    base, separator, selector = ref.partition("#")
    suffix = selector if separator else None
    if base.startswith("evidence:"):
        return {
            "source": "evidence",
            "evidence_id": base.removeprefix("evidence:"),
            "selector": suffix,
        }
    if not base.startswith("execution:"):
        raise ValueError(f"unsupported execution input ref: {ref}")
    execution_id = base.removeprefix("execution:")
    try:
        step_index = execution_positions[execution_id]
    except KeyError as exc:
        raise ValueError(f"unresolved execution input ref: {ref}") from exc
    return {
        "source": "step",
        "step_index": step_index,
        "selector": suffix,
    }


def _student_operation_catalog(target: dict[str, Any]) -> list[dict[str, Any]]:
    response = AgentResponseContract.model_validate(target)
    catalog: dict[str, dict[str, Any]] = {}
    for item in response.execution_trace.steps:
        catalog[item.operator_id] = {
            "operator_id": item.operator_id,
            "tool_capability": item.tool_name,
        }
    return [catalog[key] for key in sorted(catalog)]


def _model_owned_candidate_attempt(candidate: dict[str, Any]) -> dict[str, Any]:
    try:
        action, answer = _student_model_contracts_from_response(candidate)
    except (ValueError, KeyError, TypeError):
        return {
            "unrepresentable_candidate": True,
            "instruction": "Construct a fresh action plan from the public task and evidence.",
        }
    return {"action_plan": action, "answer_decision": answer}


def _d1_random_records(
    config: TrainingUtilityMVPConfig,
    examples: tuple[QualityCriticExample, ...],
) -> tuple[SFTRecord, ...]:
    real_records = _representable_example_records(
        tuple(item for item in examples if item.candidate_source == "real_agent"),
        UtilityCohort.RANDOM_SYNTHETIC,
        prompt_version=config.prompt_version,
    )
    if config.d1_construction_mode == "unfiltered_real_agent":
        return _balanced_take(real_records, config.cohort_size, config.seed + 101)

    negative = _representable_example_records(
        tuple(item for item in examples if item.candidate_source == "typed_counterfactual"),
        UtilityCohort.RANDOM_SYNTHETIC,
        prompt_version=config.prompt_version,
    )
    negative_count = round(config.cohort_size * config.d1_counterfactual_fraction)
    positive_count = config.cohort_size - negative_count
    return tuple(
        (
            *_balanced_take(real_records, positive_count, config.seed + 101),
            *_balanced_take(negative, negative_count, config.seed + 102),
        )
    )


def _d4_counterfactual_calibrated_records(
    config: TrainingUtilityMVPConfig,
    clean_examples: tuple[QualityCriticExample, ...],
    all_examples: tuple[QualityCriticExample, ...],
) -> tuple[SFTRecord, ...]:
    if config.d4_training_format == "legacy_mixed_repair":
        return _d4_legacy_mixed_repair_records(config, clean_examples, all_examples)

    counterfactuals_by_task: dict[str, list[QualityCriticExample]] = defaultdict(list)
    for item in all_examples:
        if item.candidate_source == "typed_counterfactual":
            counterfactuals_by_task[item.task_id].append(item)
    ranked_clean = []
    for clean in clean_examples:
        counterfactuals = counterfactuals_by_task.get(clean.task_id, [])
        if not counterfactuals:
            continue
        failure_families = tuple(
            sorted(
                {
                    family
                    for item in counterfactuals
                    for family in item.contract_annotation.failure_families
                }
            )
        )
        record = record_from_quality_example(
            clean,
            UtilityCohort.CONTRACT_COUNTERFACTUAL,
            prompt_version=config.prompt_version,
            metadata={
                "feedback_policy": "typed_counterfactual_to_clean_solve_allocation",
                "feedback_failure_families": failure_families,
                "feedback_counterfactual_example_ids": tuple(
                    sorted(item.example_id for item in counterfactuals)
                ),
                "feedback_failure_family_count": len(failure_families),
                "training_mode": "solve",
            },
        )
        ranked_clean.append((len(failure_families), record))
    ranked_clean.sort(
        key=lambda item: (
            -item[0],
            canonical_hash(
                {"seed": config.seed + 401, "record_id": item[1].record_id},
                prefix="counterfactual_guided_clean_order:",
            ),
        )
    )
    return _balanced_ranked_take(
        tuple(item[1] for item in ranked_clean),
        config.cohort_size,
    )


def _d4_legacy_mixed_repair_records(
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
            record_from_quality_example(
                item,
                UtilityCohort.CONTRACT_COUNTERFACTUAL,
                prompt_version=config.prompt_version,
            )
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
                record_from_quality_example(
                    clean,
                    UtilityCohort.CONTRACT_COUNTERFACTUAL,
                    prompt_version=config.prompt_version,
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


def _select_d5_examples(
    config: TrainingUtilityMVPConfig,
    reviewed_clean: tuple[QualityCriticExample, ...],
    prediction_by_task: dict[str, Any],
) -> tuple[tuple[QualityCriticExample, ...], dict[str, str]]:
    selected: list[QualityCriticExample] = []
    domain_results = []
    per_domain = config.cohort_size // len(("finance", "legal", "science"))
    selector = QualityAwareSelector()
    for domain in ("finance", "legal", "science"):
        domain_examples = tuple(item for item in reviewed_clean if item.domain == domain)
        predictions = tuple(prediction_by_task[item.task_id] for item in domain_examples)
        for example, prediction in zip(domain_examples, predictions, strict=True):
            if prediction.example_id != example.example_id:
                raise ValueError(f"D5 Critic prediction identity mismatch for {example.task_id}")
        policy = QualitySelectionPolicy(
            policy_id=f"training_utility.d5.{domain}.v2",
            target_size=per_domain,
            minimum_overall_score=config.d5_minimum_overall_score,
            minimum_dimension_score=config.d5_minimum_dimension_score,
            minimum_critic_accept_probability=(config.d5_minimum_critic_accept_probability),
            stratum_fields=("candidate_source",),
        )
        result = selector.select(domain_examples, policy, predictions)
        if result.shortfall:
            raise ValueError(f"D5 QualityAwareSelector shortfall for {domain}: {result.shortfall}")
        example_by_id = {item.example_id: item for item in domain_examples}
        selected.extend(example_by_id[item] for item in result.selected_example_ids)
        domain_results.append(result)
    policy_hash = canonical_hash(
        tuple(item.policy_hash for item in domain_results),
        prefix="training_utility_d5_policy_bundle:",
    )
    selection_id = canonical_hash(
        {
            "policy_hash": policy_hash,
            "domain_selection_ids": tuple(item.selection_id for item in domain_results),
            "selected_example_ids": tuple(item.example_id for item in selected),
        },
        prefix="training_utility_d5_selection:",
    )
    return tuple(selected), {
        "selection_id": selection_id,
        "policy_hash": policy_hash,
        "status": "complete",
    }


def _reference_and_evaluation_records(
    config: TrainingUtilityMVPConfig,
    *,
    finance_cases: tuple[ContractCase, ...] | None = None,
) -> tuple[tuple[SFTRecord, ...], tuple[SFTRecord, ...]]:
    totals = {
        domain: config.candidate_task_target(domain) + config.evaluation_task_target(domain)
        for domain in ("finance", "legal", "science")
    }
    non_finance = build_pattern_validation_cases(per_domain=max(totals["legal"], totals["science"]))
    resolved_finance_cases = (
        build_finance_counterfactual_cases(count=totals["finance"])
        if finance_cases is None
        else finance_cases
    )
    if len(resolved_finance_cases) != totals["finance"]:
        raise ValueError(
            "Finance reference/evaluation source count mismatch: "
            f"expected={totals['finance']}, observed={len(resolved_finance_cases)}"
        )
    if any(item.domain != "finance" for item in resolved_finance_cases):
        raise ValueError("Finance reference/evaluation source contains another domain")
    if len({item.task.task_id for item in resolved_finance_cases}) != len(resolved_finance_cases):
        raise ValueError("Finance reference/evaluation tasks must be unique")
    cases = (
        *resolved_finance_cases,
        *tuple(item for item in non_finance if item.domain == "legal")[: totals["legal"]],
        *tuple(item for item in non_finance if item.domain == "science")[: totals["science"]],
    )
    domain_seen: Counter[str] = Counter()
    train: list[SFTRecord] = []
    evaluation: list[SFTRecord] = []
    for case in cases:
        ordinal = domain_seen[case.domain]
        domain_seen[case.domain] += 1
        candidate_target = config.candidate_task_target(case.domain)
        task = materialize_track_variant(
            case.task,
            case.corpus,
            retrieval_track=RetrievalTrack.RESOLVED,
            planning_track=PlanningTrack.PLAN_GIVEN,
        )
        record = make_sft_record(
            cohort=(
                UtilityCohort.REFERENCE_WORKFLOW if ordinal < candidate_target else "evaluation"
            ),
            task=task.public.model_dump(mode="json", exclude_none=True),
            evidence=[
                item.model_dump(mode="json", exclude_none=True) for item in case.corpus.evidence
            ],
            target=_reference_response(task, case.bundle, case.registry),
            source_kind="deterministic_reference_workflow",
            contract_label="accept",
            prompt_version=config.prompt_version,
            metadata={
                "source_ordinal": ordinal + 1,
                "source_adapter_ids": sorted(
                    {item.provenance.adapter_id for item in case.corpus.evidence}
                ),
                **_task_structure_metadata(task.public),
            },
        )
        (train if ordinal < candidate_target else evaluation).append(record)
    return tuple(train), tuple(evaluation)


def _task_structure_metadata(task) -> dict[str, Any]:
    pattern = task.metadata.get("task_pattern") or {}
    nodes = tuple(task.program_skeleton.nodes) if task.program_skeleton is not None else ()
    program_contract = tuple(
        (
            node.operator_id,
            tuple(node.dependencies),
            tuple(sorted(node.parameters.items())),
        )
        for node in nodes
    )
    answer_type = str(task.answer_schema.get("type") or "unknown")
    pattern_id = str(pattern.get("pattern_id") or task.task_type)
    return {
        "pattern_id": pattern_id,
        "task_type": task.task_type,
        "operation_sequence": [node.operator_id for node in nodes],
        "program_signature": canonical_hash(
            program_contract,
            prefix="training_utility_program_signature:",
        ),
        "answer_type": answer_type,
        "structural_group_id": canonical_hash(
            {
                "domain": task.domain,
                "pattern_id": pattern_id,
                "program_contract": program_contract,
                "answer_type": answer_type,
            },
            prefix="training_utility_structural_group:",
        ),
    }


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
        "schema_version": "agent_response.v3",
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
                node_outputs=execution.node_outputs,
            ),
            "citations": citations,
        },
    }
    AgentResponseContract.model_validate(response)
    return response


def _representable_example_records(
    examples: tuple[QualityCriticExample, ...],
    cohort: UtilityCohort,
    *,
    prompt_version: str = TRAINING_UTILITY_AGENT_PROMPT_VERSION,
) -> tuple[SFTRecord, ...]:
    records_by_id: dict[str, SFTRecord] = {}
    for example in examples:
        try:
            record = record_from_quality_example(
                example,
                cohort,
                prompt_version=prompt_version,
            )
        except ValueError:
            continue
        # Distinct annotations can collapse to the same public prompt and target.
        records_by_id.setdefault(record.record_id, record)
    return tuple(records_by_id.values())


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
        output.extend(_structural_take(domain_records, per_domain, rng=rng))
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
        output.extend(_structural_take(domain_records, per_domain))
    return tuple(output)


def _structural_take(
    records: list[SFTRecord],
    count: int,
    *,
    rng: random.Random | None = None,
) -> tuple[SFTRecord, ...]:
    if len(records) < count:
        domain = records[0].domain if records else "unknown"
        raise ValueError(f"insufficient {domain} records: {len(records)} < {count}")
    pattern_groups: dict[str, dict[str, list[SFTRecord]]] = defaultdict(lambda: defaultdict(list))
    for item in records:
        pattern_id = str(item.metadata.get("pattern_id") or item.task_id)
        structural_id = str(
            item.metadata.get("structural_group_id")
            or item.metadata.get("program_signature")
            or item.task_id
        )
        pattern_groups[pattern_id][structural_id].append(item)
    if rng is not None:
        for structural_groups in pattern_groups.values():
            for group in structural_groups.values():
                rng.shuffle(group)
    pattern_sequences = {
        pattern_id: _round_robin_groups(structural_groups)
        for pattern_id, structural_groups in pattern_groups.items()
    }
    selected = _round_robin_groups(pattern_sequences)[:count]
    if len(selected) < count:
        raise ValueError("structural round-robin could not satisfy the requested count")
    return tuple(selected)


def _round_robin_groups(groups: dict[str, list[SFTRecord]]) -> list[SFTRecord]:
    output: list[SFTRecord] = []
    index = 0
    while True:
        emitted = False
        for group_id in sorted(groups):
            group = groups[group_id]
            if index < len(group):
                output.append(group[index])
                emitted = True
        if not emitted:
            return output
        index += 1


def _cohort_manifest(
    cohort: UtilityCohort | str,
    records: tuple[SFTRecord, ...],
) -> CohortDatasetManifest:
    cohort_name = cohort.value if isinstance(cohort, UtilityCohort) else cohort
    record_ids = tuple(item.record_id for item in records)
    duplicate_ids = sorted(item for item, count in Counter(record_ids).items() if count > 1)
    if duplicate_ids:
        raise ValueError(f"cohort {cohort_name} contains duplicate record IDs: {duplicate_ids}")
    return CohortDatasetManifest(
        cohort=cohort,
        record_count=len(records),
        domain_counts=dict(sorted(Counter(item.domain for item in records).items())),
        source_kind_counts=dict(sorted(Counter(item.source_kind for item in records).items())),
        pattern_counts=_metadata_counts(records, "pattern_id"),
        program_signature_counts=_metadata_counts(records, "program_signature"),
        structural_group_count=len(
            {str(item.metadata.get("structural_group_id") or "unknown") for item in records}
        ),
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
