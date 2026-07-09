# CNInfo discovery examples

Generate a config fragment of annual report PDF URLs:

```bash
python -m finraw.cli discover-cninfo \
  --stock "000001" \
  --start-date 2023-01-01 \
  --end-date 2024-12-31 \
  --category annual \
  --output config/cninfo_announcements.generated.json
```

Then ingest with the generated config:

```bash
python -m finraw.cli --config config/cninfo_announcements.generated.json ingest cninfo
```

If CNInfo requires the exchange selector, use the website-style stock value, for example:

```bash
python -m finraw.cli discover-cninfo --stock "000001,gssz0000001" --start-date 2023-01-01 --end-date 2024-12-31
```
