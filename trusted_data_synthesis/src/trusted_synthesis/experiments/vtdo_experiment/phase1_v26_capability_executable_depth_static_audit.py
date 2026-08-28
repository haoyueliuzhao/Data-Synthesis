from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Sequence
from typing import Any, cast

from pydantic import BaseModel

from trusted_synthesis.core.task.capability_observation import (
    CapabilityFamily,
    ObservationPartition,
)
from trusted_synthesis.core.task.executable_capability_depth import (
    DEPTH_VERIFIER_CHECKS,
    TARGET_LOAD_DIMENSIONS,
    CapabilityDepthRuntime,
    CapabilityDepthVerifierContract,
    CapabilityDepthWitnessContract,
    CompiledTargetLoad,
    DepthActionKind,
    ExecutableCapabilityDepthGraph,
    ExecutableCapabilityDepthWitness,
    MechanismCounterfactualKind,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_capability_executable_depth_rematerialization_models as models,
)
from trusted_synthesis.hashing import canonical_hash


def _make_model(
    model_type: type[BaseModel],
    values: dict[str, Any],
    *,
    field: str,
    prefix: str,
) -> Any:
    provisional = model_type.model_construct(**{field: "pending"}, **values)
    return model_type(**{field: models.identity(provisional, field, prefix)}, **values)


def compile_depth_witness(
    graph: ExecutableCapabilityDepthGraph,
    witness_contract: CapabilityDepthWitnessContract,
    verifier_contract: CapabilityDepthVerifierContract,
) -> ExecutableCapabilityDepthWitness:
    if (
        witness_contract.graph_id != graph.graph_id
        or witness_contract.required_event_multiplicities != graph.required_event_multiplicities
        or verifier_contract.witness_contract_id != witness_contract.contract_id
    ):
        raise ValueError("depth Witness compiler received inconsistent contracts")
    runtime = CapabilityDepthRuntime(graph)
    reached = [runtime.state_id]
    while not runtime.state.terminal:
        candidate_id = runtime.state.reference_candidate_id
        if candidate_id is None:
            raise ValueError("depth Witness reference path ended before terminal")
        observation = runtime.execute(candidate_id)
        reached.append(observation.next_state_id)
    observations = tuple(runtime.observations)
    event_counts = dict(
        sorted(
            Counter(
                event for observation in observations for event in observation.emitted_event_types
            ).items()
        )
    )
    emitted_refs = tuple(
        sorted(
            {
                reference
                for observation in observations
                for reference in observation.emitted_reference_ids
            }
        )
    )
    consumed_refs = tuple(
        sorted(
            {
                reference
                for observation in observations
                for reference in observation.consumed_reference_ids
            }
        )
    )
    state_by_id = {item.state_id: item for item in graph.states}
    candidate_by_id = {item.candidate_id: item for item in graph.candidates}
    transition_by_id = {item.transition_id: item for item in graph.transitions}
    checks = {
        "answer_ready_only_after_reference_path": (
            runtime.state_id == graph.success_terminal_state_id
            and runtime.state.answer_ready
            and all(not state_by_id[item].answer_ready for item in reached[:-1])
        ),
        "candidate_sets_exact": all(
            observation.visible_candidate_ids == state_by_id[observation.state_id].candidate_ids
            for observation in observations
        ),
        "event_multiplicities_exact": event_counts
        == witness_contract.required_event_multiplicities,
        "normalization_references_consumed": set(emitted_refs) <= set(consumed_refs),
        "reference_path_complete": reached[0] == graph.initial_state_id
        and reached[-1] == graph.success_terminal_state_id,
        "state_transitions_exact": all(
            transition_by_id[observation.transition_id].to_state_id == observation.next_state_id
            for observation in observations
        ),
        "target_decisions_model_owned": all(
            candidate_by_id[observation.chosen_candidate_id].model_owned
            for observation in observations
        ),
        "typed_failures_recovered": event_counts.get("typed_failure_observed", 0)
        == event_counts.get("recovery_succeeded", 0),
        "verified_stop_has_no_later_action": (
            graph.capability_family != CapabilityFamily.STATE_DEPENDENT_STOPPING
            or (
                event_counts.get("completion_verified", 0) >= 1
                and event_counts.get("stopped_after_completion", 0) == 1
                and runtime.state.terminal
            )
        ),
    }
    if set(checks) != set(DEPTH_VERIFIER_CHECKS) or not all(checks.values()):
        failed = tuple(sorted(key for key, value in checks.items() if not value))
        raise ValueError(f"depth Witness failed:{failed}")
    values = {
        "graph_id": graph.graph_id,
        "witness_contract_id": witness_contract.contract_id,
        "verifier_contract_id": verifier_contract.contract_id,
        "observations": observations,
        "reached_state_ids": tuple(reached),
        "event_multiplicities": event_counts,
        "emitted_reference_ids": emitted_refs,
        "consumed_reference_ids": consumed_refs,
        "final_state_id": runtime.state_id,
        "checks": checks,
    }
    return cast(
        ExecutableCapabilityDepthWitness,
        _make_model(
            ExecutableCapabilityDepthWitness,
            values,
            field="witness_id",
            prefix="executable_capability_depth_witness:",
        ),
    )


def compute_target_load(
    graph: ExecutableCapabilityDepthGraph,
    witness: ExecutableCapabilityDepthWitness,
) -> CompiledTargetLoad:
    candidates_by_state: dict[str, list[Any]] = {}
    for candidate in graph.candidates:
        candidates_by_state.setdefault(candidate.state_id, []).append(candidate)
    active = set(graph.active_slot_ids)
    active_states = tuple(
        item for item in graph.states if item.slot_id in active and not item.terminal
    )
    events = witness.event_multiplicities
    if graph.capability_family == CapabilityFamily.CONTEXT_CONDITIONED_ACTION:
        decision_states = tuple(item for item in active_states if item.phase == "context_decision")
        dimensions = {
            "candidate_ambiguity": sum(
                max(0, len(candidates_by_state[item.state_id]) - 1) for item in decision_states
            ),
            "context_dependency_edges": max(0, len(decision_states) - 1),
            "delayed_public_updates": sum(
                transition.public_update_delayed for transition in graph.transitions
            ),
            "irreversible_choices": events.get("context_irreversible_choice", 0),
            "model_owned_decision_states": len(decision_states),
        }
    elif graph.capability_family == CapabilityFamily.SEMANTIC_RECONCILIATION:
        normalization_states = tuple(item for item in active_states if item.phase == "normalize")
        reference_candidates = {
            item.reference_candidate_id
            for item in normalization_states
            if item.reference_candidate_id
        }
        dimensions = {
            "downstream_consumption_edges": sum(
                len(item.consumed_reference_ids) for item in witness.observations
            ),
            "nonidentity_axes": sum(
                len(item.nonidentity_axes)
                for item in graph.candidates
                if item.candidate_id in reference_candidates
            ),
            "normalization_states": len(normalization_states),
            "normalized_reference_consumptions": events.get("normalization_reference_consumed", 0),
            "raw_bypass_candidates": sum(
                item.action_kind == DepthActionKind.TARGET_BYPASS
                for item in graph.candidates
                if item.state_id in {state.state_id for state in active_states}
            ),
        }
    elif graph.capability_family == CapabilityFamily.FAILURE_RECOVERY:
        recovery_states = tuple(item for item in active_states if item.phase == "recover")
        dimensions = {
            "failure_type_diversity": len(
                {
                    item.failure_type
                    for item in graph.candidates
                    if item.failure_type is not None
                    and item.state_id in {state.state_id for state in active_states}
                }
            ),
            "recovery_branching": sum(
                max(0, len(candidates_by_state[item.state_id]) - 1) for item in recovery_states
            ),
            "recovery_dependency_depth": len(graph.active_slot_ids),
            "recovery_successes": events.get("recovery_succeeded", 0),
            "typed_failures": events.get("typed_failure_observed", 0),
        }
    else:
        checkpoint_states = tuple(item for item in active_states if item.phase == "checkpoint")
        dimensions = {
            "completion_predicates": events.get("completion_predicate_evaluated", 0),
            "delayed_readiness_states": events.get("readiness_delayed", 0),
            "near_terminal_checkpoints": len(checkpoint_states),
            "tempting_continuations": sum(
                item.action_kind == DepthActionKind.TEMPTING_CONTINUATION
                for item in graph.candidates
            ),
            "verification_stop_separations": events.get("completion_verified", 0),
        }
    if set(dimensions) != set(TARGET_LOAD_DIMENSIONS[graph.capability_family]):
        raise ValueError("compiled target load dimensions are incomplete")
    values = {
        "graph_id": graph.graph_id,
        "witness_id": witness.witness_id,
        "capability_family": graph.capability_family,
        "depth": graph.depth,
        "dimensions": dimensions,
        "total": sum(dimensions.values()),
    }
    return cast(
        CompiledTargetLoad,
        _make_model(
            CompiledTargetLoad,
            values,
            field="load_id",
            prefix="compiled_capability_target_load:",
        ),
    )


def build_counterfactual_replays(
    packages: Sequence[models.ExecutableDepthPackage],
) -> models.MechanismNecessityCatalog:
    rows: list[models.MechanismCounterfactualReplay] = []
    for package in packages:
        graph = package.graph
        candidate_by_id = {item.candidate_id: item for item in graph.candidates}
        first_target_state = next(
            state
            for state in graph.states
            if not state.terminal
            and any(candidate_by_id[item].target_capability_action for item in state.candidate_ids)
            and any(not candidate_by_id[item].reference_action for item in state.candidate_ids)
        )
        target_id = cast(str, first_target_state.reference_candidate_id)

        graph_payload = graph.model_dump(mode="python")
        deleted = dict(graph_payload)
        deleted["candidates"] = tuple(
            item for item in graph_payload["candidates"] if item["candidate_id"] != target_id
        )
        deleted["transitions"] = tuple(
            item for item in graph_payload["transitions"] if item["candidate_id"] != target_id
        )
        deleted_states = []
        for item in graph_payload["states"]:
            value = dict(item)
            if value["state_id"] == first_target_state.state_id:
                value["candidate_ids"] = tuple(
                    candidate for candidate in value["candidate_ids"] if candidate != target_id
                )
            deleted_states.append(value)
        deleted["states"] = tuple(deleted_states)
        try:
            ExecutableCapabilityDepthGraph.model_validate(deleted)
        except (TypeError, ValueError):
            delete_failure = "production_graph_rejected_missing_reference_action"
        else:
            raise ValueError("target-action deletion escaped production graph validation")
        delete_values = {
            "package_id": package.package_id,
            "graph_id": graph.graph_id,
            "baseline_witness_id": package.depth_witness.witness_id,
            "counterfactual_kind": MechanismCounterfactualKind.DELETE_TARGET_ACTION,
            "mutation_target_candidate_id": target_id,
            "observed_failure_code": delete_failure,
        }
        rows.append(
            _make_model(
                models.MechanismCounterfactualReplay,
                delete_values,
                field="replay_id",
                prefix="finance_v26_executable_depth_counterfactual_replay:",
            )
        )

        bypass_id = next(
            item
            for item in first_target_state.candidate_ids
            if item != target_id and candidate_by_id[item].target_capability_action
        )
        runtime = CapabilityDepthRuntime(graph)
        while runtime.state_id != first_target_state.state_id:
            reference = runtime.state.reference_candidate_id
            if reference is None:
                raise ValueError("counterfactual cannot reach target State")
            runtime.execute(reference)
        runtime.execute(bypass_id)
        while not runtime.state.terminal:
            reference = runtime.state.reference_candidate_id
            if reference is None:
                raise ValueError("counterfactual path cannot continue")
            runtime.execute(reference)
        counterfactual_events = Counter(
            event
            for observation in runtime.observations
            for event in observation.emitted_event_types
        )
        if dict(sorted(counterfactual_events.items())) == graph.required_event_multiplicities:
            raise ValueError("target bypass retained exact mechanism events")
        bypass_values = {
            "package_id": package.package_id,
            "graph_id": graph.graph_id,
            "baseline_witness_id": package.depth_witness.witness_id,
            "counterfactual_kind": MechanismCounterfactualKind.BYPASS_TARGET_ACTION,
            "mutation_target_candidate_id": bypass_id,
            "observed_failure_code": "runtime_trace_missing_target_mechanism_event",
        }
        rows.append(
            _make_model(
                models.MechanismCounterfactualReplay,
                bypass_values,
                field="replay_id",
                prefix="finance_v26_executable_depth_counterfactual_replay:",
            )
        )
    values = {"replays": tuple(sorted(rows, key=lambda item: item.replay_id))}
    return cast(
        models.MechanismNecessityCatalog,
        _make_model(
            models.MechanismNecessityCatalog,
            values,
            field="catalog_id",
            prefix="finance_v26_executable_depth_mechanism_necessity_catalog:",
        ),
    )


def build_static_audit(
    *,
    packages: Sequence[models.ExecutableDepthPackage],
    development_groups: Sequence[models.ExecutableDepthGroup],
    confirmation_groups: Sequence[models.ExecutableDepthGroup],
    source_capacity: models.ExecutableDepthSourceCapacityAudit,
    v167_defect: models.V167ExecutableDepthDefectAudit,
    source_root: models.TransitiveSourceRoot,
    receipt: models.SealedConfirmationReceipt,
    noninterference: models.TargetCapabilityNoninterferenceAudit,
    boundary_totality: models.BoundaryAlgorithmTotalityAudit,
    necessity: models.MechanismNecessityCatalog,
    nuisance_audit: models.NuisanceRecomputationAudit,
) -> models.ExecutableDepthStaticAudit:
    package_count = len(packages)
    graph_distinct = sum(
        len({item.graph.graph_id for item in group.packages}) == 4
        for group in (*development_groups, *confirmation_groups)
    )
    candidate_distinct = sum(
        len({item.signature.candidate_set_hash for item in group.packages}) == 4
        for group in (*development_groups, *confirmation_groups)
    )
    transition_distinct = sum(
        len({item.signature.transition_hash for item in group.packages}) == 4
        for group in (*development_groups, *confirmation_groups)
    )
    load_monotone = sum(
        all(
            left.target_load.total < right.target_load.total
            for left, right in zip(group.packages, group.packages[1:], strict=False)
        )
        for group in (*development_groups, *confirmation_groups)
    )
    d0_real = sum(
        group.packages[0].target_load.total > 0 and bool(group.packages[0].graph.active_slot_ids)
        for group in (*development_groups, *confirmation_groups)
    )
    reconciliation = tuple(
        item
        for item in packages
        if item.capability_family == CapabilityFamily.SEMANTIC_RECONCILIATION
    )
    reconciliation_consumed = sum(
        set(item.depth_witness.emitted_reference_ids)
        <= set(item.depth_witness.consumed_reference_ids)
        and item.depth_witness.event_multiplicities.get("normalization_reference_consumed", 0)
        == sum(
            len(observation.consumed_reference_ids)
            for observation in item.depth_witness.observations
        )
        for item in reconciliation
    )
    gates: dict[models.StaticGateName, tuple[int, int, Any]] = {
        "boundary_algorithm_totality": (
            512,
            boundary_totality.uniquely_classified_pattern_count,
            boundary_totality.audit_id,
        ),
        "computed_nuisance_stability": (
            package_count,
            nuisance_audit.within_group_exact_match_count,
            nuisance_audit.audit_id,
        ),
        "computed_target_load_monotonicity": (
            16,
            load_monotone,
            tuple(item.target_load.load_id for item in packages),
        ),
        "confirmation_access_isolation": (
            1,
            int(receipt.development_payload_access_count == 0),
            receipt.receipt_id,
        ),
        "d0_real_mechanism": (
            16,
            d0_real,
            tuple(
                item.packages[0].graph.graph_id
                for item in (*development_groups, *confirmation_groups)
            ),
        ),
        "development_floor_envelope": (
            32,
            nuisance_audit.development_floor_envelope_pass_count,
            nuisance_audit.envelope_contract_id,
        ),
        "executable_candidate_delta": (
            16,
            candidate_distinct,
            tuple(item.signature.candidate_set_hash for item in packages),
        ),
        "executable_graph_delta": (
            16,
            graph_distinct,
            tuple(item.graph.graph_id for item in packages),
        ),
        "executable_transition_delta": (
            16,
            transition_distinct,
            tuple(item.signature.transition_hash for item in packages),
        ),
        "fixed_condition_noninterference": (
            32,
            noninterference.candidate_set_match_count,
            noninterference.audit_id,
        ),
        "historical_v167_freeze": (
            1,
            int(v167_defect.historical_report_rewritten is False),
            v167_defect.audit_id,
        ),
        "low_nuisance_operational_witness": (
            64,
            sum(item.variant_operational_witness.full_validity_passed for item in packages),
            tuple(item.variant_operational_witness.witness_id for item in packages),
        ),
        "mechanism_event_multiplicity": (
            64,
            sum(
                item.depth_witness.event_multiplicities == item.graph.required_event_multiplicities
                for item in packages
            ),
            tuple(item.depth_witness.witness_id for item in packages),
        ),
        "mechanism_necessity": (64, necessity.necessity_pass_count, necessity.catalog_id),
        "provider_zero": (1, 1, {"provider": 0, "stage_two": 0, "gpu": 0}),
        "public_witness": (
            64,
            sum(item.depth_witness.full_validity_passed for item in packages),
            tuple(item.depth_witness.witness_id for item in packages),
        ),
        "reconciliation_reference_consumption": (
            16,
            reconciliation_consumed,
            tuple(item.depth_witness.witness_id for item in reconciliation),
        ),
        "source_capacity_and_freshness": (
            16,
            source_capacity.selected_group_count,
            source_capacity.audit_id,
        ),
        "stale_preflight_block": (
            1,
            int(v167_defect.stale_development_preflight_authorization_blocked),
            v167_defect.audit_id,
        ),
        "task_verifier": (
            64,
            sum(item.variant_program_verification.passed for item in packages),
            tuple(
                canonical_hash(
                    item.variant_program_verification.model_dump(mode="json"),
                    prefix="variant_task_program_verification:",
                )
                for item in packages
            ),
        ),
        "transitive_source_closure": (
            source_root.file_count,
            source_root.file_count,
            source_root.root_id,
        ),
        "typed_runtime_terminal_policy": (
            64,
            sum(
                item.graph.success_terminal_state_id == item.depth_witness.final_state_id
                for item in packages
            ),
            tuple(item.graph.success_terminal_state_id for item in packages),
        ),
    }
    rows = tuple(
        models.StaticGateResult(
            gate_name=name,
            denominator=denominator,
            numerator=numerator,
            evidence_hash=canonical_hash(evidence, prefix=f"v26_168_gate_{name}:"),
        )
        for name, (denominator, numerator, evidence) in sorted(gates.items())
    )
    values = {
        "gates": rows,
        "public_witness_pass_count": sum(
            item.depth_witness.full_validity_passed for item in packages
        ),
        "task_verifier_pass_count": sum(
            item.variant_program_verification.passed for item in packages
        ),
        "mechanism_necessity_pass_count": necessity.necessity_pass_count,
        "reconciliation_consumption_pass_count": reconciliation_consumed,
    }
    return cast(
        models.ExecutableDepthStaticAudit,
        _make_model(
            models.ExecutableDepthStaticAudit,
            values,
            field="audit_id",
            prefix="finance_v26_executable_depth_static_audit:",
        ),
    )


def _revalidate(value: BaseModel, transform: Callable[[dict[str, Any]], None]) -> None:
    payload = value.model_dump(mode="python")
    transform(payload)
    type(value).model_validate(payload)


def build_production_destructive_audit(
    *,
    sample_package: models.ExecutableDepthPackage,
    development_catalog: models.ExecutableDepthCatalog,
    receipt: models.SealedConfirmationReceipt,
    source_root: models.TransitiveSourceRoot,
    boundary_contract: Any,
    sample_core: models.LowNuisanceFinanceCore,
) -> models.ProductionDestructiveAudit:
    graph = sample_package.graph
    first_state = next(item for item in graph.states if not item.terminal)
    first_candidate = cast(str, first_state.reference_candidate_id)
    bypass_candidate = next(item for item in first_state.candidate_ids if item != first_candidate)

    def candidate_deleted(payload: dict[str, Any]) -> None:
        payload["candidates"] = tuple(
            item for item in payload["candidates"] if item["candidate_id"] != first_candidate
        )

    def candidate_rebound(payload: dict[str, Any]) -> None:
        payload["candidates"][0]["state_id"] = "missing_state"

    def transition_missing(payload: dict[str, Any]) -> None:
        payload["transitions"][0]["to_state_id"] = "missing_state"

    def reference_changed(payload: dict[str, Any]) -> None:
        payload["states"][0]["reference_candidate_id"] = bypass_candidate

    def role_task_package_changed(payload: dict[str, Any]) -> None:
        payload["operational_record"]["task_package"]["package_id"] = "changed"

    def task_program_output_missing(payload: dict[str, Any]) -> None:
        payload["operational_record"]["task_package"]["task"]["oracle"]["task_program"][
            "output_node_id"
        ] = "missing_node"

    def task_verifier_binding_changed(payload: dict[str, Any]) -> None:
        payload["operational_record"]["task_package"]["verifier_binding"][
            "source_program_dag_hash"
        ] = "0" * 64

    def operational_witness_step_deleted(payload: dict[str, Any]) -> None:
        payload["operational_witness"]["steps"] = payload["operational_witness"]["steps"][1:]

    def depth_witness_event_changed(payload: dict[str, Any]) -> None:
        payload["event_multiplicities"]["injected_event"] = 1

    def runtime_observation_candidate_changed(payload: dict[str, Any]) -> None:
        payload["chosen_candidate_id"] = "not_visible"

    def runtime_bypass() -> None:
        runtime = CapabilityDepthRuntime(graph)
        runtime.execute(bypass_candidate)
        observed = Counter(
            event for item in runtime.observations for event in item.emitted_event_types
        )
        if dict(sorted(observed.items())) != graph.required_event_multiplicities:
            raise ValueError("runtime_trace_missing_target_mechanism_event")

    def runtime_nonvisible() -> None:
        CapabilityDepthRuntime(graph).execute("not_visible")

    def runtime_postterminal() -> None:
        runtime = CapabilityDepthRuntime(graph)
        while not runtime.state.terminal:
            runtime.execute(cast(str, runtime.state.reference_candidate_id))
        runtime.execute(first_candidate)

    first_observation = sample_package.depth_witness.observations[0]

    cases: dict[
        str,
        tuple[models.ProductionMutationTarget, Callable[[], None]],
    ] = {
        "boundary_depth_order_changed": (
            "boundary_contract",
            lambda: _revalidate(
                boundary_contract,
                lambda value: value.update(depth_order=tuple(reversed(value["depth_order"]))),
            ),
        ),
        "boundary_threshold_changed": (
            "boundary_contract",
            lambda: _revalidate(
                boundary_contract, lambda value: value.update(development_threshold=3)
            ),
        ),
        "catalog_confirmation_group_inserted": (
            "development_catalog",
            lambda: _revalidate(
                development_catalog,
                lambda value: value["groups"][0].update(
                    partition=ObservationPartition.CONFIRMATION
                ),
            ),
        ),
        "catalog_core_deleted": (
            "development_catalog",
            lambda: _revalidate(
                development_catalog,
                lambda value: value.update(finance_cores=value["finance_cores"][1:]),
            ),
        ),
        "core_environment_changed": (
            "finance_core",
            lambda: _revalidate(
                sample_core, lambda value: value["environment"].update(manifest_id="changed")
            ),
        ),
        "core_evidence_count_changed": (
            "finance_core",
            lambda: _revalidate(sample_core, lambda value: value.update(evidence_count=3)),
        ),
        "graph_active_slot_deleted": (
            "executable_graph",
            lambda: _revalidate(graph, lambda value: value.update(active_slot_ids=())),
        ),
        "graph_candidate_deleted": (
            "executable_graph",
            lambda: _revalidate(graph, candidate_deleted),
        ),
        "graph_candidate_state_rebound": (
            "executable_graph",
            lambda: _revalidate(graph, candidate_rebound),
        ),
        "graph_depth_relabelled": (
            "executable_graph",
            lambda: _revalidate(graph, lambda value: value.update(depth="d3_stress")),
        ),
        "graph_event_requirement_changed": (
            "executable_graph",
            lambda: _revalidate(
                graph, lambda value: value["required_event_multiplicities"].update(injected=1)
            ),
        ),
        "graph_finance_core_rebound": (
            "executable_graph",
            lambda: _revalidate(graph, lambda value: value.update(finance_core_id="changed")),
        ),
        "graph_reference_candidate_changed": (
            "executable_graph",
            lambda: _revalidate(graph, reference_changed),
        ),
        "graph_transition_target_missing": (
            "executable_graph",
            lambda: _revalidate(graph, transition_missing),
        ),
        "nuisance_evidence_count_changed": (
            "nuisance_measurement",
            lambda: _revalidate(
                sample_package.nuisance, lambda value: value.update(evidence_count=3)
            ),
        ),
        "nuisance_prompt_bytes_changed": (
            "nuisance_measurement",
            lambda: _revalidate(
                sample_package.nuisance,
                lambda value: value.update(prompt_bytes=value["prompt_bytes"] + 1),
            ),
        ),
        "prompt_candidate_hash_changed": (
            "prompt_binding",
            lambda: _revalidate(
                sample_package.prompt_binding,
                lambda value: value.update(target_capability_candidate_hash="changed"),
            ),
        ),
        "prompt_condition_rebound": (
            "prompt_binding",
            lambda: _revalidate(
                sample_package.prompt_binding,
                lambda value: value.update(fixed_generation_condition_id="changed"),
            ),
        ),
        "depth_witness_event_count_changed": (
            "depth_witness",
            lambda: _revalidate(sample_package.depth_witness, depth_witness_event_changed),
        ),
        "operational_witness_step_deleted": (
            "operational_witness",
            lambda: _revalidate(sample_core, operational_witness_step_deleted),
        ),
        "role_task_package_identity_changed": (
            "operational_task_package",
            lambda: _revalidate(sample_core, role_task_package_changed),
        ),
        "runtime_observation_candidate_nonvisible": (
            "runtime_observation",
            lambda: _revalidate(first_observation, runtime_observation_candidate_changed),
        ),
        "task_program_output_node_missing": (
            "task_program",
            lambda: _revalidate(sample_core, task_program_output_missing),
        ),
        "task_verifier_binding_source_hash_changed": (
            "task_verifier_binding",
            lambda: _revalidate(sample_core, task_verifier_binding_changed),
        ),
        "runtime_bypass_target": ("runtime_trace", runtime_bypass),
        "runtime_nonvisible_candidate": ("runtime_trace", runtime_nonvisible),
        "runtime_postterminal_action": ("runtime_trace", runtime_postterminal),
        "sealed_payload_path_disclosed": (
            "sealed_receipt",
            lambda: _revalidate(
                receipt, lambda value: value.update(payload_path_disclosed_to_development=True)
            ),
        ),
        "source_file_hash_changed": (
            "source_root",
            lambda: _revalidate(
                source_root, lambda value: value["files"][0].update(sha256="0" * 64)
            ),
        ),
        "verifier_required_check_deleted": (
            "verifier_contract",
            lambda: _revalidate(
                sample_package.verifier_contract,
                lambda value: value.update(required_checks=value["required_checks"][:-1]),
            ),
        ),
    }
    results = []
    for name, (target, callback) in sorted(cases.items()):
        try:
            callback()
        except (IndexError, KeyError, TypeError, ValueError) as error:
            results.append(
                models.ProductionMutationResult(
                    mutation_name=name,
                    target_object_kind=target,
                    failure_code=type(error).__name__,
                )
            )
        else:
            raise ValueError(f"production mutation escaped:{name}")
    values = {"mutations": tuple(results)}
    return cast(
        models.ProductionDestructiveAudit,
        _make_model(
            models.ProductionDestructiveAudit,
            values,
            field="audit_id",
            prefix="finance_v26_executable_depth_production_destructive_audit:",
        ),
    )
