"""Bounded wiring checks, not another audit or additional model calibration."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from trusted_synthesis.canonical_json import canonical_json_bytes
from trusted_synthesis.domains.finance.qa_vnext.runtime import (
    DurableStore,
    PublicQARuntime,
    evaluate_update_readonly,
)
from trusted_synthesis.domains.finance.qa_vnext.update_public_contract import (
    public_update_contract,
    publish_update_contract,
)

from ..finance_qa_vnext_model_execution.models import record, require, sha
from ..finance_qa_vnext_model_execution.plan import BASELINE_ENTRY, TaskPanel, seal_directory
from ..finance_qa_vnext_model_execution.qualification import _Artifacts
from ..finance_qa_vnext_model_execution.transport import (
    SYSTEM_PROMPT,
    TransportConfig,
    render_http_request,
)
from ..finance_qa_vnext_update_calibration.controls import isolated_receiver
from .plan import initial_request


class ZeroCallback:
    binding = record("six_zero_callback", provider_attempts=0)

    def generate(self, request: Any) -> bytes:
        raise AssertionError("entry controls cannot invoke a callback")


def run_controls(panel: TaskPanel, directory: Path, config: TransportConfig) -> dict[str, Any]:
    store = DurableStore(directory)
    require(
        config.system_prompt == SYSTEM_PROMPT
        and config.attempts_per_session == 32
        and config.maximum_pilot_attempts == 192,
        "six.full_configuration",
    )
    initial_rows, later_rows = [], []
    for group in ("C", "B", "S"):
        runtime = PublicQARuntime(
            panel.adapter(group),
            ZeroCallback(),
            directory / group,
            max_actions=12,
            max_submissions=32,
        )
        actual = runtime.request()
        require(
            canonical_json_bytes(actual)
            == canonical_json_bytes(initial_request(panel.adapter(group))),
            "six.real_initial_entry",
        )
        require(
            actual["state"]["accepted_claims"] == []
            and actual["state"]["pending_observation"] is None
            and actual["public_update_contract"] == public_update_contract(),
            "six.fresh_public_state",
        )
        initial_rows.append({"group": group, "request_id": actual["id"], "bounds": runtime.bounds})
    for label in ("branch_cdw_fy2015_fy2016", "share_disclosed_total", "share_reconstructed_total"):
        directory_path = panel.root / BASELINE_ENTRY / "sessions" / label
        files = _Artifacts(directory_path)
        session = files.json("session.json")
        for event in session["events"]:
            request = event["request"]
            if request["state"]["pending_observation"] is None:
                continue
            if "public_update_contract" not in request:
                request = publish_update_contract(request)
            http = render_http_request(
                request, config, session_id="offline_later_shape", attempt_index=0
            )
            for disposition in ("accept", "reject"):
                raw = canonical_json_bytes(isolated_receiver(request, disposition))
                evaluation = evaluate_update_readonly(raw, request)
                require(
                    evaluation["update_admitted"] is True
                    and evaluation["complete_accept"] == (disposition == "accept"),
                    "six.later_public_rule_admission",
                )
                index = len(later_rows)
                store.json(f"later/{index:02d}_request.json", request)
                store.write(f"later/{index:02d}_response.json", raw)
                later_rows.append(
                    {
                        "fixture": label,
                        "fixture_manifest_id": files.manifest["id"],
                        "fixture_session_id": session["id"],
                        "sequence": event["sequence"],
                        "observation_id": request["state"]["pending_observation"]["id"],
                        "operation": request["state"]["pending_observation"]["selected_action"][
                            "operation"
                        ],
                        "disposition": disposition,
                        "raw_sha256": sha(raw),
                        "http_body_bytes": http["body_byte_count"],
                        "evaluation": evaluation,
                    }
                )
    report = record(
        "repaired_entry_controls",
        initial_rows=initial_rows,
        later_shape_rows=later_rows,
        later_shape_control_count=len(later_rows),
        model_samples=0,
        provider_attempts=0,
        action_executions=0,
        update_commits=0,
        historical_fixture_operations_reexecuted=False,
        control_responses_used_as_online_prefix=False,
        passed=True,
    )
    store.json("report.json", report)
    seal_directory(store, kind="six_entry_controls_manifest", report_id=report["id"])
    return report
