"""Bounded hybrid-history continuation using the unchanged native public tools.

The prefix and V73 first response are evidence, never regenerated or relabelled.
Only P may produce later responses. Native scoring is deliberately absent here.
"""
from __future__ import annotations

import copy
import hashlib
import importlib
import json
from pathlib import Path
import time
from types import SimpleNamespace

import finqa_v74_binding as b

require, digest = b.require, b.digest


class UnknownContinuation(RuntimeError):
    """An issued operation lacks a durable return; automatic repetition is unsafe."""


def native_modules():
    b.install_scientific_paths()
    b.install_registered_auxiliary()
    base = "trusted_synthesis.finance_research."
    return SimpleNamespace(contracts=importlib.import_module(base + "contracts"),
        harness=importlib.import_module(base + "harness"),
        providers=importlib.import_module(base + "providers"),
        task=importlib.import_module(base + "v6_task"),
        settlement=importlib.import_module(base + "settlement"),
        profiles=importlib.import_module(base + "profiles"))


def _check(guard, label):
    if guard is not None:
        guard.check(label, boundary=True)


def audit_condition(output_dir):
    """Read only durable evidence; a missing return is never a fresh call budget."""
    root = Path(output_dir)
    unknown, model_returns, tool_returns = [], [], []
    for path in sorted(root.glob("model/step*/attempt*/intent.json")):
        returned, rejected = path.with_name("returned.json"), path.with_name("not_executed.json")
        intent = b.checked(path)
        require(not (returned.exists() and rejected.exists()), "call returned and rejected simultaneously")
        if returned.exists():
            value = b.checked(returned)
            require(value["intent_id"] == intent["id"], "saved model return has a foreign intent")
            model_returns.append(value)
        elif rejected.exists():
            value = b.checked(rejected)
            require(value["intent_id"] == intent["id"] and value["actual_model_calls"] == 0
                and value["confirmed_forward_calls"] == 0, "unexecuted-call evidence changed")
        else:
            unknown.append(str(path))
    for path in sorted(root.glob("tool/step*/intent.json")):
        returned = path.with_name("returned.json")
        if returned.exists():
            value, intent = b.checked(returned), b.checked(path)
            require(value["intent_id"] == intent["id"], "saved tool return has a foreign intent")
            tool_returns.append(value)
        else:
            unknown.append(str(path))
    for path in sorted(root.glob("reconstruction/attempt*/event*/intent.json")):
        returned = path.with_name("returned.json")
        if returned.exists():
            value, intent = b.checked(returned), b.checked(path)
            require(value["intent_id"] == intent["id"] and value["exact_event_match"] is True,
                    "saved state reconstruction failed or has a foreign intent")
        else:
            unknown.append(str(path))
    steps = [value["step"] for value in model_returns]
    require(len(steps) == len(set(steps)), "a logical new response was generated more than once")
    return dict(complete=(root / "result.json").exists(), unknown_intents=unknown,
        unknown_calls=len(unknown), resume_allowed=not unknown,
        new_model_calls=len(model_returns), new_tool_calls=len(tool_returns),
        progress_units=len(model_returns) + len(tool_returns),
        completed_digest=digest([v["id"] for v in model_returns + tool_returns]))


def _new_request(messages, tools, config, predictor):
    """Render the whole actual history with the same native template, without cuts."""
    rendered = predictor.tokenizer.apply_chat_template(copy.deepcopy(messages),
        tools=copy.deepcopy(tools), tokenize=False, add_generation_prompt=True)
    ids = list(predictor.tokenizer(rendered, add_special_tokens=False,
        truncation=False, padding=False)["input_ids"])
    request = dict(messages=copy.deepcopy(messages), tools=copy.deepcopy(tools),
        config=config.model_dump(mode="json"), tool_protocol=config.local_tool_protocol,
        template_tools_kwarg_used=True,
        rendered_prompt_sha256=hashlib.sha256(rendered.encode()).hexdigest())
    return dict(request=request, prompt_input_ids=ids)


def _verify_turn(turn, identity, *, prompt=None, request=None):
    receipt = turn["receipt"]
    require(receipt is not None and receipt["identity"] == identity,
            "hybrid successor response belongs to another checkpoint")
    require(hashlib.sha256(turn["raw_text"].encode()).hexdigest() == receipt["raw_response_sha256"],
            "original response text changed")
    require(prompt is None or receipt["prompt_input_ids"] == list(prompt),
            "response input tokens differ from the registered full history")
    if request is not None:
        require(receipt["request_sha256"] == digest(request)
            and turn["provider_metadata"]["request"] == request,
            "new response receipt is not bound to the exact requested full history")
    require(turn["finish_reason"] == receipt["finish_reason"]
        and 0 < len(receipt["raw_generated_token_ids"]) <= 2048,
        "response receipt is incomplete or exceeds the original output budget")


def validate_outcome(condition, outcome, modules=None):
    """Validate explicit mixed provenance before the native terminal metric adapter."""
    require(outcome["condition_id"] == condition["condition_id"]
        and outcome["status"] == "COMPLETE", "condition result identity or status changed")
    episode = outcome["episode"]
    prior = condition["source_turn_index"]
    require(episode["turns"][:prior] == condition["prefix_turns"]
        and episode["turns"][prior] == condition["first_turn"],
        "hybrid prefix or reused V73 first response was changed")
    require(episode["tool_events"][:len(condition["prefix_events"])] == condition["prefix_events"],
        "original prefix tool evidence changed")
    require(episode["call_settlements"][:prior] == condition["prefix_settlements"],
        "original prefix call settlements changed")
    require(episode["provider"] == condition["actor_identity"]
        and outcome["provenance"]["episode_provider_semantics"] == "successor_only_not_homogeneous_trajectory",
        "mixed trajectory misrepresented as a homogeneous model run")
    require(0 <= outcome["new_model_calls"] <= condition["remaining_model_calls"]
        and len(episode["turns"]) == prior + 1 + outcome["new_model_calls"]
        and len(episode["turns"]) <= 32, "continued model call budget reset or exceeded")
    if outcome["new_model_calls"]:
        require(condition["actor_model"] == "P"
            and condition["first_action_category"] == "compliant_nonterminal_candidate",
            "new inference outside the 31 registered P continuations")
    for turn in episode["turns"][prior:]:
        _verify_turn(turn, condition["actor_identity"])
    require(outcome["episode_sha256"] == digest(episode), "terminal episode bytes changed")
    if modules is not None:
        parsed = modules.contracts.Episode.model_validate(episode)
        require(modules.settlement.episode_is_complete(parsed), "native hybrid episode is unsettled")
    return True


def run_condition(condition, *, output_dir, protocol_id, inputs_id, attempt,
                  predictor_factory, guard, modules=None):
    """Execute one condition once, or reconstruct a fully returned durable boundary.

    ``predictor_factory`` returns the worker's lazy shared frozen V73 P Predictor.
    Its creation is impossible for the 161 immediate terminal conditions.
    """
    root = Path(output_dir)
    bound = dict(protocol_id=protocol_id, inputs_id=inputs_id,
        condition_id=condition["condition_id"], condition_sha256=digest(condition))
    if (root / "result.json").exists():
        result = b.checked(root / "result.json")
        require(all(result[key] == value for key, value in bound.items()), "saved terminal binding changed")
        validate_outcome(condition, result)
        return result
    audit = audit_condition(root)
    if audit["unknown_intents"]:
        raise UnknownContinuation("unsettled continuation operations: " + repr(audit["unknown_intents"]))
    m = modules or native_modules()
    c = m.contracts
    config = c.RunConfig.model_validate(condition["config"])
    require((config.max_steps, config.max_new_tokens, config.context_limit, config.temperature,
             config.top_p, config.top_k, config.seed, config.tier, config.role) ==
            (32, 2048, 24576, 0.0, 1.0, 0, 20260928, "EVAL_NATIVE", "development"),
            "original native greedy budget/config changed")
    prior = condition["source_turn_index"]
    require(type(prior) is int and 0 <= prior < 32
        and len(condition["prefix_turns"]) == len(condition["prefix_settlements"]) == prior,
        "source history model-call count is inconsistent")
    category = condition["first_action_category"]
    expected_remaining = max(0, 32 - prior - 1) if category == "compliant_nonterminal_candidate" else 0
    require(condition["remaining_model_calls"] == expected_remaining,
            "residual call allowance differs from original32 minus prior minus reused first")
    public = c.PublicTask.model_validate(condition["public_task"])
    require(digest(public.model_dump(mode="json")) == condition["public_task_sha256"],
            "source public task binding changed")
    scope = dict(run_id=protocol_id, episode_id=condition["condition_id"], attempt_index=0)
    session = m.task.PublicProgramSession(public, invocation_context=scope)
    # This is already the original profiled public run view. Do not apply the
    # profile a second time or serialize its content with a different key order.
    messages = copy.deepcopy(condition["original_request"]["messages"][:2])
    require(len(messages) == 2 and messages[0] == m.harness.system_message(config)
        and messages[1]["role"] == "user"
        and json.loads(messages[1]["content"]) == public.model_dump(mode="json"),
        "saved initial system/public source context changed")
    tools = m.harness.episode_tool_specs(config)
    require(tools == condition["original_request"]["tools"], "native tool dictionary values changed")
    turns, events = [], []
    settlements = copy.deepcopy(condition["prefix_settlements"])
    started = time.time()
    restoration_root = root / "reconstruction" / f"attempt{attempt:04d}"
    reconstruction_index = 0

    def restore(call, saved, origin, step):
        nonlocal reconstruction_index
        _check(guard, "before_hybrid_tool_state_reconstruction")
        directory = restoration_root / f"event{reconstruction_index:04d}"
        require(not directory.exists(), "same worker attempt cannot reconstruct a tool twice")
        intent = b.publish(directory / "intent.json", dict(**bound, kind="tool_state_reconstruction",
            origin=origin, step=step, tool_call=call.model_dump(mode="json"),
            saved_event_sha256=digest(saved), created_epoch=time.time()))
        event = session.execute(call, invocation_id=saved["invocation_id"])
        actual = event.model_dump(mode="json")
        b.publish(directory / "returned.json", dict(**bound, intent_id=intent["id"],
            kind="tool_state_reconstruction", origin=origin, step=step,
            returned_epoch=time.time(), actual_event=actual,
            saved_event_sha256=digest(saved), exact_event_match=actual == saved))
        reconstruction_index += 1
        require(actual == saved, "isolated tool state cannot reproduce the saved event exactly")
        _check(guard, "after_durable_hybrid_tool_reconstruction")
        return event

    require(len(condition["prefix_events"]) == prior,
            "every prior turn must be a single completed nonterminal tool event")
    for step, (old_turn, old_event) in enumerate(zip(condition["prefix_turns"], condition["prefix_events"], strict=True)):
        turn = c.ModelTurn.model_validate(old_turn)
        require(len(turn.tool_calls) == 1 and turn.tool_calls[0].call_id == old_event["call_id"],
                "prefix tool history is not the original chronological chain")
        event = restore(turn.tool_calls[0], old_event, "source_prefix", step)
        require(not (event.name == "submit_program" and not event.is_error),
                "source prefix already terminated before the selected call")
        turns.append(copy.deepcopy(old_turn)); events.append(copy.deepcopy(old_event))
        messages.append(m.providers.canonical_assistant_message(turn))
        messages.append(dict(role="tool", tool_call_id=event.call_id, content=event.visible_output))
    require(messages == condition["original_request"]["messages"],
            "restored public session history differs from the exact V73 source request")
    b.publish(restoration_root / "verified.json", dict(**bound,
        source_prefix_turns=prior, source_prefix_tools=len(events),
        exact_messages_match=True, restored_session_attempts=session._tool_attempts,
        restored_handles=sorted(session.events_by_handle), verified_epoch=time.time()))
    first = copy.deepcopy(condition["first_turn"])
    _verify_turn(first, condition["actor_identity"], prompt=condition["prompt_input_ids"])
    response = c.ModelTurn.model_validate(first)
    calls = response.tool_calls
    require((category == "plain_no_tool_call" and len(calls) == 0)
        or (category == "compliant_submit_candidate" and len(calls) == 1 and calls[0].name == "submit_program")
        or (category == "compliant_nonterminal_candidate" and len(calls) == 1
            and calls[0].name in {"list_sources", "read_source", "run_program"}),
        "saved first response no longer agrees with the registered V73 action category")
    new_calls, new_tools, reused_first_tools, context_rejected = 0, 0, 0, False
    final_program, error, stop_reason = None, None, "max_steps"
    predictor = None
    for step in range(prior, 32):
        if step == prior:
            raw_turn = first
            settlements.append(dict(attempt_index=step, state="returned", actual_model_calls=1,
                request_sha256=digest(dict(messages=messages, tools=tools, config=config.model_dump(mode="json"))),
                evidence=dict(kind="V73_first_response_reused_without_generation",
                    condition_id=condition["condition_id"], source_refs=dict(returned=condition.get("first_response_returned"), result=condition.get("first_response_result")),
                    original_receipt_request_sha256=first["receipt"]["request_sha256"],
                    response_sha256=digest(first))))
        else:
            require(category == "compliant_nonterminal_candidate" and condition["actor_model"] == "P"
                and new_calls < condition["remaining_model_calls"], "unregistered new continuation")
            if predictor is None:
                predictor = predictor_factory()
                require(predictor.model_label == "P", "only the frozen parent may generate new turns")
            context = _new_request(messages, tools, config, predictor)
            if not context["prompt_input_ids"] or len(context["prompt_input_ids"]) + 2048 > 24576:
                # Native pre-call context rejection: no truncate, no hidden continuation.
                context_rejected, stop_reason = True, "context_exceeded"
                error = "ContextLimitError: complete hybrid history exceeds original output reservation"
                settlements.append(dict(attempt_index=step, state="pre_call_rejected", actual_model_calls=0,
                    request_sha256=digest(dict(messages=messages, tools=tools, config=config.model_dump(mode="json"))),
                    evidence=dict(exception_type="ContextLimitError", actual_prompt_tokens=len(context["prompt_input_ids"]),
                        context_limit=24576, max_new_tokens=2048, history_truncated=False)))
                b.publish(root / "context_rejected.json", dict(**bound, step=step,
                    settlement=settlements[-1], actual_new_model_calls=0))
                break
            step_dir = root / "model" / f"step{step:04d}"
            saved = list(step_dir.glob("attempt*/returned.json"))
            require(len(saved) <= 1, "duplicate actual new response")
            if saved:
                returned = b.checked(saved[0])
                require(all(returned[k] == v for k,v in bound.items())
                    and returned["context_sha256"] == digest(context), "saved next response has a different full history")
            else:
                _check(guard, "before_hybrid_new_model_intent")
                attempt_dir = step_dir / f"attempt{attempt:04d}"
                before_calls = predictor.provider.actual_model_calls
                before_counters = predictor.counters
                intent = b.publish(attempt_dir / "intent.json", dict(**bound, step=step,
                    context_sha256=digest(context), context=context, created_epoch=time.time()))
                try:
                    value = predictor.generate(context)
                except BaseException as exception:
                    call_delta = predictor.provider.actual_model_calls - before_calls
                    delta = {key: val - before_counters.get(key, 0) for key,val in predictor.counters.items()}
                    forwards = sum(val for key,val in delta.items() if key.endswith("_forward_calls"))
                    if call_delta == forwards == 0:
                        b.publish(attempt_dir / "not_executed.json", dict(**bound, intent_id=intent["id"],
                            actual_model_calls=0, confirmed_forward_calls=0, exception=type(exception).__name__,
                            message=str(exception), no_retry_authorization_implied=True))
                    raise
                require(value["actual_model_generate_calls"] == 1, "new response counter is not exactly one")
                returned = b.publish(attempt_dir / "returned.json", dict(**bound, step=step,
                    intent_id=intent["id"], context_sha256=digest(context), value=value,
                    returned_epoch=time.time()))
                _check(guard, "after_durable_hybrid_model_return")
            raw_turn = copy.deepcopy(returned["value"]["turn"])
            _verify_turn(raw_turn, condition["actor_identity"], prompt=context["prompt_input_ids"], request=context["request"])
            new_calls += 1
            settlements.append(dict(attempt_index=step, state="returned", actual_model_calls=1,
                request_sha256=digest(dict(messages=messages, tools=tools, config=config.model_dump(mode="json"))),
                evidence=dict(kind="V74_actual_parent_continuation", returned_id=returned["id"],
                    response_sha256=digest(raw_turn))))
        turn = c.ModelTurn.model_validate(raw_turn)
        turns.append(raw_turn)
        messages.append(m.providers.canonical_assistant_message(turn))
        if not turn.tool_calls:
            stop_reason, error = "no_tool_call", "plain assistant text is not a final_answer submission"
            break
        if len(turn.tool_calls) != 1:
            stop_reason, error = "multiple_tool_calls", "exactly one tool call per model turn is permitted; none executed"
            break
        call = turn.tool_calls[0]
        tool_dir = root / "tool" / f"step{step:04d}"
        if (tool_dir / "returned.json").exists():
            saved = b.checked(tool_dir / "returned.json")
            require(all(saved[k] == v for k,v in bound.items()) and saved["step"] == step,
                    "saved tool result belongs to another condition")
            event = restore(call, saved["event"], "durable_continuation_tool", step)
        else:
            _check(guard, "before_hybrid_new_tool_intent")
            invocation = c.invocation_identity(scope, turn_index=step, tool_index=0)
            intent = b.publish(tool_dir / "intent.json", dict(**bound, step=step,
                tool_call=call.model_dump(mode="json"), invocation=invocation,
                response_sha256=digest(raw_turn), created_epoch=time.time()))
            event = session.execute(call, invocation_id=invocation["invocation_id"])
            b.publish(tool_dir / "returned.json", dict(**bound, step=step, intent_id=intent["id"],
                event=event.model_dump(mode="json"), returned_epoch=time.time()))
            _check(guard, "after_durable_hybrid_tool_return")
        new_tools += 1
        if step == prior:
            reused_first_tools += 1
        events.append(event.model_dump(mode="json"))
        messages.append(dict(role="tool", tool_call_id=call.call_id, content=event.visible_output))
        if call.name == "submit_program" and not event.is_error:
            final_program, stop_reason = event.raw_output["program"], "final_answer"
            break
        # A registered submit candidate should terminate under the unchanged tool.
        # Never grant L a fresh call or manufacture a second chance for such a case.
        require(category == "compliant_nonterminal_candidate",
                "immediate terminal first candidate unexpectedly failed native execution")
    episode = c.Episode(task_id=public.task_id, dataset=public.dataset,
        public_task_sha256=condition["public_task_sha256"], config=config,
        provider=c.ModelIdentity.model_validate(condition["actor_identity"]),
        turns=tuple(c.ModelTurn.model_validate(v) for v in turns),
        tool_events=tuple(c.ToolEvent.model_validate(v) for v in events), messages=tuple(messages),
        final_program=final_program, stop_reason=stop_reason, error=error,
        actual_model_calls=prior + 1 + new_calls, provider_attempts=len(settlements),
        call_settlements=tuple(c.CallSettlement.model_validate(v) for v in settlements),
        all_provider_calls_settled=True, elapsed_seconds=time.time()-started).model_dump(mode="json")
    restorations = [b.checked(path) for path in sorted(root.glob("reconstruction/attempt*/event*/returned.json"))]
    result = dict(**bound, schema="v74_hybrid_native_continuation.v1", status="COMPLETE",
        episode=episode, episode_sha256=digest(episode),
        direction=condition["direction"], group=condition["group"],
        source_model_calls_before_first=prior, first_action_category=category,
        new_model_calls=new_calls, new_tool_calls=new_tools,
        reused_first_response_tool_calls=reused_first_tools,
        reconstruction_tool_calls=len(restorations),
        source_prefix_reconstruction_tool_calls=sum(v["origin"] == "source_prefix" for v in restorations),
        durable_new_tool_reconstruction_calls=sum(v["origin"] == "durable_continuation_tool" for v in restorations),
        budget_exhausted=stop_reason == "max_steps", context_exhausted=context_rejected,
        budget=dict(original_max_steps=32, prior_model_calls=prior, reused_first_response=1,
            frozen_additional_model_call_cap=condition["remaining_model_calls"]),
        provenance=dict(schema="v74_explicit_mixed_model_lineage.v1",
            source_model=condition["source_model"], successor_model=condition["actor_model"],
            original_prefix_turn_range=[0,prior], reused_V73_turn_index=prior,
            new_successor_turn_range=[prior+1,len(turns)],
            episode_provider_semantics="successor_only_not_homogeneous_trajectory",
            original_source_episode=condition.get("source_episode"),
            original_first_response=dict(returned=condition.get("first_response_returned"), result=condition.get("first_response_result")),
            prefix_turn_receipt_identity_rewritten=False, first_response_regenerated=False),
        native_scoring_calls=0, external_API_calls=0, optimizer_updates=0,
        backward_calls=0, new_probability_sequences=0, completed_epoch=time.time())
    validate_outcome(condition, result, modules=m)
    return b.publish(root / "result.json", result)
