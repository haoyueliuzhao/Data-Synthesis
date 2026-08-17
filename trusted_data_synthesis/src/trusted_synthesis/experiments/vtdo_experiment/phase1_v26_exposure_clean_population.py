from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.core.evidence.schema import EvidenceItem
from trusted_synthesis.domains.finance.adapter import FinanceArchiveAdapter
from trusted_synthesis.domains.finance.schema import FinanceArchiveConfig
from trusted_synthesis.domains.finance.source_grounding import (
    FinanceSourceGroundingVerifier,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_sensitive_frontier import (
    CapabilitySensitiveFrontierPopulation,
    build_capability_sensitive_frontier_population,
    load_capability_source_public_evidence,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_bridge_rollout import (
    HistoricalApiRecordManifest,
    HistoricalEvidencePoolExposureAudit,
    audit_historical_evidence_pool_exposure,
    replay_historical_api_record_manifest,
)
from trusted_synthesis.hashing import canonical_hash

V26_EXPOSURE_CLEAN_POPULATION_RECEIPT_VERSION = "finance_v26_exposure_clean_population_receipt.v3"
V26_SOURCE_GROUNDING_POOL_AUDIT_VERSION = "finance_v26_source_grounding_pool_audit.v1"


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class SourceGroundingPoolAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    source_artifacts_path: str = Field(min_length=1)
    source_artifacts_sha256: str = Field(min_length=64, max_length=64)
    archive_config_path: str = Field(min_length=1)
    archive_config_sha256: str = Field(min_length=64, max_length=64)
    verifier_id: str = Field(min_length=1)
    verifier_version: str = Field(min_length=1)
    archive_compatibility_hash: str = Field(min_length=1)
    source_evidence_set_hash: str = Field(min_length=1)
    source_evidence_count: int = Field(ge=1)
    raw_object_count: int = Field(ge=1)
    passed_evidence_count: int = Field(ge=0)
    failed_evidence_ids: tuple[str, ...]
    failed_evidence_set_hash: str = Field(min_length=1)
    failed_evidence_count: int = Field(ge=0)
    failure_counts: dict[str, int]
    failure_source_counts: dict[str, int]
    status: Literal["observed"] = "observed"
    schema_version: Literal["finance_v26_source_grounding_pool_audit.v1"] = (
        "finance_v26_source_grounding_pool_audit.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> SourceGroundingPoolAudit:
        if self.failed_evidence_ids != tuple(sorted(set(self.failed_evidence_ids))):
            raise ValueError("source-grounding failed Evidence identities are not canonical")
        if self.failed_evidence_count != len(self.failed_evidence_ids):
            raise ValueError("source-grounding failed Evidence count is inconsistent")
        if self.passed_evidence_count + self.failed_evidence_count != self.source_evidence_count:
            raise ValueError("source-grounding Evidence accounting is inconsistent")
        if self.failed_evidence_set_hash != canonical_hash(
            self.failed_evidence_ids,
            prefix="finance_v26_source_grounding_failed_evidence_set:",
        ):
            raise ValueError("source-grounding failed Evidence set hash is invalid")
        if self.failure_counts != dict(sorted(self.failure_counts.items())):
            raise ValueError("source-grounding failure counts are not canonical")
        if self.failure_source_counts != dict(sorted(self.failure_source_counts.items())):
            raise ValueError("source-grounding failure source counts are not canonical")
        if sum(self.failure_source_counts.values()) != self.failed_evidence_count:
            raise ValueError("source-grounding failure source accounting is inconsistent")
        if self.audit_id != source_grounding_pool_audit_id(self):
            raise ValueError("source-grounding pool audit identity is invalid")
        return self


class ExposureCleanPopulationReceipt(FrozenModel):
    receipt_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    historical_pool_exposure_audit_id: str = Field(min_length=1)
    historical_pool_exposure_audit_path: str = Field(min_length=1)
    historical_pool_exposure_audit_sha256: str = Field(min_length=64, max_length=64)
    source_grounding_pool_audit_id: str = Field(min_length=1)
    source_grounding_pool_audit_path: str = Field(min_length=1)
    source_grounding_pool_audit_sha256: str = Field(min_length=64, max_length=64)
    historical_record_manifest_id: str = Field(min_length=1)
    source_artifacts_path: str = Field(min_length=1)
    source_artifacts_sha256: str = Field(min_length=64, max_length=64)
    archive_config_path: str = Field(min_length=1)
    archive_config_sha256: str = Field(min_length=64, max_length=64)
    source_grounding_verifier_id: str = Field(min_length=1)
    source_grounding_verifier_version: str = Field(min_length=1)
    source_evidence_count: int = Field(ge=1)
    historical_exposed_evidence_count: int = Field(ge=0)
    historical_exposed_evidence_set_hash: str = Field(min_length=1)
    grounding_failed_evidence_count: int = Field(ge=0)
    grounding_failed_evidence_set_hash: str = Field(min_length=1)
    effective_excluded_evidence_count: int = Field(ge=0)
    eligible_evidence_count: int = Field(ge=1)
    excluded_evidence_ids: tuple[str, ...]
    excluded_evidence_set_hash: str = Field(min_length=1)
    output_population_id: str = Field(min_length=1)
    output_population_path: str = Field(min_length=1)
    output_population_sha256: str = Field(min_length=64, max_length=64)
    output_population_content_hash: str = Field(min_length=1)
    output_task_count: int = Field(ge=1)
    selected_excluded_evidence_overlap_count: Literal[0] = 0
    model_api_calls: Literal[0] = 0
    status: Literal["passed"] = "passed"
    schema_version: Literal["finance_v26_exposure_clean_population_receipt.v3"] = (
        "finance_v26_exposure_clean_population_receipt.v3"
    )

    @model_validator(mode="after")
    def validate_receipt(self) -> ExposureCleanPopulationReceipt:
        if self.excluded_evidence_ids != tuple(sorted(set(self.excluded_evidence_ids))):
            raise ValueError("exposure-clean exclusion identities are not canonical")
        expected_set_hash = canonical_hash(
            self.excluded_evidence_ids,
            prefix="finance_v26_exposure_clean_exclusion_set:",
        )
        if self.excluded_evidence_set_hash != expected_set_hash:
            raise ValueError("exposure-clean exclusion set hash is invalid")
        if self.effective_excluded_evidence_count != len(self.excluded_evidence_ids):
            raise ValueError("exposure-clean effective exclusion count is inconsistent")
        if self.eligible_evidence_count != (
            self.source_evidence_count - self.effective_excluded_evidence_count
        ):
            raise ValueError("exposure-clean eligible Evidence count is inconsistent")
        if self.historical_exposed_evidence_count > self.effective_excluded_evidence_count:
            raise ValueError("historical exposure exceeds the effective exclusion set")
        if self.grounding_failed_evidence_count > self.effective_excluded_evidence_count:
            raise ValueError("grounding failures exceed the effective exclusion set")
        if self.receipt_id != exposure_clean_population_receipt_id(self):
            raise ValueError("exposure-clean Population receipt identity is invalid")
        return self


def source_grounding_pool_audit_id(value: SourceGroundingPoolAudit) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"audit_id"}),
        prefix="finance_v26_source_grounding_pool_audit:",
    )


def exposure_clean_population_receipt_id(value: ExposureCleanPopulationReceipt) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"receipt_id"}),
        prefix="finance_v26_exposure_clean_population_receipt:",
    )


def audit_source_grounding_pool(
    *,
    source_artifacts_path: Path,
    source_evidence: tuple[EvidenceItem, ...],
    archive_config_path: Path,
    output_path: Path | None = None,
) -> SourceGroundingPoolAudit:
    source_path = source_artifacts_path.resolve()
    config_path = archive_config_path.resolve()
    canonical_evidence = tuple(sorted(source_evidence, key=lambda item: item.evidence_id))
    evidence_ids = tuple(item.evidence_id for item in canonical_evidence)
    if not evidence_ids or len(evidence_ids) != len(set(evidence_ids)):
        raise ValueError("source-grounding audit requires unique nonempty Evidence support")

    adapter = FinanceArchiveAdapter(FinanceArchiveConfig.from_json(config_path))
    compatibility = adapter.inspect()
    if not compatibility.get("compatible"):
        raise ValueError("source-grounding audit received an incompatible Finance archive")
    verifier = adapter.source_grounding_verifier()
    grouped: defaultdict[str, list[EvidenceItem]] = defaultdict(list)
    for item in canonical_evidence:
        grouped[item.source_locator.raw_object_id or ""].append(item)

    failed: list[str] = []
    failure_counts: Counter[str] = Counter()
    failure_source_counts: Counter[str] = Counter()
    for raw_object_id in sorted(grouped):
        for item in grouped[raw_object_id]:
            report = verifier.verify(item)
            if report.passed:
                continue
            failed.append(item.evidence_id)
            failure_counts.update(report.failures)
            failure_source_counts[item.source.source_id] += 1

    failed_ids = tuple(sorted(failed))
    values: dict[str, Any] = {
        "source_artifacts_path": str(source_path),
        "source_artifacts_sha256": _sha256(source_path),
        "archive_config_path": str(config_path),
        "archive_config_sha256": _sha256(config_path),
        "verifier_id": FinanceSourceGroundingVerifier.verifier_id,
        "verifier_version": FinanceSourceGroundingVerifier.verifier_version,
        "archive_compatibility_hash": canonical_hash(
            compatibility,
            prefix="finance_v26_archive_compatibility:",
        ),
        "source_evidence_set_hash": canonical_hash(
            evidence_ids,
            prefix="finance_v26_source_grounding_evidence_set:",
        ),
        "source_evidence_count": len(evidence_ids),
        "raw_object_count": len(grouped),
        "passed_evidence_count": len(evidence_ids) - len(failed_ids),
        "failed_evidence_ids": failed_ids,
        "failed_evidence_set_hash": canonical_hash(
            failed_ids,
            prefix="finance_v26_source_grounding_failed_evidence_set:",
        ),
        "failed_evidence_count": len(failed_ids),
        "failure_counts": dict(sorted(failure_counts.items())),
        "failure_source_counts": dict(sorted(failure_source_counts.items())),
        "status": "observed",
        "schema_version": V26_SOURCE_GROUNDING_POOL_AUDIT_VERSION,
    }
    provisional = SourceGroundingPoolAudit.model_construct(audit_id="pending", **values)
    audit = SourceGroundingPoolAudit(
        audit_id=source_grounding_pool_audit_id(provisional),
        **values,
    )
    if output_path is not None:
        _write_json_atomic(output_path, audit.model_dump(mode="json"))
    return audit


def replay_source_grounding_pool_audit(
    audit: SourceGroundingPoolAudit,
    *,
    source_artifacts_path: Path,
    source_evidence_ids: tuple[str, ...],
    archive_config_path: Path,
) -> None:
    source_path = source_artifacts_path.resolve()
    config_path = archive_config_path.resolve()
    canonical_ids = tuple(sorted(set(source_evidence_ids)))
    if len(canonical_ids) != len(source_evidence_ids):
        raise ValueError("source-grounding replay received duplicate Evidence identities")
    if audit.source_artifacts_path != str(source_path) or audit.source_artifacts_sha256 != _sha256(
        source_path
    ):
        raise ValueError("source-grounding replay source artifacts changed")
    if audit.archive_config_path != str(config_path) or audit.archive_config_sha256 != _sha256(
        config_path
    ):
        raise ValueError("source-grounding replay archive config changed")
    if (
        audit.verifier_id != FinanceSourceGroundingVerifier.verifier_id
        or audit.verifier_version != FinanceSourceGroundingVerifier.verifier_version
    ):
        raise ValueError("source-grounding replay verifier changed")
    expected_evidence_hash = canonical_hash(
        canonical_ids,
        prefix="finance_v26_source_grounding_evidence_set:",
    )
    if (
        audit.source_evidence_count != len(canonical_ids)
        or audit.source_evidence_set_hash != expected_evidence_hash
    ):
        raise ValueError("source-grounding replay Evidence support changed")
    adapter = FinanceArchiveAdapter(FinanceArchiveConfig.from_json(config_path))
    compatibility = adapter.inspect()
    if not compatibility.get("compatible"):
        raise ValueError("source-grounding replay archive is incompatible")
    if audit.archive_compatibility_hash != canonical_hash(
        compatibility,
        prefix="finance_v26_archive_compatibility:",
    ):
        raise ValueError("source-grounding replay archive compatibility changed")


def _load_source_grounding_pool_audit(path: Path) -> SourceGroundingPoolAudit:
    return SourceGroundingPoolAudit.model_validate_json(path.read_text(encoding="utf-8"))


def build_exposure_clean_population(
    *,
    run_id: str,
    source_artifacts_path: Path,
    historical_record_manifest_path: Path,
    archive_config_path: Path,
    sampling_salt: str,
    output_pool_exposure_audit_path: Path,
    output_source_grounding_audit_path: Path,
    output_population_path: Path,
    output_receipt_path: Path,
) -> tuple[CapabilitySensitiveFrontierPopulation, ExposureCleanPopulationReceipt]:
    if output_population_path.exists() or output_receipt_path.exists():
        raise ValueError("exposure-clean Population and receipt outputs are immutable")
    exposure_exists = output_pool_exposure_audit_path.exists()
    grounding_exists = output_source_grounding_audit_path.exists()
    if exposure_exists != grounding_exists:
        raise ValueError("source-pool audit checkpoint is incomplete")
    for output_path in (
        output_pool_exposure_audit_path,
        output_source_grounding_audit_path,
        output_population_path,
        output_receipt_path,
    ):
        output_path.parent.mkdir(parents=True, exist_ok=True)
    record_manifest = HistoricalApiRecordManifest.model_validate_json(
        historical_record_manifest_path.read_text(encoding="utf-8")
    )
    source_path = source_artifacts_path.resolve()
    config_path = archive_config_path.resolve()
    exposure_audit_path = output_pool_exposure_audit_path.resolve()
    grounding_audit_path = output_source_grounding_audit_path.resolve()
    source_evidence = load_capability_source_public_evidence(source_path)
    source_evidence_ids = tuple(item.evidence_id for item in source_evidence)
    if exposure_exists:
        exposure_audit = HistoricalEvidencePoolExposureAudit.model_validate_json(
            exposure_audit_path.read_text(encoding="utf-8")
        )
        grounding_audit = _load_source_grounding_pool_audit(grounding_audit_path)
        replay_historical_api_record_manifest(exposure_audit.record_manifest)
        if exposure_audit.record_manifest.manifest_id != record_manifest.manifest_id:
            raise ValueError("source-pool checkpoint uses another Provider manifest")
        if (
            exposure_audit.source_artifacts_path != str(source_path)
            or exposure_audit.source_artifacts_sha256 != _sha256(source_path)
            or exposure_audit.source_evidence_ids != source_evidence_ids
        ):
            raise ValueError("historical source-pool checkpoint input changed")
        replay_source_grounding_pool_audit(
            grounding_audit,
            source_artifacts_path=source_path,
            source_evidence_ids=source_evidence_ids,
            archive_config_path=config_path,
        )
    else:
        exposure_audit = audit_historical_evidence_pool_exposure(
            source_artifacts_path=source_path,
            source_evidence_ids=source_evidence_ids,
            record_manifest=record_manifest,
            output_path=exposure_audit_path,
        )
        grounding_audit = audit_source_grounding_pool(
            source_artifacts_path=source_path,
            source_evidence=source_evidence,
            archive_config_path=config_path,
            output_path=grounding_audit_path,
        )
    if exposure_audit.source_evidence_count != grounding_audit.source_evidence_count:
        raise ValueError("source-pool audits disagree on the Evidence denominator")
    excluded_ids = tuple(
        sorted(set(exposure_audit.exposed_evidence_ids) | set(grounding_audit.failed_evidence_ids))
    )
    if len(excluded_ids) >= len(source_evidence):
        raise ValueError("source-pool audits leave no eligible Evidence")
    population = build_capability_sensitive_frontier_population(
        source_artifacts_path=source_path,
        output_path=output_population_path,
        run_id=run_id,
        sampling_salt=sampling_salt,
        excluded_evidence_ids=excluded_ids,
    )
    selected_evidence_ids = {
        evidence.evidence_id
        for task in population.tasks
        for evidence in task.public_corpus.evidence
    }
    overlap = selected_evidence_ids & set(excluded_ids)
    if overlap:
        raise ValueError("exposure-clean Population retained excluded Evidence")
    if not population.audit.structural_frontier_ready:
        raise ValueError("exposure-clean Population failed structural Frontier admission")

    values: dict[str, Any] = {
        "run_id": run_id,
        "historical_pool_exposure_audit_id": exposure_audit.audit_id,
        "historical_pool_exposure_audit_path": str(exposure_audit_path),
        "historical_pool_exposure_audit_sha256": _sha256(exposure_audit_path),
        "source_grounding_pool_audit_id": grounding_audit.audit_id,
        "source_grounding_pool_audit_path": str(grounding_audit_path),
        "source_grounding_pool_audit_sha256": _sha256(grounding_audit_path),
        "historical_record_manifest_id": exposure_audit.record_manifest.manifest_id,
        "source_artifacts_path": str(source_path),
        "source_artifacts_sha256": _sha256(source_path),
        "archive_config_path": str(config_path),
        "archive_config_sha256": _sha256(config_path),
        "source_grounding_verifier_id": grounding_audit.verifier_id,
        "source_grounding_verifier_version": grounding_audit.verifier_version,
        "source_evidence_count": exposure_audit.source_evidence_count,
        "historical_exposed_evidence_count": exposure_audit.exposed_evidence_count,
        "historical_exposed_evidence_set_hash": exposure_audit.exposed_evidence_set_hash,
        "grounding_failed_evidence_count": grounding_audit.failed_evidence_count,
        "grounding_failed_evidence_set_hash": grounding_audit.failed_evidence_set_hash,
        "effective_excluded_evidence_count": len(excluded_ids),
        "eligible_evidence_count": len(source_evidence) - len(excluded_ids),
        "excluded_evidence_ids": excluded_ids,
        "excluded_evidence_set_hash": canonical_hash(
            excluded_ids,
            prefix="finance_v26_exposure_clean_exclusion_set:",
        ),
        "output_population_id": population.population_id,
        "output_population_path": str(output_population_path.resolve()),
        "output_population_sha256": _sha256(output_population_path),
        "output_population_content_hash": canonical_hash(
            population.model_dump(mode="json"),
            prefix="finance_v26_exposure_clean_population_content:",
        ),
        "output_task_count": len(population.tasks),
        "selected_excluded_evidence_overlap_count": 0,
        "model_api_calls": 0,
        "status": "passed",
        "schema_version": V26_EXPOSURE_CLEAN_POPULATION_RECEIPT_VERSION,
    }
    provisional = ExposureCleanPopulationReceipt.model_construct(receipt_id="pending", **values)
    receipt = ExposureCleanPopulationReceipt(
        receipt_id=exposure_clean_population_receipt_id(provisional),
        **values,
    )
    output_receipt_path.parent.mkdir(parents=True, exist_ok=True)
    _write_json_atomic(output_receipt_path, receipt.model_dump(mode="json"))
    return population, receipt


def replay_exposure_clean_population_receipt(
    receipt: ExposureCleanPopulationReceipt,
) -> CapabilitySensitiveFrontierPopulation:
    exposure_path = Path(receipt.historical_pool_exposure_audit_path)
    grounding_path = Path(receipt.source_grounding_pool_audit_path)
    source_path = Path(receipt.source_artifacts_path)
    config_path = Path(receipt.archive_config_path)
    population_path = Path(receipt.output_population_path)
    if _sha256(exposure_path) != receipt.historical_pool_exposure_audit_sha256:
        raise ValueError("historical exposure audit changed after clean Population build")
    if _sha256(grounding_path) != receipt.source_grounding_pool_audit_sha256:
        raise ValueError("source-grounding audit changed after clean Population build")
    exposure = HistoricalEvidencePoolExposureAudit.model_validate_json(
        exposure_path.read_text(encoding="utf-8")
    )
    grounding = SourceGroundingPoolAudit.model_validate_json(
        grounding_path.read_text(encoding="utf-8")
    )
    replay_historical_api_record_manifest(exposure.record_manifest)
    if exposure.audit_id != receipt.historical_pool_exposure_audit_id:
        raise ValueError("historical pool exposure identity differs from receipt")
    if grounding.audit_id != receipt.source_grounding_pool_audit_id:
        raise ValueError("source-grounding pool identity differs from receipt")
    if exposure.record_manifest.manifest_id != receipt.historical_record_manifest_id:
        raise ValueError("historical Provider manifest differs from receipt")
    if _sha256(source_path) != receipt.source_artifacts_sha256:
        raise ValueError("source artifacts changed after clean Population build")
    if _sha256(config_path) != receipt.archive_config_sha256:
        raise ValueError("Finance archive config changed after clean Population build")
    if (
        grounding.verifier_id != receipt.source_grounding_verifier_id
        or grounding.verifier_version != receipt.source_grounding_verifier_version
        or grounding.verifier_id != FinanceSourceGroundingVerifier.verifier_id
        or grounding.verifier_version != FinanceSourceGroundingVerifier.verifier_version
    ):
        raise ValueError("source-grounding verifier differs from receipt")
    if exposure.source_evidence_count != grounding.source_evidence_count:
        raise ValueError("replayed source-pool audits disagree on their denominator")
    expected_grounding_set_hash = canonical_hash(
        exposure.source_evidence_ids,
        prefix="finance_v26_source_grounding_evidence_set:",
    )
    if grounding.source_evidence_set_hash != expected_grounding_set_hash:
        raise ValueError("source-grounding audit covers a different Evidence set")
    excluded = tuple(
        sorted(set(exposure.exposed_evidence_ids) | set(grounding.failed_evidence_ids))
    )
    if excluded != receipt.excluded_evidence_ids:
        raise ValueError("effective exclusion set differs from source-pool audits")
    if _sha256(population_path) != receipt.output_population_sha256:
        raise ValueError("exposure-clean Population changed after build")
    population = CapabilitySensitiveFrontierPopulation.model_validate_json(
        population_path.read_text(encoding="utf-8")
    )
    if population.population_id != receipt.output_population_id:
        raise ValueError("exposure-clean Population identity differs from receipt")
    if len(population.tasks) != receipt.output_task_count:
        raise ValueError("exposure-clean Population task count differs from receipt")
    if (
        canonical_hash(
            population.model_dump(mode="json"),
            prefix="finance_v26_exposure_clean_population_content:",
        )
        != receipt.output_population_content_hash
    ):
        raise ValueError("exposure-clean Population content hash differs from receipt")
    selected = {
        evidence.evidence_id
        for task in population.tasks
        for evidence in task.public_corpus.evidence
    }
    if selected & set(receipt.excluded_evidence_ids):
        raise ValueError("replayed clean Population contains excluded Evidence")
    return population


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Build a v26 Population excluding historically exposed or ungrounded Evidence."
        )
    )
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--source-artifacts", type=Path, required=True)
    parser.add_argument("--historical-record-manifest", type=Path, required=True)
    parser.add_argument("--archive-config", type=Path, required=True)
    parser.add_argument("--sampling-salt", required=True)
    parser.add_argument("--output-pool-exposure-audit", type=Path, required=True)
    parser.add_argument("--output-source-grounding-audit", type=Path, required=True)
    parser.add_argument("--output-population", type=Path, required=True)
    parser.add_argument("--output-receipt", type=Path, required=True)
    args = parser.parse_args(argv)
    population, receipt = build_exposure_clean_population(
        run_id=args.run_id,
        source_artifacts_path=args.source_artifacts,
        historical_record_manifest_path=args.historical_record_manifest,
        archive_config_path=args.archive_config,
        sampling_salt=args.sampling_salt,
        output_pool_exposure_audit_path=args.output_pool_exposure_audit,
        output_source_grounding_audit_path=args.output_source_grounding_audit,
        output_population_path=args.output_population,
        output_receipt_path=args.output_receipt,
    )
    print(
        json.dumps(
            {
                "population_id": population.population_id,
                "receipt_id": receipt.receipt_id,
                "historical_exposed_evidence_count": (receipt.historical_exposed_evidence_count),
                "grounding_failed_evidence_count": receipt.grounding_failed_evidence_count,
                "effective_excluded_evidence_count": receipt.effective_excluded_evidence_count,
                "task_count": receipt.output_task_count,
                "status": receipt.status,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
