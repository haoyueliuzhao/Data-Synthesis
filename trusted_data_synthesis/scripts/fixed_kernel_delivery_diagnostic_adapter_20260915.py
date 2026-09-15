"""Prepared, not self-launching, fixed-checkpoint delivery diagnostic.

Only the common API documentation differs between the two complete-session
conditions.  Original tools, financial scoring, task envelopes, and the original
32/32/2048/24576 limits are retained.  Prefix continuation is a separate one-step
diagnostic over supplied public Probe history, never an autonomous evaluation.
"""

from __future__ import annotations

# ruff: noqa: E501 -- preserve the frozen common API wording and exact import targets
import ast
import copy
import inspect
import textwrap
import time
from collections import Counter
from pathlib import Path
from types import FunctionType, SimpleNamespace

import fixed_kernel_budget_reevaluation_adapter_20260915 as isolation

from trusted_synthesis.experiments.finance_qa_vnext_eval_readiness import assessment, runtime
from trusted_synthesis.experiments.finance_qa_vnext_eval_surface import overlay
from trusted_synthesis.experiments.finance_qa_vnext_fixed_kernel_value import evaluation as original
from trusted_synthesis.experiments.finance_qa_vnext_fixed_kernel_value import protocol as p

CONDITIONS = ("original", "gamma_doc")
GAMMA_DOC = """Public API clarification (the same for every task):
- query_source concept is an exact namespace:tag identifier from the public source, not a free-text metric name.
- label_contains filters concept labels/descriptions, not observation dates. The start and end arguments filter actual record dates.
- query_source unit matches the source's native unit string exactly; a requested answer unit is not automatically a source-query unit. Unit conversion belongs to supported reads/calculations.
- read_source native_pointer must be an actual pointer obtained from a public source return; do not invent a pointer from a year, metric name, or amount.
These clarifications do not identify any task's concept, evidence, answer, or solution method."""
GROUPS = ("dual_sufficient", "composition_required", "other_financial")
make_host_admission = isolation.make_host_admission
public_parent_binding = isolation.public_parent_binding


def _parent_id(parent):
    kind = parent.get("schema_version", "").rsplit(".", 1)[-1]
    p.require(
        kind in {"execution_freeze", "budget_parent_public_binding"},
        "delivery.explicit_parent_binding",
    )
    p.checked_record(parent, kind)
    # A full execution freeze may itself carry an older ancestor link.  Only
    # the projected public-parent record uses that field as its authority.
    return parent["id"] if kind == "execution_freeze" else parent["parent_execution_freeze_id"]


def base_checkpoint_identity(binding):
    return p.record(
        "delivery_base_checkpoint",
        base_binding_id=binding["id"],
        revision=binding["revision"],
        checkpoint_members=copy.deepcopy(binding["members"]),
        identity_basis="verified_original_base_files_and_loaded_tensor_schema_not_LoRA_digest",
        finetuning_applied=False,
        adapter_present=False,
    )


def _recompile(source, namespace, transform, provenance, name):
    tree = ast.parse(textwrap.dedent(inspect.getsource(source)))
    tree = transform.visit(tree)
    ast.fix_missing_locations(tree)
    temporary = dict(namespace)
    exec(compile(tree, source.__code__.co_filename + "[delivery-binding]", "exec"), temporary)
    compiled = temporary[source.__name__]
    result = FunctionType(compiled.__code__, namespace, source.__name__, source.__defaults__)
    result.__kwdefaults__ = copy.copy(source.__kwdefaults__)
    provenance.append(
        dict(
            function=source.__qualname__,
            transform=name,
            original_source_sha256=p.sha(inspect.getsource(source)),
            transformed_ast_sha256=p.sha(ast.dump(tree, include_attributes=False)),
        )
    )
    return result


def build_adapter(task_ids, parent_frozen, condition, host_admission=None):
    """Return load/generate/score and separate raw-prefix diagnostic interfaces."""
    p.require(condition in CONDITIONS, "delivery.registered_condition")
    parent_id = _parent_id(parent_frozen)
    ids = tuple(task_ids)
    registry = {row["task_id"]: row for row in parent_frozen["evaluation_registry"]["dev"]}
    p.require(
        len(ids) == 3 and len(set(ids)) == 3 and set(ids) <= set(registry),
        "delivery.exact_three_preselected_original_dev_tasks",
    )
    quotas = dict(Counter(registry[key]["group"] for key in ids))
    p.require(quotas == dict.fromkeys(GROUPS, 1), "delivery.one_task_per_group")
    base = parent_frozen["base_binding"]
    base_identity = base_checkpoint_identity(base)
    system = runtime.SYSTEM if condition == "original" else runtime.SYSTEM + "\n\n" + GAMMA_DOC
    provenance = []
    namespace = dict(vars(original))
    namespace["QUOTAS"] = {"dev": quotas}

    def policy():
        # Return the original limits, not the prior 64-response diagnostic.
        return original.policy()

    def bind_policy(tokenizer_binding, base_binding):
        config = original.bind_policy(tokenizer_binding, base_binding)
        return p.record(
            "decoder_config",
            **{
                **{
                    key: value
                    for key, value in config.items()
                    if key not in {"id", "schema_version"}
                },
                "delivery_diagnostic": True,
                "condition": condition,
                "runtime_system_prompt_sha256": p.sha(system + "\nRequested guidance: neutral"),
                "gamma_doc_sha256": p.sha(GAMMA_DOC) if condition == "gamma_doc" else None,
                "original_tool_execution_unchanged": True,
            },
        )

    def make_model_identity(old_identity_or_None, study_id, requested_condition=None):
        p.require(requested_condition in {None, condition}, "delivery.condition_identity_join")
        config = bind_policy(parent_frozen["tokenizer_binding"], base)
        if old_identity_or_None is None:
            fields = dict(
                pool=None,
                arm=None,
                seed=None,
                checkpoint_id=base_identity["id"],
                training_report_id=None,
                training_configuration_id="not_applicable:unfinetuned_base",
                final_adapter=None,
                adapter_directory=None,
                base_binding_id=base["id"],
                tokenizer_binding_id=parent_frozen["tokenizer_binding"]["id"],
                surface_manifest_id=original.SURFACE_MANIFEST_ID,
                kernel_id="not_applicable:base_not_trained_on_kernel",
            )
            kind, load_seed, parent_model = "unfinetuned_base", 11, None
        else:
            original.validate_model_identity(old_identity_or_None)
            p.require(
                old_identity_or_None["base_binding_id"] == base["id"], "delivery.same_original_base"
            )
            fields = {
                key: copy.deepcopy(value)
                for key, value in old_identity_or_None.items()
                if key not in {"id", "schema_version"}
            }
            kind, load_seed, parent_model = (
                "finetuned",
                fields["seed"],
                old_identity_or_None["id"],
            )
        fields.update(
            study_freeze_id=study_id,
            decoder_config_id=config["id"],
            model_kind=kind,
            condition=condition,
            load_seed=load_seed,
            parent_model_identity_id=parent_model,
            base_checkpoint_identity_id=base_identity["id"],
        )
        return p.record("delivery_model_identity", **fields)

    def validate_model_identity(identity):
        p.checked_record(identity, "delivery_model_identity")
        extras = {
            "model_kind",
            "condition",
            "load_seed",
            "parent_model_identity_id",
            "base_checkpoint_identity_id",
        }
        original_fields = {
            *original.BINDING_FIELDS,
            "pool",
            "arm",
            "seed",
            "checkpoint_id",
            "training_report_id",
            "final_adapter",
            "adapter_directory",
            "base_binding_id",
            "tokenizer_binding_id",
            "id",
            "schema_version",
        }
        p.require(
            set(identity) == original_fields | extras
            and identity["condition"] == condition
            and identity["base_binding_id"] == base["id"]
            and identity["base_checkpoint_identity_id"] == base_identity["id"],
            "delivery.closed_honest_model_identity",
        )
        if identity["model_kind"] == "finetuned":
            clean = p.record(
                "model_identity",
                **{
                    key: value
                    for key, value in identity.items()
                    if key not in extras | {"id", "schema_version"}
                },
            )
            original.validate_model_identity(clean)
            p.require(
                identity["load_seed"] == identity["seed"]
                and isinstance(identity["parent_model_identity_id"], str),
                "delivery.original_finetuned_checkpoint_lineage",
            )
        else:
            p.require(
                identity["model_kind"] == "unfinetuned_base"
                and identity["checkpoint_id"] == base_identity["id"]
                and identity["load_seed"] == 11
                and identity["training_configuration_id"] == "not_applicable:unfinetuned_base"
                and all(
                    identity[key] is None
                    for key in (
                        "pool",
                        "arm",
                        "seed",
                        "training_report_id",
                        "final_adapter",
                        "adapter_directory",
                        "parent_model_identity_id",
                    )
                ),
                "delivery.base_is_not_alpha0_or_a_training_result",
            )
        return identity

    def validate_load_receipt(receipt, identity):
        p.checked_record(receipt, "model_load_receipt")
        expected = 1 if identity["model_kind"] == "finetuned" else 0
        p.require(
            receipt["model_identity_id"] == identity["id"]
            and receipt["execution_kind"] == original.ACTUAL
            and receipt["restored_checkpoint_id"] == identity["checkpoint_id"]
            and receipt["model_kind"] == identity["model_kind"]
            and receipt["final_adapter_loads"] == expected
            and all(
                receipt[key] == 1 for key in ("model_weight_loads", "tokenizer_loads", "GPU_loads")
            ),
            "delivery.actual_base_or_finetuned_model_load",
        )

    def binding(identity):
        return {
            **original._binding(identity),
            "model_kind": identity["model_kind"],
            "condition": condition,
            "parent_model_identity_id": identity["parent_model_identity_id"],
        }

    holder = {}

    def record(kind, **fields):
        if kind in {"generation_registration", "generation_report", "evaluation_report"}:
            fields.update(
                delivery_diagnostic=True,
                condition=condition,
                parent_execution_freeze_id=parent_id,
                prospectively_selected_task_ids=list(ids),
                independent_training_value_confirmation=False,
                original_experiment_decision_replaced=False,
            )
        if kind == "generation_registration":
            fields["subset_catalog"] = copy.deepcopy(holder["catalog"])
        return p.record(kind, **fields)

    class SelectedPublicOverlay:
        def __init__(self, root=None, directory=None, expected_manifest_id=None, *, parent=None):
            self.original = (
                parent
                if parent is not None
                else overlay.PublicOverlay(root, directory, expected_manifest_id)
            )
            original_rows = {row["task_id"]: row for row in self.original.catalog["tasks"]}
            rows = [copy.deepcopy(original_rows[key]) for key in ids]
            p.require(
                all(
                    row["split"] == "dev"
                    and row["family"] == registry[row["task_id"]]["group"]
                    and all(
                        row[key] == registry[row["task_id"]][key]
                        for key in ("surface_version_id", "public_messages_sha256")
                    )
                    for row in rows
                ),
                "delivery.original_selected_public_metadata",
            )
            self.catalog = p.record(
                "delivery_subset_catalog",
                parent_catalog_id=self.original.catalog["id"],
                parent_surface_manifest_id=self.original.parent.manifest["id"],
                tasks=rows,
                task_count=len(rows),
                quotas={"dev": quotas},
                public_envelopes_unchanged=True,
            )
            holder["catalog"] = self.catalog
            self.parent, self.tasks = self.original.parent, {row["task_id"]: row for row in rows}

        def public_envelope(self, task_id):
            p.require(task_id in self.tasks, "delivery.selected_public_task")
            return self.original.public_envelope(task_id)

    class SelectedOfflineOverlay:
        def __init__(self, root, directory, expected_manifest_id):
            self.original = overlay.OfflineOverlay(root, directory, expected_manifest_id)
            self.public = SelectedPublicOverlay(parent=self.original.public)

        def fixture(self, task_id):
            p.require(task_id in self.public.tasks, "delivery.selected_offline_task")
            return self.original.fixture(task_id)

    runtime_globals = {**vars(runtime), "SYSTEM": system}
    runtime_generate = isolation.clone_function(
        runtime.generate, runtime_globals, provenance=provenance
    )
    private_runtime = SimpleNamespace(
        **{**vars(runtime), "SYSTEM": system, "generate": runtime_generate}
    )
    assessment_globals = {**vars(assessment), "generate": runtime_generate}
    replay = isolation.clone_function(
        assessment.replay_session, assessment_globals, provenance=provenance
    )
    assessment_globals["replay_session"] = replay
    assess = isolation.clone_function(
        assessment.assess_session, assessment_globals, provenance=provenance
    )
    namespace.update(
        policy=policy,
        bind_policy=bind_policy,
        validate_model_identity=validate_model_identity,
        validate_load_receipt=validate_load_receipt,
        _binding=binding,
        record=record,
        PublicOverlay=SelectedPublicOverlay,
        OfflineOverlay=SelectedOfflineOverlay,
        runtime=private_runtime,
        assess_session=assess,
    )

    def decoder_init(
        self,
        model,
        tokenizer,
        tokenizer_binding,
        model_identity,
        output,
        *,
        base_binding,
        configuration=None,
        execution_kind,
        load_receipt,
    ):
        validate_model_identity(model_identity)
        p.require(execution_kind in {original.ACTUAL, original.CONTROL}, "delivery.execution_kind")
        self.identity = copy.deepcopy(model_identity)
        self.model, self.tokenizer = model, tokenizer
        self.output, self.execution_kind = Path(output).absolute(), execution_kind
        self.configuration = bind_policy(tokenizer_binding, base_binding)
        p.require(
            configuration in (None, self.configuration)
            and self.identity["decoder_config_id"] == self.configuration["id"]
            and tokenizer.chat_template == tokenizer_binding["chat_template"]
            and all(
                getattr(tokenizer, key) == tokenizer_binding[key]
                for key in ("eos_token_id", "pad_token_id", "bos_token_id")
            ),
            "delivery.actual_tokenizer_and_condition_binding",
        )
        p.require(
            not any(path.is_symlink() for path in (self.output, *self.output.parents)),
            "delivery.non_symlink_decoder_output",
        )
        if execution_kind == original.ACTUAL:
            import torch

            validate_load_receipt(load_receipt, self.identity)
            p.require(
                isinstance(model, torch.nn.Module)
                and all(parameter.device.type == "cuda" for parameter in model.parameters()),
                "delivery.actual_loaded_GPU_model",
            )
            if self.identity["model_kind"] == "unfinetuned_base":
                p.require(
                    not any(".lora_" in name for name, _ in model.named_parameters()),
                    "delivery.unfinetuned_base_has_no_adapter",
                )
        else:
            p.checked_record(load_receipt, "model_load_receipt")
            p.require(
                all(
                    load_receipt[key] == 0
                    for key in (
                        "model_weight_loads",
                        "final_adapter_loads",
                        "tokenizer_loads",
                        "GPU_loads",
                    )
                ),
                "delivery.synthetic_never_actual_load",
            )
        self.load_receipt = copy.deepcopy(load_receipt)
        model.requires_grad_(False)
        model.eval()
        self.receipts, self.fatal_error = [], None
        self.counters = dict.fromkeys(
            (
                "callback_attempts",
                "tokenization_calls",
                "model_generate_api_calls",
                "actual_model_generation_calls",
                "synthetic_model_generation_calls",
                "actual_GPU_generation_calls",
                "completed_generation_calls",
                "context_rejections",
                "generated_tokens",
                "public_content_tokens",
                "callback_failures",
            ),
            0,
        )

    decoder_type = type(
        "DeliveryBoundDecoder",
        (),
        {
            "__init__": decoder_init,
            **{
                name: isolation.clone_function(
                    getattr(original.BoundDecoder, name), namespace, provenance=provenance
                )
                for name in ("snapshot", "_generate", "__call__")
            },
        },
    )
    namespace["BoundDecoder"] = decoder_type

    def load_decoder(root, output, identity, base_binding, tokenizer_binding, decoder_config):
        from trusted_synthesis.experiments.finance_qa_vnext_fixed_kernel_value import (
            trajectory_training,
        )
        from trusted_synthesis.experiments.finance_qa_vnext_pq_student import model as components
        from trusted_synthesis.experiments.qa_reasoning_share_training_preflight.tokenization import (
            load_tokenizer,
        )

        validate_model_identity(identity)
        p.require(not Path(output).exists(), "delivery.no_repeat_model_worker")
        p.require(
            base_binding == base
            and tokenizer_binding == parent_frozen["tokenizer_binding"]
            and decoder_config == bind_policy(tokenizer_binding, base_binding)
            and identity["decoder_config_id"] == decoder_config["id"],
            "delivery.exact_original_assets_and_condition",
        )
        if identity["model_kind"] == "finetuned":
            path = original.path_within(
                Path(root).resolve(),
                Path(identity["adapter_directory"]) / identity["final_adapter"]["path"],
            )
            loader = isolation._admitted_loader(host_admission)
            model, _ = loader(
                base_binding,
                identity["load_seed"],
                config=trajectory_training.training_config(),
                trainable=False,
                adapter_path=path,
                adapter_record=identity["final_adapter"],
            )
            restored = components.adapter_digest(model)
            p.require(restored == identity["checkpoint_id"], "delivery.restored_old_adapter_digest")
        else:
            loader = components.load_student
            if host_admission is not None:
                p.require(
                    type(host_admission) is isolation.HostAdmission
                    and host_admission._mint is isolation._HOST_MINT,
                    "delivery.trusted_spawn_base_admission",
                )

                def verify_admitted(value):
                    p.require(
                        value == host_admission.binding
                        and all(
                            isolation._signature(row["path"]) == row["signature"]
                            for row in host_admission.files
                        ),
                        "delivery.unchanged_once_verified_base",
                    )

                loader = isolation.clone_function(
                    loader, {**vars(components), "verify_checkpoint": verify_admitted}
                )
            model, scope = loader(base_binding, identity["load_seed"], trainable=False)
            p.require(scope is None, "delivery.no_adapters_installed_on_base")
            restored = base_identity["id"]
        tokenizer = load_tokenizer(tokenizer_binding)
        receipt = p.record(
            "model_load_receipt",
            model_identity_id=identity["id"],
            execution_kind=original.ACTUAL,
            restored_checkpoint_id=restored,
            model_kind=identity["model_kind"],
            model_weight_loads=1,
            final_adapter_loads=int(identity["model_kind"] == "finetuned"),
            tokenizer_loads=1,
            GPU_loads=1,
            base_binding_id=base_binding["id"],
            tokenizer_binding_id=tokenizer_binding["id"],
            base_checkpoint_identity=base_identity
            if identity["model_kind"] == "unfinetuned_base"
            else None,
            private_material_or_evaluation_bundle_opened=False,
            actual_base_verification_mode="one_parent_SHA_then_trusted_spawn_stat_identity"
            if host_admission is not None
            else "original_loader_full_SHA_safe_fallback",
        )
        return decoder_type(
            model,
            tokenizer,
            tokenizer_binding,
            identity,
            output,
            base_binding=base_binding,
            configuration=decoder_config,
            execution_kind=original.ACTUAL,
            load_receipt=receipt,
        )

    class AllowHonestBase(ast.NodeTransformer):
        changes = 0

        def visit_Compare(self, node):
            self.generic_visit(node)
            if ast.unparse(node) == "model_identity['pool'] == 'A'":
                self.changes += 1
                return ast.BoolOp(
                    op=ast.Or(),
                    values=[
                        node,
                        ast.parse(
                            "model_identity['model_kind'] == 'unfinetuned_base'", mode="eval"
                        ).body,
                    ],
                )
            return node

    generator_transform = AllowHonestBase()
    generate = _recompile(
        original.generate,
        namespace,
        generator_transform,
        provenance,
        "allow_honestly_identified_unfinetuned_base_on_dev",
    )
    p.require(generator_transform.changes == 1, "delivery.exact_base_admission_change")

    class HonestLoadCount(ast.NodeTransformer):
        changes = 0

        def visit_Expr(self, node):
            if isinstance(node.value, ast.Call) and any(
                isinstance(arg, ast.Constant)
                and arg.value == "evaluation.actual_final_model_and_tokenizer_loads"
                for arg in node.value.args
            ):
                self.changes += 1
                return ast.Expr(
                    value=ast.Call(
                        func=ast.Name(id="validate_load_receipt", ctx=ast.Load()),
                        args=[
                            ast.Name(id="load", ctx=ast.Load()),
                            ast.Name(id="identity", ctx=ast.Load()),
                        ],
                        keywords=[],
                    )
                )
            return self.generic_visit(node)

    load_transform = HonestLoadCount()
    verifier = _recompile(
        original.verify_generation_records,
        namespace,
        load_transform,
        provenance,
        "base_zero_adapter_or_finetuned_one_adapter_actual_load_check",
    )
    p.require(load_transform.changes == 1, "delivery.exact_load_receipt_check_change")
    namespace["verify_generation_records"] = verifier
    score = isolation._remove_local_imports(
        original.score,
        namespace,
        {
            (2, "finance_qa_vnext_eval_readiness.assessment", (("assess_session", None),)),
            (2, "finance_qa_vnext_eval_surface.overlay", (("OfflineOverlay", None),)),
        },
        provenance,
    )
    transform = p.record(
        "delivery_diagnostic_transform",
        parent_execution_freeze_id=parent_id,
        task_ids=list(ids),
        condition=condition,
        policy=policy(),
        system_prompt_sha256=p.sha(system + "\nRequested guidance: neutral"),
        gamma_doc_sha256=p.sha(GAMMA_DOC),
        function_transforms=provenance,
        source_files=[
            {"path": str(Path(module.__file__).resolve()), "sha256": p.sha(Path(module.__file__))}
            for module in (original, runtime, assessment, overlay, isolation)
        ],
        adapter_source_sha256=p.sha(Path(__file__)),
        original_tools_and_financial_qualification_unchanged=True,
        prior_budget_64_policy_reused=False,
        frozen_modules_modified=False,
        model_kind_explicit_base_is_not_alpha0=True,
        automatic_retry_expansion_training_or_B_restart=False,
    )
    return SimpleNamespace(
        policy=policy,
        bind_policy=bind_policy,
        make_model_identity=make_model_identity,
        validate_model_identity=validate_model_identity,
        load_decoder=load_decoder,
        generate=generate,
        score=score,
        BoundDecoder=decoder_type,
        runtime=private_runtime,
        replay_session=replay,
        assess_session=assess,
        verify_generation_records=verifier,
        transform_provenance=transform,
        base_checkpoint_identity=base_identity,
        predict_prefix=predict_prefix,
        actual_base_verification_mode="one_parent_SHA_then_trusted_spawn_stat_identity"
        if host_admission is not None
        else "original_loader_full_SHA_safe_fallback",
    )


def predict_prefix(decoder, prefix_record, output):
    """One exact Probe-history continuation; never call the evaluation runtime.

    Required public fields: input_messages, reference_response, boundary, plus an
    honest content-addressed record id.  All other prefix provenance is retained
    by its record ID/SHA.  The reference is only compared after generation.
    """
    kind = prefix_record.get("schema_version", "").rsplit(".", 1)[-1]
    p.checked_record(prefix_record, kind)
    messages = copy.deepcopy(prefix_record["input_messages"])
    p.require(
        messages
        and messages[0]["role"] == "system"
        and all(
            set(row) == {"role", "content"} and isinstance(row["content"], str) for row in messages
        ),
        "delivery.exact_original_Probe_public_history",
    )
    p.require(
        prefix_record["boundary"] in {"calculate", "final"}, "delivery.registered_prefix_boundary"
    )
    p.require(
        isinstance(prefix_record["reference_response"], str), "delivery.original_reference_response"
    )
    p.require(
        decoder.fatal_error is None and not decoder.model.training,
        "delivery.no_prefix_after_model_fault_or_with_dropout_enabled",
    )
    output = Path(output)
    p.require(not output.exists(), "delivery.one_prefix_callback_no_retry")
    rendered = decoder.tokenizer.apply_chat_template(
        messages, tokenize=False, add_generation_prompt=True
    )
    encoded = decoder.tokenizer(rendered, add_special_tokens=False, truncation=False, padding=False)
    tokens = encoded["input_ids"]
    mask = encoded.get("attention_mask", [1] * len(tokens))
    p.require(
        tokens and len(mask) == len(tokens) and all(value == 1 for value in mask),
        "delivery.full_unpadded_prefix_tokens",
    )
    p.write_once(
        output / "request.json",
        p.record(
            "delivery_prefix_request",
            prefix_record_id=prefix_record["id"],
            model_identity=decoder.identity,
            input_messages=messages,
            original_Probe_history_unchanged=True,
            gamma_doc_not_added=True,
            input_system_prompt_sha256=p.sha(messages[0]["content"]),
            rendered_prompt=rendered,
            input_token_ids=tokens,
            attention_mask=mask,
            reference_response_not_sent_to_model=True,
        ),
    )
    started = time.perf_counter()
    generated, content, raw, failure = [], [], None, None
    invoked = False
    if len(tokens) + 2048 > 24576:
        terminal = "context_rejected_before_model_generate"
    else:
        invoked = True
        try:
            sequence = decoder._generate(tokens, mask)
            p.require(
                len(sequence) == 1 and sequence[0][: len(tokens)] == tokens,
                "delivery.exact_prefix_preserved_by_generate",
            )
            generated = sequence[0][len(tokens) :]
            p.require(len(generated) <= 2048, "delivery.original_single_response_limit")
            ended = bool(generated) and generated[-1] in decoder.configuration["eos_token_ids"]
            content = generated[:-1] if ended else generated
            raw = decoder.tokenizer.decode(
                content, skip_special_tokens=False, clean_up_tokenization_spaces=False
            )
            terminal = (
                "actual_EOS"
                if ended
                else "new_token_limit"
                if len(generated) == 2048
                else "model_stopped_without_EOS"
            )
        except Exception as error:
            failure, terminal = type(error).__name__ + ": " + str(error), "decoder_error"
            decoder.fatal_error = failure
    parsed, parse_error = None, None
    if raw is not None:
        try:
            parsed = runtime.strict_json(raw)
        except (ValueError, TypeError) as error:
            parse_error = str(error)
    actual = decoder.execution_kind == original.ACTUAL
    result = p.record(
        "delivery_prefix_prediction",
        prefix_record_id=prefix_record["id"],
        prefix_record_sha256=p.sha(p.encode(prefix_record)),
        model_identity_id=decoder.identity["id"],
        model_kind=decoder.identity["model_kind"],
        checkpoint_id=decoder.identity["checkpoint_id"],
        model_load_receipt_id=decoder.load_receipt["id"],
        input_origin="fixed_public_Probe_training_history_not_Student_generated",
        boundary=prefix_record["boundary"],
        input_token_count=len(tokens),
        generated_token_ids=generated,
        public_content_token_ids=content,
        raw_response=raw,
        parsed_response=parsed,
        parse_error=parse_error,
        terminal=terminal,
        error=failure,
        reference_response=prefix_record["reference_response"],
        exact_reference_response_match=raw == prefix_record["reference_response"]
        if raw is not None
        else False,
        syntactic_top_level_final=isinstance(parsed, dict) and "final" in parsed,
        predicted_tool=parsed.get("tool") if isinstance(parsed, dict) else None,
        autonomous_task_success_claimed=False,
        financial_qualification_score=None,
        original_Probe_prefix_counted_as_Student_generation=False,
        evaluation_tool_runtime_invocations=0,
        original_training_tool_execution_performed=False,
        execution_kind=decoder.execution_kind,
        actual_model_generation_calls=int(invoked and actual),
        actual_GPU_generation_calls=int(invoked and actual),
        synthetic_model_generation_calls=int(invoked and not actual),
        elapsed_seconds=time.perf_counter() - started,
        policy=original.policy(),
        gamma_doc_applied_to_prefix=False,
    )
    p.write_once(output / "result.json", result)
    return result
