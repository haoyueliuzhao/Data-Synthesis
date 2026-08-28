from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import replace
from pathlib import Path
from typing import Any, Final, Literal, cast

from pydantic import BaseModel

from trusted_synthesis.core.task.capability_observation import (
    CAPABILITY_FAMILY_ORDER,
    OBSERVATION_DEPTH_ORDER,
    BoundarySelectionContract,
    CapabilityDepthOverlay,
    CapabilityFamily,
    CapabilityObservationGroup,
    CapabilityObservationProtocol,
    CapabilityObservationVariant,
    DepthDeltaContract,
    DepthDeltaRow,
    ExposureBlockContract,
    MatchedTaskSkeleton,
    NuisanceSignature,
    ObservabilityFloorContract,
    ObservationDepth,
    ObservationPartition,
    ObservationSlot,
    RoleExecutableDepthSignature,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_bounded_policy_capability_censoring_vtdo_admission_audit_models as v166,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_capability_breadth_depth_task_synthesis_models as models,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_capability_observation_static_audit as static_audit,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_role_kernel_compatibility_preflight as source_base,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_role_kernel_scalability_design as role_compiler,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_sensitive_frontier import (
    CapabilitySensitiveFrontierPopulation,
    CapabilitySensitiveTaskArtifact,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_matched_capability_ladder import (
    _core_instruction,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_mapper_v2_frequency_preflight_models import (  # noqa: E501
    FreshFrequencySourcePopulation,
)
from trusted_synthesis.hashing import canonical_hash

RUN_ID: Final = "finance_v26_167_capability_breadth_depth_static_audit_v1_20260828"
OUTPUT_DIR: Final = (
    "artifacts/vtdo_experiment/finance_v26_167_capability_breadth_depth_static_audit_v1_20260828"
)
SOURCE_SELECTION_SALT: Final = "finance-v26.167-capability-observation-source-selection-v1"
EXPECTED_REVIEW_SHA256: Final = "5fac66582cb594bd5299c3d11f4d7fe274ba72fb258791f74513ea183a120608"
EXPECTED_REVIEW_BYTE_COUNT: Final = 37_622
V163_DIR: Final = (
    "artifacts/vtdo_experiment/"
    "finance_v26_163_bounded_policy_endpoint_frequency_preflight_v1_20260827"
)
V166_DIR: Final = v166.OUTPUT_DIR
SOURCE_FRAME_PATH: Final = f"{V163_DIR}/fresh_source_sampling_frame.json"
PRIOR_SOURCE_POPULATION_PATH: Final = f"{V163_DIR}/fresh_reachability_source_population.json"
V163_PACKAGE_CATALOG_PATH: Final = f"{V163_DIR}/reachability_task_package_catalog.json"
V163_POLICY_PATH: Final = f"{V163_DIR}/generation_policy.json"
V163_RESOURCE_PATH: Final = f"{V163_DIR}/reachability_resource_contract.json"
V163_SOURCE_SELECTION_AUDIT_PATH: Final = f"{V163_DIR}/source_selection_audit.json"
IMPLEMENTATION_PATHS: Final = (
    "src/trusted_synthesis/core/task/capability_observation.py",
    "src/trusted_synthesis/experiments/vtdo_experiment/"
    "phase1_v26_capability_breadth_depth_task_synthesis_models.py",
    "src/trusted_synthesis/experiments/vtdo_experiment/"
    "phase1_v26_capability_observation_static_audit.py",
    "src/trusted_synthesis/experiments/vtdo_experiment/"
    "phase1_v26_capability_breadth_depth_task_synthesis.py",
)
FAMILY_SOURCE_MAP: Final = {
    CapabilityFamily.CONTEXT_CONDITIONED_ACTION: "finance.branching_operation_plan",
    CapabilityFamily.SEMANTIC_RECONCILIATION: "finance.definition_reconciliation",
    CapabilityFamily.FAILURE_RECOVERY: "finance.recovery_guided_search",
    CapabilityFamily.STATE_DEPENDENT_STOPPING: "finance.stopping_decision_control",
}
NUISANCE_DIMENSIONS: Final = (
    "distractor_load",
    "evidence_count",
    "program_node_count",
    "resource_ceiling",
    "tool_count",
    "verification_structure",
)


def _resolve_package_root(root: Path) -> Path:
    if (root / "src" / "trusted_synthesis").is_dir():
        return root.resolve()
    candidate = root / "trusted_data_synthesis"
    if (candidate / "src" / "trusted_synthesis").is_dir():
        return candidate.resolve()
    raise ValueError("v26.167 cannot resolve the trusted_data_synthesis package root")


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _json_value(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, Mapping):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    return value


def _canonical_bytes(value: Any) -> bytes:
    return (
        json.dumps(
            _json_value(value),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
        + b"\n"
    )


def _write(path: Path, value: Any) -> None:
    if path.exists():
        raise ValueError(f"v26.167 immutable output already exists:{path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(_canonical_bytes(value))
    temporary.replace(path)


def _make_model(
    model_type: type[BaseModel],
    values: dict[str, Any],
    *,
    field: str,
    prefix: str,
) -> Any:
    provisional = model_type.model_construct(**{field: "pending"}, **values)
    return model_type(**{field: models.identity(provisional, field, prefix)}, **values)


def _source_rank(family: CapabilityFamily, task: CapabilitySensitiveTaskArtifact) -> str:
    return hashlib.sha256(
        (f"{SOURCE_SELECTION_SALT}|{family.value}|{task.artifact_id}").encode()
    ).hexdigest()


def _source_channels(task: CapabilitySensitiveTaskArtifact) -> dict[str, tuple[str, ...]]:
    channels = source_base._source_task_channels((task,))  # noqa: SLF001
    return {key: tuple(sorted(value)) for key, value in channels.items()}


def _select_fresh_sources(
    *,
    package_root: Path,
) -> tuple[
    CapabilitySensitiveFrontierPopulation,
    FreshFrequencySourcePopulation,
    tuple[models.SelectedObservationSource, ...],
    dict[str, CapabilitySensitiveTaskArtifact],
    dict[CapabilityFamily, int],
    dict[str, int],
]:
    frame_path = package_root / SOURCE_FRAME_PATH
    prior_path = package_root / PRIOR_SOURCE_POPULATION_PATH
    frame = CapabilitySensitiveFrontierPopulation.model_validate(_load(frame_path))
    prior = FreshFrequencySourcePopulation.model_validate(_load(prior_path))
    source_selection = cast(
        dict[str, Any],
        _load(package_root / V163_SOURCE_SELECTION_AUDIT_PATH),
    )
    source_freshness_rows = cast(
        Sequence[Mapping[str, Any]],
        source_selection["freshness_channels"],
    )
    if (
        source_selection["source_frame_population_id"] != frame.population_id
        or source_selection["source_population_id"] != prior.population_id
        or source_selection["frame_candidate_count_before_exclusion"] != 70
        or source_selection["frame_candidate_count_after_exclusion"] != 70
        or source_selection["source_selection_before_policy_mapper_path_resource_or_outcome_load"]
        is not True
        or source_selection["model_outcomes_used_for_selection"] is not False
        or any(int(item["overlap_count"]) for item in source_freshness_rows)
    ):
        raise ValueError("v26.167 v26.163 source-frame freshness proof changed")
    historical_excluded_counts = {
        str(item["channel"]): int(item["excluded_count"]) for item in source_freshness_rows
    }
    if len(frame.tasks) != 70 or len(prior.tasks) != 12:
        raise ValueError("v26.167 frozen source denominators changed")
    prior_ids = {item.source_task_artifact_id for item in prior.tasks}
    prior_tasks = tuple(item.source_task for item in prior.tasks)
    prior_channels = source_base._source_task_channels(prior_tasks)  # noqa: SLF001
    selected: list[models.SelectedObservationSource] = []
    selected_tasks: dict[str, CapabilitySensitiveTaskArtifact] = {}
    eligible_counts: dict[CapabilityFamily, int] = {}
    selected_channel_sets: dict[str, set[str]] = {
        key: set() for key in source_base.FRESHNESS_CHANNELS
    }
    for family in CAPABILITY_FAMILY_ORDER:
        source_family = FAMILY_SOURCE_MAP[family]
        eligible = []
        for task in frame.tasks:
            if task.family != source_family or task.artifact_id in prior_ids:
                continue
            channels = source_base._source_task_channels((task,))  # noqa: SLF001
            if any(
                channels[channel] & prior_channels[channel]
                for channel in source_base.FRESHNESS_CHANNELS
            ):
                continue
            eligible.append(task)
        eligible_counts[family] = len(eligible)
        if len(eligible) < 4:
            raise ValueError(
                f"v26.167 Evidence Capacity supports only {len(eligible)} groups for {family.value}"
            )
        ranked = sorted(eligible, key=lambda item: _source_rank(family, item))
        for group_index, task in enumerate(ranked[:4], start=1):
            canonical_channels = _source_channels(task)
            for channel in source_base.FRESHNESS_CHANNELS:
                overlap = set(canonical_channels[channel]) & selected_channel_sets[channel]
                if overlap:
                    raise ValueError(
                        f"v26.167 selected matched groups overlap on {channel}:{sorted(overlap)}"
                    )
                selected_channel_sets[channel].update(canonical_channels[channel])
            partition = (
                ObservationPartition.DEVELOPMENT
                if group_index <= 2
                else ObservationPartition.CONFIRMATION
            )
            values = {
                "capability_family": family,
                "group_index": group_index,
                "partition": partition,
                "source_rank": _source_rank(family, task),
                "source_task_artifact_id": task.artifact_id,
                "source_task_id": task.task.task_id,
                "historical_difficulty_tier": task.tier.value,
                "core_semantic_signature": next(
                    iter(canonical_channels["core_semantic_signature"])
                ),
                "task_signature": task.task.task_hash,
                "mechanism_instance_signature": next(
                    iter(canonical_channels["mechanism_instance_signature"])
                ),
                "evidence_ids": canonical_channels["evidence_id"],
                "evidence_version_ids": canonical_channels["evidence_version_id"],
                "source_record_ids": canonical_channels["source_record_id"],
            }
            binding = cast(
                models.SelectedObservationSource,
                _make_model(
                    models.SelectedObservationSource,
                    values,
                    field="binding_id",
                    prefix="finance_v26_capability_observation_source_binding:",
                ),
            )
            selected.append(binding)
            selected_tasks[binding.binding_id] = task
    return (
        frame,
        prior,
        tuple(selected),
        selected_tasks,
        eligible_counts,
        historical_excluded_counts,
    )


def _external_authorization(path: Path) -> models.ExternalAuditAuthorization:
    if _sha256(path) != EXPECTED_REVIEW_SHA256 or path.stat().st_size != EXPECTED_REVIEW_BYTE_COUNT:
        raise ValueError("v26.167 external review binding changed")
    values = {
        "review_sha256": EXPECTED_REVIEW_SHA256,
        "review_byte_count": EXPECTED_REVIEW_BYTE_COUNT,
        "authorized_stage": "capability_breadth_depth_task_synthesis_and_static_audit_only",
    }
    return cast(
        models.ExternalAuditAuthorization,
        _make_model(
            models.ExternalAuditAuthorization,
            values,
            field="authorization_id",
            prefix="finance_v26_capability_breadth_depth_external_audit_authorization:",
        ),
    )


def _file_binding(
    *,
    package_root: Path,
    relative_path: str,
    source_kind: str,
) -> models.FileBinding:
    path = package_root / relative_path
    if not path.is_file():
        raise ValueError(f"v26.167 bound input is missing:{relative_path}")
    return models.FileBinding(
        relative_path=relative_path,
        sha256=_sha256(path),
        byte_count=path.stat().st_size,
        source_kind=cast(Any, source_kind),
    )


def _source_replay(
    *,
    package_root: Path,
    authorization: models.ExternalAuditAuthorization,
) -> models.SourceReplayAudit:
    v163_paths = (
        SOURCE_FRAME_PATH,
        PRIOR_SOURCE_POPULATION_PATH,
        V163_PACKAGE_CATALOG_PATH,
        V163_POLICY_PATH,
        V163_RESOURCE_PATH,
        V163_SOURCE_SELECTION_AUDIT_PATH,
    )
    v166_paths = (
        f"{V166_DIR}/coverage_gap_registry.json",
        f"{V166_DIR}/fresh_confirmation_protocol.json",
        f"{V166_DIR}/report.json",
        f"{V166_DIR}/terminal_endpoint_schema_audit.json",
        f"{V166_DIR}/transition_contract.json",
    )
    bindings = [
        models.FileBinding(
            relative_path="external_joint_audit_input.txt",
            sha256=authorization.review_sha256,
            byte_count=authorization.review_byte_count,
            source_kind="external_audit_input",
        )
    ]
    bindings.extend(
        _file_binding(
            package_root=package_root,
            relative_path=path,
            source_kind="implementation",
        )
        for path in IMPLEMENTATION_PATHS
    )
    bindings.extend(
        _file_binding(
            package_root=package_root,
            relative_path=path,
            source_kind="v26_163_frozen_source",
        )
        for path in v163_paths
    )
    bindings.extend(
        _file_binding(
            package_root=package_root,
            relative_path=path,
            source_kind="v26_166_frozen_output",
        )
        for path in v166_paths
    )
    values = {
        "authorization_id": authorization.authorization_id,
        "bindings": tuple(sorted(bindings, key=lambda item: item.relative_path)),
    }
    return cast(
        models.SourceReplayAudit,
        _make_model(
            models.SourceReplayAudit,
            values,
            field="audit_id",
            prefix="finance_v26_capability_breadth_depth_source_replay:",
        ),
    )


def _load_v166(
    package_root: Path,
) -> tuple[
    v166.CapabilityCensoringAuditReport,
    v166.FreshConfirmationProtocol,
    v166.TransitionContract,
    v166.CoverageGapRegistry,
    dict[str, Any],
]:
    directory = package_root / V166_DIR
    report = v166.CapabilityCensoringAuditReport.model_validate(_load(directory / "report.json"))
    protocol = v166.FreshConfirmationProtocol.model_validate(
        _load(directory / "fresh_confirmation_protocol.json")
    )
    transition = v166.TransitionContract.model_validate(
        _load(directory / "transition_contract.json")
    )
    coverage = v166.CoverageGapRegistry.model_validate(
        _load(directory / "coverage_gap_registry.json")
    )
    terminal = cast(dict[str, Any], _load(directory / "terminal_endpoint_schema_audit.json"))
    if (
        report.fresh_confirmation_protocol_id != protocol.protocol_id
        or report.transition_id != transition.transition_id
        or transition.fresh_confirmation_protocol_id != protocol.protocol_id
        or report.coverage_gap_registry_id != coverage.registry_id
    ):
        raise ValueError("v26.167 v26.166 predecessor bindings changed")
    return report, protocol, transition, coverage, terminal


def _legacy_supersession(
    *,
    report: v166.CapabilityCensoringAuditReport,
    protocol: v166.FreshConfirmationProtocol,
    transition: v166.TransitionContract,
) -> models.LegacyProtocolSupersession:
    values = {
        "v26_166_report_id": report.report_id,
        "v26_166_fresh_confirmation_protocol_id": protocol.protocol_id,
        "v26_166_transition_id": transition.transition_id,
        "missing_contract_dimensions": tuple(
            sorted(
                (
                    "boundary_selection",
                    "capability_family",
                    "confirmation_seal",
                    "d0_observability_anchor",
                    "depth_delta",
                    "development_confirmation_split",
                    "exposure_block",
                    "freshness_channels",
                    "independent_group_count",
                    "matched_group_identity",
                    "maximum_skeleton",
                    "nuisance_invariance",
                    "observation_depth",
                    "primary_target_load",
                    "role_depth_preservation",
                )
            )
        ),
        "replacement_stage": "capability_breadth_depth_task_synthesis_and_static_audit_only",
    }
    return cast(
        models.LegacyProtocolSupersession,
        _make_model(
            models.LegacyProtocolSupersession,
            values,
            field="decision_id",
            prefix="finance_v26_legacy_confirmation_protocol_supersession:",
        ),
    )


def _tier_boundary() -> models.HistoricalTierBoundaryContract:
    return cast(
        models.HistoricalTierBoundaryContract,
        _make_model(
            models.HistoricalTierBoundaryContract,
            {},
            field="contract_id",
            prefix="finance_v26_historical_tier_observation_depth_boundary:",
        ),
    )


def _protocol() -> CapabilityObservationProtocol:
    return cast(
        CapabilityObservationProtocol,
        _make_model(
            CapabilityObservationProtocol,
            {},
            field="protocol_id",
            prefix="capability_observation_protocol:",
        ),
    )


def _observability_floor() -> ObservabilityFloorContract:
    values = {
        "d0_requirements": {
            CapabilityFamily.CONTEXT_CONDITIONED_ACTION: (
                "at_least_two_legal_context_actions",
                "one_real_context_dependent_decision",
            ),
            CapabilityFamily.SEMANTIC_RECONCILIATION: (
                "one_nonidentity_normalization_axis",
                "normalization_reference_consumed_downstream",
            ),
            CapabilityFamily.FAILURE_RECOVERY: (
                "one_real_typed_failure",
                "revised_action_then_success",
            ),
            CapabilityFamily.STATE_DEPENDENT_STOPPING: (
                "clear_completed_state",
                "one_visible_legal_action_that_must_not_execute",
            ),
        }
    }
    return cast(
        ObservabilityFloorContract,
        _make_model(
            ObservabilityFloorContract,
            values,
            field="contract_id",
            prefix="observability_floor_contract:",
        ),
    )


def _boundary_selection() -> BoundarySelectionContract:
    return cast(
        BoundarySelectionContract,
        _make_model(
            BoundarySelectionContract,
            {},
            field="contract_id",
            prefix="capability_boundary_selection_contract:",
        ),
    )


def _neutral_conditions() -> tuple[models.CapabilityNeutralGenerationCondition, ...]:
    output = []
    for family in CAPABILITY_FAMILY_ORDER:
        values = {"capability_family": family}
        output.append(
            _make_model(
                models.CapabilityNeutralGenerationCondition,
                values,
                field="condition_id",
                prefix="capability_neutral_generation_condition:",
            )
        )
    return tuple(output)


def _nuisance_signature(
    *,
    task: CapabilitySensitiveTaskArtifact,
    profile: Mapping[str, str],
    tool_ids: tuple[str, ...],
) -> NuisanceSignature:
    core_question = _core_instruction(task.task.public.instruction)
    verifier_hash = canonical_hash(
        {
            "program_verification": task.verification,
            "program_verifier_ids": tuple(
                node.verifier_id for node in task.task.oracle.task_program.nodes
            ),
        },
        prefix="capability_observation_verifier_core:",
    )
    values = {
        "source_task_artifact_id": task.artifact_id,
        "source_task_id": task.task.task_id,
        "historical_difficulty_tier": task.tier.value,
        "evidence_ids": tuple(sorted(item.evidence_id for item in task.public_corpus.evidence)),
        "evidence_version_ids": tuple(
            sorted(item.evidence_version_id for item in task.public_corpus.evidence)
        ),
        "source_record_ids": tuple(
            sorted({item.provenance.source_record_id for item in task.public_corpus.evidence})
        ),
        "core_question_hash": canonical_hash(
            core_question,
            prefix="capability_observation_core_question:",
        ),
        "canonical_result_hash": canonical_hash(
            task.projected_expected_output,
            prefix="capability_observation_canonical_result:",
        ),
        "answer_schema_hash": canonical_hash(
            task.task.public.answer_schema,
            prefix="capability_observation_answer_schema:",
        ),
        "answer_projection_hash": canonical_hash(
            task.answer_projection,
            prefix="capability_observation_answer_projection:",
        ),
        "oracle_program_hash": task.task.oracle.task_program.program_hash,
        "verifier_hash": verifier_hash,
        "verification_structure_hash": canonical_hash(
            {
                "verification_checkpoints": task.verification_checkpoints,
                "stopping_conditions": task.stopping_conditions,
            },
            prefix="capability_observation_verification_structure:",
        ),
        "tool_ids": tool_ids,
        "tool_environment_contract_id": canonical_hash(
            tool_ids,
            prefix="capability_observation_tool_environment_contract:",
        ),
        "prompt_contract_id": profile["prompt_contract_id"],
        "action_grammar_id": profile["action_grammar_id"],
        "final_grammar_id": profile["final_grammar_id"],
        "model_config_id": profile["model_config_id"],
        "thinking_policy_id": profile["thinking_policy_id"],
        "bounded_generation_policy_id": profile["bounded_generation_policy_id"],
        "resource_contract_id": profile["resource_contract_id"],
        "candidate_cap": 63,
    }
    return cast(
        NuisanceSignature,
        _make_model(
            NuisanceSignature,
            values,
            field="signature_id",
            prefix="capability_observation_nuisance_signature:",
        ),
    )


def _slot(
    slot_id: str,
    *,
    semantic_role: str,
    active: bool,
    legal_candidate_count: int,
    inactive_mode: str | None = None,
    dependency_slot_ids: tuple[str, ...] = (),
    delayed_public_update: bool = False,
    irreversible_choice: bool = False,
    typed_failure_kind: str | None = None,
    nonidentity_axes: tuple[str, ...] = (),
) -> ObservationSlot:
    return ObservationSlot(
        slot_id=slot_id,
        semantic_role=semantic_role,
        active=active,
        legal_candidate_count=legal_candidate_count,
        inactive_mode=cast(Any, inactive_mode),
        dependency_slot_ids=dependency_slot_ids,
        delayed_public_update=delayed_public_update,
        irreversible_choice=irreversible_choice,
        typed_failure_kind=typed_failure_kind,
        nonidentity_axes=nonidentity_axes,
        public_witness={
            "state_is_public": True,
            "slot_id": slot_id,
            "target_mechanism_required": active,
            "legal_candidate_count": legal_candidate_count,
            "expected_inert_mode": inactive_mode,
        },
    )


def _context_overlay(depth: ObservationDepth) -> tuple[dict[str, int], tuple[ObservationSlot, ...]]:
    loads = {
        ObservationDepth.D0_OBSERVABILITY_ANCHOR: (1, 1, 1, 0, 0),
        ObservationDepth.D1_BASIC: (2, 2, 1, 0, 1),
        ObservationDepth.D2_COMPOSITIONAL: (3, 3, 2, 1, 1),
        ObservationDepth.D3_STRESS: (4, 4, 3, 2, 2),
    }[depth]
    keys = (
        "ambiguity_load",
        "context_dependency_load",
        "decision_slot_load",
        "delayed_update_load",
        "irreversible_choice_load",
    )
    active_count = {
        ObservationDepth.D0_OBSERVABILITY_ANCHOR: 1,
        ObservationDepth.D1_BASIC: 1,
        ObservationDepth.D2_COMPOSITIONAL: 2,
        ObservationDepth.D3_STRESS: 3,
    }[depth]
    candidate_counts = {
        ObservationDepth.D0_OBSERVABILITY_ANCHOR: (2, 1, 1),
        ObservationDepth.D1_BASIC: (4, 1, 1),
        ObservationDepth.D2_COMPOSITIONAL: (4, 3, 1),
        ObservationDepth.D3_STRESS: (5, 4, 3),
    }[depth]
    slots = tuple(
        _slot(
            f"context_decision_slot_{index:02d}",
            semantic_role=f"context_dependent_operation_choice_{index:02d}",
            active=index <= active_count,
            legal_candidate_count=candidate_counts[index - 1],
            inactive_mode=None if index <= active_count else "unique_legal_action",
            dependency_slot_ids=((f"context_decision_slot_{index - 1:02d}",) if index > 1 else ()),
            delayed_public_update=index > 1 and index <= active_count,
            irreversible_choice=(
                index == active_count and depth != ObservationDepth.D0_OBSERVABILITY_ANCHOR
            ),
        )
        for index in range(1, 4)
    )
    return dict(zip(keys, loads, strict=True)), slots


def _reconciliation_overlay(
    depth: ObservationDepth,
) -> tuple[dict[str, int], tuple[ObservationSlot, ...]]:
    loads = {
        ObservationDepth.D0_OBSERVABILITY_ANCHOR: (1, 1, 1, 0, 1),
        ObservationDepth.D1_BASIC: (1, 2, 1, 0, 2),
        ObservationDepth.D2_COMPOSITIONAL: (2, 3, 2, 1, 3),
        ObservationDepth.D3_STRESS: (3, 4, 3, 2, 3),
    }[depth]
    keys = (
        "downstream_fanout_load",
        "nonidentity_axis_load",
        "normalization_reference_consumption_load",
        "raw_bypass_constraint_load",
        "target_record_load",
    )
    active_count = {
        ObservationDepth.D0_OBSERVABILITY_ANCHOR: 1,
        ObservationDepth.D1_BASIC: 2,
        ObservationDepth.D2_COMPOSITIONAL: 3,
        ObservationDepth.D3_STRESS: 3,
    }[depth]
    axis_sets = {
        ObservationDepth.D0_OBSERVABILITY_ANCHOR: (("definition",), (), ()),
        ObservationDepth.D1_BASIC: (("definition", "period"), ("unit",), ()),
        ObservationDepth.D2_COMPOSITIONAL: (
            ("definition", "period"),
            ("unit", "frequency"),
            ("time_basis",),
        ),
        ObservationDepth.D3_STRESS: (
            ("definition", "period"),
            ("unit", "currency"),
            ("frequency", "time_basis"),
        ),
    }[depth]
    slots = tuple(
        _slot(
            f"reconciliation_slot_{index:02d}",
            semantic_role=f"normalization_reference_contract_{index:02d}",
            active=index <= active_count,
            legal_candidate_count=2 if index <= active_count else 1,
            inactive_mode=None if index <= active_count else "identity_normalization",
            dependency_slot_ids=((f"reconciliation_slot_{index - 1:02d}",) if index > 1 else ()),
            nonidentity_axes=tuple(sorted(axis_sets[index - 1])),
        )
        for index in range(1, 4)
    )
    return dict(zip(keys, loads, strict=True)), slots


def _recovery_overlay(
    depth: ObservationDepth,
) -> tuple[dict[str, int], tuple[ObservationSlot, ...]]:
    loads = {
        ObservationDepth.D0_OBSERVABILITY_ANCHOR: (1, 1, 1, 1, 1),
        ObservationDepth.D1_BASIC: (2, 1, 1, 1, 1),
        ObservationDepth.D2_COMPOSITIONAL: (3, 2, 2, 1, 2),
        ObservationDepth.D3_STRESS: (4, 3, 3, 2, 3),
    }[depth]
    keys = (
        "branching_load",
        "consequence_load",
        "dependency_depth_load",
        "failure_type_diversity_load",
        "typed_failure_load",
    )
    active_count = {
        ObservationDepth.D0_OBSERVABILITY_ANCHOR: 1,
        ObservationDepth.D1_BASIC: 1,
        ObservationDepth.D2_COMPOSITIONAL: 2,
        ObservationDepth.D3_STRESS: 3,
    }[depth]
    candidates = {
        ObservationDepth.D0_OBSERVABILITY_ANCHOR: (1, 1, 1),
        ObservationDepth.D1_BASIC: (2, 1, 1),
        ObservationDepth.D2_COMPOSITIONAL: (2, 2, 1),
        ObservationDepth.D3_STRESS: (3, 2, 2),
    }[depth]
    failure_kinds = (
        "typed_selector_requires_refinement",
        "typed_definition_mismatch",
        "typed_dependency_not_ready",
    )
    slots = tuple(
        _slot(
            f"recovery_slot_{index:02d}",
            semantic_role=f"typed_failure_revision_success_{index:02d}",
            active=index <= active_count,
            legal_candidate_count=candidates[index - 1],
            inactive_mode=None if index <= active_count else "nontrigger_recovery_slot",
            dependency_slot_ids=((f"recovery_slot_{index - 1:02d}",) if index > 1 else ()),
            typed_failure_kind=failure_kinds[index - 1] if index <= active_count else None,
        )
        for index in range(1, 4)
    )
    return dict(zip(keys, loads, strict=True)), slots


def _stopping_overlay(
    depth: ObservationDepth,
) -> tuple[dict[str, int], tuple[ObservationSlot, ...]]:
    loads = {
        ObservationDepth.D0_OBSERVABILITY_ANCHOR: (1, 0, 1, 1, 1),
        ObservationDepth.D1_BASIC: (2, 1, 1, 2, 2),
        ObservationDepth.D2_COMPOSITIONAL: (3, 1, 2, 3, 3),
        ObservationDepth.D3_STRESS: (4, 2, 3, 4, 4),
    }[depth]
    keys = (
        "completion_predicate_load",
        "delayed_readiness_load",
        "near_terminal_load",
        "tempting_continuation_load",
        "verification_separation_load",
    )
    active_count = {
        ObservationDepth.D0_OBSERVABILITY_ANCHOR: 1,
        ObservationDepth.D1_BASIC: 2,
        ObservationDepth.D2_COMPOSITIONAL: 2,
        ObservationDepth.D3_STRESS: 3,
    }[depth]
    candidate_counts = {
        ObservationDepth.D0_OBSERVABILITY_ANCHOR: (2, 1, 1),
        ObservationDepth.D1_BASIC: (3, 2, 1),
        ObservationDepth.D2_COMPOSITIONAL: (3, 3, 1),
        ObservationDepth.D3_STRESS: (4, 3, 3),
    }[depth]
    slots = tuple(
        _slot(
            f"stopping_checkpoint_{index:02d}",
            semantic_role=f"near_terminal_completion_checkpoint_{index:02d}",
            active=index <= active_count,
            legal_candidate_count=candidate_counts[index - 1],
            inactive_mode=None if index <= active_count else "explicit_nonterminal_state",
            dependency_slot_ids=((f"stopping_checkpoint_{index - 1:02d}",) if index > 1 else ()),
            delayed_public_update=index == active_count
            and depth != ObservationDepth.D0_OBSERVABILITY_ANCHOR,
        )
        for index in range(1, 4)
    )
    return dict(zip(keys, loads, strict=True)), slots


def _overlay(family: CapabilityFamily, depth: ObservationDepth) -> CapabilityDepthOverlay:
    builder = {
        CapabilityFamily.CONTEXT_CONDITIONED_ACTION: _context_overlay,
        CapabilityFamily.SEMANTIC_RECONCILIATION: _reconciliation_overlay,
        CapabilityFamily.FAILURE_RECOVERY: _recovery_overlay,
        CapabilityFamily.STATE_DEPENDENT_STOPPING: _stopping_overlay,
    }[family]
    primary_load, slots = builder(depth)
    values = {
        "capability_family": family,
        "depth": depth,
        "slots": slots,
        "primary_load": primary_load,
        "primary_load_total": sum(primary_load.values()),
        "nuisance_delta": {key: 0 for key in NUISANCE_DIMENSIONS},
        "d0_is_real_mechanism_observation": True,
    }
    return cast(
        CapabilityDepthOverlay,
        _make_model(
            CapabilityDepthOverlay,
            values,
            field="overlay_id",
            prefix="capability_depth_overlay:",
        ),
    )


def _depth_delta(
    *,
    group_id: str,
    family: CapabilityFamily,
    overlays: tuple[CapabilityDepthOverlay, ...],
) -> DepthDeltaContract:
    rows = []
    for left, right in zip(overlays, overlays[1:], strict=False):
        deltas = {
            key: right.primary_load[key] - left.primary_load[key] for key in left.primary_load
        }
        rows.append(
            DepthDeltaRow(
                from_depth=left.depth,
                to_depth=right.depth,
                changed_primary_dimensions=tuple(
                    sorted(key for key, value in deltas.items() if value > 0)
                ),
                primary_deltas=deltas,
                total_delta=sum(deltas.values()),
            )
        )
    values = {
        "group_id": group_id,
        "capability_family": family,
        "rows": tuple(rows),
    }
    return cast(
        DepthDeltaContract,
        _make_model(
            DepthDeltaContract,
            values,
            field="contract_id",
            prefix="capability_depth_delta_contract:",
        ),
    )


def _compile_role_signature(
    *,
    group_id: str,
    family: CapabilityFamily,
    task: CapabilitySensitiveTaskArtifact,
    overlay: CapabilityDepthOverlay,
    nuisance: NuisanceSignature,
) -> RoleExecutableDepthSignature:
    draft = role_compiler._role_draft(  # noqa: SLF001
        task,
        role="capability",
        mechanism=cast(Any, family.value),
    )
    public_overlay = overlay.model_dump(mode="json")
    overlay_instruction = json.dumps(
        {
            "capability_observation": public_overlay,
            "fixed_maximum_skeleton": True,
            "inactive_slots_are_explicit": True,
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    draft = replace(
        draft,
        instruction=(
            f"{_core_instruction(task.task.public.instruction)} "
            "Follow this public capability-observation contract without changing the core "
            f"finance result: {overlay_instruction}"
        ),
        mechanism_public_state={
            **draft.mechanism_public_state,
            "capability_observation_contract": public_overlay,
        },
        mechanism_private_state={
            **draft.mechanism_private_state,
            "capability_observation_overlay_id": overlay.overlay_id,
            "capability_observation_primary_load": dict(overlay.primary_load),
        },
    )
    record, environment = role_compiler._upgrade_role_task(draft)  # noqa: SLF001
    role_overlay = record.task_package.task.public.metadata["mechanism_public_state"].get(
        "capability_observation_contract"
    )
    if role_overlay != public_overlay:
        raise ValueError("v26.167 Role compiler erased or changed the depth overlay")
    if (
        record.evidence_bundle.bundle_hash != task.evidence_bundle.bundle_hash
        or record.public_corpus.corpus_hash != task.public_corpus.corpus_hash
        or record.projected_expected_output != task.projected_expected_output
        or record.answer_projection != task.answer_projection
        or record.task_package.operation_contract.source_program_dag_hash
        != task.task.oracle.task_program.program_hash
    ):
        raise ValueError("v26.167 Role compiler changed a matched core dimension")
    environment_tool_ids = tuple(sorted(item.tool_id for item in environment.tools))
    allowed_tool_ids = tuple(sorted(record.task_package.tool_closure.allowed_tool_ids))
    tool_closure_passed = environment_tool_ids == allowed_tool_ids == nuisance.tool_ids
    runtime_replay_passed = (
        task.verification.passed
        and task.execution.final_output == task.verification.independently_computed_output
    )
    mechanism_necessity_passed = (
        record.task_package.mechanism_contract.target_mechanism_id == family.value
        and bool(record.task_package.mechanism_contract.required_witness_event_ids)
        and any(item.active for item in overlay.slots)
    )
    if not (tool_closure_passed and runtime_replay_passed and mechanism_necessity_passed):
        raise ValueError("v26.167 Role static closure failed")
    source_primary_hash = canonical_hash(
        overlay.primary_load,
        prefix="capability_observation_primary_load:",
    )
    role_primary_hash = canonical_hash(
        cast(Mapping[str, int], role_overlay)["primary_load"],
        prefix="capability_observation_primary_load:",
    )
    public_overlay_hash = canonical_hash(
        public_overlay,
        prefix="capability_observation_public_overlay:",
    )
    role_overlay_hash = canonical_hash(
        role_overlay,
        prefix="capability_observation_public_overlay:",
    )
    values = {
        "group_id": group_id,
        "overlay_id": overlay.overlay_id,
        "capability_family": family,
        "depth": overlay.depth,
        "source_task_artifact_id": task.artifact_id,
        "role_record_id": record.record_id,
        "role_task_package_id": record.task_package.package_id,
        "role_environment_manifest_id": environment.manifest_id,
        "source_primary_load_hash": source_primary_hash,
        "role_primary_load_hash": role_primary_hash,
        "source_nuisance_signature_id": nuisance.signature_id,
        "role_nuisance_signature_id": nuisance.signature_id,
        "public_overlay_hash": public_overlay_hash,
        "role_public_overlay_hash": role_overlay_hash,
    }
    return cast(
        RoleExecutableDepthSignature,
        _make_model(
            RoleExecutableDepthSignature,
            values,
            field="signature_id",
            prefix="role_executable_depth_signature:",
        ),
    )


def _build_groups(
    *,
    selected: tuple[models.SelectedObservationSource, ...],
    selected_tasks: Mapping[str, CapabilitySensitiveTaskArtifact],
    profile: Mapping[str, str],
) -> tuple[CapabilityObservationGroup, ...]:
    groups = []
    for binding in selected:
        task = selected_tasks[binding.binding_id]
        base_draft = role_compiler._role_draft(  # noqa: SLF001
            task,
            role="capability",
            mechanism=cast(Any, binding.capability_family.value),
        )
        _, base_environment = role_compiler._upgrade_role_task(base_draft)  # noqa: SLF001
        group_tool_ids = tuple(sorted(item.tool_id for item in base_environment.tools))
        nuisance = _nuisance_signature(
            task=task,
            profile=profile,
            tool_ids=group_tool_ids,
        )
        skeleton_values = {
            "capability_family": binding.capability_family,
            "source_task_artifact_id": task.artifact_id,
            "source_task_id": task.task.task_id,
            "historical_difficulty_tier": task.tier.value,
            "core_finance_question": _core_instruction(task.task.public.instruction),
            "nuisance_signature": nuisance,
        }
        skeleton = cast(
            MatchedTaskSkeleton,
            _make_model(
                MatchedTaskSkeleton,
                skeleton_values,
                field="skeleton_id",
                prefix="matched_capability_observation_skeleton:",
            ),
        )
        group_id = canonical_hash(
            {
                "capability_family": binding.capability_family.value,
                "group_index": binding.group_index,
                "partition": binding.partition.value,
                "source_binding_id": binding.binding_id,
                "skeleton_id": skeleton.skeleton_id,
            },
            prefix="capability_observation_group:",
        )
        overlays = tuple(
            _overlay(binding.capability_family, depth) for depth in OBSERVATION_DEPTH_ORDER
        )
        delta = _depth_delta(
            group_id=group_id,
            family=binding.capability_family,
            overlays=overlays,
        )
        variants = []
        for overlay in overlays:
            role_signature = _compile_role_signature(
                group_id=group_id,
                family=binding.capability_family,
                task=task,
                overlay=overlay,
                nuisance=nuisance,
            )
            variant_values = {
                "group_id": group_id,
                "partition": binding.partition,
                "capability_family": binding.capability_family,
                "depth": overlay.depth,
                "skeleton_id": skeleton.skeleton_id,
                "overlay": overlay,
                "role_signature": role_signature,
            }
            variants.append(
                _make_model(
                    CapabilityObservationVariant,
                    variant_values,
                    field="variant_id",
                    prefix="capability_observation_variant:",
                )
            )
        group_values = {
            "group_id": group_id,
            "group_index": binding.group_index,
            "partition": binding.partition,
            "capability_family": binding.capability_family,
            "skeleton": skeleton,
            "variants": tuple(variants),
            "depth_delta_contract": delta,
        }
        provisional = CapabilityObservationGroup.model_construct(
            group_hash="pending",
            **group_values,
        )
        groups.append(
            CapabilityObservationGroup(
                group_hash=models.identity(
                    provisional,
                    "group_hash",
                    "capability_observation_group_hash:",
                ),
                **group_values,
            )
        )
    return tuple(groups)


def _profile(package_root: Path) -> dict[str, str]:
    package_catalog = cast(dict[str, Any], _load(package_root / V163_PACKAGE_CATALOG_PATH))
    packages = cast(list[dict[str, Any]], package_catalog["packages"])

    def singleton(field: str) -> str:
        values = {str(item[field]) for item in packages}
        if len(values) != 1:
            raise ValueError(f"v26.167 v26.163 package profile varies on {field}")
        return next(iter(values))

    policy = cast(dict[str, Any], _load(package_root / V163_POLICY_PATH))
    resource = cast(dict[str, Any], _load(package_root / V163_RESOURCE_PATH))
    compact_projection_id = singleton("compact_projection_protocol_id")
    prompt_metadata_id = singleton("prompt_metadata_contract_id")
    profile = {
        "prompt_contract_id": canonical_hash(
            {
                "compact_projection_protocol_id": compact_projection_id,
                "prompt_metadata_contract_id": prompt_metadata_id,
            },
            prefix="capability_observation_prompt_contract:",
        ),
        "action_grammar_id": singleton("semantic_action_grammar_id"),
        "final_grammar_id": singleton("qualified_final_grammar_id"),
        "model_config_id": singleton("model_config_id"),
        "thinking_policy_id": singleton("thinking_binding_id"),
        "bounded_generation_policy_id": str(policy["policy_id"]),
        "resource_contract_id": str(resource["contract_id"]),
    }
    return profile


def _capacity_audit(
    *,
    package_root: Path,
    frame: CapabilitySensitiveFrontierPopulation,
    prior: FreshFrequencySourcePopulation,
    selected: tuple[models.SelectedObservationSource, ...],
    eligible_counts: dict[CapabilityFamily, int],
) -> models.EvidenceCapacityAudit:
    values = {
        "source_frame_population_id": frame.population_id,
        "source_frame_sha256": _sha256(package_root / SOURCE_FRAME_PATH),
        "prior_exposed_population_id": prior.population_id,
        "prior_exposed_population_sha256": _sha256(package_root / PRIOR_SOURCE_POPULATION_PATH),
        "eligible_source_counts": eligible_counts,
        "required_group_counts": {item: 4 for item in CAPABILITY_FAMILY_ORDER},
        "selected_sources": selected,
    }
    return cast(
        models.EvidenceCapacityAudit,
        _make_model(
            models.EvidenceCapacityAudit,
            values,
            field="audit_id",
            prefix="finance_v26_capability_observation_evidence_capacity_audit:",
        ),
    )


def _group_catalog(
    *,
    partition: ObservationPartition,
    groups: Sequence[CapabilityObservationGroup],
) -> models.CapabilityObservationGroupCatalog:
    values = {
        "partition": partition,
        "groups": tuple(sorted(groups, key=lambda item: item.group_id)),
    }
    return cast(
        models.CapabilityObservationGroupCatalog,
        _make_model(
            models.CapabilityObservationGroupCatalog,
            values,
            field="catalog_id",
            prefix=f"capability_observation_{partition.value}_group_catalog:",
        ),
    )


def _breadth_catalog(
    *,
    protocol: CapabilityObservationProtocol,
    groups: Sequence[CapabilityObservationGroup],
) -> models.CapabilityBreadthCatalog:
    values = {
        "protocol_id": protocol.protocol_id,
        "group_ids": tuple(sorted(item.group_id for item in groups)),
        "group_counts": dict(Counter(item.capability_family for item in groups)),
        "depth_counts": dict(
            Counter(variant.depth.value for group in groups for variant in group.variants)
        ),
        "generation_conditions": _neutral_conditions(),
    }
    return cast(
        models.CapabilityBreadthCatalog,
        _make_model(
            models.CapabilityBreadthCatalog,
            values,
            field="catalog_id",
            prefix="finance_v26_capability_breadth_catalog:",
        ),
    )


def _freshness_audit(
    *,
    capacity: models.EvidenceCapacityAudit,
    groups: Sequence[CapabilityObservationGroup],
    prior: FreshFrequencySourcePopulation,
    historical_excluded_counts: Mapping[str, int],
) -> models.PairedFreshnessAudit:
    selected = capacity.selected_sources
    prior_tasks = tuple(item.source_task for item in prior.tasks)
    prior_channels = source_base._source_task_channels(prior_tasks)  # noqa: SLF001
    selected_channel_map: dict[str, set[str]] = {
        "core_semantic_signature": {item.core_semantic_signature for item in selected},
        "evidence_id": {value for item in selected for value in item.evidence_ids},
        "evidence_version_id": {value for item in selected for value in item.evidence_version_ids},
        "group_semantic_identity": {item.group_id for item in groups},
        "mechanism_instance_signature": {item.mechanism_instance_signature for item in selected},
        "source_record_id": {value for item in selected for value in item.source_record_ids},
        "source_task_id": {item.source_task_artifact_id for item in selected},
        "task_id": {item.source_task_id for item in selected},
    }
    prior_map = {
        "core_semantic_signature": prior_channels["core_semantic_signature"],
        "evidence_id": prior_channels["evidence_id"],
        "evidence_version_id": prior_channels["evidence_version_id"],
        "group_semantic_identity": set(),
        "mechanism_instance_signature": prior_channels["mechanism_instance_signature"],
        "source_record_id": prior_channels["source_record_id"],
        "source_task_id": prior_channels["source_task_id"],
        "task_id": prior_channels["task_id"],
    }
    rows = tuple(
        models.FreshnessChannelRow(
            channel=cast(Any, channel),
            historical_or_exposed_count=(
                historical_excluded_counts.get(channel, 0) + len(prior_map[channel])
            ),
            selected_group_count=len(selected_channel_map[channel]),
            overlap_count=cast(Literal[0], len(selected_channel_map[channel] & prior_map[channel])),
        )
        for channel in sorted(selected_channel_map)
    )
    if any(item.overlap_count for item in rows):
        raise ValueError("v26.167 selected groups overlap prior model-exposed sources")
    values = {
        "capacity_audit_id": capacity.audit_id,
        "channels": rows,
    }
    return cast(
        models.PairedFreshnessAudit,
        _make_model(
            models.PairedFreshnessAudit,
            values,
            field="audit_id",
            prefix="finance_v26_capability_observation_paired_freshness_audit:",
        ),
    )


def _role_depth_audit(
    groups: Sequence[CapabilityObservationGroup],
) -> models.RoleDepthPreservationAudit:
    signatures = tuple(
        sorted(
            (variant.role_signature for group in groups for variant in group.variants),
            key=lambda item: item.signature_id,
        )
    )
    values = {"signatures": signatures}
    return cast(
        models.RoleDepthPreservationAudit,
        _make_model(
            models.RoleDepthPreservationAudit,
            values,
            field="audit_id",
            prefix="finance_v26_role_depth_preservation_audit:",
        ),
    )


def _terminal_matrix(source: Mapping[str, Any]) -> models.TerminalEndpointMatrix:
    names = {
        "completed_endpoint": "completed_endpoint",
        "instrument_endpoint": "instrument_failure",
        "measurement_support_exit": "measurement_support_exit",
        "model_result_failure": "model_result_failure",
        "policy_horizon": "policy_horizon",
        "privacy_endpoint": "privacy_rejection",
        "transport_endpoint": "transport_failure",
        "typed_semantic_rejection": "typed_semantic_rejection",
    }
    cases = []
    for row in cast(Sequence[Mapping[str, Any]], source["cases"]):
        endpoint = cast(Mapping[str, Any], row["endpoint"])
        cases.append(
            models.TerminalEndpointCase(
                terminal_kind=cast(Any, names[str(row["case_name"])]),
                endpoint_complete=bool(endpoint["bounded_policy_endpoint_observed"]),
                task_completion=cast(bool | None, row["expected_task_completion"]),
                base_valid=cast(bool | None, row["expected_base_validity"]),
                mechanism_endpoint_qualification=cast(
                    bool | None,
                    row["expected_mechanism_qualification"],
                ),
                qualified_valid=cast(bool | None, row["expected_qualified_validity"]),
                mapping_eligible=cast(bool | None, row["expected_mapping_eligible"]),
                task_verifier_invoked=int(row["expected_task_verifier_invocation_count"]) > 0,
            )
        )
    values = {"cases": tuple(sorted(cases, key=lambda item: item.terminal_kind))}
    return cast(
        models.TerminalEndpointMatrix,
        _make_model(
            models.TerminalEndpointMatrix,
            values,
            field="matrix_id",
            prefix="finance_v26_capability_observation_terminal_endpoint_matrix:",
        ),
    )


def _coverage_gap_disposition(
    coverage: v166.CoverageGapRegistry,
) -> models.CoverageGapDispositionCatalog:
    rows = []
    for historical in sorted(coverage.rows, key=lambda item: item.row_id):
        values = {"historical_coverage_gap_row_id": historical.row_id}
        rows.append(
            _make_model(
                models.CoverageGapDispositionRow,
                values,
                field="row_id",
                prefix="finance_v26_coverage_gap_prospective_disposition_row:",
            )
        )
    catalog_values: dict[str, Any] = {
        "historical_registry_id": coverage.registry_id,
        "rows": tuple(rows),
    }
    return cast(
        models.CoverageGapDispositionCatalog,
        _make_model(
            models.CoverageGapDispositionCatalog,
            catalog_values,
            field="catalog_id",
            prefix="finance_v26_coverage_gap_prospective_disposition_catalog:",
        ),
    )


def _exposure_block(
    *,
    development: models.CapabilityObservationGroupCatalog,
    confirmation: models.CapabilityObservationGroupCatalog,
    development_path: Path,
    confirmation_path: Path,
) -> ExposureBlockContract:
    values = {
        "development_group_ids": tuple(sorted(item.group_id for item in development.groups)),
        "confirmation_group_ids": tuple(sorted(item.group_id for item in confirmation.groups)),
        "development_catalog_sha256": _sha256(development_path),
        "sealed_confirmation_catalog_sha256": _sha256(confirmation_path),
    }
    return cast(
        ExposureBlockContract,
        _make_model(
            ExposureBlockContract,
            values,
            field="contract_id",
            prefix="capability_observation_exposure_block_contract:",
        ),
    )


def _transition(
    *,
    authorization: models.ExternalAuditAuthorization,
    static: models.TaskLadderStaticAudit,
    exposure: ExposureBlockContract,
    boundary: BoundarySelectionContract,
) -> models.TransitionContract:
    values = {
        "authorization_id": authorization.authorization_id,
        "static_audit_id": static.audit_id,
        "exposure_block_contract_id": exposure.contract_id,
        "boundary_selection_contract_id": boundary.contract_id,
    }
    return cast(
        models.TransitionContract,
        _make_model(
            models.TransitionContract,
            values,
            field="transition_id",
            prefix="finance_v26_capability_observation_transition:",
        ),
    )


def _detail_files(output_dir: Path) -> tuple[models.DetailFile, ...]:
    return tuple(
        models.DetailFile(
            relative_path=path.name,
            sha256=_sha256(path),
            byte_count=path.stat().st_size,
        )
        for path in sorted(output_dir.iterdir(), key=lambda item: item.name)
        if path.is_file() and path.name != "report.json"
    )


def build(
    *,
    package_root: Path,
    output_dir: Path,
    external_audit_path: Path,
) -> models.BuildProducts:
    package_root = _resolve_package_root(package_root)
    output_dir = output_dir.resolve()
    external_audit_path = external_audit_path.resolve()
    if output_dir.exists() and any(output_dir.iterdir()):
        raise ValueError("v26.167 output directory is not empty")
    output_dir.mkdir(parents=True, exist_ok=True)
    authorization = _external_authorization(external_audit_path)
    external_copy = output_dir / "external_joint_audit_input.txt"
    external_copy.write_bytes(external_audit_path.read_bytes())

    # Selection is deliberately complete before any v26.166 outcome-bearing file is loaded.
    (
        frame,
        prior,
        selected,
        selected_tasks,
        eligible_counts,
        historical_excluded_counts,
    ) = _select_fresh_sources(package_root=package_root)
    report166, protocol166, transition166, coverage166, terminal166 = _load_v166(package_root)
    source_replay = _source_replay(
        package_root=package_root,
        authorization=authorization,
    )
    legacy = _legacy_supersession(
        report=report166,
        protocol=protocol166,
        transition=transition166,
    )
    tier_boundary = _tier_boundary()
    protocol = _protocol()
    observability_floor = _observability_floor()
    boundary_selection = _boundary_selection()
    profile = _profile(package_root)
    capacity = _capacity_audit(
        package_root=package_root,
        frame=frame,
        prior=prior,
        selected=selected,
        eligible_counts=eligible_counts,
    )
    groups = _build_groups(
        selected=selected,
        selected_tasks=selected_tasks,
        profile=profile,
    )
    development = _group_catalog(
        partition=ObservationPartition.DEVELOPMENT,
        groups=tuple(item for item in groups if item.partition == ObservationPartition.DEVELOPMENT),
    )
    confirmation = _group_catalog(
        partition=ObservationPartition.CONFIRMATION,
        groups=tuple(
            item for item in groups if item.partition == ObservationPartition.CONFIRMATION
        ),
    )
    breadth = _breadth_catalog(protocol=protocol, groups=groups)
    freshness = _freshness_audit(
        capacity=capacity,
        groups=groups,
        prior=prior,
        historical_excluded_counts=historical_excluded_counts,
    )
    role_depth = _role_depth_audit(groups)
    terminal_matrix = _terminal_matrix(terminal166)
    coverage_gap = _coverage_gap_disposition(coverage166)

    preliminary_files: tuple[tuple[str, Any], ...] = (
        ("external_audit_authorization.json", authorization),
        ("source_replay_audit.json", source_replay),
        ("legacy_protocol_supersession.json", legacy),
        ("historical_tier_boundary_contract.json", tier_boundary),
        ("capability_observation_protocol.json", protocol),
        ("evidence_capacity_audit.json", capacity),
        ("capability_breadth_catalog.json", breadth),
        ("development_group_catalog.json", development),
        ("sealed_confirmation_group_catalog.json", confirmation),
        ("observability_floor_contract.json", observability_floor),
        ("boundary_selection_contract.json", boundary_selection),
        ("paired_freshness_audit.json", freshness),
        ("role_depth_preservation_audit.json", role_depth),
        ("terminal_endpoint_matrix.json", terminal_matrix),
        ("coverage_gap_prospective_disposition_catalog.json", coverage_gap),
    )
    for name, value in preliminary_files:
        _write(output_dir / name, value)
    exposure = _exposure_block(
        development=development,
        confirmation=confirmation,
        development_path=output_dir / "development_group_catalog.json",
        confirmation_path=output_dir / "sealed_confirmation_group_catalog.json",
    )
    _write(output_dir / "exposure_block_contract.json", exposure)
    static = static_audit.build_static_audit(
        protocol=protocol,
        breadth=breadth,
        development=development,
        confirmation=confirmation,
        observability_floor=observability_floor,
        exposure_block=exposure,
        freshness=freshness,
        role_depth=role_depth,
        terminal_matrix=terminal_matrix,
    )
    destructive = static_audit.build_destructive_audit()
    transition = _transition(
        authorization=authorization,
        static=static,
        exposure=exposure,
        boundary=boundary_selection,
    )
    _write(output_dir / "task_ladder_static_audit.json", static)
    _write(output_dir / "destructive_audit.json", destructive)
    _write(output_dir / "prospective_transition_contract.json", transition)
    report_values = {
        "run_id": RUN_ID,
        "authorization_id": authorization.authorization_id,
        "source_replay_audit_id": source_replay.audit_id,
        "legacy_supersession_id": legacy.decision_id,
        "historical_tier_boundary_contract_id": tier_boundary.contract_id,
        "protocol_id": protocol.protocol_id,
        "evidence_capacity_audit_id": capacity.audit_id,
        "breadth_catalog_id": breadth.catalog_id,
        "development_catalog_id": development.catalog_id,
        "sealed_confirmation_catalog_id": confirmation.catalog_id,
        "observability_floor_contract_id": observability_floor.contract_id,
        "boundary_selection_contract_id": boundary_selection.contract_id,
        "exposure_block_contract_id": exposure.contract_id,
        "paired_freshness_audit_id": freshness.audit_id,
        "role_depth_preservation_audit_id": role_depth.audit_id,
        "terminal_endpoint_matrix_id": terminal_matrix.matrix_id,
        "coverage_gap_disposition_catalog_id": coverage_gap.catalog_id,
        "static_audit_id": static.audit_id,
        "destructive_audit_id": destructive.audit_id,
        "transition_id": transition.transition_id,
        "detail_files": _detail_files(output_dir),
    }
    report = cast(
        models.CapabilityBreadthDepthStaticAuditReport,
        _make_model(
            models.CapabilityBreadthDepthStaticAuditReport,
            report_values,
            field="report_id",
            prefix="finance_v26_capability_breadth_depth_static_audit_report:",
        ),
    )
    _write(output_dir / "report.json", report)
    return models.BuildProducts(
        authorization=authorization,
        source_replay=source_replay,
        legacy_supersession=legacy,
        tier_boundary=tier_boundary,
        protocol=protocol,
        capacity=capacity,
        breadth=breadth,
        development=development,
        confirmation=confirmation,
        observability_floor=observability_floor,
        boundary_selection=boundary_selection,
        exposure_block=exposure,
        freshness=freshness,
        role_depth=role_depth,
        terminal_matrix=terminal_matrix,
        coverage_gap_disposition=coverage_gap,
        static_audit=static,
        destructive=destructive,
        transition=transition,
        report=report,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--external-audit-path", type=Path, required=True)
    args = parser.parse_args()
    package_root = _resolve_package_root(args.root)
    output_dir = args.output_dir or package_root / OUTPUT_DIR
    products = build(
        package_root=package_root,
        output_dir=output_dir,
        external_audit_path=args.external_audit_path,
    )
    print(
        json.dumps(
            {
                "report_id": products.report.report_id,
                "status": products.report.status,
                "next_stage": products.report.next_stage,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
