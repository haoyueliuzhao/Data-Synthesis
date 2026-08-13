from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.domains.finance.iterative_agent_verifier import (
    FinanceIterativeAgentVerifier,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_boundary import (
    make_v25_native_runtime_context,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_mechanism_flash_development import (  # noqa: E501
    FinanceCapabilityMechanismFlashContract,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_multitier_runtime_resolution import (
    _load_records,
)
from trusted_synthesis.hashing import canonical_hash
from trusted_synthesis.runtime.agent.iterative import (
    IterativeAgentAudit,
    IterativeAgentSolveResult,
)

CAPABILITY_MECHANISM_REVERIFICATION_VERSION = (
    "finance_capability_mechanism_offline_reverification.v1"
)


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class OfflineReverificationRow(FrozenModel):
    record_id: str = Field(min_length=1)
    binding_id: str = Field(min_length=1)
    task_artifact_id: str = Field(min_length=1)
    mechanism_id: str = Field(min_length=1)
    variant_role: str = Field(min_length=1)
    replicate: int = Field(ge=0)
    valid: bool
    answer_correct: bool
    failed_check_ids: tuple[str, ...]
    verifier_report_id: str = Field(min_length=1)


class FinanceCapabilityMechanismReverificationManifest(FrozenModel):
    manifest_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    source_contract_path: str = Field(min_length=1)
    source_contract_sha256: str = Field(min_length=64, max_length=64)
    source_contract_id: str = Field(min_length=1)
    source_records_path: str = Field(min_length=1)
    source_records_sha256: str = Field(min_length=64, max_length=64)
    implementation_manifest: dict[str, str]
    implementation_manifest_hash: str = Field(min_length=1)
    source_record_count: int = Field(ge=1)
    reverifiable_record_count: int = Field(ge=0)
    unreverifiable_record_ids: tuple[str, ...]
    answer_correct_count: int = Field(ge=0)
    valid_count: int = Field(ge=0)
    reports_path: str = Field(min_length=1)
    reports_sha256: str = Field(min_length=64, max_length=64)
    model_api_calls: int = Field(default=0, ge=0, le=0)
    gpu_jobs: int = Field(default=0, ge=0, le=0)
    source_records_overwritten: bool = False
    next_permitted_stage: str = "corrected_contract_regression_or_development_only"
    schema_version: str = CAPABILITY_MECHANISM_REVERIFICATION_VERSION

    @model_validator(mode="after")
    def validate_manifest(self) -> FinanceCapabilityMechanismReverificationManifest:
        if self.source_records_overwritten:
            raise ValueError("offline reverification cannot overwrite source records")
        if self.source_record_count != (
            self.reverifiable_record_count + len(self.unreverifiable_record_ids)
        ):
            raise ValueError("offline reverification denominator is inconsistent")
        if self.answer_correct_count > self.reverifiable_record_count:
            raise ValueError("answer-correct numerator exceeds reverifiable records")
        if self.valid_count > self.reverifiable_record_count:
            raise ValueError("valid numerator exceeds reverifiable records")
        if self.implementation_manifest_hash != canonical_hash(
            self.implementation_manifest,
            prefix="finance_capability_mechanism_reverification_implementation:",
        ):
            raise ValueError("offline reverification implementation hash is invalid")
        if self.manifest_id != reverification_manifest_id(self):
            raise ValueError("offline reverification manifest identity is invalid")
        return self


def reverification_manifest_id(
    value: FinanceCapabilityMechanismReverificationManifest,
) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"manifest_id"}),
        prefix="finance_capability_mechanism_offline_reverification:",
    )


def reverify_mechanism_records(
    *,
    contract_path: Path,
    source_records_path: Path,
    output_dir: Path,
    run_id: str,
) -> FinanceCapabilityMechanismReverificationManifest:
    manifest_path = output_dir / "offline_reverification_manifest.json"
    reports_path = output_dir / "offline_reverification_reports.jsonl"
    if output_dir.exists():
        raise ValueError("offline reverification output is immutable")
    contract = FinanceCapabilityMechanismFlashContract.model_validate_json(
        contract_path.read_text(encoding="utf-8")
    )
    records = _load_records(source_records_path)
    tasks = {item.artifact_id: item for item in contract.tasks}
    bindings = {item.binding_id: item for item in contract.bindings}
    rows: list[OfflineReverificationRow] = []
    unreverifiable: list[str] = []
    verifier = FinanceIterativeAgentVerifier()
    for record in records:
        if record.contract_id != contract.contract_id:
            raise ValueError("offline reverification record crosses contract identity")
        if record.agent_audit is None or record.trajectory is None:
            unreverifiable.append(record.record_id)
            continue
        task = tasks[record.task_artifact_id]
        binding = bindings[record.binding_id]
        context, environment, _ = make_v25_native_runtime_context(
            task,
            binding.runtime_arm,
            contract.protocol_profile,
        )
        result = IterativeAgentSolveResult(
            trajectory=record.trajectory,
            audit=IterativeAgentAudit.model_validate(record.agent_audit),
            observations=record.observations,
        )
        report = verifier.verify(
            context,
            context.public_corpus,
            environment,
            result,
        )
        answer_correct = next(
            item.passed for item in report.checks if item.check_id == "answer_correct"
        )
        rows.append(
            OfflineReverificationRow(
                record_id=record.record_id,
                binding_id=record.binding_id,
                task_artifact_id=record.task_artifact_id,
                mechanism_id=contract.task_mechanism_ids[record.task_artifact_id],
                variant_role=contract.task_variant_roles[record.task_artifact_id],
                replicate=record.replicate,
                valid=report.valid,
                answer_correct=answer_correct,
                failed_check_ids=tuple(
                    item.check_id for item in report.checks if not item.passed
                ),
                verifier_report_id=report.report_id,
            )
        )
    output_dir.mkdir(parents=True)
    _write_jsonl_atomic(
        reports_path,
        (item.model_dump(mode="json") for item in rows),
    )
    implementation = _implementation_manifest()
    values = {
        "run_id": run_id,
        "source_contract_path": str(contract_path.resolve()),
        "source_contract_sha256": _sha256(contract_path),
        "source_contract_id": contract.contract_id,
        "source_records_path": str(source_records_path.resolve()),
        "source_records_sha256": _sha256(source_records_path),
        "implementation_manifest": implementation,
        "implementation_manifest_hash": canonical_hash(
            implementation,
            prefix="finance_capability_mechanism_reverification_implementation:",
        ),
        "source_record_count": len(records),
        "reverifiable_record_count": len(rows),
        "unreverifiable_record_ids": tuple(sorted(unreverifiable)),
        "answer_correct_count": sum(item.answer_correct for item in rows),
        "valid_count": sum(item.valid for item in rows),
        "reports_path": str(reports_path.resolve()),
        "reports_sha256": _sha256(reports_path),
    }
    provisional = FinanceCapabilityMechanismReverificationManifest.model_construct(
        manifest_id="pending", **values
    )
    manifest = FinanceCapabilityMechanismReverificationManifest(
        manifest_id=reverification_manifest_id(provisional), **values
    )
    _write_json_atomic(manifest_path, manifest.model_dump(mode="json"))
    _write_text_atomic(output_dir / "offline_reverification_report.md", _render_report(manifest))
    return manifest


def _implementation_manifest() -> dict[str, str]:
    root = Path(__file__).resolve().parents[4]
    paths = (
        Path(__file__).resolve(),
        root / "src/trusted_synthesis/domains/finance/iterative_agent_verifier.py",
        root / "src/trusted_synthesis/core/evaluation/answer.py",
        root / "src/trusted_synthesis/core/operations/executors/numeric.py",
        root
        / "src/trusted_synthesis/experiments/vtdo_experiment/phase1_capability_boundary.py",
    )
    return {str(path.relative_to(root)): _sha256(path) for path in paths}


def _render_report(value: FinanceCapabilityMechanismReverificationManifest) -> str:
    return "\n".join(
        (
            "# Finance v25.21 Offline Reverification Report",
            "",
            f"- Manifest ID: `{value.manifest_id}`",
            f"- Source records: **{value.source_record_count}**",
            f"- Reverified records: **{value.reverifiable_record_count}**",
            f"- Transport failures retained: **{len(value.unreverifiable_record_ids)}**",
            f"- Answer correct: **{value.answer_correct_count}/{value.reverifiable_record_count}**",
            f"- Fully valid: **{value.valid_count}/{value.reverifiable_record_count}**",
            "- Additional API calls: **0**",
            "- GPU jobs: **0**",
            "",
            "The source trajectories are immutable. This artifact only replays them under the "
            "content-hashed verifier contract and cannot promote a failed transport record.",
            "",
        )
    )


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


def _write_jsonl_atomic(path: Path, values: Any) -> None:
    _write_text_atomic(
        path,
        "".join(json.dumps(item, ensure_ascii=False, sort_keys=True) + "\n" for item in values),
    )


def _write_text_atomic(path: Path, value: str) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(value, encoding="utf-8")
    temporary.replace(path)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Reverify immutable v25.21 trajectories under a new verifier contract."
    )
    parser.add_argument("--contract", required=True, type=Path)
    parser.add_argument("--source-records", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--run-id", required=True)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    result = reverify_mechanism_records(
        contract_path=args.contract,
        source_records_path=args.source_records,
        output_dir=args.output_dir,
        run_id=args.run_id,
    )
    print(
        json.dumps(
            {
                "manifest_id": result.manifest_id,
                "source_record_count": result.source_record_count,
                "reverifiable_record_count": result.reverifiable_record_count,
                "valid_count": result.valid_count,
                "next_permitted_stage": result.next_permitted_stage,
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
