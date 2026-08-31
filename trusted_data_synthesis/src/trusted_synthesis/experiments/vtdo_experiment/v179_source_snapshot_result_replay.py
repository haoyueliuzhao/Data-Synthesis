from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_capability_all_typed_rejection_public_feedback_runtime as step_runtime,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_capability_job_bound_multistep_outcome_preflight as v179,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_capability_job_bound_multistep_outcome_preflight_runtime as runtime,
)
from trusted_synthesis.runtime.agent.prospective_qualified_final_response_grammar import (
    compile_qualified_final_response_grammar,
)
from trusted_synthesis.runtime.agent.prospective_semantic_action_response_grammar import (
    compile_semantic_action_response_grammar,
)


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def replay(*, package_root: Path, output_path: Path) -> None:
    if output_path.exists():
        raise FileExistsError(f"v26.179 snapshot replay output exists:{output_path}")
    source_root = (package_root / "src").resolve()
    for module in (v179, runtime, step_runtime):
        module_path = Path(module.__file__ or "").resolve()
        if not module_path.is_relative_to(source_root):
            raise ValueError("v26.179 replay imported a module outside the extracted snapshot")
    frozen = v179._predecessor_freeze(package_root)  # noqa: SLF001
    profile = v179._generation_profile(package_root, frozen.source).profile  # noqa: SLF001
    contract = v179._outcome_contract()  # noqa: SLF001
    feedback_id, rejection_id = v179._v177_public_parent_ids(package_root)  # noqa: SLF001
    manifest = v179._manifest(  # noqa: SLF001
        predecessor=frozen.source,
        profile=profile,
        contract=contract,
        public_feedback_contract_id=feedback_id,
        rejection_surface_id=rejection_id,
    )
    catalog = runtime.runtime_catalog(frozen.source)
    action_grammar = compile_semantic_action_response_grammar()
    final_grammar = compile_qualified_final_response_grammar()
    rows: list[dict[str, Any]] = []
    for job in manifest.jobs:
        context = runtime.prepare_job(job, catalog)
        state = runtime._initialize(context)  # noqa: SLF001
        while state.current_index < len(state.ordered_components):
            component_index = state.current_index
            prompt = step_runtime.render_next_prompt(state)
            dispositions = runtime._candidate_dispositions(state, prompt)  # noqa: SLF001
            selection = runtime._reference_selection(  # noqa: SLF001
                state,
                prompt,
                dispositions,
                component_index,
            )
            action = runtime._parse_action_response(  # noqa: SLF001
                prompt,
                selection,
                grammar=action_grammar,
                profile=profile,
            )
            if action is None or not getattr(
                step_runtime.step(state, action),
                "action_accepted",
                False,
            ):
                raise ValueError("v26.179 snapshot reference Action did not commit")
        result = step_runtime.finalize(state)
        runtime._parse_final_fixture(  # noqa: SLF001
            result,
            context.source,
            grammar=final_grammar,
            profile=profile,
        )
        rows.append(
            {
                "job_id": job.job_id,
                "source_package_artifact_id": job.source_package_artifact_id,
                "replica_index": job.replica_index,
                "result": result.model_dump(mode="json", warnings=False),
            }
        )
    if len(rows) != 192 or len({item["job_id"] for item in rows}) != 192:
        raise ValueError("v26.179 snapshot Result denominator differs")
    payload = {
        "manifest_id": manifest.manifest_id,
        "row_count": len(rows),
        "rows": rows,
        "provider_calls": 0,
        "schema_version": "v179_source_snapshot_result_replay.v1",
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("xb") as stream:
        stream.write((_canonical_json(payload) + "\n").encode("utf-8"))
        stream.flush()
        os.fsync(stream.fileno())


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--package-root", type=Path, required=True)
    parser.add_argument("--output-path", type=Path, required=True)
    args = parser.parse_args()
    replay(package_root=args.package_root.resolve(), output_path=args.output_path.resolve())


if __name__ == "__main__":
    main()
