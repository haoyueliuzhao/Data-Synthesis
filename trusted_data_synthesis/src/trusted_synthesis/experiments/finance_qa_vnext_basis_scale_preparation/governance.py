"""Bounded historical exposure and source-cluster drafts, never task certification.

Inputs are original FinQA entries. Additional source_split/source_file_sha256/
source_record_index metadata is carried as provenance, not hashed into source
table or context equivalence. No intake download, model, tokenizer or write occurs.
"""

import ast
import hashlib
import json
import math
import re
import subprocess
from collections import Counter, defaultdict
from pathlib import Path

ARCHIVE = "trusted_data_synthesis/benchmarks/finqa/frozen/test.json"
ARCHIVE_SHA256 = "831dbfb2e785dbc227f895ce3f24046433467aec67b09db2bd6ac7692a8a30dc"
NEW_OUTPUT = "trusted_data_synthesis/artifacts/qa_vnext_basis_scale_preparation/"
BIDIRECTIONAL = (
    "trusted_data_synthesis/artifacts/qa_vnext_bidirectional_utility/"
    "three_tasks_24rep_flash_rerun_20260910/preparation/panel_selection.json"
)
DIFFICULTY_REJECTED = (
    "trusted_data_synthesis/artifacts/qa_vnext_finqa_difficulty/"
    "original_12_ef_v1_20260908/preparation/screening_exclusions.json"
)
PQ_PANEL = (
    "trusted_data_synthesis/artifacts/qa_vnext_pq_student/"
    "pq_3seed_20260910/preparation/panel_selection.json"
)
SOURCE_DISPOSITIONS = (
    "trusted_data_synthesis/src/trusted_synthesis/experiments/"
    "qa_reasoning_source_distinct_support/source.py"
)
CENSUS = (
    "trusted_data_synthesis/artifacts/qa_vnext_finqa_difficulty/"
    "original_12_ef_v1_20260908/preparation/census_summary.json"
)
SPLIT_SEED = "basis_scale_company_source_draft_20260911.v1"
SPLIT_WEIGHTS = {"train": 10, "dev": 9, "confirm": 36}
IDENTIFIER_FIELDS = {"id", "qa_id", "task_id", "original_task_id", "source_question_id"}
_EMPTY_CELLS = frozenset({"", "-", "—", "–", "−", "n/a", "na", "not available", "null", "none"})


def _record(kind, **fields):
    value = {"schema_version": "basis_scale_preparation.v1." + kind, **fields}
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return {**value, "id": kind + ":" + hashlib.sha256(raw).hexdigest()}


def _hash(value):
    """Match the historical census's table/context hashing convention exactly."""
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()


def _reference(root, relative):
    path = root / relative
    if path.is_symlink() or not path.resolve().is_relative_to(root.resolve()):
        raise ValueError("governance.reference_outside_root_or_symlink")
    raw = path.read_bytes()
    return {"path": relative, "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def _read(root, relative):
    return json.loads((root / relative).read_bytes())


def _table_identity(table, field):
    """Hash actual nonempty table content; placeholders cannot establish overlap.

    This is a source identity check, not a financial-information or sufficiency
    judgment. Nonblank text-only tables still have content. Malformed and wholly
    blank/placeholder views remain diagnostics, with no hash in the exclusion or
    connected-component keys; original source bytes remain in the intake.
    """
    malformed = not isinstance(table, list) or any(
        not isinstance(row, list)
        or any(
            not isinstance(cell, (str, int, float))
            or isinstance(cell, bool)
            or (isinstance(cell, float) and not math.isfinite(cell))
            for cell in row
        )
        for row in table
    )
    if malformed:
        return None, {
            "field": field,
            "code": "MALFORMED_TABLE_NOT_SOURCE_IDENTITY",
            "used_for_source_equality": False,
        }
    if not any(str(cell).strip().casefold() not in _EMPTY_CELLS for row in table for cell in row):
        return None, {
            "field": field,
            "code": "EMPTY_OR_PLACEHOLDER_TABLE_NOT_SOURCE_IDENTITY",
            "used_for_source_equality": False,
        }
    return _hash(table), None


def _table_hashes(row):
    return tuple(row[key] for key in ("table_sha256", "table_ori_sha256") if row[key] is not None)


def _source(entry):
    identifier, page = entry["id"], entry["filename"]
    if not isinstance(identifier, str) or not isinstance(page, str) or len(page.split("/")) < 3:
        raise ValueError("governance.original_entry_identity")
    company, year = page.split("/")[:2]
    if not company or not year.isdigit():
        raise ValueError("governance.company_report_proxy")
    table = entry.get("table", entry.get("table_ori"))
    pre, post = entry["pre_text"], entry["post_text"]
    if not isinstance(pre, list) or not isinstance(post, list):
        raise ValueError("governance.original_source_shape")
    table_field = "table" if "table" in entry else "table_ori"
    table_hash, table_issue = _table_identity(table, table_field)
    original_hash, original_issue = _table_identity(
        entry.get("table_ori", table), "table_ori" if "table_ori" in entry else table_field
    )
    issues = [table_issue] if table_issue else []
    if original_issue is not None and original_issue not in issues:
        issues.append(original_issue)
    valid_context = all(isinstance(text, str) for text in pre + post)
    valid_table_shape = table_issue is None or table_issue["code"].startswith("EMPTY_")
    context_has_content = table_hash is not None or any(
        isinstance(text, str) and text.strip().casefold() not in _EMPTY_CELLS for text in pre + post
    )
    context_hash = (
        _hash([table, pre + post])
        if valid_context and valid_table_shape and context_has_content
        else None
    )
    if context_hash is None:
        issues.append(
            {
                "field": "context",
                "code": "EMPTY_OR_MALFORMED_CONTEXT_NOT_SOURCE_IDENTITY",
                "used_for_source_equality": False,
            }
        )
    return {
        "question_id": identifier.split("::")[0],
        "entry_id": identifier,
        "page": page,
        "company_proxy": company,
        "report_proxy": company + "/" + year,
        "table_sha256": table_hash,
        "table_ori_sha256": original_hash,
        "context_sha256": context_hash,
        "source_identity_diagnostics": issues,
        "empty_or_malformed_table_never_establishes_source_overlap": True,
        "provenance": {
            key: entry[key]
            for key in ("source_split", "source_file_sha256", "source_record_index")
            if key in entry
        },
    }


def _ids(value, original_ids):
    found = set()
    if isinstance(value, dict):
        for key, item in value.items():
            if key in IDENTIFIER_FIELDS and isinstance(item, str):
                candidate = item.split("::")[0]
                if candidate in original_ids:
                    found.add(candidate)
            if isinstance(item, (dict, list)):
                found.update(_ids(item, original_ids))
    elif isinstance(value, list):
        for item in value:
            found.update(_ids(item, original_ids))
    return found


def _blacklist(entries):
    rows = [_source(entry) for entry in entries]
    return {
        "question_ids": sorted({r["question_id"] for r in rows}),
        "pages": sorted({r["page"] for r in rows}),
        "table_hashes": sorted({value for row in rows for value in _table_hashes(row)}),
        "context_hashes": sorted(
            {r["context_sha256"] for r in rows if r["context_sha256"] is not None}
        ),
        "company_proxies": sorted({r["company_proxy"] for r in rows}),
    }


def known_exposure(root):
    """Reproduce saved registrations/public panels plus bounded source-only reviews.

    This is not a search of all git history, logs, research reads or model pretraining.
    The whole 1,147-row metadata census is reported as exposure, not silently
    converted into 1,147 historically evaluated tasks or a blanket blacklist.
    """
    root = Path(root)
    archive_ref = _reference(root, ARCHIVE)
    if archive_ref["sha256"] != ARCHIVE_SHA256:
        raise ValueError("governance.exact_historical_benchmark_snapshot")
    entries = _read(root, ARCHIVE)
    by_id = {entry["id"]: entry for entry in entries}
    if len(by_id) != len(entries):
        raise ValueError("governance.unique_historical_question_ids")
    listed = subprocess.run(
        ["rg", "--files", "trusted_data_synthesis/artifacts"],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    if listed.returncode not in {0, 1}:
        raise ValueError("governance.historical_path_inventory_failed")
    paths = sorted(
        path
        for path in listed.stdout.splitlines()
        if not path.startswith(NEW_OUTPUT)
        and (
            re.search(r"/preparation/(public|public_tasks|sources|tasks)/[^/]+\.json$", path)
            or path.endswith("/preparation/registrations.json")
            or path.endswith("/preparation/panel_selection.json")
        )
    )
    references = {ARCHIVE: archive_ref}
    registered = defaultdict(set)
    for relative in paths:
        references[relative] = _reference(root, relative)
        for identifier in _ids(_read(root, relative), by_id):
            registered[identifier].add(relative)
    source_ids, source_pages = defaultdict(set), defaultdict(set)
    missing = []
    for relative in (BIDIRECTIONAL, DIFFICULTY_REJECTED, PQ_PANEL, SOURCE_DISPOSITIONS, CENSUS):
        if not (root / relative).is_file():
            missing.append(relative)
            continue
        references[relative] = _reference(root, relative)
        if relative == SOURCE_DISPOSITIONS:
            module = ast.parse((root / relative).read_text())
            for node in module.body:
                if isinstance(node, ast.Assign) and any(
                    isinstance(target, ast.Name) and target.id == "PAGE_DISPOSITIONS"
                    for target in node.targets
                ):
                    for page in ast.literal_eval(node.value):
                        source_pages[page].add(relative)
            continue
        value = _read(root, relative)
        if relative == BIDIRECTIONAL:
            for identifier in value.get("source_screen_rejections", {}):
                if identifier in by_id:
                    source_ids[identifier].add(relative)
        elif relative in {DIFFICULTY_REJECTED, PQ_PANEL}:
            items = (
                value
                if isinstance(value, list)
                else value.get("selection", {}).get("selection_exclusions", [])
            )
            for item in items:
                if item.get("qa_id") in by_id:
                    source_ids[item["qa_id"]].add(relative)
                if item.get("filename"):
                    source_pages[item["filename"]].add(relative)
    for identifier, entry in by_id.items():
        if entry["filename"] in source_pages:
            source_ids[identifier].update(source_pages[entry["filename"]])
    registered_rows = [by_id[key] for key in sorted(registered)]
    reviewed_rows = [by_id[key] for key in sorted(source_ids)]
    union = [by_id[key] for key in sorted(set(registered) | set(source_ids))]
    return _record(
        "known_source_exposure",
        archive_reference=archive_ref,
        archive_rows=len(entries),
        scanned_registered_files=paths,
        scanned_registered_file_count=len(paths),
        registered_question_ids=sorted(registered),
        registered_id_count=len(registered),
        registered_id_references={key: sorted(value) for key, value in sorted(registered.items())},
        source_reviewed_question_ids=sorted(source_ids),
        source_reviewed_id_references={
            key: sorted(value) for key, value in sorted(source_ids.items())
        },
        source_reviewed_pages={key: sorted(value) for key, value in sorted(source_pages.items())},
        exposure_layers={
            "registered": _blacklist(registered_rows),
            "source_reviewed": _blacklist(reviewed_rows),
            "union": _blacklist(union),
        },
        source_references=[references[key] for key in sorted(references)],
        missing_supplemental_inputs=missing,
        whole_snapshot_metadata_previously_inspected=(CENSUS in references),
        metadata_inspection_not_all_tasks_previously_evaluated=True,
        bounded_path_policy=(
            "Historical preparation public documents/registrations/panel lists plus the five "
            "named supplemental source-review inputs; current study outputs excluded."
        ),
        scanning_caveat=(
            "Saved finite records only; not every research read, arbitrary archived request, "
            "all git history, issuer identity, or pretraining exposure. Missing supplemental "
            "paths stay explicit."
        ),
        company_exclusion_is_scenario_not_audit_mandate=True,
        certified_new_tasks=0,
        Provider_calls=0,
        tokenizer_calls=0,
    )


class _Union:
    def __init__(self):
        self.parent = {}

    def find(self, key):
        self.parent.setdefault(key, key)
        if self.parent[key] != key:
            self.parent[key] = self.find(self.parent[key])
        return self.parent[key]

    def join(self, left, right):
        a, b = self.find(left), self.find(right)
        self.parent[max(a, b)] = min(a, b)


def _aliases(aliases=None):
    groups = _Union()
    # Conservative grouping only: no legal-entity identity is inferred from a ticker.
    edges = [("UA", "UAA")]
    for alias, target in (aliases or {}).items():
        canonical = target.get("canonical") if isinstance(target, dict) else target
        if (
            not isinstance(alias, str)
            or not isinstance(canonical, str)
            or not alias
            or not canonical
        ):
            raise ValueError("governance.alias_shape")
        edges.append((alias, canonical))
    for left, right in edges:
        groups.join(left, right)
    return groups, sorted(set(edges))


def _exposure(row, known):
    reasons = []
    for layer in ("registered", "source_reviewed"):
        values = known.get("exposure_layers", {}).get(layer, {})
        checks = {
            "question": row["question_id"] in values.get("question_ids", []),
            "page": row["page"] in values.get("pages", []),
            "table": bool(set(_table_hashes(row)) & set(values.get("table_hashes", []))),
            "context": row["context_sha256"] is not None
            and row["context_sha256"] in values.get("context_hashes", []),
        }
        reasons.extend(f"historical_{layer}_{kind}" for kind, hit in checks.items() if hit)
    return reasons


def _overlap(left, right, field):
    groups = defaultdict(lambda: {"rows": set(), "evaluation_rows": set()})
    for side, entries in (("rows", left), ("evaluation_rows", right)):
        for row in entries:
            values = _table_hashes(row) if field == "table" else (row[field],)
            for value in values:
                if value is None:
                    continue
                groups[value][side].add(row["entry_id"])
    return [
        {"key": key, **{side: sorted(ids) for side, ids in value.items()}}
        for key, value in sorted(groups.items())
        if value["rows"] and value["evaluation_rows"]
    ]


def annotated_governance(rows, evaluation_rows, known, aliases=None):
    """Separate evaluation-only training exclusions from historical freshness.

    evaluation_rows contains the caller's evaluation-only source records, such
    as the unchanged historical test snapshot. Exact source overlap excludes
    training even after a re-download changes split/provenance labels. Historical
    non-evaluation-only exposure excludes fresh evaluation, not training by
    itself. A shared company proxy alone is reported, never a hard exclusion.
    """
    company, edges = _aliases(aliases)
    historical_companies = (
        known.get("exposure_layers", {}).get("union", {}).get("company_proxies", [])
    )
    historical_groups = {company.find(value) for value in historical_companies}
    evaluation_only = _blacklist(evaluation_rows)

    def annotate(entries):
        result = []
        for entry in entries:
            row = _source(entry)
            row["company_proxy_group"] = company.find(row["company_proxy"])
            reasons = _exposure(row, known)
            evaluation_matches = {
                "question": row["question_id"] in evaluation_only["question_ids"],
                "page": row["page"] in evaluation_only["pages"],
                "table": bool(set(_table_hashes(row)) & set(evaluation_only["table_hashes"])),
                "context": row["context_sha256"] is not None
                and row["context_sha256"] in evaluation_only["context_hashes"],
            }
            training_reasons = [
                "evaluation_only_" + kind for kind, hit in evaluation_matches.items() if hit
            ]
            same_company = row["company_proxy_group"] in historical_groups
            row.update(
                historical_exact_exposure_reasons=reasons,
                training_source_excluded=bool(training_reasons),
                training_source_exclusion_reasons=training_reasons,
                fresh_evaluation_source_excluded=bool(reasons),
                fresh_evaluation_source_exclusion_reasons=reasons,
                fresh_source_lead=not reasons,
                fresh_source_status=(
                    "EXCLUDE_KNOWN_SOURCE" if reasons else "LEAD_NOT_TASK_CERTIFIED"
                ),
                historical_company_proxy_exposed=same_company,
                strict_fresh_company_scenario_eligible=not reasons and not same_company,
                strict_fresh_company_scenario_reasons=(
                    reasons + (["historical_company_proxy"] if same_company else [])
                ),
                dual_sufficiency_certified=False,
                task_certified=False,
            )
            result.append(row)
        return result

    left, right = annotate(rows), annotate(evaluation_rows)
    overlap = {
        field: _overlap(left, right, field)
        for field in ("company_proxy_group", "page", "table", "context_sha256")
    }
    exact_collision = any(overlap[field] for field in ("page", "table", "context_sha256"))
    usable_training_leads = sum(not row["training_source_excluded"] for row in left)
    return _record(
        "annotated_source_governance",
        rows=left,
        evaluation_rows=right,
        population_counts={"rows": len(left), "evaluation_rows": len(right)},
        exposure_counts={
            side: dict(Counter(row["fresh_source_status"] for row in values))
            for side, values in (("rows", left), ("evaluation_rows", right))
        },
        eligibility_counts={
            side: {
                "training_source_excluded": sum(row["training_source_excluded"] for row in values),
                "training_source_leads": sum(not row["training_source_excluded"] for row in values),
                "fresh_evaluation_source_excluded": sum(
                    row["fresh_evaluation_source_excluded"] for row in values
                ),
                "fresh_evaluation_source_leads": sum(
                    not row["fresh_evaluation_source_excluded"] for row in values
                ),
            }
            for side, values in (("rows", left), ("evaluation_rows", right))
        },
        strict_fresh_company_scenario_counts={
            side: sum(row["strict_fresh_company_scenario_eligible"] for row in values)
            for side, values in (("rows", left), ("evaluation_rows", right))
        },
        overlap=overlap,
        cross_population_source_collision=exact_collision,
        company_proxy_overlap_observed=bool(overlap["company_proxy_group"]),
        company_proxy_overlap_is_not_a_training_exclusion=True,
        alias_edges=edges,
        alias_evidence_status="CONSERVATIVE_GROUPING_NOT_ENTITY_CERTIFICATION",
        real_company_disjoint_certified=False,
        status=(
            "SOURCE_LEADS_NOT_TASK_CERTIFIED"
            if usable_training_leads
            else "SOURCE_GAP_NO_TRAINING_SOURCE_LEADS"
        ),
        known_exposure_id=known.get("id"),
        known_company_exclusion_is_optional_strict_scenario=True,
        historical_exact_page_table_context_blacklist_enforced=True,
        evaluation_only_exact_source_training_blacklist_enforced=True,
        historical_non_evaluation_only_sources_not_automatically_banned_from_training=True,
        generated_quality_used=False,
        certified_new_tasks=0,
        support_generation_allowed=False,
        training_allowed=False,
        scope=(
            "Source identities and exposure only; row volume and split labels do not certify "
            "object/period/quantity uniqueness, dual sufficiency, task quotas, power or "
            "fresh-confirmation admission."
        ),
    )


def draft_company_split(rows, known=None, aliases=None, *, evaluation_rows=()):
    """One fixed hash draft, joining company proxies and exact shared sources first.

    No seed search, task-output quality, relation score or model result is read.
    Hash proportions reflect 200/180/720 planning, not guaranteed task counts.
    Historical company exclusions remain an explicitly separate strict scenario.
    """
    annotated = annotated_governance(rows, evaluation_rows, known or {}, aliases)
    union, owner = _Union(), {}
    for row in annotated["rows"]:
        group = row["company_proxy_group"]
        union.find(group)
        for kind, value in (
            ("page", row["page"]),
            ("table", row["table_sha256"]),
            ("table", row["table_ori_sha256"]),
            ("context", row["context_sha256"]),
        ):
            if value is None:
                continue
            key = (kind, value)
            if key in owner:
                union.join(group, owner[key])
            else:
                owner[key] = group
    grouped = defaultdict(list)
    for row in annotated["rows"]:
        grouped[union.find(row["company_proxy_group"])].append(row)
    components, assignments = [], []
    for entries in grouped.values():
        proxies = sorted({row["company_proxy_group"] for row in entries})
        identity = _hash(proxies)
        number = int(hashlib.sha256((SPLIT_SEED + ":" + identity).encode()).hexdigest(), 16)
        cumulative = 0
        for candidate_split, weight in SPLIT_WEIGHTS.items():
            cumulative += weight
            if number * sum(SPLIT_WEIGHTS.values()) < cumulative * 2**256:
                split = candidate_split
                break
        components.append(
            {
                "component_id": identity,
                "company_proxy_groups": proxies,
                "raw_company_codes": sorted({row["company_proxy"] for row in entries}),
                "draft_split": split,
                "source_rows": len(entries),
                "historically_exposed_rows": sum(not row["fresh_source_lead"] for row in entries),
                "historical_company_scenario_flag": any(
                    row["historical_company_proxy_exposed"] for row in entries
                ),
            }
        )
        assignments.extend(
            {**row, "component_id": identity, "draft_split": split} for row in entries
        )
    return _record(
        "company_source_split_draft",
        status="DRAFT_NOT_TASK_CERTIFIED",
        seed=SPLIT_SEED,
        seed_search_attempts=0,
        fixed_split_weights=SPLIT_WEIGHTS,
        components=sorted(components, key=lambda row: row["component_id"]),
        rows=sorted(assignments, key=lambda row: (row["entry_id"], row["page"])),
        split_row_counts=dict(Counter(row["draft_split"] for row in assignments)),
        exact_duplicate_and_company_proxy_components_kept_together=True,
        alias_edges=annotated["alias_edges"],
        real_company_disjoint_certified=False,
        known_exposure_id=(known or {}).get("id"),
        source_eligibility_not_overridden_by_hash=True,
        generated_quality_used=False,
        certified_new_tasks=0,
        support_generation_allowed=False,
        training_allowed=False,
        model_calls=0,
        limitation=(
            "A reproducible source-cluster draft only. Entity aliases, source exposures, "
            "task-group supply and actual physical task uniqueness still need explicit "
            "review; no dataset row count is a dual-sufficiency guarantee."
        ),
    )
