"""Presentation-only B/R condition. The v2.1 transition method is inherited intact."""

from trusted_synthesis.domains.finance.qa_vnext.protocol import record, require
from trusted_synthesis.experiments.finance_qa_vnext_finqa_difficulty.reference_revision import (
    ReferenceExplicitRuntime,
)

PRESENTATION_VERSION = "finqa_final_recovery_feedback.v1"
TARGET_ERROR = "final.target_not_established"
REVIEW_KEY = "target_failure_review"
REVIEW_TEXT = (
    "The selected Claim establishes a numeric derivation, but has not established the "
    "target asked by the question. Compare the original question and sources with the "
    "metric, periods, unit scales, and actual inputs used. Changing Final wording, unit "
    "labels, or citations does not change the Claim's executed derivation. If correction "
    "is needed, execute and explicitly accept the new calculation before selecting the "
    "answer."
)


def verify_feedback(request, feedback_condition):
    require(feedback_condition in {"B", "R"}, "feedback.condition")
    expected = feedback_condition == "R" and request["state"]["feedback"] == TARGET_ERROR
    require(
        (request["rules"].get(REVIEW_KEY) == REVIEW_TEXT)
        if expected
        else REVIEW_KEY not in request["rules"],
        "feedback.exact_conditional_presentation",
    )
    return expected


class FinalRecoveryRuntime(ReferenceExplicitRuntime):
    def __init__(self, *args, feedback_condition, **kwargs):
        require(feedback_condition in {"B", "R"}, "feedback.condition")
        self.feedback_condition = feedback_condition
        super().__init__(*args, **kwargs)

    def request(self):
        request = super().request()
        if self.feedback_condition == "R" and self.feedback == TARGET_ERROR:
            request["rules"][REVIEW_KEY] = REVIEW_TEXT
            return record(
                "public_request",
                **{k: v for k, v in request.items() if k not in {"id", "schema_version"}},
            )
        return request
