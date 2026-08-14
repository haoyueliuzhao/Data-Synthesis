from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.core.evidence.schema import EvidenceItem
from trusted_synthesis.experiments.vtdo_experiment.multistate import (
    FinanceTaskStateArtifact,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_agent_population import (
    FinanceAgentPopulationReport,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_agent_population_union import (
    FinanceAgentPopulationUnionSource,
    _read_artifacts,
    _sha256,
    _write_json_atomic,
    _write_jsonl_atomic,
)
from trusted_synthesis.hashing import canonical_hash

FINANCE_AGENT_EVIDENCE_UNION_VERSION = "finance_agent_evidence_union.v1"
FINANCE_AGENT_EVIDENCE_UNION_ITEM_VERSION = "finance_agent_evidence_union_item.v1"


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class FinanceAgentEvidenceUnionItem(FrozenModel):
    union_item_id: str = Field(min_length=1)
    union_id: str = Field(min_length=1)
    evidence: EvidenceItem
    source_artifact_ids: tuple[str, ...] = Field(min_length=1)
    schema_version: str = FINANCE_AGENT_EVIDENCE_UNION_ITEM_VERSION

    @model_validator(mode="after")
    def validate_item(self) -> FinanceAgentEvidenceUnionItem:
        if tuple(sorted(set(self.source_artifact_ids))) != self.source_artifact_ids:
            raise ValueError("Evidence-union source artifacts are not unique and sorted")
        if self.union_item_id != finance_agent_evidence_union_item_id(self):
            raise ValueError("Evidence-union item identity is invalid")
        return self


class FinanceAgentEvidenceUnionReport(FrozenModel):
    report_id: str = Field(min_length=1)
    union_id: str = Field(min_length=1)
    kg_build_id: str = Field(min_length=1)
    archive_config_sha256: str = Field(min_length=64, max_length=64)
    sources: tuple[FinanceAgentPopulationUnionSource, ...] = Field(min_length=1)
    source_record_count: int = Field(ge=1)
    source_artifact_count: int = Field(ge=1)
    public_evidence_occurrence_count: int = Field(ge=1)
    retained_evidence_count: int = Field(ge=1)
    duplicate_occurrence_count: int = Field(ge=0)
    superseded_version_occurrence_count: int = Field(ge=0)
    conflicting_content_count: int = Field(ge=0)
    contributing_artifact_count: int = Field(ge=1)
    evidence_count_by_source_sha256: dict[str, int]
    evidence_id_unique: bool
    evidence_version_id_unique: bool
    content_bound_duplicate_consistent: bool
    artifact_sha256: str = Field(min_length=64, max_length=64)
    status: str = Field(pattern="^(passed|blocked)$")
    schema_version: str = FINANCE_AGENT_EVIDENCE_UNION_VERSION

    @model_validator(mode="after")
    def validate_report(self) -> FinanceAgentEvidenceUnionReport:
        source_hashes = tuple(source.artifact_sha256 for source in self.sources)
        if tuple(source.priority for source in self.sources) != tuple(range(len(self.sources))):
            raise ValueError("Evidence-union priorities are invalid")
        if len(source_hashes) != len(set(source_hashes)):
            raise ValueError("Evidence-union source contents are duplicated")
        if self.source_record_count != sum(source.source_record_count for source in self.sources):
            raise ValueError("Evidence-union source record accounting is inconsistent")
        if set(self.evidence_count_by_source_sha256) != set(source_hashes):
            raise ValueError("Evidence-union source contribution keys are incomplete")
        if sum(self.evidence_count_by_source_sha256.values()) != self.retained_evidence_count:
            raise ValueError("Evidence-union source contribution accounting is inconsistent")
        if self.contributing_artifact_count > self.source_artifact_count:
            raise ValueError("Evidence-union contributing artifact accounting is inconsistent")
        if self.public_evidence_occurrence_count != (
            self.retained_evidence_count
            + self.duplicate_occurrence_count
            + self.superseded_version_occurrence_count
        ):
            raise ValueError("Evidence-union occurrence accounting is inconsistent")
        if self.conflicting_content_count != 0:
            raise ValueError("Evidence-union contains a content-bound identity conflict")
        if not (
            self.evidence_id_unique
            and self.evidence_version_id_unique
            and self.content_bound_duplicate_consistent
        ):
            raise ValueError("Evidence-union identities are not publishable")
        if self.status != "passed":
            raise ValueError("a non-empty consistent Evidence union must pass")
        if self.report_id != finance_agent_evidence_union_report_id(self):
            raise ValueError("Evidence-union report identity is invalid")
        return self


def finance_agent_evidence_union_item_id(value: FinanceAgentEvidenceUnionItem) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"union_item_id"}),
        prefix="finance_agent_evidence_union_item:",
    )


def finance_agent_evidence_union_report_id(value: FinanceAgentEvidenceUnionReport) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"report_id"}),
        prefix="finance_agent_evidence_union_report:",
    )


def build_finance_agent_evidence_union(
    *,
    source_artifact_paths: tuple[Path, ...],
    source_report_paths: tuple[Path, ...],
    output_dir: Path,
) -> FinanceAgentEvidenceUnionReport:
    if not source_artifact_paths or len(source_artifact_paths) != len(source_report_paths):
        raise ValueError("source artifact and report paths must be non-empty and aligned")
    output_path = output_dir / "finance_agent_evidence_union.jsonl"
    report_path = output_dir / "finance_agent_evidence_union_report.json"
    if output_path.exists() or report_path.exists():
        raise ValueError("Finance Agent Evidence union is immutable")

    sources: list[FinanceAgentPopulationUnionSource] = []
    source_records: list[tuple[str, tuple[FinanceTaskStateArtifact, ...]]] = []
    source_hashes: set[str] = set()
    kg_build_ids: set[str] = set()
    archive_hashes: set[str] = set()
    for priority, (artifact_path, source_report_path) in enumerate(
        zip(source_artifact_paths, source_report_paths, strict=True)
    ):
        artifact_path = artifact_path.resolve()
        source_report_path = source_report_path.resolve()
        report = FinanceAgentPopulationReport.model_validate_json(
            source_report_path.read_text(encoding="utf-8")
        )
        if report.status == "blocked" or report.accepted_task_count < 1:
            raise ValueError("blocked or empty Agent population cannot supply Evidence")
        artifact_sha256 = _sha256(artifact_path)
        if artifact_sha256 in source_hashes:
            raise ValueError("Evidence-union source contents are duplicated")
        if report.artifact_sha256 != artifact_sha256:
            raise ValueError("source Agent population artifact hash mismatch")
        records = _read_artifacts(artifact_path)
        if len(records) != report.accepted_task_count:
            raise ValueError("source Agent population record count mismatch")
        source_hashes.add(artifact_sha256)
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
        raise ValueError("Evidence sources do not share one frozen KG and archive contract")

    union_id = canonical_hash(
        {
            "schema_version": FINANCE_AGENT_EVIDENCE_UNION_VERSION,
            "sources": tuple(sources),
            "kg_build_id": next(iter(kg_build_ids)),
            "archive_config_sha256": next(iter(archive_hashes)),
        },
        prefix="finance_agent_evidence_union:",
    )
    (
        items,
        source_artifact_count,
        occurrence_count,
        duplicate_count,
        superseded_count,
        contribution_counts,
    ) = _merge_evidence_sources(source_records, union_id=union_id)
    if not items:
        raise ValueError("Evidence union is empty")
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_jsonl_atomic(output_path, (item.model_dump(mode="json") for item in items))
    contributing_artifacts = {
        artifact_id for item in items for artifact_id in item.source_artifact_ids
    }
    report_values: dict[str, Any] = {
        "union_id": union_id,
        "kg_build_id": next(iter(kg_build_ids)),
        "archive_config_sha256": next(iter(archive_hashes)),
        "sources": tuple(sources),
        "source_record_count": sum(source.source_record_count for source in sources),
        "source_artifact_count": source_artifact_count,
        "public_evidence_occurrence_count": occurrence_count,
        "retained_evidence_count": len(items),
        "duplicate_occurrence_count": duplicate_count,
        "superseded_version_occurrence_count": superseded_count,
        "conflicting_content_count": 0,
        "contributing_artifact_count": len(contributing_artifacts),
        "evidence_count_by_source_sha256": dict(sorted(contribution_counts.items())),
        "evidence_id_unique": True,
        "evidence_version_id_unique": True,
        "content_bound_duplicate_consistent": True,
        "artifact_sha256": _sha256(output_path),
        "status": "passed",
        "schema_version": FINANCE_AGENT_EVIDENCE_UNION_VERSION,
    }
    provisional = FinanceAgentEvidenceUnionReport.model_construct(
        report_id="pending", **report_values
    )
    report = FinanceAgentEvidenceUnionReport(
        report_id=finance_agent_evidence_union_report_id(provisional),
        **report_values,
    )
    _write_json_atomic(report_path, report.model_dump(mode="json"))
    return report


def _merge_evidence_sources(
    sources: Iterable[tuple[str, tuple[FinanceTaskStateArtifact, ...]]],
    *,
    union_id: str,
) -> tuple[
    tuple[FinanceAgentEvidenceUnionItem, ...],
    int,
    int,
    int,
    int,
    Counter[str],
]:
    retained: dict[str, EvidenceItem] = {}
    content_hashes: dict[str, str] = {}
    origins: dict[str, set[str]] = defaultdict(set)
    version_to_evidence: dict[str, str] = {}
    all_source_artifacts: set[str] = set()
    contribution_counts: Counter[str] = Counter()
    occurrences = 0
    duplicates = 0
    superseded = 0
    for source_sha256, records in sources:
        contribution_counts[source_sha256] += 0
        for record in records:
            all_source_artifacts.add(record.artifact_id)
            for evidence in record.omega.public_corpus.evidence:
                occurrences += 1
                evidence_id = evidence.evidence_id
                version_id = evidence.evidence_version_id
                owner = version_to_evidence.get(version_id)
                if owner is not None and owner != evidence_id:
                    raise ValueError("one Evidence Version identifies multiple Evidence IDs")
                prior = retained.get(evidence_id)
                if prior is None:
                    retained[evidence_id] = evidence
                    content_hashes[evidence_id] = canonical_hash(
                        evidence.model_dump(mode="json"), prefix="evidence_union_content:"
                    )
                    version_to_evidence[version_id] = evidence_id
                    contribution_counts[source_sha256] += 1
                elif prior.evidence_version_id == version_id:
                    observed_hash = canonical_hash(
                        evidence.model_dump(mode="json"), prefix="evidence_union_content:"
                    )
                    if observed_hash != content_hashes[evidence_id]:
                        raise ValueError("content-bound Evidence Version has conflicting content")
                    duplicates += 1
                else:
                    superseded += 1
                    continue
                origins[evidence_id].add(record.artifact_id)
    items: list[FinanceAgentEvidenceUnionItem] = []
    for evidence_id, evidence in sorted(retained.items()):
        values = {
            "union_id": union_id,
            "evidence": evidence,
            "source_artifact_ids": tuple(sorted(origins[evidence_id])),
            "schema_version": FINANCE_AGENT_EVIDENCE_UNION_ITEM_VERSION,
        }
        provisional = FinanceAgentEvidenceUnionItem.model_construct(
            union_item_id="pending", **values
        )
        items.append(
            FinanceAgentEvidenceUnionItem(
                union_item_id=finance_agent_evidence_union_item_id(provisional),
                **values,
            )
        )
    return (
        tuple(items),
        len(all_source_artifacts),
        occurrences,
        duplicates,
        superseded,
        contribution_counts,
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build an immutable Evidence-level union from Finance Agent populations"
    )
    parser.add_argument("--source-artifact-paths", nargs="+", required=True)
    parser.add_argument("--source-report-paths", nargs="+", required=True)
    parser.add_argument("--output-dir", required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    report = build_finance_agent_evidence_union(
        source_artifact_paths=tuple(Path(value).resolve() for value in args.source_artifact_paths),
        source_report_paths=tuple(Path(value).resolve() for value in args.source_report_paths),
        output_dir=Path(args.output_dir).resolve(),
    )
    print(report.model_dump_json(indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
