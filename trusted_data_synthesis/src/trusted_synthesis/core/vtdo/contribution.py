from __future__ import annotations

import math
import statistics
from collections import defaultdict
from collections.abc import Iterable, Mapping
from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.core.vtdo.estimation import estimate_centered_contributions
from trusted_synthesis.core.vtdo.schema import (
    VTDO_SCHEMA_VERSION,
    ConditionalTrajectoryDistribution,
    ContributionEstimationManifest,
)
from trusted_synthesis.hashing import canonical_hash


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class ContributionMetricContract(FrozenModel):
    """Freeze a higher-is-better performance functional J on nu_int."""

    contract_id: str = Field(min_length=1)
    target_metric_id: str = Field(min_length=1)
    evaluation_distribution_id: str = Field(min_length=1)
    evaluation_snapshot_hash: str = Field(min_length=1)
    objective_direction: Literal["higher_is_better"] = "higher_is_better"
    score_transform: Literal["identity", "negative_loss"]
    schema_version: str = VTDO_SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_contract(self) -> ContributionMetricContract:
        if self.contract_id != contribution_metric_contract_id(self):
            raise ValueError("contribution metric contract identity is invalid")
        return self


class ContributionDataIsolationContract(FrozenModel):
    """Freeze D_t, each B_z, nu_int, and the untouched final-test split."""

    contract_id: str = Field(min_length=1)
    task_condition_id: str = Field(min_length=1)
    baseline_training_set_id: str = Field(min_length=1)
    baseline_training_instance_ids: tuple[str, ...] = Field(min_length=1)
    probe_update_instance_ids_by_state: dict[str, tuple[str, ...]] = Field(min_length=1)
    internal_validation_set_id: str = Field(min_length=1)
    internal_validation_instance_ids: tuple[str, ...] = Field(min_length=1)
    final_test_set_id: str = Field(min_length=1)
    final_test_instance_ids: tuple[str, ...] = Field(min_length=1)
    schema_version: str = VTDO_SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_contract(self) -> ContributionDataIsolationContract:
        protected = {
            "baseline_training": self.baseline_training_instance_ids,
            "internal_validation": self.internal_validation_instance_ids,
            "final_test": self.final_test_instance_ids,
        }
        for role, instance_ids in protected.items():
            if len(instance_ids) != len(set(instance_ids)):
                raise ValueError(f"{role} contains duplicate instances")
            if any(not instance_id for instance_id in instance_ids):
                raise ValueError(f"{role} contains an empty instance identity")
        set_ids = (
            self.baseline_training_set_id,
            self.internal_validation_set_id,
            self.final_test_set_id,
        )
        if len(set(set_ids)) != len(set_ids):
            raise ValueError("Contribution train, validation, and final-test set IDs must differ")
        update_sets: dict[str, set[str]] = {}
        for state_id, instance_ids in self.probe_update_instance_ids_by_state.items():
            if not state_id or not instance_ids:
                raise ValueError("each quotient state requires a nonempty Probe update set")
            if len(instance_ids) != len(set(instance_ids)):
                raise ValueError(f"Probe update set contains duplicates:{state_id}")
            if any(not instance_id for instance_id in instance_ids):
                raise ValueError(f"Probe update set contains an empty instance:{state_id}")
            update_sets[state_id] = set(instance_ids)
        protected_sets = {role: set(values) for role, values in protected.items()}
        roles = tuple(sorted(protected_sets))
        for index, left_role in enumerate(roles):
            for right_role in roles[index + 1 :]:
                if protected_sets[left_role] & protected_sets[right_role]:
                    raise ValueError(
                        f"Contribution data leakage between {left_role} and {right_role}"
                    )
        for state_id, update_values in update_sets.items():
            for role, protected_values in protected_sets.items():
                if update_values & protected_values:
                    raise ValueError(f"Probe update instances leak into {role}:{state_id}")
        ordered_states = tuple(sorted(update_sets))
        for index, left_state in enumerate(ordered_states):
            for right_state in ordered_states[index + 1 :]:
                if update_sets[left_state] & update_sets[right_state]:
                    raise ValueError(f"Probe update sets overlap:{left_state}:{right_state}")
        if self.contract_id != contribution_data_isolation_contract_id(self):
            raise ValueError("contribution data-isolation contract identity is invalid")
        return self


class ProbeOptimizerContract(FrozenModel):
    """A local optimizer whose state cannot inherit the main training history."""

    contract_id: str = Field(min_length=1)
    optimizer_name: Literal["sgd", "adamw"]
    learning_rate: float = Field(gt=0)
    step_count: int = Field(default=3, ge=1, le=3)
    weight_decay: float = Field(default=0.0, ge=0)
    momentum: float = Field(default=0.0, ge=0)
    cold_start: Literal[True] = True
    reuse_main_optimizer_state: Literal[False] = False
    initial_state_policy: Literal["zero_state"] = "zero_state"
    schema_version: str = VTDO_SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_contract(self) -> ProbeOptimizerContract:
        if self.optimizer_name == "sgd" and not math.isclose(self.momentum, 0.0, abs_tol=1e-12):
            raise ValueError("SGD Contribution Probe requires momentum=0")
        if self.contract_id != probe_optimizer_contract_id(self):
            raise ValueError("Probe optimizer contract identity is invalid")
        return self


class ContributionProbeProtocol(FrozenModel):
    """Frozen production approximation protocol for C-hat_probe."""

    protocol_id: str = Field(min_length=1)
    beneficiary_model_state_id: str = Field(min_length=1)
    beneficiary_checkpoint_hash: str = Field(min_length=1)
    metric_contract: ContributionMetricContract
    data_isolation: ContributionDataIsolationContract
    optimizer: ProbeOptimizerContract
    probe_seeds: tuple[int, ...] = Field(min_length=1)
    schema_version: str = VTDO_SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_protocol(self) -> ContributionProbeProtocol:
        if len(self.probe_seeds) != len(set(self.probe_seeds)):
            raise ValueError("Contribution Probe seeds must be unique")
        if (
            self.metric_contract.evaluation_distribution_id
            != self.data_isolation.internal_validation_set_id
        ):
            raise ValueError("Contribution Probe must evaluate only on nu_int")
        if self.protocol_id != contribution_probe_protocol_id(self):
            raise ValueError("Contribution Probe protocol identity is invalid")
        return self


class ContributionInterventionProtocol(FrozenModel):
    """Frozen finite-perturbation validation protocol for C-hat_int."""

    protocol_id: str = Field(min_length=1)
    beneficiary_model_state_id: str = Field(min_length=1)
    beneficiary_checkpoint_hash: str = Field(min_length=1)
    metric_contract: ContributionMetricContract
    data_isolation: ContributionDataIsolationContract
    retraining_protocol_hash: str = Field(min_length=1)
    target_epsilon: float = Field(default=0.05, gt=0, lt=0.5)
    intervention_seeds: tuple[int, ...] = Field(min_length=1)
    schema_version: str = VTDO_SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_protocol(self) -> ContributionInterventionProtocol:
        if len(self.intervention_seeds) != len(set(self.intervention_seeds)):
            raise ValueError("Contribution Intervention seeds must be unique")
        if (
            self.metric_contract.evaluation_distribution_id
            != self.data_isolation.internal_validation_set_id
        ):
            raise ValueError("Contribution Intervention must evaluate only on nu_int")
        expected = intervention_addition_count(
            len(self.data_isolation.baseline_training_instance_ids),
            self.target_epsilon,
        )
        mismatched = tuple(
            state_id
            for state_id, instance_ids in sorted(
                self.data_isolation.probe_update_instance_ids_by_state.items()
            )
            if len(instance_ids) != expected
        )
        if mismatched:
            raise ValueError(
                f"finite Intervention update sets do not implement the frozen epsilon:{mismatched}"
            )
        if self.protocol_id != contribution_intervention_protocol_id(self):
            raise ValueError("Contribution Intervention protocol identity is invalid")
        return self


class ProbeAdaptationResult(FrozenModel):
    adapted_model_state_id: str = Field(min_length=1)
    adapted_checkpoint_hash: str = Field(min_length=1)
    base_model_state_id: str = Field(min_length=1)
    base_checkpoint_hash: str = Field(min_length=1)
    optimizer_contract_id: str = Field(min_length=1)
    initial_optimizer_state_hash: str = Field(min_length=1)
    executed_step_count: int = Field(ge=1, le=3)


class InterventionTrainingResult(FrozenModel):
    intervention_model_state_id: str = Field(min_length=1)
    intervention_checkpoint_hash: str = Field(min_length=1)
    base_model_state_id: str = Field(min_length=1)
    base_checkpoint_hash: str = Field(min_length=1)
    retraining_protocol_hash: str = Field(min_length=1)
    baseline_training_set_id: str = Field(min_length=1)


class ContributionProbeObservation(FrozenModel):
    """One cold-start local adaptation measurement for C-hat_probe(x, z)."""

    observation_id: str = Field(min_length=1)
    task_condition_id: str = Field(min_length=1)
    round_index: int = Field(ge=0)
    state_id: str = Field(min_length=1)
    probe_contract: ContributionProbeProtocol
    seed: int
    adaptation_result: ProbeAdaptationResult
    baseline_performance: float
    adapted_performance: float
    performance_gain: float
    measurement_confidence: float = Field(default=1.0, ge=0, le=1)
    update_sample_count: int = Field(ge=1)
    validation_sample_count: int = Field(ge=1)
    schema_version: str = VTDO_SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_observation(self) -> ContributionProbeObservation:
        _validate_finite_scores(
            self.baseline_performance,
            self.adapted_performance,
            self.performance_gain,
        )
        if self.task_condition_id != self.probe_contract.data_isolation.task_condition_id:
            raise ValueError("Contribution Probe crosses task conditions")
        if (
            self.state_id
            not in self.probe_contract.data_isolation.probe_update_instance_ids_by_state
        ):
            raise ValueError("Contribution Probe state is absent from its B_z contract")
        if self.seed not in self.probe_contract.probe_seeds:
            raise ValueError("Contribution Probe seed is absent from its protocol")
        _validate_probe_adaptation_result(self.probe_contract, self.adaptation_result)
        expected_gain = self.adapted_performance - self.baseline_performance
        if not math.isclose(self.performance_gain, expected_gain, abs_tol=1e-12):
            raise ValueError("Contribution Probe performance gain is inconsistent")
        expected_update_count = len(
            self.probe_contract.data_isolation.probe_update_instance_ids_by_state[self.state_id]
        )
        if self.update_sample_count != expected_update_count:
            raise ValueError("Contribution Probe update sample count is inconsistent")
        if self.validation_sample_count != len(
            self.probe_contract.data_isolation.internal_validation_instance_ids
        ):
            raise ValueError("Contribution Probe validation sample count is inconsistent")
        if self.observation_id != contribution_probe_observation_id(self):
            raise ValueError("Contribution Probe observation identity is invalid")
        return self


class ContributionInterventionObservation(FrozenModel):
    """One finite retraining perturbation measuring (J(M+z)-J(M))/epsilon."""

    observation_id: str = Field(min_length=1)
    task_condition_id: str = Field(min_length=1)
    round_index: int = Field(ge=0)
    state_id: str = Field(min_length=1)
    intervention_contract: ContributionInterventionProtocol
    seed: int
    training_result: InterventionTrainingResult
    baseline_performance: float
    intervention_performance: float
    performance_gain: float
    epsilon: float = Field(gt=0, lt=1)
    normalized_intervention_contribution: float
    validation_sample_count: int = Field(ge=1)
    schema_version: str = VTDO_SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_observation(self) -> ContributionInterventionObservation:
        _validate_finite_scores(
            self.baseline_performance,
            self.intervention_performance,
            self.performance_gain,
            self.normalized_intervention_contribution,
        )
        if self.task_condition_id != self.intervention_contract.data_isolation.task_condition_id:
            raise ValueError("Contribution Intervention crosses task conditions")
        if (
            self.state_id
            not in self.intervention_contract.data_isolation.probe_update_instance_ids_by_state
        ):
            raise ValueError("Contribution Intervention state is absent from its delta set")
        if self.seed not in self.intervention_contract.intervention_seeds:
            raise ValueError("Contribution Intervention seed is absent from its protocol")
        _validate_intervention_training_result(
            self.intervention_contract,
            self.training_result,
        )
        expected_gain = self.intervention_performance - self.baseline_performance
        if not math.isclose(self.performance_gain, expected_gain, abs_tol=1e-12):
            raise ValueError("Contribution Intervention performance gain is inconsistent")
        baseline_count = len(
            self.intervention_contract.data_isolation.baseline_training_instance_ids
        )
        addition_count = len(
            self.intervention_contract.data_isolation.probe_update_instance_ids_by_state[
                self.state_id
            ]
        )
        expected_epsilon = addition_count / (baseline_count + addition_count)
        if not math.isclose(self.epsilon, expected_epsilon, abs_tol=1e-12):
            raise ValueError("Contribution Intervention epsilon is inconsistent")
        expected_contribution = self.performance_gain / self.epsilon
        if not math.isclose(
            self.normalized_intervention_contribution,
            expected_contribution,
            abs_tol=1e-12,
        ):
            raise ValueError("Contribution Intervention normalization is inconsistent")
        if self.validation_sample_count != len(
            self.intervention_contract.data_isolation.internal_validation_instance_ids
        ):
            raise ValueError("Contribution Intervention validation sample count is inconsistent")
        if self.observation_id != contribution_intervention_observation_id(self):
            raise ValueError("Contribution Intervention observation identity is invalid")
        return self


class SyntheticOracleContributionObservation(FrozenModel):
    """A controlled-experiment oracle value, never a production model probe."""

    observation_id: str = Field(min_length=1)
    task_condition_id: str = Field(min_length=1)
    round_index: int = Field(ge=0)
    state_id: str = Field(min_length=1)
    oracle_contribution: float
    oracle_protocol_hash: str = Field(min_length=1)
    schema_version: str = VTDO_SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_observation(self) -> SyntheticOracleContributionObservation:
        _validate_finite_scores(self.oracle_contribution)
        if self.observation_id != synthetic_oracle_contribution_observation_id(self):
            raise ValueError("synthetic Contribution oracle identity is invalid")
        return self


class ContributionProbeRuntimeProtocol(Protocol):
    def evaluate(
        self,
        model_state_id: str,
        checkpoint_hash: str,
        instance_ids: tuple[str, ...],
        metric_contract: ContributionMetricContract,
    ) -> float: ...

    def cold_start_adapt(
        self,
        beneficiary_model_state_id: str,
        beneficiary_checkpoint_hash: str,
        update_instance_ids: tuple[str, ...],
        optimizer_contract: ProbeOptimizerContract,
        seed: int,
    ) -> ProbeAdaptationResult: ...


class ContributionInterventionRuntimeProtocol(Protocol):
    def evaluate(
        self,
        model_state_id: str,
        checkpoint_hash: str,
        instance_ids: tuple[str, ...],
        metric_contract: ContributionMetricContract,
    ) -> float: ...

    def retrain_with_intervention(
        self,
        beneficiary_model_state_id: str,
        beneficiary_checkpoint_hash: str,
        baseline_training_instance_ids: tuple[str, ...],
        added_instance_ids: tuple[str, ...],
        retraining_protocol_hash: str,
        seed: int,
    ) -> InterventionTrainingResult: ...


def make_contribution_metric_contract(
    *,
    target_metric_id: str,
    evaluation_distribution_id: str,
    evaluation_snapshot_hash: str,
    score_transform: Literal["identity", "negative_loss"],
) -> ContributionMetricContract:
    values = {
        "target_metric_id": target_metric_id,
        "evaluation_distribution_id": evaluation_distribution_id,
        "evaluation_snapshot_hash": evaluation_snapshot_hash,
        "objective_direction": "higher_is_better",
        "score_transform": score_transform,
        "schema_version": VTDO_SCHEMA_VERSION,
    }
    provisional = ContributionMetricContract.model_construct(contract_id="pending", **values)
    return ContributionMetricContract(
        contract_id=contribution_metric_contract_id(provisional),
        **values,
    )


def make_contribution_data_isolation_contract(
    *,
    task_condition_id: str,
    baseline_training_set_id: str,
    baseline_training_instance_ids: Iterable[str],
    probe_update_instance_ids_by_state: Mapping[str, Iterable[str]],
    internal_validation_set_id: str,
    internal_validation_instance_ids: Iterable[str],
    final_test_set_id: str,
    final_test_instance_ids: Iterable[str],
) -> ContributionDataIsolationContract:
    values = {
        "task_condition_id": task_condition_id,
        "baseline_training_set_id": baseline_training_set_id,
        "baseline_training_instance_ids": tuple(baseline_training_instance_ids),
        "probe_update_instance_ids_by_state": {
            state_id: tuple(instance_ids)
            for state_id, instance_ids in sorted(probe_update_instance_ids_by_state.items())
        },
        "internal_validation_set_id": internal_validation_set_id,
        "internal_validation_instance_ids": tuple(internal_validation_instance_ids),
        "final_test_set_id": final_test_set_id,
        "final_test_instance_ids": tuple(final_test_instance_ids),
        "schema_version": VTDO_SCHEMA_VERSION,
    }
    provisional = ContributionDataIsolationContract.model_construct(
        contract_id="pending",
        **values,
    )
    return ContributionDataIsolationContract(
        contract_id=contribution_data_isolation_contract_id(provisional),
        **values,
    )


def make_probe_optimizer_contract(
    *,
    optimizer_name: Literal["sgd", "adamw"] = "sgd",
    learning_rate: float,
    step_count: int = 3,
    weight_decay: float = 0.0,
    momentum: float = 0.0,
) -> ProbeOptimizerContract:
    values = {
        "optimizer_name": optimizer_name,
        "learning_rate": learning_rate,
        "step_count": step_count,
        "weight_decay": weight_decay,
        "momentum": momentum,
        "cold_start": True,
        "reuse_main_optimizer_state": False,
        "initial_state_policy": "zero_state",
        "schema_version": VTDO_SCHEMA_VERSION,
    }
    provisional = ProbeOptimizerContract.model_construct(contract_id="pending", **values)
    return ProbeOptimizerContract(
        contract_id=probe_optimizer_contract_id(provisional),
        **values,
    )


def make_contribution_probe_protocol(
    *,
    beneficiary_model_state_id: str,
    beneficiary_checkpoint_hash: str,
    metric_contract: ContributionMetricContract,
    data_isolation: ContributionDataIsolationContract,
    optimizer: ProbeOptimizerContract,
    probe_seeds: Iterable[int],
) -> ContributionProbeProtocol:
    values = {
        "beneficiary_model_state_id": beneficiary_model_state_id,
        "beneficiary_checkpoint_hash": beneficiary_checkpoint_hash,
        "metric_contract": metric_contract,
        "data_isolation": data_isolation,
        "optimizer": optimizer,
        "probe_seeds": tuple(sorted(probe_seeds)),
        "schema_version": VTDO_SCHEMA_VERSION,
    }
    provisional = ContributionProbeProtocol.model_construct(protocol_id="pending", **values)
    return ContributionProbeProtocol(
        protocol_id=contribution_probe_protocol_id(provisional),
        **values,
    )


def make_contribution_intervention_protocol(
    *,
    beneficiary_model_state_id: str,
    beneficiary_checkpoint_hash: str,
    metric_contract: ContributionMetricContract,
    data_isolation: ContributionDataIsolationContract,
    retraining_protocol_hash: str,
    intervention_seeds: Iterable[int],
    target_epsilon: float = 0.05,
) -> ContributionInterventionProtocol:
    values = {
        "beneficiary_model_state_id": beneficiary_model_state_id,
        "beneficiary_checkpoint_hash": beneficiary_checkpoint_hash,
        "metric_contract": metric_contract,
        "data_isolation": data_isolation,
        "retraining_protocol_hash": retraining_protocol_hash,
        "target_epsilon": target_epsilon,
        "intervention_seeds": tuple(sorted(intervention_seeds)),
        "schema_version": VTDO_SCHEMA_VERSION,
    }
    provisional = ContributionInterventionProtocol.model_construct(
        protocol_id="pending",
        **values,
    )
    return ContributionInterventionProtocol(
        protocol_id=contribution_intervention_protocol_id(provisional),
        **values,
    )


def make_contribution_probe_observation(
    *,
    task_condition_id: str,
    round_index: int,
    state_id: str,
    protocol: ContributionProbeProtocol,
    seed: int,
    adaptation_result: ProbeAdaptationResult,
    baseline_performance: float,
    adapted_performance: float,
    measurement_confidence: float = 1.0,
) -> ContributionProbeObservation:
    values = {
        "task_condition_id": task_condition_id,
        "round_index": round_index,
        "state_id": state_id,
        "probe_contract": protocol,
        "seed": seed,
        "adaptation_result": adaptation_result,
        "baseline_performance": baseline_performance,
        "adapted_performance": adapted_performance,
        "performance_gain": adapted_performance - baseline_performance,
        "measurement_confidence": measurement_confidence,
        "update_sample_count": len(
            protocol.data_isolation.probe_update_instance_ids_by_state[state_id]
        ),
        "validation_sample_count": len(protocol.data_isolation.internal_validation_instance_ids),
        "schema_version": VTDO_SCHEMA_VERSION,
    }
    provisional = ContributionProbeObservation.model_construct(
        observation_id="pending",
        **values,
    )
    return ContributionProbeObservation(
        observation_id=contribution_probe_observation_id(provisional),
        **values,
    )


def make_contribution_intervention_observation(
    *,
    task_condition_id: str,
    round_index: int,
    state_id: str,
    protocol: ContributionInterventionProtocol,
    seed: int,
    training_result: InterventionTrainingResult,
    baseline_performance: float,
    intervention_performance: float,
) -> ContributionInterventionObservation:
    baseline_count = len(protocol.data_isolation.baseline_training_instance_ids)
    addition_count = len(protocol.data_isolation.probe_update_instance_ids_by_state[state_id])
    epsilon = addition_count / (baseline_count + addition_count)
    gain = intervention_performance - baseline_performance
    values = {
        "task_condition_id": task_condition_id,
        "round_index": round_index,
        "state_id": state_id,
        "intervention_contract": protocol,
        "seed": seed,
        "training_result": training_result,
        "baseline_performance": baseline_performance,
        "intervention_performance": intervention_performance,
        "performance_gain": gain,
        "epsilon": epsilon,
        "normalized_intervention_contribution": gain / epsilon,
        "validation_sample_count": len(protocol.data_isolation.internal_validation_instance_ids),
        "schema_version": VTDO_SCHEMA_VERSION,
    }
    provisional = ContributionInterventionObservation.model_construct(
        observation_id="pending",
        **values,
    )
    return ContributionInterventionObservation(
        observation_id=contribution_intervention_observation_id(provisional),
        **values,
    )


def make_synthetic_oracle_contribution_observation(
    *,
    task_condition_id: str,
    round_index: int,
    state_id: str,
    oracle_contribution: float,
    oracle_protocol_hash: str,
) -> SyntheticOracleContributionObservation:
    values = {
        "task_condition_id": task_condition_id,
        "round_index": round_index,
        "state_id": state_id,
        "oracle_contribution": oracle_contribution,
        "oracle_protocol_hash": oracle_protocol_hash,
        "schema_version": VTDO_SCHEMA_VERSION,
    }
    provisional = SyntheticOracleContributionObservation.model_construct(
        observation_id="pending",
        **values,
    )
    return SyntheticOracleContributionObservation(
        observation_id=synthetic_oracle_contribution_observation_id(provisional),
        **values,
    )


def run_contribution_probe(
    runtime: ContributionProbeRuntimeProtocol,
    *,
    protocol: ContributionProbeProtocol,
    round_index: int,
    state_id: str,
    seed: int,
    measurement_confidence: float = 1.0,
) -> ContributionProbeObservation:
    update_ids = protocol.data_isolation.probe_update_instance_ids_by_state[state_id]
    validation_ids = protocol.data_isolation.internal_validation_instance_ids
    baseline = runtime.evaluate(
        protocol.beneficiary_model_state_id,
        protocol.beneficiary_checkpoint_hash,
        validation_ids,
        protocol.metric_contract,
    )
    adapted = runtime.cold_start_adapt(
        protocol.beneficiary_model_state_id,
        protocol.beneficiary_checkpoint_hash,
        update_ids,
        protocol.optimizer,
        seed,
    )
    _validate_probe_adaptation_result(protocol, adapted)
    after = runtime.evaluate(
        adapted.adapted_model_state_id,
        adapted.adapted_checkpoint_hash,
        validation_ids,
        protocol.metric_contract,
    )
    return make_contribution_probe_observation(
        task_condition_id=protocol.data_isolation.task_condition_id,
        round_index=round_index,
        state_id=state_id,
        protocol=protocol,
        seed=seed,
        adaptation_result=adapted,
        baseline_performance=baseline,
        adapted_performance=after,
        measurement_confidence=measurement_confidence,
    )


def run_contribution_intervention(
    runtime: ContributionInterventionRuntimeProtocol,
    *,
    protocol: ContributionInterventionProtocol,
    round_index: int,
    state_id: str,
    seed: int,
) -> ContributionInterventionObservation:
    validation_ids = protocol.data_isolation.internal_validation_instance_ids
    baseline = runtime.evaluate(
        protocol.beneficiary_model_state_id,
        protocol.beneficiary_checkpoint_hash,
        validation_ids,
        protocol.metric_contract,
    )
    result = runtime.retrain_with_intervention(
        protocol.beneficiary_model_state_id,
        protocol.beneficiary_checkpoint_hash,
        protocol.data_isolation.baseline_training_instance_ids,
        protocol.data_isolation.probe_update_instance_ids_by_state[state_id],
        protocol.retraining_protocol_hash,
        seed,
    )
    _validate_intervention_training_result(protocol, result)
    after = runtime.evaluate(
        result.intervention_model_state_id,
        result.intervention_checkpoint_hash,
        validation_ids,
        protocol.metric_contract,
    )
    return make_contribution_intervention_observation(
        task_condition_id=protocol.data_isolation.task_condition_id,
        round_index=round_index,
        state_id=state_id,
        protocol=protocol,
        seed=seed,
        training_result=result,
        baseline_performance=baseline,
        intervention_performance=after,
    )


def estimate_contributions_from_probes(
    distribution: ConditionalTrajectoryDistribution,
    observations: Iterable[ContributionProbeObservation],
    *,
    estimator_id: str = "cold_start_local_probe.v1",
) -> ContributionEstimationManifest:
    """Aggregate local probes and center their unscaled gains under pi_t."""

    items = tuple(observations)
    by_state, protocol = _validate_probe_support(distribution, items)
    gains = {
        state_id: statistics.fmean(item.performance_gain for item in state_items)
        for state_id, state_items in by_state.items()
    }
    standard_errors = {
        state_id: _standard_error(item.performance_gain for item in state_items)
        for state_id, state_items in by_state.items()
    }
    confidences = {
        state_id: min(item.measurement_confidence for item in state_items)
        for state_id, state_items in by_state.items()
    }
    counts = {state_id: len(state_items) for state_id, state_items in by_state.items()}
    return estimate_centered_contributions(
        distribution,
        gains,
        confidences=confidences,
        observation_counts=counts,
        standard_errors=standard_errors,
        beneficiary_model_state_id=protocol.beneficiary_model_state_id,
        beneficiary_checkpoint_hash=protocol.beneficiary_checkpoint_hash,
        target_evaluation_distribution_id=(protocol.metric_contract.evaluation_distribution_id),
        target_metric_id=protocol.metric_contract.target_metric_id,
        target_metric_direction=protocol.metric_contract.objective_direction,
        estimator_kind="local_probe",
        usage_scope="production_distribution_update",
        estimation_protocol_hash=protocol.protocol_id,
        data_isolation_contract_id=protocol.data_isolation.contract_id,
        final_test_set_id=protocol.data_isolation.final_test_set_id,
        estimator_id=estimator_id,
    )


def estimate_contributions_from_interventions(
    distribution: ConditionalTrajectoryDistribution,
    observations: Iterable[ContributionInterventionObservation],
    *,
    estimator_id: str = "finite_probability_mass_intervention.v1",
) -> ContributionEstimationManifest:
    """Aggregate finite interventions for validation, not production updates."""

    items = tuple(observations)
    by_state, protocol = _validate_intervention_support(distribution, items)
    values = {
        state_id: statistics.fmean(
            item.normalized_intervention_contribution for item in state_items
        )
        for state_id, state_items in by_state.items()
    }
    standard_errors = {
        state_id: _standard_error(item.normalized_intervention_contribution for item in state_items)
        for state_id, state_items in by_state.items()
    }
    counts = {state_id: len(state_items) for state_id, state_items in by_state.items()}
    return estimate_centered_contributions(
        distribution,
        values,
        confidences={state_id: 1.0 for state_id in by_state},
        observation_counts=counts,
        standard_errors=standard_errors,
        beneficiary_model_state_id=protocol.beneficiary_model_state_id,
        beneficiary_checkpoint_hash=protocol.beneficiary_checkpoint_hash,
        target_evaluation_distribution_id=(protocol.metric_contract.evaluation_distribution_id),
        target_metric_id=protocol.metric_contract.target_metric_id,
        target_metric_direction=protocol.metric_contract.objective_direction,
        estimator_kind="finite_intervention",
        usage_scope="intervention_validation",
        estimation_protocol_hash=protocol.protocol_id,
        data_isolation_contract_id=protocol.data_isolation.contract_id,
        final_test_set_id=protocol.data_isolation.final_test_set_id,
        estimator_id=estimator_id,
    )


def estimate_synthetic_oracle_contributions(
    distribution: ConditionalTrajectoryDistribution,
    observations: Iterable[SyntheticOracleContributionObservation],
    *,
    estimator_id: str = "synthetic_oracle.v1",
) -> ContributionEstimationManifest:
    items = tuple(observations)
    if not items:
        raise ValueError("synthetic Contribution estimation requires oracle observations")
    by_state = {item.state_id: item for item in items}
    if len(by_state) != len(items) or set(by_state) != set(distribution.probabilities):
        raise ValueError("synthetic Contribution oracle must cover pi_t exactly")
    if {item.task_condition_id for item in items} != {distribution.task_condition_id}:
        raise ValueError("synthetic Contribution oracle crosses task conditions")
    if {item.round_index for item in items} != {distribution.round_index}:
        raise ValueError("synthetic Contribution oracle belongs to another round")
    protocols = {item.oracle_protocol_hash for item in items}
    if len(protocols) != 1:
        raise ValueError("synthetic Contribution oracle protocol is not frozen")
    return estimate_centered_contributions(
        distribution,
        {state_id: item.oracle_contribution for state_id, item in by_state.items()},
        confidences={state_id: 1.0 for state_id in by_state},
        observation_counts={state_id: 1 for state_id in by_state},
        standard_errors={state_id: 0.0 for state_id in by_state},
        beneficiary_model_state_id="synthetic_oracle",
        beneficiary_checkpoint_hash="synthetic_oracle",
        target_evaluation_distribution_id="synthetic_oracle",
        target_metric_id="synthetic_oracle",
        target_metric_direction="higher_is_better",
        estimator_kind="synthetic_oracle",
        usage_scope="synthetic_operator_control",
        estimation_protocol_hash=next(iter(protocols)),
        data_isolation_contract_id="not_applicable:synthetic_oracle",
        final_test_set_id="not_applicable:synthetic_oracle",
        estimator_id=estimator_id,
    )


def intervention_addition_count(
    baseline_task_sample_count: int,
    epsilon: float = 0.05,
) -> int:
    if baseline_task_sample_count < 1:
        raise ValueError("Intervention baseline requires at least one task sample")
    if not 0 < epsilon < 1:
        raise ValueError("Intervention epsilon must lie in (0, 1)")
    return math.ceil(epsilon / (1.0 - epsilon) * baseline_task_sample_count)


def empty_optimizer_state_hash(contract: ProbeOptimizerContract) -> str:
    return canonical_hash(
        {
            "optimizer_contract_id": contract.contract_id,
            "initial_state_policy": "zero_state",
            "state": {},
        },
        prefix="contribution_probe_optimizer_state:",
    )


def contribution_metric_contract_id(value: ContributionMetricContract) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"contract_id"}),
        prefix="contribution_metric_contract:",
    )


def contribution_data_isolation_contract_id(
    value: ContributionDataIsolationContract,
) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"contract_id"}),
        prefix="contribution_data_isolation_contract:",
    )


def probe_optimizer_contract_id(value: ProbeOptimizerContract) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"contract_id"}),
        prefix="contribution_probe_optimizer_contract:",
    )


def contribution_probe_protocol_id(value: ContributionProbeProtocol) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"protocol_id"}),
        prefix="contribution_probe_protocol:",
    )


def contribution_intervention_protocol_id(
    value: ContributionInterventionProtocol,
) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"protocol_id"}),
        prefix="contribution_intervention_protocol:",
    )


def contribution_probe_observation_id(value: ContributionProbeObservation) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"observation_id"}),
        prefix="trajectory_contribution_probe:",
    )


def contribution_intervention_observation_id(
    value: ContributionInterventionObservation,
) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"observation_id"}),
        prefix="trajectory_contribution_intervention:",
    )


def synthetic_oracle_contribution_observation_id(
    value: SyntheticOracleContributionObservation,
) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"observation_id"}),
        prefix="synthetic_contribution_oracle:",
    )


def _validate_probe_adaptation_result(
    protocol: ContributionProbeProtocol,
    result: ProbeAdaptationResult,
) -> None:
    if (
        result.base_model_state_id != protocol.beneficiary_model_state_id
        or result.base_checkpoint_hash != protocol.beneficiary_checkpoint_hash
        or result.optimizer_contract_id != protocol.optimizer.contract_id
        or result.executed_step_count != protocol.optimizer.step_count
        or result.initial_optimizer_state_hash != empty_optimizer_state_hash(protocol.optimizer)
        or result.adapted_model_state_id == protocol.beneficiary_model_state_id
    ):
        raise ValueError("Probe runtime violated the cold-start optimizer contract")


def _validate_intervention_training_result(
    protocol: ContributionInterventionProtocol,
    result: InterventionTrainingResult,
) -> None:
    if (
        result.base_model_state_id != protocol.beneficiary_model_state_id
        or result.base_checkpoint_hash != protocol.beneficiary_checkpoint_hash
        or result.retraining_protocol_hash != protocol.retraining_protocol_hash
        or result.baseline_training_set_id != protocol.data_isolation.baseline_training_set_id
        or result.intervention_model_state_id == protocol.beneficiary_model_state_id
    ):
        raise ValueError("Intervention runtime violated the frozen retraining contract")


def _validate_probe_support(
    distribution: ConditionalTrajectoryDistribution,
    items: tuple[ContributionProbeObservation, ...],
) -> tuple[dict[str, tuple[ContributionProbeObservation, ...]], ContributionProbeProtocol]:
    if not items:
        raise ValueError("Contribution estimation requires empirical Probe observations")
    protocols = {item.probe_contract.protocol_id: item.probe_contract for item in items}
    if len(protocols) != 1:
        raise ValueError("Contribution Probes must use one frozen protocol")
    protocol = next(iter(protocols.values()))
    if protocol.data_isolation.task_condition_id != distribution.task_condition_id:
        raise ValueError("Contribution Probe protocol crosses task conditions")
    if {item.round_index for item in items} != {distribution.round_index}:
        raise ValueError("Contribution Probes belong to another refinement round")
    if set(protocol.data_isolation.probe_update_instance_ids_by_state) != set(
        distribution.probabilities
    ):
        raise ValueError("Contribution Probe B_z contract must cover pi_t exactly")
    by_state = _group_probe_observations(items)
    if set(by_state) != set(distribution.probabilities):
        raise ValueError("Contribution Probes must cover pi_t exactly")
    expected_seeds = tuple(sorted(protocol.probe_seeds))
    for state_id, state_items in by_state.items():
        seeds = tuple(item.seed for item in state_items)
        if seeds != expected_seeds:
            raise ValueError(f"Contribution Probe seed coverage mismatch:{state_id}")
        if len({item.baseline_performance for item in state_items}) != 1:
            raise ValueError(f"Contribution Probe baseline varies across seeds:{state_id}")
    if len({item.baseline_performance for item in items}) != 1:
        raise ValueError("Contribution Probe baseline is not frozen across states")
    return by_state, protocol


def _validate_intervention_support(
    distribution: ConditionalTrajectoryDistribution,
    items: tuple[ContributionInterventionObservation, ...],
) -> tuple[
    dict[str, tuple[ContributionInterventionObservation, ...]],
    ContributionInterventionProtocol,
]:
    if not items:
        raise ValueError("Contribution validation requires finite Interventions")
    protocols = {
        item.intervention_contract.protocol_id: item.intervention_contract for item in items
    }
    if len(protocols) != 1:
        raise ValueError("Contribution Interventions must use one frozen protocol")
    protocol = next(iter(protocols.values()))
    if protocol.data_isolation.task_condition_id != distribution.task_condition_id:
        raise ValueError("Contribution Intervention protocol crosses task conditions")
    if {item.round_index for item in items} != {distribution.round_index}:
        raise ValueError("Contribution Interventions belong to another refinement round")
    if set(protocol.data_isolation.probe_update_instance_ids_by_state) != set(
        distribution.probabilities
    ):
        raise ValueError("Contribution Intervention delta sets must cover pi_t exactly")
    grouped: defaultdict[str, list[ContributionInterventionObservation]] = defaultdict(list)
    for item in items:
        grouped[item.state_id].append(item)
    by_state = {
        state_id: tuple(sorted(state_items, key=lambda item: item.seed))
        for state_id, state_items in sorted(grouped.items())
    }
    if set(by_state) != set(distribution.probabilities):
        raise ValueError("Contribution Interventions must cover pi_t exactly")
    expected_seeds = tuple(sorted(protocol.intervention_seeds))
    for state_id, state_items in by_state.items():
        if tuple(item.seed for item in state_items) != expected_seeds:
            raise ValueError(f"Contribution Intervention seed coverage mismatch:{state_id}")
    if len({item.baseline_performance for item in items}) != 1:
        raise ValueError("Contribution Intervention baseline is not frozen across states and seeds")
    return by_state, protocol


def _group_probe_observations(
    items: tuple[ContributionProbeObservation, ...],
) -> dict[str, tuple[ContributionProbeObservation, ...]]:
    grouped: defaultdict[str, list[ContributionProbeObservation]] = defaultdict(list)
    for item in items:
        grouped[item.state_id].append(item)
    return {
        state_id: tuple(sorted(state_items, key=lambda item: item.seed))
        for state_id, state_items in sorted(grouped.items())
    }


def _standard_error(values: Iterable[float]) -> float:
    items = tuple(values)
    if len(items) < 2:
        return 0.0
    return statistics.stdev(items) / math.sqrt(len(items))


def _validate_finite_scores(*values: float) -> None:
    if any(not math.isfinite(value) for value in values):
        raise ValueError("Contribution scores must be finite")
