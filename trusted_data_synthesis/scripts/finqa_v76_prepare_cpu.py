"""Single CPU-only, no-retry preparation child for the V75 repair and source strata."""
from __future__ import annotations
import json
import os
from pathlib import Path
import signal
import sys
import threading
import time
import finqa_v76_binding as b
GIB=1024**3

def policy():
    return dict(schema='v76_preparation_CPU_resource_policy.v1',max_cpu_children=1,
        rss_historical_peak_limit_bytes=64*GIB,host_available_reserve_bytes=96*GIB,
        startup_required_available_bytes=160*GIB,CUDA_initialized=False,
        new_native_scores=0,new_model_calls=0,automatic_retry=False)

def run():
    root=b.ROOT;directory=root/'preflight_execution/attempt0001'
    b.require(Path(__file__).resolve().parent==root/'implementation','frozen CPU preparation entry required')
    b.require(os.environ.get('CUDA_VISIBLE_DEVICES')=='','preparation must have no CUDA devices exposed')
    import finqa_v76_resources as resource
    import finqa_v76_preflight as preflight
    observations=[];failures=[];done=threading.Event();thread=None;status='FAILED';result=None
    started=time.time();limits=policy()
    def check():
        memory=resource.process_memory(os.getpid());host=resource.host_memory()
        b.require(isinstance(memory,dict) and isinstance(host,dict),'CPU resource observation unavailable')
        row=dict(epoch=time.time(),peak_rss_bytes=memory['peak_rss_bytes'],available_bytes=host['available_bytes'])
        row['passed']=row['peak_rss_bytes']<=64*GIB and row['available_bytes']>=96*GIB
        observations.append(row)
        b.require(row['passed'],'preparation CPU RAM gate failed')
        b.require(not(root/'STOP').exists(),'explicit stop during CPU preparation')
    def monitor():
        while not done.wait(1):
            try:check()
            except BaseException as error:
                failures.append(dict(type=type(error).__name__,error=str(error)))
                os.kill(os.getpid(),signal.SIGTERM);return
    def stopped(signum,_frame):raise RuntimeError(f'CPU preparation stopped by signal {signum}')
    old={s:signal.getsignal(s) for s in (signal.SIGTERM,signal.SIGINT)}
    for s in old:signal.signal(s,stopped)
    try:
        check();b.require(observations[-1]['available_bytes']>=160*GIB,'CPU startup RAM below160GiB')
        thread=threading.Thread(target=monitor,daemon=True);thread.start()
        result=preflight.prepare(root)
        check();torch=sys.modules.get('torch')
        b.require(torch is None or not torch.cuda.is_initialized(),'CPU preparation initialized CUDA')
        b.require(not failures,'CPU preparation monitor failed');status='COMPLETE'
    except BaseException as error:
        failures.append(dict(type=type(error).__name__,error=str(error)));raise
    finally:
        done.set()
        if thread:thread.join(timeout=5)
        for s in old:signal.signal(s,old[s])
        b.publish(directory/'resources/record.json',dict(status=status,policy=limits,pid=os.getpid(),
            birth=resource.birth(os.getpid()),started_epoch=started,finished_epoch=time.time(),
            all_gates_passed=all(r['passed'] for r in observations) and not failures,
            observations=observations,failures=failures,CUDA_initialized=False))
    return b.publish(directory/'result/record.json',dict(status='COMPLETE',pid=os.getpid(),
        analysis=result,resources=b.entry(directory/'resources/record.json')))

if __name__=='__main__':
    value=run();print(json.dumps(dict(id=value['id'],status=value['status'])))
