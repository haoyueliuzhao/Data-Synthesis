"""CPU-only V51 clean handoff and unchanged resource-recovery safety."""

import copy
import importlib
import json
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
subject = importlib.import_module("finqa_v51_inheritance")
GIB = 1024**3


def authority():
    return dict(
        user_consent="提高并发上限至2；允许新增第二张GPU，每卡最多1个worker",
        time_limits_removed=True,
        automatic_recovery_authorized=True,
        unknown_feedback_retry_allowed=False,
        total_worker_limit_removed=False,
        independent_total_worker_limit=2,
        max_gpu_workers=2,
        max_workers_per_gpu=1,
        effective_device_capacity=2,
        allowed_gpu_indices=[0, 6],
        steady_gpu_indices=[0, 6],
        steady_max_gpu_workers=2,
        dual_gpu_two_worker_authorized=True,
        host_ram_runtime_hard_gates_unchanged=True,
        fixed_gpu_reservation_authorized=True,
        clean_handoff_authorized=True,
    )


@pytest.mark.parametrize(
    "key,value",
    [
        ("max_gpu_workers", None),
        ("max_gpu_workers", 5),
        ("independent_total_worker_limit", None),
        ("total_worker_limit_removed", True),
        ("max_workers_per_gpu", 2),
        ("allowed_gpu_indices", [0]),
        ("allowed_gpu_indices", [0, 5]),
        ("allowed_gpu_indices", [0, 6, 7]),
        ("steady_gpu_indices", [0]),
        ("steady_max_gpu_workers", 1),
        ("effective_device_capacity", 8),
        ("dual_gpu_two_worker_authorized", False),
        ("unknown_feedback_retry_allowed", True),
        ("host_ram_runtime_hard_gates_unchanged", False),
    ],
)
def test_cap_two_authority_cannot_silently_retain_old_unlimited_policy(key, value):
    body = authority()
    body[key] = value
    with pytest.raises(ValueError, match="authority required"):
        subject._authorization(subject.ROOT, body=body)


def test_cap_two_authority_accepts_exact_requested_scope():
    assert subject._authorization(subject.ROOT, body=authority())["preview_only"] is True


@pytest.fixture
def clean_pool(tmp_path, monkeypatch):
    source, target = tmp_path / "single_gpu0_01", tmp_path / "dual_gpu0_gpu6_01"
    parent = source / "attempts/attempt0003"
    monkeypatch.setattr(subject, "SOURCE_ROOT", source)
    monkeypatch.setattr(subject, "ROOT", target)

    def ref(path):
        return dict(path=str(path))

    protocol = dict(
        id="source-protocol",
        schema=subject.SOURCE_PROTOCOL_SCHEMA,
        output_root=str(parent),
        supervision_root=str(source),
        inheritance=ref(parent / "inheritance/record.json"),
    )
    queue = dict(
        protocol_id="source-protocol",
        active_children=[],
        phase="PAUSED_DURABLE_BOUNDARY_NO_AUTO_RESUME",
        global_external_resource_wait_seconds=123456.1,
        pilot_accepted=True,
        completed_evaluation_coordinates=[],
    )
    receipt = dict(
        schema="v51_clean_handoff_receipt.v1",
        status="CLEAN_NATURAL_HANDOFF",
        parent_root=str(parent),
        parent_attempt_root=str(parent),
        parent_supervision_root=str(source),
        parent_protocol=ref(parent / "protocol/record.json"),
        worker_signals_sent=0,
        all_gpu_locks_held=[0],
        fresh_empty_queue_verified=True,
        controller_original_process_exited=True,
        supervisor_original_process_exited=True,
        supervisor_signal_sent=True,
        supervisor_signals_sent=1,
        controller_launch=ref(parent / "launch_01/record.json"),
        supervisor_launch=ref(source / "supervisor/launch/record.json"),
        supervisor_actual_controller_exit=ref(
            source / "supervisor/attempt0003/actual_exit/record.json"
        ),
        supervisor_closeout=ref(source / "supervisor/closeout/record.json"),
        actual_progress=ref(parent / "actual_final_progress/record.json"),
        parent_final_queue=ref(parent / "queue/status.json"),
        global_resource_wait_seconds=123457,
        preflight=ref(target / "handoff/preflight/record.json"),
    )
    records = {
        parent / "protocol/record.json": protocol,
        parent / "inheritance/record.json": dict(
            schema=subject.SOURCE_INHERITANCE_SCHEMA,
            new_root=str(parent),
            context_inheritances=[],
            safe_recovery_audit=dict(allowed=True),
        ),
        parent / "queue/status.json": queue,
        parent / "launch_01/record.json": dict(
            protocol_id="source-protocol", pid=100, birth="1000"
        ),
        source / "supervisor/launch/record.json": dict(pid=99, birth="999"),
        source / "supervisor/attempt0003/actual_exit/record.json": dict(
            pid=100,
            birth="1000",
            attempt_root=str(parent),
            returncode=1,
            manual_stop_requested=True,
            stop_forwarded=True,
        ),
        source / "supervisor/closeout/record.json": dict(
            status="STOPPED_BY_EXPLICIT_REQUEST",
            automatic_recovery_after_manual_stop=False,
            received_signals=[15],
        ),
        parent / "actual_final_progress/record.json": dict(
            remaining_physical_updates=1142,
            remaining_outers=3,
            endpoint_scores_or_answers_read=False,
            original_state_or_feedback_modified=False,
        ),
        parent / "failure/record.json": dict(
            phase=queue["phase"],
            error_type="DurablePause",
            error="explicit safe stop requested",
            stop_error=None,
            actual_progress_audit_error=None,
        ),
        target / "handoff/preflight/record.json": dict(
            status="CLEAN_NATURAL_WORKER_BOUNDARY",
            parent_protocol=receipt["parent_protocol"],
            launched_workers_all_complete_and_exit_zero=True,
            worker_signals_sent=0,
            observed_stage_bindings=[],
        ),
        target / "handoff/receipt/record.json": receipt,
    }
    monkeypatch.setattr(subject, "checked", lambda path: copy.deepcopy(records[Path(path)]))
    monkeypatch.setattr(subject, "entry", ref)
    monkeypatch.setattr(subject, "file_ref", ref)
    monkeypatch.setattr(
        subject, "read_ref", lambda item: copy.deepcopy(records[Path(item["path"])])
    )
    monkeypatch.setattr(subject.old, "_stopped", lambda launch: None)
    return SimpleNamespace(
        source=source,
        parent=parent,
        target=target,
        protocol=protocol,
        queue=queue,
        receipt=receipt,
        records=records,
        receipt_ref=ref(target / "handoff/receipt/record.json"),
    )


def test_clean_receipt_uses_latest_validated_attempt_not_historical_pinned_failure(clean_pool):
    value = subject._read_handoff(clean_pool.parent, clean_pool.protocol, clean_pool.receipt_ref)
    assert value[1]["parent_attempt_root"].endswith("attempt0003")
    assert value[2]["global_external_resource_wait_seconds"] == 123456.1


@pytest.mark.parametrize(
    "mutation",
    [
        "worker_signal",
        "not_all_locks",
        "not_empty",
        "worker_failure",
        "unknown_pause",
        "wrong_controller_birth",
        "not_manual_supervisor_exit",
        "auto_after_stop",
        "wrong_attempt",
        "wait_reset",
        "missing_preflight_success",
    ],
)
def test_clean_receipt_fails_closed_on_any_nonclean_boundary(clean_pool, mutation):
    pool = clean_pool
    if mutation == "worker_signal":
        pool.receipt["worker_signals_sent"] = 1
    elif mutation == "not_all_locks":
        pool.receipt["all_gpu_locks_held"] = [0, 1, 2, 3]
    elif mutation == "not_empty":
        pool.queue["active_children"] = [dict(pid=44)]
    elif mutation == "worker_failure":
        pool.records[pool.parent / "failure/record.json"]["error_type"] = "ValueError"
    elif mutation == "unknown_pause":
        pool.records[pool.parent / "failure/record.json"]["error"] = "unknown failure"
    elif mutation == "wrong_controller_birth":
        pool.records[pool.source / "supervisor/attempt0003/actual_exit/record.json"]["birth"] = (
            "other"
        )
    elif mutation == "not_manual_supervisor_exit":
        pool.records[pool.source / "supervisor/attempt0003/actual_exit/record.json"][
            "manual_stop_requested"
        ] = False
    elif mutation == "auto_after_stop":
        pool.records[pool.source / "supervisor/closeout/record.json"][
            "automatic_recovery_after_manual_stop"
        ] = True
    elif mutation == "wrong_attempt":
        pool.receipt["parent_attempt_root"] = str(pool.source)
    elif mutation == "wait_reset":
        pool.receipt["global_resource_wait_seconds"] = 0
    elif mutation == "missing_preflight_success":
        pool.records[pool.target / "handoff/preflight/record.json"][
            "launched_workers_all_complete_and_exit_zero"
        ] = False
    with pytest.raises(ValueError):
        subject._read_handoff(pool.parent, pool.protocol, pool.receipt_ref)


def test_clean_initialization_inherits_dynamic_frontier_and_partial_safe_prefix(
    clean_pool, monkeypatch
):
    calls = []

    def frontier(root, parent, protocol, authority_ref, audit, *, allowed_parent_schemas):
        calls.append((root, parent, protocol, authority_ref, audit, allowed_parent_schemas))
        return dict(
            context_inheritances=[
                dict(
                    interrupted_stage_bindings={}, replay_resume=dict(inherited_response_count=288)
                )
            ],
            remaining_optimizer_updates=1142,
            remaining_outer_updates=3,
        )

    monkeypatch.setattr(subject, "_build_frontier", frontier)
    value = subject.inspect_clean_handoff(
        clean_pool.target,
        clean_pool.parent,
        handoff_receipt=clean_pool.receipt_ref,
        authorization_body=authority(),
    )
    assert value["remaining_optimizer_updates"] == 1142
    assert value["context_inheritances"][0]["replay_resume"]["inherited_response_count"] == 288
    assert value["inherited_resource_wait_seconds"] == 123457
    assert value["max_gpu_workers"] == value["independent_total_worker_limit"] == 2
    assert value["total_worker_limit_removed"] is False
    assert value["clean_handoff_from_successful_workers"] is True
    assert value["initial_known_failure_exception_applied"] is False
    assert calls[0][1] == clean_pool.parent
    assert calls[0][-1] == (subject.SOURCE_INHERITANCE_SCHEMA,)
    assert calls[0][4]["reason"] == "explicit_clean_natural_handoff_not_failure_retry"


def test_clean_initialization_cannot_smuggle_current_interrupted_worker(clean_pool, monkeypatch):
    monkeypatch.setattr(
        subject,
        "_build_frontier",
        lambda *args, **kwargs: dict(
            context_inheritances=[dict(interrupted_stage_bindings={"train": {}})]
        ),
    )
    with pytest.raises(ValueError, match="interrupted worker"):
        subject.inspect_clean_handoff(
            clean_pool.target,
            clean_pool.parent,
            handoff_receipt=clean_pool.receipt_ref,
            authorization_body=authority(),
        )


def test_live_preflight_requires_all_current_workers_to_succeed(clean_pool):
    queue = dict(clean_pool.queue, phase="RUNNING")
    # This metadata-only empty synthetic attempt may still carry safe old
    # prefixes; new launch failure is separately refused by inspect_stage.
    value = subject.preflight_clean_handoff(clean_pool.parent, queue)
    assert value["launched_workers_all_complete_and_exit_zero"] is True
    assert value["worker_signals_sent"] == 0


@pytest.mark.parametrize("mutation", ["active", "failed", "foreign", "all_finished"])
def test_live_preflight_rejects_nonhandoff_state(clean_pool, mutation):
    queue = dict(clean_pool.queue, phase="RUNNING")
    if mutation == "active":
        queue["active_children"] = [dict(pid=8)]
    elif mutation == "failed":
        queue["phase"] = "STOPPED_FAILURE_NO_RETRY"
    elif mutation == "foreign":
        clean_pool.protocol["supervision_root"] = "/tmp/foreign"
    else:
        queue["completed_evaluation_coordinates"] = list(range(9))
    with pytest.raises(ValueError):
        subject.preflight_clean_handoff(clean_pool.parent, queue)


def test_actual_historical_frontier_read_only_math_preserved(tmp_path):
    # Exercise the real immutable frontier assembly, not the old initial
    # exception. This fixture is historical only; production uses the receipt's
    # latest V50 attempt and its post-stop progress.
    parent = subject.PRODUCTION_ROOT / "fixed_gpu_reservation_02/attempts/attempt0004"
    protocol = subject.checked(parent / "protocol/record.json")
    value = subject._build_frontier(
        tmp_path / "new",
        parent,
        protocol,
        dict(test=True),
        dict(allowed=True),
        allowed_parent_schemas=("v47_fixed_gpu_reservation_inheritance.v1",),
    )
    assert value["remaining_optimizer_updates"] == 1147
    assert value["remaining_outer_updates"] == 3
    assert value["remaining_scientific_budget"]["future_first_sampling_feedback_episodes"] == 700
    assert value["remaining_scientific_budget"]["pending_sealed_feedback_episodes"] == 1400
    assert value["max_gpu_workers"] == value["independent_total_worker_limit"] == 2
    assert value["total_worker_limit_removed"] is False
    assert "Full251_actual_training_restart_step" not in value
    assert value["initial_known_failure_exception_applied"] is False
    assert value["original_accounting_reset"] is False


def test_dynamic_frontier_retires_old_bootstrap_without_restarting_full251(tmp_path, monkeypatch):
    """A completed Full251 uses its actual 1490 checkpoint, never the old 1334 bootstrap."""
    parent, target = tmp_path / "parent", tmp_path / "new"

    def ref(path):
        return dict(path=str(path))

    rows = [
        dict(seed=seed, arm=arm, step=1490, checkpoint=dict(path=f"saved/{seed}/{arm}"))
        for seed in (137, 251, 389)
        for arm in ("Static", "C-only", "Full")
    ]
    rows[-1]["step"] = 894
    protocol = dict(inheritance=ref(parent / "inheritance/record.json"))
    historical = dict(
        schema=subject.SOURCE_INHERITANCE_SCHEMA,
        new_root=str(parent),
        context_inheritances=[],
        all_parent_stage_bindings=[],
        completed_evaluations=[],
        single_gpu0_authorized=True,
        Full251_actual_training_restart_step=1334,
        Full251_initial_training_complete=False,
        Full251_training_first_if_incomplete=True,
        resource_retirement_handoff=dict(path="old-manual-stop"),
        final_device_authorization=dict(path="old-gpu0-only-choice"),
    )
    records = {
        parent / "inheritance/record.json": historical,
        parent / "actual_final_progress/record.json": dict(
            arms=rows,
            completed_physical_updates=11026,
            remaining_physical_updates=596,
            completed_outers=22,
            remaining_outers=2,
        ),
        parent / "queue/status.json": dict(global_external_resource_wait_seconds=123456.25),
    }
    monkeypatch.setattr(subject, "entry", ref)
    monkeypatch.setattr(subject, "file_ref", ref)
    monkeypatch.setattr(subject, "checked", lambda path: copy.deepcopy(records[Path(path)]))
    monkeypatch.setattr(
        subject, "read_ref", lambda item: copy.deepcopy(records[Path(item["path"])])
    )
    monkeypatch.setattr(
        subject,
        "checkpoint_metadata",
        lambda value, *, coordinate: dict(
            seed=coordinate[0], arm=coordinate[1], step=coordinate[2], reference=value
        ),
    )
    value = subject._build_frontier(
        target,
        parent,
        protocol,
        dict(test=True),
        dict(allowed=True),
        allowed_parent_schemas=(subject.SOURCE_INHERITANCE_SCHEMA,),
    )
    latest = {(row["seed"], row["arm"]): row for row in value["latest_checkpoints"]}
    assert latest[(251, "Full")]["step"] == 1490
    assert value["remaining_optimizer_updates"] == 596
    assert value["remaining_outer_updates"] == 2
    assert value["inherited_resource_wait_seconds"] == 123457
    assert value["allowed_gpu_indices"] == [0, 6]
    assert value["max_gpu_workers"] == value["independent_total_worker_limit"] == 2
    assert value["max_workers_per_gpu"] == 1
    assert value["dual_gpu_two_worker_authorized"] is True
    assert "single_gpu0_authorized" not in value
    assert not any(key.startswith("Full251_") for key in value)
    assert "resource_retirement_handoff" not in value
    assert "final_device_authorization" not in value
    old_policy = value["historical_source_transition_policy"]
    assert old_policy["Full251_actual_training_restart_step"] == 1334
    assert historical["Full251_initial_training_complete"] is False


def test_real_live_v50_metadata_is_compatible_without_claiming_clean_handoff():
    """Read-only real metadata preview; does not require/forge an empty queue or receipt."""
    parent = subject.SOURCE_ROOT
    protocol_ref = subject.entry(parent / "protocol/record.json")
    protocol = subject.read_ref(protocol_ref)
    assert protocol["id"] == "bd19014d33e034cc7b64b25bd919f9e332dadff65b934b2e89b70aaae300c912"
    assert protocol["schema"] == subject.SOURCE_PROTOCOL_SCHEMA
    assert protocol["output_root"] == protocol["supervision_root"] == str(parent)
    assert protocol["allowed_gpu_indices"] == [0]
    assert protocol["max_gpu_workers"] == protocol["max_workers_per_gpu"] == 1
    inherited = subject.read_ref(protocol["inheritance"])
    assert inherited["schema"] == subject.SOURCE_INHERITANCE_SCHEMA
    assert inherited["new_root"] == str(parent)
    assert inherited["safe_recovery_audit"]["allowed"] is True
    queue = subject.read_ref(subject.file_ref(parent / "queue/status.json"))
    assert queue["protocol_id"] == protocol["id"]
    # Any live/initializing/draining processes remain untouched and are not
    # accepted here. The production handoff must later run its full preflight.
    prior_items = {row["new_context_directory"]: row for row in inherited["context_inheritances"]}
    observed_complete = []
    for path in sorted(parent.glob("contexts/seed*/*/step*/context/record.json")):
        directory = path.parent.parent
        item = prior_items.get(str(directory))
        original = item["original_context"] if item else subject.entry(path)
        _, context, origin = subject._actual_context(original)
        assert context["id"] == (item["original_context_id"] if item else context["id"])
        assert context["run_root"] == context["outer_root"] == str(origin)
        task_plan = subject.read_ref(context["task_plan"]) if context["due_outer"] else None
        for stage in subject.STAGES:
            binding = item["stage_bindings"][stage] if item else None
            parent_bound = binding is not None and binding["protocol_scope"] == "parent"
            stage_root = Path(binding["directory"]) if parent_bound else directory / stage
            if not all((stage_root / name / "record.json").exists() for name in ("result", "exit")):
                continue
            exit_record = subject.checked(stage_root / "exit/record.json")
            assert exit_record["returncode"] == 0
            owner = binding["protocol_ref"] if parent_bound else protocol_ref
            complete = subject.inspect_stage(
                stage_root, subject.read_ref(owner), context, stage, task_plan, protocol_ref=owner
            )
            assert complete is not None
            observed_complete.append(complete)
    assert observed_complete, "expected actual successful V50 stages or inherited stages"


@pytest.fixture
def real_handoff_records(tmp_path, monkeypatch):
    """Actual producer/consumer JSON formats; no real process operations."""
    handoff = importlib.import_module("finqa_v51_handoff")
    source = tmp_path / "single_gpu0_01"
    parent, target = source, tmp_path / "dual_gpu0_gpu6_01"
    monkeypatch.setattr(subject, "SOURCE_ROOT", source)
    monkeypatch.setattr(subject, "ROOT", target)
    monkeypatch.setattr(subject.old, "_stopped", lambda launch: None)
    handoff.publish(
        parent / "inheritance/record.json",
        dict(
            schema=subject.SOURCE_INHERITANCE_SCHEMA,
            new_root=str(parent),
            context_inheritances=[],
            safe_recovery_audit=dict(allowed=True),
        ),
    )
    protocol = handoff.publish(
        parent / "protocol/record.json",
        dict(
            schema=subject.SOURCE_PROTOCOL_SCHEMA,
            output_root=str(parent),
            supervision_root=str(source),
            inheritance=handoff.entry(parent / "inheritance/record.json"),
        ),
    )
    controller = dict(pid=901, birth="12345", protocol_id=protocol["id"])
    handoff.publish(parent / "launch_01/record.json", controller)
    handoff.publish(source / "supervisor/launch/record.json", dict(pid=900, birth="12344"))
    queue = dict(
        at=handoff.base.timestamp(time.time()),
        protocol_id=protocol["id"],
        active_children=[],
        phase="RUNNING",
        pilot_accepted=True,
        completed_evaluation_coordinates=[],
        global_external_resource_wait_seconds=140000.25,
    )
    preflight = subject.preflight_clean_handoff(parent, queue)
    handoff.publish(
        target / "handoff_01/preflight/record.json",
        dict(at=handoff.base.timestamp(time.time()), **preflight),
    )
    handoff.publish(target / "handoff_01/barrier_acquired/record.json", dict(gpus=[0]))
    queue["phase"] = "PAUSED_DURABLE_BOUNDARY_NO_AUTO_RESUME"
    # The real controller's status is mutable non-self-ID JSON, whereas all
    # other refs below are immutable records. Keep this important distinction.
    (parent / "queue").mkdir()
    (parent / "queue/status.json").write_text(json.dumps(queue))
    handoff.publish(
        parent / "failure/record.json",
        dict(
            phase=queue["phase"],
            error_type="DurablePause",
            error="explicit safe stop requested",
            stop_error=None,
            actual_progress_audit_error=None,
        ),
    )
    handoff.publish(
        parent / "actual_final_progress/record.json",
        dict(
            endpoint_scores_or_answers_read=False,
            original_state_or_feedback_modified=False,
            remaining_physical_updates=1110,
            remaining_outers=3,
        ),
    )
    handoff.publish(
        source / "supervisor/attempt0001/actual_exit/record.json",
        dict(
            **controller,
            attempt_number=1,
            attempt_root=str(parent),
            returncode=1,
            manual_stop_requested=True,
            stop_forwarded=True,
        ),
    )
    handoff.publish(
        source / "supervisor/closeout/record.json",
        dict(
            status="STOPPED_BY_EXPLICIT_REQUEST",
            automatic_recovery_after_manual_stop=False,
            final_attempt=1,
            received_signals=[15],
        ),
    )
    spec = dict(
        parent_root=str(parent),
        parent_supervision_root=str(source),
        parent_protocol=handoff.entry(parent / "protocol/record.json"),
        parent_protocol_id=protocol["id"],
        controller_identity=controller,
        controller_launch=handoff.entry(parent / "launch_01/record.json"),
        supervisor_launch=handoff.entry(source / "supervisor/launch/record.json"),
    )
    current = dict(root=parent, number=1, controller_identity=controller, queue=queue)
    return SimpleNamespace(
        handoff=handoff,
        source=source,
        parent=parent,
        target=target,
        spec=spec,
        current=current,
        protocol=protocol,
        queue=queue,
    )


def test_real_handoff_producer_receipt_and_preflight_consumed_without_ref_reformatting(
    real_handoff_records,
):
    case = real_handoff_records
    h = case.handoff
    receipt = h.clean_receipt_body(case.target, case.spec, elapsed_seconds=17.25)
    path = case.target / "handoff_01/closeout/record.json"
    h.publish(path, receipt)
    reference = h.entry(path)
    accepted_ref, accepted, queue, preflight = subject._read_handoff(
        case.parent, case.protocol, reference
    )
    assert accepted_ref == reference == subject.entry(path)
    assert accepted["parent_protocol"] == subject.entry(case.parent / "protocol/record.json")
    assert accepted["parent_final_queue"] == subject.file_ref(case.parent / "queue/status.json")
    assert "id" not in accepted["parent_final_queue"]
    assert "id" in accepted["actual_progress"]
    assert accepted["global_resource_wait_seconds"] == 140001
    assert accepted["handoff_elapsed_seconds"] == 17.25
    assert subject.old._time(accepted["at"]) > 0
    assert queue["global_external_resource_wait_seconds"] == 140000.25
    assert preflight["launched_workers_all_complete_and_exit_zero"] is True


def test_real_producer_receipt_enters_controller_activation_and_inheritance(
    real_handoff_records,
    monkeypatch,
):
    case = real_handoff_records
    h = case.handoff
    controller = importlib.import_module("finqa_v51_controller")
    receipt_path = case.target / "handoff_01/closeout/record.json"
    h.publish(
        receipt_path,
        h.clean_receipt_body(case.target, case.spec, elapsed_seconds=31.5),
    )
    prepared = h.publish(case.target / "authorization/record.json", authority())
    h.publish(case.target / "preparation/record.json", dict(test_only=True))
    monkeypatch.setattr(controller, "ROOT", case.target)
    monkeypatch.setattr(controller, "LIVE_PARENT_ROOT", case.source)
    monkeypatch.setattr(controller, "checked_implementation", lambda root: dict(id="CPU-only"))
    monkeypatch.setattr(
        controller, "checked_preparation", lambda: dict(parent_root=str(case.parent))
    )
    monkeypatch.setattr(
        controller, "live_parent_protocol", lambda root: h.checked(root / "protocol/record.json")
    )
    monkeypatch.setattr(
        controller,
        "authorization_body",
        lambda *, parentroot, automatic: dict(
            authority(),
            parent_protocol=h.entry(parentroot / "protocol/record.json"),
            source_supervision_root=str(case.source),
        ),
    )
    # Exercise actual initializer, publication, activation authority, and clean
    # receipt checks. The scientific frontier itself has separate real-metadata
    # coverage above and must not load tensors or register science in this test.
    monkeypatch.setattr(
        subject,
        "_build_frontier",
        lambda *args, **kwargs: dict(
            schema=subject.SCHEMA,
            new_root=str(case.target),
            context_inheritances=[],
            remaining_optimizer_updates=1110,
            remaining_outer_updates=3,
        ),
    )
    monkeypatch.setattr(
        controller, "_finish_initialization", lambda root, implementation, inherited: inherited
    )
    inherited = controller.initialize_with_handoff(receipt_path, root=case.target)
    assert inherited["remaining_optimizer_updates"] == 1110
    assert inherited["inherited_resource_wait_seconds"] == 140001
    assert inherited["max_gpu_workers"] == inherited["independent_total_worker_limit"] == 2
    activated = h.checked(case.target / "activation_authorization/record.json")
    assert activated["prepared_authorization"]["id"] == prepared["id"]
    assert activated["parent_protocol"] == h.entry(case.parent / "protocol/record.json")
    registration = h.checked(case.target / "activation_registration/record.json")
    assert registration["handoff"] == h.entry(receipt_path)
    assert registration["scientific_controller_started"] is False


def physical_proof():
    return dict(
        observation=dict(
            label="before_response",
            allocated_bytes=20 * GIB,
            reserved_bytes=56 * GIB,
            peak_allocated_bytes=56 * GIB,
            peak_reserved_bytes=56 * GIB,
            physical_free_bytes=GIB,
            device_total_bytes=80 * GIB,
        ),
        required_physical_free_bytes=2 * GIB,
        lifetime_allocated_limit_bytes=76 * GIB,
        reason="physical_boundary_free_exhausted",
        model_load_started=True,
        proof_no_scientific_work=False,
        allocator_anchor_and_lifetime_peak_invariants_passed=True,
    )


def test_typed_physical_failure_requires_actual_failed_free_predicate():
    proof = physical_proof()
    assert subject._physical_resource_assessment(proof) == proof["observation"]


@pytest.mark.parametrize(
    "mutation",
    [
        "no_actual_bytes",
        "boolean_bytes",
        "free_passes",
        "peak_exceeded",
        "reservation_impossible",
        "wrong_limit",
        "wrong_reason",
        "claimed_no_science",
        "before_model",
        "invariant_failed",
    ],
)
def test_typed_physical_failure_cannot_hide_unrelated_or_inconsistent_error(mutation):
    proof = physical_proof()
    row = proof["observation"]
    if mutation == "no_actual_bytes":
        row["physical_free_bytes"] = None
    elif mutation == "boolean_bytes":
        row["physical_free_bytes"] = False
    elif mutation == "free_passes":
        row["physical_free_bytes"] = 2 * GIB
    elif mutation == "peak_exceeded":
        row["peak_allocated_bytes"] = 77 * GIB
    elif mutation == "reservation_impossible":
        row["device_total_bytes"] = 56 * GIB
    elif mutation == "wrong_limit":
        proof["required_physical_free_bytes"] = GIB
    elif mutation == "wrong_reason":
        proof["reason"] = "checksum mismatch"
    elif mutation == "claimed_no_science":
        proof["proof_no_scientific_work"] = True
    elif mutation == "before_model":
        proof["model_load_started"] = False
    elif mutation == "invariant_failed":
        proof["allocator_anchor_and_lifetime_peak_invariants_passed"] = False
    with pytest.raises(ValueError, match="typed physical"):
        subject._physical_resource_assessment(proof)


@pytest.fixture
def recovery_pool(tmp_path, monkeypatch):
    root = tmp_path / "dual_gpu0_gpu6_01"
    directory = root / "contexts/seed251/full/step1237_train/train"
    monkeypatch.setattr(subject, "ROOT", root)
    owner = dict(
        protocol_id="p",
        context_id="c",
        stage="train",
        pid=2,
        birth="CPU",
        gpu_index=6,
        gpu_uuid="g6",
    )
    proof = dict(
        physical_proof(),
        **owner,
        schema="v51_observed_physical_resource_failure.v1",
        error_type="ReservationPhysicalResourceError",
    )
    admission_path = directory / "reservation/admission/record.json"
    proof["reservation_admission"] = dict(path=str(admission_path))
    protocol = dict(
        schema=subject.PROTOCOL_SCHEMA,
        max_gpu_workers=2,
        independent_total_worker_limit=2,
        total_worker_limit_removed=False,
        max_workers_per_gpu=1,
        output_root=str(root),
        supervision_root=str(root),
        id="p",
        allowed_gpu_indices=[0, 6],
        gpu_uuids={"6": "g6"},
        implementation_id="impl",
        gpu_reservation_policy=dict(schema="policy"),
    )
    source = root / "implementation/finqa_v51_reservation.py"
    records = {
        root / "protocol/record.json": protocol,
        root / "queue/status.json": dict(
            protocol_id="p", active_children=[], phase="STOPPED_FAILURE_NO_RETRY"
        ),
        root / "failure/record.json": dict(
            protocol_id="p",
            phase="STOPPED_FAILURE_NO_RETRY",
            stop_error=None,
            actual_progress_audit_error=None,
            error_type="ValueError",
            error="worker reported failure: train",
        ),
        root / "launch_01/record.json": dict(pid=1, birth="CPU"),
        root / "actual_final_progress/record.json": dict(
            endpoint_scores_or_answers_read=False, original_state_or_feedback_modified=False
        ),
        directory / "launch/record.json": owner,
        directory / "exit/record.json": dict(owner, returncode=1, stop_requested=True),
        directory / "failure/record.json": dict(
            owner,
            error_type="ReservationPhysicalResourceError",
            error="physical boundary reserve exhausted",
            API_calls=0,
            original_mathematical_functions_unchanged=True,
            resources=None,
            stop_evidence=dict(stop_requested=False, received_signals=[]),
        ),
        directory / "reservation/physical_resource_failure/record.json": proof,
        admission_path: dict(
            owner,
            before_CPU_state_and_model_load=True,
            scientific_model_calls=0,
            cuda_initialized=True,
            policy=protocol["gpu_reservation_policy"],
        ),
        root / "implementation/record.json": dict(id="impl", sha256={source.name: "actualsha"}),
    }
    for path, value in records.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value))
    monkeypatch.setattr(subject, "checked", lambda path: copy.deepcopy(records[Path(path)]))
    monkeypatch.setattr(subject, "entry", lambda path: dict(path=str(path)))
    monkeypatch.setattr(subject, "file_ref", lambda path: dict(path=str(path)))
    monkeypatch.setattr(subject, "read_ref", lambda ref: copy.deepcopy(records[Path(ref["path"])]))
    monkeypatch.setattr(subject.old, "_stopped", lambda launch: None)
    monkeypatch.setattr(subject.old, "sha", lambda path: "actualsha")
    return SimpleNamespace(root=root, directory=directory, records=records, proof=proof)


def test_future_typed_physical_failure_has_actual_resource_trigger_not_generic_whitelist(
    recovery_pool,
):
    result = subject.validate_safe_recovery(recovery_pool.root)
    assert result["allowed"] is True
    assert result["controller_trigger_stage"] == "train"
    assert result["child_stop_consequences_not_used_as_root_cause"] is True
    assert result["interrupted_stages"][0]["recovery_kind"] == "actual_committed_training_state"


@pytest.mark.parametrize(
    "key,value",
    [
        ("schema", "v50_single_gpu0_supervised_protocol.v1"),
        ("allowed_gpu_indices", [0]),
        ("allowed_gpu_indices", [0, 5]),
        ("max_gpu_workers", 3),
        ("independent_total_worker_limit", 3),
        ("total_worker_limit_removed", True),
        ("max_workers_per_gpu", 2),
    ],
)
def test_automatic_recovery_cannot_reclassify_parent_or_expand_dual_gpu_scope(
    recovery_pool, key, value
):
    recovery_pool.records[recovery_pool.root / "protocol/record.json"][key] = value
    result = subject.validate_safe_recovery(recovery_pool.root)
    assert result["allowed"] is False
    assert "foreign automatic-recovery parent" in result["reason"]


def add_stopped_premodel_sibling(pool):
    directory = pool.root / "contexts/seed389/full/step1192_outer/virtual_point"
    owner = dict(
        protocol_id="p",
        context_id="waiting",
        stage="virtual_point",
        pid=3,
        birth="WAIT",
        gpu_index=6,
        gpu_uuid="g6",
    )
    failure = dict(
        owner,
        error_type="ReservationWaitStopped",
        error="safe stop requested during CUDA resource wait",
        API_calls=0,
        original_mathematical_functions_unchanged=True,
        resources=None,
        stop_evidence=dict(stop_requested=True, received_signals=[15]),
    )
    status = dict(
        owner,
        schema="v51_pre_scientific_resource_wait.v1",
        phase="STOPPED",
        sequence=1,
        error=dict(type=failure["error_type"], message=failure["error"]),
        cuda_initialized=True,
        model_load_started=False,
        proof_no_scientific_work=True,
        scientific_model_calls=0,
        API_calls=0,
        optimizer_commits=0,
        new_feedback_calls=0,
        actual_response_calls=0,
        original_scientific_source_unchanged=True,
        worker_slot_retained=True,
        gpu_lease_retained=True,
        lifetime_peak_reset_calls=1,
        gpu_admission_policy_schema="v51_empirical_shared_gpu_reserved_admission.v1",
        gpu_reservation_policy_schema="v51_adaptive_same_process_native_segment_reservation.v1",
    )
    updates = {
        directory / "launch/record.json": owner,
        directory / "exit/record.json": dict(owner, returncode=1, stop_requested=True),
        directory / "failure/record.json": failure,
        directory / "reservation_wait/episode0001/status.json": status,
        directory / "reservation_wait/episode0001/event000001/record.json": copy.deepcopy(status),
    }
    pool.records.update(updates)
    for path, value in updates.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value))
    return directory, status


def test_stopped_premodel_virtual_sibling_is_safe_consequence_of_actual_resource_failure(
    recovery_pool,
):
    add_stopped_premodel_sibling(recovery_pool)
    result = subject.validate_safe_recovery(recovery_pool.root)
    assert result["allowed"] is True
    waiting = next(row for row in result["interrupted_stages"] if row["stage"] == "virtual_point")
    assert waiting["pre_scientific_resource_wait"] is True
    assert waiting["pre_cuda"] is False
    assert result["controller_trigger_stage"] == "train"


@pytest.mark.parametrize("mutation", ["started", "counter", "owner", "event", "as_root"])
def test_wait_stop_cannot_hide_science_or_become_resource_root(recovery_pool, mutation):
    directory, status = add_stopped_premodel_sibling(recovery_pool)
    if mutation == "started":
        marker = directory / "reservation/model_load_started/record.json"
        marker.parent.mkdir(parents=True)
        marker.write_text("{}")
    elif mutation == "counter":
        status["new_feedback_calls"] = 1
    elif mutation == "owner":
        status["birth"] = "foreign"
    elif mutation == "event":
        recovery_pool.records[directory / "reservation_wait/episode0001/event000001/record.json"][
            "sequence"
        ] = 0
    else:
        recovery_pool.records[recovery_pool.root / "failure/record.json"]["error"] = (
            "worker reported failure: virtual_point"
        )
    assert subject.validate_safe_recovery(recovery_pool.root)["allowed"] is False


@pytest.mark.parametrize(
    "mutation",
    [
        "generic_error",
        "wrong_worker",
        "wrong_gpu",
        "changed_source",
        "prior_signal",
        "unknown_controller",
        "manual_stop",
        "no_failed_predicate",
        "wrong_admission",
    ],
)
def test_future_typed_failure_requires_exact_provenance_and_safe_root(recovery_pool, mutation):
    root, directory, records = recovery_pool.root, recovery_pool.directory, recovery_pool.records
    failure = records[directory / "failure/record.json"]
    if mutation == "generic_error":
        failure["error_type"] = "ReservationAdmissionError"
    elif mutation == "wrong_worker":
        recovery_pool.proof["birth"] = "OTHER"
    elif mutation == "wrong_gpu":
        recovery_pool.proof["gpu_uuid"] = "foreign"
    elif mutation == "changed_source":
        records[root / "implementation/record.json"]["sha256"]["finqa_v51_reservation.py"] = (
            "changed"
        )
    elif mutation == "prior_signal":
        failure["stop_evidence"]["stop_requested"] = True
        failure["stop_evidence"]["received_signals"] = [15]
    elif mutation == "unknown_controller":
        records[root / "failure/record.json"]["error"] = "admission heartbeat binding mismatch"
    elif mutation == "manual_stop":
        records[root / "failure/record.json"]["error"] = "explicit safe stop requested"
    elif mutation == "no_failed_predicate":
        recovery_pool.proof["observation"]["physical_free_bytes"] = 3 * GIB
    elif mutation == "wrong_admission":
        records[directory / "reservation/admission/record.json"]["context_id"] = "other"
    assert subject.validate_safe_recovery(root)["allowed"] is False


@pytest.mark.parametrize("stage", ["virtual_point", "generate"])
def test_post_model_generation_resource_failure_does_not_reexecute_unknown_feedback(
    recovery_pool, stage, monkeypatch
):
    records, root, old_dir = recovery_pool.records, recovery_pool.root, recovery_pool.directory
    new_dir = root / (
        "evaluations/seed389_full/generate"
        if stage == "generate"
        else "contexts/seed389/full/step1192_outer/virtual_point"
    )
    changed = {}
    for path, value in records.items():
        value = copy.deepcopy(value)
        if path.is_relative_to(old_dir):
            path = new_dir / path.relative_to(old_dir)
            value["stage"] = stage
        changed[path] = value
    records.clear()
    records.update(changed)
    records[root / "failure/record.json"]["error"] = "worker reported failure: " + stage
    for path, value in records.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value))
    monkeypatch.setattr(
        subject,
        "_verified_physical_resource_failure",
        lambda *args: dict(evidence_refs=[]),
    )
    # Old launch files are a mock fixture only; constrain enumeration to the
    # transformed scientific consumer so the refusal tests generation safety.
    original_glob = Path.glob
    monkeypatch.setattr(
        Path,
        "glob",
        lambda self, pat: (
            iter([new_dir / "launch/record.json"])
            if self == root
            and (
                ("evaluations" in pat and stage == "generate")
                or ("contexts" in pat and stage != "generate")
            )
            else iter([])
            if self == root
            else original_glob(self, pat)
        ),
    )
    result = subject.validate_safe_recovery(root)
    assert result["allowed"] is False
    assert result["reason"] == "unsupported_partial_generation_or_unknown_feedback_requires_user"
