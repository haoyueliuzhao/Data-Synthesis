from __future__ import annotations

import argparse
import hashlib
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from trusted_synthesis.core.vtdo import ConditionalTrajectoryDistribution
from trusted_synthesis.experiments.vtdo_experiment.multistate import (
    FinanceTaskStateArtifact,
    load_finance_multi_state_artifacts,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_initial_distribution import (
    FinanceInitialDistributionReport,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_state_realizations import (
    FinanceStateRealizationReport,
)
from trusted_synthesis.experiments.vtdo_experiment.schema import GradientStateRealization
from trusted_synthesis.hashing import canonical_hash

TARGET_POPULATION_VERSION = "finance_target_identifiability_population.v20"
TARGET_POPULATION_HASH_PREFIX = "finance_target_identifiability_population:"
IDENTIFIABILITY_CONTRACT_VERSION = "finance_target_identifiability_contract.v20"
IDENTIFIABILITY_CONTRACT_HASH_PREFIX = "finance_target_identifiability_contract:"
TARGET_IDENTIFIABILITY_ROLE = "target_identifiability"
REQUIRED_TASK_TYPES = (
    "comparison",
    "derived_growth_comparison",
    "registered_ratio",
    "temporal_absolute_change",
    "temporal_average",
    "temporal_growth",
)
STEP_RATIO_LADDER = (0.01, 0.005, 0.0025)
BLOCK_SIZES = (2, 4, 7)
OBJECTIVE_RECORDS_PER_ROLE = 16
OBJECTIVE_MICRO_SPLIT_COUNT = 4
OBJECTIVE_RECORDS_PER_MICRO_SPLIT = 4
STUDY_THRESHOLDS = {
    "maximum_parameter_step_ratio_relative_error": 5e-5,
    "minimum_anchor_identifiable_rate": 1.0,
    "minimum_micro_split_sign_consistency": 0.75,
    "maximum_micro_split_slope_cv": 0.5,
    "maximum_p95_nonlinearity_ratio": 0.25,
    "maximum_block_reconstruction_relative_error": 0.15,
    "minimum_block_direction_agreement": 0.8,
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"v20 artifact is not a JSON object:{path}")
    return value


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(dict(value), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _write_jsonl(path: Path, values: tuple[dict[str, Any], ...]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        "".join(json.dumps(value, ensure_ascii=False, sort_keys=True) + "\n" for value in values),
        encoding="utf-8",
    )
    temporary.replace(path)


def _replay_hash(value: Mapping[str, Any], *, field: str, prefix: str) -> str:
    payload = dict(value)
    observed = payload.pop(field, None)
    expected = canonical_hash(payload, prefix=prefix)
    if observed != expected:
        raise ValueError(f"v20 identity replay failed:{field}")
    return str(observed)


def _artifact_evidence_versions(artifact: FinanceTaskStateArtifact) -> set[str]:
    return {evidence.evidence_version_id for evidence in artifact.omega.public_corpus.evidence}


def select_target_population(*, source_report_path: Path, output_dir: Path) -> dict[str, Any]:
    source_report = _read_json(source_report_path)
    if source_report.get("status") != "passed":
        raise ValueError("v20 target source population did not pass")
    unused_ids = {str(value) for value in source_report.get("unused_artifact_ids", ())}
    if not unused_ids:
        raise ValueError("v20 target source has no predecessor-unused reserve")
    used_ids = {
        str(value)
        for partition in source_report.get("partitions", {}).values()
        for value in partition.get("artifact_ids", ())
    }
    if unused_ids & used_ids:
        raise ValueError("v20 target reserve overlaps a predecessor partition")
    source_paths = (
        Path(str(source_report["source_artifacts_path"])).resolve(),
        Path(str(source_report["supplemental_source_artifacts_path"])).resolve(),
    )
    candidates = {
        artifact.artifact_id: artifact
        for path in source_paths
        for artifact in load_finance_multi_state_artifacts(path)
        if artifact.artifact_id in unused_ids
    }
    if set(candidates) != unused_ids:
        raise ValueError("v20 target reserve cannot be replayed from source artifacts")
    selected: list[FinanceTaskStateArtifact] = []
    for task_type in REQUIRED_TASK_TYPES:
        rows = sorted(
            (
                artifact
                for artifact in candidates.values()
                if artifact.omega.task.public.task_type == task_type
            ),
            key=lambda artifact: artifact.artifact_id,
        )
        if not rows:
            raise ValueError(f"v20 target reserve lacks task type:{task_type}")
        selected.append(rows[0])
    selected_ids = {artifact.artifact_id for artifact in selected}
    if selected_ids & used_ids or not selected_ids <= unused_ids:
        raise ValueError("v20 selected target was previously observed")
    task_ids = [artifact.omega.task.task_id for artifact in selected]
    if len(set(task_ids)) != len(REQUIRED_TASK_TYPES):
        raise ValueError("v20 selected target tasks are not unique")
    evidence_sets = [_artifact_evidence_versions(artifact) for artifact in selected]
    if any(
        left & right
        for index, left in enumerate(evidence_sets)
        for right in evidence_sets[index + 1 :]
    ):
        raise ValueError("v20 selected target tasks share public Evidence")
    output_dir.mkdir(parents=True, exist_ok=True)
    artifact_path = output_dir / "target_task_states.jsonl"
    _write_jsonl(
        artifact_path,
        tuple(artifact.model_dump(mode="json") for artifact in selected),
    )
    report: dict[str, Any] = {
        "experiment_version": TARGET_POPULATION_VERSION,
        "source_report_path": str(source_report_path),
        "source_report_sha256": _sha256(source_report_path),
        "source_report_hash": source_report["report_hash"],
        "source_artifact_paths": [str(path) for path in source_paths],
        "source_artifact_sha256s": [_sha256(path) for path in source_paths],
        "selection_policy": "lexicographic_first_predecessor_unused_per_required_task_type",
        "required_task_types": list(REQUIRED_TASK_TYPES),
        "selected_artifact_ids": [artifact.artifact_id for artifact in selected],
        "selected_task_ids": task_ids,
        "selected_task_type_by_id": {
            artifact.omega.task.task_id: artifact.omega.task.public.task_type
            for artifact in selected
        },
        "task_count": len(selected),
        "state_count": sum(len(artifact.accepted_states) for artifact in selected),
        "evidence_version_count": len(set().union(*evidence_sets)),
        "target_artifacts_path": str(artifact_path),
        "target_artifacts_sha256": _sha256(artifact_path),
        "predecessor_partition_overlap_count": len(selected_ids & used_ids),
        "outcomes_observed_before_selection": False,
        "authorization_eligible": False,
        "claim_boundary": (
            "This population is selected only for a target-identifiability development study. "
            "It cannot authorize GP-C, Contribution, a VTDO update, or production."
        ),
    }
    report["report_hash"] = canonical_hash(report, prefix=TARGET_POPULATION_HASH_PREFIX)
    _write_json(output_dir / "target_population_report.json", report)
    return report


def verify_target_population(report: Mapping[str, Any]) -> dict[str, Any]:
    frozen = dict(report)
    _replay_hash(frozen, field="report_hash", prefix=TARGET_POPULATION_HASH_PREFIX)
    if frozen.get("experiment_version") != TARGET_POPULATION_VERSION:
        raise ValueError("v20 target population version differs")
    if frozen.get("required_task_types") != list(REQUIRED_TASK_TYPES):
        raise ValueError("v20 target task-type contract differs")
    if frozen.get("task_count") != 6 or frozen.get("state_count") != 20:
        raise ValueError("v20 target support differs")
    if frozen.get("predecessor_partition_overlap_count") != 0:
        raise ValueError("v20 target population was previously observed")
    if frozen.get("outcomes_observed_before_selection") is not False:
        raise ValueError("v20 target selection used outcomes")
    path = Path(str(frozen["target_artifacts_path"])).resolve()
    if not path.is_file() or _sha256(path) != frozen.get("target_artifacts_sha256"):
        raise ValueError("v20 target artifacts changed")
    return frozen


def _load_distributions(path: Path) -> tuple[ConditionalTrajectoryDistribution, ...]:
    values = tuple(
        ConditionalTrajectoryDistribution.model_validate_json(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    )
    if len({value.task_condition_id for value in values}) != len(values):
        raise ValueError("v20 distributions are empty or duplicated")
    return values


def _load_realizations(path: Path) -> tuple[GradientStateRealization, ...]:
    return tuple(
        GradientStateRealization.model_validate_json(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    )


def verify_identifiability_contract(contract: Mapping[str, Any]) -> dict[str, Any]:
    frozen = dict(contract)
    _replay_hash(frozen, field="contract_hash", prefix=IDENTIFIABILITY_CONTRACT_HASH_PREFIX)
    if frozen.get("contract_version") != IDENTIFIABILITY_CONTRACT_VERSION:
        raise ValueError("v20 identifiability contract version differs")
    if frozen.get("run_role") != TARGET_IDENTIFIABILITY_ROLE:
        raise ValueError("v20 identifiability run role differs")
    if frozen.get("task_count") != 6 or frozen.get("state_count") != 20:
        raise ValueError("v20 identifiability target support differs")
    if frozen.get("state_realization_count") != 60:
        raise ValueError("v20 identifiability realization support differs")
    if frozen.get("step_ratio_ladder") != list(STEP_RATIO_LADDER):
        raise ValueError("v20 parameter-step ladder differs")
    if frozen.get("block_sizes") != list(BLOCK_SIZES):
        raise ValueError("v20 block-size comparison differs")
    if frozen.get("objective_micro_split_count") != OBJECTIVE_MICRO_SPLIT_COUNT:
        raise ValueError("v20 Objective micro-split contract differs")
    if frozen.get("study_thresholds") != STUDY_THRESHOLDS:
        raise ValueError("v20 identifiability thresholds differ")
    support = frozen.get("source_support")
    partitions = support.get("objective_partition_ids") if isinstance(support, dict) else None
    if not isinstance(partitions, dict) or set(partitions) != {
        "estimation",
        "validation",
        "authorization",
    }:
        raise ValueError("v20 Objective partitions differ")
    for role in ("estimation", "validation", "authorization"):
        values = partitions[role]
        if not isinstance(values, list) or len(values) != OBJECTIVE_RECORDS_PER_ROLE:
            raise ValueError("v20 Objective partition size differs")
    if frozen.get("allowed_objective_roles") != ["estimation", "validation"]:
        raise ValueError("v20 Objective access differs")
    if frozen.get("authorization_objective_access") != "forbidden":
        raise ValueError("v20 Authorization Objective must remain sealed")
    if frozen.get("gp_c_execution_allowed") is not False:
        raise ValueError("v20 identifiability study cannot execute GP-C")
    if frozen.get("contribution_approximation_authorized") is not False:
        raise ValueError("v20 identifiability study cannot authorize Contribution")
    if frozen.get("production_authorization_eligible") is not False:
        raise ValueError("v20 identifiability study cannot be production eligible")
    return frozen


def issue_identifiability_contract(
    *,
    source_v19_contract_path: Path,
    target_population_report_path: Path,
    initial_distribution_dir: Path,
    state_realization_dir: Path,
    support_dir: Path,
    output_path: Path,
) -> dict[str, Any]:
    from trusted_synthesis.experiments.vtdo_experiment import (
        phase1_contribution_numeric_execution as numeric_execution,
    )

    source_v19 = numeric_execution.verify_execution_contract(_read_json(source_v19_contract_path))
    target_report = verify_target_population(_read_json(target_population_report_path))
    target_path = Path(str(target_report["target_artifacts_path"])).resolve()
    artifacts = load_finance_multi_state_artifacts(target_path)
    task_ids = {artifact.omega.task.task_id for artifact in artifacts}
    state_ids = {
        state.assignment.state.state_id
        for artifact in artifacts
        for state in artifact.accepted_states
    }
    initial_report_path = initial_distribution_dir / "finance_initial_distribution_report.json"
    distributions_path = initial_distribution_dir / "initial_distributions.jsonl"
    initial_report = FinanceInitialDistributionReport.model_validate_json(
        initial_report_path.read_text(encoding="utf-8")
    )
    distributions = _load_distributions(distributions_path)
    if (
        initial_report.status != "passed"
        or {row.task_condition_id for row in distributions} != task_ids
    ):
        raise ValueError("v20 initial distribution does not cover the target")
    realization_report_path = state_realization_dir / "finance_state_realization_report.json"
    realizations_path = state_realization_dir / "gradient_state_realizations.jsonl"
    realization_report = FinanceStateRealizationReport.model_validate_json(
        realization_report_path.read_text(encoding="utf-8")
    )
    realizations = _load_realizations(realizations_path)
    if realization_report.status != "passed" or len(realizations) != 60:
        raise ValueError("v20 state realization population is incomplete")
    if {row.task_condition_id for row in realizations} != task_ids:
        raise ValueError("v20 state realizations cross target tasks")
    if {row.state_id for row in realizations} != state_ids:
        raise ValueError("v20 state realizations do not cover target states")
    realization_counts: dict[str, int] = {}
    for row in realizations:
        realization_counts[row.state_id] = realization_counts.get(row.state_id, 0) + 1
    if set(realization_counts.values()) != {3}:
        raise ValueError("v20 requires exactly three realizations per state")

    support_plan_path = support_dir / "plan.json"
    support_report_path = support_dir / "beneficiary_evaluation_report.json"
    support_plan = _read_json(support_plan_path)
    support_report = _read_json(support_report_path)
    if support_plan.get("run_role") != TARGET_IDENTIFIABILITY_ROLE:
        raise ValueError("v20 support has another run role")
    if support_report.get("status") != "passed" or support_report.get(
        "plan_hash"
    ) != support_plan.get("plan_hash"):
        raise ValueError("v20 Objective Support did not pass")
    if support_report.get("authorization_objective_access") != "forbidden":
        raise ValueError("v20 support opened Authorization Objective")
    if set(support_report.get("objective_partition_results", {})) != {
        "estimation",
        "validation",
    }:
        raise ValueError("v20 support evaluated an undeclared Objective role")
    partitions = support_plan.get("objective_partitions")
    if not isinstance(partitions, dict):
        raise ValueError("v20 support lacks Objective partitions")
    partition_ids = {
        role: [str(value) for value in partitions[role]["record_ids"]]
        for role in ("estimation", "validation", "authorization")
    }
    if any(len(values) != OBJECTIVE_RECORDS_PER_ROLE for values in partition_ids.values()):
        raise ValueError("v20 support is not 16+16+16")
    if set(support_plan["gradient_target_contract"]["task_ids"]) != task_ids:
        raise ValueError("v20 support targets another task population")

    contract: dict[str, Any] = {
        "contract_version": IDENTIFIABILITY_CONTRACT_VERSION,
        "run_role": TARGET_IDENTIFIABILITY_ROLE,
        "source_v19_contract": {
            "path": str(source_v19_contract_path),
            "sha256": _sha256(source_v19_contract_path),
            "contract_hash": source_v19["contract_hash"],
        },
        "source_support": {
            "plan_path": str(support_plan_path),
            "plan_sha256": _sha256(support_plan_path),
            "plan_hash": support_plan["plan_hash"],
            "report_path": str(support_report_path),
            "report_sha256": _sha256(support_report_path),
            "report_hash": support_report["report_hash"],
            "source_numeric_contract_hash": support_plan["numeric_contract_hash"],
            "objective_partition_ids": partition_ids,
        },
        "frozen_inputs": {
            "target_artifacts": {"path": str(target_path), "sha256": _sha256(target_path)},
            "target_population_report": {
                "path": str(target_population_report_path),
                "sha256": _sha256(target_population_report_path),
                "report_hash": target_report["report_hash"],
            },
            "distributions": {
                "path": str(distributions_path),
                "sha256": _sha256(distributions_path),
                "report_path": str(initial_report_path),
                "report_sha256": _sha256(initial_report_path),
            },
            "state_realizations": {
                "path": str(realizations_path),
                "sha256": _sha256(realizations_path),
                "report_path": str(realization_report_path),
                "report_sha256": _sha256(realization_report_path),
            },
        },
        "selected_profile": source_v19["selected_profile"],
        "profile_algorithm_contract": source_v19["profile_algorithm_contract"],
        "numeric_thresholds": source_v19["numeric_thresholds"],
        "task_set_id": support_plan["gradient_target_contract"]["task_set_id"],
        "task_ids": sorted(task_ids),
        "task_count": len(task_ids),
        "state_count": len(state_ids),
        "state_realization_count": len(realizations),
        "required_task_types": list(REQUIRED_TASK_TYPES),
        "step_ratio_ladder": list(STEP_RATIO_LADDER),
        "block_sizes": list(BLOCK_SIZES),
        "direct_coordinate_policy": "one_anchor_per_task_type_plus_one_extra_largest_support",
        "objective_micro_split_count": OBJECTIVE_MICRO_SPLIT_COUNT,
        "objective_records_per_micro_split": OBJECTIVE_RECORDS_PER_MICRO_SPLIT,
        "local_slope_model": "odd_cubic_delta_J_equals_a1_h_plus_a3_h_cubed",
        "study_thresholds": STUDY_THRESHOLDS,
        "allowed_objective_roles": ["estimation", "validation"],
        "authorization_objective_access": "forbidden",
        "gp_c_execution_allowed": False,
        "contribution_approximation_authorized": False,
        "production_authorization_eligible": False,
        "success_transition": "freeze_fresh_proxy_comparison_study",
        "failure_transition": "retain_contribution_zero_and_redesign_target_measurement",
        "claim_boundary": (
            "This study tests first-order finite-target observability only. It cannot evaluate "
            "GP-C, open Authorization, authorize Contribution, or update VTDO."
        ),
    }
    contract["contract_hash"] = canonical_hash(
        contract,
        prefix=IDENTIFIABILITY_CONTRACT_HASH_PREFIX,
    )
    verify_identifiability_contract(contract)
    if output_path.exists():
        raise ValueError("v20 identifiability contract is immutable and already exists")
    _write_json(output_path, contract)
    return contract


def _select(args: argparse.Namespace) -> None:
    report = select_target_population(
        source_report_path=Path(args.source_report).resolve(),
        output_dir=Path(args.output_dir).resolve(),
    )
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))


def _issue(args: argparse.Namespace) -> None:
    contract = issue_identifiability_contract(
        source_v19_contract_path=Path(args.source_v19_contract).resolve(),
        target_population_report_path=Path(args.target_population_report).resolve(),
        initial_distribution_dir=Path(args.initial_distribution_dir).resolve(),
        state_realization_dir=Path(args.state_realization_dir).resolve(),
        support_dir=Path(args.support_dir).resolve(),
        output_path=Path(args.output_path).resolve(),
    )
    print(json.dumps(contract, ensure_ascii=False, indent=2, sort_keys=True))


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Freeze the v20 target-identifiability contract")
    subparsers = parser.add_subparsers(dest="command", required=True)
    select = subparsers.add_parser("select-target-population")
    select.add_argument("--source-report", required=True)
    select.add_argument("--output-dir", required=True)
    select.set_defaults(handler=_select)
    issue = subparsers.add_parser("issue-contract")
    issue.add_argument("--source-v19-contract", required=True)
    issue.add_argument("--target-population-report", required=True)
    issue.add_argument("--initial-distribution-dir", required=True)
    issue.add_argument("--state-realization-dir", required=True)
    issue.add_argument("--support-dir", required=True)
    issue.add_argument("--output-path", required=True)
    issue.set_defaults(handler=_issue)
    return parser


def main() -> None:
    args = _parser().parse_args()
    args.handler(args)


if __name__ == "__main__":
    main()
