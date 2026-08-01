from __future__ import annotations

import math
from collections import Counter
from itertools import islice
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.core.trajectory.schema import Trajectory
from trusted_synthesis.core.trajectory.specification import (
    TrajectoryVerificationContext,
    make_omega_component_manifest,
)
from trusted_synthesis.core.trajectory.state import (
    TrajectoryState,
    TrajectoryStateAssignment,
    map_trajectory_to_state,
    trajectory_decision_trace_hash,
)
from trusted_synthesis.core.trajectory.validity import (
    TrajectoryValidityEvaluator,
    TrajectoryValidityReport,
)
from trusted_synthesis.hashing import canonical_hash

from .catalog import TrajectoryStateCatalog
from .explorer import StateConditionedTrajectoryProviderProtocol
from .schema import (
    VTDO_SCHEMA_VERSION,
    ConditionalTrajectoryDistribution,
    VTDORoleContract,
)
from .state_space import (
    PublicStateGenerationRequest,
    PublicStateLeakageAudit,
    audit_public_state_generation_request,
    make_public_state_generation_request,
)


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class StateConditionedTrainingArtifact(FrozenModel):
    """One released training trajectory carrying its task, Omega, and target state."""

    artifact_id: str = Field(min_length=1)
    context: TrajectoryVerificationContext
    target_state: TrajectoryState
    trajectory: Trajectory
    validity_report: TrajectoryValidityReport
    assignment: TrajectoryStateAssignment
    state_catalog_id: str = Field(min_length=1)
    source_distribution_id: str = Field(min_length=1)
    role_contract_id: str = Field(min_length=1)
    materialization_provider_id: str = Field(min_length=1)
    public_request_id: str = Field(min_length=1)
    decision_trace_hash: str = Field(min_length=1)
    generation_phase: Literal["distribution_materialization"] = (
        "distribution_materialization"
    )
    schema_version: str = VTDO_SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_artifact(self) -> StateConditionedTrainingArtifact:
        if self.target_state.omega_context_id != self.context.context_id:
            raise ValueError("training target state belongs to another Omega context")
        if self.trajectory.task_id != self.context.task.task_id:
            raise ValueError("training trajectory belongs to another task")
        if not self.validity_report.valid:
            raise ValueError("training artifact cannot carry an invalid trajectory")
        if (
            self.validity_report.context_id != self.context.context_id
            or self.validity_report.trajectory_id != self.trajectory.trajectory_id
            or self.validity_report.trajectory_hash != self.trajectory.trajectory_hash
        ):
            raise ValueError("training validity report has another trajectory")
        if self.assignment.trajectory_hash != self.trajectory.trajectory_hash:
            raise ValueError("training assignment has another trajectory hash")
        if self.assignment.state != self.target_state:
            raise ValueError("training trajectory missed its requested quotient state")
        if self.target_state.omega_component_manifest != (
            self.assignment.state.omega_component_manifest
        ):
            raise ValueError("training trajectory crossed Omega component manifests")
        expected_trace = trajectory_decision_trace_hash(
            self.trajectory,
            program_node_aliases=self.validity_report.program_node_mapping,
        )
        if self.decision_trace_hash != expected_trace:
            raise ValueError("training decision trace hash is invalid")
        if self.artifact_id != state_conditioned_training_artifact_id(self):
            raise ValueError("state-conditioned training artifact identity is invalid")
        return self


class TrajectoryStateMaterializationReport(FrozenModel):
    report_id: str = Field(min_length=1)
    explorer_provider_id: str = Field(min_length=1)
    materialization_provider_id: str = Field(min_length=1)
    materialization_provider_version: str = Field(min_length=1)
    context_id: str = Field(min_length=1)
    state_catalog_id: str = Field(min_length=1)
    source_distribution_id: str = Field(min_length=1)
    role_contract_id: str = Field(min_length=1)
    seed: int
    maximum_attempt_multiplier: int = Field(ge=1)
    requested_state_counts: dict[str, int] = Field(min_length=1)
    attempted_state_counts: dict[str, int] = Field(min_length=1)
    off_target_state_counts: dict[str, int] = Field(min_length=1)
    attempted_trajectory_count: int = Field(ge=0)
    released_state_counts: dict[str, int] = Field(min_length=1)
    public_state_requests: dict[str, PublicStateGenerationRequest] = Field(default_factory=dict)
    public_state_leakage_audits: dict[str, PublicStateLeakageAudit] = Field(default_factory=dict)
    source_state_distribution: dict[str, float] = Field(min_length=1)
    target_state_distribution: dict[str, float] = Field(min_length=1)
    released_state_distribution: dict[str, float] = Field(min_length=1)
    released_budget_shares: dict[str, float] = Field(min_length=1)
    allocation_total_variation: float = Field(ge=0, le=1)
    distribution_total_variation: float = Field(ge=0, le=1)
    jensen_shannon_divergence: float = Field(ge=0, le=1)
    distribution_fidelity_error: float = Field(ge=0)
    quota_fill_rate: float = Field(ge=0, le=1)
    generation_acceptance_rate: float = Field(ge=0, le=1)
    state_acceptance_rates: dict[str, float] = Field(min_length=1)
    state_off_target_rates: dict[str, float] = Field(min_length=1)
    minimum_support_floor_applied: bool
    finite_budget_support_truncation: bool
    unique_decision_trace_count: int = Field(ge=0)
    independent_regeneration_enforced: Literal[True] = True
    artifacts: tuple[StateConditionedTrainingArtifact, ...] = ()
    failure_counts: dict[str, int] = Field(default_factory=dict)
    status: Literal["passed", "blocked"]
    schema_version: str = VTDO_SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_report(self) -> TrajectoryStateMaterializationReport:
        support = set(self.requested_state_counts)
        maps = (
            self.attempted_state_counts,
            self.off_target_state_counts,
            self.released_state_counts,
            self.source_state_distribution,
            self.target_state_distribution,
            self.released_state_distribution,
            self.released_budget_shares,
            self.state_acceptance_rates,
            self.state_off_target_rates,
        )
        if any(set(item) != support for item in maps):
            raise ValueError("materialization metrics do not share one state support")
        if any(count < 0 for count in self.requested_state_counts.values()):
            raise ValueError("materialization request counts cannot be negative")
        if any(
            self.off_target_state_counts[state_id] > self.attempted_state_counts[state_id]
            or self.released_state_counts[state_id] > self.attempted_state_counts[state_id]
            for state_id in support
        ):
            raise ValueError("materialization state counts are inconsistent")
        total_requested = sum(self.requested_state_counts.values())
        total_attempted = sum(self.attempted_state_counts.values())
        total_released = sum(self.released_state_counts.values())
        if total_requested < 1 or total_attempted != self.attempted_trajectory_count:
            raise ValueError("materialization total counts are inconsistent")
        if not math.isclose(sum(self.source_state_distribution.values()), 1.0, abs_tol=1e-9):
            raise ValueError("source state distribution is not normalized")
        positive_states = {
            state_id for state_id, count in self.requested_state_counts.items() if count > 0
        }
        if set(self.public_state_requests) != positive_states:
            raise ValueError("materialization public requests do not cover positive quotas")
        if set(self.public_state_leakage_audits) != positive_states:
            raise ValueError("materialization leakage audits do not cover positive quotas")
        if any(not audit.passed for audit in self.public_state_leakage_audits.values()):
            raise ValueError("materialization contains a leaking public request")
        if any(
            audit.request_id != self.public_state_requests[state_id].request_id
            for state_id, audit in self.public_state_leakage_audits.items()
        ):
            raise ValueError("materialization leakage audit binds another request")

        expected_target = {
            state_id: count / total_requested
            for state_id, count in self.requested_state_counts.items()
        }
        expected_budget_shares = {
            state_id: count / total_requested
            for state_id, count in self.released_state_counts.items()
        }
        expected_released = (
            {
                state_id: count / total_released
                for state_id, count in self.released_state_counts.items()
            }
            if total_released
            else {state_id: 0.0 for state_id in support}
        )
        if not _probability_maps_close(self.target_state_distribution, expected_target):
            raise ValueError("materialization target distribution is inconsistent")
        if not _probability_maps_close(self.released_budget_shares, expected_budget_shares):
            raise ValueError("materialization released budget shares are inconsistent")
        if not _probability_maps_close(self.released_state_distribution, expected_released):
            raise ValueError("materialization released distribution is inconsistent")
        expected_allocation_tv = _total_variation(
            self.source_state_distribution, expected_target
        )
        expected_release_tv = (
            _total_variation(expected_target, expected_released) if total_released else 1.0
        )
        expected_js = (
            _jensen_shannon(expected_target, expected_released) if total_released else 1.0
        )
        if not math.isclose(
            self.allocation_total_variation, expected_allocation_tv, abs_tol=1e-12
        ):
            raise ValueError("materialization allocation TV is inconsistent")
        if not math.isclose(
            self.distribution_total_variation, expected_release_tv, abs_tol=1e-12
        ):
            raise ValueError("materialization release TV is inconsistent")
        if not math.isclose(self.jensen_shannon_divergence, expected_js, abs_tol=1e-12):
            raise ValueError("materialization JS divergence is inconsistent")
        expected_error = sum(
            abs(expected_target[state_id] - expected_budget_shares[state_id])
            for state_id in expected_target
        )
        if not math.isclose(self.distribution_fidelity_error, expected_error, abs_tol=1e-12):
            raise ValueError("materialization distribution fidelity is inconsistent")
        if not math.isclose(self.quota_fill_rate, total_released / total_requested, abs_tol=1e-12):
            raise ValueError("materialization quota fill rate is inconsistent")
        expected_acceptance = total_released / total_attempted if total_attempted else 0.0
        if not math.isclose(
            self.generation_acceptance_rate, expected_acceptance, abs_tol=1e-12
        ):
            raise ValueError("materialization acceptance rate is inconsistent")
        for state_id in support:
            attempts = self.attempted_state_counts[state_id]
            acceptance = self.released_state_counts[state_id] / attempts if attempts else 0.0
            off_target = self.off_target_state_counts[state_id] / attempts if attempts else 0.0
            if not math.isclose(
                self.state_acceptance_rates[state_id], acceptance, abs_tol=1e-12
            ):
                raise ValueError("state acceptance rate is inconsistent")
            if not math.isclose(
                self.state_off_target_rates[state_id], off_target, abs_tol=1e-12
            ):
                raise ValueError("state off-target rate is inconsistent")
        expected_floor = total_requested >= len(support)
        expected_truncation = any(
            self.source_state_distribution[state_id] > 0
            and self.requested_state_counts[state_id] == 0
            for state_id in support
        )
        if self.minimum_support_floor_applied != expected_floor:
            raise ValueError("minimum support floor status is inconsistent")
        if self.finite_budget_support_truncation != expected_truncation:
            raise ValueError("finite-budget support truncation is inconsistent")

        observed = Counter(item.target_state.state_id for item in self.artifacts)
        if dict(sorted(observed.items())) != {
            state_id: count
            for state_id, count in sorted(self.released_state_counts.items())
            if count
        }:
            raise ValueError("materialization artifacts disagree with released counts")
        traces = [item.decision_trace_hash for item in self.artifacts]
        if len(traces) != len(set(traces)):
            raise ValueError("materialization artifacts contain duplicate decision traces")
        if self.unique_decision_trace_count != len(set(traces)):
            raise ValueError("materialization decision-trace count is inconsistent")
        if any(item.context.context_id != self.context_id for item in self.artifacts):
            raise ValueError("materialization artifacts cross verification contexts")
        if any(
            item.source_distribution_id != self.source_distribution_id
            or item.role_contract_id != self.role_contract_id
            or item.state_catalog_id != self.state_catalog_id
            or item.materialization_provider_id != self.materialization_provider_id
            or item.public_request_id
            != self.public_state_requests[item.target_state.state_id].request_id
            for item in self.artifacts
        ):
            raise ValueError("materialization artifacts cross frozen contracts")
        exact = (
            self.released_state_counts == self.requested_state_counts
            and math.isclose(self.distribution_fidelity_error, 0.0, abs_tol=1e-12)
            and math.isclose(self.distribution_total_variation, 0.0, abs_tol=1e-12)
        )
        expected_status: Literal["passed", "blocked"] = "passed" if exact else "blocked"
        if self.status != expected_status:
            raise ValueError("materialization status is inconsistent")
        if self.report_id != trajectory_state_materialization_report_id(self):
            raise ValueError("trajectory-state materialization report identity is invalid")
        return self


class ValidTrajectoryStateMaterializer:
    """Materialize pi_(t+1) as independently verified on-target trajectories."""

    def __init__(
        self,
        provider: StateConditionedTrajectoryProviderProtocol,
        evaluator: TrajectoryValidityEvaluator,
    ) -> None:
        self._provider = provider
        self._evaluator = evaluator

    def materialize(
        self,
        context: TrajectoryVerificationContext,
        state_catalog: TrajectoryStateCatalog,
        distribution: ConditionalTrajectoryDistribution,
        role_contract: VTDORoleContract,
        *,
        total_budget: int,
        seed: int,
        maximum_attempt_multiplier: int = 3,
    ) -> tuple[tuple[StateConditionedTrainingArtifact, ...], TrajectoryStateMaterializationReport]:
        if total_budget < 1:
            raise ValueError("trajectory-state materialization budget must be positive")
        if maximum_attempt_multiplier < 1:
            raise ValueError("materialization attempt multiplier must be positive")
        if self._provider.provider_id != role_contract.materialization_provider_id:
            raise ValueError("materialization provider violates the VTDO role contract")
        if state_catalog.omega_context_id != context.context_id:
            raise ValueError("materialization catalog belongs to another Omega context")
        if state_catalog.omega_component_manifest != make_omega_component_manifest(context):
            raise ValueError("materialization catalog has another Omega component manifest")
        if distribution.task_condition_id != state_catalog.task_condition_id:
            raise ValueError("materialization distribution crosses task conditions")
        if not set(distribution.probabilities) <= set(state_catalog.states):
            raise ValueError("materialization distribution contains an unknown state")

        requested = allocate_materialization_budget(distribution, total_budget)
        released: list[StateConditionedTrainingArtifact] = []
        released_counts = {state_id: 0 for state_id in requested}
        attempted_counts = {state_id: 0 for state_id in requested}
        off_target_counts = {state_id: 0 for state_id in requested}
        public_requests: dict[str, PublicStateGenerationRequest] = {}
        leakage_audits: dict[str, PublicStateLeakageAudit] = {}
        failures: Counter[str] = Counter()
        attempted = 0
        seen_trajectory_ids: set[str] = set()
        seen_decision_trace_hashes: set[str] = set()
        discovery_trajectory_ids = state_catalog.discovery_trajectory_ids()
        discovery_trajectory_hashes = state_catalog.discovery_trajectory_hashes()
        discovery_decision_trace_hashes = state_catalog.discovery_decision_trace_hashes()
        for state_id in sorted(requested):
            target_count = requested[state_id]
            if target_count == 0:
                continue
            target_state = state_catalog.states[state_id]
            attempt_budget = target_count * maximum_attempt_multiplier
            request = make_public_state_generation_request(
                context,
                state_catalog.public_state_conditions[state_id],
                candidate_count=attempt_budget,
                seed=_state_seed(seed, state_id),
            )
            public_requests[state_id] = request
            leakage_audits[state_id] = audit_public_state_generation_request(request, context)
            try:
                candidates = islice(self._provider.generate(request), attempt_budget)
                for trajectory in candidates:
                    if released_counts[state_id] >= target_count:
                        break
                    attempted += 1
                    attempted_counts[state_id] += 1
                    if (
                        trajectory.trajectory_id in discovery_trajectory_ids
                        or trajectory.trajectory_hash in discovery_trajectory_hashes
                    ):
                        failures["discovery_trajectory_reuse"] += 1
                        continue
                    if trajectory.trajectory_id in seen_trajectory_ids:
                        failures["duplicate_trajectory"] += 1
                        continue
                    seen_trajectory_ids.add(trajectory.trajectory_id)
                    try:
                        report = self._evaluator.evaluate(context, trajectory)
                    except Exception:
                        failures["verification_error"] += 1
                        continue
                    if not report.valid:
                        failures["invalid_trajectory"] += 1
                        continue
                    decision_trace = trajectory_decision_trace_hash(
                        trajectory,
                        program_node_aliases=report.program_node_mapping,
                    )
                    if decision_trace in discovery_decision_trace_hashes:
                        failures["discovery_decision_trace_reuse"] += 1
                        continue
                    if decision_trace in seen_decision_trace_hashes:
                        failures["duplicate_decision_trace"] += 1
                        continue
                    seen_decision_trace_hashes.add(decision_trace)
                    try:
                        assignment = map_trajectory_to_state(
                            context,
                            trajectory,
                            task_condition_id=distribution.task_condition_id,
                            program_node_aliases=report.program_node_mapping,
                        )
                    except Exception:
                        failures["state_mapping_error"] += 1
                        continue
                    if assignment.state.state_id != state_id:
                        failures["off_target_state"] += 1
                        off_target_counts[state_id] += 1
                        continue
                    values = {
                        "context": context,
                        "target_state": target_state,
                        "trajectory": trajectory,
                        "validity_report": report,
                        "assignment": assignment,
                        "state_catalog_id": state_catalog.catalog_id,
                        "source_distribution_id": distribution.distribution_id,
                        "role_contract_id": role_contract.contract_id,
                        "materialization_provider_id": self._provider.provider_id,
                        "public_request_id": request.request_id,
                        "decision_trace_hash": decision_trace,
                        "generation_phase": "distribution_materialization",
                        "schema_version": VTDO_SCHEMA_VERSION,
                    }
                    provisional = StateConditionedTrainingArtifact.model_construct(
                        artifact_id="pending",
                        **values,
                    )
                    released.append(
                        StateConditionedTrainingArtifact(
                            artifact_id=state_conditioned_training_artifact_id(provisional),
                            **values,
                        )
                    )
                    released_counts[state_id] += 1
            except Exception:
                failures["provider_error"] += 1
            if released_counts[state_id] < target_count:
                failures["target_quota_unfilled"] += target_count - released_counts[state_id]

        total_released = len(released)
        target_distribution = {
            state_id: count / total_budget for state_id, count in requested.items()
        }
        released_budget_shares = {
            state_id: count / total_budget for state_id, count in released_counts.items()
        }
        released_distribution = (
            {
                state_id: count / total_released
                for state_id, count in released_counts.items()
            }
            if total_released
            else {state_id: 0.0 for state_id in requested}
        )
        distribution_tv = (
            _total_variation(target_distribution, released_distribution)
            if total_released
            else 1.0
        )
        js_divergence = (
            _jensen_shannon(target_distribution, released_distribution)
            if total_released
            else 1.0
        )
        status: Literal["passed", "blocked"] = (
            "passed"
            if released_counts == requested
            and math.isclose(distribution_tv, 0.0, abs_tol=1e-12)
            else "blocked"
        )
        report_values = {
            "explorer_provider_id": role_contract.explorer_provider_id,
            "materialization_provider_id": self._provider.provider_id,
            "materialization_provider_version": self._provider.provider_version,
            "context_id": context.context_id,
            "state_catalog_id": state_catalog.catalog_id,
            "source_distribution_id": distribution.distribution_id,
            "role_contract_id": role_contract.contract_id,
            "seed": seed,
            "maximum_attempt_multiplier": maximum_attempt_multiplier,
            "requested_state_counts": requested,
            "attempted_state_counts": attempted_counts,
            "off_target_state_counts": off_target_counts,
            "attempted_trajectory_count": attempted,
            "released_state_counts": released_counts,
            "public_state_requests": dict(sorted(public_requests.items())),
            "public_state_leakage_audits": dict(sorted(leakage_audits.items())),
            "source_state_distribution": dict(sorted(distribution.probabilities.items())),
            "target_state_distribution": target_distribution,
            "released_state_distribution": released_distribution,
            "released_budget_shares": released_budget_shares,
            "allocation_total_variation": _total_variation(
                distribution.probabilities, target_distribution
            ),
            "distribution_total_variation": distribution_tv,
            "jensen_shannon_divergence": js_divergence,
            "distribution_fidelity_error": sum(
                abs(target_distribution[state_id] - released_budget_shares[state_id])
                for state_id in requested
            ),
            "quota_fill_rate": total_released / total_budget,
            "generation_acceptance_rate": total_released / attempted if attempted else 0.0,
            "state_acceptance_rates": {
                state_id: (
                    released_counts[state_id] / attempted_counts[state_id]
                    if attempted_counts[state_id]
                    else 0.0
                )
                for state_id in requested
            },
            "state_off_target_rates": {
                state_id: (
                    off_target_counts[state_id] / attempted_counts[state_id]
                    if attempted_counts[state_id]
                    else 0.0
                )
                for state_id in requested
            },
            "minimum_support_floor_applied": total_budget >= len(requested),
            "finite_budget_support_truncation": any(
                distribution.probabilities[state_id] > 0 and requested[state_id] == 0
                for state_id in requested
            ),
            "unique_decision_trace_count": len(
                {item.decision_trace_hash for item in released}
            ),
            "independent_regeneration_enforced": True,
            "artifacts": tuple(released),
            "failure_counts": dict(sorted(failures.items())),
            "status": status,
            "schema_version": VTDO_SCHEMA_VERSION,
        }
        provisional_report = TrajectoryStateMaterializationReport.model_construct(
            report_id="pending",
            **report_values,
        )
        report = TrajectoryStateMaterializationReport(
            report_id=trajectory_state_materialization_report_id(provisional_report),
            **report_values,
        )
        return tuple(released), report


def state_conditioned_training_artifact_id(
    value: StateConditionedTrainingArtifact,
) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"artifact_id"}),
        prefix="state_conditioned_training_artifact:",
    )


def trajectory_state_materialization_report_id(
    value: TrajectoryStateMaterializationReport,
) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"report_id"}),
        prefix="trajectory_state_materialization_report:",
    )


def allocate_materialization_budget(
    distribution: ConditionalTrajectoryDistribution,
    total_budget: int,
) -> dict[str, int]:
    support_size = len(distribution.probabilities)
    floor = 1 if total_budget >= support_size else 0
    remaining = total_budget - floor * support_size
    exact = {
        state_id: probability * remaining
        for state_id, probability in distribution.probabilities.items()
    }
    counts = {state_id: floor + math.floor(value) for state_id, value in exact.items()}
    remainder = total_budget - sum(counts.values())
    order = sorted(
        exact,
        key=lambda state_id: (-(exact[state_id] - math.floor(exact[state_id])), state_id),
    )
    for state_id in order[:remainder]:
        counts[state_id] += 1
    return dict(sorted(counts.items()))


def _probability_maps_close(
    left: dict[str, float],
    right: dict[str, float],
) -> bool:
    return set(left) == set(right) and all(
        math.isclose(left[state_id], right[state_id], abs_tol=1e-12)
        for state_id in left
    )


def _total_variation(left: dict[str, float], right: dict[str, float]) -> float:
    if set(left) != set(right):
        raise ValueError("distribution supports do not match")
    return 0.5 * sum(abs(left[state_id] - right[state_id]) for state_id in left)


def _jensen_shannon(left: dict[str, float], right: dict[str, float]) -> float:
    if set(left) != set(right):
        raise ValueError("distribution supports do not match")
    midpoint = {state_id: (left[state_id] + right[state_id]) / 2 for state_id in left}

    def divergence(values: dict[str, float]) -> float:
        return sum(
            probability * math.log2(probability / midpoint[state_id])
            for state_id, probability in values.items()
            if probability > 0
        )

    return 0.5 * (divergence(left) + divergence(right))


def _state_seed(seed: int, state_id: str) -> int:
    digest = canonical_hash(
        {"seed": seed, "state_id": state_id},
        prefix="trajectory_state_materialization_seed:",
    ).rsplit(":", 1)[-1]
    return int(digest[:16], 16)
