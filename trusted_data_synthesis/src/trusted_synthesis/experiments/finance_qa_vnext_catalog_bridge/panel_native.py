"""Fixed-salt evaluation source adapter; no train-label or heldout-label rewriting."""

import json
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from pathlib import Path

from finraw.builds import ensure_build_schema
from finraw.derived_facts import refresh_derived_facts
from finraw.fact_quality import enforce_fact_quality_gates
from finraw.fact_standardization import refresh_fact_standardization
from finraw.kg_builder import build_kg, ensure_kg_schema

from ..finance_qa_vnext_task_build import native_facts
from ..finance_qa_vnext_task_build.archive import (
    WORK,
    RecordDB,
    insert,
    record,
    require,
    sha,
    write_json,
)
from ..finance_qa_vnext_task_build.protocol import (
    CASH,
    METRIC_TAGS,
    RESTRICTED,
    source_identity,
    source_split,
)

HISTORICAL_PANEL = (
    "trusted_data_synthesis/artifacts/qa_vnext_bidirectional_utility/"
    "three_tasks_24rep_flash_rerun_20260910/preparation/panel_selection.json"
)


def source_metadata(root, db):
    """Read only identities. No companyfacts numeric payload or new task is examined."""
    from ..finance_qa_vnext_bidirectional_utility.panel_specs import CONFIRM

    path = Path(root) / HISTORICAL_PANEL
    historical = json.loads(path.read_bytes())
    old_symbols = sorted({item["qa_id"].split("/")[0] for item in CONFIRM.values()})
    require(
        old_symbols == historical["company_clusters"]["confirm"],
        "panel.old_confirmation_authorities_agree",
    )
    entities = db.fetchall(
        "SELECT * FROM canonical_entities WHERE entity_type='company' AND market='US'"
    )
    sources = db.fetchall("SELECT * FROM raw_objects WHERE source_id='sec_companyfacts'")
    rows = []
    for entity in sorted(entities, key=source_identity):
        identity = source_identity(entity)
        refs = [raw for raw in sources if f"cik={identity[4:]}/" in raw["storage_uri"]]
        rows.append(
            {
                "entity": entity,
                "source_cluster": identity,
                "split": source_split(identity),
                "historical_confirmation_issuer": entity["ticker"] in old_symbols,
                "raw_object": native_facts.select_snapshot(refs) if refs else None,
                "all_pinned_snapshot_references": refs,
            }
        )
    return record(
        "panel_source_metadata",
        rows=rows,
        original_split_counts=dict(Counter(row["split"] for row in rows)),
        eligible_split_counts=dict(
            Counter(
                row["split"]
                for row in rows
                if row["split"] != "train"
                and not row["historical_confirmation_issuer"]
                and row["raw_object"]
            )
        ),
        historical_confirmation_authority={
            "path": HISTORICAL_PANEL,
            "sha256": sha(path),
            "id": historical["id"],
        },
        historical_confirmation_tickers=old_symbols,
        historical_confirmation_cik_bindings=[
            {
                "ticker": row["entity"]["ticker"],
                "source_cluster": row["source_cluster"],
                "split": row["split"],
            }
            for row in rows
            if row["historical_confirmation_issuer"]
        ],
        historical_confirmation_tickers_absent_from_archived_universe=sorted(
            set(old_symbols) - {row["entity"]["ticker"] for row in rows}
        ),
        historical_train_dev_issuers_blanket_excluded=False,
        identity_join="exact canonical archived ticker and CIK; no name or value matching",
        scope=(
            "frozen 100-company archive; new development metadata review, not blind source sampling"
        ),
    )


def select_native(payload, entity, raw, *, expected_split):
    require(expected_split in {"dev", "confirm"}, "panel.evaluation_split_only")
    identity = source_identity(entity)
    require(source_split(identity) == expected_split, "panel.original_salt_split_required")
    require(str(payload["cik"]).zfill(10) == identity[4:], "panel.native_CIK_join")
    grouped, rejected, definitions = defaultdict(list), Counter(), {}
    taxonomy = payload.get("facts", {}).get("us-gaap", {})
    for metric, tags in METRIC_TAGS.items():
        for priority, tag in enumerate(tags):
            concept = taxonomy.get(tag)
            if not concept:
                rejected["missing_tag:" + tag] += 1
                continue
            require(
                isinstance(concept.get("description"), str) and bool(concept["description"]),
                "panel.native_definition_present",
            )
            definitions[tag] = {
                "label": concept.get("label"),
                "description": concept["description"],
            }
            items = concept.get("units", {}).get("USD", [])
            occurrences = defaultdict(list)
            for index, item in enumerate(items):
                if isinstance(item, dict) and "val" in item:
                    key = (item.get("start"), item.get("end"), str(Decimal(str(item["val"]))))
                    occurrences[key].append(
                        {"pointer": f"/facts/us-gaap/{tag}/units/USD/{index}", "record": item}
                    )
            for index, item in enumerate(items):
                if not native_facts.annual_observation(item, instant=metric in {CASH, RESTRICTED}):
                    rejected["outside_registered_annual_observation"] += 1
                    continue
                period = (item.get("start"), item["end"])
                grouped[(metric, *period)].append(
                    {
                        "metric_id": metric,
                        "tag": tag,
                        "tag_priority": priority,
                        "record": item,
                        "pointer": f"/facts/us-gaap/{tag}/units/USD/{index}",
                        "all_equal_source_occurrences": occurrences[
                            (*period, str(Decimal(str(item["val"]))))
                        ],
                        "native_definition": definitions[tag],
                    }
                )
    chosen = []
    for key in sorted(grouped, key=lambda key: tuple(str(value) for value in key)):
        preferred = min(row["tag_priority"] for row in grouped[key])
        values = sorted(
            (row for row in grouped[key] if row["tag_priority"] == preferred),
            key=lambda row: (
                row["record"].get("filed", ""),
                row["record"].get("accn", ""),
                row["pointer"],
            ),
        )
        latest = values[-1]
        ties = [
            row
            for row in values
            if (row["record"].get("filed"), row["record"].get("accn"))
            == (latest["record"].get("filed"), latest["record"].get("accn"))
        ]
        if len({str(Decimal(str(row["record"]["val"]))) for row in ties}) != 1:
            rejected["conflicting_same_vintage_amounts"] += 1
            continue
        chosen.append(
            {
                **latest,
                "entity_id": entity["entity_id"],
                "source_cluster": identity,
                "raw_object_id": raw["raw_object_id"],
                "raw_sha256": raw["content_sha256"],
                "native_unit": "USD",
                "split": expected_split,
                "allowed_uses": [expected_split],
            }
        )
    return chosen, definitions, dict(rejected)


def build(root, output, database, metadata, split):
    """Actual fact -> standardization -> quality -> derived -> KG build after freeze."""
    root, output, database = Path(root).resolve(), Path(output), Path(database)
    require(split in {"dev", "confirm"}, "panel.evaluation_split_only")
    require(not database.exists(), "panel.new_database_only")
    database.parent.mkdir(parents=True, exist_ok=True)
    rows = [
        row
        for row in metadata["rows"]
        if row["split"] == split and not row["historical_confirmation_issuer"] and row["raw_object"]
    ]

    def read(row):
        entity, raw = row["entity"], row["raw_object"]
        path = native_facts.resolve_raw(root, raw)
        observations, definitions, rejected = select_native(
            json.loads(path.read_bytes()), entity, raw, expected_split=split
        )
        return {
            **row,
            "local_path": str(path.relative_to(root)),
            "observations": observations,
            "definitions": definitions,
            "selection_exclusions": rejected,
        }

    with ThreadPoolExecutor(max_workers=8) as executor:
        inputs = list(executor.map(read, rows))
    archived = RecordDB(str(root / WORK / "qa_build.sqlite3"))
    db = RecordDB(str(database))
    db.init_schema()
    ensure_build_schema(db)
    ensure_kg_schema(db)
    with db.transaction():
        insert(db, "canonical_entities", archived.fetchall("SELECT * FROM canonical_entities"))
        source = archived.fetchone(
            "SELECT properties_json FROM kg_nodes WHERE source_table='source_registry' "
            "AND source_pk='sec_companyfacts'"
        )
        require(source is not None, "panel.source_registry_parent")
        insert(db, "source_registry", [{**json.loads(source["properties_json"]), "is_active": 1}])
        insert(db, "raw_objects", [item["raw_object"] for item in inputs])
        metric_build, definition_build = native_facts.populate_ontology(db, archived, inputs)
        fact_build, document_build, bindings = native_facts.populate_facts(db, inputs)
    archived.close()
    reports = {
        "standardization": refresh_fact_standardization(db, {}),
        "fact_quality": enforce_fact_quality_gates(
            db, {"fact_quality_gates": {"min_graph_ready_count": 20}}
        ),
    }
    reports["derived"] = refresh_derived_facts(
        db,
        {
            "kg": {
                "derived_policy": {
                    "multi_year_windows": [],
                    "long_window_return_years": [],
                    "annual_filing_sources": ["sec_companyfacts"],
                }
            }
        },
    )
    reports["kg"] = build_kg(db, {}, activate=False)
    kg = db.fetchone("SELECT * FROM kg_builds WHERE kg_build_id=?", (reports["kg"]["kg_build_id"],))
    require(
        kg["status"] == "success" and kg["quality_status"] == "passed",
        "panel.actual_KG_quality_passed",
    )
    summary = record(
        "panel_native_build",
        split=split,
        database_path=str(database.relative_to(root)),
        kg_build=kg,
        metric_build_id=metric_build,
        source_definition_build_id=definition_build,
        fact_build_id=fact_build,
        document_build_id=document_build,
        reports=reports,
        source_company_count=len(inputs),
        native_observation_count=len(bindings),
        model_calls=0,
    )
    write_json(
        output / "native_source_inventory.json",
        [
            {
                key: value
                for key, value in item.items()
                if key not in {"observations", "definitions"}
            }
            for item in inputs
        ],
    )
    write_json(output / "native_bindings.json", bindings)
    write_json(output / "native_fact_build_report.json", summary)
    return db, inputs, bindings, summary
