"""Focused CPU checks for saved-data explanatory statistics, no scientific runs."""
import importlib.util
import math
from pathlib import Path

import pytest

PATH=Path(__file__).parents[1]/'scripts/finqa_v71_mechanism_analysis.py'
spec=importlib.util.spec_from_file_location('v71_mechanism',PATH)
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def test_direction_support_does_not_apply_task_mass_twice():
    result=m.direction_support({'x':{'a':2.,'b':-2.},'y':{'c':0.}},
                               {'x':{'a':.1,'b':-.1},'y':{'c':0.}})
    assert result['score']==pytest.approx(.4)
    assert result['task_mass_multiplied_again'] is False


def test_direction_support_rejects_different_states():
    with pytest.raises(ValueError,match='state support'):
        m.direction_support({'x':{'a':2.}},{'x':{'b':.1}})


def test_weighted_cosine_uses_original_probability_metric():
    result=m.contribution_cosines({'x':{'a':1.,'b':0.}}, {'x':{'a':1.,'b':1.}},
        {'x':{'a':.9,'b':.1}},{'x':1.},set())
    assert result['RMS_metric']['cosine']==pytest.approx(math.sqrt(.9))
    assert result['raw_C_Euclidean']['cosine']==pytest.approx(1/math.sqrt(2))


def test_zero_norm_cosine_is_not_successful_agreement():
    result=m.contribution_cosines({'x':{'a':0.}}, {'x':{'a':1.}},
                                  {'x':{'a':1.}},{'x':1.},set())
    assert result['RMS_metric']['cosine'] is None
    assert result['RMS_metric']['status']=='UNDEFINED_ZERO_NORM'


def test_nominal_coefficients_use_actual_tail_batch_and_package_denominator():
    packages={}; receipts=[]; pi={}
    for batch_size in (5,4):
        receipt=dict(evidence=dict(batch_size=batch_size,task_batch=dict(task_ids=[]),packages=[]))
        for index in range(batch_size):
            task=f'{batch_size}.{index}';pi[task]={'s':1.}
            receipt['evidence']['task_batch']['task_ids'].append(task)
            # Two packages of unequal length: equal package mass; token-count
            # pooling would incorrectly make the final layer dominate.
            for suffix,lp,layer in (('a',10,'reason'),('b',90,'final')):
                sid=task+suffix
                package=dict(task_id=task,state_id='s',package_id=sid,n_state=2,
                             whole_package_target_tokens=lp,target_token_coefficient=1/(batch_size*2*lp))
                receipt['evidence']['packages'].append(package)
                packages[sid]=dict(**package,layer_target_counts={k:lp if k==layer else 0 for k in m.LAYERS},
                                   action_sequence='submit_program')
        receipts.append(receipt)
    result=m.nominal_window(receipts,pi,packages,compare_actual=True)
    assert result['total_nominal_supervision_coefficient']==pytest.approx(2.)
    assert result['layer_shares']==pytest.approx(dict(reason=.5,tool=0.,final=.5))
    assert result['tail_batch_sizes']=={4:1,5:1}
    assert result['task_exposures']==9


def test_encoding_layers_include_registered_eos_and_saved_action_structure():
    package=dict(package_id='P',task_id='T',state_id='S',n_state=1,whole_package_target_tokens=3)
    encoding=dict(slot_id='P',task_id='T',L_P=3,layer_target_counts=dict(reason=1,tool=0,final=2),
        total_sequence_tokens=30,max_sequence_tokens=30,rows=[dict(
            layer_target_positions=dict(reason=[1],tool=[],final=[2,3]),target_ids=[8,9,10],
            student_eos_supervised=True,
            rendered_response='<tool_call>{"name":"submit_program","arguments":{"program":"add(1,2)"}}</tool_call>')])
    result=m.encoding_features(encoding,package)
    assert result['layer_token_fraction']['final']==pytest.approx(2/3)
    assert result['supervised_EOS']==1
    assert result['terminal_action']=='submit_program'
    assert result['terminal_argument_keys']==['program']


def test_second_window_refresh_and_control_difference_are_distinct():
    pi0={'x':{'a':.2,'b':.8}};q1={'x':{'a':.4,'b':.6}};q2={'x':{'a':.5,'b':.5}}
    assert m.delta_distribution(q2,q1)['x']['a']==pytest.approx(.1)
    assert m.delta_distribution(q2,pi0)['x']['a']==pytest.approx(.3)


def test_saved_training_dynamics_uses_actual_package_loss_coefficients():
    rows=[dict(step=895,evidence=dict(batch_size=1,packages=[dict(package_id='p',target_token_coefficient=.1)],
        package_losses=[dict(package_id='p',target_nll_sum=20)],preclip_gradient_norm=1.2,
        target_tokens=10,sequence_tokens=100))]
    result=m.training_dynamics(rows)
    assert result['weighted_package_NLL']['mean']==2.
    assert result['clipping_threshold_exceeded_updates']==1
    assert result['layerwise_loss_and_gradient_contribution_saved'] is False
