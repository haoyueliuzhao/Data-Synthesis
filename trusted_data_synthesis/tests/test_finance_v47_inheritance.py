"""Metadata-only V47 saved-frontier tests; never load a scientific Tensor."""

import copy
import importlib
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
subject = importlib.import_module("finqa_v47_inheritance")


def authority():
    return dict(
        user_consent="用户明确恢复、固定显存占用并取消独立并发上限",
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
        known_failure_recovery_authorized=True,
        parent_failure=subject.entry(subject.PARENT_ROOT / "failure/record.json"),
    )


@pytest.fixture(scope="module")
def real_frontier(tmp_path_factory):
    target = tmp_path_factory.mktemp("v47_metadata") / "fixed_gpu_reservation_01"
    original = Path.read_bytes
    tensor_attempts = []

    def metadata_only(path):
        if path.suffix == ".pt":
            tensor_attempts.append(str(path))
            raise AssertionError("scientific Tensor bytes must not be read")
        return original(path)

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(subject, "ROOT", target)
        patch.setattr(Path, "read_bytes", metadata_only)
        value = subject.inspect_initial_recovery(
            target, subject.PARENT_ROOT, authorization_body=authority()
        )
    assert not tensor_attempts
    assert not target.exists(), "preview must not publish a formal or mock episode"
    return SimpleNamespace(target=target, value=value)


def test_actual_three_model_frontier_and_feedback_dose_are_preserved(real_frontier):
    value = real_frontier.value
    assert value["schema"] == subject.SCHEMA
    assert (value["remaining_optimizer_updates"], value["remaining_outer_updates"]) == (1171, 3)
    assert len(value["completed_evaluations"]) == 6
    budget = value["remaining_scientific_budget"]
    assert budget["remaining_endpoint_answers"] == 3441
    assert budget["pending_sealed_feedback_episodes"] == 1400
    assert budget["future_first_sampling_feedback_episodes"] == 700
    assert budget["already_generated_first_sampling_feedback_episodes"] == 7700
    assert value["max_gpu_workers"] is None
    assert value["independent_total_worker_limit"] is None
    assert value["effective_device_capacity"] == 8 and value["max_workers_per_gpu"] == 1


def test_observed_251_is_not_mislabelled_as_a_saved_response_prefix(real_frontier):
    rows = {
        (x["seed"], x["arm"], x["step"]): x for x in real_frontier.value["context_inheritances"]
    }
    c = rows[(389, "C-only", 1192)]["replay_resume"]
    f = rows[(389, "Full", 894)]["replay_resume"]
    assert (
        c["inherited_response_count"],
        c["observed_response_count"],
        c["remaining_response_count"],
    ) == (240, 251, 179)
    assert c["observed_unpersisted_response_count"] == 11
    assert c["parent_saved_prefix_replayed_again"] is False
    assert c["unpersisted_observed_responses_must_be_recomputed_in_original_order"] is True
    assert (f["inherited_response_count"], f["remaining_response_count"]) == (133, 407)
    assert f["observed_unpersisted_response_count"] == 0
    assert real_frontier.value["zero_additional_replay_claimed"] is False
    for row in rows.values():
        assert all(
            row["stage_bindings"][stage]["protocol_scope"] == "parent"
            for stage in (*subject.SHARDS, "virtual_point")
        )
        assert row["stage_bindings"]["replay_R3"]["protocol_scope"] == "current"


def test_full251_uses_sft1213_without_repeating_committed_outer1192(real_frontier):
    value = real_frontier.value
    checkpoints = {(x["seed"], x["arm"]): x for x in value["latest_checkpoints"]}
    assert checkpoints[(251, "Full")]["step"] == 1213
    superseded = value["superseded_interrupted_training_contexts"]
    assert len(superseded) == 1
    assert superseded[0]["actual_checkpoint"] == checkpoints[(251, "Full")]["reference"]
    assert all(row["seed"] != 251 for row in value["context_inheritances"])
    assert value["previously_committed_Full251_outer1192_repeated"] is False
    assert value["Full251_actual_training_restart_step"] == 1213


def test_old_unsafe_automatic_refusal_remains_unsafe_without_new_initial_authority(real_frontier):
    old_audit = subject.validate_safe_recovery(subject.PARENT_ROOT)
    assert old_audit["allowed"] is False
    audit = real_frontier.value["safe_recovery_audit"]
    assert audit["allowed"] is True and audit["previous_automatic_recovery_allowed"] is False
    assert audit["old_unsafe_failure_relabelled"] is False
    decision = subject.read_ref(audit["previous_unsafe_decision"])
    assert decision["allowed"] is False
    assert "unsupported_nonresource_failure_requires_user" in decision["reason"]


@pytest.mark.parametrize(
    "key,value",
    [
        ("known_failure_recovery_authorized", False),
        ("parent_failure", {"path": "wrong", "sha256": "wrong"}),
    ],
)
def test_initial_exception_requires_fresh_specific_user_authority(key, value):
    body = authority()
    body[key] = value
    with pytest.raises(ValueError, match="explicit known V45"):
        subject._initial_failure_audit(subject.PARENT_ROOT, body)


@pytest.mark.parametrize(
    "key,value",
    [
        ("total_worker_limit_removed", False),
        ("independent_total_worker_limit", 5),
        ("max_gpu_workers", 5),
        ("max_workers_per_gpu", 2),
        ("effective_device_capacity", 9),
        ("unknown_feedback_retry_allowed", True),
        ("fixed_gpu_reservation_authorized", False),
    ],
)
def test_authority_does_not_reintroduce_five_cap_or_expand_other_permissions(key, value):
    body = authority()
    body[key] = value
    with pytest.raises(ValueError, match="authority required"):
        subject._authorization(subject.ROOT, body=body)


@pytest.mark.parametrize("mutation", ["error", "context", "manual_stop", "physical_gate"])
def test_initial_exception_does_not_generalize_to_unknown_or_numeric_failures(
    monkeypatch, mutation
):
    original = subject.checked

    def checked(path):
        result = original(path)
        text = str(path)
        if mutation == "manual_stop" and text.endswith(
            "supervisor/attempt0001/actual_exit/record.json"
        ):
            result = copy.deepcopy(result)
            result["manual_stop_requested"] = True
        if text.endswith("seed389/c_only/step1192_outer/replay_R3/failure/record.json"):
            result = copy.deepcopy(result)
            if mutation == "error":
                result["error"] = "unknown provider request outcome"
            elif mutation == "context":
                result["context_id"] = "wrong-point"
            elif mutation == "physical_gate":
                result["resources"]["observations"][0]["free_pass"] = False
        return result

    monkeypatch.setattr(subject, "checked", checked)
    with pytest.raises(ValueError):
        subject._initial_failure_audit(subject.PARENT_ROOT, authority())


@pytest.mark.parametrize("field", ["variant", "source_hash", "resident_budget"])
def test_replay_checkpoint_backend_cannot_change_to_a_new_math_variant(field):
    saved = subject.checked(subject.R3_REFERENCE)
    binding = copy.deepcopy(saved["binding"])
    if field == "variant":
        binding["backend_identity"]["variant"] = "R2"
    elif field == "source_hash":
        binding["backend_identity"]["source_binding"]["sources"][
            "finqa_v33_activation_residency.py"
        ] = "changed"
    else:
        binding["backend_identity"]["source_binding"]["activation_resident_budget_bytes"] = (
            8 * 1024**3
        )
    with pytest.raises(ValueError, match="mathematical backend changed"):
        subject._verify_replay_backend(binding, dict(id=binding["execution_profile_id"]))


def test_alias_publication_retains_original_stage_owners_and_resume_binding(
    real_frontier, monkeypatch
):
    root, value = real_frontier.target, copy.deepcopy(real_frontier.value)
    monkeypatch.setattr(subject, "ROOT", root)
    monkeypatch.setattr(subject, "inspect_parent_recovery", lambda *args, **kwargs: value)
    original = Path.read_bytes

    def metadata_only(path):
        assert path.suffix != ".pt"
        return original(path)

    monkeypatch.setattr(Path, "read_bytes", metadata_only)
    sealed = subject.initialize_parent_recovery(root, subject.PARENT_ROOT)
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
        assert subject.feedback_resume_binding(directory, plan) is None
        assert subject.checked(directory / "context/record.json")["schema"] == subject.ALIAS_SCHEMA


@pytest.mark.parametrize("next_attempt", ["attempt0003", "attempt2", "elsewhere"])
def test_future_automatic_attempts_remain_fresh_and_sequential(tmp_path, monkeypatch, next_attempt):
    supervision = tmp_path / "fixed_gpu_reservation_01"
    protocol = dict(supervision_root=str(supervision))
    monkeypatch.setattr(
        subject, "validate_safe_recovery", lambda root: dict(allowed=True, reason="CPU")
    )
    monkeypatch.setattr(subject, "checked", lambda path: protocol)
    with pytest.raises(ValueError, match="automatic attempt"):
        subject.inspect_automatic_recovery(
            supervision / "attempts" / next_attempt, supervision, authorization_body=authority()
        )


def test_future_plain_valueerror_is_not_automatically_the_initial_exception(tmp_path, monkeypatch):
    root = tmp_path / "fixed_gpu_reservation_01"
    monkeypatch.setattr(subject, "ROOT", root)
    directory = root / "contexts/seed389/c_only/step1192_outer/replay_R3"
    records = {
        root / "protocol/record.json": dict(
            schema=subject.PROTOCOL_SCHEMA,
            output_root=str(root),
            supervision_root=str(root),
            id="p",
        ),
        root / "queue/status.json": dict(active_children=[], phase="STOPPED_FAILURE_NO_RETRY"),
        root / "failure/record.json": dict(
            phase="STOPPED_FAILURE_NO_RETRY",
            stop_error=None,
            actual_progress_audit_error=None,
            error="worker reported failure: replay_R3",
        ),
        root / "launch_01/record.json": dict(pid=1, birth="CPU"),
        root / "actual_final_progress/record.json": dict(
            endpoint_scores_or_answers_read=False, original_state_or_feedback_modified=False
        ),
        directory / "launch/record.json": dict(
            protocol_id="p", context_id="c", stage="replay_R3", pid=2, birth="CPU"
        ),
        directory / "exit/record.json": dict(
            protocol_id="p", context_id="c", stage="replay_R3", returncode=1, stop_requested=True
        ),
        directory / "failure/record.json": dict(
            protocol_id="p",
            context_id="c",
            stage="replay_R3",
            error_type="ValueError",
            error="insufficient free memory for R3 KV/non-KV residency plus reserve",
        ),
    }
    for path, value in records.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value))
    monkeypatch.setattr(subject, "checked", lambda path: copy.deepcopy(records[Path(path)]))
    monkeypatch.setattr(subject, "entry", lambda path: dict(path=str(path)))
    monkeypatch.setattr(subject, "file_ref", lambda path: dict(path=str(path)))
    monkeypatch.setattr(
        subject, "read_ref", lambda reference: copy.deepcopy(records[Path(reference["path"])])
    )
    monkeypatch.setattr(subject.old, "_stopped", lambda launch: None)
    result = subject.validate_safe_recovery(root)
    assert result["allowed"] is False
    assert "unsupported_nonresource_failure" in result["reason"]


def capacity_assessment(allocated=30, reserved=36, free=3, total=80, kv=1, peak=72):
    # This producer is pure integer arithmetic; importing it does not import Torch.
    producer = importlib.import_module("finqa_v47_reservation")
    gib = 1024**3
    value = producer.assess_r3_capacity(
        *(int(v * gib) for v in (allocated, reserved, free, total, kv))
    )
    value["peak_allocated_bytes"] = int(peak * gib)
    value["lifetime_allocated_pass"] = peak <= 76
    if peak > 76:
        value["recoverable_when_capacity_changes"] = False
        value["retry_capacity_condition"]["recoverable_when_capacity_changes"] = False
    return value


def test_typed_capacity_requires_real_improvement_beyond_own_context_reclaim():
    condition = subject._capacity_assessment(capacity_assessment())
    gib = 1024**3
    assert condition["required_dispatch_free_bytes"] == 56 * gib
    assert condition["failed_available_capacity_bytes"] == 39 * gib
    assert condition["self_context_reclaim_allowance_bytes"] == 3 * gib
    assert condition["minimum_capacity_increase_bytes"] == 4 * gib
    assert condition["recoverable_when_capacity_changes"] is True


@pytest.mark.parametrize(
    "overrides",
    [
        dict(allocated=60, reserved=62),
        dict(kv=5),
        dict(reserved=76),
        dict(peak=77),
    ],
)
def test_unrepairable_capacity_or_fixed_headroom_does_not_authorize_cold_retries(overrides):
    condition = subject._capacity_assessment(capacity_assessment(**overrides))
    assert condition["recoverable_when_capacity_changes"] is False


@pytest.mark.parametrize(
    "mutation", ["one_gib_growth", "raw_required", "fake_free_failure", "bool_bytes"]
)
def test_typed_capacity_arithmetic_cannot_be_forged(mutation):
    value = capacity_assessment()
    if mutation == "one_gib_growth":
        value["retry_capacity_condition"]["minimum_capacity_increase_bytes"] = 1024**3
    elif mutation == "raw_required":
        value["raw_required_free_bytes"] = 0
    elif mutation == "fake_free_failure":
        value["physical_free_pass"] = False  # Actual free is 3GiB, above the 2GiB gate.
    else:
        value["allocated_bytes"] = True
    with pytest.raises(ValueError, match="typed R3"):
        subject._capacity_assessment(value)


def test_capacity_proof_must_demonstrate_a_real_failed_predicate():
    with pytest.raises(ValueError, match="actual failed predicate"):
        subject._capacity_assessment(capacity_assessment(reserved=60, free=8))


@pytest.fixture
def typed_failure(tmp_path, monkeypatch):
    root = tmp_path / "fixed_gpu_reservation_01"
    directory = root / "contexts/seed389/c_only/step1192_outer/replay_R3"
    context_directory = subject.PARENT_ROOT / "contexts/seed389/c_only/step1192_outer"
    context = subject.checked(context_directory / "context/record.json")
    original = subject.checked(subject.R3_REFERENCE)
    checkpoint = subject.entry(subject.R3_REFERENCE)
    producer = root / "implementation/finqa_v47_reservation.py"
    producer.parent.mkdir(parents=True)
    producer.write_text("# CPU-only frozen producer fixture\n")
    implementation = subject.publish(
        producer.parent / "record.json",
        dict(
            sha256={producer.name: subject.old.sha(producer)},
        ),
    )
    gpu_uuid = "GPU-f813ce38-39d7-ab21-f72b-55f87284eaa5"
    protocol = dict(
        id="CPU_V47_PROTOCOL",
        output_root=str(root),
        implementation_id=implementation["id"],
        allowed_gpu_indices=[0],
        gpu_uuids={"0": gpu_uuid},
        gpu_reservation_policy={"CPU": True},
    )
    launch = dict(
        protocol_id=protocol["id"],
        context_id=context["id"],
        stage="replay_R3",
        gpu_index=0,
        gpu_uuid=gpu_uuid,
        pid=123,
        birth="CPU_BIRTH",
    )
    stopped = dict(
        **launch,
        error_type="R3CapacityError",
        API_calls=0,
        original_mathematical_functions_unchanged=True,
    )
    subject.publish(
        directory / "inherited_prefix/record.json",
        dict(
            parent_checkpoint=checkpoint,
            inherited_response_count=240,
        ),
    )
    subject.publish(
        directory / "checkpoints/progress/status.json",
        dict(
            completed_responses=251,
            restored_completed_responses=240,
            total_responses=419,
        ),
    )
    subject.publish(
        directory / "reservation/admission/record.json",
        dict(
            **launch,
            before_CPU_state_and_model_load=True,
            scientific_model_calls=0,
            cuda_initialized=True,
            policy=protocol["gpu_reservation_policy"],
        ),
    )
    assessment = capacity_assessment()
    source_binding = original["binding"]["backend_identity"]["source_binding"]
    body = dict(
        **launch,
        schema="v47_r3_internal_capacity_failure.v1",
        error_type="R3CapacityError",
        before_scientific_response=True,
        failed_response_forward_calls=0,
        original_R3_predicates_not_bypassed=True,
        successful_response_calls_this_worker=11,
        latest_actual_checkpoint_ref=checkpoint,
        latest_actual_checkpoint_cursor=240,
        backend_source_binding=source_binding,
        backend_source_binding_digest=subject.digest(source_binding),
        reservation_admission=subject.entry(directory / "reservation/admission/record.json"),
        assessment=assessment,
        recoverable_when_capacity_changes=True,
        retry_capacity_condition=assessment["retry_capacity_condition"],
    )
    monkeypatch.setattr(subject, "resolve_origin_context", lambda path, plan: context_directory)
    monkeypatch.setattr(
        subject, "stage_directory", lambda path, plan, stage: context_directory / stage
    )
    monkeypatch.setattr(
        subject, "inherited_context", lambda *args: {"replay_resume": {"cursor": 240}}
    )
    return SimpleNamespace(**locals())


def test_typed_same_worker_proof_preserves_original_math_and_real_saved_prefix(typed_failure):
    f = typed_failure
    subject.publish(f.directory / "reservation/r3_capacity_failure/record.json", f.body)
    result = subject._verified_r3_capacity_failure(f.directory, f.protocol, f.launch, f.stopped)
    assert result["recoverable"] is True
    assert result["condition"] == f.assessment["retry_capacity_condition"]
    assert f.checkpoint in result["evidence_refs"]


@pytest.mark.parametrize(
    "field,value",
    [
        ("pid", 999),
        ("before_scientific_response", False),
        ("failed_response_forward_calls", 1),
        ("latest_actual_checkpoint_cursor", 251),
        ("successful_response_calls_this_worker", 12),
        ("backend_source_binding_digest", "wrong"),
    ],
)
def test_typed_resource_error_cannot_bypass_identity_math_or_durable_cursor(
    typed_failure, field, value
):
    f = typed_failure
    f.body[field] = value
    subject.publish(f.directory / "reservation/r3_capacity_failure/record.json", f.body)
    with pytest.raises(ValueError):
        subject._verified_r3_capacity_failure(f.directory, f.protocol, f.launch, f.stopped)
