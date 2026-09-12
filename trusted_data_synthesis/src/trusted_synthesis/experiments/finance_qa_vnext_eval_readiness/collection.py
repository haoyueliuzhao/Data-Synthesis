"""One fully registered A/B collection; no pilot, adaptive quota stop, or top-up."""

import json
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from ..finance_qa_vnext_task_build.archive import require, write_json
from . import training_assessment, training_runtime


def policy():
    return training_runtime.record(
        "fixed_collection_policy",
        pools=["A", "B"],
        dual_replicates_per_guidance=32,
        control_replicates=24,
        max_responses=32,
        max_tools=32,
        workers=8,
        session_registration="every pool/task/guidance/replicate before the first response",
        generation_order=(
            "registered pool/task/basis/replicate order; up to eight concurrent sessions"
        ),
        early_eight_package_stop=False,
        Teacher_success_ranking=False,
        ordinary_transport_failure=(
            "terminal for that session, retained denominator; next registered session"
        ),
        global_budget_or_model_contract_stop=(
            "retain entire unfinished registry; no population selection"
        ),
        tokenizer_calls_during_collection=0,
        Student_calls=0,
    )


def _validate_registration(tasks, sessions):
    expected = set()
    for task in tasks:
        bases = ("control",) if task["family"] == "control" else ("endpoint", "movement")
        for pool in ("A", "B"):
            for basis in bases:
                for replicate in range(24 if basis == "control" else 32):
                    expected.add((task["task_id"], pool, basis, replicate))
    actual = {(row["task_id"], row["pool"], row["basis"], row["replicate"]) for row in sessions}
    require(
        actual == expected and len(actual) == len(sessions),
        "collection.complete_fixed_session_registry",
    )
    require(
        all(row["state"] == "registered" for row in sessions),
        "collection.new_run_no_partial_replay",
    )


def run(
    root,
    output,
    ledger,
    public_catalog,
    offline_catalog,
    provider_factory,
    *,
    gate_id,
    receipt_verifier,
    workers=8,
):
    """Execute only already registered sessions after a separately validated gate.

    ``provider_factory`` receives one registered session identity, never its private
    bundle. The private reader is first invoked after the online session returns.
    """
    root, output = Path(root).resolve(), Path(output).resolve()
    require(output.is_relative_to(root) and not output.exists(), "collection.new_contained_output")
    require(
        type(workers) is int and workers == policy()["workers"], "collection.frozen_parallelism"
    )
    require(
        callable(provider_factory) and callable(receipt_verifier),
        "collection.explicit_live_transport_and_receipt_verifier",
    )
    with ledger.connection() as db:
        row = db.execute("SELECT value FROM metadata WHERE key='collection_gate'").fetchone()
    require(row is not None, "collection.formal_gate_registered")
    gate = json.loads(row[0])
    require(
        gate["id"] == gate_id and gate["status"] == "READY_FOR_FIXED_COLLECTION",
        "collection.exact_admission_gate",
    )
    sessions = ledger.sessions()
    tasks = list(public_catalog.tasks.values())
    _validate_registration(tasks, sessions)
    output.mkdir(parents=True)
    write_json(output / "policy.json", policy())
    write_json(output / "registered_sessions.json", sessions)
    write_json(output / "admission_gate.json", gate)
    stop = threading.Event()
    failures, results = [], []

    def one(registered):
        if stop.is_set():
            return None
        envelope = public_catalog.public_envelope(registered["task_id"])
        actual_provider = provider_factory(registered)

        def guarded_provider(messages, context):
            if stop.is_set():
                raise training_runtime.FatalStudyError("collection.stopped_before_next_request")
            try:
                return actual_provider(messages, context)
            except Exception as error:
                if training_runtime.global_failure(error):
                    stop.set()
                raise

        session = training_runtime.generate(
            envelope["messages"],
            envelope["identity"],
            provider=guarded_provider,
            session_id=registered["session_id"],
            requested_basis=registered["basis"],
        )
        directory = output / "sessions" / registered["session_id"]
        write_json(directory / "session.json", session)
        if session["global_fatal"]:
            stop.set()
        try:
            origin = receipt_verifier(session, ledger)
        except (ValueError, KeyError, TypeError, OSError) as error:
            origin = {
                "status": "ORIGIN_NOT_VERIFIED",
                "session_id": registered["session_id"],
                "reason": str(error),
                "callback_self_attestation_accepted": False,
            }
        # Separate capability boundary: this bundle never enters provider messages.
        fixture = offline_catalog.fixture(registered["task_id"], public_catalog)
        require(
            fixture["messages"] == envelope["messages"]
            and fixture["identity"] == envelope["identity"],
            "collection.original_public_identity_unchanged",
        )
        qualification = training_assessment.assess_session(
            session,
            fixture["bundle"],
            fixture["native_bindings"],
            origin_evidence=origin,
        )
        write_json(directory / "qualification.json", qualification)
        if not session["global_fatal"]:
            ledger.finish_session(registered["session_id"], session["terminal"])
        return training_runtime.record(
            "collected_original_session",
            registered_session=registered,
            session_id=session["id"],
            qualification_id=qualification["id"],
            session_path=str((directory / "session.json").relative_to(root)),
            qualification_path=str((directory / "qualification.json").relative_to(root)),
            terminal=session["terminal"],
            global_fatal=session["global_fatal"],
            financial_valid=qualification["financial_valid"],
            full_mapping_status=qualification["full_mapping_status"],
            actual_method=qualification["actual_method"],
            representation_eligible=qualification["representation_eligible"],
        )

    with ThreadPoolExecutor(max_workers=workers) as executor:
        pending = {executor.submit(one, row): row for row in sessions}
        for future in as_completed(pending):
            registered = pending[future]
            try:
                result = future.result()
                if result is not None:
                    results.append(result)
            except Exception as error:
                stop.set()
                failures.append(
                    {
                        "registered_session_id": registered["session_id"],
                        "phase": "collection_or_offline_integrity_failure",
                        "type": type(error).__name__,
                        "reason": str(error),
                    }
                )
    rank = {row["session_id"]: index for index, row in enumerate(sessions)}
    results.sort(key=lambda row: rank[row["registered_session"]["session_id"]])
    final_sessions = ledger.sessions()
    complete = (
        not stop.is_set()
        and len(results) == len(sessions)
        and all(row["state"] == "finished" for row in final_sessions)
    )
    write_json(output / "session_results.json", results)
    write_json(output / "final_session_registry.json", final_sessions)
    write_json(output / "collection_failures.json", failures)
    write_json(output / "budget_after_collection.json", ledger.snapshot())
    report = training_runtime.record(
        "fixed_collection_report",
        status="COMPLETE_FIXED_COLLECTION" if complete else "INCOMPLETE_FIXED_COLLECTION_STOP",
        collection_complete=complete,
        admission_gate_id=gate_id,
        policy_id=policy()["id"],
        registered_session_count=len(sessions),
        source_task_order=[
            {"task_id": task["task_id"], "family": task["family"]} for task in tasks
        ],
        recorded_session_count=len(results),
        finished_session_count=sum(row["state"] == "finished" for row in final_sessions),
        financially_valid_sessions=sum(row["financial_valid"] for row in results),
        representation_eligible_sessions=sum(row["representation_eligible"] for row in results),
        all_registered_denominators_preserved=True,
        original_package_consumer_registered=True,
        population_selection_allowed=complete,
        training_population_selected=False,
        tokenizer_loads=0,
        Student_sessions=0,
        GPU_operations=0,
    )
    write_json(output / "report.json", report)
    return report
