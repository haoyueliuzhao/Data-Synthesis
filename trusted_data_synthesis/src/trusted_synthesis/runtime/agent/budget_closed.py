from __future__ import annotations

import hashlib
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.hashing import canonical_hash
from trusted_synthesis.runtime.agent.client import JsonCompletionClient, LLMClientError
from trusted_synthesis.runtime.agent.schema import AgentModelConfig, ModelCallTelemetry

BUDGET_CLOSED_PROVIDER_CONTRACT_VERSION = "provider_token_budget_contract.v1"
BUDGET_CLOSED_PROVIDER_CERTIFICATE_VERSION = "provider_token_budget_certificate.v1"
BUDGET_CLOSED_PROVIDER_USAGE_VERSION = "provider_token_usage_record.v1"
BUDGET_CLOSED_NO_CALL_TERMINAL_VERSION = "provider_budget_no_call_terminal.v1"
BUDGET_CLOSED_PROVIDER_AUDIT_VERSION = "provider_token_budget_audit.v1"

ProviderRequestKind = Literal[
    "plan",
    "decision",
    "scripted_tool",
    "final_answer",
    "contract_repair",
    "unknown",
]
CertificateDecision = Literal["allowed", "denied_no_call"]
NoCallReason = Literal[
    "oversized_prompt",
    "request_bound_exceeds_remaining_budget",
    "required_reserve_not_available",
]

_PLAN_HEADER = "Return only one compact JSON object with exactly these keys: plan_summary"
_SCRIPTED_HEADER = "The Host has frozen the next tool."
_FINAL_HEADER = "Return only one JSON object with exactly rationale_summary, answer"
_DECISION_HEADER = "Return only one compact JSON object. Choose one next public action."
_REPAIR_MARKER = "\nCONTRACT_REPAIR_JSON:\n"


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class ProviderTokenBudgetContract(FrozenModel):
    """Provider-bound upper bounds used before any token-bearing request."""

    contract_id: str = Field(min_length=1)
    provider: str = Field(min_length=1)
    model_id: str = Field(min_length=1)
    maximum_total_tokens: int = Field(ge=1)
    maximum_prompt_utf8_bytes: int = Field(ge=1)
    maximum_output_tokens: int = Field(ge=1)
    provider_chat_envelope_token_upper_bound: int = Field(ge=0)
    contract_repair_reserve_tokens: int = Field(ge=0)
    final_answer_reserve_tokens: int = Field(ge=0)
    prompt_token_upper_bound_method: Literal["utf8_bytes_plus_provider_chat_envelope"] = (
        "utf8_bytes_plus_provider_chat_envelope"
    )
    http_failure_usage_policy: Literal["exclude_http_unsuccessful_attempts"] = (
        "exclude_http_unsuccessful_attempts"
    )
    successful_http_usage_required: Literal[True] = True
    prompt_completion_sum_required: Literal[True] = True
    cache_partition_sum_required_when_present: Literal[True] = True
    maximum_model_attempts: Literal[1] = 1
    fallback_forbidden: Literal[True] = True
    schema_version: str = BUDGET_CLOSED_PROVIDER_CONTRACT_VERSION

    @model_validator(mode="after")
    def validate_contract(self) -> ProviderTokenBudgetContract:
        if self.maximum_output_tokens >= self.maximum_total_tokens:
            raise ValueError("Provider output bound exhausts the rollout budget")
        if (
            self.contract_repair_reserve_tokens + self.final_answer_reserve_tokens
            >= self.maximum_total_tokens
        ):
            raise ValueError("Provider reserves exhaust the rollout budget")
        if self.contract_id != provider_token_budget_contract_id(self):
            raise ValueError("Provider token budget Contract identity is invalid")
        return self


class ProviderTokenBudgetCertificate(FrozenModel):
    certificate_id: str = Field(min_length=1)
    contract_id: str = Field(min_length=1)
    request_index: int = Field(ge=0)
    request_kind: ProviderRequestKind
    repaired_request_kind: ProviderRequestKind | None = None
    request_hash: str = Field(min_length=64, max_length=64)
    prompt_utf8_bytes: int = Field(ge=0)
    prompt_token_upper_bound: int = Field(ge=0)
    completion_token_upper_bound: int = Field(ge=1)
    request_token_upper_bound: int = Field(ge=1)
    cumulative_provider_tokens_before: int = Field(ge=0)
    contract_repair_reserve_tokens: int = Field(ge=0)
    final_answer_reserve_tokens: int = Field(ge=0)
    required_reserve_tokens: int = Field(ge=0)
    projected_upper_total: int = Field(ge=1)
    maximum_total_tokens: int = Field(ge=1)
    decision: CertificateDecision
    denial_reason: NoCallReason | None = None
    provider_call_permitted: bool
    schema_version: str = BUDGET_CLOSED_PROVIDER_CERTIFICATE_VERSION

    @model_validator(mode="after")
    def validate_certificate(self) -> ProviderTokenBudgetCertificate:
        if self.prompt_token_upper_bound < self.prompt_utf8_bytes:
            raise ValueError("Provider prompt upper bound is below its UTF-8 byte count")
        if self.request_token_upper_bound != (
            self.prompt_token_upper_bound + self.completion_token_upper_bound
        ):
            raise ValueError("Provider request upper-bound arithmetic is invalid")
        if self.required_reserve_tokens != (
            self.contract_repair_reserve_tokens + self.final_answer_reserve_tokens
        ):
            raise ValueError("Provider request reserve arithmetic is invalid")
        if self.projected_upper_total != (
            self.cumulative_provider_tokens_before
            + self.request_token_upper_bound
            + self.required_reserve_tokens
        ):
            raise ValueError("Provider projected budget arithmetic is invalid")
        allowed = self.decision == "allowed"
        if allowed != self.provider_call_permitted:
            raise ValueError("Provider certificate decision and call permission disagree")
        if allowed and (
            self.denial_reason is not None or self.projected_upper_total > self.maximum_total_tokens
        ):
            raise ValueError("Provider certificate allowed an unclosed request")
        if not allowed and self.denial_reason is None:
            raise ValueError("Provider no-call certificate lacks a typed reason")
        if self.request_kind == "contract_repair" and self.repaired_request_kind is None:
            raise ValueError("Contract-repair certificate lost its original request kind")
        if self.request_kind != "contract_repair" and self.repaired_request_kind is not None:
            raise ValueError("Non-repair certificate carries a repaired request kind")
        if self.certificate_id != provider_token_budget_certificate_id(self):
            raise ValueError("Provider token budget Certificate identity is invalid")
        return self


class ProviderTokenUsageRecord(FrozenModel):
    record_id: str = Field(min_length=1)
    contract_id: str = Field(min_length=1)
    certificate_id: str = Field(min_length=1)
    request_index: int = Field(ge=0)
    request_hash: str = Field(min_length=64, max_length=64)
    http_success: bool
    provider_call_observed: Literal[True] = True
    prompt_tokens: int | None = Field(default=None, ge=0)
    completion_tokens: int | None = Field(default=None, ge=0)
    total_tokens: int | None = Field(default=None, ge=0)
    counted_tokens: int = Field(ge=0)
    cumulative_provider_tokens_after: int = Field(ge=0)
    validation_checks: dict[str, bool]
    failure_ids: tuple[str, ...] = ()
    passed: bool
    schema_version: str = BUDGET_CLOSED_PROVIDER_USAGE_VERSION

    @model_validator(mode="after")
    def validate_record(self) -> ProviderTokenUsageRecord:
        if tuple(self.validation_checks) != tuple(sorted(self.validation_checks)):
            raise ValueError("Provider Usage checks are not canonical")
        expected_failures = tuple(
            f"resource_budget:{key}" for key, passed in self.validation_checks.items() if not passed
        )
        if self.failure_ids != expected_failures:
            raise ValueError("Provider Usage failures do not match its checks")
        if self.passed != (not self.failure_ids):
            raise ValueError("Provider Usage status does not match its failures")
        if not self.http_success and self.counted_tokens:
            raise ValueError("HTTP-unsuccessful Provider attempts entered token usage")
        if self.http_success and self.total_tokens is not None:
            if self.counted_tokens != self.total_tokens:
                raise ValueError("HTTP-successful Provider usage was not counted exactly")
        if self.record_id != provider_token_usage_record_id(self):
            raise ValueError("Provider token Usage identity is invalid")
        return self


class ProviderBudgetNoCallTerminal(FrozenModel):
    terminal_id: str = Field(min_length=1)
    contract_id: str = Field(min_length=1)
    denied_certificate_id: str = Field(min_length=1)
    request_index: int = Field(ge=0)
    request_kind: ProviderRequestKind
    request_hash: str = Field(min_length=64, max_length=64)
    reason_code: NoCallReason
    terminal_category: Literal["budget_exhausted_no_call"] = "budget_exhausted_no_call"
    denominator_classification: Literal["model_invalid_resource_terminal"] = (
        "model_invalid_resource_terminal"
    )
    provider_call_made: Literal[False] = False
    denominator_retained: Literal[True] = True
    instrument_failure: Literal[False] = False
    schema_version: str = BUDGET_CLOSED_NO_CALL_TERMINAL_VERSION

    @model_validator(mode="after")
    def validate_terminal(self) -> ProviderBudgetNoCallTerminal:
        if self.terminal_id != provider_budget_no_call_terminal_id(self):
            raise ValueError("Provider no-call terminal identity is invalid")
        return self


class ProviderTokenBudgetAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    contract_id: str = Field(min_length=1)
    certificates: tuple[ProviderTokenBudgetCertificate, ...] = ()
    usage_records: tuple[ProviderTokenUsageRecord, ...] = ()
    no_call_terminal: ProviderBudgetNoCallTerminal | None = None
    actual_request_prompt_hashes: tuple[str, ...] = ()
    provider_call_count: int = Field(ge=0)
    permitted_request_count: int = Field(ge=0)
    denied_no_call_count: int = Field(ge=0, le=1)
    cumulative_provider_tokens: int = Field(ge=0)
    maximum_total_tokens: int = Field(ge=1)
    contract_failure_ids: tuple[str, ...] = ()
    all_provider_calls_precertified: bool
    strict_budget_closed: bool
    status: Literal["passed", "failed"]
    schema_version: str = BUDGET_CLOSED_PROVIDER_AUDIT_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> ProviderTokenBudgetAudit:
        if tuple(item.request_index for item in self.certificates) != tuple(
            range(len(self.certificates))
        ):
            raise ValueError("Provider certificates are not contiguous")
        if self.permitted_request_count != sum(
            item.provider_call_permitted for item in self.certificates
        ):
            raise ValueError("Provider permitted-request denominator changed")
        if self.denied_no_call_count != sum(
            not item.provider_call_permitted for item in self.certificates
        ):
            raise ValueError("Provider no-call denominator changed")
        if self.provider_call_count != len(self.usage_records):
            raise ValueError("Provider Usage denominator changed")
        if len(self.actual_request_prompt_hashes) != self.provider_call_count:
            raise ValueError("Provider actual Prompt accounting is incomplete")
        if self.cumulative_provider_tokens != sum(
            item.counted_tokens for item in self.usage_records
        ):
            raise ValueError("Provider cumulative Usage is not derived from calls")
        if self.cumulative_provider_tokens > self.maximum_total_tokens:
            raise ValueError("Provider audit exceeds its frozen rollout budget")
        if (self.no_call_terminal is None) != (self.denied_no_call_count == 0):
            raise ValueError("Provider no-call terminal accounting is inconsistent")
        if self.contract_failure_ids != tuple(sorted(set(self.contract_failure_ids))):
            raise ValueError("Provider Contract failures are not canonical")
        expected_status = "failed" if self.contract_failure_ids else "passed"
        if self.status != expected_status:
            raise ValueError("Provider budget audit status is inconsistent")
        if self.strict_budget_closed != (
            self.status == "passed" and self.all_provider_calls_precertified
        ):
            raise ValueError("Provider strict-budget status is inconsistent")
        if self.audit_id != provider_token_budget_audit_id(self):
            raise ValueError("Provider token budget Audit identity is invalid")
        return self


class BudgetClosedJsonClient:
    """A zero-trust token ledger wrapped around one exact Provider route."""

    def __init__(
        self,
        client: JsonCompletionClient,
        contract: ProviderTokenBudgetContract,
    ) -> None:
        config = client.config
        if config.provider != contract.provider or config.model != contract.model_id:
            raise ValueError("budget Contract does not bind the Provider client")
        if config.max_output_tokens != contract.maximum_output_tokens:
            raise ValueError("budget Contract and Provider output bounds differ")
        if config.maximum_model_attempts != 1 or contract.maximum_model_attempts != 1:
            raise ValueError("budget closure requires one model attempt per client call")
        if config.fallback_models or not config.require_requested_model:
            raise ValueError("budget closure requires exact model identity and no fallback")
        self._client = client
        self._contract = contract
        self._certificates: list[ProviderTokenBudgetCertificate] = []
        self._usage_records: list[ProviderTokenUsageRecord] = []
        self._request_prompts: list[str] = []
        self._telemetry: list[ModelCallTelemetry] = []
        self._contract_failure_ids: set[str] = set()
        self._no_call_terminal: ProviderBudgetNoCallTerminal | None = None
        self._cumulative_tokens = 0

    @property
    def config(self) -> AgentModelConfig:
        return self._client.config

    @property
    def contract(self) -> ProviderTokenBudgetContract:
        return self._contract

    @property
    def no_call_terminal(self) -> ProviderBudgetNoCallTerminal | None:
        return self._no_call_terminal

    @property
    def contract_failure_ids(self) -> tuple[str, ...]:
        return tuple(sorted(self._contract_failure_ids))

    @property
    def actual_request_prompts(self) -> tuple[str, ...]:
        return tuple(self._request_prompts)

    @property
    def telemetry(self) -> tuple[ModelCallTelemetry, ...]:
        return tuple(self._telemetry)

    def complete_json(self, prompt: str) -> tuple[dict[str, Any], ModelCallTelemetry]:
        if self._contract_failure_ids:
            raise LLMClientError("Provider token budget Contract is already failed")
        if self._no_call_terminal is not None:
            raise LLMClientError("Provider call forbidden by frozen no-call terminal")
        certificate = self._make_certificate(prompt)
        self._certificates.append(certificate)
        if not certificate.provider_call_permitted:
            terminal_values = {
                "contract_id": self._contract.contract_id,
                "denied_certificate_id": certificate.certificate_id,
                "request_index": certificate.request_index,
                "request_kind": certificate.request_kind,
                "request_hash": certificate.request_hash,
                "reason_code": certificate.denial_reason,
            }
            provisional = ProviderBudgetNoCallTerminal.model_construct(
                terminal_id="pending", **terminal_values
            )
            self._no_call_terminal = ProviderBudgetNoCallTerminal(
                terminal_id=provider_budget_no_call_terminal_id(provisional),
                **terminal_values,
            )
            raise LLMClientError(
                f"Provider call denied before construction: {certificate.denial_reason}"
            )
        try:
            payload, telemetry = self._client.complete_json(prompt)
        except LLMClientError as exc:
            if len(exc.telemetry) > 1:
                self._contract_failure_ids.add("resource_budget:multiple_model_attempts")
            for item in exc.telemetry:
                self._record_usage(certificate, prompt, item)
            if self._contract_failure_ids:
                raise LLMClientError(
                    "Provider token budget Contract failed",
                    exc.telemetry,
                ) from exc
            raise
        self._record_usage(certificate, prompt, telemetry)
        if self._contract_failure_ids:
            raise LLMClientError(
                "Provider token budget Contract failed",
                (telemetry,),
            )
        return payload, telemetry

    def audit(self) -> ProviderTokenBudgetAudit:
        failure_ids = tuple(sorted(self._contract_failure_ids))
        values = {
            "contract_id": self._contract.contract_id,
            "certificates": tuple(self._certificates),
            "usage_records": tuple(self._usage_records),
            "no_call_terminal": self._no_call_terminal,
            "actual_request_prompt_hashes": tuple(
                _sha256_text(item) for item in self._request_prompts
            ),
            "provider_call_count": len(self._usage_records),
            "permitted_request_count": sum(
                item.provider_call_permitted for item in self._certificates
            ),
            "denied_no_call_count": sum(
                not item.provider_call_permitted for item in self._certificates
            ),
            "cumulative_provider_tokens": self._cumulative_tokens,
            "maximum_total_tokens": self._contract.maximum_total_tokens,
            "contract_failure_ids": failure_ids,
            "all_provider_calls_precertified": len(self._usage_records)
            <= sum(item.provider_call_permitted for item in self._certificates),
            "strict_budget_closed": not failure_ids,
            "status": "failed" if failure_ids else "passed",
        }
        provisional = ProviderTokenBudgetAudit.model_construct(audit_id="pending", **values)
        return ProviderTokenBudgetAudit(
            audit_id=provider_token_budget_audit_id(provisional),
            **values,
        )

    def _make_certificate(self, prompt: str) -> ProviderTokenBudgetCertificate:
        prompt_bytes = len(prompt.encode("utf-8"))
        request_kind, repaired_kind = _provider_request_kind(prompt)
        repair_reserve, final_reserve = _required_reserves(
            request_kind,
            repaired_kind,
            self._contract,
        )
        prompt_upper = prompt_bytes + self._contract.provider_chat_envelope_token_upper_bound
        request_upper = prompt_upper + self._contract.maximum_output_tokens
        projected_without_reserve = self._cumulative_tokens + request_upper
        projected = projected_without_reserve + repair_reserve + final_reserve
        denial: NoCallReason | None = None
        if prompt_bytes > self._contract.maximum_prompt_utf8_bytes:
            denial = "oversized_prompt"
        elif projected_without_reserve > self._contract.maximum_total_tokens:
            denial = "request_bound_exceeds_remaining_budget"
        elif projected > self._contract.maximum_total_tokens:
            denial = "required_reserve_not_available"
        values = {
            "contract_id": self._contract.contract_id,
            "request_index": len(self._certificates),
            "request_kind": request_kind,
            "repaired_request_kind": repaired_kind,
            "request_hash": _sha256_text(prompt),
            "prompt_utf8_bytes": prompt_bytes,
            "prompt_token_upper_bound": prompt_upper,
            "completion_token_upper_bound": self._contract.maximum_output_tokens,
            "request_token_upper_bound": request_upper,
            "cumulative_provider_tokens_before": self._cumulative_tokens,
            "contract_repair_reserve_tokens": repair_reserve,
            "final_answer_reserve_tokens": final_reserve,
            "required_reserve_tokens": repair_reserve + final_reserve,
            "projected_upper_total": projected,
            "maximum_total_tokens": self._contract.maximum_total_tokens,
            "decision": "denied_no_call" if denial is not None else "allowed",
            "denial_reason": denial,
            "provider_call_permitted": denial is None,
        }
        provisional = ProviderTokenBudgetCertificate.model_construct(
            certificate_id="pending", **values
        )
        return ProviderTokenBudgetCertificate(
            certificate_id=provider_token_budget_certificate_id(provisional),
            **values,
        )

    def _record_usage(
        self,
        certificate: ProviderTokenBudgetCertificate,
        prompt: str,
        telemetry: ModelCallTelemetry,
    ) -> None:
        self._request_prompts.append(prompt)
        self._telemetry.append(telemetry)
        checks: dict[str, bool] = {
            "request_hash_match": telemetry.request_hash == certificate.request_hash,
            "requested_model_match": telemetry.model_requested == self._contract.model_id,
            "fallback_absent": not telemetry.fallback_used,
        }
        counted = 0
        if telemetry.http_success:
            prompt_tokens = telemetry.prompt_tokens
            completion_tokens = telemetry.completion_tokens
            total_tokens = telemetry.total_tokens
            cache_hit_tokens = telemetry.prompt_cache_hit_tokens
            cache_miss_tokens = telemetry.prompt_cache_miss_tokens
            prompt_present = prompt_tokens is not None
            completion_present = completion_tokens is not None
            total_present = total_tokens is not None
            checks.update(
                {
                    "successful_usage_present": (
                        prompt_present and completion_present and total_present
                    ),
                    "prompt_completion_sum_match": (
                        prompt_tokens is not None
                        and completion_tokens is not None
                        and total_tokens is not None
                        and prompt_tokens + completion_tokens == total_tokens
                    ),
                    "prompt_upper_bound_respected": (
                        prompt_tokens is not None
                        and prompt_tokens <= certificate.prompt_token_upper_bound
                    ),
                    "completion_upper_bound_respected": (
                        completion_tokens is not None
                        and completion_tokens <= certificate.completion_token_upper_bound
                    ),
                    "request_upper_bound_respected": (
                        total_tokens is not None
                        and total_tokens <= certificate.request_token_upper_bound
                    ),
                    "rollout_ceiling_respected": (
                        total_tokens is not None
                        and self._cumulative_tokens + total_tokens
                        <= self._contract.maximum_total_tokens
                    ),
                }
            )
            if cache_hit_tokens is not None or cache_miss_tokens is not None:
                checks["cache_partition_sum_match"] = (
                    prompt_tokens is not None
                    and cache_hit_tokens is not None
                    and cache_miss_tokens is not None
                    and cache_hit_tokens + cache_miss_tokens == prompt_tokens
                )
            if total_tokens is not None:
                counted = total_tokens
        ordered_checks = dict(sorted(checks.items()))
        failures = tuple(
            f"resource_budget:{key}" for key, passed in ordered_checks.items() if not passed
        )
        cumulative_after = self._cumulative_tokens + counted
        values = {
            "contract_id": self._contract.contract_id,
            "certificate_id": certificate.certificate_id,
            "request_index": certificate.request_index,
            "request_hash": certificate.request_hash,
            "http_success": telemetry.http_success,
            "prompt_tokens": telemetry.prompt_tokens,
            "completion_tokens": telemetry.completion_tokens,
            "total_tokens": telemetry.total_tokens,
            "counted_tokens": counted,
            "cumulative_provider_tokens_after": cumulative_after,
            "validation_checks": ordered_checks,
            "failure_ids": failures,
            "passed": not failures,
        }
        provisional = ProviderTokenUsageRecord.model_construct(record_id="pending", **values)
        record = ProviderTokenUsageRecord(
            record_id=provider_token_usage_record_id(provisional),
            **values,
        )
        self._usage_records.append(record)
        self._cumulative_tokens = cumulative_after
        self._contract_failure_ids.update(failures)


def make_provider_token_budget_contract(
    *,
    provider: str,
    model_id: str,
    maximum_total_tokens: int,
    maximum_prompt_utf8_bytes: int,
    maximum_output_tokens: int,
    provider_chat_envelope_token_upper_bound: int,
    contract_repair_reserve_tokens: int,
    final_answer_reserve_tokens: int,
) -> ProviderTokenBudgetContract:
    values = {
        "provider": provider,
        "model_id": model_id,
        "maximum_total_tokens": maximum_total_tokens,
        "maximum_prompt_utf8_bytes": maximum_prompt_utf8_bytes,
        "maximum_output_tokens": maximum_output_tokens,
        "provider_chat_envelope_token_upper_bound": (provider_chat_envelope_token_upper_bound),
        "contract_repair_reserve_tokens": contract_repair_reserve_tokens,
        "final_answer_reserve_tokens": final_answer_reserve_tokens,
    }
    provisional = ProviderTokenBudgetContract.model_construct(contract_id="pending", **values)
    return ProviderTokenBudgetContract(
        contract_id=provider_token_budget_contract_id(provisional),
        **values,
    )


def provider_token_budget_contract_id(value: ProviderTokenBudgetContract) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"contract_id"}),
        prefix="provider_token_budget_contract:",
    )


def provider_token_budget_certificate_id(value: ProviderTokenBudgetCertificate) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"certificate_id"}),
        prefix="provider_token_budget_certificate:",
    )


def provider_token_usage_record_id(value: ProviderTokenUsageRecord) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"record_id"}),
        prefix="provider_token_usage_record:",
    )


def provider_budget_no_call_terminal_id(value: ProviderBudgetNoCallTerminal) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"terminal_id"}),
        prefix="provider_budget_no_call_terminal:",
    )


def provider_token_budget_audit_id(value: ProviderTokenBudgetAudit) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"audit_id"}),
        prefix="provider_token_budget_audit:",
    )


def _provider_request_kind(
    prompt: str,
) -> tuple[ProviderRequestKind, ProviderRequestKind | None]:
    base_prompt = prompt.split(_REPAIR_MARKER, 1)[0]
    if base_prompt.startswith(_PLAN_HEADER):
        base_kind: ProviderRequestKind = "plan"
    elif base_prompt.startswith(_SCRIPTED_HEADER):
        base_kind = "scripted_tool"
    elif base_prompt.startswith(_FINAL_HEADER):
        base_kind = "final_answer"
    elif base_prompt.startswith(_DECISION_HEADER):
        base_kind = "decision"
    else:
        base_kind = "unknown"
    if _REPAIR_MARKER in prompt:
        return "contract_repair", base_kind
    return base_kind, None


def _required_reserves(
    request_kind: ProviderRequestKind,
    repaired_kind: ProviderRequestKind | None,
    contract: ProviderTokenBudgetContract,
) -> tuple[int, int]:
    if request_kind == "contract_repair":
        return (
            0,
            0 if repaired_kind == "final_answer" else contract.final_answer_reserve_tokens,
        )
    if request_kind == "final_answer":
        return contract.contract_repair_reserve_tokens, 0
    return (
        contract.contract_repair_reserve_tokens,
        contract.final_answer_reserve_tokens,
    )


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()
