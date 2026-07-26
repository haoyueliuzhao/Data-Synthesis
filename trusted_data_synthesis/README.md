# Trusted Data Synthesis

This is the active project for constructing verifiable training data for
knowledge-intensive agents. It is intentionally domain-agnostic:

```text
Domain Adapter
-> Evidence Construction
-> Evidence Graph
-> Task Synthesis
-> Trajectory Generation
-> Quality Evaluation
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

The demo creates deterministic retrieval tasks and auditable trajectories. It
does not call an LLM and does not expose hidden chain-of-thought; trajectory
steps store actions, tool inputs, observations, and concise rationale summaries.
