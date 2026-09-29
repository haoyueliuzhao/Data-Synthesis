"""Real V10 material binding: full new roster, paid A/B, one map and A-only mask.

No model/GPU training or new API calls. A hard-to-map or hard-to-encode jointly
valid original blocks material admission; it is never removed to obtain ready.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from collections import Counter
from fractions import Fraction
from pathlib import Path

from .calibration import publish
from .contracts import Episode, digest, invocation_identity
from .probe_budget import _acknowledged_unknowns, _request_record_digest
from .providers import tokenizer_binding
from .qwen_protocol import strict_json_decoder
from .storage import read_json, snapshot_manifest
from .v6_collection import STUDY, bound, persist, require
from .v7_base_evaluation import ORIGIN, load_tokenizer
from .v8_training_driver import VerifiedPool
from .v9_conditional_training import execution_plan
from .v10_budget import generation_episode_id, map_episode_id
from .v10_process_review import validate_manifest
from .v10_review_protocol import (
    checked_request,
    prepare_review_request,
    resolve_joint_review,
    review_policy_definition,
    validate_mapping_record,
    validate_review_record,
)
from .v10_review_provider import request_body
from .v10_student_encoding import encode_process_review_for_student

OUTPUT = STUDY / "v10_new8000_01"
BINDING_SCHEMA = "v10_material_binding.v1"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def checked(value, schema=None):
    require(
        isinstance(value, dict)
        and value.get("id") == digest({k: v for k, v in value.items() if k != "id"})
        and (schema is None or value.get("schema") == schema),
        "material artifact identity/schema changed",
    )
    return value


def entry(path):
    path = Path(path).resolve()
    value = read_json(path)
    return dict(path=str(path), sha256=sha(path), id=value.get("id", value.get("encoding_id")))


class Reader:
    def __init__(self):
        self.cache = {}

    def read(self, item, expected_path=None):
        path = Path(item["path"]).resolve()
        require(
            expected_path is None or path == Path(expected_path).resolve(),
            "artifact redirected outside registered coordinate",
        )
        if path not in self.cache:
            raw = path.read_bytes()
            self.cache[path] = hashlib.sha256(raw).hexdigest(), json.loads(raw)
        file_hash, value = self.cache[path]
        require(
            file_hash == item["sha256"]
            and item.get("id") == value.get("id", value.get("encoding_id")),
            "bound artifact bytes/content identity changed",
        )
        return value


def _roster(plan):
    from .v8_representation import validate_material_registration

    checked(plan, "v10_new8000_generation_protocol.v1")
    original = plan["original"]
    validate_material_registration(original)
    require(
        plan["policy"] == review_policy_definition()
        and plan["review_policy_id"] == review_policy_definition()["id"]
        and plan["api_model"] == "deepseek-flash"
        and plan["task_ids"] == original["task_ids"]
        and plan["configs_by_task"] == original["configs_by_task"]
        and plan["snapshot_id"] == original["snapshot_id"],
        "new material must retain original public contract, not old material",
    )
    tasks, slots = plan["task_ids"], plan["slots"]
    require(
        len(tasks) == len(set(tasks)) == 1000
        and len(slots) == 8000
        and len({s["slot_id"] for s in slots}) == 8000
        and Counter(s["task_id"] for s in slots) == Counter({t: 8 for t in tasks}),
        "complete original1000/new8000 roster required",
    )
    for slot in slots:
        require(
            slot["purpose"] == "common_material_candidate"
            and slot["slot_id"]
            == generation_episode_id(plan["batch_id"], slot["task_id"], slot["slot_index"]),
            "new independent slot identity changed",
        )
    return tasks, slots


def _terminal_coordinate(row):
    return row["slot_id"], row["role"]


def _same_request_contract(saved, expected):
    """Equivalent reconstruction without rewriting the original sent strings."""
    checked_request(saved)

    def normalize(value):
        value = dict(value)
        value.pop("id", None)
        value["messages"] = [
            {**message, "content": strict_json_decoder().decode(message["content"])}
            if message["role"] == "user"
            else dict(message)
            for message in value["messages"]
        ]
        if "candidate_request" in value:
            value["candidate_request"] = normalize(value["candidate_request"])
            # This hash binds the retained raw message spelling, which is checked
            # by checked_request. It is not a financial or source identity.
            value["candidate_request"].pop("messages_sha256", None)
        return value

    require(
        normalize(saved) == normalize(expected),
        "registered request differs from all original material/context inputs",
    )
    return saved


def validate_complete_seals(plan, generation, native, reviews, mapping):
    tasks, slots = _roster(plan)
    checked(generation, "v10_whole_generation_seal.v1")
    checked(native, "v10_new_native_support.v1")
    checked(reviews, "v10_complete_process_review_seal.v1")
    checked(mapping, "v10_complete_task_mapping_seal.v1")
    require(
        generation["protocol_id"]
        == native["protocol_id"]
        == reviews["protocol_id"]
        == mapping["protocol_id"]
        == plan["id"]
        and all(r["batch_id"] == plan["batch_id"] for r in (generation, native, reviews, mapping))
        and native["generation_seal_id"] == reviews["generation_seal_id"] == generation["id"]
        and reviews["native_support_id"] == native["id"]
        and mapping["review_seal_id"] == reviews["id"]
        and generation["denominator"] == native["slot_denominator"] == 8000
        and native["task_denominator"] == 1000
        and generation["all_slots_have_real_terminal"] is True
        and [r["slot"] for r in generation["slots"]]
        == [r["slot"] for r in native["rows"]]
        == slots,
        "new whole generation/native/production barrier changed",
    )
    for outcome, score in zip(generation["slots"], native["rows"], strict=True):
        checked(outcome, "v10_generation_slot_outcome.v1")
        require(
            score["generation_outcome_id"] == outcome["id"]
            and (type(score["Q_native"]) is bool or score["Q_native"] is None)
            and outcome["status"] in {"COMPLETE", "NETWORK_UNKNOWN_TERMINAL"},
            "native outcome/terminal changed",
        )
        if outcome["status"] == "NETWORK_UNKNOWN_TERMINAL":
            require(
                score["Q_native"] is None and outcome.get("native_zero_claimed") is False,
                "missing generation response cannot become a native zero or training original",
            )
        value = score["native"]["native"]["execution_accuracy"]
        require(
            score["Q_native"] is (None if value is None else bool(value)),
            "native eligibility differs from sealed execution result",
        )
    eligible = [r["slot"]["slot_id"] for r in native["rows"] if r["Q_native"] is True]
    expected = [(sid, role) for sid in eligible for role in ("A", "B")]
    require(
        native["M"] == reviews["M"] == len(eligible)
        and reviews["expected_reviews"] == len(expected)
        and [_terminal_coordinate(r) for r in reviews["terminals"]] == expected
        and reviews["all_registered_jobs_terminal"] is True
        and set(reviews["joint_records"]) == set(eligible)
        and mapping["all_registered_jobs_terminal"] is True,
        "all new native-correct A/B jobs must terminate; no successful prefix",
    )
    returned = sum(r["terminal_kind"] == "paid_model_return" for r in reviews["terminals"])
    unknowns = sum(
        r["terminal_kind"] == "acknowledged_connection_unknown" for r in reviews["terminals"]
    )
    require(
        returned == reviews["returned"]
        and unknowns == reviews["network_unknowns"]
        and returned + unknowns == len(expected),
        "actual response and unknown denominators must stay separate",
    )
    return tasks, slots, eligible


class LedgerReader:
    def __init__(self, plan):
        self.connection = sqlite3.connect(
            Path(plan["budget_database"]).resolve().as_uri() + "?mode=ro", uri=True
        )
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA query_only=ON")
        self.connection.execute("BEGIN")
        cfg = json.loads(
            self.connection.execute("SELECT value FROM metadata WHERE key='config'").fetchone()[0]
        )
        require(
            digest(cfg) == plan["budget_config_sha256"],
            "same original wallet configuration required",
        )
        self.run_id = cfg["run_id"]
        self.config = cfg
        self.acks = {r["invocation_id"]: r for r in _acknowledged_unknowns(self.connection, cfg)}

    def row(self, iid):
        row = self.connection.execute(
            "SELECT * FROM requests WHERE invocation_id=?", (iid,)
        ).fetchone()
        require(row is not None, "actual paid invocation absent from original wallet")
        return dict(row)

    def close(self):
        self.connection.close()


def _network_terminal(record, request, ledger, *, attempt_index=1):
    iid = record["invocation_id"]
    row, ack = ledger.row(iid), ledger.acks.get(iid)
    coords = invocation_identity(
        dict(
            run_id=ledger.run_id,
            episode_id=request["episode_id"],
            attempt_index=attempt_index,
        ),
        turn_index=0,
    )
    require(
        record["protocol_id"] == request["protocol_id"]
        and record["policy_id"] == request["policy_id"]
        and record["episode_id"] == request["episode_id"]
        and record["task_id"] == request["task_id"]
        and record["role"] == request["role"]
        and record["request_id"] == request["id"]
        and record.get("original_response") is None
        and record.get("usage") is None,
        "unknown terminal cannot relabel its original registered job or manufacture a return",
    )
    require(
        row["state"] == "UNKNOWN"
        and ack is not None
        and json.loads(row["coordinates_json"]) == coords
        and coords["invocation_id"] == iid
        and row["request_sha256"] == digest(request_body(request))
        and record.get("request_sha", record.get("request_sha256")) == row["request_sha256"]
        and record["ack_id"] == ack["id"]
        and ack["original_unknown_record_sha256"] == _request_record_digest(row)
        and record["actual_model_call_receipt_verified"] is False,
        "network terminal must retain exact acknowledged original UNKNOWN, not invented return",
    )


def _final_retry_binding(output, plan, reviews, reader, ledger):
    """Audit the sole authorized side substitution without relabeling the first UNKNOWN."""
    from .v10_final_retry import (
        EPISODE_ID,
        ORIGIN_INVOCATION_ID,
        ROLE,
        SLOT_ID,
        TASK_ID,
        read_final_retry_activation_from_connection,
        read_final_retry_permit_from_connection,
        retry_coordinates,
        supplement_directory,
    )

    permit = read_final_retry_permit_from_connection(ledger.connection, ledger.config)
    if permit is None:
        require(
            reviews.get("final_retry_resolution") is None
            and all(t.get("physical_attempt_index", 1) == 1 for t in reviews["terminals"]),
            "supplementary attempt is absent from the registered original wallet",
        )
        return None
    directory = supplement_directory(output)
    require(reviews.get("final_retry_resolution"), "authorized final result cannot be skipped")
    resolution = checked(
        reader.read(reviews["final_retry_resolution"], directory / "resolution/record.json"),
        "v10_final_retry_resolution.v1",
    )
    require(
        reader.read(resolution["authorization"], directory / "authorization/record.json") == permit,
        "supplementary authorization must match the immutable wallet permit",
    )
    activation = read_final_retry_activation_from_connection(ledger.connection, ledger.config)
    require(
        activation is not None
        and reader.read(resolution["activation"], directory / "activation/record.json")
        == activation
        and activation["permit_id"] == permit["id"]
        and activation["primary_completion"] == resolution["primary_matrix"],
        "attempt2 requires the original complete-matrix financial activation",
    )
    barrier = checked(
        reader.read(
            resolution["primary_matrix"], directory / "complete_primary_matrix/record.json"
        ),
        "v10_primary_review_matrix_complete_before_final_retry.v1",
    )
    phase = checked(reader.read(entry(Path(output) / "review_registration/record.json")))
    require(
        barrier["protocol_id"] == resolution["protocol_id"] == plan["id"]
        and barrier["phase_id"] == phase["id"]
        and resolution["batch_id"] == plan["batch_id"]
        and barrier["authorization"] == resolution["authorization"]
        and barrier["original_terminal"] == resolution["original_terminal"]
        and barrier["all_registered_jobs_terminal"] is True
        and barrier["expected_reviews"]
        == activation["expected_reviews"]
        == resolution["fixed_logical_review_denominator"]
        == reviews["expected_reviews"]
        == len(phase["jobs"])
        and [t["episode_id"] for t in barrier["terminals"]]
        == [j["episode_id"] for j in phase["jobs"]]
        == [t["episode_id"] for t in reviews["terminals"]],
        "only the full original fixed matrix may precede the authorized final attempt",
    )
    target = [t for t in reviews["terminals"] if t["episode_id"] == EPISODE_ID]
    require(
        len(target) == 1
        and target[0]["slot_id"] == resolution["slot_id"] == SLOT_ID
        and target[0]["role"] == resolution["role"] == ROLE
        and resolution["episode_id"] == EPISODE_ID
        and resolution["original_invocation_id"] == ORIGIN_INVOCATION_ID
        and resolution["supplementary_attempt_index"] == target[0]["physical_attempt_index"] == 2
        and target[0]["authorization"] == resolution["authorization"]
        and target[0]["original_terminal"] == resolution["original_terminal"]
        and target[0]["final_retry_resolution"] == reviews["final_retry_resolution"]
        and target[0]["record"] == resolution["final_terminal"]
        and resolution["only_supplementary_result_decides_final_side"] is True
        and resolution["favorable_result_selection"] is False
        and resolution["original_unknown_overwritten"] is False
        and resolution["further_retry_authorized"] is False,
        "one fixed supplementary side, not favorable selection or wider retry scope",
    )
    for old, final in zip(barrier["terminals"], reviews["terminals"], strict=True):
        old_directory = Path(output) / "reviews" / final["slot_id"].split(":", 1)[1] / final["role"]
        checked(reader.read(old["record"], old_directory / "record/record.json"))
        if old["episode_id"] == EPISODE_ID:
            require(
                old["record"] == resolution["original_terminal"]
                and old["terminal_kind"] == "acknowledged_connection_unknown",
                "original physical UNKNOWN must remain in the full-matrix barrier",
            )
        else:
            require(
                old["record"] == final["record"]
                and old["terminal_kind"] == final["terminal_kind"]
                and final.get("physical_attempt_index", 1) == 1,
                "no other original outcome may be replaced by the single final retry",
            )
    primary_directory = Path(output) / "reviews" / SLOT_ID.split(":", 1)[1] / ROLE
    original = checked(reader.read(resolution["original_terminal"]))
    request = checked(reader.read(entry(primary_directory / "request/record.json")))
    require(
        original["schema"] == "v10_network_unknown_review.v1"
        and original["invocation_id"] == ORIGIN_INVOCATION_ID
        and original["task_id"] == request["task_id"] == TASK_ID,
        "supplementary original is not the authorized retained UNKNOWN",
    )
    _network_terminal(original, request, ledger)
    require(
        reader.read(entry(directory / "request/record.json")) == request,
        "final attempt must preserve the original request object and HTTP message spelling",
    )
    coordinates = retry_coordinates(ledger.run_id)
    row = ledger.row(resolution["supplementary_invocation_id"])
    original_row = ledger.row(ORIGIN_INVOCATION_ID)
    evidence = json.loads(row["evidence_json"] or "{}")
    final_record = checked(
        reader.read(resolution["final_terminal"], directory / "record/record.json")
    )
    final_iid = (
        final_record["artifact"]["budget_invocation_id"]
        if final_record.get("actual_model_call_receipt_verified") is True
        else final_record["invocation_id"]
    )
    require(
        coordinates["invocation_id"] == resolution["supplementary_invocation_id"] == final_iid
        and json.loads(row["coordinates_json"]) == coordinates
        and row["request_body"] == original_row["request_body"]
        and row["request_sha256"] == original_row["request_sha256"]
        and row["state"] in {"SETTLED", "UNKNOWN"}
        and evidence.get("final_retry_permit") == permit
        and evidence.get("final_retry_activation") == activation
        and resolution["original_unknown_permanent_reserved_microcny"]
        == reviews["retained_original_unknown_reserved_microcny"]
        == original["permanent_reserved_microcny"]
        == original_row["reserved_microcny"]
        and reviews["physical_attempts"]
        == resolution["physical_attempts"]
        == reviews["expected_reviews"] + 1
        and reviews["supplementary_attempts"] == reviews["retained_original_unknown_attempts"] == 1,
        "logical denominator, real attempt2 and the original permanent hold must stay distinct",
    )
    return resolution


def _network_retry_binding(output, plan, reviews, reader, ledger):
    """Bind the all-and-only frozen original network group and every unique attempt2."""
    from .v10_network_retry import (
        read_network_retry_activation_from_connection,
        read_network_retry_permit_from_connection,
        supplement_directory,
    )

    permit = read_network_retry_permit_from_connection(ledger.connection, ledger.config)
    if permit is None:
        require(reviews.get("network_retry_resolution") is None, "unregistered group supplement")
        return None
    directory = supplement_directory(output)
    require(
        reviews.get("network_retry_resolution") is not None
        and reviews.get("final_retry_resolution") is None,
        "registered group supersedes the single future attempt and cannot be skipped",
    )
    resolution = checked(
        reader.read(reviews["network_retry_resolution"], directory / "resolution/record.json"),
        "v10_network_retry_resolution.v1",
    )
    activation = read_network_retry_activation_from_connection(ledger.connection, ledger.config)
    require(
        activation is not None
        and reader.read(resolution["authorization"], directory / "authorization/record.json")
        == permit
        and reader.read(resolution["activation"], directory / "activation/record.json")
        == activation
        and activation["permit_id"] == permit["id"]
        and activation["primary_completion"] == resolution["primary_matrix"]
        and resolution["superseded_single_permit_id"] == activation["superseded_single_permit_id"],
        "group authority/activation must match the same immutable wallet records",
    )
    barrier = checked(
        reader.read(
            resolution["primary_matrix"], directory / "complete_primary_matrix/record.json"
        ),
        "v10_primary_review_matrix_complete_before_network_retry.v1",
    )
    phase = checked(
        reader.read(
            activation["primary_registration"], Path(output) / "review_registration/record.json"
        )
    )
    require(
        barrier["protocol_id"] == resolution["protocol_id"] == phase["protocol_id"] == plan["id"]
        and barrier["phase_id"] == phase["id"]
        and resolution["batch_id"] == plan["batch_id"]
        and barrier["authorization"] == resolution["authorization"]
        and barrier["all_registered_jobs_terminal"] is True
        and activation["all_primary_attempt1_terminal"] is True
        and barrier["expected_reviews"]
        == activation["expected_reviews"]
        == resolution["fixed_logical_review_denominator"]
        == reviews["expected_reviews"]
        == len(phase["jobs"])
        and [t["episode_id"] for t in barrier["terminals"]]
        == [j["episode_id"] for j in phase["jobs"]]
        == [t["episode_id"] for t in reviews["terminals"]],
        "one complete original matrix must precede the once-frozen supplementary manifest",
    )
    targets = {t["episode_id"]: t for t in activation["targets"]}
    replacements = {r["episode_id"]: r for r in resolution["replacements"]}
    require(
        list(targets)
        == list(replacements)
        == [j["episode_id"] for j in activation["jobs"]]
        == [
            t["episode_id"]
            for t in barrier["terminals"]
            if t["terminal_kind"] == "acknowledged_connection_unknown"
        ]
        and len(targets)
        == len(activation["targets"])
        == len(resolution["replacements"])
        == activation["target_count"]
        == resolution["supplementary_attempts"]
        and resolution["only_supplementary_result_decides_final_sides"] is True
        and resolution["favorable_result_selection"] is False
        and resolution["original_unknowns_overwritten"] is False
        and resolution["attempt3_authorized"] is False,
        "no primary network item may be omitted, duplicated, selected by outcome, "
        "or retried a third time",
    )
    original_hold, retry_unknown_hold, retry_returns, primary_returns = 0, 0, 0, 0
    for old, final in zip(barrier["terminals"], reviews["terminals"], strict=True):
        eid = final["episode_id"]
        primary_dir = Path(output) / "reviews" / final["slot_id"].split(":", 1)[1] / final["role"]
        original = checked(reader.read(old["record"], primary_dir / "record/record.json"))
        if eid not in targets:
            require(
                old["record"] == final["record"]
                and old["terminal_kind"] == final["terminal_kind"] == "paid_model_return"
                and final.get("physical_attempt_index", 1) == 1,
                "a returned primary, mapping, or non-target cannot be replaced by network recovery",
            )
            primary_returns += 1
            continue
        target, replacement = targets[eid], replacements[eid]
        slot_dir = directory / "slots" / eid.split(":", 1)[1]
        request = checked(reader.read(entry(primary_dir / "request/record.json")))
        require(
            all(target[k] == request[k] for k in ("episode_id", "slot_id", "task_id", "role"))
            and original["schema"] == "v10_network_unknown_review.v1"
            and original["invocation_id"]
            == replacement["origin_invocation_id"]
            == target["origin_invocation_id"]
            and replacement["slot_id"] == final["slot_id"] == target["slot_id"]
            and replacement["role"] == final["role"] == target["role"]
            and old["record"] == replacement["original_terminal"] == final["original_terminal"]
            and final["record"] == replacement["final_terminal"]
            and final["physical_attempt_index"] == 2
            and final["authorization"] == resolution["authorization"]
            and final["network_retry_resolution"] == reviews["network_retry_resolution"]
            and reader.read(entry(slot_dir / "request/record.json")) == request,
            "every replacement must retain the same original request and actual primary UNKNOWN",
        )
        _network_terminal(original, request, ledger)
        row = ledger.row(target["retry_invocation_id"])
        origin = ledger.row(target["origin_invocation_id"])
        coordinates = invocation_identity(
            dict(run_id=ledger.run_id, episode_id=eid, attempt_index=2), turn_index=0
        )
        evidence = json.loads(row["evidence_json"] or "{}")
        record = checked(reader.read(final["record"], slot_dir / "record/record.json"))
        returned = record.get("actual_model_call_receipt_verified") is True
        iid = record["artifact"]["budget_invocation_id"] if returned else record["invocation_id"]
        require(
            coordinates["invocation_id"]
            == iid
            == replacement["retry_invocation_id"]
            == target["retry_invocation_id"]
            and json.loads(row["coordinates_json"]) == coordinates
            and row["state"] == ("SETTLED" if returned else "UNKNOWN")
            and row["request_body"] == origin["request_body"]
            and row["request_sha256"]
            == origin["request_sha256"]
            == target["original_request_sha256"]
            and evidence.get("network_retry_permit") == permit
            and evidence.get("network_retry_activation") == activation
            and evidence.get("network_retry_target") == target
            and replacement["original_reserved_microcny"]
            == target["origin_reserved_microcny"]
            == original["permanent_reserved_microcny"]
            == origin["reserved_microcny"],
            "real unique attempt2, exact HTTP bytes, wallet group witnesses "
            "and original hold required",
        )
        original_hold += origin["reserved_microcny"]
        retry_returns += int(returned)
        if not returned:
            _network_terminal(record, request, ledger, attempt_index=2)
            retry_unknown_hold += row["reserved_microcny"]
    statistics = dict(
        primary_first_pass_returns=primary_returns,
        primary_first_pass_network_unknowns=len(targets),
        retry_returns=retry_returns,
        retry_network_unknowns=len(targets) - retry_returns,
        physical_attempts=reviews["expected_reviews"] + len(targets),
        supplementary_attempts=len(targets),
        retained_original_unknown_reserved_microcny=original_hold,
        retry_unknown_reserved_microcny=retry_unknown_hold,
    )
    require(
        all(resolution[k] == reviews[k] == value for k, value in statistics.items())
        and reviews["retained_original_unknown_attempts"] == len(targets)
        and reviews["returned"] == primary_returns + retry_returns
        and reviews["network_unknowns"] == len(targets) - retry_returns,
        "first-pass/retry responses, logical denominator "
        "and physical retained holds must be separate",
    )
    return replacements


def _episode(outcome, plan, reader):
    path = Path(outcome["episode_path"])
    raw = path.read_bytes()
    require(
        hashlib.sha256(raw).hexdigest() == outcome["episode_file_sha256"],
        "original Episode bytes changed",
    )
    episode = Episode.model_validate_json(raw)
    require(
        digest(episode) == outcome["episode_sha256"]
        and episode.task_id == outcome["slot"]["task_id"]
        and episode.config.model_dump(mode="json") == plan["configs_by_task"][episode.task_id],
        "new original Episode/configuration changed",
    )
    integrity = checked(
        reader.read(entry(outcome["integrity_path"])), "v10_generated_record_integrity.v1"
    )
    require(
        integrity["id"] == outcome["integrity_id"]
        and integrity["episode_sha256"] == digest(episode)
        and integrity["slot_id"] == outcome["slot"]["slot_id"],
        "original mechanical evidence differs",
    )
    return episode, integrity


def _validate_encoding(encoding, episode, mask, tokenizer):
    require(
        encoding.get("schema") == "v10_student_encoding.v1"
        and encoding.get("encoding_id")
        == "v10_student_encoding:"
        + digest({k: v for k, v in encoding.items() if k != "encoding_id"}),
        "not an authentic V10 encoding identity",
    )
    validate_manifest(episode, mask)
    require(
        encode_process_review_for_student(episode, mask, tokenizer) == encoding,
        "actual Student tokens/masks must reproduce from unique A authority and full original",
    )


def support_profile(
    task_order, joint_by_task, maps, encodings, source_groups=None, reason_coverage=None
):
    """Pure whole-kernel profile; no minimum-N or quality/length selection rule."""
    support, layers = {}, Counter(reason=0, tool=0, final=0)
    all_joint = [sid for task in task_order for sid in joint_by_task.get(task, [])]
    blockers = []
    for task in task_order:
        sids = joint_by_task.get(task, [])
        if not sids:
            continue
        mapping = maps[task]
        if mapping.get("mapping_status") != "complete":
            blockers.append(
                dict(task_id=task, reason="joint_originals_mapping_unresolved", slot_ids=sids)
            )
            continue
        counts, chi = Counter(), {}
        require(
            set(mapping["state_by_slot"]) == set(sids),
            "all jointly valid originals must map exactly once",
        )
        for sid in sids:
            state = mapping["state_by_slot"][sid]
            bit = mapping["chi_by_state"][state]
            require(type(bit) is int and bit in (0, 1), "state chi must be actual mapped binary")
            chi[state], counts[state] = bit, counts[state] + 1
        support[task] = dict(joint_valid_slot_ids=sids, states=dict(counts), chi=chi, n_x=len(sids))
    for sid in all_joint:
        encoding = encodings.get(sid)
        if encoding is None or not encoding.get("encoding_admitted"):
            blockers.append(
                dict(
                    slot_id=sid,
                    reason="joint_original_encoding_unresolved",
                    failures=None if encoding is None else encoding["failures"],
                )
            )
        if encoding:
            layers.update(encoding["layer_target_counts"])
    require(
        set(encodings) == set(all_joint), "all and only jointly valid originals require encoding"
    )
    if (
        all_joint
        and layers["reason"] == 0
        and any(e["public_content_present"] for e in encodings.values())
    ):
        blockers.append(
            dict(
                reason="all_public_reasoning_masked_supervision_projection",
                interpretation=(
                    "tool-only targets cannot be reported as full public-reasoning training"
                ),
            )
        )
    N = sum(bool(joint_by_task.get(t)) for t in task_order)
    mapped = len(support)
    degrees = sum(len(s["states"]) - 1 for s in support.values()) if mapped == N else None
    flexible = sum(len(s["states"]) > 1 for s in support.values()) if mapped == N else None
    mixed = sum(len(set(s["chi"].values())) > 1 for s in support.values()) if mapped == N else None
    complete = not blockers and N > 0
    distinct = complete and degrees > 0 and mixed > 0
    counts = [n for s in support.values() for n in s["states"].values()]
    dose = None
    if mapped == N and N:
        from .v9_material_diagnostics import manual_dose

        dose = manual_dose(
            {
                t: {z: str(Fraction(n, row["n_x"])) for z, n in row["states"].items()}
                for t, row in support.items()
            },
            {t: row["chi"] for t, row in support.items()},
            {t: str(Fraction(1, N)) for t in support},
        )
    profile = bound(
        dict(
            schema="v10_conditional_capability_profile.v1",
            N=N,
            package_count=len(all_joint),
            state_count=len(counts) if mapped == N else None,
            D_pi=degrees,
            multi_state_tasks=flexible,
            M_flex=str(Fraction(flexible, N)) if mapped == N and N else "0",
            chi_flexible_tasks=mixed,
            chi_flexible_mass=str(Fraction(mixed, N)) if mapped == N and N else "0",
            one_state_tasks=N - flexible if flexible is not None else None,
            singleton_package_tasks=sum(len(joint_by_task[t]) == 1 for t in joint_by_task),
            state_package_histogram=dict(sorted(Counter(str(n) for n in counts).items())),
            supervised_tokens=dict(layers),
            supervised_token_layers={"reason": "R+U", "tool": "A", "final": "F"},
            separate_R_U_token_counts_available=False,
            package_reason_coverage=reason_coverage or {},
            raw_public_content_characters=sum(
                r["raw_characters"] for r in (reason_coverage or {}).values()
            ),
            approved_public_content_characters=sum(
                r["approved_characters"] for r in (reason_coverage or {}).values()
            ),
            reason_coverage_is_not_substantive_reasoning_quality=True,
            public_content_all_masked_packages=[
                sid
                for sid, e in encodings.items()
                if e["public_content_without_positive_reason_targets"]
            ],
            maximum_sequence_tokens=max(
                (e["max_sequence_tokens"] for e in encodings.values()), default=0
            ),
            total_sequence_tokens=sum(e["total_sequence_tokens"] for e in encodings.values()),
            source_groups=dict(
                Counter((source_groups or {}).get(t, "not_reported") for t in joint_by_task)
            ),
            material_complete=complete,
            manual_intervention_dose=dose,
            blockers=blockers,
            nontrivial_pi=degrees is not None and degrees > 0,
            nontrivial_manual=mixed is not None and mixed > 0,
            five_arm_algebraic_distinguishability_possible=distinct,
            power_established=False,
            student_results_used=False,
            no_arbitrary_minimum_N=True,
        )
    )
    return bound(
        dict(
            schema="v10_conditional_support_manifest.v1",
            original_task_ids=task_order,
            original_task_denominator=1000,
            original_slot_denominator=8000,
            training_task_ids=[t for t in task_order if joint_by_task.get(t)],
            N=N,
            mu={t: str(Fraction(1, N)) for t in task_order if joint_by_task.get(t)},
            joint_valid_slot_ids=all_joint,
            task_support=support,
            capability_profile=profile,
            material_complete=complete,
            exploratory_training_admitted=distinct,
            execution_plan=execution_plan(N) if N else None,
            original1000_protocol_admitted=False,
            all_originals_retained=True,
            no_valid_package_or_task_dropped=True,
            semantic_truth_proved=False,
        )
    )


def _collect(output, plan, reader, *, produce_encodings):
    output = Path(output).resolve()
    generation = reader.read(entry(output / "generation_seal/record.json"))
    native = reader.read(entry(output / "native_support/record.json"))
    reviews = reader.read(entry(output / "review_seal/record.json"))
    mapping_seal = reader.read(entry(output / "mapping_seal/record.json"))
    tasks, slots, eligible = validate_complete_seals(
        plan, generation, native, reviews, mapping_seal
    )
    outcomes = {r["slot"]["slot_id"]: r for r in generation["slots"]}
    native_rows = {r["slot"]["slot_id"]: r for r in native["rows"]}
    originals, integrity, sides = {}, {}, {}
    ledger = LedgerReader(plan)
    try:
        network_retries = _network_retry_binding(output, plan, reviews, reader, ledger)
        final_retry = (
            _final_retry_binding(output, plan, reviews, reader, ledger)
            if network_retries is None
            else None
        )
        for outcome in generation["slots"]:
            if outcome["status"] != "NETWORK_UNKNOWN_TERMINAL":
                continue
            unknown_ids = outcome["unknown_invocation_ids"]
            require(
                unknown_ids and len(unknown_ids) == len(set(unknown_ids)),
                "generation unknown terminal needs its real original invocation",
            )
            expected_acks, hold = [], 0
            for iid in unknown_ids:
                row, ack = ledger.row(iid), ledger.acks.get(iid)
                coords = json.loads(row["coordinates_json"])
                require(
                    row["state"] == "UNKNOWN"
                    and ack is not None
                    and coords["run_id"] == ledger.run_id
                    and coords["episode_id"] == outcome["slot"]["slot_id"]
                    and coords["attempt_index"] == 1
                    and 0 <= coords["turn_index"] < 32
                    and invocation_identity(coords, turn_index=coords["turn_index"]) == coords,
                    "whole generation terminal lacks acknowledged same-slot evidence",
                )
                expected_acks.append(ack["id"])
                hold += row["reserved_microcny"]
            require(
                outcome["acknowledgment_ids"] == expected_acks
                and outcome["permanent_reserved_microcny"] == hold,
                "generation UNKNOWN receipts/holds changed",
            )
        for terminal in reviews["terminals"]:
            sid, role = _terminal_coordinate(terminal)
            if sid not in originals:
                originals[sid], integrity[sid] = _episode(outcomes[sid], plan, reader)
            request = prepare_review_request(
                originals[sid],
                slot_id=sid,
                role=role,
                native_result=native_rows[sid]["native"],
                integrity=integrity[sid]["checks"],
                protocol_id=plan["batch_id"],
            )
            require(
                terminal["episode_id"] == request["episode_id"],
                "review terminal coordinate changed",
            )
            directory = output / "reviews" / sid.split(":", 1)[1] / role
            saved_request = checked(reader.read(entry(directory / "request/record.json")))
            request = _same_request_contract(saved_request, request)
            retried = (
                terminal["episode_id"] in (network_retries or {})
                or final_retry is not None
                and terminal["episode_id"] == final_retry["episode_id"]
            )
            record_path = (
                output
                / "network_retry_01/slots"
                / terminal["episode_id"].split(":", 1)[1]
                / "record/record.json"
                if terminal["episode_id"] in (network_retries or {})
                else output / "final_retry_01/record/record.json"
                if retried
                else directory / "record/record.json"
            )
            record = checked(reader.read(terminal["record"], record_path))
            if terminal["terminal_kind"] == "paid_model_return":
                require(record["request"] == request, "paid record request changed")
                validate_review_record(
                    record, ledger.row(record["artifact"]["budget_invocation_id"])
                )
            else:
                require(
                    record["schema"] == "v10_network_unknown_review.v1"
                    and record["review_status"] == "network_unknown"
                    and record["process_validity"] == "unknown",
                    "unknown connection is not a process verdict",
                )
                _network_terminal(record, request, ledger, attempt_index=2 if retried else 1)
            sides[sid, role] = record
        joints, joint_by_task = {}, {}
        for sid in eligible:
            a, b = sides[sid, "A"], sides[sid, "B"]
            joint = checked(
                reader.read(
                    reviews["joint_records"][sid],
                    output / "joint" / sid.split(":", 1)[1] / "record.json",
                )
            )
            if a["schema"] == b["schema"] == "v10_paid_process_review.v1":
                require(
                    joint == resolve_joint_review(a, b, q_native=True),
                    "joint qualification differs from complete actual A/B",
                )
            else:
                require(
                    joint["schema"] == "v10_joint_process_unknown.v1"
                    and joint["joint_valid"] is False
                    and joint["q_native"] is True
                    and joint["A_record_id"] == a["id"]
                    and joint["B_record_id"] == b["id"],
                    "unknown return cannot become positive by a status flag",
                )
            joints[sid] = joint
            if joint["joint_valid"]:
                joint_by_task.setdefault(outcomes[sid]["slot"]["task_id"], []).append(sid)
        joint_ids = [
            s["slot_id"]
            for s in slots
            if s["slot_id"] in joints and joints[s["slot_id"]]["joint_valid"]
        ]
        require(
            reviews["joint_slot_ids"] == joint_ids
            and reviews["joint_by_task"] == joint_by_task
            and reviews["N"] == mapping_seal["expected_tasks"] == len(joint_by_task)
            and [r["task_id"] for r in mapping_seal["terminals"]]
            == [t for t in tasks if t in joint_by_task],
            "whole material support/mapping roster cannot select a favorable subset",
        )
        maps = {}
        from .v10_review_protocol import prepare_mapping_request

        for terminal in mapping_seal["terminals"]:
            task = terminal["task_id"]
            request = prepare_mapping_request(
                task_id=task,
                joint_records=[joints[s] for s in joint_by_task[task]],
                protocol_id=plan["batch_id"],
            )
            directory = output / "mapping" / digest(task)
            request = _same_request_contract(
                checked(reader.read(entry(directory / "request/record.json"))), request
            )
            require(
                terminal["episode_id"] == map_episode_id(plan["batch_id"], task),
                "mapping must use every jointly valid original",
            )
            record = checked(reader.read(terminal["record"], directory / "record/record.json"))
            if terminal["terminal_kind"] == "paid_model_return":
                require(record["request"] == request, "paid mapping request changed")
                validate_mapping_record(
                    record, ledger.row(record["artifact"]["budget_invocation_id"])
                )
            else:
                require(
                    terminal["terminal_kind"] == "acknowledged_connection_unknown"
                    and record["schema"] == "v10_network_unknown_mapping.v1"
                    and record["mapping_status"] == "unknown",
                    "unreturned mapping cannot be approved",
                )
                _network_terminal(record, request, ledger)
            maps[task] = record
        require(
            mapping_seal["all_joint_states_resolved"]
            is all(m["mapping_status"] == "complete" for m in maps.values()),
            "mapping readiness flag cannot override actual whole-task mapping",
        )
    finally:
        ledger.close()
    assets_source = checked(read_json(ORIGIN))
    require(
        assets_source["id"] == plan["original"]["prior_original_protocol_id"],
        "fixed Student/role assets source differs",
    )
    tokenizer = load_tokenizer(assets_source["assets"])
    encodings, encoding_entries = {}, {}
    for sid in joint_ids:
        path = output / "encoding" / sid.split(":", 1)[1] / "record.json"
        mask, episode = joints[sid]["A_manifest"], originals[sid]
        if not path.exists():
            require(produce_encodings, "joint original lacks frozen encoding; never drop it")
            encoding = encode_process_review_for_student(episode, mask, tokenizer)
            publish(path.parent, encoding)
        else:
            encoding = read_json(path)
            _validate_encoding(encoding, episode, mask, tokenizer)
        encodings[sid], encoding_entries[sid] = encoding, entry(path)
    manifest = snapshot_manifest(plan["snapshot"])
    require(manifest["id"] == plan["snapshot_id"], "benchmark source identity changed")
    lineage_path = Path(plan["snapshot"]) / "lineage.jsonl"
    require(
        sha(lineage_path) == manifest["files"]["lineage.jsonl"]["sha256"],
        "source-group lineage changed",
    )
    lineages = [json.loads(line) for line in lineage_path.read_bytes().splitlines() if line.strip()]
    source_groups = {r["original_id"]: r["source_group"] for r in lineages}
    coverage = {
        sid: dict(
            raw_characters=joints[sid]["A_manifest"]["original_public_content_characters"],
            approved_characters=joints[sid]["A_manifest"]["positive_public_content_characters"],
            positive_tokens=encodings[sid]["layer_target_counts"]["reason"],
            all_reason_tokens_masked=encodings[sid][
                "public_content_without_positive_reason_targets"
            ],
        )
        for sid in joint_ids
    }
    support = support_profile(tasks, joint_by_task, maps, encodings, source_groups, coverage)
    return dict(
        support=support,
        joints=joints,
        encodings=encodings,
        encoding_entries=encoding_entries,
        tokenizer_binding=tokenizer_binding(tokenizer),
        source_manifest=manifest,
        reviews=reviews,
        maps=maps,
        originals=originals,
    )


def freeze_material(output=OUTPUT, plan=None, review_seal=None):
    output = Path(output).resolve()
    reader = Reader()
    actual_plan = checked(reader.read(entry(output / "registration/protocol.json")))
    require(
        plan is None or plan == actual_plan, "material plan differs from the actual registration"
    )
    if review_seal is not None:
        require(
            review_seal == reader.read(entry(output / "review_seal/record.json")),
            "supplied review seal differs",
        )
    result = _collect(output, actual_plan, reader, produce_encodings=True)
    support = result["support"]
    support_path = output / "material/support/record.json"
    persist(support_path.parent, support)
    ready = support["material_complete"] and support["exploratory_training_admitted"]
    body = dict(
        schema="v10_material_freeze_result.v1",
        protocol_id=actual_plan["id"],
        support=entry(support_path),
        N=support["N"],
        phase="READY_EXPLORATORY"
        if ready
        else "BLOCKED_REPRESENTATION_OR_MAPPING"
        if support["capability_profile"]["blockers"]
        else "DEGENERATE_SUPPORT",
        training_admitted=ready,
        source_file_count=len(reader.cache),
        no_joint_original_removed=True,
        API_calls=0,
        GPU_used=False,
    )
    if ready:
        binding = bound(
            dict(
                schema=BINDING_SCHEMA,
                protocol_id=actual_plan["id"],
                batch_id=actual_plan["batch_id"],
                review_policy_id=review_policy_definition()["id"],
                generation_root=str(output),
                generation_protocol=entry(output / "registration/protocol.json"),
                generation_seal=entry(output / "generation_seal/record.json"),
                native_support=entry(output / "native_support/record.json"),
                review_seal=entry(output / "review_seal/record.json"),
                mapping_seal=entry(output / "mapping_seal/record.json"),
                support_manifest=entry(support_path),
                encodings=result["encoding_entries"],
                tokenizer_binding=list(result["tokenizer_binding"]),
                fixed_arms=["Static", "Manual+", "Manual-", "C-only", "Full"],
                fixed_seeds=[11, 29, 47],
                no_extra_minimum_N=True,
                actual_data_only=True,
                feedback_denominator=700,
            )
        )
        path = output / "material/binding/record.json"
        persist(path.parent, binding)
        body["binding"] = entry(path)
    frozen = bound(body)
    persist(output / "material/result", frozen)
    return frozen


def load_training_pool(binding_path):
    binding_path = Path(binding_path).resolve()
    binding = checked(read_json(binding_path), BINDING_SCHEMA)
    reader = Reader()
    output = Path(binding["generation_root"]).resolve()
    require(
        binding_path == output / "material/binding/record.json"
        and binding["review_policy_id"] == review_policy_definition()["id"],
        "new real material binding required",
    )
    for key, relative in (
        ("generation_protocol", "registration/protocol.json"),
        ("generation_seal", "generation_seal/record.json"),
        ("native_support", "native_support/record.json"),
        ("review_seal", "review_seal/record.json"),
        ("mapping_seal", "mapping_seal/record.json"),
        ("support_manifest", "material/support/record.json"),
    ):
        checked(reader.read(binding[key], output / relative))
    plan = reader.read(binding["generation_protocol"])
    require(
        binding["protocol_id"] == plan["id"] and binding["batch_id"] == plan["batch_id"],
        "new material registration identity changed",
    )
    result = _collect(output, plan, reader, produce_encodings=False)
    support = result["support"]
    require(
        reader.read(binding["support_manifest"]) == support
        and support["material_complete"]
        and support["exploratory_training_admitted"]
        and binding["encodings"] == result["encoding_entries"]
        and tuple(binding["tokenizer_binding"]) == result["tokenizer_binding"],
        "no partial, degenerate, cherry-picked or unencoded kernel may train",
    )
    packages, arrays, chi = [], {}, {}
    for task in support["training_task_ids"]:
        part = support["task_support"][task]
        chi[task] = part["chi"]
        for sid in part["joint_valid_slot_ids"]:
            encoded = result["encodings"][sid]
            arrays[sid] = encoded["rows"]
            packages.append(
                dict(
                    package_id=sid,
                    task_id=task,
                    state_id=result["maps"][task]["state_by_slot"][sid],
                    whole_package_target_tokens=encoded["L_P"],
                    fused=False,
                )
            )
    pool = VerifiedPool(
        support["training_task_ids"],
        packages,
        arrays,
        binding_id=binding["id"],
        chi=chi,
        production=True,
    )
    pool._manifest.registration.validator_binding_id = "v10_real_AB_A_mask_once_semantic_mapping.v1"
    pool.material_schema = BINDING_SCHEMA
    pool.conditional_scope_verified = True
    pool.execution_plan = support["execution_plan"]
    pool.support_manifest, pool.capability_profile = support, support["capability_profile"]
    pool.tokenizer_binding = result["tokenizer_binding"]
    pool.source_manifest_sha256 = digest(result["source_manifest"])
    pool.generation_launch_id = pool.original_material_protocol_id = plan["id"]
    pool.public_input_parent_id = plan["original"]["id"]
    pool.verified_file_count = len(reader.cache)
    return pool
