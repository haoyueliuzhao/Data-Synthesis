"""CPU-parallel encoding of the exact closed completion inventory.

Workers read original local references, load the frozen tokenizer at most once,
and store full arrays directly. Only compact references cross the process pipe.
No financial assessment, outcome selection, truncation, or GPU operation occurs.
The original serial materializer remains the baseline and the failed-gate path.
"""

from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from multiprocessing import get_context
from pathlib import Path

from . import materials as m
from . import protocol as p

_WORKER = None


def _load_item(row, output):
    return {
        key: m._read_reference(row[key], output) if row.get(key) else None
        for key in ("session", "qualification")
    }


def _initialize_worker(data_root, output, code_id, expected, loader, encoder):
    global _WORKER
    _WORKER = {
        "data_root": data_root,
        "output": output,
        "code_id": code_id,
        "expected": expected,
        "loader": loader,
        "encoder": encoder,
        "binding": None,
        "tokenizer": None,
    }


def _encode_job(job):
    registered, terminal, lineage_binding = job
    state = _WORKER
    item = _load_item(terminal, state["output"])
    session, qualification = item["session"], item["qualification"]
    p.require(
        session is not None and qualification is not None,
        "materials.finished_requires_session_and_qualification",
    )
    m._qualification(session, registered, qualification)
    m._assessor_code(session, registered, qualification, state["code_id"], lineage_binding)
    loads = 0
    if qualification["token_materialization_eligible"] and state["binding"] is None:
        state["binding"], state["tokenizer"] = state["loader"](state["data_root"])
        p.require(
            state["binding"] == state["expected"],
            "completion.parallel_frozen_tokenizer_binding",
        )
        loads = 1
    materialized = m.materialize_session(
        session,
        registered,
        qualification,
        state["binding"],
        state["tokenizer"],
        code_snapshot_id=state["code_id"],
        status=terminal["status"],
        encoder=state["encoder"],
        qualification_lineage_binding=lineage_binding,
    )
    outcome = materialized["outcome"]
    entry = m.store_materialized(materialized, state["output"])
    return {
        "entry": entry,
        "status": outcome["status"],
        "role": outcome["role"],
        "consumable": outcome["consumable"],
        "tokenizer_loads": loads,
    }


def materialize_all(
    registry,
    results,
    data_root,
    output,
    *,
    code_snapshot_id,
    qualification_lineage_bindings=None,
    collection_gate_passed=True,
    collection_gate_reason=None,
    workers=24,
    loader=m.load_local_tokenizer,
    encoder=m.encode_original_candidate,
):
    """Encode each registered slot once in order, returning a normal index.

    Optional loader/encoder callbacks are for small explicit CPU controls only.
    The production path checks each worker's actual tokenizer against the
    already frozen ``tokenizer_binding_preflight.json`` before its first encode.
    """
    p.require(
        type(workers) is int and 1 <= workers <= p.CPU_WORKERS,
        "completion.bounded_parallel_materialization_workers",
    )
    output = Path(output)
    p.checked(registry, "material_registry")
    sessions = registry["sessions"]
    p.require(
        len(sessions) == registry["session_count"] == p.SESSION_CAP,
        "materials.full_registered_denominator",
    )
    p.require(
        isinstance(results, list) and len(results) == len(sessions),
        "materials.all_terminal_rows_required_before_encoding",
    )
    by_session = {row["session_id"]: row for row in results}
    p.require(
        len(by_session) == len(sessions)
        and set(by_session) == {row["session_id"] for row in sessions},
        "materials.no_missing_duplicate_foreign_terminals",
    )
    bindings = {} if qualification_lineage_bindings is None else qualification_lineage_bindings
    p.require(
        isinstance(bindings, dict) and set(bindings) <= set(by_session),
        "materials.inherited_lineage_registered_slots_only",
    )
    for session_id, binding in bindings.items():
        p.checked(binding, "material_qualification_lineage_binding")
        p.require(
            binding["registered_session_id"] == session_id,
            "materials.inherited_lineage_slot_key",
        )
    for registered in sessions:
        m._registration(registered)
        p.require(
            registered["freeze_id"] == registry["freeze_id"],
            "materials.registry_freeze_join",
        )
        p.require(
            by_session[registered["session_id"]]["status"] in m.TERMINALS,
            "materials.all_terminal_statuses",
        )
    p.require(type(collection_gate_passed) is bool, "materials.explicit_external_collection_gate")
    complete = collection_gate_passed and all(row["status"] == "finished" for row in results)
    if not complete:
        # Preserve the old fail-closed semantics; no process or tokenizer starts.
        return m.materialize_all(
            registry,
            results,
            data_root,
            output,
            code_snapshot_id=code_snapshot_id,
            item_loader=lambda row: _load_item(row, output),
            qualification_lineage_bindings=bindings,
            collection_gate_passed=collection_gate_passed,
            collection_gate_reason=collection_gate_reason,
            loader=loader,
            encoder=encoder,
        )
    expected = p.read_json(output / "tokenizer_binding_preflight.json")
    if workers == 1:

        def frozen_loader(root):
            binding, tokenizer = loader(root)
            p.require(binding == expected, "completion.parallel_frozen_tokenizer_binding")
            return binding, tokenizer

        return m.materialize_all(
            registry,
            results,
            data_root,
            output,
            code_snapshot_id=code_snapshot_id,
            item_loader=lambda row: _load_item(row, output),
            qualification_lineage_bindings=bindings,
            collection_gate_passed=True,
            collection_gate_reason=collection_gate_reason,
            loader=frozen_loader,
            encoder=encoder,
        )
    jobs = (
        (registered, by_session[registered["session_id"]], bindings.get(registered["session_id"]))
        for registered in sessions
    )
    entries, counts, loads = [], Counter(), 0
    with ProcessPoolExecutor(
        max_workers=workers,
        mp_context=get_context("spawn"),
        initializer=_initialize_worker,
        initargs=(data_root, output, code_snapshot_id, expected, loader, encoder),
    ) as pool:
        for result in pool.map(_encode_job, jobs, chunksize=1):
            entries.append(result["entry"])
            counts[result["status"]] += 1
            counts["consumable_" + result["role"]] += int(result["consumable"])
            loads += result["tokenizer_loads"]
    if loads:
        p.write_once(output / "tokenizer_binding.json", expected)
    result = p.record(
        "materialization_index",
        registry_id=registry["id"],
        freeze_id=registry["freeze_id"],
        code_snapshot_id=code_snapshot_id,
        **(
            {
                "qualification_lineage_binding_ids": {
                    session_id: binding["id"] for session_id, binding in bindings.items()
                },
                "inherited_qualification_bytes_rewritten": False,
            }
            if bindings
            else {}
        ),
        complete_registered_denominator=len(sessions),
        collection_complete=True,
        collection_complete_is_admission_gate_not_raw_attempt_count=True,
        raw_registry_complete=True,
        generation_contract_passed=True,
        materialization_permitted=True,
        collection_gate_passed=True,
        collection_gate_reason=collection_gate_reason,
        status="COMPLETE_FIXED_MATERIALIZATION",
        entries=entries,
        counts=dict(counts),
        tokenizer_binding_id=expected["id"] if loads else None,
        tokenizer_loads=loads,
        maximum_sequence_length=p.SEQUENCE_CAP,
        all_valid_train_and_sealed_considered=True,
        token_arrays_repeated_in_index=False,
        scoring_or_top_k=False,
        role_reassignment=False,
        truncation=False,
        API_calls=0,
        GPU_operations=0,
        model_weight_loads=0,
        training_runs=0,
        CPU_encoding_workers=workers,
        worker_tokenizer_load_limit=1,
        token_arrays_transferred_between_processes=False,
        financial_semantics_reassessed=False,
    )
    p.write_once(output / "materialization_index.json", result)
    return result
