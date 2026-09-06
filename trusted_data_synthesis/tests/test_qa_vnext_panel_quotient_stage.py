"""Small wiring guards and immutable-directory controls, not another historical audit."""

import pytest

from trusted_synthesis.domains.finance.qa_vnext import measurement
from trusted_synthesis.domains.finance.qa_vnext.protocol import ProtocolError
from trusted_synthesis.domains.finance.qa_vnext.runtime import DurableStore
from trusted_synthesis.experiments.finance_qa_vnext_model_execution import (
    qualification,
    representation,
)
from trusted_synthesis.experiments.finance_qa_vnext_model_execution.models import record
from trusted_synthesis.experiments.finance_qa_vnext_model_execution.plan import (
    seal_directory,
    verify_directory,
)
from trusted_synthesis.experiments.finance_qa_vnext_panel_quotient import stage
from trusted_synthesis.experiments.finance_qa_vnext_panel_quotient.guards import (
    guard_report,
    measurement_guard,
)


@pytest.mark.parametrize(
    "owner,attribute",
    [
        (qualification, "qualify_session"),
        (measurement, "audit_session"),
        (measurement, "_validate"),
        (representation, "encode_original_candidate"),
        (representation, "register_tokenizer"),
        (representation, "tokenize_candidates"),
        (representation.frozen_tokenizer_assets, "load_tokenizer"),
        (representation.frozen_tokenizer_assets, "_load_local"),
    ],
)
def test_measurement_blocks_old_recomputation_before_entry(owner, attribute):
    with measurement_guard() as counts:
        with pytest.raises(RuntimeError, match="panel_quotient.forbidden"):
            getattr(owner, attribute)()
    assert sum(counts.values()) == 1  # the forbidden entry is stopped before any execution


def test_empty_guard_report_is_zero():
    with measurement_guard() as counts:
        result = guard_report(counts, "constructed_wiring_check")
    assert result["all_zero"] and not result["cuda_initialized"]


def test_only_additive_artifact_target_allowed(tmp_path):
    root = tmp_path / "repo"
    for target in (
        root,
        root / "trusted_data_synthesis/artifacts/qa_vnext_task_panel",
        root / stage.ARTIFACT_PREFIX,
    ):
        with pytest.raises(ProtocolError):
            stage._target(root, target)
    _, target = stage._target(root, root / stage.ARTIFACT_PREFIX / "isolated-control")
    assert target == root / stage.ARTIFACT_PREFIX / "isolated-control"


def test_partial_or_changed_measurement_directory_never_silently_overwritten(tmp_path):
    directory = tmp_path / "partial"
    store = DurableStore(directory)
    store.json("report.json", record("panel_quotient_constructed_report", control_evidence=True))
    with pytest.raises(FileNotFoundError):
        verify_directory(directory, kind="panel_quotient_measurement_manifest")
    seal_directory(store, kind="panel_quotient_measurement_manifest", condition_id="constructed")
    assert (
        verify_directory(directory, kind="panel_quotient_measurement_manifest")["condition_id"]
        == "constructed"
    )
    store.json("unexpected.json", {"control": True})
    with pytest.raises(ProtocolError, match="manifest.complete_members"):
        verify_directory(directory, kind="panel_quotient_measurement_manifest")
