# VTDO Finance Research

The current development entry is
[`trusted_synthesis.finance_research`](trusted_data_synthesis/src/trusted_synthesis/finance_research):
original **FinQA** tasks, a restricted **BigFinance-derived** tool loop, real local
Student token receipts, and the existing anchored AdamW / C / N / π research kernel.
**TAT-QA** is reserved for external evaluation; **FinanceMath** accepts an authorized
local snapshot but is not downloaded automatically. The original experiment results
are retained, not reclassified as evidence for this new harness.

See the [refactor and operating guide](trusted_data_synthesis/docs/finance_research_refactor_20260928.md)
for what is implemented, what has actually been tested, and what still needs research
admission. The [new CLI](trusted_data_synthesis/src/trusted_synthesis/finance_research/cli.py)
separates import, role planning, generation sealing, and private native scoring.

```bash
cd trusted_data_synthesis
python -m pip install -e ".[research]"
vtdo-finance catalog
vtdo-finance preflight --output /tmp/vtdo-finance-preflight-unique
```

`preflight` is a synthetic zero-model integration control, not a benchmark result.
Real API/GPU runs require an explicit `run` command. New API calls use only
`deepseek-flash`; an API response cannot stand in for a local differentiable receipt.

## Retained infrastructure and historical experiments

This repository retains two explicit infrastructure boundaries:

```text
raw_financial_data_lake/   archived finance data-production system
trusted_data_synthesis/    active domain-agnostic synthesis framework
```

`raw_financial_data_lake` remains the source of frozen raw objects, normalized
facts, and versioned knowledge-graph artifacts. New framework development lives
in `trusted_data_synthesis`. The active project reads published archive artifacts
through a read-only Finance Adapter; it does not import or mutate `finraw`
internals.

See [Architecture](trusted_data_synthesis/docs/architecture.md) and
[Archive Contract](trusted_data_synthesis/docs/archive_contract.md). After a
server migration, use the checked recovery procedure in
[Migrated Server Recovery](trusted_data_synthesis/docs/server_recovery.md).
