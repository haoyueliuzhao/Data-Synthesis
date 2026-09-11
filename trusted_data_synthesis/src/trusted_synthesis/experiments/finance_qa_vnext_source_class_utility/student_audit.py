"""Unchanged local Student transcript audit, bound to this study configuration."""

from pathlib import Path

from trusted_synthesis.experiments.finance_qa_vnext_pq_student.evaluate import parse_math, rational
from trusted_synthesis.experiments.finance_qa_vnext_thinking_comparison.online.common import (
    LIMITS,
    strict_json,
)

from .plan import SYSTEM, encode, evaluation_config, read_json, record, require, sha


def _initial(public):
    return [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": encode({"task": public}).decode()},
    ]


def _unicode_scalars(value):
    pending = [value]
    while pending:
        current = pending.pop()
        if isinstance(current, str):
            if any(0xD800 <= ord(character) <= 0xDFFF for character in current):
                raise ValueError("response_strings_must_be_unicode_scalars")
        elif isinstance(current, dict):
            pending.extend(current)
            pending.extend(current.values())
        elif isinstance(current, list):
            pending.extend(current)


def _source_result(args, public):
    catalog = {fact["id"]: fact for fact in public["numeric_catalog"]}
    locators = args["locators"]
    require(isinstance(locators, list) and 1 <= len(locators) <= 32, "audit.source_locators")
    rows = []
    for locator in locators:
        if locator in catalog:
            fact = catalog[locator]
            rows.append({"numeric_record": fact, "segment": public["segments"][fact["segment"]]})
        else:
            rows.append({"segment_id": locator, "segment": public["segments"][locator]})
    result = {"records": rows}
    if len(locators) == 1 and locators[0] in catalog:
        result.update(exact_value=catalog[locators[0]]["value"], numeric_source_id=locators[0])
    return result


def _calculation(call, index, previous, public):
    args, output = call["arguments"], call["output"]["result"]
    variables, sources = args.get("variables", {}), args.get("sources", {})
    facts = {fact["id"]: fact for fact in public["numeric_catalog"]}
    resolved, bindings, refs = {}, [], set()

    def lookup(name):
        if name in resolved:
            return rational(resolved[name]["exact_value"])
        supplied = variables[name]
        if isinstance(supplied, dict) and set(supplied) == {"result_id"}:
            ref = supplied["result_id"]
            require(ref in previous, "audit.real_prior_numeric_result_reference")
            value = previous[ref]
            refs.add(ref)
            resolved[name] = {"exact_value": str(value), "result_id": ref}
            bindings.append(
                {"variable": name, "kind": "actual_tool_result_reference", "result_id": ref}
            )
        else:
            value = rational(supplied.get("value") if isinstance(supplied, dict) else supplied)
            declared = sources.get(name) if isinstance(sources, dict) else None
            if declared is None and isinstance(supplied, dict):
                declared = supplied.get("source", supplied.get("source_id"))
            resolved[name] = {"exact_value": str(value), "result_id": None}
            linked = isinstance(declared, str) and declared in facts
            bindings.append(
                {
                    "variable": name,
                    "kind": "explicit_source" if linked else "unlinked_numeric_constant",
                    "source_id": declared,
                    "numeric_alignment": bool(value == rational(facts[declared]["value"]))
                    if linked
                    else None,
                    "no_numeric_coincidence_source_inference": True,
                }
            )
        return value

    value = parse_math(args["expression"], lookup)
    require(value == rational(output["exact_value"]), "audit.independent_actual_arithmetic")
    require(
        output["expression"] == args["expression"]
        and output["resolved_variables"] == resolved
        and output["used_result_ids"] == sorted(refs)
        and output["model_supplied_sources"] == args.get("sources"),
        "audit.calculation_arguments_and_real_resultrefs",
    )
    require(
        output["financial_meaning_certified"] is False
        and output["source_declarations_validated"] is False,
        "audit.no_oracle_calculator_feedback",
    )
    return value, {
        "call_id": call["id"],
        "response_index": index,
        "original_expression": args["expression"],
        "original_arguments": args,
        "actual_exact_value": str(value),
        "independent_execution_verified": True,
        "variable_bindings": bindings,
        "used_result_ids": sorted(refs),
        "operation_count": output["operation_count"],
        "dependency_depth": output["dependency_depth"],
        "financial_meaning_requires_offline_review": True,
    }


def audit_session(directory, public, expected_identity=None):
    """Replay admitted public history and recompute original arithmetic without model calls."""
    directory = Path(directory)
    result = read_json(directory / "result.json")
    config = evaluation_config()
    require(
        result["origin"] == "local_student_generation"
        and result["no_fake_HTTP_or_teacher_response_projection"] is True,
        "audit.actual_local_origin_not_HTTP",
    )
    require(
        expected_identity is None or result["model_identity"] == expected_identity,
        "audit.expected_checkpoint_identity",
    )
    require(
        result["public_document_id"] == public["id"]
        and result["public_document_sha256"] == sha(encode(public)),
        "audit.exact_public_document",
    )
    messages, notebook, previous, calculations, requests, raw_messages = (
        _initial(public),
        {},
        {},
        [],
        [],
        {},
    )
    require(
        result["initial_request_messages_sha256"] == sha(encode(messages)), "audit.exact_original_T"
    )
    events, attempts = result["events"], result["attempts"]
    require(len(attempts) <= config["maximum_responses"], "audit.fixed_response_budget")
    event_pos, calls, invoked, final, final_index = 0, 0, 0, None, None
    terminal = "response_budget_exhausted"
    for index, outcome in enumerate(attempts):
        prefix = directory / f"turns/{index:03d}"

        def path(suffix, prefix=prefix):
            return prefix.with_name(prefix.name + suffix)

        request_raw = path("_request.json").read_bytes()
        require(
            request_raw == encode({"messages": messages, "decoder_configuration_id": config["id"]})
            and sha(request_raw) == outcome["request_sha256"],
            "audit.full_exact_history",
        )
        require(
            outcome == read_json(path("_outcome.json")) and outcome["response_index"] == index,
            "audit.outcome_binding",
        )
        require(
            outcome["origin"] == "local_student_generation"
            and outcome["is_HTTP_response"] is False
            and outcome["model_identity"] == result["model_identity"]
            and outcome["prompt_truncated"] is False,
            "audit.no_HTTP_or_hidden_history_truncation",
        )
        generated, content_ids = outcome["generated_token_ids"], outcome["public_content_token_ids"]
        require(
            type(outcome["generation_invoked"]) is bool
            and outcome["generated_token_count"] == len(generated)
            and all(type(t) is int and t >= 0 for t in generated),
            "audit.generation_accounting",
        )
        raw = outcome["content"].encode()
        if not outcome["generation_invoked"]:
            require(
                not raw
                and not generated
                and not content_ids
                and outcome["raw_response_sha256"] is None
                and not path("_assistant.raw").exists()
                and outcome["finish_reason"] == "context_token_limit",
                "audit.no_fabricated_noninvoked_generation",
            )
        else:
            invoked += 1
            require(
                path("_assistant.raw").read_bytes() == raw
                and sha(raw) == outcome["raw_response_sha256"],
                "audit.original_generated_public_content",
            )
            ended = bool(generated) and generated[-1] in config["eos_token_ids"]
            require(
                content_ids == (generated[:-1] if ended else generated)
                and (outcome["finish_reason"] == "stop") == ended,
                "audit.only_actual_final_EOS_removed",
            )
        if (
            outcome["finish_reason"] != "stop"
            or not raw
            or len(raw) > LIMITS["public_content_bytes"]
        ):
            terminal = (
                outcome["finish_reason"]
                if outcome["finish_reason"] != "stop"
                else "unknown_empty_public_output"
                if not raw
                else "public_content_byte_limit"
            )
            require(
                index == len(attempts) - 1 and not path("_event.json").exists(),
                "audit.unadmitted_terminal_never_retried",
            )
            break
        event = events[event_pos]
        event_pos += 1
        require(
            event == read_json(path("_event.json"))
            and event["response_index"] == index
            and event["raw_sha256"] == sha(raw)
            and event["oracle_feedback"] is False,
            "audit.event_binding",
        )
        raw_messages[index] = raw.decode()
        messages.append({"role": "assistant", "content": raw.decode()})
        error, model = None, None
        try:
            model = strict_json(raw)
            if not isinstance(model, dict):
                raise ValueError("response_must_be_json_object")
            _unicode_scalars(model)
        except (ValueError, TypeError, KeyError, RecursionError) as exc:
            error = str(exc)[:300]
        require(error == event["protocol_error"], "audit.unrepaired_protocol_error")
        if error:
            require(
                not event["final"] and event["tool_call"] is None,
                "audit.protocol_failure_not_final",
            )
            messages.append(
                {"role": "user", "content": encode({"interface_error": error}).decode()}
            )
            continue
        require(event["final"] == ("final" in model), "audit.literal_Final_detection")
        if "final" in model:
            require(
                index == len(attempts) - 1 and event["tool_call"] is None,
                "audit.first_Final_terminal",
            )
            final, final_index, terminal = model["final"], index, "model_final"
            break
        if "tool" not in model:
            require(event["tool_call"] is None, "audit.no_invented_tool")
            messages.append(
                {"role": "user", "content": encode({"receipt": "model_message_recorded"}).decode()}
            )
            continue
        if calls == config["maximum_tool_calls"]:
            require(
                index == len(attempts) - 1 and event["tool_call"] is None, "audit.fixed_tool_budget"
            )
            terminal = "tool_budget_exhausted"
            break
        calls += 1
        call = event["tool_call"]
        require(
            call["id"] == f"tool:{calls}"
            and call["name"] == model["tool"]
            and call["arguments"] == model.get("arguments", {}),
            "audit.original_tool_arguments",
        )
        output, args = call["output"], call["arguments"]
        require(
            output == read_json(path("_tool.json"))
            and output["call_id"] == call["id"]
            and output["tool"] == call["name"]
            and output["status"] in {"ok", "error"},
            "audit.original_tool_output",
        )
        messages.append({"role": "user", "content": encode({"tool_result": output}).decode()})
        if call["name"] == "calculate":
            requests.append(
                {
                    "call_id": call["id"],
                    "response_index": index,
                    "expression": args.get("expression") if isinstance(args, dict) else None,
                    "execution_status": output["status"],
                }
            )
        if output["status"] == "error":
            require(
                output["result"] is None and isinstance(output["error"], dict),
                "audit.tool_error_not_numeric_result",
            )
            continue
        if call["name"] == "read_source":
            expected = _source_result(args, public)
            require(output["result"] == expected, "audit.literal_public_source_retrieval")
            if "exact_value" in expected:
                previous[call["id"]] = rational(expected["exact_value"])
        elif call["name"] == "notebook":
            key, operation = args["key"], args["operation"]
            require(
                isinstance(key, str) and 0 < len(key) <= 80 and operation in {"read", "write"},
                "audit.notebook_arguments",
            )
            if operation == "write":
                require(
                    isinstance(args["text"], str)
                    and len(args["text"]) <= 8192
                    and (key in notebook or len(notebook) < 32),
                    "audit.notebook_limits",
                )
                notebook[key] = args["text"]
            require(
                output["result"]
                == {"key": key, "text": notebook[key], "author": "model", "operation": operation},
                "audit.actual_model_notebook",
            )
        elif call["name"] == "calculate":
            value, calculation = _calculation(call, index, previous, public)
            previous[call["id"]] = value
            calculations.append(calculation)
        else:
            raise ValueError("audit.unknown_successful_tool")
    context_path = directory / "context_limit_request.json"
    if context_path.exists():
        expected_request = encode({"messages": messages, "decoder_configuration_id": config["id"]})
        require(
            terminal == "response_budget_exhausted"
            and len(attempts) < config["maximum_responses"]
            and len(expected_request) > LIMITS["request_bytes"]
            and context_path.read_bytes() == expected_request,
            "audit.context_byte_limit_before_generation",
        )
        terminal = "context_byte_limit"
    require(
        terminal != "response_budget_exhausted" or len(attempts) == config["maximum_responses"],
        "audit.no_early_budget_stop",
    )
    require(
        messages == read_json(directory / "messages.json")
        and notebook == read_json(directory / "notebook.json"),
        "audit.persisted_complete_history_and_notebook",
    )
    require(
        event_pos == len(events) == result["admitted_public_responses"]
        and len(attempts) == result["decoder_requests"]
        and invoked == result["model_requests"]
        and calls == result["tool_calls"],
        "audit.honest_request_event_tool_counts",
    )
    require(
        result["terminal"] == terminal
        and result["final"] == final
        and (terminal == "model_final") == (final_index is not None),
        "audit.original_first_Final_and_terminal",
    )
    require(
        all(
            result[key] is True
            for key in (
                "no_online_answer_feedback",
                "first_Final_stops",
                "no_teacher_provider_calls",
                "original_T_and_public_tool_semantics_preserved",
            )
        )
        and result["history_truncated"] is False,
        "audit.no_online_oracle_or_final_retry",
    )
    return record(
        "local_student_audit",
        result_id=result["id"],
        public_document_id=public["id"],
        origin=result["origin"],
        model_identity=result["model_identity"],
        terminal=terminal,
        raw_final=final,
        first_final_index=final_index,
        raw_messages={str(k): v for k, v in raw_messages.items()},
        calculations=calculations,
        calculation_requests=requests,
        model_requests=invoked,
        decoder_requests=len(attempts),
        tool_calls=calls,
        raw_model_and_history_verified=True,
        independent_arithmetic_verified=True,
        no_online_answer_feedback=True,
        no_final_retry=True,
        no_HTTP_or_teacher_projection=True,
    )
