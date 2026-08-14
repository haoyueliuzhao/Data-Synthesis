from __future__ import annotations

import argparse
import hashlib
import json
from collections.abc import Sequence
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_submechanism_flash_development import (  # noqa: E501
    PRIMARY_RESPONSE_VARIABLE,
    FinanceSubmechanismFlashContract,
    FinanceSubmechanismFlashReport,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_stable_submechanism_geometry import (  # noqa: E501
    StableIdentifiableSubspacePolicy,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_stable_submechanism_protocol import (  # noqa: E501
    FinanceStableSupportProtocol,
)
from trusted_synthesis.hashing import canonical_hash

CAPABILITY_DECISION_STABLE_PROTOCOL_VERSION = (
    "finance_capability_decision_stable_support_protocol.v1"
)
REQUIRED_DISJOINTNESS_DIMENSIONS = (
    "task",
    "evidence",
    "evidence_version",
    "semantic_signature",
    "submechanism_signature_instance",
)


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class FinanceCapabilityDecisionStableProtocol(FrozenModel):
    protocol_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    experiment_label: Literal["finance_v25_33_capability_decision_stable_support"] = (
        "finance_v25_33_capability_decision_stable_support"
    )
    source_stable_protocol_path: str = Field(min_length=1)
    source_stable_protocol_sha256: str = Field(min_length=64, max_length=64)
    source_stable_protocol_id: str = Field(min_length=1)
    source_calibration_contract_path: str = Field(min_length=1)
    source_calibration_contract_sha256: str = Field(min_length=64, max_length=64)
    source_calibration_contract_id: str = Field(min_length=1)
    source_calibration_report_path: str = Field(min_length=1)
    source_calibration_report_sha256: str = Field(min_length=64, max_length=64)
    source_calibration_report_id: str = Field(min_length=1)
    calibration_runtime_ready: Literal[True]
    calibration_geometry_admitted: Literal[False]
    calibration_failure_codes: tuple[str, ...]
    calibration_identifiable_rank: int = Field(ge=0)
    calibration_effective_rank: float = Field(ge=0)
    calibration_condition_number: float = Field(gt=0)
    calibration_parent_information_share: dict[str, float]
    primary_response_variable: Literal["capability_contract_success"] = (
        "capability_contract_success"
    )
    stable_subspace_policy: StableIdentifiableSubspacePolicy
    selected_task_instances_per_submechanism: Literal[3] = 3
    selected_realizations_per_task: Literal[8] = 8
    selected_task_count: Literal[60] = 60
    selected_rollout_count: Literal[480] = 480
    development_population_count: Literal[3] = 3
    confirmation_population_count: Literal[3] = 3
    required_disjointness_dimensions: tuple[str, ...] = REQUIRED_DISJOINTNESS_DIMENSIONS
    historical_results_reclassified: Literal[False] = False
    pro_api_call_count: Literal[0] = 0
    beneficiary_screening_authorized: Literal[False] = False
    validation_objective_access: Literal["forbidden"] = "forbidden"
    authorization_objective_access: Literal["forbidden"] = "forbidden"
    exact_target_evaluated: Literal[False] = False
    gp_c_evaluated: Literal[False] = False
    production_contribution: float = Field(default=0, ge=0, le=0)
    next_permitted_stage: Literal[
        "capability_decision_stable_support_development_population_build"
    ] = "capability_decision_stable_support_development_population_build"
    schema_version: str = CAPABILITY_DECISION_STABLE_PROTOCOL_VERSION

    @model_validator(mode="after")
    def validate_protocol(self) -> FinanceCapabilityDecisionStableProtocol:
        if self.primary_response_variable != PRIMARY_RESPONSE_VARIABLE:
            raise ValueError("stable capability-decision response variable changed")
        if self.required_disjointness_dimensions != REQUIRED_DISJOINTNESS_DIMENSIONS:
            raise ValueError("stable capability-decision disjointness contract changed")
        if self.stable_subspace_policy.required_rank != 4:
            raise ValueError("stable capability-decision protocol no longer claims Top-4")
        if self.protocol_id != capability_decision_stable_protocol_id(self):
            raise ValueError("stable capability-decision protocol identity is invalid")
        return self


def capability_decision_stable_protocol_id(
    value: FinanceCapabilityDecisionStableProtocol,
) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"protocol_id"}),
        prefix="finance_capability_decision_stable_support_protocol:",
    )


def prepare_capability_decision_stable_protocol(
    *,
    source_stable_protocol_path: Path,
    calibration_contract_path: Path,
    calibration_report_path: Path,
    output_path: Path,
    run_id: str,
) -> FinanceCapabilityDecisionStableProtocol:
    if output_path.exists():
        raise ValueError("stable capability-decision protocol is immutable")
    stable_path = source_stable_protocol_path.resolve()
    contract_path = calibration_contract_path.resolve()
    report_path = calibration_report_path.resolve()
    stable = FinanceStableSupportProtocol.model_validate_json(
        stable_path.read_text(encoding="utf-8")
    )
    contract = FinanceSubmechanismFlashContract.model_validate_json(
        contract_path.read_text(encoding="utf-8")
    )
    report = FinanceSubmechanismFlashReport.model_validate_json(
        report_path.read_text(encoding="utf-8")
    )
    if report.contract_id != contract.contract_id:
        raise ValueError("capability-decision calibration lineage is inconsistent")
    if contract.primary_response_variable != PRIMARY_RESPONSE_VARIABLE:
        raise ValueError("calibration contract used the wrong primary response")
    if report.primary_response_variable != PRIMARY_RESPONSE_VARIABLE:
        raise ValueError("calibration report used the wrong primary response")
    if not report.runtime_measurement_ready:
        raise ValueError("capability-decision calibration Runtime did not pass")
    if report.primary_information_geometry_ready:
        raise ValueError("calibration unexpectedly authorized stable capability support")
    if report.fresh_submechanism_confirmation_authorized:
        raise ValueError("calibration unexpectedly authorized Confirmation")
    spectrum = report.primary_spectrum
    values = {
        "run_id": run_id,
        "source_stable_protocol_path": str(stable_path),
        "source_stable_protocol_sha256": _sha256(stable_path),
        "source_stable_protocol_id": stable.protocol_id,
        "source_calibration_contract_path": str(contract_path),
        "source_calibration_contract_sha256": _sha256(contract_path),
        "source_calibration_contract_id": contract.contract_id,
        "source_calibration_report_path": str(report_path),
        "source_calibration_report_sha256": _sha256(report_path),
        "source_calibration_report_id": report.report_id,
        "calibration_runtime_ready": True,
        "calibration_geometry_admitted": False,
        "calibration_failure_codes": report.failure_codes,
        "calibration_identifiable_rank": spectrum.residual_numerical_rank,
        "calibration_effective_rank": spectrum.residual_effective_rank,
        "calibration_condition_number": spectrum.residual_condition_number,
        "calibration_parent_information_share": spectrum.parent_information_share,
        "stable_subspace_policy": stable.stable_subspace_policy,
    }
    provisional = FinanceCapabilityDecisionStableProtocol.model_construct(
        protocol_id="pending", **values
    )
    protocol = FinanceCapabilityDecisionStableProtocol(
        protocol_id=capability_decision_stable_protocol_id(provisional),
        **values,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    _write_json(output_path, protocol.model_dump(mode="json"))
    output_path.with_suffix(".md").write_text(_render_protocol(protocol), encoding="utf-8")
    return protocol


def _render_protocol(protocol: FinanceCapabilityDecisionStableProtocol) -> str:
    shares = ", ".join(
        f"{key}={value:.2%}"
        for key, value in sorted(protocol.calibration_parent_information_share.items())
    )
    return "\n".join(
        (
            "# Finance v25.33 Capability-decision Stable Support Protocol",
            "",
            "## Frozen Decision",
            "",
            f"- Protocol ID: `{protocol.protocol_id}`",
            f"- Primary response: `{protocol.primary_response_variable}`",
            "- Design: **3 independent task instances × 8 realizations**",
            "- Development denominator: **60 tasks / 480 Flash rollouts**",
            "- Claimed identifiable subspace: **Top-4**",
            (
                "- Calibration geometry: "
                f"rank={protocol.calibration_identifiable_rank}, "
                f"effective rank={protocol.calibration_effective_rank:.4f}, "
                f"condition={protocol.calibration_condition_number:.4f}"
            ),
            f"- Calibration parent shares: {shares}",
            f"- Calibration failures: `{list(protocol.calibration_failure_codes)}`",
            "",
            "The calibration remains a formal failure and is not reclassified.",
            "Pro, Beneficiary, Exact Target, GP-C, and Contribution remain blocked.",
            "",
        )
    )


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


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Freeze v25.33 capability-decision stable-support protocol"
    )
    parser.add_argument("--source-stable-protocol", required=True, type=Path)
    parser.add_argument("--calibration-contract", required=True, type=Path)
    parser.add_argument("--calibration-report", required=True, type=Path)
    parser.add_argument("--output-path", required=True, type=Path)
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args(argv)
    protocol = prepare_capability_decision_stable_protocol(
        source_stable_protocol_path=args.source_stable_protocol,
        calibration_contract_path=args.calibration_contract,
        calibration_report_path=args.calibration_report,
        output_path=args.output_path,
        run_id=args.run_id,
    )
    print(
        json.dumps(
            {
                "protocol_id": protocol.protocol_id,
                "primary_response_variable": protocol.primary_response_variable,
                "selected_rollout_count": protocol.selected_rollout_count,
                "next_permitted_stage": protocol.next_permitted_stage,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
