"""Registered Flash request expenses; same arithmetic, current model binding."""

from decimal import Decimal

from .plan import ARMS, MODEL, read_json, require


def cost_summary(online_directory):
    """Account from durable files, including unknown sessions without a result.json."""
    rows = []
    for registration in read_json(online_directory / "launch.json")["registrations"]:
        require(registration["requested_model"] == MODEL, "cost.fixed_flash_model")
        require(registration["arm"] in ARMS, "cost.registered_instruction_condition")
        directory = online_directory / "sessions" / registration["label"]
        turns = directory / "turns"
        reservations = [read_json(p) for p in sorted(turns.glob("*_reservation.json"))]
        outcomes = [read_json(p) for p in sorted(turns.glob("*_outcome.json"))]
        outputs = [read_json(p) for p in sorted(turns.glob("*_tool.json"))]
        numeric = [o["result"] for o in outputs if o["tool"] == "calculate" and o["status"] == "ok"]
        usage_rows = [dict(o.get("usage") or {}) for o in outcomes]
        for u in usage_rows:
            u["reasoning_tokens"] = (u.get("completion_tokens_details") or {}).get(
                "reasoning_tokens"
            )
        usage_fields = (
            "prompt_tokens",
            "completion_tokens",
            "total_tokens",
            "prompt_cache_hit_tokens",
            "prompt_cache_miss_tokens",
            "reasoning_tokens",
        )
        usage = {}
        for field in usage_fields:
            values = [
                u[field] for u in usage_rows if isinstance(u, dict) and type(u.get(field)) is int
            ]
            usage[field] = {
                "observed_sum": sum(values),
                "observed_attempts": len(values),
                "missing_attempts": len(reservations) - len(values),
                "complete_sum": sum(values) if len(values) == len(reservations) else None,
            }
        rows.append(
            {
                "label": registration["label"],
                "task_key": registration["task_key"],
                "arm": registration["arm"],
                "requested_model": registration["requested_model"],
                "reserved_attempts": len(reservations),
                "recorded_outcomes": len(outcomes),
                "public_model_responses": len(list(turns.glob("*_assistant.raw"))),
                "tool_calls": len(outputs),
                "tool_errors": sum(o["status"] != "ok" for o in outputs),
                "successful_calculations": len(numeric),
                "successful_expression_operations": sum(n["operation_count"] for n in numeric),
                "maximum_expression_dependency_depth": max(
                    (n["dependency_depth"] for n in numeric), default=0
                ),
                "http_request_bytes": sum(r["request_bytes"] for r in reservations),
                "maximum_http_request_bytes": max(
                    (r["request_bytes"] for r in reservations), default=0
                ),
                "http_response_bytes": sum(o["response_bytes"] for o in outcomes),
                "response_projection_bytes": sum(
                    p.stat().st_size for p in turns.glob("*_response_projection.json")
                ),
                "reasoning_nonempty_responses": sum(
                    o["reasoning_telemetry"]["nonempty"] is True for o in outcomes
                ),
                "reasoning_characters_observed": sum(
                    o["reasoning_telemetry"]["characters"] or 0 for o in outcomes
                ),
                "reasoning_length_unknown_responses": sum(
                    o["reasoning_telemetry"]["characters"] is None for o in outcomes
                ),
                "raw_assistant_bytes": sum(p.stat().st_size for p in turns.glob("*_assistant.raw")),
                "summed_request_elapsed_ns": sum(o["elapsed_ns"] for o in outcomes),
                "reserved_token_allowance": sum(
                    r["reserved_token_allowance"] for r in reservations
                ),
                "provider_usage": usage,
            }
        )
    additive = (
        "reserved_attempts",
        "recorded_outcomes",
        "public_model_responses",
        "tool_calls",
        "tool_errors",
        "successful_calculations",
        "successful_expression_operations",
        "http_request_bytes",
        "http_response_bytes",
        "response_projection_bytes",
        "reasoning_nonempty_responses",
        "reasoning_characters_observed",
        "reasoning_length_unknown_responses",
        "raw_assistant_bytes",
        "summed_request_elapsed_ns",
        "reserved_token_allowance",
    )
    aggregate = {field: sum(r[field] for r in rows) for field in additive}
    aggregate["maximum_http_request_bytes"] = max(r["maximum_http_request_bytes"] for r in rows)
    aggregate["provider_usage"] = {}
    for field in usage_fields:
        metrics = [r["provider_usage"][field] for r in rows]
        known = sum(m["observed_sum"] for m in metrics)
        missing = sum(m["missing_attempts"] for m in metrics)
        aggregate["provider_usage"][field] = {
            "observed_sum": known,
            "observed_attempts": sum(m["observed_attempts"] for m in metrics),
            "missing_attempts": missing,
            "complete_sum": None if missing else known,
        }
    for row in rows:
        u = row["provider_usage"]
        values = [
            u[k]["complete_sum"]
            for k in ("prompt_cache_hit_tokens", "prompt_cache_miss_tokens", "completion_tokens")
        ]
        estimate = None
        if all(v is not None for v in values):
            hit, miss, completion = map(Decimal, values)
            offpeak = (
                hit * Decimal("0.05") + miss * Decimal("1.5") + completion * Decimal("4.5")
            ) / Decimal(1000000)
            estimate = {"offpeak": str(offpeak), "peak": str(offpeak * 2)}
        row["published_rate_estimate_cny"] = estimate
        row["actual_billed_cost"] = None
    return {
        "rows": rows,
        "aggregate": aggregate,
        "all_registered_sessions_included": True,
        "summed_latency_is_not_parallel_wall_clock": True,
        "usage_missing_is_not_zero": True,
        "expression_operations_are_not_old_atomic_actions": True,
        "reasoning_is_subset_not_added_twice": True,
        "price_source": "https://api-docs.deepseek.com/zh-cn/quick_start/pricing/",
        "price_checked_date": "2026-09-09",
        "price_estimates_are_not_settled_invoices": True,
    }
