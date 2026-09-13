"""Fixed Flash HTTP transport with real receipts, no private CoT text storage."""

import json
from pathlib import Path
from types import SimpleNamespace

from ..finance_qa_vnext_model_execution.transport import HTTPSendError, HttpxSender
from . import protocol as p


class FatalProbeError(RuntimeError):
    global_fatal = True


def render(messages):
    p.require(isinstance(messages, list) and messages, "complete_public_history")
    p.require(
        all(
            isinstance(x, dict)
            and set(x) == {"role", "content"}
            and x["role"] in {"system", "user", "assistant"}
            and isinstance(x["content"], str)
            for x in messages
        ),
        "closed_text_message_contract",
    )
    body = {
        "model": p.MODEL,
        "thinking": {"type": "enabled"},
        "reasoning_effort": "high",
        "response_format": {"type": "json_object"},
        "max_tokens": p.OUTPUT_ALLOWANCE,
        "stream": False,
        "messages": messages,
    }
    raw = p.encode(body)
    p.require(
        len(raw) <= p.MAX_BODY_BYTES and len(raw) + 1024 <= p.INPUT_ALLOWANCE,
        "full_history_exceeds_registered_input_bound",
    )
    return body, raw


class Provider:
    def __init__(self, ledger, registered, output, credential, *, sender=None):
        self.ledger, self.registered = ledger, registered
        self.output, self.credential = Path(output), credential
        config = SimpleNamespace(
            endpoint=p.ENDPOINT,
            timeout_seconds=180,
            connect_timeout_seconds=30,
            maximum_http_response_bytes=2097152,
        )
        self.sender, self.live_http = sender or HttpxSender(config), sender is None

    def __call__(self, messages, context):
        registered = self.ledger.registered(self.registered["session_id"])
        p.require(
            registered == self.registered
            and context["session_id"] == registered["session_id"]
            and context["identity"] == registered["identity"]
            and context["requested_basis"] == registered["basis"]
            and context["protocol_profile"] == registered["profile"]
            and context["protocol"] == p.PROTOCOL
            and context["max_responses"] == p.MAX_RESPONSES
            and context["max_tools"] == p.MAX_TOOLS
            and messages[0]
            == {
                "role": "system",
                "content": p.system_prompt(registered["profile"], registered["basis"]),
            },
            "exact_public_registered_request_context",
        )
        body, raw = render(messages)
        lease = self.ledger.reserve(registered["session_id"])
        p.require(
            lease["attempt"] == context["response_index"] + 1, "one_request_per_runtime_attempt"
        )
        request_id = lease["request_id"]
        directory = self.output / request_id
        request = p.record(
            "probe_public_request",
            **lease,
            freeze_id=self.ledger.freeze_id,
            policy_id=p.policy()["id"],
            endpoint=p.ENDPOINT,
            body=body,
            body_json=raw.decode(),
            body_sha256=p.sha(raw),
            context=context,
            live_http_sender=self.live_http,
            private_targets_or_witnesses_supplied=False,
            exact_public_body_saved=True,
        )
        p.write_once(directory / "request.json", request)
        self.ledger.mark_sent(request_id)
        response, usage, model, observation, settled = None, None, None, None, False
        try:
            response = self.sender.send(
                {
                    "endpoint": p.ENDPOINT,
                    "body_json": raw.decode(),
                    "body_sha256": request["body_sha256"],
                },
                api_key=self.credential,
            )
            if response.status_code in {400, 401, 402, 403}:
                raise FatalProbeError(
                    "probe01_transport.fixed_request_or_auth_billing_HTTP_"
                    + str(response.status_code)
                )
            p.require(response.complete and response.status_code == 200, "complete_HTTP200")
            envelope = json.loads(response.body)
            usage, model = envelope.get("usage"), envelope.get("model")
            choice = (envelope.get("choices") or [{}])[0]
            message = choice.get("message") or {}
            content = message.get("content")
            is_string = isinstance(content, str)
            echoed = bool(is_string and self.credential in content)
            public = (
                content.replace(self.credential, "[REDACTED_CREDENTIAL]") if is_string else None
            )
            stripped = bool(is_string and content.strip())
            byte_count = len(content.encode()) if is_string else None
            valid_content = (
                is_string and stripped and byte_count <= p.PUBLIC_RESPONSE_BYTES and not echoed
            )
            observation = p.record(
                "probe_public_response",
                request_id=request_id,
                http_status=response.status_code,
                received_complete=True,
                received_body_sha256=p.sha(response.body),
                response_model=model,
                usage=usage,
                public_content=public,
                public_content_sha256=p.sha(content) if is_string else None,
                original_public_content_is_string=is_string,
                original_public_content_nonempty=stripped,
                original_public_content_bytes=byte_count,
                public_content_redacted=echoed,
                private_reasoning_present=bool(message.get("reasoning_content")),
                private_reasoning_text_saved=False,
                wire_envelope_not_reconstructible_from_projection=True,
                finish_reason=choice.get("finish_reason"),
            )
            p.write_once(directory / "public_response.json", observation)
            outcome = (
                "public_response_received"
                if model == p.MODEL and valid_content
                else "response_contract_failure"
            )
            known = self.ledger.settle(
                request_id, usage=usage, http_success=True, response_model=model, outcome=outcome
            )
            settled = True
            receipt = p.record(
                "probe_request_receipt",
                request_id=request_id,
                response_id=observation["id"],
                known_usage=known,
                outcome=outcome,
                live_http_sender=self.live_http,
                freeze_id=self.ledger.freeze_id,
                purpose="probe_behavior_coverage",
            )
            p.write_once(directory / "receipt.json", receipt)
            if echoed:
                raise FatalProbeError("probe01_transport.credential_echo_not_original_data")
            if model != p.MODEL:
                raise FatalProbeError("probe01_transport.fixed_model_identity")
            if not known:
                raise FatalProbeError("probe01_transport.known_usage_within_reservation")
            p.require(valid_content, "nonempty_bounded_public_content")
            return {
                "raw_response": public,
                "receipt": receipt,
                "authentic_model_origin": self.live_http,
                "evidence": {
                    "request_id": request_id,
                    "session_id": registered["session_id"],
                    "response_model": model,
                    "usage": usage,
                    "request_body_sha256": request["body_sha256"],
                    "public_content_sha256": observation["public_content_sha256"],
                    "receipt_id": receipt["id"],
                },
            }
        except Exception as error:
            if getattr(error, "global_fatal", False):
                self.ledger.halt(str(error))
            if not settled:
                self.ledger.settle(
                    request_id,
                    usage=usage,
                    http_success=bool(response and response.status_code == 200),
                    response_model=model,
                    outcome=type(error).__name__,
                )
            partial = response or (error.response if isinstance(error, HTTPSendError) else None)
            p.write_once(
                directory / "failure.json",
                p.record(
                    "probe_transport_failure",
                    request_id=request_id,
                    error_type=type(error).__name__,
                    reason=str(error).replace(self.credential, "[REDACTED]")[:2000],
                    http_status=partial.status_code if partial else None,
                    received_bytes=len(partial.body) if partial else 0,
                    received_body_sha256=p.sha(partial.body) if partial else None,
                    public_response_id=observation["id"] if observation else None,
                    private_reasoning_text_saved=False,
                ),
            )
            raise


def verify_origin(session, ledger, output):
    """Verify every public turn against the stored request and actual settlement."""
    p.checked(session, "probe_session")
    registered = ledger.registered(session["registered_session_id"])
    p.require(registered == session["registered_session"], "origin_registered_identity")
    requests, turns = ledger.requests(registered["session_id"]), session["turns"]
    p.require(len(requests) >= len(turns), "origin_all_received_turns_have_leases")
    verified = []
    for index, turn in enumerate(turns):
        row = requests[index]
        directory = Path(output) / row["request_id"]
        request = p.checked(
            json.loads((directory / "request.json").read_bytes()), "probe_public_request"
        )
        response = p.checked(
            json.loads((directory / "public_response.json").read_bytes()), "probe_public_response"
        )
        receipt = p.checked(
            json.loads((directory / "receipt.json").read_bytes()), "probe_request_receipt"
        )
        body, raw = render(turn["input_messages"])
        p.require(
            row["attempt"] == index + 1
            and row["state"] == "settled"
            and row["http_success"] == 1
            and row["response_model"] == p.MODEL
            and row["outcome"] == "public_response_received"
            and request["session_id"] == registered["session_id"]
            and request["request_id"] == row["request_id"]
            and request["policy_id"] == p.policy()["id"]
            and request["endpoint"] == p.ENDPOINT
            and request["reserved_tokens"] == row["reserved_tokens"] == p.REQUEST_RESERVATION
            and request["attempt"] == row["attempt"]
            and request["body"] == body
            and request["body_json"] == raw.decode()
            and request["body_sha256"] == p.sha(raw)
            and request["context"] == session["provider_attempts"][index]["context"]
            and request["live_http_sender"] is True
            and request["freeze_id"] == ledger.freeze_id
            and response["request_id"] == row["request_id"]
            and response["http_status"] == 200
            and response["response_model"] == p.MODEL
            and response["received_complete"] is True
            and not response["public_content_redacted"]
            and response["public_content"] == turn["raw_response"]
            and response["public_content_sha256"]
            == p.sha(turn["raw_response"])
            == turn["raw_response_sha256"]
            and receipt["request_id"] == row["request_id"]
            and receipt["response_id"] == response["id"]
            and receipt["known_usage"] is True
            and receipt["live_http_sender"] is True
            and receipt["outcome"] == "public_response_received"
            and receipt["freeze_id"] == ledger.freeze_id
            and receipt["purpose"] == "probe_behavior_coverage"
            and turn["transport_response_metadata"]["receipt"] == receipt,
            "authentic_exact_request_response_chain",
        )
        usage = response["usage"]
        p.require(
            all(
                type(usage.get(k)) is int
                for k in ("prompt_tokens", "completion_tokens", "total_tokens")
            )
            and usage["prompt_tokens"] == row["prompt_tokens"]
            and usage["completion_tokens"] == row["completion_tokens"]
            and usage["total_tokens"] == row["charged_tokens"] == row["reported_total_tokens"],
            "origin_actual_ledger_usage",
        )
        evidence = {
            "request_id": row["request_id"],
            "session_id": registered["session_id"],
            "response_model": p.MODEL,
            "usage": usage,
            "request_body_sha256": request["body_sha256"],
            "public_content_sha256": response["public_content_sha256"],
            "receipt_id": receipt["id"],
        }
        p.require(
            turn["transport_evidence"] == evidence
            and session["provider_attempts"][index]["evidence"] == evidence,
            "origin_evidence_projection",
        )
        verified.append(
            {
                "request_id": row["request_id"],
                "request_record_id": request["id"],
                "response_id": response["id"],
                "receipt_id": receipt["id"],
            }
        )
    complete = (
        session["first_final_index"] is not None and len(requests) == len(turns) and bool(turns)
    )
    return p.record(
        "probe_origin_verification",
        session_id=session["id"],
        registered_session_id=registered["session_id"],
        verified_turns=verified,
        verified_public_prefix=bool(turns),
        complete_first_Final_request_chain=complete,
        status="PASS_AUTHENTIC_PROBE_PUBLIC_CHAIN"
        if complete
        else "AUTHENTIC_PREFIX_NOT_COMPLETE_FINAL"
        if turns
        else "NO_AUTHENTIC_PUBLIC_TURNS",
        callback_self_attestation_accepted=False,
        wire_envelope_reconstruction_claimed=False,
    )
