from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from trusted_synthesis.core.vtdo import (
    AnchoredEnergyConfig,
    ContributionApproximationAuthorization,
    ContributionEstimationManifest,
    ExplorationDistribution,
    StateConditionedExplorationBatch,
    TrajectoryStateCatalog,
    ValidityThresholds,
    VTDORoleContract,
    VTDORoundArtifact,
    assemble_vtdo_round,
    estimate_exploration_state_validity,
    estimate_importance_weighted_pushforward,
)
from trusted_synthesis.hashing import canonical_hash

from .schema import VTDO_EXPERIMENT_VERSION


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class RealRoundAssemblyInput(FrozenModel):
    input_id: str = Field(min_length=1)
    state_catalog: TrajectoryStateCatalog
    role_contract: VTDORoleContract
    exploration: ExplorationDistribution
    exploration_batch: StateConditionedExplorationBatch
    contribution_manifest: ContributionEstimationManifest
    contribution_approximation_authorization: ContributionApproximationAuthorization | None
    contribution_source_artifact_hash: str = Field(min_length=1)
    validity_thresholds: ValidityThresholds
    validity_prior_success: float = Field(default=0.0, ge=0)
    validity_prior_failure: float = Field(default=0.0, ge=0)
    pushforward_prior_strength: float = Field(default=1.0, gt=0)
    energy_config: AnchoredEnergyConfig
    explorer_checkpoint_hash: str = Field(min_length=1)
    beneficiary_checkpoint_hash: str = Field(min_length=1)
    catalog_version: str = Field(min_length=1)
    schema_version: str = VTDO_EXPERIMENT_VERSION

    @model_validator(mode="after")
    def validate_identity(self) -> RealRoundAssemblyInput:
        if self.input_id != real_round_assembly_input_id(self):
            raise ValueError("real-round assembly input identity is invalid")
        if self.exploration.task_condition_id != self.state_catalog.task_condition_id:
            raise ValueError("real-round input crosses task conditions")
        if self.contribution_manifest.beneficiary_checkpoint_hash != (
            self.beneficiary_checkpoint_hash
        ):
            raise ValueError("real-round input has another beneficiary checkpoint")
        if self.contribution_manifest.beneficiary_model_state_id != (
            self.role_contract.beneficiary_model_state_id
        ):
            raise ValueError("real-round Contribution violates the beneficiary role contract")
        if self.contribution_source_artifact_hash != (
            self.contribution_manifest.estimation_protocol_hash
        ):
            raise ValueError("real-round Contribution source identity is detached")
        authorization = self.contribution_approximation_authorization
        if self.contribution_manifest.estimator_kind == "gradient_projection":
            if authorization is None:
                raise ValueError("real-round Gradient Projection lacks authorization")
            if authorization.beneficiary_checkpoint_hash != self.beneficiary_checkpoint_hash:
                raise ValueError("real-round authorization has another beneficiary checkpoint")
        elif authorization is not None:
            raise ValueError("real-round diagnostic Contribution cannot carry authorization")
        return self


class RealRoundAssemblyReport(FrozenModel):
    report_id: str = Field(min_length=1)
    input_record_count: int = Field(ge=0)
    assembled_round_count: int = Field(ge=0)
    task_condition_count: int = Field(ge=0)
    complete_sequence_count: int = Field(ge=0)
    status: str
    blockers: tuple[str, ...]
    output_hash: str | None = None
    schema_version: str = VTDO_EXPERIMENT_VERSION

    @model_validator(mode="after")
    def validate_identity(self) -> RealRoundAssemblyReport:
        if self.status not in {"passed", "blocked"}:
            raise ValueError("unknown real-round assembly status")
        if self.status == "passed" and (self.blockers or not self.output_hash):
            raise ValueError("passed real-round assembly is incomplete")
        if self.status == "blocked" and not self.blockers:
            raise ValueError("blocked real-round assembly lacks blockers")
        if self.report_id != real_round_assembly_report_id(self):
            raise ValueError("real-round assembly report identity is invalid")
        return self


def assemble_real_vtdo_rounds(
    input_path: Path,
    output_path: Path,
) -> tuple[RealRoundAssemblyReport, tuple[VTDORoundArtifact, ...]]:
    """Compile frozen Explorer evidence and Contribution manifests into VTDO rounds."""

    blockers: list[str] = []
    inputs: list[RealRoundAssemblyInput] = []
    if not input_path.is_file():
        blockers.append(f"real_round_input_missing:{input_path}")
    else:
        for index, line in enumerate(input_path.read_text(encoding="utf-8").splitlines()):
            if not line.strip():
                continue
            try:
                inputs.append(RealRoundAssemblyInput.model_validate_json(line))
            except ValidationError:
                blockers.append(f"real_round_input_invalid:{index}")
    manifest_ids = tuple(item.contribution_manifest.manifest_id for item in inputs)
    if len(manifest_ids) != len(set(manifest_ids)):
        blockers.append("real_round_contribution_manifest_reused")
    rounds: list[VTDORoundArtifact] = []
    for item in inputs:
        try:
            pushforward = estimate_importance_weighted_pushforward(
                item.exploration_batch,
                item.exploration,
                prior_strength=item.pushforward_prior_strength,
            )
            _, partition = estimate_exploration_state_validity(
                item.exploration_batch,
                thresholds=item.validity_thresholds,
                prior_success=item.validity_prior_success,
                prior_failure=item.validity_prior_failure,
            )
            rounds.append(
                assemble_vtdo_round(
                    state_catalog=item.state_catalog,
                    role_contract=item.role_contract,
                    exploration=item.exploration,
                    exploration_batch=item.exploration_batch,
                    pushforward_estimate=pushforward,
                    validity_partition=partition,
                    contribution_manifest=item.contribution_manifest,
                    contribution_approximation_authorization=(
                        item.contribution_approximation_authorization
                    ),
                    energy_config=item.energy_config,
                )
            )
        except ValueError as error:
            blockers.append(f"real_round_assembly_failed:{item.input_id}:{type(error).__name__}")

    grouped: dict[str, list[VTDORoundArtifact]] = {}
    input_by_exploration: dict[str, RealRoundAssemblyInput] = {}
    for item in inputs:
        exploration_id = item.exploration.exploration_id
        if exploration_id in input_by_exploration:
            blockers.append(f"duplicate_real_round_exploration:{exploration_id}")
        input_by_exploration[exploration_id] = item
    for round_artifact in rounds:
        grouped.setdefault(round_artifact.task_condition_id, []).append(round_artifact)
    complete_sequence_count = 0
    for condition_id, condition_rounds in sorted(grouped.items()):
        ordered = sorted(condition_rounds, key=lambda value: value.round_index)
        frozen_sequence_fields: dict[str, set[str]] = {
            "explorer_checkpoint_hash": {
                input_by_exploration[item.exploration.exploration_id].explorer_checkpoint_hash
                for item in ordered
            },
            "beneficiary_checkpoint_hash": {
                input_by_exploration[item.exploration.exploration_id].beneficiary_checkpoint_hash
                for item in ordered
            },
            "approximation_contract_id": {
                item.contribution_manifest.approximation_contract_id or ""
                for item in ordered
            },
            "catalog_version": {
                input_by_exploration[item.exploration.exploration_id].catalog_version
                for item in ordered
            },
            "state_catalog": {
                canonical_hash(item.state_catalog, prefix="real_round_state_catalog:")
                for item in ordered
            },
            "role_contract": {item.role_contract.contract_id for item in ordered},
            "energy_config": {
                canonical_hash(item.update.energy_config, prefix="real_round_energy_config:")
                for item in ordered
            },
            "contribution_estimator": {
                item.contribution_manifest.estimator_id for item in ordered
            },
        }
        for field, identities in frozen_sequence_fields.items():
            if len(identities) != 1:
                blockers.append(f"real_round_frozen_identity_mismatch:{condition_id}:{field}")
        indices = tuple(value.round_index for value in ordered)
        if indices != tuple(range(len(ordered))):
            blockers.append(f"real_round_sequence_not_contiguous:{condition_id}")
            continue
        if any(
            current.exploration.training_distribution.distribution_id
            != previous.update.next_distribution.distribution_id
            for previous, current in zip(ordered, ordered[1:], strict=False)
        ):
            blockers.append(f"real_round_sequence_link_failure:{condition_id}")
            continue
        complete_sequence_count += 1

    if not inputs:
        blockers.append("real_round_inputs_empty")
    if len(rounds) != len(inputs):
        blockers.append(f"real_round_assembly_incomplete:{len(rounds)}!={len(inputs)}")
    blockers_tuple = tuple(sorted(set(blockers)))
    output_hash = None
    if not blockers_tuple:
        ordered_rounds: tuple[VTDORoundArtifact, ...] = tuple(
            sorted(rounds, key=lambda value: (value.task_condition_id, value.round_index))
        )
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            "".join(value.model_dump_json() + "\n" for value in ordered_rounds),
            encoding="utf-8",
        )
        output_hash = canonical_hash(ordered_rounds, prefix="real_vtdo_round_sequence:")
    else:
        ordered_rounds = ()
    report_values = {
        "input_record_count": len(inputs),
        "assembled_round_count": len(ordered_rounds),
        "task_condition_count": len(grouped),
        "complete_sequence_count": complete_sequence_count,
        "status": "blocked" if blockers_tuple else "passed",
        "blockers": blockers_tuple,
        "output_hash": output_hash,
        "schema_version": VTDO_EXPERIMENT_VERSION,
    }
    provisional = RealRoundAssemblyReport.model_construct(
        report_id="pending",
        **report_values,
    )
    report = RealRoundAssemblyReport(
        report_id=real_round_assembly_report_id(provisional),
        **report_values,
    )
    return report, ordered_rounds


def real_round_assembly_input_id(value: RealRoundAssemblyInput) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"input_id"}),
        prefix="real_round_assembly_input:",
    )


def real_round_assembly_report_id(value: RealRoundAssemblyReport) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"report_id"}),
        prefix="real_round_assembly_report:",
    )
