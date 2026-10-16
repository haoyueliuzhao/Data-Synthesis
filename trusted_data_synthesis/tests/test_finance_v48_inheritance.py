"""CPU-only V48 inheritance and typed recovery regressions."""

import copy
import importlib
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
subject = importlib.import_module("finqa_v48_inheritance")
GIB = 1024**3


def authority():
    return dict(
        user_consent="修复问题，自动恢复应当覆盖此类问题，或者此类问题不应该阻塞任务池的派发",
        time_limits_removed=True,
        automatic_recovery_authorized=True,
        unknown_feedback_retry_allowed=False,
        total_worker_limit_removed=True,
        independent_total_worker_limit=None,
        max_gpu_workers=None,
        max_workers_per_gpu=1,
        effective_device_capacity=8,
        host_ram_runtime_hard_gates_unchanged=True,
        fixed_gpu_reservation_authorized=True,
        pre_model_resource_recovery_authorized=True,
        parent_failure=subject.entry(subject.RECOVERY_PARENT_ROOT / "failure/record.json"),
        parent_closed_episode=subject.entry(subject.STOPPED_ROOT / "closeout_01/record.json"),
        parent_supervisor_closeout=subject.entry(
            subject.STOPPED_ROOT / "supervisor/closeout/record.json"
        ),
    )


@pytest.fixture(scope="module")
def real_frontier(tmp_path_factory):
    target = tmp_path_factory.mktemp("v48_metadata") / "new_root"
    original = Path.read_bytes

    def metadata_only(path):
        assert path.suffix != ".pt", "inheritance preview must not load a Tensor"
        return original(path)

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(subject, "ROOT", target)
        patch.setattr(Path, "read_bytes", metadata_only)
        value = subject.inspect_initial_recovery(
            target, subject.RECOVERY_PARENT_ROOT, authorization_body=authority()
        )
    assert not target.exists(), "preview must not publish an episode"
    return SimpleNamespace(target=target, value=value)


def test_actual_frontier_preserves_committed_training_and_complete_feedback(real_frontier):
    value = real_frontier.value
    assert value["schema"] == subject.SCHEMA
    assert (value["remaining_optimizer_updates"], value["remaining_outer_updates"]) == (1147, 3)
    assert len(value["completed_evaluations"]) == 6
    budget = value["remaining_scientific_budget"]
    assert budget["remaining_endpoint_answers"] == 3441
    assert budget["pending_sealed_feedback_episodes"] == 1400
    assert budget["future_first_sampling_feedback_episodes"] == 700
    assert budget["remaining_new_feedback_episodes"] == 700
    assert budget["already_generated_first_sampling_feedback_episodes"] == 7700
    assert budget["reserved_partial_feedback_episodes"] == 0
    checkpoints = {(x["seed"], x["arm"]): x for x in value["latest_checkpoints"]}
    assert checkpoints[(251, "Full")]["step"] == 1237
    assert value["Full251_actual_training_restart_step"] == 1237
    assert value["previously_committed_Full251_outer1192_repeated"] is False
    assert all(row["seed"] != 251 for row in value["context_inheritances"])
    assert value["max_gpu_workers"] is value["independent_total_worker_limit"] is None
    assert value["effective_device_capacity"] == 8 and value["max_workers_per_gpu"] == 1


def test_latest_saved_prefixes_are_not_historical_observed_counts(real_frontier):
    rows = {(x["seed"], x["arm"]): x for x in real_frontier.value["context_inheritances"]}
    for coordinate, cursor, total in (((389, "C-only"), 240, 419), ((389, "Full"), 133, 540)):
        item = rows[coordinate]
        replay = item["replay_resume"]
        assert replay["inherited_response_count"] == replay["observed_response_count"] == cursor
        assert replay["total_response_count"] == total
        assert replay["remaining_response_count"] == total - cursor
        assert replay["observed_unpersisted_response_count"] == 0
        assert replay["parent_saved_prefix_replayed_again"] is False
        assert Path(replay["checkpoint"]["path"]).is_relative_to(subject.RECOVERY_PARENT_ROOT)
        assert all(
            item["stage_bindings"][key]["protocol_scope"] == "parent"
            for key in (*subject.SHARDS, "virtual_point")
        )
        assert item["stage_bindings"]["replay_R3"]["protocol_scope"] == "current"
    assert real_frontier.value["historical_max_observed_C_only389_response_count"] == 251
    assert real_frontier.value["C_only389_observed_but_unpersisted_responses"] == 0


def test_no_deadlines_but_all_parent_elapsed_time_is_carried(real_frontier):
    value = real_frontier.value
    assert value["parent_root"] == str(subject.RECOVERY_PARENT_ROOT)
    assert value["inherited_resource_wait_seconds"] == 105003
    assert value["resource_wait_budget_seconds"] is value["outer_compute_budget_seconds"] is None
    assert value["original_accounting_reset"] is False
    rows = {(row["seed"], row["arm"]): row for row in value["context_inheritances"]}
    assert rows[(389, "C-only")]["earlier_inherited_compute_seconds"] == 42784
    assert rows[(389, "C-only")]["inherited_compute_seconds"] == 42894
    assert rows[(389, "Full")]["earlier_inherited_compute_seconds"] == 36192
    assert rows[(389, "Full")]["inherited_compute_seconds"] == 36303
    assert all(row["phase_deadlines_epoch"] == {} for row in rows.values())


def test_initial_exception_preserves_unsafe_stop_and_does_not_invent_free_bytes(real_frontier):
    audit = real_frontier.value["safe_recovery_audit"]
    assert audit["allowed"] is True and audit["previous_automatic_recovery_allowed"] is False
    assert audit["historical_failure_reclassified"] is False
    assert audit["unrecorded_physical_free_bytes"] is None
    assert audit["historical_observation_missing_not_fabricated"] is True
    assert subject.read_ref(audit["previous_unsafe_decision"])["allowed"] is False
    assert subject.validate_safe_recovery(subject.RECOVERY_PARENT_ROOT)["allowed"] is False
    assert real_frontier.value["known_failure_exception_authorizes_future_unknown_errors"] is False


@pytest.mark.parametrize(
    "key,value",
    [
        ("pre_model_resource_recovery_authorized", False),
        ("parent_failure", {}),
        ("parent_closed_episode", {}),
        ("parent_supervisor_closeout", {}),
    ],
)
def test_initial_exception_requires_exact_new_authority(key, value):
    body = authority()
    body[key] = value
    with pytest.raises(ValueError, match="new explicit exact stopped"):
        subject._initial_failure_audit(subject.RECOVERY_PARENT_ROOT, body)


@pytest.mark.parametrize("mutation", ["error", "context", "resources", "stop", "progress"])
def test_initial_exception_rejects_changed_failure_or_science(monkeypatch, mutation):
    original = subject.checked

    def checked(path):
        result = original(path)
        text = str(path)
        if text.endswith("seed251/full/step1237_train/train/failure/record.json"):
            result = copy.deepcopy(result)
            if mutation == "error":
                result["error"] = "unknown provider outcome"
            elif mutation == "context":
                result["context_id"] = "wrong-point"
            elif mutation == "resources":
                result["resources"] = dict(free_bytes=1)
            elif mutation == "stop":
                result["stop_evidence"]["stop_requested"] = True
        if mutation == "progress" and text.endswith("actual_final_progress/record.json"):
            result = copy.deepcopy(result)
            result["remaining_physical_updates"] -= 1
        return result

    monkeypatch.setattr(subject, "checked", checked)
    with pytest.raises(ValueError):
        subject._initial_failure_audit(subject.RECOVERY_PARENT_ROOT, authority())


def test_alias_publication_keeps_original_point_and_stage_owners(real_frontier, monkeypatch):
    root, value = real_frontier.target, copy.deepcopy(real_frontier.value)
    monkeypatch.setattr(subject, "inspect_parent_recovery", lambda *args, **kwargs: value)
    sealed = subject.initialize_parent_recovery(root, subject.RECOVERY_PARENT_ROOT)
    plan = dict(output_root=str(root), inheritance=subject.entry(root / "inheritance/record.json"))
    for item in sealed["context_inheritances"]:
        directory = Path(item["new_context_directory"])
        assert subject.resolve_origin_context(directory, plan) == Path(
            item["origin_context_directory"]
        )
        assert subject.stage_directory(directory, plan, "virtual_point") == Path(
            item["stage_bindings"]["virtual_point"]["directory"]
        )
        assert subject.stage_directory(directory, plan, "replay_R3") == directory / "replay_R3"
        assert subject.replay_resume_binding(directory, plan) == item["replay_resume"]
        assert subject.checked(directory / "context/record.json")["schema"] == subject.ALIAS_SCHEMA


@pytest.mark.parametrize(
    "key,value",
    [
        ("max_gpu_workers", 5),
        ("independent_total_worker_limit", 5),
        ("max_workers_per_gpu", 2),
        ("unknown_feedback_retry_allowed", True),
        ("host_ram_runtime_hard_gates_unchanged", False),
    ],
)
def test_common_authority_retains_scope_and_runtime_gates(key, value):
    body = authority()
    body[key] = value
    with pytest.raises(ValueError, match="authority required"):
        subject._authorization(subject.ROOT, body=body)


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
    root = tmp_path / "resource_deferral_recovery_01"
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
        schema="v48_observed_physical_resource_failure.v1",
        error_type="ReservationPhysicalResourceError",
    )
    admission_path = directory / "reservation/admission/record.json"
    proof["reservation_admission"] = dict(path=str(admission_path))
    protocol = dict(
        schema=subject.PROTOCOL_SCHEMA,
        output_root=str(root),
        supervision_root=str(root),
        id="p",
        allowed_gpu_indices=list(range(8)),
        gpu_uuids={"6": "g6"},
        implementation_id="impl",
        gpu_reservation_policy=dict(schema="policy"),
    )
    source = root / "implementation/finqa_v48_reservation.py"
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
        schema="v48_pre_scientific_resource_wait.v1",
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
        gpu_admission_policy_schema="v48_empirical_shared_gpu_reserved_admission.v1",
        gpu_reservation_policy_schema="v48_adaptive_same_process_native_segment_reservation.v1",
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
        records[root / "implementation/record.json"]["sha256"]["finqa_v48_reservation.py"] = (
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
