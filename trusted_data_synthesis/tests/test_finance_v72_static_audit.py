"""Focused saved-array and joint-observation tests; no model or scoring."""
import copy
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

PATH=Path(__file__).parents[1]/'scripts/finqa_v72_static_audit.py'
spec=importlib.util.spec_from_file_location('v72_static_test',PATH)
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)


class CharacterBackend:
    def encode(self,text,add_special_tokens=False):
        return SimpleNamespace(ids=[ord(x)+1000 for x in text], offsets=[(i,i+1) for i in range(len(text))])
    def decode(self,ids,skip_special_tokens=False):
        return ''.join(chr(x-1000) for x in ids)


def parse(raw,call_prefix):
    start=raw.find('<tool_call>')
    if start<0:return raw,[]
    try:
        value=json.loads(raw[start+11:raw.index('</tool_call>')])
        call=SimpleNamespace(name=value['name'],arguments=value['arguments'])
        return raw[:start],[call]
    except (ValueError,KeyError):return raw,[]


API=SimpleNamespace(parse=parse,decoder=json.JSONDecoder,
                    program_tokens=lambda x:['valid'] if x.startswith('add(') else None)


def row_fixture(action='submit_program',program='add(1, 2)'):
    prompt='<|im_start|>system\ns<|im_end|>\n<|im_start|>user\nu<|im_end|>\n<|im_start|>assistant\n'
    response='R: fact.\n<tool_call>\n'+json.dumps(dict(name=action,arguments={'program':program}))+'\n</tool_call>'
    pc=len(prompt);left=response.index('<tool_call>');layer='final' if action=='submit_program' else 'tool'
    positions={name:[] for name in m.LAYERS}; positions['reason']=list(range(pc,pc+8))
    positions[layer]=list(range(pc+left,pc+len(response)+1))
    intervals={name:[] for name in m.LAYERS};intervals['reason']=[[0,8]];intervals[layer]=[[left,len(response)]]
    ids=[ord(x)+1000 for x in prompt+response]+[9];targets=sorted(p for values in positions.values() for p in values)
    return dict(turn_index=0,row_sha256='row',rendered_prompt=prompt,rendered_response=response,
        input_ids=ids,prompt_token_count=pc,target_positions=targets,target_ids=[ids[p] for p in targets],
        layer_target_positions=positions,response_character_target_intervals=intervals,
        student_eos_appended=True,student_eos_position=len(ids)-1,student_eos_supervised=True)


def inspect(row):return m.audit_row(row,backend=CharacterBackend(),eos=9,stop_ids={9},api=API)


def test_native_submit_envelope_name_arguments_and_eos_are_actual_targets():
    out=inspect(row_fixture())
    assert out['conflicts']==[] and out['positive_action_layer']=='final'
    assert all(x['token_count']==x['supervised'] for x in out['critical_token_coverage'].values())
    assert out['prompt_history_or_role_header_target_count']==0


def test_masking_out_closing_envelope_is_a_concrete_conflict():
    row=row_fixture();p=row['prompt_token_count']+row['rendered_response'].index('</tool_call>')
    row['layer_target_positions']['final'].remove(p);index=row['target_positions'].index(p)
    row['target_positions'].pop(index);row['target_ids'].pop(index)
    codes={x['code'] for x in inspect(row)['conflicts']}
    assert 'critical_action_tokens_not_supervised' in codes
    assert 'actual_mask_differs_from_original_span_union_or_EOS_policy' in codes


def test_current_response_mask_cannot_supervise_prompt_or_tool_history():
    row=row_fixture();row['target_positions'].insert(0,2);row['target_ids'].insert(0,row['input_ids'][2])
    row['layer_target_positions']['reason'].insert(0,2)
    assert 'target_ids_or_causal_response_positions_mismatch' in {x['code'] for x in inspect(row)['conflicts']}


def test_bare_number_final_program_is_not_a_legal_positive_submit_shape():
    result=inspect(row_fixture(program='827'))
    assert 'positive_action_arguments_or_program_shape_conflict' in {x['code'] for x in result['conflicts']}


def test_final_answer_action_cannot_be_promoted_to_valid_terminal_target():
    result=inspect(row_fixture(action='final_answer'))
    assert 'positive_action_is_not_one_valid_native_envelope' in {x['code'] for x in result['conflicts']}


def test_supervised_eos_is_required_for_positive_action():
    row=row_fixture();row['student_eos_supervised']=False
    assert 'actual_mask_differs_from_original_span_union_or_EOS_policy' in {x['code'] for x in inspect(row)['conflicts']}


def native_row(task,state):
    value=dict(status='invalid_prediction',program_executable=False) if state=='I' else dict(
        status='scored',program_executable=True,native={'execution_accuracy':int(state=='R')})
    return dict(task_key=task,native=value)


def test_joint_states_use_actual_rows_not_reconstructible_pairwise_counts():
    reports={name:dict(results=[native_row('t',state)]) for name,state in [('base','R'),('fixed','I'),('Full','W')]}
    value=m.join_states(reports,('base','fixed','Full'))
    assert value['joint_counts']=={'R->I->W':1}
    reports['Full']['results'][0]['task_key']='other'
    with pytest.raises(ValueError,match='ordered task'):m.join_states(reports,('base','fixed','Full'))


def receipt(step,loss,coef='1/20'):
    return dict(step=step,schedule_sha256='schedule',evidence=dict(
        packages=[dict(package_id='p',task_id='t',state_id='z',whole_package_target_tokens=10,target_token_coefficient=coef)],
        package_losses=[dict(package_id='p',target_nll_sum=loss,target_tokens=10)]))


def test_online_loss_aligns_same_package_and_tokens_not_different_weights():
    full=[receipt(895,20,'1/10'),receipt(1044,10,'1/10')]
    fixed=[receipt(895,30,'1/20'),receipt(1044,20,'1/20')]
    result=m.aligned_package_losses({'Full':full,'Fixed':fixed})
    assert result['within_branch_next_epoch_same_package_delta']['Full']['7->8']['mean']==-1
    assert result['between_branch_same_epoch_same_step_mean_target_nll_delta']['7']['mean']==-1
    assert result['raw_package_NLL_not_probability_weighted_training_objective'] is True
    assert result['same_package_same_tokens_different_online_model_states'] is True


def test_online_package_alignment_rejects_task_or_epoch_drift():
    a=[receipt(895,20),receipt(1044,10)];b=copy.deepcopy(a)
    b[1]['evidence']['packages'][0]['task_id']='another'
    with pytest.raises(ValueError,match='semantic identity'):m.aligned_package_losses({'a':a,'b':b})


def test_publication_is_immutable_and_keeps_original_artifacts_outside_scope(tmp_path):
    path=tmp_path/'derived.json';m.publish({'id':'one'},path)
    with pytest.raises(ValueError,match='immutable'):m.publish({'id':'two'},path)
    with pytest.raises(ValueError,match='scratch'):m.publish({'id':'x'},m.V71/'not_authorized.json')
