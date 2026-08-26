from __future__ import annotations

import hashlib
import json
import tempfile
from collections.abc import Sequence
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Final, Literal, cast

from pydantic import BaseModel

from trusted_synthesis.canonical_json import strict_canonical_hash
from trusted_synthesis.core.evaluation.joint_support_validity import (
    JointSupportValidityContract,
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
    phase1_v26_fresh_role_kernel_compatibility_preflight as source_base,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_joint_support_verifier_preflight as joint_preflight,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_valid_only_state_semantics_audit as state_semantics,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_sensitive_frontier import (
    CapabilitySensitiveFrontierPopulation,
    CapabilitySensitiveTaskArtifact,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_mapper_v2_frequency_preflight_models import (  # noqa: E501
    DetailFile,
    FileBinding,
    FreshFrequencySourceBinding,
    FreshFrequencySourcePopulation,
    FreshnessChannelRow,
    ReproducibilityRootAudit,
    SourceSelectionAudit,
    identity,
)
from trusted_synthesis.runtime.agent.prospective_qualified_final_response_grammar import (
    QualifiedFinalResponseGrammar,
)

RUN_ID: Final = "finance_v26_160_mapper_v2_reachability_frequency_preflight_v1_20260827"
OUTPUT_DIR: Final = (
    "artifacts/vtdo_experiment/"
    "finance_v26_160_mapper_v2_reachability_frequency_preflight_v1_20260827"
)
IMPLEMENTATION_PATHS: Final = (
    "src/trusted_synthesis/core/trajectory/reachability_frequency_v2.py",
    "src/trusted_synthesis/core/trajectory/empirical_state_mapping_v2.py",
    "src/trusted_synthesis/core/trajectory/reference_empirical_state_mapping_v2.py",
    "src/trusted_synthesis/experiments/vtdo_experiment/"
    "phase1_v26_mapper_v2_frequency_preflight_models.py",
    "src/trusted_synthesis/experiments/vtdo_experiment/"
    "phase1_v26_mapper_v2_reachability_frequency_preflight.py",
    "src/trusted_synthesis/experiments/vtdo_experiment/phase1_v26_mapper_v2_gold_fixtures.py",
    "src/trusted_synthesis/runtime/agent/prospective_reachability_runner_vnext.py",
)
NEXT_STAGE: Final = "fresh_mapper_v2_reachability_frequency_execution_only"
PROSPECTIVE_RUNNER_RUN_ID: Final = "finance_v26_160_mapper_v2_frequency_runner_v1_20260827"
PROSPECTIVE_EXECUTION_RUN_ID: Final = (
    "finance_v26_161_mapper_v2_reachability_frequency_execution_v1_20260827"
)
PROSPECTIVE_REPORT_RUN_ID: Final = (
    "finance_v26_161_mapper_v2_reachability_frequency_execution_report_v1_20260827"
)
SOURCE_SELECTION_SALT: Final = "finance-v26.160-mapper-v2-frequency-source-selection-v1"
SEED_SALT: Final = "finance-v26.160-mapper-v2-frequency-seed-v1"
EXPECTED_PREDECESSOR_REPORT_ID: Final = (
    "finance_v26_state_semantics_audit_report:"
    "1af922c296dba8df78cec0082178e0e913d8ad228bb3b95dfe7371b06b73fd08"
)
EXPECTED_PREDECESSOR_TRANSITION_ID: Final = (
    "finance_v26_state_semantics_transition:"
    "17fe66c33e8c2d0f284b0d06bb85a881f61f7d52ff685a74e5f6c26cade44f31"
)
MISSING_HISTORICAL_SNAPSHOT: Final = (
    "artifacts/vtdo_experiment/"
    "finance_v25_44_hardened_stopping_evidence_snapshot_v3_20260816/"
    "finance_stopping_evidence_snapshot.jsonl"
)
TASK_COUNT: Final = 12
PATH_COUNT: Final = 36
CELL_COUNT: Final = 48
JOB_COUNT: Final = 360
UNCONDITIONAL_REPLICAS: Final = 12
CONDITIONED_REPLICAS: Final = 6


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _canonical_bytes(value: Any) -> bytes:
    if isinstance(value, BaseModel):
        value = value.model_dump(mode="json")
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
        + b"\n"
    )


def _write_json_atomic(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(_canonical_bytes(value))
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


def _reproducibility_root(
    *,
    package_root: Path,
    implementation_root: Path,
    implementation_paths: Sequence[str] = IMPLEMENTATION_PATHS,
) -> ReproducibilityRootAudit:
    predecessor_dir = package_root / state_semantics.OUTPUT_DIR
    report = state_semantics.StateSemanticsAuditReport.model_validate(
        _load(predecessor_dir / "report.json")
    )
    transition = state_semantics.StateSemanticsTransitionContract.model_validate(
        _load(predecessor_dir / "prospective_transition_contract.json")
    )
    if (
        report.report_id != EXPECTED_PREDECESSOR_REPORT_ID
        or transition.contract_id != EXPECTED_PREDECESSOR_TRANSITION_ID
        or report.transition_contract_id != transition.contract_id
        or transition.next_permitted_stage
        != "fresh_mapper_v2_reachability_frequency_experiment_preflight_only"
        or transition.provider_execution_authorized
    ):
        raise ValueError("v26.160 predecessor authorization changed")
    predecessor_files = tuple(sorted(path for path in predecessor_dir.iterdir() if path.is_file()))
    with tempfile.TemporaryDirectory(prefix="v26_160_predecessor_") as temporary:
        rebuilt_dir = Path(temporary)
        state_semantics.build_state_semantics_audit(
            implementation_root=package_root,
            output_dir=rebuilt_dir,
        )
        rebuilt_files = tuple(sorted(path for path in rebuilt_dir.iterdir() if path.is_file()))
        if tuple(path.name for path in predecessor_files) != tuple(
            path.name for path in rebuilt_files
        ):
            raise ValueError("v26.160 predecessor direct file set changed")
        match_count = sum(
            path.read_bytes() == (rebuilt_dir / path.name).read_bytes()
            for path in predecessor_files
        )
    bindings: dict[str, FileBinding] = {}

    def bind(relative_path: str, source_kind: Any) -> None:
        path = implementation_root / relative_path
        if not path.is_file():
            path = package_root / relative_path
        if not path.is_file():
            raise ValueError(f"v26.160 input binding unavailable: {relative_path}")
        bindings[relative_path] = FileBinding(
            relative_path=relative_path,
            sha256=_sha256(path),
            byte_count=path.stat().st_size,
            source_kind=source_kind,
        )

    for path in predecessor_files:
        bind(str(path.relative_to(package_root)), "v26_159_direct_output")
    source_files = (
        f"{source_base.OUTPUT_DIR}/fresh_source_sampling_frame.json",
        f"{source_base.OUTPUT_DIR}/capability_source_population.json",
        f"{source_base.OUTPUT_DIR}/reachability_source_population.json",
        f"{capability.OUTPUT_DIR}/fresh_source_sampling_frame.json",
        f"{capability.OUTPUT_DIR}/fresh_capability_source_population.json",
    )
    for relative in source_files:
        bind(
            relative,
            "fresh_sampling_frame"
            if relative.endswith("fresh_source_sampling_frame.json")
            else ("historical_source_population"),
        )
    protocol_files = (
        bounded.PROFILE_PATH,
        source_base.ACTION_GRAMMAR_PATH,
        source_base.FINAL_GRAMMAR_PATH,
        "artifacts/vtdo_experiment/"
        "finance_v26_90_budget_feasible_role_task_rematerialization_v2_20260821/"
        "verifier_v2_replay_bindings.json",
    )
    for relative in protocol_files:
        bind(relative, "frozen_protocol_input")
    for relative in implementation_paths:
        bind(relative, "implementation")
    values = {
        "predecessor_report_id": report.report_id,
        "predecessor_transition_id": transition.contract_id,
        "predecessor_direct_output_count": len(predecessor_files),
        "predecessor_rebuilt_output_count": len(rebuilt_files),
        "predecessor_byte_match_count": match_count,
        "file_bindings": tuple(bindings[key] for key in sorted(bindings)),
        "current_stage_input_file_count": len(bindings),
        "missing_historical_snapshot_path": MISSING_HISTORICAL_SNAPSHOT,
    }
    return cast(
        ReproducibilityRootAudit,
        _model(
            ReproducibilityRootAudit,
            values,
            field="audit_id",
            prefix="finance_v26_frequency_reproducibility_root:",
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
        prefix="finance_v26_frequency_source_rank:",
    )


def _fresh_source_binding(
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
    root_audit: ReproducibilityRootAudit,
) -> tuple[
    CapabilitySensitiveFrontierPopulation,
    FreshFrequencySourcePopulation,
    SourceSelectionAudit,
]:
    old_dir = package_root / source_base.OUTPUT_DIR
    old_frame = CapabilitySensitiveFrontierPopulation.model_validate(
        _load(old_dir / "fresh_source_sampling_frame.json")
    )
    old_by_id = {item.artifact_id: item for item in old_frame.tasks}
    prior_tasks: list[CapabilitySensitiveTaskArtifact] = []
    for name in ("capability_source_population.json", "reachability_source_population.json"):
        population = source_base.FreshRoleSourcePopulation.model_validate(_load(old_dir / name))
        prior_tasks.extend(old_by_id[item.source_task_artifact_id] for item in population.tasks)
    frame_dir = package_root / capability.OUTPUT_DIR
    frame = CapabilitySensitiveFrontierPopulation.model_validate(
        _load(frame_dir / "fresh_source_sampling_frame.json")
    )
    prior_capability = capability.FreshCapabilitySourcePopulation.model_validate(
        _load(frame_dir / "fresh_capability_source_population.json")
    )
    prior_tasks.extend(item.source_task for item in prior_capability.tasks)
    if len({item.artifact_id for item in prior_tasks}) != 36:
        raise ValueError("v26.160 prior source-task exclusion denominator changed")
    excluded = source_base._source_task_channels(tuple(prior_tasks))  # noqa: SLF001
    eligible: list[CapabilitySensitiveTaskArtifact] = []
    for task in frame.tasks:
        channels = source_base._source_task_channels((task,))  # noqa: SLF001
        if all(
            not (channels[channel] & excluded[channel])
            for channel in source_base.FRESHNESS_CHANNELS
        ):
            eligible.append(task)
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
                raise ValueError(f"v26.160 source frame lacks {mechanism}|{tier}")
            selected.append(candidates[0])
            bindings.append(_fresh_source_binding(candidates[0], mechanism=mechanism, tier=tier))
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
        raise ValueError("v26.160 fresh Population overlaps prior sources")
    selection_values = {
        "reproducibility_root_audit_id": root_audit.audit_id,
        "source_frame_population_id": frame.population_id,
        "source_population_id": population.population_id,
        "eligible_model_unexposed_task_count": len(eligible),
        "freshness_channels": channel_rows,
    }
    selection = cast(
        SourceSelectionAudit,
        _model(
            SourceSelectionAudit,
            selection_values,
            field="audit_id",
            prefix="finance_v26_frequency_source_selection:",
        ),
    )
    _write_json_atomic(output_dir / "fresh_source_sampling_frame.json", frame)
    _write_json_atomic(output_dir / "fresh_reachability_source_population.json", population)
    _write_json_atomic(output_dir / "source_selection_audit.json", selection)
    return frame, population, selection


def _load_joint_contract(package_root: Path) -> JointSupportValidityContract:
    value = JointSupportValidityContract.model_validate(
        _load(package_root / joint_preflight.OUTPUT_DIR / "joint_support_validity_contract.json")
    )
    if value.contract_id != reachability.EXPECTED_JOINT_CONTRACT_ID:
        raise ValueError("v26.160 Joint Support/Validity Contract changed")
    return value


def _make_paths(
    *,
    tasks: reachability.TaskPackageCatalog,
    selection: SourceSelectionAudit,
    static: Any,
    grammar: QualifiedFinalResponseGrammar,
) -> tuple[
    reachability.PathCatalog,
    tuple[reachability._CompiledPath, ...],
    tuple[reachability._CompiledPath, ...],
]:
    registered = tuple(
        reachability._compile_path(  # noqa: SLF001
            package=package,
            frozen_input_id=selection.audit_id,
            path_strategy_id=strategy,
            public_path_condition=strategy,
            materialize_registered_path=True,
            action_grammar=static.action_grammar,
            old_final_grammar=static.final_grammar,
            qualified_grammar=grammar,
        )
        for package in tasks.packages
        for strategy in reachability.PATH_STRATEGIES
    )
    unconditional = tuple(
        reachability._compile_path(  # noqa: SLF001
            package=package,
            frozen_input_id=selection.audit_id,
            path_strategy_id="unconditional",
            public_path_condition=None,
            materialize_registered_path=False,
            action_grammar=static.action_grammar,
            old_final_grammar=static.final_grammar,
            qualified_grammar=grammar,
        )
        for package in tasks.packages
    )
    paths = tuple(
        sorted(
            (cast(reachability.FreshReachabilityPath, item.path) for item in registered),
            key=lambda item: item.path_id,
        )
    )
    values = {
        "task_package_catalog_id": tasks.catalog_id,
        "paths": paths,
        "registered_state_count": sum(item.action_state_count for item in paths),
        "maximum_candidate_count": max(item.maximum_candidate_count for item in paths),
        "maximum_prompt_utf8_bytes": max(
            max(
                item.maximum_action_primary_prompt_utf8_bytes,
                item.maximum_action_abi_rescue_prompt_utf8_bytes,
                item.maximum_semantic_recovery_prompt_utf8_bytes,
                item.final_primary_prompt_utf8_bytes,
                item.final_rescue_prompt_utf8_bytes,
            )
            for item in paths
        ),
        "maximum_registered_path_tokens": max(
            item.static_complete_path_upper_bound_tokens for item in paths
        ),
    }
    provisional = reachability.PathCatalog.model_construct(catalog_id="pending", **values)
    catalog = reachability.PathCatalog(
        catalog_id=reachability._identity(  # noqa: SLF001
            provisional,
            "catalog_id",
            "finance_v26_fresh_reachability_path_catalog:",
        ),
        **values,
    )
    registered_by_id = {
        cast(reachability.FreshReachabilityPath, item.path).path_id: item for item in registered
    }
    ordered_registered = tuple(registered_by_id[item.path_id] for item in catalog.paths)
    return catalog, ordered_registered, unconditional


def _make_support_and_resource(
    *,
    package_root: Path,
    paths: reachability.PathCatalog,
    registered: tuple[reachability._CompiledPath, ...],
    selection: SourceSelectionAudit,
    static: Any,
    grammar: QualifiedFinalResponseGrammar,
) -> tuple[
    reachability.SupportClosureAudit,
    reachability.ReachabilityDetourQualificationAudit,
    reachability.ResourceContract,
]:
    support = reachability._support_closure(paths, registered)  # noqa: SLF001
    if support.typed_support_exit_count != 0:
        raise ValueError("v26.160 registered support closure contains a typed Support Exit")
    detours = reachability._make_detour_audit(  # noqa: SLF001
        package_root=package_root,
        paths=paths,
        executions=registered,
        frozen_input=cast(Any, SimpleNamespace(audit_id=selection.audit_id)),
        static=static,
        grammar=grammar,
        support=support,
    )
    resource = reachability._make_resource(paths, support, detours)  # noqa: SLF001
    return support, detours, resource
