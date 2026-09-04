from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from collections.abc import Callable, Mapping, Sequence
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

from trusted_synthesis.canonical_json import canonical_json_bytes, strict_canonical_hash
from trusted_synthesis.core.evaluation.evaluator import CandidateQualityEvaluator
from trusted_synthesis.core.evaluation.schema import ReleaseDecision
from trusted_synthesis.core.evidence.corpus import EvidenceCorpus
from trusted_synthesis.core.evidence.payloads import ScalarObservation
from trusted_synthesis.core.evidence.schema import EvidenceBundle, EvidenceItem
from trusted_synthesis.core.graph.builder import ProofGraphBuilder
from trusted_synthesis.core.immutable_artifacts import write_immutable_artifact_directory
from trusted_synthesis.core.task.binding import make_evidence_binding
from trusted_synthesis.core.task.pattern_compiler import TaskPatternCompiler
from trusted_synthesis.core.task.program import (
    InputRefKind,
    OperationNode,
    ProgramInputRef,
    TaskProgram,
    make_program,
)
from trusted_synthesis.core.task.program_depth import (
    admit_program_depth_metrics,
    derive_program_depth_metrics,
)
from trusted_synthesis.core.task.realization import RealizedTaskPackage, realize_task
from trusted_synthesis.core.task.semantic import build_semantic_binding_bundle
from trusted_synthesis.core.trajectory.candidate_verifier import CandidateWorkflowVerifier
from trusted_synthesis.core.trajectory.public_plan_executor import PublicPlanCandidateExecutor
from trusted_synthesis.core.trajectory.schema import Trajectory
from trusted_synthesis.domains.finance.policy import FinanceSemanticPolicy
from trusted_synthesis.experiments.counterfactual_finance_fixture import (
    build_finance_counterfactual_case,
)
from trusted_synthesis.hashing import canonical_hash

from . import models
from .operations import depth_three_operation_registry
from .patterns import (
    BRANCH_TASK_TYPE,
    SERIAL_TASK_TYPE,
    DepthThreePatternRuntime,
    depth_three_patterns,
    depth_three_renderer_profiles,
)


def _git_text(root: Path, *arguments: str) -> str:
    return subprocess.run(
        ("git", "-C", str(root), *arguments),
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _git_bytes(root: Path, *arguments: str) -> bytes:
    return subprocess.run(
        ("git", "-C", str(root), *arguments),
        check=True,
        capture_output=True,
    ).stdout


def _directory_files(directory: Path) -> dict[str, bytes]:
    return {
        path.relative_to(directory).as_posix(): path.read_bytes()
        for path in directory.rglob("*")
        if path.is_file()
    }


def _freeze_predecessor(root: Path, authorization_id: str) -> models.PredecessorFreeze:
    directory = root / models.PREDECESSOR_DIRECTORY
    files = _directory_files(directory)
    manifest = json.loads(files["artifact_manifest.json"])
    members = manifest.get("members")
    if not isinstance(members, list):
        raise ValueError("predecessor Manifest members are absent")
    member_map = {str(item["relative_path"]): item for item in members}
    if set(member_map) != set(files) - {"artifact_manifest.json"}:
        raise ValueError("predecessor Manifest path set differs")
    for relative_path, item in member_map.items():
        payload = files[relative_path]
        if (
            int(item["byte_count"]) != len(payload)
            or str(item["sha256"]) != hashlib.sha256(payload).hexdigest()
        ):
            raise ValueError(f"predecessor member bytes differ:{relative_path}")
    report = json.loads(files["report.json"])
    decision = json.loads(files["decision.json"])
    transition = json.loads(files["transition.json"])
    depth = json.loads(files["depth_metric_audit.json"])
    if (
        len(files) != 21
        or sum(map(len, files.values())) != 99_487
        or manifest.get("file_count") != 20
        or manifest.get("member_bytes") != 96_276
        or manifest.get("manifest_id") != models.PREDECESSOR_MANIFEST_ID
        or manifest.get("artifact_root") != models.PREDECESSOR_ARTIFACT_ROOT
        or report.get("report_id") != models.PREDECESSOR_REPORT_ID
        or decision.get("decision_id") != models.PREDECESSOR_DECISION_ID
        or transition.get("transition_id") != models.PREDECESSOR_TRANSITION_ID
        or transition.get("next_stage") != models.STAGE
        or transition.get("next_stage_authorized") is not False
        or transition.get("separate_external_audit_decision_required") is not True
        or depth.get("semantic_operation_depth_distribution") != {"0": 1, "1": 6, "2": 1}
        or depth.get("maximum_semantic_operation_depth") != 2
        or depth.get("semantic_depth_three_plus_count") != 0
    ):
        raise ValueError("predecessor QA independent-audit authority differs")
    return models.identified(
        models.PredecessorFreeze,
        {
            "authorization_id": authorization_id,
            "file_count": len(files),
            "total_byte_count": sum(map(len, files.values())),
            "manifest_member_count": len(members),
            "manifest_member_bytes": sum(int(item["byte_count"]) for item in members),
        },
        "freeze_id",
        "qa_semantic_depth_three_plus_predecessor_freeze:",
    )


def _source_binding(
    root: Path,
    authorization_id: str,
    source_commit: str,
    source_tree: str,
) -> models.SourceBinding:
    resolved_commit = _git_text(root, "rev-parse", f"{source_commit}^{{commit}}")
    resolved_tree = _git_text(root, "rev-parse", f"{resolved_commit}^{{tree}}")
    if _git_text(root, "cat-file", "-t", resolved_commit) != "commit":
        raise ValueError("source authority did not resolve a commit")
    if source_commit != resolved_commit or source_tree != resolved_tree:
        raise ValueError("source commit/tree relation differs")
    members = []
    for relative_path in models.SOURCE_PATHS:
        committed = _git_bytes(root, "show", f"{resolved_commit}:{relative_path}")
        current = (root / relative_path).read_bytes()
        blob = hashlib.sha1(
            f"blob {len(committed)}\0".encode("ascii") + committed,
            usedforsecurity=False,
        ).hexdigest()
        resolved_blob = _git_text(root, "rev-parse", f"{resolved_commit}:{relative_path}")
        if blob != resolved_blob or committed != current:
            raise ValueError(f"source member authority differs:{relative_path}")
        members.append(
            models.SourceMember(
                relative_path=relative_path,
                git_blob_oid=blob,
                committed_sha256=hashlib.sha256(committed).hexdigest(),
                committed_byte_count=len(committed),
                current_sha256=hashlib.sha256(current).hexdigest(),
                current_byte_count=len(current),
            )
        )
    rows = tuple(item.model_dump(mode="json") for item in members)
    return models.identified(
        models.SourceBinding,
        {
            "authorization_id": authorization_id,
            "requested_commit": source_commit,
            "resolved_commit": resolved_commit,
            "requested_tree": source_tree,
            "resolved_tree": resolved_tree,
            "members": tuple(members),
            "path_set_sha256": hashlib.sha256(
                canonical_json_bytes(models.SOURCE_PATHS)
            ).hexdigest(),
            "member_set_sha256": hashlib.sha256(canonical_json_bytes(rows)).hexdigest(),
        },
        "binding_id",
        "qa_semantic_depth_three_plus_source_binding:",
    )


def _registry_binding(source_binding_id: str) -> models.RegistryBinding:
    registry = depth_three_operation_registry()
    manifest = registry.manifest()
    extension_ids = {
        "absolute_percentage_point_gap",
        "scale_ratio_percent",
        "signed_percentage_point_gap",
    }
    extension = tuple(item for item in manifest if item["operator_id"] in extension_ids)
    if (
        len(extension) != 3
        or any(item["program_role"] != "semantic" for item in extension)
        or any(item["executor"] == item["oracle_verifier"] for item in extension)
    ):
        raise ValueError("depth-three operation Registry is not authoritative")
    manifest_sha = strict_canonical_hash(
        manifest, prefix="qa_semantic_depth_three_plus_registry_manifest:"
    ).rsplit(":", maxsplit=1)[-1]
    return models.identified(
        models.RegistryBinding,
        {
            "source_binding_id": source_binding_id,
            "registry_manifest_sha256": manifest_sha,
            "base_operator_count": len(manifest) - len(extension),
        },
        "binding_id",
        "qa_semantic_depth_three_plus_registry_binding:",
    )


def _evidence(
    fixture_id: str,
    predicate: str,
    year: int,
    value: str,
    *,
    unit: str = "million USD",
) -> EvidenceItem:
    source = build_finance_counterfactual_case(1).bundle.evidence[0]
    subject_id = "QA_DEPTH_THREE_COMPANY_A"
    suffix = f"{fixture_id}_{predicate}_{year}".casefold()
    statement_type = "management_target" if predicate.endswith("_target") else "income_statement"
    return source.model_copy(
        update={
            "evidence_id": f"evidence:finance:{suffix}@qa_depth_three",
            "assertion_id": f"assertion:finance:{suffix}",
            "evidence_version_id": f"version:finance:{suffix}@qa_depth_three",
            "subject": source.subject.model_copy(
                update={"subject_id": subject_id, "name": "QA Depth Three Company A"}
            ),
            "predicate": predicate,
            "payload": ScalarObservation(
                value=Decimal(value),
                unit=unit,
                currency="USD" if unit == "million USD" else None,
            ),
            "temporal_context": source.temporal_context.model_copy(
                update={
                    "label": f"FY{year}",
                    "valid_from": date(year - 1, 10, 1),
                    "valid_to": date(year, 9, 30),
                    "observed_at": None,
                    "basis": "fiscal_period",
                    "frequency": "annual",
                }
            ),
            "scope": source.scope.model_copy(
                update={"scope_id": subject_id, "label": f"{subject_id} consolidated"}
            ),
            "source_locator": source.source_locator.model_copy(
                update={"raw_object_id": f"raw_qa_depth_three_{suffix}"}
            ),
            "definition": source.definition.model_copy(
                update={
                    "definition_id": f"sdef_{predicate}_depth_three",
                    "text": f"Exact {predicate.replace('_', ' ')} for the consolidated entity.",
                    "attributes": {
                        **source.definition.attributes,
                        "comparability_level": "exact_experimental_fixture",
                        "statement_type": statement_type,
                        "period_type": "duration",
                        "default_unit": unit,
                    },
                }
            ),
            "provenance": source.provenance.model_copy(
                update={"source_record_id": f"qa_depth_three_{suffix}"}
            ),
            "domain_context": {
                **source.domain_context,
                "fiscal_year": year,
                "economic_period_year": year,
                "statement_type": statement_type,
                "period_type": "duration",
                "is_forecast": False,
                "experimental_fixture": True,
            },
        }
    )


def _bundle(case_id: str, evidence: tuple[EvidenceItem, ...]) -> EvidenceBundle:
    identity = {
        "case_id": case_id,
        "evidence_ids": tuple(item.evidence_id for item in evidence),
        "evidence_version_ids": tuple(item.evidence_version_id for item in evidence),
        "schema_version": "qa_semantic_depth_three_fixture_bundle.v1",
    }
    return EvidenceBundle(
        bundle_id=strict_canonical_hash(identity, prefix="qa_semantic_depth_three_fixture_bundle:"),
        evidence=evidence,
        purpose="credential-free semantic-depth-three constructibility preflight",
        graph_build_id=f"qa_semantic_depth_three_graph:{case_id}",
        metadata={"provider_generated": False, "stage": models.STAGE},
    )


def _fixture_inputs() -> dict[str, tuple[EvidenceBundle, dict[str, tuple[str, ...]]]]:
    serial = _bundle(
        "serial_margin_target_gap",
        (
            _evidence("serial", "gross_profit", 2025, "60"),
            _evidence("serial", "revenue", 2025, "120"),
            _evidence("serial", "gross_margin_target", 2025, "45", unit="percent"),
        ),
    )
    branch = _bundle(
        "branch_merge_growth_gap",
        (
            _evidence("branch", "revenue", 2024, "100"),
            _evidence("branch", "revenue", 2025, "130"),
            _evidence("branch", "operating_income", 2024, "20"),
            _evidence("branch", "operating_income", 2025, "25"),
        ),
    )
    return {
        "branch_merge_growth_gap": (
            branch,
            {
                "revenue_earlier": (branch.evidence[0].evidence_id,),
                "revenue_later": (branch.evidence[1].evidence_id,),
                "income_earlier": (branch.evidence[2].evidence_id,),
                "income_later": (branch.evidence[3].evidence_id,),
            },
        ),
        "serial_margin_target_gap": (
            serial,
            {
                "numerator": (serial.evidence[0].evidence_id,),
                "denominator": (serial.evidence[1].evidence_id,),
                "target": (serial.evidence[2].evidence_id,),
            },
        ),
    }


def _compile_realized(
    *,
    case_id: str,
    bundle: EvidenceBundle,
    role_bindings: dict[str, tuple[str, ...]],
    registry: Any,
) -> RealizedTaskPackage:
    patterns = {pattern.task_type: pattern for pattern in depth_three_patterns()}
    task_type = BRANCH_TASK_TYPE if case_id == "branch_merge_growth_gap" else SERIAL_TASK_TYPE
    pattern = patterns[task_type]
    runtime = DepthThreePatternRuntime()
    graph = ProofGraphBuilder().build(bundle)
    binding = make_evidence_binding(
        pattern_id=pattern.pattern_id,
        pattern_version=pattern.pattern_version,
        pattern_hash=pattern.pattern_hash,
        role_bindings=role_bindings,
        source_graph_id=graph.graph_id,
        domain_snapshot_id=graph.source_build_id,
    )
    instantiation = TaskPatternCompiler(registry, runtime).compile(pattern, binding, bundle, graph)
    semantic = build_semantic_binding_bundle(
        pattern=pattern,
        program=instantiation.program,
        binding=binding,
        bundle=bundle,
        proof_graph=graph,
        registry=registry,
        effective_answer_schema=instantiation.task.public.answer_schema,
    )
    by_id = {item.evidence_id: item for item in bundle.evidence}
    evidence_by_role = {
        role: tuple(by_id[evidence_id] for evidence_id in ids)
        for role, ids in role_bindings.items()
    }
    profile = next(item for item in depth_three_renderer_profiles() if item.task_type == task_type)
    return realize_task(
        plan=semantic.plan,
        binding=semantic.binding,
        instance=semantic.instance,
        task=instantiation.task,
        profile=profile,
        slot_values=runtime.slot_values(task_type, evidence_by_role),
    )


def _check(report: Any, check_id: str) -> bool:
    return next(item.passed for item in report.checks if item.check_id == check_id)


def _coverage_row(
    *,
    authorization_id: str,
    source_binding_id: str,
    registry_binding_id: str,
    case_id: str,
    bundle: EvidenceBundle,
    package: RealizedTaskPackage,
    execution: Any,
    verification: Any,
    assessment: Any,
    metrics: Any,
) -> models.CoverageRow:
    topology = "branch_and_merge" if case_id.startswith("branch") else "serial_chain"
    semantic_sequence = (
        (
            "growth|growth",
            "signed_percentage_point_gap",
            "absolute_percentage_point_gap",
        )
        if topology == "branch_and_merge"
        else ("ratio", "scale_ratio_percent", "signed_percentage_point_gap")
    )
    program = execution.reconstructed_program
    values = {
        "authorization_id": authorization_id,
        "source_binding_id": source_binding_id,
        "registry_binding_id": registry_binding_id,
        "case_id": case_id,
        "task_type": package.task.public.task_type,
        "topology_kind": topology,
        "evidence_bundle_id": bundle.bundle_id,
        "realized_package_id": package.realized_package_id,
        "source_program_id": program.program_id,
        "source_program_hash": program.program_hash,
        "topology_hash": package.semantic_plan.topology_hash,
        "execution_id": execution.execution_id,
        "trajectory_id": execution.trajectory.trajectory_id,
        "verification_trajectory_id": verification.trajectory_id,
        "assessment_id": assessment.assessment_id,
        "depth_metrics_id": metrics.metrics_id,
        "operator_sequence": tuple(node.operator_id for node in program.nodes),
        "semantic_transition_sequence": semantic_sequence,
        "node_count": len(program.nodes),
        "edge_count": sum(len(node.dependencies) for node in program.nodes),
        "structural_dependency_depth": metrics.structural_dependency_depth,
        "semantic_operation_depth": metrics.semantic_operation_depth,
        "workflow_interaction_depth": metrics.workflow_interaction_depth,
        "source_program_exact": (
            program == package.task.oracle.task_program
            and program.program_id == package.semantic_plan.source_program_id
            and program.program_hash == package.semantic_plan.source_program_hash
        ),
        "output_dependency_closed": metrics.output_dependency_closed,
        "program_execution_complete": len(execution.program_execution.node_outputs)
        == len(program.nodes),
        "independent_node_replay_passed": execution.independent_verification.passed,
        "answer_schema_correct": _check(verification, "answer_schema_validity"),
        "answer_correct": _check(verification, "answer_correctness"),
        "citation_correct": _check(verification, "citation_binding"),
        "evaluator_accepted": assessment.decision == ReleaseDecision.ACCEPTED,
    }
    return models.identified(
        models.CoverageRow,
        values,
        "row_id",
        "qa_semantic_depth_three_plus_coverage_row:",
    )


def _rehashed_trajectory(trajectory: Trajectory, final_answer: dict[str, Any]) -> Trajectory:
    values = trajectory.model_dump(mode="python", exclude={"trajectory_id"})
    values["final_answer"] = final_answer
    values["trajectory_id"] = canonical_hash(
        values, prefix="qa_semantic_depth_three_plus_attack_trajectory:"
    )
    return Trajectory.model_validate(values)


def _negative_controls(
    *,
    authorization_id: str,
    cases: Mapping[str, dict[str, Any]],
    registry: Any,
) -> models.NegativeAudit:
    controls: list[models.NegativeControl] = []

    def reject(
        name: str,
        stage: str,
        action: Callable[[], None],
        *,
        rehashed: bool,
        answer_retained: bool = False,
    ) -> None:
        try:
            action()
        except (ValueError, TypeError, KeyError) as exc:
            reason = str(exc).encode("utf-8")
            controls.append(
                models.NegativeControl(
                    name=name,
                    rejection_stage=stage,
                    reason_type=type(exc).__name__,
                    reason_sha256=hashlib.sha256(reason).hexdigest(),
                    candidate_rehashed=rehashed,
                    original_answer_bytes_retained=answer_retained,
                )
            )
            return
        raise ValueError(f"semantic-depth negative control accepted:{name}")

    serial: TaskProgram = cases["serial_margin_target_gap"]["program"]
    branch: TaskProgram = cases["branch_merge_growth_gap"]["program"]
    serial_metrics = cases["serial_margin_target_gap"]["metrics"]

    irrelevant = OperationNode(
        node_id="irrelevant_lookup",
        operator_id="lookup",
        input_refs=(
            ProgramInputRef(
                kind=InputRefKind.EVIDENCE,
                ref_id="evidence:irrelevant",
            ),
        ),
        output_schema="payload",
        verifier_id="lookup.oracle.v1",
    )
    inflated = make_program(
        (*serial.nodes[:-1], irrelevant, serial.nodes[-1]), serial.output_node_id
    )
    reject(
        "serial_irrelevant_lookup_inflation",
        "output_dependency_closure",
        lambda: derive_program_depth_metrics(inflated, registry),
        rehashed=True,
        answer_retained=True,
    )

    serial_result = serial.nodes[-1].model_copy(
        update={
            "input_refs": (
                serial.nodes[-1].input_refs[0],
                ProgramInputRef(
                    kind=InputRefKind.OPERATION,
                    ref_id="margin_ratio",
                    selector="value",
                ),
            ),
            "dependencies": ("target_value", "margin_ratio"),
        }
    )
    serial_bypass = make_program((*serial.nodes[:4], serial_result), "result")
    reject(
        "serial_semantic_scale_bypass",
        "exact_source_program_admission",
        lambda: admit_program_depth_metrics(
            expected_program=serial,
            candidate_program=serial_bypass,
            candidate_metrics=derive_program_depth_metrics(serial_bypass, registry),
            registry=registry,
        ),
        rehashed=True,
        answer_retained=True,
    )

    branch_bypass = make_program(branch.nodes[:-1], "signed_gap")
    reject(
        "branch_merge_absolute_bypass",
        "exact_source_program_admission",
        lambda: admit_program_depth_metrics(
            expected_program=branch,
            candidate_program=branch_bypass,
            candidate_metrics=derive_program_depth_metrics(branch_bypass, registry),
            registry=registry,
        ),
        rehashed=True,
        answer_retained=True,
    )
    reject(
        "branch_to_serial_topology_substitution",
        "exact_source_program_admission",
        lambda: admit_program_depth_metrics(
            expected_program=branch,
            candidate_program=serial,
            candidate_metrics=serial_metrics,
            registry=registry,
        ),
        rehashed=True,
        answer_retained=True,
    )

    branch_bundle: EvidenceBundle = cases["branch_merge_growth_gap"]["bundle"]
    crossed = branch_bundle.evidence[2].model_copy(update={"predicate": "revenue"})
    crossed_bundle = _bundle(
        "branch_cross_metric_attack",
        (
            branch_bundle.evidence[0],
            branch_bundle.evidence[1],
            crossed,
            branch_bundle.evidence[3],
        ),
    )
    crossed_roles: dict[str, tuple[str, ...]] = {
        "revenue_earlier": (crossed_bundle.evidence[0].evidence_id,),
        "revenue_later": (crossed_bundle.evidence[1].evidence_id,),
        "income_earlier": (crossed_bundle.evidence[2].evidence_id,),
        "income_later": (crossed_bundle.evidence[3].evidence_id,),
    }
    reject(
        "branch_cross_metric_evidence_substitution",
        "pattern_source_admission",
        lambda: _compile_realized(
            case_id="branch_merge_growth_gap",
            bundle=crossed_bundle,
            role_bindings=crossed_roles,
            registry=registry,
        ),
        rehashed=True,
    )

    branch_case = cases["branch_merge_growth_gap"]
    trajectory: Trajectory = branch_case["execution"].trajectory
    wrong = dict(trajectory.final_answer)
    result = dict(wrong["result"])
    result["value"] = "999999"
    wrong["result"] = result
    citations = list(wrong["citations"])
    citations[0] = {**citations[0], "evidence_id": "evidence:forged:depth-three"}
    wrong["citations"] = citations
    forged = _rehashed_trajectory(trajectory, wrong)

    def require_forged_acceptance() -> None:
        assessment = CandidateQualityEvaluator(
            semantic_policy=FinanceSemanticPolicy(),
            workflow_verifier=CandidateWorkflowVerifier(
                registry=registry, semantic_policy=FinanceSemanticPolicy()
            ),
        ).evaluate(
            branch_case["package"].task,
            EvidenceCorpus.from_bundle(branch_case["bundle"]),
            ProofGraphBuilder().build(branch_case["bundle"]),
            forged,
        )
        if assessment.decision == ReleaseDecision.REJECTED:
            raise ValueError("fully rehashed forged answer and citation rejected")

    reject(
        "fully_rehashed_wrong_answer_and_citation",
        "verifier_evaluator_admission",
        require_forged_acceptance,
        rehashed=True,
    )

    laundered = depth_three_operation_registry(scale_ratio_program_role="transparent_projection")
    laundered_metrics = derive_program_depth_metrics(serial, laundered)
    reject(
        "operation_role_laundering",
        "authoritative_registry_metric_admission",
        lambda: admit_program_depth_metrics(
            expected_program=serial,
            candidate_program=serial,
            candidate_metrics=laundered_metrics,
            registry=registry,
        ),
        rehashed=True,
        answer_retained=True,
    )

    return models.identified(
        models.NegativeAudit,
        {
            "authorization_id": authorization_id,
            "controls": tuple(controls),
            "candidate_rehashed_count": sum(item.candidate_rehashed for item in controls),
            "original_answer_bytes_retained_count": sum(
                item.original_answer_bytes_retained for item in controls
            ),
        },
        "audit_id",
        "qa_semantic_depth_three_plus_negative_audit:",
    )


def build_qa_semantic_depth_three_plus_preflight(
    *,
    repo_root: str | Path,
    external_audit_path: str | Path,
    source_commit: str,
    source_tree: str,
) -> models.Products:
    root = Path(repo_root).resolve()
    review = Path(external_audit_path).read_bytes()
    if (
        len(review) != models.EXTERNAL_AUDIT_BYTE_COUNT
        or hashlib.sha256(review).hexdigest() != models.EXTERNAL_AUDIT_SHA256
    ):
        raise ValueError("external semantic-depth audit bytes differ")
    directive = models.OPERATOR_DIRECTIVE.encode("utf-8")
    if (
        len(directive) != models.OPERATOR_DIRECTIVE_BYTE_COUNT
        or hashlib.sha256(directive).hexdigest() != models.OPERATOR_DIRECTIVE_SHA256
    ):
        raise ValueError("semantic-depth operator directive bytes differ")
    authorization = models.identified(
        models.DepthExpansionAuthorization,
        {},
        "authorization_id",
        "qa_semantic_depth_three_plus_authorization:",
    )
    predecessor = _freeze_predecessor(root, authorization.authorization_id)
    source = _source_binding(
        root,
        authorization.authorization_id,
        source_commit,
        source_tree,
    )
    registry_binding = _registry_binding(source.binding_id)
    registry = depth_three_operation_registry()
    workflow = CandidateWorkflowVerifier(registry=registry, semantic_policy=FinanceSemanticPolicy())
    evaluator = CandidateQualityEvaluator(
        semantic_policy=FinanceSemanticPolicy(), workflow_verifier=workflow
    )

    cases: dict[str, dict[str, Any]] = {}
    rows = []
    for case_id, (bundle, roles) in _fixture_inputs().items():
        package = _compile_realized(
            case_id=case_id,
            bundle=bundle,
            role_bindings=roles,
            registry=registry,
        )
        corpus = EvidenceCorpus.from_bundle(bundle)
        graph = ProofGraphBuilder().build(bundle)
        execution = PublicPlanCandidateExecutor(registry).generate(package, corpus)
        verification = workflow.verify(package.task, corpus, graph, execution.trajectory)
        assessment = evaluator.evaluate(package.task, corpus, graph, execution.trajectory)
        metrics = derive_program_depth_metrics(execution.reconstructed_program, registry)
        admitted = admit_program_depth_metrics(
            expected_program=package.task.oracle.task_program,
            candidate_program=execution.reconstructed_program,
            candidate_metrics=metrics,
            registry=registry,
        )
        if admitted.semantic_operation_depth < 3:
            raise ValueError("semantic-depth-three case is shallow")
        row = _coverage_row(
            authorization_id=authorization.authorization_id,
            source_binding_id=source.binding_id,
            registry_binding_id=registry_binding.binding_id,
            case_id=case_id,
            bundle=bundle,
            package=package,
            execution=execution,
            verification=verification,
            assessment=assessment,
            metrics=metrics,
        )
        cases[case_id] = {
            "bundle": bundle,
            "package": package,
            "program": execution.reconstructed_program,
            "execution": execution,
            "verification": verification,
            "assessment": assessment,
            "metrics": metrics,
        }
        rows.append(row)

    coverage = models.identified(
        models.CoverageAudit,
        {
            "authorization_id": authorization.authorization_id,
            "source_binding_id": source.binding_id,
            "registry_binding_id": registry_binding.binding_id,
            "rows": tuple(rows),
        },
        "audit_id",
        "qa_semantic_depth_three_plus_coverage_audit:",
    )
    negative = _negative_controls(
        authorization_id=authorization.authorization_id,
        cases=cases,
        registry=registry,
    )
    scope = models.identified(
        models.ScopeAudit,
        {
            "authorization_id": authorization.authorization_id,
            "coverage_audit_id": coverage.audit_id,
            "negative_audit_id": negative.audit_id,
        },
        "audit_id",
        "qa_semantic_depth_three_plus_scope_audit:",
    )
    gates = {
        "G0_exact_external_scope": True,
        "G1_exact_predecessor_independent_audit_freeze": (
            predecessor.formal_bytes_modified is False
        ),
        "G2_exact_git_source_and_operation_registry_authority": (
            len(source.members) == 5
            and source.all_current_bytes_equal_committed_bytes
            and registry_binding.all_extension_roles_semantic
        ),
        "G3_exact_serial_and_branch_merge_source_programs": (
            coverage.case_count == coverage.topology_count == 2
            and coverage.serial_chain_count == coverage.branch_and_merge_count == 1
        ),
        "G4_complete_execution_and_independent_replay_2_of_2": (
            coverage.complete_execution_count == coverage.independent_replay_count == 2
        ),
        "G5_answer_schema_answer_citation_evaluator_2_of_2": (
            coverage.answer_schema_correct_count
            == coverage.answer_correct_count
            == coverage.citation_correct_count
            == coverage.evaluator_accepted_count
            == 2
        ),
        "G6_semantic_depth_three_plus_and_two_topologies": (
            coverage.semantic_depth_three_plus_count == 2
            and coverage.semantic_depth_distribution == {"3": 2}
        ),
        "G7_seven_attacks_reject_and_zero_external_scope": (
            negative.rejected_count == 7
            and negative.accepted_count == 0
            and not any(
                (
                    scope.provider_calls,
                    scope.credential_lookups,
                    scope.gpu_jobs,
                    scope.archive_selections,
                    scope.benchmark_rows,
                    scope.empirical_estimates,
                    scope.online_job_manifests,
                    scope.qa_release_objects,
                    scope.vtdo_rows,
                    scope.training_rows,
                    scope.production_rows,
                )
            )
        ),
    }
    gate = models.identified(
        models.GateEvaluation,
        {"gates": gates},
        "gate_id",
        "qa_semantic_depth_three_plus_gate:",
    )
    decision = models.identified(
        models.Decision,
        {"gate_id": gate.gate_id},
        "decision_id",
        "qa_semantic_depth_three_plus_decision:",
    )
    transition = models.identified(
        models.Transition,
        {"decision_id": decision.decision_id},
        "transition_id",
        "qa_semantic_depth_three_plus_transition:",
    )
    report = models.identified(
        models.Report,
        {
            "authorization_id": authorization.authorization_id,
            "predecessor_freeze_id": predecessor.freeze_id,
            "source_binding_id": source.binding_id,
            "registry_binding_id": registry_binding.binding_id,
            "coverage_audit_id": coverage.audit_id,
            "negative_audit_id": negative.audit_id,
            "scope_audit_id": scope.audit_id,
            "gate_id": gate.gate_id,
            "decision_id": decision.decision_id,
            "transition_id": transition.transition_id,
        },
        "report_id",
        "qa_semantic_depth_three_plus_report:",
    )
    ordered = tuple(cases[case_id] for case_id in models.CASE_IDS)
    return models.Products(
        authorization=authorization,
        external_review_bytes=review,
        operator_directive_bytes=directive,
        predecessor_freeze=predecessor,
        source_binding=source,
        registry_binding=registry_binding,
        coverage_audit=coverage,
        negative_audit=negative,
        scope_audit=scope,
        gate=gate,
        decision=decision,
        transition=transition,
        report=report,
        bundles=tuple(item["bundle"] for item in ordered),
        packages=tuple(item["package"] for item in ordered),
        executions=tuple(item["execution"] for item in ordered),
        verification_reports=tuple(item["verification"] for item in ordered),
        assessments=tuple(item["assessment"] for item in ordered),
        depth_metrics=tuple(item["metrics"] for item in ordered),
    )


def _jsonl(values: Sequence[Any]) -> bytes:
    return b"".join(canonical_json_bytes(item) + b"\n" for item in values)


def write_qa_semantic_depth_three_plus_artifacts(
    products: models.Products, output_dir: str | Path
) -> tuple[str, ...]:
    payloads = {
        "authorization.json": canonical_json_bytes(products.authorization) + b"\n",
        "coverage_audit.json": canonical_json_bytes(products.coverage_audit) + b"\n",
        "coverage_rows.jsonl": _jsonl(products.coverage_audit.rows),
        "decision.json": canonical_json_bytes(products.decision) + b"\n",
        "depth_metrics.jsonl": _jsonl(products.depth_metrics),
        "evidence_bundles.jsonl": _jsonl(products.bundles),
        "external_review.txt": products.external_review_bytes,
        "gate_evaluation.json": canonical_json_bytes(products.gate) + b"\n",
        "negative_control_audit.json": canonical_json_bytes(products.negative_audit) + b"\n",
        "operator_directive.txt": products.operator_directive_bytes,
        "operation_registry_binding.json": canonical_json_bytes(products.registry_binding) + b"\n",
        "predecessor_freeze.json": canonical_json_bytes(products.predecessor_freeze) + b"\n",
        "public_plan_executions.jsonl": _jsonl(products.executions),
        "quality_assessments.jsonl": _jsonl(products.assessments),
        "realized_task_packages.jsonl": _jsonl(products.packages),
        "report.json": canonical_json_bytes(products.report) + b"\n",
        "scope_boundary_audit.json": canonical_json_bytes(products.scope_audit) + b"\n",
        "source_binding.json": canonical_json_bytes(products.source_binding) + b"\n",
        "transition.json": canonical_json_bytes(products.transition) + b"\n",
        "verification_reports.jsonl": _jsonl(products.verification_reports),
    }
    members = tuple(
        {
            "relative_path": relative_path,
            "sha256": hashlib.sha256(payload).hexdigest(),
            "byte_count": len(payload),
        }
        for relative_path, payload in sorted(payloads.items())
    )
    manifest_body = {
        "members": members,
        "file_count": len(members),
        "member_bytes": sum(len(payload) for payload in payloads.values()),
        "artifact_root": strict_canonical_hash(
            members, prefix="qa_semantic_depth_three_plus_artifact_root:"
        ),
        "self_excluding": True,
        "schema_version": "qa_semantic_depth_three_plus_artifact_manifest.v1",
    }
    payloads["artifact_manifest.json"] = (
        canonical_json_bytes(
            {
                "manifest_id": strict_canonical_hash(
                    manifest_body, prefix="qa_semantic_depth_three_plus_artifact_manifest:"
                ),
                **manifest_body,
            }
        )
        + b"\n"
    )
    return write_immutable_artifact_directory(output_dir, payloads)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--external-audit", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--source-tree", required=True)
    arguments = parser.parse_args()
    products = build_qa_semantic_depth_three_plus_preflight(
        repo_root=arguments.repo_root,
        external_audit_path=arguments.external_audit,
        source_commit=arguments.source_commit,
        source_tree=arguments.source_tree,
    )
    write_qa_semantic_depth_three_plus_artifacts(products, arguments.output_dir)


if __name__ == "__main__":
    main()
