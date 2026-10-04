"""CPU-only continuation controls; no controller, model, GPU or API is launched."""

import copy
import hashlib
import importlib
import json
import sys
import types
from pathlib import Path
from types import SimpleNamespace

import pytest

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "scripts"))
continuation = importlib.import_module("finqa_v22_eval_continuation")
EVALUATION_SOURCES = ()
GPUS = [0, 1, 2, 3, 4, 6]


def six_gpu_require(condition, message):
    if not condition:
        raise ValueError(message)


def bound(value):
    return {**value, "id": hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()}


def runtime_binding():
    raise AssertionError("mock runtime must be explicitly bound")


def bind(function, **values):
    return types.FunctionType(
        function.__code__,
        {**function.__globals__, **values},
        function.__name__,
        function.__defaults__,
        function.__closure__,
    )


def original_public_contract(assets, base):
    """Small mock of the frozen public-input and complete source guards."""
    if assets != base["public_assets"]:
        raise ValueError("public evaluation contract changed")
    current = runtime_binding()
    sources = [*EVALUATION_SOURCES, *(k for k in current if k.startswith("metric_vendor/"))]
    if any(current[k] != base["runtime_binding"].get(k) for k in sources):
        raise ValueError("public/scorer source changed")
    return {"evaluation_source_sha256": {k: current[k] for k in sources}, "tasks": ["dev"]}


@pytest.fixture
def contract_fixture():
    compat = continuation.provider_compat
    provider = PROJECT / "src/trusted_synthesis/finance_research/providers.py"
    current = {
        "providers.py": compat.CURRENT_PROVIDERS_SHA256,
        "harness.py": "same-harness",
        "metric_vendor/scorer.py": "same-scorer",
    }
    assets = {"snapshot": "original", "config": {"temperature": 0}, "tasks": ["dev"]}
    base = {
        "runtime_binding": {**current, "providers.py": compat.BASE_PROVIDERS_SHA256},
        "public_assets": copy.deepcopy(assets),
    }
    sources = ("harness.py", "providers.py")
    original = bind(
        original_public_contract, runtime_binding=lambda: current.copy(), EVALUATION_SOURCES=sources
    )
    final = SimpleNamespace(
        __file__=str(provider.with_name("v9_final_evaluation.py")),
        public_evaluation_contract=original,
        EVALUATION_SOURCES=sources,
        runtime_binding=lambda: current.copy(),
    )
    proof = compat.prove_provider_compatibility(
        provider.read_bytes(),
        base_sha256=compat.BASE_PROVIDERS_SHA256,
        current_sha256=compat.CURRENT_PROVIDERS_SHA256,
    )
    certificate = {
        "id": "immutable-certificate",
        "actual_runtime_binding": current.copy(),
        "actual_evaluation_sources": current.copy(),
        "provider_proof": proof,
        "API_calls": 0,
    }
    ref = {"path": "certificate/record.json", "sha256": "certificate-hash"}
    return SimpleNamespace(
        rt=SimpleNamespace(final=final, bind=bind),
        current=current,
        assets=assets,
        base=base,
        certificate=certificate,
        ref=ref,
    )


def test_contract_only_admits_exact_provider_edit_and_keeps_actual_sources(contract_fixture):
    f = contract_fixture
    original_sources = f.rt.final.EVALUATION_SOURCES
    with pytest.raises(ValueError, match="source changed"):
        f.rt.final.public_evaluation_contract(f.assets, f.base)
    compatible = continuation.make_public_contract(f.rt, f.certificate, f.ref)
    result = compatible(f.assets, f.base)
    assert result["evaluation_source_sha256"] == f.current
    assert (
        result["evaluation_source_sha256"]["providers.py"]
        != f.base["runtime_binding"]["providers.py"]
    )
    evidence = result["Base_source_compatibility"]
    assert evidence["certificate"] == f.certificate
    assert evidence["certificate_ref"] == f.ref
    assert evidence["original_public_contract_code_reused"] is True
    assert evidence["all_other_public_input_and_scorer_checks_unchanged"] is True
    assert f.rt.final.EVALUATION_SOURCES == original_sources
    # Binding must not weaken the original function/module for other callers.
    with pytest.raises(ValueError, match="source changed"):
        f.rt.final.public_evaluation_contract(f.assets, f.base)


@pytest.mark.parametrize("source", ("harness.py", "metric_vendor/scorer.py"))
def test_contract_rejects_other_sources_even_if_certificate_is_replaced(contract_fixture, source):
    f = contract_fixture
    f.current[source] = "changed"
    f.certificate["actual_runtime_binding"] = f.current.copy()
    f.certificate["actual_evaluation_sources"] = f.current.copy()
    with pytest.raises(ValueError, match="public/scorer source changed"):
        continuation.make_public_contract(f.rt, f.certificate, f.ref)(f.assets, f.base)


@pytest.mark.parametrize(
    "field,value",
    (("snapshot", "different"), ("config", {"temperature": 1}), ("tasks", ["subset"])),
)
def test_contract_rejects_changed_public_inputs(contract_fixture, field, value):
    f = contract_fixture
    f.assets[field] = value
    with pytest.raises(ValueError, match="public evaluation contract changed"):
        continuation.make_public_contract(f.rt, f.certificate, f.ref)(f.assets, f.base)


@pytest.mark.parametrize(
    "mutation,error",
    (
        ("runtime", "frozen runtime changed"),
        ("proof", "provider compatibility proof changed"),
        ("actual_sources", "report actual evaluation sources"),
        ("base_provider", "exact registered Base/V18"),
    ),
)
def test_contract_rejects_certificate_or_provider_mismatch(contract_fixture, mutation, error):
    f = contract_fixture
    if mutation == "runtime":
        f.current["harness.py"] = "changed"
    elif mutation == "proof":
        f.certificate["provider_proof"] = {"unproved": True}
    elif mutation == "actual_sources":
        f.certificate["actual_evaluation_sources"]["providers.py"] = f.base["runtime_binding"][
            "providers.py"
        ]
    else:
        f.base["runtime_binding"]["providers.py"] = "other-base"
    with pytest.raises(ValueError, match=error):
        continuation.make_public_contract(f.rt, f.certificate, f.ref)(f.assets, f.base)


def test_compatibility_certificate_binds_provider_as_source_bytes_not_json_identity(tmp_path):
    compat = continuation.provider_compat
    provider = PROJECT / "src/trusted_synthesis/finance_research/providers.py"
    sources = ("providers.py", *(f"source{index}.py" for index in range(8)))
    current = {key: "unchanged" for key in sources}
    current.update({f"metric_vendor/source{index}.py": "unchanged" for index in range(4)})
    current["providers.py"] = compat.CURRENT_PROVIDERS_SHA256
    base = {"runtime_binding": {**current, "providers.py": compat.BASE_PROVIDERS_SHA256}}
    rt = mock_runtime()
    entries = []

    def json_entry(path):
        assert path.suffix == ".json", "source bytes must not be parsed as bound JSON"
        entries.append(path)
        return {"path": str(path), "id": "json-artifact"}

    rt.entry = json_entry
    rt.final = SimpleNamespace(
        __file__=str(provider.with_name("v9_final_evaluation.py")),
        base=SimpleNamespace(OUTPUT=tmp_path / "base"),
        read_bound=lambda path: base,
        runtime_binding=lambda: current.copy(),
        EVALUATION_SOURCES=sources,
        file_binding=lambda path: dict(
            path=str(path), sha256=hashlib.sha256(path.read_bytes()).hexdigest()
        ),
    )
    certificate, _ = continuation.compatibility_certificate(rt, tmp_path)
    assert certificate["actual_provider_source"] == {
        "path": str(provider),
        "sha256": compat.CURRENT_PROVIDERS_SHA256,
    }
    assert "id" not in certificate["actual_provider_source"]
    assert provider not in entries
    assert len(certificate["actual_evaluation_sources"]) == 13


def training_jobs():
    return [
        dict(key=f"arm-{seed}-{arm}", module="v16_arm_training", args=["resume-arm"])
        for seed in (11, 29, 47)
        for arm in ("static", "c_only", "full", "manual_plus", "manual_minus")
    ]


def test_completed_matrix_requires_all_fifteen_unique_complete_results():
    jobs = training_jobs()
    checked = []
    continuation.require_completed_matrix(jobs, lambda j: checked.append(j["key"]) or True)
    assert len(checked) == 15
    for invalid in (jobs[:-1], [*jobs[:-1], jobs[0]], [*jobs, jobs[0]]):
        with pytest.raises(ValueError, match="all fifteen"):
            continuation.require_completed_matrix(invalid, lambda j: True)
    with pytest.raises(ValueError, match="incomplete arm"):
        continuation.require_completed_matrix(jobs, lambda j: j["key"] != "arm-47-full")


def tail_job(module="v9_final_evaluation", action="run-model", **overrides):
    return dict(key="final-seed11/static", module=module, args=[action], **overrides)


@pytest.mark.parametrize(
    "module,action",
    (
        ("v9_final_evaluation", "run-model"),
        ("v9_final_evaluation", "resume-model"),
        ("v9_mechanism_execution", "run-seed"),
        ("v9_mechanism_execution", "evaluate-point"),
    ),
)
def test_tail_whitelist_accepts_only_existing_dev_and_mechanism_commands(module, action):
    continuation.require_tail_job(tail_job(module, action))


@pytest.mark.parametrize(
    "change",
    (
        {"key": "arm-11-full"},
        {"module": "v16_arm_training"},
        {"script": Path("training.py")},
        {"module": "unknown"},
        {"args": ["resume-arm"]},
        {"args": ["register"]},
        {"args": []},
    ),
)
def test_tail_whitelist_rejects_training_scripts_and_unknown_actions(change):
    with pytest.raises(ValueError, match="must never launch training"):
        continuation.require_tail_job({**tail_job(), **change})


class FakePreviousSupervisor:
    """Records delegation without executing any source, command or subprocess."""

    def __init__(self, root, *, resume):
        self.parent_init = (root, resume)
        self.root = root / "queue"
        self.history_root = self.root / "jobs"
        self.calls, self.statuses = [], []
        self.incomplete = set()
        self.children = {}
        self.profile = training_profile()
        self.profile_ref = {"id": "original-training-profile"}
        self.workflow = {"allowed_gpu_indices": GPUS, "max_gpu_workers": 6}
        self.max_gpu_workers = 6
        self.launch_records = []

    def update(self, phase, **details):
        self.statuses.append((self.root, phase, details))

    def job_complete(self, job):
        return job["key"] not in self.incomplete

    def launch(self, job, *, gpu=None):
        six_gpu_require(gpu in GPUS and len(self.children) < len(GPUS), "six-GPU scope")
        self.calls.append(("launch", job, gpu))
        self.launch_records.append(bound(dict(execution_profile_id=self.profile["id"], gpu=gpu)))
        return "launched-mock"

    def eligible_job(self, job):
        self.calls.append(("eligible", job))
        return True

    def gpu_queue(self, jobs, allowed):
        six_gpu_require(list(allowed) == GPUS, "six-GPU scope")
        self.calls.append(("queue", jobs, allowed))
        self.update("V20_FIVE_GPU_QUEUE_RUNNING")
        return True


def mock_runtime():
    bindings = []

    def recorded_bind(function, **values):
        bindings.append((function.__name__, values))
        return bind(function, **values)

    def entry(path):
        return {"path": str(path)}

    def persist(path, value):
        path.mkdir(parents=True, exist_ok=True)
        (path / "record.json").write_text(json.dumps(value))

    return SimpleNamespace(
        previous=SimpleNamespace(Supervisor=FakePreviousSupervisor),
        bind=recorded_bind,
        bound=bound,
        entry=entry,
        persist=persist,
        checked=lambda path: json.loads(path.read_text()),
        now=lambda: "frozen-time",
        bindings=bindings,
    )


def supervisor(tmp_path, *, resume=False):
    rt = mock_runtime()
    result = continuation.create_supervisor(rt, tmp_path / "continuation", resume=resume)
    result.mock_runtime = rt
    result.continuation = {"id": "continuation-id"}
    return result


def test_new_root_and_completed_training_are_observed_without_parent_dispatch(tmp_path):
    controller = supervisor(tmp_path)
    assert controller.parent_init == (continuation.OLD_ROOT, True)
    assert controller.root == tmp_path / "continuation/queue"
    assert controller.history_root == controller.root / "jobs"
    assert controller.resume is False
    assert controller.gpu_queue(training_jobs(), continuation.GPUS)
    assert not controller.calls
    root, phase, details = controller.statuses[-1]
    assert root == controller.root and phase == "V22_TRAINING_ALREADY_COMPLETE"
    assert details["completed_arms"] == 15
    assert details["evaluation_only_continuation"] and details["no_training_launch"]
    controller.incomplete.add("arm-47-full")
    with pytest.raises(ValueError, match="incomplete arm"):
        controller.gpu_queue(training_jobs(), continuation.GPUS)
    assert not controller.calls


@pytest.mark.parametrize(
    "module,action,stage",
    (
        ("v9_final_evaluation", "run-model", "DEV_EVALUATION"),
        ("v9_mechanism_execution", "run-seed", "MECHANISM_BUILD"),
        ("v9_mechanism_execution", "evaluate-point", "MECHANISM_EVALUATION"),
    ),
)
def test_nonarm_queue_retains_eight_gpu_scope_and_stage_routes(tmp_path, module, action, stage):
    controller = supervisor(tmp_path)
    job = tail_job(module, action)
    assert controller.gpu_queue([job], continuation.GPUS)
    assert controller.calls == [("queue", [job], continuation.GPUS)]
    assert controller.stage == stage
    assert controller.statuses[-1][1] == f"V22_{stage}_RUNNING"
    assert continuation.GPUS == list(range(8))
    with pytest.raises(ValueError, match="authorized eight GPUs"):
        controller.gpu_queue([job], list(range(9)))
    assert len(controller.calls) == 1
    assert controller.eligible_job(job)
    for gpu in (5, 7):
        assert controller.launch(job, gpu=gpu) == "launched-mock"
        assert controller.calls[-1] == ("launch", job, gpu)
    assert controller.launch_records[-1]["schema"] == "v22_eight_gpu_evaluation_worker_launch.v1"
    assert (
        controller.launch_records[-1]["original_training_execution_profile"]
        == controller.profile_ref
    )
    assert controller.launch_records[-1]["evaluation_resource_profile"] == {
        "path": str(controller.continuation_root / "resource_profile/record.json")
    }
    assert controller.mock_runtime.bindings[-1][1]["GPUS"] == list(range(8))
    with pytest.raises(ValueError, match="at most eight"):
        controller.launch(job, gpu=8)
    controller.children = {str(index): {} for index in range(8)}
    with pytest.raises(ValueError, match="at most eight"):
        controller.launch(job, gpu=0)


def test_training_cannot_reach_parent_launch_or_eligibility(tmp_path):
    controller = supervisor(tmp_path)
    for job in (
        training_jobs()[0],
        {**tail_job(), "script": Path("train.py")},
        tail_job("v16_arm_training", "resume-arm"),
    ):
        for dispatch in (controller.launch, controller.eligible_job):
            with pytest.raises(ValueError, match="must never launch training"):
                dispatch(job)
    assert not controller.calls
    with pytest.raises(ValueError, match="all fifteen"):
        controller.gpu_queue([training_jobs()[0], tail_job()], continuation.GPUS)
    assert not controller.calls


def test_existing_new_queue_attempts_require_explicit_resume(tmp_path):
    (tmp_path / "continuation/queue/jobs").mkdir(parents=True)
    with pytest.raises(ValueError, match="existing evaluation attempts require resume"):
        supervisor(tmp_path)
    assert supervisor(tmp_path, resume=True).resume is True


def all_affinity():
    return {str(gpu): "0-37,76-113" if gpu < 4 else "38-75,114-151" for gpu in range(8)}


def training_profile():
    return dict(
        id="original-training-profile",
        cpu_affinity={str(g): all_affinity()[str(g)] for g in GPUS},
        minimum_free_mib=24576,
        taskset={"path": "/usr/bin/taskset", "sha256": "taskset-hash"},
        parent_execution_profile={"id": "original-V20"},
        protected_workers=[],
    )


@pytest.mark.parametrize("missing", (False, True))
def test_observed_affinity_binds_gpu5_gpu7_to_numa1_and_requires_all_cards(monkeypatch, missing):
    calls = []

    def nvidia(command, **kwargs):
        calls.append((command, kwargs))
        return "\n".join(
            f"{gpu}, 00000000:{gpu + 1:02x}:00.0" for gpu in range(7 if missing else 8)
        )

    def read_sysfs(path, *args, **kwargs):
        value = str(path)
        if value.endswith("/numa_node"):
            gpu = int(path.parent.name.split(":")[1], 16) - 1
            return "0" if gpu < 4 else "1"
        if value == "/sys/devices/system/node/node0/cpulist":
            return "0-37,76-113"
        if value == "/sys/devices/system/node/node1/cpulist":
            return "38-75,114-151"
        raise AssertionError(f"unexpected sysfs lookup {value}")

    monkeypatch.setattr(continuation.subprocess, "check_output", nvidia)
    monkeypatch.setattr(Path, "read_text", read_sysfs)
    if missing:
        with pytest.raises(ValueError, match="all eight GPUs"):
            continuation.observed_cpu_affinity()
    else:
        observed = continuation.observed_cpu_affinity()
        assert observed == all_affinity()
        assert observed["5"] == observed["7"] == "38-75,114-151"
    assert calls[0][0] == ["nvidia-smi", "--query-gpu=index,pci.bus_id", "--format=csv,noheader"]


def test_resource_profile_retains_training_identity_and_is_immutable_on_resume(
    monkeypatch, tmp_path
):
    monkeypatch.setattr(continuation, "observed_cpu_affinity", all_affinity)
    rt, old = mock_runtime(), training_profile()
    original = copy.deepcopy(old)
    record, ref = continuation.evaluation_resource_profile(rt, tmp_path, old)
    assert old == original
    assert record["id"] != old["id"]
    assert record["allowed_gpu_indices"] == list(range(8)) and record["max_gpu_workers"] == 8
    assert record["minimum_free_mib"] == 24576
    assert record["cpu_affinity"]["5"] == record["cpu_affinity"]["7"] == "38-75,114-151"
    assert record["parent_training_execution_profile"] == rt.entry(
        continuation.OLD_ROOT / "registration/record.json"
    )
    cold, cold_ref = continuation.evaluation_resource_profile(rt, tmp_path, old)
    assert (cold, cold_ref) == (record, ref)
    changed = {**record, "max_gpu_workers": 9}
    rt.persist(tmp_path / "resource_profile", changed)
    with pytest.raises(ValueError, match="evaluation resources changed"):
        continuation.evaluation_resource_profile(rt, tmp_path, old)


@pytest.mark.parametrize("mutation", ("original_affinity", "new_affinity", "headroom"))
def test_resource_profile_rejects_changed_affinity_or_headroom(monkeypatch, tmp_path, mutation):
    rt, old = mock_runtime(), training_profile()
    observed = all_affinity()
    monkeypatch.setattr(continuation, "observed_cpu_affinity", lambda: observed)
    if mutation == "original_affinity":
        observed["0"] = "different-cpus"
        match = "existing six GPU CPU affinity"
    elif mutation == "headroom":
        old["minimum_free_mib"] = 16000
        match = "original 24 GiB"
    else:
        continuation.evaluation_resource_profile(rt, tmp_path, old)
        observed["7"] = "different-cpus"
        match = "evaluation resources changed"
    with pytest.raises(ValueError, match=match):
        continuation.evaluation_resource_profile(rt, tmp_path, old)


def test_prepare_uses_new_resource_id_without_rebinding_completed_training(monkeypatch, tmp_path):
    monkeypatch.setattr(continuation, "V18", tmp_path)
    monkeypatch.setattr(continuation, "OLD_ROOT", tmp_path / "six_gpu_queue_01")
    monkeypatch.setattr(continuation, "observed_cpu_affinity", all_affinity)
    monkeypatch.setattr(continuation, "mechanism_inputs", lambda rt, launcher: ({"id": "mech"}, []))
    certificate, cert_ref = {"id": "compat"}, {"path": "compat-ref"}
    monkeypatch.setattr(
        continuation, "compatibility_certificate", lambda rt, root: (certificate, cert_ref)
    )
    controller = supervisor(tmp_path)
    rt = controller.mock_runtime
    controller.handoff = {"launcher": str(tmp_path / "training")}
    jobs = [
        {**job, "result": tmp_path / job["key"] / "result/record.json"} for job in training_jobs()
    ]
    controller.arm_jobs = lambda launcher: jobs
    old_ref, old_parent = (
        copy.deepcopy(controller.profile_ref),
        controller.profile["parent_execution_profile"],
    )
    plan = {
        "Base_source_compatibility": {"certificate": certificate, "certificate_ref": cert_ref},
        "total_models": 15,
        "total_episodes": 13245,
        "Base_rerun": False,
        "API_calls": 0,
    }
    rt.final = SimpleNamespace(checked_plan=lambda output: plan)
    rt.persist(tmp_path / "final_evaluation/registration", plan)
    continuation.prepare_evaluation(rt, controller)
    resource = rt.checked(controller.continuation_root / "resource_profile/record.json")
    assert controller.profile["id"] == resource["id"] != old_ref["id"]
    assert controller.profile_ref == old_ref
    assert controller.profile["parent_execution_profile"] == old_parent
    assert controller.max_gpu_workers == controller.workflow["max_gpu_workers"] == 8
    assert controller.workflow["allowed_gpu_indices"] == list(range(8))
    controller.launch(tail_job(), gpu=7)
    launch = controller.launch_records[-1]
    assert launch["execution_profile_id"] == resource["id"]
    assert launch["original_training_execution_profile"] == old_ref
    assert launch["continuation_id"] == controller.continuation["id"]

    # The original cold-restore logic must accept only the new evaluation ID.
    original = importlib.import_module("finqa_v19_queued_scheduler")
    monkeypatch.setattr(original, "checked", rt.checked)
    monkeypatch.setattr(original, "identity", lambda pid: "birth")
    job = tail_job()
    path = controller.history_root / job["key"] / "attempt001/launch"
    receipt = dict(
        key=job["key"],
        execution_profile_id=resource["id"],
        pid=987654321,
        process_start_time_ticks="birth",
        gpu_index=7,
    )
    rt.persist(path, receipt)
    controller.resume = True
    controller.job_complete = lambda value: False
    original.Supervisor.recover_active(controller, [job])
    assert controller.children[job["key"]]["gpu"] == 7
    controller.children.clear()
    rt.persist(path, {**receipt, "execution_profile_id": old_ref["id"]})
    with pytest.raises(ValueError, match="cold queue restore changed execution profile"):
        original.Supervisor.recover_active(controller, [job])
