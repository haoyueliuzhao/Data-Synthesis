"""Independent lifecycle controls: synthetic files and pure callback mocks only.

No old archive, source parser, QA build, model/API, tokenizer or GPU is executed.
"""

import contextlib
import hashlib
import json
import threading
from pathlib import Path
from types import SimpleNamespace

import pytest

from trusted_synthesis.experiments.finance_qa_vnext_eval_readiness import (
    collection,
    materials,
    panel,
    stage,
    token_controls,
)
from trusted_synthesis.experiments.finance_qa_vnext_task_build.archive import record, write_json

GATES = (
    "panel_quota_complete",
    "actual_period_semantics_passed",
    "increment_source_semantics_passed",
    "complete_trajectory_qualification_passed",
    "new_original_CPU_representation_passed",
    "training_catalog_locked",
    "live_transport_controls_passed",
    "original_package_consumer_registered",
)


def test_freeze_code_set_includes_direct_runtime_and_schema_dependencies():
    root = Path(__file__).resolve().parents[2]
    included = set(stage.code_paths(root))
    required = {
        "raw_financial_data_lake/finraw/db/client.py",
        "raw_financial_data_lake/finraw/db/schema.py",
        "raw_financial_data_lake/finraw/qa/evaluation/schema.py",
        "trusted_data_synthesis/src/trusted_synthesis/canonical_json.py",
        "trusted_data_synthesis/src/trusted_synthesis/domains/finance/qa_vnext/protocol.py",
        "trusted_data_synthesis/src/trusted_synthesis/domains/finance/qa_vnext/runtime.py",
        "trusted_data_synthesis/src/trusted_synthesis/experiments/finance_qa_vnext_model_execution/runner.py",
    }
    assert required <= included, sorted(required - included)


def test_check_freeze_detects_cached_input_change_without_old_stage_revalidation(
    tmp_path, monkeypatch
):
    from trusted_synthesis.experiments.finance_qa_vnext_catalog_bridge import stage as old_stage

    path = tmp_path / "cache.json"
    path.write_bytes(b"original-cached-fact-selection")
    descriptor = {"directory": "old", "manifest_id": "old-manifest", "manifest_sha256": "x"}
    metadata = {"id": "frozen-source-metadata"}
    software = {"python": "mock-python", "packages": {"sympy": "mock-fixed"}}
    monkeypatch.setattr(stage, "software_versions", lambda: software)
    frozen = record(
        "eval_readiness_freeze",
        rule=stage.policy(panel.policy()),
        code=[],
        source_files=[
            {"path": "cache.json", "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
        ],
        prior_debits=[],
        tokenizer_assets=[],
        parent_bridge=descriptor,
        panel_source_metadata=metadata,
        software_versions=software,
    )
    monkeypatch.setattr(
        stage, "old_parent", lambda root: SimpleNamespace(descriptor=lambda: descriptor)
    )
    monkeypatch.setattr(stage.previous_panels, "inspect_source_metadata", lambda root: metadata)
    monkeypatch.setattr(
        old_stage, "check_freeze", lambda *args: pytest.fail("old stage must not be revalidated")
    )
    stage.check_freeze(tmp_path, frozen)
    path.write_bytes(b"changed-cached-fact-selection")
    with pytest.raises(ValueError, match="frozen_code_or_input"):
        stage.check_freeze(tmp_path, frozen)


def test_check_freeze_rejects_software_drift_before_source_reads(tmp_path, monkeypatch):
    frozen = record(
        "eval_readiness_freeze",
        rule=stage.policy(panel.policy()),
        software_versions={"python": "fixed-python", "packages": {"sympy": "fixed"}},
    )
    monkeypatch.setattr(
        stage,
        "software_versions",
        lambda: {"python": "changed-python", "packages": {"sympy": "fixed"}},
    )
    monkeypatch.setattr(
        stage, "old_parent", lambda root: pytest.fail("must stop before parent reads")
    )
    with pytest.raises(ValueError, match="frozen_software_versions"):
        stage.check_freeze(tmp_path, frozen)


def test_freeze_checks_forbidden_sidecars_without_tokenizer_or_model_reads(tmp_path, monkeypatch):
    (tmp_path / "mock_config.json").write_text("{}")
    model_directory = tmp_path / "model-files-must-not-be-read"
    inspected = []

    def inspect_members(directory):
        inspected.append(directory)
        raise ValueError("tokenizer.unbound_sidecar")

    monkeypatch.setattr(
        stage,
        "assets",
        SimpleNamespace(
            SOURCE_CONFIGURATION="mock_config.json",
            SOURCE_CONFIGURATION_SHA256="mock-sha",
            MODEL_DIRECTORY=model_directory,
            _read_members=inspect_members,
        ),
    )
    monkeypatch.setattr(stage, "sha", lambda path: "mock-sha")
    monkeypatch.setattr(stage, "credential", lambda root: "mock-credential")
    monkeypatch.setattr(
        stage,
        "verify_old_public_bytes",
        lambda root: (
            SimpleNamespace(read=lambda name: {"source_files": []}),
            {"id": "mock-catalog"},
        ),
    )
    monkeypatch.setattr(
        stage.previous_panels, "inspect_source_metadata", lambda root: {"id": "metadata"}
    )
    monkeypatch.setattr(
        stage.source_policy, "metadata", lambda root: {"source_files": [], "cached_files": []}
    )
    monkeypatch.setattr(
        stage.subprocess,
        "check_output",
        lambda *args, **kwargs: pytest.fail("stop before Git or test dispatch"),
    )
    with pytest.raises(ValueError, match="unbound_sidecar"):
        stage.freeze(tmp_path)
    assert inspected == [model_directory]
    assert not model_directory.exists() and not (tmp_path / stage.OUTPUT).exists()


def test_ledger_rejects_intermediate_symlink_before_database_creation(tmp_path, monkeypatch):
    outside = tmp_path / "outside"
    outside.mkdir()
    link = tmp_path / "linked"
    link.symlink_to(outside, target_is_directory=True)
    monkeypatch.setattr(stage, "WORK", "linked/runtime")
    constructed = []
    monkeypatch.setattr(stage, "ResearchLedger", lambda *args, **kwargs: constructed.append(args))
    with pytest.raises(ValueError, match="symlink"):
        stage.ledger(tmp_path, {"id": "freeze", "prior_debits": []})
    assert not constructed


def test_real_fixture_selection_is_public_snapshot_bound_and_source_only(tmp_path, monkeypatch):
    output = tmp_path / "version"
    references, values = [], {}
    for split in ("dev", "confirm"):
        directory = output / "panels" / split
        tasks = []
        bindings = {"native": {"record": {"start": "2019-01-01", "end": "2019-12-31"}}}
        values[str(directory / "native_bindings.json")] = bindings
        for suffix in ("b", "a"):
            identifier = split + "_" + suffix
            public = {
                "period_contract": {
                    "quantity": "three_annual_flow_mean",
                    "periods": [
                        {
                            "period_id": "period:duration:2019-01-01:2019-12-31",
                            "period_type": "duration",
                            "label_basis": "calendar_year",
                        }
                    ],
                },
                "source_document": {
                    "source_id": "source-" + split,
                    "complete_original_snapshot": {
                        "path": "raw.json",
                        "sha256": "fixed",
                        "bytes": 1,
                    },
                },
            }
            bundle = {
                "task_id": identifier,
                "public": public,
                "private": {"canary": "must-not-be-source-projection"},
            }
            task = {
                "task_id": identifier,
                "path": identifier + "/bundle.json",
                "public_path": identifier + "/public.json",
                "surface_version_id": "surface-" + identifier,
                "public_messages_sha256": "hash-" + identifier,
                "family": "composition_required",
                "source_cluster": "cik-" + split,
            }
            values[str(directory / task["path"])] = bundle
            values[str(directory / task["public_path"])] = [{"role": "user", "content": identifier}]
            tasks.append(task)
        values[str(directory / "catalog.json")] = {"tasks": tasks}
    monkeypatch.setattr(stage, "read", lambda path: values[str(path)])

    def sources(root, refs):
        references.append((root, refs))
        assert "private" not in json.dumps(refs)
        return SimpleNamespace(references=refs)

    monkeypatch.setattr(stage, "SnapshotSources", sources)
    selected, population = stage.real_control_fixtures(tmp_path, output, {"id": "freeze"})
    assert [row["task_id"] for row in selected] == ["dev_a", "confirm_a"]
    assert all(row["fixture"]["identity"]["parent_manifest_id"] == "freeze" for row in selected)
    assert all(
        set(row["fixture"]["identity"])
        == {
            "task_id",
            "family",
            "surface_version_id",
            "public_messages_sha256",
            "parent_manifest_id",
        }
        for row in selected
    )
    assert len(references) == 2 and sum(map(len, population.values())) == 4


def test_prepare_parallel_signatures_one_new_control_encoding_and_no_old_dispatch(
    tmp_path, monkeypatch
):
    output = tmp_path / stage.OUTPUT
    frozen = {
        "id": "freeze",
        "panel_source_metadata": {"id": "metadata"},
        "rule": {"controls": {"real_fixture_selection": "fixed"}},
    }
    write_json(output / "stage_freeze.json", frozen)
    monkeypatch.setattr(stage, "check_freeze", lambda *args: None)
    monkeypatch.setattr(stage, "credential", lambda root: "mock-credential")
    monkeypatch.setattr(
        stage,
        "ledger",
        lambda *args: SimpleNamespace(
            sessions=lambda: [], snapshot=lambda: {"request_reservations": 0}
        ),
    )
    monkeypatch.setattr(stage, "rewrite_guard", lambda: contextlib.nullcontext({"forbidden": {}}))
    entered_panel, entered_train = threading.Event(), threading.Event()

    def panel_run(
        root, destination, work, *, expected_policy_id, expected_source_metadata_id, freeze_id
    ):
        assert root == tmp_path and destination == output / "panels"
        assert work == tmp_path / stage.WORK / "panels"
        assert (
            expected_policy_id == panel.policy()["id"]
            and expected_source_metadata_id == "metadata"
            and freeze_id == "freeze"
        )
        entered_panel.set()
        assert entered_train.wait(2), "train and panel were not run concurrently"
        return {
            "unique_task_count": 900,
            "quota_complete": True,
            "all_selected_public_period_checks_passed": True,
        }

    def train_run(root, destination, work, freeze, bank, key):
        assert root == tmp_path and destination == output / "incremental"
        assert work == stage.WORK + "/train" and freeze is not None and key == "mock-credential"
        entered_train.set()
        assert entered_panel.wait(2), "panel and train were not run concurrently"
        return {"tasks": 0, "all_registered_tasks_retained": True}

    monkeypatch.setattr(stage.panel, "run", panel_run)
    monkeypatch.setattr(stage.training_increment, "run", train_run)
    monkeypatch.setattr(
        stage, "old_parent", lambda root: SimpleNamespace(read=lambda name: {"parents": []})
    )
    monkeypatch.setattr(stage, "Parent", lambda *args: SimpleNamespace())
    tasks = [
        {"task_id": group + str(i), "family": group}
        for group, size in (
            ("stock_rollforward", 53),
            ("annual_flow", 54),
            ("company_defined_metric", 36),
            ("control", 100),
        )
        for i in range(size)
    ]
    monkeypatch.setattr(
        stage, "compose", lambda *args: ({"id": "catalog", "tasks": tasks}, {"id": "public"})
    )
    monkeypatch.setattr(
        stage, "real_control_fixtures", lambda *args: ([], {"dev": [], "confirm": []})
    )
    dispatches = []

    def run_controls(cases=None, output=None):
        dispatches.append((cases, output))
        return {"status": "PASS", "control_count": 1, "passed_count": 1}

    monkeypatch.setattr(stage.controls, "run_controls", run_controls)
    monkeypatch.setattr(stage.controls, "source_bound_cases", lambda fixtures: ["fixed-new-case"])
    monkeypatch.setattr(stage.controls, "raw_packages", lambda report: ["new-original-package"])
    encodings = []

    def materialize(packages, root):
        encodings.append((packages, root))
        return {
            "status": "PASS_SCRIPTED_REPRESENTATION_ONLY",
            "failures": [],
            "tokenizer_constructions": 1,
            "encoded_rows": 1,
            "maximum_sequence_length": 24576,
            "truncation": False,
        }

    monkeypatch.setattr(stage.token_controls, "materialize", materialize)
    monkeypatch.setattr(stage.power, "run", lambda tasks: {"mock_power": True})
    monkeypatch.setattr(stage, "verify_old_public_bytes", lambda *args: None)
    monkeypatch.setattr(stage, "seal", lambda *args, **kwargs: {"id": "manifest"})
    result = stage.prepare(tmp_path)
    assert result["evaluation_tasks"] == 900
    assert len(dispatches) == 2 and dispatches[1][0] == ["fixed-new-case"]
    assert encodings == [(["new-original-package"], tmp_path)]
    assert (output / "run_completed.json").exists()


def _collection_stage(tmp_path, monkeypatch, *, bad_gate=None, complete=True):
    from trusted_synthesis.experiments.finance_qa_vnext_task_panel import guards

    frozen = {
        "id": "freeze",
        "new_test_result": {"return_code": 0},
        "rule": stage.policy(panel.policy()),
        "code": [
            {
                "path": "trusted_data_synthesis/scripts/audit_qa_vnext_eval_readiness_"
                + label
                + ".py",
                "sha256": "sha-" + label,
            }
            for label in ("panels", "increment")
        ],
    }
    prep = record(
        "eval_readiness_preparation_report",
        panel_quota_complete=True,
        evaluation_tasks=900,
        panel_public_period_checks=True,
        balanced_reference_supply_ceiling=180,
        all_new_registered_targets_retained=True,
        new_synthetic_controls={"status": "PASS", "control_count": 1, "passed_count": 1},
        new_source_bound_controls={"status": "PASS", "control_count": 1, "passed_count": 1},
        new_CPU_materialization={
            "status": "PASS_SCRIPTED_REPRESENTATION_ONLY",
            "failures": [],
            "tokenizer_constructions": 1,
            "encoded_rows": 1,
            "maximum_sequence_length": 24576,
            "truncation": False,
            "financial_complete_packages": 1,
        },
    )
    flags = dict.fromkeys(GATES, True)
    if bad_gate:
        flags[bad_gate] = False
    audits = {
        label: record(
            "readiness_independent_audit",
            stage_manifest_id="prepared",
            script="audit_qa_vnext_eval_readiness_" + label + ".py",
            script_sha256="sha-" + label,
            status=status,
            result={"status": status},
        )
        for label, status in (("panels", "PASS_AS_SCOPED"), ("increment", "passed"))
    }
    gate = record(
        "fixed_study_admission",
        status="READY_FOR_FIXED_COLLECTION",
        **flags,
        preparation_manifest_id="prepared",
        preparation_report_id=prep["id"],
        freeze_id="freeze",
        collection_policy_id=collection.policy()["id"],
        consumer_policy_id=materials.policy()["id"],
        independent_audit_ids={key: value["id"] for key, value in audits.items()},
        failed_gates=[],
    )
    calls = {
        "verify": [],
        "register": [],
        "send": [],
        "material": [],
        "gate": gate,
        "frozen": frozen,
        "prep": prep,
        "audits": audits,
    }

    class Parent:
        def __init__(self, root, relative, *args):
            self.relative = str(relative)
            self.manifest = {
                "id": "prepared"
                if self.relative == stage.OUTPUT
                else "audited"
                if self.relative == stage.AUDITS
                else "collected"
            }

        def verify_all(self):
            calls["verify"].append(self.relative)

        def read(self, name):
            if name == "admission_gate.json":
                return gate
            if name in {"panels.json", "increment.json"}:
                return audits[name.split(".")[0]]
            if name == "report.json":
                return (
                    prep
                    if self.relative == stage.OUTPUT
                    else {"id": "collection-report", "collection_complete": complete}
                )
            return {"id": name, "tasks": []}

    class Bank:
        def register_collection(self, tasks, *, gate_id, gate):
            calls["register"].append((tasks, gate_id, gate))

    online = SimpleNamespace(tasks={"task": {"task_id": "task", "family": "control"}})
    monkeypatch.setattr(
        stage,
        "read",
        lambda path: (
            frozen if str(path).endswith("stage_freeze.json") else {"id": "public_catalog.json"}
        ),
    )
    monkeypatch.setattr(stage, "check_freeze", lambda *args: None)
    monkeypatch.setattr(stage, "Parent", Parent)
    monkeypatch.setattr(stage, "PublicCatalog", lambda *args: online)
    monkeypatch.setattr(stage, "OfflineCatalog", lambda *args: SimpleNamespace())
    monkeypatch.setattr(stage, "ledger", lambda *args: Bank())
    monkeypatch.setattr(stage, "credential", lambda root: "mock")
    monkeypatch.setattr(guards, "execution_guard", lambda **kwargs: contextlib.nullcontext({}))
    monkeypatch.setattr(stage, "seal", lambda *args, **kwargs: {"id": "sealed"})

    def collect(*args, **kwargs):
        calls["send"].append((args, kwargs))
        return {
            "id": "collection-report",
            "status": "COMPLETE_FIXED_COLLECTION",
            "registered_session_count": 48,
            "recorded_session_count": 48,
            "finished_session_count": 48,
            "financially_valid_sessions": 0,
            "representation_eligible_sessions": 0,
        }

    def material(*args, **kwargs):
        calls["material"].append((args, kwargs))
        return {
            "id": "material-report",
            "status": "STOP_INSUFFICIENT_COMMON_AB_MATERIALS",
            "population_selection": {},
            "tokenizer_loads": 0,
        }

    monkeypatch.setattr(stage.collection, "run", collect)
    monkeypatch.setattr(stage.materials, "run", material)
    return calls


@pytest.mark.parametrize("bad_gate", GATES)
def test_collect_any_false_gate_sends_nothing_even_if_ready_label_is_inconsistent(
    tmp_path, monkeypatch, bad_gate
):
    calls = _collection_stage(tmp_path, monkeypatch, bad_gate=bad_gate)
    with pytest.raises(ValueError, match="every_gate_recomputed"):
        stage.collect(tmp_path)
    assert not calls["send"]


def test_collect_ready_positive_reaches_exact_single_registration_and_receipt_bound_callback(
    tmp_path, monkeypatch
):
    calls = _collection_stage(tmp_path, monkeypatch)
    result = stage.collect(tmp_path)
    assert len(calls["register"]) == len(calls["send"]) == 1
    assert calls["register"][0][1] == calls["gate"]["id"]
    assert result["registered_session_count"] == 48
    kwargs = calls["send"][0][1]
    assert kwargs["workers"] == 8 and callable(kwargs["receipt_verifier"])
    checked = []
    monkeypatch.setattr(
        stage,
        "verify_receipts",
        lambda session, bank, directory: checked.append((session, bank, directory)),
    )
    kwargs["receipt_verifier"]("original-session", "fixed-ledger")
    assert checked == [
        ("original-session", "fixed-ledger", tmp_path / stage.COLLECTION / "requests")
    ]


@pytest.mark.parametrize(
    "field,value,error",
    [
        ("freeze_id", "other-freeze", "exact_freeze_report"),
        ("collection_policy_id", "other-policy", "frozen_collection"),
        ("failed_gates", ["failed"], "every_gate_recomputed"),
    ],
)
def test_collect_rejects_mixed_freeze_policy_or_hidden_failure(
    tmp_path, monkeypatch, field, value, error
):
    calls = _collection_stage(tmp_path, monkeypatch)
    body = {key: item for key, item in calls["gate"].items() if key not in {"id", "schema_version"}}
    body[field] = value
    calls["gate"].clear()
    calls["gate"].update(record("fixed_study_admission", **body))
    with pytest.raises(ValueError, match=error):
        stage.collect(tmp_path)
    assert not calls["send"] and not calls["register"]


def test_materialize_rechecks_prepared_manifest_before_new_tokenizer_path(tmp_path, monkeypatch):
    calls = _collection_stage(tmp_path, monkeypatch)
    stage.materialize(tmp_path)
    assert stage.OUTPUT in calls["verify"]
    assert stage.COLLECTION in calls["verify"]
    assert len(calls["material"]) == 1


def test_materialize_incomplete_collection_never_enters_consumer(tmp_path, monkeypatch):
    calls = _collection_stage(tmp_path, monkeypatch, complete=False)
    with pytest.raises(ValueError, match="incomplete"):
        stage.materialize(tmp_path)
    assert not calls["material"]


@pytest.mark.parametrize(
    "label,status,flag",
    [
        ("panels", "BLOCKED_PANEL_ADMISSION", "actual_period_semantics_passed"),
        ("increment", "AUDIT_ERROR", "increment_source_semantics_passed"),
        ("increment", "PASS_AS_SCOPED", "increment_source_semantics_passed"),
    ],
)
def test_admission_uses_each_independent_auditor_exact_success_status(
    tmp_path, monkeypatch, label, status, flag
):
    calls = _collection_stage(tmp_path, monkeypatch)
    calls["audits"][label]["status"] = status
    checks = stage.admission_checks(calls["prep"], calls["audits"], calls["frozen"])
    assert checks[flag] is False
    assert not all(checks.values())


def _token_package():
    return {
        "id": "package",
        "session_id": "session",
        "origin": "scripted_evaluation_control",
        "training_eligible": False,
        "training_samples": 0,
        "financial_valid": True,
        "complete_first_final_package": True,
        "candidates": [
            {
                "id": "candidate",
                "messages": [{"role": "user", "content": "original history"}],
                "target_text": "original raw Final",
                "response_kind": "Final",
            }
        ],
    }


def test_new_token_controls_construct_once_and_preserve_whole_untruncated_candidate(
    tmp_path, monkeypatch
):
    package = _token_package()
    calls = []

    def loader(root):
        calls.append("load")
        return {"maximum_sequence_length": 24576, "model_max_position_embeddings": 32768}, object()

    def encoder(candidate, binding, tokenizer, *, maximum_sequence_length):
        assert candidate is package["candidates"][0] and maximum_sequence_length == 24576
        return {
            "consumable_token_representation": False,
            "reason": "maximum_sequence_length_exceeded",
            "target_token_count": 7,
            "sequence_length": 24577,
        }

    monkeypatch.setattr(token_controls, "encode_original_candidate", encoder)
    result = token_controls.materialize([package], tmp_path, loader=loader)
    assert calls == ["load"] and result["tokenizer_constructions"] == 1
    assert result["status"] == "FAIL" and not result["truncation"]
    assert result["maximum_actual_sequence_length"] == 24577 and result["failures"]


def test_new_token_controls_no_eligible_package_never_constructs_tokenizer(tmp_path):
    package = _token_package()
    package["financial_valid"] = False
    result = token_controls.materialize(
        [package], tmp_path, loader=lambda root: pytest.fail("no eligible package")
    )
    assert result["tokenizer_constructions"] == 0
    assert result["status"] == "NO_FINANCIAL_COMPLETE_PACKAGES"


@pytest.mark.parametrize("mutation", ["empty", "last_not_Final"])
def test_new_token_controls_rejects_false_complete_package_before_loader(tmp_path, mutation):
    package = _token_package()
    if mutation == "empty":
        package["candidates"] = []
    else:
        package["candidates"][-1]["response_kind"] = "calculate"
    with pytest.raises(ValueError, match="financial_complete_requires_actual_Final"):
        token_controls.materialize(
            [package],
            tmp_path,
            loader=lambda root: pytest.fail("invalid package must not load tokenizer"),
        )


@pytest.mark.parametrize("cap,context", [(49152, 65536), (32768, 32768), (24576, 16384)])
def test_new_token_controls_rejects_wrong_binding_limit_without_encoding(
    tmp_path, monkeypatch, cap, context
):
    calls = []

    def loader(root):
        calls.append("one-mock-construction")
        return {"maximum_sequence_length": cap, "model_max_position_embeddings": context}, object()

    monkeypatch.setattr(
        token_controls,
        "encode_original_candidate",
        lambda *args, **kwargs: pytest.fail("invalid model limit must not encode"),
    )
    result = token_controls.materialize([_token_package()], tmp_path, loader=loader)
    assert calls == ["one-mock-construction"]
    assert result["tokenizer_constructions"] == 1 and result["status"] == "FAIL"
    assert result["encoded_rows"] == 0 and result["failures"]


@pytest.mark.parametrize(
    "field,value",
    [
        ("encoded_rows", 0),
        ("tokenizer_constructions", 2),
        ("maximum_sequence_length", 49152),
        ("truncation", True),
    ],
)
def test_admission_rejects_empty_encoding_duplicate_construction_wrong_cap_or_truncation(
    tmp_path, monkeypatch, field, value
):
    calls = _collection_stage(tmp_path, monkeypatch)
    calls["prep"]["new_CPU_materialization"][field] = value
    checks = stage.admission_checks(calls["prep"], calls["audits"], calls["frozen"])
    assert checks["new_original_CPU_representation_passed"] is False
