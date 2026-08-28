from __future__ import annotations

from copy import deepcopy
from typing import Any, cast

from trusted_synthesis.core.task.capability_observation import (
    CAPABILITY_FAMILY_ORDER,
    OBSERVATION_DEPTH_ORDER,
    CapabilityFamily,
    CapabilityObservationGroup,
    CapabilityObservationProtocol,
    ExposureBlockContract,
    ObservabilityFloorContract,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_capability_breadth_depth_task_synthesis_models as models,
)
from trusted_synthesis.hashing import canonical_hash

STATIC_GATE_NAMES = (
    "breadth",
    "confirmation_seal",
    "d0_necessity",
    "d0_nontriviality",
    "depth_delta",
    "exposure_block",
    "group_core_match",
    "max_skeleton_closure",
    "mechanism_necessity",
    "nuisance_stability",
    "paired_freshness",
    "public_witness",
    "resource_equality",
    "role_depth_preservation",
    "runtime_replay",
    "terminal_matrix",
    "tool_closure",
)

DESTRUCTIVE_MUTATIONS = (
    "all_paths_pooled",
    "answer_changed_within_group",
    "compiler_erases_depth",
    "compiler_intervention_applied",
    "current_27_cells_used_for_selection",
    "d0_mechanism_missing",
    "development_confirmation_overlap",
    "evidence_version_changed_within_group",
    "mapper_contribution_or_vtdo_called",
    "nuisance_distractor_changed",
    "nuisance_program_node_changed",
    "nuisance_tool_changed",
    "old_tier_mapped_to_depth",
    "partial_exposure_regeneration",
    "primary_load_nonmonotone",
    "result_based_rollout_edit",
    "result_based_task_text_edit",
    "source_role_signature_mismatch",
    "stale_hash_accepted",
    "threshold_tuned_after_results",
    "variants_counted_as_independent_tasks",
    "verifier_or_citation_changed_within_group",
)


def _make_model(
    model_type: type[models.FrozenModel],
    values: dict[str, Any],
    *,
    field: str,
    prefix: str,
) -> Any:
    provisional = model_type.model_construct(**{field: "pending"}, **values)
    return model_type(**{field: models.identity(provisional, field, prefix)}, **values)


def _d0_nontrivial(group: CapabilityObservationGroup) -> bool:
    d0 = group.variants[0].overlay
    active = tuple(item for item in d0.slots if item.active)
    if not active or not d0.d0_is_real_mechanism_observation:
        return False
    family = group.capability_family
    if family == CapabilityFamily.CONTEXT_CONDITIONED_ACTION:
        return (
            d0.primary_load["decision_slot_load"] >= 1
            and max(item.legal_candidate_count for item in active) >= 2
        )
    if family == CapabilityFamily.SEMANTIC_RECONCILIATION:
        return d0.primary_load["nonidentity_axis_load"] >= 1 and any(
            item.nonidentity_axes for item in active
        )
    if family == CapabilityFamily.FAILURE_RECOVERY:
        return d0.primary_load["typed_failure_load"] >= 1 and any(
            item.typed_failure_kind for item in active
        )
    return (
        d0.primary_load["completion_predicate_load"] >= 1
        and d0.primary_load["tempting_continuation_load"] >= 1
        and max(item.legal_candidate_count for item in active) >= 2
    )


def _d0_necessary(group: CapabilityObservationGroup) -> bool:
    d0 = group.variants[0].overlay
    ablated_total = sum(
        value
        for key, value in d0.primary_load.items()
        if key not in _d0_required_dimensions(group.capability_family)
    )
    return ablated_total < d0.primary_load_total and _d0_nontrivial(group)


def _d0_required_dimensions(family: CapabilityFamily) -> set[str]:
    return {
        CapabilityFamily.CONTEXT_CONDITIONED_ACTION: {
            "context_dependency_load",
            "decision_slot_load",
        },
        CapabilityFamily.SEMANTIC_RECONCILIATION: {
            "nonidentity_axis_load",
            "normalization_reference_consumption_load",
        },
        CapabilityFamily.FAILURE_RECOVERY: {
            "typed_failure_load",
            "dependency_depth_load",
        },
        CapabilityFamily.STATE_DEPENDENT_STOPPING: {
            "completion_predicate_load",
            "tempting_continuation_load",
        },
    }[family]


def _depth_monotone(group: CapabilityObservationGroup) -> bool:
    overlays = tuple(item.overlay for item in group.variants)
    if tuple(item.depth for item in overlays) != OBSERVATION_DEPTH_ORDER:
        return False
    dimensions = tuple(overlays[0].primary_load)
    return all(
        left.primary_load_total < right.primary_load_total
        and all(left.primary_load[key] <= right.primary_load[key] for key in dimensions)
        for left, right in zip(overlays, overlays[1:], strict=False)
    )


def _maximum_skeleton_closed(group: CapabilityObservationGroup) -> bool:
    slot_ids = tuple(item.slot_id for item in group.variants[-1].overlay.slots)
    return all(
        tuple(item.slot_id for item in variant.overlay.slots) == slot_ids
        and len(variant.overlay.slots) == 3
        and all(
            slot.active or (slot.legal_candidate_count == 1 and slot.inactive_mode is not None)
            for slot in variant.overlay.slots
        )
        for variant in group.variants
    )


def _public_witness_closed(group: CapabilityObservationGroup) -> bool:
    return all(
        variant.role_signature.public_witness_passed
        and all(slot.public_witness for slot in variant.overlay.slots)
        for variant in group.variants
    )


def _nuisance_stable(group: CapabilityObservationGroup) -> bool:
    expected = group.skeleton.nuisance_signature.signature_id
    return all(
        variant.role_signature.source_nuisance_signature_id == expected
        and variant.role_signature.role_nuisance_signature_id == expected
        and not any(variant.overlay.nuisance_delta.values())
        for variant in group.variants
    )


def _role_depth_preserved(group: CapabilityObservationGroup) -> bool:
    signatures = tuple(item.role_signature for item in group.variants)
    return (
        len({item.role_task_package_id for item in signatures}) == 4
        and all(item.depth_preserved and not item.compiler_erased_depth for item in signatures)
        and all(item.source_primary_load_hash == item.role_primary_load_hash for item in signatures)
        and all(item.public_overlay_hash == item.role_public_overlay_hash for item in signatures)
    )


def _group_checks(group: CapabilityObservationGroup) -> dict[str, bool]:
    signatures = tuple(item.role_signature for item in group.variants)
    return {
        "core_match": len({item.skeleton_id for item in group.variants}) == 1,
        "d0_nontrivial": _d0_nontrivial(group),
        "d0_necessary": _d0_necessary(group),
        "constructive_depth_monotone": _depth_monotone(group),
        "nuisance_stable": _nuisance_stable(group),
        "maximum_skeleton_closed": _maximum_skeleton_closed(group),
        "public_witness_passed": _public_witness_closed(group),
        "tool_closure_passed": all(item.tool_closure_passed for item in signatures),
        "runtime_replay_passed": all(item.runtime_replay_passed for item in signatures),
        "mechanism_necessity_passed": all(item.mechanism_necessity_passed for item in signatures),
        "role_depth_preserved": _role_depth_preserved(group),
    }


def _gate(
    name: str,
    *,
    passed: bool,
    checked_row_count: int,
    evidence: Any,
) -> models.StaticGateResult:
    if not passed:
        raise ValueError(f"v26.167 noncompensatory static Gate failed:{name}")
    return models.StaticGateResult(
        gate_name=cast(Any, name),
        checked_row_count=checked_row_count,
        evidence_hash=canonical_hash(evidence, prefix=f"capability_observation_gate:{name}:"),
    )


def build_static_audit(
    *,
    protocol: CapabilityObservationProtocol,
    breadth: models.CapabilityBreadthCatalog,
    development: models.CapabilityObservationGroupCatalog,
    confirmation: models.CapabilityObservationGroupCatalog,
    observability_floor: ObservabilityFloorContract,
    exposure_block: ExposureBlockContract,
    freshness: models.PairedFreshnessAudit,
    role_depth: models.RoleDepthPreservationAudit,
    terminal_matrix: models.TerminalEndpointMatrix,
) -> models.TaskLadderStaticAudit:
    groups = tuple(
        sorted((*development.groups, *confirmation.groups), key=lambda item: item.group_id)
    )
    if len(groups) != 16:
        raise ValueError("v26.167 static audit lacks sixteen matched groups")
    checks = {group.group_id: _group_checks(group) for group in groups}
    rows = []
    for group in groups:
        values = {
            "group_id": group.group_id,
            "capability_family": group.capability_family,
            "partition": group.partition,
            **checks[group.group_id],
        }
        rows.append(
            _make_model(
                models.GroupStaticAuditRow,
                values,
                field="row_id",
                prefix="finance_v26_capability_observation_group_static_audit:",
            )
        )
    all_checks = tuple(checks.values())
    resource_ids = {group.skeleton.nuisance_signature.resource_contract_id for group in groups}
    expected_dev = tuple(sorted(group.group_id for group in development.groups))
    expected_confirmation = tuple(sorted(group.group_id for group in confirmation.groups))
    gate_inputs: dict[str, tuple[bool, int, Any]] = {
        "breadth": (
            breadth.capability_families == CAPABILITY_FAMILY_ORDER
            and breadth.group_counts == {item: 4 for item in CAPABILITY_FAMILY_ORDER},
            4,
            breadth,
        ),
        "confirmation_seal": (
            exposure_block.confirmation_sealed_until_development_audit
            and not exposure_block.development_reader_may_access_confirmation_payload,
            8,
            exposure_block.sealed_confirmation_catalog_sha256,
        ),
        "d0_necessity": (
            all(item["d0_necessary"] for item in all_checks),
            16,
            observability_floor,
        ),
        "d0_nontriviality": (
            all(item["d0_nontrivial"] for item in all_checks),
            16,
            tuple(group.variants[0].overlay for group in groups),
        ),
        "depth_delta": (
            all(item["constructive_depth_monotone"] for item in all_checks),
            48,
            tuple(group.depth_delta_contract for group in groups),
        ),
        "exposure_block": (
            exposure_block.development_group_ids == expected_dev
            and exposure_block.confirmation_group_ids == expected_confirmation,
            16,
            exposure_block,
        ),
        "group_core_match": (
            all(item["core_match"] for item in all_checks),
            16,
            tuple(group.skeleton.skeleton_id for group in groups),
        ),
        "max_skeleton_closure": (
            all(item["maximum_skeleton_closed"] for item in all_checks),
            64,
            tuple(group.group_hash for group in groups),
        ),
        "mechanism_necessity": (
            all(item["mechanism_necessity_passed"] for item in all_checks),
            64,
            tuple(item.signature_id for item in role_depth.signatures),
        ),
        "nuisance_stability": (
            all(item["nuisance_stable"] for item in all_checks),
            64,
            tuple(group.skeleton.nuisance_signature.signature_id for group in groups),
        ),
        "paired_freshness": (
            freshness.passed and freshness.cross_group_channel_overlap_count == 0,
            16,
            freshness,
        ),
        "public_witness": (
            all(item["public_witness_passed"] for item in all_checks),
            64,
            tuple(group.group_hash for group in groups),
        ),
        "resource_equality": (
            len(resource_ids) == 1,
            64,
            tuple(sorted(resource_ids)),
        ),
        "role_depth_preservation": (
            role_depth.passed
            and role_depth.source_role_signature_match_count == 64
            and all(item["role_depth_preserved"] for item in all_checks),
            64,
            role_depth,
        ),
        "runtime_replay": (
            all(item["runtime_replay_passed"] for item in all_checks),
            64,
            tuple(item.signature_id for item in role_depth.signatures),
        ),
        "terminal_matrix": (
            len(terminal_matrix.cases) == 8,
            8,
            terminal_matrix,
        ),
        "tool_closure": (
            all(item["tool_closure_passed"] for item in all_checks),
            64,
            tuple(item.role_environment_manifest_id for item in role_depth.signatures),
        ),
    }
    if tuple(sorted(gate_inputs)) != STATIC_GATE_NAMES:
        raise ValueError("v26.167 static Gate language changed")
    gates = tuple(
        _gate(
            name,
            passed=gate_inputs[name][0],
            checked_row_count=gate_inputs[name][1],
            evidence=gate_inputs[name][2],
        )
        for name in STATIC_GATE_NAMES
    )
    values = {
        "protocol_id": protocol.protocol_id,
        "breadth_catalog_id": breadth.catalog_id,
        "group_rows": tuple(rows),
        "gates": gates,
    }
    return _make_model(
        models.TaskLadderStaticAudit,
        values,
        field="audit_id",
        prefix="finance_v26_capability_observation_static_audit:",
    )


def _destructive_control() -> dict[str, Any]:
    return {
        "all_paths_pooled": False,
        "answer_hashes": ["answer"] * 4,
        "compiler_erased_depth": False,
        "compiler_intervention_count": 0,
        "current_27_cells_used": False,
        "d0_mechanism_present": True,
        "development_confirmation_overlap": 0,
        "evidence_version_hashes": ["evidence"] * 4,
        "mapper_calls": 0,
        "contribution_rows": 0,
        "vtdo_rows": 0,
        "distractor_signature": ["distractor"] * 4,
        "program_node_signature": ["program"] * 4,
        "tool_signature": ["tools"] * 4,
        "old_tier_mapped_to_depth": False,
        "partial_exposure_regeneration": False,
        "primary_totals": [2, 4, 7, 11],
        "rollouts_edited_after_results": False,
        "task_text_edited_after_results": False,
        "source_role_hash_match": True,
        "stored_hash": "current",
        "computed_hash": "current",
        "threshold_tuned_after_results": False,
        "primary_unit": "matched_group",
        "verifier_hashes": ["verifier"] * 4,
    }


def _control_failure_codes(value: dict[str, Any]) -> set[str]:
    failures: set[str] = set()
    if value["all_paths_pooled"]:
        failures.add("all_path_pooling_forbidden")
    for key, code in (
        ("answer_hashes", "answer_core_changed"),
        ("evidence_version_hashes", "evidence_version_core_changed"),
        ("distractor_signature", "nuisance_distractor_changed"),
        ("program_node_signature", "nuisance_program_changed"),
        ("tool_signature", "nuisance_tool_changed"),
        ("verifier_hashes", "verifier_or_citation_core_changed"),
    ):
        if len(set(value[key])) != 1:
            failures.add(code)
    if value["compiler_erased_depth"]:
        failures.add("role_depth_erased")
    if value["compiler_intervention_count"]:
        failures.add("compiler_intervention_forbidden")
    if value["current_27_cells_used"]:
        failures.add("outcome_selected_frame_forbidden")
    if not value["d0_mechanism_present"]:
        failures.add("d0_mechanism_absent")
    if value["development_confirmation_overlap"]:
        failures.add("exposure_partition_overlap")
    if any(value[key] for key in ("mapper_calls", "contribution_rows", "vtdo_rows")):
        failures.add("premature_vtdo_pipeline_use")
    if value["old_tier_mapped_to_depth"]:
        failures.add("historical_tier_depth_alias_forbidden")
    if value["partial_exposure_regeneration"]:
        failures.add("partial_group_regeneration_forbidden")
    totals = value["primary_totals"]
    if any(left >= right for left, right in zip(totals, totals[1:], strict=False)):
        failures.add("primary_load_not_constructively_monotone")
    if value["rollouts_edited_after_results"]:
        failures.add("result_based_rollout_edit_forbidden")
    if value["task_text_edited_after_results"]:
        failures.add("result_based_task_edit_forbidden")
    if not value["source_role_hash_match"]:
        failures.add("source_role_signature_mismatch")
    if value["stored_hash"] != value["computed_hash"]:
        failures.add("stale_hash_rejected")
    if value["threshold_tuned_after_results"]:
        failures.add("postresult_threshold_tuning_forbidden")
    if value["primary_unit"] != "matched_group":
        failures.add("variant_pseudoreplication_forbidden")
    return failures


def build_destructive_audit() -> models.DestructiveAudit:
    mutation_specs: dict[str, tuple[str, Any]] = {
        "all_paths_pooled": ("all_paths_pooled", True),
        "answer_changed_within_group": ("answer_hashes", ["answer", "changed"] * 2),
        "compiler_erases_depth": ("compiler_erased_depth", True),
        "compiler_intervention_applied": ("compiler_intervention_count", 1),
        "current_27_cells_used_for_selection": ("current_27_cells_used", True),
        "d0_mechanism_missing": ("d0_mechanism_present", False),
        "development_confirmation_overlap": ("development_confirmation_overlap", 1),
        "evidence_version_changed_within_group": (
            "evidence_version_hashes",
            ["evidence", "changed"] * 2,
        ),
        "mapper_contribution_or_vtdo_called": ("mapper_calls", 1),
        "nuisance_distractor_changed": (
            "distractor_signature",
            ["distractor", "changed"] * 2,
        ),
        "nuisance_program_node_changed": (
            "program_node_signature",
            ["program", "changed"] * 2,
        ),
        "nuisance_tool_changed": ("tool_signature", ["tools", "changed"] * 2),
        "old_tier_mapped_to_depth": ("old_tier_mapped_to_depth", True),
        "partial_exposure_regeneration": ("partial_exposure_regeneration", True),
        "primary_load_nonmonotone": ("primary_totals", [2, 4, 4, 11]),
        "result_based_rollout_edit": ("rollouts_edited_after_results", True),
        "result_based_task_text_edit": ("task_text_edited_after_results", True),
        "source_role_signature_mismatch": ("source_role_hash_match", False),
        "stale_hash_accepted": ("computed_hash", "changed"),
        "threshold_tuned_after_results": ("threshold_tuned_after_results", True),
        "variants_counted_as_independent_tasks": ("primary_unit", "variant"),
        "verifier_or_citation_changed_within_group": (
            "verifier_hashes",
            ["verifier", "changed"] * 2,
        ),
    }
    if tuple(sorted(mutation_specs)) != DESTRUCTIVE_MUTATIONS:
        raise ValueError("v26.167 destructive mutation language changed")
    baseline = _destructive_control()
    if _control_failure_codes(baseline):
        raise ValueError("v26.167 destructive baseline is invalid")
    results = []
    for name in DESTRUCTIVE_MUTATIONS:
        field, replacement = mutation_specs[name]
        mutated = deepcopy(baseline)
        mutated[field] = replacement
        failures = _control_failure_codes(mutated)
        if not failures:
            raise ValueError(f"v26.167 destructive mutation escaped:{name}")
        values = {
            "mutation_name": name,
            "failure_code": sorted(failures)[0],
        }
        results.append(
            _make_model(
                models.MutationResult,
                values,
                field="mutation_id",
                prefix="finance_v26_capability_observation_destructive_mutation:",
            )
        )
    audit_values: dict[str, Any] = {"mutations": tuple(results)}
    return _make_model(
        models.DestructiveAudit,
        audit_values,
        field="audit_id",
        prefix="finance_v26_capability_observation_destructive_audit:",
    )
