"""Supplemental actual-evidence verification; no Provider or financial execution."""

import json
import socket
from collections import Counter
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

from trusted_synthesis.architecture.generalization import audit_generalization_contract
from trusted_synthesis.domains.finance.qa_vnext.program_adapter import ProgramTaskAdapter
from trusted_synthesis.domains.finance.qa_vnext.runtime import DurableStore, PublicQARuntime
from trusted_synthesis.domains.finance.qa_vnext.share_adapter import ShareTaskAdapter
from trusted_synthesis.experiments.finance_qa_vnext_model_execution import runner as original
from trusted_synthesis.experiments.finance_qa_vnext_model_execution.models import read_json, record, require
from trusted_synthesis.experiments.finance_qa_vnext_model_execution.plan import seal_directory, verify_source_snapshot
from trusted_synthesis.experiments.finance_qa_vnext_model_execution.qualification import _Artifacts
from trusted_synthesis.experiments.finance_qa_vnext_model_execution.transport import HttpxSender, OnlineModelCallback
from trusted_synthesis.experiments.finance_qa_vnext_repaired_full_task import runner
from trusted_synthesis.experiments.finance_qa_vnext_repaired_full_task.plan import history_inventory

ROOT = Path('/data1/zhuxinrui/projects/Data-Synthesis')
RUN = ROOT / 'trusted_data_synthesis/artifacts/qa_vnext_repaired_full_task/finance_qa_vnext_repaired_update_six_session_full_task_20260906'
PREP, EXEC = RUN / 'preparation', RUN / 'execution'
counters = Counter({key: 0 for key in ['credential', 'provider', 'callback', 'socket', 'runtime', 'program_execute', 'share_execute']})


def forbidden(name):
    def fail(*args, **kwargs):
        counters[name] += 1
        raise AssertionError('readonly forbidden: ' + name)
    return fail


def members(directory):
    return {p.relative_to(directory).as_posix(): p.read_bytes()
            for p in directory.rglob('*') if p.is_file()}


with ExitStack() as stack:
    for obj, name, key in [
        (runner, '_credential', 'credential'), (original, '_credential', 'credential'),
        (HttpxSender, 'send', 'provider'), (OnlineModelCallback, 'generate', 'callback'),
        (socket.socket, 'connect', 'socket'), (socket, 'create_connection', 'socket'),
        (PublicQARuntime, '__init__', 'runtime'),
        (ProgramTaskAdapter, 'execute', 'program_execute'), (ShareTaskAdapter, 'execute', 'share_execute'),
    ]:
        stack.enter_context(patch.object(obj, name, forbidden(key)))
    reports = [runner.analyze(ROOT, PREP, EXEC, RUN / 'reanalysis')]
    # The other branch of the initial parallel verification completed and was sealed.
    # Preserve it; do not overwrite or re-run it. Its bytes are checked below.
    reports.append(read_json((RUN / 'guarded_reanalysis/report.json').read_bytes()))
require(all(value == 0 for value in counters.values()), 'verification.zero_execution')
original_members = members(EXEC / 'analysis')
require(all(members(RUN / name) == original_members for name in ['reanalysis', 'guarded_reanalysis']),
        'verification.byte_identical_reanalysis')
require(all(report == read_json((EXEC / 'report.json').read_bytes()) for report in reports),
        'verification.report_identical')
implementation = read_json((PREP / 'implementation.json').read_bytes())
verify_source_snapshot(ROOT, implementation)
historical = history_inventory(ROOT)
require(historical == read_json((PREP / 'history_inventory.json').read_bytes()), 'verification.old_artifacts_unchanged')
verified = []
for name in ['preparation', 'execution', 'reanalysis', 'guarded_reanalysis']:
    for path in sorted((RUN / name).rglob('manifest.json')):
        evidence = _Artifacts(path.parent)
        verified.append({'directory': path.parent.relative_to(RUN).as_posix(),
                         'manifest_id': evidence.manifest['id'], 'members': len(evidence.files)})
audit = audit_generalization_contract(ROOT / 'trusted_data_synthesis/src')
require(audit.passed, 'verification.architecture')
store = DurableStore(RUN / 'readonly_verification')
store.write('verify.py', Path(__file__).read_bytes())
store.json('architecture.json', audit.model_dump(mode='json'))
report = record('repaired_readonly_verification', report_id=reports[0]['id'],
                implementation_id=implementation['id'], source_commit=implementation['source_commit'],
                source_file_count=len(implementation['members']), guards=dict(counters),
                repeated_analysis_count=2, byte_identical_analysis_files=len(original_members),
                new_guarded_analysis_this_check=1, prior_guarded_analysis_preserved=1,
                initial_parallel_local_failure={
                    'exception': 'ImportError: cannot import name AutoTokenizer from transformers',
                    'failed_branch': 'reanalysis, before output directory creation',
                    'completed_branch': 'guarded_reanalysis',
                    'recovery': 'sequential invocation; no experiment source change',
                    'provider_calls': 0, 'online_evidence_changed': False,
                },
                byte_identical_analysis_bytes=sum(len(x) for x in original_members.values()),
                historical_file_count=len(historical['members']),
                historical_bytes=sum(x['bytes'] for x in historical['members']),
                historical_inventory_id=historical['id'], old_artifacts_unchanged=True,
                all_recursive_manifests=verified, architecture_passed=audit.passed,
                architecture_file_count=audit.scanned_file_count, passed=True)
store.json('report.json', report)
seal_directory(store, kind='six_readonly_verification_manifest', report_id=report['id'])
print(json.dumps(report, ensure_ascii=False, sort_keys=True), flush=True)
