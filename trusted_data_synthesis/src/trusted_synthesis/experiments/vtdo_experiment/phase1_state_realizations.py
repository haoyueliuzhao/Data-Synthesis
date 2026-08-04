from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.core.operations.registry import default_registry
from trusted_synthesis.core.vtdo import (
    TRAJECTORY_STATE_MATERIALIZATION_REPORT_VERSION,
    ConditionalTrajectoryDistribution,
    StateConditionedTrainingArtifact,
    TrajectoryStateMaterializationReport,
    ValidTrajectoryStateMaterializer,
    VTDORoleContract,
    make_vtdo_role_contract,
)
from trusted_synthesis.experiments.vtdo_experiment.multistate import (
    FinanceTaskStateArtifact,
    load_finance_multi_state_artifacts,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_initial_distribution import (
    FinanceInitialDistributionReport,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_mvp import _make_evaluator
from trusted_synthesis.experiments.vtdo_experiment.phase1_reachability import (
    _load_model_config,
    _telemetry,
)
from trusted_synthesis.experiments.vtdo_experiment.schema import (
    GradientStateRealization,
    gradient_state_realization_id,
)
from trusted_synthesis.experiments.vtdo_experiment.training import _make_record
from trusted_synthesis.hashing import canonical_hash
from trusted_synthesis.runtime.agent import (
    LLMAgentSolver,
    OpenAICompatibleJsonClient,
    StateConditionedLLMTrajectoryProvider,
)
from trusted_synthesis.runtime.agent.llm_agent import LLM_AGENT_SOLVER_VERSION
from trusted_synthesis.runtime.agent.state_conditioned import (
    STATE_CONDITIONED_AGENT_PROVIDER_VERSION,
    StateConditionedGenerationFailureRecord,
    StateConditionedGenerationRecord,
)

FINANCE_STATE_REALIZATION_VERSION: Literal[
    "finance_state_realization_materialization.v7"
] = "finance_state_realization_materialization.v7"
FINANCE_INDEPENDENT_TRAJECTORY_VERIFIER_ID = "finance_trajectory_validity_evaluator.v2"
FINANCE_REALIZATION_UNIQUENESS_POLICY: Literal["independent_trajectory_draws"] = (
    "independent_trajectory_draws"
)

TaskMaterializationResult = tuple[
    tuple[StateConditionedTrainingArtifact, ...],
    TrajectoryStateMaterializationReport,
    tuple[StateConditionedGenerationRecord, ...],
    tuple[StateConditionedGenerationFailureRecord, ...],
]


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class FinanceStateRealizationReport(FrozenModel):
    report_id: str = Field(min_length=1)
    artifact_sha256: str = Field(min_length=64, max_length=64)
    distribution_sha256: str = Field(min_length=64, max_length=64)
    initial_distribution_report_id: str = Field(min_length=1)
    initial_distribution_report_sha256: str = Field(min_length=64, max_length=64)
    model_config_hash: str = Field(min_length=1)
    explorer_provider_id: str = Field(min_length=1)
    materialization_provider_id: str = Field(min_length=1)
    materialization_report_version: Literal[
        "trajectory_state_materialization_report.v3"
    ] = TRAJECTORY_STATE_MATERIALIZATION_REPORT_VERSION
    run_identity: str = Field(min_length=1)
    resumed_task_count: int = Field(ge=0)
    new_task_attempt_count: int = Field(ge=0)
    role_contract_id: str = Field(min_length=1)
    task_count: int = Field(ge=1)
    state_count: int = Field(ge=1)
    requested_realization_count: int = Field(ge=1)
    released_realization_count: int = Field(ge=0)
    realization_uniqueness_policy: Literal["independent_trajectory_draws"] = (
        FINANCE_REALIZATION_UNIQUENESS_POLICY
    )
    unique_trajectory_hash_count: int = Field(ge=0)
    unique_decision_trace_count: int = Field(ge=0)
    decision_trace_diversity_rate: float = Field(ge=0, le=1)
    task_report_ids: dict[str, str] = Field(default_factory=dict)
    requested_counts_by_task: dict[str, dict[str, int]] = Field(default_factory=dict)
    released_counts_by_task: dict[str, dict[str, int]] = Field(default_factory=dict)
    failure_counts: dict[str, int] = Field(default_factory=dict)
    generation_attempt_count: int = Field(ge=0)
    generation_success_record_count: int = Field(ge=0)
    generation_failure_record_count: int = Field(ge=0)
    generation_failure_counts: dict[str, int] = Field(default_factory=dict)
    telemetry: dict[str, Any] = Field(default_factory=dict)
    training_artifacts_sha256: str = Field(min_length=64, max_length=64)
    materialization_reports_sha256: str = Field(min_length=64, max_length=64)
    generation_records_sha256: str = Field(min_length=64, max_length=64)
    generation_failures_sha256: str = Field(min_length=64, max_length=64)
    realizations_sha256: str = Field(min_length=64, max_length=64)
    status: str = Field(pattern="^(passed|partial|blocked)$")
    schema_version: Literal["finance_state_realization_materialization.v7"] = (
        FINANCE_STATE_REALIZATION_VERSION
    )

    @model_validator(mode="after")
    def validate_report(self) -> FinanceStateRealizationReport:
        if self.task_count != len(self.requested_counts_by_task):
            raise ValueError("state realization task accounting is inconsistent")
        if self.state_count != sum(
            len(item) for item in self.requested_counts_by_task.values()
        ):
            raise ValueError("state realization support accounting is inconsistent")
        if self.requested_realization_count != sum(
            sum(item.values()) for item in self.requested_counts_by_task.values()
        ):
            raise ValueError("state realization request accounting is inconsistent")
        if self.released_realization_count != sum(
            sum(item.values()) for item in self.released_counts_by_task.values()
        ):
            raise ValueError("state realization release accounting is inconsistent")
        if self.generation_attempt_count != (
            self.generation_success_record_count + self.generation_failure_record_count
        ):
            raise ValueError("state realization generation accounting is inconsistent")
        if sum(self.generation_failure_counts.values()) != self.generation_failure_record_count:
            raise ValueError("state realization generation failures are inconsistent")
        if self.generation_success_record_count < self.released_realization_count:
            raise ValueError("released realization has no successful generation record")
        if self.unique_trajectory_hash_count != self.released_realization_count:
            raise ValueError("state realizations are not unique independent trajectories")
        expected_trace_rate = (
            self.unique_decision_trace_count / self.released_realization_count
            if self.released_realization_count
            else 0.0
        )
        if abs(self.decision_trace_diversity_rate - expected_trace_rate) > 1e-12:
            raise ValueError("state realization structural diversity is inconsistent")
        if set(self.task_report_ids) != set(self.requested_counts_by_task):
            raise ValueError("state realization task reports do not cover requested tasks")
        if self.explorer_provider_id == self.materialization_provider_id:
            raise ValueError("Explorer and materialization provider identities must differ")
        if (
            self.materialization_report_version
            != TRAJECTORY_STATE_MATERIALIZATION_REPORT_VERSION
        ):
            raise ValueError("state realization references another materializer contract")
        if self.resumed_task_count + self.new_task_attempt_count != self.task_count:
            raise ValueError("state realization resume accounting is inconsistent")
        expected = (
            "passed"
            if self.released_realization_count == self.requested_realization_count
            and len(self.task_report_ids) == self.task_count
            else "partial"
            if self.released_realization_count
            else "blocked"
        )
        if self.status != expected:
            raise ValueError("state realization status is inconsistent")
        if self.report_id != finance_state_realization_report_id(self):
            raise ValueError("state realization report identity is invalid")
        return self


def run_state_realizations(args: argparse.Namespace) -> FinanceStateRealizationReport:
    if args.workers < 1:
        raise ValueError("state realization workers must be positive")
    artifacts_path = Path(args.artifacts_path).resolve()
    distributions_path = Path(args.distributions_path).resolve()
    initial_report_path = Path(args.initial_distribution_report).resolve()
    model_config_path = Path(args.model_config_path).resolve()
    archive_config_path = Path(args.archive_config_path).resolve()
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    artifacts = load_finance_multi_state_artifacts(artifacts_path)
    artifact_by_task = {item.omega.task.task_id: item for item in artifacts}
    distributions = _load_distributions(distributions_path)
    initial_report = FinanceInitialDistributionReport.model_validate_json(
        initial_report_path.read_text(encoding="utf-8")
    )
    validate_initial_distribution_lineage(
        initial_report,
        artifacts_path=artifacts_path,
        distributions_path=distributions_path,
        distributions=distributions,
    )
    if set(distributions) - set(artifact_by_task):
        raise ValueError("state realization distribution references an unknown task")
    selected = tuple(artifact_by_task[task_id] for task_id in sorted(distributions))
    for artifact in selected:
        distribution = distributions[artifact.omega.task.task_id]
        if set(distribution.probabilities) != set(artifact.state_catalog.states):
            raise ValueError("state realization distribution support differs from catalog")

    model_config = _load_model_config(
        model_config_path,
        temperature=args.temperature,
    )
    materialization_provider_id = finance_state_materialization_provider_id(
        model_config.public_manifest_hash
    )
    role_contract = make_vtdo_role_contract(
        explorer_provider_id=initial_report.explorer_provider_id,
        materialization_provider_id=materialization_provider_id,
        beneficiary_model_state_id=args.beneficiary_model_state_id,
        final_student_model_id=args.final_student_model_id,
    )
    requested_by_task = {
        artifact.omega.task.task_id: {
            state_id: args.minimum_realizations_per_state
            for state_id in sorted(
                distributions[artifact.omega.task.task_id].probabilities
            )
        }
        for artifact in selected
    }
    run_identity = canonical_hash(
        {
            "artifact_sha256": _sha256(artifacts_path),
            "distribution_sha256": _sha256(distributions_path),
            "initial_distribution_report_id": initial_report.report_id,
            "model_config_hash": model_config.public_manifest_hash,
            "role_contract_id": role_contract.contract_id,
            "materialization_report_version": (
                TRAJECTORY_STATE_MATERIALIZATION_REPORT_VERSION
            ),
            "realization_uniqueness_policy": FINANCE_REALIZATION_UNIQUENESS_POLICY,
            "minimum_realizations_per_state": args.minimum_realizations_per_state,
            "maximum_realizations_per_state": args.maximum_realizations_per_state,
            "maximum_attempt_multiplier": args.maximum_attempt_multiplier,
            "seed": args.seed,
            "contract_version": FINANCE_STATE_REALIZATION_VERSION,
        },
        prefix="finance_state_realization_run:",
    )
    checkpoint_dir = output_dir / "task_checkpoints"
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    result_by_task = _load_task_checkpoints(
        checkpoint_dir,
        run_identity=run_identity,
        artifacts_by_task=artifact_by_task,
        distributions=distributions,
        requested_by_task=requested_by_task,
        role_contract_id=role_contract.contract_id,
        materialization_provider_id=materialization_provider_id,
    )
    resumed_task_ids = set(result_by_task)
    pending = [
        (task_ordinal, artifact)
        for task_ordinal, artifact in enumerate(selected)
        if artifact.omega.task.task_id not in resumed_task_ids
    ]
    discovered_models: tuple[str, ...] = ()
    if pending:
        client = OpenAICompatibleJsonClient(model_config)
        discovered_models = client.discover_models()
        solver = LLMAgentSolver(client, default_registry())
        evaluator = _make_evaluator(archive_config_path)
        with ThreadPoolExecutor(max_workers=args.workers) as executor:
            future_map = {
                executor.submit(
                    _materialize_task,
                    artifact,
                    distributions[artifact.omega.task.task_id],
                    requested_by_task[artifact.omega.task.task_id],
                    role_contract,
                    materialization_provider_id=materialization_provider_id,
                    solver=solver,
                    evaluator=evaluator,
                    total_budget=choose_realization_budget(
                        distributions[artifact.omega.task.task_id],
                        minimum_per_state=args.minimum_realizations_per_state,
                        maximum_per_state=args.maximum_realizations_per_state,
                    ),
                    task_seed=_task_seed(
                        args.seed,
                        artifact.omega.task.task_id,
                        task_ordinal,
                    ),
                    maximum_attempt_multiplier=args.maximum_attempt_multiplier,
                ): artifact
                for task_ordinal, artifact in pending
            }
            for future in as_completed(future_map):
                artifact = future_map[future]
                task_id = artifact.omega.task.task_id
                result = future.result()
                result_by_task[task_id] = result
                _write_task_checkpoint(
                    checkpoint_dir,
                    run_identity=run_identity,
                    task_id=task_id,
                    result=result,
                )

    all_training_artifacts: list[StateConditionedTrainingArtifact] = []
    materialization_reports: list[TrajectoryStateMaterializationReport] = []
    generation_records: list[StateConditionedGenerationRecord] = []
    generation_failures: list[StateConditionedGenerationFailureRecord] = []
    released_by_task: dict[str, dict[str, int]] = {}
    failures: Counter[str] = Counter()
    for artifact in selected:
        task_id = artifact.omega.task.task_id
        (
            training_artifacts,
            report,
            task_generation_records,
            task_generation_failures,
        ) = result_by_task[task_id]
        all_training_artifacts.extend(training_artifacts)
        materialization_reports.append(report)
        generation_records.extend(task_generation_records)
        generation_failures.extend(task_generation_failures)
        released_by_task[task_id] = dict(report.released_state_counts)
        failures.update(report.failure_counts)

    generation_by_trajectory: dict[str, StateConditionedGenerationRecord] = {}
    for item in generation_records:
        generation_by_trajectory.setdefault(item.trajectory_id, item)
    realizations: list[GradientStateRealization] = []
    artifact_by_context = {item.omega.context_id: item for item in selected}
    distribution_by_id = {
        item.distribution_id: item for item in distributions.values()
    }
    for training_artifact in all_training_artifacts:
        artifact = artifact_by_context[training_artifact.context.context_id]
        distribution = distribution_by_id[training_artifact.source_distribution_id]
        generation = generation_by_trajectory.get(
            training_artifact.trajectory.trajectory_id
        )
        if generation is None:
            raise ValueError("released trajectory has no generation audit record")
        realizations.append(
            make_gradient_state_realization(
                artifact=artifact,
                training_artifact=training_artifact,
                distribution=distribution,
                generation_record=generation,
                independent_verifier_id=FINANCE_INDEPENDENT_TRAJECTORY_VERIFIER_ID,
            )
        )
    all_training_artifacts.sort(key=lambda item: item.artifact_id)
    materialization_reports.sort(key=lambda item: item.context_id)
    generation_records.sort(key=lambda item: (item.trajectory_id, item.candidate_index))
    generation_failures.sort(key=lambda item: (item.request_id, item.candidate_index))
    realizations.sort(key=lambda item: item.realization_id)
    training_artifacts_path = output_dir / "state_conditioned_training_artifacts.jsonl"
    materialization_reports_path = output_dir / "state_materialization_reports.jsonl"
    generation_records_path = output_dir / "state_conditioned_generation_records.jsonl"
    generation_failures_path = output_dir / "state_conditioned_generation_failures.jsonl"
    realizations_path = output_dir / "gradient_state_realizations.jsonl"
    _write_jsonl_atomic(
        training_artifacts_path,
        (item.model_dump(mode="json") for item in all_training_artifacts),
    )
    _write_jsonl_atomic(
        materialization_reports_path,
        (item.model_dump(mode="json") for item in materialization_reports),
    )
    _write_jsonl_atomic(
        generation_records_path,
        (item.model_dump(mode="json") for item in generation_records),
    )
    _write_jsonl_atomic(
        generation_failures_path,
        (item.model_dump(mode="json") for item in generation_failures),
    )
    _write_jsonl_atomic(
        realizations_path,
        (item.model_dump(mode="json") for item in realizations),
    )
    telemetry = _telemetry(
        [
            {"generation_audit": item.generation_audit.model_dump(mode="json")}
            for item in generation_records
        ]
        + [
            {"telemetry": [call.model_dump(mode="json") for call in item.telemetry]}
            for item in generation_failures
        ]
    )
    telemetry["discovered_models"] = list(discovered_models)
    requested_total = sum(sum(item.values()) for item in requested_by_task.values())
    released_total = len(realizations)
    generation_failure_counts = Counter(item.error_type for item in generation_failures)
    failures.update(
        {
            f"generation:{error_type}": count
            for error_type, count in generation_failure_counts.items()
        }
    )
    report_values: dict[str, Any] = {
        "artifact_sha256": _sha256(artifacts_path),
        "distribution_sha256": _sha256(distributions_path),
        "initial_distribution_report_id": initial_report.report_id,
        "initial_distribution_report_sha256": _sha256(initial_report_path),
        "model_config_hash": model_config.public_manifest_hash,
        "explorer_provider_id": initial_report.explorer_provider_id,
        "materialization_provider_id": materialization_provider_id,
        "materialization_report_version": (
            TRAJECTORY_STATE_MATERIALIZATION_REPORT_VERSION
        ),
        "run_identity": run_identity,
        "resumed_task_count": len(resumed_task_ids),
        "new_task_attempt_count": len(pending),
        "role_contract_id": role_contract.contract_id,
        "task_count": len(selected),
        "state_count": sum(len(item) for item in requested_by_task.values()),
        "requested_realization_count": requested_total,
        "released_realization_count": released_total,
        "realization_uniqueness_policy": FINANCE_REALIZATION_UNIQUENESS_POLICY,
        "unique_trajectory_hash_count": len(
            {item.trajectory_hash for item in realizations}
        ),
        "unique_decision_trace_count": len(
            {item.decision_trace_hash for item in realizations}
        ),
        "decision_trace_diversity_rate": (
            len({item.decision_trace_hash for item in realizations}) / released_total
            if released_total
            else 0.0
        ),
        "task_report_ids": {
            artifact_by_context[report.context_id].omega.task.task_id: report.report_id
            for report in materialization_reports
        },
        "requested_counts_by_task": requested_by_task,
        "released_counts_by_task": released_by_task,
        "failure_counts": dict(sorted(failures.items())),
        "generation_attempt_count": len(generation_records) + len(generation_failures),
        "generation_success_record_count": len(generation_records),
        "generation_failure_record_count": len(generation_failures),
        "generation_failure_counts": dict(sorted(generation_failure_counts.items())),
        "telemetry": telemetry,
        "training_artifacts_sha256": _sha256(training_artifacts_path),
        "materialization_reports_sha256": _sha256(materialization_reports_path),
        "generation_records_sha256": _sha256(generation_records_path),
        "generation_failures_sha256": _sha256(generation_failures_path),
        "realizations_sha256": _sha256(realizations_path),
        "status": (
            "passed"
            if released_total == requested_total
            and len(materialization_reports) == len(selected)
            else "partial"
            if released_total
            else "blocked"
        ),
        "schema_version": FINANCE_STATE_REALIZATION_VERSION,
    }
    provisional = FinanceStateRealizationReport.model_construct(
        report_id="pending", **report_values
    )
    report = FinanceStateRealizationReport(
        report_id=finance_state_realization_report_id(provisional),
        **report_values,
    )
    _write_json_atomic(
        output_dir / "finance_state_realization_report.json",
        report.model_dump(mode="json"),
    )
    return report


def choose_realization_budget(
    distribution: ConditionalTrajectoryDistribution,
    *,
    minimum_per_state: int,
    maximum_per_state: int,
) -> int:
    if not 1 <= minimum_per_state <= maximum_per_state <= 5:
        raise ValueError("realization count bounds must lie in [1, 5]")
    return minimum_per_state * len(distribution.probabilities)


def _materialize_task(
    artifact: FinanceTaskStateArtifact,
    distribution: ConditionalTrajectoryDistribution,
    requested_counts: dict[str, int],
    role_contract: VTDORoleContract,
    *,
    materialization_provider_id: str,
    solver: LLMAgentSolver,
    evaluator,
    total_budget: int,
    task_seed: int,
    maximum_attempt_multiplier: int,
) -> TaskMaterializationResult:
    provider = StateConditionedLLMTrajectoryProvider(
        provider_id=materialization_provider_id,
        solver=solver,
        public_corpora_by_task_id={
            artifact.omega.task.task_id: artifact.omega.public_corpus
        },
    )
    training_artifacts, report = ValidTrajectoryStateMaterializer(
        provider,
        evaluator,
    ).materialize(
        artifact.omega,
        artifact.state_catalog,
        distribution,
        role_contract,
        total_budget=total_budget,
        seed=task_seed,
        maximum_attempt_multiplier=maximum_attempt_multiplier,
        requested_state_counts=requested_counts,
        realization_uniqueness_policy=FINANCE_REALIZATION_UNIQUENESS_POLICY,
    )
    return training_artifacts, report, provider.records, provider.failure_records


def _write_task_checkpoint(
    checkpoint_dir: Path,
    *,
    run_identity: str,
    task_id: str,
    result: TaskMaterializationResult,
) -> None:
    artifacts, report, generation_records, generation_failures = result
    _write_json_atomic(
        _task_checkpoint_path(checkpoint_dir, task_id),
        {
            "run_identity": run_identity,
            "task_id": task_id,
            "training_artifacts": [item.model_dump(mode="json") for item in artifacts],
            "materialization_report": report.model_dump(mode="json"),
            "generation_records": [
                item.model_dump(mode="json") for item in generation_records
            ],
            "generation_failures": [
                item.model_dump(mode="json") for item in generation_failures
            ],
        },
    )


def _load_task_checkpoints(
    checkpoint_dir: Path,
    *,
    run_identity: str,
    artifacts_by_task: dict[str, FinanceTaskStateArtifact],
    distributions: dict[str, ConditionalTrajectoryDistribution],
    requested_by_task: dict[str, dict[str, int]],
    role_contract_id: str,
    materialization_provider_id: str,
) -> dict[str, TaskMaterializationResult]:
    output: dict[str, TaskMaterializationResult] = {}
    for path in sorted(checkpoint_dir.glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload.get("run_identity") != run_identity:
            raise ValueError("state realization checkpoint belongs to another run")
        task_id = str(payload.get("task_id") or "")
        artifact = artifacts_by_task.get(task_id)
        distribution = distributions.get(task_id)
        if artifact is None or distribution is None or task_id in output:
            raise ValueError("state realization checkpoint contains an unknown task")
        report = TrajectoryStateMaterializationReport.model_validate(
            payload["materialization_report"]
        )
        training_artifacts = tuple(
            StateConditionedTrainingArtifact.model_validate(item)
            for item in payload.get("training_artifacts") or ()
        )
        generation_records = tuple(
            StateConditionedGenerationRecord.model_validate(item)
            for item in payload.get("generation_records") or ()
        )
        generation_failures = tuple(
            StateConditionedGenerationFailureRecord.model_validate(item)
            for item in payload.get("generation_failures") or ()
        )
        if report.status != "passed":
            continue
        if (
            report.context_id != artifact.omega.context_id
            or report.state_catalog_id != artifact.state_catalog.catalog_id
            or report.source_distribution_id != distribution.distribution_id
            or report.role_contract_id != role_contract_id
            or report.materialization_provider_id != materialization_provider_id
            or report.schema_version
            != TRAJECTORY_STATE_MATERIALIZATION_REPORT_VERSION
            or report.realization_uniqueness_policy
            != FINANCE_REALIZATION_UNIQUENESS_POLICY
            or report.requested_state_counts != requested_by_task[task_id]
            or report.released_state_counts != requested_by_task[task_id]
        ):
            raise ValueError("state realization checkpoint does not replay its task contract")
        generation_by_trajectory = {item.trajectory_id for item in generation_records}
        if any(
            item.trajectory.trajectory_id not in generation_by_trajectory
            for item in training_artifacts
        ):
            raise ValueError("state realization checkpoint lost generation lineage")
        output[task_id] = (
            training_artifacts,
            report,
            generation_records,
            generation_failures,
        )
    return output


def _task_checkpoint_path(checkpoint_dir: Path, task_id: str) -> Path:
    digest = canonical_hash(task_id, prefix="finance_state_checkpoint:").rsplit(":", 1)[-1]
    return checkpoint_dir / f"{digest}.json"


def make_gradient_state_realization(
    *,
    artifact: FinanceTaskStateArtifact,
    training_artifact: StateConditionedTrainingArtifact,
    distribution: ConditionalTrajectoryDistribution,
    generation_record: StateConditionedGenerationRecord,
    independent_verifier_id: str,
) -> GradientStateRealization:
    trajectory = training_artifact.trajectory
    state_id = training_artifact.target_state.state_id
    if training_artifact.context.context_id != artifact.omega.context_id:
        raise ValueError("gradient realization crosses task artifacts")
    if distribution.distribution_id != training_artifact.source_distribution_id:
        raise ValueError("gradient realization crosses source distributions")
    if generation_record.trajectory_id != trajectory.trajectory_id:
        raise ValueError("gradient realization has another generation record")
    if generation_record.trajectory_hash != trajectory.trajectory_hash:
        raise ValueError("gradient realization generation payload hash changed")
    metadata = {
        "trajectory_id": trajectory.trajectory_id,
        "trajectory_hash": trajectory.trajectory_hash,
        "decision_trace_hash": training_artifact.decision_trace_hash,
        "independent_verifier_id": independent_verifier_id,
        "validity_report_id": training_artifact.validity_report.report_id,
        "fresh_from_discovery": True,
        "independently_verified": True,
        "on_target": True,
        "materialization_artifact_id": training_artifact.artifact_id,
        "generation_audit_id": generation_record.generation_audit.audit_id,
        "candidate_seed": generation_record.candidate_seed,
    }
    record = _make_record(
        artifact=artifact,
        trajectory=trajectory,
        state_id=state_id,
        arm_id="B5_vtdo",
        accepted_target=True,
        sampling_weight=distribution.probabilities[state_id],
        source_distribution_id=distribution.distribution_id,
        metadata=metadata,
        source_artifact_id=artifact.artifact_id,
    )
    values = {
        "task_condition_id": artifact.omega.task.task_id,
        "state_id": state_id,
        "record": record,
        "source_task_artifact_id": artifact.artifact_id,
        "source_distribution_id": distribution.distribution_id,
        "trajectory_id": trajectory.trajectory_id,
        "trajectory_hash": trajectory.trajectory_hash,
        "decision_trace_hash": training_artifact.decision_trace_hash,
        "independent_verifier_id": independent_verifier_id,
        "validity_report_id": training_artifact.validity_report.report_id,
        "generation_seed": generation_record.candidate_seed,
        "generation_ordinal": generation_record.candidate_index,
        "fresh_from_discovery": True,
        "independently_verified": True,
        "on_target": True,
        "schema_version": "gradient_state_realization.v1",
    }
    provisional = GradientStateRealization.model_construct(
        realization_id="pending", **values
    )
    return GradientStateRealization(
        realization_id=gradient_state_realization_id(provisional),
        **values,
    )


def finance_state_materialization_provider_id(model_config_hash: str) -> str:
    if not model_config_hash.strip():
        raise ValueError("state materializer model config hash cannot be empty")
    return canonical_hash(
        {
            "role": "state_conditioned_materializer",
            "model_config_hash": model_config_hash,
            "solver_version": LLM_AGENT_SOLVER_VERSION,
            "provider_version": STATE_CONDITIONED_AGENT_PROVIDER_VERSION,
            "experiment_contract": FINANCE_STATE_REALIZATION_VERSION,
            "materialization_report_version": (
                TRAJECTORY_STATE_MATERIALIZATION_REPORT_VERSION
            ),
            "realization_uniqueness_policy": FINANCE_REALIZATION_UNIQUENESS_POLICY,
        },
        prefix="agent_provider:",
    )


def validate_initial_distribution_lineage(
    report: FinanceInitialDistributionReport,
    *,
    artifacts_path: Path,
    distributions_path: Path,
    distributions: dict[str, ConditionalTrajectoryDistribution],
) -> None:
    if report.status != "passed":
        raise ValueError("state realization requires a passed initial distribution report")
    if report.artifact_sha256 != _sha256(artifacts_path):
        raise ValueError("initial distribution report references another task population")
    if report.distribution_sha256 != _sha256(distributions_path):
        raise ValueError("initial distribution payload hash does not match its report")
    if set(report.selected_task_ids) != set(distributions):
        raise ValueError("initial distribution task support does not match its report")
    observed_distribution_ids = {
        task_id: distribution.distribution_id
        for task_id, distribution in distributions.items()
    }
    if report.task_distribution_ids != observed_distribution_ids:
        raise ValueError("initial distribution IDs do not replay the frozen report")


def _load_distributions(
    path: Path,
) -> dict[str, ConditionalTrajectoryDistribution]:
    values = tuple(
        ConditionalTrajectoryDistribution.model_validate_json(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    )
    output = {item.task_condition_id: item for item in values}
    if not values or len(output) != len(values):
        raise ValueError("state realization distributions are empty or duplicate a task")
    return output


def _task_seed(seed: int, task_id: str, task_ordinal: int) -> int:
    digest = canonical_hash(
        {"seed": seed, "task_id": task_id, "task_ordinal": task_ordinal},
        prefix="finance_state_realization_task_seed:",
    ).rsplit(":", 1)[-1]
    return int(digest[:16], 16)


def finance_state_realization_report_id(
    value: FinanceStateRealizationReport,
) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"report_id"}),
        prefix="finance_state_realization_report:",
    )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_jsonl_atomic(path: Path, values) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as sink:
        for value in values:
            sink.write(json.dumps(value, ensure_ascii=False, sort_keys=True) + "\n")
    temporary.replace(path)


def _write_json_atomic(path: Path, value: dict[str, Any]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Materialize fresh verified state realizations for Finance GP-C"
    )
    parser.add_argument("--artifacts-path", required=True)
    parser.add_argument("--distributions-path", required=True)
    parser.add_argument("--initial-distribution-report", required=True)
    parser.add_argument("--model-config-path", required=True)
    parser.add_argument("--archive-config-path", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--minimum-realizations-per-state", type=int, default=3)
    parser.add_argument("--maximum-realizations-per-state", type=int, default=5)
    parser.add_argument("--maximum-attempt-multiplier", type=int, default=3)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--temperature", type=float, default=0.6)
    parser.add_argument("--seed", type=int, default=20260803)
    parser.add_argument(
        "--beneficiary-model-state-id",
        default="qwen2_5_7b_finance_beneficiary_adapter.phase1",
    )
    parser.add_argument(
        "--final-student-model-id",
        default="qwen2_5_7b_vtdo_student.fresh_training",
    )
    return parser


def main() -> None:
    report = run_state_realizations(_parser().parse_args())
    print(report.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
