"""Read-only fixed training-side V75 selection and exact collection inputs.

The predeclared roster is chosen from the unchanged 744-task SFT support before
any new inference. No teacher success, development answer or existing score
influences the selection. Import and preparation never execute tools or models.
"""
from __future__ import annotations
from collections import Counter, defaultdict
import copy
import hashlib
import importlib
import json
from pathlib import Path

SELECTION_SALT = "finqa-v75-training-state-demonstration-20261027-v1"
COUNT = 128
PHASES = ("L.initial", "P.initial", "P.post")


def binding():
    return importlib.import_module("finqa_v75_binding")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
        separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def bound(body):
    body = {k:v for k,v in body.items() if k != "id"}
    return dict(body, id=digest(body))


class Reader:
    def __init__(self):
        self.values, self.sources = {}, {}

    def bytes(self, path, *, expected=None):
        path = str(Path(path).resolve())
        if path not in self.values:
            value = Path(path).read_bytes()
            self.values[path] = value
            self.sources[path] = dict(path=path, sha256=hashlib.sha256(value).hexdigest(), bytes=len(value))
        value = self.values[path]
        require(expected is None or self.sources[path]["sha256"] == expected, "source byte binding changed: " + path)
        return value

    def read(self, path, *, ref=None, record=True):
        raw = self.bytes(path, expected=ref.get("sha256") if ref else None)
        value = json.loads(raw)
        if record:
            require(value.get("id") == digest({k:v for k,v in value.items() if k != "id"}), "source record identity changed")
            self.sources[str(Path(path).resolve())]["id"] = value["id"]
        if ref and "id" in ref:
            require(value["id"] == ref["id"], "source record differs from reference")
        return value

    def ref(self, path):
        return copy.deepcopy(self.sources[str(Path(path).resolve())])


def config():
    return dict(harness_id="bigfinance-derived-vtdo-v7", submission_profile="finqa-public-reasoning-v2",
        local_tool_protocol="qwen2.5-native-tool-call-v1", max_steps=32, max_new_tokens=2048,
        context_limit=24576, temperature=0.0, top_p=1.0, top_k=0, seed=20260928,
        tier="EVAL_NATIVE", role="sft", api_model="deepseek-flash")


def select(candidates, count=COUNT, *, salt=SELECTION_SALT):
    """Hash source clusters and tasks, then round robin without outcome access."""
    require(count == COUNT and len(candidates) >= count, "fixed128 support cannot be changed")
    require(len({r["task_id"] for r in candidates}) == len(candidates), "duplicate candidate task")
    clusters = defaultdict(list)
    for row in candidates:
        clusters[row["source_group"]["group"]].append(row)
    for group, rows in clusters.items():
        rows.sort(key=lambda r:(digest([salt,"task",r["original_task_key"]]),r["original_task_key"]))
    order = sorted(clusters,key=lambda group:(digest([salt,"cluster",group]),group))
    selected, depth = [], 0
    while len(selected) < count:
        for group in order:
            if depth < len(clusters[group]):
                selected.append(copy.deepcopy(clusters[group][depth]))
                if len(selected) == count:
                    break
        depth += 1
    return selected


def overlap(selected, all_training, development, mechanism):
    def values(rows, key):
        return {row[key] for row in rows if row.get(key) is not None}
    def groups(rows):
        return {row["source_group"]["group"] for row in rows}
    def pair(left, right):
        common_ids = values(left,"original_task_key") & values(right,"original_task_key")
        common_clusters = groups(left) & groups(right)
        common_companies = values(left,"company") & values(right,"company")
        common_reports = values(left,"report") & values(right,"report")
        return dict(task_id_overlap=sorted(common_ids), source_cluster_overlap=sorted(common_clusters),
            company_overlap=sorted(common_companies), report_overlap=sorted(common_reports),
            left_tasks=len(left), right_tasks=len(right),
            left_tasks_in_shared_source_clusters=sum(r["source_group"]["group"] in common_clusters for r in left),
            source_cluster_count=len(common_clusters), company_count=len(common_companies),report_count=len(common_reports))
    return dict(schema="v75_existing_split_source_overlap.v1",
        selected128_vs_development883=pair(selected,development),
        original744_vs_development883=pair(all_training,development),
        selected128_vs_V73_V74_fixed96=pair(selected,mechanism),
        task_disjointness_not_report_or_company_independence=True,
        overlaps_registered_not_used_to_reselect=True, development_answers_accessed=False)


def jobs(bundle):
    require(len(bundle["tasks"]) == COUNT, "collection roster must be128")
    result = {}
    for phase in PHASES:
        for shard in range(2):
            rows = [r for r in bundle["tasks"] if int(digest(r["original_task_key"]),16)%2 == shard]
            key = f"{phase}.shard{shard}"
            result[key] = dict(job_id=key,id=key,phase=phase,model=phase[0],shard=shard,
                stage="collect",kind="generate",memory_phase="generate",seed=137,
                task_ids=[r["task_id"] for r in rows],task_keys=[r["original_task_key"] for r in rows],
                maximum_model_calls=len(rows)*(31 if phase=="P.post" else 32),
                source_L_actual_exit_required=phase=="P.post")
    require(sum(j["maximum_model_calls"] for j in result.values()) == 12160, "collection cap changed")
    return result


def prepare_inputs():
    b, reader = binding(), Reader()
    v74 = getattr(b,"V74_ROOT",b.V18 / "v74_cross_history_continuation_01")
    prior_protocol = reader.read(v74 / "protocol/record.json")
    prior_closeout = reader.read(v74 / "closeout/record.json")
    require(prior_closeout["status"] == "COMPLETE" and prior_closeout["protocol_id"] == prior_protocol["id"], "V74 must be complete")
    registrations = {model:reader.read(b.V72_ROOT / "evaluations/jobs" / name / "registration/record.json")
        for model,name in (("P","step1192.dev_greedy"),("L","step1490.dev_greedy"))}
    require(all(registrations[m]["model_identity"] == prior_protocol["model_bindings"][m]["model_identity"]
        and registrations[m]["checkpoint"] == prior_protocol["model_bindings"][m]["checkpoint"] for m in ("P","L")), "P/L original checkpoint identity changed")
    base = registrations["P"]
    require(registrations["L"]["snapshot"] == base["snapshot"] and registrations["L"]["snapshot_id"] == base["snapshot_id"]
        and registrations["L"]["role_plan"] == base["role_plan"], "P/L source split differs")
    point_path = b.V71_ROOT / "points/step0894/context/record.json"
    point = reader.read(point_path)
    training_path = Path(point["training_root"]) / "registration/record.json"
    training = reader.read(training_path)
    material = reader.read(training["material_binding"]["path"],ref=training["material_binding"])
    support = reader.read(material["support_manifest"]["path"],ref=material["support_manifest"])
    ids = support["training_task_ids"]
    require(len(ids)==len(set(ids))==744 and set(ids)==set(training["training_task_ids"])
        and material["id"]==point["pool_id"], "original744 task support changed")
    snapshot = Path(base["snapshot"])
    manifest = reader.read(snapshot / "manifest.json")
    require(manifest["id"]==base["snapshot_id"], "public snapshot identity changed")
    publics, lineages = {}, {}
    for filename, target in (("public.jsonl",publics),("lineage.jsonl",lineages)):
        raw = reader.bytes(snapshot / filename,expected=manifest["files"][filename]["sha256"])
        require(len(raw)==manifest["files"][filename]["bytes"], "public snapshot size changed")
        for line in raw.splitlines():
            if not line.strip():
                continue
            row=json.loads(line); key=f"{row['dataset']}/{row.get('task_id',row.get('original_id'))}"
            require(key not in target,"duplicate public snapshot key")
            target[key]=row
    selection_path = b.V73_ROOT.parent / "selection/record.json"
    mechanism = reader.read(selection_path)
    require(len(mechanism["selected"])==96, "fixed V73 mechanism roster changed")
    dev_keys = [k for k,role in base["role_plan"]["assignments"].items() if role=="development"]
    mechanism_keys = [r["original_task_key"] for r in mechanism["selected"]]
    require(len(dev_keys)==883 and set(mechanism_keys)<=set(dev_keys), "original development role binding changed")
    def row(key):
        require(key in publics and key in lineages,"missing original public task or lineage")
        lineage=lineages[key]
        return dict(task_id=publics[key]["task_id"],task_key=key,original_task_key=key,
            source_group=dict(group=lineage["source_group"],level=lineage["source_group_level"]),
            company=lineage["company"],report=lineage["report"],year=lineage["year"],
            public_task_sha256=digest(publics[key]),lineage_sha256=digest(lineage))
    candidates=[row("finqa/"+task_id) for task_id in ids]
    require(all(base["role_plan"]["assignments"].get(r["original_task_key"])=="sft" for r in candidates), "training material contains a non-SFT role")
    require(not set(r["original_task_key"] for r in candidates)&set(dev_keys), "training tasks overlap heldout task IDs")
    selected=select(candidates)
    return bound(dict(schema="v75_fixed_training_collection_inputs.v1",selection_salt=SELECTION_SALT,
        selection_rule="hash fixed salt/source cluster order; hash original task key within each cluster; round robin; no result access",
        source_support_count=744,selected_task_count=128,tasks=selected,
        public_tasks={r["original_task_key"]:publics[r["original_task_key"]] for r in selected},
        lineages={r["original_task_key"]:lineages[r["original_task_key"]] for r in selected},
        source_cluster_count=len({r["source_group"]["group"] for r in selected}),
        selected_per_cluster=dict(Counter(r["source_group"]["group"] for r in selected)),
        overlap=overlap(selected,candidates,[row(k) for k in dev_keys],[row(k) for k in mechanism_keys]),
        config=config(),generation_registrations=registrations,
        model_bindings={m:prior_protocol["model_bindings"][m] for m in ("P","L")},
        training_registration=reader.ref(training_path),material_binding=training["material_binding"],
        support_manifest=material["support_manifest"],parent_context=reader.ref(point_path),
        public_snapshot=dict(path=str(snapshot),manifest=reader.ref(snapshot/"manifest.json")),
        V73_V74_mechanism_selection=reader.ref(selection_path),
        fixed_before_generation=True,teacher_failure_replacement=False,
        collection_call_cap=12160,initial_L_sessions=128,initial_P_sessions=128,post_P_slots=128,
        post_condition_only_last_L_returned_call_with_prior_tool_history=True,
        post_remaining_budget="32-b",new_first_responses_from_V73_V74=0,
        existing_exact_collection_reused=False,existing_collection_reuse_scope="V72/V73/V74 artifacts contain evaluation/probe runs, not this predeclared training128 collection",
        new_model_calls=0,new_tool_executions=0,new_native_scores=0,private_references_read=False,
        source_refs=list(reader.sources.values())))
