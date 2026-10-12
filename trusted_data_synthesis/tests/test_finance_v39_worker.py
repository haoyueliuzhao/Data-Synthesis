"""Only orchestration deltas are exercised; scientific kernels stay the V37 ones."""

import ast
import importlib
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
sys.path.insert(0, str(Path(__file__).parent))
worker = importlib.import_module("finqa_v39_worker")
fixtures = importlib.import_module("test_finance_v38_worker")


@pytest.fixture
def episode(tmp_path, monkeypatch):
    # The existing CPU fake supplies genuine original training commit logic and
    # checks point locks, payload routing, the lifetime peak and parent immutability.
    monkeypatch.setattr(fixtures, "worker", worker)
    value = fixtures.episode.__wrapped__(tmp_path, monkeypatch)
    value.plan.update(
        allowed_gpu_indices=list(worker.admission.ALLOWED_GPUS),
        gpu_uuids=dict(worker.admission.GPU_UUIDS),
    )
    monkeypatch.setattr(worker, "__file__", str(value.root / "implementation/finqa_v39_worker.py"))
    return value


def test_pending_distribution_keeps_point_and_changes_only_output_protocol(episode):
    fixtures.test_parent_reads_new_protocol_outputs_and_original_state_resource_checks(episode)


def test_pending_train_uses_saved_distribution_and_original_commit_semantics(episode):
    fixtures.test_inherited_training_reads_new_distribution_and_commits_one_outer_and_one_step(
        episode
    )


@pytest.mark.parametrize("stage", ["shard00", "shard03", "virtual_point", "replay_R3"])
def test_old_complete_stage_is_never_dispatched_again(episode, stage):
    fixtures.test_inherited_completed_stages_cannot_be_redispatched(episode, stage)


def test_even_unbound_inherited_shard_is_forbidden(episode, monkeypatch):
    monkeypatch.setattr(
        worker.inheritance, "stage_directory", lambda directory, _plan, stage: directory / stage
    )
    with pytest.raises(ValueError, match="completed parent stages"):
        episode.run("shard02")
    assert not episode.calls and not episode.cuda.initialized


def test_inherited_later_outer_does_not_reapply_the_v38_pilot_boundary(episode):
    episode.context["training_stop_step"] = 1490
    result = episode.run("distribution")
    assert result["status"] == "COMPLETE"
    assert result["context_id"] == episode.context["id"]


def test_invalid_parent_exit_stops_before_model_or_admission(episode):
    fixtures.test_invalid_upstream_stops_before_admission_or_cuda(episode)


def test_native_new_context_reads_its_own_stage_outputs(episode):
    fixtures.test_future_context_uses_its_own_payloads_without_parent_alias(episode)


def test_failed_final_resources_do_not_create_complete_result(episode):
    fixtures.test_final_resource_gate_is_not_relaxed(episode)


def test_unsealed_worker_is_rejected_before_source_loading(episode, monkeypatch):
    fixtures.test_worker_rejects_unsealed_entry_file_before_loading_sources(episode, monkeypatch)


@pytest.mark.parametrize("index", [0, 1, 2, 8])
def test_unauthorized_gpu_is_rejected_before_any_work(episode, index):
    with pytest.raises(ValueError, match="unregistered"):
        worker.run(
            episode.root, episode.directory, "distribution", index, fixtures.time.time() + 10
        )
    assert not episode.calls and not episode.cuda.initialized


def test_new_shell_keeps_one_preload_peak_reset_and_original_mathematical_calls():
    source = Path(__file__).parents[1] / "scripts/finqa_v39_worker.py"
    attrs = [
        node.func.attr
        for node in ast.walk(ast.parse(source.read_text()))
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    ]
    assert attrs.count("reset_peak_memory_stats") == 1
    for phase in ("execute_shard", "execute_virtual", "execute_replay", "execute_distribution"):
        assert attrs.count(phase) == 1
    assert not {"outer_update", "run_until", "load_saved_gradient"}.intersection(attrs)
