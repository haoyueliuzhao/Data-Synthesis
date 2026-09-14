"""Small CPU-only wiring/equivalence controls, with no models or live execution."""

from types import SimpleNamespace

import pytest
from test_qa_vnext_fixed_kernel_consumer_training import admitted_inputs as admitted_inputs

from trusted_synthesis.experiments.finance_qa_vnext_fixed_kernel_value import distribution as d
from trusted_synthesis.experiments.finance_qa_vnext_fixed_kernel_value import execution as x
from trusted_synthesis.experiments.finance_qa_vnext_fixed_kernel_value import fast_materials as f
from trusted_synthesis.experiments.finance_qa_vnext_fixed_kernel_value import protocol as p
from trusted_synthesis.experiments.finance_qa_vnext_fixed_kernel_value import training as t


@pytest.fixture
def owned(admitted_inputs, tmp_path):
    selected, registry, outcomes, kernel = admitted_inputs
    # Explicitly synthetic minted ownership: the separate material-loader tests
    # establish real descriptor/SHA/receipt minting. No real wallet is involved.
    return f.VerifiedInputs(
        f.freeze_json(
            dict(population=selected, registry=registry, outcomes=outcomes, kernel=kernel)
        ),
        mint=f._MINT,
        root=tmp_path,
        files={},
        stamps={},
        refs={
            item["package_id"]: {
                "path": "synthetic/" + item["session_id"],
                "sha256": item["original_package_sha256"],
                "id": item["package_id"],
            }
            for item in kernel["train_packages"]
        },
        receipt={"kernel_id": kernel["id"], "materialization_index_id": "synthetic_index"},
    )


def test_full_preflight_verification_matches_existing_record_without_second_build(
    admitted_inputs, owned, monkeypatch
):
    selected, registry, outcomes, kernel = admitted_inputs
    expected = t.validate_materials(kernel, selected, registry, outcomes)
    monkeypatch.setattr(d, "build_kernel", lambda *_args: pytest.fail("duplicate kernel rebuild"))
    actual = t.validate_materials(
        owned["kernel"],
        owned["population"],
        owned["registry"],
        owned["outcomes"],
        verified_inputs=owned,
    )
    assert actual == expected
    f.make_receipt(owned, actual)
    monkeypatch.setattr(
        t.consumer, "validate_row", lambda *_args: pytest.fail("duplicate row scan")
    )
    assert (
        t.validate_materials(
            owned["kernel"],
            owned["population"],
            owned["registry"],
            owned["outcomes"],
            verified_inputs=owned,
        )
        == expected
    )


@pytest.mark.parametrize("pool", p.POOLS)
def test_original_weighting_bytecode_all_arms_exact_and_token_arrays_shared(
    admitted_inputs, owned, pool
):
    kernel = admitted_inputs[3]
    for arm in p.ARMS:
        expected = d.weighted_packages(kernel, pool, arm)
        examples, assigned = t.weighted_inputs(owned, pool, arm)
        assert examples == expected
        assert assigned == d.distribution(kernel, pool, arm)
        originals = {item["package_id"]: item for item in owned["kernel"]["train_packages"]}
        assert all(
            example["rows"] is originals[example["package_id"]]["original_package"]["rows"]
            for example in examples
        )
        with pytest.raises(TypeError, match="immutable"):
            examples[0]["rows"].append({})


def test_release_ids_are_exactly_unchanged_and_plain_dict_cannot_claim_authority(
    admitted_inputs, owned
):
    kernel = admitted_inputs[3]
    kwargs = dict(
        study_freeze_id="synthetic_study",
        surface_manifest_id="synthetic_surface",
        allowed_runs=[dict(pool="A", arm="plus", seed=11)],
    )
    expected = t.make_release(kernel, **kwargs)
    actual = t.make_release(owned["kernel"], **kwargs, verified_inputs=owned)
    assert actual == expected
    t.validate_release(
        actual, owned["kernel"], pool="A", arm="plus", seed=11, verified_inputs=owned
    )
    with pytest.raises(ValueError, match="private_immutable"):
        t.weighted_inputs(dict(owned), "A", "plus")


def test_training_worker_loads_only_its_pool_and_passes_private_receipt(tmp_path, monkeypatch):
    calls = []
    authority = SimpleNamespace(verification={"id": "verification"})
    inputs = {
        "kernel": {"id": "original_kernel"},
        "population": {},
        "registry": {},
        "outcomes": [],
    }

    class View(dict):
        verification = authority.verification

    view = View(inputs)

    def load_pool(root, receipt, files, **kwargs):
        calls.append(("load_pool", kwargs))
        assert receipt == {"path": "receipt"}
        return view

    def train(*args, **kwargs):
        calls.append(("train", kwargs))
        assert kwargs["verified_inputs"] is view
        return {"actual_complete": True}

    monkeypatch.setattr(x, "verify_code", lambda *_args: None)
    monkeypatch.setattr(
        x, "load_material_inputs", lambda *_args: pytest.fail("full worker hydrate")
    )
    monkeypatch.setattr(x.fast_materials, "load_training_pool", load_pool)
    monkeypatch.setattr(x.training, "run", train)
    job = dict(kind="train", pool="B", arm="minus", seed=11)
    value = p.record(
        "worker_job",
        job=job,
        gpu={},
        code_binding={},
        execution_freeze_id="execution_freeze",
        launched_at="synthetic",
        training_input={
            "input_files": {},
            "material_input_receipt": {"path": "receipt"},
            "expected_kernel_id": "original_kernel",
            "expected_material_verification_id": "verification",
            "base_binding": {},
            "release": {"kernel_id": "original_kernel"},
            "output_directory": "student_B",
        },
    )
    path = tmp_path / "jobs/B_train/job.json"
    p.write_once(path, value)
    assert x.worker(tmp_path, path)["actual_complete"] is True
    assert calls[0] == ("load_pool", {"pool": "B", "expected_kernel_id": "original_kernel"})
    assert calls[1][1]["pool"] == "B"


def test_training_configuration_and_optimizer_loss_functions_not_replaced():
    assert t.training_config()["optimizer_updates"] == 400
    assert t.optimizer_factory.__name__ == "optimizer_factory"
    assert t.selected_target_loss.__module__.endswith("finance_qa_vnext_pq_student.loss")


def test_interrupted_prepare_reuses_receipt_without_rebuild_or_overwrite(tmp_path, monkeypatch):
    output, material = tmp_path / "execution", tmp_path / "material"
    population = {"id": "population"}
    registry = {"id": "registry", "freeze_id": "original_study"}
    kernel = {"id": "original_kernel", "physical_originals_sha256": "physical"}
    verification = p.record(
        "material_input_verification",
        kernel_id=kernel["id"],
        population_id=population["id"],
        registry_id=registry["id"],
        tokenizer_binding_id="tokenizer",
    )
    inputs = dict(population=population, registry=registry, outcomes=[], kernel=kernel)
    for name, value in (
        ("population.json", population),
        ("registry.json", registry),
        ("materialization_index.json", {"id": "index"}),
    ):
        p.write_once(material / name, value)
    gate = p.record(
        "material_gate",
        kernel_id=kernel["id"],
        registry_id=registry["id"],
        training_gate="PASS",
        material_gate="PASS",
        dose_gate="PASS",
        physical_originals_sha256=kernel["physical_originals_sha256"],
    )
    p.write_once(material / "material_gate.json", gate)
    receipt_path = output / "preparation/material_input_receipt.json"
    p.write_once(receipt_path, p.record("verified_material_receipt", already_fully_verified=True))
    receipt_sha = p.sha(receipt_path)
    calls = []

    def authority(root, reference, files, *, expected_kernel_id):
        assert root == tmp_path and expected_kernel_id == kernel["id"]
        assert reference["sha256"] == receipt_sha
        calls.append("authority")
        return inputs

    def verify(*args, verified_inputs):
        assert verified_inputs is inputs
        calls.append("verify")
        return verification

    monkeypatch.setattr(x.fast_materials, "load_authority", authority)
    monkeypatch.setattr(
        x, "load_material_inputs", lambda *_args, **_kwargs: pytest.fail("full material rebuilt")
    )
    monkeypatch.setattr(
        x.fast_materials, "make_receipt", lambda *_args: pytest.fail("verified receipt rebuilt")
    )
    monkeypatch.setattr(x.training, "validate_materials", verify)
    monkeypatch.setattr(x.e, "bind_policy", lambda *_args: {"id": "decoder"})
    monkeypatch.setattr(x, "evaluation_registry", lambda *_args: {})
    monkeypatch.setattr(x, "code_binding", lambda: {"id": "committed_code"})
    arguments = dict(
        source_root=tmp_path,
        study_freeze_id="original_study",
        population_path=material / "population.json",
        registry_path=material / "registry.json",
        materialization_index_path=material / "materialization_index.json",
        material_gate_path=material / "material_gate.json",
        base_binding={"id": "base"},
        tokenizer_binding={"id": "tokenizer"},
        resume_existing_receipt=True,
    )
    frozen = x.prepare(tmp_path, output, **arguments)
    assert frozen["receipt_reused_after_interrupted_preparation"] is True
    assert frozen["material_verification"] == verification
    assert frozen["material_input_receipt"]["sha256"] == receipt_sha == p.sha(receipt_path)
    assert calls == ["authority", "verify"]
    with pytest.raises(ValueError, match="without_freeze_or_Student"):
        x.prepare(tmp_path, output, **arguments)
    assert calls == ["authority", "verify"]
