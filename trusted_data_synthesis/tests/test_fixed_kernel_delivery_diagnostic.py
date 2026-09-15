"""Necessary CPU-only controls for the prepared delivery diagnostic adapter."""

import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace


def inputs():
    root = Path(__file__).resolve().parents[2]
    directory = root / "trusted_data_synthesis/scripts"
    name = "fixed_kernel_delivery_diagnostic_adapter_20260915"
    sys.path.insert(0, str(directory))
    try:
        spec = importlib.util.spec_from_file_location(name, directory / (name + ".py"))
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
    finally:
        sys.path.pop(0)
    output = root / (
        "trusted_data_synthesis/artifacts/qa_vnext_fixed_kernel_value/"
        "parallel_tail_execution_20260914"
    )
    frozen = module.p.read_json(output / "preparation/execution_freeze.json")
    selected = [
        next(
            row["task_id"] for row in frozen["evaluation_registry"]["dev"] if row["group"] == group
        )
        for group in module.GROUPS
    ]
    old_identity = module.p.read_json(output / "generation/dev/A_alpha0_11/model_identity.json")
    return module, frozen, selected, old_identity


def test_original_budget_and_honest_base_are_separate_from_alpha0():
    module, frozen, selected, old_identity = inputs()
    old_policy, old_system = module.original.policy(), module.runtime.SYSTEM
    bound = module.build_adapter(selected, frozen, "original")
    public = module.public_parent_binding(frozen)
    other = module.build_adapter(selected, public, "original")
    assert bound.transform_provenance["parent_execution_freeze_id"] == frozen["id"]
    assert other.transform_provenance["parent_execution_freeze_id"] == frozen["id"]
    assert bound.transform_provenance["id"] == other.transform_provenance["id"]
    assert bound.policy() == old_policy
    assert tuple(
        bound.policy()[key]
        for key in ("max_responses", "max_tools", "max_new_tokens", "maximum_sequence_length")
    ) == (32, 32, 2048, 24576)
    base = bound.make_model_identity(None, "synthetic_diagnostic_plan", "original")
    assert base == other.make_model_identity(None, "synthetic_diagnostic_plan", "original")
    assert base["model_kind"] == "unfinetuned_base"
    assert base["checkpoint_id"] == bound.base_checkpoint_identity["id"]
    assert all(
        base[key] is None
        for key in (
            "pool",
            "arm",
            "seed",
            "training_report_id",
            "final_adapter",
            "adapter_directory",
        )
    )
    assert base["training_configuration_id"] == "not_applicable:unfinetuned_base"
    assert bound.validate_model_identity(base) == base
    trained = bound.make_model_identity(old_identity, "synthetic_diagnostic_plan", "original")
    assert trained["model_kind"] == "finetuned"
    assert trained["checkpoint_id"] == old_identity["checkpoint_id"]
    assert trained["training_report_id"] == old_identity["training_report_id"]
    assert trained["parent_model_identity_id"] == old_identity["id"]
    assert bound.validate_model_identity(trained) == trained
    assert module.original.policy() == old_policy
    assert module.runtime.SYSTEM == old_system


def test_gamma_doc_changes_only_private_common_system_and_same_runtime_replay(monkeypatch):
    module, frozen, selected, _ = inputs()
    original_system = module.runtime.SYSTEM
    plain = module.build_adapter(selected, frozen, "original")
    documented = module.build_adapter(selected, frozen, "gamma_doc")
    assert plain.runtime.SYSTEM == original_system
    assert documented.runtime.SYSTEM == original_system + "\n\n" + module.GAMMA_DOC
    assert plain.policy() == documented.policy()
    assert plain.runtime.execute is documented.runtime.execute is module.runtime.execute
    assert (
        plain.bind_policy(frozen["tokenizer_binding"], frozen["base_binding"])["id"]
        != (documented.bind_policy(frozen["tokenizer_binding"], frozen["base_binding"])["id"])
    )
    monkeypatch.setitem(
        documented.runtime.generate.__globals__, "public_document", lambda *args: {}
    )
    sources = SimpleNamespace(descriptors=lambda: [])
    session = documented.runtime.generate(
        [{"role": "user", "content": "synthetic public task"}],
        {"task_id": "synthetic_task"},
        sources,
        scripted=["{}"] * 32,
    )
    assert len(session["turns"]) == 32
    assert session["terminal"] == "response_budget_exhausted"
    assert (
        session["initial_messages"][0]["content"]
        == documented.runtime.SYSTEM + "\nRequested guidance: neutral"
    )
    assert documented.replay_session(session, sources) == session
    assert documented.score.__globals__["assess_session"] is documented.assess_session
    assert module.runtime.SYSTEM == original_system


def test_prefix_is_one_raw_probe_continuation_without_gamma_or_eval_tool_runtime(tmp_path):
    module, _, _, _ = inputs()
    messages = [
        {"role": "system", "content": "ORIGINAL PROBE TRAINING TOOL CONTRACT"},
        {"role": "user", "content": "Only already supplied public history."},
    ]
    target = '{"final":{"value":"7","unit":"synthetic","result_id":"tool:1"}}'
    prefix = module.p.record(
        "delivery_training_prefix",
        input_messages=messages,
        reference_response=target,
        boundary="final",
        task_id="synthetic_task",
    )
    observed = {}

    class Tokenizer:
        def apply_chat_template(self, supplied, **options):
            observed["messages"] = supplied
            return "synthetic_rendered_original_history"

        def __call__(self, rendered, **options):
            return {"input_ids": [1, 2], "attention_mask": [1, 1]}

        def decode(self, tokens, **options):
            return target

    def generate(tokens, mask):
        observed["model_calls"] = observed.get("model_calls", 0) + 1
        return [tokens + [3, 99]]

    decoder = SimpleNamespace(
        tokenizer=Tokenizer(),
        _generate=generate,
        fatal_error=None,
        model=SimpleNamespace(training=False),
        identity={
            "id": "synthetic_model",
            "model_kind": "unfinetuned_base",
            "checkpoint_id": "synthetic_base",
        },
        load_receipt={"id": "synthetic_load"},
        configuration={"eos_token_ids": [99]},
        execution_kind=module.original.CONTROL,
    )
    result = module.predict_prefix(decoder, prefix, tmp_path / "prefix")
    assert observed["messages"] == messages
    assert observed["model_calls"] == 1
    assert all(module.GAMMA_DOC not in row["content"] for row in observed["messages"])
    assert all(target not in row["content"] for row in observed["messages"])
    assert result["exact_reference_response_match"] is True
    assert result["syntactic_top_level_final"] is True
    assert result["autonomous_task_success_claimed"] is False
    assert result["financial_qualification_score"] is None
    assert result["evaluation_tool_runtime_invocations"] == 0
    assert result["actual_GPU_generation_calls"] == 0
    assert result["synthetic_model_generation_calls"] == 1
