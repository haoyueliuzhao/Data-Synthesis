"""CPU-only checks for the independent six-worker registration contract."""
import copy
import importlib
from pathlib import Path
from types import SimpleNamespace

import pytest

from finqa_v61_binding import resource_override
import finqa_v61_registration as reg


def test_override_retains_mathematics_and_original_resource_gates():
    value = resource_override()
    assert (value['original_scientific_max_gpu_workers'], value['max_gpu_workers'], value['per_gpu_workers']) == (4, 6, 1)
    assert value['logical_class_shards'] == 4
    assert value['host_startup_gib_by_kind']['generate'] == 48
    assert (value['allocated_lifetime_limit_gib'], value['boundary_free_reserve_gib'],
            value['other_rss_limit_gib'], value['effective_host_available_reserve_gib']) == (76, 2, 192, 96)
    assert value['new_sampling_API_or_evaluation_budget'] == 0
    assert value['original_scientific_protocol_bytes_and_ID_unchanged']
    assert value['current_replay_not_split_or_migrated']


def policies(monkeypatch):
    controller = SimpleNamespace(adapter_contract=lambda root: dict(root=str(root), override=resource_override()))
    observer = SimpleNamespace(observer_policy=lambda: {'observer': 'unchanged'})
    watchdog = SimpleNamespace(policy=lambda: {'limit': 6})
    monkeypatch.setattr(reg, 'policy_modules', lambda: (watchdog, controller, observer))
    return watchdog, controller, observer


def test_master_requires_six_override_and_exact_handoff_binding(monkeypatch, tmp_path):
    monkeypatch.setattr(reg, 'MASTER_ROOT', tmp_path)
    watchdog, _, _ = policies(monkeypatch)
    calls = []
    handoff = SimpleNamespace(policy=lambda: {'passive': True},
        checked_binding=lambda value, **kwargs: calls.append((value, kwargs)))
    cron = SimpleNamespace(cron_policy=lambda: {'cron': 'new'})
    original_import = importlib.import_module
    monkeypatch.setattr(reg.importlib, 'import_module', lambda name, *args, **kwargs:
        handoff if name == 'finqa_v61_handoff' else cron if name == 'finqa_v61_cron'
        else original_import(name, *args, **kwargs))
    helper = SimpleNamespace(signals_policy=lambda: {'signal': 'owner-preserved'},
        gpu_isolation_policy=lambda: {'yyy': 'excluded'})
    monkeypatch.setattr(reg, 'load_v59_module', lambda name: helper)
    monkeypatch.setattr(reg, 'checked_implementation', lambda root: {'id': 'implementation'})
    monkeypatch.setattr(reg, 'read_ref', lambda ref: ref)
    locks = [tmp_path / 'science.lock', tmp_path / 'gpu.lock']
    monkeypatch.setattr(reg, 'original_lock_paths', lambda value: locks)
    value = dict(schema=reg.MASTER_SCHEMA, root=str(tmp_path), scientific_root=str(reg.SCIENCE_ROOT),
        scientific_protocol_id=reg.SCIENTIFIC_PROTOCOL_ID, policy=watchdog.policy(),
        recovery_contract=reg.recovery_contract(),
        initial_control_protocol={'id': reg.SOURCE_CONTROL_PROTOCOL_ID},
        scientific_protocol={'id': reg.SCIENTIFIC_PROTOCOL_ID}, implementation={'id': 'implementation'},
        signals_policy=helper.signals_policy(), gpu_isolation_policy=helper.gpu_isolation_policy(),
        cron_policy=cron.cron_policy(),
        original_lock_bindings={str(path): {'device': 1, 'inode': index} for index, path in enumerate(locks)},
        original_scientific_max_gpu_workers=4, max_gpu_workers=6, per_gpu_workers=1,
        resource_override=resource_override(), prior_watchdog_protocol={'id': reg.PARENT_WATCHDOG_PROTOCOL_ID},
        handoff_policy=handoff.policy(), handoff_binding={'bound_source': 'old04'})
    monkeypatch.setattr(reg, 'checked_record', lambda path: value)
    assert reg.checked_master_protocol(tmp_path) is value
    assert calls == [({'bound_source': 'old04'}, {'require_live': False, 'allow_superseded': True})]
    for field, invalid in [('max_gpu_workers', 4), ('original_scientific_max_gpu_workers', 6),
                           ('per_gpu_workers', 2)]:
        saved = value[field]
        value[field] = invalid
        with pytest.raises(ValueError):
            reg.checked_master_protocol(tmp_path)
        value[field] = saved


def test_episode_requires_original_four_and_effective_six(monkeypatch, tmp_path):
    root = tmp_path / 'episode000001'
    monkeypatch.setattr(reg, 'episode_root', lambda path: Path(path).resolve())
    _, controller, observer = policies(monkeypatch)
    master = dict(id='master', implementation={'id': 'impl'}, signals_policy={'owner': True},
                  gpu_isolation_policy={'yyy': True})
    monkeypatch.setattr(reg, 'checked_master_protocol', lambda: master)
    value = dict(schema=reg.EPISODE_SCHEMA, control_root=str(root), scientific_root=str(reg.SCIENCE_ROOT),
        scientific_protocol_id=reg.SCIENTIFIC_PROTOCOL_ID, master_protocol_id='master',
        implementation=master['implementation'], adapter_contract=controller.adapter_contract(root),
        observer_policy=observer.observer_policy(), signals_policy=master['signals_policy'],
        gpu_isolation_policy=master['gpu_isolation_policy'], original_scientific_max_gpu_workers=4,
        max_gpu_workers=6, per_gpu_workers=1, resource_override=resource_override(),
        durable_audit={'id': 'audit'}, exit_observation={'id': 'observation'})
    monkeypatch.setattr(reg, 'checked_record', lambda path: value)
    seen = []
    monkeypatch.setattr(reg, 'read_ref', lambda reference: seen.append(reference))
    assert reg.checked_protocol(root) is value
    assert seen == [value['durable_audit'], value['exit_observation']]
    value['resource_override'] = copy.deepcopy(value['resource_override'])
    value['resource_override']['new_sampling_API_or_evaluation_budget'] = 700
    with pytest.raises(ValueError):
        reg.checked_protocol(root)


def test_initial_preparation_cannot_change_bound_handoff(monkeypatch, tmp_path):
    monkeypatch.setattr(reg, 'MASTER_ROOT', tmp_path)
    protocol = dict(id='master', handoff_binding={'source': 'fixed'})
    monkeypatch.setattr(reg, 'checked_protocol', lambda root: protocol)
    value = dict(protocol_id='master', handoff_binding={'source': 'fixed'},
        initial_episode=dict(root=str(reg.SOURCE_CONTROL_ROOT), protocol_id=reg.SOURCE_CONTROL_PROTOCOL_ID),
        initial_action='observe_only_until_authorized_safe_handoff')
    monkeypatch.setattr(reg, 'checked_record', lambda path: value)
    assert reg.checked_prepared(tmp_path) is value
    value['handoff_binding'] = {'source': 'other'}
    with pytest.raises(ValueError):
        reg.checked_prepared(tmp_path)


def test_default_backend_bridge_and_bundle_preserve_required_members(monkeypatch):
    hook = object()
    original_import = importlib.import_module
    monkeypatch.setattr(reg.importlib, 'import_module', lambda name, *args, **kwargs:
        SimpleNamespace(checked_authorized_handoff=hook) if name == 'finqa_v61_backend'
        else original_import(name, *args, **kwargs))
    assert reg.checked_authorized_handoff is hook
    assert len(reg.FILES) == 14
    assert len(reg.INHERITED_FILES) == 6
    assert 'finqa_v59_worker.py' in reg.INHERITED_FILES
    assert 'finqa_v61_handoff.py' in reg.NEW_FILES
    contract = reg.recovery_contract()
    assert contract['independent_GPU_workers'] == 6
    assert contract['original_scientific_max_gpu_workers'] == 4
    assert contract['all_core_training_accepted_before_handoff']
