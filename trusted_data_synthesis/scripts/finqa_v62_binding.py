"""Pure, byte-bound imports for the account watchdog's independent episodes."""
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import sys

REPO = Path('/data1/zhuxinrui/projects/Data-Synthesis')
SCIENCE_ROOT = REPO / 'trusted_data_synthesis/artifacts/finance_research_20260928/finqa_v6_01/v18_researcher_continuation_01/v54_feedback_temperature_01/automatic_recovery_01'
MASTER_ROOT = SCIENCE_ROOT / 'shared_gpu_admission_01'
SUPERSEDED_MASTER_ROOT = SCIENCE_ROOT / 'concurrency_six_01'
SUPERSEDED_MASTER_PROTOCOL_ID = '004dd186042eb61c4168531d36c04fd740a54458841100b5c9ef8b9374076ff9'
PREPARATION_ROOT = SCIENCE_ROOT / 'shared_gpu_admission_preparation_01'
PARENT_WATCHDOG_ROOT = SCIENCE_ROOT / 'automatic_control_watchdog_01'
PARENT_WATCHDOG_PROTOCOL_ID = '3348cfe262cfdd12c6e4fb74b5b926d4845dc64301e4d3259df3261494f25b3b'
SOURCE_CONTROL_ROOT = SCIENCE_ROOT / 'signal_recovery_04'
SOURCE_CONTROL_PROTOCOL_ID = 'ffad4c05b8031cf94be53746b40ea1f0636c66e13e8a042d02b51cdb70736d5d'
SCIENTIFIC_PROTOCOL_ID = '53e084012b25dc34cc9a073cb53a1a3bf5d1dc7c4547937cd39e87e4d4be75af'
PYTHON = REPO / 'trusted_data_synthesis/.venv/bin/python'


def resource_override():
    return dict(schema='v62_authorized_six_worker_resource_override.v1',
        scientific_root=str(SCIENCE_ROOT), scientific_protocol_id=SCIENTIFIC_PROTOCOL_ID,
        original_scientific_max_gpu_workers=4, max_gpu_workers=6, per_gpu_workers=1,
        allowed_gpu_indices=list(range(8)), logical_class_shards=4,
        CPU_initialization_resource_wait_and_draining_count=True,
        original_scientific_protocol_bytes_and_ID_unchanged=True,
        original_math_feedback_point_attempts_budgets_and_scientific_dose_unchanged=True,
        effective_override_only='effective total workers 6 and cancellation of the yyy account-specific GPU exclusion',
        excluded_gpu_username=None, excluded_gpu_uid=None,
        prior_known_account_exclusion_cancelled=True,
        unknown_ownership_or_unattributed_MPS_blocks_admission=True,
        inherited_policy_worker_limits_interpreted_as_per_worker_hard_gates=True,
        host_startup_gib_by_kind=dict(class_=160, feedback=64, replay=48,
            distribution=64, train=48, generate=48),
        original_host_admission_formula_unchanged=True,
        allocated_lifetime_limit_gib=76, boundary_free_reserve_gib=2,
        class_rss_limit_gib=160, other_rss_limit_gib=192,
        effective_host_available_reserve_gib=96,
        GPU_UUIDs_CPU_affinity_and_unknown_owner_checks_unchanged=True,
        original_GPU_and_host_hard_limits_unchanged=True,
        prior_passive_V61_guard_must_be_superseded_without_scientific_STOP=True,
        new_sampling_API_or_evaluation_budget=0,
        accepted_jobs_and_real_exits_reused_without_recomputation=True,
        current_replay_not_split_or_migrated=True,
        activation='registered passive all-or-none handoff after core training acceptance',
        old_watchdog_and_old_control_frozen_files_not_hot_edited=True,
        actual_six_worker_dispatch_not_claimed_from_preparation=True)

def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
        separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def checked_record(path):
    value = json.loads(Path(path).read_bytes())
    require(value['id'] == digest({key: item for key, item in value.items() if key != 'id'}),
            'record identity changed: ' + str(path))
    return value


def episode_root(root):
    value = Path(root)
    require(not value.is_symlink(), 'a watchdog control episode cannot be a symlink')
    value = value.resolve()
    require(value.parent == MASTER_ROOT / 'episodes'
            and re.fullmatch(r'episode[0-9]{4,}', value.name) is not None,
            'one independent registered watchdog episode is required')
    return value


def checked_v59_implementation():
    protocol = checked_record(SOURCE_CONTROL_ROOT / 'protocol/record.json')
    require(protocol['id'] == SOURCE_CONTROL_PROTOCOL_ID
            and protocol['scientific_protocol_id'] == SCIENTIFIC_PROTOCOL_ID,
            'the exact initial V59 control/scientific authorization changed')
    reference = protocol['implementation']
    path = SOURCE_CONTROL_ROOT / 'implementation/record.json'
    require(Path(reference['path']).resolve() == path
            and hashlib.sha256(path.read_bytes()).hexdigest() == reference['sha256'],
            'initial V59 implementation reference changed')
    value = checked_record(path)
    require(value['id'] == reference['id'], 'initial V59 implementation identity changed')
    return value


def load_v59_module(name):
    require(name in {'finqa_v59_signals', 'finqa_v59_gpu_isolation', 'finqa_v59_observer'},
            'unregistered watchdog helper import')
    manifest = checked_v59_implementation()
    source = SOURCE_CONTROL_ROOT / 'implementation' / (name + '.py')
    expected = manifest['files'][source.name]
    require(hashlib.sha256(source.read_bytes()).hexdigest() == expected,
            'frozen V59 helper bytes changed: ' + name)
    private_name = '_v62_bound_' + name
    if private_name not in sys.modules:
        spec = importlib.util.spec_from_file_location(private_name, source)
        module = importlib.util.module_from_spec(spec)
        sys.modules[private_name] = module
        spec.loader.exec_module(module)
    result = sys.modules[private_name]
    require(Path(result.__file__).resolve() == source, 'bound helper import origin changed')
    return result
