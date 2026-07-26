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
  --pilot-config config/finance_pilot_small.json \
  --output-dir artifacts/finance_pilot/small_v1
pytest -q
```

The v0.3 demo creates isolated public/oracle task packages and evaluates both
deterministic references and public-only candidates. Candidate generators receive
only the public task and an evidence corpus runtime. Candidate gates independently
check retrieval, operation results, answer schemas, citations, unsupported claims,
and oracle leakage. Workflow records contain auditable actions, tool calls,
observations, citations, and concise summaries, never hidden chain-of-thought.

The small Finance Pilot adds stratified evidence sampling, six distractors per
task, four task families, controlled mutations, failure localization,
candidate-only release selection, and full-run determinism checks. Its current
result validates the global resolved-track architecture; it does not establish
Greater China coverage, live-model quality, or production readiness.
