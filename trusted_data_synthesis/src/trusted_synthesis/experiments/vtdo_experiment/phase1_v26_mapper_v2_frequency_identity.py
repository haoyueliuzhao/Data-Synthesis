from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, cast

from trusted_synthesis.canonical_json import strict_canonical_hash
from trusted_synthesis.core.evaluation.joint_support_validity import JointSupportValidityContract
from trusted_synthesis.core.evaluation.valid_only_state_mapping_v2 import (
    ValidOnlyStateMapperContractV2,
    make_valid_only_state_mapper_contract_v2,
)
from trusted_synthesis.core.trajectory.empirical_state_mapping_v2 import (
    EmpiricalStateSemanticPolicyV2,
    extract_typed_action_references_v2,
    make_experimental_condition_v2,
)
from trusted_synthesis.core.trajectory.reachability_frequency_v2 import (
    BoundedGenerationPolicyV2,
    TaskConditionCellCatalogV2,
    make_bounded_generation_policy_v2,
    make_task_condition_cell_catalog_v2,
    make_task_condition_cell_v2,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_bounded_dynamic_role_preflight as bounded,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_capability_runner_preflight as capability,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_reachability_runner_preflight as reachability,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_mapper_v2_frequency_preflight_inputs as base,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_valid_only_state_semantics_audit as state_semantics,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_mapper_v2_frequency_preflight_models import (  # noqa: E501
    FrequencyAssignmentContract,
    FrequencyEstimandContract,
    FrequencyExecutionContract,
    FrequencyJob,
    FrequencyManifest,
    FrequencyOutcomeContract,
    FrequencyRunnerContract,
    MapperV2FrequencyProtocol,
    OmegaTaskContextCatalogV2,
    OmegaTaskContextV2,
    ToolSchemaClosureAudit,
    ToolSchemaClosureRow,
)
from trusted_synthesis.runtime.agent.prospective_qualified_final_response_grammar import (
    QualifiedFinalResponseGrammar,
)


def load_semantic_policy(package_root: Path) -> EmpiricalStateSemanticPolicyV2:
    policy = EmpiricalStateSemanticPolicyV2.model_validate(
        base._load(package_root / state_semantics.OUTPUT_DIR / "mapper_v2_semantic_policy.json")
    )
    predecessor_report = state_semantics.StateSemanticsAuditReport.model_validate(
        base._load(package_root / state_semantics.OUTPUT_DIR / "report.json")
    )
    if (
        predecessor_report.report_id != base.EXPECTED_PREDECESSOR_REPORT_ID
        or predecessor_report.semantic_policy_id != policy.policy_id
    ):
        raise ValueError("v26.160 Mapper v2 semantic policy changed")
    return policy


def make_omega_catalog(
    *,
    tasks: reachability.TaskPackageCatalog,
    semantic_policy: EmpiricalStateSemanticPolicyV2,
) -> OmegaTaskContextCatalogV2:
    contexts: list[OmegaTaskContextV2] = []
    for package in tasks.packages:
        values = {
            "task_package_id": package.task_package_id,
            "source_task_artifact_id": package.source_task_artifact_id,
            "mechanism_id": package.mechanism_id,
            "tier": package.tier,
            "operational_record_id": package.operational_record.record_id,
            "environment_manifest_id": package.environment.manifest_id,
            "verifier_contract_id": package.verifier_vnext_contract_id,
            "joint_support_validity_contract_id": (package.joint_support_validity_contract_id),
            "qualified_final_grammar_id": package.qualified_final_grammar_id,
            "semantic_policy_id": semantic_policy.policy_id,
            "typed_reference_policy_id": semantic_policy.typed_reference_policy.policy_id,
            "task_package_content_hash": strict_canonical_hash(
                package,
                prefix="finance_v26_frequency_task_package_content:",
            ),
            "operational_record_content_hash": strict_canonical_hash(
                package.operational_record,
                prefix="finance_v26_frequency_operational_record_content:",
            ),
            "environment_content_hash": strict_canonical_hash(
                package.environment,
                prefix="finance_v26_frequency_environment_content:",
            ),
        }
        contexts.append(
            cast(
                OmegaTaskContextV2,
                base._model(
                    OmegaTaskContextV2,
                    values,
                    field="context_id",
                    prefix="finance_v26_frequency_omega_task_context:",
                ),
            )
        )
    catalog_values: dict[str, Any] = {
        "task_package_catalog_id": tasks.catalog_id,
        "semantic_policy_id": semantic_policy.policy_id,
        "contexts": tuple(sorted(contexts, key=lambda item: item.context_id)),
    }
    return cast(
        OmegaTaskContextCatalogV2,
        base._model(
            OmegaTaskContextCatalogV2,
            catalog_values,
            field="catalog_id",
            prefix="finance_v26_frequency_omega_catalog:",
        ),
    )


def make_mapper_contract(
    *,
    package_root: Path,
    tasks: reachability.TaskPackageCatalog,
    semantic_policy: EmpiricalStateSemanticPolicyV2,
) -> tuple[ValidOnlyStateMapperContractV2, str]:
    verifier_ids = {item.verifier_vnext_contract_id for item in tasks.packages}
    if len(verifier_ids) != 1:
        raise ValueError("v26.160 TaskPackages crossed Qualified Verifier Contracts")
    production_path = package_root / state_semantics.MAPPER_V2_PATH
    reference_path = package_root / state_semantics.REFERENCE_MAPPER_V2_PATH
    frequency_path = package_root / base.IMPLEMENTATION_PATHS[0]
    implementation_id = strict_canonical_hash(
        {
            "production_mapper": {
                "relative_path": state_semantics.MAPPER_V2_PATH,
                "sha256": base._sha256(production_path),
            },
            "frequency_core": {
                "relative_path": base.IMPLEMENTATION_PATHS[0],
                "sha256": base._sha256(frequency_path),
            },
        },
        prefix="finance_v26_frequency_mapper_v2_implementation:",
    )
    reference_implementation_id = strict_canonical_hash(
        {
            "relative_path": state_semantics.REFERENCE_MAPPER_V2_PATH,
            "sha256": base._sha256(reference_path),
        },
        prefix="finance_v26_frequency_reference_mapper_implementation:",
    )
    return (
        make_valid_only_state_mapper_contract_v2(
            qualified_verifier_contract_id=next(iter(verifier_ids)),
            mapper_implementation_id=implementation_id,
            semantic_policy_id=semantic_policy.policy_id,
        ),
        reference_implementation_id,
    )


def make_tool_closure(
    *,
    tasks: reachability.TaskPackageCatalog,
    paths: reachability.PathCatalog,
    registered: Sequence[reachability._CompiledPath],
    unconditional: Sequence[reachability._CompiledPath],
    semantic_policy: EmpiricalStateSemanticPolicyV2,
) -> ToolSchemaClosureAudit:
    environment_counts: Counter[str] = Counter(
        tool.tool_id for package in tasks.packages for tool in package.environment.tools
    )
    candidate_counts: Counter[str] = Counter(
        candidate.tool_id
        for execution in (*registered, *unconditional)
        for state in execution.states
        for candidate in state.action_candidates
        if candidate.tool_id is not None
    )
    commit_counts: Counter[str] = Counter(
        commit.call.tool_id
        for execution in (*registered, *unconditional)
        for commit in execution.commits
        if commit.call is not None
    )
    schemas = {item.tool_id: item for item in semantic_policy.typed_reference_policy.tool_schemas}
    expected = set(schemas)
    if (
        set(environment_counts) != expected
        or set(candidate_counts) != expected
        or set(commit_counts) != expected
        or len(expected) != 6
    ):
        raise ValueError("v26.160 reachable Tool set is not closed by Mapper v2 schemas")
    try:
        extract_typed_action_references_v2(
            tool_id="unregistered_fixture_tool",
            arguments={},
            observation_result=None,
            policy=semantic_policy.typed_reference_policy,
        )
    except ValueError:
        unknown_rejected = 1
    else:
        raise ValueError("v26.160 unknown Tool did not fail closed")
    tool_schema_version_id = strict_canonical_hash(
        semantic_policy.typed_reference_policy.tool_schemas,
        prefix="finance_v26_frequency_tool_schema_version:",
    )
    rows = tuple(
        ToolSchemaClosureRow(
            tool_id=tool_id,
            schema_hash=strict_canonical_hash(
                schemas[tool_id],
                prefix="finance_v26_frequency_tool_schema:",
            ),
            environment_manifest_count=environment_counts[tool_id],
            reachable_candidate_count=candidate_counts[tool_id],
            reference_commit_count=commit_counts[tool_id],
        )
        for tool_id in sorted(expected)
    )
    values = {
        "semantic_policy_id": semantic_policy.policy_id,
        "typed_reference_policy_id": semantic_policy.typed_reference_policy.policy_id,
        "tool_schema_version_id": tool_schema_version_id,
        "task_package_catalog_id": tasks.catalog_id,
        "path_catalog_id": paths.catalog_id,
        "unknown_tool_rejection_count": unknown_rejected,
        "closure_rows": rows,
    }
    return cast(
        ToolSchemaClosureAudit,
        base._model(
            ToolSchemaClosureAudit,
            values,
            field="audit_id",
            prefix="finance_v26_frequency_tool_schema_closure:",
        ),
    )


def make_generation_policy(
    *,
    resource: reachability.ResourceContract,
    tasks: reachability.TaskPackageCatalog,
) -> BoundedGenerationPolicyV2:
    support_ids = {item.measurement_support_contract_id for item in tasks.packages}
    if len(support_ids) != 1:
        raise ValueError("v26.160 TaskPackages crossed Measurement Support Contracts")
    return make_bounded_generation_policy_v2(
        resource_contract_id=resource.contract_id,
        measurement_support_contract_id=next(iter(support_ids)),
    )


def make_cell_catalog(
    *,
    tasks: reachability.TaskPackageCatalog,
    paths: reachability.PathCatalog,
    generation_policy: BoundedGenerationPolicyV2,
) -> TaskConditionCellCatalogV2:
    cells = []
    for package in tasks.packages:
        condition = make_experimental_condition_v2(
            sampling_mode="reachability_unconditional",
            public_condition_id=None,
            requested_path_id=None,
            requested_path_strategy=None,
            static_path_catalog_id=paths.catalog_id,
        )
        cells.append(
            make_task_condition_cell_v2(
                task_package_id=package.task_package_id,
                experimental_condition=condition,
                generation_policy_id=generation_policy.policy_id,
            )
        )
    for path in paths.paths:
        condition = make_experimental_condition_v2(
            sampling_mode="reachability_conditioned",
            public_condition_id=path.public_condition_id,
            requested_path_id=path.path_id,
            requested_path_strategy=path.path_strategy_id,
            static_path_catalog_id=paths.catalog_id,
        )
        cells.append(
            make_task_condition_cell_v2(
                task_package_id=path.task_package_id,
                experimental_condition=condition,
                generation_policy_id=generation_policy.policy_id,
            )
        )
    catalog = make_task_condition_cell_catalog_v2(
        static_path_catalog_id=paths.catalog_id,
        generation_policy_id=generation_policy.policy_id,
        cells=cells,
    )
    if (
        catalog.task_count != base.TASK_COUNT
        or catalog.cell_count != base.CELL_COUNT
        or catalog.unconditional_cell_count != base.TASK_COUNT
        or catalog.conditioned_cell_count != base.PATH_COUNT
    ):
        raise ValueError("v26.160 TaskConditionCell denominator changed")
    return catalog


def make_assignment_contract(
    *,
    mapper_contract: ValidOnlyStateMapperContractV2,
    semantic_policy: EmpiricalStateSemanticPolicyV2,
    cells: TaskConditionCellCatalogV2,
) -> FrequencyAssignmentContract:
    values = {
        "mapper_contract_id": mapper_contract.contract_id,
        "semantic_policy_id": semantic_policy.policy_id,
        "task_condition_cell_catalog_id": cells.catalog_id,
    }
    return cast(
        FrequencyAssignmentContract,
        base._model(
            FrequencyAssignmentContract,
            values,
            field="contract_id",
            prefix="finance_v26_frequency_assignment_contract:",
        ),
    )


def make_mapper_protocol(
    *,
    semantic_policy: EmpiricalStateSemanticPolicyV2,
    mapper_contract: ValidOnlyStateMapperContractV2,
    omega: OmegaTaskContextCatalogV2,
    cells: TaskConditionCellCatalogV2,
    assignment_contract: FrequencyAssignmentContract,
    tool_closure: ToolSchemaClosureAudit,
) -> MapperV2FrequencyProtocol:
    values = {
        "semantic_policy": semantic_policy,
        "mapper_contract": mapper_contract,
        "omega_task_context_catalog_id": omega.catalog_id,
        "task_condition_cell_catalog_id": cells.catalog_id,
        "frequency_assignment_contract_id": assignment_contract.contract_id,
        "tool_schema_closure_audit_id": tool_closure.audit_id,
        "tool_schema_version_id": tool_closure.tool_schema_version_id,
    }
    return cast(
        MapperV2FrequencyProtocol,
        base._model(
            MapperV2FrequencyProtocol,
            values,
            field="protocol_id",
            prefix="finance_v26_mapper_v2_frequency_protocol:",
        ),
    )


def make_estimand_contract(
    *,
    cells: TaskConditionCellCatalogV2,
    generation_policy: BoundedGenerationPolicyV2,
    assignment_contract: FrequencyAssignmentContract,
) -> FrequencyEstimandContract:
    values = {
        "task_condition_cell_catalog_id": cells.catalog_id,
        "generation_policy_id": generation_policy.policy_id,
        "frequency_assignment_contract_id": assignment_contract.contract_id,
    }
    return cast(
        FrequencyEstimandContract,
        base._model(
            FrequencyEstimandContract,
            values,
            field="contract_id",
            prefix="finance_v26_frequency_estimand_contract:",
        ),
    )


def make_execution_contract(
    *,
    population: Any,
    selection: Any,
    tasks: reachability.TaskPackageCatalog,
    paths: reachability.PathCatalog,
    resource: reachability.ResourceContract,
    generation_policy: BoundedGenerationPolicyV2,
    protocol: MapperV2FrequencyProtocol,
    cells: TaskConditionCellCatalogV2,
    estimand: FrequencyEstimandContract,
    assignment_contract: FrequencyAssignmentContract,
    joint: JointSupportValidityContract,
) -> FrequencyExecutionContract:
    values = {
        "source_population_id": population.population_id,
        "source_selection_audit_id": selection.audit_id,
        "task_package_catalog_id": tasks.catalog_id,
        "path_catalog_id": paths.catalog_id,
        "resource_contract_id": resource.contract_id,
        "generation_policy_id": generation_policy.policy_id,
        "mapper_protocol_id": protocol.protocol_id,
        "mapper_contract_id": protocol.mapper_contract.contract_id,
        "task_condition_cell_catalog_id": cells.catalog_id,
        "frequency_estimand_contract_id": estimand.contract_id,
        "frequency_assignment_contract_id": assignment_contract.contract_id,
        "joint_support_validity_contract_id": joint.contract_id,
    }
    return cast(
        FrequencyExecutionContract,
        base._model(
            FrequencyExecutionContract,
            values,
            field="contract_id",
            prefix="finance_v26_frequency_execution_contract:",
        ),
    )


def _historical_seed_and_job_ids(package_root: Path) -> tuple[set[int], set[str]]:
    historical_seeds: set[int] = set()
    historical_jobs: set[str] = set()
    manifests = (
        capability.CapabilityManifest.model_validate(
            base._load(package_root / capability.OUTPUT_DIR / "capability_manifest.json")
        ),
        reachability.ReachabilityManifest.model_validate(
            base._load(package_root / reachability.OUTPUT_DIR / "reachability_manifest.json")
        ),
    )
    for manifest in manifests:
        historical_seeds.update(item.seed for item in manifest.jobs)
        historical_jobs.update(item.job_id for item in manifest.jobs)
    return historical_seeds, historical_jobs


def _fresh_seed(payload: Mapping[str, Any], used: set[int], historical: set[int]) -> int:
    nonce = 0
    while True:
        digest = strict_canonical_hash(
            {"salt": base.SEED_SALT, "payload": dict(payload), "nonce": nonce},
            prefix="finance_v26_frequency_seed:",
        )
        seed = int(digest.rsplit(":", 1)[-1][:16], 16)
        if seed not in used and seed not in historical:
            used.add(seed)
            return seed
        nonce += 1


def _job(
    *,
    contract: FrequencyExecutionContract,
    resource: reachability.ResourceContract,
    protocol: MapperV2FrequencyProtocol,
    package: reachability.FreshReachabilityTaskPackage,
    cell: Any,
    selection_id: str,
    replicate: int,
    seed: int,
    generation_policy: BoundedGenerationPolicyV2,
    path: reachability.FreshReachabilityPath | None,
) -> FrequencyJob:
    values = {
        "execution_contract_id": contract.contract_id,
        "resource_contract_id": resource.contract_id,
        "mapper_protocol_id": protocol.protocol_id,
        "task_condition_cell_id": cell.cell_id,
        "task_package_id": package.task_package_id,
        "source_task_artifact_id": package.source_task_artifact_id,
        "mechanism_id": package.mechanism_id,
        "tier": package.tier,
        "sampling_mode": cell.experimental_condition.sampling_mode,
        "replicate_index": replicate,
        "seed": seed,
        "experimental_condition": cell.experimental_condition,
        "requested_path_id": None if path is None else path.path_id,
        "requested_path_strategy": None if path is None else path.path_strategy_id,
        "public_path_condition": None if path is None else path.public_path_condition,
        "public_condition_id": None if path is None else path.public_condition_id,
        "stage_one_profile_id": package.stage_one_profile_id,
        "stage_two_profile_id": package.stage_two_profile_id,
        "exact_final_response_grammar_id": package.qualified_final_grammar_id,
        "generation_policy_id": generation_policy.policy_id,
        "candidate_presentation_parent_id": selection_id,
    }
    return cast(
        FrequencyJob,
        base._model(
            FrequencyJob,
            values,
            field="job_id",
            prefix="finance_v26_frequency_job:",
        ),
    )


def make_manifest(
    *,
    package_root: Path,
    contract: FrequencyExecutionContract,
    population: Any,
    selection: Any,
    tasks: reachability.TaskPackageCatalog,
    paths: reachability.PathCatalog,
    resource: reachability.ResourceContract,
    protocol: MapperV2FrequencyProtocol,
    cells: TaskConditionCellCatalogV2,
    generation_policy: BoundedGenerationPolicyV2,
) -> FrequencyManifest:
    historical_seeds, historical_job_ids = _historical_seed_and_job_ids(package_root)
    cell_by_key = {
        (item.task_package_id, item.experimental_condition.requested_path_id): item
        for item in cells.cells
    }
    paths_by_task: dict[str, list[reachability.FreshReachabilityPath]] = defaultdict(list)
    for path in paths.paths:
        paths_by_task[path.task_package_id].append(path)
    jobs: list[FrequencyJob] = []
    used_seeds: set[int] = set()
    for package in tasks.packages:
        cell = cell_by_key[(package.task_package_id, None)]
        for replicate in range(base.UNCONDITIONAL_REPLICAS):
            seed = _fresh_seed(
                {
                    "task_package_id": package.task_package_id,
                    "task_condition_cell_id": cell.cell_id,
                    "replicate_index": replicate,
                },
                used_seeds,
                historical_seeds,
            )
            jobs.append(
                _job(
                    contract=contract,
                    resource=resource,
                    protocol=protocol,
                    package=package,
                    cell=cell,
                    selection_id=selection.audit_id,
                    replicate=replicate,
                    seed=seed,
                    generation_policy=generation_policy,
                    path=None,
                )
            )
        for path in sorted(paths_by_task[package.task_package_id], key=lambda item: item.path_id):
            cell = cell_by_key[(package.task_package_id, path.path_id)]
            for replicate in range(base.CONDITIONED_REPLICAS):
                seed = _fresh_seed(
                    {
                        "task_package_id": package.task_package_id,
                        "task_condition_cell_id": cell.cell_id,
                        "replicate_index": replicate,
                    },
                    used_seeds,
                    historical_seeds,
                )
                jobs.append(
                    _job(
                        contract=contract,
                        resource=resource,
                        protocol=protocol,
                        package=package,
                        cell=cell,
                        selection_id=selection.audit_id,
                        replicate=replicate,
                        seed=seed,
                        generation_policy=generation_policy,
                        path=path,
                    )
                )
    ordered = tuple(sorted(jobs, key=lambda item: item.job_id))
    if historical_job_ids & {item.job_id for item in ordered}:
        raise ValueError("v26.160 Job identity overlaps history")
    values = {
        "execution_contract_id": contract.contract_id,
        "source_population_id": population.population_id,
        "source_selection_audit_id": selection.audit_id,
        "resource_contract_id": resource.contract_id,
        "mapper_protocol_id": protocol.protocol_id,
        "task_condition_cell_catalog_id": cells.catalog_id,
        "prospective_runner_run_id": base.PROSPECTIVE_RUNNER_RUN_ID,
        "prospective_execution_run_id": base.PROSPECTIVE_EXECUTION_RUN_ID,
        "prospective_report_run_id": base.PROSPECTIVE_REPORT_RUN_ID,
        "jobs": ordered,
    }
    return cast(
        FrequencyManifest,
        base._model(
            FrequencyManifest,
            values,
            field="manifest_id",
            prefix="finance_v26_frequency_manifest:",
        ),
    )


def make_outcome_contract(
    *,
    execution: FrequencyExecutionContract,
    manifest: FrequencyManifest,
    estimand: FrequencyEstimandContract,
    assignment: FrequencyAssignmentContract,
) -> FrequencyOutcomeContract:
    values = {
        "execution_contract_id": execution.contract_id,
        "manifest_id": manifest.manifest_id,
        "frequency_estimand_contract_id": estimand.contract_id,
        "frequency_assignment_contract_id": assignment.contract_id,
    }
    return cast(
        FrequencyOutcomeContract,
        base._model(
            FrequencyOutcomeContract,
            values,
            field="contract_id",
            prefix="finance_v26_frequency_outcome_contract:",
        ),
    )


def make_runner_contract(
    *,
    execution: FrequencyExecutionContract,
    manifest: FrequencyManifest,
    outcome: FrequencyOutcomeContract,
    resource: reachability.ResourceContract,
    protocol: MapperV2FrequencyProtocol,
    assignment: FrequencyAssignmentContract,
    cells: TaskConditionCellCatalogV2,
    tool_closure: ToolSchemaClosureAudit,
    reference_implementation_id: str,
    grammar: QualifiedFinalResponseGrammar,
    joint: JointSupportValidityContract,
) -> FrequencyRunnerContract:
    values = {
        "execution_contract_id": execution.contract_id,
        "manifest_id": manifest.manifest_id,
        "outcome_contract_id": outcome.contract_id,
        "resource_contract_id": resource.contract_id,
        "mapper_protocol_id": protocol.protocol_id,
        "mapper_contract_id": protocol.mapper_contract.contract_id,
        "frequency_assignment_contract_id": assignment.contract_id,
        "task_condition_cell_catalog_id": cells.catalog_id,
        "tool_schema_closure_audit_id": tool_closure.audit_id,
        "independent_reference_mapper_implementation_id": reference_implementation_id,
        "stage_one_profile_id": bounded.EXPECTED_STAGE_ONE_PROFILE_ID,
        "stage_two_profile_id": bounded.EXPECTED_STAGE_TWO_PROFILE_ID,
        "exact_final_response_grammar_id": grammar.grammar_id,
        "joint_support_validity_contract_id": joint.contract_id,
        "qualified_final_grammar_id": grammar.grammar_id,
        "runner_run_id": base.PROSPECTIVE_RUNNER_RUN_ID,
        "execution_run_id": base.PROSPECTIVE_EXECUTION_RUN_ID,
    }
    return cast(
        FrequencyRunnerContract,
        base._model(
            FrequencyRunnerContract,
            values,
            field="contract_id",
            prefix="finance_v26_frequency_runner_contract:",
        ),
    )
