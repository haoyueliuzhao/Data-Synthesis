from trusted_synthesis.core.task.schema import TaskRequirement
from trusted_synthesis.domains.finance.iterative_agent_verifier import (
    _required_tool_failures,
)


def test_retrieve_evidence_accepts_each_registered_evidence_access_path() -> None:
    requirements = {TaskRequirement.RETRIEVE_EVIDENCE}

    for tool_id in ("search_archive", "open_document", "query_structured_fact"):
        assert not _required_tool_failures(requirements, (tool_id,))


def test_retrieve_evidence_remains_fail_closed_without_an_access_tool() -> None:
    assert _required_tool_failures(
        {TaskRequirement.RETRIEVE_EVIDENCE},
        ("calculator", "cross_check_evidence"),
    ) == ("retrieve_evidence:open_document,query_structured_fact,search_archive",)
