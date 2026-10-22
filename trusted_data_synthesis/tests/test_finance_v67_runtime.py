"""Cold CPU checks of the unchanged resource math and two global GPU lanes."""
from __future__ import annotations

import fcntl
import json
from pathlib import Path

import pytest

import finqa_v67_binding as binding
import finqa_v67_runtime as runtime


def test_private_nested_guards_publish_only_to_new_control_root():
    old = binding.early_module('finqa_v65_runtime')
    science = binding.source_module('finqa_v63_runtime')
    assert old._reference.ROOT == binding.SOURCE_GENERATION_ROOT
    assert science.ROOT == science._base.ROOT == binding.SCIENTIFIC_ROOT
    assert runtime._reference.ROOT == runtime._reference._base.ROOT == binding.ROOT
    assert runtime._reference._durable.ROOT == runtime._protection.ROOT == binding.ROOT
    assert runtime._reference._base.publish is runtime._reference._durable.publish is binding.publish
    assert runtime._protection.binding is binding
    assert runtime._runtime.ResourceGuard is runtime.ResourceGuard


def test_only_authorized_global_and_per_gpu_caps_change_resource_policy():
    old = binding.early_module('finqa_v65_runtime')
    before, after = old.resource_policy(), runtime.resource_policy()
    assert before['max_gpu_workers'] == 5 and after['max_gpu_workers'] == 3
    assert before['max_workers_per_gpu'] == 1 and after['max_workers_per_gpu'] == 2
    omitted = {'max_gpu_workers', 'max_workers_per_gpu'}
    assert {k: v for k, v in before.items() if k not in omitted} == {
        k: v for k, v in after.items() if k not in omitted}
    assert after['minimum_free_gib_by_kind']['generate'] == 24
    assert after['host_startup_gib_by_kind']['generate'] == 48
    assert after['allocated_lifetime_limit_bytes'] == 76 * runtime.GIB
    assert after['boundary_physical_free_reserve_bytes'] == 2 * runtime.GIB
    assert after['effective_host_available_reserve_bytes'] == 96 * runtime.GIB
    assert runtime.memory_protection_policy() == old.memory_protection_policy()
    assert runtime.resource_recovery_policy() == old.resource_recovery_policy()


def test_frozen_descriptor_path_inode_and_exclusive_flock_code_unchanged():
    old = binding.early_module('finqa_v65_runtime')
    new_enter = runtime._reference._base.ResourceGuard.__enter__
    old_enter = old._reference._base.ResourceGuard.__enter__
    assert new_enter.__code__.co_code == old_enter.__code__.co_code
    assert new_enter.__code__.co_consts == old_enter.__code__.co_consts
    assert new_enter.__code__.co_names == old_enter.__code__.co_names


@pytest.mark.parametrize('root,stage', [('science', 'generate'), ('new', 'train_C1'),
                                         ('old', 'generate'), ('new', 'replay_C05')])
def test_other_root_or_science_rejected_before_resource_and_cuda(root, stage):
    target = {'science': binding.SCIENTIFIC_ROOT, 'old': binding.SOURCE_GENERATION_ROOT,
              'new': binding.ROOT}[root]
    with pytest.raises(ValueError, match='generation-only'):
        runtime.ResourceGuard(target, {'stage': stage, 'kind': stage.split('_')[0]}, 0)


def test_secondary_lane_admits_one_and_legacy_exit_cannot_admit_third(tmp_path, monkeypatch):
    monkeypatch.setattr(binding, 'base_protocol', lambda: {'gpu_lease_root': str(tmp_path / 'leases')})
    policy = binding.gpu_slot_policy()
    assert policy['max_total_project_workers_per_gpu'] == 2
    assert policy['max_legacy_workers_per_gpu'] == policy['own_max_workers_per_gpu'] == 1
    original = Path(policy['legacy_gpu_lease_root'])
    secondary = Path(policy['second_slot_lease_root'])
    assert secondary == original / 'v67-secondary-slot'
    secondary.mkdir(parents=True)
    name = 'gpu-' + binding.digest('GPU-fixture') + '.lock'
    with (original / name).open('a') as legacy, (secondary / name).open('a') as first_new:
        fcntl.flock(legacy, fcntl.LOCK_EX | fcntl.LOCK_NB)
        fcntl.flock(first_new, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with (secondary / name).open('a') as second_new:
            with pytest.raises(BlockingIOError):
                fcntl.flock(second_new, fcntl.LOCK_EX | fcntl.LOCK_NB)
        fcntl.flock(legacy, fcntl.LOCK_UN)
        with (original / name).open('a') as next_legacy:
            fcntl.flock(next_legacy, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with (secondary / name).open('a') as third:
                with pytest.raises(BlockingIOError):
                    fcntl.flock(third, fcntl.LOCK_EX | fcntl.LOCK_NB)


@pytest.mark.parametrize('change', ['none', 'legacy', 'owncap', 'totalcap', 'policy'])
def test_guard_requires_registered_second_lane_before_parent_constructor(tmp_path, monkeypatch, change):
    monkeypatch.setattr(binding, 'ROOT', tmp_path / 'control')
    monkeypatch.setattr(binding, 'base_protocol', lambda: {'gpu_lease_root': str(tmp_path / 'leases')})
    slots = binding.gpu_slot_policy()
    value = dict(gpu_slot_policy=slots, max_workers_per_gpu=2, own_max_workers_per_gpu=1,
        gpu_lease_root=slots['second_slot_lease_root'], legacy_gpu_lease_root=slots['legacy_gpu_lease_root'])
    if change == 'legacy':
        value['gpu_lease_root'] = value['legacy_gpu_lease_root']
    elif change == 'owncap':
        value['own_max_workers_per_gpu'] = 2
    elif change == 'totalcap':
        value['max_workers_per_gpu'] = 3
    elif change == 'policy':
        value['gpu_slot_policy'] = {**slots, 'max_legacy_workers_per_gpu': 2}
    target = binding.ROOT / 'protocol/record.json'
    target.parent.mkdir(parents=True)
    target.write_text(json.dumps({**value, 'id': binding.digest(value)}))
    calls = []
    monkeypatch.setattr(runtime._GenerationGuard, '__init__', lambda *args, **kwargs: calls.append(args))
    if change == 'none':
        runtime.ResourceGuard(binding.ROOT, {'kind': 'generate', 'stage': 'generate'}, 0)
        assert len(calls) == 1
    else:
        with pytest.raises(ValueError, match='sole secondary lane'):
            runtime.ResourceGuard(binding.ROOT, {'kind': 'generate', 'stage': 'generate'}, 0)
        assert not calls
