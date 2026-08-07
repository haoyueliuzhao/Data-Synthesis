from __future__ import annotations

import math
from copy import deepcopy
from pathlib import Path

import pytest

import trusted_synthesis.core.refinement as refinement
from trusted_synthesis.core.evaluation.contracts import (
    QualityContractCompiler,
    QualityContractRuntime,
)
from trusted_synthesis.core.synthesis import ProofCarryingSampleCompiler
from trusted_synthesis.core.trajectory import (
    TrajectoryValidityEvaluator,
    ValidTrajectoryPoolBuilder,
    make_trajectory_verification_context,
    map_trajectory_to_state,
    trajectory_decision_trace_hash,
)
from trusted_synthesis.core.trajectory.candidate_verifier import (
    CandidateWorkflowVerifier,
)
from trusted_synthesis.core.trajectory.schema import (
    Trajectory,
    WorkflowKind,
)
from trusted_synthesis.core.vtdo import (
    AnchoredDistributionUpdate,
    AnchoredEnergyConfig,
    ProbeAdaptationResult,
    StateConditionedTrajectoryExplorer,
    ValidityRegion,
    ValidityThresholds,
    ValidTrajectoryStateMaterializer,
    VTDORoundArtifact,
    allocate_exploration_budget,
    allocate_materialization_budget,
    apply_conditional_updates,
    assemble_vtdo_round,
    compile_trajectory_state_space,
    condition_on_accepted_support,
    empty_optimizer_state_hash,
    estimate_contributions_from_probes,
    estimate_exploration_state_validity,
    estimate_importance_weighted_pushforward,
    estimate_pushforward_distribution,
    estimate_state_validity,
    estimate_synthetic_oracle_contributions,
    make_admissible_trajectory_variation,
    make_conditional_distribution,
    make_contribution_data_isolation_contract,
    make_contribution_metric_contract,
    make_contribution_probe_observation,
    make_contribution_probe_protocol,
    make_exploration_distribution,
    make_probe_optimizer_contract,
    make_public_state_condition,
    make_public_state_generation_request,
    make_state_validity_partition,
    make_synthetic_oracle_contribution_observation,
    make_task_conditioned_policy,
    make_trajectory_state_catalog,
    make_unconditioned_reachability_manifest,
    make_uniform_coverage_prior,
    make_vtdo_role_contract,
    observed_variation,
    update_valid_trajectory_distribution,
)
from trusted_synthesis.core.vtdo.estimation import make_coverage_prior
from trusted_synthesis.core.vtdo.schema import (
    StateValidityEstimate,
    anchored_distribution_update_id,
    state_validity_estimate_id,
    validity_region,
)
from trusted_synthesis.experiments.cross_domain_contract_suite.candidate import (
    PlanGivenContractCandidate,
)
from trusted_synthesis.experiments.cross_domain_contract_suite.fixtures import (
    build_contract_cases,
)
from trusted_synthesis.experiments.vtdo_experiment.dynamics import _real_round_dynamics
from trusted_synthesis.experiments.vtdo_experiment.real_rounds import (
    RealRoundAssemblyInput,
    assemble_real_vtdo_rounds,
    real_round_assembly_input_id,
)
from trusted_synthesis.experiments.vtdo_experiment.schema import (
    MovingPotentialBenchmarkConfig,
    RefinementDynamicsConfig,
)
from trusted_synthesis.hashing import canonical_hash
from trusted_synthesis.runtime import InMemoryEvidenceToolRuntime
from trusted_synthesis.runtime.agent import (
    assess_state_condition_controllability,
    project_state_condition_constraints,
)


def test_oracle_specification_freezes_validity_boundary_not_unique_reasoning() -> None:
    case, compiled, _, _, context = _case_runtime(0)

    assert compiled.reference_examples == (compiled.reference_trajectory,)
    assert compiled.oracle_execution_specification.task_program_hash == (
        case.task.oracle.task_program.program_hash
    )
    assert compiled.sample.metadata["trajectory_contract"] == {
        "oracle_execution_specification_id": (
            compiled.oracle_execution_specification.specification_id
        ),
        "joint_compilation_artifact_id": compiled.joint_compilation.artifact_id,
        "omega_context_id": compiled.joint_compilation.omega.context_id,
        "reference_semantics": "one_valid_example_not_unique_gold",
    }
    assert context == compiled.joint_compilation.omega
    assert compiled.joint_compilation.component_manifest.task_program_hash == (
        case.task.oracle.task_program.program_hash
    )

    mutated_specification = compiled.oracle_execution_specification.model_copy(
        update={"proof_graph_hash": "proof_graph:mutated"}
    )
    with pytest.raises(ValueError, match="identity|does not reproduce"):
        make_trajectory_verification_context(
            case.task,
            case.bundle,
            case.corpus,
            case.proof_graph,
            compiled.quality_contract,
            mutated_specification,
        )


def test_profile_pool_remains_an_explicit_noncanonical_baseline() -> None:
    _, _, candidate, evaluator, context = _case_runtime(0)
    alternative = _trajectory_variant(candidate, "alternative-valid")
    invalid = _trajectory_variant(candidate, "invalid-citation", remove_citations=True)

    pool = ValidTrajectoryPoolBuilder(evaluator).build(
        context,
        (candidate, alternative, invalid),
        minimum_valid_count=1,
        max_per_profile=1,
    )

    assert pool.status == "passed"
    assert pool.attempted_count == 3
    assert pool.verified_valid_count == 2
    assert pool.retained_valid_count == 1
    assert not hasattr(refinement, "TrajectoryConfiguration")
    assert not hasattr(refinement, "update_valid_trajectory_policy")
    assert refinement.TRAJECTORY_PROFILE_PROXY_ALGORITHM_ID == (
        "trajectory_attribute_profile_proxy"
    )


def test_structural_quotient_erases_order_rationale_and_execution_metadata() -> None:
    _, _, candidate, evaluator, context = _case_runtime(0)
    report = evaluator.evaluate(context, candidate)
    reordered = _reorder_independent_legal_steps(candidate)
    surface_variant = _trajectory_variant(
        candidate,
        "surface-only",
        generator_version="another-runtime-build",
    )

    original_assignment = map_trajectory_to_state(
        context,
        candidate,
        program_node_aliases=report.program_node_mapping,
    )
    reordered_assignment = map_trajectory_to_state(
        context,
        reordered,
        program_node_aliases=report.program_node_mapping,
    )
    surface_assignment = map_trajectory_to_state(
        context,
        surface_variant,
        program_node_aliases=report.program_node_mapping,
    )

    assert original_assignment.trajectory_hash != reordered_assignment.trajectory_hash
    assert original_assignment.trajectory_hash != surface_assignment.trajectory_hash
    assert original_assignment.state.state_id == reordered_assignment.state.state_id
    assert original_assignment.state.state_id == surface_assignment.state.state_id
    assert "attribute" not in original_assignment.state.model_dump_json().lower()


def test_structural_quotient_preserves_result_and_evidence_semantics() -> None:
    _, _, candidate, evaluator, context = _case_runtime(0)
    report = evaluator.evaluate(context, candidate)
    changed_result = _trajectory_variant(candidate, "changed-result", mutate_result=True)
    changed_evidence = _trajectory_variant(
        candidate,
        "changed-evidence",
        replace_evidence=True,
    )

    original = map_trajectory_to_state(
        context,
        candidate,
        program_node_aliases=report.program_node_mapping,
    )
    result_state = map_trajectory_to_state(
        context,
        changed_result,
        program_node_aliases=report.program_node_mapping,
    )
    evidence_state = map_trajectory_to_state(
        context,
        changed_evidence,
        program_node_aliases=report.program_node_mapping,
    )

    assert original.state.state_id != result_state.state.state_id
    assert original.state.result_semantics_hash != result_state.state.result_semantics_hash
    assert original.state.state_id != evidence_state.state.state_id
    assert original.state.evidence_lineage_hash != evidence_state.state.evidence_lineage_hash


def test_structural_quotient_erases_equivalent_numeric_formatting() -> None:
    _, _, candidate, evaluator, context = _case_runtime(1)
    report = evaluator.evaluate(context, candidate)
    answer = deepcopy(candidate.final_answer)
    answer["result"]["difference"] = "0.8"
    steps = []
    for step in candidate.steps:
        observation = deepcopy(step.observation)
        result = observation.get("result")
        if isinstance(result, dict) and result.get("difference") == "0.80":
            result["difference"] = "8e-1"
        verified_result = observation.get("verified_result")
        if isinstance(verified_result, dict) and verified_result.get("difference") == "0.80":
            verified_result["difference"] = 0.8
        steps.append(step.model_copy(update={"observation": observation}))
    formatted = candidate.model_copy(
        update={
            "trajectory_id": canonical_hash(
                {"source": candidate.trajectory_id, "variant": "numeric-format"},
                prefix="trajectory_variant:",
            ),
            "steps": tuple(steps),
            "final_answer": answer,
        }
    )

    original = map_trajectory_to_state(
        context,
        candidate,
        program_node_aliases=report.program_node_mapping,
    )
    normalized = map_trajectory_to_state(
        context,
        formatted,
        program_node_aliases=report.program_node_mapping,
    )

    assert original.trajectory_hash != normalized.trajectory_hash
    assert original.state.state_id == normalized.state.state_id
    assert original.state.operation_graph_hash == normalized.state.operation_graph_hash
    assert original.state.result_semantics_hash == normalized.state.result_semantics_hash


def test_same_quotient_state_can_contain_valid_and_invalid_realizations() -> None:
    _, compiled, candidate, evaluator, context = _case_runtime(0)
    invalid = _trajectory_variant(
        candidate,
        "reference-kind-is-invalid-for-candidate",
        workflow_kind=WorkflowKind.REFERENCE,
    )
    valid_report = evaluator.evaluate(context, candidate)
    invalid_report = evaluator.evaluate(context, invalid)
    valid_assignment = map_trajectory_to_state(
        context,
        candidate,
        program_node_aliases=valid_report.program_node_mapping,
    )
    invalid_assignment = map_trajectory_to_state(
        context,
        invalid,
        program_node_aliases=invalid_report.program_node_mapping,
    )

    assert valid_report.valid
    assert not invalid_report.valid
    assert valid_assignment.state.state_id == invalid_assignment.state.state_id

    thresholds = ValidityThresholds(reject_below=0.25, accept_at_or_above=0.75)
    mixed = estimate_state_validity(
        (valid_assignment, invalid_assignment),
        (valid_report, invalid_report),
        thresholds=thresholds,
    )
    accepted = estimate_state_validity(
        (valid_assignment,),
        (valid_report,),
        thresholds=thresholds,
    )
    rejected = estimate_state_validity(
        (invalid_assignment,),
        (invalid_report,),
        thresholds=thresholds,
    )

    assert mixed.estimated_validity == 0.5
    assert mixed.region == ValidityRegion.QUARANTINED
    assert accepted.region == ValidityRegion.ACCEPTED
    assert rejected.region == ValidityRegion.REJECTED

    state_space_compilation = compile_trajectory_state_space(
        compiled.joint_compilation,
        _TestVariationProvider((observed_variation(valid_report.attributes),)),
    )
    catalog = make_trajectory_state_catalog(
        (
            (valid_assignment, valid_report, candidate),
            (invalid_assignment, invalid_report, invalid),
        ),
        state_space_compilation=state_space_compilation,
        discovery_method="mixed_validity_same_state_contract",
        revision_reason="prove_validity_is_not_a_state_condition",
    )
    assert len(catalog.states) == 1
    assert len(catalog.discovery_witnesses[valid_assignment.state.state_id]) == 2


def test_pushforward_estimate_counts_quotient_states_with_prior_smoothing() -> None:
    _, _, candidate, evaluator, context = _case_runtime(0)
    report = evaluator.evaluate(context, candidate)
    same_state = _trajectory_variant(candidate, "same-state")
    other_state = _trajectory_variant(candidate, "other-state", mutate_result=True)
    assignments = tuple(
        map_trajectory_to_state(
            context,
            trajectory,
            program_node_aliases=report.program_node_mapping,
        )
        for trajectory in (candidate, same_state, other_state)
    )
    state_ids = {item.state.state_id for item in assignments}
    assert len(state_ids) == 2
    prior = make_uniform_coverage_prior(context.task.task_id, state_ids)

    estimate = estimate_pushforward_distribution(
        assignments,
        prior,
        round_index=0,
        prior_strength=1.0,
    )

    counts = sorted(estimate.state_exposure_counts.values())
    probabilities = sorted(estimate.distribution.probabilities.values())
    assert counts == [1, 2]
    assert probabilities == pytest.approx([0.375, 0.625])
    assert all(value > 0 for value in estimate.distribution.probabilities.values())


def test_empirical_contribution_is_model_tied_and_centered_under_current_pi() -> None:
    distribution = make_conditional_distribution(
        "task:x",
        {"state:a": 0.8, "state:b": 0.2},
        round_index=0,
    )
    probes = (
        _probe("task:x", "state:a", baseline=0.50, intervention=0.60, seed=7),
        _probe("task:x", "state:a", baseline=0.50, intervention=0.61, seed=13),
        _probe("task:x", "state:b", baseline=0.50, intervention=0.90, seed=7),
        _probe("task:x", "state:b", baseline=0.50, intervention=0.89, seed=13),
    )

    manifest = estimate_contributions_from_probes(distribution, probes)
    contributions = {item.state_id: item.centered_contribution for item in manifest.estimates}

    assert manifest.beneficiary_model_state_id == "model:qwen-round-3"
    assert manifest.target_evaluation_distribution_id == "eval:fixed-v1"
    assert manifest.weighted_centered_mean == pytest.approx(0.0, abs=1e-12)
    assert sum(
        distribution.probabilities[state_id] * value for state_id, value in contributions.items()
    ) == pytest.approx(0.0, abs=1e-12)
    assert contributions["state:b"] > contributions["state:a"]


def test_anchored_update_matches_frozen_equation_and_exact_novelty() -> None:
    prior, coverage, validity, manifest, authorization, config, roles = _update_inputs("task:x")

    update = update_valid_trajectory_distribution(
        prior,
        coverage,
        validity,
        manifest,
        authorization,
        config,
        roles,
    )

    potential_by_state = {item.state_id: item for item in update.state_potentials}
    assert potential_by_state["state:a"].coverage_relative_novelty == 0
    assert potential_by_state["state:b"].coverage_relative_novelty == pytest.approx(
        math.log(0.5 / 0.2)
    )
    unnormalized = {
        state_id: (
            prior.probabilities[state_id] ** config.history_exponent
            * coverage.probabilities[state_id] ** (1.0 - config.history_exponent)
            * potential_by_state[state_id].potential ** config.energy_exponent
        )
        for state_id in prior.probabilities
    }
    denominator = sum(unnormalized.values())
    expected = {state_id: weight / denominator for state_id, weight in unnormalized.items()}
    assert update.next_distribution.probabilities == pytest.approx(expected)
    assert update.next_distribution.probabilities["state:b"] > 0.2
    assert update.algorithm_id == ("anchored_energy_valid_trajectory_distribution_refinement")


def test_reachability_aware_energy_penalizes_unobserved_novel_states() -> None:
    prior, coverage, validity, manifest, authorization, config, roles = _update_inputs("task:x")
    baseline = update_valid_trajectory_distribution(
        prior,
        coverage,
        validity,
        manifest,
        authorization,
        config,
        roles,
    )
    reachability = make_unconditioned_reachability_manifest(
        task_condition_id="task:x",
        explorer_provider_id="provider:explorer-v1",
        explorer_provider_version="1.0.0",
        state_counts={"state:a": 19, "state:b": 1},
        attempted_trajectory_count=20,
        source_batch_ids=("exploration:round-0",),
    )
    reachability_config = config.model_copy(
        update={
            "reachability_weight": 1.0,
            "reachability_floor": 0.01,
            "reachability_signal": "posterior_mean",
        }
    )

    aware = update_valid_trajectory_distribution(
        prior,
        coverage,
        validity,
        manifest,
        authorization,
        reachability_config,
        roles,
        reachability,
    )

    assert aware.reachability_manifest == reachability
    potentials = {item.state_id: item for item in aware.state_potentials}
    assert potentials["state:a"].reachability_probability > (
        potentials["state:b"].reachability_probability
    )
    assert (
        aware.next_distribution.probabilities["state:b"]
        < (baseline.next_distribution.probabilities["state:b"])
    )


def test_reachability_aware_energy_fails_closed_without_measurements() -> None:
    prior, coverage, validity, manifest, authorization, config, roles = _update_inputs("task:x")
    reachability_config = config.model_copy(update={"reachability_weight": 1.0})

    with pytest.raises(ValueError, match="complete manifest"):
        update_valid_trajectory_distribution(
            prior,
            coverage,
            validity,
            manifest,
            authorization,
            reachability_config,
            roles,
        )


def test_reachability_confidence_lower_uses_positive_floor_for_zero_hits() -> None:
    prior, coverage, validity, manifest, authorization, config, roles = _update_inputs("task:x")
    reachability = make_unconditioned_reachability_manifest(
        task_condition_id="task:x",
        explorer_provider_id="provider:explorer-v1",
        explorer_provider_version="1.0.0",
        state_counts={"state:a": 2, "state:b": 0},
        attempted_trajectory_count=2,
        source_batch_ids=("exploration:round-0",),
    )
    reachability_config = config.model_copy(
        update={
            "reachability_weight": 1.0,
            "reachability_floor": 0.01,
            "reachability_signal": "confidence_lower",
        }
    )

    aware = update_valid_trajectory_distribution(
        prior,
        coverage,
        validity,
        manifest,
        authorization,
        reachability_config,
        roles,
        reachability,
    )

    potentials = {item.state_id: item for item in aware.state_potentials}
    assert potentials["state:b"].reachability_probability == 0
    assert potentials["state:b"].normalized_reachability == 0.01
    assert potentials["state:b"].potential > 0


def test_update_artifact_replays_equation_instead_of_trusting_serialized_metrics() -> None:
    inputs = _update_inputs("task:x")
    update = update_valid_trajectory_distribution(*inputs)
    wrong_next = make_conditional_distribution(
        "task:x",
        {"state:a": 0.9, "state:b": 0.1},
        round_index=1,
        source_distribution_id=inputs[0].distribution_id,
        estimator_manifest_hash=inputs[3].manifest_id,
    )
    values = {
        field: getattr(update, field) for field in type(update).model_fields if field != "update_id"
    }
    values["next_distribution"] = wrong_next
    provisional = AnchoredDistributionUpdate.model_construct(
        update_id="pending",
        **values,
    )

    with pytest.raises(ValueError, match="anchored equation"):
        AnchoredDistributionUpdate(
            update_id=anchored_distribution_update_id(provisional),
            **values,
        )


def test_update_rejects_potential_detached_from_contribution_manifest() -> None:
    update = update_valid_trajectory_distribution(*_update_inputs("task:x"))
    changed = update.state_potentials[0].model_copy(
        update={"centered_contribution": (update.state_potentials[0].centered_contribution + 0.1)}
    )
    values = {
        field: getattr(update, field) for field in type(update).model_fields if field != "update_id"
    }
    values["state_potentials"] = (changed, *update.state_potentials[1:])

    with pytest.raises(ValueError, match="detached from its contribution"):
        AnchoredDistributionUpdate(update_id=update.update_id, **values)


def test_update_rejects_contribution_from_another_beneficiary_model() -> None:
    prior, coverage, validity, manifest, authorization, config, _ = _update_inputs("task:x")
    wrong_roles = make_vtdo_role_contract(
        explorer_provider_id="provider:explorer-v1",
        materialization_provider_id="provider:materializer-v1",
        beneficiary_model_state_id="model:another-beneficiary",
        final_student_model_id="model:qwen-student-round-4",
    )

    with pytest.raises(ValueError, match="role contract"):
        update_valid_trajectory_distribution(
            prior,
            coverage,
            validity,
            manifest,
            authorization,
            config,
            wrong_roles,
        )


def test_validity_is_a_noncompensable_gate_and_conditions_training_support() -> None:
    prior, coverage, validity, manifest, authorization, config, roles = _update_inputs("task:x")
    quarantined = _validity_estimate("task:x", "state:b", 0.5)

    with pytest.raises(ValueError, match="non-Accepted"):
        update_valid_trajectory_distribution(
            prior,
            coverage,
            (validity[0], quarantined),
            manifest,
            authorization,
            config,
            roles,
        )

    partition = make_state_validity_partition((validity[0], quarantined))
    accepted_prior, accepted_coverage = condition_on_accepted_support(
        prior,
        coverage,
        partition,
    )
    assert accepted_prior.probabilities == {"state:a": 1.0}
    assert accepted_coverage.probabilities == {"state:a": 1.0}
    assert partition.quarantined_state_ids == ("state:b",)


def test_task_marginal_is_fixed_while_each_conditional_advances() -> None:
    inputs_x = _update_inputs("task:x")
    inputs_y = _update_inputs(
        "task:y",
        probabilities={"state:c": 0.3, "state:d": 0.7},
        coverage_probabilities={"state:c": 0.5, "state:d": 0.5},
    )
    update_x = update_valid_trajectory_distribution(*inputs_x)
    update_y = update_valid_trajectory_distribution(*inputs_y)
    policy = make_task_conditioned_policy(
        {"task:x": 0.65, "task:y": 0.35},
        {"task:x": inputs_x[0], "task:y": inputs_y[0]},
        round_index=0,
    )

    next_policy = apply_conditional_updates(
        policy,
        {"task:x": update_x, "task:y": update_y},
    )

    assert next_policy.task_marginal == policy.task_marginal
    assert next_policy.round_index == 1
    assert next_policy.conditionals["task:x"] == update_x.next_distribution
    assert next_policy.conditionals["task:y"] == update_y.next_distribution


def test_exploration_distribution_and_state_conditioned_batch_use_observed_states() -> None:
    _, compiled, candidate, evaluator, context = _case_runtime(0)
    report = evaluator.evaluate(context, candidate)
    assignment = map_trajectory_to_state(
        context,
        candidate,
        program_node_aliases=report.program_node_mapping,
    )
    target = assignment.state
    state_space_compilation = compile_trajectory_state_space(
        compiled.joint_compilation,
        _TestVariationProvider((observed_variation(report.attributes),)),
    )
    catalog = make_trajectory_state_catalog(
        ((assignment, report, candidate),),
        state_space_compilation=state_space_compilation,
        discovery_method="verified_test_exploration",
        revision_reason="test_public_state_projection",
    )
    training = make_conditional_distribution(
        context.task.task_id,
        {target.state_id: 1.0},
        round_index=0,
    )
    coverage = make_uniform_coverage_prior(context.task.task_id, (target.state_id,))
    exploration = make_exploration_distribution(
        training,
        coverage,
        exploration_rate=0.2,
    )
    provider = _StateTrajectoryProvider(candidate)

    batch = StateConditionedTrajectoryExplorer(provider, evaluator).explore(
        context,
        catalog,
        exploration,
        _role_contract(provider.provider_id),
        total_budget=2,
        seed=41,
    )

    assert allocate_exploration_budget(exploration, 2) == {target.state_id: 2}
    assert batch.status == "passed"
    assert batch.mapped_candidate_count == 2
    assert batch.on_target_candidate_count == 2
    assert batch.observed_state_counts == {target.state_id: 2}
    assert all(item.validity_report.valid for item in batch.observations)
    estimates, partition = estimate_exploration_state_validity(
        batch,
        thresholds=ValidityThresholds(
            reject_below=0.25,
            accept_at_or_above=0.75,
        ),
    )
    assert estimates[0].estimated_validity == 1.0
    assert partition.accepted_state_ids == (target.state_id,)
    assert all(item.requested_state_importance_weight == 1.0 for item in batch.observations)


def test_public_state_request_excludes_host_only_omega_and_oracle_artifacts() -> None:
    _, compiled, candidate, evaluator, context = _case_runtime(0)
    report = evaluator.evaluate(context, candidate)
    variation = make_admissible_trajectory_variation(
        acquisition_requirement="bounded",
        evidence_support_requirement="required_roles",
        verification_requirement="full",
        lineage_requirement="direct",
        required_capabilities=report.attributes.capability_tags,
        minimum_tool_calls=report.attributes.tool_call_count,
        minimum_evidence_count=report.attributes.evidence_dependency_count,
        minimum_reasoning_depth=report.attributes.reasoning_depth,
        minimum_verification_degree=report.attributes.verification_degree,
    )
    state_space_compilation = compile_trajectory_state_space(
        compiled.joint_compilation,
        _TestVariationProvider((variation,)),
    )
    condition = state_space_compilation.public_conditions_by_variation_id[variation.variation_id]
    assert state_space_compilation.joint_compilation_artifact_id == (
        compiled.joint_compilation.artifact_id
    )
    assert state_space_compilation.omega_context_id == context.context_id
    assert state_space_compilation.joint_compilation == compiled.joint_compilation
    with pytest.raises(ValueError, match="duplicate variations"):
        compile_trajectory_state_space(
            compiled.joint_compilation,
            _TestVariationProvider((variation, variation)),
        )
    request = make_public_state_generation_request(
        context,
        condition,
        candidate_count=2,
        seed=17,
    )

    payload = request.model_dump_json()
    public_payload = context.task.public.model_dump_json()
    host_only_values = (
        context.context_id,
        context.oracle_specification.specification_id,
        context.evidence_bundle.bundle_id,
        context.evidence_bundle.bundle_hash,
        context.proof_graph.graph_id,
        context.proof_graph.graph_hash,
        context.task.oracle.task_program.program_id,
        context.task.oracle.task_program.program_hash,
        context.quality_contract.contract_id,
        context.quality_contract.contract_hash,
        compiled.reference_trajectory.trajectory_id,
    )
    assert all(value not in payload or value in public_payload for value in host_only_values)
    assert not hasattr(request.state_condition, "state_id")


def test_state_condition_controllability_rejects_host_blocked_targets() -> None:
    _, compiled, candidate, evaluator, context = _case_runtime(0)
    report = evaluator.evaluate(context, candidate)
    bounded = make_admissible_trajectory_variation(
        acquisition_requirement="bounded",
        evidence_support_requirement="required_roles",
        verification_requirement="full",
        lineage_requirement="direct",
        retrieval_elaboration="required_only",
        execution_elaboration="baseline_program",
        required_capabilities=report.attributes.capability_tags,
        minimum_tool_calls=report.attributes.tool_call_count,
        minimum_evidence_count=report.attributes.evidence_dependency_count,
        minimum_reasoning_depth=report.attributes.reasoning_depth,
        minimum_verification_degree=report.attributes.verification_degree,
    )
    expanded = make_admissible_trajectory_variation(
        acquisition_requirement="expanded",
        evidence_support_requirement="expanded_context",
        verification_requirement="full",
        lineage_requirement="full",
        retrieval_elaboration="full_corpus",
        execution_elaboration="transparent_projection",
        required_capabilities=report.attributes.capability_tags,
        minimum_tool_calls=report.attributes.tool_call_count,
        minimum_evidence_count=report.attributes.evidence_dependency_count,
        minimum_reasoning_depth=report.attributes.reasoning_depth,
        minimum_verification_degree=report.attributes.verification_degree,
    )
    compilation = compile_trajectory_state_space(
        compiled.joint_compilation,
        _TestVariationProvider((bounded, expanded)),
    )
    bounded_request = make_public_state_generation_request(
        context,
        compilation.public_conditions_by_variation_id[bounded.variation_id],
        candidate_count=1,
        seed=11,
    )
    expanded_request = make_public_state_generation_request(
        context,
        compilation.public_conditions_by_variation_id[expanded.variation_id],
        candidate_count=1,
        seed=13,
    )

    bounded_audit = assess_state_condition_controllability(
        bounded_request,
        interaction_protocol="host_instrumented",
    )
    expanded_audit = assess_state_condition_controllability(
        expanded_request,
        interaction_protocol="host_instrumented",
    )
    constraints = project_state_condition_constraints(
        bounded_request.state_condition,
        bounded_audit,
    )

    assert bounded_audit.condition_requestable
    assert not bounded_audit.blocked_dimensions
    assert constraints["target_behavior"]["acquisition_requirement"] == "bounded"
    assert constraints["control_plan"]["retrieval"]["mode"] == "required_only"
    assert constraints["control_plan"]["execution"]["mode"] == "baseline_program"
    assert "condition_id" not in constraints["target_behavior"]
    assert not expanded_audit.condition_requestable
    assert set(expanded_audit.blocked_dimensions) == {
        "acquisition_requirement",
        "evidence_support_requirement",
        "execution_elaboration",
        "lineage_requirement",
        "retrieval_elaboration",
    }


def test_decision_trace_erases_runtime_identity_but_preserves_decisions() -> None:
    _, _, candidate, evaluator, context = _case_runtime(0)
    report = evaluator.evaluate(context, candidate)
    surface_clone = _trajectory_variant(
        candidate,
        "new-id-and-rationale-only",
        generator_version="another-runtime-build",
    )
    changed_decision = _trajectory_variant(
        candidate,
        "changed-search-decision",
        search_variant="expanded-search-route",
    )

    original_hash = trajectory_decision_trace_hash(
        candidate,
        program_node_aliases=report.program_node_mapping,
    )
    assert candidate.trajectory_hash != surface_clone.trajectory_hash
    assert original_hash == trajectory_decision_trace_hash(
        surface_clone,
        program_node_aliases=report.program_node_mapping,
    )
    assert original_hash != trajectory_decision_trace_hash(
        changed_decision,
        program_node_aliases=report.program_node_mapping,
    )


def test_materialization_budget_preserves_support_or_reports_truncation() -> None:
    distribution = make_conditional_distribution(
        "task:x",
        {"state:dominant": 0.99, "state:rare": 0.01},
        round_index=1,
    )

    assert allocate_materialization_budget(distribution, 2) == {
        "state:dominant": 1,
        "state:rare": 1,
    }
    truncated = allocate_materialization_budget(distribution, 1)
    assert sum(truncated.values()) == 1
    assert 0 in truncated.values()


def test_vtdo_roles_are_distinct_unless_sharing_is_explicitly_declared() -> None:
    with pytest.raises(ValueError, match="distinct"):
        make_vtdo_role_contract(
            explorer_provider_id="model:shared",
            materialization_provider_id="model:materializer",
            beneficiary_model_state_id="model:shared",
            final_student_model_id="model:student",
        )

    with pytest.raises(ValueError, match="materialization"):
        make_vtdo_role_contract(
            explorer_provider_id="model:explorer",
            materialization_provider_id="model:student",
            beneficiary_model_state_id="model:beneficiary",
            final_student_model_id="model:student",
        )

    shared = make_vtdo_role_contract(
        explorer_provider_id="model:shared",
        materialization_provider_id="model:materializer",
        beneficiary_model_state_id="model:shared",
        final_student_model_id="model:student",
        separation_mode="declared_shared",
        shared_role_justification_hash="experiment:shared-model-ablation",
    )
    assert shared.separation_mode == "declared_shared"


def test_exploration_q_mixes_training_and_coverage_and_reports_importance() -> None:
    training = make_conditional_distribution(
        "task:x",
        {"state:a": 0.8, "state:b": 0.2},
        round_index=0,
    )
    coverage = make_coverage_prior(
        "task:x",
        {"state:a": 0.5, "state:b": 0.5},
        policy="balanced",
    )

    exploration = make_exploration_distribution(
        training,
        coverage,
        exploration_rate=0.25,
    )

    assert exploration.probabilities == pytest.approx({"state:a": 0.725, "state:b": 0.275})
    assert exploration.importance_weights == pytest.approx(
        {"state:a": 0.8 / 0.725, "state:b": 0.2 / 0.275}
    )
    assert sum(allocate_exploration_budget(exploration, 17).values()) == 17


def test_quotient_mapper_is_shared_by_legal_and_science_contracts() -> None:
    states = []
    domains = []
    for index in (0, 1):
        case, _, candidate, evaluator, context = _case_runtime(index)
        report = evaluator.evaluate(context, candidate)
        assignment = map_trajectory_to_state(
            context,
            candidate,
            program_node_aliases=report.program_node_mapping,
        )
        assert report.valid
        states.append(assignment.state.state_id)
        domains.append(case.task.public.domain)

    assert domains == ["legal", "science"]
    assert len(set(states)) == 2


def test_legal_and_science_compile_multiple_states_inside_one_omega() -> None:
    for index in (0, 1):
        case, compiled, candidate, evaluator, context = _case_runtime(index)
        expanded = _expanded_retrieval_variant(
            candidate, tuple(item.evidence_id for item in case.corpus.evidence)
        )
        base_report = evaluator.evaluate(context, candidate)
        expanded_report = evaluator.evaluate(context, expanded)
        assert base_report.valid
        assert expanded_report.valid

        base_assignment = map_trajectory_to_state(
            context,
            candidate,
            program_node_aliases=base_report.program_node_mapping,
        )
        expanded_assignment = map_trajectory_to_state(
            context,
            expanded,
            program_node_aliases=expanded_report.program_node_mapping,
        )
        assert base_assignment.state.omega_context_id == context.context_id
        assert expanded_assignment.state.omega_context_id == context.context_id
        assert base_assignment.state.state_id != expanded_assignment.state.state_id

        base_variation = make_admissible_trajectory_variation(
            acquisition_requirement="bounded",
            evidence_support_requirement="required_roles",
            verification_requirement="full",
            lineage_requirement="direct",
            required_capabilities=base_report.attributes.capability_tags,
        )
        expanded_variation = make_admissible_trajectory_variation(
            acquisition_requirement="expanded",
            evidence_support_requirement="expanded_context",
            verification_requirement="full",
            lineage_requirement="direct",
            required_capabilities=expanded_report.attributes.capability_tags,
        )
        state_space_compilation = compile_trajectory_state_space(
            compiled.joint_compilation,
            _TestVariationProvider((base_variation, expanded_variation)),
        )
        catalog = make_trajectory_state_catalog(
            (
                (base_assignment, base_report, candidate),
                (expanded_assignment, expanded_report, expanded),
            ),
            state_space_compilation=state_space_compilation,
            public_conditions_by_assignment_id={
                base_assignment.assignment_id: (
                    state_space_compilation.public_conditions_by_variation_id[
                        base_variation.variation_id
                    ]
                ),
                expanded_assignment.assignment_id: (
                    state_space_compilation.public_conditions_by_variation_id[
                        expanded_variation.variation_id
                    ]
                ),
            },
            discovery_method=f"{case.domain}_cross_domain_contract",
            revision_reason="prove_same_omega_multi_state_compilation",
        )

        assert catalog.omega_context_id == context.context_id
        assert len(catalog.states) == 2
        assert (
            len({condition.condition_id for condition in catalog.public_state_conditions.values()})
            == 2
        )


def test_search_only_distractor_identity_is_quantized_within_context_class() -> None:
    case, _, candidate, evaluator, context = _case_runtime(0)
    selected_ids = {
        evidence_id
        for step in candidate.steps
        if step.action.value != "search"
        for evidence_id in step.evidence_ids
    }
    distractor_ids = [
        item.evidence_id for item in case.corpus.evidence if item.evidence_id not in selected_ids
    ]
    assert len(distractor_ids) >= 2

    left = _expanded_retrieval_variant(candidate, tuple(sorted((*selected_ids, distractor_ids[0]))))
    right = _expanded_retrieval_variant(
        candidate, tuple(sorted((*selected_ids, distractor_ids[1])))
    )
    full = _expanded_retrieval_variant(
        candidate, tuple(item.evidence_id for item in case.corpus.evidence)
    )
    left_report = evaluator.evaluate(context, left)
    right_report = evaluator.evaluate(context, right)
    full_report = evaluator.evaluate(context, full)
    assert left_report.valid and right_report.valid and full_report.valid

    left_state = map_trajectory_to_state(
        context, left, program_node_aliases=left_report.program_node_mapping
    )
    right_state = map_trajectory_to_state(
        context, right, program_node_aliases=right_report.program_node_mapping
    )
    full_state = map_trajectory_to_state(
        context, full, program_node_aliases=full_report.program_node_mapping
    )

    assert left_state.state.state_id == right_state.state.state_id
    assert left_state.state.state_id != full_state.state.state_id


def test_sparse_training_support_remains_explorable_under_full_catalog_q() -> None:
    training = make_conditional_distribution(
        "task:x",
        {"state:accepted": 1.0},
        round_index=3,
    )
    coverage = make_coverage_prior(
        "task:x",
        {"state:accepted": 0.5, "state:quarantined": 0.5},
        policy="full_catalog_uniform",
    )

    exploration = make_exploration_distribution(
        training,
        coverage,
        exploration_rate=0.2,
    )

    assert exploration.probabilities == pytest.approx(
        {"state:accepted": 0.9, "state:quarantined": 0.1}
    )
    assert exploration.importance_weights == pytest.approx(
        {"state:accepted": 1.0 / 0.9, "state:quarantined": 0.0}
    )
    assert allocate_exploration_budget(exploration, 20) == {
        "state:accepted": 18,
        "state:quarantined": 2,
    }


def test_round_artifact_replays_exploration_estimation_update_and_materialization(
    tmp_path: Path,
) -> None:
    case, compiled, candidate, evaluator, context = _case_runtime(0)
    expanded = _expanded_retrieval_variant(
        candidate, tuple(item.evidence_id for item in case.corpus.evidence)
    )
    invalid = _trajectory_variant(expanded, "catalog-invalid", mutate_result=True)
    valid_report = evaluator.evaluate(context, candidate)
    invalid_report = evaluator.evaluate(context, invalid)
    valid_assignment = map_trajectory_to_state(
        context,
        candidate,
        program_node_aliases=valid_report.program_node_mapping,
    )
    invalid_assignment = map_trajectory_to_state(
        context,
        invalid,
        program_node_aliases=invalid_report.program_node_mapping,
    )
    valid_state = valid_assignment.state
    invalid_state = invalid_assignment.state
    assert valid_report.valid
    assert not invalid_report.valid
    assert valid_state.state_id != invalid_state.state_id

    fallback_compilation = compile_trajectory_state_space(
        compiled.joint_compilation,
        _TestVariationProvider((observed_variation(valid_report.attributes),)),
    )
    with pytest.raises(ValueError, match="does not bind its assignment"):
        make_trajectory_state_catalog(
            ((valid_assignment, invalid_report, candidate),),
            state_space_compilation=fallback_compilation,
            discovery_method="mismatched_validity_report",
            revision_reason="test_fail_closed_validity_witness",
        )

    valid_variation = make_admissible_trajectory_variation(
        acquisition_requirement="bounded",
        evidence_support_requirement="required_roles",
        verification_requirement="full",
        lineage_requirement="direct",
        required_capabilities=valid_report.attributes.capability_tags,
    )
    invalid_variation = make_admissible_trajectory_variation(
        acquisition_requirement="expanded",
        evidence_support_requirement="expanded_context",
        verification_requirement="full",
        lineage_requirement="direct",
        required_capabilities=invalid_report.attributes.capability_tags,
    )
    state_space_compilation = compile_trajectory_state_space(
        compiled.joint_compilation,
        _TestVariationProvider((valid_variation, invalid_variation)),
    )
    catalog = make_trajectory_state_catalog(
        (
            (valid_assignment, valid_report, candidate),
            (invalid_assignment, invalid_report, invalid),
        ),
        state_space_compilation=state_space_compilation,
        public_conditions_by_assignment_id={
            valid_assignment.assignment_id: (
                state_space_compilation.public_conditions_by_variation_id[
                    valid_variation.variation_id
                ]
            ),
            invalid_assignment.assignment_id: (
                state_space_compilation.public_conditions_by_variation_id[
                    invalid_variation.variation_id
                ]
            ),
        },
        discovery_method="verified_test_exploration",
        revision_reason="test_initial_state_discovery",
    )
    assert {
        witness.valid for witnesses in catalog.discovery_witnesses.values() for witness in witnesses
    } == {False, True}
    training = make_conditional_distribution(
        context.task.task_id,
        {valid_state.state_id: 1.0},
        round_index=0,
    )
    coverage = make_uniform_coverage_prior(context.task.task_id, catalog.states)
    exploration = make_exploration_distribution(
        training,
        coverage,
        exploration_rate=0.2,
    )
    provider = _CatalogTrajectoryProvider(
        catalog,
        {
            valid_state.state_id: candidate,
            invalid_state.state_id: invalid,
        },
    )
    roles = _role_contract(
        provider.provider_id,
        beneficiary_model_state_id="synthetic_oracle",
    )
    batch = StateConditionedTrajectoryExplorer(provider, evaluator).explore(
        context,
        catalog,
        exploration,
        roles,
        total_budget=20,
        seed=73,
    )
    assert batch.status == "passed"
    assert batch.observed_state_counts == {
        valid_state.state_id: 18,
        invalid_state.state_id: 2,
    }

    pushforward = estimate_importance_weighted_pushforward(
        batch,
        exploration,
        prior_strength=1.0,
    )
    assert pushforward.state_exposure_counts == batch.observed_state_counts
    assert pushforward.state_exposure_weights[valid_state.state_id] == pytest.approx(20.0)
    assert pushforward.state_exposure_weights[invalid_state.state_id] == 0.0
    assert pushforward.effective_sample_size == pytest.approx(18.0)
    assert pushforward.distribution.probabilities[invalid_state.state_id] > 0

    estimates, partition = estimate_exploration_state_validity(
        batch,
        thresholds=ValidityThresholds(
            reject_below=0.25,
            accept_at_or_above=0.75,
        ),
    )
    assert {item.region for item in estimates} == {
        ValidityRegion.ACCEPTED,
        ValidityRegion.REJECTED,
    }
    assert partition.accepted_state_ids == (valid_state.state_id,)
    assert partition.rejected_state_ids == (invalid_state.state_id,)

    accepted_prior, _ = condition_on_accepted_support(
        pushforward.distribution,
        exploration.coverage_prior,
        partition,
    )
    contribution_manifest = estimate_synthetic_oracle_contributions(
        accepted_prior,
        (
            make_synthetic_oracle_contribution_observation(
                task_condition_id=context.task.task_id,
                round_index=accepted_prior.round_index,
                state_id=valid_state.state_id,
                oracle_contribution=0.2,
                oracle_protocol_hash="synthetic-round:0",
            ),
        ),
    )
    round_artifact = assemble_vtdo_round(
        state_catalog=catalog,
        role_contract=roles,
        exploration=exploration,
        exploration_batch=batch,
        pushforward_estimate=pushforward,
        validity_partition=partition,
        contribution_manifest=contribution_manifest,
        contribution_approximation_authorization=None,
        energy_config=AnchoredEnergyConfig(
            epsilon=0.01,
            contribution_temperature=0.2,
            novelty_temperature=1.0,
            contribution_weight=0.5,
            novelty_weight=0.5,
            history_kl_weight=2.0,
            coverage_kl_weight=1.0,
        ),
    )
    assert round_artifact.status == "passed"
    assert round_artifact.update.next_distribution.probabilities == {valid_state.state_id: 1.0}

    wrong_manifest = estimate_synthetic_oracle_contributions(
        accepted_prior,
        (
            make_synthetic_oracle_contribution_observation(
                task_condition_id=context.task.task_id,
                round_index=accepted_prior.round_index,
                state_id=valid_state.state_id,
                oracle_contribution=0.9,
                oracle_protocol_hash="synthetic-round:tampered",
            ),
        ),
    )
    round_values = {
        field: getattr(round_artifact, field)
        for field in type(round_artifact).model_fields
        if field != "round_id"
    }
    round_values["contribution_manifest"] = wrong_manifest
    with pytest.raises(ValueError, match="does not replay the complete round evidence"):
        VTDORoundArtifact(round_id=round_artifact.round_id, **round_values)

    artifacts, materialization = ValidTrajectoryStateMaterializer(
        provider,
        evaluator,
    ).materialize(
        context,
        catalog,
        round_artifact.update.next_distribution,
        roles,
        total_budget=3,
        seed=91,
    )
    assert materialization.status == "passed"
    assert materialization.independent_regeneration_enforced
    assert materialization.distribution_fidelity_error == 0.0
    assert materialization.quota_fill_rate == 1.0
    assert materialization.distribution_total_variation == 0.0
    assert materialization.jensen_shannon_divergence == 0.0
    assert materialization.minimum_support_floor_applied
    assert not materialization.finite_budget_support_truncation
    assert materialization.unique_decision_trace_count == 3
    assert set(materialization.state_acceptance_rates) == {valid_state.state_id}
    assert materialization.state_off_target_rates[valid_state.state_id] == 0.0
    assert all(audit.passed for audit in materialization.public_state_leakage_audits.values())
    assert materialization.materialization_provider_id == provider.provider_id
    assert materialization.explorer_provider_id == roles.explorer_provider_id
    assert len(artifacts) == 3
    assert all(item.assignment.state == valid_state for item in artifacts)
    assert all(item.context.task == context.task for item in artifacts)
    assert all(item.context.evidence_bundle == context.evidence_bundle for item in artifacts)

    direct_rounds = [round_artifact]
    prior = round_artifact.update.next_distribution
    for round_index in (1, 2):
        next_exploration = make_exploration_distribution(
            prior,
            coverage,
            exploration_rate=0.2,
        )
        next_batch = StateConditionedTrajectoryExplorer(provider, evaluator).explore(
            context,
            catalog,
            next_exploration,
            roles,
            total_budget=20,
            seed=73 + round_index,
        )
        next_pushforward = estimate_importance_weighted_pushforward(
            next_batch,
            next_exploration,
            prior_strength=1.0,
        )
        _, next_partition = estimate_exploration_state_validity(
            next_batch,
            thresholds=ValidityThresholds(
                reject_below=0.25,
                accept_at_or_above=0.75,
            ),
        )
        next_accepted_prior, _ = condition_on_accepted_support(
            next_pushforward.distribution,
            next_exploration.coverage_prior,
            next_partition,
        )
        next_manifest = estimate_synthetic_oracle_contributions(
            next_accepted_prior,
            (
                make_synthetic_oracle_contribution_observation(
                    task_condition_id=context.task.task_id,
                    round_index=next_accepted_prior.round_index,
                    state_id=valid_state.state_id,
                    oracle_contribution=0.2,
                    oracle_protocol_hash=f"synthetic-round:{round_index}",
                ),
            ),
        )
        next_round = assemble_vtdo_round(
            state_catalog=catalog,
            role_contract=roles,
            exploration=next_exploration,
            exploration_batch=next_batch,
            pushforward_estimate=next_pushforward,
            validity_partition=next_partition,
            contribution_manifest=next_manifest,
            contribution_approximation_authorization=None,
            energy_config=round_artifact.update.energy_config,
        )
        direct_rounds.append(next_round)
        prior = next_round.update.next_distribution

    assembly_inputs = []
    for item in direct_rounds:
        input_values = {
            "state_catalog": item.state_catalog,
            "role_contract": item.role_contract,
            "exploration": item.exploration,
            "exploration_batch": item.exploration_batch,
            "contribution_manifest": item.contribution_manifest,
            "contribution_approximation_authorization": (
                item.contribution_approximation_authorization
            ),
            "contribution_source_artifact_hash": (
                item.contribution_manifest.estimation_protocol_hash
            ),
            "validity_thresholds": ValidityThresholds(reject_below=0.25, accept_at_or_above=0.75),
            "validity_prior_success": 0.0,
            "validity_prior_failure": 0.0,
            "pushforward_prior_strength": 1.0,
            "energy_config": item.update.energy_config,
            "explorer_checkpoint_hash": "explorer-checkpoint:v1",
            "beneficiary_checkpoint_hash": "synthetic_oracle",
            "catalog_version": "test-catalog:v1",
        }
        provisional_input = RealRoundAssemblyInput.model_construct(
            input_id="pending", **input_values
        )
        assembly_inputs.append(
            RealRoundAssemblyInput(
                input_id=real_round_assembly_input_id(provisional_input),
                **input_values,
            )
        )
    assert len({item.contribution_source_artifact_hash for item in assembly_inputs}) == 3
    input_path = tmp_path / "three_round_inputs.jsonl"
    output_path = tmp_path / "three_round_artifacts.jsonl"
    input_path.write_text(
        "".join(item.model_dump_json() + "\n" for item in assembly_inputs),
        encoding="utf-8",
    )
    assembly_report, replayed_rounds = assemble_real_vtdo_rounds(input_path, output_path)
    assert assembly_report.status == "passed", assembly_report.blockers
    assert assembly_report.complete_sequence_count == 1
    assert tuple(item.round_index for item in replayed_rounds) == (0, 1, 2)
    assert tuple(item.round_id for item in replayed_rounds) == tuple(
        item.round_id for item in direct_rounds
    )

    dynamics_config = RefinementDynamicsConfig(
        analysis_rounds=3,
        checkpoint_rounds=(1, 3),
        primary_training_round=3,
        fixed_potential_rounds=3,
        moving_potential_benchmark=MovingPotentialBenchmarkConfig(rounds=3),
        real_round_artifact_paths=(output_path,),
        expected_real_task_condition_ids=(context.task.task_id,),
    )
    dynamics_summary, _ = _real_round_dynamics(dynamics_config)
    assert dynamics_summary.status == "passed", dynamics_summary.blockers
    assert dynamics_summary.turnover_probability_threshold == pytest.approx(1e-4)
    mismatched_summary, _ = _real_round_dynamics(
        dynamics_config.model_copy(
            update={"expected_real_task_condition_ids": ("task:unexpected",)}
        )
    )
    assert mismatched_summary.status != "passed"
    assert mismatched_summary.missing_task_condition_count == 1
    assert mismatched_summary.unexpected_task_condition_count == 1


def test_materializer_rejects_reuse_of_state_discovery_trajectory() -> None:
    _, compiled, candidate, evaluator, context = _case_runtime(0)
    report = evaluator.evaluate(context, candidate)
    assignment = map_trajectory_to_state(
        context,
        candidate,
        program_node_aliases=report.program_node_mapping,
    )
    state_space_compilation = compile_trajectory_state_space(
        compiled.joint_compilation,
        _TestVariationProvider((observed_variation(report.attributes),)),
    )
    catalog = make_trajectory_state_catalog(
        ((assignment, report, candidate),),
        state_space_compilation=state_space_compilation,
        discovery_method="verified_test_exploration",
        revision_reason="test_discovery_reuse_guard",
    )
    distribution = make_conditional_distribution(
        context.task.task_id,
        {assignment.state.state_id: 1.0},
        round_index=1,
    )
    provider = _ReplayDiscoveryTrajectoryProvider(candidate)
    roles = _role_contract(provider.provider_id)

    artifacts, materialization = ValidTrajectoryStateMaterializer(
        provider,
        evaluator,
    ).materialize(
        context,
        catalog,
        distribution,
        roles,
        total_budget=2,
        seed=19,
    )

    assert artifacts == ()
    assert materialization.status == "blocked"
    assert materialization.failure_counts["discovery_trajectory_reuse"] == 6
    assert materialization.quota_fill_rate == 0.0
    assert materialization.distribution_fidelity_error == 1.0


def test_off_target_trace_does_not_block_a_later_on_target_quota() -> None:
    _, compiled, candidate, evaluator, context = _case_runtime(0)
    expanded = _expanded_retrieval_variant(
        candidate,
        tuple(item.evidence_id for item in context.public_corpus.evidence),
    )
    compact_report = evaluator.evaluate(context, candidate)
    expanded_report = evaluator.evaluate(context, expanded)
    assert compact_report.valid and expanded_report.valid
    compact_assignment = map_trajectory_to_state(
        context,
        candidate,
        program_node_aliases=compact_report.program_node_mapping,
    )
    expanded_assignment = map_trajectory_to_state(
        context,
        expanded,
        program_node_aliases=expanded_report.program_node_mapping,
    )
    assignments = {
        compact_assignment.state.state_id: (compact_assignment, compact_report, candidate),
        expanded_assignment.state.state_id: (expanded_assignment, expanded_report, expanded),
    }
    assert len(assignments) == 2
    compact_variation = make_admissible_trajectory_variation(
        acquisition_requirement="bounded",
        evidence_support_requirement="required_roles",
        retrieval_elaboration="required_only",
    )
    expanded_variation = make_admissible_trajectory_variation(
        acquisition_requirement="expanded",
        evidence_support_requirement="expanded_context",
        retrieval_elaboration="full_corpus",
    )
    compilation = compile_trajectory_state_space(
        compiled.joint_compilation,
        _TestVariationProvider((compact_variation, expanded_variation)),
    )
    ordered_state_ids = tuple(sorted(assignments))
    actual_state_id = ordered_state_ids[1]
    actual_source = assignments[actual_state_id][2]
    condition_by_assignment_id = {
        assignments[ordered_state_ids[0]][0].assignment_id: make_public_state_condition(
            context.task.task_id,
            compact_variation,
        ),
        assignments[ordered_state_ids[1]][0].assignment_id: make_public_state_condition(
            context.task.task_id,
            expanded_variation,
        ),
    }
    catalog = make_trajectory_state_catalog(
        tuple(assignments[state_id] for state_id in ordered_state_ids),
        state_space_compilation=compilation,
        discovery_method="verified_test_exploration",
        revision_reason="test_off_target_trace_is_not_released_dedup_state",
        public_conditions_by_assignment_id=condition_by_assignment_id,
    )
    distribution = make_conditional_distribution(
        context.task.task_id,
        {state_id: 0.5 for state_id in ordered_state_ids},
        round_index=1,
    )
    provider = _AlwaysActualStateProvider(actual_source)
    roles = _role_contract(provider.provider_id)

    artifacts, report = ValidTrajectoryStateMaterializer(provider, evaluator).materialize(
        context,
        catalog,
        distribution,
        roles,
        total_budget=2,
        requested_state_counts={state_id: 1 for state_id in ordered_state_ids},
        maximum_attempt_multiplier=1,
        seed=31,
    )

    assert len(artifacts) == 1
    assert artifacts[0].target_state.state_id == actual_state_id
    assert report.off_target_state_counts[ordered_state_ids[0]] == 1
    assert report.observed_state_counts_by_target[ordered_state_ids[0]] == {
        actual_state_id: 1
    }
    assert report.observed_state_counts_by_target[actual_state_id] == {
        actual_state_id: 1
    }
    assert "duplicate_decision_trace" not in report.failure_counts
    assert report.failure_counts["target_quota_unfilled"] == 1


def test_materializer_rejects_reidentified_discovery_decision_trace() -> None:
    _, compiled, candidate, evaluator, context = _case_runtime(0)
    report = evaluator.evaluate(context, candidate)
    assignment = map_trajectory_to_state(
        context,
        candidate,
        program_node_aliases=report.program_node_mapping,
    )
    state_space_compilation = compile_trajectory_state_space(
        compiled.joint_compilation,
        _TestVariationProvider((observed_variation(report.attributes),)),
    )
    catalog = make_trajectory_state_catalog(
        ((assignment, report, candidate),),
        state_space_compilation=state_space_compilation,
        discovery_method="verified_test_exploration",
        revision_reason="test_decision_trace_reuse_guard",
    )
    distribution = make_conditional_distribution(
        context.task.task_id,
        {assignment.state.state_id: 1.0},
        round_index=1,
    )
    provider = _ReplayDecisionTraceProvider(candidate)
    roles = _role_contract(provider.provider_id)

    artifacts, materialization = ValidTrajectoryStateMaterializer(
        provider,
        evaluator,
    ).materialize(
        context,
        catalog,
        distribution,
        roles,
        total_budget=2,
        seed=23,
    )

    assert artifacts == ()
    assert materialization.status == "blocked"
    assert materialization.failure_counts["discovery_decision_trace_reuse"] == 6
    assert "discovery_trajectory_reuse" not in materialization.failure_counts


def test_materializer_freezes_independent_invalid_trajectory_reports() -> None:
    _, compiled, candidate, evaluator, context = _case_runtime(0)
    valid_report = evaluator.evaluate(context, candidate)
    assignment = map_trajectory_to_state(
        context,
        candidate,
        program_node_aliases=valid_report.program_node_mapping,
    )
    compilation = compile_trajectory_state_space(
        compiled.joint_compilation,
        _TestVariationProvider((observed_variation(valid_report.attributes),)),
    )
    catalog = make_trajectory_state_catalog(
        ((assignment, valid_report, candidate),),
        state_space_compilation=compilation,
        discovery_method="verified_test_exploration",
        revision_reason="test_invalid_materialization_audit",
    )
    distribution = make_conditional_distribution(
        context.task.task_id,
        {assignment.state.state_id: 1.0},
        round_index=1,
    )
    invalid = _trajectory_variant(
        candidate,
        "invalid-materialization-audit",
        remove_citations=True,
    )
    provider = _CatalogTrajectoryProvider(
        catalog,
        {assignment.state.state_id: invalid},
    )
    roles = _role_contract(provider.provider_id)

    artifacts, report = ValidTrajectoryStateMaterializer(provider, evaluator).materialize(
        context,
        catalog,
        distribution,
        roles,
        total_budget=1,
        maximum_attempt_multiplier=1,
        seed=43,
    )

    assert artifacts == ()
    assert report.failure_counts["invalid_trajectory"] == 1
    assert len(report.rejected_trajectories) == 1
    rejection = report.rejected_trajectories[0]
    assert rejection.target_state_id == assignment.state.state_id
    assert rejection.trajectory.trajectory_id != candidate.trajectory_id
    assert not rejection.validity_report.valid
    assert rejection.validity_report.failure_types


def test_materializer_preserves_independent_draws_with_one_decision_structure() -> None:
    _, compiled, candidate, evaluator, context = _case_runtime(0)
    report = evaluator.evaluate(context, candidate)
    assignment = map_trajectory_to_state(
        context,
        candidate,
        program_node_aliases=report.program_node_mapping,
    )
    state_space_compilation = compile_trajectory_state_space(
        compiled.joint_compilation,
        _TestVariationProvider((observed_variation(report.attributes),)),
    )
    catalog = make_trajectory_state_catalog(
        ((assignment, report, candidate),),
        state_space_compilation=state_space_compilation,
        discovery_method="verified_test_exploration",
        revision_reason="test_independent_draws_do_not_bias_structural_modes",
    )
    distribution = make_conditional_distribution(
        context.task.task_id,
        {assignment.state.state_id: 1.0},
        round_index=1,
    )
    provider = _ReplayDecisionTraceProvider(candidate)
    roles = _role_contract(provider.provider_id)

    artifacts, materialization = ValidTrajectoryStateMaterializer(
        provider,
        evaluator,
    ).materialize(
        context,
        catalog,
        distribution,
        roles,
        total_budget=3,
        seed=29,
        realization_uniqueness_policy="independent_trajectory_draws",
    )

    assert materialization.status == "passed"
    assert materialization.realization_uniqueness_policy == "independent_trajectory_draws"
    assert len(artifacts) == 3
    assert provider.yield_count == 3
    assert materialization.unique_trajectory_hash_count == 3
    assert materialization.unique_decision_trace_count == 1
    assert "discovery_decision_trace_reuse" not in materialization.failure_counts
    assert "duplicate_decision_trace" not in materialization.failure_counts


class _ReplayDecisionTraceProvider:
    provider_id = "decision_trace_replay_provider:test"
    provider_version = "1.0.0"

    def __init__(self, source: Trajectory) -> None:
        self._source = source
        self.yield_count = 0

    def generate(self, request):
        for index in range(request.candidate_count):
            self.yield_count += 1
            yield _trajectory_variant(
                self._source,
                f"reidentified-discovery-{request.seed}-{index}",
                generator_version=f"runtime-{index}",
            )


class _AlwaysActualStateProvider:
    provider_id = "always_actual_state_provider:test"
    provider_version = "1.0.0"

    def __init__(self, source: Trajectory) -> None:
        self._source = source

    def generate(self, request):
        for index in range(request.candidate_count):
            yield _trajectory_variant(
                self._source,
                f"actual-state-{request.seed}-{index}",
                generator_version=f"materializer-{request.seed}-{index}",
                search_variant="shared-materialized-route",
            )


class _TestVariationProvider:
    variation_provider_id = "test_public_variation_provider"
    variation_provider_version = "1.0.0"

    def __init__(self, variations) -> None:
        self._variations = variations

    def compile_variations(self, context):
        del context
        return self._variations


class _ReplayDiscoveryTrajectoryProvider:
    provider_id = "discovery_replay_provider:test"
    provider_version = "1.0.0"

    def __init__(self, source: Trajectory) -> None:
        self._source = source

    def generate(self, request):
        for _ in range(request.candidate_count):
            yield self._source


class _CatalogTrajectoryProvider:
    provider_id = "state_catalog_provider:test"
    provider_version = "1.0.0"

    def __init__(self, catalog, sources: dict[str, Trajectory]) -> None:
        self._sources = {
            catalog.public_state_conditions[state_id].condition_id: source
            for state_id, source in sources.items()
        }

    def generate(self, request):
        source = self._sources[request.state_condition.condition_id]
        for index in range(request.candidate_count):
            yield _trajectory_variant(
                source,
                f"state-conditioned-{request.seed}-{index}",
                search_variant=f"query-route-{request.seed}-{index}",
            )


class _TrajectoryProvider:
    provider_id = "trajectory_provider:test"
    provider_version = "1.0.0"

    def __init__(self, trajectories: tuple[Trajectory, ...]) -> None:
        self._trajectories = trajectories

    def generate(
        self,
        context,
        target_profile,
        *,
        candidate_count: int,
        seed: int,
    ):
        del context, target_profile, candidate_count, seed
        yield from self._trajectories


class _StateTrajectoryProvider:
    provider_id = "state_trajectory_provider:test"
    provider_version = "1.0.0"

    def __init__(self, source: Trajectory) -> None:
        self._source = source

    def generate(self, request):
        for index in range(request.candidate_count):
            yield _trajectory_variant(
                self._source,
                f"exploration-{index}",
                search_variant=f"exploration-route-{request.seed}-{index}",
            )


def _case_runtime(index: int):
    case = build_contract_cases()[index]
    contract_compiler = QualityContractCompiler(
        case.registry,
        domain_provider=case.quality_clause_provider,
    )
    compiled = ProofCarryingSampleCompiler(
        case.registry,
        contract_compiler,
        case.plugin_set,
        semantic_policy=case.semantic_policy,
    ).compile(
        case.task,
        case.bundle,
        case.proof_graph,
        public_corpus=case.corpus,
    )
    candidate = PlanGivenContractCandidate(case.registry).generate(
        case.task.public,
        InMemoryEvidenceToolRuntime(case.corpus),
    )
    verifier = CandidateWorkflowVerifier(
        case.registry,
        semantic_policy=case.semantic_policy,
    )
    evaluator = TrajectoryValidityEvaluator(
        verifier,
        contract_runtime=QualityContractRuntime(
            verifier,
            verifier_registry=contract_compiler.verifier_registry,
        ),
    )
    context = compiled.joint_compilation.omega
    return case, compiled, candidate, evaluator, context


def _expanded_retrieval_variant(
    source: Trajectory,
    corpus_evidence_ids: tuple[str, ...],
) -> Trajectory:
    steps = tuple(
        step.model_copy(
            update={
                "tool_input": {
                    **step.tool_input,
                    "retrieval_policy": "expanded_context",
                },
                "observation": {
                    **step.observation,
                    "matched_count": len(corpus_evidence_ids),
                },
                "evidence_ids": corpus_evidence_ids,
            }
        )
        if step.action.value == "search"
        else step
        for step in source.steps
    )
    return source.model_copy(
        update={
            "trajectory_id": canonical_hash(
                {"source": source.trajectory_id, "variant": "expanded-retrieval"},
                prefix="trajectory_variant:",
            ),
            "steps": steps,
        }
    )


def _trajectory_variant(
    source: Trajectory,
    label: str,
    *,
    remove_citations: bool = False,
    mutate_result: bool = False,
    replace_evidence: bool = False,
    workflow_kind: WorkflowKind | None = None,
    generator_version: str | None = None,
    search_variant: str | None = None,
) -> Trajectory:
    replacement = "evidence:synthetic:semantically-different@v1"
    steps = []
    for step in source.steps:
        evidence_ids = step.evidence_ids
        input_refs = step.input_refs
        if replace_evidence and evidence_ids:
            original = evidence_ids[0]
            evidence_ids = tuple(replacement if item == original else item for item in evidence_ids)
            input_refs = tuple(item.replace(original, replacement) for item in input_refs)
        tool_input = step.tool_input
        if search_variant is not None and step.action.value == "search":
            tool_input = {**tool_input, "query_variant": search_variant}
        steps.append(
            step.model_copy(
                update={
                    "tool_input": tool_input,
                    "evidence_ids": evidence_ids,
                    "input_refs": input_refs,
                    "rationale_summary": f"{step.rationale_summary} {label}",
                }
            )
        )
    answer = deepcopy(source.final_answer)
    if remove_citations:
        answer["citations"] = []
    if mutate_result:
        result = dict(answer["result"])
        result[next(iter(result))] = "semantically-different-result"
        answer["result"] = result
    if replace_evidence:
        for citation in answer.get("citations", []):
            citation["evidence_id"] = replacement
    return source.model_copy(
        update={
            "trajectory_id": canonical_hash(
                {"source": source.trajectory_id, "variant": label},
                prefix="trajectory_variant:",
            ),
            "workflow_kind": workflow_kind or source.workflow_kind,
            "steps": tuple(steps),
            "final_answer": answer,
            "generator_version": generator_version or source.generator_version,
        }
    )


def _reorder_independent_legal_steps(source: Trajectory) -> Trajectory:
    steps = list(source.steps)
    first = next(index for index, step in enumerate(steps) if step.program_node_id == "apply_1")
    second = next(index for index, step in enumerate(steps) if step.program_node_id == "apply_2")
    steps[first], steps[second] = steps[second], steps[first]
    reindexed = tuple(
        step.model_copy(update={"step_index": index}) for index, step in enumerate(steps, start=1)
    )
    return source.model_copy(
        update={
            "trajectory_id": canonical_hash(
                {"source": source.trajectory_id, "variant": "dependency-reorder"},
                prefix="trajectory_variant:",
            ),
            "steps": reindexed,
        }
    )


def _probe(
    condition: str,
    state_id: str,
    *,
    baseline: float,
    intervention: float,
    state_ids: tuple[str, ...] = ("state:a", "state:b"),
    round_index: int = 0,
    seed: int = 7,
):
    data = make_contribution_data_isolation_contract(
        task_condition_id=condition,
        baseline_training_set_id=f"train:{condition}",
        baseline_training_instance_ids=tuple(f"{condition}:train:{index}" for index in range(19)),
        probe_update_instance_ids_by_state={
            candidate_state_id: (f"{condition}:probe:{candidate_state_id}",)
            for candidate_state_id in state_ids
        },
        internal_validation_set_id="eval:fixed-v1",
        internal_validation_instance_ids=tuple(
            f"{condition}:validation:{index}" for index in range(8)
        ),
        final_test_set_id=f"test:{condition}",
        final_test_instance_ids=(f"{condition}:final-test:0",),
    )
    metric = make_contribution_metric_contract(
        target_metric_id="metric:task-success",
        evaluation_distribution_id="eval:fixed-v1",
        evaluation_snapshot_hash="eval-snapshot:fixed-v1",
        score_transform="identity",
    )
    protocol = make_contribution_probe_protocol(
        beneficiary_model_state_id="model:qwen-round-3",
        beneficiary_checkpoint_hash="checkpoint:qwen-round-3",
        metric_contract=metric,
        data_isolation=data,
        optimizer=make_probe_optimizer_contract(
            optimizer_name="sgd",
            learning_rate=1e-5,
            step_count=3,
        ),
        probe_seeds=(7, 13),
    )
    return make_contribution_probe_observation(
        task_condition_id=condition,
        round_index=round_index,
        state_id=state_id,
        protocol=protocol,
        seed=seed,
        adaptation_result=ProbeAdaptationResult(
            adapted_model_state_id=(
                f"model:qwen-round-3:probe:{state_id}:round{round_index}:seed{seed}"
            ),
            adapted_checkpoint_hash=(
                f"checkpoint:qwen-round-3:probe:{state_id}:round{round_index}:seed{seed}"
            ),
            base_model_state_id=protocol.beneficiary_model_state_id,
            base_checkpoint_hash=protocol.beneficiary_checkpoint_hash,
            optimizer_contract_id=protocol.optimizer.contract_id,
            initial_optimizer_state_hash=empty_optimizer_state_hash(protocol.optimizer),
            executed_step_count=protocol.optimizer.step_count,
        ),
        baseline_performance=baseline,
        adapted_performance=intervention,
        measurement_confidence=0.9,
    )


def _validity_estimate(
    condition: str,
    state_id: str,
    value: float,
) -> StateValidityEstimate:
    thresholds = ValidityThresholds(reject_below=0.25, accept_at_or_above=0.75)
    attempted = 2 if value == 0.5 else 1
    valid_count = 1 if value in {0.5, 1.0} else 0
    values = {
        "task_condition_id": condition,
        "state_id": state_id,
        "attempted_trajectory_count": attempted,
        "valid_trajectory_count": valid_count,
        "estimated_validity": value,
        "confidence_lower": 0.0 if value < 1.0 else 0.5,
        "confidence_upper": 1.0,
        "mean_component_validity": {"independent_verifier": value},
        "thresholds": thresholds,
        "classification_statistic": "posterior_mean",
        "region": validity_region(value, thresholds),
        "estimator_id": "test_empirical_validity",
        "estimator_version": "1.0.0",
    }
    provisional = StateValidityEstimate.model_construct(estimate_id="pending", **values)
    return StateValidityEstimate(
        estimate_id=state_validity_estimate_id(provisional),
        **values,
    )


def _update_inputs(
    condition: str,
    *,
    probabilities: dict[str, float] | None = None,
    coverage_probabilities: dict[str, float] | None = None,
):
    probabilities = probabilities or {"state:a": 0.8, "state:b": 0.2}
    coverage_probabilities = coverage_probabilities or {
        "state:a": 0.5,
        "state:b": 0.5,
    }
    prior = make_conditional_distribution(condition, probabilities, round_index=0)
    coverage = make_coverage_prior(
        condition,
        coverage_probabilities,
        policy="frozen_target_coverage",
    )
    state_ids = tuple(sorted(probabilities))
    observations = tuple(
        make_synthetic_oracle_contribution_observation(
            task_condition_id=condition,
            round_index=prior.round_index,
            state_id=state_id,
            oracle_contribution=0.1 + index * 0.3,
            oracle_protocol_hash="synthetic-update-equation:test-v1",
        )
        for index, state_id in enumerate(state_ids)
    )
    manifest = estimate_synthetic_oracle_contributions(prior, observations)
    validity = tuple(_validity_estimate(condition, state_id, 1.0) for state_id in state_ids)
    config = AnchoredEnergyConfig(
        epsilon=0.01,
        contribution_temperature=0.2,
        novelty_temperature=1.0,
        contribution_weight=0.5,
        novelty_weight=0.5,
        history_kl_weight=2.0,
        coverage_kl_weight=1.0,
    )
    return (
        prior,
        coverage,
        validity,
        manifest,
        None,
        config,
        _role_contract(
            "provider:explorer-v1",
            beneficiary_model_state_id="synthetic_oracle",
        ),
    )


def _role_contract(
    explorer_provider_id: str,
    *,
    beneficiary_model_state_id: str = "model:qwen-round-3",
):
    return make_vtdo_role_contract(
        explorer_provider_id=explorer_provider_id,
        materialization_provider_id=explorer_provider_id,
        beneficiary_model_state_id=beneficiary_model_state_id,
        final_student_model_id="model:qwen-student-round-4",
    )
