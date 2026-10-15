"""Real XFS/flock CPU tests: only newly created test locks and owned helpers."""

import fcntl
import importlib
import os
import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
b = importlib.import_module("finqa_v46_queued_barrier")


@pytest.fixture
def locks(tmp_path):
    root = tmp_path / "training"
    (root / "locks").mkdir(parents=True)
    uuids = {str(gpu): f"CPU-ONLY-GPU-{gpu}" for gpu in b.GPUS}
    paths = {gpu: b.lock_path(root, uuids[str(gpu)]) for gpu in b.GPUS}
    for path in paths.values():
        path.write_bytes(b"original mock lease inode; not a production lock\n")
    original = {gpu: (path.stat().st_ino, path.read_bytes()) for gpu, path in paths.items()}
    return root, uuids, paths, original


def wait_until(predicate, timeout=5):
    deadline = time.monotonic() + timeout
    while not predicate():
        assert time.monotonic() < deadline, "CPU-only lock condition timed out"
        time.sleep(0.005)


def own(path):
    fd = os.open(path, os.O_RDWR)
    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    return fd


def assert_unavailable(path):
    fd = os.open(path, os.O_RDWR)
    try:
        with pytest.raises(BlockingIOError):
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    finally:
        os.close(fd)


def assert_released(paths):
    for path in paths.values():
        os.close(own(path))


def test_queued_anchor_beats_observed_point35_second_reacquisition(locks):
    root, uuids, paths, original = locks
    prior = {gpu: own(path) for gpu, path in paths.items()}
    barrier = b.QueuedBarrier(root, uuids)
    try:
        barrier.start_waiters()
        wait_until(barrier.waiters_ready)
        before = barrier.snapshot()
        assert not barrier.held
        assert all(
            row["waiting_pipe_receipt"] and row["kernel_queued"] for row in before["helpers"]
        )
        assert not any(row["acquired_pipe_receipt"] for row in before["helpers"])
        os.close(prior.pop(3))  # The mocked scientific owner exits naturally.
        time.sleep(0.35)  # The observed old-controller reacquisition interval.
        assert_unavailable(paths[3])
        wait_until(lambda: bool(barrier.acquire_available()) or 3 in barrier.held)
        assert set(barrier.held) == {3}
        anchor = next(row for row in barrier.snapshot()["helpers"] if row["gpu"] == 3)
        assert anchor["actual_helper_exit"] == 0 and anchor["acquired_pipe_receipt"]
        assert not barrier.complete
    finally:
        barrier.close()
        for fd in prior.values():
            os.close(fd)
    assert_released(paths)
    assert {gpu: (p.stat().st_ino, p.read_bytes()) for gpu, p in paths.items()} == original


def test_helper_exit_leaves_parent_same_ofd_holding_all_locks(locks):
    root, uuids, paths, _ = locks
    barrier = b.QueuedBarrier(root, uuids)
    try:
        barrier.start_waiters()
        wait_until(lambda: (barrier.acquire_available(), barrier.complete)[1])
        assert all(row["actual_helper_exit"] == 0 for row in barrier.snapshot()["helpers"])
        assert all(row["process"].returncode == 0 for row in barrier.waiters.values())
        for path in paths.values():
            assert_unavailable(path)
    finally:
        barrier.close()
        barrier.close()
    assert_released(paths)


def test_cancel_blocked_helpers_reaps_before_closing_parent_fds(locks):
    root, uuids, paths, _ = locks
    prior = {gpu: own(path) for gpu, path in paths.items()}
    barrier = b.QueuedBarrier(root, uuids)
    try:
        barrier.start_waiters()
        wait_until(barrier.waiters_ready)
        started = time.monotonic()
        barrier.close()
        assert time.monotonic() - started < 3
        assert not barrier.held and barrier.closed
        for row in barrier.waiters.values():
            assert row["process"].returncode is not None
            assert row["fd"] is None and row["pidfd"] is None
        for path in paths.values():
            assert_unavailable(path)  # Cancellation did not unlock the old owner.
    finally:
        barrier.close()
        for fd in prior.values():
            os.close(fd)
    assert_released(paths)


def test_helpers_inherit_only_their_one_project_lease_fd(locks):
    root, uuids, paths, _ = locks
    prior = {gpu: own(path) for gpu, path in paths.items()}
    barrier = b.QueuedBarrier(root, uuids)
    try:
        barrier.start_waiters()
        wait_until(barrier.waiters_ready)
        all_paths = {str(path) for path in paths.values()}
        for gpu, row in barrier.waiters.items():
            inherited = {
                os.readlink(path)
                for path in Path(f"/proc/{row['process'].pid}/fd").iterdir()
            }
            assert inherited & all_paths == {str(paths[gpu])}
    finally:
        barrier.close()
        for fd in prior.values():
            os.close(fd)
    assert_released(paths)


def test_missing_inode_does_not_create_a_new_lock_and_cancels_prior_helpers(locks):
    root, uuids, paths, _ = locks
    absent = paths[7]
    absent.unlink()  # Only this test's freshly created mock inode.
    barrier = b.QueuedBarrier(root, uuids)
    with pytest.raises(FileNotFoundError):
        barrier.start_waiters()
    assert not absent.exists() and barrier.closed
    assert all(row["process"].returncode is not None for row in barrier.waiters.values())
    assert_released({gpu: path for gpu, path in paths.items() if gpu != 7})


def test_cancellation_during_acquisition_does_not_leave_a_late_lock(locks):
    root, uuids, paths, _ = locks
    prior = {gpu: own(path) for gpu, path in paths.items()}
    barrier = b.QueuedBarrier(root, uuids)
    barrier.start_waiters()
    try:
        wait_until(barrier.waiters_ready)
        for fd in prior.values():
            os.close(fd)
        prior.clear()
        # Stop before harvesting READY/exit: pending and newly acquired share cleanup.
        barrier.close()
        assert all(row["process"].returncode is not None for row in barrier.waiters.values())
    finally:
        barrier.close()
        for fd in prior.values():
            os.close(fd)
    assert_released(paths)
