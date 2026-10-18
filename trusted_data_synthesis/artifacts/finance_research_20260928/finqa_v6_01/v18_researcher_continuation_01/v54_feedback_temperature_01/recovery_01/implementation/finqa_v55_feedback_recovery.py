"""Exactly two explicitly authorized old UNKNOWN request reexecutions.

The scientific request is the provider's original public_request, including its
rendered prompt digest and full configuration. Old ephemeral invocation UUIDs
remain evidence references, never scientific equality keys. An atomic claim is
consumed before model.generate and is never reset, even when no receipt returns.
"""

from __future__ import annotations

import copy
import hashlib
import json
import math
import os
import time
from pathlib import Path

SEEDS = (137, 251, 389)
REEXECUTION_SEEDS = (137, 389)
AUTHORIZATION_SCHEMA = "v55_explicit_two_single_request_reexecutions.v1"


def require(value, message):
    if not value:
        raise ValueError(message)


def digest(value):
    # Keep module import independent of the scientific package: registration
    # must select its original frozen package before importing that package.
    if hasattr(value, "model_dump"):
        value = value.model_dump(mode="json")
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def _read(path):
    path = Path(path).resolve()
    raw = path.read_bytes()
    return json.loads(raw), dict(path=str(path), sha256=hashlib.sha256(raw).hexdigest())


def _read_ref(reference):
    value, observed = _read(reference["path"])
    require(observed == reference, "registered historical evidence changed")
    return value


def _bound(body):
    return {**body, "id": digest(body)}


def _atomic_record(directory, body):
    """No idempotent success: an existing claim always refuses another call."""
    from trusted_synthesis.core.immutable_artifacts import write_immutable_artifact_directory

    value = _bound(body)
    raw = (json.dumps(value, sort_keys=True, ensure_ascii=False, indent=2,
                      allow_nan=False) + "\n").encode()
    write_immutable_artifact_directory(Path(directory), {"record.json": raw})
    return value


def build_registration(old_root):
    """Read-only registration helper; no GPU/model, directory creation or retry."""
    from finqa_v54_temperature import RunConfig, build_condition, checked_condition

    old_root = Path(old_root).resolve()
    protocol, protocol_ref = _read(old_root / "protocol/record.json")
    closeout, closeout_ref = _read(old_root / "closeout/record.json")
    require(closeout["status"] == "STOPPED_FAILURE_NO_RETRY"
            and closeout["active_workers"] == 0 and closeout["automatic_retry"] is False
            and closeout["protocol_id"] == protocol["id"],
            "old experiment must remain stopped without automatic retry")
    rows = {}
    for seed in SEEDS:
        parent, parent_ref = _read(old_root / f"parents/seed{seed}/record.json")
        require(parent["seed"] == seed and parent["protocol_id"] == protocol["id"],
                "historical parent coordinate changed")
        old_t1 = Path(parent["original_T1_feedback_root"])
        intent, intent_ref = _read(old_t1 / "intent/record.json")
        runs = [_read(old_t1 / f"draw{index}/run.json") for index in (0, 1)]
        require(intent["seeds"] == [11, 29] and intent["denominator"] == 700,
                "original fixed feedback roster changed")
        configs = [RunConfig.model_validate(run["config"]).model_copy(update={"temperature": 0.5})
                   for run, _reference in runs]
        condition = build_condition(
            identity=intent["identity"], temperature=0.5, configs=configs,
            task_roster=[dict(dataset="finqa", task_id=task) for task in intent["task_ids"]],
            source_manifest_sha256=intent["source_manifest_sha256"],
            role_plan_id=intent["role_plan_id"],
        )
        stage = old_root / f"stages/seed{seed}/feedback_C05"
        failure, failure_ref = _read(stage / "attempts/attempt0001/failure/record.json")
        actual_exit, exit_ref = _read(stage / "actual_exit/record.json")
        require(actual_exit["actual_waitpid_observed"] is True
                and actual_exit["returncode"] != 0,
                "old scientific process must have actually exited")
        events = sorted((stage / "feedback").glob("*/draw*/events/*/*/event.json"))
        event_records = [(path, *_read(path)) for path in events]
        intents = [item for item in event_records if item[1]["kind"] == "model_call_intent"]
        returned = [item for item in event_records if item[1]["kind"] == "model_call_returned"]
        base = dict(seed=seed, condition=condition, expected_condition_id=condition["id"],
                    point_id=parent["point_id"],
                    parameter_digest=condition["identity"]["parameter_digest"],
                    old_parent=parent_ref, old_worker_failure=failure_ref, old_actual_exit=exit_ref,
                    old_T1_intent=intent_ref, old_T1_draw_runs=[ref for _, ref in runs],
                    old_files_written=False,
                    original_successful_model_returns=len(returned))
        require(not returned, "this authorization cannot replace any returned old feedback")
        if seed in REEXECUTION_SEEDS:
            condition_paths = list((stage / "feedback").glob("*/intent/record.json"))
            incomplete_paths = list((stage / "feedback").glob("*/draw0/incomplete/*/record.json"))
            failed = [item for item in event_records if item[1]["kind"] == "model_call_failed"]
            require(len(condition_paths) == len(incomplete_paths) == len(intents) == len(failed) == 1,
                    "only the single old first request is authorized for reexecution")
            old_condition, condition_ref = _read(condition_paths[0])
            require(checked_condition(old_condition) == condition,
                    "new condition differs from the actual old temperature/point/config/roster")
            incomplete, incomplete_ref = _read(incomplete_paths[0])
            event_path, failure_event, event_ref = failed[0]
            settlement = failure_event["payload"]["settlement"]
            evidence = settlement["evidence"]
            request = evidence["public_request"]
            episode_path = event_path.parent.parent.parent.parent / "episodes" / incomplete["episode_key"] / "episode.json"
            episode, episode_ref = _read(episode_path)
            first = condition["ordered_episode_roster"][0]
            require(incomplete["all_provider_calls_settled"] is False
                    and incomplete["automatic_retry_allowed"] is False
                    and incomplete["stop_reason"] == episode["stop_reason"] == "provider_error"
                    and len(episode["call_settlements"]) == 1 and not episode["turns"]
                    and episode["actual_model_calls"] == 1
                    and settlement["state"] == "unknown" and settlement["actual_model_calls"] == 1
                    and settlement["attempt_index"] == failure_event["step"] == 0
                    and evidence["token_receipt_available"] is False,
                    "registered old call is not the single unreturned step0 request")
            require(incomplete["episode_key"] == first["episode_key"]
                    and episode["task_id"] == first["task_id"]
                    and episode["config"] == request["config"] == condition["configs"][0]
                    and episode["provider"] == condition["identity"]
                    and request["config"]["seed"] == 11
                    and digest(request) == evidence["request_sha256"],
                    "old unknown scientific request or original first task binding differs")
            base.update(authorized_reexecution_count=1, original_unknown_model_calls=1,
                        old_condition=condition_ref, old_incomplete=incomplete_ref,
                        old_failure_event=event_ref, old_episode=episode_ref,
                        original_task_id=first["task_id"], original_episode_key=first["episode_key"],
                        draw_index=0, draw_seed=11, turn_index=0,
                        scientific_request=copy.deepcopy(request), scientific_request_sha256=digest(request))
        else:
            require(not intents and not events
                    and failure["exception_type"] == "ExplicitStop"
                    and failure["error"] == "explicit stop during pre-scientific resource wait",
                    "seed251 must have no prior C05 model invocation")
            base.update(authorized_reexecution_count=0, original_unknown_model_calls=0,
                        old_condition=None, old_incomplete=None, old_failure_event=None,
                        old_episode=None, scientific_request=None, scientific_request_sha256=None,
                        first_execution_only=True)
        rows[str(seed)] = base
    return checked_authorization(_bound(dict(
        schema=AUTHORIZATION_SCHEMA, old_root=str(old_root),
        recovery_root=str(old_root / "recovery_01"), old_protocol=protocol_ref,
        old_closeout=closeout_ref, seeds=rows, total_authorized_reexecutions=2,
        scientific_request_equality="complete provider public_request plus actual point/condition; old ephemeral invocation UUIDs excluded",
        condition_scientific_identity_unchanged=True,
        claim_before_model_generate=True, atomic_claim_noreplace=True,
        successful_receipt_resolution_is_separate=True, old_unknown_records_written=False,
        failure_or_new_unknown_stops_without_retry=True, claim_reset_allowed=False,
        remaining_feedback_is_first_execution_only=True,
        new_logical_feedback_budget=2100, original_test_or_feedback_budgets_expanded=False,
    )))


def checked_authorization(value):
    from finqa_v54_temperature import checked_condition

    require(value.get("id") == digest({k: v for k, v in value.items() if k != "id"})
            and value["schema"] == AUTHORIZATION_SCHEMA,
            "explicit feedback recovery authorization changed")
    require(set(value["seeds"]) == {str(seed) for seed in SEEDS}
            and value["total_authorized_reexecutions"] == 2
            and value["new_logical_feedback_budget"] == 2100
            and value["claim_reset_allowed"] is False
            and value["old_unknown_records_written"] is False
            and value["failure_or_new_unknown_stops_without_retry"] is True
            and Path(value["recovery_root"]).resolve() == Path(value["old_root"]).resolve() / "recovery_01",
            "only one independent recovery and the two specific requests are authorized")
    for seed in SEEDS:
        row = value["seeds"][str(seed)]
        condition = checked_condition(row["condition"])
        require(row["seed"] == seed
                and row["authorized_reexecution_count"] == int(seed in REEXECUTION_SEEDS)
                and row["original_unknown_model_calls"] == int(seed in REEXECUTION_SEEDS)
                and row["original_successful_model_returns"] == 0
                and condition["id"] == row["expected_condition_id"]
                and condition["identity"]["point_id"] == row["point_id"]
                and condition["identity"]["parameter_digest"] == row["parameter_digest"]
                and condition["temperature"] == 0.5 and condition["denominator"] == 700
                and not condition["cpu_test_only"],
                "recovery seed/condition/point/dose differs")
        if seed in REEXECUTION_SEEDS:
            first = condition["ordered_episode_roster"][0]
            require((row["draw_index"], row["draw_seed"], row["turn_index"]) == (0, 11, 0)
                    and row["original_task_id"] == first["task_id"]
                    and row["original_episode_key"] == first["episode_key"]
                    and digest(row["scientific_request"]) == row["scientific_request_sha256"]
                    and row["scientific_request"]["config"] == condition["configs"][0]
                    and len(row["scientific_request"]["messages"]) == 2,
                    "only the registered original draw0 seed11 first invocation may repeat")
        else:
            require(row["scientific_request"] is row["scientific_request_sha256"] is None
                    and row["first_execution_only"] is True, "seed251 has no reexecution quota")
    return value


class RecoveryGuard:
    def __init__(self, root, seed, condition, authorization, protocol_id):
        self.authorization = copy.deepcopy(checked_authorization(authorization))
        self.root = Path(root).resolve()
        require(str(self.root) == authorization["recovery_root"] and seed in SEEDS,
                "feedback recovery guard belongs to another authorized root")
        self.seed, self.row, self.protocol_id = seed, self.authorization["seeds"][str(seed)], protocol_id
        require(condition == self.row["condition"],
                "same scientific condition required despite new protocol/parent audit identities")
        self.condition = copy.deepcopy(condition)
        self.directory = self.root / f"feedback_recovery/seed{seed}"
        self.pending = None
        self.resolved_this_process = False
        for key in ("old_parent", "old_worker_failure", "old_actual_exit", "old_T1_intent"):
            _read_ref(self.row[key])
        for ref in self.row["old_T1_draw_runs"]:
            _read_ref(ref)
        if self.row["authorized_reexecution_count"]:
            for key in ("old_condition", "old_incomplete", "old_failure_event", "old_episode"):
                _read_ref(self.row[key])
        self.roster = {(row["dataset"], row["task_id"], row["seed"])
                       for row in condition["ordered_episode_roster"]}

    def before_generate(self, request, request_sha256):
        """Called after native request construction, before generate call/count."""
        require(digest(request) == request_sha256
                and request["config"] in self.condition["configs"],
                "scientific request/config changed before generation")
        user = next((message for message in request["messages"] if message["role"] == "user"), None)
        require(user is not None and isinstance(user.get("content"), str),
                "original structured public task required")
        task = json.loads(user["content"])
        require((task["dataset"], task["task_id"], request["config"]["seed"]) in self.roster,
                "request left the registered original task/draw roster")
        require(self.pending is None, "unresolved claimed request cannot be followed by another call")
        if not self.row["authorized_reexecution_count"]:
            require(not (self.directory / "claim").exists(), "seed251 cannot consume old-request quota")
            return
        matches_old = request_sha256 == self.row["scientific_request_sha256"]
        if self.resolved_this_process and not matches_old:
            return
        require(matches_old and request == self.row["scientific_request"],
                "first recovered request must equal the exact old scientific request")
        # No exists()/write race and no idempotent existing-record acceptance.
        # Even a crash after this claim but before generate consumes the slot.
        self.pending = _atomic_record(self.directory / "claim", dict(
            schema="v55_actual_single_request_reexecution_claim.v1",
            protocol_id=self.protocol_id, authorization_id=self.authorization["id"],
            seed=self.seed, condition_id=self.condition["id"], point_id=self.row["point_id"],
            parameter_digest=self.row["parameter_digest"],
            original_episode_key=self.row["original_episode_key"],
            original_task_id=self.row["original_task_id"], draw_seed=11, turn_index=0,
            scientific_request_sha256=request_sha256,
            old_incomplete=self.row["old_incomplete"], old_failure_event=self.row["old_failure_event"],
            authorized_reexecution_ordinal=1, claim_consumed_before_generate=True,
            pid=os.getpid(), claimed_epoch=time.time(), automatic_retry=False,
            claim_reset_allowed=False, old_record_written=False,
        ))

    def returned(self, turn):
        """Persist the actual returned receipt; do not settle the old event in place."""
        if self.pending is None:
            return
        receipt = turn.receipt
        require(receipt is not None and receipt.identity.model_dump(mode="json") == self.condition["identity"]
                and receipt.request_sha256 == self.pending["scientific_request_sha256"]
                and digest(turn.provider_metadata["request"]) == receipt.request_sha256
                and receipt.sampling["feedback_condition_id"] == self.condition["id"]
                and receipt.sampling["probability_contract_id"] == self.condition["probability_contract_id"]
                and receipt.sampling["temperature"] == 0.5
                and receipt.sampling["actual_model_generate_calls"] == 1
                and receipt.raw_generated_token_ids and receipt.sampled_token_logprobs is not None
                and len(receipt.raw_generated_token_ids) == len(receipt.sampled_token_logprobs)
                and all(math.isfinite(v) and v <= 1e-6 for v in receipt.sampled_token_logprobs)
                and hashlib.sha256(turn.raw_text.encode()).hexdigest() == receipt.raw_response_sha256,
                "a complete actual same-request temperature receipt is required to resolve the claim")
        _atomic_record(self.directory / "resolution", dict(
            schema="v55_authorized_reexecution_actual_return.v1", protocol_id=self.protocol_id,
            authorization_id=self.authorization["id"], seed=self.seed,
            condition_id=self.condition["id"], claim_id=self.pending["id"],
            claim=_read(self.directory / "claim/record.json")[1],
            old_incomplete=self.row["old_incomplete"], old_failure_event=self.row["old_failure_event"],
            scientific_request_sha256=receipt.request_sha256, receipt_sha256=digest(receipt),
            actual_returned_turn=turn.model_dump(mode="json"), new_actual_model_calls=1,
            old_unknown_record_preserved=True, old_unknown_reclassified=False,
            whole_episode_complete_claimed=False, claim_reset=False,
        ))
        self.pending = None
        self.resolved_this_process = True


def registered_guard(root, seed, condition):
    root = Path(root).resolve()
    protocol, _reference = _read(root / "protocol/record.json")
    require(protocol.get("id") == digest({k: v for k, v in protocol.items() if k != "id"})
            and protocol["output_root"] == str(root), "recovery protocol binding changed")
    return RecoveryGuard(root, seed, condition, protocol["feedback_recovery"], protocol["id"])
