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
-> Candidate Agent Workflow
-> Legacy Evaluator + Contract Runtime parity gate
-> Candidate-aware Release Selection
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
trusted-synthesis audit-generalization --source-root src
pytest -q
```

The v0.7.0 compiler first binds a versioned declarative Task Pattern to a content-addressed
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
