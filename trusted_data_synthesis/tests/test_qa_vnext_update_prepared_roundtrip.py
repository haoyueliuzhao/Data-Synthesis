"""Actual committed-source prepare/readback plus 24 local mock calls, never Provider calls."""

from __future__ import annotations

import json
import socket
from pathlib import Path

import pytest

from trusted_synthesis.canonical_json import canonical_json_bytes
from trusted_synthesis.domains.finance.qa_vnext.runtime import PublicQARuntime
from trusted_synthesis.domains.finance.qa_vnext.update_public_contract import (
    publish_update_contract,
)
from trusted_synthesis.experiments.finance_qa_vnext_model_execution.transport import HTTPResponse
from trusted_synthesis.experiments.finance_qa_vnext_update_calibration import plan, runner
from trusted_synthesis.experiments.finance_qa_vnext_update_calibration.controls import (
    isolated_receiver,
)
from trusted_synthesis.experiments.finance_qa_vnext_update_calibration.evidence import audit_call
from trusted_synthesis.experiments.finance_qa_vnext_update_calibration.models import read

ROOT = Path(__file__).resolve().parents[2]


def test_actual_committed_preparation_and_full_mock_run_roundtrip(tmp_path, monkeypatch):
    """No source snapshot, preparation, historical-input, public-control or reader mock."""
    counters = {"network": 0, "runtime": 0, "real_credential": 0, "mock_http": 0}

    def forbidden_network(*args, **kwargs):
        counters["network"] += 1
        pytest.fail("actual preparation roundtrip may not open a network connection")

    def forbidden_runtime(*args, **kwargs):
        counters["runtime"] += 1
        pytest.fail("calibration must not construct a Runtime")

    def forbidden_credential(*args, **kwargs):
        counters["real_credential"] += 1
        pytest.fail("prepare and analyze must not read credentials")

    monkeypatch.setattr(socket.socket, "connect", forbidden_network)
    monkeypatch.setattr(socket, "create_connection", forbidden_network)
    monkeypatch.setattr(PublicQARuntime, "__init__", forbidden_runtime)
    monkeypatch.setattr(runner, "_credential", forbidden_credential)
    prep = tmp_path / "preparation"
    design = (
        ROOT / "trusted_data_synthesis/docs/finance_qa_vnext_update_public_contract_calibration.md"
    )
    prepared = plan.prepare(ROOT, prep, design, run_tag="local-mock-committed-roundtrip")
    assert prepared["prepared"] and prepared["provider_calls"] == 0
    frozen = plan.prepared(ROOT, prep)
    assert len(frozen["registrations"]) == 24
    assert not (tmp_path / "execution").exists()
    assert read(prep / "controls.json")["provider_calls"] == 0
    assert len(read(prep / "controls.json")["rows"]) >= 112
    assert set(counters.values()) == {0}
    original_callback = runner.OnlineModelCallback

    class LocalSender:
        def send(self, http, *, api_key):
            counters["mock_http"] += 1
            public = json.loads(http["messages"][1]["content"])
            if "public_update_contract" not in public:
                public = publish_update_contract(public)
            response = isolated_receiver(public, "accept")
            return HTTPResponse(
                200,
                canonical_json_bytes(
                    {
                        "id": "local-mock-never-provider",
                        "object": "chat.completion",
                        "model": "deepseek-v4-pro",
                        "choices": [
                            {
                                "index": 0,
                                "finish_reason": "stop",
                                "message": {
                                    "role": "assistant",
                                    "content": canonical_json_bytes(response).decode(),
                                },
                            }
                        ],
                        "usage": {
                            "prompt_tokens": 200,
                            "completion_tokens": 10,
                            "total_tokens": 210,
                        },
                    }
                ),
            )

    def callback(config, **kwargs):
        return original_callback(config, **kwargs, sender=LocalSender())

    def local_audit(root, directory, registration, public, http):
        return audit_call(root, directory, registration, public, http, require_live=False)

    monkeypatch.setattr(runner, "OnlineModelCallback", callback)
    monkeypatch.setattr(runner, "audit_call", local_audit)
    monkeypatch.setattr(runner, "_credential", lambda path: "not-a-real-key-never-sent")
    report = runner.run(ROOT, prep)
    assert report["execution_evidence_complete"]
    assert report["overall"]["O"]["successes"] == report["overall"]["R"]["successes"] == 12
    assert all(not row["model_sample"] for row in read(tmp_path / "execution/audits.json").values())
    monkeypatch.setattr(runner, "_credential", forbidden_credential)
    reanalysis = runner.analyze(ROOT, prep, tmp_path / "reanalysis")
    assert reanalysis == report
    assert (tmp_path / "execution/report.json").read_bytes() == (
        tmp_path / "reanalysis/report.json"
    ).read_bytes()
    assert counters == {"network": 0, "runtime": 0, "real_credential": 0, "mock_http": 24}
