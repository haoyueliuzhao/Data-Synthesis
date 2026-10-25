"""Static single-action labels and fixed-response probabilities for V73.

No tool is executed and no native scorer, model loader, optimizer or backward
entry is exposed here. Token groups describe the *saved generated token IDs*,
not a re-encoding of the old response or a new answer supplied to generation.
"""
from __future__ import annotations

from functools import lru_cache
import hashlib
import json
import math


ACTION_NAMES = ("list_sources", "read_source", "run_program", "submit_program")
ACTION_CATEGORIES = (
    "compliant_submit_candidate", "compliant_nonterminal_candidate",
    "attempted_invalid_submit", "plain_no_tool_call", "other_contract_failure",
)
TOKEN_GROUPS = (
    "pre_action_text", "action_structure", "program_parameter_content",
    "actual_terminal_EOS", "boundary_mixed", "post_action_whitespace",
)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
        separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def policy():
    return dict(
        schema="v73_static_action_and_fixed_target_measurement_policy.v1",
        categories=list(ACTION_CATEGORIES), token_groups=list(TOKEN_GROUPS),
        one_native_call_per_response=True,
        A="one registered statically compliant submit or nonterminal action",
        S="one statically compliant submit_program candidate",
        legal_nonterminal_action_is_not_failure=True,
        attempted_invalid_submit_requires_single_parsed_submit=True,
        malformed_envelope_or_multiple_calls_are_other_contract_failure=True,
        bare_text_submit_mentions_are_not_actual_submit_attempts=True,
        pure_syntax_only_no_program_execution=True, native_scoring=False,
        no_execution_or_correctness_claim_from_A_or_S=True,
        token_positions="zero-based positions in original raw_generated_token_ids, including actual final EOS",
        original_response_tokenization_preserved=True,
        token_byte_mapping="Qwen ByteLevel vocabulary bytes; added token literal UTF-8; exact raw-response reconstruction required",
        pre_action_text="all actual UTF-8 bytes preceding first valid native envelope",
        action_structure="native envelope, action name and JSON syntax including program string boundary quotes",
        program_parameter_content="bytes inside the original JSON program string, including literal JSON escapes",
        boundary_mixed="a saved BPE token intersects more than one byte group; never attributed exclusively to syntax or content",
        post_action_whitespace="actual trailing whitespace after the single native envelope",
        EOS="only the originally generated final stop token, not a synthetically appended token",
        empty_group_mean_is_null=True,
        teacher_forcing="original hP plus original yP prefix; never exposed to free generation",
        causal_logit_position="prompt_length + response_index - 1",
        probability="unmodified full-vocabulary float32 log_softmax; no sampling warp, temperature or vocabulary restriction",
        sequence_and_group_aggregation="saved per-token logp; each group's NLL sum/count, null mean if count=0",
        no_grad=True, backward=False,
        fixed_reference_expression_not_all_legal_expressions=True,
    )


@lru_cache(maxsize=1)
def _api():
    import finqa_v73_binding as binding
    return binding.source_v72("static_audit")._frozen_api()


def _registered_names(tools):
    require(isinstance(tools, (list, tuple)), "saved tools must be a list")
    names = []
    for tool in tools:
        require(isinstance(tool, dict) and tool.get("type") == "function", "unknown tool schema container")
        function = tool.get("function")
        require(isinstance(function, dict) and isinstance(function.get("name"), str), "unknown tool name")
        names.append(function["name"])
    require(len(names) == len(set(names)), "duplicate registered tool name")
    require(set(names) == set(ACTION_NAMES), "saved four-tool contract differs from V73")
    return set(names)


def _argument_valid(name, arguments, api):
    if name == "list_sources":
        return arguments == {}
    if name == "read_source":
        return (set(arguments) == {"source_id"} and isinstance(arguments["source_id"], str)
                and bool(arguments["source_id"]))
    if name in ("run_program", "submit_program"):
        return (set(arguments) == {"program"} and isinstance(arguments["program"], str)
                and bool(arguments["program"].strip()) and api.program_tokens(arguments["program"]) is not None)
    return False


def classification(raw_response, tools, *, api=None):
    """Classify one raw response; malformed JSON is never repaired or executed."""
    require(isinstance(raw_response, str), "raw response must be text")
    registered = _registered_names(tools)
    api = api or _api()
    _, calls = api.parse(raw_response, call_prefix="v73-static")
    reason, action = None, None
    if not calls:
        if "<tool_call" in raw_response or "</tool_call" in raw_response:
            category, reason = "other_contract_failure", "native_envelope_or_JSON_parse_failed"
        else:
            category, reason = "plain_no_tool_call", "no_native_tool_envelope"
    elif len(calls) != 1:
        category, reason = "other_contract_failure", "multiple_calls_in_single_response"
    else:
        call = calls[0]
        action = call.name
        if action not in registered:
            category, reason = "other_contract_failure", "unregistered_tool"
        elif not _argument_valid(action, call.arguments, api):
            category = "attempted_invalid_submit" if action == "submit_program" else "other_contract_failure"
            reason = "argument_container_or_pure_program_syntax_failed"
        else:
            category = "compliant_submit_candidate" if action == "submit_program" else "compliant_nonterminal_candidate"
    return dict(
        schema="v73_single_response_static_action.v1", category=category,
        A=int(category in ACTION_CATEGORIES[:2]), S=int(category == ACTION_CATEGORIES[0]),
        native_call_count=len(calls), action=action, reason=reason,
        raw_response_sha256=hashlib.sha256(raw_response.encode()).hexdigest(),
        tool_execution=0, native_scoring=0, answer_correctness=None,
    )


def completion_labels(*, response_ids, actual_eos, finish_reason, max_new_tokens, eos_ids):
    """Orthogonal receipt labels; length does not change the action category."""
    ids = list(response_ids)
    require(ids and len(ids) <= max_new_tokens, "response token count outside registered bound")
    require(bool(actual_eos) == (ids[-1] in set(eos_ids)), "actual EOS disagrees with saved IDs")
    require(finish_reason == ("stop" if actual_eos else "length"), "finish reason disagrees with EOS")
    return dict(finish_reason=finish_reason, actual_eos=bool(actual_eos),
        response_tokens=len(ids), reached_token_limit=len(ids) == max_new_tokens,
        truncated_by_token_limit=finish_reason == "length" and len(ids) == max_new_tokens,
        non_EOS_finish_before_token_limit=not actual_eos and len(ids) < max_new_tokens,
        actual_final_token_id=ids[-1])


def _member_spans(raw, start, decoder):
    obj, end = decoder.raw_decode(raw, start)
    require(isinstance(obj, dict), "expected actual JSON object")
    spans, cursor = {}, start + 1

    def skip(index):
        while index < len(raw) and raw[index] in " \t\r\n":
            index += 1
        return index

    while True:
        cursor = skip(cursor)
        if raw[cursor] == "}":
            break
        key, key_end = decoder.raw_decode(raw, cursor)
        separator = skip(key_end)
        require(raw[separator] == ":", "JSON member separator absent")
        left = skip(separator + 1)
        _, right = decoder.raw_decode(raw, left)
        spans[key] = (left, right)
        cursor = skip(right)
        if raw[cursor] == ",":
            cursor += 1
        else:
            require(raw[cursor] == "}", "JSON object closing delimiter absent")
    return obj, end, spans


@lru_cache(maxsize=1)
def _byte_level_inverse():
    # The reversible GPT-2/Qwen ByteLevel alphabet, not Unicode encode(token).
    byte_values = list(range(ord("!"), ord("~") + 1)) + list(range(161, 173)) + list(range(174, 256))
    codepoints, extra = list(byte_values), 0
    for value in range(256):
        if value not in byte_values:
            byte_values.append(value)
            codepoints.append(256 + extra)
            extra += 1
    return {chr(code): value for value, code in zip(byte_values, codepoints, strict=True)}


def _token_bytes(tokenizer, token_id, added_ids):
    token = tokenizer.convert_ids_to_tokens(int(token_id))
    require(isinstance(token, str), "saved token has no vocabulary entry")
    if token_id in added_ids:
        return token.encode("utf-8")
    inverse = _byte_level_inverse()
    require(all(char in inverse for char in token), "token outside frozen Qwen ByteLevel alphabet")
    return bytes(inverse[char] for char in token)


def annotate_parent_target(tokenizer, response_ids, raw_response, *, eos_ids, actual_eos, tools, api=None):
    """Freeze group positions on actual parent response IDs without retokenizing.

    Token/character boundaries can differ. Classification uses UTF-8 byte spans
    and explicitly retains mixed-boundary BPE tokens as their own group.
    """
    api = api or _api()
    label = classification(raw_response, tools, api=api)
    require(label["category"] == "compliant_submit_candidate", "parent target is not a static compliant submit")
    ids = [int(value) for value in response_ids]
    require(bool(ids), "empty saved parent target")
    eos_set = set(eos_ids)
    require(bool(actual_eos) == (ids[-1] in eos_set), "parent EOS receipt and token IDs disagree")
    body_ids = ids[:-1] if actual_eos else ids
    require(not any(value in eos_set for value in body_ids), "unexpected early stop token in parent target")
    require(tokenizer.decode(body_ids, skip_special_tokens=False,
        clean_up_tokenization_spaces=False) == raw_response, "saved parent response decode mismatch")
    first = raw_response.index("<tool_call>")
    decoder = api.decoder()
    start = first + len("<tool_call>")
    while raw_response[start] in " \t\r\n":
        start += 1
    _, json_end, members = _member_spans(raw_response, start, decoder)
    _, _, arguments = _member_spans(raw_response, members["arguments"][0], decoder)
    content_left, content_right = arguments["program"]
    require(raw_response[content_left] == raw_response[content_right - 1] == '"', "program target is not a JSON string")
    content_left, content_right = content_left + 1, content_right - 1
    close = json_end
    while raw_response[close] in " \t\r\n":
        close += 1
    require(raw_response.startswith("</tool_call>", close), "parent closing envelope absent")
    envelope_end = close + len("</tool_call>")
    require(not raw_response[envelope_end:].strip(), "unexpected text after parent envelope")

    byte_offset = lambda char: len(raw_response[:char].encode("utf-8"))
    spans = {
        "pre_action_text": [(0, byte_offset(first))],
        "action_structure": [(byte_offset(first), byte_offset(content_left)),
                             (byte_offset(content_right), byte_offset(envelope_end))],
        "program_parameter_content": [(byte_offset(content_left), byte_offset(content_right))],
        "post_action_whitespace": [(byte_offset(envelope_end), len(raw_response.encode("utf-8")))],
    }
    added_ids = set(tokenizer.get_added_vocab().values())
    token_bytes = [_token_bytes(tokenizer, value, added_ids) for value in body_ids]
    require(b"".join(token_bytes) == raw_response.encode("utf-8"), "actual ByteLevel token bytes do not reconstruct parent response")
    groups, boundaries, cursor = {name: [] for name in TOKEN_GROUPS}, [], 0
    for index, (token, raw) in enumerate(zip(body_ids, token_bytes, strict=True)):
        left, right = cursor, cursor + len(raw)
        require(right > left, "empty actual token byte interval")
        intersections = sorted(name for name, intervals in spans.items()
            if any(left < end and right > begin for begin, end in intervals))
        require(bool(intersections), "saved token is outside all frozen groups")
        group = intersections[0] if len(intersections) == 1 else "boundary_mixed"
        groups[group].append(index)
        boundaries.append(dict(position=index, token_id=token, byte_start=left,
            byte_end=right, group=group, intersected_groups=intersections))
        cursor = right
    if actual_eos:
        groups["actual_terminal_EOS"].append(len(ids) - 1)
        boundaries.append(dict(position=len(ids) - 1, token_id=ids[-1], byte_start=None,
            byte_end=None, group="actual_terminal_EOS", intersected_groups=["actual_terminal_EOS"]))
    require(sorted(p for positions in groups.values() for p in positions) == list(range(len(ids))), "token groups do not partition saved response")
    output = dict(schema="v73_actual_parent_target_token_groups.v1", policy_id=digest(policy()),
        raw_response_sha256=hashlib.sha256(raw_response.encode()).hexdigest(),
        response_token_ids_sha256=digest(ids), response_token_count=len(ids),
        actual_eos=bool(actual_eos), eos_token_id=ids[-1] if actual_eos else None,
        position_groups=groups, group_token_counts={k: len(v) for k, v in groups.items()},
        byte_spans=spans, token_boundaries=boundaries, original_tokenization_preserved=True,
        label=label)
    output["id"] = digest(output)
    return output


def target_logps_from_logits(logits, target_ids, *, position_chunk_size=64):
    """Logits are already causally aligned, [target positions, full vocabulary]."""
    import torch
    require(position_chunk_size > 0, "nonpositive log-softmax position block")
    if logits.ndim == 3:
        require(logits.shape[0] == 1, "only one probability sequence is authorized per input")
        logits = logits[0]
    ids = list(target_ids)
    require(logits.ndim == 2 and logits.shape[0] == len(ids), "target/logit alignment mismatch")
    require(all(type(i) is int and 0 <= i < logits.shape[1] for i in ids), "target ID outside full vocabulary")
    values = []
    with torch.no_grad():
        for start in range(0, len(ids), position_chunk_size):
            stop = min(start + position_chunk_size, len(ids))
            block = logits[start:stop].detach().float()
            require(bool(torch.isfinite(block).all()), "nonfinite raw logits")
            target = torch.tensor(ids[start:stop], dtype=torch.long, device=block.device)
            logps = torch.log_softmax(block, dim=-1).gather(1, target[:, None]).squeeze(1)
            values.extend(logps.cpu().tolist())
    require(all(math.isfinite(value) and value <= 0 for value in values), "invalid original-logit target probability")
    return values


def causal_target_logps(logits, *, prompt_length, response_ids, position_chunk_size=64):
    """Select the logit immediately *before* each actual response target token."""
    require(prompt_length > 0, "empty prompt has no preceding causal logit")
    if logits.ndim == 3:
        require(logits.shape[0] == 1, "expected single-sequence raw logits")
        logits = logits[0]
    stop = prompt_length + len(response_ids) - 1
    require(logits.shape[0] >= stop, "response targets exceed available causal logits")
    return target_logps_from_logits(logits[prompt_length - 1:stop], response_ids,
        position_chunk_size=position_chunk_size)


def summarize_token_logps(logps, grouping):
    """Retain empty groups as NA and forbid overlapping or dropped positions."""
    values = [float(value) for value in logps]
    require(len(values) == grouping["response_token_count"], "probability target count changed")
    require(all(math.isfinite(value) and value <= 0 for value in values), "unknown/nonfinite target probability")
    groups = grouping["position_groups"]
    require(set(groups) == set(TOKEN_GROUPS), "frozen probability groups changed")
    require(sorted(p for positions in groups.values() for p in positions) == list(range(len(values))), "overlapping or missing probability positions")
    summaries = {}
    for name in TOKEN_GROUPS:
        positions = groups[name]
        nll = -math.fsum(values[index] for index in positions)
        summaries[name] = dict(token_count=len(positions), nll_sum=nll if positions else None,
            mean_nll=nll / len(positions) if positions else None,
            status="MEASURED" if positions else "NA")
    return dict(schema="v73_fixed_parent_response_grouped_log_probability.v1",
        grouping_id=grouping["id"], policy_id=grouping["policy_id"],
        target_token_count=len(values), token_logps=values, groups=summaries,
        total_nll=-math.fsum(values), total_mean_nll=-math.fsum(values) / len(values) if values else None,
        full_vocabulary_log_softmax=True, temperature_applied=False,
        tool_execution=0, native_scoring=0, optimizer_updates=0, backward_calls=0)
