from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.experiments.vtdo_experiment.multistate import (
    FinanceTaskStateArtifact,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_agent_population import (
    FinanceAgentPopulationReport,
)
from trusted_synthesis.hashing import canonical_hash

FINANCE_AGENT_POPULATION_UNION_VERSION = "finance_agent_population_union.v1"


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class FinanceAgentPopulationUnionSource(FrozenModel):
    priority: int = Field(ge=0)
    artifact_sha256: str = Field(min_length=64, max_length=64)
    report_id: str = Field(min_length=1)
    source_schema_version: str = Field(min_length=1)
    source_status: str = Field(pattern="^(passed|partial)$")
    source_record_count: int = Field(ge=1)
    candidate_pool_id: str = Field(min_length=1)
    sampling_partition: str = Field(min_length=1)


class FinanceAgentPopulationUnionReport(FrozenModel):
    report_id: str = Field(min_length=1)
    kg_build_id: str = Field(min_length=1)
    archive_config_sha256: str = Field(min_length=64, max_length=64)
    sources: tuple[FinanceAgentPopulationUnionSource, ...] = Field(min_length=1)
    source_record_count: int = Field(ge=1)
    retained_record_count: int = Field(ge=1)
    dropped_record_count: int = Field(ge=0)
    retained_records_by_source_sha256: dict[str, int]
    dropped_records_by_source_sha256: dict[str, int]
    dropped_records_by_reason: dict[str, int]
    retained_public_evidence_version_count: int = Field(ge=1)
    retained_task_type_counts: dict[str, int]
    within_union_task_id_unique: bool
    within_union_artifact_id_unique: bool
    within_union_evidence_version_disjoint: bool
    artifact_sha256: str = Field(min_length=64, max_length=64)
    status: str = Field(pattern="^(passed|blocked)$")
    schema_version: str = FINANCE_AGENT_POPULATION_UNION_VERSION

    @model_validator(mode="after")
    def validate_report(self) -> FinanceAgentPopulationUnionReport:
        if tuple(source.priority for source in self.sources) != tuple(range(len(self.sources))):
            raise ValueError("source priorities must form a zero-based contiguous sequence")
        source_hashes = tuple(source.artifact_sha256 for source in self.sources)
        if len(set(source_hashes)) != len(source_hashes):
            raise ValueError("source population contents are duplicated")
        if self.source_record_count != sum(source.source_record_count for source in self.sources):
            raise ValueError("source record accounting is inconsistent")
        if self.source_record_count != self.retained_record_count + self.dropped_record_count:
            raise ValueError("union record accounting is inconsistent")
        if self.retained_record_count != sum(self.retained_records_by_source_sha256.values()):
            raise ValueError("retained source accounting is inconsistent")
        if self.dropped_record_count != sum(self.dropped_records_by_source_sha256.values()):
            raise ValueError("dropped source accounting is inconsistent")
        if self.dropped_record_count != sum(self.dropped_records_by_reason.values()):
            raise ValueError("drop-reason accounting is inconsistent")
        if set(self.retained_records_by_source_sha256) != set(source_hashes):
            raise ValueError("retained source keys are incomplete")
        if set(self.dropped_records_by_source_sha256) != set(source_hashes):
            raise ValueError("dropped source keys are incomplete")
        if not (
            self.within_union_task_id_unique
            and self.within_union_artifact_id_unique
            and self.within_union_evidence_version_disjoint
        ):
            raise ValueError("a published source union must be identity-disjoint")
        if self.status != "passed":
            raise ValueError("a non-empty identity-disjoint source union must pass")
        if self.report_id != finance_agent_population_union_report_id(self):
            raise ValueError("source union report identity is invalid")
        return self


def finance_agent_population_union_report_id(
    value: FinanceAgentPopulationUnionReport,
) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"report_id"}),
        prefix="finance_agent_population_union_report:",
    )


def build_finance_agent_population_union(
    *,
    source_artifact_paths: tuple[Path, ...],
    source_report_paths: tuple[Path, ...],
    output_dir: Path,
) -> FinanceAgentPopulationUnionReport:
    if not source_artifact_paths or len(source_artifact_paths) != len(source_report_paths):
        raise ValueError("source artifact and report paths must be non-empty and aligned")
    output_artifact_path = output_dir / "finance_agent_source_union.jsonl"
    output_report_path = output_dir / "finance_agent_source_union_report.json"
    if output_artifact_path.exists() or output_report_path.exists():
        raise ValueError("Finance Agent population union is immutable")
    resolved_artifacts = tuple(path.resolve() for path in source_artifact_paths)
    resolved_reports = tuple(path.resolve() for path in source_report_paths)
    if len(set(resolved_artifacts)) != len(resolved_artifacts):
        raise ValueError("source artifact paths are duplicated")
    if len(set(resolved_reports)) != len(resolved_reports):
        raise ValueError("source report paths are duplicated")

    sources: list[FinanceAgentPopulationUnionSource] = []
    source_records: list[tuple[str, tuple[FinanceTaskStateArtifact, ...]]] = []
    kg_build_ids: set[str] = set()
    archive_hashes: set[str] = set()
    for priority, (artifact_path, report_path) in enumerate(
        zip(resolved_artifacts, resolved_reports, strict=True)
    ):
        report = FinanceAgentPopulationReport.model_validate_json(
            report_path.read_text(encoding="utf-8")
        )
        if report.status == "blocked" or report.accepted_task_count < 1:
            raise ValueError("blocked or empty Agent population cannot enter a source union")
        artifact_sha256 = _sha256(artifact_path)
        if report.artifact_sha256 != artifact_sha256:
            raise ValueError("source Agent population artifact hash mismatch")
        records = _read_artifacts(artifact_path)
        if len(records) != report.accepted_task_count:
            raise ValueError("source Agent population record count mismatch")
        sources.append(
            FinanceAgentPopulationUnionSource(
                priority=priority,
                artifact_sha256=artifact_sha256,
                report_id=report.report_id,
                source_schema_version=report.schema_version,
                source_status=report.status,
                source_record_count=len(records),
                candidate_pool_id=report.candidate_pool_id,
                sampling_partition=report.sampling_partition,
            )
        )
        source_records.append((artifact_sha256, records))
        kg_build_ids.add(report.kg_build_id)
        archive_hashes.add(report.archive_config_sha256)
    if len(kg_build_ids) != 1 or len(archive_hashes) != 1:
        raise ValueError("source populations do not share one frozen KG and archive contract")

    retained_records, retained_by_source, dropped_by_source, dropped_by_reason = (
        _deduplicate_population_records(source_records)
    )
    if not retained_records:
        raise ValueError("source union has no records after identity de-duplication")
    retained = tuple(sorted(retained_records, key=lambda item: item.omega.task.task_id))
    _assert_union_identity_disjoint(retained)

    output_dir.mkdir(parents=True, exist_ok=True)
    _write_jsonl_atomic(
        output_artifact_path,
        (item.model_dump(mode="json") for item in retained),
    )
    evidence_version_ids = {
        evidence.evidence_version_id
        for item in retained
        for evidence in item.omega.public_corpus.evidence
    }
    report_values: dict[str, Any] = {
        "kg_build_id": next(iter(kg_build_ids)),
        "archive_config_sha256": next(iter(archive_hashes)),
        "sources": tuple(sources),
        "source_record_count": sum(source.source_record_count for source in sources),
        "retained_record_count": len(retained),
        "dropped_record_count": sum(dropped_by_reason.values()),
        "retained_records_by_source_sha256": dict(sorted(retained_by_source.items())),
        "dropped_records_by_source_sha256": dict(sorted(dropped_by_source.items())),
        "dropped_records_by_reason": dict(sorted(dropped_by_reason.items())),
        "retained_public_evidence_version_count": len(evidence_version_ids),
        "retained_task_type_counts": dict(
            sorted(Counter(item.omega.task.public.task_type for item in retained).items())
        ),
        "within_union_task_id_unique": True,
        "within_union_artifact_id_unique": True,
        "within_union_evidence_version_disjoint": True,
        "artifact_sha256": _sha256(output_artifact_path),
        "status": "passed",
        "schema_version": FINANCE_AGENT_POPULATION_UNION_VERSION,
    }
    provisional = FinanceAgentPopulationUnionReport.model_construct(
        report_id="pending", **report_values
    )
    report = FinanceAgentPopulationUnionReport(
        report_id=finance_agent_population_union_report_id(provisional),
        **report_values,
    )
    _write_json_atomic(
        output_report_path,
        report.model_dump(mode="json"),
    )
    return report


def _read_artifacts(path: Path) -> tuple[FinanceTaskStateArtifact, ...]:
    records: list[FinanceTaskStateArtifact] = []
    with path.open(encoding="utf-8") as source:
        for line_number, line in enumerate(source, start=1):
            if not line.strip():
                continue
            try:
                records.append(FinanceTaskStateArtifact.model_validate_json(line))
            except Exception as exc:
                raise ValueError(f"invalid source artifact at line {line_number}") from exc
    if not records:
        raise ValueError("source Agent population artifact is empty")
    return tuple(records)


def _deduplicate_population_records(
    sources: Iterable[tuple[str, tuple[FinanceTaskStateArtifact, ...]]],
) -> tuple[
    list[FinanceTaskStateArtifact],
    Counter[str],
    Counter[str],
    Counter[str],
]:
    retained: list[FinanceTaskStateArtifact] = []
    retained_by_source: Counter[str] = Counter()
    dropped_by_source: Counter[str] = Counter()
    dropped_by_reason: Counter[str] = Counter()
    task_ids: set[str] = set()
    artifact_ids: set[str] = set()
    evidence_version_ids: set[str] = set()
    for source_sha256, records in sources:
        retained_by_source[source_sha256] += 0
        dropped_by_source[source_sha256] += 0
        for item in records:
            task_id = item.omega.task.task_id
            artifact_id = item.artifact_id
            record_versions = tuple(
                evidence.evidence_version_id for evidence in item.omega.public_corpus.evidence
            )
            if not record_versions or len(record_versions) != len(set(record_versions)):
                raise ValueError("source record has empty or duplicated Evidence Versions")
            reason: str | None = None
            if artifact_id in artifact_ids:
                reason = "duplicate_artifact_id"
            elif task_id in task_ids:
                reason = "duplicate_task_id"
            elif evidence_version_ids.intersection(record_versions):
                reason = "public_evidence_version_overlap"
            if reason is not None:
                dropped_by_source[source_sha256] += 1
                dropped_by_reason[reason] += 1
                continue
            retained.append(item)
            retained_by_source[source_sha256] += 1
            task_ids.add(task_id)
            artifact_ids.add(artifact_id)
            evidence_version_ids.update(record_versions)
    return retained, retained_by_source, dropped_by_source, dropped_by_reason


def _assert_union_identity_disjoint(records: tuple[FinanceTaskStateArtifact, ...]) -> None:
    task_ids = [item.omega.task.task_id for item in records]
    artifact_ids = [item.artifact_id for item in records]
    evidence_versions = [
        evidence.evidence_version_id
        for item in records
        for evidence in item.omega.public_corpus.evidence
    ]
    if len(task_ids) != len(set(task_ids)):
        raise ValueError("source union contains a duplicated task identity")
    if len(artifact_ids) != len(set(artifact_ids)):
        raise ValueError("source union contains a duplicated artifact identity")
    if len(evidence_versions) != len(set(evidence_versions)):
        raise ValueError("source union contains overlapping public Evidence Versions")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_jsonl_atomic(path: Path, values: Iterable[dict[str, Any]]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as sink:
        for value in values:
            sink.write(json.dumps(value, ensure_ascii=False, sort_keys=True) + "\n")
    temporary.replace(path)


def _write_json_atomic(path: Path, value: dict[str, Any]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build an immutable, identity-disjoint Finance Agent source union"
    )
    parser.add_argument("--source-artifact-paths", nargs="+", required=True)
    parser.add_argument("--source-report-paths", nargs="+", required=True)
    parser.add_argument("--output-dir", required=True)
    return parser


def main() -> None:
    args = _parser().parse_args()
    report = build_finance_agent_population_union(
        source_artifact_paths=tuple(Path(value).resolve() for value in args.source_artifact_paths),
        source_report_paths=tuple(Path(value).resolve() for value in args.source_report_paths),
        output_dir=Path(args.output_dir).resolve(),
    )
    print(report.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
