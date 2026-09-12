"""Real material-consumer/driver wiring using tiny CPU tensors and fake assets."""

import copy
import json
from types import SimpleNamespace

import pytest
import torch
from torch import nn

from trusted_synthesis.experiments.finance_qa_vnext_basis_scale_preparation import design
from trusted_synthesis.experiments.finance_qa_vnext_basis_student import protocol, train
from trusted_synthesis.experiments.finance_qa_vnext_eval_readiness import (
    materials,
    training_runtime,
)
from trusted_synthesis.experiments.finance_qa_vnext_pq_student import model as components


@pytest.fixture(autouse=True)
def single_thread():
    previous = torch.get_num_threads()
    torch.set_num_threads(1)
    yield
    torch.set_num_threads(previous)


class TinyAdapter(nn.Module):
    def __init__(self, seed=11):
        super().__init__()
        self.block = nn.Module()
        self.block.lora_A = nn.Parameter(torch.arange(28, dtype=torch.float32).reshape(4, 7) / 100)
        self.block.lora_B = nn.Parameter(torch.full((7,), seed / 1000))
        self.register_parameter(
            "base", nn.Parameter(torch.ones((), dtype=torch.bfloat16), requires_grad=False)
        )

    def forward(self, *, input_ids, attention_mask, use_cache, logits_to_keep):
        assert use_cache is False
        state = input_ids.cumsum(-1) % 4
        return SimpleNamespace(
            logits=(self.block.lora_A[state] + self.block.lora_B)[:, logits_to_keep]
        )


def fake_loader(checkpoint_binding, seed, config=None, *, trainable):
    assert config == protocol.training_config() and trainable
    assert checkpoint_binding == {"id": "synthetic_base"}
    return TinyAdapter(seed), protocol.record("synthetic_adapter_scope", real_model_loaded=False)


def rerecord(value, **changes):
    return training_runtime.record(
        "fixed_AB_material_manifest",
        **{
            **{key: item for key, item in value.items() if key not in {"id", "schema_version"}},
            **changes,
        },
    )


def make_materials(root):
    """All 255 catalog entries, real 180-task shape, both separate 8+2 kernels."""
    sizes = dict(zip(design.GROUPS, (53, 54, 48, 100), strict=True))
    ready = {
        group: [f"{group}-{index}" for index in range(72 if group == "control" else 36)]
        for group in design.GROUPS
    }
    selection = design.choose_population(ready)
    binding = {"id": "synthetic_tokenizer", "maximum_sequence_length": 24576}
    readiness = []
    for group in design.GROUPS:
        for index in range(sizes[group]):
            methods = ("control",) if group == "control" else design.METHODS
            available = index < len(ready[group])
            readiness.append(
                {
                    "task_id": f"{group}-{index}",
                    "group": group,
                    "counts_by_pool_actual_method": {
                        pool: dict.fromkeys(methods, 10 if available else 0)
                        for pool in design.POOLS
                    },
                    "common_AB_ready": available,
                }
            )
    descriptors = []
    for task in selection["selected"]:
        for pool in design.POOLS:
            for method in ("control",) if task["group"] == "control" else design.METHODS:
                for index in range(10):
                    session = f"{pool}-{task['task_id']}-{method}-{index}"
                    target_count = 1 + index % 3 + int(pool == "B")
                    ids = [4, 3, *([1] * target_count), 2]
                    mask = [0, 0, *([1] * target_count), 0]
                    rows = [
                        {
                            "candidate_id": session + "-Final",
                            "representation": {
                                "input_ids": ids,
                                "attention_mask": [1] * len(ids),
                                "target_mask": mask,
                                "labels": [
                                    token if active else -100
                                    for token, active in zip(ids, mask, strict=True)
                                ],
                                "sequence_length": len(ids),
                                "target_token_count": target_count,
                                "consumable_token_representation": True,
                            },
                        }
                    ]
                    package = training_runtime.record(
                        "encoded_original_package",
                        registered_session_id=session,
                        raw_package_id="raw-" + session,
                        task_id=task["task_id"],
                        pool=pool,
                        group=task["group"],
                        actual_method=method,
                        full_class="synthetic-class",
                        rows=rows,
                        errors=[],
                        consumable=True,
                        whole_package_target_tokens=target_count,
                        maximum_sequence_length=24576,
                        tokenizer_binding_id=binding["id"],
                        original_request_response_bytes_retained=True,
                        truncation=False,
                        training_eligible=False,
                    )
                    path = root / "packages" / (session + ".json")
                    protocol.write_once(path, package)
                    descriptors.append(
                        {
                            **{
                                key: package[key]
                                for key in (
                                    "id",
                                    "registered_session_id",
                                    "task_id",
                                    "pool",
                                    "group",
                                    "actual_method",
                                    "consumable",
                                    "whole_package_target_tokens",
                                )
                            },
                            "path": str(path.relative_to(root)),
                            "sha256": protocol.sha(path),
                            "role": "train" if index < 8 else "heldout",
                            "within_stratum_index": index,
                        }
                    )
    return training_runtime.record(
        "fixed_AB_material_manifest",
        status="FIXED_AB_MATERIALS_READY",
        collection_id="synthetic_collection",
        collection_complete=True,
        all_original_registered_denominators=24640,
        policy_id=materials.policy()["id"],
        source_task_order=[row["task_id"] for row in readiness],
        common_AB_readiness=readiness,
        population_selection=selection,
        packages=descriptors,
        tokenizer_binding=binding,
        tokenizer_loads=1,
        original_package_consumer_registered=True,
        loss_rule="alpha(method|task)/(40*whole_package_target_tokens)",
        Student_sessions=0,
        GPU_operations=0,
        training_started=False,
    )


@pytest.fixture(scope="module")
def original_materials(tmp_path_factory):
    root = tmp_path_factory.mktemp("student_synthetic_materials")
    return root, make_materials(root)


def bindings(manifest):
    return {
        "study_freeze_id": "synthetic_freeze",
        "surface_manifest_id": "synthetic_surface",
        "materials_manifest_id": manifest["id"],
        "training_config_id": protocol.training_config()["id"],
        "decoder_config_id": "synthetic_decoder",
    }


def test_real_material_consumer_uses_exact_own_pool_and_records_different_actual_budgets(
    original_materials,
):
    root, manifest = original_materials
    result = train.validate_materials(root, manifest)
    assert result["tasks"] == 180 and result["validated_packages"] == 5760
    for pool in design.POOLS:
        budget = result["pool_budgets"][pool]
        assert budget["training_packages"] == 2304 and budget["heldout_packages"] == 576
        assert budget["target_tokens_all_epochs"] == 10 * budget["target_tokens_per_epoch"]
        assert budget["sequence_tokens_all_epochs"] == 10 * budget["sequence_tokens_per_epoch"]
    assert (
        result["pool_budgets"]["A"]["target_tokens_all_epochs"]
        < result["pool_budgets"]["B"]["target_tokens_all_epochs"]
    )
    batch = design.task_batches(manifest["population_selection"], 11)["batches"][0]
    for pool in design.POOLS:
        examples = materials.update_examples(root, manifest, batch, pool=pool, arm="plus")
        expected = train._expected_packages(manifest, batch, pool)
        train.kernel.validate_update(
            examples, batch, pool=pool, arm="plus", expected_package_ids=expected
        )
        assert len(examples) == 64 and all(item["pool"] == pool for item in examples)


@pytest.mark.parametrize(
    "change,code",
    [
        (lambda value: value.update(collection_complete=False), "complete_fixed"),
        (lambda value: value.update(all_original_registered_denominators=125), "complete_fixed"),
        (lambda value: value["packages"][0].update(role="heldout"), "eight_train_two_heldout"),
        (
            lambda value: value["packages"][0].update(within_stratum_index=8),
            "eight_train_two_heldout",
        ),
        (lambda value: value["packages"].pop(), "eight_train_two_heldout"),
        (
            lambda value: value["common_AB_readiness"][0].update(common_AB_ready=False),
            "true_common",
        ),
        (lambda value: value["packages"][0].update(pool="B"), "consumable_package"),
        (lambda value: value["packages"][0].update(sha256="0" * 64), "encoded_package_bytes"),
        (
            lambda value: value["packages"][0].update(whole_package_target_tokens=999),
            "consumable_package",
        ),
    ],
)
def test_invalid_real_manifest_shapes_fail_closed(original_materials, change, code):
    root, original = original_materials
    changed = copy.deepcopy(original)
    change(changed)
    changed = rerecord(changed)
    with pytest.raises(ValueError, match=code):
        train.validate_materials(root, changed)


def test_driver_full_registered_360_updates_and_final_restore_are_synthetic_only(
    original_materials,
):
    root, manifest = original_materials
    result = train.run(
        root,
        root / "full_synthetic_run",
        manifest,
        {"id": "synthetic_base"},
        pool="A",
        arm="plus",
        seed=11,
        binding=bindings(manifest),
        model_loader=fake_loader,
    )
    assert (
        result["status"] == "COMPLETE_SYNTHETIC_CHECKPOINT" and result["actual_complete"] is False
    )
    assert result["execution_mode"] == "synthetic_injected" and result["optimizer_updates"] == 360
    assert result["epochs_completed"] == 10 and result["intermediate_checkpoints"] == 0
    assert result["target_tokens"] == result["actual_budget"]["target_tokens_all_epochs"]
    assert result["sequence_tokens"] == result["actual_budget"]["sequence_tokens_all_epochs"]
    assert result["training_retokenizations"] == 0 and result["automatic_retries"] == 0
    output = root / result["adapter_directory"]
    assert [path.name for path in output.glob("*.safetensors")] == ["final_adapter.safetensors"]
    restored = TinyAdapter()
    components.load_adapter(
        restored, output / result["final_adapter"]["path"], result["final_adapter"]
    )
    assert components.adapter_digest(restored) == result["checkpoint_id"]
    assert result["final_adapter_restored_identity_verified"]
    first = protocol.read_json(root / result["updates"][0]["path"])
    assert (
        first["packages_completed"] == 64
        and first["zero_grad_calls"] == first["optimizer_step_calls"] == 1
    )
    events = [
        json.loads(line) for line in (output / "updates/0001/events.jsonl").read_text().splitlines()
    ]
    assert events[0]["event"] == "update_validated" and events[-1]["event"] == "update_complete"
    for index, event in enumerate(events, 1):
        protocol.checked_record(event, "optimizer_update_event")
        assert event["index"] == index
    assert protocol.read_json(output / "report.json") == result
    with pytest.raises(ValueError, match="no_retry"):
        train.run(
            root,
            output,
            manifest,
            {"id": "synthetic_base"},
            pool="A",
            arm="plus",
            seed=11,
            binding=bindings(manifest),
            model_loader=fake_loader,
        )


def test_driver_failure_durable_no_retry_no_final_and_no_step(original_materials):
    root, manifest = original_materials
    output = root / "failed_synthetic_run"
    calls = []

    def loss(logits, targets, coefficient):
        calls.append(1)
        return logits.sum() * float("nan")

    with pytest.raises(ValueError, match="finite_scalar_loss"):
        train.run(
            root,
            output,
            manifest,
            {"id": "synthetic_base"},
            pool="A",
            arm="alpha0",
            seed=29,
            binding=bindings(manifest),
            model_loader=fake_loader,
            loss_fn=loss,
        )
    failure = protocol.read_json(output / "failure.json")
    assert failure["actual_complete"] is False and failure["completed_updates"] == []
    assert len(calls) == 1 and not (output / "final_adapter.safetensors").exists()
    events = [
        json.loads(line) for line in (output / "updates/0001/events.jsonl").read_text().splitlines()
    ]
    assert events[-1]["event"] == "update_failed" and events[-1]["optimizer_step_calls"] == 0


def test_injected_loader_cannot_modify_original_rows_under_same_package_id(original_materials):
    root, manifest = original_materials

    def replacement(root, manifest, batch, *, pool, arm):
        examples = materials.update_examples(root, manifest, batch, pool=pool, arm=arm)
        examples[0]["rows"][0]["representation"]["input_ids"][0] += 1
        return examples

    with pytest.raises(ValueError, match="original_rows_no_reencoding"):
        train.run(
            root,
            root / "changed_rows",
            manifest,
            {"id": "synthetic_base"},
            pool="A",
            arm="alpha0",
            seed=47,
            binding=bindings(manifest),
            model_loader=fake_loader,
            example_loader=replacement,
        )


def test_loader_reuses_base_loader_with_explicit_new_scope_and_eval_restoration(
    monkeypatch, tmp_path
):
    class Base(nn.Module):
        def __init__(self):
            super().__init__()
            self.layer = nn.Module()
            self.layer.q_proj = nn.Linear(3, 3, bias=False, dtype=torch.bfloat16)
            self.layer.v_proj = nn.Linear(3, 3, bias=False, dtype=torch.bfloat16)
            self.other = nn.Linear(3, 3, bias=False, dtype=torch.bfloat16)
            self.config = SimpleNamespace(num_hidden_layers=1, use_cache=True)

        def gradient_checkpointing_enable(self, *, gradient_checkpointing_kwargs):
            assert gradient_checkpointing_kwargs == {"use_reentrant": False}

    calls = []

    def base_loader(binding, seed, *, trainable):
        calls.append((binding, seed, trainable))
        return Base().requires_grad_(False), None

    monkeypatch.setattr(components, "load_student", base_loader)
    model, scope = train.load_registered_student({"id": "fake"}, 11, trainable=True)
    assert calls == [({"id": "fake"}, 11, False)]
    assert scope["target_module_names"] == ["layer.q_proj", "layer.v_proj"]
    assert model.layer.q_proj.lora_A.shape == (8, 3)
    assert model.layer.q_proj.scaling == 2 and model.layer.q_proj.dropout.p == 0.05
    assert model.training and model.config.use_cache is False
    path = tmp_path / "adapter.safetensors"
    descriptor = components.save_adapter(model, path)
    restored, _ = train.load_registered_student(
        {"id": "fake"}, 11, trainable=False, adapter_path=path, adapter_record=descriptor
    )
    assert components.adapter_digest(restored) == descriptor["parameter_digest"]
    assert not restored.training and not any(
        parameter.requires_grad for parameter in restored.parameters()
    )
    assert all(
        not module.training for module in restored.modules() if isinstance(module, nn.Dropout)
    )
    assert restored.config.use_cache is True
    config = protocol.training_config()
    config["lora_rank"] = 7
    with pytest.raises(ValueError, match="new_configuration"):
        train.load_registered_student({"id": "fake"}, 11, config=config, trainable=True)


@pytest.mark.parametrize("seed", design.SEEDS)
def test_same_seed_arms_share_initial_adapter_and_task_schedule(seed):
    first, second = (
        fake_loader({"id": "synthetic_base"}, seed, protocol.training_config(), trainable=True)[0],
        fake_loader({"id": "synthetic_base"}, seed, protocol.training_config(), trainable=True)[0],
    )
    assert components.adapter_digest(first) == components.adapter_digest(second)
    ready = {
        group: [f"{group}-{index}" for index in range(72 if group == "control" else 36)]
        for group in design.GROUPS
    }
    selection = design.choose_population(ready)
    schedules = [design.task_batches(selection, seed) for _ in design.ARMS]
    assert schedules[0] == schedules[1] == schedules[2]
