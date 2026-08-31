from __future__ import annotations

import json
from pathlib import Path

import pytest

from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_minimal_exact_route_online_diagnostic as diagnostic,
)

AUTHORIZATION = Path(
    "/home/zhuxinrui/.codex/attachments/69cfc83c-d7a8-4d6a-8d07-f8f9250f3e96/pasted-text.txt"
)


def _package_root() -> Path:
    return Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def prepared_base(tmp_path_factory: pytest.TempPathFactory) -> diagnostic.PreparedDiagnostic:
    output = tmp_path_factory.mktemp("v26-191-prepare") / "unused-output"
    return diagnostic.prepare(
        package_root=_package_root(),
        output_dir=output,
        authorization_path=AUTHORIZATION,
    )


def _prepared(base: diagnostic.PreparedDiagnostic, output: Path) -> diagnostic.PreparedDiagnostic:
    return diagnostic.PreparedDiagnostic(
        package_root=base.package_root,
        output_dir=output,
        authorization_bytes=base.authorization_bytes,
        prepare_audit=base.prepare_audit,
        first_frozen_prompt=base.first_frozen_prompt,
        first_frozen_body=base.first_frozen_body,
    )


def _success_body(label: str) -> bytes:
    if label == "D0":
        return json.dumps({"data": [{"id": diagnostic.MODEL}]}).encode()
    return b'{"id":"redacted-success","choices":[]}'


def test_prepare_binds_exact_authorization_and_first_frozen_prompt(
    prepared_base: diagnostic.PreparedDiagnostic,
) -> None:
    audit = prepared_base.prepare_audit
    assert audit.external_audit_sha256 == diagnostic.EXTERNAL_AUDIT_SHA256
    assert audit.first_frozen_prompt_utf8_bytes >= 12_053
    assert audit.first_frozen_request_body_bytes >= 13_418
    assert audit.first_v188_certificate_match
    assert audit.provider_calls_during_prepare == 0
    assert audit.credentials_read_during_prepare == 0


def test_current_route_healthy_branch_is_fresh_and_bounded(
    prepared_base: diagnostic.PreparedDiagnostic, tmp_path: Path
) -> None:
    def transport(
        request: diagnostic.DiagnosticRequest, body: bytes | None, api_key: str
    ) -> diagnostic.RawTransportResult:
        assert api_key == "test-secret"
        if request.method == "POST":
            assert body is not None
            assert diagnostic._sha256_bytes(body) == request.request_body_sha256  # noqa: SLF001
        return diagnostic.RawTransportResult(
            status=200,
            headers={"x-request-id": f"request-{request.label}"},
            body=_success_body(request.label),
        )

    output = tmp_path / "healthy"
    report = diagnostic.execute(
        prepared=_prepared(prepared_base, output),
        api_key="test-secret",
        urllib_transport=transport,
        curl_transport=transport,
    )
    assert report["decision"] == "current_route_healthy"
    assert report["online_http_request_count"] == 5
    assert report["old_v188_job_rerun_count"] == 0
    assert report["recovery_job_count"] == 0
    assert report["v188_q_job"] == "0/192"
    observations = sorted((output / "observations").glob("*.json"))
    assert [path.stem.split("_", 1)[1] for path in observations] == [
        "D0",
        "D1",
        "D2",
        "D3",
        "D4",
    ]
    d1 = json.loads(observations[1].read_text())
    d2 = json.loads(observations[2].read_text())
    assert d1["request"]["request_body_sha256"] == d2["request"]["request_body_sha256"]


def test_parameter_failure_persists_only_typed_redacted_error(
    prepared_base: diagnostic.PreparedDiagnostic, tmp_path: Path
) -> None:
    secret = "sk-super-secret-value-that-must-never-persist"

    def transport(
        request: diagnostic.DiagnosticRequest, body: bytes | None, api_key: str
    ) -> diagnostic.RawTransportResult:
        del body
        if request.label in {"D3", "D4a"}:
            payload = {
                "error": {
                    "type": "invalid_request_error",
                    "code": "invalid_parameter",
                    "param": "thinking",
                    "message": f"invalid Bearer {api_key}; key={secret}",
                }
            }
            return diagnostic.RawTransportResult(
                status=400,
                headers={"request-id": "safe-request-id"},
                body=json.dumps(payload).encode(),
            )
        return diagnostic.RawTransportResult(
            status=200, headers={}, body=_success_body(request.label)
        )

    output = tmp_path / "parameter"
    report = diagnostic.execute(
        prepared=_prepared(prepared_base, output),
        api_key=secret,
        urllib_transport=transport,
        curl_transport=transport,
    )
    assert report["decision"] == "request_parameter_contract_failure"
    assert report["localized_request_contract_field"] == "thinking"
    assert report["online_http_request_count"] == 5
    persisted = b"".join(path.read_bytes() for path in output.rglob("*") if path.is_file())
    assert secret.encode() not in persisted
    observation_bytes = b"".join(
        path.read_bytes() for path in (output / "observations").glob("*.json")
    )
    assert b"Authorization" not in observation_bytes
    d4a = json.loads((output / "observations" / "05_D4a.json").read_text())
    assert d4a["error_body_schema"] == "typed_error"
    assert d4a["error_param"] == "thinking"
    assert "REDACTED" in d4a["error_message_redacted"]
    assert d4a["unchecked_raw_body_persisted"] is False


def test_paired_transport_control_localizes_python_surface(
    prepared_base: diagnostic.PreparedDiagnostic, tmp_path: Path
) -> None:
    def urllib_transport(
        request: diagnostic.DiagnosticRequest, body: bytes | None, api_key: str
    ) -> diagnostic.RawTransportResult:
        del body, api_key
        if request.label == "D0":
            return diagnostic.RawTransportResult(status=200, headers={}, body=_success_body("D0"))
        return diagnostic.RawTransportResult(
            status=400,
            headers={},
            body=b'{"error":{"message":"bad request","type":"invalid_request_error"}}',
        )

    def curl_transport(
        request: diagnostic.DiagnosticRequest, body: bytes | None, api_key: str
    ) -> diagnostic.RawTransportResult:
        del request, body, api_key
        return diagnostic.RawTransportResult(status=200, headers={}, body=b'{"ok":true}')

    output = tmp_path / "transport"
    report = diagnostic.execute(
        prepared=_prepared(prepared_base, output),
        api_key="test-secret",
        urllib_transport=urllib_transport,
        curl_transport=curl_transport,
    )
    assert report["decision"] == "client_transport_or_implicit_header_failure"
    assert report["online_http_request_count"] == 5
    assert (output / "observations" / "05_C_CURL.json").is_file()


def test_unrecognized_error_body_preview_is_bounded_and_redacted() -> None:
    secret = "sk-abcdefghijklmnopqrstuvwxyz0123456789"
    request = diagnostic._request(  # noqa: SLF001
        "DX",
        "POST",
        diagnostic.OFFICIAL_ENDPOINT,
        b"{}",
        ("messages",),
    )
    raw = diagnostic.RawTransportResult(
        status=400,
        headers={},
        body=(f"Bearer {secret} " + ("z" * 5000)).encode(),
    )
    projected = diagnostic._project(request, raw, secret)  # noqa: SLF001
    assert projected.error_body_schema == "unrecognized"
    assert projected.unrecognized_body_prefix_redacted is not None
    assert secret not in projected.unrecognized_body_prefix_redacted
    assert len(projected.unrecognized_body_prefix_redacted.encode()) <= 4096


def test_wrong_authorization_and_existing_output_fail_closed(
    prepared_base: diagnostic.PreparedDiagnostic, tmp_path: Path
) -> None:
    wrong = tmp_path / "wrong.txt"
    wrong.write_text("wrong")
    with pytest.raises(ValueError, match="authorization bytes differ"):
        diagnostic.prepare(
            package_root=_package_root(),
            output_dir=tmp_path / "wrong-output",
            authorization_path=wrong,
        )
    existing = tmp_path / "existing"
    existing.mkdir()
    with pytest.raises(FileExistsError):
        diagnostic.execute(
            prepared=_prepared(prepared_base, existing),
            api_key="test-secret",
        )


def test_explicit_private_credential_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    private = tmp_path / ".env"
    private.write_text("DEEPSEEK_API_KEY=test-secret\n")
    private.chmod(0o600)
    assert diagnostic._load_credential(tmp_path / "unused", private) == "test-secret"  # noqa: SLF001
    private.chmod(0o644)
    with pytest.raises(ValueError, match="must be private"):
        diagnostic._load_credential(tmp_path / "unused", private)  # noqa: SLF001
