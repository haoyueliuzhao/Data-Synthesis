"""Accept and encode two fixed teacher slots on the selected training tasks.

Only new teacher assistant tokens are targets. Student prefixes, user messages
and tool observations remain causal inputs. This module does not modify the old
material pool or repeat its V72 static supervision audit.
"""
from __future__ import annotations
from collections import Counter
import copy
from fractions import Fraction
import hashlib
import importlib
from pathlib import Path

import finqa_v75_binding as b

SLOTS = ("initial", "post")
PHASES = ("L.initial", "P.initial", "P.post")
COLLECTION_JOBS = {f"{phase}.shard{shard}" for phase in PHASES for shard in range(2)}


def slot_weights(initial, post):
    """Absent slot mass returns to the old loss, never to the other teacher."""
    b.require(type(initial) is bool and type(post) is bool, "slot availability must be explicit")
    return dict(old=Fraction(1)-Fraction(1,4)*int(initial)-Fraction(1,4)*int(post),
                initial=Fraction(1,4)*int(initial), post=Fraction(1,4)*int(post))


def material_policy():
    return dict(schema="v75_two_fixed_demonstration_slots.v1", slots=list(SLOTS),
        weight_per_available_slot="1/4", old_weight="1-1/4*I_initial-1/4*I_post",
        missing_slot_mass_returns_to_old=True, other_teacher_slot_not_renormalized=True,
        teacher_loss="sum of CE on every actual newly generated teacher response token / full teacher-suffix target token count",
        teacher_responses_unfused=True, student_prefix_user_and_tools_target_weight=0,
        exact_actual_response_tokens=True, actual_EOS_targeted_if_present=True, invented_EOS=0,
        old_package_masks_and_denominators_unchanged=True, original_task_schedule_unchanged=True,
        no_full_old_supervision_reaudit=True, no_teacher_search_or_failure_resampling=True,
        native_EA_is_not_public_reasoning_or_semantic_trace_certification=True,
        acceptance="complete native EA=1, original public/source contract, lossless new-assistant token mapping",
        native_PA_separately_reported=True, semantic_reasoning_evidence_status="NOT_INDEPENDENTLY_CERTIFIED",
        no_new_outer_Contribution_VJP=True)


def _modules():
    b.install_scientific_paths(); b.install_registered_auxiliary()
    original=b.source_module("finqa_v63_evaluation")
    final=original._runtime()
    base="trusted_synthesis.finance_research."
    return original, final, importlib.import_module(base+"contracts"), importlib.import_module(base+"v6_task")


def _guard(guard,label):
    if guard is not None:
        if callable(guard): guard()
        else: guard.check(label,boundary=True)
    b.require(not (b.ROOT/"STOP").exists() and not (b.ROOT/"control/stop_requested/record.json").exists(),
              "explicit stop forbids material preparation")


def encode_teacher_suffix(episode, *, teacher_start, teacher_identity, tokenizer):
    """Receipt-bound target selection: every teacher token once, no prefix target."""
    b.require(type(teacher_start) is int and 0 <= teacher_start < len(episode["turns"]),
              "teacher suffix must contain at least one actual response")
    rows=[]
    for index,turn in enumerate(episode["turns"][teacher_start:],teacher_start):
        receipt=turn["receipt"]; request=turn["provider_metadata"]["request"]
        b.require(receipt["identity"] == teacher_identity and receipt["request_sha256"] == b.digest(request),
                  "teacher token receipt/request/checkpoint changed")
        prompt=list(receipt["prompt_input_ids"]); target=list(receipt["raw_generated_token_ids"])
        b.require(prompt and target and len(target)<=2048 and len(prompt)+len(target)<=24576,
                  "new material cannot truncate the full teacher input or response")
        b.require(all(type(x) is int and x>=0 for x in prompt+target), "nonintegral or negative source token")
        eos_ids=receipt["sampling"]["eos_token_ids"]
        actual_eos=target[-1] in eos_ids
        b.require(receipt["actual_eos"] == actual_eos
            and receipt["sampling"]["context_truncated"] is False,
            "actual EOS or untruncated source receipt changed")
        decoded=tokenizer.decode(target[:-1] if actual_eos else target,
            skip_special_tokens=False,clean_up_tokenization_spaces=False)
        b.require(decoded==turn["raw_text"] and hashlib.sha256(decoded.encode()).hexdigest()==receipt["raw_response_sha256"],
                  "actual teacher tokens do not decode to the original response")
        # Restore only canonical original tool dictionary insertion order before
        # exact rendering; source values and saved request hashes stay unchanged.
        old_inputs=b.source_v73("inputs")
        restored=old_inputs.restore_request_tool_order(request)
        rendered=tokenizer.apply_chat_template(copy.deepcopy(restored["messages"]),tools=copy.deepcopy(restored["tools"]),
            tokenize=False,add_generation_prompt=True)
        encoded=list(tokenizer(rendered,add_special_tokens=False,truncation=False,padding=False)["input_ids"])
        b.require(encoded==prompt and hashlib.sha256(rendered.encode()).hexdigest()==request["rendered_prompt_sha256"],
                  "new teacher training prompt differs from its exact actual request tokens")
        positions=list(range(len(prompt),len(prompt)+len(target)))
        row=dict(input_ids=prompt+target,target_ids=target,target_positions=positions,
            original_turn_index=index,prompt_tokens=len(prompt),target_tokens=len(target),
            sequence_tokens=len(prompt)+len(target),actual_EOS_target_count=int(actual_eos),
            source_receipt_sha256=b.digest(receipt),source_turn_sha256=b.digest(turn),
            request_sha256=receipt["request_sha256"],target_domain="new_teacher_assistant_only",
            prefix_target_count=0,context_truncated=False)
        b.require(all(row["input_ids"][i]==t for i,t in zip(positions,target,strict=True)),
                  "new target positions do not identify exactly the teacher response")
        rows.append(row)
    return dict(rows=rows,teacher_turn_start=teacher_start,teacher_turns=len(rows),
        target_tokens=sum(r["target_tokens"] for r in rows),
        input_positions=sum(r["sequence_tokens"] for r in rows),
        prompt_tokens=sum(r["prompt_tokens"] for r in rows),
        actual_EOS_target_count=sum(r["actual_EOS_target_count"] for r in rows),
        max_sequence_tokens=max(r["sequence_tokens"] for r in rows),
        target_mask_check="PASS_EXACT_NEW_TEACHER_RESPONSES_ONLY",student_prefix_target_count=0,
        denominator="all actual new teacher response tokens, summed across the complete teacher suffix")


def l_stratum(episode,native):
    if native["status"]=="scored" and native["native"]["execution_accuracy"]==1:
        return "L_original_success"
    if episode["stop_reason"]=="no_tool_call":
        return "L_original_no_call"
    return "L_original_other_failure"


def planned_dose(tasks, batches, *, old_receipts=None, fixed_pi=None):
    """Exact realized batch masses; four-task tails use their actual divisor."""
    b.require(len(batches)==298 and sum(len(x["task_ids"]) for x in batches)==1488,
              "the original298/1488 window changed")
    actual_masses=[]
    if old_receipts is not None:
        b.require(len(old_receipts)==298 and fixed_pi is not None,"existing baseline window dose receipts and fixed pi required")
        for batch,receipt in zip(batches,old_receipts,strict=True):
            evidence=receipt["evidence"]
            b.require(evidence["task_batch"]["task_ids"]==batch["task_ids"],"old baseline actual task schedule differs")
            weights={}
            for package in evidence["packages"]:
                task=package["task_id"]
                b.require(task in batch["task_ids"],"old receipt has a foreign task")
                probability=Fraction(str(fixed_pi[task][package["state_id"]]))
                # Recover mu/(B*p_s) before state weighting. Fixed float pi can
                # sum to 1 +/- roundoff; do not silently renormalize that old loss.
                unit=Fraction(package["target_token_coefficient"])*package["n_state"]*package["whole_package_target_tokens"]/probability
                b.require(task not in weights or weights[task]==unit,"old packages disagree on realized task mass")
                weights[task]=unit
            b.require(set(weights)==set(batch["task_ids"]) and all(value>0 for value in weights.values()) and sum(weights.values())==1,
                "actual baseline task sampling masses are not complete and normalized")
            actual_masses.append(weights)
    exposures=Counter();mass=Counter();per_step=[]
    tokens=Counter();inputs=Counter();micro=Counter()
    for offset,batch in enumerate(batches,1193):
        ids=batch["task_ids"];stepslots=[]
        for task in ids:
            unit=actual_masses[offset-1193][task] if actual_masses else Fraction(1,len(ids))
            exposures[task]+=1
            slots=tasks.get(task,{}).get("slots",{})
            available={name:slots.get(name) is not None for name in SLOTS}
            weights=slot_weights(available["initial"],available["post"])
            for name,weight in weights.items():mass[name]+=unit*weight
            for name in SLOTS:
                if not available[name]:continue
                m=slots[name]["encoding_summary"]
                tokens[name]+=m["target_tokens"];inputs[name]+=m["input_positions"];micro[name]+=m["teacher_turns"]
                stepslots.append(dict(task_id=task,slot=name,package_id=slots[name]["package_id"],
                    task_coefficient=str(unit*weights[name]),target_tokens=m["target_tokens"],
                    input_positions=m["input_positions"],teacher_turns=m["teacher_turns"]))
        per_step.append(dict(step=offset,batch_size=len(ids),task_ids=ids,demonstrations=stepslots))
    counts={name:sum(row["slots"].get(name) is not None for row in tasks.values()) for name in SLOTS}
    value=dict(schema="v75_planned_exact_demonstration_dose.v1",updates=298,task_exposures=1488,
        four_task_tail_batches=sum(len(x["task_ids"])==4 for x in batches),
        selected_task_exposures={k:exposures[k] for k in tasks},available_tasks=counts,
        equal_744_task_mass={name:str(Fraction(counts[name],4*744)) for name in SLOTS},
        realized_average_update_mass={name:str(mass[name]/298) for name in ("old",*SLOTS)},
        realized_window_mass_sum={name:str(mass[name]) for name in ("old",*SLOTS)},
        planned_teacher_target_tokens=dict(tokens),planned_teacher_input_positions=dict(inputs),
        planned_teacher_microbatches=dict(micro),per_step=per_step,
        task_mass_source="actual V72 coefficient*n_state*L/fixed_pi, mu/(B*p_s); old pi roundoff not renormalized" if old_receipts is not None else "explicit uniform CPU fixture",
        weights_are_not_gradient_or_loss_measurements=True,additional_forward_RNG_consumption_not_paired=True)
    b.require(sum(mass.values())==298,"each actual batch must retain unit total task mass")
    if old_receipts is not None:
        b.require(len(old_receipts)==298,"existing baseline window dose receipt count changed")
        totals=Counter()
        for index,r in enumerate(old_receipts):
            evidence=r["evidence"]
            b.require(evidence["task_batch"]["task_ids"]==batches[index]["task_ids"],"old baseline actual task schedule differs")
            for field in ("target_tokens","sequence_tokens","rows_completed","physical_package_count"):
                totals[field]+=evidence[field]
        value["old_baseline_actual_consumption"]=dict(totals)
        value["planned_candidate_total_target_tokens"]=totals["target_tokens"]+sum(tokens.values())
        value["planned_candidate_total_input_positions"]=totals["sequence_tokens"]+sum(inputs.values())
        value["planned_candidate_total_microbatches"]=totals["rows_completed"]+sum(micro.values())
        value["old_tokens_still_consumed_but_weight_diluted"]=True
    return value


def _barrier(root,reference,protocol_id):
    b.require(reference is not None,"material preparation requires actual collection exit barrier")
    value=b.read_ref(reference)
    b.require(value["protocol_id"]==protocol_id and value["active_workers"]==[]
        and set(value["accepted_jobs"])==COLLECTION_JOBS,
        "all six accepted actual collection exits must precede teacher scoring")
    for job in COLLECTION_JOBS:
        accepted=b.read_ref(value["accepted_jobs"][job]);actual=b.read_ref(accepted["actual_exit"])
        b.require(accepted["actual_exit_zero"] is True and accepted["resources_passed"] is True
            and actual["actual_waitpid_observed"] is True and actual["returncode"]==0
            and actual["job_id"]==accepted["job_id"]==job and actual["protocol_id"]==protocol_id,
            "collection result is not accepted after its actual exit")
    return value


def prepare_materials(root,bundle,phase_outcomes,protocol_id,guard=None,barrier_ref=None):
    """One bounded native score/encoding phase; never loads language-model weights."""
    root=Path(root).resolve();b.require(root==b.ROOT.resolve(),"foreign material root")
    _barrier(root,barrier_ref,protocol_id)
    roster={r["task_id"]:r for r in bundle["tasks"]}
    b.require(len(roster)==128 and set(phase_outcomes)==set(PHASES),"fixed128 collection denominator changed")
    outcomes={};refs={}
    for phase in PHASES:
        b.require(set(phase_outcomes[phase])==set(roster),"collection phase cannot drop missing teacher conditions")
        outcomes[phase]={};refs[phase]={}
        for task,ref in phase_outcomes[phase].items():
            value=b.read_ref(ref);b.require(value["protocol_id"]==protocol_id and value["task_id"]==task,
                "collected condition source changed")
            b.require(value["status"]=="COMPLETE" or (phase=="P.post" and value["status"]=="NOT_APPLICABLE"),
                "incomplete collection must not become absent teacher mass")
            outcomes[phase][task]=value;refs[phase][task]=ref
    original,final,contracts,taskmod=_modules()
    plan=bundle["generation_registrations"]["P"]
    manifest,public,lineages=final.load_public_snapshot(plan["snapshot"])
    b.require(manifest["id"]==plan["snapshot_id"],"original training public snapshot changed")
    wanted={r["original_task_key"] for r in roster.values()}
    private=original._panel_private_bundles(final,plan,manifest,public,lineages,wanted)
    tokenizer=final.base.load_tokenizer(plan["assets"])
    scores={};packages={};tasks={};coverage=Counter();source_clusters={name:set() for name in SLOTS}
    for task,selected in roster.items():
        task_scores={}
        for phase in PHASES:
            outcome=outcomes[phase][task]
            if outcome["status"]=="NOT_APPLICABLE":
                task_scores[phase]=dict(status="NOT_APPLICABLE",reason="L_last_call_was_initial",native=None)
                continue
            _guard(guard,"before_teacher_native_score")
            episode=contracts.Episode.model_validate(outcome["episode"])
            score_path=root/"materials/scores"/phase/b.digest(task)/"record.json"
            if score_path.exists():
                stored=b.checked(score_path)
                b.require(stored["outcome"]==refs[phase][task] and stored["protocol_id"]==protocol_id,
                    "saved native score belongs to another collected trajectory")
                native=stored["native"]
            else:
                native=final.score_public_reasoning_program(private[selected["original_task_key"]],episode)
                b.publish(score_path,dict(schema="v75_training_collection_native_score.v1",protocol_id=protocol_id,
                    task_id=task,phase=phase,outcome=refs[phase][task],native=native))
            b.require(native["status"]!="unknown","native training collection score UNKNOWN blocks material preparation")
            task_scores[phase]=dict(status="SCORED",native=native,score=b.entry(score_path))
        student=outcomes["L.initial"][task]["episode"]
        stratum=l_stratum(student,task_scores["L.initial"]["native"])
        slotmap={};slotstatus={}
        for slot,phase in (("initial","P.initial"),("post","P.post")):
            outcome=outcomes[phase][task];score=task_scores[phase]
            key=slot+":"+stratum
            coverage[key+":selected"]+=1
            if outcome["status"]=="NOT_APPLICABLE":
                slotmap[slot]=None;slotstatus[slot]=dict(status="NO_TOOL_AFTER_STATE",reason=score["reason"])
                coverage[key+":no_state"]+=1;continue
            coverage[key+":state_exists"]+=1
            native=score["native"]
            if native["status"]!="scored" or native["native"]["execution_accuracy"]!=1:
                slotmap[slot]=None;slotstatus[slot]=dict(status="TEACHER_NOT_EA_CORRECT",native=native)
                coverage[key+":teacher_not_correct"]+=1;continue
            _guard(guard,"before_new_teacher_mapping")
            episode=contracts.Episode.model_validate(outcome["episode"])
            # This original public projection authenticates strings/source/action
            # structure. It is not a new semantic reasoning-quality certification.
            view=taskmod.public_trajectory_view(episode)
            b.require(episode.config.role=="sft","development trajectory cannot enter new training material")
            start=outcome.get("teacher_turn_start",outcome["source_turn_index"])
            b.require(start==outcome["source_turn_index"] and ((slot=="initial" and start==0) or(slot=="post" and start>=1)),
                "post slot must target the actual terminal boundary, not a relabelled initial request")
            encoded=encode_teacher_suffix(outcome["episode"],teacher_start=start,
                teacher_identity=bundle["model_bindings"]["P"]["model_identity"],tokenizer=tokenizer)
            package_id="v75_demo:"+b.digest(dict(task_id=task,slot=slot,outcome=refs[phase][task],encoding=encoded))
            package_path=root/"materials/packages"/b.digest(package_id)/"record.json"
            package=b.publish(package_path,dict(schema="v75_teacher_suffix_package.v1",protocol_id=protocol_id,
                package_id=package_id,task_id=task,slot=slot,outcome=refs[phase][task],native_score=score["score"],
                native_EA=1,native_PA=native["native"]["program_accuracy"],public_view_id=view["view_id"],
                public_source_structure_check="PASS",public_semantic_reasoning_check="NOT_INDEPENDENTLY_CERTIFIED",
                student_original_stratum=stratum,**encoded))
            summary={k:v for k,v in encoded.items() if k!="rows"}
            slotmap[slot]=dict(package_id=package_id,package=b.entry(package_path),encoding_summary=summary)
            slotstatus[slot]=dict(status="ADMITTED",EA=1,PA=native["native"]["program_accuracy"],
                public_source_structure_check="PASS",public_semantic_reasoning_check="NOT_INDEPENDENTLY_CERTIFIED")
            packages[package_id]=b.entry(package_path);coverage[key+":admitted"]+=1
            source_clusters[slot].add(selected["source_group"]["group"])
        tasks[task]=dict(task_id=task,original_task_key=selected["original_task_key"],source_group=selected["source_group"],
            student_original_stratum=stratum,student_native=task_scores["L.initial"]["native"],
            slots=slotmap,slot_status=slotstatus,weights={k:str(v) for k,v in slot_weights(slotmap["initial"] is not None,slotmap["post"] is not None).items()})
        scores[task]=task_scores
    # Reuse the old successful window receipts for original input/target counts;
    # no old row encoding or target-mask audit is repeated.
    old_context=b.checked(b.V72_ROOT/"points/step1192/context/record.json")
    old_completed=b.checked(b.V72_ROOT/"points/step1192/train/completed/record.json")
    import json
    old_receipts=[]
    for row in old_completed["update_receipts"]:
        ref=row["record"];raw=Path(ref["path"]).read_bytes()
        b.require(hashlib.sha256(raw).hexdigest()==ref["sha256"],"V72 actual old-consumer receipt bytes changed")
        old_receipts.append(json.loads(raw))
    dose=planned_dose(tasks,old_context["window_task_batches"],old_receipts=old_receipts,fixed_pi=old_context["fixed_pi"])
    status="COMPLETE" if packages else "STOPPED_NO_USABLE_DEMONSTRATIONS"
    result=b.publish(root/"materials/record.json",dict(schema="v75_training_demonstration_materials.v1",status=status,
        protocol_id=protocol_id,input_id=bundle["id"],policy=material_policy(),collection_exit_barrier=barrier_ref,
        selected_tasks=128,tasks=tasks,packages=packages,scores=scores,coverage=dict(sorted(coverage.items())),
        available_source_clusters={k:len(v) for k,v in source_clusters.items()},dose=dose,
        source_outcomes=refs,old_consumer_reference=b.entry(b.V72_ROOT/"points/step1192/train/completed/record.json"),
        new_model_calls=0,new_teacher_search=0,private_references_never_model_inputs=True,
        old_material_static_reaudit=False,new_training_performed=False))
    if status=="COMPLETE":
        importlib.import_module("finqa_v75_training").prepare_initial(root,protocol_id)
    return result
