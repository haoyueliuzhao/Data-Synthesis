"""Synthetic fixed-registration metadata only; no live archive or model reads."""

import copy
from collections import Counter

import pytest

from trusted_synthesis.experiments.finance_qa_vnext_eval_readiness.training_runtime import record
from trusted_synthesis.experiments.finance_qa_vnext_movement_support import funnel
from trusted_synthesis.experiments.finance_qa_vnext_movement_support import protocol as p


def reseal(value, kind):
    return record(
        kind, **{key: item for key, item in value.items() if key not in {"id", "schema_version"}}
    )


@pytest.fixture
def inputs():
    tasks = [
        {"task_id": "dual", "family": "annual_flow"},
        {"task_id": "control", "family": "control"},
    ]
    results, qualifications, inventory = [], {}, []
    for task in tasks:
        control = task["family"] == "control"
        for pool in ("A", "B"):
            for basis in ("control",) if control else ("endpoint", "movement"):
                for replicate in range(24 if control else 32):
                    sid = ":".join([task["task_id"], pool, basis, str(replicate)])
                    mapped = replicate < (12 if control else 10)
                    supported = mapped or (not control and replicate < 20)
                    first = control or replicate != 31
                    quantity = (
                        "PASS"
                        if replicate < (24 if control else 30)
                        else "FAIL"
                        if first
                        else "UNDETERMINED"
                    )
                    method = ("control" if control else "endpoint") if supported else "UNDETERMINED"
                    terminal = "first_final" if first else "response_budget_exhausted"
                    fields = dict(
                        session_id="session:" + sid,
                        task_id=task["task_id"],
                        requested_basis=basis,
                        terminal=terminal,
                        first_final_index=2 if first else None,
                        quantity_status=quantity,
                        support_status="PASS" if supported else "UNDETERMINED",
                        actual_method=method,
                        financial_valid=supported,
                        full_mapping_status="MAPPED" if mapped else "PENDING_REVIEW",
                        representation_eligible=mapped,
                        authentic_Teacher_origin_verified=True,
                        reason=None
                        if supported
                        else "no_final"
                        if not first
                        else "unresolved_support",
                    )
                    if supported:
                        fields["full_mapping_pending_reasons"] = (
                            [] if mapped else ["unresolved_auxiliary", "unresolved_auxiliary"]
                        )
                    qualification = record("training_assessment", **fields)
                    qualifications[qualification["id"]] = qualification
                    reg = dict(
                        session_id=sid,
                        task_id=task["task_id"],
                        pool=pool,
                        basis=basis,
                        replicate=replicate,
                        state="registered",
                        terminal=None,
                    )
                    results.append(
                        record(
                            "collected_original_session",
                            registered_session=reg,
                            session_id=qualification["session_id"],
                            qualification_id=qualification["id"],
                            qualification_path=p.COLLECTION
                            + "/sessions/"
                            + sid
                            + "/qualification.json",
                            terminal=terminal,
                            global_fatal=False,
                            **{
                                key: fields[key]
                                for key in [
                                    "actual_method",
                                    "financial_valid",
                                    "full_mapping_status",
                                    "representation_eligible",
                                ]
                            },
                        )
                    )
                    if mapped:
                        inventory.append(
                            dict(
                                id="encoded:" + sid,
                                registered_session_id=sid,
                                task_id=task["task_id"],
                                group="control" if control else "annual_flow_components",
                                pool=pool,
                                actual_method=method,
                                consumable=control or replicate != 9,
                            )
                        )
    report = record(
        "fixed_collection_report",
        status="COMPLETE_FIXED_COLLECTION",
        collection_complete=True,
        registered_session_count=len(results),
        recorded_session_count=len(results),
        finished_session_count=len(results),
        source_task_order=tasks,
        financially_valid_sessions=sum(row["financial_valid"] for row in results),
        representation_eligible_sessions=sum(row["representation_eligible"] for row in results),
    )
    counts = Counter(
        (row["task_id"], row["pool"], row["actual_method"])
        for row in inventory
        if row["consumable"]
    )
    readiness = []
    for task in tasks:
        methods = ("control",) if task["family"] == "control" else ("endpoint", "movement")
        by_pool = {
            pool: {method: counts[task["task_id"], pool, method] for method in methods}
            for pool in ("A", "B")
        }
        readiness.append(
            dict(
                task_id=task["task_id"],
                group=funnel.FAMILY_TO_SCALE_GROUP[task["family"]],
                counts_by_pool_actual_method=by_pool,
                common_AB_ready=all(
                    count >= 10 for items in by_pool.values() for count in items.values()
                ),
            )
        )
    manifest = record(
        "fixed_AB_material_manifest",
        collection_id=report["id"],
        collection_complete=True,
        all_original_registered_denominators=len(results),
        source_task_order=[row["task_id"] for row in tasks],
        common_AB_readiness=readiness,
        packages=[],
        population_selection={
            "ready_counts": {
                "annual_flow_components": 0,
                "stock_rollforward": 0,
                "defined_metric_reconstruction": 0,
                "control": 1,
            },
            "selected": [],
        },
    )
    return dict(
        collection_report=report,
        session_results=results,
        qualifications=qualifications,
        material_manifest=manifest,
        encoded_inventory=inventory,
        expected_session_count=len(results),
    )


def test_original_quantity_support_mapping_and_encoding_are_distinct_fixed_denominator_stages(
    inputs,
):
    before = p.encode(inputs)
    result = funnel.aggregate(**inputs)
    assert p.encode(inputs) == before
    assert result["totals"]["registered_denominator"] == 176
    assert result["totals"]["actual_method_at_original_qualification"] == {
        "UNDETERMINED": 72,
        "control": 24,
        "endpoint": 80,
    }
    assert result["totals"]["financial_false_by_quantity_status"]["PASS"] == 64
    assert result["totals"]["stage_marginal_counts"]["quantity_PASS"] == 168
    assert result["totals"]["stage_marginal_counts"]["support_PASS"] == 104
    assert result["totals"]["encoding_attempted"] == 64
    assert result["totals"]["token_nonconsumable"] == 4
    assert result["totals"]["stage_marginal_counts"]["token_consumable"] == 60
    assert result["totals"]["pending_reason_session_histogram"] == {"unresolved_auxiliary": 40}
    assert len(result["all_session_rows"]) == 176 and len(result["cohort_rows"]) == 6
    assert sum(row["registered_denominator"] for row in result["cohort_rows"]) == 176
    assert result["selected_task_count"] == result["selected_package_descriptor_count"] == 0
    assert result["is_original_24640_session_cohort"] is False


def test_movement_guidance_is_not_reclassified_as_actual_movement(inputs):
    result = funnel.aggregate(**inputs)
    requested = next(
        row for row in result["requested_basis_rows"] if row["requested_basis"] == "movement"
    )
    assert requested["registered_denominator"] == 64
    assert requested["actual_method_at_original_qualification"] == {
        "UNDETERMINED": 24,
        "endpoint": 40,
    }
    assert requested["pending_reason_session_histogram"] == {"unresolved_auxiliary": 20}
    assert result["original_actual_method_counts_precede_old_fine_mapping"] is True
    assert result["UNDETERMINED_is_not_proof_of_zero_movement_generation"] is True


@pytest.mark.parametrize(
    "change",
    [
        "prefix",
        "duplicate_session",
        "missing_qualification",
        "same_ID_qualification_tamper",
        "wrong_summary",
        "missing_encoding",
        "duplicate_encoding",
        "wrong_encoding_method",
        "wrong_common_count",
        "wrong_requested_basis",
        "bad_metadata",
    ],
)
def test_missing_changed_or_misjoined_inputs_are_rejected_not_dropped(inputs, change):
    if change == "prefix":
        inputs["session_results"].pop()
    elif change == "duplicate_session":
        inputs["session_results"][1] = copy.deepcopy(inputs["session_results"][0])
    elif change == "missing_qualification":
        inputs["qualifications"].pop(next(iter(inputs["qualifications"])))
    elif change == "same_ID_qualification_tamper":
        next(iter(inputs["qualifications"].values()))["actual_method"] = "movement"
    elif change == "wrong_summary":
        inputs["collection_report"]["financially_valid_sessions"] += 1
        inputs["collection_report"] = reseal(inputs["collection_report"], "fixed_collection_report")
    elif change == "missing_encoding":
        inputs["encoded_inventory"].pop()
    elif change == "duplicate_encoding":
        inputs["encoded_inventory"].append(copy.deepcopy(inputs["encoded_inventory"][0]))
    elif change == "wrong_encoding_method":
        inputs["encoded_inventory"][0]["actual_method"] = "movement"
    elif change == "wrong_common_count":
        inputs["material_manifest"]["common_AB_readiness"][0]["counts_by_pool_actual_method"]["A"][
            "movement"
        ] = 1
        inputs["material_manifest"] = reseal(
            inputs["material_manifest"], "fixed_AB_material_manifest"
        )
    elif change == "wrong_requested_basis":
        item = inputs["session_results"][0]
        item["registered_session"]["basis"] = "movement"
        inputs["session_results"][0] = reseal(item, "collected_original_session")
    else:
        inputs["task_metadata"] = {
            "dual": {"family": "control", "group": "control"},
            "control": {"family": "control", "group": "control"},
        }
    with pytest.raises(ValueError):
        funnel.aggregate(**inputs)


def test_default_count_never_accepts_a_small_synthetic_cohort(inputs):
    inputs.pop("expected_session_count")
    with pytest.raises(ValueError, match="fixed_denominator"):
        funnel.aggregate(**inputs)


def test_original_hybrid_undetermined_enum_is_retained_not_a_determined_method(inputs):
    result = inputs["session_results"][10]
    old_id = result["qualification_id"]
    qualification = inputs["qualifications"].pop(old_id)
    qualification["actual_method"] = "HYBRID_UNDETERMINED"
    qualification = reseal(qualification, "training_assessment")
    inputs["qualifications"][qualification["id"]] = qualification
    result["qualification_id"] = qualification["id"]
    result["actual_method"] = "HYBRID_UNDETERMINED"
    inputs["session_results"][10] = reseal(result, "collected_original_session")
    actual = funnel.aggregate(**inputs)
    assert actual["totals"]["actual_method_at_original_qualification"]["HYBRID_UNDETERMINED"] == 1
    assert actual["totals"]["stage_marginal_counts"]["actual_method_determined"] == 103


class MetadataParent:
    def __init__(self, relative, identity, values):
        self.relative, self.manifest, self.values = relative, {"id": identity}, values
        self.reads = []
        self.checks = 0

    def read(self, name):
        assert name in self.values, "attempted an unregistered or raw/Student read"
        self.reads.append(name)
        return copy.deepcopy(self.values[name])

    def check_manifest(self):
        self.checks += 1

    def verify_all(self):
        pytest.fail("metadata diagnostic must not run full parent sweep")


def parents(inputs):
    values = {
        "report.json": inputs["collection_report"],
        "session_results.json": inputs["session_results"],
    }
    for result in inputs["session_results"]:
        values[result["qualification_path"][len(p.COLLECTION) + 1 :]] = inputs["qualifications"][
            result["qualification_id"]
        ]
    return (
        MetadataParent(p.COLLECTION, p.COLLECTION_MANIFEST, values),
        MetadataParent(
            p.MATERIALS,
            p.MATERIAL_MANIFEST,
            {
                "material_manifest.json": inputs["material_manifest"],
                "encoded_package_inventory.json": inputs["encoded_inventory"],
            },
        ),
    )


def test_reader_only_reads_registered_metadata_and_never_full_verifies(inputs):
    first, second = parents(inputs)
    actual = funnel.read_inputs(first, second)
    assert actual == {
        key: value for key, value in inputs.items() if key != "expected_session_count"
    }
    assert len(first.reads) == 178 and len(second.reads) == 2
    assert first.checks == second.checks == 1
    assert not any(
        name.endswith("session.json") or name.endswith("encoded_package.json")
        for name in first.reads + second.reads
    )


@pytest.mark.parametrize("suffix", ["../qualification.json", "session.json", "raw_response.json"])
def test_reader_rejects_raw_or_parent_traversal_references_before_open(inputs, suffix):
    item = inputs["session_results"][0]
    item["qualification_path"] = (
        p.COLLECTION + "/sessions/" + item["registered_session"]["session_id"] + "/" + suffix
    )
    inputs["session_results"][0] = reseal(item, "collected_original_session")
    first, second = parents(inputs)
    with pytest.raises(ValueError):
        funnel.read_inputs(first, second)
    assert first.reads == ["report.json", "session_results.json"]
