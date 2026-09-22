"""Report-auditor checks only; no experimental model, scoring, or GPU work."""

import importlib
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
a = importlib.import_module("audit_fixed_kernel_delayed_C_report_20260922")


def test_fixed_cohort_rejects_duplicate_task():
    tasks = {str(i): "group" for i in range(180)}
    rows = [dict(task_id=str(i), group="group", Q=i % 2) for i in range(180)]
    assert sum(a.outcomes(rows, tasks).values()) == 90
    rows[-1] = rows[0]
    with pytest.raises(ValueError, match="unique_registered_task"):
        a.outcomes(rows, tasks)


def test_fixed_cohort_rejects_changed_group_and_nonbinary_Q():
    tasks = {str(i): "group" for i in range(180)}
    rows = [dict(task_id=str(i), group="group", Q=0) for i in range(180)]
    rows[0]["Q"] = 2
    with pytest.raises(ValueError, match="fixed_group_and_binary_score"):
        a.outcomes(rows, tasks)
    rows[0].update(Q=0, group="changed")
    with pytest.raises(ValueError, match="fixed_group_and_binary_score"):
        a.outcomes(rows, tasks)


def test_pairing_keeps_regressions_and_fixed_denominator():
    result = a.paired(dict(a=0, b=1, c=1, d=0), dict(a=1, b=0, c=1, d=0))
    assert result == dict(
        static0_delayed1=1, static1_delayed0=1, both1=1, both0=1, net=0, denominator=4
    )
    with pytest.raises(ValueError, match="paired_task_set"):
        a.paired(dict(a=1), dict(b=1))


def test_tampered_record_is_rejected(tmp_path):
    body = dict(schema_version="fixed_kernel_value.v1.test", qualified=1)
    value = dict(body, id="test:" + a.digest(a.canonical(body)))
    path = tmp_path / "report.json"
    path.write_bytes(a.canonical(value))
    evidence = a.Evidence(tmp_path, tmp_path / "raw")
    assert evidence.read(path) == value
    assert evidence.rows["ROOT/report.json"]["content_id_checked"]
    value["qualified"] = 2
    path.write_bytes(a.canonical(value))
    with pytest.raises(ValueError, match="record_identity"):
        a.Evidence(tmp_path, tmp_path / "raw").read(path)
