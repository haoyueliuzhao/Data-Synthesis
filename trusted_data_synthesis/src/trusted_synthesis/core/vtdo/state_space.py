from __future__ import annotations

import json
from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.core.task.schema import TaskPublicSpec
from trusted_synthesis.core.trajectory.attributes import CapabilityTag, TrajectoryAttributes
from trusted_synthesis.core.trajectory.specification import (
    JointCompilationArtifact,
    OmegaComponentManifest,
    TrajectoryVerificationContext,
)
from trusted_synthesis.hashing import canonical_hash

STATE_SPACE_CONTRACT_VERSION = "trajectory_state_space.v3"

AcquisitionRequirement = Literal["none", "bounded", "expanded", "multi_stage"]
EvidenceSupportRequirement = Literal["required_roles", "expanded_context"]
ExecutionRequirement = Literal[
    "program_equivalent",
    "independent_reordering",
    "equivalent_tool",
    "composed_execution",
]
VerificationRequirement = Literal["none", "output", "intermediate", "full"]
LineageRequirement = Literal["direct", "citation_minimum", "output_upstream", "full"]
RetrievalElaboration = Literal[
    "unconstrained",
    "required_only",
    "semantic_context",
    "full_corpus",
]
ExecutionElaboration = Literal[
    "unconstrained",
    "baseline_program",
    "program_projection",
    "transparent_projection",
]


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class AdmissibleTrajectoryVariation(FrozenModel):
    """Domain-neutral behavior constraints compiled by a domain or experiment plugin."""

    variation_id: str = Field(min_length=1)
    acquisition_requirement: AcquisitionRequirement
    evidence_support_requirement: EvidenceSupportRequirement
    execution_requirement: ExecutionRequirement
    verification_requirement: VerificationRequirement
    lineage_requirement: LineageRequirement
    retrieval_elaboration: RetrievalElaboration = "unconstrained"
    execution_elaboration: ExecutionElaboration = "unconstrained"
    required_capabilities: tuple[CapabilityTag, ...] = ()
    minimum_tool_calls: int = Field(default=0, ge=0)
    minimum_evidence_count: int = Field(default=0, ge=0)
    minimum_reasoning_depth: int = Field(default=0, ge=0)
    minimum_verification_degree: float = Field(default=0.0, ge=0.0, le=1.0)
    schema_version: str = STATE_SPACE_CONTRACT_VERSION

    @model_validator(mode="after")
    def validate_variation(self) -> AdmissibleTrajectoryVariation:
        if len(self.required_capabilities) != len(set(self.required_capabilities)):
            raise ValueError("trajectory variation capabilities must be unique")
        if self.variation_id != admissible_trajectory_variation_id(self):
            raise ValueError("admissible trajectory variation identity is invalid")
        return self


class TrajectoryVariationProviderProtocol(Protocol):
    """Translate domain semantics into domain-neutral admissible variations."""

    variation_provider_id: str
    variation_provider_version: str

    def compile_variations(
        self,
        context: TrajectoryVerificationContext,
    ) -> tuple[AdmissibleTrajectoryVariation, ...]: ...


class PublicStateCondition(FrozenModel):
    """Safe model-visible projection of a host-only quotient-state target."""

    condition_id: str = Field(min_length=1)
    task_id: str = Field(min_length=1)
    acquisition_requirement: AcquisitionRequirement
    evidence_support_requirement: EvidenceSupportRequirement
    execution_requirement: ExecutionRequirement
    verification_requirement: VerificationRequirement
    lineage_requirement: LineageRequirement
    retrieval_elaboration: RetrievalElaboration = "unconstrained"
    execution_elaboration: ExecutionElaboration = "unconstrained"
    required_capabilities: tuple[CapabilityTag, ...] = ()
    minimum_tool_calls: int = Field(default=0, ge=0)
    minimum_evidence_count: int = Field(default=0, ge=0)
    minimum_reasoning_depth: int = Field(default=0, ge=0)
    minimum_verification_degree: float = Field(default=0.0, ge=0.0, le=1.0)
    forbidden_surface_template: bool = True
    schema_version: str = STATE_SPACE_CONTRACT_VERSION

    @model_validator(mode="after")
    def validate_condition(self) -> PublicStateCondition:
        if len(self.required_capabilities) != len(set(self.required_capabilities)):
            raise ValueError("public state capabilities must be unique")
        if not self.forbidden_surface_template:
            raise ValueError("public state conditions cannot prescribe a surface template")
        if self.condition_id != public_state_condition_id(self):
            raise ValueError("public state condition identity is invalid")
        return self


class TrajectoryStateSpaceCompilation(FrozenModel):
    compilation_id: str = Field(min_length=1)
    joint_compilation: JointCompilationArtifact
    variation_provider_id: str = Field(min_length=1)
    variation_provider_version: str = Field(min_length=1)
    variations: tuple[AdmissibleTrajectoryVariation, ...] = Field(min_length=1)
    public_conditions_by_variation_id: dict[str, PublicStateCondition] = Field(min_length=1)
    schema_version: str = STATE_SPACE_CONTRACT_VERSION

    @property
    def joint_compilation_artifact_id(self) -> str:
        return self.joint_compilation.artifact_id

    @property
    def omega_context_id(self) -> str:
        return self.joint_compilation.omega.context_id

    @property
    def omega_component_manifest(self) -> OmegaComponentManifest:
        return self.joint_compilation.component_manifest

    @model_validator(mode="after")
    def validate_compilation(self) -> TrajectoryStateSpaceCompilation:
        variation_ids = tuple(item.variation_id for item in self.variations)
        if len(variation_ids) != len(set(variation_ids)):
            raise ValueError("state-space compilation contains duplicate variations")
        if set(self.public_conditions_by_variation_id) != set(variation_ids):
            raise ValueError("state-space conditions do not exactly cover variations")
        expected_conditions = {
            variation.variation_id: make_public_state_condition(
                self.joint_compilation.component_manifest.task_id,
                variation,
            )
            for variation in self.variations
        }
        if self.public_conditions_by_variation_id != expected_conditions:
            raise ValueError("state-space public conditions do not replay variations")
        if any(
            condition.task_id != self.joint_compilation.component_manifest.task_id
            for condition in self.public_conditions_by_variation_id.values()
        ):
            raise ValueError("state-space compilation crosses task conditions")
        if self.compilation_id != trajectory_state_space_compilation_id(self):
            raise ValueError("trajectory state-space compilation identity is invalid")
        return self


class PublicStateGenerationRequest(FrozenModel):
    """The only state-conditioned request that a model-facing provider may receive."""

    request_id: str = Field(min_length=1)
    task_public: TaskPublicSpec
    public_corpus_id: str = Field(min_length=1)
    public_corpus_hash: str = Field(min_length=1)
    state_condition: PublicStateCondition
    allowed_tools: tuple[str, ...] = Field(min_length=1)
    candidate_count: int = Field(ge=1)
    seed: int
    schema_version: str = STATE_SPACE_CONTRACT_VERSION

    @model_validator(mode="after")
    def validate_request(self) -> PublicStateGenerationRequest:
        if self.state_condition.task_id != self.task_public.task_id:
            raise ValueError("public state condition belongs to another task")
        if self.allowed_tools != tuple(sorted(self.task_public.allowed_tools)):
            raise ValueError("public generation tools disagree with the public task")
        if self.request_id != public_state_generation_request_id(self):
            raise ValueError("public state generation request identity is invalid")
        return self


class PublicStateLeakageAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    request_id: str = Field(min_length=1)
    passed: bool
    leaked_secret_labels: tuple[str, ...] = ()
    schema_version: str = STATE_SPACE_CONTRACT_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> PublicStateLeakageAudit:
        expected_passed = not self.leaked_secret_labels
        if self.passed != expected_passed:
            raise ValueError("public state leakage status is inconsistent")
        if self.audit_id != public_state_leakage_audit_id(self):
            raise ValueError("public state leakage audit identity is invalid")
        return self


def make_admissible_trajectory_variation(
    *,
    acquisition_requirement: AcquisitionRequirement,
    evidence_support_requirement: EvidenceSupportRequirement,
    execution_requirement: ExecutionRequirement = "program_equivalent",
    verification_requirement: VerificationRequirement = "output",
    lineage_requirement: LineageRequirement = "direct",
    retrieval_elaboration: RetrievalElaboration = "unconstrained",
    execution_elaboration: ExecutionElaboration = "unconstrained",
    required_capabilities: tuple[CapabilityTag, ...] = (),
    minimum_tool_calls: int = 0,
    minimum_evidence_count: int = 0,
    minimum_reasoning_depth: int = 0,
    minimum_verification_degree: float = 0.0,
) -> AdmissibleTrajectoryVariation:
    values = {
        "acquisition_requirement": acquisition_requirement,
        "evidence_support_requirement": evidence_support_requirement,
        "execution_requirement": execution_requirement,
        "verification_requirement": verification_requirement,
        "lineage_requirement": lineage_requirement,
        "retrieval_elaboration": retrieval_elaboration,
        "execution_elaboration": execution_elaboration,
        "required_capabilities": tuple(sorted(required_capabilities)),
        "minimum_tool_calls": minimum_tool_calls,
        "minimum_evidence_count": minimum_evidence_count,
        "minimum_reasoning_depth": minimum_reasoning_depth,
        "minimum_verification_degree": minimum_verification_degree,
        "schema_version": STATE_SPACE_CONTRACT_VERSION,
    }
    provisional = AdmissibleTrajectoryVariation.model_construct(variation_id="pending", **values)
    return AdmissibleTrajectoryVariation(
        variation_id=admissible_trajectory_variation_id(provisional), **values
    )


def observed_variation(attributes: TrajectoryAttributes) -> AdmissibleTrajectoryVariation:
    capabilities = set(attributes.capability_tags)
    acquisition: AcquisitionRequirement = "bounded" if "retrieval" in capabilities else "none"
    verification: VerificationRequirement
    if attributes.verification_degree == 0:
        verification = "none"
    elif attributes.verification_degree < 1:
        verification = "intermediate"
    else:
        verification = "full"
    lineage: LineageRequirement = "citation_minimum" if "citation" in capabilities else "direct"
    return make_admissible_trajectory_variation(
        acquisition_requirement=acquisition,
        evidence_support_requirement="required_roles",
        verification_requirement=verification,
        lineage_requirement=lineage,
        required_capabilities=attributes.capability_tags,
        minimum_tool_calls=attributes.tool_call_count,
        minimum_evidence_count=attributes.evidence_dependency_count,
        minimum_reasoning_depth=attributes.reasoning_depth,
        minimum_verification_degree=attributes.verification_degree,
    )


def make_public_state_condition(
    task_id: str,
    variation: AdmissibleTrajectoryVariation,
) -> PublicStateCondition:
    values = {
        "task_id": task_id,
        "acquisition_requirement": variation.acquisition_requirement,
        "evidence_support_requirement": variation.evidence_support_requirement,
        "execution_requirement": variation.execution_requirement,
        "verification_requirement": variation.verification_requirement,
        "lineage_requirement": variation.lineage_requirement,
        "retrieval_elaboration": variation.retrieval_elaboration,
        "execution_elaboration": variation.execution_elaboration,
        "required_capabilities": variation.required_capabilities,
        "minimum_tool_calls": variation.minimum_tool_calls,
        "minimum_evidence_count": variation.minimum_evidence_count,
        "minimum_reasoning_depth": variation.minimum_reasoning_depth,
        "minimum_verification_degree": variation.minimum_verification_degree,
        "forbidden_surface_template": True,
        "schema_version": STATE_SPACE_CONTRACT_VERSION,
    }
    provisional = PublicStateCondition.model_construct(condition_id="pending", **values)
    return PublicStateCondition(condition_id=public_state_condition_id(provisional), **values)


def compile_trajectory_state_space(
    joint_compilation: JointCompilationArtifact,
    provider: TrajectoryVariationProviderProtocol,
) -> TrajectoryStateSpaceCompilation:
    variations = tuple(provider.compile_variations(joint_compilation.omega))
    if not variations:
        raise ValueError("state-space compilation requires at least one variation")
    conditions = {
        variation.variation_id: make_public_state_condition(
            joint_compilation.omega.task.task_id,
            variation,
        )
        for variation in variations
    }
    values = {
        "joint_compilation": joint_compilation,
        "variation_provider_id": provider.variation_provider_id,
        "variation_provider_version": provider.variation_provider_version,
        "variations": variations,
        "public_conditions_by_variation_id": dict(sorted(conditions.items())),
        "schema_version": STATE_SPACE_CONTRACT_VERSION,
    }
    provisional = TrajectoryStateSpaceCompilation.model_construct(
        compilation_id="pending",
        **values,
    )
    return TrajectoryStateSpaceCompilation(
        compilation_id=trajectory_state_space_compilation_id(provisional),
        **values,
    )


def make_public_state_generation_request(
    context: TrajectoryVerificationContext,
    condition: PublicStateCondition,
    *,
    candidate_count: int,
    seed: int,
) -> PublicStateGenerationRequest:
    if condition.task_id != context.task.task_id:
        raise ValueError("cannot project a state condition across tasks")
    values = {
        "task_public": context.task.public,
        "public_corpus_id": context.public_corpus.corpus_id,
        "public_corpus_hash": context.public_corpus.corpus_hash,
        "state_condition": condition,
        "allowed_tools": tuple(sorted(context.task.public.allowed_tools)),
        "candidate_count": candidate_count,
        "seed": seed,
        "schema_version": STATE_SPACE_CONTRACT_VERSION,
    }
    provisional = PublicStateGenerationRequest.model_construct(request_id="pending", **values)
    request = PublicStateGenerationRequest(
        request_id=public_state_generation_request_id(provisional), **values
    )
    audit = audit_public_state_generation_request(request, context)
    if not audit.passed:
        raise ValueError(
            "public state generation request leaks host-only fields: "
            + ",".join(audit.leaked_secret_labels)
        )
    return request


def audit_public_state_generation_request(
    request: PublicStateGenerationRequest,
    context: TrajectoryVerificationContext,
) -> PublicStateLeakageAudit:
    serialized = json.dumps(request.model_dump(mode="json"), ensure_ascii=False, sort_keys=True)
    public_serialized = json.dumps(
        context.task.public.model_dump(mode="json"), ensure_ascii=False, sort_keys=True
    )
    secrets = {
        "omega_context_id": context.context_id,
        "oracle_specification_id": context.oracle_specification.specification_id,
        "evidence_bundle_id": context.evidence_bundle.bundle_id,
        "evidence_bundle_hash": context.evidence_bundle.bundle_hash,
        "proof_graph_id": context.proof_graph.graph_id,
        "proof_graph_hash": context.proof_graph.graph_hash,
        "task_program_id": context.task.oracle.task_program.program_id,
        "task_program_hash": context.task.oracle.task_program.program_hash,
        "quality_contract_id": context.quality_contract.contract_id,
        "quality_contract_hash": context.quality_contract.contract_hash,
    }
    secrets.update(
        {
            f"gold_evidence_id:{index}": value
            for index, value in enumerate(context.task.oracle.gold_evidence_ids)
        }
    )
    secrets.update(
        {
            f"reference_trajectory_id:{index}": value
            for index, value in enumerate(context.oracle_specification.reference_example_ids)
        }
    )
    leaked = tuple(
        sorted(
            label
            for label, secret in secrets.items()
            if secret and secret in serialized and secret not in public_serialized
        )
    )
    values = {
        "request_id": request.request_id,
        "passed": not leaked,
        "leaked_secret_labels": leaked,
        "schema_version": STATE_SPACE_CONTRACT_VERSION,
    }
    provisional = PublicStateLeakageAudit.model_construct(audit_id="pending", **values)
    return PublicStateLeakageAudit(audit_id=public_state_leakage_audit_id(provisional), **values)


def admissible_trajectory_variation_id(value: AdmissibleTrajectoryVariation) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"variation_id"}),
        prefix="admissible_trajectory_variation:",
    )


def public_state_condition_id(value: PublicStateCondition) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"condition_id"}),
        prefix="public_state_condition:",
    )


def trajectory_state_space_compilation_id(
    value: TrajectoryStateSpaceCompilation,
) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"compilation_id"}),
        prefix="trajectory_state_space_compilation:",
    )


def public_state_generation_request_id(value: PublicStateGenerationRequest) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"request_id"}),
        prefix="public_state_generation_request:",
    )


def public_state_leakage_audit_id(value: PublicStateLeakageAudit) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"audit_id"}),
        prefix="public_state_leakage_audit:",
    )
