"""Read-only exact CPU evidence and narrowly scoped FAIL disposition."""
from __future__ import annotations

import io
import time

import finqa_v66_binding as b

b.source_module('finqa_v63_binding').install_scientific_paths()
original = b.source_module('finqa_v63_draw_components')
torch = original.torch


def compare_values(formal, draws, tolerances):
    original.checked_tolerances(tolerances)
    passed, maximum, squared, reference_squared, elements = True, 0.0, 0.0, 0.0, 0
    failed = []
    for name, tensor in formal.items():
        reference = tensor.detach().to('cpu')
        mean = (draws[101][name] + draws[103][name]) * 0.5
        delta = mean.to(torch.float64) - reference.to(torch.float64)
        maximum = max(maximum, float(delta.abs().max()) if delta.numel() else 0.0)
        squared += float(delta.square().sum())
        reference_squared += float(reference.to(torch.float64).square().sum())
        same = torch.isclose(mean, reference, atol=tolerances['atol'], rtol=tolerances['rtol'])
        passed &= bool(same.all())
        elements += reference.numel()
        for index in (~same).flatten().nonzero().flatten().tolist():
            value = float(reference.flatten()[index])
            failed.append(dict(parameter=name, flat_index=index, shape=list(reference.shape),
                formal=value, draw101=float(draws[101][name].flatten()[index]),
                draw103=float(draws[103][name].flatten()[index]),
                mean=float(mean.flatten()[index]), absolute_error=float(delta.flatten()[index].abs()),
                registered_threshold=tolerances['atol'] + tolerances['rtol'] * abs(value)))
    return dict(passed=passed, **tolerances, maximum_absolute_error=maximum,
        L2_error=squared ** 0.5,
        relative_L2_error=(squared / reference_squared) ** 0.5 if reference_squared else None,
        reference_L2_norm=reference_squared ** 0.5,
        source_is_CPU_gradient_comparison_not_old_production_bitwise_gate=True,
        formal_gradient_replaced_by_component_mean=False,
        parameter_count=len(formal), element_count=elements, failed_element_count=len(failed),
        failing_elements=failed)


def cpu_evidence():
    record = b.checked(b.CHECKPOINT / 'record.json')
    failure = b.checked(b.FAILURE)
    raw = (b.CHECKPOINT / 'state.pt').read_bytes()
    b.require(b.sha(b.CHECKPOINT / 'state.pt') == record['state_sha256'], 'saved checkpoint SHA changed')
    state = torch.load(io.BytesIO(raw), map_location='cpu', weights_only=False)
    b.require(state['cursor'] == record['cursor'] == record['binding']['response_count'] == 830
              and state['binding'] == record['binding'] and record['full_replay_complete'] is True
              and original.original._tree_digest(state) == record['state_digest'],
              'exception requires the actual complete atomic response830 checkpoint')
    components = state['draw_components']
    b.require(components['condition_id'] == record['binding']['backend_identity']['feedback_condition_id']
              and components['cursor'] == 830 and components['formal_denominator'] == 700
              and components['draw_denominator'] == 350, 'diagnostic checkpoint condition changed')
    report = compare_values(state['total'], components['draws'], components['mean_tolerances'])
    b.require(report['passed'] is False and report['failed_element_count'] == 1
              and report['parameter_count'] == 112 and report['element_count'] == 2523136,
              'the explicitly diagnosed one-element failure changed')
    item = report['failing_elements'][0]
    b.require(item['parameter'] == 'model.layers.17.self_attn.v_proj.lora_B'
              and item['flat_index'] == 73 and item['shape'] == [512, 8],
              'exception cannot cover another failed coordinate')
    return dict(schema='v66_readonly_exact_single_failure_CPU_evidence.v1', status='FAIL',
        checkpoint=b.entry(b.CHECKPOINT / 'record.json'), checkpoint_state=b.file_ref(b.CHECKPOINT / 'state.pt'),
        state_bytes=len(raw), checkpoint_binding_digest=b.digest(state['binding']),
        condition_id=components['condition_id'], point_id=state['binding']['point_id'],
        completed_responses=830, new_response_replays=0, original_failure=b.entry(b.FAILURE),
        formal_digest=original.original.parameter_digest(state['total']),
        draw_digests={str(seed): original.original.parameter_digest(value) for seed, value in components['draws'].items()},
        report=report, formal_gradient_replaced=False, tolerance_changed=False,
        cause_established=False,
        interpretation='Observed opposite-sign draw components are consistent with floating-point cancellation; cause not proved.')


def checked_evidence():
    import finqa_v66_registration as registration
    protocol = registration.checked_protocol()
    return b.read_ref(protocol['diagnostic_evidence'])


def accepted_exception(value):
    evidence = checked_evidence()
    return (value.get('draw_diagnostics_passed') is False
            and value.get('draw_diagnostics_accepted_by_exception') is True
            and value.get('diagnostic_exception_id') == evidence['id'])


class DrawAccumulator(original.DrawAccumulator):
    def compare(self, formal):
        self.observe('before_draw_component_mean_check')
        began = time.monotonic()
        report = compare_values(formal, self.draws, self.tolerances)
        self.mean_check_seconds_this_process += time.monotonic() - began
        self.observe('after_draw_component_mean_check')
        if report['passed']:
            return report
        evidence = checked_evidence()
        original.require(self.cursor == 830 and len(self.work) == 830 and self.denominator == 700
            and self.condition_id == evidence['condition_id']
            and original.original.parameter_digest(formal) == evidence['formal_digest']
            and {str(seed): original.original.parameter_digest(value) for seed, value in self.draws.items()}
                == evidence['draw_digests']
            and all(report[key] == evidence['report'][key] for key in
                ('passed', 'atol', 'rtol', 'maximum_absolute_error', 'parameter_count',
                 'element_count', 'failed_element_count', 'failing_elements')),
            'unregistered diagnostic failure: the response830 single-point exception does not apply')
        return dict(report, status='FAIL', accepted_by_exception=True,
                    diagnostic_exception_id=evidence['id'], original_failure=evidence['original_failure'])


class ComponentCheckpoints(original.ComponentCheckpoints):
    def read(self, directory):
        from pathlib import Path
        evidence = checked_evidence()
        original.require(Path(directory).resolve() == b.CHECKPOINT
            and b.sha(Path(directory) / 'record.json') == evidence['checkpoint']['sha256']
            and b.sha(Path(directory) / 'state.pt') == evidence['checkpoint_state']['sha256'],
            'V66 may restore only the bound original complete response830 checkpoint')
        return super().read(directory)

    def save(self, cursor, total, accounting, *, complete=False):
        # A legal stop already at830 asks the original loop to commit its same
        # boundary. Return that immutable original after exact validation; never
        # rewrite timestamps, RNG, gradient tensors or the historical record.
        record, state = self.read(b.CHECKPOINT)
        original.require(cursor == self.accumulator.cursor == 830 and complete is True
            and accounting == state['accounting']
            and original.original.parameter_digest(total) == original.original.parameter_digest(state['total']),
            'V66 does not authorize any new or changed response checkpoint')
        return record
