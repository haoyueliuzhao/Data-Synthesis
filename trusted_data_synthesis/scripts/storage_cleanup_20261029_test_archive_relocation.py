"""Move this cleanup's verified test archive to persistent system-disk storage."""
import os
from pathlib import Path

import storage_cleanup_20261029_cold_relocation as engine


def main():
    source_root = engine.ART / 'storage_cleanup_20261029_unused_01'
    output = source_root / 'backup_relocation_01'
    source = source_root / 'test_fixtures.tar.gz'
    destination = Path('/home/zhuxinrui/cold_storage/Data-Synthesis/local_test_archive_20261029_01/test_fixtures.tar.gz')
    engine.require(engine.file_sha(engine.__file__) ==
        '2c27ae33470f57daec67afb53707d3be885070f36a05fb7b8afc94bf008ede11', 'copy engine changed')
    engine.require(os.getuid() == os.geteuid() == 1004, 'registered archive owner required')
    engine.require(not output.exists(), 'single fresh relocation only')
    receipt = engine.checked(source_root / 'backup_verified.json')
    complete = engine.checked(source_root / 'complete.json')
    engine.require(complete['status'] == 'COMPLETE' and Path(receipt['archive']) == source,
                   'only the successful verified test backup may move')
    info = engine.identity(source, uid=1004)
    engine.require(info['bytes'] == receipt['archive_bytes'], 'archive size changed')
    engine.require(source == source.resolve() and not os.path.lexists(destination), 'source/target already redirected')
    scope = engine.Scope(source_root, source_root, output, {'unused_tests': destination},
                         {'unused_tests': Path('/home/zhuxinrui')})
    row = dict(group='unused_tests', source=str(source), destination=str(destination),
        destination_anchor='/home/zhuxinrui', bytes=info['bytes'],
        sha256=receipt['archive_sha256'], source_identity=info)
    capacities = engine.capacity(scope, [row])
    output.mkdir(mode=0o700)
    (output / 'producer.py').write_bytes(Path(__file__).read_bytes())
    plan = engine.publish(output / 'plan.json', dict(authorization='清理历史无用数据',
        row=row, source_receipt_id=receipt['id'], completed_cleanup_id=complete['id'],
        capacity=capacities, copy_engine_sha256=engine.file_sha(engine.__file__),
        data_movement_not_additional_global_reclamation=True))
    engine.publish(output / 'execution_intent.json', dict(plan_id=plan['id'], automatic_retry=False))
    copied = engine.copy_verified(scope, row, engine.CopyBudget(scope, [row]))
    engine.require(engine.identity(source, uid=1004) == info, 'source changed before replacement')
    engine.require(engine.identity(destination, uid=1004) == copied['destination_identity'],
                   'verified destination changed before replacement')
    link = source.with_name(source.name + '.relocation-link')
    engine.require(not os.path.lexists(link), 'temporary link already exists')
    os.symlink(destination, link)
    os.replace(link, source)
    engine.sync_directory(source.parent)
    result = engine.publish(output / 'result.json', dict(status='COMPLETE', plan_id=plan['id'],
        source=str(source), destination=str(destination), sha256=row['sha256'],
        data1_source_allocated_bytes_relocated=info['allocated_bytes'],
        system_disk_destination_allocated_bytes=copied['destination_identity']['allocated_bytes'],
        original_path_preserved_as_symlink=True, original_receipt_unchanged=True,
        no_new_scientific_operations=True))
    print(result['status'], result['id'])


if __name__ == '__main__':
    main()
