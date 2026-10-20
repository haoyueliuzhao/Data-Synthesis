"""Balanced b=1 feedback and unchanged formal temperature-aware R3 replay.

Only new conditions (T1/T0.5, draws101/103) are admitted here. Historical
conditions and records are read-only elsewhere. Real generation, durable turn
recovery, exact token probabilities, gradients and scoring reuse frozen code.
"""
from __future__ import annotations

import asyncio
import copy
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import finqa_v63_binding as binding

binding.install_scientific_paths()

import finqa_v54_temperature as original
import finqa_v56_feedback as durable
import finqa_v63_draw_components as components
import torch

from trusted_synthesis.finance_research.contracts import (
    PrivateReference, RunConfig, TaskBundle, digest,
)
from trusted_synthesis.finance_research.v8_training_driver import (
    LocalFeedbackCollector as HistoricalCollector, _publish, installed_point,
)

require = binding.require
ARMS, TEMPERATURES = binding.ARMS, binding.TEMPERATURES
BATCH, DRAW_SEEDS = binding.BATCH, binding.DRAW_SEEDS
BACKEND_VERSION = "v63_balanced_b1_exact_temperature_r3.v1"
PROBABILITY_CONTRACT = {
    **original.PROBABILITY_CONTRACT,
    "schema": "v63_balanced_b1_feedback_probability.v1",
    "feedback_batch": BATCH,
    "draw_seeds": list(DRAW_SEEDS),
    "new_T1_receipts_require_condition_binding": True,
    "diagnostic_draw_denominator": 350,
    "formal_response_accumulation_unchanged": True,
}
PROBABILITY_CONTRACT_ID = digest(PROBABILITY_CONTRACT)
PauseRequest, ReplayPaused = original.PauseRequest, original.ReplayPaused
MEAN_TOLERANCES = components.MEAN_TOLERANCES
providers = original.providers


def _arm(temperature, arm=None, batch=BATCH):
    temperature = original._temperature(temperature)
    require(type(batch) is int and batch == BATCH, "only the separately registered feedback batch1")
    arm = arm or next(name for name, value in TEMPERATURES.items() if value == temperature)
    require(arm in ARMS and TEMPERATURES[arm] == temperature,
            "feedback arm and sampled temperature differ")
    return arm, temperature


def build_condition(*, identity, temperature, configs, task_roster,
                    source_manifest_sha256, role_plan_id=None, arm=None, batch=BATCH,
                    cpu_test=False):
    """Bind both temperatures to a new batch and exact ordered draw roster."""
    arm, temperature = _arm(temperature, arm, batch)
    identity = providers.ModelIdentity.model_validate(identity)
    configs = [RunConfig.model_validate(config) for config in configs]
    tasks = [dict(dataset=t["dataset"], task_id=t["task_id"]) if isinstance(t, dict)
             else dict(dataset=t.dataset, task_id=t.task_id) for t in task_roster]
    require(identity.backend == "local_torch" and all((
        identity.point_id, identity.parameter_digest, identity.tokenizer_digest,
        identity.chat_template_digest)), "complete actual local parameter/tokenizer point required")
    require(isinstance(source_manifest_sha256, str) and len(source_manifest_sha256) == 64,
            "admitted source manifest digest required")
    require(len(configs) == 2 and tuple(cfg.seed for cfg in configs) == DRAW_SEEDS,
            "registered batch1 draw order is exactly 101,103")
    require(tasks and len({(t["dataset"], t["task_id"]) for t in tasks}) == len(tasks)
            and (cpu_test or len(tasks) == 350), "complete distinct 350-task roster required")
    for cfg in configs:
        require((cfg.tier, cfg.role, cfg.temperature, cfg.top_p, cfg.top_k)
                == ("VTDO_FEEDBACK", "feedback", temperature, 1.0, 0),
                "new feedback configuration differs from its probability contract")
    require(configs[0].model_copy(update={"seed": DRAW_SEEDS[1]}) == configs[1],
            "draw configurations may differ only in seed")
    roster = [
        dict(task, draw_index=index, seed=cfg.seed,
             config_sha256=digest(cfg.model_dump(mode="json")),
             episode_key=digest(dict(task, seed=cfg.seed, point_id=identity.point_id)))
        for index, cfg in enumerate(configs) for task in tasks
    ]
    body = dict(
        schema="v63_pre_generation_balanced_feedback_condition.v1",
        identity=identity.model_dump(mode="json"), temperature=temperature, arm=arm,
        feedback_batch=batch, draw_seeds=list(DRAW_SEEDS),
        probability_contract=PROBABILITY_CONTRACT,
        probability_contract_id=PROBABILITY_CONTRACT_ID,
        source_manifest_sha256=source_manifest_sha256, role_plan_id=role_plan_id,
        configs=[cfg.model_dump(mode="json") for cfg in configs],
        task_roster=tasks, ordered_episode_roster=roster,
        denominator=len(roster), cpu_test_only=bool(cpu_test),
        old_feedback_or_single_request_quota_reused=False,
    )
    return {**body, "id": digest(body)}


def checked_condition(condition):
    body = {key: value for key, value in condition.items() if key != "id"}
    require(condition.get("id") == digest(body), "batch1 feedback condition identity changed")
    expected = build_condition(
        identity=condition["identity"], temperature=condition["temperature"],
        configs=condition["configs"], task_roster=condition["task_roster"],
        source_manifest_sha256=condition["source_manifest_sha256"],
        role_plan_id=condition["role_plan_id"], arm=condition["arm"],
        batch=condition["feedback_batch"], cpu_test=condition["cpu_test_only"],
    )
    require(condition == expected, "feedback condition is outside the registered batch1 contract")
    return condition


class LocalTorchProvider(original.LocalTorchProvider):
    """Exact frozen sampling implementation with new, strict receipt binding."""

    __init__ = original.optimized.bind_dependencies(
        original.LocalTorchProvider.__init__, checked_condition=checked_condition)
    chat = original.optimized.bind_dependencies(
        original.LocalTorchProvider.chat, PROBABILITY_CONTRACT_ID=PROBABILITY_CONTRACT_ID)


def seal_feedback_cohort(episodes, *, condition, denominator, identity,
                         source_manifest_sha256, registered_episode_keys):
    condition = checked_condition(condition)
    episodes = tuple(episodes)
    require(identity.model_dump(mode="json") == condition["identity"]
            and denominator == condition["denominator"]
            and source_manifest_sha256 == condition["source_manifest_sha256"],
            "cohort point/denominator/source differs from the batch1 condition")
    registered = [row["episode_key"] for row in condition["ordered_episode_roster"]]
    require(list(registered_episode_keys) == registered and len(episodes) == len(registered),
            "cohort differs from the registered batch1 task/draw order")
    for episode, row in zip(episodes, condition["ordered_episode_roster"], strict=True):
        require(digest(episode.config.model_dump(mode="json")) == row["config_sha256"],
                "episode belongs to another registered draw configuration")
        for turn in episode.turns:
            sampling = turn.receipt.sampling if turn.receipt else {}
            # Unlike the old T1 compatibility branch, NEW T1 must carry this
            # condition too; an old T1 receipt can never become new b=1 data.
            require(sampling.get("feedback_condition_id") == condition["id"]
                    and sampling.get("probability_contract_id") == PROBABILITY_CONTRACT_ID,
                    "new T1/C05 receipt lacks the exact batch1 condition binding")
    validator = original._adapt_temperature_guard(
        original.feedback._validate_episode, condition["temperature"], receipt_guard=True)
    seal = original.optimized.bind_dependencies(
        original.feedback.seal_feedback_cohort, _validate_episode=validator)
    return seal(episodes, denominator=denominator, identity=identity,
                source_manifest_sha256=source_manifest_sha256,
                registered_episode_keys=registered)


def condition_cohort_binding(condition, cohort, *, generation_seals=None):
    checked = seal_feedback_cohort(
        cohort.episodes, condition=condition, denominator=cohort.denominator,
        identity=cohort.identity, source_manifest_sha256=cohort.source_manifest_sha256,
        registered_episode_keys=cohort.registered_episode_keys)
    require(checked == cohort, "actual batch1 cohort seal changed")
    body = dict(
        schema="v63_condition_actual_cohort_binding.v1",
        condition_id=condition["id"], feedback_batch=BATCH, arm=condition["arm"],
        temperature=condition["temperature"], draw_seeds=list(DRAW_SEEDS),
        probability_contract_id=PROBABILITY_CONTRACT_ID,
        cohort_seal_sha256=cohort.seal_sha256,
        identity=cohort.identity.model_dump(mode="json"), denominator=cohort.denominator,
        receipts=[dict(episode_index=i, turn_index=j, call_id=turn.receipt.call_id,
                       receipt_sha256=digest(turn.receipt))
                  for i, ep in enumerate(cohort.episodes) for j, turn in enumerate(ep.turns)],
        generation_seals=generation_seals or [],
    )
    return {**body, "id": digest(body)}


read_complete = original.optimized.bind_dependencies(
    original.read_complete, checked_condition=checked_condition,
    seal_feedback_cohort=seal_feedback_cohort, condition_cohort_binding=condition_cohort_binding)


class ReplaySession(original.ReplaySession):
    """The exact existing temperature-scaled forward and adjoint arithmetic."""

    def __call__(self, *args, **kwargs):
        values, gradient, report = super().__call__(*args, **kwargs)
        report.update(replay_backend_version=BACKEND_VERSION,
                      probability_contract_id=PROBABILITY_CONTRACT_ID,
                      feedback_batch=BATCH, diagnostic_draw_seeds=list(DRAW_SEEDS))
        return values, gradient, report


def backend_identity(condition, *, mean_tolerances):
    checked_condition(condition)
    return dict(
        backend_version=BACKEND_VERSION, temperature=condition["temperature"],
        arm=condition["arm"], feedback_batch=BATCH, draw_seeds=list(DRAW_SEEDS),
        feedback_condition_id=condition["id"], probability_contract_id=PROBABILITY_CONTRACT_ID,
        source_sha256=binding.sha(__file__), draw_component_source_sha256=binding.sha(components.__file__),
        draw_component_version=components.VERSION,
        mean_tolerances=components.checked_tolerances(mean_tolerances),
        original_temperature_source_sha256=binding.sha(original.__file__),
        original_R3=original.r3.source_binding(),
    )


def feedback_gradient(cohort, rewards, model, theta, *, condition, mean_tolerances,
                      backend_factory=None, draw_components_out=None,
                      component_monitor=None, **kwargs):
    """Keep formal R3 total.add_(reward/700) bytecode; atomically save diagnostics."""
    checked_condition(condition)
    cpu_test = kwargs.get("cpu_test", False)
    require(cpu_test or not condition["cpu_test_only"], "CPU fixture cannot authorize production")
    require(cpu_test or callable(component_monitor), "production component resource monitor required")
    require(cpu_test or Path(kwargs["root"]).resolve().is_relative_to(binding.ROOT.resolve()),
            "production replay checkpoints must remain in the independent V63 root")
    require(draw_components_out is None or isinstance(draw_components_out, dict)
            and not draw_components_out, "draw output must be a fresh empty dictionary")
    rewards = tuple(rewards)
    require(len(rewards) == cohort.denominator, "complete frozen reward vector required")
    work = [
        dict(trajectory=i, turn=j, draw_seed=ep.config.seed, reward=reward, receipt=turn.receipt)
        for i, (ep, reward) in enumerate(zip(cohort.episodes, rewards, strict=True))
        if reward != 0 for j, turn in enumerate(ep.turns)
    ]
    require(all(row["draw_seed"] in DRAW_SEEDS for row in work), "foreign draw in replay work")
    accumulator = components.DrawAccumulator(
        theta, work, condition_id=condition["id"], denominator=cohort.denominator,
        mean_tolerances=mean_tolerances, monitor=component_monitor, cpu_test=cpu_test)
    if backend_factory is None:
        backend_factory = lambda actual_model, actual_theta: ReplaySession(
            actual_model, actual_theta, temperature=condition["temperature"],
            condition_id=condition["id"], profile_id=kwargs["profile_id"], cpu_test=cpu_test)

    class ObservedSession:
        def __init__(self, session):
            self.session = session

        def __call__(self, actual_model, actual_theta, prompt, targets, **fields):
            values, gradient, report = self.session(actual_model, actual_theta, prompt, targets, **fields)
            accumulator.accumulate(gradient, prompt=prompt, targets=targets, expected=fields["expected"])
            return values, gradient, report

        def close(self, **fields):
            if hasattr(self.session, "close"):
                return self.session.close(**fields)

    def factory(actual_model, actual_theta):
        session = backend_factory(actual_model, actual_theta)
        require(cpu_test or isinstance(session, ReplaySession)
                and session.temperature == condition["temperature"]
                and session.condition_id == condition["id"],
                "production R3 backend differs from sampled batch1 temperature")
        return ObservedSession(session)

    def seal(episodes, **fields):
        return seal_feedback_cohort(episodes, condition=condition, **fields)

    def checkpoints(root, scientific_binding, actual_theta):
        return components.ComponentCheckpoints(
            root, scientific_binding, actual_theta, accumulator=accumulator)

    required_identity = backend_identity(condition, mean_tolerances=mean_tolerances)
    if "backend_identity" in kwargs:
        require(kwargs.pop("backend_identity") == required_identity,
                "checkpoint backend identity differs from registered batch1 contract")
    compute = original.optimized.bind_dependencies(
        original.v32.feedback_gradient, seal_feedback_cohort=seal,
        state=SimpleNamespace(ReplayCheckpoints=checkpoints), BACKEND_VERSION=BACKEND_VERSION)
    # No AST edit, cloned loop, or replacement total: this is the original
    # response order, validation, add_ coefficient, accounting and pause logic.
    gradients, report = compute(
        cohort, rewards, model, theta, backend_factory=factory,
        backend_identity=required_identity, **kwargs)
    require(accumulator.cursor == len(work), "draw diagnostic prefix did not finish with formal replay")
    diagnostics = accumulator.report(gradients)
    if draw_components_out is not None:
        # Ownership transfer; do not hide another full CPU duplicate.
        draw_components_out.update(accumulator.draws)
    report.update(
        feedback_condition_id=condition["id"], temperature=condition["temperature"],
        probability_contract_id=PROBABILITY_CONTRACT_ID, feedback_batch=BATCH, arm=condition["arm"],
        draw_components=diagnostics, formal_and_draw_checkpoint_atomic=True)
    return gradients, report


class LocalFeedbackCollector(HistoricalCollector):
    """New-only b1 collection using original durable-turn/UNKNOWN semantics."""

    def __init__(self, *, arm, attempt_root, batch=BATCH, **kwargs):
        config = RunConfig.model_validate(kwargs["config"])
        self.arm, self.temperature = _arm(config.temperature, arm, batch)
        require(tuple(kwargs.get("seeds", DRAW_SEEDS)) == DRAW_SEEDS,
                "new feedback collector requires draws101,103")
        require(kwargs.pop("recovery_guard_factory", None) is None,
                "old single-request reexecution quota is not available in batch1")
        super().__init__(**{**kwargs, "seeds": DRAW_SEEDS,
                            "config": config.model_copy(update={"temperature": 1.0})})
        self.config = config
        self.attempt_root = Path(attempt_root)
        require(self.root.resolve().is_relative_to(binding.ROOT.resolve())
                and self.attempt_root.resolve().is_relative_to(binding.ROOT.resolve()),
                "new feedback and attempt writes must remain in the independent V63 root")
        self.condition = self.feedback_root = None

    def collect(self, model, tokenizer, theta, *, point_id, event_sink=None):
        from trusted_synthesis.finance_research import storage
        from trusted_synthesis.finance_research.planning import task_key
        from trusted_synthesis.finance_research.v6_task import score_public_reasoning_program

        emit = event_sink or (lambda event: None)
        with installed_point(model, theta) as installed:
            identity = providers.local_model_identity(
                model, tokenizer, model_id=self.model_id, point_id=point_id, parameter_tensors=installed)
            configs = [self.config.model_copy(update={"seed": seed}) for seed in DRAW_SEEDS]
            condition = build_condition(
                identity=identity, temperature=self.temperature, configs=configs,
                task_roster=self.tasks, source_manifest_sha256=digest(self.manifest),
                role_plan_id=self.role_plan["id"], arm=self.arm, batch=BATCH)
            root = self.root / condition["id"]
            self.condition, self.feedback_root = condition, root
            _publish(root / "intent", condition)
            emit(dict(phase="feedback_condition_registration", feedback_root=str(root),
                      feedback_condition_id=condition["id"], temperature=self.temperature,
                      arm=self.arm, feedback_batch=BATCH))
            if (root / "native_rewards/record.json").exists():
                cohort, rewards = read_complete(root, condition)
                emit(dict(phase="restored_complete_feedback_without_rescoring",
                          feedback_root=str(root), feedback_condition_id=condition["id"],
                          denominator=700, feedback_batch=BATCH))
                return cohort, rewards
            for index, config in enumerate(configs):
                directory = root / f"draw{index}"
                if not (directory / "run.json").exists():
                    storage.prepare_run(
                        self.snapshot, self.role_plan, directory, role="feedback", config=config,
                        identity=identity, task_keys=[task_key(task) for task in self.tasks])
                provider = LocalTorchProvider(model, tokenizer, identity, parameter_tensors=installed,
                                              condition=condition, before_call=emit)
                asyncio.run(durable.execute_run_resumable(
                    directory, provider, attempt_root=self.attempt_root / f"draw{index}",
                    inheritance=None,
                    after_return=lambda value: emit(dict(value, phase="after_durable_feedback_return"))))
        episodes, seals = [], []
        for index in range(2):
            _, _, part = storage.sealed_episodes(root / f"draw{index}")
            episodes.extend(part)
            path = root / f"draw{index}/generation_seal/seal.json"
            seals.append(dict(path=str(path), sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
        cohort = seal_feedback_cohort(
            episodes, condition=condition, denominator=700, identity=identity,
            source_manifest_sha256=digest(self.manifest),
            registered_episode_keys=[row["episode_key"] for row in condition["ordered_episode_roster"]])
        _publish(root / "cohort_seal", cohort.model_dump(mode="json"))
        _publish(root / "condition_cohort_binding",
                 condition_cohort_binding(condition, cohort, generation_seals=seals))
        emit(dict(phase="native_scoring", feedback_root=str(root),
                  feedback_condition_id=condition["id"], cohort_seal_sha256=cohort.seal_sha256,
                  denominator=700))
        # Original scorer and references: first private read after both draws
        # are durably complete; an already-saved reward record is never rescored.
        references = storage._read_snapshot_rows(
            self.snapshot, "private.references.jsonl", PrivateReference, self.manifest)
        bundles = {task.task_id: TaskBundle(public=task, reference=reference, lineage=lineage)
                   for task, reference, lineage in zip(self.public, references, self.lineages, strict=True)}
        scores = [score_public_reasoning_program(bundles[ep.task_id], ep) for ep in episodes]
        rewards = [score["native"]["execution_accuracy"] for score in scores]
        valid = all(type(value) in (int, float) and value in (0, 1) for value in rewards)
        if not valid:
            _publish(root / "native_scoring_failure", dict(
                condition_id=condition["id"], cohort_seal_sha256=cohort.seal_sha256,
                scores=scores, unmodified_native_values=rewards, missing_or_unknown_values_imputed=False))
        require(valid, "infrastructure/reference UNKNOWN cannot become zero reward")
        _publish(root / "native_rewards", dict(condition_id=condition["id"],
                 cohort_seal_sha256=cohort.seal_sha256, rewards=rewards, scores=scores))
        emit(dict(phase="feedback_and_native_rewards_complete", feedback_root=str(root),
                  feedback_condition_id=condition["id"], cohort_seal_sha256=cohort.seal_sha256,
                  denominator=700))
        return cohort, rewards
