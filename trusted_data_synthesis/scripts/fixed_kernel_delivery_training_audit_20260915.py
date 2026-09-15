"""Bounded, train-only contract/mask audit; never loads a tokenizer or Student.

One task per target family is selected from public population metadata before
opening any original. The first A/train cache session for that task is used
without replacement. Only those three original packages and their mmap slices
are inspected. Public Probe prefixes are conditional tests, not autonomous
Student trajectories or private answers.
"""

import argparse
import copy
import hashlib
import json
import subprocess
from collections import Counter
from pathlib import Path

import numpy as np

from trusted_synthesis.experiments.finance_qa_vnext_fixed_kernel_value import protocol as p

OUTPUT = Path(
    "trusted_data_synthesis/artifacts/qa_vnext_fixed_kernel_value/delivery_diagnostic_20260915/stage_B"
)
PARENT = Path(
    "trusted_data_synthesis/artifacts/qa_vnext_fixed_kernel_value/parallel_tail_execution_20260914"
)
SCRIPT = Path("trusted_data_synthesis/scripts/fixed_kernel_delivery_training_audit_20260915.py")
SALT = "delivery_diagnostic_20260915_stage_B_public_training_metadata_v1"
FAMILIES = ("annual_flow", "stock_rollforward", "company_defined_metric")
SOURCE_FILES = {
    "material_runtime": "finance_qa_vnext_fixed_kernel_value/runtime.py",
    "material_tools": "finance_qa_vnext_catalog_bridge/worker.py",
    "evaluation_runtime": "finance_qa_vnext_eval_readiness/runtime.py",
    "evaluation_decoder": "finance_qa_vnext_fixed_kernel_value/evaluation.py",
    "original_representation": "finance_qa_vnext_model_execution/representation.py",
    "trajectory_fusion": "finance_qa_vnext_fixed_kernel_value/trajectory_materials.py",
    "trajectory_consumer": "finance_qa_vnext_fixed_kernel_value/trajectory_consumer.py",
}


def read(path):
    return json.loads(Path(path).read_bytes())


def choose_tasks(population):
    """No performance, raw output, method, loss or private bundle fields used."""
    selected = []
    for family in FAMILIES:
        candidates = [row for row in population["tasks"] if row["family"] == family]
        p.require(bool(candidates), "delivery.audit_target_family_present")
        rank = lambda row, family=family: hashlib.sha256(  # noqa: E731
            (SALT + "|" + family + "|" + row["task_id"]).encode()
        ).hexdigest()
        row = min(candidates, key=lambda item: (rank(item), item["task_id"]))
        selected.append(
            {
                "task_id": row["task_id"],
                "family": family,
                "selection_digest": rank(row),
                "candidate_count": len(candidates),
                "public_messages_sha256": row["public_messages_sha256"],
                "surface_version_id": row["surface_version_id"],
            }
        )
    return selected


def choose_packages(tasks, index):
    selected = []
    for task in tasks:
        candidates = [
            row
            for row in index["packages"]
            if row["task_id"] == task["task_id"] and row["pool"] == "A" and row["role"] == "train"
        ]
        p.require(bool(candidates), "delivery.preselected_task_has_A_train_package")
        package = min(candidates, key=lambda row: row["session_id"])
        selected.append({"task": task, "package": package})
    return selected


def audit_rows(original, metadata, inputs, target_positions):
    """Compare actual selected cache slices; do not rebuild or re-tokenize."""
    p.require(
        original["role"] == metadata["role"] == "train"
        and original["pool"] == metadata["pool"] == "A"
        and original["id"] == metadata["package_id"]
        and original["task_id"] == metadata["task_id"]
        and original["registered_session_id"] == metadata["session_id"],
        "delivery.exact_selected_train_package",
    )
    segments = []
    for segment in metadata["segments"]:
        ids = np.asarray(
            inputs[segment["input_offset"] : segment["input_offset"] + segment["input_length"]]
        )
        targets = np.asarray(
            target_positions[
                segment["target_offset"] : segment["target_offset"] + segment["target_count"]
            ]
        )
        p.require(
            ids.ndim == targets.ndim == 1
            and len(targets) > 0
            and int(targets.min()) > 0
            and int(targets.max()) < len(ids),
            "delivery.local_cache_bounds",
        )
        segments.append((segment, ids, targets))
    row_results, union = [], []
    for row in original["rows"]:
        candidate, representation = row["candidate"], row["representation"]
        ids = np.asarray(representation["input_ids"], dtype=np.int32)
        mask = np.asarray(representation["target_mask"], dtype=np.int32)
        labels = np.asarray(representation["labels"], dtype=np.int32)
        positions = np.flatnonzero(mask).astype(np.int32)
        p.require(
            len(ids) == len(mask) == len(labels) == representation["sequence_length"]
            and len(positions) == representation["target_token_count"] > 0
            and set(mask.tolist()) <= {0, 1}
            and int(positions[0]) > 0
            and np.array_equal(labels, np.where(mask, ids, -100))
            and representation["causal_shift"] == 1
            and representation["causal_target_token_start"] == int(positions[0]) - 1
            and representation["causal_target_token_end"] == int(positions[-1])
            and representation["target_token_start"] == int(positions[0])
            and representation["target_token_end"] == int(positions[-1]) + 1
            and candidate["target_raw_sha256"] == p.sha(candidate["target_text"])
            and candidate["target_raw_sha256"] == representation["target_raw_sha256"]
            and candidate["public_runtime_state_id"]
            == "history:" + p.sha(p.encode(candidate["messages"])),
            "delivery.original_mask_labels_public_bytes_and_causal_shift",
        )
        matching = [
            (meta, fused_ids, fused_positions)
            for meta, fused_ids, fused_positions in segments
            if candidate["response_index"] in meta["source_response_indices"]
        ]
        p.require(len(matching) == 1, "delivery.one_original_response_segment")
        _, fused_ids, fused_positions = matching[0]
        p.require(
            len(ids) <= len(fused_ids)
            and np.array_equal(ids, fused_ids[: len(ids)])
            and np.all(np.isin(positions, fused_positions))
            and np.array_equal(ids[positions], fused_ids[positions]),
            "delivery.actual_original_sequence_and_all_targets_retained",
        )
        union.extend(positions.tolist())
        row_results.append(
            {
                "candidate_id": candidate["id"],
                "response_index": candidate["response_index"],
                "response_kind": candidate["response_kind"],
                "target_count": len(positions),
                "target_token_start": int(positions[0]),
                "target_token_end_exclusive": int(positions[-1]) + 1,
                "causal_logit_start": int(positions[0]) - 1,
                "causal_logit_end_exclusive": int(positions[-1]),
                "actual_cache_targets_retained": True,
                "original_labels_equal_actual_token_ids": True,
                "public_runtime_state_id": candidate["public_runtime_state_id"],
                "target_raw_sha256": candidate["target_raw_sha256"],
                "original_public_response_object": json.loads(candidate["target_text"]),
                "no_retokenization_performed": True,
            }
        )
    if metadata["fused"]:
        p.require(
            len(segments) == 1
            and len(set(union)) == len(union)
            and np.array_equal(np.sort(union), segments[0][2]),
            "delivery.exact_union_no_missing_added_or_deduplicated_targets",
        )
    p.require(
        sum(row["target_count"] for row in row_results)
        == original["whole_package_target_tokens"]
        == metadata["whole_package_target_tokens"],
        "delivery.selected_package_target_count_unchanged",
    )
    return row_results


def choose_boundaries(original):
    """Prefer the final-referenced calculation; otherwise label operator-only."""
    finals = [
        row["candidate"] for row in original["rows"] if row["candidate"]["response_kind"] == "Final"
    ]
    calculations = [
        row["candidate"]
        for row in original["rows"]
        if row["candidate"]["response_kind"] == "calculate"
    ]
    final = min(finals, key=lambda row: row["response_index"]) if finals else None
    calculation = min(calculations, key=lambda row: row["response_index"]) if calculations else None
    direct_final_dependency = False
    if final is not None:
        payload = json.loads(final["target_text"])
        result_id = payload.get("final", {}).get("result_id")
        response_index = -1
        for message in final["messages"]:
            if message["role"] == "assistant":
                response_index += 1
            if message["role"] != "user":
                continue
            try:
                body = json.loads(message["content"])
            except (json.JSONDecodeError, TypeError):
                continue
            observation = body.get("tool_observation", {}) if isinstance(body, dict) else {}
            if (
                observation.get("call_id") == result_id
                and observation.get("tool") == "calculate"
                and observation.get("status") == "ok"
            ):
                candidates = [
                    row for row in calculations if row["response_index"] == response_index
                ]
                p.require(len(candidates) == 1, "delivery.public_final_calculation_candidate_join")
                calculation, direct_final_dependency = candidates[0], True
    return [("calculate", calculation, direct_final_dependency), ("Final", final, True)]


def public_prefix(
    candidate, task, package, *, direct_final_dependency=False, source_reference=None
):
    """Target stays offline; input_messages are only the exact public history."""
    p.require(
        candidate["response_kind"] in {"calculate", "Final"}
        and candidate["role"] == "train"
        and candidate["pool"] == "A",
        "delivery.public_train_prefix_kind",
    )
    messages = copy.deepcopy(candidate["messages"])
    p.require(
        all(set(message) == {"role", "content"} for message in messages)
        and messages[0]["role"] == "system"
        and p.sha(p.encode(messages)) == candidate["public_runtime_state_id"].split(":", 1)[1],
        "delivery.exact_native_public_history",
    )
    return p.record(
        "delivery_public_training_prefix",
        task_id=task["task_id"],
        family=task["family"],
        prefix_kind="before_" + candidate["response_kind"].lower(),
        input_messages=messages,
        public_runtime_state_id=candidate["public_runtime_state_id"],
        reference_response=candidate["target_text"],
        reference_response_sha256=candidate["target_raw_sha256"],
        reference_response_is_Probe_public_output_not_private_gold=True,
        reference_response_is_offline_only_never_sent_to_Student=True,
        boundary=candidate["response_kind"].lower(),
        direct_final_result_calculation=(
            direct_final_dependency if candidate["response_kind"] == "calculate" else None
        ),
        diagnostic_scope=(
            "direct_Final_dependency_calculation"
            if direct_final_dependency
            else "operator_only_not_claimed_sufficient_for_task"
        )
        if candidate["response_kind"] == "calculate"
        else "delivery_after_original_public_Probe_history",
        source_reference=source_reference,
        source_candidate_id=candidate["id"],
        source_package_id=package["package_id"],
        registered_session_id=package["session_id"],
        original_response_index=candidate["response_index"],
        role="train",
        pool="A",
        original_public_history_retained=True,
        target_response_not_in_input_messages=True,
        private_bundle_opened=False,
        conditional_continuation_is_autonomous_success=False,
        supplied_Probe_history_is_Student_capability=False,
    )


def contract_ledger(root):
    source_root = root / "trusted_data_synthesis/src/trusted_synthesis/experiments"
    sources = {
        name: {
            "path": str((source_root / path).relative_to(root)),
            "sha256": p.sha(source_root / path),
        }
        for name, path in SOURCE_FILES.items()
    }
    return p.record(
        "delivery_training_evaluation_contract",
        source_files=sources,
        training={
            "optimizer_mode": (
                "offline supervised public Probe response targets; "
                "no online Student tools or reward updates"
            ),
            "runtime_successful_dispatch": ["read_source", "calculate"],
            "other_tool_dispatch": "tool.unknown_tool",
            "read_source_arguments": ["source_id", "cells", "unit"],
            "JSON_source": (
                "specific record and native_pointer already public; source_id reads that record"
            ),
            "table_source": "original_rows public; cells select adjacent same-row amount",
            "source_units_and_output_units": (
                "read_source uses source unit or explicit compatible unit conversion"
            ),
            "coverage_claim": (
                "dispatch capability plus three sampled train originals, "
                "not a full success-frequency audit"
            ),
        },
        evaluation={
            "agent_framework": "project-owned public-only runtime with actual local-model callback",
            "loop": [
                "bound base plus final LoRA adapter generates JSON",
                "runtime parses tool or Final",
                "execute public snapshot tool",
                "append observation to next model history",
                "first lowercase top-level final or registered limit stops",
            ],
            "successful_dispatch": [
                "query_source",
                "list_concepts",
                "read_json",
                "read_source",
                "calculate",
                "select_max",
                "compare",
                "lookup_selected",
            ],
            "query_concept": "exact namespace:tag",
            "query_unit": "exact native snapshot unit",
            "query_label_contains": (
                "case-insensitive substring of tag/label/description, not record date"
            ),
            "query_start_end": "exact original record start/end fields",
            "read_source_arguments": ["source_id", "native_pointer", "unit"],
            "native_pointer": (
                "public API returns original pointers; Student must identify the record"
            ),
            "complete_snapshot_not_training_selected_records": True,
            "financial_assessment_returned_online": False,
        },
        observed_contract_difference_is_an_implementation_bug_by_itself=False,
        target_mask_policy=(
            "original response text supervised; "
            "EOS and template suffix excluded by registered encoder"
        ),
        EOS_policy_is_newly_proven_failure_cause=False,
        causal_consumer="target_ids=input_ids[target_positions]; logits_to_keep=target_positions-1",
        API_calls=0,
        GPU_loads=0,
        private_or_sealed_material_opened=False,
    )


def prior_model_receipts(root, freeze):
    rows = []
    for arm in ("alpha0", "plus", "minus"):
        for seed in (11, 29, 47):
            key = f"A_{arm}_{seed}"
            directory = root / PARENT / "generation/dev" / key
            receipt = read(directory / "model_load_receipt.json")
            identity = read(directory / "model_identity.json")
            decoder = read(directory / "decoder_config.json")
            matched = (
                receipt["execution_kind"] == "actual_local_model"
                and receipt["restored_checkpoint_id"] == identity["checkpoint_id"]
                and receipt["model_identity_id"] == identity["id"]
                and receipt["final_adapter_loads"] == 1
                and receipt["base_binding_id"] == freeze["base_binding"]["id"]
                and receipt["tokenizer_binding_id"] == freeze["tokenizer_binding"]["id"]
                and decoder["chat_template_sha256"]
                == freeze["tokenizer_binding"]["chat_template_sha256"]
            )
            rows.append(
                {
                    "model": key,
                    "receipt_id": receipt["id"],
                    "restored_checkpoint_id": receipt["restored_checkpoint_id"],
                    "existing_restoration_and_template_bindings_match": matched,
                }
            )
    return {
        "rows": rows,
        "all_match": all(row["existing_restoration_and_template_bindings_match"] for row in rows),
        "scope": "existing actual restore receipts; no new model restore or base shard SHA",
    }


def run(root):
    root = Path(root).resolve()
    output = root / OUTPUT
    p.require(not output.exists(), "delivery.stage_B_once_new_output_only")
    freeze = read(root / PARENT / "preparation/execution_freeze.json")
    input_root = Path(freeze["input_root"])
    population_path = input_root / freeze["input_files"]["population"]["path"]
    population = read(population_path)
    cache = root / freeze["trajectory_cache"]["cache_root"] / "A"
    index = read(cache / "packages.json")
    chosen = choose_packages(choose_tasks(population), index)
    source_head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    committed_script = subprocess.check_output(["git", "show", f"HEAD:{SCRIPT}"], cwd=root)
    p.require(
        committed_script == (root / SCRIPT).read_bytes(),
        "delivery.committed_audit_script_before_execution",
    )
    selection = p.record(
        "delivery_stage_B_freeze",
        source_commit=source_head,
        script_sha256=p.sha(committed_script),
        parent_execution_freeze_id=freeze["id"],
        population_id=population["id"],
        population_sha256=p.sha(population_path),
        pool_index_id=index["id"],
        trajectory_cache_id=freeze["trajectory_cache"]["manifest_id"],
        task_selection_salt=SALT,
        task_selection="minimum SHA256(salt|family|task_id)",
        package_selection=(
            "lexicographically first session_id among already admitted A/train packages; "
            "no replacement"
        ),
        selected=chosen,
        chosen_before_opening_original_packages=True,
        if_calculate_or_Final_missing="report insufficiency; never select another package or task",
        no_sealed_or_private_bundle_access=True,
        maximum_original_packages=3,
        API_calls=0,
        tokenizer_calls=0,
        Student_loads=0,
    )
    output.mkdir(parents=True)
    p.write_once(output / "freeze.json", selection)
    contracts = contract_ledger(root)
    p.write_once(output / "contract_ledger.json", contracts)
    materialization_path = input_root / freeze["input_files"]["materialization_index"]["path"]
    materialization = read(materialization_path)
    entries = {
        row["registered_session_id"]: row
        for row in materialization["entries"]
        if row["role"] == "train" and row["consumable"]
    }
    inputs = np.load(cache / "input_ids.npy", mmap_mode="r", allow_pickle=False)
    targets = np.load(cache / "target_positions.npy", mmap_mode="r", allow_pickle=False)
    audits, prefixes = [], []
    for item in chosen:
        task, metadata = item["task"], item["package"]
        entry = entries[metadata["session_id"]]
        reference = entry["package"]
        path = materialization_path.parent / reference["path"]
        p.require(
            path.resolve().is_relative_to(materialization_path.parent.resolve()),
            "delivery.original_package_in_registered_material_directory",
        )
        raw = path.read_bytes()
        p.require(
            p.sha(raw) == reference["sha256"] == metadata["original_package_sha256"],
            "delivery.only_selected_original_package_SHA",
        )
        original = json.loads(raw)
        rows = audit_rows(original, metadata, inputs, targets)
        selected_prefixes = []
        missing = []
        for kind, candidate, direct_dependency in choose_boundaries(original):
            if candidate is None:
                missing.append(kind)
                continue
            prefix = public_prefix(
                candidate,
                task,
                metadata,
                direct_final_dependency=direct_dependency,
                source_reference={"path": str(path), "sha256": reference["sha256"]},
            )
            prefix_path = Path("prefixes") / f"{task['family']}_{prefix['prefix_kind']}.json"
            (output / "prefixes").mkdir(exist_ok=True)
            p.write_once(output / prefix_path, prefix)
            summary = {
                "id": prefix["id"],
                "path": str(OUTPUT / prefix_path),
                "task_id": task["task_id"],
                "family": task["family"],
                "prefix_kind": prefix["prefix_kind"],
                "public_runtime_state_id": prefix["public_runtime_state_id"],
            }
            prefixes.append(summary)
            selected_prefixes.append(summary)
        audits.append(
            {
                "task": task,
                "package_id": metadata["package_id"],
                "registered_session_id": metadata["session_id"],
                "original_package_path": str(path),
                "original_package_sha256": p.sha(raw),
                "actual_method": metadata["method"],
                "fused": metadata["fused"],
                "rows": rows,
                "response_kind_counts": dict(Counter(row["response_kind"] for row in rows)),
                "prefixes": selected_prefixes,
                "missing_required_prefixes": missing,
                "all_original_targets_and_causal_shift_pass": True,
            }
        )
    receipts = prior_model_receipts(root, freeze)
    result = p.record(
        "delivery_stage_B_report",
        freeze_id=selection["id"],
        contract_ledger_id=contracts["id"],
        status="PASS_AS_SCOPED"
        if len(prefixes) == 6 and receipts["all_match"]
        else "INSUFFICIENT_OR_BINDING_FAILURE",
        audits=audits,
        public_prefixes=prefixes,
        existing_model_restore_evidence=receipts,
        full_7076_package_mask_audit_performed=False,
        numeric_arrays_fully_hashed=False,
        original_packages_opened=len(audits),
        sealed_packages_opened=0,
        private_bundles_opened=0,
        tokenizer_calls=0,
        GPU_loads=0,
        API_calls=0,
        direct_implementation_defect_detected=not receipts["all_match"],
        interface_migration_hypothesis=(
            "observed contract difference; not proof all no_Final share one mechanism"
        ),
        continuation_scope="provided public Probe histories only, never autonomous Student success",
        interpretation=(
            "three deterministic training tasks only; "
            "no claim all 7076 packages independently rechecked"
        ),
    )
    p.write_once(output / "report.json", result)
    return {
        "id": result["id"],
        "status": result["status"],
        "prefixes": len(prefixes),
        "output": str(output),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True)
    print(json.dumps(run(parser.parse_args().root), ensure_ascii=False))
