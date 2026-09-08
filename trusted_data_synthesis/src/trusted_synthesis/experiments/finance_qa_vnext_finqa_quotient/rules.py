"""New protocol-local rule; no inherited Share state IDs or equivalence proofs."""

from trusted_synthesis.domains.finance.qa_vnext.protocol import record

VERSION = "finqa_numeric_public_behavior.v1"
BASELINE = "da2d6879d02c400f7515fa01af4308ee24d9c49b"
PARENT = "trusted_data_synthesis/artifacts/qa_vnext_finqa_binding_view/e1_j2_e_v0v1_2rep_20260908"
OUTPUT = "trusted_data_synthesis/artifacts/qa_vnext_finqa_quotient/j2_existing_20260908"
PACKAGE = "trusted_data_synthesis/src/trusted_synthesis/experiments/finance_qa_vnext_finqa_quotient"
DOCUMENT = "trusted_data_synthesis/docs/finance_qa_vnext_finqa_quotient_materialization.md"
TEST = "trusted_data_synthesis/tests/test_qa_vnext_finqa_quotient.py"
VALID = ("J2_E_V0_02", "J2_E_V1_01", "J2_E_V1_02")
MAX_SEQUENCE_LENGTH = 32768


def rule():
    return record(
        "finqa_numeric_quotient_rule",
        version=VERSION,
        epistemic_scope="finite instantiation on three already inspected successful trajectories; "
        "not data-blind confirmation and not a universal reason interpreter",
        domain="source-bound current numerical protocol, E/P/R, V0 and V1 separate populations",
        full_behavior="exact isomorphism of labeled action-resolution/proposal/Final DAGs, "
        "including source nodes and reviewed explicit public commitments",
        atomic_unit="one actual Action and its first legal Update; supported only when no "
        "intervening submission occurs. Both original model targets are retained separately",
        retain=[
            "every actual operation, exact output, source identity and actual input edge",
            "every explicit accept/reject and actual accepted-Claim producer/consumer identity",
            "every unadmitted proposal, including raw-source versus accepted-Claim distinction",
            "every unused duplicate; no dead-code elimination in full behavior",
            "manual, quote-grounded key object/period/value/method commitments; unspecified "
            "current period remains unspecified, never inferred from actual inputs",
            "order across an unadmitted proposal or rejected observation as an observed "
            "adjustment boundary, not a causal assertion",
            "explicit assertions about already accepted results as dependency edges",
            "chronology and identities of all 52 original interactions outside quotient labels",
        ],
        reductions=[
            "pure local ID renaming with bijective occurrence correspondence",
            "multiply input exchange only; subtraction remains ordered",
            "independent scheduling within adjustment-free regions, subject to data, "
            "explicit public knowledge and duplicate-predecessor edges",
            "surface wording only through explicit reviewed finite public-commitment records; "
            "no edit-distance, bag-of-words, or raw prose class keys",
        ],
        rejected_proposal_policy="retain all three observed source/Claim lifecycle violations. "
        "They propose computations before reading a required price and have distinct inputs; "
        "no proof of a semantically empty adjacent expression repair is claimed",
        duplicate_policy="retain multiplicity and predecessor edge for an earlier identical "
        "actual operation on the same input occurrences; mark actual Final ancestry separately",
        unsupported="missing/unresolved judgment review, unbound reference, unsupported action, "
        "or unsupported interleaved lifecycle => UNDETERMINED; validity and raw candidates stay",
        answer_equivalence="inherit each original valid Final finding, display its exact "
        "source expression; this alone never assigns a full-behavior state",
        mechanism_comparison="separate exact isomorphism of actual Final-support operation DAG "
        "with judgments and adjustment history omitted, explicitly NOT full behavior",
        empirical_distribution="pi_v(z|J2,Y=1)=n_vz/m_v, m_V0=1,m_V1=2; any unresolved "
        "valid mapping leaves full pi_v null and retains unresolved mass",
        task_marginal="original E1/J2 weights 1/2 each per view preserved as metadata; "
        "E1 success-conditional law not estimable from zero successes",
        materialization="exact actual HTTP messages -> exact original admitted content; "
        "whole successful trajectory packages; unadmitted content remains in raw bundle",
        representation="existing Qwen2.5-7B-Instruct local five-file/template identity and "
        "target-only mask, separate 32768-token policy, no truncation, CPU tokenizer only",
        sampling="future sampler must select condition/task/class/trajectory before units; "
        "no 49-row uniform sampler and no implemented class-weight intervention",
        new_provider_calls=0,
        student_loads=0,
        gpu_jobs=0,
        training_utility=None,
        novelty=None,
        contribution=None,
        old_mainline_resumed=False,
    )
