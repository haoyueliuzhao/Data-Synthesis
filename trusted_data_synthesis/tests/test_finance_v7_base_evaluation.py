"""CPU-only miniature lifecycle of the full-denominator original-Base controller."""

import asyncio
import json

import pytest

from trusted_synthesis.finance_research import storage
from trusted_synthesis.finance_research import v7_base_evaluation as base
from trusted_synthesis.finance_research.datasets import adapt_finqa
from trusted_synthesis.finance_research.planning import build_role_plan, task_key
from trusted_synthesis.finance_research.providers import ScriptedProvider


@pytest.fixture
def cohort(tmp_path):
    records = [
        {
            "id": f"BASE_FIXTURE_{index}/2020/page_1.pdf-1",
            "filename": f"BASE_FIXTURE_{index}/2020/page_1.pdf",
            "pre_text": ["All figures are USD."],
            "post_text": [],
            "table": [["Year", "Revenue"], ["2020", "8"], ["2019", "2"]],
            "qa": {
                "question": "What is the revenue increase?",
                "exe_ans": 6,
                "program": "subtract(8, 2)",
                "gold_inds": {"table_1": "PRIVATE ONLY"},
            },
        }
        for index in range(2)
    ]
    bundles = adapt_finqa(records, split="dev", revision="synthetic-base-v1")
    snapshot, output = tmp_path / "snapshot", tmp_path / "baseline"
    manifest = storage.import_snapshot(bundles, snapshot, source={"synthetic": True})
    role_plan = build_role_plan([b.public for b in bundles], [b.lineage for b in bundles])
    keys = [task_key(b.public) for b in bundles]
    shards = [dict(key=f"dev{i:02d}", task_keys=[key]) for i, key in enumerate(keys)]
    providers = [
        ScriptedProvider(['{"name":"submit_program","arguments":{"program":"subtract(8, 2)"}}'])
        for _ in keys
    ]
    config = base.evaluation_config()
    plan = base.bound(
        dict(
            runtime_binding=storage.runtime_binding(),
            snapshot=str(snapshot),
            snapshot_id=manifest["id"],
            tasks=keys,
            shards=shards,
            denominator=2,
            config=config.model_dump(mode="json"),
            model_identity=providers[0].identity.model_dump(mode="json"),
            role_plan=role_plan,
            process_attempts_per_shard=3,
        )
    )
    base.persist(output, plan, "protocol.json")
    for shard in shards:
        storage.prepare_run(
            snapshot,
            role_plan,
            base.shard_root(output, shard),
            role="development",
            config=config,
            identity=providers[0].identity,
            task_keys=shard["task_keys"],
        )
    return output, plan, providers


def test_exact_configuration_and_full_fixed_shards():
    config = base.evaluation_config()
    assert config.harness_id == "bigfinance-derived-vtdo-v7"
    assert config.submission_profile == "finqa-public-reasoning-v2"
    assert (config.temperature, config.top_p, config.top_k) == (0, 1, 0)
    assert (config.max_steps, config.max_new_tokens, config.context_limit) == (32, 2048, 24576)
    assert config.seed == 20260928 and config.role == "development"
    keys = [f"finqa/task{i}" for i in range(883)]
    shards = base.fixed_shards(keys)
    assert [len(s["task_keys"]) for s in shards] == [442, 441]
    assert sum((s["task_keys"] for s in shards), []) == keys
    with pytest.raises(ValueError, match="dev883"):
        base.fixed_shards(keys[:-1])


def test_shared_gpu_only_free_memory_and_registered_indices():
    rows = [
        dict(index=0, uuid="gpu0", free=25000, processes=[123], utilization=100),
        dict(index=7, uuid="gpu7", free=30000, processes=[456], utilization=100),
        dict(index=1, uuid="gpu1", free=80000),
    ]
    assert [r["uuid"] for r in base.eligible_gpus(rows)] == ["gpu7", "gpu0"]
    assert [r["uuid"] for r in base.eligible_gpus(rows, ["gpu7"])] == ["gpu0"]
    assert not base.eligible_gpus([dict(index=0, uuid="gpu0", free=24575)])


def test_no_private_reads_before_both_shards_seal(cohort, monkeypatch):
    output, plan, providers = cohort
    first = base.shard_root(output, plan["shards"][0])
    asyncio.run(storage.execute_run(first, providers[0]))

    def private_read_forbidden(*args, **kwargs):
        raise AssertionError("private reference read before full original cohort seal")

    monkeypatch.setattr(base, "_read_snapshot_rows", private_read_forbidden)
    with pytest.raises(ValueError, match="all registered shards"):
        base.score_all(output, plan)
    assert not (output / "scores").exists()
    assert not (output / "generation_seal").exists()


def test_full_seal_program_only_native_score_and_readonly_resume(cohort):
    output, plan, providers = cohort
    for shard, provider in zip(plan["shards"], providers, strict=True):
        root = base.shard_root(output, shard)
        seal = asyncio.run(storage.execute_run(root, provider))
        assert base.inspect_shard(output, plan, shard) == {
            "completed": 1,
            "denominator": 1,
            "sealed": True,
        }
        # The scripted response iterator is now exhausted: any resampling fails.
        assert asyncio.run(storage.execute_run(root, provider)) == seal
        assert provider._calls == 1
        _, _, episodes = storage.sealed_episodes(root)
        assert episodes[0].final_answer is None
        assert episodes[0].final_program == "subtract(8, 2)"
    report = base.score_all(output, plan)
    assert report["denominator"] == 2
    for metric in report["metrics"].values():
        assert metric["scored"] == 2 and metric["unknown"] == 0
        assert metric["complete_dataset_mean"] == 1
    assert report["trajectory_CompletePass_claimed"] is False
    assert base.score_all(output, plan) == report


def test_interrupted_intent_blocks_without_retry(cohort):
    output, plan, providers = cohort
    shard = plan["shards"][0]
    root = base.shard_root(output, shard)
    run = storage.read_json(root / "run.json")
    sink = storage.EventSink(root / "events" / run["episode_keys"][0])
    sink(dict(kind="model_call_intent", payload={"fixture": "interrupted"}))
    with pytest.raises(storage.UnsettledExecution, match="durable episode intent"):
        base.inspect_shard(output, plan, shard)
    with pytest.raises(ValueError, match="unsettled episode"):
        asyncio.run(storage.execute_run(root, providers[0]))
    assert providers[0]._calls == 0


def test_completed_episode_tampering_is_not_admitted(cohort):
    output, plan, providers = cohort
    shard = plan["shards"][0]
    root = base.shard_root(output, shard)
    asyncio.run(storage.execute_run(root, providers[0]))
    path = next((root / "episodes").glob("*/episode.json"))
    episode = json.loads(path.read_bytes())
    episode["final_program"] = "add(8, 2)"
    path.write_text(json.dumps(episode))
    with pytest.raises(ValueError, match="durable completion"):
        base.inspect_shard(output, plan, shard)
    assert providers[0]._calls == 1


def test_unknown_pid_identity_never_counts_as_alive(tmp_path, monkeypatch):
    base.persist(
        tmp_path / "shards/dev00/attempts/01/launched",
        dict(pid=99999999, process_identity=None, gpu="gpu0"),
    )
    monkeypatch.setattr(base, "process_identity", lambda pid: None)
    assert base.latest_worker(tmp_path, "dev00")["alive"] is False
