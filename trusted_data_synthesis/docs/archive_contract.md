# Finance Archive Contract

## Read-only Rule

`raw_financial_data_lake` is an archived producer. The new project may read only
published artifacts named in `config/finance_archive.json`. It must not import
`finraw`, connect with write privileges, update archive metadata, or place new
outputs below the archive root.

## Required Inputs

```text
kg_build_report.json
kg_nodes.jsonl
kg_edges.jsonl
canonical_entities.parquet
metrics.parquet
source_registry.parquet
source_metric_definitions.parquet
```

The adapter rejects an archive when:

- any artifact is missing;
- the KG quality gate is not `passed`;
- the KG build ID differs from the explicitly pinned build;
- the graph schema version differs from the pinned contract;
- a Fact node is inactive, not graph-ready, forecast when excluded, or has an
  unaccepted verification status.

## Mapping

| Finance archive | Shared contract |
| --- | --- |
| canonical entity | SubjectRef |
| metric ontology | predicate + SemanticDefinitionRef |
| standardized Fact node | EvidenceItem |
| normalized value | ScalarObservation payload |
| period fields | TemporalContext |
| source registry | SourceRef |
| raw object / URL | SourceLocator |
| build IDs | ProvenanceRef |

The current archive contains 658,535 graph-ready Fact nodes in KG schema 3.0.
The adapter streams these records and loads only small catalogs in memory. No
raw document, KG, or fact file is duplicated.

## Version Policy

Every Evidence item freezes the KG build, standardized-fact build, source
record, source definition, and raw object identity. A later archive release is a
new input version; it never mutates Evidence identities already published by the
active framework.
