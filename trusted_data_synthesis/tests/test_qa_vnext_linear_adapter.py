"""CPU-only controls for reader alias scope and future-freeze registration."""

import copy
import importlib

import pytest
from test_qa_vnext_linear_manifest import fixture

from trusted_synthesis.experiments.finance_qa_vnext_basis_student import protocol as student
from trusted_synthesis.experiments.finance_qa_vnext_basis_student import worker
from trusted_synthesis.experiments.finance_qa_vnext_linear_postprocess import adapter
from trusted_synthesis.experiments.finance_qa_vnext_linear_postprocess.protocol import (
    checked,
    encode,
    policy,
    record,
)


def binding():
    sources = record(
        "linear_source_registration",
        adapter_code=[
            {"path": "new/reader.py", "sha256": "1" * 64, "role": "adapter_source"},
            {"path": "new/test.py", "sha256": "2" * 64, "role": "adapter_CPU_test"},
            {"path": "new/README.md", "sha256": "3" * 64, "role": "adapter_documentation"},
        ],
        historical_source_snapshot_sha256="4" * 64,
        historical_source_file_count=1850,
    )
    reviewed = record(
        "linear_handoff_plan",
        original_follow_started_id="follow_started:synthetic",
        collection_parent={"directory": "synthetic", "manifest_id": "manifest:synthetic"},
    )
    authorization = record("linear_handoff_authorization", operator_approved=True)
    return adapter.binding(sources, reviewed, authorization)


def imported_modules():
    return [importlib.import_module(adapter.PREFIX + name) for name in adapter.READER_MODULES]


def functions_in(modules):
    return {
        (module.__name__, name): value
        for module in modules
        for name, value in vars(module).items()
        if callable(value) and name != "Parent"
    }


def test_aliases_only_no_scientific_functions_or_worker_reader_replaced():
    modules = imported_modules()
    before = functions_in(modules)
    worker_symbols = dict(vars(worker))
    factory = student.record
    with adapter.installed(binding()) as active:
        assert all(module.Parent is active["reader_class"] for module in modules)
        assert issubclass(active["reader_class"], adapter.OriginalParent)
        assert functions_in(modules) == before
        assert dict(vars(worker)) == worker_symbols
        assert student.record is not factory
    assert all(module.Parent is adapter.OriginalParent for module in modules)
    assert student.record is factory
    assert functions_in(modules) == before
    assert active["shared_notification_monitor"].fd == -1


def test_bound_parent_preserves_real_static_bytes_and_emits_only_verification(tmp_path):
    _, manifest, supplied = fixture(tmp_path)
    with adapter.installed(binding()) as active:
        parent = active["reader_class"](tmp_path, "parent", manifest["id"])
        assert parent.verify_all() == manifest["id"]
        assert parent.bytes(next(iter(supplied))) == next(iter(supplied.values()))
        assert len(active["verifications"]) == 1
        assert active["verifications"][0] == parent.last_verification
    with pytest.raises(ValueError, match="parent_closed"):
        parent.check_manifest()


def test_aliases_and_record_factory_restored_after_original_pipeline_error():
    modules = imported_modules()
    factory = student.record
    with pytest.raises(RuntimeError, match="synthetic pipeline failure"):
        with adapter.installed(binding()):
            raise RuntimeError("synthetic pipeline failure")
    assert all(module.Parent is adapter.OriginalParent for module in modules)
    assert student.record is factory


def test_last_parent_cleanup_mutation_cannot_be_reported_as_success(tmp_path):
    directory, manifest, supplied = fixture(tmp_path)
    with pytest.raises(ValueError, match="mutation_already_observed"):
        with adapter.installed(binding()) as active:
            parent = active["reader_class"](tmp_path, "parent", manifest["id"])
            parent.verify_all()
            (directory / next(iter(supplied))).write_bytes(b"late mutation")
    assert all(module.Parent is adapter.OriginalParent for module in imported_modules())
    assert active["shared_notification_monitor"].fd == -1


def test_cleanup_mutation_does_not_hide_an_existing_scientific_failure(tmp_path):
    directory, manifest, supplied = fixture(tmp_path)
    with pytest.raises(RuntimeError, match="original failure"):
        with adapter.installed(binding()) as active:
            parent = active["reader_class"](tmp_path, "parent", manifest["id"])
            parent.verify_all()
            (directory / next(iter(supplied))).write_bytes(b"late mutation")
            raise RuntimeError("original failure")
    assert active["shared_notification_monitor"].tainted is not None
    assert active["shared_notification_monitor"].fd == -1


def test_nested_injection_is_rejected_without_uninstalling_outer_reader():
    with adapter.installed(binding()) as outer:
        with pytest.raises(ValueError, match="no_nested_adapters"):
            with adapter.installed(binding()):
                pytest.fail("nested adapter must not enter")
        assert all(module.Parent is outer["reader_class"] for module in imported_modules())


@pytest.mark.parametrize("field", ["adapter_policy_id", "reader_alias_modules"])
def test_wrong_reader_registration_rejected_before_replacing_any_alias(field):
    value = binding()
    value[field] = "wrong"
    factory = student.record
    with pytest.raises(ValueError, match="explicit_reader_adapter_binding"):
        with adapter.installed(value):
            pytest.fail("wrong registration")
    assert all(module.Parent is adapter.OriginalParent for module in imported_modules())
    assert student.record is factory


@pytest.mark.parametrize(
    "kind",
    [
        "training_configuration",
        "model_identity",
        "training_report",
        "evaluation_report",
        "decision",
    ],
)
def test_nonfreeze_original_records_remain_byte_identical(kind):
    fields = {"synthetic": True, "data": [1, 2, {"unicode": "真实"}]}
    expected = student.record(kind, **fields)
    with adapter.installed(binding()):
        assert encode(student.record(kind, **fields)) == encode(expected)


def test_freeze_metadata_binds_source_tests_docs_without_changing_original_fields():
    registered = binding()
    fields = {
        "code": [{"path": "new/reader.py", "sha256": "1" * 64}],
        "training_configuration": {"unchanged": True},
        "decoder_configuration": {"unchanged": True},
        "materials": {"manifest_id": "manifest:original"},
    }
    untouched = copy.deepcopy(fields)
    with adapter.installed(registered):
        result = student.record("study_freeze", **fields)
        assert student.checked_record(result, "study_freeze") == result
    assert student.checked_record(result, "study_freeze") == result
    assert fields == untouched
    assert all(result[key] == value for key, value in fields.items())
    assert result["postprocessing_verification_adapter"] == registered
    assert checked(result["postprocessing_verification_adapter"], "postprocessing_reader_binding")
    registered["adapter_code"][0]["sha256"] = "later mutation"
    assert result["postprocessing_verification_adapter"]["adapter_code"][0]["sha256"] == "1" * 64


@pytest.mark.parametrize("code", [[], [{"path": "new/reader.py", "sha256": "0" * 64}]])
def test_freeze_rejects_missing_or_changed_actual_adapter_source(code):
    with adapter.installed(binding()):
        with pytest.raises(ValueError, match="adapter_sources_in_actual_training_freeze"):
            student.record("study_freeze", code=code)


def test_freeze_rejects_rebinding_an_existing_different_adapter():
    with adapter.installed(binding()):
        with pytest.raises(ValueError, match="training_freeze_adapter_identity"):
            student.record("study_freeze", postprocessing_verification_adapter={"id": "other"})


def test_policy_is_not_a_production_authorization():
    value = policy()
    assert value["production_handoff_requires_explicit_review"] is True
    assert value["this_policy_record_alone_authorizes_execution"] is False
    assert value["changed_historical_source_files"] == 0
