from __future__ import annotations

import argparse
import hashlib
import json
from collections.abc import Sequence
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_decision_stable_protocol import (  # noqa: E501
    FinanceCapabilityDecisionStableProtocol,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_stable_submechanism_geometry import (  # noqa: E501
    StableIdentifiableSubspacePolicy,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_stopping_boundary_calibration import (  # noqa: E501
    STOPPING_PARENT_ID,
    FinanceStoppingBoundaryCalibrationContract,
    FinanceStoppingBoundaryCalibrationReport,
)
from trusted_synthesis.hashing import canonical_hash

CROSS_POPULATION_STABLE_PROTOCOL_VERSION = "finance_cross_population_stable_support_protocol.v1"
CROSS_POPULATION_EXPERIMENT_LABEL = "finance_v25_35_cross_population_stable_support_development"

EXPECTED_POPULATION_COUNT = 3
EXPECTED_TASK_COUNT = 60
EXPECTED_ROLLOUT_COUNT = 480
EXPECTED_TASKS_PER_POPULATION = 20
EXPECTED_ROLLOUTS_PER_POPULATION = 160

STOPPING_SHAPE_MAPPING: dict[str, tuple[str, ...]] = {
    "incomplete_source_must_continue": (
        f"{STOPPING_PARENT_ID}.incomplete_continue",
        f"{STOPPING_PARENT_ID}.uncertain_source_coverage",
    ),
    "unresolved_conflict_cannot_stop": (f"{STOPPING_PARENT_ID}.unresolved_conflict_cannot_stop",),
    "evidence_complete_should_stop": (
        f"{STOPPING_PARENT_ID}.post_complete_cost",
        f"{STOPPING_PARENT_ID}.post_complete_error_risk",
    ),
    "extra_call_adds_cost": (f"{STOPPING_PARENT_ID}.post_complete_cost",),
    "extra_call_risks_wrong_candidate": (f"{STOPPING_PARENT_ID}.post_complete_error_risk",),
    "terminal_answer_depends_on_stopping_moment": (
        f"{STOPPING_PARENT_ID}.incomplete_continue",
        f"{STOPPING_PARENT_ID}.post_complete_cost",
        f"{STOPPING_PARENT_ID}.post_complete_error_risk",
    ),
}

TYPED_CONTEXT_MUTATIONS = (
    "missing_conflict_dimensions_rejected",
    "action_order_permutation_accepted",
    "unavailable_distractor_action_rejected",
    "latest_typed_prerequisite_survives_repeated_failure",
    "host_secret_injection_absent",
)


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class FrozenArtifactReference(FrozenModel):
    path: str = Field(min_length=1)
    sha256: str = Field(min_length=64, max_length=64)
    artifact_id: str = Field(min_length=1)


class FinanceCrossPopulationStableProtocol(FrozenModel):
    protocol_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    experiment_label: Literal["finance_v25_35_cross_population_stable_support_development"] = (
        "finance_v25_35_cross_population_stable_support_development"
    )
    source_stable_protocol: FrozenArtifactReference
    source_stopping_calibration_contract: FrozenArtifactReference
    source_stopping_calibration_report: FrozenArtifactReference
    historical_population_references: tuple[FrozenArtifactReference, ...] = Field(min_length=1)
    stable_subspace_policy: StableIdentifiableSubspacePolicy
    population_count: Literal[3] = 3
    task_count: Literal[60] = 60
    rollout_count: Literal[480] = 480
    tasks_per_population: Literal[20] = 20
    rollouts_per_population: Literal[160] = 160
    stopping_shape_mapping: dict[str, tuple[str, ...]] = STOPPING_SHAPE_MAPPING
    typed_context_mutations: tuple[str, ...] = TYPED_CONTEXT_MUTATIONS
    require_per_population_execution_integrity: float = Field(default=1.0, ge=1, le=1)
    require_per_population_terminal_resolution: float = Field(default=1.0, ge=1, le=1)
    require_per_population_observation_replay: float = Field(default=1.0, ge=1, le=1)
    require_per_population_authority_integrity: float = Field(default=1.0, ge=1, le=1)
    require_per_population_l0_l2_failure_count: Literal[0] = 0
    require_per_population_typed_context_replay: float = Field(default=1.0, ge=1, le=1)
    require_stopping_parent_bootstrap_lcb_strictly_positive: Literal[True] = True
    require_stopping_nonzero_task_count: Literal[2] = 2
    pooled_result_may_rescue_population_failure: Literal[False] = False
    action_relevant_public_state_observable: Literal[True] = True
    action_relevant_public_state_replayable: Literal[True] = True
    historical_results_reclassified: Literal[False] = False
    pro_api_call_count: Literal[0] = 0
    beneficiary_screening_authorized: Literal[False] = False
    validation_objective_access: Literal["forbidden"] = "forbidden"
    authorization_objective_access: Literal["forbidden"] = "forbidden"
    exact_target_evaluated: Literal[False] = False
    gp_c_evaluated: Literal[False] = False
    production_contribution: float = Field(default=0, ge=0, le=0)
    next_permitted_stage: Literal["fresh_cross_population_stable_development_population_build"] = (
        "fresh_cross_population_stable_development_population_build"
    )
    schema_version: str = CROSS_POPULATION_STABLE_PROTOCOL_VERSION

    @model_validator(mode="after")
    def validate_protocol(self) -> FinanceCrossPopulationStableProtocol:
        if self.schema_version != CROSS_POPULATION_STABLE_PROTOCOL_VERSION:
            raise ValueError("cross-population stable protocol version is unsupported")
        if self.stopping_shape_mapping != STOPPING_SHAPE_MAPPING:
            raise ValueError("cross-population stopping-shape coverage changed")
        if self.typed_context_mutations != TYPED_CONTEXT_MUTATIONS:
            raise ValueError("cross-population typed-context mutations changed")
        population_ids = {item.artifact_id for item in self.historical_population_references}
        if len(population_ids) != len(self.historical_population_references):
            raise ValueError("historical population references are duplicated")
        if self.protocol_id != cross_population_stable_protocol_id(self):
            raise ValueError("cross-population stable protocol identity is invalid")
        return self


def cross_population_stable_protocol_id(
    value: FinanceCrossPopulationStableProtocol,
) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"protocol_id"}),
        prefix="finance_cross_population_stable_support_protocol:",
    )


def prepare_cross_population_stable_protocol(
    *,
    source_stable_protocol_path: Path,
    stopping_calibration_contract_path: Path,
    stopping_calibration_report_path: Path,
    historical_population_paths: tuple[Path, ...],
    output_path: Path,
    run_id: str,
) -> FinanceCrossPopulationStableProtocol:
    if output_path.exists():
        raise ValueError("cross-population stable protocol is immutable")
    if not historical_population_paths:
        raise ValueError("cross-population protocol lacks historical exclusions")
    stable_path = source_stable_protocol_path.resolve()
    calibration_contract_path = stopping_calibration_contract_path.resolve()
    calibration_report_path = stopping_calibration_report_path.resolve()
    stable = FinanceCapabilityDecisionStableProtocol.model_validate_json(
        stable_path.read_text(encoding="utf-8")
    )
    calibration_contract = FinanceStoppingBoundaryCalibrationContract.model_validate_json(
        calibration_contract_path.read_text(encoding="utf-8")
    )
    calibration_report = FinanceStoppingBoundaryCalibrationReport.model_validate_json(
        calibration_report_path.read_text(encoding="utf-8")
    )
    if calibration_report.contract_id != calibration_contract.contract_id:
        raise ValueError("stopping calibration lineage is inconsistent")
    if not (
        calibration_report.runtime_measurement_ready
        and calibration_report.stopping_instrument_repair_validated
        and calibration_report.boundary_signal_observed
        and calibration_report.fresh_stable_support_development_permitted
        and calibration_report.next_permitted_stage
        == "fresh_stable_support_development_population_build"
    ):
        raise ValueError("stopping calibration did not authorize fresh Development")
    population_paths = tuple(
        sorted((item.resolve() for item in historical_population_paths), key=str)
    )
    population_payloads = tuple(
        json.loads(path.read_text(encoding="utf-8")) for path in population_paths
    )
    population_ids = tuple(
        str(item.get("population_id", "")) if isinstance(item, dict) else ""
        for item in population_payloads
    )
    if not all(population_ids) or len(set(population_ids)) != len(population_ids):
        raise ValueError("historical population identities are missing or duplicated")
    references = tuple(
        FrozenArtifactReference(
            path=str(path),
            sha256=_sha256(path),
            artifact_id=population_id,
        )
        for path, population_id in zip(population_paths, population_ids, strict=True)
    )
    values = {
        "run_id": run_id,
        "source_stable_protocol": _reference(stable_path, stable.protocol_id),
        "source_stopping_calibration_contract": _reference(
            calibration_contract_path, calibration_contract.contract_id
        ),
        "source_stopping_calibration_report": _reference(
            calibration_report_path, calibration_report.report_id
        ),
        "historical_population_references": references,
        "stable_subspace_policy": stable.stable_subspace_policy,
    }
    provisional = FinanceCrossPopulationStableProtocol.model_construct(
        protocol_id="pending", **values
    )
    protocol = FinanceCrossPopulationStableProtocol(
        protocol_id=cross_population_stable_protocol_id(provisional), **values
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    _write_json(output_path, protocol.model_dump(mode="json"))
    output_path.with_suffix(".md").write_text(_render_protocol(protocol), encoding="utf-8")
    return protocol


def verify_cross_population_stable_protocol_inputs(
    protocol: FinanceCrossPopulationStableProtocol,
) -> None:
    references = (
        protocol.source_stable_protocol,
        protocol.source_stopping_calibration_contract,
        protocol.source_stopping_calibration_report,
        *protocol.historical_population_references,
    )
    for reference in references:
        path = Path(reference.path)
        if _sha256(path) != reference.sha256:
            raise ValueError(f"cross-population frozen input changed:{path}")
    stable = FinanceCapabilityDecisionStableProtocol.model_validate_json(
        Path(protocol.source_stable_protocol.path).read_text(encoding="utf-8")
    )
    calibration_contract = FinanceStoppingBoundaryCalibrationContract.model_validate_json(
        Path(protocol.source_stopping_calibration_contract.path).read_text(encoding="utf-8")
    )
    calibration_report = FinanceStoppingBoundaryCalibrationReport.model_validate_json(
        Path(protocol.source_stopping_calibration_report.path).read_text(encoding="utf-8")
    )
    if (
        stable.protocol_id != protocol.source_stable_protocol.artifact_id
        or calibration_contract.contract_id
        != protocol.source_stopping_calibration_contract.artifact_id
        or calibration_report.report_id != protocol.source_stopping_calibration_report.artifact_id
    ):
        raise ValueError("cross-population protocol artifact identity changed")


def _reference(path: Path, artifact_id: str) -> FrozenArtifactReference:
    return FrozenArtifactReference(path=str(path), sha256=_sha256(path), artifact_id=artifact_id)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_json(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _render_protocol(protocol: FinanceCrossPopulationStableProtocol) -> str:
    return "\n".join(
        (
            "# Finance v25.35 Cross-population Stable-support Protocol",
            "",
            "## Frozen Design",
            "",
            f"- Protocol ID: `{protocol.protocol_id}`",
            "- Three mutually disjoint fresh populations",
            "- 60 tasks / 480 Flash rollouts",
            "- Every population is judged independently; pooled rescue is forbidden",
            "- Six Stopping decision shapes are structurally required",
            "- Typed failed-action context is observable, replayable, and mutation-tested",
            "- Stopping parent bootstrap LCB must be strictly positive in every population",
            "- At least two nonzero Stopping tasks are required in every population",
            "",
            "v25.33 remains a frozen failure. v25.34 authorizes only this fresh Development.",
            "Pro, Beneficiary, Exact Target, GP-C, and Contribution remain blocked.",
            "",
        )
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Freeze v25.35 cross-population stable-support protocol"
    )
    parser.add_argument("--source-stable-protocol", required=True, type=Path)
    parser.add_argument("--stopping-calibration-contract", required=True, type=Path)
    parser.add_argument("--stopping-calibration-report", required=True, type=Path)
    parser.add_argument("--historical-population", action="append", required=True, type=Path)
    parser.add_argument("--output-path", required=True, type=Path)
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args(argv)
    protocol = prepare_cross_population_stable_protocol(
        source_stable_protocol_path=args.source_stable_protocol,
        stopping_calibration_contract_path=args.stopping_calibration_contract,
        stopping_calibration_report_path=args.stopping_calibration_report,
        historical_population_paths=tuple(args.historical_population),
        output_path=args.output_path,
        run_id=args.run_id,
    )
    print(
        json.dumps(
            {
                "protocol_id": protocol.protocol_id,
                "historical_population_count": len(protocol.historical_population_references),
                "task_count": protocol.task_count,
                "rollout_count": protocol.rollout_count,
                "next_permitted_stage": protocol.next_permitted_stage,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
