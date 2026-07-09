# Raw Financial Data Lake Storage Budget

## Current Local Storage

Checked on 2026-07-08:

```text
Filesystem: /root overlay
Total: 6.0T
Used: 3.7T
Available: 2.1T
Current project data: ~92M
```

## Phase 1 Storage Location

Use the local filesystem for the first scaled raw snapshot:

```text
/root/Data Synthesis/raw_financial_data_lake/data/fin_raw
```

This keeps the MVP simple and reproducible. The path is configurable through `storage_root`, so it can later move to MinIO/S3/NAS without changing connector logic.

## Phase 1 Budget

Recommended hard budget for the first production-scale run:

```text
storage_budget_bytes: 300 GB
minimum_free_bytes: 500 GB
```

Expected rough footprint:

```text
SEC 100 companyfacts/submissions JSON: < 2 GB
SEC 100 company filings primary documents, limited forms/years: 20-150 GB
FRED 50 series metadata/observations/release/vintages: < 5 GB
World Bank 20 countries x 20 indicators x 30 years: < 1 GB
CNInfo selected reports, if enabled: highly variable, 5-100 GB for modest pools
IMF selected targets: usually < 10 GB for bounded slices
```

## Migration Target

When the data lake grows beyond a single-node MVP, use one of:

```text
MinIO: s3://fin-raw/
AWS S3: s3://<bucket>/fin_raw/
NAS mount: /mnt/fin_raw/
```

Keep PostgreSQL for metadata and store only `storage_uri` references in the DB.
