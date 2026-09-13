"""Prospective generation-protocol comparison on unchanged certified tasks."""

import copy
import hashlib
import json
import os
import random
from datetime import datetime, timezone
from pathlib import Path

from ..finance_qa_vnext_eval_readiness import training_runtime as original

BRANCH = "codex/probe-coverage-20260913"
BASE_COMMIT = "5f7e102c955ecb4a2fa2f63fc8e16238f004a4d3"
MAIN_COMMIT = "30284a2f139b7981bc96413646459c51b76e57d5"
PACKAGE = "trusted_data_synthesis/src/trusted_synthesis/experiments/finance_qa_vnext_probe_coverage"
OUTPUT = "trusted_data_synthesis/artifacts/qa_vnext_probe_coverage/probe_20260913"
RUNTIME = "trusted_data_synthesis/runtime/probe_coverage_20260913"
WALLET = (
    "trusted_data_synthesis/artifacts/qa_vnext_readiness_revision/runtime_20260912/"
    "rewrite_and_Teacher_budget.sqlite3"
)
OWNER = "readiness_revision_freeze:c2bf02ab9d7c70632073db2eeecf30bac9f3f97bf6c8927b045c7b68fa226af9"
REVISION = "trusted_data_synthesis/artifacts/qa_vnext_readiness_revision/revision_20260912"
REVISION_MANIFEST = "manifest:6f646a8e45e4e65bec53fe9b75e5bf04047baae0f4b92cfa307bae90b731b4ec"
PHASE_ZERO = "trusted_data_synthesis/artifacts/qa_vnext_movement_support/diagnosis_20260913_final"
PHASE_ZERO_REPORT = "cohort_report:61a8e70251ff2f53e2ed47d027620ef74837b12cbe46209e6c4dcec8581a9a6a"
MODEL = "deepseek-flash"
ENDPOINT = "https://api.deepseek.com/chat/completions"
PROFILES = ("P0_original", "P1_delivery", "P2_method_delivery")
BASES = ("endpoint", "movement")
FAMILIES = ("annual_flow", "stock_rollforward", "company_defined_metric")
QUANTITIES = ("difference", "relative_change")
TASKS_PER_STRATUM, TASK_CAP, REPLICATES, SESSION_CAP = 2, 12, 2, 144
MAX_RESPONSES, MAX_TOOLS, WORKERS, ORDER_SEED = 32, 32, 12, 20260913
INPUT_ALLOWANCE, OUTPUT_ALLOWANCE = 99328, 16384
REQUEST_RESERVATION = INPUT_ALLOWANCE + OUTPUT_ALLOWANCE
REQUEST_CAP, TOKEN_CAP, COMMON_CAP = SESSION_CAP * MAX_RESPONSES, 40000000, 1000000000
MAX_BODY_BYTES, PUBLIC_RESPONSE_BYTES, SEQUENCE_CAP = 98304, 65536, 24576
PROTOCOL = "probe_coverage_runtime.v1"

DELIVERY = """
Public evidence-delivery requirement for this run:
Return exactly one JSON tool object or one JSON final object per response. Never
return a list of actions, markdown, explanatory prose, or an unexecuted program.
An amount appearing in a source is not an executed tool result. Read the source
first; for each subsequent calculation use variables referring to its actual
result_id. Do not replace a source value or an intermediate result by a copied
numeric literal, even if the resulting numeric answer would be identical.
Dimensionless coefficients such as signs or multipliers are permitted. Keep
all requested actual periods and financial definitions; do not substitute a
different report/period merely because numbers look similar. For a table, use
the financial row and actual date column, preserving the complete numeric cell
fragment and any sign characters. The public table coordinates are zero-based.
For example, a calculation using two already executed results is JSON of the
form {"tool":"calculate","arguments":{"expression":"a-b","variables":{
"a":{"result_id":"tool:2"},"b":{"result_id":"tool:1"}},"unit":"million USD"}}.
This example specifies references, not the formula or sources for your task.
For a percentage change, use the change divided by the requested earlier base,
with output unit percent: the tool applies the percent conversion itself.
Before Final, execute the required last calculation. Final must name that
successful result_id and report its value in the requested unit. A component
side check does not supply Final evidence unless Final actually depends on it.
Do not fabricate result IDs, source observations, periods or missing evidence.
The first Final terminates the rollout; it is not a proposal for later repair.
""".strip()

ADOPTION = {
    "endpoint": """
Requested evidence-route commitment for this run: endpoint.
Use source-supported reported endpoints of the requested financial quantity at
the specified actual periods as the primary Final support, then compute the
requested difference or relative change. A reconstructed or unrelated quantity
must not be substituted merely to obtain the expected-looking number. Retain
the actual earlier endpoint as the base when the question asks for a rate.
""".strip(),
    "movement": """
Requested evidence-route commitment for this run: movement.
Actively construct primary Final support from disclosed components, changes or
movements whose financial definitions establish the requested target at its
specified actual periods. For an annual-flow target, use the disclosed within-
year flow components; for a stock change use the disclosed roll-forward
movements; for a company-defined metric reconstruct it from its disclosed
definition and components. Determine the appropriate facts from public sources.
Do not use a difference of two reported target endpoints as this primary route.
A reported earlier target value may be retained as the base for a growth rate
where financially appropriate. Compute the component/movement result with
executed tool references and make Final depend on that result. Reading a
component and then delivering an endpoint-only or literal-only calculation
does not fulfill this requested route. Do not invent a decomposition if public
evidence does not establish it. No oracle answer or route-specific fact list is
provided; this request does not determine the evaluator's actual method label.
""".strip(),
}


def require(value, code):
    if not value:
        raise ValueError("probe01." + code)


def encode(value):
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode()


def sha(value):
    if isinstance(value, Path):
        with value.open("rb") as stream:
            return hashlib.file_digest(stream, "sha256").hexdigest()
    return hashlib.sha256(value.encode() if isinstance(value, str) else value).hexdigest()


def record(kind, **fields):
    require(not {"id", "schema_version"} & set(fields), "reserved_record_fields")
    body = {"schema_version": "probe_coverage.v1." + kind, **copy.deepcopy(fields)}
    return {**body, "id": kind + ":" + sha(encode(body))}


def checked(value, kind):
    require(isinstance(value, dict), "record_object")
    expected = record(
        kind, **{key: item for key, item in value.items() if key not in {"id", "schema_version"}}
    )
    require(value == expected, "content_identity:" + kind)
    return value


def now():
    return datetime.now(timezone.utc).isoformat()


def write_once(path, value):
    path = Path(path)
    require(
        ".." not in path.parts and not any(p.is_symlink() for p in (path, *path.parents)),
        "safe_exclusive_path",
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        stream.write(encode(value))
        stream.flush()
        os.fsync(stream.fileno())
    return value


def system_prompt(profile, basis):
    require(profile in PROFILES and basis in BASES, "registered_profile_and_guidance")
    result = original.SYSTEM + "\n" + original.GUIDANCE[basis]
    if profile != PROFILES[0]:
        result += "\n\n" + DELIVERY
    if profile == PROFILES[2]:
        result += "\n\n" + ADOPTION[basis]
    return result


def policy():
    return record(
        "coverage_policy",
        experiment="0.1 Probe behavior coverage, not training",
        branch=BRANCH,
        parent_commit=BASE_COMMIT,
        requested_user_audit=(
            "Phase0 PASS; recover real multi-state support before "
            "fixed-distribution/VTDO/HierLoss training"
        ),
        design_dimensions_chosen_prospectively_under_standing_API_authorization=True,
        task_selection=(
            "first two distinct source_cluster tasks sorted by TaskID in each "
            "family x quantity stratum; no qualification/success filter"
        ),
        families=list(FAMILIES),
        quantities=list(QUANTITIES),
        tasks_per_stratum=TASKS_PER_STRATUM,
        task_count=TASK_CAP,
        protocol_profiles=list(PROFILES),
        requested_bases=list(BASES),
        replicates=REPLICATES,
        registered_rollouts=SESSION_CAP,
        assignment_order_seed=ORDER_SEED,
        assignment_seed_is_not_a_provider_generation_seed=True,
        all_conditions_fresh_and_interleaved=True,
        generation_workers=WORKERS,
        maximum_responses=MAX_RESPONSES,
        maximum_tools=MAX_TOOLS,
        model=MODEL,
        accepted_response_models=[MODEL],
        endpoint=ENDPOINT,
        thinking={"type": "enabled"},
        reasoning_effort="high",
        response_format={"type": "json_object"},
        max_tokens=OUTPUT_ALLOWANCE,
        stream=False,
        temperature_top_p_seed_omitted=True,
        model_switch_or_fallback=False,
        maximum_serialized_body_bytes=MAX_BODY_BYTES,
        input_reservation=INPUT_ALLOWANCE,
        output_reservation=OUTPUT_ALLOWANCE,
        per_request_reservation=REQUEST_RESERVATION,
        request_cap=REQUEST_CAP,
        purpose_token_cap=TOKEN_CAP,
        common_token_cap=COMMON_CAP,
        same_existing_wallet=True,
        old_charges_or_unknown_leases_reclaimed=False,
        cap_does_not_guarantee_every_rollout_completes_32_responses=True,
        transport_retries=0,
        response_or_trajectory_resampling=0,
        stop_on_first_Final=True,
        failed_unrequested_and_UNDETERMINED_remain_in_full_denominators=True,
        source_task_public_messages_private_reference_and_qualification_rules_unchanged=True,
        only_generation_system_protocol_is_varied=True,
        no_route_specific_source_ID_or_private_target_in_prompt=True,
        scripted_examples_or_controls_are_not_Probe_data=True,
        requested_basis_does_not_assign_actual_method=True,
        original_finite_financial_and_fine_mapper_used=True,
        finite_sample_coverage_is_not_population_generation_probability=True,
        CPU_token_consumability=(
            "all authentic financially valid MAPPED complete rollouts, after full "
            "registry terminal; original 24576 cap, no truncation"
        ),
        maximum_sequence_length=SEQUENCE_CAP,
        separate_probe_only_corpus=True,
        creates_original_AB_material_pool=False,
        training_eligible=False,
        Student_weight_loads=0,
        Student_runs=0,
        GPU_operations=0,
        training_gate=(
            "original quotas, common AB, 8+2 and population gates remain unchanged; "
            "discovery alone grants no training"
        ),
        development_or_confirmation_Student_outputs_read=False,
        public_prompts=[
            {
                "profile": profile,
                "guidance": basis,
                "system_prompt": system_prompt(profile, basis),
                "system_prompt_sha256": sha(system_prompt(profile, basis)),
            }
            for profile in PROFILES
            for basis in BASES
        ],
    )


def select_tasks(catalog):
    require(isinstance(catalog, dict) and isinstance(catalog.get("tasks"), list), "task_catalog")
    tasks = catalog["tasks"]
    require(
        len(tasks) == 255 and len({x["task_id"] for x in tasks}) == 255, "complete_original_catalog"
    )
    selected = []
    fields = (
        "task_id",
        "family",
        "quantity",
        "source_cluster",
        "bundle_id",
        "bundle_path",
        "public_path",
        "public_messages_sha256",
        "surface_version_id",
        "parent_manifest_id",
        "parent_directory",
        "native_bindings_path",
        "scale_group",
    )
    for family in FAMILIES:
        for quantity in QUANTITIES:
            eligible = sorted(
                (x for x in tasks if x["family"] == family and x["quantity"] == quantity),
                key=lambda x: x["task_id"],
            )
            chosen, clusters = [], set()
            for row in eligible:
                require(
                    isinstance(row["source_cluster"], str) and row["source_cluster"],
                    "source_cluster_identity",
                )
                if row["source_cluster"] not in clusters:
                    chosen.append({key: row[key] for key in fields})
                    clusters.add(row["source_cluster"])
                if len(chosen) == TASKS_PER_STRATUM:
                    break
            require(len(chosen) == TASKS_PER_STRATUM, "two_distinct_sources_per_registered_stratum")
            selected.extend(chosen)
    require(
        len(selected) == TASK_CAP and len({x["task_id"] for x in selected}) == TASK_CAP,
        "fixed_twelve_tasks",
    )
    return selected


def make_registry(tasks, freeze_id):
    require(
        len(tasks) == TASK_CAP and len({x["task_id"] for x in tasks}) == TASK_CAP,
        "registry_twelve_unique_tasks",
    )
    rows = []
    for task in tasks:
        for profile in PROFILES:
            for basis in BASES:
                for replicate in range(REPLICATES):
                    identifier = "probe01_session_" + sha(
                        encode([freeze_id, task["task_id"], profile, basis, replicate])
                    )
                    rows.append(
                        {
                            "session_id": identifier,
                            "task_id": task["task_id"],
                            "family": task["family"],
                            "quantity": task["quantity"],
                            "profile": profile,
                            "basis": basis,
                            "replicate": replicate,
                            "identity": {
                                key: task[key]
                                for key in (
                                    "task_id",
                                    "family",
                                    "surface_version_id",
                                    "public_messages_sha256",
                                    "parent_manifest_id",
                                )
                            },
                            "system_prompt_sha256": sha(system_prompt(profile, basis)),
                        }
                    )
    random.Random(ORDER_SEED).shuffle(rows)
    require(len(rows) == SESSION_CAP, "complete_144_registration")
    return [{"ordinal": i, **row} for i, row in enumerate(rows)]


def validate_registry(rows, tasks, freeze_id):
    require(
        encode(rows) == encode(make_registry(tasks, freeze_id)),
        "exact_preregistered_matrix_and_order",
    )
