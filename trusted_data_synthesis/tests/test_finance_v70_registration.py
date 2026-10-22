"""Small V70 prospective-scope checks; no real artifact or scientific writes."""
from __future__ import annotations

from pathlib import Path

import pytest

import finqa_v70_binding as binding
import finqa_v70_registration as registration


def test_one_fixed_initialization_two_applications_and_terminal_probe_only():
    value = registration.scientific_contract()
    assert value['initialization'] == dict(seed=137, source='V63/C1/b1', step=894,
        phase='step', source_algorithm='C-only', restore=['theta', 'Adam', 'training_RNG', 'pi'],
        real_parent_not_virtual=True, new_initialization_seed=False)
    assert value['actual_parameter_points'] == [894, 1192, 1490]
    assert value['applied_outer_steps'] == [894, 1192]
    assert value['terminal_probe_applied'] is False
    assert value['algorithm'] == 'Full' and value['novelty_exponent'] == .2
    assert value['initialization']['step'] == value['C_only_to_Full_transition_step']
    assert value['automatic_old_driver_outer_disabled']
    assert value['exactly_once_explicit_outer_commit']
    assert value['old_outer_history_not_fabricated']


def test_exact_new_dose_no_width_or_history_expansion():
    value = registration.scientific_contract()
    assert sum(end - start + 1 for start, end in value['train_windows']) == 596
    assert value['new_feedback_sessions'] == len(value['actual_parameter_points']) * 700 == 2100
    assert value['new_optimizer_updates'] == 596
    assert value['new_training_task_exposures'] == 2976
    assert value['new_complete_class_passes'] == 3
    assert value['new_complete_class_tasks'] == 2232
    assert value['new_effective_class_rows'] == 14922
    assert value['new_evaluation_sessions'] == 2 * 120 + 883 == 1123
    assert value['new_total_logical_sessions'] == 3223
    assert value['new_training_paths'] == value['independent_parent_count'] == 1
    assert value['new_training_seeds'] == value['new_random_evaluation'] == value['new_test_evaluation'] == 0
    assert value['new_step1192_dev'] == 0
    assert value['historical596_gradients_G_theta_bar_or_C_reused'] is False
    assert value['automatic_followup_authorized'] is False


def test_original_mean_check_is_not_excepted_and_formal_q_is_not_draw_average():
    value = registration.scientific_contract()
    assert value['draw_mean_tolerances'] == dict(atol=1e-7, rtol=2e-4,
        source='V54_CPU_full_autograd_gradient_comparison')
    assert value['legacy_single_point_exception_inherited'] is False
    assert value['legacy_unknown_request_reexecution_permission_inherited'] is False
    assert value['formal_q_uses_complete_700_feedback_only'] is True
    assert value['mean_of_normalized_draw_q_forbidden'] is True
    assert value['no_performance_based_early_stop_or_checkpoint_selection'] is True
    assert value['new_cluster_bootstrap'] is False


def test_publication_is_independent_and_immutable(tmp_path, monkeypatch):
    root = tmp_path / 'v70_full_closed_loop_01'
    monkeypatch.setattr(binding, 'ROOT', root)
    path = root / 'test/record.json'
    value = binding.publish(path, dict(schema='CPU-test', feedback_calls=0))
    assert binding.checked(path) == value
    assert binding.publish(path, dict(schema='CPU-test', feedback_calls=0)) == value
    with pytest.raises(ValueError, match='existing immutable'):
        binding.publish(path, dict(schema='CPU-test', feedback_calls=700))
    with pytest.raises(ValueError, match='must not overwrite'):
        binding.publish(tmp_path / 'historical/record.json', dict(schema='CPU-test'))
    assert not (tmp_path / 'historical').exists()


def test_reference_content_is_bound_not_just_path(tmp_path, monkeypatch):
    monkeypatch.setattr(binding, 'ROOT', tmp_path)
    path = tmp_path / 'test/record.json'
    binding.publish(path, dict(schema='CPU-test'))
    reference = binding.entry(path)
    assert binding.read_ref(reference)['id'] == reference['id']
    with pytest.raises(ValueError, match='bytes changed'):
        binding.read_ref(dict(reference, sha256='0' * 64))
    with pytest.raises(ValueError, match='ID changed'):
        binding.read_ref(dict(reference, id='0' * 64))


def test_only_new_implementation_files_and_original_primary_GPU_lane():
    assert len(registration.FILES) == len(set(registration.FILES))
    assert all(Path(name).name == name and name.startswith('finqa_v70_') for name in registration.FILES)
    assert binding.MAX_WORKERS == 6 and binding.MAX_WORKERS_PER_GPU == 1
    assert set(binding.GPU_PRIORITY) == set(range(8))
    assert binding.POINTS == (894, 1192, 1490)
    assert binding.ROOT != binding.SOURCE_ROOT
