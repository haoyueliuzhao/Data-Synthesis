"""Scoped native-record backfill through the existing fact/quality/KG builders.

Only the actual missing annual periods and registered statement components are
read. No FinQA question, answer, program, screening label or model output is an
input to this adapter. Original archived parents remain read-only.
"""

import json
import re
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path

from finraw.atomic_facts import _fact, _with_build
from finraw.builds import ensure_build_schema, finish_build, start_build
from finraw.derived_facts import refresh_derived_facts
from finraw.fact_quality import enforce_fact_quality_gates
from finraw.fact_standardization import refresh_fact_standardization
from finraw.kg_builder import build_kg, ensure_kg_schema

from . import issuer_tables
from .archive import WORK, RecordDB, insert, record, require, sha, write_json
from .protocol import CASH, METRIC_TAGS, NEW_FLOW_METRICS, RESTRICTED, source_identity, source_split


def resolve_raw(root, value):
    raw = str(value["storage_uri"])
    prefix = "/workspace/Data Synthesis/"
    if raw.startswith(prefix):
        relative = raw[len(prefix) :]
    else:
        require(
            raw.startswith((
                "trusted_data_synthesis/artifacts/qa_vnext_surface_build/",
                "trusted_data_synthesis/artifacts/qa_vnext_catalog_bridge/",
            )),
            "native.registered_new_source_storage_prefix",
        )
        relative = raw
    path = Path(root) / relative
    require(path.resolve().is_relative_to(Path(root).resolve()), "native.source_path_containment")
    require(path.is_file() and not path.is_symlink(), "native.original_file_available")
    require(
        path.stat().st_size == value["content_size_bytes"] and sha(path) == value["content_sha256"],
        "native.original_byte_identity",
    )
    return path


def annual_observation(item, *, instant=False):
    if item.get("form") not in {"10-K", "10-K/A"} or item.get("fp") != "FY":
        return False
    try:
        end = date.fromisoformat(item["end"])
        value = Decimal(str(item["val"]))
        if not value.is_finite() or not 2010 <= end.year <= 2025 or item.get("fy") != end.year:
            return False
        if instant:
            return not item.get("start")
        start = date.fromisoformat(item["start"])
        return 330 <= (end - start).days + 1 <= 380
    except (KeyError, ValueError, TypeError, InvalidOperation):
        return False


def select_native(payload, entity, raw):
    """Choose by source metadata before testing any financial equality."""
    require(str(payload["cik"]).zfill(10) == str(entity["cik"]).zfill(10), "native.entity_CIK_join")
    require(source_split(source_identity(entity)) == "train", "native.fixed_source_usage")
    grouped, rejected = defaultdict(list), Counter()
    definitions = {}
    taxonomy = payload.get("facts", {}).get("us-gaap", {})
    for metric, tags in METRIC_TAGS.items():
        for priority, tag in enumerate(tags):
            concept = taxonomy.get(tag)
            if not concept:
                rejected["missing_tag:" + tag] += 1
                continue
            require(
                isinstance(concept.get("description"), str) and bool(concept["description"]),
                "native.definition_text_present",
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
                if not annual_observation(item, instant=metric in {CASH, RESTRICTED}):
                    rejected["outside_registered_annual_observation"] += 1
                    continue
                period = (item.get("start"), item["end"])
                key = (period[0], period[1], str(Decimal(str(item["val"]))))
                grouped[(metric, *period)].append(
                    {
                        "metric_id": metric,
                        "tag": tag,
                        "tag_priority": priority,
                        "record": item,
                        "pointer": f"/facts/us-gaap/{tag}/units/USD/{index}",
                        "all_equal_source_occurrences": occurrences[key],
                        "native_definition": definitions[tag],
                    }
                )
    chosen = []
    for key in sorted(grouped, key=lambda value: tuple(str(item) for item in value)):
        values = grouped[key]
        preferred = min(value["tag_priority"] for value in values)
        values = [value for value in values if value["tag_priority"] == preferred]
        values.sort(
            key=lambda value: (
                value["record"].get("filed", ""),
                value["record"].get("accn", ""),
                value["pointer"],
            )
        )
        latest = values[-1]
        tied = [
            value
            for value in values
            if (value["record"].get("filed"), value["record"].get("accn"))
            == (latest["record"].get("filed"), latest["record"].get("accn"))
        ]
        if len({str(Decimal(str(value["record"]["val"]))) for value in tied}) != 1:
            rejected["conflicting_same_vintage_amounts"] += 1
            continue
        chosen.append(
            {
                **latest,
                "entity_id": entity["entity_id"],
                "source_cluster": source_identity(entity),
                "raw_object_id": raw["raw_object_id"],
                "raw_sha256": raw["content_sha256"],
                "native_unit": "USD",
                "split": "train",
                "allowed_uses": ["train"],
            }
        )
    return chosen, definitions, dict(rejected)


def source_inputs(root, archived):
    entities = {
        value["entity_id"]: value
        for value in archived.fetchall(
            "SELECT * FROM canonical_entities WHERE entity_type='company' AND market='US'"
        )
    }
    selected_entities = [
        value for value in entities.values() if source_split(source_identity(value)) == "train"
    ]
    selected_entities.sort(key=source_identity)
    raw_rows = archived.fetchall("SELECT * FROM raw_objects WHERE source_id='sec_companyfacts'")
    prepared = []
    for entity in selected_entities:
        cik = str(entity["cik"]).zfill(10)
        matches = [raw for raw in raw_rows if f"cik={cik}/" in str(raw["storage_uri"])]
        raw = select_snapshot(matches)
        path = resolve_raw(root, raw)
        prepared.append((entity, raw, path, matches))

    def read(item):
        entity, raw, path, matches = item
        chosen, definitions, rejected = select_native(json.loads(path.read_bytes()), entity, raw)
        return {
            "entity": entity,
            "raw_object": raw,
            "local_path": str(path.relative_to(root)),
            "observations": chosen,
            "definitions": definitions,
            "selection_exclusions": rejected,
            "all_pinned_snapshot_references": matches,
            "snapshot_selection": (
                "latest snapshot date, then raw_object_id, before inspecting values"
            ),
        }

    with ThreadPoolExecutor(max_workers=8) as executor:
        return list(executor.map(read, prepared))


def select_snapshot(matches):
    require(bool(matches), "native.pinned_snapshot_available")

    def key(row):
        date_match = re.search(r"/snapshot_date=(\d{4}-\d{2}-\d{2})\.json$", row["storage_uri"])
        require(date_match is not None, "native.snapshot_date_in_pinned_path")
        return date_match.group(1), row["raw_object_id"]

    return max(matches, key=key)


def populate_ontology(db, archived, inputs, issuer=None):
    issuer = issuer or {"observations": []}
    # Actual new ontology/source-definition builds are used when the registered
    # bridge introduces exchange-rate/change metrics not present in the archive.
    metric_build = start_build(
        db,
        layer="metric_ontology",
        command="task-build-native-component-extension",
        prefix="metric_ontology",
    )
    metrics = archived.fetchall("SELECT * FROM metrics")
    by_metric = {row["metric_id"]: row for row in metrics}
    for metric in NEW_FLOW_METRICS:
        tag = METRIC_TAGS[metric][0]
        available = [item["definitions"][tag] for item in inputs if tag in item["definitions"]]
        if not available:
            continue
        by_metric[metric] = {
            "metric_id": metric,
            "canonical_name": available[0]["label"] or tag,
            "metric_category": "financial_statement",
            "statement_type": "cash_flow_statement",
            "period_type": "period_flow",
            "default_unit": "monetary",
            "default_currency": "USD",
            "accounting_standard": "US_GAAP",
            "aggregation_rule": "signed period flow; exact native concept scope",
            "revision_risk": "medium",
            "ambiguity_notes": "Restricted-cash and cash-only scopes must not be combined.",
        }
    issuer_metrics, _ = issuer_tables.ontology_rows(issuer, metric_build, None)
    by_metric.update({row["metric_id"]: row for row in issuer_metrics})
    for value in by_metric.values():
        value.update(build_id=metric_build, is_active=1, superseded_by=None)
    insert(db, "metrics", list(by_metric.values()))
    finish_build(
        db,
        metric_build,
        "success",
        "Archived ontology plus native SEC component definitions; no synthetic amounts",
    )
    definition_build = start_build(
        db,
        layer="source_definitions",
        command="task-build-native-source-definitions",
        prefix="source_definitions",
        input_build_id=metric_build,
    )
    originals = archived.fetchall("SELECT * FROM source_metric_definitions")
    by_tag = {
        value["raw_concept_name"]: value
        for value in originals
        if value["source_id"] == "sec_companyfacts"
    }
    rows = []
    for metric, tags in METRIC_TAGS.items():
        for tag in tags:
            available = [
                (item, item["definitions"][tag]) for item in inputs if tag in item["definitions"]
            ]
            if not available:
                continue
            texts = {value[1]["description"] for value in available}
            require(len(texts) == 1, "native.taxonomy_definition_version_consistent")
            full = "us-gaap:" + tag
            value = dict(by_tag.get(full) or {})
            native = record(
                "native_definition",
                concept=full,
                description=next(iter(texts)),
                raw_sha256s=sorted(item[0]["raw_object"]["content_sha256"] for item in available),
            )
            value.update(
                definition_id="sdef_task_" + native["id"].split(":")[1][:24],
                source_id="sec_companyfacts",
                metric_id=metric,
                raw_concept_name=full,
                definition_text=next(iter(texts)),
                unit_rule="Original USD / 1000000 = million USD; exact Decimal gate",
                frequency="annual",
                vintage_policy=(
                    "fixed snapshot; registered filing-year filter and latest filed/accession; "
                    "raw occurrences retained"
                ),
                is_forecast=0,
                comparable_to_metric_id=metric,
                comparability_level="xbrl_concept_level",
                notes=json.dumps(
                    {
                        "original_archived_definition_id": by_tag.get(full, {}).get(
                            "definition_id"
                        ),
                        "native_definition_reference": native,
                    },
                    sort_keys=True,
                ),
                build_id=definition_build,
                is_active=1,
                superseded_by=None,
            )
            rows.append(value)
    _, issuer_definitions = issuer_tables.ontology_rows(issuer, metric_build, definition_build)
    insert(db, "source_metric_definitions", rows + issuer_definitions)
    finish_build(
        db,
        definition_build,
        "success",
        "Exact descriptions bound to original native SEC snapshot bytes",
    )
    return metric_build, definition_build


def populate_facts(db, inputs, issuer=None):
    fact_build = start_build(
        db, layer="fact_build", command="task-build-native-annual-backfill", prefix="fact_build"
    )
    document_build = start_build(
        db,
        layer="document",
        command="task-build-native-JSON-documents",
        prefix="document_build",
        input_build_id=fact_build,
    )
    facts, bindings, docs = [], {}, []
    definitions = {
        (row["metric_id"], row["raw_concept_name"]): row["definition_id"]
        for row in db.fetchall("SELECT * FROM source_metric_definitions")
    }
    for item in inputs:
        raw, entity = item["raw_object"], item["entity"]
        document_id = "doc_task_" + raw["content_sha256"][:24]
        docs.append(
            {
                "document_id": document_id,
                "stable_document_id": document_id,
                "build_id": document_build,
                "entity_id": entity["entity_id"],
                "source_id": "sec_companyfacts",
                "form_type": "SEC_COMPANYFACTS_JSON",
                "report_type": "pinned_native_snapshot",
                "storage_uri": raw["storage_uri"],
                "original_url": raw["original_url"],
                "raw_object_id": raw["raw_object_id"],
                "document_status": "passed",
                "is_active": 1,
                "notes": json.dumps(
                    {
                        "validation": (
                            "original raw byte identity and CIK join; not an HTML filing extraction"
                        )
                    }
                ),
            }
        )
        for value in item["observations"]:
            native = value["record"]
            fact = _fact(
                entity_id=entity["entity_id"],
                metric_id=value["metric_id"],
                value=Decimal(str(native["val"])),
                unit="USD",
                currency="USD",
                period_start=native.get("start"),
                period_end=native["end"],
                fiscal_year=native["fy"],
                fiscal_quarter="FY",
                as_of_date=native["filed"],
                report_date=native["end"],
                source_id="sec_companyfacts",
                raw_object_id=raw["raw_object_id"],
                source_field_name="us-gaap:" + value["tag"],
                source_page_or_table=value["pointer"],
                extraction_method="xbrl",
                confidence_score=0.98,
                verification_status="single_source",
                tolerance=None,
                notes=json.dumps(
                    {
                        "native_binding": value,
                        "document_id": document_id,
                        "frequency": "annual",
                        "period_role": "instant" if not native.get("start") else "annual_flow",
                        "financial_scope_type": "consolidated_entity",
                        "entity_scope_id": entity["entity_id"],
                    },
                    sort_keys=True,
                ),
                stable_parts=[
                    "task_native_annual_v1",
                    raw["content_sha256"],
                    entity["entity_id"],
                    value["tag"],
                    value["pointer"],
                ],
            )
            fact = _with_build(fact, fact_build)
            facts.append(fact)
            bindings[fact["fact_id"]] = {
                **value,
                "document_id": document_id,
                "atomic_build_id": fact_build,
                "source_definition_id": definitions[value["metric_id"], "us-gaap:" + value["tag"]],
            }
    db.insert_atomic_facts(facts)
    insert(db, "source_documents", docs)
    if issuer is not None:
        bindings.update(issuer_tables.populate(db, issuer, fact_build, document_build, bindings))
    finish_build(
        db,
        fact_build,
        "success",
        f"{len(bindings)} exact source records; native annual and issuer-table adapters",
    )
    finish_build(
        db, document_build, "success", "Original JSON snapshots and qualified issuer HTML tables"
    )
    return fact_build, document_build, bindings


def run(root, output, *, work=WORK, extra_issuer_sources=(), prepared_context=None):
    root, output = Path(root).resolve(), Path(output)
    database = root / work / "native_fact_qa.sqlite3"
    database.parent.mkdir(parents=True, exist_ok=True)
    require(not database.exists(), "native.new_scoped_database_only")
    archived = RecordDB(str(root / WORK / "qa_build.sqlite3"))
    # Reading the archive projection does not activate or amend old builds.
    if prepared_context is None:
        inputs = source_inputs(root, archived)
        issuer = issuer_tables.prepare(root, archived, inputs, extra_sources=extra_issuer_sources)
    else:
        require(not extra_issuer_sources, "native.single_explicit_input_provider")
        # The provider must pin a prior source manifest and preserve its admitted
        # records. It may append only the newly frozen source extension. Actual
        # Fact/quality/KG construction below is shared, never fabricated in caller.
        inputs, issuer = prepared_context(root, archived)
    write_json(output / "issuer_source_tables.json", issuer)
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
    db = RecordDB(str(database))
    db.init_schema()
    ensure_build_schema(db)
    ensure_kg_schema(db)
    with db.transaction():
        insert(db, "canonical_entities", archived.fetchall("SELECT * FROM canonical_entities"))
        # Source registry content is another original archived node, not a guessed authority flag.
        for source_id in ("sec_companyfacts", "sec_filings"):
            source = archived.fetchone(
                "SELECT properties_json FROM kg_nodes "
                "WHERE source_table='source_registry' AND source_pk=?",
                (source_id,),
            )
            require(bool(source), "native.archived_source_registry_parent")
            insert(
                db, "source_registry", [{**json.loads(source["properties_json"]), "is_active": 1}]
            )
        insert(db, "raw_objects", [item["raw_object"] for item in inputs])
        metric_build, definition_build = populate_ontology(db, archived, inputs, issuer)
        fact_build, document_build, bindings = populate_facts(db, inputs, issuer)
    archived.close()
    write_json(output / "native_bindings.json", bindings)
    reports = {}
    reports["standardization"] = refresh_fact_standardization(db, {})
    reports["fact_quality"] = enforce_fact_quality_gates(
        db, {"fact_quality_gates": {"min_graph_ready_count": 20}}
    )
    # A real DerivedFact build is required by the KG API. These are upstream
    # oracle data, not the later task targets and never a substitute for a model.
    reports["derived"] = refresh_derived_facts(
        db,
        {
            "kg": {
                "derived_policy": {
                    "multi_year_windows": [],
                    "long_window_return_years": [],
                    "annual_filing_sources": ["sec_companyfacts", "sec_filings"],
                }
            }
        },
    )
    reports["kg"] = build_kg(db, {}, activate=False)
    kg_id = reports["kg"]["kg_build_id"]
    kg = db.fetchone("SELECT * FROM kg_builds WHERE kg_build_id=?", (kg_id,))
    require(
        kg["status"] == "success" and kg["quality_status"] == "passed",
        "native.actual_KG_quality_passed",
    )
    # SQLite REAL is never assumed to preserve arbitrary precision. Bound
    # amounts must match the original exact Decimal scale, or remain excluded.
    precision = []
    for fact in db.fetchall(
        "SELECT * FROM standardized_facts WHERE build_id=?", (kg["input_fact_build_id"],)
    ):
        bound = bindings[fact["fact_id"]]
        scale = 1 if bound.get("source_kind") == "issuer_report_table" else 1000000
        exact = Decimal(str(bound["record"]["val"])) / Decimal(scale)
        actual = Decimal(str(fact["normalized_value"]))
        if actual != exact:
            precision.append(
                {
                    "fact_id": fact["fact_id"],
                    "native_normalized_exact": str(exact),
                    "stored": str(actual),
                }
            )
    summary = record(
        "native_fact_build",
        status="REAL_FACT_STANDARDIZATION_QUALITY_DERIVED_KG_BUILDS_EXECUTED",
        source_company_count=len(inputs),
        source_observation_count=len(bindings),
        issuer_FCF_source_counts=issuer["counts"],
        issuer_FCF_rejection_reasons=dict(Counter(row["reason"] for row in issuer["failures"])),
        fact_build_id=fact_build,
        metric_build_id=metric_build,
        source_definition_build_id=definition_build,
        document_build_id=document_build,
        kg_build=kg,
        reports=reports,
        precision_exclusions=precision,
        database_path=str(database.relative_to(root)),
        native_input_parent="verified archived source/entity/ontology/raw-object references",
        original_archives_mutated=False,
        original_database_mutated=False,
        model_calls=0,
        oracle_executions_are_Teacher_trajectories=False,
    )
    write_json(output / "native_fact_build_report.json", summary)
    db.close()
    return summary
