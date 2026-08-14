from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import math
from collections import Counter, defaultdict
from collections.abc import Sequence
from pathlib import Path
from statistics import fmean
from typing import Any

from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_mechanism_information_geometry import (  # noqa: E501
    CONFIRMED_MECHANISM_IDS,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_sensitive_frontier import (
    CAPABILITY_AXES,
    _symmetric_eigenvalues,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_submechanism_catalog import (  # noqa: E501
    make_candidate_specs,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_submechanism_direction_design import (  # noqa: E501
    CapabilitySubmechanismDirectionReport,
    CapabilitySubmechanismSpec,
    StructuralDirectionGate,
    StructuralDirectionGeometry,
    StructuralDirectionThresholds,
    _report_id,
)
from trusted_synthesis.hashing import canonical_hash


def structural_geometry(
    specs: Sequence[CapabilitySubmechanismSpec],
    *,
    thresholds: StructuralDirectionThresholds,
) -> StructuralDirectionGeometry:
    if not specs:
        raise ValueError("submechanism structural geometry has no tasks")
    raw_vectors = tuple(_normalize(item.raw_capability_demand) for item in specs)
    general = tuple(1 / math.sqrt(len(CAPABILITY_AXES)) for _ in CAPABILITY_AXES)
    residual_vectors = tuple(
        tuple(
            vector[index] - _dot(vector, general) * general[index]
            for index in range(len(CAPABILITY_AXES))
        )
        for vector in raw_vectors
    )
    raw_matrix = _second_moment(raw_vectors)
    residual_matrix = _second_moment(residual_vectors)
    raw_eigenvalues = _eigenvalues(raw_matrix)
    residual_eigenvalues = _eigenvalues(residual_matrix)
    positive = _positive_eigenvalues(residual_eigenvalues)
    cosines = tuple(
        _dot(left, right)
        for index, left in enumerate(raw_vectors)
        for right in raw_vectors[index + 1 :]
    )
    backbones = Counter(item.backbone_signature for item in specs)
    parent_support = {
        axis: len(
            {item.parent_mechanism_id for item in specs if item.raw_capability_demand[axis] >= 0.75}
        )
        for axis in CAPABILITY_AXES
    }
    return StructuralDirectionGeometry(
        task_count=len(specs),
        raw_matrix=raw_matrix,
        residual_matrix=residual_matrix,
        raw_eigenvalues=raw_eigenvalues,
        residual_eigenvalues=residual_eigenvalues,
        residual_numerical_rank=len(positive),
        residual_effective_rank=_effective_rank(positive),
        residual_condition_number=_condition_number(positive),
        regularized_log_determinant=sum(
            math.log(value + thresholds.regularization) for value in residual_eigenvalues
        ),
        minimum_positive_eigenvalue=min(positive, default=0.0),
        pairwise_cosine_mean=fmean(cosines) if cosines else 1.0,
        high_cosine_fraction=(
            sum(value >= thresholds.high_cosine_threshold for value in cosines) / len(cosines)
            if cosines
            else 1.0
        ),
        parent_support_per_axis=parent_support,
        distinct_backbone_count=len(backbones),
        maximum_backbone_share=max(backbones.values()) / len(specs),
    )


def select_submechanisms(
    candidates: Sequence[CapabilitySubmechanismSpec],
    *,
    thresholds: StructuralDirectionThresholds,
) -> tuple[CapabilitySubmechanismSpec, ...]:
    grouped: dict[str, list[CapabilitySubmechanismSpec]] = defaultdict(list)
    for item in candidates:
        grouped[item.parent_mechanism_id].append(item)
    if set(grouped) != set(CONFIRMED_MECHANISM_IDS):
        raise ValueError("submechanism candidates do not cover every confirmed parent")
    for parent, values in grouped.items():
        if len(values) != thresholds.candidates_per_parent:
            raise ValueError(f"submechanism candidate denominator changed for {parent}")
    option_groups = tuple(
        tuple(
            itertools.combinations(
                sorted(grouped[parent], key=lambda item: item.submechanism_id),
                thresholds.selected_per_parent,
            )
        )
        for parent in CONFIRMED_MECHANISM_IDS
    )
    best: tuple[CapabilitySubmechanismSpec, ...] | None = None
    best_key: tuple[float, ...] | None = None
    best_ids: tuple[str, ...] | None = None
    for choices in itertools.product(*option_groups):
        selected = tuple(item for choice in choices for item in choice)
        geometry = structural_geometry(selected, thresholds=thresholds)
        key = (
            float(
                min(geometry.parent_support_per_axis.values())
                >= thresholds.minimum_parent_support_per_axis
            ),
            float(min(geometry.parent_support_per_axis.values())),
            float(geometry.residual_numerical_rank),
            geometry.residual_effective_rank,
            -geometry.high_cosine_fraction,
            -geometry.residual_condition_number,
            geometry.regularized_log_determinant,
            geometry.minimum_positive_eigenvalue,
        )
        ids = tuple(item.submechanism_id for item in selected)
        if best_key is None or key > best_key or (key == best_key and ids < (best_ids or ())):
            best = selected
            best_key = key
            best_ids = ids
    if best is None:
        raise AssertionError("submechanism direction search produced no design")
    return best


def make_structural_gates(
    *,
    candidates: Sequence[CapabilitySubmechanismSpec],
    selected: Sequence[CapabilitySubmechanismSpec],
    geometry: StructuralDirectionGeometry,
    thresholds: StructuralDirectionThresholds,
) -> tuple[StructuralDirectionGate, ...]:
    candidate_counts = Counter(item.parent_mechanism_id for item in candidates)
    selected_counts = Counter(item.parent_mechanism_id for item in selected)
    diagnostic_counts = Counter(
        outcome for item in selected for outcome in item.diagnostic_outcomes
    )
    witnessed = all(
        item.capability_witnesses[axis]
        for item in selected
        for axis, value in item.raw_capability_demand.items()
        if value > 0
    )
    values: tuple[tuple[str, bool, float, str], ...] = (
        (
            "candidate_denominator",
            len(candidates) == len(CONFIRMED_MECHANISM_IDS) * thresholds.candidates_per_parent,
            float(len(candidates)),
            f"={len(CONFIRMED_MECHANISM_IDS) * thresholds.candidates_per_parent}",
        ),
        (
            "candidate_parent_balance",
            all(
                candidate_counts[parent] == thresholds.candidates_per_parent
                for parent in CONFIRMED_MECHANISM_IDS
            ),
            float(min(candidate_counts.values(), default=0)),
            f"={thresholds.candidates_per_parent}",
        ),
        (
            "selected_denominator",
            len(selected) == len(CONFIRMED_MECHANISM_IDS) * thresholds.selected_per_parent,
            float(len(selected)),
            f"={len(CONFIRMED_MECHANISM_IDS) * thresholds.selected_per_parent}",
        ),
        (
            "selected_parent_balance",
            all(
                selected_counts[parent] == thresholds.selected_per_parent
                for parent in CONFIRMED_MECHANISM_IDS
            ),
            float(min(selected_counts.values(), default=0)),
            f"={thresholds.selected_per_parent}",
        ),
        (
            "residual_structural_rank",
            geometry.residual_numerical_rank >= thresholds.minimum_residual_rank,
            float(geometry.residual_numerical_rank),
            f">={thresholds.minimum_residual_rank}",
        ),
        (
            "residual_structural_effective_rank",
            geometry.residual_effective_rank >= thresholds.minimum_residual_effective_rank,
            geometry.residual_effective_rank,
            f">={thresholds.minimum_residual_effective_rank}",
        ),
        (
            "residual_structural_condition_number",
            geometry.residual_condition_number <= thresholds.maximum_residual_condition_number,
            geometry.residual_condition_number,
            f"<={thresholds.maximum_residual_condition_number}",
        ),
        (
            "pairwise_demand_cosine",
            geometry.high_cosine_fraction <= thresholds.maximum_high_cosine_fraction,
            geometry.high_cosine_fraction,
            f"<={thresholds.maximum_high_cosine_fraction}",
        ),
        (
            "cross_parent_axis_support",
            min(geometry.parent_support_per_axis.values())
            >= thresholds.minimum_parent_support_per_axis,
            float(min(geometry.parent_support_per_axis.values())),
            f">={thresholds.minimum_parent_support_per_axis}",
        ),
        (
            "distinct_workflow_backbones",
            geometry.distinct_backbone_count >= thresholds.minimum_distinct_backbones,
            float(geometry.distinct_backbone_count),
            f">={thresholds.minimum_distinct_backbones}",
        ),
        (
            "workflow_backbone_dominance",
            geometry.maximum_backbone_share <= thresholds.maximum_backbone_share,
            geometry.maximum_backbone_share,
            f"<={thresholds.maximum_backbone_share}",
        ),
        (
            "typed_capability_witnesses",
            witnessed,
            float(witnessed),
            "=1",
        ),
        (
            "multi_output_diagnostic_coverage",
            set(diagnostic_counts) == {"tool", "verification", "recovery", "stopping"},
            float(len(diagnostic_counts)),
            "=4",
        ),
    )
    return tuple(
        StructuralDirectionGate(
            gate_id=gate_id,
            observed=observed,
            requirement=requirement,
            passed=passed,
        )
        for gate_id, passed, observed, requirement in values
    )


def run_direction_design(
    *,
    source_geometry_report_path: Path,
    output_dir: Path,
    run_id: str,
    thresholds: StructuralDirectionThresholds | None = None,
) -> CapabilitySubmechanismDirectionReport:
    output_path = output_dir / "finance_capability_submechanism_direction_report.json"
    if output_path.exists():
        raise ValueError("submechanism direction report is immutable")
    source = _load_source_geometry_report(source_geometry_report_path)
    active_thresholds = thresholds or StructuralDirectionThresholds()
    candidates = make_candidate_specs()
    selected = select_submechanisms(candidates, thresholds=active_thresholds)
    geometry = structural_geometry(selected, thresholds=active_thresholds)
    gates = make_structural_gates(
        candidates=candidates,
        selected=selected,
        geometry=geometry,
        thresholds=active_thresholds,
    )
    structural_ready = all(item.passed for item in gates)
    selected_ids = {item.submechanism_id for item in selected}
    executable = tuple(
        item.submechanism_id
        for item in candidates
        if item.submechanism_id in selected_ids
        and item.runtime_contract.implementation_status == "host_and_materializer_implemented"
    )
    runtime_ready = structural_ready and len(executable) == len(selected)
    failures = [item.gate_id for item in gates if not item.passed]
    if structural_ready and not runtime_ready:
        failures.append("runtime_implementation_coverage")
    next_stage = (
        "flash_submechanism_development"
        if runtime_ready
        else (
            "submechanism_runtime_implementation_only"
            if structural_ready
            else "submechanism_direction_redesign_only"
        )
    )
    manifest = _implementation_manifest()
    values = {
        "run_id": run_id,
        "source_geometry_report_path": str(source_geometry_report_path.resolve()),
        "source_geometry_report_sha256": _sha256(source_geometry_report_path),
        "source_geometry_report_id": str(source["report_id"]),
        "candidate_specs": candidates,
        "selected_submechanism_ids": tuple(item.submechanism_id for item in selected),
        "selected_geometry": geometry,
        "executable_selected_submechanism_ids": executable,
        "gates": gates,
        "structural_geometry_ready": structural_ready,
        "runtime_population_ready": runtime_ready,
        "multi_output_diagnostic_preregistered": True,
        "failure_codes": tuple(failures),
        "next_permitted_stage": next_stage,
        "implementation_manifest": manifest,
        "implementation_manifest_hash": canonical_hash(
            manifest,
            prefix="finance_capability_submechanism_implementation:",
        ),
    }
    provisional = CapabilitySubmechanismDirectionReport.model_construct(
        report_id="pending", **values
    )
    report = CapabilitySubmechanismDirectionReport(report_id=_report_id(provisional), **values)
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_json_atomic(
        output_dir / "finance_capability_submechanism_candidate_catalog.json",
        [item.model_dump(mode="json") for item in candidates],
    )
    _write_json_atomic(output_path, report.model_dump(mode="json"))
    _write_text_atomic(
        output_dir / "finance_capability_submechanism_direction_report.md",
        render_direction_report(report),
    )
    return report


def _load_source_geometry_report(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("v25.23 source geometry report is malformed")
    if tuple(payload.get("confirmed_mechanism_ids", ())) != CONFIRMED_MECHANISM_IDS:
        raise ValueError("v25.24 source changes the confirmed mechanism set")
    if payload.get("information_geometry_ready") is not False:
        raise ValueError("v25.24 requires the blocked v25.23 geometry source")
    if payload.get("next_permitted_stage") != "capability_mechanism_support_redesign_only":
        raise ValueError("v25.24 source did not authorize support redesign")
    required_failures = {
        "raw_effective_rank",
        "raw_condition_number",
        "residual_numerical_rank",
        "residual_effective_rank",
    }
    if set(payload.get("failure_codes", ())) != required_failures:
        raise ValueError("v25.24 source failure diagnosis differs from the frozen audit")
    return payload


def render_direction_report(report: CapabilitySubmechanismDirectionReport) -> str:
    geometry = report.selected_geometry
    selected = set(report.selected_submechanism_ids)
    lines = [
        "# Finance v25.24 Submechanism Direction Design",
        "",
        "## Scientific status",
        "",
        f"- Structural geometry ready: `{str(report.structural_geometry_ready).lower()}`",
        f"- Runtime population ready: `{str(report.runtime_population_ready).lower()}`",
        f"- Next permitted stage: `{report.next_permitted_stage}`",
        "- Flash/Pro/API calls: `0`; GPU jobs: `0`.",
        "- Beneficiary, Exact Target, GP-C, and production Contribution remain forbidden.",
        "",
        "## Structural geometry",
        "",
        f"- Selected tasks: {geometry.task_count}",
        f"- Residual numerical rank: {geometry.residual_numerical_rank}",
        f"- Residual effective rank: {geometry.residual_effective_rank:.6f}",
        f"- Residual condition number: {geometry.residual_condition_number:.6f}",
        f"- High-cosine pair fraction: {geometry.high_cosine_fraction:.6f}",
        f"- Mean pairwise demand cosine: {geometry.pairwise_cosine_mean:.6f}",
        f"- Distinct backbones: {geometry.distinct_backbone_count}",
        "- Executable selected variants: "
        f"{len(report.executable_selected_submechanism_ids)}/{len(selected)}",
        "",
        "## Gates",
        "",
        "| Gate | Observed | Requirement | Passed |",
        "| --- | ---: | ---: | :---: |",
    ]
    lines.extend(
        f"| `{gate.gate_id}` | {gate.observed:.6f} | {gate.requirement} | "
        f"{'yes' if gate.passed else 'no'} |"
        for gate in report.gates
    )
    lines.extend(
        (
            "",
            "## Selected submechanisms",
            "",
            "| Parent | Submechanism | Runtime |",
            "| --- | --- | --- |",
        )
    )
    lines.extend(
        f"| `{item.parent_mechanism_id}` | `{item.submechanism_id}` | "
        f"`{item.runtime_contract.implementation_status}` |"
        for item in report.candidate_specs
        if item.submechanism_id in selected
    )
    lines.extend(
        (
            "",
            "## Interpretation",
            "",
            "The structural matrix is computed before observing any model response. Capability "
            "demands are recomputed from typed action primitives and Evidence dependencies; "
            "submechanism names do not contribute to the vector.",
            "",
            "Passing structural geometry does not authorize Flash by itself. Every selected "
            "variant must first obtain a distinct Host intervention and real-Finance "
            "Materializer implementation. The preregistered tool/verification/recovery/stopping "
            "outputs remain diagnostic and cannot rescue the primary `valid_success` matrix.",
            "",
        )
    )
    return "\n".join(lines)


def _normalize(values: dict[str, float]) -> tuple[float, ...]:
    vector = tuple(float(values[axis]) for axis in CAPABILITY_AXES)
    norm = math.sqrt(_dot(vector, vector))
    if norm <= 0:
        raise ValueError("submechanism structural demand is empty")
    return tuple(value / norm for value in vector)


def _dot(left: Sequence[float], right: Sequence[float]) -> float:
    return sum(a * b for a, b in zip(left, right, strict=True))


def _second_moment(values: Sequence[Sequence[float]]) -> tuple[tuple[float, ...], ...]:
    size = len(values[0])
    return tuple(
        tuple(
            sum(value[row] * value[column] for value in values) / len(values)
            for column in range(size)
        )
        for row in range(size)
    )


def _eigenvalues(matrix: Sequence[Sequence[float]]) -> tuple[float, ...]:
    values = sorted(_symmetric_eigenvalues([list(row) for row in matrix]), reverse=True)
    return tuple(0.0 if abs(value) <= 1e-15 else max(0.0, value) for value in values)


def _positive_eigenvalues(values: Sequence[float]) -> tuple[float, ...]:
    maximum = max(values, default=0.0)
    tolerance = max(1e-12, maximum * 1e-6)
    return tuple(value for value in values if maximum > tolerance and value > tolerance)


def _effective_rank(values: Sequence[float]) -> float:
    total = sum(values)
    if total <= 0:
        return 0.0
    probabilities = tuple(value / total for value in values)
    return math.exp(-sum(value * math.log(value) for value in probabilities if value > 0))


def _condition_number(values: Sequence[float]) -> float:
    return values[0] / values[-1] if values else 1e12


def _implementation_manifest() -> dict[str, str]:
    root = Path(__file__).resolve().parents[4]
    relative_paths = (
        "src/trusted_synthesis/experiments/vtdo_experiment/phase1_capability_submechanism_direction_design.py",
        "src/trusted_synthesis/experiments/vtdo_experiment/phase1_capability_submechanism_catalog.py",
        "src/trusted_synthesis/experiments/vtdo_experiment/phase1_capability_submechanism_direction_runner.py",
        "src/trusted_synthesis/experiments/vtdo_experiment/phase1_capability_mechanism_information_geometry.py",
    )
    return {path: _sha256(root / path) for path in relative_paths}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_json_atomic(path: Path, value: Any) -> None:
    _write_text_atomic(path, json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def _write_text_atomic(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(value, encoding="utf-8")
    temporary.replace(path)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the model-free v25.24 submechanism direction-design experiment."
    )
    parser.add_argument("--source-geometry-report", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--run-id", required=True)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    report = run_direction_design(
        source_geometry_report_path=args.source_geometry_report,
        output_dir=args.output_dir,
        run_id=args.run_id,
    )
    print(
        json.dumps(
            {
                "report_id": report.report_id,
                "structural_geometry_ready": report.structural_geometry_ready,
                "runtime_population_ready": report.runtime_population_ready,
                "failure_codes": report.failure_codes,
                "next_permitted_stage": report.next_permitted_stage,
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
