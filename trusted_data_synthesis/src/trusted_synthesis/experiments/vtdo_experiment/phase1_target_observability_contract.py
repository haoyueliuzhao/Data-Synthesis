from __future__ import annotations

import argparse
import hashlib
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from trusted_synthesis.core.vtdo import ConditionalTrajectoryDistribution
from trusted_synthesis.experiments.vtdo_experiment.multistate import (
    FinanceTaskStateArtifact,
    load_finance_multi_state_artifacts,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_agent_population import (
    FinanceAgentPopulationReport,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_initial_distribution import (
    FinanceInitialDistributionReport,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_state_realizations import (
    FinanceStateRealizationReport,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_target_observability import (
    DIRECT_COORDINATE_COUNT,
    MINIMUM_PRACTICAL_EFFECT,
    OBJECTIVE_MICRO_SPLIT_COUNT,
    OBJECTIVE_RECORDS_PER_MICRO_SPLIT,
    OBJECTIVE_RECORDS_PER_ROLE,
    PRIMARY_STEP_RATIO,
    STEP_RATIO_LADDER,
    verify_preregistration,
)
from trusted_synthesis.experiments.vtdo_experiment.schema import GradientStateRealization
from trusted_synthesis.hashing import canonical_hash

TARGET_POPULATION_VERSION = "finance_target_observability_population.v21"
TARGET_POPULATION_HASH_PREFIX = "finance_target_observability_population:"
OBSERVABILITY_CONTRACT_VERSION = "finance_target_observability_contract.v21"
OBSERVABILITY_CONTRACT_HASH_PREFIX = "finance_target_observability_contract:"
TARGET_OBSERVABILITY_ROLE = "target_observability"

REQUIRED_TASK_TYPES = (
    "comparison",
    "derived_growth_comparison",
    "registered_ratio",
    "temporal_absolute_change",
    "temporal_average",
    "temporal_growth",
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"v21 target artifact is not a JSON object:{path}")
    return value


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(dict(value), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _write_jsonl(path: Path, values: Sequence[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        "".join(
            json.dumps(dict(value), ensure_ascii=False, sort_keys=True) + "\n" for value in values
        ),
        encoding="utf-8",
    )
    temporary.replace(path)


def _replay_hash(value: Mapping[str, Any], *, field: str, prefix: str) -> str:
    payload = dict(value)
    observed = payload.pop(field, None)
    expected = canonical_hash(payload, prefix=prefix)
    if observed != expected:
        raise ValueError(f"v21 target identity replay failed:{field}")
    return str(observed)


def _artifact_evidence_versions(artifact: FinanceTaskStateArtifact) -> frozenset[str]:
    values = frozenset(
        evidence.evidence_version_id for evidence in artifact.omega.public_corpus.evidence
    )
    if not values:
        raise ValueError(f"v21 target task has no public Evidence:{artifact.artifact_id}")
    return values


def _select_target_artifacts(
    artifacts: Sequence[FinanceTaskStateArtifact],
) -> tuple[FinanceTaskStateArtifact, ...]:
    selected: list[FinanceTaskStateArtifact] = []
    for task_type in REQUIRED_TASK_TYPES:
        rows = sorted(
            (
                artifact
                for artifact in artifacts
                if artifact.omega.task.public.task_type == task_type
            ),
            key=lambda artifact: artifact.artifact_id,
        )
        if not rows:
            raise ValueError(f"v21 fresh population lacks task type:{task_type}")
        selected.append(rows[0])

    artifact_ids = [artifact.artifact_id for artifact in selected]
    task_ids = [artifact.omega.task.task_id for artifact in selected]
    if len(set(artifact_ids)) != len(REQUIRED_TASK_TYPES):
        raise ValueError("v21 target artifacts are duplicated")
    if len(set(task_ids)) != len(REQUIRED_TASK_TYPES):
        raise ValueError("v21 target tasks are duplicated")
    evidence_sets = [_artifact_evidence_versions(artifact) for artifact in selected]
    if any(
        left & right
        for index, left in enumerate(evidence_sets)
        for right in evidence_sets[index + 1 :]
    ):
        raise ValueError("v21 target tasks share public Evidence")
    return tuple(selected)


def select_target_population(
    *,
    source_report_path: Path,
    source_artifacts_path: Path,
    preregistration_path: Path,
    output_dir: Path,
) -> dict[str, Any]:
    report_path = output_dir / "target_population_report.json"
    target_path = output_dir / "target_task_states.jsonl"
    if report_path.exists() or target_path.exists():
        raise ValueError("v21 target population is immutable and already exists")

    source_report = FinanceAgentPopulationReport.model_validate(_read_json(source_report_path))
    if source_report.status != "passed":
        raise ValueError("v21 source population did not pass")
    if _sha256(source_artifacts_path) != source_report.artifact_sha256:
        raise ValueError("v21 source population artifact changed")
    preregistration = verify_preregistration(_read_json(preregistration_path))

    source_artifacts = load_finance_multi_state_artifacts(source_artifacts_path)
    if len(source_artifacts) != source_report.accepted_task_count:
        raise ValueError("v21 source population record count differs")
    if len({artifact.artifact_id for artifact in source_artifacts}) != len(source_artifacts):
        raise ValueError("v21 source population contains duplicate artifacts")
    observed_type_counts: dict[str, int] = {}
    for artifact in source_artifacts:
        task_type = artifact.omega.task.public.task_type
        observed_type_counts[task_type] = observed_type_counts.get(task_type, 0) + 1
    if dict(sorted(observed_type_counts.items())) != source_report.task_type_counts:
        raise ValueError("v21 source population task-type accounting differs")

    selected = _select_target_artifacts(source_artifacts)
    evidence_sets = [_artifact_evidence_versions(artifact) for artifact in selected]
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_jsonl(
        target_path,
        tuple(artifact.model_dump(mode="json") for artifact in selected),
    )
    report: dict[str, Any] = {
        "experiment_version": TARGET_POPULATION_VERSION,
        "preregistration": {
            "path": str(preregistration_path.resolve()),
            "sha256": _sha256(preregistration_path),
            "preregistration_hash": preregistration["preregistration_hash"],
        },
        "source_population_report": {
            "path": str(source_report_path.resolve()),
            "sha256": _sha256(source_report_path),
            "report_id": source_report.report_id,
        },
        "source_population_artifacts": {
            "path": str(source_artifacts_path.resolve()),
            "sha256": _sha256(source_artifacts_path),
            "task_count": len(source_artifacts),
        },
        "selection_policy": "lexicographic_first_per_required_task_type",
        "required_task_types": list(REQUIRED_TASK_TYPES),
        "selected_artifact_ids": [artifact.artifact_id for artifact in selected],
        "selected_task_ids": [artifact.omega.task.task_id for artifact in selected],
        "selected_task_type_by_id": {
            artifact.omega.task.task_id: artifact.omega.task.public.task_type
            for artifact in selected
        },
        "task_count": len(selected),
        "state_count": sum(len(artifact.accepted_states) for artifact in selected),
        "evidence_version_count": len(set().union(*evidence_sets)),
        "target_artifacts_path": str(target_path.resolve()),
        "target_artifacts_sha256": _sha256(target_path),
        "outcomes_observed_before_selection": False,
        "authorization_objective_access": "forbidden",
        "gp_c_execution_allowed": False,
        "contribution_approximation_authorized": False,
        "production_authorization_eligible": False,
        "claim_boundary": (
            "This fresh population is selected before target outcomes for a Direct Coordinate "
            "observability study. It cannot evaluate GP-C, open Authorization, authorize "
            "Contribution, or update VTDO."
        ),
    }
    report["report_hash"] = canonical_hash(report, prefix=TARGET_POPULATION_HASH_PREFIX)
    verify_target_population(report)
    _write_json(report_path, report)
    return report


def verify_target_population(report: Mapping[str, Any]) -> dict[str, Any]:
    frozen = dict(report)
    _replay_hash(frozen, field="report_hash", prefix=TARGET_POPULATION_HASH_PREFIX)
    if frozen.get("experiment_version") != TARGET_POPULATION_VERSION:
        raise ValueError("v21 target population version differs")
    if frozen.get("required_task_types") != list(REQUIRED_TASK_TYPES):
        raise ValueError("v21 target task-type contract differs")
    if frozen.get("task_count") != len(REQUIRED_TASK_TYPES):
        raise ValueError("v21 target task count differs")
    if int(frozen.get("state_count", 0)) < len(REQUIRED_TASK_TYPES) * 3:
        raise ValueError("v21 target state support is insufficient")
    if frozen.get("outcomes_observed_before_selection") is not False:
        raise ValueError("v21 target selection used outcomes")
    for field, expected in {
        "authorization_objective_access": "forbidden",
        "gp_c_execution_allowed": False,
        "contribution_approximation_authorized": False,
        "production_authorization_eligible": False,
    }.items():
        if frozen.get(field) != expected:
            raise ValueError(f"v21 target access boundary differs:{field}")

    preregistration = frozen.get("preregistration")
    source_report_info = frozen.get("source_population_report")
    source_artifacts_info = frozen.get("source_population_artifacts")
    if not all(
        isinstance(value, dict)
        for value in (preregistration, source_report_info, source_artifacts_info)
    ):
        raise ValueError("v21 target source identity is incomplete")
    assert isinstance(preregistration, dict)
    assert isinstance(source_report_info, dict)
    assert isinstance(source_artifacts_info, dict)

    preregistration_path = Path(str(preregistration["path"])).resolve()
    if not preregistration_path.is_file() or _sha256(preregistration_path) != preregistration.get(
        "sha256"
    ):
        raise ValueError("v21 preregistration changed")
    verified_preregistration = verify_preregistration(_read_json(preregistration_path))
    if verified_preregistration["preregistration_hash"] != preregistration.get(
        "preregistration_hash"
    ):
        raise ValueError("v21 preregistration identity differs")

    source_report_path = Path(str(source_report_info["path"])).resolve()
    source_artifacts_path = Path(str(source_artifacts_info["path"])).resolve()
    if not source_report_path.is_file() or _sha256(source_report_path) != source_report_info.get(
        "sha256"
    ):
        raise ValueError("v21 source population report changed")
    source_report = FinanceAgentPopulationReport.model_validate(_read_json(source_report_path))
    if source_report.report_id != source_report_info.get("report_id"):
        raise ValueError("v21 source population report identity differs")
    if not source_artifacts_path.is_file() or _sha256(
        source_artifacts_path
    ) != source_artifacts_info.get("sha256"):
        raise ValueError("v21 source population artifacts changed")
    if source_report.artifact_sha256 != source_artifacts_info.get("sha256"):
        raise ValueError("v21 source population lineage differs")

    target_path = Path(str(frozen["target_artifacts_path"])).resolve()
    if not target_path.is_file() or _sha256(target_path) != frozen.get("target_artifacts_sha256"):
        raise ValueError("v21 target artifacts changed")
    target_artifacts = load_finance_multi_state_artifacts(target_path)
    if len(target_artifacts) != len(REQUIRED_TASK_TYPES):
        raise ValueError("v21 target artifact count differs")
    source_by_id = {
        artifact.artifact_id: artifact
        for artifact in load_finance_multi_state_artifacts(source_artifacts_path)
    }
    selected_ids = [str(value) for value in frozen.get("selected_artifact_ids", ())]
    if [artifact.artifact_id for artifact in target_artifacts] != selected_ids:
        raise ValueError("v21 target artifact order or identity differs")
    if any(
        artifact.artifact_id not in source_by_id or artifact != source_by_id[artifact.artifact_id]
        for artifact in target_artifacts
    ):
        raise ValueError("v21 target artifacts do not replay from the fresh population")
    task_ids = [artifact.omega.task.task_id for artifact in target_artifacts]
    if task_ids != [str(value) for value in frozen.get("selected_task_ids", ())]:
        raise ValueError("v21 target task identity differs")
    task_type_by_id = {
        artifact.omega.task.task_id: artifact.omega.task.public.task_type
        for artifact in target_artifacts
    }
    if task_type_by_id != frozen.get("selected_task_type_by_id"):
        raise ValueError("v21 target task-type identity differs")
    if set(task_type_by_id.values()) != set(REQUIRED_TASK_TYPES):
        raise ValueError("v21 target task-type coverage differs")
    evidence_sets = [_artifact_evidence_versions(artifact) for artifact in target_artifacts]
    if any(
        left & right
        for index, left in enumerate(evidence_sets)
        for right in evidence_sets[index + 1 :]
    ):
        raise ValueError("v21 target tasks share public Evidence")
    if len(set().union(*evidence_sets)) != frozen.get("evidence_version_count"):
        raise ValueError("v21 target Evidence accounting differs")
    if sum(len(artifact.accepted_states) for artifact in target_artifacts) != frozen.get(
        "state_count"
    ):
        raise ValueError("v21 target state accounting differs")
    return frozen


def _load_distributions(path: Path) -> tuple[ConditionalTrajectoryDistribution, ...]:
    values = tuple(
        ConditionalTrajectoryDistribution.model_validate_json(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    )
    if not values or len({value.task_condition_id for value in values}) != len(values):
        raise ValueError("v21 distributions are empty or duplicate a task")
    return values


def _load_realizations(path: Path) -> tuple[GradientStateRealization, ...]:
    values = tuple(
        GradientStateRealization.model_validate_json(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    )
    if not values or len({value.realization_id for value in values}) != len(values):
        raise ValueError("v21 realizations are empty or duplicated")
    return values


def _verify_embedded_file(
    value: Mapping[str, Any],
    *,
    label: str,
) -> Path:
    path = Path(str(value["path"])).resolve()
    if not path.is_file() or _sha256(path) != value.get("sha256"):
        raise ValueError(f"v21 frozen input changed:{label}")
    return path


def _replay_support_artifacts(
    plan_path: Path,
    report_path: Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    plan = _read_json(plan_path)
    report = _read_json(report_path)
    _replay_hash(
        plan,
        field="plan_hash",
        prefix="finance_contribution_evaluation_support_plan:",
    )
    _replay_hash(
        report,
        field="report_hash",
        prefix="finance_contribution_evaluation_support_report:",
    )
    if plan.get("run_role") != TARGET_OBSERVABILITY_ROLE:
        raise ValueError("v21 Objective Support has another role")
    if report.get("run_role") != TARGET_OBSERVABILITY_ROLE:
        raise ValueError("v21 Objective report has another role")
    if report.get("status") != "passed" or report.get("plan_hash") != plan.get("plan_hash"):
        raise ValueError("v21 Objective Support did not pass")
    if report.get("authorization_objective_access") != "forbidden":
        raise ValueError("v21 Objective Support opened Authorization")
    if set(report.get("objective_partition_results", {})) != {"estimation", "validation"}:
        raise ValueError("v21 Objective Support evaluated an undeclared role")
    return plan, report


def verify_observability_contract(contract: Mapping[str, Any]) -> dict[str, Any]:
    frozen = dict(contract)
    _replay_hash(
        frozen,
        field="contract_hash",
        prefix=OBSERVABILITY_CONTRACT_HASH_PREFIX,
    )
    expected = {
        "contract_version": OBSERVABILITY_CONTRACT_VERSION,
        "run_role": TARGET_OBSERVABILITY_ROLE,
        "task_count": len(REQUIRED_TASK_TYPES),
        "state_count": 20,
        "state_realization_count": 60,
        "required_task_types": list(REQUIRED_TASK_TYPES),
        "direct_coordinate_count": DIRECT_COORDINATE_COUNT,
        "step_ratio_ladder": list(STEP_RATIO_LADDER),
        "primary_step_ratio": PRIMARY_STEP_RATIO,
        "objective_micro_split_count": OBJECTIVE_MICRO_SPLIT_COUNT,
        "objective_records_per_micro_split": OBJECTIVE_RECORDS_PER_MICRO_SPLIT,
        "minimum_practical_effect": MINIMUM_PRACTICAL_EFFECT,
        "allowed_objective_roles": ["estimation", "validation"],
        "authorization_objective_access": "forbidden",
        "gp_c_execution_allowed": False,
        "contribution_approximation_authorized": False,
        "production_authorization_eligible": False,
    }
    for field, expected_value in expected.items():
        if frozen.get(field) != expected_value:
            raise ValueError(f"v21 observability contract differs:{field}")

    preregistration_info = frozen.get("preregistration")
    numeric_info = frozen.get("source_numeric_execution_contract")
    support_info = frozen.get("source_support")
    inputs = frozen.get("frozen_inputs")
    if not all(
        isinstance(value, dict)
        for value in (preregistration_info, numeric_info, support_info, inputs)
    ):
        raise ValueError("v21 observability contract identity is incomplete")
    assert isinstance(preregistration_info, dict)
    assert isinstance(numeric_info, dict)
    assert isinstance(support_info, dict)
    assert isinstance(inputs, dict)

    preregistration_path = _verify_embedded_file(
        preregistration_info,
        label="preregistration",
    )
    preregistration = verify_preregistration(_read_json(preregistration_path))
    if preregistration["preregistration_hash"] != preregistration_info.get("preregistration_hash"):
        raise ValueError("v21 preregistration identity differs")

    numeric_path = _verify_embedded_file(numeric_info, label="numeric_execution_contract")
    from trusted_synthesis.experiments.vtdo_experiment import (
        phase1_contribution_numeric_execution as numeric_execution,
    )

    numeric_contract = numeric_execution.verify_execution_contract(_read_json(numeric_path))
    if numeric_contract["contract_hash"] != numeric_info.get("contract_hash"):
        raise ValueError("v21 numeric execution identity differs")
    if numeric_contract["selected_profile"] != frozen.get("selected_profile"):
        raise ValueError("v21 numeric profile differs")

    plan_path = _verify_embedded_file(support_info["plan"], label="support_plan")
    report_path = _verify_embedded_file(support_info["report"], label="support_report")
    support_plan, support_report = _replay_support_artifacts(plan_path, report_path)
    if support_plan["plan_hash"] != support_info.get("plan_hash"):
        raise ValueError("v21 support plan identity differs")
    if support_report["report_hash"] != support_info.get("report_hash"):
        raise ValueError("v21 support report identity differs")
    if (
        support_plan.get("numeric_contract_hash") != numeric_contract["contract_hash"]
        or support_info.get("source_numeric_contract_hash") != numeric_contract["contract_hash"]
    ):
        raise ValueError("v21 support uses another numeric contract")
    if support_plan.get("gradient_target_contract", {}).get("task_set_id") != frozen.get(
        "task_set_id"
    ):
        raise ValueError("v21 support target set differs")
    partition_ids = support_info.get("objective_partition_ids")
    if not isinstance(partition_ids, dict) or set(partition_ids) != {
        "estimation",
        "validation",
        "authorization",
    }:
        raise ValueError("v21 Objective partitions differ")
    if any(
        not isinstance(partition_ids[role], list)
        or len(partition_ids[role]) != OBJECTIVE_RECORDS_PER_ROLE
        or len(set(partition_ids[role])) != OBJECTIVE_RECORDS_PER_ROLE
        for role in partition_ids
    ):
        raise ValueError("v21 Objective partition support differs")
    partition_sets = [set(values) for values in partition_ids.values()]
    if any(
        left & right
        for index, left in enumerate(partition_sets)
        for right in partition_sets[index + 1 :]
    ):
        raise ValueError("v21 Objective partitions overlap")

    required_input_keys = {
        "target_artifacts",
        "target_population_report",
        "distributions",
        "initial_distribution_report",
        "state_realizations",
        "state_realization_report",
    }
    if set(inputs) != required_input_keys:
        raise ValueError("v21 frozen input manifest differs")
    frozen_paths = {
        name: _verify_embedded_file(value, label=name) for name, value in inputs.items()
    }
    target_report = verify_target_population(_read_json(frozen_paths["target_population_report"]))
    if target_report["target_artifacts_sha256"] != inputs["target_artifacts"]["sha256"]:
        raise ValueError("v21 target artifact lineage differs")
    artifacts = load_finance_multi_state_artifacts(frozen_paths["target_artifacts"])
    task_ids = {artifact.omega.task.task_id for artifact in artifacts}
    state_ids = {
        state.assignment.state.state_id
        for artifact in artifacts
        for state in artifact.accepted_states
    }
    if task_ids != set(str(value) for value in frozen.get("task_ids", ())):
        raise ValueError("v21 target task support differs")
    if len(state_ids) != frozen["state_count"]:
        raise ValueError("v21 target state support differs")

    initial_report = FinanceInitialDistributionReport.model_validate_json(
        frozen_paths["initial_distribution_report"].read_text(encoding="utf-8")
    )
    distributions = _load_distributions(frozen_paths["distributions"])
    if initial_report.status != "passed":
        raise ValueError("v21 initial distribution did not pass")
    if initial_report.artifact_sha256 != inputs["target_artifacts"]["sha256"]:
        raise ValueError("v21 initial distribution uses another target")
    if initial_report.distribution_sha256 != inputs["distributions"]["sha256"]:
        raise ValueError("v21 distribution payload differs")
    if {row.task_condition_id for row in distributions} != task_ids:
        raise ValueError("v21 distributions do not cover target tasks")

    realization_report = FinanceStateRealizationReport.model_validate_json(
        frozen_paths["state_realization_report"].read_text(encoding="utf-8")
    )
    realizations = _load_realizations(frozen_paths["state_realizations"])
    if realization_report.status != "passed":
        raise ValueError("v21 state realizations did not pass")
    if realization_report.realizations_sha256 != inputs["state_realizations"]["sha256"]:
        raise ValueError("v21 realization payload differs")
    if len(realizations) != frozen["state_realization_count"]:
        raise ValueError("v21 realization count differs")
    if {row.task_condition_id for row in realizations} != task_ids:
        raise ValueError("v21 realizations cross target tasks")
    if {row.state_id for row in realizations} != state_ids:
        raise ValueError("v21 realizations do not cover target states")
    counts: dict[str, int] = {}
    for row in realizations:
        counts[row.state_id] = counts.get(row.state_id, 0) + 1
    if set(counts.values()) != {3}:
        raise ValueError("v21 requires exactly three realizations per state")
    return frozen


def issue_observability_contract(
    *,
    source_numeric_contract_path: Path,
    preregistration_path: Path,
    target_population_report_path: Path,
    initial_distribution_dir: Path,
    state_realization_dir: Path,
    support_dir: Path,
    output_path: Path,
) -> dict[str, Any]:
    if output_path.exists():
        raise ValueError("v21 observability contract is immutable and already exists")
    from trusted_synthesis.experiments.vtdo_experiment import (
        phase1_contribution_numeric_execution as numeric_execution,
    )

    numeric_contract = numeric_execution.verify_execution_contract(
        _read_json(source_numeric_contract_path)
    )
    preregistration = verify_preregistration(_read_json(preregistration_path))
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
        or initial_report.artifact_sha256 != _sha256(target_path)
        or initial_report.distribution_sha256 != _sha256(distributions_path)
        or {row.task_condition_id for row in distributions} != task_ids
    ):
        raise ValueError("v21 initial distribution does not replay the target")

    realization_report_path = state_realization_dir / "finance_state_realization_report.json"
    realizations_path = state_realization_dir / "gradient_state_realizations.jsonl"
    realization_report = FinanceStateRealizationReport.model_validate_json(
        realization_report_path.read_text(encoding="utf-8")
    )
    realizations = _load_realizations(realizations_path)
    if (
        realization_report.status != "passed"
        or realization_report.realizations_sha256 != _sha256(realizations_path)
        or len(realizations) != 60
    ):
        raise ValueError("v21 state realization population is incomplete")
    if {row.task_condition_id for row in realizations} != task_ids:
        raise ValueError("v21 realizations cross target tasks")
    if {row.state_id for row in realizations} != state_ids:
        raise ValueError("v21 realizations do not cover target states")
    realization_counts: dict[str, int] = {}
    for row in realizations:
        realization_counts[row.state_id] = realization_counts.get(row.state_id, 0) + 1
    if set(realization_counts.values()) != {3}:
        raise ValueError("v21 requires exactly three realizations per state")

    support_plan_path = support_dir / "plan.json"
    support_report_path = support_dir / "beneficiary_evaluation_report.json"
    support_plan, support_report = _replay_support_artifacts(
        support_plan_path,
        support_report_path,
    )
    if support_plan["numeric_contract_hash"] != numeric_contract["contract_hash"]:
        raise ValueError("v21 support numeric contract differs")
    if set(support_plan["gradient_target_contract"]["task_ids"]) != task_ids:
        raise ValueError("v21 support targets another population")
    partitions = support_plan.get("objective_partitions")
    if not isinstance(partitions, dict):
        raise ValueError("v21 support lacks Objective partitions")
    partition_ids = {
        role: [str(value) for value in partitions[role]["record_ids"]]
        for role in ("estimation", "validation", "authorization")
    }
    if any(len(values) != OBJECTIVE_RECORDS_PER_ROLE for values in partition_ids.values()):
        raise ValueError("v21 support is not 128+128+128")

    contract: dict[str, Any] = {
        "contract_version": OBSERVABILITY_CONTRACT_VERSION,
        "run_role": TARGET_OBSERVABILITY_ROLE,
        "preregistration": {
            "path": str(preregistration_path.resolve()),
            "sha256": _sha256(preregistration_path),
            "preregistration_hash": preregistration["preregistration_hash"],
        },
        "source_numeric_execution_contract": {
            "path": str(source_numeric_contract_path.resolve()),
            "sha256": _sha256(source_numeric_contract_path),
            "contract_hash": numeric_contract["contract_hash"],
        },
        "source_support": {
            "plan": {
                "path": str(support_plan_path.resolve()),
                "sha256": _sha256(support_plan_path),
            },
            "report": {
                "path": str(support_report_path.resolve()),
                "sha256": _sha256(support_report_path),
            },
            "plan_hash": support_plan["plan_hash"],
            "report_hash": support_report["report_hash"],
            "source_numeric_contract_hash": support_plan["numeric_contract_hash"],
            "objective_partition_ids": partition_ids,
        },
        "frozen_inputs": {
            "target_artifacts": {
                "path": str(target_path),
                "sha256": _sha256(target_path),
            },
            "target_population_report": {
                "path": str(target_population_report_path.resolve()),
                "sha256": _sha256(target_population_report_path),
            },
            "distributions": {
                "path": str(distributions_path.resolve()),
                "sha256": _sha256(distributions_path),
            },
            "initial_distribution_report": {
                "path": str(initial_report_path.resolve()),
                "sha256": _sha256(initial_report_path),
            },
            "state_realizations": {
                "path": str(realizations_path.resolve()),
                "sha256": _sha256(realizations_path),
            },
            "state_realization_report": {
                "path": str(realization_report_path.resolve()),
                "sha256": _sha256(realization_report_path),
            },
        },
        "selected_profile": numeric_contract["selected_profile"],
        "profile_algorithm_contract": numeric_contract["profile_algorithm_contract"],
        "numeric_thresholds": numeric_contract["numeric_thresholds"],
        "task_set_id": support_plan["gradient_target_contract"]["task_set_id"],
        "task_ids": sorted(task_ids),
        "task_count": len(task_ids),
        "state_count": len(state_ids),
        "state_realization_count": len(realizations),
        "required_task_types": list(REQUIRED_TASK_TYPES),
        "direct_coordinate_count": DIRECT_COORDINATE_COUNT,
        "direct_coordinate_policy": "one_anchor_per_task_type_plus_one_extra_largest_support",
        "step_ratio_ladder": list(STEP_RATIO_LADDER),
        "primary_step_ratio": PRIMARY_STEP_RATIO,
        "parameter_step_normalization": ("actual_perturbation_norm_over_actual_global_step_norm"),
        "objective_micro_split_count": OBJECTIVE_MICRO_SPLIT_COUNT,
        "objective_records_per_micro_split": OBJECTIVE_RECORDS_PER_MICRO_SPLIT,
        "minimum_practical_effect": MINIMUM_PRACTICAL_EFFECT,
        "minimum_practical_effect_semantics": preregistration["minimum_practical_effect_semantics"],
        "radius_agreement_policy": preregistration["radius_agreement_policy"],
        "effect_resolution_policy": preregistration["effect_resolution_policy"],
        "exact_hypergradient_role": preregistration["exact_hypergradient_role"],
        "allowed_objective_roles": ["estimation", "validation"],
        "authorization_objective_access": "forbidden",
        "gp_c_execution_allowed": False,
        "contribution_approximation_authorized": False,
        "production_authorization_eligible": False,
        "success_transition": "freeze_independent_gp_c_comparison_protocol",
        "failure_transition": ("retain_contribution_zero_and_report_target_unobservability"),
        "claim_boundary": preregistration["claim_boundary"],
    }
    contract["contract_hash"] = canonical_hash(
        contract,
        prefix=OBSERVABILITY_CONTRACT_HASH_PREFIX,
    )
    verify_observability_contract(contract)
    _write_json(output_path, contract)
    return contract


def _issue(args: argparse.Namespace) -> None:
    contract = issue_observability_contract(
        source_numeric_contract_path=Path(args.source_numeric_contract).resolve(),
        preregistration_path=Path(args.preregistration).resolve(),
        target_population_report_path=Path(args.target_population_report).resolve(),
        initial_distribution_dir=Path(args.initial_distribution_dir).resolve(),
        state_realization_dir=Path(args.state_realization_dir).resolve(),
        support_dir=Path(args.support_dir).resolve(),
        output_path=Path(args.output_path).resolve(),
    )
    print(json.dumps(contract, ensure_ascii=False, indent=2, sort_keys=True))


def _select(args: argparse.Namespace) -> None:
    report = select_target_population(
        source_report_path=Path(args.source_report).resolve(),
        source_artifacts_path=Path(args.source_artifacts).resolve(),
        preregistration_path=Path(args.preregistration).resolve(),
        output_dir=Path(args.output_dir).resolve(),
    )
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Freeze the v21 target-observability contract")
    subparsers = parser.add_subparsers(dest="command", required=True)
    select = subparsers.add_parser("select-target-population")
    select.add_argument("--source-report", required=True)
    select.add_argument("--source-artifacts", required=True)
    select.add_argument("--preregistration", required=True)
    select.add_argument("--output-dir", required=True)
    select.set_defaults(handler=_select)
    issue = subparsers.add_parser("issue-contract")
    issue.add_argument("--source-numeric-contract", required=True)
    issue.add_argument("--preregistration", required=True)
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
