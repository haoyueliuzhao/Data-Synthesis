"""Finite successor: no panel rebuild, source refill, or old-array re-encoding."""

from ..finance_qa_vnext_eval_readiness import collection, materials, source_policy, transport
from ..finance_qa_vnext_task_build.archive import record

BASE = "trusted_data_synthesis/artifacts/qa_vnext_readiness_revision"
OUTPUT = BASE + "/revision_20260912"
WORK = BASE + "/runtime_20260912"
AUDITS = OUTPUT + "_audits"
COLLECTION = BASE + "/fixed_AB_20260912"
PARENT = "trusted_data_synthesis/artifacts/qa_vnext_eval_readiness/eval_readiness_20260912"
PARENT_MANIFEST = "manifest:90ebc575be3e1c825edb598a937677e0bd83c49cd43c29f35cfe67f543055407"
PARENT_AUDITS = PARENT + "_audits"
PARENT_AUDIT_MANIFEST = "manifest:72c5120253e04a0d6c5c6e806b2b5b59a223f99b4789e70acc5c60eb676639af"
PARENT_CODE = "f138191c0f2840d39b18266117434838f7f173bc"
PARENT_PUBLICATION = "20719627547867426aa291e8160592f076282d91"
PARENT_WORK = "trusted_data_synthesis/artifacts/qa_vnext_eval_readiness/runtime_20260912"
AUDIT_ATTACHMENT = (
    "/home/zhuxinrui/.codex/attachments/aa6177d9-d7ac-495c-93e7-3e74146e4d8b/pasted-text.txt"
)
CHANGED_PARENT_CODE = (
    "trusted_data_synthesis/src/trusted_synthesis/experiments/finance_qa_vnext_eval_readiness/assessment.py",
    "trusted_data_synthesis/src/trusted_synthesis/experiments/finance_qa_vnext_task_build/issuer_tables.py",
    "trusted_data_synthesis/scripts/audit_qa_vnext_eval_readiness_increment.py",
)


def policy():
    return record(
        "readiness_revision_policy",
        purpose="growth certificate consumer and same-six-source UNP cover correction",
        revision_count=1,
        parent_manifest_id=PARENT_MANIFEST,
        parent_audit_manifest_id=PARENT_AUDIT_MANIFEST,
        allowed_changed_parent_code=list(CHANGED_PARENT_CODE),
        parent_code_verification=(
            "unchanged working bytes or original committed Git blob; no disabled hashes"
        ),
        panel_rebuilds=0,
        reused_selected_evaluation_tasks=900,
        reused_compiled_overflow=48,
        preserved_old_training_public_tasks=243,
        fixed_prior_source_controls=70,
        unchanged_expected_positive_controls=54,
        unchanged_expected_negative_controls=16,
        inherited_financial_valid_packages=39,
        inherited_encoded_rows=253,
        original_control_sessions_rewritten=False,
        qualification="one consistent replay against original bundles and unchanged expectations",
        relative_certificate=(
            "only registered relative wrapper; base completeness plus outer growth witnesses, "
            "target, original source bindings, positive previous denominator and percent units"
        ),
        UNP_cover=(
            "actual SEC annual-report cover semantic region; legal DOM whitespace; "
            "reconstructible original DOM evidence; no known offsets or archive-year substitution"
        ),
        independent_UNP_cover="independent original-DOM verification of the same semantic cover",
        source_increment=source_policy.policy(),
        no_definition_or_amount_rule_expansion=True,
        no_new_HTTP_source_acquisition=True,
        no_403_retries=True,
        original_rows_reencoded=0,
        incremental_CPU=(
            "only newly financial-complete original scripts; zero or one tokenizer construction"
        ),
        maximum_sequence_length=24576,
        truncation=False,
        script_training_samples=0,
        primary_requires_fine_mapping=False,
        fine_mapping_required_for_training=True,
        prior_known_common_debit=221538,
        shared_new_rewrite_requests=34,
        shared_new_rewrite_token_cap=330752,
        global_token_cap=1_000_000_000,
        ledger_handoff=(
            "zero-attempt predecessor retired durably before exclusive successor creation"
        ),
        model=transport.policy(),
        registered_collection_policy=collection.policy(),
        registered_original_package_consumer=materials.policy(),
        no_UNP_positive_yield_hard_gate=True,
        no_live_pilot=True,
        complete_gate_then_direct_fixed_AB=True,
        no_population_from_incomplete_collection=True,
        no_post_output_source_prompt_or_qualification_changes=True,
        Student_design=(
            "inherit original frozen three-arm/three-seed A development and B confirmation"
        ),
        further_failure=(
            "preserve concrete failures; no automatic reopening, source refill, or PASS edit"
        ),
    )
