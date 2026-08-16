from __future__ import annotations

import argparse
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, cast

from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_boundary import (
    CapabilityRuntimeArm,
    _make_runtime_binding,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_boundary_analysis import (
    CapabilityRolloutOutcome,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_submechanism_flash_development import (  # noqa: E501
    _make_terminals,
    make_submechanism_behavior_observations,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_multitier_confirmation import (
    _execute_stage,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_multitier_runtime_resolution import (
    _load_records,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_pro_flash_agent_pilot import (
    ExplorerArm,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_stopping_boundary_calibration import (
    FinanceStoppingBoundaryCalibrationContract,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_stopping_contextual_counterfactual import (  # noqa: E501
    EXPECTED_ACTION_BY_CONDITION,
    EXPECTED_ROLLOUT_COUNT,
    PAIR_COUNT,
    REPLICAS,
    ContextualPairFlipResult,
    FinanceStoppingContextualCounterfactualContract,
    FinanceStoppingContextualCounterfactualPopulation,
    FinanceStoppingContextualCounterfactualProtocol,
    FinanceStoppingContextualCounterfactualReport,
    FinanceStoppingContextualFlipReport,
    _artifact_id,
    _population_implementation_manifest,
    _reference,
    _sha256,
    _verify_protocol_inputs,
    _verify_reference,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_stopping_instrument_reset import (
    InstrumentResetRawAudit,
    make_raw_instrument_audit,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_stopping_shape_policy import (
    FinanceStoppingShapePolicyContract,
    FinanceStoppingShapePolicyReport,
    make_stopping_shape_policy_observations,
    make_stopping_shape_policy_report,
    stopping_shape_policy_contract_id,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_stopping_shape_policy import (
    _implementation_manifest as _shape_execution_implementation_manifest,
)
from trusted_synthesis.hashing import canonical_hash
from trusted_synthesis.runtime.agent.iterative import IterativeAgentFailureArtifact

PREFIX = "stopping_contextual_counterfactual"
BASE_CONTRACT_NAME = "finance_stopping_shape_policy_contract.json"
WRAPPER_CONTRACT_NAME = "finance_stopping_contextual_counterfactual_contract.json"
RAW_AUDIT_NAME = "finance_stopping_contextual_counterfactual_raw_audit.json"
SHAPE_REPORT_NAME = "finance_stopping_contextual_counterfactual_shape_report.json"
FLIP_REPORT_NAME = "finance_stopping_contextual_flip_report.json"
REPORT_NAME = "finance_stopping_contextual_counterfactual_report.json"
REPORT_MARKDOWN_NAME = "finance_stopping_contextual_counterfactual_report.md"
MANIFEST_NAME = "finance_stopping_contextual_counterfactual_manifest.json"


def prepare_contextual_counterfactual_contract(
    *,
    protocol_path: Path,
    population_path: Path,
    output_dir: Path,
    run_id: str,
) -> tuple[
    FinanceStoppingShapePolicyContract,
    FinanceStoppingContextualCounterfactualContract,
]:
    output_dir.mkdir(parents=True, exist_ok=False)
    protocol_path = protocol_path.resolve()
    population_path = population_path.resolve()
    protocol = FinanceStoppingContextualCounterfactualProtocol.model_validate_json(
        protocol_path.read_text(encoding="utf-8")
    )
    population = FinanceStoppingContextualCounterfactualPopulation.model_validate_json(
        population_path.read_text(encoding="utf-8")
    )
    _verify_protocol_inputs(protocol)
    _verify_population(protocol, population, population_path)

    calibration_path = Path(protocol.source_calibration_contract.path).resolve()
    calibration = FinanceStoppingBoundaryCalibrationContract.model_validate_json(
        calibration_path.read_text(encoding="utf-8")
    )
    if calibration.contract_id != protocol.source_calibration_contract.artifact_id:
        raise ValueError("v25.46 calibration identity changed")
    model_contracts = tuple(
        item for item in calibration.model_contracts if item.arm == ExplorerArm.FLASH
    )
    if len(model_contracts) != 1:
        raise ValueError("v25.46 requires exactly one frozen Flash model")

    tasks = tuple(item.artifact for item in population.tasks)
    bindings = tuple(
        _make_runtime_binding(
            task,
            CapabilityRuntimeArm.AUTONOMOUS_AGENT,
            calibration.protocol_profile,
        )
        for task in tasks
    )
    record_by_task = {item.artifact.artifact_id: item for item in population.tasks}
    design_by_shape = {item.shape_id: item for item in protocol.shape_designs}
    task_design_statuses = {
        task_id: (
            "structural_redesign"
            if item.shape_id == "contextual_resolution_choice"
            else design_by_shape[item.shape_id].design_status
        )
        for task_id, item in record_by_task.items()
    }
    task_instances = {
        task_id: canonical_hash(
            {
                "task_record_id": item.task_record_id,
                "shape_id": item.shape_id,
                "stratum_id": item.stratum_id,
                "stratum_instance_index": (population.task_stratum_instance_indices[task_id]),
                "design_status": task_design_statuses[task_id],
                "pair_id": population.task_pair_ids[task_id],
                "context_condition": population.task_context_conditions[task_id],
                "semantic_signature": item.source_semantic_signature,
                "materializer_hash": item.materializer_hash,
                "estimand_definition": protocol.estimand_definition,
            },
            prefix="finance_stopping_contextual_counterfactual_task_instance:",
        )
        for task_id, item in record_by_task.items()
    }
    rollout_tokens = {
        f"{binding.binding_id}|{replicate}": canonical_hash(
            {
                "run_id": run_id,
                "binding_id": binding.binding_id,
                "replicate": replicate,
                "task_instance_id": task_instances[binding.task_artifact_id],
            },
            prefix="finance_stopping_contextual_counterfactual_rollout:",
        )
        for binding in bindings
        for replicate in range(REPLICAS)
    }
    shape_implementation = _shape_execution_implementation_manifest()
    finance_config = Path(calibration.finance_archive_config_path).resolve()
    base_values = {
        "run_id": run_id,
        "source_protocol": _reference(protocol_path, protocol.protocol_id),
        "source_population": _reference(population_path, population.population_id),
        "source_calibration_contract": _reference(calibration_path, calibration.contract_id),
        "finance_archive_config_path": str(finance_config),
        "finance_archive_config_sha256": _sha256(finance_config),
        "implementation_manifest": shape_implementation,
        "implementation_manifest_hash": canonical_hash(
            shape_implementation,
            prefix="finance_stopping_shape_policy_implementation:",
        ),
        "model_contracts": model_contracts,
        "protocol_profile": calibration.protocol_profile,
        "estimand_definition": protocol.estimand_definition,
        "tasks": tasks,
        "task_records": population.tasks,
        "task_shape_ids": {task_id: item.shape_id for task_id, item in record_by_task.items()},
        "task_shape_roles": {task_id: item.shape_role for task_id, item in record_by_task.items()},
        "task_design_statuses": task_design_statuses,
        "task_stratum_instance_indices": (population.task_stratum_instance_indices),
        "task_stratum_ids": {task_id: item.stratum_id for task_id, item in record_by_task.items()},
        "task_submechanism_ids": {
            task_id: item.scenario.submechanism_id for task_id, item in record_by_task.items()
        },
        "task_parent_mechanism_ids": {
            task_id: item.scenario.parent_mechanism_id for task_id, item in record_by_task.items()
        },
        "task_instance_ids": task_instances,
        "task_expected_host_events": population.task_expected_host_events,
        "task_raw_capability_demands": {
            task_id: design_by_shape[item.shape_id].spec.raw_capability_demand
            for task_id, item in record_by_task.items()
        },
        "task_difficulty_vectors": {
            task_id: item.difficulty for task_id, item in record_by_task.items()
        },
        "bindings": bindings,
        "maximum_model_tokens_per_rollout": (calibration.maximum_model_tokens_per_rollout),
        "maximum_observation_summary_bytes": (calibration.maximum_observation_summary_bytes),
        "maximum_public_context_bytes": calibration.maximum_public_context_bytes,
        "model_contract_repair_attempts": calibration.model_contract_repair_attempts,
        "rollout_identity_tokens": rollout_tokens,
        "thresholds": protocol.shape_thresholds,
    }
    provisional_base = FinanceStoppingShapePolicyContract.model_construct(
        contract_id="pending", **base_values
    )
    base = FinanceStoppingShapePolicyContract(
        contract_id=stopping_shape_policy_contract_id(provisional_base),
        **base_values,
    )
    base_path = output_dir / BASE_CONTRACT_NAME
    _write_or_verify_json(base_path, base.model_dump(mode="json"))

    implementation = _execution_implementation_manifest()
    wrapper_values = {
        "run_id": run_id,
        "source_protocol": _reference(protocol_path, protocol.protocol_id),
        "source_population": _reference(population_path, population.population_id),
        "source_execution_contract": _reference(base_path, base.contract_id),
        "implementation_manifest": implementation,
        "implementation_manifest_hash": canonical_hash(
            implementation,
            prefix="finance_stopping_contextual_counterfactual_implementation:",
        ),
        "pair_ids": tuple(sorted(item.pair_id for item in population.contextual_pairs)),
        "task_pair_ids": population.task_pair_ids,
        "task_context_conditions": population.task_context_conditions,
        "flip_thresholds": protocol.flip_thresholds,
    }
    provisional_wrapper = FinanceStoppingContextualCounterfactualContract.model_construct(
        contract_id="pending", **wrapper_values
    )
    wrapper = FinanceStoppingContextualCounterfactualContract(
        contract_id=_artifact_id(
            provisional_wrapper,
            "contract_id",
            "finance_stopping_contextual_counterfactual_contract:",
        ),
        **wrapper_values,
    )
    _write_or_verify_json(
        output_dir / WRAPPER_CONTRACT_NAME,
        wrapper.model_dump(mode="json"),
    )
    return base, wrapper


def run_contextual_counterfactual(
    *, contract_path: Path, output_dir: Path, workers: int
) -> FinanceStoppingContextualCounterfactualReport:
    wrapper, base, population = _load_execution_inputs(contract_path)
    if (output_dir / REPORT_NAME).exists():
        raise ValueError("v25.46 immutable final report already exists")
    output_dir.mkdir(parents=True, exist_ok=True)
    outcomes, discovered = _execute_stage(
        contract=cast(Any, base),
        tasks={item.artifact_id: item for item in base.tasks},
        bindings=base.bindings,
        model_arm=ExplorerArm.FLASH,
        replicas=base.replicas,
        output_dir=output_dir,
        prefix=PREFIX,
        workers=workers,
    )
    return _finalize_run(
        wrapper=wrapper,
        base=base,
        population=population,
        output_dir=output_dir,
        outcomes=outcomes,
        discovered_models=discovered,
    )


def finalize_contextual_counterfactual_run(
    *, contract_path: Path, output_dir: Path
) -> FinanceStoppingContextualCounterfactualReport:
    """Recompute deterministic artifacts after an interrupted post-API finalization."""

    wrapper, base, population = _load_execution_inputs(contract_path)
    records_path = output_dir / f"{PREFIX}_records.jsonl"
    outcomes_path = output_dir / f"{PREFIX}_outcomes.jsonl"
    discovery_path = output_dir / f"{PREFIX}_model_discovery.json"
    missing = tuple(
        str(path) for path in (records_path, outcomes_path, discovery_path) if not path.is_file()
    )
    if missing:
        raise ValueError(f"v25.46 finalizer lacks expensive artifacts: {missing}")
    outcomes = _load_outcomes(outcomes_path)
    discovery = json.loads(discovery_path.read_text(encoding="utf-8"))
    discovered_models = tuple(str(item) for item in discovery["discovered_models"])
    return _finalize_run(
        wrapper=wrapper,
        base=base,
        population=population,
        output_dir=output_dir,
        outcomes=outcomes,
        discovered_models=discovered_models,
    )


def make_contextual_flip_report(
    wrapper: FinanceStoppingContextualCounterfactualContract,
    population: FinanceStoppingContextualCounterfactualPopulation,
    records: Sequence[Any],
) -> FinanceStoppingContextualFlipReport:
    records_by_key = {(item.task_artifact_id, item.replicate): item for item in records}
    if len(records_by_key) != EXPECTED_ROLLOUT_COUNT:
        raise ValueError("Contextual Flip lacks the full rollout denominator")
    task_by_id = {item.artifact.artifact_id: item for item in population.tasks}
    pair_results = []
    for pair in sorted(population.contextual_pairs, key=lambda item: item.pair_id):
        period_values = []
        definition_values = []
        dual_values = []
        for replicate in range(REPLICAS):
            period_record = records_by_key[(pair.period_task_artifact_id, replicate)]
            definition_record = records_by_key[(pair.definition_task_artifact_id, replicate)]
            period_correct = _contextual_action_correct(
                period_record,
                task_by_id[pair.period_task_artifact_id],
                expected_action=pair.period_expected_action,
            )
            definition_correct = _contextual_action_correct(
                definition_record,
                task_by_id[pair.definition_task_artifact_id],
                expected_action=pair.definition_expected_action,
            )
            period_values.append(period_correct)
            definition_values.append(definition_correct)
            dual_values.append(period_correct and definition_correct)
        period_count = sum(period_values)
        definition_count = sum(definition_values)
        dual_count = sum(dual_values)
        period_rate = period_count / REPLICAS
        definition_rate = definition_count / REPLICAS
        pair_results.append(
            ContextualPairFlipResult(
                pair_id=pair.pair_id,
                stratum_id=pair.stratum_id,
                period_action_correct_count=period_count,
                definition_action_correct_count=definition_count,
                dual_correct_replicate_count=dual_count,
                period_action_correct_rate=period_rate,
                definition_action_correct_rate=definition_rate,
                dual_correct_rate=dual_count / REPLICAS,
                action_rate_difference=abs(period_rate - definition_rate),
                informative=(
                    dual_count >= wrapper.flip_thresholds.minimum_dual_correct_replicates_per_pair
                ),
            )
        )
    results = tuple(pair_results)
    period_total = sum(item.period_action_correct_count for item in results)
    definition_total = sum(item.definition_action_correct_count for item in results)
    dual_total = sum(item.dual_correct_replicate_count for item in results)
    informative = sum(item.informative for item in results)
    max_difference = max(item.action_rate_difference for item in results)
    flip_rate = dual_total / (PAIR_COUNT * REPLICAS)
    rejections = []
    if flip_rate < wrapper.flip_thresholds.minimum_contextual_flip_consistency:
        rejections.append("minimum_contextual_flip_consistency")
    if informative < wrapper.flip_thresholds.minimum_informative_pair_count:
        rejections.append("minimum_informative_pair_count")
    if max_difference > wrapper.flip_thresholds.maximum_branch_action_rate_difference:
        rejections.append("maximum_branch_action_rate_difference")
    values = {
        "contract_id": wrapper.contract_id,
        "pair_results": results,
        "period_action_correct_count": period_total,
        "definition_action_correct_count": definition_total,
        "dual_correct_replicate_count": dual_total,
        "contextual_flip_consistency": flip_rate,
        "informative_pair_count": informative,
        "maximum_branch_action_rate_difference": max_difference,
        "thresholds": wrapper.flip_thresholds,
        "passed": not rejections,
        "rejection_reasons": tuple(rejections),
    }
    provisional = FinanceStoppingContextualFlipReport.model_construct(report_id="pending", **values)
    return FinanceStoppingContextualFlipReport(
        report_id=_artifact_id(
            provisional,
            "report_id",
            "finance_stopping_contextual_flip_report:",
        ),
        **values,
    )


def _contextual_action_correct(
    record: Any,
    task: Any,
    *,
    expected_action: str,
) -> bool:
    observations = _record_observations(record)
    required_ids = {item.evidence_id for item in task.scenario.evidence_roles}
    selected: set[str] = set()
    action_set = {
        *EXPECTED_ACTION_BY_CONDITION.values(),
        "open_document",
    }
    for observation in observations:
        prerequisites_ready = required_ids <= selected
        if prerequisites_ready and observation.call.tool_id in action_set:
            return bool(
                observation.call.tool_id == expected_action and observation.status == "succeeded"
            )
        if observation.status == "succeeded":
            selected.update(observation.evidence_ids)
    return False


def _record_observations(record: Any) -> tuple[Any, ...]:
    if record.status == "completed":
        return tuple(record.observations)
    if record.status == "failed" and record.failure_artifact is not None:
        try:
            failure = IterativeAgentFailureArtifact.model_validate(record.failure_artifact)
        except ValueError:
            return ()
        return tuple(failure.observations)
    return ()


def _finalize_run(
    *,
    wrapper: FinanceStoppingContextualCounterfactualContract,
    base: FinanceStoppingShapePolicyContract,
    population: FinanceStoppingContextualCounterfactualPopulation,
    output_dir: Path,
    outcomes: tuple[CapabilityRolloutOutcome, ...],
    discovered_models: tuple[str, ...],
) -> FinanceStoppingContextualCounterfactualReport:
    records_path = output_dir / f"{PREFIX}_records.jsonl"
    records = _load_records(records_path)
    raw = make_raw_instrument_audit(cast(Any, wrapper), base, records)
    _write_or_verify_json(output_dir / RAW_AUDIT_NAME, raw.model_dump(mode="json"))

    shape: FinanceStoppingShapePolicyReport | None = None
    flip: FinanceStoppingContextualFlipReport | None = None
    if raw.shape_analysis_authorized:
        terminals = _make_terminals(cast(Any, base), records, outcomes)
        behaviors = make_submechanism_behavior_observations(
            cast(Any, base), records, outcomes, terminals
        )
        observations = make_stopping_shape_policy_observations(base, behaviors, outcomes, terminals)
        _write_or_verify_jsonl(
            output_dir / f"{PREFIX}_terminal_outcomes.jsonl",
            (item.model_dump(mode="json") for item in terminals),
        )
        _write_or_verify_jsonl(
            output_dir / f"{PREFIX}_behavior_diagnostics.jsonl",
            (item.model_dump(mode="json") for item in behaviors),
        )
        _write_or_verify_jsonl(
            output_dir / f"{PREFIX}_shape_observations.jsonl",
            (item.model_dump(mode="json") for item in observations),
        )
        shape = make_stopping_shape_policy_report(
            base,
            records,
            outcomes,
            terminals,
            observations,
            discovered_models=discovered_models,
        )
        _write_or_verify_json(output_dir / SHAPE_REPORT_NAME, shape.model_dump(mode="json"))
        flip = make_contextual_flip_report(wrapper, population, records)
        _write_or_verify_json(output_dir / FLIP_REPORT_NAME, flip.model_dump(mode="json"))

    report = _make_overall_report(wrapper, raw, shape, flip)
    report_path = output_dir / REPORT_NAME
    markdown_path = output_dir / REPORT_MARKDOWN_NAME
    _write_or_verify_json(report_path, report.model_dump(mode="json"))
    _write_or_verify_text(markdown_path, _render_report(report, raw, shape, flip))
    manifest = _make_manifest(
        wrapper=wrapper,
        report=report,
        raw=raw,
        shape=shape,
        flip=flip,
        output_dir=output_dir,
    )
    _write_or_verify_json(output_dir / MANIFEST_NAME, manifest)
    return report


def _make_overall_report(
    wrapper: FinanceStoppingContextualCounterfactualContract,
    raw: InstrumentResetRawAudit,
    shape: FinanceStoppingShapePolicyReport | None,
    flip: FinanceStoppingContextualFlipReport | None,
) -> FinanceStoppingContextualCounterfactualReport:
    all_shapes = bool(shape and shape.all_shapes_contract_passing)
    flip_passed = bool(flip and flip.passed)
    values = {
        "contract_id": wrapper.contract_id,
        "raw_audit_id": raw.audit_id,
        "raw_instrument_status": raw.instrument_status,
        "shape_analysis_authorized": raw.shape_analysis_authorized,
        "shape_report_id": shape.report_id if shape else None,
        "flip_report_id": flip.report_id if flip else None,
        "successful_agent_outcome_count": raw.successful_record_count,
        "fail_closed_behavior_outcome_count": raw.behavior_failure_record_count,
        "full_valid_trajectory_count": (shape.valid_training_trajectory_count if shape else 0),
        "boundary_candidate_admitted_count": (
            shape.boundary_candidate_admitted_count if shape else 0
        ),
        "runtime_control_pass_count": shape.runtime_control_pass_count if shape else 0,
        "all_shape_contracts_passing": all_shapes,
        "contextual_flip_passing": flip_passed,
        "all_v25_46_gates_passing": bool(
            raw.shape_analysis_authorized and all_shapes and flip_passed
        ),
        "next_permitted_stage": (
            "instrument_repair_only"
            if not raw.shape_analysis_authorized
            else (
                "fresh_three_population_shape_policy_preparation"
                if all_shapes and flip_passed
                else "contextual_shape_redesign_only"
            )
        ),
    }
    provisional = FinanceStoppingContextualCounterfactualReport.model_construct(
        report_id="pending", **values
    )
    return FinanceStoppingContextualCounterfactualReport(
        report_id=_artifact_id(
            provisional,
            "report_id",
            "finance_stopping_contextual_counterfactual_report:",
        ),
        **values,
    )


def _load_execution_inputs(
    contract_path: Path,
) -> tuple[
    FinanceStoppingContextualCounterfactualContract,
    FinanceStoppingShapePolicyContract,
    FinanceStoppingContextualCounterfactualPopulation,
]:
    wrapper = FinanceStoppingContextualCounterfactualContract.model_validate_json(
        contract_path.read_text(encoding="utf-8")
    )
    for reference in (
        wrapper.source_protocol,
        wrapper.source_population,
        wrapper.source_execution_contract,
    ):
        _verify_reference(reference.path, reference.sha256)
    if wrapper.implementation_manifest != _execution_implementation_manifest():
        raise ValueError("v25.46 execution implementation changed after freeze")
    protocol = FinanceStoppingContextualCounterfactualProtocol.model_validate_json(
        Path(wrapper.source_protocol.path).read_text(encoding="utf-8")
    )
    population = FinanceStoppingContextualCounterfactualPopulation.model_validate_json(
        Path(wrapper.source_population.path).read_text(encoding="utf-8")
    )
    base = FinanceStoppingShapePolicyContract.model_validate_json(
        Path(wrapper.source_execution_contract.path).read_text(encoding="utf-8")
    )
    _verify_protocol_inputs(protocol)
    _verify_population(protocol, population, Path(wrapper.source_population.path))
    if base.implementation_manifest != _shape_execution_implementation_manifest():
        raise ValueError("v25.46 frozen Shape runner implementation changed")
    if not (
        base.contract_id == wrapper.source_execution_contract.artifact_id
        and base.run_id == wrapper.run_id
        and set(base.task_shape_ids) == set(wrapper.task_pair_ids)
        and wrapper.task_pair_ids == population.task_pair_ids
        and wrapper.task_context_conditions == population.task_context_conditions
        and set(wrapper.pair_ids) == {item.pair_id for item in population.contextual_pairs}
    ):
        raise ValueError("v25.46 wrapper, base Contract, and population differ")
    return wrapper, base, population


def _verify_population(
    protocol: FinanceStoppingContextualCounterfactualProtocol,
    population: FinanceStoppingContextualCounterfactualPopulation,
    population_path: Path,
) -> None:
    _verify_reference(population.source_protocol.path, population.source_protocol.sha256)
    if not (
        population.source_protocol.artifact_id == protocol.protocol_id
        and population.run_id
        and population.static_audit.ready
        and population.next_permitted_stage == "flash_contextual_counterfactual_development"
        and population.implementation_manifest == _population_implementation_manifest()
    ):
        raise ValueError("v25.46 population is not execution-ready")


def _execution_implementation_manifest() -> dict[str, str]:
    root = Path(__file__).resolve().parents[4]
    paths = (
        "src/trusted_synthesis/runtime/agent/client.py",
        "src/trusted_synthesis/runtime/agent/iterative.py",
        "src/trusted_synthesis/domains/finance/agent_tools.py",
        "src/trusted_synthesis/domains/finance/interactive_agent_runtime.py",
        "src/trusted_synthesis/domains/finance/iterative_agent_verifier.py",
        "src/trusted_synthesis/domains/finance/public_tool_results.py",
        "src/trusted_synthesis/domains/finance/capability_submechanism_runtime.py",
        "src/trusted_synthesis/experiments/vtdo_experiment/phase1_capability_boundary_runner.py",
        "src/trusted_synthesis/experiments/vtdo_experiment/phase1_multitier_confirmation.py",
        "src/trusted_synthesis/experiments/vtdo_experiment/phase1_stopping_shape_policy.py",
        "src/trusted_synthesis/experiments/vtdo_experiment/phase1_stopping_instrument_reset.py",
        "src/trusted_synthesis/experiments/vtdo_experiment/phase1_stopping_contextual_counterfactual.py",
        "src/trusted_synthesis/experiments/vtdo_experiment/phase1_stopping_contextual_counterfactual_runner.py",
        "src/trusted_synthesis/experiments/vtdo_experiment/phase1_stopping_contextual_counterfactual_finalize.py",
    )
    return {path: _sha256(root / path) for path in paths}


def _load_outcomes(path: Path) -> tuple[CapabilityRolloutOutcome, ...]:
    return tuple(
        CapabilityRolloutOutcome.model_validate_json(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    )


def _make_manifest(
    *,
    wrapper: FinanceStoppingContextualCounterfactualContract,
    report: FinanceStoppingContextualCounterfactualReport,
    raw: InstrumentResetRawAudit,
    shape: FinanceStoppingShapePolicyReport | None,
    flip: FinanceStoppingContextualFlipReport | None,
    output_dir: Path,
) -> dict[str, Any]:
    names = (
        f"{PREFIX}_records.jsonl",
        f"{PREFIX}_outcomes.jsonl",
        f"{PREFIX}_model_discovery.json",
        RAW_AUDIT_NAME,
        REPORT_NAME,
        REPORT_MARKDOWN_NAME,
        *((SHAPE_REPORT_NAME, FLIP_REPORT_NAME) if shape and flip else ()),
    )
    return {
        "schema_version": "finance_stopping_contextual_counterfactual_manifest.v1",
        "contract_id": wrapper.contract_id,
        "report_id": report.report_id,
        "raw_audit_id": raw.audit_id,
        "shape_report_id": shape.report_id if shape else None,
        "flip_report_id": flip.report_id if flip else None,
        "artifact_sha256": {name: _sha256(output_dir / name) for name in sorted(names)},
        "execution_implementation_manifest_hash": (wrapper.implementation_manifest_hash),
        "api_execution_replayed": False,
        "deterministic_recomputation_passed": True,
        "historical_shape_support_transferred": False,
        "pro_api_call_count": 0,
        "beneficiary_authorized": False,
        "exact_target_authorized": False,
        "gp_c_authorized": False,
        "production_contribution": 0.0,
    }


def _write_or_verify_json(path: Path, value: Mapping[str, Any] | dict[str, Any]) -> None:
    if path.exists():
        observed = json.loads(path.read_text(encoding="utf-8"))
        if observed != value:
            raise ValueError(f"v25.46 immutable JSON differs: {path}")
        return
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_or_verify_jsonl(path: Path, values: Any) -> None:
    rows = tuple(values)
    if path.exists():
        observed = tuple(
            json.loads(line)
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        )
        if observed != rows:
            raise ValueError(f"v25.46 immutable JSONL differs: {path}")
        return
    path.write_text(
        "".join(json.dumps(item, ensure_ascii=False, sort_keys=True) + "\n" for item in rows),
        encoding="utf-8",
    )


def _write_or_verify_text(path: Path, value: str) -> None:
    if path.exists():
        if path.read_text(encoding="utf-8") != value:
            raise ValueError(f"v25.46 immutable text differs: {path}")
        return
    path.write_text(value, encoding="utf-8")


def _render_report(
    report: FinanceStoppingContextualCounterfactualReport,
    raw: InstrumentResetRawAudit,
    shape: FinanceStoppingShapePolicyReport | None,
    flip: FinanceStoppingContextualFlipReport | None,
) -> str:
    lines = [
        "# Finance v25.46 Contextual Counterfactual Development",
        "",
        f"- Raw instrument status: `{report.raw_instrument_status}`",
        f"- Auditable records: **{raw.auditable_record_count}/384**",
        f"- Successful Agent outcomes: **{report.successful_agent_outcome_count}**",
        f"- Fail-closed behavior outcomes: **{report.fail_closed_behavior_outcome_count}**",
        f"- Full-valid trajectories: **{report.full_valid_trajectory_count}**",
        "- Recursive Host field / marker violations: "
        f"**{raw.recursive_host_field_violation_count}/"
        f"{raw.recursive_host_marker_violation_count}**",
        f"- Shape analysis authorized: **{report.shape_analysis_authorized}**",
        f"- Boundary candidates admitted: **{report.boundary_candidate_admitted_count}/4**",
        f"- Runtime controls passed: **{report.runtime_control_pass_count}/2**",
        f"- All Shape contracts passing: **{report.all_shape_contracts_passing}**",
        f"- Contextual Flip passing: **{report.contextual_flip_passing}**",
        f"- All v25.46 gates passing: **{report.all_v25_46_gates_passing}**",
        f"- Next permitted stage: `{report.next_permitted_stage}`",
        "- Historical Shape support transferred: **false**",
        "- Pro / Beneficiary / Exact Target / GP-C: **blocked**",
        "- Production Contribution: **0**",
        "",
    ]
    if raw.rejection_reasons:
        lines.extend(
            ["## Instrument failures", "", *(f"- `{x}`" for x in raw.rejection_reasons), ""]
        )
    if shape is not None:
        lines.extend(
            [
                "## Shape diagnostics",
                "",
                f"- Stopping success: **{shape.stopping_behavior_success_rate:.4f}**",
                f"- Full-valid success: **{shape.full_valid_trajectory_success_rate:.4f}**",
                f"- Semantic success: **{shape.answer_semantic_success_rate:.4f}**",
                "",
            ]
        )
        for item in shape.shape_results:
            lines.append(
                f"- `{item.shape_id}`: admitted={item.admitted}, "
                f"stopping={item.mean_stopping_success_rate:.4f}, "
                f"range={item.between_task_stopping_probability_range:.4f}, "
                f"failures={list(item.failure_codes)}"
            )
        lines.append("")
    if flip is not None:
        lines.extend(
            [
                "## Contextual flip",
                "",
                f"- Dual-correct consistency: **{flip.contextual_flip_consistency:.4f}**",
                f"- Informative pairs: **{flip.informative_pair_count}/4**",
                "- Maximum branch action-rate difference: "
                f"**{flip.maximum_branch_action_rate_difference:.4f}**",
                f"- Passed: **{flip.passed}**",
                "",
            ]
        )
    return "\n".join(lines)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Prepare, run, or finalize Finance v25.46")
    sub = parser.add_subparsers(dest="command", required=True)
    prepare = sub.add_parser("prepare")
    prepare.add_argument("--protocol", type=Path, required=True)
    prepare.add_argument("--population", type=Path, required=True)
    prepare.add_argument("--output-dir", type=Path, required=True)
    prepare.add_argument("--run-id", required=True)
    run = sub.add_parser("run")
    run.add_argument("--contract", type=Path, required=True)
    run.add_argument("--output-dir", type=Path, required=True)
    run.add_argument("--workers", type=int, default=48)
    finalize = sub.add_parser("finalize")
    finalize.add_argument("--contract", type=Path, required=True)
    finalize.add_argument("--output-dir", type=Path, required=True)
    return parser


def main() -> None:
    args = _parser().parse_args()
    if args.command == "prepare":
        prepare_contextual_counterfactual_contract(
            protocol_path=args.protocol,
            population_path=args.population,
            output_dir=args.output_dir,
            run_id=args.run_id,
        )
    elif args.command == "run":
        run_contextual_counterfactual(
            contract_path=args.contract,
            output_dir=args.output_dir,
            workers=args.workers,
        )
    else:
        finalize_contextual_counterfactual_run(
            contract_path=args.contract,
            output_dir=args.output_dir,
        )


if __name__ == "__main__":
    main()
