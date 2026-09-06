from __future__ import annotations

from pathlib import Path

import pytest

from trusted_synthesis.domains.finance.qa_vnext.callbacks import PublicFixtureCallback
from trusted_synthesis.domains.finance.qa_vnext.measurement import audit_session
from trusted_synthesis.domains.finance.qa_vnext.protocol import ProtocolError
from trusted_synthesis.domains.finance.qa_vnext.runtime import PublicQARuntime
from trusted_synthesis.experiments.finance_qa_vnext_model_execution.plan import load_panel

ROOT = Path(__file__).resolve().parents[2]


class _ObservedStop(ProtocolError):
    code = "provider.timeout"
    evidence_id = "test-only-external-outcome-not-independently-certified"


@pytest.mark.parametrize("after", [0, 1, 2])
def test_observed_callback_stop_preserves_prefix_without_a_fabricated_submission(
    tmp_path: Path, after: int
) -> None:
    panel = load_panel(ROOT)
    adapter = panel.adapter("C")
    fixture = PublicFixtureCallback()

    class Callback:
        binding = fixture.binding
        count = 0

        def generate(self, request):
            if self.count == after:
                raise _ObservedStop("no public response")
            self.count += 1
            return fixture.generate(request)

    directory = tmp_path / "session"
    session = PublicQARuntime(
        adapter, Callback(), directory, max_submissions=32, max_actions=12
    ).run()
    assert len(session["events"]) == after
    assert session["final"] is None
    assert session["callback_stop"]["sequence"] == after
    assert (directory / f"turns/{after:03d}_request.json").exists()
    assert (directory / f"turns/{after:03d}_callback_stop.json").exists()
    assert not (directory / f"turns/{after:03d}_receipt.json").exists()
    assert not (directory / f"turns/{after:03d}_response.txt").exists()
    audited = audit_session(adapter, session, directory)
    assert audited["validation_passed"] is True
    assert audited["trajectory_valid"] is True
    assert audited["qualified"] is False
    assert audited["qa_valid"] is False
    assert audited["external_callback_stop_present"] is True
    assert audited["external_callback_stop_reason_verified_by_domain_audit"] is False
    assert audited["depth_is_completed_session"] is False
    assert audited["action_count"] == int(after > 0)
    assert audited["accepted_claim_count"] == int(after == 2)
