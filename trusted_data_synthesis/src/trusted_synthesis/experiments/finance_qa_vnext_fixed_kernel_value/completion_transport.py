"""Budget-only continuation of frozen slots, with split-source authentication.

The original runtime, source execution, request rendering and scientific rules
are unchanged. Public prefixes are replayed, never requested again; their fatal
budget attempt remains an immutable parent artifact and explicit lineage field.
"""

import copy
from pathlib import Path

from . import protocol as p
from . import runtime, transport


def _public_request_ids(session):
    return [turn["transport_evidence"]["request_id"] for turn in session["turns"]]


def validate_parent_prefix(session, registered, journal):
    """Only a known, unsent budget interruption is eligible for continuation."""
    p.checked(session, "material_session")
    p.require(
        session["registered_session"] == registered
        and session["registered_session_id"] == registered["session_id"]
        and session["first_final_index"] is None
        and session["global_fatal"] is True
        and session["fatal_error"] is not None
        and session["fatal_error"]["response_index"] == len(session["turns"])
        and len(session["turns"]) < p.MAX_RESPONSES,
        "completion.budget_interrupted_original_slot_only",
    )
    runtime.replay(session)
    rows = [row for row in journal if row["state"] != "not_sent"]
    p.require(
        len(rows) == len(session["turns"])
        and all(row["state"] == "settled" for row in rows)
        and all(row["outcome"] == "public_response_received" for row in rows)
        and all(row.get("http_success") == 1 for row in rows)
        and all(
            type(row.get("reported_total_tokens")) is int
            and row["charged_tokens"] == row["reported_total_tokens"]
            for row in rows
        )
        and [row["request_id"] for row in rows] == _public_request_ids(session),
        "completion.no_sent_unknown_or_failed_request_replay",
    )
    p.require(
        all(row.get("charged_tokens") == 0 for row in journal if row["state"] == "not_sent"),
        "completion.unsent_parent_cancellation_known_zero",
    )
    return len(session["turns"])


class PrefixProvider:
    """Feed exact stored turns to the runner before the first new HTTP call."""

    def __init__(self, provider, *, registered, parent_session=None, parent_journal=()):
        self.provider = provider
        self.registered = registered
        self.parent = parent_session
        self.prefix_count = (
            validate_parent_prefix(parent_session, registered, parent_journal)
            if parent_session is not None
            else 0
        )
        if parent_session is None:
            p.require(not parent_journal, "completion.unrequested_slot_has_no_parent_requests")
        self.next_index = 0
        self.new_provider_calls = 0

    def __call__(self, messages, context):
        index = context["response_index"]
        p.require(
            index == self.next_index and context["session_id"] == self.registered["session_id"],
            "completion.exact_monotone_original_response_index",
        )
        self.next_index += 1
        if index < self.prefix_count:
            turn = self.parent["turns"][index]
            p.require(
                messages == turn["input_messages"]
                and context == self.parent["provider_attempts"][index]["context"]
                and p.sha(turn["raw_response"]) == turn["raw_response_sha256"],
                "completion.exact_original_public_prefix",
            )
            metadata = copy.deepcopy(turn["transport_response_metadata"])
            return {"raw_response": turn["raw_response"], **metadata}
        self.new_provider_calls += 1
        return self.provider(messages, context)


def generate(
    registered,
    fixture,
    provider,
    *,
    completion_freeze_id,
    parent_session=None,
    parent_journal=(),
    slot_manifest=None,
):
    """Return a derived session and immutable lineage, not a rewritten parent."""
    wrapped = PrefixProvider(
        provider,
        registered=registered,
        parent_session=parent_session,
        parent_journal=parent_journal,
    )
    if slot_manifest is not None:
        p.require(
            slot_manifest["registered_session"] == registered
            and slot_manifest["parent_status"]
            == ("budget_aborted" if parent_session is not None else "not_run")
            and slot_manifest["prefix_request_ids"]
            == (_public_request_ids(parent_session) if parent_session else []),
            "completion.exact_prospective_slot_manifest",
        )
    session = runtime.generate(
        fixture["messages"], fixture["identity"], provider=wrapped, registered=registered
    )
    count = wrapped.prefix_count
    if parent_session is not None:
        p.require(
            session["turns"][:count] == parent_session["turns"]
            and session["events"][:count] == parent_session["events"]
            and session["provider_attempts"][:count] == parent_session["provider_attempts"][:count],
            "completion.derived_history_keeps_every_original_public_event",
        )
    lineage = p.record(
        "material_completion_lineage",
        completion_freeze_id=completion_freeze_id,
        registered_session_id=registered["session_id"],
        registration_id=registered["id"],
        material_session_id=session["id"],
        parent_material_session_id=parent_session["id"] if parent_session else None,
        parent_session_content_sha256=p.sha(p.encode(parent_session)) if parent_session else None,
        parent_fatal_attempt=copy.deepcopy(parent_session["provider_attempts"][-1])
        if parent_session
        else None,
        original_public_prefix_count=count,
        original_public_prefix_sha256=p.sha(p.encode(session["turns"][:count])),
        original_public_request_ids=_public_request_ids(parent_session) if parent_session else [],
        appended_public_request_ids=[
            turn["transport_evidence"]["request_id"] for turn in session["turns"][count:]
        ],
        new_provider_calls=wrapped.new_provider_calls,
        maximum_total_responses=p.MAX_RESPONSES,
        maximum_total_tools=p.MAX_TOOLS,
        parent_budget_attempt_reclassified_as_success=False,
        parent_budget_attempt_retained_in_lineage=True,
        original_parent_files_rewritten=False,
        public_prefix_requests_reissued=0,
        role_reassignment=False,
        outcome_based_reselection=False,
        slot_manifest_id=slot_manifest.get("id") if slot_manifest else None,
        slot_manifest_sha256=p.sha(p.encode(slot_manifest)) if slot_manifest else None,
    )
    return {"session": session, "lineage": lineage}


def verify_origin(
    session,
    ledger,
    output,
    *,
    parent_output,
    parent_policy,
    lineage,
    completion_policy=None,
):
    """Authenticate the exact parent/suffix union using each actual ledger row.

    ``output`` and ``parent_output`` are request directories, not study roots.
    No inherited session is re-assessed by this function: it serves new slots.
    The receipt's original purpose label is preserved; new request leases carry
    separate completion authority, whose ledger owns all additional charges.
    """
    p.checked(session, "material_session")
    p.checked(parent_policy, "fixed_kernel_policy")
    completion_policy = p.policy() if completion_policy is None else completion_policy
    p.checked(completion_policy, "fixed_kernel_policy")
    p.checked(lineage, "material_completion_lineage")
    registered = ledger.registered(session["registered_session_id"])
    p.require(
        registered == session["registered_session"]
        and lineage["registered_session_id"] == registered["session_id"]
        and lineage["registration_id"] == registered["id"]
        and lineage["material_session_id"] == session["id"]
        and lineage["completion_freeze_id"] == ledger.completion_freeze_id,
        "completion.origin_registered_lineage_authority",
    )
    parent_rows = ledger.parent_requests(registered["session_id"])
    new_rows = ledger.new_requests(registered["session_id"])
    rows = [row for row in parent_rows if row["state"] != "not_sent"] + new_rows
    turns = session["turns"]
    count = lineage["original_public_prefix_count"]
    parent_ids = [row["request_id"] for row in parent_rows if row["state"] != "not_sent"]
    p.require(
        len(parent_ids) == count
        and parent_ids == lineage["original_public_request_ids"]
        and p.sha(p.encode(turns[:count])) == lineage["original_public_prefix_sha256"]
        and len(rows) >= len(turns)
        and len({row["request_id"] for row in rows}) == len(rows),
        "completion.origin_exact_split_prefix_inventory",
    )
    verified = []
    for index, turn in enumerate(turns):
        row = rows[index]
        inherited = index < count
        directory = Path(parent_output if inherited else output) / row["request_id"]
        policy = parent_policy if inherited else completion_policy
        request = p.checked(p.read_json(directory / "request.json"), "material_public_request")
        response = p.checked(
            p.read_json(directory / "public_response.json"), "material_public_response"
        )
        receipt = p.checked(p.read_json(directory / "receipt.json"), "material_request_receipt")
        body, raw = transport.render(turn["input_messages"])
        p.require(
            row["attempt"] == index + 1
            and row["state"] == "settled"
            and row["http_success"] == 1
            and row["response_model"] == p.MODEL
            and row["outcome"] == "public_response_received"
            and request["session_id"] == registered["session_id"]
            and request["request_id"] == row["request_id"]
            and request["policy_id"] == policy["id"]
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
            and response["public_content_sha256"] == p.sha(turn["raw_response"])
            and turn["raw_response_sha256"] == p.sha(turn["raw_response"])
            and receipt["request_id"] == row["request_id"]
            and receipt["response_id"] == response["id"]
            and receipt["known_usage"] is True
            and receipt["live_http_sender"] is True
            and receipt["outcome"] == "public_response_received"
            and receipt["freeze_id"] == ledger.freeze_id
            and receipt["purpose"] == "fixed_empirical_material_kernel"
            and turn["transport_response_metadata"]["receipt"] == receipt,
            "completion.authentic_exact_split_request_response_chain",
        )
        if not inherited:
            p.require(
                request["completion_freeze_id"] == ledger.completion_freeze_id,
                "completion.new_request_separate_budget_authority",
            )
        usage = response["usage"]
        p.require(
            all(
                type(usage.get(key)) is int
                for key in ("prompt_tokens", "completion_tokens", "total_tokens")
            )
            and usage["prompt_tokens"] == row["prompt_tokens"]
            and usage["completion_tokens"] == row["completion_tokens"]
            and usage["total_tokens"] == row["charged_tokens"] == row["reported_total_tokens"],
            "completion.origin_actual_ledger_usage",
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
            "completion.origin_evidence_projection",
        )
        verified.append(
            {
                "request_id": row["request_id"],
                "request_record_id": request["id"],
                "response_id": response["id"],
                "receipt_id": receipt["id"],
                "source": "parent" if inherited else "completion",
            }
        )
    p.require(
        [turn["transport_evidence"]["request_id"] for turn in turns[count:]]
        == lineage["appended_public_request_ids"],
        "completion.exact_appended_public_request_inventory",
    )
    complete = session["first_final_index"] is not None and len(rows) == len(turns) and bool(turns)
    return p.record(
        "material_origin_verification",
        session_id=session["id"],
        registered_session_id=registered["session_id"],
        verified_turns=verified,
        verified_public_prefix=bool(turns),
        complete_first_Final_request_chain=complete,
        status="PASS_AUTHENTIC_MATERIAL_PUBLIC_CHAIN"
        if complete
        else "AUTHENTIC_PREFIX_NOT_COMPLETE_FINAL"
        if turns
        else "NO_AUTHENTIC_PUBLIC_TURNS",
        completion_lineage_id=lineage["id"],
        completion_freeze_id=ledger.completion_freeze_id,
        parent_public_prefix_count=count,
        callback_self_attestation_accepted=False,
        wire_envelope_reconstruction_claimed=False,
    )
