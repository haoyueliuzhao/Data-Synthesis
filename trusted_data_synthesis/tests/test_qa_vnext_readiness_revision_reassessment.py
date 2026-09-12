"""New revision controls use the actual factory's relative_certificate producer."""

import copy
import json
from fractions import Fraction

import pytest

from trusted_synthesis.experiments.finance_qa_vnext_eval_readiness import (
    assessment,
    controls,
    runtime,
)
from trusted_synthesis.experiments.finance_qa_vnext_model_execution.models import (
    record as token_record,
)
from trusted_synthesis.experiments.finance_qa_vnext_readiness_revision import (
    reassessment as revision,
)
from trusted_synthesis.experiments.finance_qa_vnext_task_build import relations
from trusted_synthesis.experiments.finance_qa_vnext_task_build.archive import (
    record,
    sha,
    write_json,
)


def producer_fixture():
    fixture = controls.synthetic_fixture("dual_sufficient", quantity="relative_change")
    base = controls.synthetic_fixture("dual_sufficient")["bundle"]["private"][
        "relation_certificate"
    ]
    facts = {}
    for identifier, native in fixture["native_bindings"].items():
        raw = native["record"]
        facts[identifier] = {
            "fact_id": identifier,
            "entity_id": native["entity_id"],
            "metric_id": native["metric_id"],
            "period_start": raw.get("start"),
            "period_end": raw["end"],
            "normalized_value": str(Fraction(raw["val"], 1000000)),
            "normalized_unit": "million USD",
            "normalized_currency": "USD",
            "fiscal_year": int(raw["end"][:4]),
            "frequency": "annual",
        }
    witnesses = [
        relations.witness(
            witness["operator_dag"],
            witness["input_bindings"],
            list(facts.values()),
            witness["basis"],
        )
        for witness in base["witnesses"]
    ]
    base = record(
        "financial_relation_certificate",
        family="annual_flow",
        complete=True,
        leaf_fact_ids=base["leaf_fact_ids"],
        public_fact_ids=base["leaf_fact_ids"],
        witnesses=witnesses,
        previous_component_fact_ids=base["previous_component_fact_ids"],
        previous_component_coefficients=base["previous_component_coefficients"],
    )
    produced = relations.relative_certificate(base, facts["fact:gross_profit:0"], facts)
    fixture["bundle"]["private"]["relation_certificate"] = produced
    fixture["bundle"].update(_rehash(fixture["bundle"]))
    return fixture


def reassess(fixture, script):
    session = runtime.generate(
        fixture["messages"], fixture["identity"], fixture["sources"], scripted=script
    )
    result = assessment.assess_session(
        session, fixture["bundle"], fixture["native_bindings"], fixture["sources"]
    )
    return session, result


def _rehash(item):
    return {
        **item,
        "id": item["id"].split(":", 1)[0]
        + ":"
        + runtime.sha(runtime.encode({key: value for key, value in item.items() if key != "id"})),
    }


def _rehash_wrapper(fixture):
    certificate = fixture["bundle"]["private"]["relation_certificate"]
    for witness in certificate.get("witnesses", []):
        witness.update(_rehash(witness))
    base = certificate.get("base_relation_certificate")
    if isinstance(base, dict) and "id" in base:
        for witness in base.get("witnesses", []):
            witness.update(_rehash(witness))
        base.update(_rehash(base))
    certificate.update(_rehash(certificate))


@pytest.mark.parametrize("basis", ["endpoint", "movement"])
def test_real_factory_growth_wrapper_retains_outer_rate_target(basis):
    fixture = producer_fixture()
    certificate = fixture["bundle"]["private"]["relation_certificate"]
    assert certificate["schema_version"].endswith(".relative_quantity_certificate")
    assert "complete" not in certificate and certificate["base_relation_certificate"]["complete"]
    script = controls._dual_script(
        fixture, next(w for w in certificate["witnesses"] if w["basis"] == basis)
    )
    _, result = reassess(fixture, script)
    assert result["financial_valid"] and result["full_mapping_status"] == "MAPPED", result
    assert result["actual_method"] == basis
    assert script[-1]["final"]["unit"] == "percent" and Fraction(script[-1]["final"]["value"]) == 75
    assert Fraction(script[-1]["final"]["value"]) != 30


@pytest.mark.parametrize(
    "mutation",
    [
        "missing_base",
        "incomplete_base",
        "unknown_wrapper",
        "recursive_unknown_base",
        "wrong_target_quantity",
        "wrong_outer_quantity",
        "wrong_unit",
        "wrong_period",
        "wrong_source",
        "changed_leaf_set",
        "changed_original_binding",
        "wrong_denominator",
        "wrong_direction",
        "lost_percentage_operator",
    ],
)
def test_real_factory_wrapper_damage_is_not_admitted_by_nested_complete(mutation):
    fixture = producer_fixture()
    certificate = fixture["bundle"]["private"]["relation_certificate"]
    script = controls._dual_script(fixture, certificate["witnesses"][0])
    if mutation == "missing_base":
        del certificate["base_relation_certificate"]
    elif mutation == "incomplete_base":
        certificate["base_relation_certificate"]["complete"] = False
    elif mutation == "unknown_wrapper":
        certificate["schema_version"] = "finance_qa_vnext_task_build.v1.unregistered_wrapper"
        certificate["complete"] = True
    elif mutation == "recursive_unknown_base":
        certificate["base_relation_certificate"] = record(
            "unregistered_wrapper",
            complete=True,
            base_relation_certificate=certificate["base_relation_certificate"],
        )
    elif mutation == "wrong_target_quantity":
        fixture["bundle"]["private"]["canonical_target"]["quantity"] = "difference"
    elif mutation == "wrong_outer_quantity":
        certificate["quantity"] = "difference"
    elif mutation == "wrong_unit":
        fixture["bundle"]["public"]["quantity_contract"]["unit"] = "million USD"
        fixture["messages"] = [
            {"role": "user", "content": runtime.encode(fixture["bundle"]["public"]).decode()}
        ]
        fixture["identity"]["public_messages_sha256"] = runtime.sha(
            runtime.encode(fixture["messages"])
        )
    elif mutation == "wrong_period":
        fixture["native_bindings"]["fact:gross_profit:0"]["record"]["start"] = "2020-01-01"
    elif mutation == "wrong_source":
        fixture["native_bindings"]["fact:gross_profit:0"]["source_cluster"] = "cik:0000009999"
    elif mutation == "changed_leaf_set":
        certificate["leaf_fact_ids"] = certificate["leaf_fact_ids"][1:]
    elif mutation == "changed_original_binding":
        certificate["witnesses"][0]["input_bindings"]["previous"] = "fact:gross_profit:1"
    elif mutation == "wrong_denominator":
        certificate["witnesses"][0]["input_bindings"]["positive_base"] = "fact:gross_profit:1"
    elif mutation == "wrong_direction":
        certificate["witnesses"][0]["operator_dag"]["operators"][0]["inputs"].reverse()
    else:
        certificate["witnesses"][0]["operator_dag"]["output_step"] = "change"
    _rehash_wrapper(fixture)
    _, result = reassess(fixture, script)
    assert not result["financial_valid"] and result["reason"], result


@pytest.mark.parametrize("base", [0, -1])
def test_relative_consumer_requires_actual_strictly_positive_earlier_base(base):
    fixture = producer_fixture()
    certificate = fixture["bundle"]["private"]["relation_certificate"]
    script = controls._dual_script(fixture, certificate["witnesses"][0])
    fixture["native_bindings"]["fact:gross_profit:0"]["record"]["val"] = base
    _, result = reassess(fixture, script)
    assert not result["financial_valid"]
    assert result["reason"] == "assessment.relative_strictly_positive_previous"


@pytest.mark.parametrize(
    "expression,unit,value",
    [
        ("(b-a)/b", "percent", "3000/70"),
        ("(a-b)/a", "percent", "-75"),
        ("b-a", "million USD", "30"),
        ("(b-a)/a*100", "percent", "7500"),
    ],
)
def test_real_factory_growth_wrong_executed_base_direction_or_units_still_fail(
    expression, unit, value
):
    fixture = producer_fixture()
    computation = controls.calculate(expression, a="tool:1", b="tool:2")
    computation["arguments"]["unit"] = unit
    final = controls.final(value, "tool:3")
    final["final"]["unit"] = unit
    script = [controls.read("GrossProfit", 0), controls.read("GrossProfit", 1), computation, final]
    _, result = reassess(fixture, script)
    assert not result["financial_valid"]


def typed_fixture(family="composition_required"):
    fixture = controls.synthetic_fixture(family)
    certificate = fixture["bundle"]["private"]["relation_certificate"]
    kind = {
        "composition_required": "panel_composition_certificate",
        "other_financial": "panel_other_financial_certificate",
        "dual_sufficient": "financial_relation_certificate",
    }[family]
    fixture["bundle"]["private"]["relation_certificate"] = record(kind, **certificate)
    fixture["bundle"].update(_rehash(fixture["bundle"]))
    return fixture


@pytest.mark.parametrize("family", ["dual_sufficient", "composition_required", "other_financial"])
def test_nonrelative_production_type_path_remains_supported(family):
    fixture = typed_fixture(family)
    case = controls.source_bound_cases([fixture])[0]
    _, result = reassess(fixture, case["scripted"])
    assert result["financial_valid"], result
    fixture["bundle"]["private"]["relation_certificate"].pop("schema_version")
    _, rejected = reassess(fixture, case["scripted"])
    assert not rejected["financial_valid"]
    assert rejected["reason"] == "assessment.unregistered_certificate_type"


def test_replacing_relative_outer_with_complete_base_does_not_authorize_difference_target():
    fixture = producer_fixture()
    certificate = fixture["bundle"]["private"]["relation_certificate"]
    script = controls._dual_script(fixture, certificate["witnesses"][0])
    fixture["bundle"]["private"]["relation_certificate"] = certificate["base_relation_certificate"]
    _, result = reassess(fixture, script)
    assert not result["financial_valid"]
    assert result["reason"] == "assessment.relative_registered_wrapper_required"


def test_actual_cash_factory_wrapper_without_reconstructed_base_keeps_percent_target():
    from test_qa_vnext_eval_readiness_panels import cash_fixture

    from trusted_synthesis.experiments.finance_qa_vnext_eval_readiness import panel_rules, periods

    facts, bindings, usage = cash_fixture()
    for identifier, amount in (("previous", 120), ("current", 150)):
        facts[identifier]["normalized_value"] = str(amount)
        bindings[identifier]["record"]["val"] = amount * 1000000
    lookup = {
        (fact["entity_id"], fact["metric_id"], fact["period_start"], fact["period_end"]): fact
        for fact in facts.values()
    }
    base = panel_rules.cash_certificate(
        facts["previous"], facts["current"], lookup, bindings, usage, "dev"
    )
    wrapper = relations.relative_certificate(base, facts["previous"], facts)
    task, target = relations.target_identity(
        facts["previous"], facts["current"], bindings, "relative_change"
    )
    item = {"task_id": task, "target": target, "match": {"fact_ids": ["previous", "current"]}}
    contract = periods.build_contract(item, facts, bindings)
    bundle = {
        "family": "dual_sufficient",
        "private": {"canonical_target": target, "relation_certificate": wrapper},
        "public": {"quantity_contract": {"unit": "percent"}, "period_contract": contract},
    }
    assert "previous_component_fact_ids" not in base
    assert wrapper["family"] == "stock_rollforward"
    assert {Fraction(witness["output"]["value"]) for witness in wrapper["witnesses"]} == {25}
    assert assessment._consume_certificate(bundle, bindings) is wrapper


def prior_control(fixture, name, script, *, was_wrapper_failure=False):
    session, current = reassess(fixture, script)
    previous = {
        key: value
        for key, value in current.items()
        if key
        not in {
            "id",
            "schema_version",
            "certificate_consumer_revision",
            "support_assessment_entered",
        }
    }
    if was_wrapper_failure:
        previous.update(
            financial_valid=False,
            complete_trajectory_qualified=False,
            support_status="UNDETERMINED",
            actual_method="UNDETERMINED",
            full_mapping_status="PENDING_REVIEW",
            full_class=None,
            reason=revision.WRAPPER_GATE,
        )
        for key in (
            "full_signature",
            "full_mapping_pending_reasons",
            "support_result_ids",
            "selected_actual_period",
        ):
            previous.pop(key, None)
    previous = runtime.record("evaluation_assessment", **previous)
    row = {
        "name": name,
        "session": session,
        "assessment": previous,
        "expected_financial_valid": current["financial_valid"],
        "expected_full_mapping_status": current["full_mapping_status"],
        "passed": not was_wrapper_failure,
    }
    return row


def prior_report(rows):
    return runtime.record(
        "new_evaluation_controls",
        controls=rows,
        control_count=len(rows),
        passed_count=sum(row["passed"] for row in rows),
    )


def test_saved_control_loop_replays_once_and_keeps_original_expectations(monkeypatch):
    fixture = producer_fixture()
    certificate = fixture["bundle"]["private"]["relation_certificate"]
    old = prior_control(
        fixture,
        "old-growth",
        controls._dual_script(fixture, certificate["witnesses"][0]),
        was_wrapper_failure=True,
    )
    calls = []
    actual = assessment.assess_session

    def counted(*args):
        calls.append(args[0]["id"])
        return actual(*args)

    monkeypatch.setattr(assessment, "assess_session", counted)
    unchanged = copy.deepcopy(old)
    rows, packages, regressions = revision.saved_control_reassessments(
        prior_report([old]), lambda _: fixture
    )
    assert calls == [old["session"]["id"]]
    assert old == unchanged
    assert rows[0]["passed"] and rows[0]["old_wrapper_failure_reached_support_assessment"]
    assert rows[0]["original_assessment_id"] != rows[0]["reassessment"]["id"]
    assert len(packages) == 1 and not any(regressions.values())
    assert not packages[0]["training_eligible"]


def test_saved_control_exception_is_retained_without_retry(monkeypatch):
    fixture = producer_fixture()
    old = prior_control(
        fixture,
        "old-growth",
        controls._dual_script(
            fixture, fixture["bundle"]["private"]["relation_certificate"]["witnesses"][0]
        ),
        was_wrapper_failure=True,
    )
    calls = []

    def failed(*args):
        calls.append(args[0]["id"])
        raise ValueError("synthetic replay failure")

    monkeypatch.setattr(assessment, "assess_session", failed)
    rows, packages, regressions = revision.saved_control_reassessments(
        prior_report([old]), lambda _: fixture
    )
    assert len(calls) == 1 and not packages
    assert rows[0]["exception"] == "ValueError: synthetic replay failure"
    assert not rows[0]["old_wrapper_failure_reached_support_assessment"]
    assert regressions["reassessment_exceptions"]


def token_fixture(packages):
    eligible = [package for package in packages if package["financial_valid"]]
    rows = [
        {
            "package_id": package["id"],
            "candidate_id": candidate["id"],
            "representation": token_record(
                "token_representation",
                row_id=candidate["id"],
                session_id=package["session_id"],
                qualification_id=package["assessment_id"],
                target_raw_sha256=candidate["target_raw_sha256"],
                maximum_sequence_length=24576,
                truncated=False,
                **{
                    "consumable_token_representation": True,
                    "sequence_length": 10,
                    "target_token_count": 2,
                    "input_ids": [1] * 10,
                    "labels": [-100] * 8 + [1, 1],
                },
            ),
        }
        for package in eligible
        for candidate in package["candidates"]
    ]
    return record(
        "new_eval_token_controls",
        status="PASS_SCRIPTED_REPRESENTATION_ONLY"
        if eligible
        else "NO_FINANCIAL_COMPLETE_PACKAGES",
        maximum_sequence_length=24576,
        truncation=False,
        financial_complete_packages=len(eligible),
        encoded_rows=len(rows),
        rows=rows,
        target_tokens=2 * len(rows),
        sequence_tokens=10 * len(rows),
        tokenizer_constructions=int(bool(eligible)),
        failures=[],
    )


def test_prior_arrays_are_inherited_without_encoder_or_tokenizer(monkeypatch):
    fixture = typed_fixture()
    case = controls.source_bound_cases([fixture])[0]
    old = prior_control(fixture, "old-mean", case["scripted"])
    report = prior_report([old])
    packages = controls.raw_packages(report)
    tokens = token_fixture(packages)
    before = copy.deepcopy(tokens)

    def forbidden(*args, **kwargs):
        raise AssertionError("inherited arrays must never re-encode")

    monkeypatch.setattr(revision.token_controls, "encode_original_candidate", forbidden)
    monkeypatch.setattr(revision.token_controls, "load_local_tokenizer", forbidden)
    inherited = revision.inherited_token_evidence(packages, tokens, report["controls"])
    assert inherited["verified"] and inherited["packages"] == 1 and inherited["rows"] == 6
    assert inherited["tokenizer_constructions"] == inherited["old_rows_reencoded"] == 0
    assert tokens == before


@pytest.mark.parametrize(
    "mutation", ["missing_row", "foreign_package", "overflow", "wrong_target_text"]
)
def test_inherited_arrays_require_exact_old_package_and_row_identities(mutation):
    fixture = typed_fixture()
    old = prior_control(fixture, "old-mean", controls.source_bound_cases([fixture])[0]["scripted"])
    report = prior_report([old])
    packages = controls.raw_packages(report)
    tokens = token_fixture(packages)
    if mutation == "missing_row":
        tokens["rows"].pop()
    elif mutation == "foreign_package":
        tokens["rows"][0]["package_id"] = "foreign"
    elif mutation == "overflow":
        tokens["rows"][0]["representation"]["sequence_length"] = 24577
    else:
        packages[0]["candidates"][0]["target_text"] = "changed"
    tokens.update(_rehash(tokens))
    with pytest.raises(ValueError):
        revision.inherited_token_evidence(packages, tokens, report["controls"])


def test_actual_frozen_format_pending_class_is_not_forced_to_map():
    fixture = typed_fixture()
    case = next(
        case for case in controls.source_bound_cases([fixture]) if "format_recovery" in case["name"]
    )
    old = prior_control(fixture, "old-mean-recovery", case["scripted"])
    rows, packages, regressions = revision.saved_control_reassessments(
        prior_report([old]), lambda _: fixture
    )
    assert rows[0]["passed"] and rows[0]["reassessment"]["financial_valid"]
    assert rows[0]["reassessment"]["full_mapping_status"] == "PENDING_REVIEW"
    assert rows[0]["reassessment"]["full_class"] is None
    assert not packages and not any(regressions.values())


def synthetic_parent(tmp_path):
    """A new synthetic seventy-row archive, never the original production scripts."""
    directory = tmp_path / "synthetic_old"
    frozen = record("eval_readiness_freeze", git_commit="synthetic-test-only")
    mean, growth = typed_fixture(), producer_fixture()
    for fixture in (mean, growth):
        fixture["identity"]["parent_manifest_id"] = frozen["id"]
    assert mean["sources"].payloads == growth["sources"].payloads
    write_json(tmp_path / "synthetic/snapshot.json", mean["sources"].payloads["snapshot"])
    rows = []
    for index in range(39):
        script = controls._Script(mean)
        script.call(
            "query_source", {"source_id": "snapshot", "concept": "us-gaap:Revenue", "offset": index}
        )
        if index >= 20:
            script.call("list_concepts", {"source_id": "snapshot", "offset": index})
        references = {name: script.read(f"fact:revenue:{i}") for i, name in enumerate("abc")}
        result = script.calculate("avg(a,b,c)", references)
        responses = script.finish(200, result)
        if index < 4:
            responses.insert(0, "retained synthetic formatting failure")
        rows.append(prior_control(mean, f"old_mean:{index}", responses))
    for index in range(15):
        certificate = growth["bundle"]["private"]["relation_certificate"]
        witness = next(
            w
            for w in certificate["witnesses"]
            if w["basis"] == ("movement" if index % 3 == 2 else "endpoint")
        )
        script = controls._dual_script(growth, witness)
        script[0]["arguments"]["offset"] = index
        rows.append(prior_control(growth, f"old_growth:{index}", script, was_wrapper_failure=True))
    for index in range(16):
        script = controls._Script(mean)
        script.call("query_source", {"source_id": "snapshot", "offset": 200 + index})
        result = script.calculate(
            "avg(a,c)", {"a": script.read("fact:revenue:0"), "c": script.read("fact:revenue:2")}
        )
        rows.append(prior_control(mean, f"old_negative:{index}", script.finish(200, result)))
    report = prior_report(rows)
    packages = controls.raw_packages(report)
    tokens = token_fixture(packages)
    assert report["control_count"] == 70 and report["passed_count"] == 55
    assert tokens["financial_complete_packages"] == 39 and len(tokens["rows"]) == 253
    write_json(directory / "stage_freeze.json", frozen)
    write_json(directory / "controls/source_bound_report.json", report)
    write_json(directory / "controls/original_packages.json", packages)
    write_json(directory / "controls/token_report.json", tokens)
    write_json(
        directory / "controls/fixture_selection.json",
        record(
            "real_eval_fixture_selection",
            rows=[
                {
                    "task_id": fixture["identity"]["task_id"],
                    "cell": ["dev", fixture["identity"]["family"]],
                }
                for fixture in (mean, growth)
            ],
        ),
    )
    entries = []
    for fixture in (mean, growth):
        task = fixture["identity"]["task_id"]
        public_path, bundle_path = (
            f"tasks/{task}/public_messages.json",
            f"tasks/{task}/task_bundle.json",
        )
        write_json(directory / "panels/dev" / public_path, fixture["messages"])
        write_json(directory / "panels/dev" / bundle_path, fixture["bundle"])
        entries.append(
            {
                **{
                    key: value
                    for key, value in fixture["identity"].items()
                    if key != "parent_manifest_id"
                },
                "public_path": public_path,
                "path": bundle_path,
                "bundle_id": fixture["bundle"]["id"],
            }
        )
    write_json(
        directory / "panels/dev/catalog.json",
        record("actual_period_evaluation_catalog", tasks=entries),
    )
    write_json(directory / "panels/dev/native_bindings.json", mean["native_bindings"])
    manifest = record(
        "manifest",
        members=[
            {
                "path": str(path.relative_to(directory)),
                "sha256": sha(path),
                "bytes": path.stat().st_size,
            }
            for path in sorted(directory.rglob("*"))
            if path.is_file()
        ],
    )
    write_json(directory / "manifest.json", manifest)
    return directory, manifest, report


def test_complete_revision_run_uses_only_synthetic_archive_and_encodes_only_new_packages(
    tmp_path, monkeypatch
):
    directory, manifest, original = synthetic_parent(tmp_path)
    old_hashes = {row["path"]: row["sha256"] for row in manifest["members"]}
    actual = assessment.assess_session
    replays, encoded = [], []

    def counted(*args):
        replays.append(args[0]["id"])
        return actual(*args)

    def materializer(packages, root):
        encoded.extend(package["session_id"] for package in packages)
        assert root == tmp_path
        assert len(packages) == 15
        return token_fixture(packages)

    monkeypatch.setattr(assessment, "assess_session", counted)
    output = tmp_path / "synthetic_revision/controls"
    result = revision.run(
        tmp_path,
        output,
        directory.relative_to(tmp_path),
        expected_parent_manifest_id=manifest["id"],
        freeze_id="new-synthetic-freeze",
        materializer=materializer,
    )
    assert result["status"] == "PASS", result
    assert result["control_count"] == result["passed_count"] == 70
    assert (
        result["financial_valid_count"] == 54
        and result["prior_15_reached_support_assessment"] == 15
    )
    assert result["full_mapping_counts"] == {"MAPPED": 50, "PENDING_REVIEW": 20}
    assert len(replays) == len(set(replays)) == 70
    assert set(replays) == {row["session"]["id"] for row in original["controls"]}
    old_valid = {
        row["session"]["id"] for row in original["controls"] if row["assessment"]["financial_valid"]
    }
    assert old_valid.isdisjoint(encoded)
    assert result["inherited_CPU"]["rows"] == 253 and result["inherited_CPU"]["packages"] == 39
    assert result["incremental_CPU"]["rows"] == 105
    assert result["token_combined"]["all_current_qualified_covered"]
    assert result["token_combined"]["old_rows_reencoded"] == 0
    assert json.loads((output / "report.json").read_text()) == result
    for key in ("reassessments_path", "newly_qualified_packages_path"):
        assert not (tmp_path / result[key]).is_relative_to(directory)
        assessment._body_valid(json.loads((tmp_path / result[key]).read_text()))
    assert all(sha(directory / relative) == expected for relative, expected in old_hashes.items())
    with pytest.raises(ValueError, match="new_frozen_control_output_only"):
        revision.run(
            tmp_path,
            output,
            directory.relative_to(tmp_path),
            expected_parent_manifest_id=manifest["id"],
            freeze_id="new-synthetic-freeze",
            materializer=materializer,
        )
