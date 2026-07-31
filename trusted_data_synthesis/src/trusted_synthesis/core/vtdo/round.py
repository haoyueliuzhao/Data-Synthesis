from __future__ import annotations

from collections.abc import Iterable

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.hashing import canonical_hash

from .catalog import TrajectoryStateCatalog
from .contribution import ContributionProbeObservation, estimate_contributions_from_probes
from .explorer import StateConditionedExplorationBatch
from .feasibility import StateValidityPartition, condition_on_accepted_support
from .schema import (
    VTDO_SCHEMA_VERSION,
    AnchoredDistributionUpdate,
    AnchoredEnergyConfig,
    ConditionalTrajectoryDistribution,
    ContributionEstimationManifest,
    CoveragePrior,
    EmpiricalDistributionEstimate,
    ExplorationDistribution,
    ValidityRegion,
    VTDORoleContract,
)
from .update import update_valid_trajectory_distribution


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class VTDORoundArtifact(FrozenModel):
    """Proof-carrying, independently replayable record for one VTDO conditional round."""

    round_id: str = Field(min_length=1)
    task_condition_id: str = Field(min_length=1)
    round_index: int = Field(ge=0)
    state_catalog: TrajectoryStateCatalog
    role_contract: VTDORoleContract
    exploration: ExplorationDistribution
    exploration_batch: StateConditionedExplorationBatch
    pushforward_estimate: EmpiricalDistributionEstimate
    validity_partition: StateValidityPartition
    accepted_prior: ConditionalTrajectoryDistribution
    accepted_coverage_prior: CoveragePrior
    contribution_probes: tuple[ContributionProbeObservation, ...] = Field(min_length=1)
    contribution_manifest: ContributionEstimationManifest
    update: AnchoredDistributionUpdate
    status: str = "passed"
    schema_version: str = VTDO_SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_round(self) -> VTDORoundArtifact:
        if self.status != "passed":
            raise ValueError("canonical VTDO round artifacts represent only completed rounds")
        if self.task_condition_id != self.state_catalog.task_condition_id:
            raise ValueError("VTDO round state catalog crosses task conditions")
        catalog_support = set(self.state_catalog.states)
        if set(self.exploration.coverage_prior.probabilities) != catalog_support:
            raise ValueError("VTDO exploration does not cover the frozen state catalog")
        if self.exploration.task_condition_id != self.task_condition_id:
            raise ValueError("VTDO exploration crosses task conditions")
        if self.exploration.training_distribution.round_index != self.round_index:
            raise ValueError("VTDO exploration consumes another round")
        if self.exploration_batch.exploration_distribution_id != self.exploration.exploration_id:
            raise ValueError("VTDO exploration batch belongs to another q_t")
        if self.exploration_batch.role_contract_id != self.role_contract.contract_id:
            raise ValueError("VTDO exploration batch violates the role contract")
        if self.exploration_batch.context_id != self.state_catalog.verification_context_id:
            raise ValueError("VTDO exploration batch uses another verification context")
        if self.exploration_batch.status != "passed":
            raise ValueError("VTDO round cannot use an incomplete exploration batch")
        observation_ids = {item.observation_id for item in self.exploration_batch.observations}
        if set(self.pushforward_estimate.source_observation_ids) != observation_ids:
            raise ValueError("VTDO push-forward estimate does not cover its exploration batch")
        if self.pushforward_estimate.sampling_distribution_id != self.exploration.exploration_id:
            raise ValueError("VTDO push-forward estimate names another sampling policy")
        if self.pushforward_estimate.coverage_prior != self.exploration.coverage_prior:
            raise ValueError("VTDO push-forward estimate uses another coverage prior")
        if set(self.pushforward_estimate.distribution.probabilities) != catalog_support:
            raise ValueError("VTDO push-forward estimate does not cover the state catalog")
        if self.pushforward_estimate.distribution.round_index != self.round_index:
            raise ValueError("VTDO push-forward estimate belongs to another round")
        if self.pushforward_estimate.distribution.source_distribution_id != (
            self.exploration.training_distribution.distribution_id
        ):
            raise ValueError("VTDO push-forward estimate names another training distribution")
        partition_support = (
            set(self.validity_partition.accepted_state_ids)
            | set(self.validity_partition.quarantined_state_ids)
            | set(self.validity_partition.rejected_state_ids)
        )
        if partition_support != catalog_support:
            raise ValueError("VTDO validity partition does not cover the state catalog")
        expected_prior, expected_coverage = condition_on_accepted_support(
            self.pushforward_estimate.distribution,
            self.exploration.coverage_prior,
            self.validity_partition,
        )
        if self.accepted_prior != expected_prior:
            raise ValueError("VTDO Accepted prior does not replay support conditioning")
        if self.accepted_coverage_prior != expected_coverage:
            raise ValueError("VTDO Accepted coverage does not replay support conditioning")
        probe_by_state = {item.state_id: item for item in self.contribution_probes}
        accepted_support = set(self.validity_partition.accepted_state_ids)
        if len(probe_by_state) != len(self.contribution_probes):
            raise ValueError("VTDO round has duplicate contribution probes")
        if set(probe_by_state) != accepted_support:
            raise ValueError("VTDO contribution probes do not cover Accepted support")
        expected_manifest = estimate_contributions_from_probes(
            self.accepted_prior,
            self.contribution_probes,
        )
        if self.contribution_manifest != expected_manifest:
            raise ValueError("VTDO contribution manifest does not replay its probes")
        accepted_estimates = tuple(
            item
            for item in self.validity_partition.estimates
            if item.region == ValidityRegion.ACCEPTED
        )
        expected_update = update_valid_trajectory_distribution(
            self.accepted_prior,
            self.accepted_coverage_prior,
            accepted_estimates,
            self.contribution_manifest,
            self.update.energy_config,
            self.role_contract,
        )
        if self.update != expected_update:
            raise ValueError("VTDO update does not replay the complete round evidence")
        if self.round_id != vtdo_round_artifact_id(self):
            raise ValueError("VTDO round artifact identity is invalid")
        return self


def assemble_vtdo_round(
    *,
    state_catalog: TrajectoryStateCatalog,
    role_contract: VTDORoleContract,
    exploration: ExplorationDistribution,
    exploration_batch: StateConditionedExplorationBatch,
    pushforward_estimate: EmpiricalDistributionEstimate,
    validity_partition: StateValidityPartition,
    contribution_probes: Iterable[ContributionProbeObservation],
    energy_config: AnchoredEnergyConfig,
) -> VTDORoundArtifact:
    probes = tuple(sorted(contribution_probes, key=lambda item: item.state_id))
    accepted_prior, accepted_coverage = condition_on_accepted_support(
        pushforward_estimate.distribution,
        exploration.coverage_prior,
        validity_partition,
    )
    contribution_manifest = estimate_contributions_from_probes(accepted_prior, probes)
    accepted_estimates = tuple(
        item for item in validity_partition.estimates if item.region == ValidityRegion.ACCEPTED
    )
    update = update_valid_trajectory_distribution(
        accepted_prior,
        accepted_coverage,
        accepted_estimates,
        contribution_manifest,
        energy_config,
        role_contract,
    )
    values = {
        "task_condition_id": state_catalog.task_condition_id,
        "round_index": exploration.training_distribution.round_index,
        "state_catalog": state_catalog,
        "role_contract": role_contract,
        "exploration": exploration,
        "exploration_batch": exploration_batch,
        "pushforward_estimate": pushforward_estimate,
        "validity_partition": validity_partition,
        "accepted_prior": accepted_prior,
        "accepted_coverage_prior": accepted_coverage,
        "contribution_probes": probes,
        "contribution_manifest": contribution_manifest,
        "update": update,
        "status": "passed",
        "schema_version": VTDO_SCHEMA_VERSION,
    }
    provisional = VTDORoundArtifact.model_construct(round_id="pending", **values)
    return VTDORoundArtifact(round_id=vtdo_round_artifact_id(provisional), **values)


def vtdo_round_artifact_id(value: VTDORoundArtifact) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"round_id"}),
        prefix="vtdo_round_artifact:",
    )
