"""Post-run audit of a sealed task build; never imports its generator or executor.

Checks original JSON/HTML bytes, exported parent rows and source-level arithmetic.
This is a separate implementation, not independent human financial review.
The optional report must live outside the immutable production artifact directory.
"""

import argparse
import hashlib
import json
import re
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

from lxml import html

STAGE = "trusted_data_synthesis/artifacts/qa_vnext_task_build/task_factory_20260911"


def require(condition, name):
    if not condition:
        raise ValueError(name)


def read(path):
    return json.loads(path.read_bytes())


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def check_identity(value):
    kind, digest = value["id"].split(":", 1)
    body = {key: item for key, item in value.items() if key != "id"}
    require(body["schema_version"] == "finance_qa_vnext_task_build.v1." + kind, "schema")
    require(hashlib.sha256(canonical(body)).hexdigest() == digest, "content identity")


def normalized_text(node):
    return " ".join(" ".join(node.itertext()).split())


def amount(text):
    text = re.sub(r"[\s,$]", "", text)
    require(bool(re.fullmatch(r"(?:-?\d+(?:\.\d+)?|\(\d+(?:\.\d+)?\))", text)), "amount")
    return -Decimal(text[1:-1]) if text.startswith("(") else Decimal(text)


def pointer(document, path):
    for part in path.lstrip("/").split("/"):
        part = part.replace("~1", "/").replace("~0", "~")
        document = document[int(part)] if isinstance(document, list) else document[part]
    return document


class Audit:
    def __init__(self, root, stage=STAGE):
        self.root = root.resolve()
        self.stage = (self.root / stage).resolve()
        require(self.stage.is_relative_to(self.root), "audit stage contained in project")
        self.tables = {}
        for item in read(self.stage / "parent_table_inventory.json"):
            rows = []
            for path in sorted((self.stage / "parents" / item["table"]).glob("*.json")):
                rows.extend(read(path))
            require(len(rows) == item["row_count"], "parent row count")
            self.tables[item["table"]] = rows
        self.bindings = read(self.stage / "native_bindings.json")
        self.raw = self.index("raw_objects", "raw_object_id")
        self.facts = self.index("standardized_facts", "fact_id")
        self.documents = self.index("source_documents", "document_id")
        self.definitions = self.index("source_metric_definitions", "definition_id")
        self.entities = self.index("canonical_entities", "entity_id")
        self.values, self.native, self.dom, self.grids, self.issuer = {}, {}, {}, {}, {}
        self.counts = Counter()

    def index(self, table, key):
        result = {row[key]: row for row in self.tables[table]}
        require(len(result) == len(self.tables[table]), "unique parent keys: " + table)
        return result

    def verify_manifest(self):
        manifest = read(self.stage / "manifest.json")
        check_identity(manifest)
        observed = set()
        for member in manifest["members"]:
            path = self.stage / member["path"]
            require(path.resolve().is_relative_to(self.stage), "member contained in stage")
            require(not path.is_symlink(), "regular manifest member")
            data = path.read_bytes()
            require(len(data) == member["bytes"], "member length")
            require(hashlib.sha256(data).hexdigest() == member["sha256"], "member hash")
            require(member["path"] not in observed, "unique manifest path")
            observed.add(member["path"])
        actual = {
            str(path.relative_to(self.stage))
            for path in self.stage.rglob("*")
            if path.is_file() and path != self.stage / "manifest.json"
        }
        require(actual == observed, "complete manifest members")
        self.counts["manifest_members"] = len(observed)
        return manifest["id"]

    def verify_sources(self):
        for identifier, row in self.raw.items():
            prefix = "/workspace/Data Synthesis/"
            require(row["storage_uri"].startswith(prefix), "recognized archived path")
            path = self.root / row["storage_uri"].removeprefix(prefix)
            require(path.resolve().is_relative_to(self.root), "local source contained")
            data = path.read_bytes()
            require(len(data) == row["content_size_bytes"], "raw source byte length")
            require(hashlib.sha256(data).hexdigest() == row["content_sha256"], "raw source hash")
            if row["object_type"] == "json":
                self.native[identifier] = json.loads(data)
            else:
                self.dom[identifier] = html.fromstring(data)
            self.counts["original_raw_files"] += 1
        issuer = read(self.stage / "issuer_source_tables.json")
        for table in issuer["tables"]:
            dom = self.dom[table["raw_object_id"]]
            nodes = dom.xpath(table["table_xpath"])
            require(len(nodes) == 1, "unique original table")
            grid = []
            for row_number, row in enumerate(nodes[0].xpath(".//tr")):
                result, start = [], 0
                for number, cell in enumerate(row.xpath("./th|./td")):
                    require(int(cell.get("rowspan", 1)) == 1, "no implicit row span")
                    stop = start + int(cell.get("colspan", 1))
                    result.append(
                        {
                            "row": row_number,
                            "cell": number,
                            "start": start,
                            "stop": stop,
                            "text": normalized_text(cell),
                        }
                    )
                    start = stop
                grid.append(result)
            require(grid == table["structure"]["rows"], "original DOM cell grid")
            require(
                table["structure"]["definition_quote"] in normalized_text(dom), "raw definition"
            )
            require(table["structure"]["nearby_source_text"] in normalized_text(dom), "raw context")
            full_text = normalized_text(dom)
            for note in table["structure"].get("label_annotations", []):
                require(
                    note["note_text_start"] >= table["structure"]["table_text_end"],
                    "footnote outside actual table",
                )
                require(
                    full_text[note["note_text_start"] : note["note_text_end"]]
                    == note["note_quote"],
                    "original following footnote text",
                )
                require(note["original"].endswith(note["marker"]), "original annotated label")
            self.grids[table["table_id"]] = grid
            self.issuer[table["table_id"]] = table
            self.counts["original_issuer_tables"] += 1
        atomic = self.index("atomic_facts", "fact_id")
        for identifier, binding in self.bindings.items():
            fact = self.facts[identifier]
            require(identifier in atomic, "real atomic parent")
            require(fact["graph_ready"] == 1 and not fact["is_forecast"], "qualified native fact")
            require(fact["raw_object_id"] == binding["raw_object_id"], "raw parent")
            require(fact["entity_id"] == binding["entity_id"], "entity parent")
            require(
                fact["source_definition_id"] == binding["source_definition_id"], "definition parent"
            )
            require(binding["document_id"] in self.documents, "document parent")
            require(binding["source_definition_id"] in self.definitions, "definition exists")
            require(fact["period_start"] == binding["record"].get("start"), "native start")
            require(fact["period_end"] == binding["record"]["end"], "native end")
            if binding.get("source_kind") == "issuer_report_table":
                cells = binding["record"]["cell_reference"]["cells"]
                grid = self.grids[binding["table_id"]]
                for cell in cells:
                    require(grid[cell["row"]][cell["cell"]] == cell, "original referenced cell")
                value = amount(" ".join(cell["text"] for cell in cells))
                require(value == Decimal(binding["record"]["val"]), "original table amount")
                self.counts["issuer_cell_facts"] += 1
            else:
                document = self.native[binding["raw_object_id"]]
                require(
                    pointer(document, binding["pointer"]) == binding["record"], "original JSON row"
                )
                definition = document["facts"]["us-gaap"][binding["tag"]]
                require(
                    {key: definition[key] for key in ("label", "description")}
                    == binding["native_definition"],
                    "original concept definition",
                )
                require(
                    str(document["cik"]).zfill(10) == binding["source_cluster"][4:], "native CIK"
                )
                for occurrence in binding["all_equal_source_occurrences"]:
                    require(
                        pointer(document, occurrence["pointer"]) == occurrence["record"],
                        "original equal-value disclosure occurrence",
                    )
                    self.counts["original_disclosure_occurrences"] += 1
                value = Decimal(str(binding["record"]["val"])) / 1000000
                self.counts["native_JSON_facts"] += 1
            require(
                value == Decimal(str(fact["normalized_value"])), "exact normalized source value"
            )
            self.values[identifier] = value
        require(set(self.values) == set(self.facts), "all standardized facts source checked")

    def execute_arithmetic(self, witness):
        results, used = {}, set()
        for step in witness["operator_dag"]["operators"]:
            require(step["step_id"] not in results, "unique arithmetic step")
            operands = []
            for reference in step["inputs"]:
                if "step" in reference:
                    operands.append(results[reference["step"]])
                else:
                    identifier = witness["input_bindings"][reference["binding"]]
                    operands.append(self.values[identifier])
                    used.add(identifier)
            operator = step["operator"]
            if operator == "difference":
                require(len(operands) == 2, "difference arity")
                result = operands[1] - operands[0]
            elif operator == "linear_combination":
                coefficients = step["params"]["coefficients"]
                require(len(coefficients) == len(operands), "linear arity")
                require(set(coefficients) <= {-1, 1}, "signed finite coefficients")
                result = sum(
                    (c * v for c, v in zip(coefficients, operands, strict=True)), Decimal(0)
                )
            elif operator == "ratio_percent":
                require(len(operands) == 2 and operands[1] > 0, "positive ratio base")
                result = 100 * operands[0] / operands[1]
            else:
                raise ValueError("unsupported audit operator: " + operator)
            results[step["step_id"]] = result
        return results[witness["operator_dag"]["output_step"]], used

    def public_target(self, public):
        """Choose endpoints from public source concepts/labels, never private role maps."""
        question = public["question"]
        dates = re.findall(r"\b\d{4}-\d{2}-\d{2}\b", question)
        require(bool(dates), "explicit question dates")
        target_end = max(dates)
        sources = public["sources"]
        if "company-defined free cash flow" in question:
            endpoints = {}
            for source in sources:
                grid = self.grids[source["source_id"]]
                total_rows = [
                    row
                    for row in grid
                    if re.fullmatch(
                        r"(?:non-gaap\s+)?free cash flow(?:\s*\(non-gaap\))?\s*(?:\*|\(\d+\))?",
                        next((cell["text"] for cell in row if cell["text"]), "").lower(),
                    )
                ]
                require(len(total_rows) == 1, "public issuer total label")
                body_start = next(
                    index
                    for index, row in enumerate(grid)
                    if any(
                        re.search(
                            r"operating activities|cash flows? from operations", cell["text"], re.I
                        )
                        for cell in row
                    )
                )
                prefix = " ".join(cell["text"] for row in grid[:body_start] for cell in row)
                month_days = set(
                    re.findall(
                        r"\b(January|February|March|April|May|June|July|August|September|October|November|December)"
                        r"\s+(\d{1,2})(?!\d)",
                        prefix,
                    )
                )
                for row in grid[:body_start]:
                    for cell in row:
                        try:
                            end = datetime.strptime(cell["text"], "%B %d, %Y").date().isoformat()
                        except ValueError:
                            if not re.fullmatch(r"20\d{2}", cell["text"]) or len(month_days) != 1:
                                continue
                            month, day = next(iter(month_days))
                            end = (
                                datetime.strptime(
                                    month + " " + day + " " + cell["text"], "%B %d %Y"
                                )
                                .date()
                                .isoformat()
                            )
                        cells = [
                            x
                            for x in total_rows[0]
                            if cell["start"] <= x["start"] and x["stop"] <= cell["stop"]
                        ]
                        value = amount(" ".join(x["text"] for x in cells))
                        require(
                            end not in endpoints or endpoints[end] == value,
                            "unambiguous public total",
                        )
                        endpoints[end] = value
            end = max(x for x in endpoints if x < target_end)
            previous, current = endpoints[end], endpoints[target_end]
            require(
                330 <= (date.fromisoformat(target_end) - date.fromisoformat(end)).days <= 380,
                "public issuer annual adjacency",
            )
        else:
            if "Gross Profit" in question:
                allowed = {"GrossProfit"}
            elif "Cash, Cash Equivalents, Restricted Cash" in question:
                allowed = {"CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents"}
            elif "Cash and Cash Equivalents" in question:
                allowed = {"CashAndCashEquivalentsAtCarryingValue"}
            else:
                allowed = {source["concept"].split(":", 1)[1] for source in sources}
                require(len(allowed) == 1, "one public control concept")
            records = [
                source["record"]
                for source in sources
                if source["concept"].split(":", 1)[1] in allowed
            ]
            require(len(records) == 2, "two public endpoints")
            prior, current_row = sorted(records, key=lambda row: row["end"])
            end = prior["end"]
            require(current_row["end"] == target_end, "question current endpoint")
            require(
                330 <= (date.fromisoformat(target_end) - date.fromisoformat(end)).days <= 380,
                "public native annual adjacency",
            )
            if current_row.get("start"):
                require(
                    date.fromisoformat(current_row["start"])
                    == date.fromisoformat(end) + timedelta(days=1),
                    "public flow adjacency",
                )
                require(current_row["start"] in dates, "question current flow start")
            previous, current = (Decimal(str(row["val"])) / 1000000 for row in (prior, current_row))
        contract = public["quantity_contract"]
        require(
            contract["decimal_places"] == 2 and contract["rounding"] == "half away from zero",
            "public rounding contract",
        )
        if contract["unit"] == "percent":
            require(previous > 0 and "percent" in question, "public percentage")
            return 100 * (current - previous) / previous
        require(
            contract["unit"] == "million USD" and "USD millions" in question, "public dollar unit"
        )
        require(end in dates, "question prior endpoint")
        return current - previous

    def verify_tasks(self):
        catalog = read(self.stage / "catalog.json")
        check_identity(catalog)
        samples = self.index("qa_samples", "qa_id")
        candidates = self.index("qa_candidates", "candidate_id")
        plans = self.index("qa_operation_plans", "plan_id")
        builds = self.index("qa_builds", "qa_build_id")
        patterns = self.index("qa_graph_patterns", "pattern_id")
        checks = self.index("qa_quality_checks", "check_id")
        derived = self.index("derived_facts", "derived_id")
        kg = self.tables["kg_builds"][0]
        kg_fact_ids = {
            row["source_pk"] for row in self.tables["kg_nodes"] if row["node_type"] == "Fact"
        }
        usage = read(self.stage / "all_leaf_usage.json")
        frozen = read(self.stage / "stage_freeze.json")
        compilations = {}
        for batch in ("first_20", "candidate_catalog"):
            for row in read(self.stage / batch / "pattern_compilations.json"):
                check_identity(row)
                compilations[row["id"]] = row
        task_ids, results = set(), []
        for item in catalog["tasks"]:
            bundle = read(self.stage / item["path"])
            check_identity(bundle)
            require(bundle["task_id"] not in task_ids, "unique target identity")
            task_ids.add(bundle["task_id"])
            require(bundle["id"] == item["bundle_id"], "catalog bundle parent")
            public, private, parents = bundle["public"], bundle["private"], bundle["parents"]
            require(
                set(public)
                == {"question", "sources", "quantity_contract", "source_policy", "tool_contract"},
                "public top-level whitelist",
            )
            visible = read((self.stage / item["path"]).parent / "teacher_visible.json")
            require(
                visible == [{"role": "user", "content": canonical(public).decode()}],
                "actual public message",
            )
            require(
                (
                    not bundle["actual_model_sessions"]
                    or (
                        "surface_realization" in bundle
                        and all(
                            row["purpose"] == "question_rewrite"
                            and row["is_Teacher_trajectory"] is False
                            for row in bundle["actual_model_sessions"]
                        )
                    )
                )
                and not bundle["training_materials"]
                and not bundle["tokenizer_artifacts"],
                "no Teacher or training artifacts; rewrite requests explicitly distinct",
            )
            sample, candidate = samples[parents["qa_id"]], candidates[parents["candidate_id"]]
            plan, build = plans[parents["operation_plan_id"]], builds[parents["qa_build_id"]]
            require(
                sample["candidate_id"] == candidate["candidate_id"] == plan["candidate_id"],
                "QA parent join",
            )
            require(
                sample["qa_build_id"]
                == candidate["qa_build_id"]
                == plan["qa_build_id"]
                == parents["qa_build_id"],
                "QA build join",
            )
            require(
                sample["question"] == public["question"]
                and sample["validation_status"] == "passed",
                "actual QA question",
            )
            require(
                build["git_commit_sha"] == frozen["git_commit"], "actual build frozen code revision"
            )
            require(
                build["kg_build_id"] == parents["kg_build_id"] == kg["kg_build_id"],
                "KG parent join",
            )
            require(
                candidate["pattern_hash"]
                == parents["pattern_hash"]
                == patterns[parents["pattern_id"]]["pattern_hash"],
                "registered pattern hash",
            )
            compilation = compilations[parents["compilation_id"]]
            require(
                compilation["task_id"] == bundle["task_id"]
                and compilation["candidate_id"] == candidate["candidate_id"],
                "compilation parent join",
            )
            leaves = set(parents["all_leaf_fact_ids"])
            for identifier in leaves:
                require(identifier in kg_fact_ids, "leaf is actual KG fact")
                fact, source = self.facts[identifier], self.bindings[identifier]
                require(fact["build_id"] == parents["fact_build_id"], "leaf fact build")
                require(source["document_id"] in parents["source_document_ids"], "leaf document")
                require(
                    source["source_definition_id"] in parents["source_definition_ids"],
                    "leaf definition",
                )
                require(
                    usage[identifier]
                    == {
                        "allowed_uses": ["train"],
                        "split": "train",
                        "source_cluster": bundle["source_cluster"],
                    },
                    "all leaf uses",
                )
                cik = str(self.entities[fact["entity_id"]]["cik"]).zfill(10)
                require("cik:" + cik == bundle["source_cluster"], "leaf entity CIK")
            split = frozen["rule"].get("inherited_source_rules", frozen["rule"])["source_split"]
            bucket = int(
                hashlib.sha256((split["salt"] + bundle["source_cluster"]).encode()).hexdigest(), 16
            )
            require(bucket % split["buckets"] <= split["train"][1], "independent split hash")
            for identifier in parents["source_derived_ids"]:
                parent = derived[identifier]
                require(set(json.loads(parent["input_fact_ids"])) <= leaves, "all indirect leaves")
                require(parent["build_id"] == build["derived_build_id"], "derived build parent")
            for identifier in bundle["validation"]["qa_check_ids"]:
                require(
                    checks[identifier]["qa_id"] == sample["qa_id"]
                    and checks[identifier]["check_status"] == "passed",
                    "actual validation row",
                )
            for source in public["sources"]:
                if source.get("source_kind") == "original_issuer_reconciliation":
                    table = self.issuer[source["source_id"]]
                    grid = self.grids[source["source_id"]]
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
                        "public issuer source field whitelist",
                    )
                    require(
                        source["definition"] == table["structure"]["definition_quote"]
                        and source["nearby_original_source_text"]
                        == table["structure"]["nearby_source_text"]
                        and source["native_table_xpath"] == table["table_xpath"]
                        and source["original_url"]
                        == self.raw[table["raw_object_id"]]["original_url"]
                        and source["raw_sha256"] == table["raw_sha256"]
                        and source["unit"] == "million USD",
                        "public issuer original context",
                    )
                    require(
                        source["original_rows"] == [[cell["text"] for cell in row] for row in grid],
                        "public original table",
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
                        "public native source field whitelist",
                    )
                    require(
                        source["record"] == binding["record"]
                        and source["native_pointer"] == binding["pointer"]
                        and source["raw_sha256"] == binding["raw_sha256"]
                        and source["label"] == binding["native_definition"]["label"]
                        and source["definition"] == binding["native_definition"]["description"]
                        and source["original_url"]
                        == self.raw[binding["raw_object_id"]]["original_url"]
                        and source["concept"] == "us-gaap:" + binding["tag"]
                        and source["unit"] == "USD",
                        "public native source",
                    )
            answer = self.public_target(public)
            require(answer == Decimal(private["answer_exact"]), "independent public target answer")
            target = private["canonical_target"]
            require(
                "task_" + hashlib.sha256(canonical(target)).hexdigest() == bundle["task_id"],
                "semantic identity",
            )
            expected_witnesses = 1 if bundle["family"] == "control" else 2
            require(len(private["basis_witnesses"]) == expected_witnesses, "basis count")
            for witness in private["basis_witnesses"]:
                result, used = self.execute_arithmetic(witness)
                require(
                    result == answer == Decimal(witness["output"]["value"]),
                    "independent witness arithmetic",
                )
                require(
                    used <= leaves and not witness["is_Teacher_trajectory"],
                    "Oracle leaf accounting",
                )
                self.counts["source_recomputed_witnesses"] += 1
            results.append(
                {
                    "task_id": bundle["task_id"],
                    "family": bundle["family"],
                    "source_cluster": bundle["source_cluster"],
                    "qa_build_id": parents["qa_build_id"],
                    "question": public["question"],
                    "answer_exact": str(answer),
                    "answer_rounded": str(answer.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)),
                    "unit": public["quantity_contract"]["unit"],
                    "leaf_count": len(leaves),
                    "status": "passed",
                }
            )
        self.counts["source_recomputed_tasks"] = len(results)
        return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--stage", default=STAGE)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    audit = Audit(args.root, args.stage)
    manifest_id = audit.verify_manifest()
    audit.verify_sources()
    results = audit.verify_tasks()
    report = {
        "schema_version": "post_run_task_source_audit.v1",
        "status": "passed",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "input_manifest_id": manifest_id,
        "auditor_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "implementation_independence": (
            "no task generator, relation compiler or plan executor imports"
        ),
        "limitation": (
            "source arithmetic and provenance, not independent human financial review or "
            "natural-language equivalence proof; actual rewrite semantics require the separately "
            "registered finite question parser"
        ),
        "production_artifacts_changed": False,
        "model_calls": 0,
        "counts": dict(audit.counts),
        "tasks": results,
    }
    if args.output:
        output = args.output.resolve()
        require(
            not output.is_relative_to(audit.stage), "audit report outside sealed production stage"
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
