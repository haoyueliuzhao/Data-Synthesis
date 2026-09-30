"""New researcher authority for ABMD; the held V17 binding stays permanently held."""

from __future__ import annotations

import copy
from datetime import datetime
from pathlib import Path

from . import v16_material as shared
from . import v17_material as predecessor
from .v6_collection import bound, require, sha
from .v13_material_registration import checked, entry, read_ref

BINDING_SCHEMA = "v18_researcher_complete_material_binding.v1"
ABMD = "ABMD/2008/page_87.pdf-1"
RETAINED_V17_TASKS = {"KHC/2018/page_27.pdf-1", "PNC/2016/page_73.pdf-1"}


def held_history(definition):
    """Reading revoked history never clears it or makes its ABMD judgment valid."""
    hold = read_ref(definition["source_v17_admission_hold"])
    revoked = read_ref(definition["source_v17_revoked_binding"])
    require(
        hold["schema"] == "v17_explicit_semantic_admission_hold.v1"
        and hold["revoked_binding"] == definition["source_v17_revoked_binding"]
        and hold["registration"] == definition["source_v17_registration"]
        and hold["task_id"] == ABMD
        and hold["original_prefix_must_continue"] is True
        and hold["no_replacement_partition_or_chi_supplied"] is True
        and revoked["schema"] == predecessor.BINDING_SCHEMA
        and revoked["definition"] == definition["source_v17_definition"]
        and revoked["registration"] == definition["source_v17_registration"]
        and revoked["completion_seal"] == definition["source_v17_completion_seal"]
        and revoked["prefix_material_binding"] == definition["prefix_material_binding"]
        and revoked["mapping_authorities"][ABMD] == hold["paid_source"]
        and definition["previous_failed_authorities"] == {ABMD: hold["paid_source"]},
        "original V17 binding and its exact semantic hold must remain immutable history",
    )
    old_root = Path(revoked["material_root"])
    require(
        definition["source_v17_admission_hold"] == entry(old_root / "admission_hold/record.json")
        and definition["source_v17_revoked_binding"]
        == entry(old_root / "material/binding/record.json")
        and datetime.fromisoformat(hold["at"]) < datetime.fromisoformat(definition["at"]),
        "new authority must follow the original hold; old hold cannot be deleted or replaced",
    )
    return hold, revoked


def historical_context(definition):
    hold, revoked = held_history(definition)
    plan = read_ref(definition["source_v17_registration"])
    parent = read_ref(definition["source_v17_definition"])
    seal = read_ref(definition["source_v17_completion_seal"])
    frozen = (
        Path(definition["source_v17_frozen_root"])
        / "trusted_data_synthesis/src/trusted_synthesis/finance_research"
    )
    require(
        plan["schema"] == "v17_three_task_adjudication_plan.v1"
        and plan["definition"] == definition["source_v17_definition"]
        and all(sha(frozen / name) == value for name, value in plan["source_bindings"].items())
        and seal["registration_id"] == plan["id"]
        and seal["protocol_id"] == plan["protocol_identity"] == parent["id"]
        and seal["all_registered_jobs_have_authentic_terminals"] is True
        and seal["actual_returns"] == seal["expected_calls"] == len(plan["jobs"]) == 3
        and seal["network_unknowns"] == 0,
        "all three actual V17 returns and their frozen implementation must remain recorded",
    )
    for field in (
        "source_root",
        "source_registration",
        "source_frozen_root",
        "source_completion_seal",
        "source_support",
        "prospective_intent",
        "prefix_material_binding",
        "fixed_task_slots",
    ):
        require(
            definition[field] == parent[field],
            "original prefix material and pre-prefix intent cannot change",
        )
    history = predecessor.historical_context(parent)
    mappings, authorities = history["mappings"], history["authorities"]
    seen = set()
    for job, ref in zip(plan["jobs"], seal["terminals"], strict=True):
        terminal = read_ref(ref)
        record = read_ref(terminal["record"])
        task = job["task_id"]
        require(
            task not in seen
            and task == terminal["task_id"]
            and terminal["registration_id"] == plan["id"]
            and terminal["terminal_kind"] == "paid_model_return"
            and record["schema"] == "v17_paid_material_annotation.v1"
            and record["actual_model_call_receipt_verified"] is True
            and record["request"] == read_ref(job["request"]),
            "original paid source and all three historical returns must remain unchanged",
        )
        seen.add(task)
        if task == ABMD:
            require(
                terminal["record"] == hold["paid_source"],
                "exclude precisely the semantically held ABMD source",
            )
            mappings[task] = None
        else:
            require(
                task in RETAINED_V17_TASKS
                and record["inspection"]["mapping_admitted"] is True
                and record["inspection"]["mapping_status"] == "complete",
                "only the unchanged admitted KHC and PNC decisions may be inherited",
            )
            mappings[task] = copy.deepcopy(record["inspection"])
        authorities[task] = terminal["record"]
    good = set(definition["fixed_task_slots"]) - {ABMD}
    require(
        seen == RETAINED_V17_TASKS | {ABMD}
        and len(good) == 743
        and len(definition["fixed_task_slots"][ABMD]) == 4
        and definition["fixed_unresolved_task_ids"] == [ABMD]
        and {t: authorities[t] for t in good} == definition["inherited_mapping_authorities"]
        and authorities == revoked["mapping_authorities"],
        "inherit exactly 743 authorities; the fourth ABMD source must be named researcher judgment",
    )
    history["failed"] = {ABMD}
    return history


def researcher_results(output, plan, definition):
    from .v18_researcher_authority import load_authority

    seal = checked(Path(output) / "completion_seal/record.json")
    inspection = load_authority(definition["researcher_authority"], definition["fixed_task_slots"])
    require(
        seal["schema"] == "v18_researcher_adjudication_seal.v1"
        and seal["registration_id"] == plan["id"]
        and seal["protocol_id"] == plan["protocol_identity"]
        and seal["authority"] == definition["researcher_authority"]
        and seal["expected_model_calls"] == seal["actual_model_calls"] == 0,
        "a named no-API researcher source cannot be relabeled as another paid return",
    )
    return seal, {
        ABMD: dict(
            inspection=copy.deepcopy(inspection), reference=definition["researcher_authority"]
        )
    }


def collect(output):
    from .v18_registration import checked_plan

    result = shared.collect(
        output,
        plan_loader=checked_plan,
        history_loader=historical_context,
        results_loader=researcher_results,
        support_schema="v18_researcher_complete_support_manifest.v1",
    )
    body = {k: v for k, v in result["support"].items() if k != "id"}
    result["support"] = bound(
        dict(
            body,
            inherited_743_authorities_unchanged=True,
            old_V17_semantic_hold_preserved=True,
            ABMD_source_kind="codex_source_grounded_research_adjudication",
        )
    )
    return result


def binding_body(output, value):
    definition = value["definition"]
    _, old = held_history(definition)
    require(
        Path(output).resolve() != Path(old["material_root"]).resolve(),
        "never republish into the held V17 material root",
    )
    return shared.binding_body(output, value, schema=BINDING_SCHEMA) | {
        "source_v17_revoked_binding": definition["source_v17_revoked_binding"],
        "source_v17_admission_hold": definition["source_v17_admission_hold"],
        "researcher_authority": definition["researcher_authority"],
        "inherited_743_authorities_unchanged": True,
        "old_V17_binding_remains_not_trainable": True,
    }


def produce(output):
    return shared.produce(
        output,
        collector=collect,
        body_builder=binding_body,
        result_schema="v18_researcher_complete_material_result.v1",
    )


def load_historical_prefix(definition):
    return shared.load_historical_prefix(definition, history=historical_context(definition))


def load_training_pool(binding_path):
    path = Path(binding_path).resolve()
    require(
        not (path.parents[2] / "admission_hold/record.json").exists(),
        "explicit admission hold blocks this material",
    )
    binding = checked(path)
    _, revoked = held_history(read_ref(binding["definition"]))
    require(binding["id"] != revoked["id"], "the revoked V17 binding is never reinstated")
    return shared.load_training_pool(
        path,
        schema=BINDING_SCHEMA,
        collector=collect,
        body_builder=binding_body,
        validator_id="v18_researcher_states_original_supervision.v1",
    )
