"""Read-only V32 admission for existing V25 feedback, never a sampling entry point.

This module does not resume B, publish files, score answers, construct a provider,
or call the frozen collector. A manifest binds bytes, not recovery authorization.
The runtime point must still be independently recomputed before consuming it.
"""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import finqa_v25_training_replication as replication

SCHEMA = "v32_read_only_same_point_manifest.v1"
TARGETS = (
    (
        137,
        "c_only",
        1192,
        "step",
        "c07e70cc25add945f46a87646a237679d093ad26f15cd94a9efc4d0a2a2c402a",
    ),
    (137, "full", 1192, "step", "48ae977e67bf65a82f9823c01e86ea1481f3303d61ba5f5d9ed75bf92b2ae57f"),
    (
        251,
        "c_only",
        894,
        "step",
        "1c1030c652c297cc960ed4c9d0f674596e06381281e88257092bdb42531afc09",
    ),
    (
        137,
        "c_only",
        298,
        "outer",
        "946a8dacfdd859ee75515ce946589c7832156995956e6e974b44087e54148238",
    ),
)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def _digest(value):
    # Same canonical JSON encoding as frozen contracts.digest, without importing
    # torch merely to reject a changed point or missing feedback directory.
    return hashlib.sha256(
        json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode()
    ).hexdigest()


def _runtime(frozen_runtime=None):
    rt = frozen_runtime if frozen_runtime is not None else replication.load_runtime()
    require(
        Path(rt.v8.__file__).resolve()
        == replication.FROZEN
        / ("trusted_data_synthesis/src/trusted_synthesis/finance_research/v8_training_driver.py"),
        "only the original frozen numerical runtime is admitted",
    )
    return rt


def _read(path):
    path = Path(path)
    require(path.is_file(), "required sealed file is missing: " + str(path))
    raw = path.read_bytes()
    return json.loads(raw), dict(path=str(path.resolve()), sha256=hashlib.sha256(raw).hexdigest())


def _file_ref(path):
    path = Path(path)
    require(path.is_file(), "required checkpoint file is missing: " + str(path))
    sha = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            sha.update(chunk)
    return dict(path=str(path.resolve()), sha256=sha.hexdigest())


def registered_targets(root=replication.DEFAULT_ROOT):
    """Four fixed targets; this is not a request to launch any of them."""
    root = Path(root).resolve()
    result = []
    for seed, arm, step, phase, point_id in TARGETS:
        branch = root / f"seed{seed}/arms/{arm}"
        result.append(
            dict(
                name=f"seed{seed}_{arm}_outer{step}",
                purpose="completed_point_benchmark"
                if phase == "outer"
                else "pending_outer_binding_only",
                checkpoint=str(branch / f"training/step{step:04d}_{phase}"),
                feedback_root=str(branch / "feedback" / _digest(point_id)),
                expected_point_id=point_id,
            )
        )
    return result


def _checked_manifest(manifest):
    require(manifest.get("schema") == SCHEMA, "same-point manifest schema mismatch")
    require(
        manifest.get("id") == _digest({k: v for k, v in manifest.items() if k != "id"}),
        "same-point manifest identity changed",
    )
    require(
        manifest.get("read_only") is True
        and manifest.get("new_sampling_allowed") is False
        and manifest.get("training_resume_authorized") is False,
        "manifest cannot authorize sampling or formal training",
    )


def check_recomputed_point(manifest, point_id, feedback_root=None):
    """Fail before model/provider construction or mkdir; never substitute an ID.

    ``point_id`` must be the result of the frozen actual-state computation, e.g.
    :func:`recompute_point_id`, not a copied identity from the old intent.
    """
    _checked_manifest(manifest)
    require(
        point_id == manifest["point_id"], "actual recomputed point_id drift; resampling forbidden"
    )
    root = Path(manifest["feedback_root"]).resolve()
    require(root.name == _digest(point_id), "sealed feedback root does not match point_id")
    if feedback_root is not None:
        require(Path(feedback_root).resolve() == root, "new feedback root forbidden")
    require(root.is_dir(), "original sealed feedback root missing; creation forbidden")
    for relative in (
        "intent/record.json",
        "draw0/generation_seal/seal.json",
        "draw1/generation_seal/seal.json",
        "cohort_seal/record.json",
        "native_rewards/record.json",
    ):
        require((root / relative).is_file(), "required sealed file is missing: " + relative)
    return root


def recompute_point_id(pre_state, *, theta_bar, G, frozen_runtime=None):
    """Frozen V18 point formula on actual saved/rebuilt tensors and complete state.

    Completed-point validation uses saved ``outer_inputs.pre_state/G/theta_bar``;
    a future pending-outer resume must use the restored state and newly computed
    G/theta_bar along the unchanged frozen numerical path.
    """
    v8 = _runtime(frozen_runtime).v8
    split = (pre_state.get("execution_plan") or {}).get("sharing_split_step", 1200)
    return v8.digest(
        dict(
            pool=pre_state["pool_id"],
            seed=pre_state["seed"],
            step=pre_state["step"],
            sharing_domain=pre_state["arm"]
            if pre_state["step"] >= split
            else "common_actual_point",
            theta=v8.parameter_digest(theta_bar),
            frozen_base_digest=pre_state["frozen_base_digest"],
            buffers=v8._tree_digest(pre_state["buffers"]),
            G=v8.parameter_digest(G),
            adam=v8._tree_digest(pre_state["optimizer"]),
            rng=v8._tree_digest(pre_state["rng"]),
            schedule=pre_state["schedule"]["schedule_sha256"],
            pi=pre_state["pi"],
        )
    )


def _load_sealed(root, intent, rt):
    """Use frozen receipt validation, but never its collector/publisher/scorer."""
    require(intent["point_id"] == intent["identity"]["point_id"], "intent point mismatch")
    require(
        intent["denominator"] == 700
        and len(intent["task_ids"]) == 350
        and len(set(intent["task_ids"])) == 350
        and len(set(intent["seeds"])) == 2,
        "fixed 350 by 2 cohort required",
    )
    episodes, bindings = [], {}
    for index, seed in enumerate(intent["seeds"]):
        draw = root / f"draw{index}"
        run, seal, part = rt.storage.sealed_episodes(draw)
        require(
            run["registered_denominator"] == seal["registered_denominator"] == len(part) == 350,
            "fixed draw denominator changed",
        )
        require(
            run["config"]["seed"] == seed
            and [ep.task_id for ep in part] == intent["task_ids"]
            and all(ep.config.seed == seed for ep in part),
            "original episode/seed order changed",
        )
        require(
            run["provider"] == intent["identity"]
            and run["source_manifest_sha256"] == intent["source_manifest_sha256"]
            and run["role_plan_id"] == intent["role_plan_id"],
            "draw intent changed",
        )
        episodes.extend(part)
        bindings[f"draw{index}_run"] = _file_ref(draw / "run.json")
        bindings[f"draw{index}_seal"] = _file_ref(draw / "generation_seal/seal.json")
    identity = episodes[0].provider
    require(identity.model_dump(mode="json") == intent["identity"], "sealed model identity changed")
    cohort = rt.v8.seal_feedback_cohort(
        episodes,
        denominator=700,
        identity=identity,
        source_manifest_sha256=intent["source_manifest_sha256"],
        registered_episode_keys=[rt.v8.episode_key(ep) for ep in episodes],
    )
    original, bindings["cohort"] = _read(root / "cohort_seal/record.json")
    require(original == cohort.model_dump(mode="json"), "original complete cohort seal changed")
    native, bindings["rewards"] = _read(root / "native_rewards/record.json")
    rewards = native["rewards"]
    require(
        native["cohort_seal_sha256"] == cohort.seal_sha256
        and len(rewards) == 700
        and all(type(r) in (int, float) and r in (0, 1) for r in rewards),
        "unchanged complete native reward vector required",
    )
    require(
        len(native["scores"]) == 700
        and [score["native"]["execution_accuracy"] for score in native["scores"]] == rewards,
        "stored native scores and reward vector differ; rescoring forbidden",
    )
    return cohort, rewards, bindings


def build_manifest(checkpoint, feedback_root, *, expected_point_id, frozen_runtime=None):
    """Read/verify existing artifacts and return a JSON manifest; writes nothing."""
    checkpoint, root = Path(checkpoint).resolve(), Path(feedback_root).resolve()
    require(
        root.is_dir() and root.name == _digest(expected_point_id),
        "original point-specific sealed feedback root required; creation forbidden",
    )
    require(
        checkpoint.parent.name == "training"
        and root.parent.name == "feedback"
        and checkpoint.parent.parent == root.parent.parent,
        "cross-branch feedback forbidden",
    )
    intent, intent_ref = _read(root / "intent/record.json")
    require(
        intent["point_id"] == expected_point_id, "registered point_id differs from original intent"
    )
    record, record_ref = _read(checkpoint / "record.json")
    require(
        (
            record["seed"],
            {"C-only": "c_only", "Full": "full"}.get(record["arm"]),
            record["step"],
            record["phase"],
            expected_point_id,
        )
        in TARGETS,
        "only three paused outers and the fixed completed benchmark point are admitted",
    )
    state_ref = _file_ref(checkpoint / "state.pt")
    require(state_ref["sha256"] == record["state_sha256"], "checkpoint bytes changed")
    rt = _runtime(frozen_runtime)
    state = rt.torch.load(checkpoint / "state.pt", map_location="cpu", weights_only=False)
    require(
        rt.v8._tree_digest(state) == record["actual_state_digest"],
        "checkpoint state digest changed",
    )
    require(
        all(state[k] == record[k] for k in ("seed", "arm", "step", "pool_id")),
        "checkpoint coordinate changed",
    )
    require(
        state["schedule"]["schedule_sha256"] == record["schedule_sha256"],
        "checkpoint schedule changed",
    )
    outer_ref, pre_state = None, state
    if record["phase"] == "outer":
        outer_ref = _file_ref(checkpoint / "outer_inputs.pt")
        require(
            outer_ref["sha256"] == record["outer_inputs_sha256"], "outer evidence bytes changed"
        )
        actual = rt.torch.load(
            checkpoint / "outer_inputs.pt", map_location="cpu", weights_only=False
        )
        require(
            rt.v8._tree_digest(actual) == record["outer_inputs_digest"],
            "outer evidence digest changed",
        )
        pre_state = actual["pre_state"]
        require(
            actual["point_id"]
            == expected_point_id
            == recompute_point_id(
                pre_state, theta_bar=actual["theta_bar"], G=actual["G"], frozen_runtime=rt
            ),
            "saved actual benchmark point drift",
        )
    else:
        require(record["step"] not in state["outer_done"], "pending outer was already committed")
    cohort, rewards, bindings = _load_sealed(root, intent, rt)
    if outer_ref is not None:
        require(
            actual["feedback_seal"] == cohort.model_dump(mode="json", exclude={"episodes"})
            and actual["rewards"] == rewards,
            "saved outer feedback/rewards changed",
        )
    manifest = dict(
        schema=SCHEMA,
        point_id=expected_point_id,
        feedback_root=str(root),
        checkpoint=str(checkpoint),
        seed=record["seed"],
        arm=record["arm"],
        step=record["step"],
        phase=record["phase"],
        checkpoint_record=record_ref,
        checkpoint_state=state_ref,
        outer_inputs=outer_ref,
        actual_state_digest=record["actual_state_digest"],
        pre_state_digest=rt.v8._tree_digest(pre_state),
        component_digest={
            k: rt.v8._tree_digest(pre_state[k])
            for k in (
                "parameters",
                "buffers",
                "optimizer",
                "rng",
                "pi",
                "schedule",
                "adapter_binding",
            )
        },
        intent=intent,
        intent_file=intent_ref,
        feedback_files=bindings,
        cohort_seal_sha256=cohort.seal_sha256,
        rewards_sha256=rt.v8.digest(rewards),
        ordered_episode_keys_sha256=rt.v8.digest(cohort.registered_episode_keys),
        denominator=700,
        episode_bytes_verified=700,
        read_only=True,
        new_sampling_allowed=False,
        native_rescoring_allowed=False,
        training_resume_authorized=False,
        pending_point_recomputation_required=record["phase"] != "outer",
    )
    manifest["id"] = _digest(manifest)
    return manifest


def read_sealed_feedback(manifest, *, frozen_runtime=None):
    """Load all original 700 episodes and rewards; not an admission to sample."""
    root = check_recomputed_point(manifest, manifest["point_id"])
    intent, intent_ref = _read(root / "intent/record.json")
    require(
        intent_ref == manifest["intent_file"] and intent == manifest["intent"],
        "original feedback intent bytes changed",
    )
    rt = _runtime(frozen_runtime)
    cohort, rewards, bindings = _load_sealed(root, intent, rt)
    require(bindings == manifest["feedback_files"], "original sealed feedback bytes changed")
    require(
        cohort.seal_sha256 == manifest["cohort_seal_sha256"]
        and rt.v8.digest(rewards) == manifest["rewards_sha256"]
        and rt.v8.digest(cohort.registered_episode_keys) == manifest["ordered_episode_keys_sha256"],
        "cohort/reward/order manifest binding changed",
    )
    return cohort, rewards


class ReadOnlySamePointCollector:
    """Explicit read-only adapter, not a drop-in authorization for V25 training.

    A future production adapter must explicitly adopt this guard: frozen
    ``outer_update`` deliberately rejects replacement collector types. The V32
    performance harness instead calls these read-only methods directly.
    """

    def __init__(self, original_collector, manifest, *, pre_state, G, frozen_runtime=None):
        self.rt = _runtime(frozen_runtime)
        require(
            type(original_collector) is self.rt.v8.LocalFeedbackCollector,
            "the exact frozen original collector configuration is required",
        )
        self.original, self.manifest = original_collector, copy.deepcopy(manifest)
        self.pre_state, self.G = pre_state, G
        _checked_manifest(self.manifest)
        require(
            self.rt.v8._tree_digest(pre_state) == manifest["pre_state_digest"],
            "complete restored pre-outer state changed",
        )
        check_recomputed_point(
            manifest,
            manifest["point_id"],
            Path(original_collector.root) / _digest(manifest["point_id"]),
        )

    def collect(self, model, tokenizer, theta, *, point_id, event_sink=None):
        rt, original, manifest = self.rt, self.original, self.manifest
        # Rehash live state before any install/event callback or feedback read.
        require(
            rt.v8._tree_digest(self.pre_state) == manifest["pre_state_digest"],
            "pre-outer state mutated after admission",
        )
        actual = recompute_point_id(self.pre_state, theta_bar=theta, G=self.G, frozen_runtime=rt)
        require(point_id == actual, "caller point_id differs from actual recomputed point")
        check_recomputed_point(manifest, actual, Path(original.root) / _digest(actual))
        with rt.v8.installed_point(model, theta) as installed:
            identity = rt.v8.local_model_identity(
                model,
                tokenizer,
                model_id=original.model_id,
                point_id=actual,
                parameter_tensors=installed,
            )
            intent = dict(
                point_id=actual,
                identity=identity.model_dump(mode="json"),
                source_manifest_sha256=rt.v8.digest(original.manifest),
                role_plan_id=original.role_plan["id"],
                seeds=original.seeds,
                task_ids=[t.task_id for t in original.tasks],
                denominator=700,
            )
            require(
                json.loads(rt.v8._json(intent)) == manifest["intent"], "feedback intent changed"
            )
            cohort, rewards = read_sealed_feedback(manifest, frozen_runtime=rt)
        if event_sink is not None:
            event_sink(
                dict(
                    phase="read_only_same_point_feedback_verified",
                    point_id=actual,
                    cohort_seal_sha256=cohort.seal_sha256,
                    denominator=700,
                    provider_calls=0,
                    scoring_calls=0,
                    source_writes=0,
                )
            )
        return cohort, rewards
