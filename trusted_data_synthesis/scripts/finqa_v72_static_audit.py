"""Bounded saved-content checks for V72; no model, scorer execution, or repair.

The launch gate inspects the actual registered Student token arrays and masks.
Its companion analysis joins saved whole-package losses and native outcome rows.
Neither operation changes a scientific artifact or expands the training budget.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from fractions import Fraction
import hashlib
import importlib
import json
import math
import os
from pathlib import Path
import re
import sys
import tempfile
import threading
from types import SimpleNamespace

REPO = Path('/data1/zhuxinrui/projects/Data-Synthesis')
V18 = REPO / 'trusted_data_synthesis/artifacts/finance_research_20260928/finqa_v6_01/v18_researcher_continuation_01'
V70 = V18 / 'v70_full_closed_loop_01'
V71 = V18 / 'v71_fixed_distribution_control_01/execution_revision_01'
ROOT = V18 / 'v72_low_lr_continuation_01'
V71_IMPLEMENTATION = 'ae5ea266872c9f269ad39c2adeb8f2566fa922adfa0f5f82bb3bd20f47a00244'
FINQA_PROGRAM_TOKENIZER_SOURCE_SHA256 = 'b64686fab3de2053da53c40f01a14fac7783cae101d64af722c1b59d54269df2'
LAYERS = ('reason', 'tool', 'final')
ALLOWED_ACTIONS = ('list_sources', 'read_source', 'run_program', 'submit_program')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
        separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def file_ref(path):
    path = Path(path).resolve()
    return dict(path=str(path), sha256=hashlib.sha256(path.read_bytes()).hexdigest())


def policy():
    return dict(schema='v72_bounded_actual_supervision_gate_policy.v1',
        actual_material='same V71 material binding; all2468 registered original encoded packages',
        expected_tasks=744, expected_packages=2468, expected_effective_rows=4974,
        actual_saved_input_ids_and_target_ids=True, actual_saved_layer_masks=True,
        exact_frozen_tokenizer_and_native_parser=True, CPU_tokenizer_only=True,
        reencode_to_verify_original_token_bytes_not_material_regeneration=True,
        checks=['lossless_prompt_response_token_roundtrip', 'current_assistant_response_only_targets',
                'original_character_interval_to_actual_target_position_match',
                'positive_action_native_envelope_name_argument_contract',
                'positive_submit_is_program_only_not_final_answer',
                'positive_action_open_close_name_arguments_and_EOS_supervised',
                'original_positive_action_EOS_policy', 'no_early_generation_stop_token_in_response'],
        EOS_authority='v14: EOS positive iff whole action positive; old asset mask description is not this consumer',
        negative_original_turns_retained_without_promoting_them_to_positive_actions=True,
        unapproved_action_or_prose_mention_alone_is_not_a_conflict=True,
        semantic_program_correctness_established=False, program_execution=False,
        finite_program_value_checked=False, private_reference_read=False,
        new_token_level_loss_or_gradient=False,
        conflicts_block_dependent_scientific_launch=True,
        all_other_historical_audits_required=False, original_consumer_changed=False)


class Reader:
    """Each needed JSON is opened once, with content-bound references retained."""
    def __init__(self):
        self.sources, self.cache, self.lock = {}, {}, threading.Lock()

    def read(self, path, reference=None, *, keep=True):
        path = Path(path).resolve(); key = str(path)
        with self.lock:
            if key in self.cache:
                value = self.cache[key]
                if reference:
                    require(self.sources[key]['sha256'] == reference['sha256'], 'cached reference changed')
                return value
            require(key not in self.sources, 'unnecessary repeated JSON read: ' + key)
        raw = path.read_bytes(); value = json.loads(raw); sha = hashlib.sha256(raw).hexdigest()
        if reference:
            require(sha == reference['sha256'], 'saved input bytes changed: ' + key)
            if reference.get('id'):
                require(reference['id'] == value.get('id', value.get('encoding_id')),
                        'saved input ID changed: ' + key)
        with self.lock:
            self.sources[key] = dict(path=key, sha256=sha,
                id=value.get('id', value.get('encoding_id')))
            if keep:
                self.cache[key] = value
        return value

    def ref(self, reference, *, keep=True):
        return self.read(reference['path'], reference, keep=keep)

    def refs(self):
        return [self.sources[key] for key in sorted(self.sources)]


def _frozen_api():
    directory = V71 / 'implementation'
    manifest = json.loads((directory / 'record.json').read_bytes())
    require(manifest['id'] == V71_IMPLEMENTATION, 'V71 frozen implementation changed')
    binding_path = directory / 'finqa_v71_binding.py'
    require(file_ref(binding_path)['sha256'] == manifest['sha256'][binding_path.name],
            'frozen V71 binding bytes changed')
    sys.path.insert(0, str(directory))
    binding = importlib.import_module('finqa_v71_binding')
    require(Path(binding.__file__).resolve() == binding_path, 'workspace V71 dependency is forbidden')
    binding.install_scientific_paths()
    names = ('qwen_protocol', 'providers', 'native_metrics', 'metric_vendor.finqa_evaluate')
    modules = [importlib.import_module('trusted_synthesis.finance_research.' + name) for name in names]
    sources = []
    for module in modules:
        ref = file_ref(module.__file__)
        if module is modules[-1]:
            # V71's native scorer pins vendor bytes via PROVENANCE rather than
            # the scientific script map. Bind just its pure program tokenizer;
            # never invoke eval_program, scoring, or unrelated vendor routines.
            expected = Path(manifest['frozen_source_root']) / 'trusted_synthesis/finance_research/metric_vendor/finqa_evaluate.py'
            require(Path(ref['path']) == expected
                    and ref['sha256'] == FINQA_PROGRAM_TOKENIZER_SOURCE_SHA256,
                    'original pure FinQA program-tokenizer source changed')
        else:
            require(manifest['source_bindings'].get(ref['path']) == ref['sha256'],
                    'non-frozen parser/tokenizer dependency: ' + ref['path'])
        sources.append(ref)
    qwen, providers, native, vendor = modules
    # Only this pure tokenizer is exposed; eval_program/equal_program are never called.
    syntax = SimpleNamespace(program_tokenization=vendor.program_tokenization)
    return SimpleNamespace(parse=qwen.parse_qwen_native_response,
        decoder=qwen.strict_json_decoder, tokenizer_binding=providers.tokenizer_binding,
        program_tokens=lambda program: native._program_tokens(program, syntax), sources=sources)


def _load_tokenizer(assets, material, api):
    from transformers import AutoTokenizer
    contract = assets['tokenizer_binding']; directory = Path(contract['directory'])
    require(directory == Path(assets['base_binding']['directory']), 'base/tokenizer source mismatch')
    refs = []
    for member in contract['members']:
        ref = file_ref(directory / member['relative_path'])
        require(ref['sha256'] == member['sha256'], 'frozen tokenizer member changed')
        refs.append(ref)
    tokenizer = AutoTokenizer.from_pretrained(str(directory), local_files_only=True,
        trust_remote_code=False, token=False, use_fast=True)
    require(tokenizer.is_fast and list(api.tokenizer_binding(tokenizer)) == material['tokenizer_binding'],
            'actual tokenizer/template differs from original material')
    require(tokenizer.eos_token_id == contract['eos_token_id'], 'registered EOS changed')
    return tokenizer, refs


def _member_spans(raw, start, decoder):
    """Locations of actual JSON member values, without executing an action."""
    obj, end = decoder.raw_decode(raw, start)
    require(isinstance(obj, dict), 'envelope is not a JSON object')
    spans = {}; cursor = start + 1
    skip = lambda index: index + len(raw[index:]) - len(raw[index:].lstrip(' \t\r\n'))
    while True:
        cursor = skip(cursor)
        if raw[cursor] == '}':
            break
        key, cursor = decoder.raw_decode(raw, cursor)
        cursor = skip(cursor); require(raw[cursor] == ':', 'JSON member separator absent')
        left = skip(cursor + 1); _, right = decoder.raw_decode(raw, left)
        spans[key] = (left, right); cursor = skip(right)
        if raw[cursor] == ',':
            cursor += 1
        else:
            require(raw[cursor] == '}', 'JSON object close absent')
    return obj, end, spans


def check_action_arguments(name, arguments, program_tokens):
    if name == 'list_sources':
        return arguments == {}
    if name == 'read_source':
        return set(arguments) == {'source_id'} and isinstance(arguments['source_id'], str) and bool(arguments['source_id'])
    if name in ('run_program', 'submit_program'):
        return (set(arguments) == {'program'} and isinstance(arguments['program'], str)
                and bool(arguments['program'].strip())
                and program_tokens(arguments['program']) is not None)
    return False


def audit_row(row, *, backend, eos, stop_ids, api):
    """Check actual saved arrays; collect concrete failures, not model hypotheses."""
    conflicts = []
    def check(ok, code, **details):
        if not ok:
            conflicts.append(dict(code=code, **details))
        return ok
    prompt, response = row['rendered_prompt'], row['rendered_response']
    ids, pc = row['input_ids'], row['prompt_token_count']
    positions, target_ids = row['target_positions'], row['target_ids']
    layers = row['layer_target_positions']; text = prompt + response
    encoded = backend.encode(text, add_special_tokens=False)
    actual_ids, offsets = list(encoded.ids), list(encoded.offsets)
    check(ids == actual_ids + [eos], 'actual_input_token_bytes_differ_from_saved_rendering')
    check(backend.decode(ids[:-1], skip_special_tokens=False) == text,
          'actual_saved_token_decode_is_not_lossless')
    check(backend.decode(ids[:pc], skip_special_tokens=False) == prompt,
          'actual_prompt_token_boundary_does_not_match_saved_prompt')
    check(prompt.startswith('<|im_start|>system\n') and prompt.endswith('<|im_start|>assistant\n'),
          'current_response_not_at_expected_assistant_role_boundary')
    check(positions == sorted(set(positions)) and all(pc <= p < len(ids) for p in positions)
          and [ids[p] for p in positions] == target_ids,
          'target_ids_or_causal_response_positions_mismatch')
    check(set(layers) == set(LAYERS) and sorted(p for layer in LAYERS for p in layers[layer]) == positions,
          'layer_targets_do_not_partition_actual_loss_targets')
    expected = {}
    for layer in LAYERS:
        selected = set()
        for left, right in row['response_character_target_intervals'][layer]:
            if not check(0 <= left < right <= len(response), 'positive_character_interval_outside_response', layer=layer):
                continue
            selected.update(i for i, (a, b) in enumerate(offsets)
                if i >= pc and b > a and len(prompt)+left <= a < b <= len(prompt)+right)
        expected[layer] = sorted(selected)
    positive_layers = [layer for layer in ('tool','final')
                       if row['response_character_target_intervals'][layer]]
    check(len(positive_layers) <= 1, 'one_response_has_multiple_positive_action_layers')
    eos_layer = positive_layers[0] if len(positive_layers) == 1 else None
    if eos_layer:
        expected[eos_layer].append(len(ids)-1)
    check(row['student_eos_appended'] is True and row['student_eos_position'] == len(ids)-1
          and ids[-1] == eos, 'actual_EOS_position_or_token_changed')
    check(row['student_eos_supervised'] is (eos_layer is not None)
          and all(layers[layer] == expected[layer] for layer in LAYERS),
          'actual_mask_differs_from_original_span_union_or_EOS_policy')
    early = [i for i in range(pc, len(ids)-1) if ids[i] in stop_ids]
    check(not early, 'early_generation_stop_token_inside_saved_response', positions=early)
    prose, calls = api.parse(response, call_prefix='v72-static')
    action_name = calls[0].name if len(calls) == 1 else None
    critical = {}
    if eos_layer:
        valid = check(len(calls) == 1 and action_name in ALLOWED_ACTIONS,
            'positive_action_is_not_one_valid_native_envelope', observed_calls=len(calls), action=action_name)
        if valid:
            call = calls[0]
            check(check_action_arguments(call.name, call.arguments, api.program_tokens),
                'positive_action_arguments_or_program_shape_conflict', action=call.name,
                arguments=call.arguments)
            check((eos_layer == 'final') is (call.name == 'submit_program'),
                'positive_final_layer_is_not_submit_program', layer=eos_layer, action=call.name)
            opening = response.find('<tool_call>'); start = opening + len('<tool_call>')
            while response[start].isspace(): start += 1
            _, end, spans = _member_spans(response, start, api.decoder())
            closing = response.find('</tool_call>', end)
            envelope_end = closing + len('</tool_call>')
            check(row['response_character_target_intervals'][eos_layer] == [[opening, envelope_end]],
                'approved_action_span_is_not_complete_original_envelope')
            ranges = dict(open_envelope=(opening, opening+len('<tool_call>')),
                close_envelope=(closing,envelope_end), action_name=spans['name'], arguments=spans['arguments'])
            for key,(left,right) in ranges.items():
                located = [i for i,(a,b) in enumerate(offsets)
                           if i >= pc and a < len(prompt)+right and b > len(prompt)+left]
                critical[key] = dict(token_count=len(located), supervised=sum(i in layers[eos_layer] for i in located))
                check(bool(located) and all(i in layers[eos_layer] for i in located),
                    'critical_action_tokens_not_supervised', component=key, positions=located)
            critical['EOS'] = dict(token_count=1, supervised=int(len(ids)-1 in layers[eos_layer]))
    mentions = dict(plain_submit_program_in_prose=bool(re.search(r'\bsubmit_program\s*\(', prose)),
                    final_answer_in_prose='final_answer' in prose,
                    final_answer_as_action=any(call.name == 'final_answer' for call in calls))
    return dict(turn_index=row['turn_index'], row_sha256=row['row_sha256'],
        response_sha256=hashlib.sha256(response.encode()).hexdigest(),
        prompt_tokens=pc, sequence_tokens=len(ids), supervised_tokens=len(positions),
        layer_target_counts={layer:len(layers[layer]) for layer in LAYERS},
        native_call_count=len(calls), native_action=action_name, positive_action_layer=eos_layer,
        actual_EOS_supervised=row['student_eos_supervised'],
        prompt_history_or_role_header_target_count=sum(p < pc for p in positions),
        role_headers=dict(Counter(re.findall(r'<\|im_start\|>([^\n<]+)\n',prompt))),
        critical_token_coverage=critical, prose_mentions=mentions, conflicts=conflicts)


def build_static_audit(*, workers=8):
    reader = Reader(); api = _frozen_api()
    protocol = reader.read(V71/'protocol/record.json')
    point = reader.read(V71/'points/step0894/context/record.json')
    training = reader.read(Path(point['training_root'])/'registration/record.json')
    material = reader.ref(training['material_binding'])
    support = reader.ref(material['support_manifest'])
    assets_protocol = reader.ref(training['assets_protocol'])
    require(material['id'] == point['pool_id'] and len(material['encodings']) == 2468
            and support['N'] == 744 and support['package_count'] == 2468,
            'actual same-parent training material support changed')
    tokenizer, tokenizer_files = _load_tokenizer(assets_protocol['assets'], material, api)
    serial = tokenizer.backend_tokenizer.to_str(); eos = tokenizer.eos_token_id
    generation_eos = assets_protocol['assets']['base_binding']['generation_config']['eos_token_id']
    stop_ids = set(generation_eos if isinstance(generation_eos,list) else [generation_eos])
    stop_ids.add(eos)
    local = threading.local()
    def package(item):
        sid, ref = item
        if not hasattr(local, 'backend'):
            from tokenizers import Tokenizer
            local.backend = Tokenizer.from_str(serial)
        encoding = reader.ref(ref, keep=False)
        require(encoding['slot_id'] == sid and encoding['encoding_admitted'] is True
                and encoding['encoding_policy'] == 'v14_state_independent_original_span_union.v1'
                and [encoding['tokenizer_digest'],encoding['chat_template_digest']] == material['tokenizer_binding'],
                'encoding source/tokenizer policy mismatch')
        rows = [audit_row(row,backend=local.backend,eos=eos,stop_ids=stop_ids,api=api) for row in encoding['rows']]
        failures = [dict(package_id=sid,task_id=encoding['task_id'],turn_index=row['turn_index'],**failure)
                    for row in rows for failure in row['conflicts']]
        if sum(row['supervised_tokens'] for row in rows) != encoding['L_P']:
            failures.append(dict(package_id=sid,task_id=encoding['task_id'],code='whole_package_L_P_mismatch'))
        return dict(package_id=sid,task_id=encoding['task_id'],encoding=ref,
            L_P=encoding['L_P'],rows=rows,conflicts=failures,
            positive_submit_rows=sum(row['positive_action_layer']=='final' for row in rows))
    with ThreadPoolExecutor(max_workers=workers) as executor:
        packages = list(executor.map(package, sorted(material['encodings'].items())))
    rows = [row for package in packages for row in package['rows']]
    conflicts = [failure for package in packages for failure in package['conflicts']]
    effective = sum(row['supervised_tokens'] > 0 for row in rows)
    require(effective == 4974, 'actual effective response-row scope changed')
    critical = {name:dict(tokens=sum(row['critical_token_coverage'].get(name,{}).get('token_count',0) for row in rows),
                         supervised=sum(row['critical_token_coverage'].get(name,{}).get('supervised',0) for row in rows))
                for name in ('open_envelope','close_envelope','action_name','arguments','EOS')}
    counts = dict(rows=len(rows),effective_rows=effective,
        positive_submit_rows=sum(row['positive_action_layer']=='final' for row in rows),
        positive_other_action_rows=sum(row['positive_action_layer']=='tool' for row in rows),
        unsupervised_action_rows=sum(row['positive_action_layer'] is None for row in rows),
        packages_without_positive_submit=sum(package['positive_submit_rows']==0 for package in packages),
        supervised_tokens=sum(row['supervised_tokens'] for row in rows),
        critical_token_coverage=critical,
        layer_counts={layer:sum(row['layer_target_counts'][layer] for row in rows) for layer in LAYERS},
        native_action_counts=dict(Counter(str(row['native_action']) for row in rows)),
        prose_mentions={key:sum(row['prose_mentions'][key] for row in rows)
                        for key in ('plain_submit_program_in_prose','final_answer_in_prose','final_answer_as_action')})
    torch = sys.modules.get('torch')
    cuda = bool(torch is not None and torch.cuda.is_initialized())
    require(not cuda, 'static audit must not initialize CUDA')
    body = dict(schema='v72_actual_encoded_supervision_audit.v1',
        status='PASS' if not conflicts else 'BLOCKED_CONTRACT_CONFLICT', gate_passed=not conflicts,
        policy=policy(), scope=dict(tasks=744,packages=2468,effective_rows=effective,rows=len(rows)),
        parent_V71_protocol_id=protocol['id'], material_binding=training['material_binding'],
        parent_state_digest=point['parent_state_digest'], tokenizer_binding=material['tokenizer_binding'],
        actual_tokenizer_files=tokenizer_files,frozen_parser_sources=api.sources,
        consumer_code_unchanged=True, counts=counts,conflicts=conflicts,packages=packages,
        new_model_calls=0,new_scoring_calls=0,new_program_executions=0,new_material_packages=0,
        CUDA_initialized=False, tokenizer_CPU_only=True, model_weights_loaded=False,
        layerwise_actual_loss_or_gradient_computed=False,
        no_conflict_is_not_proof_of_sufficient_learning_or_semantic_target_quality=True,
        original_artifacts_written=0,analysis_script=file_ref(__file__),sources=reader.refs())
    return dict(body,id=digest(body))


def native_state(row):
    native=row['native']
    if native['status']=='unknown': return 'UNKNOWN'
    if native['status']=='invalid_prediction': return 'I'
    require(native['status']=='scored' and native['program_executable'] is True, 'unknown native status')
    score=native['native']['execution_accuracy']; require(score in (0,1), 'nonbinary saved EA')
    return 'R' if score else 'W'


def join_states(reports, names):
    rows=[reports[name]['results'] for name in names]
    keys=[row['task_key'] for row in rows[0]]
    require(len(keys)==len(set(keys)) and all([row['task_key'] for row in group]==keys for group in rows),
            'joint outcomes require actual identical ordered task rows')
    result=[dict(task_key=key,states={name:native_state(group[i]) for name,group in zip(names,rows,strict=True)})
            for i,key in enumerate(keys)]
    require(all('UNKNOWN' not in row['states'].values() for row in result), 'UNKNOWN forbids complete joint analysis')
    counts=Counter('->'.join(row['states'][name] for name in names) for row in result)
    return dict(denominator=len(keys),condition_order=list(names),joint_counts=dict(sorted(counts.items())),rows=result)


def scalar_stats(values):
    values=[float(x) for x in values];require(values and all(math.isfinite(x) for x in values),'finite nonempty observations required')
    return dict(count=len(values),mean=math.fsum(values)/len(values),minimum=min(values),maximum=max(values),
        negative_count=sum(x<0 for x in values),zero_count=sum(x==0 for x in values),positive_count=sum(x>0 for x in values))


def aligned_package_losses(branch_receipts):
    """Raw saved per-target NLL, aligned by task/package/epoch—not batch means."""
    by_branch={}; metadata={}; schedule_ids=set()
    for branch, receipts in branch_receipts.items():
        packages=defaultdict(dict)
        for row in receipts:
            step=row['step']; epoch=(step-1)//149+1; ev=row['evidence']
            schedule_ids.add(row['schedule_sha256'])
            losses={entry['package_id']:entry for entry in ev['package_losses']}
            require(len(losses)==len(ev['package_losses']), 'duplicate package loss in one batch')
            for entry in ev['packages']:
                sid=entry['package_id']; item=losses[sid]
                meta={key:entry[key] for key in ('package_id','task_id','state_id','whole_package_target_tokens')}
                require(sid not in metadata or metadata[sid]==meta,'same package semantic identity changed')
                metadata[sid]=meta
                require(epoch not in packages[sid] and item['target_tokens']==meta['whole_package_target_tokens'],
                        'package repeated within epoch or target denominator changed')
                packages[sid][epoch]=dict(step=step,target_nll_sum=float(item['target_nll_sum']),
                    target_tokens=item['target_tokens'],mean_target_nll=float(item['target_nll_sum'])/item['target_tokens'],
                    actual_coefficient=float(Fraction(entry['target_token_coefficient'])))
        by_branch[branch]=packages
    require(len(schedule_ids)==1 and len({tuple(sorted(p)) for p in by_branch.values()})==1,
            'branches must share actual schedule and package support')
    epochs=sorted(next(iter(next(iter(by_branch.values())).values())))
    require(all(sorted(values)==epochs for packages in by_branch.values() for values in packages.values()),
            'incomplete aligned package epoch observations')
    names=list(by_branch)
    output=[]
    for sid in sorted(metadata):
        observed={name:{str(epoch):by_branch[name][sid][epoch] for epoch in epochs} for name in names}
        for epoch in epochs:
            require(len({by_branch[name][sid][epoch]['step'] for name in names})==1,
                    'same task/package is not at the same registered step')
        output.append(dict(**metadata[sid],observations=observed))
    within={}
    for name in names:
        within[name]={}
        for left,right in zip(epochs,epochs[1:]):
            deltas=[by_branch[name][sid][right]['mean_target_nll']-by_branch[name][sid][left]['mean_target_nll'] for sid in metadata]
            within[name][f'{left}->{right}']=scalar_stats(deltas)
    between={str(epoch):scalar_stats(by_branch[names[0]][sid][epoch]['mean_target_nll']-
                                     by_branch[names[1]][sid][epoch]['mean_target_nll'] for sid in metadata) for epoch in epochs}
    return dict(package_count=len(metadata),task_count=len({m['task_id'] for m in metadata.values()}),
        epochs=epochs,condition_order=names,packages=output,
        within_branch_next_epoch_same_package_delta=within,
        between_branch_same_epoch_same_step_mean_target_nll_delta=between,
        between_branch_orientation=names[0]+' minus '+names[1],
        raw_package_NLL_not_probability_weighted_training_objective=True,
        same_package_same_tokens_different_online_model_states=True,
        off_policy_fixed_model_loss=False,tokenwise_or_layerwise_loss_available=False)


def build_existing_analysis():
    reader=Reader(); p71=reader.read(V71/'protocol/record.json')
    summary=reader.read(V71/'evaluations/final_summary/record.json')
    require(summary['status']=='COMPLETE','V71 must already be complete')
    baseline=reader.ref(p71['baseline_evaluation']['model_reports']['development'])
    fixed=reader.ref(summary['model_reports']['step1490.dev_greedy'])
    full=reader.ref(p71['full_evaluation']['model_reports']['step1490.dev_greedy'])
    triple=join_states(dict(baseline894=baseline,Fixed1490=fixed,Full1490=full),('baseline894','Fixed1490','Full1490'))
    source_R=[row for row in triple['rows'] if row['states']['baseline894']=='R']
    triple['original_correct_loss_sets']=dict(original_correct=len(source_R),
        both_lost_correct=sum(row['states']['Fixed1490']!='R' and row['states']['Full1490']!='R' for row in source_R),
        only_Fixed_lost=sum(row['states']['Fixed1490']!='R' and row['states']['Full1490']=='R' for row in source_R),
        only_Full_lost=sum(row['states']['Fixed1490']=='R' and row['states']['Full1490']!='R' for row in source_R),
        both_retained_correct=sum(row['states']['Fixed1490']==row['states']['Full1490']=='R' for row in source_R),
        both_became_invalid=sum(row['states']['Fixed1490']==row['states']['Full1490']=='I' for row in source_R))
    calibration={}
    for condition,refs in [('Fixed894',summary['model_reports']),('Full',p71['full_evaluation']['model_reports'])]:
        first=reader.ref(refs['step1192.cal_greedy']);last=reader.ref(refs['step1490.cal_greedy'])
        joined=join_states(dict(step1192=first,step1490=last),('step1192','step1490'))
        c=joined['joint_counts'];new=sum(v for k,v in c.items() if k.split('->')[0]!='R' and k.split('->')[1]=='R')
        lost=sum(v for k,v in c.items() if k.split('->')[0]=='R' and k.split('->')[1]!='R')
        joined.update(new_correct=new,lost_correct=lost,net_correct=new-lost,
            difference_pp=100*(new-lost)/joined['denominator'])
        calibration[condition]=joined
    # Actual existing per-step receipts only; no checkpoints/Tensors are opened.
    receipts={name:[reader.read(root/f'training/step{step:04d}_step/record.json',keep=False)
                    for step in range(895,1491)] for name,root in [('Full',V70),('Fixed894',V71)]}
    aligned=aligned_package_losses(receipts)
    require(aligned['epochs']==[7,8,9,10] and aligned['package_count']==2468
            and aligned['task_count']==744,'bounded original four-epoch support changed')
    body=dict(schema='v72_existing_same_package_and_joint_outcomes.v1',status='COMPLETE',
        parent_V71_protocol_id=p71['id'],triple_development=triple,
        actual_second_window_calibration_transitions=calibration,aligned_online_package_NLL=aligned,
        original_scientific_records_written=0,new_model_calls=0,new_scoring_calls=0,CUDA_initialized=False,
        new_tokenwise_or_layerwise_loss=False,new_gradient_calls=0,new_program_executions=0,
        new_scientific_material=False,analysis_script=file_ref(__file__),sources=reader.refs())
    return dict(body,id=digest(body))


def publish(value, output):
    output=Path(output).resolve()
    require(output.is_relative_to(Path('/tmp')) or output.is_relative_to(ROOT),
            'audit writes only scratch or independent V72 derived outputs')
    if output.is_relative_to(ROOT):
        require((ROOT/'protocol/record.json').exists(),'prepare V72 before publication')
    raw=(json.dumps(value,ensure_ascii=False,sort_keys=True,indent=2,allow_nan=False)+'\n').encode()
    if output.exists():
        require(output.read_bytes()==raw,'immutable audit output differs')
        return
    output.parent.mkdir(parents=True,exist_ok=True)
    fd,temporary=tempfile.mkstemp(prefix='.v72-audit-',dir=output.parent)
    try:
        with os.fdopen(fd,'wb') as stream:
            stream.write(raw);stream.flush();os.fsync(stream.fileno())
        os.link(temporary,output)
    finally:
        Path(temporary).unlink(missing_ok=True)


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode',choices=('static','existing'),required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--workers',type=int,default=8)
    args=parser.parse_args(argv)
    require(1<=args.workers<=8,'bounded CPU parallelism required')
    result=build_static_audit(workers=args.workers) if args.mode=='static' else build_existing_analysis()
    publish(result,args.output)
    print(json.dumps({key:result[key] for key in ('schema','status','id')},ensure_ascii=False))
    return 0 if result['status'] in ('PASS','COMPLETE') else 2


if __name__=='__main__':
    raise SystemExit(main())
