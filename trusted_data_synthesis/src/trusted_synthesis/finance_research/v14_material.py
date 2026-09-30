"""Join fixed V14 authorities and state-independent caches, never a training subset.

Existing accepted V13 judgments are inherited through the uniform append-only
representation review. Each predeclared residual has exactly one new authority.
Encoding may precede mapping; only the complete original 2468/744 pool can bind.
"""

from __future__ import annotations

import copy
import json
import sqlite3
from collections import Counter
from fractions import Fraction
from pathlib import Path

from .contracts import digest
from .probe_budget import _acknowledged_unknowns, _request_record_digest
from .storage import snapshot_manifest
from .v6_collection import bound, persist, require
from .v8_training_driver import VerifiedPool
from .v13_material import support_profile
from .v13_material_registration import checked, entry, read_ref

BINDING_SCHEMA = "v14_material_binding.v1"


def conditional_bounds(task_slots, mappings):
    """Separate conditional bounds; never replace an unmeasured full-domain value."""
    known = {
        t: m for t, m in mappings.items() if m is not None and m.get("mapping_status") == "complete"
    }
    require(set(known) <= set(task_slots), "resolved tasks must belong to the fixed population")
    N = len(task_slots)
    degrees = flexible = mixed = state_count = 0
    plus = minus = Fraction(0)
    for task, value in known.items():
        assignments, chi = value["state_by_slot"], value["chi_by_state"]
        require(
            set(assignments) == set(task_slots[task]) and set(assignments.values()) == set(chi),
            "same full-task partition required",
        )
        counts = Counter(assignments.values())
        state_count += len(counts)
        degrees += len(counts) - 1
        flexible += int(len(counts) > 1)
        mixed += int(set(chi.values()) == {0, 1})
        if len(task_slots[task]) == 1:
            require(list(chi.values()) == [None], "registered real singleton remains static")
            continue
        require(
            all(type(c) is int and c in (0, 1) for c in chi.values()), "unknown chi is not zero"
        )
        p = sum(
            (Fraction(n, len(task_slots[task])) for z, n in counts.items() if chi[z] == 1),
            Fraction(0),
        )
        plus += p * (1 - p) / (1 + p) / N
        minus += p * (1 - p) / (2 - p) / N
    unresolved = set(task_slots) - set(known)
    upper_extra = sum(len(task_slots[t]) - 1 for t in unresolved)
    flexible_extra = sum(len(task_slots[t]) > 1 for t in unresolved)
    return bound(
        dict(
            schema="v14_conditional_resolved_support_bounds.v1",
            fixed_tasks=N,
            fixed_packages=sum(map(len, task_slots.values())),
            resolved_tasks=len(known),
            resolved_packages=sum(len(task_slots[t]) for t in known),
            resolved_states=state_count,
            unresolved_tasks=len(unresolved),
            D_pi_interval=[degrees, degrees + upper_extra],
            multi_state_task_interval=[flexible, flexible + flexible_extra],
            chi_flexible_task_interval=[mixed, mixed + flexible_extra],
            known_mu_weighted_TV_plus=str(plus),
            known_mu_weighted_TV_minus=str(minus),
            unknown_task_dose_not_imputed=True,
            conditional_on_all_existing_partitions_and_chi_remaining_unchanged=True,
            full_domain_measurements_replaced=False,
            statistical_power_established=False,
            training_authorized=False,
        )
    )


def freeze_offline_profile(output):
    """Describe the newly resolved subset without imputing any future response."""
    output = Path(output).resolve()
    review_ref = entry(output / "representation_review/summary/record.json")
    review = read_ref(review_ref)
    definition = read_ref(review["source_v13_definition"])
    mappings = {
        item["task_id"]: read_ref(item["record"])["inspection"]
        for item in review["mapping_authority_refs"]
    }
    for item in review["inherited_singleton_refs"]:
        mappings[item["task_id"]] = read_ref(item["record"])
    result = bound(
        dict(
            schema="v14_offline_resolved_profile.v1",
            representation_review=review_ref,
            fixed_population=review["source_v13_definition"],
            conditional_bounds=conditional_bounds(definition["fixed_task_slots"], mappings),
            no_full_population_null_overwritten=True,
            no_training_subset_created=True,
            API_calls=0,
            GPU_used=False,
        )
    )
    persist(output / "offline_profile", result)
    return result


def read_context(output):
    from .v14_material_registration import checked_plan

    output = Path(output).resolve()
    plan = checked_plan(output)
    definition = read_ref(plan["definition"])
    review = read_ref(definition["representation_review"])
    parent = read_ref(definition["source_v13_definition"])
    task_slots = definition["fixed_task_slots"]
    slots = definition["candidate_slot_ids"]
    require(
        definition["parent_fixed_population_id"] == parent["id"]
        and plan["protocol_identity"] == definition["id"]
        and len(task_slots) == 744
        and len(slots) == len(set(slots)) == 2468
        and slots == [p["slot_id"] for p in parent["pairs"]]
        and task_slots == {t["task_id"]: t["slot_ids"] for t in parent["tasks"]}
        and Counter(slots) == Counter(s for members in task_slots.values() for s in members),
        "same complete original 2468/744 population required, never the resolved subset",
    )
    return plan, definition, review, parent


def new_annotations(output, plan):
    """Check only the new exact matrix against its original read-only wallet rows."""
    from .v14_material_protocol import checked_request
    from .v14_material_provider import paid_record, restore_settled

    output = Path(output).resolve()
    seal = checked(output / "completion_seal/record.json")
    jobs = plan["jobs"]
    require(
        seal["schema"] == "v14_material_completion_seal.v1"
        and seal["registration_id"] == plan["id"]
        and seal["protocol_id"] == plan["protocol_identity"]
        and seal["all_registered_jobs_have_authentic_terminals"] is True
        and seal["expected_calls"] == len(jobs) == len(seal["terminals"])
        and 0 < len(jobs) <= 323,
        "whole registered residual matrix requires authentic terminal records",
    )
    database = Path(plan["budget_database"]).resolve()
    db = sqlite3.connect(database.as_uri() + "?mode=ro", uri=True)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA query_only=ON")
    db.execute("BEGIN")
    results, returns, unknowns = {}, 0, 0
    try:
        config = json.loads(
            db.execute("SELECT value FROM metadata WHERE key='config'").fetchone()[0]
        )
        require(digest(config) == plan["budget_config_sha256"], "same original wallet required")
        acknowledgments = {a["invocation_id"]: a for a in _acknowledged_unknowns(db, config)}
        for job, ref in zip(jobs, seal["terminals"], strict=True):
            terminal = read_ref(ref)
            record = read_ref(terminal["record"])
            request = checked_request(read_ref(job["request"]))
            purpose = job["purpose"]
            require(
                terminal["schema"] == "v14_material_terminal.v1"
                and terminal["episode_id"] == job["episode_id"] == request["episode_id"]
                and terminal["registration_id"] == plan["id"]
                and request["protocol_id"] == plan["protocol_identity"]
                and terminal["purpose"] == purpose
                and terminal["task_id"] == job["task_id"] == request["task_id"],
                "new material terminal identity or registered order changed",
            )
            if terminal["terminal_kind"] == "paid_model_return":
                row = db.execute(
                    "SELECT * FROM requests WHERE invocation_id=?",
                    (record["artifact"]["budget_invocation_id"],),
                ).fetchone()
                require(row is not None, "new settled material receipt missing")
                row = dict(row)
                artifact = restore_settled(row, request)
                require(
                    record == paid_record(request, artifact, row), "new raw paid authority changed"
                )
                returns += 1
            else:
                require(
                    terminal["terminal_kind"] == "acknowledged_connection_unknown"
                    and record.get("inspection") is None
                    and record.get("actual_model_call_receipt_verified") is False,
                    "no fabricated judgment for a missing response",
                )
                row = db.execute(
                    "SELECT * FROM requests WHERE invocation_id=?", (record["invocation_id"],)
                ).fetchone()
                require(row is not None, "new UNKNOWN absent from shared wallet")
                row, ack = dict(row), acknowledgments.get(record["invocation_id"])
                require(
                    row["state"] == "UNKNOWN"
                    and ack is not None
                    and record["request_id"] == request["id"]
                    and record["request_sha256"] == row["request_sha256"] == job["request_sha256"]
                    and record["acknowledgment_id"] == ack["id"]
                    and record["original_ledger_record_sha256"] == _request_record_digest(row)
                    and record["permanent_reserved_microcny"] == row["reserved_microcny"],
                    "UNKNOWN source and full hold must remain preserved",
                )
                unknowns += 1
            key = purpose, job["slot_id"] if purpose == "projection" else job["task_id"]
            require(key not in results, "only one predeclared new authority per residual")
            results[key] = dict(record=record, reference=terminal["record"], request=request)
    finally:
        db.close()
    require(
        (returns, unknowns) == (seal["actual_returns"], seal["network_unknowns"]),
        "actual model responses and unknowns are distinct",
    )
    return seal, results


def projection_authorities(review, new):
    """Predeclared sources only: no best-of comparison with rejected old outputs."""
    authorities = {}
    for key in ("inherited_projection_authority_refs", "derived_projection_authority_refs"):
        for value in review[key]:
            sid = value["slot_id"]
            require(sid not in authorities, "projection source collision")
            authorities[sid] = value
    for sid in review["residual_projection_slot_ids"]:
        item = new["projection", sid]
        inspection = item["record"].get("inspection")
        if inspection and inspection.get("usable") is True:
            require(sid not in authorities, "new projection cannot replace a settled authority")
            authorities[sid] = dict(
                slot_id=sid,
                task_id=item["record"]["task_id"],
                authority_kind="V14_completion_only",
                record=item["reference"],
            )
    return authorities


def task_mappings(review, new):
    mappings, authorities = {}, {}
    for value in review["mapping_authority_refs"]:
        task = value["task_id"]
        record = read_ref(value["record"])
        require(task not in mappings, "one inherited mapping authority per task")
        require(
            record["schema"] == "v14_derived_mapping.v1"
            and record["usable"] is True
            and len(record["slot_ids"]) >= 2,
            "accepted derived authority must be a genuine multi-package mapping",
        )
        # Consumption metadata only, not a new state/chi judgment or old-record edit.
        interpreted = copy.deepcopy(record["inspection"])
        interpreted["deterministic_singleton"] = False
        interpreted["chi_status"] = "semantically_annotated"
        mappings[task], authorities[task] = interpreted, value["record"]
    for value in review["inherited_singleton_refs"]:
        task = value["task_id"]
        require(task not in mappings, "true singleton cannot replace a multi-package mapping")
        mappings[task], authorities[task] = read_ref(value["record"]), value["record"]
    for task in review["residual_mapping_task_ids"]:
        require(task not in mappings, "no best-of old/new mapping authority")
        item = new["mapping", task]
        mappings[task], authorities[task] = item["record"].get("inspection"), item["reference"]
    return mappings, authorities


def token_independent_profile(task_slots, mappings, encodings, missing_projections):
    """Reuse unchanged finite weighting rules; report real deferred/started counts."""
    profile = support_profile(
        list(task_slots),
        task_slots,
        mappings,
        encodings,
        projection_failures=[
            dict(slot_id=s, reason="predeclared_projection_unresolved") for s in missing_projections
        ],
    )
    capability = {k: v for k, v in profile["capability_profile"].items() if k != "id"}
    capability["schema"] = "v14_conditional_capability_profile.v1"
    capability["encoding_started_packages"] = sum(
        e.get("encoding_started", e.get("encoding_admitted", False)) for e in encodings.values()
    )
    body = {k: v for k, v in profile.items() if k != "id"}
    body["schema"] = "v14_conditional_support_manifest.v1"
    body["capability_profile"] = bound(capability)
    body["encoding_independent_of_mapping"] = True
    return bound(body)


def _char_union(spans):
    by_segment = {}
    for span in spans:
        by_segment.setdefault(span["original_segment_id"], []).append((span["start"], span["end"]))
    total = 0
    for intervals in by_segment.values():
        last = -1
        for start, end in sorted(intervals):
            total += max(0, end - max(start, last))
            last = max(last, end)
    return total


def collect(output, *, prepared=None):
    from .v14_encoding_cache import load_cache

    output = Path(output).resolve()
    if prepared is None:
        plan, definition, review, parent = read_context(output)
        seal, annotations = new_annotations(output, plan)
    else:
        plan, definition, review, parent, seal, annotations = prepared
    authorities = projection_authorities(review, annotations)
    mappings, mapping_refs = task_mappings(review, annotations)
    cache = load_cache(output / "encoding_cache", require_complete=False)
    task_slots = definition["fixed_task_slots"]
    slots = definition["candidate_slot_ids"]
    require(set(mappings) == set(task_slots), "no removed fixed task or missing mapping outcome")
    require(
        set(cache["manifests"]) == set(authorities),
        "cache must reflect every established authority",
    )
    for sid, manifest in cache["manifests"].items():
        require(
            manifest["authority_record"] == authorities[sid]["record"]
            and manifest["projection_authority"] == authorities[sid]["authority_kind"]
            and manifest["population_id"] == parent["id"],
            "old mask or another authority cannot be used for a new field source",
        )
    inherited = read_ref(definition["source_material_support"])
    original_coverage = inherited["capability_profile"]["package_reason_coverage"]
    encodings = copy.deepcopy(cache["encodings"])
    for sid in slots:
        if sid not in encodings:
            encodings[sid] = dict(
                schema="v14_encoding_unavailable.v1",
                encoding_admitted=False,
                encoding_started=False,
                failures=[dict(reason="supervision_authority_unresolved")],
            )
        encodings[sid]["original_public_content_characters"] = original_coverage[sid][
            "raw_characters"
        ]
        encodings[sid]["positive_public_content_characters"] = (
            _char_union(cache["manifests"][sid]["positive_content_spans"])
            if sid in cache["manifests"]
            else None
        )
    support = token_independent_profile(
        task_slots, mappings, encodings, [s for s in slots if s not in authorities]
    )
    original_plan = read_ref(parent["inputs"]["source_v10_plan"])
    snapshot = snapshot_manifest(original_plan["snapshot"])
    require(
        snapshot["id"] == original_plan["snapshot_id"], "fixed original source snapshot changed"
    )
    return dict(
        plan=plan,
        definition=definition,
        review=review,
        parent=parent,
        seal=seal,
        mappings=mappings,
        mapping_refs=mapping_refs,
        authorities=authorities,
        support=support,
        cache=cache,
        original_plan=original_plan,
        snapshot=snapshot,
    )


def produce(output, *, prepared=None):
    output = Path(output).resolve()
    result = collect(output, prepared=prepared)
    support, plan, cache = result["support"], result["plan"], result["cache"]
    persist(output / "material/support", support)
    persist(
        output / "material/conditional_bounds",
        conditional_bounds(result["definition"]["fixed_task_slots"], result["mappings"]),
    )
    ready = support["material_complete"] and support["exploratory_training_admitted"]
    body = dict(
        schema="v14_material_freeze_result.v1",
        protocol_id=plan["protocol_identity"],
        registration_id=plan["id"],
        support=entry(output / "material/support/record.json"),
        N=744,
        package_count=2468,
        training_admitted=ready,
        phase="READY_EXPLORATORY"
        if ready
        else "BLOCKED_COMPLETE_MATERIAL"
        if not support["material_complete"]
        else "DEGENERATE_SUPPORT",
        all_originals_retained=True,
        no_subset_training=True,
        API_calls=0,
        GPU_used=False,
    )
    if ready:
        binding = bound(
            dict(
                schema=BINDING_SCHEMA,
                protocol_id=plan["protocol_identity"],
                registration_id=plan["id"],
                material_root=str(output),
                registration=entry(output / "registration/record.json"),
                definition=plan["definition"],
                completion_seal=entry(output / "completion_seal/record.json"),
                representation_review=result["definition"]["representation_review"],
                support_manifest=entry(output / "material/support/record.json"),
                supervision_manifests=cache["manifest_entries"],
                encodings=cache["encoding_entries"],
                mapping_authorities=result["mapping_refs"],
                tokenizer_binding=list(cache["tokenizer_binding"]),
                fixed_arms=["Static", "Manual+", "Manual-", "C-only", "Full"],
                fixed_seeds=[11, 29, 47],
                actual_data_only=True,
                no_extra_minimum_N=True,
                feedback_denominator=700,
                state_independent_cache=True,
            )
        )
        persist(output / "material/binding", binding)
        body["binding"] = entry(output / "material/binding/record.json")
    final = bound(body)
    persist(output / "material/result", final)
    return final


def complete_material(output):
    """Append only newly resolved masks; finish their caches before the single join."""
    from . import v14_encoding_cache as cache

    output = Path(output).resolve()
    plan, definition, review, parent = read_context(output)
    seal, annotations = new_annotations(output, plan)
    authorities = projection_authorities(review, annotations)
    cache_root = output / "encoding_cache"
    registration, _ = cache._registration(cache_root)
    _, existing = cache._revisions(cache_root, registration)
    additions = []
    for sid, value in authorities.items():
        if sid in existing:
            require(
                existing[sid]["authority_record"] == value["record"]
                and existing[sid]["projection_authority"] == value["authority_kind"],
                "known cached supervision cannot be overwritten or selected again",
            )
        else:
            additions.append(
                dict(
                    slot_id=sid,
                    projection_authority=value["authority_kind"],
                    authority_record=value["record"],
                )
            )
    require(set(existing) <= set(authorities), "an established authority cannot disappear")
    if additions:
        cache.append_authorities(cache_root, additions)
        cache.run(cache_root, workers=8)
    prepared = plan, definition, review, parent, seal, annotations
    return produce(output, prepared=prepared)


def load_training_pool(binding_path):
    binding_path = Path(binding_path).resolve()
    binding = checked(binding_path)
    require(binding["schema"] == BINDING_SCHEMA, "genuine V14 binding required")
    output = Path(binding["material_root"]).resolve()
    require(binding_path == output / "material/binding/record.json", "fixed V14 binding location")
    result = collect(output)
    cache, support, plan = result["cache"], result["support"], result["plan"]
    require(
        binding["registration_id"] == plan["id"]
        and binding["protocol_id"] == plan["protocol_identity"]
        and read_ref(binding["support_manifest"]) == support
        and support["material_complete"]
        and support["exploratory_training_admitted"]
        and binding["encodings"] == cache["encoding_entries"]
        and binding["supervision_manifests"] == cache["manifest_entries"]
        and binding["mapping_authorities"] == result["mapping_refs"]
        and tuple(binding["tokenizer_binding"]) == tuple(cache["tokenizer_binding"]),
        "complete fixed material sources, cache and finite profile must match",
    )
    packages, rows, chi = [], {}, {}
    for task in support["training_task_ids"]:
        part = support["task_support"][task]
        chi[task] = part["chi"]
        for sid in part["candidate_slot_ids"]:
            encoding = cache["encodings"][sid]
            rows[sid] = encoding["rows"]
            packages.append(
                dict(
                    package_id=sid,
                    task_id=task,
                    state_id=result["mappings"][task]["state_by_slot"][sid],
                    whole_package_target_tokens=encoding["L_P"],
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
    pool._manifest.registration.validator_binding_id = "v14_fixed_authority_and_representation.v1"
    pool.material_schema, pool.conditional_scope_verified = BINDING_SCHEMA, True
    pool.registered_singleton_tasks = tuple(support["registered_singleton_tasks"])
    pool.execution_plan = support["execution_plan"]
    pool.support_manifest, pool.capability_profile = support, support["capability_profile"]
    pool.tokenizer_binding = tuple(cache["tokenizer_binding"])
    pool.source_manifest_sha256 = digest(result["snapshot"])
    pool.generation_launch_id = pool.original_material_protocol_id = plan["protocol_identity"]
    pool.public_input_parent_id = result["original_plan"]["original"]["id"]
    pool.verified_file_count = len(cache["encoding_entries"]) + len(cache["manifest_entries"])
    return pool
