"""CPU-only checks for new-root resource contracts and disjoint slot scope."""
from __future__ import annotations

import pytest

import finqa_v65_binding as binding
import finqa_v65_runtime as runtime
import finqa_v65_registration as registration


def test_private_resource_root_does_not_mutate_original_frozen_root():
    original = binding.source_module('finqa_v63_runtime')
    assert original.ROOT == binding.SCIENTIFIC_ROOT
    assert original._base.ROOT == binding.SCIENTIFIC_ROOT
    assert runtime._reference.ROOT == binding.ROOT
    assert runtime._reference._base.ROOT == binding.ROOT
    assert runtime._reference._base.publish is binding.publish


def test_generation_partition_changes_no_lifetime_resource_gate():
    old = binding.source_module('finqa_v63_runtime').resource_policy()
    new = runtime.resource_policy()
    assert old['max_gpu_workers'] == 6
    assert new['max_gpu_workers'] == 5
    assert {k: v for k, v in old.items() if k != 'max_gpu_workers'} == {
        k: v for k, v in new.items() if k != 'max_gpu_workers'}
    assert runtime.memory_protection_policy() == binding.predecessor_module('finqa_v64_runtime').memory_protection_policy()


@pytest.mark.parametrize('stage', ['feedback_C1', 'replay_C05', 'distribution_C05', 'train_C1'])
def test_guard_rejects_scientific_core_before_any_resource_or_cuda_call(stage):
    with pytest.raises(ValueError, match='generation-only'):
        runtime.ResourceGuard(binding.ROOT, {'stage': stage, 'kind': stage.split('_')[0]}, 0)


def test_guard_rejects_original_science_root_before_cuda():
    with pytest.raises(ValueError, match='generation-only'):
        runtime.ResourceGuard(binding.SCIENTIFIC_ROOT, {'stage': 'generate', 'kind': 'generate'}, 0)


def test_registration_files_and_five_endpoint_roster_are_exact():
    assert len(registration.FILES) == len(set(registration.FILES)) == 7
    assert len(binding.ELIGIBLE_COORDINATES) == 5
    assert (389, 'C05') not in binding.ELIGIBLE_COORDINATES
    assert binding.MAX_WORKERS + 1 == 6
    assert binding.ROOT != binding.PEER_ROOT != binding.SCIENTIFIC_ROOT


def test_shared_scope_preserves_exact_five_plus_one_and_conservative_RAM():
    scopes = registration.parallel_scopes()
    assert set(scopes) == {str(binding.ROOT), str(binding.PEER_ROOT)}
    assert sum(v['max_gpu_workers'] for v in scopes.values()) == 6
    assert scopes[str(binding.ROOT)]['reserved_other_control_startup_gib'] == 64
    assert scopes[str(binding.PEER_ROOT)]['reserved_other_control_startup_gib'] == 240
    assert scopes[str(binding.PEER_ROOT)]['additional_response_replay'] == 0
