"""Mock-only live callback, fixed-registry and original-consumer controls.

No test sends HTTP, constructs a real tokenizer, opens a Student, or trains.
"""

import copy
import json
from fractions import Fraction

import pytest
from test_qa_vnext_catalog_bridge_worker import fixture

from trusted_synthesis.experiments.finance_qa_vnext_basis_scale_preparation import design
from trusted_synthesis.experiments.finance_qa_vnext_catalog_bridge.controls import (
    script_for_witness,
)
from trusted_synthesis.experiments.finance_qa_vnext_catalog_bridge.worker import encode
from trusted_synthesis.experiments.finance_qa_vnext_eval_readiness import (
    collection,
    materials,
    training_assessment,
    training_runtime,
)
from trusted_synthesis.experiments.finance_qa_vnext_eval_readiness.budget import ResearchLedger
from trusted_synthesis.experiments.finance_qa_vnext_eval_readiness.transport import FatalStudyError
from trusted_synthesis.experiments.finance_qa_vnext_model_execution.transport import HTTPSendError
from trusted_synthesis.experiments.finance_qa_vnext_surface_build.budget import BudgetRejected
from trusted_synthesis.experiments.finance_qa_vnext_task_build.archive import write_json


def origin(session, *, verified=False):
    return {
        "session_id": session["registered_session_id"],
        "status": "PASS_AUTHENTIC_PUBLIC_REQUEST_CHAIN" if verified else "ORIGIN_NOT_VERIFIED",
        "test_only_mock_verifier": True,
    }


def run_fixture(f=None, script=None, *, basis="endpoint", verified=False):
    f = fixture() if f is None else f
    script = (
        script_for_witness(f["bundle"], f["native_bindings"], basis=basis)
        if script is None
        else script
    )
    queue = iter(script)
    calls = []

    def provider(messages, context):
        calls.append((copy.deepcopy(messages), copy.deepcopy(context)))
        value = next(queue)
        return value if isinstance(value, str) else encode(value).decode()

    session = training_runtime.generate(
        f["messages"],
        f["identity"],
        provider=provider,
        session_id="mock_registered",
        requested_basis=basis,
    )
    assessed = training_assessment.assess_session(
        session,
        f["bundle"],
        f["native_bindings"],
        origin_evidence=origin(session, verified=verified),
    )
    return session, assessed, calls


@pytest.mark.parametrize("family", ["stock_rollforward", "annual_flow", "company_defined_metric"])
@pytest.mark.parametrize("quantity", ["difference", "relative_change"])
@pytest.mark.parametrize("basis", ["endpoint", "movement"])
def test_live_callback_uses_real_tools_and_actual_method_but_mock_is_not_training(
    family, quantity, basis
):
    f = fixture(family, quantity)
    session, assessed, calls = run_fixture(f, basis=basis)
    assert assessed["financial_valid"] and assessed["actual_method"] == basis
    assert session["origin"] == assessed["origin"] == "live_teacher_callback"
    assert not assessed["authentic_Teacher_origin_verified"]
    assert not assessed["representation_eligible"] and not assessed["training_eligible"]
    assert len(calls) == len(session["turns"])
    assert training_runtime.replay(session) == session
    assert all(call[0][-1] for call in calls)
    assert all("private" not in call[1] for call in calls)


def test_new_32_tool_runtime_replays_more_than_old_24_tool_limit():
    f = fixture()
    script = [{"tool": "read_source", "arguments": {"source_id": "p", "unit": "million USD"}}] * 25
    script += [{"final": {"value": "40", "unit": "million USD", "result_id": "tool:25"}}]
    session, _, _ = run_fixture(f, script)
    assert session["max_tools"] == 32
    assert len([event for event in session["events"] if event["tool_call"]]) == 25
    assert session["terminal"] == "first_final"
    assert training_runtime.replay(session) == session


def test_first_malformed_final_stops_without_following_callback():
    session, qualification, calls = run_fixture(script=[{"final": "bad"}, {"final": "never"}])
    assert len(calls) == 1 and session["first_final_index"] == 0
    assert not qualification["financial_valid"]


def test_bad_format_is_retained_in_original_later_history_and_pending_class():
    f = fixture()
    script = ["not JSON", *script_for_witness(f["bundle"], f["native_bindings"])]
    session, assessed, calls = run_fixture(f, script, verified=True)
    assert "not JSON" in [row["content"] for row in calls[-1][0]]
    assert assessed["financial_valid"] and assessed["full_mapping_status"] == "PENDING_REVIEW"
    assert not assessed["representation_eligible"]
    assert session["turns"][0]["raw_response"] == "not JSON"


@pytest.mark.parametrize(
    "exception,fatal",
    [
        (OSError("timeout"), False),
        (HTTPSendError("transport.total_timeout"), False),
        (ValueError("HTTP500"), False),
        (FatalStudyError("wrongmodel"), True),
        (BudgetRejected("exhausted"), True),
    ],
)
def test_session_transport_failure_and_global_study_stop_are_distinct(exception, fatal):
    f = fixture()

    def provider(messages, context):
        raise exception

    session = training_runtime.generate(
        f["messages"], f["identity"], provider=provider, session_id="mock"
    )
    assert session["global_fatal"] is fatal
    assert len(session["provider_attempts"]) == 1
    assert training_runtime.replay(session) == session


def test_raw_history_tamper_is_rejected_even_with_refreshed_container_identity():
    session, _, _ = run_fixture()
    session["turns"][-1]["input_messages"][0]["content"] += "tamper"
    session = training_runtime.record(
        "training_session",
        **{key: val for key, val in session.items() if key not in {"id", "schema_version"}},
    )
    with pytest.raises(ValueError, match="replay"):
        training_runtime.replay(session)


def make_ledger(tmp_path, f):
    ledger = ResearchLedger(tmp_path / "ledger.sqlite3", "mock-stage", prior_debits=[])
    gate = {
        "id": "mock-gate",
        "status": "READY_FOR_FIXED_COLLECTION",
        **dict.fromkeys(
            (
                "panel_quota_complete",
                "actual_period_semantics_passed",
                "increment_source_semantics_passed",
                "complete_trajectory_qualification_passed",
                "live_transport_controls_passed",
                "new_original_CPU_representation_passed",
                "training_catalog_locked",
                "original_package_consumer_registered",
            ),
            True,
        ),
    }
    tasks = [{"task_id": f["identity"]["task_id"], "family": f["identity"]["family"]}]
    ledger.register_collection(tasks, gate_id=gate["id"], gate=gate)
    return ledger, gate, tasks


class Catalog:
    def __init__(self, f):
        self.f = f
        self.tasks = {f["identity"]["task_id"]: f["identity"]}

    def public_envelope(self, identifier):
        assert identifier == self.f["identity"]["task_id"]
        return {"identity": self.f["identity"], "messages": self.f["messages"]}

    def fixture(self, identifier, public_catalog):
        assert public_catalog is self
        return self.f


def mock_collect(tmp_path, *, first_error=None, verified=False):
    f = fixture("control")
    ledger, gate, tasks = make_ledger(tmp_path, f)
    catalog = Catalog(f)
    first = ledger.sessions()[0]["session_id"]

    def factory(registered):
        queue = iter(script_for_witness(f["bundle"], f["native_bindings"]))

        def provider(messages, context):
            if first_error is not None and registered["session_id"] == first:
                raise first_error
            return encode(next(queue)).decode()

        return provider

    def verifier(session, ledger):
        return origin(session, verified=verified)

    report = collection.run(
        tmp_path,
        tmp_path / "collection",
        ledger,
        catalog,
        catalog,
        factory,
        gate_id=gate["id"],
        receipt_verifier=verifier,
    )
    return report, ledger, tasks, verifier


def test_fixed_collection_runs_all_48_mock_control_sessions_without_eight_package_early_stop(
    tmp_path,
):
    report, ledger, _, _ = mock_collect(tmp_path)
    assert report["collection_complete"] and report["registered_session_count"] == 48
    assert report["recorded_session_count"] == report["finished_session_count"] == 48
    assert report["representation_eligible_sessions"] == 0
    assert not report["training_population_selected"] and report["tokenizer_loads"] == 0
    assert len(ledger.sessions()) == 48


def test_ordinary_transport_failure_keeps_fixed_denominator_and_other_sessions(tmp_path):
    report, _, _, _ = mock_collect(tmp_path, first_error=OSError("timeout"))
    assert report["collection_complete"] and report["finished_session_count"] == 48
    rows = json.loads((tmp_path / "collection/session_results.json").read_bytes())
    assert sum(row["terminal"] == "transport_session_terminal" for row in rows) == 1


def test_budget_stop_retains_incomplete_registry_and_blocks_material_selection_before_loader(
    tmp_path,
):
    report, ledger, tasks, verifier = mock_collect(
        tmp_path, first_error=BudgetRejected("budget exhausted")
    )
    assert not report["collection_complete"] and not report["population_selection_allowed"]
    assert len(ledger.sessions()) == 48 and report["finished_session_count"] < 48
    with pytest.raises(ValueError, match="complete_collection"):
        materials.run(
            tmp_path,
            tmp_path / "material",
            tmp_path / "collection",
            tasks,
            expected_collection_id=report["id"],
            ledger=ledger,
            receipt_verifier=verifier,
            loader=lambda root: pytest.fail("must not construct tokenizer for partial collection"),
        )
    assert not (tmp_path / "material").exists()


def test_raw_package_rejects_unverified_callback_origin():
    session, qualification, _ = run_fixture()
    registered = {
        "session_id": session["registered_session_id"],
        "task_id": session["identity"]["task_id"],
        "pool": "A",
    }
    with pytest.raises(ValueError, match="authentic_financial"):
        materials.raw_package(session, qualification, registered)


def test_complete_collection_mock_materializer_constructs_once_no_truncation_and_no_small_training(
    tmp_path,
):
    report, ledger, tasks, verifier = mock_collect(tmp_path, verified=True)
    count = {"loads": 0, "rows": 0}

    def loader(root):
        count["loads"] += 1
        return {
            "id": "mock-binding",
            "maximum_sequence_length": 24576,
            "model_max_position_embeddings": 32768,
        }, object()

    def encoder(row, binding, tokenizer, *, maximum_sequence_length):
        count["rows"] += 1
        assert maximum_sequence_length == 24576 and row["target_text"]
        return {
            "consumable_token_representation": True,
            "target_token_count": 2,
            "sequence_length": 10,
            "input_ids": list(range(10)),
            "labels": [-100] * 8 + [8, 9],
            "target_mask": [0] * 8 + [1, 1],
        }

    manifest = materials.run(
        tmp_path,
        tmp_path / "material",
        tmp_path / "collection",
        tasks,
        expected_collection_id=report["id"],
        ledger=ledger,
        receipt_verifier=verifier,
        loader=loader,
        encoder=encoder,
    )
    assert count["loads"] == manifest["tokenizer_loads"] == 1
    assert manifest["all_original_registered_denominators"] == 48
    assert manifest["status"] == "STOP_INSUFFICIENT_COMMON_AB_MATERIALS"
    assert not manifest["training_started"] and manifest["packages"] == []
    assert manifest["common_AB_readiness"][0]["counts_by_pool_actual_method"] == {
        "A": {"control": 24},
        "B": {"control": 24},
    }


def test_consumer_policy_retains_exact_alpha_over_40L_and_original_cap():
    rule = materials.policy()
    assert rule["maximum_sequence_length"] == 24576 and not rule["truncation"]
    assert (
        rule["per_pool_per_actual_method_train"] == 8
        and rule["per_pool_per_actual_method_heldout"] == 2
    )
    assert rule["exact_update_coefficient"] == "alpha(method|task)/(40*whole_package_target_tokens)"


@pytest.mark.parametrize("arm", ["alpha0", "plus", "minus"])
def test_real_consumer_loads_exact_64_packages_and_whole_package_coefficients(tmp_path, arm):
    tasks = [{"task_id": "task-" + group, "group": group} for group in design.DUAL_GROUPS]
    tasks.extend({"task_id": "control-" + str(index), "group": "control"} for index in range(2))
    descriptors = []
    for task in tasks:
        methods = ("control",) if task["group"] == "control" else design.METHODS
        for method in methods:
            for index in range(10):
                identifier = f"{task['task_id']}-{method}-{index}"
                representations = []
                for count in (3, 5):
                    ids = list(range(count + 2))
                    representations.append(
                        {
                            "representation": {
                                "input_ids": ids,
                                "target_mask": [0, *([1] * count), 0],
                                "labels": [-100, *ids[1:-1], -100],
                                "sequence_length": len(ids),
                                "target_token_count": count,
                            }
                        }
                    )
                package = training_runtime.record(
                    "encoded_original_package",
                    task_id=task["task_id"],
                    group=task["group"],
                    pool="A",
                    actual_method=method,
                    rows=representations,
                    whole_package_target_tokens=8,
                    maximum_sequence_length=24576,
                    consumable=True,
                )
                path = tmp_path / "package" / (identifier + ".json")
                write_json(path, package)
                descriptors.append(
                    {
                        "id": package["id"],
                        "path": str(path.relative_to(tmp_path)),
                        "sha256": training_runtime.primitive.sha(path.read_bytes()),
                        "task_id": task["task_id"],
                        "pool": "A",
                        "actual_method": method,
                        "role": "train" if index < 8 else "heldout",
                    }
                )
    manifest = training_runtime.record(
        "fixed_AB_material_manifest",
        status="FIXED_AB_MATERIALS_READY",
        collection_complete=True,
        population_selection={"selected": tasks},
        packages=descriptors,
    )
    examples = materials.update_examples(tmp_path, manifest, {"tasks": tasks}, pool="A", arm=arm)
    assert len(examples) == 64
    assert all(row["whole_package_target_tokens"] == 8 for row in examples)
    for row in examples:
        group = next(task["group"] for task in tasks if task["task_id"] == row["task_id"])
        assert Fraction(row["target_token_coefficient"]) == design.update_token_coefficient(
            arm, group, row["actual_method"], 8
        )
        assert len(row["rows"]) == 2
    with pytest.raises(ValueError, match="eight_original"):
        materials.update_examples(tmp_path, manifest, {"tasks": tasks}, pool="B", arm=arm)
