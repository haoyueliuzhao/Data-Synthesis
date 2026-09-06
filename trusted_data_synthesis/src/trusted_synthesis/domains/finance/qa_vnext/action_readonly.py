"""Invoke unchanged Action admission, including pure adapter preparation, without execution."""

from __future__ import annotations

import copy
import hashlib
from dataclasses import dataclass
from typing import Any, cast

from trusted_synthesis.canonical_json import canonical_json_bytes

from .action_public_contract import rejection_feedback
from .protocol import ProtocolError, parse, record, require
from .runtime import PublicQARuntime, TaskAdapter


@dataclass(frozen=True)
class _ReadonlyActionContext:
    pending: Any
    terminal: bool
    actions: int
    bounds: dict[str, int]
    claims: list[dict[str, Any]]
    adapter: TaskAdapter


def evaluate_action_readonly(
    raw: bytes, request: dict[str, Any], adapter: TaskAdapter, *, max_actions: int = 12
) -> dict[str, Any]:
    before = canonical_json_bytes(request)
    challenge = copy.deepcopy(request)
    state = challenge["state"]
    view = _ReadonlyActionContext(
        state["pending_observation"],
        state["terminal"],
        state["action_count"],
        {"actions": max_actions},
        copy.deepcopy(state["accepted_claims"]),
        adapter,
    )
    claims_before = canonical_json_bytes(view.claims)
    require(adapter.context["id"] == request["context"]["id"], "action_readonly.context")
    submitted = prepared = None
    try:
        submitted = parse(raw)
        require(submitted["kind"] == "action", "action_readonly.action_required")
        prepared = PublicQARuntime._admit(cast(Any, view), submitted, challenge)
    except (ProtocolError, ValueError, KeyError, TypeError) as error:
        code = str(error)
    else:
        code = None
    require(
        canonical_json_bytes(request) == before == canonical_json_bytes(challenge)
        and canonical_json_bytes(view.claims) == claims_before,
        "action_readonly.immutable",
    )
    return record(
        "action_readonly_evaluation",
        request_id=request["id"],
        state_id=state["id"],
        raw_sha256=hashlib.sha256(raw).hexdigest(),
        structure_valid=submitted is not None,
        action_admitted=prepared is not None,
        error_code=code,
        selected_action_id=prepared["option"]["id"] if prepared else None,
        feedback=rejection_feedback(code, request, submitted) if code else None,
        original_runtime_admission_used=True,
        pure_adapter_preparation_permitted=True,
        readonly=True,
        action_executions=0,
        update_commits=0,
        provider_calls=0,
    )
