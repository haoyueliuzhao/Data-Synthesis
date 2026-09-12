"""One fixed-model, one-HTTP-attempt sender used only for question realization."""

import hashlib
import json
import time
import urllib.error
import urllib.request
from pathlib import Path

from finraw.llm_client import LLMClientError

from ..finance_qa_vnext_task_build.archive import record, require, write_json
from .budget import OUTPUT_CAP
from .guards import REWRITE_NETWORK

MODEL = "deepseek-flash"
ENDPOINT = "https://api.deepseek.com/chat/completions"
MAX_PROMPT_BYTES = 6144
PROMPT = (
    "You rewrite a financial question without changing its requested quantity. "
    'Return JSON only: {"rewrites":[{"rewrite_version":"question_rewrite.v3.3",'
    '"question_template":"..."}]}. Return one or two candidates in preference order. '
    "Write the actual question template, not sentence-plan IDs. Preserve every supplied "
    "placeholder exactly once, and put the output-instruction placeholder last. Do not "
    "introduce literal numbers, company names, metric aliases, explanations, answers or "
    "extra operations. Use a natural direct question or concise request about the signed "
    "change from earlier to later, or the year-over-year percentage change with the earlier "
    "value as base. Keep the wording concise. Avoid vague magnitude, absolute growth or "
    "a simple later/earlier ratio. Do not return commentary outside the JSON object."
)


def credential(root):
    # Load only the explicitly authorized project key; never serialize it.
    for line in (Path(root) / "trusted_data_synthesis/.env").read_text().splitlines():
        if line.strip().startswith("DEEPSEEK_API_KEY="):
            value = line.split("=", 1)[1].strip().strip("\"'")
            require(bool(value), "surface.rewrite_credential_present")
            return value
    raise RuntimeError("surface.rewrite_credential_missing")


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise RuntimeError("surface.redirect_forbidden")


def send(body, key):
    require(body["model"] == MODEL, "surface.fixed_model")
    require(
        set(body) == {"model", "messages", "thinking", "response_format", "max_tokens", "stream"},
        "surface.closed_request_fields",
    )
    request = urllib.request.Request(
        ENDPOINT,
        data=json.dumps(body, ensure_ascii=False).encode(),
        headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"},
        method="POST",
    )
    token = REWRITE_NETWORK.set(True)
    try:
        opener = urllib.request.build_opener(NoRedirect())
        with opener.open(request, timeout=45) as response:
            raw = response.read(250_001)
            require(response.status == 200 and len(raw) <= 250_000, "surface.bounded_HTTP_response")
            return raw
    finally:
        REWRITE_NETWORK.reset(token)


class Provider:
    def __init__(self, task_id, ledger, output, key, *, sender=send):
        self.task_id, self.ledger, self.output = task_id, ledger, Path(output)
        self.key, self.sender = key, sender
        self.last_telemetry = {"request_count": 0}

    def generate(self, request):
        self.last_telemetry = {"request_count": 0, "request_ids": []}
        require(request.get("generation_strategy") == "protected_rewrite", "surface.rewrite_only")
        require(request.get("variant_count") == 2, "surface.two_variants_max")
        require("surface_variant_schema" not in request, "surface.no_alias_expansion")
        if request.get("repair_contract"):
            require(
                bool(request["repair_contract"].get("previous_error_codes")),
                "surface.repair_requires_explicit_contract_errors",
            )
        content = json.dumps(request, ensure_ascii=False, sort_keys=True)
        require(len((PROMPT + content).encode()) <= MAX_PROMPT_BYTES, "surface.bounded_prompt")
        body = {
            "model": MODEL,
            "messages": [
                {"role": "system", "content": PROMPT},
                {"role": "user", "content": content},
            ],
            "thinking": {"type": "disabled"},
            "response_format": {"type": "json_object"},
            "max_tokens": OUTPUT_CAP,
            "stream": False,
        }
        lease = self.ledger.reserve(self.task_id, repair=bool(request.get("repair_contract")))
        identifier = lease["request_id"]
        directory = self.output / "rewrite_requests" / identifier
        write_json(
            directory / "request.json",
            record(
                "question_rewrite_request",
                **lease,
                purpose="question_rewrite",
                endpoint=ENDPOINT,
                body=body,
                raw_body_sha256=hashlib.sha256(
                    json.dumps(body, ensure_ascii=False).encode()
                ).hexdigest(),
                private_answers_or_basis_roles_supplied=False,
                automatic_model_discovery=False,
                fallback_models=[],
                lower_level_attempts=1,
                temperature_top_p="omitted",
            ),
        )
        self.ledger.mark_sent(identifier)
        started = time.monotonic()
        self.last_telemetry = {
            "request_count": 1,
            "request_ids": [identifier],
            "http_success_count": 0,
            "structured_response_count": 0,
            "requested_model": MODEL,
        }
        envelope, usage, observed_model = None, None, None
        try:
            raw = self.sender(body, self.key)
            self.last_telemetry.update(http_success=True, http_success_count=1)
            # Response logs cannot accidentally echo the credential in an error.
            safe_raw = raw.decode("utf-8").replace(self.key, "[REDACTED_CREDENTIAL]")
            write_json(
                directory / "raw_response.json",
                {
                    "request_id": identifier,
                    "body_utf8": safe_raw,
                    "received_body_sha256": hashlib.sha256(raw).hexdigest(),
                    "http_status": 200,
                },
            )
            envelope = json.loads(safe_raw)
            usage, observed_model = envelope.get("usage"), envelope.get("model")
            require(observed_model == MODEL, "surface.exact_response_model_identity")
            message = (envelope.get("choices") or [{}])[0].get("message") or {}
            text = message.get("content")
            outcome = "response_received"
            if text is None or not str(text).strip():
                variants = []
                outcome = "no_returned_text"
            else:
                try:
                    payload = json.loads(text)
                    variants = payload.get("rewrites")
                    require(
                        isinstance(variants, list)
                        and 1 <= len(variants) <= 2
                        and all(isinstance(value, dict) for value in variants),
                        "surface.response_schema",
                    )
                    self.last_telemetry.update(json_valid=True, structured_response_count=1)
                except (ValueError, TypeError, AttributeError):
                    variants = [{"invalid_response_schema": True}]
                    outcome = "rewrite_structure_failure"
            known = self.ledger.settle(
                identifier,
                usage=usage,
                http_success=True,
                response_model=observed_model,
                outcome=outcome,
            )
            require(known, "surface.valid_token_usage_within_reservation")
            self.last_telemetry.update(
                prompt_tokens=usage["prompt_tokens"],
                completion_tokens=usage["completion_tokens"],
                total_tokens=usage["prompt_tokens"] + usage["completion_tokens"],
                response_model=observed_model,
                latency_ms=1000 * (time.monotonic() - started),
            )
            write_json(
                directory / "receipt.json",
                record(
                    "question_rewrite_receipt",
                    request_id=identifier,
                    purpose="question_rewrite",
                    status=outcome,
                    telemetry=self.last_telemetry,
                ),
            )
            return variants
        except Exception as exc:
            error_body = None
            if isinstance(exc, urllib.error.HTTPError):
                error_body = (
                    exc.read(250_000)
                    .decode("utf-8", errors="replace")
                    .replace(self.key, "[REDACTED_CREDENTIAL]")
                )
            rows = self.ledger.snapshot()["reservations"]
            row = next(value for value in rows if value["request_id"] == identifier)
            if row["state"] == "sent":
                self.ledger.settle(
                    identifier,
                    usage=usage,
                    http_success=bool(self.last_telemetry.get("http_success")),
                    response_model=observed_model,
                    outcome=type(exc).__name__,
                )
            self.last_telemetry["latency_ms"] = 1000 * (time.monotonic() - started)
            self.last_telemetry["error_type"] = type(exc).__name__
            if isinstance(usage, dict):
                self.last_telemetry["reported_usage"] = usage
            write_json(
                directory / "failure.json",
                record(
                    "question_rewrite_failure",
                    request_id=identifier,
                    error_type=type(exc).__name__,
                    status_code=getattr(exc, "code", None),
                    contract_error=str(exc).replace(self.key, "[REDACTED_CREDENTIAL]")
                    if isinstance(exc, ValueError)
                    else None,
                    bounded_error_body=error_body,
                    telemetry=self.last_telemetry,
                    retry_permitted=False,
                ),
            )
            raise LLMClientError(
                "registered_question_rewrite_failed", telemetry=self.last_telemetry
            ) from exc
