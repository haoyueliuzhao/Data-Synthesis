from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

import pytest

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
from trusted_synthesis.domains.finance.operations import finance_vnext_operation_registry
from trusted_synthesis.experiments.qa_generator_source_authority.depth import (
    DEPTH_ATTACK_NAMES,
    DepthMetricProducts,
    build_depth_metric_audit,
)
from trusted_synthesis.experiments.qa_generator_source_authority.models import (
    EXTERNAL_AUDIT_BYTE_COUNT,
    EXTERNAL_AUDIT_SHA256,
    GENERATOR_SOURCE_PATHS,
    NEXT_STAGE,
    OPERATOR_DIRECTIVE,
    OPERATOR_DIRECTIVE_BYTE_COUNT,
    OPERATOR_DIRECTIVE_SHA256,
    PREDECESSOR_ARTIFACT_ROOT,
    PREDECESSOR_MANIFEST_ID,
    REPAIR_IMPLEMENTATION_PATHS,
    SOURCE_ATTACK_NAMES,
    QAGeneratorSourceAuthorityProducts,
)
from trusted_synthesis.experiments.qa_generator_source_authority.preflight import (
    build_git_source_authority,
    build_qa_generator_source_authority_repair,
    validate_git_source_authority,
    write_qa_generator_source_authority_artifacts,
)
from trusted_synthesis.experiments.qa_generator_totality import preflight as legacy

ROOT = Path(__file__).resolve().parents[2]
AUDIT = Path(
    "/home/zhuxinrui/.codex/attachments/e69d0fda-1dee-45c5-ba68-79312141065c/pasted-text.txt"
)
LEGACY_AUDIT = Path(
    "/home/zhuxinrui/.codex/attachments/5fb1202b-02c2-4041-a76a-2613d9bf9c3e/pasted-text.txt"
)


@pytest.fixture(scope="module")
def depth_products() -> DepthMetricProducts:
    products = legacy.build_qa_generator_totality_preflight(
        repo_root=ROOT,
        external_audit_path=LEGACY_AUDIT,
        source_commit="0" * 40,
        source_tree="1" * 40,
    )
    return build_depth_metric_audit(
        executions=products.executions,
        trajectories=products.trajectories,
        registry=finance_vnext_operation_registry(),
    )


def _git(*arguments: str) -> str:
    return subprocess.run(
        ("git", "-C", str(ROOT), *arguments),
        check=True,
        stdout=subprocess.PIPE,
        text=True,
    ).stdout.strip()


@pytest.fixture(scope="module")
def products() -> QAGeneratorSourceAuthorityProducts:
    commit = _git("rev-parse", "HEAD")
    tree = _git("rev-parse", "HEAD^{tree}")
    return build_qa_generator_source_authority_repair(
        repo_root=ROOT,
        external_audit_path=AUDIT,
        source_commit=commit,
        source_tree=tree,
    )


def _files(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file()
    }


def _evidence(ref_id: str, selector: str | None = None) -> ProgramInputRef:
    return ProgramInputRef(kind=InputRefKind.EVIDENCE, ref_id=ref_id, selector=selector)


def _operation(ref_id: str, selector: str | None = None) -> ProgramInputRef:
    return ProgramInputRef(kind=InputRefKind.OPERATION, ref_id=ref_id, selector=selector)


def _lookup(node_id: str, evidence_id: str) -> OperationNode:
    return OperationNode(
        node_id=node_id,
        operator_id="lookup",
        input_refs=(_evidence(evidence_id),),
        output_schema="payload",
        verifier_id="lookup_verifier",
    )


def _growth(node_id: str, left: str, right: str) -> OperationNode:
    return OperationNode(
        node_id=node_id,
        operator_id="growth",
        input_refs=(
            _operation(left, "payload.value"),
            _operation(right, "payload.value"),
        ),
        dependencies=(left, right),
        output_schema="percentage",
        verifier_id="growth_verifier",
    )


def _compare_from_operations(node_id: str, left: str, right: str) -> OperationNode:
    return OperationNode(
        node_id=node_id,
        operator_id="compare",
        input_refs=(_operation(left, "value"), _operation(right, "value")),
        dependencies=(left, right),
        output_schema="comparison",
        verifier_id="compare_verifier",
    )


def _derived_growth_program() -> TaskProgram:
    nodes = (
        _lookup("left_earlier", "evidence:left_earlier"),
        _lookup("left_later", "evidence:left_later"),
        _lookup("right_earlier", "evidence:right_earlier"),
        _lookup("right_later", "evidence:right_later"),
        _growth("left_growth", "left_earlier", "left_later"),
        _growth("right_growth", "right_earlier", "right_later"),
        _compare_from_operations("result", "left_growth", "right_growth"),
    )
    return make_program(nodes, "result")


def test_legacy_source_binding_directly_accepts_fake_commit_and_unrelated_tree() -> None:
    binding = legacy._source_binding(  # noqa: SLF001
        ROOT,
        "legacy-counterexample-authorization",
        "0" * 40,
        "1" * 40,
    )
    assert binding.source_commit == "0" * 40
    assert binding.source_tree == "1" * 40
    assert binding.finance_numeric_candidate_v7_source_bound is True
    assert binding.registered_catalog_totalized is True


def test_four_depth_metrics_are_noninterchangeable_and_registry_derived() -> None:
    registry = finance_vnext_operation_registry()
    deep = derive_program_depth_metrics(_derived_growth_program(), registry)
    assert deep.node_count == 7
    assert deep.structural_dependency_depth == 3
    assert deep.semantic_operation_depth == 2
    assert deep.workflow_interaction_depth == 4
    assert deep.transparent_projection_node_count == 4
    assert deep.semantic_operation_node_count == 3
    assert deep.output_ancestor_node_count == deep.node_count
    assert deep.plan_template_stage_counted is False
    assert deep.answer_template_stage_counted is False

    retrieval = derive_program_depth_metrics(
        make_program((_lookup("result", "evidence:fact"),), "result"), registry
    )
    assert (
        retrieval.node_count,
        retrieval.structural_dependency_depth,
        retrieval.semantic_operation_depth,
        retrieval.workflow_interaction_depth,
    ) == (1, 1, 0, 2)


def test_depth_attack_delete_required_semantic_dependency_rejects() -> None:
    program = _derived_growth_program()
    values = program.model_dump(mode="python", exclude={"program_id"})
    nodes = tuple(node for node in program.nodes if node.node_id != "left_growth")
    with pytest.raises(ValueError, match="topologically ordered"):
        TaskProgram(
            program_id=program.program_id,
            nodes=nodes,
            **{key: value for key, value in values.items() if key != "nodes"},
        )


def test_depth_attack_bypass_derived_semantic_chain_rejects() -> None:
    registry = finance_vnext_operation_registry()
    expected = _derived_growth_program()
    bypass = make_program(
        (
            OperationNode(
                node_id="result",
                operator_id="compare",
                input_refs=(
                    _evidence("evidence:left_later", "value"),
                    _evidence("evidence:right_later", "value"),
                ),
                output_schema="comparison",
                verifier_id="compare_verifier",
            ),
        ),
        "result",
    )
    bypass_metrics = derive_program_depth_metrics(bypass, registry)
    assert bypass_metrics.semantic_operation_depth == 1
    with pytest.raises(ValueError, match="exact source Program"):
        admit_program_depth_metrics(
            expected_program=expected,
            candidate_program=bypass,
            candidate_metrics=bypass_metrics,
            registry=registry,
        )


def test_depth_attack_irrelevant_lookup_inflation_rejects() -> None:
    registry = finance_vnext_operation_registry()
    expected = _derived_growth_program()
    inflated = make_program(
        (*expected.nodes[:-1], _lookup("irrelevant", "evidence:irrelevant"), expected.nodes[-1]),
        expected.output_node_id,
    )
    with pytest.raises(ValueError, match="outside output dependency closure"):
        derive_program_depth_metrics(inflated, registry)


def test_eight_fixture_depth_distributions_are_exact_and_shallow(
    depth_products: DepthMetricProducts,
) -> None:
    audit = depth_products.audit
    assert audit.node_count_distribution == {"1": 3, "3": 3, "4": 1, "7": 1}
    assert audit.structural_dependency_depth_distribution == {"1": 3, "2": 4, "3": 1}
    assert audit.semantic_operation_depth_distribution == {"0": 1, "1": 6, "2": 1}
    assert audit.workflow_interaction_depth_distribution == {"2": 1, "3": 6, "4": 1}
    assert audit.maximum_structural_dependency_depth == 3
    assert audit.maximum_semantic_operation_depth == 2
    assert audit.semantic_depth_three_plus_count == 0
    assert audit.schema_consistent is True
    assert audit.output_dependency_closed_count == 8
    assert audit.workflow_source_bound_count == 8

    fact = next(row for row in audit.rows if row.task_type == "fact_retrieval")
    assert fact.metrics.semantic_operation_depth == 0
    assert fact.metrics.workflow_interaction_depth == 2


def test_three_formal_depth_attacks_execute_and_reject(
    depth_products: DepthMetricProducts,
) -> None:
    audit = depth_products.negative_audit
    assert tuple(item.name for item in audit.controls) == DEPTH_ATTACK_NAMES
    assert (audit.attempted_count, audit.rejected_count, audit.accepted_count) == (3, 3, 0)
    assert audit.final_answer_retained_count == 3
    assert audit.output_write_count == audit.provider_calls == audit.gpu_jobs == 0
    assert tuple(item.rejection_stage for item in audit.controls) == (
        "exact_source_program_admission",
        "exact_source_program_admission",
        "output_dependency_closure",
    )
    assert all(item.rejected and item.final_answer_retained for item in audit.controls)
    assert all(item.reason_type == "ValueError" for item in audit.controls)


def test_repair_exact_scope_and_predecessor_freeze(
    products: QAGeneratorSourceAuthorityProducts,
) -> None:
    review = AUDIT.read_bytes()
    assert len(review) == EXTERNAL_AUDIT_BYTE_COUNT == 21_798
    assert hashlib.sha256(review).hexdigest() == EXTERNAL_AUDIT_SHA256
    assert products.external_review_bytes == review
    assert products.operator_directive_bytes == OPERATOR_DIRECTIVE.encode("utf-8")
    assert len(products.operator_directive_bytes) == OPERATOR_DIRECTIVE_BYTE_COUNT == 44
    assert hashlib.sha256(products.operator_directive_bytes).hexdigest() == (
        OPERATOR_DIRECTIVE_SHA256
    )
    assert products.authorization.provider_execution_authorized is False
    assert products.authorization.gpu_execution_authorized is False
    assert products.authorization.qa_release_authorized is False

    freeze = products.predecessor_freeze
    assert (freeze.file_count, freeze.total_byte_count) == (19, 449_574)
    assert (freeze.manifest_member_count, freeze.manifest_member_bytes) == (18, 446_741)
    assert freeze.manifest_id == PREDECESSOR_MANIFEST_ID
    assert freeze.artifact_root == PREDECESSOR_ARTIFACT_ROOT
    assert freeze.formal_bytes_modified is False


def test_generator_and_successor_implementation_are_exact_git_bound(
    products: QAGeneratorSourceAuthorityProducts,
) -> None:
    bindings = (
        (products.generator_source_binding, GENERATOR_SOURCE_PATHS),
        (products.repair_source_binding, REPAIR_IMPLEMENTATION_PATHS),
    )
    assert len(products.generator_source_binding.source_files) == 14
    assert len(products.repair_source_binding.source_files) == 5
    assert "trusted_data_synthesis/src/trusted_synthesis/core/task/program_depth.py" in (
        REPAIR_IMPLEMENTATION_PATHS
    )
    assert products.generator_source_binding.resolved_source_commit == (
        "dba5d949a743dd625e5fe0e10b0f4809ac9f87ad"
    )
    assert products.generator_source_binding.resolved_source_tree == (
        "d706531377e5303265cd2dcee3e355c6642c466b"
    )
    assert products.repair_source_binding.resolved_source_commit == _git("rev-parse", "HEAD")
    assert products.repair_source_binding.resolved_source_tree == _git("rev-parse", "HEAD^{tree}")
    for binding, paths in bindings:
        assert tuple(item.relative_path for item in binding.source_files) == paths
        assert binding.commit_tree_relation_verified is True
        assert binding.all_members_exist_at_commit is True
        assert binding.all_current_bytes_equal_committed_bytes is True
        validate_git_source_authority(repo_root=ROOT, binding=binding)
        for member in binding.source_files:
            committed = subprocess.run(
                (
                    "git",
                    "-C",
                    str(ROOT),
                    "show",
                    f"{binding.resolved_source_commit}:{member.relative_path}",
                ),
                check=True,
                stdout=subprocess.PIPE,
            ).stdout
            current = (ROOT / member.relative_path).read_bytes()
            assert committed == current
            assert member.committed_sha256 == hashlib.sha256(committed).hexdigest()
            assert member.current_sha256 == hashlib.sha256(current).hexdigest()
            assert member.committed_byte_count == member.current_byte_count == len(current)


def test_legacy_counterexample_and_five_new_source_attacks_are_executed(
    products: QAGeneratorSourceAuthorityProducts,
) -> None:
    legacy_audit = products.legacy_counterexample_audit
    assert legacy_audit.fake_source_commit == "0" * 40
    assert legacy_audit.unrelated_source_tree == "1" * 40
    assert legacy_audit.legacy_binding_constructed is True
    assert legacy_audit.legacy_g2_passed is True
    assert legacy_audit.new_authority_admission_rejected is True
    assert legacy_audit.rejection_stage == "git_commit_resolution"

    with pytest.raises(Exception, match="git rev-parse"):
        build_git_source_authority(
            repo_root=ROOT,
            authorization_id=products.authorization.authorization_id,
            authority_kind="generator_verifier",
            source_commit="0" * 40,
            source_tree="1" * 40,
        )

    audit = products.source_negative_audit
    assert tuple(item.name for item in audit.controls) == SOURCE_ATTACK_NAMES
    assert (audit.attempted_count, audit.rejected_count, audit.accepted_count) == (5, 5, 0)
    assert audit.output_write_count == audit.provider_calls == 0
    assert tuple(item.rejection_stage for item in audit.controls) == (
        "git_commit_resolution",
        "commit_tree_relation",
        "committed_member_bytes",
        "committed_member_bytes",
        "current_worktree_member_bytes",
    )
    assert all(item.rejected and item.exception_type != "None" for item in audit.controls)
    assert all(item.output_writes == item.provider_calls == 0 for item in audit.controls)


def test_main_build_retains_eight_fixed_fixtures_and_exact_depth_results(
    products: QAGeneratorSourceAuthorityProducts,
) -> None:
    retained = products.retained_fixture_audit
    assert tuple(row.task_type for row in retained.rows) == retained.registered_task_types
    assert (
        retained.registered_task_count,
        retained.generator_success_count,
        retained.exact_program_execution_count,
        retained.exact_operation_correctness_count,
        retained.answer_schema_correct_count,
        retained.answer_correct_count,
        retained.citation_correct_count,
        retained.evaluator_accepted_count,
    ) == (8, 8, 8, 8, 8, 8, 8, 8)
    assert retained.insufficient_capability_count == 0
    assert retained.deterministic_fixture_constructibility_only is True
    assert retained.archive_grounding_claimed is False
    assert retained.realistic_difficulty_claimed is False
    assert len(products.bundles) == len(products.executions) == len(products.assessments) == 8

    assert products.depth_metric_audit.node_count_distribution == {
        "1": 3,
        "3": 3,
        "4": 1,
        "7": 1,
    }
    assert products.depth_metric_audit.semantic_operation_depth_distribution == {
        "0": 1,
        "1": 6,
        "2": 1,
    }
    assert products.depth_metric_audit.semantic_depth_three_plus_count == 0
    assert products.depth_contract.legacy_program_depth_authoritative is False
    assert products.depth_contract.legacy_semantic_only_depth_authoritative is False
    assert products.depth_negative_audit.rejected_count == 3


def test_report_scope_and_transition_remain_offline(
    products: QAGeneratorSourceAuthorityProducts,
) -> None:
    report = products.report
    scope = products.scope_audit
    assert report.passed_count == 8 and report.failed_count == 0
    assert len(report.gates) == 8 and all(report.gates.values())
    assert report.next_stage == NEXT_STAGE
    assert report.provider_execution_authorized is False
    assert report.gpu_execution_authorized is False
    assert report.qa_release_authorized is False
    assert report.archive_grounding_claimed is False
    assert report.semantic_depth_three_plus_claimed is False
    assert report.realistic_difficulty_claimed is False
    assert not any(
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
    )


def test_writer_two_empty_directories_are_byte_identical_and_self_excluding(
    products: QAGeneratorSourceAuthorityProducts,
    tmp_path: Path,
) -> None:
    left = tmp_path / "left"
    right = tmp_path / "right"
    write_qa_generator_source_authority_artifacts(products, left)
    write_qa_generator_source_authority_artifacts(products, right)
    assert _files(left) == _files(right)
    files = _files(left)
    assert len(files) == 24
    manifest = json.loads(files["artifact_manifest.json"])
    assert manifest["self_excluding"] is True
    assert manifest["file_count"] == len(manifest["members"]) == len(files) - 1 == 23
    assert "artifact_manifest.json" not in {item["relative_path"] for item in manifest["members"]}
    for member in manifest["members"]:
        payload = files[member["relative_path"]]
        assert member["byte_count"] == len(payload)
        assert member["sha256"] == hashlib.sha256(payload).hexdigest()
    assert files["external_review.txt"] == AUDIT.read_bytes()
    assert files["operator_directive.txt"] == OPERATOR_DIRECTIVE.encode("utf-8")
    transition = json.loads(files["transition.json"])
    assert transition["next_stage"] == NEXT_STAGE
    assert transition["provider_execution_authorized"] is False
    assert transition["gpu_execution_authorized"] is False
    assert transition["qa_release_authorized"] is False
