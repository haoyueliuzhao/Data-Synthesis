"""One newly registered 1000x8 V7 batch, with no old-stock splicing or resampling.

Generation may finish below full coverage when its fixed budget is exhausted.
No scoring, review or training is admitted from such a prefix. Original settled
HTTP bytes can reconstruct an interrupted prefix; only proved-unsent turns send.
"""

from __future__ import annotations

import argparse
import asyncio
import copy
import fcntl
import hashlib
import json
import math
import os
import signal
import sqlite3
import subprocess
from collections import Counter
from pathlib import Path

import httpx

from .calibration import now, publish, status
from .contracts import (
    Episode,
    ModelTurn,
    PrivateReference,
    RunConfig,
    TaskBundle,
    digest,
    invocation_identity,
)
from .harness import public_initial_messages, run_episode
from .probe_budget import ProbeBudget, read_budget_snapshot
from .probe_collection import ENV_FILE, slot_directory
from .probe_provider import MODEL, BudgetedDeepSeekFlashProvider
from .providers import _api_messages, _json, parse_tool_calls
from .settlement import episode_is_complete
from .storage import EventSink, _read_snapshot_rows, load_public_snapshot, read_json
from .v6_collection import STUDY, bound, persist, require, sha
from .v6_review_revision import _key
from .v6_task import score_public_reasoning_program
from .v8_collection import ORIGINAL, public_tasks
from .v8_representation import validate_material_registration

OUTPUT = STUDY / "v10_new8000_01"
BATCH_ID = "finqa-v10-20260929-new8000-01"
AUDIT = Path(
    "/home/zhuxinrui/.codex/attachments/8cd620af-ed38-4f60-a0bc-af495a58a462/已粘贴的文本.txt"
)
WORKTREE = Path(__file__).resolve().parents[4]
PROTECTED_GENERATION_SOURCES = (
    "v10_generation.py",
    "v10_budget.py",
    "probe_budget.py",
    "probe_provider.py",
    "harness.py",
    "contracts.py",
    "providers.py",
    "profiles.py",
    "tools.py",
    "v6_task.py",
    "settlement.py",
    "storage.py",
    "encoding.py",
    "v10_record_audit.py",
    "native_metrics.py",
    "v10_review_protocol.py",
    "v10_process_review.py",
    "v10_review_provider.py",
    "v8_collection.py",
    "v6_collection.py",
    "calibration.py",
)


def checked(path):
    value = read_json(path)
    require(
        value.get("id") == digest({k: v for k, v in value.items() if k != "id"}), "record changed"
    )
    return value


def source_binding():
    root = Path(__file__).parent
    return {name: sha(root / name) for name in PROTECTED_GENERATION_SOURCES}


def build_plan(*, batch_id=BATCH_ID, wallet=None):
    from .v10_budget import generation_episode_id
    from .v10_review_protocol import review_policy_definition

    original = read_json(ORIGINAL)
    original_identity = validate_material_registration(original)
    public_tasks(original)
    budget_path = Path(wallet or STUDY / "experiment0_01/budget.sqlite3").resolve()
    history = read_budget_snapshot(budget_path)
    b = history["snapshot"]
    require(
        not b["pending_requests"] and not b["halt"] and not b["unacknowledged_unknown_requests"],
        "quiescent original wallet required",
    )
    require(
        b.get("effective_hard_cap_microcny") == 1_200_000_000,
        "original effective 1200 cap required",
    )
    require(
        b["remaining_exposure_microcny"] >= 650_000_000,
        "registered generation/review sub-budgets unavailable",
    )
    require(
        b["request_cap"] - b["requests_reserved"] >= 216_000,
        "registered request allocations unavailable",
    )
    slots = [
        dict(
            slot_id=generation_episode_id(batch_id, s["task_id"], s["slot_index"]),
            task_id=s["task_id"],
            slot_index=s["slot_index"],
            purpose="common_material_candidate",
        )
        for s in original["slots"]
    ]
    require(
        len(slots) == len({s["slot_id"] for s in slots}) == 8000,
        "new independent 8000 roster required",
    )
    require(
        not {s["slot_id"] for s in slots} & {s["slot_id"] for s in original["slots"]},
        "old slot identity cannot be reused",
    )
    order = {task: i for i, task in enumerate(original["task_ids"])}
    policy = review_policy_definition()
    return bound(
        dict(
            schema="v10_new8000_generation_protocol.v1",
            at=now(),
            batch_id=batch_id,
            authorization="参照审计修订并开展后续实验",
            audit_source=dict(path=str(AUDIT), sha256=sha(AUDIT)),
            source_worktree=str(WORKTREE),
            source_commit=subprocess.check_output(
                ["git", "rev-parse", "HEAD"], cwd=WORKTREE, text=True
            ).strip(),
            protected_generation_sources=source_binding(),
            original_protocol=dict(path=str(ORIGINAL), sha256=sha(ORIGINAL), id=original["id"]),
            original_registration_identity=original_identity,
            original=original,
            snapshot=original["original_snapshot"],
            snapshot_id=original["snapshot_id"],
            task_ids=original["task_ids"],
            task_denominator=1000,
            slot_denominator=8000,
            slots=slots,
            configs_by_task=original["configs_by_task"],
            launch_order=[
                s["slot_id"]
                for s in sorted(slots, key=lambda s: (s["slot_index"], order[s["task_id"]]))
            ],
            generation_inputs_and_per_task_configs_unchanged=True,
            new_slot_identities=True,
            policy=policy,
            review_policy_id=policy["id"],
            policy_frozen_before_generation=True,
            api_model=MODEL,
            concurrency=8,
            proxy_policy="DeepSeek direct, trust_env=False, TLS on, no retry",
            budget_database=str(budget_path),
            budget_config=history["config"],
            budget_config_sha256=history["config_sha256"],
            wallet_before=history,
            generation_request_subcap=199000,
            generation_microcny_subcap=100_000_000,
            annotation_request_subcap=17000,
            annotation_microcny_subcap=550_000_000,
            unused_budget_not_automatically_spendable=True,
            completion_guaranteed=False,
            all_8000_terminals_before_native=True,
            native_infrastructure_unknown_is_not_zero=True,
            all_declared_review_jobs_before_material_freeze=True,
            require_some_reason_supervision_for_reasoning_mainline=True,
            no_prefix_training=True,
            old_stock_spliced=False,
            no_sampling_until_success=True,
            M=None,
            N=None,
            conditional_domain=(
                "Q_native true AND A valid AND B valid; all joint-valid originals mapped/encoded"
            ),
            mu="1/N after complete material freeze",
            arms=["Static", "Manual+", "Manual-", "C-only", "Full"],
            seeds=[11, 29, 47],
            epochs=10,
            feedback_denominator=700,
            no_arbitrary_minimum_N=True,
            pre_student_scale_rule=(
                "exploratory only if D_pi>0 and within-task chi0/1 support; "
                "otherwise report degenerate and do not run equivalent arms"
            ),
            no_new_paid_pilot=True,
            Base33_and_Base883_reused_under_original_contract=True,
            downstream_loader_implementation_may_follow_without_changing_frozen_policy=True,
            recovery=dict(
                SETTLED="exact original HTTP bytes; no resend",
                RESERVED="same proved-unsent reservation and original body only",
                DISPATCHED="block, never resend",
                UNKNOWN="permanent hold and explicit bounded terminal; no resend",
                deterministic_tools=(
                    "read-only replay to reconstruct a settled prefix; "
                    "retained historical event records are never replaced"
                ),
            ),
        )
    )


def checked_plan(output=OUTPUT):
    plan = checked(Path(output) / "registration/protocol.json")
    current_sources = source_binding()
    if plan["protected_generation_sources"] != current_sources:
        from .v10_execution_revision import validate_source_transition

        validate_source_transition(
            output,
            plan,
            scope="generation",
            original=plan["protected_generation_sources"],
            current=current_sources,
        )
    require(
        plan["original_protocol"]["sha256"] == sha(plan["original_protocol"]["path"]),
        "original contract changed",
    )
    return plan


def ledger_for(plan):
    cfg = plan["budget_config"]
    actual = read_budget_snapshot(plan["budget_database"])
    require(
        actual["config_sha256"] == plan["budget_config_sha256"],
        "original shared wallet config changed",
    )
    return ProbeBudget(
        plan["budget_database"],
        **{
            k: cfg[k]
            for k in (
                "run_id",
                "price_sheet",
                "max_output_tokens",
                "purpose",
                "hard_cap_microcny",
                "warning_microcny",
                "request_cap",
                "amendment_id",
                "allowed_output_limits",
            )
        },
    )


def register(output=OUTPUT):
    from .v10_budget import register_v10_batch

    output = Path(output)
    if (output / "registration/protocol.json").exists():
        plan = checked_plan(output)
    else:
        require(not output.exists(), "new batch directory required")
        plan = build_plan()
        publish(output / "registration", plan, "protocol.json")
    partition = register_v10_batch(
        plan["budget_database"],
        batch_id=plan["batch_id"],
        generation_slots=plan["slots"],
        expected_run_id=plan["budget_config"]["run_id"],
        expected_config_sha256=plan["budget_config_sha256"],
        evidence=dict(
            user_authorization=plan["authorization"],
            audit_source=plan["audit_source"],
            protocol_id=plan["id"],
            review_policy_id=plan["review_policy_id"],
            no_completion_guarantee=True,
        ),
    )
    persist(output / "budget_partition", partition)
    return plan


def _body(messages, tools, config):
    body = dict(
        model=MODEL,
        messages=_api_messages(messages),
        temperature=1.0,
        top_p=1.0,
        max_tokens=config.max_new_tokens,
        stream=False,
        thinking={"type": "disabled"},
    )
    if tools:
        body["tools"] = copy.deepcopy(tools)
    return body


def restored_turn(ledger, row, body, coordinates):
    require(
        row["state"] == "SETTLED"
        and row["response_classification"] == "model_response"
        and row["dispatched_at"] is not None
        and 200 <= row["http_status"] < 300,
        "only settled actual model returns can be replayed",
    )
    wire, raw = _json(body).encode(), bytes(row["response_body"])
    require(
        bytes(row["request_body"]) == wire
        and row["request_sha256"] == digest(body)
        and json.loads(row["coordinates_json"]) == coordinates,
        "settled prefix request/coordinates changed",
    )
    require(
        hashlib.sha256(raw).hexdigest() == row["response_sha256"], "original response bytes changed"
    )
    response = json.loads(raw)
    require(
        response["model"] == MODEL and len(response["choices"]) == 1,
        "original model response envelope changed",
    )
    choice = response["choices"][0]
    message = choice["message"]
    usage = response["usage"]
    counters = ledger.price_sheet.usage(usage, output_limit=body["max_tokens"])
    require(
        usage == json.loads(row["usage_json"])
        and ledger.price_sheet.cost_microcny(
            hit=counters["prompt_cache_hit_tokens"],
            miss=counters["prompt_cache_miss_tokens"],
            output=counters["completion_tokens"],
        )
        == row["settled_microcny"],
        "original usage/settlement changed",
    )
    require(
        not message.get("reasoning_content")
        and choice["finish_reason"] in {"stop", "length", "tool_calls", "content_filter"},
        "not a completed public response",
    )
    raw_calls = message.get("tool_calls") or []
    try:
        calls = parse_tool_calls(_json({"tool_calls": raw_calls}), call_prefix=response["id"])
    except (ValueError, TypeError, IndexError, RecursionError):
        calls = ()
    parse_error = "malformed_native_tool_calls_no_repair" if raw_calls and not calls else None
    return ModelTurn(
        raw_text=message.get("content") or "",
        tool_calls=calls,
        finish_reason=choice["finish_reason"],
        usage={k: v for k, v in usage.items() if type(v) is int},
        provider_metadata=dict(
            public_request=body,
            request_sha256=digest(body),
            public_request_body_sha256=hashlib.sha256(wire).hexdigest(),
            api_response=response,
            api_response_raw=raw.decode(),
            raw_api_response_sha256=row["response_sha256"],
            tool_protocol="deepseek-native-tool-calls-v1",
            parse_error=parse_error,
            model_tool_format_failure=parse_error is not None,
            local_token_receipt_available=False,
            API_and_local_token_budget_equivalence_claimed=False,
            context_limit_locally_verified=False,
            requested_context_limit_not_an_API_token_fact=ledger.price_sheet.context_input_token_ceiling,
            official_input_reservation_token_ceiling=ledger.price_sheet.context_input_token_ceiling,
            thinking_contract={"type": "disabled"},
            retries=0,
            budget_invocation_id=row["invocation_id"],
            budget_coordinates=coordinates,
            price_sheet_id=ledger.price_sheet.id,
            budget_reserved_microcny=row["reserved_microcny"],
            peak_tariff_upper_bound_microcny=row["settled_microcny"],
            cost_is_provider_invoice=False,
            restored_original_paid_response=True,
            new_HTTP_calls_for_this_replay=0,
        ),
    )


class ReservedContinuation:
    """A RESERVED row is proven unsent; reuse that exact reservation, not a new ID."""

    def __init__(self, ledger, original):
        self.ledger, self.original = ledger, original

    def __getattr__(self, name):
        return getattr(self.ledger, name)

    def reserve(self, invocation_id, *, coordinates, request, request_body):
        from .v10_budget import continue_reserved

        row = self.ledger.request_record(invocation_id)
        require(
            row is not None
            and row["state"] == "RESERVED"
            and row["dispatched_at"] is None
            and row["invocation_id"] == self.original["invocation_id"]
            and bytes(row["request_body"]) == request_body
            and row["request_sha256"] == digest(request)
            and json.loads(row["coordinates_json"]) == coordinates,
            "reserved continuation differs or was already dispatched",
        )
        return continue_reserved(
            self.ledger,
            invocation_id,
            coordinates=coordinates,
            request=request,
            request_body=request_body,
        )


class V10Probe(BudgetedDeepSeekFlashProvider):
    def _unknown(self, invocation_id, *, reason, **kwargs):
        if reason == "transport response or billing usage unknown":
            reason = "v10 transport response or usage unknown"
            coordinates = invocation_identity(self.scope, turn_index=self._turn_index - 1)
            require(coordinates["invocation_id"] == invocation_id, "unknown invocation differs")
            kwargs["evidence"] = {
                **(kwargs.get("evidence") or {}),
                "budget_coordinates": coordinates,
            }
        return super()._unknown(invocation_id, reason=reason, **kwargs)


class RecoverableProbe:
    """Count original paid invocations represented in the reconstructed Episode.

    ``new_HTTP_calls`` is separate: replayed turns are not additional model samples.
    The unmodified V7 harness may replay deterministic public tools for the prefix.
    """

    def __init__(self, ledger, key, sid, client, stopped=None, operator_stop=None):
        self.ledger, self.key, self.sid, self.client = ledger, key, sid, client
        self.stopped = stopped
        self.operator_stop = operator_stop
        self.provider = V10Probe(ledger=ledger, api_key=key, episode_id=sid, client=client)
        self.identity = self.provider.identity
        self.actual_model_calls = self.new_HTTP_calls = self.index = 0
        self.replayed_ids = []

    async def chat(self, messages, tools, config):
        coords = invocation_identity(
            dict(run_id=self.ledger.run_id, episode_id=self.sid, attempt_index=1),
            turn_index=self.index,
        )
        row = self.ledger.request_record(coords["invocation_id"])
        body = _body(messages, tools, config)
        if row is not None and row["state"] == "SETTLED":
            turn = restored_turn(self.ledger, row, body, coords)
            self.replayed_ids.append(row["invocation_id"])
            self.actual_model_calls += 1
            self.index += 1
            return turn
        require(
            row is None or row["state"] == "RESERVED",
            "existing dispatched/UNKNOWN request is never resent",
        )
        require(
            self.stopped is None or not self.stopped.is_set(), "dispatch paused before unsent turn"
        )
        require(
            self.operator_stop is None or not self.operator_stop.is_set(),
            "operator stopped dispatch before unsent turn",
        )
        self.provider.ledger = (
            self.ledger if row is None else ReservedContinuation(self.ledger, row)
        )
        self.provider._turn_index = self.index
        self.provider.timeout = max(180, math.ceil(90 + config.max_new_tokens / 128))
        before = self.provider.actual_model_calls
        try:
            return await self.provider.chat(messages, tools, config)
        finally:
            delta = self.provider.actual_model_calls - before
            self.actual_model_calls += delta
            self.new_HTTP_calls += delta
            self.index = self.provider._turn_index


def generation_rows(ledger, plan):
    sids = {s["slot_id"] for s in plan["slots"]}
    with sqlite3.connect(ledger.path.resolve().as_uri() + "?mode=ro", uri=True) as con:
        con.row_factory = sqlite3.Row
        return [
            dict(r)
            for r in con.execute(
                "SELECT * FROM requests WHERE "
                "json_extract(coordinates_json,'$.episode_id') LIKE 'v10gen:%'"
            )
            if json.loads(r["coordinates_json"])["episode_id"] in sids
        ]


def integrity_record(task, episode, slot):
    from .v10_record_audit import inspect_episode

    row, _ = inspect_episode(episode, task, slot, q_native=None)
    c = row["checks"]
    checks = dict(
        sealed=episode_is_complete(episode),
        calls_settled=episode.all_provider_calls_settled,
        history_complete=all(
            c[k] is True
            for k in (
                "initial_public_input_exact",
                "request_history_chain_exact",
                "API_public_content_exact",
                "API_parsed_tool_calls_exact",
            )
        ),
        actions_observations_bound=c["saved_action_event_links_exact"] is True
        and c["public_view_exact"] is True,
        private_reference_isolated=c["initial_public_input_exact"] is True,
    )
    return bound(
        dict(
            schema="v10_generated_record_integrity.v1",
            episode_sha256=digest(episode),
            slot_id=slot["slot_id"],
            checks=checks,
            original_mechanical_checks=c,
            semantic_quality_not_assessed=True,
        )
    )


def completed_slots(output, plan):
    records = {}
    for slot in plan["slots"]:
        path = slot_directory(output, slot) / "outcome/record.json"
        if not path.exists():
            continue
        row = checked(path)
        require(
            row["slot"] == slot
            and row["protocol_id"] == plan["id"]
            and row["status"] in {"COMPLETE", "NETWORK_UNKNOWN_TERMINAL"},
            "canonical generation outcome changed",
        )
        if row["status"] == "COMPLETE":
            require(
                sha(row["episode_path"]) == row["episode_file_sha256"],
                "original episode bytes changed",
            )
        records[slot["slot_id"]] = row
    return records


def recover_local_completed(output, plan):
    """Recover a completed durable Episode before any attempt at another HTTP call."""
    tasks = None
    for slot in plan["slots"]:
        directory = slot_directory(output, slot)
        if (directory / "outcome/record.json").exists() or not directory.exists():
            continue
        path = directory / "episode/episode.json"
        episode, attempt = None, None
        if path.exists():
            episode = Episode.model_validate_json(path.read_bytes())
        else:
            for candidate in sorted((directory / "attempts").glob("attempt*"), reverse=True):
                events = sorted((candidate / "events").glob("*/event.json"))
                if not events:
                    continue
                terminal = read_json(events[-1])
                if terminal.get("kind") == "episode_completed":
                    saved = Episode.model_validate(terminal["payload"])
                    if episode_is_complete(saved):
                        episode, attempt = saved, candidate
                        break
        if episode is None or not episode_is_complete(episode):
            continue
        require(
            episode.task_id == slot["task_id"]
            and episode.config.model_dump(mode="json") == plan["configs_by_task"][slot["task_id"]],
            "saved terminal belongs to another slot contract",
        )
        if tasks is None:
            tasks = public_tasks(plan["original"])
        integrity = integrity_record(tasks[slot["task_id"]], episode, slot)
        persist(directory / "episode", episode.model_dump(mode="json"), "episode.json")
        persist(directory / "integrity", integrity)
        row = bound(
            dict(
                schema="v10_generation_slot_outcome.v1",
                at=now(),
                protocol_id=plan["id"],
                slot=slot,
                status="COMPLETE",
                episode_path=str(path.resolve()),
                episode_sha256=digest(episode),
                episode_file_sha256=sha(path),
                integrity_id=integrity["id"],
                integrity_path=str((directory / "integrity/record.json").resolve()),
                completed_attempt=str(attempt.resolve()) if attempt else None,
                actual_model_calls=episode.actual_model_calls,
                stop_reason=episode.stop_reason,
                all_provider_calls_settled=True,
                no_resampling=True,
                recovery_from_original_terminal=True,
                new_model_calls_during_recovery=0,
            )
        )
        publish(directory / "outcome", row)


def expected_generation_unknowns(output, plan, ledger):
    """Bind unknown requests to durable V7 intents, not just a ledger's self-hash."""
    tasks = public_tasks(plan["original"])
    slots = {s["slot_id"]: s for s in plan["slots"]}
    acknowledged = {
        r["invocation_id"]
        for r in read_budget_snapshot(plan["budget_database"])["acknowledged_unknowns"]
    }
    expected = {}
    for row in generation_rows(ledger, plan):
        if row["state"] != "UNKNOWN" or row["invocation_id"] in acknowledged:
            continue
        coords = json.loads(row["coordinates_json"])
        slot = slots[coords["episode_id"]]
        cfg = RunConfig.model_validate(plan["configs_by_task"][slot["task_id"]])
        original = public_initial_messages(tasks[slot["task_id"]], cfg)
        matches = []
        for path in (slot_directory(output, slot) / "attempts").glob("*/events/*/event.json"):
            event = read_json(path)
            if (
                event.get("kind") != "model_call_intent"
                or event.get("step") != coords["turn_index"]
            ):
                continue
            payload = event["payload"]
            require(
                payload["config"] == cfg.model_dump(mode="json")
                and payload["messages"][:2] == original,
                "unknown intent's original public input/config differs",
            )
            body = _body(payload["messages"], payload["tools"], cfg)
            matches.append(digest(body))
        require(
            matches and set(matches) == {row["request_sha256"]},
            "UNKNOWN has no matching original durable intent",
        )
        expected[row["invocation_id"]] = matches[-1]
    return expected


def materialize_generation_unknowns(output, plan, ledger):
    """Acknowledge policy-covered missing responses without inventing an Episode."""
    history = read_budget_snapshot(plan["budget_database"])
    ack = {r["invocation_id"]: r for r in history["acknowledged_unknowns"]}
    grouped = {}
    for row in generation_rows(ledger, plan):
        if row["state"] == "UNKNOWN":
            require(
                row["invocation_id"] in ack,
                "unacknowledged generation UNKNOWN blocks terminal materialization",
            )
            sid = json.loads(row["coordinates_json"])["episode_id"]
            grouped.setdefault(sid, []).append(row)
    slots = {s["slot_id"]: s for s in plan["slots"]}
    for sid, rows in grouped.items():
        slot = slots[sid]
        directory = slot_directory(output, slot)
        if (directory / "outcome/record.json").exists():
            require(
                checked(directory / "outcome/record.json")["status"] == "NETWORK_UNKNOWN_TERMINAL",
                "normal completed slot cannot gain an UNKNOWN",
            )
            continue
        partials = sorted((directory / "attempts").glob("*/episode/episode.json"))
        partial = partials[-1] if partials else None
        value = bound(
            dict(
                schema="v10_generation_slot_outcome.v1",
                at=now(),
                protocol_id=plan["id"],
                slot=slot,
                status="NETWORK_UNKNOWN_TERMINAL",
                Q_native=None,
                native_zero_claimed=False,
                unknown_invocation_ids=[r["invocation_id"] for r in rows],
                permanent_reserved_microcny=sum(r["reserved_microcny"] for r in rows),
                acknowledgment_ids=[ack[r["invocation_id"]]["id"] for r in rows],
                original_requests_and_prefix_events_retained=True,
                partial_episode_path=str(partial) if partial else None,
                partial_episode_file_sha256=sha(partial) if partial else None,
                episode_path=None,
                actual_completed_model_responses_not_invented=True,
                no_resampling=True,
            )
        )
        publish(directory / "outcome", value)


def validate_paid_generation(output, plan, ledger, completed):
    """One finite completion check; no historical-archive or tool re-execution."""
    rows = {r["invocation_id"]: r for r in generation_rows(ledger, plan)}
    seen = set()
    for slot in plan["slots"]:
        sid = slot["slot_id"]
        if sid not in completed:
            continue
        outcome = completed[sid]
        if outcome["status"] == "NETWORK_UNKNOWN_TERMINAL":
            for iid, row in rows.items():
                if json.loads(row["coordinates_json"])["episode_id"] == sid:
                    require(
                        row["state"] in {"SETTLED", "UNKNOWN"},
                        "unresolved dispatch in UNKNOWN slot",
                    )
                    seen.add(iid)
            continue
        episode = Episode.model_validate_json(Path(outcome["episode_path"]).read_bytes())
        require(
            episode_is_complete(episode)
            and digest(episode) == outcome["episode_sha256"]
            and episode.task_id == slot["task_id"]
            and episode.config.model_dump(mode="json") == plan["configs_by_task"][slot["task_id"]],
            "normal completed episode identity differs",
        )
        for index, turn in enumerate(episode.turns):
            coord = invocation_identity(
                dict(run_id=ledger.run_id, episode_id=sid, attempt_index=1), turn_index=index
            )
            iid = coord["invocation_id"]
            row = rows.get(iid)
            require(
                row is not None
                and row["state"] == "SETTLED"
                and row["response_classification"] == "model_response"
                and iid not in seen,
                "unique settled actual generation return required",
            )
            metadata = turn.provider_metadata
            require(
                metadata["budget_invocation_id"] == iid
                and json.loads(row["coordinates_json"]) == coord
                and json.loads(row["request_body"]) == metadata["public_request"]
                and bytes(row["response_body"]).decode() == metadata["api_response_raw"]
                and row["response_sha256"] == metadata["raw_api_response_sha256"],
                "saved generation turn differs from original paid bytes",
            )
            seen.add(iid)
    if len(completed) == plan["slot_denominator"]:
        require(seen == set(rows), "unaccounted invocation at complete generation seal")
    return rows


def seal_generation(output, plan, ledger, completed):
    require(
        set(completed) == {s["slot_id"] for s in plan["slots"]},
        "all 8000 terminal slots required, never a completed prefix",
    )
    require(not ledger.snapshot()["pending_requests"], "no in-flight calls at generation seal")
    validate_paid_generation(output, plan, ledger, completed)
    seal = bound(
        dict(
            schema="v10_whole_generation_seal.v1",
            protocol_id=plan["id"],
            batch_id=plan["batch_id"],
            denominator=8000,
            all_slots_have_real_terminal=True,
            private_references_read=False,
            slots=[completed[s["slot_id"]] for s in plan["slots"]],
            terminal_counts=dict(Counter(r["status"] for r in completed.values())),
            old_stock_spliced=False,
            unknown_not_native_zero=True,
        )
    )
    persist(Path(output) / "generation_seal", seal)
    return seal


def network_continuation_classification(ledger, episode, slot):
    """A preliminary stop classifier; the budget helper still validates every UNKNOWN.

    An unrelated local/schema/subcap failure cannot inherit automatic continuation
    from another worker's lost connection. A proved-unsent turn blocked specifically
    by that connection halt is distinct from such a failure.
    """
    from .v10_budget import NETWORK_POLICY, NETWORK_REASON

    result = dict(network_only_continuation_candidate=False, failure_class="non_network_stop")
    if not episode.call_settlements:
        return result
    last = episode.call_settlements[-1]
    evidence = last.evidence
    coords = invocation_identity(
        dict(run_id=ledger.run_id, episode_id=slot["slot_id"], attempt_index=1),
        turn_index=episode.provider_attempts - 1,
    )
    row = ledger.request_record(coords["invocation_id"])
    if (
        last.state == "unknown"
        and row is not None
        and row["state"] == "UNKNOWN"
        and all(row[k] is None for k in ("http_status", "response_body", "usage_json"))
        and evidence.get("service_response_received") is False
        and evidence.get("exception_type") in NETWORK_POLICY["exception_types"]
        and evidence.get("message") == NETWORK_REASON
    ):
        return dict(network_only_continuation_candidate=True, failure_class="connection_unknown")
    paused = evidence.get("message") in {
        "dispatch paused before unsent turn",
        "unknown or halted Probe ledger forbids new requests",
        "ledger halted before dispatch; request not sent",
    }
    if last.state == "pre_call_rejected" and last.actual_model_calls == 0 and paused:
        halt = ledger.snapshot()["halt"] or {}
        stopped_by_connection = (
            halt.get("reason") == NETWORK_REASON
            and halt.get("evidence", {}).get("service_response_received") is False
            and halt.get("evidence", {}).get("exception_type") in NETWORK_POLICY["exception_types"]
        )
        if stopped_by_connection and (
            row is None or (row["state"] == "RESERVED" and row["dispatched_at"] is None)
        ):
            return dict(
                # A remaining RESERVED row still requires explicit recovery: the
                # existing network policy requires pending=0 before acknowledgment.
                network_only_continuation_candidate=row is None,
                failure_class="unsent_blocked_by_connection_halt",
                original_reservation_requires_recovery=row is not None,
            )
    return result


async def collect(output, plan, ledger, key, *, stop_requested=None, client=None):
    output = Path(output)
    tasks = public_tasks(plan["original"])
    stop_requested = stop_requested or asyncio.Event()
    halted = asyncio.Event()
    done = asyncio.Event()
    completed = completed_slots(output, plan)
    active, blocked = set(), []
    slots = {s["slot_id"]: s for s in plan["slots"]}

    def progress(phase="GENERATING"):
        status(
            output,
            dict(
                at=now(),
                phase=phase,
                protocol_id=plan["id"],
                batch_id=plan["batch_id"],
                completed=len(completed),
                denominator=8000,
                complete_model_episodes=sum(r["status"] == "COMPLETE" for r in completed.values()),
                network_unknown_slots=sum(
                    r["status"] == "NETWORK_UNKNOWN_TERMINAL" for r in completed.values()
                ),
                active=len(active),
                not_terminal=8000 - len(completed),
                blocked=blocked[-16:],
                budget=ledger.snapshot(),
                private_references_read=False,
                no_prefix_training=True,
                training_started=False,
            ),
        )

    async def monitor():
        while not done.is_set():
            if stop_requested.is_set():
                halted.set()
            progress()
            try:
                await asyncio.wait_for(done.wait(), 10)
            except TimeoutError:
                pass

    async def one(sid, transport):
        if halted.is_set() or stop_requested.is_set():
            return
        slot = slots[sid]
        directory = slot_directory(output, slot)
        active.add(sid)
        attempt = (
            directory
            / "attempts"
            / f"attempt{len(list((directory / 'attempts').glob('attempt*'))) + 1:04d}"
        )
        publish(
            attempt / "started",
            bound(dict(at=now(), slot=slot, protocol_id=plan["id"], resampling=False)),
        )
        provider = RecoverableProbe(
            ledger, key, sid, transport, stopped=halted, operator_stop=stop_requested
        )
        try:
            episode = await run_episode(
                tasks[slot["task_id"]],
                provider,
                RunConfig.model_validate(plan["configs_by_task"][slot["task_id"]]),
                sink=EventSink(attempt / "events"),
                invocation_context=dict(run_id=ledger.run_id, episode_id=sid, attempt_index=1),
            )
            publish(attempt / "episode", episode.model_dump(mode="json"), "episode.json")
            attempt_record = bound(
                dict(
                    at=now(),
                    slot=slot,
                    protocol_id=plan["id"],
                    episode_sha256=digest(episode),
                    actual_new_HTTP_calls=provider.new_HTTP_calls,
                    replayed_settled_invocation_ids=provider.replayed_ids,
                    original_paid_invocations_represented=episode.actual_model_calls,
                    stop_reason=episode.stop_reason,
                    error=episode.error,
                    all_provider_calls_settled=episode.all_provider_calls_settled,
                    deterministic_tools_may_have_been_replayed=bool(provider.replayed_ids),
                    original_attempts_retained=True,
                )
            )
            publish(attempt / "result", attempt_record)
            if episode_is_complete(episode):
                integrity = integrity_record(tasks[slot["task_id"]], episode, slot)
                publish(directory / "episode", episode.model_dump(mode="json"), "episode.json")
                publish(directory / "integrity", integrity)
                row = bound(
                    dict(
                        schema="v10_generation_slot_outcome.v1",
                        at=now(),
                        protocol_id=plan["id"],
                        slot=slot,
                        status="COMPLETE",
                        episode_path=str((directory / "episode/episode.json").resolve()),
                        episode_sha256=digest(episode),
                        episode_file_sha256=sha(directory / "episode/episode.json"),
                        integrity_id=integrity["id"],
                        integrity_path=str((directory / "integrity/record.json").resolve()),
                        completed_attempt=str(attempt.resolve()),
                        actual_model_calls=episode.actual_model_calls,
                        stop_reason=episode.stop_reason,
                        all_provider_calls_settled=True,
                        no_resampling=True,
                    )
                )
                publish(directory / "outcome", row)
                completed[sid] = row
            else:
                blocked.append(
                    dict(
                        slot_id=sid,
                        reason=episode.stop_reason,
                        error=episode.error,
                        attempt=str(attempt),
                        **network_continuation_classification(ledger, episode, slot),
                    )
                )
                halted.set()
        except BaseException as exc:
            blocked.append(
                dict(
                    slot_id=sid, error_type=type(exc).__name__, error=str(exc), attempt=str(attempt)
                )
            )
            halted.set()
            if not (attempt / "exception").exists():
                publish(
                    attempt / "exception",
                    bound(
                        dict(
                            at=now(),
                            error_type=type(exc).__name__,
                            message=str(exc),
                            resampling=False,
                        )
                    ),
                )
            if not isinstance(exc, Exception):
                raise
        finally:
            active.discard(sid)

    async def dispatch(transport):
        queue = asyncio.Queue()
        for sid in plan["launch_order"]:
            if sid not in completed:
                queue.put_nowait(sid)

        async def worker():
            while not halted.is_set() and not stop_requested.is_set():
                try:
                    sid = queue.get_nowait()
                except asyncio.QueueEmpty:
                    return
                await one(sid, transport)

        await asyncio.gather(*(worker() for _ in range(plan["concurrency"])))

    watcher = asyncio.create_task(monitor())
    try:
        if client is None:
            async with httpx.AsyncClient(
                trust_env=False,
                follow_redirects=False,
                timeout=1200,
                limits=httpx.Limits(max_connections=8, max_keepalive_connections=8),
            ) as transport:
                await dispatch(transport)
        else:
            await dispatch(client)
    finally:
        done.set()
        await watcher
    progress("GENERATION_ALL_TERMINAL" if len(completed) == 8000 else "GENERATION_SAVED_INCOMPLETE")
    return dict(
        completed=completed,
        blocked=blocked,
        operator_stop=stop_requested.is_set(),
        network_only_continuation_safe=bool(blocked)
        and all(b.get("network_only_continuation_candidate") is True for b in blocked),
    )


def score_native_support(output, plan, seal):
    output = Path(output)
    require(
        seal["protocol_id"] == plan["id"] and len(seal["slots"]) == 8000,
        "full generation seal before any private scoring",
    )
    if (output / "native_support/record.json").exists():
        result = checked(output / "native_support/record.json")
        require(
            result["generation_seal_id"] == seal["id"], "native report belongs to another batch"
        )
        return result
    manifest, tasks, lineages = load_public_snapshot(plan["snapshot"])
    require(manifest["id"] == plan["snapshot_id"], "public benchmark changed")
    refs = _read_snapshot_rows(
        plan["snapshot"], "private.references.jsonl", PrivateReference, manifest
    )
    wanted = set(plan["task_ids"])
    bundles = {
        t.task_id: TaskBundle(public=t, reference=r, lineage=lineage)
        for t, r, lineage in zip(tasks, refs, lineages, strict=True)
        if t.task_id in wanted
    }
    rows, correct, unknown = [], Counter(), Counter()
    for outcome in seal["slots"]:
        slot = outcome["slot"]
        if outcome["status"] == "NETWORK_UNKNOWN_TERMINAL":
            score = dict(
                native=dict(execution_accuracy=None, program_accuracy=None),
                status="unknown",
                reason="registered_generation_connection_unknown",
            )
        else:
            episode = Episode.model_validate_json(Path(outcome["episode_path"]).read_bytes())
            require(digest(episode) == outcome["episode_sha256"], "original scored Episode changed")
            score = score_public_reasoning_program(bundles[slot["task_id"]], episode)
        value = score["native"]["execution_accuracy"]
        q = None if value is None else bool(value)
        correct[slot["task_id"]] += q is True
        unknown[slot["task_id"]] += q is None
        rows.append(dict(slot=slot, native=score, Q_native=q, generation_outcome_id=outcome["id"]))
    body = bound(
        dict(
            schema="v10_new_native_support.v1",
            protocol_id=plan["id"],
            batch_id=plan["batch_id"],
            generation_seal_id=seal["id"],
            task_denominator=1000,
            slot_denominator=8000,
            rows=rows,
            M=sum(correct.values()),
            native_unknown_slots=sum(unknown.values()),
            native_supported_tasks=[t for t in plan["task_ids"] if correct[t] > 0],
            support_by_task={
                t: dict(native_correct=correct[t], native_unknown=unknown[t], slots=8)
                for t in plan["task_ids"]
            },
            N=None,
            old_stock_spliced=False,
            zero_native_support_is_not_global_failure=True,
            no_prefix_training=True,
            semantic_review_started=False,
            training_started=False,
        )
    )
    publish(output / "native_support", body)
    return body


async def run(output=OUTPUT, env_file=ENV_FILE):
    output = Path(output)
    plan = checked_plan(output)
    from .v10_budget import acknowledge_connection_unknowns

    with (output / "controller.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        ledger = ledger_for(plan)
        stop_requested = asyncio.Event()
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, stop_requested.set)
        key = _key(env_file)
        os.environ.pop("DEEPSEEK_API_KEY", None)
        while True:
            budget = ledger.snapshot()
            pending = [
                r for r in ledger.blocking_unsettled() if r["state"] in {"RESERVED", "DISPATCHED"}
            ]
            sids = {s["slot_id"] for s in plan["slots"]}
            require(
                all(
                    r["state"] == "RESERVED"
                    and json.loads(r["coordinates_json"])["episode_id"] in sids
                    for r in pending
                ),
                "unresolved dispatched/foreign calls require finite recovery; never resend",
            )
            if budget["halt"] or budget["unacknowledged_unknown_requests"]:
                acknowledgment = acknowledge_connection_unknowns(
                    ledger,
                    batch_id=plan["batch_id"],
                    expected_requests=expected_generation_unknowns(output, plan, ledger),
                )
                if acknowledgment is not None:
                    persist(
                        output / "network_terminal_acknowledgements" / acknowledgment["id"],
                        acknowledgment,
                    )
            materialize_generation_unknowns(output, plan, ledger)
            recover_local_completed(output, plan)
            completed = completed_slots(output, plan)
            if len(completed) == 8000:
                seal = seal_generation(output, plan, ledger, completed)
                native = score_native_support(output, plan, seal)
                status(
                    output,
                    dict(
                        at=now(),
                        phase="GENERATION_SEALED_NATIVE_READY",
                        protocol_id=plan["id"],
                        completed=8000,
                        denominator=8000,
                        M=native["M"],
                        N=None,
                        native_support_id=native["id"],
                        budget=ledger.snapshot(),
                        training_started=False,
                    ),
                )
                return native
            if stop_requested.is_set():
                return None
            result = await collect(output, plan, ledger, key, stop_requested=stop_requested)
            if result["operator_stop"]:
                status(
                    output,
                    dict(
                        at=now(),
                        phase="USER_STOPPED_SAVED",
                        protocol_id=plan["id"],
                        completed=len(result["completed"]),
                        denominator=8000,
                        budget=ledger.snapshot(),
                        no_prefix_training=True,
                    ),
                )
                return None
            if len(result["completed"]) == 8000:
                continue
            budget = ledger.snapshot()
            if (
                budget["unacknowledged_unknown_requests"]
                and result["network_only_continuation_safe"]
            ):
                # Only the explicitly bounded new-cohort network policy can advance.
                continue
            return None  # Budget/local/schema/service stops are not automatic retries.


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("register", "run", "status"))
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--env-file", type=Path, default=ENV_FILE)
    args = parser.parse_args(argv)
    if args.action == "register":
        print(register(args.output)["id"])
    elif args.action == "status":
        print(read_json(args.output / "status.json"))
    else:
        asyncio.run(run(args.output, args.env_file))


if __name__ == "__main__":
    main()
