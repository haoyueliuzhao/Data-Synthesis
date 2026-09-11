"""Linux Landlock filesystem confinement; public bundle plus one document and output only."""

import ctypes
import os
import sys
from pathlib import Path


def restrict(public_path, output_path, bundle_path, forbidden_paths, extra_read_files=()):
    if os.uname().machine != "x86_64":
        raise RuntimeError("isolation.unsupported_syscall_architecture")
    libc = ctypes.CDLL(None, use_errno=True)
    abi = libc.syscall(444, 0, 0, 1)
    if abi < 3:
        raise RuntimeError("isolation.landlock_v3_required")

    class Ruleset(ctypes.Structure):
        _fields_ = [("handled_access_fs", ctypes.c_uint64)]

    class PathRule(ctypes.Structure):
        _pack_ = 1
        _fields_ = [("allowed_access", ctypes.c_uint64), ("parent_fd", ctypes.c_int32)]

    # All filesystem rights available in ABI3; ABI4 adds networking, intentionally
    # not restricted here. No source reads, executable code or tools are user-controlled.
    handled = (1 << 15) - 1
    spec = Ruleset(handled)
    descriptor = libc.syscall(444, ctypes.byref(spec), ctypes.sizeof(spec), 0)
    if descriptor < 0:
        raise OSError(ctypes.get_errno(), "isolation.create_ruleset")
    read_file, read_dir = 1 << 2, 1 << 3
    allow = []

    def add(path, rights):
        path = Path(path).resolve()
        if not path.exists():
            return
        actual = rights if path.is_dir() else rights & (1 | 2 | 4 | (1 << 14))
        fd = os.open(path, os.O_PATH | os.O_CLOEXEC)
        rule = PathRule(actual, fd)
        try:
            if libc.syscall(445, descriptor, 1, ctypes.byref(rule), 0) != 0:
                raise OSError(ctypes.get_errno(), "isolation.add_rule")
        finally:
            os.close(fd)
        allow.append({"path": str(path), "rights": actual})

    try:
        for path in {"/usr", "/lib", "/lib64", sys.base_prefix}:
            add(path, read_file | read_dir | 1)
        for path in (
            "/etc/ssl/certs",
            "/etc/resolv.conf",
            "/etc/hosts",
            "/etc/nsswitch.conf",
            "/etc/gai.conf",
        ):
            add(path, read_file | read_dir)
        add(bundle_path, read_file | read_dir)
        add(public_path, read_file)
        for path in extra_read_files:
            add(path, read_file)
        # Write only fresh regular files/subdirectories in this session, no exec,
        # symlinks, device nodes, rename or deletion capability granted.
        add(output_path, read_file | read_dir | (1 << 1) | (1 << 7) | (1 << 8) | (1 << 14))
        if libc.prctl(38, 1, 0, 0, 0) != 0 or libc.syscall(446, descriptor, 0) != 0:
            raise OSError(ctypes.get_errno(), "isolation.restrict_self")
    finally:
        os.close(descriptor)
    checks = []
    for path in forbidden_paths:
        try:
            fd = os.open(path, os.O_RDONLY)
        except PermissionError:
            checks.append({"path": str(path), "read_denied": True})
        else:
            os.close(fd)
            raise RuntimeError("isolation.private_read_not_denied")
    return {
        "landlock_abi": abi,
        "no_new_privileges": True,
        "allowed_paths": allow,
        "private_read_probes": checks,
        "private_read_denied_before_provider": True,
        "network_policy": "fixed HTTPS client endpoint, not a Landlock network restriction",
        "scope": "filesystem content confinement plus non-evaluating AST tool; "
        "not a general production sandbox proof",
    }
