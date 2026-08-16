from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any, Literal, cast

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_boundary_analysis import (
    CapabilityRolloutOutcome,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_submechanism_flash_development import (  # noqa: E501
    _make_terminals,
    make_submechanism_behavior_observations,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_multitier_runtime_resolution import (
    _load_records,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_stopping_instrument_reset import (
    FinanceStoppingInstrumentResetReport,
    InstrumentResetRawAudit,
    _artifact_id,
    _render_report,
    _sha256,
    _verify_reference,
    make_raw_instrument_audit,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_stopping_shape_policy import (
    FinanceStoppingShapePolicyContract,
    FinanceStoppingShapePolicyReport,
    make_stopping_shape_policy_observations,
    make_stopping_shape_policy_report,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_stopping_shape_stability_protocol import (
    FrozenArtifactReference,
)
from trusted_synthesis.hashing import canonical_hash

STOPPING_INSTRUMENT_RESET_FINALIZER_VERSION = (
    "finance_stopping_instrument_reset_finalizer.v1"
)
PREFIX = "stopping_instrument_reset"


class FrozenExecutionContractSnapshot(BaseModel):
    """Read-only schema for finalizing an execution whose code identity is frozen."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    contract_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    source_protocol: FrozenArtifactReference
    source_population: FrozenArtifactReference
    source_execution_contract: FrozenArtifactReference
    implementation_manifest: dict[str, str]
    implementation_manifest_hash: str = Field(min_length=1)
    public_result_contract_manifest_hash: str = Field(min_length=1)
    noninterference_scanner_manifest_hash: str = Field(min_length=1)
    model_input_projection_manifest_hash: str = Field(min_length=1)
    task_count: Literal[48]
    rollout_count: Literal[384]
    requested_model: Literal["deepseek-v4-flash"]
    raw_audit_before_aggregation: Literal[True]
    source_outcomes_used: Literal[False]
    pro_api_calls_authorized: Literal[False]
    beneficiary_authorized: Literal[False]
    exact_target_authorized: Literal[False]
    gp_c_authorized: Literal[False]
    production_contribution: float = Field(ge=0, le=0)
    next_permitted_stage: Literal["flash_instrument_reset"]
    schema_version: Literal["finance_stopping_instrument_reset_contract.v3"]

    @model_validator(mode="after")
    def validate_snapshot(self) -> FrozenExecutionContractSnapshot:
        observed = canonical_hash(
            self.implementation_manifest,
            prefix="finance_stopping_instrument_reset_implementation:",
        )
        if observed != self.implementation_manifest_hash:
            raise ValueError("frozen execution implementation manifest is inconsistent")
        expected_id = canonical_hash(
            self.model_dump(mode="json", exclude={"contract_id"}),
            prefix="finance_stopping_instrument_reset_contract:",
        )
        if self.contract_id != expected_id:
            raise ValueError("frozen execution contract identity is invalid")
        return self


def finalize_instrument_reset_run(
    *, contract_path: Path, output_dir: Path
) -> FinanceStoppingInstrumentResetReport:
    """Finalize an interrupted run without replaying any model request.

    The finalizer requires every expensive execution artifact to exist, independently
    recomputes all deterministic audits, and byte-semantically compares them with the
    frozen artifacts before it writes the missing report and manifest.
    """

    reset = FrozenExecutionContractSnapshot.model_validate_json(
        contract_path.read_text(encoding="utf-8")
    )
    _verify_execution_inputs(reset)
    base = FinanceStoppingShapePolicyContract.model_validate_json(
        Path(reset.source_execution_contract.path).read_text(encoding="utf-8")
    )

    paths = _required_paths(output_dir)
    missing = tuple(sorted(name for name, path in paths.items() if not path.is_file()))
    if missing:
        raise ValueError(f"instrument-reset finalization lacks artifacts: {missing}")

    records = _load_records(paths["records"])
    outcomes = _load_outcomes(paths["outcomes"])
    raw_audit = make_raw_instrument_audit(cast(Any, reset), base, records)
    stored_raw = InstrumentResetRawAudit.model_validate_json(
        paths["raw_audit"].read_text(encoding="utf-8")
    )
    _require_equal(
        "raw_audit",
        stored_raw.model_dump(mode="json"),
        raw_audit.model_dump(mode="json"),
    )

    shape_report: FinanceStoppingShapePolicyReport | None = None
    if raw_audit.shape_analysis_authorized:
        terminals = _make_terminals(cast(Any, base), records, outcomes)
        behaviors = make_submechanism_behavior_observations(
            cast(Any, base), records, outcomes, terminals
        )
        observations = make_stopping_shape_policy_observations(
            base, behaviors, outcomes, terminals
        )
        _require_jsonl_equal(paths["terminals"], terminals)
        _require_jsonl_equal(paths["behaviors"], behaviors)
        _require_jsonl_equal(paths["shape_observations"], observations)
        discovered = _load_discovered_models(paths["model_discovery"])
        shape_report = make_stopping_shape_policy_report(
            base,
            records,
            outcomes,
            terminals,
            observations,
            discovered_models=discovered,
        )
        stored_shape = FinanceStoppingShapePolicyReport.model_validate_json(
            paths["shape_report"].read_text(encoding="utf-8")
        )
        _require_equal(
            "shape_report",
            stored_shape.model_dump(mode="json"),
            shape_report.model_dump(mode="json"),
        )

    report = _make_report(reset, raw_audit, shape_report)
    report_path = output_dir / "finance_stopping_instrument_reset_report.json"
    markdown_path = output_dir / "finance_stopping_instrument_reset_report.md"
    _write_or_verify_json(report_path, report.model_dump(mode="json"))
    _write_or_verify_text(markdown_path, _render_report(report, raw_audit, shape_report))

    manifest_path = output_dir / "finance_stopping_instrument_reset_manifest.json"
    manifest = _make_manifest(
        reset=reset,
        report=report,
        raw_audit=raw_audit,
        shape_report=shape_report,
        output_dir=output_dir,
        report_path=report_path,
        markdown_path=markdown_path,
    )
    _write_or_verify_json(manifest_path, manifest)
    return report


def _verify_execution_inputs(reset: FrozenExecutionContractSnapshot) -> None:
    for reference in (
        reset.source_protocol,
        reset.source_population,
        reset.source_execution_contract,
    ):
        _verify_reference(reference.path, reference.sha256)
    observed = canonical_hash(
        reset.implementation_manifest,
        prefix="finance_stopping_instrument_reset_implementation:",
    )
    if observed != reset.implementation_manifest_hash:
        raise ValueError("frozen execution implementation manifest is inconsistent")


def _required_paths(output_dir: Path) -> dict[str, Path]:
    return {
        "records": output_dir / f"{PREFIX}_records.jsonl",
        "outcomes": output_dir / f"{PREFIX}_outcomes.jsonl",
        "raw_audit": output_dir / "finance_stopping_instrument_reset_raw_audit.json",
        "terminals": output_dir / f"{PREFIX}_terminal_outcomes.jsonl",
        "behaviors": output_dir / f"{PREFIX}_behavior_diagnostics.jsonl",
        "shape_observations": output_dir / f"{PREFIX}_shape_observations.jsonl",
        "shape_report": output_dir / "finance_stopping_instrument_reset_shape_report.json",
        "model_discovery": output_dir / f"{PREFIX}_model_discovery.json",
    }


def _load_outcomes(path: Path) -> tuple[CapabilityRolloutOutcome, ...]:
    return tuple(
        CapabilityRolloutOutcome.model_validate_json(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    )


def _load_discovered_models(path: Path) -> tuple[str, ...]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or not isinstance(value.get("discovered_models"), list):
        raise ValueError("instrument-reset model discovery artifact is invalid")
    models = tuple(str(item) for item in value["discovered_models"])
    if not models:
        raise ValueError("instrument-reset model discovery artifact is empty")
    return models


def _make_report(
    reset: FrozenExecutionContractSnapshot,
    raw: InstrumentResetRawAudit,
    shape: FinanceStoppingShapePolicyReport | None,
) -> FinanceStoppingInstrumentResetReport:
    all_shapes = bool(shape and shape.all_shapes_contract_passing)
    values = {
        "contract_id": reset.contract_id,
        "instrument_audit_id": raw.audit_id,
        "instrument_status": raw.instrument_status,
        "shape_analysis_authorized": raw.shape_analysis_authorized,
        "shape_report_id": shape.report_id if shape else None,
        "boundary_candidate_admitted_count": (
            shape.boundary_candidate_admitted_count if shape else 0
        ),
        "runtime_control_pass_count": shape.runtime_control_pass_count if shape else 0,
        "all_shapes_admitted": all_shapes,
        "next_permitted_stage": (
            "instrument_reset_repair_only"
            if not raw.shape_analysis_authorized
            else (
                "fresh_three_population_shape_policy_preparation"
                if all_shapes
                else "stopping_shape_redesign_only"
            )
        ),
    }
    provisional = FinanceStoppingInstrumentResetReport.model_construct(
        report_id="pending", **values
    )
    return FinanceStoppingInstrumentResetReport(
        report_id=_artifact_id(
            provisional, "report_id", "finance_stopping_instrument_reset_report:"
        ),
        **values,
    )


def _make_manifest(
    *,
    reset: FrozenExecutionContractSnapshot,
    report: FinanceStoppingInstrumentResetReport,
    raw_audit: InstrumentResetRawAudit,
    shape_report: FinanceStoppingShapePolicyReport | None,
    output_dir: Path,
    report_path: Path,
    markdown_path: Path,
) -> dict[str, Any]:
    artifact_paths = {
        **_required_paths(output_dir),
        "report": report_path,
        "report_markdown": markdown_path,
    }
    artifact_hashes = {key: _sha256(path) for key, path in sorted(artifact_paths.items())}
    finalizer_path = Path(__file__).resolve()
    values: dict[str, Any] = {
        "schema_version": "finance_stopping_instrument_reset_manifest.v2",
        "contract_id": reset.contract_id,
        "report_id": report.report_id,
        "raw_audit_id": raw_audit.audit_id,
        "shape_report_id": shape_report.report_id if shape_report else None,
        "execution_implementation_manifest_hash": reset.implementation_manifest_hash,
        "finalizer_version": STOPPING_INSTRUMENT_RESET_FINALIZER_VERSION,
        "finalizer_sha256": _sha256(finalizer_path),
        "artifact_sha256": artifact_hashes,
        "api_execution_replayed": False,
        "deterministic_recomputation_passed": True,
        "aggregation_performed": raw_audit.shape_analysis_authorized,
        "shape_analysis_authorized": raw_audit.shape_analysis_authorized,
        "historical_shape_support_transferred": False,
        "pro_api_call_count": 0,
        "beneficiary_authorized": False,
        "exact_target_authorized": False,
        "gp_c_authorized": False,
        "production_contribution": 0.0,
    }
    values["finalization_id"] = canonical_hash(
        values, prefix="finance_stopping_instrument_reset_finalization:"
    )
    return values


def _require_jsonl_equal(path: Path, values: Sequence[Any]) -> None:
    stored = tuple(
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    )
    expected = tuple(item.model_dump(mode="json") for item in values)
    _require_equal(path.name, stored, expected)


def _require_equal(label: str, stored: Any, expected: Any) -> None:
    if canonical_hash(stored, prefix=f"instrument_reset_finalize:{label}:") != canonical_hash(
        expected, prefix=f"instrument_reset_finalize:{label}:"
    ):
        raise ValueError(f"frozen {label} differs from deterministic recomputation")


def _write_or_verify_json(path: Path, value: Any) -> None:
    if path.exists():
        _require_equal(path.name, json.loads(path.read_text(encoding="utf-8")), value)
        return
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_or_verify_text(path: Path, value: str) -> None:
    if path.exists():
        if path.read_text(encoding="utf-8") != value:
            raise ValueError(f"immutable finalization output differs: {path}")
        return
    path.write_text(value, encoding="utf-8")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Deterministically finalize an interrupted v25.45 run"
    )
    parser.add_argument("--contract", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    return parser


def main() -> None:
    args = _parser().parse_args()
    report = finalize_instrument_reset_run(
        contract_path=args.contract,
        output_dir=args.output_dir,
    )
    print(report.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
