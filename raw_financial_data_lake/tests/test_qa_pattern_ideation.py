from finraw.qa.pattern_ideation import (
    PATTERN_IDEATION_VERSION,
    generate_pattern_ideas,
)


class _IdeaProvider:
    last_telemetry = {"http_success": True, "json_valid": True}

    def generate(self, request):
        base = request["base_pattern_ids"][0]
        return [
            {
                "idea_version": PATTERN_IDEATION_VERSION,
                "base_pattern_id": base,
                "metric_ids": ["revenue", "net_income"],
                "intent_family": "consistency_check",
                "novelty_axis": "metric_pair",
                "rationale": "Compare growth and profitability signals.",
            },
            {
                "idea_version": PATTERN_IDEATION_VERSION,
                "base_pattern_id": "invented_pattern",
                "metric_ids": ["future_alpha"],
                "intent_family": "prediction",
                "novelty_axis": "fiction",
                "rationale": "Invent a forecast.",
            },
        ]


def test_pattern_ideation_is_registry_bounded_and_advisory_only():
    report = generate_pattern_ideas(
        ["revenue", "net_income"],
        {"maximum_ideas": 5},
        provider=_IdeaProvider(),
    )

    assert report["mode"] == "advisory_only"
    assert report["requires_deterministic_compilation"] is True
    assert len(report["accepted_ideas"]) == 1
    assert len(report["rejected_ideas"]) == 1
    assert {
        "idea_base_pattern_unknown",
        "idea_metric_ids_invalid",
        "idea_intent_family_invalid",
        "idea_novelty_axis_invalid",
    } <= set(report["rejected_ideas"][0]["errors"])
    assert report["manifest"]["manifest_hash"]
