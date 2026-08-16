from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict, deque
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.core.evidence.schema import EvidenceItem
from trusted_synthesis.domains.finance.adapter import FinanceArchiveAdapter
from trusted_synthesis.domains.finance.policy import FinanceSemanticPolicy
from trusted_synthesis.domains.finance.schema import FinanceArchiveConfig
from trusted_synthesis.experiments.vtdo_experiment.phase1_agent_evidence_union import (
    FINANCE_AGENT_EVIDENCE_UNION_ITEM_VERSION,
    FinanceAgentEvidenceUnionItem,
    finance_agent_evidence_union_item_id,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_agent_population_union import (
    _sha256,
    _write_json_atomic,
    _write_jsonl_atomic,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_sensitive_frontier import (
    _contiguous_windows,
    _periods_are_adjacent,
    _temporal_series,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_stopping_dual_estimand_protocol import (
    FinanceStoppingDualEstimandProtocol,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_stopping_shape_stability_protocol import (
    FrozenArtifactReference,
    _collect_excluded_identities,
)
from trusted_synthesis.hashing import canonical_hash

FINANCE_STOPPING_EVIDENCE_SNAPSHOT_VERSION: Literal["finance_stopping_evidence_snapshot.v2"] = (
    "finance_stopping_evidence_snapshot.v2"
)
FINANCE_STOPPING_EVIDENCE_SNAPSHOT_SELECTION_VERSION: Literal[
    "finance_stopping_evidence_snapshot_selection.v1"
] = "finance_stopping_evidence_snapshot_selection.v1"


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class FinanceStoppingEvidenceSnapshotThresholds(FrozenModel):
    minimum_selected_evidence_count: int = Field(default=1_000, ge=1)
    minimum_source_count: int = Field(default=3, ge=1)
    minimum_subject_count: int = Field(default=64, ge=1)
    minimum_predicate_count: int = Field(default=8, ge=1)
    minimum_disjoint_gold_window_capacity: int = Field(default=72, ge=48)
    minimum_contextual_pair_capacity: int = Field(default=24, ge=8)
    minimum_normalization_pair_capacity: int = Field(default=24, ge=8)


class FinanceStoppingEvidenceSnapshotReport(FrozenModel):
    report_id: str = Field(min_length=1)
    snapshot_id: str = Field(min_length=1)
    source_v25_38_protocol: FrozenArtifactReference
    source_v25_38_population: FrozenArtifactReference
    archive_config_path: str = Field(min_length=1)
    archive_config_sha256: str = Field(min_length=64, max_length=64)
    kg_build_id: str = Field(min_length=1)
    graph_schema_version: str = Field(min_length=1)
    selection_version: Literal["finance_stopping_evidence_snapshot_selection.v1"] = (
        FINANCE_STOPPING_EVIDENCE_SNAPSHOT_SELECTION_VERSION
    )
    selection_salt: str = Field(min_length=1)
    maximum_selected_evidence_count: int = Field(ge=1)
    maximum_scan_evidence_count: int = Field(ge=0)
    full_archive_scan: bool
    historical_reference_count: int = Field(ge=1)
    historical_population_references: tuple[FrozenArtifactReference, ...] = Field(min_length=1)
    historical_reference_manifest_hash: str = Field(min_length=1)
    excluded_evidence_id_count: int = Field(ge=0)
    excluded_evidence_version_count: int = Field(ge=0)
    scanned_evidence_count: int = Field(ge=1)
    excluded_occurrence_count: int = Field(ge=0)
    semantic_rejection_count: int = Field(ge=0)
    eligible_evidence_count: int = Field(ge=1)
    selected_evidence_count: int = Field(ge=1)
    selected_source_count: int = Field(ge=1)
    selected_subject_count: int = Field(ge=1)
    selected_predicate_count: int = Field(ge=1)
    selected_evidence_by_source: dict[str, int]
    temporal_series_count: int = Field(ge=1)
    contiguous_window_count: int = Field(ge=1)
    disjoint_gold_window_capacity: int = Field(ge=0)
    contextual_pair_capacity: int = Field(ge=0)
    normalization_pair_capacity: int = Field(ge=0)
    thresholds: FinanceStoppingEvidenceSnapshotThresholds
    historical_identity_disjoint: bool
    evidence_id_unique: bool
    evidence_version_id_unique: bool
    artifact_path: str = Field(min_length=1)
    artifact_sha256: str = Field(min_length=64, max_length=64)
    rejection_reasons: tuple[str, ...]
    status: Literal["passed", "blocked"]
    next_permitted_stage: Literal[
        "stopping_shape_policy_protocol_build",
        "evidence_snapshot_repair_only",
    ]
    schema_version: Literal["finance_stopping_evidence_snapshot.v2"] = (
        FINANCE_STOPPING_EVIDENCE_SNAPSHOT_VERSION
    )

    @model_validator(mode="after")
    def validate_report(self) -> FinanceStoppingEvidenceSnapshotReport:
        expected_status = "passed" if not self.rejection_reasons else "blocked"
        if self.status != expected_status:
            raise ValueError("Stopping Evidence Snapshot decision is inconsistent")
        expected_stage = (
            "stopping_shape_policy_protocol_build"
            if self.status == "passed"
            else "evidence_snapshot_repair_only"
        )
        if self.next_permitted_stage != expected_stage:
            raise ValueError("Stopping Evidence Snapshot transition is inconsistent")
        if self.selected_evidence_count != sum(self.selected_evidence_by_source.values()):
            raise ValueError("Stopping Evidence Snapshot source accounting is inconsistent")
        if self.historical_reference_count != len(self.historical_population_references):
            raise ValueError("Stopping Evidence Snapshot history count is inconsistent")
        if len({item.artifact_id for item in self.historical_population_references}) != len(
            self.historical_population_references
        ):
            raise ValueError("Stopping Evidence Snapshot history contains duplicates")
        if self.historical_reference_manifest_hash != canonical_hash(
            self.historical_population_references,
            prefix="finance_stopping_evidence_snapshot_history:",
        ):
            raise ValueError("Stopping Evidence Snapshot history identity is invalid")
        if self.report_id != finance_stopping_evidence_snapshot_report_id(self):
            raise ValueError("Stopping Evidence Snapshot report identity is invalid")
        return self


def finance_stopping_evidence_snapshot_report_id(
    value: FinanceStoppingEvidenceSnapshotReport,
) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"report_id"}),
        prefix="finance_stopping_evidence_snapshot_report:",
    )


def _population_identity_matches(payload: dict[str, object]) -> bool:
    population_id = payload.get("population_id")
    if not isinstance(population_id, str) or ":" not in population_id:
        return False
    prefix = population_id.rsplit(":", 1)[0] + ":"
    return population_id == canonical_hash(
        {key: value for key, value in payload.items() if key != "population_id"},
        prefix=prefix,
    )


def build_finance_stopping_evidence_snapshot(
    *,
    source_protocol_path: Path,
    source_population_path: Path,
    output_dir: Path,
    selection_salt: str,
    maximum_selected_evidence_count: int = 30_000,
    maximum_scan_evidence_count: int = 0,
    thresholds: FinanceStoppingEvidenceSnapshotThresholds | None = None,
    additional_historical_population_paths: tuple[Path, ...] = (),
) -> FinanceStoppingEvidenceSnapshotReport:
    output_path = output_dir / "finance_stopping_evidence_snapshot.jsonl"
    report_path = output_dir / "finance_stopping_evidence_snapshot_report.json"
    if output_path.exists() or report_path.exists():
        raise ValueError("Finance Stopping Evidence Snapshot is immutable")
    if maximum_selected_evidence_count < 1 or maximum_scan_evidence_count < 0:
        raise ValueError("Finance Stopping Evidence Snapshot limits are invalid")

    source_protocol_path = source_protocol_path.resolve()
    source_population_path = source_population_path.resolve()
    source_protocol = FinanceStoppingDualEstimandProtocol.model_validate_json(
        source_protocol_path.read_text(encoding="utf-8")
    )
    source_population_payload = json.loads(source_population_path.read_text(encoding="utf-8"))
    if not isinstance(source_population_payload, dict):
        raise ValueError("v25.38 Population is not a JSON object")
    source_population_id = source_population_payload.get("population_id")
    source_population_protocol_id = source_population_payload.get("protocol_id")
    source_population_schema = source_population_payload.get("schema_version")
    if (
        not isinstance(source_population_id, str)
        or not source_population_id.startswith("finance_stopping_dual_estimand_population:")
        or not _population_identity_matches(source_population_payload)
    ):
        raise ValueError("v25.38 Population identity is missing or malformed")
    if source_population_protocol_id != source_protocol.protocol_id:
        raise ValueError("v25.38 protocol and Population lineage is inconsistent")
    if source_population_schema != "finance_stopping_dual_estimand_population.v1":
        raise ValueError("v25.38 Population schema identity is unexpected")

    calibration_path = Path(source_protocol.source_calibration_contract.path).resolve()
    if _sha256(calibration_path) != source_protocol.source_calibration_contract.sha256:
        raise ValueError("v25.38 calibration contract content changed")
    calibration = json.loads(calibration_path.read_text(encoding="utf-8"))
    archive_config_path = Path(calibration["finance_archive_config_path"]).resolve()
    archive_config_sha256 = _sha256(archive_config_path)
    if archive_config_sha256 != calibration["finance_archive_config_sha256"]:
        raise ValueError("Finance Archive config differs from the frozen calibration contract")
    archive_config = FinanceArchiveConfig.from_json(archive_config_path)
    adapter = FinanceArchiveAdapter(archive_config)
    inspection = adapter.inspect()
    if not inspection["compatible"]:
        raise ValueError(f"Finance Archive is incompatible: {inspection['errors']}")

    population_reference = FrozenArtifactReference(
        artifact_id=source_population_id,
        path=str(source_population_path),
        sha256=_sha256(source_population_path),
    )
    additional_historical_references: list[FrozenArtifactReference] = []
    for path in additional_historical_population_paths:
        resolved = path.resolve()
        payload = json.loads(resolved.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("Additional historical Population is not a JSON object")
        population_id = payload.get("population_id")
        if (
            not isinstance(population_id, str)
            or not population_id
            or not _population_identity_matches(payload)
        ):
            raise ValueError("Additional historical Population identity is missing or invalid")
        additional_historical_references.append(
            FrozenArtifactReference(
                artifact_id=population_id,
                path=str(resolved),
                sha256=_sha256(resolved),
            )
        )
    historical_references = tuple(
        sorted(
            (
                *source_protocol.historical_population_references,
                population_reference,
                *additional_historical_references,
            ),
            key=lambda item: item.artifact_id,
        )
    )
    if len({item.artifact_id for item in historical_references}) != len(historical_references):
        raise ValueError("Stopping Evidence Snapshot historical references are duplicated")
    excluded = _collect_excluded_identities(historical_references)

    policy = FinanceSemanticPolicy()
    eligible: dict[str, EvidenceItem] = {}
    seen_versions: set[str] = set()
    scanned = 0
    excluded_occurrences = 0
    semantic_rejections = 0
    scan_limit = maximum_scan_evidence_count or None
    for item in adapter.iter_evidence(limit=scan_limit):
        scanned += 1
        if (
            item.evidence_id in excluded["evidence_id"]
            or item.evidence_version_id in excluded["evidence_version_id"]
        ):
            excluded_occurrences += 1
            continue
        if not policy.validate_evidence(item).passed:
            semantic_rejections += 1
            continue
        if item.evidence_id in eligible or item.evidence_version_id in seen_versions:
            raise ValueError("Finance Archive repeats a content-bound Evidence identity")
        eligible[item.evidence_id] = item
        seen_versions.add(item.evidence_version_id)
    if not eligible:
        raise ValueError("Finance Archive has no fresh semantically valid Evidence")

    selected = select_stopping_evidence_snapshot(
        tuple(eligible.values()),
        maximum_selected_evidence_count=maximum_selected_evidence_count,
        selection_salt=selection_salt,
    )
    capacity = stopping_evidence_snapshot_capacity(selected, selection_salt=selection_salt)
    threshold_contract = thresholds or FinanceStoppingEvidenceSnapshotThresholds()
    rejection_reasons = _snapshot_rejection_reasons(
        selected,
        capacity=capacity,
        thresholds=threshold_contract,
        excluded=excluded,
    )
    snapshot_id = canonical_hash(
        {
            "schema_version": FINANCE_STOPPING_EVIDENCE_SNAPSHOT_VERSION,
            "selection_version": FINANCE_STOPPING_EVIDENCE_SNAPSHOT_SELECTION_VERSION,
            "archive_config_sha256": archive_config_sha256,
            "kg_build_id": archive_config.required_kg_build_id,
            "historical_references": historical_references,
            "selection_salt": selection_salt,
            "maximum_selected_evidence_count": maximum_selected_evidence_count,
            "maximum_scan_evidence_count": maximum_scan_evidence_count,
            "evidence_version_ids": tuple(item.evidence_version_id for item in selected),
        },
        prefix="finance_stopping_evidence_snapshot:",
    )
    records = tuple(_snapshot_item(snapshot_id, item) for item in selected)
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_jsonl_atomic(
        output_path,
        (item.model_dump(mode="json") for item in records),
    )
    artifact_sha256 = _sha256(output_path)
    source_counts = Counter(item.source.source_id for item in selected)
    historical_disjoint = not (
        {item.evidence_id for item in selected} & excluded["evidence_id"]
        or {item.evidence_version_id for item in selected} & excluded["evidence_version_id"]
    )
    values = {
        "snapshot_id": snapshot_id,
        "source_v25_38_protocol": FrozenArtifactReference(
            artifact_id=source_protocol.protocol_id,
            path=str(source_protocol_path),
            sha256=_sha256(source_protocol_path),
        ),
        "source_v25_38_population": population_reference,
        "archive_config_path": str(archive_config_path),
        "archive_config_sha256": archive_config_sha256,
        "kg_build_id": archive_config.required_kg_build_id,
        "graph_schema_version": archive_config.required_graph_schema_version,
        "selection_salt": selection_salt,
        "maximum_selected_evidence_count": maximum_selected_evidence_count,
        "maximum_scan_evidence_count": maximum_scan_evidence_count,
        "full_archive_scan": maximum_scan_evidence_count == 0,
        "historical_reference_count": len(historical_references),
        "historical_population_references": historical_references,
        "historical_reference_manifest_hash": canonical_hash(
            historical_references,
            prefix="finance_stopping_evidence_snapshot_history:",
        ),
        "excluded_evidence_id_count": len(excluded["evidence_id"]),
        "excluded_evidence_version_count": len(excluded["evidence_version_id"]),
        "scanned_evidence_count": scanned,
        "excluded_occurrence_count": excluded_occurrences,
        "semantic_rejection_count": semantic_rejections,
        "eligible_evidence_count": len(eligible),
        "selected_evidence_count": len(selected),
        "selected_source_count": len(source_counts),
        "selected_subject_count": len({item.subject.subject_id for item in selected}),
        "selected_predicate_count": len({item.predicate for item in selected}),
        "selected_evidence_by_source": dict(sorted(source_counts.items())),
        **capacity,
        "thresholds": threshold_contract,
        "historical_identity_disjoint": historical_disjoint,
        "evidence_id_unique": len({item.evidence_id for item in selected}) == len(selected),
        "evidence_version_id_unique": (
            len({item.evidence_version_id for item in selected}) == len(selected)
        ),
        "artifact_path": str(output_path.resolve()),
        "artifact_sha256": artifact_sha256,
        "rejection_reasons": rejection_reasons,
        "status": "passed" if not rejection_reasons else "blocked",
        "next_permitted_stage": (
            "stopping_shape_policy_protocol_build"
            if not rejection_reasons
            else "evidence_snapshot_repair_only"
        ),
    }
    provisional = FinanceStoppingEvidenceSnapshotReport.model_construct(
        report_id="pending", **values
    )
    report = FinanceStoppingEvidenceSnapshotReport(
        report_id=finance_stopping_evidence_snapshot_report_id(provisional), **values
    )
    _write_json_atomic(report_path, report.model_dump(mode="json"))
    return report


def select_stopping_evidence_snapshot(
    evidence: tuple[EvidenceItem, ...],
    *,
    maximum_selected_evidence_count: int,
    selection_salt: str,
) -> tuple[EvidenceItem, ...]:
    """Select complete contiguous series, stratified by source and peer support."""

    series_values = _temporal_series(evidence)
    contextual_keys: dict[tuple[object, ...], set[str]] = defaultdict(set)
    for item in evidence:
        contextual_keys[_contextual_identity(item)].add(item.subject.subject_id)
    contextual_supported = {key for key, subjects in contextual_keys.items() if len(subjects) >= 2}
    chunks_by_source: dict[str, list[tuple[int, str, tuple[EvidenceItem, ...]]]] = defaultdict(list)
    for series in series_values:
        for chunk in _contiguous_chunks(series, maximum_length=6):
            if len(chunk) < 4:
                continue
            peer_priority = int(
                not any(_contextual_identity(item) in contextual_supported for item in chunk)
            )
            rank = canonical_hash(
                {
                    "selection_salt": selection_salt,
                    "evidence_versions": tuple(item.evidence_version_id for item in chunk),
                },
                prefix="finance_stopping_evidence_chunk_order:",
            )
            chunks_by_source[chunk[0].source.source_id].append((peer_priority, rank, chunk))
    queues = {
        source_id: deque(sorted(chunks, key=lambda row: (row[0], row[1])))
        for source_id, chunks in chunks_by_source.items()
    }
    selected: dict[str, EvidenceItem] = {}
    source_order = sorted(queues)
    while source_order and len(selected) < maximum_selected_evidence_count:
        next_sources: list[str] = []
        added = False
        for source_id in source_order:
            queue = queues[source_id]
            if not queue:
                continue
            _, _, chunk = queue.popleft()
            fresh = tuple(item for item in chunk if item.evidence_id not in selected)
            if fresh and len(selected) + len(fresh) <= maximum_selected_evidence_count:
                selected.update((item.evidence_id, item) for item in fresh)
                added = True
            if queue:
                next_sources.append(source_id)
        if not added and next_sources == source_order:
            break
        source_order = next_sources
    return tuple(sorted(selected.values(), key=lambda item: item.evidence_id))


def stopping_evidence_snapshot_capacity(
    evidence: tuple[EvidenceItem, ...],
    *,
    selection_salt: str,
) -> dict[str, int]:
    series_values = _temporal_series(evidence)
    windows = [window for series in series_values for window in _contiguous_windows(series, 3)]
    ordered_windows = sorted(
        windows,
        key=lambda window: canonical_hash(
            {
                "selection_salt": selection_salt,
                "versions": tuple(item.evidence_version_id for item in window),
            },
            prefix="finance_stopping_snapshot_window_capacity:",
        ),
    )
    used: set[str] = set()
    disjoint_windows = 0
    for window in ordered_windows:
        ids = {item.evidence_id for item in window}
        if ids & used:
            continue
        used.update(ids)
        disjoint_windows += 1
    return {
        "temporal_series_count": len(series_values),
        "contiguous_window_count": len(windows),
        "disjoint_gold_window_capacity": disjoint_windows,
        "contextual_pair_capacity": _single_mismatch_pair_capacity(evidence, "subject"),
        "normalization_pair_capacity": sum(
            _single_mismatch_pair_capacity(evidence, field)
            for field in ("period", "definition", "payload_context")
        ),
    }


def _single_mismatch_pair_capacity(evidence: tuple[EvidenceItem, ...], mismatch_field: str) -> int:
    grouped: dict[tuple[object, ...], Counter[object]] = defaultdict(Counter)
    for item in evidence:
        fields = _mismatch_identity_fields(item)
        if mismatch_field not in fields:
            raise ValueError("unknown one-dimensional mismatch field")
        grouped[tuple(value for field, value in fields.items() if field != mismatch_field)][
            fields[mismatch_field]
        ] += 1
    pair_count = 0
    for category_counts in grouped.values():
        total = sum(category_counts.values())
        largest_category = max(category_counts.values(), default=0)
        pair_count += min(total // 2, total - largest_category)
    return pair_count


def _mismatch_identity_fields(item: EvidenceItem) -> dict[str, object]:
    payload = item.payload
    return {
        "subject": item.subject.subject_id,
        "predicate": item.predicate,
        "period": (
            item.temporal_context.label,
            item.temporal_context.valid_from,
            item.temporal_context.valid_to,
            item.temporal_context.observed_at,
        ),
        "source": item.source.source_id,
        "definition": item.definition.definition_id,
        "payload_context": (
            getattr(payload, "unit", None),
            getattr(payload, "currency", None),
        ),
    }


def _snapshot_rejection_reasons(
    selected: tuple[EvidenceItem, ...],
    *,
    capacity: dict[str, int],
    thresholds: FinanceStoppingEvidenceSnapshotThresholds,
    excluded: dict[str, set[str]],
) -> tuple[str, ...]:
    values = {
        "selected_evidence_below_minimum": (
            len(selected) < thresholds.minimum_selected_evidence_count
        ),
        "source_breadth_below_minimum": (
            len({item.source.source_id for item in selected}) < thresholds.minimum_source_count
        ),
        "subject_breadth_below_minimum": (
            len({item.subject.subject_id for item in selected}) < thresholds.minimum_subject_count
        ),
        "predicate_breadth_below_minimum": (
            len({item.predicate for item in selected}) < thresholds.minimum_predicate_count
        ),
        "disjoint_gold_capacity_below_minimum": (
            capacity["disjoint_gold_window_capacity"]
            < thresholds.minimum_disjoint_gold_window_capacity
        ),
        "contextual_pair_capacity_below_minimum": (
            capacity["contextual_pair_capacity"] < thresholds.minimum_contextual_pair_capacity
        ),
        "normalization_pair_capacity_below_minimum": (
            capacity["normalization_pair_capacity"] < thresholds.minimum_normalization_pair_capacity
        ),
        "historical_identity_overlap": bool(
            {item.evidence_id for item in selected} & excluded["evidence_id"]
            or {item.evidence_version_id for item in selected} & excluded["evidence_version_id"]
        ),
    }
    return tuple(key for key, failed in values.items() if failed)


def _snapshot_item(snapshot_id: str, evidence: EvidenceItem) -> FinanceAgentEvidenceUnionItem:
    values = {
        "union_id": snapshot_id,
        "evidence": evidence,
        "source_artifact_ids": (snapshot_id,),
        "schema_version": FINANCE_AGENT_EVIDENCE_UNION_ITEM_VERSION,
    }
    provisional = FinanceAgentEvidenceUnionItem.model_construct(union_item_id="pending", **values)
    return FinanceAgentEvidenceUnionItem(
        union_item_id=finance_agent_evidence_union_item_id(provisional), **values
    )


def _contiguous_chunks(
    series: tuple[EvidenceItem, ...], *, maximum_length: int
) -> Iterable[tuple[EvidenceItem, ...]]:
    run: list[EvidenceItem] = []
    for item in series:
        if run and not _periods_are_adjacent(run[-1], item):
            yield from _split_run(tuple(run), maximum_length=maximum_length)
            run = []
        run.append(item)
    if run:
        yield from _split_run(tuple(run), maximum_length=maximum_length)


def _split_run(
    run: tuple[EvidenceItem, ...], *, maximum_length: int
) -> Iterable[tuple[EvidenceItem, ...]]:
    for start in range(0, len(run), maximum_length):
        chunk = run[start : start + maximum_length]
        if len(chunk) >= 4:
            yield chunk


def _contextual_identity(item: EvidenceItem) -> tuple[object, ...]:
    payload = item.payload
    unit = getattr(payload, "unit", None)
    currency = getattr(payload, "currency", None)
    temporal = item.temporal_context
    return (
        item.predicate,
        temporal.label,
        temporal.valid_from,
        temporal.valid_to,
        temporal.observed_at,
        item.source.source_id,
        item.definition.definition_id,
        unit,
        currency,
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build a capacity-audited immutable Finance Evidence Snapshot"
    )
    parser.add_argument("--source-protocol-path", required=True)
    parser.add_argument("--source-population-path", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--selection-salt", required=True)
    parser.add_argument("--maximum-selected-evidence-count", type=int, default=30_000)
    parser.add_argument("--maximum-scan-evidence-count", type=int, default=0)
    parser.add_argument(
        "--additional-historical-population",
        action="append",
        default=[],
        type=Path,
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    report = build_finance_stopping_evidence_snapshot(
        source_protocol_path=Path(args.source_protocol_path),
        source_population_path=Path(args.source_population_path),
        output_dir=Path(args.output_dir),
        selection_salt=args.selection_salt,
        maximum_selected_evidence_count=args.maximum_selected_evidence_count,
        maximum_scan_evidence_count=args.maximum_scan_evidence_count,
        additional_historical_population_paths=tuple(args.additional_historical_population),
    )
    print(report.model_dump_json(indent=2))
    return 0 if report.status == "passed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
