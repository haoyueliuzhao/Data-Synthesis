"""Fixed DeepSeek text transport: one POST, no redirects/discovery/retries.

The caller must reserve each physical attempt before using this module.
Credentials are never logged. This transport cannot produce semantic approval.
"""

import json
import time
import urllib.error
import urllib.request
from pathlib import Path

import cross_market_source_review_20260926 as core

base = core.base
SCRIPT = "trusted_data_synthesis/scripts/cross_market_review_transport_20260927.py"
ENDPOINT = "https://api.deepseek.com/chat/completions"
MODELS = {"discovery": "deepseek-flash", "challenge": "deepseek-v4-pro"}
MAX_REQUEST_BYTES = 131072
MAX_RESPONSE_BYTES = 2097152
TIMEOUT_SECONDS = 120
CREDENTIAL = Path("/data1/zhuxinrui/projects/Data-Synthesis/trusted_data_synthesis/.env")


def credential(path=CREDENTIAL):
    values = [
        line.split("=", 1)[1].strip().strip("\"'")
        for line in path.read_text().splitlines()
        if line.strip().startswith("DEEPSEEK_API_KEY=")
    ]
    base.require(len(values) == 1 and bool(values[0]), "review_transport_credential_present")
    return values[0]


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError("review_transport_redirect_forbidden")


def request_bytes(request):
    base.require(
        set(request) == {"model", "messages", "max_tokens", "response_format", "thinking", "stream"}
        and request["model"] in MODELS.values()
        and request["max_tokens"] == core.MAX_OUTPUT_TOKENS
        and request["response_format"] == {"type": "json_object"}
        and request["thinking"] == {"type": "disabled"}
        and request["stream"] is False
        and len(request["messages"]) == 2
        and [m["role"] for m in request["messages"]] == ["system", "user"]
        and all(type(m["content"]) is str for m in request["messages"]),
        "review_transport_fixed_request_contract",
    )
    payload = base.encode(request)
    base.require(len(payload) <= MAX_REQUEST_BYTES, "review_transport_request_bytes")
    return payload


def one_post(payload, key):
    request = urllib.request.Request(
        ENDPOINT,
        data=payload,
        headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"},
        method="POST",
    )
    # Direct, fixed API destination; no local SEC proxy or egress selection.
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    with opener.open(request, timeout=TIMEOUT_SECONDS) as response:
        data = response.read(MAX_RESPONSE_BYTES + 1)
        base.require(
            response.status == 200 and len(data) <= MAX_RESPONSE_BYTES,
            "review_transport_response_bounds",
        )
        return data, response.headers.get("x-request-id")


class Provider:
    def __init__(self, output, key, sender=one_post):
        self.output, self.key, self.sender = Path(output), key, sender

    def __call__(self, request):
        payload = request_bytes(request)
        identifier = base.sha(payload)
        directory = self.output / "physical_requests" / identifier
        base.require(not (directory / "receipt.json").exists(), "review_transport_no_hidden_retry")
        base.write(
            directory / "request.json",
            dict(
                endpoint=ENDPOINT,
                body=request,
                raw_body_sha256=identifier,
                bytes=len(payload),
                automatic_model_discovery=False,
                fallback_models=[],
                hidden_retries=0,
                at=base.now(),
            ),
        )
        started = time.monotonic()
        try:
            raw, request_id = self.sender(payload, self.key)
            safe_raw = raw.decode("utf-8").replace(self.key, "[REDACTED_CREDENTIAL]")
            base.write(
                directory / "raw_response.json",
                dict(body_utf8=safe_raw, received_sha256=base.sha(raw), bytes=len(raw)),
            )
            envelope = json.loads(safe_raw)
            base.require(envelope["model"] == request["model"], "review_transport_response_model")
            usage = envelope["usage"]
            base.require(
                all(
                    type(usage[k]) is int and usage[k] >= 0
                    for k in ("prompt_tokens", "completion_tokens", "total_tokens")
                )
                and usage["completion_tokens"] <= core.MAX_OUTPUT_TOKENS
                and usage["total_tokens"] == usage["prompt_tokens"] + usage["completion_tokens"]
                and usage["total_tokens"] <= 1000000,
                "review_transport_usage_bounds",
            )
            choice = envelope["choices"][0]
            result = dict(
                finish_reason=choice["finish_reason"],
                content=choice["message"].get("content"),
                model=envelope["model"],
                usage=usage,
                request_id=request_id.replace(self.key, "[REDACTED_CREDENTIAL]")
                if request_id is not None
                else None,
                response_id=envelope["id"],
                transport_retries=0,
            )
            base.write(
                directory / "receipt.json",
                dict(
                    status="RESPONSE_SAVED_NOT_SEMANTICALLY_REVIEWED",
                    request_sha256=identifier,
                    latency_seconds=time.monotonic() - started,
                    response_model=envelope["model"],
                    usage=usage,
                    at=base.now(),
                    physical_requests=1,
                ),
            )
            return result
        except Exception as error:
            base.write(
                directory / "receipt.json",
                dict(
                    status="ATTEMPT_FAILED_NOT_REFUNDED",
                    request_sha256=identifier,
                    error_type=type(error).__name__,
                    http_status=error.code if isinstance(error, urllib.error.HTTPError) else None,
                    latency_seconds=time.monotonic() - started,
                    at=base.now(),
                    physical_requests=1,
                    error_detail="Transport/provider detail deliberately redacted",
                ),
            )
            raise RuntimeError("review_transport_failed_see_redacted_receipt") from None
