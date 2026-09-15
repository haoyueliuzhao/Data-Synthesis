"""New R1 wiring controls, not a rerun of the old nullable-query unit controls."""

import copy
import importlib
import os
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest


def inputs():
    root = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(root / "trusted_data_synthesis/scripts"))
    module = importlib.import_module("fixed_kernel_delivery_r1_adapter_20260915")
    frozen = module.p.read_json(root / module.PARENT / "preparation/execution_freeze.json")
    plan = module.p.read_json(root / module.BUDGET / "plan.json")
    return module, frozen, plan["pilot_task_ids"]


def test_R1_online_and_offline_fixture_replay_are_the_same_class(monkeypatch):
    module, frozen, tasks = inputs()
    before_system, before_class = module.runtime.SYSTEM, module.runtime.SnapshotSources
    adapter = module.build_adapter(tasks, frozen, "gamma_doc")
    sources = adapter.runtime.SnapshotSources.synthetic(
        {
            "s": {
                "facts": {
                    "us-gaap": {
                        "Revenue": {
                            "label": None,
                            "description": "Revenue",
                            "units": {"USD": [{"val": 3, "end": "2020-12-31"}]},
                        }
                    }
                }
            }
        }
    )
    public = {
        "question": "synthetic public question",
        "source_document": sources.descriptors()[0],
        "quantity_contract": {},
        "source_policy": {},
        "tool_contract": {},
        "period_contract": {"task_id": "synthetic"},
    }
    messages = [{"role": "user", "content": module.runtime.encode(public).decode()}]
    identity = {
        "task_id": "synthetic",
        "family": "dual_sufficient",
        "surface_version_id": "synthetic_surface",
        "public_messages_sha256": module.runtime.sha(module.runtime.encode(messages)),
        "parent_manifest_id": "synthetic_manifest",
    }
    supplied = [
        '{"tool":"query_source","arguments":{"source_id":"s","label_contains":"Revenue","unit":"USD"}}',
        '{"tool":"read_source","arguments":{"source_id":"s","native_pointer":"/facts/us-gaap/Revenue/units/USD/0"}}',
        '{"final":{"value":"3","unit":"USD","result_id":"tool:2"}}',
    ]
    session = adapter.runtime.generate(messages, identity, sources, scripted=supplied)
    assert session["events"][0]["tool_call"]["status"] == "ok"
    assert session["events"][1]["tool_call"]["result"]["exact_value"] == "3"
    assert adapter.replay_session(session, sources) == session
    assert session["tool_implementation_binding_id"] == adapter.tool_implementation_binding["id"]
    assert (
        adapter.offline_source_factory.__globals__["SnapshotSources"]
        is adapter.runtime.SnapshotSources
    )
    assert adapter.score.__globals__["assess_session"] is adapter.assess_session
    assert (
        adapter.score.__globals__["verify_generation_records"] is adapter.verify_generation_records
    )
    # Exercise the exact offline fixture constructor using only synthetic public
    # objects; no private finance task/answer is opened for this wiring check.
    monkeypatch.setitem(
        adapter.offline_source_factory.__globals__,
        "Parent",
        lambda *args: SimpleNamespace(read=lambda path: {}),
    )
    fake = SimpleNamespace(
        root=None,
        runtime_bundle=lambda key: {"public": {"source_document": sources.descriptors()[0]}},
        public=SimpleNamespace(
            public_envelope=lambda key: {"messages": messages, "identity": identity}
        ),
        tasks={
            "synthetic": {
                "original_bundle_reference": {
                    "parent_directory": "unused",
                    "parent_manifest_id": "synthetic",
                },
                "split": "dev",
            }
        },
    )
    fixture = adapter.offline_source_factory(fake, "synthetic")
    assert type(fixture["sources"]) is type(sources)
    fixture["sources"].payloads = copy.deepcopy(sources.payloads)
    assert adapter.replay_session(session, fixture["sources"]) == session
    assert module.runtime.SYSTEM == before_system and module.runtime.SnapshotSources is before_class


def test_R1_configuration_is_explicit_and_shared_load_counts_are_honest():
    module, frozen, tasks = inputs()
    plain = module.build_adapter(tasks, frozen, "original")
    documented = module.build_adapter(tasks, frozen, "gamma_doc")
    assert plain.runtime.SYSTEM == module.runtime.SYSTEM
    assert documented.runtime.SYSTEM == module.runtime.SYSTEM + "\n\n" + module.GAMMA_DOC
    assert plain.policy() == documented.policy() == module.original.policy()
    config = documented.bind_policy(frozen["tokenizer_binding"], frozen["base_binding"])
    assert config["R0_tool_execution_unchanged"] is False
    assert "original_tool_execution_unchanged" not in config
    identity = documented.make_model_identity(None, "synthetic_plan")
    physical = module.p.record(
        "model_load_receipt",
        model_identity_id="synthetic_first_condition",
        execution_kind=module.original.ACTUAL,
        restored_checkpoint_id=identity["checkpoint_id"],
        model_kind="unfinetuned_base",
        model_weight_loads=1,
        final_adapter_loads=0,
        tokenizer_loads=1,
        GPU_loads=1,
        base_binding_id=identity["base_binding_id"],
        tokenizer_binding_id=identity["tokenizer_binding_id"],
        tool_implementation_binding_id=plain.tool_implementation_binding["id"],
        process_id=os.getpid(),
        load_mode="physical_restore",
    )
    reused = module.make_reuse_receipt(physical, identity, documented.tool_implementation_binding)
    assert all(reused[key] == 0 for key in module.LOAD_FIELDS)
    documented.validate_load_receipt(reused, identity)
    changed = module.p.record(
        "model_load_receipt",
        **{
            **{key: value for key, value in reused.items() if key not in {"id", "schema_version"}},
            "model_weight_loads": 1,
        },
    )
    with pytest.raises(ValueError, match="zero_new_loads"):
        documented.validate_load_receipt(changed, identity)
    assert documented.transform_provenance["load_accounting_transforms"]


def test_decoder_cache_reset_prevents_previous_call_state_without_loading_a_model():
    module, frozen, tasks = inputs()
    adapter = module.build_adapter(tasks, frozen, "original")
    seen = {}

    class Cache:
        def reset(self):
            seen["reset"] = True

    class SyntheticModel:
        _cache = Cache()

        def generate(self, **kwargs):
            seen["kwargs"] = kwargs
            return [[1, 2, 3]]

    # Instance-local cache, just as the optional persistent generation cache.
    model = SyntheticModel()
    model._cache = Cache()
    decoder = SimpleNamespace(
        model=model,
        configuration={"eos_token_ids": [3], "pad_token_id": 0, "bos_token_id": None},
        execution_kind=module.original.CONTROL,
    )
    assert adapter.BoundDecoder._generate(decoder, [1, 2], [1, 1]) == [[1, 2, 3]]
    assert seen["reset"]
    assert "past_key_values" not in seen["kwargs"]
    assert seen["kwargs"]["max_new_tokens"] == 2048
