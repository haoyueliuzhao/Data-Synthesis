"""Explicit new-process Parent aliases and a metadata-only training-freeze hook."""

import copy
import importlib
import weakref
from contextlib import contextmanager

from .manifest import LinearParent, MutationMonitor, OriginalParent
from .protocol import policy, record, require

PREFIX = "trusted_synthesis.experiments."
READER_MODULES = (
    "finance_qa_vnext_catalog_bridge.catalog",
    "finance_qa_vnext_catalog_bridge.stage",
    "finance_qa_vnext_eval_readiness.stage",
    "finance_qa_vnext_readiness_revision.stage",
    "finance_qa_vnext_readiness_revision.provenance",
    "finance_qa_vnext_eval_surface.stage",
    "finance_qa_vnext_eval_surface.overlay",
    "finance_qa_vnext_basis_student.stage",
    "finance_qa_vnext_basis_student.publication",
)


def binding(source_registration, reviewed_plan, authorization):
    return record(
        "postprocessing_reader_binding",
        adapter_policy_id=policy()["id"],
        source_registration_id=source_registration["id"],
        adapter_code=source_registration["adapter_code"],
        historical_source_snapshot_sha256=source_registration["historical_source_snapshot_sha256"],
        historical_source_file_count=source_registration["historical_source_file_count"],
        original_follow_started_id=reviewed_plan["original_follow_started_id"],
        original_collection_parent=reviewed_plan["collection_parent"],
        reviewed_handoff_plan_id=reviewed_plan["id"],
        authorization_id=authorization["id"],
        reader_alias_modules=list(READER_MODULES),
        scope=(
            "new postprocessing supervisor reader aliases only; "
            "original model worker reader remains unchanged"
        ),
        training_freeze_metadata_field="postprocessing_verification_adapter",
        scientific_record_values_rewritten=False,
    )


@contextmanager
def installed(adapter_binding):
    """Never attach to another process; restore every alias on normal/error exit."""
    require(
        adapter_binding["adapter_policy_id"] == policy()["id"]
        and adapter_binding["reader_alias_modules"] == list(READER_MODULES),
        "linear.explicit_reader_adapter_binding",
    )
    # Import every declared module before substituting any alias. No function
    # implementing qualification, budget, package choice, training or scoring is replaced.
    modules = [importlib.import_module(PREFIX + name) for name in READER_MODULES]
    require(
        all(getattr(module, "Parent", None) is OriginalParent for module in modules),
        "linear.original_reader_aliases_required_no_nested_adapters",
    )
    student_protocol = importlib.import_module(PREFIX + "finance_qa_vnext_basis_student.protocol")
    original_record = student_protocol.record
    monitor, parents, verifications = MutationMonitor(), weakref.WeakSet(), []

    class BoundLinearParent(LinearParent):
        shared_monitor = monitor
        audit_sink = staticmethod(verifications.append)

        def __init__(self, root, relative, expected_manifest_id=None):
            super().__init__(root, relative, expected_manifest_id)
            parents.add(self)

    def bound_record(kind, **fields):
        if kind == "study_freeze":
            expected = copy.deepcopy(adapter_binding)
            require(
                "postprocessing_verification_adapter" not in fields
                or fields["postprocessing_verification_adapter"] == expected,
                "linear.training_freeze_adapter_identity",
            )
            if "code" in fields:
                code = {row["path"]: row["sha256"] for row in fields["code"]}
                require(
                    all(
                        code.get(row["path"]) == row["sha256"]
                        for row in expected["adapter_code"]
                        if row["role"] == "adapter_source"
                    ),
                    "linear.adapter_sources_in_actual_training_freeze",
                )
            fields = {**fields, "postprocessing_verification_adapter": expected}
        return original_record(kind, **fields)

    body_completed = False
    try:
        for module in modules:
            module.Parent = BoundLinearParent
        student_protocol.record = bound_record
        yield {
            "binding": adapter_binding,
            "verifications": verifications,
            "shared_notification_monitor": monitor,
            "reader_class": BoundLinearParent,
        }
        body_completed = True
    finally:
        student_protocol.record = original_record
        for module in modules:
            module.Parent = OriginalParent
        try:
            for parent in list(parents):
                parent.close()
            if body_completed:
                # Best-effort close preserves a sticky late mutation; do not
                # turn a successful body into success after cleanup detected it.
                monitor.check()
        finally:
            monitor.close()
