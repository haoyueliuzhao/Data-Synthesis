from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.core.trajectory.schema import Trajectory
from trusted_synthesis.core.trajectory.specification import OmegaComponentManifest
from trusted_synthesis.core.trajectory.state import (
    TRAJECTORY_CANONICALIZER_VERSION,
    TRAJECTORY_STATE_SCHEMA_VERSION,
    TrajectoryState,
    TrajectoryStateAssignment,
    trajectory_decision_trace_hash,
)
from trusted_synthesis.core.trajectory.validity import TrajectoryValidityReport
from trusted_synthesis.hashing import canonical_hash

from .schema import VTDO_SCHEMA_VERSION
from .state_space import (
    PublicStateCondition,
    TrajectoryStateSpaceCompilation,
    make_public_state_condition,
    observed_variation,
)


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class StateDiscoveryWitness(FrozenModel):
    """One verified trajectory proving that a quotient state was actually discovered."""

    witness_id: str = Field(min_length=1)
    state_id: str = Field(min_length=1)
    assignment_id: str = Field(min_length=1)
    trajectory: Trajectory
    decision_trace_hash: str = Field(min_length=1)
    validity_report: TrajectoryValidityReport
    schema_version: str = VTDO_SCHEMA_VERSION

    @property
    def trajectory_id(self) -> str:
        return self.trajectory.trajectory_id

    @property
    def trajectory_hash(self) -> str:
        return self.trajectory.trajectory_hash

    @property
    def validity_report_id(self) -> str:
        return self.validity_report.report_id

    @property
    def valid(self) -> bool:
        return self.validity_report.valid

    @model_validator(mode="after")
    def validate_witness(self) -> StateDiscoveryWitness:
        if (
            self.validity_report.trajectory_id != self.trajectory_id
            or self.validity_report.trajectory_hash != self.trajectory_hash
        ):
            raise ValueError("state discovery witness and validity report disagree")
        expected_trace = trajectory_decision_trace_hash(
            self.trajectory,
            program_node_aliases=self.validity_report.program_node_mapping,
        )
        if self.decision_trace_hash != expected_trace:
            raise ValueError("state discovery decision trace is invalid")
        if self.witness_id != state_discovery_witness_id(self):
            raise ValueError("state discovery witness identity is invalid")
        return self


class TrajectoryStateCatalog(FrozenModel):
    """Immutable, witnessed state support for one task condition and Omega_x."""

    catalog_id: str = Field(min_length=1)
    task_condition_id: str = Field(min_length=1)
    omega_context_id: str = Field(min_length=1)
    omega_component_manifest: OmegaComponentManifest
    mapper_schema_version: str = TRAJECTORY_STATE_SCHEMA_VERSION
    canonicalizer_version: str = TRAJECTORY_CANONICALIZER_VERSION
    canonicalization_method: str = Field(min_length=1)
    state_space_compilation: TrajectoryStateSpaceCompilation
    states: dict[str, TrajectoryState] = Field(min_length=1)
    public_state_conditions: dict[str, PublicStateCondition] = Field(min_length=1)
    discovery_witnesses: dict[str, tuple[StateDiscoveryWitness, ...]] = Field(min_length=1)
    discovery_method: str = Field(min_length=1)
    parent_catalog_id: str | None = None
    revision_reason: str = Field(min_length=1)
    schema_version: str = VTDO_SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_catalog(self) -> TrajectoryStateCatalog:
        if any(state_id != state.state_id for state_id, state in self.states.items()):
            raise ValueError("trajectory state catalog contains an invalid state key")
        if any(state.task_condition_id != self.task_condition_id for state in self.states.values()):
            raise ValueError("trajectory state catalog crosses task conditions")
        if any(state.omega_context_id != self.omega_context_id for state in self.states.values()):
            raise ValueError("trajectory state catalog crosses Omega contexts")
        if any(
            state.omega_component_manifest != self.omega_component_manifest
            for state in self.states.values()
        ):
            raise ValueError("trajectory state catalog crosses Omega component manifests")
        if any(
            state.schema_version != self.mapper_schema_version for state in self.states.values()
        ):
            raise ValueError("trajectory state catalog mixes mapper schema versions")
        if any(
            state.canonicalizer_version != self.canonicalizer_version
            for state in self.states.values()
        ):
            raise ValueError("trajectory state catalog mixes canonicalizer versions")
        methods = {state.canonical_graph.canonicalization_method for state in self.states.values()}
        if methods != {self.canonicalization_method}:
            raise ValueError("trajectory state catalog mixes canonicalization methods")
        if (
            self.state_space_compilation.omega_context_id != self.omega_context_id
            or self.state_space_compilation.omega_component_manifest
            != self.omega_component_manifest
        ):
            raise ValueError("state catalog is detached from state-space compilation")
        compiled_condition_ids = {
            condition.condition_id
            for condition in (
                self.state_space_compilation.public_conditions_by_variation_id.values()
            )
        }
        if any(
            condition.condition_id not in compiled_condition_ids
            for condition in self.public_state_conditions.values()
        ):
            raise ValueError("state catalog contains an uncompiled public condition")
        if set(self.public_state_conditions) != set(self.states):
            raise ValueError("public state conditions do not exactly cover the catalog")
        if any(
            condition.task_id != self.omega_component_manifest.task_id
            for condition in self.public_state_conditions.values()
        ):
            raise ValueError("public state condition belongs to another task")
        if set(self.discovery_witnesses) != set(self.states):
            raise ValueError("state discovery witnesses do not exactly cover the catalog")
        witnesses = tuple(
            witness
            for state_id in sorted(self.discovery_witnesses)
            for witness in self.discovery_witnesses[state_id]
        )
        if any(not items for items in self.discovery_witnesses.values()):
            raise ValueError("every state requires at least one discovery witness")
        if any(
            witness.state_id != state_id
            for state_id, items in self.discovery_witnesses.items()
            for witness in items
        ):
            raise ValueError("state discovery witness is stored under another state")
        assignment_ids = [item.assignment_id for item in witnesses]
        trajectory_ids = [item.trajectory_id for item in witnesses]
        if len(assignment_ids) != len(set(assignment_ids)):
            raise ValueError("state catalog reuses a discovery assignment")
        if len(trajectory_ids) != len(set(trajectory_ids)):
            raise ValueError("state catalog reuses a discovery trajectory")
        if any(
            witness.validity_report.context_id != self.omega_context_id
            for witness in witnesses
        ):
            raise ValueError("state discovery witness belongs to another Omega context")
        if self.parent_catalog_id == self.catalog_id:
            raise ValueError("trajectory state catalog cannot be its own parent")
        if self.catalog_id != trajectory_state_catalog_id(self):
            raise ValueError("trajectory state catalog identity is invalid")
        return self

    def discovery_trajectory_ids(self) -> frozenset[str]:
        return frozenset(
            witness.trajectory_id
            for items in self.discovery_witnesses.values()
            for witness in items
        )

    def discovery_trajectory_hashes(self) -> frozenset[str]:
        return frozenset(
            witness.trajectory_hash
            for items in self.discovery_witnesses.values()
            for witness in items
        )

    def discovery_decision_trace_hashes(self) -> frozenset[str]:
        return frozenset(
            witness.decision_trace_hash
            for items in self.discovery_witnesses.values()
            for witness in items
        )


def make_trajectory_state_catalog(
    discoveries: Iterable[
        tuple[TrajectoryStateAssignment, TrajectoryValidityReport, Trajectory]
    ],
    *,
    state_space_compilation: TrajectoryStateSpaceCompilation,
    discovery_method: str,
    revision_reason: str,
    public_conditions_by_assignment_id: Mapping[str, PublicStateCondition] | None = None,
    parent_catalog_id: str | None = None,
) -> TrajectoryStateCatalog:
    items = tuple(discoveries)
    if not items:
        raise ValueError("trajectory state catalog requires at least one verified assignment")

    by_id: dict[str, TrajectoryState] = {}
    conditions: dict[str, PublicStateCondition] = {}
    witnesses: dict[str, list[StateDiscoveryWitness]] = defaultdict(list)
    supplied_conditions = dict(public_conditions_by_assignment_id or {})
    for assignment, validity_report, trajectory in items:
        state = assignment.state
        if (
            validity_report.context_id != state.omega_context_id
            or validity_report.trajectory_id != assignment.trajectory_id
            or validity_report.trajectory_hash != assignment.trajectory_hash
            or trajectory.trajectory_id != assignment.trajectory_id
            or trajectory.trajectory_hash != assignment.trajectory_hash
        ):
            raise ValueError("state discovery validity report does not bind its assignment")
        existing = by_id.setdefault(state.state_id, state)
        if existing != state:
            raise ValueError("one state identity resolves to different state payloads")
        condition = supplied_conditions.get(assignment.assignment_id)
        if condition is None:
            condition = make_public_state_condition(
                state.omega_component_manifest.task_id,
                observed_variation(validity_report.attributes),
            )
        existing_condition = conditions.setdefault(state.state_id, condition)
        if existing_condition != condition:
            raise ValueError("one quotient state received conflicting public conditions")
        witness_values = {
            "state_id": state.state_id,
            "assignment_id": assignment.assignment_id,
            "trajectory": trajectory,
            "decision_trace_hash": trajectory_decision_trace_hash(
                trajectory,
                program_node_aliases=validity_report.program_node_mapping,
            ),
            "validity_report": validity_report,
            "schema_version": VTDO_SCHEMA_VERSION,
        }
        provisional_witness = StateDiscoveryWitness.model_construct(
            witness_id="pending",
            **witness_values,
        )
        witnesses[state.state_id].append(
            StateDiscoveryWitness(
                witness_id=state_discovery_witness_id(provisional_witness),
                **witness_values,
            )
        )

    first = next(iter(by_id.values()))
    fields = {
        "task_condition_id": first.task_condition_id,
        "omega_context_id": first.omega_context_id,
        "omega_component_manifest": first.omega_component_manifest,
        "mapper_schema_version": first.schema_version,
        "canonicalizer_version": first.canonicalizer_version,
        "canonicalization_method": first.canonical_graph.canonicalization_method,
        "state_space_compilation": state_space_compilation,
        "states": dict(sorted(by_id.items())),
        "public_state_conditions": dict(sorted(conditions.items())),
        "discovery_witnesses": {
            state_id: tuple(sorted(state_witnesses, key=lambda item: item.witness_id))
            for state_id, state_witnesses in sorted(witnesses.items())
        },
        "discovery_method": discovery_method,
        "parent_catalog_id": parent_catalog_id,
        "revision_reason": revision_reason,
        "schema_version": VTDO_SCHEMA_VERSION,
    }
    provisional = TrajectoryStateCatalog.model_construct(catalog_id="pending", **fields)
    return TrajectoryStateCatalog(
        catalog_id=trajectory_state_catalog_id(provisional),
        **fields,
    )


def state_discovery_witness_id(value: StateDiscoveryWitness) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"witness_id"}),
        prefix="state_discovery_witness:",
    )


def trajectory_state_catalog_id(value: TrajectoryStateCatalog) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"catalog_id"}),
        prefix="trajectory_state_catalog:",
    )
