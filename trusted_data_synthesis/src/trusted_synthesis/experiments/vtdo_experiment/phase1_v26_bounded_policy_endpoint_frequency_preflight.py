from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from collections import defaultdict
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any, Final, Literal, cast

from pydantic import BaseModel, ValidationError

from trusted_synthesis.canonical_json import strict_canonical_hash
from trusted_synthesis.core.evaluation.bounded_policy_endpoint import (
    BoundedPolicyCellFrequencyReport,
    BoundedPolicyEndpointGenerationPolicy,
    BoundedPolicyEndpointProjection,
    make_bounded_policy_global_integrity_gate,
    summarize_bounded_policy_cell,
)
from trusted_synthesis.core.trajectory.empirical_state_mapping_v2 import (
    EmpiricalStateSemanticPolicyV2,
    extract_typed_action_references_v2,
    make_state_contrast_v2,
)
from trusted_synthesis.core.trajectory.reachability_frequency_v2 import TaskConditionCellV2
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
    phase1_v26_fresh_role_kernel_compatibility_preflight as source_base,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_mapper_v2_frequency_fixtures as fixtures,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_mapper_v2_frequency_identity as identity_builders,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_mapper_v2_frequency_postrun_audit as predecessor,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_mapper_v2_frequency_preflight_inputs as old_inputs,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_mapper_v2_frequency_static as static_inputs,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_mapper_v2_reachability_frequency_preflight as old_preflight,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_s1_representation_qualification_preflight as s1_runner,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_sensitive_frontier import (
    CapabilitySensitiveFrontierPopulation,
    CapabilitySensitiveTaskArtifact,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_bounded_policy_endpoint_frequency_preflight_models import (  # noqa: E501
    BoundedPolicyEndpointFixtureAudit,
    BoundedPolicyEstimandContract,
    BoundedPolicyFrequencyApiFixtureAudit,
    BoundedPolicyOutcomeContract,
    BoundedPolicyPreflightReport,
    BoundedPolicyRunnerContract,
    BuildProducts,
    DestructiveAudit,
    DetailFile,
    FileBinding,
    MutationResult,
    PredecessorReplayAudit,
    ProspectiveTransitionContract,
    RouteBSourceSelectionAudit,
    RunnerPreflightAudit,
    identity,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_mapper_v2_frequency_preflight_models import (  # noqa: E501
    FrequencyExecutionContract,
    FrequencyJob,
    FrequencyManifest,
    FreshFrequencySourceBinding,
    FreshFrequencySourcePopulation,
    FreshnessChannelRow,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_mapper_v2_gold_fixtures import (
    build_mapper_v2_gold_fixture_audit,
)
from trusted_synthesis.runtime.agent import prospective_reachability_runner_vnext as runner_vnext
from trusted_synthesis.runtime.agent.prospective_bounded_policy_endpoint_runner import (
    BoundedPolicyEndpointRecord,
    make_bounded_policy_endpoint_record,
)
from trusted_synthesis.runtime.agent.prospective_qualified_final_response_grammar import (
    QualifiedFinalResponseGrammar,
    compile_qualified_final_response_grammar,
)

RUN_ID: Final = "finance_v26_163_bounded_policy_endpoint_frequency_preflight_v1_20260827"
OUTPUT_DIR: Final = (
    "artifacts/vtdo_experiment/"
    "finance_v26_163_bounded_policy_endpoint_frequency_preflight_v1_20260827"
)
NEXT_STAGE: Final = "fresh_bounded_policy_endpoint_frequency_execution_only"
PROSPECTIVE_RUNNER_RUN_ID: Final = (
    "finance_v26_163_bounded_policy_endpoint_frequency_runner_v1_20260827"
)
PROSPECTIVE_EXECUTION_RUN_ID: Final = (
    "finance_v26_164_bounded_policy_endpoint_frequency_execution_v1_20260827"
)
PROSPECTIVE_REPORT_RUN_ID: Final = (
    "finance_v26_164_bounded_policy_endpoint_frequency_execution_report_v1_20260827"
)
SOURCE_FRAME_RUN_ID: Final = "finance_v26_163_bounded_policy_source_frame_v1_20260827"
SOURCE_SAMPLING_SALT: Final = "finance-v26.163-bounded-policy-source-sampling-v1"
SOURCE_SELECTION_SALT: Final = "finance-v26.163-bounded-policy-source-selection-v1"
SEED_SALT: Final = "finance-v26.163-bounded-policy-frequency-seed-v1"
EXPECTED_PREDECESSOR_REPORT_ID: Final = (
    "finance_v26_mapper_v2_frequency_postrun_audit_report:"
    "a536a3a85e2011587d880ac527b4e6a6ca1bec494bbfbe28b7421be8113fdc5e"
)
EXPECTED_PREDECESSOR_REPORT_SHA256: Final = (
    "0603bb3c0cf84bab38cec287cba59de47f60d0f6bf8cbe787adec1697bbb9b62"
)
EXPECTED_ROUTE_B_DECISION_ID: Final = (
    "finance_v26_route_b_bounded_policy_decision:"
    "6a7fb04af06ee74c95de0bce29e6d3bd8506c180ac4a5c928e6e37e6ca775704"
)
CANONICAL_PACKAGE_ROOT: Final = Path(
    "/home/zhuxinrui/datatmp/projects/Data-Synthesis/trusted_data_synthesis"
)
RECOVERED_ARTIFACT_ROOT: Final = Path(
    "/data1/zhuxinrui/projects/Data-Synthesis/trusted_data_synthesis"
)
RECOVERED_SOURCE_SNAPSHOT_PATH: Final = RECOVERED_ARTIFACT_ROOT / source_base.SNAPSHOT_PATH
EXPECTED_SOURCE_SNAPSHOT_SHA256: Final = (
    "c6ac2b985607a0f964cb919010bd9a7c9eee9ac57534983e4ab09a7b10c3f17e"
)
EXPECTED_SOURCE_SNAPSHOT_BYTE_COUNT: Final = 604_998_387
TASK_COUNT: Final = 12
PATH_COUNT: Final = 36
CELL_COUNT: Final = 48
JOB_COUNT: Final = 360
UNCONDITIONAL_REPLICAS: Final = 12
CONDITIONED_REPLICAS: Final = 6
IMPLEMENTATION_PATHS: Final = (
    "src/trusted_synthesis/core/evaluation/bounded_policy_endpoint.py",
    "src/trusted_synthesis/runtime/agent/prospective_bounded_policy_endpoint_runner.py",
    "src/trusted_synthesis/experiments/vtdo_experiment/"
    "phase1_v26_bounded_policy_endpoint_frequency_preflight_models.py",
    "src/trusted_synthesis/experiments/vtdo_experiment/"
    "phase1_v26_bounded_policy_endpoint_frequency_preflight.py",
    "src/trusted_synthesis/experiments/vtdo_experiment/"
    "phase1_v26_mapper_v2_frequency_preflight_inputs.py",
    "src/trusted_synthesis/experiments/vtdo_experiment/phase1_v26_mapper_v2_frequency_identity.py",
    "src/trusted_synthesis/experiments/vtdo_experiment/phase1_v26_mapper_v2_frequency_fixtures.py",
    "src/trusted_synthesis/experiments/vtdo_experiment/phase1_v26_mapper_v2_frequency_static.py",
    "src/trusted_synthesis/runtime/agent/prospective_reachability_runner_vnext.py",
)


def _resolve_package_root(root: Path) -> Path:
    if (root / "src" / "trusted_synthesis").is_dir():
        return root
    candidate = root / "trusted_data_synthesis"
    if (candidate / "src" / "trusted_synthesis").is_dir():
        return candidate
    raise ValueError("v26.163 cannot resolve package root")


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _json_payload(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, Mapping):
        return {str(key): _json_payload(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_payload(item) for item in value]
    return value


def _canonical_bytes(value: Any) -> bytes:
    return (
        json.dumps(
            _json_payload(value),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
        + b"\n"
    )


def _write_json_atomic(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = _canonical_bytes(value)
    if path.exists() and path.read_bytes() == payload:
        return
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(payload)
    temporary.replace(path)


def _model(model_type: type[BaseModel], values: dict[str, Any], *, field: str, prefix: str) -> Any:
    provisional = model_type.model_construct(**{field: "pending"}, **values)
    return model_type(**{field: identity(provisional, field, prefix)}, **values)


def _detail(path: Path, output_dir: Path) -> DetailFile:
    return DetailFile(
        relative_path=str(path.relative_to(output_dir)),
        sha256=_sha256(path),
        byte_count=path.stat().st_size,
    )


def _bind_file(
    bindings: dict[str, FileBinding],
    *,
    package_root: Path,
    relative_path: str,
    source_kind: str,
) -> None:
    path = package_root / relative_path
    if not path.is_file():
        raise ValueError(f"v26.163 bound input unavailable: {relative_path}")
    bindings[relative_path] = FileBinding(
        relative_path=relative_path,
        sha256=_sha256(path),
        byte_count=path.stat().st_size,
        source_kind=source_kind,
    )


def _predecessor_replay(package_root: Path, artifact_root: Path) -> PredecessorReplayAudit:
    direct_dir = package_root / predecessor.OUTPUT_DIR
    report_path = direct_dir / "report.json"
    report = predecessor.PostrunAuditReport.model_validate(_load(report_path))
    route_b = predecessor.RouteBDecisionContract.model_validate(
        _load(direct_dir / "route_b_decision_contract.json")
    )
    if (
        report.report_id != EXPECTED_PREDECESSOR_REPORT_ID
        or _sha256(report_path) != EXPECTED_PREDECESSOR_REPORT_SHA256
        or route_b.contract_id != EXPECTED_ROUTE_B_DECISION_ID
        or report.route_b_decision_contract_id != route_b.contract_id
        or route_b.next_permitted_stage != "fresh_bounded_policy_endpoint_frequency_preflight_only"
        or route_b.provider_execution_authorized
    ):
        raise ValueError("v26.163 predecessor Route B authorization changed")
    direct_files = tuple(sorted(path for path in direct_dir.iterdir() if path.is_file()))
    with tempfile.TemporaryDirectory(prefix="v26_163_predecessor_") as temporary:
        rebuilt_dir = Path(temporary)
        predecessor.build_postrun_audit(
            execution_dir=artifact_root / predecessor.EXECUTION_DIR,
            output_dir=rebuilt_dir,
            package_root=artifact_root,
            implementation_root=package_root,
        )
        rebuilt_files = tuple(sorted(path for path in rebuilt_dir.iterdir() if path.is_file()))
        if tuple(path.name for path in direct_files) != tuple(path.name for path in rebuilt_files):
            raise ValueError("v26.163 predecessor direct output set changed")
        byte_matches = sum(
            path.read_bytes() == (rebuilt_dir / path.name).read_bytes() for path in direct_files
        )
    if len(direct_files) != 9 or byte_matches != 9:
        raise ValueError("v26.163 predecessor byte replay failed")
    bindings: dict[str, FileBinding] = {}
    for path in direct_files:
        _bind_file(
            bindings,
            package_root=package_root,
            relative_path=str(path.relative_to(package_root)),
            source_kind="v26_162_direct_output",
        )
    source_paths = (
        f"{source_base.OUTPUT_DIR}/source_replay_audit.json",
        f"{source_base.OUTPUT_DIR}/fresh_source_sampling_frame.json",
        f"{source_base.OUTPUT_DIR}/capability_source_population.json",
        f"{source_base.OUTPUT_DIR}/reachability_source_population.json",
        f"{capability.OUTPUT_DIR}/fresh_source_sampling_frame.json",
        f"{capability.OUTPUT_DIR}/fresh_capability_source_population.json",
        f"{capability.OUTPUT_DIR}/source_selection_audit.json",
        f"{old_preflight.OUTPUT_DIR}/fresh_reachability_source_population.json",
    )
    for relative in source_paths:
        _bind_file(
            bindings,
            package_root=package_root,
            relative_path=relative,
            source_kind="source_population_input",
        )
    for relative in IMPLEMENTATION_PATHS:
        _bind_file(
            bindings,
            package_root=package_root,
            relative_path=relative,
            source_kind="implementation",
        )
    recovered_path = RECOVERED_SOURCE_SNAPSHOT_PATH
    if (
        not recovered_path.is_file()
        or recovered_path.stat().st_size != EXPECTED_SOURCE_SNAPSHOT_BYTE_COUNT
        or _sha256(recovered_path) != EXPECTED_SOURCE_SNAPSHOT_SHA256
    ):
        raise ValueError("v26.163 external source snapshot recovery identity changed")
    bindings[str(recovered_path)] = FileBinding(
        relative_path=str(recovered_path),
        sha256=EXPECTED_SOURCE_SNAPSHOT_SHA256,
        byte_count=EXPECTED_SOURCE_SNAPSHOT_BYTE_COUNT,
        source_kind="external_content_matched_source_snapshot",
    )
    values = {
        "predecessor_report_id": report.report_id,
        "predecessor_report_sha256": _sha256(report_path),
        "predecessor_route_b_decision_id": route_b.contract_id,
        "external_recovered_snapshot_path": str(recovered_path),
        "external_recovered_snapshot_sha256": EXPECTED_SOURCE_SNAPSHOT_SHA256,
        "file_bindings": tuple(bindings[key] for key in sorted(bindings)),
        "current_stage_input_file_count": len(bindings),
    }
    return cast(
        PredecessorReplayAudit,
        _model(
            PredecessorReplayAudit,
            values,
            field="audit_id",
            prefix="finance_v26_bounded_policy_predecessor_replay:",
        ),
    )


def _source_rank(task: CapabilitySensitiveTaskArtifact, mechanism: str, tier: str) -> str:
    return strict_canonical_hash(
        {
            "salt": SOURCE_SELECTION_SALT,
            "mechanism": mechanism,
            "tier": tier,
            "source_task_artifact_id": task.artifact_id,
        },
        prefix="finance_v26_bounded_policy_source_rank:",
    )


def _source_binding(
    task: CapabilitySensitiveTaskArtifact,
    *,
    mechanism: str,
    tier: str,
) -> FreshFrequencySourceBinding:
    channels = source_base._source_task_channels((task,))  # noqa: SLF001
    values = {
        "mechanism_id": mechanism,
        "tier": tier,
        "source_task": task,
        "source_task_artifact_id": task.artifact_id,
        "task_id": task.task.task_id,
        "core_semantic_signature": next(iter(channels["core_semantic_signature"])),
        "task_signature": task.task.task_hash,
        "mechanism_instance_signature": next(iter(channels["mechanism_instance_signature"])),
        "evidence_ids": tuple(sorted(channels["evidence_id"])),
        "evidence_version_ids": tuple(sorted(channels["evidence_version_id"])),
        "source_record_ids": tuple(sorted(channels["source_record_id"])),
        "source_rank": _source_rank(task, mechanism, tier),
    }
    return cast(
        FreshFrequencySourceBinding,
        _model(
            FreshFrequencySourceBinding,
            values,
            field="binding_id",
            prefix="finance_v26_frequency_source_binding:",
        ),
    )


def _freeze_source_population(
    *,
    package_root: Path,
    output_dir: Path,
    predecessor_replay: PredecessorReplayAudit,
) -> tuple[
    CapabilitySensitiveFrontierPopulation,
    FreshFrequencySourcePopulation,
    RouteBSourceSelectionAudit,
]:
    old_dir = package_root / source_base.OUTPUT_DIR
    old_source = source_base.SourceReplayAudit.model_validate(
        _load(old_dir / "source_replay_audit.json")
    )
    historical = source_base._build_historical_inputs(  # noqa: SLF001
        source=old_source,
        package_root=RECOVERED_ARTIFACT_ROOT,
        implementation_root=package_root,
    )
    if len(historical.effective_excluded_evidence_ids) != 27_173:
        raise ValueError("v26.163 historical Evidence exclusion denominator changed")
    old_frame = CapabilitySensitiveFrontierPopulation.model_validate(
        _load(old_dir / "fresh_source_sampling_frame.json")
    )
    old_by_id = {item.artifact_id: item for item in old_frame.tasks}
    prior_tasks: list[CapabilitySensitiveTaskArtifact] = []
    for name in ("capability_source_population.json", "reachability_source_population.json"):
        population = source_base.FreshRoleSourcePopulation.model_validate(_load(old_dir / name))
        prior_tasks.extend(old_by_id[item.source_task_artifact_id] for item in population.tasks)

    capability_dir = package_root / capability.OUTPUT_DIR
    prior_capability = capability.FreshCapabilitySourcePopulation.model_validate(
        _load(capability_dir / "fresh_capability_source_population.json")
    )
    prior_tasks.extend(item.source_task for item in prior_capability.tasks)
    prior_frequency = FreshFrequencySourcePopulation.model_validate(
        _load(package_root / old_preflight.OUTPUT_DIR / "fresh_reachability_source_population.json")
    )
    prior_tasks.extend(item.source_task for item in prior_frequency.tasks)
    distinct_prior = {item.artifact_id: item for item in prior_tasks}
    if len(distinct_prior) != 48:
        raise ValueError("v26.163 four-Population exclusion registry changed")

    prior_task_channels = source_base._source_task_channels(  # noqa: SLF001
        tuple(distinct_prior.values())
    )
    excluded = {
        channel: set(historical.prior_channels[channel])
        for channel in source_base.FRESHNESS_CHANNELS
    }
    for channel in source_base.FRESHNESS_CHANNELS:
        if excluded[channel] & prior_task_channels[channel]:
            raise ValueError("v26.163 prior Population overlaps historical exclusion")
        excluded[channel].update(prior_task_channels[channel])
    prior_population_evidence_count = len(prior_task_channels["evidence_id"])
    effective_excluded_evidence_count = len(excluded["evidence_id"])
    if effective_excluded_evidence_count != 27_173 + prior_population_evidence_count:
        raise ValueError("v26.163 effective Evidence exclusion union changed")

    frame = capability.build_capability_sensitive_frontier_population(
        source_artifacts_path=RECOVERED_SOURCE_SNAPSHOT_PATH,
        output_path=output_dir / "fresh_source_sampling_frame.json",
        run_id=SOURCE_FRAME_RUN_ID,
        sampling_salt=SOURCE_SAMPLING_SALT,
        excluded_evidence_ids=tuple(sorted(excluded["evidence_id"])),
    )
    frame_ids = {item.artifact_id for item in frame.tasks}
    overlap_with_frame = len(frame_ids & set(distinct_prior))
    eligible: list[CapabilitySensitiveTaskArtifact] = []
    for task in frame.tasks:
        channels = source_base._source_task_channels((task,))  # noqa: SLF001
        if all(
            not (channels[channel] & excluded[channel])
            for channel in source_base.FRESHNESS_CHANNELS
        ):
            eligible.append(task)
    if len(frame.tasks) != 70:
        raise ValueError("v26.163 fresh source Sampling Frame denominator changed")

    bindings: list[FreshFrequencySourceBinding] = []
    selected: list[CapabilitySensitiveTaskArtifact] = []
    for mechanism in source_base.TARGET_MECHANISMS:
        family = source_base.ROLE_MECHANISM_SOURCE_FAMILY[mechanism]
        for tier in source_base.TIERS:
            candidates = sorted(
                (item for item in eligible if item.family == family and item.tier.value == tier),
                key=lambda item: _source_rank(item, mechanism, tier),
            )
            if not candidates:
                raise ValueError(f"v26.163 recovered source frame lacks {mechanism}|{tier}")
            selected.append(candidates[0])
            bindings.append(_source_binding(candidates[0], mechanism=mechanism, tier=tier))
    population_values = {
        "source_frame_population_id": frame.population_id,
        "source_selection_salt": SOURCE_SELECTION_SALT,
        "tasks": tuple(sorted(bindings, key=lambda item: item.binding_id)),
    }
    population = cast(
        FreshFrequencySourcePopulation,
        _model(
            FreshFrequencySourcePopulation,
            population_values,
            field="population_id",
            prefix="finance_v26_frequency_source_population:",
        ),
    )
    selected_channels = source_base._source_task_channels(tuple(selected))  # noqa: SLF001
    channel_rows = tuple(
        FreshnessChannelRow(
            channel=channel,
            excluded_count=len(excluded[channel]),
            selected_count=len(selected_channels[channel]),
            overlap_count=cast(Literal[0], len(excluded[channel] & selected_channels[channel])),
        )
        for channel in sorted(source_base.FRESHNESS_CHANNELS)
    )
    if any(item.overlap_count for item in channel_rows):
        raise ValueError("v26.163 fresh Population overlaps historical or prior sources")
    selection_values = {
        "predecessor_replay_audit_id": predecessor_replay.audit_id,
        "source_frame_population_id": frame.population_id,
        "source_population_id": population.population_id,
        "source_selection_salt": SOURCE_SELECTION_SALT,
        "exclusion_overlap_with_frame": overlap_with_frame,
        "frame_candidate_count_before_exclusion": len(frame.tasks),
        "frame_candidate_count_after_exclusion": len(eligible),
        "prior_population_evidence_count": prior_population_evidence_count,
        "effective_excluded_evidence_count": effective_excluded_evidence_count,
        "freshness_channels": channel_rows,
    }
    selection = cast(
        RouteBSourceSelectionAudit,
        _model(
            RouteBSourceSelectionAudit,
            selection_values,
            field="audit_id",
            prefix="finance_v26_bounded_policy_source_selection:",
        ),
    )
    _write_json_atomic(output_dir / "fresh_reachability_source_population.json", population)
    _write_json_atomic(output_dir / "source_selection_audit.json", selection)
    return frame, population, selection


def _make_generation_policy(
    *,
    resource: Any,
    tasks: Any,
) -> BoundedPolicyEndpointGenerationPolicy:
    support_ids = {item.measurement_support_contract_id for item in tasks.packages}
    if len(support_ids) != 1:
        raise ValueError("v26.163 TaskPackages crossed Measurement Support Contracts")
    values = {
        "resource_contract_id": resource.contract_id,
        "measurement_support_contract_id": next(iter(support_ids)),
    }
    provisional = BoundedPolicyEndpointGenerationPolicy.model_construct(
        policy_id="pending",
        **values,
    )
    return BoundedPolicyEndpointGenerationPolicy(
        policy_id=strict_canonical_hash(
            provisional.model_dump(mode="python", exclude={"policy_id"}),
            prefix="bounded_policy_endpoint_generation_policy:",
        ),
        **values,
    )


def _make_estimand(
    *,
    cells: Any,
    policy: BoundedPolicyEndpointGenerationPolicy,
    assignment: Any,
) -> BoundedPolicyEstimandContract:
    values = {
        "task_condition_cell_catalog_id": cells.catalog_id,
        "generation_policy_id": policy.policy_id,
        "frequency_assignment_contract_id": assignment.contract_id,
    }
    return cast(
        BoundedPolicyEstimandContract,
        _model(
            BoundedPolicyEstimandContract,
            values,
            field="contract_id",
            prefix="finance_v26_bounded_policy_estimand_contract:",
        ),
    )


def _historical_seed_and_job_ids(package_root: Path) -> tuple[set[int], set[str]]:
    manifests: tuple[Any, ...] = (
        capability.CapabilityManifest.model_validate(
            _load(package_root / capability.OUTPUT_DIR / "capability_manifest.json")
        ),
        reachability.ReachabilityManifest.model_validate(
            _load(package_root / reachability.OUTPUT_DIR / "reachability_manifest.json")
        ),
        FrequencyManifest.model_validate(
            _load(package_root / old_preflight.OUTPUT_DIR / "frequency_manifest.json")
        ),
    )
    seeds = {item.seed for manifest in manifests for item in manifest.jobs}
    jobs = {item.job_id for manifest in manifests for item in manifest.jobs}
    return seeds, jobs


def _fresh_seed(payload: Mapping[str, Any], used: set[int], historical: set[int]) -> int:
    nonce = 0
    while True:
        digest = strict_canonical_hash(
            {"salt": SEED_SALT, "payload": dict(payload), "nonce": nonce},
            prefix="finance_v26_bounded_policy_seed:",
        )
        seed = int(digest.rsplit(":", 1)[-1][:16], 16)
        if seed not in used and seed not in historical:
            used.add(seed)
            return seed
        nonce += 1


def _make_manifest(
    *,
    package_root: Path,
    contract: FrequencyExecutionContract,
    population: FreshFrequencySourcePopulation,
    selection: RouteBSourceSelectionAudit,
    tasks: Any,
    paths: Any,
    resource: Any,
    protocol: Any,
    cells: Any,
    policy: BoundedPolicyEndpointGenerationPolicy,
) -> FrequencyManifest:
    historical_seeds, historical_jobs = _historical_seed_and_job_ids(package_root)
    cell_by_key = {
        (item.task_package_id, item.experimental_condition.requested_path_id): item
        for item in cells.cells
    }
    paths_by_task: dict[str, list[Any]] = defaultdict(list)
    for path in paths.paths:
        paths_by_task[path.task_package_id].append(path)
    jobs: list[FrequencyJob] = []
    used_seeds: set[int] = set()
    for package in tasks.packages:
        cell = cell_by_key[(package.task_package_id, None)]
        for replicate in range(UNCONDITIONAL_REPLICAS):
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
                identity_builders._job(  # noqa: SLF001
                    contract=contract,
                    resource=resource,
                    protocol=protocol,
                    package=package,
                    cell=cell,
                    selection_id=selection.audit_id,
                    replicate=replicate,
                    seed=seed,
                    generation_policy=cast(Any, policy),
                    path=None,
                )
            )
        for path in sorted(paths_by_task[package.task_package_id], key=lambda item: item.path_id):
            cell = cell_by_key[(package.task_package_id, path.path_id)]
            for replicate in range(CONDITIONED_REPLICAS):
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
                    identity_builders._job(  # noqa: SLF001
                        contract=contract,
                        resource=resource,
                        protocol=protocol,
                        package=package,
                        cell=cell,
                        selection_id=selection.audit_id,
                        replicate=replicate,
                        seed=seed,
                        generation_policy=cast(Any, policy),
                        path=path,
                    )
                )
    ordered = tuple(sorted(jobs, key=lambda item: item.job_id))
    if historical_jobs & {item.job_id for item in ordered}:
        raise ValueError("v26.163 Job identity overlaps history")
    values = {
        "execution_contract_id": contract.contract_id,
        "source_population_id": population.population_id,
        "source_selection_audit_id": selection.audit_id,
        "resource_contract_id": resource.contract_id,
        "mapper_protocol_id": protocol.protocol_id,
        "task_condition_cell_catalog_id": cells.catalog_id,
        "prospective_runner_run_id": PROSPECTIVE_RUNNER_RUN_ID,
        "prospective_execution_run_id": PROSPECTIVE_EXECUTION_RUN_ID,
        "prospective_report_run_id": PROSPECTIVE_REPORT_RUN_ID,
        "jobs": ordered,
    }
    return cast(
        FrequencyManifest,
        _model(
            FrequencyManifest,
            values,
            field="manifest_id",
            prefix="finance_v26_frequency_manifest:",
        ),
    )


def _make_outcome(
    *,
    execution: FrequencyExecutionContract,
    manifest: FrequencyManifest,
    policy: BoundedPolicyEndpointGenerationPolicy,
    estimand: BoundedPolicyEstimandContract,
    assignment: Any,
) -> BoundedPolicyOutcomeContract:
    values = {
        "execution_contract_id": execution.contract_id,
        "manifest_id": manifest.manifest_id,
        "generation_policy_id": policy.policy_id,
        "estimand_contract_id": estimand.contract_id,
        "assignment_contract_id": assignment.contract_id,
    }
    return cast(
        BoundedPolicyOutcomeContract,
        _model(
            BoundedPolicyOutcomeContract,
            values,
            field="contract_id",
            prefix="finance_v26_bounded_policy_outcome_contract:",
        ),
    )


def _make_runner(
    *,
    package_root: Path,
    execution: FrequencyExecutionContract,
    manifest: FrequencyManifest,
    outcome: BoundedPolicyOutcomeContract,
    estimand: BoundedPolicyEstimandContract,
    policy: BoundedPolicyEndpointGenerationPolicy,
    resource: Any,
    protocol: Any,
    assignment: Any,
    cells: Any,
    tool_closure: Any,
    reference_implementation_id: str,
    grammar: QualifiedFinalResponseGrammar,
    joint: Any,
) -> BoundedPolicyRunnerContract:
    adapter_path = (
        package_root
        / "src/trusted_synthesis/runtime/agent/prospective_bounded_policy_endpoint_runner.py"
    )
    adapter_id = strict_canonical_hash(
        {
            "relative_path": str(adapter_path.relative_to(package_root)),
            "sha256": _sha256(adapter_path),
        },
        prefix="finance_v26_bounded_policy_endpoint_adapter:",
    )
    values = {
        "execution_contract_id": execution.contract_id,
        "manifest_id": manifest.manifest_id,
        "outcome_contract_id": outcome.contract_id,
        "estimand_contract_id": estimand.contract_id,
        "generation_policy_id": policy.policy_id,
        "endpoint_adapter_implementation_id": adapter_id,
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
        "runner_run_id": PROSPECTIVE_RUNNER_RUN_ID,
        "execution_run_id": PROSPECTIVE_EXECUTION_RUN_ID,
    }
    return cast(
        BoundedPolicyRunnerContract,
        _model(
            BoundedPolicyRunnerContract,
            values,
            field="contract_id",
            prefix="finance_v26_bounded_policy_runner_contract:",
        ),
    )


def _endpoint_fixture(
    *,
    tasks: Any,
    registered: Sequence[Any],
    manifest: FrequencyManifest,
    resource: Any,
    runner: BoundedPolicyRunnerContract,
    policy: BoundedPolicyEndpointGenerationPolicy,
    grammar: QualifiedFinalResponseGrammar,
    static: Any,
    support: Any,
) -> tuple[
    BoundedPolicyEndpointFixtureAudit,
    tuple[BoundedPolicyEndpointRecord, BoundedPolicyEndpointRecord],
]:
    detour_row = min(
        (item for item in support.event_rows if item.decision.ordinary_detour_observed),
        key=lambda item: item.row_id,
    )
    task_by_id = {item.task_package_id: item for item in tasks.packages}
    path_by_id = {cast(Any, item.path).path_id: item for item in registered}
    job = next(item for item in manifest.jobs if item.requested_path_id == detour_row.path_id)
    package = task_by_id[job.task_package_id]
    execution = path_by_id[cast(str, job.requested_path_id)]
    binding = reachability._runtime_binding(  # noqa: SLF001
        package,
        package.frozen_input_audit_id,
        path_strategy_id=execution.path_strategy_id,
        public_path_condition=execution.public_path_condition,
    )
    final_answer = reachability._reference_final_answer(  # noqa: SLF001
        execution,
        old_grammar=static.final_grammar,
    )
    raws: list[Any] = []
    with tempfile.TemporaryDirectory(prefix="v26_163_endpoint_fixture_") as temporary:
        root = Path(temporary)
        for name, uses in (("one_detour", 1), ("two_detours", 2)):
            client = s1_runner.ScriptedS1QualificationClient(
                static.agent_model_config,
                final_answer=final_answer,
                force_action_id=detour_row.selected_action_id,
                force_action_uses=uses,
            )
            raw = runner_vnext.execute_fresh_reachability_job_raw(
                job=job,
                runner_contract=runner,
                resource_contract=resource,
                static=static,
                qualified_grammar=grammar,
                binding=binding,
                client=client,
                output_dir=root / name,
            )
            raws.append(raw)
    one_raw, two_raw = raws
    if (
        one_raw.terminal_disposition != "completed_model_endpoint"
        or one_raw.ordinary_detour_count != 1
        or two_raw.terminal_disposition != "measurement_support_exit"
        or two_raw.terminal_failure_type != "ordinary_detour_allowance_exhausted"
        or two_raw.ordinary_detour_count != 2
        or two_raw.later_provider_calls_after_support_exit
    ):
        raise ValueError("v26.163 exact one/two Detour Runtime fixture changed")
    one_record = make_bounded_policy_endpoint_record(
        raw=one_raw,
        policy=policy,
        provider_identity_integrity=True,
        thinking_usage_integrity=True,
        privacy_artifact_integrity=True,
        transport_resolved=True,
        task_completion=True,
        base_validity=True,
        mechanism_qualification=True,
        qualified_validity=True,
        task_verifier_invocation_count=1,
    )
    two_record = make_bounded_policy_endpoint_record(
        raw=two_raw,
        policy=policy,
        provider_identity_integrity=True,
        thinking_usage_integrity=True,
        privacy_artifact_integrity=True,
        transport_resolved=True,
        task_completion=None,
        base_validity=None,
        mechanism_qualification=None,
        qualified_validity=None,
        task_verifier_invocation_count=0,
    )
    horizon = two_record.projection
    gate = make_bounded_policy_global_integrity_gate(
        exact_job_denominator=2,
        complete_raw_count=2,
        bounded_policy_endpoint_count=2,
    )
    if (
        not gate.passed
        or one_record.projection.qualified_validity is not True
        or horizon.terminal_class != "policy_horizon_exhausted"
        or horizon.policy_horizon_reason != "ordinary_detour_limit"
        or not horizon.raw_instrument_integrity
        or not horizon.measurement_support_available
        or not horizon.resource_accounting_integrity
        or not horizon.bounded_policy_endpoint_observed
        or horizon.task_completion is not False
        or horizon.base_validity is not False
        or horizon.qualified_validity is not False
        or horizon.state_mapping_eligible
        or horizon.task_verifier_invocation_count
    ):
        raise ValueError("v26.163 second Detour did not become a complete Policy endpoint")
    values = {
        "generation_policy_id": policy.policy_id,
        "runner_contract_id": runner.contract_id,
    }
    audit = cast(
        BoundedPolicyEndpointFixtureAudit,
        _model(
            BoundedPolicyEndpointFixtureAudit,
            values,
            field="audit_id",
            prefix="finance_v26_bounded_policy_endpoint_fixture:",
        ),
    )
    return audit, (one_record, two_record)


def _frequency_api_fixture(
    policy: BoundedPolicyEndpointGenerationPolicy,
) -> tuple[
    BoundedPolicyFrequencyApiFixtureAudit,
    tuple[BoundedPolicyCellFrequencyReport, ...],
]:
    passing = make_bounded_policy_global_integrity_gate(
        exact_job_denominator=30,
        complete_raw_count=30,
        bounded_policy_endpoint_count=30,
    )
    failed = make_bounded_policy_global_integrity_gate(
        exact_job_denominator=1,
        complete_raw_count=1,
        bounded_policy_endpoint_count=0,
    )
    zero = summarize_bounded_policy_cell(
        task_condition_cell_id="fixture-zero-qualified-cell",
        generation_policy_id=policy.policy_id,
        global_gate=passing,
        expected_n_total=12,
        observed_n_total=12,
        endpoint_count=12,
        qualified_state_ids=(),
    )
    single = summarize_bounded_policy_cell(
        task_condition_cell_id="fixture-single-qualified-cell",
        generation_policy_id=policy.policy_id,
        global_gate=passing,
        expected_n_total=6,
        observed_n_total=6,
        endpoint_count=6,
        qualified_state_ids=("state-a",),
    )
    multi = summarize_bounded_policy_cell(
        task_condition_cell_id="fixture-multi-state-cell",
        generation_policy_id=policy.policy_id,
        global_gate=passing,
        expected_n_total=6,
        observed_n_total=6,
        endpoint_count=6,
        qualified_state_ids=("state-a", "state-a", "state-b"),
    )
    incomplete = summarize_bounded_policy_cell(
        task_condition_cell_id="fixture-incomplete-cell",
        generation_policy_id=policy.policy_id,
        global_gate=passing,
        expected_n_total=6,
        observed_n_total=6,
        endpoint_count=5,
        qualified_state_ids=("state-a",),
    )
    global_null = summarize_bounded_policy_cell(
        task_condition_cell_id="fixture-global-failed-cell",
        generation_policy_id=policy.policy_id,
        global_gate=failed,
        expected_n_total=6,
        observed_n_total=6,
        endpoint_count=6,
        qualified_state_ids=(),
    )
    if (
        zero.q_hat != "0"
        or zero.q_wilson_interval is None
        or zero.pi_instantiated
        or zero.pi_null_reason != "no_qualified_rows"
        or not single.pi_instantiated
        or single.empirical_non_degenerate is not False
        or single.stable_population_probability_claimed
        or not multi.pi_instantiated
        or multi.empirical_non_degenerate is not True
        or len(multi.state_frequencies) != 2
        or incomplete.pi_null_reason != "cell_endpoint_gate_failed"
        or global_null.pi_null_reason != "global_integrity_gate_failed"
    ):
        raise ValueError("v26.163 Route B Frequency API fixture changed")
    values = {"generation_policy_id": policy.policy_id}
    audit = cast(
        BoundedPolicyFrequencyApiFixtureAudit,
        _model(
            BoundedPolicyFrequencyApiFixtureAudit,
            values,
            field="audit_id",
            prefix="finance_v26_bounded_policy_frequency_api_fixture:",
        ),
    )
    return audit, (zero, single, multi, incomplete, global_null)


def _transition(
    *,
    execution: FrequencyExecutionContract,
    manifest: FrequencyManifest,
    outcome: BoundedPolicyOutcomeContract,
    runner: BoundedPolicyRunnerContract,
    policy: BoundedPolicyEndpointGenerationPolicy,
) -> ProspectiveTransitionContract:
    values = {
        "execution_contract_id": execution.contract_id,
        "manifest_id": manifest.manifest_id,
        "outcome_contract_id": outcome.contract_id,
        "runner_contract_id": runner.contract_id,
        "generation_policy_id": policy.policy_id,
    }
    return cast(
        ProspectiveTransitionContract,
        _model(
            ProspectiveTransitionContract,
            values,
            field="contract_id",
            prefix="finance_v26_bounded_policy_transition:",
        ),
    )


def _reject(rows: list[MutationResult], name: str, callback: Callable[[], Any]) -> None:
    try:
        callback()
    except (AssertionError, KeyError, TypeError, ValueError, ValidationError) as exc:
        rows.append(MutationResult(mutation_name=name, failure_type=type(exc).__name__))
        return
    raise AssertionError(f"v26.163 destructive mutation did not fail: {name}")


def _destructive(
    *,
    products: Mapping[str, Any],
) -> DestructiveAudit:
    selection = products["selection"]
    policy = products["policy"]
    cells = products["cells"]
    estimand = products["estimand"]
    manifest = products["manifest"]
    outcome = products["outcome"]
    runner = products["runner"]
    transition = products["transition"]
    endpoint_records = products["endpoint_records"]
    api_reports = products["api_reports"]
    mapper_fixture = products["mapper_fixture"]
    semantic_policy: EmpiricalStateSemanticPolicyV2 = products["semantic_policy"]
    rows: list[MutationResult] = []

    def changed(model: BaseModel, **updates: Any) -> Any:
        return type(model).model_validate({**model.model_dump(mode="python"), **updates})

    horizon: BoundedPolicyEndpointProjection = endpoint_records[1].projection
    _reject(
        rows, "policy_second_detour_admitted", lambda: changed(policy, maximum_ordinary_detours=2)
    )
    _reject(
        rows,
        "policy_horizon_recast_as_support_exit",
        lambda: changed(horizon, measurement_support_available=False, support_exit=True),
    )
    _reject(
        rows,
        "policy_horizon_recast_as_model_terminal",
        lambda: changed(horizon, model_terminal_observed=True),
    )
    _reject(rows, "policy_horizon_task_completed", lambda: changed(horizon, task_completion=True))
    _reject(rows, "policy_horizon_base_valid", lambda: changed(horizon, base_validity=True))
    _reject(rows, "policy_horizon_qualified", lambda: changed(horizon, qualified_validity=True))
    _reject(
        rows,
        "policy_horizon_state_mapped",
        lambda: changed(horizon, state_mapping_eligible=True),
    )
    _reject(
        rows,
        "source_selection_outcome_leak",
        lambda: changed(selection, model_outcomes_used_for_selection=True),
    )
    _reject(
        rows,
        "source_selection_compatibility_leak",
        lambda: changed(selection, compatibility_results_used_for_selection=True),
    )
    _reject(
        rows,
        "estimand_unrestricted_distribution_claim",
        lambda: changed(estimand, unrestricted_natural_agent_distribution_claimed=True),
    )
    _reject(
        rows,
        "estimand_route_condition_inserted",
        lambda: changed(estimand, empirical_route_signature_conditioning_allowed=True),
    )
    _reject(
        rows,
        "estimand_simultaneous_coverage_claim",
        lambda: changed(estimand, simultaneous_multinomial_coverage_claimed=True),
    )
    _reject(
        rows,
        "estimand_zero_state_imputation",
        lambda: changed(estimand, zero_vector_or_state_imputation_allowed=True),
    )
    _reject(
        rows,
        "outcome_horizon_support_exit",
        lambda: changed(outcome, policy_horizon_is_measurement_support_exit=True),
    )
    _reject(
        rows,
        "runner_mapper_before_qualified",
        lambda: changed(runner, mapper_runs_only_after_qualified_verifier=False),
    )
    _reject(
        rows,
        "runner_stage_two_provider_enabled",
        lambda: changed(runner, stage_two_provider_call_upper_bound=1),
    )
    _reject(
        rows,
        "runner_horizon_after_later_provider",
        lambda: changed(runner, policy_horizon_after_observation_before_next_provider=False),
    )
    _reject(
        rows,
        "manifest_job_deleted",
        lambda: changed(manifest, jobs=manifest.jobs[:-1]),
    )
    _reject(
        rows,
        "manifest_seed_duplicated",
        lambda: changed(
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
        "task_condition_route_inserted",
        lambda: TaskConditionCellV2.model_validate(
            {
                **cells.cells[0].model_dump(mode="python"),
                "empirical_route_signature_id": "forbidden-route",
            }
        ),
    )
    _reject(
        rows,
        "failed_global_gate_frequency_leak",
        lambda: changed(
            api_reports[-1],
            q_hat="0",
            q_wilson_interval=api_reports[0].q_wilson_interval,
        ),
    )
    _reject(
        rows,
        "zero_qualified_pi_imputed",
        lambda: changed(
            api_reports[0],
            pi_instantiated=True,
            pi_null_reason=None,
            state_frequencies=api_reports[1].state_frequencies,
        ),
    )
    _reject(
        rows,
        "same_state_contrast",
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
        "historical_reclassification_enabled",
        lambda: changed(
            transition,
            historical_rerun_pooling_or_reclassification_authorized=True,
        ),
    )
    _reject(
        rows,
        "vtdo_authorized_early",
        lambda: changed(
            transition,
            state_probability_vtdo_training_release_or_production_authorized=True,
        ),
    )
    ordered = tuple(sorted(rows, key=lambda item: item.mutation_name))
    values = {
        "mutations": ordered,
        "mutation_count": len(ordered),
        "rejected_count": len(ordered),
    }
    return cast(
        DestructiveAudit,
        _model(
            DestructiveAudit,
            values,
            field="audit_id",
            prefix="finance_v26_bounded_policy_destructive:",
        ),
    )


def build_bounded_policy_endpoint_frequency_preflight(
    *,
    implementation_root: Path,
    output_dir: Path,
    artifact_root: Path | None = None,
) -> BuildProducts:
    package_root = _resolve_package_root(implementation_root)
    immutable_root = (
        package_root
        if artifact_root is None
        and (package_root / predecessor.EXECUTION_DIR / "report.json").is_file()
        else (artifact_root or CANONICAL_PACKAGE_ROOT)
    )
    predecessor_replay = _predecessor_replay(package_root, immutable_root)
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_json_atomic(output_dir / "predecessor_replay_audit.json", predecessor_replay)
    frame, population, selection = _freeze_source_population(
        package_root=package_root,
        output_dir=output_dir,
        predecessor_replay=predecessor_replay,
    )
    print(
        "[v26.163] fresh Route B source Population frozen before Policy/Mapper/Path load: "
        f"{len(population.tasks)}/12",
        flush=True,
    )

    joint = old_inputs._load_joint_contract(package_root)
    grammar = compile_qualified_final_response_grammar()
    static = static_inputs.load_static_inputs(package_root)
    tasks = static_inputs.make_task_catalog(
        package_root=package_root,
        population=population,
        selection=cast(Any, selection),
        joint=joint,
        grammar=grammar,
    )
    paths, registered, unconditional = old_inputs._make_paths(
        tasks=tasks,
        selection=cast(Any, selection),
        static=static,
        grammar=grammar,
    )
    support, detours, resource = old_inputs._make_support_and_resource(
        package_root=package_root,
        paths=paths,
        registered=registered,
        selection=cast(Any, selection),
        static=static,
        grammar=grammar,
    )
    semantic_policy = identity_builders.load_semantic_policy(package_root)
    omega = identity_builders.make_omega_catalog(tasks=tasks, semantic_policy=semantic_policy)
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
    policy = _make_generation_policy(resource=resource, tasks=tasks)
    cells = identity_builders.make_cell_catalog(
        tasks=tasks,
        paths=paths,
        generation_policy=cast(Any, policy),
    )
    assignment = identity_builders.make_assignment_contract(
        mapper_contract=mapper_contract,
        semantic_policy=semantic_policy,
        cells=cells,
    )
    protocol = identity_builders.make_mapper_protocol(
        semantic_policy=semantic_policy,
        mapper_contract=mapper_contract,
        omega=omega,
        cells=cells,
        assignment_contract=assignment,
        tool_closure=tool_closure,
    )
    estimand = _make_estimand(cells=cells, policy=policy, assignment=assignment)
    execution = identity_builders.make_execution_contract(
        population=population,
        selection=selection,
        tasks=tasks,
        paths=paths,
        resource=resource,
        generation_policy=cast(Any, policy),
        protocol=protocol,
        cells=cells,
        estimand=cast(Any, estimand),
        assignment_contract=assignment,
        joint=joint,
    )
    manifest = _make_manifest(
        package_root=package_root,
        contract=execution,
        population=population,
        selection=selection,
        tasks=tasks,
        paths=paths,
        resource=resource,
        protocol=protocol,
        cells=cells,
        policy=policy,
    )
    outcome = _make_outcome(
        execution=execution,
        manifest=manifest,
        policy=policy,
        estimand=estimand,
        assignment=assignment,
    )
    runner = _make_runner(
        package_root=package_root,
        execution=execution,
        manifest=manifest,
        outcome=outcome,
        estimand=estimand,
        policy=policy,
        resource=resource,
        protocol=protocol,
        assignment=assignment,
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
        runner=cast(Any, runner),
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
        runner=cast(Any, runner),
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
    endpoint_fixture, endpoint_records = _endpoint_fixture(
        tasks=tasks,
        registered=registered,
        manifest=manifest,
        resource=resource,
        runner=runner,
        policy=policy,
        grammar=grammar,
        static=static,
        support=support,
    )
    frequency_api, api_reports = _frequency_api_fixture(policy)
    runner_preflight_values = {
        "runner_contract_id": runner.contract_id,
        "manifest_id": manifest.manifest_id,
        "generation_fixture_audit_id": generation_fixture.audit_id,
        "independent_mapper_preflight_audit_id": mapper_fixture.audit.audit_id,
        "bounded_policy_endpoint_fixture_audit_id": endpoint_fixture.audit_id,
        "bounded_policy_frequency_api_fixture_audit_id": frequency_api.audit_id,
        "temporal_gold_fixture_audit_id": temporal_gold.audit_id,
        "within_cell_contrast_audit_id": within_cell.audit_id,
    }
    runner_preflight = cast(
        RunnerPreflightAudit,
        _model(
            RunnerPreflightAudit,
            runner_preflight_values,
            field="audit_id",
            prefix="finance_v26_bounded_policy_runner_preflight:",
        ),
    )
    transition = _transition(
        execution=execution,
        manifest=manifest,
        outcome=outcome,
        runner=runner,
        policy=policy,
    )
    destructive = _destructive(
        products={
            "selection": selection,
            "policy": policy,
            "cells": cells,
            "estimand": estimand,
            "manifest": manifest,
            "outcome": outcome,
            "runner": runner,
            "transition": transition,
            "endpoint_records": endpoint_records,
            "api_reports": api_reports,
            "mapper_fixture": mapper_fixture,
            "semantic_policy": semantic_policy,
        }
    )
    prospective_execution_id = strict_canonical_hash(
        {
            "run_id": PROSPECTIVE_EXECUTION_RUN_ID,
            "manifest_id": manifest.manifest_id,
            "runner_contract_id": runner.contract_id,
            "outcome_contract_id": outcome.contract_id,
            "generation_policy_id": policy.policy_id,
        },
        prefix="finance_v26_bounded_policy_frequency_execution:",
    )
    prospective_report_id = strict_canonical_hash(
        {
            "run_id": PROSPECTIVE_REPORT_RUN_ID,
            "prospective_execution_id": prospective_execution_id,
            "outcome_contract_id": outcome.contract_id,
        },
        prefix="finance_v26_bounded_policy_frequency_execution_report:",
    )
    outputs: tuple[tuple[str, Any], ...] = (
        ("bounded_policy_endpoint_fixture_audit.json", endpoint_fixture),
        ("bounded_policy_frequency_api_fixture_audit.json", frequency_api),
        ("destructive_audit.json", destructive),
        ("detour_qualification_audit.json", detours),
        ("frequency_assignment_contract.json", assignment),
        ("frequency_estimand_contract.json", estimand),
        ("frequency_execution_contract.json", execution),
        ("frequency_manifest.json", manifest),
        ("frequency_outcome_contract.json", outcome),
        ("frequency_runner_contract.json", runner),
        ("frequency_runner_preflight_audit.json", runner_preflight),
        ("fresh_reachability_source_population.json", population),
        ("fresh_source_sampling_frame.json", frame),
        ("generation_policy.json", policy),
        ("independent_mapper_preflight_audit.json", mapper_fixture.audit),
        ("joint_support_validity_contract.json", joint),
        ("mapper_v2_contract.json", mapper_contract),
        ("mapper_v2_frequency_protocol.json", protocol),
        ("mapper_v2_semantic_policy.json", semantic_policy),
        ("mapper_v2_temporal_gold_fixture_audit.json", temporal_gold),
        ("omega_task_context_catalog.json", omega),
        ("predecessor_replay_audit.json", predecessor_replay),
        ("prospective_transition_contract.json", transition),
        ("qualified_final_response_grammar.json", grammar),
        ("reachability_path_catalog.json", paths),
        ("reachability_resource_contract.json", resource),
        ("reachability_runner_fixture_audit.json", generation_fixture),
        ("reachability_task_package_catalog.json", tasks),
        ("source_selection_audit.json", selection),
        ("support_closure_audit.json", support),
        ("task_condition_cell_catalog.json", cells),
        ("tool_schema_closure_audit.json", tool_closure),
        ("within_cell_state_contrast_audit.json", within_cell),
    )
    for name, value in outputs:
        _write_json_atomic(output_dir / name, value)
    details = tuple(
        sorted(
            (_detail(output_dir / name, output_dir) for name, _ in outputs),
            key=lambda item: item.relative_path,
        )
    )
    report_values = {
        "run_id": RUN_ID,
        "predecessor_replay_audit_id": predecessor_replay.audit_id,
        "source_population_id": population.population_id,
        "source_selection_audit_id": selection.audit_id,
        "task_package_catalog_id": tasks.catalog_id,
        "path_catalog_id": paths.catalog_id,
        "support_closure_audit_id": support.audit_id,
        "detour_qualification_audit_id": detours.audit_id,
        "resource_contract_id": resource.contract_id,
        "generation_policy_id": policy.policy_id,
        "semantic_policy_id": semantic_policy.policy_id,
        "mapper_contract_id": mapper_contract.contract_id,
        "omega_task_context_catalog_id": omega.catalog_id,
        "task_condition_cell_catalog_id": cells.catalog_id,
        "frequency_assignment_contract_id": assignment.contract_id,
        "mapper_protocol_id": protocol.protocol_id,
        "estimand_contract_id": estimand.contract_id,
        "tool_schema_closure_audit_id": tool_closure.audit_id,
        "execution_contract_id": execution.contract_id,
        "manifest_id": manifest.manifest_id,
        "outcome_contract_id": outcome.contract_id,
        "runner_contract_id": runner.contract_id,
        "endpoint_fixture_audit_id": endpoint_fixture.audit_id,
        "frequency_api_fixture_audit_id": frequency_api.audit_id,
        "independent_mapper_preflight_audit_id": mapper_fixture.audit.audit_id,
        "runner_preflight_audit_id": runner_preflight.audit_id,
        "destructive_audit_id": destructive.audit_id,
        "transition_contract_id": transition.contract_id,
        "prospective_execution_id": prospective_execution_id,
        "prospective_report_id": prospective_report_id,
        "detail_files": details,
    }
    report = cast(
        BoundedPolicyPreflightReport,
        _model(
            BoundedPolicyPreflightReport,
            report_values,
            field="report_id",
            prefix="finance_v26_bounded_policy_preflight_report:",
        ),
    )
    _write_json_atomic(output_dir / "report.json", report)
    return BuildProducts(
        predecessor_replay=predecessor_replay,
        source_population=population,
        source_selection=selection,
        generation_policy=policy,
        manifest=manifest,
        estimand_contract=estimand,
        outcome_contract=outcome,
        runner_contract=runner,
        endpoint_fixture=endpoint_fixture,
        frequency_api_fixture=frequency_api,
        runner_preflight=runner_preflight,
        destructive=destructive,
        transition=transition,
        report=report,
        internal={
            "tasks": tasks,
            "paths": paths,
            "support": support,
            "detours": detours,
            "resource": resource,
            "semantic_policy": semantic_policy,
            "mapper_contract": mapper_contract,
            "omega": omega,
            "cells": cells,
            "assignment": assignment,
            "protocol": protocol,
            "execution": execution,
            "tool_closure": tool_closure,
            "temporal_gold": temporal_gold,
            "generation_fixture": generation_fixture,
            "mapper_fixture": mapper_fixture.audit,
            "within_cell": within_cell,
        },
    )


def main() -> None:
    package_default = Path(__file__).resolve().parents[4]
    parser = argparse.ArgumentParser(
        description="Credential-free v26.163 Route B bounded-policy endpoint frequency preflight"
    )
    parser.add_argument("--implementation-root", type=Path, default=package_default)
    parser.add_argument("--artifact-root", type=Path, default=CANONICAL_PACKAGE_ROOT)
    parser.add_argument("--output-dir", type=Path, default=package_default / OUTPUT_DIR)
    args = parser.parse_args()
    products = build_bounded_policy_endpoint_frequency_preflight(
        implementation_root=args.implementation_root,
        output_dir=args.output_dir,
        artifact_root=args.artifact_root,
    )
    print(products.report.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
