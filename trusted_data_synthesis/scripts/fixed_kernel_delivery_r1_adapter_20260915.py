"""Explicit R1 online/replay binding with fresh-condition shared-model decoders.

The old C adapter is compiled into a private namespace with a small, counted AST
revision. No old module, tool, experiment output, SYSTEM or GAMMA_DOC is changed.
The CLI runs only three task-independent public tool round trips, not a model.
"""

from __future__ import annotations

import argparse
import ast
import copy
import inspect
import json
import os
import resource
import subprocess
import textwrap
import time
from collections import Counter
from pathlib import Path
from types import SimpleNamespace

import fixed_kernel_delivery_diagnostic_adapter_20260915 as old
import fixed_kernel_query_null_repair_20260915 as repair

p = old.p
CONDITIONS = old.CONDITIONS
GAMMA_DOC = old.GAMMA_DOC
GROUPS = old.GROUPS
original = old.original
runtime = old.runtime
make_host_admission = old.make_host_admission
public_parent_binding = old.public_parent_binding
predict_prefix = old.predict_prefix
R1Sources = repair.repaired_snapshot_sources_class(runtime)
OUTPUT = Path(
    "trusted_data_synthesis/artifacts/qa_vnext_fixed_kernel_value/delivery_r1_contrast_20260915"
)
PARENT = Path(
    "trusted_data_synthesis/artifacts/qa_vnext_fixed_kernel_value/parallel_tail_execution_20260914"
)
BUDGET = Path(
    "trusted_data_synthesis/artifacts/qa_vnext_fixed_kernel_value/budget_reevaluation_20260915"
)
_OWNER_MINT = object()
LOAD_FIELDS = ("model_weight_loads", "final_adapter_loads", "tokenizer_loads", "GPU_loads")


def tool_binding():
    return p.record(
        "delivery_R1_tool_binding",
        original_runtime_sha256=p.sha(Path(runtime.__file__)),
        original_runtime_path=str(Path(runtime.__file__).resolve()),
        repair_version=repair.REPAIR_VERSION,
        repair_source_sha256=p.sha(Path(repair.__file__)),
        repair_source_path=str(Path(repair.__file__).resolve()),
        repaired_query_source_sha256=p.sha(inspect.getsource(R1Sources.query)),
        adapter_source_sha256=p.sha(Path(__file__)),
        online_source_class=R1Sources.__module__ + "." + R1Sources.__qualname__,
        offline_replay_source_class=R1Sources.__module__ + "." + R1Sources.__qualname__,
        online_and_replay_same_class=True,
        original_SYSTEM_sha256=p.sha(runtime.SYSTEM),
        original_GAMMA_DOC_sha256=p.sha(GAMMA_DOC),
        R0_tool_execution_unchanged=False,
        only_explicit_null_query_metadata_search_text_changes=True,
        financial_qualification_logic_unchanged=True,
        task_envelopes_and_decoder_limits_unchanged=True,
    )


def validate_r1_load_receipt(receipt, identity, binding):
    """Counts physical loads, not the number of condition-specific wrappers."""
    p.checked_record(receipt, "model_load_receipt")
    p.require(
        receipt["model_identity_id"] == identity["id"]
        and receipt["execution_kind"] == original.ACTUAL
        and receipt["restored_checkpoint_id"] == identity["checkpoint_id"]
        and receipt["model_kind"] == identity["model_kind"]
        and receipt["tool_implementation_binding_id"] == binding["id"],
        "R1.actual_identity_checkpoint_and_tool_load_binding",
    )
    mode = receipt["load_mode"]
    if mode == "physical_restore":
        expected = dict.fromkeys(LOAD_FIELDS, 1)
        expected["final_adapter_loads"] = int(identity["model_kind"] == "finetuned")
        p.require(
            all(receipt[key] == value for key, value in expected.items())
            and type(receipt["process_id"]) is int,
            "R1.exact_one_physical_base_or_finetuned_restore",
        )
    else:
        p.require(mode == "same_process_shared_model", "R1.explicit_shared_load_mode")
        physical = receipt["physical_load_receipt"]
        p.checked_record(physical, "model_load_receipt")
        expected = dict.fromkeys(LOAD_FIELDS, 1)
        expected["final_adapter_loads"] = int(identity["model_kind"] == "finetuned")
        p.require(
            all(receipt[key] == 0 for key in LOAD_FIELDS)
            and physical["load_mode"] == "physical_restore"
            and all(physical[key] == value for key, value in expected.items())
            and physical["execution_kind"] == original.ACTUAL
            and physical["restored_checkpoint_id"] == identity["checkpoint_id"]
            and physical["model_kind"] == identity["model_kind"]
            and physical["tool_implementation_binding_id"] == binding["id"]
            and physical["process_id"] == receipt["process_id"]
            and physical["base_binding_id"] == receipt["base_binding_id"]
            and physical["tokenizer_binding_id"] == receipt["tokenizer_binding_id"]
            and receipt["fresh_decoder_state"] is True
            and receipt["previous_condition_history_reused"] is False,
            "R1.zero_new_loads_bound_to_same_process_real_restore",
        )


def make_reuse_receipt(physical, identity, binding):
    receipt = p.record(
        "model_load_receipt",
        model_identity_id=identity["id"],
        execution_kind=original.ACTUAL,
        restored_checkpoint_id=identity["checkpoint_id"],
        model_kind=identity["model_kind"],
        **dict.fromkeys(LOAD_FIELDS, 0),
        base_binding_id=identity["base_binding_id"],
        tokenizer_binding_id=identity["tokenizer_binding_id"],
        tool_implementation_binding_id=binding["id"],
        process_id=os.getpid(),
        load_mode="same_process_shared_model",
        physical_load_receipt=copy.deepcopy(physical),
        fresh_decoder_state=True,
        previous_condition_history_reused=False,
        past_key_values_from_previous_call_supplied=False,
        physical_counts_are_not_logical_wrapper_counts=True,
    )
    validate_r1_load_receipt(receipt, identity, binding)
    return receipt


class _BuilderRevision(ast.NodeTransformer):
    def __init__(self):
        self.changes = Counter()
        self.scope = []

    def visit_FunctionDef(self, node):
        if node.name == "validate_load_receipt":
            self.changes["honest_physical_or_shared_load_validator"] += 1
            node.body = ast.parse(
                "return validate_r1_load_receipt(receipt, identity, R1_BINDING)"
            ).body
            return node
        self.scope.append(node.name)
        self.generic_visit(node)
        self.scope.pop()
        if node.name == "validate_model_identity":
            self.changes["identity_matches_exact_R1_configuration"] += 1
            node.body.insert(
                -1,
                ast.parse(
                    "p.require(identity['decoder_config_id'] == "
                    "bind_policy(parent_frozen['tokenizer_binding'], base)['id'], "
                    "'R1.identity_requires_this_tool_and_condition_configuration')"
                ).body[0],
            )
        return node

    def visit_Dict(self, node):
        self.generic_visit(node)
        for i, key in enumerate(node.keys):
            if isinstance(key, ast.Constant) and key.value == "original_tool_execution_unchanged":
                self.changes["explicit_R1_decoder_configuration"] += 1
                node.keys[i] = ast.Constant("R0_tool_execution_unchanged")
                node.values[i] = ast.Constant(False)
                node.keys.extend(
                    [
                        ast.Constant("tool_implementation_binding_id"),
                        ast.Constant("tool_implementation_binding"),
                    ]
                )
                node.values.extend(
                    [
                        ast.parse("R1_BINDING['id']", mode="eval").body,
                        ast.Name("R1_BINDING", ast.Load()),
                    ]
                )
                break
        return node

    def visit_Call(self, node):
        self.generic_visit(node)
        if (
            ast.unparse(node.func) == "p.record"
            and node.args
            and isinstance(node.args[0], ast.Constant)
            and node.args[0].value == "model_load_receipt"
        ):
            self.changes["physical_restore_receipt"] += 1
            node.keywords.extend(
                [
                    ast.keyword("load_mode", ast.Constant("physical_restore")),
                    ast.keyword("process_id", ast.parse("R1_OS.getpid()", mode="eval").body),
                    ast.keyword(
                        "tool_implementation_binding_id",
                        ast.parse("R1_BINDING['id']", mode="eval").body,
                    ),
                ]
            )
        if self.scope and self.scope[-1] == "record" and ast.unparse(node.func) == "fields.update":
            self.changes["generation_score_record_tool_binding"] += 1
            node.keywords.append(
                ast.keyword(
                    "tool_implementation_binding_id",
                    ast.parse("R1_BINDING['id']", mode="eval").body,
                )
            )
        for keyword in node.keywords:
            if keyword.arg == "original_tools_and_financial_qualification_unchanged":
                self.changes["honest_R1_transform_identity"] += 1
                keyword.arg, keyword.value = "R0_tool_execution_unchanged", ast.Constant(False)
                node.keywords.extend(
                    [
                        ast.keyword("financial_qualification_logic_unchanged", ast.Constant(True)),
                        ast.keyword(
                            "tool_implementation_binding", ast.Name("R1_BINDING", ast.Load())
                        ),
                    ]
                )
                break
        return node


class _LoadAccounting(ast.NodeTransformer):
    def __init__(self):
        self.load_check = 0
        self.usage_changes = 0

    def visit_Expr(self, node):
        if isinstance(node.value, ast.Call) and any(
            isinstance(arg, ast.Constant)
            and arg.value == "evaluation.actual_final_model_and_tokenizer_loads"
            for arg in node.value.args
        ):
            self.load_check += 1
            return ast.parse("validate_load_receipt(load, identity)").body[0]
        return self.generic_visit(node)

    def visit_Compare(self, node):
        self.generic_visit(node)
        for usage_field, load_field in (
            ("model_weight_loads", "model_weight_loads"),
            ("final_adapter_loads", "final_adapter_loads"),
            ("tokenizer_loads", "tokenizer_loads"),
            ("GPU_model_loads", "GPU_loads"),
        ):
            if ast.unparse(node) == f"usage['{usage_field}'] == 1":
                self.usage_changes += 1
                return ast.parse(
                    f"usage['{usage_field}'] == load['{load_field}']", mode="eval"
                ).body
        return node


def build_adapter(task_ids, parent_frozen, condition, host_admission=None):
    binding = tool_binding()
    r1_runtime = SimpleNamespace(**{**vars(runtime), "SnapshotSources": R1Sources})

    def bound_runtime_record(kind, **fields):
        if kind == "evaluation_session":
            fields["tool_implementation_binding_id"] = binding["id"]
        return runtime.record(kind, **fields)

    r1_runtime.record = bound_runtime_record
    fixture_globals = {**vars(old.overlay), "SnapshotSources": R1Sources}
    fixture = old.isolation.clone_function(old.overlay.OfflineOverlay.fixture, fixture_globals)
    offline_type = type("R1OfflineOverlay", (old.overlay.OfflineOverlay,), {"fixture": fixture})
    r1_overlay = SimpleNamespace(**{**vars(old.overlay), "OfflineOverlay": offline_type})
    tree = ast.parse(textwrap.dedent(inspect.getsource(old.build_adapter)))
    revision = _BuilderRevision()
    tree = revision.visit(tree)
    ast.fix_missing_locations(tree)
    p.require(
        revision.changes
        == Counter(
            dict.fromkeys(
                (
                    "honest_physical_or_shared_load_validator",
                    "identity_matches_exact_R1_configuration",
                    "explicit_R1_decoder_configuration",
                    "physical_restore_receipt",
                    "generation_score_record_tool_binding",
                    "honest_R1_transform_identity",
                ),
                1,
            )
        ),
        "R1.exact_private_C_builder_revision_sites",
    )
    namespace = {
        **vars(old),
        "runtime": r1_runtime,
        "overlay": r1_overlay,
        "R1_BINDING": binding,
        "R1_OS": os,
        "validate_r1_load_receipt": validate_r1_load_receipt,
        "__file__": __file__,
    }
    exec(compile(tree, __file__ + "[R1-private-C-builder]", "exec"), namespace)
    adapter = namespace["build_adapter"](task_ids, parent_frozen, condition, host_admission)
    # Old C only replaced the initial load check. Its final aggregate check also
    # needs honest base=0 / reused=0 adapter accounting, without weakening joins.
    accounting = _LoadAccounting()
    provenance = []
    verification = old._recompile(
        original.verify_generation_records,
        adapter.generate.__globals__,
        accounting,
        provenance,
        "actual_restore_or_shared_zero_counts_match_saved_load_receipt",
    )
    p.require(
        accounting.load_check == 1 and accounting.usage_changes == 4,
        "R1.exact_load_accounting_sites",
    )
    adapter.generate.__globals__["verify_generation_records"] = verification
    adapter.verify_generation_records = verification
    original_loader = adapter.load_decoder
    raw_generate = adapter.BoundDecoder._generate

    def fresh_generate(self, input_ids, attention_mask):
        # The normal decoder supplies no past_key_values and creates one fresh
        # GenerationConfig per call. Remove any optional persistent HF cache too.
        cached = getattr(self.model, "_cache", None)
        if cached is not None:
            reset = getattr(cached, "reset", None)
            p.require(callable(reset), "R1.known_resettable_persistent_generation_cache")
            reset()
            delattr(self.model, "_cache")
        return raw_generate(self, input_ids, attention_mask)

    adapter.BoundDecoder._generate = fresh_generate

    def load_decoder(root, output, identity, base_binding, tokenizer_binding, decoder_config):
        decoder = original_loader(
            root, output, identity, base_binding, tokenizer_binding, decoder_config
        )
        decoder._r1_owner = SimpleNamespace(
            mint=_OWNER_MINT,
            process_id=os.getpid(),
            model=decoder.model,
            tokenizer=decoder.tokenizer,
            physical_receipt=copy.deepcopy(decoder.load_receipt),
            conditions={condition},
            checkpoint_id=identity["checkpoint_id"],
            study_freeze_id=identity["study_freeze_id"],
        )
        return decoder

    def reuse_decoder(existing_decoder, root, output, identity, configuration):
        adapter.validate_model_identity(identity)
        root, output = Path(root).resolve(), Path(output).absolute()
        p.require(
            output.is_relative_to(root) and not output.exists(), "R1.new_condition_decoder_output"
        )
        owner = getattr(existing_decoder, "_r1_owner", None)
        p.require(
            owner is not None
            and owner.mint is _OWNER_MINT
            and owner.process_id == os.getpid()
            and owner.model is existing_decoder.model
            and owner.tokenizer is existing_decoder.tokenizer
            and owner.checkpoint_id == identity["checkpoint_id"]
            and owner.study_freeze_id == identity["study_freeze_id"]
            and existing_decoder.execution_kind == original.ACTUAL
            and existing_decoder.fatal_error is None
            and not existing_decoder.model.training
            and condition not in owner.conditions
            and len(owner.conditions) == 1,
            "R1.only_second_condition_reuses_same_actual_worker_model",
        )
        config = adapter.bind_policy(
            parent_frozen["tokenizer_binding"], parent_frozen["base_binding"]
        )
        p.require(configuration == config, "R1.exact_reused_condition_decoder_config")
        receipt = make_reuse_receipt(owner.physical_receipt, identity, binding)
        decoder = adapter.BoundDecoder(
            owner.model,
            owner.tokenizer,
            parent_frozen["tokenizer_binding"],
            identity,
            output,
            base_binding=parent_frozen["base_binding"],
            configuration=config,
            execution_kind=original.ACTUAL,
            load_receipt=receipt,
        )
        decoder._r1_owner = owner
        owner.conditions.add(condition)
        p.require(
            not decoder.receipts
            and not any(decoder.counters.values())
            and decoder.fatal_error is None,
            "R1.fresh_decoder_not_old_history_or_counters",
        )
        return decoder

    adapter.load_decoder, adapter.reuse_decoder = load_decoder, reuse_decoder
    adapter.tool_implementation_binding = binding
    adapter.offline_source_factory = fixture
    adapter.validate_load_receipt = lambda receipt, identity: validate_r1_load_receipt(
        receipt, identity, binding
    )
    adapter.transform_provenance = p.record(
        "delivery_R1_transform",
        tool_implementation_binding=binding,
        previous_C_source_sha256=p.sha(Path(old.__file__)),
        previous_C_builder_sha256=p.sha(inspect.getsource(old.build_adapter)),
        compiled_private_builder_ast_sha256=p.sha(ast.dump(tree, include_attributes=False)),
        counted_revision_sites=dict(revision.changes),
        transformed_C_provenance=adapter.transform_provenance,
        load_accounting_transforms=provenance,
        generation_source_class_is_replay_source_class=True,
        source_class_binding_from_actual_fixture_globals=fixture.__globals__["SnapshotSources"]
        is R1Sources,
        history_tool_outputs_and_decoder_counters_new_per_condition=True,
        model_generate_never_receives_previous_call_past_key_values=True,
        optional_persistent_generation_cache_reset_each_call=True,
        original_SYSTEM_and_existing_GAMMA_DOC_reused_verbatim=True,
        original_modules_modified=False,
    )
    return adapter


def _select_numeric(payload):
    """Task-blind lexical first legal numeric source record; no private fixture."""
    from trusted_synthesis.experiments.finance_qa_vnext_catalog_bridge.worker import UNITS

    for namespace, concepts in sorted(payload.get("facts", {}).items()):
        for tag, concept in sorted(concepts.items()):
            for unit, values in sorted(concept.get("units", {}).items()):
                if unit not in UNITS:
                    continue
                for index, raw in enumerate(values):
                    try:
                        runtime.actual_period(raw)
                        value = runtime.number(raw["val"])
                    except (ValueError, TypeError, KeyError, ArithmeticError):
                        continue
                    # The frozen exact calculator returns Fraction, whose
                    # accepted numerator/denominator already imply finiteness.
                    if value.denominator != 0:
                        return namespace + ":" + tag, unit, index, raw
    raise ValueError("R1.no_legal_public_numeric_record_for_positive_control")


def preflight(root, output):
    root, output = Path(root).resolve(), Path(output).resolve()
    p.require(
        output == root / OUTPUT / "preflight" and not output.exists(),
        "R1.new_unique_preflight_directory",
    )
    started, usage_before = time.monotonic(), resource.getrusage(resource.RUSAGE_SELF)
    frozen = p.read_json(root / PARENT / "preparation/execution_freeze.json")
    old_plan = p.read_json(root / BUDGET / "plan.json")
    task_ids = old_plan["pilot_task_ids"]
    adapter = build_adapter(task_ids, frozen, "original")
    other = build_adapter(task_ids, frozen, "gamma_doc")
    p.require(
        adapter.runtime.SnapshotSources is other.runtime.SnapshotSources is R1Sources,
        "R1.two_conditions_same_sources_class",
    )
    source_root = Path(frozen["source_root"]).resolve()
    public = old.overlay.PublicOverlay(
        source_root, original.SURFACE_DIRECTORY, original.SURFACE_MANIFEST_ID
    )
    outcomes, seen_sources = [], set()
    snapshot_bytes = 0
    for task_id in task_ids:
        envelope = public.public_envelope(task_id)
        visible = json.loads(envelope["messages"][0]["content"])
        descriptors = visible["source_document"]
        descriptors = [descriptors] if isinstance(descriptors, dict) else descriptors
        p.require(len(descriptors) == 1, "R1.exact_one_snapshot_per_fixed_task")
        descriptor = descriptors[0]
        source_id = descriptor["source_id"]
        p.require(source_id not in seen_sources, "R1.three_distinct_fixed_public_snapshots")
        seen_sources.add(source_id)
        sources = R1Sources(source_root, descriptors)
        payload = sources._payload(source_id)  # Exactly one file read/SHA per source.
        metadata = descriptor["complete_original_snapshot"]
        snapshot_bytes += metadata["bytes"]
        concept, unit, index, raw = _select_numeric(payload)
        arguments = {
            "source_id": source_id,
            "concept": concept,
            "unit": unit,
            "offset": index,
            "limit": 1,
        }
        queried = sources.query(arguments)
        p.require(len(queried["records"]) == 1, "R1.positive_query_one_record")
        returned = queried["records"][0]
        read_arguments = {
            "source_id": source_id,
            "native_pointer": returned["native_pointer"],
            "unit": unit,
        }
        read = sources.read_source(read_arguments)
        p.require(
            read["record"] == raw == returned["record"]
            and read["exact_value"] == str(runtime.number(raw["val"]))
            and read["native_pointer"] == returned["native_pointer"],
            "R1.actual_query_pointer_numeric_read_round_trip",
        )
        outcomes.append(
            {
                "task_id_for_snapshot_binding_only": task_id,
                "surface_version_id": envelope["identity"]["surface_version_id"],
                "public_messages_sha256": envelope["identity"]["public_messages_sha256"],
                "source_id": source_id,
                "public_snapshot": copy.deepcopy(metadata),
                "query_arguments_offline_only": arguments,
                "query_total": queried["total"],
                "returned_record_pointer_offline_only": returned["native_pointer"],
                "read_arguments_offline_only": read_arguments,
                "exact_value_offline_only": read["exact_value"],
                "unit": read["unit"],
                "query_result_sha256": p.sha(p.encode(queried)),
                "read_result_sha256": p.sha(p.encode(read)),
                "status": "PASS_QUERY_RETURNED_POINTER_NUMERIC_READ",
                "model_input_modified": False,
                "task_answer_correctness_assessed": False,
            }
        )
    usage_after = resource.getrusage(resource.RUSAGE_SELF)
    report = p.record(
        "delivery_R1_preflight",
        status="PASS_THREE_FIXED_SNAPSHOT_ROUND_TRIPS",
        actual_complete=True,
        code_commit=subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=root, text=True
        ).strip(),
        adapter_source_sha256=p.sha(Path(__file__)),
        tool_implementation_binding=adapter.tool_implementation_binding,
        condition_transforms={
            "original": adapter.transform_provenance,
            "gamma_doc": other.transform_provenance,
        },
        conditions_use_same_R1_tools=True,
        pilot_plan_id=old_plan["id"],
        task_ids=task_ids,
        selection_rule=(
            "lexicographic namespace/tag/native-unit/index; native unit supported, finite numeric "
            "val and valid original actual period; independent of task question/answer"
        ),
        public_source_root=str(source_root),
        outcomes=outcomes,
        snapshot_files_read=3,
        snapshot_file_bytes=snapshot_bytes,
        query_calls=3,
        read_source_calls=3,
        old_runtime_sessions_read=0,
        callback_files_read=0,
        model_loads=0,
        model_generation_calls=0,
        source_control_values_not_injected_into_model_inputs=True,
        financial_scoring_not_performed=True,
        elapsed_seconds=time.monotonic() - started,
        CPU_user_seconds=usage_after.ru_utime - usage_before.ru_utime,
        CPU_system_seconds=usage_after.ru_stime - usage_before.ru_stime,
        max_RSS_KiB=usage_after.ru_maxrss,
    )
    p.write_once(output / "report.json", report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    output = args.output or args.root / OUTPUT / "preflight"
    report = preflight(args.root, output)
    print(
        json.dumps(
            {
                "id": report["id"],
                "status": report["status"],
                "snapshot_bytes": report["snapshot_file_bytes"],
            }
        )
    )


if __name__ == "__main__":
    main()
