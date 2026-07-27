# Data Synthesis

This repository now has two explicit project boundaries:

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
