"""Guarded reanalysis of the two completed actual B sessions; no Provider or execution."""

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
from trusted_synthesis.experiments.finance_qa_vnext_action_branch import runner
from trusted_synthesis.experiments.finance_qa_vnext_action_branch.controls import validator_preservation
from trusted_synthesis.experiments.finance_qa_vnext_action_branch.plan import history_inventory
from trusted_synthesis.experiments.finance_qa_vnext_model_execution import runner as original
from trusted_synthesis.experiments.finance_qa_vnext_model_execution.models import read_json, record, require
from trusted_synthesis.experiments.finance_qa_vnext_model_execution.plan import seal_directory, verify_source_snapshot
from trusted_synthesis.experiments.finance_qa_vnext_model_execution.qualification import _Artifacts
from trusted_synthesis.experiments.finance_qa_vnext_model_execution.transport import HttpxSender, OnlineModelCallback

ROOT = Path('/data1/zhuxinrui/projects/Data-Synthesis')
RUN = ROOT / 'trusted_data_synthesis/artifacts/qa_vnext_action_branch/action_contract_branch_v1_20260906'
PREP, EXEC = RUN / 'preparation', RUN / 'execution'
counters = Counter({k: 0 for k in ['credential', 'provider', 'callback', 'socket', 'runtime', 'program_execute', 'share_execute']})


def forbidden(name):
    def fail(*args, **kwargs):
        counters[name] += 1
        raise AssertionError('readonly forbidden: ' + name)
    return fail


def members(directory):
    return {p.relative_to(directory).as_posix(): p.read_bytes() for p in directory.rglob('*') if p.is_file()}


reports = []
with ExitStack() as stack:
    for obj, name, key in [
        (runner, '_credential', 'credential'), (original, '_credential', 'credential'),
        (HttpxSender, 'send', 'provider'), (OnlineModelCallback, 'generate', 'callback'),
        (socket.socket, 'connect', 'socket'), (socket, 'create_connection', 'socket'),
        (PublicQARuntime, '__init__', 'runtime'),
        (ProgramTaskAdapter, 'execute', 'program_execute'), (ShareTaskAdapter, 'execute', 'share_execute'),
    ]:
        stack.enter_context(patch.object(obj, name, forbidden(key)))
    # Serial local tokenizer initialization avoids introducing unrelated concurrent-import hazards.
    for name in ['reanalysis', 'guarded_reanalysis']:
        print('START readonly', name, flush=True)
        reports.append(runner.analyze(ROOT, PREP, EXEC, RUN / name))
        print('END readonly', name, flush=True)
require(all(n == 0 for n in counters.values()), 'verification.zero_execution')
baseline = members(EXEC / 'analysis')
require(all(members(RUN / n) == baseline for n in ['reanalysis', 'guarded_reanalysis']), 'verification.byte_exact_reanalysis')
require(all(r == read_json((EXEC / 'report.json').read_bytes()) for r in reports), 'verification.report_exact')
implementation = read_json((PREP / 'implementation.json').read_bytes())
verify_source_snapshot(ROOT, implementation)
preservation = validator_preservation(ROOT)
require(preservation == read_json((PREP / 'validator_preservation.json').read_bytes()), 'verification.same_original_validators')
historical = history_inventory(ROOT)
require(historical == read_json((PREP / 'history_inventory.json').read_bytes()), 'verification.old_artifacts_unchanged')
verified = []
for name in ['preparation', 'execution', 'reanalysis', 'guarded_reanalysis']:
    for path in sorted((RUN / name).rglob('manifest.json')):
        files = _Artifacts(path.parent)
        verified.append({'directory': path.parent.relative_to(RUN).as_posix(),
                         'manifest_id': files.manifest['id'], 'member_count': len(files.files)})
architecture = audit_generalization_contract(ROOT / 'trusted_data_synthesis/src')
require(architecture.passed, 'verification.architecture')
store = DurableStore(RUN / 'readonly_verification')
store.write('verify.py', Path(__file__).read_bytes())
store.json('architecture.json', architecture.model_dump(mode='json'))
report = record('action_branch_readonly_verification', execution_report_id=reports[0]['id'],
                source_commit=implementation['source_commit'], source_file_count=len(implementation['members']),
                guards=dict(counters), analysis_runs=2, original_analysis_files=len(baseline),
                original_analysis_bytes=sum(len(v) for v in baseline.values()),
                all_analysis_files_byte_equal=True, unchanged_validator_record_id=preservation['id'],
                old_file_count=len(historical['members']), old_bytes=sum(m['bytes'] for m in historical['members']),
                old_inventory_id=historical['id'], all_old_files_unchanged=True,
                recursive_manifests=verified, architecture_file_count=architecture.scanned_file_count,
                architecture_violation_count=len(architecture.violations), passed=True)
store.json('report.json', report)
seal_directory(store, kind='action_branch_readonly_verification_manifest', report_id=report['id'])
print(json.dumps(report, sort_keys=True), flush=True)
