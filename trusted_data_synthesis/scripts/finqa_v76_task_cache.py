"""Atomic complete-task V76 old-state AND fixed-teacher gradient bundles.

Teacher slots remain outside the old state plan and simplex. A task is complete
only after both parts are durably published in the same no-replace directory.
"""
from __future__ import annotations

import copy
import hashlib
import io
import json
import os
from pathlib import Path
from types import SimpleNamespace

import finqa_v76_binding as binding_api

require = binding_api.require


def _file_identity(path):
    require(not path.is_symlink(), 'gradient payload symlink forbidden')
    s = path.stat()
    return (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns)


def _tensor_identity(value):
    return tuple((kind,slot,name,id(tensor),tensor._version,tensor.untyped_storage()._cdata,
                  tuple(tensor.shape),tuple(tensor.stride()),tensor.storage_offset())
        for kind, part in (('old',value['values_cpu']),('teacher',value['teacher_values_cpu']))
        for slot, parameters in part.items() for name,tensor in parameters.items())


class MixedTaskCache:
    def __init__(self, root, binding, task_plan, parameter_spec, rt, *, materials,
                 original_cache_module=None):
        original_cache_module = original_cache_module or binding_api.old_module('finqa_v35_task_cache')
        self.original = original_cache_module.TaskCache(root,binding,task_plan,parameter_spec,rt)
        self.root,self.binding,self.plan,self.parameter_spec,self.rt = (
            self.original.root,self.original.binding,self.original.plan,self.original.parameter_spec,rt)
        self.binding_sha256 = self.original.binding_sha256
        self.materials = materials
        require(materials['status']=='COMPLETE' and materials['packages']
                and set(materials['tasks']) <= set(self.plan['task_ids']),
                'V76 requires existing nonempty fixed teacher material within old task support')
        self.verified_state = SimpleNamespace(values={},file_reads=0,pid=os.getpid())

    def task(self,task):return self.original.task(task)
    def directory(self,task):return self.original.directory(task)

    def expected_slots(self,task):
        row=self.materials['tasks'].get(task,{}).get('slots',{})
        return [slot for slot in ('initial','post') if row.get(slot) is not None]

    def _validate_teachers(self,task,values):
        require(isinstance(values,dict) and list(values)==self.expected_slots(task),
                'partial or additional fixed teacher gradients are forbidden')
        names=[row['name'] for row in self.parameter_spec]
        for slot,tensors in values.items():
            require(list(tensors)==names,'teacher parameter order differs')
            for item in self.parameter_spec:
                t=tensors[item['name']]
                require(isinstance(t,self.rt.torch.Tensor) and t.device.type=='cpu'
                    and list(t.shape)==item['shape'] and str(t.dtype)==item['dtype']
                    and t.layout==self.rt.torch.strided and not t.requires_grad
                    and bool(self.rt.torch.isfinite(t).all()),'invalid/nonfinite teacher gradient')
        return values

    def commit(self,task,values_cpu,teacher_values_cpu=None,receipt=None):
        from trusted_synthesis.core.immutable_artifacts import write_immutable_artifact_directory
        target=self.directory(task)
        require(not target.exists() and not target.is_symlink(),'complete mixed task cannot be overwritten')
        old=self.original._validate_values(task,values_cpu)
        teachers=self._validate_teachers(task,teacher_values_cpu if teacher_values_cpu is not None else {})
        payload=dict(schema='v76_complete_mixed_task_gradient_payload.v1',binding=self.binding,
            task_plan_id=self.plan['id'],task=self.task(task),parameter_spec=self.parameter_spec,
            material_id=self.materials['id'],values_cpu=old,teacher_values_cpu=teachers)
        stream=io.BytesIO();self.rt.torch.save(payload,stream);raw=stream.getvalue()
        body=dict(schema='v76_complete_mixed_task_gradient.v1',binding=self.binding,
            binding_sha256=self.binding_sha256,task_plan_id=self.plan['id'],task=self.task(task),
            parameter_spec=self.parameter_spec,material_id=self.materials['id'],
            complete_task=True,complete_fixed_teachers=True,teacher_slots=self.expected_slots(task),
            teacher_support_not_added_to_state_plan=True,gradient_sha256=hashlib.sha256(raw).hexdigest(),
            gradient_bytes=len(raw),gradient_semantic_digest=self.rt.v8._tree_digest(old),
            teacher_semantic_digest=self.rt.v8._tree_digest(teachers),
            payload_semantic_digest=self.rt.v8._tree_digest(payload),
            tensor_manifest=self.original._tensor_manifest(old),
            teacher_tensor_manifest=self.original._tensor_manifest(teachers),receipt=receipt)
        record=dict(body,id=binding_api.digest(body))
        write_immutable_artifact_directory(target,{'record.json':(json.dumps(record,
            ensure_ascii=False,sort_keys=True,indent=2,allow_nan=False)+'\n').encode(),'gradient.pt':raw})
        return record

    def _read_bundle(self,task):
        target=self.directory(task)
        require(target.is_dir() and not target.is_symlink()
            and {x.name for x in target.iterdir()}=={'record.json','gradient.pt'},
            'complete task requires one atomic old+teacher payload')
        before=tuple(_file_identity(target/name) for name in ('record.json','gradient.pt'))
        cached=self.verified_state.values.get(task)
        if cached is not None:
            payload,record,identity,tensors=cached
            require(before==identity and _tensor_identity(payload)==tensors,
                    'verified same-process task bytes or tensors changed')
            return payload,record
        record=binding_api.checked(target/'record.json')
        require(record['schema']=='v76_complete_mixed_task_gradient.v1'
            and record['binding']==self.binding and record['binding_sha256']==self.binding_sha256
            and record['task_plan_id']==self.plan['id'] and record['task']==self.task(task)
            and record['parameter_spec']==self.parameter_spec and record['material_id']==self.materials['id']
            and record['complete_task'] is True and record['complete_fixed_teachers'] is True
            and record['teacher_slots']==self.expected_slots(task),
            'mixed task belongs to another complete state/material/source')
        raw=(target/'gradient.pt').read_bytes()
        require(len(raw)==record['gradient_bytes'] and hashlib.sha256(raw).hexdigest()==record['gradient_sha256'],
                'complete mixed task bytes changed')
        payload=self.rt.torch.load(io.BytesIO(raw),map_location='cpu',weights_only=True)
        require(payload['schema']=='v76_complete_mixed_task_gradient_payload.v1'
            and all(payload[k]==record[k] for k in ('binding','task_plan_id','task','parameter_spec','material_id')),
            'mixed task payload binding changed')
        old=self.original._validate_values(task,payload['values_cpu'])
        teachers=self._validate_teachers(task,payload['teacher_values_cpu'])
        require(self.rt.v8._tree_digest(old)==record['gradient_semantic_digest']
            and self.rt.v8._tree_digest(teachers)==record['teacher_semantic_digest']
            and self.rt.v8._tree_digest(payload)==record['payload_semantic_digest']
            and self.original._tensor_manifest(old)==record['tensor_manifest']
            and self.original._tensor_manifest(teachers)==record['teacher_tensor_manifest'],
            'mixed task values or semantic hash changed')
        after=tuple(_file_identity(target/name) for name in ('record.json','gradient.pt'))
        require(before==after,'mixed task changed during cold read')
        self.verified_state.values[task]=(payload,record,after,_tensor_identity(payload))
        self.verified_state.file_reads+=1
        return payload,record

    def _read(self,task):
        payload,record=self._read_bundle(task)
        return payload['values_cpu'],record

    def read(self,task):return self._read(task)[0]
    def read_teachers(self,task):return self._read_bundle(task)[0]['teacher_values_cpu']

    def has(self,task):
        path=self.directory(task)
        if not path.exists() and not path.is_symlink():return False
        self._read_bundle(task);return True

    def _complete(self):
        require(all(self.directory(task).is_dir() for task in self.plan['task_ids']),
                'all complete original tasks and fixed teachers required, no zero fill')

    def assemble(self,device='cpu'):
        self._complete()
        return {task:self.rt.v8._DeviceGradients(self.read(task),device) for task in self.plan['task_ids']}

    def assemble_teachers(self,device='cpu'):
        self._complete()
        return {task:self.rt.v8._DeviceGradients(self.read_teachers(task),device) for task in self.plan['task_ids']}

    def coverage(self):
        complete=[task for task in self.plan['task_ids'] if self.has(task)]
        return dict(complete_task_ids=complete,missing_task_ids=[task for task in self.plan['task_ids'] if task not in set(complete)],
            complete_task_count=len(complete),total_task_count=len(self.plan['task_ids']))

    def verification_summary(self):
        return dict(binding_sha256=self.binding_sha256,process_id=os.getpid(),
            strict_payload_file_reads=self.verified_state.file_reads,
            verified_task_count=len(self.verified_state.values),material_id=self.materials['id'],
            atomic_old_and_fixed_teacher=True,cross_parameter_point_reuse=False)
