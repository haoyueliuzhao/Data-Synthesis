"""Known-owner sharing only; no GPU, CUDA, process control or scientific work."""
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

import finqa_v62_gpu_isolation as isolation


def xml(*entries):
    return '<nvidia_smi_log><gpu><uuid>GPU-test</uuid><processes>' + ''.join(
        f'<process_info><pid>{pid}</pid><type>{kind}</type><process_name>{name}</process_name></process_info>'
        for pid, kind, name in entries) + '</processes></gpu></nvidia_smi_log>'


def owner(uid=1000, **changes):
    return dict(dict(pid=20, ownership_known=True, birth='123', uids=[uid] * 4), **changes)


@pytest.mark.parametrize('uid,kind', [(1000, 'C'), (1000, 'G'), (0, 'C'), (1004, 'C')])
def test_all_known_UIDs_allowed_without_account_lookup(uid, kind):
    result = isolation.probe_gpus(['GPU-test'], query=lambda _: xml((20, kind, 'python')),
        process_identity=lambda _: owner(uid))['GPU-test']
    assert result['allowed'] and result['known_processes'] == [dict(pid=20, birth='123', uids=[uid] * 4)]
    assert isolation.gpu_isolation_policy()['excluded_host_uid'] is None


@pytest.mark.parametrize('identity,name,kind', [
    (owner(ownership_known=False), 'python', 'C'),
    (owner(uids=[]), 'python', 'C'),
    (owner(uids=[1000, 1000, None, 1000]), 'python', 'C'),
    (owner(pid=21), 'python', 'C'),
    (owner(birth=None), 'python', 'C'),
    (owner(), 'nvidia-cuda-mps-server', 'C'),
    (owner(), 'python', 'M'),
])
def test_unknown_and_unattributed_MPS_still_denied(identity, name, kind):
    result = isolation.probe_gpus(['GPU-test'], query=lambda _: xml((20, kind, name)),
        process_identity=lambda _: identity)['GPU-test']
    assert result['allowed'] is False and result['unresolved_processes']


def test_unavailable_query_fails_closed_and_empty_GPU_allows():
    def denied(_):
        raise PermissionError('unavailable')
    assert not isolation.probe_gpus(['GPU-test'], query=denied)['GPU-test']['allowed']
    assert isolation.probe_gpus(['GPU-test'], query=lambda _: xml())['GPU-test']['allowed']


def test_controller_filter_preserves_original_memory_UUID_and_gate(monkeypatch):
    calls = []
    delegate = SimpleNamespace(inventory=lambda: calls.append('inventory') or
        [dict(index=2, uuid='GPU-test', free_mib=123)], original_capacity_gate=lambda row: row['free_mib'] >= 200)
    proxy = isolation.install_controller_runtime(delegate)
    assert not calls
    monkeypatch.setattr(isolation, 'probe_gpus', lambda _: {'GPU-test': dict(allowed=True)})
    row = proxy.inventory()[0]
    assert row['free_mib'] == 123 and row['uuid'] == 'GPU-test'
    assert not proxy.original_capacity_gate(row)
    monkeypatch.setattr(isolation, 'probe_gpus', lambda _: {'GPU-test': dict(allowed=False)})
    assert proxy.inventory() == []


def test_worker_hard_gate_and_stop_precede_unknown_owner_deferral(monkeypatch):
    events = []
    class Deferred(Exception):
        pass
    class Hard(Exception):
        pass
    class Stop(Exception):
        pass
    class Base:
        gpu, violation, stop, job = 2, None, SimpleNamespace(requested=False), dict(stage='generate')
        def _defer(self, observation):
            events.append(observation['resource_category'])
            raise Deferred()
        def _wait_until_capacity(self, **kwargs):
            events.append('original_wait')
        def _sample(self, *args):
            return dict(peak_allocated_bytes=100)
        def _hard_gates(self, value):
            events.append('hard_gate')
            raise Hard()
    runtime = SimpleNamespace(ResourceGuard=Base, GPU_UUIDS={'2': 'GPU-test'}, now=lambda: 'now',
        ExplicitStop=Stop, LifetimeResourceFailure=Hard)
    guard = isolation.guarded_class(runtime)()
    monkeypatch.setattr(isolation, 'probe_gpus', lambda _: {'GPU-test': dict(allowed=False)})
    with pytest.raises(Deferred):
        guard._wait_until_capacity(cuda_initialized=False)
    assert events == ['GPU_ownership_unresolved']
    events.clear()
    with pytest.raises(Hard):
        guard._sample('before_work', True, {})
    assert events == ['hard_gate']
    guard.stop = SimpleNamespace(requested=True)
    with pytest.raises(Stop):
        guard._isolation('stopped')
    assert events == ['hard_gate']


def bound(value):
    canonical = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode()
    return dict(value, id=hashlib.sha256(canonical).hexdigest())


def test_policy_binding_master_only_for_CPU_and_episode_for_production(tmp_path, monkeypatch):
    master = tmp_path / 'master'
    monkeypatch.setattr(isolation, 'MASTER_ROOT', master)
    manifest_path = master / 'implementation/record.json'
    manifest_path.parent.mkdir(parents=True)
    source = Path(isolation.__file__)
    manifest = bound(dict(files={source.name: hashlib.sha256(source.read_bytes()).hexdigest()}))
    manifest_path.write_text(json.dumps(manifest))
    reference = dict(path=str(manifest_path), id=manifest['id'], sha256=hashlib.sha256(manifest_path.read_bytes()).hexdigest())
    def publish(root, *, key):
        protocol = bound({key: str(root), 'scientific_root': str(isolation.SCIENCE_ROOT),
            'scientific_protocol_id': isolation.SCIENTIFIC_PROTOCOL_ID,
            'gpu_isolation_policy': isolation.gpu_isolation_policy(), 'implementation': reference})
        (root / 'protocol').mkdir(parents=True)
        (root / 'protocol/record.json').write_text(json.dumps(protocol))
        return protocol
    publish(master, key='root')
    monkeypatch.setenv('V57_CONTROL_ROOT', str(master))
    with pytest.raises(ValueError, match='CPU-check-only'):
        isolation._checked_control_policy()
    assert isolation._checked_control_policy(allow_master=True)['root'] == str(master)
    episode = master / 'episodes/episode000001'
    assert publish(episode, key='control_root')
    monkeypatch.setenv('V57_CONTROL_ROOT', str(episode))
    assert isolation._checked_control_policy()['control_root'] == str(episode)
    value = json.loads((episode / 'protocol/record.json').read_bytes())
    value['gpu_isolation_policy']['unknown_ownership_or_unattributed_MPS_blocks_admission'] = False
    value = bound({k: v for k, v in value.items() if k != 'id'})
    (episode / 'protocol/record.json').write_text(json.dumps(value))
    with pytest.raises(ValueError, match='sharing authorization'):
        isolation._checked_control_policy()

