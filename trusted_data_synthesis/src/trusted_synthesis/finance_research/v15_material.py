"""Full state-aware join after fixed54 adjudication, separate from prefix admission."""

from __future__ import annotations

import copy
import json
import sqlite3
from pathlib import Path

from .contracts import digest
from .probe_budget import _acknowledged_unknowns, _request_record_digest
from .v6_collection import bound, persist, require
from .v8_training_driver import VerifiedPool
from .v13_material_registration import checked, entry, read_ref
from .v14_material import conditional_bounds, token_independent_profile
from .v15_prefix_material import load_prefix_pool, material_order_identity

BINDING_SCHEMA = "v15_complete_material_binding.v1"


def mapping_results(output, plan):
    from .v15_mapping_protocol import checked_request
    from .v15_mapping_provider import paid_record, restore_settled

    output = Path(output).resolve()
    seal = checked(output / "completion_seal/record.json")
    jobs = plan["jobs"]
    require(
        seal["registration_id"] == plan["id"]
        and seal["protocol_id"] == plan["protocol_identity"]
        and seal["all_registered_jobs_have_authentic_terminals"] is True
        and seal["expected_calls"] == len(jobs) == len(seal["terminals"])
        and 0 <= len(jobs) <= 54,
        "entire fixed residual matrix must have actual terminal records",
    )
    if not jobs:
        require(
            seal["actual_returns"] == seal["network_unknowns"] == 0,
            "zero residual matrix cannot contain synthetic responses",
        )
        return seal, {}
    db = sqlite3.connect(Path(plan["budget_database"]).resolve().as_uri() + "?mode=ro", uri=True)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA query_only=ON")
    db.execute("BEGIN")
    results, returned, unknown = {}, 0, 0
    try:
        config = json.loads(
            db.execute("SELECT value FROM metadata WHERE key='config'").fetchone()[0]
        )
        require(digest(config) == plan["budget_config_sha256"], "same shared wallet required")
        acknowledgments = {a["invocation_id"]: a for a in _acknowledged_unknowns(db, config)}
        for job, ref in zip(jobs, seal["terminals"], strict=True):
            terminal = read_ref(ref)
            record = read_ref(terminal["record"])
            request = checked_request(read_ref(job["request"]))
            require(
                job["purpose"] == terminal["purpose"] == request["purpose"] == "mapping"
                and job["task_id"] == terminal["task_id"] == request["task_id"]
                and job["episode_id"] == terminal["episode_id"] == request["episode_id"]
                and terminal["registration_id"] == plan["id"]
                and request["protocol_id"] == plan["protocol_identity"],
                "mapping source, scope or order changed",
            )
            if terminal["terminal_kind"] == "paid_model_return":
                row = db.execute(
                    "SELECT * FROM requests WHERE invocation_id=?",
                    (record["artifact"]["budget_invocation_id"],),
                ).fetchone()
                require(row is not None, "actual new mapping receipt missing")
                row = dict(row)
                require(
                    record == paid_record(request, restore_settled(row, request), row),
                    "new mapping raw response or original inspection changed",
                )
                returned += 1
            else:
                require(
                    terminal["terminal_kind"] == "acknowledged_connection_unknown"
                    and record.get("inspection") is None
                    and record.get("actual_model_call_receipt_verified") is False,
                    "missing response never supplies a judgment",
                )
                row = db.execute(
                    "SELECT * FROM requests WHERE invocation_id=?", (record["invocation_id"],)
                ).fetchone()
                require(row is not None, "UNKNOWN receipt absent")
                row, ack = dict(row), acknowledgments.get(record["invocation_id"])
                require(
                    row["state"] == "UNKNOWN"
                    and ack is not None
                    and record["request_id"] == request["id"]
                    and record["request_sha256"] == row["request_sha256"] == job["request_sha256"]
                    and record["acknowledgment_id"] == ack["id"]
                    and record["original_ledger_record_sha256"] == _request_record_digest(row)
                    and record["permanent_reserved_microcny"] == row["reserved_microcny"],
                    "UNKNOWN original and hold must remain untouched",
                )
                unknown += 1
            require(job["task_id"] not in results, "one new source per residual task")
            results[job["task_id"]] = dict(record=record, reference=terminal["record"])
    finally:
        db.close()
    require(
        (returned, unknown) == (seal["actual_returns"], seal["network_unknowns"]),
        "returns cannot be conflated with attempted UNKNOWN",
    )
    return seal, results


def authority_mapping(value, task_slots):
    record = read_ref(value["record"])
    task = value["task_id"]
    if len(task_slots[task]) == 1:
        require(
            record.get("deterministic_singleton") is True
            and record.get("chi_status") == "not_required_for_weighting",
            "only genuine registered singletons use deterministic chi=None",
        )
        inspected = copy.deepcopy(record)
    else:
        require(
            record.get("schema")
            in {
                "v14_derived_mapping.v1",
                "v15_derived_mapping.v1",
                "v14_paid_material_annotation.v1",
                "v15_paid_material_annotation.v1",
            },
            "explicit existing or derived mapping authority required",
        )
        inspected = copy.deepcopy(record["inspection"])
        require(
            inspected.get("mapping_status") == "complete"
            and inspected.get("mapping_admitted") is True,
            "unresolved original cannot be inherited as complete",
        )
        if record["schema"].startswith(("v14_derived", "v15_derived")):
            require(record["usable"] is True, "derived mapping did not pass its own contract")
        inspected["deterministic_singleton"] = False
    require(
        set(inspected["state_by_slot"]) == set(task_slots[task]),
        "one complete original task partition required",
    )
    return inspected


def collect(output):
    from .v15_mapping_registration import checked_plan

    output = Path(output).resolve()
    plan = checked_plan(output)
    definition = read_ref(plan["definition"])
    review = read_ref(definition["mapping_review"])
    task_slots = definition["fixed_task_slots"]
    prefix_ref = entry(output / "prefix_material/binding/record.json")
    prefix = load_prefix_pool(prefix_ref["path"])
    require(
        len(prefix.task_ids) == 744
        and len(prefix.packages) == 2468
        and list(prefix.task_ids) == list(task_slots),
        "same complete prefix population required",
    )
    seal, new = mapping_results(output, plan)
    mappings, authorities = {}, {}
    for field in ("inherited_mapping_authority_refs", "derived_mapping_authority_refs"):
        for value in review[field]:
            task = value["task_id"]
            require(task not in mappings, "one source for each accepted mapping")
            mappings[task] = authority_mapping(value, task_slots)
            authorities[task] = value["record"]
    for task in review["residual_mapping_task_ids"]:
        require(task not in mappings, "new residual authority cannot replace an inherited decision")
        mappings[task] = new[task]["record"].get("inspection")
        authorities[task] = new[task]["reference"]
    require(set(mappings) == set(task_slots), "all 744 original tasks, never only resolved tasks")
    source_support = read_ref(definition["source_material_support"])
    coverage = source_support["capability_profile"]["package_reason_coverage"]
    encodings = copy.deepcopy(prefix._encodings)
    for sid, encoded in encodings.items():
        encoded["original_public_content_characters"] = coverage[sid]["raw_characters"]
        encoded["positive_public_content_characters"] = coverage[sid]["approved_characters"]
    support = token_independent_profile(task_slots, mappings, encodings, [])
    body = {k: v for k, v in support.items() if k != "id"}
    capability = {k: v for k, v in body["capability_profile"].items() if k != "id"}
    body["schema"] = "v15_complete_support_manifest.v1"
    capability["schema"] = "v15_complete_capability_profile.v1"
    body["capability_profile"] = bound(capability)
    body["prefix_binding"] = prefix_ref
    body["supervision_and_encoding_unchanged"] = True
    support = bound(body)
    return dict(
        plan=plan,
        definition=definition,
        review=review,
        prefix=prefix,
        prefix_ref=prefix_ref,
        seal=seal,
        mappings=mappings,
        mapping_authorities=authorities,
        support=support,
    )


def produce(output):
    output = Path(output).resolve()
    value = collect(output)
    support, prefix, plan = value["support"], value["prefix"], value["plan"]
    persist(output / "material/support", support)
    persist(
        output / "material/conditional_bounds",
        conditional_bounds(value["definition"]["fixed_task_slots"], value["mappings"]),
    )
    ready = support["material_complete"] and support["exploratory_training_admitted"]
    result = dict(
        schema="v15_complete_material_result.v1",
        registration_id=plan["id"],
        protocol_id=plan["protocol_identity"],
        N=744,
        package_count=2468,
        phase="READY_EXPLORATORY"
        if ready
        else "BLOCKED_MAPPING"
        if not support["material_complete"]
        else "DEGENERATE_SUPPORT",
        training_admitted=ready,
        prefix_only_binding_unchanged=True,
        no_subset_training=True,
        support=entry(output / "material/support/record.json"),
        API_calls=0,
        GPU_used=False,
    )
    if ready:
        binding = bound(
            dict(
                schema=BINDING_SCHEMA,
                material_root=str(output),
                registration_id=plan["id"],
                protocol_id=plan["protocol_identity"],
                registration=entry(output / "registration/record.json"),
                definition=plan["definition"],
                mapping_review=value["definition"]["mapping_review"],
                completion_seal=entry(output / "completion_seal/record.json"),
                prefix_material_binding=value["prefix_ref"],
                material_order_id=prefix.material_order_id,
                support_manifest=entry(output / "material/support/record.json"),
                mapping_authorities=value["mapping_authorities"],
                supervision_manifests=prefix.supervision_manifest_refs,
                encodings=prefix.encoding_refs,
                tokenizer_binding=list(prefix.tokenizer_binding),
                original_prefix_not_retrained=True,
                fixed_arms=["Static", "Manual+", "Manual-", "C-only", "Full"],
                fixed_seeds=[11, 29, 47],
                feedback_denominator=700,
            )
        )
        persist(output / "material/binding", binding)
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
        "complete genuine V15 state-aware binding, not a prefix-only binding",
    )
    value = collect(binding["material_root"])
    prefix, support = value["prefix"], value["support"]
    require(
        support["material_complete"]
        and support["exploratory_training_admitted"]
        and read_ref(binding["support_manifest"]) == support
        and binding["mapping_authorities"] == value["mapping_authorities"]
        and binding["prefix_material_binding"] == value["prefix_ref"]
        and binding["encodings"] == prefix.encoding_refs
        and binding["supervision_manifests"] == prefix.supervision_manifest_refs
        and binding["material_order_id"] == prefix.material_order_id
        and binding["registration_id"] == value["plan"]["id"],
        "no changed masks, order, partial mapping or alternative prefix source",
    )
    packages = [
        dict(p, state_id=value["mappings"][p["task_id"]]["state_by_slot"][p["package_id"]])
        for p in prefix.packages
    ]
    rows = {sid: encoded["rows"] for sid, encoded in prefix._encodings.items()}
    pool = VerifiedPool(
        prefix.task_ids,
        packages,
        rows,
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
        "adding genuine state names cannot change prefix execution order",
    )
    pool._manifest.registration.validator_binding_id = (
        "v15_complete_fixed_states_original_supervision.v1"
    )
    pool.material_schema, pool.conditional_scope_verified = BINDING_SCHEMA, True
    pool.registered_singleton_tasks = tuple(support["registered_singleton_tasks"])
    pool.execution_plan, pool.support_manifest = support["execution_plan"], support
    pool.capability_profile, pool.tokenizer_binding = (
        support["capability_profile"],
        prefix.tokenizer_binding,
    )
    pool.source_manifest_sha256 = prefix.source_snapshot_sha256
    pool.public_input_parent_id = prefix.public_input_parent_id
    pool.generation_launch_id = pool.original_material_protocol_id = value["plan"][
        "protocol_identity"
    ]
    pool.material_order_id = prefix.material_order_id
    pool.prefix_binding_ref = value["prefix_ref"]
    pool.supervision_manifest_refs, pool.encoding_refs = (
        prefix.supervision_manifest_refs,
        prefix.encoding_refs,
    )
    pool.verified_file_count = len(prefix.encoding_refs) + len(prefix.supervision_manifest_refs)
    return pool
