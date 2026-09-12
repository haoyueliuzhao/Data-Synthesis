"""One bounded source increment, generic interface controls, and isolated panels."""

from ..finance_qa_vnext_surface_build.protocol import qa_config
from ..finance_qa_vnext_task_build.archive import record
from ..finance_qa_vnext_task_build.protocol import CAPS, SPLIT_SALT
from .budget import GLOBAL_CAP, REQUEST_CAP, TOKEN_CAP
from .catalog import FAMILY_TO_SCALE

OUTPUT = "trusted_data_synthesis/artifacts/qa_vnext_catalog_bridge/catalog_bridge_20260912"
WORK = "trusted_data_synthesis/artifacts/qa_vnext_catalog_bridge/runtime_20260912"
PARENT = "trusted_data_synthesis/artifacts/qa_vnext_surface_build/task_surface_20260912"
PARENT_MANIFEST = "manifest:0ce0233feff6c6d1069034dc6df7f164c30f161663a60237c777ea340d9578a1"
EXTRA_REPORTS = [
    {
        "period_end": "2020-05-31",
        "accession": "0001564590-20-030125",
        "filed": "2020-06-22",
        "url": "https://www.sec.gov/Archives/edgar/data/1341439/000156459020030125/orcl-10k_20200531.htm",
    },
    {
        "period_end": "2019-05-31",
        "accession": "0001564590-19-023119",
        "filed": "2019-06-21",
        "url": "https://www.sec.gov/Archives/edgar/data/1341439/000156459019023119/orcl-10k_20190531.htm",
    },
]


def policy(panel_policy):
    return record(
        "catalog_bridge_protocol",
        parent_manifest_id=PARENT_MANIFEST,
        prior_stage="PASS_AS_SCOPED; 233 tasks; protected rewrite branch closed",
        same_source_split_salt=SPLIT_SALT,
        source_scope=(
            "same training CIKs, same indexed reports, plus only two prelisted SEC reports"
        ),
        source_layout="unique geometric numeric core and directional adjacent sign ownership",
        source_layout_not_selected_by="financial closure, quota or model performance",
        known_six_Oracle_tables_are_development_inputs=True,
        bounded_source_acquisition=EXTRA_REPORTS,
        source_HTTP_attempt_cap=2,
        source_acquisition_trigger=(
            "known primary six-table upper bound is 26+10=36<40; try each prelisted source once "
            "before any new TaskBundle; no alternate host, retry or further source search"
        ),
        previously_rejected_Oracle_2020_publisher_file_readmitted=False,
        total_candidate_cap=260,
        inherited_tasks=233,
        maximum_new_tasks=27,
        family_caps=CAPS,
        family_to_scale=FAMILY_TO_SCALE,
        incremental_enumeration=(
            "inherited source-cluster round robin; subtract old canonical IDs; fixed group order"
        ),
        old_public_bytes_and_fallbacks_unchanged=True,
        old_tasks_rewritten=False,
        qa_config=qa_config(),
        new_rewrite_request_cap=REQUEST_CAP,
        new_rewrite_token_allocation=TOKEN_CAP,
        old_unused_209_requests_transferred=False,
        global_token_cap_unchanged=GLOBAL_CAP,
        known_prior_rewrite_debit=211338,
        other_prior_scope=(
            "same new scale-study registry: scale preparation "
            "and initial task factory were zero-model; "
            "older independent experiments are not reclassified as this new budget"
        ),
        mechanism=(
            "existing persistent rewrite Ledger plus "
            "same-transaction registered-task/global-debit triggers"
        ),
        TaskCatalog=(
            "explicit parent manifests; isolated public reader; separate offline oracle reader"
        ),
        worker_controls={
            "selection": (
                "first canonical task ID for each available family/quantity/surface-category cell"
            ),
            "required_axes": [
                "four training families",
                "difference/relative_change",
                "rewritten/canonical",
            ],
            "live_Teacher_sessions": 0,
            "scripted_sessions_are_training_examples": False,
            "tools": (
                "real bounded public-source reads and exact arithmetic, "
                "with first-Final dependency chain"
            ),
            "method": (
                "actual source-supported computation, not requested guidance or answer equality"
            ),
            "complete_classes": "separate finite signature; unresolved records retained",
            "tokenizer": (
                "existing frozen local Qwen tokenizer on CPU; original response rows, no weights"
            ),
        },
        evaluation_panel=panel_policy,
        evaluation_rewrite_requests=0,
        formal_Teacher_collection_sessions=0,
        Student_runs=0,
        GPU_runs=0,
        future_design={
            "N": [180, 185, 190, 195, 200],
            "dual_groups_each": 40,
            "control_target": 80,
            "pools": ["A", "B"],
            "same_task_public_bytes_in_all_arms": True,
            "alpha": ["1/2,1/2", "1/3,2/3", "2/3,1/3"],
            "global_mass_shift": "1/10",
            "packages_at_200_per_pool": {"train": 2560, "heldout": 640},
            "five_task_updates": "alpha/(40*L), no extra global N or microbatch normalization",
            "updates_at_200": 400,
            "maximum_training_runs_A": 9,
            "maximum_training_runs_B": 6,
            "dev_sessions": 1620,
            "confirm_sessions": 8640,
            "direction_rule": "move only if mean paired primary utility is strictly positive",
            "main_confirmation_pool": "B",
        },
        stop_rule=(
            "after this one bounded source increment, "
            "if balanced supply<180 no formal pool collection; "
            "no quota relaxation or automatic new search. Even sufficient reference supply is not "
            "common A/B trajectory readiness; no live Teacher pilot in this stage"
        ),
    )
