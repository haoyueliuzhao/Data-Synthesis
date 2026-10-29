"""One CPU-only V75 summary repair and actual-demo source-overlap analysis.

Reads already sealed native scores and materials. No scorer, model, Tensor,
raw episode, new bootstrap or historical mutable status writer is reachable.
"""
from __future__ import annotations
from collections import Counter
import hashlib
import json
from pathlib import Path
import finqa_v76_binding as binding

require=binding.require


class Reader:
    def __init__(self):self.sources={};self.cache={}
    def read(self,path,reference=None):
        path=Path(path).resolve()
        if path not in self.cache:
            raw=path.read_bytes();value=json.loads(raw)
            if 'id' in value:
                require(value['id']==binding.digest({k:v for k,v in value.items() if k!='id'}),
                        'immutable CPU preparation input changed: '+str(path))
            self.cache[path]=value
            self.sources[str(path)]=dict(path=str(path),sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw),id=value.get('id'))
        if reference is not None:
            source=self.sources[str(path)]
            require(source['sha256']==reference['sha256'] and ('id' not in reference or source['id']==reference['id']),
                    'CPU source reference differs: '+str(path))
        return self.cache[path]
    def ref(self,path):self.read(path);return self.sources[str(Path(path).resolve())]
    def bound(self,reference):return self.read(reference['path'],reference)
    def raw(self,path,sha256,byte_count=None):
        path=Path(path).resolve();raw=path.read_bytes()
        require(hashlib.sha256(raw).hexdigest()==sha256 and (byte_count is None or len(raw)==byte_count),
                'bound source bytes differ: '+str(path))
        self.sources[str(path)]=dict(path=str(path),sha256=sha256,bytes=len(raw),kind='lineage_or_log_bytes')
        return raw


def _same_reference(left,right):
    return Path(left['path']).resolve()==Path(right['path']).resolve() and left['sha256']==right['sha256']


def _revision_contract(materials,completed,native,previous_analysis):
    """Repair only the missing field interface; assert actual consumption."""
    actual=completed['actual_demonstration_consumption'];planned=materials['dose']
    require(completed['status']=='COMPLETE' and completed['initial_step']==1192 and completed['final_step']==1490
        and completed['optimizer_updates']==298 and completed['outer_updates']==0
        and completed['learning_rate']==1e-5 and completed['outer_done']==[298],
        'V75 real fixed-mixture training must be complete')
    require(actual['material_id']==materials['id'] and actual['status']=='PASS'
        and actual['all298_actual_receipts_match_frozen_slots'] is True
        and actual['updates']==planned['updates']==298 and actual['task_exposures']==planned['task_exposures']==1488
        and actual['student_prefix_target_count']==0,'V75 actual consumption binding differs')
    for actual_key,planned_key in (('teacher_target_tokens','planned_teacher_target_tokens'),
                                 ('teacher_input_positions','planned_teacher_input_positions'),
                                 ('teacher_microbatches','planned_teacher_microbatches')):
        require(actual[actual_key]==sum(planned[planned_key].values()),'actual/planned teacher consumption differs')
    require(native['status']=='COMPLETE' and native['denominator']==len(native['results'])==883
        and native['metrics']['execution_accuracy']['correct']==557
        and all(native['metrics'][metric]['unknown']==0 for metric in ('execution_accuracy','program_accuracy')),
        'V75 complete native evaluation required without rescoring')
    require(previous_analysis['native_metrics']['S']==native['metrics'],
            'existing report analysis differs from original sealed scores')
    return dict(planned_demonstration_dose=planned,actual_demonstration_consumption=actual,
        repaired_field_source='planned <- materials.dose; actual <- training.actual_demonstration_consumption',
        read_missing_completed_field=False,original_V75_exception='KeyError: planned_demonstration_dose',
        new_optimizer_updates=0,new_model_calls=0,new_tool_calls=0,new_native_scores=0,
        new_bootstrap_runs=0,Tensor_reads=0,raw_episode_reads=0)


def _source_rows(reports,lineages):
    tasks=[r['original_task_key'] for r in reports['S']['results']]
    require(len(tasks)==len(set(tasks))==883,'V75 complete original task order required')
    for label,report in reports.items():
        require(report['denominator']==883 and [r['original_task_key'] for r in report['results']]==tasks,
                'V75 reference task order differs: '+label)
        for row in report['results']:
            lineage=lineages[row['original_task_key']]
            require(row['source_group']==dict(group=lineage['source_group'],level=lineage['source_group_level']),
                    'native score group differs from the real frozen lineage')
    return tasks


def summarize_slice(reports,indices,*,stats,previous):
    n=len(indices)
    rows={label:[report['results'][i] for i in indices] for label,report in reports.items()}
    if not n:
        return dict(denominator=0,status='NA_EMPTY_SLICE',native_metrics=None,paired=None,no_call=None,task_keys=[])
    return dict(denominator=n,status='COMPLETE',native_metrics={k:stats.native_metrics(v,n) for k,v in rows.items()},
        paired={f'S-{label}':previous.paired_metrics(rows['S'],rows[label],n,stats=stats) for label in ('B','P')},
        no_call={k:previous.no_call_summary(v,n) for k,v in rows.items()},
        task_keys=[row['original_task_key'] for row in rows['S']],
        descriptive_posthoc=True,independent_validation=False)


def actual_source_strata(*,reports,materials,completed,inputs,support,lineages,selection,stats,previous):
    actual=completed['actual_demonstration_consumption']
    require(actual['all298_actual_receipts_match_frozen_slots'] is True and actual['status']=='PASS',
            'actual training consumption must cover all registered V75 batches')
    tasks=_source_rows(reports,lineages)
    exposures=materials['dose']['selected_task_exposures']
    consumed={task for task,row in materials['tasks'].items() if any(row['slots'].values()) and exposures[task]>0}
    slot_counts={slot:sum(materials['tasks'][task]['slots'][slot] is not None for task in consumed)
                 for slot in ('initial','post')}
    actual_exposures={slot:sum(exposures[task] for task in consumed if materials['tasks'][task]['slots'][slot] is not None)
                     for slot in ('initial','post')}
    require(len(consumed)==111 and slot_counts==dict(initial=101,post=78)
        and actual_exposures==actual['teacher_trajectory_exposures_by_slot']
        and sum(actual_exposures.values())==actual['teacher_trajectories']==358,
        'actual consumed teacher support differs from V75')
    selected={row['task_id']:row for row in inputs['tasks']}
    require(consumed<=set(selected) and len(selected)==128,'consumed support escaped fixed128')
    for task in consumed:
        lineage=lineages['finqa/'+task]
        require(binding.digest(lineage)==selected[task]['lineage_sha256']
            and lineage==inputs['lineages']['finqa/'+task], 'teacher source lineage binding changed')
    old_tasks=support['training_task_ids']
    require(len(old_tasks)==len(set(old_tasks))==744 and consumed<=set(old_tasks),
            'original744 support or teacher membership changed')
    output={}
    for level,field in (('report','source_group'),('company','company')):
        new_sources={lineages['finqa/'+task][field] for task in consumed}
        old_sources={lineages['finqa/'+task][field] for task in old_tasks}
        require(new_sources<=old_sources,'teacher source outside the original train support')
        groups={key:[] for key in ('shared_actual_demo','shared_old_only','no_explicit_train_overlap')}
        for ordinal,task in enumerate(tasks):
            source=lineages[task][field]
            key='shared_actual_demo' if source in new_sources else 'shared_old_only' if source in old_sources else 'no_explicit_train_overlap'
            groups[key].append(ordinal)
        require(sorted(i for values in groups.values() for i in values)==list(range(883)),
                'source slices must be disjoint and exhaustive')
        dev_sources={lineages[task][field] for task in tasks}
        output[level]=dict(level=level,source_field=field,
            actual_demo_source_count=len(new_sources),old_train_source_count=len(old_sources),
            actual_demo_dev_overlap=sorted(new_sources&dev_sources),
            old_train_dev_overlap=sorted(old_sources&dev_sources),
            slices={key:summarize_slice(reports,indices,stats=stats,previous=previous) for key,indices in groups.items()},
            report_nonoverlap_is_company_nonoverlap=False,unseen_confirmation=False)
    chosen={row['original_task_key'] for row in selection['selected']}
    require(len(chosen)==96 and chosen<=set(tasks),'original96 mechanism selection changed')
    complement=[i for i,task in enumerate(tasks) if task not in chosen]
    require(len(complement)==787,'old96 complement denominator differs')
    return dict(schema='v76_readonly_V75_actual_consumed_source_stratification.v1',status='COMPLETE',
        full_denominator=883,actual_demo_tasks=len(consumed),actual_demo_slots=slot_counts,
        actual_demo_trajectory_exposures=actual_exposures,selected_but_no_demo_tasks=128-len(consumed),
        partitions=output,old96_complement=summarize_slice(reports,complement,stats=stats,previous=previous),
        primary883_not_replaced=True,posthoc_not_independent_validation=True,
        new_model_calls=0,new_native_scores=0,new_bootstrap_runs=0,
        reported_overlap_based_on_consumed_support_not_preselection=True)


def prepare(root=None):
    root=binding.ROOT if root is None else Path(root)
    require(root.resolve()==binding.ROOT.resolve(),'V76 CPU preparation output escaped its root')
    revision_path=root/'v75_cpu_revision/record.json';strata_path=root/'source_overlap/record.json'
    if revision_path.exists() or strata_path.exists():
        require(revision_path.exists() and strata_path.exists(),'incomplete one-shot CPU preparation cannot be auto-retried')
        revision=binding.checked(revision_path)
        protocol=binding.read_ref(revision['references']['original_protocol'])
        return dict(v75_cpu_revision=binding.entry(revision_path),source_overlap=binding.entry(strata_path),
            reused_evaluation={'S':revision['references']['native_scores'],**protocol['reused_evaluation']},
            evaluation_source_registration=protocol['evaluation_source_registration'],
            demonstration_materials=revision['references']['materials'],original_parent=protocol['initial_parent'],
            new_model_calls=0,new_native_scores=0)
    reader=Reader();old=binding.V75_ROOT
    protocol=reader.read(old/'protocol/record.json');close=reader.read(old/'closeout/record.json')
    require(close['status']=='STOPPED_FAILURE_NO_RETRY' and close['protocol_id']==protocol['id']
        and close['active_workers']==0,'original V75 failure must remain sealed')
    require(not (old/'evaluations/final_summary/record.json').exists(),'old formal failed summary must not be overwritten')
    native=reader.read(old/'evaluations/native_scores/record.json')
    materials=reader.read(old/'materials/record.json');completed=reader.read(old/'points/step1192/train/completed/record.json')
    train=reader.read(old/'points/step1192/train/result/record.json')
    require(train['protocol_id']==completed['protocol_id']==materials['protocol_id']==native['protocol_id']==protocol['id']
        and _same_reference(completed['demonstration_materials'],reader.ref(old/'materials/record.json'))
        and _same_reference(train['branch_result'],reader.ref(old/'points/step1192/train/completed/record.json'))
        and train['actual_demonstration_consumption']==completed['actual_demonstration_consumption'],
        'V75 material/training/native scientific bindings changed')
    barrier=reader.read(old/'all_jobs_exit_barrier/record.json')
    require(barrier['protocol_id']==protocol['id'] and barrier['active_workers']==[]
        and set(barrier['actual_exits'])==set(barrier['accepted_jobs'])==set(protocol['jobs'])
        and _same_reference(native['all_jobs_exit_barrier'],reader.ref(old/'all_jobs_exit_barrier/record.json')),'all V75 GPU jobs must have exited before saved scoring')
    for key in protocol['jobs']:
        accepted=reader.bound(barrier['accepted_jobs'][key]);actual=reader.bound(barrier['actual_exits'][key])
        result=reader.bound(accepted['result'])
        launch=reader.read(Path(barrier['actual_exits'][key]['path']).parent.parent/'launch/record.json')
        require(accepted['actual_exit']==barrier['actual_exits'][key]
            and accepted['actual_exit_zero'] is True and accepted['resources_passed'] is True
            and actual['actual_waitpid_observed'] is True and actual['returncode']==0
            and result['id']==accepted['result_id'] and result['resources']['all_gates_passed'] is True
            and (actual['pid'],actual['birth'])==(launch['pid'],launch['birth'])
            and accepted['protocol_id']==actual['protocol_id']==result['protocol_id']==launch['protocol_id']==protocol['id'],
            'V75 actual GPU exit/accepted-result binding differs: '+key)
    finalexit=reader.read(old/'final_analysis/attempt0001/actual_exit/record.json')
    finalresource=reader.read(old/'final_analysis/attempt0001/resources/closeout/record.json')
    require(finalexit['actual_waitpid_observed'] is True and finalexit['returncode']==1
        and finalresource['all_gates_passed'] is True and finalresource['CUDA_initialized'] is False,
        'V75 CPU software failure evidence differs')
    paired=reader.read(old/'report_derivation_20261028/paired_analysis.json')
    analysis=paired['analysis']
    require(any(_same_reference(source,reader.ref(old/'evaluations/native_scores/record.json')) for source in paired['sources']),
            'existing paired analysis does not bind the original native scores')
    revision=_revision_contract(materials,completed,native,analysis)
    old_reports={label:reader.bound(protocol['reused_evaluation'][label]) for label in ('B','P')}
    reports=dict(S=native,**old_reports)
    inputs=reader.bound(protocol['inputs']);support=reader.bound(inputs['support_manifest'])
    selection=reader.bound(protocol['mechanism_selection'])
    manifest=reader.bound(inputs['public_snapshot']['manifest'])
    member=manifest['files']['lineage.jsonl'];lineage_path=Path(inputs['public_snapshot']['path'])/'lineage.jsonl'
    raw=reader.raw(lineage_path,member['sha256'],member['bytes'])
    lineages={}
    for line in raw.splitlines():
        if line.strip():
            row=json.loads(line);key=f"{row['dataset']}/{row['original_id']}"
            require(key not in lineages,'duplicate original lineage task');lineages[key]=row
    from finqa_v76_analysis import _stats
    stats=_stats();previous=binding.source_v75('analysis')
    strata=actual_source_strata(reports=reports,materials=materials,completed=completed,inputs=inputs,
        support=support,lineages=lineages,selection=selection,stats=stats,previous=previous)
    # Both results are fully computed before either immutable publication.
    references=dict(original_protocol=reader.ref(old/'protocol/record.json'),
        original_failed_closeout=reader.ref(old/'closeout/record.json'),
        native_scores=reader.ref(old/'evaluations/native_scores/record.json'),
        all_GPU_exit_barrier=reader.ref(old/'all_jobs_exit_barrier/record.json'),
        failed_final_CPU_exit=reader.ref(old/'final_analysis/attempt0001/actual_exit/record.json'),
        materials=reader.ref(old/'materials/record.json'),
        training_completed=reader.ref(old/'points/step1192/train/completed/record.json'),
        reused_report_analysis=reader.ref(old/'report_derivation_20261028/paired_analysis.json'))
    binding.publish(revision_path,dict(revision,schema='v76_independent_V75_CPU_summary_revision.v1',
        status='COMPLETE_REVISED_SUMMARY',references=references,analysis=analysis,
        original_scientific_status='STOPPED_FAILURE_NO_RETRY',original_final_CPU_exitcode=1,
        original_records_changed=False,scientific_work_reexecuted=False,
        successful_revision_CPU_exit_to_be_accepted_separately=True))
    binding.publish(strata_path,dict(strata,revision=binding.entry(revision_path),
        source_records=list(reader.sources.values())))
    return dict(v75_cpu_revision=binding.entry(revision_path),source_overlap=binding.entry(strata_path),
        reused_evaluation={'S':reader.ref(old/'evaluations/native_scores/record.json'),**protocol['reused_evaluation']},
        evaluation_source_registration=protocol['evaluation_source_registration'],
        demonstration_materials=reader.ref(old/'materials/record.json'),
        original_parent=protocol['initial_parent'],new_model_calls=0,new_native_scores=0)
