"""The V17 source realizes the same pre-prefix intent and zero-update migration."""

from datetime import datetime

from . import v16_continuation as shared
from .v6_collection import require
from .v13_material_registration import read_ref
from .v17_material import BINDING_SCHEMA, load_historical_prefix, load_training_pool

SCHEMA = "v17_three_task_condition_realization.v1"


def validate_lineage(binding, definition):
    intent = shared.validate_lineage(
        binding,
        definition,
        binding_schema=BINDING_SCHEMA,
        definition_schema="v17_three_task_definition.v1",
        inherited_count=741,
        successor_count=3,
    )
    parent = read_ref(definition["predecessor_definition"])
    require(
        binding["predecessor_registration"] == definition["predecessor_registration"]
        and binding["predecessor_completion_seal"] == definition["predecessor_completion_seal"]
        and parent["prospective_intent"] == definition["prospective_intent"]
        and parent["prefix_material_binding"] == definition["prefix_material_binding"]
        and parent["source_registration"] == definition["source_registration"]
        and datetime.fromisoformat(parent["at"]) < datetime.fromisoformat(definition["at"]),
        "V17 must preserve its actual V16 predecessor and original prospective intent",
    )
    return intent


def validate_condition_realization(record, material_binding, material_identity):
    return shared.validate_condition_realization(
        record,
        material_binding,
        material_identity,
        schema=SCHEMA,
        lineage_validator=validate_lineage,
    )


def register_and_migrate(output, *, allowed_gpu_indices):
    return shared.register_and_migrate(
        output,
        allowed_gpu_indices=allowed_gpu_indices,
        lineage_validator=validate_lineage,
        prefix_loader=load_historical_prefix,
        pool_loader=load_training_pool,
        schema=SCHEMA,
        receipt_schema="v17_three_task_prefix_migration_receipt.v1",
        handoff_schema="v17_three_task_original_five_arm_handoff.v1",
    )
