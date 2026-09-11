"""New adapter controls only; no original census or provider reruns."""

import copy
import json

import pytest
from finraw.qa import pipeline
from finraw.qa.graph_patterns import get_pattern
from finraw.qa.operators import OperatorError, execute_operator
from finraw.qa.plans import execute_plan

from trusted_synthesis.experiments.finance_qa_vnext_task_build import factory, relations
from trusted_synthesis.experiments.finance_qa_vnext_task_build.native_facts import (
    annual_observation,
    select_native,
)
from trusted_synthesis.experiments.finance_qa_vnext_task_build.protocol import (
    METRIC_TAGS,
    all_leaf_uses,
    source_identity,
    source_split,
)


def fixture():
    facts, bindings, usage = {}, {}, {}
    definitions = {
        "gross_profit": (
            "Aggregate revenue less cost of goods and services sold or operating expenses "
            "directly attributable to the revenue generation activity."
        ),
        "revenue": "Amount of revenue recognized from goods sold and services rendered.",
        "cost_of_revenue": (
            "The aggregate costs related to goods produced and sold and services rendered "
            "by an entity during the reporting period."
        ),
    }
    for year, amounts in ((2019, (30, 100, 70)), (2020, (40, 130, 90))):
        for metric, amount in zip(definitions, amounts, strict=True):
            identifier = metric + str(year)
            tag = "CostOfRevenue" if metric == "cost_of_revenue" else METRIC_TAGS[metric][0]
            native = {
                "val": amount * 1000000,
                "start": f"{year}-01-01",
                "end": f"{year}-12-31",
                "fy": year,
                "fp": "FY",
                "form": "10-K",
                "filed": f"{year + 1}-02-15",
                "accn": f"filing-{year}",
            }
            facts[identifier] = {
                "fact_id": identifier,
                "entity_id": "AMD_US",
                "entity_type": "company",
                "metric_id": metric,
                "normalized_value": str(amount),
                "normalized_unit": "million USD",
                "normalized_currency": "USD",
                "period_start": native["start"],
                "period_end": native["end"],
                "fiscal_year": year,
                "fiscal_quarter": "FY",
                "source_definition_id": "definition-" + metric,
                "source_id": "sec_companyfacts",
                "raw_object_id": "raw1",
                "graph_ready": 1,
                "verification_status": "single_source",
                "frequency": "annual",
                "time_basis": "fiscal_period",
                "is_forecast": False,
                "financial_scope_type": "consolidated_entity",
                "entity_scope_id": "AMD_US",
                "comparability_level": "xbrl_concept_level",
                "vintage_policy": "fixed_native",
                "metric_period_type": "period_flow",
            }
            bindings[identifier] = {
                "entity_id": "AMD_US",
                "tag": tag,
                "source_definition_id": "definition-" + metric,
                "source_cluster": "cik:0000002488",
                "raw_object_id": "raw1",
                "record": native,
                "native_definition": {"label": metric, "description": definitions[metric]},
                "document_id": "doc1",
                "all_equal_source_occurrences": [{"pointer": "/" + identifier, "record": native}],
            }
            usage[identifier] = {"split": "train", "allowed_uses": ["train"]}
    return facts, bindings, usage


def relation(facts, bindings, usage):
    lookup = {
        (row["entity_id"], row["metric_id"], *relations.actual_period(row)): row
        for row in facts.values()
    }
    return relations.annual_relation(
        facts["gross_profit2019"], facts["gross_profit2020"], lookup, bindings, usage
    )


def test_real_plan_executor_has_two_source_disjoint_sufficient_witnesses():
    facts, bindings, usage = fixture()
    result = relation(facts, bindings, usage)
    assert result["complete"]
    left, right = result["witnesses"]
    assert left["output"]["value"] == right["output"]["value"] == "10"
    assert set(left["input_bindings"].values()).isdisjoint(right["input_bindings"].values())
    assert all(
        not item["is_Teacher_trajectory"] and item["model_session_id"] is None
        for item in (left, right)
    )


@pytest.mark.parametrize(
    "change,reason",
    [
        ("missing_fact", "relation.missing_annual_component"),
        ("wrong_period", "relation.missing_annual_component"),
        ("wrong_definition", "binding.wrong_definition_parent"),
        ("incomplete_cost_scope", "relation.cost_scope_not_proven_complete"),
        ("missing_definition", "binding.missing_definition"),
        ("different_company", "relation.missing_annual_component"),
        ("numeric_only_fake_relation", "relation.native_gross_profit_definition_not_supported"),
        ("no_common_filing", "relation.no_common_filing_accession"),
    ],
)
def test_relation_fails_closed_despite_numeric_closure(change, reason):
    facts, bindings, usage = fixture()
    identifier = "cost_of_revenue2020"
    if change == "missing_fact":
        del facts[identifier]
    elif change == "wrong_period":
        facts[identifier]["period_end"] = "2020-09-30"
    elif change == "wrong_definition":
        facts[identifier]["source_definition_id"] = "other"
    elif change == "incomplete_cost_scope":
        bindings[identifier]["tag"] = "CostOfGoodsSold"
    elif change == "missing_definition":
        bindings[identifier]["native_definition"]["description"] = ""
    elif change == "different_company":
        facts[identifier]["entity_id"] = "OTHER"
    elif change == "numeric_only_fake_relation":
        for year in (2019, 2020):
            bindings["gross_profit" + str(year)]["native_definition"]["description"] = (
                "Some quantity with coincidentally equal values."
            )
    elif change == "no_common_filing":
        bindings[identifier]["all_equal_source_occurrences"][0]["record"]["accn"] = "another-filing"
    with pytest.raises(relations.BindingRejected, match=reason):
        relation(facts, bindings, usage)


def test_native_precision_loss_is_not_silently_accepted():
    facts, bindings, usage = fixture()
    facts["gross_profit2020"]["normalized_value"] = "40.0000001"
    with pytest.raises(relations.BindingRejected, match="normalization_precision_loss"):
        relation(facts, bindings, usage)


@pytest.mark.parametrize(
    "split,uses", [("confirm", ["confirm"]), ("train", ["dev"]), ("dev", ["train", "dev"])]
)
def test_all_leaf_use_and_split_gate_including_indirect_derived_facts(split, uses):
    usage = {
        "F1": {"split": "train", "allowed_uses": ["train"]},
        "F2": {"split": split, "allowed_uses": uses},
    }
    with pytest.raises(ValueError, match="forbidden_leaf"):
        all_leaf_uses(["D2"], {"D2": ["D1", "F1"], "D1": ["F2"]}, usage)


def test_lineage_cannot_drop_an_unknown_leaf_or_hide_a_cycle():
    with pytest.raises(ValueError, match="missing_leaf_authority"):
        all_leaf_uses(["D"], {"D": ["missing"]}, {})
    with pytest.raises(ValueError, match="cyclic_lineage"):
        all_leaf_uses(["D1"], {"D1": ["D2"], "D2": ["D1"]}, {})


def test_same_goal_wordings_and_reference_routes_keep_one_task_identity():
    facts, bindings, usage = fixture()
    left, right = facts["gross_profit2019"], facts["gross_profit2020"]
    identifier, _ = relations.target_identity(left, right, bindings)
    certificate = relation(facts, bindings, usage)
    ids = {
        relations.target_identity(left, right, bindings)[0]
        for wording in ("change", "difference")
        for witness in certificate["witnesses"]
    }
    assert ids == {identifier}
    assert relations.target_identity(left, right, bindings, "relative_change")[0] != identifier


def test_private_answer_plan_canaries_do_not_enter_teacher_messages():
    public = factory.public_projection(
        "What changed?",
        [{"record": {"val": 1}}],
        {
            "unit": "million USD",
            "currency": "USD",
            "decimal_places": 2,
            "rounding": "half away from zero",
        },
    )
    bundle = {
        "public": public,
        "private": {"answer_payload": "SECRET_CANARY_ANSWER", "plan": "SECRET_CANARY_ROUTE"},
        "canonical_semantics": {"answer": "SECRET_CANARY_SEMANTICS"},
    }
    before = factory.teacher_messages(bundle)
    bundle["private"]["answer_payload"] = "REPLACED_CANARY"
    assert before == factory.teacher_messages(bundle)
    assert "CANARY" not in json.dumps(before)
    bundle["public"]["reference_plan"] = {}
    with pytest.raises(ValueError, match="only_whitelisted_fields"):
        factory.teacher_messages(bundle)


def test_native_selector_ignores_FinQA_original_question_gold_and_program():
    raw = {"raw_object_id": "raw1", "content_sha256": "test"}
    entity = {"entity_id": "AMD_US", "cik": "0000002488"}
    payload = {
        "cik": 2488,
        "facts": {
            "us-gaap": {
                "GrossProfit": {
                    "label": "Gross Profit",
                    "description": "Aggregate revenue less cost of goods and services sold.",
                    "units": {
                        "USD": [
                            {
                                "val": 30000000,
                                "start": "2019-01-01",
                                "end": "2019-12-31",
                                "fy": 2019,
                                "fp": "FY",
                                "form": "10-K",
                                "filed": "2020-02-01",
                                "accn": "001",
                            }
                        ]
                    },
                }
            }
        },
    }
    baseline = select_native(payload, entity, raw)
    modified = copy.deepcopy(payload)
    modified["qa"] = {"question": "Copy this unrelated task", "gold": 77777, "program": "fake()"}
    assert select_native(modified, entity, raw) == baseline
    del modified["qa"]
    assert select_native(modified, entity, raw) == baseline


@pytest.mark.parametrize(
    "field,value",
    [
        ("fy", 2020),
        ("start", "2019-10-01"),
        ("end", "2019-01-01"),
        ("form", "10-Q"),
        ("val", "NaN"),
        ("val", "not numeric"),
    ],
)
def test_filing_FY_is_not_enough_to_certify_an_annual_observation(field, value):
    item = {
        "val": 30000000,
        "start": "2019-01-01",
        "end": "2019-12-31",
        "fy": 2019,
        "fp": "FY",
        "form": "10-K",
    }
    assert annual_observation(item)
    item[field] = value
    assert not annual_observation(item)


def test_explicit_source_dates_never_use_the_filing_FY_as_public_period():
    scope = {
        "basis": "explicit_source_periods",
        "fiscal_year": 2099,
        "period_start": "2020-01-01",
        "period_end": "2020-12-31",
        "previous_period_start": "2019-01-01",
        "previous_period_end": "2019-12-31",
    }
    assert pipeline._period_label(scope) == "the period 2020-01-01 through 2020-12-31"
    assert pipeline._previous_period_label(scope) == "the period 2019-01-01 through 2019-12-31"


def test_pattern_is_really_registered_and_executes_no_literal_oracle_binding():
    facts, bindings, usage = fixture()
    pattern = get_pattern("pinned_annual_metric_change")
    execution = execute_plan(
        pattern.operator_template,
        {"previous": "gross_profit2019", "current": "gross_profit2020"},
        facts,
    )
    assert execution.status == "passed" and execution.output["value"] == "10"
    assert execution.output["lineage"]["input_fact_ids"] == ["gross_profit2019", "gross_profit2020"]


@pytest.mark.parametrize("coefficients", [[], [1], [1, 0], [1, True], [1, 0.5], [1, 99]])
def test_signed_component_operator_rejects_bad_or_arbitrary_coefficients(coefficients):
    facts, _, _ = fixture()
    with pytest.raises(OperatorError):
        execute_operator(
            "linear_combination",
            [facts["gross_profit2019"], facts["gross_profit2020"]],
            {"coefficients": coefficients},
        )


def test_typed_result_arithmetic_rejects_wrong_dimensions_and_nonpositive_base():
    with pytest.raises(OperatorError, match="dimensions"):
        execute_operator(
            "linear_combination",
            [{"value": "2", "unit": "USD"}, {"value": "3", "unit": "percent"}],
            {"coefficients": [1, 1]},
        )
    with pytest.raises(OperatorError, match="positive base"):
        execute_operator(
            "ratio_percent", [{"value": "2", "unit": "USD"}, {"value": "0", "unit": "USD"}]
        )
    assert execute_operator(
        "ratio_percent", [{"value": "2", "unit": "USD"}, {"value": "4", "unit": "USD"}]
    ) == {"value": "50", "unit": "percent", "currency": None}


def test_fixed_CIK_source_split_and_zero_default_QA_quotas():
    assert source_identity({"cik": "2488"}) == "cik:0000002488"
    assert source_split("cik:0000002488") == "train"
    config = factory.qa_config()
    resolved = pipeline._qa_policy(config)
    assert not any(resolved["quotas"].values()) and not any(resolved["derived_quotas"].values())
    assert not resolved["pattern_mining"]["enabled"]


def test_enumerator_creates_targets_from_facts_without_any_original_QA():
    facts, bindings, usage = fixture()
    selected, failures, summary = factory.enumerate_bindings(facts, bindings, usage)
    assert len(selected["annual_flow"]) == 2 and len(selected["control"]) == 2
    assert not failures
    assert summary["qualified_counts"]["annual_flow"] == 2


def test_synthetic_positive_runs_existing_fact_KG_QA_build_and_question_parser(tmp_path):
    """A real local Build execution on labelled synthetic control inputs."""
    from finraw.builds import ensure_build_schema, finish_build, start_build
    from finraw.db.client import MetadataDB
    from finraw.derived_facts import refresh_derived_facts
    from finraw.fact_quality import enforce_fact_quality_gates
    from finraw.fact_standardization import refresh_fact_standardization
    from finraw.kg_builder import build_kg, ensure_kg_schema

    from trusted_synthesis.experiments.finance_qa_vnext_task_build.archive import insert
    from trusted_synthesis.experiments.finance_qa_vnext_task_build.native_facts import (
        populate_facts,
        populate_ontology,
    )

    facts, bindings, usage = fixture()
    db = MetadataDB(str(tmp_path / "synthetic_build.sqlite3"))
    db.init_schema()
    ensure_build_schema(db)
    ensure_kg_schema(db)
    entity_build = start_build(
        db, layer="entity", command="synthetic-control", prefix="fixture_entity"
    )
    entity = {
        "entity_id": "AMD_US",
        "canonical_name": "Synthetic Fixture Company",
        "entity_type": "company",
        "market": "US",
        "country": "US",
        "cik": "0000002488",
        "build_id": entity_build,
        "is_active": 1,
    }
    raw = {
        "raw_object_id": "raw1",
        "source_id": "sec_companyfacts",
        "storage_uri": "fixture://explicitly-synthetic-source",
        "original_url": "https://example.invalid/fixture",
        "content_sha256": "synthetic-control-only",
        "validation_status": "passed",
    }
    insert(db, "canonical_entities", [entity])
    insert(db, "raw_objects", [raw])
    insert(
        db,
        "source_registry",
        [
            {
                "source_id": "sec_companyfacts",
                "source_name": "Synthetic fixture registry",
                "source_type": "fixture",
                "authority_level": "fixture",
                "is_active": 1,
            }
        ],
    )
    finish_build(db, entity_build, "success", "Synthetic control, not experimental sources")
    metric_rows = [
        {
            "metric_id": name,
            "canonical_name": name.replace("_", " "),
            "period_type": "period_flow",
            "metric_category": "financial_statement",
            "statement_type": "income_statement",
            "default_unit": "monetary",
        }
        for name in ("gross_profit", "revenue", "cost_of_revenue")
    ]

    class FixtureArchive:
        def fetchall(self, query):
            if query == "SELECT * FROM metrics":
                return copy.deepcopy(metric_rows)
            assert query == "SELECT * FROM source_metric_definitions"
            return []

    observations = []
    for identifier, native in bindings.items():
        observations.append(
            {
                **copy.deepcopy(native),
                "metric_id": facts[identifier]["metric_id"],
                "pointer": "/" + identifier,
                "raw_sha256": raw["content_sha256"],
                "split": "train",
                "allowed_uses": ["train"],
            }
        )
    inputs = [
        {
            "entity": entity,
            "raw_object": raw,
            "observations": observations,
            "definitions": {
                native["tag"]: native["native_definition"] for native in bindings.values()
            },
        }
    ]
    populate_ontology(db, FixtureArchive(), inputs)
    _, _, native_bindings = populate_facts(db, inputs)
    refresh_fact_standardization(db, {})
    assert enforce_fact_quality_gates(db, {})["fact_quality_gate_status"] == "passed"
    refresh_derived_facts(db, {})
    kg_result = build_kg(db, {}, activate=False)
    kg = db.fetchone("SELECT * FROM kg_builds WHERE kg_build_id=?", (kg_result["kg_build_id"],))
    assert kg["status"] == "success" and kg["quality_status"] == "passed"
    native_facts = pipeline._load_facts_by_id(
        db, list(native_bindings), kg["input_fact_build_id"], kg["input_entity_build_id"]
    )
    native_usage = {key: {"split": "train", "allowed_uses": ["train"]} for key in native_bindings}
    selected, failures, _ = factory.enumerate_bindings(native_facts, native_bindings, native_usage)
    assert not failures
    items = selected["annual_flow"] + selected["control"]
    qa_id, candidates, plans, compilations, validation = factory.compile_batch(
        db, kg, items, native_facts, native_bindings, tmp_path, "synthetic_positive"
    )
    assert validation["passed_count"] == 4, validation
    exported, rejected = factory.export_batch(
        db,
        kg,
        qa_id,
        items,
        candidates,
        plans,
        compilations,
        native_facts,
        native_bindings,
        native_usage,
        tmp_path,
    )
    assert len(exported) == 4 and not rejected
    sample = db.fetchone("SELECT * FROM qa_samples WHERE qa_build_id=? LIMIT 1", (qa_id,))
    candidate = next(row for row in candidates if row["candidate_id"] == sample["candidate_id"])
    plan = next(row for row in plans if row["plan_id"] == candidate["operation_plan_id"])
    row = {**sample, **candidate, **plan, "source_metadata": json.loads(sample["source_metadata"])}
    build = pipeline._qa_build(db, qa_id)
    parser = pipeline._question_parser_contract_validation(row, build)
    assert pipeline._reparse_persisted_question(row, parser)["passed"]
    row["question"] = row["question"].replace("2020-12-31", "2021-12-31")
    assert not pipeline._reparse_persisted_question(row, parser)["passed"]
    db.close()


def stock_fixture():
    from trusted_synthesis.experiments.finance_qa_vnext_task_build.protocol import (
        CASH,
        FLOW_METRICS,
    )

    original, _, _ = fixture()
    facts, bindings, usage = {}, {}, {}
    metrics = [
        (CASH, 2019, 10),
        (CASH, 2020, 16),
        (FLOW_METRICS[0], 2020, 20),
        (FLOW_METRICS[1], 2020, -10),
        (FLOW_METRICS[2], 2020, -5),
        ("effect_of_exchange_rate_on_cash_and_cash_equivalents", 2020, 1),
        ("change_in_cash_including_exchange_rate_effect", 2020, 6),
    ]
    for metric, year, amount in metrics:
        identifier = metric + str(year)
        fact = {
            **original["gross_profit" + str(year)],
            "fact_id": identifier,
            "metric_id": metric,
            "normalized_value": str(amount),
            "source_definition_id": "definition-" + metric,
        }
        if metric == CASH:
            fact["period_start"] = None
            fact["metric_period_type"] = "point_in_time"
        native = {
            "val": amount * 1000000,
            "end": fact["period_end"],
            "fy": year,
            "fp": "FY",
            "form": "10-K",
            "accn": "one-common-filing",
            "filed": "2021-02-15",
        }
        if fact["period_start"]:
            native["start"] = fact["period_start"]
        facts[identifier] = fact
        bindings[identifier] = {
            "entity_id": "AMD_US",
            "raw_object_id": "raw1",
            "source_cluster": "cik:0000002488",
            "tag": METRIC_TAGS[metric][0],
            "source_definition_id": fact["source_definition_id"],
            "native_definition": {
                "label": metric,
                "description": "Synthetic typed concept control.",
            },
            "record": native,
            "all_equal_source_occurrences": [{"pointer": "/" + identifier, "record": native}],
        }
        usage[identifier] = {"split": "train", "allowed_uses": ["train"]}
    return facts, bindings, usage


def stock_relation(facts, bindings, usage):
    from trusted_synthesis.experiments.finance_qa_vnext_task_build.protocol import CASH

    lookup = {
        (row["entity_id"], row["metric_id"], *relations.actual_period(row)): row
        for row in facts.values()
    }
    return relations.stock_relation(
        facts[CASH + "2019"], facts[CASH + "2020"], lookup, bindings, usage
    )


def test_complete_cash_bridge_uses_four_signed_components_not_aggregate_answer():
    facts, bindings, usage = stock_fixture()
    certificate = stock_relation(facts, bindings, usage)
    assert [row["output"]["value"] for row in certificate["witnesses"]] == ["6", "6"]
    aggregate = certificate["private_validation_only_fact_ids"][0]
    assert aggregate not in certificate["public_fact_ids"]
    assert aggregate not in certificate["witnesses"][1]["input_bindings"].values()
    assert len(certificate["witnesses"][1]["input_bindings"]) == 4


@pytest.mark.parametrize(
    "change,reason",
    [
        ("missing_fx", "missing_cash_bridge_component"),
        ("missing_aggregate", "missing_cash_bridge_component"),
        ("wrong_aggregate", "cash_bridge_not_complete_or_does_not_close"),
        ("private_leaf_is_eval", "forbidden_leaf"),
        ("wrong_fx_period", "missing_cash_bridge_component"),
    ],
)
def test_cash_relation_completeness_and_all_private_leaf_uses(change, reason):
    facts, bindings, usage = stock_fixture()
    fx = "effect_of_exchange_rate_on_cash_and_cash_equivalents2020"
    aggregate = "change_in_cash_including_exchange_rate_effect2020"
    if change == "missing_fx":
        del facts[fx]
    elif change == "missing_aggregate":
        del facts[aggregate]
    elif change == "wrong_aggregate":
        facts[aggregate]["normalized_value"] = "7"
        bindings[aggregate]["record"]["val"] = 7000000
    elif change == "private_leaf_is_eval":
        usage[aggregate]["split"] = "confirm"
    elif change == "wrong_fx_period":
        facts[fx]["period_start"] = "2020-07-01"
    with pytest.raises(ValueError, match=reason):
        stock_relation(facts, bindings, usage)


def test_existing_semantic_validator_checks_actual_dates_again():
    from finraw.qa.semantic_constraints import validate_semantic_constraints

    facts, _, _ = fixture()
    pattern = get_pattern("pinned_annual_metric_change")
    match = {
        "fact_ids": ["gross_profit2019", "gross_profit2020"],
        "input_bindings": {"previous": "gross_profit2019", "current": "gross_profit2020"},
    }
    metric = {"gross_profit": {"metric_category": "financial_statement"}}
    good = validate_semantic_constraints(pattern, match, facts, metric, {})
    assert good.checks["actual_periods_adjacent_annual"]["passed"]
    facts["gross_profit2020"]["period_end"] = "2019-12-31"
    bad = validate_semantic_constraints(pattern, match, facts, metric, {})
    assert not bad.passed and not bad.checks["actual_periods_adjacent_annual"]["passed"]


def test_content_addressed_identity_cannot_be_kept_after_mutation():
    from trusted_synthesis.experiments.finance_qa_vnext_task_build.archive import (
        record,
        validate_record,
    )

    value = record("manifest", members=[])
    assert validate_record(value, "manifest") == value
    value["members"] = [{"path": "unregistered"}]
    with pytest.raises(ValueError, match="content_addressed_identity"):
        validate_record(value, "manifest")


def test_actual_SQLite_rows_cross_the_record_adapter_boundary_as_mappings(tmp_path):
    from trusted_synthesis.experiments.finance_qa_vnext_task_build.archive import RecordDB, insert

    db = RecordDB(str(tmp_path / "row_boundary.sqlite3"))
    db.execute("CREATE TABLE input_fixture (identifier TEXT PRIMARY KEY, value TEXT)")
    db.execute("INSERT INTO input_fixture VALUES (?, ?)", ("source1", "42"))
    row = db.fetchone("SELECT * FROM input_fixture")
    assert row.get("identifier") == "source1" and "identifier" in row
    assert json.loads(json.dumps(db.fetchall("SELECT * FROM input_fixture")))[0] == row
    db.execute("CREATE TABLE output_fixture (identifier TEXT PRIMARY KEY, value TEXT)")
    raw_rows = db.conn.execute("SELECT * FROM input_fixture").fetchall()
    insert(db, "output_fixture", raw_rows)
    assert db.fetchone("SELECT * FROM output_fixture") == row
    db.close()


def test_synthesized_catalog_reader_exposes_public_not_private_canaries(tmp_path):
    from trusted_synthesis.experiments.finance_qa_vnext_task_build.archive import (
        OUTPUT,
        record,
        sha,
        write_json,
    )
    from trusted_synthesis.experiments.finance_qa_vnext_task_build.catalog import (
        SynthesizedTaskCatalog,
    )

    directory = tmp_path / OUTPUT
    public = factory.public_projection(
        "A synthetic question",
        [],
        {
            "unit": "percent",
            "currency": None,
            "decimal_places": 2,
            "rounding": "half away from zero",
        },
    )
    bundle = record(
        "TaskBundle",
        task_id="synthetic_target",
        public=public,
        private={"answer_payload": "PRIVATE_CANARY"},
        validation={"status": "passed"},
    )
    relative = "tasks/synthetic_target/task_bundle.json"
    write_json(directory / relative, bundle)
    catalog = record(
        "fixed_task_catalog",
        tasks=[{"task_id": "synthetic_target", "path": relative, "bundle_id": bundle["id"]}],
    )
    write_json(directory / "catalog.json", catalog)
    manifest = record(
        "manifest",
        members=[
            {
                "path": path,
                "sha256": sha(directory / path),
                "bytes": (directory / path).stat().st_size,
            }
            for path in (relative, "catalog.json")
        ],
    )
    write_json(directory / "manifest.json", manifest)
    reader = SynthesizedTaskCatalog(tmp_path, expected_manifest_id=manifest["id"])
    assert reader.task_ids() == ("synthetic_target",)
    assert "CANARY" not in json.dumps(reader.public_messages("synthetic_target"))
    assert reader.private_oracle("synthetic_target")["answer_payload"] == "PRIVATE_CANARY"
    with pytest.raises(ValueError, match="explicit_manifest_pin"):
        SynthesizedTaskCatalog(tmp_path, expected_manifest_id="wrong")
