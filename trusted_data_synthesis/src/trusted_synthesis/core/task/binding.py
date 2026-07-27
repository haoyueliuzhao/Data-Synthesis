from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.hashing import canonical_hash


class EvidenceBinding(BaseModel):
    """Immutable role-to-evidence assignment for one task-pattern instantiation."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    binding_id: str = Field(min_length=1)
    binding_hash: str = Field(min_length=1)
    pattern_id: str = Field(min_length=1)
    pattern_version: str = Field(min_length=1)
    pattern_hash: str = Field(min_length=1)
    role_bindings: dict[str, tuple[str, ...]] = Field(min_length=1)
    source_graph_id: str = Field(min_length=1)
    domain_snapshot_id: str | None = None
    public_slots: dict[str, Any] = Field(default_factory=dict)
    node_parameters: dict[str, dict[str, Any]] = Field(default_factory=dict)
    binding_features: dict[str, Any] = Field(default_factory=dict)
    schema_version: str = "evidence_binding.v1"

    @model_validator(mode="after")
    def validate_identity(self) -> EvidenceBinding:
        if any(
            not role_id or not evidence_ids for role_id, evidence_ids in self.role_bindings.items()
        ):
            raise ValueError("every evidence binding role must be non-empty")
        if any(len(set(ids)) != len(ids) for ids in self.role_bindings.values()):
            raise ValueError("an evidence role cannot bind the same evidence more than once")
        expected_id, expected_hash = evidence_binding_hashes(
            pattern_id=self.pattern_id,
            pattern_version=self.pattern_version,
            pattern_hash=self.pattern_hash,
            role_bindings=self.role_bindings,
            source_graph_id=self.source_graph_id,
            domain_snapshot_id=self.domain_snapshot_id,
            public_slots=self.public_slots,
            node_parameters=self.node_parameters,
            binding_features=self.binding_features,
            schema_version=self.schema_version,
        )
        if self.binding_id != expected_id or self.binding_hash != expected_hash:
            raise ValueError("evidence binding identity or hash is invalid")
        return self

    @property
    def evidence_ids(self) -> tuple[str, ...]:
        return tuple(
            evidence_id
            for role_id in sorted(self.role_bindings)
            for evidence_id in self.role_bindings[role_id]
        )


def make_evidence_binding(
    *,
    pattern_id: str,
    pattern_version: str,
    pattern_hash: str,
    role_bindings: dict[str, tuple[str, ...]],
    source_graph_id: str,
    domain_snapshot_id: str | None = None,
    public_slots: dict[str, Any] | None = None,
    node_parameters: dict[str, dict[str, Any]] | None = None,
    binding_features: dict[str, Any] | None = None,
) -> EvidenceBinding:
    resolved_public_slots = public_slots or {}
    resolved_node_parameters = node_parameters or {}
    resolved_binding_features = binding_features or {}
    schema_version = "evidence_binding.v1"
    binding_id, binding_hash = evidence_binding_hashes(
        pattern_id=pattern_id,
        pattern_version=pattern_version,
        pattern_hash=pattern_hash,
        role_bindings=role_bindings,
        source_graph_id=source_graph_id,
        domain_snapshot_id=domain_snapshot_id,
        public_slots=resolved_public_slots,
        node_parameters=resolved_node_parameters,
        binding_features=resolved_binding_features,
        schema_version=schema_version,
    )
    return EvidenceBinding(
        binding_id=binding_id,
        binding_hash=binding_hash,
        pattern_id=pattern_id,
        pattern_version=pattern_version,
        pattern_hash=pattern_hash,
        role_bindings=role_bindings,
        source_graph_id=source_graph_id,
        domain_snapshot_id=domain_snapshot_id,
        public_slots=resolved_public_slots,
        node_parameters=resolved_node_parameters,
        binding_features=resolved_binding_features,
        schema_version=schema_version,
    )


def evidence_binding_hashes(**identity: Any) -> tuple[str, str]:
    return (
        canonical_hash(identity, prefix="evidence_binding:"),
        canonical_hash(identity, prefix="evidence_binding_hash:"),
    )
