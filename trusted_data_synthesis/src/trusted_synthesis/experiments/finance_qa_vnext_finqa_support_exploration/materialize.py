"""Original supervision from the new population, separate from graph determinacy."""

from trusted_synthesis.domains.finance.qa_vnext.protocol import record, require
from trusted_synthesis.experiments.finance_qa_vnext_finqa_quotient.source import (
    candidate as old_candidate,
)
from trusted_synthesis.experiments.finance_qa_vnext_harness_responsibility.audit import manifest

from .source import bind_turn, read


def load_session(directory, registration, audit, *, model_required=True):
    require(audit["complete_valid"], "materialize.complete_valid_only")
    manifest(directory)
    require(read(directory / "audit.json") == audit, "materialize.saved_audit")
    if model_required:
        require(audit["model_origin_verified"], "materialize.model_origin")
    turns = [
        bind_turn(directory, i, registration, model_required=model_required)
        for i in range(audit["submissions"])
    ]
    require(turns[-1]["event"]["terminal"], "materialize.complete_terminal")
    row = {**registration, "registration": registration, "complete_valid": True}
    return {"row": row, "audit": audit, "turns": turns}


def candidate(session, turn):
    row = old_candidate(session, turn)
    return record(
        "support_original_candidate",
        **{k: v for k, v in row.items() if k not in {"id", "schema_version", "task_key"}},
        task_key=session["row"]["task_key"],
        exploration_stratum=session["row"]["exploration_stratum"],
        original_N_D_prompt_preserved=True,
        old_candidate_reused=False,
    )
