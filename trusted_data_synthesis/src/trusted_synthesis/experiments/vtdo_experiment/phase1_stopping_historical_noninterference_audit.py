from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.hashing import canonical_hash
from trusted_synthesis.runtime.tools import (
    RESERVED_HOST_RESULT_MARKERS,
    reserved_host_marker_paths,
    reserved_host_result_paths,
)

HISTORICAL_NONINTERFERENCE_AUDIT_VERSION = (
    "finance_stopping_historical_noninterference_audit.v1"
)
HISTORICAL_NONINTERFERENCE_REPORT_VERSION = (
    "finance_stopping_historical_noninterference_report.v1"
)
_PROMPT_FIELDS = (
    "plan_prompt",
    "decision_prompts",
    "model_prompt",
    "model_prompts",
    "prompt_payloads",
)


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class HistoricalNoninterferenceAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    records_path: str = Field(min_length=1)
    records_sha256: str = Field(min_length=1)
    record_count: int = Field(ge=0)
    observation_count: int = Field(ge=0)
    contaminated_observation_count: int = Field(ge=0)
    contaminated_task_count: int = Field(ge=0)
    recursive_host_field_violation_count: int = Field(ge=0)
    recursive_host_marker_violation_count: int = Field(ge=0)
    prompt_payload_record_count: int = Field(ge=0)
    prompt_payload_count: int = Field(ge=0)
    prompt_contamination_count: int = Field(ge=0)
    recursive_host_isolation_status: Literal["passed", "failed", "unknown"]
    authorization_eligible: Literal[False] = False
    historical_shape_support_transferred: Literal[False] = False
    notes: tuple[str, ...]
    schema_version: str = HISTORICAL_NONINTERFERENCE_AUDIT_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> HistoricalNoninterferenceAudit:
        violations = (
            self.recursive_host_field_violation_count
            + self.recursive_host_marker_violation_count
            + self.prompt_contamination_count
        )
        expected = (
            "failed"
            if violations
            else ("passed" if self.prompt_payload_record_count == self.record_count else "unknown")
        )
        if self.recursive_host_isolation_status != expected:
            raise ValueError("Historical noninterference status is inconsistent")
        if self.audit_id != _artifact_id(self, "audit_id", "historical_noninterference_audit:"):
            raise ValueError("Historical noninterference audit identity is invalid")
        return self


class HistoricalNoninterferenceReport(FrozenModel):
    report_id: str = Field(min_length=1)
    audits: tuple[HistoricalNoninterferenceAudit, ...] = Field(min_length=1)
    failed_artifact_count: int = Field(ge=0)
    unknown_artifact_count: int = Field(ge=0)
    passed_artifact_count: int = Field(ge=0)
    historical_shape_support_transferred: Literal[False] = False
    authorization_eligible: Literal[False] = False
    schema_version: str = HISTORICAL_NONINTERFERENCE_REPORT_VERSION

    @model_validator(mode="after")
    def validate_report(self) -> HistoricalNoninterferenceReport:
        counts = {
            status: sum(item.recursive_host_isolation_status == status for item in self.audits)
            for status in ("failed", "unknown", "passed")
        }
        if (
            self.failed_artifact_count != counts["failed"]
            or self.unknown_artifact_count != counts["unknown"]
            or self.passed_artifact_count != counts["passed"]
        ):
            raise ValueError("Historical noninterference report counts are inconsistent")
        if self.report_id != _artifact_id(
            self, "report_id", "historical_noninterference_report:"
        ):
            raise ValueError("Historical noninterference report identity is invalid")
        return self


def audit_historical_records(path: Path) -> HistoricalNoninterferenceAudit:
    records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
    observation_count = 0
    contaminated_observations = 0
    contaminated_tasks: set[str] = set()
    host_field_violations = 0
    host_marker_violations = 0
    prompt_record_count = 0
    prompt_count = 0
    prompt_contamination_count = 0

    for record in records:
        task_id = str(record.get("task_artifact_id") or record.get("task_id") or "unknown")
        prompt_payloads = _prompt_payloads(record)
        if prompt_payloads:
            prompt_record_count += 1
        for prompt in prompt_payloads:
            prompt_count += 1
            if _prompt_contaminated(prompt):
                prompt_contamination_count += 1
                contaminated_tasks.add(task_id)
        for observation in record.get("observations", ()):
            observation_count += 1
            result = observation.get("result", {})
            outer_events = tuple(str(item) for item in observation.get("host_events", ()))
            fields = reserved_host_result_paths(result)
            markers = reserved_host_marker_paths(
                result,
                markers=frozenset((*RESERVED_HOST_RESULT_MARKERS, *outer_events)),
            )
            host_field_violations += len(fields)
            host_marker_violations += len(markers)
            if fields or markers:
                contaminated_observations += 1
                contaminated_tasks.add(task_id)

    violations = host_field_violations + host_marker_violations + prompt_contamination_count
    status: Literal["passed", "failed", "unknown"] = (
        "failed"
        if violations
        else ("passed" if prompt_record_count == len(records) else "unknown")
    )
    notes = []
    if status == "unknown":
        notes.append("actual_model_prompt_payloads_not_frozen_for_every_record")
    if status == "failed":
        notes.append("historical_artifact_remains_immutable_and_diagnostic_only")
    values = {
        "records_path": str(path.resolve()),
        "records_sha256": _sha256(path),
        "record_count": len(records),
        "observation_count": observation_count,
        "contaminated_observation_count": contaminated_observations,
        "contaminated_task_count": len(contaminated_tasks),
        "recursive_host_field_violation_count": host_field_violations,
        "recursive_host_marker_violation_count": host_marker_violations,
        "prompt_payload_record_count": prompt_record_count,
        "prompt_payload_count": prompt_count,
        "prompt_contamination_count": prompt_contamination_count,
        "recursive_host_isolation_status": status,
        "notes": tuple(notes),
    }
    provisional = HistoricalNoninterferenceAudit.model_construct(audit_id="pending", **values)
    return HistoricalNoninterferenceAudit(
        audit_id=_artifact_id(provisional, "audit_id", "historical_noninterference_audit:"),
        **values,
    )


def make_historical_report(paths: tuple[Path, ...]) -> HistoricalNoninterferenceReport:
    audits = tuple(audit_historical_records(path) for path in paths)
    values = {
        "audits": audits,
        "failed_artifact_count": sum(
            item.recursive_host_isolation_status == "failed" for item in audits
        ),
        "unknown_artifact_count": sum(
            item.recursive_host_isolation_status == "unknown" for item in audits
        ),
        "passed_artifact_count": sum(
            item.recursive_host_isolation_status == "passed" for item in audits
        ),
    }
    provisional = HistoricalNoninterferenceReport.model_construct(report_id="pending", **values)
    return HistoricalNoninterferenceReport(
        report_id=_artifact_id(
            provisional, "report_id", "historical_noninterference_report:"
        ),
        **values,
    )


def write_historical_report(
    paths: tuple[Path, ...], output_dir: Path
) -> HistoricalNoninterferenceReport:
    output_dir.mkdir(parents=True, exist_ok=False)
    report = make_historical_report(paths)
    json_path = output_dir / "finance_stopping_historical_noninterference_report.json"
    json_path.write_text(report.model_dump_json(indent=2) + "\n", encoding="utf-8")
    lines = [
        "# Historical Stopping Noninterference Audit",
        "",
        "This is a read-only lineage audit. It cannot authorize or re-score "
        "historical Shape results.",
        "",
        f"- Failed artifacts: **{report.failed_artifact_count}**",
        f"- Unknown artifacts: **{report.unknown_artifact_count}**",
        f"- Passed artifacts: **{report.passed_artifact_count}**",
        "- Historical Shape support transferred: **false**",
        "",
        "| Artifact | Records | Observations | Contaminated | Prompt status | Isolation |",
        "| --- | ---: | ---: | ---: | ---: | --- |",
    ]
    for item in report.audits:
        lines.append(
            "| "
            f"{Path(item.records_path).parent.name} | {item.record_count} | "
            f"{item.observation_count} | {item.contaminated_observation_count} | "
            f"{item.prompt_payload_record_count}/{item.record_count} | "
            f"{item.recursive_host_isolation_status} |"
        )
    (output_dir / "finance_stopping_historical_noninterference_report.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )
    return report


def _prompt_payloads(record: dict[str, Any]) -> tuple[Any, ...]:
    values: list[Any] = []
    for container in (record, record.get("agent_audit", {})):
        if not isinstance(container, dict):
            continue
        for key in _PROMPT_FIELDS:
            value = container.get(key)
            if value is None:
                continue
            values.extend(value if isinstance(value, list) else (value,))
    return tuple(values)


def _prompt_contaminated(value: Any) -> bool:
    if reserved_host_result_paths(value, path="prompt"):
        return True
    if reserved_host_marker_paths(value, path="prompt"):
        return True
    rendered = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
    return any(marker in rendered for marker in RESERVED_HOST_RESULT_MARKERS)


def _artifact_id(value: BaseModel, field: str, prefix: str) -> str:
    return canonical_hash(value.model_dump(mode="json", exclude={field}), prefix=prefix)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description="Read-only historical Stopping audit")
    parser.add_argument("--records", action="append", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    report = write_historical_report(tuple(args.records), args.output_dir)
    print(report.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
