"""Narrow non-destructive tests for the new fixed historical archive scope."""
import hashlib
import importlib.util
import json
from pathlib import Path
import stat
from types import SimpleNamespace

import pytest

SOURCE = Path('/data1/zhuxinrui/projects/Data-Synthesis/trusted_data_synthesis/artifacts/storage_cleanup_20261019_cold_archive_01/archive.py')
spec = importlib.util.spec_from_file_location('cold_archive_20261019_tests', SOURCE)
archive = importlib.util.module_from_spec(spec)
spec.loader.exec_module(archive)


def context(seed=137, arm='c_only', step='0298'):
    return archive.PRODUCTION + f'/recovery_02/attempts/attempt0001/contexts/seed{seed}/{arm}/step{step}_outer'


def test_only_the_exact_wallets_trace_and_single_large_cohort_are_admitted():
    assert all(archive.allowed_source(path, 100) == 'wallet_snapshot' for path in archive.WALLETS)
    assert archive.allowed_source(archive.PROFILE, 100) == 'historical_profile_trace'
    assert archive.allowed_source(archive.COHORT, 8 * 1024**2 + 1) == 'old_non596_cohort_seal'
    for path, size in ((archive.COHORT, 8 * 1024**2), (archive.COHORT.replace('/step0894_', '/step0596_'), 20 * 1024**2),
                       (archive.COHORT.replace('dc03ecaa', 'different'), 20 * 1024**2),
                       (archive.FINQA + '/unknown/wallet_before_other.sqlite3', 100)):
        with pytest.raises(RuntimeError):
            archive.allowed_source(path, size)


def test_registered_non596_gradient_context_pattern_accepts_only_exact_complete_tail():
    for seed, arm, step in ((137, 'c_only', '0298'), (251, 'full', '0894'), (389, 'c_only', '1192')):
        path = context(seed, arm, step) + '/task_cache/task0007/gradient.pt'
        assert archive.allowed_source(path, 123) == 'old_non596_complete_task_gradient'


def test_protected_points_current_science_and_other_tensors_cannot_enter_gradient_scope():
    forbidden = (context(step='0596') + '/task_cache/task0007/gradient.pt',
        context(step='596') + '/task_cache/task0007/gradient.pt',
        context() + '/task_cache/task007/gradient.pt', context() + '/task_cache/task0007/state.pt',
        context() + '/task_cache/task0007/extra/gradient.pt',
        archive.V25 + '/training_replication/seed137/arms/c_only/training/step0298_step/state.pt',
        archive.V18 + '/v54_feedback_temperature_01/automatic_recovery_01/parents/seed137/task_cache/task0007/gradient.pt')
    for path in forbidden:
        with pytest.raises(RuntimeError):
            archive.allowed_source(path, 123)


def test_context_scope_totals_and_seed_group_are_strict():
    value = dict(schema=archive.SCOPE_SCHEMA, authorization=archive.AUTHORIZATION, sources=[],
        gradient_contexts=[dict(path=context(), group='old_class_seed137', count=2, allocated_bytes=8192, logical_bytes=6000)],
        groups={'old_class_seed137': dict(count=2, allocated_bytes=8192, logical_bytes=6000)})
    assert archive.validate_scope(value) is value
    wrong = {**value, 'gradient_contexts': [dict(value['gradient_contexts'][0], group='old_class_seed389')]}
    with pytest.raises(RuntimeError):
        archive.validate_scope(wrong)
    wrong = {**value, 'groups': {'old_class_seed137': dict(count=3, allocated_bytes=8192)}}
    with pytest.raises(RuntimeError):
        archive.validate_scope(wrong)


def test_changed_source_and_new_wallet_sidecar_fail_before_archival(tmp_path, monkeypatch):
    item = dict(path=archive.PROFILE, group='profiling_trace', allocated_bytes=4096, logical_bytes=20)
    scope = dict(sources=[item], groups={'profiling_trace': dict(count=1, allocated_bytes=4096)})
    monkeypatch.setattr(archive, 'configure', lambda: scope)
    monkeypatch.setattr(archive.engine, 'tracked_paths', lambda: set())
    monkeypatch.setattr(archive, 'ordinary', lambda path: [1, 2, stat.S_IFREG, 21, 0, 0, 1, 4096])
    with pytest.raises(RuntimeError, match='source changed'):
        archive.selected()
    wallet_relative = sorted(archive.WALLETS)[0]
    wallet = tmp_path / wallet_relative
    wallet.parent.mkdir(parents=True)
    wallet.with_name(wallet.name + '-wal').touch()
    monkeypatch.setattr(archive, 'REPO', tmp_path)
    with pytest.raises(RuntimeError, match='sidecar'):
        archive.check_database_sidecars(wallet)


def test_task_metadata_is_validated_once_then_any_identity_change_is_rejected(tmp_path, monkeypatch):
    gradient = tmp_path / 'gradient.pt'
    metadata = gradient.with_name('record.json')
    body = dict(schema='v35_complete_task_gradient.v1', complete_task=True, gradient_bytes=123)
    value = {**body, 'id': hashlib.sha256(archive.engine.encode(body)).hexdigest()}
    identity = [1, 2, stat.S_IFREG | 0o600, 200, 10, 10, 1, 4096]
    calls = []
    monkeypatch.setattr(archive, '_TASK_RECORD_CACHE', {})
    monkeypatch.setattr(archive, '_original_ordinary', lambda path: [1, 3, stat.S_IFREG, 123, 0, 0, 1, 4096])
    monkeypatch.setattr(archive, 'check_database_sidecars', lambda path: None)
    monkeypatch.setattr(archive.engine, 'identity', lambda path: list(identity))
    monkeypatch.setattr(archive, 'read', lambda path: calls.append(path) or value)
    archive.ordinary(gradient)
    archive.ordinary(gradient)
    assert calls == [metadata]
    identity[5] += 1
    with pytest.raises(RuntimeError, match='after its first validation'):
        archive.ordinary(gradient)


def test_positive_gain_includes_manifest_and_parent_scopes_do_not_expand():
    assert archive.positive_gain(16384, 8192, 4096) == 4096
    with pytest.raises(RuntimeError, match='positive allocated gain'):
        archive.positive_gain(12288, 8192, 4096)
    paths = [Path('/repo/old/task_cache'), Path('/repo/old/task_cache/task0001'), Path('/repo/separate/profile')]
    assert archive.minimal_scopes(paths) == [Path('/repo/old/task_cache'), Path('/repo/separate/profile')]


def test_precise_old_context_consumer_blocks_before_fd_open_without_blocking_current_observer():
    root = '/repo/' + context()
    target = root + '/task_cache/task0007/gradient.pt'
    parents, roots = {str(Path(target).parent)}, {root}
    assert archive.references_sources(['python', '--context', root], '/repo', {target}, parents, roots)
    assert archive.references_sources(['python', '--context=' + root + '/task_cache'], '/repo', {target}, parents, roots)
    assert archive.references_sources(['python'], root + '/task_cache', {target}, parents, roots)
    assert not archive.references_sources(['python', '--root', str(archive.V61)], '/repo', {target}, parents, roots)
    assert not archive.references_sources(['python', '--context', root + '_other'], '/repo', {target}, parents, roots)
    assert not archive.references_sources(['python', '/repo/' + archive.FINQA + '/v15_prefix_completion_01'],
                                          '/repo', {target}, parents, roots)


def test_restore_plan_binding_and_immutable_v61_sources_are_required(tmp_path, monkeypatch):
    monkeypatch.setattr(archive, 'checked_scope', lambda: {})
    monkeypatch.setattr(archive, '_SCOPE_SHA256', 'scope-sha')
    monkeypatch.setattr(archive, 'sha', lambda path: 'wrapper-sha')
    body = dict(frozen_engine_sha256=archive.ENGINE_SHA256, original_helper_sha256=archive.ORIGINAL_HELPER_SHA256,
        protection_helper_sha256=archive.PROTECTION_HELPER_SHA256, dependency_scope_sha256='scope-sha', script_sha256='wrapper-sha')
    bound = {**body, 'id': hashlib.sha256(archive.engine.encode(body)).hexdigest()}
    monkeypatch.setattr(archive, 'read', lambda path: bound)
    assert archive.require_plan_bindings() == bound
    monkeypatch.setattr(archive, 'read', lambda path: dict(bound, dependency_scope_sha256='changed'))
    with pytest.raises(RuntimeError, match='binding changed'):
        archive.require_plan_bindings()
    monkeypatch.setattr(archive, 'V61', tmp_path)
    monkeypatch.setattr(archive, 'protection_helper', lambda: SimpleNamespace(protected=lambda: {'old-anchor': [1]}))
    manifest = dict(files={f'frozen{index:02d}.py': 'hash' for index in range(14)})
    monkeypatch.setattr(archive, 'read', lambda path: manifest)
    monkeypatch.setattr(archive.engine, 'identity', lambda path: [str(path)])
    protected = archive.protected()
    assert 'old-anchor' in protected and str(tmp_path / 'protocol/record.json') in protected
    assert all(str(tmp_path / 'implementation' / name) in protected for name in manifest['files'])
    manifest['files'].pop('frozen13.py')
    with pytest.raises(RuntimeError, match='fourteen'):
        archive.protected()
