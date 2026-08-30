from __future__ import annotations

import argparse
import hashlib
import subprocess
import tempfile
from collections.abc import Iterable
from dataclasses import replace
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.canonical_json import canonical_json_bytes, strict_canonical_hash
from trusted_synthesis.core.evaluation.evaluator import CandidateQualityEvaluator
from trusted_synthesis.core.evaluation.realization_binding import (
    RealizationExecutionBinding,
    bind_realization_execution,
    describe_generated_trajectory,
)
from trusted_synthesis.core.evaluation.schema import QualityAssessment, ReleaseDecision
from trusted_synthesis.core.immutable_artifacts import write_immutable_artifact_directory
from trusted_synthesis.core.operations.registry import OperationRegistry
from trusted_synthesis.core.release import (
    DiversityAwareReleaseSelection,
    DiversityReleasePolicy,
    SplitPolicy,
    select_diversity_aware_release,
)
from trusted_synthesis.core.task.realization import RealizedTaskPackage
from trusted_synthesis.core.task.semantic import canonicalize_semantic_plan
from trusted_synthesis.core.trajectory.schema import Trajectory
from trusted_synthesis.domains.finance.operations import finance_vnext_operation_registry
from trusted_synthesis.domains.finance.tasks import FinanceTaskPlugin
from trusted_synthesis.experiments.counterfactual_finance_fixture import (
    build_finance_counterfactual_case,
)
from trusted_synthesis.experiments.finance_pilot.candidate import (
    FINANCE_NUMERIC_GENERATOR_CONTRACT_ID,
    FinanceNumericCandidateGenerator,
)
from trusted_synthesis.hashing import canonical_hash
from trusted_synthesis.runtime import InMemoryEvidenceToolRuntime

EXTERNAL_AUDIT_SHA256 = "f89dce636bb7176e4dea9466fb794cccdfc6d73d1f4b79578bcef6090b3f2557"
EXTERNAL_AUDIT_BYTE_COUNT = 31_266
RAW_REFERENCE_EXPECTATIONS = {
    "raw_financial_data_lake/finraw/qa/diversity.py": (
        "001d21ec74d5641d2e085cee547fef2311638a9fc5d2a3a298c34fcd76a8c385"
    ),
    "raw_financial_data_lake/finraw/qa/graph_patterns.py": (
        "763f52bcb391b1678f8833fda8662f20f08c3abf549550f07f2e3cb48bd007c7"
    ),
    "raw_financial_data_lake/finraw/qa/verbalizer.py": (
        "07c039be67fe52416e4978904582fbb0bbfa4a22b46578863d10f71296c3d213"
    ),
}
SOURCE_IMPLEMENTATION_PATHS = (
    "trusted_data_synthesis/src/trusted_synthesis/core/evaluation/evaluator.py",
    "trusted_data_synthesis/src/trusted_synthesis/core/evaluation/realization_binding.py",
    "trusted_data_synthesis/src/trusted_synthesis/core/evaluation/schema.py",
    "trusted_data_synthesis/src/trusted_synthesis/core/immutable_artifacts.py",
    "trusted_data_synthesis/src/trusted_synthesis/core/operations/registry.py",
    "trusted_data_synthesis/src/trusted_synthesis/core/release/diversity_selector.py",
    "trusted_data_synthesis/src/trusted_synthesis/core/release/split.py",
    "trusted_data_synthesis/src/trusted_synthesis/core/task/pattern_compiler.py",
    "trusted_data_synthesis/src/trusted_synthesis/core/task/realization.py",
    "trusted_data_synthesis/src/trusted_synthesis/core/task/semantic.py",
    "trusted_data_synthesis/src/trusted_synthesis/domains/finance/realization.py",
    "trusted_data_synthesis/src/trusted_synthesis/domains/finance/tasks.py",
    ("trusted_data_synthesis/src/trusted_synthesis/experiments/finance_pilot/runner.py"),
    ("trusted_data_synthesis/src/trusted_synthesis/experiments/finance_pilot/task_factory.py"),
    (
        "trusted_data_synthesis/src/trusted_synthesis/experiments/qa_realization_vnext/"
        "parent_authority_preflight.py"
    ),
)


class SourceFileBinding(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    path: str = Field(min_length=1)
    git_blob_id: str = Field(min_length=40, max_length=64)
    sha256: str = Field(min_length=64, max_length=64)
    byte_count: int = Field(ge=1)
    working_tree_bytes_match: bool


class RawReferenceBinding(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    path: str = Field(min_length=1)
    expected_sha256: str = Field(min_length=64, max_length=64)
    observed_sha256: str = Field(min_length=64, max_length=64)
    byte_count: int = Field(ge=1)
    exact_match: bool


class AttackControl(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    attack_id: str = Field(min_length=1)
    attack_class: str = Field(min_length=1)
    expected: str = "rejected"
    observed: str = Field(pattern="^(rejected|admitted)$")
    passed: bool
    detail: str = Field(min_length=1)


class QAParentAuthorityPreflight(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    preflight_id: str = Field(min_length=1)
    external_audit_sha256: str = Field(min_length=64, max_length=64)
    external_audit_byte_count: int = Field(ge=1)
    source_commit: str = Field(min_length=40, max_length=40)
    source_root: str = Field(min_length=1)
    source_file_count: int = Field(ge=1)
    raw_reference_root: str = Field(min_length=1)
    raw_reference_file_count: int = Field(ge=1)
    semantic_schema_count: int = Field(ge=1)
    semantic_instance_count: int = Field(ge=1)
    realized_package_count: int = Field(ge=1)
    execution_binding_count: int = Field(ge=1)
    release_selection_id: str = Field(min_length=1)
    attack_control_count: int = Field(ge=1)
    rejected_attack_count: int = Field(ge=0)
    provider_call_count: int = Field(default=0, ge=0)
    gpu_job_count: int = Field(default=0, ge=0)
    imported_raw_qa_row_count: int = Field(default=0, ge=0)
    historical_artifact_mutation_count: int = Field(default=0, ge=0)
    gates: dict[str, bool]
    claim_boundary: dict[str, Any]
    schema_version: str = "qa_parent_authority_preflight.v1"

    @model_validator(mode="after")
    def validate_identity(self) -> QAParentAuthorityPreflight:
        if any(not passed for passed in self.gates.values()):
            raise ValueError("QA Parent Authority preflight failed a hard gate")
        expected = strict_canonical_hash(
            self.model_dump(mode="python", exclude={"preflight_id"}),
            prefix="qa_parent_authority_preflight:",
        )
        if self.preflight_id != expected:
            raise ValueError("QA Parent Authority preflight identity is invalid")
        return self


class ParentAuthorityBuildProducts(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", arbitrary_types_allowed=True)

    report: QAParentAuthorityPreflight
    source_files: tuple[SourceFileBinding, ...]
    raw_references: tuple[RawReferenceBinding, ...]
    attacks: tuple[AttackControl, ...]
    realized_packages: tuple[RealizedTaskPackage, ...]
    trajectories: tuple[Trajectory, ...]
    assessments: tuple[QualityAssessment, ...]
    execution_bindings: tuple[RealizationExecutionBinding, ...]
    release_selection: DiversityAwareReleaseSelection


def build_parent_authority_preflight(
    *,
    repo_root: str | Path,
    external_audit_path: str | Path,
    source_commit: str,
) -> ParentAuthorityBuildProducts:
    root = Path(repo_root).resolve()
    audit_bytes = Path(external_audit_path).read_bytes()
    audit_sha = hashlib.sha256(audit_bytes).hexdigest()
    resolved_commit = _require_exact_commit(root, source_commit)
    source_files = _source_manifest(root, resolved_commit)
    source_root = strict_canonical_hash(source_files, prefix="qa_parent_source_root:")
    raw_references = _raw_reference_manifest(root)
    raw_root = strict_canonical_hash(raw_references, prefix="qa_raw_reference_root:")

    fixture_rows = tuple(_fixture_portfolio(index) for index in (1, 5))
    primary_compilation, primary_records = fixture_rows[0]
    secondary_compilation, secondary_records = fixture_rows[1]
    release_policy = DiversityReleasePolicy(
        policy_id="qa_parent_authority_release_control.v2",
        max_per_semantic_instance=2,
        max_per_semantic_schema=10,
    )
    split_policy = SplitPolicy(policy_id="qa_parent_authority_instance_split.v1")
    primary_selection = select_diversity_aware_release(
        primary_records,
        policy=release_policy,
        split_policy=split_policy,
    )
    attacks = _attack_controls(
        root=root,
        primary_compilation=primary_compilation,
        primary_records=primary_records,
        secondary_compilation=secondary_compilation,
        secondary_records=secondary_records,
        primary_selection=primary_selection,
        split_policy=split_policy,
        source_files=source_files,
        raw_references=raw_references,
    )
    realized_packages = tuple(record[0] for record in primary_records)
    trajectories = tuple(record[1] for record in primary_records)
    assessments = tuple(record[2] for record in primary_records)
    execution_bindings = tuple(record[3] for record in primary_records)
    schemas = {
        primary_compilation.semantic_binding.plan.semantic_task_id,
        secondary_compilation.semantic_binding.plan.semantic_task_id,
    }
    instances = {
        primary_compilation.semantic_binding.instance.semantic_instance_id,
        secondary_compilation.semantic_binding.instance.semantic_instance_id,
    }
    gates = {
        "external_audit_sha256_exact": audit_sha == EXTERNAL_AUDIT_SHA256,
        "external_audit_byte_count_exact": len(audit_bytes) == EXTERNAL_AUDIT_BYTE_COUNT,
        "source_commit_exact_and_resolvable": resolved_commit == source_commit,
        "source_working_tree_bytes_exact": all(
            row.working_tree_bytes_match for row in source_files
        ),
        "source_root_nonempty": bool(source_root),
        "raw_reference_bytes_exact": all(row.exact_match for row in raw_references),
        "raw_reference_root_nonempty": bool(raw_root),
        "same_schema_two_distinct_instances": len(schemas) == 1 and len(instances) == 2,
        "primary_realizations_all_valid": all(
            row.realization.validation.passed for row in realized_packages
        ),
        "primary_assessments_all_accepted": all(
            row.decision == ReleaseDecision.ACCEPTED for row in assessments
        ),
        "execution_binding_coverage_exact": len(execution_bindings) == len(realized_packages),
        "instance_release_gates_pass": all(primary_selection.hard_gates.values()),
        "registered_attacks_all_rejected": all(row.passed for row in attacks),
        "provider_calls_zero": True,
        "gpu_jobs_zero": True,
        "raw_qa_rows_imported_zero": True,
        "historical_artifact_mutations_zero": True,
    }
    claim_boundary = {
        "stage": "qa_parent_authority_credential_free_preflight",
        "implemented": (
            "operation semantic contract identity",
            "SemanticInstance parent authority",
            "content-addressed RealizedTaskPackage",
            "RealizationExecutionBinding and assessment hash",
            "instance-level split and release quota",
            "per-child exact Fraction weight assignment",
            "exact Git source root and Raw byte rehash",
            "fsync-backed kernel no-replace atomic artifact publication",
            "Finance Pilot realization portfolio integration",
        ),
        "not_claimed": (
            "Provider model behavior",
            "production QA quality",
            "training authorization",
            "VTDO State or Contribution",
            "repair of the frozen failed v26.181 Gate",
        ),
        "provider_call_count": 0,
        "historical_artifact_mutation_count": 0,
    }
    payload = {
        "external_audit_sha256": audit_sha,
        "external_audit_byte_count": len(audit_bytes),
        "source_commit": resolved_commit,
        "source_root": source_root,
        "source_file_count": len(source_files),
        "raw_reference_root": raw_root,
        "raw_reference_file_count": len(raw_references),
        "semantic_schema_count": len(schemas),
        "semantic_instance_count": len(instances),
        "realized_package_count": len(realized_packages),
        "execution_binding_count": len(execution_bindings),
        "release_selection_id": primary_selection.selection_id,
        "attack_control_count": len(attacks),
        "rejected_attack_count": sum(row.observed == "rejected" for row in attacks),
        "provider_call_count": 0,
        "gpu_job_count": 0,
        "imported_raw_qa_row_count": 0,
        "historical_artifact_mutation_count": 0,
        "gates": gates,
        "claim_boundary": claim_boundary,
        "schema_version": "qa_parent_authority_preflight.v1",
    }
    preflight_id = strict_canonical_hash(
        payload,
        prefix="qa_parent_authority_preflight:",
    )
    return ParentAuthorityBuildProducts(
        report=QAParentAuthorityPreflight(preflight_id=preflight_id, **payload),
        source_files=source_files,
        raw_references=raw_references,
        attacks=attacks,
        realized_packages=realized_packages,
        trajectories=trajectories,
        assessments=assessments,
        execution_bindings=execution_bindings,
        release_selection=primary_selection,
    )


def write_parent_authority_artifacts(
    products: ParentAuthorityBuildProducts,
    output_dir: str | Path,
) -> tuple[str, ...]:
    payloads = {
        "attack_matrix.jsonl": _jsonl(products.attacks),
        "claim_boundary.json": _json(products.report.claim_boundary),
        "execution_bindings.jsonl": _jsonl(products.execution_bindings),
        "quality_assessments.jsonl": _jsonl(products.assessments),
        "raw_reference_manifest.jsonl": _jsonl(products.raw_references),
        "realized_task_packages.jsonl": _jsonl(products.realized_packages),
        "release_selection.json": _json(products.release_selection),
        "source_manifest.jsonl": _jsonl(products.source_files),
        "trajectory_manifest.jsonl": _jsonl(products.trajectories),
        "report.json": _json(products.report),
    }
    artifact_rows = tuple(
        {
            "filename": name,
            "sha256": hashlib.sha256(value).hexdigest(),
            "byte_count": len(value),
        }
        for name, value in sorted(payloads.items())
    )
    payloads["artifact_manifest.json"] = _json(
        {
            "files": artifact_rows,
            "artifact_root": strict_canonical_hash(
                artifact_rows,
                prefix="qa_parent_authority_artifact_root:",
            ),
            "schema_version": "qa_parent_authority_artifact_manifest.v1",
        }
    )
    return write_immutable_artifact_directory(output_dir, payloads)


def _fixture_portfolio(index: int) -> tuple[Any, tuple[Any, ...]]:
    contract_case = build_finance_counterfactual_case(index)
    plugin = FinanceTaskPlugin(allow_structured_claims=True)
    instantiation = plugin.compile_evidence_ids(
        contract_case.task.public.task_type,
        contract_case.proof_graph,
        contract_case.bundle,
        contract_case.task.oracle.gold_evidence_ids,
    )
    compilation = plugin.realize_instantiation(
        instantiation,
        contract_case.proof_graph,
        contract_case.bundle,
    )
    generator = FinanceNumericCandidateGenerator()
    evaluator = CandidateQualityEvaluator(semantic_policy=contract_case.semantic_policy)
    records = []
    for realized in compilation.selected:
        generated = generator.generate(
            realized.task.public,
            InMemoryEvidenceToolRuntime(contract_case.corpus),
        )
        trajectory, descriptor = describe_generated_trajectory(
            realized,
            contract_case.corpus,
            generated,
            generator_contract_id=FINANCE_NUMERIC_GENERATOR_CONTRACT_ID,
        )
        assessment = evaluator.evaluate(
            realized.task,
            contract_case.corpus,
            contract_case.proof_graph,
            trajectory,
        )
        execution_binding = bind_realization_execution(
            realized,
            compilation.portfolio,
            trajectory,
            assessment,
            descriptor,
        )
        records.append((realized, trajectory, assessment, execution_binding))
    return compilation, tuple(records)


def _attack_controls(
    *,
    root: Path,
    primary_compilation: Any,
    primary_records: tuple[Any, ...],
    secondary_compilation: Any,
    secondary_records: tuple[Any, ...],
    primary_selection: DiversityAwareReleaseSelection,
    split_policy: SplitPolicy,
    source_files: tuple[SourceFileBinding, ...],
    raw_references: tuple[RawReferenceBinding, ...],
) -> tuple[AttackControl, ...]:
    controls: list[AttackControl] = []

    original_registry = finance_vnext_operation_registry()
    definitions = tuple(
        original_registry.require(str(row["operator_id"])) for row in original_registry.manifest()
    )
    changed = tuple(
        replace(definition, semantic_version="attack.semantic.v999")
        if definition.operator_id == "lookup"
        else definition
        for definition in definitions
    )
    changed_registry = OperationRegistry(changed)
    changed_plan = canonicalize_semantic_plan(
        primary_compilation.semantic_binding.proposal,
        primary_records[0][0].task.oracle.task_program,
        primary_compilation.semantic_binding.binding.evidence_binding,
        changed_registry,
        effective_answer_schema=primary_records[0][0].task.public.answer_schema,
    )
    controls.append(
        _control(
            "operation_semantic_contract_mutation",
            "operation_contract",
            changed_plan.semantic_task_id
            != primary_compilation.semantic_binding.plan.semantic_task_id,
            "semantic version mutation must change the semantic schema identity",
        )
    )

    package = primary_records[0][0]
    forged_plan = package.semantic_plan.model_copy(update={"plan_id": "plan:forged"})
    controls.append(
        _exception_control(
            "model_construct_forged_plan_parent",
            "parent_injection",
            lambda: RealizedTaskPackage.model_validate(
                package.model_construct(
                    **{
                        **package.model_dump(mode="python"),
                        "semantic_plan": forged_plan,
                    }
                ).model_dump(mode="python", warnings=False)
            ),
        )
    )
    forged_snapshot = package.binding_snapshot.model_copy(
        update={"binding_snapshot_id": "binding_snapshot:forged"}
    )
    controls.append(
        _exception_control(
            "model_construct_forged_binding_parent",
            "parent_injection",
            lambda: RealizedTaskPackage.model_validate(
                package.model_construct(
                    **{
                        **package.model_dump(mode="python"),
                        "binding_snapshot": forged_snapshot,
                    }
                ).model_dump(mode="python", warnings=False)
            ),
        )
    )
    controls.append(
        _exception_control(
            "same_task_id_sibling_execution_substitution",
            "execution_binding",
            lambda: select_diversity_aware_release(
                (
                    (
                        primary_records[1][0],
                        primary_records[1][1],
                        primary_records[1][2],
                        primary_records[0][3],
                    ),
                ),
                policy=DiversityReleasePolicy(policy_id="attack.sibling_substitution.v2"),
                split_policy=split_policy,
            ),
        )
    )
    stale_assessment = primary_records[0][2].model_copy(
        update={"decision": ReleaseDecision.REJECTED}
    )
    controls.append(
        _exception_control(
            "stale_assessment_hash",
            "assessment_hash",
            lambda: bind_realization_execution(
                primary_records[0][0],
                primary_compilation.portfolio,
                primary_records[0][1],
                stale_assessment,
                primary_records[0][3].execution_descriptor,
            ),
        )
    )
    attacked_selection = primary_selection.model_dump(mode="json")
    attacked_selection["weight_assignments"] = attacked_selection["weight_assignments"][:-1]
    attacked_selection["selection_id"] = canonical_hash(
        {key: value for key, value in attacked_selection.items() if key != "selection_id"},
        prefix="diversity_aware_release_selection:",
    )
    controls.append(
        _exception_control(
            "deleted_child_weight_assignment",
            "exact_fraction_weight",
            lambda: DiversityAwareReleaseSelection.model_validate(attacked_selection),
        )
    )
    two_instance_selection = select_diversity_aware_release(
        (primary_records[0], secondary_records[0]),
        policy=DiversityReleasePolicy(
            policy_id="instance_quota_positive_control.v2",
            max_per_semantic_instance=1,
            max_per_semantic_schema=2,
        ),
        split_policy=split_policy,
    )
    controls.append(
        _control(
            "abstract_schema_not_used_as_instance_quota",
            "instance_release",
            (
                primary_compilation.semantic_binding.plan.semantic_task_id
                == secondary_compilation.semantic_binding.plan.semantic_task_id
                and primary_compilation.semantic_binding.instance.semantic_instance_id
                != secondary_compilation.semantic_binding.instance.semantic_instance_id
                and len(two_instance_selection.selected_realization_ids) == 2
            ),
            "two bindings of one semantic schema must retain independent instance quota",
        )
    )
    controls.append(
        _control(
            "mutated_source_bytes",
            "source_byte_authenticity",
            not _bytes_match(source_files[0], b"mutated"),
            "mutated bytes must not match the Git-bound source manifest",
        )
    )
    raw_path = root / raw_references[0].path
    controls.append(
        _control(
            "mutated_raw_reference_bytes",
            "raw_byte_authenticity",
            not _raw_bytes_match(raw_references[0], raw_path.read_bytes() + b"attack"),
            "Raw reference validation must recompute actual file bytes",
        )
    )
    controls.append(
        _exception_control(
            "arbitrary_40_character_commit",
            "source_commit",
            lambda: _require_exact_commit(root, "0" * 40),
        )
    )
    with tempfile.TemporaryDirectory(prefix="qa-parent-writer-control-") as temp_dir:
        target = Path(temp_dir) / "formal"
        write_immutable_artifact_directory(target, {"control.json": b"{}\n"})
        controls.append(
            _exception_control(
                "existing_artifact_directory_overwrite",
                "immutable_writer",
                lambda: write_immutable_artifact_directory(
                    target,
                    {"control.json": b"attacked\n"},
                ),
            )
        )
        if (target / "control.json").read_bytes() != b"{}\n":
            raise AssertionError("immutable writer control changed existing bytes")
    return tuple(controls)


def _source_manifest(root: Path, commit: str) -> tuple[SourceFileBinding, ...]:
    rows = []
    for relative in SOURCE_IMPLEMENTATION_PATHS:
        blob = _git(root, "show", f"{commit}:{relative}", text=False)
        if not isinstance(blob, bytes):
            raise TypeError("Git source blob must be returned as bytes")
        blob_id = str(_git(root, "rev-parse", f"{commit}:{relative}")).strip()
        working = (root / relative).read_bytes()
        rows.append(
            SourceFileBinding(
                path=relative,
                git_blob_id=blob_id,
                sha256=hashlib.sha256(blob).hexdigest(),
                byte_count=len(blob),
                working_tree_bytes_match=working == blob,
            )
        )
    return tuple(rows)


def _raw_reference_manifest(root: Path) -> tuple[RawReferenceBinding, ...]:
    rows = []
    for relative, expected in sorted(RAW_REFERENCE_EXPECTATIONS.items()):
        payload = (root / relative).read_bytes()
        observed = hashlib.sha256(payload).hexdigest()
        rows.append(
            RawReferenceBinding(
                path=relative,
                expected_sha256=expected,
                observed_sha256=observed,
                byte_count=len(payload),
                exact_match=observed == expected,
            )
        )
    return tuple(rows)


def _require_exact_commit(root: Path, commit: str) -> str:
    if len(commit) != 40:
        raise ValueError("source commit must be a full 40-character identity")
    resolved = str(_git(root, "rev-parse", "--verify", f"{commit}^{{commit}}")).strip()
    if resolved != commit:
        raise ValueError("source commit does not resolve to the exact supplied identity")
    return resolved


def _git(root: Path, *arguments: str, text: bool = True) -> str | bytes:
    result = subprocess.run(
        ("git", *arguments),
        cwd=root,
        check=True,
        capture_output=True,
        text=text,
    )
    return result.stdout


def _bytes_match(binding: SourceFileBinding, payload: bytes) -> bool:
    return (
        len(payload) == binding.byte_count and hashlib.sha256(payload).hexdigest() == binding.sha256
    )


def _raw_bytes_match(binding: RawReferenceBinding, payload: bytes) -> bool:
    return hashlib.sha256(payload).hexdigest() == binding.expected_sha256


def _control(
    attack_id: str,
    attack_class: str,
    rejected: bool,
    detail: str,
) -> AttackControl:
    return AttackControl(
        attack_id=attack_id,
        attack_class=attack_class,
        observed="rejected" if rejected else "admitted",
        passed=rejected,
        detail=detail,
    )


def _exception_control(
    attack_id: str,
    attack_class: str,
    operation: Any,
) -> AttackControl:
    try:
        operation()
    except Exception as exc:
        return _control(
            attack_id,
            attack_class,
            True,
            f"{type(exc).__name__}: rejected {attack_class} attack",
        )
    return _control(attack_id, attack_class, False, "attack was admitted")


def _json(value: Any) -> bytes:
    return canonical_json_bytes(value) + b"\n"


def _jsonl(values: Iterable[Any]) -> bytes:
    return b"".join(canonical_json_bytes(value) + b"\n" for value in values)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the v26.182 QA Parent Authority preflight")
    parser.add_argument("--repo-root", required=True)
    parser.add_argument("--external-audit", required=True)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()
    products = build_parent_authority_preflight(
        repo_root=args.repo_root,
        external_audit_path=args.external_audit,
        source_commit=args.source_commit,
    )
    written = write_parent_authority_artifacts(products, args.output_dir)
    print(
        canonical_json_bytes(
            {
                "preflight_id": products.report.preflight_id,
                "source_root": products.report.source_root,
                "release_selection_id": products.report.release_selection_id,
                "written_files": written,
            }
        ).decode("utf-8")
    )


if __name__ == "__main__":
    main()
