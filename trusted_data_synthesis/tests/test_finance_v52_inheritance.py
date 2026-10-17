"""V52 explicit response121 recovery; later attempts remain resource-failure only."""

import copy
import importlib
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
subject = importlib.import_module("finqa_v52_inheritance")
GIB = 1024**3


def authority():
    parent = subject.SOURCE_ROOT
    return dict(
        user_consent="恢复实验",
        time_limits_removed=True,
        automatic_recovery_authorized=True,
        unknown_feedback_retry_allowed=False,
        unknown_signal_automatic_retry_allowed=False,
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
        explicit_signal_checkpoint_recovery_authorized=True,
        known_failure_recovery_authorized=True,
        automatic_attempt=False,
        clean_handoff_authorized=False,
        initial_parent_protocol=subject.entry(parent / "protocol/record.json"),
        parent_protocol=subject.entry(parent / "protocol/record.json"),
        initial_response_checkpoint=subject.entry(
            parent / subject.SOURCE_CHECKPOINT_RELATIVE / "record.json"
        ),
        initial_response_checkpoint_id=subject.SOURCE_CHECKPOINT_ID,
        initial_inherited_response_count=121,
        initial_remaining_response_count=310,
        initial_total_response_count=431,
        conditional_four_worker_authorization_activated=False,
        new_sampling_or_optimizer_dose_authorized=False,
    )


@pytest.fixture(scope="module")
def real_initial(tmp_path_factory):
    root = tmp_path_factory.mktemp("v52_actual_frontier") / "fresh"
    parent = subject.SOURCE_ROOT
    original_failure = subject.entry(parent / "failure/record.json")
    original_denial = subject.entry(parent / "supervisor/attempt0001/recovery_decision/record.json")
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(subject, "ROOT", root)
        value = subject.inspect_parent_recovery(root, parent, authorization_body=authority())
    assert not root.exists(), "read-only preview cannot publish official V52 records"
    assert subject.entry(parent / "failure/record.json") == original_failure
    assert (
        subject.entry(parent / "supervisor/attempt0001/recovery_decision/record.json")
        == original_denial
    )
    return SimpleNamespace(root=root, parent=parent, value=value)


def test_actual_initial_frontier_only_continues_response122_to431(real_initial):
    value = real_initial.value
    assert value["schema"] == subject.SCHEMA
    assert len(value["context_inheritances"]) == 1
    item = value["context_inheritances"][0]
    assert (item["seed"], item["arm"], item["step"]) == (389, "Full", 1192)
    replay = item["replay_resume"]
    assert replay["checkpoint"]["id"] == subject.SOURCE_CHECKPOINT_ID
    assert replay["inherited_response_count"] == 121
    assert replay["remaining_response_count"] == 310
    assert replay["total_response_count"] == 431
    assert replay["state_bytes_verified"] is True
    assert replay["state"]["sha256"] == subject.SOURCE_CHECKPOINT_SHA256
    assert replay["parent_saved_prefix_replayed_again"] is False
    assert item["task_cache_view"]["tasks"] == 744
    assert item["task_cache_view"]["read_only"] is True
    assert set(item["interrupted_stage_bindings"]) == {"replay_R3"}
    assert all(
        item["stage_bindings"][key]["protocol_scope"] == "parent"
        for key in (*subject.SHARDS, "virtual_point")
    )
    assert all(
        item["stage_bindings"][key]["protocol_scope"] == "current"
        for key in ("replay_R3", "distribution", "train")
    )


def test_actual_initial_scientific_dose_and_elapsed_accounting_are_inherited(real_initial):
    value = real_initial.value
    assert len(value["completed_evaluations"]) == 8
    assert value["remaining_optimizer_updates"] == 298
    assert value["remaining_outer_updates"] == 1
    budget = value["remaining_scientific_budget"]
    assert budget["pending_sealed_feedback_episodes"] == 700
    assert budget["future_first_sampling_feedback_episodes"] == 0
    assert budget["future_first_sampling_outers"] == 0
    assert budget["remaining_new_feedback_episodes"] == 0
    assert budget["remaining_endpoint_answers"] == 1147
    assert value["inherited_resource_wait_seconds"] == 117692
    assert value["original_accounting_reset"] is False
    assert value["allowed_gpu_indices"] == [0, 6]
    assert value["max_gpu_workers"] == value["independent_total_worker_limit"] == 2
    assert value["max_workers_per_gpu"] == 1
    assert value["time_limits_removed"] is True
    assert value["conditional_four_worker_authorization_activated"] is False


def test_explicit_new_authority_does_not_reclassify_old_unsafe_stop(real_initial):
    value = real_initial.value
    audit = value["safe_recovery_audit"]
    assert audit["allowed"] is True
    assert audit["explicit_initial_recovery_exception"] is True
    assert audit["automatic_recovery_of_this_old_failure_allowed"] is False
    assert audit["old_unsafe_decision_reclassified"] is False
    assert subject.read_ref(audit["old_unsafe_decision"])["allowed"] is False
    assert audit["sender_attribution"] == "unknown"
    assert audit["signal_sender_inferred"] is False
    assert audit["successful_model_release_claimed"] is False
    assert audit["checkpoint_state_bytes_sha256_verified"] is True
    assert value["initial_explicit_signal_recovery_exception_applied"] is True
    assert value["unknown_signal_automatic_retry_allowed"] is False
    assert subject.validate_safe_recovery(real_initial.parent)["allowed"] is False


@pytest.mark.parametrize(
    "key,value",
    [
        ("user_consent", ""),
        ("unknown_signal_automatic_retry_allowed", True),
        ("explicit_signal_checkpoint_recovery_authorized", False),
        ("known_failure_recovery_authorized", False),
        ("automatic_attempt", True),
        ("clean_handoff_authorized", True),
        ("initial_response_checkpoint_id", "other"),
        ("initial_inherited_response_count", 120),
        ("initial_remaining_response_count", 311),
        ("conditional_four_worker_authorization_activated", True),
        ("new_sampling_or_optimizer_dose_authorized", True),
        ("allowed_gpu_indices", [0, 6, 7]),
        ("max_gpu_workers", 4),
    ],
)
def test_explicit_authorization_cannot_expand_or_generalize_this_exception(
    tmp_path, monkeypatch, key, value
):
    root = tmp_path / "fresh"
    monkeypatch.setattr(subject, "ROOT", root)
    body = authority()
    body[key] = value
    with pytest.raises(ValueError):
        subject.inspect_parent_recovery(root, subject.SOURCE_ROOT, authorization_body=body)


@pytest.mark.parametrize(
    "relative,mutator",
    [
        ("protocol/record.json", lambda x: x.update(id="other")),
        (
            "supervisor/attempt0001/actual_exit/record.json",
            lambda x: x.update(manual_stop_requested=True),
        ),
        ("supervisor/attempt0001/recovery_decision/record.json", lambda x: x.update(allowed=True)),
        ("supervisor/closeout/record.json", lambda x: x.update(status="COMPLETE")),
        ("failure/record.json", lambda x: x.update(error="new failure")),
        (
            str(subject.SOURCE_CONTEXT_RELATIVE / "replay_R3/exit/record.json"),
            lambda x: x.update(returncode=0),
        ),
        (
            str(subject.SOURCE_CONTEXT_RELATIVE / "replay_R3/failure/record.json"),
            lambda x: x.update(error_type="OutOfMemoryError"),
        ),
        (
            str(subject.SOURCE_CONTEXT_RELATIVE / "replay_R3/failure/record.json"),
            lambda x: x["stop_evidence"].update(sender_attribution="guessed_sender"),
        ),
        (
            str(subject.SOURCE_CONTEXT_RELATIVE / "replay_R3/failure/record.json"),
            lambda x: x["resources"].update(all_gates_passed=False),
        ),
        (
            str(subject.SOURCE_CONTEXT_RELATIVE / "replay_R3/failure/record.json"),
            lambda x: x["resources"]["observations"][-1].update(deadline_limit_enforced=True),
        ),
        (str(subject.SOURCE_CHECKPOINT_RELATIVE / "record.json"), lambda x: x.update(cursor=120)),
        (
            str(subject.SOURCE_CHECKPOINT_RELATIVE / "record.json"),
            lambda x: x.update(state_sha256="bad"),
        ),
        ("actual_final_progress/record.json", lambda x: x.update(remaining_outers=0)),
    ],
)
def test_pinned_source_event_or_resource_evidence_mutation_is_rejected(
    relative, mutator, monkeypatch
):
    parent = subject.SOURCE_ROOT
    original = subject.checked
    target = parent / relative

    def changed(path):
        value = original(path)
        if Path(path) == target:
            value = copy.deepcopy(value)
            mutator(value)
        return value

    monkeypatch.setattr(subject, "checked", changed)
    with pytest.raises(ValueError):
        subject._inspect_explicit_source_stop(parent, changed(parent / "protocol/record.json"))


@pytest.mark.parametrize("replay_complete", [False, True])
def test_future_resource_recovery_uses_latest_prefix_or_completed_replay_not_initial121(
    real_initial, tmp_path, monkeypatch, replay_complete
):
    """Actual frontier machinery; only temporary process/resource plumbing is mocked."""
    parent = tmp_path / "signal_checkpoint_recovery_01"
    target = parent / "attempts/attempt0002"
    directory = parent / subject.SOURCE_CONTEXT_RELATIVE
    context_path = directory / "context/record.json"
    original_checked, original_read = subject.checked, subject.read_ref
    original_entry, original_file_ref = subject.entry, subject.file_ref
    prior = copy.deepcopy(real_initial.value)
    prior["new_root"] = str(parent)
    prior_item = prior["context_inheritances"][0]
    prior_item["new_context_directory"] = str(directory)
    prior_item["immediate_parent_context_directory"] = str(directory)
    for stage, binding in prior_item["stage_bindings"].items():
        if binding["protocol_scope"] == "current":
            binding["directory"] = str(directory / stage)
    context = subject.read_ref(prior_item["original_context"])

    def ref(path):
        path = Path(path)
        return dict(path=str(path)) if path.is_relative_to(tmp_path) else original_entry(path)

    def file_reference(path):
        path = Path(path)
        return dict(path=str(path)) if path.is_relative_to(tmp_path) else original_file_ref(path)

    protocol_ref = ref(parent / "protocol/record.json")
    protocol = dict(
        id="future-resource-attempt",
        schema=subject.PROTOCOL_SCHEMA,
        output_root=str(parent),
        supervision_root=str(parent),
        inheritance=ref(parent / "inheritance/record.json"),
    )
    progress = original_checked(subject.SOURCE_ROOT / "actual_final_progress/record.json")
    interrupted_stage = "distribution" if replay_complete else "replay_R3"
    records = {
        parent / "protocol/record.json": protocol,
        parent / "inheritance/record.json": prior,
        parent / "actual_final_progress/record.json": progress,
        parent / "queue/status.json": dict(global_external_resource_wait_seconds=118000.5),
        context_path: dict(schema=subject.ALIAS_SCHEMA),
    }
    replay_root = directory / "replay_R3"
    for stage in {"replay_R3", interrupted_stage}:
        owner = dict(
            protocol_id=protocol["id"],
            context_id=context["id"],
            stage=stage,
            pid=123,
            birth="MOCK",
            at="2026-10-17T12:00:00+00:00",
        )
        records[directory / stage / "launch/record.json"] = owner
        records[directory / stage / "exit/record.json"] = dict(
            owner,
            returncode=0 if replay_complete and stage == "replay_R3" else 1,
            stop_requested=not (replay_complete and stage == "replay_R3"),
        )
    if replay_complete:
        records[replay_root / "result/record.json"] = dict(
            response_count=431, context_id=context["id"], stage="replay_R3"
        )
    else:
        new_checkpoint = original_checked(
            subject.SOURCE_ROOT / subject.SOURCE_CHECKPOINT_RELATIVE / "record.json"
        )
        new_checkpoint.update(id="actual-later-prefix160", cursor=160)
        records[replay_root / "checkpoints/response000160/record.json"] = new_checkpoint
    for path in records:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{}")

    def checked(path):
        path = Path(path)
        return copy.deepcopy(records[path]) if path in records else original_checked(path)

    def read(reference):
        path = Path(reference["path"])
        return copy.deepcopy(records[path]) if path in records else original_read(reference)

    def stage_binding(source, owner, ctx, stage, plan=None, *, protocol_ref):
        if stage in (*subject.SHARDS, "virtual_point"):
            return copy.deepcopy(prior_item["stage_bindings"][stage])
        if replay_complete and stage == "replay_R3":
            return dict(
                protocol_scope="parent",
                protocol_ref=protocol_ref,
                protocol_id=protocol["id"],
                directory=str(source),
                result=ref(Path(source) / "result/record.json"),
                launch=ref(Path(source) / "launch/record.json"),
                exit=ref(Path(source) / "exit/record.json"),
            )
        return None

    monkeypatch.setattr(subject, "ROOT", parent)
    monkeypatch.setattr(subject, "entry", ref)
    monkeypatch.setattr(subject, "file_ref", file_reference)
    monkeypatch.setattr(subject, "checked", checked)
    monkeypatch.setattr(subject, "read_ref", read)
    monkeypatch.setattr(subject.previous, "read_ref", read)
    monkeypatch.setattr(subject, "inspect_stage", stage_binding)
    monkeypatch.setattr(subject.old, "_stopped", lambda value: None)
    monkeypatch.setattr(subject.old, "_file_identity", lambda path: dict(path=str(path), mock=True))
    monkeypatch.setattr(
        subject,
        "_automatic_cache",
        lambda *args: (copy.deepcopy(prior_item["task_cache_view"]), None),
    )
    monkeypatch.setattr(
        subject,
        "_charged_time",
        lambda prior_seconds, *args: dict(inherited_compute_seconds=prior_seconds + 500),
    )
    monkeypatch.setattr(
        subject,
        "validate_safe_recovery",
        lambda root: dict(
            allowed=True,
            reason="resource_failure_with_verified_exits_and_durable_boundary_consumers",
        ),
    )
    body = authority()
    body.update(
        explicit_signal_checkpoint_recovery_authorized=False,
        known_failure_recovery_authorized=False,
        automatic_attempt=True,
        parent_protocol=protocol_ref,
    )
    value = subject.inspect_parent_recovery(target, parent, authorization_body=body)
    assert value["initial_explicit_signal_recovery_exception_applied"] is False
    assert value["initial_known_failure_exception_applied"] is False
    assert value["safe_recovery_audit"]["reason"].startswith("resource_failure_")
    assert value["initial_authorized_signal_stop"]["complete_response_prefix"] == 121
    assert value["inherited_resource_wait_seconds"] == 118001
    item = value["context_inheritances"][0]
    if replay_complete:
        assert item["replay_resume"] is None
        assert item["stage_bindings"]["replay_R3"]["protocol_scope"] == "parent"
        assert item["stage_bindings"]["replay_R3"]["directory"] == str(replay_root)
    else:
        assert item["replay_resume"]["inherited_response_count"] == 160
        assert item["replay_resume"]["remaining_response_count"] == 271
        assert item["replay_resume"]["checkpoint"]["path"].endswith("response000160/record.json")
        assert item["replay_resume"]["parent_saved_prefix_replayed_again"] is False


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
    root = tmp_path / "signal_checkpoint_recovery_01"
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
        schema="v52_observed_physical_resource_failure.v1",
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
    source = root / "implementation/finqa_v52_reservation.py"
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


def test_future_unknown_sigterm_is_not_covered_by_initial_explicit_exception(recovery_pool):
    failure = recovery_pool.records[recovery_pool.directory / "failure/record.json"]
    failure.update(
        error_type="TailStopRequested",
        error="stop requested at actual committed training boundary",
        stop_evidence=dict(stop_requested=True, received_signals=[15]),
    )
    decision = subject.validate_safe_recovery(recovery_pool.root)
    assert decision["allowed"] is False
    assert (
        "controller_failure_requires_one_matching_resource_worker_not_stop_consequences"
        in decision["reason"]
    )


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
        schema="v52_pre_scientific_resource_wait.v1",
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
        gpu_admission_policy_schema="v52_empirical_shared_gpu_reserved_admission.v1",
        gpu_reservation_policy_schema="v52_adaptive_same_process_native_segment_reservation.v1",
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
        records[root / "implementation/record.json"]["sha256"]["finqa_v52_reservation.py"] = (
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
