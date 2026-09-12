"""Independent source/provenance audit of only a sealed catalog increment.

No task generator, issuer adapter, or plan executor is imported. The older
read-only auditor supplies parent indexing, manifest checks, JSON pointers and
a separate arithmetic interpreter. Physical amount geometry is reconstructed
from original HTML here; claimed certificates are compared to that reconstruction.
"""

import argparse
import hashlib
import importlib.util
import json
import re
from collections import defaultdict
from datetime import date, datetime, timezone
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

from lxml import html

_PARENT = Path(__file__).with_name("audit_qa_vnext_task_build.py")
_SPEC = importlib.util.spec_from_file_location("catalog_incremental_parent_audit", _PARENT)
_BASE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_BASE)
require, read, canonical = _BASE.require, _BASE.read, _BASE.canonical
check_identity, pointer, normalized_text = (
    _BASE.check_identity,
    _BASE.pointer,
    _BASE.normalized_text,
)
STAGE = (
    "trusted_data_synthesis/artifacts/qa_vnext_catalog_bridge/catalog_bridge_20260912/incremental"
)
CELL_KEYS = ("row", "cell", "start", "stop", "text", "raw_text", "cell_xpath", "has_superscript")
MONTH = "January|February|March|April|May|June|July|August|September|October|November|December"
TOTAL = re.compile(r"^(?:non-gaap\s+)?free cash flow(?:\s*\(non-gaap\))?\s*(?:\*|\(\d+\))?$", re.I)
CFO = re.compile(
    r"^(?:gaap\s+)?(?:net\s+cash\s+(?:provided\s+by|from)\s+operating\s+activities"
    r"|cash\s+flows?\s+from\s+(?:operations|operating\s+activities))"
    r"(?:\s*\(gaap\))?\s*[*]?$",
    re.I,
)


def printed_amount(value):
    """Independent strict whole-amount scanner, never a sign-stripping fallback."""
    require(not re.search(r"\d\s+\d", value), "separate digit bodies")
    token = "".join(value.split()).replace("−", "-")
    if token.startswith("$"):
        token = token[1:]
        outer_currency = True
    else:
        outer_currency = False
    negative = token.startswith("(")
    if negative:
        require(token.endswith(")"), "unclosed printed negative")
        token = token[1:-1]
        if token.startswith("$"):
            require(not outer_currency, "duplicate printed currency")
            token = token[1:]
    elif token.startswith("-"):
        negative, token = True, token[1:]
    require(
        bool(re.fullmatch(r"(?:\d+|\d{1,3}(?:,\d{3})+)(?:\.\d+)?", token)),
        "unsupported printed amount",
    )
    result = Decimal(token.replace(",", ""))
    return -result if negative else result


def verify_quantity_identity(target, contract):
    require(target["unit"] == contract["unit"], "canonical target unit")
    require(
        target["quantity"]
        == ("relative_change" if contract["unit"] == "percent" else "difference"),
        "canonical target quantity",
    )


def original_grid(table):
    result = []
    for row_number, row in enumerate(table.xpath("./tr|./thead/tr|./tbody/tr|./tfoot/tr")):
        output, position = [], 0
        for number, cell in enumerate(row.xpath("./th|./td")):
            width = int(cell.get("colspan", "1"))
            require(int(cell.get("rowspan", "1")) == 1 and 0 < width < 100, "finite DOM span")
            output.append(
                {
                    "row": row_number,
                    "cell": number,
                    "start": position,
                    "stop": position + width,
                    "text": normalized_text(cell),
                    "raw_text": "".join(cell.itertext()),
                    "cell_xpath": cell.getroottree().getpath(cell),
                    "has_superscript": bool(cell.xpath(".//sup")),
                }
            )
            position += width
        result.append(output)
    return result


def annual_headers(grid):
    """Infer the annual row from original labels/dates, not the stored certificate."""
    labels = [next((cell["text"] for cell in row if cell["text"]), "") for row in grid]
    totals = [index for index, label in enumerate(labels) if TOTAL.fullmatch(label)]
    require(len(totals) == 1, "one original issuer total")
    starts = [index for index, label in enumerate(labels[: totals[0]]) if CFO.fullmatch(label)]
    require(len(starts) == 1, "one original operating cash row")
    before = starts[0]
    prefix = " ".join(cell["text"] for row in grid[:before] for cell in row)
    require(re.search(r"\byears?\s+ended\b", prefix, re.I), "original annual table scope")
    month_days = set(re.findall(rf"\b({MONTH})\s+(\d{{1,2}})(?!\d)", prefix, re.I))
    candidates = []
    for row in grid[:before]:
        anchors = []
        for cell in row:
            full = re.fullmatch(rf"({MONTH})\s+(\d{{1,2}}),?\s+(20\d{{2}})", cell["text"], re.I)
            if full:
                month, day, year = full.groups()
            elif re.fullmatch(r"20\d{2}", cell["text"]) and len(month_days) == 1:
                month, day = next(iter(month_days))
                year = cell["text"]
            else:
                continue
            end = datetime.strptime(f"{month} {day} {year}", "%B %d %Y").date().isoformat()
            anchors.append({**cell, "period_end": end})
        if 2 <= len(anchors) <= 5 and len({x["period_end"] for x in anchors}) == len(anchors):
            candidates.append(anchors)
    require(len(candidates) == 1, "unique original annual row")
    headers = candidates[0]
    require(
        all(
            left["stop"] <= right["start"]
            for left, right in zip(headers, headers[1:], strict=False)
        ),
        "nonoverlapping original annual headers",
    )
    selected = [i for i in range(before, totals[0] + 1) if labels[i]]
    return headers, selected


def logical_amount(row, header, headers, header_row):
    """Build an independent body-to-symbol ownership graph from original coordinates."""

    def inside(outer, cell):
        return outer["start"] <= cell["start"] < cell["stop"] <= outer["stop"]

    def overlap(a, b):
        return max(a["start"], b["start"]) < min(a["stop"], b["stop"])

    physical = [cell for cell in row if overlap(header, cell)]
    require(all(inside(header, cell) for cell in physical), "body/header boundary ambiguity")
    bodies = [i for i, cell in enumerate(row) if re.search(r"\d", cell["text"])]
    owned = [i for i in bodies if inside(header, row[i])]
    require(len(owned) == 1, "one original numeric body per year")
    selected = owned[0]
    body = row[selected]
    require(not body["has_superscript"], "numeric superscript ambiguity")
    require([h for h in headers if inside(h, body)] == [header], "unique original body year")
    roles = {}
    for i, cell in enumerate(row):
        token = "".join(cell["text"].split())
        if token and re.fullmatch(r"[$()]+", token) and not cell["has_superscript"]:
            roles[i] = ({"prefix"} if "(" in token or "$" in token else set()) | (
                {"suffix"} if ")" in token else set()
            )
    claims = defaultdict(set)
    for body_index in bodies:
        for direction, role in ((-1, "prefix"), (1, "suffix")):
            for distance in range(1, 4):
                index = body_index + distance * direction
                if index not in roles:
                    break
                if role in roles[index]:
                    claims[index].add(body_index)
    attachments, bindings = [], []
    for index in sorted(claims):
        owners = claims[index]
        if selected not in owners:
            continue
        require(owners == {selected}, "shared indivisible symbol")
        cell = row[index]
        require(
            not any(h != header and overlap(h, cell) for h in headers),
            "symbol overlaps another annual header",
        )
        outside = not inside(header, cell)
        if outside:
            cover = [h for h in header_row if overlap(h, cell)]
            require(
                cover
                and cover[0]["start"] <= cell["start"]
                and cover[-1]["stop"] >= cell["stop"]
                and all(not h["text"] for h in cover),
                "external symbol requires original blank header slot",
            )
        attachments.append(cell)
        bindings.append(
            {
                "cell": cell,
                "roles": sorted(roles[index]),
                "candidate_body_cells": [body],
                "owner_period_end": header["period_end"],
                "outside_annual_header": outside,
            }
        )
    included = sorted(
        physical + [cell for cell in attachments if cell not in physical], key=lambda c: c["start"]
    )
    require(
        all(not c["text"] or c == body or c in attachments for c in included),
        "unassigned original annotation or symbol",
    )
    rendered = " ".join(c["text"] for c in included if c["text"])
    value = printed_amount(rendered)
    reference = {
        "printed_text": rendered,
        "cells": included,
        "geometry_certificate": {
            "rule": "unique_annual_body_directional_adjacent_symbols_v1",
            "body": body,
            "annual_header": header,
            "all_annual_headers": headers,
            "original_header_row": header_row,
            "original_amount_row": row,
            "symbol_bindings": bindings,
            "selection_uses_amount_value_or_reconciliation": False,
        },
    }
    return value, reference


class IncrementalAudit(_BASE.Audit):
    def __init__(self, root, directory):
        super().__init__(root, directory)
        self.header_sets = {}
        self.selected_rows = {}

    def table_amount(self, table_id, row_index, period_end):
        grid, headers = self.grids[table_id], self.header_sets[table_id]
        matches = [h for h in headers if h["period_end"] == period_end]
        require(len(matches) == 1, "one original selected year")
        h = matches[0]
        return logical_amount(grid[row_index], h, headers, grid[h["row"]])

    def original_file(self, raw, pin=None):
        prefix = "/workspace/Data Synthesis/"
        added_prefix = "trusted_data_synthesis/artifacts/qa_vnext_catalog_bridge/"
        require(
            raw["storage_uri"].startswith((prefix, added_prefix)), "recognized original raw path"
        )
        relative = raw["storage_uri"].removeprefix(prefix)
        path = (self.root / relative).resolve()
        require(path.is_relative_to(self.root), "original source inside project")
        data = path.read_bytes()
        require(len(data) == raw["content_size_bytes"], "original byte length")
        require(hashlib.sha256(data).hexdigest() == raw["content_sha256"], "original SHA")
        if pin is not None:
            require(pin["path"] == relative, "unmaterialized original frozen path")
            require(
                pin["bytes"] == len(data) and pin["sha256"] == hashlib.sha256(data).hexdigest(),
                "unmaterialized original independent frozen bytes",
            )
        return data

    def unmaterialized_sources(self, issuer):
        """Read source-only structural tables without inventing actual database parents."""
        extra = {table["raw_object_id"] for table in issuer["tables"]} - self.raw.keys()
        originals = {}
        if extra:
            incremental_freeze = read(self.stage / "stage_freeze.json")
            parent_freeze = read(self.stage.parent / "stage_freeze.json")
            input_freeze = incremental_freeze["input_freeze"]
            for value in (incremental_freeze, parent_freeze, input_freeze):
                check_identity(value)
            require(
                incremental_freeze["stage_freeze_id"]
                == parent_freeze["id"]
                == input_freeze["stage_freeze_id"],
                "unmaterialized source freeze parent join",
            )
            pins = {}
            for member in [*parent_freeze["source_files"], *input_freeze["members"]]:
                old = pins.setdefault(member["path"], member)
                require(
                    all(old.get(key) == member.get(key) for key in ("path", "bytes", "sha256")),
                    "consistent original input pins",
                )
            inventory = {
                s["raw_object"]["raw_object_id"]: s["raw_object"] for s in issuer["sources"]
            }
            for identifier in sorted(extra):
                require(identifier in inventory, "unmaterialized actual source inventory")
                raw = inventory[identifier]
                relative = raw["storage_uri"].removeprefix("/workspace/Data Synthesis/")
                require(relative in pins, "unmaterialized source independently frozen")
                require(raw["object_type"] == "html", "unmaterialized structural HTML only")
                self.dom[identifier] = html.fromstring(self.original_file(raw, pins[relative]))
                originals[identifier] = raw
        self.counts["unmaterialized_table_original_files_separately_checked"] = len(extra)
        # Keep self.raw and the actual exported raw_objects table unchanged.
        return {**self.raw, **originals}

    def verify_sources(self):
        for identifier, row in self.raw.items():
            data = self.original_file(row)
            if row["object_type"] == "json":
                self.native[identifier] = json.loads(data)
            else:
                self.dom[identifier] = html.fromstring(data)
            self.counts["original_raw_files"] += 1
        issuer = read(self.stage / "issuer_source_tables.json")
        originals = self.unmaterialized_sources(issuer)
        for table in issuer["tables"]:
            check_identity(table)
            identifier = table["table_id"]
            require(identifier not in self.issuer, "unique source table")
            require(
                table["raw_sha256"] == originals[table["raw_object_id"]]["content_sha256"],
                "table raw SHA",
            )
            uri = originals[table["raw_object_id"]]["storage_uri"]
            require(
                "cik=" + table["source_cluster"].removeprefix("cik:") + "/" in uri
                and "/accession=" + table["accession"] + "/" in uri,
                "original table CIK and accession path",
            )
            dom = self.dom[table["raw_object_id"]]
            nodes = dom.xpath(table["table_xpath"])
            require(len(nodes) == 1, "one original HTML table")
            require(dom.xpath("//table")[table["table_index"]] is nodes[0], "original table index")
            grid = original_grid(nodes[0])
            require(grid == table["structure"]["rows"], "all original cells and coordinates")
            headers, selected = annual_headers(grid)
            require(headers == table["structure"]["headers"], "independent annual header geometry")
            require(selected == table["structure"]["selected_rows"], "complete original row domain")
            text = normalized_text(dom)
            structure = table["structure"]
            require(
                text[structure["definition_text_start"] : structure["definition_text_end"]]
                == structure["definition_quote"],
                "original definition offsets",
            )
            require(
                text[structure["table_text_start"] : structure["table_text_end"]]
                == normalized_text(nodes[0])
                == structure["table_text"],
                "original table text offsets",
            )
            require(structure["nearby_source_text"] in text, "original surrounding text")
            unit_region = text[
                max(0, structure["table_text_start"] - 2000) : structure["table_text_end"]
            ]
            require(
                "in millions" in unit_region.lower()
                or re.search(
                    r"All dollar amounts in the tables are stated in millions of U\.S\. dollars\.",
                    text,
                    re.I,
                ),
                "independent original million scale",
            )
            for note in structure.get("label_annotations", []):
                require(
                    note["note_text_start"] >= structure["table_text_end"]
                    and text[note["note_text_start"] : note["note_text_end"]] == note["note_quote"],
                    "actual source footnote",
                )
            labels = [next((cell["text"] for cell in row if cell["text"]), "") for row in grid]
            require(labels == structure["original_labels"], "original row labels")
            for note in structure.get("label_annotations", []):
                require(labels[note["row"]] == note["original"], "annotated label parent")
                require(note["original"].endswith(note["marker"]), "annotation suffix")
                require(
                    note["normalized"] == note["original"][: -len(note["marker"])].rstrip(),
                    "annotation-only normalization",
                )
                labels[note["row"]] = note["normalized"]
            require(labels == structure["labels"], "only sourced label normalization")
            self.issuer[identifier], self.grids[identifier] = table, grid
            self.header_sets[identifier], self.selected_rows[identifier] = headers, selected
            self.counts["original_issuer_tables"] += 1
        atomic = self.index("atomic_facts", "fact_id")
        for identifier, binding in self.bindings.items():
            fact = self.facts[identifier]
            require(identifier in atomic, "actual atomic fact parent")
            require(fact["graph_ready"] == 1 and not fact["is_forecast"], "qualified source fact")
            for name in ("raw_object_id", "entity_id", "source_definition_id"):
                require(fact[name] == binding[name], "source parent " + name)
            require(binding["document_id"] in self.documents, "source document parent")
            require(binding["source_definition_id"] in self.definitions, "source definition parent")
            require(fact["period_start"] == binding["record"].get("start"), "original period start")
            require(fact["period_end"] == binding["record"]["end"], "original period end")
            require(
                binding["raw_sha256"] == self.raw[binding["raw_object_id"]]["content_sha256"],
                "binding original SHA",
            )
            require(
                fact["normalized_unit"] == "million USD" and fact["normalized_currency"] == "USD",
                "actual normalized unit and currency",
            )
            if binding.get("source_kind") == "issuer_report_table":
                table = self.issuer[binding["table_id"]]
                require(binding["table_record"] == table, "binding exact issuer table parent")
                reference = binding["record"]["cell_reference"]
                rows = {c["row"] for c in reference["cells"]}
                require(len(rows) == 1, "one amount row")
                row_index = next(iter(rows))
                require(
                    row_index in self.selected_rows[binding["table_id"]], "complete row selection"
                )
                value, reconstructed = self.table_amount(
                    binding["table_id"], row_index, fact["period_end"]
                )
                require(reference == reconstructed, "independent logical block certificate")
                require(value == Decimal(binding["record"]["val"]), "original signed table value")
                require(
                    binding["native_definition"]["description"]
                    == table["structure"]["definition_quote"],
                    "binding original definition",
                )
                self.counts["independently_checked_logical_blocks"] += 1
            else:
                original = self.native[binding["raw_object_id"]]
                require("/units/USD/" in binding["pointer"], "native original USD unit path")
                require(
                    pointer(original, binding["pointer"]) == binding["record"],
                    "original JSON pointer",
                )
                concept = original["facts"]["us-gaap"][binding["tag"]]
                require(
                    {k: concept[k] for k in ("label", "description")}
                    == binding["native_definition"],
                    "original native definition",
                )
                require(str(original["cik"]).zfill(10) == binding["source_cluster"][4:], "JSON CIK")
                for occurrence in binding["all_equal_source_occurrences"]:
                    require(
                        pointer(original, occurrence["pointer"]) == occurrence["record"],
                        "original alternate JSON occurrence",
                    )
                    self.counts["original_disclosure_occurrences"] += 1
                value = Decimal(str(binding["record"]["val"])) / 1000000
                self.counts["native_JSON_facts"] += 1
            require(value == Decimal(str(fact["normalized_value"])), "independent normalization")
            self.values[identifier] = value
        require(
            set(self.values) == set(self.facts), "every standardized fact independently grounded"
        )
        checked_periods = set()
        for observation in issuer["observations"]:
            table_id, end = observation["table_id"], observation["period_end"]
            require((table_id, end) not in checked_periods, "unique chosen source period")
            checked_periods.add((table_id, end))
            require(
                observation["definition_shape"] == self.issuer[table_id]["definition_shape"],
                "observation source definition shape",
            )
            expected_rows = self.selected_rows[table_id]
            require(
                [r["row_index"] for r in observation["rows"]] == expected_rows,
                "all reconciliation rows",
            )
            values = []
            for row in observation["rows"]:
                value, reference = self.table_amount(table_id, row["row_index"], end)
                require(
                    value == Decimal(row["value"]) and reference == row["cell_reference"],
                    "observation original block",
                )
                values.append(value)
            require(sum(values[:-1], Decimal(0)) == values[-1], "source reconciliation closure")
            anchor = observation["cfo_anchor"]
            original = self.native[anchor["raw_object_id"]]
            require("/units/USD/" in anchor["pointer"], "anchor original USD unit path")
            require(
                anchor["metric_id"] == "net_cash_provided_by_used_in_operating_activities"
                and anchor["source_cluster"]
                == observation["source_cluster"]
                == self.issuer[table_id]["source_cluster"]
                == "cik:" + str(original["cik"]).zfill(10),
                "source CFO metric and original issuer identity",
            )
            require(pointer(original, anchor["pointer"]) == anchor["record"], "original CFO anchor")
            require(
                anchor["record"]["end"] == end
                and anchor["record"]["start"] == observation["period_start"]
                and Decimal(str(anchor["record"]["val"])) == values[0] * 1000000,
                "same period exact USD CFO anchor",
            )
            occurrences = [
                x
                for x in anchor["all_equal_source_occurrences"]
                if x["record"].get("accn") == observation["accession"]
            ]
            require(bool(occurrences), "same accession CFO anchor")
            for occurrence in occurrences:
                require(
                    pointer(original, occurrence["pointer"]) == occurrence["record"],
                    "raw same filing anchor",
                )
            require(2010 <= int(end[:4]) <= 2025, "inherited observation year scope")
            self.counts["source_reconciliations_and_native_anchors"] += 1
        require(
            {
                (b["table_id"], b["record"]["end"])
                for b in self.bindings.values()
                if b.get("source_kind") == "issuer_report_table"
            }
            <= checked_periods,
            "every bound issuer period has independently checked reconciliation and native anchor",
        )

    def public_target(self, public):
        if not any(
            s.get("source_kind") == "original_issuer_reconciliation" for s in public["sources"]
        ):
            return super().public_target(public)
        require(
            "company-defined free cash flow" in public["question"], "public financial target label"
        )
        dates = set(re.findall(r"\b\d{4}-\d{2}-\d{2}\b", public["question"]))
        endpoints = {}
        for source in public["sources"]:
            table_id = source["source_id"]
            for header in self.header_sets[table_id]:
                end = header["period_end"]
                if end not in dates:
                    continue
                value, _ = self.table_amount(table_id, self.selected_rows[table_id][-1], end)
                require(
                    end not in endpoints or endpoints[end] == value, "unique public source endpoint"
                )
                endpoints[end] = value
        require(len(endpoints) == 2, "two explicit question endpoint dates")
        previous_end, current_end = sorted(endpoints)
        require(
            330 <= (date.fromisoformat(current_end) - date.fromisoformat(previous_end)).days <= 380,
            "public original adjacent years",
        )
        previous, current = endpoints[previous_end], endpoints[current_end]
        contract = public["quantity_contract"]
        require(
            contract["decimal_places"] == 2 and contract["rounding"] == "half away from zero",
            "public quantity rounding",
        )
        if contract["unit"] == "percent":
            require(
                previous > 0 and "percent" in public["question"], "positive public percent base"
            )
            return 100 * (current - previous) / previous
        require(
            contract["unit"] == "million USD" and "USD millions" in public["question"],
            "public monetary units",
        )
        return current - previous

    def verify_public_sources(self, public):
        for source in public["sources"]:
            if source.get("source_kind") == "original_issuer_reconciliation":
                table = self.issuer[source["source_id"]]
                require(
                    set(source)
                    == {
                        "source_id",
                        "source_kind",
                        "original_url",
                        "raw_sha256",
                        "native_table_xpath",
                        "unit",
                        "definition",
                        "original_rows",
                        "nearby_original_source_text",
                    },
                    "public issuer whitelist",
                )
                require(
                    source["raw_sha256"] == table["raw_sha256"]
                    and source["native_table_xpath"] == table["table_xpath"]
                    and source["definition"] == table["structure"]["definition_quote"]
                    and source["nearby_original_source_text"]
                    == table["structure"]["nearby_source_text"]
                    and source["original_url"] == self.raw[table["raw_object_id"]]["original_url"]
                    and source["unit"] == "million USD",
                    "actual public issuer metadata",
                )
                require(
                    source["original_rows"]
                    == [[c["text"] for c in r] for r in self.grids[source["source_id"]]],
                    "actual public original rows",
                )
            else:
                binding = self.bindings[source["source_id"]]
                require(
                    set(source)
                    == {
                        "source_id",
                        "original_url",
                        "raw_sha256",
                        "native_pointer",
                        "concept",
                        "label",
                        "definition",
                        "unit",
                        "record",
                    },
                    "public native whitelist",
                )
                require(
                    source["record"] == binding["record"]
                    and source["native_pointer"] == binding["pointer"]
                    and source["raw_sha256"] == binding["raw_sha256"]
                    and source["concept"] == "us-gaap:" + binding["tag"]
                    and source["label"] == binding["native_definition"]["label"]
                    and source["definition"] == binding["native_definition"]["description"]
                    and source["original_url"] == self.raw[binding["raw_object_id"]]["original_url"]
                    and source["unit"] == "USD",
                    "actual public JSON source",
                )

    def verify_tasks(self):
        catalog = read(self.stage / "catalog.json")
        check_identity(catalog)
        require(0 <= len(catalog["tasks"]) <= 27, "bounded incremental task count")
        samples = self.index("qa_samples", "qa_id")
        candidates = self.index("qa_candidates", "candidate_id")
        plans = self.index("qa_operation_plans", "plan_id")
        builds = self.index("qa_builds", "qa_build_id")
        patterns = self.index("qa_graph_patterns", "pattern_id")
        checks = self.index("qa_quality_checks", "check_id")
        derived = self.index("derived_facts", "derived_id")
        kg_builds = self.index("kg_builds", "kg_build_id")
        usage = read(self.stage / "all_leaf_usage.json")
        frozen = read(self.stage / "stage_freeze.json")
        check_identity(frozen)
        split = frozen["rule"].get("inherited_source_rules", frozen["rule"])["source_split"]
        compilations = {}
        for row in read(self.stage / "new_tasks" / "pattern_compilations.json"):
            check_identity(row)
            require(row["id"] not in compilations, "unique compilation identity")
            compilations[row["id"]] = row
        seen, results = set(), []
        for item in catalog["tasks"]:
            path = (self.stage / item["path"]).resolve()
            require(path.is_relative_to(self.stage), "task path inside increment")
            bundle = read(path)
            check_identity(bundle)
            task_id = bundle["task_id"]
            require(task_id not in seen and item["task_id"] == task_id, "unique catalog task")
            seen.add(task_id)
            require(item["bundle_id"] == bundle["id"], "exact bundle content parent")
            require(
                item["family"] == bundle["family"]
                and item["source_cluster"] == bundle["source_cluster"],
                "catalog semantic fields",
            )
            require(
                bundle["split"] == "train" and bundle["allowed_uses"] == ["train"],
                "train-only increment",
            )
            public, private, parents = bundle["public"], bundle["private"], bundle["parents"]
            require(
                set(public)
                == {"question", "sources", "quantity_contract", "source_policy", "tool_contract"},
                "public/private separation",
            )
            visible_path = path.parent / "teacher_visible.json"
            visible = read(visible_path)
            require(
                visible == [{"role": "user", "content": canonical(public).decode()}],
                "exact public message",
            )
            surface = bundle["surface_realization"]
            check_identity(surface)
            public_sha = hashlib.sha256(canonical(visible)).hexdigest()
            require(
                hashlib.sha256(visible_path.read_bytes()).hexdigest()
                == public_sha
                == surface["public_messages_sha256"],
                "literal and semantic public SHA",
            )
            require(
                surface["surface_version_id"]
                == "surface_" + hashlib.sha256(canonical([task_id, public_sha])).hexdigest()
                and task_id == bundle["canonical_task_id"] == surface["canonical_task_id"],
                "fixed surface identity",
            )
            require(
                all(
                    s["purpose"] == "question_rewrite" and s["is_Teacher_trajectory"] is False
                    for s in bundle["actual_model_sessions"]
                )
                and not bundle["training_materials"]
                and not bundle["tokenizer_artifacts"],
                "rewrite is not Teacher material",
            )
            sample, candidate = samples[parents["qa_id"]], candidates[parents["candidate_id"]]
            plan, build = plans[parents["operation_plan_id"]], builds[parents["qa_build_id"]]
            require(
                sample["candidate_id"] == candidate["candidate_id"] == plan["candidate_id"],
                "actual QA candidate-plan join",
            )
            require(
                sample["qa_build_id"]
                == candidate["qa_build_id"]
                == plan["qa_build_id"]
                == parents["qa_build_id"]
                == item["qa_build_id"],
                "actual QA build join",
            )
            require(
                sample["question"] == public["question"]
                and sample["validation_status"] == "passed"
                and sample["qa_id"] == item["qa_id"],
                "persisted public QA question",
            )
            require(build["git_commit_sha"] == frozen["git_commit"], "frozen execution revision")
            kg = kg_builds[parents["kg_build_id"]]
            require(build["kg_build_id"] == kg["kg_build_id"], "actual KG build parent")
            require(
                candidate["pattern_hash"]
                == parents["pattern_hash"]
                == patterns[parents["pattern_id"]]["pattern_hash"],
                "actual pattern hash",
            )
            compilation = compilations[parents["compilation_id"]]
            require(
                compilation["task_id"] == task_id
                and compilation["candidate_id"] == parents["candidate_id"],
                "actual compilation parent",
            )
            leaves = set(parents["all_leaf_fact_ids"])
            require(
                len(leaves) == len(parents["all_leaf_fact_ids"]) and bool(leaves),
                "unique real leaves",
            )
            kg_ids = {
                row["source_pk"]
                for row in self.tables["kg_nodes"]
                if row["node_type"] == "Fact" and row["kg_build_id"] == kg["kg_build_id"]
            }
            for identifier in leaves:
                require(identifier in kg_ids, "leaf actual KG node")
                fact, binding = self.facts[identifier], self.bindings[identifier]
                require(fact["build_id"] == parents["fact_build_id"], "actual leaf fact build")
                require(
                    binding["document_id"] in parents["source_document_ids"], "leaf source document"
                )
                require(
                    binding["source_definition_id"] in parents["source_definition_ids"],
                    "leaf source definition",
                )
                require(
                    usage[identifier]
                    == {
                        "allowed_uses": ["train"],
                        "split": "train",
                        "source_cluster": bundle["source_cluster"],
                    },
                    "complete all-leaf split",
                )
                require(
                    binding["source_cluster"]
                    == bundle["source_cluster"]
                    == "cik:" + str(self.entities[fact["entity_id"]]["cik"]).zfill(10),
                    "original entity CIK",
                )
            bucket = (
                int(
                    hashlib.sha256((split["salt"] + bundle["source_cluster"]).encode()).hexdigest(),
                    16,
                )
                % split["buckets"]
            )
            require(
                split["train"][0] <= bucket <= split["train"][1], "independent inherited split hash"
            )
            for identifier in parents["source_derived_ids"]:
                parent = derived[identifier]
                require(
                    set(json.loads(parent["input_fact_ids"])) <= leaves,
                    "all indirect source leaves",
                )
                require(parent["build_id"] == build["derived_build_id"], "actual derived build")
            all_checks = {key for key, row in checks.items() if row["qa_id"] == sample["qa_id"]}
            require(
                set(bundle["validation"]["qa_check_ids"]) == all_checks and bool(all_checks),
                "all actual QA check parents",
            )
            require(
                all(checks[key]["check_status"] == "passed" for key in all_checks),
                "all QA checks passed",
            )
            self.verify_public_sources(public)
            answer = self.public_target(public)
            require(
                answer == Decimal(private["answer_exact"]), "independent original source target"
            )
            target = private["canonical_target"]
            require(
                "task_" + hashlib.sha256(canonical(target)).hexdigest() == task_id,
                "canonical target identity",
            )
            require(target["source_cluster"] == bundle["source_cluster"], "canonical target CIK")
            verify_quantity_identity(target, public["quantity_contract"])
            witnesses = private["basis_witnesses"]
            expected = (
                {"fixed_control_reference"}
                if bundle["family"] == "control"
                else {"endpoint", "movement"}
            )
            require(
                len(witnesses) == len(expected) and {w["basis"] for w in witnesses} == expected,
                "complete distinct reference bases",
            )
            for witness in witnesses:
                check_identity(witness)
                result, used = self.execute_arithmetic(witness)
                require(
                    result == answer == Decimal(witness["output"]["value"]),
                    "independent reference arithmetic",
                )
                require(
                    used <= leaves and witness["is_Teacher_trajectory"] is False,
                    "reference original leaf accounting",
                )
                require(
                    witness["output"]["unit"] == public["quantity_contract"]["unit"],
                    "reference output unit",
                )
                if bundle["family"] == "company_defined_metric":
                    inputs = [self.bindings[key] for key in used]
                    if witness["basis"] == "endpoint":
                        require(
                            len(inputs) == 2 and all(x.get("is_reported_total") for x in inputs),
                            "endpoint basis actual reported totals",
                        )
                    else:
                        required = {
                            key
                            for key in leaves
                            if self.bindings[key].get("source_kind") == "issuer_report_table"
                            and not self.bindings[key].get("is_reported_total")
                        }
                        require(
                            bool(required) and required <= used,
                            "movement basis all signed components",
                        )
                self.counts["source_recomputed_witnesses"] += 1
            results.append(
                {
                    "task_id": task_id,
                    "family": bundle["family"],
                    "source_cluster": bundle["source_cluster"],
                    "qa_build_id": parents["qa_build_id"],
                    "question": public["question"],
                    "answer_exact": str(answer),
                    "answer_rounded": str(answer.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)),
                    "unit": public["quantity_contract"]["unit"],
                    "public_messages_sha256": public_sha,
                    "status": "passed",
                }
            )
        require(
            {x["qa_id"] for x in catalog["tasks"]} == set(samples),
            "no undeclared incremental QA samples",
        )
        self.counts["source_recomputed_tasks"] = len(results)
        return results


def verify(root, directory):
    audit = IncrementalAudit(Path(root), Path(directory))
    manifest_id = audit.verify_manifest()
    audit.verify_sources()
    tasks = audit.verify_tasks()
    return {
        "schema_version": "post_run_incremental_source_audit.v1",
        "status": "passed",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "input_manifest_id": manifest_id,
        "auditor_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "parent_auditor_sha256": hashlib.sha256(_PARENT.read_bytes()).hexdigest(),
        "implementation_independence": "no task generator, issuer adapter or plan executor imports",
        "limitation": (
            "source arithmetic and provenance, not financial NL equivalence "
            "or independent human review"
        ),
        "production_artifacts_changed": False,
        "model_calls": 0,
        "old_233_tasks_reaudited": False,
        "counts": dict(audit.counts),
        "tasks": tasks,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--directory", type=Path, default=Path(STAGE))
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = verify(args.root, args.directory)
    if args.output:
        output = args.output.resolve()
        require(
            not output.is_relative_to((args.root / args.directory).resolve()),
            "report outside sealed increment",
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
