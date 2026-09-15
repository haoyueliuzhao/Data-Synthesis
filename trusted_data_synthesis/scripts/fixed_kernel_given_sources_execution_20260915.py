"""Actual fixed-checkpoint decoding and unchanged offline financial qualification.

Generation capabilities contain only new public source views and original model
assets. Private original TaskBundles enter the separate offline fixture loader.
The existing actual model.generate/callback receipt code is reused unmodified.
"""

import copy
import json
import os
from collections import Counter
from pathlib import Path

import fixed_kernel_budget_reevaluation_adapter_20260915 as isolation
import fixed_kernel_source_view_compact_20260915 as views
import fixed_kernel_source_view_compile_20260915 as compiler

from trusted_synthesis.experiments.finance_qa_vnext_fixed_kernel_value import evaluation as original
from trusted_synthesis.experiments.finance_qa_vnext_fixed_kernel_value import protocol as p

BASE = views.BASE
COUNTERS = (
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
)


def configuration(assets, manifest_id):
    bound = original.bind_policy(assets["tokenizer_binding"], assets["base_binding"])
    return p.record(
        "given_sources_decoder_config",
        **{key: value for key, value in bound.items() if key not in {"id", "schema_version"}},
        source_view_manifest_id=manifest_id,
        runtime_binding_id=views.binding()["id"],
        SYSTEM_sha256=p.sha(views.SYSTEM + "\nRequested guidance: neutral"),
        original_generation_options_and_flash_backend_unchanged=True,
    )


class Decoder(original.BoundDecoder):
    def __init__(self, model, tokenizer, identity, output, config, load_receipt, *, control=False):
        p.checked(identity, "given_sources_model_identity")
        p.checked(config, "given_sources_decoder_config")
        p.require(
            identity["decoder_config_id"] == config["id"]
            and identity["surface_manifest_id"] == config["source_view_manifest_id"],
            "given_sources.new_model_surface_and_decoder_identity",
        )
        self.model, self.tokenizer = model, tokenizer
        self.identity, self.configuration = copy.deepcopy(identity), copy.deepcopy(config)
        self.output, self.load_receipt = Path(output), copy.deepcopy(load_receipt)
        self.execution_kind = original.CONTROL if control else original.ACTUAL
        p.require(
            load_receipt["model_identity_id"] == identity["id"]
            and load_receipt["restored_checkpoint_id"] == identity["checkpoint_id"]
            and load_receipt["execution_kind"] == self.execution_kind,
            "given_sources.real_restore_identity",
        )
        if not control:
            import torch

            p.require(
                isinstance(model, torch.nn.Module)
                and all(parameter.device.type == "cuda" for parameter in model.parameters()),
                "given_sources.actual_GPU_model",
            )
        model.requires_grad_(False)
        model.eval()
        self.receipts, self.fatal_error = [], None
        self.counters = dict.fromkeys(COUNTERS, 0)

    def _generate(self, input_ids, attention_mask):
        cached = getattr(self.model, "_cache", None)
        if cached is not None:
            p.require(callable(getattr(cached, "reset", None)), "given_sources.resettable_cache")
            cached.reset()
            delattr(self.model, "_cache")
        return super()._generate(input_ids, attention_mask)

    def __call__(self, messages, context):
        p.require(
            messages[0]["content"] == views.SYSTEM + "\nRequested guidance: neutral",
            "given_sources.exact_fixed_SYSTEM",
        )
        return super().__call__(messages, context)


def load_decoder(root, output, identity, assets, host_admission):
    from trusted_synthesis.experiments.finance_qa_vnext_pq_student import model as components
    from trusted_synthesis.experiments.qa_reasoning_share_training_preflight.tokenization import (
        load_tokenizer,
    )

    root, output = Path(root).resolve(), Path(output)
    p.require(not output.exists(), "given_sources.one_model_restore_no_retry")
    base = assets["base_binding"]
    p.require(
        type(host_admission) is isolation.HostAdmission
        and host_admission._mint is isolation._HOST_MINT,
        "given_sources.trusted_once_admitted_base",
    )
    if identity["model_kind"] == "finetuned":
        old = identity["original_model_identity"]
        adapter_path = original.path_within(
            root, Path(old["adapter_directory"]) / old["final_adapter"]["path"]
        )
        model, _ = isolation._admitted_loader(host_admission)(
            base,
            old["seed"],
            trainable=False,
            adapter_path=adapter_path,
            adapter_record=old["final_adapter"],
        )
        restored = components.adapter_digest(model)
        p.require(
            restored == identity["checkpoint_id"], "given_sources.original_final_adapter_restored"
        )
    else:
        p.require(
            identity["model_kind"] == "unfinetuned_base"
            and identity["original_model_identity"] is None,
            "given_sources.base_not_alpha0",
        )

        def verify_admitted(binding):
            p.require(
                binding == host_admission.binding
                and all(
                    isolation._signature(row["path"]) == row["signature"]
                    for row in host_admission.files
                ),
                "given_sources.exact_once_verified_base_unchanged",
            )

        loader = isolation.clone_function(
            components.load_student, {**vars(components), "verify_checkpoint": verify_admitted}
        )
        model, scope = loader(base, 11, trainable=False)
        p.require(scope is None, "given_sources.no_adapter_on_base")
        restored = identity["checkpoint_id"]
    tokenizer = load_tokenizer(assets["tokenizer_binding"])
    config = configuration(assets, identity["surface_manifest_id"])
    p.require(
        config["id"] == identity["decoder_config_id"], "given_sources.frozen_actual_configuration"
    )
    receipt = p.record(
        "model_load_receipt",
        model_identity_id=identity["id"],
        model_kind=identity["model_kind"],
        restored_checkpoint_id=restored,
        execution_kind=original.ACTUAL,
        model_weight_loads=1,
        final_adapter_loads=int(identity["model_kind"] == "finetuned"),
        tokenizer_loads=1,
        GPU_loads=1,
        process_id=os.getpid(),
        base_binding_id=base["id"],
        tokenizer_binding_id=assets["tokenizer_binding"]["id"],
        base_SHA_admission="one_parent_SHA_then_trusted_spawn_stat_identity",
        actual_base_tensor_shape_dtype_and_device_checked_by_loader=True,
    )
    decoder = Decoder(model, tokenizer, identity, output, config, receipt)
    return decoder


def load_view(root, row, manifest_id):
    view = p.checked(p.read_json(Path(root) / row["path"]), "given_public_source_view_v2")
    p.require(
        view["id"] == row["surface_version_id"]
        and view["public_messages_sha256"] == row["public_messages_sha256"]
        and p.sha(p.encode(view["public_messages"])) == row["public_messages_sha256"],
        "given_sources.exact_frozen_public_view",
    )
    identity = {
        "task_id": row["task_id"],
        "family": row["group"],
        "surface_version_id": row["surface_version_id"],
        "public_messages_sha256": row["public_messages_sha256"],
        "parent_manifest_id": manifest_id,
    }
    return view, identity


def resource_from_session(session, identity, config):
    """One saved-session pass, not a repeated scan of cumulative callback requests."""
    result = Counter()
    for turn in session["turns"]:
        receipt = turn["provider_receipt"]
        p.checked(receipt, "decoder_receipt")
        p.require(
            receipt["model_identity_id"] == identity["id"]
            and receipt["checkpoint_id"] == identity["checkpoint_id"]
            and receipt["decoder_config_id"] == config["id"]
            and receipt["execution_kind"] == original.ACTUAL
            and receipt["model_generation_invoked"]
            and receipt["model_generation_completed"]
            and receipt["context"]["identity"] == session["identity"]
            and receipt["raw_response"] == turn["raw_response"]
            and receipt["raw_response_sha256"] == p.sha(turn["raw_response"])
            and not receipt["prompt_truncated"]
            and not receipt["host_JSON_repair"],
            "given_sources.actual_unchanged_response_receipt",
        )
        ids = receipt["generated_token_ids"]
        ended = bool(ids) and ids[-1] in config["eos_token_ids"]
        p.require(
            len(ids) <= 2048
            and receipt["generated_token_count"] == len(ids)
            and receipt["public_content_token_ids"] == (ids[:-1] if ended else ids)
            and receipt["actual_terminating_EOS_removed"] == ended,
            "given_sources.original_token_and_EOS_accounting",
        )
        result.update(actual_model_generation_calls=1, generated_tokens=len(ids))
    return dict(result)


def offline_assets(root, source_root, rows):
    p, _overlay, surface, Parent, safe_path, _old, _new = compiler.modules(root)
    parent = Parent(source_root, surface.PARENT_PANEL, surface.PARENT_PANEL_MANIFEST)
    cache = {}

    def read(path):
        return compiler.read_member(parent, path, p, safe_path, cache)

    catalog = read("panels/dev/catalog.json")
    registered = {row["task_id"]: row for row in catalog["tasks"]}
    bindings = read("panels/dev/native_bindings.json")
    bundles = {
        row["task_id"]: read("panels/dev/" + registered[row["task_id"]]["path"]) for row in rows
    }
    return {
        "bundles": bundles,
        "native_bindings": bindings,
        "private_uses": "offline_given_sources_sufficiency_and_scoring_only",
        "confirm_bundles_opened": 0,
    }


def fixture(root, row, manifest_id, private):
    view, identity = load_view(root, row, manifest_id)
    original_bundle = private["bundles"][row["task_id"]]
    public = json.loads(view["public_messages"][0]["content"])
    bundle = p.record(
        "given_sources_runtime_bundle",
        **{
            key: copy.deepcopy(value)
            for key, value in original_bundle.items()
            if key not in {"id", "schema_version", "public", "surface"}
        },
        public=public,
        surface={"id": view["id"], "public_messages_sha256": view["public_messages_sha256"]},
        original_bundle_id=original_bundle["id"],
        canonical_target_unchanged=True,
        conditional_utility_environment="J_sources_not_J_snapshot",
    )
    return {
        "bundle": bundle,
        "identity": identity,
        "messages": view["public_messages"],
        "sources": views.SourceViewSources(public),
        "native_bindings": private["native_bindings"],
    }


def financial_controls(root):
    """Three preselected development fixtures; four positive methods and one negative.

    Private witnesses construct explicit CPU controls only. No source-control script
    is sent to a Student or added to a training package.
    """
    from trusted_synthesis.experiments.finance_qa_vnext_eval_readiness import controls

    root = Path(root).resolve()
    output = root / BASE / "preflight"
    p.require(
        not (output / "financial_controls.json").exists(), "given_sources.single_financial_control"
    )
    manifest = p.read_json(root / BASE / "inputs_v2/manifest.json")
    selected = [
        min(
            (row for row in manifest["tasks"] if row["group"] == group),
            key=lambda row: row["task_id"],
        )
        for group in ("dual_sufficient", "composition_required", "other_financial")
    ]
    p.write_once(
        output / "control_selection.json",
        p.record(
            "given_sources_control_selection",
            source_view_manifest_id=manifest["id"],
            tasks=selected,
            rule="lexicographic first TaskID per fixed group before offline answer read",
            model_calls=0,
        ),
    )
    frozen = p.read_json(root / compiler.PARENT / "preparation/execution_freeze.json")
    private = offline_assets(root, Path(frozen["source_root"]), selected)
    fixtures = [fixture(root, row, manifest["id"], private) for row in selected]

    class Script(controls._Script):
        def query(self, fact_id):
            return None  # All source records are already supplied; no extra tool execution.

        def read(self, fact_id):
            if fact_id not in self.reads:
                native = self.fixture["native_bindings"][fact_id]
                matching = [
                    row["source_id"]
                    for row in self.fixture["sources"].references.values()
                    if row["raw_object_id"] == native["raw_object_id"]
                    and row["native_pointer"] == native["pointer"]
                ]
                p.require(len(matching) == 1, "given_sources.control_exact_public_pointer_mapping")
                self.reads[fact_id] = self.call(
                    "read_source", {"source_id": matching[0], "unit": "million USD"}
                )
            return self.reads[fact_id]

    namespace = {**vars(controls), "_Script": Script}
    namespace["_dual_script"] = isolation.clone_function(controls._dual_script, namespace)
    builder = isolation.clone_function(controls.source_bound_cases, namespace)
    allowed = {
        "dual_endpoint",
        "dual_movement",
        "mean_avg",
        "peak_lookup_dependency",
        "peak_only_secondary_hit",
    }
    cases = [case for case in builder(fixtures) if case["name"].rsplit(":", 1)[-1] in allowed]
    p.require(len(cases) == 5, "given_sources.five_necessary_contract_cases")
    bound, results = views.build_runtime(), []
    for index, case in enumerate(cases):
        f = case["fixture"]
        session = bound.generate(
            f["messages"],
            f["identity"],
            f["sources"],
            scripted=case["scripted"],
            requested_basis="neutral",
        )
        score = bound.assess_session(session, f["bundle"], f["native_bindings"], f["sources"])
        passed = score["financial_valid"] is case["expected_financial_valid"]
        p.write_once(output / "cases" / (str(index) + "_session.json"), session)
        p.write_once(output / "cases" / (str(index) + "_assessment.json"), score)
        results.append(
            dict(
                name=case["name"],
                passed=passed,
                expected=case["expected_financial_valid"],
                observed=score["financial_valid"],
                reason=score["reason"],
                session_id=session["id"],
                assessment_id=score["id"],
                model_output=False,
            )
        )
    report = p.record(
        "given_sources_financial_controls",
        passed=all(row["passed"] for row in results),
        results=results,
        model_calls=0,
        private_fixtures=3,
        scripts_added_to_training_or_model_inputs=False,
        runtime_binding=bound.binding,
        execution_script_sha256=p.sha(Path(__file__)),
        finished_at=p.now(),
    )
    p.write_once(output / "financial_controls.json", report)
    return report
