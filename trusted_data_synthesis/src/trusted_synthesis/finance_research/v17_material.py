"""Three newly authorized sources appended to the unchanged 741-task authority."""

from __future__ import annotations

import copy
from datetime import datetime
from pathlib import Path

from . import v16_material as shared
from .v6_collection import bound, require, sha
from .v13_material_registration import entry, read_ref

BINDING_SCHEMA = "v17_three_task_complete_material_binding.v1"


def historical_context(definition):
    previous = Path(definition["predecessor_root"]).resolve()
    plan = read_ref(definition["predecessor_registration"])
    parent = read_ref(definition["predecessor_definition"])
    seal = read_ref(definition["predecessor_completion_seal"])
    support = read_ref(definition["predecessor_support"])
    frozen = (
        Path(definition["predecessor_frozen_root"])
        / "trusted_data_synthesis/src/trusted_synthesis/finance_research"
    )
    require(
        definition["predecessor_registration"] == entry(previous / "registration/record.json")
        and definition["predecessor_definition"] == plan["definition"]
        and definition["predecessor_completion_seal"]
        == entry(previous / "completion_seal/record.json")
        and definition["predecessor_support"] == entry(previous / "material/support/record.json")
        and plan["schema"] == "v16_six_task_adjudication_plan.v1"
        and plan["model"] == "deepseek-flash"
        and all(sha(frozen / name) == value for name, value in plan["source_bindings"].items())
        and seal["registration_id"] == plan["id"]
        and seal["protocol_id"] == plan["protocol_identity"] == parent["id"]
        and seal["all_registered_jobs_have_authentic_terminals"] is True
        and seal["actual_returns"] == seal["expected_calls"] == len(plan["jobs"]) == 6
        and seal["network_unknowns"] == 0
        and datetime.fromisoformat(parent["at"]) < datetime.fromisoformat(definition["at"]),
        "actual frozen V16 six-call source and explicitly later three-task successor required",
    )
    for field in (
        "source_root",
        "source_registration",
        "source_completion_seal",
        "source_support",
        "source_frozen_root",
        "prospective_intent",
        "prefix_material_binding",
        "fixed_task_slots",
    ):
        require(
            definition[field] == parent[field],
            "original V15 population, source and intent cannot change",
        )
    history = shared.historical_context(parent)
    mappings, authorities = history["mappings"], history["authorities"]
    tasks = set()
    for job, ref in zip(plan["jobs"], seal["terminals"], strict=True):
        terminal = read_ref(ref)
        record = read_ref(terminal["record"])
        task = job["task_id"]
        require(
            task not in tasks
            and task == terminal["task_id"]
            and task in history["failed"]
            and terminal["registration_id"] == plan["id"]
            and terminal["terminal_kind"] == "paid_model_return"
            and record["schema"] == "v16_paid_material_annotation.v1"
            and record["actual_model_call_receipt_verified"] is True
            and record["request"] == read_ref(job["request"]),
            "all six actual old returns, including three failures, must remain original",
        )
        tasks.add(task)
        mappings[task], authorities[task] = copy.deepcopy(record["inspection"]), terminal["record"]
    good = {
        t
        for t, value in mappings.items()
        if value
        and (
            value.get("deterministic_singleton") is True
            or (value.get("mapping_status") == "complete" and value.get("mapping_admitted") is True)
        )
    }
    failed = set(definition["fixed_task_slots"]) - good
    require(
        tasks == history["failed"]
        and len(good) == 741
        and len(failed) == 3
        and sum(len(definition["fixed_task_slots"][t]) for t in failed) == 13
        and failed == set(definition["fixed_unresolved_task_ids"])
        and good == set(support["task_support"])
        and {t: authorities[t] for t in good} == definition["inherited_mapping_authorities"]
        and {t: authorities[t] for t in failed} == definition["previous_failed_authorities"],
        "only the fixed three/13 originals may change source; all 741 authorities remain exact",
    )
    history.update(support=support, failed=failed)
    return history


def verify_successor_receipt(plan, job, terminal, record):
    from . import v17_provider

    return shared.verify_successor_receipt(plan, job, terminal, record, provider=v17_provider)


def successor_results(output, plan, definition):
    return shared.successor_results(
        output,
        plan,
        definition,
        expected_calls=3,
        paid_schema="v17_paid_material_annotation.v1",
        receipt_verifier=verify_successor_receipt,
    )


def collect(output):
    from .v17_registration import checked_plan

    result = shared.collect(
        output,
        plan_loader=checked_plan,
        history_loader=historical_context,
        results_loader=successor_results,
        support_schema="v17_three_task_complete_support_manifest.v1",
    )
    body = {k: v for k, v in result["support"].items() if k != "id"}
    result["support"] = bound(dict(body, inherited_741_authorities_unchanged=True))
    return result


def binding_body(output, value):
    return shared.binding_body(output, value, schema=BINDING_SCHEMA) | {
        "predecessor_registration": value["definition"]["predecessor_registration"],
        "predecessor_completion_seal": value["definition"]["predecessor_completion_seal"],
        "inherited_741_authorities_unchanged": True,
    }


def produce(output):
    return shared.produce(
        output,
        collector=collect,
        body_builder=binding_body,
        result_schema="v17_three_task_complete_material_result.v1",
    )


def load_historical_prefix(definition):
    return shared.load_historical_prefix(definition, history=historical_context(definition))


def load_training_pool(binding_path):
    return shared.load_training_pool(
        binding_path,
        schema=BINDING_SCHEMA,
        collector=collect,
        body_builder=binding_body,
        validator_id="v17_three_successor_states_original_supervision.v1",
    )
