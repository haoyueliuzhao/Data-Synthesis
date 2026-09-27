"""Immutable snapshots, durable invocation records, and generation-before-score barrier."""

from __future__ import annotations

import fcntl
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

from trusted_synthesis.core.immutable_artifacts import write_immutable_artifact_directory

from .contracts import Episode, Lineage, PrivateReference, PublicTask, RunConfig, TaskBundle, digest
from .planning import task_key, verify_role_plan


def encode(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False).encode()


def read_json(path):
    return json.loads(Path(path).read_bytes())


def _lines(records):
    return b"".join(
        json.dumps(
            record.model_dump(mode="json"), ensure_ascii=False, sort_keys=True, allow_nan=False
        ).encode()
        + b"\n"
        for record in records
    )


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def import_snapshot(bundles: list[TaskBundle], output: Path, *, source: dict) -> dict:
    if not bundles or len({task_key(row.public) for row in bundles}) != len(bundles):
        raise ValueError("snapshot requires nonempty unique original task identities")
    payloads = {
        "public.jsonl": _lines([row.public for row in bundles]),
        "lineage.jsonl": _lines([row.lineage for row in bundles]),
        "private.references.jsonl": _lines([row.reference for row in bundles]),
    }
    manifest = dict(
        schema="finance_research_dataset_snapshot.v1",
        source=source,
        counts=dict(Counter(row.public.dataset for row in bundles)),
        task_order=[task_key(row.public) for row in bundles],
        files={name: dict(sha256=_sha(raw), bytes=len(raw)) for name, raw in payloads.items()},
        public_projection_allowlisted=True,
        original_QA_not_regenerated=True,
        private_reference_not_an_observation=True,
    )
    manifest["id"] = digest(manifest)
    payloads["manifest.json"] = encode(manifest)
    write_immutable_artifact_directory(output, payloads)
    return manifest


def snapshot_manifest(path):
    path = Path(path)
    value = read_json(path / "manifest.json")
    if value.get("id") != digest({key: row for key, row in value.items() if key != "id"}):
        raise ValueError("snapshot manifest identity mismatch")
    return value


def _read_snapshot_rows(path, name, cls, manifest):
    raw = (Path(path) / name).read_bytes()
    if manifest["files"][name] != dict(sha256=_sha(raw), bytes=len(raw)):
        raise ValueError(f"snapshot member changed: {name}")
    return [cls.model_validate_json(line) for line in raw.splitlines() if line.strip()]


def load_public_snapshot(path):
    """Generation and role planning deliberately never open private.references.jsonl."""
    manifest = snapshot_manifest(path)
    tasks = _read_snapshot_rows(path, "public.jsonl", PublicTask, manifest)
    lineages = _read_snapshot_rows(path, "lineage.jsonl", Lineage, manifest)
    if [task_key(task) for task in tasks] != manifest["task_order"]:
        raise ValueError("public task order does not match snapshot")
    return manifest, tasks, lineages


def runtime_binding():
    root = Path(__file__).parent
    binding = {
        str(path.relative_to(root)): _sha(path.read_bytes()) for path in sorted(root.rglob("*.py"))
    }
    retained = (
        "core/immutable_artifacts.py",
        "experiments/finance_qa_vnext_anchored_vtdo/optimizer_pullback.py",
        "experiments/finance_qa_vnext_anchored_vtdo/distribution.py",
        "experiments/finance_qa_vnext_anchored_vtdo/protocol.py",
        "experiments/finance_qa_vnext_fixed_kernel_value/trajectory_consumer.py",
        "experiments/finance_qa_vnext_pq_student/model.py",
        "experiments/finance_qa_vnext_pq_student/plan.py",
    )
    for relative in retained:
        binding["retained/" + relative] = _sha((root.parent / relative).read_bytes())
    for name in (
        "fixed_kernel_anchored_segmented_replay_20260916.py",
        "fixed_kernel_anchored_sources_gpu_gate_20260916.py",
    ):
        path = root.parents[2] / "scripts" / name
        # The CUDA replay backend needs a source checkout; ordinary wheel-installed
        # dataset/eval paths do not silently pretend that backend is available.
        binding["retained/scripts/" + name] = _sha(path.read_bytes()) if path.is_file() else None
    return binding


def episode_key(task, config, identity):
    return digest(
        dict(
            dataset=task.dataset, task_id=task.task_id, seed=config.seed, point_id=identity.point_id
        )
    )


def prepare_run(snapshot, role_plan, output, *, role, config, identity, limit=None):
    snapshot, output = Path(snapshot).resolve(), Path(output).resolve()
    manifest, tasks, lineages = load_public_snapshot(snapshot)
    verify_role_plan(role_plan, tasks, lineages)
    if config.role != role:
        raise ValueError("run config role must match selected dataset role")
    if config.tier == "VTDO_FEEDBACK" and role != "feedback":
        raise ValueError("only the original feedback role can enter VTDO")
    chosen = [task for task in tasks if role_plan["assignments"][task_key(task)] == role]
    if limit is not None:
        if type(limit) is not int or limit <= 0:
            raise ValueError("limit must be positive and fixed before the first model call")
        chosen = chosen[:limit]
    if not chosen:
        raise ValueError("no tasks in requested role")
    value = dict(
        schema="finance_research_run.v1",
        snapshot=str(snapshot),
        snapshot_id=manifest["id"],
        role_plan=role_plan,
        role_plan_id=role_plan["id"],
        role=role,
        config=config.model_dump(mode="json"),
        provider=identity.model_dump(mode="json"),
        tasks=[task_key(task) for task in chosen],
        episode_keys=[episode_key(task, config, identity) for task in chosen],
        registered_denominator=len(chosen),
        source_manifest_sha256=digest(manifest),
        runtime_binding=runtime_binding(),
        total_provider_attempt_cap=len(chosen) * config.max_steps,
        no_hidden_retries=True,
        all_generation_before_reference_scoring=True,
    )
    value["id"] = digest(value)
    write_immutable_artifact_directory(output, {"run.json": encode(value)})
    return value


def _run_manifest(root):
    value = read_json(Path(root) / "run.json")
    if value.get("id") != digest({key: item for key, item in value.items() if key != "id"}):
        raise ValueError("run registration identity mismatch")
    if value["runtime_binding"] != runtime_binding():
        raise ValueError("registered runtime bytes changed; create a new explicit run")
    return value


class EventSink:
    def __init__(self, directory):
        self.directory = Path(directory)
        self.counter = 0
        if self.directory.exists():
            raise ValueError("unsettled episode exists; do not silently repeat model calls")

    def __call__(self, event):
        write_immutable_artifact_directory(
            self.directory / f"{self.counter:06d}", {"event.json": encode(event)}
        )
        self.counter += 1


async def execute_run(root, provider):
    from .harness import run_episode

    root = Path(root).resolve()
    with (root / "generation.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        run = _run_manifest(root)
        config = RunConfig.model_validate(run["config"])
        if provider.identity.model_dump(mode="json") != run["provider"]:
            raise ValueError("provider differs from registered model/parameter identity")
        manifest, tasks, lineages = load_public_snapshot(run["snapshot"])
        if manifest["id"] != run["snapshot_id"]:
            raise ValueError("source dataset changed after registration")
        verify_role_plan(run["role_plan"], tasks, lineages)
        by_key = {task_key(task): task for task in tasks}
        references = []
        for key, episode_id in zip(run["tasks"], run["episode_keys"], strict=True):
            task = by_key[key]
            path = root / "episodes" / episode_id / "episode.json"
            if path.exists():
                episode = Episode.model_validate_json(path.read_bytes())
            else:
                sink = EventSink(root / "events" / episode_id)
                episode = await run_episode(task, provider, config, sink=sink)
                write_immutable_artifact_directory(
                    path.parent, {"episode.json": encode(episode.model_dump(mode="json"))}
                )
            if (
                episode.public_task_sha256 != digest(task)
                or episode.config != config
                or episode.provider != provider.identity
                or episode.task_id != task.task_id
                or episode.dataset != task.dataset
            ):
                raise ValueError("completed episode does not belong to this registered task")
            recorded = sorted((root / "events" / episode_id).glob("*/event.json"))
            if not recorded:
                raise ValueError("completed episode has no durable completion event")
            completion = read_json(recorded[-1])
            if completion.get("kind") != "episode_completed" or completion.get(
                "payload"
            ) != episode.model_dump(mode="json"):
                raise ValueError("completed episode differs from durable completion event")
            references.append(
                dict(
                    key=episode_id, path=str(path.relative_to(root)), sha256=_sha(path.read_bytes())
                )
            )
        seal = dict(
            schema="finance_research_generation_seal.v1",
            run_id=run["id"],
            episodes=references,
            complete=True,
            registered_denominator=run["registered_denominator"],
            all_provider_calls_settled=True,
            private_references_read=False,
        )
        seal["id"] = digest(seal)
        seal_dir = root / "generation_seal"
        if seal_dir.exists():
            if read_json(seal_dir / "seal.json") != seal:
                raise ValueError("sealed generation differs from current complete cohort")
        else:
            write_immutable_artifact_directory(seal_dir, {"seal.json": encode(seal)})
        return seal


def sealed_episodes(root):
    root = Path(root).resolve()
    run = _run_manifest(root)
    seal = read_json(root / "generation_seal" / "seal.json")
    if (
        seal.get("id") != digest({k: v for k, v in seal.items() if k != "id"})
        or seal["run_id"] != run["id"]
        or seal["complete"] is not True
        or seal["registered_denominator"] != run["registered_denominator"]
        or [row["key"] for row in seal["episodes"]] != run["episode_keys"]
    ):
        raise ValueError("all registered generation must be sealed before scoring")
    episodes = []
    for row in seal["episodes"]:
        path = (root / row["path"]).resolve()
        if not path.is_relative_to(root / "episodes"):
            raise ValueError("episode path outside registered run")
        raw = path.read_bytes()
        if _sha(raw) != row["sha256"]:
            raise ValueError("sealed episode bytes changed")
        episodes.append(Episode.model_validate_json(raw))
    return run, seal, episodes


def score_run(root, output):
    """The only runtime path that opens private references: after full cohort sealing."""
    from .native_metrics import score_native

    run, seal, episodes = sealed_episodes(root)
    manifest, tasks, lineages = load_public_snapshot(run["snapshot"])
    if manifest["id"] != run["snapshot_id"]:
        raise ValueError("dataset identity changed before scoring")
    references = _read_snapshot_rows(
        run["snapshot"], "private.references.jsonl", PrivateReference, manifest
    )
    if len(tasks) != len(references) or len(tasks) != len(lineages):
        raise ValueError("private/reference cohort size mismatch")
    bundles = {
        task_key(task): TaskBundle(public=task, reference=reference, lineage=lineage)
        for task, reference, lineage in zip(tasks, references, lineages, strict=True)
    }
    results, datasets = [], defaultdict(list)
    for key, episode in zip(run["tasks"], episodes, strict=True):
        bundle = bundles[key]
        native = score_native(
            bundle, episode.final_answer, scale=episode.final_scale, program=episode.final_program
        )
        trajectory = dict(
            stop_reason=episode.stop_reason,
            explicit_final=episode.stop_reason == "final_answer",
            tool_calls=len(episode.tool_events),
            tool_errors=sum(x.is_error for x in episode.tool_events),
            actual_model_calls=episode.actual_model_calls,
            provider_attempts=episode.provider_attempts,
            complete_semantic_support="unknown",
            native_answer_correctness_is_not_CompletePass=True,
        )
        row = dict(task_key=key, native=native, trajectory=trajectory)
        results.append(row)
        datasets[bundle.public.dataset].append(row)
    report = dict(
        schema="finance_research_separate_metrics.v1",
        run_id=run["id"],
        generation_seal_id=seal["id"],
        denominator=run["registered_denominator"],
        datasets={
            name: dict(
                tasks=len(rows), explicit_final=sum(x["trajectory"]["explicit_final"] for x in rows)
            )
            for name, rows in datasets.items()
        },
        results=results,
        no_pooled_cross_dataset_finance_score=True,
        real_model_execution=run["provider"]["backend"] != "scripted",
        fixture_only=run["provider"]["backend"] == "scripted",
        new_API_calls_for_scoring=0,
        training_value_claimed=False,
    )
    for name, rows in datasets.items():
        summary = report["datasets"][name]
        summary["native_status_counts"] = dict(Counter(row["native"]["status"] for row in rows))
        summary["native_metrics"] = {}
        names = {key for row in rows for key in row["native"]["native"]}
        for metric in sorted(names):
            values = [row["native"]["native"].get(metric) for row in rows]
            supported = [value for value in values if type(value) in (int, float)]
            summary["native_metrics"][metric] = dict(
                denominator=len(rows),
                scored=len(supported),
                unsupported=len(rows) - len(supported),
                mean_over_scored=sum(supported) / len(supported) if supported else None,
                complete_dataset_mean=sum(supported) / len(rows)
                if len(supported) == len(rows)
                else None,
            )
    report["id"] = digest(report)
    write_immutable_artifact_directory(output, {"report.json": encode(report)})
    return report
