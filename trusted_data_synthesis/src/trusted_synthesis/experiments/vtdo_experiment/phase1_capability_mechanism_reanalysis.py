from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_boundary_analysis import (
    CapabilityRolloutOutcome,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_mechanism_flash_development import (  # noqa: E501
    FinanceCapabilityMechanismFlashContract,
    FinanceCapabilityMechanismFlashReport,
    _make_terminals,
    _render_report,
    make_mechanism_behavior_observations,
    make_mechanism_flash_report,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_multitier_runtime_resolution import (
    _load_records,
)
from trusted_synthesis.hashing import canonical_hash

CAPABILITY_MECHANISM_REANALYSIS_VERSION = "finance_capability_mechanism_reanalysis.v1"


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class FinanceCapabilityMechanismReanalysisManifest(FrozenModel):
    manifest_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    source_contract_path: str = Field(min_length=1)
    source_contract_sha256: str = Field(min_length=64, max_length=64)
    source_contract_id: str = Field(min_length=1)
    source_records_path: str = Field(min_length=1)
    source_records_sha256: str = Field(min_length=64, max_length=64)
    source_outcomes_path: str = Field(min_length=1)
    source_outcomes_sha256: str = Field(min_length=64, max_length=64)
    source_report_path: str = Field(min_length=1)
    source_report_sha256: str = Field(min_length=64, max_length=64)
    source_report_id: str = Field(min_length=1)
    analysis_implementation_path: str = Field(min_length=1)
    analysis_implementation_sha256: str = Field(min_length=64, max_length=64)
    corrected_report_path: str = Field(min_length=1)
    corrected_report_sha256: str = Field(min_length=64, max_length=64)
    corrected_report_id: str = Field(min_length=1)
    recorded_rollout_count: int = Field(ge=1)
    model_api_calls: int = Field(default=0, ge=0, le=0)
    gpu_jobs: int = Field(default=0, ge=0, le=0)
    original_report_overwritten: bool = False
    schema_version: str = CAPABILITY_MECHANISM_REANALYSIS_VERSION

    @model_validator(mode="after")
    def validate_manifest(self) -> FinanceCapabilityMechanismReanalysisManifest:
        if self.original_report_overwritten:
            raise ValueError("mechanism reanalysis cannot overwrite its source report")
        if self.manifest_id != mechanism_reanalysis_manifest_id(self):
            raise ValueError("mechanism reanalysis manifest identity is invalid")
        return self


def mechanism_reanalysis_manifest_id(
    value: FinanceCapabilityMechanismReanalysisManifest,
) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"manifest_id"}),
        prefix="finance_capability_mechanism_reanalysis:",
    )


def reanalyze_mechanism_flash_development(
    *,
    contract_path: Path,
    source_run_dir: Path,
    output_dir: Path,
    run_id: str,
) -> tuple[FinanceCapabilityMechanismFlashReport, FinanceCapabilityMechanismReanalysisManifest]:
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / "finance_capability_mechanism_flash_report.json"
    manifest_path = output_dir / "finance_capability_mechanism_reanalysis_manifest.json"
    if report_path.exists() or manifest_path.exists():
        raise ValueError("mechanism reanalysis output is immutable")
    contract = FinanceCapabilityMechanismFlashContract.model_validate_json(
        contract_path.read_text(encoding="utf-8")
    )
    records_path = source_run_dir / "capability_mechanism_flash_development_records.jsonl"
    outcomes_path = source_run_dir / "capability_mechanism_flash_development_outcomes.jsonl"
    source_report_path = source_run_dir / "finance_capability_mechanism_flash_report.json"
    source_report = json.loads(source_report_path.read_text(encoding="utf-8"))
    records = _load_records(records_path)
    outcomes = tuple(
        CapabilityRolloutOutcome.model_validate_json(line)
        for line in outcomes_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    )
    if len(records) != contract.requested_rollout_count or len(outcomes) != len(records):
        raise ValueError("mechanism reanalysis source denominator is incomplete")
    if any(item.contract_id != contract.contract_id for item in (*records, *outcomes)):
        raise ValueError("mechanism reanalysis source crosses contract identities")
    terminals = _make_terminals(contract, records, outcomes)
    behaviors = make_mechanism_behavior_observations(contract, records, terminals)
    report = make_mechanism_flash_report(contract, outcomes, terminals, behaviors)
    _write_json_atomic(report_path, report.model_dump(mode="json"))
    _write_text_atomic(
        output_dir / "finance_capability_mechanism_flash_report.md",
        _render_report(report),
    )
    implementation_path = Path(__file__).with_name(
        "phase1_capability_mechanism_flash_development.py"
    )
    values = {
        "run_id": run_id,
        "source_contract_path": str(contract_path.resolve()),
        "source_contract_sha256": _sha256(contract_path),
        "source_contract_id": contract.contract_id,
        "source_records_path": str(records_path.resolve()),
        "source_records_sha256": _sha256(records_path),
        "source_outcomes_path": str(outcomes_path.resolve()),
        "source_outcomes_sha256": _sha256(outcomes_path),
        "source_report_path": str(source_report_path.resolve()),
        "source_report_sha256": _sha256(source_report_path),
        "source_report_id": str(source_report["report_id"]),
        "analysis_implementation_path": str(implementation_path.resolve()),
        "analysis_implementation_sha256": _sha256(implementation_path),
        "corrected_report_path": str(report_path.resolve()),
        "corrected_report_sha256": _sha256(report_path),
        "corrected_report_id": report.report_id,
        "recorded_rollout_count": len(records),
    }
    provisional = FinanceCapabilityMechanismReanalysisManifest.model_construct(
        manifest_id="pending", **values
    )
    manifest = FinanceCapabilityMechanismReanalysisManifest(
        manifest_id=mechanism_reanalysis_manifest_id(provisional), **values
    )
    _write_json_atomic(manifest_path, manifest.model_dump(mode="json"))
    return report, manifest


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_json_atomic(path: Path, value: Any) -> None:
    _write_text_atomic(
        path,
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    )


def _write_text_atomic(path: Path, value: str) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(value, encoding="utf-8")
    temporary.replace(path)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Reanalyze a frozen v25.21 Flash mechanism Development run."
    )
    parser.add_argument("--contract", required=True, type=Path)
    parser.add_argument("--source-run-dir", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--run-id", required=True)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    report, manifest = reanalyze_mechanism_flash_development(
        contract_path=args.contract,
        source_run_dir=args.source_run_dir,
        output_dir=args.output_dir,
        run_id=args.run_id,
    )
    print(
        json.dumps(
            {
                "report_id": report.report_id,
                "manifest_id": manifest.manifest_id,
                "recorded_rollout_count": report.recorded_rollout_count,
                "runtime_qualification_passed": report.runtime_qualification_passed,
                "selected_mechanism_ids": report.selected_mechanism_ids,
                "next_permitted_stage": report.next_permitted_stage,
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
