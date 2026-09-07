"""Post-observation typed retention, not relaxation of original generation or QA."""

from ..finance_qa_vnext_model_execution.models import record
from ..finance_qa_vnext_panel_quotient.rules import quotient_rule as prior_rule

STAGE = "finance_qa_vnext_support_transition_and_grounding_assertion_measurement_only"


def measurement_rule():
    return record(
        "support_transition_rule",
        stage=STAGE,
        version="support_transition_grounding_assertion.v1",
        extends_rule_id=prior_rule()["id"],
        epistemic_scope=(
            "finite measurement extension on already observed development trajectories, "
            "not blind confirmation"
        ),
        original_generation_qualification_or_rule_mutated=False,
        baseline=(
            "copy all actual nodes and Final; reuse all fourteen already resolved "
            "event interpretations verbatim"
        ),
        support_transition=(
            "Retain the unadmitted disclosed-total proposal, public offers, original judgment "
            "and rejection. Prove no execution/Observation/accepted Claim only within the "
            "unadmitted interval up to its nearest admitted successor. Bind that actual sum, "
            "independent accept Update, new total Claim and subsequent actual reconstructed "
            "ratio using it. The same ratio obligation, operation contract, parameters and "
            "numerator are bound, but both different denominator inputs are retained, never "
            "equated. Proposal-to-sum is observed order, sum-Claim-to-ratio is real data "
            "dependency. Actual reconstruction changes State. No prior executed D or "
            "accepted-knowledge retraction is invented."
        ),
        grounding_assertion=(
            "For one existing accepted answer Claim, bind its actual lineage separately "
            "from every submitted Final citation set across the entire Final segment, "
            "including intervening ordinary alignments and the admitted terminal Final. "
            "Record exact missing=L-C and extra=C-L, raw feedback, before/after State and "
            "budget for every event. Incorrect public Evidence substitutions are retained "
            "as assertion states, never actual uses edges. Require the unchanged existing "
            "Claim numeric projection/metadata contract; do not change citations to test it. "
            "Only already public references are interpreted; otherwise remain undetermined."
        ),
        assertion_normal_form=(
            "The full segment ledger keeps every declared set, result and feedback. In its "
            "behavioral assertion sequence, ordinary legacy-proved full-lineage redundant "
            "citations retain their already nonclassifying status and normalize to L; "
            "incorrect missing/substituted Evidence sets remain exact semantic assertions. "
            "Collapse only consecutive identical normalized assertion states. Retain their "
            "ordered returns to incorrect assertions, rejection of incorrect assertions, "
            "and the final admitted same-Claim assertion equal to L. This does not claim "
            "ordinary intermediate submissions were admitted. Raw feedback remains in ledger."
        ),
        normalization=(
            "Existing alpha-renaming and registered set rules apply. Consecutive identical "
            "proposal multiplicity is nonclassifying while every source event remains. "
            "Different Evidence roles, Claim producers, actual actions, public judgments "
            "or nonconsecutive grounding-assertion changes are not normalized away."
        ),
        e04_compatibility=(
            "entire previously supported behavior and eleven interpretations unchanged"
        ),
        fallback=(
            "unbound effects, unknown result representation or unsupported relation "
            "remain undetermined"
        ),
        difference_authority=(
            "exact full graph correspondence plus explicit actual denominator "
            "production-consumption contrast"
        ),
        forbidden_inferences=[
            "feedback caused internal strategy change",
            "D proposal was executed",
            "accepted knowledge was retracted",
            "profile name defines a class",
            "more errors imply useful diversity",
            "Student benefit or Contribution",
        ],
    )
