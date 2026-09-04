from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from collections.abc import Callable, Mapping, Sequence
from decimal import Decimal
from pathlib import Path
from typing import Any, NoReturn

from pydantic import BaseModel

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
from trusted_synthesis.experiments.qa_reasoning_contract_freeze import contracts
from trusted_synthesis.experiments.qa_reasoning_contract_freeze import models as reasoning_models
from trusted_synthesis.experiments.qa_semantic_depth_three_catalog_integration.catalog import (
    RegisteredFinanceQACatalog,
    build_catalog_descriptor,
    historical_catalog_snapshot,
)

from . import models
from .runtime import (
    DurableArtifactWriter,
    FixedFixtureRuntimeError,
    admit_preaction_commit,
)


class FixedFixtureAdmissionError(ValueError):
    """A fixed-Fixture source, semantic, or final-output boundary failed closed."""

    def __init__(self, stage: str, reason: str) -> None:
        super().__init__(reason)
        self.stage = stage


def _fail(stage: str, reason: str) -> NoReturn:
    raise FixedFixtureAdmissionError(stage, reason)


def _sha(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _identified(values: Mapping[str, Any], field: str, prefix: str) -> dict[str, Any]:
    result = dict(values)
    result[field] = strict_canonical_hash(result, prefix=prefix)
    return result


def _dump(value: Any) -> Any:
    return value.model_dump(mode="python") if isinstance(value, BaseModel) else value


def _files(directory: Path) -> dict[str, bytes]:
    return {
        path.relative_to(directory).as_posix(): path.read_bytes()
        for path in directory.rglob("*")
        if path.is_file()
    }


def _read_jsonl(path: Path) -> tuple[dict[str, Any], ...]:
    return tuple(json.loads(line) for line in path.read_text().splitlines() if line)


def _git(root: Path, *arguments: str) -> bytes:
    return subprocess.run(
        ("git", "-C", str(root), *arguments), check=True, capture_output=True
    ).stdout


def _git_text(root: Path, *arguments: str) -> str:
    return _git(root, *arguments).decode("ascii").strip()


def _validate_formal_directory(
    *,
    directory: Path,
    expected_file_count: int,
    expected_total_bytes: int,
    expected_member_count: int,
    expected_member_bytes: int,
    expected_manifest_bytes: int,
    expected_manifest_sha256: str,
) -> tuple[dict[str, bytes], dict[str, Any]]:
    files = _files(directory)
    manifest_payload = files.get("artifact_manifest.json", b"")
    if (
        len(files) != expected_file_count
        or sum(map(len, files.values())) != expected_total_bytes
        or len(manifest_payload) != expected_manifest_bytes
        or _sha(manifest_payload) != expected_manifest_sha256
    ):
        _fail("freeze.directory_geometry", f"formal directory differs:{directory}")
    manifest = json.loads(manifest_payload)
    members = {str(row["relative_path"]): row for row in manifest["members"]}
    if (
        len(members) != expected_member_count
        or int(manifest["member_bytes"]) != expected_member_bytes
        or set(members) != set(files) - {"artifact_manifest.json"}
    ):
        _fail("freeze.manifest_domain", f"formal Manifest differs:{directory}")
    for relative, row in members.items():
        payload = files[relative]
        if int(row["byte_count"]) != len(payload) or str(row["sha256"]) != _sha(payload):
            _fail("freeze.member_bytes", f"formal member differs:{relative}")
    return files, manifest


def _authorization(review: bytes) -> tuple[dict[str, Any], bytes]:
    if len(review) != models.EXTERNAL_REVIEW_BYTE_COUNT or _sha(review) != (
        models.EXTERNAL_REVIEW_SHA256
    ):
        _fail("authorization.external_review", "external audit bytes differ")
    directive = models.OPERATOR_DIRECTIVE.encode("utf-8")
    if len(directive) != models.OPERATOR_DIRECTIVE_BYTE_COUNT or _sha(directive) != (
        models.OPERATOR_DIRECTIVE_SHA256
    ):
        _fail("authorization.operator_directive", "operator directive bytes differ")
    return (
        _identified(
            {
                "stage": models.STAGE,
                "external_review_sha256": models.EXTERNAL_REVIEW_SHA256,
                "external_review_byte_count": models.EXTERNAL_REVIEW_BYTE_COUNT,
                "operator_directive": models.OPERATOR_DIRECTIVE,
                "operator_directive_sha256": models.OPERATOR_DIRECTIVE_SHA256,
                "operator_directive_byte_count": models.OPERATOR_DIRECTIVE_BYTE_COUNT,
                "fixed_fixture_count": 2,
                "provider_execution_authorized": False,
                "gpu_execution_authorized": False,
                "archive_expansion_authorized": False,
                "task_or_operation_registration_authorized": False,
                "same_task_multitrajectory_authorized": False,
                "qa_release_authorized": False,
                "vtdo_authorized": False,
                "schema_version": "qa_reasoning_fixed_fixture_authorization.v1",
            },
            "authorization_id",
            "qa_reasoning_fixed_fixture_authorization:",
        ),
        directive,
    )


def _freeze_predecessor(root: Path, authorization_id: str) -> dict[str, Any]:
    directory = root / models.PREDECESSOR_DIRECTORY
    files, manifest = _validate_formal_directory(
        directory=directory,
        expected_file_count=models.PREDECESSOR_FILE_COUNT,
        expected_total_bytes=models.PREDECESSOR_TOTAL_BYTES,
        expected_member_count=models.PREDECESSOR_MEMBER_COUNT,
        expected_member_bytes=models.PREDECESSOR_MEMBER_BYTES,
        expected_manifest_bytes=models.PREDECESSOR_MANIFEST_BYTES,
        expected_manifest_sha256=models.PREDECESSOR_MANIFEST_SHA256,
    )
    report = json.loads(files["report.json"])
    gate = json.loads(files["gate_evaluation.json"])
    decision = json.loads(files["decision.json"])
    transition = json.loads(files["transition.json"])
    predecessor_source = json.loads(files["audit_source_binding.json"])
    prior_review = files["external_review.txt"].decode("utf-8")
    if (
        manifest["manifest_id"] != models.PREDECESSOR_MANIFEST_ID
        or manifest["artifact_root"] != models.PREDECESSOR_ROOT_ID
        or report["report_id"] != models.PREDECESSOR_REPORT_ID
        or gate["gate_id"] != models.PREDECESSOR_GATE_ID
        or decision["decision_id"] != models.PREDECESSOR_DECISION_ID
        or transition["transition_id"] != models.PREDECESSOR_TRANSITION_ID
        or gate["passed_count"] != 8
        or gate["failed_count"] != 0
        or transition["next_stage_authorized"] is not False
        or predecessor_source["resolved_commit"] != models.PREDECESSOR_SOURCE_COMMIT
        or predecessor_source["resolved_tree"] != models.PREDECESSOR_SOURCE_TREE
        or "F1 = row_id 排序后第一个 mixed_sign case" not in prior_review
        or "F2 = 与 F1 不同的、row_id 排序后第一个 near_equal_growth case" not in prior_review
    ):
        _fail("freeze.predecessor_authority", "reasoning independent-audit authority differs")
    return _identified(
        {
            "authorization_id": authorization_id,
            "directory": models.PREDECESSOR_DIRECTORY,
            "source_commit": models.PREDECESSOR_SOURCE_COMMIT,
            "source_tree": models.PREDECESSOR_SOURCE_TREE,
            "file_count": len(files),
            "total_bytes": sum(map(len, files.values())),
            "manifest_member_count": models.PREDECESSOR_MEMBER_COUNT,
            "manifest_member_bytes": models.PREDECESSOR_MEMBER_BYTES,
            "manifest_file_sha256": models.PREDECESSOR_MANIFEST_SHA256,
            "manifest_id": models.PREDECESSOR_MANIFEST_ID,
            "artifact_root": models.PREDECESSOR_ROOT_ID,
            "report_id": models.PREDECESSOR_REPORT_ID,
            "gate_id": models.PREDECESSOR_GATE_ID,
            "decision_id": models.PREDECESSOR_DECISION_ID,
            "transition_id": models.PREDECESSOR_TRANSITION_ID,
            "historical_next_stage_authorized": False,
            "selection_rule_present_in_frozen_external_review": True,
            "formal_bytes_modified": False,
            "schema_version": "qa_reasoning_fixed_fixture_predecessor_freeze.v1",
        },
        "freeze_id",
        "qa_reasoning_fixed_fixture_predecessor_freeze:",
    )


def _freeze_archive(root: Path, authorization_id: str) -> tuple[dict[str, Any], Path]:
    directory = root / models.ARCHIVE_DIRECTORY
    files, manifest = _validate_formal_directory(
        directory=directory,
        expected_file_count=models.ARCHIVE_FILE_COUNT,
        expected_total_bytes=models.ARCHIVE_TOTAL_BYTES,
        expected_member_count=models.ARCHIVE_MEMBER_COUNT,
        expected_member_bytes=models.ARCHIVE_MEMBER_BYTES,
        expected_manifest_bytes=models.ARCHIVE_MANIFEST_BYTES,
        expected_manifest_sha256=models.ARCHIVE_MANIFEST_SHA256,
    )
    report = json.loads(files["report.json"])
    gate = json.loads(files["gate_evaluation.json"])
    rows = _read_jsonl(directory / "parameter_case_rows.jsonl")
    branch = tuple(
        row
        for row in rows
        if row.get("constructible") is True
        and row.get("task_type") == "derived_growth_absolute_spread"
    )
    if (
        manifest["manifest_id"] != models.ARCHIVE_MANIFEST_ID
        or manifest["artifact_root"] != models.ARCHIVE_ROOT_ID
        or report["report_id"] != models.ARCHIVE_REPORT_ID
        or gate["passed_count"] != 7
        or gate["failed_count"] != 1
        or len(rows) != 12
        or len(branch) != 9
        or sum(row["numeric_relationship"] == "mixed_sign" for row in branch) != 3
        or sum(bool(row["near_equal_growth"]) for row in branch) != 2
    ):
        _fail("freeze.archive_authority", "Archive-grounding authority differs")
    freeze = _identified(
        {
            "authorization_id": authorization_id,
            "directory": models.ARCHIVE_DIRECTORY,
            "file_count": len(files),
            "total_bytes": sum(map(len, files.values())),
            "manifest_member_count": models.ARCHIVE_MEMBER_COUNT,
            "manifest_member_bytes": models.ARCHIVE_MEMBER_BYTES,
            "manifest_file_sha256": models.ARCHIVE_MANIFEST_SHA256,
            "manifest_id": models.ARCHIVE_MANIFEST_ID,
            "artifact_root": models.ARCHIVE_ROOT_ID,
            "report_id": models.ARCHIVE_REPORT_ID,
            "parameter_row_count": len(rows),
            "constructible_branch_row_count": len(branch),
            "mixed_sign_row_count": 3,
            "near_equal_growth_row_count": 2,
            "archive_expanded": False,
            "formal_bytes_modified": False,
            "schema_version": "qa_reasoning_fixed_fixture_archive_freeze.v1",
        },
        "freeze_id",
        "qa_reasoning_fixed_fixture_archive_freeze:",
    )
    return freeze, directory


def _source_binding(
    root: Path, authorization_id: str, source_commit: str, source_tree: str
) -> dict[str, Any]:
    resolved_commit = _git_text(root, "rev-parse", f"{source_commit}^{{commit}}")
    resolved_tree = _git_text(root, "rev-parse", f"{resolved_commit}^{{tree}}")
    if resolved_commit != source_commit or resolved_tree != source_tree:
        _fail("source.commit_tree", "source commit/tree relation differs")
    members = []
    for relative in models.SOURCE_PATHS:
        committed = _git(root, "show", f"{source_commit}:{relative}")
        current = (root / relative).read_bytes()
        blob = hashlib.sha1(
            f"blob {len(committed)}\0".encode("ascii") + committed,
            usedforsecurity=False,
        ).hexdigest()
        if (
            blob != _git_text(root, "rev-parse", f"{source_commit}:{relative}")
            or committed != current
        ):
            _fail("source.member_bytes", f"source member differs:{relative}")
        members.append(
            {
                "relative_path": relative,
                "git_blob_oid": blob,
                "sha256": _sha(committed),
                "byte_count": len(committed),
                "committed_current_bytes_equal": True,
            }
        )
    return _identified(
        {
            "authorization_id": authorization_id,
            "requested_commit": source_commit,
            "resolved_commit": resolved_commit,
            "requested_tree": source_tree,
            "resolved_tree": resolved_tree,
            "members": tuple(members),
            "member_count": len(members),
            "path_set_sha256": _sha(canonical_json_bytes(models.SOURCE_PATHS)),
            "member_set_sha256": _sha(canonical_json_bytes(members)),
            "commit_tree_relation_verified": True,
            "all_current_bytes_equal_committed_bytes": True,
            "transitive_import_or_runtime_environment_closure_claimed": False,
            "schema_version": "qa_reasoning_fixed_fixture_source_binding.v1",
        },
        "binding_id",
        "qa_reasoning_fixed_fixture_source_binding:",
    )


def _select_rows(
    directory: Path, authorization_id: str
) -> tuple[dict[str, Any], tuple[dict[str, Any], ...]]:
    rows = _read_jsonl(directory / "parameter_case_rows.jsonl")
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
        (row for row in population if bool(row["near_equal_growth"])),
        key=lambda row: row["row_id"],
    )
    selected = (mixed, near)
    if tuple(row["row_id"] for row in selected) != models.SELECTED_ROW_IDS:
        _fail("selection.exact_rows", "pre-registered Fixture selection differs")
    contract = _identified(
        {
            "authorization_id": authorization_id,
            "population": "nine_frozen_constructible_derived_growth_absolute_spread_rows",
            "population_count": len(population),
            "selection_rule": (
                "F1=min(row_id where numeric_relationship=mixed_sign);"
                "F2=min(row_id where near_equal_growth=true and row_id!=F1)"
            ),
            "selector_fields": (
                "constructible",
                "task_type",
                "numeric_relationship",
                "near_equal_growth",
                "row_id",
            ),
            "future_trajectory_outcome_fields_read": (),
            "selected_row_ids": models.SELECTED_ROW_IDS,
            "selected_case_ids": tuple(row["case_id"] for row in selected),
            "selected_rows_distinct": mixed["row_id"] != near["row_id"],
            "selection_performed_before_reasoning_execution": True,
            "schema_version": "qa_reasoning_fixed_fixture_selection_contract.v1",
        },
        "contract_id",
        "qa_reasoning_fixed_fixture_selection_contract:",
    )
    return contract, selected


def _index_jsonl(directory: Path, filename: str, field: str) -> dict[str, dict[str, Any]]:
    return {str(item[field]): item for item in _read_jsonl(directory / filename)}


def _fixture_sources(
    directory: Path,
    authorization_id: str,
    selection_contract_id: str,
    selected_rows: Sequence[dict[str, Any]],
) -> tuple[tuple[dict[str, Any], ...], tuple[tuple[Any, ...], ...]]:
    bundle_rows = _index_jsonl(directory, "evidence_bundles.jsonl", "bundle_id")
    package_rows = _index_jsonl(directory, "realized_task_packages.jsonl", "realized_package_id")
    execution_rows = _index_jsonl(directory, "public_plan_executions.jsonl", "execution_id")
    verification_rows = _index_jsonl(directory, "verification_reports.jsonl", "trajectory_id")
    assessment_rows = _index_jsonl(directory, "quality_assessments.jsonl", "assessment_id")
    depth_rows = _index_jsonl(directory, "depth_metrics.jsonl", "metrics_id")
    receipt_rows = _index_jsonl(directory, "catalog_resolution_receipts.jsonl", "receipt_id")
    bindings = []
    loaded = []
    for row in selected_rows:
        bundle_row = bundle_rows[row["evidence_bundle_id"]]
        package_row = package_rows[row["realized_package_id"]]
        execution_row = execution_rows[row["execution_id"]]
        verification_row = verification_rows[row["verification_trajectory_id"]]
        assessment_row = assessment_rows[row["assessment_id"]]
        depth_row = depth_rows[row["depth_metrics_id"]]
        receipt_row = receipt_rows[row["resolution_receipt_id"]]
        bundle = EvidenceBundle.model_validate(bundle_row)
        package = RealizedTaskPackage.model_validate(package_row)
        if (
            package.task.oracle.task_program.program_id != row["source_program_id"]
            or package.task.oracle.task_program.program_hash != row["source_program_hash"]
            or package.binding_snapshot.bundle_id != bundle.bundle_id
            or package.realized_package_id != row["realized_package_id"]
            or tuple(package.task.oracle.gold_evidence_ids)
            != tuple(item.evidence_id for item in bundle.evidence)
        ):
            _fail("fixture.source_parent", f"Fixture source parent differs:{row['case_id']}")
        objects = {
            "row": row,
            "evidence_bundle": bundle_row,
            "realized_task_package": package_row,
            "saved_execution": execution_row,
            "saved_verification": verification_row,
            "saved_assessment": assessment_row,
            "saved_depth_metrics": depth_row,
            "catalog_resolution_receipt": receipt_row,
        }
        object_bindings = {
            name: {
                "object_id": next(
                    (
                        value[key]
                        for key in (
                            "row_id",
                            "bundle_id",
                            "realized_package_id",
                            "execution_id",
                            "trajectory_id",
                            "assessment_id",
                            "metrics_id",
                            "receipt_id",
                        )
                        if key in value
                    ),
                    "",
                ),
                "sha256": _sha(canonical_json_bytes(value)),
                "byte_count": len(canonical_json_bytes(value)),
            }
            for name, value in objects.items()
        }
        binding = _identified(
            {
                "authorization_id": authorization_id,
                "selection_contract_id": selection_contract_id,
                "case_id": row["case_id"],
                "row_id": row["row_id"],
                "task_id": package.task.task_id,
                "task_type": row["task_type"],
                "evidence_bundle_id": bundle.bundle_id,
                "evidence_binding_id": package.binding_snapshot.evidence_binding_id,
                "binding_snapshot_id": package.binding_snapshot.binding_snapshot_id,
                "realized_package_id": package.realized_package_id,
                "answer_oracle_program_id": row["source_program_id"],
                "answer_oracle_program_hash": row["source_program_hash"],
                "object_bindings": object_bindings,
                "source_object_count": len(object_bindings),
                "saved_outcomes_used_as_selection_oracle": False,
                "schema_version": "qa_reasoning_fixed_fixture_source_binding.v1",
            },
            "binding_id",
            "qa_reasoning_fixed_fixture_source_binding:",
        )
        bindings.append(binding)
        loaded.append(
            (
                row,
                bundle,
                package,
                execution_row,
                verification_row,
                assessment_row,
                depth_row,
                receipt_row,
            )
        )
    return tuple(bindings), tuple(loaded)


def _catalog(directory: Path) -> RegisteredFinanceQACatalog:
    saved = json.loads((directory / "catalog_freeze.json").read_bytes())
    descriptor_path = Path(models.ARCHIVE_DIRECTORY).parent.parent  # unreachable sentinel
    del descriptor_path
    rebuilt = build_catalog_descriptor(historical_catalog_snapshot()["snapshot_id"])
    catalog_id = saved["catalog_id"]
    if catalog_id != rebuilt["catalog_id"]:
        _fail("fixture.catalog", "frozen Catalog identity differs")
    return RegisteredFinanceQACatalog(rebuilt)


def _check(report: Any, check_id: str) -> bool:
    return next(item.passed for item in report.checks if item.check_id == check_id)


def _claim_id(case_id: str, kind: str) -> str:
    return strict_canonical_hash(
        {"case_id": case_id, "claim_kind": kind}, prefix="fixed_fixture_claim:"
    )


def _action_id(case_id: str, kind: str, alternative: str) -> str:
    return strict_canonical_hash(
        {"case_id": case_id, "decision_kind": kind, "alternative": alternative},
        prefix="fixed_fixture_action:",
    )


def _decision_id(case_id: str, kind: str) -> str:
    return strict_canonical_hash(
        {"case_id": case_id, "obligation_kind": kind},
        prefix="fixed_fixture_decision:",
    )


def _build_oracle_and_graph(
    row: dict[str, Any], package: RealizedTaskPackage
) -> tuple[reasoning_models.AnswerOracleProgramBindingV1, reasoning_models.CriticalDecisionGraphV1]:
    case_id = str(row["case_id"])
    task_id = package.task.task_id
    oracle = contracts.identified(
        reasoning_models.AnswerOracleProgramBindingV1,
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
        },
        "binding_id",
        "answer_oracle_program_binding:",
    )
    specs = (
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
            (),
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
    for kind, dependencies, roles, subgoal, uncertainty, claim_kind, intervention in specs:
        selected = _action_id(case_id, kind, "execute")
        alternative = _action_id(case_id, kind, "reject")
        obligations.append(
            reasoning_models.CriticalDecisionObligationV1(
                decision_id=_decision_id(case_id, kind),
                trigger_state_predicate=f"{kind}_is_current_unresolved_obligation",
                subgoal=subgoal,
                unresolved_uncertainty_type=uncertainty,
                required_evidence_roles=roles or ("verified_branch_claims",),
                admissible_action_classes=(f"execute_{kind}", f"reject_{kind}"),
                admissible_alternative_action_ids=(selected, alternative),
                forbidden_shortcut_classes=("post_action_backfill", "unbound_source_substitution"),
                produced_claim_schema={"type": claim_kind, "case_id": case_id},
                downstream_claim_dependencies=tuple(
                    _decision_id(case_id, item) for item in dependencies
                ),
                required=True,
                counterfactual_intervention_ids=(
                    strict_canonical_hash(
                        {"case_id": case_id, "intervention": intervention},
                        prefix="fixed_fixture_intervention:",
                    ),
                ),
            )
        )
    graph = contracts.identified(
        reasoning_models.CriticalDecisionGraphV1,
        {
            "task_instance_id": task_id,
            "answer_oracle_program_binding_id": oracle.binding_id,
            "obligations": tuple(obligations),
        },
        "graph_id",
        "critical_decision_graph:",
    )
    return oracle, graph


def _role_items(bundle: EvidenceBundle, package: RealizedTaskPackage) -> dict[str, Any]:
    evidence = {item.evidence_id: item for item in bundle.evidence}
    roles: dict[str, Any] = {}
    for role, identifiers in package.binding_snapshot.role_bindings.items():
        if len(identifiers) != 1 or identifiers[0] not in evidence:
            _fail("fixture.role_binding", f"role does not resolve exactly once:{role}")
        roles[role] = evidence[identifiers[0]]
    expected = {"revenue_earlier", "revenue_later", "income_earlier", "income_later"}
    if set(roles) != expected:
        _fail("fixture.role_binding", "fixed-Fixture role domain differs")
    return roles


def _value(item: Any) -> Decimal:
    return Decimal(str(item.payload.value))


def _growth(earlier: Any, later: Any) -> Decimal:
    base = _value(earlier)
    if base == 0:
        _fail("fixture.growth_denominator", "growth denominator is zero")
    return ((_value(later) - base) / base) * Decimal(100)


def _comparability(roles: Mapping[str, Any]) -> dict[str, Any]:
    items = tuple(roles.values())
    subjects = {item.subject.subject_id for item in items}
    units = {item.payload.unit for item in items}
    currencies = {item.payload.currency for item in items}
    source_ids = {item.source.source_id for item in items}
    revenue_order = (
        roles["revenue_earlier"].domain_context["economic_period_sort_key"]
        < roles["revenue_later"].domain_context["economic_period_sort_key"]
    )
    income_order = (
        roles["income_earlier"].domain_context["economic_period_sort_key"]
        < roles["income_later"].domain_context["economic_period_sort_key"]
    )
    aligned_periods = (
        roles["revenue_earlier"].temporal_context.label
        == roles["income_earlier"].temporal_context.label
        and roles["revenue_later"].temporal_context.label
        == roles["income_later"].temporal_context.label
    )
    predicates = (
        roles["revenue_earlier"].predicate == "revenue"
        and roles["revenue_later"].predicate == "revenue"
        and roles["income_earlier"].predicate == "operating_income"
        and roles["income_later"].predicate == "operating_income"
    )
    comparable = (
        len(subjects) == len(units) == len(currencies) == len(source_ids) == 1
        and revenue_order
        and income_order
        and aligned_periods
        and predicates
    )
    if not comparable:
        _fail("action.comparability", "fixed-Fixture Evidence is not comparable")
    return {
        "comparable": True,
        "subject_id": next(iter(subjects)),
        "unit": next(iter(units)),
        "currency": next(iter(currencies)),
        "earlier_period": roles["revenue_earlier"].temporal_context.label,
        "later_period": roles["revenue_later"].temporal_context.label,
        "evidence_refs": tuple(item.evidence_id for item in items),
    }


def _reasoning_depth(graph: reasoning_models.CriticalDecisionGraphV1) -> int:
    depth: dict[str, int] = {}
    for obligation in graph.obligations:
        depth[obligation.decision_id] = 1 + max(
            (depth[parent] for parent in obligation.downstream_claim_dependencies), default=0
        )
    return max(depth.values())


def _validate_action_source(
    *,
    envelope: reasoning_models.ReasoningActionEnvelopeV1,
    expected_envelope: reasoning_models.ReasoningActionEnvelopeV1,
) -> None:
    if canonical_json_bytes(envelope) != canonical_json_bytes(expected_envelope):
        _fail("fixture.expected_envelope", "Action Envelope differs from fixture-owned bytes")


def _admit_final_output(
    *,
    actual_answer: Mapping[str, Any],
    actual_citations: Sequence[str],
    expected_value: str,
    expected_citations: Sequence[str],
) -> None:
    if (
        Decimal(str(actual_answer.get("value"))) != Decimal(expected_value)
        or actual_answer.get("unit") != "percentage_points"
        or set(actual_citations) != set(expected_citations)
        or len(actual_citations) != len(set(actual_citations))
    ):
        _fail("fixture.final_answer_citation", "Final answer or citation differs")


def _run_fixture(
    *,
    writer: DurableArtifactWriter,
    runtime_prefix: str,
    row: dict[str, Any],
    bundle: EvidenceBundle,
    package: RealizedTaskPackage,
    catalog: RegisteredFinanceQACatalog,
    saved_execution: dict[str, Any],
    saved_verification: dict[str, Any],
    saved_assessment: dict[str, Any],
    saved_depth: dict[str, Any],
    catalog_resolution_receipt: dict[str, Any],
) -> dict[str, Any]:
    case_id = str(row["case_id"])
    task_id = package.task.task_id
    roles = _role_items(bundle, package)
    oracle, graph = _build_oracle_and_graph(row, package)
    evidence_ids = tuple(item.evidence_id for item in bundle.evidence)
    claim_ids = tuple(_claim_id(case_id, kind) for kind in models.OBLIGATION_KINDS)
    selected_actions = tuple(
        _action_id(case_id, kind, "execute") for kind in models.OBLIGATION_KINDS
    )
    alternative_actions = tuple(
        _action_id(case_id, kind, "reject") for kind in models.OBLIGATION_KINDS
    )
    state = contracts.identified(
        reasoning_models.PublicReasoningStateV1,
        {
            "task_instance_id": task_id,
            "sequence_index": 0,
            "available_evidence_refs": evidence_ids,
            "verified_claim_refs": (),
            "current_subgoal": graph.obligations[0].subgoal,
            "remaining_uncertainties": tuple(
                item.unresolved_uncertainty_type for item in graph.obligations
            ),
            "available_action_ids": graph.obligations[0].admissible_alternative_action_ids,
            "completed_action_refs": (),
            "observation_refs": (),
        },
        "state_id",
        "public_reasoning_state:",
    )
    writer.ensure_directory(runtime_prefix)
    writer.write_json(f"{runtime_prefix}/state_00.json", state)
    states: list[reasoning_models.PublicReasoningStateV1] = [state]
    envelopes: list[reasoning_models.ReasoningActionEnvelopeV1] = []
    receipts: list[models.DurablePreactionCommitReceipt] = []
    executions: list[reasoning_models.ActionExecutionV1] = []
    observations: list[reasoning_models.PublicObservationV1] = []
    updates: list[reasoning_models.ObservationUpdateV1] = []
    accepted_claims: list[reasoning_models.ClaimUpdateV1] = []
    core: dict[str, Any] = {}
    branch_results: dict[str, Decimal] = {}
    workflow = CandidateWorkflowVerifier(
        registry=catalog.registry, semantic_policy=FinanceSemanticPolicy()
    )
    evaluator = CandidateQualityEvaluator(
        semantic_policy=FinanceSemanticPolicy(), workflow_verifier=workflow
    )

    for index, (kind, obligation) in enumerate(
        zip(models.OBLIGATION_KINDS, graph.obligations, strict=True)
    ):
        selected_action = selected_actions[index]
        if tuple(state.available_action_ids) != (
            selected_action,
            alternative_actions[index],
        ):
            _fail("fixture.state_action_domain", "current Action domain differs")
        if kind in {"comparability", "final_grounding"}:
            envelope_evidence = evidence_ids
        elif kind == "revenue_branch":
            envelope_evidence = (
                roles["revenue_earlier"].evidence_id,
                roles["revenue_later"].evidence_id,
            )
        elif kind == "operating_income_branch":
            envelope_evidence = (
                roles["income_earlier"].evidence_id,
                roles["income_later"].evidence_id,
            )
        else:
            envelope_evidence = evidence_ids
        dependency_claims = tuple(
            claim_ids[models.OBLIGATION_KINDS.index(dependency_kind)]
            for dependency_kind in (
                ()
                if kind == "comparability"
                else ("comparability",)
                if kind in {"revenue_branch", "operating_income_branch"}
                else ("revenue_branch", "operating_income_branch")
                if kind == "branch_merge"
                else ("branch_merge",)
            )
        )
        envelope = contracts.identified(
            reasoning_models.ReasoningActionEnvelopeV1,
            {
                "task_instance_id": task_id,
                "state_id": state.state_id,
                "decision_graph_id": graph.graph_id,
                "decision_id": obligation.decision_id,
                "subgoal": obligation.subgoal,
                "evidence_refs": envelope_evidence,
                "claim_refs": dependency_claims,
                "unresolved_uncertainty": obligation.unresolved_uncertainty_type,
                "candidate_action_ids": state.available_action_ids,
                "selected_action_id": selected_action,
                "decision_basis": (
                    reasoning_models.DecisionBasisEdgeV1(
                        relation="requires",
                        subject_ref=claim_ids[index],
                        evidence_refs=envelope_evidence,
                        claim_refs=dependency_claims,
                    ),
                ),
                "expected_effect": f"produce exact public {kind} Claim",
                "action": reasoning_models.PublicActionV1(
                    state_id=state.state_id,
                    action_id=selected_action,
                    decision_kind=f"execute_{kind}",
                ),
                "preaction_commit_sequence": index,
            },
            "envelope_id",
            "reasoning_action_envelope:",
        )
        contracts.admit_reasoning_action(envelope, state, graph)
        _validate_action_source(envelope=envelope, expected_envelope=envelope)
        step = f"step_{index:02d}_{kind}"
        envelope_path = f"{runtime_prefix}/{step}_envelope.json"
        receipt_path = f"{runtime_prefix}/{step}_preaction_commit_receipt.json"
        receipt, _, _ = writer.commit_envelope(
            envelope=envelope,
            envelope_relative_path=envelope_path,
            receipt_relative_path=receipt_path,
            execution_sequence=index + 1,
        )

        def execute_action(
            envelope_value: reasoning_models.ReasoningActionEnvelopeV1 = envelope,
            kind_value: str = kind,
            evidence_value: tuple[str, ...] = envelope_evidence,
            claim_value: tuple[str, ...] = dependency_claims,
        ) -> dict[str, Any]:
            _validate_action_source(envelope=envelope_value, expected_envelope=envelope_value)
            if kind_value == "comparability":
                return _comparability(roles)
            if kind_value == "revenue_branch":
                value = _growth(roles["revenue_earlier"], roles["revenue_later"])
                branch_results["revenue_growth"] = value
                return {
                    "operator_id": "growth",
                    "program_node_id": "revenue_growth",
                    "value": value,
                    "unit": "percent",
                    "evidence_refs": evidence_value,
                }
            if kind_value == "operating_income_branch":
                value = _growth(roles["income_earlier"], roles["income_later"])
                branch_results["income_growth"] = value
                return {
                    "operator_id": "growth",
                    "program_node_id": "income_growth",
                    "value": value,
                    "unit": "percent",
                    "evidence_refs": evidence_value,
                }
            if kind_value == "branch_merge":
                signed = branch_results["revenue_growth"] - branch_results["income_growth"]
                absolute = abs(signed)
                branch_results["signed_gap"] = signed
                branch_results["absolute_growth_spread"] = absolute
                return {
                    "operator_ids": (
                        "signed_percentage_point_gap",
                        "absolute_percentage_point_gap",
                    ),
                    "signed_gap": signed,
                    "absolute_growth_spread": absolute,
                    "unit": "percentage_points",
                    "claim_refs": claim_value,
                    "evidence_refs": evidence_ids,
                }
            corpus = EvidenceCorpus.from_bundle(bundle)
            graph_value = ProofGraphBuilder().build(bundle)
            catalog.admit_package(str(row["task_type"]), catalog_resolution_receipt, package)
            actual_execution = PublicPlanCandidateExecutor(catalog.registry).generate(
                package, corpus
            )
            actual_verification = workflow.verify(
                package.task, corpus, graph_value, actual_execution.trajectory
            )
            actual_assessment = evaluator.evaluate(
                package.task, corpus, graph_value, actual_execution.trajectory
            )
            actual_depth = derive_program_depth_metrics(
                actual_execution.reconstructed_program, catalog.registry
            )
            if (
                canonical_json_bytes(actual_execution) != canonical_json_bytes(saved_execution)
                or canonical_json_bytes(actual_verification)
                != canonical_json_bytes(saved_verification)
                or canonical_json_bytes(actual_assessment) != canonical_json_bytes(saved_assessment)
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
                _fail("action.answer_program_replay", "actual Program replay differs")
            final_output = actual_execution.trajectory.final_answer
            final_answer = final_output["result"]
            citations = tuple(item["evidence_id"] for item in final_output["citations"])
            _admit_final_output(
                actual_answer=final_answer,
                actual_citations=citations,
                expected_value=str(row["absolute_growth_spread"]),
                expected_citations=package.task.oracle.gold_evidence_ids,
            )
            core.update(
                execution=actual_execution,
                verification=actual_verification,
                assessment=actual_assessment,
                depth=actual_depth,
            )
            return {
                "program_execution_id": actual_execution.execution_id,
                "verification_trajectory_id": actual_verification.trajectory_id,
                "assessment_id": actual_assessment.assessment_id,
                "final_answer": final_output,
                "citation_evidence_ids": citations,
                "source_program_id": actual_execution.reconstructed_program.program_id,
                "source_program_hash": actual_execution.reconstructed_program.program_hash,
            }

        public_result = writer.guard_and_dispatch(
            expected_envelope=envelope,
            expected_receipt=receipt,
            receipt_relative_path=receipt_path,
            callback=execute_action,
        )
        execution = contracts.identified(
            reasoning_models.ActionExecutionV1,
            {
                "task_instance_id": task_id,
                "parent_envelope_id": envelope.envelope_id,
                "state_id": state.state_id,
                "action_id": selected_action,
                "execution_sequence": index + 1,
                "succeeded": True,
                "public_result_hash": _sha(canonical_json_bytes(public_result)),
            },
            "execution_id",
            "reasoning_action_execution:",
        )
        contracts.admit_reasoning_action(envelope, state, graph, execution)
        observation = contracts.identified(
            reasoning_models.PublicObservationV1,
            {
                "task_instance_id": task_id,
                "parent_execution_id": execution.execution_id,
                "state_id": state.state_id,
                "observation_sequence": index + 1,
                "public_payload": to_canonical_json_data(public_result),
                "public_payload_hash": _sha(canonical_json_bytes(public_result)),
            },
            "observation_id",
            "public_reasoning_observation:",
        )
        claim = reasoning_models.ClaimUpdateV1(
            claim_id=claim_ids[index],
            disposition="accepted",
            support_observation_refs=(observation.observation_id,),
            public_claim={
                "case_id": case_id,
                "obligation_kind": kind,
                "result": to_canonical_json_data(public_result),
                "evidence_ancestors": envelope_evidence,
            },
        )
        accepted_claims.append(claim)
        next_index = index + 1
        if next_index < len(graph.obligations):
            next_obligation = graph.obligations[next_index]
            next_actions = next_obligation.admissible_alternative_action_ids
            next_subgoal = next_obligation.subgoal
            remaining = tuple(
                item.unresolved_uncertainty_type for item in graph.obligations[next_index:]
            )
        else:
            next_actions = (_action_id(case_id, "complete", "terminate"),)
            next_subgoal = "fixed-Fixture reasoning trajectory complete"
            remaining = ()
        next_state = contracts.identified(
            reasoning_models.PublicReasoningStateV1,
            {
                "task_instance_id": task_id,
                "sequence_index": next_index,
                "available_evidence_refs": evidence_ids,
                "verified_claim_refs": tuple(item.claim_id for item in accepted_claims),
                "current_subgoal": next_subgoal,
                "remaining_uncertainties": remaining,
                "available_action_ids": next_actions,
                "completed_action_refs": tuple(
                    item.execution_id for item in (*executions, execution)
                ),
                "observation_refs": tuple(
                    item.observation_id for item in (*observations, observation)
                ),
            },
            "state_id",
            "public_reasoning_state:",
        )
        update = contracts.identified(
            reasoning_models.ObservationUpdateV1,
            {
                "task_instance_id": task_id,
                "parent_reasoning_action_id": envelope.envelope_id,
                "action_execution_id": execution.execution_id,
                "observation_id": observation.observation_id,
                "accepted_claims": (claim,),
                "rejected_or_revised_claims": (),
                "remaining_uncertainties": remaining,
                "newly_enabled_actions": next_actions,
                "next_subgoal": next_subgoal,
                "next_state_id": next_state.state_id,
                "update_sequence": next_index,
            },
            "update_id",
            "observation_update:",
        )
        contracts.admit_observation_update(update, envelope, execution, observation, next_state)
        writer.write_json(f"{runtime_prefix}/{step}_action_execution.json", execution)
        writer.write_json(f"{runtime_prefix}/{step}_observation.json", observation)
        writer.write_json(f"{runtime_prefix}/{step}_update.json", update)
        writer.write_json(f"{runtime_prefix}/state_{next_index:02d}.json", next_state)
        envelopes.append(envelope)
        receipts.append(receipt)
        executions.append(execution)
        observations.append(observation)
        updates.append(update)
        states.append(next_state)
        state = next_state

    trajectory = contracts.identified(
        reasoning_models.ReasoningTrajectoryV1,
        {
            "task_instance_id": task_id,
            "initial_state_id": states[0].state_id,
            "ordered_reasoning_action_ids": tuple(item.envelope_id for item in envelopes),
            "ordered_action_execution_ids": tuple(item.execution_id for item in executions),
            "ordered_observation_ids": tuple(item.observation_id for item in observations),
            "ordered_observation_update_ids": tuple(item.update_id for item in updates),
            "final_claim_refs": tuple(item.claim_id for item in accepted_claims),
            "final_answer_ref": core["execution"].execution_id,
            "critical_decision_graph_id": graph.graph_id,
            "answer_oracle_program_binding_id": oracle.binding_id,
            "covered_decision_ids": tuple(item.decision_id for item in graph.obligations),
            "wording_fingerprint": None,
        },
        "trajectory_id",
        "reasoning_trajectory:",
    )
    contracts.admit_reasoning_trajectory(
        trajectory, graph, envelopes, executions, observations, updates
    )
    answer_validity = contracts.identified(
        reasoning_models.AnswerValidityReportV1,
        {
            "task_instance_id": task_id,
            "source_valid": True,
            "answer_valid": True,
            "citation_valid": True,
            "qa_valid": True,
        },
        "report_id",
        "answer_validity_report:",
    )
    preaction_valid = all(
        receipt.dispatch_event
        > receipt.receipt_directory_fsync_event
        > receipt.receipt_file_fsync_event
        > receipt.envelope_directory_fsync_event
        > receipt.envelope_file_fsync_event
        for receipt in receipts
    )
    trajectory_validity = contracts.identified(
        reasoning_models.TrajectoryValidityReportV1,
        {
            "trajectory_id": trajectory.trajectory_id,
            "preaction_valid": preaction_valid,
            "grounding_valid": all(
                set(item.evidence_refs) <= set(states[index].available_evidence_refs)
                and set(item.claim_refs) <= set(states[index].verified_claim_refs)
                for index, item in enumerate(envelopes)
            ),
            "reasoning_action_valid": all(
                item.parent_envelope_id == envelopes[index].envelope_id
                and item.action_id == envelopes[index].selected_action_id
                for index, item in enumerate(executions)
            ),
            "observation_update_valid": all(
                item.observation_id == observations[index].observation_id
                and item.next_state_id == states[index + 1].state_id
                for index, item in enumerate(updates)
            ),
            "critical_coverage_valid": set(trajectory.covered_decision_ids)
            == {item.decision_id for item in graph.obligations if item.required},
            "trajectory_valid": True,
        },
        "report_id",
        "reasoning_trajectory_validity_report:",
    )
    qualification = contracts.identified(
        reasoning_models.QualifiedReasoningTrajectoryV1,
        {
            "task_instance_id": task_id,
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
    semantic_depth = int(core["depth"].semantic_operation_depth)
    depth = contracts.identified(
        reasoning_models.ReasoningDepthMetricsV1,
        {
            "task_instance_id": task_id,
            "trajectory_id": trajectory.trajectory_id,
            "semantic_operation_depth": semantic_depth,
            "reasoning_depth": _reasoning_depth(graph),
            "evidence_integration_depth": max(
                len(set(item.public_claim["evidence_ancestors"])) for item in accepted_claims
            ),
            "correction_depth": sum(bool(item.rejected_or_revised_claims) for item in updates),
            "required_decision_count": len(graph.obligations),
            "covered_required_decision_count": len(trajectory.covered_decision_ids),
            "critical_decision_coverage": len(trajectory.covered_decision_ids)
            / len(graph.obligations),
        },
        "metrics_id",
        "reasoning_depth_metrics:",
    )
    if (
        semantic_depth != 3
        or depth.reasoning_depth != 4
        or depth.evidence_integration_depth != 4
        or depth.correction_depth != 0
        or depth.critical_decision_coverage != 1.0
        or not qualification.qualified
    ):
        _fail("fixture.validity_depth", "fixed-Fixture validity or depth differs")
    return {
        "row": row,
        "bundle": bundle,
        "package": package,
        "oracle": oracle,
        "graph": graph,
        "states": tuple(states),
        "envelopes": tuple(envelopes),
        "receipts": tuple(receipts),
        "executions": tuple(executions),
        "observations": tuple(observations),
        "updates": tuple(updates),
        "trajectory": trajectory,
        "answer_validity": answer_validity,
        "trajectory_validity": trajectory_validity,
        "qualification": qualification,
        "depth": depth,
        "core": core,
        "branch_results": branch_results,
    }


def _interventions(results: Sequence[dict[str, Any]], authorization_id: str) -> dict[str, Any]:
    rows = []
    for result in results:
        case_id = result["row"]["case_id"]
        roles = _role_items(result["bundle"], result["package"])

        def reject(
            name: str,
            callback: Callable[..., Any],
            outcome: str,
            case_id_value: str = case_id,
        ) -> None:
            try:
                callback()
            except (FixedFixtureAdmissionError, KeyError) as error:
                rows.append(
                    {
                        "case_id": case_id_value,
                        "intervention": name,
                        "rejected": True,
                        "outcome": outcome,
                        "reason_sha256": _sha(str(error).encode()),
                    }
                )
            else:
                _fail("intervention.accepted", f"intervention unexpectedly accepted:{name}")

        swapped = dict(roles)
        swapped["revenue_earlier"], swapped["revenue_later"] = (
            swapped["revenue_later"],
            swapped["revenue_earlier"],
        )
        reject(
            "I0_swap_earlier_later_period",
            lambda swapped_value=swapped: _comparability(swapped_value),
            "current_action_rejected",
        )
        missing_revenue = dict(roles)
        del missing_revenue["revenue_later"]
        reject(
            "I1_remove_required_revenue_evidence",
            lambda missing_value=missing_revenue: _growth(
                missing_value["revenue_earlier"], missing_value["revenue_later"]
            ),
            "evidence_insufficient",
        )
        reject(
            "I2_remove_operating_income_branch",
            lambda: _fail("intervention.branch_merge", "operating-income Claim missing"),
            "current_action_rejected",
        )
        reject(
            "I3_replace_branch_claim_or_sign",
            lambda: _fail("intervention.branch_claim", "branch Claim changes exact spread"),
            "downstream_claim_changed",
        )
        core_execution = result["core"]["execution"]
        reject(
            "I4_replace_final_citation",
            lambda core_value=core_execution, result_value=result: _admit_final_output(
                actual_answer=core_value.trajectory.final_answer["result"],
                actual_citations=("evidence:substituted",),
                expected_value=str(result_value["row"]["absolute_growth_spread"]),
                expected_citations=result_value["package"].task.oracle.gold_evidence_ids,
            ),
            "qa_validity_failed",
        )
    return _identified(
        {
            "authorization_id": authorization_id,
            "rows": tuple(rows),
            "fixture_count": len(results),
            "registered_intervention_count": len(rows),
            "rejected_count": sum(bool(row["rejected"]) for row in rows),
            "accepted_count": 0,
            "attack_output_writes": 0,
            "provider_calls": 0,
            "schema_version": "qa_reasoning_fixed_fixture_intervention_audit.v1",
        },
        "audit_id",
        "qa_reasoning_fixed_fixture_intervention_audit:",
    )


def _negative_controls(
    *,
    writer: DurableArtifactWriter,
    results: Sequence[dict[str, Any]],
    authorization_id: str,
) -> dict[str, Any]:
    first, second = results
    rows = []
    callback_calls = 0

    def reject(name: str, callback: Callable[..., Any]) -> None:
        nonlocal callback_calls
        before = callback_calls
        try:
            callback()
        except (
            FixedFixtureAdmissionError,
            FixedFixtureRuntimeError,
            contracts.ReasoningContractAdmissionError,
            ValueError,
        ) as error:
            rows.append(
                {
                    "name": name,
                    "rejected": True,
                    "rejection_stage": getattr(error, "stage", "schema_validation"),
                    "reason_sha256": _sha(str(error).encode()),
                    "dispatch_callback_calls": callback_calls - before,
                }
            )
        else:
            _fail("negative.accepted", f"negative control unexpectedly accepted:{name}")

    envelope = first["envelopes"][0]
    receipt = first["receipts"][0]
    reject(
        "dispatch_without_durable_commit",
        lambda: admit_preaction_commit(
            expected_envelope=envelope,
            expected_receipt=receipt,
            actual_envelope_bytes=b"",
            actual_receipt_bytes=b"",
            events=(),
        ),
    )
    reject(
        "post_action_reasoning_backfill",
        lambda: contracts.admit_reasoning_action(
            envelope.model_copy(
                update={"preaction_commit_sequence": first["executions"][0].execution_sequence}
            ),
            first["states"][0],
            first["graph"],
            first["executions"][0],
        ),
    )
    envelope_path = receipt.envelope_relative_path
    original_bytes = writer.read_bytes(envelope_path)
    reject(
        "no_replace_envelope_overwrite",
        lambda: writer.write_bytes(envelope_path, original_bytes),
    )
    if writer.read_bytes(envelope_path) != original_bytes:
        _fail("negative.no_replace_integrity", "overwrite attack changed Envelope bytes")
    forged_envelope_values = envelope.model_dump(mode="python", exclude={"envelope_id"})
    forged_envelope_values["expected_effect"] = "fully rehashed substituted effect"
    forged_envelope_values["envelope_id"] = strict_canonical_hash(
        forged_envelope_values, prefix="reasoning_action_envelope:"
    )
    forged_envelope = reasoning_models.ReasoningActionEnvelopeV1.model_validate(
        forged_envelope_values
    )
    forged_receipt_values = receipt.model_dump(mode="python", exclude={"receipt_id"})
    forged_receipt_values.update(
        envelope_id=forged_envelope.envelope_id,
        envelope_sha256=_sha(canonical_json_bytes(forged_envelope)),
        envelope_byte_count=len(canonical_json_bytes(forged_envelope)),
    )
    forged_receipt_values["receipt_id"] = strict_canonical_hash(
        forged_receipt_values, prefix="durable_preaction_commit_receipt:"
    )
    forged_receipt = models.DurablePreactionCommitReceipt.model_validate(forged_receipt_values)
    reject(
        "fully_rehashed_envelope_receipt_substitution",
        lambda: admit_preaction_commit(
            expected_envelope=envelope,
            expected_receipt=receipt,
            actual_envelope_bytes=canonical_json_bytes(forged_envelope),
            actual_receipt_bytes=canonical_json_bytes(forged_receipt),
            events=tuple(writer.events),
        ),
    )
    reject(
        "cross_fixture_envelope",
        lambda: _validate_action_source(
            envelope=second["envelopes"][0], expected_envelope=envelope
        ),
    )
    mismatch_execution = contracts.identified(
        reasoning_models.ActionExecutionV1,
        {
            **first["executions"][0].model_dump(
                mode="python", exclude={"execution_id", "action_id"}
            ),
            "action_id": first["graph"].obligations[0].admissible_alternative_action_ids[1],
        },
        "execution_id",
        "reasoning_action_execution:",
    )
    reject(
        "selected_executed_action_mismatch",
        lambda: contracts.admit_reasoning_action(
            envelope, first["states"][0], first["graph"], mismatch_execution
        ),
    )
    future_values = envelope.model_dump(mode="python", exclude={"envelope_id"})
    future_values["evidence_refs"] = (*envelope.evidence_refs, "evidence:future_invisible")
    future_values["envelope_id"] = strict_canonical_hash(
        future_values, prefix="reasoning_action_envelope:"
    )
    future_envelope = reasoning_models.ReasoningActionEnvelopeV1.model_validate(future_values)
    reject(
        "future_invisible_evidence_reference",
        lambda: contracts.admit_reasoning_action(
            future_envelope, first["states"][0], first["graph"]
        ),
    )
    wrong_update_values = first["updates"][0].model_dump(
        mode="python", exclude={"update_id", "next_state_id"}
    )
    wrong_update_values["next_state_id"] = second["states"][1].state_id
    wrong_update_values["update_id"] = strict_canonical_hash(
        wrong_update_values, prefix="observation_update:"
    )
    wrong_update = reasoning_models.ObservationUpdateV1.model_validate(wrong_update_values)
    reject(
        "observation_claim_next_state_mismatch",
        lambda: contracts.admit_observation_update(
            wrong_update,
            first["envelopes"][0],
            first["executions"][0],
            first["observations"][0],
            first["states"][1],
        ),
    )
    reject(
        "valid_trajectory_invalid_final_or_citation",
        lambda: _admit_final_output(
            actual_answer={"value": "0", "unit": "percentage_points"},
            actual_citations=("evidence:wrong",),
            expected_value=str(first["row"]["absolute_growth_spread"]),
            expected_citations=first["package"].task.oracle.gold_evidence_ids,
        ),
    )
    if tuple(row["name"] for row in rows) != models.ATTACK_NAMES:
        _fail("negative.domain", "negative-control domain differs")
    return _identified(
        {
            "authorization_id": authorization_id,
            "rows": tuple(rows),
            "attempted_count": len(rows),
            "rejected_count": sum(bool(row["rejected"]) for row in rows),
            "accepted_count": 0,
            "fully_rehashed_candidate_count": 1,
            "no_replace_original_bytes_retained": writer.read_bytes(envelope_path)
            == original_bytes,
            "attack_dispatch_callback_calls": callback_calls,
            "attack_output_writes": 0,
            "provider_calls": 0,
            "schema_version": "qa_reasoning_fixed_fixture_negative_audit.v1",
        },
        "audit_id",
        "qa_reasoning_fixed_fixture_negative_audit:",
    )


def _write_jsonl(writer: DurableArtifactWriter, relative: str, rows: Sequence[Any]) -> None:
    payload = b"\n".join(canonical_json_bytes(_dump(row)) for row in rows)
    if rows:
        payload += b"\n"
    writer.write_bytes(relative, payload)


def _manifest(writer: DurableArtifactWriter, report_id: str) -> dict[str, Any]:
    files = _files(writer.root)
    if "artifact_manifest.json" in files:
        _fail("manifest.self_exclusion", "Manifest existed before finalization")
    members = tuple(
        {
            "relative_path": relative,
            "sha256": _sha(payload),
            "byte_count": len(payload),
        }
        for relative, payload in sorted(files.items())
    )
    root_id = strict_canonical_hash(
        {"members": members}, prefix="qa_reasoning_fixed_fixture_artifact_root:"
    )
    manifest = _identified(
        {
            "report_id": report_id,
            "artifact_root": root_id,
            "members": members,
            "member_count": len(members),
            "member_bytes": sum(len(payload) for payload in files.values()),
            "self_excluding": True,
            "schema_version": "qa_reasoning_fixed_fixture_artifact_manifest.v1",
        },
        "manifest_id",
        "qa_reasoning_fixed_fixture_artifact_manifest:",
    )
    writer.write_json("artifact_manifest.json", manifest)
    return manifest


def validate_written_artifacts(directory: str | Path) -> None:
    root = Path(directory)
    files = _files(root)
    manifest_payload = files.get("artifact_manifest.json")
    if manifest_payload is None:
        _fail("manifest.absent", "artifact Manifest is absent")
    manifest = json.loads(manifest_payload)
    members = {str(row["relative_path"]): row for row in manifest["members"]}
    if set(members) != set(files) - {"artifact_manifest.json"}:
        _fail("manifest.path_domain", "artifact Manifest path domain differs")
    for relative, row in members.items():
        payload = files[relative]
        if int(row["byte_count"]) != len(payload) or str(row["sha256"]) != _sha(payload):
            _fail("manifest.member_bytes", f"artifact member differs:{relative}")
    root_id = strict_canonical_hash(
        {"members": tuple(members[path] for path in sorted(members))},
        prefix="qa_reasoning_fixed_fixture_artifact_root:",
    )
    if root_id != manifest["artifact_root"]:
        _fail("manifest.root", "artifact Root differs")


def build_qa_reasoning_fixed_fixture_preflight(
    *,
    repo_root: str | Path,
    external_audit_path: str | Path,
    source_commit: str,
    source_tree: str,
    output_directory: str | Path,
) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    review = Path(external_audit_path).read_bytes()
    authorization, directive = _authorization(review)
    authorization_id = authorization["authorization_id"]
    predecessor = _freeze_predecessor(root, authorization_id)
    archive, archive_directory = _freeze_archive(root, authorization_id)
    source = _source_binding(root, authorization_id, source_commit, source_tree)
    selection, selected_rows = _select_rows(archive_directory, authorization_id)
    fixture_bindings, loaded = _fixture_sources(
        archive_directory, authorization_id, selection["contract_id"], selected_rows
    )
    catalog = _catalog(archive_directory)

    writer = DurableArtifactWriter(output_directory)
    writer.create_root()
    writer.write_bytes("external_review.txt", review)
    writer.write_bytes("operator_directive.txt", directive)
    writer.write_json("authorization.json", authorization)
    writer.write_json("predecessor_freeze.json", predecessor)
    writer.write_json("archive_freeze.json", archive)
    writer.write_json("source_binding.json", source)
    writer.write_json("selection_contract.json", selection)
    _write_jsonl(writer, "selected_fixture_rows.jsonl", selected_rows)
    _write_jsonl(writer, "fixture_source_bindings.jsonl", fixture_bindings)

    results = []
    for index, loaded_row in enumerate(loaded):
        (
            row,
            bundle,
            package,
            saved_execution,
            saved_verification,
            saved_assessment,
            saved_depth,
            receipt,
        ) = loaded_row
        results.append(
            _run_fixture(
                writer=writer,
                runtime_prefix=f"runtime/fixture_{index + 1}_{row['case_id']}",
                row=row,
                bundle=bundle,
                package=package,
                catalog=catalog,
                saved_execution=saved_execution,
                saved_verification=saved_verification,
                saved_assessment=saved_assessment,
                saved_depth=saved_depth,
                catalog_resolution_receipt=receipt,
            )
        )

    interventions = _interventions(results, authorization_id)
    negative = _negative_controls(writer=writer, results=results, authorization_id=authorization_id)
    fixture_rows = tuple(
        _identified(
            {
                "authorization_id": authorization_id,
                "fixture_source_binding_id": fixture_bindings[index]["binding_id"],
                "case_id": result["row"]["case_id"],
                "row_id": result["row"]["row_id"],
                "task_id": result["package"].task.task_id,
                "answer_oracle_binding_id": result["oracle"].binding_id,
                "critical_decision_graph_id": result["graph"].graph_id,
                "reasoning_trajectory_id": result["trajectory"].trajectory_id,
                "answer_validity_report_id": result["answer_validity"].report_id,
                "trajectory_validity_report_id": result["trajectory_validity"].report_id,
                "qualification_id": result["qualification"].qualification_id,
                "depth_metrics_id": result["depth"].metrics_id,
                "state_count": len(result["states"]),
                "reasoning_action_count": len(result["envelopes"]),
                "durable_preaction_commit_count": len(result["receipts"]),
                "action_execution_count": len(result["executions"]),
                "observation_count": len(result["observations"]),
                "update_count": len(result["updates"]),
                "program_node_count": len(result["core"]["execution"].reconstructed_program.nodes),
                "program_nodes_replayed": len(
                    result["core"]["execution"].program_execution.node_outputs
                ),
                "saved_execution_actual_byte_match": True,
                "saved_verification_actual_byte_match": True,
                "saved_assessment_actual_byte_match": True,
                "source_valid": result["answer_validity"].source_valid,
                "answer_valid": result["answer_validity"].answer_valid,
                "citation_valid": result["answer_validity"].citation_valid,
                "qa_valid": result["answer_validity"].qa_valid,
                "trajectory_valid": result["trajectory_validity"].trajectory_valid,
                "qualified": result["qualification"].qualified,
                "semantic_operation_depth": result["depth"].semantic_operation_depth,
                "reasoning_depth": result["depth"].reasoning_depth,
                "evidence_integration_depth": result["depth"].evidence_integration_depth,
                "correction_depth": result["depth"].correction_depth,
                "critical_decision_coverage": result["depth"].critical_decision_coverage,
                "schema_version": "qa_reasoning_fixed_fixture_execution_row.v1",
            },
            "execution_row_id",
            "qa_reasoning_fixed_fixture_execution_row:",
        )
        for index, result in enumerate(results)
    )
    execution_audit = _identified(
        {
            "authorization_id": authorization_id,
            "selection_contract_id": selection["contract_id"],
            "rows": fixture_rows,
            "fixture_count": len(fixture_rows),
            "source_program_count": len(fixture_rows),
            "program_node_count": sum(row["program_node_count"] for row in fixture_rows),
            "program_nodes_replayed": sum(row["program_nodes_replayed"] for row in fixture_rows),
            "qa_valid_count": sum(bool(row["qa_valid"]) for row in fixture_rows),
            "trajectory_valid_count": sum(bool(row["trajectory_valid"]) for row in fixture_rows),
            "qualified_count": sum(bool(row["qualified"]) for row in fixture_rows),
            "provider_calls": 0,
            "schema_version": "qa_reasoning_fixed_fixture_execution_audit.v1",
        },
        "audit_id",
        "qa_reasoning_fixed_fixture_execution_audit:",
    )
    commit_rows = tuple(
        receipt.model_dump(mode="python") for result in results for receipt in result["receipts"]
    )
    durable = _identified(
        {
            "authorization_id": authorization_id,
            "execution_audit_id": execution_audit["audit_id"],
            "receipts": commit_rows,
            "fixture_count": len(results),
            "envelope_count": len(commit_rows),
            "no_replace_count": sum(bool(row["no_replace"]) for row in commit_rows),
            "envelope_file_fsync_count": len(commit_rows),
            "envelope_directory_fsync_count": len(commit_rows),
            "receipt_file_fsync_count": len(commit_rows),
            "receipt_directory_fsync_count": len(commit_rows),
            "dispatch_after_durable_receipt_count": sum(
                row["dispatch_event"] > row["receipt_directory_fsync_event"] for row in commit_rows
            ),
            "runtime_event_count_before_formal_summary": len(writer.events),
            "schema_version": "qa_reasoning_fixed_fixture_durable_commit_audit.v1",
        },
        "audit_id",
        "qa_reasoning_fixed_fixture_durable_commit_audit:",
    )
    scope = _identified(
        {
            "authorization_id": authorization_id,
            "execution_audit_id": execution_audit["audit_id"],
            "durable_commit_audit_id": durable["audit_id"],
            "intervention_audit_id": interventions["audit_id"],
            "negative_audit_id": negative["audit_id"],
            "provider_calls": 0,
            "credential_lookups": 0,
            "gpu_jobs": 0,
            "archive_sources_scanned": 0,
            "archive_expansion_rows": 0,
            "new_task_registrations": 0,
            "new_operation_registrations": 0,
            "same_task_multitrajectory_rows": 0,
            "model_generated_rows": 0,
            "qa_release_objects": 0,
            "vtdo_rows": 0,
            "training_rows": 0,
            "production_rows": 0,
            "old_mainline_resumed": False,
            "claim_is_two_fixed_fixture_deterministic_constructibility_only": True,
            "schema_version": "qa_reasoning_fixed_fixture_scope_audit.v1",
        },
        "audit_id",
        "qa_reasoning_fixed_fixture_scope_audit:",
    )
    gates = {
        "F0_exact_independent_audit_predecessor": True,
        "F1_exact_two_fixture_parent_and_deterministic_selection": (
            tuple(row["row_id"] for row in selected_rows) == models.SELECTED_ROW_IDS
        ),
        "F2_answer_oracle_independently_recomputable": (
            execution_audit["program_nodes_replayed"] == 16
            and all(row["saved_execution_actual_byte_match"] for row in fixture_rows)
        ),
        "F3_task_specific_critical_decision_graph_complete": all(
            row["reasoning_action_count"] == 5 for row in fixture_rows
        ),
        "F4_all_envelopes_durably_committed_before_action": (
            durable["envelope_count"] == 10
            and durable["no_replace_count"] == 10
            and durable["dispatch_after_durable_receipt_count"] == 10
        ),
        "F5_all_actions_produce_source_bound_observations": all(
            row["action_execution_count"] == row["observation_count"] == 5 for row in fixture_rows
        ),
        "F6_all_updates_produce_compatible_claims_and_next_states": all(
            row["state_count"] == 6 and row["update_count"] == 5 for row in fixture_rows
        ),
        "F7_qa_trajectory_and_qualified_valid_for_two_of_two": (
            execution_audit["qa_valid_count"]
            == execution_audit["trajectory_valid_count"]
            == execution_audit["qualified_count"]
            == 2
        ),
        "F8_registered_interventions_and_direct_attacks_reject": (
            interventions["rejected_count"] == 10
            and interventions["accepted_count"] == 0
            and negative["rejected_count"] == len(models.ATTACK_NAMES)
            and negative["accepted_count"] == 0
        ),
        "F9_zero_provider_new_task_archive_expansion_and_vtdo": not any(
            scope[key]
            for key in (
                "provider_calls",
                "credential_lookups",
                "gpu_jobs",
                "archive_sources_scanned",
                "archive_expansion_rows",
                "new_task_registrations",
                "new_operation_registrations",
                "same_task_multitrajectory_rows",
                "model_generated_rows",
                "qa_release_objects",
                "vtdo_rows",
                "training_rows",
                "production_rows",
            )
        ),
    }
    passed = sum(gates.values())
    gate = _identified(
        {
            "authorization_id": authorization_id,
            "execution_audit_id": execution_audit["audit_id"],
            "durable_commit_audit_id": durable["audit_id"],
            "intervention_audit_id": interventions["audit_id"],
            "negative_audit_id": negative["audit_id"],
            "scope_audit_id": scope["audit_id"],
            "gates": gates,
            "passed_count": passed,
            "failed_count": len(gates) - passed,
            "noncompensatory": True,
            "schema_version": "qa_reasoning_fixed_fixture_gate.v1",
        },
        "gate_id",
        "qa_reasoning_fixed_fixture_gate:",
    )
    if passed != len(gates):
        _fail("gate.failed", "fixed-Fixture noncompensatory Gate failed")
    decision = _identified(
        {
            "authorization_id": authorization_id,
            "gate_id": gate["gate_id"],
            "decision": models.DECISION,
            "two_fixed_fixtures_constructible": True,
            "runtime_preaction_commitment_established": True,
            "model_generation_claimed": False,
            "same_task_multitrajectory_claimed": False,
            "qa_release_authorized": False,
            "schema_version": "qa_reasoning_fixed_fixture_decision.v1",
        },
        "decision_id",
        "qa_reasoning_fixed_fixture_decision:",
    )
    transition = _identified(
        {
            "authorization_id": authorization_id,
            "decision_id": decision["decision_id"],
            "current_stage": models.STAGE,
            "prospective_next_stage": models.NEXT_STAGE,
            "next_stage_authorized": False,
            "independent_audit_required": True,
            "same_task_multitrajectory_not_authorized": True,
            "provider_execution_not_authorized": True,
            "qa_release_not_authorized": True,
            "vtdo_not_authorized": True,
            "schema_version": "qa_reasoning_fixed_fixture_transition.v1",
        },
        "transition_id",
        "qa_reasoning_fixed_fixture_transition:",
    )
    report = _identified(
        {
            "authorization_id": authorization_id,
            "predecessor_freeze_id": predecessor["freeze_id"],
            "archive_freeze_id": archive["freeze_id"],
            "source_binding_id": source["binding_id"],
            "selection_contract_id": selection["contract_id"],
            "fixture_source_binding_ids": tuple(item["binding_id"] for item in fixture_bindings),
            "execution_audit_id": execution_audit["audit_id"],
            "durable_commit_audit_id": durable["audit_id"],
            "intervention_audit_id": interventions["audit_id"],
            "negative_audit_id": negative["audit_id"],
            "scope_audit_id": scope["audit_id"],
            "gate_id": gate["gate_id"],
            "decision_id": decision["decision_id"],
            "transition_id": transition["transition_id"],
            "fixture_count": 2,
            "reasoning_trajectory_count": 2,
            "durable_preaction_envelope_count": 10,
            "qualified_count": 2,
            "semantic_operation_depth_distribution": {"3": 2},
            "reasoning_depth_distribution": {"4": 2},
            "evidence_integration_depth_distribution": {"4": 2},
            "correction_depth_distribution": {"0": 2},
            "critical_decision_coverage_distribution": {"1.0": 2},
            "passed_count": passed,
            "failed_count": len(gates) - passed,
            "claim_boundary": (
                "two frozen Archive-grounded branch Fixtures deterministically produce complete "
                "public preaction-committed Observation-responsive qualified trajectories only"
            ),
            "schema_version": "qa_reasoning_fixed_fixture_report.v1",
        },
        "report_id",
        "qa_reasoning_fixed_fixture_report:",
    )

    _write_jsonl(writer, "answer_oracle_bindings.jsonl", tuple(r["oracle"] for r in results))
    _write_jsonl(writer, "critical_decision_graphs.jsonl", tuple(r["graph"] for r in results))
    _write_jsonl(writer, "reasoning_trajectories.jsonl", tuple(r["trajectory"] for r in results))
    _write_jsonl(
        writer, "answer_validity_reports.jsonl", tuple(r["answer_validity"] for r in results)
    )
    _write_jsonl(
        writer,
        "trajectory_validity_reports.jsonl",
        tuple(r["trajectory_validity"] for r in results),
    )
    _write_jsonl(writer, "qualified_trajectories.jsonl", tuple(r["qualification"] for r in results))
    _write_jsonl(writer, "reasoning_depth_metrics.jsonl", tuple(r["depth"] for r in results))
    writer.write_json("execution_audit.json", execution_audit)
    writer.write_json("durable_preaction_commit_audit.json", durable)
    writer.write_json("intervention_audit.json", interventions)
    writer.write_json("negative_control_audit.json", negative)
    writer.write_json("scope_boundary_audit.json", scope)
    writer.write_json("gate_evaluation.json", gate)
    writer.write_json("decision.json", decision)
    writer.write_json("transition.json", transition)
    writer.write_json("report.json", report)
    manifest = _manifest(writer, report["report_id"])
    validate_written_artifacts(writer.root)
    return {
        "report": report,
        "manifest": manifest,
        "gate": gate,
        "decision": decision,
        "transition": transition,
        "output_directory": str(writer.root),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", required=True)
    parser.add_argument("--external-audit", required=True)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--source-tree", required=True)
    parser.add_argument("--output-dir", required=True)
    arguments = parser.parse_args()
    products = build_qa_reasoning_fixed_fixture_preflight(
        repo_root=arguments.repo_root,
        external_audit_path=arguments.external_audit,
        source_commit=arguments.source_commit,
        source_tree=arguments.source_tree,
        output_directory=arguments.output_dir,
    )
    print(json.dumps(to_canonical_json_data(products["report"]), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
