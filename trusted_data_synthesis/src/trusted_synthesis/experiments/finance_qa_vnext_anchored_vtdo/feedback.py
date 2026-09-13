"""Fixed-denominator, full sampled-trajectory feedback (CPU validated only).

Nothing here loads a model/tokenizer, launches a worker, or performs an optimizer
step. Public collection and offline qualification are separate functions. The
production adapter is deliberately unavailable; synthetic controls cannot be
relabeled as actual rounds. Records retain actual prompt and sampled token IDs:
probability replay never retokenizes text and never uses a positive SFT mask.
"""

import copy
import math
import re

from .protocol import checked_record, encode, record, require, sha

GROUPS = ("dual_sufficient", "composition_required", "other_financial")
CONTROL = "synthetic_cpu_control"
STATUSES = ("PASS", "FAIL", "UNDETERMINED", "NO_FINAL")


def production_adapter_status():
    return record(
        "probe_adapter_status",
        status="PRODUCTION_ADAPTER_NOT_VALIDATED",
        actual_round=False,
        new_student_sessions_authorized=False,
        public_random_worker_end_to_end_validated=False,
        conditional_16740_budget_is_execution_authorization=False,
    )


def require_production_adapter():
    raise ValueError("PRODUCTION_ADAPTER_NOT_VALIDATED")


def _ids(value, *, empty=False):
    require(isinstance(value, list) and (empty or bool(value)), "probe.token_ids_list")
    require(all(type(item) is int and item >= 0 for item in value), "probe.token_ids_integer")
    return value


def _parameter_snapshot(model):
    import torch

    require(getattr(model, "training", None) is False, "probe.dropout_must_be_off")
    if hasattr(model, "modules"):
        require(all(not module.training for module in model.modules()), "probe.all_modules_eval")
    items = list(model.named_parameters())
    require(
        items and len({name for name, _ in items}) == len(items), "probe.unique_named_parameters"
    )
    parameters = []
    for name, tensor in sorted(items):
        require(tensor.device.type == "cpu", "PRODUCTION_ADAPTER_NOT_VALIDATED")
        require(bool(torch.isfinite(tensor).all()), "probe.finite_parameters")
        parameters.append(
            {
                "name": name,
                "shape": list(tensor.shape),
                "dtype": str(tensor.dtype),
                "requires_grad": tensor.requires_grad,
                "sha256": sha(
                    tensor.detach().contiguous().reshape(-1).view(torch.uint8).numpy().tobytes()
                ),
            }
        )
    buffers = []
    for name, tensor in sorted(model.named_buffers() if hasattr(model, "named_buffers") else []):
        require(tensor.device.type == "cpu", "PRODUCTION_ADAPTER_NOT_VALIDATED")
        buffers.append(
            {
                "name": name,
                "shape": list(tensor.shape),
                "dtype": str(tensor.dtype),
                "sha256": sha(
                    tensor.detach().contiguous().reshape(-1).view(torch.uint8).numpy().tobytes()
                ),
            }
        )
    return {"parameters": parameters, "buffers": buffers}


def bind_virtual_model(model, *, base_identity, virtual_step_id):
    """Bind actual exposed parameter/buffer bytes, including functional tensors.

    A functional wrapper must additionally supply its immutable base descriptor;
    this CPU API does not certify a Qwen base merely from a caller's string.
    """
    require(isinstance(base_identity, (dict, str)) and bool(base_identity), "probe.base_identity")
    require(isinstance(virtual_step_id, str) and bool(virtual_step_id), "probe.virtual_step_id")
    snapshot = _parameter_snapshot(model)
    return record(
        "probe_virtual_identity",
        execution_kind=CONTROL,
        actual_round=False,
        base_identity=copy.deepcopy(base_identity),
        virtual_step_id=virtual_step_id,
        parameter_snapshot=snapshot,
        parameter_digest=sha(encode(snapshot)),
        dropout=False,
        production_base_certified=False,
    )


def validate_virtual_model(model, virtual_identity):
    checked_record(virtual_identity, "probe_virtual_identity")
    require(
        virtual_identity["execution_kind"] == CONTROL and virtual_identity["actual_round"] is False,
        "PRODUCTION_ADAPTER_NOT_VALIDATED",
    )
    snapshot = _parameter_snapshot(model)
    require(
        snapshot == virtual_identity["parameter_snapshot"]
        and sha(encode(snapshot)) == virtual_identity["parameter_digest"],
        "probe.virtual_parameter_bytes_changed",
    )


def probe_seed(*, pool, training_seed, outer_round, task_id, repeat):
    require(pool in ("A", "B") and training_seed in (11, 29, 47), "probe.pool_seed")
    require(type(outer_round) is int and outer_round in (0, 1), "probe.outer_round")
    require(type(repeat) is int and repeat in (1, 2), "probe.repeat")
    require(
        isinstance(task_id, str) and re.fullmatch(r"task_[0-9a-f]{64}", task_id),
        "probe.canonical_task_id",
    )
    # Condition is intentionally absent: common random numbers across algorithms.
    key = [pool, training_seed, outer_round, task_id, repeat]
    return int(sha(encode(key))[:16], 16) % (2**63)


def register_probes(dev_tasks, *, pool, training_seed, outer_round):
    require(isinstance(dev_tasks, list) and len(dev_tasks) == 180, "probe.exact_180_dev_tasks")
    require(
        all(set(row) == {"task_id", "group"} for row in dev_tasks), "probe.public_dev_fields_only"
    )
    require(len({row["task_id"] for row in dev_tasks}) == 180, "probe.unique_dev_tasks")
    require(
        all(sum(row["group"] == group for row in dev_tasks) == 60 for group in GROUPS),
        "probe.exact_60_tasks_per_group",
    )
    probes = []
    for row in sorted(dev_tasks, key=lambda item: (GROUPS.index(item["group"]), item["task_id"])):
        for repeat in (1, 2):
            fields = {
                "pool": pool,
                "training_seed": training_seed,
                "outer_round": outer_round,
                "task_id": row["task_id"],
                "repeat": repeat,
            }
            probes.append(
                record(
                    "probe_registration",
                    **fields,
                    group=row["group"],
                    rng_seed=probe_seed(**fields),
                    utility_coefficient="1/360",
                    execution_kind=CONTROL,
                    actual_round=False,
                )
            )
    return record(
        "probe_registry",
        pool=pool,
        training_seed=training_seed,
        outer_round=outer_round,
        dev_tasks=copy.deepcopy(dev_tasks),
        probes=probes,
        task_count=180,
        probe_count=360,
        group_weight="1/3",
        within_group_task_weight="1/60",
        repeat_weight="1/2",
        condition_in_rng_key=False,
        actual_round=False,
        execution_kind=CONTROL,
    )


def validate_registry(registry):
    checked_record(registry, "probe_registry")
    expected = register_probes(
        registry["dev_tasks"],
        pool=registry["pool"],
        training_seed=registry["training_seed"],
        outer_round=registry["outer_round"],
    )
    require(registry == expected, "probe.fixed_registration")
    return registry


def decoder_policy(*, eos_token_ids, pad_token_id, tokenizer_binding_id, chat_template_sha256):
    _ids(eos_token_ids)
    require(len(set(eos_token_ids)) == len(eos_token_ids), "probe.unique_eos")
    require(type(pad_token_id) is int and pad_token_id >= 0, "probe.pad_token")
    require(
        isinstance(tokenizer_binding_id, str) and bool(tokenizer_binding_id),
        "probe.tokenizer_binding",
    )
    require(
        isinstance(chat_template_sha256, str)
        and re.fullmatch(r"[0-9a-f]{64}", chat_template_sha256),
        "probe.template_digest",
    )
    return record(
        "probe_decoder_policy",
        temperature=1.0,
        top_p=1.0,
        top_k=0,
        do_sample=True,
        max_new_tokens=2048,
        max_context_tokens=24576,
        max_responses=32,
        max_tools=32,
        guidance="neutral",
        dropout=False,
        eos_token_ids=list(eos_token_ids),
        pad_token_id=pad_token_id,
        tokenizer_binding_id=tokenizer_binding_id,
        chat_template_sha256=chat_template_sha256,
        probability_length_normalization=False,
        repetition_penalty=1.0,
        forced_eos=False,
        execution_kind=CONTROL,
        actual_round=False,
    )


def _policy(policy):
    checked_record(policy, "probe_decoder_policy")
    expected = decoder_policy(
        **{
            key: policy[key]
            for key in (
                "eos_token_ids",
                "pad_token_id",
                "tokenizer_binding_id",
                "chat_template_sha256",
            )
        }
    )
    require(policy == expected, "probe.exact_random_decoder_policy")


def _forward_logits(model, ids):
    import torch

    tensor = torch.tensor([ids], dtype=torch.long, device="cpu")
    output = model(input_ids=tensor, attention_mask=torch.ones_like(tensor), use_cache=False)
    logits = output.logits if hasattr(output, "logits") else output["logits"]
    require(
        logits.ndim == 3 and tuple(logits.shape[:2]) == (1, len(ids)), "probe.causal_logits_shape"
    )
    require(bool(torch.isfinite(logits).all()), "probe.finite_logits")
    return logits


def sample_tokens(model, prompt_input_ids, *, generator, policy, virtual_identity):
    """Untruncated full-softmax sampling; saved IDs include an actually sampled EOS.

    Context rejection occurs before a forward call. Partial generated sequences
    survive a later forward failure, with their known probabilities retained.
    This helper is an actual Torch implementation, but only CPU is admitted.
    """
    import torch

    _policy(policy)
    validate_virtual_model(model, virtual_identity)
    _ids(prompt_input_ids)
    require(str(generator.device) == "cpu", "PRODUCTION_ADAPTER_NOT_VALIDATED")
    generator_before = sha(generator.get_state().numpy().tobytes())
    generated, logprobs = [], []
    error, reason, invoked = None, "length", False
    if len(prompt_input_ids) + policy["max_new_tokens"] > policy["max_context_tokens"]:
        reason = "context_rejected"
    else:
        try:
            with torch.no_grad():
                for _ in range(policy["max_new_tokens"]):
                    invoked = True
                    logits = _forward_logits(model, prompt_input_ids + generated)[0, -1]
                    # No top-k/top-p cutoff, no warpers, no forced EOS, T exactly one.
                    logp = torch.log_softmax(logits, dim=-1)
                    sampled = int(torch.multinomial(logp.exp(), 1, generator=generator).item())
                    generated.append(sampled)
                    logprobs.append(float(logp[sampled]))
                    if sampled in policy["eos_token_ids"]:
                        reason = "eos"
                        break
        except Exception as exc:
            reason, error = "generation_error", type(exc).__name__ + ": " + str(exc)
    validate_virtual_model(model, virtual_identity)
    return record(
        "sampled_generation",
        prompt_input_ids=list(prompt_input_ids),
        prompt_attention_mask=[1] * len(prompt_input_ids),
        prompt_ids_sha256=sha(encode(prompt_input_ids)),
        generated_token_ids=generated,
        generated_ids_sha256=sha(encode(generated)),
        sampled_token_logprobs=logprobs,
        finish_reason=reason,
        error=error,
        model_generation_invoked=invoked,
        virtual_identity_id=virtual_identity["id"],
        parameter_digest=virtual_identity["parameter_digest"],
        decoder_policy_id=policy["id"],
        includes_actual_eos=reason == "eos",
        generator_initial_seed=generator.initial_seed(),
        generator_state_before_sha256=generator_before,
        generator_state_after_sha256=sha(generator.get_state().numpy().tobytes()),
        execution_kind=CONTROL,
        actual_round=False,
    )


def _validate_sample(sample, virtual_identity, policy):
    checked_record(sample, "sampled_generation")
    _ids(sample["prompt_input_ids"])
    _ids(sample["generated_token_ids"], empty=True)
    require(
        sample["execution_kind"] == CONTROL and sample["actual_round"] is False,
        "PRODUCTION_ADAPTER_NOT_VALIDATED",
    )
    require(
        sample["virtual_identity_id"] == virtual_identity["id"]
        and sample["parameter_digest"] == virtual_identity["parameter_digest"]
        and sample["decoder_policy_id"] == policy["id"],
        "probe.sample_identity",
    )
    prompt, target = sample["prompt_input_ids"], sample["generated_token_ids"]
    require(sample["prompt_attention_mask"] == [1] * len(prompt), "probe.unpadded_full_prompt")
    require(
        sample["prompt_ids_sha256"] == sha(encode(prompt))
        and sample["generated_ids_sha256"] == sha(encode(target)),
        "probe.exact_token_hashes",
    )
    require(
        len(target) == len(sample["sampled_token_logprobs"])
        and all(
            type(p) in (float, int) and math.isfinite(p) and p <= 0
            for p in sample["sampled_token_logprobs"]
        ),
        "probe.complete_sampling_probabilities",
    )
    require(len(target) <= policy["max_new_tokens"], "probe.no_cropping_or_overlength")
    reason = sample["finish_reason"]
    require(
        reason in ("eos", "length", "generation_error", "context_rejected"), "probe.finish_reason"
    )
    require(
        not any(token in policy["eos_token_ids"] for token in target[:-1]),
        "probe.no_tokens_after_eos",
    )
    require(sample["includes_actual_eos"] is (reason == "eos"), "probe.eos_identity")
    if reason != "eos":
        require(not target or target[-1] not in policy["eos_token_ids"], "probe.eos_must_stop")
    if reason == "context_rejected":
        require(
            not target
            and sample["model_generation_invoked"] is False
            and len(prompt) + 2048 > 24576,
            "probe.pre_forward_context_stop",
        )
    else:
        require(
            len(prompt) + 2048 <= 24576 and sample["model_generation_invoked"] is True,
            "probe.full_context_budget",
        )
        if reason == "eos":
            require(target and target[-1] in policy["eos_token_ids"], "probe.actual_eos_required")
        elif reason == "length":
            require(
                len(target) == 2048 and target[-1] not in policy["eos_token_ids"],
                "probe.length_stop",
            )


class BoundProbeDecoder:
    """Injected CPU model/tokenizer callback for the existing public runtime.

    The tokenizer is used only at actual generation. Replay consumes these exact
    prompt IDs. Offline qualification is intentionally absent from this object.
    """

    def __init__(self, model, tokenizer, registration, *, policy, virtual_identity):
        import torch

        checked_record(registration, "probe_registration")
        _policy(policy)
        validate_virtual_model(model, virtual_identity)
        require(
            sha(tokenizer.chat_template) == policy["chat_template_sha256"],
            "probe.exact_chat_template",
        )
        self.model, self.tokenizer = model, tokenizer
        self.registration, self.policy, self.virtual_identity = (
            registration,
            policy,
            virtual_identity,
        )
        self.generator = torch.Generator(device="cpu").manual_seed(registration["rng_seed"])
        self.attempts = []

    def __call__(self, messages, context):
        before = len(self.attempts)
        try:
            return self._respond(messages, context)
        except Exception as exc:
            if len(self.attempts) == before:
                # Unknown sampling provenance blocks g_J, never disappears.
                self.attempts.append(
                    record(
                        "probe_incomplete_attempt",
                        registration_id=self.registration["id"],
                        response_index=before,
                        input_messages=copy.deepcopy(messages),
                        context=copy.deepcopy(context),
                        error=type(exc).__name__ + ": " + str(exc),
                        sampling_record_complete=False,
                        model_generation_invoked="UNKNOWN",
                        raw_response=None,
                        execution_kind=CONTROL,
                        actual_round=False,
                    )
                )
            raise

    def _respond(self, messages, context):
        from ..finance_qa_vnext_eval_readiness import runtime

        require(
            messages[0]
            == {"role": "system", "content": runtime.SYSTEM + "\nRequested guidance: neutral"},
            "probe.original_neutral_system",
        )
        require(
            all(
                set(message) == {"role", "content"} and isinstance(message["content"], str)
                for message in messages
            ),
            "probe.exact_public_messages",
        )
        require(
            context["identity"]["task_id"] == self.registration["task_id"]
            and context["response_index"] == len(self.attempts)
            and context["max_responses"] == 32
            and context["max_tools"] == 32
            and context["history_must_not_be_truncated"] is True,
            "probe.public_runtime_context",
        )
        rendered = self.tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )
        encoded = self.tokenizer(
            rendered, add_special_tokens=False, truncation=False, padding=False
        )
        ids = list(encoded["input_ids"])
        require(list(encoded["attention_mask"]) == [1] * len(ids), "probe.no_prompt_padding")
        sampled = sample_tokens(
            self.model,
            ids,
            generator=self.generator,
            policy=self.policy,
            virtual_identity=self.virtual_identity,
        )
        target = sampled["generated_token_ids"]
        content = target[:-1] if sampled["includes_actual_eos"] else target
        raw, decode_error = None, None
        if sampled["finish_reason"] in ("eos", "length"):
            try:
                raw = self.tokenizer.decode(
                    content, skip_special_tokens=False, clean_up_tokenization_spaces=False
                )
                require(isinstance(raw, str), "probe.decoded_text")
            except Exception as exc:
                decode_error = type(exc).__name__ + ": " + str(exc)
        attempt = record(
            "probe_attempt",
            registration_id=self.registration["id"],
            response_index=len(self.attempts),
            input_messages=copy.deepcopy(messages),
            context=copy.deepcopy(context),
            rendered_prompt=rendered,
            rendered_prompt_sha256=sha(rendered),
            sampled=sampled,
            public_content_token_ids=content,
            raw_response=raw,
            raw_response_sha256=sha(raw) if raw is not None else None,
            decode_error=decode_error,
            no_history_retokenization_during_replay=True,
            execution_kind=CONTROL,
            actual_round=False,
        )
        self.attempts.append(attempt)
        if raw is None:
            raise ValueError("probe.generation_or_decode_stop:" + sampled["finish_reason"])
        return {"raw_response": raw, "receipt": attempt["id"]}


def seal_probe(registration, attempts, *, terminal, transcript, virtual_identity, policy):
    checked_record(registration, "probe_registration")
    _policy(policy)
    checked_record(virtual_identity, "probe_virtual_identity")
    require(
        isinstance(transcript, dict) and transcript.get("terminal") == terminal,
        "probe.original_transcript",
    )
    require(
        transcript.get("identity", {}).get("task_id") == registration["task_id"],
        "probe.transcript_task",
    )
    turns = transcript.get("turns")
    require(
        isinstance(turns, list)
        and len(attempts) <= 32
        and len(attempts) == transcript.get("provider_calls"),
        "probe.complete_attempt_denominator",
    )
    require(
        len({turn["response_index"] for turn in turns}) == len(turns),
        "probe.unique_transcript_turns",
    )
    accepted = {turn["response_index"]: turn for turn in turns}
    complete_sampling_record = True
    for index, attempt in enumerate(attempts):
        if attempt.get("schema_version") == "anchored_vtdo.v1.probe_incomplete_attempt":
            checked_record(attempt, "probe_incomplete_attempt")
            require(
                attempt["registration_id"] == registration["id"]
                and attempt["response_index"] == index
                and index == len(attempts) - 1
                and index not in accepted
                and terminal == "provider_error"
                and attempt["sampling_record_complete"] is False
                and attempt["raw_response"] is None
                and attempt["execution_kind"] == CONTROL
                and attempt["actual_round"] is False,
                "probe.incomplete_terminal_attempt",
            )
            complete_sampling_record = False
            continue
        checked_record(attempt, "probe_attempt")
        require(
            attempt["registration_id"] == registration["id"] and attempt["response_index"] == index,
            "probe.attempt_registration",
        )
        _validate_sample(attempt["sampled"], virtual_identity, policy)
        require(
            attempt["sampled"]["generator_initial_seed"] == registration["rng_seed"],
            "probe.registered_random_stream",
        )
        if index:
            require(
                attempt["sampled"]["generator_state_before_sha256"]
                == attempts[index - 1]["sampled"]["generator_state_after_sha256"],
                "probe.unbroken_random_stream",
            )
        require(
            sha(attempt["rendered_prompt"]) == attempt["rendered_prompt_sha256"],
            "probe.prompt_text_hash",
        )
        generated = attempt["sampled"]["generated_token_ids"]
        expected_content = (
            generated[:-1] if attempt["sampled"]["includes_actual_eos"] else generated
        )
        require(
            attempt["public_content_token_ids"] == expected_content, "probe.strip_only_actual_eos"
        )
        require(
            attempt["context"]["response_index"] == index
            and attempt["context"]["identity"]["task_id"] == registration["task_id"]
            and attempt["context"]["max_responses"] == 32
            and attempt["context"]["max_tools"] == 32
            and attempt["context"]["history_must_not_be_truncated"] is True
            and attempt["execution_kind"] == CONTROL
            and attempt["actual_round"] is False,
            "probe.attempt_runtime_contract",
        )
        raw = attempt["raw_response"]
        if raw is not None:
            require(
                index in accepted
                and accepted[index]["input_messages"] == attempt["input_messages"]
                and accepted[index]["raw_response"] == raw
                and accepted[index]["raw_response_sha256"]
                == sha(raw)
                == attempt["raw_response_sha256"]
                and accepted[index]["provider_receipt"] == attempt["id"],
                "probe.original_turn_binding",
            )
        else:
            require(
                index not in accepted
                and index == len(attempts) - 1
                and terminal == "provider_error",
                "probe.unaccepted_attempt_is_terminal_failure",
            )
    require(
        set(accepted)
        == {i for i, attempt in enumerate(attempts) if attempt["raw_response"] is not None},
        "probe.no_unrecorded_turns",
    )
    return record(
        "probe",
        registration=copy.deepcopy(registration),
        attempts=copy.deepcopy(attempts),
        terminal=terminal,
        transcript=copy.deepcopy(transcript),
        transcript_sha256=sha(encode(transcript)),
        virtual_identity_id=virtual_identity["id"],
        parameter_digest=virtual_identity["parameter_digest"],
        decoder_policy_id=policy["id"],
        execution_kind=CONTROL,
        actual_round=False,
        training_eligible=False,
        training_samples=0,
        all_failures_retained=True,
        complete_sampling_record=complete_sampling_record,
    )


def validate_probe(probe, *, virtual_identity, policy):
    checked_record(probe, "probe")
    expected = seal_probe(
        probe["registration"],
        probe["attempts"],
        terminal=probe["terminal"],
        transcript=probe["transcript"],
        virtual_identity=virtual_identity,
        policy=policy,
    )
    require(probe == expected, "probe.exact_sealed_trajectory")


def collect_probes(
    registry, overlay, source_factory, *, model, tokenizer, policy, virtual_identity
):
    """CPU capability-injected public collection; no qualifier argument exists.

    ``overlay.public_envelope`` must expose the original public-only envelope.
    Caller supplies public sources, not private scoring records. Production use
    remains impossible through the CPU model/device/identity gate.
    """
    from ..finance_qa_vnext_eval_readiness import runtime

    validate_registry(registry)
    validate_virtual_model(model, virtual_identity)
    probes = []
    for registration in registry["probes"]:
        envelope = overlay.public_envelope(registration["task_id"])
        decoder = BoundProbeDecoder(
            model, tokenizer, registration, policy=policy, virtual_identity=virtual_identity
        )
        transcript = runtime.generate(
            envelope["messages"],
            envelope["identity"],
            source_factory(envelope),
            provider=decoder,
            requested_basis="neutral",
            max_responses=32,
            max_tools=32,
        )
        probes.append(
            seal_probe(
                registration,
                decoder.attempts,
                terminal=transcript["terminal"],
                transcript=transcript,
                virtual_identity=virtual_identity,
                policy=policy,
            )
        )
    return probes


def _fixed_probes(probes, registry, virtual_identity, policy):
    validate_registry(registry)
    require(isinstance(probes, list) and len(probes) == 360, "probe.fixed_360_attempted_probes")
    require(
        [probe["registration"] for probe in probes] == registry["probes"],
        "probe.exact_registered_order",
    )
    for probe in probes:
        validate_probe(probe, virtual_identity=virtual_identity, policy=policy)


def qualify_probes(probes, qualifier, *, registry, virtual_identity, policy):
    """Offline-only injected original qualifier, after ALL 360 probes are sealed.

    Qualifier returns ``{qualification_id, status}``, where PASS is complete
    trajectory qualification (not merely correct Final). Its underlying original
    report ID is retained. This function does not turn a synthetic callback into
    validated original production qualification.
    """
    _fixed_probes(probes, registry, virtual_identity, policy)
    rewards = {}
    for probe in probes:
        result = qualifier(copy.deepcopy(probe["transcript"]))
        require(
            set(result) == {"qualification_id", "status"} and result["status"] in STATUSES,
            "probe.original_qualification_result",
        )
        rewards[probe["id"]] = copy.deepcopy(result)
    _rewards(probes, rewards)
    return rewards


def _rewards(probes, rewards):
    require(
        isinstance(rewards, dict) and set(rewards) == {probe["id"] for probe in probes},
        "probe.every_failure_has_reward_record",
    )
    for probe in probes:
        result = rewards[probe["id"]]
        require(
            set(result) == {"qualification_id", "status"}
            and result["status"] in STATUSES
            and isinstance(result["qualification_id"], str)
            and bool(result["qualification_id"]),
            "probe.original_qualification_result",
        )
        if result["status"] == "PASS":
            require(
                probe["terminal"] == "first_final"
                and probe["transcript"].get("first_final_index") is not None,
                "probe.no_success_without_final",
            )


def recompute_trajectory_logprob(model, probe, *, virtual_identity, policy):
    """Sum log probabilities of ALL generated tokens, including errors and EOS.

    Tool observations and all earlier text are conditioning only. Sampling
    receipts are checked against full causal replay at the actual parameter
    digest. No masks, cropping, response filtering or length normalization.
    """
    import torch

    _policy(policy)
    validate_virtual_model(model, virtual_identity)
    validate_probe(probe, virtual_identity=virtual_identity, policy=policy)
    require(probe["complete_sampling_record"] is True, "probe.incomplete_sampling_record_no_gJ")
    trainable = [tensor for _, tensor in model.named_parameters() if tensor.requires_grad]
    require(trainable, "probe.trainable_parameters")
    total = sum(tensor.sum() * 0 for tensor in trainable)
    token_count = 0
    for attempt in probe["attempts"]:
        sample = attempt["sampled"]
        prompt, target = sample["prompt_input_ids"], sample["generated_token_ids"]
        if not target:
            continue
        logits = _forward_logits(model, prompt + target)
        causal = logits[0, len(prompt) - 1 : len(prompt) + len(target) - 1]
        actual = torch.tensor(target, dtype=torch.long, device="cpu")
        logps = torch.log_softmax(causal, dim=-1).gather(-1, actual[:, None]).squeeze(-1)
        recorded = torch.tensor(sample["sampled_token_logprobs"], dtype=logps.dtype)
        require(
            torch.allclose(logps.detach(), recorded, atol=1e-6, rtol=1e-5),
            "probe.replayed_sampling_probabilities_mismatch",
        )
        total = total + logps.sum()
        token_count += len(target)
    validate_virtual_model(model, virtual_identity)
    return {"logprob": total, "sampled_token_count": token_count}


def reward_gradient(model, probes, rewards, *, virtual_identity, registry, policy):
    """Return g_J tensors without mutating parameter .grad or stepping Student.

    Every registered failure/unknown/no-Final remains in the 360 denominator.
    Returned gradient is a feedback estimator for the virtual-step pullback,
    never an instruction or permission for direct policy-gradient training.
    """
    import torch

    _fixed_probes(probes, registry, virtual_identity, policy)
    _rewards(probes, rewards)
    require(
        all(probe["complete_sampling_record"] for probe in probes),
        "probe.incomplete_sampling_record_no_gJ",
    )
    validate_virtual_model(model, virtual_identity)
    named = [(name, tensor) for name, tensor in model.named_parameters() if tensor.requires_grad]
    require(named, "probe.trainable_parameters")
    # Autograd.grad rather than backward leaves the real .grad accumulation alone.
    gradients = {name: torch.zeros_like(tensor) for name, tensor in named}
    token_count, successes, logprob_sum = 0, 0, 0.0
    for probe in probes:
        replay = recompute_trajectory_logprob(
            model, probe, virtual_identity=virtual_identity, policy=policy
        )
        reward = int(rewards[probe["id"]]["status"] == "PASS")
        token_count += replay["sampled_token_count"]
        successes += reward
        logprob_sum += float(replay["logprob"].detach())
        # Even zero-reward trajectories are replayed/checked, not silently omitted.
        local = torch.autograd.grad(
            replay["logprob"] * (reward / 360), [tensor for _, tensor in named], allow_unused=True
        )
        for (name, _), gradient in zip(named, local, strict=True):
            if gradient is not None:
                gradients[name] = gradients[name] + gradient.detach()
    validate_virtual_model(model, virtual_identity)
    artifact = record(
        "probe_reward_gradient",
        registry_id=registry["id"],
        virtual_identity_id=virtual_identity["id"],
        parameter_digest=virtual_identity["parameter_digest"],
        decoder_policy_id=policy["id"],
        probe_ids=[probe["id"] for probe in probes],
        rewards=copy.deepcopy(rewards),
        fixed_denominator=360,
        group_count=3,
        tasks_per_group=60,
        repeats_per_task=2,
        utility_coefficient="(1/3)*(1/60)*(1/2)=1/360",
        successes=successes,
        utility=successes / 360,
        sampled_token_count=token_count,
        full_logprob_sum=logprob_sum,
        status="UNINFORMATIVE_FEEDBACK" if successes == 0 else "SYNTHETIC_FEEDBACK_COMPUTED",
        zero_reward_uninformative=successes == 0,
        theoretical_Contribution_zero=False,
        includes_failed_outputs=True,
        includes_actual_eos=True,
        tool_output_tokens_as_targets=False,
        uses_SFT_positive_mask=False,
        trajectory_length_normalization=False,
        actual_round=False,
        execution_kind=CONTROL,
        probe_added_to_SFT=False,
        direct_policy_gradient_step=False,
        optimizer_steps=0,
        production_adapter_validated=False,
        gradient_digest=sha(
            encode(
                {
                    name: sha(tensor.contiguous().reshape(-1).view(torch.uint8).numpy().tobytes())
                    for name, tensor in gradients.items()
                }
            )
        ),
    )
    return {"gradient": gradients, "artifact": artifact}
