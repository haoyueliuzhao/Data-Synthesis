"""Fixed current Flash public-only callbacks, not a pilot or model discovery path."""

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

from ..finance_qa_vnext_model_execution.transport import HTTPSendError, HttpxSender
from ..finance_qa_vnext_task_build.archive import record, require, validate_record, write_json
from .budget import INPUT_ALLOWANCE, OUTPUT_ALLOWANCE

MODEL = "deepseek-flash"
ENDPOINT = "https://api.deepseek.com/chat/completions"
MAX_BODY_BYTES = 98_304
PUBLIC_RESPONSE_BYTES = 65_536


class FatalStudyError(RuntimeError):
    """A model/authentication/billing contract failure stops the fixed study."""


def policy():
    return record(
        "actual_period_live_transport",
        model=MODEL,
        accepted_response_models=[MODEL],
        endpoint=ENDPOINT,
        thinking={"type": "enabled"},
        reasoning_effort="high",
        temperature_top_p="omitted",
        max_tokens=OUTPUT_ALLOWANCE,
        maximum_responses=32,
        maximum_tools=32,
        old_scripted_tools_were_24=True,
        maximum_serialized_UTF8_body_bytes=MAX_BODY_BYTES,
        input_admission_allowance=INPUT_ALLOWANCE,
        input_overhead_allowance=1024,
        input_bound_is_exact_DeepSeek_token_count=False,
        input_rule="full serialized UTF8 body bytes plus fixed 1024 overhead; no truncation",
        response_bytes=2_097_152,
        public_content_bytes=PUBLIC_RESPONSE_BYTES,
        total_timeout_seconds=180,
        connect_timeout_seconds=30,
        automatic_retries=0,
        redirects=0,
        fallbacks=[],
        model_catalog_requests=0,
        public_response_only_material=True,
        private_reasoning_not_persisted=True,
        formal_gate_required_before_any_reservation=True,
    )


def render(messages):
    require(isinstance(messages, list) and bool(messages), "transport.complete_public_history")
    require(
        all(
            isinstance(x, dict)
            and set(x) == {"role", "content"}
            and x["role"] in {"system", "user", "assistant"}
            and isinstance(x["content"], str)
            for x in messages
        ),
        "transport.closed_text_message_contract",
    )
    body = {
        "model": MODEL,
        "thinking": {"type": "enabled"},
        "reasoning_effort": "high",
        "response_format": {"type": "json_object"},
        "max_tokens": OUTPUT_ALLOWANCE,
        "stream": False,
        "messages": messages,
    }
    raw = json.dumps(
        body, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode()
    require(
        len(raw) <= MAX_BODY_BYTES and len(raw) + 1024 <= INPUT_ALLOWANCE,
        "transport.full_history_exceeds_registered_input_bound",
    )
    return body, raw


class Provider:
    def __init__(self, ledger, session_id, output, credential, *, sender=None):
        self.ledger, self.session_id = ledger, session_id
        self.output, self.credential = Path(output), credential
        config = SimpleNamespace(
            endpoint=ENDPOINT,
            timeout_seconds=180,
            connect_timeout_seconds=30,
            maximum_http_response_bytes=2_097_152,
        )
        self.sender = sender or HttpxSender(config)
        self.live_http = sender is None

    def __call__(self, messages, context):
        with self.ledger.connection() as db:
            session = db.execute(
                "SELECT * FROM collection_sessions WHERE session_id=?", (self.session_id,)
            ).fetchone()
        require(
            session is not None and context.get("session_id") == self.session_id,
            "transport.registered_session_context",
        )
        require(
            context.get("identity", {}).get("task_id") == session["task_id"],
            "transport.public_task_and_registered_session_join",
        )
        body, raw = render(messages)
        lease = self.ledger.reserve_teacher(self.session_id)
        identifier = lease["request_id"]
        directory = self.output / identifier
        request = record(
            "Teacher_public_request",
            **lease,
            purpose="fixed_AB_Teacher_solution",
            policy_id=policy()["id"],
            endpoint=ENDPOINT,
            body=body,
            body_json=raw.decode(),
            body_sha256=hashlib.sha256(raw).hexdigest(),
            context=context,
            exact_public_body_saved=True,
            private_targets_supplied=False,
            live_http_sender=self.live_http,
        )
        write_json(directory / "request.json", request)
        self.ledger.mark_teacher_sent(identifier)
        usage, model, response = None, None, None
        settled = False
        try:
            response = self.sender.send(
                {
                    "endpoint": ENDPOINT,
                    "body_json": raw.decode(),
                    "body_sha256": request["body_sha256"],
                },
                api_key=self.credential,
            )
            require(response.complete and response.status_code == 200, "transport.complete_HTTP200")
            envelope = json.loads(response.body)
            usage, model = envelope.get("usage"), envelope.get("model")
            message = (envelope.get("choices") or [{}])[0].get("message") or {}
            content = message.get("content")
            public_content = (
                content.replace(self.credential, "[REDACTED_CREDENTIAL]")
                if isinstance(content, str)
                else content
            )
            observation = record(
                "Teacher_public_response",
                request_id=identifier,
                http_status=response.status_code,
                received_complete=True,
                received_body_sha256=hashlib.sha256(response.body).hexdigest(),
                response_model=model,
                usage=usage,
                public_content=public_content,
                public_content_sha256=(
                    hashlib.sha256(content.encode()).hexdigest()
                    if isinstance(content, str)
                    else None
                ),
                private_reasoning_present=bool(message.get("reasoning_content")),
                private_reasoning_text_saved=False,
                wire_envelope_not_reconstructible_from_public_projection=True,
                finish_reason=(envelope.get("choices") or [{}])[0].get("finish_reason"),
            )
            write_json(directory / "public_response.json", observation)
            valid_model = model == MODEL
            valid_content = (
                isinstance(public_content, str)
                and bool(public_content.strip())
                and len(public_content.encode()) <= PUBLIC_RESPONSE_BYTES
            )
            outcome = (
                "public_response_received"
                if valid_model and valid_content
                else "response_contract_failure"
            )
            known = self.ledger.settle_teacher(
                identifier, usage=usage, http_success=True, response_model=model, outcome=outcome
            )
            settled = True
            receipt = record(
                "Teacher_request_receipt",
                request_id=identifier,
                response_id=observation["id"],
                known_usage=known,
                outcome=outcome,
                purpose="fixed_AB_Teacher_solution",
                live_http_sender=self.live_http,
            )
            write_json(directory / "receipt.json", receipt)
            if not valid_model:
                raise FatalStudyError("transport.fixed_response_model_identity")
            require(valid_content, "transport.nonempty_bounded_public_content")
            if not known:
                raise FatalStudyError("transport.known_usage_within_reservation")
            return {
                "raw_response": public_content,
                "receipt": receipt,
                "authentic_model_origin": self.live_http,
                "evidence": {
                    "request_id": identifier,
                    "session_id": self.session_id,
                    "response_model": model,
                    "usage": usage,
                    "request_body_sha256": request["body_sha256"],
                    "public_content_sha256": observation["public_content_sha256"],
                    "receipt_id": receipt["id"],
                },
            }
        except Exception as error:
            if isinstance(error, FatalStudyError):
                self.ledger.halt(str(error))
            if not settled:
                self.ledger.settle_teacher(
                    identifier,
                    usage=usage,
                    http_success=bool(response and response.status_code == 200),
                    response_model=model,
                    outcome=type(error).__name__,
                )
            partial = (
                response
                if response
                else error.response
                if isinstance(error, HTTPSendError)
                else None
            )
            write_json(
                directory / "failure.json",
                record(
                    "Teacher_transport_failure",
                    request_id=identifier,
                    error_type=type(error).__name__,
                    reason=str(error).replace(self.credential, "[REDACTED]"),
                    http_status=partial.status_code if partial else None,
                    received_bytes=len(partial.body) if partial else 0,
                    received_body_sha256=hashlib.sha256(partial.body).hexdigest()
                    if partial
                    else None,
                    failed_session_not_retried=True,
                    unknown_charge_not_reclaimed=True,
                ),
            )
            if partial and partial.status_code in {401, 403}:
                self.ledger.halt("transport.authentication_or_access_denied")
                raise FatalStudyError("transport.authentication_or_access_denied") from error
            raise


def verify_receipts(session, ledger, output):
    """Reopen actual public bytes and same-session billing, not callback self-report.

    Instrumented code provenance and original request files are verified, not a
    cryptographic attestation of arbitrary replacement network implementations.
    """
    session_id = session.get("session_id") or session.get("collection_session_id")
    require(isinstance(session_id, str), "receipt.collection_session_identity")
    with ledger.connection() as db:
        registered = db.execute(
            "SELECT * FROM collection_sessions WHERE session_id=?", (session_id,)
        ).fetchone()
        rows = [
            dict(x)
            for x in db.execute(
                "SELECT * FROM teacher_reservations WHERE session_id=? ORDER BY attempt",
                (session_id,),
            )
        ]
    require(registered is not None, "receipt.registered_session")
    require(registered["task_id"] == session["identity"]["task_id"], "receipt.actual_task_join")
    turns = session["turns"]
    require(bool(turns) and len(turns) == len(rows), "receipt.complete_response_reservation_join")
    identifiers = []
    for turn, row in zip(turns, rows, strict=True):
        require(
            row["state"] == "settled"
            and row["http_success"] == 1
            and row["response_model"] == MODEL
            and row["outcome"] == "public_response_received",
            "receipt.authentic_successful_settled_return",
        )
        directory = Path(output) / row["request_id"]

        def read_record(name, kind, _directory=directory):
            value = json.loads((_directory / name).read_bytes())
            validate_record(value, kind)
            return value

        request = read_record("request.json", "Teacher_public_request")
        response = read_record("public_response.json", "Teacher_public_response")
        receipt = read_record("receipt.json", "Teacher_request_receipt")
        require(
            response["response_model"] == row["response_model"] == MODEL,
            "receipt.response_model_and_ledger_identity",
        )
        require(
            request["live_http_sender"] is True and receipt["live_http_sender"] is True,
            "receipt.mock_sender_cannot_create_training_material",
        )
        require(
            request["session_id"] == session_id
            and request["attempt"] == row["attempt"]
            and receipt["response_id"] == response["id"]
            and all(x["request_id"] == row["request_id"] for x in (request, response, receipt)),
            "receipt.exact_persisted_identity_join",
        )
        body, raw = render(turn["input_messages"])
        require(
            body == request["body"]
            and raw.decode() == request["body_json"]
            and hashlib.sha256(raw).hexdigest() == request["body_sha256"],
            "receipt.exact_full_public_request_bytes",
        )
        require(
            response["public_content"] == turn["raw_response"]
            and hashlib.sha256(turn["raw_response"].encode()).hexdigest()
            == response["public_content_sha256"],
            "receipt.exact_original_public_return",
        )
        usage = response["usage"]
        require(
            usage["prompt_tokens"] == row["prompt_tokens"]
            and usage["completion_tokens"] == row["completion_tokens"]
            and usage["total_tokens"] == row["charged_tokens"]
            and receipt["known_usage"],
            "receipt.actual_usage_and_ledger_join",
        )
        identifiers.append(row["request_id"])
    return {
        "status": "PASS_AUTHENTIC_PUBLIC_REQUEST_CHAIN",
        "session_id": session_id,
        "request_ids": identifiers,
        "provider_calls": len(identifiers),
        "mock_callback_origin_is_not_sufficient": True,
    }
