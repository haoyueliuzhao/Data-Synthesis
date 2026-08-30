from __future__ import annotations

import ctypes
import errno
import os
import shutil
import tempfile
from collections.abc import Mapping
from pathlib import Path

_AT_FDCWD = -100
_RENAME_NOREPLACE = 1


def write_immutable_artifact_directory(
    output_dir: str | Path,
    payloads: Mapping[str, bytes],
) -> tuple[str, ...]:
    """Durably publish one complete artifact set without replacing an existing path."""

    if not payloads:
        raise ValueError("immutable artifact publication requires payloads")
    names = tuple(sorted(payloads))
    if any(Path(name).name != name or not name for name in names):
        raise ValueError("immutable artifact filenames must be non-empty local names")
    output = Path(output_dir).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    lock = output.with_name(f".{output.name}.write-lock")
    lock.mkdir(exist_ok=False)
    staging: Path | None = None
    try:
        if output.exists():
            raise FileExistsError(f"immutable artifact directory already exists: {output}")
        staging = Path(
            tempfile.mkdtemp(
                prefix=f".{output.name}.staging-",
                dir=output.parent,
            )
        )
        for name in names:
            path = staging / name
            with path.open("xb") as handle:
                handle.write(payloads[name])
                handle.flush()
                os.fsync(handle.fileno())
        _fsync_directory(staging)
        _rename_directory_noreplace(staging, output)
        staging = None
        _fsync_directory(output.parent)
        return names
    finally:
        if staging is not None and staging.exists():
            shutil.rmtree(staging)
        lock.rmdir()
        _fsync_directory(output.parent)


def _rename_directory_noreplace(source: Path, destination: Path) -> None:
    libc = ctypes.CDLL(None, use_errno=True)
    renameat2 = getattr(libc, "renameat2", None)
    if renameat2 is None:
        raise RuntimeError("kernel/libc renameat2 support is required for no-replace publication")
    renameat2.argtypes = (
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_uint,
    )
    renameat2.restype = ctypes.c_int
    result = renameat2(
        _AT_FDCWD,
        os.fsencode(source),
        _AT_FDCWD,
        os.fsencode(destination),
        _RENAME_NOREPLACE,
    )
    if result == 0:
        return
    error_number = ctypes.get_errno()
    if error_number == errno.EEXIST:
        raise FileExistsError(f"immutable artifact directory already exists: {destination}")
    raise OSError(error_number, os.strerror(error_number), destination)


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
