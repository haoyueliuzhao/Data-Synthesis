import pytest

from trusted_synthesis.finance_research.contracts import digest
from trusted_synthesis.finance_research.v8_review_policy import (
    nonassertive_fragment_kind,
    policy_definition,
)


def test_policy_identity_is_static_and_independent_of_caller_mutation():
    value = policy_definition()
    assert value["id"] == digest({k: v for k, v in value.items() if k != "id"})
    value["granularity"]["action_fields"]["submit_program"].append("reason")
    assert policy_definition()["granularity"]["action_fields"]["submit_program"] == ["program"]
    assert policy_definition()["technical_validation"]["maximum_new_calls"] == 108
    assert not policy_definition()["technical_validation"]["twelve_call_pilot"]
    assert not policy_definition()["technical_validation"]["percentage_perfection_gate"]


@pytest.mark.parametrize(
    "text",
    [
        "Q: None;",
        "U: N/A.",
        "submitting the predicted program.",
        "R: I'll read the relevant table.",
        "Now submit the program.",
    ],
)
def test_only_model_selected_whole_nonassertive_examples_are_in_the_domain(text):
    assert nonassertive_fragment_kind(text) is not None


@pytest.mark.parametrize(
    "text",
    [
        "Q: None; revenue is 8.",
        "The result is correct.",
        "I verified the calculation.",
        "Submit the correct program.",
        "Revenue rose 20%.",
        "The source supports our answer.",
        "I will compute 8 minus 2.",
        "Q: maybe not correct",
    ],
)
def test_financial_verification_and_mixed_claims_cannot_use_zero_context_exception(text):
    assert nonassertive_fragment_kind(text) is None
