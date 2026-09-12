"""One frozen six-document UNP extension; all earlier admitted records are reused."""

import json
from pathlib import Path

from ..finance_qa_vnext_catalog_bridge.catalog import Parent, safe_path
from ..finance_qa_vnext_task_build import native_facts
from ..finance_qa_vnext_task_build.archive import record, require, sha
from ..finance_qa_vnext_task_build.protocol import source_identity, source_split

BRIDGE = "trusted_data_synthesis/artifacts/qa_vnext_catalog_bridge/catalog_bridge_20260912"
BRIDGE_MANIFEST = "manifest:93e7733ea14ee5ce52dfaf657c63086e18b73667c30300daf3971b9b1fde5136"
CACHE = BRIDGE + "/incremental"
CACHE_MANIFEST = "manifest:818206eaf7822fdc68ddfb5ad4055301467f307ca2d3c307273f024030b0fcc2"
CIK = "cik:0000100885"
ENTITY = "UNP_US"
MAX_NEW_TASKS = 17
REQUEST_CAP = 34
TOKEN_CAP = 330_752
RAW_IDS = {
    "2020-12-31": "rawobj_sec_filings_d1a54ca80e05a968c4b97722",
    "2021-12-31": "rawobj_sec_filings_82c67e42a3a4592192959884",
    "2022-12-31": "rawobj_sec_filings_df74ee279bd8e89d812b3ab5",
    "2023-12-31": "rawobj_sec_filings_9c3597bc393d12fc5a301094",
    "2024-12-31": "rawobj_sec_filings_a31296f247110db86bb12f1f",
    "2025-12-31": "rawobj_sec_filings_95565f51e3ac8a7f8e90411d",
}
CACHED_FILES = ("native_source_inventory.json", "native_bindings.json", "issuer_source_tables.json")


def policy():
    return record(
        "training_increment_source_policy",
        source_scope="only six already archived UNP annual reports, 2020 through 2025",
        source_cluster=CIK,
        entity_id=ENTITY,
        registered_raw_objects=RAW_IDS,
        new_HTTP_requests=0,
        Oracle_403_retries=0,
        other_issuer_source_parsing=0,
        old_native_selection="reuse all 1995 previously admitted JSON observations exactly",
        old_issuer_selection="reuse 24 admitted periods and 20 parsed tables without re-extraction",
        taxonomy_metadata=(
            "read label/description only for original registered tags; no new observations"
        ),
        source_enumeration=(
            "all six once; every failure retained; latest legally admitted "
            "vintage per actual period"
        ),
        task_enumeration=(
            "existing factory on UNP issuer facts only; subtract old 243 identities; fixed order"
        ),
        new_task_cap=MAX_NEW_TASKS,
        total_candidate_cap=260,
        company_defined_candidate_cap=53,
        rewrite_request_cap=REQUEST_CAP,
        rewrite_token_cap=TOKEN_CAP,
        per_task_rewrite_cap=2,
        previous_known_common_debit=221538,
        observed_Teacher_outcomes_used=False,
        cap_excess_retained=True,
        live_Teacher_allowed_here=False,
        original_sources_and_tasks_rewritten=False,
    )


def cache_parent(root):
    return Parent(root, CACHE, CACHE_MANIFEST)


def select_sources(issuer):
    selected = [row for row in issuer["sources"] if row["entity"]["entity_id"] == ENTITY]
    require(len(selected) == len(RAW_IDS), "increment.exact_six_UNP_sources")
    seen = set()
    for source in selected:
        entity, document, raw = source["entity"], source["document"], source["raw_object"]
        end = document["period_end"]
        require(
            end not in seen and RAW_IDS.get(end) == raw["raw_object_id"],
            "increment.frozen_UNP_document_identity",
        )
        require(
            source_identity(entity) == CIK and source_split(CIK) == "train",
            "increment.original_UNP_train_split",
        )
        require(
            document["entity_id"] == ENTITY and document["raw_object_id"] == raw["raw_object_id"],
            "increment.archived_document_raw_join",
        )
        require(document["form_type"] == "10-K", "increment.original_annual_report")
        seen.add(end)
    return sorted(selected, key=lambda row: row["document"]["period_end"])


def source_file(root, raw, role):
    path = native_facts.resolve_raw(root, raw)
    relative = str(path.relative_to(root))
    require(safe_path(root, relative) == path, "increment.no_source_symlink")
    return {
        "path": relative,
        "sha256": raw["content_sha256"],
        "bytes": raw["content_size_bytes"],
        "role": role,
    }


def metadata(root):
    """Read source metadata and hashes only; never invoke any source parser."""
    root = Path(root).resolve()
    parent = cache_parent(root)
    inventory = parent.read("native_source_inventory.json")
    issuer = parent.read("issuer_source_tables.json")
    require(len(inventory) == 14, "increment.fixed_fourteen_native_sources")
    clusters = [source_identity(row["entity"]) for row in inventory]
    require(
        len(set(clusters)) == 14 and all(source_split(key) == "train" for key in clusters),
        "increment.original_fourteen_train_clusters",
    )
    require(
        len(issuer["observations"]) == 24 and len(issuer["tables"]) == 20,
        "increment.fixed_admitted_issuer_cache",
    )
    require(
        not any(row["entity_id"] == ENTITY for row in issuer["observations"]),
        "increment.UNP_not_already_admitted_issuer",
    )
    selected = select_sources(issuer)
    sources = [
        source_file(root, row["raw_object"], "cached_native_taxonomy_metadata") for row in inventory
    ]
    sources += [
        source_file(root, row["raw_object"], "new_UNP_bounded_table_parser") for row in selected
    ]
    cache_files = [
        {"path": CACHE + "/" + name, **{k: parent.members[name][k] for k in ("sha256", "bytes")}}
        for name in CACHED_FILES
    ]
    bridge = Parent(root, BRIDGE, BRIDGE_MANIFEST)
    old_catalog = bridge.read("catalog.json")
    require(len(old_catalog["tasks"]) == 243, "increment.old_243_catalog")
    cache_files.append(
        {
            "path": BRIDGE + "/catalog.json",
            **{k: bridge.members["catalog.json"][k] for k in ("sha256", "bytes")},
        }
    )
    return record(
        "training_increment_source_metadata",
        policy_id=policy()["id"],
        cache_parent=parent.descriptor(),
        catalog_parent=bridge.descriptor(),
        selected_sources=selected,
        source_files=sources,
        cached_files=cache_files,
        native_source_count=14,
        cached_native_observations=1995,
        cached_issuer_periods=24,
        cached_issuer_tables=20,
        old_task_ids=sorted(row["task_id"] for row in old_catalog["tasks"]),
        new_source_contents_parsed=False,
        source_selection_precedes_outputs=True,
    )


def validate_metadata(root, frozen):
    require(frozen["policy_id"] == policy()["id"], "increment.frozen_source_rule")
    require(metadata(root) == frozen, "increment.source_metadata_or_parent_changed")
    for member in [*frozen["source_files"], *frozen["cached_files"]]:
        path = safe_path(Path(root).resolve(), member["path"])
        require(
            path.stat().st_size == member["bytes"] and sha(path) == member["sha256"],
            "increment.frozen_input_bytes",
        )


def cached_inputs(root, parent):
    """Restore exact selected records; reading taxonomy is not another selection."""
    inventory = parent.read("native_source_inventory.json")
    old = parent.read("native_bindings.json")
    observations = [
        value for value in old.values() if value.get("source_kind") != "issuer_report_table"
    ]
    require(len(observations) == 1995, "increment.exact_native_observation_count")
    output = []
    from ..finance_qa_vnext_task_build.protocol import METRIC_TAGS

    tags = {tag for values in METRIC_TAGS.values() for tag in values}
    for item in inventory:
        selected = [
            row
            for row in observations
            if row["raw_object_id"] == item["raw_object"]["raw_object_id"]
        ]
        require(
            bool(selected)
            and all(row["entity_id"] == item["entity"]["entity_id"] for row in selected),
            "increment.cached_native_entity_parent",
        )
        path = native_facts.resolve_raw(root, item["raw_object"])
        taxonomy = json.loads(path.read_bytes()).get("facts", {}).get("us-gaap", {})
        definitions = {
            tag: {"label": taxonomy[tag].get("label"), "description": taxonomy[tag]["description"]}
            for tag in tags
            if tag in taxonomy
        }
        require(
            all(row["native_definition"] == definitions[row["tag"]] for row in selected),
            "increment.cached_native_definition_identity",
        )
        # No call to annual_observation/select_native and no access to taxonomy units.
        output.append({**item, "observations": selected, "definitions": definitions})
    require(
        sum(len(item["observations"]) for item in output) == 1995,
        "increment.no_cached_observation_lost_or_duplicated",
    )
    return output
