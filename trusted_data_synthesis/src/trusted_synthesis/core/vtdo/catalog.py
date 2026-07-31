from __future__ import annotations

from collections.abc import Iterable, Mapping

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.core.trajectory.state import (
    TRAJECTORY_STATE_SCHEMA_VERSION,
    TrajectoryState,
)
from trusted_synthesis.hashing import canonical_hash

from .schema import VTDO_SCHEMA_VERSION


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class TrajectoryStateCatalog(FrozenModel):
    """Immutable state support for one task condition and verification context."""

    catalog_id: str = Field(min_length=1)
    task_condition_id: str = Field(min_length=1)
    verification_context_id: str = Field(min_length=1)
    oracle_specification_id: str = Field(min_length=1)
    mapper_schema_version: str = TRAJECTORY_STATE_SCHEMA_VERSION
    canonicalization_method: str = Field(min_length=1)
    states: dict[str, TrajectoryState] = Field(min_length=1)
    parent_catalog_id: str | None = None
    revision_reason: str = Field(min_length=1)
    schema_version: str = VTDO_SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_catalog(self) -> TrajectoryStateCatalog:
        if any(state_id != state.state_id for state_id, state in self.states.items()):
            raise ValueError("trajectory state catalog contains an invalid state key")
        if any(state.task_condition_id != self.task_condition_id for state in self.states.values()):
            raise ValueError("trajectory state catalog crosses task conditions")
        if any(
            state.verification_context_id != self.verification_context_id
            for state in self.states.values()
        ):
            raise ValueError("trajectory state catalog crosses verification contexts")
        if any(
            state.oracle_specification_id != self.oracle_specification_id
            for state in self.states.values()
        ):
            raise ValueError("trajectory state catalog crosses Oracle specifications")
        if any(
            state.schema_version != self.mapper_schema_version for state in self.states.values()
        ):
            raise ValueError("trajectory state catalog mixes mapper schema versions")
        methods = {state.canonical_graph.canonicalization_method for state in self.states.values()}
        if methods != {self.canonicalization_method}:
            raise ValueError("trajectory state catalog mixes canonicalization methods")
        if self.parent_catalog_id == self.catalog_id:
            raise ValueError("trajectory state catalog cannot be its own parent")
        if self.catalog_id != trajectory_state_catalog_id(self):
            raise ValueError("trajectory state catalog identity is invalid")
        return self


def make_trajectory_state_catalog(
    states: Iterable[TrajectoryState] | Mapping[str, TrajectoryState],
    *,
    revision_reason: str,
    parent_catalog_id: str | None = None,
) -> TrajectoryStateCatalog:
    items = tuple(states.values() if isinstance(states, Mapping) else states)
    by_id = {state.state_id: state for state in items}
    if not by_id:
        raise ValueError("trajectory state catalog requires at least one state")
    if len(by_id) != len(items):
        raise ValueError("trajectory state catalog contains duplicate state identities")
    first = next(iter(by_id.values()))
    fields = {
        "task_condition_id": first.task_condition_id,
        "verification_context_id": first.verification_context_id,
        "oracle_specification_id": first.oracle_specification_id,
        "mapper_schema_version": first.schema_version,
        "canonicalization_method": first.canonical_graph.canonicalization_method,
        "states": dict(sorted(by_id.items())),
        "parent_catalog_id": parent_catalog_id,
        "revision_reason": revision_reason,
        "schema_version": VTDO_SCHEMA_VERSION,
    }
    provisional = TrajectoryStateCatalog.model_construct(catalog_id="pending", **fields)
    return TrajectoryStateCatalog(
        catalog_id=trajectory_state_catalog_id(provisional),
        **fields,
    )


def trajectory_state_catalog_id(value: TrajectoryStateCatalog) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"catalog_id"}),
        prefix="trajectory_state_catalog:",
    )
