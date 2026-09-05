"""Independent replay of the four current persisted execution chains.

Only the frozen graph constructor, schemas, and core Program APIs are shared.
No candidate runtime, replay, quotient, saved Gate, or saved validity decision is
an outcome oracle. Durability events here are consistency evidence; the separate
detached dynamic probe supplies observations of real system calls and callbacks.
"""

from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Mapping, Sequence
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from trusted_synthesis.canonical_json import canonical_json_bytes, strict_canonical_hash
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
from trusted_synthesis.experiments.qa_reasoning_contract_freeze import models as schemas
from trusted_synthesis.experiments.qa_reasoning_fixed_fixture.models import (
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

ARCHIVE = (
    "trusted_data_synthesis/artifacts/qa_semantic_depth_three_archive_grounding/"
    "qa_semantic_operation_depth_three_plus_archive_grounded_parameter_space_"
    "constructibility_preflight_v1_20260904"
)
KINDS = (
    "comparability",
    "revenue_branch",
    "operating_income_branch",
    "branch_merge",
    "final_grounding",
)
SCHEDULES = (("D0", "D1", "D2", "D3", "D4"), ("D0", "D2", "D1", "D3", "D4"))
SOURCE_ROWS = (
    "qa_archive_parameter_case_row:4fba9ca1c78dad48c2967342be05775c8da6ae4ed1544aba5d8c4e8fbedd1e62",
    "qa_archive_parameter_case_row:08615e003521da447a78d55af5ac14f1b0cfc69e72eb650cfcb5c87deddcf39e",
)


class IndependentTrajectoryError(ValueError):
    def __init__(self, stage: str, reason: str) -> None:
        super().__init__(reason)
        self.stage = stage


def _require(condition: bool, stage: str) -> None:
    if not condition:
        raise IndependentTrajectoryError(
            stage, "independent current-trajectory reconstruction differs"
        )


def _same(actual: Any, expected: Any, stage: str) -> None:
    _require(canonical_json_bytes(actual) == canonical_json_bytes(expected), stage)


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _rows(data: bytes) -> list[dict[str, Any]]:
    return [json.loads(line) for line in data.splitlines() if line]


def _make(schema: Any, field: str, prefix: str, **values: Any) -> Any:
    provisional = schema.model_construct(**values, **{field: "pending"})
    payload = provisional.model_dump(mode="python", exclude={field})
    payload[field] = strict_canonical_hash(payload, prefix=prefix)
    return schema.model_validate(payload)


def _claim(case: str, kind: str) -> str:
    return strict_canonical_hash(
        {"case_id": case, "claim_kind": kind}, prefix="fixed_fixture_claim:"
    )


def _action(case: str, kind: str, alternative: str = "execute") -> str:
    return strict_canonical_hash(
        {"case_id": case, "decision_kind": kind, "alternative": alternative},
        prefix="fixed_fixture_action:",
    )


def select_fixtures(repo_root: Path) -> tuple[dict[str, Any], tuple[tuple[Any, ...], ...]]:
    directory = repo_root / ARCHIVE
    population = _rows((directory / "parameter_case_rows.jsonl").read_bytes())
    eligible = [
        r
        for r in population
        if r["constructible"] is True and r["task_type"] == "derived_growth_absolute_spread"
    ]
    selected = (
        min(
            (r for r in eligible if r["numeric_relationship"] == "mixed_sign"),
            key=lambda r: r["row_id"],
        ),
        min((r for r in eligible if r["near_equal_growth"] is True), key=lambda r: r["row_id"]),
    )
    _require(
        len(population) == 12 and tuple(r["row_id"] for r in selected) == SOURCE_ROWS,
        "source.fixture_selection",
    )

    def index(filename: str, key: str) -> dict[str, Any]:
        rows = _rows((directory / filename).read_bytes())
        result = {r[key]: r for r in rows}
        _require(
            all(canonical_json_bytes(r) == canonical_json_bytes(result[r[key]]) for r in rows),
            "source.conflicting_duplicate_object",
        )
        return result

    bundles = index("evidence_bundles.jsonl", "bundle_id")
    packages = index("realized_task_packages.jsonl", "realized_package_id")
    receipts = index("catalog_resolution_receipts.jsonl", "receipt_id")
    loaded = tuple(
        (
            r,
            EvidenceBundle.model_validate(bundles[r["evidence_bundle_id"]]),
            RealizedTaskPackage.model_validate(packages[r["realized_package_id"]]),
            None,
            None,
            None,
            None,
            receipts[r["resolution_receipt_id"]],
        )
        for r in selected
    )
    selection = {
        "archive_rows": len(population),
        "eligible_rows": len(eligible),
        "selected_row_ids": tuple(r["row_id"] for r in selected),
        "selected_case_ids": tuple(r["case_id"] for r in selected),
        "candidate_selection_helper_calls": 0,
        "saved_outcome_selection": False,
        "passed": True,
    }
    return selection, loaded


def _program(loaded: Sequence[Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    row, bundle, package, *_, receipt = loaded
    catalog = RegisteredFinanceQACatalog(
        build_catalog_descriptor(historical_catalog_snapshot()["snapshot_id"])
    )
    catalog.admit_package(row["task_type"], receipt, package)
    corpus = EvidenceCorpus.from_bundle(bundle)
    proof = ProofGraphBuilder().build(bundle)
    verifier = CandidateWorkflowVerifier(
        registry=catalog.registry, semantic_policy=FinanceSemanticPolicy()
    )
    execution = PublicPlanCandidateExecutor(catalog.registry).generate(package, corpus)
    verification = verifier.verify(package.task, corpus, proof, execution.trajectory)
    assessment = CandidateQualityEvaluator(
        semantic_policy=FinanceSemanticPolicy(), workflow_verifier=verifier
    ).evaluate(package.task, corpus, proof, execution.trajectory)
    core = {
        "execution": execution,
        "verification": verification,
        "assessment": assessment,
        "depth": derive_program_depth_metrics(execution.reconstructed_program, catalog.registry),
    }
    checks = {r.check_id: r.passed for r in verification.checks}
    _require(
        execution.independent_verification.passed
        and execution.independently_replayed_node_count
        == len(execution.reconstructed_program.nodes)
        and all(
            checks.get(k, False)
            for k in ("answer_schema_validity", "answer_correctness", "citation_binding")
        )
        and assessment.decision == ReleaseDecision.ACCEPTED,
        "semantics.program_verification",
    )
    _same(
        execution.reconstructed_program,
        package.task.oracle.task_program,
        "semantics.source_program",
    )
    answer = execution.trajectory.final_answer
    citations = tuple(r["evidence_id"] for r in answer["citations"])
    _require(
        len(citations) == len(set(citations))
        and set(citations) == set(package.task.oracle.gold_evidence_ids)
        and answer["result"]["unit"] == "percentage_points",
        "semantics.final_citations",
    )
    return core, {
        "program_execution_id": execution.execution_id,
        "verification_trajectory_id": verification.trajectory_id,
        "assessment_id": assessment.assessment_id,
        "final_answer": answer,
        "citation_evidence_ids": citations,
        "source_program_id": execution.reconstructed_program.program_id,
        "source_program_hash": execution.reconstructed_program.program_hash,
    }


def validate_one(
    *,
    candidate_files: Mapping[str, bytes],
    loaded: Sequence[Any],
    runtime_prefix: str,
    schedule: Sequence[str],
) -> dict[str, Any]:
    """Rebuild and compare one actual chain; also admits mutated-file controls."""
    schedule = tuple(schedule)
    _require(schedule in SCHEDULES, "replay.schedule_scope")
    row, bundle, package = loaded[:3]
    case, task = row["case_id"], package.task.task_id
    evidence = {e.evidence_id: e for e in bundle.evidence}
    roles = {}
    for role, refs in package.binding_snapshot.role_bindings.items():
        _require(len(refs) == 1 and refs[0] in evidence, "replay.source_role")
        roles[role] = evidence[refs[0]]
    _require(
        set(roles) == {"revenue_earlier", "revenue_later", "income_earlier", "income_later"},
        "replay.source_role_domain",
    )
    evidence_ids = tuple(e.evidence_id for e in bundle.evidence)
    _require(
        package.binding_snapshot.bundle_id == bundle.bundle_id
        and package.realized_package_id == row["realized_package_id"]
        and tuple(package.task.oracle.gold_evidence_ids) == evidence_ids,
        "replay.source_parents",
    )
    oracle, graph = _build_oracle_and_graph(row, package)
    obligations = dict(zip(KINDS, graph.obligations, strict=True))
    by_decision = {o.decision_id: kind for kind, o in obligations.items()}
    dependencies = {
        kind: tuple(by_decision[d] for d in o.downstream_claim_dependencies)
        for kind, o in obligations.items()
    }
    events = _rows(candidate_files["runtime_events.jsonl"])
    event_by_id = {e["event_ordinal"]: e for e in events}
    _require(len(events) == len(event_by_id), "replay.event_domain")
    snapshots = {
        s["receipt_relative_path"]: s for s in _rows(candidate_files["durable_observations.jsonl"])
    }
    parsed: dict[str, list[Any]] = {
        k: [] for k in ("states", "envelopes", "receipts", "executions", "observations", "updates")
    }
    claims: list[Any] = []
    done: list[str] = []
    paths_all: list[dict[str, str]] = []
    branch: dict[str, Decimal] = {}
    core: dict[str, Any] = {}

    def compare_file(path: str, expected: Any, stage: str) -> None:
        _require(path in candidate_files, "replay.missing_runtime_object")
        _require(candidate_files[path] == canonical_json_bytes(expected), stage)

    def state() -> Any:
        ready = [k for k in KINDS if k not in done and set(dependencies[k]) <= set(done)]
        return _make(
            schemas.PublicReasoningStateV1,
            "state_id",
            "public_reasoning_state:",
            task_instance_id=task,
            sequence_index=len(done),
            available_evidence_refs=evidence_ids,
            verified_claim_refs=tuple(c.claim_id for c in claims),
            completed_action_refs=tuple(e.execution_id for e in parsed["executions"]),
            observation_refs=tuple(o.observation_id for o in parsed["observations"]),
            available_action_ids=tuple(
                a for k in ready for a in obligations[k].admissible_alternative_action_ids
            )
            or (_action(case, "complete", "terminate"),),
            current_subgoal=(
                "resolve dependency-ready Critical Decisions: "
                + "; ".join(obligations[k].subgoal for k in ready)
            )
            if ready
            else "same-task reasoning trajectory complete",
            remaining_uncertainties=tuple(
                obligations[k].unresolved_uncertainty_type for k in KINDS if k not in done
            ),
        )

    current = state()
    compare_file(f"{runtime_prefix}/state_00.json", current, "replay.current_state")
    parsed["states"].append(current)
    for number, label in enumerate(schedule):
        kind = KINDS[int(label[1:])]
        _require(
            kind not in done and set(dependencies[kind]) <= set(done), "replay.dependency_ready"
        )
        obligation = obligations[kind]
        role = "revenue" if kind == "revenue_branch" else "income"
        refs = (
            (roles[role + "_earlier"].evidence_id, roles[role + "_later"].evidence_id)
            if kind in KINDS[1:3]
            else evidence_ids
        )
        claim_refs = tuple(_claim(case, dep) for dep in dependencies[kind])
        selected = _action(case, kind)
        envelope = _make(
            schemas.ReasoningActionEnvelopeV1,
            "envelope_id",
            "reasoning_action_envelope:",
            task_instance_id=task,
            state_id=current.state_id,
            decision_graph_id=graph.graph_id,
            decision_id=obligation.decision_id,
            subgoal=obligation.subgoal,
            unresolved_uncertainty=obligation.unresolved_uncertainty_type,
            evidence_refs=refs,
            claim_refs=claim_refs,
            selected_action_id=selected,
            candidate_action_ids=current.available_action_ids,
            preaction_commit_sequence=number,
            expected_effect=f"produce exact public {kind} Claim",
            decision_basis=(
                schemas.DecisionBasisEdgeV1(
                    relation="requires",
                    subject_ref=_claim(case, kind),
                    evidence_refs=refs,
                    claim_refs=claim_refs,
                ),
            ),
            action=schemas.PublicActionV1(
                state_id=current.state_id, action_id=selected, decision_kind=f"execute_{kind}"
            ),
        )
        stem = f"{runtime_prefix}/step_{number:02d}_{kind}"
        paths = {
            "envelope": stem + "_envelope.json",
            "receipt": stem + "_preaction_commit_receipt.json",
            "execution": stem + "_action_execution.json",
            "observation": stem + "_observation.json",
            "update": stem + "_update.json",
            "next_state": f"{runtime_prefix}/state_{number + 1:02d}.json",
        }
        compare_file(paths["envelope"], envelope, "replay.source_grounded_commitment")
        event_refs = []
        for event_kind, path in (
            ("file_fsync", paths["envelope"]),
            ("directory_fsync", paths["envelope"]),
            ("file_fsync", paths["receipt"]),
            ("directory_fsync", paths["receipt"]),
            ("action_dispatch", paths["receipt"]),
        ):
            matches = [
                e["event_ordinal"]
                for e in events
                if e["kind"] == event_kind and e["relative_path"] == path
            ]
            _require(len(matches) == 1, "replay.own_event_relation")
            event_refs.extend(matches)
        receipt = _make(
            DurablePreactionCommitReceipt,
            "receipt_id",
            "durable_preaction_commit_receipt:",
            task_instance_id=task,
            state_id=current.state_id,
            decision_id=obligation.decision_id,
            envelope_id=envelope.envelope_id,
            envelope_relative_path=paths["envelope"],
            envelope_sha256=_sha(canonical_json_bytes(envelope)),
            envelope_byte_count=len(canonical_json_bytes(envelope)),
            preaction_commit_sequence=number,
            execution_sequence=number + 1,
            envelope_file_fsync_event=event_refs[0],
            envelope_directory_fsync_event=event_refs[1],
            receipt_file_fsync_event=event_refs[2],
            receipt_directory_fsync_event=event_refs[3],
            dispatch_event=event_refs[4],
        )
        compare_file(paths["receipt"], receipt, "replay.receipt_commitment")
        snapshot = {
            "task_instance_id": task,
            "state_id": current.state_id,
            "envelope_id": envelope.envelope_id,
            "receipt_id": receipt.receipt_id,
            "envelope_relative_path": paths["envelope"],
            "receipt_relative_path": paths["receipt"],
            "envelope_sha256": _sha(candidate_files[paths["envelope"]]),
            "receipt_sha256": _sha(candidate_files[paths["receipt"]]),
            "envelope_byte_count": len(candidate_files[paths["envelope"]]),
            "receipt_byte_count": len(candidate_files[paths["receipt"]]),
            "dispatch_event": event_refs[4],
            "receipt_directory_fsync_event": event_refs[3],
            "callback_after_receipt_directory_fsync": event_refs[4] > event_refs[3],
        }
        _same(snapshots.get(paths["receipt"]), snapshot, "replay.callback_snapshot")
        if kind == "comparability":
            items = tuple(roles.values())
            early, late = roles["revenue_earlier"], roles["revenue_later"]
            _require(
                len({e.subject.subject_id for e in items}) == 1
                and len({e.payload.unit for e in items})
                == len({e.payload.currency for e in items})
                == len({e.source.source_id for e in items})
                == 1,
                "semantics.comparability",
            )
            for branch_role, predicate in (("revenue", "revenue"), ("income", "operating_income")):
                earlier, later = roles[branch_role + "_earlier"], roles[branch_role + "_later"]
                _require(
                    earlier.predicate == later.predicate == predicate
                    and earlier.domain_context["economic_period_sort_key"]
                    < later.domain_context["economic_period_sort_key"]
                    and earlier.temporal_context.label == early.temporal_context.label
                    and later.temporal_context.label == late.temporal_context.label,
                    "semantics.comparability",
                )
            payload = {
                "comparable": True,
                "subject_id": early.subject.subject_id,
                "unit": early.payload.unit,
                "currency": early.payload.currency,
                "earlier_period": early.temporal_context.label,
                "later_period": late.temporal_context.label,
                "evidence_refs": tuple(e.evidence_id for e in items),
            }
        elif kind in KINDS[1:3]:
            early_value, late_value = (
                Decimal(str(roles[role + suffix].payload.value))
                for suffix in ("_earlier", "_later")
            )
            _require(early_value != 0, "semantics.growth_denominator")
            growth = (late_value - early_value) / early_value * Decimal(100)
            branch[role] = growth
            payload = {
                "operator_id": "growth",
                "program_node_id": role + "_growth",
                "value": growth,
                "unit": "percent",
                "evidence_refs": refs,
            }
        elif kind == "branch_merge":
            _require(set(branch) == {"revenue", "income"}, "semantics.merge_dependencies")
            signed = branch["revenue"] - branch["income"]
            branch["spread"] = abs(signed)
            payload = {
                "operator_ids": ("signed_percentage_point_gap", "absolute_percentage_point_gap"),
                "signed_gap": signed,
                "absolute_growth_spread": abs(signed),
                "unit": "percentage_points",
                "claim_refs": claim_refs,
                "evidence_refs": evidence_ids,
            }
        else:
            core, payload = _program(loaded)
            _require(
                Decimal(str(payload["final_answer"]["result"]["value"])) == branch["spread"],
                "semantics.final_branch_grounding",
            )
        execution = _make(
            schemas.ActionExecutionV1,
            "execution_id",
            "reasoning_action_execution:",
            task_instance_id=task,
            parent_envelope_id=envelope.envelope_id,
            state_id=current.state_id,
            action_id=selected,
            execution_sequence=number + 1,
            succeeded=True,
            public_result_hash=_sha(canonical_json_bytes(payload)),
        )
        observation = _make(
            schemas.PublicObservationV1,
            "observation_id",
            "public_reasoning_observation:",
            task_instance_id=task,
            parent_execution_id=execution.execution_id,
            state_id=current.state_id,
            observation_sequence=number + 1,
            public_payload=json.loads(canonical_json_bytes(payload)),
            public_payload_hash=_sha(canonical_json_bytes(payload)),
        )
        claim = schemas.ClaimUpdateV1(
            claim_id=_claim(case, kind),
            disposition="accepted",
            support_observation_refs=(observation.observation_id,),
            public_claim={
                "case_id": case,
                "obligation_kind": kind,
                "result": json.loads(canonical_json_bytes(payload)),
                "evidence_ancestors": refs,
            },
        )
        for name, value in (
            ("envelopes", envelope),
            ("receipts", receipt),
            ("executions", execution),
            ("observations", observation),
        ):
            parsed[name].append(value)
        done.append(kind)
        claims.append(claim)
        following = state()
        update = _make(
            schemas.ObservationUpdateV1,
            "update_id",
            "observation_update:",
            task_instance_id=task,
            parent_reasoning_action_id=envelope.envelope_id,
            action_execution_id=execution.execution_id,
            observation_id=observation.observation_id,
            accepted_claims=(claim,),
            rejected_or_revised_claims=(),
            remaining_uncertainties=following.remaining_uncertainties,
            newly_enabled_actions=following.available_action_ids,
            next_subgoal=following.current_subgoal,
            next_state_id=following.state_id,
            update_sequence=number + 1,
        )
        for name, value in (
            ("execution", execution),
            ("observation", observation),
            ("update", update),
            ("next_state", following),
        ):
            compare_file(paths[name], value, "replay.independent_" + name)
        parsed["updates"].append(update)
        parsed["states"].append(following)
        paths_all.append(paths)
        current = following
    trajectory = _make(
        schemas.ReasoningTrajectoryV1,
        "trajectory_id",
        "reasoning_trajectory:",
        task_instance_id=task,
        initial_state_id=parsed["states"][0].state_id,
        ordered_reasoning_action_ids=tuple(e.envelope_id for e in parsed["envelopes"]),
        ordered_action_execution_ids=tuple(e.execution_id for e in parsed["executions"]),
        ordered_observation_ids=tuple(e.observation_id for e in parsed["observations"]),
        ordered_observation_update_ids=tuple(e.update_id for e in parsed["updates"]),
        final_claim_refs=tuple(c.claim_id for c in claims),
        final_answer_ref=core["execution"].execution_id,
        critical_decision_graph_id=graph.graph_id,
        answer_oracle_program_binding_id=oracle.binding_id,
        covered_decision_ids=tuple(obligations[k].decision_id for k in done),
        wording_fingerprint=None,
    )
    qa = _make(
        schemas.AnswerValidityReportV1,
        "report_id",
        "answer_validity_report:",
        task_instance_id=task,
        source_valid=True,
        answer_valid=True,
        citation_valid=True,
        qa_valid=True,
    )
    tv = _make(
        schemas.TrajectoryValidityReportV1,
        "report_id",
        "reasoning_trajectory_validity_report:",
        trajectory_id=trajectory.trajectory_id,
        preaction_valid=True,
        grounding_valid=True,
        reasoning_action_valid=True,
        observation_update_valid=True,
        critical_coverage_valid=True,
        trajectory_valid=True,
    )
    qualified = _make(
        schemas.QualifiedReasoningTrajectoryV1,
        "qualification_id",
        "qualified_reasoning_trajectory:",
        task_instance_id=task,
        trajectory_id=trajectory.trajectory_id,
        answer_validity_report_id=qa.report_id,
        trajectory_validity_report_id=tv.report_id,
        qa_valid=qa.qa_valid,
        trajectory_valid=tv.trajectory_valid,
        qualified=qa.qa_valid and tv.trajectory_valid,
    )
    decision_depth: dict[str, int] = {}
    for kind in KINDS:
        decision_depth[kind] = 1 + max((decision_depth[k] for k in dependencies[kind]), default=0)
    depth = _make(
        schemas.ReasoningDepthMetricsV1,
        "metrics_id",
        "reasoning_depth_metrics:",
        task_instance_id=task,
        trajectory_id=trajectory.trajectory_id,
        semantic_operation_depth=core["depth"].semantic_operation_depth,
        reasoning_depth=max(decision_depth.values()),
        evidence_integration_depth=max(
            len(set(c.public_claim["evidence_ancestors"])) for c in claims
        ),
        correction_depth=sum(bool(u.rejected_or_revised_claims) for u in parsed["updates"]),
        required_decision_count=len(obligations),
        covered_required_decision_count=len(set(done)),
        critical_decision_coverage=len(set(done)) / len(obligations),
    )
    result = {
        "loaded": tuple(loaded),
        "row": row,
        "bundle": bundle,
        "package": package,
        "oracle": oracle,
        "graph": graph,
        "core": core,
        "trajectory": trajectory,
        "answer_validity": qa,
        "trajectory_validity": tv,
        "qualification": qualified,
        "depth": depth,
        "claims": tuple(claims),
        "schedule": schedule,
        "runtime_prefix": runtime_prefix,
        "step_paths": tuple(paths_all),
        **{k: tuple(v) for k, v in parsed.items()},
    }
    replay = {
        "independent_replay": True,
        "passed": True,
        "trajectory_id": trajectory.trajectory_id,
        "runtime_prefix": runtime_prefix,
        "runtime_objects_reconstructed": 31,
        "actual_action_results_recomputed": 5,
        "program_nodes_replayed": len(core["execution"].reconstructed_program.nodes),
        "qa_valid": qa.qa_valid,
        "trajectory_valid": tv.trajectory_valid,
        "qualified": qualified.qualified,
        "candidate_runtime_helper_calls": 0,
        "candidate_validation_helper_calls": 0,
        "replay_input_sha256": strict_canonical_hash(
            {
                k: result[k]
                for k in (
                    "trajectory",
                    "envelopes",
                    "executions",
                    "observations",
                    "updates",
                    "qualification",
                )
            }
        ),
    }
    replay["audit_id"] = strict_canonical_hash(
        replay, prefix="qa_multitrajectory_independent_own_replay:"
    )
    result["replay_audit"] = replay
    return result


def audit_trajectories(
    *, repo_root: Path, candidate_files: Mapping[str, bytes]
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    selection, loaded = select_fixtures(repo_root)
    results = [
        validate_one(
            candidate_files=candidate_files,
            loaded=fixture,
            runtime_prefix=f"runtime/fixture_{fi}/schedule_{si}",
            schedule=schedule,
        )
        for fi, fixture in enumerate(loaded, 1)
        for si, schedule in enumerate(SCHEDULES, 1)
    ]
    # Comparisons begin only after selecting source rows and executing all own chains.
    saved_selection = json.loads(candidate_files["selection_audit.json"])
    _same(
        saved_selection["selected_row_ids"], selection["selected_row_ids"], "comparison.source_rows"
    )
    registration = json.loads(candidate_files["preregistration.json"])
    _require(len(registration["task_parents"]) == 2, "comparison.registered_task_count")
    for parent, fixture in zip(registration["task_parents"], loaded, strict=True):
        row, bundle, package = fixture[:3]
        expected = {
            "case_id": row["case_id"],
            "row_id": row["row_id"],
            "task_id": package.task.task_id,
            "task_bytes_sha256": _sha(canonical_json_bytes(package.task)),
            "package_id": package.realized_package_id,
            "package_bytes_sha256": _sha(canonical_json_bytes(package)),
            "bundle_id": bundle.bundle_id,
            "bundle_bytes_sha256": _sha(canonical_json_bytes(bundle)),
            "answer_program_id": package.task.oracle.task_program.program_id,
            "schedules": tuple(tuple(KINDS[int(label[1:])] for label in s) for s in SCHEDULES),
        }
        _same(parent, expected, "comparison.same_task_parent")
    projections = {
        "reasoning_trajectories": [r["trajectory"] for r in results],
        "answer_validity": [r["answer_validity"] for r in results],
        "trajectory_validity": [r["trajectory_validity"] for r in results],
        "qualified_trajectories": [r["qualification"] for r in results],
        "critical_decision_graphs": [r["graph"] for r in results[::2]],
        "answer_oracle_bindings": [r["oracle"] for r in results[::2]],
        "program_executions": [r["core"]["execution"] for r in results],
        "verification_reports": [r["core"]["verification"] for r in results],
        "quality_assessments": [r["core"]["assessment"] for r in results],
        "depth_metrics": [r["depth"] for r in results],
    }
    for name, projected_values in projections.items():
        _require(
            candidate_files[name + ".jsonl"]
            == b"".join(canonical_json_bytes(v) + b"\n" for v in projected_values),
            "comparison." + name,
        )
    runtime_paths = {p for p in candidate_files if p.startswith("runtime/")}
    expected_paths = {f"{r['runtime_prefix']}/state_00.json" for r in results}
    expected_paths.update(p for r in results for paths in r["step_paths"] for p in paths.values())
    _require(
        runtime_paths == expected_paths and len(runtime_paths) == 124,
        "comparison.runtime_path_domain",
    )
    audit = {
        "selection": selection,
        "task_count": len(loaded),
        "trajectory_count": len(results),
        "runtime_objects_reconstructed": len(runtime_paths),
        "action_results_recomputed": 20,
        "program_nodes_replayed": sum(r["replay_audit"]["program_nodes_replayed"] for r in results),
        "qa_valid": sum(r["qualification"].qa_valid for r in results),
        "trajectory_valid": sum(r["qualification"].trajectory_valid for r in results),
        "qualified": sum(r["qualification"].qualified for r in results),
        "depth_rows": tuple(r["depth"] for r in results),
        "own_replay_rows": tuple(r["replay_audit"] for r in results),
        "same_task_parent_matches": 2,
        "saved_outcomes_used_as_oracle": False,
        "saved_event_integers_alone_prove_durability": False,
        "dynamic_durability_audit_required": True,
        "candidate_runtime_helper_calls": 0,
        "candidate_validation_helper_calls": 0,
        "candidate_quotient_helper_calls": 0,
        "provider_calls": 0,
        "passed": True,
    }
    audit["audit_id"] = strict_canonical_hash(
        audit, prefix="qa_multitrajectory_independent_semantics:"
    )
    return audit, results


def independent_runtime_controls(
    candidate_files: Mapping[str, bytes], results: Sequence[Mapping[str, Any]]
) -> dict[str, Any]:
    """Actual scratch-file mutations; four have valid single-object fresh hashes."""
    result = results[0]
    step = result["step_paths"][0]
    specifications = (
        (
            "missing_durable_receipt",
            "receipt",
            None,
            "receipt_id",
            "durable_preaction_commit_receipt:",
        ),
        (
            "rehashed_single_observation_wrong_result",
            "observation",
            schemas.PublicObservationV1,
            "observation_id",
            "public_reasoning_observation:",
        ),
        (
            "rehashed_single_envelope_future_evidence",
            "envelope",
            schemas.ReasoningActionEnvelopeV1,
            "envelope_id",
            "reasoning_action_envelope:",
        ),
        (
            "rehashed_single_update_cross_task",
            "update",
            schemas.ObservationUpdateV1,
            "update_id",
            "observation_update:",
        ),
        (
            "rehashed_single_execution_wrong_action",
            "execution",
            schemas.ActionExecutionV1,
            "execution_id",
            "reasoning_action_execution:",
        ),
    )
    controls = []
    for name, domain, schema, field, prefix in specifications:
        with TemporaryDirectory(prefix="qa-independent-current-mutation-") as temporary:
            target = Path(temporary) / "candidate.json"
            original = candidate_files[step[domain]]
            target.write_bytes(original)
            rehashed = schema is not None
            if schema is None:
                target.rename(target.with_suffix(".withheld"))
            else:
                candidate = json.loads(target.read_bytes())
                if domain == "observation":
                    candidate["public_payload"]["comparable"] = False
                    candidate["public_payload_hash"] = _sha(
                        canonical_json_bytes(candidate["public_payload"])
                    )
                elif domain == "envelope":
                    candidate["evidence_refs"].append("evidence:future_unobserved")
                elif domain == "update":
                    candidate["task_instance_id"] = results[2]["package"].task.task_id
                else:
                    candidate["action_id"] = "action:unselected"
                candidate[field] = strict_canonical_hash(
                    {key: value for key, value in candidate.items() if key != field}, prefix=prefix
                )
                validated = schema.model_validate(candidate)
                target.write_bytes(canonical_json_bytes(validated))
            changed = dict(candidate_files)
            if target.exists():
                changed[step[domain]] = target.read_bytes()
            else:
                del changed[step[domain]]
            try:
                validate_one(
                    candidate_files=changed,
                    loaded=result["loaded"],
                    runtime_prefix=result["runtime_prefix"],
                    schedule=result["schedule"],
                )
            except IndependentTrajectoryError as error:
                controls.append(
                    {
                        "name": name,
                        "rejected": True,
                        "stage": error.stage,
                        "exception": type(error).__name__,
                        "reason_sha256": _sha(str(error).encode()),
                        "single_object_rehashed": rehashed,
                        "candidate_schema_passed": rehashed,
                        "actual_scratch_file_mutation": True,
                        "formal_attack_writes": 0,
                    }
                )
            else:
                raise IndependentTrajectoryError(
                    "controls.accepted", "independent runtime mutation was accepted"
                )
    with TemporaryDirectory(prefix="qa-independent-no-replace-") as temporary:
        target = Path(temporary) / "envelope.json"
        original = candidate_files[step["envelope"]]
        target.write_bytes(original)
        try:
            descriptor = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError as error:
            controls.append(
                {
                    "name": "no_replace_original_envelope",
                    "rejected": True,
                    "stage": "independent_os_open_create_exclusive",
                    "exception": type(error).__name__,
                    "errno": error.errno,
                    "single_object_rehashed": False,
                    "actual_scratch_file_mutation": False,
                    "formal_attack_writes": 0,
                }
            )
        else:
            os.close(descriptor)
            raise IndependentTrajectoryError(
                "controls.accepted", "exclusive creation replaced existing Envelope"
            )
        _require(target.read_bytes() == original, "controls.original_preserved")
    audit = {
        "controls": tuple(controls),
        "attempted": len(controls),
        "rejected": len(controls),
        "accepted": 0,
        "single_object_rehashed_controls": 4,
        "joint_full_chain_rehash_claimed": False,
        "candidate_attack_helper_calls": 0,
        "formal_attack_writes": 0,
        "provider_calls": 0,
        "passed": True,
    }
    audit["audit_id"] = strict_canonical_hash(
        audit, prefix="qa_multitrajectory_independent_runtime_controls:"
    )
    return audit
