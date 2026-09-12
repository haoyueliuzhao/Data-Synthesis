#!/usr/bin/env python3
"""Read-only post-seal worker/material/request audit; JSON report goes to stdout.

Does not load a tokenizer, decode token IDs, fetch sources, generate model outputs,
write any artifacts, or change frozen code. Run with the existing project venv:
    trusted_data_synthesis/.venv/bin/python \
      trusted_data_synthesis/scripts/audit_qa_vnext_catalog_bridge_worker.py

Replay uses the frozen evaluator; hashes, array masks, original text rendering,
fine-class comparisons and three-way request usage checks are independent code.
This is a same-team reproducibility audit, not external financial certification.
Evaluation-panel financial/period semantics are explicitly OUT OF SCOPE.
"""

import argparse
import ast
import hashlib
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ARTIFACT = "trusted_data_synthesis/artifacts/qa_vnext_catalog_bridge/catalog_bridge_20260912"
PRODUCTION_COMMIT = "dd7567a11961176c2aea07680438ba06c9a36a07"


def encode(value):
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode()


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def read(path):
    return json.loads(path.read_bytes())


class Audit:
    def __init__(self):
        self.count = 0
        self.failures = []

    def check(self, name, condition, detail=None):
        self.count += 1
        if not condition:
            self.failures.append({"check": name, "detail": detail})

    def identities(self, value):
        if isinstance(value, dict):
            identifier = value.get("id")
            if isinstance(identifier, str) and isinstance(value.get("schema_version"), str):
                digest = identifier.rsplit(":", 1)[-1]
                if len(digest) == 64:
                    self.check(
                        "record_identity:" + identifier,
                        sha(encode({k: v for k, v in value.items() if k != "id"})) == digest,
                    )
            for child in value.values():
                self.identities(child)
        elif isinstance(value, list):
            for child in value:
                self.identities(child)


def source_order_body(body):
    """Restore only the frozen sender's key order; archive JSON sorts mappings."""
    return {
        "model": body["model"],
        "messages": [{"role": m["role"], "content": m["content"]} for m in body["messages"]],
        "thinking": {"type": body["thinking"]["type"]},
        "response_format": {"type": body["response_format"]["type"]},
        "max_tokens": body["max_tokens"],
        "stream": body["stream"],
    }


def audit(root):
    root = Path(root).resolve()
    directory = root / ARTIFACT
    audit = Audit()
    check = audit.check
    manifest = read(directory / "manifest.json")
    manifest_hash_before = sha((directory / "manifest.json").read_bytes())
    report_hash_before = sha((directory / "controls/report.json").read_bytes())
    members = {m["path"]: m for m in manifest["members"]}
    for relative, member in members.items():
        path = directory / relative
        check(
            "manifest_member:" + relative,
            path.is_file()
            and path.stat().st_size == member["bytes"]
            and sha(path.read_bytes()) == member["sha256"],
        )
    frozen = read(directory / "stage_freeze.json")
    for member in frozen["code"]:
        path = root / member["path"]
        check(
            "frozen_code:" + member["path"],
            path.is_file() and sha(path.read_bytes()) == member["sha256"],
        )
    check("production_commit", frozen["git_commit"] == PRODUCTION_COMMIT)
    # Do not replay mismatching code or altered artifacts.
    if audit.failures:
        return {"status": "INPUT_OR_CODE_BINDING_FAILED", "failures": audit.failures}
    report = read(directory / "controls/report.json")
    audit.identities(report)
    top = read(directory / "report.json")
    full = read(directory / "catalog.json")
    selection = read(directory / "controls/fixture_selection.json")
    guards = read(directory / "execution_guards.json")
    catalog = {row["task_id"]: row for row in full["tasks"]}
    parent_cache, native_cache, bundles = {}, {}, {}
    for row in selection["rows"]:
        entry = catalog[row["task_id"]]
        parent = entry["parent_directory"]
        if parent not in parent_cache:
            source_manifest = read(root / parent / "manifest.json")
            parent_cache[parent] = (
                source_manifest,
                {member["path"]: member for member in source_manifest["members"]},
            )
        source_manifest, source_members = parent_cache[parent]
        for key in ("bundle_path", "native_bindings_path", "public_path"):
            check("parent_manifest:" + parent, source_manifest["id"] == entry["parent_manifest_id"])
            relative = Path(entry[key]).relative_to(parent).as_posix()
            member = source_members[relative]
            path = root / entry[key]
            check(
                "parent_member:" + entry[key],
                path.stat().st_size == member["bytes"]
                and sha(path.read_bytes()) == member["sha256"],
            )
        bundles[row["task_id"]] = read(root / entry["bundle_path"])
        native_path = entry["native_bindings_path"]
        if native_path not in native_cache:
            native_cache[native_path] = read(root / native_path)
        check("existing_parent_fixture:" + row["task_id"], "qa_vnext_surface_build" in parent)
    sys.path.insert(0, str(root / "trusted_data_synthesis/src"))
    from trusted_synthesis.experiments.finance_qa_vnext_catalog_bridge.assessment import (
        assess_session,
    )

    assessments = {a["session_id"]: a for a in report["assessments"]}
    sessions = {s["id"]: s for s in report["sessions"]}
    names = {row["session_id"]: row["name"] for row in report["rows"]}
    session_rows, event_counts, method_counts = [], Counter(), Counter()
    for sid, session in sessions.items():
        tid = session["identity"]["task_id"]
        entry = catalog[tid]
        assessment = assessments[sid]
        repeated = assess_session(
            session, bundles[tid], native_cache[entry["native_bindings_path"]]
        )
        check("assessment_full_replay:" + sid, repeated == assessment)
        check(
            "session_public_hash:" + sid,
            sha(encode(session["public_messages"]))
            == session["identity"]["public_messages_sha256"]
            == entry["public_messages_sha256"],
        )
        check(
            "public_only_identity:" + sid,
            set(session["identity"])
            == {
                "task_id",
                "family",
                "surface_version_id",
                "public_messages_sha256",
                "parent_manifest_id",
            },
        )
        check(
            "original_public_messages:" + sid,
            read(root / entry["public_path"]) == session["public_messages"],
        )
        raw_finals = []
        for turn, event in zip(session["turns"], session["events"], strict=True):
            try:
                parsed = json.loads(turn["raw_response"])
            except (ValueError, TypeError):
                parsed = None
            if isinstance(parsed, dict) and "final" in parsed:
                raw_finals.append(turn["response_index"])
            check(
                "response_utf8_hash:" + sid + ":" + str(turn["response_index"]),
                sha(turn["raw_response"].encode()) == turn["raw_response_sha256"],
            )
            event_counts["events"] += 1
            if event["tool_call"]:
                event_counts[event["tool_call"]["tool"] + ":" + event["tool_call"]["status"]] += 1
            event_counts["protocol_errors"] += int(bool(event["protocol_error"]))
            event_counts["finals"] += int(event["final"])
        check(
            "first_final_terminal:" + sid,
            (not raw_finals and session["first_final_index"] is None)
            or (
                len(raw_finals) == 1
                and raw_finals[0] == session["first_final_index"] == len(session["turns"]) - 1
            ),
        )
        for key in (
            "provider_calls",
            "teacher_sessions",
            "training_samples",
            "model_weight_loads",
            "gpu_calls",
        ):
            check("session_zero_" + key + ":" + sid, session[key] == 0)
        check(
            "session_scripted:" + sid,
            session["origin"] == "scripted_interface_control"
            and session["private_oracle_access"] is False,
        )
        check("assessment_not_training:" + sid, assessment["training_eligible"] is False)
        method_counts[assessment["actual_method"]] += 1
        session_rows.append(
            {
                "name": names[sid],
                "session_id": sid,
                "first_final_index": session["first_final_index"],
                "financial_valid": assessment["financial_valid"],
                "actual_method": assessment["actual_method"],
                "full_mapping_status": assessment["full_mapping_status"],
                "reason": assessment["reason"],
                "pending_reasons": assessment.get("full_mapping_pending_reasons", []),
            }
        )
    pending = [row for row in session_rows if row["full_mapping_status"] != "MAPPED"]
    check(
        "registered_36",
        len(sessions)
        == len(assessments)
        == len(report["rows"])
        == report["registered"]
        == report["passed"]
        == 36,
    )
    check(
        "mapped_29_pending_7",
        Counter(a["full_mapping_status"] for a in assessments.values())
        == {"MAPPED": 29, "PENDING_REVIEW": 7},
    )
    check(
        "pending_one_valid_recovery",
        sum(p["financial_valid"] for p in pending) == 1
        and [p["pending_reasons"] for p in pending if p["financial_valid"]]
        == [["format_recovery_complete_class_review"]],
    )
    packages = {p["id"]: p for p in report["raw_packages"]}
    candidates = {}
    material = report["materialization"]
    binding, policy = material["binding"], material["policy"]
    for package in packages.values():
        session = sessions[package["session_id"]]
        assessment = assessments[package["session_id"]]
        check(
            "raw_package_join:" + package["id"],
            package["assessment_id"] == assessment["id"]
            and package["all_raw_turns_retained"] == session["turns"],
        )
        check(
            "raw_package_nontraining:" + package["id"],
            package["financial_valid"]
            and package["complete_first_final_package"]
            and package["training_eligible"] is False
            and package["training_samples"] == 0
            and package["origin"] == "scripted_interface_control",
        )
        expected = [
            turn["response_index"]
            for turn, event in zip(session["turns"], session["events"], strict=True)
            if event["final"]
            or event["tool_call"] is not None
            and event["tool_call"]["status"] == "ok"
        ]
        check(
            "whole_original_positive_package:" + package["id"],
            [r["response_index"] for r in package["candidates"]] == expected,
        )
        for candidate in package["candidates"]:
            candidates[candidate["id"]] = candidate
            turn = session["turns"][candidate["response_index"]]
            check(
                "raw_candidate_original_history:" + candidate["id"],
                candidate["messages"] == turn["input_messages"]
                and candidate["target_text"] == turn["raw_response"]
                and candidate["target_raw_sha256"] == sha(turn["raw_response"].encode())
                and candidate["training_sample"] is False,
            )
    check(
        "raw_packages_30_rows_167",
        len(packages) == material["packages"] == 30
        and len(candidates) == material["encoded_rows"] == len(material["checks"]) == 167,
    )
    lengths, total_target, total_sequence = [], 0, 0
    for tokencheck in material["checks"]:
        row = tokencheck["representation"]
        candidate = candidates[tokencheck["candidate_id"]]
        ids, mask, labels = row["input_ids"], row["target_mask"], row["labels"]
        start, end, length = row["target_token_start"], row["target_token_end"], len(ids)
        check(
            "token_identity_joins:" + candidate["id"],
            row["row_id"] == candidate["id"]
            and row["session_id"] == candidate["session_id"]
            and row["qualification_id"] == candidate["qualification_id"]
            and tokencheck["policy_id"] == policy["id"],
        )
        check(
            "token_array_lengths:" + candidate["id"],
            length
            == row["sequence_length"]
            == len(mask)
            == len(labels)
            == len(row["attention_mask"])
            and row["attention_mask"] == [1] * length,
        )
        check(
            "causal_target_mask:" + candidate["id"],
            mask == [int(start <= i < end) for i in range(length)]
            and labels == [token if mask[i] else -100 for i, token in enumerate(ids)]
            and start > 0
            and sum(mask[1:]) == end - start == row["target_token_count"],
        )
        check(
            "causal_shift:" + candidate["id"],
            row["causal_shift"] == 1
            and row["causal_target_token_start"] == start - 1
            and row["causal_target_token_end"] == end - 1,
        )
        check(
            "no_truncation_or_overflow:" + candidate["id"],
            length <= 24576
            and row["maximum_sequence_length"] == 24576
            and row["truncated"] is False
            and row["consumable_token_representation"] is True
            and tokencheck["status"] == "PASS",
        )
        check(
            "suffix_and_prompt_excluded:" + candidate["id"],
            ids[end:] == binding["suffix_token_ids"] == [151645, 198]
            and row["prompt_token_count"] == start
            and row["suffix_token_count"] == length - end,
        )
        check(
            "ordinary_original_roles:" + candidate["id"],
            all(
                set(m) == {"role", "content"} and m["role"] in {"system", "user", "assistant"}
                for m in candidate["messages"]
            ),
        )
        prefix = (
            "".join(
                "<|im_start|>" + m["role"] + "\n" + m["content"] + "<|im_end|>\n"
                for m in candidate["messages"]
            )
            + "<|im_start|>assistant\n"
        )
        rendered = prefix + candidate["target_text"] + "<|im_end|>\n"
        check(
            "rendered_original_bytes:" + candidate["id"],
            sha(rendered.encode()) == row["rendered_sha256"]
            and len(rendered.encode()) == row["rendered_byte_count"]
            and len(prefix) == row["target_character_start"]
            and len(prefix) + len(candidate["target_text"]) == row["target_character_end"],
        )
        check(
            "token_target_raw_hash:" + candidate["id"],
            row["target_raw_sha256"] == candidate["target_raw_sha256"]
            and row["target_raw_byte_count"] == len(candidate["target_text"].encode()),
        )
        lengths.append(length)
        total_target += row["target_token_count"]
        total_sequence += length
    check(
        "target_sum_9284",
        total_target
        == material["target_tokens"]
        == top["materialization_summary"]["target_tokens"]
        == 9284,
    )
    check(
        "frozen_cap_and_context",
        policy["maximum_sequence_length"] == binding["maximum_sequence_length"] == 24576
        and binding["model_max_position_embeddings"] == 32768
        and binding["tokenizer_declared_limit_is_model_context_authority"] is False,
    )
    check("single_reported_tokenizer_load", material["tokenizer_loads"] == 1)
    source = (
        root
        / "trusted_data_synthesis/src/trusted_synthesis/experiments"
        / "finance_qa_vnext_catalog_bridge/materials.py"
    ).read_text()
    loader = next(
        n
        for n in ast.parse(source).body
        if isinstance(n, ast.FunctionDef) and n.name == "load_local_tokenizer"
    )
    loader_calls = [
        n.func.attr
        for n in ast.walk(loader)
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
    ]
    check(
        "single_frozen_tokenizer_constructor_path",
        loader_calls == ["_binding_and_tokenizer"],
        loader_calls,
    )
    for key in ("training_samples", "model_weight_loads", "gpu_calls", "provider_calls"):
        check("material_zero_" + key, material[key] == 0)
    check("runtime_forbidden_guard_zero", all(value == 0 for value in guards["forbidden"].values()))
    fine = fine_classes(report)
    for name, passed in fine.items():
        check("fine_class:" + name, passed)
    rewrite = audit_requests(directory, members, top, check)
    check(
        "manifest_unchanged_after_audit",
        sha((directory / "manifest.json").read_bytes()) == manifest_hash_before,
    )
    check(
        "controls_unchanged_after_audit",
        sha((directory / "controls/report.json").read_bytes()) == report_hash_before,
    )
    check(
        "no_tokenizer_import_or_model_load",
        "transformers" not in sys.modules
        and "tokenizers" not in sys.modules
        and "torch" not in sys.modules,
    )
    return {
        "schema_version": "catalog_bridge_readonly_worker_audit_reproduction.v1",
        "audited_utc": datetime.now(timezone.utc).isoformat(),
        "status": "PASS_AS_SCOPED" if not audit.failures else "DEFECTS_FOUND",
        "check_count": audit.count,
        "failure_count": len(audit.failures),
        "failures": audit.failures,
        "production_commit": frozen["git_commit"],
        "audited_directory": ARTIFACT,
        "manifest_id": manifest["id"],
        "manifest_sha256": manifest_hash_before,
        "controls_report_sha256": report_hash_before,
        "manifest_member_count": len(members),
        "manifest_member_bytes": sum(m["bytes"] for m in members.values()),
        "frozen_code_files_checked": len(frozen["code"]),
        "sessions": session_rows,
        "actual_method_counts": dict(method_counts),
        "event_counts": dict(event_counts),
        "fine_class_checks": fine,
        "material_summary": {
            "packages": len(packages),
            "rows": len(candidates),
            "target_tokens": total_target,
            "sequence_tokens": total_sequence,
            "minimum_sequence_length": min(lengths),
            "maximum_sequence_length": max(lengths),
            "policy_cap": 24576,
            "model_context": 32768,
            "reported_production_tokenizer_loads": 1,
            "audit_tokenizer_model_GPU_calls": 0,
            "token_to_text_decode_rerun": False,
        },
        "rewrite_summary": rewrite,
        "scope_limits": [
            "Replays frozen evaluator; not an external independent financial semantics audit.",
            "Checks are assertion evaluations, not independent samples or tests.",
            "Token arrays/masks and original rendering checked without tokenizer decoding.",
            "Single production tokenizer construction supported by code path; "
            "not an independent dynamic counter.",
            "Stored execution guards are not OS isolation "
            "or a survey of unrelated server activity.",
            "Evaluation panel financial/period semantics OUT OF SCOPE; "
            "this PASS cannot remove any panel admission blocker.",
            "Old development 9263 target tokens, 49152 cap and four constructions "
            "are not final-stage evidence.",
        ],
    }


def fine_classes(report):
    assessments = {a["session_id"]: a for a in report["assessments"]}
    rows = report["rows"]
    named = {row["name"]: assessments[row["session_id"]] for row in rows}
    plain = named["fine_class_equivalent_spelling"]
    equivalent = [
        assessments[row["session_id"]]
        for row in rows
        if row["name"] == "equivalent_endpoint_with_movement_request"
        and row["task_id"] == plain["task_id"]
    ]
    repeat = named["fine_class_redundant_recomputation"]
    revision = named["fine_class_substantive_revision"]
    reorder = named["fine_class_source_execution_order"]
    alternate = named["alternative_basis_cross_check_keeps_endpoint_final_method"]
    return {
        "equivalent_spelling_same_complete_class": len(equivalent) == 1
        and equivalent[0]["full_class"] == plain["full_class"],
        "requested_basis_not_method": all(
            row["actual_method"] == "endpoint"
            for row in rows
            if row["name"] == "equivalent_endpoint_with_movement_request"
            and row["family"] != "control"
        )
        and all(
            row["actual_method"] == "movement"
            for row in rows
            if row["name"] == "equivalent_movement_with_endpoint_request"
        ),
        "repeat_distinct_class": repeat["actual_method"] == plain["actual_method"] == "endpoint"
        and repeat["full_class"] != plain["full_class"],
        "repeat_not_independent_source_claim": len(repeat["full_signature"]["target_cross_checks"])
        == 1
        and repeat["full_signature"]["target_cross_checks"][0]["kind"]
        == "redundant_target_recomputation",
        "substantive_revision_retained": revision["actual_method"] == "endpoint"
        and revision["full_class"] not in {plain["full_class"], repeat["full_class"]}
        and revision["full_signature"]["revision_edges"]
        == [
            {
                "from_result_id": "tool:3",
                "to_result_id": "tool:4",
                "substantive_program_change": True,
                "revised_result_supports_first_final": True,
            }
        ],
        "source_execution_order_preserved": reorder["full_class"] != plain["full_class"]
        and reorder["full_signature"]["final_support_program"]
        == plain["full_signature"]["final_support_program"],
        "alternative_basis_not_final_method": alternate["actual_method"] == "endpoint"
        and len(alternate["full_signature"]["target_cross_checks"]) == 1
        and alternate["full_signature"]["target_cross_checks"][0]["kind"]
        == "alternative_basis_target_cross_check",
    }


def audit_requests(directory, members, top, check):
    inc = directory / "incremental"
    ledger = read(inc / "rewrite_budget_ledger.json")
    reservations = {r["request_id"]: r for r in ledger["reservations"]}
    directories = sorted(path for path in (inc / "rewrite_requests").iterdir() if path.is_dir())
    check(
        "rewrite_15_unique",
        len(reservations)
        == len(directories)
        == ledger["request_reservations"]
        == ledger["sent_request_count"]
        == 15
        and {p.name for p in directories} == set(reservations),
    )
    new_tasks = {row["task_id"] for row in read(inc / "catalog.json")["tasks"]}
    totals, attempts, request_rows = Counter(), Counter(), []
    for path in directories:
        request = read(path / "request.json")
        receipt = read(path / "receipt.json")
        response = read(path / "raw_response.json")
        reservation = reservations[path.name]
        body = request["body"]
        envelope = json.loads(response["body_utf8"])
        usage, telemetry = envelope["usage"], receipt["telemetry"]
        check(
            "rewrite_request_joins:" + path.name,
            request["request_id"] == receipt["request_id"] == response["request_id"] == path.name
            and request["task_id"] == reservation["task_id"]
            and request["task_id"] in new_tasks
            and request["attempt"] == reservation["attempt"],
        )
        reconstructed = json.dumps(source_order_body(body), ensure_ascii=False).encode()
        check(
            "rewrite_body_source_order_hash:" + path.name,
            sha(reconstructed) == request["raw_body_sha256"],
        )
        check(
            "rewrite_response_hash:" + path.name,
            response["received_body_sha256"] == sha(response["body_utf8"].encode()),
        )
        check(
            "rewrite_envelope:" + path.name,
            response["http_status"] == 200
            and envelope["object"] == "chat.completion"
            and envelope["model"] == body["model"] == "deepseek-flash"
            and len(envelope["choices"]) == 1
            and envelope["choices"][0]["finish_reason"] == "stop",
        )
        check(
            "rewrite_fixed_condition:" + path.name,
            body["thinking"] == {"type": "disabled"}
            and body["stream"] is False
            and body["max_tokens"] == 1536
            and "temperature" not in body
            and "top_p" not in body
            and request["private_answers_or_basis_roles_supplied"] is False,
        )
        check(
            "rewrite_not_teacher:" + path.name,
            request["purpose"]
            == receipt["purpose"]
            == ledger["policy"]["purpose"]
            == "question_rewrite"
            and request["automatic_model_discovery"] is False
            and request["fallback_models"] == [],
        )
        amount = usage["prompt_tokens"] + usage["completion_tokens"]
        check(
            "rewrite_usage_three_way:" + path.name,
            usage["total_tokens"]
            == amount
            == telemetry["total_tokens"]
            == reservation["charged_tokens"]
            and usage["prompt_tokens"] == telemetry["prompt_tokens"] == reservation["prompt_tokens"]
            and usage["completion_tokens"]
            == telemetry["completion_tokens"]
            == reservation["completion_tokens"],
        )
        check(
            "rewrite_settled_within_reserve:" + path.name,
            reservation["state"] == "settled"
            and reservation["reserved_tokens"] == request["reserved_tokens"] == 9728
            and amount <= 9728
            and reservation["http_success"] == 1,
        )
        totals.update(
            prompt=usage["prompt_tokens"], completion=usage["completion_tokens"], total=amount
        )
        attempts[reservation["attempt"]] += 1
        request_rows.append(
            {
                "request_id": path.name,
                "task_id": reservation["task_id"],
                "attempt": reservation["attempt"],
                "prompt_tokens": usage["prompt_tokens"],
                "completion_tokens": usage["completion_tokens"],
                "total_tokens": amount,
                "reconstructed_request_sha256": sha(reconstructed),
                "raw_response_sha256": response["received_body_sha256"],
            }
        )
    check(
        "rewrite_request_population",
        len(new_tasks) == len({r["task_id"] for r in reservations.values()}) == 10
        and attempts == {1: 10, 2: 5},
    )
    check(
        "rewrite_usage_totals",
        totals == {"prompt": 8480, "completion": 1720, "total": 10200}
        and totals["prompt"] == ledger["known_prompt_tokens"]
        and totals["completion"] == ledger["known_completion_tokens"]
        and totals["total"] == ledger["conservative_charged_tokens"],
    )
    check(
        "rewrite_no_breach_unsettled",
        ledger["budget_breach_count"] == ledger["unsettled_or_unknown_count"] == 0
        and ledger["http_success_count"] == 15,
    )
    check(
        "common_allowance_not_reset",
        ledger["previous_registered_debit"] == 211338
        and ledger["cumulative_conservative_debit"] == top["known_cumulative_token_debit"] == 221538
        and ledger["remaining_registered_global_allowance"] == 1000000000 - 221538 == 999778462,
    )
    check(
        "rewrite_manifest_request_files",
        all(
            f"incremental/rewrite_requests/{p.name}/{name}" in members
            for p in directories
            for name in ("request.json", "receipt.json", "raw_response.json")
        ),
    )
    return {
        "requests": 15,
        "tasks": 10,
        "initial": attempts[1],
        "repair": attempts[2],
        "usage": dict(totals),
        "cumulative_debit": ledger["cumulative_conservative_debit"],
        "remaining_allowance": ledger["remaining_registered_global_allowance"],
        "rows": request_rows,
        "raw_request_wire_bytes_separately_saved": False,
        "request_byte_hash_verified_by_frozen_serializer_reconstruction": True,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    arguments = parser.parse_args()
    result = audit(arguments.root)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
    return 0 if result["status"] == "PASS_AS_SCOPED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
