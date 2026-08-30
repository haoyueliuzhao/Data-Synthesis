from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.core.evidence.schema import EvidenceBundle
from trusted_synthesis.core.graph.schema import ProofGraph
from trusted_synthesis.core.operations.registry import (
    OperationRegistry,
    operation_semantic_contract_hash,
)
from trusted_synthesis.core.task.binding import EvidenceBinding
from trusted_synthesis.core.task.pattern import TaskPatternSpec
from trusted_synthesis.core.task.pattern_compiler import (
    instantiate_pattern_program,
    validate_and_resolve_binding,
)
from trusted_synthesis.core.task.program import InputRefKind, TaskProgram
from trusted_synthesis.core.task.schema import PlanningTrack, RetrievalTrack
from trusted_synthesis.hashing import canonical_hash


class ProposalSource(str, Enum):
    CURRENT_PATTERN = "current_pattern"
    RAW_STATIC_GRAPH_PATTERN = "raw_static_graph_pattern"
    RAW_MINED_PATTERN = "raw_mined_pattern"
    RAW_TYPED_WALK = "raw_typed_walk"
    CAPABILITY_FRONTIER = "capability_frontier"


class ProposalEvidenceRole(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    role_id: str = Field(min_length=1)
    accepted_kinds: tuple[str, ...] = Field(min_length=1)
    min_count: int = Field(ge=1)
    max_count: int | None = Field(default=None, ge=1)
    semantic_constraints: tuple[str, ...] = ()
    temporal_constraints: tuple[str, ...] = ()
    scope_constraints: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_role(self) -> ProposalEvidenceRole:
        if self.max_count is not None and self.max_count < self.min_count:
            raise ValueError("proposal evidence-role maximum is below its minimum")
        if len(self.accepted_kinds) != len(set(self.accepted_kinds)):
            raise ValueError("proposal evidence role repeats an accepted kind")
        return self


class ProposalInput(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: str = Field(pattern="^(evidence_role|current_evidence|operation_node|operation_group)$")
    ref_id: str = Field(min_length=1)
    selector: str | None = None


class ProposalOperation(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    node_role_id: str = Field(min_length=1)
    operator_id: str = Field(min_length=1)
    inputs: tuple[ProposalInput, ...] = Field(min_length=1)
    parameters: dict[str, Any] = Field(default_factory=dict)
    output_schema: str = Field(min_length=1)
    foreach_evidence_role: str | None = None


class SemanticTaskProposal(BaseModel):
    """A renderer-free proposal that must be authorized before task materialization."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    proposal_id: str = Field(min_length=1)
    source: ProposalSource
    source_artifact_id: str = Field(min_length=1)
    domain: str = Field(min_length=1)
    task_family: str = Field(min_length=1)
    task_type: str = Field(min_length=1)
    evidence_roles: tuple[ProposalEvidenceRole, ...] = Field(min_length=1)
    operations: tuple[ProposalOperation, ...] = Field(min_length=1)
    output_node_role_id: str = Field(min_length=1)
    answer_schema: dict[str, Any]
    retrieval_track: RetrievalTrack
    planning_track: PlanningTrack
    semantic_constraints: tuple[str, ...] = ()
    question_intents: tuple[str, ...] = Field(min_length=1)
    mechanism_contract: dict[str, Any] = Field(default_factory=dict)
    migration_provenance: dict[str, Any] = Field(default_factory=dict)
    schema_version: str = "semantic_task_proposal.v1"

    @model_validator(mode="after")
    def validate_identity(self) -> SemanticTaskProposal:
        role_ids = [role.role_id for role in self.evidence_roles]
        if len(role_ids) != len(set(role_ids)):
            raise ValueError("semantic proposal contains duplicate evidence roles")
        node_ids = [node.node_role_id for node in self.operations]
        if len(node_ids) != len(set(node_ids)):
            raise ValueError("semantic proposal contains duplicate operation roles")
        if self.output_node_role_id not in set(node_ids):
            raise ValueError("semantic proposal output operation is missing")
        known_roles = set(role_ids)
        seen_nodes: dict[str, ProposalOperation] = {}
        for node in self.operations:
            if (
                node.foreach_evidence_role is not None
                and node.foreach_evidence_role not in known_roles
            ):
                raise ValueError("semantic proposal foreach role is not declared")
            for ref in node.inputs:
                if ref.kind == "evidence_role" and ref.ref_id not in known_roles:
                    raise ValueError("semantic proposal references an unknown evidence role")
                if ref.kind == "current_evidence":
                    if node.foreach_evidence_role is None:
                        raise ValueError("current evidence requires a foreach operation")
                    if ref.ref_id != node.foreach_evidence_role:
                        raise ValueError("current evidence does not match the foreach role")
                if ref.kind in {"operation_node", "operation_group"}:
                    target = seen_nodes.get(ref.ref_id)
                    if target is None:
                        raise ValueError("semantic proposal operation reference is not prior")
                    if ref.kind == "operation_node" and target.foreach_evidence_role is not None:
                        raise ValueError("operation_node cannot reference a foreach group")
                    if ref.kind == "operation_group" and target.foreach_evidence_role is None:
                        raise ValueError("operation_group must reference a foreach operation")
            seen_nodes[node.node_role_id] = node
        expected = canonical_hash(
            _proposal_identity(self.model_dump(mode="json", exclude={"proposal_id"})),
            prefix="semantic_task_proposal:",
        )
        if self.proposal_id != expected:
            raise ValueError("semantic proposal identity is invalid")
        return self


class CanonicalProgramInput(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: str = Field(pattern="^(evidence_role|operation)$")
    role_id: str | None = None
    role_position: int | None = Field(default=None, ge=0)
    operation_key: str | None = None
    operation_topology_key: str | None = None
    selector: str | None = None

    @model_validator(mode="after")
    def validate_target(self) -> CanonicalProgramInput:
        if self.kind == "evidence_role":
            if (
                self.role_id is None
                or self.role_position is None
                or self.operation_key is not None
                or self.operation_topology_key is not None
            ):
                raise ValueError("evidence-role input has an invalid target")
        elif (
            self.operation_key is None
            or self.operation_topology_key is None
            or self.role_id is not None
            or self.role_position is not None
        ):
            raise ValueError("operation input has an invalid target")
        return self


class CanonicalProgramNode(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    node_key: str = Field(min_length=1)
    topology_node_key: str = Field(min_length=1)
    operator_id: str = Field(min_length=1)
    inputs: tuple[CanonicalProgramInput, ...] = Field(min_length=1)
    parameters: dict[str, Any] = Field(default_factory=dict)
    output_schema: str = Field(min_length=1)
    verifier_id: str = Field(min_length=1)
    input_order_policy: str = Field(pattern="^(ordered|permutation_invariant)$")
    tool_capability: str | None = None
    operation_semantic_contract_hash: str = Field(min_length=1)
    operation_implementation_hash: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_node_keys(self) -> CanonicalProgramNode:
        topology_node_key, node_key = _canonical_program_node_keys(self)
        if self.topology_node_key != topology_node_key:
            raise ValueError("canonical Program topology node key is invalid")
        if self.node_key != node_key:
            raise ValueError("canonical Program node key is invalid")
        return self


class CanonicalSemanticPlan(BaseModel):
    """Concrete renderer-free semantics with node names and evidence IDs removed."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    plan_id: str = Field(min_length=1)
    proposal_id: str = Field(min_length=1)
    semantic_task_id: str = Field(min_length=1)
    source_program_id: str = Field(min_length=1)
    source_program_hash: str = Field(min_length=1)
    domain: str = Field(min_length=1)
    task_family: str = Field(min_length=1)
    task_type: str = Field(min_length=1)
    nodes: tuple[CanonicalProgramNode, ...] = Field(min_length=1)
    output_node_key: str = Field(min_length=1)
    output_topology_node_key: str = Field(min_length=1)
    topology_hash: str = Field(min_length=1)
    parameterized_hash: str = Field(min_length=1)
    evidence_roles: tuple[ProposalEvidenceRole, ...] = Field(min_length=1)
    answer_schema: dict[str, Any]
    retrieval_track: RetrievalTrack
    planning_track: PlanningTrack
    semantic_constraints: tuple[str, ...] = ()
    mechanism_contract: dict[str, Any] = Field(default_factory=dict)
    schema_version: str = "canonical_semantic_plan.v2"

    @model_validator(mode="after")
    def validate_hashes(self) -> CanonicalSemanticPlan:
        node_by_key = {node.node_key: node for node in self.nodes}
        topology_by_key = {node.topology_node_key: node for node in self.nodes}
        if len(node_by_key) != len(self.nodes) or len(topology_by_key) != len(self.nodes):
            raise ValueError("canonical semantic plan repeats a Program node identity")
        try:
            output_node = node_by_key[self.output_node_key]
        except KeyError as exc:
            raise ValueError("canonical semantic plan output node is absent") from exc
        if output_node.topology_node_key != self.output_topology_node_key:
            raise ValueError("canonical semantic plan output topology pair is invalid")
        role_by_id = {role.role_id: role for role in self.evidence_roles}
        dependencies: dict[str, set[str]] = {node.node_key: set() for node in self.nodes}
        for node in self.nodes:
            for item in node.inputs:
                if item.kind == "evidence_role":
                    role = role_by_id.get(str(item.role_id))
                    if role is None:
                        raise ValueError("canonical Program references an unknown evidence role")
                    if (
                        role.max_count is not None
                        and int(item.role_position or 0) >= role.max_count
                    ):
                        raise ValueError("canonical Program evidence role position exceeds maximum")
                    continue
                target = node_by_key.get(str(item.operation_key))
                if target is None:
                    raise ValueError("canonical Program references an unknown operation node")
                if target.topology_node_key != item.operation_topology_key:
                    raise ValueError("canonical Program operation/topology parent pair is invalid")
                dependencies[node.node_key].add(target.node_key)
        _validate_canonical_program_acyclic(dependencies)
        topology = _canonical_program_payload(
            self.nodes,
            self.output_node_key,
            self.output_topology_node_key,
            parameters=False,
        )
        parameterized = _canonical_program_payload(
            self.nodes,
            self.output_node_key,
            self.output_topology_node_key,
            parameters=True,
        )
        if self.topology_hash != canonical_hash(topology, prefix="program_topology:"):
            raise ValueError("canonical program topology hash is invalid")
        if self.parameterized_hash != canonical_hash(
            parameterized, prefix="parameterized_program:"
        ):
            raise ValueError("canonical parameterized program hash is invalid")
        semantic_identity = _semantic_task_identity(self.model_dump(mode="json"))
        if self.semantic_task_id != canonical_hash(semantic_identity, prefix="semantic_task:"):
            raise ValueError("semantic task identity is invalid")
        plan_identity = self.model_dump(mode="json", exclude={"plan_id"})
        if self.plan_id != canonical_hash(plan_identity, prefix="canonical_semantic_plan:"):
            raise ValueError("canonical semantic plan identity is invalid")
        return self


class BindingSnapshot(BaseModel):
    """One exact evidence/KG realization of a renderer-free semantic task."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    binding_snapshot_id: str = Field(min_length=1)
    semantic_task_id: str = Field(min_length=1)
    evidence_binding_id: str = Field(min_length=1)
    evidence_binding: EvidenceBinding
    role_bindings: dict[str, tuple[str, ...]] = Field(min_length=1)
    evidence_ids: tuple[str, ...] = Field(min_length=1)
    evidence_version_ids: tuple[str, ...] = Field(min_length=1)
    source_record_ids: tuple[str, ...] = Field(min_length=1)
    source_snapshot_ids: tuple[str, ...] = ()
    bundle_id: str = Field(min_length=1)
    bundle_hash: str = Field(min_length=1)
    proof_graph_id: str = Field(min_length=1)
    proof_graph_hash: str = Field(min_length=1)
    kg_build_id: str | None = None
    schema_version: str = "binding_snapshot.v2"

    @model_validator(mode="after")
    def validate_identity(self) -> BindingSnapshot:
        EvidenceBinding.model_validate(
            self.evidence_binding.model_dump(mode="python", warnings=False)
        )
        if self.evidence_binding_id != self.evidence_binding.binding_id:
            raise ValueError("binding snapshot crosses its EvidenceBinding identity")
        if self.role_bindings != self.evidence_binding.role_bindings:
            raise ValueError("binding snapshot role bindings cross the EvidenceBinding")
        flattened = tuple(
            evidence_id
            for role_id in sorted(self.role_bindings)
            for evidence_id in self.role_bindings[role_id]
        )
        if any(not role_id or not ids for role_id, ids in self.role_bindings.items()):
            raise ValueError("binding snapshot roles must be non-empty")
        if flattened != self.evidence_ids:
            raise ValueError("binding snapshot evidence IDs disagree with role bindings")
        if len(self.evidence_ids) != len(set(self.evidence_ids)):
            raise ValueError("binding snapshot contains duplicate evidence IDs")
        if len(self.evidence_ids) != len(self.evidence_version_ids):
            raise ValueError("binding snapshot evidence/version cardinality mismatch")
        if len(self.evidence_ids) != len(self.source_record_ids):
            raise ValueError("binding snapshot evidence/source-record cardinality mismatch")
        if any(not value for value in (*self.evidence_version_ids, *self.source_record_ids)):
            raise ValueError("binding snapshot lineage identities must be non-empty")
        expected = canonical_hash(
            self.model_dump(mode="json", exclude={"binding_snapshot_id"}),
            prefix="binding_snapshot:",
        )
        if self.binding_snapshot_id != expected:
            raise ValueError("binding snapshot identity is invalid")
        return self


class SemanticInstance(BaseModel):
    """One concrete binding-level parent for sibling surface realizations."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    semantic_instance_id: str = Field(min_length=1)
    semantic_task_id: str = Field(min_length=1)
    semantic_plan_id: str = Field(min_length=1)
    binding_snapshot_id: str = Field(min_length=1)
    schema_version: str = "semantic_instance.v1"

    @model_validator(mode="after")
    def validate_identity(self) -> SemanticInstance:
        expected = canonical_hash(
            {
                "semantic_task_id": self.semantic_task_id,
                "binding_snapshot_id": self.binding_snapshot_id,
                "schema_version": self.schema_version,
            },
            prefix="semantic_instance:",
        )
        if self.semantic_instance_id != expected:
            raise ValueError("semantic instance identity is invalid")
        return self


class SemanticBindingBundle(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    proposal: SemanticTaskProposal
    plan: CanonicalSemanticPlan
    binding: BindingSnapshot
    instance: SemanticInstance

    @model_validator(mode="after")
    def validate_lineage(self) -> SemanticBindingBundle:
        SemanticTaskProposal.model_validate(self.proposal.model_dump(mode="python", warnings=False))
        CanonicalSemanticPlan.model_validate(self.plan.model_dump(mode="python", warnings=False))
        BindingSnapshot.model_validate(self.binding.model_dump(mode="python", warnings=False))
        SemanticInstance.model_validate(self.instance.model_dump(mode="python", warnings=False))
        if self.plan.proposal_id != self.proposal.proposal_id:
            raise ValueError("canonical plan does not bind the proposal")
        if self.binding.semantic_task_id != self.plan.semantic_task_id:
            raise ValueError("binding snapshot does not bind the semantic task")
        if (
            self.instance.semantic_task_id != self.plan.semantic_task_id
            or self.instance.semantic_plan_id != self.plan.plan_id
            or self.instance.binding_snapshot_id != self.binding.binding_snapshot_id
        ):
            raise ValueError("semantic instance crosses its Plan or BindingSnapshot")
        return self


def proposal_from_pattern(
    pattern: TaskPatternSpec,
    registry: OperationRegistry,
    *,
    question_intents: tuple[str, ...] | None = None,
) -> SemanticTaskProposal:
    roles = tuple(
        ProposalEvidenceRole(
            role_id=role.role_id,
            accepted_kinds=tuple(kind.value for kind in role.accepted_kinds),
            min_count=role.min_count,
            max_count=role.max_count,
            semantic_constraints=role.semantic_constraints,
            temporal_constraints=role.temporal_constraints,
            scope_constraints=role.scope_constraints,
        )
        for role in pattern.evidence_roles
    )
    operations = tuple(
        ProposalOperation(
            node_role_id=node.node_role_id,
            operator_id=node.operator_id,
            inputs=tuple(
                ProposalInput(kind=ref.kind.value, ref_id=ref.ref_id, selector=ref.selector)
                for ref in node.input_refs
            ),
            parameters=node.parameters,
            output_schema=node.output_schema,
            foreach_evidence_role=node.foreach_evidence_role,
        )
        for node in pattern.program_template
    )
    for node in operations:
        registry.require(node.operator_id)
    payload = {
        "source": ProposalSource.CURRENT_PATTERN,
        "source_artifact_id": pattern.pattern_hash,
        "domain": pattern.domain,
        "task_family": pattern.task_type,
        "task_type": pattern.task_type,
        "evidence_roles": roles,
        "operations": operations,
        "output_node_role_id": pattern.output_node_role_id,
        "answer_schema": pattern.answer_schema,
        "retrieval_track": pattern.retrieval_track,
        "planning_track": pattern.planning_track,
        "semantic_constraints": pattern.cross_role_constraints,
        "question_intents": question_intents or (pattern.task_type,),
        "mechanism_contract": {
            "quality_profile_id": pattern.quality_profile_id,
            "source_grounding_requirement": pattern.source_grounding_requirement.value,
        },
        "migration_provenance": {
            "source_pattern_id": pattern.pattern_id,
            "source_pattern_version": pattern.pattern_version,
            "renderer_excluded_from_semantic_identity": True,
        },
        "schema_version": "semantic_task_proposal.v1",
    }
    return make_semantic_task_proposal(**payload)


def make_semantic_task_proposal(**payload: Any) -> SemanticTaskProposal:
    resolved = {
        **payload,
        "schema_version": str(payload.get("schema_version") or "semantic_task_proposal.v1"),
    }
    proposal_id = canonical_hash(
        _proposal_identity(resolved),
        prefix="semantic_task_proposal:",
    )
    return SemanticTaskProposal(proposal_id=proposal_id, **resolved)


def canonicalize_semantic_plan(
    proposal: SemanticTaskProposal,
    program: TaskProgram,
    binding: EvidenceBinding,
    registry: OperationRegistry,
    *,
    effective_answer_schema: dict[str, Any] | None = None,
) -> CanonicalSemanticPlan:
    answer_schema = effective_answer_schema or proposal.answer_schema
    evidence_roles: dict[str, tuple[str, int]] = {}
    for role_id, evidence_ids in sorted(binding.role_bindings.items()):
        for position, evidence_id in enumerate(evidence_ids):
            if evidence_id in evidence_roles:
                raise ValueError("canonical plan cannot disambiguate shared evidence roles")
            evidence_roles[evidence_id] = (role_id, position)

    structural_keys: dict[str, str] = {}
    topology_keys: dict[str, str] = {}
    nodes: list[CanonicalProgramNode] = []
    for node in program.nodes:
        definition = registry.require(node.operator_id)
        registry.validate_node_contract(node)
        inputs = []
        for ref in node.input_refs:
            if ref.kind == InputRefKind.EVIDENCE:
                try:
                    role_id, role_position = evidence_roles[ref.ref_id]
                except KeyError as exc:
                    raise ValueError(
                        f"program evidence is absent from binding roles: {ref.ref_id}"
                    ) from exc
                inputs.append(
                    CanonicalProgramInput(
                        kind="evidence_role",
                        role_id=role_id,
                        role_position=role_position,
                        selector=ref.selector,
                    )
                )
            else:
                try:
                    operation_key = structural_keys[ref.ref_id]
                    operation_topology_key = topology_keys[ref.ref_id]
                except KeyError as exc:
                    raise ValueError(
                        f"program operation is not topologically available: {ref.ref_id}"
                    ) from exc
                inputs.append(
                    CanonicalProgramInput(
                        kind="operation",
                        operation_key=operation_key,
                        operation_topology_key=operation_topology_key,
                        selector=ref.selector,
                    )
                )
        if definition.input_order_policy == "permutation_invariant":
            inputs.sort(key=lambda item: canonical_hash(item))
        topology_identity = {
            "operator_id": node.operator_id,
            "inputs": [_canonical_input_payload(item, parameters=False) for item in inputs],
            "output_schema": node.output_schema,
            "verifier_id": node.verifier_id,
            "input_order_policy": definition.input_order_policy,
            "tool_capability": definition.tool_capability,
        }
        topology_node_key = canonical_hash(
            topology_identity,
            prefix="canonical_program_topology_node:",
        )
        node_identity = {
            **topology_identity,
            "inputs": [_canonical_input_payload(item, parameters=True) for item in inputs],
            "parameters": node.parameters,
        }
        node_key = canonical_hash(node_identity, prefix="canonical_program_node:")
        structural_keys[node.node_id] = node_key
        topology_keys[node.node_id] = topology_node_key
        nodes.append(
            CanonicalProgramNode(
                node_key=node_key,
                topology_node_key=topology_node_key,
                operator_id=node.operator_id,
                inputs=tuple(inputs),
                parameters=node.parameters,
                output_schema=node.output_schema,
                verifier_id=node.verifier_id,
                input_order_policy=definition.input_order_policy,
                tool_capability=definition.tool_capability,
                operation_semantic_contract_hash=operation_semantic_contract_hash(definition),
                operation_implementation_hash=definition.implementation_hash,
            )
        )
    canonical_nodes = tuple(sorted(nodes, key=lambda item: canonical_hash(item)))
    output_node_key = structural_keys[program.output_node_id]
    output_topology_node_key = topology_keys[program.output_node_id]
    topology = _canonical_program_payload(
        canonical_nodes,
        output_node_key,
        output_topology_node_key,
        parameters=False,
    )
    parameterized = _canonical_program_payload(
        canonical_nodes,
        output_node_key,
        output_topology_node_key,
        parameters=True,
    )
    topology_hash = canonical_hash(topology, prefix="program_topology:")
    parameterized_hash = canonical_hash(parameterized, prefix="parameterized_program:")
    semantic_payload = {
        "domain": proposal.domain,
        "task_family": proposal.task_family,
        "task_type": proposal.task_type,
        "parameterized_hash": parameterized_hash,
        "evidence_roles": [role.model_dump(mode="json") for role in proposal.evidence_roles],
        "answer_schema": answer_schema,
        "retrieval_track": proposal.retrieval_track.value,
        "planning_track": proposal.planning_track.value,
        "semantic_constraints": proposal.semantic_constraints,
        "mechanism_contract": proposal.mechanism_contract,
        "schema_version": "semantic_task_identity.v2",
    }
    semantic_task_id = canonical_hash(semantic_payload, prefix="semantic_task:")
    payload = {
        "proposal_id": proposal.proposal_id,
        "semantic_task_id": semantic_task_id,
        "source_program_id": program.program_id,
        "source_program_hash": program.program_hash,
        "domain": proposal.domain,
        "task_family": proposal.task_family,
        "task_type": proposal.task_type,
        "nodes": canonical_nodes,
        "output_node_key": output_node_key,
        "output_topology_node_key": output_topology_node_key,
        "topology_hash": topology_hash,
        "parameterized_hash": parameterized_hash,
        "evidence_roles": proposal.evidence_roles,
        "answer_schema": answer_schema,
        "retrieval_track": proposal.retrieval_track,
        "planning_track": proposal.planning_track,
        "semantic_constraints": proposal.semantic_constraints,
        "mechanism_contract": proposal.mechanism_contract,
        "schema_version": "canonical_semantic_plan.v2",
    }
    plan_id = canonical_hash(_json_ready(payload), prefix="canonical_semantic_plan:")
    return CanonicalSemanticPlan(plan_id=plan_id, **payload)


def make_binding_snapshot(
    plan: CanonicalSemanticPlan,
    binding: EvidenceBinding,
    bundle: EvidenceBundle,
    proof_graph: ProofGraph,
) -> BindingSnapshot:
    if binding.source_graph_id != proof_graph.graph_id:
        raise ValueError("binding snapshot proof graph identity mismatch")
    evidence_by_id = {item.evidence_id: item for item in bundle.evidence}
    evidence_ids = tuple(
        evidence_id
        for role_id in sorted(binding.role_bindings)
        for evidence_id in binding.role_bindings[role_id]
    )
    try:
        evidence = tuple(evidence_by_id[evidence_id] for evidence_id in evidence_ids)
    except KeyError as exc:
        raise ValueError(f"binding snapshot evidence is absent from bundle: {exc.args[0]}") from exc
    if any(not proof_graph.contains_evidence(item.evidence_id) for item in evidence):
        raise ValueError("binding snapshot evidence is absent from proof graph")
    source_snapshot_ids = tuple(
        sorted(
            {
                build_id
                for item in evidence
                for build_id in item.provenance.build_ids.values()
                if build_id
            }
        )
    )
    payload = {
        "semantic_task_id": plan.semantic_task_id,
        "evidence_binding_id": binding.binding_id,
        "evidence_binding": binding,
        "role_bindings": binding.role_bindings,
        "evidence_ids": evidence_ids,
        "evidence_version_ids": tuple(item.evidence_version_id for item in evidence),
        "source_record_ids": tuple(item.provenance.source_record_id for item in evidence),
        "source_snapshot_ids": source_snapshot_ids,
        "bundle_id": bundle.bundle_id,
        "bundle_hash": bundle.bundle_hash,
        "proof_graph_id": proof_graph.graph_id,
        "proof_graph_hash": proof_graph.graph_hash,
        "kg_build_id": proof_graph.source_build_id or bundle.graph_build_id,
        "schema_version": "binding_snapshot.v2",
    }
    identity = canonical_hash(_json_ready(payload), prefix="binding_snapshot:")
    return BindingSnapshot(binding_snapshot_id=identity, **payload)


def make_semantic_instance(
    plan: CanonicalSemanticPlan,
    binding: BindingSnapshot,
) -> SemanticInstance:
    if binding.semantic_task_id != plan.semantic_task_id:
        raise ValueError("semantic instance BindingSnapshot crosses the Plan")
    payload = {
        "semantic_task_id": plan.semantic_task_id,
        "semantic_plan_id": plan.plan_id,
        "binding_snapshot_id": binding.binding_snapshot_id,
        "schema_version": "semantic_instance.v1",
    }
    instance_id = canonical_hash(
        {
            "semantic_task_id": plan.semantic_task_id,
            "binding_snapshot_id": binding.binding_snapshot_id,
            "schema_version": "semantic_instance.v1",
        },
        prefix="semantic_instance:",
    )
    return SemanticInstance(semantic_instance_id=instance_id, **payload)


def build_semantic_binding_bundle(
    *,
    pattern: TaskPatternSpec,
    program: TaskProgram,
    binding: EvidenceBinding,
    bundle: EvidenceBundle,
    proof_graph: ProofGraph,
    registry: OperationRegistry,
    question_intents: tuple[str, ...] | None = None,
    effective_answer_schema: dict[str, Any] | None = None,
) -> SemanticBindingBundle:
    validate_and_resolve_binding(pattern, binding, bundle, proof_graph)
    expected_program, _ = instantiate_pattern_program(pattern, binding, registry)
    if program != expected_program:
        raise ValueError("semantic binding Program is not authorized by Pattern and Binding")
    proposal = proposal_from_pattern(pattern, registry, question_intents=question_intents)
    plan = canonicalize_semantic_plan(
        proposal,
        program,
        binding,
        registry,
        effective_answer_schema=effective_answer_schema,
    )
    snapshot = make_binding_snapshot(plan, binding, bundle, proof_graph)
    instance = make_semantic_instance(plan, snapshot)
    return SemanticBindingBundle(
        proposal=proposal,
        plan=plan,
        binding=snapshot,
        instance=instance,
    )


def _proposal_identity(payload: dict[str, Any]) -> dict[str, Any]:
    return _json_ready(
        {
            key: value
            for key, value in payload.items()
            if key not in {"proposal_id", "migration_provenance"}
        }
    )


def _canonical_program_payload(
    nodes: tuple[CanonicalProgramNode, ...],
    output_node_key: str,
    output_topology_node_key: str,
    *,
    parameters: bool,
) -> dict[str, Any]:
    projected_nodes = []
    for node in nodes:
        projected_inputs = [
            _canonical_input_payload(item, parameters=parameters) for item in node.inputs
        ]
        if node.input_order_policy == "permutation_invariant":
            projected_inputs.sort(key=canonical_hash)
        projected_nodes.append(
            {
                "node_key": node.node_key if parameters else node.topology_node_key,
                "operator_id": node.operator_id,
                "inputs": projected_inputs,
                **({"parameters": node.parameters} if parameters else {}),
                "output_schema": node.output_schema,
                "verifier_id": node.verifier_id,
                "input_order_policy": node.input_order_policy,
                "tool_capability": node.tool_capability,
                "operation_semantic_contract_hash": (node.operation_semantic_contract_hash),
            }
        )
    return {
        "nodes": sorted(projected_nodes, key=canonical_hash),
        "output_node_key": output_node_key if parameters else output_topology_node_key,
        "schema_version": ("parameterized_program.v1" if parameters else "program_topology.v1"),
    }


def _canonical_program_node_keys(node: CanonicalProgramNode) -> tuple[str, str]:
    topology_inputs = [_canonical_input_payload(item, parameters=False) for item in node.inputs]
    parameterized_inputs = [_canonical_input_payload(item, parameters=True) for item in node.inputs]
    topology_identity = {
        "operator_id": node.operator_id,
        "inputs": topology_inputs,
        "output_schema": node.output_schema,
        "verifier_id": node.verifier_id,
        "input_order_policy": node.input_order_policy,
        "tool_capability": node.tool_capability,
    }
    topology_node_key = canonical_hash(
        topology_identity,
        prefix="canonical_program_topology_node:",
    )
    node_key = canonical_hash(
        {
            **topology_identity,
            "inputs": parameterized_inputs,
            "parameters": node.parameters,
        },
        prefix="canonical_program_node:",
    )
    return topology_node_key, node_key


def _validate_canonical_program_acyclic(dependencies: dict[str, set[str]]) -> None:
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(node_key: str) -> None:
        if node_key in visiting:
            raise ValueError("canonical Program dependency graph contains a cycle")
        if node_key in visited:
            return
        visiting.add(node_key)
        for parent_key in dependencies[node_key]:
            visit(parent_key)
        visiting.remove(node_key)
        visited.add(node_key)

    for key in dependencies:
        visit(key)


def _canonical_input_payload(
    value: CanonicalProgramInput,
    *,
    parameters: bool,
) -> dict[str, Any]:
    if value.kind == "evidence_role":
        return {
            "kind": value.kind,
            "role_id": value.role_id,
            "role_position": value.role_position,
            "selector": value.selector,
        }
    return {
        "kind": value.kind,
        "operation_key": (value.operation_key if parameters else value.operation_topology_key),
        "selector": value.selector,
    }


def _semantic_task_identity(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "domain": payload["domain"],
        "task_family": payload["task_family"],
        "task_type": payload["task_type"],
        "parameterized_hash": payload["parameterized_hash"],
        "evidence_roles": payload["evidence_roles"],
        "answer_schema": payload["answer_schema"],
        "retrieval_track": payload["retrieval_track"],
        "planning_track": payload["planning_track"],
        "semantic_constraints": payload["semantic_constraints"],
        "mechanism_contract": payload["mechanism_contract"],
        "schema_version": "semantic_task_identity.v2",
    }


def _json_ready(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_ready(item) for item in value]
    return value
