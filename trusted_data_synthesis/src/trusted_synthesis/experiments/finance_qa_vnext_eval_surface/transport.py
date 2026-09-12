"""One strict public-contract request; selection and any one repair belong upstream."""

import copy
import hashlib
import json
import re
import urllib.error
from pathlib import Path

from ..finance_qa_vnext_catalog_bridge.worker import strict_json
from ..finance_qa_vnext_surface_build.transport import ENDPOINT
from ..finance_qa_vnext_surface_build.transport import send as strict_send
from ..finance_qa_vnext_task_build.archive import record, validate_record, write_json
from .budget import INPUT_CAP, MODEL, OUTPUT_CAP, BudgetRejected, canonical_sha256, encode, require

VERSION = "evaluation_surface_rewrite.v1"
OVERHEAD = 1024
MODEL_CONTRACT_FIELDS = {
    "rewrite_version",
    "quantity_kind",
    "canonical_template",
    "required_placeholders",
    "language",
    "output_schema",
    "candidate_count",
    "immutable_slots",
    "semantic_constraints",
    "permitted_wording",
    "forbidden",
}
PROMPT = (
    "Rewrite the protected financial question template under the supplied contract. "
    "Return only its exact JSON output schema with one or two candidates in preference order. "
    "Each candidate has only rewrite_version and question_template. Preserve every required "
    "placeholder exactly once and put the output_instruction placeholder last. Preserve the "
    "specified operation: signed current-minus-previous difference, positive-previous-base "
    "percentage change, arithmetic mean over all three comparison periods, or primary maximum "
    "selection followed by secondary lookup in that same period. Use only the permitted wording. "
    "Do not invent literal numbers, companies, metric names, period labels, source values, "
    "answers, explanations, extra operations, or alternative source definitions."
)


class EvaluationTransportError(RuntimeError):
    def __init__(self, code, *, request_id, receipt, global_fatal):
        self.request_id, self.receipt, self.global_fatal = request_id, receipt, global_fatal
        super().__init__(code)


def policy():
    return record(
        "evaluation_rewrite_transport_policy",
        model=MODEL,
        endpoint=ENDPOINT,
        thinking={"type": "disabled"},
        max_tokens=OUTPUT_CAP,
        input_allowance=INPUT_CAP,
        input_bound="complete serialized UTF8 request body plus fixed overhead",
        overhead=OVERHEAD,
        exact_DeepSeek_tokenization_claimed=False,
        output_version=VERSION,
        response_bytes=250000,
        lower_level_HTTP_attempts=1,
        redirects=0,
        retries=0,
        model_discovery=False,
        fallback_models=[],
        model_inputs=(
            "fixed prompt and public protected model_contract only; no whole spec or identity"
        ),
        candidate_selection_performed_here=False,
        automatic_contract_repair=False,
    )


def _repair(reason):
    if reason is None:
        return None
    require(
        isinstance(reason, list)
        and 1 <= len(reason) <= 32
        and all(
            isinstance(code, str) and re.fullmatch(r"[A-Za-z][A-Za-z0-9_.:-]{0,127}", code)
            for code in reason
        ),
        "explicit_bounded_contract_error_codes",
    )
    return list(reason)


def render(model_contract, *, repair_reason=None):
    reason = _repair(repair_reason)
    require(
        isinstance(model_contract, dict)
        and set(model_contract) == MODEL_CONTRACT_FIELDS
        and model_contract["rewrite_version"] == VERSION,
        "closed_public_model_contract",
    )
    system = PROMPT
    if reason is not None:
        system += (
            "\nThe prior returned candidate violated these contract checks; correct them: "
            + encode(reason).decode()
        )
    body = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": encode(model_contract).decode()},
        ],
        "thinking": {"type": "disabled"},
        "response_format": {"type": "json_object"},
        "max_tokens": OUTPUT_CAP,
        "stream": False,
    }
    # The reused sender serializes using these exact json.dumps parameters.
    raw = json.dumps(body, ensure_ascii=False).encode()
    require(len(raw) + OVERHEAD <= INPUT_CAP, "full_request_exceeds_registered_input_bound")
    return body, raw


def parse_candidates(raw_content):
    errors = []
    try:
        require(
            isinstance(raw_content, str) and bool(raw_content.strip()), "nonempty_returned_rewrite"
        )
        value = strict_json(raw_content)
        require(isinstance(value, dict) and set(value) == {"rewrites"}, "closed_rewrite_response")
        candidates = value["rewrites"]
        require(isinstance(candidates, list) and 1 <= len(candidates) <= 2, "one_or_two_candidates")
        require(
            all(
                isinstance(row, dict)
                and set(row) == {"rewrite_version", "question_template"}
                and row["rewrite_version"] == VERSION
                and isinstance(row["question_template"], str)
                and bool(row["question_template"].strip())
                for row in candidates
            ),
            "closed_candidate_schema",
        )
        return candidates, errors
    except (ValueError, TypeError, RuntimeError) as error:
        return [], [str(error)]


class EvaluationProvider:
    def __init__(self, task_identity, spec, ledger, output, key, *, sender=strict_send):
        validate_record(spec, "evaluation_rewrite_spec")
        self.identity, self.spec = copy.deepcopy(task_identity), copy.deepcopy(spec)
        self.ledger, self.output, self.key, self.sender = (
            ledger,
            Path(output).absolute(),
            key,
            sender,
        )
        require(isinstance(key, str) and bool(key), "credential_present")
        require(
            not any(path.is_symlink() for path in (self.output, *self.output.parents)),
            "output_must_not_follow_symlinks",
        )
        registered = ledger.evaluation_registration(self.identity["task_id"])
        require(
            registered["identity"] == self.identity
            and registered["spec_sha256"] == canonical_sha256(self.spec),
            "frozen_identity_and_complete_public_spec",
        )
        self.spec_sha256 = registered["spec_sha256"]
        render(self.spec["model_contract"])

    def request(self, repair_reason=None):
        reason = _repair(repair_reason)
        body, raw = render(self.spec["model_contract"], repair_reason=reason)
        parent = self.output / "evaluation_requests"
        require(
            not any(path.is_symlink() for path in (parent, *parent.parents)),
            "output_must_not_follow_symlinks",
        )
        lease = self.ledger.reserve_evaluation(self.identity["task_id"], repair=reason is not None)
        identifier = lease["request_id"]
        directory = self.output / "evaluation_requests" / identifier
        request = record(
            "evaluation_question_rewrite_request",
            **lease,
            task_identity=self.identity,
            spec_sha256=self.spec_sha256,
            policy_id=policy()["id"],
            endpoint=ENDPOINT,
            body=body,
            body_json=raw.decode(),
            body_sha256=hashlib.sha256(raw).hexdigest(),
            serialized_body_bytes=len(raw),
            admitted_input_bound=len(raw) + OVERHEAD,
            repair_reason=reason,
            lower_level_attempts=1,
            live_HTTP_sender=self.sender is strict_send,
            only_public_model_contract_sent=True,
            whole_spec_or_private_target_sent=False,
        )
        try:
            write_json(directory / "request.json", request)
            self.ledger.mark_evaluation_sent(identifier)
        except Exception as error:
            code = (
                "NOT_SENT_AFTER_STUDY_STOP"
                if isinstance(error, BudgetRejected)
                else "NOT_SENT_EVIDENCE_WRITE_FAILED"
            )
            self.ledger.halt(code)
            receipt = record(
                "evaluation_question_rewrite_failure",
                request_id=identifier,
                request_record_id=request["id"],
                purpose="evaluation_question_rewrite",
                error_type=type(error).__name__,
                error=str(error).replace(self.key, "[REDACTED_CREDENTIAL]"),
                failure_code=code,
                sent=False,
                lower_level_attempts=0,
                reservation=lease,
                settlement=None,
                retained_reservation_state="reserved",
                retained_charge=lease["reserved_tokens"],
                allowance_released=False,
                global_fatal=True,
                automatic_retry=False,
            )
            try:
                write_json(directory / "failure.json", receipt)
            except OSError:
                # The typed error still gives the caller the original lease and receipt.
                # The durable bank STOP and reserved charge do not depend on output storage.
                pass
            raise EvaluationTransportError(
                code, request_id=identifier, receipt=receipt, global_fatal=True
            ) from error
        usage, observed_model, raw_content, settlement = None, None, None, None
        complete_HTTP200 = False
        response, wire = None, None
        try:
            wire = self.sender(body, self.key)
            complete_HTTP200 = True
            require(
                isinstance(wire, bytes) and len(wire) <= 250000, "bounded_complete_HTTP_response"
            )
            envelope = strict_json(wire.decode("utf-8"))
            require(isinstance(envelope, dict), "model_response_envelope")
            usage, observed_model = envelope.get("usage"), envelope.get("model")
            if not isinstance(observed_model, str):
                observed_model = None
            choices = envelope.get("choices")
            message = (
                choices[0].get("message", {})
                if isinstance(choices, list) and choices and isinstance(choices[0], dict)
                else {}
            )
            raw_content = message.get("content") if isinstance(message, dict) else None
            echoed = isinstance(raw_content, str) and self.key in raw_content
            retained = (
                raw_content.replace(self.key, "[REDACTED_CREDENTIAL]") if echoed else raw_content
            )
            response = record(
                "evaluation_question_rewrite_response",
                request_id=identifier,
                http_status=200,
                received_body_sha256=hashlib.sha256(wire).hexdigest(),
                response_model=observed_model,
                usage=usage,
                raw_public_content=retained,
                original_public_content_sha256=hashlib.sha256(raw_content.encode()).hexdigest()
                if isinstance(raw_content, str)
                else None,
                private_reasoning_present=bool(message.get("reasoning_content"))
                if isinstance(message, dict)
                else False,
                private_reasoning_text_saved=False,
                credential_echo_redacted=echoed,
            )
            write_json(directory / "public_response.json", response)
            candidates, errors = parse_candidates(raw_content)
            outcome = "rewrite_structure_failure" if errors else "response_received"
            fatal = "evaluation_credential_echo_in_public_response" if echoed else None
            settlement = self.ledger.settle_evaluation(
                identifier,
                usage=usage,
                http_success=True,
                response_model=observed_model,
                outcome=outcome,
                fatal_reason=fatal,
            )
            receipt = record(
                "evaluation_question_rewrite_receipt",
                request_id=identifier,
                request_record_id=request["id"],
                response_record_id=response["id"],
                purpose="evaluation_question_rewrite",
                settlement=settlement,
                outcome=outcome,
                structure_errors=errors,
                candidate_count=len(candidates),
                automatic_retry=False,
                original_candidate_preference_order_preserved=True,
            )
            write_json(directory / "receipt.json", receipt)
            if settlement["study_fatal"]:
                raise EvaluationTransportError(
                    "evaluation_global_model_or_billing_stop",
                    request_id=identifier,
                    receipt=receipt,
                    global_fatal=True,
                )
            return {
                "candidates": candidates,
                "receipt": receipt,
                "request_id": identifier,
                "raw_content": raw_content,
                "structure_errors": errors,
            }
        except EvaluationTransportError:
            raise
        except Exception as error:
            error_body = None
            if isinstance(error, urllib.error.HTTPError):
                try:
                    error_body = (
                        error.read(250000)
                        .decode("utf-8", errors="replace")
                        .replace(self.key, "[REDACTED_CREDENTIAL]")
                    )
                except (OSError, ValueError):
                    error_body = "unreadable_HTTP_error_body"
            status = getattr(error, "code", None)
            fatal = "evaluation_authentication_or_access_denied" if status in {401, 403} else None
            if complete_HTTP200:
                fatal = fatal or "evaluation_complete_HTTP_model_or_billing_contract_failure"
            if settlement is None:
                settlement = self.ledger.settle_evaluation(
                    identifier,
                    usage=usage,
                    http_success=complete_HTTP200,
                    response_model=observed_model,
                    outcome=type(error).__name__,
                    fatal_reason=fatal,
                )
            elif fatal:
                self.ledger.halt(fatal)
            receipt = record(
                "evaluation_question_rewrite_failure",
                request_id=identifier,
                request_record_id=request["id"],
                purpose="evaluation_question_rewrite",
                error_type=type(error).__name__,
                error=str(error).replace(self.key, "[REDACTED_CREDENTIAL]"),
                http_status=status,
                bounded_error_body=error_body,
                received_body_sha256=hashlib.sha256(wire).hexdigest()
                if isinstance(wire, bytes)
                else None,
                settlement=settlement,
                persisted_fatal_reason=fatal,
                automatic_retry=False,
                canonical_fallback_decided_upstream=True,
            )
            write_json(directory / "failure.json", receipt)
            raise EvaluationTransportError(
                "evaluation_single_attempt_failed",
                request_id=identifier,
                receipt=receipt,
                global_fatal=bool(fatal or settlement["study_fatal"]),
            ) from error
