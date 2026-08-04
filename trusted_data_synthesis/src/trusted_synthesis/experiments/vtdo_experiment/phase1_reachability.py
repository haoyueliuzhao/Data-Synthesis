from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import stat
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from trusted_synthesis.core.operations.registry import default_registry
from trusted_synthesis.core.trajectory.state import map_trajectory_to_state
from trusted_synthesis.core.vtdo import (
    AnchoredDistributionUpdate,
    StateReachabilityManifest,
    make_public_state_generation_request,
    make_unconditioned_reachability_manifest,
    update_valid_trajectory_distribution,
)
from trusted_synthesis.experiments.vtdo_experiment.multistate import (
    FinanceTaskStateArtifact,
    load_finance_multi_state_artifacts,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_mvp import _make_evaluator
from trusted_synthesis.hashing import canonical_hash
from trusted_synthesis.runtime.agent import (
    AgentModelConfig,
    LLMAgentSolver,
    LLMClientError,
    OpenAICompatibleJsonClient,
    StateConditionedLLMTrajectoryProvider,
    assess_state_condition_controllability,
)
from trusted_synthesis.runtime.tools import InMemoryEvidenceToolRuntime

PHASE11_REACHABILITY_VERSION = "finance_phase1_reachability.v1"
DEFAULT_TARGET_TASK_ID = "task:61de93de9105f5c99ec23dc792f0cbb2c7252b8db6002f31522da43b402aeb01"
EXPLORER_PROVIDER_ID = "deepseek_v4_pro_state_conditioned.phase1"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_jsonl(path: Path, values: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(item, ensure_ascii=False, sort_keys=True) + "\n" for item in values),
        encoding="utf-8",
    )


def _load_model_config(path: Path, *, temperature: float) -> AgentModelConfig:
    raw = json.loads(path.read_text(encoding="utf-8"))
    value = raw.get("model", raw)
    config = AgentModelConfig.model_validate(value)
    _load_project_credential(config.api_key_env)
    return config.model_copy(
        update={
            "temperature": temperature,
            "interaction_protocol": "host_instrumented",
        }
    )


def _load_project_credential(variable_name: str) -> None:
    """Load one credential from a private project .env without changing run identity."""
    if os.environ.get(variable_name):
        return
    path = Path.cwd() / ".env"
    if not path.exists():
        return
    mode = stat.S_IMODE(path.stat().st_mode)
    if mode & 0o077:
        raise ValueError("project .env must not be accessible by group or other users")
    matches: list[str] = []
    for line_number, raw_line in enumerate(
        path.read_text(encoding="utf-8").splitlines(),
        start=1,
    ):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line.removeprefix("export ").lstrip()
        key, separator, raw_value = line.partition("=")
        if not separator or not key.strip():
            raise ValueError(f"invalid project .env entry on line {line_number}")
        if key.strip() != variable_name:
            continue
        value = raw_value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        if not value:
            continue
        matches.append(value)
    if len(matches) > 1:
        raise ValueError(f"project .env defines {variable_name} more than once")
    if matches:
        os.environ[variable_name] = matches[0]


def _select_artifacts(
    artifacts: tuple[FinanceTaskStateArtifact, ...],
    *,
    task_count: int,
    required_task_id: str,
) -> tuple[FinanceTaskStateArtifact, ...]:
    if task_count < 1:
        raise ValueError("task_count must be positive")
    by_id = {item.omega.task.task_id: item for item in artifacts}
    required = by_id.get(required_task_id)
    if required is None:
        raise ValueError(f"required comparison task is missing: {required_task_id}")
    groups: defaultdict[str, list[FinanceTaskStateArtifact]] = defaultdict(list)
    for artifact in artifacts:
        task_type = artifact.omega.task.public.task_type
        groups[task_type].append(artifact)
    for values in groups.values():
        values.sort(key=lambda item: item.artifact_id)
    selected = [required]
    seen = {required.artifact_id}
    cursor = 0
    group_names = tuple(sorted(groups))
    while len(selected) < min(task_count, len(artifacts)):
        progressed = False
        for group_name in group_names:
            values = groups[group_name]
            if cursor >= len(values):
                continue
            candidate = values[cursor]
            progressed = True
            if candidate.artifact_id not in seen:
                selected.append(candidate)
                seen.add(candidate.artifact_id)
                if len(selected) == min(task_count, len(artifacts)):
                    break
        if not progressed:
            break
        cursor += 1
    return tuple(selected)


def _error_record(
    *,
    artifact: FinanceTaskStateArtifact,
    replicate: int,
    mode: str,
    exc: Exception,
    generation_audit: dict[str, Any] | None = None,
    requested_state_id: str | None = None,
) -> dict[str, Any]:
    telemetry = (
        [item.model_dump(mode="json") for item in exc.telemetry]
        if isinstance(exc, LLMClientError)
        else []
    )
    record = {
        "task_id": artifact.omega.task.task_id,
        "task_type": artifact.omega.task.public.task_type,
        "replicate": replicate,
        "mode": mode,
        "status": "failed",
        "requested_state_id": requested_state_id,
        "error_type": type(exc).__name__,
        "error_message": " ".join(str(exc).split())[:500],
        "telemetry": telemetry,
    }
    if generation_audit is not None:
        record["generation_audit"] = generation_audit
        record["failure_stage"] = "trajectory_evaluation"
    else:
        record["failure_stage"] = "model_generation"
    return record


def _solve_unconditioned(
    solver: LLMAgentSolver,
    artifact: FinanceTaskStateArtifact,
    replicate: int,
):
    result = solver.solve_with_audit(
        artifact.omega.task.public,
        InMemoryEvidenceToolRuntime(artifact.omega.public_corpus),
    )
    return artifact, replicate, result


def _evaluate_result(
    evaluator,
    artifact: FinanceTaskStateArtifact,
    result,
    *,
    replicate: int,
    mode: str,
    requested_state_id: str | None = None,
) -> dict[str, Any]:
    context = artifact.omega
    report = evaluator.evaluate(context, result.trajectory)
    assignment = map_trajectory_to_state(
        context,
        result.trajectory,
        program_node_aliases=report.program_node_mapping,
    )
    catalog_hit = assignment.state.state_id in artifact.state_catalog.states
    return {
        "task_id": context.task.task_id,
        "task_type": context.task.public.task_type,
        "replicate": replicate,
        "mode": mode,
        "status": "completed",
        "requested_state_id": requested_state_id,
        "on_target": (
            assignment.state.state_id == requested_state_id
            if requested_state_id is not None
            else None
        ),
        "catalog_hit": catalog_hit,
        "trajectory": result.trajectory.model_dump(mode="json"),
        "generation_audit": result.audit.model_dump(mode="json"),
        "validity_report": report.model_dump(mode="json"),
        "state_assignment": assignment.model_dump(mode="json"),
    }


def _telemetry(records: list[dict[str, Any]]) -> dict[str, Any]:
    calls: list[dict[str, Any]] = []
    for record in records:
        audit = record.get("generation_audit")
        if isinstance(audit, dict):
            calls.extend(audit.get("telemetry") or [])
        calls.extend(record.get("telemetry") or [])
    selected_models = Counter(
        str(item.get("response_model") or item.get("model_selected") or "unknown")
        for item in calls
        if item.get("http_success")
    )
    token_bearing_calls = [item for item in calls if int(item.get("total_tokens") or 0)]
    priced_calls = [
        item
        for item in token_bearing_calls
        if item.get("estimated_cost") is not None and item.get("cost_estimation_method") is not None
    ]
    estimation_methods = Counter(str(item["cost_estimation_method"]) for item in priced_calls)
    unpriced_call_count = len(token_bearing_calls) - len(priced_calls)
    return {
        "api_call_count": len(calls),
        "api_call_success_count": sum(bool(item.get("http_success")) for item in calls),
        "json_contract_success_count": sum(
            bool(item.get("json_contract_success")) for item in calls
        ),
        "prompt_tokens": sum(int(item.get("prompt_tokens") or 0) for item in calls),
        "completion_tokens": sum(int(item.get("completion_tokens") or 0) for item in calls),
        "total_tokens": sum(int(item.get("total_tokens") or 0) for item in calls),
        "reported_estimated_cost": sum(float(item.get("estimated_cost") or 0.0) for item in calls),
        "selected_models": dict(sorted(selected_models.items())),
        "fallback_call_count": sum(bool(item.get("fallback_used")) for item in calls),
        "priced_call_count": len(priced_calls),
        "unpriced_call_count": unpriced_call_count,
        "cost_estimation_methods": dict(sorted(estimation_methods.items())),
        "cost_warning": (
            "One or more token-bearing calls lack a frozen price estimate; token counts remain "
            "authoritative for those calls."
            if unpriced_call_count
            else None
        ),
    }


def _entropy(counts: Counter[str]) -> float:
    total = sum(counts.values())
    if not total:
        return 0.0
    return -sum((count / total) * math.log(count / total) for count in counts.values() if count)


def _reachability_manifests(
    selected: tuple[FinanceTaskStateArtifact, ...],
    records: list[dict[str, Any]],
    *,
    batch_id: str,
) -> dict[str, StateReachabilityManifest]:
    by_task: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        if record["mode"] == "unconditioned":
            by_task[record["task_id"]].append(record)
    manifests: dict[str, StateReachabilityManifest] = {}
    for artifact in selected:
        task_records = by_task[artifact.omega.task.task_id]
        state_counts = {state_id: 0 for state_id in artifact.state_catalog.states}
        for record in task_records:
            if record.get("status") != "completed":
                continue
            if not record["validity_report"]["valid"]:
                continue
            assignment = record["state_assignment"]
            state_id = assignment["state"]["state_id"]
            if state_id in state_counts:
                state_counts[state_id] += 1
        manifests[artifact.omega.task.task_id] = make_unconditioned_reachability_manifest(
            task_condition_id=artifact.omega.task.task_id,
            explorer_provider_id=EXPLORER_PROVIDER_ID,
            explorer_provider_version=PHASE11_REACHABILITY_VERSION,
            state_counts=state_counts,
            attempted_trajectory_count=len(task_records),
            source_batch_ids=(batch_id,),
        )
    return manifests


def _compare_update(
    aggregate_dir: Path,
    manifest: StateReachabilityManifest,
    output_dir: Path,
) -> dict[str, Any]:
    archived = AnchoredDistributionUpdate.model_validate_json(
        (aggregate_dir / "anchored_distribution_update.json").read_text(encoding="utf-8")
    )
    config = archived.energy_config.model_copy(
        update={
            "reachability_weight": 1.0,
            "reachability_floor": 0.01,
            "reachability_signal": "posterior_mean",
        }
    )
    support = set(archived.prior_distribution.probabilities)
    subset = tuple(item for item in manifest.estimates if item.state_id in support)
    if {item.state_id for item in subset} != support:
        raise ValueError("target-task reachability does not cover archived update support")
    values = {
        "task_condition_id": manifest.task_condition_id,
        "explorer_provider_id": manifest.explorer_provider_id,
        "explorer_provider_version": manifest.explorer_provider_version,
        "estimates": subset,
        "source_batch_ids": manifest.source_batch_ids,
        "schema_version": manifest.schema_version,
    }
    provisional = StateReachabilityManifest.model_construct(
        manifest_id="pending",
        **values,
    )
    from trusted_synthesis.core.vtdo.schema import state_reachability_manifest_id

    subset_manifest = StateReachabilityManifest(
        manifest_id=state_reachability_manifest_id(provisional),
        **values,
    )
    aware = update_valid_trajectory_distribution(
        archived.prior_distribution,
        archived.coverage_prior,
        archived.validity_estimates,
        archived.contribution_manifest,
        archived.contribution_approximation_authorization,
        config,
        archived.role_contract,
        subset_manifest,
    )
    _write_json(
        output_dir / "reachability_aware_update.json",
        aware.model_dump(mode="json"),
    )
    comparison = {
        "task_condition_id": archived.prior_distribution.task_condition_id,
        "baseline_update_id": archived.update_id,
        "reachability_aware_update_id": aware.update_id,
        "pi0": archived.prior_distribution.probabilities,
        "pi1_baseline": archived.next_distribution.probabilities,
        "pi1_reachability_aware": aware.next_distribution.probabilities,
        "baseline_total_variation": archived.total_variation_from_history,
        "reachability_aware_total_variation": aware.total_variation_from_history,
        "reachability": {
            item.state_id: {
                "attempts": item.attempted_trajectory_count,
                "hits": item.on_target_trajectory_count,
                "posterior_mean": item.posterior_mean,
                "confidence_interval": [
                    item.confidence_lower,
                    item.confidence_upper,
                ],
            }
            for item in subset_manifest.estimates
        },
    }
    comparison["comparison_hash"] = canonical_hash(
        comparison,
        prefix="finance_phase11_update_comparison:",
    )
    return comparison


def run(args: argparse.Namespace) -> None:
    artifact_path = Path(args.artifacts_path).resolve()
    model_config_path = Path(args.model_config_path).resolve()
    archive_config_path = Path(args.archive_config_path).resolve()
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    artifacts = load_finance_multi_state_artifacts(artifact_path)
    selected = _select_artifacts(
        artifacts,
        task_count=args.task_count,
        required_task_id=args.target_task_id,
    )
    model_config = _load_model_config(
        model_config_path,
        temperature=args.temperature,
    )
    client = OpenAICompatibleJsonClient(model_config)
    discovered_models = client.discover_models()
    solver = LLMAgentSolver(client, default_registry())
    evaluator = _make_evaluator(archive_config_path)
    experiment_identity = {
        "experiment_version": PHASE11_REACHABILITY_VERSION,
        "artifact_sha256": _sha256(artifact_path),
        "model_config_hash": model_config.public_manifest_hash,
        "archive_config_sha256": _sha256(archive_config_path),
        "selected_task_ids": tuple(item.omega.task.task_id for item in selected),
        "replicas_per_task": args.replicas_per_task,
        "conditioned_task_count": args.conditioned_task_count,
        "seed": args.seed,
    }
    batch_id = canonical_hash(experiment_identity, prefix="finance_phase11_explorer_batch:")
    records: list[dict[str, Any]] = []
    jobs = [
        (artifact, replicate)
        for artifact in selected
        for replicate in range(args.replicas_per_task)
    ]
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        future_map = {
            executor.submit(_solve_unconditioned, solver, artifact, replicate): (
                artifact,
                replicate,
            )
            for artifact, replicate in jobs
        }
        for future in as_completed(future_map):
            artifact, replicate = future_map[future]
            try:
                result_artifact, result_replicate, result = future.result()
            except Exception as exc:
                records.append(
                    _error_record(
                        artifact=artifact,
                        replicate=replicate,
                        mode="unconditioned",
                        exc=exc,
                    )
                )
                continue
            try:
                evaluated = _evaluate_result(
                    evaluator,
                    result_artifact,
                    result,
                    replicate=result_replicate,
                    mode="unconditioned",
                )
            except Exception as exc:
                records.append(
                    _error_record(
                        artifact=result_artifact,
                        replicate=result_replicate,
                        mode="unconditioned",
                        exc=exc,
                        generation_audit=result.audit.model_dump(mode="json"),
                    )
                )
            else:
                records.append(evaluated)
    records.sort(key=lambda item: (item["task_id"], item["mode"], item["replicate"]))
    checkpoint_path = output_dir / "exploration_records.checkpoint.jsonl"
    _write_jsonl(checkpoint_path, records)

    provider = StateConditionedLLMTrajectoryProvider(
        provider_id=EXPLORER_PROVIDER_ID,
        solver=solver,
        public_corpora_by_task_id={
            item.omega.task.task_id: item.omega.public_corpus for item in selected
        },
    )
    controllability_rows: list[dict[str, Any]] = []
    for artifact in selected[: args.conditioned_task_count]:
        for state_id, condition in sorted(artifact.state_catalog.public_state_conditions.items()):
            request = make_public_state_generation_request(
                artifact.omega,
                condition,
                candidate_count=1,
                seed=args.seed,
            )
            audit = assess_state_condition_controllability(
                request,
                interaction_protocol=solver.interaction_protocol,
            )
            row = {
                "task_id": artifact.omega.task.task_id,
                "state_id": state_id,
                "condition_id": condition.condition_id,
                "audit": audit.model_dump(mode="json"),
                "api_called": False,
            }
            if audit.condition_requestable:
                try:
                    trajectory = next(iter(provider.generate(request)))
                except Exception as exc:
                    records.append(
                        _error_record(
                            artifact=artifact,
                            replicate=0,
                            mode="state_conditioned",
                            exc=exc,
                            requested_state_id=state_id,
                        )
                    )
                    row["api_called"] = True
                    row["error_type"] = type(exc).__name__
                    continue
                result = provider.records[-1]
                from trusted_synthesis.runtime.agent.schema import AgentSolveResult

                solved = AgentSolveResult(
                    trajectory=trajectory,
                    audit=result.generation_audit,
                )
                row["api_called"] = True
                row["generation_constraints_hash"] = (
                    result.generation_audit.generation_constraints_hash
                )
                try:
                    evaluated = _evaluate_result(
                        evaluator,
                        artifact,
                        solved,
                        replicate=0,
                        mode="state_conditioned",
                        requested_state_id=state_id,
                    )
                except Exception as exc:
                    records.append(
                        _error_record(
                            artifact=artifact,
                            replicate=0,
                            mode="state_conditioned",
                            exc=exc,
                            generation_audit=result.generation_audit.model_dump(mode="json"),
                            requested_state_id=state_id,
                        )
                    )
                    row["error_type"] = type(exc).__name__
                else:
                    records.append(evaluated)
            controllability_rows.append(row)
    records.sort(key=lambda item: (item["task_id"], item["mode"], item["replicate"]))
    _write_jsonl(output_dir / "exploration_records.jsonl", records)
    _write_jsonl(output_dir / "state_controllability.jsonl", controllability_rows)
    _write_jsonl(
        output_dir / "conditioned_generation_audits.jsonl",
        [item.model_dump(mode="json") for item in provider.records],
    )

    manifests = _reachability_manifests(selected, records, batch_id=batch_id)
    _write_jsonl(
        output_dir / "reachability_manifests.jsonl",
        [item.model_dump(mode="json") for _, item in sorted(manifests.items())],
    )
    completed = [item for item in records if item["status"] == "completed"]
    valid = [item for item in completed if item["validity_report"]["valid"]]
    catalog_hits = [item for item in valid if item["catalog_hit"]]
    observed_counts = Counter(item["state_assignment"]["state"]["state_id"] for item in valid)
    task_reachability = {
        artifact.omega.task.task_id: {
            "task_type": artifact.omega.task.public.task_type,
            "catalog_state_count": len(artifact.state_catalog.states),
            "observed_catalog_state_count": sum(
                item.on_target_trajectory_count > 0
                for item in manifests[artifact.omega.task.task_id].estimates
            ),
            "reachable_state_ratio": (
                sum(
                    item.on_target_trajectory_count > 0
                    for item in manifests[artifact.omega.task.task_id].estimates
                )
                / len(artifact.state_catalog.states)
            ),
        }
        for artifact in selected
    }
    conditioned = [item for item in completed if item["mode"] == "state_conditioned"]
    summary: dict[str, Any] = {
        **experiment_identity,
        "batch_id": batch_id,
        "discovered_models": discovered_models,
        "selected_task_count": len(selected),
        "selected_task_type_counts": dict(
            sorted(Counter(item.omega.task.public.task_type for item in selected).items())
        ),
        "unconditioned_attempt_count": len(jobs),
        "conditioned_target_audit_count": len(controllability_rows),
        "conditioned_requestable_count": sum(
            item["audit"]["condition_requestable"] for item in controllability_rows
        ),
        "conditioned_api_call_target_count": sum(
            item["api_called"] for item in controllability_rows
        ),
        "completed_trajectory_count": len(completed),
        "valid_trajectory_count": len(valid),
        "catalog_hit_count": len(catalog_hits),
        "novel_valid_state_count": len(
            {
                item["state_assignment"]["state"]["state_id"]
                for item in valid
                if not item["catalog_hit"]
            }
        ),
        "observed_state_count": len(observed_counts),
        "observed_state_entropy": _entropy(observed_counts),
        "conditioned_on_target_count": sum(item["on_target"] is True for item in conditioned),
        "conditioned_completed_count": len(conditioned),
        "task_reachability": task_reachability,
        "telemetry": _telemetry(records),
        "status": "passed" if valid and catalog_hits else "partial",
    }
    target_manifest = manifests[args.target_task_id]
    comparison = _compare_update(
        Path(args.phase1_aggregate_dir).resolve(),
        target_manifest,
        output_dir,
    )
    _write_json(output_dir / "update_comparison.json", comparison)
    summary["update_comparison_hash"] = comparison["comparison_hash"]
    summary["summary_hash"] = canonical_hash(
        summary,
        prefix="finance_phase11_reachability_summary:",
    )
    _write_json(output_dir / "summary.json", summary)
    _write_json(
        output_dir / "input_manifest.json",
        {
            **experiment_identity,
            "batch_id": batch_id,
            "artifact_path": str(artifact_path),
            "model_config_path": str(model_config_path),
            "archive_config_path": str(archive_config_path),
        },
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the finance Phase 1.1 Explorer reachability experiment"
    )
    parser.add_argument("--artifacts-path", required=True)
    parser.add_argument("--model-config-path", required=True)
    parser.add_argument("--archive-config-path", required=True)
    parser.add_argument("--phase1-aggregate-dir", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--task-count", type=int, default=20)
    parser.add_argument("--replicas-per-task", type=int, default=2)
    parser.add_argument("--conditioned-task-count", type=int, default=3)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--temperature", type=float, default=0.2)
    parser.add_argument("--seed", type=int, default=20260802)
    parser.add_argument("--target-task-id", default=DEFAULT_TARGET_TASK_ID)
    return parser


def main() -> None:
    run(_parser().parse_args())


if __name__ == "__main__":
    main()
