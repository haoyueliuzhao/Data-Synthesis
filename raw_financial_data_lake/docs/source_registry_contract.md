# Source Registry Contract

## Authority

`SOURCE_REGISTRY_SEED` is the canonical identity registry for external data sources. `finraw.source_registry` derives all runtime identity sets from that seed and exposes the contract used by configuration, QA market filtering, FinSearchComp alignment, and regional audits.

A persisted `source_id` must be a member of `CANONICAL_SOURCE_IDS`. Provider names, filenames, connector labels, and dataset descriptions are not Source IDs.

## Greater China Sources

The production Greater China QA set is centrally defined as `GREATER_CHINA_QA_SOURCE_IDS` and currently contains:

```text
bse_disclosures
bse_market_statistics
cninfo_announcements
csi_index_publications
hkex_disclosures
nbs_official_statistics
pboc_official_statistics
safe_official_statistics
sse_market_statistics
szse_market_statistics
```

QA profiles inherit this set. They may provide an explicit canonical subset, but they do not duplicate the complete list.

## Deprecated Aliases

The following values were stale profile IDs and never existed in the live Source Registry:

```text
hkex_announcements → hkex_disclosures
nbs_publications → nbs_official_statistics
pboc_publications → pboc_official_statistics
safe_publications → safe_official_statistics
```

They are retained only as migration aliases for old configuration files. New profiles must use canonical IDs. Persisted Raw Objects, Facts, KG nodes, and QA lineage must never use deprecated aliases.

## Config Boundary

`load_config()` canonicalizes all registered source-bearing fields after profile inheritance and secret merging. It handles scalar IDs, source lists, per-source quality maps, and `source_id:record_type` quality keys.

```text
known canonical ID → accepted
known deprecated alias → canonicalized
unknown ID → configuration load fails
```

This prevents a misspelled or retired Source ID from silently yielding an empty quota pool or incorrect market classification.

## Runtime Consumers

The following components share this contract:

```text
QA Greater China source pools
FinSearchComp current-market classification
regional share audits
quality-gate per-source maps
annual filing source lists
official publication source contracts
```

Multi-region sources such as World Bank and IMF remain separate from Greater China-only sources. Their regional assignment depends on the bound entity rather than the source alone.

## Audit

The registry audit compares:

```text
registry seed IDs
live source_registry IDs
loaded profile and scope references
deprecated alias usage
unknown IDs
```

The 2026-07-24 audit checked 28 profiles and 731 source references. All references were canonical; the 16 seed IDs exactly matched the 16 live registry IDs.
