from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.core.evaluation.contracts.compiler import QualityContractCompiler
from trusted_synthesis.core.evidence.corpus import EvidenceCorpus
from trusted_synthesis.core.evidence.schema import EvidenceBundle
from trusted_synthesis.core.graph.schema import ProofGraph
from trusted_synthesis.core.operations.registry import OperationRegistry
from trusted_synthesis.core.plugins import (
    DomainPluginSet,
    DomainQualityClauseProviderProtocol,
    SemanticPolicyProtocol,
    SourceGroundingVerifierProtocol,
    TaskPatternRuntimeProtocol,
)
from trusted_synthesis.core.synthesis import (
    CompiledProofCarryingArtifacts,
    ProofCarryingSampleCompiler,
)
from trusted_synthesis.core.task.binding import EvidenceBinding, make_evidence_binding
from trusted_synthesis.core.task.pattern import TaskPatternSpec
from trusted_synthesis.core.task.pattern_compiler import (
    TaskPatternCompiler,
    TaskPatternInstantiation,
)
from trusted_synthesis.hashing import canonical_hash

from .aggregate import build_synthesis_cell
from .schema import PolicyUpdateResult, SynthesisCell

REFINED_SYNTHESIS_MATERIALIZER_VERSION = "refined_synthesis_materializer.v5"


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class SynthesisCellRequest(FrozenModel):
    """One policy allocation translated into a concrete synthesis request."""

    request_id: str = Field(min_length=1)
    policy_update_id: str = Field(min_length=1)
    cell: SynthesisCell
    policy_allocated_count: int = Field(ge=0)
    requested_count: int = Field(ge=0)
    seed: int
    schema_version: str = "synthesis_cell_request.v1"

    @model_validator(mode="after")
    def validate_identity(self) -> SynthesisCellRequest:
        if self.request_id != synthesis_cell_request_id(self):
            raise ValueError("synthesis cell request identity is invalid")
        return self


class SynthesisMaterializationReport(FrozenModel):
    """Auditable proof that a policy allocation produced newly compiled artifacts."""

    report_id: str = Field(min_length=1)
    policy_update_id: str = Field(min_length=1)
    provider_id: str = Field(min_length=1)
    provider_version: str = Field(min_length=1)
    provider_contract_hash: str = Field(min_length=1)
    compiler_contract_hash: str = "legacy:unknown"
    sampling_contract_hash: str = "legacy:unknown"
    candidate_pool_contract_hash: str = "legacy:unknown"
    candidate_pool_id: str = "legacy:unknown"
    sampling_partition_id: str = "legacy:unknown"
    materialization_seed: int = 0
    seed_effective: bool = False
    policy_allocated_counts: dict[str, int]
    requested_cell_counts: dict[str, int]
    materialized_cell_counts: dict[str, int]
    requested_sample_count: int = Field(ge=0)
    provider_candidate_count: int = Field(ge=0)
    binding_feasible_count: int = Field(ge=0)
    contract_attempt_count: int = Field(ge=0)
    contract_pass_count: int = Field(ge=0)
    grounding_required_sample_count: int = Field(ge=0, default=0)
    grounding_checked_count: int = Field(ge=0, default=0)
    grounding_pass_count: int = Field(ge=0, default=0)
    grounding_failure_counts: dict[str, int] = Field(default_factory=dict)
    candidate_rejection_counts: dict[str, int] = Field(default_factory=dict)
    forbidden_subject_count: int = Field(ge=0, default=0)
    forbidden_subject_manifest_hash: str = "legacy:unknown"
    successfully_materialized_count: int = Field(ge=0)
    new_task_identity_count: int = Field(ge=0)
    new_binding_identity_count: int = Field(ge=0)
    new_evidence_identity_count: int = Field(ge=0)
    binding_feasibility_rate: float = Field(ge=0, le=1)
    contract_pass_rate: float = Field(ge=0, le=1)
    new_task_identity_rate: float = Field(ge=0, le=1)
    new_binding_identity_rate: float = Field(ge=0, le=1)
    new_evidence_identity_rate: float = Field(ge=0, le=1)
    task_identity_manifest_hash: str = Field(min_length=1)
    binding_identity_manifest_hash: str = Field(min_length=1)
    evidence_identity_manifest_hash: str = Field(min_length=1)
    failure_counts: dict[str, int]
    status: Literal["passed", "blocked"]
    version: str = REFINED_SYNTHESIS_MATERIALIZER_VERSION

    @model_validator(mode="after")
    def validate_counts_and_identity(self) -> SynthesisMaterializationReport:
        if sum(self.requested_cell_counts.values()) != self.requested_sample_count:
            raise ValueError("requested Cell counts do not sum to the requested sample count")
        if sum(self.materialized_cell_counts.values()) != self.successfully_materialized_count:
            raise ValueError("materialized Cell counts do not cover successful artifacts")
        if self.successfully_materialized_count > self.requested_sample_count:
            raise ValueError("materialized samples cannot exceed requested samples")
        if self.grounding_pass_count > self.grounding_checked_count:
            raise ValueError("grounding pass count cannot exceed checked evidence")
        grounding_passed = self.grounding_required_sample_count == 0 or (
            self.grounding_checked_count > 0
            and self.grounding_checked_count == self.grounding_pass_count
            and not self.grounding_failure_counts
        )
        if self.version == REFINED_SYNTHESIS_MATERIALIZER_VERSION:
            expected_status = (
                "passed"
                if self.successfully_materialized_count == self.requested_sample_count
                and not self.failure_counts
                and self.seed_effective
                else "blocked"
            )
        else:
            expected_status = (
                "passed"
                if self.successfully_materialized_count == self.requested_sample_count
                and not self.failure_counts
                and self.binding_feasibility_rate == 1.0
                and self.contract_pass_rate == 1.0
                and self.new_task_identity_rate == 1.0
                and self.new_binding_identity_rate == 1.0
                and self.new_evidence_identity_rate == 1.0
                and grounding_passed
                and (self.seed_effective or self.version == "refined_synthesis_materializer.v1")
                else "blocked"
            )
        if self.status != expected_status:
            raise ValueError("materialization status disagrees with fail-closed gates")
        if self.report_id not in {
            synthesis_materialization_report_id(self),
            legacy_synthesis_materialization_report_id(self),
        }:
            raise ValueError("synthesis materialization report identity is invalid")
        return self


@dataclass(frozen=True)
class SynthesisBindingCandidate:
    """Domain-provided binding input; Core owns compilation and verification."""

    candidate_id: str
    pattern: TaskPatternSpec
    binding: EvidenceBinding
    bundle: EvidenceBundle
    corpus: EvidenceCorpus
    proof_graph: ProofGraph
    operation_registry: OperationRegistry
    pattern_runtime: TaskPatternRuntimeProtocol
    semantic_policy: SemanticPolicyProtocol
    quality_clause_provider: DomainQualityClauseProviderProtocol
    domain_plugin_set: DomainPluginSet
    source_grounding_verifier: SourceGroundingVerifierProtocol | None = None
    applied_binding_constraints: tuple[str, ...] = ()


class SynthesisBindingProviderProtocol(Protocol):
    """Domain-owned enumerator for one requested structural synthesis Cell."""

    provider_id: str
    provider_version: str
    provider_contract_hash: str
    compiler_contract_hash: str
    sampling_contract_hash: str
    candidate_pool_contract_hash: str
    candidate_pool_id: str
    sampling_partition_id: str
    seed_effective: bool

    def iter_candidates(
        self,
        request: SynthesisCellRequest,
    ) -> Iterable[SynthesisBindingCandidate]: ...


@dataclass(frozen=True)
class RefinedSynthesisArtifact:
    request: SynthesisCellRequest
    candidate: SynthesisBindingCandidate
    binding: EvidenceBinding
    instantiation: TaskPatternInstantiation
    compiled: CompiledProofCarryingArtifacts


@dataclass(frozen=True)
class _FeasibleSynthesisBinding:
    request: SynthesisCellRequest
    candidate: SynthesisBindingCandidate
    binding: EvidenceBinding
    instantiation: TaskPatternInstantiation


class RefinedSynthesisMaterializer:
    """Compile policy Cell requests into new proof-carrying task identities."""

    def __init__(self, provider: SynthesisBindingProviderProtocol) -> None:
        self._provider = provider

    def materialize(
        self,
        update: PolicyUpdateResult,
        *,
        requested_counts: Mapping[str, int] | None = None,
        seed: int,
        forbidden_task_ids: Iterable[str] = (),
        forbidden_binding_ids: Iterable[str] = (),
        forbidden_evidence_version_ids: Iterable[str] = (),
        forbidden_subject_ids: Iterable[str] = (),
    ) -> tuple[tuple[RefinedSynthesisArtifact, ...], SynthesisMaterializationReport]:
        if update.status != "passed":
            raise ValueError("a blocked policy update cannot materialize synthesis requests")
        cells = {cell.cell_id: cell for cell in update.next_policy.cells}
        resolved_counts = dict(requested_counts or update.allocated_counts)
        if set(resolved_counts) != set(cells):
            raise ValueError("requested counts must cover every next-policy Cell")
        if any(value < 0 for value in resolved_counts.values()):
            raise ValueError("requested Cell counts cannot be negative")
        if sum(resolved_counts.values()) != update.total_budget:
            raise ValueError("requested Cell counts must preserve the policy budget")

        forbidden_tasks = set(forbidden_task_ids)
        forbidden_bindings = set(forbidden_binding_ids)
        forbidden_evidence = set(forbidden_evidence_version_ids)
        forbidden_subjects = {item for item in forbidden_subject_ids if item}
        artifacts: list[RefinedSynthesisArtifact] = []
        materialized_counts: Counter[str] = Counter()
        failure_counts: Counter[str] = Counter()
        candidate_rejection_counts: Counter[str] = Counter()
        provider_candidate_count = 0
        binding_feasible_count = 0
        contract_attempt_count = 0
        contract_pass_count = 0
        grounding_required_sample_count = 0
        grounding_checked_count = 0
        grounding_pass_count = 0
        grounding_failure_counts: Counter[str] = Counter()
        new_task_count = 0
        new_binding_count = 0
        new_evidence_count = 0
        observed_task_ids: set[str] = set()
        observed_binding_ids: set[str] = set()
        observed_evidence_ids: set[str] = set()

        for cell_id in sorted(cells):
            requested_count = resolved_counts[cell_id]
            request = make_synthesis_cell_request(
                policy_update_id=update.update_id,
                cell=cells[cell_id],
                policy_allocated_count=update.allocated_counts[cell_id],
                requested_count=requested_count,
                seed=seed,
            )
            if requested_count == 0:
                continue
            candidates = iter(self._provider.iter_candidates(request))
            accepted_count = 0
            while accepted_count < requested_count:
                try:
                    candidate = next(candidates)
                except StopIteration:
                    failure_counts["binding_provider_exhausted"] += requested_count - accepted_count
                    break
                except (TypeError, ValueError) as exc:
                    failure_counts[f"binding_provider:{type(exc).__name__}"] += (
                        requested_count - accepted_count
                    )
                    break
                provider_candidate_count += 1
                candidate_subjects = {
                    item.subject.subject_id
                    for item in candidate.bundle.evidence
                    if item.subject.subject_id
                }
                if candidate_subjects & forbidden_subjects:
                    candidate_rejection_counts["subject_identity_collision"] += 1
                    continue
                try:
                    feasible = _instantiate_candidate(request, candidate)
                    binding_feasible_count += 1
                except (TypeError, ValueError) as exc:
                    candidate_rejection_counts[f"binding:{type(exc).__name__}"] += 1
                    continue
                grounding = _verify_candidate_grounding(feasible)
                grounding_required_sample_count += int(grounding.required)
                grounding_checked_count += grounding.checked_count
                grounding_pass_count += grounding.pass_count
                grounding_failure_counts.update(grounding.failure_counts)
                if not grounding.passed:
                    candidate_rejection_counts["source_grounding_failed"] += 1
                    continue
                contract_attempt_count += 1
                try:
                    artifact = _compile_contract(feasible)
                    contract_pass_count += 1
                except (TypeError, ValueError) as exc:
                    candidate_rejection_counts[f"contract:{type(exc).__name__}"] += 1
                    continue
                compiled = artifact.compiled
                task_id = compiled.task.task_id
                binding_id = artifact.binding.binding_id
                evidence_ids = {item.evidence_version_id for item in candidate.corpus.evidence}
                evidence_is_new = not (
                    evidence_ids & forbidden_evidence or evidence_ids & observed_evidence_ids
                )
                task_is_new = task_id not in forbidden_tasks and task_id not in observed_task_ids
                # Evidence IDs are part of role_bindings and therefore of the Binding hash.
                # Requiring disjoint Evidence makes Binding novelty auditable even for
                # legacy source records that did not persist their full Binding ID.
                binding_is_new = (
                    evidence_is_new
                    and binding_id not in forbidden_bindings
                    and binding_id not in observed_binding_ids
                )
                new_task_count += int(task_is_new)
                new_binding_count += int(binding_is_new)
                new_evidence_count += int(evidence_is_new)
                if not task_is_new:
                    candidate_rejection_counts["task_identity_collision"] += 1
                    continue
                if not binding_is_new:
                    candidate_rejection_counts["binding_identity_collision"] += 1
                    continue
                if not evidence_is_new:
                    candidate_rejection_counts["evidence_identity_collision"] += 1
                    continue
                observed_task_ids.add(task_id)
                observed_binding_ids.add(binding_id)
                observed_evidence_ids.update(evidence_ids)
                artifacts.append(artifact)
                materialized_counts[cell_id] += 1
                accepted_count += 1

        requested_total = sum(resolved_counts.values())
        success_total = len(artifacts)
        task_ids = tuple(sorted(item.compiled.task.task_id for item in artifacts))
        binding_ids = tuple(sorted(item.binding.binding_id for item in artifacts))
        materialized_evidence_ids = tuple(
            sorted(
                item.evidence_version_id
                for artifact in artifacts
                for item in artifact.candidate.corpus.evidence
            )
        )
        report_fields = {
            "policy_update_id": update.update_id,
            "provider_id": self._provider.provider_id,
            "provider_version": self._provider.provider_version,
            "provider_contract_hash": self._provider.provider_contract_hash,
            "compiler_contract_hash": self._provider.compiler_contract_hash,
            "sampling_contract_hash": self._provider.sampling_contract_hash,
            "candidate_pool_contract_hash": self._provider.candidate_pool_contract_hash,
            "candidate_pool_id": self._provider.candidate_pool_id,
            "sampling_partition_id": self._provider.sampling_partition_id,
            "materialization_seed": seed,
            "seed_effective": self._provider.seed_effective,
            "policy_allocated_counts": dict(sorted(update.allocated_counts.items())),
            "requested_cell_counts": dict(sorted(resolved_counts.items())),
            "materialized_cell_counts": {
                cell_id: materialized_counts[cell_id] for cell_id in sorted(cells)
            },
            "requested_sample_count": requested_total,
            "provider_candidate_count": provider_candidate_count,
            "binding_feasible_count": binding_feasible_count,
            "contract_attempt_count": contract_attempt_count,
            "contract_pass_count": contract_pass_count,
            "grounding_required_sample_count": grounding_required_sample_count,
            "grounding_checked_count": grounding_checked_count,
            "grounding_pass_count": grounding_pass_count,
            "grounding_failure_counts": dict(sorted(grounding_failure_counts.items())),
            "candidate_rejection_counts": dict(sorted(candidate_rejection_counts.items())),
            "forbidden_subject_count": len(forbidden_subjects),
            "forbidden_subject_manifest_hash": canonical_hash(
                tuple(sorted(forbidden_subjects)),
                prefix="refined_synthesis_forbidden_subject_manifest:",
            ),
            "successfully_materialized_count": success_total,
            "new_task_identity_count": new_task_count,
            "new_binding_identity_count": new_binding_count,
            "new_evidence_identity_count": new_evidence_count,
            "binding_feasibility_rate": _rate(binding_feasible_count, provider_candidate_count),
            "contract_pass_rate": _rate(contract_pass_count, contract_attempt_count),
            "new_task_identity_rate": _rate(new_task_count, contract_pass_count),
            "new_binding_identity_rate": _rate(new_binding_count, contract_pass_count),
            "new_evidence_identity_rate": _rate(new_evidence_count, contract_pass_count),
            "task_identity_manifest_hash": canonical_hash(
                task_ids,
                prefix="refined_synthesis_task_manifest:",
            ),
            "binding_identity_manifest_hash": canonical_hash(
                binding_ids,
                prefix="refined_synthesis_binding_manifest:",
            ),
            "evidence_identity_manifest_hash": canonical_hash(
                materialized_evidence_ids,
                prefix="refined_synthesis_evidence_manifest:",
            ),
            "failure_counts": dict(sorted(failure_counts.items())),
            "status": (
                "passed"
                if success_total == requested_total
                and not failure_counts
                and self._provider.seed_effective
                else "blocked"
            ),
        }
        provisional = SynthesisMaterializationReport.model_construct(
            report_id="pending",
            **report_fields,
        )
        report = SynthesisMaterializationReport(
            report_id=synthesis_materialization_report_id(provisional),
            **report_fields,
        )
        return tuple(artifacts), report


def make_synthesis_cell_request(
    *,
    policy_update_id: str,
    cell: SynthesisCell,
    policy_allocated_count: int,
    requested_count: int,
    seed: int,
) -> SynthesisCellRequest:
    fields = {
        "policy_update_id": policy_update_id,
        "cell": cell,
        "policy_allocated_count": policy_allocated_count,
        "requested_count": requested_count,
        "seed": seed,
    }
    provisional = SynthesisCellRequest.model_construct(request_id="pending", **fields)
    return SynthesisCellRequest(
        request_id=synthesis_cell_request_id(provisional),
        **fields,
    )


def synthesis_cell_request_id(value: SynthesisCellRequest) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"request_id"}),
        prefix="synthesis_cell_request:",
    )


def synthesis_materialization_report_id(
    value: SynthesisMaterializationReport,
) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"report_id"}),
        prefix="synthesis_materialization_report:",
    )


def legacy_synthesis_materialization_report_id(
    value: SynthesisMaterializationReport,
) -> str:
    return canonical_hash(
        value.model_dump(
            mode="json",
            exclude={
                "report_id",
                "compiler_contract_hash",
                "sampling_contract_hash",
                "candidate_pool_contract_hash",
                "candidate_pool_id",
                "sampling_partition_id",
                "materialization_seed",
                "seed_effective",
                "grounding_required_sample_count",
                "grounding_checked_count",
                "grounding_pass_count",
                "grounding_failure_counts",
                "candidate_rejection_counts",
            },
        ),
        prefix="synthesis_materialization_report:",
    )


def _instantiate_candidate(
    request: SynthesisCellRequest,
    candidate: SynthesisBindingCandidate,
) -> _FeasibleSynthesisBinding:
    if candidate.pattern.pattern_id != request.cell.pattern_id:
        raise ValueError("binding candidate targets a different Pattern")
    if tuple(sorted(candidate.applied_binding_constraints)) != tuple(
        sorted(request.cell.active_binding_constraints)
    ):
        raise ValueError("binding provider did not apply the requested constraints exactly")
    if candidate.domain_plugin_set.domain != candidate.pattern.domain:
        raise ValueError("binding candidate plugin set does not match the Pattern domain")
    binding = _bind_refinement_contract(request, candidate.binding)
    instantiation = TaskPatternCompiler(
        candidate.operation_registry,
        candidate.pattern_runtime,
    ).compile(
        candidate.pattern,
        binding,
        candidate.bundle,
        candidate.proof_graph,
    )
    observed_cell = build_synthesis_cell(
        instantiation.task.public,
        candidate.corpus,
        instantiation.task.oracle.gold_evidence_ids,
        declared_tightening_options=request.cell.declared_tightening_options,
        active_binding_constraints=request.cell.active_binding_constraints,
    )
    if observed_cell != request.cell:
        raise ValueError("compiled task does not reproduce the requested synthesis Cell")
    return _FeasibleSynthesisBinding(
        request=request,
        candidate=candidate,
        binding=binding,
        instantiation=instantiation,
    )


def _compile_contract(
    feasible: _FeasibleSynthesisBinding,
) -> RefinedSynthesisArtifact:
    request = feasible.request
    candidate = feasible.candidate
    binding = feasible.binding
    instantiation = feasible.instantiation
    quality_compiler = QualityContractCompiler(
        candidate.operation_registry,
        domain_provider=candidate.quality_clause_provider,
    )
    compiled = ProofCarryingSampleCompiler(
        candidate.operation_registry,
        quality_compiler,
        candidate.domain_plugin_set,
        semantic_policy=candidate.semantic_policy,
        source_grounding_verifier=candidate.source_grounding_verifier,
    ).compile(
        instantiation.task,
        candidate.bundle,
        candidate.proof_graph,
        public_corpus=candidate.corpus,
        pattern_id=candidate.pattern.pattern_id,
        binding_id=binding.binding_id,
        metadata={
            "synthesis_cell_request_id": request.request_id,
            "policy_update_id": request.policy_update_id,
            "synthesis_cell_id": request.cell.cell_id,
            "binding_provider_candidate_id": candidate.candidate_id,
        },
    )
    return RefinedSynthesisArtifact(
        request=request,
        candidate=candidate,
        binding=binding,
        instantiation=instantiation,
        compiled=compiled,
    )


@dataclass(frozen=True)
class _GroundingResult:
    required: bool
    checked_count: int
    pass_count: int
    failure_counts: dict[str, int]

    @property
    def passed(self) -> bool:
        return not self.required or (
            self.checked_count > 0
            and self.checked_count == self.pass_count
            and not self.failure_counts
        )


def _verify_candidate_grounding(
    feasible: _FeasibleSynthesisBinding,
) -> _GroundingResult:
    requirement = feasible.instantiation.task.public.metadata.get(
        "source_grounding_requirement",
        "not_applicable",
    )
    if requirement == "not_applicable":
        return _GroundingResult(False, 0, 0, {})
    if requirement != "required":
        return _GroundingResult(True, 0, 0, {"unknown_grounding_requirement": 1})
    verifier = feasible.candidate.source_grounding_verifier
    if verifier is None:
        return _GroundingResult(True, 0, 0, {"missing_required_verifier": 1})
    failures: Counter[str] = Counter()
    passed = 0
    evidence = feasible.candidate.corpus.evidence
    if not evidence:
        return _GroundingResult(True, 0, 0, {"required_grounding_has_no_evidence": 1})
    for item in evidence:
        report = verifier.verify(item)
        if report.failures:
            failures.update(report.failures)
        else:
            passed += 1
    return _GroundingResult(
        required=True,
        checked_count=len(evidence),
        pass_count=passed,
        failure_counts=dict(sorted(failures.items())),
    )


def _bind_refinement_contract(
    request: SynthesisCellRequest,
    binding: EvidenceBinding,
) -> EvidenceBinding:
    features = {
        **binding.binding_features,
        "refinement_contract": {
            "synthesis_cell_request_id": request.request_id,
            "policy_update_id": request.policy_update_id,
            "tightening_options": request.cell.declared_tightening_options,
            "active_binding_constraints": request.cell.active_binding_constraints,
        },
    }
    return make_evidence_binding(
        pattern_id=binding.pattern_id,
        pattern_version=binding.pattern_version,
        pattern_hash=binding.pattern_hash,
        role_bindings=binding.role_bindings,
        source_graph_id=binding.source_graph_id,
        domain_snapshot_id=binding.domain_snapshot_id,
        public_slots=binding.public_slots,
        node_parameters=binding.node_parameters,
        binding_features=features,
    )


def _rate(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0.0
