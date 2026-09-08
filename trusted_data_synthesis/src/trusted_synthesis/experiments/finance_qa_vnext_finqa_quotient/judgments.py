"""Explicit finite human review, not automatic financial-intent recognition.

These commitments were written after reading all 26 original Action proposals.
Full reason/subgoal quotes are attached to every annotation when instantiated.
The checker authenticates those quotes, not the correctness of human semantics.
An unspecified current object is represented as unspecified, not filled from the
selected input. That is compatible with the earlier intent review's UNKNOWN.
"""

from trusted_synthesis.domains.finance.qa_vnext.protocol import record, require

from .source import sha

# (public commitments, prior accepted Action submissions explicitly asserted).
# A proposition is a finite semantic label, not a preferred action or answer plan
# shown to a model. Numeric/period assignments below are statements by the model.
REVIEWS = {
    "J2_E_V0_02": {
        1: (
            [
                "need:options_count:2016,2017",
                "need:exercise_price:2016,2017",
                "goal:total_value_increase:2017_minus_2016",
                "current_period:unspecified",
            ],
            [],
        ),
        3: (
            [
                "read:options_value_measure_unspecified:2016",
                "goal:total_value_increase:2017_minus_2016",
            ],
            [],
        ),
        5: (
            [
                "method:per_year_count_times_price_then_2017_minus_2016",
                "current_period:unspecified",
            ],
            [],
        ),
        6: (
            [
                "assert:accepted_options_value_measure_unspecified:2017=11,2016=13",
                "method:subtract_these_2017_minus_2016_as_total_value_increase",
            ],
            [1, 3],
        ),
        8: (
            [
                "need:exercise_price:2016=source:q0n3,2017=source:q0n2",
                "basis:shares_and_exercise_prices_for_total_value_increase",
                "current_period:unspecified",
            ],
            [],
        ),
        10: (["read:exercise_price:2017=source:q0n2", "purpose:total_value:2017"], []),
        12: (
            [
                "method:per_year_count_times_price_then_2017_minus_2016",
                "current_period:unspecified",
            ],
            [],
        ),
        14: (
            [
                "method:count_times_price:2016",
                "assert:accepted_price:2016=26.93",
                "assert:accepted_count:2016=13",
                "purpose:compare_total_value:2017,2016",
            ],
            [3, 8],
        ),
        16: (
            [
                "assert:accepted_total_value:2017=366.52,2016=350.09",
                "method:total_value_2017_minus_2016",
            ],
            [12, 14],
        ),
    },
    "J2_E_V1_01": {
        1: (
            [
                "need:options_count:2016,2017",
                "purpose:count_times_price_total_value",
                "current_period:unspecified",
            ],
            [],
        ),
        3: (
            [
                "read:options_value_measure_unspecified:2016=source:t3c3n0",
                "goal:total_value_increase:2017_minus_2016",
            ],
            [],
        ),
        5: (
            [
                "method:per_year_count_times_price_then_2017_minus_2016",
                "current_period:unspecified",
            ],
            [],
        ),
        6: (
            [
                "method:per_year_count_times_price_then_2017_minus_2016",
                "assert:count:2016=13,2017=11",
                "assert:price:2016=26.93,2017=33.32",
                "current_period:unspecified",
            ],
            [],
        ),
        7: (
            [
                "need:exercise_price:2016,2017:fragment=q0",
                "method:per_year_count_times_price_then_2017_minus_2016",
                "current_period:unspecified",
            ],
            [],
        ),
        9: (
            [
                "assert:accepted_count:2017=11,2016=13",
                "assert:accepted_price:2017=33.32",
                "read:exercise_price:2016=26.93:source:q0n3",
                "method:per_year_count_times_price_then_2017_minus_2016",
            ],
            [1, 3, 7],
        ),
        11: (["method:count_times_price:2016,2017", "current_period:unspecified"], []),
        13: (
            [
                "method:count_times_price:2017",
                "assert:count:2017=11",
                "assert:price:2017=33.32",
                "purpose:compare_total_value:2017,2016",
            ],
            [],
        ),
        15: (
            [
                "method:count_times_price:2016",
                "assert:count_million:2016=13",
                "assert:price_dollar:2016=26.93",
                "goal:total_value_increase:2017_minus_2016",
            ],
            [],
        ),
        17: (
            ["assert:total_value:2017=366.52,2016=350.09", "method:total_value_2017_minus_2016"],
            [11, 15],
        ),
    },
    "J2_E_V1_02": {
        1: (
            [
                "need:exercise_price:2016,2017",
                "goal:total_value_increase:2017_minus_2016",
                "current_period:unspecified",
            ],
            [],
        ),
        3: (["read:exercise_price:2016", "goal:total_value_increase:2017_minus_2016"], []),
        5: (["read:options_count:2017:table"], []),
        7: (
            ["read:options_count_million:2016=13", "goal:total_value_increase:2017_minus_2016"],
            [],
        ),
        9: (
            [
                "method:count_times_price:2017",
                "assert:price:2017=33.32",
                "assert:count_million:2017=11",
            ],
            [],
        ),
        11: (["method:count_times_price:2016", "assert:accepted_price_and_count:2016"], [3, 7]),
        13: (
            ["method:total_value_2017_minus_2016", "assert:explicit_claim_pair:2017,2016"],
            [9, 11],
        ),
    },
}


def review_session(session):
    label = session["row"]["label"]
    proposals = {
        t["event"]["submission_count"]: t
        for t in session["turns"]
        if t["event"]["model_submission"]["kind"] == "action"
    }
    require(set(proposals) == set(REVIEWS[label]), "judgment.complete_proposal_denominator")
    annotations = []
    for index, turn in proposals.items():
        model = turn["event"]["model_submission"]
        commitments, prior = REVIEWS[label][index]
        annotations.append(
            {
                "submission": index,
                "status": "REVIEWED",
                "public_commitments": sorted(commitments),
                "explicit_prior_accepted_actions": prior,
                "reason_quote": model["reason"],
                "subgoal_quote": model["subgoal"],
                "raw_sha256": sha(turn["raw"]),
                "interpretation": "Finite post-observation manual key-commitment "
                "review; not an intent-MATCH label or financial correctness verdict.",
            }
        )
    result = record(
        "finqa_public_commitment_review",
        label=label,
        annotations=annotations,
        unblinded=True,
        quotes_auto_certify_semantic_labels=False,
        unspecified_current_object_not_inferred=True,
    )
    verify_review(session, result)
    return result


def verify_review(session, review):
    actions = {
        t["event"]["submission_count"]: t
        for t in session["turns"]
        if t["event"]["model_submission"]["kind"] == "action"
    }
    rows = review["annotations"]
    require(
        len(rows) == len(actions) and {r["submission"] for r in rows} == set(actions),
        "judgment.complete_unique_reviews",
    )
    for row in rows:
        turn = actions[row["submission"]]
        model = turn["event"]["model_submission"]
        require(
            row["reason_quote"] == model["reason"]
            and row["subgoal_quote"] == model["subgoal"]
            and row["raw_sha256"] == sha(turn["raw"]),
            "judgment.original_quotes",
        )
        require(row["status"] in {"REVIEWED", "UNDETERMINED"}, "judgment.status")
        require(isinstance(row["public_commitments"], list), "judgment.commitments")
        for prior in row["explicit_prior_accepted_actions"]:
            require(prior in actions and prior < row["submission"], "judgment.prior_action")
