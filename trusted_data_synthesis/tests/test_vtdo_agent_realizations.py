from __future__ import annotations

import hashlib
import json
import os

import pytest

from trusted_synthesis.core.evaluation.contracts import (
    QualityContractCompiler,
    QualityContractRuntime,
)
from trusted_synthesis.core.synthesis import ProofCarryingSampleCompiler
from trusted_synthesis.core.task.schema import PlanningTrack, RetrievalTrack
from trusted_synthesis.core.trajectory import (
    TrajectoryValidityEvaluator,
    map_trajectory_to_state,
)
from trusted_synthesis.core.trajectory.candidate_verifier import CandidateWorkflowVerifier
from trusted_synthesis.core.vtdo import (
    estimate_pushforward_distribution,
    make_conditional_distribution,
    make_public_state_condition,
    make_public_state_generation_request,
    make_uniform_coverage_prior,
)
from trusted_synthesis.domains.finance.verification import FinanceClaimVerifier
from trusted_synthesis.experiments.counterfactual_finance_fixture import (
    build_finance_counterfactual_case,
)
from trusted_synthesis.experiments.vtdo_experiment.multistate import (
    FinanceDeterministicStateFixtureProvider,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_agent_population import (
    AGENT_DISCOVERY_STRATEGIES,
    compile_finance_agent_case,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_initial_distribution import (
    FINANCE_INITIAL_DISTRIBUTION_VERSION,
    FinanceInitialDistributionReport,
    _record_is_reusable,
    finance_initial_distribution_report_id,
    finance_initial_distribution_run_identity,
    finance_unconditioned_explorer_provider_id,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_reachability import (
    _load_model_config,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_state_realizations import (
    MINIMUM_PARTIAL_INITIAL_CATALOG_HIT_RATE,
    MINIMUM_PARTIAL_INITIAL_CATALOG_HITS_PER_TASK,
    PartialInitialDistributionQualification,
    choose_realization_budget,
    finance_state_materialization_provider_id,
    partial_initial_distribution_qualification_id,
    validate_initial_distribution_lineage,
)
from trusted_synthesis.runtime.agent.client import LLMClientError
from trusted_synthesis.runtime.agent.host_execution import ActionPlanExecutionError
from trusted_synthesis.runtime.agent.llm_agent import (
    LLM_AGENT_SOLVER_VERSION,
    _state_search_contract,
    _validate_state_control_action_plan,
)
from trusted_synthesis.runtime.agent.schema import (
    AgentActionDecision,
    AgentActionInput,
    AgentActionPlanContract,
)
from trusted_synthesis.runtime.agent.state_conditioned import (
    StateConditionedLLMTrajectoryProvider,
    assess_state_condition_controllability,
    project_state_condition_constraints,
)


def _agent_runtime():
    case = compile_finance_agent_case(build_finance_counterfactual_case(2))
    contract_compiler = QualityContractCompiler(
        case.registry,
        domain_provider=case.quality_clause_provider,
    )
    compiled = ProofCarryingSampleCompiler(
        case.registry,
        contract_compiler,
        case.plugin_set,
        semantic_policy=case.semantic_policy,
        source_grounding_verifier=case.source_grounding_verifier,
    ).compile(
        case.task,
        case.bundle,
        case.proof_graph,
        public_corpus=case.corpus,
    )
    verifier = CandidateWorkflowVerifier(
        case.registry,
        semantic_policy=case.semantic_policy,
        claim_verifier=FinanceClaimVerifier(),
        source_grounding_verifier=case.source_grounding_verifier,
    )
    evaluator = TrajectoryValidityEvaluator(
        verifier,
        contract_runtime=QualityContractRuntime(
            verifier,
            verifier_registry=contract_compiler.verifier_registry,
        ),
    )
    fixture_provider = FinanceDeterministicStateFixtureProvider()
    trajectory = fixture_provider.generate_fixture(
        compiled.joint_compilation.omega,
        case.registry,
        "compact_direct",
    )
    validity = evaluator.evaluate(compiled.joint_compilation.omega, trajectory)
    assert validity.valid
    assignment = map_trajectory_to_state(
        compiled.joint_compilation.omega,
        trajectory,
        program_node_aliases=validity.program_node_mapping,
    )
    return compiled.joint_compilation.omega, fixture_provider, assignment


def _file_sha256(path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_model_config_loads_private_project_env_without_changing_routing(
    tmp_path,
    monkeypatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    env_path = tmp_path / ".env"
    env_path.write_text("DEEPSEEK_API_KEY=test-secret\n", encoding="utf-8")
    env_path.chmod(0o600)
    config_path = tmp_path / "model.json"
    config_path.write_text(
        json.dumps(
            {
                "model": {
                    "provider": "deepseek",
                    "endpoint": "https://api.deepseek.test/v1/chat/completions",
                    "models_endpoint": "https://api.deepseek.test/models",
                    "model": "deepseek-v4-pro",
                    "fallback_models": [],
                    "api_key_env": "DEEPSEEK_API_KEY",
                    "maximum_model_attempts": 1,
                    "require_requested_model": True,
                }
            }
        ),
        encoding="utf-8",
    )

    config = _load_model_config(config_path, temperature=0.6)

    assert os.environ["DEEPSEEK_API_KEY"] == "test-secret"
    assert config.model == "deepseek-v4-pro"
    assert config.fallback_models == ()
    assert config.require_requested_model is True
    assert config.maximum_model_attempts == 1
    assert config.temperature == 0.6
    assert config.interaction_protocol == "host_instrumented"


def test_model_config_rejects_group_readable_project_env(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    env_path = tmp_path / ".env"
    env_path.write_text("DEEPSEEK_API_KEY=test-secret\n", encoding="utf-8")
    env_path.chmod(0o640)
    config_path = tmp_path / "model.json"
    config_path.write_text(
        json.dumps(
            {
                "model": {
                    "provider": "deepseek",
                    "endpoint": "https://api.deepseek.test/v1/chat/completions",
                    "model": "deepseek-v4-pro",
                    "api_key_env": "DEEPSEEK_API_KEY",
                }
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="must not be accessible"):
        _load_model_config(config_path, temperature=0.6)


def _comparison_action_plan(*, projected: bool) -> AgentActionPlanContract:
    evidence_ids = ("evidence:left", "evidence:right")
    if not projected:
        executions = (
            AgentActionDecision(
                operator_id="compare",
                inputs=tuple(
                    AgentActionInput(source="evidence", evidence_id=evidence_id)
                    for evidence_id in evidence_ids
                ),
                rationale_summary="Compare the two evidence values directly.",
            ),
        )
    else:
        executions = (
            AgentActionDecision(
                operator_id="lookup",
                inputs=(AgentActionInput(source="evidence", evidence_id=evidence_ids[0]),),
                rationale_summary="Project the left evidence value.",
            ),
            AgentActionDecision(
                operator_id="lookup",
                inputs=(AgentActionInput(source="evidence", evidence_id=evidence_ids[1]),),
                rationale_summary="Project the right evidence value.",
            ),
            AgentActionDecision(
                operator_id="compare",
                inputs=(
                    AgentActionInput(source="step", step_index=1),
                    AgentActionInput(source="step", step_index=2),
                ),
                rationale_summary="Compare the projected values.",
            ),
        )
    return AgentActionPlanContract(
        plan_summary="Execute the requested comparison.",
        selected_evidence_ids=evidence_ids,
        executions=executions,
        output_step_index=len(executions),
    )


def _execution_constraints(mode: str) -> dict[str, object]:
    return {
        "control_plan": {
            "execution": {
                "mode": mode,
                "control_status": "model_controlled",
            }
        }
    }


class _AlwaysFailingStateSolver:
    interaction_protocol = "host_instrumented"

    def __init__(self) -> None:
        self.call_count = 0

    def solve_with_audit(self, *args, **kwargs):
        self.call_count += 1
        raise LLMClientError("synthetic state-conditioned model failure")


def test_state_execution_control_is_symmetric_and_fail_closed() -> None:
    direct = _comparison_action_plan(projected=False)
    projected = _comparison_action_plan(projected=True)

    _validate_state_control_action_plan(direct, _execution_constraints("baseline_program"))
    _validate_state_control_action_plan(
        projected,
        _execution_constraints("transparent_projection"),
    )
    _validate_state_control_action_plan(
        projected,
        _execution_constraints("program_projection"),
    )
    with pytest.raises(
        ActionPlanExecutionError,
        match="forbids optional lookup projections",
    ):
        _validate_state_control_action_plan(
            projected,
            _execution_constraints("baseline_program"),
        )
    with pytest.raises(
        ActionPlanExecutionError,
        match="requires at least one lookup operation",
    ):
        _validate_state_control_action_plan(
            direct,
            _execution_constraints("transparent_projection"),
        )
    with pytest.raises(
        ActionPlanExecutionError,
        match="requires at least one lookup operation",
    ):
        _validate_state_control_action_plan(
            direct,
            _execution_constraints("program_projection"),
        )


def test_state_conditioned_provider_records_failure_and_continues_candidates() -> None:
    context, fixture_provider, _ = _agent_runtime()
    condition = make_public_state_condition(
        context.task.task_id,
        fixture_provider.variation_for("compact_direct"),
    )
    request = make_public_state_generation_request(
        context,
        condition,
        candidate_count=3,
        seed=19,
    )
    solver = _AlwaysFailingStateSolver()
    provider = StateConditionedLLMTrajectoryProvider(
        provider_id="test_state_provider",
        solver=solver,
        public_corpora_by_task_id={context.task.task_id: context.public_corpus},
    )

    assert tuple(provider.generate(request)) == ()
    assert solver.call_count == 3
    assert len(provider.failure_records) == 3
    assert len({item.failure_id for item in provider.failure_records}) == 3
    assert {item.candidate_index for item in provider.failure_records} == {0, 1, 2}
    assert not provider.records


def test_projection_expanded_state_is_valid_distinct_and_requestable() -> None:
    case = compile_finance_agent_case(build_finance_counterfactual_case(2))
    contract_compiler = QualityContractCompiler(
        case.registry,
        domain_provider=case.quality_clause_provider,
    )
    compiled = ProofCarryingSampleCompiler(
        case.registry,
        contract_compiler,
        case.plugin_set,
        semantic_policy=case.semantic_policy,
        source_grounding_verifier=case.source_grounding_verifier,
    ).compile(
        case.task,
        case.bundle,
        case.proof_graph,
        public_corpus=case.corpus,
    )
    verifier = CandidateWorkflowVerifier(
        case.registry,
        semantic_policy=case.semantic_policy,
        claim_verifier=FinanceClaimVerifier(),
        source_grounding_verifier=case.source_grounding_verifier,
    )
    evaluator = TrajectoryValidityEvaluator(
        verifier,
        contract_runtime=QualityContractRuntime(
            verifier,
            verifier_registry=contract_compiler.verifier_registry,
        ),
    )
    context = compiled.joint_compilation.omega
    guidance = context.task.public.metadata["agent_contract_guidance"]
    assert context.task.public.metadata["domain_plugin_id"] == "finance_tasks.v4"
    assert guidance["comparison"]["input_role_order"] == ("left", "right")
    assert guidance["terminal_operation_contract"]["allowed_operator_ids"] == ("compare",)

    provider = FinanceDeterministicStateFixtureProvider()
    direct = provider.generate_fixture(context, case.registry, "compact_direct")
    projected = provider.generate_fixture(
        context,
        case.registry,
        "compact_projection",
    )
    semantic_projected = provider.generate_fixture(
        context,
        case.registry,
        "semantic_projection",
    )
    direct_validity = evaluator.evaluate(context, direct)
    projected_validity = evaluator.evaluate(context, projected)
    semantic_projected_validity = evaluator.evaluate(context, semantic_projected)

    assert direct_validity.valid
    assert projected_validity.valid
    assert semantic_projected_validity.valid
    direct_assignment = map_trajectory_to_state(
        context,
        direct,
        program_node_aliases=direct_validity.program_node_mapping,
    )
    projected_assignment = map_trajectory_to_state(
        context,
        projected,
        program_node_aliases=projected_validity.program_node_mapping,
    )
    semantic_projected_assignment = map_trajectory_to_state(
        context,
        semantic_projected,
        program_node_aliases=semantic_projected_validity.program_node_mapping,
    )
    assert direct_assignment.state.state_id != projected_assignment.state.state_id
    assert projected_assignment.state.state_id != semantic_projected_assignment.state.state_id
    assert direct_assignment.attributes.operation_count == 1
    assert projected_assignment.attributes.operation_count == 3
    assert semantic_projected_assignment.attributes.operation_count == 3
    assert len(semantic_projected.steps[1].evidence_ids) > len(projected.steps[1].evidence_ids)

    condition = make_public_state_condition(
        context.task.task_id,
        provider.variation_for("compact_projection"),
    )
    assert condition.retrieval_elaboration == "required_only"
    assert condition.execution_elaboration == "transparent_projection"
    assert condition.minimum_reasoning_depth <= projected_validity.attributes.reasoning_depth
    request = make_public_state_generation_request(
        context,
        condition,
        candidate_count=1,
        seed=17,
    )
    audit = assess_state_condition_controllability(
        request,
        interaction_protocol="host_instrumented",
    )
    assert audit.condition_requestable
    assert not audit.blocked_dimensions


def test_agent_recompilation_hides_plan_and_preserves_oracle_semantics() -> None:
    source = build_finance_counterfactual_case(2)
    agent = compile_finance_agent_case(source)

    assert agent.task.public.retrieval_track == RetrievalTrack.SEMI_OPEN
    assert agent.task.public.planning_track == PlanningTrack.PLAN_HIDDEN
    assert agent.task.public.program_skeleton is None
    assert agent.task.oracle.task_program == source.task.oracle.task_program
    assert agent.task.oracle.gold_evidence_ids == source.task.oracle.gold_evidence_ids
    assert agent.task.public.retrieval_scope["aliases"]
    assert agent.task.public.retrieval_scope["partial_constraints"]
    assert agent.task.public.retrieval_scope["corpus_boundary"]
    public_payload = agent.task.public.model_dump_json()
    assert "gold_evidence_ids" not in public_payload
    assert "program_id" not in public_payload


def test_agent_state_catalog_only_contains_requestable_conditions() -> None:
    context, fixture_provider, _ = _agent_runtime()

    conditions_by_strategy = {
        strategy: make_public_state_condition(
            context.task.task_id,
            fixture_provider.variation_for(strategy),
        )
        for strategy in AGENT_DISCOVERY_STRATEGIES
    }
    conditions = tuple(conditions_by_strategy.values())
    assert len({condition.condition_id for condition in conditions}) == len(
        AGENT_DISCOVERY_STRATEGIES
    )
    assert conditions_by_strategy["compact_direct"].retrieval_elaboration == "required_only"
    assert conditions_by_strategy["semantic_direct"].retrieval_elaboration == ("semantic_context")
    assert conditions_by_strategy["broad_direct"].retrieval_elaboration == "full_corpus"
    assert conditions_by_strategy["compact_direct"].execution_elaboration == ("baseline_program")
    assert conditions_by_strategy["semantic_projection"].execution_elaboration == (
        "transparent_projection"
    )
    for condition in conditions:
        request = make_public_state_generation_request(
            context,
            condition,
            candidate_count=1,
            seed=17,
        )
        audit = assess_state_condition_controllability(
            request,
            interaction_protocol="host_instrumented",
        )
        assert audit.condition_requestable
        assert not audit.blocked_dimensions


def test_state_search_contract_provides_mode_specific_public_examples() -> None:
    context, fixture_provider, _ = _agent_runtime()

    contracts = {}
    for strategy in ("compact_direct", "semantic_direct", "broad_direct"):
        condition = make_public_state_condition(
            context.task.task_id,
            fixture_provider.variation_for(strategy),
        )
        request = make_public_state_generation_request(
            context,
            condition,
            candidate_count=1,
            seed=17,
        )
        audit = assess_state_condition_controllability(
            request,
            interaction_protocol="host_instrumented",
        )
        constraints = project_state_condition_constraints(condition, audit)
        contracts[strategy] = _state_search_contract(context.task.public, constraints)

    required = contracts["compact_direct"]
    semantic = contracts["semantic_direct"]
    full = contracts["broad_direct"]
    assert required is not None and semantic is not None and full is not None
    required_query = required["valid_response_example"]["search_query"]
    semantic_query = semantic["valid_response_example"]["search_query"]
    full_query = full["valid_response_example"]["search_query"]
    assert required_query["subject_ids"]
    assert required_query["predicates"]
    assert required_query["temporal_labels"]
    assert semantic_query["subject_ids"] == required_query["subject_ids"]
    assert semantic_query["predicates"] == required_query["predicates"]
    assert "temporal_labels" not in semantic_query
    assert full_query == {}


def test_pushforward_preserves_independent_draws_with_identical_assignment() -> None:
    context, _, assignment = _agent_runtime()
    prior = make_uniform_coverage_prior(
        context.task.task_id,
        (assignment.state.state_id,),
    )

    estimate = estimate_pushforward_distribution(
        (assignment, assignment),
        prior,
        round_index=0,
        prior_strength=1.0,
        observation_ids=("draw:1", "draw:2"),
    )

    assert estimate.total_exposure_count == 2
    assert estimate.state_exposure_counts[assignment.state.state_id] == 2
    assert len(set(estimate.source_observation_ids)) == 2
    with pytest.raises(ValueError, match="independent draws"):
        estimate_pushforward_distribution(
            (assignment, assignment),
            prior,
            round_index=0,
            prior_strength=1.0,
            observation_ids=("draw:1", "draw:1"),
        )


def test_gradient_realization_budget_is_state_balanced_not_pi_weighted() -> None:
    distribution = make_conditional_distribution(
        "task:test",
        {"state:a": 0.97, "state:b": 0.01, "state:c": 0.01, "state:d": 0.01},
        round_index=0,
    )

    assert (
        choose_realization_budget(
            distribution,
            minimum_per_state=3,
            maximum_per_state=5,
        )
        == 12
    )


def test_state_realization_replays_initial_distribution_manifest(tmp_path) -> None:
    artifacts_path = tmp_path / "agent_population.jsonl"
    distributions_path = tmp_path / "initial_distributions.jsonl"
    artifacts_path.write_text("frozen-population\n", encoding="utf-8")
    distribution = make_conditional_distribution(
        "task:test",
        {"state:a": 0.75, "state:b": 0.25},
        round_index=0,
    )
    distributions_path.write_text(
        distribution.model_dump_json() + "\n",
        encoding="utf-8",
    )
    model_config_hash = "agent_model_config:test"
    explorer_provider_id = finance_unconditioned_explorer_provider_id(model_config_hash)
    values = {
        "artifact_sha256": _file_sha256(artifacts_path),
        "model_config_hash": model_config_hash,
        "explorer_provider_id": explorer_provider_id,
        "explorer_provider_version": LLM_AGENT_SOLVER_VERSION,
        "trajectory_records_sha256": "a" * 64,
        "estimate_sha256": "b" * 64,
        "distribution_sha256": _file_sha256(distributions_path),
        "sampling_salt": "test",
        "run_identity": finance_initial_distribution_run_identity(
            artifact_sha256=_file_sha256(artifacts_path),
            model_config_hash=model_config_hash,
            explorer_provider_id=explorer_provider_id,
            explorer_provider_version=LLM_AGENT_SOLVER_VERSION,
            selected_task_ids=("task:test",),
            replicas_per_task=4,
            prior_strength=1.0,
            sampling_salt="test",
            seed=17,
        ),
        "seed": 17,
        "selected_task_ids": ("task:test",),
        "replicas_per_task": 4,
        "prior_strength": 1.0,
        "requested_trajectory_count": 4,
        "recorded_attempt_count": 4,
        "resumed_valid_catalog_count": 0,
        "new_generation_attempt_count": 4,
        "completed_trajectory_count": 4,
        "valid_trajectory_count": 4,
        "catalog_hit_count": 4,
        "off_catalog_valid_count": 0,
        "task_estimate_ids": {"task:test": "estimate:test"},
        "task_distribution_ids": {
            "task:test": distribution.distribution_id,
        },
        "observed_state_counts": {"task:test": {"state:a": 3, "state:b": 1}},
        "valid_catalog_observation_counts": {"task:test": 4},
        "complete_observation_task_count": 1,
        "nonuniform_distribution_count": 1,
        "full_support_distribution_count": 1,
        "failure_counts": {},
        "telemetry": {},
        "status": "passed",
        "schema_version": FINANCE_INITIAL_DISTRIBUTION_VERSION,
    }
    provisional = FinanceInitialDistributionReport.model_construct(
        report_id="pending",
        **values,
    )
    report = FinanceInitialDistributionReport(
        report_id=finance_initial_distribution_report_id(provisional),
        **values,
    )
    incomplete_values = {
        **values,
        "valid_catalog_observation_counts": {"task:test": 3},
        "complete_observation_task_count": 0,
    }
    incomplete = FinanceInitialDistributionReport.model_construct(
        report_id="pending",
        **incomplete_values,
    )
    with pytest.raises(ValueError, match="status is inconsistent"):
        FinanceInitialDistributionReport(
            report_id=finance_initial_distribution_report_id(incomplete),
            **incomplete_values,
        )

    validate_initial_distribution_lineage(
        report,
        artifacts_path=artifacts_path,
        distributions_path=distributions_path,
        distributions={"task:test": distribution},
    )
    assert explorer_provider_id != finance_state_materialization_provider_id(model_config_hash)

    distributions_path.write_text("tampered\n", encoding="utf-8")
    with pytest.raises(ValueError, match="payload hash"):
        validate_initial_distribution_lineage(
            report,
            artifacts_path=artifacts_path,
            distributions_path=distributions_path,
            distributions={"task:test": distribution},
        )


def test_partial_initial_distribution_requires_hashed_development_qualification(
    tmp_path,
) -> None:
    artifacts_path = tmp_path / "agent_population.jsonl"
    distributions_path = tmp_path / "initial_distributions.jsonl"
    initial_report_path = tmp_path / "initial_report.json"
    artifacts_path.write_text("frozen-population\n", encoding="utf-8")
    task_ids = tuple(f"task:{index:02d}" for index in range(30))
    distributions = {
        task_id: make_conditional_distribution(
            task_id,
            {f"{task_id}:state:a": 0.75, f"{task_id}:state:b": 0.25},
            round_index=0,
        )
        for task_id in task_ids
    }
    distributions_path.write_text(
        "".join(distributions[task_id].model_dump_json() + "\n" for task_id in task_ids),
        encoding="utf-8",
    )
    model_config_hash = "agent_model_config:test-partial"
    explorer_provider_id = finance_unconditioned_explorer_provider_id(model_config_hash)
    catalog_counts = {task_id: 8 if index == 0 else 10 for index, task_id in enumerate(task_ids)}
    values = {
        "artifact_sha256": _file_sha256(artifacts_path),
        "model_config_hash": model_config_hash,
        "explorer_provider_id": explorer_provider_id,
        "explorer_provider_version": LLM_AGENT_SOLVER_VERSION,
        "trajectory_records_sha256": "a" * 64,
        "estimate_sha256": "b" * 64,
        "distribution_sha256": _file_sha256(distributions_path),
        "sampling_salt": "test-partial",
        "run_identity": finance_initial_distribution_run_identity(
            artifact_sha256=_file_sha256(artifacts_path),
            model_config_hash=model_config_hash,
            explorer_provider_id=explorer_provider_id,
            explorer_provider_version=LLM_AGENT_SOLVER_VERSION,
            selected_task_ids=task_ids,
            replicas_per_task=10,
            prior_strength=1.0,
            sampling_salt="test-partial",
            seed=19,
        ),
        "seed": 19,
        "selected_task_ids": task_ids,
        "replicas_per_task": 10,
        "prior_strength": 1.0,
        "requested_trajectory_count": 300,
        "recorded_attempt_count": 300,
        "resumed_valid_catalog_count": 0,
        "new_generation_attempt_count": 300,
        "completed_trajectory_count": 300,
        "valid_trajectory_count": 300,
        "catalog_hit_count": 298,
        "off_catalog_valid_count": 2,
        "task_estimate_ids": {task_id: f"estimate:{task_id}" for task_id in task_ids},
        "task_distribution_ids": {
            task_id: distribution.distribution_id for task_id, distribution in distributions.items()
        },
        "observed_state_counts": {
            task_id: {f"{task_id}:state:a": catalog_counts[task_id]} for task_id in task_ids
        },
        "valid_catalog_observation_counts": catalog_counts,
        "complete_observation_task_count": 29,
        "nonuniform_distribution_count": 30,
        "full_support_distribution_count": 30,
        "failure_counts": {},
        "telemetry": {
            "api_call_count": 900,
            "api_call_success_count": 900,
            "json_contract_success_count": 900,
        },
        "status": "partial",
        "schema_version": FINANCE_INITIAL_DISTRIBUTION_VERSION,
    }
    provisional_report = FinanceInitialDistributionReport.model_construct(
        report_id="pending",
        **values,
    )
    report = FinanceInitialDistributionReport(
        report_id=finance_initial_distribution_report_id(provisional_report),
        **values,
    )
    initial_report_path.write_text(report.model_dump_json(), encoding="utf-8")
    qualification_values = {
        "use_case": "development_variance_and_power_only",
        "development_contract_hash": "finance_development_power_contract:test",
        "development_contract_sha256": "c" * 64,
        "materializer_model_config_hash": "agent_model_config:materializer-test",
        "initial_distribution_report_id": report.report_id,
        "initial_distribution_report_sha256": _file_sha256(initial_report_path),
        "artifact_sha256": report.artifact_sha256,
        "distribution_sha256": report.distribution_sha256,
        "trajectory_records_sha256": report.trajectory_records_sha256,
        "selected_task_ids": task_ids,
        "requested_trajectory_count": 300,
        "valid_trajectory_count": 300,
        "catalog_hit_count": 298,
        "off_catalog_valid_count": 2,
        "catalog_hit_rate": 298 / 300,
        "minimum_catalog_hits_per_task": 8,
        "required_minimum_catalog_hits_per_task": (MINIMUM_PARTIAL_INITIAL_CATALOG_HITS_PER_TASK),
        "required_minimum_catalog_hit_rate": (MINIMUM_PARTIAL_INITIAL_CATALOG_HIT_RATE),
        "full_support_distribution_count": 30,
        "api_call_count": 900,
        "api_call_success_count": 900,
        "json_contract_success_count": 900,
        "decision": "passed",
        "schema_version": "partial_initial_distribution_qualification.v2",
    }
    provisional_qualification = PartialInitialDistributionQualification.model_construct(
        qualification_id="pending",
        **qualification_values,
    )
    qualification = PartialInitialDistributionQualification(
        qualification_id=partial_initial_distribution_qualification_id(provisional_qualification),
        **qualification_values,
    )

    with pytest.raises(ValueError, match="explicit qualification"):
        validate_initial_distribution_lineage(
            report,
            artifacts_path=artifacts_path,
            distributions_path=distributions_path,
            distributions=distributions,
            initial_report_path=initial_report_path,
        )
    validate_initial_distribution_lineage(
        report,
        artifacts_path=artifacts_path,
        distributions_path=distributions_path,
        distributions=distributions,
        initial_report_path=initial_report_path,
        qualification=qualification,
    )

    initial_report_path.write_text(
        report.model_dump_json() + "\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="initial_distribution_report_sha256"):
        validate_initial_distribution_lineage(
            report,
            artifacts_path=artifacts_path,
            distributions_path=distributions_path,
            distributions=distributions,
            initial_report_path=initial_report_path,
            qualification=qualification,
        )


def test_initial_distribution_only_resumes_valid_catalog_hits() -> None:
    reusable = {
        "status": "completed",
        "catalog_hit": True,
        "validity_report": {"valid": True},
    }
    assert _record_is_reusable(reusable)
    assert not _record_is_reusable({**reusable, "catalog_hit": False})
    assert not _record_is_reusable({**reusable, "validity_report": {"valid": False}})
    assert not _record_is_reusable({**reusable, "status": "failed"})
