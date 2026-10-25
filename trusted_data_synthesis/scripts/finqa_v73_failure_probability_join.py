"""Read-only posthoc join of sealed V73 hP action-loss and probability records."""
import hashlib
import json
import statistics
from pathlib import Path

ROOT = Path('/data1/zhuxinrui/projects/Data-Synthesis/trusted_data_synthesis/artifacts/finance_research_20260928/finqa_v6_01/v18_researcher_continuation_01/v73_same_context_probe_01/execution_revision_02')
GROUPS = ('action_structure','pre_action_text','program_parameter_content','actual_terminal_EOS')

def digest(v):
    return hashlib.sha256(json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()

cache, refs = {}, {}
def read(path, expected=None):
    path = Path(path).resolve()
    if str(path) not in cache:
        raw = path.read_bytes(); value = json.loads(raw)
        ref = {'path':str(path),'sha256':hashlib.sha256(raw).hexdigest(),'id':value['id']}
        assert value['id'] == digest({k:v for k,v in value.items() if k!='id'}), str(path)
        cache[str(path)],refs[str(path)] = value,ref
    if expected:
        assert refs[str(path)] == expected, str(path)
    return cache[str(path)]

protocol = read(ROOT/'protocol/record.json')
final = read(ROOT/'final_summary/record.json')
assert final['status']=='COMPLETE' and final['protocol_id']==protocol['id']
assert final['input_ref']==protocol['inputs']
bundle=read(protocol['inputs']['path'],protocol['inputs'])
tasks=bundle['logical_rows']
assert len(tasks)==96 and {g:sum(r['group']==g for r in tasks) for g in ('F','K')}=={'F':48,'K':48}

locations={}
for job_id,job in protocol['jobs'].items():
    for key in job['context_ids']:
        identity=('generation',job['model'],key)
        assert identity not in locations
        locations[identity]=ROOT/'jobs'/job_id/'outputs/generation'/key/'result.json'
    for key in job['target_keys']:
        identity=('probability',job['model'],key)
        assert identity not in locations
        locations[identity]=ROOT/'jobs'/job_id/'outputs/probability'/digest(key)/'result.json'

def output(kind,model,key):
    path=locations[kind,model,key]
    row=read(path)
    assert (row['kind'],row['model'],row['key'],row['protocol_id'])==(kind,model,key,protocol['id'])
    return row,refs[str(path.resolve())]

joined=[]; summaries={}; skipped=[]
for group in ('F','K'):
    summaries[group]={}
    for model in ('H','L'):
        expected=final['panels'][group]['primary_hP_paired_models'][model+'_minus_P']['A']['lost']
        assert final['panels'][group]['primary_hP_paired_models'][model+'_minus_P']['known_pair_count']==48
        rows=[]
        if expected==0:
            skipped.append({'group':group,'model':model,'reason':'sealed complete 48-task pairing reports zero A losses; no generation scan needed'})
        else:
            for task in [r for r in tasks if r['group']==group]:
                context=task['contexts']['P']; assert context is not None
                candidate,gen_c_ref=output('generation',model,context)
                if candidate['classification']['A']!=0:
                    continue
                parent,gen_p_ref=output('generation','P',context)
                if parent['classification']['A']!=1:
                    continue
                p,prob_p_ref=output('probability','P',task['task_key'])
                c,prob_c_ref=output('probability',model,task['task_key'])
                pm,cm=p['measurement'],c['measurement']
                assert pm['grouping_id']==cm['grouping_id']
                differences={}
                for name in GROUPS:
                    a,b=pm['groups'][name],cm['groups'][name]
                    assert a['token_count']==b['token_count']
                    known=a['token_count']>0
                    if not known:
                        assert a['mean_nll'] is None and b['mean_nll'] is None
                    differences[name]={'token_count':a['token_count'],'parent_mean_nll':a['mean_nll'],
                        'candidate_mean_nll':b['mean_nll'],
                        'candidate_minus_parent_mean_nll':b['mean_nll']-a['mean_nll'] if known else None,
                        'status':'MEASURED' if known else 'NA'}
                value={'group':group,'model':model,'reference_model':'P','task_key':task['task_key'],
                    'context_source':'P','context_id':context,'parent_classification':parent['classification'],
                    'candidate_classification':candidate['classification'],
                    'parent_completion':parent['completion'],'candidate_completion':candidate['completion'],
                    'fixed_parent_target_grouping_id':pm['grouping_id'],'NLL':differences,
                    'source_refs':{'parent_generation':gen_p_ref,'candidate_generation':gen_c_ref,
                        'parent_probability':prob_p_ref,'candidate_probability':prob_c_ref}}
                rows.append(value)
        assert len(rows)==expected, (group,model,len(rows),expected)
        joined.extend(rows)
        summary={'full_group_denominator':48,'posthoc_A_loss_count':len(rows),'probability_group_deltas':{}}
        for name in GROUPS:
            values=[r['NLL'][name]['candidate_minus_parent_mean_nll'] for r in rows if r['NLL'][name]['status']=='MEASURED']
            summary['probability_group_deltas'][name]={'measured_pairs':len(values),'NA_pairs':len(rows)-len(values),
                'positive_count':sum(v>0 for v in values),'negative_count':sum(v<0 for v in values),'exact_zero_count':sum(v==0 for v in values),
                'mean_delta':statistics.fmean(values) if values else None,
                'median_delta':statistics.median(values) if values else None,
                'minimum_delta':min(values) if values else None,'maximum_delta':max(values) if values else None}
        summaries[group][model]=summary

out={'schema':'v73_posthoc_hP_A_loss_fixed_parent_probability_join.v1','status':'COMPLETE',
    'protocol_id':protocol['id'],'final_summary_id':final['id'],'actual_root':str(ROOT),
    'scope':{'subset_condition':'new same-hP generation P A=1 and candidate H/L A=0',
        'posthoc_descriptive_subset':True,'not_preregistered_independent_test':True,
        'new_significance_tests':0,'new_model_calls':0,'new_native_scores':0,'original_records_written':0,
        'raw_episodes_or_Tensors_opened':False,'new_probability_measurements':0,
        'positive_delta_means_worse_fit_to_same_saved_parent_expression':True,
        'not_all_legal_expressions_or_unique_root_cause':True,'no_delta_tolerance_added':True},
    'rows':joined,'summaries':summaries,'skipped_zero_loss_panels':skipped,
    'source_JSON_count':len(refs),'sources':list(refs.values()),
    'analysis_script':{'path':str(Path(__file__).resolve()),'sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}}
out['id']=digest(out)
target=Path('/tmp/v73_failure_probability_join.json')
with target.open('x') as stream:
    json.dump(out,stream,ensure_ascii=False,sort_keys=True,indent=2);stream.write('\n')
print(json.dumps({'id':out['id'],'source_JSON_count':len(refs),'rows':len(joined),'summaries':summaries},ensure_ascii=False))
for r in joined:
    print(json.dumps({'group':r['group'],'model':r['model'],'task_key':r['task_key'],
        'category':r['candidate_classification']['category'],'completion':r['candidate_completion'],
        'deltas':{k:v['candidate_minus_parent_mean_nll'] for k,v in r['NLL'].items()}},ensure_ascii=False))
