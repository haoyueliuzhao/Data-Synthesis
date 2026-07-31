from __future__ import annotations

from copy import deepcopy

import pytest

from trusted_synthesis.core.evaluation.contracts import (
    QualityContractCompiler,
    QualityContractRuntime,
)
from trusted_synthesis.core.feedback import (
    FeedbackExposure,
    make_trajectory_feedback,
    make_trajectory_feedback_batch,
)
from trusted_synthesis.core.refinement import (
    TrajectoryUtilityWeights,
    aggregate_cell_feedback,
    build_observed_policy,
    make_synthesis_cell,
    update_valid_trajectory_policy,
)
from trusted_synthesis.core.synthesis import ProofCarryingSampleCompiler
from trusted_synthesis.core.trajectory import (
    TrajectoryValidityEvaluator,
    ValidTrajectoryMaterializer,
    ValidTrajectoryPoolBuilder,
    make_trajectory_verification_context,
)
from trusted_synthesis.core.trajectory.candidate_verifier import (
    CandidateWorkflowVerifier,
)
from trusted_synthesis.core.trajectory.schema import Trajectory
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


def test_valid_pool_retains_alternative_legal_trajectories_and_rejects_bad_answer() -> None:
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
    assert pool.rejected_trajectory_ids == (invalid.trajectory_id,)
    assert pool.diversity_pruned_trajectory_ids == (alternative.trajectory_id,)
    assert set(pool.capability_coverage) == {
        "citation",
        "evidence_selection",
        "multi_step_reasoning",
        "retrieval",
        "verification",
    }


def test_valid_trajectory_materializer_generates_and_verifies_multiple_paths() -> None:
    _, _, candidate, evaluator, context = _case_runtime(0)
    alternative = _trajectory_variant(candidate, "materialized-alternative")
    invalid = _trajectory_variant(candidate, "materialized-invalid", remove_citations=True)
    target = evaluator.evaluate(context, candidate).attributes.profile
    materializer = ValidTrajectoryMaterializer(
        _TrajectoryProvider((candidate, alternative, invalid)),
        evaluator,
    )

    pool, report = materializer.materialize(
        context,
        target,
        candidate_count=3,
        minimum_valid_count=1,
        seed=19,
        max_per_profile=1,
    )

    assert pool is not None
    assert report.status == "passed"
    assert report.generated_candidate_count == 3
    assert report.verified_candidate_count == 3
    assert report.retained_valid_count == 1
    assert pool.verified_valid_count == 2


def test_valid_trajectory_update_rewards_verified_capability_not_invalid_path() -> None:
    reports = []
    cells = {}
    task_cells = {}
    trajectory_feedback = []
    for index in (0, 1):
        case, _, candidate, evaluator, context = _case_runtime(index)
        if index == 1:
            candidate = _trajectory_variant(
                candidate,
                "invalid-answer",
                mutate_result=True,
            )
        report = evaluator.evaluate(context, candidate)
        reports.append(report)
        task_id = case.task.task_id
        cell = make_synthesis_cell(
            pattern_id=case.task.public.task_type,
            binding_stratum_id=f"binding:{index}",
            difficulty_bucket="hard",
            distractor_profile_id="distractor:contract",
            trajectory_attribute_profile=report.attributes.profile,
        )
        cells[index] = cell
        task_cells[task_id] = cell
        trajectory_feedback.append(
            make_trajectory_feedback(
                task_id=task_id,
                configuration_id=cell.cell_id,
                report=report,
                diversity_contribution=1.0 if report.valid else 0.0,
                target_profile=cell.trajectory_attribute_profile,
            )
        )
    exposures = tuple(
        FeedbackExposure(
            task_id=task_id,
            domain="contract_fixture",
            pattern_id=cell.pattern_id,
            failure_family="trajectory_validity",
        )
        for task_id, cell in task_cells.items()
    )
    policy = build_observed_policy(task_cells)
    statistics = aggregate_cell_feedback(
        policy,
        exposures,
        (),
        task_cells,
        trajectory_feedback=trajectory_feedback,
    )
    update = update_valid_trajectory_policy(
        policy,
        statistics,
        (),
        eta=1.0,
        total_budget=20,
        calibration_manifest_hash="calibration:trajectory",
        trajectory_feedback_manifest_hash=canonical_hash(
            tuple(item.feedback_id for item in trajectory_feedback),
            prefix="trajectory_feedback_manifest:",
        ),
        weights=TrajectoryUtilityWeights(
            alpha_validity=1.0,
            beta_coverage=0.0,
            gamma_diversity=0.0,
            lambda_defect=0.0,
        ),
    )

    assert reports[0].valid
    assert not reports[1].valid
    assert update.algorithm_id == "valid_trajectory_distribution_optimization"
    assert update.utility_mode == "valid_trajectory_objective"
    assert update.cell_utility_components[cells[0].cell_id].validity_reward == 1
    assert update.cell_utility_components[cells[1].cell_id].validity_reward == 0
    assert update.next_policy.probabilities[cells[0].cell_id] > (
        policy.probabilities[cells[0].cell_id]
    )
    assert update.prior_trajectory_metrics is not None
    assert update.next_trajectory_metrics is not None
    assert update.trajectory_feedback_count == 2


def test_invalid_trajectory_profiles_do_not_inflate_valid_diversity() -> None:
    case, _, candidate, evaluator, context = _case_runtime(0)
    invalid = _trajectory_variant(candidate, "invalid-profile", remove_citations=True)
    reports = (
        evaluator.evaluate(context, candidate),
        evaluator.evaluate(context, invalid),
    )
    cell = make_synthesis_cell(
        pattern_id=case.task.public.task_type,
        binding_stratum_id="binding:valid-diversity",
        difficulty_bucket="hard",
        distractor_profile_id="distractor:contract",
        trajectory_attribute_profile=reports[0].attributes.profile,
    )
    task_cells = {case.task.task_id: cell}
    exposures = (
        FeedbackExposure(
            task_id=case.task.task_id,
            domain="contract_fixture",
            pattern_id=cell.pattern_id,
            failure_family="trajectory_validity",
        ),
    )
    trajectory_ids = {item.trajectory_id for item in reports}
    feedback = make_trajectory_feedback_batch(
        reports,
        task_ids={item: case.task.task_id for item in trajectory_ids},
        configuration_ids={item: cell.cell_id for item in trajectory_ids},
    )
    policy = build_observed_policy(task_cells)
    statistics = aggregate_cell_feedback(
        policy,
        exposures,
        (),
        task_cells,
        trajectory_feedback=feedback,
    )[0]

    assert statistics.trajectory_attempt_count == 2
    assert statistics.valid_trajectory_count == 1
    assert statistics.trajectory_attribute_profile_count == 1
    assert statistics.trajectory_attribute_entropy == 0
    assert statistics.trajectory_diversity_gain == 0


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
) -> Trajectory:
    steps = tuple(
        step.model_copy(update={"rationale_summary": f"{step.rationale_summary} {label}"})
        for step in source.steps
    )
    answer = deepcopy(source.final_answer)
    if remove_citations:
        answer["citations"] = []
    if mutate_result:
        result = dict(answer["result"])
        result[next(iter(result))] = "invalid-result"
        answer["result"] = result
    return source.model_copy(
        update={
            "trajectory_id": canonical_hash(
                {"source": source.trajectory_id, "variant": label},
                prefix="trajectory_variant:",
            ),
            "steps": steps,
            "final_answer": answer,
        }
    )
