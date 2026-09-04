from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

from trusted_synthesis.canonical_json import canonical_json_bytes, strict_canonical_hash
from trusted_synthesis.core.evaluation.evaluator import CandidateQualityEvaluator
from trusted_synthesis.core.evaluation.schema import ReleaseDecision
from trusted_synthesis.core.evidence.corpus import EvidenceCorpus
from trusted_synthesis.core.graph.builder import ProofGraphBuilder
from trusted_synthesis.core.immutable_artifacts import write_immutable_artifact_directory
from trusted_synthesis.core.trajectory.candidate_verifier import CandidateWorkflowVerifier
from trusted_synthesis.domains.finance.operations import finance_vnext_operation_registry
from trusted_synthesis.domains.finance.policy import FinanceSemanticPolicy
from trusted_synthesis.domains.finance.tasks import FinanceTaskPlugin
from trusted_synthesis.experiments.qa_generator_totality import preflight as predecessor
from trusted_synthesis.runtime.tools import InMemoryEvidenceToolRuntime

from . import models
from .depth import build_depth_metric_audit


class GitSourceAuthorityError(RuntimeError):
    def __init__(self, stage: str, message: str) -> None:
        super().__init__(message)
        self.stage = stage


def _git_bytes(repo_root: Path, stage: str, *arguments: str) -> bytes:
    result = subprocess.run(
        ("git", "-C", str(repo_root), *arguments),
        check=False,
        capture_output=True,
    )
    if result.returncode:
        detail = result.stderr.decode("utf-8", errors="replace").strip()
        raise GitSourceAuthorityError(stage, f"git {' '.join(arguments)} failed: {detail}")
    return result.stdout


def _git_text(repo_root: Path, stage: str, *arguments: str) -> str:
    return _git_bytes(repo_root, stage, *arguments).decode("ascii").strip()


def _source_paths(authority_kind: str) -> tuple[str, ...]:
    if authority_kind == "generator_verifier":
        return models.GENERATOR_SOURCE_PATHS
    if authority_kind == "repair_implementation":
        return models.REPAIR_IMPLEMENTATION_PATHS
    raise GitSourceAuthorityError("source_domain", f"unknown authority kind: {authority_kind}")


def _source_member(
    *,
    relative_path: str,
    blob_oid: str,
    committed: bytes,
    current: bytes,
) -> models.SourceMemberBinding:
    if current != committed:
        raise GitSourceAuthorityError(
            "current_worktree_member_bytes",
            f"current source bytes differ from committed bytes: {relative_path}",
        )
    return models.SourceMemberBinding(
        relative_path=relative_path,
        git_blob_oid=blob_oid,
        committed_sha256=hashlib.sha256(committed).hexdigest(),
        committed_byte_count=len(committed),
        current_sha256=hashlib.sha256(current).hexdigest(),
        current_byte_count=len(current),
    )


def _binding_from_members(
    *,
    authorization_id: str,
    authority_kind: str,
    source_commit: str,
    source_tree: str,
    members: tuple[models.SourceMemberBinding, ...],
) -> models.AuthoritativeSourceBinding:
    rows = tuple(item.model_dump(mode="json") for item in members)
    return models.identified(
        models.AuthoritativeSourceBinding,
        {
            "authorization_id": authorization_id,
            "authority_kind": authority_kind,
            "requested_source_commit": source_commit,
            "resolved_source_commit": source_commit,
            "requested_source_tree": source_tree,
            "resolved_source_tree": source_tree,
            "source_files": members,
            "source_path_set_sha256": hashlib.sha256(
                canonical_json_bytes(_source_paths(authority_kind))
            ).hexdigest(),
            "source_file_set_sha256": hashlib.sha256(canonical_json_bytes(rows)).hexdigest(),
        },
        "binding_id",
        "qa_generator_authoritative_source_binding:",
    )


def build_git_source_authority(
    *,
    repo_root: Path,
    authorization_id: str,
    authority_kind: str,
    source_commit: str,
    source_tree: str,
) -> models.AuthoritativeSourceBinding:
    """Bind actual Git commit/tree members and require current execution bytes to match."""

    root = repo_root.resolve()
    resolved = _git_text(root, "git_commit_resolution", "rev-parse", f"{source_commit}^{{commit}}")
    if resolved != source_commit:
        raise GitSourceAuthorityError(
            "git_commit_resolution", "source commit is not the exact resolved commit identity"
        )
    object_type = _git_text(root, "git_commit_resolution", "cat-file", "-t", resolved)
    if object_type != "commit":
        raise GitSourceAuthorityError("git_commit_resolution", "source object is not a commit")
    resolved_tree = _git_text(root, "commit_tree_relation", "rev-parse", f"{resolved}^{{tree}}")
    if resolved_tree != source_tree:
        raise GitSourceAuthorityError(
            "commit_tree_relation", "source tree differs from git rev-parse commit^{tree}"
        )
    members: list[models.SourceMemberBinding] = []
    for relative_path in _source_paths(authority_kind):
        blob_oid = _git_text(
            root,
            "committed_member_resolution",
            "rev-parse",
            f"{resolved}:{relative_path}",
        )
        committed = _git_bytes(
            root, "committed_member_resolution", "show", f"{resolved}:{relative_path}"
        )
        current_path = root / relative_path
        if not current_path.is_file():
            raise GitSourceAuthorityError(
                "current_worktree_member_bytes", f"current source member is absent: {relative_path}"
            )
        members.append(
            _source_member(
                relative_path=relative_path,
                blob_oid=blob_oid,
                committed=committed,
                current=current_path.read_bytes(),
            )
        )
    binding = _binding_from_members(
        authorization_id=authorization_id,
        authority_kind=authority_kind,
        source_commit=resolved,
        source_tree=resolved_tree,
        members=tuple(members),
    )
    validate_git_source_authority(repo_root=root, binding=binding)
    return binding


def validate_git_source_authority(
    *,
    repo_root: Path,
    binding: models.AuthoritativeSourceBinding,
    current_overrides: Mapping[str, bytes] | None = None,
) -> None:
    """Reread Git and the worktree; candidate hashes never serve as their own authority."""

    root = repo_root.resolve()
    resolved = _git_text(
        root,
        "git_commit_resolution",
        "rev-parse",
        f"{binding.requested_source_commit}^{{commit}}",
    )
    if resolved != binding.resolved_source_commit:
        raise GitSourceAuthorityError(
            "git_commit_resolution", "candidate commit resolution differs"
        )
    resolved_tree = _git_text(root, "commit_tree_relation", "rev-parse", f"{resolved}^{{tree}}")
    if (
        resolved_tree != binding.requested_source_tree
        or resolved_tree != binding.resolved_source_tree
    ):
        raise GitSourceAuthorityError(
            "commit_tree_relation", "candidate commit/tree relation differs"
        )
    expected_paths = _source_paths(binding.authority_kind)
    if tuple(item.relative_path for item in binding.source_files) != expected_paths:
        raise GitSourceAuthorityError(
            "source_member_domain", "candidate source member paths differ"
        )
    override = current_overrides or {}
    if set(override) - set(expected_paths):
        raise GitSourceAuthorityError(
            "source_member_domain", "current override path is outside domain"
        )
    for row in binding.source_files:
        committed = _git_bytes(
            root,
            "committed_member_resolution",
            "show",
            f"{resolved}:{row.relative_path}",
        )
        blob_oid = _git_text(
            root,
            "committed_member_resolution",
            "rev-parse",
            f"{resolved}:{row.relative_path}",
        )
        if (
            row.git_blob_oid != blob_oid
            or row.committed_sha256 != hashlib.sha256(committed).hexdigest()
            or row.committed_byte_count != len(committed)
        ):
            raise GitSourceAuthorityError(
                "committed_member_bytes",
                f"candidate committed source member differs from Git: {row.relative_path}",
            )
        current_path = root / row.relative_path
        if not current_path.is_file() and row.relative_path not in override:
            raise GitSourceAuthorityError(
                "current_worktree_member_bytes",
                f"current source member is absent: {row.relative_path}",
            )
        current = override.get(row.relative_path, current_path.read_bytes())
        if (
            current != committed
            or row.current_sha256 != hashlib.sha256(current).hexdigest()
            or row.current_byte_count != len(current)
        ):
            raise GitSourceAuthorityError(
                "current_worktree_member_bytes",
                f"candidate current source member differs from Git commit: {row.relative_path}",
            )


def _directory_files(directory: Path) -> dict[str, bytes]:
    return {
        path.relative_to(directory).as_posix(): path.read_bytes()
        for path in directory.rglob("*")
        if path.is_file()
    }


def _freeze_predecessor(
    repo_root: Path, authorization_id: str
) -> tuple[models.PredecessorFreeze, dict[str, Any]]:
    directory = repo_root / models.PREDECESSOR_DIRECTORY
    files = _directory_files(directory)
    if len(files) != 19 or sum(map(len, files.values())) != 449_574:
        raise ValueError("QA totality predecessor directory geometry differs")
    manifest = json.loads(files["artifact_manifest.json"])
    members = manifest.get("members")
    if not isinstance(members, list):
        raise ValueError("QA totality predecessor Manifest lacks members")
    by_path = {str(item["relative_path"]): item for item in members}
    if set(by_path) != set(files) - {"artifact_manifest.json"}:
        raise ValueError("QA totality predecessor Manifest member set differs")
    for relative_path, item in by_path.items():
        payload = files[relative_path]
        if (
            int(item["byte_count"]) != len(payload)
            or str(item["sha256"]) != hashlib.sha256(payload).hexdigest()
        ):
            raise ValueError(f"QA totality predecessor member bytes differ: {relative_path}")
    report = json.loads(files["report.json"])
    transition = json.loads(files["transition.json"])
    manifest_body = {key: value for key, value in manifest.items() if key != "manifest_id"}
    recomputed_root = strict_canonical_hash(
        tuple(members), prefix="qa_generator_totality_artifact_root:"
    )
    recomputed_manifest_id = strict_canonical_hash(
        manifest_body, prefix="qa_generator_totality_artifact_manifest:"
    )
    if (
        len(members) != 18
        or int(manifest.get("member_bytes", -1)) != 446_741
        or manifest.get("manifest_id") != recomputed_manifest_id
        or recomputed_manifest_id != models.PREDECESSOR_MANIFEST_ID
        or manifest.get("artifact_root") != recomputed_root
        or recomputed_root != models.PREDECESSOR_ARTIFACT_ROOT
        or report.get("report_id") != models.PREDECESSOR_REPORT_ID
        or transition.get("transition_id") != models.PREDECESSOR_TRANSITION_ID
    ):
        raise ValueError("QA totality predecessor identities differ")
    source_binding = json.loads(files["source_binding.json"])
    freeze = models.identified(
        models.PredecessorFreeze,
        {"authorization_id": authorization_id},
        "freeze_id",
        "qa_generator_source_authority_predecessor_freeze:",
    )
    return freeze, source_binding


def _require_predecessor_member_claims(
    source_binding: Mapping[str, Any], repaired: models.AuthoritativeSourceBinding
) -> None:
    claimed = source_binding.get("source_files")
    if not isinstance(claimed, list) or len(claimed) != len(repaired.source_files):
        raise ValueError("predecessor source member claims differ")
    for old, new in zip(claimed, repaired.source_files, strict=True):
        if (
            old.get("relative_path") != new.relative_path
            or old.get("sha256") != new.committed_sha256
            or int(old.get("byte_count", -1)) != new.committed_byte_count
        ):
            raise ValueError("repaired Git member differs from predecessor source claim")


def _legacy_counterexample(
    *, repo_root: Path, authorization_id: str
) -> models.LegacySourceCounterexampleAudit:
    legacy = predecessor._source_binding(
        repo_root,
        authorization_id,
        "0" * 40,
        "1" * 40,
    )
    new_rejected = False
    caught: Exception | None = None
    try:
        build_git_source_authority(
            repo_root=repo_root,
            authorization_id=authorization_id,
            authority_kind="generator_verifier",
            source_commit="0" * 40,
            source_tree="1" * 40,
        )
    except Exception as exc:  # exact failure is recorded below
        caught = exc
        new_rejected = True
    if not new_rejected or caught is None:
        raise ValueError("new Git source authority accepted the legacy fake-label counterexample")
    stage = getattr(caught, "stage", "git_commit_resolution")
    if stage != "git_commit_resolution":
        raise ValueError("legacy fake-label counterexample rejected at an unexpected stage")
    return models.identified(
        models.LegacySourceCounterexampleAudit,
        {
            "authorization_id": authorization_id,
            "legacy_binding_id": legacy.binding_id,
            "exception_type": type(caught).__name__,
            "reason_sha256": hashlib.sha256(str(caught).encode("utf-8")).hexdigest(),
        },
        "audit_id",
        "qa_generator_legacy_source_counterexample_audit:",
    )


def _mutated_binding(
    binding: models.AuthoritativeSourceBinding,
    members: Sequence[models.SourceMemberBinding],
) -> models.AuthoritativeSourceBinding:
    return _binding_from_members(
        authorization_id=binding.authorization_id,
        authority_kind=binding.authority_kind,
        source_commit=binding.resolved_source_commit,
        source_tree=binding.resolved_source_tree,
        members=tuple(members),
    )


def _control(name: str, operation: Callable[[], object]) -> models.SourceAuthorityNegativeControl:
    caught: Exception | None = None
    try:
        operation()
    except Exception as exc:  # rejection evidence is materialized, never inferred
        caught = exc
    rejected = caught is not None
    return models.SourceAuthorityNegativeControl(
        name=name,
        rejected=rejected,
        rejection_stage=str(getattr(caught, "stage", "not_rejected")),
        exception_type=type(caught).__name__ if caught is not None else "None",
        reason_sha256=hashlib.sha256(
            (str(caught) if caught is not None else "accepted").encode("utf-8")
        ).hexdigest(),
    )


def _source_negative_audit(
    *,
    repo_root: Path,
    authorization_id: str,
    generator: models.AuthoritativeSourceBinding,
    repair: models.AuthoritativeSourceBinding,
) -> models.SourceAuthorityNegativeAudit:
    wrong_tree = ("0" if generator.resolved_source_tree[0] != "0" else "1") + (
        generator.resolved_source_tree[1:]
    )
    first = generator.source_files[0]
    changed = b"changed-source-member-control\n"
    changed_row = models.SourceMemberBinding(
        relative_path=first.relative_path,
        git_blob_oid=first.git_blob_oid,
        committed_sha256=hashlib.sha256(changed).hexdigest(),
        committed_byte_count=len(changed),
        current_sha256=hashlib.sha256(changed).hexdigest(),
        current_byte_count=len(changed),
    )
    changed_binding = _mutated_binding(generator, (changed_row, *generator.source_files[1:]))
    left, right = generator.source_files[:2]
    crossed_left = models.SourceMemberBinding(
        relative_path=left.relative_path,
        git_blob_oid=right.git_blob_oid,
        committed_sha256=right.committed_sha256,
        committed_byte_count=right.committed_byte_count,
        current_sha256=right.current_sha256,
        current_byte_count=right.current_byte_count,
    )
    crossed_right = models.SourceMemberBinding(
        relative_path=right.relative_path,
        git_blob_oid=left.git_blob_oid,
        committed_sha256=left.committed_sha256,
        committed_byte_count=left.committed_byte_count,
        current_sha256=left.current_sha256,
        current_byte_count=left.current_byte_count,
    )
    crossed_binding = _mutated_binding(
        generator, (crossed_left, crossed_right, *generator.source_files[2:])
    )
    uncommitted = (repo_root / repair.source_files[-1].relative_path).read_bytes() + (
        b"\n# uncommitted-worktree-control\n"
    )
    controls = (
        _control(
            "nonexistent_commit",
            lambda: build_git_source_authority(
                repo_root=repo_root,
                authorization_id=authorization_id,
                authority_kind="generator_verifier",
                source_commit="0" * 40,
                source_tree="1" * 40,
            ),
        ),
        _control(
            "real_commit_wrong_tree",
            lambda: build_git_source_authority(
                repo_root=repo_root,
                authorization_id=authorization_id,
                authority_kind="generator_verifier",
                source_commit=generator.resolved_source_commit,
                source_tree=wrong_tree,
            ),
        ),
        _control(
            "changed_source_member",
            lambda: validate_git_source_authority(repo_root=repo_root, binding=changed_binding),
        ),
        _control(
            "crossed_source_members",
            lambda: validate_git_source_authority(repo_root=repo_root, binding=crossed_binding),
        ),
        _control(
            "uncommitted_worktree_source",
            lambda: validate_git_source_authority(
                repo_root=repo_root,
                binding=repair,
                current_overrides={repair.source_files[-1].relative_path: uncommitted},
            ),
        ),
    )
    return models.identified(
        models.SourceAuthorityNegativeAudit,
        {
            "authorization_id": authorization_id,
            "generator_source_binding_id": generator.binding_id,
            "repair_source_binding_id": repair.binding_id,
            "controls": controls,
        },
        "audit_id",
        "qa_generator_source_authority_negative_audit:",
    )


def _run_retained_fixtures(
    *, authorization_id: str, generator_source_binding_id: str
) -> tuple[models.RetainedFixtureAudit, dict[str, tuple[Any, ...]]]:
    registry = finance_vnext_operation_registry()
    plugin = FinanceTaskPlugin()
    if tuple(sorted(plugin.task_family_ids)) != models.REGISTERED_TASK_TYPES:
        raise ValueError("registered Finance task catalog differs")
    workflow_verifier = CandidateWorkflowVerifier(
        registry=registry, semantic_policy=FinanceSemanticPolicy()
    )
    evaluator = CandidateQualityEvaluator(
        semantic_policy=FinanceSemanticPolicy(), workflow_verifier=workflow_verifier
    )
    bundles: list[Any] = []
    packages: list[Any] = []
    executions: list[Any] = []
    trajectories: list[Any] = []
    verification_reports: list[Any] = []
    assessments: list[Any] = []
    rows: list[models.RetainedFixtureRow] = []
    for task_type, bundle in predecessor._canonical_bundles():
        graph = ProofGraphBuilder().build(bundle)
        instantiation = plugin.compile_evidence_ids(
            task_type, graph, bundle, tuple(item.evidence_id for item in bundle.evidence)
        )
        compilation = plugin.realize_instantiation(instantiation, graph, bundle, max_realizations=1)
        if len(compilation.selected) != 1:
            raise ValueError("canonical registered fixture did not produce one package")
        realized = compilation.selected[0]
        corpus = EvidenceCorpus.from_bundle(bundle)
        generator = predecessor.FinanceNumericCandidateGeneratorTotality(
            realized=realized, corpus=corpus, registry=registry
        )
        trajectory = generator.generate(realized.task.public, InMemoryEvidenceToolRuntime(corpus))
        execution = generator.last_execution
        if execution is None:
            raise ValueError("registered fixture omitted public Program execution")
        verification = workflow_verifier.verify(realized.task, corpus, graph, trajectory)
        assessment = evaluator.evaluate(realized.task, corpus, graph, trajectory)
        checks = {item.check_id: item.passed for item in verification.checks}
        if not verification.passed or assessment.decision != ReleaseDecision.ACCEPTED:
            raise ValueError(
                "registered fixed fixture did not retain verifier/evaluator acceptance"
            )
        row = models.identified(
            models.RetainedFixtureRow,
            {
                "generator_source_binding_id": generator_source_binding_id,
                "task_type": task_type,
                "evidence_bundle_id": bundle.bundle_id,
                "realized_package_id": realized.realized_package_id,
                "trajectory_id": trajectory.trajectory_id,
                "public_plan_execution_id": execution.execution_id,
                "program_node_count": execution.actual_node_count,
                "structural_dependency_depth": execution.maximum_dependency_depth,
                "executed_node_count": verification.executed_program_node_count,
                "independently_replayed_node_count": execution.independently_replayed_node_count,
                "operation_correct": checks.get("operation_correctness", False),
                "answer_schema_correct": checks.get("answer_schema_validity", False),
                "answer_correct": checks.get("answer_correctness", False),
                "citation_correct": checks.get("citation_binding", False),
                "evaluator_accepted": assessment.decision == ReleaseDecision.ACCEPTED,
            },
            "row_id",
            "qa_generator_source_authority_retained_fixture_row:",
        )
        bundles.append(bundle)
        packages.append(realized)
        executions.append(execution)
        trajectories.append(trajectory)
        verification_reports.append(verification)
        assessments.append(assessment)
        rows.append(row)
    audit = models.identified(
        models.RetainedFixtureAudit,
        {
            "authorization_id": authorization_id,
            "generator_source_binding_id": generator_source_binding_id,
            "rows": tuple(rows),
        },
        "audit_id",
        "qa_generator_source_authority_retained_fixture_audit:",
    )
    return audit, {
        "bundles": tuple(bundles),
        "packages": tuple(packages),
        "executions": tuple(executions),
        "trajectories": tuple(trajectories),
        "verification_reports": tuple(verification_reports),
        "assessments": tuple(assessments),
        "registry": registry,
    }


def _depth_gate(depth_products: Any) -> bool:
    audit = depth_products.audit
    negative = depth_products.negative_audit
    schema_consistent = bool(
        getattr(audit, "schema_consistent", getattr(audit, "depth_schema_consistent", False))
    )
    return (
        schema_consistent
        and int(negative.rejected_count) == 3
        and int(negative.accepted_count) == 0
    )


def build_qa_generator_source_authority_repair(
    *,
    repo_root: Path,
    external_audit_path: Path,
    source_commit: str,
    source_tree: str,
) -> models.QAGeneratorSourceAuthorityProducts:
    root = repo_root.resolve()
    review = external_audit_path.read_bytes()
    if (
        len(review) != models.EXTERNAL_AUDIT_BYTE_COUNT
        or hashlib.sha256(review).hexdigest() != models.EXTERNAL_AUDIT_SHA256
    ):
        raise ValueError("external QA source-authority audit bytes differ")
    directive = models.OPERATOR_DIRECTIVE.encode("utf-8")
    if (
        len(directive) != models.OPERATOR_DIRECTIVE_BYTE_COUNT
        or hashlib.sha256(directive).hexdigest() != models.OPERATOR_DIRECTIVE_SHA256
    ):
        raise ValueError("QA source-authority operator directive bytes differ")
    authorization = models.identified(
        models.SourceAuthorityAuthorization,
        {},
        "authorization_id",
        "qa_generator_source_authority_authorization:",
    )
    predecessor_freeze, old_source = _freeze_predecessor(root, authorization.authorization_id)
    generator_binding = build_git_source_authority(
        repo_root=root,
        authorization_id=authorization.authorization_id,
        authority_kind="generator_verifier",
        source_commit=str(old_source["source_commit"]),
        source_tree=str(old_source["source_tree"]),
    )
    _require_predecessor_member_claims(old_source, generator_binding)
    repair_binding = build_git_source_authority(
        repo_root=root,
        authorization_id=authorization.authorization_id,
        authority_kind="repair_implementation",
        source_commit=source_commit,
        source_tree=source_tree,
    )
    validate_git_source_authority(repo_root=root, binding=generator_binding)
    validate_git_source_authority(repo_root=root, binding=repair_binding)
    legacy = _legacy_counterexample(repo_root=root, authorization_id=authorization.authorization_id)
    source_negative = _source_negative_audit(
        repo_root=root,
        authorization_id=authorization.authorization_id,
        generator=generator_binding,
        repair=repair_binding,
    )
    retained, fixture = _run_retained_fixtures(
        authorization_id=authorization.authorization_id,
        generator_source_binding_id=generator_binding.binding_id,
    )
    depth_products = build_depth_metric_audit(
        executions=fixture["executions"],
        trajectories=fixture["trajectories"],
        registry=fixture["registry"],
    )
    if not _depth_gate(depth_products):
        raise ValueError("depth metric Contract or its three negative controls did not close")
    depth_contract_id = str(depth_products.contract.contract_id)
    depth_audit_id = str(depth_products.audit.audit_id)
    depth_negative_id = str(depth_products.negative_audit.audit_id)
    scope = models.identified(
        models.SourceAuthorityScopeAudit,
        {
            "authorization_id": authorization.authorization_id,
            "generator_source_binding_id": generator_binding.binding_id,
            "repair_source_binding_id": repair_binding.binding_id,
            "retained_fixture_audit_id": retained.audit_id,
            "depth_metric_audit_id": depth_audit_id,
            "depth_negative_audit_id": depth_negative_id,
        },
        "audit_id",
        "qa_generator_source_authority_scope_audit:",
    )
    gates = {
        "G0_exact_external_scope": True,
        "G1_predecessor_formal_directory_frozen": predecessor_freeze.formal_bytes_modified is False,
        "G2_exact_git_commit_tree_and_member_authority": (
            len(generator_binding.source_files) == len(models.GENERATOR_SOURCE_PATHS)
            and len(repair_binding.source_files) == len(models.REPAIR_IMPLEMENTATION_PATHS)
            and all(item.bytes_equal for item in generator_binding.source_files)
            and all(item.bytes_equal for item in repair_binding.source_files)
        ),
        "G3_four_depth_metrics_and_legacy_fields_non_authoritative": (
            depth_products.audit.schema_consistent
            and depth_products.audit.maximum_semantic_operation_depth == 2
            and depth_products.audit.semantic_depth_three_plus_count == 0
            and not depth_products.contract.legacy_program_depth_authoritative
            and not depth_products.contract.legacy_semantic_only_depth_authoritative
        ),
        "G4_retained_fixed_fixture_totality_8_of_8": (
            retained.generator_success_count
            == retained.exact_program_execution_count
            == retained.exact_operation_correctness_count
            == retained.answer_correct_count
            == retained.citation_correct_count
            == retained.evaluator_accepted_count
            == 8
        ),
        "G5_legacy_counterexample_and_five_source_attacks_reject": (
            legacy.legacy_g2_passed
            and legacy.new_authority_admission_rejected
            and source_negative.rejected_count == 5
            and source_negative.accepted_count == 0
        ),
        "G6_three_depth_attacks_reject": (
            depth_products.negative_audit.rejected_count == 3
            and depth_products.negative_audit.accepted_count == 0
        ),
        "G7_zero_provider_gpu_online_release": not any(
            (
                scope.provider_calls,
                scope.credential_lookups,
                scope.gpu_jobs,
                scope.online_job_manifests,
                scope.empirical_rows,
                scope.qa_release_objects,
                scope.vtdo_rows,
                scope.training_rows,
                scope.production_rows,
            )
        ),
    }
    report = models.identified(
        models.SourceAuthorityRepairReport,
        {
            "authorization_id": authorization.authorization_id,
            "predecessor_freeze_id": predecessor_freeze.freeze_id,
            "generator_source_binding_id": generator_binding.binding_id,
            "repair_source_binding_id": repair_binding.binding_id,
            "legacy_counterexample_audit_id": legacy.audit_id,
            "source_negative_audit_id": source_negative.audit_id,
            "retained_fixture_audit_id": retained.audit_id,
            "depth_contract_id": depth_contract_id,
            "depth_metric_audit_id": depth_audit_id,
            "depth_negative_audit_id": depth_negative_id,
            "scope_audit_id": scope.audit_id,
            "gates": gates,
        },
        "report_id",
        "qa_generator_source_authority_repair_report:",
    )
    return models.QAGeneratorSourceAuthorityProducts(
        authorization=authorization,
        external_review_bytes=review,
        operator_directive_bytes=directive,
        predecessor_freeze=predecessor_freeze,
        generator_source_binding=generator_binding,
        repair_source_binding=repair_binding,
        legacy_counterexample_audit=legacy,
        source_negative_audit=source_negative,
        retained_fixture_audit=retained,
        depth_contract=depth_products.contract,
        depth_metric_audit=depth_products.audit,
        depth_negative_audit=depth_products.negative_audit,
        scope_audit=scope,
        report=report,
        bundles=fixture["bundles"],
        realized_packages=fixture["packages"],
        executions=fixture["executions"],
        trajectories=fixture["trajectories"],
        verification_reports=fixture["verification_reports"],
        assessments=fixture["assessments"],
    )


def _jsonl(values: Sequence[Any]) -> bytes:
    return b"".join(canonical_json_bytes(item) + b"\n" for item in values)


def write_qa_generator_source_authority_artifacts(
    products: models.QAGeneratorSourceAuthorityProducts, output_dir: Path
) -> tuple[str, ...]:
    gate = {
        "gate_id": strict_canonical_hash(
            products.report.gates, prefix="qa_generator_source_authority_gate:"
        ),
        "passed": products.report.passed_count,
        "failed": products.report.failed_count,
        "noncompensatory": True,
        "gates": products.report.gates,
    }
    transition_body = {
        "report_id": products.report.report_id,
        "next_stage": models.NEXT_STAGE,
        "provider_execution_authorized": False,
        "gpu_execution_authorized": False,
        "qa_release_authorized": False,
    }
    transition = {
        "transition_id": strict_canonical_hash(
            transition_body, prefix="qa_generator_source_authority_transition:"
        ),
        **transition_body,
    }
    payloads = {
        "authorization.json": canonical_json_bytes(products.authorization) + b"\n",
        "depth_metric_audit.json": canonical_json_bytes(products.depth_metric_audit) + b"\n",
        "depth_metric_contract.json": canonical_json_bytes(products.depth_contract) + b"\n",
        "depth_negative_control_audit.json": canonical_json_bytes(products.depth_negative_audit)
        + b"\n",
        "evidence_bundles.jsonl": _jsonl(products.bundles),
        "external_review.txt": products.external_review_bytes,
        "gate_evaluation.json": canonical_json_bytes(gate) + b"\n",
        "generator_source_binding.json": canonical_json_bytes(products.generator_source_binding)
        + b"\n",
        "legacy_source_counterexample_audit.json": canonical_json_bytes(
            products.legacy_counterexample_audit
        )
        + b"\n",
        "operator_directive.txt": products.operator_directive_bytes,
        "predecessor_freeze.json": canonical_json_bytes(products.predecessor_freeze) + b"\n",
        "program_executions.jsonl": _jsonl(products.executions),
        "quality_assessments.jsonl": _jsonl(products.assessments),
        "realized_task_packages.jsonl": _jsonl(products.realized_packages),
        "repair_implementation_source_binding.json": canonical_json_bytes(
            products.repair_source_binding
        )
        + b"\n",
        "report.json": canonical_json_bytes(products.report) + b"\n",
        "retained_fixture_audit.json": canonical_json_bytes(products.retained_fixture_audit)
        + b"\n",
        "retained_fixture_rows.jsonl": _jsonl(products.retained_fixture_audit.rows),
        "scope_boundary_audit.json": canonical_json_bytes(products.scope_audit) + b"\n",
        "source_negative_control_audit.json": canonical_json_bytes(products.source_negative_audit)
        + b"\n",
        "trajectories.jsonl": _jsonl(products.trajectories),
        "transition.json": canonical_json_bytes(transition) + b"\n",
        "verification_reports.jsonl": _jsonl(products.verification_reports),
    }
    members: tuple[dict[str, Any], ...] = tuple(
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
        "member_bytes": sum(int(item["byte_count"]) for item in members),
        "artifact_root": strict_canonical_hash(
            members, prefix="qa_generator_source_authority_artifact_root:"
        ),
        "self_excluding": True,
        "schema_version": "qa_generator_source_authority_artifact_manifest.v1",
    }
    payloads["artifact_manifest.json"] = (
        canonical_json_bytes(
            {
                "manifest_id": strict_canonical_hash(
                    manifest_body, prefix="qa_generator_source_authority_artifact_manifest:"
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
    args = parser.parse_args()
    products = build_qa_generator_source_authority_repair(
        repo_root=args.repo_root,
        external_audit_path=args.external_audit,
        source_commit=args.source_commit,
        source_tree=args.source_tree,
    )
    write_qa_generator_source_authority_artifacts(products, args.output_dir)


if __name__ == "__main__":
    main()
