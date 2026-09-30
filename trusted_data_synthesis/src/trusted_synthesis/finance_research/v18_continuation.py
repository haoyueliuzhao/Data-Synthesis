"""A new named research source realizes the original intent, never unholds V17."""

from pathlib import Path

from . import v16_continuation as shared
from .v6_collection import require
from .v18_material import BINDING_SCHEMA, held_history, load_historical_prefix, load_training_pool

SCHEMA = "v18_researcher_condition_realization.v1"


def validate_lineage(binding, definition):
    intent = shared.validate_lineage(
        binding,
        definition,
        binding_schema=BINDING_SCHEMA,
        definition_schema="v18_researcher_continuation_definition.v1",
        inherited_count=743,
        successor_count=1,
    )
    _, revoked = held_history(definition)
    require(
        binding["source_v17_admission_hold"] == definition["source_v17_admission_hold"]
        and binding["source_v17_revoked_binding"] == definition["source_v17_revoked_binding"]
        and binding["researcher_authority"] == definition["researcher_authority"]
        and binding["id"] != revoked["id"]
        and Path(binding["material_root"]).resolve() != Path(revoked["material_root"]).resolve()
        and binding["old_V17_binding_remains_not_trainable"] is True,
        "new V18 material cannot reinstate or mutate the held V17 binding",
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
    require(
        not (Path(output) / "admission_hold/record.json").exists(),
        "explicit admission hold blocks this material",
    )
    return shared.register_and_migrate(
        output,
        allowed_gpu_indices=allowed_gpu_indices,
        lineage_validator=validate_lineage,
        prefix_loader=load_historical_prefix,
        pool_loader=load_training_pool,
        schema=SCHEMA,
        receipt_schema="v18_researcher_prefix_migration_receipt.v1",
        handoff_schema="v18_researcher_original_five_arm_handoff.v1",
    )
