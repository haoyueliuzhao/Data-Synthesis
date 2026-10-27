"""Candidate-only autonomous dev883 generation and all-exits-gated native scoring.

Two fixed disjoint generation shards change scheduling only. The merged native
883-task scorer, harness, greedy parameters and original task order are retained.
"""
from __future__ import annotations
import asyncio
import gc
import importlib
from pathlib import Path
import finqa_v75_binding as binding

require,checked,publish=binding.require,binding.checked,binding.publish
GREEDY_SEED=20260928
ARM='StateDemo1192'
CONDITION='state_demonstration_from_fixed1192'


def _original():
    return binding.source_module('finqa_v63_evaluation')


def _runtime():
    return _original()._runtime()


def panel_config(role='development'):
    require(role=='development','only the original dev883 greedy panel is authorized')
    return dict(harness_id='bigfinance-derived-vtdo-v7',submission_profile='finqa-public-reasoning-v2',
        local_tool_protocol='qwen2.5-native-tool-call-v1',max_steps=32,max_new_tokens=2048,
        context_limit=24576,temperature=0.0,top_p=1.0,top_k=0,seed=GREEDY_SEED,
        tier='EVAL_NATIVE',role='development',api_model='deepseek-flash')


def planned_jobs():
    jobs={}
    for shard,n in ((0,442),(1,441)):
        key=f'step1490.dev_greedy.shard{shard}'
        jobs[key]=dict(job_id=key,id=key,kind='generate',memory_phase='generate',stage='generate',
            seed=137,arm=ARM,step=1490,role='development',algorithm=CONDITION,
            denominator=n,full_denominator=883,draw_seed=GREEDY_SEED,panel=key,
            shard=shard,shards=2,config=panel_config())
    return jobs


def evaluation_contract():
    analysis=importlib.import_module('finqa_v75_analysis')
    return dict(schema='v75_candidate_only_autonomous_dev_evaluation.v1',jobs=planned_jobs(),
        total_sessions=883,new_generation_shards=2,shard_assignment='original dev883 ordinal modulo2',
        new_model_conditions=1,new_model_call_cap=28256,final_endpoint=1490,
        generation_starts_from_initial_public_request=True,teacher_history_supplied=False,
        reused_control=dict(source='V72',step=1490,EA_correct=431,new_sessions=0,new_scores=0),
        reused_parent=dict(source='V71Fixed1192 evaluated in V72',step=1192,EA_correct=536,new_sessions=0,new_scores=0),
        original_894_525_used_as_parent=False,calibration_sessions=0,test_sessions=0,
        stochastic_evaluation=False,old96_extra_generations=0,intermediate_evaluation=False,
        original_native_harness_and_metric_sources_unchanged=True,
        original_native_failure_rules_unchanged=True,greedy_config=panel_config(),
        before_generation='candidate298updates complete and train actual accepted exit0',
        before_private_scoring='all collection,materials,train,and both dev shards accepted actual exit0; no live GPU workers',
        canonical_episode_encoding='native Episode.model_dump(mode=json)',
        complete_returns_never_regenerated=True,unknown_call_auto_retry=False,
        UNKNOWN_as_zero=False,full_denominator=883,statistics=analysis.statistics_contract(),
        no_adaptive_outer_updates=True,no_new_Contribution_or_VJP=True,
        reused_baseline_is_new_independent_replication=False,
        equal_step_count_implies_equal_compute=False,dropout_random_streams_remain_paired=False,
        automatic_followup=False,automatic_Full_resume=False)


def canonical_episode_payload(episode):
    value=episode if isinstance(episode,dict) else episode.model_dump(mode='json')
    require(isinstance(value,dict),'native Episode must serialize to an object')
    return value


def canonical_episode_hash(episode):
    return binding.digest(canonical_episode_payload(episode))


def _protocol(root):
    require(Path(root).resolve()==binding.ROOT.resolve(),'foreign V75 evaluation root')
    protocol=checked(Path(root)/'protocol/record.json')
    require(protocol['evaluation']==evaluation_contract(),'frozen candidate evaluation contract changed')
    return protocol


def _job(job):
    jobs=planned_jobs()
    require(job['job_id'] in jobs and all(job.get(k)==v for k,v in jobs[job['job_id']].items()),
            'unregistered candidate endpoint shard or decoding')
    return jobs[job['job_id']]


def job_root(root,job):
    return Path(root)/'evaluations/jobs'/job['job_id']


def generation_root(root,job):
    return job_root(root,job)/'shards'/job['panel']/'generation'


def _same_reference(left,right):
    return Path(left['path']).resolve()==Path(right['path']).resolve() and left['sha256']==right['sha256']


def _check_stop(root):
    require(not (Path(root)/'STOP').exists() and not (Path(root)/'control/stop_requested/record.json').exists(),
            'explicit STOP forbids continuing final evaluation')


def _accepted(root,job_id,directory,protocol):
    accepted=checked(directory/'accepted/record.json')
    result,actual=binding.read_ref(accepted['result']),binding.read_ref(accepted['actual_exit'])
    exit_path=Path(accepted['actual_exit']['path']).resolve()
    require(exit_path.is_relative_to((directory/'attempts').resolve()),'actual exit escaped its job')
    launch=checked(exit_path.parent.parent/'launch/record.json')
    require(accepted['protocol_id']==result['protocol_id']==actual['protocol_id']==launch['protocol_id']==protocol['id']
        and accepted['job_id']==result['job_id']==actual['job_id']==job_id
        and accepted['actual_exit_zero'] is True and accepted['resources_passed'] is True
        and result['status']=='COMPLETE' and accepted['result_id']==result['id']
        and actual['returncode']==0 and actual['actual_waitpid_observed'] is True
        and (actual['pid'],actual['birth'])==(launch['pid'],launch['birth'])
        and result['pid']==actual['pid']
        and result['resources']['all_gates_passed'] is True
        and _same_reference(accepted['result'],binding.entry(directory/'result/record.json')),
        'job requires bound result/resources and identity-matched actual exit0')
    return accepted,result


def _training_snapshot(root,job,protocol):
    require(job['step']==1490 and job['arm']==ARM,'only the final candidate endpoint is authorized')
    directory=Path(root)/'points/step1192/train'
    accepted,result=_accepted(root,'step1192.train',directory,protocol)
    completed=checked(directory/'completed/record.json')
    require(completed['protocol_id']==protocol['id'] and completed['status']=='COMPLETE'
        and completed['seed']==137 and completed['arm']==ARM
        and completed['initial_step']==1192 and completed['final_step']==1490
        and completed['optimizer_updates']==298 and completed['outer_updates']==0
        and completed['learning_rate']==1e-5 and completed['initial_learning_rate']==1e-4
        and completed['fixed_distribution_digest']==completed['distribution_digest']
        and result['final_checkpoint']==completed['final_checkpoint']
        and _same_reference(result['branch_result'],binding.entry(directory/'completed/record.json')),
        'candidate generation requires exact298-update fixed-pi low-lr training')
    return completed['final_checkpoint'],dict(accepted=binding.entry(directory/'accepted/record.json'),
        result=accepted['result'],completed=binding.entry(directory/'completed/record.json'))


def _snapshot_state(reference):
    training=importlib.import_module('finqa_v75_training')
    _,rt=training.runtime()
    state=training.read_checkpoint(reference,rt)
    context=training.checked_window(binding.ROOT,1192)
    training.validate_candidate_state(state,1490,context,rt)
    return state


def shard_cohort(full,shard):
    require(shard in (0,1) and full['denominator']==len(full['tasks'])==883
        and len(set(full['tasks']))==883,'exact original883 cohort required')
    indices=list(range(shard,883,2));tasks=[full['tasks'][i] for i in indices]
    return dict(tasks=tasks,denominator=len(tasks),source_groups={t:full['source_groups'][t] for t in tasks},
        original_full_denominator=883,original_ordinals=indices,assignment='original ordinal modulo2')


def _prepare(root,job,protocol,final):
    reference,train_binding=_training_snapshot(root,job,protocol)
    path=job_root(root,job)/'registration/record.json'
    if path.exists():
        plan=checked(path)
        require(plan['protocol_id']==protocol['id'] and plan['job']==_job(job)
            and plan['checkpoint']==reference and plan['training']==train_binding
            and plan['runtime_binding']==final.runtime_binding(),'saved candidate generation registration changed')
        return plan,None
    source,cohorts=_original()._public_source(protocol,final)
    require(job['config']==_original().panel_config('step894_dev883_greedy',GREEDY_SEED).model_dump(mode='json'),
            'candidate greedy decoding differs from the reused native control')
    state=_snapshot_state(reference)
    original_identity=next(iter(source['jobs'].values()))['model_identity']
    identity=final.ModelIdentity(backend='local_torch',model_id=source['assets']['base_binding']['id'],
        point_id='v75-StateDemo1192-evaluation:'+binding.digest(dict(protocol_id=protocol['id'],checkpoint=reference)),
        parameter_digest=final.parameter_digest(state['parameters']),
        tokenizer_digest=original_identity['tokenizer_digest'],
        chat_template_digest=original_identity['chat_template_digest']).model_dump(mode='json')
    plan=publish(path,dict(schema='v75_candidate_endpoint_generation_registration.v1',protocol_id=protocol['id'],
        job=_job(job),checkpoint=reference,training=train_binding,model_identity=identity,
        assets=source['assets'],snapshot=source['snapshot'],snapshot_id=source['snapshot_id'],
        role_plan=source['role_plan'],cohort=shard_cohort(cohorts['development'],job['shard']),
        runtime_binding=final.runtime_binding(),source_registration=protocol['evaluation_source_registration'],
        original_full_cohort_digest=binding.digest(cohorts['development']),private_references_read=False))
    return plan,state


def _inspect(root,job,plan,final):
    return final.base.inspect_shard(job_root(root,job),
        dict(runtime_binding=plan['runtime_binding'],config=job['config'],model_identity=plan['model_identity'],snapshot_id=plan['snapshot_id']),
        dict(key=job['panel'],task_keys=plan['cohort']['tasks']))


def audit_job_resume(root,job):
    _job(job);directory=generation_root(root,job)
    if not (directory/'run.json').exists():
        return dict(resume_allowed=True,unknown_calls=0,progress_units=0,evidence=[],
            durable_progress_digest=binding.digest([]),complete_stage=False)
    protocol=_protocol(root);plan=checked(job_root(root,job)/'registration/record.json')
    require(plan['protocol_id']==protocol['id'] and plan['job']==_job(job),'resume generation binding changed')
    final=_runtime();_inspect(root,job,plan,final)
    return binding.old_module('finqa_v56_feedback').audit_resume(directory)


def _seal(root,job,plan,final):
    run,seal,episodes=final.sealed_episodes(generation_root(root,job))
    require(run['tasks']==plan['cohort']['tasks'] and len(episodes)==job['denominator']
        and run['config']==job['config'] and run['provider']==plan['model_identity'] and run['role']=='development',
        'native shard identity or disjoint dose changed')
    value=publish(job_root(root,job)/'whole_queue_seal/record.json',dict(schema='v75_candidate_generation_shard_seal.v1',
        protocol_id=plan['protocol_id'],registration_id=plan['id'],job_id=job['job_id'],checkpoint=plan['checkpoint'],
        denominator=job['denominator'],run_id=run['id'],generation_seal_id=seal['id'],
        generation_seal=binding.file_ref(generation_root(root,job)/'generation_seal/seal.json'),
        episode_sha256=[canonical_episode_hash(e) for e in episodes],all_provider_calls_settled=True,private_references_read=False))
    return value,episodes


def run(root,job,gpu,attempt_root,guard):
    _job(job);protocol,final=_protocol(root),_runtime()
    guard.check('before_endpoint_registration',boundary=True)
    plan,state=_prepare(root,job,protocol,final)
    directory=generation_root(root,job)
    if not (directory/'run.json').exists():
        final.prepare_run(plan['snapshot'],plan['role_plan'],directory,role='development',
            config=_original().RunConfig.model_validate(job['config']),
            identity=final.ModelIdentity.model_validate(plan['model_identity']),task_keys=plan['cohort']['tasks'])
    audit=audit_job_resume(root,job)
    require(audit['resume_allowed'] and audit['unknown_calls']==0,'UNKNOWN generation cannot be retried')
    response_calls=0
    if not audit['complete_stage']:
        if state is None:state=_snapshot_state(plan['checkpoint'])
        guard.check('before_evaluation_model_load',boundary=True)
        provider=final.load_final_provider(dict(assets=plan['assets'],config=job['config']),dict(job,model_identity=plan['model_identity']),state)
        del state;state=None
        guard.check('after_evaluation_model_load',boundary=True)
        original_chat=provider.chat
        async def observed_chat(*args,**kwargs):
            guard.check('before_evaluation_response',boundary=True)
            return await original_chat(*args,**kwargs)
        def stopped():
            if guard.stop.requested:
                raise importlib.import_module('finqa_v75_resources').ExplicitStop('explicit evaluation stop')
        provider.chat=observed_chat
        try:
            asyncio.run(binding.old_module('finqa_v56_feedback').execute_run_resumable(directory,provider,
                attempt_root=Path(attempt_root)/'generation',stop_check=stopped,
                after_return=lambda event:guard.check('after_durable_evaluation_return',boundary=True)))
            response_calls=provider.actual_model_calls
        finally:
            provider.chat=original_chat
            del provider,original_chat
            gc.collect();final.torch.cuda.empty_cache()
        guard.check('after_evaluation_model_release',boundary=True)
    elif state is not None:
        del state;gc.collect()
    seal,_=_seal(root,job,plan,final)
    return dict(registration_id=plan['id'],whole_queue_seal=binding.entry(job_root(root,job)/'whole_queue_seal/record.json'),
        whole_queue_seal_id=seal['id'],sessions=job['denominator'],actual_new_response_calls=response_calls,
        scoring_calls=0,private_references_read=False,new_API_calls=0,model_released=True)


def _directory(root,job):
    if job['job_id'] in planned_jobs():return job_root(root,job)
    if job['job_id']=='step1192.train':return Path(root)/'points/step1192/train'
    return Path(root)/'jobs'/job['job_id']


def generation_exit_barrier(root,protocol):
    path=Path(root)/'all_jobs_exit_barrier/record.json';barrier=checked(path)
    jobs=protocol['jobs']
    require(barrier['protocol_id']==protocol['id'] and barrier['active_workers']==[]
        and set(barrier['accepted_jobs'])==set(barrier['actual_exits'])==set(jobs)
        and set(planned_jobs())<=set(jobs),'all fixed jobs must actually exit before final private scoring')
    for key,job in jobs.items():
        directory=_directory(root,job);accepted,result=_accepted(root,key,directory,protocol)
        require(barrier['accepted_jobs'][key]==binding.entry(directory/'accepted/record.json')
            and barrier['actual_exits'][key]==accepted['actual_exit'],'all-exits barrier bytes changed')
        if key in planned_jobs():
            seal=binding.read_ref(result['whole_queue_seal'])
            require(_same_reference(result['whole_queue_seal'],binding.entry(directory/'whole_queue_seal/record.json'))
                and result['sessions']==seal['denominator']==job['denominator']
                and result['registration_id']==seal['registration_id'] and result['whole_queue_seal_id']==seal['id'],
                'accepted dev shard lacks its full native seal')
    material_ref=barrier['materials_accepted'];material=binding.read_ref(material_ref)
    require(_same_reference(material_ref,binding.entry(Path(root)/'materials_preparation/accepted/record.json')),
            'material CPU acceptance path changed')
    actual,result,resources=(binding.read_ref(material[k]) for k in ('actual_exit','result','resources'))
    material_attempt=Path(root)/'materials_preparation/attempt0001'
    require(Path(material['actual_exit']['path']).resolve()==material_attempt/'actual_exit/record.json'
        and Path(material['result']['path']).resolve()==material_attempt/'result/record.json',
        'material CPU acceptance escaped the registered single attempt')
    launch=checked(material_attempt/'launch/record.json')
    require(launch['protocol_id']==protocol['id'] and (launch['pid'],launch['birth'])==(actual['pid'],actual['birth']),
        'material CPU actual exit differs from its launched process identity')
    require(material['protocol_id']==actual['protocol_id']==result['protocol_id']==resources['protocol_id']==protocol['id']
        and actual['actual_waitpid_observed'] is True and actual['returncode']==0
        and result['status']==resources['status']=='COMPLETE' and resources['all_gates_passed'] is True
        and resources['CUDA_initialized'] is False and actual['pid']==result['pid']==resources['pid']
        and actual['birth']==resources['birth'],'material CPU must actually complete and exit0 before evaluation')
    return binding.entry(path)


def _scored_candidate(root,protocol,barrier_ref,final,guard=None):
    path=Path(root)/'evaluations/native_scores/record.json'
    if path.exists():
        saved=checked(path)
        require(saved['protocol_id']==protocol['id'] and saved['all_jobs_exit_barrier']==barrier_ref
            and saved['denominator']==883,'durable final native panel binding changed')
        return saved
    old={label:binding.read_ref(protocol['reused_evaluation'][label]) for label in ('B','P')}
    full_tasks=[r['original_task_key'] for r in old['B']['results']]
    require(len(full_tasks)==len(set(full_tasks))==883
        and [r['original_task_key'] for r in old['P']['results']]==full_tasks,'original883 reused cohort changed')
    indexed={};plans={};seals={};common=None
    for key,job in planned_jobs().items():
        plan=checked(job_root(root,job)/'registration/record.json')
        require(plan['protocol_id']==protocol['id'] and plan['job']==job,'candidate shard registration changed')
        identity=(plan['model_identity'],plan['checkpoint'],plan['snapshot_id'],plan['original_full_cohort_digest'])
        require(common is None or identity==common,'candidate shards used different models or original cohorts')
        common=identity
        require(plan['cohort']['tasks']==full_tasks[job['shard']::2],'candidate shard ordinal partition changed')
        seal,episodes=_seal(root,job,plan,final);plans[key]=plan;seals[key]=binding.entry(job_root(root,job)/'whole_queue_seal/record.json')
        for task,episode in zip(plan['cohort']['tasks'],episodes,strict=True):
            require(task not in indexed,'task generated in more than one dev shard')
            indexed[task]=(episode,plan['cohort']['source_groups'][task],key)
    require(set(indexed)==set(full_tasks),'complete883 task coverage required before private scores')
    plan=next(iter(plans.values()))
    manifest,public,lineages=final.load_public_snapshot(plan['snapshot'])
    require(manifest['id']==plan['snapshot_id'],'candidate public snapshot changed')
    bundles=None;rows=[]
    for ordinal,task in enumerate(full_tasks):
        _check_stop(root)
        if guard is not None:guard.check('before_v75_native_score',boundary=True)
        episode,source_group,job_id=indexed[task];episode_sha=canonical_episode_hash(episode)
        row_path=Path(root)/'evaluations/native_rows'/f'row{ordinal:04d}'/'record.json'
        if row_path.exists():
            saved=checked(row_path)
            require(saved['protocol_id']==protocol['id'] and saved['ordinal']==ordinal
                and saved['episode_sha256']==episode_sha and saved['job_id']==job_id
                and saved['all_jobs_exit_barrier']==barrier_ref,'saved native row changed; never rescore')
            row=saved['row']
        else:
            if bundles is None:bundles=_original()._panel_private_bundles(final,plan,manifest,public,lineages,set(full_tasks))
            row=dict(task_key=f'draw{GREEDY_SEED}/{task}',original_task_key=task,draw_seed=GREEDY_SEED,
                native=final.score_public_reasoning_program(bundles[task],episode),stop_reason=episode.stop_reason,
                actual_model_calls=episode.actual_model_calls,tool_call_count=len(episode.tool_events),
                generated_token_count=sum(len(t.receipt.raw_generated_token_ids) for t in episode.turns if t.receipt is not None),
                source_group=source_group)
            publish(row_path,dict(schema='v75_durable_candidate_native_row.v1',protocol_id=protocol['id'],
                ordinal=ordinal,job_id=job_id,episode_sha256=episode_sha,all_jobs_exit_barrier=barrier_ref,row=row))
        rows.append(row)
    metrics=_original().stats.native_metrics(rows,883)
    return publish(path,dict(schema='v75_complete_candidate_native_panel.v1',protocol_id=protocol['id'],
        arm=ARM,step=1490,seed=137,role='development',denominator=883,results=rows,metrics=metrics,
        all_jobs_exit_barrier=barrier_ref,whole_queue_seals=seals,reused_evaluation=protocol['reused_evaluation'],
        status='COMPLETE' if all(metrics[m]['unknown']==0 for m in ('execution_accuracy','program_accuracy')) else 'COMPLETE_WITH_UNKNOWN',
        old_scores_rescored=False,UNKNOWN_as_zero=False,old96_extra_generations=0))


def finish(root,guard=None):
    _check_stop(root);protocol=_protocol(root)
    barrier_ref=generation_exit_barrier(root,protocol)
    path=Path(root)/'evaluations/final_summary/record.json'
    if path.exists():
        value=checked(path)
        require(value['protocol_id']==protocol['id'] and value['all_jobs_exit_barrier']==barrier_ref,'saved final analysis binding changed')
        return value
    final=_runtime();candidate=_scored_candidate(root,protocol,barrier_ref,final,guard)
    old={label:binding.read_ref(protocol['reused_evaluation'][label]) for label in ('B','P')}
    selection=binding.read_ref(protocol['mechanism_selection'])
    analysis=importlib.import_module('finqa_v75_analysis')
    summary=analysis.compare_reports(candidate,old['B'],old['P'],selection)
    completed=checked(Path(root)/'points/step1192/train/completed/record.json')
    return publish(path,dict(summary,protocol_id=protocol['id'],all_jobs_exit_barrier=barrier_ref,
        candidate_report=binding.entry(Path(root)/'evaluations/native_scores/record.json'),
        reused_evaluation=protocol['reused_evaluation'],mechanism_selection=protocol['mechanism_selection'],
        historical_V74_stratification=protocol['historical_V74_stratification'],
        training_completed=binding.entry(Path(root)/'points/step1192/train/completed/record.json'),
        demonstration_materials=completed['demonstration_materials'],
        planned_demonstration_dose=completed['planned_demonstration_dose'],
        actual_demonstration_consumption=completed['actual_demonstration_consumption'],
        new_development_sessions=883,new_native_scores=883,new_optimizer_updates=298,
        task_exposures=1488,endpoint1490_selected_in_advance=True,new_outer_updates=0,
        new_Contribution_or_VJP=0,new_probability_probe_sequences=0,external_API_calls=0,
        no_unit_compute_advantage_claim=True,common_old_consumer_unchanged=True,
        automatic_followup=False,automatic_Full_resume=False))
