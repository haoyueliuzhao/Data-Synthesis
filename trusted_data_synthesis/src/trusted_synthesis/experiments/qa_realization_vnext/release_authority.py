from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.core.evaluation.evaluator import (
    CANDIDATE_EVALUATOR_VERSION,
    CANDIDATE_REQUIRED_CHECK_MANIFEST,
    CandidateQualityEvaluator,
)
from trusted_synthesis.core.evaluation.realization_binding import (
    bind_realization_execution,
    describe_generated_trajectory,
)
from trusted_synthesis.core.evidence.corpus import EvidenceCorpus
from trusted_synthesis.core.evidence.schema import EvidenceBundle
from trusted_synthesis.core.graph.schema import ProofGraph
from trusted_synthesis.core.release import (
    DiversityAwareReleaseSelection,
    DiversityReleasePolicy,
    SplitPolicy,
    select_diversity_aware_release,
)
from trusted_synthesis.core.task.binding import EvidenceBinding
from trusted_synthesis.domains.finance.policy import FinanceSemanticPolicy
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


class QAReleaseAuthorityError(ValueError):
    """Structured rejection that proves an intended authority stage was reached."""

    def __init__(self, *, reason_code: str, stage: str, message: str) -> None:
        super().__init__(message)
        self.reason_code = reason_code
        self.stage = stage
        self.target_validator_reached = True


class AuthorityFixtureInput(BaseModel):
    """Exact evidence parents and binding for one frozen authority fixture."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    fixture_input_id: str = Field(min_length=1)
    fixture_index: int = Field(ge=1)
    task_type: str = Field(min_length=1)
    evidence_bundle: EvidenceBundle
    evidence_corpus: EvidenceCorpus
    proof_graph: ProofGraph
    evidence_binding: EvidenceBinding
    schema_version: str = "qa_release_authority_fixture_input.v1"

    @model_validator(mode="after")
    def validate_identity(self) -> AuthorityFixtureInput:
        EvidenceBundle.model_validate(
            self.evidence_bundle.model_dump(mode="python", warnings=False)
        )
        EvidenceCorpus.model_validate(
            self.evidence_corpus.model_dump(mode="python", warnings=False)
        )
        ProofGraph.model_validate(self.proof_graph.model_dump(mode="python", warnings=False))
        EvidenceBinding.model_validate(
            self.evidence_binding.model_dump(mode="python", warnings=False)
        )
        if self.evidence_binding.source_graph_id != self.proof_graph.graph_id:
            raise ValueError("authority fixture binding crosses its ProofGraph")
        corpus_by_id = self.evidence_corpus.by_id()
        if any(
            evidence.evidence_id not in corpus_by_id
            or canonical_hash(evidence) != canonical_hash(corpus_by_id[evidence.evidence_id])
            for evidence in self.evidence_bundle.evidence
        ):
            raise ValueError("authority fixture EvidenceBundle crosses its EvidenceCorpus")
        expected = canonical_hash(
            self.model_dump(mode="json", exclude={"fixture_input_id"}),
            prefix="qa_release_authority_fixture_input:",
        )
        if self.fixture_input_id != expected:
            raise ValueError("authority fixture input identity is invalid")
        return self


class QAReleaseAuthorityBundle(BaseModel):
    """Top-level, source-bound authority object for one persisted QA release."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    authority_bundle_id: str = Field(min_length=1)
    source_tree_id: str = Field(pattern=r"^[0-9a-f]{40}$")
    source_archive_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_snapshot_manifest_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    operation_manifest_hash: str = Field(min_length=1)
    pattern_manifest_hash: str = Field(min_length=1)
    renderer_manifest_hash: str = Field(min_length=1)
    generator_contract_id: str = Field(min_length=1)
    evaluator_contract_id: str = Field(min_length=1)
    semantic_policy_id: str = Field(min_length=1)
    release_policy_hash: str = Field(min_length=1)
    split_policy_hash: str = Field(min_length=1)
    frozen_task_types: tuple[str, ...]
    frozen_renderer_profile_ids: tuple[str, ...]
    fixture_inputs: tuple[AuthorityFixtureInput, ...] = Field(min_length=1)
    release_selection: DiversityAwareReleaseSelection
    schema_version: str = "qa_release_authority_bundle.v1"

    @model_validator(mode="after")
    def validate_identity(self) -> QAReleaseAuthorityBundle:
        if len(self.frozen_task_types) != 8 or len(set(self.frozen_task_types)) != 8:
            raise ValueError("authority bundle must freeze exactly eight task types")
        if (
            len(self.frozen_renderer_profile_ids) != 32
            or len(set(self.frozen_renderer_profile_ids)) != 32
        ):
            raise ValueError("authority bundle must freeze exactly thirty-two renderer profiles")
        fixture_ids = tuple(item.fixture_input_id for item in self.fixture_inputs)
        fixture_indexes = tuple(item.fixture_index for item in self.fixture_inputs)
        if len(fixture_ids) != len(set(fixture_ids)) or len(fixture_indexes) != len(
            set(fixture_indexes)
        ):
            raise ValueError("authority bundle contains duplicate fixture inputs")
        for item in self.fixture_inputs:
            AuthorityFixtureInput.model_validate(item.model_dump(mode="python", warnings=False))
        DiversityAwareReleaseSelection.model_validate(
            self.release_selection.model_dump(mode="python", warnings=False)
        )
        if self.release_policy_hash != self.release_selection.policy_hash:
            raise ValueError("authority bundle ReleasePolicy hash crosses its selection")
        if self.split_policy_hash != self.release_selection.split_policy_hash:
            raise ValueError("authority bundle SplitPolicy hash crosses its selection")
        expected = canonical_hash(
            self.model_dump(mode="json", exclude={"authority_bundle_id"}),
            prefix="qa_release_authority_bundle:",
        )
        if self.authority_bundle_id != expected:
            raise ValueError("QA release authority bundle identity is invalid")
        return self


def current_evaluator_contract_id() -> str:
    return canonical_hash(
        {
            "evaluator_version": CANDIDATE_EVALUATOR_VERSION,
            "required_check_manifest": CANDIDATE_REQUIRED_CHECK_MANIFEST,
            "semantic_policy_id": FinanceSemanticPolicy.policy_id,
            "schema_version": "qa_release_evaluator_contract.v1",
        },
        prefix="qa_release_evaluator_contract:",
    )


def authoritative_release_policy() -> DiversityReleasePolicy:
    return DiversityReleasePolicy(
        policy_id="qa_release_authority_frozen_policy.v1",
        max_total=10_000,
        max_per_semantic_instance=3,
        max_per_semantic_schema=10_000,
    )


def authoritative_split_policy() -> SplitPolicy:
    return SplitPolicy(policy_id="qa_release_authority_frozen_split.v1")


def build_qa_release_authority_bundle(
    *,
    source_tree_id: str,
    source_archive_sha256: str,
    source_snapshot_manifest_sha256: str,
    fixture_indexes: tuple[int, ...] = (1, 2),
    release_policy: DiversityReleasePolicy | None = None,
    split_policy: SplitPolicy | None = None,
) -> QAReleaseAuthorityBundle:
    plugin = FinanceTaskPlugin(allow_structured_claims=True)
    inputs = tuple(_build_fixture_input(index, plugin) for index in fixture_indexes)
    records = tuple(
        record
        for authority_input in inputs
        for record in _reconstruct_fixture_records(authority_input, plugin)
    )
    resolved_release_policy = release_policy or authoritative_release_policy()
    resolved_split_policy = split_policy or authoritative_split_policy()
    selection = select_diversity_aware_release(
        records,
        policy=resolved_release_policy,
        split_policy=resolved_split_policy,
    )
    payload = _bundle_payload(
        source_tree_id=source_tree_id,
        source_archive_sha256=source_archive_sha256,
        source_snapshot_manifest_sha256=source_snapshot_manifest_sha256,
        plugin=plugin,
        fixture_inputs=inputs,
        release_selection=selection,
    )
    provisional = QAReleaseAuthorityBundle.model_construct(
        authority_bundle_id="pending",
        **payload,
    )
    authority_bundle_id = canonical_hash(
        provisional.model_dump(mode="json", exclude={"authority_bundle_id"}),
        prefix="qa_release_authority_bundle:",
    )
    return QAReleaseAuthorityBundle(
        authority_bundle_id=authority_bundle_id,
        **payload,
    )


def load_and_reconstruct_qa_release_authority_bundle(
    value: QAReleaseAuthorityBundle | dict[str, Any],
    *,
    expected_source_tree_id: str,
    expected_source_archive_sha256: str,
    expected_source_snapshot_manifest_sha256: str,
) -> QAReleaseAuthorityBundle:
    try:
        bundle = (
            value
            if isinstance(value, QAReleaseAuthorityBundle)
            else QAReleaseAuthorityBundle.model_validate(value)
        )
        QAReleaseAuthorityBundle.model_validate(bundle.model_dump(mode="python", warnings=False))
    except ValueError as exc:
        raise QAReleaseAuthorityError(
            reason_code="bundle_schema_or_content_identity_invalid",
            stage="bundle_schema",
            message=str(exc),
        ) from exc

    expected_source = (
        expected_source_tree_id,
        expected_source_archive_sha256,
        expected_source_snapshot_manifest_sha256,
    )
    observed_source = (
        bundle.source_tree_id,
        bundle.source_archive_sha256,
        bundle.source_snapshot_manifest_sha256,
    )
    if observed_source != expected_source:
        raise QAReleaseAuthorityError(
            reason_code="full_source_snapshot_binding_mismatch",
            stage="source_snapshot",
            message="authority bundle does not bind the exact executed source snapshot",
        )

    plugin = FinanceTaskPlugin(allow_structured_claims=True)
    expected_contracts = _bundle_contracts(plugin)
    observed_contracts = {
        "operation_manifest_hash": bundle.operation_manifest_hash,
        "pattern_manifest_hash": bundle.pattern_manifest_hash,
        "renderer_manifest_hash": bundle.renderer_manifest_hash,
        "generator_contract_id": bundle.generator_contract_id,
        "evaluator_contract_id": bundle.evaluator_contract_id,
        "semantic_policy_id": bundle.semantic_policy_id,
        "release_policy_hash": bundle.release_policy_hash,
        "split_policy_hash": bundle.split_policy_hash,
        "frozen_task_types": bundle.frozen_task_types,
        "frozen_renderer_profile_ids": bundle.frozen_renderer_profile_ids,
    }
    if observed_contracts != expected_contracts:
        raise QAReleaseAuthorityError(
            reason_code="runtime_semantic_contract_mismatch",
            stage="runtime_contracts",
            message="persisted runtime contracts differ from the executed source",
        )

    reconstructed_records = []
    for authority_input in bundle.fixture_inputs:
        expected_input = _build_fixture_input(authority_input.fixture_index, plugin)
        if canonical_hash(expected_input) != canonical_hash(authority_input):
            raise QAReleaseAuthorityError(
                reason_code="fixture_evidence_parent_mismatch",
                stage="evidence_parents",
                message=(
                    "EvidenceBundle, EvidenceCorpus, ProofGraph, or EvidenceBinding "
                    "differs from the source-derived fixture"
                ),
            )
        try:
            reconstructed_records.extend(_reconstruct_fixture_records(authority_input, plugin))
        except ValueError as exc:
            raise QAReleaseAuthorityError(
                reason_code="compile_generate_or_evaluate_replay_mismatch",
                stage="execution_replay",
                message=str(exc),
            ) from exc

    try:
        expected_selection = select_diversity_aware_release(
            reconstructed_records,
            policy=bundle.release_selection.release_policy,
            split_policy=bundle.release_selection.split_policy,
        )
    except ValueError as exc:
        raise QAReleaseAuthorityError(
            reason_code="release_selection_replay_failed",
            stage="release_selection",
            message=str(exc),
        ) from exc
    if canonical_hash(expected_selection) != canonical_hash(bundle.release_selection):
        raise QAReleaseAuthorityError(
            reason_code="release_selection_replay_mismatch",
            stage="release_selection",
            message="persisted release selection differs from source-derived replay",
        )
    return bundle


def _build_fixture_input(
    fixture_index: int,
    plugin: FinanceTaskPlugin,
) -> AuthorityFixtureInput:
    case = build_finance_counterfactual_case(fixture_index)
    instantiation = plugin.compile_evidence_ids(
        case.task.public.task_type,
        case.proof_graph,
        case.bundle,
        case.task.oracle.gold_evidence_ids,
    )
    payload = {
        "fixture_index": fixture_index,
        "task_type": case.task.public.task_type,
        "evidence_bundle": case.bundle,
        "evidence_corpus": case.corpus,
        "proof_graph": case.proof_graph,
        "evidence_binding": instantiation.binding,
        "schema_version": "qa_release_authority_fixture_input.v1",
    }
    provisional = AuthorityFixtureInput.model_construct(
        fixture_input_id="pending",
        **payload,
    )
    fixture_input_id = canonical_hash(
        provisional.model_dump(mode="json", exclude={"fixture_input_id"}),
        prefix="qa_release_authority_fixture_input:",
    )
    return AuthorityFixtureInput(fixture_input_id=fixture_input_id, **payload)


def _reconstruct_fixture_records(
    authority_input: AuthorityFixtureInput,
    plugin: FinanceTaskPlugin,
):
    instantiation = plugin.compile_binding(
        authority_input.task_type,
        authority_input.proof_graph,
        authority_input.evidence_bundle,
        authority_input.evidence_binding,
    )
    compilation = plugin.realize_instantiation(
        instantiation,
        authority_input.proof_graph,
        authority_input.evidence_bundle,
    )
    generator = FinanceNumericCandidateGenerator()
    evaluator = CandidateQualityEvaluator(semantic_policy=FinanceSemanticPolicy())
    records = []
    for realized in compilation.selected:
        generated = generator.generate(
            realized.task.public,
            InMemoryEvidenceToolRuntime(authority_input.evidence_corpus),
        )
        trajectory, descriptor = describe_generated_trajectory(
            realized,
            authority_input.evidence_corpus,
            generated,
            generator_contract_id=FINANCE_NUMERIC_GENERATOR_CONTRACT_ID,
        )
        assessment = evaluator.evaluate(
            realized.task,
            authority_input.evidence_corpus,
            authority_input.proof_graph,
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
    return tuple(records)


def _bundle_payload(
    *,
    source_tree_id: str,
    source_archive_sha256: str,
    source_snapshot_manifest_sha256: str,
    plugin: FinanceTaskPlugin,
    fixture_inputs: tuple[AuthorityFixtureInput, ...],
    release_selection: DiversityAwareReleaseSelection,
) -> dict[str, Any]:
    return {
        "source_tree_id": source_tree_id,
        "source_archive_sha256": source_archive_sha256,
        "source_snapshot_manifest_sha256": source_snapshot_manifest_sha256,
        **_bundle_contracts(plugin),
        "fixture_inputs": fixture_inputs,
        "release_selection": release_selection,
        "schema_version": "qa_release_authority_bundle.v1",
    }


def _bundle_contracts(plugin: FinanceTaskPlugin) -> dict[str, Any]:
    renderer_manifest = plugin.renderer_manifest
    return {
        "operation_manifest_hash": canonical_hash(
            plugin.operation_registry().manifest(),
            prefix="operation_manifest:",
        ),
        "pattern_manifest_hash": canonical_hash(
            plugin.pattern_manifest,
            prefix="finance_pattern_manifest:",
        ),
        "renderer_manifest_hash": canonical_hash(
            renderer_manifest,
            prefix="finance_renderer_manifest:",
        ),
        "generator_contract_id": FINANCE_NUMERIC_GENERATOR_CONTRACT_ID,
        "evaluator_contract_id": current_evaluator_contract_id(),
        "semantic_policy_id": FinanceSemanticPolicy.policy_id,
        "release_policy_hash": authoritative_release_policy().policy_hash,
        "split_policy_hash": authoritative_split_policy().policy_hash,
        "frozen_task_types": tuple(plugin.task_family_ids),
        "frozen_renderer_profile_ids": tuple(
            sorted(str(row["profile_id"]) for row in renderer_manifest)
        ),
    }
