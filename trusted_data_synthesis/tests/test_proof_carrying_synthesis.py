from __future__ import annotations

import json
from dataclasses import dataclass

import pytest

from trusted_synthesis.core.evaluation.contracts import QualityContractCompiler
from trusted_synthesis.core.evidence.corpus import EvidenceCorpus
from trusted_synthesis.core.evidence.schema import EvidenceItem
from trusted_synthesis.core.release import SplitPolicy, build_release_manifest
from trusted_synthesis.core.synthesis import ProofCarryingSampleCompiler, ProofCertificate
from trusted_synthesis.experiments.cross_domain_contract_suite import (
    run_cross_domain_contract_suite,
)
from trusted_synthesis.experiments.cross_domain_contract_suite.fixtures import (
    build_contract_cases,
)


class _ContractAdapter:
    adapter_id = "proof_contract_fixture.v1"
    domain = "contract_fixture"

    @staticmethod
    def capability_manifest() -> tuple:
        return ()


@dataclass(frozen=True)
class _GroundingReport:
    evidence_id: str
    checks: dict[str, bool]
    failures: tuple[str, ...]


class _SelectiveGroundingVerifier:
    verifier_id = "selective_grounding_test.v1"
    verifier_version = "1.0.0"

    def __init__(self, rejected_evidence_id: str) -> None:
        self._rejected_evidence_id = rejected_evidence_id

    def verify(self, evidence: EvidenceItem) -> _GroundingReport:
        rejected = evidence.evidence_id == self._rejected_evidence_id
        return _GroundingReport(
            evidence_id=evidence.evidence_id,
            checks={"grounded": not rejected},
            failures=("test_distractor_not_grounded",) if rejected else (),
        )


def _compile_case(index: int = 0):
    case = build_contract_cases()[index]
    quality_compiler = QualityContractCompiler(
        case.registry,
        domain_provider=case.quality_clause_provider,
    )
    artifacts = ProofCarryingSampleCompiler(
        case.registry,
        quality_compiler,
        case.plugin_set,
        semantic_policy=case.semantic_policy,
    ).compile(
        case.task,
        case.bundle,
        case.proof_graph,
        public_corpus=case.corpus,
    )
    return case, artifacts


def test_proof_certificate_binds_all_hidden_artifacts_and_public_view_is_clean() -> None:
    case, artifacts = _compile_case()
    sample = artifacts.sample
    certificate = sample.certificate

    assert certificate.task_package_hash == case.task.task_hash
    assert certificate.evidence_bundle_hash == case.bundle.bundle_hash
    assert certificate.public_corpus_id == case.corpus.corpus_id
    assert certificate.public_corpus_hash == case.corpus.corpus_hash
    assert artifacts.public_corpus == case.corpus
    assert certificate.proof_graph_hash == case.proof_graph.graph_hash
    assert certificate.task_program_hash == case.task.oracle.task_program.program_hash
    assert certificate.quality_contract_hash == artifacts.quality_contract.contract_hash
    assert certificate.reference_execution_hash == artifacts.reference_trajectory.trajectory_hash
    public_json = json.dumps(artifacts.public_artifact.model_dump(mode="json"))
    assert "oracle" not in public_json.casefold()
    assert "expected_output" not in public_json
    assert all(item not in public_json for item in case.task.oracle.gold_evidence_ids)


def test_proof_certificate_tampering_is_rejected() -> None:
    _, artifacts = _compile_case()
    payload = artifacts.sample.certificate.model_dump(mode="json")
    payload["proof_graph_hash"] = "proof_graph:tampered"

    with pytest.raises(ValueError, match="identity or hash"):
        ProofCertificate.model_validate(payload)


def test_public_corpus_content_is_bound_into_sample_and_certificate() -> None:
    case, baseline = _compile_case()
    gold_ids = set(case.task.oracle.gold_evidence_ids)
    distractor = next(item for item in case.corpus.evidence if item.evidence_id not in gold_ids)
    mutated_distractor = distractor.model_copy(
        update={
            "source": distractor.source.model_copy(
                update={"name": f"{distractor.source.name} mutated"}
            )
        }
    )
    corpus = EvidenceCorpus(
        corpus_id=case.corpus.corpus_id,
        evidence=tuple(
            mutated_distractor if item.evidence_id == distractor.evidence_id else item
            for item in case.corpus.evidence
        ),
        build_id=case.corpus.build_id,
    )
    quality_compiler = QualityContractCompiler(
        case.registry,
        domain_provider=case.quality_clause_provider,
    )
    mutated = ProofCarryingSampleCompiler(
        case.registry,
        quality_compiler,
        case.plugin_set,
        semantic_policy=case.semantic_policy,
    ).compile(
        case.task,
        case.bundle,
        case.proof_graph,
        public_corpus=corpus,
    )

    assert corpus.corpus_id == case.corpus.corpus_id
    assert corpus.corpus_hash != case.corpus.corpus_hash
    assert (
        mutated.sample.certificate.certificate_hash != baseline.sample.certificate.certificate_hash
    )
    assert mutated.sample.sample_id != baseline.sample.sample_id


def test_proof_compiler_rejects_ungrounded_public_distractor() -> None:
    case = build_contract_cases()[0]
    gold_ids = set(case.task.oracle.gold_evidence_ids)
    distractor = next(item for item in case.corpus.evidence if item.evidence_id not in gold_ids)
    quality_compiler = QualityContractCompiler(
        case.registry,
        domain_provider=case.quality_clause_provider,
    )

    with pytest.raises(ValueError, match="public Corpus Source Grounding failed"):
        ProofCarryingSampleCompiler(
            case.registry,
            quality_compiler,
            case.plugin_set,
            semantic_policy=case.semantic_policy,
            source_grounding_verifier=_SelectiveGroundingVerifier(distractor.evidence_id),
        ).compile(
            case.task,
            case.bundle,
            case.proof_graph,
            public_corpus=case.corpus,
        )


def test_proof_compiler_accepts_an_explicitly_providerless_domain_contract() -> None:
    case = build_contract_cases()[0]
    plugin_set = case.plugin_set.model_copy(
        update={
            "quality_clause_provider_id": None,
            "quality_clause_provider_version": None,
        }
    )
    quality_compiler = QualityContractCompiler(case.registry)

    artifacts = ProofCarryingSampleCompiler(
        case.registry,
        quality_compiler,
        plugin_set,
        semantic_policy=case.semantic_policy,
    ).compile(case.task, case.bundle, case.proof_graph)

    assert artifacts.quality_contract.domain_provider_identity is None
    assert plugin_set.quality_provider_identity is None


def test_release_freezes_contracts_and_certificates_and_requires_exact_coverage() -> None:
    case, artifacts = _compile_case()
    contracts = run_cross_domain_contract_suite()
    manifest = build_release_manifest(
        release_id="release:proof_carrying_contract",
        tasks=(case.task,),
        adapters=(_ContractAdapter(),),
        registry=case.registry,
        split_policy=SplitPolicy(policy_id="proof_carrying_contract"),
        source_build_ids={"fixture": "fixture_build_v1"},
        domain_plugin_sets=contracts.plugin_sets,
        cross_domain_contract_suite=contracts.result,
        quality_contracts=(artifacts.quality_contract,),
        proof_certificates=(artifacts.sample.certificate,),
    )

    assert artifacts.quality_contract.contract_hash in manifest.quality_contract_hashes
    assert artifacts.sample.certificate.certificate_hash in manifest.proof_certificate_hashes
    assert "quality_contract_compiler.v5" in manifest.quality_contract_compiler_versions
    assert "proof_carrying_compiler.v4" in manifest.proof_compiler_versions
    assert artifacts.sample.certificate.counterfactual_operator_manifest_hash
    assert manifest.counterfactual_operator_manifest_hashes
    assert manifest.task_pattern_schema_versions == ("task_pattern.v1",)
    assert manifest.task_pattern_compiler_versions == ("task_pattern_compiler.v1",)
    assert manifest.task_pattern_runtimes == {"legal_task_pattern_runtime.v3": "3.0.0"}
    assert manifest.task_pattern_quality_profile_ids == ("legal.rule_application.quality.v1",)
    assert manifest.task_difficulty_policy_versions == ("task_difficulty.v2",)
    assert len(manifest.evidence_binding_hashes) == 1

    with pytest.raises(ValueError, match="quality contracts do not exactly cover"):
        build_release_manifest(
            release_id="release:missing_quality_contract",
            tasks=(case.task,),
            adapters=(_ContractAdapter(),),
            registry=case.registry,
            split_policy=SplitPolicy(policy_id="missing_quality_contract"),
            source_build_ids={"fixture": "fixture_build_v1"},
            domain_plugin_sets=contracts.plugin_sets,
            cross_domain_contract_suite=contracts.result,
        )

    with pytest.raises(ValueError, match="duplicate task IDs"):
        build_release_manifest(
            release_id="release:duplicate_task",
            tasks=(case.task, case.task),
            adapters=(_ContractAdapter(),),
            registry=case.registry,
            split_policy=SplitPolicy(policy_id="duplicate_task"),
            source_build_ids={"fixture": "fixture_build_v1"},
            domain_plugin_sets=contracts.plugin_sets,
            cross_domain_contract_suite=contracts.result,
            quality_contracts=(artifacts.quality_contract,),
            proof_certificates=(artifacts.sample.certificate,),
        )
