from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.core.operations.registry import default_registry
from trusted_synthesis.core.trajectory import TrajectoryStateAssignment
from trusted_synthesis.core.trajectory.state import map_trajectory_to_state
from trusted_synthesis.core.vtdo import (
    EmpiricalDistributionEstimate,
    estimate_pushforward_distribution,
    make_uniform_coverage_prior,
)
from trusted_synthesis.experiments.vtdo_experiment.multistate import (
    FinanceTaskStateArtifact,
    load_finance_multi_state_artifacts,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_contribution_gradient import (
    select_gradient_tasks,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_mvp import _make_evaluator
from trusted_synthesis.experiments.vtdo_experiment.phase1_reachability import (
    _load_model_config,
    _telemetry,
)
from trusted_synthesis.hashing import canonical_hash
from trusted_synthesis.runtime.agent import (
    LLMAgentSolver,
    LLMClientError,
    OpenAICompatibleJsonClient,
)
from trusted_synthesis.runtime.agent.llm_agent import LLM_AGENT_SOLVER_VERSION
from trusted_synthesis.runtime.tools import InMemoryEvidenceToolRuntime

FINANCE_INITIAL_DISTRIBUTION_VERSION = "finance_initial_distribution.v11"
MINIMUM_INITIAL_REPLICAS_PER_TASK = 4


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class FinanceInitialDistributionReport(FrozenModel):
    report_id: str = Field(min_length=1)
    artifact_sha256: str = Field(min_length=64, max_length=64)
    model_config_hash: str = Field(min_length=1)
    explorer_provider_id: str = Field(min_length=1)
    explorer_provider_version: str = Field(min_length=1)
    trajectory_records_sha256: str = Field(min_length=64, max_length=64)
    estimate_sha256: str = Field(min_length=64, max_length=64)
    distribution_sha256: str = Field(min_length=64, max_length=64)
    sampling_salt: str = Field(min_length=1)
    run_identity: str = Field(min_length=1)
    seed: int
    selected_task_ids: tuple[str, ...] = Field(min_length=1)
    replicas_per_task: int = Field(ge=MINIMUM_INITIAL_REPLICAS_PER_TASK)
    prior_strength: float = Field(gt=0)
    requested_trajectory_count: int = Field(ge=1)
    recorded_attempt_count: int = Field(ge=0)
    resumed_valid_catalog_count: int = Field(ge=0)
    new_generation_attempt_count: int = Field(ge=0)
    completed_trajectory_count: int = Field(ge=0)
    valid_trajectory_count: int = Field(ge=0)
    catalog_hit_count: int = Field(ge=0)
    off_catalog_valid_count: int = Field(ge=0)
    task_estimate_ids: dict[str, str] = Field(default_factory=dict)
    task_distribution_ids: dict[str, str] = Field(default_factory=dict)
    observed_state_counts: dict[str, dict[str, int]] = Field(default_factory=dict)
    valid_catalog_observation_counts: dict[str, int] = Field(default_factory=dict)
    complete_observation_task_count: int = Field(ge=0)
    nonuniform_distribution_count: int = Field(ge=0)
    full_support_distribution_count: int = Field(ge=0)
    failure_counts: dict[str, int] = Field(default_factory=dict)
    telemetry: dict[str, Any] = Field(default_factory=dict)
    status: str = Field(pattern="^(passed|partial|blocked)$")
    schema_version: str = FINANCE_INITIAL_DISTRIBUTION_VERSION

    @model_validator(mode="after")
    def validate_report(self) -> FinanceInitialDistributionReport:
        if self.completed_trajectory_count > self.requested_trajectory_count:
            raise ValueError("initial distribution completion count exceeds requests")
        if (
            self.resumed_valid_catalog_count + self.new_generation_attempt_count
            != self.requested_trajectory_count
            or self.recorded_attempt_count < self.requested_trajectory_count
        ):
            raise ValueError("initial distribution resume accounting is inconsistent")
        if self.valid_trajectory_count > self.completed_trajectory_count:
            raise ValueError("initial distribution validity count exceeds completions")
        if self.catalog_hit_count + self.off_catalog_valid_count != self.valid_trajectory_count:
            raise ValueError("initial distribution state accounting is inconsistent")
        selected = set(self.selected_task_ids)
        if (
            set(self.task_estimate_ids) != set(self.task_distribution_ids)
            or not set(self.task_estimate_ids) <= selected
        ):
            raise ValueError("initial distribution lineage maps are inconsistent")
        if (
            set(self.observed_state_counts) != selected
            or set(self.valid_catalog_observation_counts) != selected
        ):
            raise ValueError("initial distribution observation accounting is incomplete")
        complete_task_count = sum(
            count == self.replicas_per_task
            for count in self.valid_catalog_observation_counts.values()
        )
        if self.complete_observation_task_count != complete_task_count:
            raise ValueError("initial distribution complete-task accounting is inconsistent")
        if any(
            count < 0 or count > self.replicas_per_task
            for count in self.valid_catalog_observation_counts.values()
        ):
            raise ValueError("initial distribution per-task observation count is invalid")
        if (
            self.explorer_provider_version != LLM_AGENT_SOLVER_VERSION
            or self.explorer_provider_id
            != finance_unconditioned_explorer_provider_id(self.model_config_hash)
        ):
            raise ValueError("initial distribution Explorer identity is invalid")
        if self.run_identity != finance_initial_distribution_run_identity(
            artifact_sha256=self.artifact_sha256,
            model_config_hash=self.model_config_hash,
            explorer_provider_id=self.explorer_provider_id,
            explorer_provider_version=self.explorer_provider_version,
            selected_task_ids=self.selected_task_ids,
            replicas_per_task=self.replicas_per_task,
            prior_strength=self.prior_strength,
            sampling_salt=self.sampling_salt,
            seed=self.seed,
        ):
            raise ValueError("initial distribution run identity is invalid")
        expected = (
            "passed"
            if len(self.task_estimate_ids) == len(self.selected_task_ids)
            and self.full_support_distribution_count == len(self.selected_task_ids)
            and self.complete_observation_task_count == len(self.selected_task_ids)
            else "partial"
            if self.task_estimate_ids
            else "blocked"
        )
        if self.status != expected:
            raise ValueError("initial distribution status is inconsistent")
        if self.report_id != finance_initial_distribution_report_id(self):
            raise ValueError("initial distribution report identity is invalid")
        return self


def run_initial_distribution(args: argparse.Namespace) -> FinanceInitialDistributionReport:
    artifacts_path = Path(args.artifacts_path).resolve()
    model_config_path = Path(args.model_config_path).resolve()
    archive_config_path = Path(args.archive_config_path).resolve()
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    artifacts = load_finance_multi_state_artifacts(artifacts_path)
    selected = select_gradient_tasks(
        artifacts,
        count=args.task_count,
        excluded_task_ids=set(),
        sampling_salt=args.sampling_salt,
    )
    if len(selected) != args.task_count:
        raise ValueError("initial distribution could not fill the frozen task quota")
    model_config = _load_model_config(
        model_config_path,
        temperature=args.temperature,
    )
    explorer_provider_id = finance_unconditioned_explorer_provider_id(
        model_config.public_manifest_hash
    )
    evaluator = _make_evaluator(archive_config_path)
    all_jobs = [
        (artifact, replicate)
        for artifact in selected
        for replicate in range(args.replicas_per_task)
    ]
    run_identity = finance_initial_distribution_run_identity(
        artifact_sha256=_sha256(artifacts_path),
        model_config_hash=model_config.public_manifest_hash,
        explorer_provider_id=explorer_provider_id,
        explorer_provider_version=LLM_AGENT_SOLVER_VERSION,
        selected_task_ids=tuple(item.omega.task.task_id for item in selected),
        replicas_per_task=args.replicas_per_task,
        prior_strength=args.prior_strength,
        sampling_salt=args.sampling_salt,
        seed=args.seed,
    )
    checkpoint = output_dir / "initial_trajectory_records.checkpoint.jsonl"
    historical_records = _load_checkpoint_records(
        checkpoint,
        run_identity=run_identity,
        selected_task_ids={item.omega.task.task_id for item in selected},
        replicas_per_task=args.replicas_per_task,
    )
    latest_by_key = {_record_key(record): record for record in historical_records}
    resumed_keys = {key for key, record in latest_by_key.items() if _record_is_reusable(record)}
    jobs = [
        (artifact, replicate)
        for artifact, replicate in all_jobs
        if (artifact.omega.task.task_id, replicate) not in resumed_keys
    ]
    new_records: list[dict[str, Any]] = []
    discovered_models: tuple[str, ...] = ()
    if jobs:
        client = OpenAICompatibleJsonClient(model_config)
        discovered_models = client.discover_models()
        solver = LLMAgentSolver(client, default_registry())
        with ThreadPoolExecutor(max_workers=args.workers) as executor:
            future_map = {
                executor.submit(
                    _solve_one,
                    solver,
                    artifact,
                    replicate,
                    args.seed,
                ): (artifact, replicate)
                for artifact, replicate in jobs
            }
            for future in as_completed(future_map):
                artifact, replicate = future_map[future]
                try:
                    result = future.result()
                    record = _evaluate_one(
                        evaluator,
                        artifact,
                        result,
                        replicate=replicate,
                        seed=args.seed,
                        run_identity=run_identity,
                    )
                except Exception as exc:
                    record = _failure_record(
                        artifact,
                        replicate,
                        exc,
                        run_identity=run_identity,
                    )
                new_records.append(record)
                latest_by_key[_record_key(record)] = record
                _append_jsonl(checkpoint, record)
    records = [
        latest_by_key[(artifact.omega.task.task_id, replicate)] for artifact, replicate in all_jobs
    ]
    records.sort(key=lambda item: (item["task_id"], item["replicate"]))
    trajectory_records_path = output_dir / "initial_trajectory_records.jsonl"
    _write_jsonl_atomic(trajectory_records_path, records)

    by_task: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        if record.get("status") == "completed" and record["validity_report"]["valid"]:
            by_task[record["task_id"]].append(record)
    estimates: list[EmpiricalDistributionEstimate] = []
    observed_state_counts: dict[str, dict[str, int]] = {}
    valid_catalog_observation_counts: dict[str, int] = {}
    failures: Counter[str] = Counter(
        str(record.get("error_type") or "unknown_failure")
        for record in records
        if record.get("status") != "completed"
    )
    catalog_hit_count = 0
    off_catalog_count = 0
    for artifact in selected:
        task_id = artifact.omega.task.task_id
        catalog_support = set(artifact.state_catalog.states)
        task_records = by_task[task_id]
        accepted_records = [
            record
            for record in task_records
            if record["state_assignment"]["state"]["state_id"] in catalog_support
        ]
        valid_catalog_observation_counts[task_id] = len(accepted_records)
        observed_state_counts[task_id] = dict(
            sorted(
                Counter(
                    record["state_assignment"]["state"]["state_id"] for record in accepted_records
                ).items()
            )
        )
        catalog_hit_count += len(accepted_records)
        off_catalog_count += len(task_records) - len(accepted_records)
        if not accepted_records:
            failures["task_without_catalog_observation"] += 1
            continue
        assignments = tuple(
            TrajectoryStateAssignment.model_validate(record["state_assignment"])
            for record in accepted_records
        )
        observation_ids = tuple(str(record["observation_id"]) for record in accepted_records)
        prior = make_uniform_coverage_prior(task_id, catalog_support)
        estimate = estimate_pushforward_distribution(
            assignments,
            prior,
            round_index=0,
            prior_strength=args.prior_strength,
            observation_ids=observation_ids,
        )
        estimates.append(estimate)
    estimate_path = output_dir / "initial_distribution_estimates.jsonl"
    distribution_path = output_dir / "initial_distributions.jsonl"
    _write_jsonl_atomic(
        estimate_path,
        (item.model_dump(mode="json") for item in estimates),
    )
    _write_jsonl_atomic(
        distribution_path,
        (item.distribution.model_dump(mode="json") for item in estimates),
    )
    nonuniform_count = sum(
        len({round(value, 15) for value in item.distribution.probabilities.values()}) > 1
        for item in estimates
    )
    full_support_count = sum(
        all(value > 0 for value in item.distribution.probabilities.values()) for item in estimates
    )
    telemetry = _telemetry([*historical_records, *new_records])
    telemetry["discovered_models"] = list(discovered_models)
    report_values: dict[str, Any] = {
        "artifact_sha256": _sha256(artifacts_path),
        "model_config_hash": model_config.public_manifest_hash,
        "explorer_provider_id": explorer_provider_id,
        "explorer_provider_version": LLM_AGENT_SOLVER_VERSION,
        "trajectory_records_sha256": _sha256(trajectory_records_path),
        "estimate_sha256": _sha256(estimate_path),
        "distribution_sha256": _sha256(distribution_path),
        "sampling_salt": args.sampling_salt,
        "run_identity": run_identity,
        "seed": args.seed,
        "selected_task_ids": tuple(item.omega.task.task_id for item in selected),
        "replicas_per_task": args.replicas_per_task,
        "prior_strength": args.prior_strength,
        "requested_trajectory_count": len(all_jobs),
        "recorded_attempt_count": len(historical_records) + len(new_records),
        "resumed_valid_catalog_count": len(resumed_keys),
        "new_generation_attempt_count": len(jobs),
        "completed_trajectory_count": sum(
            record.get("status") == "completed" for record in records
        ),
        "valid_trajectory_count": sum(
            record.get("status") == "completed" and record["validity_report"]["valid"]
            for record in records
        ),
        "catalog_hit_count": catalog_hit_count,
        "off_catalog_valid_count": off_catalog_count,
        "task_estimate_ids": {item.task_condition_id: item.estimate_id for item in estimates},
        "task_distribution_ids": {
            item.task_condition_id: item.distribution.distribution_id for item in estimates
        },
        "observed_state_counts": observed_state_counts,
        "valid_catalog_observation_counts": valid_catalog_observation_counts,
        "complete_observation_task_count": sum(
            count == args.replicas_per_task for count in valid_catalog_observation_counts.values()
        ),
        "nonuniform_distribution_count": nonuniform_count,
        "full_support_distribution_count": full_support_count,
        "failure_counts": dict(sorted(failures.items())),
        "telemetry": telemetry,
        "status": (
            "passed"
            if len(estimates) == len(selected)
            and full_support_count == len(selected)
            and all(
                count == args.replicas_per_task
                for count in valid_catalog_observation_counts.values()
            )
            else "partial"
            if estimates
            else "blocked"
        ),
        "schema_version": FINANCE_INITIAL_DISTRIBUTION_VERSION,
    }
    provisional = FinanceInitialDistributionReport.model_construct(
        report_id="pending", **report_values
    )
    report = FinanceInitialDistributionReport(
        report_id=finance_initial_distribution_report_id(provisional),
        **report_values,
    )
    _write_json_atomic(
        output_dir / "finance_initial_distribution_report.json",
        report.model_dump(mode="json"),
    )
    return report


def _solve_one(
    solver: LLMAgentSolver,
    artifact: FinanceTaskStateArtifact,
    replicate: int,
    seed: int,
):
    generation_seed = _generation_seed(seed, artifact.omega.task.task_id, replicate)
    return solver.solve_with_audit(
        artifact.omega.task.public,
        InMemoryEvidenceToolRuntime(artifact.omega.public_corpus),
        generation_constraints={
            "contract_version": FINANCE_INITIAL_DISTRIBUTION_VERSION,
            "sampling_context": {
                "experiment_seed": seed,
                "replicate": replicate,
                "generation_seed": generation_seed,
            },
            "state_target": None,
            "binding_rule": (
                "Solve the public task naturally. No quotient state is requested or disclosed."
            ),
        },
    )


def _evaluate_one(
    evaluator,
    artifact,
    result,
    *,
    replicate: int,
    seed: int,
    run_identity: str,
) -> dict[str, Any]:
    context = artifact.omega
    validity = evaluator.evaluate(context, result.trajectory)
    assignment = map_trajectory_to_state(
        context,
        result.trajectory,
        program_node_aliases=validity.program_node_mapping,
    )
    observation_id = canonical_hash(
        {
            "task_id": context.task.task_id,
            "replicate": replicate,
            "generation_seed": _generation_seed(seed, context.task.task_id, replicate),
            "generation_audit_id": result.audit.audit_id,
        },
        prefix="finance_initial_trajectory_observation:",
    )
    return {
        "run_identity": run_identity,
        "observation_id": observation_id,
        "task_id": context.task.task_id,
        "task_type": context.task.public.task_type,
        "replicate": replicate,
        "status": "completed",
        "trajectory": result.trajectory.model_dump(mode="json"),
        "generation_audit": result.audit.model_dump(mode="json"),
        "validity_report": validity.model_dump(mode="json"),
        "state_assignment": assignment.model_dump(mode="json"),
        "catalog_hit": assignment.state.state_id in artifact.state_catalog.states,
    }


def _failure_record(
    artifact: FinanceTaskStateArtifact,
    replicate: int,
    exc: Exception,
    *,
    run_identity: str,
) -> dict[str, Any]:
    telemetry = (
        [item.model_dump(mode="json") for item in exc.telemetry]
        if isinstance(exc, LLMClientError)
        else []
    )
    failure_artifact = None
    interaction_progress = None
    if isinstance(exc, LLMClientError):
        if exc.failure_artifact is not None:
            failure_artifact = exc.failure_artifact.model_dump(mode="json")
        if exc.interaction_progress is not None:
            interaction_progress = exc.interaction_progress.model_dump(mode="json")

    return {
        "run_identity": run_identity,
        "task_id": artifact.omega.task.task_id,
        "task_type": artifact.omega.task.public.task_type,
        "replicate": replicate,
        "status": "failed",
        "error_type": type(exc).__name__,
        "error_message": " ".join(str(exc).split())[:500],
        "telemetry": telemetry,
        "failure_artifact": failure_artifact,
        "interaction_progress": interaction_progress,
    }


def _record_key(record: dict[str, Any]) -> tuple[str, int]:
    return str(record["task_id"]), int(record["replicate"])


def _record_is_reusable(record: dict[str, Any]) -> bool:
    return bool(
        record.get("status") == "completed"
        and record.get("catalog_hit") is True
        and isinstance(record.get("validity_report"), dict)
        and record["validity_report"].get("valid") is True
    )


def _load_checkpoint_records(
    path: Path,
    *,
    run_identity: str,
    selected_task_ids: set[str],
    replicas_per_task: int,
) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    records = [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]
    for record in records:
        if record.get("run_identity") != run_identity:
            raise ValueError("initial distribution checkpoint belongs to another run")
        task_id, replicate = _record_key(record)
        if task_id not in selected_task_ids or not 0 <= replicate < replicas_per_task:
            raise ValueError("initial distribution checkpoint contains an unknown job")
    return records


def _generation_seed(seed: int, task_id: str, replicate: int) -> int:
    digest = canonical_hash(
        {"seed": seed, "task_id": task_id, "replicate": replicate},
        prefix="finance_initial_distribution_seed:",
    ).rsplit(":", 1)[-1]
    return int(digest[:16], 16)


def finance_initial_distribution_report_id(
    value: FinanceInitialDistributionReport,
) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"report_id"}),
        prefix="finance_initial_distribution_report:",
    )


def finance_initial_distribution_run_identity(
    *,
    artifact_sha256: str,
    model_config_hash: str,
    explorer_provider_id: str,
    explorer_provider_version: str,
    selected_task_ids: tuple[str, ...],
    replicas_per_task: int,
    prior_strength: float,
    sampling_salt: str,
    seed: int,
) -> str:
    return canonical_hash(
        {
            "artifact_sha256": artifact_sha256,
            "model_config_hash": model_config_hash,
            "explorer_provider_id": explorer_provider_id,
            "explorer_provider_version": explorer_provider_version,
            "selected_task_ids": selected_task_ids,
            "replicas_per_task": replicas_per_task,
            "prior_strength": prior_strength,
            "sampling_salt": sampling_salt,
            "seed": seed,
            "contract_version": FINANCE_INITIAL_DISTRIBUTION_VERSION,
        },
        prefix="finance_initial_distribution_run:",
    )


def finance_unconditioned_explorer_provider_id(model_config_hash: str) -> str:
    if not model_config_hash.strip():
        raise ValueError("unconditioned Explorer model config hash cannot be empty")
    return canonical_hash(
        {
            "role": "unconditioned_explorer",
            "model_config_hash": model_config_hash,
            "solver_version": LLM_AGENT_SOLVER_VERSION,
            "experiment_contract": FINANCE_INITIAL_DISTRIBUTION_VERSION,
        },
        prefix="agent_provider:",
    )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _append_jsonl(path: Path, value: dict[str, Any]) -> None:
    with path.open("a", encoding="utf-8") as sink:
        sink.write(json.dumps(value, ensure_ascii=False, sort_keys=True) + "\n")
        sink.flush()


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
        description="Estimate pi_0 from unconditioned real Finance Agent trajectories"
    )
    parser.add_argument("--artifacts-path", required=True)
    parser.add_argument("--model-config-path", required=True)
    parser.add_argument("--archive-config-path", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--task-count", type=int, default=2)
    parser.add_argument(
        "--replicas-per-task",
        type=int,
        default=MINIMUM_INITIAL_REPLICAS_PER_TASK,
    )
    parser.add_argument("--prior-strength", type=float, default=1.0)
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--temperature", type=float, default=0.6)
    parser.add_argument("--seed", type=int, default=20260803)
    parser.add_argument(
        "--sampling-salt",
        default="finance_v12_initial_distribution_dev_20260803",
    )
    return parser


def main() -> None:
    report = run_initial_distribution(_parser().parse_args())
    print(report.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
