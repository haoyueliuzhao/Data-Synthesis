"""V76 three autonomous dev883 endpoints and all-exits-gated native scoring.

Two fixed disjoint generation shards per endpoint change scheduling only. The merged native
883-task scorer, harness, greedy parameters and original task order are retained.
"""
from __future__ import annotations
import asyncio
import gc
import importlib
from pathlib import Path
import finqa_v76_binding as binding

require,checked,publish=binding.require,binding.checked,binding.publish
GREEDY_SEED=20260928
ENDPOINTS=(('A',1490),('A',1788),('D',1788))
CONDITION='fixed_V75_demonstrations_two_window_Full_vs_fixed'


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
    for arm,step in ENDPOINTS:
        for shard,n in ((0,442),(1,441)):
            key=f'{arm}.step{step}.dev_greedy.shard{shard}'
            dependency=f'step{step-298}.train' if arm=='A' else 'D.step1490.train'
            jobs[key]=dict(job_id=key,id=key,kind='generate',memory_phase='generate',stage='generate',
                seed=137,arm=arm,step=step,role='development',algorithm=CONDITION,
                denominator=n,full_denominator=883,draw_seed=GREEDY_SEED,panel=key,
                shard=shard,shards=2,config=panel_config(),dependencies=[dependency])
    return jobs


def evaluation_contract():
    analysis=importlib.import_module('finqa_v76_analysis')
    return dict(schema='v76_two_window_three_endpoint_autonomous_evaluation.v1',jobs=planned_jobs(),
        total_sessions=2649,new_generation_shards=6,shard_assignment='original dev883 ordinal modulo2 per endpoint',
        new_model_conditions=3,new_model_call_cap=84768,endpoints=[dict(arm=a,step=s) for a,s in ENDPOINTS],
        generation_starts_from_initial_public_request=True,teacher_history_supplied=False,
        reused_fixed1490=dict(source='V75',EA_correct=557,new_sessions=0,new_scores=0),
        reused_parent1192=dict(source='V71 evaluated in V72',EA_correct=536,new_sessions=0,new_scores=0),
        historical_low_lr1490=dict(source='V72',EA_correct=431,primary_algorithm_control=False,new_scores=0),
        calibration_sessions=0,test_sessions=0,stochastic_evaluation=False,old96_extra_generations=0,
        primary='EA(A1788)-EA(D1788)',first_window_descriptive='EA(A1490)-EA(S1490)',
        fixed_continuation='EA(D1788)-EA(S1490)',
        original_native_harness_and_metric_sources_unchanged=True,greedy_config=panel_config(),
        before_generation='matching complete298updates and actual accepted training exit0',
        before_private_scoring='all30 scientific and evaluation jobs accepted actual exit0 including terminal1788 probe',
        intermediate_scores_observed_before_second_window=False,
        canonical_episode_encoding='native Episode.model_dump(mode=json)',complete_returns_never_regenerated=True,
        unknown_call_auto_retry=False,UNKNOWN_as_zero=False,full_denominator=883,
        statistics=analysis.statistics_contract(),terminal1788_probe_applied=False,
        reused_baseline_is_new_independent_replication=False,equal_total_compute=False,
        source_composition_is_cross_seed_uncertainty=False,automatic_followup=False)


def canonical_episode_payload(episode):
    value=episode if isinstance(episode,dict) else episode.model_dump(mode='json')
    require(isinstance(value,dict),'native Episode must serialize to an object')
    return value


def canonical_episode_hash(episode):
    return binding.digest(canonical_episode_payload(episode))


def _protocol(root):
    require(Path(root).resolve()==binding.ROOT.resolve(),'foreign V76 evaluation root')
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
    result_pid_matches = result['pid']==actual['pid']
    if not result_pid_matches:
        proof_path=exit_path.parent.parent/'reused_result/record.json'
        proof=checked(proof_path)
        source=binding.read_ref(proof['source_result'])
        resources=binding.read_ref(proof['source_resource_closeout'])
        require(proof['protocol_id']==protocol['id'] and proof['job_id']==job_id
            and proof['scientific_calls']==0 and proof['verified_durable_result'] is True
            and _same_reference(proof['source_result'],accepted['result']) and source==result
            and resources['protocol_id']==protocol['id'] and resources['job_id']==job_id
            and resources['pid']==result['pid'] and resources['status']=='COMPLETE'
            and resources['resources']==result['resources']
            and resources['resources']['all_gates_passed'] is True,
            'cold complete-result reuse lacks its original successful resource binding')
        result_pid_matches=True
    require(accepted['protocol_id']==result['protocol_id']==actual['protocol_id']==launch['protocol_id']==protocol['id']
        and accepted['job_id']==result['job_id']==actual['job_id']==job_id
        and accepted['actual_exit_zero'] is True and accepted['resources_passed'] is True
        and result['status']=='COMPLETE' and accepted['result_id']==result['id']
        and actual['returncode']==0 and actual['actual_waitpid_observed'] is True
        and (actual['pid'],actual['birth'])==(launch['pid'],launch['birth'])
        and result_pid_matches
        and result['resources']['all_gates_passed'] is True
        and _same_reference(accepted['result'],binding.entry(directory/'result/record.json')),
        'job requires bound result/resources and identity-matched actual exit0')
    return accepted,result


def _training_snapshot(root,job,protocol):
    require((job['arm'],job['step']) in ENDPOINTS,'only three registered V76 endpoints are authorized')
    start=job['step']-298
    directory=(Path(root)/'fixed' if job['arm']=='D' else Path(root))/'points'/f'step{start:04d}'/'train'
    key=f'D.step{start}.train' if job['arm']=='D' else f'step{start}.train'
    accepted,result=_accepted(root,key,directory,protocol)
    completed=checked(directory/'completed/record.json')
    require(completed['protocol_id']==protocol['id'] and completed['status']=='COMPLETE'
        and completed['seed']==137 and completed['initial_step']==start and completed['final_step']==job['step']
        and completed['optimizer_updates']==298 and completed['outer_updates']==(1 if job['arm']=='A' else 0)
        and completed['learning_rate']==1e-5
        and completed['actual_demonstration_consumption']['all298_actual_receipts_match_frozen_slots'] is True
        and completed['actual_demonstration_consumption']['student_prefix_target_count']==0
        and result['final_checkpoint']==completed['final_checkpoint']
        and _same_reference(result['branch_result'],binding.entry(directory/'completed/record.json')),
        'generation requires exact matching mixed-loss training and actual exit0')
    return completed['final_checkpoint'],dict(accepted=binding.entry(directory/'accepted/record.json'),
        result=accepted['result'],completed=binding.entry(directory/'completed/record.json'))


def _snapshot_state(reference,job):
    training=importlib.import_module('finqa_v76_training')
    _,rt=training.runtime()
    state=training.read_checkpoint(reference,rt)
    training.validate_evaluation_state(state,job['step'],job['arm'],rt)
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
    state=_snapshot_state(reference,job)
    original_identity=next(iter(source['jobs'].values()))['model_identity']
    identity=final.ModelIdentity(backend='local_torch',model_id=source['assets']['base_binding']['id'],
        point_id='v76-'+job['arm']+'-evaluation:'+binding.digest(dict(protocol_id=protocol['id'],checkpoint=reference)),
        parameter_digest=final.parameter_digest(state['parameters']),
        tokenizer_digest=original_identity['tokenizer_digest'],
        chat_template_digest=original_identity['chat_template_digest']).model_dump(mode='json')
    plan=publish(path,dict(schema='v76_candidate_endpoint_generation_registration.v1',protocol_id=protocol['id'],
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
    value=publish(job_root(root,job)/'whole_queue_seal/record.json',dict(schema='v76_candidate_generation_shard_seal.v1',
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
        if state is None:state=_snapshot_state(plan['checkpoint'],job)
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
                raise importlib.import_module('finqa_v76_resources').ExplicitStop('explicit evaluation stop')
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
    if job['kind']=='generate':return job_root(root,job)
    prefix=Path(root)/'fixed' if job['job_id'].startswith('D.') else Path(root)
    return prefix/'points'/f"step{job['step']:04d}"/job['stage']


def generation_exit_barrier(root,protocol):
    path=Path(root)/'all_jobs_exit_barrier/record.json';barrier=checked(path)
    jobs=protocol['jobs']
    require(barrier['protocol_id']==protocol['id'] and barrier['active_workers']==[]
        and len(jobs)==30 and set(barrier['accepted_jobs'])==set(barrier['actual_exits'])==set(jobs)
        and set(planned_jobs())<=set(jobs),'all30 fixed jobs must actually exit before final private scoring')
    for key,job in jobs.items():
        directory=_directory(root,job);accepted,result=_accepted(root,key,directory,protocol)
        require(barrier['accepted_jobs'][key]==binding.entry(directory/'accepted/record.json')
            and barrier['actual_exits'][key]==accepted['actual_exit'],'all-exits barrier bytes changed')
        if key in planned_jobs():
            seal=binding.read_ref(result['whole_queue_seal'])
            require(_same_reference(result['whole_queue_seal'],binding.entry(directory/'whole_queue_seal/record.json'))
                and result['sessions']==seal['denominator']==job['denominator']
                and result['registration_id']==seal['registration_id'] and result['whole_queue_seal_id']==seal['id'],
                'accepted development shard lacks its full native seal')
        if key=='step1788.distribution':
            require(result['probe_only'] is True and result['applied'] is False,
                    'terminal1788 probe must complete without a third application')
    require('step1788.distribution' in jobs,'terminal probe missing from the global exit barrier')
    prepared=binding.read_ref(protocol['preflight_accepted'])
    actual=binding.read_ref(prepared['actual_exit'])
    require(actual['actual_waitpid_observed'] is True and actual['returncode']==0
        and prepared['actual_exit_zero'] is True and prepared['resources_passed'] is True,
        'independent V75 CPU revision must have a successful actual accepted exit')
    binding.read_ref(protocol['v75_cpu_revision']);binding.read_ref(protocol['source_overlap'])
    return binding.entry(path)


def _scored_endpoint(root,protocol,barrier_ref,final,arm,step,guard=None):
    endpoint=f'{arm}{step}';base=Path(root)/'evaluations/panels'/endpoint
    path=base/'native_scores/record.json'
    if path.exists():
        saved=checked(path)
        require(saved['protocol_id']==protocol['id'] and saved['all_jobs_exit_barrier']==barrier_ref
            and saved['denominator']==883 and saved['arm']==arm and saved['step']==step,
            'durable endpoint native panel binding changed')
        return saved
    old={label:binding.read_ref(protocol['reused_evaluation'][label]) for label in ('S','P')}
    full_tasks=[r['original_task_key'] for r in old['S']['results']]
    require(len(full_tasks)==len(set(full_tasks))==883
        and [r['original_task_key'] for r in old['P']['results']]==full_tasks,'original883 reused cohort changed')
    indexed={};plans={};seals={};common=None
    for key,job in planned_jobs().items():
        if (job['arm'],job['step'])!=(arm,step):continue
        plan=checked(job_root(root,job)/'registration/record.json')
        require(plan['protocol_id']==protocol['id'] and plan['job']==job,'endpoint shard registration changed')
        identity=(plan['model_identity'],plan['checkpoint'],plan['snapshot_id'],plan['original_full_cohort_digest'])
        require(common is None or identity==common,'endpoint shards used different models or cohorts')
        common=identity
        require(plan['cohort']['tasks']==full_tasks[job['shard']::2],'endpoint ordinal partition changed')
        seal,episodes=_seal(root,job,plan,final);plans[key]=plan;seals[key]=binding.entry(job_root(root,job)/'whole_queue_seal/record.json')
        for task,episode in zip(plan['cohort']['tasks'],episodes,strict=True):
            require(task not in indexed,'task generated in more than one endpoint shard')
            indexed[task]=(episode,plan['cohort']['source_groups'][task],key)
    require(len(plans)==2 and set(indexed)==set(full_tasks),'complete883 coverage required before private scores')
    plan=next(iter(plans.values()))
    manifest,public,lineages=final.load_public_snapshot(plan['snapshot'])
    require(manifest['id']==plan['snapshot_id'],'endpoint public snapshot changed')
    bundles=None;rows=[]
    for ordinal,task in enumerate(full_tasks):
        _check_stop(root)
        if guard is not None:guard.check('before_v76_native_score',boundary=True)
        episode,source_group,job_id=indexed[task];episode_sha=canonical_episode_hash(episode)
        row_path=base/'native_rows'/f'row{ordinal:04d}'/'record.json'
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
            publish(row_path,dict(schema='v76_durable_endpoint_native_row.v1',protocol_id=protocol['id'],
                ordinal=ordinal,job_id=job_id,episode_sha256=episode_sha,all_jobs_exit_barrier=barrier_ref,row=row))
        rows.append(row)
    metrics=_original().stats.native_metrics(rows,883)
    return publish(path,dict(schema='v76_complete_endpoint_native_panel.v1',protocol_id=protocol['id'],
        arm=arm,step=step,seed=137,role='development',denominator=883,results=rows,metrics=metrics,
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
    final=_runtime();reports={};report_refs={}
    for arm,step in ENDPOINTS:
        _check_stop(root)
        endpoint=f'{arm}{step}';report=_scored_endpoint(root,protocol,barrier_ref,final,arm,step,guard)
        require(report['status']=='COMPLETE','native UNKNOWN blocks final acceptance; never impute or rescore')
        reports[endpoint]=report
        report_refs[endpoint]=binding.entry(Path(root)/'evaluations/panels'/endpoint/'native_scores/record.json')
    reused={label:binding.read_ref(protocol['reused_evaluation'][label]) for label in ('S','P','B')}
    analysis=importlib.import_module('finqa_v76_analysis')
    summary=analysis.compare_reports(reports,reused)
    completed={}
    for arm,start in (('A',1192),('A',1490),('D',1490)):
        prefix=Path(root)/'fixed' if arm=='D' else Path(root)
        train_path=prefix/'points'/f'step{start:04d}'/'train/completed/record.json'
        completed[f'{arm}{start}']=dict(record=checked(train_path),reference=binding.entry(train_path))
    diagnostics=importlib.import_module('finqa_v76_diagnostics')
    points={};refs={};tracks={}
    for step in (1192,1490,1788):
        diag_path=Path(root)/'points'/f'step{step:04d}'/'distribution/frozen_diagnostics/record.json'
        points[step]=checked(diag_path)
        require(points[step]['policy']==diagnostics.policy(),'frozen point diagnostic policy changed')
        refs[str(step)]=binding.entry(diag_path)
    for before,after in ((1192,1490),(1490,1788)):
        track_path=Path(root)/'points'/f'step{after:04d}'/'distribution/tracking_diagnostics/record.json'
        track=checked(track_path)
        require(track['previous_binding']==points[before]['binding'] and track['current_binding']==points[after]['binding'],
                'target drift diagnostic point identity changed')
        tracks[f'{before}_{after}']=binding.entry(track_path)
    materials=binding.read_ref(protocol['demonstration_materials'])
    result=analysis.assemble_final_summary(analysis=summary,protocol_id=protocol['id'],barrier_ref=barrier_ref,
        reports=report_refs,reused=protocol['reused_evaluation'],train_records=completed,
        material_ref=protocol['demonstration_materials'],materials=materials,diagnostics=refs,tracks=tracks)
    return publish(path,dict(result,v75_cpu_revision=protocol['v75_cpu_revision'],
        source_overlap=protocol['source_overlap']))
