"""Executable five-task training and sealed virtual-point feedback, not a launcher.

No model is loaded, API called, or device reserved on import. Production entry
requires existing, byte-bound V8 material for all original 1000 tasks. Tiny CPU
controls use a separate, explicitly non-production pool constructor.
"""

from __future__ import annotations

import asyncio
import copy
import hashlib
import io
import json
import random
import re
from collections import Counter
from collections.abc import Mapping
from contextlib import contextmanager
from fractions import Fraction
from pathlib import Path
from types import SimpleNamespace

import torch

from trusted_synthesis.core.immutable_artifacts import write_immutable_artifact_directory

from .contracts import Episode, PrivateReference, RunConfig, TaskBundle, digest
from .feedback import episode_key, feedback_gradient, seal_feedback_cohort
from .kernel import prepare_virtual_point, update_distribution
from .materials import TaskBatch, execute_task_batch_update
from .providers import LocalTorchProvider, local_model_identity, parameter_digest
from .v6_distribution import ARMS, OUTER_STEPS, PARAMETERS, manual_distribution
from .v6_training_plan import build_task_schedule

REVIEW_POLICY_ID = "8bef26302b75eae1cf504df39de8a4da7a794503451edcd6a601805b0969dd99"
ORIGINAL_MATERIAL_ID = "ed78f27d36129f3668f40914824178ce5604b25c60ffc030b1fbb0b90703e1bb"


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _json(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode()


def _publish(path, value):
    path, raw = Path(path), _json(value)
    if path.exists():
        _require((path / "record.json").read_bytes() == raw, "immutable record changed")
        return
    write_immutable_artifact_directory(path, {"record.json": raw})


class VerifiedPool:
    """Thin consumer adapter; never masquerades as an API TokenReceipt/CompletePass.

    Zero-target rows stay in the verified encoding. Only empty backward calls are
    omitted; subsequent prompts still contain their complete original history.
    """

    def __init__(self, task_ids, packages, rows, *, binding_id, chi, production=False):
        self.task_ids = tuple(task_ids)
        self._packages = tuple(copy.deepcopy(packages))
        self._rows = copy.deepcopy(rows)
        self.production_verified = production
        self.cache_id = binding_id
        self.chi = copy.deepcopy(chi)
        counts = {task: Counter() for task in task_ids}
        for item in packages:
            counts[item["task_id"]][item["state_id"]] += 1
        _require(all(counts.values()), "every original task needs material support")
        prior = {
            task: {state: str(Fraction(n, sum(states.values()))) for state, n in states.items()}
            for task, states in counts.items()
        }
        registration = SimpleNamespace(
            dataset="finqa",
            state_support={task: tuple(states) for task, states in counts.items()},
            mu={task: str(Fraction(1, len(task_ids))) for task in task_ids},
            pi0=prior,
            qualification_registration_id=binding_id,
            validator_binding_id="v8_single_authoritative_targets.v1",
        )
        self._manifest = SimpleNamespace(registration=registration)
        self.admitted = True  # Only means this in-memory pool is consumable.

    @property
    def packages(self):
        return self._packages

    def row_arrays(self, package_id):
        return tuple(row for row in self._rows[package_id] if row["target_ids"])


def _validate_encoding(encoding, mask, episode, token_binding):
    _require(
        encoding.get("schema") == "v8_student_encoding.v1"
        and encoding.get("encoding_policy") == "v8_single_authoritative_targets.v1"
        and encoding.get("encoding_admitted") is True
        and encoding.get("context_limit") == 24576
        and encoding.get("context_truncated") is False
        and not encoding.get("failures")
        and encoding.get("not_a_TokenReceipt") is True,
        "unknown, incomplete, truncated or non-V8 Student encoding",
    )
    _require(
        encoding["episode_sha256"] == mask["episode_sha256"] == digest(episode)
        and encoding["resolved_mask_sha256"] == digest(mask)
        and encoding["task_id"] == episode.task_id
        and (encoding["tokenizer_digest"], encoding["chat_template_digest"])
        == tuple(token_binding),
        "Student encoding/episode/mask/tokenizer binding mismatch",
    )
    rows = encoding["rows"]
    _require(len(rows) == len(episode.turns), "all original response rows must remain")
    total = 0
    for row, turn in zip(rows, episode.turns, strict=True):
        _require(
            row["row_sha256"] == digest({k: v for k, v in row.items() if k != "row_sha256"})
            and row["raw_response_sha256"] == _sha(turn.raw_text.encode()),
            "Student row changed or not bound to its original response",
        )
        ids, positions, targets = row["input_ids"], row["target_positions"], row["target_ids"]
        _require(
            ids
            and len(ids) <= 24576
            and all(type(token) is int and token >= 0 for token in ids)
            and len(positions) == len(targets)
            and positions == sorted(set(positions))
            and all(
                type(p) is int and row["prompt_token_count"] <= p < len(ids) and p > 0
                for p in positions
            )
            and [ids[p] for p in positions] == targets,
            "invalid complete-prefix causal targets",
        )
        layers = row["layer_target_positions"]
        _require(
            set(layers) == {"reason", "tool", "final"}
            and sorted(p for values in layers.values() for p in values) == positions,
            "target layers must partition exactly the approved token mask",
        )
        total += len(targets)
    _require(
        total > 0 and total == encoding["L_P"] == encoding["total_supervised_tokens"],
        "whole-package denominator mismatch",
    )


def _generation_contract(protocol, protocol_path, read):
    """Validate the real V8 launch/public prefix without touching generated outcomes."""
    from .planning import task_key, verify_role_plan
    from .storage import load_public_snapshot
    from .v8_representation import validate_material_registration

    _require(
        protocol_path.name == "protocol.json" and protocol_path.parent.name == "registration",
        "generation protocol must be the registered launch file",
    )
    _require(
        protocol.get("schema") == "v8_independent_public_generation_launch.v1"
        and protocol.get("id") == digest({k: v for k, v in protocol.items() if k != "id"}),
        "unknown or changed V8 generation launch",
    )
    original = protocol["original"]
    historical = validate_material_registration(original)
    _require(
        original["id"] == protocol["original_protocol_id"] == ORIGINAL_MATERIAL_ID
        and historical == protocol["original_registration_identity_evidence"]
        and read(
            {
                "path": protocol["original_protocol_path"],
                "sha256": protocol["original_protocol_sha256"],
            }
        )
        == original,
        "original material registration/launch identity mismatch",
    )
    tasks, registered = protocol["task_ids"], protocol["slots"]
    _require(
        tasks == original["task_ids"]
        and registered == original["slots"]
        and protocol["configs_by_task"] == original["configs_by_task"]
        and protocol["snapshot"] == original["original_snapshot"]
        and protocol["snapshot_id"] == original["snapshot_id"]
        and protocol["task_denominator"] == 1000
        and protocol["slot_denominator"] == 8000,
        "launch changed original source/config/roster",
    )
    _require(len(tasks) == len(set(tasks)) == 1000, "original 1000 tasks required")
    manifest, public, lineages = load_public_snapshot(original["original_snapshot"])
    verify_role_plan(original["role_plan"], public, lineages)
    _require(
        manifest["id"] == protocol["snapshot_id"]
        and [
            t.task_id for t in public if original["role_plan"]["assignments"][task_key(t)] == "sft"
        ]
        == tasks,
        "original source/role roster mismatch",
    )
    _require(
        len(registered) == 8000
        and len({s["slot_id"] for s in registered}) == 8000
        and Counter(s["task_id"] for s in registered) == Counter({t: 8 for t in tasks})
        and all(re.fullmatch(r"v7-slot:[0-9a-f]{64}", s["slot_id"]) for s in registered)
        and all(
            sorted(s["slot_index"] for s in registered if s["task_id"] == task) == list(range(8))
            for task in tasks
        ),
        "all original 1000 by 8 registered slots required",
    )
    return protocol_path.parent.parent, manifest


def inspect_generation_binding(entry):
    """Read-only public-prefix check; does not imply generation/material completion."""
    path = Path(entry["path"]).resolve()

    def read(item):
        raw = Path(item["path"]).read_bytes()
        _require(_sha(raw) == item["sha256"], "generation prefix artifact byte SHA mismatch")
        return json.loads(raw)

    protocol = read({**entry, "path": str(path)})
    root, manifest = _generation_contract(protocol, path, read)
    return dict(
        generation_root=str(root),
        generation_launch_id=protocol["id"],
        original_material_protocol_id=protocol["original_protocol_id"],
        snapshot_id=manifest["id"],
        original_tasks=1000,
        original_slots=8000,
        generated_outcomes_read=False,
        material_admission=False,
    )


def load_training_pool(binding_path):
    """Open/hash each bound file once, then cache verified arrays for all updates.

    Binding is a list of existing artifacts, NOT a replacement material schema:
    generation_protocol, generation_seal, inventory, resolutions[task],
    encodings[slot] are {path,sha256}; tokenizer_binding is [codec,template].
    """
    from .probe_collection import slot_directory
    from .settlement import episode_is_complete

    binding_path = Path(binding_path).resolve()
    binding = json.loads(binding_path.read_bytes())
    cache = {}

    def location(entry):
        path = Path(entry["path"])
        return (binding_path.parent / path).resolve() if not path.is_absolute() else path.resolve()

    def read(entry):
        path = location(entry)
        if path not in cache:
            raw = path.read_bytes()  # A missing future artifact fails here, never launches.
            cache[path] = (_sha(raw), json.loads(raw))
        sha, value = cache[path]
        _require(sha == entry["sha256"], f"artifact byte SHA mismatch: {path}")
        return value

    _require(
        binding.get("schema") == "v8_training_artifact_binding.v1"
        and binding.get("review_policy_id") == REVIEW_POLICY_ID,
        "unknown binding/policy",
    )
    protocol = read(binding["generation_protocol"])
    generation_root, manifest = _generation_contract(
        protocol, location(binding["generation_protocol"]), read
    )
    _require(
        location(binding["generation_seal"]) == generation_root / "generation_seal/record.json",
        "generation seal must belong to the registered launch root",
    )
    seal, inventory = (read(binding[key]) for key in ("generation_seal", "inventory"))
    for record in (protocol, seal, inventory):
        _require(
            record.get("id") == digest({k: v for k, v in record.items() if k != "id"}),
            "artifact content identity mismatch",
        )
    tasks = protocol["task_ids"]
    registered = protocol["slots"]
    _require(
        seal.get("schema") == "v8_whole_generation_seal.v1"
        and seal["protocol_id"] == protocol["id"]
        and seal["denominator"] == 8000
        and [r["slot"] for r in seal["slots"]] == registered,
        "complete original generation seal required",
    )
    _require(
        inventory.get("schema") != "v8_native_full_population_support.v1"
        and inventory.get("original_tasks") == 1000
        and inventory.get("original_slots") == 8000
        and inventory.get("all_originals_retained") is True
        and [r["task_id"] for r in inventory["tasks"]] == tasks,
        "separate semantic inventory required; native support is not material admission",
    )
    _require(set(binding["resolutions"]) == set(tasks), "all original resolutions required")
    originals = {}
    for row in seal["slots"]:
        episode_path = slot_directory(generation_root, row["slot"]) / "episode/episode.json"
        _require(
            episode_path.resolve() == episode_path,
            "registered episode path cannot redirect outside its slot",
        )
        episode = Episode.model_validate(
            read({"path": str(episode_path), "sha256": row["episode_file_sha256"]})
        )
        _require(
            row["status"] == "COMPLETE"
            and digest(episode) == row["episode_sha256"]
            and episode_is_complete(episode)
            and episode.task_id == row["slot"]["task_id"]
            and episode.config.model_dump(mode="json")
            == protocol["configs_by_task"][episode.task_id]
            and episode.actual_model_calls == row["actual_model_calls"]
            and episode.stop_reason == row["stop_reason"]
            and episode.all_provider_calls_settled == row["all_provider_calls_settled"],
            "original episode mismatch",
        )
        originals[row["slot"]["slot_id"]] = episode
    packages, arrays, chi, eligible = [], {}, {}, set()
    inventory_tasks = {r["task_id"]: r for r in inventory["tasks"]}
    for task in tasks:
        resolution = read(binding["resolutions"][task])
        _require(
            resolution.get("schema") == "v8_common_material_resolution.v1"
            and resolution["task_id"] == task
            and resolution.get("review_policy_id") == binding["review_policy_id"],
            "unknown or foreign V8 resolution",
        )
        slots = resolution["slots"]
        expected = {s["slot_id"] for s in registered if s["task_id"] == task}
        _require(
            set(slots) == expected and resolution["all_eight_candidates_retained"] is True,
            "original slots absent or substituted",
        )
        valid = {
            sid
            for sid, row in slots.items()
            if row.get("q_native") is True and row.get("v_trace") == "valid"
        }
        _require(
            valid
            and set(resolution["valid_slots_retained"]) == valid
            and resolution["task_mapping"] == "complete"
            and resolution["no_dropping_hard_to_map_valid_packages"] is True,
            "missing task support or incomplete whole-task mapping",
        )
        chi[task], counts = {}, Counter()
        for sid, slot in slots.items():
            _require(type(slot.get("q_native")) is bool, "native assessment incomplete")
            _require(
                slot.get("v_trace") != "not_assessed_native_ineligible"
                or slot["q_native"] is False,
                "unassessed trace requires native False",
            )
            if sid not in valid:
                _require(
                    slot.get("common_material_valid") is not True,
                    "ineligible slot cannot enter common material",
                )
                continue
            _require(
                slot.get("mapper") == "mapped"
                and slot.get("state_id")
                and type(slot.get("chi")) is int
                and slot["chi"] in (0, 1)
                and slot.get("common_material_valid") is True,
                "qualified package lacks mapped state/chi",
            )
            mask = slot["encoding_manifest"]
            _require(mask and mask.get("mask_agreement") is True, "dual mask agreement required")
            encoding = read(binding["encodings"][sid])
            _validate_encoding(encoding, mask, originals[sid], binding["tokenizer_binding"])
            state = slot["state_id"]
            _require(
                state not in chi[task] or chi[task][state] == slot["chi"],
                "chi differs within a mapped state",
            )
            chi[task][state], counts[state] = slot["chi"], counts[state] + 1
            eligible.add(sid)
            arrays[sid] = encoding["rows"]
            packages.append(
                dict(
                    package_id=sid,
                    task_id=task,
                    state_id=state,
                    whole_package_target_tokens=encoding["L_P"],
                    fused=False,
                )
            )
        inv = inventory_tasks[task]
        _require(
            inv["states"] == dict(counts)
            and inv["n_x"] == len(valid)
            and inv["joint_valid"] == len(valid)
            and inv["mapping_complete"] is True
            and inv["masks_complete"] is True,
            "inventory/resolution support mismatch",
        )
    _require(set(binding["encodings"]) == eligible, "all and only joint-valid originals required")
    pool = VerifiedPool(
        tasks, packages, arrays, binding_id=digest(binding), chi=chi, production=True
    )
    pool.tokenizer_binding = tuple(binding["tokenizer_binding"])
    pool.source_manifest_sha256 = digest(manifest)
    pool.generation_launch_id = protocol["id"]
    pool.original_material_protocol_id = protocol["original_protocol_id"]
    pool.verified_file_count = len(cache)
    return pool


def tiny_cpu_pool(task_ids, packages, rows, *, chi):
    """Explicit test-only adapter: cannot authorize CUDA or a production launch."""
    _require(len(task_ids) >= 5, "tiny CPU control still requires five complete tasks")
    return VerifiedPool(
        task_ids,
        packages,
        rows,
        binding_id="tiny_cpu:" + digest(packages),
        chi=chi,
        production=False,
    )


def _rng():
    return dict(
        python=random.getstate(),
        torch=torch.get_rng_state(),
        cuda=torch.cuda.get_rng_state_all() if torch.cuda.is_initialized() else None,
    )


def _restore_rng(state):
    random.setstate(state["python"])
    torch.set_rng_state(state["torch"].cpu())
    if state["cuda"] is not None:
        torch.cuda.set_rng_state_all(state["cuda"])


def _tree_digest(value):
    if isinstance(value, torch.Tensor):
        raw = value.detach().cpu().contiguous()
        return digest(
            dict(
                shape=list(raw.shape),
                dtype=str(raw.dtype),
                sha256=_sha(raw.reshape(-1).view(torch.uint8).numpy().tobytes()),
            )
        )
    if isinstance(value, dict):
        return digest({str(k): _tree_digest(v) for k, v in value.items()})
    if isinstance(value, (tuple, list)):
        return digest([_tree_digest(v) for v in value])
    return digest(value)


@contextmanager
def installed_point(model, theta):
    """Actually install the virtual Student; always restore the live point/RNG."""
    named = dict(model.named_parameters())
    saved = {name: named[name].detach().clone() for name in theta}
    rng, mode = _rng(), model.training
    try:
        with torch.no_grad():
            for name, tensor in theta.items():
                named[name].copy_(tensor)
        model.eval()
        yield {name: named[name] for name in theta}
    finally:
        with torch.no_grad():
            for name, tensor in saved.items():
                named[name].copy_(tensor)
        model.train(mode)
        _restore_rng(rng)


class _DeviceGradients(Mapping):
    """CPU class-gradient cache, transferring only one state at a time for the kernel."""

    def __init__(self, values, device):
        self.values_cpu, self.device = values, device

    def __len__(self):
        return len(self.values_cpu)

    def __iter__(self):
        return iter(self.values_cpu)

    def __getitem__(self, key):
        return {name: tensor.to(self.device) for name, tensor in self.values_cpu[key].items()}


def class_gradients(model, pool, *, device):
    """Real complete-package means, including every single-state control task."""
    from trusted_synthesis.experiments.finance_qa_vnext_fixed_kernel_value import (
        trajectory_consumer,
    )

    named = {n: p for n, p in model.named_parameters() if p.requires_grad}
    counts = Counter((p["task_id"], p["state_id"]) for p in pool.packages)
    values = {
        t: {
            z: {n: torch.zeros_like(p, device="cpu") for n, p in named.items()}
            for z in pool._manifest.registration.pi0[t]
        }
        for t in pool.task_ids
    }
    mode, rng = model.training, _rng()
    model.eval()
    try:
        for package in pool.packages:
            task, state = package["task_id"], package["state_id"]
            coefficient = 1 / (counts[task, state] * package["whole_package_target_tokens"])
            for row in pool.row_arrays(package["package_id"]):
                ids = torch.tensor([row["input_ids"]], device=device)
                positions = torch.tensor(row["target_positions"], device=device) - 1
                targets = torch.tensor(row["target_ids"], device=device)
                logits = model(
                    input_ids=ids,
                    attention_mask=torch.ones_like(ids),
                    use_cache=False,
                    logits_to_keep=positions,
                ).logits
                loss = trajectory_consumer.selected_target_loss(logits, targets, coefficient)
                gradients = torch.autograd.grad(loss, tuple(named.values()))
                for name, gradient in zip(named, gradients, strict=True):
                    values[task][state][name].add_(gradient.detach().cpu())
        return {task: _DeviceGradients(states, device) for task, states in values.items()}
    finally:
        model.train(mode)
        _restore_rng(rng)


class LocalFeedbackCollector:
    """Real 350×2 generation with a common seal BEFORE any private-reference read.

    A partial attempt is never resampled. An existing complete generation seal
    can be read again; no callback is permitted to invent trajectories or rewards.
    """

    def __init__(self, *, snapshot, role_plan, root, config, model_id, seeds=(11, 29)):
        from .planning import task_key, verify_role_plan
        from .storage import load_public_snapshot

        self.snapshot, self.root = Path(snapshot), Path(root)
        self.role_plan, self.config, self.model_id = (
            role_plan,
            RunConfig.model_validate(config),
            model_id,
        )
        self.seeds = tuple(seeds)
        self.manifest, self.public, self.lineages = load_public_snapshot(snapshot)
        verify_role_plan(role_plan, self.public, self.lineages)
        self.tasks = [t for t in self.public if role_plan["assignments"][task_key(t)] == "feedback"]
        _require(len(self.tasks) == 350 and len(set(self.seeds)) == 2, "fixed 350 by 2 feedback")
        cfg = self.config
        _require(
            (
                cfg.tier,
                cfg.role,
                cfg.temperature,
                cfg.top_p,
                cfg.top_k,
                cfg.max_steps,
                cfg.max_new_tokens,
                cfg.context_limit,
                cfg.harness_id,
                cfg.submission_profile,
            )
            == (
                "VTDO_FEEDBACK",
                "feedback",
                1.0,
                1.0,
                0,
                32,
                2048,
                24576,
                "bigfinance-derived-vtdo-v7",
                "finqa-public-reasoning-v2",
            ),
            "feedback must use the registered fixed local harness/sampling contract",
        )

    def collect(self, model, tokenizer, theta, *, point_id, event_sink=None):
        from .planning import task_key
        from .storage import _read_snapshot_rows, execute_run, prepare_run, sealed_episodes
        from .v6_task import score_public_reasoning_program

        root = self.root / digest(point_id)
        emit = event_sink or (lambda event: None)
        emit(dict(phase="feedback_point_installation", feedback_root=str(root)))
        with installed_point(model, theta) as installed:
            identity = local_model_identity(
                model,
                tokenizer,
                model_id=self.model_id,
                point_id=point_id,
                parameter_tensors=installed,
            )
            intent = dict(
                point_id=point_id,
                identity=identity.model_dump(mode="json"),
                source_manifest_sha256=digest(self.manifest),
                role_plan_id=self.role_plan["id"],
                seeds=self.seeds,
                task_ids=[t.task_id for t in self.tasks],
                denominator=700,
            )
            if root.exists():
                emit(dict(phase="restore_complete_feedback", feedback_root=str(root)))
                _require(
                    json.loads((root / "intent/record.json").read_bytes())
                    == json.loads(_json(intent)),
                    "feedback intent changed",
                )
                _require(
                    all((root / f"draw{i}/generation_seal/seal.json").exists() for i in range(2)),
                    "partial feedback attempt retained; automatic resampling forbidden",
                )
            else:
                _publish(root / "intent", intent)
                for index, seed in enumerate(self.seeds):
                    emit(
                        dict(
                            phase="feedback_generation",
                            feedback_root=str(root),
                            draw_index=index,
                            feedback_seed=seed,
                        )
                    )
                    cfg = self.config.model_copy(update={"seed": seed})
                    directory = root / f"draw{index}"
                    prepare_run(
                        self.snapshot,
                        self.role_plan,
                        directory,
                        role="feedback",
                        config=cfg,
                        identity=identity,
                        task_keys=[task_key(t) for t in self.tasks],
                    )
                    provider = LocalTorchProvider(
                        model, tokenizer, identity, parameter_tensors=installed
                    )
                    asyncio.run(execute_run(directory, provider))
            emit(dict(phase="feedback_cohort_validation", feedback_root=str(root)))
            episodes = []
            for index in range(2):
                _, _, part = sealed_episodes(root / f"draw{index}")
                episodes.extend(part)
            cohort = seal_feedback_cohort(
                episodes,
                denominator=700,
                identity=identity,
                source_manifest_sha256=digest(self.manifest),
                registered_episode_keys=[episode_key(ep) for ep in episodes],
            )
            _publish(root / "cohort_seal", cohort.model_dump(mode="json"))
            emit(
                dict(
                    phase="native_scoring",
                    feedback_root=str(root),
                    cohort_seal_sha256=cohort.seal_sha256,
                    denominator=cohort.denominator,
                )
            )
            # This is deliberately AFTER the common 700-cohort seal, not after draw0.
            references = _read_snapshot_rows(
                self.snapshot, "private.references.jsonl", PrivateReference, self.manifest
            )
            bundles = {
                t.task_id: TaskBundle(public=t, reference=r, lineage=lineage)
                for t, r, lineage in zip(self.public, references, self.lineages, strict=True)
            }
            scores = [score_public_reasoning_program(bundles[e.task_id], e) for e in episodes]
            rewards = [score["native"]["execution_accuracy"] for score in scores]
            valid_rewards = all(type(r) in (int, float) and r in (0, 1) for r in rewards)
            if not valid_rewards:
                # Preserve each fixed-cohort position and actual None/reason before
                # the original rejection. This artifact is never a reward source.
                _publish(
                    root / "native_scoring_failure",
                    dict(
                        schema="fixed_feedback_scoring_failure.v1",
                        cohort_seal_sha256=cohort.seal_sha256,
                        denominator=cohort.denominator,
                        positions=[
                            dict(
                                index=i,
                                episode_key=episode_key(ep),
                                task_id=ep.task_id,
                                feedback_seed=ep.config.seed,
                                score=score,
                            )
                            for i, (ep, score) in enumerate(zip(episodes, scores, strict=True))
                        ],
                        unmodified_native_values=rewards,
                        not_rewards_admitted=True,
                        missing_or_unknown_values_imputed=False,
                        feedback_resampled=False,
                    ),
                )
            _require(
                valid_rewards,
                "infrastructure/reference unknown cannot become zero reward",
            )
            _publish(
                root / "native_rewards",
                dict(cohort_seal_sha256=cohort.seal_sha256, rewards=rewards, scores=scores),
            )
            emit(
                dict(
                    phase="feedback_and_native_rewards_complete",
                    feedback_root=str(root),
                    cohort_seal_sha256=cohort.seal_sha256,
                    denominator=cohort.denominator,
                )
            )
            return cohort, rewards


def validate_student_adapters(model, adapter_scope=None):
    """Check the repository's actual custom q/v LowRankLinear implementation.

    ``adapter_scope`` may be the second value returned by existing load_student;
    it is checked against the installed tensors, never substituted for that check.
    This checks architecture, not whether a resumed adapter is freshly initialized.
    """
    from trusted_synthesis.experiments.finance_qa_vnext_pq_student.model import LowRankLinear
    from trusted_synthesis.experiments.finance_qa_vnext_pq_student.plan import record

    layers = getattr(getattr(model, "config", None), "num_hidden_layers", None)
    _require(type(layers) is int and layers > 0, "registered Qwen layer count required")
    expected = {
        f"model.layers.{i}.self_attn.{target}"
        for i in range(layers)
        for target in ("q_proj", "v_proj")
    }
    adapters = {
        name: module for name, module in model.named_modules() if isinstance(module, LowRankLinear)
    }
    _require(set(adapters) == expected, "custom LoRA must cover exactly every Qwen q/v target")
    trainable = {}
    for name, module in adapters.items():
        _require(
            type(module) is LowRankLinear and isinstance(module.base, torch.nn.Linear),
            "existing LowRankLinear implementation required",
        )
        _require(
            module.lora_A.shape == (8, module.base.in_features)
            and module.lora_B.shape == (module.base.out_features, 8)
            and module.scaling == 2.0,
            "registered custom LoRA rank8/alpha16 changed",
        )
        _require(
            type(module.dropout) is torch.nn.Dropout and module.dropout.p == 0.05,
            "registered custom LoRA dropout .05 changed",
        )
        for suffix in ("lora_A", "lora_B"):
            tensor = getattr(module, suffix)
            _require(
                tensor.requires_grad
                and tensor.dtype == torch.float32
                and tensor.device == module.base.weight.device,
                "custom LoRA A/B must be trainable colocated FP32",
            )
            trainable[f"{name}.{suffix}"] = tensor
    parameters = dict(model.named_parameters())
    _require(
        {name for name, value in parameters.items() if value.requires_grad} == set(trainable),
        "only registered custom LoRA A/B may be trainable",
    )
    _require(
        all(
            not value.requires_grad and value.dtype == torch.bfloat16
            for name, value in parameters.items()
            if name not in trainable
        ),
        "all original Base parameters must remain frozen BF16",
    )
    shapes = {name: list(value.shape) for name, value in trainable.items()}
    count = sum(value.numel() for value in trainable.values())
    if adapter_scope is not None:
        expected_record = record(
            "trainable_adapter_scope",
            **{k: v for k, v in adapter_scope.items() if k not in ("id", "schema_version")},
        )
        _require(
            adapter_scope == expected_record
            and set(adapter_scope["target_module_names"]) == expected
            and len(adapter_scope["target_module_names"]) == len(expected)
            and adapter_scope["trainable_shapes"] == shapes
            and adapter_scope["trainable_parameter_count"] == count
            and adapter_scope["base_weights_frozen"] is True
            and adapter_scope["input_output_embeddings_frozen"] is True,
            "load_student adapter scope differs from actual installed custom LoRA",
        )
    return dict(
        implementation="repository.LowRankLinear",
        target_module_names=sorted(adapters),
        trainable_shapes=shapes,
        trainable_parameter_count=count,
        rank=8,
        scaling=2.0,
        dropout=0.05,
        base_dtype="bfloat16",
        adapter_dtype="float32",
        loader_scope_id=adapter_scope["id"] if adapter_scope is not None else None,
    )


def material_report_identity(material_schema):
    """Audit labels follow the real successor binding; original supervision stays fixed."""
    version = {
        "v18_researcher_complete_material_binding.v1": "v18",
        "v17_three_task_complete_material_binding.v1": "v17",
        "v16_six_task_complete_material_binding.v1": "v16",
        "v15_complete_material_binding.v1": "v15",
        "v14_material_binding.v1": "v14",
        "v13_material_binding.v1": "v13",
        "v10_material_binding.v1": "v10",
    }.get(material_schema, "v8")
    policy = {
        "v18": "v14_state_independent_original_span_union.v1",
        "v17": "v14_state_independent_original_span_union.v1",
        "v16": "v14_state_independent_original_span_union.v1",
        "v15": "v14_state_independent_original_span_union.v1",
        "v14": "v14_state_independent_original_span_union.v1",
        "v13": "v13_fixed_authority_original_spans.v1",
        "v10": "v10_single_authority_original_spans.v1",
        "v8": "v8_single_authoritative_targets.v1",
    }[version]
    return version, policy


def outer_failure_kind(error, phase):
    """Classify only observed exceptions/stages, never reinterpret a failure as Q=0."""
    chain, seen, current = [], set(), error
    while current is not None and id(current) not in seen and len(chain) < 8:
        seen.add(id(current))
        chain.append(current)
        current = current.__cause__ or current.__context__
    messages = " ".join(str(item).lower() for item in chain)
    if (
        any(isinstance(item, (MemoryError, torch.cuda.OutOfMemoryError)) for item in chain)
        or "out of memory" in messages
    ):
        return "resource_OOM"
    if phase == "logP_replay" and (
        "probability_mismatch" in messages
        or "probabilities differ" in messages
        or "sampling_probability_mismatch" in messages
    ):
        return "logP_replay_mismatch"
    if any(word in messages for word in ("nonfinite", "non-finite")) or re.search(
        r"\b(?:nan|infinity)\b", messages
    ):
        return "nonfinite_numeric"
    if isinstance(error, OSError):
        return "other_engineering_failure"
    if phase == "native_scoring":
        return "scoring_infrastructure_failure"
    if phase in {"feedback_generation", "restore_complete_feedback", "feedback_cohort_validation"}:
        return "missing_or_incomplete_feedback"
    return "other_engineering_failure"


class FirstOuterAudit:
    """Append-only first-formal-outer phases; no extra Student computation or sampling."""

    def __init__(self, driver):
        from .calibration import now

        self.driver, self.now = driver, now
        attempts = driver.root / "outer_attempts" / f"step{driver.step_index:04d}"
        self.root = attempts / f"attempt{len(list(attempts.glob('attempt*'))) + 1:03d}"
        self.last_phase, self.last_phase_ref, self.last_replay_progress = None, None, None
        self.counter, self.feedback_root = 0, None
        self.identity = dict(
            seed=driver.seed,
            arm=driver.arm,
            step=driver.step_index,
            pool_id=driver.pool.cache_id,
            schedule_sha256=driver.schedule["schedule_sha256"],
            CPU_control_only=not driver.pool.production_verified,
        )
        self.intent = self.publish(
            "intent",
            dict(
                schema="first_formal_outer_intent.v1",
                at=now(),
                **self.identity,
                formal_experiment_not_pilot=True,
                registered_denominator=700 if driver.pool.production_verified else None,
                last_committed_training_step=driver.step_index,
                optimizer_steps_in_outer=0,
                automatic_resampling=False,
                context_or_denominator_changed=False,
            ),
        )

    def publish(self, relative, value):
        record = {**value, "id": digest(value)}
        directory = self.root / relative
        _publish(directory, record)
        path = directory / "record.json"
        return dict(path=str(path.resolve()), id=record["id"], sha256=_sha(path.read_bytes()))

    def phase(self, name, **metadata):
        self.last_phase = name
        if "feedback_root" in metadata:
            self.feedback_root = metadata["feedback_root"]
        self.last_phase_ref = self.publish(
            f"phases/{self.counter:03d}",
            dict(
                schema="first_formal_outer_phase.v1",
                at=self.now(),
                **self.identity,
                phase=name,
                **metadata,
            ),
        )
        self.counter += 1

    def collector_event(self, event):
        self.phase(event["phase"], **{k: v for k, v in event.items() if k != "phase"})

    def replay_progress(self, event):
        # The existing callback reports completed response backpropagation only.
        # Keep that limited meaning; it does not identify a later failing token.
        self.last_replay_progress = copy.deepcopy(event)

    def failure(self, error):
        seals, incomplete = {}, []
        if self.feedback_root is not None:
            root = Path(self.feedback_root)
            for name, relative in (
                ("draw0", "draw0/generation_seal/seal.json"),
                ("draw1", "draw1/generation_seal/seal.json"),
                ("cohort", "cohort_seal/record.json"),
                ("scoring_failure", "native_scoring_failure/record.json"),
                ("native_rewards", "native_rewards/record.json"),
            ):
                path = root / relative
                seals[name] = dict(path=str(path.resolve()), exists=path.is_file())
            # execute_run retains the actual provider settlement before raising
            # its generic UnsettledExecution. Preserve its observed exception type
            # so a wrapped CUDA OOM is not mislabeled as merely a missing receipt.
            for path in sorted(root.glob("draw*/incomplete/*/record.json")):
                record = json.loads(path.read_bytes())
                incomplete.append(
                    dict(
                        path=str(path.resolve()),
                        sha256=_sha(path.read_bytes()),
                        episode_key=record.get("episode_key"),
                        stop_reason=record.get("stop_reason"),
                        exception_types=[
                            row.get("evidence", {}).get("exception_type")
                            for row in record.get("call_settlements", [])
                        ],
                    )
                )
        kind = outer_failure_kind(error, self.last_phase)
        if any(
            name in {"OutOfMemoryError", "MemoryError"}
            for record in incomplete
            for name in record["exception_types"]
        ):
            kind = "resource_OOM"
        checkpoint = self.driver.root / f"step{self.driver.step_index:04d}_outer/record.json"
        return self.publish(
            "failure",
            dict(
                schema="first_formal_outer_failure.v1",
                at=self.now(),
                **self.identity,
                intent=self.intent,
                last_phase=self.last_phase,
                last_phase_record=self.last_phase_ref,
                failure_kind=kind,
                error_type=type(error).__name__,
                error=str(error),
                last_completed_replay_response=self.last_replay_progress,
                feedback_artifacts=seals,
                retained_incomplete_feedback=incomplete,
                outer_commit_record_exists=checkpoint.is_file(),
                last_committed_training_step=self.driver.step_index,
                failure_counted_as_Q_zero=False,
                feedback_resampled=False,
                context_or_denominator_changed=False,
                automatic_retry=False,
                stopped_before_next_training_step=True,
                recovery=(
                    "explicit inspection and durable checkpoint restore; never refill partial700"
                ),
            ),
        )

    def complete(self, checkpoint):
        self.publish(
            "complete",
            dict(
                schema="first_formal_outer_complete.v1",
                at=self.now(),
                **self.identity,
                intent=self.intent,
                last_phase=self.last_phase,
                last_phase_record=self.last_phase_ref,
                outer_checkpoint=str(checkpoint.resolve()),
                outer_commit_completed=True,
                optimizer_steps_in_outer=0,
            ),
        )


class TrainingDriver:
    """One actual optimizer step/commit per call; explicit arms after shared step400."""

    def __init__(
        self,
        model,
        optimizer,
        pool,
        *,
        root,
        seed,
        arm="shared",
        device="cpu",
        tokenizer=None,
        feedback_collector=None,
        cpu_control_schedule=None,
        adapter_scope=None,
        execution_plan=None,
        task_schedule=None,
    ):
        _require(arm in (*ARMS, "shared"), "unknown arm")
        _require(type(optimizer) is torch.optim.AdamW, "actual AdamW required")
        _require(
            pool.production_verified or (str(device) == "cpu" and cpu_control_schedule),
            "unverified material cannot launch production training",
        )
        self.model, self.optimizer, self.pool = model, optimizer, pool
        self.root, self.seed, self.arm, self.device = Path(root), seed, arm, device
        self.tokenizer, self.collector = tokenizer, feedback_collector
        self.execution_plan = copy.deepcopy(execution_plan)
        if execution_plan is not None:
            from .v9_conditional_training import validate_execution_schedule

            validate_execution_schedule(execution_plan, task_schedule, pool.task_ids, seed)
            _require(
                not pool.production_verified
                or (
                    getattr(pool, "conditional_scope_verified", False)
                    and execution_plan == pool.execution_plan
                ),
                "conditional execution requires the strict V9 parent/scope binding",
            )
            self.schedule = copy.deepcopy(task_schedule)
        else:
            _require(task_schedule is None, "custom production schedule needs a V9 scope binding")
            self.schedule = (
                build_task_schedule(pool.task_ids, seed)
                if pool.production_verified
                else copy.deepcopy(cpu_control_schedule)
            )
        self.shared_step = execution_plan["shared_step"] if execution_plan else 400
        self.outer_steps = tuple(execution_plan["outer_steps"]) if execution_plan else OUTER_STEPS
        self.final_step = execution_plan["final_step"] if execution_plan else 2000
        self.sharing_split_step = execution_plan["sharing_split_step"] if execution_plan else 1200
        self.parameters = {n: p for n, p in model.named_parameters() if p.requires_grad}
        self.adapter_binding = None
        _require(self.parameters, "actual trainable parameter coordinates required")
        _require(
            {id(p) for g in optimizer.param_groups for p in g["params"]}
            == {id(p) for p in self.parameters.values()},
            "optimizer parameter mismatch",
        )
        if pool.production_verified:
            from .providers import tokenizer_binding

            _require(
                tokenizer is not None and tokenizer_binding(tokenizer) == pool.tokenizer_binding,
                "actual training tokenizer differs from encoded material",
            )
            _require(seed in (11, 29, 47), "paired seeds11/29/47 only")
            _require(
                all(p.dtype == torch.float32 for p in self.parameters.values()),
                "registered trainable LoRA coordinates must be FP32",
            )
            for group in optimizer.param_groups:
                _require(
                    (group["lr"], group["betas"], group["eps"], group["weight_decay"])
                    == (1e-4, (0.9, 0.999), 1e-8, 0),
                    "registered fixed AdamW configuration changed",
                )
                _require(
                    not any(
                        group.get(flag, False)
                        for flag in ("maximize", "amsgrad", "fused", "capturable", "differentiable")
                    ),
                    "AdamW configuration is unsupported by the frozen pullback",
                )
            self.adapter_binding = validate_student_adapters(model, adapter_scope)
        self.base_digest = parameter_digest(
            {n: p for n, p in model.named_parameters() if not p.requires_grad}
        )
        self.prior = copy.deepcopy(pool._manifest.registration.pi0)
        self.pi = copy.deepcopy(self.prior)
        self.step_index, self.outer_done, self.tainted = 0, [], False
        self.initialized = False

    def _payload(self):
        payload = dict(
            schema="v8_committed_training_state.v1",
            seed=self.seed,
            arm=self.arm,
            pool_id=self.pool.cache_id,
            schedule=self.schedule,
            step=self.step_index,
            outer_done=list(self.outer_done),
            pi=self.pi,
            prior=self.prior,
            adapter_binding=self.adapter_binding,
            frozen_base_digest=self.base_digest,
            parameters={n: p.detach().cpu().clone() for n, p in self.parameters.items()},
            buffers={n: p.detach().cpu().clone() for n, p in self.model.named_buffers()},
            optimizer=copy.deepcopy(self.optimizer.state_dict()),
            rng=_rng(),
            model_training=self.model.training,
        )
        if self.execution_plan is not None:
            payload["execution_plan"] = self.execution_plan
        return payload

    def commit(self, phase="step", evidence=None, *, outer_inputs=None):
        payload = self._payload()
        buffer = io.BytesIO()
        torch.save(payload, buffer)
        raw = buffer.getvalue()
        directory = self.root / f"step{self.step_index:04d}_{phase}"
        summary = dict(
            step=self.step_index,
            phase=phase,
            arm=self.arm,
            seed=self.seed,
            state_sha256=_sha(raw),
            actual_state_digest=_tree_digest(payload),
            pool_id=self.pool.cache_id,
            schedule_sha256=self.schedule["schedule_sha256"],
            evidence=evidence,
            checkpoint_contains_actual_model_Adam_RNG_pi=True,
        )
        files = {"state.pt": raw}
        if outer_inputs is not None:
            _require(phase == "outer", "real outer tensors belong only to an outer commit")
            buffer = io.BytesIO()
            torch.save(outer_inputs, buffer)
            inputs_raw = buffer.getvalue()
            files["outer_inputs.pt"] = inputs_raw
            summary["outer_inputs_sha256"] = _sha(inputs_raw)
            summary["outer_inputs_digest"] = _tree_digest(outer_inputs)
            summary["outer_inputs_bytes"] = len(inputs_raw)
        files["record.json"] = _json(summary)
        write_immutable_artifact_directory(directory, files)
        return directory

    def restore(self, directory, *, branch=False):
        directory = Path(directory)
        summary = json.loads((directory / "record.json").read_bytes())
        raw = (directory / "state.pt").read_bytes()
        _require(_sha(raw) == summary["state_sha256"], "committed checkpoint bytes changed")
        # Non-capturable Adam step tensors and RNG receipts must stay on CPU.
        # load_state_dict moves parameter moments to the actual parameter device.
        state = torch.load(io.BytesIO(raw), map_location="cpu", weights_only=False)
        _require(_tree_digest(state) == summary["actual_state_digest"], "state digest mismatch")
        _require(
            state["pool_id"] == self.pool.cache_id
            and state["seed"] == self.seed
            and state["schedule"] == self.schedule
            and state.get("execution_plan") == self.execution_plan
            and state["frozen_base_digest"] == self.base_digest,
            "checkpoint/model/material/schedule binding mismatch",
        )
        _require(
            state.get("adapter_binding") == self.adapter_binding,
            "checkpoint custom adapter architecture/scope changed",
        )
        _require(
            (state["arm"] == self.arm and not branch)
            or (
                branch
                and state["arm"] == "shared"
                and state["step"] == self.shared_step
                and self.arm in ARMS
                and not state["outer_done"]
            ),
            "branch only from the actual registered shared snapshot",
        )
        with torch.no_grad():
            for name, value in state["parameters"].items():
                self.parameters[name].copy_(value)
            buffers = dict(self.model.named_buffers())
            for name, value in state["buffers"].items():
                buffers[name].copy_(value)
        self.optimizer.load_state_dict(state["optimizer"])
        _restore_rng(state["rng"])
        self.model.train(state["model_training"])
        self.pi, self.prior = copy.deepcopy(state["pi"]), copy.deepcopy(state["prior"])
        self.step_index, self.outer_done, self.tainted = state["step"], state["outer_done"], False
        self.initialized = True
        if branch and self.arm in ("Manual+", "Manual-"):
            self.pi = manual_distribution(
                self.prior,
                self.pool.chi,
                direction=self.arm,
                registered_singleton_tasks=getattr(self.pool, "registered_singleton_tasks", ()),
            )
        if branch:
            self.commit(
                "branch",
                dict(
                    shared_checkpoint=str(directory),
                    shared_actual_state_digest=summary["actual_state_digest"],
                ),
            )

    def step(self):
        _require(not self.tainted, "failed uncommitted update: restore a committed checkpoint")
        _require(
            self.step_index < (self.shared_step if self.arm == "shared" else self.final_step),
            "arm complete",
        )
        _require(self.step_index < len(self.schedule["batches"]), "schedule exhausted")
        _require(
            not self.pool.production_verified
            or self.arm == "shared"
            or self.step_index >= self.shared_step,
            "production branches require the actual registered shared checkpoint",
        )
        if self.arm in ("C-only", "Full") and self.step_index in self.outer_steps:
            _require(
                self.step_index in self.outer_done,
                "real sealed outer update required before next batch",
            )
        if not self.initialized:
            _require(
                not self.root.exists(), "existing run requires explicit committed-state restore"
            )
            self.commit("initial")
            self.initialized = True
        entry = self.schedule["batches"][self.step_index]
        _require(
            len(entry["task_ids"]) == len(set(entry["task_ids"]))
            and (
                1 <= len(entry["task_ids"]) <= 5
                if self.execution_plan is not None
                else len(entry["task_ids"]) == 5
            ),
            "update must contain exactly the registered real complete-task batch",
        )
        batch = TaskBatch(
            task_ids=tuple(entry["task_ids"]),
            sampling_probability={
                t: str(Fraction(1, len(self.pool.task_ids))) for t in self.pool.task_ids
            },
            sampling_design="uniform_epoch_permutation",
            schedule_id=self.schedule["schedule_sha256"],
            step=self.step_index + 1,
        )
        self.tainted = True
        self.model.train()
        report = execute_task_batch_update(
            self.model, self.optimizer, self.pool, self.pi, batch, device=self.device, arm=self.arm
        )
        _require(
            report["optimizer_step_calls"] == report["clip_calls"] == 1,
            "exactly one real clip and optimizer step required",
        )
        self.step_index += 1
        underlying_update_id = report.pop("id")
        material_version, supervision_policy = material_report_identity(
            getattr(self.pool, "material_schema", None)
        )
        report.update(
            schema_version=f"{material_version}_actual_task_batch_update.v1",
            underlying_task_batch_update_id=underlying_update_id,
            supervision_policy=supervision_policy,
            loss_domain="review-approved original token spans/actions/EOS; full-package L_P",
            execution_design=f"original_unfused_response_rows_{material_version}",
            original_history_retained=True,
            actual_parameter_update=True,
            CPU_control_only=not self.pool.production_verified,
        )
        report["id"] = f"{material_version}_task_batch_update:" + digest(report)
        self.commit("step", report)
        self.tainted = False
        return report

    def outer_update(self, *, cpu_control_feedback=None, replay=None):
        _require(
            not self.tainted
            and self.arm in ("C-only", "Full")
            and self.step_index in self.outer_steps
            and self.step_index not in self.outer_done,
            "outer update requires an actual scheduled committed point",
        )
        _require(
            self.collector is not None
            or (not self.pool.production_verified and cpu_control_feedback),
            "real feedback collector unavailable; outer chain is blocked",
        )
        if self.pool.production_verified:
            _require(
                type(self.collector) is LocalFeedbackCollector
                and replay is None
                and cpu_control_feedback is None,
                "production cannot replace real collection/replay with test callbacks",
            )
        audit = FirstOuterAudit(self) if self.step_index == self.shared_step else None
        try:
            return self._outer_update(
                cpu_control_feedback=cpu_control_feedback, replay=replay, audit=audit
            )
        except BaseException as failure:
            self.tainted = True
            if audit is not None:
                try:
                    failure.outer_failure_audit = audit.failure(failure)
                except Exception as audit_failure:
                    # Never replace the real engineering fault with a logging fault.
                    failure.outer_audit_write_error = (
                        f"{type(audit_failure).__name__}: {audit_failure}"
                    )
            raise

    def _outer_update(self, *, cpu_control_feedback=None, replay=None, audit=None):
        if audit is not None:
            audit.phase("capture_pre_outer_state")
        pre_outer_state = self._payload()
        if audit is not None:
            audit.phase("full_class_gradients")
        gradients = class_gradients(self.model, self.pool, device=self.device)
        mu = self.pool._manifest.registration.mu
        if audit is not None:
            audit.phase("virtual_Adam")
        prepared = prepare_virtual_point(self.parameters, self.optimizer, gradients, self.pi, mu)
        if audit is not None:
            audit.phase("virtual_point_identity")
        point_id = digest(
            dict(
                pool=self.pool.cache_id,
                seed=self.seed,
                step=self.step_index,
                sharing_domain=(
                    self.arm
                    if self.step_index >= self.sharing_split_step
                    else "common_actual_point"
                ),
                theta=parameter_digest(prepared["theta_bar"]),
                frozen_base_digest=self.base_digest,
                buffers=_tree_digest(dict(self.model.named_buffers())),
                G=parameter_digest(prepared["G"]),
                adam=_tree_digest(self.optimizer.state_dict()),
                rng=_tree_digest(_rng()),
                schedule=self.schedule["schedule_sha256"],
                pi=self.pi,
            )
        )
        self.tainted = True
        if audit is not None:
            audit.phase("feedback_generation_and_scoring", point_id=point_id)
        if self.pool.production_verified or self.collector is not None:
            collector_options = (
                dict(event_sink=audit.collector_event)
                if audit is not None and type(self.collector) is LocalFeedbackCollector
                else {}
            )
            cohort, rewards = self.collector.collect(
                self.model,
                self.tokenizer,
                prepared["theta_bar"],
                point_id=point_id,
                **collector_options,
            )
        else:
            cohort, rewards = cpu_control_feedback(prepared, point_id)
        _require(
            not self.pool.production_verified or cohort.denominator == 700,
            "production feedback denominator must remain 700",
        )
        if audit is not None:
            audit.phase(
                "logP_replay",
                point_id=point_id,
                cohort_seal_sha256=cohort.seal_sha256,
                denominator=cohort.denominator,
            )
        with installed_point(self.model, prepared["theta_bar"]) as installed:
            replay_options = dict(event_sink=audit.replay_progress) if audit is not None else {}
            gJ, report = feedback_gradient(
                cohort, rewards, self.model, installed, replay=replay, **replay_options
            )
        if audit is not None:
            audit.phase("optimizer_pullback_Contribution_and_pi", point_id=point_id)
        result = update_distribution(
            prepared,
            gradients,
            gJ,
            self.pi,
            self.prior,
            mu,
            feedback_report=report,
            contribution_only=self.arm == "C-only",
            control_tasks=[t for t, p in self.prior.items() if len(p) == 1],
            **PARAMETERS,
        )
        if audit is not None:
            audit.phase("outer_commit", point_id=point_id)
        self.pi = result["distribution"]["pi_next"]
        self.outer_done.append(self.step_index)
        evidence = {k: v for k, v in result.items() if k != "a"}
        evidence.update(
            actual_virtual_theta_digest=parameter_digest(prepared["theta_bar"]),
            population_gradient_digest=parameter_digest(prepared["G"]),
            feedback_gradient_digest=parameter_digest(gJ),
            pullback_digest=parameter_digest(result["a"]),
            feedback_seal_sha256=cohort.seal_sha256,
            actual_feedback_denominator=cohort.denominator,
            shared_with_other_arm=False,
        )
        # Retain actual inputs for same-point mechanisms; digests alone cannot
        # execute the registered N-only intervention without new feedback.
        outer_inputs = dict(
            schema="v9_real_outer_inputs.v1",
            pre_state=pre_outer_state,
            point_id=point_id,
            mu=copy.deepcopy(mu),
            G={n: p.detach().cpu().clone() for n, p in prepared["G"].items()},
            theta_bar={n: p.detach().cpu().clone() for n, p in prepared["theta_bar"].items()},
            gJ={n: p.detach().cpu().clone() for n, p in gJ.items()},
            pullback={n: p.detach().cpu().clone() for n, p in result["a"].items()},
            C=copy.deepcopy(result["C"]),
            q_next=copy.deepcopy(self.pi),
            feedback_seal=cohort.model_dump(mode="json", exclude={"episodes"}),
            rewards=list(rewards),
            feedback_report=copy.deepcopy(report),
            actual_tensors_saved=True,
            new_feedback_for_mechanisms=False,
        )
        checkpoint = self.commit("outer", evidence, outer_inputs=outer_inputs)
        if audit is not None:
            audit.complete(checkpoint)
        self.tainted = False
        return evidence

    def run_until(self, stop):
        """Execute the requested interval, invoking real due outer updates en route.

        Arrival at an outer coordinate preserves the pre-outer checkpoint. The
        outer runs before departing that coordinate, including a resumed run.
        This method never creates/models/collectors or grants material admission.
        """
        limit = self.shared_step if self.arm == "shared" else self.final_step
        _require(
            type(stop) is int and self.step_index <= stop <= limit,
            "requested interval is outside the fixed training schedule",
        )
        while self.step_index < stop:
            if (
                self.arm in ("C-only", "Full")
                and self.step_index in self.outer_steps
                and self.step_index not in self.outer_done
            ):
                self.outer_update()
            self.step()
        return dict(
            arm=self.arm,
            seed=self.seed,
            committed_step=self.step_index,
            outer_done=list(self.outer_done),
            production=self.pool.production_verified,
        )


def identical_committed_state(left, right):
    """Only actual bound state proof; no inference from equal rewards or pi alone."""

    def state(path):
        path = Path(path)
        record = json.loads((path / "record.json").read_bytes())
        raw = (path / "state.pt").read_bytes()
        _require(_sha(raw) == record["state_sha256"], "state proof byte mismatch")
        value = torch.load(io.BytesIO(raw), map_location="cpu", weights_only=False)
        _require(
            _tree_digest(value) == record["actual_state_digest"], "state proof content mismatch"
        )
        # Arm labels do not alter the actual computation state; everything else does.
        return _tree_digest({k: v for k, v in value.items() if k != "arm"})

    return state(left) == state(right)


def conditional_sharing_proof(left, right, *, shared_step=400):
    """Sharing is optional and only proved from actual paired step400 outer commits."""
    records = [json.loads((Path(p) / "record.json").read_bytes()) for p in (left, right)]
    fields = (
        "actual_virtual_theta_digest",
        "population_gradient_digest",
        "feedback_gradient_digest",
        "feedback_seal_sha256",
        "pullback_digest",
        "C",
    )
    return (
        identical_committed_state(left, right)
        and {r["arm"] for r in records} == {"C-only", "Full"}
        and all(
            r["step"] == shared_step
            and r["phase"] == "outer"
            and r["evidence"]["actual_feedback_denominator"] == 700
            for r in records
        )
        and all(records[0]["evidence"][key] == records[1]["evidence"][key] for key in fields)
    )
