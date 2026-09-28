"""Evidence-derived call settlement; unknown calls are never sealed as complete."""

from .contracts import CallSettlement, ContextLimitError, ProviderCallError

MODEL_TERMINALS = {
    "final_answer",
    "max_steps",
    "context_exceeded",
    "no_tool_call",
    "multiple_tool_calls",
}


def counter_delta(before, after):
    return (
        after - before if type(before) is int and type(after) is int and after >= before else None
    )


def failed_call(error, *, before, after, request_sha256, attempt_index):
    actual = counter_delta(before, after)
    evidence = {"exception_type": type(error).__name__, "message": str(error)}
    if isinstance(error, ProviderCallError):
        state = error.settlement
        evidence.update(error.evidence)
        if error.actual_model_calls is not None:
            if actual is not None and actual != error.actual_model_calls:
                state = "unknown"
                evidence["counter_conflict"] = True
            else:
                actual = error.actual_model_calls
    elif actual == 0:
        state = "pre_call_rejected"
    else:
        state = "unknown"
    # A context exception after a request has started is not evidence of no charge.
    if isinstance(error, ContextLimitError) and actual != 0:
        state = "unknown"
    return CallSettlement(
        attempt_index=attempt_index,
        state=state,
        actual_model_calls=actual,
        request_sha256=request_sha256,
        evidence=evidence,
    )


def calls_settled(records, attempts, actual_calls):
    if len(records) != attempts or [row.attempt_index for row in records] != list(range(attempts)):
        return False
    if any(row.state == "unknown" or row.actual_model_calls is None for row in records):
        return False
    if actual_calls is None or sum(row.actual_model_calls for row in records) != actual_calls:
        return False
    return all(row.actual_model_calls == 0 for row in records if row.state == "pre_call_rejected")


def episode_is_complete(episode):
    """Model terminal != infrastructure terminal; both need truthful settlement."""
    return (
        episode.stop_reason in MODEL_TERMINALS
        and episode.all_provider_calls_settled is True
        and calls_settled(
            episode.call_settlements, episode.provider_attempts, episode.actual_model_calls
        )
        and sum(row.state == "returned" for row in episode.call_settlements) == len(episode.turns)
    )
