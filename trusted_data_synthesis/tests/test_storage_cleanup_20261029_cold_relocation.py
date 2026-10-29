"""Small actual-byte fixtures; source in tmp and target in ephemeral /dev/shm."""
from pathlib import Path
from dataclasses import replace
import importlib.util
import os
import shutil
import sys
import tempfile
import pytest

SCRIPT=Path(__file__).resolve().parents[1]/'scripts/storage_cleanup_20261029_cold_relocation.py'
spec=importlib.util.spec_from_file_location('cold_relocation_fixture',SCRIPT)
r=importlib.util.module_from_spec(spec);sys.modules[spec.name]=r;spec.loader.exec_module(r)


@pytest.fixture
def scope(tmp_path):
    if not Path('/dev/shm').is_dir():pytest.skip('actual distinct ephemeral filesystem unavailable')
    with tempfile.TemporaryDirectory(prefix='v76-relocation-fixture-',dir='/dev/shm') as target:
        source=tmp_path/'source';source.mkdir();receipts=tmp_path/'receipts';receipts.mkdir()
        destination=Path(target)
        if destination.stat().st_dev==source.stat().st_dev:pytest.skip('actual distinct filesystem required')
        destinations={g:destination/'private'/f'{g}.tar.zst' for g in r.GROUPS}
        for i,g in enumerate(r.GROUPS,1):
            p=source/(g+'.tar.zst');p.write_bytes((bytes([i])+b'unchanged scientific archive\0')*4096)
            r.publish(receipts/(g+'_verified.json'),dict(group=g,archive=str(p),archive_bytes=p.stat().st_size,
                archive_sha256=r.file_sha(p),member_manifest=g+'_members.json.gz',member_manifest_sha256='bound-member-sha'))
        yield r.Scope(source,receipts,tmp_path/'operation',destinations,{g:destination for g in r.GROUPS},
            uid=os.getuid(),reserve_bytes=1024**2)


def test_prepare_is_metadata_only_and_fixes_three_paths(scope,monkeypatch):
    original=r.file_sha
    def bounded(path):
        assert Path(path).parent!=scope.source_root,'prepare must not reread archive content'
        return original(path)
    monkeypatch.setattr(r,'file_sha',bounded)
    plan=r.prepare(scope,SCRIPT)
    assert len(plan['rows'])==3
    assert plan['data1_space_relocation_not_whole_machine_reclamation']
    assert not any(p.exists() for p in scope.destinations.values())
    assert not (scope.output/'execution_intent.json').exists()
    assert all(not (scope.source_root/(g+'.tar.zst')).is_symlink() for g in r.GROUPS)


def test_all_copies_sha_verified_fsynced_before_first_atomic_source_replace(scope,monkeypatch):
    plan=r.prepare(scope,SCRIPT);receipts={g:r.file_sha(scope.receipt_root/(g+'_verified.json')) for g in r.GROUPS}
    original=r.os.replace;seen=[]
    sources={scope.source_root/(g+'.tar.zst') for g in r.GROUPS}
    def observe(src,dst):
        if Path(dst) in sources:
            record=r.checked(scope.output/'all_copies_verified.json')
            assert record['source_replacements_so_far']==0 and len(record['verified_copies'])==3
            assert all(r.checked(scope.output/'copy_verified'/f'{g}.json')['full_destination_SHA_readback_passed'] for g in r.GROUPS)
            if not seen:assert all(not p.is_symlink() for p in sources)
            seen.append(str(dst))
        return original(src,dst)
    monkeypatch.setattr(r.os,'replace',observe)
    result=r.apply(scope)
    assert result['status']=='COMPLETE' and len(seen)==3
    assert result['original_scientific_contents_deleted'] is False
    assert result['whole_machine_net_reclamation_claimed'] is False
    for row in plan['rows']:
        old,new=Path(row['source']),Path(row['destination'])
        assert old.is_symlink() and old.resolve()==new
        assert r.file_sha(old)==r.file_sha(new)==row['sha256']
        assert new.stat().st_mode&0o777==0o600 and new.parent.stat().st_mode&0o777==0o700
        assert r.file_sha(scope.receipt_root/(row['group']+'_verified.json'))==receipts[row['group']]
    with pytest.raises(RuntimeError,match='no automatic retry'):r.apply(scope)


def test_wrong_source_receipt_sha_never_replaces_originals(scope):
    path=scope.receipt_root/(r.GROUPS[0]+'_verified.json');body=r.checked(path);body.pop('id');body['archive_sha256']='0'*64
    path.unlink();r.publish(path,body)
    r.prepare(scope,SCRIPT)
    with pytest.raises(RuntimeError):r.apply(scope,max_copy_workers=1)
    assert not (scope.output/'all_copies_verified.json').exists()
    assert all(p.is_file() and not p.is_symlink() for p in scope.source_root.iterdir())
    assert r.checked(scope.output/'result.json')['status']=='PARTIAL_STOPPED_NO_RETRY'


def test_destination_readback_mismatch_retains_all_originals(scope,monkeypatch):
    r.prepare(scope,SCRIPT);original=r.file_sha
    monkeypatch.setattr(r,'file_sha',lambda path:'0'*64 if Path(path).name.endswith('.copying') else original(path))
    with pytest.raises(RuntimeError):r.apply(scope,max_copy_workers=1)
    assert all(not (scope.source_root/(g+'.tar.zst')).is_symlink() for g in r.GROUPS)
    assert r.checked(scope.output/'result.json')['atomically_relocated_groups']==[]


def test_changed_source_identity_after_plan_stops_before_copy(scope):
    r.prepare(scope,SCRIPT)
    path=scope.source_root/(r.GROUPS[0]+'.tar.zst');path.write_bytes(path.read_bytes()+b'x')
    with pytest.raises(RuntimeError,match='source changed'):r.apply(scope)
    assert not (scope.output/'execution_intent.json').exists()


def test_destination_created_after_plan_is_not_overwritten(scope):
    r.prepare(scope,SCRIPT);destination=scope.destinations[r.GROUPS[0]]
    destination.parent.mkdir(mode=0o700);destination.write_bytes(b'unrelated')
    with pytest.raises(RuntimeError,match='destination must still be absent'):r.apply(scope)
    assert destination.read_bytes()==b'unrelated'


def test_symlink_source_rejected_before_plan(scope):
    path=scope.source_root/(r.GROUPS[0]+'.tar.zst');real=path.with_suffix('.kept');path.rename(real);path.symlink_to(real)
    with pytest.raises(RuntimeError,match='redirected'):r.prepare(scope,SCRIPT)
    assert not scope.output.exists()


def test_insufficient_capacity_rejects_without_external_directory_creation(scope,monkeypatch):
    monkeypatch.setattr(r.shutil,'disk_usage',lambda _:shutil._ntuple_diskusage(100,99,1))
    with pytest.raises(RuntimeError,match='reserved capacity'):r.prepare(scope,SCRIPT)
    assert not scope.output.exists() and not next(iter(scope.destinations.values())).parent.exists()


def test_same_filesystem_is_not_claimed_as_data1_relocation(scope):
    local={g:scope.source_root.parent/'destination'/(g+'.tar.zst') for g in r.GROUPS}
    other=replace(scope,destinations=local,destination_anchors={g:scope.source_root.parent for g in r.GROUPS})
    with pytest.raises(RuntimeError,match='another filesystem'):r.prepare(other,SCRIPT)
