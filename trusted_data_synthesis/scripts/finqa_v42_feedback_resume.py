"""Explicitly authorized one-request feedback recovery, never a cohort retry.

All 450 complete episodes and the old unknown intent remain immutable. A fresh
view executes one unresolved episode and 249 never-started episodes, before the
original complete-700 seal and first scoring path. A second attempt is rejected.
"""

from __future__ import annotations

import asyncio
import copy
import hashlib
import importlib
import json
import re
from pathlib import Path
from types import FunctionType

SCHEMA = "v42_single_unreturned_feedback_request_resume.v1"
COORDINATE = (389, "C-only", 894)
CONTEXT_ID = "fb2d04ed951f4500e4fd6f9efd5f42f860ad7a7b34fb570115c854f15ddc8e63"
POINT_ID = "f99047e7eb6575b171043f22fd534d7430a51ee635f3deef48a6903cd534ca32"
UNKNOWN_KEY = "1570f71edeaaf4b5481cf32de1b8e4b856d17c0f2bd2f8c966a7f7a113d8409f"


def require(value, message):
    if not value:
        raise ValueError(message)


def digest(value):
    return hashlib.sha256(
        json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode()
    ).hexdigest()


def read(path):
    return json.loads(Path(path).read_bytes())


def file_ref(path):
    path = Path(path).resolve()
    return dict(path=str(path), sha256=hashlib.sha256(path.read_bytes()).hexdigest())


def read_ref(reference):
    raw = Path(reference["path"]).read_bytes()
    require(
        hashlib.sha256(raw).hexdigest() == reference["sha256"], "inherited feedback bytes changed"
    )
    return raw


def inspect_partial_feedback(context_directory, *, bundle=None):
    """Read-only metadata registration, without model/private-reference loading."""
    directory = Path(context_directory).resolve()
    context = read(directory / "context/record.json")
    require(
        (context["seed"], context["arm"], context["step"]) == COORDINATE
        and context["id"] == CONTEXT_ID
        and context["feedback"]["mode"] == "first_sampling",
        "unregistered feedback coordinate",
    )
    computed = directory / "virtual_point/computed_point/payload"
    payload = read(computed / "record.json")
    require(
        payload["context_id"] == context["id"]
        and payload["phase"] == "virtual_point_values"
        and payload["actual_tensors_saved"] is True,
        "missing actual saved virtual point",
    )
    root = Path(context["feedback"]["base_root"]) / digest(POINT_ID)
    intent = read(root / "intent/record.json")
    require(
        intent["point_id"] == POINT_ID
        and intent["denominator"] == 700
        and intent["seeds"] == [11, 29]
        and len(intent["task_ids"]) == 350,
        "original 350 by 2 feedback intent changed",
    )
    require(
        not (root / "cohort_seal").exists()
        and not (root / "native_rewards").exists()
        and not (root / "native_scoring_failure").exists(),
        "already sealed or scored feedback",
    )
    inherited = [dict(relative="intent/record.json", **file_ref(root / "intent/record.json"))]
    runs, complete, unknown = [], [], None
    settled_calls = 0
    for draw, expected in ((0, 350), (1, 100)):
        base = root / f"draw{draw}"
        run = read(base / "run.json")
        require(
            run["provider"] == intent["identity"]
            and run["provider"]["point_id"] == POINT_ID
            and run["registered_denominator"] == 350
            and len(run["episode_keys"]) == 350
            and len(set(run["episode_keys"])) == 350
            and run["config"]["seed"] == (11, 29)[draw]
            and run["config"]["tier"] == "VTDO_FEEDBACK"
            and run["config"]["role"] == "feedback"
            and run["role_plan_id"] == intent["role_plan_id"]
            and run["source_manifest_sha256"] == intent["source_manifest_sha256"],
            "feedback draw registration changed",
        )
        require(
            run["id"] == digest({k: v for k, v in run.items() if k != "id"}), "run digest changed"
        )
        runs.append(file_ref(base / "run.json"))
        inherited.append(dict(relative=f"draw{draw}/run.json", **runs[-1]))
        present = {p.parent.name for p in base.glob("episodes/*/episode.json")}
        require(present == set(run["episode_keys"][:expected]), "complete feedback prefix changed")
        event_keys = {p.name for p in (base / "events").iterdir() if p.is_dir()}
        require(
            event_keys == set(run["episode_keys"][: expected + (draw == 1)]),
            "unregistered additional feedback attempt exists",
        )
        for index, key in enumerate(run["episode_keys"][:expected]):
            episode_path = base / "episodes" / key / "episode.json"
            episode = read(episode_path)
            event_paths = sorted((base / "events" / key).glob("*/event.json"))
            require(
                event_paths
                and [p.parent.name for p in event_paths]
                == [f"{j:06d}" for j in range(len(event_paths))],
                "episode event gap",
            )
            completion = read(event_paths[-1])
            require(
                completion.get("kind") == "episode_completed"
                and completion["payload"] == episode
                and episode["provider"] == intent["identity"]
                and episode["config"] == run["config"]
                and episode["all_provider_calls_settled"] is True
                and episode["actual_model_calls"] == len(episode["turns"]),
                "incomplete inherited episode",
            )
            for turn in episode["turns"]:
                receipt = turn.get("receipt")
                require(
                    receipt
                    and receipt["identity"] == intent["identity"]
                    and len(receipt["raw_generated_token_ids"])
                    == len(receipt["sampled_token_logprobs"]),
                    "inherited token receipt changed",
                )
            settled_calls += episode["actual_model_calls"]
            complete.append(
                dict(draw=draw, index=index, episode_key=key, episode=file_ref(episode_path))
            )
            for path in [episode_path, *event_paths]:
                inherited.append(dict(relative=str(path.relative_to(root)), **file_ref(path)))
        seal_path = base / "generation_seal/seal.json"
        if draw == 0:
            seal = read(seal_path)
            require(
                seal["run_id"] == run["id"]
                and seal["complete"] is True
                and seal["all_provider_calls_settled"] is True
                and seal["registered_denominator"] == 350
                and [e["key"] for e in seal["episodes"]] == run["episode_keys"],
                "draw0 seal changed",
            )
            require(
                seal["id"] == digest({k: v for k, v in seal.items() if k != "id"}),
                "seal digest changed",
            )
            for item in seal["episodes"]:
                require(
                    item["path"] == f"episodes/{item['key']}/episode.json",
                    "draw0 seal path escapes original episode",
                )
                require(
                    file_ref(base / item["path"])["sha256"] == item["sha256"], "draw0 bytes changed"
                )
            inherited.append(
                dict(relative="draw0/generation_seal/seal.json", **file_ref(seal_path))
            )
        else:
            require(
                not seal_path.exists() and run["episode_keys"][100] == UNKNOWN_KEY,
                "unknown coordinate changed",
            )
            events = sorted((base / "events" / UNKNOWN_KEY).glob("*/event.json"))
            require(
                len(events) == 2
                and [read(p)["kind"] for p in events] == ["episode_started", "model_call_intent"]
                and read(events[1])["step"] == 0,
                "unknown request has additional durable evidence",
            )
            old_intent = read(events[1])["payload"]
            request = {key: old_intent[key] for key in ("messages", "tools", "config")}
            require(digest(request) == old_intent["request_sha256"], "unknown request hash changed")
            unknown = dict(
                draw=1,
                index=100,
                episode_key=UNKNOWN_KEY,
                step=0,
                task=run["tasks"][100],
                old_events=[file_ref(p) for p in events],
                old_intent=file_ref(events[1]),
                request_sha256=old_intent["request_sha256"],
                previous_actual_call_outcome="unknown_no_token_receipt",
                maximum_reexecutions=1,
            )
    result = dict(
        schema=SCHEMA,
        original_context_id=context["id"],
        coordinate=list(COORDINATE),
        context_ref=file_ref(directory / "context/record.json"),
        point_id=POINT_ID,
        computed_point_payload=str(computed),
        computed_point_ref=file_ref(computed / "record.json"),
        computed_point_state=dict(path=str(computed / "state.pt"), sha256=payload["state_sha256"]),
        source_feedback_root=str(root),
        registered_provider=intent["identity"],
        draw_runs=runs,
        inherited_files=inherited,
        inherited_episodes=complete,
        inherited_episode_count=450,
        inherited_returned_model_calls=settled_calls,
        unknown_request=unknown,
        first_time_episode_keys=read(runs[1]["path"])["episode_keys"][101:],
        new_completed_episodes=250,
        first_time_episodes=249,
        explicitly_reexecuted_unreturned_requests=1,
        denominator=700,
        old_artifacts_written=False,
        prior_reward_scoring=False,
    )
    result["id"] = digest(result)
    return result


def checked_binding(binding, context):
    require(
        binding is not None
        and binding.get("schema") == SCHEMA
        and binding["original_context_id"] == context["id"] == CONTEXT_ID
        and tuple(binding["coordinate"]) == COORDINATE
        and binding["point_id"] == POINT_ID,
        "unregistered feedback recovery binding",
    )
    body = {k: v for k, v in binding.items() if k not in ("id", "new_feedback_base_root")}
    require(binding["id"] == digest(body), "feedback recovery binding digest changed")
    require(
        binding["inherited_episode_count"] == len(binding["inherited_episodes"]) == 450
        and len(binding["first_time_episode_keys"]) == 249
        and binding["unknown_request"]["episode_key"] == UNKNOWN_KEY
        and binding["unknown_request"]["maximum_reexecutions"] == 1
        and binding["new_completed_episodes"] == 250
        and binding["denominator"] == 700,
        "feedback recovery dose changed",
    )
    require(
        json.loads(read_ref(binding["context_ref"])) == context, "scientific context was altered"
    )
    return binding


def restore_saved_point(binding, context, pre_state, bundle, *, original_worker):
    """Only saved CPU tensors; no class/G/virtual-point recomputation."""
    checked_binding(binding, context)
    read_ref(binding["computed_point_ref"])
    read_ref(binding["computed_point_state"])
    point = original_worker.read_payload(
        binding["computed_point_payload"], bundle.rt, context=context, phase="virtual_point_values"
    )
    require(
        point["pre_state_digest"]
        == context["pre_state_digest"]
        == bundle.rt.v8._tree_digest(pre_state)
        and point["branch"] == context["branch"],
        "saved point belongs to another pre-state or branch",
    )
    for name in ("G", "theta_bar", "update"):
        original_worker.checked_vector(point[name], context, bundle.rt)
        require(
            all(t.device.type == "cpu" for t in point[name].values()),
            "saved point must restore on CPU",
        )
    require(
        bundle.guard.recompute_point_id(
            pre_state, theta_bar=point["theta_bar"], G=point["G"], frozen_runtime=bundle.rt
        )
        == point["point_id"]
        == binding["point_id"]
        and bundle.rt.v8.parameter_digest(point["theta_bar"])
        == binding["registered_provider"]["parameter_digest"],
        "saved point or parameter digest differs",
    )
    return point


def prepare_feedback_overlay(binding, context, *, immutable):
    """Fresh byte-exact execution copy; never unlink/edit/retry the parent."""
    checked_binding(binding, context)
    base = Path(binding["new_feedback_base_root"]).resolve()
    source = Path(binding["source_feedback_root"]).resolve()
    require(
        not base.is_relative_to(source) and not source.is_relative_to(base),
        "feedback overlay overlaps source",
    )
    require(not base.exists(), "feedback recovery view already exists; automatic retry forbidden")
    target = base / digest(binding["point_id"])
    immutable.write_immutable_artifact_directory(
        base,
        {
            "recovery_binding.json": json.dumps(binding, sort_keys=True, indent=2).encode(),
        },
    )
    groups = {}
    for reference in binding["inherited_files"]:
        relative = Path(reference["relative"])
        require(
            not relative.is_absolute()
            and ".." not in relative.parts
            and (source / relative).resolve() == Path(reference["path"]).resolve(),
            "inherited feedback path escapes the registered parent",
        )
        groups.setdefault(relative.parent, {})[relative.name] = read_ref(reference)
    for parent, files in groups.items():
        immutable.write_immutable_artifact_directory(target / parent, files)
    old = binding["unknown_request"]
    immutable.write_immutable_artifact_directory(
        base / "unreturned_request_disposition",
        {
            "record.json": json.dumps(
                dict(
                    schema="v42_explicit_unknown_request_disposition.v1",
                    binding_id=binding["id"],
                    previous=old,
                    disposition="one_explicit_same_request_reexecution",
                    previous_outcome_remains_unknown=True,
                    original_intent_deleted=False,
                    complete_episodes_reexecuted=0,
                    maximum_reexecutions=1,
                ),
                sort_keys=True,
                indent=2,
            ).encode(),
            "original_episode_started.json": read_ref(old["old_events"][0]),
            "original_model_call_intent.json": read_ref(old["old_intent"]),
        },
    )
    return target


def validate_reexecution_intent(old_event, new_event, *, contracts, registered_provider=None):
    """Match the scientific request, verifying fresh audit-only UUID scope.

    The original V7 executor does not supply invocation_context: its harness
    mints fresh ephemeral run/episode IDs. These are not provider input and must
    not be forged to impersonate the unresolved old invocation. Every scientific
    request, actual point and turn field remains exact.
    """
    require(
        old_event["kind"] == new_event["kind"] == "model_call_intent"
        and old_event["step"] == new_event["step"] == 0,
        "reexecution must target the original step0 model-call intent",
    )
    old, new = old_event["payload"], new_event["payload"]
    fields = {
        "messages",
        "tools",
        "config",
        "request_sha256",
        "harness_invocation",
        "invocation_id",
    }
    require(set(old) == set(new) == fields, "reexecution intent fields changed")
    request_keys = ("messages", "tools", "config")
    old_request = {key: old[key] for key in request_keys}
    new_request = {key: new[key] for key in request_keys}
    require(
        old_request == new_request
        and old["request_sha256"] == digest(old_request)
        and new["request_sha256"] == digest(new_request)
        and old["request_sha256"] == new["request_sha256"],
        "explicit reexecution must use the exact original request and request digest",
    )
    invocations = []
    for payload in (old, new):
        value = payload["harness_invocation"]
        require(
            set(value)
            == {
                "run_id",
                "episode_id",
                "attempt_index",
                "turn_index",
                "invocation_id",
                "point_id",
                "parameter_digest",
            }
            and type(value["attempt_index"]) is int
            and value["attempt_index"] == 0
            and type(value["turn_index"]) is int
            and value["turn_index"] == 0
            and all(
                isinstance(value[key], str) and re.fullmatch(r"ephemeral:[0-9a-f]{32}", value[key])
                for key in ("run_id", "episode_id")
            ),
            "reexecution requires the original V7 ephemeral step0 audit-scope contract",
        )
        expected = contracts.invocation_identity(value, turn_index=0)
        expected.update(point_id=value["point_id"], parameter_digest=value["parameter_digest"])
        require(
            value == expected and payload["invocation_id"] == value["invocation_id"],
            "reexecution invocation identity is not internally consistent",
        )
        if registered_provider is not None:
            require(
                all(
                    value[key] == registered_provider[key]
                    for key in ("point_id", "parameter_digest")
                ),
                "reexecution invocation does not match the registered actual model point",
            )
        invocations.append(value)
    old_invocation, new_invocation = invocations
    require(
        all(
            old_invocation[key] == new_invocation[key]
            for key in ("point_id", "parameter_digest", "attempt_index", "turn_index")
        ),
        "reexecution point, parameter or turn coordinates changed",
    )
    require(
        old_invocation["run_id"] != new_invocation["run_id"]
        and old_invocation["episode_id"] != new_invocation["episode_id"]
        and old_invocation["invocation_id"] != new_invocation["invocation_id"],
        "reexecution must retain fresh audit identity, not impersonate the old invocation",
    )
    return dict(
        scientific_request_sha256=new["request_sha256"],
        original_harness_invocation=copy.deepcopy(old_invocation),
        new_harness_invocation=copy.deepcopy(new_invocation),
        scientific_request_identical=True,
        old_invocation_identity_reused=False,
        old_unreturned_outcome_remains_unknown=True,
        provider_call_has_not_started=True,
    )


async def execute_remaining_draw(
    root, provider, binding, *, storage, stop_requested, boundary, record_reexecution=None
):
    """Original executor/harness with an episode-boundary stop and intent guard."""
    original_sink = storage.EventSink
    contracts = importlib.import_module(storage.__name__.rsplit(".", 1)[0] + ".contracts")
    old_intent = json.loads(read_ref(binding["unknown_request"]["old_intent"]))
    allowed = [binding["unknown_request"]["episode_key"], *binding["first_time_episode_keys"]]
    started = []

    class BoundarySink(original_sink):
        def __init__(self, directory):
            require(not stop_requested(), "feedback stopped at a complete episode boundary")
            boundary()
            key = Path(directory).name
            require(
                len(started) < len(allowed) and key == allowed[len(started)],
                "feedback resume dispatched an inherited or out-of-order episode",
            )
            self.episode_key = key
            started.append(key)
            super().__init__(directory)

        def __call__(self, event):
            if (
                self.episode_key == UNKNOWN_KEY
                and event["kind"] == "model_call_intent"
                and event["step"] == 0
            ):
                mapping = validate_reexecution_intent(
                    old_intent,
                    event,
                    contracts=contracts,
                    registered_provider=binding.get("registered_provider"),
                )
                if record_reexecution is not None:
                    record_reexecution(mapping)
            return super().__call__(event)

    namespace = dict(storage.execute_run.__globals__, EventSink=BoundarySink)
    execute = FunctionType(
        storage.execute_run.__code__,
        namespace,
        storage.execute_run.__name__,
        storage.execute_run.__defaults__,
        storage.execute_run.__closure__,
    )
    result = await execute(root, provider)
    require(started == allowed, "registered remaining250 episode coverage differs")
    return result


def execute_virtual(
    directory,
    context,
    pre_state,
    driver,
    gradients,
    bundle,
    monitor,
    stop,
    *,
    collector=None,
    control,
    binding,
    original_worker,
):
    rt = bundle.rt
    original_worker.validate_branch(context, rt)
    require(type(collector) is rt.v8.LocalFeedbackCollector, "original local collector required")
    point = restore_saved_point(
        binding, context, pre_state, bundle, original_worker=original_worker
    )
    require(not stop.requested, "stopped before feedback recovery view creation")
    root = prepare_feedback_overlay(binding, context, immutable=bundle.immutable)
    storage = importlib.import_module(
        rt.v8.LocalFeedbackCollector.collect.__module__.rsplit(".", 1)[0] + ".storage"
    )
    rebound = copy.copy(collector)
    rebound.root = Path(binding["new_feedback_base_root"])
    with rt.v8.installed_point(driver.model, point["theta_bar"]) as installed:
        identity = rt.v8.local_model_identity(
            driver.model,
            driver.tokenizer,
            model_id=collector.model_id,
            point_id=point["point_id"],
            parameter_tensors=installed,
        )
        require(
            identity.model_dump(mode="json") == binding["registered_provider"],
            "restored feedback model/tokenizer/point identity differs",
        )
        provider = rt.v8.LocalTorchProvider(
            driver.model, driver.tokenizer, identity, parameter_tensors=installed
        )

        def record_reexecution(mapping):
            # Sealed after semantic validation, before the original intent write
            # and provider.chat. This does not claim a model call occurred.
            require(
                root
                == Path(binding["new_feedback_base_root"]).resolve() / digest(binding["point_id"]),
                "reexecution audit escaped the registered fresh feedback view",
            )
            control.publish(
                root.parent / "reexecution_invocation_link/record.json",
                dict(
                    schema="v42_semantic_request_fresh_invocation_link.v1",
                    at=control.now(),
                    context_id=context["id"],
                    feedback_resume_binding_id=binding["id"],
                    episode_key=binding["unknown_request"]["episode_key"],
                    original_intent=binding["unknown_request"]["old_intent"],
                    **mapping,
                ),
            )

        asyncio.run(
            execute_remaining_draw(
                root / "draw1",
                provider,
                binding,
                storage=storage,
                stop_requested=lambda: stop.requested,
                boundary=lambda: monitor.snapshot(
                    "feedback_resume_episode_boundary", boundary=True
                ),
                record_reexecution=record_reexecution,
            )
        )
        new_calls = provider.actual_model_calls
    require(not stop.requested, "stopped after complete generation before first scoring")
    event_count = 0

    def event(value):
        nonlocal event_count
        control.publish(
            Path(directory) / "feedback_events" / f"event{event_count:06d}/record.json",
            dict(
                schema="v42_resumed_original_collector_event.v1",
                at=control.now(),
                context_id=context["id"],
                point_id=point["point_id"],
                event=value,
                feedback_resume_binding_id=binding["id"],
            ),
        )
        event_count += 1
        monitor.snapshot("feedback_resume." + value["phase"], boundary=True)

    # Complete draw seals already exist: original collector cannot generate.
    cohort, rewards = rebound.collect(
        driver.model,
        driver.tokenizer,
        point["theta_bar"],
        point_id=point["point_id"],
        event_sink=event,
    )
    require(
        cohort.denominator == len(rewards) == 700
        and cohort.identity.point_id == binding["point_id"]
        and cohort.identity.model_dump(mode="json") == binding["registered_provider"],
        "resumed700 identity differs",
    )
    for reference in binding["inherited_files"]:
        require(
            read_ref(reference) == (root / reference["relative"]).read_bytes(),
            "inherited feedback changed",
        )
    files = {
        relative: control.file_ref(root / relative)
        for relative in (
            "intent/record.json",
            "cohort_seal/record.json",
            "native_rewards/record.json",
            "draw0/run.json",
            "draw0/generation_seal/seal.json",
            "draw1/run.json",
            "draw1/generation_seal/seal.json",
        )
    }
    point.update(
        feedback_root=str(root),
        feedback_files=files,
        feedback_seal=cohort.model_dump(mode="json", exclude={"episodes"}),
        rewards=list(rewards),
        computed_point_payload=binding["computed_point_ref"],
        feedback_mode="first_sampling",
        feedback_resume_binding_id=binding["id"],
        new_feedback_episodes=250,
        inherited_feedback_episodes=450,
        positive_reward_response_count=sum(
            len(ep.turns)
            for ep, reward in zip(cohort.episodes, rewards, strict=True)
            if reward != 0
        ),
    )
    payload = original_worker.save_payload(
        directory, rt, bundle.immutable, context=context, phase="virtual_point", value=point
    )
    monitor.clear_unused("virtual_feedback_resumed_and_sealed")
    return dict(
        payload=payload,
        point_id=point["point_id"],
        feedback_mode="first_sampling",
        denominator=700,
        feedback_seal_sha256=cohort.seal_sha256,
        new_feedback_episodes=250,
        inherited_feedback_episodes=450,
        first_time_feedback_episodes=249,
        explicitly_reexecuted_unreturned_requests=1,
        inherited_returned_model_calls=binding["inherited_returned_model_calls"],
        new_sampling_calls=new_calls,
        scoring_calls=700,
        original_sealed_point_matched=None,
        population_gradient_digest=rt.v8.parameter_digest(point["G"]),
        actual_virtual_theta_digest=rt.v8.parameter_digest(point["theta_bar"]),
        class_gradient_passes=0,
        virtual_point_recomputations=0,
        response_count=point["positive_reward_response_count"],
        feedback_resume_binding_id=binding["id"],
        old_unreturned_request_outcome_remains_unknown=True,
    )


def load_feedback(point, context, bundle, *, binding, control, original_loader):
    if binding is None:
        return original_loader(point, context, bundle)
    checked_binding(binding, context)
    root = Path(binding["new_feedback_base_root"]).resolve() / digest(binding["point_id"])
    require(
        Path(point["feedback_root"]).resolve() == root
        and point["feedback_resume_binding_id"] == binding["id"]
        and point["point_id"] == binding["point_id"],
        "unregistered feedback path alias",
    )
    for reference in point["feedback_files"].values():
        require(
            Path(reference["path"]).resolve().is_relative_to(root),
            "feedback alias file escapes view",
        )
        read_ref(reference)
    intent = read(root / "intent/record.json")
    require(
        intent["identity"] == binding["registered_provider"]
        and intent["point_id"] == binding["point_id"],
        "resumed feedback intent differs",
    )
    cohort, rewards, _ = bundle.guard._load_sealed(root, intent, bundle.rt)
    require(
        cohort.denominator == len(rewards) == 700
        and rewards == point["rewards"]
        and cohort.identity.parameter_digest == bundle.rt.v8.parameter_digest(point["theta_bar"])
        and cohort.model_dump(mode="json", exclude={"episodes"}) == point["feedback_seal"],
        "resumed sealed cohort/reward/point binding differs",
    )
    return cohort, rewards
