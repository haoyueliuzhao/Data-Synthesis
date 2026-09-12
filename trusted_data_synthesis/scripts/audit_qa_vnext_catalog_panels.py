"""Read-only panel audit using raw JSON, Decimal and saved parent rows only.

No generator, native adapter, QA executor, model or tokenizer is imported.
The optional audit sidecar must be outside the sealed production directory.
"""

import argparse
import hashlib
import json
import re
from collections import Counter, defaultdict
from datetime import date, timedelta
from decimal import Decimal
from functools import lru_cache
from pathlib import Path

STAGE = "trusted_data_synthesis/artifacts/qa_vnext_catalog_bridge/catalog_bridge_20260912"
SALT = "basis_task_factory_sources_20260911.v1:"
GROUPS = ("dual_sufficient", "composition_required", "other_financial")


def year_kind_literals(question):
    """Finite lexical check of this stage's registered template domain only."""
    return {
        kind: bool(re.search(r"\b" + kind + r"[ -]+years?\b", question, re.I))
        for kind in ("calendar", "fiscal", "financial")
    }


def calendar_period_mismatch(question, periods):
    """An explicit calendar-year label cannot replace actual non-calendar flows."""
    if not periods:
        raise ValueError("an explicit nonempty actual-period target is required")
    noncalendar = any(
        start != end[:4] + "-01-01" or end != end[:4] + "-12-31" for start, end in periods
    )
    return year_kind_literals(question)["calendar"] and noncalendar


def read(path):
    return json.loads(Path(path).read_bytes())


def sha(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def unpack(value):
    return json.loads(value) if isinstance(value, str) else value


def rows(directory, table):
    for path in sorted((directory / "parents" / table).glob("*.json")):
        yield from read(path)


class Audit:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.stage = self.root / STAGE
        self.directory = self.stage / "panels"
        self.failures = []
        self.checks = Counter()
        self.task_ids = set()
        self.source_refs = {}

    def check(self, condition, code, *, task=None, detail=None):
        self.checks[code] += 1
        if not condition:
            self.failures.append({"code": code, "task_id": task, "detail": detail})

    def identity(self, value):
        body = {key: item for key, item in value.items() if key != "id"}
        digest = hashlib.sha256(
            json.dumps(
                body, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False
            ).encode()
        ).hexdigest()
        expected = value["schema_version"].rsplit(".", 1)[-1] + ":" + digest
        self.check(value["id"] == expected, "record_content_identity", task=value.get("task_id"))

    @lru_cache(maxsize=2)  # noqa: B019 -- one short-lived audit, cache explicitly bounded.
    def payload(self, relative):
        reference = self.source_refs[relative]
        path = self.root / relative
        self.check(
            path.resolve().is_relative_to(self.root) and not path.is_symlink(),
            "original_source_containment",
        )
        self.check(
            path.stat().st_size == reference["bytes"] and sha(path) == reference["sha256"],
            "complete_original_source_bytes",
        )
        return read(path)

    def amount(self, identifier, bindings, facts, source):
        bound = bindings[identifier]
        reference = source["complete_original_snapshot"]
        payload = self.payload(reference["path"])
        current = payload
        for token in bound["pointer"][1:].split("/"):
            token = token.replace("~1", "/").replace("~0", "~")
            current = current[int(token)] if isinstance(current, list) else current[token]
        self.check(current == bound["record"], "native_pointer_exact_record")
        self.check(str(payload["cik"]).zfill(10) == bound["source_cluster"][4:], "native_CIK")
        value = Decimal(str(current["val"])) / Decimal(1000000)
        fact = facts[identifier]
        self.check(
            value == Decimal(str(fact["normalized_value"])), "native_exact_million_USD_scale"
        )
        self.check(
            (fact["period_start"], fact["period_end"]) == (current.get("start"), current["end"]),
            "native_actual_period",
        )
        self.check(
            payload["facts"]["us-gaap"][bound["tag"]]["description"]
            == bound["native_definition"]["description"],
            "original_native_definition",
        )
        return value

    def interpret(self, witness, values):
        """Independent arithmetic interpreter for the dual certificates only."""
        result = {}
        bindings = witness["input_bindings"]
        for step in witness["operator_dag"]["operators"]:
            args = [
                values[bindings[item["binding"]]] if "binding" in item else result[item["step"]]
                for item in step["inputs"]
            ]
            op = step["operator"]
            if op == "difference":
                answer = args[1] - args[0]
            elif op == "linear_combination":
                answer = sum(
                    a * Decimal(str(c))
                    for a, c in zip(args, step["params"]["coefficients"], strict=True)
                )
            elif op == "ratio_percent":
                answer = 100 * args[0] / args[1]
            elif op == "sum":
                answer = sum(args)
            else:
                raise ValueError("unregistered independent dual operator: " + op)
            result[step["step_id"]] = answer
        return result[witness["operator_dag"]["output_step"]]

    def consecutive(self, identifiers, facts, task):
        ordered = sorted((facts[key] for key in identifiers), key=lambda row: row["period_end"])
        for row in ordered:
            duration = (
                date.fromisoformat(row["period_end"]) - date.fromisoformat(row["period_start"])
            ).days + 1
            self.check(330 <= duration <= 380, "annual_duration", task=task)
        for left, right in zip(ordered, ordered[1:], strict=False):
            self.check(
                date.fromisoformat(right["period_start"])
                == date.fromisoformat(left["period_end"]) + timedelta(days=1),
                "actual_period_continuity",
                task=task,
            )
        self.check(
            len({row["source_definition_id"] for row in ordered}) == 1,
            "unchanged_series_definition",
            task=task,
        )
        return ordered

    def panel(self, split, metadata):
        directory = self.directory / split
        catalog = read(directory / "catalog.json")
        self.identity(catalog)
        sources = read(directory / "public_source_index.json")
        for cluster, source in sources.items():
            reference = source["complete_original_snapshot"]
            self.source_refs[reference["path"]] = reference
            document = read(directory / source["path"])
            self.identity(document)
            self.check(
                sha(directory / source["path"]) == source["sha256"]
                and document["id"] == source["document_id"],
                "public_source_document_identity",
            )
            self.check(
                document["complete_original_snapshot"] == reference
                and document["source_cluster"] == cluster,
                "public_complete_snapshot_reference",
            )
        bindings = read(directory / "native_bindings.json")
        facts = {row["fact_id"]: row for row in rows(directory, "standardized_facts")}
        entities = {row["entity_id"]: row for row in rows(directory, "canonical_entities")}
        definitions = {
            row["definition_id"]: row for row in rows(directory, "source_metric_definitions")
        }
        documents = {row["document_id"]: row for row in rows(directory, "source_documents")}
        derived = {row["derived_id"]: row for row in rows(directory, "derived_facts")}
        candidates = {row["candidate_id"]: row for row in rows(directory, "qa_candidates")}
        samples = {row["qa_id"]: row for row in rows(directory, "qa_samples")}
        plans = {row["plan_id"]: row for row in rows(directory, "qa_operation_plans")}
        kg_builds = {row["kg_build_id"]: row for row in rows(directory, "kg_builds")}
        qa_builds = {row["qa_build_id"]: row for row in rows(directory, "qa_builds")}
        quality = {row["check_id"]: row for row in rows(directory, "qa_quality_checks")}
        compilation = {row["id"]: row for row in read(directory / "QA/pattern_compilations.json")}
        fact_nodes = {
            row["source_pk"]: row
            for row in rows(directory, "kg_nodes")
            if row["node_type"] == "Fact"
        }
        relevant_edges = defaultdict(set)
        for row in rows(directory, "kg_edges"):
            if row["relation_type"] in {"HAS_FACT", "MEASURES", "DERIVED_FROM"}:
                relevant_edges[row["src_node_id"], row["relation_type"]].add(row["dst_node_id"])
        counts, clusters, snapshots = Counter(), Counter(), Counter()
        year_literals = defaultdict(Counter)
        public_period_issues = []
        group_clusters = defaultdict(set)
        memberships = Counter()
        examples = {}
        old = {row["source_cluster"] for row in metadata["historical_confirmation_cik_bindings"]}
        for row in sorted(
            catalog["tasks"], key=lambda row: (row["source_cluster"], row["task_id"])
        ):
            task = row["task_id"]
            bundle = read(directory / row["path"])
            self.identity(bundle)
            self.check(
                bundle["id"] == row["bundle_id"] and task == bundle["task_id"],
                "catalog_bundle_identity",
                task=task,
            )
            self.check(task not in self.task_ids, "scientific_task_unique", task=task)
            self.task_ids.add(task)
            cluster = bundle["source_cluster"]
            bucket = int(hashlib.sha256((SALT + cluster).encode()).hexdigest(), 16) % 55
            expected_split = "train" if bucket < 10 else "dev" if bucket < 19 else "confirm"
            self.check(
                expected_split == split == bundle["split"] and bundle["allowed_uses"] == [split],
                "original_salt_and_usage",
                task=task,
            )
            self.check(cluster not in old, "old_confirmation_issuer_excluded", task=task)
            family = bundle["family"]
            counts[family] += 1
            clusters[cluster] += 1
            group_clusters[family].add(cluster)
            source = sources[cluster]
            snapshots[source["complete_original_snapshot"]["sha256"]] += 1
            private, parent, public = bundle["private"], bundle["parents"], bundle["public"]
            target = private["canonical_target"]
            actual_periods = target.get("actual_periods") or [
                target["previous_period"],
                target["current_period"],
            ]
            literals = year_kind_literals(public["question"])
            for kind, present in literals.items():
                year_literals[family][kind] += present
            if not any(literals.values()):
                year_literals[family]["no_explicit_year_kind"] += 1
            mismatch = calendar_period_mismatch(public["question"], actual_periods)
            detail = {
                "split": split,
                "family": family,
                "task_id": task,
                "source_cluster": cluster,
                "actual_periods": actual_periods,
                "public_question": public["question"],
                "question_utf8_sha256": hashlib.sha256(public["question"].encode()).hexdigest(),
                "public_json_sha256": hashlib.sha256(
                    json.dumps(
                        public, sort_keys=True, ensure_ascii=False, separators=(",", ":")
                    ).encode()
                ).hexdigest(),
                "bundle_path": str((directory / row["path"]).relative_to(self.root)),
                "bundle_file_sha256": sha(directory / row["path"]),
                "original_snapshot_sha256": source["complete_original_snapshot"]["sha256"],
                "reason": (
                    "Public calendar-year wording names a different time basis "
                    "from the bound non-calendar annual flows."
                ),
                "numeric_reference_recomputed_but_public_target_not_admitted": True,
            }
            self.check(
                not mismatch,
                "public_calendar_year_matches_actual_flow_periods",
                task=task,
                detail=detail if mismatch else None,
            )
            if mismatch:
                public_period_issues.append(detail)
            serialized = json.dumps(
                target,
                sort_keys=True,
                ensure_ascii=family != "dual_sufficient",
                separators=(",", ":"),
            ).encode()
            self.check(
                task == "task_" + hashlib.sha256(serialized).hexdigest(),
                "semantic_task_ID_recomputed",
                task=task,
            )
            self.check(
                public["source_document"] == source, "public_full_source_preserved", task=task
            )
            self.check(
                bundle["Teacher_sessions"] == bundle["Student_sessions"] == 0,
                "no_model_trajectory_claim",
                task=task,
            )
            candidate, sample, plan = (
                candidates[parent["candidate_id"]],
                samples[parent["qa_id"]],
                plans[parent["operation_plan_id"]],
            )
            compiled = compilation[parent["compilation_id"]]
            self.identity(compiled)
            self.check(
                sample["candidate_id"] == candidate["candidate_id"]
                and sample["qa_build_id"] == parent["qa_build_id"]
                and sample["question"] == public["question"],
                "real_QA_and_public_question_join",
                task=task,
            )
            self.check(
                sample["validation_status"] == bundle["validation"]["status"] == "passed"
                and candidate["eligibility_status"] == "eligible",
                "exported_QA_qualified",
                task=task,
            )
            self.check(
                sample["generation_method"] == "deterministic_template",
                "no_evaluation_rewrite",
                task=task,
                detail=sample["generation_method"],
            )
            self.check(
                parent["pattern_id"]
                == candidate["pattern_id"]
                == plan["pattern_id"]
                == compiled["pattern_id"]
                and parent["pattern_hash"] == candidate["pattern_hash"] == compiled["pattern_hash"],
                "registered_Pattern_parent_join",
                task=task,
            )
            self.check(
                plan["candidate_id"] == candidate["candidate_id"]
                and plan["qa_build_id"] == parent["qa_build_id"],
                "plan_candidate_build_join",
                task=task,
            )
            self.check(
                kg_builds[parent["kg_build_id"]]["status"] == "success"
                and kg_builds[parent["kg_build_id"]]["quality_status"] == "passed"
                and qa_builds[parent["qa_build_id"]]["quality_status"] == "passed",
                "actual_successful_KG_QA_builds",
                task=task,
            )
            check_ids = bundle["validation"]["qa_check_ids"]
            self.check(
                bool(check_ids)
                and all(
                    quality[key]["qa_id"] == sample["qa_id"]
                    and quality[key]["check_status"] == "passed"
                    for key in check_ids
                ),
                "all_exported_actual_QA_checks",
                task=task,
            )
            leaves = parent["all_leaf_fact_ids"]
            values = {}
            for identifier in leaves:
                bound, fact = bindings[identifier], facts[identifier]
                self.check(
                    bound["source_cluster"] == cluster
                    and bound["split"] == split
                    and bound["allowed_uses"] == [split],
                    "all_leaf_isolation",
                    task=task,
                )
                self.check(
                    "cik:" + str(entities[fact["entity_id"]]["cik"]).zfill(10) == cluster
                    and fact["entity_id"] == bound["entity_id"],
                    "all_leaf_entity_CIK_join",
                    task=task,
                )
                self.check(
                    fact["build_id"] == parent["fact_build_id"]
                    and fact["graph_ready"] == 1
                    and not fact["is_forecast"],
                    "actual_qualified_fact_parent",
                    task=task,
                )
                self.check(
                    fact["source_definition_id"] == bound["source_definition_id"]
                    and fact["source_definition_id"] in definitions
                    and bound["document_id"] in documents,
                    "actual_definition_document_parent",
                    task=task,
                )
                node = fact_nodes[identifier]
                self.check(
                    node["kg_build_id"] == parent["kg_build_id"] and node["is_active"] == 1,
                    "actual_Fact_KG_node",
                    task=task,
                )
                self.check(
                    bool(relevant_edges[node["node_id"], "MEASURES"]),
                    "actual_Fact_metric_KG_edge",
                    task=task,
                )
                values[identifier] = self.amount(identifier, bindings, facts, source)
            for identifier in parent["source_derived_ids"]:
                derivation = derived[identifier]
                self.check(
                    derivation["build_id"] == kg_builds[parent["kg_build_id"]]["input_qa_build_id"]
                    and set(unpack(derivation["input_fact_ids"])) <= set(leaves),
                    "actual_DerivedFact_leaf_parent",
                    task=task,
                )
            inputs = unpack(plan["input_bindings"])
            certificate = private["relation_certificate"]
            self.identity(certificate)
            self.check(
                set(certificate["leaf_fact_ids"]) == set(leaves),
                "certificate_all_leaf_join",
                task=task,
            )
            if family == "dual_sufficient":
                previous, current = inputs["previous"], inputs["current"]
                self.consecutive([previous, current], facts, task)
                answer = values[current] - values[previous]
                if target["quantity"] == "relative_change":
                    self.check(values[previous] > 0, "growth_positive_earlier_base", task=task)
                    answer = answer / values[previous] * 100
                self.check(
                    target["metric_id"] == "gross_profit"
                    and "revenue less cost of goods and services sold"
                    in target["definition"]["description"].lower(),
                    "dual_native_financial_definition",
                    task=task,
                )
                witnesses = certificate["witnesses"]
                self.check(
                    len(witnesses) == 2
                    and set(witnesses[0]["input_bindings"].values()).isdisjoint(
                        witnesses[1]["input_bindings"].values()
                    ),
                    "dual_source_disjoint_witnesses",
                    task=task,
                )
                for witness in witnesses:
                    self.identity(witness)
                    self.check(
                        self.interpret(witness, values) == answer,
                        "independent_dual_basis_recompute",
                        task=task,
                    )
                base = certificate.get("base_relation_certificate", certificate)
                self.identity(base)
                for endpoint in (previous, current):
                    period = (facts[endpoint]["period_start"], facts[endpoint]["period_end"])
                    parts = {
                        facts[key]["metric_id"]: key
                        for key in leaves
                        if (facts[key]["period_start"], facts[key]["period_end"]) == period
                    }
                    revenue, cost = parts["revenue"], parts["cost_of_revenue"]
                    self.check(
                        values[endpoint] == values[revenue] - values[cost]
                        and bindings[cost]["tag"]
                        in {"CostOfRevenue", "CostOfGoodsAndServicesSold"},
                        "independent_complete_annual_revenue_cost_relation",
                        task=task,
                    )
                for citation in base["source_citations"]:
                    self.check(
                        all(
                            item["record"]["accn"] == citation["accession"]
                            for item in citation["source_occurrences"]
                        ),
                        "dual_common_filing_accession",
                        task=task,
                    )
                    for item in citation["source_occurrences"]:
                        original = self.payload(source["complete_original_snapshot"]["path"])
                        for token in item["pointer"][1:].split("/"):
                            token = token.replace("~1", "/").replace("~0", "~")
                            original = (
                                original[int(token)]
                                if isinstance(original, list)
                                else original[token]
                            )
                        self.check(
                            original == item["record"], "dual_original_accession_pointer", task=task
                        )
            elif family == "composition_required":
                identifiers = inputs["series"]
                ordered = self.consecutive(identifiers, facts, task)
                self.check(
                    len(identifiers) == len(set(identifiers)) == 3
                    and certificate["target_coefficients"] == ["1/3"] * 3,
                    "three_real_temporal_components",
                    task=task,
                )
                answer = sum(values[key] for key in identifiers) / 3
                self.check(
                    unpack(plan["operator_dag"])["operators"][0]["operator"] == "mean",
                    "registered_mean_not_difference",
                    task=task,
                )
                bound = bindings[identifiers[0]]
                concept = self.payload(source["complete_original_snapshot"]["path"])["facts"][
                    "us-gaap"
                ][bound["tag"]]
                aggregate = any(
                    item.get("start") == ordered[0]["period_start"]
                    and item.get("end") == ordered[-1]["period_end"]
                    for item in concept["units"].get("USD", [])
                )
                self.check(
                    not aggregate, "full_source_same_concept_window_aggregate_absent", task=task
                )
                self.check(
                    not certificate["endpoints_only_sufficient"]
                    and certificate["complete_original_snapshot_available"],
                    "bounded_composition_claim_not_hidden_endpoints",
                    task=task,
                )
            else:
                primary = self.consecutive(inputs["primary_series"], facts, task)
                secondary = self.consecutive(inputs["secondary_series"], facts, task)
                peak = max(primary, key=lambda row: values[row["fact_id"]])
                self.check(
                    sum(values[row["fact_id"]] == values[peak["fact_id"]] for row in primary) == 1,
                    "unique_primary_peak",
                    task=task,
                )
                chosen = [
                    row
                    for row in secondary
                    if (row["period_start"], row["period_end"])
                    == (peak["period_start"], peak["period_end"])
                ]
                self.check(len(chosen) == 1, "same_actual_period_secondary", task=task)
                answer = values[chosen[0]["fact_id"]]
                self.check(
                    str(peak["fiscal_year"]) == private["answer"]["period"],
                    "independent_peak_year",
                    task=task,
                )
                self.check(
                    [step["operator"] for step in unpack(plan["operator_dag"])["operators"]]
                    == ["argmax", "select_by_period"],
                    "other_finance_not_temporal_difference",
                    task=task,
                )
            exact = Decimal(private["answer"]["value"])
            # Decimal's finite precision may differ only in the final ulp by
            # rearranging percent multiplication; the two-place target must agree.
            self.check(
                abs(answer - exact) <= Decimal("1e-20")
                and Decimal(unpack(candidate["answer_payload"])["value"]) == exact,
                "independent_exact_target",
                task=task,
                detail={"recomputed": str(answer), "stored": str(exact)},
            )
            for period in sorted({facts[key]["period_end"] for key in leaves}):
                memberships[cluster, period] += 1
            examples.setdefault(
                family,
                {
                    "task_id": task,
                    "question": public["question"],
                    "answer": private["answer"],
                    "source_cluster": cluster,
                },
            )
        saved = read(directory / "source_correlation_report.json")
        self.check(
            saved["task_count"] == len(catalog["tasks"])
            and saved["tasks_per_CIK_cluster"] == dict(clusters)
            and saved["source_CIK_cluster_count"] == len(clusters),
            "independent_CIK_correlation_counts",
        )
        self.check(
            saved["tasks_per_original_snapshot"] == dict(snapshots)
            and saved["original_snapshot_count"] == len(snapshots),
            "independent_snapshot_counts",
        )
        overlap = sum(n * (n - 1) // 2 for n in memberships.values())
        self.check(
            saved["overlapping_issuer_period_pairs"] == overlap, "independent_overlap_pair_sum"
        )
        rejected = read(directory / "QA_export_rejections.json")
        rejected_ids = {row["task_id"] for row in rejected}
        selected = read(directory / "QA/target_bindings.json")
        self.check(
            len(selected) == len(catalog["tasks"]) + len(rejected_ids)
            and not rejected_ids & {row["task_id"] for row in catalog["tasks"]},
            "all_fixed_selected_targets_retained_in_denominator",
        )
        qualified = read(directory / "binding_enumeration.json")["qualified_counts"]
        compiler_reasons = Counter(
            reason for item in compilation.values() for reason in item.get("rejection_reasons", [])
        )
        return {
            "task_count": len(catalog["tasks"]),
            "group_counts": dict(counts),
            "shortages": catalog["shortages"],
            "source_CIK_clusters": dict(clusters),
            "source_CIK_count": len(clusters),
            "source_snapshot_count": len(snapshots),
            "CIK_count_by_group": {group: len(group_clusters[group]) for group in GROUPS},
            "overlapping_issuer_period_pair_sum": overlap,
            "qualified_before_caps": qualified,
            "selected_before_QA": len(selected),
            "not_exported_reasons": dict(Counter(row["reason"] for row in rejected)),
            "compiler_semantic_rejections": dict(compiler_reasons),
            "QA_validation": read(directory / "QA/validation_report.json"),
            "examples": examples,
            "year_kind_literal_counts_by_group": {
                key: dict(value) for key, value in year_literals.items()
            },
            "public_period_mismatch_count": len(public_period_issues),
            "public_period_mismatches": public_period_issues,
        }

    def run(self):
        report = read(self.directory / "report.json")
        metadata = read(self.directory / "source_metadata.json")
        self.identity(report)
        self.identity(metadata)
        frozen = read(self.stage / "stage_freeze.json")
        self.check(metadata == frozen["panel_source_metadata"], "frozen_source_metadata_join")
        self.check(report["parent_freeze_id"] == frozen["id"], "frozen_panel_parent_join")
        historical = metadata["historical_confirmation_authority"]
        self.check(
            sha(self.root / historical["path"]) == historical["sha256"],
            "old_confirmation_authority_bytes",
        )
        old_tickers = set(read(self.root / historical["path"])["company_clusters"]["confirm"])
        old_ciks = {
            "cik:" + str(row["entity"]["cik"]).zfill(10)
            for row in metadata["rows"]
            if row["entity"]["ticker"] in old_tickers
        }
        self.check(
            old_ciks
            == {row["source_cluster"] for row in metadata["historical_confirmation_cik_bindings"]},
            "independent_historical_CIK_exclusion_join",
        )
        results = {split: self.panel(split, metadata) for split in ("dev", "confirm")}
        left, right = (set(results[split]["source_CIK_clusters"]) for split in ("dev", "confirm"))
        self.check(left.isdisjoint(right), "dev_confirm_CIK_disjoint")
        self.check(
            len(self.task_ids)
            == report["unique_task_count"]
            == sum(row["task_count"] for row in results.values()),
            "total_scientific_task_denominator",
        )
        period_failures = [
            row
            for row in self.failures
            if row["code"] == "public_calendar_year_matches_actual_flow_periods"
        ]
        other_failures = [row for row in self.failures if row not in period_failures]
        return {
            "status": (
                "BLOCKED_PUBLIC_PERIOD_MISMATCH"
                if period_failures and not other_failures
                else "AUDIT_FAILURE"
                if self.failures
                else "PASS_AS_SCOPED_PARTIAL_PANEL"
            ),
            "audit_revision": 3,
            "post_run_audit_not_preregistered_selection": True,
            "latest_audit_takes_precedence": True,
            "source_parent_arithmetic_checks_passed": not other_failures,
            "public_period_mismatch_count": len(period_failures),
            "no_task_removed_rewritten_replaced_or_refilled": True,
            "no_recomputed_success_panel_from_remaining_records": True,
            "production_panel_report_id": report["id"],
            "production_panel_report_sha256": sha(self.directory / "report.json"),
            "panels": results,
            "unique_tasks": len(self.task_ids),
            "checks": dict(self.checks),
            "check_count": sum(self.checks.values()),
            "failures": self.failures,
            "imported_generation_or_QA_execution_code": False,
            "read_only_original_inputs_and_production_outputs": True,
            "model_calls": 0,
            "primary_evaluation_worker_qualified": False,
            "limitations": [
                (
                    "Composition necessity audited only within registered annual-flow semantics "
                    "and the same-concept whole-window screen, not arbitrary disclosures."
                ),
                (
                    "Same CIK/snapshot and overlapping windows remain correlated; "
                    "no power or effective independent sample size inferred."
                ),
                (
                    "Recorded QA and numeric checks do not override the independently found "
                    "public period mismatch; primary evaluation-worker admission is blocked."
                ),
            ],
        }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    audit = Audit(args.root)
    result = audit.run()
    if args.output:
        path = args.output.resolve()
        if path.is_relative_to(audit.stage):
            raise ValueError("audit output must be outside sealed production directory")
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("x", encoding="utf-8") as stream:
            json.dump(result, stream, ensure_ascii=False, sort_keys=True, indent=2)
    print(
        json.dumps(
            {
                "status": result["status"],
                "unique_tasks": result["unique_tasks"],
                "check_count": result["check_count"],
                "failure_count": len(result["failures"]),
                "failure_codes": dict(Counter(row["code"] for row in result["failures"])),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
