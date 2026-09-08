"""Prospectively scoped human review input and quote checks, never auto-certification."""

from trusted_synthesis.domains.finance.qa_vnext.protocol import record, require
from trusted_synthesis.experiments.finance_qa_vnext_finqa_quotient.source import sha
from trusted_synthesis.experiments.finance_qa_vnext_finqa_reason_policy.runtime import decode


def actions(session):
    selected = {}
    for turn in session["turns"]:
        try:
            value = decode(turn["raw"])
        except (ValueError, TypeError):
            continue
        if value.get("kind") == "action":
            selected[turn["event"]["submission_count"]] = (turn, value)
    return selected


def template(session):
    return record(
        "support_public_review",
        label=session["row"]["label"],
        annotations=[
            {
                "submission": index,
                "status": "UNDETERMINED",
                "public_commitments": [],
                "explicit_prior_accepted_actions": [],
                "reason_quote": value.get("reason"),
                "subgoal_quote": value.get("subgoal"),
                "raw_sha256": sha(turn["raw"]),
                "interpretation": "Awaiting finite human interpretation under frozen rubric.",
            }
            for index, (turn, value) in actions(session).items()
        ],
        unblinded=True,
        quotes_auto_certify_semantic_labels=False,
    )


def verify_review(session, review):
    expected = actions(session)
    rows = review["annotations"]
    require(
        len(rows) == len(expected) and {r["submission"] for r in rows} == set(expected),
        "judgment.complete_unique_reviews",
    )
    for row in rows:
        turn, value = expected[row["submission"]]
        require(
            row["reason_quote"] == value.get("reason")
            and row["subgoal_quote"] == value.get("subgoal")
            and row["raw_sha256"] == sha(turn["raw"]),
            "judgment.original_quotes",
        )
        require(row["status"] in {"REVIEWED", "UNDETERMINED"}, "judgment.status")
        require(
            isinstance(row["public_commitments"], list)
            and all(isinstance(c, str) and c for c in row["public_commitments"]),
            "judgment.commitments",
        )
        require(
            row["status"] != "REVIEWED" or row["public_commitments"],
            "judgment.no_silent_empty_review",
        )
        for prior in row["explicit_prior_accepted_actions"]:
            require(prior in expected and prior < row["submission"], "judgment.prior_action")
