"""One cross-task instruction difference; original executable Harness bytes retained."""

from trusted_synthesis.experiments.finance_qa_vnext_thinking_comparison.online.common import (
    SYSTEM as BASE_SYSTEM,
)

ORIGIN_ONLINE = (
    "trusted_data_synthesis/src/trusted_synthesis/experiments/"
    "finance_qa_vnext_thinking_comparison/online"
)
TRACE_SUFFIX = """Your deliverable includes both the answer and an auditable public calculation.
Before a relevant calculation, or in the same calculation request, state the relationship you
chose, the meaning and source of its inputs, and any necessary unit handling. Use the calculate
tool to produce the result on which your final answer is based. You still choose the plan,
formula, evidence, calculation granularity, checks, and when to finish. No fixed sequence,
extra planning turn, lengthy explanation, or repeated calculation is required."""
SYSTEMS = {"A": BASE_SYSTEM, "T": BASE_SYSTEM + "\n\n" + TRACE_SUFFIX}
CAPSULE_MEMBERS = ("calculator.py", "common.py", "isolate.py", "projection.py", "worker.py")


def capsule_files(root, arm):
    """Assemble stdlib-only files; T only appends one public constant assignment.

    No executable routing, calculation, logging, termination or evaluation branch
    depends on A/T. In particular, a no-calculation Final remains terminal under T.
    No condition name or task-specific solution is added to the source document.
    """
    if arm not in SYSTEMS:
        raise ValueError("instruction.unknown_condition")
    files = {name: (root / ORIGIN_ONLINE / name).read_bytes() for name in CAPSULE_MEMBERS}
    if arm == "T":
        files["common.py"] += (
            "\n\nSYSTEM = SYSTEM + " + repr("\n\n" + TRACE_SUFFIX) + "\n"
        ).encode()
    return files
