from __future__ import annotations

import hashlib
from collections.abc import Mapping, Sequence
from decimal import Decimal
from typing import Any, NoReturn

from trusted_synthesis.canonical_json import (
    canonical_json_bytes,
    strict_canonical_hash,
    to_canonical_json_data,
)
from trusted_synthesis.core.evaluation.evaluator import CandidateQualityEvaluator
from trusted_synthesis.core.evaluation.schema import ReleaseDecision
from trusted_synthesis.core.evidence.corpus import EvidenceCorpus
from trusted_synthesis.core.graph.builder import ProofGraphBuilder
from trusted_synthesis.core.task.program_depth import derive_program_depth_metrics
from trusted_synthesis.core.trajectory.candidate_verifier import CandidateWorkflowVerifier
from trusted_synthesis.core.trajectory.public_plan_executor import PublicPlanCandidateExecutor
from trusted_synthesis.domains.finance.policy import FinanceSemanticPolicy
from trusted_synthesis.experiments.qa_reasoning_contract_freeze import contracts
from trusted_synthesis.experiments.qa_reasoning_contract_freeze import models as reasoning_models
from trusted_synthesis.experiments.qa_reasoning_fixed_fixture import preflight as primitives
from trusted_synthesis.experiments.qa_reasoning_fixed_fixture.runtime import (
    DurableArtifactWriter,
    admit_preaction_commit,
)
from trusted_synthesis.experiments.qa_semantic_depth_three_catalog_integration.catalog import (
    RegisteredFinanceQACatalog,
    build_catalog_descriptor,
    historical_catalog_snapshot,
)

KINDS = (
    "comparability",
    "revenue_branch",
    "operating_income_branch",
    "branch_merge",
    "final_grounding",
)
LABELS = ("D0", "D1", "D2", "D3", "D4")
ALLOWED_SCHEDULES = (LABELS, ("D0", "D2", "D1", "D3", "D4"))


class MultitrajectoryRuntimeError(ValueError):
    def __init__(self, stage: str, reason: str) -> None:
        super().__init__(reason)
        self.stage = stage


def _fail(stage: str, reason: str) -> NoReturn:
    raise MultitrajectoryRuntimeError(stage, reason)


def _sha(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _ready(graph: Any, completed: Sequence[str]) -> tuple[Any, ...]:
    done = set(completed)
    return tuple(
        obligation
        for obligation in graph.obligations
        if obligation.decision_id not in done
        and set(obligation.downstream_claim_dependencies) <= done
    )


def _state(
    *,
    case_id: str,
    task_id: str,
    graph: Any,
    evidence_ids: tuple[str, ...],
    completed: Sequence[str],
    claims: Sequence[Any],
    executions: Sequence[Any],
    observations: Sequence[Any],
) -> Any:
    ready = _ready(graph, completed)
    actions = tuple(
        action for obligation in ready for action in obligation.admissible_alternative_action_ids
    ) or (primitives._action_id(case_id, "complete", "terminate"),)
    remaining = tuple(
        obligation.unresolved_uncertainty_type
        for obligation in graph.obligations
        if obligation.decision_id not in set(completed)
    )
    return contracts.identified(
        reasoning_models.PublicReasoningStateV1,
        {
            "task_instance_id": task_id,
            "sequence_index": len(completed),
            "available_evidence_refs": evidence_ids,
            "verified_claim_refs": tuple(claim.claim_id for claim in claims),
            "current_subgoal": (
                "resolve dependency-ready Critical Decisions: "
                + "; ".join(obligation.subgoal for obligation in ready)
                if ready
                else "same-task reasoning trajectory complete"
            ),
            "remaining_uncertainties": remaining,
            "available_action_ids": actions,
            "completed_action_refs": tuple(value.execution_id for value in executions),
            "observation_refs": tuple(value.observation_id for value in observations),
        },
        "state_id",
        "public_reasoning_state:",
    )


def _inputs(
    case_id: str,
    kind: str,
    graph: Any,
    roles: Mapping[str, Any],
    evidence_ids: tuple[str, ...],
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    index = KINDS.index(kind)
    obligation = graph.obligations[index]
    by_decision = {
        item.decision_id: primitives._claim_id(case_id, KINDS[position])
        for position, item in enumerate(graph.obligations)
    }
    evidence: tuple[str, ...]
    if kind == "revenue_branch":
        evidence = (roles["revenue_earlier"].evidence_id, roles["revenue_later"].evidence_id)
    elif kind == "operating_income_branch":
        evidence = (roles["income_earlier"].evidence_id, roles["income_later"].evidence_id)
    else:
        evidence = evidence_ids
    return evidence, tuple(
        by_decision[parent] for parent in obligation.downstream_claim_dependencies
    )


def _envelope(*, case_id: str, kind: str, graph: Any, state: Any, roles: Mapping[str, Any]) -> Any:
    obligation = graph.obligations[KINDS.index(kind)]
    evidence, claims = _inputs(case_id, kind, graph, roles, tuple(state.available_evidence_refs))
    action_id = primitives._action_id(case_id, kind, "execute")
    return contracts.identified(
        reasoning_models.ReasoningActionEnvelopeV1,
        {
            "task_instance_id": state.task_instance_id,
            "state_id": state.state_id,
            "decision_graph_id": graph.graph_id,
            "decision_id": obligation.decision_id,
            "subgoal": obligation.subgoal,
            "evidence_refs": evidence,
            "claim_refs": claims,
            "unresolved_uncertainty": obligation.unresolved_uncertainty_type,
            "candidate_action_ids": state.available_action_ids,
            "selected_action_id": action_id,
            "decision_basis": (
                reasoning_models.DecisionBasisEdgeV1(
                    relation="requires",
                    subject_ref=primitives._claim_id(case_id, kind),
                    evidence_refs=evidence,
                    claim_refs=claims,
                ),
            ),
            "expected_effect": f"produce exact public {kind} Claim",
            "action": reasoning_models.PublicActionV1(
                state_id=state.state_id,
                action_id=action_id,
                decision_kind=f"execute_{kind}",
            ),
            "preaction_commit_sequence": state.sequence_index,
        },
        "envelope_id",
        "reasoning_action_envelope:",
    )


def admit_step_envelope(
    *,
    envelope: Any,
    state: Any,
    graph: Any,
    case_id: str,
    roles: Mapping[str, Any],
    completed: Sequence[str],
) -> None:
    """Admit this candidate's public choice from current source and dependencies."""
    decisions = {item.decision_id: KINDS[index] for index, item in enumerate(graph.obligations)}
    kind = decisions.get(envelope.decision_id)
    if kind is None or envelope.decision_id not in {
        item.decision_id for item in _ready(graph, completed)
    }:
        _fail("runtime.dependency_readiness", "Action decision is absent, completed, or not ready")
    expected = _envelope(case_id=case_id, kind=kind, graph=graph, state=state, roles=roles)
    if canonical_json_bytes(envelope) != canonical_json_bytes(expected):
        _fail("runtime.current_source_action", "Action differs from its current source and State")
    contracts.admit_reasoning_action(envelope, state, graph)


def _catalog() -> RegisteredFinanceQACatalog:
    descriptor = build_catalog_descriptor(historical_catalog_snapshot()["snapshot_id"])
    return RegisteredFinanceQACatalog(descriptor)


def _program(loaded: tuple[Any, ...]) -> dict[str, Any]:
    row, bundle, package, _, _, _, _, receipt = loaded
    catalog = _catalog()
    catalog.admit_package(str(row["task_type"]), receipt, package)
    corpus = EvidenceCorpus.from_bundle(bundle)
    proof = ProofGraphBuilder().build(bundle)
    workflow = CandidateWorkflowVerifier(
        registry=catalog.registry,
        semantic_policy=FinanceSemanticPolicy(),
    )
    execution = PublicPlanCandidateExecutor(catalog.registry).generate(package, corpus)
    verification = workflow.verify(package.task, corpus, proof, execution.trajectory)
    assessment = CandidateQualityEvaluator(
        semantic_policy=FinanceSemanticPolicy(),
        workflow_verifier=workflow,
    ).evaluate(package.task, corpus, proof, execution.trajectory)
    depth = derive_program_depth_metrics(execution.reconstructed_program, catalog.registry)
    if (
        not execution.independent_verification.passed
        or execution.independently_replayed_node_count != len(execution.reconstructed_program.nodes)
        or assessment.decision != ReleaseDecision.ACCEPTED
        or not all(
            primitives._check(verification, check)
            for check in ("answer_schema_validity", "answer_correctness", "citation_binding")
        )
    ):
        _fail("runtime.program_verification", "current Program and answer verification failed")
    return {
        "execution": execution,
        "verification": verification,
        "assessment": assessment,
        "depth": depth,
    }


def _program_result(core: Mapping[str, Any], package: Any) -> dict[str, Any]:
    execution = core["execution"]
    final = execution.trajectory.final_answer
    citations = tuple(item["evidence_id"] for item in final["citations"])
    if set(citations) != set(package.task.oracle.gold_evidence_ids) or len(citations) != len(
        set(citations)
    ):
        _fail("runtime.final_citations", "Final citations differ from exact source Evidence")
    return {
        "program_execution_id": execution.execution_id,
        "verification_trajectory_id": core["verification"].trajectory_id,
        "assessment_id": core["assessment"].assessment_id,
        "final_answer": final,
        "citation_evidence_ids": citations,
        "source_program_id": execution.reconstructed_program.program_id,
        "source_program_hash": execution.reconstructed_program.program_hash,
    }


def _execute(
    *,
    kind: str,
    roles: Mapping[str, Any],
    evidence: tuple[str, ...],
    claims: tuple[str, ...],
    branch_results: dict[str, Decimal],
    loaded: tuple[Any, ...],
    core: dict[str, Any],
) -> dict[str, Any]:
    if kind == "comparability":
        return primitives._comparability(roles)
    if kind in {"revenue_branch", "operating_income_branch"}:
        prefix = "revenue" if kind == "revenue_branch" else "income"
        value = primitives._growth(roles[f"{prefix}_earlier"], roles[f"{prefix}_later"])
        branch_results[f"{prefix}_growth"] = value
        return {
            "operator_id": "growth",
            "program_node_id": f"{prefix}_growth",
            "value": value,
            "unit": "percent",
            "evidence_refs": evidence,
        }
    if kind == "branch_merge":
        if not {"revenue_growth", "income_growth"} <= set(branch_results):
            _fail("runtime.merge_claims", "both executed branch results are required")
        signed = branch_results["revenue_growth"] - branch_results["income_growth"]
        branch_results.update(signed_gap=signed, absolute_growth_spread=abs(signed))
        return {
            "operator_ids": ("signed_percentage_point_gap", "absolute_percentage_point_gap"),
            "signed_gap": signed,
            "absolute_growth_spread": abs(signed),
            "unit": "percentage_points",
            "claim_refs": claims,
            "evidence_refs": evidence,
        }
    core.update(_program(loaded))
    result = _program_result(core, loaded[2])
    value = Decimal(str(result["final_answer"]["result"]["value"]))
    if value != branch_results["absolute_growth_spread"]:
        _fail("runtime.final_claim_grounding", "Program answer differs from executed branch Claims")
    return result


def _replay_payload(
    kind: str,
    roles: Mapping[str, Any],
    evidence: tuple[str, ...],
    claims: tuple[str, ...],
    replay_values: dict[str, Decimal],
    replay_core: Mapping[str, Any],
    package: Any,
) -> dict[str, Any]:
    """Recompute candidate results; never consult old trajectory or saved result bytes."""
    if kind == "comparability":
        items = tuple(roles.values())
        earlier, later = roles["revenue_earlier"], roles["revenue_later"]
        income_earlier, income_later = roles["income_earlier"], roles["income_later"]
        if (
            len({item.subject.subject_id for item in items}) != 1
            or len({item.payload.unit for item in items}) != 1
            or len({item.payload.currency for item in items}) != 1
            or len({item.source.source_id for item in items}) != 1
            or earlier.predicate != "revenue"
            or later.predicate != "revenue"
            or income_earlier.predicate != "operating_income"
            or income_later.predicate != "operating_income"
            or earlier.domain_context["economic_period_sort_key"]
            >= later.domain_context["economic_period_sort_key"]
            or income_earlier.domain_context["economic_period_sort_key"]
            >= income_later.domain_context["economic_period_sort_key"]
            or earlier.temporal_context.label != income_earlier.temporal_context.label
            or later.temporal_context.label != income_later.temporal_context.label
        ):
            _fail("replay.comparability", "Evidence comparability predicates failed")
        return {
            "comparable": True,
            "subject_id": earlier.subject.subject_id,
            "unit": earlier.payload.unit,
            "currency": earlier.payload.currency,
            "earlier_period": earlier.temporal_context.label,
            "later_period": later.temporal_context.label,
            "evidence_refs": tuple(item.evidence_id for item in items),
        }
    if kind in {"revenue_branch", "operating_income_branch"}:
        prefix = "revenue" if kind == "revenue_branch" else "income"
        first = Decimal(str(roles[f"{prefix}_earlier"].payload.value))
        last = Decimal(str(roles[f"{prefix}_later"].payload.value))
        if first == 0:
            _fail("replay.growth_denominator", "growth denominator is zero")
        value = ((last - first) / first) * Decimal(100)
        replay_values[f"{prefix}_growth"] = value
        return {
            "operator_id": "growth",
            "program_node_id": f"{prefix}_growth",
            "value": value,
            "unit": "percent",
            "evidence_refs": evidence,
        }
    if kind == "branch_merge":
        if not {"revenue_growth", "income_growth"} <= set(replay_values):
            _fail("replay.merge_dependencies", "independent merge lacks branch results")
        signed = replay_values["revenue_growth"] - replay_values["income_growth"]
        replay_values["absolute_growth_spread"] = abs(signed)
        return {
            "operator_ids": ("signed_percentage_point_gap", "absolute_percentage_point_gap"),
            "signed_gap": signed,
            "absolute_growth_spread": abs(signed),
            "unit": "percentage_points",
            "claim_refs": claims,
            "evidence_refs": evidence,
        }
    result = _program_result(replay_core, package)
    if (
        Decimal(str(result["final_answer"]["result"]["value"]))
        != replay_values["absolute_growth_spread"]
    ):
        _fail("replay.final_claim_grounding", "independent Program answer differs from Claim chain")
    return result


def validate_trajectory(
    *, result: Mapping[str, Any], writer: DurableArtifactWriter
) -> dict[str, Any]:
    """Validate the candidate against its own durable commitment and actual source replay."""
    loaded = result["loaded"]
    row, bundle, package = loaded[:3]
    case_id = str(row["case_id"])
    roles = primitives._role_items(bundle, package)
    oracle, graph = primitives._build_oracle_and_graph(row, package)
    if canonical_json_bytes(result["graph"]) != canonical_json_bytes(graph) or canonical_json_bytes(
        result["oracle"]
    ) != canonical_json_bytes(oracle):
        _fail("replay.source_graph", "candidate changes its fixed decision graph or answer Oracle")
    schedule = tuple(result["schedule"])
    if schedule not in ALLOWED_SCHEDULES:
        _fail("replay.schedule_scope", "candidate schedule is outside the two frozen orders")
    domains = ("envelopes", "receipts", "executions", "observations", "updates")
    if len(result["states"]) != 6 or any(len(result[key]) != 5 for key in domains):
        _fail("replay.chain_cardinality", "candidate must have five complete steps and six States")
    evidence_ids = tuple(item.evidence_id for item in bundle.evidence)
    completed: list[str] = []
    claims: list[Any] = []
    executions: list[Any] = []
    observations: list[Any] = []
    replay_values: dict[str, Decimal] = {}
    replay_core = _program(loaded)
    if writer.read_bytes(f"{result['runtime_prefix']}/state_00.json") != canonical_json_bytes(
        result["states"][0]
    ):
        _fail("replay.persisted_initial_state", "initial State differs from candidate disk bytes")
    for field in ("execution", "verification", "assessment", "depth"):
        if canonical_json_bytes(result["core"][field]) != canonical_json_bytes(replay_core[field]):
            _fail("replay.program_objects", "independent Program or verification object differs")
    for index, label in enumerate(schedule):
        kind = KINDS[LABELS.index(label)]
        state = _state(
            case_id=case_id,
            task_id=package.task.task_id,
            graph=graph,
            evidence_ids=evidence_ids,
            completed=completed,
            claims=claims,
            executions=executions,
            observations=observations,
        )
        if canonical_json_bytes(state) != canonical_json_bytes(result["states"][index]):
            _fail("replay.current_state", "State differs from prior observed results")
        envelope = result["envelopes"][index]
        receipt = result["receipts"][index]
        execution = result["executions"][index]
        observation = result["observations"][index]
        update = result["updates"][index]
        paths = result["step_paths"][index]
        if envelope.decision_id != graph.obligations[KINDS.index(kind)].decision_id:
            _fail("replay.actual_schedule", "actual decision order differs from candidate schedule")
        admit_step_envelope(
            envelope=envelope,
            state=state,
            graph=graph,
            case_id=case_id,
            roles=roles,
            completed=completed,
        )
        admit_preaction_commit(
            expected_envelope=envelope,
            expected_receipt=receipt,
            actual_envelope_bytes=writer.read_bytes(paths["envelope"]),
            actual_receipt_bytes=writer.read_bytes(paths["receipt"]),
            events=tuple(
                event for event in writer.events if event["event_ordinal"] < receipt.dispatch_event
            ),
        )
        dispatch = next(
            (event for event in writer.events if event["event_ordinal"] == receipt.dispatch_event),
            None,
        )
        if (
            dispatch is None
            or dispatch["kind"] != "action_dispatch"
            or dispatch["relative_path"] != paths["receipt"]
        ):
            _fail("replay.actual_dispatch", "candidate has no matching actual dispatch event")
        evidence, dependencies = _inputs(case_id, kind, graph, roles, evidence_ids)
        expected_payload = _replay_payload(
            kind, roles, evidence, dependencies, replay_values, replay_core, package
        )
        payload_bytes = canonical_json_bytes(expected_payload)
        if (
            canonical_json_bytes(observation.public_payload) != payload_bytes
            or observation.public_payload_hash != _sha(payload_bytes)
            or execution.public_result_hash != _sha(payload_bytes)
            or not execution.succeeded
            or execution.execution_sequence != index + 1
            or observation.observation_sequence != index + 1
            or observation.state_id != state.state_id
        ):
            _fail("replay.actual_semantics", "observed result differs from current Evidence replay")
        contracts.admit_reasoning_action(envelope, state, graph, execution)
        expected_claim = reasoning_models.ClaimUpdateV1(
            claim_id=primitives._claim_id(case_id, kind),
            disposition="accepted",
            support_observation_refs=(observation.observation_id,),
            public_claim={
                "case_id": case_id,
                "obligation_kind": kind,
                "result": to_canonical_json_data(expected_payload),
                "evidence_ancestors": evidence,
            },
        )
        if (
            canonical_json_bytes(update.accepted_claims) != canonical_json_bytes((expected_claim,))
            or update.rejected_or_revised_claims
        ):
            _fail("replay.observed_claim", "Claim does not follow the actual Observation")
        completed.append(envelope.decision_id)
        claims.append(expected_claim)
        executions.append(execution)
        observations.append(observation)
        next_state = _state(
            case_id=case_id,
            task_id=package.task.task_id,
            graph=graph,
            evidence_ids=evidence_ids,
            completed=completed,
            claims=claims,
            executions=executions,
            observations=observations,
        )
        if canonical_json_bytes(next_state) != canonical_json_bytes(
            result["states"][index + 1]
        ) or (
            update.remaining_uncertainties != next_state.remaining_uncertainties
            or update.newly_enabled_actions != next_state.available_action_ids
            or update.next_subgoal != next_state.current_subgoal
        ):
            _fail(
                "replay.observation_responsive_state",
                "next State is not derived from accepted Claims",
            )
        contracts.admit_observation_update(update, envelope, execution, observation, next_state)
        for key, value in (
            ("execution", execution),
            ("observation", observation),
            ("update", update),
            ("next_state", next_state),
        ):
            if writer.read_bytes(paths[key]) != canonical_json_bytes(value):
                _fail(
                    "replay.persisted_objects",
                    "candidate object differs from its own persisted bytes",
                )
    trajectory = result["trajectory"]
    if (
        tuple(completed) != trajectory.covered_decision_ids
        or len(set(completed)) != 5
        or set(completed) != {item.decision_id for item in graph.obligations}
    ):
        _fail("replay.critical_coverage", "actual decisions must cover D0-D4 exactly once")
    if (
        trajectory.final_claim_refs != tuple(claim.claim_id for claim in claims)
        or trajectory.final_answer_ref != replay_core["execution"].execution_id
        or trajectory.initial_state_id != result["states"][0].state_id
    ):
        _fail("replay.trajectory_endpoints", "trajectory endpoints do not follow actual runtime")
    contracts.admit_reasoning_trajectory(
        trajectory,
        graph,
        result["envelopes"],
        result["executions"],
        result["observations"],
        result["updates"],
    )
    return {
        "passed": True,
        "own_commitment_admissions": 5,
        "actual_dispatches": 5,
        "independently_recomputed_decision_payloads": 5,
        "independent_program_nodes": replay_core["execution"].independently_replayed_node_count,
        "observation_responsive_state_matches": 5,
        "runtime_file_matches": 31,
        "old_reference_trajectory_byte_admissions": 0,
    }


def run_trajectory(
    *,
    writer: DurableArtifactWriter,
    runtime_prefix: str,
    loaded: tuple[Any, ...],
    schedule: Sequence[str],
) -> dict[str, Any]:
    schedule = tuple(schedule)
    if all(value in KINDS for value in schedule):
        schedule = tuple(LABELS[KINDS.index(value)] for value in schedule)
    if schedule not in ALLOWED_SCHEDULES:
        _fail("runtime.schedule_scope", "candidate schedule is outside the two frozen orders")
    row, bundle, package = loaded[:3]
    case_id = str(row["case_id"])
    roles = primitives._role_items(bundle, package)
    oracle, graph = primitives._build_oracle_and_graph(row, package)
    evidence_ids = tuple(item.evidence_id for item in bundle.evidence)
    completed: list[str] = []
    accepted_claims: list[Any] = []
    states: list[Any] = []
    envelopes: list[Any] = []
    receipts: list[Any] = []
    executions: list[Any] = []
    observations: list[Any] = []
    updates: list[Any] = []
    step_paths: list[dict[str, str]] = []
    durable_observations: list[dict[str, Any]] = []
    core: dict[str, Any] = {}
    branch_results: dict[str, Decimal] = {}
    state = _state(
        case_id=case_id,
        task_id=package.task.task_id,
        graph=graph,
        evidence_ids=evidence_ids,
        completed=completed,
        claims=accepted_claims,
        executions=executions,
        observations=observations,
    )
    writer.ensure_directory(runtime_prefix)
    writer.write_json(f"{runtime_prefix}/state_00.json", state)
    states.append(state)
    for index, label in enumerate(schedule):
        kind = KINDS[LABELS.index(label)]
        envelope = _envelope(case_id=case_id, kind=kind, graph=graph, state=state, roles=roles)
        admit_step_envelope(
            envelope=envelope,
            state=state,
            graph=graph,
            case_id=case_id,
            roles=roles,
            completed=completed,
        )
        prefix = f"{runtime_prefix}/step_{index:02d}_{kind}"
        paths = {
            "envelope": f"{prefix}_envelope.json",
            "receipt": f"{prefix}_preaction_commit_receipt.json",
            "execution": f"{prefix}_action_execution.json",
            "observation": f"{prefix}_observation.json",
            "update": f"{prefix}_update.json",
            "next_state": f"{runtime_prefix}/state_{index + 1:02d}.json",
        }
        receipt, _, _ = writer.commit_envelope(
            envelope=envelope,
            envelope_relative_path=paths["envelope"],
            receipt_relative_path=paths["receipt"],
            execution_sequence=index + 1,
        )

        def execute_action(
            envelope_value: Any = envelope,
            kind_value: str = kind,
            state_value: Any = state,
            receipt_value: Any = receipt,
            paths_value: dict[str, str] = paths,
        ) -> dict[str, Any]:
            admit_step_envelope(
                envelope=envelope_value,
                state=state_value,
                graph=graph,
                case_id=case_id,
                roles=roles,
                completed=completed,
            )
            actual_envelope_bytes = writer.read_bytes(paths_value["envelope"])
            actual_receipt_bytes = writer.read_bytes(paths_value["receipt"])
            durable_observations.append(
                {
                    "task_instance_id": package.task.task_id,
                    "state_id": state_value.state_id,
                    "envelope_id": envelope_value.envelope_id,
                    "receipt_id": receipt_value.receipt_id,
                    "envelope_relative_path": paths_value["envelope"],
                    "receipt_relative_path": paths_value["receipt"],
                    "envelope_sha256": _sha(actual_envelope_bytes),
                    "receipt_sha256": _sha(actual_receipt_bytes),
                    "envelope_byte_count": len(actual_envelope_bytes),
                    "receipt_byte_count": len(actual_receipt_bytes),
                    "dispatch_event": writer.events[-1]["event_ordinal"],
                    "receipt_directory_fsync_event": receipt_value.receipt_directory_fsync_event,
                    "callback_after_receipt_directory_fsync": writer.events[-1]["event_ordinal"]
                    > receipt_value.receipt_directory_fsync_event,
                }
            )
            return _execute(
                kind=kind_value,
                roles=roles,
                evidence=tuple(envelope_value.evidence_refs),
                claims=tuple(envelope_value.claim_refs),
                branch_results=branch_results,
                loaded=loaded,
                core=core,
            )

        payload = writer.guard_and_dispatch(
            expected_envelope=envelope,
            expected_receipt=receipt,
            receipt_relative_path=paths["receipt"],
            callback=execute_action,
        )
        execution = contracts.identified(
            reasoning_models.ActionExecutionV1,
            {
                "task_instance_id": package.task.task_id,
                "parent_envelope_id": envelope.envelope_id,
                "state_id": state.state_id,
                "action_id": envelope.selected_action_id,
                "execution_sequence": index + 1,
                "succeeded": True,
                "public_result_hash": _sha(canonical_json_bytes(payload)),
            },
            "execution_id",
            "reasoning_action_execution:",
        )
        observation = contracts.identified(
            reasoning_models.PublicObservationV1,
            {
                "task_instance_id": package.task.task_id,
                "parent_execution_id": execution.execution_id,
                "state_id": state.state_id,
                "observation_sequence": index + 1,
                "public_payload": to_canonical_json_data(payload),
                "public_payload_hash": _sha(canonical_json_bytes(payload)),
            },
            "observation_id",
            "public_reasoning_observation:",
        )
        claim = reasoning_models.ClaimUpdateV1(
            claim_id=primitives._claim_id(case_id, kind),
            disposition="accepted",
            support_observation_refs=(observation.observation_id,),
            public_claim={
                "case_id": case_id,
                "obligation_kind": kind,
                "result": to_canonical_json_data(payload),
                "evidence_ancestors": tuple(envelope.evidence_refs),
            },
        )
        completed.append(envelope.decision_id)
        accepted_claims.append(claim)
        executions.append(execution)
        observations.append(observation)
        next_state = _state(
            case_id=case_id,
            task_id=package.task.task_id,
            graph=graph,
            evidence_ids=evidence_ids,
            completed=completed,
            claims=accepted_claims,
            executions=executions,
            observations=observations,
        )
        update = contracts.identified(
            reasoning_models.ObservationUpdateV1,
            {
                "task_instance_id": package.task.task_id,
                "parent_reasoning_action_id": envelope.envelope_id,
                "action_execution_id": execution.execution_id,
                "observation_id": observation.observation_id,
                "accepted_claims": (claim,),
                "rejected_or_revised_claims": (),
                "remaining_uncertainties": next_state.remaining_uncertainties,
                "newly_enabled_actions": next_state.available_action_ids,
                "next_subgoal": next_state.current_subgoal,
                "next_state_id": next_state.state_id,
                "update_sequence": index + 1,
            },
            "update_id",
            "observation_update:",
        )
        contracts.admit_reasoning_action(envelope, state, graph, execution)
        contracts.admit_observation_update(update, envelope, execution, observation, next_state)
        for key, value in (
            ("execution", execution),
            ("observation", observation),
            ("update", update),
            ("next_state", next_state),
        ):
            writer.write_json(paths[key], value)
        envelopes.append(envelope)
        receipts.append(receipt)
        updates.append(update)
        step_paths.append(paths)
        states.append(next_state)
        state = next_state
    trajectory = contracts.identified(
        reasoning_models.ReasoningTrajectoryV1,
        {
            "task_instance_id": package.task.task_id,
            "initial_state_id": states[0].state_id,
            "ordered_reasoning_action_ids": tuple(value.envelope_id for value in envelopes),
            "ordered_action_execution_ids": tuple(value.execution_id for value in executions),
            "ordered_observation_ids": tuple(value.observation_id for value in observations),
            "ordered_observation_update_ids": tuple(value.update_id for value in updates),
            "final_claim_refs": tuple(value.claim_id for value in accepted_claims),
            "final_answer_ref": core["execution"].execution_id,
            "critical_decision_graph_id": graph.graph_id,
            "answer_oracle_program_binding_id": oracle.binding_id,
            "covered_decision_ids": tuple(completed),
            "wording_fingerprint": None,
        },
        "trajectory_id",
        "reasoning_trajectory:",
    )
    result: dict[str, Any] = {
        "loaded": loaded,
        "row": row,
        "bundle": bundle,
        "package": package,
        "graph": graph,
        "oracle": oracle,
        "states": tuple(states),
        "envelopes": tuple(envelopes),
        "receipts": tuple(receipts),
        "executions": tuple(executions),
        "observations": tuple(observations),
        "updates": tuple(updates),
        "claims": tuple(accepted_claims),
        "trajectory": trajectory,
        "core": core,
        "schedule": schedule,
        "step_paths": tuple(step_paths),
        "runtime_prefix": runtime_prefix,
        "branch_results": branch_results,
        "durable_observations": tuple(durable_observations),
        "schedule_kinds": tuple(KINDS[LABELS.index(value)] for value in schedule),
    }
    replay = validate_trajectory(result=result, writer=writer)
    answer_validity = contracts.identified(
        reasoning_models.AnswerValidityReportV1,
        {
            "task_instance_id": package.task.task_id,
            "source_valid": True,
            "answer_valid": True,
            "citation_valid": True,
            "qa_valid": True,
        },
        "report_id",
        "answer_validity_report:",
    )
    trajectory_validity = contracts.identified(
        reasoning_models.TrajectoryValidityReportV1,
        {
            "trajectory_id": trajectory.trajectory_id,
            "preaction_valid": replay["passed"],
            "grounding_valid": replay["passed"],
            "reasoning_action_valid": replay["passed"],
            "observation_update_valid": replay["passed"],
            "critical_coverage_valid": replay["passed"],
            "trajectory_valid": replay["passed"],
        },
        "report_id",
        "reasoning_trajectory_validity_report:",
    )
    qualification = contracts.identified(
        reasoning_models.QualifiedReasoningTrajectoryV1,
        {
            "task_instance_id": package.task.task_id,
            "trajectory_id": trajectory.trajectory_id,
            "answer_validity_report_id": answer_validity.report_id,
            "trajectory_validity_report_id": trajectory_validity.report_id,
            "qa_valid": answer_validity.qa_valid,
            "trajectory_valid": trajectory_validity.trajectory_valid,
            "qualified": answer_validity.qa_valid and trajectory_validity.trajectory_valid,
        },
        "qualification_id",
        "qualified_reasoning_trajectory:",
    )
    contracts.admit_qualification(qualification, answer_validity, trajectory_validity)
    depth = contracts.identified(
        reasoning_models.ReasoningDepthMetricsV1,
        {
            "task_instance_id": package.task.task_id,
            "trajectory_id": trajectory.trajectory_id,
            "semantic_operation_depth": core["depth"].semantic_operation_depth,
            "reasoning_depth": primitives._reasoning_depth(graph),
            "evidence_integration_depth": max(
                len(set(claim.public_claim["evidence_ancestors"])) for claim in accepted_claims
            ),
            "correction_depth": sum(bool(update.rejected_or_revised_claims) for update in updates),
            "required_decision_count": len(graph.obligations),
            "covered_required_decision_count": len(completed),
            "critical_decision_coverage": len(completed) / len(graph.obligations),
        },
        "metrics_id",
        "reasoning_depth_metrics:",
    )
    result.update(
        answer_validity=answer_validity,
        trajectory_validity=trajectory_validity,
        qualification=qualification,
        depth=depth,
        replay_audit=replay,
    )
    replay["trajectory_id"] = trajectory.trajectory_id
    replay["replay_input_sha256"] = strict_canonical_hash(
        {
            key: result[key]
            for key in (
                "trajectory",
                "envelopes",
                "executions",
                "observations",
                "updates",
                "qualification",
            )
        }
    )
    return result
