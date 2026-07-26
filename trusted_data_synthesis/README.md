# Trusted Data Synthesis

This is the active project for constructing verifiable training data for
knowledge-intensive agents. It is intentionally domain-agnostic:

```text
Domain Adapter
-> Evidence IR v2
-> Task-local Proof Graph
-> Public Task + Oracle Contract
-> Task Program DAG
-> Reference / Candidate Workflows
-> Hard Gates + Quality Diagnostics
-> Release Selection
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
pytest -q
```

The v0.2 demo creates isolated public/oracle task packages and independently
verified reference workflows. Candidate generators receive only the public task
and a tool runtime. It does not expose hidden chain-of-thought; workflow steps
store actions, tool calls, observations, citations, and concise summaries.
