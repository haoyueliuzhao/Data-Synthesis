from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any, cast

from pydantic import ValidationError

from trusted_synthesis.canonical_json import strict_canonical_hash
from trusted_synthesis.core.trajectory.empirical_state_mapping_v2 import (
    EmpiricalStateSemanticPolicyV2,
    extract_typed_action_references_v2,
    make_state_contrast_v2,
)
from trusted_synthesis.core.trajectory.reachability_frequency_v2 import (
    TaskConditionCellV2,
    make_frequency_measurement_gate_v2,
    make_reachability_frequency_assignment_v2,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_mapper_v2_frequency_fixtures as fixtures,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_mapper_v2_frequency_identity as identity_builders,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_mapper_v2_frequency_preflight_inputs as inputs,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_mapper_v2_frequency_static as static_inputs,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_mapper_v2_frequency_preflight_models import (  # noqa: E501
    BuildProducts,
    DestructiveAudit,
    FrequencyPreflightReport,
    MutationResult,
    ProspectiveTransitionContract,
    RunnerPreflightAudit,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_mapper_v2_gold_fixtures import (
    build_mapper_v2_gold_fixture_audit,
)
from trusted_synthesis.runtime.agent.prospective_qualified_final_response_grammar import (
    compile_qualified_final_response_grammar,
)

RUN_ID = inputs.RUN_ID
OUTPUT_DIR = inputs.OUTPUT_DIR
NEXT_STAGE = inputs.NEXT_STAGE
PROSPECTIVE_EXECUTION_RUN_ID = inputs.PROSPECTIVE_EXECUTION_RUN_ID
PROSPECTIVE_REPORT_RUN_ID = inputs.PROSPECTIVE_REPORT_RUN_ID
ADDITIONAL_IMPLEMENTATION_PATHS = (
    "src/trusted_synthesis/experiments/vtdo_experiment/"
    "phase1_v26_mapper_v2_frequency_preflight_inputs.py",
    "src/trusted_synthesis/experiments/vtdo_experiment/phase1_v26_mapper_v2_frequency_identity.py",
    "src/trusted_synthesis/experiments/vtdo_experiment/phase1_v26_mapper_v2_frequency_fixtures.py",
    "src/trusted_synthesis/experiments/vtdo_experiment/phase1_v26_mapper_v2_frequency_static.py",
)
IMPLEMENTATION_PATHS = tuple(
    dict.fromkeys((*inputs.IMPLEMENTATION_PATHS, *ADDITIONAL_IMPLEMENTATION_PATHS))
)


def _resolve_package_root(implementation_root: Path) -> Path:
    if (implementation_root / "src" / "trusted_synthesis").is_dir():
        return implementation_root
    candidate = implementation_root / "trusted_data_synthesis"
    if (candidate / "src" / "trusted_synthesis").is_dir():
        return candidate
    raise ValueError("v26.160 cannot resolve package root")


def _transition(
    *,
    execution: Any,
    manifest: Any,
    runner: Any,
    outcome: Any,
) -> ProspectiveTransitionContract:
    values = {
        "execution_contract_id": execution.contract_id,
        "manifest_id": manifest.manifest_id,
        "runner_contract_id": runner.contract_id,
        "outcome_contract_id": outcome.contract_id,
    }
    return cast(
        ProspectiveTransitionContract,
        inputs._model(
            ProspectiveTransitionContract,
            values,
            field="contract_id",
            prefix="finance_v26_frequency_transition:",
        ),
    )


def _reject(
    rows: list[MutationResult],
    name: str,
    callback: Any,
) -> None:
    try:
        callback()
    except (AssertionError, TypeError, ValueError, ValidationError) as exc:
        rows.append(
            MutationResult(
                mutation_name=name,
                failure_type=type(exc).__name__,
            )
        )
        return
    raise AssertionError(f"v26.160 destructive mutation did not fail: {name}")


def _destructive_audit(
    *,
    products: dict[str, Any],
) -> DestructiveAudit:
    population = products["population"]
    selection = products["selection"]
    generation = products["generation"]
    cells = products["cells"]
    assignment_contract = products["assignment_contract"]
    protocol = products["protocol"]
    estimand = products["estimand"]
    execution = products["execution"]
    manifest = products["manifest"]
    outcome = products["outcome"]
    runner = products["runner"]
    transition = products["transition"]
    mapper_fixture = products["mapper_fixture"]
    semantic_policy: EmpiricalStateSemanticPolicyV2 = products["semantic_policy"]
    rows: list[MutationResult] = []

    def validate_changed(model: Any, **changes: Any) -> Any:
        return type(model).model_validate({**model.model_dump(mode="python"), **changes})

    _reject(
        rows,
        "source_population_model_exposure_inserted",
        lambda: validate_changed(population, model_exposure_count=1),
    )
    _reject(
        rows,
        "source_binding_outcome_selection_inserted",
        lambda: validate_changed(population.tasks[0], model_outcomes_used_for_selection=True),
    )
    _reject(
        rows,
        "source_selection_compatibility_leak",
        lambda: validate_changed(selection, compatibility_results_used_for_selection=True),
    )
    _reject(
        rows,
        "generation_policy_second_detour",
        lambda: validate_changed(generation, maximum_ordinary_detours=2),
    )
    _reject(
        rows,
        "task_condition_cell_route_inserted",
        lambda: TaskConditionCellV2.model_validate(
            {
                **cells.cells[0].model_dump(mode="python"),
                "empirical_route_signature_id": "forbidden-route",
            }
        ),
    )
    _reject(
        rows,
        "task_condition_cell_task_changed",
        lambda: validate_changed(cells.cells[0], task_package_id="crossed-task"),
    )
    _reject(
        rows,
        "frequency_assignment_parent_removed",
        lambda: validate_changed(
            assignment_contract,
            required_parent_bindings=assignment_contract.required_parent_bindings[1:],
        ),
    )
    _reject(
        rows,
        "diagnostic_assignment_promoted",
        lambda: validate_changed(protocol, v26_159_diagnostic_assignment_promotion=True),
    )
    _reject(
        rows,
        "unrestricted_natural_distribution_claimed",
        lambda: validate_changed(estimand, unrestricted_natural_agent_distribution_claimed=True),
    )
    _reject(
        rows,
        "conditioned_rows_pooled_into_unconditional",
        lambda: validate_changed(
            estimand, conditioned_rows_can_augment_unconditional_denominator=True
        ),
    )
    _reject(
        rows,
        "execution_denominator_changed",
        lambda: validate_changed(execution, exact_denominator=359),
    )
    _reject(
        rows,
        "job_cell_parent_changed",
        lambda: validate_changed(manifest.jobs[0], task_condition_cell_id="crossed-cell"),
    )
    _reject(
        rows,
        "historical_seed_reuse_enabled",
        lambda: validate_changed(manifest.jobs[0], historical_seed_reused=True),
    )
    _reject(
        rows,
        "manifest_job_deleted",
        lambda: validate_changed(manifest, jobs=manifest.jobs[:-1]),
    )
    _reject(
        rows,
        "manifest_seed_duplicated",
        lambda: validate_changed(
            manifest,
            jobs=(
                manifest.jobs[0],
                manifest.jobs[1].model_copy(update={"seed": manifest.jobs[0].seed}),
                *manifest.jobs[2:],
            ),
        ),
    )
    _reject(
        rows,
        "support_exit_row_deletion_enabled",
        lambda: validate_changed(outcome, support_exit_row_deletion_forbidden=False),
    )
    _reject(
        rows,
        "mapper_before_qualified_verifier",
        lambda: validate_changed(runner, mapper_runs_only_after_qualified_verifier=False),
    )
    _reject(
        rows,
        "stage_two_provider_route_enabled",
        lambda: validate_changed(runner, stage_two_provider_call_upper_bound=1),
    )
    _reject(
        rows,
        "historical_reclassification_authorized",
        lambda: validate_changed(
            transition,
            historical_rerun_pooling_or_reclassification_authorized=True,
        ),
    )
    _reject(
        rows,
        "vtdo_authorized_early",
        lambda: validate_changed(transition, vtdo_training_release_or_production_authorized=True),
    )
    failed_gate = make_frequency_measurement_gate_v2(
        exact_job_denominator=48,
        complete_raw_count=48,
        model_endpoint_count=47,
        validity_evaluable_count=47,
        measurement_support_exit_count=1,
    )
    _reject(
        rows,
        "frequency_assignment_after_failed_gate",
        lambda: make_reachability_frequency_assignment_v2(
            experiment_id=runner.execution_run_id,
            job_id=manifest.jobs[0].job_id,
            cell=cells.cells[0],
            mapping_assignment=mapper_fixture.mapping_assignments[0],
            measurement_gate=failed_gate,
        ),
    )
    _reject(
        rows,
        "same_state_contrast_requested",
        lambda: make_state_contrast_v2(
            mapper_fixture.mapping_assignments[0].structural_state,
            mapper_fixture.mapping_assignments[0].structural_state,
        ),
    )
    _reject(
        rows,
        "unknown_tool_schema_fallback",
        lambda: extract_typed_action_references_v2(
            tool_id="unknown-tool",
            arguments={},
            observation_result=None,
            policy=semantic_policy.typed_reference_policy,
        ),
    )
    _reject(
        rows,
        "tool_schema_removed_under_stale_policy",
        lambda: type(semantic_policy.typed_reference_policy).model_validate(
            {
                **semantic_policy.typed_reference_policy.model_dump(mode="python"),
                "tool_schemas": semantic_policy.typed_reference_policy.tool_schemas[:-1],
            }
        ),
    )
    _reject(
        rows,
        "reference_mapper_match_requirement_disabled",
        lambda: validate_changed(runner, reference_mapper_exact_match_required=False),
    )
    ordered = tuple(sorted(rows, key=lambda item: item.mutation_name))
    values = {
        "mutations": ordered,
        "mutation_count": len(ordered),
        "rejected_count": len(ordered),
    }
    return cast(
        DestructiveAudit,
        inputs._model(
            DestructiveAudit,
            values,
            field="audit_id",
            prefix="finance_v26_frequency_destructive:",
        ),
    )


def build_mapper_v2_reachability_frequency_preflight(
    *,
    implementation_root: Path,
    output_dir: Path,
) -> BuildProducts:
    package_root = _resolve_package_root(implementation_root)
    reproducibility_root = inputs._reproducibility_root(
        package_root=package_root,
        implementation_root=package_root,
        implementation_paths=IMPLEMENTATION_PATHS,
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    inputs._write_json_atomic(output_dir / "reproducibility_root_audit.json", reproducibility_root)
    frame, population, selection = inputs._freeze_source_population(
        package_root=package_root,
        output_dir=output_dir,
        root_audit=reproducibility_root,
    )
    print(
        f"[v26.160] fresh source Population frozen: {len(population.tasks)}/12 tasks",
        flush=True,
    )

    # Source identities are persisted before any Mapper, Path, Support, or resource load.
    joint = inputs._load_joint_contract(package_root)
    grammar = compile_qualified_final_response_grammar()
    static = static_inputs.load_static_inputs(package_root)
    tasks = static_inputs.make_task_catalog(
        package_root=package_root,
        population=population,
        selection=selection,
        joint=joint,
        grammar=grammar,
    )
    paths, registered, unconditional = inputs._make_paths(
        tasks=tasks,
        selection=selection,
        static=static,
        grammar=grammar,
    )
    support, detours, resource = inputs._make_support_and_resource(
        package_root=package_root,
        paths=paths,
        registered=registered,
        selection=selection,
        static=static,
        grammar=grammar,
    )
    semantic_policy = identity_builders.load_semantic_policy(package_root)
    omega = identity_builders.make_omega_catalog(
        tasks=tasks,
        semantic_policy=semantic_policy,
    )
    mapper_contract, reference_implementation_id = identity_builders.make_mapper_contract(
        package_root=package_root,
        tasks=tasks,
        semantic_policy=semantic_policy,
    )
    tool_closure = identity_builders.make_tool_closure(
        tasks=tasks,
        paths=paths,
        registered=registered,
        unconditional=unconditional,
        semantic_policy=semantic_policy,
    )
    generation_policy = identity_builders.make_generation_policy(
        resource=resource,
        tasks=tasks,
    )
    cells = identity_builders.make_cell_catalog(
        tasks=tasks,
        paths=paths,
        generation_policy=generation_policy,
    )
    assignment_contract = identity_builders.make_assignment_contract(
        mapper_contract=mapper_contract,
        semantic_policy=semantic_policy,
        cells=cells,
    )
    protocol = identity_builders.make_mapper_protocol(
        semantic_policy=semantic_policy,
        mapper_contract=mapper_contract,
        omega=omega,
        cells=cells,
        assignment_contract=assignment_contract,
        tool_closure=tool_closure,
    )
    estimand = identity_builders.make_estimand_contract(
        cells=cells,
        generation_policy=generation_policy,
        assignment_contract=assignment_contract,
    )
    execution = identity_builders.make_execution_contract(
        population=population,
        selection=selection,
        tasks=tasks,
        paths=paths,
        resource=resource,
        generation_policy=generation_policy,
        protocol=protocol,
        cells=cells,
        estimand=estimand,
        assignment_contract=assignment_contract,
        joint=joint,
    )
    manifest = identity_builders.make_manifest(
        package_root=package_root,
        contract=execution,
        population=population,
        selection=selection,
        tasks=tasks,
        paths=paths,
        resource=resource,
        protocol=protocol,
        cells=cells,
        generation_policy=generation_policy,
    )
    outcome = identity_builders.make_outcome_contract(
        execution=execution,
        manifest=manifest,
        estimand=estimand,
        assignment=assignment_contract,
    )
    runner = identity_builders.make_runner_contract(
        execution=execution,
        manifest=manifest,
        outcome=outcome,
        resource=resource,
        protocol=protocol,
        assignment=assignment_contract,
        cells=cells,
        tool_closure=tool_closure,
        reference_implementation_id=reference_implementation_id,
        grammar=grammar,
        joint=joint,
    )
    temporal_gold = build_mapper_v2_gold_fixture_audit(
        semantic_policy=semantic_policy,
        mapper_contract=mapper_contract,
    )
    generation_fixture = fixtures.make_generation_fixture(
        tasks=tasks,
        registered=registered,
        unconditional=unconditional,
        manifest=manifest,
        resource=resource,
        runner=runner,
        joint=joint,
        grammar=grammar,
        static=static,
    )
    context_by_task = {item.task_package_id: item.context_id for item in omega.contexts}
    mapper_fixture = fixtures.make_independent_mapper_preflight(
        tasks=tasks,
        registered=registered,
        unconditional=unconditional,
        manifest=manifest,
        resource=resource,
        runner=runner,
        joint=joint,
        grammar=grammar,
        static=static,
        cells=cells,
        omega_contexts=context_by_task,
        semantic_policy=semantic_policy,
        mapper_contract=mapper_contract,
    )
    fixture_cell = next(
        item
        for item in cells.cells
        if item.experimental_condition.sampling_mode == "reachability_unconditional"
    )
    within_cell = fixtures.make_within_cell_contrast_audit(
        fixture_cell=fixture_cell,
        omega_context_id=context_by_task[fixture_cell.task_package_id],
        semantic_policy=semantic_policy,
        mapper_contract=mapper_contract,
        mapper_protocol_id=protocol.protocol_id,
    )
    frequency_api = fixtures.make_frequency_api_fixture(
        runner=runner,
        cells=cells,
        mapper_products=mapper_fixture,
    )
    runner_preflight_values = {
        "runner_contract_id": runner.contract_id,
        "manifest_id": manifest.manifest_id,
        "generation_fixture_audit_id": generation_fixture.audit_id,
        "independent_mapper_preflight_audit_id": mapper_fixture.audit.audit_id,
        "frequency_api_fixture_audit_id": frequency_api.audit_id,
        "temporal_gold_fixture_audit_id": temporal_gold.audit_id,
        "within_cell_contrast_audit_id": within_cell.audit_id,
    }
    runner_preflight = cast(
        RunnerPreflightAudit,
        inputs._model(
            RunnerPreflightAudit,
            runner_preflight_values,
            field="audit_id",
            prefix="finance_v26_frequency_runner_preflight:",
        ),
    )
    transition = _transition(
        execution=execution,
        manifest=manifest,
        runner=runner,
        outcome=outcome,
    )
    products_for_mutation = {
        "population": population,
        "selection": selection,
        "generation": generation_policy,
        "cells": cells,
        "assignment_contract": assignment_contract,
        "protocol": protocol,
        "estimand": estimand,
        "execution": execution,
        "manifest": manifest,
        "outcome": outcome,
        "runner": runner,
        "transition": transition,
        "mapper_fixture": mapper_fixture,
        "semantic_policy": semantic_policy,
    }
    destructive = _destructive_audit(products=products_for_mutation)
    prospective_execution_id = strict_canonical_hash(
        {
            "run_id": PROSPECTIVE_EXECUTION_RUN_ID,
            "manifest_id": manifest.manifest_id,
            "runner_contract_id": runner.contract_id,
            "outcome_contract_id": outcome.contract_id,
            "mapper_protocol_id": protocol.protocol_id,
        },
        prefix="finance_v26_mapper_v2_frequency_execution:",
    )
    prospective_report_id = strict_canonical_hash(
        {
            "run_id": PROSPECTIVE_REPORT_RUN_ID,
            "prospective_execution_id": prospective_execution_id,
            "outcome_contract_id": outcome.contract_id,
        },
        prefix="finance_v26_mapper_v2_frequency_execution_report:",
    )
    outputs: tuple[tuple[str, Any], ...] = (
        ("destructive_audit.json", destructive),
        ("detour_qualification_audit.json", detours),
        ("frequency_assignment_contract.json", assignment_contract),
        ("frequency_estimand_contract.json", estimand),
        ("frequency_execution_contract.json", execution),
        ("frequency_manifest.json", manifest),
        ("frequency_outcome_contract.json", outcome),
        ("frequency_runner_contract.json", runner),
        ("frequency_runner_preflight_audit.json", runner_preflight),
        ("frequency_api_fixture_audit.json", frequency_api),
        ("fresh_reachability_source_population.json", population),
        ("fresh_source_sampling_frame.json", frame),
        ("generation_policy.json", generation_policy),
        ("independent_mapper_preflight_audit.json", mapper_fixture.audit),
        ("joint_support_validity_contract.json", joint),
        ("mapper_v2_contract.json", mapper_contract),
        ("mapper_v2_frequency_protocol.json", protocol),
        ("mapper_v2_semantic_policy.json", semantic_policy),
        ("mapper_v2_temporal_gold_fixture_audit.json", temporal_gold),
        ("omega_task_context_catalog.json", omega),
        ("prospective_transition_contract.json", transition),
        ("qualified_final_response_grammar.json", grammar),
        ("reachability_path_catalog.json", paths),
        ("reachability_resource_contract.json", resource),
        ("reachability_runner_fixture_audit.json", generation_fixture),
        ("reachability_task_package_catalog.json", tasks),
        ("reproducibility_root_audit.json", reproducibility_root),
        ("source_selection_audit.json", selection),
        ("support_closure_audit.json", support),
        ("task_condition_cell_catalog.json", cells),
        ("tool_schema_closure_audit.json", tool_closure),
        ("within_cell_state_contrast_audit.json", within_cell),
    )
    for name, value in outputs:
        inputs._write_json_atomic(output_dir / name, value)
    details = tuple(
        sorted(
            (inputs._detail(output_dir / name, output_dir) for name, _ in outputs),
            key=lambda item: item.relative_path,
        )
    )
    report_values = {
        "run_id": RUN_ID,
        "reproducibility_root_audit_id": reproducibility_root.audit_id,
        "source_population_id": population.population_id,
        "source_selection_audit_id": selection.audit_id,
        "task_package_catalog_id": tasks.catalog_id,
        "path_catalog_id": paths.catalog_id,
        "support_closure_audit_id": support.audit_id,
        "resource_contract_id": resource.contract_id,
        "generation_policy_id": generation_policy.policy_id,
        "semantic_policy_id": semantic_policy.policy_id,
        "mapper_contract_id": mapper_contract.contract_id,
        "omega_task_context_catalog_id": omega.catalog_id,
        "task_condition_cell_catalog_id": cells.catalog_id,
        "frequency_assignment_contract_id": assignment_contract.contract_id,
        "mapper_protocol_id": protocol.protocol_id,
        "frequency_estimand_contract_id": estimand.contract_id,
        "tool_schema_closure_audit_id": tool_closure.audit_id,
        "temporal_gold_fixture_audit_id": temporal_gold.audit_id,
        "within_cell_contrast_audit_id": within_cell.audit_id,
        "execution_contract_id": execution.contract_id,
        "manifest_id": manifest.manifest_id,
        "outcome_contract_id": outcome.contract_id,
        "runner_contract_id": runner.contract_id,
        "independent_mapper_preflight_audit_id": mapper_fixture.audit.audit_id,
        "frequency_api_fixture_audit_id": frequency_api.audit_id,
        "runner_preflight_audit_id": runner_preflight.audit_id,
        "destructive_audit_id": destructive.audit_id,
        "transition_contract_id": transition.contract_id,
        "prospective_execution_id": prospective_execution_id,
        "prospective_report_id": prospective_report_id,
        "detail_files": details,
    }
    report = cast(
        FrequencyPreflightReport,
        inputs._model(
            FrequencyPreflightReport,
            report_values,
            field="report_id",
            prefix="finance_v26_frequency_preflight_report:",
        ),
    )
    inputs._write_json_atomic(output_dir / "report.json", report)
    return BuildProducts(
        reproducibility_root=reproducibility_root,
        source_population=population,
        source_selection=selection,
        semantic_policy=semantic_policy,
        mapper_contract=mapper_contract,
        omega_catalog=omega,
        cell_catalog=cells,
        assignment_contract=assignment_contract,
        mapper_protocol=protocol,
        estimand_contract=estimand,
        execution_contract=execution,
        manifest=manifest,
        outcome_contract=outcome,
        runner_contract=runner,
        tool_closure=tool_closure,
        within_cell_contrast=within_cell,
        independent_mapper=mapper_fixture.audit,
        frequency_api=frequency_api,
        runner_preflight=runner_preflight,
        destructive=destructive,
        transition=transition,
        report=report,
        internal={
            "support": support,
            "detours": detours,
            "resource": resource,
            "generation_fixture": generation_fixture,
            "temporal_gold": temporal_gold,
        },
    )


def main() -> None:
    package_default = Path(__file__).resolve().parents[4]
    parser = argparse.ArgumentParser(
        description="Credential-free v26.160 Mapper v2 Reachability frequency preflight"
    )
    parser.add_argument("--implementation-root", type=Path, default=package_default)
    parser.add_argument("--output-dir", type=Path, default=package_default / OUTPUT_DIR)
    args = parser.parse_args()
    products = build_mapper_v2_reachability_frequency_preflight(
        implementation_root=args.implementation_root,
        output_dir=args.output_dir,
    )
    print(products.report.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
