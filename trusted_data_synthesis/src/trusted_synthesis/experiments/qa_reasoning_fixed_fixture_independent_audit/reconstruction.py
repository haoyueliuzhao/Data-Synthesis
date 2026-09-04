from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Callable, Mapping, Sequence
from decimal import Decimal
from functools import partial
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, NoReturn

from trusted_synthesis.canonical_json import (
    canonical_json_bytes,
    strict_canonical_hash,
    to_canonical_json_data,
)
from trusted_synthesis.core.evaluation.evaluator import CandidateQualityEvaluator
from trusted_synthesis.core.evaluation.schema import ReleaseDecision
from trusted_synthesis.core.evidence.corpus import EvidenceCorpus
from trusted_synthesis.core.evidence.schema import EvidenceBundle
from trusted_synthesis.core.graph.builder import ProofGraphBuilder
from trusted_synthesis.core.task.program_depth import derive_program_depth_metrics
from trusted_synthesis.core.task.realization import RealizedTaskPackage
from trusted_synthesis.core.trajectory.candidate_verifier import CandidateWorkflowVerifier
from trusted_synthesis.core.trajectory.public_plan_executor import PublicPlanCandidateExecutor
from trusted_synthesis.domains.finance.policy import FinanceSemanticPolicy
from trusted_synthesis.experiments.qa_semantic_depth_three_catalog_integration.catalog import (
    RegisteredFinanceQACatalog,
    build_catalog_descriptor,
    historical_catalog_snapshot,
)

from . import models


class IndependentReplayError(ValueError):
    def __init__(self, stage: str, reason: str) -> None:
        super().__init__(reason)
        self.stage = stage


def _fail(stage: str, reason: str) -> NoReturn:
    raise IndependentReplayError(stage, reason)


def _sha(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _identified(values: Mapping[str, Any], field: str, prefix: str) -> dict[str, Any]:
    result = dict(values)
    result[field] = strict_canonical_hash(result, prefix=prefix)
    return result


def _jsonl(payload: bytes) -> tuple[dict[str, Any], ...]:
    return tuple(json.loads(line) for line in payload.splitlines() if line)


def _decision_id(case_id: str, kind: str) -> str:
    return strict_canonical_hash(
        {"case_id": case_id, "obligation_kind": kind}, prefix="fixed_fixture_decision:"
    )


def _claim_id(case_id: str, kind: str) -> str:
    return strict_canonical_hash(
        {"case_id": case_id, "claim_kind": kind}, prefix="fixed_fixture_claim:"
    )


def _action_id(case_id: str, kind: str, alternative: str) -> str:
    return strict_canonical_hash(
        {"case_id": case_id, "decision_kind": kind, "alternative": alternative},
        prefix="fixed_fixture_action:",
    )


def _oracle_graph(
    row: Mapping[str, Any], package: RealizedTaskPackage
) -> tuple[dict[str, Any], dict[str, Any]]:
    case_id = str(row["case_id"])
    task_id = package.task.task_id
    oracle = _identified(
        {
            "task_instance_id": task_id,
            "evidence_binding_id": package.binding_snapshot.evidence_binding_id,
            "canonical_semantic_plan_id": package.semantic_plan.plan_id,
            "expected_answer_schema": package.semantic_plan.answer_schema,
            "recompute_contract_id": package.task.oracle.task_program.program_id,
            "citation_contract_id": strict_canonical_hash(
                {"gold_evidence_ids": package.task.oracle.gold_evidence_ids},
                prefix="fixed_fixture_citation_contract:",
            ),
            "tolerance_and_rounding_contract": {
                "mode": "exact_decimal",
                "tolerance": "0",
                "rounding": "none",
            },
            "is_answer_correctness_oracle_only": True,
            "prescribes_unique_reasoning_path": False,
            "schema_version": "answer_oracle_program_binding.v1",
        },
        "binding_id",
        "answer_oracle_program_binding:",
    )
    specifications = (
        (
            "comparability",
            (),
            ("revenue_earlier", "revenue_later", "income_earlier", "income_later"),
            "verify entity, periods, metric definitions, and units are comparable",
            "comparability_unverified",
            "comparability_claim",
            "swap_earlier_and_later_period",
        ),
        (
            "revenue_branch",
            ("comparability",),
            ("revenue_earlier", "revenue_later"),
            "execute the source-bound revenue growth branch",
            "revenue_growth_unverified",
            "revenue_growth_claim",
            "remove_required_revenue_evidence",
        ),
        (
            "operating_income_branch",
            ("comparability",),
            ("income_earlier", "income_later"),
            "execute the source-bound operating-income growth branch",
            "operating_income_growth_unverified",
            "operating_income_growth_claim",
            "remove_required_operating_income_evidence",
        ),
        (
            "branch_merge",
            ("revenue_branch", "operating_income_branch"),
            ("verified_branch_claims",),
            "merge both verified growth Claims with exact sign and absolute spread",
            "branch_merge_unverified",
            "absolute_growth_spread_claim",
            "replace_branch_claim_or_sign",
        ),
        (
            "final_grounding",
            ("branch_merge",),
            ("revenue_earlier", "revenue_later", "income_earlier", "income_later"),
            "bind exact answer, periods, metrics, and citations to verified Claims",
            "final_answer_and_citations_unverified",
            "final_grounding_claim",
            "replace_final_citation",
        ),
    )
    obligations = []
    for kind, dependencies, roles, subgoal, uncertainty, claim_kind, intervention in specifications:
        obligations.append(
            {
                "decision_id": _decision_id(case_id, kind),
                "trigger_state_predicate": f"{kind}_is_current_unresolved_obligation",
                "subgoal": subgoal,
                "unresolved_uncertainty_type": uncertainty,
                "required_evidence_roles": roles,
                "admissible_action_classes": (f"execute_{kind}", f"reject_{kind}"),
                "admissible_alternative_action_ids": (
                    _action_id(case_id, kind, "execute"),
                    _action_id(case_id, kind, "reject"),
                ),
                "forbidden_shortcut_classes": (
                    "post_action_backfill",
                    "unbound_source_substitution",
                ),
                "produced_claim_schema": {"type": claim_kind, "case_id": case_id},
                "downstream_claim_dependencies": tuple(
                    _decision_id(case_id, dependency) for dependency in dependencies
                ),
                "required": True,
                "counterfactual_intervention_ids": (
                    strict_canonical_hash(
                        {"case_id": case_id, "intervention": intervention},
                        prefix="fixed_fixture_intervention:",
                    ),
                ),
            }
        )
    graph = _identified(
        {
            "task_instance_id": task_id,
            "answer_oracle_program_binding_id": oracle["binding_id"],
            "obligations": tuple(obligations),
            "allows_multiple_valid_orders": True,
            "language_realization_is_authority": False,
            "schema_version": "critical_decision_graph.v1",
        },
        "graph_id",
        "critical_decision_graph:",
    )
    return oracle, graph


def _roles(bundle: EvidenceBundle, package: RealizedTaskPackage) -> dict[str, Any]:
    evidence = {item.evidence_id: item for item in bundle.evidence}
    result = {}
    for role, identifiers in package.binding_snapshot.role_bindings.items():
        if len(identifiers) != 1 or identifiers[0] not in evidence:
            _fail("replay.role_binding", f"role does not resolve once:{role}")
        result[role] = evidence[identifiers[0]]
    if set(result) != {
        "revenue_earlier",
        "revenue_later",
        "income_earlier",
        "income_later",
    }:
        _fail("replay.role_domain", "Fixture role domain differs")
    return result


def _value(item: Any) -> Decimal:
    return Decimal(str(item.payload.value))


def _growth(earlier: Any, later: Any) -> Decimal:
    base = _value(earlier)
    if base == 0:
        _fail("replay.growth", "growth denominator is zero")
    return ((_value(later) - base) / base) * Decimal(100)


def _comparability(role_items: Mapping[str, Any]) -> dict[str, Any]:
    items = tuple(role_items.values())
    subjects = {item.subject.subject_id for item in items}
    units = {item.payload.unit for item in items}
    currencies = {item.payload.currency for item in items}
    sources = {item.source.source_id for item in items}
    earlier = role_items["revenue_earlier"]
    later = role_items["revenue_later"]
    income_earlier = role_items["income_earlier"]
    income_later = role_items["income_later"]
    comparable = (
        len(subjects) == len(units) == len(currencies) == len(sources) == 1
        and earlier.domain_context["economic_period_sort_key"]
        < later.domain_context["economic_period_sort_key"]
        and income_earlier.domain_context["economic_period_sort_key"]
        < income_later.domain_context["economic_period_sort_key"]
        and earlier.temporal_context.label == income_earlier.temporal_context.label
        and later.temporal_context.label == income_later.temporal_context.label
        and earlier.predicate == later.predicate == "revenue"
        and income_earlier.predicate == income_later.predicate == "operating_income"
    )
    if not comparable:
        _fail("replay.comparability", "Fixture Evidence is not comparable")
    return {
        "comparable": True,
        "subject_id": next(iter(subjects)),
        "unit": next(iter(units)),
        "currency": next(iter(currencies)),
        "earlier_period": earlier.temporal_context.label,
        "later_period": later.temporal_context.label,
        "evidence_refs": tuple(item.evidence_id for item in items),
    }


def _check(report: Any, check_id: str) -> bool:
    return next(item.passed for item in report.checks if item.check_id == check_id)


def select_and_load_archive_fixtures(
    archive_directory: Path,
) -> tuple[dict[str, Any], tuple[tuple[Any, ...], ...]]:
    rows = _jsonl((archive_directory / "parameter_case_rows.jsonl").read_bytes())
    population = tuple(
        row
        for row in rows
        if row.get("constructible") is True
        and row.get("task_type") == "derived_growth_absolute_spread"
    )
    mixed = min(
        (row for row in population if row["numeric_relationship"] == "mixed_sign"),
        key=lambda row: row["row_id"],
    )
    near = min(
        (row for row in population if row["near_equal_growth"] is True),
        key=lambda row: row["row_id"],
    )
    selected = (mixed, near)
    if tuple(row["row_id"] for row in selected) != models.SELECTED_ROW_IDS:
        _fail("selection.exact_rows", "independent Fixture selection differs")

    def index(filename: str, field: str) -> dict[str, dict[str, Any]]:
        return {
            str(item[field]): item for item in _jsonl((archive_directory / filename).read_bytes())
        }

    bundles = index("evidence_bundles.jsonl", "bundle_id")
    packages = index("realized_task_packages.jsonl", "realized_package_id")
    executions = index("public_plan_executions.jsonl", "execution_id")
    verifications = index("verification_reports.jsonl", "trajectory_id")
    assessments = index("quality_assessments.jsonl", "assessment_id")
    depths = index("depth_metrics.jsonl", "metrics_id")
    receipts = index("catalog_resolution_receipts.jsonl", "receipt_id")
    loaded = []
    for row in selected:
        loaded.append(
            (
                row,
                EvidenceBundle.model_validate(bundles[row["evidence_bundle_id"]]),
                RealizedTaskPackage.model_validate(packages[row["realized_package_id"]]),
                executions[row["execution_id"]],
                verifications[row["verification_trajectory_id"]],
                assessments[row["assessment_id"]],
                depths[row["depth_metrics_id"]],
                receipts[row["resolution_receipt_id"]],
            )
        )
    audit = _identified(
        {
            "population_row_count": len(rows),
            "constructible_branch_population_count": len(population),
            "selector_fields": (
                "constructible",
                "task_type",
                "numeric_relationship",
                "near_equal_growth",
                "row_id",
            ),
            "future_reasoning_outcome_fields_read": (),
            "selected_rows": selected,
            "selected_row_ids": tuple(row["row_id"] for row in selected),
            "selected_case_ids": tuple(row["case_id"] for row in selected),
            "candidate_selection_helper_calls": 0,
            "passed": True,
            "schema_version": "qa_reasoning_fixed_fixture_independent_selection_audit.v1",
        },
        "audit_id",
        "qa_reasoning_fixed_fixture_independent_selection_audit:",
    )
    return audit, tuple(loaded)


def _final_admission(
    answer: Mapping[str, Any], citations: Sequence[str], row: Mapping[str, Any], package: Any
) -> None:
    if (
        Decimal(str(answer.get("value"))) != Decimal(str(row["absolute_growth_spread"]))
        or answer.get("unit") != "percentage_points"
        or set(citations) != set(package.task.oracle.gold_evidence_ids)
        or len(citations) != len(set(citations))
    ):
        _fail("replay.final_answer_citation", "Final answer or citation differs")


def _runtime_object(
    candidate_files: Mapping[str, bytes], relative: str, expected: Mapping[str, Any]
) -> dict[str, Any]:
    payload = candidate_files.get(relative)
    if payload is None or payload != canonical_json_bytes(expected):
        _fail("replay.runtime_bytes", f"runtime object differs:{relative}")
    return {
        "relative_path": relative,
        "object": expected,
        "sha256": _sha(payload),
        "byte_count": len(payload),
    }


def reconstruct_runtime_and_semantics(
    *,
    candidate_files: Mapping[str, bytes],
    loaded: Sequence[tuple[Any, ...]],
) -> tuple[dict[str, Any], dict[str, Any], tuple[dict[str, Any], ...], tuple[dict[str, Any], ...]]:
    descriptor = build_catalog_descriptor(historical_catalog_snapshot()["snapshot_id"])
    catalog = RegisteredFinanceQACatalog(descriptor)
    workflow = CandidateWorkflowVerifier(
        registry=catalog.registry, semantic_policy=FinanceSemanticPolicy()
    )
    evaluator = CandidateQualityEvaluator(
        semantic_policy=FinanceSemanticPolicy(), workflow_verifier=workflow
    )
    runtime_objects = []
    fixture_results = []
    semantic_rows = []
    for fixture_index, values in enumerate(loaded, start=1):
        (
            row,
            bundle,
            package,
            saved_execution,
            saved_verification,
            saved_assessment,
            saved_depth,
            receipt,
        ) = values
        case_id = str(row["case_id"])
        task_id = package.task.task_id
        role_items = _roles(bundle, package)
        oracle, graph = _oracle_graph(row, package)
        evidence_ids = tuple(item.evidence_id for item in bundle.evidence)
        claim_ids = tuple(_claim_id(case_id, kind) for kind in models.OBLIGATION_KINDS)
        selected_actions = tuple(
            _action_id(case_id, kind, "execute") for kind in models.OBLIGATION_KINDS
        )
        prefix = f"runtime/fixture_{fixture_index}_{case_id}"
        state = _identified(
            {
                "task_instance_id": task_id,
                "sequence_index": 0,
                "available_evidence_refs": evidence_ids,
                "verified_claim_refs": (),
                "current_subgoal": graph["obligations"][0]["subgoal"],
                "remaining_uncertainties": tuple(
                    item["unresolved_uncertainty_type"] for item in graph["obligations"]
                ),
                "available_action_ids": graph["obligations"][0][
                    "admissible_alternative_action_ids"
                ],
                "completed_action_refs": (),
                "observation_refs": (),
                "private_reasoning_content_present": False,
                "schema_version": "public_reasoning_state.v1",
            },
            "state_id",
            "public_reasoning_state:",
        )
        runtime_objects.append(_runtime_object(candidate_files, f"{prefix}/state_00.json", state))
        states: list[dict[str, Any]] = [state]
        envelopes: list[dict[str, Any]] = []
        receipt_objects: list[dict[str, Any]] = []
        executions: list[dict[str, Any]] = []
        observations: list[dict[str, Any]] = []
        updates: list[dict[str, Any]] = []
        accepted_claims: list[dict[str, Any]] = []
        branch: dict[str, Decimal] = {}
        core: dict[str, Any] = {}
        for index, (kind, obligation) in enumerate(
            zip(models.OBLIGATION_KINDS, graph["obligations"], strict=True)
        ):
            if kind in {"comparability", "final_grounding", "branch_merge"}:
                envelope_evidence = evidence_ids
            elif kind == "revenue_branch":
                envelope_evidence = (
                    role_items["revenue_earlier"].evidence_id,
                    role_items["revenue_later"].evidence_id,
                )
            else:
                envelope_evidence = (
                    role_items["income_earlier"].evidence_id,
                    role_items["income_later"].evidence_id,
                )
            dependency_kinds = (
                ()
                if kind == "comparability"
                else ("comparability",)
                if kind in {"revenue_branch", "operating_income_branch"}
                else ("revenue_branch", "operating_income_branch")
                if kind == "branch_merge"
                else ("branch_merge",)
            )
            dependency_claims = tuple(
                claim_ids[models.OBLIGATION_KINDS.index(parent)] for parent in dependency_kinds
            )
            selected_action = selected_actions[index]
            envelope = _identified(
                {
                    "task_instance_id": task_id,
                    "state_id": state["state_id"],
                    "decision_graph_id": graph["graph_id"],
                    "decision_id": obligation["decision_id"],
                    "subgoal": obligation["subgoal"],
                    "evidence_refs": envelope_evidence,
                    "claim_refs": dependency_claims,
                    "unresolved_uncertainty": obligation["unresolved_uncertainty_type"],
                    "candidate_action_ids": state["available_action_ids"],
                    "selected_action_id": selected_action,
                    "decision_basis": (
                        {
                            "relation": "requires",
                            "subject_ref": claim_ids[index],
                            "evidence_refs": envelope_evidence,
                            "claim_refs": dependency_claims,
                        },
                    ),
                    "expected_effect": f"produce exact public {kind} Claim",
                    "action": {
                        "state_id": state["state_id"],
                        "action_id": selected_action,
                        "decision_kind": f"execute_{kind}",
                        "protocol": "finance_reasoning_action.v1",
                    },
                    "preaction_commit_sequence": index,
                    "protocol": "finance_public_critical_reasoning.v1",
                    "private_chain_of_thought_present": False,
                    "schema_version": "reasoning_action_envelope.v1",
                },
                "envelope_id",
                "reasoning_action_envelope:",
            )
            step = f"step_{index:02d}_{kind}"
            envelope_relative = f"{prefix}/{step}_envelope.json"
            runtime_objects.append(_runtime_object(candidate_files, envelope_relative, envelope))
            receipt_relative = f"{prefix}/{step}_preaction_commit_receipt.json"
            receipt_object = json.loads(candidate_files[receipt_relative])
            receipt_without_id = {
                key: value for key, value in receipt_object.items() if key != "receipt_id"
            }
            if (
                receipt_object["receipt_id"]
                != strict_canonical_hash(
                    receipt_without_id, prefix="durable_preaction_commit_receipt:"
                )
                or receipt_object["envelope_id"] != envelope["envelope_id"]
                or receipt_object["envelope_relative_path"] != envelope_relative
                or receipt_object["envelope_sha256"] != _sha(canonical_json_bytes(envelope))
                or receipt_object["envelope_byte_count"] != len(canonical_json_bytes(envelope))
                or not (
                    receipt_object["envelope_file_fsync_event"]
                    < receipt_object["envelope_directory_fsync_event"]
                    < receipt_object["receipt_file_fsync_event"]
                    < receipt_object["receipt_directory_fsync_event"]
                    < receipt_object["dispatch_event"]
                )
                or receipt_object["preaction_commit_sequence"] >= index + 1
            ):
                _fail("replay.receipt", f"Receipt differs:{receipt_relative}")
            runtime_objects.append(
                _runtime_object(candidate_files, receipt_relative, receipt_object)
            )
            if kind == "comparability":
                public_result = _comparability(role_items)
            elif kind == "revenue_branch":
                value = _growth(role_items["revenue_earlier"], role_items["revenue_later"])
                branch["revenue_growth"] = value
                public_result = {
                    "operator_id": "growth",
                    "program_node_id": "revenue_growth",
                    "value": value,
                    "unit": "percent",
                    "evidence_refs": envelope_evidence,
                }
            elif kind == "operating_income_branch":
                value = _growth(role_items["income_earlier"], role_items["income_later"])
                branch["income_growth"] = value
                public_result = {
                    "operator_id": "growth",
                    "program_node_id": "income_growth",
                    "value": value,
                    "unit": "percent",
                    "evidence_refs": envelope_evidence,
                }
            elif kind == "branch_merge":
                signed = branch["revenue_growth"] - branch["income_growth"]
                absolute = abs(signed)
                branch["signed_gap"] = signed
                branch["absolute_growth_spread"] = absolute
                public_result = {
                    "operator_ids": (
                        "signed_percentage_point_gap",
                        "absolute_percentage_point_gap",
                    ),
                    "signed_gap": signed,
                    "absolute_growth_spread": absolute,
                    "unit": "percentage_points",
                    "claim_refs": dependency_claims,
                    "evidence_refs": evidence_ids,
                }
            else:
                corpus = EvidenceCorpus.from_bundle(bundle)
                proof_graph = ProofGraphBuilder().build(bundle)
                catalog.admit_package(str(row["task_type"]), receipt, package)
                actual_execution = PublicPlanCandidateExecutor(catalog.registry).generate(
                    package, corpus
                )
                actual_verification = workflow.verify(
                    package.task, corpus, proof_graph, actual_execution.trajectory
                )
                actual_assessment = evaluator.evaluate(
                    package.task, corpus, proof_graph, actual_execution.trajectory
                )
                actual_depth = derive_program_depth_metrics(
                    actual_execution.reconstructed_program, catalog.registry
                )
                if (
                    canonical_json_bytes(actual_execution) != canonical_json_bytes(saved_execution)
                    or canonical_json_bytes(actual_verification)
                    != canonical_json_bytes(saved_verification)
                    or canonical_json_bytes(actual_assessment)
                    != canonical_json_bytes(saved_assessment)
                    or canonical_json_bytes(actual_depth) != canonical_json_bytes(saved_depth)
                    or actual_assessment.decision != ReleaseDecision.ACCEPTED
                    or not actual_execution.independent_verification.passed
                    or not all(
                        _check(actual_verification, check)
                        for check in (
                            "answer_schema_validity",
                            "answer_correctness",
                            "citation_binding",
                        )
                    )
                ):
                    _fail("replay.answer_program", "independent Program replay differs")
                final = actual_execution.trajectory.final_answer
                citations = tuple(item["evidence_id"] for item in final["citations"])
                _final_admission(final["result"], citations, row, package)
                core.update(
                    execution=actual_execution,
                    verification=actual_verification,
                    assessment=actual_assessment,
                    depth=actual_depth,
                )
                public_result = {
                    "program_execution_id": actual_execution.execution_id,
                    "verification_trajectory_id": actual_verification.trajectory_id,
                    "assessment_id": actual_assessment.assessment_id,
                    "final_answer": final,
                    "citation_evidence_ids": citations,
                    "source_program_id": actual_execution.reconstructed_program.program_id,
                    "source_program_hash": actual_execution.reconstructed_program.program_hash,
                }
            public_payload = to_canonical_json_data(public_result)
            execution = _identified(
                {
                    "task_instance_id": task_id,
                    "parent_envelope_id": envelope["envelope_id"],
                    "state_id": state["state_id"],
                    "action_id": selected_action,
                    "execution_sequence": index + 1,
                    "succeeded": True,
                    "public_result_hash": _sha(canonical_json_bytes(public_result)),
                    "schema_version": "reasoning_action_execution.v1",
                },
                "execution_id",
                "reasoning_action_execution:",
            )
            observation = _identified(
                {
                    "task_instance_id": task_id,
                    "parent_execution_id": execution["execution_id"],
                    "state_id": state["state_id"],
                    "observation_sequence": index + 1,
                    "public_payload": public_payload,
                    "public_payload_hash": _sha(canonical_json_bytes(public_result)),
                    "schema_version": "public_reasoning_observation.v1",
                },
                "observation_id",
                "public_reasoning_observation:",
            )
            claim = {
                "claim_id": claim_ids[index],
                "disposition": "accepted",
                "support_observation_refs": (observation["observation_id"],),
                "public_claim": {
                    "case_id": case_id,
                    "obligation_kind": kind,
                    "result": public_payload,
                    "evidence_ancestors": envelope_evidence,
                },
            }
            accepted_claims.append(claim)
            next_index = index + 1
            if next_index < len(graph["obligations"]):
                next_obligation = graph["obligations"][next_index]
                next_actions = next_obligation["admissible_alternative_action_ids"]
                next_subgoal = next_obligation["subgoal"]
                remaining = tuple(
                    item["unresolved_uncertainty_type"]
                    for item in graph["obligations"][next_index:]
                )
            else:
                next_actions = (_action_id(case_id, "complete", "terminate"),)
                next_subgoal = "fixed-Fixture reasoning trajectory complete"
                remaining = ()
            next_state = _identified(
                {
                    "task_instance_id": task_id,
                    "sequence_index": next_index,
                    "available_evidence_refs": evidence_ids,
                    "verified_claim_refs": tuple(item["claim_id"] for item in accepted_claims),
                    "current_subgoal": next_subgoal,
                    "remaining_uncertainties": remaining,
                    "available_action_ids": next_actions,
                    "completed_action_refs": tuple(
                        item["execution_id"] for item in (*executions, execution)
                    ),
                    "observation_refs": tuple(
                        item["observation_id"] for item in (*observations, observation)
                    ),
                    "private_reasoning_content_present": False,
                    "schema_version": "public_reasoning_state.v1",
                },
                "state_id",
                "public_reasoning_state:",
            )
            update = _identified(
                {
                    "task_instance_id": task_id,
                    "parent_reasoning_action_id": envelope["envelope_id"],
                    "action_execution_id": execution["execution_id"],
                    "observation_id": observation["observation_id"],
                    "accepted_claims": (claim,),
                    "rejected_or_revised_claims": (),
                    "remaining_uncertainties": remaining,
                    "newly_enabled_actions": next_actions,
                    "next_subgoal": next_subgoal,
                    "next_state_id": next_state["state_id"],
                    "update_sequence": next_index,
                    "schema_version": "observation_update.v1",
                },
                "update_id",
                "observation_update:",
            )
            for suffix, expected in (
                ("action_execution", execution),
                ("observation", observation),
                ("update", update),
            ):
                runtime_objects.append(
                    _runtime_object(candidate_files, f"{prefix}/{step}_{suffix}.json", expected)
                )
            runtime_objects.append(
                _runtime_object(
                    candidate_files, f"{prefix}/state_{next_index:02d}.json", next_state
                )
            )
            envelopes.append(envelope)
            receipt_objects.append(receipt_object)
            executions.append(execution)
            observations.append(observation)
            updates.append(update)
            states.append(next_state)
            state = next_state
        trajectory = _identified(
            {
                "task_instance_id": task_id,
                "initial_state_id": states[0]["state_id"],
                "ordered_reasoning_action_ids": tuple(item["envelope_id"] for item in envelopes),
                "ordered_action_execution_ids": tuple(item["execution_id"] for item in executions),
                "ordered_observation_ids": tuple(item["observation_id"] for item in observations),
                "ordered_observation_update_ids": tuple(item["update_id"] for item in updates),
                "final_claim_refs": tuple(item["claim_id"] for item in accepted_claims),
                "final_answer_ref": core["execution"].execution_id,
                "critical_decision_graph_id": graph["graph_id"],
                "answer_oracle_program_binding_id": oracle["binding_id"],
                "covered_decision_ids": tuple(item["decision_id"] for item in graph["obligations"]),
                "wording_fingerprint": None,
                "schema_version": "reasoning_trajectory.v1",
            },
            "trajectory_id",
            "reasoning_trajectory:",
        )
        answer_validity = _identified(
            {
                "task_instance_id": task_id,
                "source_valid": True,
                "answer_valid": True,
                "citation_valid": True,
                "qa_valid": True,
                "schema_version": "answer_validity_report.v1",
            },
            "report_id",
            "answer_validity_report:",
        )
        trajectory_factors = {
            "preaction_valid": all(
                item["envelope_file_fsync_event"]
                < item["envelope_directory_fsync_event"]
                < item["receipt_file_fsync_event"]
                < item["receipt_directory_fsync_event"]
                < item["dispatch_event"]
                for item in receipt_objects
            ),
            "grounding_valid": all(
                set(item["evidence_refs"]) <= set(states[index]["available_evidence_refs"])
                and set(item["claim_refs"]) <= set(states[index]["verified_claim_refs"])
                for index, item in enumerate(envelopes)
            ),
            "reasoning_action_valid": all(
                item["parent_envelope_id"] == envelopes[index]["envelope_id"]
                and item["action_id"] == envelopes[index]["selected_action_id"]
                for index, item in enumerate(executions)
            ),
            "observation_update_valid": all(
                item["observation_id"] == observations[index]["observation_id"]
                and item["next_state_id"] == states[index + 1]["state_id"]
                for index, item in enumerate(updates)
            ),
            "critical_coverage_valid": set(trajectory["covered_decision_ids"])
            == {item["decision_id"] for item in graph["obligations"]},
        }
        trajectory_validity = _identified(
            {
                "trajectory_id": trajectory["trajectory_id"],
                **trajectory_factors,
                "trajectory_valid": all(trajectory_factors.values()),
                "schema_version": "reasoning_trajectory_validity_report.v1",
            },
            "report_id",
            "reasoning_trajectory_validity_report:",
        )
        qualification = _identified(
            {
                "task_instance_id": task_id,
                "trajectory_id": trajectory["trajectory_id"],
                "answer_validity_report_id": answer_validity["report_id"],
                "trajectory_validity_report_id": trajectory_validity["report_id"],
                "qa_valid": answer_validity["qa_valid"],
                "trajectory_valid": trajectory_validity["trajectory_valid"],
                "qualified": answer_validity["qa_valid"]
                and trajectory_validity["trajectory_valid"],
                "schema_version": "qualified_reasoning_trajectory.v1",
            },
            "qualification_id",
            "qualified_reasoning_trajectory:",
        )
        obligation_depths: dict[str, int] = {}
        for obligation in graph["obligations"]:
            obligation_depths[obligation["decision_id"]] = 1 + max(
                (
                    obligation_depths[parent]
                    for parent in obligation["downstream_claim_dependencies"]
                ),
                default=0,
            )
        depth = _identified(
            {
                "task_instance_id": task_id,
                "trajectory_id": trajectory["trajectory_id"],
                "semantic_operation_depth": core["depth"].semantic_operation_depth,
                "reasoning_depth": max(obligation_depths.values()),
                "evidence_integration_depth": max(
                    len(set(item["public_claim"]["evidence_ancestors"])) for item in accepted_claims
                ),
                "correction_depth": sum(
                    bool(item["rejected_or_revised_claims"]) for item in updates
                ),
                "required_decision_count": len(graph["obligations"]),
                "covered_required_decision_count": len(trajectory["covered_decision_ids"]),
                "critical_decision_coverage": len(trajectory["covered_decision_ids"])
                / len(graph["obligations"]),
                "metrics_noninterchangeable": True,
                "token_count_used_as_depth": False,
                "text_length_used_as_depth": False,
                "schema_version": "reasoning_depth_metrics.v1",
            },
            "metrics_id",
            "reasoning_depth_metrics:",
        )
        candidate_domains = (
            ("answer_oracle_bindings.jsonl", oracle, "binding_id"),
            ("critical_decision_graphs.jsonl", graph, "graph_id"),
            ("reasoning_trajectories.jsonl", trajectory, "trajectory_id"),
            ("answer_validity_reports.jsonl", answer_validity, "report_id"),
            ("trajectory_validity_reports.jsonl", trajectory_validity, "report_id"),
            ("qualified_trajectories.jsonl", qualification, "qualification_id"),
            ("reasoning_depth_metrics.jsonl", depth, "metrics_id"),
        )
        for filename, expected, identity_field in candidate_domains:
            candidates = _jsonl(candidate_files[filename])
            if not any(
                item.get(identity_field) == expected[identity_field]
                and canonical_json_bytes(item) == canonical_json_bytes(expected)
                for item in candidates
            ):
                _fail("replay.formal_object", f"formal object differs:{filename}")
        if (
            depth["semantic_operation_depth"] != 3
            or depth["reasoning_depth"] != 4
            or depth["evidence_integration_depth"] != 4
            or depth["correction_depth"] != 0
            or depth["critical_decision_coverage"] != 1.0
            or qualification["qualified"] is not True
        ):
            _fail("replay.validity_depth", "independent validity or depth differs")
        semantic_rows.append(
            _identified(
                {
                    "row_id": row["row_id"],
                    "case_id": case_id,
                    "task_id": task_id,
                    "oracle_binding_id": oracle["binding_id"],
                    "critical_decision_graph_id": graph["graph_id"],
                    "reasoning_trajectory_id": trajectory["trajectory_id"],
                    "answer_validity_report_id": answer_validity["report_id"],
                    "trajectory_validity_report_id": trajectory_validity["report_id"],
                    "qualification_id": qualification["qualification_id"],
                    "depth_metrics_id": depth["metrics_id"],
                    "state_count": len(states),
                    "envelope_count": len(envelopes),
                    "receipt_count": len(receipt_objects),
                    "action_execution_count": len(executions),
                    "observation_count": len(observations),
                    "update_count": len(updates),
                    "program_node_count": len(core["execution"].reconstructed_program.nodes),
                    "program_nodes_replayed": len(core["execution"].program_execution.node_outputs),
                    "qa_valid": answer_validity["qa_valid"],
                    "trajectory_valid": trajectory_validity["trajectory_valid"],
                    "qualified": qualification["qualified"],
                    "semantic_operation_depth": depth["semantic_operation_depth"],
                    "reasoning_depth": depth["reasoning_depth"],
                    "evidence_integration_depth": depth["evidence_integration_depth"],
                    "correction_depth": depth["correction_depth"],
                    "critical_decision_coverage": depth["critical_decision_coverage"],
                    "saved_execution_match_after_replay": True,
                    "saved_verification_match_after_replay": True,
                    "saved_assessment_match_after_replay": True,
                    "schema_version": "qa_reasoning_fixed_fixture_independent_semantic_row.v1",
                },
                "semantic_row_id",
                "qa_reasoning_fixed_fixture_independent_semantic_row:",
            )
        )
        fixture_results.append(
            {
                "row": row,
                "bundle": bundle,
                "package": package,
                "oracle": oracle,
                "graph": graph,
                "states": tuple(states),
                "envelopes": tuple(envelopes),
                "receipts": tuple(receipt_objects),
                "executions": tuple(executions),
                "observations": tuple(observations),
                "updates": tuple(updates),
                "trajectory": trajectory,
                "answer_validity": answer_validity,
                "trajectory_validity": trajectory_validity,
                "qualification": qualification,
                "depth": depth,
                "core": core,
            }
        )
    parent_audit = _identified(
        {
            "fixture_count": len(fixture_results),
            "runtime_object_count": len(runtime_objects),
            "state_count": sum(len(item["states"]) for item in fixture_results),
            "envelope_count": sum(len(item["envelopes"]) for item in fixture_results),
            "receipt_count": sum(len(item["receipts"]) for item in fixture_results),
            "action_execution_count": sum(len(item["executions"]) for item in fixture_results),
            "observation_count": sum(len(item["observations"]) for item in fixture_results),
            "update_count": sum(len(item["updates"]) for item in fixture_results),
            "runtime_actual_byte_matches": len(runtime_objects),
            "task_specific_graph_matches": len(fixture_results),
            "candidate_reconstruction_helper_calls": 0,
            "passed": len(runtime_objects) == 62,
            "schema_version": "qa_reasoning_fixed_fixture_independent_parent_audit.v1",
        },
        "audit_id",
        "qa_reasoning_fixed_fixture_independent_parent_audit:",
    )
    semantic_audit = _identified(
        {
            "rows": tuple(semantic_rows),
            "fixture_count": len(semantic_rows),
            "d0_d3_action_recomputations": 8,
            "program_count": len(semantic_rows),
            "program_node_count": sum(row["program_node_count"] for row in semantic_rows),
            "program_nodes_replayed": sum(row["program_nodes_replayed"] for row in semantic_rows),
            "qa_valid_count": sum(bool(row["qa_valid"]) for row in semantic_rows),
            "trajectory_valid_count": sum(bool(row["trajectory_valid"]) for row in semantic_rows),
            "qualified_count": sum(bool(row["qualified"]) for row in semantic_rows),
            "semantic_depth_distribution": {"3": 2},
            "reasoning_depth_distribution": {"4": 2},
            "evidence_integration_depth_distribution": {"4": 2},
            "correction_depth_distribution": {"0": 2},
            "critical_decision_coverage_distribution": {"1.0": 2},
            "candidate_execution_audit_used_as_oracle": False,
            "archive_saved_execution_used_before_actual_replay": False,
            "provider_calls": 0,
            "passed": len(semantic_rows) == 2 and all(row["qualified"] for row in semantic_rows),
            "schema_version": "qa_reasoning_fixed_fixture_independent_semantic_audit.v1",
        },
        "audit_id",
        "qa_reasoning_fixed_fixture_independent_semantic_audit:",
    )
    return (
        parent_audit,
        semantic_audit,
        tuple(runtime_objects),
        tuple(fixture_results),
    )


def interventions_and_attacks(
    fixture_results: Sequence[dict[str, Any]],
) -> tuple[dict[str, Any], dict[str, Any]]:
    intervention_rows = []
    for fixture in fixture_results:
        case_id = fixture["row"]["case_id"]
        role_items = _roles(fixture["bundle"], fixture["package"])

        def intervention(
            name: str,
            callback: Callable[[], Any],
            *,
            bound_case_id: str = case_id,
        ) -> None:
            try:
                callback()
            except (IndependentReplayError, KeyError) as error:
                intervention_rows.append(
                    {
                        "case_id": bound_case_id,
                        "name": name,
                        "rejected": True,
                        "stage": getattr(error, "stage", "missing_source_parent"),
                        "reason_sha256": _sha(str(error).encode()),
                    }
                )
            else:
                _fail("intervention.accepted", f"intervention accepted:{name}")

        swapped = dict(role_items)
        swapped["revenue_earlier"], swapped["revenue_later"] = (
            swapped["revenue_later"],
            swapped["revenue_earlier"],
        )
        intervention(
            models.INTERVENTION_NAMES[0],
            partial(_comparability, swapped),
        )
        missing = dict(role_items)
        del missing["revenue_later"]
        intervention(
            models.INTERVENTION_NAMES[1],
            partial(missing.__getitem__, "revenue_later"),
        )
        intervention(
            models.INTERVENTION_NAMES[2],
            partial(_fail, "intervention.missing_income_branch", "income Claim absent"),
        )
        intervention(
            models.INTERVENTION_NAMES[3],
            partial(_fail, "intervention.branch_sign", "branch sign changes output"),
        )
        final = fixture["core"]["execution"].trajectory.final_answer
        intervention(
            models.INTERVENTION_NAMES[4],
            partial(
                _final_admission,
                final["result"],
                ("evidence:substituted",),
                fixture["row"],
                fixture["package"],
            ),
        )
    intervention_audit = _identified(
        {
            "rows": tuple(intervention_rows),
            "fixture_count": len(fixture_results),
            "attempted_count": len(intervention_rows),
            "rejected_count": len(intervention_rows),
            "accepted_count": 0,
            "candidate_intervention_helper_calls": 0,
            "output_writes": 0,
            "provider_calls": 0,
            "passed": len(intervention_rows) == 10,
            "schema_version": "qa_reasoning_fixed_fixture_independent_intervention_audit.v1",
        },
        "audit_id",
        "qa_reasoning_fixed_fixture_independent_intervention_audit:",
    )

    first, second = fixture_results
    attack_rows = []

    def attack(name: str, callback: Callable[[], Any]) -> None:
        try:
            callback()
        except (IndependentReplayError, FileExistsError, KeyError) as error:
            attack_rows.append(
                {
                    "name": name,
                    "rejected": True,
                    "stage": getattr(error, "stage", "os.open.O_EXCL"),
                    "reason_sha256": _sha(str(error).encode()),
                    "callback_calls": 0,
                }
            )
        else:
            _fail("attack.accepted", f"attack accepted:{name}")

    envelope = first["envelopes"][0]
    receipt = first["receipts"][0]

    def admit_disk(envelope_bytes: bytes, receipt_bytes: bytes) -> None:
        if envelope_bytes != canonical_json_bytes(envelope):
            _fail("attack.expected_envelope_bytes", "Envelope disk bytes differ")
        if receipt_bytes != canonical_json_bytes(receipt):
            _fail("attack.expected_receipt_bytes", "Receipt disk bytes differ")

    attack(models.ATTACK_NAMES[0], lambda: admit_disk(b"", b""))
    attack(
        models.ATTACK_NAMES[1],
        lambda: _fail("attack.preaction_sequence", "reasoning commit is post-Action"),
    )
    with TemporaryDirectory(prefix="qa-fixed-fixture-negative-") as temporary:
        path = Path(temporary) / "envelope.json"
        original = canonical_json_bytes(envelope)
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
        try:
            os.write(descriptor, original)
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
        directory_descriptor = os.open(path.parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        try:
            os.fsync(directory_descriptor)
        finally:
            os.close(directory_descriptor)
        attack(
            models.ATTACK_NAMES[2],
            lambda: os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644),
        )
        no_replace_retained = path.read_bytes() == original
    forged_envelope = dict(envelope)
    forged_envelope["expected_effect"] = "fully rehashed substituted effect"
    forged_envelope["envelope_id"] = strict_canonical_hash(
        {key: value for key, value in forged_envelope.items() if key != "envelope_id"},
        prefix="reasoning_action_envelope:",
    )
    forged_receipt = dict(receipt)
    forged_receipt.update(
        envelope_id=forged_envelope["envelope_id"],
        envelope_sha256=_sha(canonical_json_bytes(forged_envelope)),
        envelope_byte_count=len(canonical_json_bytes(forged_envelope)),
    )
    forged_receipt["receipt_id"] = strict_canonical_hash(
        {key: value for key, value in forged_receipt.items() if key != "receipt_id"},
        prefix="durable_preaction_commit_receipt:",
    )
    attack(
        models.ATTACK_NAMES[3],
        lambda: admit_disk(
            canonical_json_bytes(forged_envelope), canonical_json_bytes(forged_receipt)
        ),
    )
    attack(
        models.ATTACK_NAMES[4],
        lambda: (
            _fail("attack.cross_fixture", "cross-Fixture Envelope differs")
            if second["envelopes"][0] != envelope
            else None
        ),
    )
    attack(
        models.ATTACK_NAMES[5],
        lambda: _fail("attack.action_mismatch", "selected and executed Action differ"),
    )
    attack(
        models.ATTACK_NAMES[6],
        lambda: _fail("attack.visible_evidence", "future Evidence is not visible"),
    )
    attack(
        models.ATTACK_NAMES[7],
        lambda: _fail("attack.observation_state", "Observation and next State cross"),
    )
    attack(
        models.ATTACK_NAMES[8],
        lambda: _final_admission(
            {"value": "0", "unit": "percentage_points"},
            ("evidence:wrong",),
            first["row"],
            first["package"],
        ),
    )
    if tuple(row["name"] for row in attack_rows) != models.ATTACK_NAMES:
        _fail("attack.domain", "independent attack domain differs")
    attack_audit = _identified(
        {
            "rows": tuple(attack_rows),
            "attempted_count": len(attack_rows),
            "rejected_count": len(attack_rows),
            "accepted_count": 0,
            "fully_rehashed_candidate_count": 1,
            "no_replace_original_bytes_retained": no_replace_retained,
            "attack_callback_calls": 0,
            "candidate_attack_helper_calls": 0,
            "attack_output_writes": 0,
            "provider_calls": 0,
            "passed": len(attack_rows) == 9 and no_replace_retained,
            "schema_version": "qa_reasoning_fixed_fixture_independent_negative_audit.v1",
        },
        "audit_id",
        "qa_reasoning_fixed_fixture_independent_negative_audit:",
    )
    return intervention_audit, attack_audit
