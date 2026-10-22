"""Only seed389-C05 finish830, original distribution, original298 train."""
from __future__ import annotations

import finqa_v66_binding as b
import finqa_v66_diagnostics as diagnostics
import finqa_v66_runtime as runtime

original = b.source_module('finqa_v63_worker')
_worker = b.private_module('_v66_private_scientific_worker', original.__file__, (
    ('import finqa_v63_runtime as resources', 'import finqa_v66_runtime as resources', 1),
    ('importlib.import_module("finqa_v63_temperature")', 'importlib.import_module("finqa_v66_temperature")', 5),
    ('value["draw_diagnostics_passed"] is True', 'diagnostics.accepted_exception(value)', 1),
    ('replay["draw_diagnostics_passed"] is True', 'diagnostics.accepted_exception(replay)', 1),
    ('replayed_responses=0, completed_payload_reused=True,',
     'restored_completed_responses=report["restored_completed_responses"], replayed_responses=0, completed_payload_reused=True,', 1),
    ('draw_diagnostics_passed=True', 'draw_diagnostics_passed=False, draw_diagnostics_accepted_by_exception=True, diagnostic_exception_id=diagnostics.checked_evidence()["id"]', 3),
))
_worker.diagnostics = diagnostics
_worker.ScientificMonitor = runtime.ScientificMonitor


def run(root, seed, stage, gpu_index, *, attempt_root=None):
    b.scope(_worker.job_spec(seed, stage))
    return _worker.run(root, seed, stage, gpu_index, attempt_root=attempt_root)


def audit_job_resume(root, job):
    b.scope(job)
    return _worker.audit_job_resume(root, job)


def __getattr__(name):
    return getattr(_worker, name)
