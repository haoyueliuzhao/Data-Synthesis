"""All-or-block V13 material: fixed candidates, fixed authority and real consumers.

No API dispatch, model training, GPU reservation or private scoring occurs here.
Every registered original remains in the denominator even if material is blocked.
"""

from __future__ import annotations

import copy
import hashlib
import json
import multiprocessing
import os
import sqlite3
from collections import Counter
from fractions import Fraction
from pathlib import Path

from .contracts import Episode, digest
from .probe_budget import _acknowledged_unknowns, _request_record_digest
from .providers import tokenizer_binding
from .storage import read_json, snapshot_manifest
from .v6_collection import bound, persist, require
from .v6_distribution import manual_distribution
from .v6_task import public_trajectory_view
from .v7_base_evaluation import ORIGIN, load_tokenizer
from .v8_training_driver import VerifiedPool
from .v9_conditional_training import execution_plan
from .v10_material import Reader, checked, entry
from .v13_material_protocol import checked_request, singleton
from .v13_material_provider import paid_record, restore_settled
from .v13_student_encoding import MANIFEST_SCHEMA, encode_for_student, validate_encoding

BINDING_SCHEMA = "v13_material_binding.v1"
ENCODING_WORKERS = 8
_ENCODING_STATE = None


def _encoding_worker_init(tokenizer, originals, manifests, output, produce_encodings):
    global _ENCODING_STATE
    # Worker-local only; avoid inherited tokenizer thread pools and nested threads.
    os.environ["TOKENIZERS_PARALLELISM"] = "false"
    _ENCODING_STATE = tokenizer, originals, manifests, output, produce_encodings


def _encode_registered_original(sid):
    tokenizer, originals, manifests, output, producing = _ENCODING_STATE
    episode, manifest = originals[sid], manifests[sid]
    if not producing:
        path = output / "encoding" / sid.split(":", 1)[-1] / "record.json"
        return validate_encoding(read_json(path), episode, manifest, tokenizer)
    try:
        return encode_for_student(episode, manifest, tokenizer)
    except (ValueError, TypeError, KeyError) as exc:
        return bound(
            dict(
                schema="v13_encoding_blocked.v1",
                slot_id=sid,
                task_id=episode.task_id,
                episode_sha256=digest(episode),
                authority_record=manifest["authority_record"],
                encoding_admitted=False,
                failures=[
                    dict(reason="lossless_encoding_failed", error=f"{type(exc).__name__}: {exc}")
                ],
            )
        )


def supervision_manifest(episode, pair, authority_record, projection, *, protocol_id):
    """Pure locator transcription, not a new semantic decision or best-of mask."""
    require(projection.get("usable") is True, "unresolved projection has no supervision authority")
    view = public_trajectory_view(episode, slot_id=pair["slot_id"])
    return bound(
        dict(
            schema=MANIFEST_SCHEMA,
            protocol_id=protocol_id,
            task_id=episode.task_id,
            slot_id=pair["slot_id"],
            episode_sha256=digest(episode),
            view_id=view["view_id"],
            projection_authority=pair["projection_authority"],
            authority_record=copy.deepcopy(authority_record),
            projection_sha256=digest(projection),
            positive_content_spans=[
                dict(
                    original_segment_id=s["segment_id"],
                    layer="reason",
                    start=s["start"],
                    end=s["end"],
                    quote=s["quote"],
                )
                for s in projection["positive_content"]
            ],
            positive_action_ids=[a["action_id"] for a in projection["positive_actions"]],
            original_projection=copy.deepcopy(projection),
            original_process_judgments_unchanged=True,
            JSON_repaired=False,
            field_authority_chosen_before_new_annotations=True,
        )
    )


def support_profile(task_ids, task_slots, mappings, encodings, *, projection_failures=()):
    """Pure profile with fixed denominator; missing material never shrinks support."""
    require(
        list(task_slots) == list(task_ids) and len(set(task_ids)) == len(task_ids),
        "fixed task order and exact membership required",
    )
    slots = [s for task in task_ids for s in task_slots[task]]
    require(
        len(set(slots)) == len(slots) and set(encodings) == set(slots),
        "all and only fixed candidate packages require encoding outcomes",
    )
    blockers = list(copy.deepcopy(projection_failures))
    support, layers, coverage, singletons = {}, Counter(reason=0, tool=0, final=0), {}, []
    for task in task_ids:
        members, mapping = task_slots[task], mappings.get(task)
        require(bool(members), "fixed training task cannot have empty original support")
        if mapping is None or mapping.get("mapping_status") != "complete":
            blockers.append(
                dict(task_id=task, reason="whole_task_mapping_unresolved", slot_ids=members)
            )
            continue
        assigned, chi = mapping["state_by_slot"], mapping["chi_by_state"]
        require(
            set(assigned) == set(members) and set(assigned.values()) == set(chi),
            "mapping must cover each fixed task original exactly once",
        )
        counts = Counter(assigned.values())
        if len(members) == 1:
            require(
                mapping.get("deterministic_singleton") is True
                and len(counts) == 1
                and list(chi.values()) == [None]
                and mapping.get("chi_status") == "not_required_for_weighting",
                "true one-package task requires registered deterministic null-chi branch",
            )
            singletons.append(task)
        else:
            require(
                mapping.get("deterministic_singleton") is False
                and all(type(v) is int and v in (0, 1) for v in chi.values()),
                "multi-package mapping cannot use singleton fallback or fabricated null chi",
            )
        support[task] = dict(
            candidate_slot_ids=list(members),
            joint_valid_slot_ids=list(members),
            states=dict(counts),
            chi=copy.deepcopy(chi),
            n_x=len(members),
            deterministic_singleton=len(members) == 1,
        )
    for sid in slots:
        value = encodings[sid]
        if not value.get("encoding_admitted"):
            blockers.append(
                dict(
                    slot_id=sid,
                    reason="fixed_original_encoding_unresolved",
                    failures=value.get("failures", []),
                )
            )
        layers.update(value.get("layer_target_counts", {}))
        coverage[sid] = dict(
            positive_tokens=value.get("layer_target_counts", {}).get("reason"),
            raw_characters=value.get("original_public_content_characters"),
            approved_characters=value.get("positive_public_content_characters"),
            all_reason_tokens_masked=value.get("public_content_without_positive_reason_targets"),
        )
    token_counts_known = bool(slots) and all(
        e.get("encoding_admitted") is True and "layer_target_counts" in e
        for e in encodings.values()
    )
    all_reason_masked = (
        layers["reason"] == 0 and any(e.get("public_content_present") for e in encodings.values())
        if token_counts_known
        else None
    )
    if all_reason_masked is True:
        blockers.append(dict(reason="all_public_reasoning_masked_supervision_projection"))
    N = len(task_ids)
    resolved = len(support) == N
    degrees = sum(len(s["states"]) - 1 for s in support.values()) if resolved else None
    flexible = sum(len(s["states"]) > 1 for s in support.values()) if resolved else None
    mixed = sum(len(set(s["chi"].values())) > 1 for s in support.values()) if resolved else None
    dose = None
    if resolved:
        prior = {
            t: {z: str(Fraction(n, s["n_x"])) for z, n in s["states"].items()}
            for t, s in support.items()
        }
        chi = {t: s["chi"] for t, s in support.items()}
        plus = manual_distribution(
            prior, chi, direction="Manual+", registered_singleton_tasks=singletons
        )
        minus = manual_distribution(
            prior, chi, direction="Manual-", registered_singleton_tasks=singletons
        )
        per_task = {}
        totals = dict(plus=Fraction(0), minus=Fraction(0))
        for task in task_ids:
            p = (
                None
                if task in singletons
                else sum(
                    (Fraction(prior[task][z]) for z in prior[task] if chi[task][z] == 1),
                    Fraction(0),
                )
            )
            row = dict(p=None if p is None else str(p))
            for name, q in (("plus", plus), ("minus", minus)):
                tv = (
                    Fraction(0) if p is None else p * (1 - p) / (1 + p if name == "plus" else 2 - p)
                )
                observed = (
                    sum(
                        abs(float(Fraction(str(q[task][z]))) - float(Fraction(prior[task][z])))
                        for z in prior[task]
                    )
                    / 2
                )
                require(
                    abs(observed - float(tv)) < 1e-12,
                    "actual Manual consumer differs from exact dose formula",
                )
                row["TV_" + name] = str(tv)
                totals[name] += tv / N
            row.update(
                chi_status="not_required_for_weighting"
                if task in singletons
                else "semantically_annotated",
                q_plus=plus[task],
                q_minus=minus[task],
            )
            per_task[task] = row
        dose = dict(
            per_task=per_task,
            mu_weighted_TV_plus=str(totals["plus"]),
            mu_weighted_TV_minus=str(totals["minus"]),
            alpha=2,
        )
    complete = not blockers and N > 0
    distinct = bool(complete and degrees > 0 and mixed > 0)
    profile = bound(
        dict(
            schema="v13_conditional_capability_profile.v1",
            N=N,
            package_count=len(slots),
            state_count=sum(len(s["states"]) for s in support.values()) if resolved else None,
            D_pi=degrees,
            multi_state_tasks=flexible,
            chi_flexible_tasks=mixed,
            M_flex=str(Fraction(flexible, N)) if resolved else None,
            chi_flexible_mass=str(Fraction(mixed, N)) if resolved else None,
            singleton_package_tasks=sum(len(v) == 1 for v in task_slots.values()),
            deterministic_singleton_tasks=singletons,
            one_state_tasks=N - flexible if resolved else None,
            supervised_tokens=dict(layers) if token_counts_known else None,
            observed_encoded_supervised_tokens=dict(layers),
            all_public_reasoning_masked=all_reason_masked,
            encoding_started_packages=sum(
                e.get("schema") != "v13_encoding_not_started.v1" for e in encodings.values()
            ),
            package_reason_coverage=coverage,
            raw_public_content_characters=sum(v["raw_characters"] or 0 for v in coverage.values()),
            approved_public_content_characters=(
                sum(v["approved_characters"] for v in coverage.values())
                if all(v["approved_characters"] is not None for v in coverage.values())
                else None
            ),
            observed_known_approved_public_content_characters=sum(
                v["approved_characters"] or 0 for v in coverage.values()
            ),
            public_content_all_masked_packages=[
                s
                for s, e in encodings.items()
                if e.get("public_content_without_positive_reason_targets")
            ],
            maximum_sequence_tokens=max(
                (e.get("max_sequence_tokens", 0) for e in encodings.values()), default=0
            ),
            total_sequence_tokens=sum(
                e.get("total_sequence_tokens", 0) for e in encodings.values()
            ),
            manual_intervention_dose=dose,
            material_complete=complete,
            blockers=blockers,
            nontrivial_pi=degrees is not None and degrees > 0,
            nontrivial_manual=mixed is not None and mixed > 0,
            five_arm_algebraic_distinguishability_possible=distinct,
            reason_coverage_is_not_substantive_reasoning_quality=True,
            power_established=False,
            student_results_used=False,
            no_arbitrary_minimum_N=True,
        )
    )
    return bound(
        dict(
            schema="v13_conditional_support_manifest.v1",
            training_task_ids=list(task_ids),
            N=N,
            candidate_slot_ids=slots,
            joint_valid_slot_ids=slots,
            package_count=len(slots),
            task_support=support,
            mu={t: str(Fraction(1, N)) for t in task_ids},
            registered_singleton_tasks=singletons,
            capability_profile=profile,
            material_complete=complete,
            exploratory_training_admitted=distinct,
            execution_plan=execution_plan(N) if N else None,
            all_originals_retained=True,
            no_valid_package_or_task_dropped=True,
            original_process_judgments_unchanged=True,
            semantic_truth_proved=False,
        )
    )


def _population(output, reader):
    plan = checked(
        reader.read(entry(output / "registration/record.json")),
        "v13_fixed_candidate_material_plan.v1",
    )
    definition = checked(
        reader.read(plan["definition"], output / "definition/record.json"),
        "v13_fixed_candidate_population.v1",
    )
    source = checked(
        reader.read(definition["inputs"]["source_v12_seal"]), "v12_complete_rereview_seal.v1"
    )
    pairs, tasks = definition["pairs"], definition["tasks"]
    slots = [p["slot_id"] for p in pairs]
    task_slots = {t["task_id"]: t["slot_ids"] for t in tasks}
    missing = [p["slot_id"] for p in pairs if p["projection_authority"] == "V13_completion_only"]
    require(
        plan["protocol_identity"] == definition["id"]
        and len(pairs) == len(set(slots)) == 2468
        and len(tasks) == len(task_slots) == 744
        and slots == source["joint_process_candidate_slot_ids"] == plan["candidate_slot_ids"]
        and missing
        == source["projection_blocked_candidate_slot_ids"]
        == plan["projection_completion_slot_ids"]
        and len(missing) == 671
        and plan["fixed_task_slots"] == task_slots
        and sum(len(v) == 1 for v in task_slots.values()) == 99
        and set(plan["singleton_task_ids"]) == {t for t, s in task_slots.items() if len(s) == 1}
        and all(
            p["projection_authority"] in {"V12_A_original", "V13_completion_only"} for p in pairs
        ),
        "complete fixed 2468/744 population and predeclared 1797/671 authority required",
    )
    require(
        Counter(p["task_id"] for p in pairs) == Counter({t: len(s) for t, s in task_slots.items()})
        and all(
            [p["slot_id"] for p in pairs if p["task_id"] == t] == s for t, s in task_slots.items()
        ),
        "fixed task membership differs from original candidate order",
    )
    source_plan = checked(reader.read(definition["inputs"]["source_v12_plan"]))
    native = checked(reader.read(definition["inputs"]["source_native"]))
    generation = checked(reader.read(definition["inputs"]["source_generation"]))
    native_rows = {r["slot"]["slot_id"]: r for r in native["rows"]}
    generated = {r["slot"]["slot_id"]: r for r in generation["slots"]}
    require(
        source["registration_id"] == source_plan["id"]
        and source["all_model_responses_returned"] is True
        and source["actual_returns"] == source["expected_reviews"] == 11438
        and native["generation_seal_id"] == generation["id"]
        and native["protocol_id"] == generation["protocol_id"] == source_plan["source_protocol_id"],
        "complete original native/generation/review chain required",
    )
    original_pairs = {r["id"]: r for r in source["paired_cores"]}
    for pair in pairs:
        sid = pair["slot_id"]
        outcome, native_row = generated[sid], native_rows[sid]
        require(
            original_pairs.get(pair["pair"]["id"]) == pair["pair"]
            and native_row["Q_native"] is True
            and pair["native_result"] == native_row["native"]
            and outcome["status"] == "COMPLETE"
            and pair["original_episode"]
            == dict(
                path=outcome["episode_path"],
                sha256=outcome["episode_file_sha256"],
                episode_sha256=outcome["episode_sha256"],
            )
            and pair["original_integrity"]["id"] == outcome["integrity_id"],
            "fixed package source was redirected from its original qualification/episode",
        )
    return plan, definition, task_slots


def _annotations(output, plan, reader):
    seal = checked(
        reader.read(entry(output / "completion_seal/record.json")),
        "v13_material_completion_seal.v1",
    )
    jobs = plan["jobs"]
    require(
        seal["registration_id"] == plan["id"]
        and seal["protocol_id"] == plan["protocol_identity"]
        and seal["expected_calls"] == len(jobs) == len(seal["terminals"]) == 1316
        and Counter(j["purpose"] for j in jobs) == {"projection": 671, "mapping": 645}
        and seal["all_registered_jobs_have_authentic_terminals"] is True,
        "all actual registered terminals required before any material admission",
    )
    db = sqlite3.connect(Path(plan["budget_database"]).resolve().as_uri() + "?mode=ro", uri=True)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA query_only=ON")
    db.execute("BEGIN")
    result, returns, unknowns = {}, 0, 0
    try:
        config = json.loads(
            db.execute("SELECT value FROM metadata WHERE key='config'").fetchone()[0]
        )
        require(
            digest(config) == plan["budget_config_sha256"], "same original flash wallet required"
        )
        acknowledgments = {r["invocation_id"]: r for r in _acknowledged_unknowns(db, config)}
        for job, ref in zip(jobs, seal["terminals"], strict=True):
            terminal = checked(reader.read(ref), "v13_material_terminal.v1")
            require(
                terminal["episode_id"] == job["episode_id"]
                and terminal["registration_id"] == plan["id"]
                and terminal["purpose"] == job["purpose"]
                and terminal["task_id"] == job["task_id"],
                "complete seal terminal order/coordinate changed",
            )
            request = checked_request(reader.read(job["request"]))
            record = checked(reader.read(terminal["record"]))
            require(
                request["protocol_id"] == plan["protocol_identity"],
                "registered request/returned material authority differs",
            )
            if terminal["terminal_kind"] == "paid_model_return":
                require(record["request"] == request, "returned request differs from fixed job")
                row = db.execute(
                    "SELECT * FROM requests WHERE invocation_id=?",
                    (record["artifact"]["budget_invocation_id"],),
                ).fetchone()
                require(row is not None, "paid material receipt absent from original wallet")
                row = dict(row)
                artifact = restore_settled(row, request)
                require(
                    record == paid_record(request, artifact, row),
                    "paid record differs from settled raw annotation",
                )
                returns += 1
            else:
                require(
                    terminal["terminal_kind"] == "acknowledged_connection_unknown"
                    and record["schema"] == "v13_network_unknown_material.v1"
                    and record.get("inspection") is None
                    and record.get("actual_model_call_receipt_verified") is False,
                    "missing return is unknown, never a synthetic material annotation",
                )
                row = db.execute(
                    "SELECT * FROM requests WHERE invocation_id=?", (record["invocation_id"],)
                ).fetchone()
                require(row is not None, "UNKNOWN material call absent from original wallet")
                row, ack = dict(row), acknowledgments.get(record["invocation_id"])
                require(
                    row["state"] == "UNKNOWN"
                    and ack is not None
                    and record["request_id"] == request["id"]
                    and record["acknowledgment_id"] == ack["id"]
                    and record["request_sha256"] == row["request_sha256"] == job["request_sha256"]
                    and record["original_ledger_record_sha256"] == _request_record_digest(row)
                    and record["permanent_reserved_microcny"] == row["reserved_microcny"],
                    "UNKNOWN must retain actual same-call acknowledgment and hold",
                )
                unknowns += 1
            key = (
                job["purpose"],
                job["slot_id"] if job["purpose"] == "projection" else job["task_id"],
            )
            require(key not in result, "one registered call per material coordinate required")
            result[key] = dict(record=record, reference=terminal["record"], request=request)
        require(
            seal["actual_returns"] == returns and seal["network_unknowns"] == unknowns,
            "returned and unknown material counts cannot be conflated",
        )
    finally:
        db.close()
    return seal, result


def _collect(output, reader, *, produce_encodings):
    plan, definition, task_slots = _population(output, reader)
    seal, annotations = _annotations(output, plan, reader)
    preparation = checked(reader.read(plan["preparation"]))
    deterministic = {r["task_id"]: r["record"] for r in preparation["singletons"]}
    require(
        set(deterministic) == set(plan["singleton_task_ids"]),
        "all registered singleton records required",
    )
    original_plan = checked(reader.read(definition["inputs"]["source_v10_plan"]))
    encodings, encoding_entries, manifest_entries, views, failures = {}, {}, {}, {}, []
    originals, manifests = {}, {}
    pairs_by_slot = {p["slot_id"]: p for p in definition["pairs"]}
    sources = {
        task: dict(
            v13_population_id=definition["id"],
            task_slot_ids=slots,
            source_review_seal=definition["inputs"]["source_v12_seal"],
            original_records=[
                {
                    k: pairs_by_slot[s][k]
                    for k in ("slot_id", "pair", "A_record", "B_record", "A_request")
                }
                for s in slots
            ],
        )
        for task, slots in task_slots.items()
    }
    for pair in definition["pairs"]:
        sid, task = pair["slot_id"], pair["task_id"]
        core = checked(reader.read(pair["pair"]), "v12_paired_process_core.v1")
        original_a = checked(reader.read(pair["A_record"]))
        original_b = checked(reader.read(pair["B_record"]))
        request_a = checked(reader.read(pair["A_request"]))
        terminals = {role: checked(reader.read(core[role + "_terminal"])) for role in ("A", "B")}
        require(
            core["joint_process_candidate"] is True
            and core["slot_id"] == sid
            and core["task_id"] == task
            and original_a["actual_model_call_receipt_verified"] is True
            and original_b["actual_model_call_receipt_verified"] is True
            and terminals["A"]["record"] == pair["A_record"]
            and terminals["B"]["record"] == pair["B_record"]
            and original_a["request"] == request_a,
            "original candidate qualification and source records must remain unchanged",
        )
        raw = Path(pair["original_episode"]["path"]).read_bytes()
        require(
            hashlib.sha256(raw).hexdigest() == pair["original_episode"]["sha256"],
            "original episode bytes changed",
        )
        episode = Episode.model_validate_json(raw)
        require(
            digest(episode) == pair["original_episode"]["episode_sha256"]
            and episode.task_id == task
            and episode.config.model_dump(mode="json") == original_plan["configs_by_task"][task],
            "original episode/task/configuration changed",
        )
        view = public_trajectory_view(episode, slot_id=sid)
        require(
            request_a["candidate_request"]["trajectory"] == view,
            "complete original public view changed",
        )
        views[sid] = view
        originals[sid] = episode
        if pair["projection_authority"] == "V12_A_original":
            require(
                core["A_projection_usable"] is True
                and original_a["new_pipeline_outcomes"]["projection_usable"] is True,
                "original usable A projection cannot be replaced or silently downgraded",
            )
            projection, authority = (
                original_a["inspection"]["auxiliary"]["supervision"],
                pair["A_record"],
            )
        else:
            require(
                core["A_projection_usable"] is not True,
                "new projection outside predeclared missing list",
            )
            item = annotations["projection", sid]
            require(
                item["request"]["views"] == [view]
                and item["request"]["source_bindings"] == sources[task],
                "projection must use full original public trajectory and fixed authorities",
            )
            inspected = item["record"].get("inspection")
            projection = inspected["projection"] if inspected and inspected.get("usable") else None
            authority = item["reference"]
        if projection is None:
            failures.append(dict(slot_id=sid, reason="predeclared_projection_unresolved"))
        else:
            manifests[sid] = supervision_manifest(
                episode, pair, authority, projection, protocol_id=plan["protocol_identity"]
            )
    mappings = {}
    for task, slots in task_slots.items():
        if len(slots) == 1:
            record = checked(reader.read(deterministic[task]))
            require(
                record
                == singleton(
                    views[slots[0]],
                    protocol_id=plan["protocol_identity"],
                    source_bindings=sources[task],
                ),
                "registered one-element deterministic partition changed",
            )
            mappings[task] = record
        else:
            item = annotations["mapping", task]
            require(
                item["request"]["views"] == [views[s] for s in slots]
                and item["request"]["source_bindings"] == sources[task],
                "whole-task mapping must consume every full original, never the approved mask",
            )
            mappings[task] = item["record"].get("inspection")
    # A complete fixed-authority/mapping barrier precedes even loading the tokenizer.
    # A partial material inventory never triggers encoding just its successful subset.
    authority_complete = not failures and all(
        m is not None and m.get("mapping_status") == "complete" for m in mappings.values()
    )
    token_binding = None
    if authority_complete:
        assets = checked(read_json(ORIGIN))
        require(
            assets["id"] == original_plan["original"]["prior_original_protocol_id"],
            "fixed Student assets source changed",
        )
        tokenizer = load_tokenizer(assets["assets"])
        token_binding = tokenizer_binding(tokenizer)
        for pair in definition["pairs"]:
            sid = pair["slot_id"]
            manifest = manifests[sid]
            manifest_path = output / "supervision" / sid.split(":", 1)[-1] / "record.json"
            if produce_encodings:
                persist(manifest_path.parent, manifest)
            else:
                require(
                    reader.read(entry(manifest_path)) == manifest, "frozen field authority changed"
                )
            manifest_entries[sid] = entry(manifest_path)
        # imap preserves registered order; only this parent publishes immutable bytes.
        ordered = [p["slot_id"] for p in definition["pairs"]]
        with multiprocessing.get_context("fork").Pool(
            min(ENCODING_WORKERS, len(ordered)),
            initializer=_encoding_worker_init,
            initargs=(tokenizer, originals, manifests, output, produce_encodings),
        ) as workers:
            for sid, encoding in zip(
                ordered,
                workers.imap(_encode_registered_original, ordered, chunksize=1),
                strict=True,
            ):
                encoding_path = output / "encoding" / sid.split(":", 1)[-1] / "record.json"
                if produce_encodings:
                    persist(encoding_path.parent, encoding)
                encodings[sid], encoding_entries[sid] = encoding, entry(encoding_path)
    else:
        require(produce_encodings, "training cannot consume an unresolved all-authority barrier")
        encodings = {
            sid: dict(
                schema="v13_encoding_not_started.v1",
                encoding_admitted=False,
                encoding_started=False,
                failures=[dict(reason="whole_pool_authority_barrier_unresolved")],
            )
            for sid in originals
        }
    # Character inventories are reporting only, not fields added to immutable token receipts.
    profile_encodings = copy.deepcopy(encodings)
    for pair in definition["pairs"]:
        sid = pair["slot_id"]
        value = profile_encodings[sid]
        value["original_public_content_characters"] = sum(
            len(s["text"]) for s in views[sid]["segments"] if s["kind"] == "public_content"
        )
        value["positive_public_content_characters"] = (
            sum(s["end"] - s["start"] for s in manifests[sid]["positive_content_spans"])
            if sid in manifests
            else None
        )
    support = support_profile(
        list(task_slots), task_slots, mappings, profile_encodings, projection_failures=failures
    )
    source_manifest = snapshot_manifest(original_plan["snapshot"])
    require(
        source_manifest["id"] == original_plan["snapshot_id"], "original snapshot identity changed"
    )
    return dict(
        plan=plan,
        definition=definition,
        original_plan=original_plan,
        seal=seal,
        support=support,
        encodings=encodings,
        encoding_entries=encoding_entries,
        manifest_entries=manifest_entries,
        mappings=mappings,
        tokenizer_binding=token_binding,
        source_manifest=source_manifest,
    )


def produce(output):
    output, reader = Path(output).resolve(), Reader()
    result = _collect(output, reader, produce_encodings=True)
    support, plan = result["support"], result["plan"]
    persist(output / "material/support", support)
    ready = support["material_complete"] and support["exploratory_training_admitted"]
    body = dict(
        schema="v13_material_freeze_result.v1",
        protocol_id=plan["protocol_identity"],
        registration_id=plan["id"],
        support=entry(output / "material/support/record.json"),
        N=support["N"],
        package_count=support["package_count"],
        training_admitted=ready,
        phase="READY_EXPLORATORY"
        if ready
        else "BLOCKED_REPRESENTATION_OR_MAPPING"
        if not support["material_complete"]
        else "DEGENERATE_SUPPORT",
        no_fixed_original_removed=True,
        API_calls=0,
        GPU_used=False,
    )
    if ready:
        binding = bound(
            dict(
                schema=BINDING_SCHEMA,
                protocol_id=plan["protocol_identity"],
                registration_id=plan["id"],
                generation_root=str(output),
                material_root=str(output),
                registration=entry(output / "registration/record.json"),
                definition=plan["definition"],
                completion_seal=entry(output / "completion_seal/record.json"),
                support_manifest=entry(output / "material/support/record.json"),
                supervision_manifests=result["manifest_entries"],
                encodings=result["encoding_entries"],
                tokenizer_binding=list(result["tokenizer_binding"]),
                fixed_arms=["Static", "Manual+", "Manual-", "C-only", "Full"],
                fixed_seeds=[11, 29, 47],
                actual_data_only=True,
                feedback_denominator=700,
                no_extra_minimum_N=True,
            )
        )
        persist(output / "material/binding", binding)
        body["binding"] = entry(output / "material/binding/record.json")
    result = bound(body)
    persist(output / "material/result", result)
    return result


def load_training_pool(binding_path):
    binding_path, reader = Path(binding_path).resolve(), Reader()
    binding = checked(read_json(binding_path), BINDING_SCHEMA)
    output = Path(binding["material_root"]).resolve()
    require(
        binding_path == output / "material/binding/record.json",
        "registered V13 material binding coordinate required",
    )
    for key, relative in (
        ("registration", "registration/record.json"),
        ("definition", "definition/record.json"),
        ("completion_seal", "completion_seal/record.json"),
        ("support_manifest", "material/support/record.json"),
    ):
        checked(reader.read(binding[key], output / relative))
    result = _collect(output, reader, produce_encodings=False)
    support, plan = result["support"], result["plan"]
    require(
        binding["protocol_id"] == plan["protocol_identity"]
        and binding["registration_id"] == plan["id"]
        and reader.read(binding["support_manifest"]) == support
        and support["material_complete"]
        and support["exploratory_training_admitted"]
        and binding["encodings"] == result["encoding_entries"]
        and binding["supervision_manifests"] == result["manifest_entries"]
        and tuple(binding["tokenizer_binding"]) == result["tokenizer_binding"],
        "no partial, selected, substituted or unencoded V13 pool may train",
    )
    packages, rows, chi = [], {}, {}
    for task in support["training_task_ids"]:
        part = support["task_support"][task]
        chi[task] = part["chi"]
        for sid in part["candidate_slot_ids"]:
            encoded = result["encodings"][sid]
            rows[sid] = encoded["rows"]
            packages.append(
                dict(
                    package_id=sid,
                    task_id=task,
                    state_id=result["mappings"][task]["state_by_slot"][sid],
                    whole_package_target_tokens=encoded["L_P"],
                    fused=False,
                )
            )
    pool = VerifiedPool(
        support["training_task_ids"],
        packages,
        rows,
        binding_id=binding["id"],
        chi=chi,
        production=True,
    )
    pool._manifest.registration.validator_binding_id = (
        "v13_fixed_population_fixed_field_authority.v1"
    )
    pool.material_schema, pool.conditional_scope_verified = BINDING_SCHEMA, True
    pool.registered_singleton_tasks = tuple(support["registered_singleton_tasks"])
    pool.execution_plan = support["execution_plan"]
    pool.support_manifest, pool.capability_profile = support, support["capability_profile"]
    pool.tokenizer_binding = result["tokenizer_binding"]
    pool.source_manifest_sha256 = digest(result["source_manifest"])
    pool.generation_launch_id = pool.original_material_protocol_id = plan["protocol_identity"]
    pool.public_input_parent_id = result["original_plan"]["original"]["id"]
    pool.verified_file_count = len(reader.cache)
    return pool


freeze_material = produce
