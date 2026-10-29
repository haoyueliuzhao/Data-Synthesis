"""Relocate exactly three existing lossless cold archives, preserving old paths.

prepare is metadata-only. apply copies and hashes every source, re-reads and hashes
every destination, fsyncs all copies, then atomically replaces each old archive
file by a symlink to its verified new location. No scientific member is deleted.
An interrupted apply is recorded and never automatically retried.
"""
from __future__ import annotations
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import threading

REPO=Path('/data1/zhuxinrui/projects/Data-Synthesis')
ART=REPO/'trusted_data_synthesis/artifacts'
OUTPUT=ART/'storage_cleanup_20261029_cold_relocation_01'
OLD=ART/'cold_archive_20261019_01'
RECEIPTS=ART/'storage_cleanup_20261019_cold_archive_01'
GROUPS=('old_class_seed137','old_class_seed251','old_class_seed389')
RESERVE=16*1024**3
CHUNK=8*1024**2


def require(condition,message):
    if not condition:raise RuntimeError(message)


def encode(value):return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
def digest(value):return hashlib.sha256(encode(value)).hexdigest()
def now():return datetime.now(timezone.utc).isoformat()


def file_sha(path):
    value=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda:stream.read(CHUNK),b''):value.update(block)
    return value.hexdigest()


def identity(path,*,regular=True,uid=None):
    path=Path(path);value=path.lstat()
    if regular:
        require(stat.S_ISREG(value.st_mode) and value.st_nlink==1 and not path.is_symlink(),
                'archive must remain an ordinary single-link file: '+str(path))
    if uid is not None:require(value.st_uid==uid,'archive owner changed: '+str(path))
    return dict(device=value.st_dev,inode=value.st_ino,mode=value.st_mode,uid=value.st_uid,gid=value.st_gid,
        links=value.st_nlink,bytes=value.st_size,mtime_ns=value.st_mtime_ns,ctime_ns=value.st_ctime_ns,
        allocated_bytes=value.st_blocks*512)


def sync_directory(path):
    descriptor=os.open(path,os.O_RDONLY|os.O_DIRECTORY)
    try:os.fsync(descriptor)
    finally:os.close(descriptor)


def checked(path):
    value=json.loads(Path(path).read_bytes())
    require(value.get('id')==digest({k:v for k,v in value.items() if k!='id'}),'record identity changed: '+str(path))
    return value


def publish(path,body):
    path=Path(path);value=dict(body,id=digest(body));path.parent.mkdir(parents=True,exist_ok=True)
    require(not os.path.lexists(path),'immutable relocation record already exists: '+str(path))
    with path.open('xb') as stream:
        stream.write(json.dumps(value,ensure_ascii=False,sort_keys=True,indent=2,allow_nan=False).encode()+b'\n')
        stream.flush();os.fsync(stream.fileno())
    sync_directory(path.parent);return value


@dataclass(frozen=True)
class Scope:
    source_root: Path
    receipt_root: Path
    output: Path
    destinations: dict
    destination_anchors: dict
    uid: int=1004
    reserve_bytes: int=RESERVE


def production_scope():
    data0=Path('/data0/zhuxinrui/cold_storage/Data-Synthesis/cold_archive_20261019_01')
    system=Path('/home/zhuxinrui/cold_storage/Data-Synthesis/cold_archive_20261019_01')
    return Scope(OLD,RECEIPTS,OUTPUT,
        {g:(system if g.endswith('389') else data0)/(g+'.tar.zst') for g in GROUPS},
        {g:Path('/home/zhuxinrui') if g.endswith('389') else Path('/data0') for g in GROUPS})


def destination_parent(path,anchor,uid,*,create=False):
    path,anchor=Path(path),Path(anchor)
    require(path.is_absolute() and anchor.is_absolute() and path.is_relative_to(anchor)
        and anchor==anchor.resolve() and anchor.is_dir(),'target must remain under its exact canonical persistent anchor')
    current=anchor
    for name in path.parent.relative_to(anchor).parts:
        current=current/name
        if not os.path.lexists(current):
            if not create:return current.parent
            current.mkdir(mode=0o700);sync_directory(current.parent)
        value=current.lstat()
        require(stat.S_ISDIR(value.st_mode) and not current.is_symlink() and value.st_uid==uid
            and value.st_mode&0o077==0,'target directory must be private, owned and unredirected: '+str(current))
    return current


def capacity(scope,rows):
    devices={}
    for row in rows:
        parent=destination_parent(row['destination'],row['destination_anchor'],scope.uid)
        dev=parent.stat().st_dev
        require(dev!=row['source_identity']['device'],'relocation target must be another filesystem')
        value=devices.setdefault(dev,dict(device=dev,path=str(parent),required_copy_bytes=0,
            available_bytes=shutil.disk_usage(parent).free,reserve_bytes=scope.reserve_bytes))
        value['required_copy_bytes']+=row['bytes']
    for value in devices.values():
        value['remaining_after_copy_bytes']=value['available_bytes']-value['required_copy_bytes']
        require(value['remaining_after_copy_bytes']>=scope.reserve_bytes,'destination lacks full copies plus reserved capacity')
    return list(devices.values())


def prepare(scope,producer):
    require(os.getuid()==os.geteuid()==scope.uid,'only the registered archive owner may relocate')
    require(not scope.output.exists(),'one fresh relocation plan required')
    require(tuple(scope.destinations)==GROUPS,'only the three registered historical archive groups are allowed')
    rows=[]
    for group in GROUPS:
        source=scope.source_root/(group+'.tar.zst');receipt_path=scope.receipt_root/(group+'_verified.json')
        require(source==source.resolve(),'source path is already redirected')
        receipt=checked(receipt_path);info=identity(source,uid=scope.uid)
        require(receipt['group']==group and Path(receipt['archive'])==source
            and receipt['archive_bytes']==info['bytes'],'source size or old archive receipt changed')
        destination=Path(scope.destinations[group]);anchor=Path(scope.destination_anchors[group])
        destination_parent(destination,anchor,scope.uid)
        require(not os.path.lexists(destination) and not os.path.lexists(destination.with_name(destination.name+'.copying')),
                'target archive/copying file exists; never overwrite')
        rows.append(dict(group=group,source=str(source),destination=str(destination),destination_anchor=str(anchor),
            bytes=info['bytes'],sha256=receipt['archive_sha256'],source_identity=info,
            old_receipt=dict(path=str(receipt_path),id=receipt['id'],sha256=file_sha(receipt_path)),
            member_manifest=receipt['member_manifest'],member_manifest_sha256=receipt['member_manifest_sha256']))
    capacities=capacity(scope,rows)
    require(len({r['source_identity']['device'] for r in rows})==1,'source archives must share the data1 filesystem')
    require(sum(r['bytes'] for r in rows)>0,'empty relocation is not authorized')
    scope.output.mkdir(mode=0o700);sync_directory(scope.output.parent)
    producer=Path(producer);snapshot=scope.output/'relocate.py'
    with snapshot.open('xb') as stream:
        stream.write(producer.read_bytes());stream.flush();os.fsync(stream.fileno())
    os.chmod(snapshot,0o600);sync_directory(scope.output)
    return publish(scope.output/'plan.json',dict(schema='cold_archive_three_package_relocation_plan.v1',
        created_at=now(),authorization='先整理历史数据，腾出数据盘空间',scope='three already verified 20261019 old_class archives only',
        owner_uid=scope.uid,rows=rows,source_filesystem_device=rows[0]['source_identity']['device'],
        total_logical_bytes=sum(r['bytes'] for r in rows),total_source_allocated_bytes=sum(r['source_identity']['allocated_bytes'] for r in rows),
        destination_capacity=capacities,destination_reserve_bytes=scope.reserve_bytes,
        producer=dict(path=str(snapshot),sha256=file_sha(snapshot)),
        all_destination_SHA_verification_and_fsync_before_any_source_replacement=True,
        original_source_paths_preserved_as_atomic_symlinks=True,original_receipts_and_SHA_unchanged=True,
        data1_space_relocation_not_whole_machine_reclamation=True,archive_contents_recoverable=True,
        new_model_or_scientific_data_changes=0,automatic_retry=False))


class CopyBudget:
    def __init__(self,scope,rows):
        self.scope=scope;self.lock=threading.Lock();self.progress={};self.abort=threading.Event()
        self.remaining={}
        for row in rows:
            parent=destination_parent(row['destination'],row['destination_anchor'],scope.uid,create=True)
            device=parent.stat().st_dev
            self.remaining[device]=self.remaining.get(device,0)+row['bytes']
            self.progress[row['group']]=dict(phase='WAITING',copied_bytes=0,total_bytes=row['bytes'],device=device)
    def update(self,row,*,add=0,phase=None):
        with self.lock:
            require(not self.abort.is_set(),'another copy failed; stop without replacing any source')
            item=self.progress[row['group']];item['copied_bytes']+=add
            self.remaining[item['device']]-=add
            if phase is not None:item['phase']=phase
            available=shutil.disk_usage(Path(row['destination']).parent).free
            require(available>=self.remaining[item['device']]+self.scope.reserve_bytes,
                    'destination capacity fell below remaining bytes plus reserve')
            temporary=self.scope.output/'progress.json.tmp'
            temporary.write_text(json.dumps(dict(updated_at=now(),groups=self.progress),sort_keys=True,indent=2)+'\n')
            os.replace(temporary,self.scope.output/'progress.json')


def copy_verified(scope,row,budget):
    source=Path(row['source']);destination=Path(row['destination']);temporary=destination.with_name(destination.name+'.copying')
    require(identity(source,uid=scope.uid)==row['source_identity'],'source changed before archive copy')
    require(not os.path.lexists(destination) and not os.path.lexists(temporary),'target exists; never overwrite')
    source_fd=os.open(source,os.O_RDONLY|os.O_NOFOLLOW)
    target_fd=None;value=hashlib.sha256();total=0
    try:
        stat_before=os.fstat(source_fd)
        require(stat_before.st_ino==row['source_identity']['inode'] and stat_before.st_dev==row['source_identity']['device'],
                'source identity changed while opening')
        target_fd=os.open(temporary,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
        budget.update(row,phase='COPYING')
        with os.fdopen(source_fd,'rb',closefd=False) as incoming,os.fdopen(target_fd,'wb',closefd=False) as outgoing:
            for block in iter(lambda:incoming.read(CHUNK),b''):
                value.update(block);outgoing.write(block);total+=len(block)
                budget.update(row,add=len(block))
            outgoing.flush();os.fsync(target_fd)
        require(total==row['bytes'] and value.hexdigest()==row['sha256'],'copied source SHA differs from original verified receipt')
        require(identity(source,uid=scope.uid)==row['source_identity'],'source changed during archive copy')
    finally:
        os.close(source_fd)
        if target_fd is not None:os.close(target_fd)
    budget.update(row,phase='DESTINATION_SHA_VERIFICATION')
    require(temporary.stat().st_size==row['bytes'] and file_sha(temporary)==row['sha256'],
            'full destination readback SHA mismatch; all originals retained')
    # Hard-link publication is exclusive; it cannot replace an existing target.
    os.link(temporary,destination,follow_symlinks=False);temporary.unlink();os.chmod(destination,0o600)
    with destination.open('rb') as stream:os.fsync(stream.fileno())
    sync_directory(destination.parent)
    target_info=identity(destination,uid=scope.uid)
    require(target_info['bytes']==row['bytes'] and target_info['device']!=row['source_identity']['device'],
            'verified target location or size changed')
    budget.update(row,phase='VERIFIED_FSYNCED')
    return publish(scope.output/'copy_verified'/f"{row['group']}.json",dict(
        schema='cold_archive_destination_copy_verified.v1',group=row['group'],source=row['source'],destination=row['destination'],
        source_identity=row['source_identity'],destination_identity=target_info,sha256=row['sha256'],bytes=total,
        source_hash_matches_original_receipt=True,full_destination_SHA_readback_passed=True,
        destination_fsynced=True,directory_fsynced=True,verified_at=now()))


def apply(scope,*,max_copy_workers=3):
    require(os.getuid()==os.geteuid()==scope.uid,'only the registered archive owner may relocate')
    require(type(max_copy_workers) is int and 1<=max_copy_workers<=3,'copy concurrency outside fixed1-3 bound')
    plan=checked(scope.output/'plan.json');rows=plan['rows']
    require(plan['owner_uid']==scope.uid and plan['destination_reserve_bytes']==scope.reserve_bytes
        and [r['group'] for r in rows]==list(GROUPS),'fixed plan scope changed')
    require(file_sha(plan['producer']['path'])==plan['producer']['sha256'],'frozen relocation implementation changed')
    require(Path(__file__).resolve()==Path(plan['producer']['path']).resolve() or scope.output!=OUTPUT,
            'production apply must execute the exact frozen producer')
    require(not (scope.output/'execution_intent.json').exists(),'attempt already consumed; no automatic retry')
    for row in rows:
        require(Path(row['source'])==scope.source_root/(row['group']+'.tar.zst')
            and Path(row['destination'])==Path(scope.destinations[row['group']])
            and Path(row['destination_anchor'])==Path(scope.destination_anchors[row['group']]),'plan path scope changed')
        require(identity(row['source'],uid=scope.uid)==row['source_identity'],'source changed since plan')
        require(file_sha(row['old_receipt']['path'])==row['old_receipt']['sha256'],'original archive receipt changed')
        require(not os.path.lexists(row['destination']),'destination must still be absent')
    capacities=capacity(scope,rows);free_before=shutil.disk_usage(scope.source_root).free
    publish(scope.output/'execution_intent.json',dict(plan_id=plan['id'],at=now(),destination_capacity=capacities,
        data1_free_before=free_before,copy_workers=max_copy_workers,original_archives_intact=True))
    verified={};replaced=[];success=False;failure=None
    try:
        budget=CopyBudget(scope,rows)
        with ThreadPoolExecutor(max_workers=max_copy_workers) as executor:
            futures={executor.submit(copy_verified,scope,row,budget):row['group'] for row in rows}
            copy_errors=[]
            for future in as_completed(futures):
                try:
                    result=future.result();verified[result['group']]=result
                except BaseException as error:
                    copy_errors.append(error);budget.abort.set()
            if copy_errors:raise copy_errors[0]
        require(set(verified)==set(GROUPS),'all three copies required before any source replacement')
        for row in rows:
            require(identity(row['source'],uid=scope.uid)==row['source_identity'],'source changed after copies verified')
            require(identity(row['destination'],uid=scope.uid)==verified[row['group']]['destination_identity'],
                    'verified destination changed before source replacement')
        publish(scope.output/'all_copies_verified.json',dict(plan_id=plan['id'],at=now(),
            verified_copies={g:dict(path=str(scope.output/'copy_verified'/f'{g}.json'),id=verified[g]['id']) for g in GROUPS},
            all_three_destination_hashes_and_fsync_complete=True,source_replacements_so_far=0))
        for row in rows:
            source=Path(row['source']);destination=Path(row['destination'])
            require(identity(source,uid=scope.uid)==row['source_identity'],'source changed before atomic replacement')
            require(identity(destination,uid=scope.uid)==verified[row['group']]['destination_identity'],
                    'target changed before atomic replacement')
            link=source.with_name('.'+source.name+'.relocation-'+plan['id'][:16])
            require(not os.path.lexists(link),'unexpected relocation link already exists')
            os.symlink(str(destination),link)
            os.replace(link,source);sync_directory(source.parent)
            require(source.is_symlink() and source.resolve()==destination and source.stat().st_size==row['bytes'],
                    'old archive path failed to resolve to its verified bytes')
            replaced.append(row['group'])
            publish(scope.output/'replaced'/f"{row['group']}.json",dict(plan_id=plan['id'],group=row['group'],
                old_path=str(source),new_path=str(destination),at=now(),atomic_replace=True,
                archive_SHA_unchanged=row['sha256'],old_receipt_unchanged=True))
        success=True
    except BaseException as error:
        failure=dict(type=type(error).__name__,message=str(error));raise
    finally:
        publish(scope.output/'result.json',dict(schema='cold_archive_three_package_relocation_result.v1',
            status='COMPLETE' if success else 'PARTIAL_STOPPED_NO_RETRY',plan_id=plan['id'],at=now(),failure=failure,
            copied_and_verified_groups=sorted(verified),atomically_relocated_groups=replaced,
            all_three_verified_before_first_source_replacement=(scope.output/'all_copies_verified.json').exists(),
            data1_original_allocated_bytes_unlinked=sum(r['source_identity']['allocated_bytes'] for r in rows if r['group'] in replaced),
            observed_data1_free_delta=shutil.disk_usage(scope.source_root).free-free_before,
            observed_disk_delta_not_attributed_only_to_relocation=True,
            verified_destination_allocated_bytes=sum(v['destination_identity']['allocated_bytes'] for v in verified.values()),
            whole_machine_net_reclamation_claimed=False,operation_is_cross_filesystem_relocation=True,
            original_paths_accessible=all(Path(r['source']).exists() for r in rows),original_receipts_modified=False,
            original_scientific_contents_deleted=False,model_feedback_gradient_sources_modified=False,
            data1_free_before=free_before,data1_free_after=shutil.disk_usage(scope.source_root).free,
            no_GPU_API_or_process_signals=True,automatic_retry=False))
    return checked(scope.output/'result.json')


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('action',choices=('prepare','apply'))
    args=parser.parse_args(argv);scope=production_scope()
    result=prepare(scope,__file__) if args.action=='prepare' else apply(scope)
    print(json.dumps({key:result[key] for key in ('id','status','total_logical_bytes','total_source_allocated_bytes',
        'data1_original_allocated_bytes_unlinked','atomically_relocated_groups') if key in result},sort_keys=True))

if __name__=='__main__':main()
