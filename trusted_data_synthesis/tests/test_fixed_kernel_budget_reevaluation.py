"""Small CPU controls for the new post-run budget diagnostic, not old-model replay."""

import importlib.util
import sys
from pathlib import Path


def load_script(name):
    directory = Path(__file__).resolve().parents[1] / "scripts"
    sys.path.insert(0, str(directory))
    try:
        spec = importlib.util.spec_from_file_location(name, directory / (name + ".py"))
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
        return module
    finally:
        sys.path.pop(0)


def rows():
    return [
        dict(task_id=f"task_{group}_{index:03d}", group=group, source_cluster=f"CIK{index % 12}")
        for group in ("dual_sufficient", "composition_required", "other_financial")
        for index in range(60)
    ]


def test_metadata_selection_is_order_invariant_balanced_and_source_distinct():
    runner = load_script("run_fixed_kernel_budget_reevaluation_20260915")
    tasks = rows()
    selected = runner.select_pilot_tasks(tasks)
    assert selected == runner.select_pilot_tasks(list(reversed(tasks)))
    by_id = {row["task_id"]: row for row in tasks}
    assert len(selected) == len(set(selected)) == 3
    assert len({by_id[key]["group"] for key in selected}) == 3
    assert len({by_id[key]["source_cluster"] for key in selected}) == 3


def test_full_followup_only_contains_unseen_177_tasks():
    runner = load_script("run_fixed_kernel_budget_reevaluation_20260915")
    tasks = rows()
    selected = runner.select_pilot_tasks(tasks)
    remaining = runner.remaining_task_ids(tasks, selected)
    assert len(remaining) == len(set(remaining)) == 177
    assert not set(remaining) & set(selected)
    assert remaining == [row["task_id"] for row in tasks if row["task_id"] not in selected]


def test_full_stage_requires_complete_pilot_and_observed_financial_qualification():
    runner = load_script("run_fixed_kernel_budget_reevaluation_20260915")
    reports = [
        dict(actual_complete=True, outcomes=[dict(financial_valid=False) for _ in range(3)])
        for _ in range(9)
    ]
    assert runner.decide_next_stage(reports) == "STOP_ZERO_QUALIFIED"
    reports[0]["outcomes"][0]["financial_valid"] = True
    assert runner.decide_next_stage(reports) == "FULL_DEV_REEVALUATION"
    assert runner.decide_next_stage(reports[:-1]) == "INCOMPLETE_PILOT"
    reports[-1]["actual_complete"] = False
    assert runner.decide_next_stage(reports) == "INCOMPLETE_PILOT"


def budget_inputs():
    adapter = load_script("fixed_kernel_budget_reevaluation_adapter_20260915")
    root = Path(__file__).resolve().parents[2]
    output = root / (
        "trusted_data_synthesis/artifacts/qa_vnext_fixed_kernel_value/"
        "parallel_tail_execution_20260914"
    )
    frozen = adapter.p.read_json(output / "preparation/execution_freeze.json")
    selected = [
        next(
            row["task_id"] for row in frozen["evaluation_registry"]["dev"] if row["group"] == group
        )
        for group in adapter.GROUPS
    ]
    return adapter, frozen, selected, output


def test_budget_policy_public_parent_identity_and_original_globals_preserved():
    adapter, frozen, selected, _ = budget_inputs()
    original_policy = adapter.original.policy()
    original_generate = adapter.runtime.generate
    public = adapter.public_parent_binding(frozen)
    assert public["id"] != frozen["id"]
    assert public["parent_execution_freeze_id"] == frozen["id"]
    assert public["private_TaskBundles_or_answers_included"] is False
    full = adapter.build_adapter(selected, frozen)
    minimal = adapter.build_adapter(selected, public)
    assert full.transform_provenance["id"] == minimal.transform_provenance["id"]
    assert full.policy() == minimal.policy()
    policy = full.policy()
    assert tuple(
        policy[key]
        for key in ("max_responses", "max_tools", "max_new_tokens", "maximum_sequence_length")
    ) == (64, 64, 4096, 32768)
    configuration = full.bind_policy(frozen["tokenizer_binding"], frozen["base_binding"])
    assert configuration["policy"] == policy
    assert "unchanged_latest_baseline_2048_limit" not in configuration
    assert configuration["original_model_context_configuration_unchanged"] is True
    assert adapter.original.policy() == original_policy
    assert adapter.runtime.generate is original_generate
    assert adapter.runtime.MAX_RESPONSES == adapter.runtime.MAX_TOOLS == 32
    assert full.replay_session.__globals__["generate"] is full.runtime.generate
    assert full.assess_session.__globals__["replay_session"] is full.replay_session
    assert full.score.__globals__["assess_session"] is full.assess_session


def test_private_runtime_64_response_limit_and_same_budget_offline_replay(monkeypatch):
    from types import SimpleNamespace

    import pytest

    adapter, frozen, selected, _ = budget_inputs()
    bound = adapter.build_adapter(selected, frozen)
    runtime = adapter.runtime
    descriptor = {"source_id": "synthetic_public_source"}
    public = dict(
        question="Synthetic CPU protocol control; no financial answer.",
        source_document=descriptor,
        quantity_contract={},
        source_policy="synthetic_control",
        tool_contract={},
        period_contract={"task_id": "synthetic_task"},
    )
    messages = [{"role": "user", "content": runtime.encode(public).decode()}]
    identity = dict(
        task_id="synthetic_task",
        family="dual_sufficient",
        surface_version_id="synthetic_surface",
        public_messages_sha256=runtime.sha(runtime.encode(messages)),
        parent_manifest_id="synthetic_manifest",
    )
    sources = SimpleNamespace(
        references={descriptor["source_id"]: descriptor}, descriptors=lambda: [descriptor]
    )
    original_public_document = runtime.public_document
    monkeypatch.setitem(bound.runtime.generate.__globals__, "public_document", lambda *args: public)
    session = bound.runtime.generate(
        messages, identity, sources, scripted=["{}"] * 64, max_responses=64, max_tools=64
    )
    assert len(session["turns"]) == len(session["events"]) == 64
    assert session["terminal"] == "response_budget_exhausted"
    assert session["first_final_index"] is None
    assert session["gpu_calls"] == session["model_weight_loads"] == 0
    assert bound.replay_session(session, sources) == session
    assert runtime.public_document is original_public_document
    original_limit_control = adapter.clone_function(
        runtime.generate, {**vars(runtime), "public_document": lambda *args: public}
    )
    with pytest.raises(ValueError, match="runtime.session_limits"):
        original_limit_control(
            messages, identity, sources, scripted=["{}"] * 64, max_responses=64, max_tools=64
        )


def test_subset_has_new_catalog_identity_and_unchanged_original_public_envelopes():
    adapter, frozen, selected, _ = budget_inputs()
    bound = adapter.build_adapter(selected, adapter.public_parent_binding(frozen))
    view = bound.PublicOverlay(
        Path(frozen["source_root"]),
        adapter.original.SURFACE_DIRECTORY,
        adapter.original.SURFACE_MANIFEST_ID,
    )
    assert view.catalog["id"] != view.original.catalog["id"]
    assert view.catalog["parent_catalog_id"] == view.original.catalog["id"]
    assert len(view.catalog["tasks"]) == 3
    assert len(view.original.catalog["tasks"]) == 900
    assert [row["task_id"] for row in view.catalog["tasks"]] == selected
    for task_id in selected:
        assert view.public_envelope(task_id) == view.original.public_envelope(task_id)


def test_synthetic_decoder_accepts_more_than_2048_and_enforces_32768_context(tmp_path):
    import pytest

    adapter, frozen, selected, output = budget_inputs()
    bound = adapter.build_adapter(selected, frozen)
    config = bound.bind_policy(frozen["tokenizer_binding"], frozen["base_binding"])
    old_identity = adapter.p.read_json(output / "generation/dev/A_alpha0_11/model_identity.json")
    identity = adapter.p.record(
        "model_identity",
        **{
            **{
                key: value
                for key, value in old_identity.items()
                if key not in {"id", "schema_version"}
            },
            "study_freeze_id": "synthetic_budget_control",
            "decoder_config_id": config["id"],
        },
    )

    class Tokenizer:
        def __init__(self):
            binding = frozen["tokenizer_binding"]
            for name in ("chat_template", "eos_token_id", "pad_token_id", "bos_token_id"):
                setattr(self, name, binding[name])
            self.prompt_count = 32768 - 4096

        def apply_chat_template(self, messages, **kwargs):
            return "synthetic_prompt"

        def __call__(self, rendered, **kwargs):
            return {"input_ids": [1] * self.prompt_count, "attention_mask": [1] * self.prompt_count}

        def decode(self, token_ids, **kwargs):
            return "x" * len(token_ids)

    class Model:
        training = False
        calls = 0

        def requires_grad_(self, enabled):
            assert enabled is False
            return self

        def eval(self):
            self.training = False
            return self

        def generate(self, input_ids, attention_mask, **options):
            self.calls += 1
            assert options["max_new_tokens"] == 4096
            return [input_ids[0] + [7] * 3000 + [config["eos_token_ids"][0]]]

    receipt = adapter.p.record(
        "model_load_receipt",
        model_identity_id=identity["id"],
        execution_kind=adapter.original.CONTROL,
        restored_checkpoint_id=identity["checkpoint_id"],
        model_weight_loads=0,
        final_adapter_loads=0,
        tokenizer_loads=0,
        GPU_loads=0,
    )
    model, tokenizer = Model(), Tokenizer()
    decoder = bound.BoundDecoder(
        model,
        tokenizer,
        frozen["tokenizer_binding"],
        identity,
        tmp_path / "decoder",
        base_binding=frozen["base_binding"],
        configuration=config,
        execution_kind=adapter.original.CONTROL,
        load_receipt=receipt,
    )
    context = dict(
        identity={"parent_manifest_id": identity["surface_manifest_id"]},
        response_index=0,
        max_responses=64,
        max_tools=64,
        remaining_tool_calls=64,
        history_must_not_be_truncated=True,
    )
    messages = [{"role": "system", "content": "Synthetic\nRequested guidance: neutral"}]
    decoder(messages, context)
    assert model.calls == 1
    assert decoder.receipts[-1]["generated_token_count"] == 3001
    assert decoder.receipts[-1]["finish_reason"] == "actual_EOS"
    assert decoder.receipts[-1]["prompt_token_count"] + 4096 == 32768
    tokenizer.prompt_count += 1
    context["response_index"] = 1
    with pytest.raises(adapter.original.ContextRejected, match="4096_exceeds_32768"):
        decoder(messages, context)
    assert model.calls == 1
    assert decoder.receipts[-1]["finish_reason"] == "context_rejected_before_model_generate"
    assert decoder.receipts[-1]["model_generation_invoked"] is False
    assert decoder.snapshot()["actual_GPU_generation_calls"] == 0
    assert decoder.snapshot()["synthetic_model_generation_calls"] == 1
    assert decoder.fatal_error is None
    assert 4096 in bound.verify_generation_records.__code__.co_consts
    assert 32768 in bound.verify_generation_records.__code__.co_consts
    assert 2048 not in bound.verify_generation_records.__code__.co_consts
    assert 24576 not in bound.verify_generation_records.__code__.co_consts
