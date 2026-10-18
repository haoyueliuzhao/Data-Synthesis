from types import SimpleNamespace

import pytest

import finqa_v59_gpu_isolation as isolation


def xml(*entries):
    return '<nvidia_smi_log><gpu><uuid>GPU-test</uuid><processes>' + ''.join(
        f'<process_info><pid>{pid}</pid><type>{kind}</type><process_name>{name}</process_name></process_info>'
        for pid, kind, name in entries) + '</processes></gpu></nvidia_smi_log>'


@pytest.mark.parametrize('entries,owner,allowed', [
    ([], {}, True),
    ([(20, 'C', 'python')], dict(ownership_known=True, excluded_owner=True, birth='123'), False),
    ([(20, 'G', 'display')], dict(ownership_known=True, excluded_owner=True, birth='123'), False),
    ([(20, 'C', 'python')], dict(ownership_known=True, excluded_owner=False, birth='123'), True),
    ([(20, 'C', 'python')], dict(ownership_known=False, reason='gone'), False),
    ([(20, 'C', 'nvidia-cuda-mps-server')], dict(ownership_known=True, excluded_owner=False), False),
])
def test_compute_graphics_unknown_and_MPS(entries, owner, allowed):
    value = isolation.probe_gpus(['GPU-test'], query=lambda _: xml(*entries),
        process_identity=lambda _: owner, uid_resolver=lambda _: 1000)['GPU-test']
    assert value['allowed'] is allowed


def test_unavailable_query_and_changed_user_fail_closed():
    def denied(_):
        raise PermissionError('unavailable')
    assert not isolation.probe_gpus(['GPU-test'], query=denied,
        uid_resolver=lambda _: 1000)['GPU-test']['allowed']
    assert not isolation.probe_gpus(['GPU-test'], query=lambda _: xml(),
        uid_resolver=lambda _: 999)['GPU-test']['allowed']


def test_controller_proxy_is_lazy_and_never_changes_memory_or_UUID(monkeypatch):
    calls = []
    original = SimpleNamespace(inventory=lambda: calls.append('inventory') or [dict(index=2, uuid='GPU-test', free_mib=75000)], marker=7)
    proxy = isolation.install_controller_runtime(original)
    assert calls == [] and proxy.marker == 7
    monkeypatch.setattr(isolation, 'probe_gpus', lambda _: {'GPU-test': dict(allowed=False)})
    assert proxy.inventory() == []
    monkeypatch.setattr(isolation, 'probe_gpus', lambda _: {'GPU-test': dict(allowed=True)})
    assert proxy.inventory()[0]['free_mib'] == 75000
    assert proxy.inventory()[0]['uuid'] == 'GPU-test'


def test_worker_pre_cuda_defers_before_original_wait_and_preserves_hard_gate(monkeypatch):
    events = []
    class Deferred(Exception):
        pass
    class Hard(Exception):
        pass
    class Stop(Exception):
        pass
    class Base:
        gpu, violation, stop, job = 2, None, SimpleNamespace(requested=False), dict(stage='shard00')
        def _defer(self, observation):
            events.append(('defer', observation['resource_category']))
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
    assert events == [('defer', 'excluded_GPU_owner_or_unresolved_ownership')]
    events.clear()
    with pytest.raises(Hard):
        guard._sample('before_work', True, {})
    assert events == ['hard_gate']
    guard.stop = SimpleNamespace(requested=True)
    with pytest.raises(Stop):
        guard._isolation('stopped')
