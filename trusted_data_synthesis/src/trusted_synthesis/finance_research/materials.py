"""Explicitly qualified real-token material, not an automatic state certifier.

Neither native answer correctness, a successful tool call, wording, nor call
order proves CompletePass or establishes a trajectory equivalence class. A
caller must supply a separately registered validator and its explicit decisions.
Unknown/invalid decisions remain in the inventory but never become train states.
Source-role provenance must already have been admitted from original splits.
"""

from __future__ import annotations

import math
from collections import Counter
from fractions import Fraction
from typing import Literal

from pydantic import model_validator

from .contracts import Episode, Record, digest
from .encoding import (
    EOS_POLICY,
    SUPERVISION_POLICY,
    StudentEncodingRecord,
    _native_response,
    events_for_turns,
    probe_generation_record,
    supervised_turns,
)
from .providers import _sha, canonical_assistant_message
from .settlement import episode_is_complete


class QualificationDecision(Record):
    episode_sha256: str
    task_id: str
    verdict: Literal["CompletePass", "invalid", "unknown"]
    state_id: str | None = None
    evidence_sha256: str
    reason: str

    @model_validator(mode="after")
    def explicit_state(self):
        if self.verdict == "CompletePass" and not self.state_id:
            raise ValueError("CompletePass requires an explicitly assigned registered state")
        if self.verdict != "CompletePass" and self.state_id is not None:
            raise ValueError("unknown/invalid material cannot mint a valid state")
        if any(len(value) != 64 for value in (self.episode_sha256, self.evidence_sha256)):
            raise ValueError("qualification requires bound episode and validator evidence hashes")
        return self


class MaterialRegistration(Record):
    source_manifest_sha256: str
    validator_binding_id: str
    qualification_registration_id: str
    dataset: str = "finqa"
    state_support: dict[str, tuple[str, ...]]
    mu: dict[str, str | float]
    pi0: dict[str, dict[str, str | float]]
    decisions: tuple[QualificationDecision, ...]

    @model_validator(mode="after")
    def explicit_registration(self):
        if len(self.source_manifest_sha256) != 64:
            raise ValueError("an admitted original-split source manifest is required")
        if not self.validator_binding_id or not self.qualification_registration_id:
            raise ValueError("independent validator and qualification registration are required")
        if (
            not self.state_support
            or set(self.state_support) != set(self.mu)
            or set(self.state_support) != set(self.pi0)
        ):
            raise ValueError("registered task supports must match")
        for task, states in self.state_support.items():
            if not states or len(set(states)) != len(states) or any(not state for state in states):
                raise ValueError("states must be explicitly named and unique per task")
            if set(states) != set(self.pi0[task]):
                raise ValueError("prior must have exactly the declared state support")
        _validate_mass(self.mu, "task marginal")
        for states in self.pi0.values():
            _validate_mass(states, "state prior")
        hashes = [decision.episode_sha256 for decision in self.decisions]
        if len(set(hashes)) != len(hashes):
            raise ValueError("one episode cannot receive multiple qualification decisions")
        for decision in self.decisions:
            if decision.task_id not in self.state_support:
                raise ValueError("qualification task is outside registered support")
            if (
                decision.verdict == "CompletePass"
                and decision.state_id not in self.state_support[decision.task_id]
            ):
                raise ValueError("qualification cannot create an undeclared state")
        return self


def _fraction(value):
    if isinstance(value, bool):
        raise ValueError("probability/mass cannot be boolean")
    return Fraction(str(value))


def _validate_mass(values, label):
    masses = [_fraction(value) for value in values.values()]
    if (
        not masses
        or any(value <= 0 for value in masses)
        or not math.isclose(float(sum(masses)), 1.0, rel_tol=0, abs_tol=1e-12)
    ):
        raise ValueError(f"{label} must be an interior simplex without probability repair")


class TokenTrainingRow(Record):
    input_ids: tuple[int, ...]
    target_positions: tuple[int, ...]
    target_ids: tuple[int, ...]
    call_id: str


class TrainingPackage(Record):
    package_id: str
    episode_sha256: str
    task_id: str
    state_id: str
    whole_package_target_tokens: int
    tokenizer_digest: str
    chat_template_digest: str
    rows: tuple[TokenTrainingRow, ...]
    encoding_origin: Literal["actual_local_tokens", "offline_student_tokenizer"] = (
        "actual_local_tokens"
    )
    student_encoding_id: str | None = None
    supervision_policy: str = SUPERVISION_POLICY
    eos_policy: str = EOS_POLICY


class MaterialPoolManifest(Record):
    cache_id: str
    registration: MaterialRegistration
    inventory: tuple[dict, ...]
    packages: tuple[TrainingPackage, ...]
    admitted: bool
    missing_support: tuple[tuple[str, str], ...]
    static_control_tasks: tuple[str, ...]
    state_semantics_independently_proven: bool = False
    validation_scope: str = "byte binding and structural admission, not state-semantic proof"
    original_response_rows_retained: bool = True
    target_retokenization_performed: bool = False
    offline_student_encoding_used: bool = False


class MaterialPool:
    """One frozen inventory, exposing the existing training consumer's cache API."""

    def __init__(self, manifest: MaterialPoolManifest):
        expected = "finance_materials:" + digest(
            manifest.model_dump(mode="json", exclude={"cache_id"})
        )
        if manifest.cache_id != expected:
            raise ValueError("material pool manifest content identity mismatch")
        # Keep a private round-trippable snapshot, not mutable caller dictionaries.
        self._manifest = MaterialPoolManifest.model_validate_json(manifest.model_dump_json())
        self.cache_id = manifest.cache_id
        self._packages = {package.package_id: package for package in self._manifest.packages}

    @property
    def manifest(self):
        return MaterialPoolManifest.model_validate_json(self._manifest.model_dump_json())

    @property
    def admitted(self):
        return self._manifest.admitted

    @property
    def packages(self):
        return tuple(
            package.model_dump(exclude={"rows"}) | {"fused": False}
            for package in self._manifest.packages
        )

    def row_arrays(self, package_id):
        if not self.admitted:
            raise ValueError("incomplete registered support is not an admitted training cache")
        # Zero-target failed turns remain in the frozen package and all later
        # actual prompts. Do not ask the consumer to backpropagate an empty loss.
        return tuple(
            row.model_dump(exclude={"call_id"})
            for row in self._packages[package_id].rows
            if row.target_ids
        )


def _training_rows(episode: Episode):
    if episode.config.role != "sft" or episode.provider.backend != "local_torch":
        raise ValueError("training packages require SFT-role local Student token receipts")
    if (
        episode.actual_model_calls != len(episode.turns)
        or not episode.turns
        or episode.stop_reason != "final_answer"
        or episode.error is not None
        or episode.final_answer is None
        or not episode_is_complete(episode)
    ):
        raise ValueError("incomplete generated episode cannot become a training package")
    rows, calls = [], set()
    previous_request, previous_turn, previous_event = None, None, None
    for turn, supervise, event in zip(
        episode.turns, supervised_turns(episode), events_for_turns(episode), strict=True
    ):
        receipt = turn.receipt
        if receipt is None or receipt.identity != episode.provider:
            raise ValueError("missing or foreign actual token receipt")
        if not receipt.identity.tokenizer_digest or not receipt.identity.chat_template_digest:
            raise ValueError("training tokens require a bound tokenizer and template")
        if receipt.call_id in calls:
            raise ValueError("duplicate response receipt")
        calls.add(receipt.call_id)
        if receipt.raw_response_sha256 != _sha(turn.raw_text):
            raise ValueError("training receipt text binding mismatch")
        request = turn.provider_metadata.get("request")
        if (
            request is None
            or digest(request) != receipt.request_sha256
            or request.get("config") != episode.config.model_dump(mode="json")
        ):
            raise ValueError("training receipt request/config binding mismatch")
        if previous_turn is not None:
            if len(previous_turn.tool_calls) != 1 or previous_event is None:
                raise ValueError("continued local trajectory lacks its actual tool event")
            previous_call = previous_turn.tool_calls[0]
            expected_messages = previous_request["messages"] + [
                canonical_assistant_message(previous_turn),
                {
                    "role": "tool",
                    "tool_call_id": previous_call.call_id,
                    "content": previous_event.visible_output,
                },
            ]
            if request.get("messages") != expected_messages:
                raise ValueError("local SFT history was dropped, altered or compacted")
        previous_request, previous_turn, previous_event = request, turn, event
        if receipt.sampling.get("actual_model_generate_calls") != 1 or any(
            receipt.sampling.get(key) is not False
            for key in ("context_truncated", "host_JSON_repair", "SFT_mask_used")
        ):
            raise ValueError("training requires complete original generated response tokens")
        prompt, targets = receipt.prompt_input_ids, receipt.raw_generated_token_ids
        if (
            not prompt
            or not targets
            or len(targets) > episode.config.max_new_tokens
            or len(prompt) + episode.config.max_new_tokens > episode.config.context_limit
            or len(prompt) + len(targets) > 24576
            or any(type(token) is not int or token < 0 for token in (*prompt, *targets))
        ):
            raise ValueError("invalid untruncated real token rows")
        if receipt.actual_eos != (targets[-1] in receipt.sampling.get("eos_token_ids", [])):
            raise ValueError("EOS token accounting mismatch")
        rows.append(
            TokenTrainingRow(
                input_ids=prompt + targets,
                target_positions=tuple(range(len(prompt), len(prompt) + len(targets)))
                if supervise
                else (),
                target_ids=targets if supervise else (),
                call_id=receipt.call_id,
            )
        )
    return tuple(rows)


def build_material_pool(
    episodes, registration: MaterialRegistration, *, student_encodings=()
) -> MaterialPool:
    """Bind qualifications to local tokens or separate offline API Probe encoding.

    API SFT does not require API logP. Its Student IDs are never presented as
    actual Probe sampling tokens. Neither pathway infers CompletePass, changes
    the registered support, or drops missing tasks.
    """
    registration = MaterialRegistration.model_validate_json(registration.model_dump_json())
    episodes = tuple(episodes)
    encodings = tuple(
        StudentEncodingRecord.model_validate_json(row.model_dump_json())
        for row in student_encodings
    )
    by_encoding = {row.episode_sha256: row for row in encodings}
    if len(by_encoding) != len(encodings):
        raise ValueError("one Student encoding is permitted per frozen episode")
    by_hash = {digest(episode): episode for episode in episodes}
    if len(by_hash) != len(episodes) or set(by_hash) != {
        decision.episode_sha256 for decision in registration.decisions
    }:
        raise ValueError("every distinct source episode needs exactly one explicit decision")
    if set(by_encoding) - set(by_hash):
        raise ValueError("Student encoding has no source episode in this pool")
    inventory, packages, calls = [], [], set()
    for decision in registration.decisions:
        episode = by_hash[decision.episode_sha256]
        if (
            episode.task_id != decision.task_id
            or episode.dataset != registration.dataset
            or episode.config.role != "sft"
        ):
            raise ValueError("qualification dataset/task/SFT-role mismatch")
        inventory.append({**decision.model_dump(), "retained": True})
        if decision.verdict != "CompletePass":
            continue
        encoded = by_encoding.get(decision.episode_sha256)
        if episode.provider.backend == "deepseek_api":
            probe = probe_generation_record(episode)
            if encoded is None or encoded.generation_record_id != probe.generation_record_id:
                raise ValueError("API Probe SFT requires a separately bound StudentEncodingRecord")
            positive = supervised_turns(episode)
            if (
                len(encoded.rows) != len(episode.turns)
                or tuple(row.supervised for row in encoded.rows) != positive
            ):
                raise ValueError("Student encoding supervision differs from actual tool outcomes")
            if any(
                row.public_request_sha256 != digest(request)
                or row.raw_response_sha256 != _sha(turn.raw_text)
                or row.rendered_response != _native_response(turn)
                for row, request, turn in zip(
                    encoded.rows, probe.public_requests, episode.turns, strict=True
                )
            ):
                raise ValueError("Student encoding raw evidence binding mismatch")
            rows = tuple(
                TokenTrainingRow(
                    **row.model_dump(
                        include={"call_id", "input_ids", "target_positions", "target_ids"}
                    )
                )
                for row in encoded.rows
            )
            token_hash, template_hash = encoded.tokenizer_digest, encoded.chat_template_digest
        else:
            if encoded is not None:
                raise ValueError("offline API encoding cannot replace actual local token receipts")
            rows = _training_rows(episode)
            token_hash, template_hash = (
                episode.provider.tokenizer_digest,
                episode.provider.chat_template_digest,
            )
        if not sum(len(row.target_ids) for row in rows):
            raise ValueError("qualified package has no positive-response target tokens")
        if calls & {row.call_id for row in rows}:
            raise ValueError("one actual response cannot fill multiple training packages")
        calls.update(row.call_id for row in rows)
        body = dict(
            episode_sha256=decision.episode_sha256,
            task_id=decision.task_id,
            state_id=decision.state_id,
            whole_package_target_tokens=sum(len(row.target_ids) for row in rows),
            tokenizer_digest=token_hash,
            chat_template_digest=template_hash,
            rows=[row.model_dump(mode="json") for row in rows],
            encoding_origin="offline_student_tokenizer" if encoded else "actual_local_tokens",
            student_encoding_id=encoded.encoding_id if encoded else None,
        )
        packages.append(TrainingPackage(package_id="package:" + digest(body), **body))
    if len({package.tokenizer_digest for package in packages}) > 1:
        raise ValueError("one training cache cannot mix incompatible tokenizers")
    if len({package.chat_template_digest for package in packages}) > 1:
        raise ValueError("one training cache cannot mix incompatible Student templates")
    counts = Counter((package.task_id, package.state_id) for package in packages)
    missing = tuple(
        (task, state)
        for task, states in registration.state_support.items()
        for state in states
        if not counts[task, state]
    )
    body = dict(
        registration=registration.model_dump(mode="json"),
        inventory=inventory,
        packages=[package.model_dump(mode="json") for package in packages],
        admitted=not missing,
        missing_support=missing,
        static_control_tasks=tuple(
            task for task, states in registration.state_support.items() if len(states) == 1
        ),
        offline_student_encoding_used=any(package.student_encoding_id for package in packages),
        target_retokenization_performed=any(package.student_encoding_id for package in packages),
    )
    prototype = MaterialPoolManifest(cache_id="pending", **body)
    manifest = prototype.model_copy(
        update={
            "cache_id": "finance_materials:"
            + digest(prototype.model_dump(mode="json", exclude={"cache_id"}))
        }
    )
    return MaterialPool(manifest)


def weighted_examples(pool: MaterialPool, pi):
    """Full-population G/control coefficients, not a mini-batch training update."""
    if not pool.admitted:
        raise ValueError("all preregistered states need explicitly qualified material")
    registration = pool._manifest.registration
    if set(pi) != set(registration.state_support):
        raise ValueError("training distribution task support changed")
    for task, states in registration.state_support.items():
        if set(pi[task]) != set(states):
            raise ValueError("training distribution cannot add or remove states")
        _validate_mass(pi[task], "training state probability")
        if len(states) == 1 and _fraction(pi[task][states[0]]) != 1:
            raise ValueError("single-state task is a static control")
    counts = Counter((row["task_id"], row["state_id"]) for row in pool.packages)
    examples = []
    for package in pool.packages:
        task, state = package["task_id"], package["state_id"]
        coefficient = (
            _fraction(registration.mu[task])
            * _fraction(pi[task][state])
            / (counts[task, state] * package["whole_package_target_tokens"])
        )
        examples.append(
            {
                **package,
                "target_token_coefficient": str(coefficient),
                "coefficient_float": float(coefficient),
                "n_state": counts[task, state],
            }
        )
    return examples


def execute_training_update(
    model, optimizer, pool: MaterialPool, pi, *, device, arm="vtdo", event_sink=None
):
    """Explicit full-pool update through the frozen local trajectory consumer.

    Calling this function really trains. Building/importing material never does.
    The existing consumer uses global clip norm 1 and one optimizer step. Its old
    hardcoded textual loss-rule label is replaced in this new report, not reused.
    """
    from trusted_synthesis.experiments.finance_qa_vnext_fixed_kernel_value import (
        trajectory_consumer,
    )

    examples = weighted_examples(pool, pi)
    tasks = list(pool._manifest.registration.state_support)
    original = trajectory_consumer.execute_update(
        model,
        optimizer,
        examples,
        {"tasks": tasks},
        pool=pool._manifest.registration.dataset,
        arm=arm,
        device=device,
        trajectory_cache=pool,
        event_sink=event_sink,
    )
    fields = {
        key: value
        for key, value in original.items()
        if key not in {"id", "schema_version", "loss_rule", "execution_design", "loss_domain"}
    }
    result = {
        "schema_version": "finance_research.qualified_token_update.v1",
        **fields,
        "loss_rule": "mu(task)*pi(state|task)/(n_state*whole_package_target_tokens)",
        "loss_domain": SUPERVISION_POLICY + "; " + EOS_POLICY,
        "execution_design": "positive_response_rows_v2",
        "full_pool_update": True,
        "legacy_consumer_result_sha256": digest(original),
        "qualification_registration_id": pool._manifest.registration.qualification_registration_id,
        "validator_binding_id": pool._manifest.registration.validator_binding_id,
        "state_semantics_independently_proven": False,
    }
    return {**result, "id": "qualified_token_update:" + digest(result)}


class TaskBatch(Record):
    """A realized task draw with the preregistered marginal sampling law.

    Repeated IID draws repeat a task's whole original package set; they do not
    create new states or change n_state. Epoch permutations use uniform p_s and
    disallow duplicate tasks within a batch. Batch normalization occurs here once.
    """

    task_ids: tuple[str, ...]
    sampling_probability: dict[str, str | float]
    sampling_design: Literal["iid_with_replacement", "uniform_epoch_permutation"]
    schedule_id: str
    step: int

    @model_validator(mode="after")
    def valid_draw(self):
        if not self.task_ids or not self.schedule_id or self.step < 0:
            raise ValueError("TaskBatch requires nonempty registered schedule coordinates")
        _validate_mass(self.sampling_probability, "task sampling probability")
        if set(self.task_ids) - set(self.sampling_probability):
            raise ValueError("drawn task has no sampling probability")
        if self.sampling_design == "uniform_epoch_permutation" and (
            len(set(self.task_ids)) != len(self.task_ids)
            or any(
                _fraction(value) != Fraction(1, len(self.sampling_probability))
                for value in self.sampling_probability.values()
            )
        ):
            raise ValueError(
                "uniform permutation batches require uniform probabilities and unique draws"
            )
        return self


def task_batch_examples(pool: MaterialPool, pi, batch: TaskBatch):
    """mu/(B*p_s) * pi/(n_state*L); no subsequent division by B."""
    batch = TaskBatch.model_validate_json(batch.model_dump_json())
    if set(batch.sampling_probability) != set(pool._manifest.registration.state_support):
        raise ValueError("task sampler cannot omit a registered task or renormalize support")
    by_task = {}
    for package in weighted_examples(pool, pi):
        by_task.setdefault(package["task_id"], []).append(package)
    result = []
    for draw_index, task in enumerate(batch.task_ids):
        divisor = len(batch.task_ids) * _fraction(batch.sampling_probability[task])
        for package in by_task[task]:
            coefficient = Fraction(package["target_token_coefficient"]) / divisor
            result.append(
                {
                    **package,
                    "target_token_coefficient": str(coefficient),
                    "coefficient_float": float(coefficient),
                    "task_draw_index": draw_index,
                }
            )
    return result


def execute_task_batch_update(
    model,
    optimizer,
    pool: MaterialPool,
    pi,
    batch: TaskBatch,
    *,
    device,
    arm="vtdo",
    event_sink=None,
):
    """Really execute exactly one optimizer update via the original consumer."""
    from trusted_synthesis.experiments.finance_qa_vnext_fixed_kernel_value import (
        trajectory_consumer,
    )

    examples = task_batch_examples(pool, pi, batch)
    original = trajectory_consumer.execute_update(
        model,
        optimizer,
        examples,
        {"tasks": list(batch.task_ids)},
        pool=pool._manifest.registration.dataset,
        arm=arm,
        device=device,
        trajectory_cache=pool,
        event_sink=event_sink,
    )
    fields = {
        key: value
        for key, value in original.items()
        if key not in {"id", "schema_version", "loss_rule", "execution_design", "loss_domain"}
    }
    result = {
        **fields,
        "schema_version": "finance_research.task_batch_update.v1",
        "loss_rule": "mu(task)/(B*p_s(task))*pi(state|task)/(n_state*whole_package_target_tokens)",
        "loss_domain": SUPERVISION_POLICY + "; " + EOS_POLICY,
        "execution_design": "positive_response_rows_v2",
        "full_pool_update": False,
        "batch_size": len(batch.task_ids),
        "additional_batch_division": False,
        "task_batch": batch.model_dump(mode="json"),
        "legacy_consumer_result_sha256": digest(original),
        "qualification_registration_id": pool._manifest.registration.qualification_registration_id,
        "validator_binding_id": pool._manifest.registration.validator_binding_id,
        "state_semantics_independently_proven": False,
    }
    return {**result, "id": "task_batch_update:" + digest(result)}
