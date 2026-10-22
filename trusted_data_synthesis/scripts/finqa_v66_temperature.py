"""Original formal loop/identity; only its diagnostic disposition is adapted."""
from __future__ import annotations

from types import FunctionType, SimpleNamespace
import finqa_v66_binding as b
import finqa_v66_diagnostics as diagnostics

original = b.source_module('finqa_v63_temperature')
components = SimpleNamespace(**vars(original.components))
components.DrawAccumulator = diagnostics.DrawAccumulator
components.ComponentCheckpoints = diagnostics.ComponentCheckpoints
namespace = dict(original.feedback_gradient.__globals__, components=components)
_compute = FunctionType(original.feedback_gradient.__code__, namespace,
                        original.feedback_gradient.__name__, original.feedback_gradient.__defaults__)
_compute.__kwdefaults__ = original.feedback_gradient.__kwdefaults__


def feedback_gradient(*args, **kwargs):
    evidence = diagnostics.checked_evidence()
    b.require(kwargs['condition']['id'] == evidence['condition_id'], 'foreign exception feedback condition')
    b.require(b.sha(b.CHECKPOINT / 'record.json') == evidence['checkpoint']['sha256']
              and b.sha(b.CHECKPOINT / 'state.pt') == evidence['checkpoint_state']['sha256'],
              'bound complete830 checkpoint required before entering unchanged formal loop')
    def forbidden_backend(*_args, **_kwargs):
        raise diagnostics.original.DrawDiagnosticError('V66 forbids any new response backend invocation')
    kwargs['backend_factory'] = forbidden_backend
    gradients, report = _compute(*args, **kwargs)
    b.require(report['restored_completed_responses'] == 830
              and report['response_checkpoint_binding']['response_count'] == 830
              and report['draw_components']['mean_check']['passed'] is False
              and report['draw_components']['mean_check']['accepted_by_exception'] is True,
              'recovery must preserve FAIL and restore all830 without new response work')
    return gradients, report


def __getattr__(name):
    return getattr(original, name)
