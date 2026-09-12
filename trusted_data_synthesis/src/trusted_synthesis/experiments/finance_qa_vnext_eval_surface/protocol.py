"""User-authorized wording overlays under the original three-purpose allowance."""

from ..finance_qa_vnext_task_build.archive import record

BASE = "trusted_data_synthesis/artifacts/qa_vnext_eval_surface"
OUTPUT = BASE + "/surface_20260912"
AUDITS = OUTPUT + "_audits"
PARENT_PANEL = "trusted_data_synthesis/artifacts/qa_vnext_eval_readiness/eval_readiness_20260912"
PARENT_PANEL_MANIFEST = "manifest:90ebc575be3e1c825edb598a937677e0bd83c49cd43c29f35cfe67f543055407"
PARENT_REVISION = "trusted_data_synthesis/artifacts/qa_vnext_readiness_revision/revision_20260912"
PARENT_REVISION_MANIFEST = (
    "manifest:6f646a8e45e4e65bec53fe9b75e5bf04047baae0f4b92cfa307bae90b731b4ec"
)
PARENT_REVISION_AUDIT_MANIFEST = (
    "manifest:52b0ca6b08d4e72b7baac91eda145ac35568f0f57f2aa0c1f8ff1381aa11ae20"
)
OWNER_FREEZE = (
    "readiness_revision_freeze:c2bf02ab9d7c70632073db2eeecf30bac9f3f97bf6c8927b045c7b68fa226af9"
)
LEDGER = (
    "trusted_data_synthesis/artifacts/qa_vnext_readiness_revision/runtime_20260912/"
    "rewrite_and_Teacher_budget.sqlite3"
)
TASK_CAP = 900
REQUEST_CAP = 1800
INPUT_RESERVATION = 8192
OUTPUT_CAP = 1536
REQUEST_RESERVATION = INPUT_RESERVATION + OUTPUT_CAP
TOKEN_CAP = REQUEST_CAP * REQUEST_RESERVATION
GLOBAL_CAP = 1_000_000_000


def policy():
    return record(
        "evaluation_surface_policy",
        purpose="evaluation_question_rewrite",
        explicit_user_authorization="900 tasks, two requests each, shared purpose cap accepted",
        parent_panel_manifest_id=PARENT_PANEL_MANIFEST,
        parent_revision_manifest_id=PARENT_REVISION_MANIFEST,
        selected_tasks=TASK_CAP,
        split_counts={"dev": 180, "confirm": 720},
        new_scientific_tasks=0,
        source_acquisition_or_QA_builds=0,
        source_order="original selected panel catalog order, dev then confirm",
        task_request_cap=2,
        request_cap=REQUEST_CAP,
        input_reservation=INPUT_RESERVATION,
        output_cap=OUTPUT_CAP,
        token_cap=TOKEN_CAP,
        common_token_cap=GLOBAL_CAP,
        ledger_owner_freeze=OWNER_FREEZE,
        inherited_known_common_debit=232357,
        old_UNP_17_task_34_request_policy_unchanged=True,
        consumer="separate evaluation purpose, three-purpose atomic common budget",
        workers=8,
        model_input="public model_contract only; no private bundle or method labels",
        validation="saved rewritten base itself, then exact restored public contract",
        registered_semantic_domains=[
            "difference with exact current-minus-previous direction",
            "growth with positive previous denominator and percent units",
            "arithmetic mean of exactly three specified actual periods",
            "primary maximum across full window then same-period secondary metric",
        ],
        unchanged_fields=(
            "TaskID, sources, private reference, periods, units and operation contract"
        ),
        selection="first semantic-valid candidate ends selection; then classify wording change",
        unchanged_rule=(
            "keep exact original public bytes; no second candidate or repair to boost rate"
        ),
        canonical_preparation_is_not_LLM_rewrite=True,
        semantic_repair_cap=1,
        transport_retries=0,
        task_drop_or_success_rate_selection=False,
        fallback="retain exact original template bytes and rejected response history",
        unrequested_after_fatal="template retained, explicitly not requested; no completion claim",
        one_final_surface_per_task=True,
        template_Student_evaluation_automatically_added=False,
        all_Student_arms_seeds_pools_share_final_version=True,
        freeze_final_before_Student_outputs=True,
        score_based_surface_selection=False,
        explicit_operation_contract_removed=False,
        natural_language_understanding_generalization_established=False,
        independent_saved_surface_audit_required=True,
        original_source_audit="inherit exact passed parent; no 900-source reaudit",
        script_or_reference_training_material=False,
    )
