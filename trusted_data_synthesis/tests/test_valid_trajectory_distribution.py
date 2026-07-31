from __future__ import annotations

import math
from copy import deepcopy

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
    StateConditionedTrajectoryExplorer,
    ValidityRegion,
    ValidityThresholds,
    ValidTrajectoryStateMaterializer,
    VTDORoundArtifact,
    allocate_exploration_budget,
    apply_conditional_updates,
    assemble_vtdo_round,
    condition_on_accepted_support,
    estimate_contributions_from_probes,
    estimate_exploration_state_validity,
    estimate_importance_weighted_pushforward,
    estimate_pushforward_distribution,
    estimate_state_validity,
    make_conditional_distribution,
    make_contribution_probe_observation,
    make_exploration_distribution,
    make_state_validity_partition,
    make_task_conditioned_policy,
    make_trajectory_state_catalog,
    make_uniform_coverage_prior,
    make_vtdo_role_contract,
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
from trusted_synthesis.hashing import canonical_hash
from trusted_synthesis.runtime import InMemoryEvidenceToolRuntime


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
        "reference_semantics": "one_valid_example_not_unique_gold",
    }
    assert context.oracle_specification == compiled.oracle_execution_specification

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


def test_same_quotient_state_can_contain_valid_and_invalid_realizations() -> None:
    _, _, candidate, evaluator, context = _case_runtime(0)
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
        _probe("task:x", "state:a", baseline=0.50, intervention=0.60),
        _probe("task:x", "state:b", baseline=0.50, intervention=0.90),
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
    prior, coverage, validity, manifest, config, roles = _update_inputs("task:x")

    update = update_valid_trajectory_distribution(
        prior,
        coverage,
        validity,
        manifest,
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
    prior, coverage, validity, manifest, config, _ = _update_inputs("task:x")
    wrong_roles = make_vtdo_role_contract(
        explorer_provider_id="provider:explorer-v1",
        beneficiary_model_state_id="model:another-beneficiary",
        final_student_model_id="model:qwen-student-round-4",
    )

    with pytest.raises(ValueError, match="role contract"):
        update_valid_trajectory_distribution(
            prior,
            coverage,
            validity,
            manifest,
            config,
            wrong_roles,
        )


def test_validity_is_a_noncompensable_gate_and_conditions_training_support() -> None:
    prior, coverage, validity, manifest, config, roles = _update_inputs("task:x")
    quarantined = _validity_estimate("task:x", "state:b", 0.5)

    with pytest.raises(ValueError, match="non-Accepted"):
        update_valid_trajectory_distribution(
            prior,
            coverage,
            (validity[0], quarantined),
            manifest,
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
    _, _, candidate, evaluator, context = _case_runtime(0)
    report = evaluator.evaluate(context, candidate)
    target = map_trajectory_to_state(
        context,
        candidate,
        program_node_aliases=report.program_node_mapping,
    ).state
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
        {target.state_id: target},
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


def test_vtdo_roles_are_distinct_unless_sharing_is_explicitly_declared() -> None:
    with pytest.raises(ValueError, match="distinct"):
        make_vtdo_role_contract(
            explorer_provider_id="model:shared",
            beneficiary_model_state_id="model:shared",
            final_student_model_id="model:student",
        )

    shared = make_vtdo_role_contract(
        explorer_provider_id="model:shared",
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


def test_round_artifact_replays_exploration_estimation_update_and_materialization() -> None:
    _, _, candidate, evaluator, context = _case_runtime(0)
    invalid = _trajectory_variant(candidate, "catalog-invalid", mutate_result=True)
    valid_report = evaluator.evaluate(context, candidate)
    invalid_report = evaluator.evaluate(context, invalid)
    valid_state = map_trajectory_to_state(
        context,
        candidate,
        program_node_aliases=valid_report.program_node_mapping,
    ).state
    invalid_state = map_trajectory_to_state(
        context,
        invalid,
        program_node_aliases=invalid_report.program_node_mapping,
    ).state
    assert valid_report.valid
    assert not invalid_report.valid
    assert valid_state.state_id != invalid_state.state_id

    catalog = make_trajectory_state_catalog(
        (valid_state, invalid_state),
        revision_reason="test_initial_state_discovery",
    )
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
        {
            valid_state.state_id: candidate,
            invalid_state.state_id: invalid,
        }
    )
    roles = _role_contract(provider.provider_id)
    batch = StateConditionedTrajectoryExplorer(provider, evaluator).explore(
        context,
        catalog.states,
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

    round_artifact = assemble_vtdo_round(
        state_catalog=catalog,
        role_contract=roles,
        exploration=exploration,
        exploration_batch=batch,
        pushforward_estimate=pushforward,
        validity_partition=partition,
        contribution_probes=(
            _probe(
                context.task.task_id,
                valid_state.state_id,
                baseline=0.5,
                intervention=0.7,
            ),
        ),
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

    wrong_probe = _probe(
        context.task.task_id,
        valid_state.state_id,
        baseline=0.5,
        intervention=0.9,
    )
    round_values = {
        field: getattr(round_artifact, field)
        for field in type(round_artifact).model_fields
        if field != "round_id"
    }
    round_values["contribution_probes"] = (wrong_probe,)
    with pytest.raises(ValueError, match="does not replay its probes"):
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
    assert len(artifacts) == 3
    assert all(item.assignment.state == valid_state for item in artifacts)
    assert all(item.context.task == context.task for item in artifacts)
    assert all(item.context.evidence_bundle == context.evidence_bundle for item in artifacts)


class _CatalogTrajectoryProvider:
    provider_id = "state_catalog_provider:test"
    provider_version = "1.0.0"

    def __init__(self, sources: dict[str, Trajectory]) -> None:
        self._sources = sources

    def generate(
        self,
        context,
        target_state,
        *,
        candidate_count: int,
        seed: int,
    ):
        del context
        source = self._sources[target_state.state_id]
        for index in range(candidate_count):
            yield _trajectory_variant(
                source,
                f"state-conditioned-{target_state.state_id}-{seed}-{index}",
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

    def generate(
        self,
        context,
        target_state,
        *,
        candidate_count: int,
        seed: int,
    ):
        del context, target_state, seed
        for index in range(candidate_count):
            yield _trajectory_variant(self._source, f"exploration-{index}")


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
    context = make_trajectory_verification_context(
        case.task,
        case.bundle,
        case.corpus,
        case.proof_graph,
        compiled.quality_contract,
        compiled.oracle_execution_specification,
    )
    return case, compiled, candidate, evaluator, context


def _trajectory_variant(
    source: Trajectory,
    label: str,
    *,
    remove_citations: bool = False,
    mutate_result: bool = False,
    replace_evidence: bool = False,
    workflow_kind: WorkflowKind | None = None,
    generator_version: str | None = None,
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
        steps.append(
            step.model_copy(
                update={
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
):
    return make_contribution_probe_observation(
        task_condition_id=condition,
        state_id=state_id,
        beneficiary_model_state_id="model:qwen-round-3",
        target_evaluation_distribution_id="eval:fixed-v1",
        target_metric_id="metric:task-success",
        probe_protocol_hash="probe:paired-sft-v1",
        baseline_metric_value=baseline,
        intervention_metric_value=intervention,
        confidence=0.9,
        sample_count=8,
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
    probes = tuple(
        _probe(
            condition,
            state_id,
            baseline=0.5,
            intervention=0.6 if index == 0 else 0.9,
        )
        for index, state_id in enumerate(state_ids)
    )
    manifest = estimate_contributions_from_probes(prior, probes)
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
    return prior, coverage, validity, manifest, config, _role_contract("provider:explorer-v1")


def _role_contract(explorer_provider_id: str):
    return make_vtdo_role_contract(
        explorer_provider_id=explorer_provider_id,
        beneficiary_model_state_id="model:qwen-round-3",
        final_student_model_id="model:qwen-student-round-4",
    )
