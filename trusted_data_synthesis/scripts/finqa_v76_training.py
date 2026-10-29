"""V76 matched mixed-objective training and explicit twelve-epoch continuation.

Actual historical checkpoints are immutable inputs.  A CPU preparation saves a
new complete state whose only initial changes are the declared low learning
rate and the registered schedule extension.  All real optimizer updates use
the frozen V75 mixed row consumer and the inherited native commit method.
"""
from __future__ import annotations

import copy
import gc
import hashlib
import importlib
import io
import json
import math
from pathlib import Path
import random
import re
from types import FunctionType

import finqa_v76_binding as binding

binding.install_scientific_paths()
previous = binding.source_v75('training')
original, records = previous.original, previous.records
task_cache = binding.old_module('finqa_v35_task_cache')
ROOT, SEED = binding.ROOT, 137
POINTS, WINDOWS = (1192, 1490, 1788), {1192: 1490, 1490: 1788}
NEW_LR, OLD_LR = 1e-5, 1e-4
PARENT_STATE_DIGEST = previous.PARENT_STATE_DIGEST
V75_PROTOCOL_ID = '542895ea40b06c777336c5c7a68b56a21ccb657f4188333e44d7d3446a1903bb'
MATERIAL_ID = '6485969c9ff287b82c93a7ea7d048d7d8b49fe7ac03aa4e46cd77c43b308182d'
require, checked, publish = binding.require, binding.checked, binding.publish
runtime, checkpoint_ref, read_checkpoint = previous.runtime, previous.checkpoint_ref, previous.read_checkpoint
validate_distribution = previous.validate_distribution
consume_task_batch = previous.consume_task_batch


def branch_root(root, arm='A'):
    require(Path(root).resolve() == ROOT.resolve() and arm in ('A', 'D'), 'unregistered V76 branch/root')
    return Path(root) if arm == 'A' else Path(root) / 'fixed'


def point_root(root, step, arm='A'):
    require(step in POINTS and (arm == 'A' or step in (1490, 1788)), 'unregistered V76 point')
    return branch_root(root, arm) / 'points' / f'step{step:04d}'


def initial_checkpoint():
    return previous.initial_checkpoint()


def fixed_initial_checkpoint():
    done = checked(binding.V75_ROOT / 'points/step1192/train/completed/record.json')
    require(done['protocol_id'] == V75_PROTOCOL_ID and done['status'] == 'COMPLETE'
        and done['initial_step'] == 1192 and done['final_step'] == 1490
        and done['optimizer_updates'] == 298 and done['outer_updates'] == 0
        and done['outer_done'] == [298] and done['actual_demonstration_consumption']['status'] == 'PASS'
        and done['actual_demonstration_consumption']['material_id'] == MATERIAL_ID,
        'D must inherit the complete actual V75 first window, never retrain it')
    ref = done['final_checkpoint']
    require(Path(ref['path']).resolve() == binding.V75_ROOT / 'training/step1490_step',
        'fixed initial endpoint changed')
    return ref


def expected_outer_history(step, arm='A', *, applied_at_start=False):
    require(arm in ('A', 'D') and 1192 <= step <= 1788, 'unregistered history coordinate')
    return [298] + ([s for s in WINDOWS if s < step or (applied_at_start and s == step)] if arm == 'A' else [])


def extended_schedule(original_schedule, original_plan, task_ids, seed=SEED):
    """Same seeded fresh-order shuffles; append epochs11/12, preserving old batches."""
    tasks = list(task_ids)
    require(seed == SEED and len(tasks) == len(set(tasks)) and tasks,
        'registered seed137 and unique task order required')
    require(original_schedule['seed'] == seed and original_schedule['epochs'] == 10
        and original_plan['epochs'] == 10 and original_schedule['N'] == len(tasks),
        'only the exact original ten-epoch schedule may be extended')
    rng, batches = random.Random(seed), []
    for epoch in range(1, 13):
        permutation = list(tasks)
        rng.shuffle(permutation)
        for offset in range(0, len(tasks), 5):
            selected = permutation[offset:offset + 5]
            batches.append(dict(step=len(batches) + 1, epoch=epoch, batch_index=offset // 5,
                task_ids=selected, actual_batch_size=len(selected)))
    old_count = original_plan['final_step']
    require(batches[:old_count] == original_schedule['batches']
        and old_count == 10 * ((len(tasks) + 4) // 5),
        'new shuffle must reproduce all original ten epochs exactly')
    plan = {k: copy.deepcopy(v) for k, v in original_plan.items() if k != 'id'}
    plan.update(schema='v76_registered_twelve_epoch_execution_plan.v1', epochs=12,
        final_step=len(batches), outer_steps=[], explicit_Full_outer_steps=[1192, 1490],
        terminal_unapplied_probe_step=1788, automatic_outer_disabled=True,
        historical_execution_plan_id=original_plan['id'],
        historical_budget_fields_are_not_V76_budgets=True,
        new_V76_optimizer_updates=894, new_V76_task_exposures=4464)
    plan['id'] = binding.digest(plan)
    schedule = {k: copy.deepcopy(v) for k, v in original_schedule.items() if k != 'schedule_sha256'}
    schedule.update(schema='v76_registered_twelve_epoch_task_schedule.v1', epochs=12,
        updates=len(batches), execution_plan_id=plan['id'], batches=batches,
        inherited_ten_epoch_schedule_sha256=original_schedule['schedule_sha256'],
        new_epochs=[11, 12], same_schedule_for_all_arms=True)
    schedule['schedule_sha256'] = binding.digest(schedule)
    return plan, schedule


def _schedule_record(root, source_state, pool, training):
    path = Path(root) / 'schedule/record.json'
    if path.exists():
        value = checked(path)
        require(value['task_ids'] == list(pool.task_ids) and value['seed'] == SEED,
            'common paired schedule roster changed')
        return value
    old_schedule = training.build_task_schedule(pool.task_ids, SEED)
    old_plan = training.load_runtime().conditional.execution_plan(len(pool.task_ids))
    require(source_state['schedule'] == old_schedule and source_state['execution_plan'] == old_plan,
        'initial complete source must bind the original ten-epoch plan')
    plan, schedule = extended_schedule(old_schedule, old_plan, pool.task_ids)
    require(len(schedule['batches']) == 1788 and len(schedule['batches'][1490:]) == 298
        and sum(len(x['task_ids']) for x in schedule['batches'][1490:]) == 1488,
        'new paired window must add exactly298 updates/1488 exposures')
    return publish(path, dict(schema='v76_common_paired_schedule_registration.v1', seed=SEED,
        task_ids=list(pool.task_ids), original_schedule=old_schedule, original_execution_plan=old_plan,
        schedule=schedule, execution_plan=plan, original_prefix_batches_unchanged=True,
        added_epochs=[11, 12], new_window_steps=[1491, 1788], new_window_updates=298,
        new_window_task_exposures=1488, explicit_new_budget_not_old_remaining_work=True))


def _materials_reference():
    ref = binding.entry(binding.V75_ROOT / 'materials/record.json')
    require(ref['id'] == MATERIAL_ID, 'only the fixed V75 material support is authorized')
    return ref


def _material_record(point):
    value = binding.read_ref(point['demonstration_materials'])
    policy = binding.source_v75('materials').material_policy()
    require(value['id'] == MATERIAL_ID and value['status'] == 'COMPLETE'
        and value['protocol_id'] == V75_PROTOCOL_ID and value['policy'] == policy
        and len(value['packages']) == 179 and value['selected_tasks'] == 128,
        'V75 fixed teacher support, original admission, or slots changed')
    return value


def load_demonstrations(point):
    material = _material_record(point)
    packages = {name: binding.read_ref(ref) for name, ref in material['packages'].items()}
    for name, package in packages.items():
        require(package['package_id'] == name and package['protocol_id'] == V75_PROTOCOL_ID
            and package['student_prefix_target_count'] == 0 and package['target_tokens'] > 0
            and package['target_mask_check'] == 'PASS_EXACT_NEW_TEACHER_RESPONSES_ONLY',
            'fixed teacher package changed or includes a student-prefix target')
    return material, packages


def planned_demonstration_dose(material, batches, mu):
    """V75 slot arithmetic with actual registered task mass and arbitrary new window."""
    from collections import Counter
    from fractions import Fraction
    slots_api = binding.source_v75('materials')
    require(len(batches) == 298 and sum(len(x['task_ids']) for x in batches) == 1488,
        'one window must contain exact298 batches/1488 task exposures')
    require(sorted(len(x['task_ids']) for x in batches) == [4, 4] + [5] * 296,
        'tail batches must remain the two real four-task batches')
    probabilities = {task: Fraction(1, len(mu)) for task in mu}
    mass, tokens, positions, micro, exposures, per_step = Counter(), Counter(), Counter(), Counter(), Counter(), []
    for batch in batches:
        rows = []
        for task in batch['task_ids']:
            unit = Fraction(str(mu[task])) / (len(batch['task_ids']) * probabilities[task])
            exposures[task] += 1
            available = material['tasks'].get(task, {}).get('slots', {})
            weights = slots_api.slot_weights(available.get('initial') is not None, available.get('post') is not None)
            for name, coefficient in weights.items():
                mass[name] += unit * coefficient
            for name in ('initial', 'post'):
                slot = available.get(name)
                if slot is None:
                    continue
                summary = slot['encoding_summary']
                tokens[name] += summary['target_tokens']; positions[name] += summary['input_positions']; micro[name] += summary['teacher_turns']
                rows.append(dict(task_id=task, slot=name, package_id=slot['package_id'],
                    task_coefficient=str(unit * weights[name]), target_tokens=summary['target_tokens'],
                    input_positions=summary['input_positions'], teacher_turns=summary['teacher_turns']))
        per_step.append(dict(step=batch['step'], batch_size=len(batch['task_ids']),
            task_ids=list(batch['task_ids']), demonstrations=rows))
    require(sum(mass.values()) == 298 and len(exposures) == 744 and set(exposures.values()) == {2},
        'fixed task frequencies or complete-window mass changed')
    return dict(schema='v76_registered_fixed_teacher_window_dose.v1', updates=298, task_exposures=1488,
        start_step=batches[0]['step'] - 1, end_step=batches[-1]['step'], per_step=per_step,
        planned_teacher_target_tokens=dict(tokens), planned_teacher_input_positions=dict(positions),
        planned_teacher_microbatches=dict(micro), realized_average_update_mass={k:str(mass[k]/298) for k in ('old','initial','post')},
        realized_window_mass_sum={k:str(mass[k]) for k in ('old','initial','post')},
        fixed_teacher_material_id=material['id'], task_mass_source='actual mu/(B*p); uniform registered epoch permutation',
        teacher_mass_independent_of_pi=True, original_task_frequency_unchanged=True,
        weights_are_not_gradient_or_loss_measurements=True)


def _write_prepared_checkpoint(directory, state, evidence, rt):
    from trusted_synthesis.core.immutable_artifacts import write_immutable_artifact_directory
    directory = Path(directory)
    if directory.exists():
        reference = checkpoint_ref(directory)
        saved = read_checkpoint(reference, rt)
        require(rt.v8._tree_digest(saved) == rt.v8._tree_digest(state), 'prepared actual state changed')
        require(json.loads((directory/'record.json').read_bytes())['evidence'] == evidence,
            'existing actual preparation evidence changed')
        return reference
    buffer = io.BytesIO(); rt.torch.save(state, buffer); raw = buffer.getvalue()
    summary = dict(step=state['step'], phase='v76_preparation', arm=state['arm'], seed=SEED,
        state_sha256=hashlib.sha256(raw).hexdigest(), actual_state_digest=rt.v8._tree_digest(state),
        pool_id=state['pool_id'], schedule_sha256=state['schedule']['schedule_sha256'], evidence=evidence,
        checkpoint_contains_actual_model_Adam_RNG_pi=True)
    write_immutable_artifact_directory(directory, {'state.pt':raw,
        'record.json':(json.dumps(summary, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)+'\n').encode()})
    return checkpoint_ref(directory)


def prepare_state(source, common, rt, *, arm, step):
    """Declare metadata/LR intervention on complete CPU tensors, never an optimizer step."""
    require(arm in ('A','D') and step in ((1192,) if arm == 'A' else (1490,)), 'only initial sources need preparation')
    before = rt.v8._tree_digest(source)
    if arm == 'A':
        previous.validate_parent_state(source, rt)
    else:
        context = checked(binding.V75_ROOT/'points/step1192/context/record.json')
        previous.validate_low_lr_state(source, 1490, context, rt)
    target = previous.state_with_learning_rate(source, NEW_LR)
    target = dict(target, schedule=copy.deepcopy(common['schedule']), execution_plan=copy.deepcopy(common['execution_plan']))
    restored = dict(target, schedule=source['schedule'], execution_plan=source['execution_plan'])
    restored = previous.state_with_learning_rate(restored, OLD_LR if arm == 'A' else NEW_LR)
    require(rt.v8._tree_digest(restored) == before and rt.v8._tree_digest(source) == before,
        'preparation must only alter registered schedule/plan and initial A learning rate')
    if arm == 'A':
        expected_low = previous.state_with_learning_rate(source, NEW_LR)
        v75_lr = checked(binding.V75_ROOT/'points/step1192/train/lr_intervention/record.json')
        require(rt.v8._tree_digest(expected_low) == v75_lr['post_state_digest'],
            'same parent and LR must reproduce the actual V75 LR-only intervention digest')
    return target


def _accepted_previous(root, step):
    start = step - 298
    directory = point_root(root, start)/'train'
    accepted = checked(directory/'accepted/record.json')
    actual, result = binding.read_ref(accepted['actual_exit']), binding.read_ref(accepted['result'])
    require(actual['actual_waitpid_observed'] is True and actual['returncode'] == 0
        and accepted['actual_exit_zero'] is True and result['resources']['all_gates_passed'] is True
        and result['final_step'] == step and result['optimizer_updates'] == 298,
        'next A point requires the actually exited preceding real training window')
    done = checked(directory/'completed/record.json')
    require(done['final_checkpoint'] == result['final_checkpoint'], 'preceding complete actual endpoint differs')
    return done['final_checkpoint']


def static_task_plan(root, step, pool, parameter_spec):
    """Reuse only first-point static metadata; every point has a fresh gradient binding."""
    require(step in POINTS, 'unregistered static-plan coordinate')
    if step == 1192:
        return task_cache.make_task_plan(pool, parameter_spec, shards=4), None
    initial = checked_point(root, 1192)
    require(initial['pool_id'] == pool.cache_id and initial['parameter_spec'] == parameter_spec,
        'static plan cannot cross a changed material pool or parameter specification')
    source = initial['task_plan']
    plan = binding.read_ref(source)
    task_cache.validate_plan(plan)  # Metadata identity only; deliberately do not pass the pool.
    registration = pool._manifest.registration
    expected = json.loads(task_cache.json_bytes(dict(task_ids=list(pool.task_ids),
        state_support=registration.state_support, mu=registration.mu, pi0=registration.pi0,
        qualification_registration_id=registration.qualification_registration_id,
        validator_binding_id=registration.validator_binding_id, pool_cache_id=pool.cache_id)))
    require(plan['parameter_spec'] == parameter_spec and plan['global_registration'] == expected
        and plan['task_ids'] == list(pool.task_ids) and plan['shards'] == 4,
        'first-point static plan no longer matches this unchanged complete support')
    return plan, source


def prepare_point(root, step, protocol_id, checkpoint_reference=None, training_root=None, arm='A'):
    directory = point_root(root, step, arm)
    destination = directory/'context/record.json'
    if destination.exists():
        point = checked_point(root, step, arm)
        require(point['protocol_id'] == protocol_id and (checkpoint_reference is None
            or point['source_parent_checkpoint'] == checkpoint_reference), 'existing point source/protocol differs')
        return point
    protocol = checked(Path(root)/'protocol/record.json')
    require(protocol['id'] == protocol_id, 'point protocol changed')
    training, rt = runtime()
    source_context = checked(binding.V75_ROOT/'points/step1192/context/record.json')
    original_training_root = Path(source_context['training_root'])
    require(training_root is None or Path(training_root).resolve() == original_training_root.resolve(), 'foreign material launch')
    science, pool, _prefix, _assets = training.checked_launch(original_training_root)
    initial = (arm == 'A' and step == 1192) or (arm == 'D' and step == 1490)
    source_ref = (initial_checkpoint() if arm == 'A' else fixed_initial_checkpoint()) if initial else _accepted_previous(root, step)
    require(checkpoint_reference is None or checkpoint_reference == source_ref, 'unregistered source endpoint')
    source = read_checkpoint(source_ref, rt)
    require(source['pool_id'] == pool.cache_id and source['prior'] == pool._manifest.registration.pi0,
        'material or fixed prior changed')
    common = _schedule_record(root, source, pool, training)
    if initial:
        state = prepare_state(source, common, rt, arm=arm, step=step)
        evidence = dict(schema='v76_zero_optimizer_complete_state_preparation.v1', protocol_id=protocol_id,
            branch=arm, source_checkpoint=source_ref, source_state_digest=rt.v8._tree_digest(source),
            schedule=binding.entry(Path(root)/'schedule/record.json'),
            actual_prepared_state_digest=rt.v8._tree_digest(state), optimizer_updates=0, model_calls=0,
            changed_components=['schedule','execution_plan'] + (['optimizer.param_groups.lr'] if arm == 'A' else []),
            source_theta_Adam_moments_RNG_pi_prior_and_history_preserved=True,
            actual_CPU_tensor_snapshot=True, old_execution_plan_not_modified=True)
        prepared_ref = _write_prepared_checkpoint(directory/'prepared_state', state, evidence, rt)
        publish(directory/'preparation/record.json',dict(evidence,actual_checkpoint=prepared_ref))
    else:
        state, prepared_ref = source, source_ref
    validate_point_state(state, step, rt, arm=arm, common=common)
    spec = [dict(name=name,shape=list(value.shape),dtype=str(value.dtype)) for name,value in state['parameters'].items()]
    material_ref = _materials_reference()
    material = binding.read_ref(material_ref)
    plan_ref, class_binding, static_plan_source = None, None, None
    if arm == 'A':
        plan, static_plan_source = static_task_plan(root, step, pool, spec)
        require((len(plan['task_ids']),plan['state_count'],plan['package_count'],plan['row_count']) == (744,1360,2468,4974),
            'complete old adjustable support changed')
        publish(directory/'task_plan/record.json',plan)
        plan_ref = binding.entry(directory/'task_plan/record.json')
        class_binding = dict(schema='v76_mixed_actual_point_task_gradient_binding.v1',protocol_id=protocol_id,
            seed=SEED,arm='Full',checkpoint_arm=state['arm'],step=step,checkpoint=prepared_ref,
            pre_state_digest=rt.v8._tree_digest(state),component_digest={key:rt.v8._tree_digest(state[key]) for key in records.COMPONENTS},
            pool_id=pool.cache_id,task_plan_id=plan['id'],parameter_spec=spec,
            demonstration_materials=material_ref,branch=dict(contribution_only=False,b_N=0.2,parameters=rt.v8.PARAMETERS),
            teacher_support_is_fixed_not_new_adjustable_states=True,cross_parameter_point_reuse=False)
    batches = copy.deepcopy(common['schedule']['batches'][step:WINDOWS[step]]) if step in WINDOWS else []
    dose = planned_demonstration_dose(material,batches,pool._manifest.registration.mu) if batches else None
    state_digest = rt.v8._tree_digest(state)
    return publish(destination,dict(schema='v76_actual_paired_mixed_point.v1',protocol_id=protocol_id,seed=SEED,
        branch=arm,step=step,algorithm='Full' if arm=='A' else 'FixedDemo',arm='Full' if arm=='A' else 'FixedDemo',
        temperature=1.0,parent_checkpoint=prepared_ref,source_parent_checkpoint=source_ref,
        parent_state_digest=state_digest,pre_state_digest=state_digest,checkpoint_arm=state['arm'],
        outer_done=list(state['outer_done']),parent_pi=copy.deepcopy(state['pi']),
        fixed_pi=copy.deepcopy(source_context['fixed_pi']),fixed_pi_digest=source_context['fixed_pi_digest'],
        prior=copy.deepcopy(state['prior']),mu=copy.deepcopy(pool._manifest.registration.mu),
        component_digests={key:rt.v8._tree_digest(state[key]) for key in records.COMPONENTS},
        pool_id=pool.cache_id,parameter_spec=spec,task_plan=plan_ref,task_binding=class_binding,
        static_task_plan_source=static_plan_source,static_task_plan_reused=static_plan_source is not None,
        task_cache_root=str(directory/'task_cache'),old_class_context=None,training_root=str(original_training_root),
        demonstration_materials=material_ref,demonstration_policy=material['policy'],
        planned_demonstration_dose=dose,planned_demonstration_per_step=dose['per_step'] if dose else [],
        window_task_batches=batches,window_task_exposures=1488 if batches else 0,
        registered_schedule=binding.entry(Path(root)/'schedule/record.json'),
        original_schedule_sha256=common['schedule']['schedule_sha256'],
        historical_ten_epoch_schedule_sha256=common['original_schedule']['schedule_sha256'],
        fresh_complete_class_required=arm=='A',cross_parameter_point_cache_reuse=False,
        original_outer_history_not_rewritten=True,probe_only=step==1788,
        new_training_arm='Full' if arm=='A' else 'C-only',learning_rate=NEW_LR,
        initial_learning_rate=OLD_LR if arm=='A' and step==1192 else NEW_LR,
        automatic_outer_disabled=True,new_teacher_materials=0,source_V75_material_protocol_id=V75_PROTOCOL_ID))


def checked_point(root, step, arm='A'):
    directory = point_root(root,step,arm); point = checked(directory/'context/record.json')
    require(point['schema']=='v76_actual_paired_mixed_point.v1' and point['seed']==SEED
        and point['step']==step and point['branch']==arm and point['probe_only']==(step==1788)
        and point['learning_rate']==NEW_LR and point['automatic_outer_disabled'] is True
        and point['demonstration_materials']['id']==MATERIAL_ID
        and point['task_cache_root']==str(directory/'task_cache')
        and point['cross_parameter_point_cache_reuse'] is False,'V76 point context changed')
    if arm=='A':
        require(point['task_binding']['pre_state_digest']==point['parent_state_digest'], 'class actual-state binding changed')
    return point


def validate_point_state(state, step, rt, *, arm='A', common=None, applied_at_start=False):
    require(arm in ('A','D') and type(step) is int and 1192<=step<=1788
        and (state['seed'],state['step'])==(SEED,step)
        and state['arm']==('Full' if arm=='A' and (step>1192 or applied_at_start) else 'C-only')
        and state['outer_done']==expected_outer_history(step,arm,applied_at_start=applied_at_start),
        'complete paired state coordinate, checkpoint arm or real outer history changed')
    require(state['model_training'] is True and state['optimizer']['state'] and state['rng']['cuda'],
        'actual complete Adam/training RNG required')
    for value in state['optimizer']['state'].values():
        require(set(value)>={'step','exp_avg','exp_avg_sq'} and int(value['step'].item())==step,
            'actual optimizer cursor or Adam moments differ')
    require(all(x==NEW_LR for x in previous._learning_rates(state['optimizer']))
        and len(state['pi'])==len(state['prior'])==744,'actual low LR or support differs')
    common = common if common is not None else checked(ROOT/'schedule/record.json')
    require(state['schedule']==common['schedule'] and state['execution_plan']==common['execution_plan']
        and state['execution_plan']['epochs']==12 and state['execution_plan']['final_step']==1788
        and state['execution_plan']['outer_steps']==[],'registered new schedule/plan differs')
    validate_distribution(state['pi'],state['prior'])
    if arm=='D':
        original_point = checked(binding.V75_ROOT/'points/step1192/context/record.json')
        require(state['pi']==original_point['fixed_pi'],'fixed continuation changed original pi')
    return state


def validate_evaluation_state(state, step, arm, rt):
    require((arm,step) in {('A',1490),('A',1788),('D',1788)},'unregistered endpoint evaluation')
    return validate_point_state(state,step,rt,arm=arm)


def load_point(root, step, rt, arm='A'):
    point=checked_point(root,step,arm)
    state=read_checkpoint(point['parent_checkpoint'],rt)
    validate_point_state(state,step,rt,arm=arm)
    require(rt.v8._tree_digest(state)==point['parent_state_digest'],'actual complete point differs from context')
    return point,state


def load_cache(root, point, rt):
    require(point['branch']=='A','fixed branch has no class pass')
    from finqa_v76_task_cache import MixedTaskCache
    directory=point_root(root,point['step'])
    return MixedTaskCache(directory/'task_cache',point['task_binding'],binding.read_ref(point['task_plan']),
        point['parameter_spec'],rt,materials=_material_record(point))


def restore_driver(driver, point, state, rt):
    """Use native strict restore with the explicitly registered new state contract."""
    driver.schedule=copy.deepcopy(state['schedule']);driver.execution_plan=copy.deepcopy(state['execution_plan'])
    driver.arm=state['arm'];driver.outer_steps=();driver.final_step=1788
    driver.restore(point['parent_checkpoint']['path'])
    require(rt.v8._tree_digest(driver._payload())==point['parent_state_digest'],
        'cold model/Adam/RNG/pi restoration differs from prepared actual point')


def configure_fixed_window(driver, start):
    require(start in WINDOWS,'terminal probe cannot open a train window')
    driver.outer_steps=();driver.final_step=WINDOWS[start]


def _native_arm(point):
    return 'Full' if point['branch']=='A' else 'C-only'


def latest_window_checkpoint(directory, start, arm='A'):
    require(start in WINDOWS and (arm=='A' or start==1490),'unregistered train recovery coordinate')
    found=[]
    for path in Path(directory).glob('step*_*'):
        match=re.fullmatch(r'step(\d{4})_(outer|step)',path.name)
        require(match is not None and path.is_dir(),'foreign or incomplete V76 train entry')
        step,phase=int(match[1]),match[2]
        require((arm=='A' and phase=='outer' and step in WINDOWS)
            or (phase=='step' and (1193 if arm=='A' else 1491)<=step<=1788),
            'training checkpoint escaped the registered branch dose')
        require((path/'record.json').is_file() and (path/'state.pt').is_file(),'partial checkpoint is not a durable boundary')
        if (step==start and phase=='outer') or (start<step<=WINDOWS[start]):found.append((step,phase=='step',path))
    return max(found,key=lambda row:row[:2])[2] if found else None


def install_demonstration_consumer(driver, point):
    """Reuse V75's actual private native-step adapter and identical mixed consumer."""
    source=previous.install_demonstration_consumer
    namespace=source.__globals__|{'load_demonstrations':load_demonstrations,'consume_task_batch':consume_task_batch,
        'require':require,'__file__':__file__}
    adapter=FunctionType(source.__code__,namespace,source.__name__,source.__defaults__)
    return adapter(driver,point)


def _check_step_report(report, point, step):
    expected=point['window_task_batches'][step-point['step']-1]
    require(report['optimizer_step_calls']==report['clip_calls']==report['zero_grad_calls']==1
        and report['actual_parameter_update'] is True and report['CPU_control_only'] is False
        and report['execution_design']=='v75_original_rows_plus_teacher_suffix_rows'
        and report['supervision_policy']=='v75_exact_teacher_suffix_plus_unchanged_old.v1'
        and report['original_supervision_policy']=='v14_state_independent_original_span_union.v1'
        and report['additional_batch_division'] is False and report['additional_loss_scaling'] is False
        and report['task_batch']['task_ids']==expected['task_ids'] and report['task_batch']['step']==step
        and report['task_batch']['schedule_id']==point['original_schedule_sha256'],
        'actual V76 update differs from inherited V75 consumer/registered schedule')
    actual=report['demonstration_consumption'];planned=point['planned_demonstration_per_step'][step-point['step']-1]
    require(actual['materials_id']==MATERIAL_ID and actual['step']==step
        and actual['student_prefix_target_count']==0 and actual['original_materials_all_rows_consumed'] is True
        and report['demonstration_slots_do_not_renormalize'] is True
        and planned['step']==step and actual['slots']==planned['demonstrations'],
        'actual fixed teacher exposure or prefix-mask contract changed')


def _window_receipts(root, point):
    refs=[];start=point['step'];native=_native_arm(point)
    for step in range(start+1,WINDOWS[start]+1):
        path=branch_root(root,point['branch'])/'training'/f'step{step:04d}_step/record.json'
        record=json.loads(path.read_bytes())
        require((record['step'],record['phase'],record['arm'],record['seed'])==(step,'step',native,SEED)
            and record['pool_id']==point['pool_id'] and record['schedule_sha256']==point['original_schedule_sha256']
            and record['checkpoint_contains_actual_model_Adam_RNG_pi'] is True and (path.parent/'state.pt').is_file(),
            'complete actual V76 optimizer receipt missing or foreign')
        _check_step_report(record['evidence'],point,step)
        refs.append(dict(step=step,record=binding.file_ref(path),state_sha256=record['state_sha256'],
            actual_state_digest=record['actual_state_digest'],update_id=record['evidence']['id'],
            demonstration_consumption=record['evidence']['demonstration_consumption']))
    return refs


def summarize_consumption(point, ledger):
    from collections import Counter
    planned=point['planned_demonstration_dose'];totals=Counter();slots=Counter()
    require(len(ledger)==298,'complete window needs298 actual receipts')
    for row,expected in zip(ledger,planned['per_step'],strict=True):
        actual=row['demonstration_consumption']
        require(row['step']==expected['step'] and actual['slots']==expected['demonstrations'],
            'actual teacher dose differs from the predeclared per-step slots')
        for key in ('teacher_target_tokens','teacher_input_positions','teacher_microbatches','teacher_trajectories'):totals[key]+=actual[key]
        for slot in actual['slots']:slots[slot['slot']]+=1
    require(totals['teacher_target_tokens']==sum(planned['planned_teacher_target_tokens'].values())
        and totals['teacher_input_positions']==sum(planned['planned_teacher_input_positions'].values())
        and totals['teacher_microbatches']==sum(planned['planned_teacher_microbatches'].values()),
        'actual target/input/microbatch totals differ from fixed material plan')
    return dict(schema='v76_complete_actual_fixed_teacher_consumption.v1',status='PASS',material_id=MATERIAL_ID,
        updates=298,task_exposures=1488,**dict(totals),teacher_trajectory_exposures_by_slot=dict(slots),
        all298_actual_receipts_match_frozen_slots=True,fixed_missing_slot_mass_retained_in_old=True,
        student_prefix_target_count=0,original_task_frequency_unchanged=True,
        extra_forward_RNG_not_bitwise_paired_to_B=True,teacher_mass_independent_of_adaptive_pi=True)


def _contract(point,q,rt,distribution_source):
    return dict(schema='v76_fixed_q_mixed_window_binding.v1',protocol_id=point['protocol_id'],
        point_context_id=point['id'],parent_state_digest=point['parent_state_digest'],seed=SEED,
        branch=point['branch'],arm=_native_arm(point),start_step=point['step'],end_step=WINDOWS[point['step']],
        distribution_digest=rt.v8._tree_digest(q),distribution_source=distribution_source,
        parent_training_rng_digest=point['component_digests']['rng'],original_task_schedule_sha256=point['original_schedule_sha256'],
        registered_schedule=point['registered_schedule'],demonstration_materials=point['demonstration_materials'],
        learning_rate=NEW_LR,outer_schedule_during_window=[],optimizer_updates=298,task_exposures=1488,
        outer_updates=int(point['branch']=='A'),initial_checkpoint_arm=point['checkpoint_arm'])


def _validate_completed(point,completed,q,rt):
    require(completed['schema']=='v76_paired_mixed_window_complete.v1' and completed['status']=='COMPLETE'
        and completed['protocol_id']==point['protocol_id'] and completed['point_context_id']==point['id']
        and completed['branch']==point['branch'] and completed['initial_step']==point['step']
        and completed['final_step']==WINDOWS[point['step']] and completed['optimizer_updates']==completed['new_optimizer_updates']==298
        and completed['task_exposures']==1488 and completed['outer_updates']==int(point['branch']=='A')
        and completed['learning_rate']==NEW_LR and completed['distribution_digest']==rt.v8._tree_digest(q)
        and completed['demonstration_materials']==point['demonstration_materials']
        and completed['actual_demonstration_consumption']['status']=='PASS'
        and completed['actual_demonstration_consumption']['material_id']==MATERIAL_ID,
        'completed actual window state/dose/teacher binding changed')
    return completed


def restore_completed_window(point,completed,driver,q,rt):
    _validate_completed(point,completed,q,rt)
    require(checkpoint_ref(completed['final_checkpoint']['path'])==completed['final_checkpoint'], 'completed actual endpoint bytes changed')
    driver.arm=_native_arm(point);configure_fixed_window(driver,point['step'])
    driver.restore(completed['final_checkpoint']['path'])
    payload=driver._payload();validate_point_state(payload,completed['final_step'],rt,arm=point['branch'])
    require(driver.pi==q and rt.v8._tree_digest(payload)==completed['final_checkpoint']['actual_state_digest'],
        'completed actual theta/Adam/RNG/pi did not restore exactly')
    return completed


def execute_training(root,point,state,driver,q,*,rt,monitor,distribution_source=None,resource_report=None):
    start=point['step'];arm=point['branch']
    require(start in WINDOWS and point['probe_only'] is False and (arm=='A' or start==1490),
        'terminal1788 must never apply a third outer or train')
    validate_distribution(q,state['pi'])
    if arm=='D':require(q==point['fixed_pi'],'D may not adopt a Full candidate')
    expected_root=branch_root(root,arm)/'training'
    require(driver.root.resolve()==expected_root.resolve(),'training output escaped the independent branch')
    directory=point_root(root,start,arm)/'train';contract=_contract(point,q,rt,distribution_source)
    publish(directory/'binding/record.json',contract)
    require(not (directory/'completed/record.json').exists(),'completed window cannot execute again')
    configure_fixed_window(driver,start)
    latest=latest_window_checkpoint(driver.root,start,arm)
    history=[*state['outer_done'],start] if arm=='A' else list(state['outer_done'])
    if latest is None:
        require(rt.v8._tree_digest(driver._payload())==point['parent_state_digest'], 'real parent must restore before training')
        if arm=='A':
            monitor.check_stop('before_explicit_V76_Full_outer_commit',step=start)
            driver.arm='Full';driver.pi=copy.deepcopy(q);driver.outer_done=list(history)
            after=driver._payload()
            for name in records.COMPONENTS:
                if name not in ('arm','pi','outer_done'):
                    require(rt.v8._tree_digest(after[name])==rt.v8._tree_digest(state[name]), 'outer changed actual component '+name)
            require(previous._learning_rates(after['optimizer'])==[NEW_LR]*len(after['optimizer']['param_groups']), 'outer changed learning rate')
            driver.commit('outer',dict(**contract,optimizer_steps_performed=0,explicit_applied_update=True,
                original_driver_outer_update_called=False,parent_checkpoint_arm=state['arm'],checkpoint_arm='Full'))
    else:
        driver.arm=_native_arm(point);driver.restore(latest)
    require(driver.pi==q and driver.outer_done==history and start<=driver.step_index<=WINDOWS[start], 'durable window/q/history changed')
    install_demonstration_consumer(driver,point);began=driver.step_index
    while driver.step_index<WINDOWS[start]:
        monitor.check_stop('before_real_V76_mixed_sft_update',step=driver.step_index+1)
        require(driver.outer_steps==() and driver.pi==q and driver.outer_done==history
            and all(group['lr']==NEW_LR for group in driver.optimizer.param_groups), 'window fixed q/LR/history changed')
        report=driver.step();_check_step_report(report,point,driver.step_index)
        require(driver.pi==q and driver.outer_done==history and all(group['lr']==NEW_LR for group in driver.optimizer.param_groups),
            'actual update changed fixed window q/LR/history')
        monitor.clear_unused('V76_sft_committed_step%04d'%driver.step_index)
    final=driver._payload();validate_point_state(final,WINDOWS[start],rt,arm=arm)
    reference=checkpoint_ref(driver.root/f'step{WINDOWS[start]:04d}_step')
    require(rt.v8._tree_digest(final)==reference['actual_state_digest'], 'actual live endpoint differs from final checkpoint')
    ledger=_window_receipts(root,point)
    return publish(directory/'completed/record.json',dict(schema='v76_paired_mixed_window_complete.v1',status='COMPLETE',
        protocol_id=point['protocol_id'],point_context_id=point['id'],seed=SEED,branch=arm,arm=_native_arm(point),
        checkpoint_arm=_native_arm(point),initial_step=start,final_step=WINDOWS[start],optimizer_updates=298,new_optimizer_updates=298,
        task_exposures=1488,outer_updates=int(arm=='A'),outer_done=history,learning_rate=NEW_LR,fixed_distribution=arm=='D',
        outer_checkpoint=checkpoint_ref(driver.root/f'step{start:04d}_outer') if arm=='A' else None,
        final_checkpoint=reference,snapshots={str(WINDOWS[start]):reference},distribution_digest=contract['distribution_digest'],
        updates_in_final_worker=WINDOWS[start]-began,next_outer_automatically_executed=False,
        training_binding=binding.entry(directory/'binding/record.json'),demonstration_materials=point['demonstration_materials'],
        planned_demonstration_dose=point['planned_demonstration_dose'],update_receipts=ledger,
        actual_demonstration_consumption=summarize_consumption(point,ledger),resources=resource_report() if resource_report else None))


def job_spec(step=1490,stage='train',arm='D'):
    require(stage=='train' and arm in ('A','D') and step in WINDOWS and (arm=='A' or step==1490), 'unregistered train job')
    name=f'step{step}.train' if arm=='A' else 'D.step1490.train'
    return dict(id=name,job_id=name,seed=SEED,step=step,stage='train',kind='train',memory_phase='train',
        arm='Full' if arm=='A' else 'FixedDemo',branch=arm,fixed_distribution=arm=='D',learning_rate=NEW_LR,
        outer_updates=int(arm=='A'))


def execute_fixed(root,job,attempt_root,guard):
    require(job['job_id']=='D.step1490.train' and job['step']==1490, 'only one D continuation authorized')
    training,rt=runtime();point,state=load_point(root,1490,rt,arm='D')
    _science,pool,_prefix,assets=training.checked_launch(point['training_root'])
    require(point['protocol_id']==guard.protocol['id'],'D worker resource protocol differs')
    monitor=binding.source_v72('runtime').ScientificMonitor(guard,cooperative_replay=False)
    monitor.check_stop('before_actual_D_model_load')
    model,tokenizer,optimizer,scope,_fresh=rt.launcher._load_components(assets,SEED)
    driver=training.adapters().TrainingDriver(model,optimizer,pool,root=branch_root(root,'D')/'training',
        seed=SEED,arm=state['arm'],device='cuda:0',tokenizer=tokenizer,adapter_scope=scope,feedback_collector=None)
    restore_driver(driver,point,state,rt);monitor.clear_unused('after_exact_D_S1490_restore_and_registered_plan')
    completed_path=point_root(root,1490,'D')/'train/completed/record.json'
    done=restore_completed_window(point,checked(completed_path),driver,point['fixed_pi'],rt) if completed_path.exists() else execute_training(
        root,point,state,driver,point['fixed_pi'],rt=rt,monitor=monitor,
        distribution_source=point['source_parent_checkpoint'],resource_report=guard.report)
    monitor.clear_unused('D_training_complete')
    del driver,model,tokenizer,optimizer,pool,state
    gc.collect();rt.torch.cuda.empty_cache();monitor.snapshot('after_model_release',boundary=True)
    return dict(branch_result=binding.entry(completed_path),initial_step=1490,final_step=1788,optimizer_updates=298,
        new_optimizer_updates=298,outer_updates=0,applied=False,fixed_distribution=True,learning_rate=NEW_LR,
        final_checkpoint=done['final_checkpoint'],demonstration_materials=point['demonstration_materials'],
        actual_demonstration_consumption=done['actual_demonstration_consumption'],point_context_id=point['id'],
        parent_state_digest=point['parent_state_digest'],seed=SEED,step=1490,stage='train',branch='D',arm='FixedDemo',
        new_feedback_sessions=0,new_class_passes=0,new_response_replay=0,new_VJP=0,model_released=True)


def audit_training_resume(root,job):
    arm='D' if job['job_id'].startswith('D.') else 'A';start=job['step'];point=checked_point(root,start,arm)
    directory=point_root(root,start,arm)/'train';evidence=[binding.entry(point_root(root,start,arm)/'context/record.json')]
    checkpoint=latest_window_checkpoint(branch_root(root,arm)/'training',start,arm)
    progress=0
    if checkpoint is not None:
        require((directory/'binding/record.json').exists(),'durable actual training lacks its registered window binding')
        contract=checked(directory/'binding/record.json');record=json.loads((checkpoint/'record.json').read_bytes())
        require(contract['protocol_id']==point['protocol_id'] and contract['point_context_id']==point['id']
            and contract['branch']==arm and contract['start_step']==start and contract['end_step']==WINDOWS[start]
            and record['arm']==_native_arm(point) and record['pool_id']==point['pool_id']
            and record['schedule_sha256']==point['original_schedule_sha256'],'durable training binding changed')
        binding.source_module('finqa_v63_worker_audit')._state_metadata(checkpoint,record)
        evidence.extend([binding.entry(directory/'binding/record.json'),binding.file_ref(checkpoint/'record.json')])
        progress=record['step']-start+int(arm=='A')
    result_path=directory/'result/record.json'
    if result_path.exists():
        validate_training_result(root,job,checked(result_path));evidence.append(binding.entry(result_path))
    return dict(resume_allowed=True,unknown_calls=0,progress_units=progress,evidence=evidence,
        complete_stage=result_path.exists(),full_tensor_validation_before_cold_scientific_use=True,
        durable_progress_digest=binding.digest(dict(progress_units=progress,evidence=evidence)))


def validate_training_result(root,job,result):
    arm='D' if job['job_id'].startswith('D.') else 'A';point=checked_point(root,job['step'],arm)
    done_path=point_root(root,job['step'],arm)/'train/completed/record.json';done=checked(done_path)
    require(result['branch_result']==binding.entry(done_path) and result['final_checkpoint']==done['final_checkpoint']
        and result['optimizer_updates']==result['new_optimizer_updates']==298
        and result['outer_updates']==int(arm=='A') and result['final_step']==WINDOWS[job['step']]
        and done['protocol_id']==point['protocol_id'] and done['status']=='COMPLETE'
        and done['actual_demonstration_consumption']['status']=='PASS'
        and done['actual_demonstration_consumption']['all298_actual_receipts_match_frozen_slots'] is True,
        'actual mixed training result or dose differs')
    return done


def training_contract():
    return dict(schema='v76_paired_two_window_fixed_teacher_training.v1',seed=SEED,common_parent_step=1192,
        logical_updates_per_path=596,new_A_updates=596,new_D_updates=298,new_optimizer_updates=894,
        reused_D_first_window_updates=298,new_task_exposures=4464,learning_rate=NEW_LR,
        A_windows=[[1193,1490],[1491,1788]],D_new_window=[1491,1788],
        A_explicit_outer_steps=[1192,1490],terminal_probe_step=1788,terminal_probe_applied=False,
        same_registered_task_schedule_for_both_arms=True,new_epochs=[11,12],new_window_task_exposures=1488,
        old_execution_plan_rewritten=False,frozen_teacher_material_id=MATERIAL_ID,new_teacher_materials=0,
        teacher_slots_fixed_and_not_new_adjustable_states=True,teacher_weights=['1/4','1/4'],
        old_task_mass='1-1/4*I_initial-1/4*I_post',c_x_applied_once=True,
        mixed_row_consumer='exact frozen V75 consume_task_batch',automatic_driver_outer_disabled=True,
        preparation_changes_only=['A.initial.optimizer.param_groups.lr','schedule','execution_plan'],
        preparation_optimizer_updates=0,complete_cpu_tensor_preparation_explicit=True,
        actual_Adam_RNG_prior_and_parameters_preserved_before_real_learning=True,
        all_new_windows_have298_actual_consumption_receipts=True,student_prefix_target_count=0,
        fixed_missing_slot_mass_retained_in_old=True,new_teacher_search=0,same_inner_dose_not_same_total_compute=True)
