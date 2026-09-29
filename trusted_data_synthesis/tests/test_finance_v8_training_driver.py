"""Real tiny CPU updates; no production model, API, GPU, or invented outcomes."""

import copy
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
import torch

from trusted_synthesis.finance_research.contracts import digest
from trusted_synthesis.finance_research.materials import TaskBatch, task_batch_examples
from trusted_synthesis.finance_research.providers import parameter_digest
from trusted_synthesis.finance_research.v8_training_driver import (
    REVIEW_POLICY_ID,
    LocalFeedbackCollector,
    TrainingDriver,
    _validate_encoding,
    class_gradients,
    identical_committed_state,
    installed_point,
    load_training_pool,
    tiny_cpu_pool,
    validate_student_adapters,
)


class TinyModel(torch.nn.Module):
    def __init__(self):
        super().__init__()
        self.weight = torch.nn.Parameter(torch.arange(20, dtype=torch.float32).reshape(4, 5) / 10)
        self.dropout = torch.nn.Dropout(0.2)

    def forward(self, input_ids, attention_mask, use_cache, logits_to_keep):
        logits = self.dropout(self.weight[input_ids])
        return SimpleNamespace(logits=logits[:, logits_to_keep])


def pool():
    tasks = [f"q{i}" for i in range(10)]
    packages, rows, chi = [], {}, {}
    for task in tasks:
        chi[task] = {"z0": 0, "z1": 1}
        for index, state in enumerate(("z0", "z0", "z1")):
            sid = f"{task}/s{index}"
            packages.append(
                dict(
                    package_id=sid,
                    task_id=task,
                    state_id=state,
                    whole_package_target_tokens=2,
                    fused=False,
                )
            )
            rows[sid] = [dict(input_ids=[0, 1, 2], target_positions=[1, 2], target_ids=[1, 2])]
    return tiny_cpu_pool(tasks, packages, rows, chi=chi)


def schedule(material):
    body = dict(
        batches=[
            dict(step=i + 1, task_ids=list(material.task_ids)[(i % 2) * 5 :][:5])
            for i in range(401)
        ]
    )
    return {**body, "schedule_sha256": digest(body)}


def driver(tmp_path, *, arm="Static", material=None):
    material = material or pool()
    model = TinyModel()
    optimizer = torch.optim.AdamW(model.parameters(), lr=1e-4, weight_decay=0)
    return TrainingDriver(
        model,
        optimizer,
        material,
        root=tmp_path,
        seed=11,
        arm=arm,
        cpu_control_schedule=schedule(material),
    )


def test_real_five_complete_tasks_no_extra_batch_division(tmp_path):
    run = driver(tmp_path / "run")
    before = parameter_digest(run.parameters)
    batch = TaskBatch(
        task_ids=tuple(run.pool.task_ids[:5]),
        sampling_probability={t: "1/10" for t in run.pool.task_ids},
        sampling_design="uniform_epoch_permutation",
        schedule_id="tiny",
        step=1,
    )
    examples = task_batch_examples(run.pool, run.pi, batch)
    assert len(examples) == 15
    assert {p["target_token_coefficient"] for p in examples} == {"1/30"}
    result = run.step()
    assert parameter_digest(run.parameters) != before
    assert result["optimizer_step_calls"] == result["clip_calls"] == result["zero_grad_calls"] == 1
    assert result["packages_completed"] == 15 and result["target_tokens"] == 30
    assert result["task_batch"]["task_ids"] == list(run.pool.task_ids[:5])
    assert result["additional_batch_division"] is False


def test_resume_restores_real_adam_rng_pi_and_next_batch(tmp_path):
    uninterrupted = driver(tmp_path / "first")
    torch.manual_seed(17)
    uninterrupted.step()
    checkpoint = uninterrupted.root / "step0001_step"
    expected = uninterrupted.step()
    expected_parameters = parameter_digest(uninterrupted.parameters)
    resumed = driver(tmp_path / "resume")
    resumed.restore(checkpoint)
    actual = resumed.step()
    assert actual["task_batch"] == expected["task_batch"]
    assert actual["weighted_loss"] == expected["weighted_loss"]
    assert parameter_digest(resumed.parameters) == expected_parameters
    assert resumed.optimizer.state[next(iter(resumed.parameters.values()))]["step"].item() == 2


def test_existing_run_cannot_silently_restart_or_retry_failed_step(tmp_path, monkeypatch):
    run = driver(tmp_path / "run")
    run.step()
    restarted = driver(tmp_path / "run")
    with pytest.raises(ValueError, match="restore"):
        restarted.step()
    original = run.optimizer.step

    def failure():
        original()
        raise RuntimeError("failure after real step before commit")

    monkeypatch.setattr(run.optimizer, "step", failure)
    with pytest.raises(RuntimeError):
        run.step()
    assert run.tainted
    with pytest.raises(ValueError, match="uncommitted"):
        run.step()
    assert not (run.root / "step0002_step").exists()


def test_class_gradient_is_complete_package_mean_including_controls(tmp_path):
    run = driver(tmp_path / "run")
    before, rng = parameter_digest(run.parameters), torch.get_rng_state().clone()
    gradients = class_gradients(run.model, run.pool, device="cpu")
    assert set(gradients) == set(run.pool.task_ids)
    assert set(gradients["q0"]) == {"z0", "z1"}
    assert torch.equal(gradients["q0"]["z0"]["weight"], gradients["q0"]["z1"]["weight"])
    assert gradients["q0"]["z0"]["weight"].abs().sum() > 0
    assert parameter_digest(run.parameters) == before and torch.equal(torch.get_rng_state(), rng)
    assert not run.optimizer.state and run.model.training


def test_virtual_point_really_installed_then_restored(tmp_path):
    run = driver(tmp_path / "run")
    before = parameter_digest(run.parameters)
    virtual = {n: p.detach() + 1 for n, p in run.parameters.items()}
    with installed_point(run.model, virtual) as actual:
        assert parameter_digest(actual) == parameter_digest(virtual)
        assert not run.model.training
    assert parameter_digest(run.parameters) == before and run.model.training


def test_real_outer_zero_feedback_invokes_kernel_without_moving_pi(tmp_path, monkeypatch):
    # Genuine tiny TokenReceipts come from the CPU LocalTorchProvider control.
    from test_finance_research_feedback import episode, seal
    from test_finance_research_providers import Model, Tokenizer

    from trusted_synthesis.finance_research.providers import (
        LocalTorchProvider,
        local_model_identity,
    )

    class Combined(TinyModel, Model):
        def __init__(self):
            TinyModel.__init__(self)
            self.generation_config = SimpleNamespace(eos_token_id=2)
            self.calls = 0

    run = driver(tmp_path / "outer", arm="Full")
    run.model = Combined()
    run.parameters = dict(run.model.named_parameters())
    run.optimizer = torch.optim.AdamW(run.model.parameters(), lr=1e-4, weight_decay=0)
    # This is an explicitly labelled tiny CPU fixture, not a claimed 400-step run.
    run.step_index = 400
    run.initialized = True
    run.commit("cpu_fixture_point", {"not_a_real_step400_training_result": True})
    original = copy.deepcopy(run.pi)

    def actual_receipts(prepared, point_id):
        with installed_point(run.model, prepared["theta_bar"]) as parameters:
            tokenizer = Tokenizer()
            identity = local_model_identity(
                run.model,
                tokenizer,
                model_id="CPU_control",
                point_id=point_id,
                parameter_tensors=parameters,
            )
            local = LocalTorchProvider(run.model, tokenizer, identity, parameter_tensors=parameters)
            episodes = [episode(local, seed=i) for i in (1, 2)]
            return seal(episodes, identity), [0, 0]

    result = run.outer_update(cpu_control_feedback=actual_receipts)
    assert result["distribution"]["status"] == "UNINFORMATIVE_FEEDBACK"
    assert result["feedback_report"]["all_receipts_validated"] is True
    assert result["feedback_report"]["accounting"]["zero_reward_trajectories_skipped"] == 2
    assert run.pi == original and run.outer_done == [400]
    assert not run.optimizer.state  # Virtual Adam never updates the real Adam.
    assert (run.root / "step0400_outer/state.pt").exists()


def test_c_only_full_cannot_step_without_real_outer(tmp_path):
    run = driver(tmp_path / "blocked", arm="C-only")
    run.step_index = 400
    with pytest.raises(ValueError, match="sealed outer"):
        run.step()
    with pytest.raises(ValueError, match="collector unavailable"):
        run.outer_update()


def test_manual_branch_uses_prior_chi_not_first_direction_reverse(tmp_path):
    shared = driver(tmp_path / "shared", arm="shared")
    shared.step_index = 400
    checkpoint = shared.commit("cpu_fixture_point", {"not_a_real_step400_result": True})
    plus, minus = (
        driver(tmp_path / "plus", arm="Manual+"),
        driver(tmp_path / "minus", arm="Manual-"),
    )
    plus.restore(checkpoint, branch=True)
    minus.restore(checkpoint, branch=True)
    assert plus.pi["q0"] == pytest.approx({"z0": 0.5, "z1": 0.5})
    assert minus.pi["q0"] == pytest.approx({"z0": 0.8, "z1": 0.2})
    assert not identical_committed_state(
        plus.root / "step0400_branch", minus.root / "step0400_branch"
    )


def test_missing_real_material_and_hash_mismatch_refuse(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_training_pool(tmp_path / "nonexistent.json")
    fake = tmp_path / "one.json"
    fake.write_text("{}")
    binding = {
        "schema": "v8_training_artifact_binding.v1",
        "review_policy_id": REVIEW_POLICY_ID,
        "generation_protocol": {"path": str(fake), "sha256": "0" * 64},
    }
    path = tmp_path / "binding.json"
    path.write_text(json.dumps(binding))
    with pytest.raises(ValueError, match="byte SHA"):
        load_training_pool(path)


def test_tiny_pool_never_admits_cuda_or_implicit_production(tmp_path):
    model, material = TinyModel(), pool()
    with pytest.raises(ValueError, match="production"):
        TrainingDriver(
            model,
            torch.optim.AdamW(model.parameters()),
            material,
            root=tmp_path,
            seed=11,
            device="cuda",
            cpu_control_schedule=schedule(material),
        )


def test_future_encoding_overflow_and_legacy_schema_blocked():
    with pytest.raises(ValueError, match="encoding"):
        _validate_encoding({"schema": "v6_student_encoding.v1"}, {}, None, ())


def test_partial_feedback_is_not_resampled(tmp_path, monkeypatch):
    from test_finance_research_providers import provider

    from trusted_synthesis.finance_research import storage
    from trusted_synthesis.finance_research.providers import local_model_identity
    from trusted_synthesis.finance_research.v8_training_driver import _publish

    local = provider()
    collector = object.__new__(LocalFeedbackCollector)  # Explicit branch-only CPU control.
    collector.root, collector.snapshot, collector.model_id = tmp_path, tmp_path, "fixture"
    collector.manifest, collector.role_plan, collector.seeds = {}, {"id": "role"}, (11, 29)
    collector.tasks = [SimpleNamespace(task_id="q0")]
    point = "same-attempt"
    identity = local_model_identity(
        local.model, local.tokenizer, model_id="fixture", point_id=point
    )
    _publish(
        tmp_path / digest(point) / "intent",
        dict(
            point_id=point,
            identity=identity.model_dump(mode="json"),
            source_manifest_sha256=digest({}),
            role_plan_id="role",
            seeds=(11, 29),
            task_ids=["q0"],
            denominator=700,
        ),
    )

    def forbidden(*args, **kwargs):
        pytest.fail("partial feedback cannot regenerate or read private references")

    monkeypatch.setattr(storage, "execute_run", forbidden)
    monkeypatch.setattr(storage, "_read_snapshot_rows", forbidden)
    with pytest.raises(ValueError, match="resampling forbidden"):
        collector.collect(local.model, local.tokenizer, local.parameters, point_id=point)
    assert local.model.calls == 0


def custom_qwen_fixture(**overrides):
    from trusted_synthesis.experiments.finance_qa_vnext_pq_student.model import install_adapters

    model = torch.nn.Module()
    model.config = SimpleNamespace(num_hidden_layers=2)
    model.model = torch.nn.Module()
    model.model.embed_tokens = torch.nn.Embedding(8, 16)
    model.model.layers = torch.nn.ModuleList()
    for _ in range(2):
        layer = torch.nn.Module()
        layer.self_attn = torch.nn.Module()
        for target in ("q_proj", "k_proj", "v_proj", "o_proj"):
            setattr(layer.self_attn, target, torch.nn.Linear(16, 16))
        model.model.layers.append(layer)
    model.to(dtype=torch.bfloat16)
    config = dict(
        target_modules=["q_proj", "v_proj"], lora_rank=8, lora_alpha=16, lora_dropout=0.05
    )
    config.update(overrides)
    scope = install_adapters(model, config)
    return model, scope


def test_existing_install_adapters_style_accepted_without_peft():
    model, scope = custom_qwen_fixture()
    assert not hasattr(model, "peft_config")
    actual = validate_student_adapters(model, scope)
    assert actual["implementation"] == "repository.LowRankLinear"
    assert actual["loader_scope_id"] == scope["id"]
    assert len(actual["target_module_names"]) == 4
    module = model.model.layers[0].self_attn.q_proj
    output = module(torch.ones(1, 2, 16, dtype=torch.bfloat16))
    output.float().sum().backward()
    assert module.lora_A.grad is not None and module.lora_B.grad is not None
    assert output.dtype == torch.bfloat16 and module.base.weight.grad is None


@pytest.mark.parametrize(
    "changes,message",
    [
        ({"lora_rank": 4}, "rank8"),
        ({"lora_dropout": 0.1}, "dropout"),
        ({"target_modules": ["q_proj", "k_proj"]}, "q/v target"),
        ({"target_modules": ["q_proj"]}, "q/v target"),
    ],
)
def test_custom_adapter_rank_dropout_or_target_drift_rejected(changes, message):
    model, scope = custom_qwen_fixture(**changes)
    with pytest.raises(ValueError, match=message):
        validate_student_adapters(model, scope)


def test_custom_adapter_scope_and_frozen_dtype_are_actual_checks():
    model, scope = custom_qwen_fixture()
    changed = copy.deepcopy(scope)
    changed["trainable_parameter_count"] += 1
    with pytest.raises(ValueError, match="scope differs"):
        validate_student_adapters(model, changed)
    model.model.layers[0].self_attn.q_proj.base.float()
    with pytest.raises(ValueError, match="frozen BF16"):
        validate_student_adapters(model, scope)


def test_actual_v8_launch_seal_layout_whole_file_contract(tmp_path, monkeypatch):
    """1000x8 synthetic file-contract only: no generation/qualification/training claim."""
    from test_finance_research_storage import fixture_bundle

    from trusted_synthesis.finance_research import v8_training_driver as runtime
    from trusted_synthesis.finance_research.contracts import (
        CallSettlement,
        Episode,
        ModelIdentity,
        ModelTurn,
        RunConfig,
        TaskBundle,
    )
    from trusted_synthesis.finance_research.planning import build_role_plan
    from trusted_synthesis.finance_research.probe_collection import slot_directory
    from trusted_synthesis.finance_research.storage import import_snapshot
    from trusted_synthesis.finance_research.v8_representation import validate_material_registration

    def write(path, value):
        path.parent.mkdir(parents=True, exist_ok=True)
        raw = json.dumps(value, sort_keys=True).encode()
        path.write_bytes(raw)
        return {"path": str(path), "sha256": runtime._sha(raw)}

    def bound(value):
        return {**value, "id": digest(value)}

    original_bundle = fixture_bundle()
    bundles = [
        TaskBundle(
            public=original_bundle.public.model_copy(update={"task_id": f"CPU_CONTRACT/{i}"}),
            reference=original_bundle.reference.model_copy(update={"task_id": f"CPU_CONTRACT/{i}"}),
            lineage=original_bundle.lineage.model_copy(
                update={"original_id": f"CPU_CONTRACT/{i}", "original_split": "train"}
            ),
        )
        for i in range(1000)
    ]
    snapshot = tmp_path / "snapshot"
    manifest = import_snapshot(bundles, snapshot, source={"CPU_file_contract_fixture": True})
    role_plan = build_role_plan(
        [b.public for b in bundles],
        [b.lineage for b in bundles],
        sft_tasks=1000,
        feedback_tasks=0,
        calibration_tasks=0,
    )
    tasks = [b.public.task_id for b in bundles]
    config = RunConfig(
        role="sft",
        harness_id="bigfinance-derived-vtdo-v7",
        submission_profile="finqa-public-reasoning-v2",
        context_limit=1048576,
    )
    registered = [
        {"task_id": t, "slot_index": i, "slot_id": "v7-slot:" + digest([t, i])}
        for t in tasks
        for i in range(8)
    ]
    original = bound(
        dict(
            schema="finqa_v7_new_full_probe.v1",
            task_ids=tasks,
            slots=registered,
            original_snapshot=str(snapshot),
            snapshot_id=manifest["id"],
            role_plan=role_plan,
            configs_by_task={t: config.model_dump(mode="json") for t in tasks},
        )
    )
    original_entry = write(tmp_path / "original/registration/protocol.json", original)
    monkeypatch.setattr(runtime, "ORIGINAL_MATERIAL_ID", original["id"])
    launch = bound(
        dict(
            schema="v8_independent_public_generation_launch.v1",
            original=original,
            original_protocol_id=original["id"],
            original_protocol_path=original_entry["path"],
            original_protocol_sha256=original_entry["sha256"],
            original_registration_identity_evidence=validate_material_registration(original),
            snapshot=str(snapshot),
            snapshot_id=manifest["id"],
            task_ids=tasks,
            slots=registered,
            task_denominator=1000,
            slot_denominator=8000,
            configs_by_task=original["configs_by_task"],
        )
    )
    generation_root = tmp_path / "generation"
    launch_entry = write(generation_root / "registration/protocol.json", launch)
    prefix = runtime.inspect_generation_binding(launch_entry)
    assert prefix["generation_launch_id"] == launch["id"]
    assert prefix["original_material_protocol_id"] == original["id"]
    assert prefix["generated_outcomes_read"] is False and prefix["material_admission"] is False
    outcome_rows, resolutions, encodings, inventory_rows = [], {}, {}, []
    for task_index, task in enumerate(tasks):
        episode = Episode(
            task_id=task,
            dataset="finqa",
            public_task_sha256=digest(bundles[task_index].public),
            config=config,
            provider=ModelIdentity(backend="scripted", model_id="CPU_file_contract"),
            turns=(ModelTurn(raw_text="CPU fixture"),),
            tool_events=(),
            messages=(),
            final_program="subtract(8, 2)",
            stop_reason="final_answer",
            actual_model_calls=1,
            provider_attempts=1,
            call_settlements=(
                CallSettlement(
                    attempt_index=0, state="returned", actual_model_calls=1, request_sha256="a" * 64
                ),
            ),
            all_provider_calls_settled=True,
            elapsed_seconds=0,
        )
        local_slots = registered[task_index * 8 : (task_index + 1) * 8]
        resolved = {}
        positive = local_slots[0]["slot_id"]
        for slot in local_slots:
            item = write(
                slot_directory(generation_root, slot) / "episode/episode.json",
                episode.model_dump(mode="json"),
            )
            outcome_rows.append(
                dict(
                    status="COMPLETE",
                    at="CPU_fixture",
                    slot=slot,
                    episode_sha256=digest(episode),
                    episode_file_sha256=item["sha256"],
                    actual_model_calls=1,
                    stop_reason="final_answer",
                    all_provider_calls_settled=True,
                )
            )
            resolved[slot["slot_id"]] = dict(
                q_native=slot["slot_id"] == positive,
                v_trace="valid"
                if slot["slot_id"] == positive
                else "not_assessed_native_ineligible",
                common_material_valid=slot["slot_id"] == positive,
            )
        mask = dict(
            episode_sha256=digest(episode), mask_agreement=True, registered_slot_id=positive
        )
        resolved[positive].update(mapper="mapped", state_id="z0", chi=0, encoding_manifest=mask)
        row = dict(
            input_ids=[1, 2],
            target_positions=[1],
            target_ids=[2],
            prompt_token_count=1,
            raw_response_sha256=runtime._sha(b"CPU fixture"),
            layer_target_positions={"reason": [], "tool": [], "final": [1]},
        )
        row["row_sha256"] = digest(row)
        encoding = dict(
            schema="v8_student_encoding.v1",
            encoding_policy="v8_single_authoritative_targets.v1",
            task_id=task,
            episode_sha256=digest(episode),
            resolved_mask_sha256=digest(mask),
            encoding_admitted=True,
            context_limit=24576,
            context_truncated=False,
            failures=[],
            not_a_TokenReceipt=True,
            tokenizer_digest="codec",
            chat_template_digest="template",
            rows=[row],
            L_P=1,
            total_supervised_tokens=1,
        )
        encodings[positive] = write(tmp_path / f"encodings/{task_index}.json", encoding)
        resolution = dict(
            schema="v8_common_material_resolution.v1",
            task_id=task,
            review_policy_id=REVIEW_POLICY_ID,
            slots=resolved,
            all_eight_candidates_retained=True,
            valid_slots_retained=[positive],
            task_mapping="complete",
            no_dropping_hard_to_map_valid_packages=True,
        )
        resolutions[task] = write(tmp_path / f"resolutions/{task_index}.json", resolution)
        inventory_rows.append(
            dict(
                task_id=task,
                states={"z0": 1},
                n_x=1,
                joint_valid=1,
                mapping_complete=True,
                masks_complete=True,
            )
        )
    seal = bound(
        dict(
            schema="v8_whole_generation_seal.v1",
            protocol_id=launch["id"],
            denominator=8000,
            private_references_read=False,
            slots=outcome_rows,
        )
    )
    seal_entry = write(generation_root / "generation_seal/record.json", seal)
    inventory = bound(
        dict(
            original_tasks=1000,
            original_slots=8000,
            all_originals_retained=True,
            tasks=inventory_rows,
        )
    )
    binding = dict(
        schema="v8_training_artifact_binding.v1",
        review_policy_id=REVIEW_POLICY_ID,
        generation_protocol=launch_entry,
        generation_seal=seal_entry,
        inventory=write(tmp_path / "semantic_inventory/record.json", inventory),
        resolutions=resolutions,
        encodings=encodings,
        tokenizer_binding=["codec", "template"],
    )
    binding_path = tmp_path / "binding.json"
    write(binding_path, binding)
    private = snapshot / "private.references.jsonl"
    original_read = Path.read_bytes

    def guard(path):
        assert path != private, "material binding must not reopen private gold"
        return original_read(path)

    monkeypatch.setattr(Path, "read_bytes", guard)
    material = load_training_pool(binding_path)
    assert len(material.task_ids) == len(material.packages) == 1000
    assert material.generation_launch_id == launch["id"]
    assert material.original_material_protocol_id == original["id"]
    assert material.row_arrays(registered[0]["slot_id"])[0]["target_ids"] == [2]
    assert "episode_path" not in outcome_rows[0]  # Match the real V8 seal contract exactly.
    native = bound(dict(schema="v8_native_full_population_support.v1", protocol_id=launch["id"]))
    binding["inventory"] = write(tmp_path / "native_support/record.json", native)
    write(binding_path, binding)
    with pytest.raises(ValueError, match="native support is not material"):
        load_training_pool(binding_path)
