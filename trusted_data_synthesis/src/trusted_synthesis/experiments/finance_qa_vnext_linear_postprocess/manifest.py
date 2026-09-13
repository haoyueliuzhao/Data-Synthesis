"""Linear, descriptor-pinned reads of an existing immutable manifest.

No scientific records are rewritten. Ordinary public methods retain Parent's
return shapes. Full verification adds a stricter exact-file/directory set and
detects namespace, stat and late-member changes without rehashing the whole
manifest for every file. No member's content hash is cached or skipped.
"""

import ctypes
import hashlib
import json
import os
import stat
import struct
import sys
import threading
import weakref
from pathlib import Path, PurePosixPath

from ..finance_qa_vnext_catalog_bridge.catalog import Parent as OriginalParent
from ..finance_qa_vnext_task_build.archive import validate_record
from .protocol import policy, record, require

BLOCK = 1024 * 1024
DIR_FLAGS = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
FILE_FLAGS = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC
SELF_EVENTS = 0x400 | 0x800 | 0x2000
MUTATION_EVENTS = SELF_EVENTS | 0x2 | 0x4 | 0x8 | 0x40 | 0x80 | 0x100 | 0x200
IN_MASK_ADD = 0x20000000


class MutationMonitor:
    """Read-only Linux change notifications; no stat-clock precision assumption.

    Watches actual file inodes as well as directories: an outside hardlink must
    not bypass observation. mmap/storage-level writes are not comprehensively
    notified by inotify; inputs must already be sealed with no writing process.
    """

    def __init__(self):
        self._lock = threading.RLock()
        require(sys.platform == "linux", "linear.Linux_inotify_required_no_fallback")
        self.libc = ctypes.CDLL(None, use_errno=True)
        self.libc.inotify_init1.argtypes = [ctypes.c_int]
        self.libc.inotify_init1.restype = ctypes.c_int
        self.libc.inotify_add_watch.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_uint32]
        self.libc.inotify_add_watch.restype = ctypes.c_int
        self.libc.inotify_rm_watch.argtypes = [ctypes.c_int, ctypes.c_int]
        self.libc.inotify_rm_watch.restype = ctypes.c_int
        self.fd = self.libc.inotify_init1(os.O_NONBLOCK | os.O_CLOEXEC)
        require(
            self.fd >= 0,
            "linear.inotify_initialization_failed_no_fallback:" + str(ctypes.get_errno()),
        )
        self.watches, self.tainted = {}, None
        self._owner_keys, self._watch_owners, self._expected_ignored = {}, {}, set()

    def close(self):
        with self._lock:
            if self.fd >= 0:
                os.close(self.fd)
                self.fd = -1
            self.watches.clear()
            self._owner_keys.clear()
            self._watch_owners.clear()
            self._expected_ignored.clear()

    def check(self):
        with self._lock:
            self._check_locked()

    def _check_locked(self):
        require(self.tainted is None, "linear.mutation_already_observed:" + str(self.tainted))
        require(self.fd >= 0, "linear.closed_notification_descriptor")
        self._drain_locked()

    def _drain_locked(self):
        """Drain cleanup events even after taint, without clearing an existing failure."""
        while True:
            try:
                data = os.read(self.fd, 65536)
            except BlockingIOError:
                return
            except OSError as error:
                self.tainted = self.tainted or "notification_read_error"
                raise ValueError("linear.notification_read_failed_no_fallback") from error
            offset, events = 0, []
            try:
                require(data, "linear.unexpected_notification_EOF")
                while offset < len(data):
                    require(len(data) - offset >= 16, "linear.truncated_notification_event")
                    watch, mask, cookie, length = struct.unpack_from("iIII", data, offset)
                    require(offset + 16 + length <= len(data), "linear.truncated_notification_name")
                    if mask == 0x8000 and cookie == length == 0 and watch in self._expected_ignored:
                        self._expected_ignored.remove(watch)
                    else:
                        events.append({"watch": watch, "mask": mask})
                    offset += 16 + length
            except ValueError:
                self.tainted = self.tainted or "notification_payload_or_EOF_observed"
                raise
            if events:
                # Overflow, unexpected IN_IGNORED, and mixed masks remain fatal.
                self.tainted = self.tainted or events[:8]
                raise ValueError("linear.mutation_or_notification_overflow_observed")

    def watch_fd(self, descriptor, *, content=True, owner=None):
        with self._lock:
            return self._watch_locked(descriptor, content=content, owner=owner)

    def _watch_locked(self, descriptor, *, content, owner):
        self.check()
        info = os.fstat(descriptor)
        key = (info.st_dev, info.st_ino)
        mask = MUTATION_EVENTS if content else SELF_EVENTS
        previous = self.watches.get(key)
        if previous is not None and previous[1] & mask == mask:
            self._owner_keys.setdefault(owner, set()).add(key)
            self._watch_owners.setdefault(key, set()).add(owner)
            return
        # Follow this procfs link to the already pinned inode, not a replaceable
        # pathname; IN_DONT_FOLLOW would instead watch the procfs link itself.
        name = ("/proc/self/fd/" + str(descriptor)).encode()
        watch = self.libc.inotify_add_watch(self.fd, name, mask | IN_MASK_ADD)
        require(watch >= 0, "linear.inotify_watch_failed_no_fallback:" + str(ctypes.get_errno()))
        self.watches[key] = (watch, mask | (previous[1] if previous else 0))
        self._owner_keys.setdefault(owner, set()).add(key)
        self._watch_owners.setdefault(key, set()).add(owner)
        self.check()

    def release_owner(self, owner):
        """Release one reader's references; owner=None lives until monitor.close()."""
        require(owner is not None, "linear.standalone_owner_lives_until_monitor_close")
        with self._lock:
            keys = self._owner_keys.pop(owner, set())
            if not keys:
                return
            failure = None

            def drain():
                nonlocal failure
                try:
                    self._drain_locked()
                except ValueError as error:
                    failure = failure or error

            if self.fd >= 0:
                drain()
            removed = 0
            for key in keys:
                owners = self._watch_owners[key]
                owners.discard(owner)
                if owners:
                    continue
                if self.fd >= 0:
                    watch = self.watches[key][0]
                    if self.libc.inotify_rm_watch(self.fd, watch) != 0:
                        self.tainted = self.tainted or "notification_remove_failed"
                        failure = failure or ValueError(
                            "linear.inotify_remove_failed_no_fallback:" + str(ctypes.get_errno())
                        )
                        continue
                    self._expected_ignored.add(watch)
                del self.watches[key]
                del self._watch_owners[key]
                removed += 1
                if self.fd >= 0 and removed % 128 == 0:
                    drain()
            if self.fd >= 0:
                drain()
            if self._expected_ignored:
                self.tainted = self.tainted or "notification_remove_acknowledgement_missing"
                failure = failure or ValueError("linear.expected_ignored_not_received")
            if failure is not None:
                raise failure


def _stamp(info):
    return (
        info.st_dev,
        info.st_ino,
        info.st_mode,
        info.st_size,
        info.st_mtime_ns,
        info.st_ctime_ns,
        info.st_nlink,
    )


def _directory_identity(info):
    return info.st_dev, info.st_ino, stat.S_IFMT(info.st_mode)


def _close_descriptors(descriptors):
    for descriptor in reversed(descriptors):
        try:
            os.close(descriptor)
        except OSError:
            pass


def _close_parent_resources(descriptors, monitor, owner, owns_monitor):
    try:
        if monitor is not None:
            monitor.release_owner(owner)
    except (ValueError, OSError):
        # The monitor retains the fatal condition. Closing must not replace an
        # earlier validation exception or leak the remaining file descriptors.
        pass
    finally:
        _close_descriptors(descriptors)
        if owns_monitor and monitor is not None:
            monitor.close()


def _parts(relative):
    require(
        isinstance(relative, str) and relative and "\\" not in relative,
        "linear.exact_POSIX_relative_path",
    )
    value = PurePosixPath(relative)
    require(
        not value.is_absolute()
        and ".." not in value.parts
        and value.parts
        and value.as_posix() == relative
        and "." not in value.parts,
        "linear.canonical_relative_path",
    )
    return value.parts


class LinearParent(OriginalParent):
    """Original Parent interface with explicitly different verification mechanics."""

    audit_sink = None
    shared_monitor = None

    def __init__(self, root, relative, expected_manifest_id=None):
        self._lock = threading.RLock()
        self._closed = False
        self._owner_token = object()
        self._monitor, self._owns_monitor = None, False
        self._fds, self._namespace = [], []
        self._member_stamps, self._directory_stamps = {}, {}
        self.verification_stats = {
            "manifest_full_hashes": 0,
            "manifest_bytes_hashed": 0,
            "member_hashes": 0,
            "member_bytes_hashed": 0,
            "metadata_checks": 0,
        }
        self.last_verification = None
        self.root = Path(os.path.abspath(root))
        self.relative = str(relative)
        parts = _parts(self.relative)
        self.directory = self.root.joinpath(*parts)
        try:
            current = os.open("/", DIR_FLAGS)
            self._fds.append(current)
            self._namespace.append((None, "/", current, _directory_identity(os.fstat(current))))
            for name in (*self.root.parts[1:], *parts):
                child = os.open(name, DIR_FLAGS, dir_fd=current)
                self._fds.append(child)
                info = os.fstat(child)
                require(stat.S_ISDIR(info.st_mode), "linear.directory_required")
                self._namespace.append((current, name, child, _directory_identity(info)))
                current = child
            self._dirfd = current
            self._root_stamp = _stamp(os.fstat(current))
            self._monitor = self.shared_monitor or MutationMonitor()
            self._owns_monitor = self.shared_monitor is None
            for _, _, descriptor, _ in self._namespace[:-1]:
                self._monitor.watch_fd(descriptor, content=False, owner=self._owner_token)
            self._monitor.watch_fd(self._dirfd, owner=self._owner_token)
            self._manifest_fd = os.open("manifest.json", FILE_FLAGS, dir_fd=current)
            self._fds.append(self._manifest_fd)
            info = os.fstat(self._manifest_fd)
            require(stat.S_ISREG(info.st_mode), "linear.regular_manifest_required")
            self._monitor.watch_fd(self._manifest_fd, owner=self._owner_token)
            info = os.fstat(self._manifest_fd)
            self._manifest_stamp = _stamp(info)
            self._check_manifest_metadata()
            raw, digest = self._hash_manifest(keep_bytes=True)
            self.manifest_sha256 = digest
            self.manifest = json.loads(raw)
            validate_record(self.manifest, "manifest")
            require(
                expected_manifest_id is None or self.manifest["id"] == expected_manifest_id,
                "linear.expected_manifest_identity",
            )
            members = self.manifest["members"]
            require(isinstance(members, list), "linear.manifest_member_list")
            self.members = {}
            self._expected_directories = set()
            for member in members:
                require(
                    isinstance(member, dict)
                    and {"path", "bytes", "sha256"} <= set(member)
                    and type(member["bytes"]) is int
                    and member["bytes"] >= 0
                    and isinstance(member["sha256"], str)
                    and len(member["sha256"]) == 64
                    and all(char in "0123456789abcdef" for char in member["sha256"]),
                    "linear.member_descriptor",
                )
                names = _parts(member["path"])
                require(
                    member["path"] != "manifest.json" and member["path"] not in self.members,
                    "linear.unique_nonself_member",
                )
                self.members[member["path"]] = member
                self._expected_directories.update(
                    "/".join(names[:index]) for index in range(1, len(names))
                )
            require(
                not set(self.members) & self._expected_directories,
                "linear.no_file_directory_collision",
            )
            self.check_manifest()
            self._finalizer = weakref.finalize(
                self,
                _close_parent_resources,
                list(self._fds),
                self._monitor,
                self._owner_token,
                self._owns_monitor,
            )
        except BaseException:
            _close_parent_resources(self._fds, self._monitor, self._owner_token, self._owns_monitor)
            raise

    def close(self):
        with self._lock:
            self._closed = True
            self._finalizer()

    def _check_namespace(self):
        for parent, name, descriptor, expected in self._namespace:
            current = (
                os.stat(name, dir_fd=parent, follow_symlinks=False)
                if parent is not None
                else os.stat("/", follow_symlinks=False)
            )
            require(
                _directory_identity(current) == expected
                and _directory_identity(os.fstat(descriptor)) == expected,
                "linear.original_directory_namespace",
            )
        require(
            _stamp(os.fstat(self._dirfd)) == self._root_stamp, "linear.sealed_root_metadata_changed"
        )

    def _check_manifest_metadata(self):
        require(not self._closed, "linear.parent_closed")
        self._monitor.check()
        self._check_namespace()
        current = os.stat("manifest.json", dir_fd=self._dirfd, follow_symlinks=False)
        require(
            _stamp(current) == self._manifest_stamp
            and _stamp(os.fstat(self._manifest_fd)) == self._manifest_stamp,
            "linear.manifest_fd_and_namespace_changed",
        )
        self.verification_stats["metadata_checks"] += 1
        self._monitor.check()

    def check_manifest(self):
        with self._lock:
            self._check_manifest_metadata()

    def _hash_manifest(self, *, keep_bytes=False):
        self._check_manifest_metadata()
        os.lseek(self._manifest_fd, 0, os.SEEK_SET)
        digest, chunks, count = hashlib.sha256(), [], 0
        while data := os.read(self._manifest_fd, BLOCK):
            digest.update(data)
            count += len(data)
            if keep_bytes:
                chunks.append(data)
        self._check_manifest_metadata()
        require(count == self._manifest_stamp[3], "linear.manifest_exact_size")
        self.verification_stats["manifest_full_hashes"] += 1
        self.verification_stats["manifest_bytes_hashed"] += count
        value = digest.hexdigest()
        if hasattr(self, "manifest_sha256"):
            require(value == self.manifest_sha256, "linear.manifest_full_hash_changed")
        return b"".join(chunks) if keep_bytes else None, value

    def _member_parent(self, names):
        descriptor = os.dup(self._dirfd)
        try:
            for index, name in enumerate(names[:-1], 1):
                child = os.open(name, DIR_FLAGS, dir_fd=descriptor)
                os.close(descriptor)
                descriptor = child
                info = os.fstat(child)
                self._monitor.watch_fd(child, owner=self._owner_token)
                key = "/".join(names[:index])
                expected = self._directory_stamps.setdefault(key, _stamp(info))
                require(
                    _stamp(info) == expected and stat.S_ISDIR(info.st_mode),
                    "linear.unchanged_member_directory",
                )
            return descriptor
        except BaseException:
            os.close(descriptor)
            raise

    def bytes(self, relative):
        with self._lock:
            names = _parts(relative)
            self.check_manifest()
            require(relative in self.members, "linear.member_declared")
            parent = self._member_parent(names)
            descriptor = None
            try:
                descriptor = os.open(names[-1], FILE_FLAGS, dir_fd=parent)
                before = os.fstat(descriptor)
                require(stat.S_ISREG(before.st_mode), "linear.regular_member_required")
                self._monitor.watch_fd(descriptor, owner=self._owner_token)
                before = os.fstat(descriptor)
                expected = self._member_stamps.setdefault(relative, _stamp(before))
                require(_stamp(before) == expected, "linear.member_metadata_changed")
                digest, chunks, count = hashlib.sha256(), [], 0
                while data := os.read(descriptor, BLOCK):
                    digest.update(data)
                    chunks.append(data)
                    count += len(data)
                require(
                    _stamp(os.fstat(descriptor)) == expected
                    and _stamp(os.stat(names[-1], dir_fd=parent, follow_symlinks=False))
                    == expected,
                    "linear.member_changed_during_read",
                )
                actual = self.members[relative]
                require(
                    count == actual["bytes"] and digest.hexdigest() == actual["sha256"],
                    "linear.original_member_bytes_and_SHA",
                )
                self.verification_stats["member_hashes"] += 1
                self.verification_stats["member_bytes_hashed"] += count
            finally:
                if descriptor is not None:
                    os.close(descriptor)
                os.close(parent)
            # Resolve again from the pinned root to reject replacement of an
            # intermediate directory while its old fd was being read.
            parent = self._member_parent(names)
            try:
                require(
                    _stamp(os.stat(names[-1], dir_fd=parent, follow_symlinks=False)) == expected,
                    "linear.member_current_namespace",
                )
            finally:
                os.close(parent)
            self.check_manifest()
            return b"".join(chunks)

    def read(self, relative):
        return json.loads(self.bytes(relative))

    def _tree(self):
        files, directories = {}, {}

        def walk(descriptor, prefix):
            with os.scandir(descriptor) as scan:
                names = sorted(entry.name for entry in scan)
            for name in names:
                path = prefix + name
                info = os.stat(name, dir_fd=descriptor, follow_symlinks=False)
                if stat.S_ISREG(info.st_mode):
                    if path != "manifest.json":
                        files[path] = _stamp(info)
                elif stat.S_ISDIR(info.st_mode):
                    require(path in self._expected_directories, "linear.undeclared_directory")
                    directories[path] = _stamp(info)
                    child = os.open(name, DIR_FLAGS, dir_fd=descriptor)
                    try:
                        self._monitor.watch_fd(child, owner=self._owner_token)
                        require(
                            _stamp(os.fstat(child)) == _stamp(info),
                            "linear.directory_changed_during_scan",
                        )
                        walk(child, path + "/")
                    finally:
                        os.close(child)
                else:
                    raise ValueError("linear.symlink_or_special_member")

        self.check_manifest()
        walk(self._dirfd, "")
        self.check_manifest()
        require(
            set(files) == set(self.members) and set(directories) == self._expected_directories,
            "linear.exact_declared_member_and_directory_set",
        )
        return files, directories

    def verify_all(self):
        with self._lock:
            self._hash_manifest()
            initial_files, initial_directories = self._tree()
            for name, stamp in initial_files.items():
                require(
                    self._member_stamps.setdefault(name, stamp) == stamp,
                    "linear.previously_read_member_changed",
                )
            for name, stamp in initial_directories.items():
                require(
                    self._directory_stamps.setdefault(name, stamp) == stamp,
                    "linear.previously_read_directory_changed",
                )
            before = dict(self.verification_stats)
            for name in self.members:
                self.bytes(name)
            # Cover mutations during the final full manifest read as well.
            self._hash_manifest()
            final_files, final_directories = self._tree()
            require(
                initial_files == final_files and initial_directories == final_directories,
                "linear.late_member_or_directory_mutation",
            )
            self.check_manifest()
            self.last_verification = record(
                "linear_parent_verification",
                adapter_policy_id=policy()["id"],
                parent=self.descriptor(),
                member_count=len(self.members),
                member_bytes=sum(row["bytes"] for row in self.members.values()),
                member_hashes_this_sweep=self.verification_stats["member_hashes"]
                - before["member_hashes"],
                exact_file_and_directory_set=True,
                before_and_after_manifest_SHA_equal=True,
                no_member_content_hash_skipped=True,
                final_all_member_metadata_sweep=True,
                mutation_notifications_checked=True,
                watched_inodes=len(self._monitor.watches),
                counters=dict(self.verification_stats),
                actual_scientific_or_budget_changes=0,
            )
            if self.audit_sink is not None:
                self.audit_sink(self.last_verification)
            return self.manifest["id"]

    def descriptor(self):
        self.check_manifest()
        return {
            "directory": self.relative,
            "manifest_id": self.manifest["id"],
            "manifest_sha256": self.manifest_sha256,
        }
