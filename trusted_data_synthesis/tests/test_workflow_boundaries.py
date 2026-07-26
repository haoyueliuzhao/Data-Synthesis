from __future__ import annotations

import inspect
import json

import pytest

from trusted_synthesis.core.evidence.schema import EvidenceBundle, EvidenceItem
from trusted_synthesis.core.graph.builder import ProofGraphBuilder
from trusted_synthesis.core.operations.registry import default_registry
from trusted_synthesis.core.task.generator import ProofGraphTaskSynthesizer
from trusted_synthesis.core.task.schema import TaskPublicSpec
from trusted_synthesis.experiments.finance_pilot.candidate import (
    FinanceNumericCandidateGenerator,
)
from trusted_synthesis.runtime import InMemoryEvidenceToolRuntime


def test_candidate_api_cannot_receive_an_oracle(finance_evidence: EvidenceItem) -> None:
    bundle = EvidenceBundle(
        bundle_id="bundle_boundary", evidence=(finance_evidence,), purpose="boundary test"
    )
    graph = ProofGraphBuilder().build(bundle)
    package = ProofGraphTaskSynthesizer().fact_retrieval(
        graph, bundle, finance_evidence.evidence_id
    )
    public_json = json.dumps(package.public.model_dump(mode="json"))
    runtime = InMemoryEvidenceToolRuntime(bundle)
    candidate = FinanceNumericCandidateGenerator().generate(package.public, runtime)

    assert list(inspect.signature(FinanceNumericCandidateGenerator.generate).parameters) == [
        "self",
        "task",
        "runtime",
    ]
    assert finance_evidence.evidence_id not in public_json
    assert finance_evidence.evidence_version_id not in public_json
    assert finance_evidence.source.source_id not in public_json
    assert bundle.bundle_id not in public_json
    assert "required_build_ids" not in public_json
    assert "domain_context_hashes" not in public_json
    assert package.public.program_skeleton is not None
    assert package.oracle.selection_contract["source_ids"] == [finance_evidence.source.source_id]
    assert runtime.last_query is not None
    assert "evidence_ids" not in runtime.last_query
    assert candidate.final_answer["result"]["payload"]["value"] == "383285"

    leaked_public = package.public.model_dump(mode="python")
    leaked_public["metadata"]["source_ids"] = [finance_evidence.source.source_id]
    with pytest.raises(ValueError, match="oracle-only keys"):
        TaskPublicSpec.model_validate(leaked_public)


def test_finance_candidate_is_not_part_of_the_generic_runtime() -> None:
    import trusted_synthesis.runtime as runtime

    assert FinanceNumericCandidateGenerator.__module__.startswith(
        "trusted_synthesis.experiments.finance_pilot"
    )
    assert not hasattr(runtime, "CandidateTrajectoryGenerator")


def test_operation_registry_uses_separate_executor_and_oracle_modules() -> None:
    for item in default_registry().manifest():
        assert item["executor"]
        assert item["oracle_verifier"]
        definition = default_registry().require(str(item["operator_id"]))
        assert type(definition.executor).__module__ != type(definition.oracle_verifier).__module__
