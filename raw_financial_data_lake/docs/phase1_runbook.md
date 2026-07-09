# Phase 1 Raw Data Lake Runbook

## Profiles

```text
config/profiles/dev.json         Local SQLite, small development scope
config/profiles/test.json        Known-good bounded test scope
config/profiles/prod_phase1.json PostgreSQL metadata, Phase 1 scale scope
```

## PostgreSQL

Production profile uses:

```text
metadata_backend.type = postgres
DATABASE_URL = postgresql://user:password@host:5432/finraw
```

Initialize:

```bash
DATABASE_URL="postgresql://..." python -m finraw.cli --config config/profiles/prod_phase1.json init-db
DATABASE_URL="postgresql://..." python -m finraw.cli --config config/profiles/prod_phase1.json seed-sources
```

## Recommended Run Order

```bash
DATABASE_URL="postgresql://..." python -m finraw.cli --config config/profiles/prod_phase1.json ingest sec-sample
DATABASE_URL="postgresql://..." python -m finraw.cli --config config/profiles/prod_phase1.json ingest sec-filings
DATABASE_URL="postgresql://..." python -m finraw.cli --config config/profiles/prod_phase1.json ingest fred
DATABASE_URL="postgresql://..." python -m finraw.cli --config config/profiles/prod_phase1.json ingest worldbank
DATABASE_URL="postgresql://..." python -m finraw.cli --config config/profiles/prod_phase1.json ingest imf
python -m finraw.cli discover-cninfo-batch --strategy config/scopes/cninfo_a_share_strategy.json --output config/cninfo_announcements.generated.json
DATABASE_URL="postgresql://..." python -m finraw.cli --config config/cninfo_announcements.generated.json ingest cninfo
DATABASE_URL="postgresql://..." python -m finraw.cli --config config/profiles/prod_phase1.json validate
DATABASE_URL="postgresql://..." python -m finraw.cli --config config/profiles/prod_phase1.json enforce-quality
```

## Resume

If a run is interrupted, rerun the same command with the same config. Existing objects are skipped when `(source_id, original_url, content_sha256)` already exists.

## Storage

See `docs/storage_budget.md`. Phase 1 local storage budget is 300 GB with a 500 GB minimum free-space guard.
