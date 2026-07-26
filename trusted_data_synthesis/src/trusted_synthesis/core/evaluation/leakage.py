from __future__ import annotations

import json

from pydantic import BaseModel, ConfigDict

from trusted_synthesis.core.task.schema import TaskOracleContract
from trusted_synthesis.core.trajectory.schema import ActionType, Trajectory


class LeakageVerification(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    passed: bool
    failures: tuple[str, ...]


class OracleLeakageChecker:
    _forbidden_keys = {
        "evidence_ids",
        "gold_evidence_ids",
        "oracle",
        "oracle_contract",
        "program_id",
        "proof_graph_id",
        "proof_graph_hash",
    }

    def verify(self, oracle: TaskOracleContract, candidate: Trajectory) -> LeakageVerification:
        failures: list[str] = []
        search_seen = False
        for step in candidate.steps:
            if not search_seen:
                sensitive_payload = {
                    "tool_input": step.tool_input,
                    "rationale_summary": step.rationale_summary,
                }
                if step.action != ActionType.SEARCH:
                    sensitive_payload.update(
                        {
                            "observation": step.observation,
                            "evidence_ids": step.evidence_ids,
                        }
                    )
                serialized = json.dumps(sensitive_payload, ensure_ascii=False, default=str)
                for evidence_id in oracle.gold_evidence_ids:
                    if evidence_id in serialized:
                        failures.append(f"gold_evidence_before_retrieval:{step.step_index}")
            forbidden = self._find_forbidden_keys(step.tool_input)
            if forbidden:
                failures.append(
                    f"forbidden_oracle_query_keys:{step.step_index}:{','.join(forbidden)}"
                )
            if step.action == ActionType.SEARCH:
                search_seen = True
        return LeakageVerification(passed=not failures, failures=tuple(failures))

    def _find_forbidden_keys(self, value) -> tuple[str, ...]:
        found: set[str] = set()
        if isinstance(value, dict):
            for key, item in value.items():
                if str(key) in self._forbidden_keys:
                    found.add(str(key))
                found.update(self._find_forbidden_keys(item))
        elif isinstance(value, list | tuple):
            for item in value:
                found.update(self._find_forbidden_keys(item))
        return tuple(sorted(found))
