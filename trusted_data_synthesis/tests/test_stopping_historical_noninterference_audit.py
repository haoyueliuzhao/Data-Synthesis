from __future__ import annotations

import json
from pathlib import Path

from trusted_synthesis.experiments.vtdo_experiment.phase1_stopping_historical_noninterference_audit import (  # noqa: E501
    audit_historical_records,
)


def _write_records(path: Path, records: list[dict[str, object]]) -> None:
    path.write_text(
        "".join(json.dumps(item) + "\n" for item in records),
        encoding="utf-8",
    )


def test_historical_audit_finds_recursive_observation_contamination(tmp_path: Path) -> None:
    path = tmp_path / "records.jsonl"
    _write_records(
        path,
        [
            {
                "task_artifact_id": "task:1",
                "observations": [
                    {
                        "result": {
                            "completion_state": {
                                "host_event": "observe:typed_host_state"
                            }
                        },
                        "host_events": ["observe:typed_host_state"],
                    }
                ],
            }
        ],
    )

    audit = audit_historical_records(path)

    assert audit.recursive_host_isolation_status == "failed"
    assert audit.contaminated_observation_count == 1
    assert audit.contaminated_task_count == 1
    assert audit.authorization_eligible is False
    assert audit.historical_shape_support_transferred is False


def test_historical_audit_keeps_missing_prompt_payload_status_unknown(tmp_path: Path) -> None:
    path = tmp_path / "records.jsonl"
    _write_records(
        path,
        [{"task_artifact_id": "task:1", "observations": [{"result": {"value": 7}}]}],
    )

    audit = audit_historical_records(path)

    assert audit.recursive_host_isolation_status == "unknown"
    assert audit.contaminated_observation_count == 0
    assert audit.notes == ("actual_model_prompt_payloads_not_frozen_for_every_record",)
