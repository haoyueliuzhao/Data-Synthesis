"""Raw compact targets only; original HTTP inputs, target-only masks, no Student."""

from __future__ import annotations

import hashlib

from trusted_synthesis.canonical_json import canonical_json_bytes
from trusted_synthesis.domains.finance.qa_vnext.protocol import record, require
from trusted_synthesis.domains.finance.qa_vnext.runtime import DurableStore
from trusted_synthesis.experiments.finance_qa_vnext_harness_responsibility.audit import (
    manifest,
    read,
)
from trusted_synthesis.experiments.finance_qa_vnext_length_adaptation.core import asset_binding
from trusted_synthesis.experiments.finance_qa_vnext_model_execution.plan import seal_directory
from trusted_synthesis.experiments.finance_qa_vnext_model_execution.representation import (
    encode_original_candidate,
)
from trusted_synthesis.experiments.qa_reasoning_share_training_preflight import (
    tokenization as assets,
)

VERSION = "harness_transfer_original_compact_supervision.v1"


def policy(binding):
    return record(
        "transfer_representation_policy",
        version=VERSION,
        tokenizer_binding_id=binding["id"],
        tokenizer_asset_id=asset_binding(binding)["id"],
        maximum_sequence_length=32768,
        truncation=False,
        chat_suffix=assets.CHAT_SUFFIX,
        suffix_token_ids=assets.SUFFIX_TOKEN_IDS,
        mask_policy=assets.MASK_POLICY,
        causal_shift=1,
        padding_side="right",
        positive_eligibility="qualified entire session AND admitted original response",
        target="exact Provider content UTF-8 bytes, never language_binding.expanded",
        inputs="actual original HTTP system/user messages, including condition and feedback",
        package="all admitted per-request rows; no concatenated conversation",
        environments_separate=["H1", "H2"],
        quotient_weights=False,
        student_weights=False,
        student_forward=False,
        student_updates=False,
    )


def export_session(directory, qualification, registration):
    rows, excluded = [], []
    if qualification["status"] != "qualified":
        return rows, [{"session": registration["label"], "reason": qualification["status"]}]
    manifest(directory)
    require(
        read(directory / "qualification.json") == qualification, "transfer_rep.saved_qualification"
    )
    session = read(directory / "runtime/session.json")
    require(
        qualification["readonly_verified"] is True
        and qualification["condition"] == registration["condition"]
        and read(directory / "runtime/base_context.json")["task_id"] == registration["task_id"],
        "transfer_rep.task_condition_binding",
    )
    ledger = read(directory / "transport/ledger.json")
    attempts = {r["turn_index"]: r for r in ledger["attempts"]}
    for event in session["events"]:
        index = event["sequence"]
        if not event["receipt"]["admitted"]:
            excluded.append(
                {
                    "session": registration["label"],
                    "turn": index,
                    "reason": event["receipt"]["error_code"],
                    "raw_event_retained": True,
                }
            )
            continue
        paths = attempts[index]["paths"]
        http = read(directory / "transport" / paths["http_request"])
        provider = read(directory / "transport" / paths["http_response_body"])
        outcome = read(directory / "transport" / paths["outcome"])
        raw = (directory / "runtime/turns" / f"{index:03d}_response.txt").read_bytes()
        require(
            outcome["public_content_returned_to_runtime"] and not outcome["condition_flags"],
            "transfer_rep.valid_model_origin",
        )
        require(
            raw
            == provider["choices"][0]["message"]["content"].encode()
            == (directory / "transport" / paths["public_content"]).read_bytes(),
            "transfer_rep.original_target_not_expansion",
        )
        require(
            http["messages"][1]["content"].encode() == canonical_json_bytes(event["request"]),
            "transfer_rep.original_public_request",
        )
        require(
            hashlib.sha256(raw).hexdigest() == event["submission"]["raw_sha256"],
            "transfer_rep.raw_submission_hash",
        )
        require(
            event["language_binding"]["model_submission"] == event["parsed"],
            "transfer_rep.model_ownership",
        )
        rows.append(
            record(
                "transfer_supervision_candidate",
                version=VERSION,
                label=registration["label"],
                condition=registration["condition"],
                task_key=registration["task_key"],
                task_id=registration["task_id"],
                session_id=session["id"],
                protocol_id=event["request"]["protocol_id"],
                qualification_id=qualification["id"],
                public_runtime_state_id=event["request"]["state"]["id"],
                public_request_id=event["request"]["id"],
                provider_outcome_id=outcome["id"],
                submission_id=event["submission"]["id"],
                receipt_id=event["receipt"]["id"],
                language_binding_id=event["language_binding"]["id"],
                turn_index=index,
                messages=http["messages"],
                target_text=raw.decode(),
                target_raw_sha256=hashlib.sha256(raw).hexdigest(),
                target_raw_bytes=len(raw),
                submission_kind=event["parsed"]["kind"],
                admitted=True,
                complete_session_qualified=True,
                original_feedback_preserved=True,
                expanded_target_used=False,
                quotient_assignment_id=None,
                class_weights_assigned=False,
            )
        )
    return rows, excluded


def encode(row, binding, tokenizer, frozen_policy):
    require(frozen_policy == policy(binding), "transfer_rep.fixed_policy")
    encoded = encode_original_candidate(row, binding, tokenizer, maximum_sequence_length=32768)
    return record(
        "transfer_token_record",
        **{k: v for k, v in encoded.items() if k not in {"id", "schema_version"}},
        representation_policy_id=frozen_policy["id"],
        condition=row["condition"],
        original_compact_target=True,
        system_expansion_target=False,
    )


def build(output, registrations, qualifications, binding, frozen_policy):
    store = DurableStore(output / "representation")
    store.json("policy.json", frozen_policy)
    store.json("tokenizer_binding.json", binding)
    by_label = {r["label"]: r for r in registrations}
    tokenizer = (
        assets.load_tokenizer(binding)
        if any(q["qualification"]["status"] == "qualified" for q in qualifications)
        else None
    )
    summaries = []
    for condition in ("H1", "H2"):
        child = DurableStore(store.root / condition)
        rows, excluded, packages = [], [], []
        for item in qualifications:
            label, q = item["label"], item["qualification"]
            if by_label[label]["condition"] != condition:
                continue
            candidates, rejections = export_session(
                output / "execution/sessions" / label, q, by_label[label]
            )
            rows.extend(candidates)
            excluded.extend(rejections)
            packages.append(
                {
                    "label": label,
                    "qualification_id": q["id"],
                    "status": q["status"],
                    "row_ids": [r["id"] for r in candidates],
                }
            )
        child.json(
            "candidates.json",
            record(
                "transfer_supervision_dataset",
                condition=condition,
                policy_id=frozen_policy["id"],
                rows=rows,
                excluded=excluded,
                target_is_original_model_content=True,
                old_rows_imported=False,
            ),
        )
        metadata = []
        for index, row in enumerate(rows):
            token = encode(row, binding, tokenizer, frozen_policy)
            child.json(f"tokens/{index:04d}.json", token)
            metadata.append(
                {
                    k: v
                    for k, v in token.items()
                    if k not in {"input_ids", "labels", "target_mask", "attention_mask"}
                }
            )
        tokens = {t["row_id"]: t for t in metadata}
        for package in packages:
            package["complete_token_package"] = bool(package["row_ids"]) and all(
                tokens[key]["consumable_token_representation"] for key in package["row_ids"]
            )
        summary = record(
            "transfer_representation_summary",
            condition=condition,
            candidate_count=len(rows),
            fit_count=sum(t["consumable_token_representation"] for t in metadata),
            not_fit_count=sum(not t["consumable_token_representation"] for t in metadata),
            sequence_length_min=min((t["sequence_length"] for t in metadata), default=None),
            sequence_length_max=max((t["sequence_length"] for t in metadata), default=None),
            target_token_count=sum(t["target_token_count"] for t in metadata),
            excluded=excluded,
            packages=packages,
            token_records=metadata,
            complete_token_packages=sum(p["complete_token_package"] for p in packages),
            failed_or_unknown_sessions_not_positive=True,
            student_forward=0,
            student_updates=0,
        )
        child.json("summary.json", summary)
        seal_directory(
            child, kind="transfer_representation_condition_manifest", summary_id=summary["id"]
        )
        summaries.append(summary)
    store.json(
        "summary.json",
        record(
            "transfer_representation",
            conditions=summaries,
            condition_datasets_combined=False,
            class_weights_assigned=False,
            provider_usage_is_not_training_representation=True,
        ),
    )
    seal_directory(store, kind="transfer_representation_manifest", policy_id=frozen_policy["id"])
    return summaries
