"""CPU-only synthetic checks for the read-only linear manifest adapter.

Every input is built under pytest's temporary directory.  No experiment archive,
Teacher/Student result, materialization worker, API, or accelerator is opened.
"""

import errno
import gc
import hashlib
import json
import os
import stat
import struct
import threading
import weakref
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

import pytest

from trusted_synthesis.experiments.finance_qa_vnext_catalog_bridge.catalog import (
    Parent as BaseParent,
)
from trusted_synthesis.experiments.finance_qa_vnext_linear_postprocess import manifest
from trusted_synthesis.experiments.finance_qa_vnext_task_build.archive import record


def put(path, raw):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)
    return raw


def json_bytes(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def fixture(tmp_path, *, count=3, members=None, relative="parent"):
    directory = tmp_path / relative
    supplied = members or {
        f"nested/member_{index:04d}.json": json_bytes({"number": index, "value": "synthetic"})
        for index in range(count)
    }
    rows = []
    for name, raw in supplied.items():
        put(directory / name, raw)
        rows.append({"path": name, "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()})
    value = record("manifest", members=rows)
    put(directory / "manifest.json", json_bytes(value))
    return directory, value, supplied


def adapter(tmp_path, **kwargs):
    directory, value, members = fixture(tmp_path, **kwargs)
    parent = manifest.LinearParent(tmp_path, str(directory.relative_to(tmp_path)), value["id"])
    return parent, directory, value, members


def replace_preserving_size_and_mtime(path, replacement):
    before = path.stat()
    assert len(replacement) == before.st_size
    path.write_bytes(replacement)
    os.utime(path, ns=(before.st_atime_ns, before.st_mtime_ns))
    after = path.stat()
    assert (after.st_size, after.st_mtime_ns) == (before.st_size, before.st_mtime_ns)
    return before, after


@pytest.mark.parametrize("count", [1, 9])
def test_static_declared_parent_outputs_match_base_parent(tmp_path, count):
    linear, directory, value, supplied = adapter(tmp_path, count=count)
    base = BaseParent(tmp_path, "parent", value["id"])
    assert linear.root == base.root
    assert linear.relative == base.relative
    assert linear.directory == base.directory == directory
    assert linear.manifest == base.manifest
    assert linear.members == base.members
    assert linear.manifest_sha256 == base.manifest_sha256
    assert linear.descriptor() == base.descriptor()
    assert linear.check_manifest() == base.check_manifest()
    for name, raw in supplied.items():
        assert linear.bytes(name) == base.bytes(name) == raw
        assert linear.read(name) == base.read(name) == json.loads(raw)
    assert linear.verify_all() == base.verify_all() == value["id"]


def test_manifest_pin_and_record_identity_are_enforced(tmp_path):
    directory, value, _ = fixture(tmp_path)
    with pytest.raises(ValueError, match="expected_manifest_identity"):
        manifest.LinearParent(tmp_path, "parent", "manifest:wrong")
    value["undeclared_change"] = True
    (directory / "manifest.json").write_bytes(json_bytes(value))
    with pytest.raises(ValueError, match="content_addressed_identity"):
        manifest.LinearParent(tmp_path, "parent")


def test_duplicate_manifest_members_are_rejected(tmp_path):
    directory, value, _ = fixture(tmp_path)
    duplicate = record("manifest", members=value["members"] * 2)
    (directory / "manifest.json").write_bytes(json_bytes(duplicate))
    with pytest.raises(ValueError, match="unique_nonself_member"):
        manifest.LinearParent(tmp_path, "parent")


@pytest.mark.parametrize("name", ["missing.json", "../outside.json", "/tmp/undeclared.json"])
def test_undeclared_member_read_is_rejected(tmp_path, name):
    parent, _, _, _ = adapter(tmp_path)
    with pytest.raises(ValueError):
        parent.bytes(name)


@pytest.mark.parametrize("action", ["bytes", "read", "descriptor", "check_manifest", "verify_all"])
def test_changed_manifest_rejected_by_every_public_read(tmp_path, action):
    parent, directory, value, supplied = adapter(tmp_path)
    changed = record("manifest", members=value["members"], additional_field=True)
    (directory / "manifest.json").write_bytes(json_bytes(changed))
    with pytest.raises((ValueError, OSError)):
        if action in {"bytes", "read"}:
            getattr(parent, action)(next(iter(supplied)))
        else:
            getattr(parent, action)()


def test_semantically_equal_manifest_with_different_bytes_is_rejected(tmp_path):
    parent, directory, value, _ = adapter(tmp_path)
    rewritten = json.dumps(value, indent=2).encode()
    assert json.loads(rewritten) == parent.manifest
    (directory / "manifest.json").write_bytes(rewritten)
    with pytest.raises(ValueError):
        parent.verify_all()


def test_same_size_manifest_change_cannot_hide_behind_restored_mtime(tmp_path):
    parent, directory, _, supplied = adapter(tmp_path)
    path = directory / "manifest.json"
    changed = path.read_bytes().replace(b"member_0000", b"member_9000", 1)
    replace_preserving_size_and_mtime(path, changed)
    with pytest.raises(ValueError):
        parent.bytes(next(iter(supplied)))


def test_manifest_rewrite_and_restore_is_detected_despite_restored_mtime(tmp_path):
    parent, directory, _, _ = adapter(tmp_path)
    path = directory / "manifest.json"
    before, raw = path.stat(), path.read_bytes()
    path.write_bytes(raw.replace(b"member_0000", b"member_9000", 1))
    path.write_bytes(raw)
    os.utime(path, ns=(before.st_atime_ns, before.st_mtime_ns))
    assert path.read_bytes() == raw
    assert path.stat().st_mtime_ns == before.st_mtime_ns
    with pytest.raises(ValueError):
        parent.check_manifest()


def test_same_bytes_manifest_inode_replacement_rejected_with_old_fd_alive(tmp_path):
    parent, directory, _, _ = adapter(tmp_path)
    path = directory / "manifest.json"
    old_fd = os.open(path, os.O_RDONLY)
    before, raw = os.fstat(old_fd), path.read_bytes()
    replacement = put(tmp_path / "replacement.json", raw)
    assert replacement == raw
    os.utime(tmp_path / "replacement.json", ns=(before.st_atime_ns, before.st_mtime_ns))
    os.replace(tmp_path / "replacement.json", path)
    try:
        assert os.read(old_fd, len(raw)) == raw
        assert path.stat().st_ino != before.st_ino
        with pytest.raises(ValueError):
            parent.check_manifest()
    finally:
        os.close(old_fd)


@pytest.mark.parametrize("name", ["manifest.json", "nested/member_0000.json"])
def test_file_symlink_at_initialization_or_read_is_rejected(tmp_path, name):
    directory, value, supplied = fixture(tmp_path)
    original = directory / name
    outside = tmp_path / "original"
    original.rename(outside)
    original.symlink_to(outside)
    with pytest.raises((ValueError, OSError)):
        parent = manifest.LinearParent(tmp_path, "parent", value["id"])
        parent.bytes(next(iter(supplied)))


def test_parent_directory_symlink_is_rejected_at_initialization(tmp_path):
    fixture(tmp_path)
    (tmp_path / "alias").symlink_to(tmp_path / "parent", target_is_directory=True)
    with pytest.raises((ValueError, OSError)):
        manifest.LinearParent(tmp_path, "alias")


@pytest.mark.parametrize("action", ["bytes", "verify_all"])
def test_member_ancestor_directory_symlink_is_rejected(tmp_path, action):
    parent, directory, _, supplied = adapter(tmp_path)
    (directory / "nested").rename(tmp_path / "moved-nested")
    (directory / "nested").symlink_to(tmp_path / "moved-nested", target_is_directory=True)
    with pytest.raises((ValueError, OSError)):
        if action == "bytes":
            parent.bytes(next(iter(supplied)))
        else:
            parent.verify_all()


def test_parent_directory_replaced_with_symlink_after_open_is_rejected(tmp_path):
    parent, directory, _, _ = adapter(tmp_path)
    directory.rename(tmp_path / "moved-parent")
    directory.symlink_to(tmp_path / "moved-parent", target_is_directory=True)
    with pytest.raises((ValueError, OSError)):
        parent.verify_all()


def test_ancestor_above_parent_replaced_by_symlink_after_open_is_rejected(tmp_path):
    parent, _, _, _ = adapter(tmp_path, relative="container/parent")
    (tmp_path / "container").rename(tmp_path / "moved-container")
    (tmp_path / "container").symlink_to(tmp_path / "moved-container", target_is_directory=True)
    with pytest.raises((ValueError, OSError)):
        parent.descriptor()


@pytest.mark.parametrize("change", ["same_length", "shorter", "missing"])
def test_changed_member_never_reuses_previously_verified_bytes(tmp_path, change):
    parent, directory, _, supplied = adapter(tmp_path)
    name = next(iter(supplied))
    raw = supplied[name]
    assert parent.bytes(name) == raw
    path = directory / name
    if change == "same_length":
        replace_preserving_size_and_mtime(path, raw.replace(b"synthetic", b"corrupted", 1))
    elif change == "shorter":
        path.write_bytes(raw[:-1])
    else:
        path.unlink()
    with pytest.raises((ValueError, OSError)):
        parent.bytes(name)


@pytest.mark.parametrize("field,bad", [("bytes", 12345), ("sha256", "0" * 64)])
def test_declared_size_and_sha_are_both_enforced(tmp_path, field, bad):
    directory, value, supplied = fixture(tmp_path)
    value["members"][0][field] = bad
    changed = record("manifest", members=value["members"])
    (directory / "manifest.json").write_bytes(json_bytes(changed))
    parent = manifest.LinearParent(tmp_path, "parent")
    with pytest.raises(ValueError):
        parent.bytes(next(iter(supplied)))


@pytest.mark.parametrize("kind", ["file", "empty_directory", "nested_file", "symlink", "fifo"])
def test_verify_all_rejects_unlisted_files_and_directories(tmp_path, kind):
    parent, directory, _, _ = adapter(tmp_path)
    extra = directory / "unlisted"
    if kind == "file":
        extra.write_bytes(b"unlisted")
    elif kind == "empty_directory":
        extra.mkdir()
    elif kind == "nested_file":
        put(extra / "nested.bin", b"unlisted")
    elif kind == "symlink":
        extra.symlink_to(directory / "nested/member_0000.json")
    else:
        os.mkfifo(extra)
    with pytest.raises((ValueError, OSError)):
        parent.verify_all()


def test_verify_all_rejects_missing_member(tmp_path):
    parent, directory, _, supplied = adapter(tmp_path)
    (directory / next(iter(supplied))).unlink()
    with pytest.raises((ValueError, OSError)):
        parent.verify_all()


def test_full_verification_is_read_only_and_does_not_rewrite_identity(tmp_path):
    parent, directory, _, _ = adapter(tmp_path)
    before = {
        str(path.relative_to(directory)): (
            path.read_bytes(),
            path.stat().st_ino,
            path.stat().st_mtime_ns,
            path.stat().st_ctime_ns,
        )
        for path in directory.rglob("*")
        if path.is_file()
    }
    parent.verify_all()
    parent.descriptor()
    after = {
        str(path.relative_to(directory)): (
            path.read_bytes(),
            path.stat().st_ino,
            path.stat().st_mtime_ns,
            path.stat().st_ctime_ns,
        )
        for path in directory.rglob("*")
        if path.is_file()
    }
    assert after == before


def inject_after_fd_read(monkeypatch, target, mutation):
    """Change real tmp files exactly between a target read and post-read checks."""
    original = os.read
    identity = target.stat()
    state = {"triggered": False}

    def read(fd, length):
        current = os.fstat(fd)
        raw = original(fd, length)
        if (
            raw
            and not state["triggered"]
            and (current.st_dev, current.st_ino) == (identity.st_dev, identity.st_ino)
        ):
            state["triggered"] = True
            mutation()
        return raw

    monkeypatch.setattr(manifest.os, "read", read)
    return state


@pytest.mark.parametrize("restore", [False, True])
@pytest.mark.parametrize("nested", [False, True])
def test_member_change_during_read_is_rejected_even_if_original_bytes_restored(
    tmp_path, monkeypatch, restore, nested
):
    members = {
        ("nested/member.json" if nested else "member.json"): json_bytes({"value": "synthetic"})
    }
    parent, directory, _, supplied = adapter(tmp_path, members=members)
    name = next(iter(supplied))
    target, original = directory / name, supplied[name]
    before = target.stat()

    def change():
        target.write_bytes(original.replace(b"synthetic", b"corrupted", 1))
        if restore:
            target.write_bytes(original)
        os.utime(target, ns=(before.st_atime_ns, before.st_mtime_ns))

    state = inject_after_fd_read(monkeypatch, target, change)
    with pytest.raises(ValueError):
        parent.bytes(name)
    assert state["triggered"], "mutation must occur during the real member read"


@pytest.mark.parametrize("replace_inode", [False, True])
def test_manifest_change_during_member_read_is_rejected(tmp_path, monkeypatch, replace_inode):
    parent, directory, _, supplied = adapter(tmp_path)
    name = next(iter(supplied))
    target = directory / "manifest.json"
    original = target.read_bytes()
    before = target.stat()

    def change():
        if replace_inode:
            put(tmp_path / "replacement-manifest.json", original)
            os.replace(tmp_path / "replacement-manifest.json", target)
            assert target.stat().st_ino != before.st_ino
        else:
            target.write_bytes(original.replace(b"member_0000", b"member_9000", 1))
        os.utime(target, ns=(before.st_atime_ns, before.st_mtime_ns))

    state = inject_after_fd_read(monkeypatch, directory / name, change)
    with pytest.raises(ValueError):
        parent.bytes(name)
    assert state["triggered"], "manifest mutation must occur during the member read"


def test_member_path_replacement_during_read_rejects_old_valid_open_fd(tmp_path, monkeypatch):
    parent, directory, _, supplied = adapter(tmp_path)
    name = next(iter(supplied))
    target, original = directory / name, supplied[name]

    def change():
        put(tmp_path / "replacement-member.json", original)
        os.replace(tmp_path / "replacement-member.json", target)

    state = inject_after_fd_read(monkeypatch, target, change)
    with pytest.raises(ValueError):
        parent.bytes(name)
    assert state["triggered"]


def test_external_hardlink_cannot_bypass_member_mutation_detection(tmp_path, monkeypatch):
    parent, directory, _, supplied = adapter(tmp_path)
    name = next(iter(supplied))
    target, raw = directory / name, supplied[name]
    alias = tmp_path / "external-hardlink.json"
    os.link(target, alias)
    before = target.stat()
    assert before.st_nlink == 2

    def mutate_via_external_alias():
        alias.write_bytes(raw.replace(b"synthetic", b"corrupted", 1))
        os.utime(alias, ns=(before.st_atime_ns, before.st_mtime_ns))

    inject_after_fd_read(monkeypatch, target, mutate_via_external_alias)
    # Rejecting a multiply-linked member before reading it is also acceptable.
    with pytest.raises(ValueError):
        parent.bytes(name)


@pytest.mark.parametrize("restore", [False, True])
def test_manifest_change_during_initial_read_is_rejected(tmp_path, monkeypatch, restore):
    directory, _, _ = fixture(tmp_path)
    target = directory / "manifest.json"
    original, before = target.read_bytes(), target.stat()

    def change():
        target.write_bytes(original.replace(b"member_0000", b"member_9000", 1))
        if restore:
            target.write_bytes(original)
        os.utime(target, ns=(before.st_atime_ns, before.st_mtime_ns))

    state = inject_after_fd_read(monkeypatch, target, change)
    with pytest.raises(ValueError):
        manifest.LinearParent(tmp_path, "parent")
    assert state["triggered"]


@pytest.mark.parametrize("change", ["earlier_member", "earlier_member_restore", "extra_file"])
def test_full_seal_rejects_tree_mutation_after_earlier_member_was_verified(
    tmp_path, monkeypatch, change
):
    parent, directory, _, supplied = adapter(tmp_path)
    first, second, *_ = supplied
    target = directory / first
    original, before = supplied[first], target.stat()

    def mutate_previously_read_member():
        if change == "extra_file":
            put(directory / "injected-after-scan.json", b"{}")
        else:
            target.write_bytes(original.replace(b"synthetic", b"corrupted", 1))
            if change == "earlier_member_restore":
                target.write_bytes(original)
            os.utime(target, ns=(before.st_atime_ns, before.st_mtime_ns))

    state = inject_after_fd_read(monkeypatch, directory / second, mutate_previously_read_member)
    with pytest.raises(ValueError):
        parent.verify_all()
    assert state["triggered"], "mutation must occur after the first member was verified"


def test_full_seal_rejects_member_mutation_during_final_manifest_hash(tmp_path, monkeypatch):
    parent, directory, _, supplied = adapter(tmp_path)
    identity = (directory / "manifest.json").stat()
    target = directory / next(iter(supplied))
    original = os.read
    observed = {"manifest_reads": 0, "triggered": False}

    def mutate_during_final_hash(fd, length):
        current = os.fstat(fd)
        raw = original(fd, length)
        if raw and (current.st_dev, current.st_ino) == (identity.st_dev, identity.st_ino):
            observed["manifest_reads"] += 1
            if observed["manifest_reads"] == 2:
                observed["triggered"] = True
                # A changed length detects this attack independently of clock granularity.
                target.write_bytes(b"changed while hashing the closing manifest")
        return raw

    monkeypatch.setattr(manifest.os, "read", mutate_during_final_hash)
    with pytest.raises(ValueError):
        parent.verify_all()
    assert observed["triggered"]


@pytest.mark.parametrize("count", [0, 1, 37])
def test_manifest_full_hash_work_is_constant_and_member_hash_work_is_linear(tmp_path, count):
    parent, directory, _, supplied = adapter(tmp_path, count=count)
    initial = dict(parent.verification_stats)
    assert initial["manifest_full_hashes"] == 1
    assert initial["manifest_bytes_hashed"] == (directory / "manifest.json").stat().st_size
    for name in supplied:
        parent.bytes(name)
    after_reads = dict(parent.verification_stats)
    assert after_reads["manifest_full_hashes"] == initial["manifest_full_hashes"]
    assert after_reads["member_hashes"] - initial["member_hashes"] == count
    assert after_reads["manifest_bytes_hashed"] == initial["manifest_bytes_hashed"]
    assert after_reads["member_bytes_hashed"] - initial["member_bytes_hashed"] == sum(
        map(len, supplied.values())
    )
    parent.verify_all()
    sealed = dict(parent.verification_stats)
    assert sealed["manifest_full_hashes"] - after_reads["manifest_full_hashes"] == 2
    assert sealed["member_hashes"] - after_reads["member_hashes"] == count
    assert sealed["manifest_bytes_hashed"] == 3 * initial["manifest_bytes_hashed"]
    assert sealed["member_bytes_hashed"] - after_reads["member_bytes_hashed"] == sum(
        map(len, supplied.values())
    )


def test_actual_manifest_fd_bytes_are_constant_across_member_reads(tmp_path, monkeypatch):
    directory, value, supplied = fixture(tmp_path, count=41)
    path = directory / "manifest.json"
    identity = path.stat()
    member_stats = [(directory / name).stat() for name in supplied]
    member_identities = {(info.st_dev, info.st_ino) for info in member_stats}
    original = os.read
    observed = {"manifest_bytes": 0, "member_bytes": 0}

    def observe_read(fd, length):
        current = os.fstat(fd)
        raw = original(fd, length)
        key = (current.st_dev, current.st_ino)
        if stat.S_ISREG(current.st_mode):
            if key == (identity.st_dev, identity.st_ino):
                observed["manifest_bytes"] += len(raw)
            elif key in member_identities:
                observed["member_bytes"] += len(raw)
        return raw

    monkeypatch.setattr(manifest.os, "read", observe_read)
    parent = manifest.LinearParent(tmp_path, "parent", value["id"])
    assert observed["manifest_bytes"] == identity.st_size
    for name in supplied:
        parent.bytes(name)
    assert observed["manifest_bytes"] == identity.st_size
    assert observed["member_bytes"] == sum(map(len, supplied.values()))
    parent.verify_all()
    assert observed["manifest_bytes"] == 3 * identity.st_size
    assert observed["member_bytes"] == 2 * sum(map(len, supplied.values()))
    assert parent.verification_stats["manifest_bytes_hashed"] == observed["manifest_bytes"]
    assert parent.verification_stats["member_bytes_hashed"] == observed["member_bytes"]


def test_shared_parent_supports_concurrent_readers_without_skipping_hashes(tmp_path):
    parent, _, _, supplied = adapter(tmp_path, count=11)
    names = list(supplied) * 3
    with ThreadPoolExecutor(max_workers=8) as workers:
        results = list(workers.map(parent.bytes, names))
    assert results == [supplied[name] for name in names]
    assert parent.verification_stats["manifest_full_hashes"] == 1
    assert parent.verification_stats["member_hashes"] == len(names)
    assert parent.verification_stats["member_bytes_hashed"] == sum(
        len(supplied[name]) for name in names
    )


def test_notification_support_is_required_without_stat_only_fallback(monkeypatch):
    monkeypatch.setattr(manifest.sys, "platform", "unsupported-test-platform")
    with pytest.raises(ValueError, match="inotify_required_no_fallback"):
        manifest.MutationMonitor()


def test_notification_initialization_failure_rejects_parent(tmp_path, monkeypatch):
    directory, _, _ = fixture(tmp_path)
    libc = SimpleNamespace(
        inotify_init1=lambda flags: -1,
        inotify_add_watch=lambda *args: -1,
        inotify_rm_watch=lambda *args: 0,
    )
    monkeypatch.setattr(manifest.ctypes, "CDLL", lambda *args, **kwargs: libc)
    with pytest.raises(ValueError, match="initialization_failed_no_fallback"):
        manifest.LinearParent(tmp_path, str(directory.relative_to(tmp_path)))


def test_notification_watch_failure_rejects_parent(tmp_path, monkeypatch):
    fixture(tmp_path)
    monitor = manifest.MutationMonitor()
    monkeypatch.setattr(monitor.libc, "inotify_add_watch", lambda *args: -1)
    monkeypatch.setattr(manifest.LinearParent, "shared_monitor", monitor)
    try:
        with pytest.raises(ValueError, match="watch_failed_no_fallback"):
            manifest.LinearParent(tmp_path, "parent")
    finally:
        monitor.close()


@pytest.mark.parametrize("mask,watch", [(0x4000, -1), (0x8000, 7), (0x2, 7)])
def test_notification_overflow_ignored_watch_and_mutation_permanently_taint(
    monkeypatch, mask, watch
):
    monitor = manifest.MutationMonitor()
    original = os.read
    delivered = False

    def event_read(fd, length):
        nonlocal delivered
        if fd != monitor.fd:
            return original(fd, length)
        if delivered:
            raise BlockingIOError(errno.EAGAIN, "synthetic empty queue")
        delivered = True
        return struct.pack("iIII", watch, mask, 0, 0)

    monkeypatch.setattr(manifest.os, "read", event_read)
    try:
        with pytest.raises(ValueError, match="mutation_or_notification_overflow"):
            monitor.check()
        with pytest.raises(ValueError, match="mutation_already_observed"):
            monitor.check()
    finally:
        monitor.close()


def test_notification_read_error_is_permanent_and_fail_closed(monkeypatch):
    monitor = manifest.MutationMonitor()
    original = os.read

    def failed_read(fd, length):
        if fd == monitor.fd:
            raise OSError(errno.EIO, "synthetic notification I/O failure")
        return original(fd, length)

    monkeypatch.setattr(manifest.os, "read", failed_read)
    try:
        with pytest.raises(ValueError, match="read_failed_no_fallback"):
            monitor.check()
        with pytest.raises(ValueError, match="mutation_already_observed"):
            monitor.check()
    finally:
        monitor.close()


@pytest.mark.parametrize("packet", [b"", b"truncated", struct.pack("iIII", 7, 0x2, 0, 8)])
def test_invalid_notification_payload_cannot_be_consumed_then_forgotten(monkeypatch, packet):
    monitor = manifest.MutationMonitor()
    original = os.read
    delivered = False

    def malformed_read(fd, length):
        nonlocal delivered
        if fd != monitor.fd:
            return original(fd, length)
        if delivered:
            raise BlockingIOError(errno.EAGAIN, "synthetic empty queue")
        delivered = True
        return packet

    monkeypatch.setattr(manifest.os, "read", malformed_read)
    try:
        with pytest.raises(ValueError):
            monitor.check()
        with pytest.raises(ValueError):
            monitor.check()
    finally:
        monitor.close()


def test_repeated_inode_watch_upgrades_ancestor_mask_to_member_content(tmp_path):
    directory = tmp_path / "watched"
    directory.mkdir()
    monitor = manifest.MutationMonitor()
    descriptor = os.open(directory, manifest.DIR_FLAGS)
    try:
        monitor.watch_fd(descriptor, content=False)
        monitor.watch_fd(descriptor, content=True)
        (directory / "new-file.json").write_bytes(b"{}")
        with pytest.raises(ValueError, match="mutation_or_notification_overflow"):
            monitor.check()
    finally:
        os.close(descriptor)
        monitor.close()


def test_shared_monitor_deduplicates_watches_and_survives_one_parent_close(tmp_path, monkeypatch):
    directory, value, supplied = fixture(tmp_path)
    monitor = manifest.MutationMonitor()
    monkeypatch.setattr(manifest.LinearParent, "shared_monitor", monitor)
    first = manifest.LinearParent(tmp_path, "parent", value["id"])
    first.verify_all()
    watch_count = len(monitor.watches)
    second = manifest.LinearParent(tmp_path, "parent", value["id"])
    try:
        second.verify_all()
        assert len(monitor.watches) == watch_count
        first.close()
        name = next(iter(supplied))
        assert second.bytes(name) == supplied[name]
        (directory / name).write_bytes(b"mutation after the first reader closed")
        with pytest.raises(ValueError):
            second.bytes(name)
    finally:
        first.close()
        second.close()
        monitor.close()


def test_closed_monitor_cannot_be_reused():
    monitor = manifest.MutationMonitor()
    monitor.close()
    monitor.close()
    with pytest.raises(ValueError, match="closed_notification_descriptor"):
        monitor.check()


def test_shared_monitor_cannot_lose_an_event_to_a_concurrent_clean_check(monkeypatch):
    monitor = manifest.MutationMonitor()
    original = os.read
    consumed = threading.Event()
    release = threading.Event()
    second_read = threading.Event()
    state_lock = threading.Lock()
    calls = 0

    def consume_event_before_publishing_taint(fd, length):
        nonlocal calls
        if fd != monitor.fd:
            return original(fd, length)
        with state_lock:
            calls += 1
            first_call = calls == 1
        if first_call:
            consumed.set()
            assert release.wait(timeout=3), "the synthetic event reader must be released"
            return struct.pack("iIII", -1, 0x4000, 0, 0)
        second_read.set()
        raise BlockingIOError(errno.EAGAIN, "the first reader consumed the queued event")

    monkeypatch.setattr(manifest.os, "read", consume_event_before_publishing_taint)
    try:
        with ThreadPoolExecutor(max_workers=2) as workers:
            try:
                first = workers.submit(monitor.check)
                assert consumed.wait(timeout=3)
                second = workers.submit(monitor.check)
                # Without serialized check(), the second thread observes an empty queue.
                second_read.wait(timeout=0.05)
                release.set()
                with pytest.raises(ValueError):
                    first.result(timeout=3)
                with pytest.raises(ValueError):
                    second.result(timeout=3)
            finally:
                release.set()
    finally:
        monitor.close()


def kernel_watch_count(monitor):
    with open(f"/proc/self/fdinfo/{monitor.fd}", encoding="utf-8") as stream:
        return sum(line.startswith("inotify wd:") for line in stream)


def test_last_parent_owner_close_reclaims_kernel_watches(tmp_path, monkeypatch):
    fixture(tmp_path)
    monitor = manifest.MutationMonitor()
    monkeypatch.setattr(manifest.LinearParent, "shared_monitor", monitor)
    first = manifest.LinearParent(tmp_path, "parent")
    second = manifest.LinearParent(tmp_path, "parent")
    try:
        first.verify_all()
        second.verify_all()
        watched = kernel_watch_count(monitor)
        assert watched == len(monitor.watches) > 0
        first.close()
        assert kernel_watch_count(monitor) == watched
        second.verify_all()
        second.close()
        assert kernel_watch_count(monitor) == 0
        assert not monitor.watches
        monitor.check()
    finally:
        first.close()
        second.close()
        monitor.close()


def test_sequential_distinct_parents_do_not_accumulate_kernel_watches(tmp_path, monkeypatch):
    for index in range(8):
        fixture(tmp_path, relative=f"parent_{index}")
    monitor = manifest.MutationMonitor()
    monkeypatch.setattr(manifest.LinearParent, "shared_monitor", monitor)
    peaks = []
    try:
        for index in range(8):
            parent = manifest.LinearParent(tmp_path, f"parent_{index}")
            try:
                parent.verify_all()
                for _ in range(5):
                    parent.bytes("nested/member_0000.json")
                peaks.append(kernel_watch_count(monitor))
            finally:
                parent.close()
            assert kernel_watch_count(monitor) == 0
            assert not monitor.watches
            monitor.check()
        assert len(set(peaks)) == 1 and peaks[0] > 0
    finally:
        monitor.close()


def test_parent_garbage_collection_releases_its_watch_owner(tmp_path, monkeypatch):
    fixture(tmp_path)
    monitor = manifest.MutationMonitor()
    monkeypatch.setattr(manifest.LinearParent, "shared_monitor", monitor)
    try:
        parent = manifest.LinearParent(tmp_path, "parent")
        parent.verify_all()
        assert kernel_watch_count(monitor) > 0
        reference = weakref.ref(parent)
        del parent
        gc.collect()
        assert reference() is None
        assert kernel_watch_count(monitor) == 0
        assert not monitor.watches
        monitor.check()
    finally:
        monitor.close()


def test_parent_initialization_failure_releases_partial_watch_owner(tmp_path, monkeypatch):
    fixture(tmp_path)
    monitor = manifest.MutationMonitor()
    monkeypatch.setattr(manifest.LinearParent, "shared_monitor", monitor)
    try:
        with pytest.raises(ValueError, match="expected_manifest_identity"):
            manifest.LinearParent(tmp_path, "parent", "manifest:wrong")
        assert kernel_watch_count(monitor) == 0
        assert not monitor.watches
        monitor.check()
    finally:
        monitor.close()


def test_standalone_watch_survives_release_of_an_explicit_owner(tmp_path):
    path = tmp_path / "shared.json"
    path.write_bytes(b"{}")
    monitor = manifest.MutationMonitor()
    descriptor = os.open(path, manifest.FILE_FLAGS)
    owner = object()
    try:
        monitor.watch_fd(descriptor)
        monitor.watch_fd(descriptor, owner=owner)
        monitor.release_owner(owner)
        assert kernel_watch_count(monitor) == 1
        path.write_bytes(b"modified")
        with pytest.raises(ValueError):
            monitor.check()
    finally:
        os.close(descriptor)
        monitor.close()


@pytest.mark.parametrize("target", ["removed", "still_owned"])
def test_expected_watch_removal_notifications_never_hide_real_mutation(
    tmp_path, monkeypatch, target
):
    paths = {name: tmp_path / f"{name}.json" for name in ("removed", "still_owned")}
    for path in paths.values():
        path.write_bytes(b"{}")
    monitor = manifest.MutationMonitor()
    owners = {name: object() for name in paths}
    descriptors = {name: os.open(path, manifest.FILE_FLAGS) for name, path in paths.items()}
    original_remove = monitor.libc.inotify_rm_watch
    mutated = False

    def mutate_while_removing(fd, watch):
        nonlocal mutated
        if not mutated:
            mutated = True
            paths[target].write_bytes(b"mutation while removing another owner")
        return original_remove(fd, watch)

    try:
        for name, descriptor in descriptors.items():
            monitor.watch_fd(descriptor, owner=owners[name])
        monkeypatch.setattr(monitor.libc, "inotify_rm_watch", mutate_while_removing)
        try:
            monitor.release_owner(owners["removed"])
        except ValueError:
            pass
        assert mutated
        with pytest.raises(ValueError):
            monitor.check()
    finally:
        for descriptor in descriptors.values():
            os.close(descriptor)
        monitor.close()


def test_expected_ignored_watch_does_not_accept_a_mixed_mutation_mask(tmp_path, monkeypatch):
    path = tmp_path / "member.json"
    path.write_bytes(b"{}")
    monitor = manifest.MutationMonitor()
    descriptor = os.open(path, manifest.FILE_FLAGS)
    owner = object()
    original_remove, original_read = monitor.libc.inotify_rm_watch, os.read
    removed_watch = None
    injected = False

    def remove_watch(fd, watch):
        nonlocal removed_watch
        result = original_remove(fd, watch)
        assert result == 0
        removed_watch = watch
        return result

    def mixed_event(fd, length):
        nonlocal injected
        if fd == monitor.fd and removed_watch is not None and not injected:
            injected = True
            return struct.pack("iIII", removed_watch, 0x8000 | 0x2, 0, 0)
        return original_read(fd, length)

    try:
        monitor.watch_fd(descriptor, owner=owner)
        monkeypatch.setattr(monitor.libc, "inotify_rm_watch", remove_watch)
        monkeypatch.setattr(manifest.os, "read", mixed_event)
        try:
            monitor.release_owner(owner)
        except ValueError:
            pass
        assert injected
        with pytest.raises(ValueError):
            monitor.check()
    finally:
        os.close(descriptor)
        monitor.close()


def test_large_owner_cleanup_drains_removal_events_in_bounded_batches(tmp_path, monkeypatch):
    fixture(tmp_path, count=270)
    monitor = manifest.MutationMonitor()
    monkeypatch.setattr(manifest.LinearParent, "shared_monitor", monitor)
    parent = manifest.LinearParent(tmp_path, "parent")
    original_remove, original_read = monitor.libc.inotify_rm_watch, os.read
    pending, maximum = 0, 0

    def count_pending_removals(fd, watch):
        nonlocal pending, maximum
        result = original_remove(fd, watch)
        if result == 0:
            pending += 1
            maximum = max(maximum, pending)
        return result

    def observe_drain(fd, length):
        nonlocal pending
        data = original_read(fd, length)
        if fd == monitor.fd and data:
            pending = 0
        return data

    try:
        parent.verify_all()
        assert kernel_watch_count(monitor) > 256
        monkeypatch.setattr(monitor.libc, "inotify_rm_watch", count_pending_removals)
        monkeypatch.setattr(manifest.os, "read", observe_drain)
        parent.close()
        assert 0 < maximum <= 128
        assert pending == 0
        assert kernel_watch_count(monitor) == 0
        monitor.check()
    finally:
        parent.close()
        monitor.close()
