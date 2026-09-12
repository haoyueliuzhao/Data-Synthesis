import copy
import json

import pytest

from trusted_synthesis.experiments.finance_qa_vnext_eval_readiness import (
    assessment,
    controls,
    runtime,
)


@pytest.fixture
def mean():
    return controls.synthetic_fixture()


@pytest.mark.parametrize("case", controls.synthetic_cases(), ids=lambda case: case["name"])
def test_new_structure_positive_and_negative_controls(case):
    result = controls.run_controls([case])
    assert result["status"] == "PASS", result["controls"][0]["assessment"]
    assert result["API_requests"] == result["tokenizer_constructions"] == 0
    assert result["training_samples"] == result["historic_material_rows_reencoded"] == 0


def _generate(fixture, scripted, **kwargs):
    return runtime.generate(
        fixture["messages"], fixture["identity"], fixture["sources"], scripted=scripted, **kwargs
    )


def _assess(fixture, session):
    return assessment.assess_session(
        session, fixture["bundle"], fixture["native_bindings"], fixture["sources"]
    )


def _refresh(fixture):
    fixture["messages"] = [
        {"role": "user", "content": runtime.encode(fixture["bundle"]["public"]).decode()}
    ]
    fixture["identity"]["public_messages_sha256"] = runtime.sha(runtime.encode(fixture["messages"]))


def test_source_query_pagination_has_original_records_and_omitted_concepts(mean):
    source = mean["sources"]
    first = source.query({"source_id": "snapshot", "concept": "us-gaap:Revenue", "limit": 2})
    second = source.query(
        {
            "source_id": "snapshot",
            "concept": "us-gaap:Revenue",
            "offset": first["next_offset"],
            "limit": 2,
        }
    )
    assert first["total"] == 3 and second["next_offset"] is None
    assert [row["record"]["val"] for row in first["records"] + second["records"]] == [
        100000000,
        200000000,
        300000000,
    ]
    unselected = source.query({"source_id": "snapshot", "concept": "us-gaap:UnselectedControl"})
    assert {row["source_unit"] for row in unselected["records"]} == {"USD", "shares"}
    assert any(row["record"]["val"] == 777 for row in unselected["records"])
    assert all(
        row["actual_period"]["period_id"].startswith("period:") for row in unselected["records"]
    )


def test_exact_actual_date_queries_do_not_infer_fy(mean):
    source = mean["sources"]
    rows = source.query(
        {
            "source_id": "snapshot",
            "concept": "us-gaap:Revenue",
            "start": "2020-09-28",
            "end": "2021-09-26",
        }
    )["records"]
    assert len(rows) == 1
    assert rows[0]["record"]["fy"] == 2022
    assert rows[0]["actual_period"]["period_id"] == "period:duration:2020-09-28:2021-09-26"
    assert not source.query(
        {
            "source_id": "snapshot",
            "concept": "us-gaap:Revenue",
            "start": "2021-01-01",
            "end": "2021-12-31",
        }
    )["records"]


@pytest.mark.parametrize(
    "arguments",
    [
        {"offset": -1},
        {"offset": True},
        {"limit": 0},
        {"limit": 21},
        {"limit": 1.5},
        {"private_leaf_ids": []},
    ],
)
def test_query_rejects_unbounded_or_private_filter_fields(mean, arguments):
    with pytest.raises(ValueError):
        mean["sources"].query({"source_id": "snapshot", **arguments})


def test_read_json_reaches_every_original_subtree_without_flattening(mean):
    source = mean["sources"]
    root = source.read_json({"source_id": "snapshot", "pointer": "", "limit": 2})
    assert root["total"] == 3 and root["next_offset"] == 2
    records = source.read_json(
        {"source_id": "snapshot", "pointer": "/facts/us-gaap/UnselectedControl/units/USD"}
    )
    assert records["items"][0]["value"] is None
    leaf = source.read_json(
        {"source_id": "snapshot", "pointer": records["items"][0]["pointer"] + "/val"}
    )
    assert leaf["items"][0]["value"] == 777
    concepts = source.list_concepts({"source_id": "snapshot", "limit": 2})
    assert concepts["total"] == 5 and concepts["next_offset"] == 2


def test_read_source_actual_currency_conversion(mean):
    result = mean["sources"].read_source(controls.read("Revenue", 0)["arguments"])
    assert result["exact_value"] == "100"
    assert result["conversion"]["factor"] == "1/1000000"
    assert result["record"]["val"] == 100000000


@pytest.mark.parametrize(
    "pointer",
    [
        "/facts/us-gaap/Revenue/units/USD/00",
        "/facts/us-gaap/Revenue/units/USD/-1",
        "/facts/us-gaap/Revenue/units/USD/0/val",
        "/facts/us-gaap/Revenue/units/USD/9",
    ],
)
def test_numeric_source_pointer_must_be_exact_original_record(mean, pointer):
    with pytest.raises((ValueError, IndexError)):
        mean["sources"].read_source({"source_id": "snapshot", "native_pointer": pointer})


def test_native_unit_cannot_be_relabelled_by_requested_unit(mean):
    with pytest.raises(ValueError):
        mean["sources"].read_source(
            {
                "source_id": "snapshot",
                "native_pointer": "/facts/us-gaap/UnselectedControl/units/shares/0",
                "unit": "USD",
            }
        )


def test_snapshot_hash_and_intermediate_symlink_are_rejected(tmp_path, mean):
    payload = mean["sources"].payloads["snapshot"]
    raw = runtime.encode(payload)
    # Test fixtures are explicitly allowed to create temporary bytes.
    target = tmp_path / "source.json"
    target.write_bytes(raw)
    references = [
        {
            "source_id": "snapshot",
            "complete_original_snapshot": {
                "path": "source.json",
                "sha256": runtime.sha(raw),
                "bytes": len(raw),
            },
        }
    ]
    assert (
        runtime.SnapshotSources(tmp_path, references).query({"source_id": "snapshot"})["total"] > 0
    )
    target.write_bytes(raw + b" ")
    with pytest.raises(ValueError, match="original_snapshot_identity"):
        runtime.SnapshotSources(tmp_path, references).query({"source_id": "snapshot"})
    folder = tmp_path / "folder"
    folder.mkdir()
    (folder / "raw.json").write_bytes(raw)
    (tmp_path / "linked").symlink_to(folder, target_is_directory=True)
    references[0]["complete_original_snapshot"]["path"] = "linked/raw.json"
    with pytest.raises(ValueError, match="snapshot_symlink"):
        runtime.SnapshotSources(tmp_path, references).query({"source_id": "snapshot"})


def test_worker_does_not_receive_private_bundle_or_native_roles(mean):
    mean["bundle"]["private"]["private_canary"] = "SECRET_EXPECTED_AMOUNT_ROLE"
    script = controls.synthetic_cases()[0]["scripted"]
    seen = []

    def provider(messages, context):
        seen.append((copy.deepcopy(messages), copy.deepcopy(context)))
        assert "SECRET_EXPECTED_AMOUNT_ROLE" not in json.dumps([messages, context])
        return {
            "raw_response": runtime.encode(script[len(seen) - 1]).decode(),
            "receipt": {"request_id": str(len(seen))},
        }

    result = runtime.generate(
        mean["messages"], mean["identity"], mean["sources"], provider=provider
    )
    assert result["provider_calls"] == 5 and result["origin"] == "live_evaluation_callback"
    assert _assess(mean, result)["financial_valid"]
    assert result["turns"][-1]["provider_receipt"] == {"request_id": "5"}


def test_provider_error_preserves_incomplete_history_and_has_no_retry(mean):
    calls = []

    def provider(messages, context):
        calls.append(context["response_index"])
        if len(calls) == 1:
            return runtime.encode(controls.read("Revenue", 0)).decode()
        raise TimeoutError("synthetic timeout")

    result = runtime.generate(
        mean["messages"], mean["identity"], mean["sources"], provider=provider
    )
    assert calls == [0, 1]
    assert result["terminal"] == "provider_error" and len(result["turns"]) == 1
    assert _assess(mean, result)["reason"] == "no_final"


def test_failures_are_in_every_later_public_history(mean):
    script = [
        "malformed",
        {"tool": "missing", "arguments": {}},
        controls.read("Revenue", 0),
        controls.final(100, "tool:2"),
    ]
    session = _generate(mean, script)
    final_history = session["turns"][-1]["input_messages"]
    assert any(row["content"] == "malformed" for row in final_history)
    assert any("tool.unknown_tool" in row["content"] for row in final_history)
    assert all(event["oracle_feedback"] is False for event in session["events"])


def test_first_malformed_final_stops_and_disallows_later_repair(mean):
    session = _generate(mean, [{"final": None}, controls.read("Revenue", 0)])
    assert len(session["turns"]) == 1 and session["terminal"] == "first_final"
    assert _assess(mean, session)["reason"] == "final_shape_or_reference"


def test_response_and_tool_limits_are_new_32_32_contract(mean):
    script = [controls.read("Revenue", 0)] * 33
    session = _generate(mean, script)
    assert len(session["turns"]) == 32 and session["max_tools"] == 32
    assert session["terminal"] == "response_budget_exhausted"
    limited = _generate(mean, script, max_tools=2)
    assert len(limited["turns"]) == 3 and limited["terminal"] == "tool_budget_exhausted"
    assert sum(event["tool_call"] is not None for event in limited["events"]) == 2
    with pytest.raises(ValueError):
        _generate(mean, script, max_tools=33)


def test_oversized_response_stops_without_retry_or_history_deletion(mean):
    raw = " " * 65537
    session = _generate(mean, [raw, controls.final(200, "tool:1")])
    assert session["terminal"] == "response_byte_limit" and len(session["turns"]) == 1
    assert session["turns"][0]["raw_response"] == raw


def test_public_identity_and_descriptor_whitelists(mean):
    mean["identity"]["answer"] = "200"
    with pytest.raises(ValueError, match="public_identity_allowlist"):
        _generate(mean, [])
    del mean["identity"]["answer"]
    mean["bundle"]["public"]["private"] = {"answer": 200}
    _refresh(mean)
    with pytest.raises(ValueError, match="public_fields_allowlist"):
        _generate(mean, [])


def test_replayed_events_and_failed_history_cannot_be_mutated(mean):
    session = _generate(mean, controls.synthetic_cases()[0]["scripted"])
    session["events"][0]["tool_call"]["result"]["record"]["val"] += 1
    session = runtime.record(
        "evaluation_session",
        **{key: value for key, value in session.items() if key not in {"id", "schema_version"}},
    )
    with pytest.raises(ValueError, match="history_replay"):
        _assess(mean, session)


def test_mean_wrong_actual_interval_equal_value_cannot_substitute(mean):
    script = [
        controls.read("Revenue", 0),
        controls.read("Revenue", 2),
        controls.calculate("a+(c-a)/2", a="tool:1", c="tool:2"),
        controls.final(200, "tool:3"),
    ]
    result = _assess(mean, _generate(mean, script))
    assert not result["financial_valid"]
    assert "all_three_actual_interval" in result["reason"]


def test_mean_rational_reassociation_and_guidance_do_not_split_fine_class(mean):
    base = [controls.read("Revenue", index) for index in range(3)]
    scripts = [
        [
            *base,
            controls.calculate(expression, a="tool:1", b="tool:2", c="tool:3"),
            controls.final(200, "tool:4"),
        ]
        for expression in ("avg(a,b,c)", "(c+a+b)/3")
    ]
    outcomes = [
        _assess(mean, _generate(mean, script, requested_basis=guidance))
        for script, guidance in zip(scripts, ("endpoint", "movement"), strict=True)
    ]
    assert all(row["financial_valid"] for row in outcomes)
    assert outcomes[0]["full_class"] == outcomes[1]["full_class"]


def test_extra_recalculation_and_explicit_revision_remain_complete_class_dimensions(mean):
    base = [controls.read("Revenue", index) for index in range(3)]
    standard = controls.calculate("avg(a,b,c)", a="tool:1", b="tool:2", c="tool:3")
    simple = _assess(mean, _generate(mean, [*base, standard, controls.final(200, "tool:4")]))
    repeated = _assess(
        mean, _generate(mean, [*base, standard, standard, controls.final(200, "tool:5")])
    )
    revision = copy.deepcopy(standard)
    revision["arguments"]["revises_result_id"] = "tool:4"
    revised = _assess(
        mean,
        _generate(
            mean,
            [
                *base,
                controls.calculate("a+b+c", a="tool:1", b="tool:2", c="tool:3"),
                revision,
                controls.final(200, "tool:5"),
            ],
        ),
    )
    assert all(
        row["financial_valid"] and row["full_mapping_status"] == "MAPPED"
        for row in (simple, repeated, revised)
    )
    assert len({row["full_class"] for row in (simple, repeated, revised)}) == 3
    assert repeated["full_signature"]["events"][3]["role"] == "redundant_target_recomputation"
    assert revised["full_signature"]["revision_edges"][0]["substantive_program_change"]


def test_unsupported_extra_intent_preserves_financial_valid_but_pending(mean):
    base = [controls.read("Revenue", index) for index in range(3)]
    script = [
        *base,
        controls.calculate("a+b", a="tool:1", b="tool:2"),
        controls.calculate("avg(a,b,c)", a="tool:1", b="tool:2", c="tool:3"),
        controls.final(200, "tool:5"),
    ]
    result = _assess(mean, _generate(mean, script))
    assert result["financial_valid"] and result["complete_trajectory_qualified"]
    assert result["full_mapping_status"] == "PENDING_REVIEW" and result["full_class"] is None


@pytest.mark.parametrize(
    "period_field",
    [
        {"actual_period": {"start": "2020-09-28", "end": "2021-09-26", "period_type": "duration"}},
        {"period": "2020-09-28/2021-09-26"},
    ],
)
def test_peak_complete_actual_interval_final_forms(period_field):
    case = next(
        case for case in controls.synthetic_cases() if case["name"] == "peak_array_selection"
    )
    script = copy.deepcopy(case["scripted"])
    del script[-1]["final"]["period_id"]
    script[-1]["final"].update(period_field)
    assert _assess(case["fixture"], _generate(case["fixture"], script))["financial_valid"]


def test_peak_equivalent_calculated_primary_candidates_are_accepted():
    fixture = controls.synthetic_fixture("other_financial")
    period = fixture["bundle"]["public"]["period_contract"]["periods"][1]["period_id"]
    script = [
        controls.read("Revenue", 0),
        controls.calculate("a*2/2", a="tool:1"),
        controls.read("Revenue", 1),
        controls.read("Revenue", 2),
        {"tool": "select_max", "arguments": {"result_ids": ["tool:2", "tool:3", "tool:4"]}},
        controls.read("NetIncomeLoss", 1),
        controls.final(9, "tool:6", selection_result_id="tool:5", period_id=period),
    ]
    assert _assess(fixture, _generate(fixture, script))["financial_valid"]


def test_peak_lookup_wrong_interval_fails_before_final():
    fixture = controls.synthetic_fixture("other_financial")
    script = [
        *[controls.read("Revenue", index) for index in range(3)],
        {"tool": "select_max", "arguments": {"result_ids": ["tool:1", "tool:2", "tool:3"]}},
        controls.read("NetIncomeLoss", 0),
        {
            "tool": "lookup_selected",
            "arguments": {"selection_result_id": "tool:4", "source_result_id": "tool:5"},
        },
    ]
    session = _generate(fixture, script)
    assert session["events"][-1]["tool_call"]["error"] == "tool.lookup_actual_period_mismatch"


def test_dual_growth_positive_previous_base_and_units():
    fixture = controls.synthetic_fixture("dual_sufficient", quantity="relative_change")
    computation = controls.calculate("(b-a)/a", a="tool:1", b="tool:2")
    computation["arguments"]["unit"] = "percent"
    answer = controls.final(75, "tool:3")
    answer["final"]["unit"] = "percent"
    script = [controls.read("GrossProfit", 0), controls.read("GrossProfit", 1), computation, answer]
    outcome = _assess(fixture, _generate(fixture, script))
    assert outcome["financial_valid"] and outcome["actual_method"] == "endpoint"
    computation["arguments"]["expression"] = "(b-a)/b"
    script[-1]["final"]["value"] = str(3000 / 70)
    assert not _assess(fixture, _generate(fixture, script))["financial_valid"]


@pytest.mark.parametrize("fiscal", [False, True])
def test_calendar_and_52_week_contracts_both_supported(fiscal):
    fixture = controls.synthetic_fixture(fiscal=fiscal)
    script = controls.synthetic_cases()[0]["scripted"]
    assert _assess(fixture, _generate(fixture, script))["financial_valid"]


def test_contract_period_change_is_not_silently_treated_as_same_target(mean):
    mean["bundle"]["public"]["period_contract"]["periods"][1]["start"] = "2021-01-01"
    _refresh(mean)
    result = _assess(mean, _generate(mean, controls.synthetic_cases()[0]["scripted"]))
    assert not result["financial_valid"] and result["reason"] == "assessment.period_identity"


@pytest.mark.parametrize(
    "family,quantity,expected_count",
    [
        ("composition_required", None, 4),
        ("other_financial", None, 6),
        ("dual_sufficient", None, 3),
        ("dual_sufficient", "relative_change", 3),
    ],
)
def test_source_bound_case_constructor_all_registered_structures(family, quantity, expected_count):
    fixture = controls.synthetic_fixture(family, quantity=quantity)
    cases = controls.source_bound_cases([fixture])
    assert len(cases) == expected_count
    assert all(case["source_bound"] for case in cases)
    report = controls.run_controls(cases)
    assert report["status"] == "PASS", [
        (row["name"], row["assessment"]["reason"])
        for row in report["controls"]
        if not row["passed"]
    ]
    assert report["source_bound_control_count"] == expected_count
    assert report["tokenizer_constructions"] == report["API_requests"] == 0


def test_source_bound_mean_counterexample_matches_amount_but_has_no_middle_support(mean):
    cases = controls.source_bound_cases([mean])
    case = next(case for case in cases if "omitted_middle" in case["name"])
    assert case["control_notes"]["answer_equal_to_correct"]
    result = controls.run_controls([case])["controls"][0]
    assert result["session"]["raw_final"]["value"] == "200"
    assert not result["assessment"]["financial_valid"]
    reads = [
        event["tool_call"]["result"]
        for event in result["session"]["events"]
        if event["tool_call"] and event["tool_call"]["tool"] == "read_source"
    ]
    assert len(reads) == 2
    assert all(row["record"]["start"] != "2020-09-28" for row in reads)


def test_source_bound_constructor_never_reselects_duplicate_fixture(mean):
    with pytest.raises(ValueError, match="unique_registered_fixture_tasks"):
        controls.source_bound_cases([mean, mean])


def test_raw_packages_retain_original_targets_and_failed_history_without_encoding(mean):
    report = controls.run_controls(controls.source_bound_cases([mean]))
    packages = controls.raw_packages(report)
    assert len(packages) == 4
    recovered = next(
        package
        for package in packages
        if package["full_mapping_status"] == "PENDING_REVIEW" and package["financial_valid"]
    )
    assert recovered["all_raw_turns_retained"][0]["raw_response"] == "not valid JSON"
    assert recovered["candidates"][0]["response_index"] == 1
    assert any(
        message["content"] == "not valid JSON"
        for message in recovered["candidates"][-1]["messages"]
    )
    for package in packages:
        assert package["complete_first_final_package"]
        assert not package["training_eligible"] and package["training_samples"] == 0
        for row in package["candidates"]:
            assert not row["training_eligible"] and not row["training_sample"]
            turn = package["all_raw_turns_retained"][row["response_index"]]
            assert row["messages"] == turn["input_messages"]
            assert row["target_text"] == turn["raw_response"]
            assert runtime.sha(row["target_text"].encode()) == row["target_raw_sha256"]


def test_raw_package_refuses_live_evaluation_samples(mean):
    script = controls.synthetic_cases()[0]["scripted"]
    iterator = iter(script)

    def provider(messages, context):
        return runtime.encode(next(iterator)).decode()

    session = runtime.generate(
        mean["messages"], mean["identity"], mean["sources"], provider=provider
    )
    result = _assess(mean, session)
    with pytest.raises(ValueError, match="scripted_packages_only"):
        controls.raw_package(session, result)


def _with_registered_equal_occurrence(fixture, mutation=None):
    payload = copy.deepcopy(fixture["sources"].payloads["snapshot"])
    raw = copy.deepcopy(payload["facts"]["us-gaap"]["Revenue"]["units"]["USD"][1])
    raw.update(
        filed="2024-02-01", accn="synthetic-later-annual-comparative", form="10-K/A", fy=2023
    )
    tag, unit = "Revenue", "USD"
    if mutation == "wrong_actual_period_same_end_year":
        raw.update(start="2021-01-01", end="2021-12-31")
    elif mutation == "wrong_concept_equal_value":
        tag = "NetIncomeLoss"
    elif mutation == "wrong_unit":
        unit = "shares"
    elif mutation == "wrong_amount":
        raw["val"] += 1
    elif mutation == "nonannual_filing":
        raw["form"] = "10-Q"
    records = payload["facts"]["us-gaap"][tag]["units"].setdefault(unit, [])
    pointer = f"/facts/us-gaap/{tag}/units/{unit}/{len(records)}"
    records.append(raw)
    fixture["sources"] = runtime.SnapshotSources.synthetic({"snapshot": payload})
    metadata = fixture["sources"].descriptors()[0]
    for native in fixture["native_bindings"].values():
        native["raw_sha256"] = metadata["complete_original_snapshot"]["sha256"]
    native = fixture["native_bindings"]["fact:revenue:1"]
    occurrence = {"pointer": pointer, "record": copy.deepcopy(raw)}
    if mutation == "wrong_snapshot_declaration":
        occurrence["raw_sha256"] = "0" * 64
    elif mutation == "forged_occurrence_record":
        occurrence["record"]["accn"] = "not-the-actual-raw-record"
    if mutation != "not_registered":
        native["all_equal_source_occurrences"] = [
            {"pointer": native["pointer"], "record": native["record"]},
            occurrence,
        ]
    fixture["bundle"]["public"]["source_document"] = metadata
    _refresh(fixture)
    alias = {
        "tool": "read_source",
        "arguments": {"source_id": "snapshot", "native_pointer": pointer, "unit": "million USD"},
    }
    return [
        controls.read("Revenue", 0),
        alias,
        controls.read("Revenue", 2),
        controls.calculate("avg(a,b,c)", a="tool:1", b="tool:2", c="tool:3"),
        controls.final(200, "tool:4"),
    ]


def test_registered_equal_annual_occurrence_is_valid_and_keeps_distinct_source_pointer(mean):
    script = _with_registered_equal_occurrence(mean)
    alias = _assess(mean, _generate(mean, script))
    selected_script = copy.deepcopy(script)
    selected_script[1] = controls.read("Revenue", 1)
    selected = _assess(mean, _generate(mean, selected_script))
    assert alias["financial_valid"] and alias["full_mapping_status"] == "MAPPED"
    assert (
        alias["full_signature"]["canonical_final_program"]
        == selected["full_signature"]["canonical_final_program"]
    )
    assert alias["full_class"] != selected["full_class"]
    assert alias["full_signature"]["events"][1]["source_locator"]["native_pointer"].endswith("/3")


@pytest.mark.parametrize(
    "mutation",
    [
        "wrong_actual_period_same_end_year",
        "wrong_concept_equal_value",
        "wrong_unit",
        "wrong_amount",
        "nonannual_filing",
        "wrong_snapshot_declaration",
        "forged_occurrence_record",
        "not_registered",
    ],
)
def test_equal_occurrence_alias_requires_all_registered_original_semantics(mean, mutation):
    script = _with_registered_equal_occurrence(mean, mutation)
    result = _assess(mean, _generate(mean, script))
    assert not result["financial_valid"] and not result["complete_trajectory_qualified"]
