"""Four bounded CPU checks; never use the real cleanup targets."""
import hashlib
import json
import os
from pathlib import Path
import sys
import tarfile

import pytest

SCRIPTS = str(Path(__file__).resolve().parents[1] / 'scripts')
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)
import storage_cleanup_20261029_unused as cleanup


def setup_case(tmp_path, monkeypatch):
    case, data, probe = tmp_path / 'case', tmp_path / 'data', tmp_path / 'probe'
    for directory in (case, data, probe):
        directory.mkdir()
    (case / 'payload').write_bytes(b'recoverable test data\n')
    (case / 'alias').symlink_to(case / 'payload')
    sentinel = data / 'immutable.txt'
    sentinel.write_text('untouched')
    state = data / 'state.pt'
    state.write_bytes(b'tiny synthetic state; no tensor loading')
    digest = hashlib.sha256(state.read_bytes()).hexdigest()
    record = data / 'record.json'
    record.write_text(json.dumps(dict(state_sha256=digest)))
    (probe / 'record.json').write_text(json.dumps(dict(sample=[dict(path=str(state), sha256=digest)])))
    producer = data / 'probe.py'
    producer.write_text('# synthetic regeneration recipe\n')
    sample = probe / '0.ordinary.zst'
    sample.write_bytes(b'dispensable synthetic sample')
    for key, value in dict(REPO=tmp_path, ART=data, OUTPUT=data / 'audit', REVIEW=data / 'review.json',
                           ROOTS=frozenset({case}), SAMPLES=frozenset({sample}),
                           PROBE=probe, PROBE_SOURCE=producer, ORIGINAL_STATES=frozenset({state}),
                           OWNER_UID=os.getuid()).items():
        monkeypatch.setattr(cleanup, key, value)
    monkeypatch.setattr(cleanup, 'science_anchors', lambda: [sentinel, state, record, producer, probe / 'record.json'])
    monkeypatch.setattr(cleanup, 'runtime_snapshot', lambda _: dict(synthetic=True, no_process_signals=True))
    monkeypatch.setattr(cleanup, 'tracked_guard', lambda _: None)
    original_factory = cleanup.engine_for
    def factory(anchors):
        engine = original_factory(anchors)
        engine.process_guard = lambda _: dict(synthetic=True, hits=[])
        return engine
    monkeypatch.setattr(cleanup, 'engine_for', factory)
    members = [cleanup.metadata(case), *[cleanup.metadata(p) for p in sorted(case.iterdir())]]
    review = dict(schema='bounded_readonly_cleanup_candidate_audit.v1',
        directory_candidates=[dict(root=str(case), metadata=members[0], members=members,
                                   allocated_bytes=sum(x['allocated_bytes'] for x in members))],
        file_candidates=[dict(metadata=cleanup.metadata(sample))],
        storage_probe_originals=[dict(state=cleanup.metadata(state), record=cleanup.metadata(record),
                                     registered_state_sha256=digest, sample_record_sha256=digest)])
    cleanup.REVIEW.write_text(json.dumps(review))
    return case, data, probe, sample, sentinel, state, review


def test_outside_root_and_escaping_symlink_are_rejected(tmp_path, monkeypatch):
    case, data, probe, sample, sentinel, state, review = setup_case(tmp_path, monkeypatch)
    with pytest.raises(RuntimeError, match='exact reviewed'):
        cleanup.allowed_root(tmp_path)
    (case / 'outside').symlink_to(sentinel)
    with pytest.raises(RuntimeError, match='symlink escaped'):
        cleanup.inventory(case, cleanup.engine_for([]))
    assert sentinel.read_text() == 'untouched' and sample.exists()


def test_changed_reviewed_member_is_retained_before_plan(tmp_path, monkeypatch):
    case, data, probe, sample, sentinel, state, review = setup_case(tmp_path, monkeypatch)
    (case / 'payload').write_bytes(b'a different test result must not be removed')
    with pytest.raises(RuntimeError, match='identity or contents changed'):
        cleanup.prepare()
    assert not cleanup.OUTPUT.exists() and case.exists() and sample.exists()


def test_real_archive_verifies_before_removal_and_freezes_one_apply(tmp_path, monkeypatch):
    case, data, probe, sample, sentinel, state, review = setup_case(tmp_path, monkeypatch)
    cleanup.prepare()
    original_remove = cleanup.shutil.rmtree
    witnessed = []
    def verified_remove(path, *args, **kwargs):
        proof = json.loads((cleanup.OUTPUT / 'backup_verified.json').read_text())
        assert proof['all_regular_files_content_verified'] and proof['verified_members'] == 3
        with tarfile.open(cleanup.OUTPUT / 'test_fixtures.tar.gz', 'r:gz') as archive:
            assert archive.extractfile(str((case / 'payload').relative_to('/'))).read() == b'recoverable test data\n'
        witnessed.append(str(path))
        return original_remove(path, *args, **kwargs)
    verified_remove.avoids_symlink_attacks = original_remove.avoids_symlink_attacks
    monkeypatch.setattr(cleanup.shutil, 'rmtree', verified_remove)
    result = cleanup.apply()
    assert result['status'] == 'COMPLETE' and witnessed == [str(case)]
    assert not case.exists() and not sample.exists()
    assert sentinel.read_text() == 'untouched' and state.exists() and (probe / 'record.json').exists()
    assert result['protected_files_unchanged'] and (cleanup.OUTPUT / 'cleanup.py').is_file()
    with pytest.raises(RuntimeError, match='no automatic cleanup retry'):
        cleanup.apply()


def test_samples_require_exact_scope_and_unchanged_originals(tmp_path, monkeypatch):
    case, data, probe, sample, sentinel, state, review = setup_case(tmp_path, monkeypatch)
    extra = probe / 'unreviewed.zst'
    extra.write_bytes(b'keep')
    changed = dict(review, file_candidates=[*review['file_candidates'], dict(metadata=cleanup.metadata(extra))])
    with pytest.raises(RuntimeError, match='exact regenerable sample list'):
        cleanup.validate_samples(changed)
    state.write_bytes(b'changed original bytes')
    with pytest.raises(RuntimeError, match='original checkpoint or record identity changed'):
        cleanup.validate_samples(review)
    assert case.exists() and sample.exists() and extra.exists()
