"""Read-only V70 weight, supervision and applied-direction analysis for V71.

Only saved JSON is consumed. No scientific runtime, tensors, model, scorer,
tokenizer, distribution update or gradient routine is imported or rerun.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from fractions import Fraction
import hashlib
import json
import math
import os
from pathlib import Path
import re
import tempfile

REPO = Path('/data1/zhuxinrui/projects/Data-Synthesis')
V18 = REPO / 'trusted_data_synthesis/artifacts/finance_research_20260928/finqa_v6_01/v18_researcher_continuation_01'
V70 = V18 / 'v70_full_closed_loop_01'
ROOT = V18 / 'v71_fixed_distribution_control_01'
LAYERS = ('reason', 'tool', 'final')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
        separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def number(value):
    require(not isinstance(value, bool), 'boolean is not a numeric measure')
    value = float(Fraction(value)) if isinstance(value, str) else float(value)
    require(math.isfinite(value), 'nonfinite saved measure')
    return value


class Reader:
    """One necessary input pass; retain references rather than large encodings."""
    def __init__(self):
        self.sources = {}

    def read(self, path, expected=None):
        path = Path(path).resolve()
        require(str(path) not in self.sources, 'input would be read redundantly: ' + str(path))
        raw = path.read_bytes()
        value = json.loads(raw)
        sha = hashlib.sha256(raw).hexdigest()
        if expected:
            require(sha == expected['sha256'], 'bound input bytes changed: ' + str(path))
            if expected.get('id'):
                require(expected['id'] == value.get('id', value.get('encoding_id')),
                        'bound input identity changed')
        self.sources[str(path)] = dict(path=str(path), sha256=sha,
                                      id=value.get('id', value.get('encoding_id')))
        return value

    def ref(self, reference):
        return self.read(reference['path'], reference)


def scalar_summary(values):
    values = sorted(number(value) for value in values)
    require(values, 'empty descriptive summary')
    def quantile(p):
        coordinate = p * (len(values) - 1)
        low = int(coordinate)
        return values[low] + (values[min(low + 1, len(values)-1)]-values[low]) * (coordinate-low)
    return dict(n=len(values), mean=math.fsum(values)/len(values), minimum=values[0],
                p25=quantile(.25), median=quantile(.5), p75=quantile(.75), maximum=values[-1])


def delta_distribution(new, old):
    require(set(new) == set(old), 'distribution task support differs')
    result = {}
    for task in sorted(old):
        require(set(new[task]) == set(old[task]), 'distribution state support differs')
        result[task] = {state: number(new[task][state])-number(old[task][state])
                        for state in sorted(old[task])}
    return result


def direction_support(C, direction):
    """C already contains task mass: never multiply mu a second time."""
    require(set(C) == set(direction), 'contribution support differs')
    per_task = {}
    for task, row in direction.items():
        require(set(C[task]) == set(row), 'contribution state support differs')
        per_task[task] = math.fsum(number(C[task][state])*value for state, value in row.items())
    total = math.fsum(per_task.values())
    return dict(score=total, sign='positive' if total > 0 else 'negative' if total < 0 else 'zero',
                per_task=per_task, formula='sum_xz C[x,z] * (candidate[x,z]-current[x,z])',
                task_mass_multiplied_again=False)


def contribution_cosines(first, second, pi, mu, controls):
    coordinates = [(task, state) for task in sorted(pi) if task not in controls for state in sorted(pi[task])]
    def cosine(weighted):
        products, first_sq, second_sq = [], [], []
        for task, state in coordinates:
            mass = number(mu[task])
            a, b = number(first[task][state]), number(second[task][state])
            if weighted:
                a, b = a/mass, b/mass
                weight = mass * number(pi[task][state])
            else:
                weight = 1.0
            products.append(weight*a*b); first_sq.append(weight*a*a); second_sq.append(weight*b*b)
        aa, bb = math.fsum(first_sq), math.fsum(second_sq)
        return dict(cosine=math.fsum(products)/math.sqrt(aa*bb) if aa and bb else None,
                    inner_product=math.fsum(products), first_squared_norm=aa, second_squared_norm=bb,
                    status='DEFINED' if aa and bb else 'UNDEFINED_ZERO_NORM')
    return dict(coordinates=len(coordinates), excluded_control_tasks=len(controls),
        RMS_metric=cosine(True), raw_C_Euclidean=cosine(False),
        RMS_metric_definition='mu(x)*pi(z|x) weighted inner product of C/mu on noncontrol tasks; common normalization cancels')


def analyze_directions(diag, *, step):
    formal, draws = diag['formal'], diag['draws']
    current, candidate = formal['current'], formal['formal_q']
    direction = delta_distribution(candidate, current)
    Cs = {'formal700': formal['frozen_inputs']['C'],
          **{draw: value['frozen_inputs']['C'] for draw, value in draws.items()}}
    evaluation = {key: direction_support(C, direction) for key, C in Cs.items()}
    cross = {source: {evaluator: direction_support(C, delta_distribution(value['formal_q'], current))
                     for evaluator, C in Cs.items()}
             for source, value in draws.items()}
    frozen = formal['frozen_inputs']
    return dict(step=step, applied_to_training=step in (894, 1192),
        actual_direction_support=evaluation, draw_candidate_support=cross,
        draw_contribution_cosines=contribution_cosines(Cs['101'], Cs['103'], current,
                                                     formal['mu'], set(frozen['control_tasks'])),
        all_700_feedback_used_by_formal_q=True, half_draw_support_is_independent_confirmation=False,
        predicts_298_step_accuracy=False, different_point_scores_must_not_be_added=True,
        terminal_probe_cannot_cause_prior_training=step == 1490)


def log_odds_decomposition(diag):
    formal = diag['formal']; frozen = formal['frozen_inputs']
    pi, q, prior = formal['current'], formal['formal_q'], frozen['prior']
    params = frozen['parameters']; regularizer = params['lambda_current']+params['lambda_prior']
    eps, TN = params['epsilon'], params['novelty_temperature']
    rows, errors = [], []
    for task in sorted(pi):
        if len(pi[task]) == 1:
            continue
        anchor = sorted(pi[task])[0]
        p, r, next_p = ({state: number(v) for state, v in item[task].items()}
                        for item in (pi, prior, q))
        novelty = {state: eps+(1-2*eps)*(-math.expm1(-max(0., math.log(r[state]/p[state]))/TN)) for state in p}
        ct = frozen['C_tilde'][task]
        for state in sorted(p):
            prior_part = params['lambda_prior']/regularizer * (math.log(r[state]/r[anchor])-math.log(p[state]/p[anchor]))
            C_part = params['contribution_exponent']/regularizer*math.log(ct[state]/ct[anchor])
            N_part = params['novelty_exponent']/regularizer*math.log(novelty[state]/novelty[anchor])
            observed = math.log(next_p[state]/next_p[anchor])-math.log(p[state]/p[anchor])
            residual = observed-prior_part-C_part-N_part
            errors.append(abs(residual))
            rows.append(dict(task_id=task, state_id=state, reference_state=anchor,
                observed_log_odds_change=observed, prior_retraction=prior_part,
                Contribution=C_part, Novelty=N_part, residual=residual))
    require(max(errors, default=0.) < 1e-12, 'saved applied q log-odds algebra differs')
    return dict(reference='lexicographically first state within each task',
        decomposition='Delta log(q_s/q_a) = prior retraction + Contribution + Novelty',
        maximum_absolute_residual=max(errors, default=0.), rows=rows,
        is_accuracy_causal_decomposition=False, distribution_recomputed=False)


def encoding_features(encoding, package):
    counts = {layer: 0 for layer in LAYERS}
    actions, eos = [], 0
    for row in encoding['rows']:
        positions = row['layer_target_positions']
        require(set(positions) == set(LAYERS), 'unknown supervision layers')
        for layer in LAYERS:
            counts[layer] += len(positions[layer])
        require(sum(len(v) for v in positions.values()) == len(row['target_ids']),
                'layer positions do not partition original selected targets')
        eos += int(row['student_eos_supervised'])
        # This is the saved original native rendering, not fresh parsing/scoring.
        text = row['rendered_response']
        for block in re.findall(r'<tool_call>\s*(.*?)\s*</tool_call>', text, re.S):
            action = json.loads(block)
            require(isinstance(action.get('name'), str), 'saved tool rendering lacks name')
            actions.append(dict(name=action['name'], argument_keys=sorted(action.get('arguments', {}))))
    require(counts == encoding['layer_target_counts'] and sum(counts.values()) == encoding['L_P']
            == package['whole_package_target_tokens'], 'saved whole-package mask denominator changed')
    require(encoding['slot_id'] == package['package_id'] and encoding['task_id'] == package['task_id'],
            'original encoding package binding differs')
    names = [a['name'] for a in actions]
    return dict(**package, layer_target_counts=counts,
        layer_token_fraction={key: value/encoding['L_P'] for key, value in counts.items()},
        response_rows=len(encoding['rows']), total_sequence_tokens=encoding['total_sequence_tokens'],
        max_sequence_tokens=encoding['max_sequence_tokens'], supervised_EOS=eos,
        action_names=names, action_sequence='>'.join(names) if names else 'NO_PARSED_TOOL_ACTION',
        terminal_action=names[-1] if names else None,
        terminal_argument_keys=actions[-1]['argument_keys'] if actions else [],
        run_program_count=names.count('run_program'), submit_program_count=names.count('submit_program'),
        action_description_source='saved rendered_response native tool_call JSON',
        public_reasoning_quality_inferred=False)


def nominal_window(receipts, pi, packages, *, compare_actual=False):
    totals = Counter({layer: 0. for layer in LAYERS})
    state_mass, task_mass, package_mass, actions = defaultdict(float), defaultdict(float), defaultdict(float), defaultdict(float)
    coefficient_error = 0.
    for row in receipts:
        evidence = row['evidence']; batch_size = evidence['batch_size']
        require(batch_size == len(evidence['task_batch']['task_ids']), 'actual tail batch size differs')
        for package in evidence['packages']:
            task, state, sid = package['task_id'], package['state_id'], package['package_id']
            data = packages[sid]
            coefficient = number(pi[task][state])/(batch_size*package['n_state']*data['whole_package_target_tokens'])
            if compare_actual:
                coefficient_error = max(coefficient_error, abs(coefficient-number(package['target_token_coefficient'])))
            mass = coefficient*data['whole_package_target_tokens']
            task_mass[task] += mass; state_mass[(task,state)] += mass; package_mass[sid] += mass
            actions[data['action_sequence']] += mass
            for layer in LAYERS:
                totals[layer] += coefficient*data['layer_target_counts'][layer]
    total = math.fsum(totals.values())
    require(math.isclose(total, len(receipts), rel_tol=0, abs_tol=1e-9), 'nominal coefficients do not sum to one per update')
    if compare_actual:
        require(coefficient_error <= 1e-15, 'analysis disagrees with saved actual package coefficient')
    return dict(optimizer_updates=len(receipts), task_exposures=sum(r['evidence']['batch_size'] for r in receipts),
        tail_batch_sizes=dict(sorted(Counter(r['evidence']['batch_size'] for r in receipts).items())),
        total_nominal_supervision_coefficient=total,
        layer_coefficients=dict(totals), layer_shares={key:value/total for key,value in totals.items()},
        task_coefficients=dict(task_mass),
        state_coefficients=[dict(task_id=t,state_id=s,coefficient=v) for (t,s),v in sorted(state_mass.items())],
        package_coefficients=dict(package_mass),
        action_sequence_coefficients=dict(sorted(actions.items())),
        maximum_actual_coefficient_discrepancy=coefficient_error if compare_actual else None,
        formula='sum_actual_batches pi(x,z)/(actual_B*n_xz*L_P) * selected_layer_tokens(P)',
        is_actual_layer_loss_or_gradient_contribution=False)


def movement(old, new, mu, packages):
    direction = delta_distribution(new, old)
    by_state = defaultdict(list)
    for data in packages.values():
        by_state[data['task_id'],data['state_id']].append(data)
    states, tasks = [], []
    for task, row in direction.items():
        tv = .5*math.fsum(abs(v) for v in row.values())
        tasks.append(dict(task_id=task, TV=tv, joint_moved_mass=number(mu[task])*tv))
        for state,value in row.items():
            group = by_state[task,state]
            states.append(dict(task_id=task,state_id=state,old_probability=number(old[task][state]),
                new_probability=number(new[task][state]),delta_probability=value,
                delta_joint_mass=number(mu[task])*value,package_count=len(group),
                mean_target_tokens=math.fsum(p['whole_package_target_tokens'] for p in group)/len(group),
                mean_response_rows=math.fsum(p['response_rows'] for p in group)/len(group),
                mean_run_program_count=math.fsum(p['run_program_count'] for p in group)/len(group),
                mean_submit_program_count=math.fsum(p['submit_program_count'] for p in group)/len(group),
                layer_fraction_mean={layer:math.fsum(p['layer_token_fraction'][layer] for p in group)/len(group) for layer in LAYERS},
                action_sequences=dict(Counter(p['action_sequence'] for p in group)),
                terminal_structures=dict(Counter(str(p['terminal_action'])+':'+','.join(p['terminal_argument_keys']) for p in group)),
                package_ids=[p['package_id'] for p in group]))
    ranked = sorted(tasks,key=lambda row:(-row['joint_moved_mass'],row['task_id']))
    total=math.fsum(row['joint_moved_mass'] for row in ranked)
    positive=sorted((s for s in states if s['delta_joint_mass']>0),key=lambda r:(-r['delta_joint_mass'],r['task_id'],r['state_id']))
    negative=sorted((s for s in states if s['delta_joint_mass']<0),key=lambda r:(r['delta_joint_mass'],r['task_id'],r['state_id']))
    def number_for_share(fraction):
        partial=0.
        for index,task in enumerate(ranked,1):
            partial+=task['joint_moved_mass']
            if partial>=fraction*total:
                return index
        return 0
    return dict(all_task_weighted_TV=total, adjustable_task_normalized_TV=total/math.fsum(number(mu[t]) for t in old if len(old[t])>1),
        top_task_movement_share={str(k):math.fsum(r['joint_moved_mass'] for r in ranked[:k])/total if total else 0. for k in (1,5,10,20,50)},
        tasks_for_half_movement=number_for_share(.5), tasks_for_90pct_movement=number_for_share(.9),
        top20_gaining_states=positive[:20],top20_losing_states=negative[:20],tasks=ranked,states=states)


def training_dynamics(receipts):
    rows=[]
    for row in receipts:
        evidence=row['evidence']; losses={p['package_id']:p for p in evidence['package_losses']}
        total=math.fsum(number(p['target_token_coefficient'])*number(losses[p['package_id']]['target_nll_sum']) for p in evidence['packages'])
        rows.append(dict(step=row['step'],batch_size=evidence['batch_size'],
            saved_weighted_package_NLL=total,preclip_gradient_norm=evidence['preclip_gradient_norm'],
            clip_threshold_exceeded=number(evidence['preclip_gradient_norm'])>1.,
            target_tokens=evidence['target_tokens'],sequence_tokens=evidence['sequence_tokens']))
    return dict(steps=rows, actual_saved_training_loss_available=True,
        weighted_package_NLL=scalar_summary(r['saved_weighted_package_NLL'] for r in rows),
        preclip_gradient_norm=scalar_summary(r['preclip_gradient_norm'] for r in rows),
        clipping_threshold_exceeded_updates=sum(r['clip_threshold_exceeded'] for r in rows),
        first30_mean_NLL=math.fsum(r['saved_weighted_package_NLL'] for r in rows[:30])/len(rows[:30]),
        last30_mean_NLL=math.fsum(r['saved_weighted_package_NLL'] for r in rows[-30:])/len(rows[-30:]),
        layerwise_loss_and_gradient_contribution_saved=False,new_model_computation=False)


def build_analysis(v70=V70):
    reader=Reader(); v70=Path(v70)
    closeout=reader.read(v70/'closeout/record.json')
    require(closeout['status']=='COMPLETE','V70 must be complete before outcome-bound analysis')
    points={step:reader.read(v70/f'points/step{step:04d}/context/record.json') for step in (894,1192,1490)}
    diagnostics={step:reader.read(v70/f'points/step{step:04d}/distribution/frozen_diagnostics/record.json') for step in points}
    pi0=points[894]['parent_pi']; q1=diagnostics[894]['formal']['formal_q']; q2=diagnostics[1192]['formal']['formal_q']
    require(points[1192]['parent_pi']==q1 and points[1490]['parent_pi']==q2,
            'saved Full q not bound to actual following training endpoints')
    require(pi0==diagnostics[894]['formal']['current'],'pi0 must be actual pre-Full distribution')
    receipts={start:[reader.read(v70/f'training/step{step:04d}_step/record.json') for step in range(start+1,start+299)] for start in (894,1192)}
    package_meta={}
    for start,window in receipts.items():
        for step,row in zip(range(start+1,start+299),window,strict=True):
            ev=row['evidence']
            require(row['step']==step and row['schedule_sha256']==points[894]['original_schedule_sha256']
                    and ev['clip_calls']==ev['optimizer_step_calls']==1 and ev['actual_parameter_update'] is True,
                    'actual saved update or original schedule differs')
            for p in ev['packages']:
                item={key:p[key] for key in ('package_id','task_id','state_id','n_state','whole_package_target_tokens')}
                require(p['package_id'] not in package_meta or package_meta[p['package_id']]==item,'package support changed')
                package_meta[p['package_id']]=item
    require(len(package_meta)==2468,'complete original package set required')
    plan=reader.read(Path(points[894]['training_root'])/'registration/record.json')
    material=reader.ref(plan['material_binding'])
    require(material['id']==points[894]['pool_id'] and set(material['encodings'])==set(package_meta),
            'wrong original material encoding support')
    def load_package(item):
        sid,meta=item
        return sid,encoding_features(reader.ref(material['encodings'][sid]),meta)
    with ThreadPoolExecutor(max_workers=8) as workers:
        packages=dict(workers.map(load_package,sorted(package_meta.items())))
    nominal={}; dynamics={}
    for start,q in ((894,q1),(1192,q2)):
        fixed=nominal_window(receipts[start],pi0,packages)
        full=nominal_window(receipts[start],q,packages,compare_actual=True)
        nominal[str(start)]=dict(Full=full, fixed_pi0=fixed,
            Full_minus_fixed_layer_share={layer:full['layer_shares'][layer]-fixed['layer_shares'][layer] for layer in LAYERS},
            fixed_is_nominal_counterfactual_not_executed_loss=True)
        dynamics[str(start)]=training_dynamics(receipts[start])
    body=dict(schema='v71_existing_weights_supervision_contribution_analysis.v1',
        status='COMPLETE_EXISTING_PRODUCT_ANALYSIS', v70_root=str(v70),
        source_implementation=dict(path=str(Path(__file__).resolve()),sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()),
        actual_parent_state_digest=points[894]['parent_state_digest'],
        actual_pi0_digest=digest(pi0),pi0_definition='actual C1/b1 distribution at parent step894 before first V70 Full update',
        distributions=dict(pi0=pi0,q1=q1,q2=q2),
        movement=dict(q1_minus_pi0=movement(pi0,q1,points[894]['mu'],packages),
                      q2_minus_q1=movement(q1,q2,points[894]['mu'],packages),
                      q2_minus_pi0=movement(pi0,q2,points[894]['mu'],packages)),
        nominal_supervision_by_window=nominal,
        package_features=packages,
        applied_direction_diagnostics={str(step):analyze_directions(diag,step=step) for step,diag in diagnostics.items()},
        applied_log_odds_decomposition={str(step):log_odds_decomposition(diagnostics[step]) for step in (894,1192)},
        existing_Full_training_dynamics=dynamics,
        scientific_operations=dict(model_forward=0,backward=0,VJP=0,optimizer_updates=0,
            new_feedback=0,API_calls=0,new_scoring=0,Tensor_loads=0,distribution_map_iterations=0),
        original_artifacts_written=0,
        interpretation_limits=['Nominal mask coefficient shares are not layer loss or gradient shares.',
          'Saved whole-package NLL and preclip norms describe the existing Full path only.',
          'The formal direction used all700 feedback; halfdraw support is not independent confirmation.',
          'Scores at distinct parameter points must not be summed as multiwindow predicted benefit.',
          'The1490 contribution was never used for training and cannot explain the earlier decline.',
          'Algebraic C/N log-odds decomposition is not a decomposition of accuracy causality.'],
        sources=[reader.sources[key] for key in sorted(reader.sources)])
    return dict(body,id=digest(body))


def publish(value, output):
    output=Path(output).resolve()
    require(output.is_relative_to(ROOT.resolve()) or output.is_relative_to(Path('/tmp')),
            'analysis may only publish in independent V71 scope or scratch')
    if output.is_relative_to(ROOT.resolve()):
        require((ROOT/'protocol/record.json').is_file(),'V71 must be prepared before analysis publication')
    raw=(json.dumps(value,sort_keys=True,ensure_ascii=False,indent=2,allow_nan=False)+'\n').encode()
    if output.exists():
        require(output.read_bytes()==raw,'immutable existing analysis differs')
        return
    output.parent.mkdir(parents=True,exist_ok=True)
    fd,temp=tempfile.mkstemp(prefix='.analysis-',dir=output.parent)
    try:
        with os.fdopen(fd,'wb') as stream:
            stream.write(raw);stream.flush();os.fsync(stream.fileno())
        os.link(temp,output)
    finally:
        Path(temp).unlink(missing_ok=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ROOT/'existing_mechanism_analysis/record.json')
    args=parser.parse_args()
    result=build_analysis()
    publish(result,args.output)
    print(json.dumps(dict(status=result['status'],id=result['id'],output=str(args.output),
        sources=len(result['sources']),scientific_operations=result['scientific_operations']),ensure_ascii=False))


if __name__=='__main__':
    main()
