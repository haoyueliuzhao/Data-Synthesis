"""Independent UNP-only source/parent audit; old 243 tasks get byte checks only.

Imports independent audit readers/arithmetic only. No issuer adapter, source
selector, QA renderer, task generator or plan executor is used as an oracle.
"""

import argparse
import hashlib
import importlib.util
import json
import re
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

from lxml import html

PARENT = Path(__file__).with_name("audit_qa_vnext_catalog_incremental.py")
SPEC = importlib.util.spec_from_file_location("unp_independent_prior_audit", PARENT)
base = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(base)
require, read, canonical, check_identity = (
    base.require,
    base.read,
    base.canonical,
    base.check_identity,
)
CIK = "cik:0000100885"
RAW_IDS = {
    "2020-12-31": "rawobj_sec_filings_d1a54ca80e05a968c4b97722",
    "2021-12-31": "rawobj_sec_filings_82c67e42a3a4592192959884",
    "2022-12-31": "rawobj_sec_filings_df74ee279bd8e89d812b3ab5",
    "2023-12-31": "rawobj_sec_filings_9c3597bc393d12fc5a301094",
    "2024-12-31": "rawobj_sec_filings_a31296f247110db86bb12f1f",
    "2025-12-31": "rawobj_sec_filings_95565f51e3ac8a7f8e90411d",
}
ROLES = [
    "cash provided by operating activities",
    "cash used in investing activities",
    "dividends paid",
    "free cash flow",
]
DEFINITION = (
    "Free cash flow is defined as cash provided by operating activities "
    "less cash used in investing activities and dividends paid."
)


def contained(root, relative):
    root, relative = Path(root).resolve(), Path(relative)
    require(not relative.is_absolute() and ".." not in relative.parts, "relative contained member")
    path = root / relative
    for part in (path, *path.parents):
        if part == root:
            break
        require(not part.is_symlink(), "no source or parent symlinks")
    require(path.resolve().is_relative_to(root), "resolved member containment")
    return path


def pinned_bytes(root, member):
    data = contained(root, member["path"]).read_bytes()
    require(
        len(data) == member["bytes"] and hashlib.sha256(data).hexdigest() == member["sha256"],
        "independently pinned source bytes",
    )
    return data


def independent_annual_cover(document_tree):
    """Select a date only when both sides are actual SEC annual-cover clauses.

    The source parser uses one complete-region expression. This auditor instead
    starts from all date clauses and independently establishes the preceding
    legal annual-report header and following transition/registrant declarations.
    """
    text = base.normalized_text(document_tree)
    candidates = list(
        re.finditer(
            r"For\s+(?:the\s+)?fiscal\s+year\s+ended\s+December\s+31\s*,?\s+(20\d{2})",
            text,
            re.IGNORECASE,
        )
    )
    agency = list(re.finditer(r"SECURITIES\s+AND\s+EXCHANGE\s+COMMISSION\b", text, re.IGNORECASE))
    legal = (
        r"REPORT\s+PURSUANT\s+TO\s+SECTION\s+13\s+OR\s+15\(d\)\s+OF\s+THE\s+"
        r"SECURITIES\s+EXCHANGE\s+ACT\s+OF\s+1934"
    )
    qualified = []
    for candidate in candidates:
        preceding = [match for match in agency if match.end() <= candidate.start()]
        if not preceding:
            continue
        beginning = preceding[-1]
        header = text[beginning.end() : candidate.start()]
        if not re.fullmatch(
            r"\s+WASHINGTON,\s*D\.C\.\s+\d{5}\s+FORM\s+10[- ]?K\s+\(Mark\s+One\)\s+"
            r"(?:\[\s*[Xx]\s*\]|☒|☑)\s+ANNUAL\s+" + legal + r"\s+",
            header,
            re.IGNORECASE,
        ):
            continue
        ending = re.match(
            r"\s+OR\s+(?:\[\s*\]|☐)\s+TRANSITION\s+"
            + legal
            + r"\s+For\s+the\s+transition\s+period\s+from\s+_+\s+to\s+_+\s+"
            r"Commission\s+File\s+Number\s+[0-9-]+\s+UNION\s+PACIFIC\s+CORP\s*ORATION\s+"
            r"\(Exact\s+name\s+of\s+registrant\s+as\s+specified\s+in\s+its\s+charter\)",
            text[candidate.end() :],
            re.IGNORECASE,
        )
        if ending is None:
            continue
        start, end = beginning.start(), candidate.end() + ending.end()
        qualified.append(
            {
                "rule": "sec_UNP_annual_cover_region_and_native_CFO_v2",
                "cover_quote": candidate.group(0),
                "cover_text_start": candidate.start(),
                "cover_text_end": candidate.end(),
                "period_end": candidate.group(1) + "-12-31",
                "cover_region": {
                    "normalized_text_start": start,
                    "normalized_text_end": end,
                    "quote": text[start:end],
                    "annual_report_selected": True,
                    "transition_report_unselected": True,
                    "registrant_identity": "UNION PACIFIC CORPORATION",
                    "selection_uses_archived_year_known_offset_or_amount": False,
                },
                "native_same_accession_annual_CFO_confirmation_required": True,
                "annual_frequency_alone_used_to_infer_calendar_year": False,
            }
        )
    require(len(qualified) == 1, "one independently identified UNP SEC annual cover")
    return qualified[0]


def verify_cover_evidence(document_tree, claimed):
    """Reopen each claimed raw DOM slice and compute its global position afresh."""
    expected = independent_annual_cover(document_tree)
    region = claimed.get("cover_region") or {}
    without_segments = {
        **claimed,
        "cover_region": {key: value for key, value in region.items() if key != "dom_text_segments"},
    }
    require(
        without_segments == expected, "claimed cover equals independently selected semantic region"
    )
    positions, offset = {}, 0
    for part in document_tree.xpath(".//text()"):
        raw = str(part)
        normalized = " ".join(raw.split())
        if not normalized:
            continue
        node = part.getparent()
        key = (node.getroottree().getpath(node), "tail" if part.is_tail else "text")
        require(key not in positions, "unique original DOM text location")
        positions[key] = (raw, offset)
        offset += len(normalized) + 1
    segments = region.get("dom_text_segments")
    require(isinstance(segments, list) and bool(segments), "original cover DOM evidence required")
    reconstructed, preceding = [], region["normalized_text_start"] - 1
    for segment in segments:
        require(
            set(segment)
            == {
                "element_xpath",
                "slot",
                "raw_character_span",
                "raw_text",
                "normalized_document_span",
            },
            "closed DOM cover evidence fields",
        )
        key = (segment["element_xpath"], segment["slot"])
        require(key in positions, "original cover DOM node/slot")
        raw, node_offset = positions[key]
        left, right = segment["raw_character_span"]
        require(
            type(left) is int and type(right) is int and 0 <= left < right <= len(raw),
            "valid original DOM raw character span",
        )
        require(
            (left == 0 or raw[left - 1].isspace())
            and (right == len(raw) or raw[right].isspace())
            and not raw[left].isspace()
            and not raw[right - 1].isspace(),
            "whole original DOM tokens",
        )
        require(raw[left:right] == segment["raw_text"], "exact original DOM raw slice")
        prefix = " ".join(raw[:left].split())
        fragment = " ".join(raw[left:right].split())
        begin = node_offset + len(prefix) + bool(prefix)
        finish = begin + len(fragment)
        require(
            segment["normalized_document_span"] == [begin, finish] and begin == preceding + 1,
            "independent contiguous original DOM positions",
        )
        preceding = finish
        reconstructed.append(fragment)
    require(
        preceding == region["normalized_text_end"] and " ".join(reconstructed) == region["quote"],
        "complete original SEC cover DOM reconstruction",
    )
    return expected


def unp_headers(grid, document_text, *, document_tree=None):
    """Derive the finite layout from original DOM, not a stored shape certificate."""
    labels = [next((cell["text"] for cell in row if cell["text"]), "") for row in grid]
    starts = [i for i, label in enumerate(labels) if label.casefold() == ROLES[0]]
    ends = [i for i, label in enumerate(labels) if label.casefold() == ROLES[-1]]
    require(len(starts) == len(ends) == 1 and starts[0] < ends[0], "unique complete UNP domain")
    selected = [i for i in range(starts[0], ends[0] + 1) if labels[i]]
    require([labels[i].casefold() for i in selected] == ROLES, "all original UNP definition roles")
    require(
        re.search(re.escape(DEFINITION), document_text, re.IGNORECASE),
        "original complete CFO-CFI-dividend definition",
    )
    require(
        document_tree is not None and base.normalized_text(document_tree) == document_text,
        "actual original DOM document required",
    )
    resolution = independent_annual_cover(document_tree)
    headings = []
    for row in grid[: starts[0]]:
        columns = [
            {**cell, "period_end": cell["text"] + "-12-31"}
            for cell in row
            if re.fullmatch(r"20\d{2}", cell["text"])
        ]
        if 2 <= len(columns) <= 3:
            require(
                len({cell["period_end"] for cell in columns}) == len(columns),
                "unique original year headings",
            )
            require(
                all(
                    cell["text"].casefold() in {"", "millions"}
                    or re.fullmatch(r"20\d{2}", cell["text"])
                    for cell in row
                ),
                "no auxiliary or hidden year heading",
            )
            headings.append(columns)
    require(len(headings) == 1, "one finite original UNP heading row")
    require(
        any(cell["text"].casefold() == "millions" for row in grid[: starts[0]] for cell in row),
        "original explicit Millions heading",
    )
    headers = headings[0]
    require(
        max(cell["period_end"] for cell in headers) == resolution["period_end"],
        "cover matches latest heading",
    )
    return headers, selected, labels, resolution


def verify_anchor(observation, values, original):
    anchor = observation["cfo_anchor"]
    require(
        str(original["cik"]).zfill(10) == "0000100885" and anchor["source_cluster"] == CIK,
        "original native UNP CIK",
    )
    require(
        anchor["metric_id"] == "net_cash_provided_by_used_in_operating_activities"
        and "/units/USD/" in anchor["pointer"],
        "original CFO metric and USD pointer",
    )
    record = base.pointer(original, anchor["pointer"])
    require(record == anchor["record"], "exact native CFO pointer")
    start, end = observation["period_start"], observation["period_end"]
    require(
        record.get("start") == start
        and record["end"] == end
        and start == end[:4] + "-01-01"
        and end == start[:4] + "-12-31",
        "same actual calendar duration, never FY index",
    )
    require(Decimal(str(record["val"])) == values[0] * 1000000, "exact original USD CFO scale")
    found = []
    for occurrence in anchor["all_equal_source_occurrences"]:
        if occurrence["record"].get("accn") != observation["accession"]:
            continue
        raw = base.pointer(original, occurrence["pointer"])
        require(
            raw == occurrence["record"] and "/units/USD/" in occurrence["pointer"],
            "actual same-accession source pointer",
        )
        require(
            raw.get("start") == start
            and raw["end"] == end
            and Decimal(str(raw["val"])) == values[0] * 1000000,
            "same filing CFO amount and interval",
        )
        require(
            raw.get("form") in {"10-K", "10-K/A"}
            and raw.get("filed") == observation["filing_date"],
            "actual annual filing/date anchor",
        )
        found.append(raw)
    require(bool(found), "same accession native CFO anchor required")
    require(values[1] <= 0 and values[2] <= 0, "printed CFI and dividend are signed deductions")
    require(
        values[0] + values[1] + values[2] == values[3], "complete signed original reconciliation"
    )


def public_intervals(question, available, unit):
    """Parse saved public actual periods; explicit YoY gives prior end=start-1day."""
    question_dates = set(re.findall(r"\b\d{4}-\d{2}-\d{2}\b", question))
    selected = sorted(end for end in available if end in question_dates)
    if len(selected) != 2:
        require(
            unit == "percent"
            and re.search(r"\b(?:year[- ]over[- ]year|yoy)\b", question, re.IGNORECASE),
            "one-period question requires explicit public YoY",
        )
        scopes = re.findall(
            r"\b(?:in|for) the period (\d{4}-\d{2}-\d{2}) through (\d{4}-\d{2}-\d{2})\b",
            question,
            re.IGNORECASE,
        )
        require(
            len(scopes) == 1 and question_dates == set(scopes[0]),
            "one unambiguous public current interval",
        )
        start, current = scopes[0]
        previous = (date.fromisoformat(start) - timedelta(days=1)).isoformat()
        selected = [previous, current]
    previous, current = selected
    require(previous in available and current in available, "both public original endpoints exist")
    require(
        (date.fromisoformat(available[current][0]) - timedelta(days=1)).isoformat() == previous,
        "public actual consecutive intervals",
    )
    require(
        available[previous][0] in question_dates or unit == "percent",
        "explicit earlier monetary interval",
    )
    require(available[current][0] in question_dates, "explicit current actual period start")
    require(
        not re.search(
            r"previous\s+minus\s+current|earlier\s+minus\s+later", question, re.IGNORECASE
        ),
        "no reverse public subtraction",
    )
    return previous, current


class UNPAudit(base.IncrementalAudit):
    def verify_frozen_inputs(self):
        frozen = read(self.stage / "stage_freeze.json")
        root_freeze = read(self.stage.parent / "stage_freeze.json")
        metadata = frozen["input_freeze"]
        for value in (frozen, root_freeze, metadata):
            check_identity(value)
        require(
            frozen["stage_freeze_id"] == root_freeze["id"]
            and metadata == root_freeze["training_source_metadata"],
            "new increment exact stage/source-freeze parents",
        )
        rule = frozen["rule"]["source_extension"]
        check_identity(rule)
        require(
            rule["id"] == metadata["policy_id"] and rule["registered_raw_objects"] == RAW_IDS,
            "independent six-source frozen rule",
        )
        require(
            rule["new_task_cap"] == 17
            and rule["rewrite_request_cap"] == 34
            and rule["rewrite_token_cap"] == 330752,
            "fixed incremental caps",
        )
        self.metadata = metadata
        self.source_pins = {member["path"]: member for member in metadata["source_files"]}
        require(
            len(self.source_pins) == len(metadata["source_files"]), "unique frozen source paths"
        )
        for member in metadata["cached_files"]:
            pinned_bytes(self.root, member)
        cache = metadata["cache_parent"]
        cache_directory = contained(self.root, cache["directory"])
        cache_bytes = contained(cache_directory, "manifest.json").read_bytes()
        require(
            hashlib.sha256(cache_bytes).hexdigest() == cache["manifest_sha256"],
            "original admitted-cache manifest SHA",
        )
        cache_manifest = json.loads(cache_bytes)
        check_identity(cache_manifest)
        require(
            cache_manifest["id"]
            == cache["manifest_id"]
            == "manifest:818206eaf7822fdc68ddfb5ad4055301467f307ca2d3c307273f024030b0fcc2",
            "original admitted-cache manifest identity",
        )
        cache_members = {row["path"]: row for row in cache_manifest["members"]}
        old_issuer = json.loads(
            pinned_bytes(cache_directory, cache_members["issuer_source_tables.json"])
        )
        old_sources = {row["raw_object"]["raw_object_id"]: row for row in old_issuer["sources"]}
        sources = metadata["selected_sources"]
        require(len(sources) == 6, "exact six preregistered original documents")
        self.new_sources = {}
        for source in sources:
            raw, doc, entity = source["raw_object"], source["document"], source["entity"]
            require(
                source == old_sources.get(raw["raw_object_id"]),
                "same original archived UNP document/raw SHA/accession metadata",
            )
            require(
                RAW_IDS.get(doc["period_end"]) == raw["raw_object_id"], "frozen original UNP raw ID"
            )
            require(
                doc["raw_object_id"] == raw["raw_object_id"]
                and doc["entity_id"] == entity["entity_id"] == "UNP_US"
                and str(entity["cik"]).zfill(10) == "0000100885",
                "source document/entity/CIK parent",
            )
            relative = raw["storage_uri"].removeprefix("/workspace/Data Synthesis/")
            data = pinned_bytes(self.root, self.source_pins[relative])
            require(
                len(data) == raw["content_size_bytes"]
                and hashlib.sha256(data).hexdigest() == raw["content_sha256"],
                "original raw bytes and metadata",
            )
            require(
                "/cik=0000100885/" in relative and "/form=10-K/" in relative,
                "original CIK/annual-report path",
            )
            self.new_sources[raw["raw_object_id"]] = source
        require(len(self.new_sources) == 6, "six distinct frozen documents")
        self.counts["new_UNP_original_file_byte_checks"] = 6
        self.verify_old_public()

    def verify_old_public(self):
        descriptor = self.metadata["catalog_parent"]
        directory = contained(self.root, descriptor["directory"])
        data = (directory / "manifest.json").read_bytes()
        require(
            hashlib.sha256(data).hexdigest() == descriptor["manifest_sha256"],
            "old catalog manifest SHA",
        )
        manifest = json.loads(data)
        check_identity(manifest)
        require(manifest["id"] == descriptor["manifest_id"], "old catalog manifest ID")
        members = {row["path"]: row for row in manifest["members"]}
        catalog = json.loads(pinned_bytes(directory, members["catalog.json"]))
        check_identity(catalog)
        old_ids = {row["task_id"] for row in catalog["tasks"]}
        require(
            len(catalog["tasks"]) == len(old_ids) == 243
            and old_ids == set(self.metadata["old_task_ids"]),
            "exact old 243 task identities",
        )
        parents = {}
        for parent in catalog["parents"]:
            path = contained(self.root, parent["directory"])
            raw = (path / "manifest.json").read_bytes()
            require(
                hashlib.sha256(raw).hexdigest() == parent["manifest_sha256"], "old task parent SHA"
            )
            value = json.loads(raw)
            check_identity(value)
            require(value["id"] == parent["manifest_id"], "old task parent ID")
            parents[value["id"]] = (path, {row["path"]: row for row in value["members"]})
        for task in catalog["tasks"]:
            path, parent_members = parents[task["parent_manifest_id"]]
            relative = str(Path(task["public_path"]).relative_to(path.relative_to(self.root)))
            raw = pinned_bytes(path, parent_members[relative])
            require(
                hashlib.sha256(raw).hexdigest() == task["public_messages_sha256"],
                "old literal public SHA unchanged",
            )
        self.old_ids = old_ids
        self.counts["old_public_bytes_checked_without_semantic_reaudit"] = 243

    def original_file(self, raw, pin=None):
        relative = raw["storage_uri"].removeprefix("/workspace/Data Synthesis/")
        require(relative in self.source_pins, "new audited source was frozen")
        data = pinned_bytes(self.root, self.source_pins[relative])
        require(
            len(data) == raw["content_size_bytes"]
            and hashlib.sha256(data).hexdigest() == raw["content_sha256"],
            "actual source raw SHA",
        )
        return data

    def verify_sources(self):
        issuer = read(self.stage / "issuer_source_tables.json")
        tables = [row for row in issuer["tables"] if row["source_cluster"] == CIK]
        observations = [row for row in issuer["observations"] if row["source_cluster"] == CIK]
        self.source_periods = {}
        for table in tables:
            check_identity(table)
            raw_id, identifier = table["raw_object_id"], table["table_id"]
            require(
                raw_id in self.new_sources and identifier not in self.issuer,
                "new unique source table only",
            )
            raw = self.new_sources[raw_id]["raw_object"]
            if raw_id not in self.dom:
                self.dom[raw_id] = html.fromstring(self.original_file(raw))
            require(
                table["raw_sha256"] == raw["content_sha256"]
                and "/accession=" + table["accession"] + "/" in raw["storage_uri"],
                "table original SHA and accession",
            )
            dom = self.dom[raw_id]
            nodes = dom.xpath(table["table_xpath"])
            require(
                len(nodes) == 1 and dom.xpath("//table")[table["table_index"]] is nodes[0],
                "unique original DOM table location",
            )
            grid, text = base.original_grid(nodes[0]), base.normalized_text(dom)
            structure = table["structure"]
            headers, selected, labels, resolution = unp_headers(grid, text, document_tree=dom)
            require(
                grid == structure["rows"]
                and headers == structure["headers"]
                and selected == structure["selected_rows"],
                "every original physical cell/header/row",
            )
            require(
                labels == structure["original_labels"] == structure["labels"],
                "exact original role labels",
            )
            require(
                verify_cover_evidence(dom, structure["header_period_resolution"]) == resolution,
                "independent original cover resolution",
            )
            quote = text[structure["definition_text_start"] : structure["definition_text_end"]]
            require(
                quote == structure["definition_quote"]
                and quote.casefold() == DEFINITION.casefold(),
                "full original definition quote and offsets",
            )
            require(
                text[structure["table_text_start"] : structure["table_text_end"]]
                == structure["table_text"]
                == base.normalized_text(nodes[0]),
                "original table text offsets",
            )
            require(structure["nearby_source_text"] in text, "original nearby source context")
            shape = {
                "source_cluster": CIK,
                "target": "issuer_defined_free_cash_flow",
                "definition_quote": quote,
                "component_labels": [labels[i] for i in selected[:-1]],
                "signed_adjustments_as_printed": True,
            }
            require(
                shape == table["definition_shape"]
                and table["source_definition_identity"]
                == "issuer_definition_"
                + hashlib.sha256(
                    json.dumps(shape, sort_keys=True, ensure_ascii=False).encode()
                ).hexdigest()[:24],
                "complete independent definition identity",
            )
            self.issuer[identifier], self.grids[identifier] = table, grid
            self.header_sets[identifier], self.selected_rows[identifier] = headers, selected
        for observation in observations:
            identifier, end = observation["table_id"], observation["period_end"]
            require(identifier in self.issuer, "admitted new period original table")
            table = self.issuer[identifier]
            require(
                observation["definition_shape"] == table["definition_shape"]
                and observation["accession"] == table["accession"],
                "observation definition and filing",
            )
            require(
                [row["row_index"] for row in observation["rows"]] == self.selected_rows[identifier],
                "all original reconciliation roles",
            )
            values = []
            for row in observation["rows"]:
                amount, reference = self.table_amount(identifier, row["row_index"], end)
                require(
                    amount == Decimal(row["value"]) and reference == row["cell_reference"],
                    "independent full logical block",
                )
                values.append(amount)
            anchor = observation["cfo_anchor"]
            raw_id = anchor["raw_object_id"]
            if raw_id not in self.native:
                self.native[raw_id] = json.loads(self.original_file(self.raw[raw_id]))
            verify_anchor(observation, values, self.native[raw_id])
            require(
                (identifier, end) not in self.source_periods, "unique newly admitted table-period"
            )
            self.source_periods[identifier, end] = (
                observation["period_start"],
                values[-1],
                table["source_definition_identity"],
            )
        catalog = read(self.stage / "catalog.json")
        needed = set()
        for task in catalog["tasks"]:
            needed.update(read(contained(self.stage, task["path"]))["parents"]["all_leaf_fact_ids"])
        atomic = self.index("atomic_facts", "fact_id")
        for identifier in needed:
            fact, binding = self.facts[identifier], self.bindings[identifier]
            require(
                identifier in atomic and fact["graph_ready"] == 1 and not fact["is_forecast"],
                "actual qualified atomic/standardized leaf",
            )
            require(
                binding["source_cluster"] == CIK
                and fact["entity_id"] == binding["entity_id"] == "UNP_US",
                "only actual UNP new task leaves",
            )
            for key in ("raw_object_id", "entity_id", "source_definition_id"):
                require(fact[key] == binding[key], "actual binding parent " + key)
            require(
                binding["document_id"] in self.documents
                and binding["source_definition_id"] in self.definitions,
                "actual document/definition parents",
            )
            require(
                fact["period_start"] == binding["record"].get("start")
                and fact["period_end"] == binding["record"]["end"],
                "actual native duration",
            )
            require(
                binding["raw_sha256"] == self.raw[binding["raw_object_id"]]["content_sha256"],
                "actual binding raw SHA",
            )
            if binding.get("source_kind") == "issuer_report_table":
                table = self.issuer[binding["table_id"]]
                require(
                    binding["table_record"] == table
                    and (binding["table_id"], fact["period_end"]) in self.source_periods,
                    "admitted original issuer table-period",
                )
                rows = {row["row"] for row in binding["record"]["cell_reference"]["cells"]}
                require(len(rows) == 1, "one original amount row")
                row_index = next(iter(rows))
                require(
                    row_index in self.selected_rows[binding["table_id"]], "complete definition row"
                )
                amount, reference = self.table_amount(
                    binding["table_id"], row_index, fact["period_end"]
                )
                require(
                    reference == binding["record"]["cell_reference"]
                    and amount == Decimal(binding["record"]["val"]),
                    "actual independently parsed issuer leaf",
                )
                require(
                    binding["native_definition"]["description"]
                    == table["structure"]["definition_quote"],
                    "original native issuer definition",
                )
            else:
                raw_id = binding["raw_object_id"]
                if raw_id not in self.native:
                    self.native[raw_id] = json.loads(self.original_file(self.raw[raw_id]))
                original = self.native[raw_id]
                require(
                    "/units/USD/" in binding["pointer"]
                    and base.pointer(original, binding["pointer"]) == binding["record"],
                    "actual original native USD pointer",
                )
                concept = original["facts"]["us-gaap"][binding["tag"]]
                require(
                    {key: concept[key] for key in ("label", "description")}
                    == binding["native_definition"],
                    "original CFO definition metadata",
                )
                amount = Decimal(str(binding["record"]["val"])) / 1000000
            require(
                amount == Decimal(str(fact["normalized_value"]))
                and fact["normalized_unit"] == "million USD"
                and fact["normalized_currency"] == "USD",
                "actual exact standardized scale",
            )
            self.values[identifier] = amount
        self.counts.update(
            new_UNP_tables=len(tables),
            new_UNP_periods=len(observations),
            new_task_original_leaves=len(needed),
        )

    def public_target_details(self, public):
        require(
            "company-defined free cash flow" in public["question"],
            "public company-defined financial target",
        )
        available = {}
        for source in public["sources"]:
            require(
                source.get("source_kind") == "original_issuer_reconciliation",
                "public original issuer tables only",
            )
            for (identifier, end), value in self.source_periods.items():
                if identifier == source["source_id"]:
                    require(
                        end not in available or available[end] == value,
                        "unique public original annual endpoint",
                    )
                    available[end] = value
        contract = public["quantity_contract"]
        require(
            contract["decimal_places"] == 2 and contract["rounding"] == "half away from zero",
            "fixed public rounding",
        )
        previous, current = public_intervals(public["question"], available, contract["unit"])
        require(
            available[previous][2] == available[current][2],
            "same full issuer definition across actual periods",
        )
        left, right = available[previous][1], available[current][1]
        if contract["unit"] == "percent":
            require(
                left > 0 and re.search(r"percent|percentage|%", public["question"], re.IGNORECASE),
                "positive previous public percent base",
            )
            answer = 100 * (right - left) / left
        else:
            require(
                contract["unit"] == "million USD"
                and re.search(
                    r"USD millions|millions of (?:US|U\.S\.) dollars|million USD",
                    public["question"],
                    re.IGNORECASE,
                ),
                "public monetary unit",
            )
            answer = right - left
        return (
            answer,
            [available[previous][0], previous],
            [available[current][0], current],
            available[current][2],
        )

    def public_target(self, public):
        return self.public_target_details(public)[0]

    def verify_tasks(self):
        catalog = read(self.stage / "catalog.json")
        require(
            len(catalog["tasks"]) <= 17
            and not ({row["task_id"] for row in catalog["tasks"]} & self.old_ids),
            "only up to 17 genuinely new IDs",
        )
        results = super().verify_tasks()
        for row in catalog["tasks"]:
            bundle = read(contained(self.stage, row["path"]))
            require(
                bundle["family"] == "company_defined_metric" and bundle["source_cluster"] == CIK,
                "new UNP company group only",
            )
            _, previous, current, definition = self.public_target_details(bundle["public"])
            target = bundle["private"]["canonical_target"]
            require(
                target["previous_period"] == previous and target["current_period"] == current,
                "canonical dates equal independently parsed public target",
            )
            require(
                target["metric_id"] == "issuer_defined_free_cash_flow"
                and definition in target["definition"]["tag"],
                "canonical same original definition identity",
            )
        ledger = read(self.stage / "rewrite_budget_ledger.json")
        require(
            ledger["policy"]["request_cap"] == 34
            and ledger["policy"]["token_cap"] == 330752
            and ledger["policy"]["per_task_cap"] == 2,
            "registered rewrite suballocation",
        )
        rows = ledger["reservations"]
        require(
            len(rows) <= 34
            and ledger["conservative_charged_tokens"]
            == sum(row["charged_tokens"] for row in rows)
            <= 330752,
            "bounded actual rewrite debit",
        )
        require(
            ledger["previous_registered_debit"]
            == sum(row["tokens"] for row in ledger["cumulative_policy"]["prior_debits"])
            >= 221538,
            "same study prior debit not reset",
        )
        registered = read(self.stage / "canonical_task_registry.json")
        check_identity(registered)
        ids = {row["task_id"] for row in registered["tasks"]}
        require(
            len(registered["tasks"]) == len(ids) <= 17 and not ids & self.old_ids,
            "exact frozen new target registry",
        )
        require(
            all(row["task_id"] in ids and row["attempt"] in {1, 2} for row in rows),
            "no old/unregistered rewrite or third attempt",
        )
        require(
            len({(row["task_id"], row["attempt"]) for row in rows}) == len(rows),
            "unique actual request attempts",
        )
        require(
            not ledger.get("Teacher_request_reservations", 0),
            "this increment contains rewrite not Teacher sessions",
        )
        return results


def verify(root, directory):
    audit = UNPAudit(Path(root), Path(directory))
    manifest = audit.verify_manifest()
    audit.verify_frozen_inputs()
    audit.verify_sources()
    tasks = audit.verify_tasks()
    return {
        "schema_version": "independent_UNP_increment_audit.v1",
        "status": "passed",
        "input_manifest_id": manifest,
        "counts": dict(audit.counts),
        "tasks": tasks,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "auditor_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "independent_parent_auditor_sha256": hashlib.sha256(PARENT.read_bytes()).hexdigest(),
        "old_243_financial_semantics_reaudited": False,
        "new_HTTP_or_model_calls": 0,
        "zero_new_tasks_is_supported": True,
        "production_artifacts_changed": False,
        "scope": (
            "new admitted UNP source arithmetic, actual parents, public periods "
            "and two witnesses; bounded NL grammar"
        ),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--directory", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = verify(args.root, args.directory)
    if args.output:
        output = args.output.resolve()
        require(
            not output.is_relative_to((args.root / args.directory).resolve().parent),
            "audit report outside entire sealed stage root",
        )
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open("x", encoding="utf-8") as stream:
            json.dump(report, stream, ensure_ascii=False, indent=2)
    print(
        json.dumps(
            {key: value for key, value in report.items() if key != "tasks"}, ensure_ascii=False
        )
    )


if __name__ == "__main__":
    main()
