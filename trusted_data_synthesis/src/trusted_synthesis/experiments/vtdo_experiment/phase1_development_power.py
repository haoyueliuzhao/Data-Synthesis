from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import math
import os
import platform
import random
import re
import statistics
import subprocess
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from trusted_synthesis.architecture.generalization import audit_generalization_contract
from trusted_synthesis.core.vtdo import ConditionalTrajectoryDistribution
from trusted_synthesis.domains.finance.schema import FinanceArchiveConfig
from trusted_synthesis.experiments.vtdo_experiment.multistate import (
    FinanceTaskStateArtifact,
    load_finance_multi_state_artifacts,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_agent_population import (
    FinanceAgentPopulationReport,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_contribution_gradient import (
    GRADIENT_STATE_STRATEGY_PRIORITY,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_contribution_support import (
    _artifact_evidence_version_ids,
    _objective_records,
    _partition_manifest,
    _select_stratified_artifacts,
    _task_semantic_signature,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_initial_distribution import (
    FinanceInitialDistributionReport,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_state_realizations import (
    MINIMUM_PARTIAL_INITIAL_CATALOG_HIT_RATE,
    MINIMUM_PARTIAL_INITIAL_CATALOG_HITS_PER_TASK,
    FinanceStateRealizationReport,
    PartialInitialDistributionQualification,
    partial_initial_distribution_qualification_id,
    validate_initial_distribution_lineage,
)
from trusted_synthesis.experiments.vtdo_experiment.schema import VTDOTrainingRecord
from trusted_synthesis.hashing import canonical_hash
from trusted_synthesis.runtime.agent.schema import AgentModelConfig

DEVELOPMENT_POPULATION_VERSION = "finance_development_power_population.v22"
DEVELOPMENT_POPULATION_HASH_PREFIX = "finance_development_power_population:"
DEVELOPMENT_SUPPORT_VERSION = "finance_development_objective_support.v22"
DEVELOPMENT_SUPPORT_HASH_PREFIX = "finance_development_objective_support:"
DEVELOPMENT_CONTRACT_VERSION = "finance_development_power_contract.v22.1"
DEVELOPMENT_CONTRACT_HASH_PREFIX = "finance_development_power_contract:"
DEVELOPMENT_REPORT_VERSION = "finance_development_power_report.v22"
DEVELOPMENT_REPORT_HASH_PREFIX = "finance_development_power_report:"
PREFLIGHT_VERSION = "finance_development_power_preflight.v22"
PREFLIGHT_HASH_PREFIX = "finance_development_power_preflight:"

REQUIRED_TASK_TYPES = (
    "comparison",
    "derived_growth_comparison",
    "registered_ratio",
    "temporal_absolute_change",
    "temporal_average",
    "temporal_growth",
)
TASKS_PER_TYPE = 5
EXPECTED_TASK_COUNT = len(REQUIRED_TASK_TYPES) * TASKS_PER_TYPE
MINIMUM_STATES_PER_TASK = 3
MAXIMUM_STATES_PER_TASK = 5
EXPLORER_REPLICAS_PER_TASK = 10
REALIZATIONS_PER_STATE = 5
DEVELOPMENT_OBJECTIVE_RECORD_COUNT = 64
OBJECTIVE_MICRO_SPLIT_COUNT = 8
OBJECTIVE_RECORDS_PER_MICRO_SPLIT = 8
TARGET_PROBABILITY_SHIFT = 0.02
POWER_TARGET = 0.80
POWER_TASK_COUNT_GRID = (30, 45, 50, 60, 80, 100)
STANDARDIZED_EFFECT_GRID = (0.3, 0.4, 0.5)
POWER_MONTE_CARLO_REPLICATES = 10_000
SELECTION_SALT = "finance_v22_development_power_preoutcome_20260807"

ENERGY_CONFIG: dict[str, float | str] = {
    "epsilon": 1e-6,
    "contribution_temperature": 0.01,
    "novelty_temperature": 1.0,
    "contribution_weight": 0.5,
    "novelty_weight": 0.5,
    "history_kl_weight": 1.0,
    "coverage_kl_weight": 1.0,
    "reachability_weight": 1.0,
    "reachability_floor": 0.01,
    "reachability_signal": "posterior_mean",
}

_SECRET_PATTERN = re.compile(r"(?:sk|key)-[A-Za-z0-9._-]{20,}")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"v22 artifact is not a JSON object:{path}")
    return value


def _read_jsonl(path: Path) -> tuple[dict[str, Any], ...]:
    values = tuple(
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    )
    if any(not isinstance(value, dict) for value in values):
        raise ValueError(f"v22 JSONL contains a non-object row:{path}")
    return values


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
        raise ValueError(f"v22 identity replay failed:{field}")
    return str(observed)


def _artifact_task_id(artifact: FinanceTaskStateArtifact) -> str:
    return artifact.omega.task.task_id


def _artifact_task_type(artifact: FinanceTaskStateArtifact) -> str:
    return artifact.omega.task.public.task_type


def _artifact_state_ids(artifact: FinanceTaskStateArtifact) -> tuple[str, ...]:
    return tuple(sorted(state.assignment.state.state_id for state in artifact.accepted_states))


def _gradient_eligible(artifact: FinanceTaskStateArtifact) -> bool:
    available = {state.strategy for state in artifact.accepted_states}
    return len(available & set(GRADIENT_STATE_STRATEGY_PRIORITY)) >= 3


def _exclusion_index(
    paths: Sequence[Path],
) -> tuple[set[str], set[str], set[str], tuple[dict[str, Any], ...]]:
    task_ids: set[str] = set()
    signatures: set[str] = set()
    evidence_versions: set[str] = set()
    manifests: list[dict[str, Any]] = []
    for path in paths:
        resolved = path.resolve()
        artifacts = load_finance_multi_state_artifacts(resolved)
        if not artifacts:
            raise ValueError(f"v22 exclusion artifact is empty:{resolved}")
        task_ids.update(_artifact_task_id(artifact) for artifact in artifacts)
        signatures.update(_task_semantic_signature(artifact) for artifact in artifacts)
        evidence_versions.update(
            evidence_version
            for artifact in artifacts
            for evidence_version in _artifact_evidence_version_ids(artifact)
        )
        manifests.append(
            {
                "path": str(resolved),
                "sha256": _sha256(resolved),
                "task_count": len(artifacts),
            }
        )
    return task_ids, signatures, evidence_versions, tuple(manifests)


def select_balanced_development_artifacts(
    artifacts: Sequence[FinanceTaskStateArtifact],
    *,
    excluded_task_ids: set[str],
    excluded_semantic_signatures: set[str],
    excluded_evidence_versions: set[str],
    tasks_per_type: int = TASKS_PER_TYPE,
    selection_salt: str = SELECTION_SALT,
) -> tuple[FinanceTaskStateArtifact, ...]:
    if tasks_per_type < 1 or not selection_salt.strip():
        raise ValueError("v22 population selection contract is invalid")
    selected: list[FinanceTaskStateArtifact] = []
    selected_evidence: set[str] = set()
    selected_task_ids: set[str] = set()
    for task_type in REQUIRED_TASK_TYPES:
        candidates = []
        for artifact in artifacts:
            task_id = _artifact_task_id(artifact)
            state_count = len(artifact.accepted_states)
            evidence = set(_artifact_evidence_version_ids(artifact))
            if _artifact_task_type(artifact) != task_type:
                continue
            if not MINIMUM_STATES_PER_TASK <= state_count <= MAXIMUM_STATES_PER_TASK:
                continue
            if not _gradient_eligible(artifact):
                continue
            if task_id in excluded_task_ids:
                continue
            if _task_semantic_signature(artifact) in excluded_semantic_signatures:
                continue
            if evidence & excluded_evidence_versions:
                continue
            candidates.append(artifact)
        candidates.sort(
            key=lambda artifact: (
                canonical_hash(
                    {
                        "selection_salt": selection_salt,
                        "task_type": task_type,
                        "state_count": len(artifact.accepted_states),
                        "artifact_id": artifact.artifact_id,
                    },
                    prefix="finance_development_power_task_order:",
                ),
                artifact.artifact_id,
            )
        )
        chosen = 0
        for artifact in candidates:
            task_id = _artifact_task_id(artifact)
            evidence = set(_artifact_evidence_version_ids(artifact))
            if task_id in selected_task_ids or evidence & selected_evidence:
                continue
            selected.append(artifact)
            selected_task_ids.add(task_id)
            selected_evidence.update(evidence)
            chosen += 1
            if chosen == tasks_per_type:
                break
        if chosen != tasks_per_type:
            raise ValueError(
                f"v22 population lacks disjoint support:{task_type}:{chosen}/{tasks_per_type}"
            )
    return tuple(selected)


def select_population(
    *,
    source_report_path: Path,
    source_artifacts_path: Path,
    excluded_artifact_paths: Sequence[Path],
    output_dir: Path,
) -> dict[str, Any]:
    report_path = output_dir / "development_population_report.json"
    artifacts_path = output_dir / "development_task_states.jsonl"
    if report_path.exists() or artifacts_path.exists():
        raise ValueError("v22 Development population is immutable and already exists")
    source_report = FinanceAgentPopulationReport.model_validate(_read_json(source_report_path))
    if source_report.status != "passed":
        raise ValueError("v22 source population did not pass")
    if _sha256(source_artifacts_path) != source_report.artifact_sha256:
        raise ValueError("v22 source population Artifact changed")
    source_artifacts = load_finance_multi_state_artifacts(source_artifacts_path)
    if len(source_artifacts) != source_report.accepted_task_count:
        raise ValueError("v22 source population accounting differs")
    (
        excluded_task_ids,
        excluded_signatures,
        excluded_evidence,
        exclusion_manifests,
    ) = _exclusion_index(excluded_artifact_paths)
    selected = select_balanced_development_artifacts(
        source_artifacts,
        excluded_task_ids=excluded_task_ids,
        excluded_semantic_signatures=excluded_signatures,
        excluded_evidence_versions=excluded_evidence,
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_jsonl(
        artifacts_path,
        tuple(artifact.model_dump(mode="json") for artifact in selected),
    )
    task_type_counts = dict(sorted(Counter(_artifact_task_type(row) for row in selected).items()))
    state_counts = {_artifact_task_id(row): len(row.accepted_states) for row in selected}
    evidence = {
        value for artifact in selected for value in _artifact_evidence_version_ids(artifact)
    }
    report: dict[str, Any] = {
        "experiment_version": DEVELOPMENT_POPULATION_VERSION,
        "population_role": "development_variance_and_power_only",
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
        "excluded_artifacts": exclusion_manifests,
        "excluded_task_count": len(excluded_task_ids),
        "excluded_semantic_signature_count": len(excluded_signatures),
        "excluded_evidence_version_count": len(excluded_evidence),
        "selection_policy": "preoutcome_hash_order_exact_five_per_task_type",
        "selection_salt": SELECTION_SALT,
        "required_task_types": list(REQUIRED_TASK_TYPES),
        "tasks_per_type": TASKS_PER_TYPE,
        "selected_artifact_ids": [row.artifact_id for row in selected],
        "selected_task_ids": [_artifact_task_id(row) for row in selected],
        "selected_task_type_by_id": {
            _artifact_task_id(row): _artifact_task_type(row) for row in selected
        },
        "task_type_counts": task_type_counts,
        "task_count": len(selected),
        "state_count": sum(state_counts.values()),
        "state_count_by_task": state_counts,
        "evidence_version_count": len(evidence),
        "development_artifacts_path": str(artifacts_path.resolve()),
        "development_artifacts_sha256": _sha256(artifacts_path),
        "outcomes_observed_before_selection": False,
        "validation_objective_access": "forbidden",
        "authorization_objective_access": "forbidden",
        "gp_c_execution_allowed": False,
        "contribution_approximation_authorized": False,
        "production_authorization_eligible": False,
        "status": "passed",
        "claim_boundary": (
            "This population supports Development-only variance and power analysis. It cannot "
            "evaluate GP-C, open Validation or Authorization, authorize Contribution, or update "
            "VTDO."
        ),
    }
    report["report_hash"] = canonical_hash(
        report,
        prefix=DEVELOPMENT_POPULATION_HASH_PREFIX,
    )
    verify_population(report)
    _write_json(report_path, report)
    return report


def verify_population(report: Mapping[str, Any]) -> dict[str, Any]:
    frozen = dict(report)
    _replay_hash(
        frozen,
        field="report_hash",
        prefix=DEVELOPMENT_POPULATION_HASH_PREFIX,
    )
    expected = {
        "experiment_version": DEVELOPMENT_POPULATION_VERSION,
        "population_role": "development_variance_and_power_only",
        "required_task_types": list(REQUIRED_TASK_TYPES),
        "tasks_per_type": TASKS_PER_TYPE,
        "task_count": EXPECTED_TASK_COUNT,
        "outcomes_observed_before_selection": False,
        "validation_objective_access": "forbidden",
        "authorization_objective_access": "forbidden",
        "gp_c_execution_allowed": False,
        "contribution_approximation_authorized": False,
        "production_authorization_eligible": False,
        "status": "passed",
    }
    for field, expected_value in expected.items():
        if frozen.get(field) != expected_value:
            raise ValueError(f"v22 population contract differs:{field}")
    if frozen.get("task_type_counts") != {
        task_type: TASKS_PER_TYPE for task_type in REQUIRED_TASK_TYPES
    }:
        raise ValueError("v22 task-type balance differs")
    state_counts = frozen.get("state_count_by_task")
    if not isinstance(state_counts, dict) or len(state_counts) != EXPECTED_TASK_COUNT:
        raise ValueError("v22 state accounting is incomplete")
    if any(
        not MINIMUM_STATES_PER_TASK <= int(value) <= MAXIMUM_STATES_PER_TASK
        for value in state_counts.values()
    ):
        raise ValueError("v22 task state count is outside the frozen range")
    if sum(int(value) for value in state_counts.values()) != frozen.get("state_count"):
        raise ValueError("v22 aggregate state accounting differs")
    path = Path(str(frozen["development_artifacts_path"])).resolve()
    if not path.is_file() or _sha256(path) != frozen.get("development_artifacts_sha256"):
        raise ValueError("v22 Development artifacts changed")
    artifacts = load_finance_multi_state_artifacts(path)
    if len(artifacts) != EXPECTED_TASK_COUNT:
        raise ValueError("v22 Development artifact count differs")
    if [row.artifact_id for row in artifacts] != frozen.get("selected_artifact_ids"):
        raise ValueError("v22 Development artifact identity differs")
    evidence_sets = [set(_artifact_evidence_version_ids(row)) for row in artifacts]
    if any(
        left & right
        for index, left in enumerate(evidence_sets)
        for right in evidence_sets[index + 1 :]
    ):
        raise ValueError("v22 Development tasks share public Evidence")
    return frozen


def _select_disjoint_objective_artifacts(
    artifacts: tuple[FinanceTaskStateArtifact, ...],
    *,
    count: int,
    salt: str,
) -> tuple[FinanceTaskStateArtifact, ...]:
    ordered = _select_stratified_artifacts(
        artifacts,
        count=len(artifacts),
        salt=salt,
    )
    selected: list[FinanceTaskStateArtifact] = []
    selected_signatures: set[str] = set()
    selected_evidence: set[str] = set()
    for artifact in ordered:
        signature = _task_semantic_signature(artifact)
        evidence = set(_artifact_evidence_version_ids(artifact))
        if signature in selected_signatures or evidence & selected_evidence:
            continue
        selected.append(artifact)
        selected_signatures.add(signature)
        selected_evidence.update(evidence)
        if len(selected) == count:
            break
    if len(selected) != count:
        raise ValueError(
            f"v22 lacks disjoint Development Objective support:{len(selected)}/{count}"
        )
    return tuple(selected)


def _micro_split_manifest(
    artifacts: Sequence[FinanceTaskStateArtifact],
    records: Sequence[VTDOTrainingRecord],
) -> tuple[dict[str, Any], ...]:
    if len(artifacts) != DEVELOPMENT_OBJECTIVE_RECORD_COUNT or len(records) != len(artifacts):
        raise ValueError("v22 micro-split input count differs")
    split_ids = tuple(
        f"development_micro_split_{index:02d}" for index in range(OBJECTIVE_MICRO_SPLIT_COUNT)
    )
    members: dict[str, list[tuple[FinanceTaskStateArtifact, VTDOTrainingRecord]]] = {
        split_id: [] for split_id in split_ids
    }
    task_type_counts: dict[str, Counter[str]] = {split_id: Counter() for split_id in split_ids}
    pairs = sorted(
        zip(artifacts, records, strict=True),
        key=lambda pair: (
            _artifact_task_type(pair[0]),
            canonical_hash(
                {"record_id": pair[1].record_id, "task_id": _artifact_task_id(pair[0])},
                prefix="finance_development_micro_split_order:",
            ),
        ),
    )
    for artifact, record in pairs:
        task_type = _artifact_task_type(artifact)
        eligible = tuple(
            split_id
            for split_id in split_ids
            if len(members[split_id]) < OBJECTIVE_RECORDS_PER_MICRO_SPLIT
        )
        if not eligible:
            raise ValueError("v22 micro-split capacity was exhausted")
        split_id = min(
            eligible,
            key=lambda value: (
                task_type_counts[value][task_type],
                len(members[value]),
                canonical_hash(
                    {"record_id": record.record_id, "split_id": value},
                    prefix="finance_development_micro_split_assignment:",
                ),
            ),
        )
        members[split_id].append((artifact, record))
        task_type_counts[split_id][task_type] += 1
    manifests = []
    for split_id in split_ids:
        values = sorted(members[split_id], key=lambda pair: pair[1].record_id)
        if len(values) != OBJECTIVE_RECORDS_PER_MICRO_SPLIT:
            raise ValueError("v22 micro-split size differs")
        record_ids = tuple(record.record_id for _, record in values)
        task_ids = tuple(_artifact_task_id(artifact) for artifact, _ in values)
        manifests.append(
            {
                "micro_split_id": split_id,
                "record_ids": record_ids,
                "task_ids": task_ids,
                "task_type_counts": dict(sorted(task_type_counts[split_id].items())),
                "set_id": canonical_hash(
                    record_ids,
                    prefix="finance_development_objective_micro_split:",
                ),
            }
        )
    return tuple(manifests)


def freeze_development_support(
    *,
    population_report_path: Path,
    source_artifacts_path: Path,
    excluded_artifact_paths: Sequence[Path],
    output_dir: Path,
) -> dict[str, Any]:
    manifest_path = output_dir / "development_objective_support.json"
    records_path = output_dir / "development_objective_records.jsonl"
    artifacts_path = output_dir / "development_objective_task_states.jsonl"
    if manifest_path.exists() or records_path.exists() or artifacts_path.exists():
        raise ValueError("v22 Development Objective support is immutable and already exists")
    population = verify_population(_read_json(population_report_path))
    target_path = Path(str(population["development_artifacts_path"])).resolve()
    exclusion_paths = (target_path, *tuple(excluded_artifact_paths))
    excluded_tasks, excluded_signatures, excluded_evidence, manifests = _exclusion_index(
        exclusion_paths
    )
    source = load_finance_multi_state_artifacts(source_artifacts_path)
    eligible = tuple(
        artifact
        for artifact in source
        if _artifact_task_id(artifact) not in excluded_tasks
        and _task_semantic_signature(artifact) not in excluded_signatures
        and not (_artifact_evidence_version_ids(artifact) & excluded_evidence)
        and _gradient_eligible(artifact)
    )
    selected = _select_disjoint_objective_artifacts(
        eligible,
        count=DEVELOPMENT_OBJECTIVE_RECORD_COUNT,
        salt="finance_v22_development_objective_support",
    )
    records = _objective_records(
        selected,
        salt="finance_v22_development_objective_strategy",
    )
    if len({row.record_id for row in records}) != DEVELOPMENT_OBJECTIVE_RECORD_COUNT:
        raise ValueError("v22 Development Objective records are duplicated")
    micro_splits = _micro_split_manifest(selected, records)
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_jsonl(
        artifacts_path,
        tuple(row.model_dump(mode="json") for row in selected),
    )
    _write_jsonl(
        records_path,
        tuple(row.model_dump(mode="json") for row in records),
    )
    partition = _partition_manifest(selected, records)
    manifest: dict[str, Any] = {
        "experiment_version": DEVELOPMENT_SUPPORT_VERSION,
        "run_role": "development_variance_and_power_only",
        "population_report": {
            "path": str(population_report_path.resolve()),
            "sha256": _sha256(population_report_path),
            "report_hash": population["report_hash"],
        },
        "source_artifacts": {
            "path": str(source_artifacts_path.resolve()),
            "sha256": _sha256(source_artifacts_path),
            "task_count": len(source),
        },
        "excluded_artifacts": manifests,
        "selection_policy": (
            "multidimensional_inverse_frequency_with_signature_and_evidence_disjointness"
        ),
        "record_count": len(records),
        "micro_split_count": OBJECTIVE_MICRO_SPLIT_COUNT,
        "records_per_micro_split": OBJECTIVE_RECORDS_PER_MICRO_SPLIT,
        "partition": partition,
        "micro_splits": micro_splits,
        "records_path": str(records_path.resolve()),
        "records_sha256": _sha256(records_path),
        "artifacts_path": str(artifacts_path.resolve()),
        "artifacts_sha256": _sha256(artifacts_path),
        "validation_objective_access": "forbidden",
        "authorization_objective_access": "forbidden",
        "gp_c_execution_allowed": False,
        "contribution_approximation_authorized": False,
        "outcomes_observed": False,
        "claim_boundary": (
            "Only the Development Objective role is frozen. Validation and Authorization do "
            "not exist in this artifact and cannot be inferred from it."
        ),
    }
    manifest["manifest_hash"] = canonical_hash(
        manifest,
        prefix=DEVELOPMENT_SUPPORT_HASH_PREFIX,
    )
    verify_development_support(manifest)
    _write_json(manifest_path, manifest)
    return manifest


def verify_development_support(value: Mapping[str, Any]) -> dict[str, Any]:
    frozen = dict(value)
    _replay_hash(
        frozen,
        field="manifest_hash",
        prefix=DEVELOPMENT_SUPPORT_HASH_PREFIX,
    )
    expected = {
        "experiment_version": DEVELOPMENT_SUPPORT_VERSION,
        "run_role": "development_variance_and_power_only",
        "record_count": DEVELOPMENT_OBJECTIVE_RECORD_COUNT,
        "micro_split_count": OBJECTIVE_MICRO_SPLIT_COUNT,
        "records_per_micro_split": OBJECTIVE_RECORDS_PER_MICRO_SPLIT,
        "validation_objective_access": "forbidden",
        "authorization_objective_access": "forbidden",
        "gp_c_execution_allowed": False,
        "contribution_approximation_authorized": False,
        "outcomes_observed": False,
    }
    for field, expected_value in expected.items():
        if frozen.get(field) != expected_value:
            raise ValueError(f"v22 Development Objective contract differs:{field}")
    records_path = Path(str(frozen["records_path"])).resolve()
    artifacts_path = Path(str(frozen["artifacts_path"])).resolve()
    if not records_path.is_file() or _sha256(records_path) != frozen.get("records_sha256"):
        raise ValueError("v22 Development Objective records changed")
    if not artifacts_path.is_file() or _sha256(artifacts_path) != frozen.get("artifacts_sha256"):
        raise ValueError("v22 Development Objective artifacts changed")
    records = tuple(VTDOTrainingRecord.model_validate(row) for row in _read_jsonl(records_path))
    if len(records) != DEVELOPMENT_OBJECTIVE_RECORD_COUNT:
        raise ValueError("v22 Development Objective record count differs")
    artifacts = load_finance_multi_state_artifacts(artifacts_path)
    if len(artifacts) != DEVELOPMENT_OBJECTIVE_RECORD_COUNT:
        raise ValueError("v22 Development Objective artifact count differs")
    if len({record.record_id for record in records}) != len(records):
        raise ValueError("v22 Development Objective records are duplicated")
    support_evidence = [set(_artifact_evidence_version_ids(row)) for row in artifacts]
    if any(
        left & right
        for index, left in enumerate(support_evidence)
        for right in support_evidence[index + 1 :]
    ):
        raise ValueError("v22 Development Objective tasks share public Evidence")
    support_signatures = {_task_semantic_signature(row) for row in artifacts}
    if len(support_signatures) != len(artifacts):
        raise ValueError("v22 Development Objective semantic signatures are duplicated")
    population_item = frozen.get("population_report")
    if not isinstance(population_item, dict):
        raise ValueError("v22 Development population reference is missing")
    population_path = Path(str(population_item.get("path"))).resolve()
    if not population_path.is_file() or _sha256(population_path) != population_item.get("sha256"):
        raise ValueError("v22 Development population reference changed")
    population = verify_population(_read_json(population_path))
    if population["report_hash"] != population_item.get("report_hash"):
        raise ValueError("v22 Development population identity differs")
    target_artifacts = load_finance_multi_state_artifacts(
        Path(str(population["development_artifacts_path"]))
    )
    target_task_ids = {_artifact_task_id(row) for row in target_artifacts}
    target_signatures = {_task_semantic_signature(row) for row in target_artifacts}
    target_evidence = {
        evidence_id
        for row in target_artifacts
        for evidence_id in _artifact_evidence_version_ids(row)
    }
    if target_task_ids & {_artifact_task_id(row) for row in artifacts}:
        raise ValueError("v22 Development target and Objective tasks overlap")
    if target_signatures & support_signatures:
        raise ValueError("v22 Development target and Objective signatures overlap")
    if target_evidence & set().union(*support_evidence):
        raise ValueError("v22 Development target and Objective Evidence overlap")
    expected_partition = _partition_manifest(artifacts, records)
    if canonical_hash(expected_partition) != canonical_hash(frozen.get("partition")):
        raise ValueError("v22 Development Objective partition differs")
    expected_micro_splits = _micro_split_manifest(artifacts, records)
    if canonical_hash(expected_micro_splits) != canonical_hash(frozen.get("micro_splits")):
        raise ValueError("v22 Development Objective micro-splits differ")
    return frozen


def _run_checked(command: Sequence[str], *, cwd: Path) -> dict[str, Any]:
    result = subprocess.run(
        tuple(command),
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    return {
        "command": list(command),
        "exit_code": result.returncode,
        "passed": result.returncode == 0,
        "output_tail": result.stdout[-4000:],
    }


def _tracked_secret_hits(repo_root: Path) -> tuple[str, ...]:
    result = subprocess.run(
        ("git", "ls-files", "-z"),
        cwd=repo_root,
        check=True,
        stdout=subprocess.PIPE,
    )
    hits = []
    for raw_path in result.stdout.split(b"\0"):
        if not raw_path:
            continue
        relative = raw_path.decode("utf-8")
        path = repo_root / relative
        if not path.is_file() or path.suffix.lower() in {".png", ".jpg", ".parquet"}:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if _SECRET_PATTERN.search(text):
            hits.append(relative)
    return tuple(sorted(hits))


def run_preflight(*, repo_root: Path, output_path: Path) -> dict[str, Any]:
    status = subprocess.run(
        ("git", "status", "--porcelain"),
        cwd=repo_root,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
    ).stdout
    if status.strip():
        raise ValueError("v22 preflight requires a clean tracked worktree")
    commands = (
        (str(repo_root / ".venv/bin/ruff"), "check", "."),
        (str(repo_root / ".venv/bin/mypy"), "src"),
        (str(repo_root / ".venv/bin/pytest"), "-q"),
        ("git", "diff", "--check"),
    )
    results = tuple(_run_checked(command, cwd=repo_root) for command in commands)
    generalization = audit_generalization_contract(repo_root / "src")
    secret_hits = _tracked_secret_hits(repo_root)
    git_commit = subprocess.run(
        ("git", "rev-parse", "HEAD"),
        cwd=repo_root,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
    ).stdout.strip()
    git_tree = subprocess.run(
        ("git", "rev-parse", "HEAD^{tree}"),
        cwd=repo_root,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
    ).stdout.strip()
    report: dict[str, Any] = {
        "preflight_version": PREFLIGHT_VERSION,
        "git_commit": git_commit,
        "git_tree": git_tree,
        "dirty_status": False,
        "commands": results,
        "generalization_audit": generalization.model_dump(mode="json"),
        "credential_leakage_hits": secret_hits,
        "credential_environment_values_recorded": False,
        "status": (
            "passed"
            if all(row["passed"] for row in results) and generalization.passed and not secret_hits
            else "failed"
        ),
    }
    report["report_hash"] = canonical_hash(report, prefix=PREFLIGHT_HASH_PREFIX)
    _write_json(output_path, report)
    if report["status"] != "passed":
        raise ValueError("v22 preflight did not pass")
    return report


def _dependency_version(name: str) -> str:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return "not-installed"


def prepare_contract(
    *,
    population_report_path: Path,
    support_manifest_path: Path,
    preflight_path: Path,
    model_config_path: Path,
    materializer_model_config_path: Path,
    archive_config_path: Path,
    source_numeric_plan_path: Path,
    output_path: Path,
) -> dict[str, Any]:
    if output_path.exists():
        raise ValueError("v22 Development contract is immutable and already exists")
    population = verify_population(_read_json(population_report_path))
    support = verify_development_support(_read_json(support_manifest_path))
    preflight = _read_json(preflight_path)
    _replay_hash(preflight, field="report_hash", prefix=PREFLIGHT_HASH_PREFIX)
    if preflight.get("status") != "passed":
        raise ValueError("v22 Development contract requires a passed preflight")
    model_raw = _read_json(model_config_path)
    model_config = AgentModelConfig.model_validate(model_raw.get("model", model_raw))
    materializer_raw = _read_json(materializer_model_config_path)
    materializer_model_config = AgentModelConfig.model_validate(
        materializer_raw.get("model", materializer_raw)
    )
    archive_config = FinanceArchiveConfig.from_json(archive_config_path)
    numeric_plan = _read_json(source_numeric_plan_path)
    required_numeric_fields = {
        "model_dir",
        "base_model_manifest_hash",
        "beneficiary_adapter_dir",
        "beneficiary_adapter_tensor_sha256",
        "beneficiary_model_state_id",
        "beneficiary_checkpoint_hash",
        "numeric_profile",
        "profile_algorithm_contract",
    }
    if not required_numeric_fields <= set(numeric_plan):
        raise ValueError("v22 source numeric plan identity is incomplete")
    contract: dict[str, Any] = {
        "contract_version": DEVELOPMENT_CONTRACT_VERSION,
        "run_role": "development_variance_and_power_only",
        "preflight": {
            "path": str(preflight_path.resolve()),
            "sha256": _sha256(preflight_path),
            "report_hash": preflight["report_hash"],
            "git_commit": preflight["git_commit"],
            "git_tree": preflight["git_tree"],
        },
        "population": {
            "path": str(population_report_path.resolve()),
            "sha256": _sha256(population_report_path),
            "report_hash": population["report_hash"],
            "artifacts_path": population["development_artifacts_path"],
            "artifacts_sha256": population["development_artifacts_sha256"],
        },
        "development_objective_support": {
            "path": str(support_manifest_path.resolve()),
            "sha256": _sha256(support_manifest_path),
            "manifest_hash": support["manifest_hash"],
            "record_count": support["record_count"],
        },
        "environment": {
            "python": platform.python_version(),
            "implementation": platform.python_implementation(),
            "platform": platform.platform(),
            "torch": _dependency_version("torch"),
            "transformers": _dependency_version("transformers"),
            "peft": _dependency_version("peft"),
            "cuda_visible_device_count": os.environ.get("CUDA_VISIBLE_DEVICES", "host-default"),
        },
        "finance_archive": {
            "path": str(archive_config_path.resolve()),
            "sha256": _sha256(archive_config_path),
            "kg_build_id": archive_config.required_kg_build_id,
            "graph_schema_version": archive_config.required_graph_schema_version,
        },
        "explorer": {
            "model_config_path": str(model_config_path.resolve()),
            "model_config_sha256": _sha256(model_config_path),
            "model_config_hash": model_config.public_manifest_hash,
            "provider": model_config.provider,
            "requested_model": model_config.model,
            "api_key_env": model_config.api_key_env,
            "credential_value_recorded": False,
            "replicas_per_task": EXPLORER_REPLICAS_PER_TASK,
        },
        "materializer": {
            "model_config_path": str(materializer_model_config_path.resolve()),
            "model_config_sha256": _sha256(materializer_model_config_path),
            "model_config_hash": materializer_model_config.public_manifest_hash,
            "provider": materializer_model_config.provider,
            "requested_model": materializer_model_config.model,
            "api_key_env": materializer_model_config.api_key_env,
            "credential_value_recorded": False,
            "realizations_per_state": REALIZATIONS_PER_STATE,
        },
        "numeric_execution": {
            "source_plan_path": str(source_numeric_plan_path.resolve()),
            "source_plan_sha256": _sha256(source_numeric_plan_path),
            **{field: numeric_plan[field] for field in sorted(required_numeric_fields)},
        },
        "data_contract": {
            "task_count": EXPECTED_TASK_COUNT,
            "tasks_per_type": TASKS_PER_TYPE,
            "state_count": population["state_count"],
            "minimum_states_per_task": MINIMUM_STATES_PER_TASK,
            "maximum_states_per_task": MAXIMUM_STATES_PER_TASK,
            "realizations_per_state": REALIZATIONS_PER_STATE,
            "objective_record_count": DEVELOPMENT_OBJECTIVE_RECORD_COUNT,
            "objective_micro_split_count": OBJECTIVE_MICRO_SPLIT_COUNT,
            "objective_records_per_micro_split": OBJECTIVE_RECORDS_PER_MICRO_SPLIT,
        },
        "mpe_contract": {
            "definition": (
                "minimum_centered_contribution_contrast_causing_selected_state_probability_shift"
            ),
            "target_probability_shift": TARGET_PROBABILITY_SHIFT,
            "energy_config": ENERGY_CONFIG,
            "freeze_policy": (
                "derive_from_preoutcome_initial_distributions_before_target_measurement"
            ),
            "aggregation_policy": "minimum_across_registered_task_state_coordinates",
        },
        "power_contract": {
            "target_power": POWER_TARGET,
            "task_count_grid": POWER_TASK_COUNT_GRID,
            "standardized_effect_grid": STANDARDIZED_EFFECT_GRID,
            "monte_carlo_replicates": POWER_MONTE_CARLO_REPLICATES,
            "final_sample_size_policy": "freeze_only_after_nested_variance_observations",
        },
        "validation_objective_access": "forbidden",
        "authorization_objective_access": "forbidden",
        "gp_c_execution_allowed": False,
        "contribution_approximation_authorized": False,
        "production_authorization_eligible": False,
        "claim_boundary": (
            "This contract expands Development data and estimates variance and power only. "
            "It cannot evaluate GP-C, inspect Validation or Authorization, authorize "
            "Contribution, or update VTDO."
        ),
    }
    contract["contract_hash"] = canonical_hash(
        contract,
        prefix=DEVELOPMENT_CONTRACT_HASH_PREFIX,
    )
    verify_contract(contract)
    _write_json(output_path, contract)
    return contract


def verify_contract(value: Mapping[str, Any]) -> dict[str, Any]:
    frozen = dict(value)
    _replay_hash(
        frozen,
        field="contract_hash",
        prefix=DEVELOPMENT_CONTRACT_HASH_PREFIX,
    )
    expected = {
        "contract_version": DEVELOPMENT_CONTRACT_VERSION,
        "run_role": "development_variance_and_power_only",
        "validation_objective_access": "forbidden",
        "authorization_objective_access": "forbidden",
        "gp_c_execution_allowed": False,
        "contribution_approximation_authorized": False,
        "production_authorization_eligible": False,
    }
    for field, expected_value in expected.items():
        if frozen.get(field) != expected_value:
            raise ValueError(f"v22 Development contract differs:{field}")
    data = frozen.get("data_contract")
    if not isinstance(data, dict):
        raise ValueError("v22 Development data contract is missing")
    state_count = data.get("state_count")
    if (
        not isinstance(state_count, int)
        or state_count < (EXPECTED_TASK_COUNT * MINIMUM_STATES_PER_TASK)
        or state_count > (EXPECTED_TASK_COUNT * MAXIMUM_STATES_PER_TASK)
    ):
        raise ValueError("v22 Development state count differs")
    if data != {
        "task_count": EXPECTED_TASK_COUNT,
        "tasks_per_type": TASKS_PER_TYPE,
        "state_count": state_count,
        "minimum_states_per_task": MINIMUM_STATES_PER_TASK,
        "maximum_states_per_task": MAXIMUM_STATES_PER_TASK,
        "realizations_per_state": REALIZATIONS_PER_STATE,
        "objective_record_count": DEVELOPMENT_OBJECTIVE_RECORD_COUNT,
        "objective_micro_split_count": OBJECTIVE_MICRO_SPLIT_COUNT,
        "objective_records_per_micro_split": OBJECTIVE_RECORDS_PER_MICRO_SPLIT,
    }:
        raise ValueError("v22 Development data contract differs")
    for label, field in (
        ("population", "report_hash"),
        ("development_objective_support", "manifest_hash"),
        ("preflight", "report_hash"),
    ):
        item = frozen.get(label)
        if not isinstance(item, dict):
            raise ValueError(f"v22 contract input is missing:{label}")
        path = Path(str(item["path"])).resolve()
        if not path.is_file() or _sha256(path) != item.get("sha256"):
            raise ValueError(f"v22 contract input changed:{label}")
        if not item.get(field):
            raise ValueError(f"v22 contract input identity is missing:{label}")
    return frozen


def _normalize_contribution(value: float) -> float:
    epsilon = float(ENERGY_CONFIG["epsilon"])
    scaled = value / float(ENERGY_CONFIG["contribution_temperature"])
    if scaled >= 0:
        sigmoid = 1.0 / (1.0 + math.exp(-scaled))
    else:
        exponential = math.exp(scaled)
        sigmoid = exponential / (1.0 + exponential)
    return epsilon + (1.0 - 2.0 * epsilon) * sigmoid


def _next_probabilities(
    probabilities: Mapping[str, float],
    contributions: Mapping[str, float],
    *,
    reachability: Mapping[str, float] | None = None,
) -> dict[str, float]:
    if set(probabilities) != set(contributions) or not probabilities:
        raise ValueError("v22 MPE support differs")
    reachability_values = (
        {state_id: 1.0 for state_id in probabilities}
        if reachability is None
        else dict(reachability)
    )
    if set(reachability_values) != set(probabilities) or any(
        not 0 < float(value) <= 1 for value in reachability_values.values()
    ):
        raise ValueError("v22 MPE reachability support differs")
    coverage = 1.0 / len(probabilities)
    rho = float(ENERGY_CONFIG["history_kl_weight"]) / (
        float(ENERGY_CONFIG["history_kl_weight"]) + float(ENERGY_CONFIG["coverage_kl_weight"])
    )
    eta = 1.0 / (
        float(ENERGY_CONFIG["history_kl_weight"]) + float(ENERGY_CONFIG["coverage_kl_weight"])
    )
    values = {}
    for state_id, probability in probabilities.items():
        novelty = max(math.log(coverage / probability), 0.0)
        epsilon = float(ENERGY_CONFIG["epsilon"])
        normalized_novelty = epsilon + (1.0 - 2.0 * epsilon) * (
            1.0 - math.exp(-novelty / float(ENERGY_CONFIG["novelty_temperature"]))
        )
        normalized_reachability = max(
            float(ENERGY_CONFIG["reachability_floor"]),
            float(reachability_values[state_id]),
        )
        potential = (
            _normalize_contribution(contributions[state_id])
            ** float(ENERGY_CONFIG["contribution_weight"])
            * normalized_novelty ** float(ENERGY_CONFIG["novelty_weight"])
            * normalized_reachability ** float(ENERGY_CONFIG["reachability_weight"])
        )
        values[state_id] = (
            rho * math.log(probability)
            + (1.0 - rho) * math.log(coverage)
            + eta * math.log(potential)
        )
    maximum = max(values.values())
    unnormalized = {key: math.exp(value - maximum) for key, value in values.items()}
    total = sum(unnormalized.values())
    return {key: unnormalized[key] / total for key in sorted(unnormalized)}


def contribution_mpe_for_state(
    probabilities: Mapping[str, float],
    *,
    selected_state_id: str,
    reachability: Mapping[str, float] | None = None,
    target_probability_shift: float = TARGET_PROBABILITY_SHIFT,
) -> float:
    if selected_state_id not in probabilities:
        raise ValueError("v22 MPE selected state is outside the distribution")
    selected_probability = float(probabilities[selected_state_id])
    if not 0 < selected_probability < 1 or not 0 < target_probability_shift < 1:
        raise ValueError("v22 MPE inputs are invalid")
    baseline = _next_probabilities(
        probabilities,
        {state_id: 0.0 for state_id in probabilities},
        reachability=reachability,
    )

    def shift(selected_effect: float) -> float:
        other_effect = -selected_effect * selected_probability / (1.0 - selected_probability)
        contributions = {
            state_id: selected_effect if state_id == selected_state_id else other_effect
            for state_id in probabilities
        }
        updated = _next_probabilities(
            probabilities,
            contributions,
            reachability=reachability,
        )
        return abs(updated[selected_state_id] - baseline[selected_state_id])

    lower = 0.0
    upper = 1e-6
    while shift(upper) < target_probability_shift and upper < 100.0:
        upper *= 2.0
    if upper >= 100.0 and shift(upper) < target_probability_shift:
        raise ValueError("v22 MPE target shift is unattainable")
    for _ in range(80):
        middle = (lower + upper) / 2.0
        if shift(middle) >= target_probability_shift:
            upper = middle
        else:
            lower = middle
    return upper / (1.0 - selected_probability)


def standardized_power_grid(
    *,
    task_counts: Sequence[int] = POWER_TASK_COUNT_GRID,
    effect_sizes: Sequence[float] = STANDARDIZED_EFFECT_GRID,
    replicates: int = POWER_MONTE_CARLO_REPLICATES,
    seed: int = 20262200,
) -> tuple[dict[str, Any], ...]:
    if replicates < 1000 or any(count < len(REQUIRED_TASK_TYPES) for count in task_counts):
        raise ValueError("v22 power simulation contract is too small")
    rows = []
    for effect in effect_sizes:
        if effect <= 0:
            raise ValueError("v22 standardized effect must be positive")
        for task_count in task_counts:
            randomizer = random.Random(seed + task_count * 100 + round(effect * 1000))
            detected = 0
            for _ in range(replicates):
                values = [randomizer.gauss(effect, 1.0) for _ in range(task_count)]
                mean = statistics.fmean(values)
                standard_error = statistics.stdev(values) / math.sqrt(task_count)
                detected += int(mean - 1.96 * standard_error > 0)
            rows.append(
                {
                    "standardized_effect": effect,
                    "task_count": task_count,
                    "power": detected / replicates,
                    "target_power_reached": detected / replicates >= POWER_TARGET,
                }
            )
    return tuple(rows)


def _wilson(successes: int, attempts: int) -> tuple[float, float]:
    if attempts < 1 or not 0 <= successes <= attempts:
        raise ValueError("v22 Wilson inputs are invalid")
    z = 1.959963984540054
    proportion = successes / attempts
    denominator = 1.0 + z * z / attempts
    center = (proportion + z * z / (2.0 * attempts)) / denominator
    radius = (
        z
        * math.sqrt(proportion * (1.0 - proportion) / attempts + z * z / (4.0 * attempts**2))
        / denominator
    )
    return max(0.0, center - radius), min(1.0, center + radius)


def _telemetry(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    calls: list[dict[str, Any]] = []
    repair_count = 0
    for row in rows:
        audit = row.get("generation_audit")
        if not isinstance(audit, dict):
            continue
        repair_count += int(audit.get("contract_repair_count", 0))
        values = audit.get("telemetry", ())
        if isinstance(values, list):
            calls.extend(value for value in values if isinstance(value, dict))
    return {
        "api_call_count": len(calls),
        "http_success_count": sum(bool(row.get("http_success")) for row in calls),
        "json_contract_success_count": sum(bool(row.get("json_contract_success")) for row in calls),
        "prompt_tokens": sum(int(row.get("prompt_tokens") or 0) for row in calls),
        "completion_tokens": sum(int(row.get("completion_tokens") or 0) for row in calls),
        "total_tokens": sum(int(row.get("total_tokens") or 0) for row in calls),
        "estimated_cost": sum(float(row.get("estimated_cost") or 0.0) for row in calls),
        "contract_repair_count": repair_count,
        "models": dict(sorted(Counter(str(row.get("model_selected")) for row in calls).items())),
    }


def qualify_partial_initial_distribution(
    *,
    contract_path: Path,
    initial_report_path: Path,
    initial_records_path: Path,
    distributions_path: Path,
    output_path: Path,
) -> dict[str, Any]:
    if output_path.exists():
        raise ValueError("v22 initial qualification is immutable and already exists")
    contract = verify_contract(_read_json(contract_path))
    population = verify_population(_read_json(Path(str(contract["population"]["path"]))))
    report = FinanceInitialDistributionReport.model_validate(_read_json(initial_report_path))
    if report.status != "partial":
        raise ValueError("v22 qualification is only valid for a partial initial report")
    if report.artifact_sha256 != population["development_artifacts_sha256"]:
        raise ValueError("v22 partial initial report belongs to another population")
    if report.model_config_hash != contract["explorer"]["model_config_hash"]:
        raise ValueError("v22 partial initial report used another effective model config")
    if report.replicas_per_task != EXPLORER_REPLICAS_PER_TASK:
        raise ValueError("v22 partial initial report has another replica contract")
    if _sha256(initial_records_path) != report.trajectory_records_sha256:
        raise ValueError("v22 partial initial trajectory records changed")
    if _sha256(distributions_path) != report.distribution_sha256:
        raise ValueError("v22 partial initial distributions changed")

    artifacts = load_finance_multi_state_artifacts(
        Path(str(contract["population"]["artifacts_path"]))
    )
    artifacts_by_task = {_artifact_task_id(artifact): artifact for artifact in artifacts}
    task_ids = set(report.selected_task_ids)
    if task_ids != set(artifacts_by_task):
        raise ValueError("v22 partial initial task support differs")
    rows = _read_jsonl(initial_records_path)
    if len(rows) != report.requested_trajectory_count:
        raise ValueError("v22 partial initial record count differs")
    observation_ids = [str(row.get("observation_id") or "") for row in rows]
    if "" in observation_ids or len(set(observation_ids)) != len(observation_ids):
        raise ValueError("v22 partial initial observation identities are invalid")
    records_by_task: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        task_id = str(row.get("task_id") or "")
        if task_id not in artifacts_by_task:
            raise ValueError("v22 partial initial record references another task")
        if row.get("status") != "completed":
            raise ValueError("v22 partial initial record is incomplete")
        if not bool(row.get("validity_report", {}).get("valid")):
            raise ValueError("v22 partial initial record is invalid")
        state_id = str(row["state_assignment"]["state"]["state_id"])
        state_ids = set(_artifact_state_ids(artifacts_by_task[task_id]))
        if bool(row.get("catalog_hit")) != (state_id in state_ids):
            raise ValueError("v22 partial initial catalog assignment is inconsistent")
        records_by_task[task_id].append(row)
    if any(len(records_by_task[task_id]) != EXPLORER_REPLICAS_PER_TASK for task_id in task_ids):
        raise ValueError("v22 partial initial per-task support differs")
    observed_catalog_counts = {
        task_id: sum(row.get("catalog_hit") is True for row in records_by_task[task_id])
        for task_id in sorted(task_ids)
    }
    if observed_catalog_counts != report.valid_catalog_observation_counts:
        raise ValueError("v22 partial initial catalog counts changed")
    if sum(observed_catalog_counts.values()) != report.catalog_hit_count:
        raise ValueError("v22 partial initial catalog total changed")

    distributions = tuple(
        ConditionalTrajectoryDistribution.model_validate(row)
        for row in _read_jsonl(distributions_path)
    )
    if {item.task_condition_id for item in distributions} != task_ids:
        raise ValueError("v22 partial initial distributions cover another task set")
    full_support_count = 0
    for distribution in distributions:
        expected_states = set(
            _artifact_state_ids(artifacts_by_task[distribution.task_condition_id])
        )
        if set(distribution.probabilities) == expected_states and all(
            probability > 0 for probability in distribution.probabilities.values()
        ):
            full_support_count += 1
    if full_support_count != len(task_ids):
        raise ValueError("v22 partial initial distributions lost full support")

    observed_telemetry = _telemetry(rows)
    report_telemetry = report.telemetry
    telemetry_pairs = {
        "api_call_count": observed_telemetry["api_call_count"],
        "api_call_success_count": observed_telemetry["http_success_count"],
        "json_contract_success_count": observed_telemetry["json_contract_success_count"],
    }
    for field, value in telemetry_pairs.items():
        if int(report_telemetry.get(field) or 0) != value:
            raise ValueError(f"v22 partial initial telemetry changed:{field}")

    values: dict[str, Any] = {
        "use_case": "development_variance_and_power_only",
        "development_contract_hash": contract["contract_hash"],
        "development_contract_sha256": _sha256(contract_path),
        "materializer_model_config_hash": contract["materializer"]["model_config_hash"],
        "initial_distribution_report_id": report.report_id,
        "initial_distribution_report_sha256": _sha256(initial_report_path),
        "artifact_sha256": report.artifact_sha256,
        "distribution_sha256": report.distribution_sha256,
        "trajectory_records_sha256": report.trajectory_records_sha256,
        "selected_task_ids": tuple(sorted(task_ids)),
        "requested_trajectory_count": report.requested_trajectory_count,
        "valid_trajectory_count": report.valid_trajectory_count,
        "catalog_hit_count": report.catalog_hit_count,
        "off_catalog_valid_count": report.off_catalog_valid_count,
        "catalog_hit_rate": report.catalog_hit_count / report.valid_trajectory_count,
        "minimum_catalog_hits_per_task": min(observed_catalog_counts.values()),
        "required_minimum_catalog_hits_per_task": (MINIMUM_PARTIAL_INITIAL_CATALOG_HITS_PER_TASK),
        "required_minimum_catalog_hit_rate": (MINIMUM_PARTIAL_INITIAL_CATALOG_HIT_RATE),
        "full_support_distribution_count": full_support_count,
        **telemetry_pairs,
        "decision": "passed",
        "schema_version": "partial_initial_distribution_qualification.v2",
    }
    provisional = PartialInitialDistributionQualification.model_construct(
        qualification_id="pending",
        **values,
    )
    qualification = PartialInitialDistributionQualification(
        qualification_id=partial_initial_distribution_qualification_id(provisional),
        **values,
    )
    payload = qualification.model_dump(mode="json")
    _write_json(output_path, payload)
    return payload


def analyze_development_data(
    *,
    contract_path: Path,
    initial_report_path: Path,
    initial_qualification_path: Path | None,
    initial_records_path: Path,
    distributions_path: Path,
    realization_report_path: Path,
    materialization_reports_path: Path,
    generation_records_path: Path,
    output_path: Path,
) -> dict[str, Any]:
    if output_path.exists():
        raise ValueError("v22 Development analysis is immutable and already exists")
    contract = verify_contract(_read_json(contract_path))
    population = verify_population(_read_json(Path(str(contract["population"]["path"]))))
    task_ids = set(population["selected_task_ids"])
    initial = FinanceInitialDistributionReport.model_validate(_read_json(initial_report_path))
    qualification = (
        PartialInitialDistributionQualification.model_validate(
            _read_json(initial_qualification_path)
        )
        if initial_qualification_path is not None
        else None
    )
    if qualification is not None and (
        qualification.development_contract_hash != contract["contract_hash"]
        or qualification.development_contract_sha256 != _sha256(contract_path)
    ):
        raise ValueError("v22 initial qualification references another contract")
    realization = FinanceStateRealizationReport.model_validate(_read_json(realization_report_path))
    target_sha = population["development_artifacts_sha256"]
    if initial.artifact_sha256 != target_sha or realization.artifact_sha256 != target_sha:
        raise ValueError("v22 generated data belongs to another task population")
    validate_initial_distribution_lineage(
        initial,
        artifacts_path=Path(str(contract["population"]["artifacts_path"])),
        distributions_path=distributions_path,
        distributions={
            row.task_condition_id: row
            for row in (
                ConditionalTrajectoryDistribution.model_validate(value)
                for value in _read_jsonl(distributions_path)
            )
        },
        initial_report_path=initial_report_path,
        qualification=qualification,
    )
    if realization.status != "passed":
        raise ValueError("v22 generated data did not pass")
    if initial.replicas_per_task != EXPLORER_REPLICAS_PER_TASK:
        raise ValueError("v22 Explorer replica count differs")
    if set(initial.selected_task_ids) != task_ids:
        raise ValueError("v22 Explorer task support differs")
    expected_realizations = population["state_count"] * REALIZATIONS_PER_STATE
    if realization.released_realization_count != expected_realizations:
        raise ValueError("v22 state realization count differs")
    if _sha256(initial_report_path) != realization.initial_distribution_report_sha256:
        raise ValueError("v22 initial distribution report changed")
    expected_qualification_id = (
        qualification.qualification_id if qualification is not None else None
    )
    expected_qualification_sha = (
        _sha256(initial_qualification_path) if initial_qualification_path is not None else None
    )
    if (
        realization.initial_distribution_qualification_id != expected_qualification_id
        or realization.initial_distribution_qualification_sha256 != expected_qualification_sha
    ):
        raise ValueError("v22 initial distribution qualification lineage changed")
    if _sha256(initial_records_path) != initial.trajectory_records_sha256:
        raise ValueError("v22 initial Explorer records changed")
    distribution_sha256 = _sha256(distributions_path)
    if (
        distribution_sha256
        not in {
            initial.distribution_sha256,
            realization.distribution_sha256,
        }
        or initial.distribution_sha256 != realization.distribution_sha256
    ):
        raise ValueError("v22 initial distribution artifact changed")
    if _sha256(materialization_reports_path) != realization.materialization_reports_sha256:
        raise ValueError("v22 materialization reports changed")
    if _sha256(generation_records_path) != realization.generation_records_sha256:
        raise ValueError("v22 state-conditioned generation records changed")
    initial_rows = _read_jsonl(initial_records_path)
    if len(initial_rows) != EXPECTED_TASK_COUNT * EXPLORER_REPLICAS_PER_TASK:
        raise ValueError("v22 Explorer records are incomplete")
    distributions = tuple(
        ConditionalTrajectoryDistribution.model_validate(row)
        for row in _read_jsonl(distributions_path)
    )
    if {row.task_condition_id for row in distributions} != task_ids:
        raise ValueError("v22 initial distributions cover another task set")
    materializations = _read_jsonl(materialization_reports_path)
    if len(materializations) != EXPECTED_TASK_COUNT:
        raise ValueError("v22 materialization reports are incomplete")
    generation_rows = _read_jsonl(generation_records_path)
    natural_rows = []
    by_task: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in initial_rows:
        by_task[str(row["task_id"])].append(row)
    for task_id in sorted(task_ids):
        rows = by_task[task_id]
        if len(rows) != EXPLORER_REPLICAS_PER_TASK:
            raise ValueError("v22 per-task Explorer support differs")
        counts = Counter(
            str(row["state_assignment"]["state"]["state_id"])
            for row in rows
            if row.get("status") == "completed" and row.get("catalog_hit") is True
        )
        entropy = -sum(
            (count / len(rows)) * math.log(count / len(rows)) for count in counts.values()
        )
        intervals = {
            state_id: _wilson(count, len(rows)) for state_id, count in sorted(counts.items())
        }
        natural_rows.append(
            {
                "task_id": task_id,
                "attempt_count": len(rows),
                "valid_count": sum(
                    row.get("status") == "completed"
                    and bool(row.get("validity_report", {}).get("valid"))
                    for row in rows
                ),
                "catalog_hit_count": sum(row.get("catalog_hit") is True for row in rows),
                "observed_state_counts": dict(sorted(counts.items())),
                "state_entropy": entropy,
                "reachability_wilson_intervals": intervals,
            }
        )
    distribution_task_by_id = {row.distribution_id: row.task_condition_id for row in distributions}
    if len(distribution_task_by_id) != EXPECTED_TASK_COUNT:
        raise ValueError("v22 distribution identities are duplicated")
    transitions: defaultdict[tuple[str, str], Counter[str]] = defaultdict(Counter)
    attempted: Counter[tuple[str, str]] = Counter()
    released: Counter[tuple[str, str]] = Counter()
    off_target: Counter[tuple[str, str]] = Counter()
    failure_counts: Counter[str] = Counter()
    failure_counts_by_task: defaultdict[str, Counter[str]] = defaultdict(Counter)
    observed_distribution_ids: set[str] = set()
    for materialization in materializations:
        distribution_id = str(materialization["source_distribution_id"])
        task_id = distribution_task_by_id.get(distribution_id)
        if task_id is None or distribution_id in observed_distribution_ids:
            raise ValueError("v22 materialization task identity differs")
        observed_distribution_ids.add(distribution_id)
        for target, count in materialization["attempted_state_counts"].items():
            attempted[(task_id, str(target))] += int(count)
        for target, count in materialization["released_state_counts"].items():
            released[(task_id, str(target))] += int(count)
        for target, count in materialization["off_target_state_counts"].items():
            off_target[(task_id, str(target))] += int(count)
        for target, observed in materialization["observed_state_counts_by_target"].items():
            key = (task_id, str(target))
            for state_id, count in observed.items():
                transitions[key][str(state_id)] += int(count)
        task_failures = {
            str(key): int(value) for key, value in materialization.get("failure_counts", {}).items()
        }
        failure_counts.update(task_failures)
        failure_counts_by_task[task_id].update(task_failures)
    if observed_distribution_ids != set(distribution_task_by_id):
        raise ValueError("v22 materialization task coverage differs")
    conditioned_rows: list[dict[str, Any]] = []
    reachability_by_task: defaultdict[str, dict[str, float]] = defaultdict(dict)
    for task_id, state_id in sorted(attempted):
        key = (task_id, state_id)
        on_target = transitions[key][state_id]
        attempts = attempted[key]
        lower, upper = _wilson(on_target, attempts)
        posterior_mean = (on_target + 1.0) / (attempts + 2.0)
        reachability_by_task[task_id][state_id] = posterior_mean
        conditioned_rows.append(
            {
                "task_id": task_id,
                "target_state_id": state_id,
                "attempt_count": attempts,
                "released_count": released[key],
                "on_target_count": on_target,
                "off_target_count": off_target[key],
                "on_target_rate": on_target / attempts,
                "reachability_posterior_mean": posterior_mean,
                "on_target_wilson_interval": (lower, upper),
                "observed_state_counts": dict(sorted(transitions[key].items())),
            }
        )
    mpe_rows = []
    for distribution in sorted(distributions, key=lambda row: row.task_condition_id):
        task_reachability = reachability_by_task[distribution.task_condition_id]
        if set(task_reachability) != set(distribution.probabilities):
            raise ValueError("v22 MPE reachability support differs")
        for state_id in sorted(distribution.probabilities):
            mpe_rows.append(
                {
                    "task_id": distribution.task_condition_id,
                    "state_id": state_id,
                    "current_probability": distribution.probabilities[state_id],
                    "reachability_posterior_mean": task_reachability[state_id],
                    "minimum_practical_effect": contribution_mpe_for_state(
                        distribution.probabilities,
                        selected_state_id=state_id,
                        reachability=task_reachability,
                    ),
                }
            )
    mpe_values = [float(row["minimum_practical_effect"]) for row in mpe_rows]
    conditioned_attempt_count = sum(attempted.values())
    conditioned_on_target_count = sum(int(row["on_target_count"]) for row in conditioned_rows)
    if conditioned_attempt_count < 1:
        raise ValueError("v22 conditioned generation support is empty")
    explorer_telemetry = _telemetry(initial_rows)
    conditioned_telemetry = _telemetry(generation_rows)
    report: dict[str, Any] = {
        "report_version": DEVELOPMENT_REPORT_VERSION,
        "run_role": "development_variance_and_power_only",
        "contract": {
            "path": str(contract_path.resolve()),
            "sha256": _sha256(contract_path),
            "contract_hash": contract["contract_hash"],
        },
        "input_manifests": {
            "initial_report": {
                "path": str(initial_report_path.resolve()),
                "sha256": _sha256(initial_report_path),
                "report_id": initial.report_id,
            },
            "initial_qualification": (
                {
                    "path": str(initial_qualification_path.resolve()),
                    "sha256": _sha256(initial_qualification_path),
                    "qualification_id": qualification.qualification_id,
                }
                if initial_qualification_path is not None and qualification is not None
                else None
            ),
            "realization_report": {
                "path": str(realization_report_path.resolve()),
                "sha256": _sha256(realization_report_path),
                "report_id": realization.report_id,
            },
        },
        "task_count": EXPECTED_TASK_COUNT,
        "state_count": population["state_count"],
        "explorer_observation_count": len(initial_rows),
        "state_realization_count": realization.released_realization_count,
        "natural_distribution_rows": natural_rows,
        "mean_task_state_entropy": statistics.fmean(row["state_entropy"] for row in natural_rows),
        "conditioned_state_rows": conditioned_rows,
        "conditioned_attempt_count": conditioned_attempt_count,
        "conditioned_on_target_count": conditioned_on_target_count,
        "conditioned_on_target_rate": (conditioned_on_target_count / conditioned_attempt_count),
        "off_target_transition_matrix": {
            task_id: {
                target_state_id: dict(sorted(values.items()))
                for (row_task_id, target_state_id), values in sorted(transitions.items())
                if row_task_id == task_id
            }
            for task_id in sorted(task_ids)
        },
        "failure_counts": dict(sorted(failure_counts.items())),
        "failure_counts_by_task": {
            task_id: dict(sorted(values.items()))
            for task_id, values in sorted(failure_counts_by_task.items())
        },
        "explorer_telemetry": explorer_telemetry,
        "conditioned_telemetry": conditioned_telemetry,
        "mpe_rows": mpe_rows,
        "minimum_practical_effect": min(mpe_values),
        "median_practical_effect": statistics.median(mpe_values),
        "maximum_practical_effect": max(mpe_values),
        "target_probability_shift": TARGET_PROBABILITY_SHIFT,
        "standardized_power_sensitivity": standardized_power_grid(),
        "nested_variance_measurement_status": "pending_direct_target_measurements",
        "final_target_task_count_frozen": False,
        "validation_objective_access": "forbidden",
        "authorization_objective_access": "forbidden",
        "gp_c_evaluated": False,
        "contribution_approximation_authorized": False,
        "production_contribution": 0.0,
        "status": "data_ready_for_development_target_measurement",
        "claim_boundary": (
            "This report establishes data support, Explorer/realization uncertainty, an "
            "update-derived MPE, and a standardized power sensitivity grid. Final sample size "
            "remains unfrozen until nested target-effect variance is observed."
        ),
    }
    report["report_hash"] = canonical_hash(
        report,
        prefix=DEVELOPMENT_REPORT_HASH_PREFIX,
    )
    _write_json(output_path, report)
    return report


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build and analyze the Finance v22 Development power population"
    )
    commands = parser.add_subparsers(dest="command", required=True)
    population = commands.add_parser("select-population")
    population.add_argument("--source-report-path", required=True)
    population.add_argument("--source-artifacts-path", required=True)
    population.add_argument("--excluded-artifact-paths", nargs="*", default=())
    population.add_argument("--output-dir", required=True)
    support = commands.add_parser("freeze-support")
    support.add_argument("--population-report-path", required=True)
    support.add_argument("--source-artifacts-path", required=True)
    support.add_argument("--excluded-artifact-paths", nargs="*", default=())
    support.add_argument("--output-dir", required=True)
    preflight = commands.add_parser("preflight")
    preflight.add_argument("--repo-root", default=".")
    preflight.add_argument("--output-path", required=True)
    contract = commands.add_parser("prepare-contract")
    contract.add_argument("--population-report-path", required=True)
    contract.add_argument("--support-manifest-path", required=True)
    contract.add_argument("--preflight-path", required=True)
    contract.add_argument("--model-config-path", required=True)
    contract.add_argument("--materializer-model-config-path", required=True)
    contract.add_argument("--archive-config-path", required=True)
    contract.add_argument("--source-numeric-plan-path", required=True)
    contract.add_argument("--output-path", required=True)
    qualify = commands.add_parser("qualify-initial")
    qualify.add_argument("--contract-path", required=True)
    qualify.add_argument("--initial-report-path", required=True)
    qualify.add_argument("--initial-records-path", required=True)
    qualify.add_argument("--distributions-path", required=True)
    qualify.add_argument("--output-path", required=True)
    analyze = commands.add_parser("analyze-data")
    analyze.add_argument("--contract-path", required=True)
    analyze.add_argument("--initial-report-path", required=True)
    analyze.add_argument("--initial-qualification-path")
    analyze.add_argument("--initial-records-path", required=True)
    analyze.add_argument("--distributions-path", required=True)
    analyze.add_argument("--realization-report-path", required=True)
    analyze.add_argument("--materialization-reports-path", required=True)
    analyze.add_argument("--generation-records-path", required=True)
    analyze.add_argument("--output-path", required=True)
    return parser


def main() -> None:
    args = _parser().parse_args()
    if args.command == "select-population":
        value = select_population(
            source_report_path=Path(args.source_report_path).resolve(),
            source_artifacts_path=Path(args.source_artifacts_path).resolve(),
            excluded_artifact_paths=tuple(
                Path(path).resolve() for path in args.excluded_artifact_paths
            ),
            output_dir=Path(args.output_dir).resolve(),
        )
    elif args.command == "freeze-support":
        value = freeze_development_support(
            population_report_path=Path(args.population_report_path).resolve(),
            source_artifacts_path=Path(args.source_artifacts_path).resolve(),
            excluded_artifact_paths=tuple(
                Path(path).resolve() for path in args.excluded_artifact_paths
            ),
            output_dir=Path(args.output_dir).resolve(),
        )
    elif args.command == "preflight":
        value = run_preflight(
            repo_root=Path(args.repo_root).resolve(),
            output_path=Path(args.output_path).resolve(),
        )
    elif args.command == "prepare-contract":
        value = prepare_contract(
            population_report_path=Path(args.population_report_path).resolve(),
            support_manifest_path=Path(args.support_manifest_path).resolve(),
            preflight_path=Path(args.preflight_path).resolve(),
            model_config_path=Path(args.model_config_path).resolve(),
            materializer_model_config_path=Path(args.materializer_model_config_path).resolve(),
            archive_config_path=Path(args.archive_config_path).resolve(),
            source_numeric_plan_path=Path(args.source_numeric_plan_path).resolve(),
            output_path=Path(args.output_path).resolve(),
        )
    elif args.command == "qualify-initial":
        value = qualify_partial_initial_distribution(
            contract_path=Path(args.contract_path).resolve(),
            initial_report_path=Path(args.initial_report_path).resolve(),
            initial_records_path=Path(args.initial_records_path).resolve(),
            distributions_path=Path(args.distributions_path).resolve(),
            output_path=Path(args.output_path).resolve(),
        )
    else:
        value = analyze_development_data(
            contract_path=Path(args.contract_path).resolve(),
            initial_report_path=Path(args.initial_report_path).resolve(),
            initial_qualification_path=(
                Path(args.initial_qualification_path).resolve()
                if args.initial_qualification_path
                else None
            ),
            initial_records_path=Path(args.initial_records_path).resolve(),
            distributions_path=Path(args.distributions_path).resolve(),
            realization_report_path=Path(args.realization_report_path).resolve(),
            materialization_reports_path=Path(args.materialization_reports_path).resolve(),
            generation_records_path=Path(args.generation_records_path).resolve(),
            output_path=Path(args.output_path).resolve(),
        )
    print(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
