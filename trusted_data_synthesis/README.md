# Trusted Data Synthesis

This is the active project for constructing verifiable training data for
knowledge-intensive agents. It is intentionally domain-agnostic:

```text
Domain Adapter
-> Evidence IR v2
-> Validated Proof Graph v3 + recursive proof closure
-> Public Task + Oracle Contract
-> Task Program DAG
-> Reference Compiler / Candidate Agent Workflows
-> Separate Reference and Candidate Hard Gates
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
  --pilot-config config/finance_pilot_v04.json \
  --output-dir artifacts/finance_pilot/v04_100k
trusted-synthesis audit-generalization --source-root src
pytest -q
```

The v0.4.1 pilot creates isolated public/oracle task packages and evaluates both
deterministic references and public-only candidates. Candidate generators receive
only the public task and an evidence corpus runtime. Candidate gates independently
check hard-distractor selection, source-object entailment, Program/Step alignment,
every calculation, strict answer schemas, structured claims, citations, and oracle
leakage. Workflow records contain auditable actions, tool calls, observations,
citations, and concise summaries, never hidden chain-of-thought.

The checked-in v0.4 profile scans 100,000 facts with deterministic stratified
reservoir sampling, verifies archived source objects, and uses ten in-scope hard
distractors plus eight broad distractors per task. Its current result validates
the global resolved-track architecture; it does not establish Greater China
coverage, live-model quality, open retrieval, or production readiness.

Finance is constrained as a reference plugin rather than a framework dependency. Every release
runs the [Generalization Contract](docs/generalization_contract.md) fail-closed across Core, Runtime,
and Architecture, and must freeze a passing cross-domain Candidate Contract Suite. That suite
executes non-lookup Legal and Science programs with hard distractors and domain mutations to verify
reuse of Task DAGs, Proof Graphs, independent replay, and Universal quality gates.
