"""Explicit, post-observation rules for the finite development panel."""

from ..finance_qa_vnext_model_execution.models import record

STAGE = "finance_qa_vnext_panel_correction_aware_finite_quotient_measurement_only"


def quotient_rule():
    return record(
        "panel_quotient_rule",
        stage=STAGE,
        version="correction_aware_finite.v1",
        epistemic_scope="known observed development trajectories; not data-blind confirmation",
        base_semantics="unchanged finite_projection.nodes and final, exact labeled DAG isomorphism",
        clean_extension=(
            "append empty retained_interactions; prove twelve old projections compatible"
        ),
        no_effect=(
            "Every rejected event has no execution/observation/claim/final; the complete State "
            "is unchanged except identity, feedback, and exactly one submission; adjacent States "
            "join exactly, public Context and candidate offers stay unchanged, nearest admitted "
            "successor is used. The original seven rejected events and budget effects remain bound."
        ),
        action_alignment=(
            "Same operation, ordered inputs, parameters, selected offer, goal and public judgment; "
            "only a proper subset of existing offered Evidence basis is completed to exact basis. "
            "No new accepted knowledge and no intervening admitted event."
        ),
        final_alignment=(
            "Same already accepted answer Claim, Context, goal, nearest admitted Final "
            "and existing information. For public_program_answer, value/output stays exact, "
            "citations stay a set, only forbidden redundant result_context metadata is trimmed. "
            "For share_percent_quantized, value is either the exact existing Claim string "
            "or its explicit Decimal final_quantum ROUND_HALF_EVEN projection; admitted Final "
            "must be that projection. Extra metadata must equal existing Claim output. "
            "Citation supersets may only add then-public Evidence or accepted Claim references "
            "and must retain exact answer lineage. No numeric tolerance."
        ),
        retained_proposal=(
            "A rejected public Action proposal followed by a different admitted Action is retained "
            "with then-public candidates/information, semantic proposal, violated field paths, "
            "feedback relation and nearest actual successor producer, explicit accepted Claim and "
            "later actual execution of the proposed operation/inputs. Retain their observed order "
            "without inventing a data dependency or causal account. No crossing an intervening "
            "sum to call the later ratio a direct correction. All actual nodes, Updates "
            "and input/decision dependencies remain, including unused semantic operations."
        ),
        repeat_rule=(
            "Consecutive identical semantic proposals with identical public information "
            "and diagnostic relation collapse only their multiplicity in retained_interactions; "
            "all raw events remain in interpretation ledger. Distinct proposal changes remain "
            "ordered. Error counts, opaque event IDs, costs and free-form error wording "
            "do not themselves define solving classes."
        ),
        fallback=(
            "undetermined for any unsupported event or unproved reduction; never clear old ledger"
        ),
        class_identity=(
            "finite source-bound reference established by correspondence/difference witnesses, "
            "not graph hash alone"
        ),
        nonclaims=[
            "feedback has no causal effect",
            "accepted knowledge revision",
            "universal task classes",
            "Contribution",
            "Student benefit",
            "VTDO weight update",
            "blind generalization",
        ],
    )
