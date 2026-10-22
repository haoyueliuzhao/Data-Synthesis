"""Register automatic first scoring when each fixed model group is sealed."""
from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import os
from pathlib import Path
import subprocess
import time

import finqa_v68_binding as b

ROOT = b.ROOT
FILES = tuple('finqa_v68_' + item + '.py' for item in
              ('binding', 'registration', 'adoption', 'scoring', 'entry'))
SCHEMA = 'v68_automatic_complete_group_native_scoring_protocol.v1'
PREPARED_SCHEMA = 'v68_six_fixed_groups_automatic_scoring_prepared.v1'
_VERIFIED_IMPLEMENTATION = None
_VERIFIED_PROTOCOL = None


def modules():
    b.source_module('finqa_v63_entry').install_registered_auxiliary()
    b.install_scientific_paths()
    return {name: importlib.import_module('finqa_v68_' + name)
            for name in ('adoption', 'scoring', 'entry')}


def fixed_roster():
    jobs = b.source_module('finqa_v63_evaluation').planned_jobs()
    result = {f'seed{seed}/{arm}': sorted(key for key, job in jobs.items()
              if (job['seed'], job['arm']) == (seed, arm)) for seed, arm in b.ELIGIBLE_COORDINATES}
    b.require(len(result) == 6 and all(len(keys) == 4 for keys in result.values())
              and len(jobs) == 24 and sum(job['denominator'] for job in jobs.values()) == 7458,
              'only the original six groups and 24 generation jobs may enter scoring')
    return result


def automatic_contract():
    return dict(schema='v68_fixed_roster_group_ready_automatic_scoring.v1',
        allowed_groups=sorted(fixed_roster()), group_count=6, generation_jobs=24, sessions=7458,
        complete_jobs_per_group=4, sessions_per_group=1243,
        before_private_scoring='this entire group has all four complete, source-bound and actually accepted generation artifacts',
        source_repaired_exit_semantics='original GPU exit1 retained plus separately accepted CPU exit0',
        source_new_exit_semantics='original new generation actual GPU exit0 accepted',
        automatic_first_dispatch_on_group_ready=True,
        currently_incomplete_groups_wait_without_reading_private_references=True,
        each_group_first_scoring_at_most_once=True, repeat_accepted_scoring=False,
        exception_retry_authorized=False, explicit_stop_disables_continuation=True,
        future_global_analysis_must_read_only_adopt_existing_score_rows=True,
        original_all_24_before_private_scoring_timing_superseded_only_in_this_scope=True,
        original_global_barrier_not_claimed_passed=True, original_protocols_rewritten=False,
        source_generation_and_training_policy_modified=False,
        private_scores_fed_to_remaining_generation_or_training=False,
        global_analysis_or_advancement_authorized=False,
        old_b0_or_Hold_rescoring_authorized=False, new_generation_or_provider_calls=0,
        numerical_scoring_and_UNKNOWN_semantics_unchanged=True)


def checked_source_plans():
    early = b.checked(b.SOURCE_GENERATION_ROOT / 'evaluations/registration/record.json')
    completion = b.checked(b.COMPLETION_ROOT / 'evaluations/registration/record.json')
    b.require(early['protocol_id'] == b.EARLY_PROTOCOL_ID
              and completion['protocol_id'] == b.COMPLETION_PROTOCOL_ID
              and early['scientific_protocol_id'] == completion['scientific_protocol_id'] == b.BASE_PROTOCOL_ID
              and len(early['jobs']) == 20 and len(completion['jobs']) == 4
              and not (set(early['jobs']) & set(completion['jobs'])),
              'the immutable twenty-plus-four generation sources changed')
    combined = dict(early['jobs'], **completion['jobs'])
    expected = b.source_module('finqa_v63_evaluation').planned_jobs()
    b.require(set(combined) == set(expected) and all(all(combined[key][field] == value
              for field, value in job.items()) for key, job in expected.items()),
              'source jobs differ from the original complete science roster')
    for key in ('snapshot', 'snapshot_id', 'cohorts'):
        b.require(early[key] == completion[key], 'two generation sources use different ' + key)
    return early, completion


def freeze(source_commit):
    b.require(not ROOT.exists(), 'automatic scoring requires one fresh independent registration')
    commit = subprocess.check_output(['git', 'rev-parse', source_commit + '^{commit}'], cwd=b.REPO, text=True).strip()
    sources = {}
    for name in FILES:
        relative = 'trusted_data_synthesis/scripts/' + name
        raw = subprocess.check_output(['git', 'show', commit + ':' + relative], cwd=b.REPO)
        b.require(hashlib.sha256(raw).hexdigest() == b.sha(b.REPO / relative), 'uncommitted V68 source: ' + name)
        sources[name] = raw
    directory = ROOT / 'implementation'
    directory.mkdir(parents=True, exist_ok=False)
    for name, raw in sources.items():
        with (directory / name).open('xb') as stream:
            stream.write(raw); stream.flush(); os.fsync(stream.fileno())
    return b.publish(directory / 'record.json', dict(schema='v68_frozen_automatic_CPU_scoring_sources.v1',
        source_commit=commit, committed_files=list(FILES),
        sha256={name: hashlib.sha256(raw).hexdigest() for name, raw in sources.items()},
        scientific_implementation=b.entry(b.SCIENTIFIC_ROOT / 'implementation/record.json'),
        early_generation_implementation=b.entry(b.SOURCE_GENERATION_ROOT / 'implementation/record.json'),
        completion_implementation=b.entry(b.COMPLETION_ROOT / 'implementation/record.json'),
        original_sources_modified=False, private_references_read=False, native_scoring_calls=0))


def checked_implementation(root=ROOT):
    global _VERIFIED_IMPLEMENTATION
    b.require(Path(root).resolve() == ROOT, 'foreign automatic scoring implementation root')
    if _VERIFIED_IMPLEMENTATION is not None:
        return _VERIFIED_IMPLEMENTATION
    value = b.checked(ROOT / 'implementation/record.json')
    b.require(value['committed_files'] == list(FILES) and set(value['sha256']) == set(FILES)
              and b.read_ref(value['scientific_implementation'])['id'] == b.BASE_IMPLEMENTATION_ID
              and b.read_ref(value['early_generation_implementation'])['id'] == b.EARLY_IMPLEMENTATION_ID
              and b.read_ref(value['completion_implementation'])['id'] == b.COMPLETION_IMPLEMENTATION_ID,
              'scoring frozen source package or lineage differs')
    for name, expected in value['sha256'].items():
        b.require(b.sha(ROOT / 'implementation' / name) == expected, 'frozen scoring source changed: ' + name)
    _VERIFIED_IMPLEMENTATION = value
    return value


def checked_protocol(root=ROOT):
    global _VERIFIED_PROTOCOL
    b.require(Path(root).resolve() == ROOT, 'foreign automatic scoring protocol root')
    if _VERIFIED_PROTOCOL is not None:
        return _VERIFIED_PROTOCOL
    value = b.checked(ROOT / 'protocol/record.json')
    scoring = importlib.import_module('finqa_v68_scoring')
    original = b.base_protocol()
    b.require(value['schema'] == SCHEMA and value['control_root'] == str(ROOT)
              and value['scientific_root'] == str(b.SCIENTIFIC_ROOT)
              and value['scientific_protocol_id'] == b.BASE_PROTOCOL_ID
              and value['group_roster'] == fixed_roster() and value['allowed_groups'] == sorted(fixed_roster())
              and value['automatic_scoring'] == automatic_contract()
              and value['scoring'] == scoring.scoring_contract()
              and value['max_cpu_workers'] == b.MAX_CPU_WORKERS == 2
              and value['cpu_rss_limit_gib'] == b.CPU_RSS_LIMIT_GIB == 32
              and value['host_reserve_gib'] == b.HOST_RESERVE_GIB == 96
              and value['other_scopes_startup_gib'] == b.OTHER_SCOPES_STARTUP_GIB == 352
              and value['startup_available_gib'] == 512
              and value['GPU_workers'] == value['new_generation_or_provider_calls'] == 0
              and value['global_analysis_or_advancement_authorized'] is False
              and value['private_references_read'] is False
              and value['original_protocols_and_failures_unchanged'] is True
              and value['implementation']['id'] == checked_implementation()['id'],
              'fixed six-group scoring, timing authorization or CPU resource contract changed')
    for key in ('signal_policy', 'signal_source_bindings'):
        b.require(value[key] == original[key], 'original explicit stop semantics changed')
    refs = {'science_protocol_ref': b.SCIENTIFIC_ROOT / 'protocol/record.json',
        'source_generation_registration': b.SOURCE_GENERATION_ROOT / 'evaluations/registration/record.json',
        'completion_generation_registration': b.COMPLETION_ROOT / 'evaluations/registration/record.json',
        'six_branch_training_barrier': b.SCIENTIFIC_ROOT / 'training_barrier/record.json'}
    for key, path in refs.items():
        b.require(Path(value[key]['path']).resolve() == path.resolve(), 'scoring source path changed: ' + key)
        b.read_ref(value[key])
    b.require(b.read_ref(value['science_protocol_ref'])['id'] == b.BASE_PROTOCOL_ID,
              'scientific scoring identity changed')
    checked_source_plans()
    _VERIFIED_PROTOCOL = value
    return value


def checked_prepared(root=ROOT):
    b.require(Path(root).resolve() == ROOT, 'foreign automatic scoring preparation root')
    protocol = checked_protocol()
    value = b.checked(ROOT / 'prepared/record.json')
    b.require(value['schema'] == PREPARED_SCHEMA and value['protocol_id'] == protocol['id']
              and value['scientific_protocol_id'] == b.BASE_PROTOCOL_ID
              and value['registered_groups'] == 6 and value['generation_jobs'] == 24
              and value['sessions'] == 7458 and value['private_references_read'] is False
              and value['native_scoring_calls'] == 0 and value['automatic_future_ready_groups'] is True,
              'automatic first-scoring roster is not prepared')
    b.read_ref(value['initial_ready_snapshot'])
    return value


def prepare(source_commit):
    loaded = modules()
    b.require(not ROOT.exists(), 'automatic scoring registration may not be overwritten')
    checked_source_plans()
    ready = loaded['adoption'].read_ready_groups()
    original = b.base_protocol()
    barrier = b.checked(b.SCIENTIFIC_ROOT / 'training_barrier/record.json')
    b.require(barrier['all_six_new_branches_complete'] is True
              and barrier['all_six_894_snapshots_sealed'] is True
              and barrier['all_dispatched_training_workers_exited'] is True
              and barrier['active_children'] == [], 'all original training must remain completed')
    implementation = freeze(source_commit)
    b.publish(ROOT / 'initial_ready_snapshot/record.json', ready)
    protocol = b.publish(ROOT / 'protocol/record.json', dict(schema=SCHEMA,
        control_root=str(ROOT), scientific_root=str(b.SCIENTIFIC_ROOT), scientific_protocol_id=b.BASE_PROTOCOL_ID,
        science_protocol_ref=b.entry(b.SCIENTIFIC_ROOT / 'protocol/record.json'),
        source_generation_registration=b.entry(b.SOURCE_GENERATION_ROOT / 'evaluations/registration/record.json'),
        completion_generation_registration=b.entry(b.COMPLETION_ROOT / 'evaluations/registration/record.json'),
        six_branch_training_barrier=b.entry(b.SCIENTIFIC_ROOT / 'training_barrier/record.json'),
        source_commit=implementation['source_commit'], implementation=b.entry(ROOT / 'implementation/record.json'),
        allowed_groups=sorted(fixed_roster()), group_roster=fixed_roster(), automatic_scoring=automatic_contract(),
        scoring=loaded['scoring'].scoring_contract(), max_cpu_workers=2, cpu_rss_limit_gib=32,
        host_reserve_gib=96, other_scopes_startup_gib=352, startup_available_gib=512,
        signal_policy=original['signal_policy'], signal_source_bindings=original['signal_source_bindings'],
        GPU_workers=0, new_generation_or_provider_calls=0, private_references_read=False,
        global_analysis_or_advancement_authorized=False, original_protocols_and_failures_unchanged=True,
        authorization=dict(initial='已经完成的几组可以先开始评分',
            automatic='设置自动接续，已完成的组自动进入评分，不再等待统一评分，提高效率'),
        created_epoch=time.time()))
    command = [str(b.PYTHON), '-c',
        'import finqa_v68_registration as r; r.modules(); r.prepare_frozen(); print("V68_AUTOMATIC_SCORING_PREPARED")']
    subprocess.run(command, cwd=b.REPO, env=dict(os.environ,
        PYTHONPATH=str(ROOT / 'implementation'), CUDA_VISIBLE_DEVICES=''), check=True)
    return protocol


def prepare_frozen():
    b.require(Path(__file__).resolve().parent == ROOT / 'implementation', 'preparation must use frozen scoring sources')
    protocol = checked_protocol()
    return b.publish(ROOT / 'prepared/record.json', dict(schema=PREPARED_SCHEMA,
        protocol_id=protocol['id'], scientific_protocol_id=b.BASE_PROTOCOL_ID,
        registered_groups=6, generation_jobs=24, sessions=7458,
        initial_ready_snapshot=b.entry(ROOT / 'initial_ready_snapshot/record.json'),
        automatic_future_ready_groups=True, private_references_read=False, native_scoring_calls=0,
        prepared_epoch=time.time()))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-commit', required=True)
    args = parser.parse_args()
    result = prepare(args.source_commit)
    print(json.dumps(dict(id=result['id'], schema=result['schema']), sort_keys=True))
