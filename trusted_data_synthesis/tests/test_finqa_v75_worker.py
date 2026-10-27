"""Training consumes only independently accepted material CPU exits."""
from pathlib import Path
import sys
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import finqa_v75_binding as b
import finqa_v75_worker as worker


def fixture(root,*,returncode=0):
    phase=root/'materials_preparation';attempt=phase/'attempt0001'
    b.publish(root/'materials/record.json',dict(protocol_id='protocol',status='COMPLETE',packages={'demo':'fixture'}))
    artifact=b.entry(root/'materials/record.json')
    b.publish(attempt/'launch/record.json',dict(protocol_id='protocol',pid=12345,birth='555',phase='materials_preparation',kind='CPU_phase'))
    b.publish(attempt/'actual_exit/record.json',dict(protocol_id='protocol',pid=12345,birth='555',actual_waitpid_observed=True,returncode=returncode))
    b.publish(attempt/'resources/closeout/record.json',dict(protocol_id='protocol',pid=12345,birth='555',status='COMPLETE',all_gates_passed=True,CUDA_initialized=False))
    resources=b.entry(attempt/'resources/closeout/record.json')
    b.publish(attempt/'result/record.json',dict(protocol_id='protocol',pid=12345,status='COMPLETE',resources=resources,analysis=artifact))
    return b.publish(phase/'accepted/record.json',dict(protocol_id='protocol',phase='materials_preparation',analysis=artifact,
        actual_exit=b.entry(attempt/'actual_exit/record.json'),result=b.entry(attempt/'result/record.json'),resources=resources))


def test_training_materials_require_bound_actual_cpu_exit_zero(tmp_path,monkeypatch):
    monkeypatch.setattr(b,'ROOT',tmp_path)
    expected=fixture(tmp_path)
    assert worker.require_materials_accepted({'id':'protocol'})==expected


def test_saved_complete_materials_cannot_hide_actual_nonzero_cpu_exit(tmp_path,monkeypatch):
    monkeypatch.setattr(b,'ROOT',tmp_path)
    fixture(tmp_path,returncode=1)
    with pytest.raises(ValueError,match='successful materials CPU actual exit'):
        worker.require_materials_accepted({'id':'protocol'})
