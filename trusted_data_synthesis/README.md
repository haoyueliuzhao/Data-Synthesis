# Trusted Data Synthesis

This is the active project for constructing verifiable training data for
knowledge-intensive agents. It is intentionally domain-agnostic:

```text
Domain Adapter
-> Evidence IR v2
-> Validated Proof Graph v3 + recursive proof closure
-> Task Pattern IR + content-addressed Evidence Binding
-> Task Program DAG
-> compiled structural Difficulty Profile
-> Public Task + Oracle Contract
-> Reference Workflow + independent replay
-> Proof-Carrying Sample + Proof Certificate
-> Sample-specific Quality Contract v2 compilation
-> Contract-driven Violation Space
-> Typed Counterfactual Generation + Minimality Validation
-> Root Cause / Failure Closure Calibration
-> Real LLM Candidate Agent (Resolved / Semi-open / Open)
-> Host-Instrumented Action Plan + Host-Owned Execution Trace
-> PLAN_GIVEN / PLAN_HIDDEN trajectory normalization
-> Legacy Evaluator + Contract Runtime parity gate
-> uncalibrated five-dimensional diagnostic Quality Vector
-> advisory Quality Critic + Contract-authoritative selection
-> executable D1-D5 Training Utility MVP
```

Finance is the first validation domain. The adapter reads immutable artifacts
from `../raw_financial_data_lake` and maps graph-ready financial facts into the
shared Evidence contract. It never writes to the archive.

## Quick Start

```bash
cd "/workspace/Data Synthesis/trusted_data_synthesis"
python -m pip install -e ".[dev]"
trusted-synthesis inspect-finance --config config/finance_archive.json
trusted-synthesis sample-finance --config config/finance_archive.json --limit 3
trusted-synthesis demo-finance --config config/finance_archive.json --limit 3
trusted-synthesis finance-pilot \
  --config config/finance_archive.json \
  --pilot-config config/finance_pilot_v06_pattern_50.json \
  --output-dir artifacts/finance_pilot/v06_pattern_50
trusted-synthesis validate-task-patterns --tasks-per-domain 10
trusted-synthesis validate-counterfactuals \
  --tasks-per-domain 10 \
  --output artifacts/counterfactual_validation/v07_contract_30.json
trusted-synthesis validate-agents \
  --agent-config config/deepseek_v4_pro_agent_v08_host_regression.json \
  --output-dir artifacts/agent_validation/v08_host_regression \
  --output artifacts/agent_validation/v08_host_regression_report.json
trusted-synthesis audit-agent-capacity \
  --agent-config config/deepseek_v4_pro_agent_v08_capacity.json \
  --output data/audit/v08_agent_capacity_preflight.json
trusted-synthesis prepare-training-utility \
  --training-config config/training_utility_mvp.json \
  --agent-artifacts artifacts/agent_validation/v08_training_utility_candidates \
  --output-dir artifacts/training_utility_mvp/pilot/data

# Export flat question/target JSONL plus per-cohort Markdown review books.
trusted-synthesis export-training-utility-review \
  --input-dir artifacts/training_utility_mvp/pilot/data \
  --output-dir artifacts/training_utility_mvp/pilot/review

# Fail closed on per-domain D1-D5 capacity before spending GPU time.
trusted-synthesis audit-training-utility-readiness \
  --training-config config/training_utility_v08_1_qwen2_5_7b.json \
  --agent-artifacts artifacts/agent_validation/v08_training_utility_candidates
trusted-synthesis freeze-release-validation \
  --repo-root . \
  --artifact docs/v08_audit_remediation_report.md \
  --test-command ".venv/bin/python -m pytest -q" \
  --test-count 114 \
  --test-status passed \
  --online-status offline_only \
  --output artifacts/release_validation/v08_1.json
trusted-synthesis audit-generalization --source-root src
pytest -q
```

`validate-agents` reads credentials only from the environment variable declared by the
configuration. The checked-in smoke profile requires `DEEPSEEK_API_KEY`, pins
`deepseek-v4-pro`, performs provider model discovery, and does not silently fall back to
another model. No API key is serialized into prompts, telemetry, reports, or manifests.

The v0.8.1 compiler first binds a versioned declarative Task Pattern to a content-addressed
Evidence Binding. It deterministically expands the Task Program, computes a structural difficulty
profile, and packages the domain-rendered Public/Oracle contracts. The proof compiler then binds
each task, Evidence Bundle, Proof Graph, Task Program,
reference execution, domain plugin, and sample-specific Quality Contract into a
reproducible Proof Certificate. Public artifacts expose only the task and certificate
identity; Oracle content, gold Evidence IDs, and reference answers remain hidden.
Candidate generators receive only the public task and an evidence corpus runtime.

Quality clauses are compiled per Evidence item, Program node, answer field, citation,
and domain policy. Missing verifiers and blocked dependencies fail closed. During the
migration, the fixed evaluator and Contract Runtime run in parallel, and a decision
parity failure blocks release. See
[Proof-Carrying Quality Contracts](docs/proof_carrying_quality_contract.md).
Each mutable clause now declares versioned mutation operators. The counterfactual
planner mines executable opportunities, generates one-factor failures, validates
structural minimality, and measures detection, root-cause localization, and transitive
failure closure. See [Typed Counterfactual Engine](docs/typed_counterfactual_engine.md).
Real model candidates are generated from public task state. In the v0.8.1 host-instrumented
protocol the model chooses search constraints, Evidence, operators, inputs, parameters, and the
answer; the host executes operations and owns immutable execution IDs, observations, source
locators, and lineage. Candidates are independently replayed, projected to an explicitly
uncalibrated diagnostic Quality Vector, and optionally reviewed by an advisory model critic.
Semi-open and open tracks use a separate bounded search decision. See
[Agent-Centered Quality Validation](docs/agent_centered_quality_validation.md).
The implementation audit and current validation boundary are recorded in
[v0.8 Agent Validation Report](docs/v08_agent_validation_report.md).
The corrected D1-D5 experiment and frozen Qwen2.5-7B profile are specified in
[v0.8 Training Utility MVP](docs/v08_training_utility_mvp.md).
The first real Qwen resource and integration run is recorded in the
[v0.8 Training Utility MVP Preflight Report](docs/v08_training_utility_mvp_preflight_report.md).
The Program Skeleton/Execution Trace correction, capacity audit, and current execution boundary
are summarized in [v0.8 Refinement Report](docs/v08_refinement_report.md).
The audit-driven host loop, cohort corrections, evaluation isolation, and release provenance
changes are summarized in [v0.8.1 Audit Remediation](docs/v08_audit_remediation_report.md).
The Host-Instrumented student loop, calibrated Clause feedback, CCGR synthesis-policy update,
safe Binding tightening, six algorithm ablations, and C1-C4 causal experiment contract are
specified in [v0.9 Calibrated Clause-Guided Refinement](docs/v09_clause_guided_refinement.md).
The Pattern and Binding boundary is specified in
[Task Pattern IR and Binding Compiler](docs/task_pattern_ir.md).

The checked-in finance profile scans 100,000 facts with deterministic stratified
reservoir sampling, verifies archived source objects, and uses ten in-scope hard
distractors plus eight broad distractors per task. Its current result validates
the global resolved-track architecture; it does not establish Greater China
coverage, live-model quality, open retrieval, or production readiness.

Finance is constrained as a reference plugin rather than a framework dependency. Every release
runs the [Generalization Contract](docs/generalization_contract.md) fail-closed across Core, Runtime,
and Architecture, and must freeze a passing cross-domain Candidate Contract Suite. That suite
executes non-lookup Legal and Science programs with hard distractors and domain mutations to verify
reuse of Task DAGs, Proof Graphs, independent replay, sample-specific contracts, and the shared
Contract Runtime.
