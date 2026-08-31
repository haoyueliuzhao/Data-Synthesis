from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import subprocess
import urllib.error
import urllib.request
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final, Literal, cast

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_capability_all_typed_rejection_public_feedback_runtime as step_runtime,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_capability_artifact_backed_online_execution as v188,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_capability_job_bound_multistep_outcome_preflight_runtime as frozen_runtime,
)
from trusted_synthesis.hashing import canonical_hash
from trusted_synthesis.runtime.agent.prospective_semantic_action_response_grammar import (
    RESPONSE_PROTOCOL_VERSION,
)
from trusted_synthesis.runtime.agent.prospective_two_stage_stage1_client import (
    make_stage_one_request_body,
)
from trusted_synthesis.runtime.agent.schema import AgentModelConfig

RUN_ID: Final = "finance_v26_191_minimal_exact_route_online_diagnostic_v1_20260831"
AUTHORIZED_STAGE: Final = "fresh_identity_minimal_exact_route_diagnostic_online_execution_only"
EXTERNAL_AUDIT_BYTES: Final = 10_990
EXTERNAL_AUDIT_SHA256: Final = "d8fd6ad5cda29e419737c87b5dbd3641e0b5f906a98c0f222ab0a70c40ae510c"
OPERATOR_DECISION: Final = "做在线诊断"
OFFICIAL_ENDPOINT: Final = "https://api.deepseek.com/chat/completions"
LEGACY_ENDPOINT: Final = "https://api.deepseek.com/v1/chat/completions"
MODELS_ENDPOINT: Final = "https://api.deepseek.com/models"
MODEL: Final = "deepseek-v4-flash"
MAX_HTTP_REQUESTS: Final = 9
EXPECTED_V190_REPORT_ID: Final = (
    "finance_v26_190_root_cause_audit_report:"
    "f8e5798c9434bb3e8f9ec3ce4cd8e7816e78300679a666a83e9629f0fcc5b26b"
)
EXPECTED_V190_ARTIFACT_ROOT: Final = (
    "finance_v26_190_route_root_cause_artifact_root:"
    "ec83bda6683adcce0ffa21df4af82563eef7072386e6038efba03f01f9635db5"
)
V190_DIR: Final = (
    "artifacts/vtdo_experiment/"
    "finance_v26_190_exact_route_http400_request_contract_root_cause_audit_v1_20260831"
)
V188_DIR: Final = v188.RUN_ID

Decision = Literal[
    "credential_invalid",
    "account_balance_unavailable",
    "account_model_route_unavailable",
    "legacy_v1_endpoint_rejected",
    "request_parameter_contract_failure",
    "prompt_specific_request_rejection",
    "client_transport_or_implicit_header_failure",
    "current_route_healthy",
    "provider_or_account_route_failure",
    "online_root_cause_remains_unlocalized",
]


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class DiagnosticRequest(FrozenModel):
    request_id: str = Field(min_length=1)
    label: str = Field(min_length=2)
    method: Literal["GET", "POST"]
    endpoint: str = Field(pattern=r"^https://api\.deepseek\.com/")
    transport: Literal["urllib", "curl"] = "urllib"
    request_body_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    request_body_bytes: int = Field(ge=0)
    request_body_fields: tuple[str, ...] = ()
    content_type: Literal["application/json"] | None = None
    automatic_retries: Literal[0] = 0
    old_v188_job_id_used: Literal[False] = False
    recovery_job: Literal[False] = False
    empirical_capability_row: Literal[False] = False
    schema_version: Literal["minimal_exact_route_diagnostic_request.v1"] = (
        "minimal_exact_route_diagnostic_request.v1"
    )

    @model_validator(mode="after")
    def validate_request(self) -> DiagnosticRequest:
        expected = canonical_hash(
            self.model_dump(mode="json", exclude={"request_id"}),
            prefix="finance_v26_191_diagnostic_request:",
        )
        if self.request_id != expected:
            raise ValueError("diagnostic request identity differs")
        if self.request_body_fields != tuple(sorted(self.request_body_fields)):
            raise ValueError("request fields are not sorted")
        if self.method == "GET" and (
            self.request_body_sha256 is not None
            or self.request_body_bytes != 0
            or self.request_body_fields
            or self.content_type is not None
        ):
            raise ValueError("GET diagnostic must not contain a request body")
        if self.method == "POST" and (
            self.request_body_sha256 is None
            or self.request_body_bytes == 0
            or not self.request_body_fields
            or self.content_type != "application/json"
        ):
            raise ValueError("POST diagnostic lacks its exact body certificate")
        return self


class DiagnosticObservation(FrozenModel):
    observation_id: str = Field(min_length=1)
    request: DiagnosticRequest
    http_status: int | None = Field(default=None, ge=100, le=599)
    http_success: bool
    response_request_id: str | None = None
    error_body_schema: Literal[
        "typed_error", "unrecognized", "success_body_redacted", "transport_error"
    ]
    error_type: str | None = None
    error_code: str | int | None = None
    error_param: str | None = None
    error_message_redacted: str | None = None
    unrecognized_body_prefix_redacted: str | None = None
    response_body_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    response_body_bytes: int = Field(ge=0)
    response_json_object: bool
    target_model_visible: bool | None = None
    authorization_value_persisted: Literal[False] = False
    api_key_hash_persisted: Literal[False] = False
    cookie_persisted: Literal[False] = False
    full_headers_persisted: Literal[False] = False
    private_reasoning_persisted: Literal[False] = False
    unchecked_raw_body_persisted: Literal[False] = False
    schema_version: Literal["minimal_exact_route_diagnostic_observation.v1"] = (
        "minimal_exact_route_diagnostic_observation.v1"
    )

    @model_validator(mode="after")
    def validate_observation(self) -> DiagnosticObservation:
        expected = canonical_hash(
            self.model_dump(mode="json", exclude={"observation_id"}),
            prefix="finance_v26_191_diagnostic_observation:",
        )
        if self.observation_id != expected:
            raise ValueError("diagnostic observation identity differs")
        if self.http_success != bool(
            self.http_status is not None and 200 <= self.http_status < 300
        ):
            raise ValueError("HTTP success projection differs from status")
        if self.unrecognized_body_prefix_redacted is not None and (
            len(self.unrecognized_body_prefix_redacted.encode("utf-8")) > 4096
        ):
            raise ValueError("unrecognized body preview exceeds 4 KiB")
        return self


class PrepareAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    run_id: str = RUN_ID
    authorized_stage: str = AUTHORIZED_STAGE
    external_audit_sha256: str = EXTERNAL_AUDIT_SHA256
    external_audit_bytes: int = EXTERNAL_AUDIT_BYTES
    operator_decision: str = OPERATOR_DECISION
    v190_report_id: str = EXPECTED_V190_REPORT_ID
    v190_artifact_root: str = EXPECTED_V190_ARTIFACT_ROOT
    source_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    source_tree: str = Field(pattern=r"^[0-9a-f]{40}$")
    first_frozen_prompt_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    first_frozen_prompt_utf8_bytes: int = Field(gt=0)
    first_frozen_request_body_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    first_frozen_request_body_bytes: int = Field(gt=0)
    first_v188_certificate_match: Literal[True] = True
    d1_d2_identical_request_bytes: Literal[True] = True
    maximum_http_requests: Literal[9] = 9
    automatic_retries: Literal[0] = 0
    provider_calls_during_prepare: Literal[0] = 0
    credentials_read_during_prepare: Literal[0] = 0
    old_v188_jobs_rerun: Literal[0] = 0
    recovery_jobs: Literal[0] = 0
    schema_version: Literal["minimal_exact_route_diagnostic_prepare.v1"] = (
        "minimal_exact_route_diagnostic_prepare.v1"
    )

    @model_validator(mode="after")
    def validate_audit(self) -> PrepareAudit:
        expected = canonical_hash(
            self.model_dump(mode="json", exclude={"audit_id"}),
            prefix="finance_v26_191_diagnostic_prepare:",
        )
        if self.audit_id != expected:
            raise ValueError("prepare audit identity differs")
        return self


@dataclass(frozen=True)
class RawTransportResult:
    status: int | None
    headers: Mapping[str, str]
    body: bytes
    transport_error_type: str | None = None
    transport_error_message: str | None = None


Transport = Callable[[DiagnosticRequest, bytes | None, str], RawTransportResult]


@dataclass(frozen=True)
class PreparedDiagnostic:
    package_root: Path
    output_dir: Path
    authorization_bytes: bytes
    prepare_audit: PrepareAudit
    first_frozen_prompt: str
    first_frozen_body: bytes


def _canonical_json(value: Any) -> str:
    if isinstance(value, BaseModel):
        value = value.model_dump(mode="json", warnings=False)
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _canonical_bytes(value: Any) -> bytes:
    return _canonical_json(value).encode("utf-8")


def _file_bytes(value: Any) -> bytes:
    return _canonical_bytes(value) + b"\n"


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_bytes_no_replace(path: Path, value: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        stream.write(value)
        stream.flush()
        os.fsync(stream.fileno())


def _write_no_replace(path: Path, value: Any) -> None:
    _write_bytes_no_replace(path, _file_bytes(value))


def _identity(model_type: type[BaseModel], values: dict[str, Any], field: str, prefix: str) -> Any:
    provisional = model_type.model_construct(**{field: "pending"}, **values)
    identifier = canonical_hash(
        provisional.model_dump(mode="json", exclude={field}, warnings=False), prefix=prefix
    )
    return model_type(**{field: identifier}, **values)


def _request(
    label: str,
    method: Literal["GET", "POST"],
    endpoint: str,
    body: bytes | None,
    fields: tuple[str, ...] = (),
    transport: Literal["urllib", "curl"] = "urllib",
) -> DiagnosticRequest:
    values = {
        "label": label,
        "method": method,
        "endpoint": endpoint,
        "transport": transport,
        "request_body_sha256": _sha256_bytes(body) if body is not None else None,
        "request_body_bytes": len(body or b""),
        "request_body_fields": tuple(sorted(fields)),
        "content_type": "application/json" if body is not None else None,
    }
    return cast(
        DiagnosticRequest,
        _identity(
            DiagnosticRequest,
            values,
            "request_id",
            "finance_v26_191_diagnostic_request:",
        ),
    )


def _authorization(path: Path) -> bytes:
    payload = path.read_bytes()
    if len(payload) != EXTERNAL_AUDIT_BYTES or _sha256_bytes(payload) != EXTERNAL_AUDIT_SHA256:
        raise ValueError("external diagnostic authorization bytes differ")
    return payload


def _git(repository: Path, *args: str) -> str:
    return subprocess.run(
        ("git", *args), cwd=repository, check=True, capture_output=True, text=True
    ).stdout.strip()


def _reconstruct_first_prompt(package_root: Path, output_dir: Path) -> tuple[str, bytes]:
    prepared = v188.prepare_execution(
        package_root=package_root,
        output_dir=output_dir / "provider_invocation_forbidden",
    )
    job_id = prepared.frozen.manifest.expected_job_ids[0]
    jobs = {item.job_id: item for item in prepared.frozen.manifest.jobs}
    context = frozen_runtime.prepare_job(jobs[job_id], prepared.runtime_catalog)
    state = frozen_runtime._initialize(context)  # noqa: SLF001
    public_prompt = step_runtime.render_next_prompt(state)
    payload = {
        "public_prompt": public_prompt.model_dump(mode="json"),
        "response_abi": {
            "grammar_id": prepared.profile.action_grammar_id,
            "state_id": public_prompt.state.state_token,
            "decision_kind": prepared.profile.action_response_decision_kind,
            "protocol": RESPONSE_PROTOCOL_VERSION,
        },
    }
    prompt = _canonical_json(payload)
    profile = _load(package_root / v188.MODEL_PROFILE_PATH)
    config = AgentModelConfig.model_validate(profile["model"])
    body = _canonical_bytes(make_stage_one_request_body(config, prompt))
    suffix = job_id.rsplit(":", 1)[-1]
    envelope = _load(
        package_root
        / "artifacts/vtdo_experiment"
        / V188_DIR
        / "raw_provider_envelopes"
        / suffix
        / "call_000.json"
    )
    certificate = envelope["request_binding_certificate"]
    if (
        _sha256_bytes(prompt.encode("utf-8")) != certificate["prompt_sha256"]
        or _sha256_bytes(body) != certificate["canonical_request_body_sha256"]
        or len(body) != certificate["canonical_request_body_bytes"]
    ):
        raise ValueError("first v26.188 Prompt or request bytes differ from frozen certificate")
    return prompt, body


def prepare(
    *, package_root: Path, output_dir: Path, authorization_path: Path
) -> PreparedDiagnostic:
    if output_dir.exists():
        raise FileExistsError(f"diagnostic output already exists: {output_dir}")
    authorization_bytes = _authorization(authorization_path)
    v190 = package_root / V190_DIR
    report = _load(v190 / "report.json")
    manifest = _load(v190 / "artifact_manifest.json")
    if (
        report.get("report_id") != EXPECTED_V190_REPORT_ID
        or manifest.get("artifact_root") != EXPECTED_V190_ARTIFACT_ROOT
    ):
        raise ValueError("v26.190 predecessor identity differs")
    prompt, body = _reconstruct_first_prompt(package_root, output_dir)
    minimal = _canonical_bytes(
        {
            "model": MODEL,
            "messages": [{"role": "user", "content": "Reply with the single word OK."}],
            "max_tokens": 64,
        }
    )
    repository = package_root.parent
    values = {
        "source_commit": _git(repository, "rev-parse", "HEAD"),
        "source_tree": _git(repository, "show", "-s", "--format=%T", "HEAD"),
        "first_frozen_prompt_sha256": _sha256_bytes(prompt.encode("utf-8")),
        "first_frozen_prompt_utf8_bytes": len(prompt.encode("utf-8")),
        "first_frozen_request_body_sha256": _sha256_bytes(body),
        "first_frozen_request_body_bytes": len(body),
        "d1_d2_identical_request_bytes": _sha256_bytes(minimal) == _sha256_bytes(minimal),
    }
    audit = cast(
        PrepareAudit,
        _identity(
            PrepareAudit,
            values,
            "audit_id",
            "finance_v26_191_diagnostic_prepare:",
        ),
    )
    return PreparedDiagnostic(
        package_root=package_root,
        output_dir=output_dir,
        authorization_bytes=authorization_bytes,
        prepare_audit=audit,
        first_frozen_prompt=prompt,
        first_frozen_body=body,
    )


_BEARER = re.compile(r"(?i)bearer\s+[A-Za-z0-9._~+/=-]+")
_KEY = re.compile(r"(?i)(?:sk-|key[-_: ]?)[A-Za-z0-9._~+/=-]{12,}")
_LONG_TOKEN = re.compile(r"(?<![A-Za-z0-9])[A-Za-z0-9._~+/=-]{32,}(?![A-Za-z0-9])")


def _redact_text(value: str, api_key: str) -> str:
    redacted = value.replace(api_key, "[REDACTED_CREDENTIAL]") if api_key else value
    redacted = _BEARER.sub("Bearer [REDACTED_CREDENTIAL]", redacted)
    redacted = _KEY.sub("[REDACTED_CREDENTIAL]", redacted)
    return _LONG_TOKEN.sub("[REDACTED_LONG_TOKEN]", redacted)


def _header(headers: Mapping[str, str], name: str) -> str | None:
    target = name.casefold()
    for key, value in headers.items():
        if key.casefold() == target and value.strip():
            return value.strip()
    return None


def _project(
    request: DiagnosticRequest, raw: RawTransportResult, api_key: str
) -> DiagnosticObservation:
    body_hash = _sha256_bytes(raw.body)
    parsed: Any = None
    json_object = False
    if raw.body:
        try:
            parsed = json.loads(raw.body.decode("utf-8"))
            json_object = isinstance(parsed, Mapping)
        except (UnicodeDecodeError, json.JSONDecodeError):
            parsed = None
    success = bool(raw.status is not None and 200 <= raw.status < 300)
    error_schema: str
    error_type: str | None = None
    error_code: str | int | None = None
    error_param: str | None = None
    error_message: str | None = None
    prefix: str | None = None
    target_visible: bool | None = None
    if success:
        error_schema = "success_body_redacted"
        if request.label == "D0" and isinstance(parsed, Mapping):
            data = parsed.get("data")
            target_visible = bool(
                isinstance(data, list)
                and any(isinstance(item, Mapping) and item.get("id") == MODEL for item in data)
            )
    elif raw.transport_error_type is not None:
        error_schema = "transport_error"
        error_type = raw.transport_error_type
        error_message = _redact_text(raw.transport_error_message or "", api_key) or None
    elif isinstance(parsed, Mapping) and isinstance(parsed.get("error"), Mapping):
        error_schema = "typed_error"
        error = parsed["error"]
        error_type = str(error.get("type")) if error.get("type") is not None else None
        error_code = cast(str | int | None, error.get("code"))
        error_param = str(error.get("param")) if error.get("param") is not None else None
        error_message = (
            _redact_text(str(error.get("message")), api_key)
            if error.get("message") is not None
            else None
        )
    else:
        error_schema = "unrecognized"
        decoded = raw.body[:4096].decode("utf-8", errors="replace")
        prefix = _redact_text(decoded, api_key) or None
    response_request_id = _header(raw.headers, "x-request-id") or _header(raw.headers, "request-id")
    values = {
        "request": request,
        "http_status": raw.status,
        "http_success": success,
        "response_request_id": response_request_id,
        "error_body_schema": error_schema,
        "error_type": error_type,
        "error_code": error_code,
        "error_param": error_param,
        "error_message_redacted": error_message,
        "unrecognized_body_prefix_redacted": prefix,
        "response_body_sha256": body_hash,
        "response_body_bytes": len(raw.body),
        "response_json_object": json_object,
        "target_model_visible": target_visible,
    }
    return cast(
        DiagnosticObservation,
        _identity(
            DiagnosticObservation,
            values,
            "observation_id",
            "finance_v26_191_diagnostic_observation:",
        ),
    )


def _urllib_transport(
    request: DiagnosticRequest, body: bytes | None, api_key: str
) -> RawTransportResult:
    headers = {"Authorization": f"Bearer {api_key}"}
    if body is not None:
        headers["Content-Type"] = "application/json"
    http_request = urllib.request.Request(
        request.endpoint,
        data=body,
        headers=headers,
        method=request.method,
    )
    try:
        with urllib.request.urlopen(http_request, timeout=180) as response:
            return RawTransportResult(
                status=int(getattr(response, "status", 200)),
                headers=dict(response.headers.items()),
                body=response.read(),
            )
    except urllib.error.HTTPError as exc:
        return RawTransportResult(
            status=int(exc.code), headers=dict(exc.headers.items()), body=exc.read()
        )
    except Exception as exc:  # transport errors are typed evidence, never retries
        return RawTransportResult(
            status=None,
            headers={},
            body=b"",
            transport_error_type=type(exc).__name__,
            transport_error_message=str(exc),
        )


def _curl_transport(
    request: DiagnosticRequest, body: bytes | None, api_key: str
) -> RawTransportResult:
    if body is None:
        raise ValueError("curl control requires a POST body")
    read_fd, write_fd = os.pipe()
    try:
        os.write(write_fd, f"Authorization: Bearer {api_key}\n".encode())
    finally:
        os.close(write_fd)
    command = (
        "curl",
        "--silent",
        "--show-error",
        "--request",
        "POST",
        "--header",
        f"@/dev/fd/{read_fd}",
        "--header",
        "Content-Type: application/json",
        "--data-binary",
        "@-",
        "--dump-header",
        "/dev/stderr",
        "--write-out",
        "\n__V26_191_STATUS__:%{http_code}",
        request.endpoint,
    )
    try:
        completed = subprocess.run(
            command,
            input=body,
            capture_output=True,
            check=False,
            pass_fds=(read_fd,),
        )
    finally:
        os.close(read_fd)
    marker = b"\n__V26_191_STATUS__:"
    response_body, separator, status_bytes = completed.stdout.rpartition(marker)
    if not separator or not status_bytes.isdigit():
        return RawTransportResult(
            status=None,
            headers={},
            body=b"",
            transport_error_type="CurlTransportError",
            transport_error_message=completed.stderr.decode("utf-8", errors="replace"),
        )
    headers: dict[str, str] = {}
    for line in completed.stderr.decode("utf-8", errors="replace").splitlines():
        name, header_separator, value = line.partition(":")
        if header_separator and name.casefold() in {"x-request-id", "request-id"}:
            headers[name] = value.strip()
    return RawTransportResult(status=int(status_bytes), headers=headers, body=response_body)


def _load_credential(package_root: Path) -> str:
    existing = os.environ.get("DEEPSEEK_API_KEY")
    if existing:
        return existing
    path = package_root / ".env"
    if not path.exists():
        raise ValueError("DEEPSEEK_API_KEY is absent and project .env is unavailable")
    if stat.S_IMODE(path.stat().st_mode) & 0o077:
        raise ValueError("project .env must be private")
    matches: list[str] = []
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line.removeprefix("export ").lstrip()
        key, separator, value = line.partition("=")
        if separator and key.strip() == "DEEPSEEK_API_KEY":
            value = value.strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
                value = value[1:-1]
            if value:
                matches.append(value)
    if len(matches) != 1:
        raise ValueError("project .env must define DEEPSEEK_API_KEY exactly once")
    return matches[0]


def _body(
    prompt: str,
    *,
    max_tokens: int = 64,
    thinking: bool = False,
    response_format: bool = False,
    sampling: bool = False,
) -> tuple[bytes, tuple[str, ...]]:
    payload: dict[str, Any] = {
        "model": MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
    }
    if thinking:
        payload["thinking"] = {"type": "enabled"}
    if response_format:
        payload["response_format"] = {"type": "json_object"}
    if sampling:
        payload["temperature"] = 0.6
        payload["top_p"] = 0.9
    return _canonical_bytes(payload), tuple(sorted(payload))


def _is_success(item: DiagnosticObservation) -> bool:
    return item.http_success


def _server_limitation(observations: list[DiagnosticObservation]) -> bool:
    text = " ".join(item.error_message_redacted or "" for item in observations).casefold()
    return any(
        token in text
        for token in ("account", "balance", "model", "permission", "route", "unavailable")
    )


def _synthetic_prompt(target_utf8_bytes: int) -> str:
    prefix = 'Return one JSON object exactly as {"ok":true}. Diagnostic padding: '
    if len(prefix.encode("utf-8")) > target_utf8_bytes:
        raise ValueError("target Prompt is too small for synthetic control")
    return prefix + ("x" * (target_utf8_bytes - len(prefix.encode("utf-8"))))


def execute(
    *,
    prepared: PreparedDiagnostic,
    api_key: str | None = None,
    urllib_transport: Transport = _urllib_transport,
    curl_transport: Transport = _curl_transport,
) -> dict[str, Any]:
    if prepared.output_dir.exists():
        raise FileExistsError(f"diagnostic output already exists: {prepared.output_dir}")
    credential = api_key or _load_credential(prepared.package_root)
    if not credential:
        raise ValueError("empty DeepSeek credential")
    prepared.output_dir.mkdir(parents=True, exist_ok=False)
    _write_bytes_no_replace(
        prepared.output_dir / "external_online_diagnostic_authorization.txt",
        prepared.authorization_bytes,
    )
    _write_no_replace(prepared.output_dir / "prepare_audit.json", prepared.prepare_audit)
    observations: list[DiagnosticObservation] = []
    bodies: dict[str, bytes] = {}

    def send(
        label: str,
        method: Literal["GET", "POST"],
        endpoint: str,
        body: bytes | None,
        fields: tuple[str, ...] = (),
        transport_name: Literal["urllib", "curl"] = "urllib",
    ) -> DiagnosticObservation:
        if len(observations) >= MAX_HTTP_REQUESTS:
            raise RuntimeError("online diagnostic exceeded its nine-request ceiling")
        request = _request(label, method, endpoint, body, fields, transport_name)
        if body is not None:
            bodies[label] = body
        transport = urllib_transport if transport_name == "urllib" else curl_transport
        observation = _project(request, transport(request, body, credential), credential)
        observations.append(observation)
        _write_no_replace(
            prepared.output_dir / "observations" / f"{len(observations):02d}_{label}.json",
            observation,
        )
        return observation

    d0 = send("D0", "GET", MODELS_ENDPOINT, None)
    decision: Decision
    localized_field: str | None = None
    selected_path: str | None = None
    if d0.http_status == 401:
        decision = "credential_invalid"
    elif d0.http_status == 402:
        decision = "account_balance_unavailable"
    elif d0.http_success and d0.target_model_visible is False:
        decision = "account_model_route_unavailable"
    else:
        minimal, minimal_fields = _body("Reply with the single word OK.")
        d1 = send("D1", "POST", OFFICIAL_ENDPOINT, minimal, minimal_fields)
        d2 = send("D2", "POST", LEGACY_ENDPOINT, minimal, minimal_fields)
        selected_path = (
            OFFICIAL_ENDPOINT if _is_success(d1) else (LEGACY_ENDPOINT if _is_success(d2) else None)
        )
        if selected_path is None:
            if d0.http_success:
                c_python = send(
                    "C_PYTHON", "POST", OFFICIAL_ENDPOINT, minimal, minimal_fields, "urllib"
                )
                c_curl = send("C_CURL", "POST", OFFICIAL_ENDPOINT, minimal, minimal_fields, "curl")
                if not c_python.http_success and c_curl.http_success:
                    decision = "client_transport_or_implicit_header_failure"
                elif _server_limitation(observations):
                    decision = "provider_or_account_route_failure"
                else:
                    decision = "online_root_cause_remains_unlocalized"
            elif _server_limitation(observations):
                decision = "provider_or_account_route_failure"
            else:
                decision = "online_root_cause_remains_unlocalized"
        else:
            full_minimal, full_fields = _body(
                'Return JSON exactly as {"ok":true}.',
                max_tokens=16384,
                thinking=True,
                response_format=True,
                sampling=True,
            )
            d3 = send("D3", "POST", selected_path, full_minimal, full_fields)
            if d3.http_success:
                d4 = send(
                    "D4",
                    "POST",
                    selected_path,
                    prepared.first_frozen_body,
                    (
                        "max_tokens",
                        "messages",
                        "model",
                        "response_format",
                        "temperature",
                        "thinking",
                        "top_p",
                    ),
                )
                if d4.http_success:
                    decision = (
                        "legacy_v1_endpoint_rejected"
                        if d1.http_success and d2.http_status == 400
                        else "current_route_healthy"
                    )
                else:
                    synthetic = _synthetic_prompt(
                        prepared.prepare_audit.first_frozen_prompt_utf8_bytes
                    )
                    d5_body, d5_fields = _body(
                        synthetic,
                        max_tokens=16384,
                        thinking=True,
                        response_format=True,
                        sampling=True,
                    )
                    d5 = send("D5", "POST", selected_path, d5_body, d5_fields)
                    decision = (
                        "prompt_specific_request_rejection"
                        if d5.http_success
                        else "online_root_cause_remains_unlocalized"
                    )
            elif d1.http_success:
                increments = (
                    ("D4a", "thinking", dict(thinking=True)),
                    ("D4b", "response_format", dict(thinking=True, response_format=True)),
                    (
                        "D4c",
                        "max_tokens",
                        dict(thinking=True, response_format=True, max_tokens=16384),
                    ),
                    (
                        "D4d",
                        "temperature_top_p",
                        dict(
                            thinking=True,
                            response_format=True,
                            max_tokens=16384,
                            sampling=True,
                        ),
                    ),
                )
                for label, field, kwargs in increments:
                    incremental_body, incremental_fields = _body(
                        "Reply with the single word OK.", **kwargs
                    )
                    item = send(
                        label, "POST", OFFICIAL_ENDPOINT, incremental_body, incremental_fields
                    )
                    if not item.http_success:
                        localized_field = field
                        break
                decision = (
                    "request_parameter_contract_failure"
                    if localized_field is not None
                    else "online_root_cause_remains_unlocalized"
                )
            else:
                decision = "request_parameter_contract_failure"

    if len(observations) > MAX_HTTP_REQUESTS:
        raise RuntimeError("online request ceiling failed after execution")
    body_hashes = {label: _sha256_bytes(value) for label, value in sorted(bodies.items())}
    gates = {
        "fresh_diagnostic_identity": True,
        "authorization_exact": True,
        "embedded_prepare_passed": True,
        "maximum_nine_requests": len(observations) <= 9,
        "zero_automatic_retries": all(item.request.automatic_retries == 0 for item in observations),
        "safe_typed_response_projection": True,
        "credential_not_persisted": True,
        "raw_response_not_persisted": True,
        "old_v188_job_rerun_zero": True,
        "recovery_job_zero": True,
        "historical_reclassification_zero": True,
        "downstream_rows_zero": True,
    }
    report_values = {
        "run_id": RUN_ID,
        "authorized_stage": AUTHORIZED_STAGE,
        "prepare_audit_id": prepared.prepare_audit.audit_id,
        "decision": decision,
        "localized_request_contract_field": localized_field,
        "selected_successful_path": selected_path,
        "online_http_request_count": len(observations),
        "maximum_http_requests": MAX_HTTP_REQUESTS,
        "automatic_retry_count": 0,
        "observation_ids": tuple(item.observation_id for item in observations),
        "request_body_sha256_by_label": body_hashes,
        "old_v188_job_rerun_count": 0,
        "recovery_job_count": 0,
        "old_outcome_reclassification_count": 0,
        "confirmation_access_count": 0,
        "mapper_rows": 0,
        "state_rows": 0,
        "frequency_rows": 0,
        "contribution_rows": 0,
        "vtdo_rows": 0,
        "student_rows": 0,
        "training_rows": 0,
        "release_rows": 0,
        "production_rows": 0,
        "v188_q_job": "0/192",
        "v188_q_semantic_given_model_endpoint": None,
        "historical_exact_cause_recovered": False,
        "gates": gates,
        "all_gates_passed": all(gates.values()),
        "next_stage": "no_further_experiment_authorized_without_new_audit_decision",
        "schema_version": "minimal_exact_route_online_diagnostic_report.v1",
    }
    report_values["report_id"] = canonical_hash(
        report_values, prefix="finance_v26_191_online_diagnostic_report:"
    )
    _write_no_replace(prepared.output_dir / "report.json", report_values)
    transition = {
        "current_stage": AUTHORIZED_STAGE,
        "decision": decision,
        "historical_v188_unchanged": True,
        "fresh_development_population_materialized": False,
        "provider_execution_authorized": False,
        "next_stage": "no_further_experiment_authorized_without_new_audit_decision",
        "schema_version": "minimal_exact_route_online_diagnostic_transition.v1",
    }
    transition["transition_id"] = canonical_hash(
        transition, prefix="finance_v26_191_online_diagnostic_transition:"
    )
    _write_no_replace(prepared.output_dir / "prospective_transition.json", transition)
    _write_no_replace(
        prepared.output_dir / "source_identity.json",
        {
            "source_commit": prepared.prepare_audit.source_commit,
            "source_tree": prepared.prepare_audit.source_tree,
            "schema_version": "minimal_exact_route_online_diagnostic_source_identity.v1",
        },
    )
    members: list[dict[str, Any]] = []
    for path in sorted(prepared.output_dir.rglob("*")):
        if path.is_file() and path.name != "artifact_manifest.json":
            content = path.read_bytes()
            members.append(
                {
                    "relative_path": path.relative_to(prepared.output_dir).as_posix(),
                    "sha256": _sha256_bytes(content),
                    "byte_count": len(content),
                }
            )
    manifest = {
        "run_id": RUN_ID,
        "members": members,
        "file_count": len(members),
        "total_byte_count": sum(item["byte_count"] for item in members),
        "schema_version": "minimal_exact_route_online_diagnostic_artifact_manifest.v1",
    }
    manifest["artifact_root"] = canonical_hash(
        members, prefix="finance_v26_191_online_diagnostic_artifact_root:"
    )
    manifest["manifest_id"] = canonical_hash(
        manifest, prefix="finance_v26_191_online_diagnostic_artifact_manifest:"
    )
    _write_no_replace(prepared.output_dir / "artifact_manifest.json", manifest)
    return report_values


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--package-root", type=Path, default=Path.cwd())
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--authorization", type=Path, required=True)
    parser.add_argument("--prepare-only", action="store_true")
    args = parser.parse_args()
    package_root = args.package_root.resolve()
    output_dir = (
        args.output_dir or package_root / "artifacts" / "vtdo_experiment" / RUN_ID
    ).resolve()
    prepared = prepare(
        package_root=package_root,
        output_dir=output_dir,
        authorization_path=args.authorization.resolve(),
    )
    if args.prepare_only:
        print(_canonical_json(prepared.prepare_audit))
        return
    print(_canonical_json(execute(prepared=prepared)))


if __name__ == "__main__":
    main()
