from __future__ import annotations

import argparse
import hashlib
import json
import random
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_mechanism_information_geometry import (  # noqa: E501
    _normalize_demand,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_stable_submechanism_geometry import (  # noqa: E501
    StableIdentifiableSubspacePolicy,
    StableTaskResponse,
    estimate_stable_subspace,
)
from trusted_synthesis.hashing import canonical_hash

STABLE_SUPPORT_PROTOCOL_VERSION = "finance_stable_support_protocol.v1"
STABLE_POWER_OPTION_VERSION = "finance_stable_support_power_option.v1"
POWER_SIMULATION_REPLICATES = 500
REQUIRED_PARENT_COUNT = 4


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class StableSupportPowerOption(FrozenModel):
    task_instances_per_submechanism: int = Field(ge=1)
    realizations_per_task: int = Field(ge=2)
    task_count: int = Field(ge=1)
    rollout_count: int = Field(ge=1)
    simulation_replicates: int = Field(ge=100)
    geometry_pass_probability: float = Field(ge=0, le=1)
    parent_support_pass_probability: float = Field(ge=0, le=1)
    joint_pass_probability: float = Field(ge=0, le=1)
    selection_role: Literal["diagnostic", "selected"]
    schema_version: str = STABLE_POWER_OPTION_VERSION

    @model_validator(mode="after")
    def validate_option(self) -> StableSupportPowerOption:
        if self.task_count != self.task_instances_per_submechanism * 20:
            raise ValueError("stable-support power task denominator is inconsistent")
        if self.rollout_count != self.task_count * self.realizations_per_task:
            raise ValueError("stable-support power rollout denominator is inconsistent")
        return self


class FinanceStableSupportProtocol(FrozenModel):
    protocol_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    experiment_label: Literal["finance_v25_30_stable_support_preregistration"] = (
        "finance_v25_30_stable_support_preregistration"
    )
    source_development_contract_path: str = Field(min_length=1)
    source_development_contract_sha256: str = Field(min_length=64, max_length=64)
    source_development_report_path: str = Field(min_length=1)
    source_development_report_sha256: str = Field(min_length=64, max_length=64)
    source_confirmation_contract_path: str = Field(min_length=1)
    source_confirmation_contract_sha256: str = Field(min_length=64, max_length=64)
    source_confirmation_report_path: str = Field(min_length=1)
    source_confirmation_report_sha256: str = Field(min_length=64, max_length=64)
    source_development_report_id: str = Field(min_length=1)
    source_confirmation_report_id: str = Field(min_length=1)
    historical_development_geometry_passed: Literal[True]
    historical_confirmation_geometry_passed: Literal[False]
    historical_confirmation_failure_codes: tuple[str, ...]
    historical_confirmation_full_condition_number: float = Field(gt=1)
    historical_confirmation_top4_condition_number: float = Field(gt=1)
    historical_candidate_verification_share: float = Field(default=0.0, ge=0, le=0)
    old_result_reclassified: Literal[False] = False
    stable_subspace_policy: StableIdentifiableSubspacePolicy
    power_options: tuple[StableSupportPowerOption, ...] = Field(min_length=4, max_length=4)
    selected_task_instances_per_submechanism: Literal[3] = 3
    selected_realizations_per_task: Literal[8] = 8
    selected_task_count: Literal[60] = 60
    selected_rollout_count: Literal[480] = 480
    development_population_count: Literal[3] = 3
    confirmation_population_count: Literal[3] = 3
    required_disjointness_dimensions: tuple[
        Literal[
            "task",
            "evidence",
            "evidence_version",
            "semantic_signature",
            "submechanism_signature_instance",
        ],
        ...,
    ] = (
        "task",
        "evidence",
        "evidence_version",
        "semantic_signature",
        "submechanism_signature_instance",
    )
    pro_api_call_count: Literal[0] = 0
    beneficiary_screening_authorized: Literal[False] = False
    exact_target_evaluated: Literal[False] = False
    gp_c_evaluated: Literal[False] = False
    production_contribution: float = Field(default=0.0, ge=0, le=0)
    next_permitted_stage: Literal["stable_support_development_population_build"] = (
        "stable_support_development_population_build"
    )
    schema_version: str = STABLE_SUPPORT_PROTOCOL_VERSION

    @model_validator(mode="after")
    def validate_protocol(self) -> FinanceStableSupportProtocol:
        selected = tuple(item for item in self.power_options if item.selection_role == "selected")
        if len(selected) != 1:
            raise ValueError("stable-support protocol must select exactly one power option")
        item = selected[0]
        if (
            item.task_instances_per_submechanism != self.selected_task_instances_per_submechanism
            or item.realizations_per_task != self.selected_realizations_per_task
            or item.task_count != self.selected_task_count
            or item.rollout_count != self.selected_rollout_count
        ):
            raise ValueError("stable-support selected power option is inconsistent")
        if self.protocol_id != stable_support_protocol_id(self):
            raise ValueError("stable-support protocol identity is invalid")
        return self


def stable_support_protocol_id(value: FinanceStableSupportProtocol) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"protocol_id"}),
        prefix="finance_stable_support_protocol:",
    )


def prepare_stable_support_protocol(
    *,
    development_contract_path: Path,
    development_report_path: Path,
    confirmation_contract_path: Path,
    confirmation_report_path: Path,
    output_path: Path,
    run_id: str,
) -> FinanceStableSupportProtocol:
    if output_path.exists():
        raise ValueError("stable-support protocol is immutable")
    paths = tuple(
        item.resolve()
        for item in (
            development_contract_path,
            development_report_path,
            confirmation_contract_path,
            confirmation_report_path,
        )
    )
    development_contract, development_report, confirmation_contract, confirmation_report = (
        _read_json(path) for path in paths
    )
    _verify_historical_lineage(
        development_contract,
        development_report,
        confirmation_contract,
        confirmation_report,
    )
    policy = StableIdentifiableSubspacePolicy()
    power_options = _make_power_options(
        development_contract,
        development_report,
        confirmation_contract,
        confirmation_report,
        policy,
    )
    confirmation_eigenvalues = tuple(
        float(value) for value in confirmation_report["primary_spectrum"]["residual_eigenvalues"]
    )
    top4_condition = confirmation_eigenvalues[0] / confirmation_eigenvalues[3]
    parent_information_share = confirmation_report["primary_spectrum"]["parent_information_share"]
    candidate_verification_share = float(
        parent_information_share["finance.candidate_verification_and_repair"]
    )
    values = {
        "run_id": run_id,
        "source_development_contract_path": str(paths[0]),
        "source_development_contract_sha256": _sha256(paths[0]),
        "source_development_report_path": str(paths[1]),
        "source_development_report_sha256": _sha256(paths[1]),
        "source_confirmation_contract_path": str(paths[2]),
        "source_confirmation_contract_sha256": _sha256(paths[2]),
        "source_confirmation_report_path": str(paths[3]),
        "source_confirmation_report_sha256": _sha256(paths[3]),
        "source_development_report_id": str(development_report["report_id"]),
        "source_confirmation_report_id": str(confirmation_report["report_id"]),
        "historical_development_geometry_passed": bool(
            development_report["primary_information_geometry_ready"]
        ),
        "historical_confirmation_geometry_passed": False,
        "historical_confirmation_failure_codes": tuple(
            str(value) for value in confirmation_report["failure_codes"]
        ),
        "historical_confirmation_full_condition_number": float(
            confirmation_report["primary_spectrum"]["residual_condition_number"]
        ),
        "historical_confirmation_top4_condition_number": top4_condition,
        "historical_candidate_verification_share": candidate_verification_share,
        "stable_subspace_policy": policy,
        "power_options": power_options,
    }
    provisional = FinanceStableSupportProtocol.model_construct(protocol_id="pending", **values)
    protocol = FinanceStableSupportProtocol(
        protocol_id=stable_support_protocol_id(provisional),
        **values,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    _write_json(output_path, protocol.model_dump(mode="json"))
    _write_text(output_path.with_suffix(".md"), _render_protocol(protocol))
    return protocol


def _make_power_options(
    development_contract: Mapping[str, Any],
    development_report: Mapping[str, Any],
    confirmation_contract: Mapping[str, Any],
    confirmation_report: Mapping[str, Any],
    policy: StableIdentifiableSubspacePolicy,
) -> tuple[StableSupportPowerOption, ...]:
    support = _historical_support(
        development_contract,
        development_report,
        confirmation_contract,
        confirmation_report,
    )
    rows = []
    for task_instances, realizations in ((2, 6), (2, 8), (3, 6), (3, 8)):
        rng = random.Random(20260814 + task_instances * 100 + realizations)
        geometry_pass = 0
        parent_pass = 0
        joint_pass = 0
        for replicate in range(POWER_SIMULATION_REPLICATES):
            simulated = _simulate_support(
                support,
                task_instances=task_instances,
                realizations=realizations,
                rng=rng,
                replicate=replicate,
            )
            estimate = estimate_stable_subspace(simulated, policy)
            geometry = (
                estimate.identifiable_rank >= policy.required_rank
                and estimate.claimed_effective_rank >= policy.minimum_effective_rank
                and estimate.claimed_condition_number <= policy.maximum_condition_number
            )
            parent = (
                estimate.minimum_parent_information_share >= policy.minimum_parent_information_share
                and estimate.maximum_parent_information_share
                <= policy.maximum_parent_information_share
                and min(estimate.nonzero_task_count_by_parent.values(), default=0)
                >= policy.minimum_nonzero_tasks_per_parent
            )
            geometry_pass += geometry
            parent_pass += parent
            joint_pass += geometry and parent
        rows.append(
            StableSupportPowerOption(
                task_instances_per_submechanism=task_instances,
                realizations_per_task=realizations,
                task_count=20 * task_instances,
                rollout_count=20 * task_instances * realizations,
                simulation_replicates=POWER_SIMULATION_REPLICATES,
                geometry_pass_probability=geometry_pass / POWER_SIMULATION_REPLICATES,
                parent_support_pass_probability=parent_pass / POWER_SIMULATION_REPLICATES,
                joint_pass_probability=joint_pass / POWER_SIMULATION_REPLICATES,
                selection_role=(
                    "selected" if (task_instances, realizations) == (3, 8) else "diagnostic"
                ),
            )
        )
    return tuple(rows)


def _historical_support(
    development_contract: Mapping[str, Any],
    development_report: Mapping[str, Any],
    confirmation_contract: Mapping[str, Any],
    confirmation_report: Mapping[str, Any],
) -> tuple[dict[str, Any], ...]:
    development_probability = development_report["primary_spectrum"]["task_response_probability"]
    confirmation_probability = confirmation_report["primary_spectrum"]["task_response_probability"]
    development_by_submechanism = {
        submechanism: task_id
        for task_id, submechanism in development_contract["task_submechanism_ids"].items()
    }
    confirmation_by_submechanism = {
        submechanism: task_id
        for task_id, submechanism in confirmation_contract["task_submechanism_ids"].items()
    }
    binding_difficulty = {
        item["task_artifact_id"]: float(item["general_difficulty"])
        for item in development_contract["bindings"]
    }
    rows = []
    for submechanism in sorted(development_by_submechanism):
        development_task = development_by_submechanism[submechanism]
        confirmation_task = confirmation_by_submechanism[submechanism]
        development_successes = float(development_probability[development_task]) * 3
        confirmation_successes = float(confirmation_probability[confirmation_task]) * 5
        historical_successes = development_successes + confirmation_successes
        rows.append(
            {
                "submechanism_id": submechanism,
                "parent_mechanism_id": development_contract["task_parent_mechanism_ids"][
                    development_task
                ],
                "historical_successes": historical_successes,
                "historical_trials": 8.0,
                "general_difficulty": binding_difficulty[development_task],
                "demand": _normalize_demand(
                    development_contract["task_raw_capability_demands"][development_task]
                ),
            }
        )
    if len(rows) != 20:
        raise ValueError("historical power support lacks 20 submechanisms")
    return tuple(rows)


def _simulate_support(
    support: Sequence[Mapping[str, Any]],
    *,
    task_instances: int,
    realizations: int,
    rng: random.Random,
    replicate: int,
) -> tuple[StableTaskResponse, ...]:
    rows = []
    for item in support:
        for instance in range(task_instances):
            successes = float(item["historical_successes"])
            trials = float(item["historical_trials"])
            probability = rng.betavariate(
                successes + 0.5,
                trials - successes + 0.5,
            )
            outcomes = tuple(int(rng.random() < probability) for _ in range(realizations))
            task_id = f"power:{replicate}:{item['submechanism_id']}:{instance}"
            rows.append(
                StableTaskResponse(
                    task_id=task_id,
                    submechanism_id=str(item["submechanism_id"]),
                    parent_mechanism_id=str(item["parent_mechanism_id"]),
                    task_instance_id=task_id,
                    general_difficulty=float(item["general_difficulty"]),
                    demand=tuple(float(value) for value in item["demand"]),
                    realizations=outcomes,
                )
            )
    return tuple(rows)


def _verify_historical_lineage(
    development_contract: Mapping[str, Any],
    development_report: Mapping[str, Any],
    confirmation_contract: Mapping[str, Any],
    confirmation_report: Mapping[str, Any],
) -> None:
    if development_report.get("contract_id") != development_contract.get("contract_id"):
        raise ValueError("historical Development report has invalid lineage")
    if development_report.get("primary_information_geometry_ready") is not True:
        raise ValueError("historical Development did not pass its frozen geometry contract")
    if confirmation_report.get("contract_id") != confirmation_contract.get("contract_id"):
        raise ValueError("historical Confirmation report has invalid lineage")
    if confirmation_contract.get("source_development_contract_id") != development_contract.get(
        "contract_id"
    ):
        raise ValueError("historical Confirmation does not descend from Development")
    if confirmation_report.get("primary_information_geometry_confirmed") is not False:
        raise ValueError("historical Confirmation is not the frozen failed result")
    if confirmation_report.get("pro_sparse_anchor_authorized") is not False:
        raise ValueError("historical failed Confirmation unexpectedly authorized Pro")
    failures = set(confirmation_report.get("failure_codes", ()))
    if "residual_condition_number" not in failures:
        raise ValueError("historical Confirmation lacks the diagnosed condition failure")
    parent_share = confirmation_report.get("primary_spectrum", {}).get(
        "parent_information_share", {}
    )
    if parent_share.get("finance.candidate_verification_and_repair") != 0.0:
        raise ValueError("historical Confirmation lacks the diagnosed zero-information parent")


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON object required: {path}")
    return value


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_json(path: Path, value: object) -> None:
    if path.exists():
        raise ValueError(f"immutable output exists: {path}")
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_text(path: Path, value: str) -> None:
    if path.exists():
        raise ValueError(f"immutable output exists: {path}")
    path.write_text(value, encoding="utf-8")


def _render_protocol(protocol: FinanceStableSupportProtocol) -> str:
    options = "\n".join(
        (
            f"- {item.task_instances_per_submechanism} instances x "
            f"{item.realizations_per_task} realizations: "
            f"geometry={item.geometry_pass_probability:.2%}, "
            f"parent={item.parent_support_pass_probability:.2%}, "
            f"joint={item.joint_pass_probability:.2%}, role={item.selection_role}"
        )
        for item in protocol.power_options
    )
    return "\n".join(
        (
            "# Finance v25.30 Stable Support Preregistration",
            "",
            "## Frozen Decision",
            "",
            "- v25.29 remains a formal failure and is not reclassified.",
            (
                "- Historical full condition: "
                f"**{protocol.historical_confirmation_full_condition_number:.4f}**"
            ),
            (
                "- Descriptive historical Top-4 condition: "
                f"**{protocol.historical_confirmation_top4_condition_number:.4f}**"
            ),
            "- Required stable rank: **4**",
            "- Candidate Verification historical information share: **0%**",
            "- Pro / Beneficiary / Exact Target / GP-C: **blocked**",
            "",
            "## Prospective Power Design",
            "",
            options,
            "",
            (
                "The selected 3 x 8 design maximizes independent task-instance support within "
                "the preregistered options. Historical simulations are design diagnostics only; "
                "fresh repaired Runtime outcomes determine admission."
            ),
            "",
        )
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Prepare the v25.30 stable-support protocol")
    parser.add_argument("--development-contract", required=True, type=Path)
    parser.add_argument("--development-report", required=True, type=Path)
    parser.add_argument("--confirmation-contract", required=True, type=Path)
    parser.add_argument("--confirmation-report", required=True, type=Path)
    parser.add_argument("--output-path", required=True, type=Path)
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args(argv)
    protocol = prepare_stable_support_protocol(
        development_contract_path=args.development_contract,
        development_report_path=args.development_report,
        confirmation_contract_path=args.confirmation_contract,
        confirmation_report_path=args.confirmation_report,
        output_path=args.output_path,
        run_id=args.run_id,
    )
    print(
        json.dumps(
            {
                "protocol_id": protocol.protocol_id,
                "selected_task_count": protocol.selected_task_count,
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
