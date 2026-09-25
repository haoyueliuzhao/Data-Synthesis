"""Deterministic, new-CIK calibration panel; no acquisition or model execution.

The caller freezes the 64-source registration before invoking ``build``.  Only
that inventory is read.  The original financial enumerator, real Fact/KG/QA
pipeline, actual-period contracts and lossless public compiler are reused.
Old task bodies, old outcomes and old private references are never inputs.
"""

import copy
import hashlib
import json
import re
import sqlite3
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import fixed_kernel_source_view_compact_20260915 as compact
import fixed_kernel_source_view_compile_20260915 as compiler
from finraw.builds import ensure_build_schema, finish_build, start_build
from finraw.derived_facts import refresh_derived_facts
from finraw.fact_quality import enforce_fact_quality_gates
from finraw.fact_standardization import refresh_fact_standardization
from finraw.kg_builder import build_kg, ensure_kg_schema
from finraw.qa import pipeline

from trusted_synthesis.experiments.finance_qa_vnext_catalog_bridge import panel_native
from trusted_synthesis.experiments.finance_qa_vnext_catalog_bridge import panels as original
from trusted_synthesis.experiments.finance_qa_vnext_eval_readiness import panel, panel_rules
from trusted_synthesis.experiments.finance_qa_vnext_task_build import native_facts
from trusted_synthesis.experiments.finance_qa_vnext_task_build.archive import (
    WORK,
    RecordDB,
    insert,
    require,
    sha,
    write_json,
)
from trusted_synthesis.experiments.finance_qa_vnext_task_build.factory import dump_parents
from trusted_synthesis.experiments.finance_qa_vnext_task_build.protocol import source_split

p = compact.p
SCRIPT = "trusted_data_synthesis/scripts/fixed_kernel_calibration_panel_20260926.py"
CODE_PATHS = (
    SCRIPT,
    compiler.SCRIPT,
    compact.SCRIPT,
    "trusted_data_synthesis/scripts/fixed_kernel_source_view_runtime_20260915.py",
    *(
        "trusted_data_synthesis/src/trusted_synthesis/experiments/" + name
        for name in (
            "finance_qa_vnext_catalog_bridge/panel_native.py",
            "finance_qa_vnext_catalog_bridge/panels.py",
            "finance_qa_vnext_catalog_bridge/panel_rules.py",
            "finance_qa_vnext_eval_readiness/panel.py",
            "finance_qa_vnext_eval_readiness/panel_rules.py",
            "finance_qa_vnext_eval_readiness/periods.py",
            "finance_qa_vnext_eval_readiness/assessment.py",
            "finance_qa_vnext_eval_readiness/runtime.py",
            "finance_qa_vnext_task_build/native_facts.py",
            "finance_qa_vnext_task_build/archive.py",
            "finance_qa_vnext_task_build/factory.py",
            "finance_qa_vnext_task_build/protocol.py",
            "finance_qa_vnext_task_build/relations.py",
        )
    ),
    *(
        "raw_financial_data_lake/finraw/" + name
        for name in (
            "builds.py",
            "atomic_facts.py",
            "derived_facts.py",
            "fact_quality.py",
            "fact_standardization.py",
            "kg_builder.py",
            "qa/pipeline.py",
            "qa/graph_patterns.py",
            "qa/operators.py",
            "qa/semantic_constraints.py",
            "qa/plans.py",
            "qa/store.py",
        )
    ),
)
SOURCE_COUNT = 64
GROUPS = tuple(panel_rules.GROUPS)
QUOTAS = dict.fromkeys(GROUPS, 60)
HISTORICAL_TICKERS = frozenset({"AAPL", "ABMD", "AMT", "BKR", "ECL", "KHC", "MRK", "UNP"})
PARENT_FREEZE = (
    "trusted_data_synthesis/artifacts/qa_vnext_fixed_kernel_value/"
    "parallel_tail_execution_20260914/preparation/execution_freeze.json"
)
HISTORICAL_METADATA = (
    "trusted_data_synthesis/artifacts/qa_vnext_eval_readiness/"
    "eval_readiness_20260912/panels/source_metadata.json"
)


def policy():
    return p.record(
        "calibration_panel_rule",
        registered_source_count=SOURCE_COUNT,
        source_split="original fixed-salt dev only; exclude all old 100 CIKs and 8 tickers",
        quotas=QUOTAS,
        source_acquisition_or_model_calls=0,
        new_Probe_materials=0,
        native_annual_years=[2010, 2025],
        financial_semantics="unchanged actual-period panel_rules.enumerate_all",
        candidate_order="CIK round robin; within CIK current-period end then task ID",
        prior_task_priority=[],
        compile_reserve_per_group=8,
        finite_continuation="next 8 from the already enumerated order until quota or exhaustion",
        missing_quota="BLOCK; no new source, changed group, outcome selection, or refill",
        compiled_view_failure="BLOCK whole panel; no task replacement",
        public_view_rule=compiler.rule(p),
        private_reference_generation="real Fact/KG/QA parents and original financial certificates",
        independent_period_and_amount_checks=True,
        original_financial_scoring_unchanged=True,
        minimum_history_growth_tokens=4096,
        context_tokens=24576,
        per_response_tokens=2048,
        evaluation_session_authorized_by_this_builder=False,
    )


def _source_root(root):
    return Path(p.read_json(Path(root) / PARENT_FREEZE)["source_root"]).resolve()


def _registered_rows(registration, historical):
    require(isinstance(registration.get("id"), str), "calibration.source_registration_identity")
    require(bool(registration.get("selection_rule")), "calibration.frozen_source_selection_rule")
    rows = registration.get("sources")
    require(isinstance(rows, list) and len(rows) == SOURCE_COUNT, "calibration.exact64_sources")
    require(len({row.get("cik") for row in rows}) == SOURCE_COUNT, "calibration.unique64_CIKs")
    for row in rows:
        cik = row.get("cik")
        require(isinstance(cik, str) and re.fullmatch(r"\d{10}", cik), "calibration.canonical_CIK")
        require("cik:" + cik not in historical, "calibration.no_old_CIK")
        require(source_split("cik:" + cik) == "dev", "calibration.original_dev_source_split")
        require(
            isinstance(row.get("ticker"), str)
            and row["ticker"]
            and row["ticker"].upper() not in HISTORICAL_TICKERS,
            "calibration.no_historical_confirmation_ticker",
        )
        require(isinstance(row.get("title"), str) and row["title"], "calibration.entity_title")
        path = Path(row["path"])
        require(path.is_absolute() and ".." not in path.parts, "calibration.exact_absolute_source")
        require(
            isinstance(row.get("sha256"), str)
            and re.fullmatch(r"[0-9a-f]{64}", row["sha256"])
            and type(row.get("bytes")) is int
            and row["bytes"] > 0,
            "calibration.registered_source_byte_identity",
        )
    require(len({row["path"] for row in rows}) == SOURCE_COUNT, "calibration.unique_source_paths")
    return copy.deepcopy(rows)


def _read_source(row):
    """Narrow resolver: this exact registered file, not an expanded path prefix."""
    path = Path(row["path"])
    require(
        path.is_file() and not path.is_symlink() and path.resolve() == path,
        "calibration.registered_regular_no_symlink_source",
    )
    raw_bytes = path.read_bytes()
    require(
        len(raw_bytes) == row["bytes"] and hashlib.sha256(raw_bytes).hexdigest() == row["sha256"],
        "calibration.source_bytes_unchanged",
    )
    payload = json.loads(raw_bytes)
    cik = row["cik"]
    entity = {
        "entity_id": "CIK_" + cik + "_US",
        "canonical_name": row["title"],
        "entity_type": "company",
        "market": "US",
        "country": "US",
        "ticker": row["ticker"],
        "cik": cik,
        "currency": "USD",
        "fiscal_year_end": None,
        "is_active": 1,
    }
    raw = {
        "raw_object_id": "rawobj_calibration_companyfacts_" + row["sha256"][:24],
        "source_id": "sec_companyfacts",
        "object_type": "json",
        "storage_uri": str(path),
        "original_url": "https://data.sec.gov/api/xbrl/companyfacts/CIK" + cik + ".json",
        "request_params": {"cik": cik, "ticker": row["ticker"]},
        "content_sha256": row["sha256"],
        "content_size_bytes": row["bytes"],
        "parse_status": "unparsed",
        "validation_status": "passed",
        "notes": "Exact registered source bytes and CIK; acquisition receipt belongs to caller",
    }
    observations, definitions, rejected = panel_native.select_native(
        payload, entity, raw, expected_split="dev"
    )
    item = {
        "entity": entity,
        "raw_object": raw,
        "source_cluster": "cik:" + cik,
        "split": "dev",
        "historical_confirmation_issuer": False,
        "local_path": str(path),
        "observations": observations,
        "definitions": definitions,
        "selection_exclusions": rejected,
    }
    return item, payload


class _ReadOnlyOntology:
    """Only ontology/source-parent rows are requested from the old actual DB."""

    def __init__(self, path):
        self.conn = sqlite3.connect(Path(path).as_uri() + "?mode=ro", uri=True)
        self.conn.row_factory = sqlite3.Row

    def fetchall(self, sql, params=()):
        return [dict(row) for row in self.conn.execute(sql, params).fetchall()]

    def fetchone(self, sql, params=()):
        row = self.conn.execute(sql, params).fetchone()
        return None if row is None else dict(row)

    def close(self):
        self.conn.close()


def _build_native(source_root, output, inputs):
    """Thin new-entity wiring around the original numerical/build functions."""
    database = output / "native_fact_qa.sqlite3"
    require(not database.exists(), "calibration.new_native_database")
    archived = _ReadOnlyOntology(source_root / WORK / "qa_build.sqlite3")
    db = RecordDB(str(database))
    try:
        db.init_schema()
        ensure_build_schema(db)
        ensure_kg_schema(db)
        with db.transaction():
            entity_build = start_build(
                db, layer="entity", command="registered-calibration-CIKs", prefix="entity_build"
            )
            insert(
                db,
                "canonical_entities",
                [{**item["entity"], "build_id": entity_build} for item in inputs],
            )
            finish_build(db, entity_build, "success", "Frozen extra CIK metadata, no old entities")
            source = archived.fetchone(
                "SELECT properties_json FROM kg_nodes WHERE source_table='source_registry' "
                "AND source_pk='sec_companyfacts'"
            )
            require(source is not None, "calibration.original_source_registry_parent")
            insert(
                db, "source_registry", [{**json.loads(source["properties_json"]), "is_active": 1}]
            )
            insert(db, "raw_objects", [item["raw_object"] for item in inputs])
            metric_build, definition_build = native_facts.populate_ontology(db, archived, inputs)
            fact_build, document_build, bindings = native_facts.populate_facts(db, inputs)
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
        kg = db.fetchone(
            "SELECT * FROM kg_builds WHERE kg_build_id=?", (reports["kg"]["kg_build_id"],)
        )
        require(
            kg["status"] == "success" and kg["quality_status"] == "passed",
            "calibration.actual_KG_quality_passed",
        )
        summary = p.record(
            "calibration_native_build",
            database_path=str(database),
            kg_build=kg,
            entity_build_id=entity_build,
            metric_build_id=metric_build,
            source_definition_build_id=definition_build,
            fact_build_id=fact_build,
            document_build_id=document_build,
            reports=reports,
            source_company_count=len(inputs),
            native_observation_count=len(bindings),
            model_calls=0,
        )
        write_json(output / "native_bindings.json", bindings)
        write_json(output / "native_fact_build_report.json", summary)
        write_json(
            output / "native_source_inventory.json",
            [
                {k: v for k, v in item.items() if k not in {"observations", "definitions"}}
                for item in inputs
            ],
        )
        return db, bindings, summary
    except BaseException:
        db.close()
        raise
    finally:
        archived.close()


def _compile_candidates(db, kg, candidates, facts, bindings, usage, sources, output, freeze_id):
    remaining = {group: list(candidates[group]) for group in GROUPS}
    selected, exported, rejected = [], [], []
    batch = 0
    while True:
        counts = Counter(row["family"] for row in selected)
        take = []
        for group in GROUPS:
            missing = QUOTAS[group] - counts[group]
            if missing > 0:
                size = missing + 8 if batch == 0 else 8
                take.extend(remaining[group][:size])
                del remaining[group][:size]
        if not take:
            break
        compiled = original.compile_batch(
            db, kg, take, facts, bindings, usage, output / "QA" / f"batch_{batch:03d}", "dev"
        )
        emitted, failed = panel.export_batch(
            db, kg, compiled, take, facts, bindings, sources, output, "dev", freeze_id, prior={}
        )
        rank = {row["task_id"]: i for i, row in enumerate(take)}
        emitted.sort(key=lambda row: rank[row["task_id"]])
        for row in emitted:
            if counts[row["family"]] < QUOTAS[row["family"]]:
                selected.append(row)
                counts[row["family"]] += 1
        exported.extend(emitted)
        rejected.extend(failed)
        batch += 1
        if all(counts[group] == QUOTAS[group] for group in GROUPS):
            break
    chosen = {row["task_id"] for row in selected}
    write_json(output / "compiler_rejections.json", rejected)
    write_json(
        output / "compiled_overflow.json", [r for r in exported if r["task_id"] not in chosen]
    )
    write_json(output / "uncompiled_overflow.json", remaining)
    return selected, rejected


def _tokenizer(root):
    from trusted_synthesis.experiments.qa_reasoning_share_training_preflight.tokenization import (
        load_tokenizer,
    )

    return load_tokenizer(p.read_json(Path(root) / PARENT_FREEZE)["tokenizer_binding"])


def _views(root, output, private, selected, sources, payloads, registration, rule):
    tokenizer = _tokenizer(root)
    documents, result, checks, failures = {}, [], [], []
    public_document = compact.prior.isolation.clone_function(
        compact.prior.public_document,
        {**vars(compact.prior), "PUBLIC_FIELDS": compact.prior.PUBLIC_FIELDS | {"source_metadata"}},
    )
    for row in selected:
        task = row["task_id"]
        try:
            messages = p.read_json(private / row["public_path"])
            require(
                p.sha(p.encode(messages)) == row["public_messages_sha256"], "calibration.public_SHA"
            )
            public = json.loads(messages[0]["content"])
            descriptor = sources[row["source_cluster"]]
            raw_id = descriptor["source_id"]
            if raw_id not in documents:
                documents[raw_id] = p.read_json(private / descriptor["path"])
            expanded, window = compiler.compile_public(public, documents[raw_id], p)
            for source in expanded["sources"]:
                require(
                    compact.prior.runtime._pointer(payloads[raw_id], source["native_pointer"])
                    == source["record"],
                    "calibration.public_original_pointer",
                )
            packed = compact.compact_public(expanded)
            require(
                compact.expand_public(packed) == expanded, "calibration.lossless_view_roundtrip"
            )
            messages = [{"role": "user", "content": p.encode(packed).decode()}]
            view = p.record(
                "given_public_source_view_v2",
                canonical_task_id=task,
                group=row["family"],
                source_cluster=row["source_cluster"],
                original_identity={
                    "task_id": task,
                    "family": row["family"],
                    "surface_version_id": row["surface_version_id"],
                    "public_messages_sha256": row["public_messages_sha256"],
                    "parent_manifest_id": registration["id"],
                },
                public_messages=messages,
                public_messages_sha256=p.sha(p.encode(messages)),
                rule_id=rule["id"],
                source_window=window,
                original_source_document_id=documents[raw_id]["id"],
                exact_lossless_expansion=True,
                split="calibration",
                private_fields_received_by_compiler=False,
            )
            identity = {
                "task_id": task,
                "family": row["family"],
                "surface_version_id": view["id"],
                "public_messages_sha256": view["public_messages_sha256"],
                "parent_manifest_id": rule["id"],
            }
            public_document(messages, identity, compact.SourceViewSources(packed))
            rendered = tokenizer.apply_chat_template(
                [
                    {"role": "system", "content": compact.SYSTEM + "\nRequested guidance: neutral"},
                    *messages,
                ],
                tokenize=False,
                add_generation_prompt=True,
            )
            count = len(
                tokenizer(rendered, add_special_tokens=False, truncation=False)["input_ids"]
            )
            path = output / "views" / (task + ".json")
            write_json(path, view)
            result.append(
                {
                    "task_id": task,
                    "group": row["family"],
                    "source_cluster": row["source_cluster"],
                    "path": str(path),
                    "surface_version_id": view["id"],
                    "public_messages_sha256": view["public_messages_sha256"],
                    **window,
                }
            )
            checks.append(
                {
                    "task_id": task,
                    "initial_prompt_tokens": count,
                    "available_history_growth_tokens": 24576 - 2048 - count,
                    "passed": 24576 - 2048 - count >= 4096,
                }
            )
        except (ValueError, KeyError, TypeError) as error:
            failures.append({"task_id": task, "error": str(error)})
    return result, checks, failures


def build(root, registered_sources, output):
    """Build once; return public manifest, admission, and isolated private index.

    ``root`` is the code worktree. ``output`` is a new absolute data directory.
    A shortage returns ``admission.passed=False``.  Corrupt identities or build
    errors also leave a failure sidecar but are raised to stop the caller.
    """
    root, output = Path(root).resolve(), Path(output)
    require(output.is_absolute() and not output.exists(), "calibration.new_absolute_output")
    source_root = _source_root(root)
    historical = p.read_json(source_root / HISTORICAL_METADATA)
    excluded = {row["source_cluster"] for row in historical["rows"]}
    require(len(excluded) == 100, "calibration.original100_source_inventory")
    rows = _registered_rows(registered_sources, excluded)
    require(
        all(not output.resolve().is_relative_to(Path(row["path"])) for row in rows),
        "calibration.output_not_source_file",
    )
    output.mkdir(parents=True)
    rule = policy()
    write_json(output / "registration.json", registered_sources)
    write_json(output / "rule.json", rule)
    private = output / "private"
    private.mkdir()
    db = None
    try:
        with ThreadPoolExecutor(max_workers=8) as executor:
            loaded = list(executor.map(_read_source, rows))
        inputs = [item for item, _payload in loaded]
        payloads = {item["raw_object"]["raw_object_id"]: value for item, value in loaded}
        db, bindings, native = _build_native(source_root, private, inputs)
        kg = native["kg_build"]
        facts = pipeline._load_facts_by_id(
            db, list(bindings), kg["input_fact_build_id"], kg["input_entity_build_id"]
        )
        present = {
            row["source_pk"]
            for row in db.fetchall(
                "SELECT source_pk FROM kg_nodes WHERE kg_build_id=? "
                "AND node_type='Fact' AND is_active=1",
                (kg["kg_build_id"],),
            )
        }
        facts = {key: value for key, value in facts.items() if key in present}
        usage = {
            key: {k: row[k] for k in ("split", "allowed_uses", "source_cluster")}
            for key, row in bindings.items()
        }
        write_json(private / "all_leaf_usage.json", usage)
        candidates, rejections = panel_rules.enumerate_all(
            facts, bindings, usage, "dev", payloads, []
        )
        write_json(private / "all_source_qualified_candidates.json", candidates)
        write_json(private / "source_rejections.json", rejections)
        sources = original.public_source_index(inputs, facts, bindings, private)
        selected, compiler_rejections = _compile_candidates(
            db, kg, candidates, facts, bindings, usage, sources, private, registered_sources["id"]
        )
        dump_parents(db, private)
        counts = Counter(row["family"] for row in selected)
        shortages = {group: QUOTAS[group] - counts[group] for group in GROUPS}
        catalog = p.record(
            "calibration_task_catalog",
            registration_id=registered_sources["id"],
            rule_id=rule["id"],
            tasks=selected,
            counts=dict(counts),
            shortages=shortages,
            source_cluster_count=len({r["source_cluster"] for r in selected}),
            selected_by_model_outcomes=False,
            prior_private_task_reads=0,
        )
        write_json(private / "catalog.json", catalog)
        public = output / "public"
        compiled, checks, failures = _views(
            root, public, private, selected, sources, payloads, registered_sources, rule
        )
        admitted = (
            not any(shortages.values())
            and len(compiled) == 180
            and len(checks) == 180
            and all(row["passed"] for row in checks)
            and not failures
        )
        manifest = p.record(
            "source_view_manifest_v2",
            protocol_id=registered_sources["id"],
            split="calibration",
            rule_id=rule["id"],
            tasks=compiled,
            task_count=len(compiled),
            planned_tasks=180,
            tasks_per_group=60,
            failures=failures,
            runtime_binding=compact.binding(),
            original_registry_sha256=p.sha(p.encode(selected)),
            source_cluster_count=catalog["source_cluster_count"],
            source_registration_id=registered_sources["id"],
            private_fields_received_by_compiler=False,
        )
        write_json(public / "manifest.json", manifest)
        private_assets = p.record(
            "calibration_private_assets",
            source_manifest_id=manifest["id"],
            catalog_id=catalog["id"],
            native_bindings={
                "path": str(private / "native_bindings.json"),
                "sha256": sha(private / "native_bindings.json"),
            },
            bundles=[
                {
                    "task_id": row["task_id"],
                    "path": str(private / row["path"]),
                    "sha256": sha(private / row["path"]),
                    "id": row["bundle_id"],
                }
                for row in selected
            ],
            private_use="offline scoring only after all registered generation is sealed",
            private_scoring_authorized=False,
        )
        write_json(private / "assets.json", private_assets)
        admission = p.record(
            "calibration_panel_admission",
            passed=admitted,
            status="READY_180_PUBLIC_INPUTS" if admitted else "BLOCKED_PANEL_CONTRACT",
            source_registration_id=registered_sources["id"],
            source_manifest_id=manifest["id"],
            private_assets_id=private_assets["id"],
            shortages=shortages,
            candidate_counts={g: len(candidates[g]) for g in GROUPS},
            source_rejection_count=len(rejections),
            compiler_rejection_count=len(compiler_rejections),
            checks=checks,
            failures=failures,
            model_calls=0,
            new_Probe_materials=0,
            no_old_task_body_or_outcome_read=True,
            failed_public_views_not_replaced=True,
            financial_reference_checks="original QA/period/amount/certificate gates",
            private_runtime_sufficiency_controls_performed=False,
        )
        write_json(output / "admission.json", admission)
        return {"manifest": manifest, "admission": admission, "private_assets": private_assets}
    except BaseException as error:
        write_json(
            output / "failure.json",
            {
                "registration_id": registered_sources["id"],
                "error_type": type(error).__name__,
                "error": str(error),
                "passed": False,
                "model_calls": 0,
            },
        )
        raise
    finally:
        if db is not None:
            db.close()
