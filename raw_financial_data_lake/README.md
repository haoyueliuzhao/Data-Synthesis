# Raw Financial Data Lake

This project builds a traceable raw financial data lake for SEC, FRED, and
World Bank data. It stores original files/API responses on disk and records
metadata, checksums, jobs, source registry rows, raw records, and snapshots in
SQLite. The schema is intentionally close to the proposed PostgreSQL design so
it can be migrated later.

## Quick Start

```bash
cd "/root/Data Synthesis/raw_financial_data_lake"
python -m finraw.cli init-db
python -m finraw.cli seed-sources
python -m finraw.cli ingest all --dry-run
```

Run real ingestion:

```bash
python -m finraw.cli ingest sec-bulk
FRED_API_KEY=your_key python -m finraw.cli ingest fred
python -m finraw.cli ingest worldbank
```

Default outputs:

```text
./data/metadata.sqlite3
./data/fin_raw/
```



## FRED API Key

FRED ingestion reads the API key from `FRED_API_KEY` first, then from the ignored local secrets file `config/local_secrets.json`:

```json
{
  "fred": {
    "api_key": "your_32_character_key"
  }
}
```

Do not put API keys in `default_config.json` or `test_config.json`.

## Real Sample Test

Use the bounded test config to fetch a small real dataset without downloading SEC bulk ZIP files:

```bash
python -m finraw.cli --config config/test_config.json ingest test --dry-run
python -m finraw.cli --config config/test_config.json ingest test
python -m finraw.cli --config config/test_config.json validate
```

The `test` source fetches SEC company-level JSON for AAPL, MSFT, and TSLA plus World Bank GDP and population data for USA and CHN. Outputs go to:

```text
./data/test_metadata.sqlite3
./data/test_fin_raw/
```

## Commands

```bash
python -m finraw.cli init-db
python -m finraw.cli seed-sources
python -m finraw.cli ingest sec-bulk [--dry-run]
python -m finraw.cli ingest fred [--dry-run]
python -m finraw.cli ingest worldbank [--dry-run]
python -m finraw.cli ingest all [--dry-run]
python -m finraw.cli validate
```

## Design

The raw lake keeps original source material, not normalized facts:

```text
source_registry -> ingestion_jobs -> raw_objects -> raw_records -> snapshots
```

Every saved object has:

- source id
- original URL
- request params
- retrieval time
- content SHA-256
- size
- storage URI
- validation status

This lets later fact extraction and QA generation trace every answer back to
the original official source.


## Expanded Capabilities

Implemented beyond the initial skeleton:

- PostgreSQL migration DDL: `sql/postgres_schema.sql`
- JSONL export: `python -m finraw.cli export-jsonl data/exports/jsonl`
- Optional Parquet export: `python -m finraw.cli export-parquet data/exports/parquet`
- SEC filing primary document ingestion: `python -m finraw.cli ingest sec-filings`
- FRED series metadata, release, observations, and vintage dates
- World Bank country metadata, indicator metadata, paginated observations
- Configurable IMF raw SDMX/JSON/XML ingestion: `python -m finraw.cli ingest imf`
- Configurable CNInfo PDF ingestion: `python -m finraw.cli ingest cninfo`
- Source entity upserts for SEC, FRED, World Bank, and CNInfo
- Duplicate detection by `(source_id, original_url, content_sha256)`
- Snapshot IDs include a run-specific suffix to preserve same-day repeated runs
- Quality report: `python -m finraw.cli quality-report`

Small real end-to-end test:

```bash
python -m finraw.cli --config config/test_config.json ingest test --dry-run
python -m finraw.cli --config config/test_config.json ingest test
python -m finraw.cli --config config/test_config.json validate
python -m finraw.cli --config config/test_config.json quality-report
python -m finraw.cli --config config/test_config.json export-jsonl data/test_exports/jsonl
```

## Configuring IMF and CNInfo Targets

IMF does not have a single fixed default slice for this project. The official IMF API page says data is available through SDMX 2.1 and SDMX 3.0 APIs and points users to the IMF swagger page for endpoint exploration. Pick the dataset/slice in the IMF swagger portal, then place the raw URL in an `imf.targets` config. See `config/examples/imf_targets.example.json`.

CNInfo PDF URLs can now be discovered instead of hand-written:

```bash
python -m finraw.cli discover-cninfo \
  --stock "000001" \
  --start-date 2023-01-01 \
  --end-date 2024-12-31 \
  --category annual \
  --output config/cninfo_announcements.generated.json

python -m finraw.cli --config config/cninfo_announcements.generated.json ingest cninfo
```

The generated config has this shape:

```json
{
  "cninfo": {
    "announcements": [
      {
        "stock_code": "000001",
        "company_name": "...",
        "year": "2023",
        "report_type": "annual",
        "url": "https://static.cninfo.com.cn/...pdf"
      }
    ]
  }
}
```

## Phase 1 Scale Profiles

Prepared profiles and scope files for the previously discussed MVP scale:

```text
config/profiles/dev.json          local SQLite, smaller development run
config/profiles/test.json         bounded verified test run
config/profiles/prod_phase1.json  PostgreSQL metadata, Phase 1 scale run

config/scopes/sec_us_100.json                  SEC 100-company CIK list
config/scopes/fred_50.json                     FRED 50-series list
config/scopes/worldbank_20x20.json             World Bank 20 countries x 20 indicators
config/scopes/imf_datamapper_weo_targets.json  IMF WEO/DataMapper targets
config/scopes/cninfo_a_share_strategy.json     CNInfo discovery strategy
```

Production PostgreSQL profile expects `DATABASE_URL`:

```bash
DATABASE_URL="postgresql://user:password@host:5432/finraw" \
  python -m finraw.cli --config config/profiles/prod_phase1.json init-db
```

Runbook: `docs/phase1_runbook.md`.
Storage budget: `docs/storage_budget.md`.

Quality gates:

```bash
python -m finraw.cli --config config/test_config.json enforce-quality
```

Resume strategy: rerun the same command with the same config. Existing objects are skipped by `(source_id, canonical original_url including request params, content_sha256)`. Raw object IDs are derived from that same key to avoid collisions when different API requests return identical content.
