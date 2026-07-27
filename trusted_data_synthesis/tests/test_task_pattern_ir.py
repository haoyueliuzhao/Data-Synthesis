from __future__ import annotations

import json

import pytest

from trusted_synthesis.core.evaluation.contracts import QualityContractCompiler
from trusted_synthesis.core.synthesis import ProofCarryingSampleCompiler
from trusted_synthesis.core.task.binding import make_evidence_binding
from trusted_synthesis.core.task.pattern import TaskPatternSpec
from trusted_synthesis.core.task.pattern_compiler import TaskPatternCompiler
from trusted_synthesis.domains.legal.operations import legal_operation_registry
from trusted_synthesis.domains.legal.pattern_runtime import LegalTaskPatternRuntime
from trusted_synthesis.domains.legal.patterns import LEGAL_RULE_APPLICATION_PATTERN
from trusted_synthesis.experiments.counterfactual_finance_fixture import (
    build_finance_counterfactual_cases,
)
from trusted_synthesis.experiments.cross_domain_contract_suite.fixtures import (
    build_contract_cases,
    build_pattern_validation_cases,
)


def test_domain_plugins_compile_declarative_pattern_and_binding_identity() -> None:
    legal, science = build_contract_cases()

    legal_pattern = legal.task.public.metadata["task_pattern"]
    legal_binding = legal.task.oracle.selection_contract["pattern_binding"]
    assert legal_pattern["pattern_id"] == "legal.rule_application"
    assert legal_pattern["compiler_version"] == "task_pattern_compiler.v1"
    assert legal_binding["role_bindings"]["rules"] == legal.task.oracle.gold_evidence_ids
    assert [node.node_id for node in legal.task.oracle.task_program.nodes] == [
        "apply_1",
        "apply_2",
        "result",
    ]

    science_pattern = science.task.public.metadata["task_pattern"]
    science_binding = science.task.oracle.selection_contract["pattern_binding"]
    assert science_pattern["pattern_id"] == "science.protocol_effect_comparison"
    assert science_binding["role_bindings"]["experiments"] == (
        science.task.oracle.gold_evidence_ids
    )
    assert [node.node_id for node in science.task.oracle.task_program.nodes] == [
        "align_protocol",
        "result",
    ]


def test_pattern_compiler_is_fail_closed_on_role_cardinality() -> None:
    legal, _ = build_contract_cases()
    evidence_id = legal.task.oracle.gold_evidence_ids[0]
    binding = make_evidence_binding(
        pattern_id=LEGAL_RULE_APPLICATION_PATTERN.pattern_id,
        pattern_version=LEGAL_RULE_APPLICATION_PATTERN.pattern_version,
        pattern_hash=LEGAL_RULE_APPLICATION_PATTERN.pattern_hash,
        role_bindings={"rules": (evidence_id,)},
        source_graph_id=legal.proof_graph.graph_id,
        node_parameters={
            "apply": {"satisfied_conditions": (), "present_exceptions": ()},
            "result": {"authority_priority": ("Example Act", "Agency Guidance")},
        },
    )

    with pytest.raises(ValueError, match="minimum cardinality"):
        TaskPatternCompiler(
            legal_operation_registry(),
            LegalTaskPatternRuntime(),
        ).compile(
            LEGAL_RULE_APPLICATION_PATTERN,
            binding,
            legal.bundle,
            legal.proof_graph,
        )


def test_pattern_compiler_rejects_registry_schema_drift() -> None:
    legal, _ = build_contract_cases()
    pattern_payload = LEGAL_RULE_APPLICATION_PATTERN.model_dump(mode="python")
    pattern_payload["program_template"][0]["output_schema"] = "scalar"
    drifted = TaskPatternSpec.model_validate(pattern_payload)
    source_binding = legal.task.oracle.selection_contract["pattern_binding"]
    binding = make_evidence_binding(
        pattern_id=drifted.pattern_id,
        pattern_version=drifted.pattern_version,
        pattern_hash=drifted.pattern_hash,
        role_bindings=source_binding["role_bindings"],
        source_graph_id=legal.proof_graph.graph_id,
        node_parameters={
            "apply": {
                "satisfied_conditions": ("threshold exceeded",),
                "present_exceptions": (),
            },
            "result": {"authority_priority": ("Example Act", "Agency Guidance")},
        },
    )

    with pytest.raises(ValueError, match="output schema disagrees"):
        TaskPatternCompiler(
            legal_operation_registry(),
            LegalTaskPatternRuntime(),
        ).compile(drifted, binding, legal.bundle, legal.proof_graph)


def test_quality_contract_and_certificate_bind_pattern_without_public_binding_leak() -> None:
    legal, _ = build_contract_cases()
    contract_compiler = QualityContractCompiler(
        legal.registry,
        domain_provider=legal.quality_clause_provider,
    )
    artifacts = ProofCarryingSampleCompiler(
        legal.registry,
        contract_compiler,
        legal.plugin_set,
        semantic_policy=legal.semantic_policy,
    ).compile(legal.task, legal.bundle, legal.proof_graph)

    clause_kinds = {clause.clause_kind for clause in artifacts.quality_contract.clauses}
    assert "task_pattern_binding_integrity" in clause_kinds
    assert "difficulty_profile_integrity" in clause_kinds
    assert artifacts.sample.pattern_hash == artifacts.sample.certificate.task_pattern_hash
    assert artifacts.sample.binding_hash == artifacts.sample.certificate.evidence_binding_hash
    public_json = json.dumps(artifacts.public_artifact.model_dump(mode="json"))
    assert artifacts.sample.binding_id not in public_json
    assert artifacts.sample.binding_hash not in public_json


def test_quality_contract_rejects_malformed_pattern_compilation_identity() -> None:
    legal, _ = build_contract_cases()
    public = legal.task.public.model_copy(
        update={
            "metadata": {
                **legal.task.public.metadata,
                "task_pattern": "not-a-typed-pattern-identity",
            }
        }
    )
    malformed = legal.task.model_copy(update={"public": public})

    with pytest.raises(ValueError, match="must be typed mappings"):
        QualityContractCompiler(
            legal.registry,
            domain_provider=legal.quality_clause_provider,
        ).compile(malformed, legal.bundle, legal.proof_graph)


def test_task_pattern_compilation_is_deterministic() -> None:
    first = build_contract_cases()
    second = build_contract_cases()

    assert [case.task.task_hash for case in first] == [case.task.task_hash for case in second]
    assert [case.task.public.metadata["task_pattern"]["pattern_hash"] for case in first] == [
        case.task.public.metadata["task_pattern"]["pattern_hash"] for case in second
    ]
    assert [
        case.task.oracle.selection_contract["pattern_binding"]["binding_hash"] for case in first
    ] == [case.task.oracle.selection_contract["pattern_binding"]["binding_hash"] for case in second]


def test_fixture_capacity_contains_distinct_patterns_and_programs_per_domain() -> None:
    cases = (
        *build_finance_counterfactual_cases(count=12),
        *build_pattern_validation_cases(per_domain=12),
    )
    expected_pattern_counts = {"finance": 4, "legal": 3, "science": 3}
    expected_program_counts = {"finance": 4, "legal": 2, "science": 3}

    for domain in ("finance", "legal", "science"):
        domain_cases = tuple(item for item in cases if item.domain == domain)
        pattern_ids = {
            item.task.public.metadata["task_pattern"]["pattern_id"] for item in domain_cases
        }
        program_signatures = {
            tuple(node.operator_id for node in item.task.oracle.task_program.nodes)
            for item in domain_cases
        }
        assert len(pattern_ids) == expected_pattern_counts[domain]
        assert len(program_signatures) == expected_program_counts[domain]
        assert len({item.task.task_id for item in domain_cases}) == 12
