"""Isolated budget-only evaluation over prospectively registered old checkpoints.

The frozen modules are never edited or monkeypatched.  Small, allowlisted code
objects receive budget constants in private global dictionaries; tool execution,
public wording, financial qualification, and raw-history replay are retained.
The caller owns a new study identity, checkpoint registration, output directory,
task-selection record, scheduler, and publication.  This module does not train,
select successful tasks, or authorize the original experiment's B stage.
"""

from __future__ import annotations

import ast
import copy
import hashlib
import inspect
import marshal
import textwrap
from collections import Counter
from pathlib import Path
from types import CodeType, FunctionType, SimpleNamespace

from trusted_synthesis.experiments.finance_qa_vnext_eval_readiness import assessment, runtime
from trusted_synthesis.experiments.finance_qa_vnext_eval_surface import overlay
from trusted_synthesis.experiments.finance_qa_vnext_fixed_kernel_value import evaluation as original
from trusted_synthesis.experiments.finance_qa_vnext_fixed_kernel_value import protocol as p

MAX_RESPONSES = 64
MAX_TOOLS = 64
MAX_NEW_TOKENS = 4096
MAXIMUM_SEQUENCE_LENGTH = 32768
GROUPS = ("dual_sufficient", "composition_required", "other_financial")
_HOST_MINT = object()


def _code_digest(code):
    return hashlib.sha256(marshal.dumps(code)).hexdigest()


def budget_code(code, replacements, *, changes=None):
    """Replace only exact typed constants; preserve instructions and all names."""
    changed = [] if changes is None else changes
    constants = []
    for index, value in enumerate(code.co_consts):
        if isinstance(value, CodeType):
            replacement = budget_code(value, replacements, changes=changed)
        else:
            replacement = value
            for old, new in replacements:
                if type(value) is type(old) and value == old:
                    replacement = new
                    changed.append(
                        {"function": code.co_qualname, "index": index, "old": old, "new": new}
                    )
                    break
        constants.append(replacement)
    return code.replace(co_consts=tuple(constants))


def clone_function(source, namespace, replacements=(), *, provenance=None):
    changes = []
    code = budget_code(source.__code__, replacements, changes=changes)
    result = FunctionType(code, namespace, source.__name__, source.__defaults__, source.__closure__)
    result.__kwdefaults__ = copy.copy(source.__kwdefaults__)
    result.__annotations__ = copy.copy(source.__annotations__)
    result.__qualname__ = source.__qualname__
    result.__doc__ = source.__doc__
    if provenance is not None:
        provenance.append(
            {
                "function": source.__module__ + "." + source.__qualname__,
                "method": "private_globals_and_exact_typed_co_consts",
                "original_code_sha256": _code_digest(source.__code__),
                "bound_code_sha256": _code_digest(code),
                "constant_changes": changes,
                "instruction_bytes_unchanged": source.__code__.co_code == code.co_code,
            }
        )
    return result


def _remove_local_imports(source, namespace, allowed, provenance):
    """Rebind explicitly named capabilities, leaving the function body intact."""
    tree = ast.parse(textwrap.dedent(inspect.getsource(source)))
    expected = set(allowed)
    removed = []

    class RemoveImports(ast.NodeTransformer):
        def visit_ImportFrom(self, node):
            key = (node.level, node.module, tuple((row.name, row.asname) for row in node.names))
            if key in expected:
                removed.append(key)
                return None
            return node

    bound = RemoveImports().visit(tree)
    p.require(
        len(removed) == len(expected) and set(removed) == expected,
        "budget.exact_local_import_rebindings",
    )
    ast.fix_missing_locations(bound)
    compiled = compile(bound, source.__code__.co_filename + "[budget-import-binding]", "exec")
    temporary = dict(namespace)
    exec(compiled, temporary)
    temporary_function = temporary[source.__name__]
    result = FunctionType(
        temporary_function.__code__,
        namespace,
        source.__name__,
        source.__defaults__,
        source.__closure__,
    )
    result.__kwdefaults__ = copy.copy(source.__kwdefaults__)
    provenance.append(
        {
            "function": source.__module__ + "." + source.__qualname__,
            "method": "AST_remove_only_named_ImportFrom_nodes",
            "removed_imports": [list(row) for row in removed],
            "original_source_sha256": p.sha(inspect.getsource(source)),
            "bound_ast_sha256": p.sha(ast.dump(bound, include_attributes=False)),
            "financial_or_runtime_body_statements_changed": False,
        }
    )
    return result


def policy():
    parent = original.policy()
    fields = {key: value for key, value in parent.items() if key not in {"id", "schema_version"}}
    fields.update(
        max_responses=MAX_RESPONSES,
        max_tools=MAX_TOOLS,
        max_new_tokens=MAX_NEW_TOKENS,
        maximum_sequence_length=MAXIMUM_SEQUENCE_LENGTH,
        context_admission="full prompt tokens plus all 4096 reserved new tokens <=32768",
    )
    return p.record("decoder_policy", **fields)


def _signature(path):
    value = Path(path).stat()
    return [value.st_dev, value.st_ino, value.st_size, value.st_mtime_ns, value.st_ctime_ns]


class HostAdmission:
    """Only a trusted parent process may mint the checkpoint SHA admission."""

    def __init__(self, binding, files, *, mint):
        p.require(mint is _HOST_MINT, "budget.private_parent_admission")
        self._mint = mint
        self.binding = copy.deepcopy(binding)
        self.files = copy.deepcopy(files)

    def __reduce__(self):
        return _restore_host_admission, (self.binding, self.files)


def _restore_host_admission(binding, files):
    # Only use via the owning parent's multiprocessing spawn channel.  Never
    # unpickle a caller-supplied file or accept an equivalent JSON dictionary.
    return HostAdmission(binding, files, mint=_HOST_MINT)


def make_host_admission(base_binding):
    """One parent SHA verification; child workers check unchanged stat identity."""
    from trusted_synthesis.experiments.finance_qa_vnext_pq_student import model

    paths = [Path(base_binding["directory"]) / row["path"] for row in base_binding["members"]]
    before = [{"path": str(path), "signature": _signature(path)} for path in paths]
    model.verify_checkpoint(base_binding)
    p.require(
        all(_signature(row["path"]) == row["signature"] for row in before),
        "budget.base_stable_during_single_parent_SHA",
    )
    return HostAdmission(base_binding, before, mint=_HOST_MINT)


def _admitted_loader(admission):
    from trusted_synthesis.experiments.finance_qa_vnext_fixed_kernel_value import (
        training,
        trajectory_training,
    )

    if admission is None:
        # Safe fallback for a standalone worker: do not trust a serialized JSON
        # receipt as proof of bytes.  A spawn coordinator should pass admission.
        return trajectory_training.load_registered_student
    p.require(
        type(admission) is HostAdmission and admission._mint is _HOST_MINT,
        "budget.owned_host_admission_object",
    )
    components = training.model_components

    def verify_admitted(binding):
        p.require(
            binding == admission.binding
            and all(_signature(row["path"]) == row["signature"] for row in admission.files),
            "budget.exact_unchanged_host_admitted_base",
        )

    component_globals = {**vars(components), "verify_checkpoint": verify_admitted}
    model_loader = clone_function(components.load_student, component_globals)
    component_proxy = SimpleNamespace(**{**vars(components), "load_student": model_loader})
    training_globals = {**vars(training), "model_components": component_proxy}
    physical = clone_function(training.load_registered_student, training_globals)

    def load_registered_student(
        binding, seed, config=None, *, trainable=True, adapter_path=None, adapter_record=None
    ):
        p.require(
            config is None or config == trajectory_training.training_config(),
            "budget.original_trajectory_training_configuration",
        )
        p.require(
            not trainable and adapter_path is not None and adapter_record is not None,
            "budget.only_restore_existing_final_adapter",
        )
        verify_admitted(binding)
        return physical(
            binding,
            seed,
            config=training.training_config(),
            trainable=False,
            adapter_path=adapter_path,
            adapter_record=adapter_record,
        )

    return load_registered_student


def public_parent_binding(parent_frozen):
    """Minimal public-only worker payload, with its own honest record identity."""
    p.checked_record(parent_frozen, "execution_freeze")
    return p.record(
        "budget_parent_public_binding",
        parent_execution_freeze_id=parent_frozen["id"],
        base_binding=copy.deepcopy(parent_frozen["base_binding"]),
        tokenizer_binding=copy.deepcopy(parent_frozen["tokenizer_binding"]),
        source_root=parent_frozen["source_root"],
        evaluation_registry={"dev": copy.deepcopy(parent_frozen["evaluation_registry"]["dev"])},
        private_TaskBundles_or_answers_included=False,
    )


def build_adapter(task_ids, parent_frozen, *, host_admission=None):
    """Build isolated policy/load/generate/score APIs for a preselected dev set.

    ``parent_frozen`` is the unmodified old execution_freeze, not the new study
    record.  The caller creates new model identities with a new study_freeze_id
    and this adapter's decoder_config_id while retaining the old checkpoints.
    Selection must be committed before any new generation; this function never
    consults original outcomes or chooses task IDs itself.
    """
    kind = parent_frozen.get("schema_version", "").rsplit(".", 1)[-1]
    p.require(
        kind in {"execution_freeze", "budget_parent_public_binding"},
        "budget.explicit_original_or_public_parent_record",
    )
    p.checked_record(parent_frozen, kind)
    parent_id = (
        parent_frozen["parent_execution_freeze_id"]
        if kind == "budget_parent_public_binding"
        else parent_frozen["id"]
    )
    ids = tuple(task_ids)
    registry_rows = parent_frozen["evaluation_registry"]["dev"]
    registry = {row["task_id"]: row for row in registry_rows}
    p.require(
        ids and len(ids) == len(set(ids)) and set(ids) <= set(registry),
        "budget.unique_prospectively_selected_original_dev_tasks",
    )
    quotas = dict(Counter(registry[task_id]["group"] for task_id in ids))
    p.require(
        set(quotas) == set(GROUPS) and all(quotas[group] > 0 for group in GROUPS),
        "budget.every_original_group_in_denominator",
    )
    p.require(
        parent_frozen["base_binding"]["config"]["max_position_embeddings"]
        >= MAXIMUM_SEQUENCE_LENGTH,
        "budget.actual_base_supports_context",
    )
    if host_admission is not None:
        p.require(
            type(host_admission) is HostAdmission
            and host_admission.binding == parent_frozen["base_binding"],
            "budget.parent_base_admission_join",
        )
    provenance = []
    namespace = dict(vars(original))
    namespace.update(policy=policy, QUOTAS={"dev": quotas})

    def budget_record(kind, **fields):
        if kind in {"generation_registration", "generation_report", "evaluation_report"}:
            fields.update(
                budget_reevaluation=True,
                parent_execution_freeze_id=parent_id,
                prospectively_selected_task_ids=list(ids),
                complete_original_180_dev_tasks=len(ids) == 180,
                original_experiment_decision_replaced=False,
            )
        if kind == "generation_registration":
            fields["subset_catalog"] = copy.deepcopy(catalog_holder["catalog"])
        return p.record(kind, **fields)

    namespace["record"] = budget_record
    policy_binder = clone_function(
        original.bind_policy, namespace, ((24576, MAXIMUM_SEQUENCE_LENGTH),), provenance=provenance
    )

    def bind_policy(tokenizer_binding, base_binding):
        result = policy_binder(tokenizer_binding, base_binding)
        fields = {
            key: value
            for key, value in result.items()
            if key not in {"id", "schema_version", "unchanged_latest_baseline_2048_limit"}
        }
        fields.update(
            budget_reevaluation=True,
            parent_decoder_policy_id=original.policy()["id"],
            original_model_context_configuration_unchanged=True,
        )
        return p.record("decoder_config", **fields)

    namespace["bind_policy"] = bind_policy
    budget_replacements = (
        (32, MAX_RESPONSES),
        (2048, MAX_NEW_TOKENS),
        (24576, MAXIMUM_SEQUENCE_LENGTH),
        (
            "decoder.full_context_plus_2048_exceeds_24576",
            "decoder.full_context_plus_4096_exceeds_32768",
        ),
    )
    methods = {}
    for name, value in vars(original.BoundDecoder).items():
        if isinstance(value, FunctionType):
            replacements = budget_replacements if name in {"__call__", "_generate"} else ()
            methods[name] = clone_function(value, namespace, replacements, provenance=provenance)
        elif name not in {"__dict__", "__weakref__"}:
            methods[name] = value
    decoder_type = type("BudgetBoundDecoder", original.BoundDecoder.__bases__, methods)
    namespace["BoundDecoder"] = decoder_type

    runtime_globals = {**vars(runtime), "MAX_RESPONSES": MAX_RESPONSES, "MAX_TOOLS": MAX_TOOLS}
    runtime_generate = clone_function(runtime.generate, runtime_globals, provenance=provenance)
    runtime_generate.__kwdefaults__.update(max_responses=MAX_RESPONSES, max_tools=MAX_TOOLS)
    private_runtime = SimpleNamespace(
        **{
            **vars(runtime),
            "generate": runtime_generate,
            "MAX_RESPONSES": MAX_RESPONSES,
            "MAX_TOOLS": MAX_TOOLS,
        }
    )
    namespace["runtime"] = private_runtime
    assessment_globals = {**vars(assessment), "generate": runtime_generate}
    replay = clone_function(assessment.replay_session, assessment_globals, provenance=provenance)
    assessment_globals["replay_session"] = replay
    assess = clone_function(assessment.assess_session, assessment_globals, provenance=provenance)
    namespace["assess_session"] = assess

    catalog_holder = {}

    class SelectedPublicOverlay:
        def __init__(self, root=None, directory=None, expected_manifest_id=None, *, parent=None):
            self.original = (
                parent
                if parent is not None
                else overlay.PublicOverlay(root, directory, expected_manifest_id)
            )
            original_catalog = self.original.catalog
            original_rows = {row["task_id"]: row for row in original_catalog["tasks"]}
            p.require(set(ids) <= set(original_rows), "budget.subset_in_original_public_catalog")
            rows = [copy.deepcopy(original_rows[task_id]) for task_id in ids]
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
                "budget.selected_public_metadata_unchanged",
            )
            self.catalog = p.record(
                "budget_evaluation_subset_catalog",
                parent_catalog_id=original_catalog["id"],
                parent_surface_manifest_id=self.original.parent.manifest["id"],
                parent_execution_freeze_id=parent_id,
                tasks=rows,
                task_count=len(rows),
                scientific_task_count=len(rows),
                quotas={"dev": quotas},
                original_public_envelopes_unchanged=True,
                selection_order="explicit_prospectively_registered_task_ids",
            )
            if "catalog" in catalog_holder:
                p.require(
                    catalog_holder["catalog"] == self.catalog, "budget.one_identical_subset_catalog"
                )
            catalog_holder["catalog"] = copy.deepcopy(self.catalog)
            self.parent = self.original.parent
            self.tasks = {row["task_id"]: row for row in rows}

        def public_envelope(self, task_id):
            p.require(task_id in self.tasks, "budget.only_registered_public_task")
            return self.original.public_envelope(task_id)

    class SelectedOfflineOverlay:
        def __init__(self, root, directory, expected_manifest_id):
            # Construct the entire original offline authority unchanged.  The
            # filtered public catalog is an explicit wrapper, not a forged ID.
            self.original = overlay.OfflineOverlay(root, directory, expected_manifest_id)
            self.public = SelectedPublicOverlay(parent=self.original.public)

        def fixture(self, task_id):
            p.require(task_id in self.public.tasks, "budget.only_registered_offline_task")
            return self.original.fixture(task_id)

    namespace.update(
        PublicOverlay=SelectedPublicOverlay,
        OfflineOverlay=SelectedOfflineOverlay,
        load_registered_student=_admitted_loader(host_admission),
    )
    load_decoder = _remove_local_imports(
        original.load_decoder,
        namespace,
        {(1, "trajectory_training", (("load_registered_student", None),))},
        provenance,
    )
    generate = clone_function(
        original.generate, namespace, ((32, MAX_RESPONSES),), provenance=provenance
    )
    verifier = clone_function(
        original.verify_generation_records, namespace, budget_replacements, provenance=provenance
    )
    namespace["verify_generation_records"] = verifier
    score = _remove_local_imports(
        original.score,
        namespace,
        {
            (2, "finance_qa_vnext_eval_readiness.assessment", (("assess_session", None),)),
            (2, "finance_qa_vnext_eval_surface.overlay", (("OfflineOverlay", None),)),
        },
        provenance,
    )
    sources = [
        Path(original.__file__),
        Path(runtime.__file__),
        Path(assessment.__file__),
        Path(overlay.__file__),
        Path(__file__),
    ]
    binding = p.record(
        "budget_reevaluation_transform",
        limits={
            "max_responses": MAX_RESPONSES,
            "max_tools": MAX_TOOLS,
            "max_new_tokens": MAX_NEW_TOKENS,
            "maximum_sequence_length": MAXIMUM_SEQUENCE_LENGTH,
        },
        parent_execution_freeze_id=parent_id,
        selected_task_ids=list(ids),
        quotas={"dev": quotas},
        sources=[{"path": str(path.resolve()), "sha256": p.sha(path)} for path in sources],
        function_transforms=provenance,
        frozen_module_globals_modified=False,
        original_system_prompt_sha256=p.sha(runtime.SYSTEM),
        original_tool_execution_unchanged=True,
        original_assessment_after_replay_unchanged=True,
        fresh_Student_training=False,
        automatic_continuation_or_JSON_repair=False,
        supported_base_verification_modes=[
            "one_parent_SHA_then_trusted_spawn_stat_identity",
            "original_loader_full_SHA_safe_fallback",
        ],
        actual_base_verification_mode_recorded_separately=True,
    )
    return SimpleNamespace(
        policy=policy,
        bind_policy=bind_policy,
        load_decoder=load_decoder,
        generate=generate,
        score=score,
        BoundDecoder=decoder_type,
        runtime=private_runtime,
        replay_session=replay,
        assess_session=assess,
        verify_generation_records=verifier,
        PublicOverlay=SelectedPublicOverlay,
        OfflineOverlay=SelectedOfflineOverlay,
        transform_provenance=binding,
        task_ids=ids,
        quotas={"dev": quotas},
        actual_base_verification_mode="one_parent_SHA_then_trusted_spawn_stat_identity"
        if host_admission is not None
        else "original_loader_full_SHA_safe_fallback",
    )
