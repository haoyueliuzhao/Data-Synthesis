"""Authenticate and encode every eligible prospectively assigned original.

Only the existing tokenizer/encoder is used. A failed or overlength row fails
the whole package, but is retained. Positive targets are successful public tool
responses and the first Final; every original failed/format prefix remains in
their exact input histories. No ranking, top-k, role reassignment or GPU occurs.
"""

import json
from collections import Counter
from pathlib import Path

from ..finance_qa_vnext_catalog_bridge.materials import load_local_tokenizer
from ..finance_qa_vnext_model_execution.models import identity as representation_identity
from ..finance_qa_vnext_model_execution.representation import encode_original_candidate
from . import protocol as p
from . import runtime, transport
from .distribution import canonical_state_id
from .semantic_mapping import assess_new_semantics

TERMINALS = {"finished", "budget_aborted", "failed", "not_run"}


def _fields(row):
    return {key: value for key, value in row.items() if key not in {"id", "schema_version"}}


def _registration(registered):
    p.checked(registered, "session_registration")
    p.require(
        type(registered["replicate"]) is int
        and 0 <= registered["replicate"] < p.REPLICATES
        and registered["role"]
        == ("train" if registered["replicate"] < p.TRAIN_REPLICATES else "sealed")
        and registered["pool"] in p.POOLS,
        "materials.prospective_role_and_pool",
    )


def _session_join(session, registered):
    _registration(registered)
    p.checked(session, "material_session")
    p.require(
        session["registered_session"] == registered
        and session["registered_session_id"] == registered["session_id"]
        and session["identity"] == registered["identity"],
        "materials.original_session_registration_join",
    )


def assess_material(
    session,
    registered,
    fixture,
    *,
    ledger,
    transport_directory,
    code_snapshot_id,
    origin_verifier=transport.verify_origin,
):
    """Replay and authenticate from real receipts, then apply new offline rules.

    The verifier default is the real ledger/HTTP-chain implementation, not the
    callback's self-attestation. The injected hook exists for scripted controls.
    Source, qualification and session original files remain separate artifacts.
    """
    _session_join(session, registered)
    p.require(isinstance(code_snapshot_id, str) and code_snapshot_id, "materials.code_identity")
    p.require(
        session["identity"] == fixture["identity"]
        and session["public_messages"] == fixture["messages"],
        "materials.frozen_public_fixture",
    )
    runtime.replay(session)
    semantic = assess_new_semantics(session, fixture)
    try:
        origin = origin_verifier(session, ledger, transport_directory)
        p.checked(origin, "material_origin_verification")
        p.require(
            origin["session_id"] == session["id"]
            and origin["registered_session_id"] == registered["session_id"],
            "materials.origin_session_join",
        )
    except (ValueError, KeyError, TypeError, OSError) as error:
        origin = p.record(
            "material_origin_verification",
            session_id=session["id"],
            registered_session_id=registered["session_id"],
            status="ORIGIN_VERIFICATION_FAILED",
            error_type=type(error).__name__,
            reason=str(error),
            callback_self_attestation_accepted=False,
        )
    authentic = origin["status"] == "PASS_AUTHENTIC_MATERIAL_PUBLIC_CHAIN"
    mapped = semantic["full_mapping_status"] == "MAPPED" and semantic["full_class"] is not None
    allowed_methods = {"control"} if registered["family"] == "control" else {"endpoint", "movement"}
    eligible = bool(
        authentic
        and semantic["financial_valid"]
        and mapped
        and semantic["actual_method"] in allowed_methods
        and session["first_final_index"] is not None
    )
    return p.record(
        "material_qualification",
        session_id=session["id"],
        registered_session_id=registered["session_id"],
        registration_id=registered["id"],
        task_id=registered["task_id"],
        pool=registered["pool"],
        role=registered["role"],
        freeze_id=registered["freeze_id"],
        code_snapshot_id=code_snapshot_id,
        bundle_id=fixture["bundle"]["id"],
        source_boundary_id=fixture["source_boundary"]["id"],
        public_messages_sha256=registered["identity"]["public_messages_sha256"],
        semantic_assessment=semantic,
        origin_verification=origin,
        authentic_origin_verified=authentic,
        financial_valid=semantic["financial_valid"],
        full_class_valid=mapped,
        full_class=semantic["full_class"],
        actual_method=semantic["actual_method"],
        token_materialization_eligible=eligible,
        method_from_requested_basis=False,
        complete_original_replay=True,
        training_eligible=False,
        GPU_operations=0,
        model_weight_loads=0,
    )


def _qualification(session, registered, qualification):
    _session_join(session, registered)
    p.checked(qualification, "material_qualification")
    p.require(
        qualification["session_id"] == session["id"]
        and qualification["registered_session_id"] == registered["session_id"]
        and qualification["registration_id"] == registered["id"]
        and qualification["task_id"] == registered["task_id"]
        and qualification["pool"] == registered["pool"]
        and qualification["role"] == registered["role"],
        "materials.qualification_registered_role_join",
    )
    semantic = qualification["semantic_assessment"]
    p.checked(semantic, "new_semantic_assessment")
    origin = qualification["origin_verification"]
    p.checked(origin, "material_origin_verification")
    p.require(
        origin["session_id"] == session["id"]
        and origin["registered_session_id"] == registered["session_id"]
        and qualification["authentic_origin_verified"]
        == (origin["status"] == "PASS_AUTHENTIC_MATERIAL_PUBLIC_CHAIN"),
        "materials.receipt_origin_not_boolean_self_attestation",
    )
    p.require(
        qualification["financial_valid"] == semantic["financial_valid"]
        and qualification["actual_method"] == semantic["actual_method"]
        and qualification["full_class"] == semantic["full_class"]
        and qualification["full_class_valid"]
        == (semantic["full_mapping_status"] == "MAPPED" and semantic["full_class"] is not None),
        "materials.actual_complete_semantics_not_labels",
    )
    expected = bool(
        qualification["financial_valid"]
        and qualification["full_class_valid"]
        and qualification["authentic_origin_verified"]
        and qualification["actual_method"]
        in ({"control"} if registered["family"] == "control" else {"endpoint", "movement"})
        and session["first_final_index"] is not None
    )
    p.require(
        qualification["token_materialization_eligible"] is expected,
        "materials.eligibility_recomputed",
    )


def original_candidates(session, registered, qualification):
    """No replacement rows: original target bytes and entire actual input history."""
    _qualification(session, registered, qualification)
    p.require(qualification["token_materialization_eligible"], "materials.qualified_original_only")
    rows = []
    for turn, event in zip(session["turns"], session["events"], strict=True):
        p.require(
            turn["response_index"] == event["response_index"]
            and turn["raw_response_sha256"] == p.sha(turn["raw_response"]),
            "materials.original_public_response_bytes",
        )
        if not (event["final"] or event["tool_call"] and event["tool_call"]["status"] == "ok"):
            continue
        rows.append(
            p.record(
                "original_material_response",
                session_id=session["id"],
                registered_session_id=registered["session_id"],
                registration_id=registered["id"],
                task_id=registered["task_id"],
                pool=registered["pool"],
                role=registered["role"],
                qualification_id=qualification["id"],
                response_index=turn["response_index"],
                public_runtime_state_id="history:" + p.sha(p.encode(turn["input_messages"])),
                messages=turn["input_messages"],
                target_text=turn["raw_response"],
                target_raw_sha256=turn["raw_response_sha256"],
                response_kind="Final" if event["final"] else event["tool_call"]["tool"],
                transport_evidence=turn["transport_evidence"],
                full_input_history_retained=True,
            )
        )
    p.require(
        rows
        and rows[-1]["response_kind"] == "Final"
        and rows[-1]["response_index"] == session["first_final_index"],
        "materials.complete_original_first_Final_package",
    )
    return rows


def _outcome(
    registered, session, qualification, package, status, reason=None, *, consumability_status=None
):
    _registration(registered)
    p.require(status in TERMINALS, "materials.terminal_status")
    q = qualification or {}
    mapped = bool(q.get("full_class_valid"))
    method = q.get("actual_method", "UNDETERMINED")
    state = canonical_state_id(method, q["full_class"]) if mapped else None
    return p.record(
        "material_outcome",
        session_id=registered["session_id"],
        material_session_id=session["id"] if session else None,
        registration_id=registered["id"],
        task_id=registered["task_id"],
        pool=registered["pool"],
        role=registered["role"],
        status=status,
        reason=reason,
        qualification_id=q.get("id"),
        financial_valid=bool(q.get("financial_valid")),
        full_class_valid=mapped,
        authentic_origin_verified=bool(q.get("authentic_origin_verified")),
        consumable=bool(package and package["consumable"] and status == "finished"),
        consumability_status=consumability_status
        or (
            "CONSUMABLE"
            if package and package["consumable"]
            else "FAILED_TOKEN_CHECK"
            if package
            else "NOT_MEASURED"
            if q.get("token_materialization_eligible")
            else "NOT_ELIGIBLE"
        ),
        actual_method=method,
        state_id=state,
        original_package=package,
        role_reassigned=False,
        ranking_or_top_k=False,
    )


def materialize_session(
    session,
    registered,
    qualification,
    binding,
    tokenizer,
    *,
    code_snapshot_id,
    status="finished",
    encoder=encode_original_candidate,
):
    """Encode one entire eligible package with an already loaded CPU tokenizer."""
    _qualification(session, registered, qualification)
    p.require(
        code_snapshot_id == qualification["code_snapshot_id"], "materials.frozen_assessor_code"
    )
    if status != "finished" or not qualification["token_materialization_eligible"]:
        return {
            "package": None,
            "outcome": _outcome(registered, session, qualification, None, status),
        }
    p.require(
        isinstance(binding, dict)
        and isinstance(binding.get("id"), str)
        and binding.get("model_max_position_embeddings", 0) >= p.SEQUENCE_CAP,
        "materials.original_CPU_tokenizer_context",
    )
    candidates = original_candidates(session, registered, qualification)
    encoded_rows, errors = [], []
    for candidate in candidates:
        returned = None
        try:
            representation = encoder(
                candidate, binding, tokenizer, maximum_sequence_length=p.SEQUENCE_CAP
            )
            returned = representation
            representation_identity(representation, "token_representation")
            p.require(
                representation["row_id"] == candidate["id"]
                and representation["session_id"] == session["id"]
                and representation["qualification_id"] == qualification["id"]
                and representation["tokenizer_binding_id"] == binding["id"]
                and representation["target_raw_sha256"] == candidate["target_raw_sha256"]
                and representation["maximum_sequence_length"] == p.SEQUENCE_CAP
                and representation["truncated"] is False,
                "materials.exact_original_encoder_result",
            )
            if representation["consumable_token_representation"]:
                ids, mask, labels = (
                    representation[key] for key in ("input_ids", "target_mask", "labels")
                )
                p.require(
                    all(isinstance(values, list) for values in (ids, mask, labels))
                    and len(ids) == len(mask) == len(labels) == representation["sequence_length"]
                    and 1 < len(ids) <= p.SEQUENCE_CAP
                    and all(type(token) is int and token >= 0 for token in ids)
                    and mask[0] == 0
                    and all(type(active) is int and active in (0, 1) for active in mask)
                    and sum(mask[1:]) == representation["target_token_count"] > 0
                    and all(
                        type(label) is int and label == (token if active else -100)
                        for token, active, label in zip(ids, mask, labels, strict=True)
                    )
                    and representation["attention_mask"] == [1] * len(ids),
                    "materials.original_causal_arrays_consistent",
                )
            if not representation["consumable_token_representation"]:
                errors.append(
                    {
                        "response_index": candidate["response_index"],
                        "reason": representation["reason"],
                    }
                )
        except (ValueError, TypeError, KeyError, UnicodeError, RuntimeError) as error:
            errors.append({"response_index": candidate["response_index"], "reason": str(error)})
            representation = p.record(
                "original_encoding_failure",
                candidate_id=candidate["id"],
                error_type=type(error).__name__,
                reason=str(error),
                input_ids=None,
                target_mask=None,
                labels=None,
                sequence_length=None,
                target_token_count=None,
                consumable_token_representation=False,
                truncation=False,
                original_candidate_retained=True,
                returned_encoder_result=returned,
            )
        encoded_rows.append({"candidate": candidate, "representation": representation})
    counts = [row["representation"]["target_token_count"] for row in encoded_rows]
    total = sum(counts) if all(type(value) is int for value in counts) else None
    package = p.record(
        "encoded_original_package",
        session_id=session["id"],
        registered_session_id=registered["session_id"],
        registration_id=registered["id"],
        task_id=registered["task_id"],
        pool=registered["pool"],
        role=registered["role"],
        freeze_id=registered["freeze_id"],
        qualification_id=qualification["id"],
        source_boundary_id=qualification["source_boundary_id"],
        bundle_id=qualification["bundle_id"],
        code_snapshot_id=code_snapshot_id,
        actual_method=qualification["actual_method"],
        full_class=qualification["full_class"],
        state_id=canonical_state_id(qualification["actual_method"], qualification["full_class"]),
        tokenizer_binding_id=binding["id"],
        maximum_sequence_length=p.SEQUENCE_CAP,
        rows=encoded_rows,
        errors=errors,
        consumable=not errors and bool(encoded_rows) and len(encoded_rows) == len(candidates),
        whole_package_target_tokens=total,
        known_target_token_subtotal=sum(value for value in counts if type(value) is int),
        original_response_count=len(session["turns"]),
        positive_original_response_count=len(candidates),
        original_request_response_bytes_retained=True,
        request_response_bytes_scope=(
            "exact public request histories and public response content; "
            "original session and transport evidence remain separately archived"
        ),
        full_provider_wire_envelope_reconstructible=False,
        failed_and_format_prefixes_retained_in_every_subsequent_input=True,
        failed_responses_promoted_to_positive_targets=False,
        truncation=False,
        retokenization_or_mask_reconstruction=False,
        role_reassigned=False,
    )
    return {
        "package": package,
        "outcome": _outcome(registered, session, qualification, package, status),
    }


def _reference(path, value, root):
    return {
        "path": str(path.relative_to(root)),
        "sha256": p.sha(p.encode(value)),
        "id": value["id"],
    }


def store_materialized(materialized, output, *, writer=p.write_once):
    """Store token arrays once; the compact outcome reconstructs the exact ID."""
    root = Path(output)
    outcome, package = materialized["outcome"], materialized["package"]
    p.checked(outcome, "material_outcome")
    p.require(outcome["original_package"] == package, "materials.package_outcome_join")
    session_id = outcome["session_id"]
    p.require(
        isinstance(session_id, str)
        and session_id
        and "/" not in session_id
        and ".." not in session_id,
        "materials.safe_registered_directory",
    )
    directory = root / "packages" / session_id
    package_ref = None
    if package is not None:
        p.checked(package, "encoded_original_package")
        path = directory / "package.json"
        writer(path, package)
        package_ref = _reference(path, package, root)
    storage = p.record(
        "stored_material_outcome",
        material_outcome_id=outcome["id"],
        outcome_fields={
            key: value for key, value in _fields(outcome).items() if key != "original_package"
        },
        original_package_reference=package_ref,
        token_arrays_repeated_in_storage_record=False,
    )
    path = directory / "outcome.json"
    writer(path, storage)
    return {
        "registered_session_id": session_id,
        "outcome_id": outcome["id"],
        "outcome": _reference(path, storage, root),
        "package": package_ref,
        "status": outcome["status"],
        "consumable": outcome["consumable"],
        "role": outcome["role"],
    }


def _read_reference(reference, root):
    root = Path(root).resolve()
    relative = Path(reference["path"])
    p.require(
        not relative.is_absolute() and ".." not in relative.parts,
        "materials.relative_artifact_reference",
    )
    path = root / relative
    p.require(
        path.is_file()
        and not any(part.is_symlink() for part in (path, *path.parents))
        and path.resolve().is_relative_to(root),
        "materials.regular_local_reference",
    )
    data = path.read_bytes()
    p.require(p.sha(data) == reference["sha256"], "materials.original_artifact_bytes")
    value = json.loads(data)
    p.require(value["id"] == reference["id"], "materials.referenced_identity")
    return value


def hydrate_outcomes(index, output):
    """Read exact per-session packages for existing ``distribution.build_kernel``.

    Do not serialize the returned arrays into another giant outcomes JSON. The
    compact index and per-session artifacts are the authoritative disk form.
    """
    if isinstance(index, dict):
        p.checked(index, "materialization_index")
    entries = index["entries"] if isinstance(index, dict) else index
    outcomes = []
    for entry in entries:
        stored = _read_reference(entry["outcome"], output)
        p.checked(stored, "stored_material_outcome")
        reference = stored["original_package_reference"]
        p.require(reference == entry["package"], "materials.index_package_reference")
        package = _read_reference(reference, output) if reference else None
        if package:
            p.checked(package, "encoded_original_package")
        outcome = p.record("material_outcome", **stored["outcome_fields"], original_package=package)
        p.require(
            outcome["id"] == stored["material_outcome_id"] == entry["outcome_id"]
            and outcome["session_id"] == entry["registered_session_id"],
            "materials.exact_hydrated_outcome",
        )
        outcomes.append(outcome)
    return outcomes


def materialize_all(
    registry,
    results,
    data_root,
    output,
    *,
    code_snapshot_id,
    item_loader,
    collection_gate_passed=True,
    collection_gate_reason=None,
    loader=load_local_tokenizer,
    encoder=encode_original_candidate,
    writer=p.write_once,
):
    """Close all 10,240 registered terminal rows before the first tokenizer load.

    ``results`` contains session_id (the registered ID) and terminal status.
    ``item_loader(result)`` lazily returns {session, qualification} from the
    separately frozen files. Failed/not-run rows may have no original session.
    An unfinished/failed collection entry suppresses ALL token materialization, preventing
    a successful prefix from becoming a training pool. Other failed candidates
    remain explicit zero-eligible outcomes in the complete registry.
    """
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
    for registered in sessions:
        _registration(registered)
        p.require(
            registered["freeze_id"] == registry["freeze_id"], "materials.registry_freeze_join"
        )
        p.require(
            by_session[registered["session_id"]]["status"] in TERMINALS,
            "materials.all_terminal_statuses",
        )
    p.require(type(collection_gate_passed) is bool, "materials.explicit_external_collection_gate")
    raw_registry_complete = all(row["status"] == "finished" for row in results)
    incomplete = not collection_gate_passed or not raw_registry_complete
    not_measured = (
        "NOT_MEASURED_GLOBAL_GATE"
        if raw_registry_complete and not collection_gate_passed
        else "NOT_MEASURED_INCOMPLETE_COLLECTION"
    )
    binding, tokenizer, loads, entries = None, None, 0, []
    counts = Counter()
    for registered in sessions:
        terminal = by_session[registered["session_id"]]
        status = terminal["status"]
        item = item_loader(terminal)
        session, qualification = item.get("session"), item.get("qualification")
        if session is None or qualification is None:
            p.require(status != "finished", "materials.finished_requires_session_and_qualification")
            materialized = {
                "package": None,
                "outcome": _outcome(
                    registered, session, None, None, status, terminal.get("reason")
                ),
            }
        else:
            _qualification(session, registered, qualification)
            p.require(
                qualification["code_snapshot_id"] == code_snapshot_id,
                "materials.frozen_assessor_code",
            )
            if incomplete:
                materialized = {
                    "package": None,
                    "outcome": _outcome(
                        registered,
                        session,
                        qualification,
                        None,
                        status,
                        collection_gate_reason or "complete_collection_required_no_success_prefix",
                        consumability_status=not_measured,
                    ),
                }
            else:
                if (
                    status == "finished"
                    and qualification["token_materialization_eligible"]
                    and binding is None
                ):
                    binding, tokenizer = loader(data_root)
                    loads += 1
                    writer(Path(output) / "tokenizer_binding.json", binding)
                materialized = materialize_session(
                    session,
                    registered,
                    qualification,
                    binding,
                    tokenizer,
                    code_snapshot_id=code_snapshot_id,
                    status=status,
                    encoder=encoder,
                )
        outcome = materialized["outcome"]
        counts[status] += 1
        counts["consumable_" + registered["role"]] += int(outcome["consumable"])
        entries.append(store_materialized(materialized, output, writer=writer))
    result = p.record(
        "materialization_index",
        registry_id=registry["id"],
        freeze_id=registry["freeze_id"],
        code_snapshot_id=code_snapshot_id,
        complete_registered_denominator=len(sessions),
        collection_complete=not incomplete,
        collection_complete_is_admission_gate_not_raw_attempt_count=True,
        raw_registry_complete=raw_registry_complete,
        generation_contract_passed=collection_gate_passed,
        materialization_permitted=not incomplete,
        collection_gate_passed=collection_gate_passed,
        collection_gate_reason=collection_gate_reason,
        status=(
            "NOT_MEASURED_GLOBAL_GATE" if raw_registry_complete else "SKIPPED_INCOMPLETE_COLLECTION"
        )
        if incomplete
        else "COMPLETE_FIXED_MATERIALIZATION",
        entries=entries,
        counts={
            **dict(counts),
            **({"consumable_train": None, "consumable_sealed": None} if incomplete else {}),
        },
        tokenizer_binding_id=binding["id"] if binding else None,
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
    )
    writer(Path(output) / "materialization_index.json", result)
    return result
