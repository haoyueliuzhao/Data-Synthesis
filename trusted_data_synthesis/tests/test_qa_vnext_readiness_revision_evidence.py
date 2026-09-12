"""Saved-evidence admission integration over wholly synthetic control archives."""

import json

import pytest
from test_qa_vnext_readiness_revision_reassessment import synthetic_parent, token_fixture

from trusted_synthesis.experiments.finance_qa_vnext_catalog_bridge.catalog import Parent
from trusted_synthesis.experiments.finance_qa_vnext_eval_readiness.runtime import encode
from trusted_synthesis.experiments.finance_qa_vnext_readiness_revision import reassessment, stage
from trusted_synthesis.experiments.finance_qa_vnext_task_build.archive import (
    record,
    sha,
    write_json,
)


def _replace_synthetic_record(path, kind, payload):
    result = record(
        kind,
        **{key: value for key, value in payload.items() if key not in {"id", "schema_version"}},
    )
    path.write_bytes(encode(result))
    return result


@pytest.mark.parametrize("mutation", [None, "summary_passed_count", "saved_row_expectation"])
def test_saved_control_evidence_does_not_trust_resealed_summary(tmp_path, monkeypatch, mutation):
    old_directory, old_manifest, _ = synthetic_parent(tmp_path)
    successor = tmp_path / "synthetic_revision"

    def synthetic_materializer(packages, root):
        assert root == tmp_path
        return token_fixture(packages)

    qualification = reassessment.run(
        tmp_path,
        successor / "controls",
        old_directory.relative_to(tmp_path),
        expected_parent_manifest_id=old_manifest["id"],
        freeze_id="synthetic-revision-only",
        materializer=synthetic_materializer,
    )
    assert qualification["status"] == "PASS"
    if mutation == "summary_passed_count":
        qualification["passed_count"] = 69
    elif mutation == "saved_row_expectation":
        path = tmp_path / qualification["reassessments_path"]
        saved = json.loads(path.read_bytes())
        row = saved["rows"][0]
        row["expected_financial_valid"] = not row["expected_financial_valid"]
        saved["rows"][0] = record(
            "fixed_control_reassessment",
            **{key: value for key, value in row.items() if key not in {"id", "schema_version"}},
        )
        _replace_synthetic_record(path, "fixed_control_reassessment_rows", saved)
        qualification["reassessments_sha256"] = sha(path)
    if mutation is not None:
        qualification = _replace_synthetic_record(
            successor / "controls/report.json", "fixed_control_reassessment_report", qualification
        )
    write_json(
        successor / "report.json",
        record("readiness_revision_preparation_report", qualification=qualification),
    )
    sealed = stage.seal(successor, scope="synthetic saved-evidence integration only")
    prepared = Parent(tmp_path, successor.relative_to(tmp_path), sealed["id"])
    old = Parent(tmp_path, old_directory.relative_to(tmp_path), old_manifest["id"])
    monkeypatch.setattr(
        stage.provenance, "parents", lambda root, verify_members=False: (old, None, None)
    )
    if mutation is None:
        assert stage.verify_control_evidence(tmp_path, prepared) == qualification
    else:
        expected = (
            "revision.qualification_summary_from_all_saved_results"
            if mutation == "summary_passed_count"
            else "revision.original_expectations_and_session_parents"
        )
        with pytest.raises(ValueError, match=expected):
            stage.verify_control_evidence(tmp_path, prepared)
