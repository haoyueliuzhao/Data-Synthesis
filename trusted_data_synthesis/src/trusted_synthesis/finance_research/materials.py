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
from .providers import _sha


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
        return tuple(row.model_dump(exclude={"call_id"}) for row in self._packages[package_id].rows)


def _training_rows(episode: Episode):
    if episode.config.role != "sft" or episode.provider.backend != "local_torch":
        raise ValueError("training packages require SFT-role local Student token receipts")
    if (
        episode.actual_model_calls != len(episode.turns)
        or not episode.turns
        or episode.stop_reason != "final_answer"
        or episode.error is not None
        or episode.final_answer is None
    ):
        raise ValueError("incomplete generated episode cannot become a training package")
    rows, calls = [], set()
    for turn in episode.turns:
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
                target_positions=tuple(range(len(prompt), len(prompt) + len(targets))),
                target_ids=targets,
                call_id=receipt.call_id,
            )
        )
    return tuple(rows)


def build_material_pool(episodes, registration: MaterialRegistration) -> MaterialPool:
    """Bind decisions to original tokens; do not infer or certify state semantics."""
    registration = MaterialRegistration.model_validate_json(registration.model_dump_json())
    episodes = tuple(episodes)
    by_hash = {digest(episode): episode for episode in episodes}
    if len(by_hash) != len(episodes) or set(by_hash) != {
        decision.episode_sha256 for decision in registration.decisions
    }:
        raise ValueError("every distinct source episode needs exactly one explicit decision")
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
        rows = _training_rows(episode)
        if calls & {row.call_id for row in rows}:
            raise ValueError("one actual response cannot fill multiple training packages")
        calls.update(row.call_id for row in rows)
        body = dict(
            episode_sha256=decision.episode_sha256,
            task_id=decision.task_id,
            state_id=decision.state_id,
            whole_package_target_tokens=sum(len(row.target_ids) for row in rows),
            tokenizer_digest=episode.provider.tokenizer_digest,
            chat_template_digest=episode.provider.chat_template_digest,
            rows=[row.model_dump(mode="json") for row in rows],
        )
        packages.append(TrainingPackage(package_id="package:" + digest(body), **body))
    if len({package.tokenizer_digest for package in packages}) > 1:
        raise ValueError("one training cache cannot mix incompatible tokenizers")
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
    """General mu*pi/(n_state*whole-package targets), with no old batch-size five."""
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
        "loss_domain": "all original response tokens including EOS; no retokenization",
        "execution_design": "original_response_rows_v1",
        "full_pool_update": True,
        "legacy_consumer_result_sha256": digest(original),
        "qualification_registration_id": pool._manifest.registration.qualification_registration_id,
        "validator_binding_id": pool._manifest.registration.validator_binding_id,
        "state_semantics_independently_proven": False,
    }
    return {**result, "id": "qualified_token_update:" + digest(result)}
