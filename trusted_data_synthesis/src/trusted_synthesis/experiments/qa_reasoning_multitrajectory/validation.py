"""Read-only source replay for each newly executed reasoning trajectory.

This validator admits the trajectory's own persisted commitment and observations.
It does not compare a new trajectory with a historical reference trajectory.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping, Sequence
from decimal import Decimal
from typing import Any, NoReturn

from pydantic import BaseModel

from trusted_synthesis.canonical_json import canonical_json_bytes, strict_canonical_hash
from trusted_synthesis.core.evaluation.evaluator import CandidateQualityEvaluator
from trusted_synthesis.core.evaluation.schema import ReleaseDecision
from trusted_synthesis.core.evidence.corpus import EvidenceCorpus
from trusted_synthesis.core.graph.builder import ProofGraphBuilder
from trusted_synthesis.core.task.program_depth import derive_program_depth_metrics
from trusted_synthesis.core.trajectory.candidate_verifier import CandidateWorkflowVerifier
from trusted_synthesis.core.trajectory.public_plan_executor import PublicPlanCandidateExecutor
from trusted_synthesis.domains.finance.policy import FinanceSemanticPolicy
from trusted_synthesis.experiments.qa_reasoning_contract_freeze import models as schemas
from trusted_synthesis.experiments.qa_reasoning_fixed_fixture.models import (
    OBLIGATION_KINDS,
    DurablePreactionCommitReceipt,
)
from trusted_synthesis.experiments.qa_reasoning_fixed_fixture.preflight import (
    _build_oracle_and_graph,
)
from trusted_synthesis.experiments.qa_semantic_depth_three_catalog_integration.catalog import (
    RegisteredFinanceQACatalog,
    build_catalog_descriptor,
    historical_catalog_snapshot,
)


class TrajectoryReplayError(ValueError):
    def __init__(self, stage: str, reason: str) -> None:
        super().__init__(reason)
        self.stage = stage


def _fail(stage: str, reason: str) -> NoReturn:
    raise TrajectoryReplayError(stage, reason)


def _equal(actual: Any, expected: Any, stage: str) -> None:
    if canonical_json_bytes(actual) != canonical_json_bytes(expected):
        _fail(stage, "own persisted trajectory differs from independent source replay")


def _sha(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _read(writer: Any, relative: str, schema: type[BaseModel]) -> Any:
    try:
        data = writer.read_bytes(relative)
        value = schema.model_validate_json(data)
    except (OSError, ValueError) as error:
        raise TrajectoryReplayError(
            "replay.persisted_schema", "persisted trajectory object is missing or invalid"
        ) from error
    _equal_bytes = canonical_json_bytes(value)
    if data != _equal_bytes:
        _fail("replay.canonical_bytes", "persisted trajectory object is not canonical")
    return value


def _claim_id(case_id: str, kind: str) -> str:
    return strict_canonical_hash(
        {"case_id": case_id, "claim_kind": kind}, prefix="fixed_fixture_claim:"
    )


def _action_id(case_id: str, kind: str, alternative: str) -> str:
    return strict_canonical_hash(
        {"case_id": case_id, "decision_kind": kind, "alternative": alternative},
        prefix="fixed_fixture_action:",
    )


def _roles(bundle: Any, package: Any) -> dict[str, Any]:
    evidence = {item.evidence_id: item for item in bundle.evidence}
    roles = {}
    for role, refs in package.binding_snapshot.role_bindings.items():
        if len(refs) != 1 or refs[0] not in evidence:
            _fail("replay.source_roles", "Evidence role does not resolve exactly once")
        roles[role] = evidence[refs[0]]
    if set(roles) != {"revenue_earlier", "revenue_later", "income_earlier", "income_later"}:
        _fail("replay.source_roles", "Evidence role domain differs")
    return roles


def _comparability(roles: Mapping[str, Any]) -> dict[str, Any]:
    items = tuple(roles.values())
    subjects = {item.subject.subject_id for item in items}
    units = {item.payload.unit for item in items}
    currencies = {item.payload.currency for item in items}
    sources = {item.source.source_id for item in items}
    checks = [len(subjects) == len(units) == len(currencies) == len(sources) == 1]
    for prefix, predicate in (("revenue", "revenue"), ("income", "operating_income")):
        early, late = roles[prefix + "_earlier"], roles[prefix + "_later"]
        checks.extend(
            (
                early.predicate == late.predicate == predicate,
                early.domain_context["economic_period_sort_key"]
                < late.domain_context["economic_period_sort_key"],
            )
        )
    checks.extend(
        roles["revenue_" + period].temporal_context.label
        == roles["income_" + period].temporal_context.label
        for period in ("earlier", "later")
    )
    if not all(checks):
        _fail("replay.comparability", "frozen Evidence is not comparable")
    return {
        "comparable": True,
        "subject_id": next(iter(subjects)),
        "unit": next(iter(units)),
        "currency": next(iter(currencies)),
        "earlier_period": roles["revenue_earlier"].temporal_context.label,
        "later_period": roles["revenue_later"].temporal_context.label,
        "evidence_refs": tuple(item.evidence_id for item in items),
    }


def _growth(early: Any, late: Any) -> Decimal:
    base = Decimal(str(early.payload.value))
    if not base:
        _fail("replay.growth", "growth denominator is zero")
    return (Decimal(str(late.payload.value)) - base) / base * Decimal(100)


def _final_replay(loaded: Sequence[Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    row, bundle, package, _, _, _, _, receipt = loaded
    catalog = RegisteredFinanceQACatalog(
        build_catalog_descriptor(historical_catalog_snapshot()["snapshot_id"])
    )
    catalog.admit_package(str(row["task_type"]), receipt, package)
    corpus = EvidenceCorpus.from_bundle(bundle)
    graph = ProofGraphBuilder().build(bundle)
    workflow = CandidateWorkflowVerifier(
        registry=catalog.registry, semantic_policy=FinanceSemanticPolicy()
    )
    evaluator = CandidateQualityEvaluator(
        semantic_policy=FinanceSemanticPolicy(), workflow_verifier=workflow
    )
    execution = PublicPlanCandidateExecutor(catalog.registry).generate(package, corpus)
    verification = workflow.verify(package.task, corpus, graph, execution.trajectory)
    assessment = evaluator.evaluate(package.task, corpus, graph, execution.trajectory)
    depth = derive_program_depth_metrics(execution.reconstructed_program, catalog.registry)
    required = {"answer_schema_validity", "answer_correctness", "citation_binding"}
    checks = {check.check_id: check.passed for check in verification.checks}
    if (
        not execution.independent_verification.passed
        or not all(checks.get(name, False) for name in required)
        or assessment.decision != ReleaseDecision.ACCEPTED
        or canonical_json_bytes(execution.reconstructed_program)
        != canonical_json_bytes(package.task.oracle.task_program)
    ):
        _fail("replay.final_program_validity", "independent Program or QA verification failed")
    answer = execution.trajectory.final_answer
    citations = tuple(item["evidence_id"] for item in answer["citations"])
    if (
        set(citations) != set(package.task.oracle.gold_evidence_ids)
        or len(citations) != len(set(citations))
        or answer["result"]["unit"] != "percentage_points"
    ):
        _fail("replay.final_grounding", "independent final answer or citation failed")
    return (
        {
            "program_execution_id": execution.execution_id,
            "verification_trajectory_id": verification.trajectory_id,
            "assessment_id": assessment.assessment_id,
            "final_answer": answer,
            "citation_evidence_ids": citations,
            "source_program_id": execution.reconstructed_program.program_id,
            "source_program_hash": execution.reconstructed_program.program_hash,
        },
        {
            "execution": execution,
            "verification": verification,
            "assessment": assessment,
            "depth": depth,
        },
    )


def _receipt_events(
    writer: Any, receipt: Any, envelope: Any, envelope_path: str, receipt_path: str
) -> None:
    payload = writer.read_bytes(envelope_path)
    if (
        receipt.envelope_relative_path != envelope_path
        or receipt.envelope_id != envelope.envelope_id
        or receipt.task_instance_id != envelope.task_instance_id
        or receipt.state_id != envelope.state_id
        or receipt.decision_id != envelope.decision_id
        or receipt.envelope_sha256 != _sha(payload)
        or receipt.envelope_byte_count != len(payload)
        or receipt.preaction_commit_sequence != envelope.preaction_commit_sequence
    ):
        _fail("replay.receipt_commitment", "Receipt does not bind own persisted Envelope")
    events = {event["event_ordinal"]: event for event in writer.events}
    required = (
        (receipt.envelope_file_fsync_event, "file_fsync", envelope_path),
        (receipt.envelope_directory_fsync_event, "directory_fsync", envelope_path),
        (receipt.receipt_file_fsync_event, "file_fsync", receipt_path),
        (receipt.receipt_directory_fsync_event, "directory_fsync", receipt_path),
        (receipt.dispatch_event, "action_dispatch", receipt_path),
    )
    for ordinal, kind, path in required:
        event = events.get(ordinal, {})
        if event.get("kind") != kind or event.get("relative_path") != path:
            _fail("replay.actual_preaction_events", "actual writer dispatch or fsync event differs")


def validate_trajectory(
    *, writer: Any, result: Mapping[str, Any], loaded: Sequence[Any]
) -> dict[str, Any]:
    row, bundle, package, *_ = loaded
    case_id, task_id, prefix = (
        str(row["case_id"]),
        package.task.task_id,
        str(result["runtime_prefix"]),
    )
    labels = dict(zip(("D0", "D1", "D2", "D3", "D4"), OBLIGATION_KINDS, strict=True))
    schedule = tuple(labels.get(name, name) for name in result["schedule"])
    if (
        len(schedule) != 5
        or len(result["step_paths"]) != 5
        or set(schedule) != set(OBLIGATION_KINDS)
    ):
        _fail("replay.schedule_domain", "trajectory omits or repeats an obligation")
    if (
        package.binding_snapshot.bundle_id != bundle.bundle_id
        or package.realized_package_id != row["realized_package_id"]
        or tuple(package.task.oracle.gold_evidence_ids)
        != tuple(item.evidence_id for item in bundle.evidence)
    ):
        _fail("replay.fixed_task_source", "frozen task or Evidence parent differs")
    oracle, graph = _build_oracle_and_graph(row, package)
    _equal(result["graph"], graph, "replay.frozen_graph")
    _equal(result["oracle"], oracle, "replay.frozen_oracle")
    roles, evidence_ids = (
        _roles(bundle, package),
        tuple(item.evidence_id for item in bundle.evidence),
    )
    obligations = dict(zip(OBLIGATION_KINDS, graph.obligations, strict=True))
    by_decision = {obligation.decision_id: kind for kind, obligation in obligations.items()}
    dependencies = {
        kind: tuple(by_decision[ref] for ref in obligation.downstream_claim_dependencies)
        for kind, obligation in obligations.items()
    }
    states = tuple(
        _read(writer, f"{prefix}/state_{index:02d}.json", schemas.PublicReasoningStateV1)
        for index in range(6)
    )
    parsed: dict[str, list[Any]] = {
        key: [] for key in ("envelopes", "receipts", "executions", "observations", "updates")
    }
    claims: list[Any] = []
    completed: list[str] = []
    branch: dict[str, Decimal] = {}
    step_rows: list[dict[str, Any]] = []
    core: dict[str, Any] = {}
    for index, kind in enumerate(schedule):
        state, next_state, obligation = states[index], states[index + 1], obligations[kind]
        ready = tuple(
            name
            for name in OBLIGATION_KINDS
            if name not in completed and set(dependencies[name]) <= set(completed)
        )
        if kind not in ready:
            _fail("replay.dependency_ready", "selected obligation has unresolved dependencies")
        expected_state = {
            "task_instance_id": task_id,
            "sequence_index": index,
            "available_evidence_refs": evidence_ids,
            "verified_claim_refs": tuple(claim.claim_id for claim in claims),
            "completed_action_refs": tuple(item.execution_id for item in parsed["executions"]),
            "observation_refs": tuple(item.observation_id for item in parsed["observations"]),
            "available_action_ids": tuple(
                action
                for name in ready
                for action in obligations[name].admissible_alternative_action_ids
            ),
            "current_subgoal": "resolve dependency-ready Critical Decisions: "
            + "; ".join(obligations[name].subgoal for name in ready),
            "remaining_uncertainties": tuple(
                obligations[name].unresolved_uncertainty_type
                for name in OBLIGATION_KINDS
                if name not in completed
            ),
        }
        for field, expected in expected_state.items():
            _equal(getattr(state, field), expected, "replay.current_state")
        paths = result["step_paths"][index]
        if any(not str(path).startswith(prefix + "/") for path in paths.values()):
            _fail("replay.path_domain", "step crosses its own runtime domain")
        envelope = _read(writer, paths["envelope"], schemas.ReasoningActionEnvelopeV1)
        receipt = _read(writer, paths["receipt"], DurablePreactionCommitReceipt)
        execution = _read(writer, paths["execution"], schemas.ActionExecutionV1)
        observation = _read(writer, paths["observation"], schemas.PublicObservationV1)
        update = _read(writer, paths["update"], schemas.ObservationUpdateV1)
        role = "revenue" if kind == "revenue_branch" else "income"
        evidence_refs = (
            (roles[role + "_earlier"].evidence_id, roles[role + "_later"].evidence_id)
            if kind in {"revenue_branch", "operating_income_branch"}
            else evidence_ids
        )
        claim_refs = tuple(_claim_id(case_id, dep) for dep in dependencies[kind])
        selected = _action_id(case_id, kind, "execute")
        envelope_expected = {
            "task_instance_id": task_id,
            "state_id": state.state_id,
            "decision_graph_id": graph.graph_id,
            "decision_id": obligation.decision_id,
            "subgoal": obligation.subgoal,
            "unresolved_uncertainty": obligation.unresolved_uncertainty_type,
            "evidence_refs": evidence_refs,
            "claim_refs": claim_refs,
            "selected_action_id": selected,
            "candidate_action_ids": state.available_action_ids,
            "preaction_commit_sequence": index,
            "expected_effect": f"produce exact public {kind} Claim",
            "decision_basis": (
                {
                    "relation": "requires",
                    "subject_ref": _claim_id(case_id, kind),
                    "evidence_refs": evidence_refs,
                    "claim_refs": claim_refs,
                },
            ),
        }
        for field, expected in envelope_expected.items():
            _equal(getattr(envelope, field), expected, "replay.source_grounded_commitment")
        if (
            not set(claim_refs) <= set(state.verified_claim_refs)
            or envelope.action.decision_kind != f"execute_{kind}"
        ):
            _fail("replay.available_claim_action", "current Claims or selected Action differ")
        _receipt_events(writer, receipt, envelope, paths["envelope"], paths["receipt"])
        snapshots = result.get("durable_observations", ())
        if len(snapshots) != len(schedule):
            _fail("replay.callback_snapshots", "actual callback snapshot domain differs")
        own_snapshot = {
            "task_instance_id": task_id,
            "state_id": state.state_id,
            "envelope_id": envelope.envelope_id,
            "receipt_id": receipt.receipt_id,
            "envelope_relative_path": paths["envelope"],
            "receipt_relative_path": paths["receipt"],
            "envelope_sha256": _sha(writer.read_bytes(paths["envelope"])),
            "receipt_sha256": _sha(writer.read_bytes(paths["receipt"])),
            "envelope_byte_count": len(writer.read_bytes(paths["envelope"])),
            "receipt_byte_count": len(writer.read_bytes(paths["receipt"])),
            "dispatch_event": receipt.dispatch_event,
            "receipt_directory_fsync_event": receipt.receipt_directory_fsync_event,
            "callback_after_receipt_directory_fsync": (
                receipt.dispatch_event > receipt.receipt_directory_fsync_event
            ),
        }
        _equal(snapshots[index], own_snapshot, "replay.callback_owned_commitment")
        if receipt.execution_sequence != index + 1:
            _fail("replay.receipt_sequence", "Receipt execution sequence differs")
        if kind == "comparability":
            payload = _comparability(roles)
        elif kind in {"revenue_branch", "operating_income_branch"}:
            value = _growth(roles[role + "_earlier"], roles[role + "_later"])
            branch[role + "_growth"] = value
            payload = {
                "operator_id": "growth",
                "program_node_id": role + "_growth",
                "value": value,
                "unit": "percent",
                "evidence_refs": evidence_refs,
            }
        elif kind == "branch_merge":
            signed = branch["revenue_growth"] - branch["income_growth"]
            branch["absolute_growth_spread"] = abs(signed)
            payload = {
                "operator_ids": ("signed_percentage_point_gap", "absolute_percentage_point_gap"),
                "signed_gap": signed,
                "absolute_growth_spread": abs(signed),
                "unit": "percentage_points",
                "claim_refs": claim_refs,
                "evidence_refs": evidence_ids,
            }
        else:
            payload, core = _final_replay(loaded)
            if (
                Decimal(str(payload["final_answer"]["result"]["value"]))
                != branch["absolute_growth_spread"]
            ):
                _fail(
                    "replay.final_branch_consistency",
                    "Final differs from independently merged Claims",
                )
        _equal(observation.public_payload, payload, "replay.independent_action_result")
        execution_expected = {
            "task_instance_id": task_id,
            "parent_envelope_id": envelope.envelope_id,
            "state_id": state.state_id,
            "action_id": selected,
            "execution_sequence": index + 1,
            "succeeded": True,
            "public_result_hash": _sha(canonical_json_bytes(payload)),
        }
        observation_expected = {
            "task_instance_id": task_id,
            "parent_execution_id": execution.execution_id,
            "state_id": state.state_id,
            "observation_sequence": index + 1,
        }
        for obj, expected_fields in (
            (execution, execution_expected),
            (observation, observation_expected),
        ):
            for field, expected in expected_fields.items():
                _equal(getattr(obj, field), expected, "replay.action_observation_lineage")
        expected_claim = {
            "claim_id": _claim_id(case_id, kind),
            "disposition": "accepted",
            "support_observation_refs": (observation.observation_id,),
            "public_claim": {
                "case_id": case_id,
                "obligation_kind": kind,
                "result": payload,
                "evidence_ancestors": evidence_refs,
            },
        }
        update_expected = {
            "task_instance_id": task_id,
            "parent_reasoning_action_id": envelope.envelope_id,
            "action_execution_id": execution.execution_id,
            "observation_id": observation.observation_id,
            "next_state_id": next_state.state_id,
            "update_sequence": index + 1,
            "accepted_claims": (expected_claim,),
            "rejected_or_revised_claims": (),
            "remaining_uncertainties": next_state.remaining_uncertainties,
            "newly_enabled_actions": next_state.available_action_ids,
            "next_subgoal": next_state.current_subgoal,
        }
        for field, expected in update_expected.items():
            _equal(getattr(update, field), expected, "replay.observation_update_lineage")
        for name, obj in (
            ("envelopes", envelope),
            ("receipts", receipt),
            ("executions", execution),
            ("observations", observation),
            ("updates", update),
        ):
            parsed[name].append(obj)
        claims.extend(update.accepted_claims)
        completed.append(kind)
        step_rows.append(
            {
                "step_index": index,
                "obligation_kind": kind,
                "envelope_id": envelope.envelope_id,
                "receipt_id": receipt.receipt_id,
                "independent_public_payload_sha256": _sha(canonical_json_bytes(payload)),
                "own_preaction_event_and_byte_match": True,
                "source_replay_passed": True,
            }
        )
    final_expected = {
        "task_instance_id": task_id,
        "sequence_index": 5,
        "available_evidence_refs": evidence_ids,
        "verified_claim_refs": tuple(item.claim_id for item in claims),
        "completed_action_refs": tuple(item.execution_id for item in parsed["executions"]),
        "observation_refs": tuple(item.observation_id for item in parsed["observations"]),
        "remaining_uncertainties": (),
        "current_subgoal": "same-task reasoning trajectory complete",
        "available_action_ids": (_action_id(case_id, "complete", "terminate"),),
    }
    for field, expected in final_expected.items():
        _equal(getattr(states[-1], field), expected, "replay.final_state")
    trajectory = schemas.ReasoningTrajectoryV1.model_validate_json(
        canonical_json_bytes(result["trajectory"])
    )
    expected_trajectory = {
        "task_instance_id": task_id,
        "initial_state_id": states[0].state_id,
        "ordered_reasoning_action_ids": tuple(item.envelope_id for item in parsed["envelopes"]),
        "ordered_action_execution_ids": tuple(item.execution_id for item in parsed["executions"]),
        "ordered_observation_ids": tuple(item.observation_id for item in parsed["observations"]),
        "ordered_observation_update_ids": tuple(item.update_id for item in parsed["updates"]),
        "final_claim_refs": tuple(item.claim_id for item in claims),
        "final_answer_ref": core["execution"].execution_id,
        "critical_decision_graph_id": graph.graph_id,
        "answer_oracle_program_binding_id": oracle.binding_id,
        "covered_decision_ids": tuple(item.decision_id for item in parsed["envelopes"]),
    }
    for field, expected in expected_trajectory.items():
        _equal(getattr(trajectory, field), expected, "replay.trajectory_parent_chain")
    if set(trajectory.covered_decision_ids) != {item.decision_id for item in graph.obligations}:
        _fail("replay.critical_coverage", "coverage differs from frozen obligations")
    _equal(result["states"], states, "replay.own_runtime_projection")
    for name, values in parsed.items():
        _equal(result[name], values, "replay.own_runtime_projection")
    for name, value in core.items():
        _equal(result["core"][name], value, "replay.own_core_projection")
    depths: dict[str, int] = {}
    for item in graph.obligations:
        depths[item.decision_id] = 1 + max(
            (depths[ref] for ref in item.downstream_claim_dependencies), default=0
        )
    metrics = {
        "semantic_operation_depth": int(core["depth"].semantic_operation_depth),
        "reasoning_depth": max(depths.values()),
        "evidence_integration_depth": max(
            len(set(item.public_claim["evidence_ancestors"])) for item in claims
        ),
        "correction_depth": sum(
            bool(item.rejected_or_revised_claims) for item in parsed["updates"]
        ),
        "critical_decision_coverage": len(set(trajectory.covered_decision_ids))
        / len(graph.obligations),
    }
    for field, expected in metrics.items():
        _equal(getattr(result["depth"], field), expected, "replay.independent_depth")
    qualification = schemas.QualifiedReasoningTrajectoryV1.model_validate_json(
        canonical_json_bytes(result["qualification"])
    )
    answer = schemas.AnswerValidityReportV1.model_validate_json(
        canonical_json_bytes(result["answer_validity"])
    )
    validity = schemas.TrajectoryValidityReportV1.model_validate_json(
        canonical_json_bytes(result["trajectory_validity"])
    )
    if (
        qualification.task_instance_id != task_id
        or qualification.trajectory_id != trajectory.trajectory_id
        or qualification.answer_validity_report_id != answer.report_id
        or qualification.trajectory_validity_report_id != validity.report_id
        or not qualification.qa_valid
        or not qualification.trajectory_valid
        or not qualification.qualified
        or answer.task_instance_id != task_id
        or not answer.qa_valid
        or validity.trajectory_id != trajectory.trajectory_id
        or not validity.trajectory_valid
    ):
        _fail(
            "replay.recomputed_validity", "reported validity differs from independent conjunction"
        )
    replay_inputs = {
        "trajectory": trajectory,
        "qualification": qualification,
        **{
            name: tuple(parsed[name])
            for name in ("envelopes", "executions", "observations", "updates")
        },
    }
    audit = {
        "task_instance_id": task_id,
        "trajectory_id": trajectory.trajectory_id,
        "case_id": case_id,
        "schedule": tuple(result["schedule"]),
        "runtime_prefix": prefix,
        "runtime_objects_reparsed": 31,
        "action_results_independently_recomputed": 5,
        "program_nodes_independently_replayed": len(core["execution"].reconstructed_program.nodes),
        "own_preaction_commitment_matches": 5,
        "step_rows": tuple(step_rows),
        "qa_valid": True,
        "trajectory_valid": True,
        "qualified": True,
        "depth_metrics": metrics,
        "historical_reference_byte_admission_used": False,
        "candidate_validity_booleans_used_as_oracle": False,
        "provider_calls": 0,
        "replay_input_sha256": strict_canonical_hash(replay_inputs),
        "passed": True,
        "schema_version": "qa_reasoning_multitrajectory_own_replay_audit.v1",
    }
    audit["audit_id"] = strict_canonical_hash(
        audit, prefix="qa_reasoning_multitrajectory_own_replay_audit:"
    )
    return audit
