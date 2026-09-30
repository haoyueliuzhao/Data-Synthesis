"""Six-task successor binding; preserve the original prefix and all 738 authorities.

Historical registrations are checked against their actual frozen source tree, not
against the later successor's code. This does not edit or re-register the past.
"""

from __future__ import annotations

import copy
import json
import sqlite3
from pathlib import Path

from .contracts import digest
from .probe_budget import _acknowledged_unknowns, _request_record_digest
from .v6_collection import bound, persist, require, sha
from .v8_training_driver import VerifiedPool
from .v9_conditional_training import build_task_schedule, execution_plan
from .v13_material_registration import checked, entry, read_ref
from .v14_material import conditional_bounds, token_independent_profile
from .v15_material import authority_mapping
from .v15_prefix_material import PrefixPool, _source_material, material_order_identity

BINDING_SCHEMA = "v16_six_task_complete_material_binding.v1"


def historical_context(definition):
    """Read the complete old authorities without reinterpreting their judgments."""
    source = Path(definition["source_root"]).resolve()
    plan = read_ref(definition["source_registration"])
    old = read_ref(plan["definition"])
    review = read_ref(old["mapping_review"])
    seal = read_ref(definition["source_completion_seal"])
    support = read_ref(definition["source_support"])
    frozen = (
        Path(definition["source_frozen_root"])
        / "trusted_data_synthesis/src/trusted_synthesis/finance_research"
    )
    require(
        definition["source_registration"] == entry(source / "registration/record.json")
        and definition["source_completion_seal"] == entry(source / "completion_seal/record.json")
        and definition["source_support"] == entry(source / "material/support/record.json")
        and plan["schema"] == "v15_fixed_mapping_plan.v1"
        and all(sha(frozen / name) == value for name, value in plan["source_bindings"].items())
        and seal["registration_id"] == plan["id"]
        and seal["protocol_id"] == plan["protocol_identity"] == old["id"]
        and seal["all_registered_jobs_have_authentic_terminals"] is True
        and seal["actual_returns"] == seal["expected_calls"] == len(plan["jobs"]) == 36
        and seal["network_unknowns"] == 0,
        "genuine completed V15 registration, frozen source and all original terminals required",
    )
    task_slots = old["fixed_task_slots"]
    mappings, authorities = {}, {}
    for field in ("inherited_mapping_authority_refs", "derived_mapping_authority_refs"):
        for value in review[field]:
            task = value["task_id"]
            require(task not in mappings, "historical authority must remain unique")
            mappings[task] = authority_mapping(value, task_slots)
            authorities[task] = value["record"]
    for job, ref in zip(plan["jobs"], seal["terminals"], strict=True):
        terminal = read_ref(ref)
        record = read_ref(terminal["record"])
        task = job["task_id"]
        require(
            task not in mappings
            and task == terminal["task_id"]
            and terminal["registration_id"] == plan["id"]
            and terminal["terminal_kind"] == "paid_model_return"
            and record["actual_model_call_receipt_verified"] is True
            and record["request"] == read_ref(job["request"]),
            "original returned decision and original failure must remain unchanged",
        )
        mappings[task] = copy.deepcopy(record["inspection"])
        authorities[task] = terminal["record"]
    good = {
        t
        for t, value in mappings.items()
        if value
        and value.get("mapping_status") == "complete"
        and value.get("mapping_admitted") is True
    }
    # Genuine deterministic singletons predate paid mapping_admitted fields.
    good.update(
        t for t, value in mappings.items() if value and value.get("deterministic_singleton") is True
    )
    failed = set(task_slots) - good
    require(
        task_slots == definition["fixed_task_slots"]
        and set(mappings) == set(task_slots)
        and len(task_slots) == support["N"] == 744
        and sum(map(len, task_slots.values())) == support["package_count"] == 2468
        and len(good) == 738
        and good == set(support["task_support"])
        and len(failed) == 6
        and sum(len(task_slots[t]) for t in failed) == 24
        and failed == set(definition["fixed_unresolved_task_ids"])
        and {t: authorities[t] for t in good} == definition["inherited_mapping_authorities"]
        and {t: authorities[t] for t in failed} == definition["previous_failed_authorities"],
        "only the fixed six may gain a successor source; original 738 authority cannot change",
    )
    return dict(
        source=source,
        plan=plan,
        definition=old,
        support=support,
        frozen=frozen,
        mappings=mappings,
        authorities=authorities,
        failed=failed,
    )


def load_historical_prefix(definition, *, history=None):
    """Verify original mask/cache/order without requiring obsolete code to be current."""
    history = history or historical_context(definition)
    ref = definition["prefix_material_binding"]
    binding = read_ref(ref)
    require(
        ref == entry(history["source"] / "prefix_material/binding/record.json")
        and binding["schema"] == "v15_prior_prefix_binding.v1"
        and binding["prefix_only_admitted"] is True
        and binding["full_five_arm_admitted"] is False
        and binding["mapping_plan"] == definition["source_registration"]
        and binding["mapping_plan_id"] == history["plan"]["id"]
        and all(
            sha(history["frozen"] / name) == value
            for name, value in binding["source_bindings"].items()
        ),
        "same historical prefix binding and actual frozen implementation required",
    )
    material = _source_material(binding["source_root"])
    cache = material["cache"]
    require(
        binding["task_ids"] == material["task_ids"] == list(definition["fixed_task_slots"])
        and binding["packages"] == material["packages"]
        and binding["encodings"] == cache["encoding_entries"]
        and binding["supervision_manifests"] == cache["manifest_entries"]
        and tuple(binding["tokenizer_binding"]) == cache["tokenizer_binding"]
        and binding["execution_plan"] == execution_plan(744)
        and binding["prefix_steps_per_seed"] == 298
        and sum(p["whole_package_target_tokens"] for p in material["packages"]) == 504276,
        "same tasks, packages, original rows, targets, tokenizer and schedule required",
    )
    for seed in (11, 29, 47):
        require(
            read_ref(binding["schedules"][str(seed)])
            == bound(build_task_schedule(material["task_ids"], seed)),
            "original prefix schedule changed",
        )
    pool = PrefixPool(
        task_ids=material["task_ids"],
        packages=material["packages"],
        encodings=cache["encodings"],
        binding_ref=ref,
        token_binding=cache["tokenizer_binding"],
        material_order_id=binding["material_order_id"],
    )
    pool.supervision_manifest_refs, pool.encoding_refs = (
        cache["manifest_entries"],
        cache["encoding_entries"],
    )
    pool.original_student_assets = binding["original_student_assets"]
    pool.source_snapshot_sha256 = binding["source_snapshot_sha256"]
    pool.public_input_parent_id = material["original_plan"]["original"]["id"]
    return pool


def successor_results(output, plan, definition):
    """Consume six explicit terminal sources; missing/failed returns never mean chi=0."""
    seal = checked(Path(output) / "completion_seal/record.json")
    require(
        seal["registration_id"] == plan["id"]
        and seal["protocol_id"] == plan["protocol_identity"]
        and seal["all_registered_jobs_have_authentic_terminals"] is True
        and seal["expected_calls"] == len(seal["terminals"]) == len(plan["jobs"]) == 6,
        "all six authentic successor terminals required",
    )
    results = {}
    for job, ref in zip(plan["jobs"], seal["terminals"], strict=True):
        terminal = read_ref(ref)
        record = read_ref(terminal["record"])
        verify_successor_receipt(plan, job, terminal, record)
        task = job["task_id"]
        require(
            task not in results
            and task == terminal["task_id"]
            and terminal["registration_id"] == plan["id"],
            "fixed one-shot task/source identity changed",
        )
        if terminal["terminal_kind"] == "paid_model_return":
            require(
                record["schema"] == "v16_paid_material_annotation.v1"
                and record["actual_model_call_receipt_verified"] is True
                and record["request"] == read_ref(job["request"]),
                "new mapping must have its own authentic one-shot source",
            )
            inspection = copy.deepcopy(record["inspection"])
        else:
            require(
                terminal["terminal_kind"] == "acknowledged_connection_unknown"
                and record.get("inspection") is None,
                "unknown or missing judgment cannot become an admitted mapping",
            )
            inspection = None
        results[task] = dict(inspection=inspection, reference=terminal["record"])
    require(
        set(results) == set(definition["fixed_unresolved_task_ids"]),
        "six-task successor scope changed",
    )
    return seal, results


def verify_successor_receipt(plan, job, terminal, record):
    """New paid/UNKNOWN sources retain their actual six-call ledger evidence."""
    from .v16_provider import paid_record, restore_settled

    db = sqlite3.connect(Path(plan["budget_database"]).resolve().as_uri() + "?mode=ro", uri=True)
    db.row_factory = sqlite3.Row
    try:
        db.execute("PRAGMA query_only=ON")
        config = json.loads(
            db.execute("SELECT value FROM metadata WHERE key='config'").fetchone()[0]
        )
        require(digest(config) == plan["budget_config_sha256"], "same shared wallet required")
        if terminal["terminal_kind"] == "paid_model_return":
            row = db.execute(
                "SELECT * FROM requests WHERE invocation_id=?",
                (record["artifact"]["budget_invocation_id"],),
            ).fetchone()
            require(row is not None, "new six-task paid receipt missing")
            request = read_ref(job["request"])
            require(
                record == paid_record(request, restore_settled(dict(row), request), dict(row)),
                "successor raw response or inspection changed",
            )
        else:
            require(
                terminal["terminal_kind"] == "acknowledged_connection_unknown",
                "unknown successor terminal kind",
            )
            row = db.execute(
                "SELECT * FROM requests WHERE invocation_id=?", (record["invocation_id"],)
            ).fetchone()
            ack = {a["invocation_id"]: a for a in _acknowledged_unknowns(db, config)}.get(
                record["invocation_id"]
            )
            require(
                row is not None and ack is not None,
                "UNKNOWN successor ledger or acknowledgment absent",
            )
            row = dict(row)
            require(
                row["state"] == "UNKNOWN"
                and record["acknowledgment_id"] == ack["id"]
                and record["request_sha256"] == row["request_sha256"] == job["request_sha256"]
                and record["original_ledger_record_sha256"] == _request_record_digest(row)
                and record["permanent_reserved_microcny"] == row["reserved_microcny"],
                "UNKNOWN original hold and failure cannot be relabeled",
            )
    finally:
        db.close()


def collect(output):
    from .v16_registration import checked_plan

    output = Path(output).resolve()
    plan = checked_plan(output)
    definition = read_ref(plan["definition"])
    history = historical_context(definition)
    prefix = load_historical_prefix(definition, history=history)
    seal, replacements = successor_results(output, plan, definition)
    mappings, authorities = history["mappings"], history["authorities"]
    for task, value in replacements.items():
        mappings[task], authorities[task] = value["inspection"], value["reference"]
    coverage = history["support"]["capability_profile"]["package_reason_coverage"]
    encodings = copy.deepcopy(prefix._encodings)
    for sid, encoded in encodings.items():
        encoded["original_public_content_characters"] = coverage[sid]["raw_characters"]
        encoded["positive_public_content_characters"] = coverage[sid]["approved_characters"]
    support = token_independent_profile(definition["fixed_task_slots"], mappings, encodings, [])
    body = {k: v for k, v in support.items() if k != "id"}
    body.update(
        schema="v16_complete_support_manifest.v1",
        prefix_binding=definition["prefix_material_binding"],
        supervision_and_encoding_unchanged=True,
        original_738_authorities_unchanged=True,
    )
    support = bound(body)
    return dict(
        plan=plan,
        definition=definition,
        prefix=prefix,
        seal=seal,
        mappings=mappings,
        mapping_authorities=authorities,
        support=support,
    )


def binding_body(output, value):
    plan, definition, prefix = value["plan"], value["definition"], value["prefix"]
    return dict(
        schema=BINDING_SCHEMA,
        material_root=str(Path(output).resolve()),
        registration_id=plan["id"],
        protocol_id=plan["protocol_identity"],
        registration=entry(Path(output) / "registration/record.json"),
        definition=plan["definition"],
        original_registration=definition["source_registration"],
        prospective_intent=definition["prospective_intent"],
        completion_seal=entry(Path(output) / "completion_seal/record.json"),
        prefix_material_binding=definition["prefix_material_binding"],
        material_order_id=prefix.material_order_id,
        support_manifest=entry(Path(output) / "material/support/record.json"),
        mapping_authorities=value["mapping_authorities"],
        inherited_mapping_authorities=definition["inherited_mapping_authorities"],
        previous_failed_authorities=definition["previous_failed_authorities"],
        successor_task_ids=definition["fixed_unresolved_task_ids"],
        supervision_manifests=prefix.supervision_manifest_refs,
        encodings=prefix.encoding_refs,
        tokenizer_binding=list(prefix.tokenizer_binding),
        original_prefix_not_retrained=True,
        fixed_arms=["Static", "Manual+", "Manual-", "C-only", "Full"],
        fixed_seeds=[11, 29, 47],
        feedback_denominator=700,
        historical_registration_rewritten=False,
    )


def produce(output):
    output = Path(output).resolve()
    value = collect(output)
    support = value["support"]
    persist(output / "material/support", support)
    persist(
        output / "material/conditional_bounds",
        conditional_bounds(value["definition"]["fixed_task_slots"], value["mappings"]),
    )
    ready = support["material_complete"] and support["exploratory_training_admitted"]
    result = dict(
        schema="v16_complete_material_result.v1",
        registration_id=value["plan"]["id"],
        protocol_id=value["plan"]["protocol_identity"],
        N=744,
        package_count=2468,
        phase="READY_EXPLORATORY"
        if ready
        else "BLOCKED_MAPPING"
        if not support["material_complete"]
        else "DEGENERATE_SUPPORT",
        training_admitted=ready,
        no_subset_training=True,
        original_738_authorities_unchanged=True,
        support=entry(output / "material/support/record.json"),
        API_calls=0,
        GPU_used=False,
    )
    if ready:
        persist(output / "material/binding", bound(binding_body(output, value)))
        result["binding"] = entry(output / "material/binding/record.json")
    result = bound(result)
    persist(output / "material/result", result)
    return result


def load_training_pool(binding_path):
    path = Path(binding_path).resolve()
    binding = checked(path)
    require(
        binding["schema"] == BINDING_SCHEMA
        and path == Path(binding["material_root"]) / "material/binding/record.json",
        "genuine V16 complete binding required",
    )
    value = collect(binding["material_root"])
    prefix, support = value["prefix"], value["support"]
    require(
        support["material_complete"]
        and support["exploratory_training_admitted"]
        and read_ref(binding["support_manifest"]) == support
        and binding == bound(binding_body(binding["material_root"], value)),
        "unchanged complete binding, inherited authorities and original supervision required",
    )
    packages = [
        dict(p, state_id=value["mappings"][p["task_id"]]["state_by_slot"][p["package_id"]])
        for p in prefix.packages
    ]
    pool = VerifiedPool(
        prefix.task_ids,
        packages,
        {sid: e["rows"] for sid, e in prefix._encodings.items()},
        binding_id=binding["id"],
        chi={t: value["mappings"][t]["chi_by_state"] for t in prefix.task_ids},
        production=True,
    )
    require(
        material_order_identity(
            prefix.task_ids,
            [
                {k: p[k] for k in ("package_id", "task_id", "whole_package_target_tokens", "fused")}
                for p in packages
            ],
            prefix._encodings,
        )
        == prefix.material_order_id,
        "genuine state names cannot alter execution order",
    )
    pool._manifest.registration.validator_binding_id = (
        "v16_six_successor_states_original_supervision.v1"
    )
    pool.material_schema, pool.conditional_scope_verified = BINDING_SCHEMA, True
    pool.registered_singleton_tasks = tuple(support["registered_singleton_tasks"])
    pool.execution_plan, pool.support_manifest = support["execution_plan"], support
    pool.capability_profile, pool.tokenizer_binding = (
        support["capability_profile"],
        prefix.tokenizer_binding,
    )
    pool.source_manifest_sha256, pool.public_input_parent_id = (
        prefix.source_snapshot_sha256,
        prefix.public_input_parent_id,
    )
    pool.generation_launch_id = pool.original_material_protocol_id = value["plan"][
        "protocol_identity"
    ]
    pool.material_order_id, pool.prefix_binding_ref = (
        prefix.material_order_id,
        prefix.prefix_binding_ref,
    )
    pool.supervision_manifest_refs, pool.encoding_refs = (
        prefix.supervision_manifest_refs,
        prefix.encoding_refs,
    )
    pool.verified_file_count = len(prefix.encoding_refs) + len(prefix.supervision_manifest_refs)
    return pool
