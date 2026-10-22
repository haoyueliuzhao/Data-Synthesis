"""Focused fixed-roster/timing/resource contract checks without private scoring."""
import copy

import pytest

import finqa_v68_registration as r


def test_automatic_scope_is_all_six_original_groups_not_only_initial_ready_pair():
    roster = r.fixed_roster()
    assert set(roster) == {f'seed{s}/{a}' for s in (137, 251, 389) for a in ('C1', 'C05')}
    assert all(len(keys) == 4 for keys in roster.values())
    assert len({key for keys in roster.values() for key in keys}) == 24
    contract = r.automatic_contract()
    assert contract['sessions'] == 7458 and contract['sessions_per_group'] == 1243
    assert contract['automatic_first_dispatch_on_group_ready'] is True
    assert contract['each_group_first_scoring_at_most_once'] is True
    assert contract['exception_retry_authorized'] is False
    assert contract['global_analysis_or_advancement_authorized'] is False
    assert contract['original_global_barrier_not_claimed_passed'] is True
    assert contract['private_scores_fed_to_remaining_generation_or_training'] is False


def _protocol(monkeypatch):
    source = r.b.base_protocol()
    import finqa_v68_scoring as scoring
    value = dict(schema=r.SCHEMA, control_root=str(r.ROOT), scientific_root=str(r.b.SCIENTIFIC_ROOT),
        scientific_protocol_id=r.b.BASE_PROTOCOL_ID, group_roster=r.fixed_roster(),
        allowed_groups=sorted(r.fixed_roster()), automatic_scoring=r.automatic_contract(),
        scoring=scoring.scoring_contract(), max_cpu_workers=2, cpu_rss_limit_gib=32,
        host_reserve_gib=96, other_scopes_startup_gib=352, startup_available_gib=512,
        GPU_workers=0, new_generation_or_provider_calls=0, implementation={'id': 'implementation'},
        global_analysis_or_advancement_authorized=False, private_references_read=False,
        original_protocols_and_failures_unchanged=True,
        signal_policy=source['signal_policy'], signal_source_bindings=source['signal_source_bindings'])
    paths = {'science_protocol_ref': r.b.SCIENTIFIC_ROOT / 'protocol/record.json',
        'source_generation_registration': r.b.SOURCE_GENERATION_ROOT / 'evaluations/registration/record.json',
        'completion_generation_registration': r.b.COMPLETION_ROOT / 'evaluations/registration/record.json',
        'six_branch_training_barrier': r.b.SCIENTIFIC_ROOT / 'training_barrier/record.json'}
    value.update({key: {'path': str(path)} for key, path in paths.items()})
    monkeypatch.setattr(r, '_VERIFIED_PROTOCOL', None)
    monkeypatch.setattr(r, 'checked_implementation', lambda: {'id': 'implementation'})
    monkeypatch.setattr(r.b, 'checked', lambda path: value)
    monkeypatch.setattr(r.b, 'read_ref', lambda ref: {'id': r.b.BASE_PROTOCOL_ID})
    monkeypatch.setattr(r, 'checked_source_plans', lambda: None)
    return value


def test_registered_cpu_only_group_watcher_policy(monkeypatch):
    value = _protocol(monkeypatch)
    assert r.checked_protocol() is value
    assert value['startup_available_gib'] == 96 + 6 * 48 + 64 + 2 * 32


@pytest.mark.parametrize('key,value', [
    ('max_cpu_workers', 3), ('cpu_rss_limit_gib', 64), ('host_reserve_gib', 95),
    ('other_scopes_startup_gib', 288), ('startup_available_gib', 448),
    ('GPU_workers', 1), ('new_generation_or_provider_calls', 1),
    ('global_analysis_or_advancement_authorized', True),
    ('private_references_read', True), ('original_protocols_and_failures_unchanged', False),
    ('scientific_protocol_id', 'different'), ('allowed_groups', ['seed137/C1']),
])
def test_expansion_or_changed_scientific_contract_rejected(monkeypatch, key, value):
    protocol = _protocol(monkeypatch)
    protocol[key] = value
    with pytest.raises(ValueError):
        r.checked_protocol()


@pytest.mark.parametrize('key', ['repeat_accepted_scoring', 'exception_retry_authorized',
                               'private_scores_fed_to_remaining_generation_or_training'])
def test_auto_continuation_is_not_auto_retry_or_feedback(monkeypatch, key):
    value = _protocol(monkeypatch)
    value['automatic_scoring'] = copy.deepcopy(value['automatic_scoring'])
    value['automatic_scoring'][key] = True
    with pytest.raises(ValueError):
        r.checked_protocol()


def test_eligibility_path_is_bound_to_original_model_coordinate():
    assert r.b.eligibility_path('seed137/C1') == r.ROOT / 'eligibility/seed137/C1/record.json'
    for bad in ('seed137/Hold', 'seed999/C1', '../../old', 'seed137/C1/../../bad'):
        with pytest.raises(ValueError):
            r.b.eligibility_path(bad)
