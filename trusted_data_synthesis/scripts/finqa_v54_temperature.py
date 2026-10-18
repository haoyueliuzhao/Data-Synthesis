"""Independent T=0.5 feedback contract and exact temperature-aware R3 replay.

Historical provider, collector, seals and replay files remain unchanged. The
only replay arithmetic change is log_softmax(logits.float() / T), in both the
saved forward and every backward recomputation (including the prefill). Thus
autograd includes the normalization and 1/T derivative; old gJ is never scaled.
"""

from __future__ import annotations

import ast
import asyncio
import copy
import hashlib
import inspect
import json
import textwrap
import traceback
from pathlib import Path

import finqa_v19_optimized_replay as optimized
import finqa_v32_replay_variants as v32
import finqa_v33_activation_residency as r3
import torch

from trusted_synthesis.finance_research import feedback, providers
from trusted_synthesis.finance_research.contracts import (
    PrivateReference, RunConfig, TaskBundle, digest,
)
from trusted_synthesis.finance_research.v6_collection import require
from trusted_synthesis.finance_research.v8_training_driver import (
    LocalFeedbackCollector as HistoricalCollector,
    _publish,
    installed_point,
)

BACKEND_VERSION = "v54_exact_temperature_r3.v1"
PROBABILITY_CONTRACT = {
    "schema": "v54_feedback_probability.v1",
    "probability": "softmax(logits.float()/T)",
    "gradient": "(one_hot(target)-softmax(logits.float()/T))/T",
    "trajectory": "sum_all_actual_generated_tokens_including_error_recovery_and_actual_EOS",
    "SFT_mask_used": False,
    "length_normalized": False,
    "top_p": 1.0,
    "top_k": 0,
    "production_denominator": 700,
    "draw_seeds": [11, 29],
    "draw_denominator": 350,
}
PROBABILITY_CONTRACT_ID = digest(PROBABILITY_CONTRACT)
PauseRequest, ReplayPaused = v32.PauseRequest, v32.ReplayPaused


def _temperature(value):
    require(type(value) in (int, float) and value in (0.5, 1.0), "only registered T=0.5 or T=1")
    return float(value)


def build_condition(*, identity, temperature, configs, task_roster,
                    source_manifest_sha256, role_plan_id=None, cpu_test=False):
    """Register the complete ordered task/draw/config roster before generation."""
    temperature = _temperature(temperature)
    identity = providers.ModelIdentity.model_validate(identity)
    configs = [RunConfig.model_validate(config) for config in configs]
    tasks = [
        {"dataset": task["dataset"], "task_id": task["task_id"]}
        if isinstance(task, dict)
        else {"dataset": task.dataset, "task_id": task.task_id}
        for task in task_roster
    ]
    require(identity.backend == "local_torch" and all((identity.point_id,
            identity.parameter_digest, identity.tokenizer_digest, identity.chat_template_digest)),
            "complete actual local parameter/tokenizer point identity required")
    require(len(source_manifest_sha256) == 64, "admitted source manifest digest required")
    require(len(configs) == 2 and [cfg.seed for cfg in configs] == [11, 29],
            "registered draw order is exactly seeds 11,29")
    require(tasks and len({(t["dataset"], t["task_id"]) for t in tasks}) == len(tasks)
            and (cpu_test or len(tasks) == 350), "complete distinct 350-task roster required")
    for cfg in configs:
        require((cfg.tier, cfg.role, cfg.temperature, cfg.top_p, cfg.top_k)
                == ("VTDO_FEEDBACK", "feedback", temperature, 1.0, 0),
                "feedback configuration differs from registered probability contract")
    require(configs[0].model_copy(update={"seed": 29}) == configs[1],
            "draw configurations may differ only in seed")
    roster = [
        dict(task, draw_index=index, seed=cfg.seed,
             config_sha256=digest(cfg.model_dump(mode="json")),
             episode_key=digest(dict(task, seed=cfg.seed, point_id=identity.point_id)))
        for index, cfg in enumerate(configs) for task in tasks
    ]
    body = dict(
        schema="v54_pre_generation_feedback_condition.v1",
        identity=identity.model_dump(mode="json"), temperature=temperature,
        probability_contract=PROBABILITY_CONTRACT,
        probability_contract_id=PROBABILITY_CONTRACT_ID,
        source_manifest_sha256=source_manifest_sha256, role_plan_id=role_plan_id,
        configs=[cfg.model_dump(mode="json") for cfg in configs],
        task_roster=tasks, ordered_episode_roster=roster,
        denominator=len(roster), cpu_test_only=bool(cpu_test),
    )
    return {**body, "id": digest(body)}


def checked_condition(condition):
    body = {key: value for key, value in condition.items() if key != "id"}
    require(condition.get("id") == digest(body), "feedback condition identity changed")
    expected = build_condition(
        identity=condition["identity"], temperature=condition["temperature"],
        configs=condition["configs"], task_roster=condition["task_roster"],
        source_manifest_sha256=condition["source_manifest_sha256"],
        role_plan_id=condition["role_plan_id"], cpu_test=condition["cpu_test_only"],
    )
    require(condition == expected, "feedback condition is outside the registered contract")
    return condition


def _adapt_temperature_guard(function, temperature, *, receipt_guard=False,
                             before_generate_hook=False):
    """Copy only two explicit old T1 checks; never mutate the old module.

    Generation, parsing, actual-token receipts and all other admission checks
    use the original function source. Fail closed if its known guard changes.
    """
    source = textwrap.dedent(inspect.getsource(function))
    tree = ast.parse(source)
    matched = {"config": 0, "receipt": 0, "generation_hook": 0}

    class Guards(ast.NodeTransformer):
        def visit_AugAssign(self, node):
            self.generic_visit(node)
            if before_generate_hook and ast.unparse(node.target) == "self.actual_model_calls":
                require(isinstance(node.op, ast.Add) and isinstance(node.value, ast.Constant)
                        and node.value.value == 1, "original actual generate-call counter changed")
                matched["generation_hook"] += 1
                call = ast.Expr(value=ast.Call(
                    func=ast.Attribute(value=ast.Name(id="self", ctx=ast.Load()),
                                       attr="_before_generate", ctx=ast.Load()),
                    args=[ast.Name(id="request", ctx=ast.Load()),
                          ast.Name(id="request_hash", ctx=ast.Load())], keywords=[]))
                return [ast.copy_location(call, node), node]
            return node

        def visit_Compare(self, node):
            self.generic_visit(node)
            if (ast.unparse(node.left) == "(config.temperature, config.top_p, config.top_k)"
                    and len(node.comparators) == 1
                    and ast.literal_eval(node.comparators[0]) == (1.0, 1.0, 0)):
                node.comparators[0] = ast.Tuple(
                    elts=[ast.Constant(temperature), ast.Constant(1.0), ast.Constant(0)],
                    ctx=ast.Load(),
                )
                matched["config"] += 1
            elif (receipt_guard and ast.unparse(node.left) == "sampling.get('temperature')"
                  and len(node.comparators) == 1
                  and isinstance(node.comparators[0], ast.Constant)
                  and node.comparators[0].value == 1.0):
                node.comparators[0] = ast.Constant(temperature)
                matched["receipt"] += 1
            return node

    tree = Guards().visit(tree)
    require(matched == {"config": 1, "receipt": int(receipt_guard),
                        "generation_hook": int(before_generate_hook)},
            "historical temperature guard structure changed")
    ast.fix_missing_locations(tree)
    namespace = dict(function.__globals__)
    exec(compile(tree, __file__ + "::temperature_guard", "exec"), namespace)
    return namespace[function.__name__]


class LocalTorchProvider(providers.LocalTorchProvider):
    """Actual HF temperature sampling, with a pre-registered condition per call."""

    def __init__(self, *args, condition, before_call=None, recovery_guard=None, **kwargs):
        self.condition = copy.deepcopy(checked_condition(condition))
        self.before_call = before_call
        self.recovery_guard = recovery_guard
        require(recovery_guard is None or recovery_guard.condition == self.condition,
                "recovery guard must retain the exact scientific feedback condition")
        super().__init__(*args, **kwargs)
        require(self.identity.model_dump(mode="json") == self.condition["identity"],
                "provider belongs to another parameter point")
        self._temperature_chat = _adapt_temperature_guard(
            providers.LocalTorchProvider.chat, self.condition["temperature"],
            before_generate_hook=True,
        )

    def _before_generate(self, request, request_sha256):
        if self.recovery_guard is not None:
            self.recovery_guard.before_generate(request, request_sha256)

    async def chat(self, messages, tools, config):
        require(config.model_dump(mode="json") in self.condition["configs"],
                "provider request is outside its pre-generation condition")
        # The callback observes resources and cooperative stop before any new
        # model call. No callback is inserted between a model return and its
        # durable receipt: an interrupted new call remains explicitly unknown.
        if self.before_call is not None:
            self.before_call(dict(phase="before_actual_feedback_call",
                                  feedback_condition_id=self.condition["id"],
                                  draw_seed=config.seed, temperature=config.temperature))
        try:
            turn = await self._temperature_chat(self, messages, tools, config)
        except providers.ProviderCallError as exception:
            # The historical provider preserves a Python exception cause but
            # its durable evidence stores only that cause's type. Once the
            # harness catches the wrapper, the actual message/trace are lost.
            # Preserve them in the new version without inferring settlement,
            # retrying a call, changing its count, or inventing a token receipt.
            cause = exception.__cause__
            evidence = dict(exception.evidence,
                            underlying_cause_available=cause is not None,
                            feedback_condition_id=self.condition["id"],
                            probability_contract_id=PROBABILITY_CONTRACT_ID)
            if cause is not None:
                evidence.update(
                    underlying_exception_type=type(cause).__name__,
                    underlying_exception_message=str(cause),
                    underlying_exception_traceback="".join(traceback.format_exception(cause)),
                )
            raise providers.ProviderCallError(
                str(exception), settlement=exception.settlement,
                actual_model_calls=exception.actual_model_calls, evidence=evidence,
            ) from exception
        sampling = dict(turn.receipt.sampling,
                        feedback_condition_id=self.condition["id"],
                        probability_contract_id=PROBABILITY_CONTRACT_ID)
        bound_turn = turn.model_copy(update={
            "receipt": turn.receipt.model_copy(update={"sampling": sampling}),
            "provider_metadata": dict(turn.provider_metadata,
                                      feedback_condition_id=self.condition["id"]),
        })
        if self.recovery_guard is not None:
            self.recovery_guard.returned(bound_turn)
        return bound_turn


def seal_feedback_cohort(episodes, *, condition, denominator, identity,
                         source_manifest_sha256, registered_episode_keys):
    """Validate actual T receipts and exact pre-registered order before rewards."""
    condition = checked_condition(condition)
    episodes = tuple(episodes)
    require(identity.model_dump(mode="json") == condition["identity"]
            and denominator == condition["denominator"]
            and source_manifest_sha256 == condition["source_manifest_sha256"],
            "cohort parameter point, denominator or source differs from condition")
    registered = [row["episode_key"] for row in condition["ordered_episode_roster"]]
    require(list(registered_episode_keys) == registered
            and len(episodes) == len(registered), "cohort differs from pre-generation roster")
    validator = _adapt_temperature_guard(
        feedback._validate_episode, condition["temperature"], receipt_guard=True
    )
    for episode, row in zip(episodes, condition["ordered_episode_roster"], strict=True):
        require(digest(episode.config.model_dump(mode="json")) == row["config_sha256"],
                "episode uses a different registered draw configuration")
        for turn in episode.turns:
            sampling = turn.receipt.sampling if turn.receipt else {}
            # Old T1 receipts are read-only and predate the new condition field.
            if condition["temperature"] == 0.5 or "feedback_condition_id" in sampling:
                require(sampling.get("feedback_condition_id") == condition["id"]
                        and sampling.get("probability_contract_id") == PROBABILITY_CONTRACT_ID,
                        "receipt belongs to another temperature condition")
    seal = optimized.bind_dependencies(feedback.seal_feedback_cohort,
                                       _validate_episode=validator)
    return seal(episodes, denominator=denominator, identity=identity,
                source_manifest_sha256=source_manifest_sha256,
                registered_episode_keys=registered)


def condition_cohort_binding(condition, cohort, *, generation_seals=None):
    """Post-generation immutable link from condition to every actual receipt."""
    checked = seal_feedback_cohort(
        cohort.episodes, condition=condition, denominator=cohort.denominator,
        identity=cohort.identity, source_manifest_sha256=cohort.source_manifest_sha256,
        registered_episode_keys=cohort.registered_episode_keys,
    )
    require(checked == cohort, "actual cohort seal changed")
    receipts = [dict(episode_index=i, turn_index=j, call_id=turn.receipt.call_id,
                     receipt_sha256=digest(turn.receipt))
                for i, ep in enumerate(cohort.episodes) for j, turn in enumerate(ep.turns)]
    body = dict(schema="v54_condition_actual_cohort_binding.v1",
                condition_id=condition["id"], temperature=condition["temperature"],
                probability_contract_id=PROBABILITY_CONTRACT_ID,
                cohort_seal_sha256=cohort.seal_sha256,
                identity=cohort.identity.model_dump(mode="json"),
                denominator=cohort.denominator, receipts=receipts,
                generation_seals=generation_seals or [])
    return {**body, "id": digest(body)}


class _TemperatureTorch:
    """Per-call globals proxy; no global torch or model hooks are modified."""

    def __init__(self, temperature):
        self.temperature = _temperature(temperature)

    def __getattr__(self, name):
        return getattr(torch, name)

    def log_softmax(self, logits, *args, **kwargs):
        # Both forward and backward see the scaled logits. In particular this
        # operation remains on the autograd graph and carries its 1/T factor.
        scaled = logits if self.temperature == 1.0 else logits / self.temperature
        return torch.log_softmax(scaled, *args, **kwargs)


class ReplaySession(r3.R3Session):
    def __init__(self, model, theta, *, temperature, condition_id, **kwargs):
        self.temperature, self.condition_id = _temperature(temperature), condition_id
        require(isinstance(condition_id, str) and len(condition_id) == 64,
                "temperature replay requires the registered feedback condition")
        super().__init__(model, theta, **kwargs)
        probability = _TemperatureTorch(self.temperature)
        forward = optimized.bind_dependencies(
            self.operation.forward.__globals__["forward_saved_tokens"], torch=probability
        )
        self.operation.forward = optimized.bind_dependencies(
            self.operation.forward, torch=probability, forward_saved_tokens=forward
        )

    def __call__(self, *args, **kwargs):
        values, gradient, report = super().__call__(*args, **kwargs)
        report.update(
            replay_backend_version=BACKEND_VERSION,
            parent_replay_backend_version=r3.BACKEND_VERSION,
            temperature=self.temperature, feedback_condition_id=self.condition_id,
            probability_contract_id=PROBABILITY_CONTRACT_ID,
            forward_and_backward_use_same_temperature=True,
            gradient_contains_inverse_temperature=True,
            original_storage_and_ordered_adjoint_path_reused=True,
            original_numeric_semantics_unchanged=self.temperature == 1.0,
            length_normalized=False, SFT_mask_used=False,
            all_actual_error_recovery_and_EOS_tokens_included=True,
        )
        return values, gradient, report


def backend_identity(condition):
    checked_condition(condition)
    return dict(backend_version=BACKEND_VERSION, temperature=condition["temperature"],
                feedback_condition_id=condition["id"],
                probability_contract_id=PROBABILITY_CONTRACT_ID,
                source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                original_R3=r3.source_binding())


def feedback_gradient(cohort, rewards, model, theta, *, condition,
                      backend_factory=None, **kwargs):
    """Original response ordering and denominator; checkpoint binds T and source."""
    checked_condition(condition)
    cpu_test = kwargs.get("cpu_test", False)
    require(cpu_test or not condition["cpu_test_only"], "CPU fixture cannot authorize production")
    if backend_factory is None:
        backend_factory = lambda actual_model, actual_theta: ReplaySession(
            actual_model, actual_theta, temperature=condition["temperature"],
            condition_id=condition["id"], profile_id=kwargs["profile_id"], cpu_test=cpu_test,
        )
    supplied_factory = backend_factory

    def factory(actual_model, actual_theta):
        result = supplied_factory(actual_model, actual_theta)
        require(cpu_test or isinstance(result, ReplaySession)
                and result.temperature == condition["temperature"]
                and result.condition_id == condition["id"],
                "production backend differs from the sampled temperature condition")
        return result

    def seal(episodes, **fields):
        return seal_feedback_cohort(episodes, condition=condition, **fields)

    required_identity = backend_identity(condition)
    if "backend_identity" in kwargs:
        require(kwargs.pop("backend_identity") == required_identity,
                "checkpoint backend identity differs from temperature contract")
    compute = optimized.bind_dependencies(
        v32.feedback_gradient, seal_feedback_cohort=seal, BACKEND_VERSION=BACKEND_VERSION
    )
    gradients, report = compute(cohort, rewards, model, theta,
                                backend_factory=factory,
                                backend_identity=required_identity, **kwargs)
    report.update(feedback_condition_id=condition["id"], temperature=condition["temperature"],
                  probability_contract_id=PROBABILITY_CONTRACT_ID)
    return gradients, report


class LocalFeedbackCollector(HistoricalCollector):
    """New C05 queue: point plus probability plus roster, before any model call."""

    def __init__(self, *, recovery_guard_factory=None, **kwargs):
        config = RunConfig.model_validate(kwargs["config"])
        require(config.temperature == 0.5, "new generation is authorized only for C05")
        # Reuse the old material/harness checks with their admitted T1 field,
        # then install the separately checked new temperature contract.
        super().__init__(**{**kwargs, "config": config.model_copy(update={"temperature": 1.0})})
        require(self.seeds == (11, 29), "only registered draw seeds 11,29")
        self.config = config
        self.condition = self.feedback_root = None
        self.recovery_guard_factory = recovery_guard_factory

    def collect(self, model, tokenizer, theta, *, point_id, event_sink=None):
        from trusted_synthesis.finance_research.planning import task_key
        from trusted_synthesis.finance_research.storage import (
            _read_snapshot_rows, execute_run, prepare_run, sealed_episodes,
        )
        from trusted_synthesis.finance_research.v6_task import score_public_reasoning_program

        emit = event_sink or (lambda event: None)
        with installed_point(model, theta) as installed:
            identity = providers.local_model_identity(
                model, tokenizer, model_id=self.model_id, point_id=point_id,
                parameter_tensors=installed,
            )
            configs = [self.config.model_copy(update={"seed": seed}) for seed in self.seeds]
            condition = build_condition(identity=identity, temperature=0.5, configs=configs,
                                        task_roster=self.tasks,
                                        source_manifest_sha256=digest(self.manifest),
                                        role_plan_id=self.role_plan["id"])
            root = self.root / condition["id"]
            self.condition, self.feedback_root = condition, root
            # One instance spans every turn/task in both draws. A new provider
            # in draw1 must not reset the consumed/resolved draw0 allowance.
            recovery_guard = (self.recovery_guard_factory(condition)
                              if self.recovery_guard_factory is not None else None)
            emit(dict(phase="feedback_condition_registration", feedback_root=str(root),
                      feedback_condition_id=condition["id"], temperature=0.5))
            if root.exists():
                require(json.loads((root / "intent/record.json").read_bytes()) == condition,
                        "pre-generation feedback condition changed")
                require(all((root / f"draw{i}/generation_seal/seal.json").exists()
                            for i in range(2)),
                        "partial C05 feedback retained; automatic resampling forbidden")
                if (root / "native_rewards/record.json").is_file():
                    cohort, rewards = read_complete(root, condition)
                    emit(dict(phase="restored_complete_feedback_without_rescoring",
                              feedback_root=str(root), feedback_condition_id=condition["id"],
                              cohort_seal_sha256=cohort.seal_sha256, denominator=700))
                    return cohort, rewards
            else:
                _publish(root / "intent", condition)
                for index, cfg in enumerate(configs):
                    emit(dict(phase="feedback_generation", feedback_root=str(root),
                              feedback_condition_id=condition["id"], draw_index=index,
                              feedback_seed=cfg.seed, temperature=0.5))
                    directory = root / f"draw{index}"
                    prepare_run(self.snapshot, self.role_plan, directory, role="feedback",
                                config=cfg, identity=identity,
                                task_keys=[task_key(t) for t in self.tasks])
                    provider = LocalTorchProvider(model, tokenizer, identity,
                                                  parameter_tensors=installed,
                                                  condition=condition, before_call=emit,
                                                  recovery_guard=recovery_guard)
                    asyncio.run(execute_run(directory, provider))
            episodes, generation_seals = [], []
            for index in range(2):
                _, _, part = sealed_episodes(root / f"draw{index}")
                episodes.extend(part)
                seal_path = root / f"draw{index}/generation_seal/seal.json"
                generation_seals.append(dict(path=str(seal_path),
                                             sha256=hashlib.sha256(seal_path.read_bytes()).hexdigest()))
            cohort = seal_feedback_cohort(
                episodes, condition=condition, denominator=700, identity=identity,
                source_manifest_sha256=digest(self.manifest),
                registered_episode_keys=[row["episode_key"]
                                         for row in condition["ordered_episode_roster"]],
            )
            _publish(root / "cohort_seal", cohort.model_dump(mode="json"))
            _publish(root / "condition_cohort_binding", condition_cohort_binding(
                condition, cohort, generation_seals=generation_seals))
            emit(dict(phase="native_scoring", feedback_root=str(root),
                      feedback_condition_id=condition["id"],
                      cohort_seal_sha256=cohort.seal_sha256, denominator=700))
            # Private references are first read only after all 700 are sealed.
            references = _read_snapshot_rows(self.snapshot, "private.references.jsonl",
                                             PrivateReference, self.manifest)
            bundles = {task.task_id: TaskBundle(public=task, reference=reference, lineage=lineage)
                       for task, reference, lineage in zip(self.public, references,
                                                            self.lineages, strict=True)}
            scores = [score_public_reasoning_program(bundles[ep.task_id], ep) for ep in episodes]
            rewards = [score["native"]["execution_accuracy"] for score in scores]
            valid = all(type(reward) in (int, float) and reward in (0, 1) for reward in rewards)
            if not valid:
                _publish(root / "native_scoring_failure",
                         dict(condition_id=condition["id"], cohort_seal_sha256=cohort.seal_sha256,
                              scores=scores, unmodified_native_values=rewards,
                              missing_or_unknown_values_imputed=False))
            require(valid, "infrastructure/reference unknown cannot become zero reward")
            _publish(root / "native_rewards",
                     dict(condition_id=condition["id"], cohort_seal_sha256=cohort.seal_sha256,
                          rewards=rewards, scores=scores))
            emit(dict(phase="feedback_and_native_rewards_complete", feedback_root=str(root),
                      feedback_condition_id=condition["id"],
                      cohort_seal_sha256=cohort.seal_sha256, denominator=700))
            return cohort, rewards


def read_complete(root, condition):
    """Read the exact sealed C05 cohort and frozen rewards, with no scoring."""
    from trusted_synthesis.finance_research.storage import sealed_episodes

    root, condition = Path(root), checked_condition(condition)
    require(root.name == condition["id"]
            and json.loads((root / "intent/record.json").read_bytes()) == condition,
            "sealed feedback directory/intent differs from its probability condition")
    episodes, generation_seals = [], []
    for index in range(2):
        _, _, part = sealed_episodes(root / f"draw{index}")
        episodes.extend(part)
        path = root / f"draw{index}/generation_seal/seal.json"
        generation_seals.append(dict(path=str(path), sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
    cohort = seal_feedback_cohort(
        episodes, condition=condition, denominator=700,
        identity=providers.ModelIdentity.model_validate(condition["identity"]),
        source_manifest_sha256=condition["source_manifest_sha256"],
        registered_episode_keys=[row["episode_key"] for row in condition["ordered_episode_roster"]],
    )
    require(json.loads((root / "cohort_seal/record.json").read_bytes())
            == cohort.model_dump(mode="json"), "saved C05 cohort differs from actual sealed draws")
    require(json.loads((root / "condition_cohort_binding/record.json").read_bytes())
            == condition_cohort_binding(condition, cohort, generation_seals=generation_seals),
            "saved condition-to-receipt binding differs")
    native = json.loads((root / "native_rewards/record.json").read_bytes())
    rewards = native["rewards"]
    require(native["condition_id"] == condition["id"]
            and native["cohort_seal_sha256"] == cohort.seal_sha256
            and len(rewards) == len(native["scores"]) == 700
            and all(type(value) in (int, float) and value in (0, 1) for value in rewards)
            and [score["native"]["execution_accuracy"] for score in native["scores"]] == rewards,
            "complete immutable C05 rewards required; UNKNOWN cannot be imputed")
    return cohort, rewards
