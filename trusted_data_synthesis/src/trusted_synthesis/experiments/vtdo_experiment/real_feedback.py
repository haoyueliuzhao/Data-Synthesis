from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.core.evaluation.contracts import (
    QualityContractCompiler,
    QualityContractRuntime,
)
from trusted_synthesis.core.operations.registry import default_registry
from trusted_synthesis.core.trajectory import TrajectoryValidityEvaluator
from trusted_synthesis.core.trajectory.candidate_verifier import CandidateWorkflowVerifier
from trusted_synthesis.core.trajectory.schema import Trajectory
from trusted_synthesis.core.vtdo import (
    AnchoredEnergyConfig,
    ConditionalTrajectoryDistribution,
    ContributionApproximationAuthorization,
    ContributionEstimationManifest,
    StateConditionedTrajectoryExplorer,
    ValidityThresholds,
    VTDORoleContract,
    assemble_vtdo_round,
    condition_on_accepted_support,
    estimate_exploration_state_validity,
    estimate_importance_weighted_pushforward,
    make_exploration_distribution,
    make_uniform_coverage_prior,
    make_vtdo_role_contract,
)
from trusted_synthesis.core.vtdo.exploration import allocate_exploration_budget
from trusted_synthesis.core.vtdo.schema import (
    contribution_current_distribution_hash,
    validate_contribution_approximation_authorization,
)
from trusted_synthesis.domains.finance.adapter import FinanceArchiveAdapter
from trusted_synthesis.domains.finance.policy import FinanceSemanticPolicy
from trusted_synthesis.domains.finance.quality_clauses import FinanceQualityClauseProvider
from trusted_synthesis.domains.finance.schema import FinanceArchiveConfig
from trusted_synthesis.domains.finance.verification import FinanceClaimVerifier
from trusted_synthesis.hashing import canonical_hash

from .multistate import FinanceTaskStateArtifact, load_finance_multi_state_artifacts
from .real_rounds import (
    RealRoundAssemblyInput,
    assemble_real_vtdo_rounds,
    real_round_assembly_input_id,
)

REAL_FEEDBACK_VERSION = "vtdo_real_feedback.v6"


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class RecordedExplorerTrajectory(FrozenModel):
    record_id: str = Field(min_length=1)
    task_condition_id: str = Field(min_length=1)
    round_index: int = Field(ge=0)
    requested_state_id: str = Field(min_length=1)
    provider_seed: int
    candidate_ordinal: int = Field(ge=0)
    explorer_checkpoint_hash: str = Field(min_length=1)
    generation_config_hash: str = Field(min_length=1)
    trajectory: Trajectory
    schema_version: str = REAL_FEEDBACK_VERSION

    @model_validator(mode="after")
    def validate_identity(self) -> RecordedExplorerTrajectory:
        if self.record_id != recorded_explorer_trajectory_id(self):
            raise ValueError("recorded Explorer trajectory identity is invalid")
        return self


class RealFeedbackProductionConfig(FrozenModel):
    task_state_artifact_path: Path
    finance_archive_config_path: Path
    explorer_trajectory_path: Path
    initial_distribution_path: Path
    contribution_manifest_path: Path
    contribution_approximation_authorization_path: Path
    output_dir: Path
    explorer_provider_id: str = Field(min_length=1)
    explorer_provider_version: str = Field(min_length=1)
    materialization_provider_id: str = Field(min_length=1)
    explorer_checkpoint_hash: str = Field(min_length=1)
    explorer_generation_config_hash: str = Field(min_length=1)
    beneficiary_model_state_id: str = Field(min_length=1)
    beneficiary_checkpoint_hash: str = Field(min_length=1)
    final_student_model_id: str = Field(min_length=1)
    separation_mode: str = "strict_distinct"
    shared_role_justification_hash: str | None = None
    round_count: int = Field(default=1, ge=1, le=5)
    exploration_rate: float = Field(default=0.2, gt=0, lt=1)
    exploration_budget_per_task: int = Field(default=20, ge=3)
    exploration_seed: int = 20260801
    validity_thresholds: ValidityThresholds
    validity_prior_success: float = Field(default=0.0, ge=0)
    validity_prior_failure: float = Field(default=0.0, ge=0)
    pushforward_prior_strength: float = Field(default=1.0, gt=0)
    energy_config: AnchoredEnergyConfig
    catalog_version: str = Field(min_length=1)
    minimum_task_count: int = Field(default=1, ge=1)
    schema_version: str = REAL_FEEDBACK_VERSION

    @model_validator(mode="after")
    def validate_config(self) -> RealFeedbackProductionConfig:
        if self.exploration_budget_per_task < 3:
            raise ValueError("Explorer budget must cover a multi-state task")
        _ = self.role_contract
        return self

    @property
    def role_contract(self) -> VTDORoleContract:
        return make_vtdo_role_contract(
            explorer_provider_id=self.explorer_provider_id,
            materialization_provider_id=self.materialization_provider_id,
            beneficiary_model_state_id=self.beneficiary_model_state_id,
            final_student_model_id=self.final_student_model_id,
            separation_mode=self.separation_mode,
            shared_role_justification_hash=self.shared_role_justification_hash,
        )

    @property
    def config_hash(self) -> str:
        return canonical_hash(self, prefix="vtdo_real_feedback_config:")

    @classmethod
    def from_json(cls, path: str | Path) -> RealFeedbackProductionConfig:
        source = Path(path).resolve()
        payload = json.loads(source.read_text(encoding="utf-8"))
        for field in (
            "task_state_artifact_path",
            "finance_archive_config_path",
            "explorer_trajectory_path",
            "initial_distribution_path",
            "contribution_manifest_path",
            "contribution_approximation_authorization_path",
            "output_dir",
        ):
            value = Path(str(payload[field]))
            if not value.is_absolute():
                value = source.parent / value
            payload[field] = value.resolve()
        return cls.model_validate(payload)


class RealFeedbackProductionReport(FrozenModel):
    report_id: str = Field(min_length=1)
    config_hash: str = Field(min_length=1)
    role_contract_id: str = Field(min_length=1)
    task_count: int = Field(ge=0)
    requested_round_count: int = Field(ge=1)
    exploration_record_count: int = Field(ge=0)
    initial_distribution_count: int = Field(ge=0)
    contribution_manifest_count: int = Field(ge=0)
    authorization_count: int = Field(ge=0)
    exploration_batch_count: int = Field(ge=0)
    real_round_input_count: int = Field(ge=0)
    assembled_round_count: int = Field(ge=0)
    input_hashes: dict[str, str]
    input_manifest_hash: str = Field(min_length=1)
    output_hashes: dict[str, str] = Field(default_factory=dict)
    status: str
    blockers: tuple[str, ...]
    schema_version: str = REAL_FEEDBACK_VERSION

    @model_validator(mode="after")
    def validate_report(self) -> RealFeedbackProductionReport:
        if self.status not in {"passed", "blocked"}:
            raise ValueError("unknown real-feedback production status")
        required_inputs = {
            "task_state_artifacts",
            "finance_archive_config",
            "explorer_trajectories",
            "initial_distributions",
            "contribution_manifests",
            "contribution_approximation_authorizations",
        }
        if set(self.input_hashes) != required_inputs:
            raise ValueError("real-feedback input hash manifest is incomplete")
        if any(
            len(value) != 64 or any(char not in "0123456789abcdef" for char in value)
            for value in self.input_hashes.values()
        ):
            raise ValueError("real-feedback input hash manifest contains an invalid digest")
        expected_input_hash = canonical_hash(
            self.input_hashes,
            prefix="vtdo_real_feedback_input_manifest:",
        )
        if self.input_manifest_hash != expected_input_hash:
            raise ValueError("real-feedback input manifest identity is invalid")
        if self.status == "passed":
            expected = self.task_count * self.requested_round_count
            if self.blockers or self.assembled_round_count != expected:
                raise ValueError("passed real-feedback report is incomplete")
            if not self.output_hashes:
                raise ValueError("passed real-feedback report lacks output identities")
        elif not self.blockers:
            raise ValueError("blocked real-feedback report lacks blockers")
        if self.report_id != real_feedback_production_report_id(self):
            raise ValueError("real-feedback production report identity is invalid")
        return self


class _RecordedRoundProvider:
    def __init__(
        self,
        *,
        provider_id: str,
        provider_version: str,
        records: Mapping[str, tuple[RecordedExplorerTrajectory, ...]],
        expected_seeds: Mapping[str, int],
        state_id_by_public_condition_id: Mapping[str, str],
    ) -> None:
        self.provider_id = provider_id
        self.provider_version = provider_version
        self._records = records
        self._expected_seeds = expected_seeds
        self._state_id_by_public_condition_id = state_id_by_public_condition_id

    def generate(self, request) -> Iterable[Trajectory]:
        state_id = self._state_id_by_public_condition_id[request.state_condition.condition_id]
        if request.seed != self._expected_seeds[state_id]:
            raise ValueError("recorded Explorer seed does not match the frozen request")
        records = self._records.get(state_id, ())
        if len(records) < request.candidate_count:
            raise ValueError("recorded Explorer candidates do not fill the requested state")
        return tuple(item.trajectory for item in records[: request.candidate_count])


def produce_real_vtdo_feedback(
    config: RealFeedbackProductionConfig,
) -> RealFeedbackProductionReport:
    """Replay Explorer records and authorized Contribution manifests into VTDO rounds."""

    if config.output_dir.exists() and any(config.output_dir.iterdir()):
        raise ValueError(f"real-feedback output directory is not empty: {config.output_dir}")
    config.output_dir.mkdir(parents=True, exist_ok=True)
    input_hashes = {
        "task_state_artifacts": _sha256(config.task_state_artifact_path),
        "finance_archive_config": _sha256(config.finance_archive_config_path),
        "explorer_trajectories": _sha256(config.explorer_trajectory_path),
        "initial_distributions": _sha256(config.initial_distribution_path),
        "contribution_manifests": _sha256(config.contribution_manifest_path),
        "contribution_approximation_authorizations": _sha256(
            config.contribution_approximation_authorization_path
        ),
    }
    input_manifest_hash = canonical_hash(
        input_hashes,
        prefix="vtdo_real_feedback_input_manifest:",
    )
    artifacts = load_finance_multi_state_artifacts(config.task_state_artifact_path)
    explorer_records = _load_records(
        config.explorer_trajectory_path,
        RecordedExplorerTrajectory,
    )
    initial_distributions = _load_records(
        config.initial_distribution_path,
        ConditionalTrajectoryDistribution,
    )
    contribution_manifests = _load_records(
        config.contribution_manifest_path,
        ContributionEstimationManifest,
    )
    authorizations = _load_records(
        config.contribution_approximation_authorization_path,
        ContributionApproximationAuthorization,
    )
    blockers: list[str] = []
    if len(artifacts) < config.minimum_task_count:
        blockers.append(
            f"feedback_tasks_below_minimum:{len(artifacts)}<{config.minimum_task_count}"
        )
    _require_unique_ids(
        (item.record_id for item in explorer_records),
        "duplicate_explorer_record_id",
        blockers,
    )
    _require_unique_ids(
        (item.distribution_id for item in initial_distributions),
        "duplicate_initial_distribution_id",
        blockers,
    )
    _require_unique_ids(
        (item.manifest_id for item in contribution_manifests),
        "duplicate_contribution_manifest_id",
        blockers,
    )
    _require_unique_ids(
        (item.authorization_id for item in authorizations),
        "duplicate_contribution_authorization_id",
        blockers,
    )
    initial_by_task = {item.task_condition_id: item for item in initial_distributions}
    if len(initial_by_task) != len(initial_distributions) or any(
        item.round_index != 0 for item in initial_distributions
    ):
        blockers.append("initial_distribution_mapping_invalid")
    manifests_by_key = {
        (item.task_condition_id, item.distribution_id): item
        for item in contribution_manifests
    }
    if len(manifests_by_key) != len(contribution_manifests):
        blockers.append("duplicate_task_round_contribution_manifest")
    role_contract = config.role_contract
    evaluator = _finance_trajectory_evaluator(config.finance_archive_config_path)
    explorer_by_key: defaultdict[
        tuple[str, int, str], list[RecordedExplorerTrajectory]
    ] = defaultdict(list)
    for record in explorer_records:
        explorer_by_key[
            (record.task_condition_id, record.round_index, record.requested_state_id)
        ].append(record)

    consumed_explorer: set[str] = set()
    consumed_manifests: set[str] = set()
    consumed_authorizations: set[str] = set()
    batches: list[Any] = []
    assembly_inputs: list[RealRoundAssemblyInput] = []
    direct_rounds: list[Any] = []
    for artifact in sorted(artifacts, key=lambda item: item.artifact_id):
        condition_id = artifact.state_catalog.task_condition_id
        initial = initial_by_task.get(condition_id)
        if initial is None:
            blockers.append(f"initial_distribution_missing:{condition_id}")
            continue
        try:
            task_inputs, task_batches, task_rounds = _produce_task_feedback(
                config,
                artifact,
                initial,
                role_contract,
                evaluator,
                explorer_by_key,
                manifests_by_key,
                authorizations,
                consumed_explorer,
                consumed_manifests,
                consumed_authorizations,
            )
        except (KeyError, TypeError, ValueError) as error:
            blockers.append(
                f"feedback_task_failed:{artifact.artifact_id}:{type(error).__name__}:{error}"
            )
            continue
        assembly_inputs.extend(task_inputs)
        batches.extend(task_batches)
        direct_rounds.extend(task_rounds)

    unconsumed_explorer = {item.record_id for item in explorer_records} - consumed_explorer
    unconsumed_manifests = {
        item.manifest_id for item in contribution_manifests
    } - consumed_manifests
    unconsumed_authorizations = {
        item.authorization_id for item in authorizations
    } - consumed_authorizations
    if unconsumed_explorer:
        blockers.append(f"unconsumed_explorer_records:{len(unconsumed_explorer)}")
    if unconsumed_manifests:
        blockers.append(f"unconsumed_contribution_manifests:{len(unconsumed_manifests)}")
    if unconsumed_authorizations:
        blockers.append(f"unconsumed_contribution_authorizations:{len(unconsumed_authorizations)}")
    expected_rounds = len(artifacts) * config.round_count
    if len(assembly_inputs) != expected_rounds:
        blockers.append(
            f"feedback_round_inputs_incomplete:{len(assembly_inputs)}!={expected_rounds}"
        )

    output_hashes: dict[str, str] = {}
    if not blockers:
        input_path = config.output_dir / "real_round_inputs.jsonl"
        batch_path = config.output_dir / "exploration_batches.jsonl"
        round_path = config.output_dir / "vtdo_rounds.jsonl"
        _write_jsonl(input_path, assembly_inputs)
        _write_jsonl(batch_path, batches)
        assembly_report, replayed_rounds = assemble_real_vtdo_rounds(input_path, round_path)
        if assembly_report.status != "passed":
            blockers.extend(assembly_report.blockers)
        elif tuple(item.round_id for item in replayed_rounds) != tuple(
            item.round_id for item in direct_rounds
        ):
            blockers.append("real_feedback_round_replay_identity_mismatch")
        else:
            output_hashes = {
                "real_round_inputs": _sha256(input_path),
                "exploration_batches": _sha256(batch_path),
                "vtdo_rounds": _sha256(round_path),
                "assembly_report": assembly_report.report_id,
            }
            (config.output_dir / "real_round_assembly_report.json").write_text(
                assembly_report.model_dump_json(indent=2) + "\n",
                encoding="utf-8",
            )

    blockers_tuple = tuple(sorted(set(blockers)))
    values: dict[str, Any] = {
        "config_hash": config.config_hash,
        "role_contract_id": role_contract.contract_id,
        "task_count": len(artifacts),
        "requested_round_count": config.round_count,
        "exploration_record_count": len(explorer_records),
        "initial_distribution_count": len(initial_distributions),
        "contribution_manifest_count": len(contribution_manifests),
        "authorization_count": len(authorizations),
        "exploration_batch_count": len(batches),
        "real_round_input_count": len(assembly_inputs),
        "assembled_round_count": len(direct_rounds) if not blockers_tuple else 0,
        "input_hashes": input_hashes,
        "input_manifest_hash": input_manifest_hash,
        "output_hashes": output_hashes if not blockers_tuple else {},
        "status": "blocked" if blockers_tuple else "passed",
        "blockers": blockers_tuple,
        "schema_version": REAL_FEEDBACK_VERSION,
    }
    provisional = RealFeedbackProductionReport.model_construct(report_id="pending", **values)
    report = RealFeedbackProductionReport(
        report_id=real_feedback_production_report_id(provisional),
        **values,
    )
    (config.output_dir / "real_feedback_production_report.json").write_text(
        report.model_dump_json(indent=2) + "\n",
        encoding="utf-8",
    )
    return report


def _produce_task_feedback(
    config: RealFeedbackProductionConfig,
    artifact: FinanceTaskStateArtifact,
    initial_distribution: ConditionalTrajectoryDistribution,
    role_contract: VTDORoleContract,
    evaluator: TrajectoryValidityEvaluator,
    explorer_by_key: Mapping[tuple[str, int, str], list[RecordedExplorerTrajectory]],
    manifests_by_key: Mapping[tuple[str, str], ContributionEstimationManifest],
    authorizations: tuple[ContributionApproximationAuthorization, ...],
    consumed_explorer: set[str],
    consumed_manifests: set[str],
    consumed_authorizations: set[str],
) -> tuple[list[RealRoundAssemblyInput], list[Any], list[Any]]:
    condition_id = artifact.state_catalog.task_condition_id
    state_ids = tuple(sorted(artifact.state_catalog.states))
    if initial_distribution.task_condition_id != condition_id:
        raise ValueError("initial distribution crosses task conditions")
    if set(initial_distribution.probabilities) != set(state_ids):
        raise ValueError("initial distribution does not cover the state catalog")
    coverage = make_uniform_coverage_prior(condition_id, state_ids)
    prior = initial_distribution
    task_inputs: list[RealRoundAssemblyInput] = []
    task_batches: list[Any] = []
    task_rounds: list[Any] = []
    for round_index in range(config.round_count):
        if prior.round_index != round_index:
            raise ValueError("real-feedback prior round is not contiguous")
        exploration = make_exploration_distribution(
            prior,
            coverage,
            exploration_rate=config.exploration_rate,
        )
        task_seed = _task_round_seed(config.exploration_seed, condition_id, round_index)
        requested = allocate_exploration_budget(exploration, config.exploration_budget_per_task)
        records_by_state: dict[str, tuple[RecordedExplorerTrajectory, ...]] = {}
        expected_seeds: dict[str, int] = {}
        for state_id in state_ids:
            records = tuple(
                sorted(
                    explorer_by_key.get((condition_id, round_index, state_id), ()),
                    key=lambda item: item.candidate_ordinal,
                )
            )
            if len(records) != requested[state_id]:
                raise ValueError(
                    "Explorer record count mismatch:"
                    f"{state_id}:{len(records)}!={requested[state_id]}"
                )
            if tuple(item.candidate_ordinal for item in records) != tuple(range(len(records))):
                raise ValueError(f"Explorer ordinals are not contiguous:{state_id}")
            expected_seed = _state_seed(task_seed, state_id)
            if any(item.provider_seed != expected_seed for item in records):
                raise ValueError(f"Explorer provider seed mismatch:{state_id}")
            if any(
                item.explorer_checkpoint_hash != config.explorer_checkpoint_hash
                or item.generation_config_hash != config.explorer_generation_config_hash
                for item in records
            ):
                raise ValueError(f"Explorer model identity mismatch:{state_id}")
            records_by_state[state_id] = records
            expected_seeds[state_id] = expected_seed
            consumed_explorer.update(item.record_id for item in records)
        provider = _RecordedRoundProvider(
            provider_id=config.explorer_provider_id,
            provider_version=config.explorer_provider_version,
            records=records_by_state,
            expected_seeds=expected_seeds,
            state_id_by_public_condition_id={
                condition.condition_id: state_id
                for state_id, condition in artifact.state_catalog.public_state_conditions.items()
            },
        )
        batch = StateConditionedTrajectoryExplorer(provider, evaluator).explore(
            artifact.omega,
            artifact.state_catalog,
            exploration,
            role_contract,
            total_budget=config.exploration_budget_per_task,
            seed=task_seed,
        )
        if batch.status != "passed":
            raise ValueError(f"Explorer replay did not pass:{batch.status}:{batch.failures}")
        pushforward = estimate_importance_weighted_pushforward(
            batch,
            exploration,
            prior_strength=config.pushforward_prior_strength,
        )
        _, partition = estimate_exploration_state_validity(
            batch,
            thresholds=config.validity_thresholds,
            prior_success=config.validity_prior_success,
            prior_failure=config.validity_prior_failure,
        )
        accepted_prior, _ = condition_on_accepted_support(
            pushforward.distribution,
            coverage,
            partition,
        )
        manifest = manifests_by_key.get((condition_id, accepted_prior.distribution_id))
        if manifest is None:
            raise ValueError("Contribution manifest missing for exact task-round distribution")
        authorization = _authorization_for_manifest(manifest, authorizations)
        if manifest.beneficiary_model_state_id != config.beneficiary_model_state_id or (
            manifest.beneficiary_checkpoint_hash != config.beneficiary_checkpoint_hash
        ):
            raise ValueError("Contribution manifest beneficiary differs from real feedback")
        input_values = {
            "state_catalog": artifact.state_catalog,
            "role_contract": role_contract,
            "exploration": exploration,
            "exploration_batch": batch,
            "contribution_manifest": manifest,
            "contribution_approximation_authorization": authorization,
            "contribution_source_artifact_hash": manifest.estimation_protocol_hash,
            "validity_thresholds": config.validity_thresholds,
            "validity_prior_success": config.validity_prior_success,
            "validity_prior_failure": config.validity_prior_failure,
            "pushforward_prior_strength": config.pushforward_prior_strength,
            "energy_config": config.energy_config,
            "explorer_checkpoint_hash": config.explorer_checkpoint_hash,
            "beneficiary_checkpoint_hash": config.beneficiary_checkpoint_hash,
            "catalog_version": config.catalog_version,
        }
        provisional_input = RealRoundAssemblyInput.model_construct(
            input_id="pending",
            **input_values,
        )
        assembly_input = RealRoundAssemblyInput(
            input_id=real_round_assembly_input_id(provisional_input),
            **input_values,
        )
        round_artifact = assemble_vtdo_round(
            state_catalog=artifact.state_catalog,
            role_contract=role_contract,
            exploration=exploration,
            exploration_batch=batch,
            pushforward_estimate=pushforward,
            validity_partition=partition,
            contribution_manifest=manifest,
            contribution_approximation_authorization=authorization,
            energy_config=config.energy_config,
        )
        consumed_manifests.add(manifest.manifest_id)
        consumed_authorizations.add(authorization.authorization_id)
        task_inputs.append(assembly_input)
        task_batches.append(batch)
        task_rounds.append(round_artifact)
        prior = round_artifact.update.next_distribution
    return task_inputs, task_batches, task_rounds


def _authorization_for_manifest(
    manifest: ContributionEstimationManifest,
    authorizations: tuple[ContributionApproximationAuthorization, ...],
) -> ContributionApproximationAuthorization:
    distribution_hash = contribution_current_distribution_hash(
        manifest.task_condition_id,
        {item.state_id: item.current_probability for item in manifest.estimates},
    )
    matches = tuple(
        item
        for item in authorizations
        if dict(item.task_distribution_hashes).get(manifest.task_condition_id)
        == distribution_hash
        and dict(item.task_distribution_ids).get(manifest.task_condition_id)
        == manifest.distribution_id
    )
    if len(matches) != 1:
        raise ValueError(f"expected one exact Contribution authorization, found {len(matches)}")
    validate_contribution_approximation_authorization(manifest, matches[0])
    return matches[0]


def _finance_trajectory_evaluator(path: Path) -> TrajectoryValidityEvaluator:
    adapter = FinanceArchiveAdapter(FinanceArchiveConfig.from_json(path))
    registry = default_registry()
    source_grounding_verifier = adapter.source_grounding_verifier()
    verifier = CandidateWorkflowVerifier(
        registry,
        semantic_policy=FinanceSemanticPolicy(),
        claim_verifier=FinanceClaimVerifier(),
        source_grounding_verifier=source_grounding_verifier,
    )
    compiler = QualityContractCompiler(
        registry,
        domain_provider=FinanceQualityClauseProvider(),
    )
    return TrajectoryValidityEvaluator(
        verifier,
        contract_runtime=QualityContractRuntime(
            verifier,
            verifier_registry=compiler.verifier_registry,
        ),
    )


def _load_records(path: Path, model: type[BaseModel]) -> tuple[Any, ...]:
    if not path.is_file():
        raise ValueError(f"real-feedback record file is missing: {path}")
    return tuple(
        model.model_validate_json(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    )


def _require_unique_ids(values: Iterable[str], code: str, blockers: list[str]) -> None:
    items = tuple(values)
    if len(items) != len(set(items)):
        blockers.append(code)


def _write_jsonl(path: Path, values: Iterable[BaseModel]) -> None:
    path.write_text(
        "".join(item.model_dump_json() + "\n" for item in values),
        encoding="utf-8",
    )


def _task_round_seed(seed: int, condition_id: str, round_index: int) -> int:
    digest = canonical_hash(
        {"seed": seed, "task_condition_id": condition_id, "round_index": round_index},
        prefix="real_feedback_task_round_seed:",
    ).rsplit(":", 1)[-1]
    return int(digest[:16], 16)


def _state_seed(seed: int, state_id: str) -> int:
    digest = canonical_hash(
        {"seed": seed, "state_id": state_id},
        prefix="trajectory_state_exploration_seed:",
    ).rsplit(":", 1)[-1]
    return int(digest[:16], 16)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def recorded_explorer_trajectory_id(value: RecordedExplorerTrajectory) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"record_id"}),
        prefix="recorded_explorer_trajectory:",
    )


def real_feedback_production_report_id(value: RealFeedbackProductionReport) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"report_id"}),
        prefix="real_feedback_production_report:",
    )
